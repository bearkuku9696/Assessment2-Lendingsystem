import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from equipment_lending import database
from equipment_lending.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_route_scope():
    assert set(app.openapi()["paths"]) == {"/health", "/auth/register", "/auth/login", "/auth/me"}
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 200


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    event.listen(engine, "connect", database.enable_foreign_keys)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY)"))
    yield factory
    engine.dispose()


def test_database_connection_and_foreign_keys(session_factory):
    dependency = database.get_session()
    session = next(dependency)
    assert session.scalar(text("SELECT 1")) == 1
    assert session.scalar(text("PRAGMA foreign_keys")) == 1
    dependency.close()


def test_explicit_commit_persists(session_factory):
    dependency = database.get_session()
    session = next(dependency)
    session.execute(text("INSERT INTO sample VALUES (1)"))
    session.commit()
    dependency.close()
    with session_factory() as check:
        assert check.scalar(text("SELECT COUNT(*) FROM sample")) == 1


def test_uncommitted_work_is_not_saved(session_factory):
    dependency = database.get_session()
    session = next(dependency)
    session.execute(text("INSERT INTO sample VALUES (1)"))
    dependency.close()
    with session_factory() as check:
        assert check.scalar(text("SELECT COUNT(*) FROM sample")) == 0
