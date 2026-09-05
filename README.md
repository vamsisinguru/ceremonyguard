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

## Phase 1 Technology Stack

| Layer    | Technology                |
|----------|---------------------------|
| Backend  | Python, FastAPI, Pydantic |
| Database | SQLAlchemy + SQLite       |
| Frontend | React, Vite, Tailwind CSS |
| Testing  | pytest, pytest-asyncio    |

## Current Implementation Status (Phase 3)

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

## Contribution Statuses

| Status      | Meaning                                                        | HTTP |
|-------------|----------------------------------------------------------------|------|
| `accepted`  | First valid contribution from a participant for a ceremony.    | 201  |
| `duplicate` | Retry with identical data; original retained.                  | 200  |
| `conflict`  | Retry with different data; original retained, new one rejected.| 409  |

## Example Demonstration Flow

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

## Planned Future Phases

- **Phase 4:** Conflict resolution and ceremony consistency enforcement.
- **Phase 5:** Recovery from failures and resumable ceremonies.
- **Phase 6:** Final cryptographic result aggregation and verification.
- **Phase 7:** Full dashboard UI and audit trail visualization.

## Repository

https://github.com/vamsisinguru/ceremonyguard.git
