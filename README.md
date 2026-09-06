# CeremonyGuard

**Multi-Party Ceremony Consistency System**

CeremonyGuard is a simulated multi-party cryptographic key/signature ceremony
consistency system. It coordinates multiple participants contributing to a
single ceremony, ensuring that the final cryptographic result is verifiable and
that the ceremony state remains consistent even when network failures, retries,
or duplicate contributions occur.

## Problem It Solves

In a multi-party cryptographic ceremony, several participants each contribute a
partial signature or key share. Real-world networks are unreliable: messages get
dropped, clients retry, and ceremonies may be restarted. This can lead to:

- Duplicate or conflicting contributions from the same participant.
- Contributions from different ceremony attempts being accidentally mixed.
- An ambiguous or unverifiable final cryptographic result.

CeremonyGuard aims to provide:

- Exactly one legitimate contribution per participant per ceremony attempt.
- Ceremony consistency across attempts and retries.
- Recovery from failures without compromising the ceremony.
- Verification of the final cryptographic result.

## Technology Stack

| Layer    | Technology                          |
|----------|-------------------------------------|
| Backend  | Python, FastAPI, Pydantic            |
| Database | SQLAlchemy + SQLite                  |
| Crypto   | `cryptography` (HMAC-SHA256)         |
| Frontend | React, Vite, Tailwind CSS            |
| Testing  | pytest, pytest-asyncio, httpx        |

## Running the Complete Application

The React frontend is built and served by the FastAPI backend, so the entire
application runs from **one server** on **http://127.0.0.1:8000**.

### One-terminal setup

```bash
# 1. Build the frontend
cd frontend
npm install
npm run build          # generates frontend/dist/

# 2. Run the backend (serves both API and frontend)
cd ../backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Then open **http://127.0.0.1:8000** in your browser.

| URL                          | What you get                      |
|------------------------------|-----------------------------------|
| http://127.0.0.1:8000/       | CeremonyGuard React dashboard     |
| http://127.0.0.1:8000/docs   | FastAPI Swagger UI                |
| http://127.0.0.1:8000/health | Health check API                  |
| http://127.0.0.1:8000/ceremonies | Ceremonies API (and all other APIs) |

### Development mode (optional)

If you want hot-reload for frontend development, run the Vite dev server
separately:

```bash
# Terminal 1 — backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend dev server
cd frontend
npm run dev          # http://127.0.0.1:5173 (proxies API calls to port 8000)
```

## Current Implementation Status (Phase 4)

### Phase 1 — Foundation
- Backend project structure with FastAPI application entrypoint.
- SQLAlchemy database configuration backed by SQLite.
- Foundation models for `Ceremony`, `Participant`, `CeremonyAttempt`,
  `Contribution`, and `AuditEvent`.
- Pydantic request/response schemas for the foundation entities.
- `GET /health` endpoint.
- React + Vite + Tailwind frontend with an initial placeholder dashboard.
- Basic Phase 1 tests (app startup, health endpoint, database connection).

### Phase 2 — Ceremony, Participants, Attempts, Contributions
- REST APIs for ceremonies (create, list, get, status update).
- REST APIs for participants (create, list, get) scoped to a ceremony.
- REST APIs for attempts (create with auto-incrementing attempt number,
  list, get) scoped to a ceremony.
- REST API for contributions (submit, list, get) with SHA-256
  fingerprinting of contribution data.
- Relationship validation: ceremony/attempt/participant must all be
  consistent before a contribution is accepted.
- Audit events recorded for ceremony, participant, attempt, and
  contribution creation.

### Phase 3 — Duplicate & Conflict Detection
- **Duplicate detection**: when a participant submits a contribution with
  the same SHA-256 hash as the existing canonical contribution for the same
  ceremony, the retry is classified as `duplicate`. The original is retained;
  the duplicate is recorded for audit history but never becomes canonical.
- **Conflict detection**: when a participant submits a contribution with a
  different hash, it is classified as `conflict`. The original remains
  canonical; the conflicting submission is recorded but rejected.
- **One canonical contribution per participant per ceremony**: enforced at the
  database level via a partial unique index on `(ceremony_id, participant_id)`
  where `status = 'accepted'`.
- **Ceremony isolation**: a participant can independently contribute to
  different ceremonies; an attempt from one ceremony cannot be used for another.
- **Cross-attempt safety**: a retry from a different attempt does not replace
  the participant's legitimate canonical contribution.
- **Audit trail**: `CONTRIBUTION_DUPLICATE` and `CONTRIBUTION_CONFLICT` audit
  events are recorded for every duplicate/conflict, with a public
  `GET /ceremonies/{id}/audit` endpoint.
- **Frontend dashboard**: shows ceremonies, participants, attempts,
  contributions with `accepted`/`duplicate`/`conflict` status badges, and an
  audit trail section.

Phase 4 recovery and final cryptographic verification are **not** implemented
yet.

### Phase 4 — Recovery & Final Verification
- **Recovery workflow**: when a ceremony is incomplete (some participants
  failed to submit), recovery can be started. A new attempt is created and
  the ceremony is marked `recovering`. Missing participants can resume their
  contributions without forcing already-complete participants to restart.
- **Recovery preserves canonical contributions**: existing accepted
  contributions are never modified or removed during recovery.
- **Recovery preserves ceremony identity**: the original ceremony ID is kept.
- **Recovery isolation**: a participant from a different ceremony cannot
  resume into this ceremony's recovery.
- **Duplicate/conflict rules apply during recovery**: resubmitting identical
  data is `duplicate`; different data is `conflict`. The original canonical
  contribution is always retained.
- **Ceremony completion check**: a ceremony is `ready` when every participant
  has exactly one accepted canonical contribution. Duplicate/conflict records
  do not count.
- **Final result generation**: when ready, the ceremony can be finalized.
  The final result is a deterministic HMAC-SHA256 digest computed over the
  set of canonical contributions. This is a **simulated** educational
  ceremony — not a real threshold signature.
- **Final result verification**: the stored digest is compared against a
  freshly computed digest from the current canonical contributions.
  Verification fails if any canonical contribution is modified, removed, or
  replaced.
- **Traceability**: the verification response shows ceremony ID, participant
  IDs/names, canonical contribution IDs, contribution hashes, attempt IDs,
  the final digest, and verification status.
- **Audit events**: `CEREMONY_RECOVERY_STARTED`, `PARTICIPANT_RECOVERY_RESUMED`,
  `FINAL_RESULT_GENERATED`, `FINAL_RESULT_VERIFIED`,
  `FINAL_RESULT_VERIFICATION_FAILED`.
- **Frontend dashboard**: Recovery section (status, incomplete participants,
  resume form) and Final Verification section (readiness, canonical
  contributions, finalize/verify actions, verification result).

### Usability Enhancements — Ceremony Timeline & "Why Rejected?"
These are application-level usability and traceability enhancements. They are
**not** part of the underlying cryptographic protocol.

- **Ceremony Timeline**: a frontend visualization of the existing audit trail
  (`GET /ceremonies/{id}/audit`). It renders the complete history of a
  selected ceremony in chronological order with human-readable titles
  (e.g. "Ceremony Created", "Contribution Accepted", "Duplicate Contribution",
  "Recovery Started", "Final Verification Succeeded") and clear status
  indicators (`✓ ACCEPTED`, `⚠ DUPLICATE`, `✕ CONFLICT`, `↻ RECOVERY`,
  `✓ VERIFIED`). Filters: All Events, Contributions, Problems, Recovery,
  Verification. The timeline does **not** duplicate audit records — it only
  reads them.
- **"Why Rejected?" explanation**: when a contribution is `duplicate` or
  `conflict`, the contribution form shows an expandable "Why was this not
  accepted?" section. It displays the participant, original contribution ID,
  rejected submission ID, original and submitted SHA-256 fingerprints, whether
  the fingerprints match, and the decision. The explanation distinguishes
  DUPLICATE (same fingerprint) from CONFLICT (different fingerprint) and
  always notes that the original canonical contribution is retained. The data
  comes from the existing contribution submission response, extended with
  optional backward-compatible fields: `original_contribution_id`,
  `submitted_contribution_id`, `original_hash`, and `reason`.

### Smart Ceremony Monitoring & Automatic Recovery

CeremonyGuard is a **simulated/educational** cryptographic ceremony system.
The Smart Monitoring feature makes it actively monitor ceremony state and
safely recover contribution-submission problems.

**Core principle:** "Never lose a valid contribution because of a temporary
connection failure, and never guess when the system cannot safely recover."

**Why this feature exists:** In a multi-party ceremony, participants submit
contributions over a network. If a submission response is lost (timeout,
connection interruption), the participant does not know whether their
contribution was received. Naively retrying could create duplicate or
conflicting contributions. Smart Monitoring solves this with idempotent
submission keys and automatic recovery.

**What it monitors (server-side ceremony state, NOT physical Wi-Fi):**
- Ceremony status (active, recovering, etc.)
- Required participant count vs. accepted canonical contribution count
- Missing/incomplete participants
- Unresolved submissions (via submission key lookup)
- Duplicate/conflict events
- Recovery state
- Final verification state

**What it can automatically recover:**
- If a submission was already accepted but the response was lost, the system
  confirms the existing contribution without creating a new one.
- If a submission never reached the server, the system safely retries the
  same logical submission (using the same idempotency key).

**What it cannot recover:**
- Conflicting contributions (different data from the same participant). The
  original is preserved and manual action is required.
- Situations where the state cannot be safely determined. The system stops
  and generates a manual-action report.

**Why idempotent retry prevents duplicate canonical contributions:** Each
submission includes an optional `submission_key`. The server records this key
and maps it to the resulting contribution. If the same key is submitted again,
the original result is returned without creating a new contribution. This
means a lost response does not lead to a second canonical contribution.

**Why the system does not claim to detect physical network failure:** The
system can only observe application-level conditions (request timeout,
connection interruption at the HTTP layer, submission confirmation not
received, unresolved submission state). It cannot determine whether a
participant's Wi-Fi or mobile signal failed. The UI uses wording like
"Connection interrupted" or "Submission confirmation was not received."

**What happens when automatic recovery is impossible:** The system generates
an incident report with manual recovery steps:
1. Verify participant identity.
2. Check ceremony status.
3. Check whether a canonical contribution exists.
4. Resume the participant's ceremony attempt.
5. Submit only if no canonical contribution exists.
6. Run final verification.

**New endpoints:**
- `GET  /ceremonies/{ceremony_id}/monitor` — overall ceremony monitoring status.
- `GET  /ceremonies/{ceremony_id}/submissions/{submission_key}/status` —
  submission status lookup by idempotency key.
- `POST /ceremonies/{ceremony_id}/recovery/report` — generate an
  incident/recovery report for a participant.

**New audit events:**
- `SUBMISSION_RECOVERY_STARTED`
- `SUBMISSION_STATUS_CHECKED`
- `SUBMISSION_ALREADY_ACCEPTED`
- `SUBMISSION_RETRY_ACCEPTED`
- `SUBMISSION_RECOVERY_FAILED`
- `MANUAL_ACTION_REQUIRED`

**Frontend additions:**
- **Ceremony Monitor** section: shows per-participant submission state
  (accepted, missing, recovering, conflict, duplicate) and overall ceremony
  health (healthy, incomplete, recovering, conflict_requires_attention,
  verification_failed). Includes a recovery report generator.
- **Auto-recovery in ContributionForm**: when a submission times out or the
  response is lost, the form automatically checks the submission status and
  either confirms the existing contribution or safely retries. The
  participant sees clear messages like "Connection interrupted. Checking
  submission status..." and "Your contribution was already accepted."
- **Timeline integration**: all monitoring/recovery events appear in the
  existing Ceremony Timeline automatically.

## Contribution Statuses

| Status      | Meaning                                                        | HTTP |
|-------------|----------------------------------------------------------------|------|
| `accepted`  | First valid contribution from a participant for a ceremony.    | 201  |
| `duplicate` | Retry with identical data; original retained.                  | 200  |
| `conflict`  | Retry with different data; original retained, new one rejected.| 409  |

## Verification Statuses

| Status               | Meaning                                                       |
|----------------------|---------------------------------------------------------------|
| `verified`           | Final result generated and canonical set unchanged.           |
| `verification_failed`| Canonical contribution set has changed since finalization.    |
| `not_generated`      | Ceremony is ready but final result not yet generated.         |
| `not_ready`          | Not all participants have canonical contributions.            |

## Simulated Cryptographic Model

This is a **simulated educational ceremony**, not production threshold
cryptography. The final result is computed as follows:

1. Collect all canonical (`accepted`) contributions, ordered by participant ID.
2. Compute a `contribution_digest` = SHA-256 of the ordered contribution hashes.
3. Compute a `final_digest` = HMAC-SHA256 of the contribution set using a
   ceremony-derived key.
4. Persist both digests in `CeremonyResult`.

Verification recomputes both digests from the current canonical contributions
and compares them against the stored values. If they match, the canonical
contribution set is unchanged. If they differ, a contribution was modified,
removed, or replaced.

**Limitations**: this does not implement a real threshold signature scheme,
does not use participant private keys, and is not suitable for production use.

## Example Demonstration Flow

### Phase 3 — Duplicate & Conflict

1. Create a ceremony.
2. Add participants A, B, C.
3. Create an attempt.
4. A submits `A1` → **accepted**.
5. B submits `B1` → **accepted**.
6. C submits `C1` → **accepted**.
7. Simulated network failure → C retries with `C2` (different from `C1`).
8. `C2` → **conflict** (409). `C1` remains canonical.
9. A `CONTRIBUTION_CONFLICT` audit event is recorded.
10. The ceremony can continue.

### Phase 4 — Recovery & Verification

1. Create a ceremony with participants A, B, C.
2. A and B submit accepted contributions. C fails (network failure).
3. `GET /ceremonies/{id}/recovery/status` → `ready: false`, C is incomplete.
4. `POST /ceremonies/{id}/recovery/start` → new recovery attempt created,
   ceremony marked `recovering`.
5. C resumes via `POST /ceremonies/{id}/recovery/resume` → **accepted**.
6. `GET /ceremonies/{id}/recovery/status` → `ready: true`.
7. `POST /ceremonies/{id}/finalize` → final result generated and verified.
8. `POST /ceremonies/{id}/verify` → verification succeeds.
9. Audit trail shows recovery and verification events.

## Planned Future Phases

- **Phase 5:** Resumable ceremonies with persistent recovery state.
- **Phase 6:** Real threshold cryptographic result aggregation.
- **Phase 7:** Full dashboard UI and audit trail visualization.

## Repository

https://github.com/vamsisinguru/ceremonyguard.git
