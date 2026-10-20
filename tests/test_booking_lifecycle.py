from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest
from sqlalchemy import create_engine, event, inspect

from equipment_lending import migrate_db
from equipment_lending.dao.booking_dao import BookingDao
from equipment_lending.model.booking import Booking
from equipment_lending.service.booking_service import BookingService


def approve(client, headers, booking_id):
    response = client.post(f"/admin/bookings/{booking_id}/approve", json={}, headers=headers["admin"])
    assert response.status_code == 200
    return response.json()


def test_full_handover_records_server_times_and_preserves_history(review):
    client, factory, headers, record, _ = review
    booking_id = record["id"]
    assert record["picked_up_at"] is None
    assert record["returned_at"] is None
    assert record["is_overdue"] is False
    approve(client, headers, booking_id)
    before = datetime.now(UTC)
    pickup = client.post(f"/admin/bookings/{booking_id}/pickup", json={}, headers=headers["admin"])
    after = datetime.now(UTC)
    assert pickup.status_code == 200
    picked = pickup.json()
    pickup_time = datetime.fromisoformat(picked["picked_up_at"])
    assert before <= pickup_time <= after
    assert pickup_time.utcoffset() == timedelta(0)
    assert picked["status"] == "borrowed"
    assert picked["returned_at"] is None
    assert client.post(f"/bookings/{booking_id}/cancel", headers=headers["member"]).status_code == 409
    before = datetime.now(UTC)
    returned = client.post(f"/admin/bookings/{booking_id}/return", json={}, headers=headers["admin"])
    after = datetime.now(UTC)
    assert returned.status_code == 200
    result = returned.json()
    assert result["status"] == "returned"
    assert result["picked_up_at"] == picked["picked_up_at"]
    assert before <= datetime.fromisoformat(result["returned_at"]) <= after
    assert result["is_overdue"] is False
    assert client.post(f"/admin/bookings/{booking_id}/return", json={}, headers=headers["admin"]).status_code == 409
    with factory() as session:
        stored = session.get(Booking, booking_id)
        assert stored.picked_up_at.replace(tzinfo=UTC) == pickup_time
        assert stored.returned_at.replace(tzinfo=UTC) == datetime.fromisoformat(result["returned_at"])
        assert stored.purpose == record["purpose"]
        assert stored.start_date.isoformat() == record["start_date"]
        assert stored.end_date.isoformat() == record["end_date"]
    owner_view = client.get(f"/bookings/{booking_id}", headers=headers["member"]).json()
    assert owner_view["picked_up_at"] == picked["picked_up_at"]
    assert owner_view["returned_at"] == result["returned_at"]


@pytest.mark.parametrize("action", ["pickup", "return"])
def test_handover_requires_admin(review, action):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = "approved" if action == "pickup" else "borrowed"
    path = f"/admin/bookings/{record['id']}/{action}"
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.post(path, json={}, headers=headers["member"]).status_code == 403
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert stored.status == ("approved" if action == "pickup" else "borrowed")
        assert stored.picked_up_at is None and stored.returned_at is None


@pytest.mark.parametrize("status", ["pending", "approved", "borrowed", "returned", "rejected", "cancelled"])
@pytest.mark.parametrize("action,required", [("pickup", "approved"), ("return", "borrowed")])
def test_handover_enforces_state_transitions(review, status, action, required):
    client, factory, headers, record, _ = review
    original_time = datetime(2020, 1, 1, 12)
    with factory.begin() as session:
        stored = session.get(Booking, record["id"])
        stored.status = status
        if status in ("borrowed", "returned"):
            stored.picked_up_at = original_time
        if status == "returned":
            stored.returned_at = original_time + timedelta(days=1)
    response = client.post(f"/admin/bookings/{record['id']}/{action}", json={}, headers=headers["admin"])
    assert response.status_code == (200 if status == required else 409)
    with factory() as session:
        stored = session.get(Booking, record["id"])
        if status != required:
            assert stored.status == status
            assert stored.picked_up_at == (original_time if status in ("borrowed", "returned") else None)
            assert stored.returned_at == (original_time + timedelta(days=1) if status == "returned" else None)


@pytest.mark.parametrize("action", ["pickup", "return"])
@pytest.mark.parametrize("forged", [{"status": "returned"}, {"picked_up_at": "2000-01-01T00:00:00Z"},
                                    {"returned_at": "2000-01-01T00:00:00Z"}, {"user_id": 1}])
def test_client_cannot_set_handover_status_or_timestamps(review, action, forged):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = "approved" if action == "pickup" else "borrowed"
    assert client.post(f"/admin/bookings/{record['id']}/{action}", json=forged,
                       headers=headers["admin"]).status_code == 422
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert stored.picked_up_at is None and stored.returned_at is None


@pytest.mark.parametrize("action", ["pickup", "return"])
def test_handover_missing_reservation(review, action):
    client, _, headers, _, _ = review
    assert client.post(f"/admin/bookings/9999/{action}", json={}, headers=headers["admin"]).status_code == 404


@pytest.mark.parametrize("action,status", [("pickup", "approved"), ("return", "borrowed")])
def test_handover_failure_rolls_back_status_and_actual_time(review, monkeypatch, action, status):
    _, factory, _, record, _ = review
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = status

    def fail_after_flush(*_):
        raise RuntimeError("Handover failed after flush")

    monkeypatch.setattr(BookingDao, "find_for_admin", fail_after_flush)
    with factory() as session, pytest.raises(RuntimeError, match="after flush"):
        service = BookingService(session)
        (service.pickup_booking if action == "pickup" else service.return_booking)(record["id"])
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert stored.status == status
        assert stored.picked_up_at is None and stored.returned_at is None


@pytest.mark.parametrize("status", ["pending", "approved", "borrowed", "returned", "rejected", "cancelled"])
@pytest.mark.parametrize("end_offset", [-1, 0, 1])
def test_overdue_is_only_for_borrowed_and_after_end_date(review, status, end_offset):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        stored = session.get(Booking, record["id"])
        stored.start_date = date.today() + timedelta(days=end_offset - 2)
        stored.end_date = date.today() + timedelta(days=end_offset)
        stored.status = status
    expected = status == "borrowed" and end_offset < 0
    for path, role in [(f"/bookings/{record['id']}", "member"), ("/my-bookings", "member"), ("/admin/bookings", "admin")]:
        response = client.get(path, headers=headers[role])
        assert response.status_code == 200
        value = response.json()
        booking = value[0] if isinstance(value, list) else value
        assert booking["is_overdue"] is expected
        assert booking["status"] == status
    page = client.get("/admin", headers=headers["admin"])
    assert (" — Overdue" in page.text) is expected


def test_returning_overdue_legacy_booking_clears_badge_without_fabricating_pickup(review):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        stored = session.get(Booking, record["id"])
        stored.start_date, stored.end_date = date.today() - timedelta(days=3), date.today() - timedelta(days=1)
        stored.status = "borrowed"
    assert client.get("/my-bookings", headers=headers["member"]).json()[0]["is_overdue"] is True
    response = client.post(f"/admin/bookings/{record['id']}/return", json={}, headers=headers["admin"])
    assert response.status_code == 200
    assert response.json()["is_overdue"] is False
    assert response.json()["picked_up_at"] is None
    assert response.json()["returned_at"] is not None


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_pickup_and_cancellation_cannot_both_succeed(review, journal_mode):
    client, factory, headers, record, _ = review
    approve(client, headers, record["id"])
    with factory.kw["bind"].connect() as connection:
        connection.exec_driver_sql(f"PRAGMA journal_mode={journal_mode}")
    gate = Barrier(2)

    def perform(path, role):
        gate.wait(timeout=5)
        return client.post(path, json={}, headers=headers[role])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(perform, f"/admin/bookings/{record['id']}/pickup", "admin"),
                   pool.submit(perform, f"/bookings/{record['id']}/cancel", "member")]
        responses = [future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert stored.status in ("borrowed", "cancelled")
        assert (stored.picked_up_at is not None) == (stored.status == "borrowed")
        assert stored.returned_at is None


@pytest.mark.parametrize("action,status", [("pickup", "approved"), ("return", "borrowed")])
def test_duplicate_concurrent_handover_only_records_once(review, action, status):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = status
    gate = Barrier(2)

    def perform():
        gate.wait(timeout=5)
        return client.post(f"/admin/bookings/{record['id']}/{action}", json={}, headers=headers["admin"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result(timeout=10) for future in [pool.submit(perform), pool.submit(perform)]]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    with factory() as session:
        stored = session.get(Booking, record["id"])
        field = "picked_up_at" if action == "pickup" else "returned_at"
        assert getattr(stored, field).replace(tzinfo=UTC) == datetime.fromisoformat(winner[field])


@pytest.mark.parametrize("action", ["pickup", "return", "cancel"])
def test_busy_database_returns_retryable_error_without_partial_handover(review, action):
    client, factory, headers, record, _ = review
    initial_status = "borrowed" if action == "return" else "approved"
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = initial_status
    engine = factory.kw["bind"]

    def short_timeout(connection, _record, _proxy):
        connection.execute("PRAGMA busy_timeout=50")

    event.listen(engine, "checkout", short_timeout)
    try:
        path = f"/bookings/{record['id']}/cancel" if action == "cancel" else f"/admin/bookings/{record['id']}/{action}"
        role = "member" if action == "cancel" else "admin"
        with sqlite3.connect(engine.url.database) as writer:
            writer.execute("BEGIN IMMEDIATE")
            response = client.post(path, json={}, headers=headers[role])
            assert response.status_code == 503
            assert response.headers["retry-after"] == "1"
            writer.rollback()
        with factory() as session:
            stored = session.get(Booking, record["id"])
            assert stored.status == initial_status
            assert stored.picked_up_at is None and stored.returned_at is None
    finally:
        event.remove(engine, "checkout", short_timeout)


def test_member_page_is_private_shell_and_login_returns_to_it(review):
    client, _, headers, record, _ = review
    response = client.get("/account/bookings")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "Community event" not in response.text
    assert 'href="/login?next=/account/bookings"' in response.text
    assert '/static/my_bookings.js' in response.text
    assert 'data-next="/account/bookings"' in client.get("/login?next=/account/bookings").text
    assert client.get("/my-bookings").status_code == 401
    assert client.get("/my-bookings", headers=headers["member"]).headers["cache-control"] == "no-store"
    for path in ["/account/bookings//example.org", "https://example.org/account/bookings"]:
        assert client.get("/login", params={"next": path}).status_code == 422


@pytest.mark.parametrize("method", ["sql", "command"])
def test_handover_upgrade_preserves_old_status_notes_and_unknown_actual_times(tmp_path, monkeypatch, method):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, status TEXT, admin_notes TEXT)")
        connection.execute("INSERT INTO bookings VALUES (1, 'borrowed', 'Historic staff note')")
    engine = create_engine(f"sqlite:///{path}")
    try:
        if method == "sql":
            script = Path(__file__).resolve().parents[1] / "migrations/004_booking_handover_times.sql"
            with sqlite3.connect(path) as connection:
                connection.executescript(script.read_text())
        else:
            monkeypatch.setattr(migrate_db, "engine", engine)
            migrate_db.migrate_db()
            migrate_db.migrate_db()
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT * FROM bookings").fetchall() == [(1, "borrowed", "Historic staff note", None, None)]
    finally:
        engine.dispose()


def test_upgrade_resumes_partial_handover_migration_without_overwriting_times(tmp_path, monkeypatch):
    path = tmp_path / "partial.db"
    pickup_time = "2020-01-01 12:00:00"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, status TEXT, admin_notes TEXT, picked_up_at DATETIME)")
        connection.execute("INSERT INTO bookings VALUES (1, 'borrowed', 'Staff note', ?)", (pickup_time,))
    engine = create_engine(f"sqlite:///{path}")
    try:
        monkeypatch.setattr(migrate_db, "engine", engine)
        migrate_db.migrate_db()
        migrate_db.migrate_db()
        assert {column["name"] for column in inspect(engine).get_columns("bookings")} >= {"picked_up_at", "returned_at"}
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT picked_up_at, returned_at FROM bookings").fetchall() == [(pickup_time, None)]
    finally:
        engine.dispose()
