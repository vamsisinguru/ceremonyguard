# CeremonyGuard Backend

FastAPI backend for the CeremonyGuard multi-party ceremony consistency system.

## Phase 1 Scope

- FastAPI application with `lifespan` startup that initializes the SQLite database.
- `GET /health` endpoint that verifies database connectivity.
- SQLAlchemy models for `Ceremony`, `Participant`, `CeremonyAttempt`,
  `Contribution`, and `AuditEvent`.
- Pydantic request/response schemas for the foundation entities.
- Basic Phase 1 tests.

## Layout

```
backend/
├── app/
│   ├── api/          # Route handlers (health)
│   ├── core/         # Config + database engine/session
│   ├── crypto/       # Reserved for later phases
│   ├── models/       # SQLAlchemy ORM models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Service layer (populated in later phases)
│   └── main.py       # FastAPI app entrypoint
├── tests/            # pytest tests
└── requirements.txt
```

## Running

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is served at http://127.0.0.1:8000 — open
http://127.0.0.1:8000/docs for the interactive Swagger UI.

## Configuration

Configuration is read from environment variables with sensible defaults:

| Variable      | Default                        | Description                  |
|---------------|--------------------------------|------------------------------|
| `APP_NAME`    | `CeremonyGuard`                | Application name             |
| `ENVIRONMENT` | `development`                  | Environment label            |
| `DATABASE_URL`| `sqlite:///./ceremonyguard.db` | SQLAlchemy database URL      |
| `DB_ECHO`     | `false`                        | Echo SQL statements to logs  |

## Tests

```bash
cd backend
pytest -v
```
