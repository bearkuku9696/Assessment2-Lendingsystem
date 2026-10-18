from datetime import datetime
from hashlib import sha256

import pytest
from sqlalchemy import select

from equipment_lending import init_db
from equipment_lending.model.login_session import LoginSession
from equipment_lending.model.user import User


ACCOUNT = {"name": "Yu Li", "email": "yu@example.org", "password": "Password123!"}


def login(client, **changes):
    return client.post("/auth/login", json={"email": ACCOUNT["email"], "password": ACCOUNT["password"], **changes})


def test_register_login_and_current_user(auth):
    client, factory = auth
    registered = client.post("/auth/register", json={**ACCOUNT, "name": " Yu Li ", "email": " YU@EXAMPLE.ORG "})
    assert registered.status_code == 201
    user = registered.json()
    assert user["name"] == "Yu Li"
    assert user["email"] == ACCOUNT["email"]
    assert user["role"] == "member"
    assert "password" not in user and "password_hash" not in user
    response = login(client, email=" YU@EXAMPLE.ORG ")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["expires_in"] == 86400
    assert result["token_type"] == "bearer"
    token = result["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json() == user
    with factory() as db:
        stored = db.scalar(select(User))
        assert stored.password_hash.startswith("$argon2id$")
        assert stored.password_hash != ACCOUNT["password"]
        assert db.scalar(select(LoginSession)).token_hash == sha256(token.encode()).hexdigest()
    init_db.init_db()
    assert login(client).status_code == 200


def test_duplicate_email(auth):
    client, factory = auth
    assert client.post("/auth/register", json=ACCOUNT).status_code == 201
    assert client.post("/auth/register", json={**ACCOUNT, "email": "YU@example.org"}).status_code == 409
    with factory() as db:
        assert len(db.scalars(select(User)).all()) == 1


@pytest.mark.parametrize("changes", [
    {"name": "  "}, {"email": "invalid"}, {"email": 123},
    {"password": "short"}, {"password": "a" * 129}, {"role": "admin"},
])
def test_invalid_registration(auth, changes):
    client, factory = auth
    assert client.post("/auth/register", json={**ACCOUNT, **changes}).status_code == 422
    with factory() as db:
        assert db.scalar(select(User)) is None


def test_wrong_password_and_unknown_email_have_same_error(auth):
    client, factory = auth
    client.post("/auth/register", json=ACCOUNT)
    wrong = login(client, password="wrong-password")
    unknown = login(client, email="unknown@example.org")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    with factory() as db:
        assert db.scalar(select(LoginSession)) is None


def test_missing_invalid_and_expired_token(auth):
    client, factory = auth
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    client.post("/auth/register", json=ACCOUNT)
    token = login(client).json()["access_token"]
    with factory.begin() as db:
        db.get(LoginSession, sha256(token.encode()).hexdigest()).expires_at = datetime(2000, 1, 1)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_tokens_identify_the_correct_user(auth):
    client, _ = auth
    client.post("/auth/register", json=ACCOUNT)
    client.post("/auth/register", json={**ACCOUNT, "email": "petter@example.org", "name": "Petter"})
    first = login(client).json()["access_token"]
    second = login(client, email="petter@example.org").json()["access_token"]
    assert first != second
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {second}"}).json()["name"] == "Petter"
