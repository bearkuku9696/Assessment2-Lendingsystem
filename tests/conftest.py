from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from equipment_lending import database, init_db
from equipment_lending.main import app
from equipment_lending.service.authentication_service import AuthenticationService


@pytest.fixture
def auth(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", database.enable_foreign_keys)
    monkeypatch.setattr(init_db, "engine", engine)
    init_db.init_db()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


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
