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

## Current Implementation Status (Phase 2)

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

Duplicate/conflict detection, cross-attempt contribution protection,
recovery logic, and full cryptographic verification are intentionally
**not** implemented yet.

## Planned Future Phases

- **Phase 3:** Contribution idempotency and duplicate/conflict detection.
- **Phase 4:** Conflict resolution and ceremony consistency enforcement.
- **Phase 5:** Recovery from failures and resumable ceremonies.
- **Phase 6:** Final cryptographic result aggregation and verification.
- **Phase 7:** Full dashboard UI and audit trail visualization.

## Repository

https://github.com/vamsisinguru/ceremonyguard.git
