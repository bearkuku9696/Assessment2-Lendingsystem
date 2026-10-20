# Community Equipment Lending System - API

Python 3.11+ with FastAPI, SQLAlchemy 2, and SQLite. This project follows the Controller -> Service -> DAO structure of the original `lending-system`, without copying its Flask implementation or database.

## Scope

F01-F05 (users and permissions) are implemented: registration, login/logout, member/admin roles, administrator-only access, and viewing/cancelling only your own bookings. The application includes a protected HTML administration page, minimal equipment creation/listing, and booking creation to support these workflows. No accounts or sample data are preloaded.

F06-F07 are implemented through `GET /equipment`: each item includes its ID, name, category, location, and status, ordered by category and name. Status values follow the reference project: `available`, `maintenance`, and `inactive`. All three statuses are included in the list.

F08-F11 are implemented on the public equipment catalogue at `/`: case-insensitive name/description search, category filtering, status filtering, and a responsive card layout. Filters combine and remain selected after submission. The catalogue uses one column on phones, two on tablets, and three on desktop.

F12-F14 are implemented through the catalogue's **Request booking** link. The application page signs in through the existing login API, then accepts a start date, end date, and purpose. The server rejects starts before today, ends on/before the start date, and empty purposes. Successful submissions display the booking ID and pending status.

Independent `/login` and `/register` pages follow the reference project's forms. Registration collects name, email, and password, then redirects to sign-in. Login returns to the selected equipment application page, catalogue, administrator review page, or personal reservations page.

F14-F18 are enforced when submitting a booking: the start date cannot be before today, the end date must be later than the start date, and equipment must be available. A request overlapping an approved or borrowed booking for the same equipment returns 409 without saving a new row. Date ranges include both endpoints, matching the reference project, so sharing a start/end boundary also conflicts. Pending, cancelled, rejected, and returned bookings do not block new requests. Accepted requests are saved as `pending`; clients cannot set their status.

F19-F25 are implemented for administrator review: list reservations with applicant name/email, equipment name, dates, purpose, status, and admin notes; approve or reject pending requests; and re-check availability and inclusive date conflicts on approval. The conflict check and decision run in one SQLite `BEGIN IMMEDIATE` transaction, serializing concurrent approvals before their first read. Rejection requires a nonempty reason. Other booking states cannot be reviewed again.

F26-F32 are implemented for pickup, return, cancellation, and overdue display. Administrators confirm `approved -> borrowed -> returned` and the server records actual pickup/return timestamps. Owners can cancel only `pending` or `approved` reservations from **My reservations**. Borrowed reservations cannot be cancelled. A borrowed reservation is displayed as overdue when the application server's current date is later than its expected return date; overdue is a computed flag, not a stored reservation status.

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
- Equipment catalogue: http://127.0.0.1:8000/
- Personal reservations: http://127.0.0.1:8000/account/bookings
- Administrator review and handover: http://127.0.0.1:8000/admin/review
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
  migrate_db.py           Repeatable booking approval and handover database upgrades
  service/                Business rules and transactions
  dao/                    Database queries
  model/                  SQLAlchemy models
  schema/                 Pydantic request and response schemas
  templating.py           Jinja2 template configuration
  templates/              HTML pages (base, login, register, catalogue, booking, my_bookings, admin)
  static/                 Shared CSS and authentication/session/booking/my_bookings/admin JavaScript
tests/                    Framework checks using a temporary database
run.py                    Local development startup
```

## Future feature files

Keep authentication, equipment, and booking code in separate files within each layer, following the original project's naming, for example `authentication_controller.py`, `authentication_service.py`, and `user_dao.py`. Add only files needed by an implemented feature. Register new routers in `main.py`.

Controllers call services and do not execute SQL. Services receive a session and coordinate DAO calls. DAOs use the same session, rather than opening their own connections. Models inherit from `database.Base`.

Pages are ordinary `.html` Jinja2 templates, following the reference project's structure. Controllers pass data to templates; HTML, CSS, and JavaScript are not embedded in Python. Jinja2 escapes displayed values automatically. Install the updated requirements to include Jinja2.

Use `DatabaseSession` as a FastAPI dependency when implementing endpoints. Keep write transaction boundaries in services: use `with session.begin():` around a complete operation. SQLAlchemy propagates failures and rolls the transaction back. DAOs should not independently commit parts of the same operation. The request dependency closes the session and does not automatically commit.

## Database configuration

The default database file is `lending.db` in this project. To change it, copy `.env.example` to `.env` and set `DATABASE_PATH`. Relative paths resolve against the project directory. The parent directory must already exist. This foundation supports SQLite only and enables foreign key constraints on each connection.

Connections open on first database use. Run `python -m equipment_lending.init_db` before starting the server to create `users`, `login_sessions`, `equipment`, and `bookings`. Existing installations must run this command again to add the equipment and booking tables. This command preserves existing rows and can run again safely. It does not migrate existing schemas. The original project's database remains untouched.

For the previous equipment table containing only `id` and `name`, run the following migration once before starting the updated application. It applies to an empty equipment table (the state of this project's local database before F06-F07). If equipment rows already exist, supply their real category and location values in a data migration first; no placeholder values are generated.

```bash
sqlite3 -bail lending.db < migrations/001_equipment_details.sql
```

Use your configured database path if different. New databases created with `init_db` already contain these fields and must not run this migration.

Existing databases without the equipment description column must run this migration once:

```bash
sqlite3 -bail lending.db < migrations/002_equipment_description.sql
```

This preserves existing equipment and adds an optional description, initially empty. New databases already have this column.

Before running this version against an existing database, stop the server and apply the booking upgrades:

```bash
python -m equipment_lending.migrate_db
```

This adds missing `bookings.admin_notes`, `picked_up_at`, and `returned_at` columns, preserving existing reservations and notes. New time fields remain NULL for historical rows because actual times are unknown. It uses the configured `DATABASE_PATH`, safely skips existing columns (including on new databases created with `init_db`), and can resume a partially upgraded schema without overwriting timestamps. It does not replace the earlier equipment migrations. Alternatively, run `migrations/003_booking_admin_notes.sql` once if notes are missing, followed by `migrations/004_booking_handover_times.sql` once if both actual-time columns are missing. Use the Python command for partially upgraded databases. The Python command does not require the SQLite CLI and works on Windows.

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
| GET | /admin/review | Browser review shell; loads data only after administrator authentication |
| POST | /admin/equipment | Administrators: create equipment with `{"name": "Camera", "category": "Photography", "location": "Room A", "status": "available"}` |
| GET | /admin/bookings | Administrators: list bookings including applicant name/email, equipment name, and admin notes |
| POST | /admin/bookings/{id}/approve | Administrators: approve a pending reservation after conflict and availability checks |
| POST | /admin/bookings/{id}/reject | Administrators: reject a pending reservation with a reason |
| POST | /admin/bookings/{id}/pickup | Administrators: mark an approved reservation as borrowed and record actual pickup time |
| POST | /admin/bookings/{id}/return | Administrators: mark a borrowed reservation as returned and record actual return time |
| GET | / | Public responsive equipment catalogue with search and filters |
| GET | /login | Sign-in page; returns to the catalogue or selected booking page |
| GET | /register | Registration page; redirects to sign-in after account creation |
| GET | /equipment/{id}/book | Application page with equipment details, sign-in, dates, and purpose |
| GET | /equipment | Public list with ID, name, description, category, location, and status |
| POST | /bookings | Signed-in users: create their own pending booking |
| GET | /my-bookings | Signed-in users: list only their own bookings |
| GET | /account/bookings | Browser shell for the owner's reservations, actual times, overdue labels, and cancellation |
| GET | /bookings/{id} | Booking owner: view details |
| POST | /bookings/{id}/cancel | Booking owner: cancel a pending or approved booking |

The HTML management page uses the same Bearer header as the API. Use Swagger's authorized `GET /admin` request to inspect its HTML response, or a client that sends that header; entering the URL in a browser without credentials returns 401.

For browser use, open `/admin/review` and sign in with an administrator account, or sign in on the catalogue and click **Booking administration**. The review URL serves a shell without reservation data. Its JavaScript sends the tab's Bearer token to protected APIs; ordinary members cannot load reservations or make decisions. Pending rows have **Approve** and **Reject** buttons and a notes field. A successful decision updates that row; **Refresh reservations** reloads other staff decisions. User-entered values are displayed as text, not HTML.

Approval accepts `{"admin_notes": "Optional staff note"}` or `{}`. Rejection accepts `{"admin_notes": "Reason for rejection"}`; blank reasons return 422. Notes are trimmed and limited to 2,000 characters. Notes are exposed only in administrator responses, while owners can see their reservation's resulting status through the existing endpoints.

Both decisions require `pending` (otherwise 409); missing reservations return 404. Approval re-checks that equipment remains `available` and that no `approved` or `borrowed` reservation overlaps the requested dates. Failed decisions leave both the status and notes unchanged. SQLite's writer lock is acquired before reading the reservation and held until the decision commits or rolls back, across threads and processes. If another writer holds the database beyond the lock timeout, review returns 503 with `Retry-After: 1`. Refresh reservations before retrying a request whose result could not be confirmed.

Approved rows show **Confirm pickup** and borrowed rows show **Confirm return**. Both APIs accept an empty JSON object `{}`. Clients cannot set the resulting status, pickup time, or return time; additional request fields return 422. Only administrators can perform either operation. Invalid transitions, including repeated pickup/return, return 409; missing reservations return 404. No extra restriction on collection dates is imposed. Status and the corresponding actual time are saved together in one immediate transaction, so a simultaneous pickup and owner cancellation cannot both succeed. Database lock timeouts return 503 with `Retry-After: 1`; failed operations roll back all changes.

Actual timestamps are recorded as UTC and returned as ISO 8601 strings with an explicit UTC offset (`Z`); no actual time is invented for old records. Browser pages format these values in the viewer's local timezone. The protected server-rendered `/admin` fallback labels its unconverted timestamps as UTC. Every booking response includes nullable `picked_up_at`/`returned_at` fields and a computed `is_overdue` boolean. A still-borrowed item is not overdue on its end date, becomes overdue the next day, and stops displaying overdue once returned. Refresh the page/list to recompute the flag after a date change.

Open `/account/bookings`, sign in, or select **My reservations** in the navigation to view your own reservations. The page loads the existing owner-filtered API with the tab's Bearer token; its public HTML shell contains no booking data. Pending and approved cards show **Cancel reservation**, while other states do not. Both admin and member pages disable duplicate operations while a request is in progress, retain existing history, and display errors when another user changes the state first. Expired sessions clear private data and require sign-in again.

Equipment creation requires nonempty name, category, and location. Status defaults to `available` when omitted; unsupported statuses return 422. `GET /equipment` returns an empty list when no equipment exists.

Equipment creation also accepts an optional `description` (up to 2,000 characters). Both `/` and `/equipment` accept `search`, `category`, and `status` query parameters, for example `/equipment?search=kit&category=Audio&status=maintenance`. Search matches part of the name or description, ignoring case. Categories match exactly; status must be empty, `available`, `maintenance`, or `inactive`. Equipment browsing is public, matching the reference project; booking and administration permissions are unchanged.

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

To apply in the browser, open the catalogue, choose an available item, click **Request booking**, and sign in or create an account. Registration leads to sign-in, which returns to the selected equipment. Fill in the two dates and a purpose, then submit. Maintenance/inactive equipment cannot be requested (409), including when its status changes before submission. Date validation uses the application server's current date, as in the reference project. Browser pages keep the token in `sessionStorage` for the current tab, preserving login across navigation and refresh; passwords are never stored. **Sign out** revokes the token and clears it from the tab. Missing or expired tokens require sign-in. A successful request disables the form and shows a confirmation.

## Tests

```bash
python -m pytest -q
```

Tests cover health, route scope, API documentation, SQLite connectivity, foreign keys, explicit commits, and uncommitted transaction cleanup. Tests do not access the original project's database.
Authentication tests additionally cover registration, login, profile retrieval, invalid input, duplicate emails, password hashing, token storage and expiration, and user isolation.
Permission tests cover administrator provisioning, logout revocation and session isolation, member/anonymous rejection on admin routes, owner-only booking reads and cancellation, forged ownership, validation, cancellation persistence, status restrictions, and HTML escaping. All database tests use temporary SQLite databases.

Administrator review tests cover enriched listings, browser login destinations, role enforcement, required rejection reasons, notes persistence, invalid state transitions, inclusive date conflicts, equipment availability, transaction rollback, migration preservation, and concurrent decisions. Overlapping approvals are tested on separate database connections in both DELETE and WAL journal modes, with the first check held while the second approval attempts its transaction.

Handover tests cover the complete approved/borrowed/returned workflow, server UTC timestamps, role restrictions, forged timestamp/status rejection, state transition rules, duplicate operations, rollback, overdue date boundaries in all states, legacy returns with unknown pickup time, pickup/cancellation races in DELETE and WAL modes, database lock timeouts, personal page login destinations, and repeatable/partial database upgrades that preserve history.

## Framework references

- [FastAPI database dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [SQLAlchemy sessions and transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
