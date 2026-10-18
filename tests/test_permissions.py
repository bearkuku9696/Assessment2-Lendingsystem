from datetime import date, datetime, timedelta
from hashlib import sha256
import sys

import pytest
from sqlalchemy import select

from equipment_lending import create_admin, init_db
from equipment_lending.model.booking import Booking
from equipment_lending.model.equipment import Equipment
from equipment_lending.model.login_session import LoginSession
from equipment_lending.model.user import User
from equipment_lending.service.authentication_service import AuthenticationService


PASSWORD = "Password123!"


def sign_in(client, email):
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def accounts(auth):
    client, factory = auth
    for name in ("alice", "bob"):
        response = client.post("/auth/register", json={
            "name": name, "email": f"{name}@example.org", "password": PASSWORD,
        })
        assert response.status_code == 201
    with factory() as session:
        AuthenticationService(session).register("Administrator", "admin@example.org", PASSWORD, role="admin")
    headers = {name: sign_in(client, f"{name}@example.org") for name in ("alice", "bob", "admin")}
    return client, factory, headers


@pytest.fixture
def booking(accounts):
    client, factory, headers = accounts
    equipment = client.post("/admin/equipment", json={
        "name": "Camera", "category": "Photography", "location": "Room A",
    }, headers=headers["admin"])
    assert equipment.status_code == 201
    data = {
        "equipment_id": equipment.json()["id"],
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=2)).isoformat(),
        "purpose": "Community event",
    }
    response = client.post("/bookings", json=data, headers=headers["alice"])
    assert response.status_code == 201
    return client, factory, headers, response.json(), data


def test_logout_revokes_only_current_session(accounts):
    client, factory, headers = accounts
    another_login = sign_in(client, "alice@example.org")
    token = headers["alice"]["Authorization"].removeprefix("Bearer ")
    assert client.post("/auth/logout", headers=headers["alice"]).status_code == 204
    assert client.get("/auth/me", headers=headers["alice"]).status_code == 401
    assert client.get("/my-bookings", headers=headers["alice"]).status_code == 401
    assert client.post("/auth/logout", headers=headers["alice"]).status_code == 401
    assert client.get("/auth/me", headers=another_login).status_code == 200
    assert client.get("/auth/me", headers=headers["bob"]).status_code == 200
    with factory() as session:
        assert session.get(LoginSession, sha256(token.encode()).hexdigest()) is None


@pytest.mark.parametrize("method,path,body", [
    ("get", "/admin", None),
    ("get", "/admin/bookings", None),
    ("post", "/admin/equipment", {"name": "Camera", "category": "Photography", "location": "Room A"}),
])
def test_admin_permissions(accounts, method, path, body):
    client, factory, headers = accounts
    assert client.request(method, path, json=body).status_code == 401
    assert client.request(method, path, json=body, headers=headers["alice"]).status_code == 403
    with factory() as session:
        assert session.scalar(select(Equipment)) is None
    assert client.request(method, path, json=body, headers=headers["admin"]).status_code in (200, 201)


@pytest.mark.parametrize("method,path", [
    ("get", "/my-bookings"), ("get", "/bookings/1"),
    ("post", "/bookings/1/cancel"), ("post", "/auth/logout"),
])
def test_protected_routes_require_login(auth, method, path):
    client, _ = auth
    assert client.request(method, path).status_code == 401
    assert client.request(method, path, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_booking_ownership_and_cancellation(booking):
    client, factory, headers, record, data = booking
    other = client.post("/bookings", json=data, headers=headers["bob"]).json()
    assert client.get("/my-bookings", headers=headers["alice"]).json() == [record]
    assert client.get("/my-bookings", headers=headers["bob"]).json() == [other]
    url = f"/bookings/{record['id']}"
    assert client.get(url, headers=headers["alice"]).json() == record
    assert client.get(url, headers=headers["bob"]).status_code == 403
    assert client.post(url + "/cancel", headers=headers["bob"]).status_code == 403
    with factory() as session:
        assert session.get(Booking, record["id"]).status == "pending"
    response = client.post(url + "/cancel", headers=headers["alice"])
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    with factory() as session:
        assert session.get(Booking, record["id"]).status == "cancelled"
        assert session.get(Booking, other["id"]).status == "pending"
    assert client.post(url + "/cancel", headers=headers["alice"]).status_code == 409
    assert len(client.get("/admin/bookings", headers=headers["admin"]).json()) == 2
    init_db.init_db()
    assert len(client.get("/admin/bookings", headers=headers["admin"]).json()) == 2


def test_booking_cannot_impersonate_other_user(booking):
    client, _, headers, record, data = booking
    response = client.post("/bookings", json={**data, "user_id": record["user_id"]}, headers=headers["bob"])
    assert response.status_code == 422
    assert client.get("/my-bookings", headers=headers["bob"]).json() == []
    assert client.post("/bookings", json=data).status_code == 401


@pytest.mark.parametrize("changes", [
    {"purpose": " "}, {"status": "approved"},
    {"start_date": (date.today() - timedelta(days=1)).isoformat()},
    {"end_date": date.today().isoformat()}, {"equipment_id": 0},
])
def test_invalid_booking_is_not_saved(booking, changes):
    client, factory, headers, _, data = booking
    assert client.post("/bookings", json={**data, **changes}, headers=headers["alice"]).status_code == 422
    with factory() as session:
        assert len(session.scalars(select(Booking)).all()) == 1


def test_missing_equipment_and_booking(booking):
    client, _, headers, _, data = booking
    assert client.post("/bookings", json={**data, "equipment_id": 9999}, headers=headers["alice"]).status_code == 404
    assert client.get("/bookings/9999", headers=headers["alice"]).status_code == 404
    assert client.post("/bookings/9999/cancel", headers=headers["alice"]).status_code == 404


@pytest.mark.parametrize("status,expected", [
    ("approved", 200), ("borrowed", 409), ("returned", 409), ("rejected", 409),
])
def test_cancellation_status_rules(booking, status, expected):
    client, factory, headers, record, _ = booking
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = status
    assert client.post(f"/bookings/{record['id']}/cancel", headers=headers["alice"]).status_code == expected
    with factory() as session:
        assert session.get(Booking, record["id"]).status == ("cancelled" if expected == 200 else status)


def test_expired_admin_token_is_denied(accounts):
    client, factory, headers = accounts
    token = headers["admin"]["Authorization"].removeprefix("Bearer ")
    with factory.begin() as session:
        session.get(LoginSession, sha256(token.encode()).hexdigest()).expires_at = datetime(2000, 1, 1)
    assert client.get("/admin", headers=headers["admin"]).status_code == 401
    assert client.post("/auth/logout", headers=headers["admin"]).status_code == 401


def test_admin_page_escapes_user_input(booking):
    client, _, headers, _, data = booking
    assert client.post("/bookings", json={**data, "purpose": "<script>alert(1)</script>"},
                       headers=headers["alice"]).status_code == 201
    response = client.get("/admin", headers=headers["admin"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert "Community event" in response.text
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_create_admin_command(auth, monkeypatch, capsys):
    client, factory = auth
    monkeypatch.setattr(create_admin, "SessionLocal", factory)
    monkeypatch.setattr(create_admin, "getpass", lambda _: PASSWORD)
    monkeypatch.setattr(sys, "argv", ["create_admin", "--name", " Admin ", "--email", " ADMIN@example.org "])
    create_admin.main()
    assert "Administrator created: admin@example.org" in capsys.readouterr().out
    headers = sign_in(client, "admin@example.org")
    assert client.get("/auth/me", headers=headers).json()["role"] == "admin"
    assert client.get("/admin", headers=headers).status_code == 200
    with pytest.raises(SystemExit):
        create_admin.main()
    with factory() as session:
        assert len(session.scalars(select(User)).all()) == 1


def test_create_admin_rejects_mismatched_passwords(auth, monkeypatch):
    _, factory = auth
    monkeypatch.setattr(create_admin, "SessionLocal", factory)
    passwords = iter([PASSWORD, "different"])
    monkeypatch.setattr(create_admin, "getpass", lambda _: next(passwords))
    monkeypatch.setattr(sys, "argv", ["create_admin", "--name", "Admin", "--email", "admin@example.org"])
    with pytest.raises(SystemExit):
        create_admin.main()
    with factory() as session:
        assert session.scalar(select(User)) is None


def test_booking_page_and_catalogue_link(booking):
    client, _, _, record, data = booking
    path = f"/equipment/{data['equipment_id']}/book"
    assert f'href="{path}"' in client.get("/").text
    response = client.get(path)
    assert response.status_code == 200
    assert "Book Camera" in response.text
    assert 'name="start_date"' in response.text
    assert f'min="{date.today().isoformat()}"' in response.text
    assert 'name="end_date"' in response.text
    assert 'name="purpose"' in response.text
    assert 'id="login-form"' in response.text
    assert 'id="booking-fields" disabled' in response.text
    assert client.get("/equipment/9999/book").status_code == 404


@pytest.mark.parametrize("status", ["maintenance", "inactive"])
def test_unavailable_equipment_cannot_be_requested(booking, status):
    client, factory, headers, _, data = booking
    with factory.begin() as session:
        session.get(Equipment, data["equipment_id"]).status = status
    path = f"/equipment/{data['equipment_id']}/book"
    assert f'href="{path}"' not in client.get("/").text
    assert client.get(path).status_code == 409
    assert client.post("/bookings", json=data, headers=headers["alice"]).status_code == 409
    with factory() as session:
        assert len(session.scalars(select(Booking)).all()) == 1


@pytest.mark.parametrize("offset,expected", [(-1, 422), (0, 201), (1, 201)])
def test_booking_start_date_boundary(booking, offset, expected):
    client, factory, headers, _, data = booking
    data = {**data, "start_date": (date.today() + timedelta(days=offset)).isoformat(),
            "end_date": (date.today() + timedelta(days=3)).isoformat(), "purpose": " Workshop "}
    response = client.post("/bookings", json=data, headers=headers["alice"])
    assert response.status_code == expected
    with factory() as session:
        assert len(session.scalars(select(Booking)).all()) == (2 if expected == 201 else 1)
        if expected == 201:
            stored = session.get(Booking, response.json()["id"])
            assert stored.start_date.isoformat() == data["start_date"]
            assert stored.end_date.isoformat() == data["end_date"]
            assert stored.purpose == "Workshop"
            assert stored.status == "pending"


@pytest.mark.parametrize("end_offset,expected", [(1, 422), (2, 422), (3, 201)])
def test_booking_end_date_must_follow_start(booking, end_offset, expected):
    client, factory, headers, _, data = booking
    response = client.post("/bookings", json={
        **data, "start_date": (date.today() + timedelta(days=2)).isoformat(),
        "end_date": (date.today() + timedelta(days=end_offset)).isoformat(),
    }, headers=headers["alice"])
    assert response.status_code == expected
    with factory() as session:
        assert len(session.scalars(select(Booking)).all()) == (2 if expected == 201 else 1)


@pytest.mark.parametrize("start_offset,end_offset,expected", [
    (0, 2, 201), (0, 3, 409), (2, 4, 409), (3, 7, 409),
    (4, 6, 409), (2, 8, 409), (6, 8, 409), (7, 9, 409), (8, 10, 201),
])
def test_approved_booking_date_overlap(booking, start_offset, end_offset, expected):
    client, factory, headers, record, data = booking
    with factory.begin() as session:
        existing = session.get(Booking, record["id"])
        existing.start_date = date.today() + timedelta(days=3)
        existing.end_date = date.today() + timedelta(days=7)
        existing.status = "approved"
    response = client.post("/bookings", json={
        **data, "start_date": (date.today() + timedelta(days=start_offset)).isoformat(),
        "end_date": (date.today() + timedelta(days=end_offset)).isoformat(),
    }, headers=headers["bob"])
    assert response.status_code == expected
    with factory() as session:
        assert len(session.scalars(select(Booking)).all()) == (2 if expected == 201 else 1)
        assert session.get(Booking, record["id"]).status == "approved"
        if expected == 201:
            assert session.get(Booking, response.json()["id"]).status == "pending"
        else:
            assert response.json()["detail"] == "The equipment is already booked for part of this period."


@pytest.mark.parametrize("status,expected", [
    ("approved", 409), ("borrowed", 409), ("pending", 201),
    ("cancelled", 201), ("rejected", 201), ("returned", 201),
])
def test_only_approved_and_borrowed_bookings_block_requests(booking, status, expected):
    client, factory, headers, record, data = booking
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = status
    response = client.post("/bookings", json=data, headers=headers["alice"])
    assert response.status_code == expected
    with factory() as session:
        assert len(session.scalars(select(Booking)).all()) == (2 if expected == 201 else 1)
        if expected == 201:
            assert session.get(Booking, response.json()["id"]).status == "pending"


def test_approved_booking_on_other_equipment_does_not_conflict(booking):
    client, factory, headers, record, data = booking
    with factory.begin() as session:
        session.get(Booking, record["id"]).status = "approved"
        equipment = Equipment(name="Projector", category="Video", location="Room B", status="available")
        session.add(equipment)
        session.flush()
        equipment_id = equipment.id
    response = client.post("/bookings", json={**data, "equipment_id": equipment_id}, headers=headers["bob"])
    assert response.status_code == 201
    with factory() as session:
        stored = session.get(Booking, response.json()["id"])
        assert stored.equipment_id == equipment_id
        assert stored.status == "pending"
