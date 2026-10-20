from datetime import date
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import select

from equipment_lending.model.equipment import Equipment
from equipment_lending.model.booking import Booking
from equipment_lending.model.user import User
from equipment_lending.service.authentication_service import AuthenticationService


@pytest.fixture
def catalogue(auth):
    client, factory = auth
    with factory() as session:
        AuthenticationService(session).register("Admin", "admin@example.org", "Password123!", role="admin")
    client.post("/auth/register", json={
        "name": "Member", "email": "member@example.org", "password": "Password123!",
    })
    headers = {}
    for role in ("admin", "member"):
        response = client.post("/auth/login", json={
            "email": f"{role}@example.org", "password": "Password123!",
        })
        headers[role] = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return client, factory, headers


def test_empty_equipment_list(catalogue):
    client, _, headers = catalogue
    response = client.get("/equipment", headers=headers["member"])
    assert response.status_code == 200
    assert response.json() == []


def test_equipment_list_shows_all_fields_and_statuses(catalogue):
    client, factory, headers = catalogue
    items = [
        {"name": "Camera", "category": "Photography", "location": "Room C", "status": "inactive"},
        {"name": "Speaker", "category": "Audio", "location": "Room B", "status": "maintenance"},
        {"name": "Microphone", "category": "Audio", "location": "Room A", "status": "available"},
    ]
    created = []
    for item in items:
        response = client.post("/admin/equipment", json=item, headers=headers["admin"])
        assert response.status_code == 201
        created.append({"id": response.json()["id"], "description": "", **item})
    for role in ("member", "admin"):
        response = client.get("/equipment", headers=headers[role])
        assert response.status_code == 200
        assert response.json() == [created[2], created[1], created[0]]
    with factory() as session:
        stored = session.get(Equipment, created[0]["id"])
        assert (stored.category, stored.location, stored.status) == ("Photography", "Room C", "inactive")


def test_equipment_creation_trims_fields_and_defaults_to_available(catalogue):
    client, _, headers = catalogue
    response = client.post("/admin/equipment", json={
        "name": " Camera ", "category": " Photography ", "location": " Room A ",
    }, headers=headers["admin"])
    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"], "name": "Camera", "category": "Photography",
        "location": "Room A", "status": "available", "description": "",
    }


@pytest.mark.parametrize("changes", [
    {"category": " "}, {"location": " "}, {"status": "borrowed"},
])
def test_invalid_equipment_details_are_rejected(catalogue, changes):
    client, factory, headers = catalogue
    response = client.post("/admin/equipment", json={
        "name": "Camera", "category": "Photography", "location": "Room A", **changes,
    }, headers=headers["admin"])
    assert response.status_code == 422
    with factory() as session:
        assert session.scalar(select(Equipment)) is None


def test_category_and_location_are_required(catalogue):
    client, _, headers = catalogue
    response = client.post("/admin/equipment", json={"name": "Camera"}, headers=headers["admin"])
    assert response.status_code == 422


def test_migrate_empty_equipment_table(tmp_path):
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_equipment_details.sql"
    with sqlite3.connect(tmp_path / "migration.db") as connection:
        connection.execute("CREATE TABLE equipment (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL)")
        connection.executescript(migration.read_text())
        connection.execute(
            "INSERT INTO equipment (name, category, location) VALUES (?, ?, ?)",
            ("Camera", "Photography", "Room A"),
        )
        assert connection.execute("SELECT name, category, location, status FROM equipment").fetchone() == (
            "Camera", "Photography", "Room A", "available",
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO equipment (name) VALUES ('Missing details')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE equipment SET status = 'unknown'")


@pytest.fixture
def searchable_equipment(auth):
    client, factory = auth
    with factory.begin() as session:
        session.add_all([
            Equipment(name="Camera", category="Photography", location="Room A",
                      status="available", description="Digital portrait kit"),
            Equipment(name="Speaker", category="Audio", location="Room B",
                      status="maintenance", description="Portable event kit"),
            Equipment(name="Microphone", category="Audio", location="Room C",
                      status="inactive", description="Studio recording"),
        ])
    return client


@pytest.mark.parametrize("params,names", [
    ({}, ["Microphone", "Speaker", "Camera"]),
    ({"search": "cAmErA"}, ["Camera"]),
    ({"search": "  PORTRAIT  "}, ["Camera"]),
    ({"search": "kit"}, ["Speaker", "Camera"]),
    ({"category": "Audio"}, ["Microphone", "Speaker"]),
    ({"status": "available"}, ["Camera"]),
    ({"status": "maintenance"}, ["Speaker"]),
    ({"status": "inactive"}, ["Microphone"]),
    ({"search": "kit", "category": "Audio", "status": "maintenance"}, ["Speaker"]),
    ({"category": "Audio", "status": "available"}, []),
    ({"search": "%"}, []),
    ({"search": "' OR 1=1 --"}, []),
])
def test_public_equipment_search_and_filters(searchable_equipment, params, names):
    response = searchable_equipment.get("/equipment", params=params)
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == names


def test_catalogue_page_filters_and_retains_selection(searchable_equipment):
    response = searchable_equipment.get("/", params={"search": "kit", "category": "Audio", "status": "maintenance"})
    assert response.status_code == 200
    assert "Speaker" in response.text and "Portable event kit" in response.text
    assert "<h2>Camera</h2>" not in response.text
    assert 'value="Audio" selected' in response.text
    assert 'value="maintenance" selected' in response.text
    assert 'value="kit"' in response.text
    assert "Photography</option>" in response.text
    assert "width=device-width" in response.text


def test_period_filter_excludes_overlapping_bookings(auth):
    client, factory = auth
    with factory.begin() as session:
        user = User(name="Member", email="member@example.org", password_hash="hash")
        camera = Equipment(name="Camera", category="Photography", location="Room A",
                           status="available", description="Digital camera")
        session.add(camera)
        session.add(user)
        session.flush()
        session.add(Booking(
            user_id=user.id,
            equipment_id=camera.id,
            start_date=date(2030, 1, 10),
            end_date=date(2030, 1, 12),
            purpose="Event",
            status="approved",
        ))

    response = client.get("/equipment", params={
        "start_date": "2030-01-11", "end_date": "2030-01-13",
    })
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == []

    response = client.get("/", params={
        "start_date": "2030-01-13", "end_date": "2030-01-15",
    })
    assert response.status_code == 200
    assert "<h2>Camera</h2>" in response.text


@pytest.mark.parametrize("params", [
    {"start_date": "2030-01-10"},
    {"end_date": "2030-01-10"},
    {"start_date": "2030-01-12", "end_date": "2030-01-10"},
])
def test_invalid_period_filter_is_rejected(auth, params):
    client, _ = auth
    assert client.get("/equipment", params=params).status_code == 422


def test_catalogue_empty_results_and_escaped_search(searchable_equipment):
    response = searchable_equipment.get("/", params={"search": '<script>alert("x")</script>'})
    assert "No equipment matches your search" in response.text
    assert '<script>alert("x")</script>' not in response.text
    assert "&lt;script&gt;" in response.text


@pytest.mark.parametrize("path", ["/", "/equipment"])
def test_invalid_status_filter_returns_validation_error(searchable_equipment, path):
    assert searchable_equipment.get(path, params={"status": "borrowed"}).status_code == 422


def test_description_migration_preserves_equipment(tmp_path):
    migration = Path(__file__).resolve().parents[1] / "migrations" / "002_equipment_description.sql"
    with sqlite3.connect(tmp_path / "description.db") as connection:
        connection.execute("CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("INSERT INTO equipment (name) VALUES ('Camera')")
        connection.executescript(migration.read_text())
        assert connection.execute("SELECT name, description FROM equipment").fetchone() == ("Camera", "")
