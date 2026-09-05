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
