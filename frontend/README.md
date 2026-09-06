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

### Usability Enhancements — Ceremony Timeline & "Why Rejected?"
These are application-level usability and traceability enhancements, not part
of the underlying cryptographic protocol.

- **Ceremony Timeline** (`CeremonyTimeline.jsx`): a chronological visualization
  of the existing audit trail for the selected ceremony. Each event shows a
  human-readable title, status indicator (`✓ ACCEPTED`, `⚠ DUPLICATE`,
  `✕ CONFLICT`, `↻ RECOVERY`, `✓ VERIFIED`), participant, event type,
  timestamp, and a short explanation. Filters: All Events, Contributions,
  Problems, Recovery, Verification. The timeline reads the existing
  `GET /ceremonies/{id}/audit` endpoint — it does not duplicate audit records.
- **"Why Rejected?" explanation** (in `ContributionForm.jsx`): when a
  contribution is `duplicate` or `conflict`, an expandable "Why was this not
  accepted?" section shows the participant, original contribution ID, rejected
  submission ID, original and submitted SHA-256 fingerprints, whether the
  fingerprints match, and the decision. The explanation distinguishes
  DUPLICATE (same fingerprint) from CONFLICT (different fingerprint).

### Smart Ceremony Monitoring & Automatic Recovery
- **Ceremony Monitor** (`CeremonyMonitor.jsx`): shows per-participant
  submission state (accepted, missing, recovering, conflict, duplicate) and
  overall ceremony health. Includes a recovery report generator that produces
  an incident report with automatic action details or manual recovery steps.
- **Auto-recovery in ContributionForm**: when a submission times out or the
  response is lost, the form automatically:
  1. Checks the submission status using the idempotency key.
  2. If the contribution was already accepted, shows "Your contribution was
     already accepted."
  3. If the submission was not received, safely retries the same logical
     submission.
  4. If a conflict is detected, shows "Conflict detected. The original
     contribution has been preserved."
  5. If the state cannot be determined, shows manual recovery steps.
- **Timeline integration**: all monitoring/recovery audit events
  (`SUBMISSION_RECOVERY_STARTED`, `SUBMISSION_STATUS_CHECKED`,
  `SUBMISSION_ALREADY_ACCEPTED`, `SUBMISSION_RETRY_ACCEPTED`,
  `SUBMISSION_RECOVERY_FAILED`, `MANUAL_ACTION_REQUIRED`) appear in the
  existing Ceremony Timeline automatically.

The existing Phase 3 contribution and audit UI continues to work unchanged.

## Running

```bash
cd frontend
npm install
npm run dev
```

The dev server runs at http://127.0.0.1:5173 and proxies API requests to the
backend at http://127.0.0.1:8000 (see `vite.config.js`). Start the backend
first for full functionality.

## Build (for combined FastAPI serving)

```bash
npm run build      # production build to dist/
```

After building, run the FastAPI backend — it serves the built frontend from
`dist/` at http://127.0.0.1:8000. See the root README for full instructions.

## Preview

```bash
npm run preview    # preview the production build
```
