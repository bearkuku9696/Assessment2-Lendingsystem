import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from equipment_lending import database, init_db
from equipment_lending.main import app


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
