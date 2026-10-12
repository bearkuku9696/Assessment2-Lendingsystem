# Community Equipment Lending System - API Foundation

Python 3.11+ with FastAPI, SQLAlchemy 2, and SQLite. This project follows the Controller -> Service -> DAO structure of the original `lending-system`, without copying its Flask implementation or database.

## Scope

Only the development framework is implemented. Registration, authentication, permissions, equipment queries, booking requests, and all administrator workflows are NOT implemented. There are no business tables, accounts, sample data, or frontend pages.

The intended future scope is sections 1-3: users and permissions, equipment queries, and borrowing requests. Other business features are outside this foundation.

## Run

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
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
    health_controller.py  Only implemented endpoint
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

Connections open on first database use. No business tables are automatically created. Define the required models and an explicit schema setup when implementing the features. The original project's database remains untouched.

## Tests

```bash
python -m pytest -q
```

Tests cover health, route scope, API documentation, SQLite connectivity, foreign keys, explicit commits, and uncommitted transaction cleanup. Tests do not access the original project's database.

## Framework references

- [FastAPI database dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [SQLAlchemy sessions and transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
