# Community Equipment Lending System - API

Python 3.11+ with FastAPI, SQLAlchemy 2, and SQLite. This project follows the Controller -> Service -> DAO structure of the original `lending-system`, without copying its Flask implementation or database.

## Scope

F01-F05 (users and permissions) are implemented: registration, login/logout, member/admin roles, administrator-only access, and viewing/cancelling only your own bookings. The application includes a protected HTML administration page, minimal equipment creation/listing, and booking creation to support these workflows. No accounts or sample data are preloaded.

F06-F07 are implemented through `GET /equipment`: each item includes its ID, name, category, location, and status, ordered by category and name. Status values follow the reference project: `available`, `maintenance`, and `inactive`. All three statuses are included in the list.

The main interface is the API and Swagger UI. A full frontend with login forms is not included. Equipment search/filtering, availability checks, booking approval, collection, and return workflows are outside this implementation.

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
    authentication_controller.py  Registration, login, logout, and role checks
    admin_controller.py   Protected HTML administration page
    equipment_controller.py  Equipment listing and administrator creation
    booking_controller.py  Booking creation, ownership, cancellation, and admin listing
  create_admin.py         Local administrator provisioning command
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

Connections open on first database use. Run `python -m equipment_lending.init_db` before starting the server to create `users`, `login_sessions`, `equipment`, and `bookings`. Existing installations must run this command again to add the equipment and booking tables. This command preserves existing rows and can run again safely. It does not migrate existing schemas. The original project's database remains untouched.

For the previous equipment table containing only `id` and `name`, run the following migration once before starting the updated application. It applies to an empty equipment table (the state of this project's local database before F06-F07). If equipment rows already exist, supply their real category and location values in a data migration first; no placeholder values are generated.

```bash
sqlite3 -bail lending.db < migrations/001_equipment_details.sql
```

Use your configured database path if different. New databases created with `init_db` already contain these fields and must not run this migration.

## Registration and login

1. In Swagger UI, use `POST /auth/register` with:

```json
{"name": "Yu Li", "email": "yu@example.org", "password": "ChooseYourPassword123!"}
```

2. Use `POST /auth/login` with the same email and password (without the name).
3. Copy `access_token` from the response, click **Authorize**, and paste the token without the `Bearer` prefix.
4. Call `GET /auth/me` to retrieve the authenticated user's profile.
5. Call `POST /auth/logout` to revoke the current token (204). That token immediately stops working; other login sessions remain active. Missing, invalid, expired, and already revoked tokens return 401.

Names are trimmed, emails are trimmed and converted to lowercase, and passwords retain their original characters. Registration requires a name, a valid email, and an 8-128 character password. New users always have the `member` role; requests cannot set an administrator role. Duplicate emails return 409, incorrect credentials return 401, and invalid input returns 422.

Passwords use Argon2 hashing. Login returns a random Bearer token valid for 24 hours; the database stores only its SHA-256 hash. Missing, invalid, or expired tokens cannot access `/auth/me`. Responses never include password hashes. `get_current_user` is reusable for future protected endpoints.

This is a local coursework API. Use HTTPS before remote deployment. Email verification, password reset, login rate limiting, and expired-session cleanup are not implemented. Do not expose this local development setup as a production authentication service.

## Administrators and bookings

After initializing the database, create an administrator locally:

```bash
python -m equipment_lending.create_admin --name "Administrator" --email "admin@example.org"
```

The command prompts for a password and confirmation without displaying either. It validates registration fields and refuses duplicate emails; it does not promote existing accounts. Public registration always creates members and rejects a supplied `role`.

Log in using the administrator credentials and authorize Swagger UI. All protected routes require an `Authorization: Bearer <access_token>` header. Unauthenticated requests return 401; authenticated members receive 403 on administrator routes.

| Method | Path | Access and purpose |
| --- | --- | --- |
| GET | /admin | Administrators: HTML page showing all bookings |
| POST | /admin/equipment | Administrators: create equipment with `{"name": "Camera", "category": "Photography", "location": "Room A", "status": "available"}` |
| GET | /admin/bookings | Administrators: list all bookings |
| GET | /equipment | Signed-in users: list equipment with ID, name, category, location, and status |
| POST | /bookings | Signed-in users: create their own pending booking |
| GET | /my-bookings | Signed-in users: list only their own bookings |
| GET | /bookings/{id} | Booking owner: view details |
| POST | /bookings/{id}/cancel | Booking owner: cancel a pending or approved booking |

The HTML management page uses the same Bearer header as the API. Use Swagger's authorized `GET /admin` request to inspect its HTML response, or a client that sends that header; entering the URL in a browser without credentials returns 401.

Equipment creation requires nonempty name, category, and location. Status defaults to `available` when omitted; unsupported statuses return 422. `GET /equipment` returns an empty list when no equipment exists.

Create equipment as an administrator first. Then log in as a member and submit a booking with its equipment ID, today's date or a future date, a later end date, and a nonempty purpose:

```json
{
  "equipment_id": 1,
  "start_date": "2030-01-10",
  "end_date": "2030-01-12",
  "purpose": "Community event"
}
```

Use dates appropriate to when you run this example. The server derives the owner from the login token; supplying `user_id` or `status` returns 422. Other users cannot read or cancel the booking (403). Missing equipment/bookings return 404. Cancelling a borrowed, returned, rejected, or already cancelled booking returns 409. Administrator listings can view all bookings; the owner-only endpoints retain their ownership checks for every role.

## Tests

```bash
python -m pytest -q
```

Tests cover health, route scope, API documentation, SQLite connectivity, foreign keys, explicit commits, and uncommitted transaction cleanup. Tests do not access the original project's database.
Authentication tests additionally cover registration, login, profile retrieval, invalid input, duplicate emails, password hashing, token storage and expiration, and user isolation.
Permission tests cover administrator provisioning, logout revocation and session isolation, member/anonymous rejection on admin routes, owner-only booking reads and cancellation, forged ownership, validation, cancellation persistence, status restrictions, and HTML escaping. All database tests use temporary SQLite databases.

## Framework references

- [FastAPI database dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [SQLAlchemy sessions and transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
