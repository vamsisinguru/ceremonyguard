# CeremonyGuard Frontend

React + Vite + Tailwind CSS frontend for CeremonyGuard.

## Current Scope (Phases 1, 2 & 3)

### Phase 1 — Foundation
- Vite + React project scaffold.
- Tailwind CSS configured.
- Initial placeholder dashboard.

### Phase 2 — Ceremony Management
- Ceremony selector and creator.
- Participant and attempt management.

### Phase 3 — Duplicate & Conflict Detection
- Contribution submission form with live status feedback.
- Visual distinction between `accepted` (green), `duplicate` (amber), and
  `conflict` (red) contribution statuses.
- Clear banner messages for duplicate and conflict outcomes:
  - "Duplicate contribution detected. The original contribution was retained."
  - "Conflict detected. A different contribution was submitted by this
    participant. The original contribution was retained."
- Contributions table showing each contribution's status badge.
- Audit trail table showing participant, event type, message, and timestamp.

The full dashboard, recovery UI, and final cryptographic result visualization
are deferred to later phases.

## Running

```bash
cd frontend
npm install
npm run dev
```

The dev server runs at http://127.0.0.1:5173 and proxies `/api/*` requests to
the backend at http://127.0.0.1:8000 (see `vite.config.js`). Start the backend
first for full functionality.

## Build

```bash
npm run build      # production build to dist/
npm run preview    # preview the production build
```
