# CeremonyGuard Frontend

React + Vite + Tailwind CSS frontend for CeremonyGuard.

## Current Scope (Phases 1, 2, 3 & 4)

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
- Clear banner messages for duplicate and conflict outcomes.
- Contributions table showing each contribution's status badge.
- Audit trail table showing participant, event type, message, and timestamp.

### Phase 4 — Recovery & Final Verification
- **Recovery section**: shows ceremony recovery status (`ready`/`recovering`/
  `incomplete`), incomplete and complete participants, a "Start Recovery"
  button, and a resume form for missing participants to submit their
  contribution during recovery.
- **Final Verification section**: shows whether the ceremony is ready, the
  list of canonical contributions (participant, contribution ID, attempt ID,
  hash), "Finalize" and "Verify" buttons, and the verification result
  (`verified`/`verification_failed`/`not_generated`/`not_ready`) with final
  and contribution digests.
- Status badges for Phase 4 states: `READY`, `RECOVERING`, `INCOMPLETE`,
  `VERIFIED`, `VERIFICATION_FAILED`.

The existing Phase 3 contribution and audit UI continues to work unchanged.

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
