# Booking Service

A RESTful API for managing **properties**, guest **bookings** and owner **blocks**. Its core
guarantee is that a non-canceled booking never shares a day with another non-canceled booking or a
block on the same property, including when requests arrive at the same time.

Built with **FastAPI**, **SQLAlchemy 2.0**, **Pydantic v2** and **SQLite**.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

uvicorn app.main:create_app --factory --reload
```

The interactive API docs are at <http://localhost:8000/docs>. Tables are created on startup in
`./booking.db`.

With Docker instead:

```bash
docker build -t booking-service .
docker run -p 8000:8000 -e BOOKING_API_KEY=change-me booking-service
```

### Configuration

All settings are read from environment variables (or a `.env` file, see `.env.example`).

| Variable               | Default                  | Purpose                                                    |
|------------------------|--------------------------|------------------------------------------------------------|
| `BOOKING_DATABASE_URL` | `sqlite:///./booking.db` | Any SQLAlchemy URL.                                        |
| `BOOKING_API_KEY`      | *(unset)*                | If set, `/api/v1/*` requires the header `X-API-Key: <key>`. |
| `BOOKING_SQL_ECHO`     | `false`                  | Log every SQL statement.                                   |

## API

All endpoints are under `/api/v1`. Dates use ISO 8601 (`YYYY-MM-DD`).

| Method   | Path                          | Description                                    | Success |
|----------|-------------------------------|------------------------------------------------|---------|
| `POST`   | `/properties`                 | Create a property                              | 201     |
| `GET`    | `/properties/{id}`            | Get a property                                 | 200     |
| `POST`   | `/bookings`                   | Create a booking (status `CONFIRMED`)          | 201     |
| `GET`    | `/bookings`                   | List bookings: `?property_id=&status=&limit=&offset=` | 200 |
| `GET`    | `/bookings/{id}`              | Get a booking                                  | 200     |
| `PATCH`  | `/bookings/{id}`              | Update `guest_name`, `start_date`, `end_date`  | 200     |
| `POST`   | `/bookings/{id}/cancel`       | Cancel a booking                               | 200     |
| `POST`   | `/bookings/{id}/rebook`       | Re-confirm a canceled booking                  | 200     |
| `DELETE` | `/bookings/{id}`              | Delete a booking                               | 204     |
| `POST`   | `/blocks`                     | Create a block                                 | 201     |
| `GET`    | `/blocks`                     | List blocks: `?property_id=&limit=&offset=`    | 200     |
| `GET`    | `/blocks/{id}`                | Get a block                                    | 200     |
| `PATCH`  | `/blocks/{id}`                | Update block dates                             | 200     |
| `DELETE` | `/blocks/{id}`                | Delete a block                                 | 204     |
| `GET`    | `/health`                     | Liveness probe (never requires an API key)     | 200     |

Lists return a page envelope: `{"items": [...], "total": 3, "limit": 50, "offset": 0}`.

### Example

```bash
curl -X POST localhost:8000/api/v1/properties \
     -H 'Content-Type: application/json' -d '{"name": "Beach House", "country_code": "PT"}'

curl -X POST localhost:8000/api/v1/bookings -H 'Content-Type: application/json' \
     -d '{"property_id": 1, "guest_name": "Jane Doe", "start_date": "2030-01-11", "end_date": "2030-01-16"}'
```

A second booking for 2030-01-16 → 2030-01-18 is rejected:

```http
HTTP/1.1 409 Conflict

{
  "error": "date_overlap",
  "message": "The requested dates overlap an existing booking.",
  "details": {"conflict_type": "booking", "conflict_id": 1,
              "start_date": "2030-01-11", "end_date": "2030-01-16"}
}
```

### Errors

Every error, including unknown routes and unexpected server errors, has the same shape:
`{"error": "<stable code>", "message": "<human text>", "details": <object | list | null>}`.

| Status | `error`                                  | When                                                        |
|--------|------------------------------------------|-------------------------------------------------------------|
| 400    | `validation_error`                       | Missing, malformed or unknown fields (no type coercion: `"1"`/`true` are not IDs, dates must be `YYYY-MM-DD`); `start_date >= end_date` |
| 401    | `unauthorized`                           | API key missing or wrong (only when a key is configured)    |
| 404    | `not_found`                              | Property, booking or block does not exist, including a `property_id` list filter |
| 409    | `date_overlap`                           | Dates collide with a non-canceled booking or a block        |
| 409    | `invalid_state`                          | Canceling a canceled booking, rebooking a confirmed one     |
| 500    | `internal_error`                         | Unexpected failure. Logged server-side; no internals are returned |

## Development

```bash
pytest                       # ~150 unit and API tests
pytest --cov=app             # with coverage (~99%)
ruff check . && ruff format --check .
mypy app tests               # strict mode
```

```
app/
  main.py              application factory and lifespan
  config.py            environment-based settings
  database.py          engine, sessions, write-transaction helper (locking)
  domain.py            DateRange + overlap rule, BookingStatus (no framework code)
  models.py            SQLAlchemy models and DB constraints
  schemas.py           Pydantic request/response models
  exceptions.py        HTTP-agnostic domain exceptions
  services/            business logic: properties, bookings, blocks, availability
  api/                 routes, dependencies (auth, sessions), error mapping
tests/
  overlap_cases.py     the spec's overlap table, shared by unit and API tests
  unit/                DateRange, schemas, database guards
  integration/         API endpoints, overlap via the database, concurrency
```

## Design Notes

**Framework and database.** FastAPI is what I'd use on the job for a JSON API like this. Its
Pydantic models give declarative validation and an accurate OpenAPI spec without extra code.
Dependency injection keeps sessions, services and authentication easy to swap in tests, and
mypy can check the whole application. I used SQLAlchemy 2.0 with synchronous endpoints, which
FastAPI runs in a thread pool. This is simpler than an async driver and fast enough at this
scale. The database is SQLite in a **file** rather than `:memory:`. A private in-memory
database exists on a single connection, so every request thread would share one transaction,
which breaks the isolation the overlap check depends on. A file needs no setup either, and it
has real transactional locking. The code stays backend-agnostic: setting
`BOOKING_DATABASE_URL` to PostgreSQL works without code changes. Integrity rules are also
enforced as database constraints (CHECK `start_date < end_date`, a CHECK on status values,
foreign keys), so even writes that bypass the API cannot store invalid rows.

**Overlap check.** A date range is a closed interval: both `start_date` and `end_date` are
occupied days. Two ranges overlap if and only if `a.start <= b.end AND b.start <= a.end`. This
rule lives in `DateRange.overlaps` (pure Python, unit-tested) and has an SQL equivalent in
`services/availability.py`. The SQL version is used for enforcement, so the database does the
filtering, backed by composite indexes on `(property_id, start_date, end_date[, status])`.
Every path that can occupy dates calls `ensure_booking_dates_available`: create, update (only
when the dates actually change) and rebook. It checks blocks and other non-canceled bookings
on the same property, excluding the booking being edited. Canceled bookings hold no dates.
For the same invariant to hold in the other direction, a block cannot be created or moved
over a non-canceled booking. Overlapping blocks are allowed because they cause no harm. The spec
table is tested twice with the same case list: once against `DateRange` (unit tests) and once
end-to-end through the API (integration tests).

**Concurrency (bonus).** "Check, then insert" is only correct if no other writer can act in
between. Each write runs inside `write_transaction()`. On SQLite, that transaction is opened
with `BEGIN IMMEDIATE`, which takes the write lock before the availability query. A concurrent
writer waits for the lock, then sees the committed row and gets a clean 409. On PostgreSQL, the
services instead `SELECT ... FOR UPDATE` the parent property row, which serializes writers *per
property* without blocking other properties. `test_concurrency.py` forces the race: six threads
book the same dates while the gap between check and insert is artificially widened. Exactly
one succeeds. With a plain `BEGIN` instead, the test fails with "database is locked" errors.

**Status codes.** Overlaps return **409 Conflict** rather than 422. The request itself is
well-formed and valid; it conflicts with the *current state* of the resource, and the same
request can succeed later once the other booking is canceled. RFC 9110 defines 409 for exactly
this case. 422 suggests a problem with the payload itself. I used 409 for the same reason on
invalid state transitions (cancel a canceled booking, rebook a confirmed one). The brief asks
for 400 on malformed input, so FastAPI's default 422 for validation errors is remapped to 400.

**Assumptions and spec ambiguities.**
- *The overlap table contradicts its own rule in one row.* "New (before, no touch)" marks days
  10–12 against an existing 11–16 and says *No*, yet it shares days 11–12. Under the written
  rule ("shares even a single day") it is an overlap. The two "touches boundary" rows also
  overlap by several days. Most likely the columns are shifted. I implemented the written rule
  and test each row's stated intent (e.g. 9–10 does not overlap, 9–11 does). The literal
  10–12 case has its own test, marked as an overlap.
- Because boundaries are inclusive, a stay ending on the 16th and one starting on the 16th
  conflict. In other words, there are no same-day turnovers, which is what the brief specifies.
- `start_date` must be strictly before `end_date`, so a booking spans at least two days.
- Input is validated strictly. Pydantic's default lax mode would accept `true` as
  property 1, `"1"` as an ID, or a Unix timestamp as a date. For an API that must return
  400 on malformed input, that silent coercion is a bug, so IDs must be JSON integers and
  dates must be `YYYY-MM-DD` strings. IDs and offsets are capped at the 64-bit integer range,
  so an absurd ID is a 400 instead of a database driver overflow (500).
- The overlap rule matches "non-canceled" (`status <> CANCELED`) rather than `= CONFIRMED`, so
  it stays correct if another status (e.g. `PENDING`) is added later.
- Updates use `PATCH` with partial bodies. Omitted fields keep their values; an explicit
  `null` or an empty body is rejected with 400. A canceled booking's dates may be edited
  freely and are checked again on rebook. `property_id` and `status` cannot be changed through `PATCH`; status changes
  only through the explicit `cancel`/`rebook` actions.
- Authentication is a single shared API key, compared in constant time. If no key is
  configured, auth is off (keeping local use simple) and a warning is logged at startup.

**Limitations and trade-offs.**
- Tables are created with `create_all` on startup. A production service would use Alembic
  migrations.
- On SQLite, writers are serialized across the whole database, not per property. This is fine
  for this workload, but PostgreSQL is the scaling path. There I would also add an exclusion
  constraint (`EXCLUDE USING gist (property_id WITH =, daterange(start_date, end_date, '[]')
  WITH &&) WHERE (status <> 'CANCELED')`), so the database itself rejects overlapping bookings.
  Bookings vs. blocks span two tables, so that pairing would still need the property lock.
- No past-date check: bookings may be created in the past, for example to import historical
  data. Country codes are checked for format (two letters) but not against the ISO 3166 list.
- There are no endpoints to list, update or delete properties, as the brief does not require
  them. Foreign keys use `ON DELETE RESTRICT`, so a property with bookings or blocks cannot
  be deleted, and booking history is never erased as a side effect.
- The PostgreSQL locking path follows standard practice but is not covered by the test suite,
  which runs on SQLite only.
