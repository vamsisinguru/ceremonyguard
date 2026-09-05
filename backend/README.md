# CeremonyGuard Backend

FastAPI backend for the CeremonyGuard multi-party ceremony consistency system.

## Current Scope (Phases 1 & 2)

### Phase 1 — Foundation
- FastAPI application with `lifespan` startup that initializes the SQLite database.
- `GET /health` endpoint that verifies database connectivity.
- SQLAlchemy models for `Ceremony`, `Participant`, `CeremonyAttempt`,
  `Contribution`, and `AuditEvent`.
- Pydantic request/response schemas for the foundation entities.
- Basic Phase 1 tests.

### Phase 2 — Ceremony, Participants, Attempts, Contributions
- REST APIs for ceremonies, participants, attempts, and contributions.
- Automatic attempt numbering per ceremony (1, 2, 3, ...).
- SHA-256 fingerprinting of contribution data for integrity.
- Relationship validation (ceremony/attempt/participant must be consistent).
- Audit events recorded for every important operation.

Duplicate/conflict detection, cross-attempt contribution protection, recovery,
and cryptographic verification are intentionally **not** implemented yet.

## Layout

```
backend/
├── app/
│   ├── api/          # Route handlers
│   │   ├── ceremonies.py
│   │   ├── participants.py
│   │   ├── attempts.py
│   │   ├── contributions.py
│   │   └── health.py
│   ├── core/         # Config + database engine/session
│   ├── crypto/       # Reserved for later phases
│   ├── models/       # SQLAlchemy ORM models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic (ceremonies, participants, attempts, contributions, audit)
│   └── main.py       # FastAPI app entrypoint
├── tests/            # pytest tests
└── requirements.txt
```

## Running

```bash
cd backend
python3.12 -m venv .venv
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

## API Reference

### Ceremonies
| Method | Path                              | Description                |
|--------|-----------------------------------|----------------------------|
| POST   | `/ceremonies`                     | Create a ceremony          |
| GET    | `/ceremonies`                     | List ceremonies            |
| GET    | `/ceremonies/{ceremony_id}`       | Retrieve a ceremony        |
| PATCH  | `/ceremonies/{ceremony_id}/status`| Update ceremony status     |

### Participants
| Method | Path                                              | Description                  |
|--------|---------------------------------------------------|------------------------------|
| POST   | `/ceremonies/{ceremony_id}/participants`          | Add a participant            |
| GET    | `/ceremonies/{ceremony_id}/participants`          | List participants in ceremony|
| GET    | `/participants/{participant_id}`                  | Retrieve a participant       |

### Attempts
| Method | Path                                          | Description                       |
|--------|-----------------------------------------------|-----------------------------------|
| POST   | `/ceremonies/{ceremony_id}/attempts`          | Create a new attempt (auto-number)|
| GET    | `/ceremonies/{ceremony_id}/attempts`          | List attempts for a ceremony      |
| GET    | `/attempts/{attempt_id}`                      | Retrieve an attempt               |

### Contributions
| Method | Path                                                                  | Description                       |
|--------|-----------------------------------------------------------------------|-----------------------------------|
| POST   | `/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions`       | Submit a contribution             |
| GET    | `/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions`       | List contributions for an attempt |
| GET    | `/contributions/{contribution_id}`                                    | Retrieve a contribution           |

### Audit Events
Audit events are created automatically by the service layer for:
- `ceremony_created`
- `ceremony_status_updated`
- `participant_created`
- `attempt_created`
- `contribution_submitted`

There is no public audit endpoint in Phase 2; audit rows are verified via the
database in tests. A public audit API is planned for a later phase.

## Example API Workflow

```bash
# 1. Create a ceremony
curl -X POST http://127.0.0.1:8000/ceremonies \
  -H 'Content-Type: application/json' \
  -d '{"name":"Key Signing"}'
# -> {"id":1,"name":"Key Signing","status":"active","created_at":"..."}

# 2. Add a participant
curl -X POST http://127.0.0.1:8000/ceremonies/1/participants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alice"}'
# -> {"id":1,"ceremony_id":1,"name":"Alice","status":"active","created_at":"..."}

# 3. Create an attempt (attempt_number auto-increments)
curl -X POST http://127.0.0.1:8000/ceremonies/1/attempts
# -> {"id":1,"ceremony_id":1,"attempt_number":1,"status":"active","created_at":"..."}

# 4. Submit a contribution (SHA-256 hash is computed server-side)
curl -X POST http://127.0.0.1:8000/ceremonies/1/attempts/1/contributions \
  -H 'Content-Type: application/json' \
  -d '{"participant_id":1,"contribution_data":"my-share-data"}'
# -> {"id":1,"ceremony_id":1,"attempt_id":1,"participant_id":1,
#     "contribution_hash":"<sha256>","contribution_data":"my-share-data",
#     "status":"accepted","created_at":"..."}

# 5. Update ceremony status
curl -X PATCH http://127.0.0.1:8000/ceremonies/1/status \
  -H 'Content-Type: application/json' \
  -d '{"status":"completed"}'
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Phase 1 tests (app startup, health, database) and Phase 2 tests (ceremonies,
participants, attempts, contributions, audit events) all run against an
in-memory SQLite database.
