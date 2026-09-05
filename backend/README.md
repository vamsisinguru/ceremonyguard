# CeremonyGuard Backend

FastAPI backend for the CeremonyGuard multi-party ceremony consistency system.

## Current Scope (Phases 1, 2, 3 & 4)

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

### Phase 4 — Recovery & Final Verification
- **Recovery workflow**: start recovery for an incomplete ceremony, creating a
  new attempt and marking the ceremony `recovering`. Existing canonical
  contributions are never modified.
- **Participant resume**: missing participants can resume their contribution
  during recovery. Duplicate/conflict rules continue to apply.
- **Recovery status**: check which participants are complete vs incomplete.
- **Ceremony completion check**: a ceremony is `ready` when every participant
  has exactly one accepted canonical contribution.
- **Final result generation**: deterministic HMAC-SHA256 digest over the
  canonical contribution set (simulated, not real threshold cryptography).
- **Final result verification**: recomputes the digest and compares against
  the stored value. Fails if any canonical contribution is modified, removed,
  or replaced.
- **Traceability**: verification response shows ceremony ID, participant
  IDs/names, canonical contribution IDs, hashes, attempt IDs, and digests.
- **Audit events**: `CEREMONY_RECOVERY_STARTED`, `PARTICIPANT_RECOVERY_RESUMED`,
  `FINAL_RESULT_GENERATED`, `FINAL_RESULT_VERIFIED`,
  `FINAL_RESULT_VERIFICATION_FAILED`.

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
│   │   ├── recovery.py
│   │   ├── verification.py
│   │   └── health.py
│   ├── core/         # Config + database engine/session
│   ├── crypto/       # Reserved for later phases
│   ├── models/       # SQLAlchemy ORM models (incl. CeremonyResult)
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic (ceremonies, participants, attempts, contributions, audit, recovery, verification)
│   └── main.py       # FastAPI app entrypoint
├── tests/            # pytest tests
└── requirements.txt
```

## Running

The backend serves both the REST API and the built React frontend, so the
complete application is available at a single URL.

### Build the frontend first

```bash
cd frontend
npm install
npm run build          # generates frontend/dist/
```

### Run the backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open **http://127.0.0.1:8000** for the CeremonyGuard dashboard, or
http://127.0.0.1:8000/docs for the interactive Swagger UI.

If `frontend/dist/` does not exist, the backend runs as an API-only server
and `GET /` returns a JSON info payload instead of the React app.

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
- `CEREMONY_RECOVERY_STARTED` (Phase 4)
- `PARTICIPANT_RECOVERY_RESUMED` (Phase 4)
- `FINAL_RESULT_GENERATED` (Phase 4)
- `FINAL_RESULT_VERIFIED` (Phase 4)
- `FINAL_RESULT_VERIFICATION_FAILED` (Phase 4)

A public read-only audit endpoint is available:

| Method | Path                              | Description                      |
|--------|-----------------------------------|----------------------------------|
| GET    | `/ceremonies/{ceremony_id}/audit` | List audit events for a ceremony |

### Recovery (Phase 4)
| Method | Path                                        | Description                              |
|--------|---------------------------------------------|------------------------------------------|
| POST   | `/ceremonies/{ceremony_id}/recovery/start`  | Start recovery for an incomplete ceremony|
| GET    | `/ceremonies/{ceremony_id}/recovery/status` | Check recovery status                    |
| POST   | `/ceremonies/{ceremony_id}/recovery/resume` | Resume a participant contribution        |

The resume endpoint returns a `RecoveryResumeResponse` with the submission
status (`accepted`/`duplicate`/`conflict`) and the updated recovery status.
HTTP status codes match the contribution submit endpoint (201/200/409).

### Final Verification (Phase 4)
| Method | Path                                        | Description                              |
|--------|---------------------------------------------|------------------------------------------|
| POST   | `/ceremonies/{ceremony_id}/finalize`        | Generate the final result                |
| GET    | `/ceremonies/{ceremony_id}/verification`    | Get final verification status            |
| POST   | `/ceremonies/{ceremony_id}/verify`          | Verify the final result                  |

The verification response (`FinalResultResponse`) includes:
- `ready`: whether all participants have canonical contributions
- `generated`: whether the final result has been generated
- `verified`: whether verification succeeded
- `verification_status`: `verified` | `verification_failed` | `not_generated` | `not_ready`
- `final_digest`, `contribution_digest`, `participant_count`
- `canonical_contributions`: list with participant IDs/names, contribution IDs, hashes, attempt IDs

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

### Phase 4 — Recovery & Verification

```bash
# 1. Add a third participant (Charlie) who fails to submit
curl -X POST http://127.0.0.1:8000/ceremonies/1/participants \
  -H 'Content-Type: application/json' -d '{"name":"Charlie"}'

# 2. Check recovery status -> ready: false (Charlie missing)
curl http://127.0.0.1:8000/ceremonies/1/recovery/status

# 3. Start recovery -> new attempt created, ceremony marked "recovering"
curl -X POST http://127.0.0.1:8000/ceremonies/1/recovery/start

# 4. Charlie resumes -> accepted (201)
curl -X POST http://127.0.0.1:8000/ceremonies/1/recovery/resume \
  -H 'Content-Type: application/json' \
  -d '{"participant_id":3,"contribution_data":"charlie-share"}'

# 5. Finalize -> final result generated and verified
curl -X POST http://127.0.0.1:8000/ceremonies/1/finalize

# 6. Verify again
curl -X POST http://127.0.0.1:8000/ceremonies/1/verify

# 7. Get verification status
curl http://127.0.0.1:8000/ceremonies/1/verification
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Phase 1 tests (app startup, health, database), Phase 2 tests (ceremonies,
participants, attempts, contributions, audit events), Phase 3 tests
(duplicate detection, conflict detection, ceremony isolation, cross-attempt
safety, the main demo scenario), and Phase 4 tests (recovery, final
verification, audit events, the full recovery demo) all run against an
in-memory SQLite database.
