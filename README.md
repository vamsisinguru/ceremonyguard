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

## Current Implementation Status (Phase 1)

Phase 1 establishes the project foundation only:

- Backend project structure with FastAPI application entrypoint.
- SQLAlchemy database configuration backed by SQLite.
- Foundation models for `Ceremony`, `Participant`, `CeremonyAttempt`,
  `Contribution`, and `AuditEvent`.
- Pydantic request/response schemas for the foundation entities.
- `GET /health` endpoint.
- React + Vite + Tailwind frontend with an initial placeholder dashboard.
- Basic Phase 1 tests (app startup, health endpoint, database connection).

Contribution validation, conflict resolution, recovery logic, and full
cryptographic verification are intentionally **not** implemented in Phase 1.

## Planned Future Phases

- **Phase 2:** Ceremony and participant lifecycle management (create ceremonies,
  register participants, start attempts).
- **Phase 3:** Contribution submission, idempotency, and duplicate detection.
- **Phase 4:** Conflict resolution and ceremony consistency enforcement.
- **Phase 5:** Recovery from failures and resumable ceremonies.
- **Phase 6:** Final cryptographic result aggregation and verification.
- **Phase 7:** Full dashboard UI and audit trail visualization.

## Repository

https://github.com/vamsisinguru/ceremonyguard.git
