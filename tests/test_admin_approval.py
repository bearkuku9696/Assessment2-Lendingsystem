from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
import sqlite3
from threading import Barrier, Event, Lock

import pytest
from sqlalchemy import create_engine, event, select

from equipment_lending import migrate_db
from equipment_lending.dao.booking_dao import BookingDao
from equipment_lending.model.booking import Booking
from equipment_lending.model.equipment import Equipment
from equipment_lending.service.authentication_service import AuthenticationService
from equipment_lending.service.booking_service import BookingService


@pytest.fixture
def review(auth):
    client, factory = auth
    with factory() as session:
        AuthenticationService(session).register("Applicant", "member@example.org", "Password123!")
        AuthenticationService(session).register("Admin", "admin@example.org", "Password123!", role="admin")
    headers = {}
    for role, email in [("member", "member@example.org"), ("admin", "admin@example.org")]:
        token = client.post("/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
        headers[role] = {"Authorization": f"Bearer {token}"}
    equipment = client.post("/admin/equipment", headers=headers["admin"], json={
        "name": "Camera", "category": "Photography", "location": "Room A",
    }).json()
    payload = {
        "equipment_id": equipment["id"], "purpose": "Community event",
        "start_date": (date.today() + timedelta(days=3)).isoformat(),
        "end_date": (date.today() + timedelta(days=7)).isoformat(),
    }
    response = client.post("/bookings", headers=headers["member"], json=payload)
    assert response.status_code == 201
    return client, factory, headers, response.json(), payload


def test_admin_listing_and_html_show_applicant_and_equipment(review):
    client, _, headers, record, _ = review
    response = client.get("/admin/bookings", headers=headers["admin"])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == [{**record, "applicant_name": "Applicant",
                               "applicant_email": "member@example.org", "equipment_name": "Camera", "admin_notes": ""}]
    page = client.get("/admin", headers=headers["admin"])
    for text in ["Applicant", "member@example.org", "Camera", record["start_date"], record["end_date"]]:
        assert text in page.text
    assert "password_hash" not in response.text


def test_browser_review_shell_and_login_destination(review):
    client, _, _, _, _ = review
    response = client.get("/admin/review")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "member@example.org" not in response.text
    assert "Community event" not in response.text
    assert '/static/admin.js' in response.text
    assert 'href="/login?next=/admin/review"' in response.text
    assert 'data-next="/admin/review"' in client.get("/login?next=/admin/review").text
    assert client.get("/login?next=//example.org/admin/review").status_code == 422


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_review_requires_admin(review, action):
    client, factory, headers, record, _ = review
    path = f"/admin/bookings/{record['id']}/{action}"
    data = {"admin_notes": "Review reason"}
    assert client.post(path, json=data).status_code == 401
    assert client.post(path, json=data, headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.post(path, json=data, headers=headers["member"]).status_code == 403
    with factory() as session:
        booking = session.get(Booking, record["id"])
        assert (booking.status, booking.admin_notes) == ("pending", "")


@pytest.mark.parametrize("action,status", [("approve", "approved"), ("reject", "rejected")])
def test_review_saves_decision_and_trimmed_notes(review, action, status):
    client, factory, headers, record, _ = review
    response = client.post(f"/admin/bookings/{record['id']}/{action}",
                           json={"admin_notes": "  Staff decision  "}, headers=headers["admin"])
    assert response.status_code == 200
    assert response.json()["status"] == status
    assert response.json()["admin_notes"] == "Staff decision"
    assert response.json()["applicant_email"] == "member@example.org"
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert (stored.status, stored.admin_notes) == (status, "Staff decision")
    assert client.get(f"/bookings/{record['id']}", headers=headers["member"]).json()["status"] == status


def test_approval_notes_are_optional(review):
    client, _, headers, record, _ = review
    response = client.post(f"/admin/bookings/{record['id']}/approve", json={}, headers=headers["admin"])
    assert response.status_code == 200
    assert response.json()["admin_notes"] == ""


@pytest.mark.parametrize("action,body", [
    ("reject", {}), ("reject", {"admin_notes": ""}), ("reject", {"admin_notes": " \n "}),
    ("reject", {"admin_notes": "x" * 2001}), ("approve", {"admin_notes": "x" * 2001}),
    ("approve", {"status": "approved"}), ("reject", {"admin_notes": "Reason", "user_id": 99}),
])
def test_invalid_review_does_not_modify_booking(review, action, body):
    client, factory, headers, record, _ = review
    assert client.post(f"/admin/bookings/{record['id']}/{action}", json=body,
                       headers=headers["admin"]).status_code == 422
    with factory() as session:
        assert session.get(Booking, record["id"]).status == "pending"
        assert session.get(Booking, record["id"]).admin_notes == ""


@pytest.mark.parametrize("status", ["approved", "rejected", "borrowed", "returned", "cancelled"])
@pytest.mark.parametrize("action", ["approve", "reject"])
def test_only_pending_reservations_can_be_reviewed(review, status, action):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        booking = session.get(Booking, record["id"])
        booking.status, booking.admin_notes = status, "Original note"
    response = client.post(f"/admin/bookings/{record['id']}/{action}",
                           json={"admin_notes": "Replacement"}, headers=headers["admin"])
    assert response.status_code == 409
    with factory() as session:
        booking = session.get(Booking, record["id"])
        assert (booking.status, booking.admin_notes) == (status, "Original note")


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_review_missing_booking(review, action):
    client, _, headers, _, _ = review
    assert client.post(f"/admin/bookings/9999/{action}", json={"admin_notes": "Reason"},
                       headers=headers["admin"]).status_code == 404


@pytest.mark.parametrize("start,end,expected", [
    (0, 2, 200), (0, 3, 409), (2, 4, 409), (3, 7, 409),
    (4, 6, 409), (2, 8, 409), (6, 8, 409), (7, 9, 409), (8, 10, 200),
])
def test_approval_rechecks_inclusive_date_conflicts(review, start, end, expected):
    client, factory, headers, first, payload = review
    pending = client.post("/bookings", headers=headers["member"], json={
        **payload, "start_date": (date.today() + timedelta(days=start)).isoformat(),
        "end_date": (date.today() + timedelta(days=end)).isoformat(),
    }).json()
    assert client.post(f"/admin/bookings/{first['id']}/approve", json={}, headers=headers["admin"]).status_code == 200
    response = client.post(f"/admin/bookings/{pending['id']}/approve",
                           json={"admin_notes": "Second decision"}, headers=headers["admin"])
    assert response.status_code == expected
    with factory() as session:
        stored = session.get(Booking, pending["id"])
        assert stored.status == ("approved" if expected == 200 else "pending")
        assert stored.admin_notes == ("Second decision" if expected == 200 else "")


@pytest.mark.parametrize("status,expected", [
    ("approved", 409), ("borrowed", 409), ("pending", 200),
    ("returned", 200), ("rejected", 200), ("cancelled", 200),
])
def test_approval_conflict_blocking_statuses(review, status, expected):
    client, factory, headers, first, payload = review
    other = client.post("/bookings", headers=headers["member"], json=payload).json()
    with factory.begin() as session:
        session.get(Booking, first["id"]).status = status
    assert client.post(f"/admin/bookings/{other['id']}/approve", json={},
                       headers=headers["admin"]).status_code == expected


def test_approval_conflicts_are_per_equipment(review):
    client, factory, headers, first, payload = review
    other_equipment = client.post("/admin/equipment", headers=headers["admin"], json={
        "name": "Projector", "category": "Video", "location": "Room B",
    }).json()
    other = client.post("/bookings", headers=headers["member"], json={
        **payload, "equipment_id": other_equipment["id"],
    }).json()
    for booking_id in [first["id"], other["id"]]:
        assert client.post(f"/admin/bookings/{booking_id}/approve", json={}, headers=headers["admin"]).status_code == 200
    with factory() as session:
        assert len(session.scalars(select(Booking).where(Booking.status == "approved")).all()) == 2


@pytest.mark.parametrize("status", ["maintenance", "inactive"])
def test_approval_rechecks_equipment_availability_but_rejection_is_allowed(review, status):
    client, factory, headers, record, _ = review
    with factory.begin() as session:
        session.get(Equipment, record["equipment_id"]).status = status
    assert client.post(f"/admin/bookings/{record['id']}/approve", json={}, headers=headers["admin"]).status_code == 409
    assert client.post(f"/admin/bookings/{record['id']}/reject", json={"admin_notes": "Unavailable"},
                       headers=headers["admin"]).status_code == 200


def test_failed_review_rolls_back_status_and_notes(review, monkeypatch):
    _, factory, _, record, _ = review

    def fail_after_update(*_):
        raise RuntimeError("Simulated failure after flush")

    monkeypatch.setattr(BookingDao, "find_for_admin", fail_after_update)
    with factory() as session, pytest.raises(RuntimeError, match="Simulated failure"):
        BookingService(session).approve_booking(record["id"], "Must not persist")
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert (stored.status, stored.admin_notes) == ("pending", "")


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_competing_overlapping_approvals_are_serialized(review, monkeypatch, journal_mode):
    client, factory, headers, first, payload = review
    second = client.post("/bookings", headers=headers["member"], json=payload).json()
    engine = factory.kw["bind"]
    with engine.connect() as connection:
        assert connection.exec_driver_sql(f"PRAGMA journal_mode={journal_mode}").scalar().upper() == journal_mode
    first_checked, second_begin, release = Event(), Event(), Event()
    counter_lock = Lock()
    begins = 0
    original = BookingDao.has_conflict

    def observe_begin(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal begins
        if statement == "BEGIN IMMEDIATE":
            with counter_lock:
                begins += 1
                if begins == 2:
                    second_begin.set()

    def pause_first_check(self, *args):
        result = original(self, *args)
        if not first_checked.is_set():
            first_checked.set()
            assert release.wait(10), "First approval was not released"
        return result

    monkeypatch.setattr(BookingDao, "has_conflict", pause_first_check)
    event.listen(engine, "before_cursor_execute", observe_begin)

    def approve(booking_id):
        return client.post(f"/admin/bookings/{booking_id}/approve", json={}, headers=headers["admin"])

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(approve, first["id"])
            try:
                assert first_checked.wait(5), "First approval did not reach its conflict check"
                second_future = pool.submit(approve, second["id"])
                assert second_begin.wait(5), "Second approval did not attempt its write transaction"
            finally:
                release.set()
            assert first_future.result(timeout=10).status_code == 200
            assert second_future.result(timeout=10).status_code == 409
    finally:
        event.remove(engine, "before_cursor_execute", observe_begin)
    with factory() as session:
        assert session.get(Booking, first["id"]).status == "approved"
        assert session.get(Booking, second["id"]).status == "pending"


def test_competing_decisions_on_same_booking_only_save_once(review):
    client, factory, headers, record, _ = review
    gate = Barrier(2)

    def decide(action):
        gate.wait(timeout=5)
        return client.post(f"/admin/bookings/{record['id']}/{action}",
                           json={"admin_notes": action}, headers=headers["admin"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(decide, action) for action in ["approve", "reject"]]
        responses = [future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    with factory() as session:
        stored = session.get(Booking, record["id"])
        assert (stored.status, stored.admin_notes) == (winner["status"], winner["admin_notes"])


def test_external_writer_timeout_returns_retryable_error_without_saving(review):
    client, factory, headers, record, _ = review
    engine = factory.kw["bind"]

    def short_timeout(dbapi_connection, _record, _proxy):
        dbapi_connection.execute("PRAGMA busy_timeout=50")

    event.listen(engine, "checkout", short_timeout)
    try:
        with sqlite3.connect(engine.url.database) as writer:
            writer.execute("BEGIN IMMEDIATE")
            response = client.post(f"/admin/bookings/{record['id']}/approve",
                                   json={"admin_notes": "Try later"}, headers=headers["admin"])
            assert response.status_code == 503
            assert response.headers["retry-after"] == "1"
            writer.rollback()
        with factory() as session:
            stored = session.get(Booking, record["id"])
            assert (stored.status, stored.admin_notes) == ("pending", "")
        assert client.post(f"/admin/bookings/{record['id']}/approve", json={},
                           headers=headers["admin"]).status_code == 200
    finally:
        event.remove(engine, "checkout", short_timeout)


def test_review_notes_and_applicant_details_are_escaped(review):
    client, factory, headers, record, _ = review
    note = '<img src=x onerror="alert(1)">'
    assert client.post(f"/admin/bookings/{record['id']}/reject", json={"admin_notes": note},
                       headers=headers["admin"]).status_code == 200
    page = client.get("/admin", headers=headers["admin"])
    assert '<img src=x' not in page.text
    assert '&lt;img src=x' in page.text
    assert 'admin_notes' not in client.get(f"/bookings/{record['id']}", headers=headers["member"]).json()


@pytest.mark.parametrize("method", ["sql", "command"])
def test_upgrade_preserves_existing_booking_and_is_repeatable_for_command(tmp_path, monkeypatch, method):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, status VARCHAR(20), purpose VARCHAR(1000))")
        connection.execute("INSERT INTO bookings VALUES (1, 'pending', 'Existing activity')")
    engine = create_engine(f"sqlite:///{path}")
    try:
        if method == "sql":
            script = Path(__file__).resolve().parents[1] / "migrations" / "003_booking_admin_notes.sql"
            with sqlite3.connect(path) as connection:
                connection.executescript(script.read_text())
        else:
            monkeypatch.setattr(migrate_db, "engine", engine)
            migrate_db.migrate_db()
            migrate_db.migrate_db()
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT * FROM bookings").fetchall() == [(1, "pending", "Existing activity", "")]
    finally:
        engine.dispose()


def test_upgrade_is_safe_on_current_database(review, monkeypatch):
    _, factory, _, record, _ = review
    monkeypatch.setattr(migrate_db, "engine", factory.kw["bind"])
    migrate_db.migrate_db()
    with factory() as session:
        assert session.get(Booking, record["id"]).status == "pending"
