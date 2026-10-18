from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import select

from equipment_lending.model.equipment import Equipment
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
        created.append({"id": response.json()["id"], **item})
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
        "location": "Room A", "status": "available",
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
