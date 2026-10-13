# Community Equipment Lending System - API

Python 3.11+ with FastAPI, SQLAlchemy 2, and SQLite. This project follows the Controller -> Service -> DAO structure of the original `lending-system`, without copying its Flask implementation or database.

## Scope

The framework, member registration, login, and current-user authentication are implemented. Equipment queries, booking requests, administrator workflows, logout, and frontend pages are NOT implemented. No accounts or sample data are preloaded.

The intended future scope is sections 1-3: users and permissions, equipment queries, and borrowing requests. Other business features are outside this foundation.

## Run

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m equipment_lending.init_db
python run.py
```

- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json
- Application health: http://127.0.0.1:8000/health

The health endpoint reports API liveness only. It does not check the database.

## Structure

```text
equipment_lending/
  main.py                 FastAPI application and router registration
  config.py               Environment settings
  database.py             Engine, ORM base, and request-scoped sessions
  controller/             HTTP endpoints
    health_controller.py  Application liveness
    authentication_controller.py  Registration, login, and current user
  service/                Business rules and transactions
  dao/                    Database queries
  model/                  SQLAlchemy models
  schema/                 Pydantic request and response schemas
tests/                    Framework checks using a temporary database
run.py                    Local development startup
```

## Future feature files

Keep authentication, equipment, and booking code in separate files within each layer, following the original project's naming, for example `authentication_controller.py`, `authentication_service.py`, and `user_dao.py`. Add only files needed by an implemented feature. Register new routers in `main.py`.

Controllers call services and do not execute SQL. Services receive a session and coordinate DAO calls. DAOs use the same session, rather than opening their own connections. Models inherit from `database.Base`.

Use `DatabaseSession` as a FastAPI dependency when implementing endpoints. Keep write transaction boundaries in services: use `with session.begin():` around a complete operation. SQLAlchemy propagates failures and rolls the transaction back. DAOs should not independently commit parts of the same operation. The request dependency closes the session and does not automatically commit.

## Database configuration

The default database file is `lending.db` in this project. To change it, copy `.env.example` to `.env` and set `DATABASE_PATH`. Relative paths resolve against the project directory. The parent directory must already exist. This foundation supports SQLite only and enables foreign key constraints on each connection.

Connections open on first database use. Run `python -m equipment_lending.init_db` before starting the server to create `users` and `login_sessions`. This command preserves existing rows and can run again safely. It does not migrate existing schemas. The original project's database remains untouched.

## Registration and login

1. In Swagger UI, use `POST /auth/register` with:

```json
{"name": "Yu Li", "email": "yu@example.org", "password": "ChooseYourPassword123!"}
```

2. Use `POST /auth/login` with the same email and password (without the name).
3. Copy `access_token` from the response, click **Authorize**, and paste the token without the `Bearer` prefix.
4. Call `GET /auth/me` to retrieve the authenticated user's profile.

Names are trimmed, emails are trimmed and converted to lowercase, and passwords retain their original characters. Registration requires a name, a valid email, and an 8-128 character password. New users always have the `member` role; requests cannot set an administrator role. Duplicate emails return 409, incorrect credentials return 401, and invalid input returns 422.

Passwords use Argon2 hashing. Login returns a random Bearer token valid for 24 hours; the database stores only its SHA-256 hash. Missing, invalid, or expired tokens cannot access `/auth/me`. Responses never include password hashes. `get_current_user` is reusable for future protected endpoints.

This is a local coursework API. Use HTTPS before remote deployment. Email verification, password reset, login rate limiting, session cleanup, and token revocation are not implemented. Do not expose this local development setup as a production authentication service.

## Tests

```bash
python -m pytest -q
```

Tests cover health, route scope, API documentation, SQLite connectivity, foreign keys, explicit commits, and uncommitted transaction cleanup. Tests do not access the original project's database.
Authentication tests additionally cover registration, login, profile retrieval, invalid input, duplicate emails, password hashing, token storage and expiration, and user isolation.

## Framework references

- [FastAPI database dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [SQLAlchemy sessions and transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
