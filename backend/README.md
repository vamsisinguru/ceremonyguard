# CeremonyGuard Backend

FastAPI backend for the CeremonyGuard multi-party ceremony consistency system.

## Current Scope (Phases 1, 2 & 3)

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

### Phase 3 — Duplicate & Conflict Detection
- **Duplicate detection**: identical retry from the same participant for the
  same ceremony is classified as `duplicate` (HTTP 200). The original
  canonical contribution is retained.
- **Conflict detection**: a different submission from the same participant for
  the same ceremony is classified as `conflict` (HTTP 409). The original
  canonical contribution is retained; the conflicting one is recorded for
  audit history but rejected.
- **One canonical contribution per participant per ceremony**: enforced at the
  database level via a partial unique index on `(ceremony_id, participant_id)`
  where `status = 'accepted'`.
- **Cross-attempt safety**: a retry submitted via a different attempt does not
  replace the participant's canonical contribution.
- **Audit events**: `CONTRIBUTION_DUPLICATE` and `CONTRIBUTION_CONFLICT` are
  recorded for every duplicate/conflict event.
- **Audit API**: `GET /ceremonies/{id}/audit` exposes the audit trail.

Phase 4 recovery and final cryptographic verification are **not** implemented
yet.

## Layout

```
backend/
├── app/
│   ├── api/          # Route handlers
│   │   ├── ceremonies.py
│   │   ├── participants.py
│   │   ├── attempts.py
│   │   ├── contributions.py
│   │   ├── audit.py
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
| Method | Path                                                                  | Description                          |
|--------|-----------------------------------------------------------------------|--------------------------------------|
| POST   | `/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions`       | Submit a contribution (Phase 3 dup/conflict detection) |
| GET    | `/ceremonies/{ceremony_id}/attempts/{attempt_id}/contributions`       | List contributions for an attempt    |
| GET    | `/ceremonies/{ceremony_id}/contributions`                             | List all contributions for a ceremony|
| GET    | `/contributions/{contribution_id}`                                    | Retrieve a contribution              |

The submit endpoint returns a `ContributionSubmissionResponse`:

```json
{
  "status": "accepted | duplicate | conflict",
  "message": "...",
  "ceremony_id": 1,
  "participant_id": 1,
  "contribution": { "id": 1, "status": "accepted", "contribution_hash": "...", ... },
  "submitted_hash": "<sha256 of submitted data>"
}
```

| Outcome     | HTTP | Meaning                                                       |
|-------------|------|---------------------------------------------------------------|
| `accepted`  | 201  | First valid contribution for this participant in this ceremony. |
| `duplicate` | 200  | Identical retry; original canonical contribution retained.    |
| `conflict`  | 409  | Different data; original canonical contribution retained.     |

### Audit Events
Audit events are created automatically by the service layer for:
- `ceremony_created`
- `ceremony_status_updated`
- `participant_created`
- `attempt_created`
- `contribution_submitted`
- `CONTRIBUTION_DUPLICATE` (Phase 3)
- `CONTRIBUTION_CONFLICT` (Phase 3)

A public read-only audit endpoint is available:

| Method | Path                              | Description                      |
|--------|-----------------------------------|----------------------------------|
| GET    | `/ceremonies/{ceremony_id}/audit` | List audit events for a ceremony |

## Example API Workflow

```bash
# 1. Create a ceremony
curl -X POST http://127.0.0.1:8000/ceremonies \
  -H 'Content-Type: application/json' \
  -d '{"name":"Key Signing"}'
# -> {"id":1,"name":"Key Signing","status":"active","created_at":"..."}

# 2. Add participants
curl -X POST http://127.0.0.1:8000/ceremonies/1/participants \
  -H 'Content-Type: application/json' -d '{"name":"Alice"}'
curl -X POST http://127.0.0.1:8000/ceremonies/1/participants \
  -H 'Content-Type: application/json' -d '{"name":"Bob"}'

# 3. Create an attempt (attempt_number auto-increments)
curl -X POST http://127.0.0.1:8000/ceremonies/1/attempts

# 4. Submit a contribution (SHA-256 hash computed server-side) -> ACCEPTED (201)
curl -X POST http://127.0.0.1:8000/ceremonies/1/attempts/1/contributions \
  -H 'Content-Type: application/json' \
  -d '{"participant_id":1,"contribution_data":"alice-share"}'
# -> {"status":"accepted","contribution":{"id":1,"status":"accepted",...},...}

# 5. Retry with identical data -> DUPLICATE (200), original retained
curl -X POST http://127.0.0.1:8000/ceremonies/1/attempts/1/contributions \
  -H 'Content-Type: application/json' \
  -d '{"participant_id":1,"contribution_data":"alice-share"}'
# -> {"status":"duplicate","message":"Duplicate contribution detected...","...}

# 6. Retry with different data -> CONFLICT (409), original retained
curl -X POST http://127.0.0.1:8000/ceremonies/1/attempts/1/contributions \
  -H 'Content-Type: application/json' \
  -d '{"participant_id":1,"contribution_data":"alice-different"}'
# -> {"status":"conflict","message":"Conflict detected...","...}

# 7. View the audit trail
curl http://127.0.0.1:8000/ceremonies/1/audit

# 8. Update ceremony status
curl -X PATCH http://127.0.0.1:8000/ceremonies/1/status \
  -H 'Content-Type: application/json' -d '{"status":"completed"}'
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Phase 1 tests (app startup, health, database), Phase 2 tests (ceremonies,
participants, attempts, contributions, audit events), and Phase 3 tests
(duplicate detection, conflict detection, ceremony isolation, cross-attempt
safety, the main demo scenario) all run against an
in-memory SQLite database.
