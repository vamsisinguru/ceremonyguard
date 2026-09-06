import { useState } from "react";
import StatusBadge from "./StatusBadge.jsx";
import { api } from "./api.js";

const STATUS_MESSAGES = {
  accepted: null,
  duplicate:
    "Duplicate contribution detected. The original contribution was retained.",
  conflict:
    "Conflict detected. A different contribution was submitted by this participant. The original contribution was retained.",
};

const STATUS_BANNERS = {
  duplicate: "border-amber-500/50 bg-amber-500/10 text-amber-200",
  conflict: "border-red-500/50 bg-red-500/10 text-red-200",
};

// Generate a unique submission key for idempotent retries.
function generateSubmissionKey(ceremonyId, participantId, data) {
  const ts = Date.now();
  return `c${ceremonyId}-p${participantId}-${ts}`;
}

// Recovery UI states for the auto-recovery flow.
const RECOVERY_STEPS = {
  checking: {
    label: "Connection interrupted. Checking submission status...",
    style: "border-sky-500/50 bg-sky-500/10 text-sky-200",
  },
  alreadyAccepted: {
    label: "Your contribution was already accepted. You do not need to submit again.",
    style: "border-emerald-500/50 bg-emerald-500/10 text-emerald-200",
  },
  retrying: {
    label: "Submission not received. Retrying safely...",
    style: "border-sky-500/50 bg-sky-500/10 text-sky-200",
  },
  retryAccepted: {
    label: "Contribution accepted after safe retry.",
    style: "border-emerald-500/50 bg-emerald-500/10 text-emerald-200",
  },
  conflictDetected: {
    label: "Conflict detected. The original contribution has been preserved.",
    style: "border-red-500/50 bg-red-500/10 text-red-200",
  },
  unrecoverable: {
    label: "Automatic recovery could not safely determine the submission state.",
    style: "border-red-500/50 bg-red-500/10 text-red-200",
  },
};

function WhyRejected({ result, participants }) {
  const [open, setOpen] = useState(false);
  if (result.status !== "duplicate" && result.status !== "conflict") return null;

  const participant = participants.find(
    (p) => p.id === result.participant_id,
  );
  const participantName = participant?.name || `#${result.participant_id}`;
  const isDuplicate = result.status === "duplicate";
  const originalHash = result.original_hash || result.contribution.contribution_hash;
  const submittedHash = result.submitted_hash;
  const hashesMatch = originalHash === submittedHash;

  return (
    <div className="rounded border border-slate-700 bg-slate-950/70 p-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left text-sm font-medium text-slate-200"
      >
        <span>Why was this not accepted?</span>
        <span className="text-xs text-slate-500">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="mt-3 space-y-2 text-xs text-slate-400">
          <p className="text-slate-300">
            {isDuplicate
              ? "This participant already submitted a contribution with the same SHA-256 fingerprint for this ceremony."
              : "This participant already has a canonical contribution, but the new submission contains different data (different SHA-256 fingerprint)."}
          </p>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
            <div>
              <span className="text-slate-500">Participant:</span>{" "}
              <span className="text-slate-200">{participantName}</span>
            </div>
            <div>
              <span className="text-slate-500">Original contribution:</span>{" "}
              <span className="text-slate-200">
                #{result.original_contribution_id ?? result.contribution.id}
              </span>
            </div>
            {result.submitted_contribution_id && (
              <div>
                <span className="text-slate-500">Rejected submission:</span>{" "}
                <span className="text-slate-200">
                  #{result.submitted_contribution_id}
                </span>
              </div>
            )}
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2 font-mono">
            <div>
              <span className="text-slate-500">Original SHA-256:</span>
              <div className="mt-0.5 break-all text-slate-300">{originalHash}</div>
            </div>
            <div className="mt-2">
              <span className="text-slate-500">Submitted SHA-256:</span>
              <div className="mt-0.5 break-all text-slate-300">{submittedHash}</div>
            </div>
            <div className="mt-2">
              <span className="text-slate-500">Fingerprints match:</span>{" "}
              <span className={hashesMatch ? "text-amber-300" : "text-red-300"}>
                {hashesMatch ? "YES (identical data)" : "NO (different data)"}
              </span>
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
            <div className="text-slate-500">Decision</div>
            <p className="mt-1 text-slate-300">
              The original contribution remains canonical. The new submission
              was {isDuplicate ? "recorded as a duplicate" : "rejected as a conflict"}{" "}
              and was not accepted as a new canonical contribution.
            </p>
          </div>

          {result.reason && (
            <p className="text-slate-400">{result.reason}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function ContributionForm({
  ceremonyId,
  attemptId,
  participants,
  onSubmitted,
}) {
  const [participantId, setParticipantId] = useState(
    participants[0]?.id || "",
  );
  const [data, setData] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [recoveryStep, setRecoveryStep] = useState(null);
  const [recoveryReport, setRecoveryReport] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setRecoveryStep(null);
    setRecoveryReport(null);

    const pid = parseInt(participantId, 10);
    const submissionKey = generateSubmissionKey(ceremonyId, pid, data);

    // Attempt the initial submission with an idempotency key.
    let res;
    try {
      res = await api.submitContribution(
        ceremonyId,
        attemptId,
        pid,
        data,
        submissionKey,
      );
    } catch {
      // Network error / timeout — begin auto-recovery flow.
      await handleAutoRecovery(ceremonyId, pid, submissionKey, data);
      return;
    }

    // A timeout-like response (status 0 or non-JSON) also triggers recovery.
    if (res.status === 0 || res.body === null) {
      await handleAutoRecovery(ceremonyId, pid, submissionKey, data);
      return;
    }

    if (res.status === 404 || res.status === 400 || res.status === 422) {
      setError(res.body?.detail || "Submission failed.");
      return;
    }

    setResult(res.body);
    onSubmitted?.();
  };

  // Auto-recovery flow: check submission status, then retry if safe.
  const handleAutoRecovery = async (
    ceremonyId,
    pid,
    submissionKey,
    contributionData,
  ) => {
    setRecoveryStep("checking");

    // Step 1: Check if the submission already exists.
    let statusRes;
    try {
      statusRes = await api.getSubmissionStatus(ceremonyId, submissionKey);
    } catch {
      // Cannot reach server at all — unrecoverable.
      setRecoveryStep("unrecoverable");
      setRecoveryReport({
        issue: "Could not connect to the server to check submission status.",
        manualSteps: [
          "1. Check your connection to the server.",
          "2. Refresh the page and check the ceremony monitor.",
          "3. If your contribution is not listed, submit again.",
        ],
      });
      return;
    }

    if (statusRes.status === 200 && statusRes.body?.status === "ACCEPTED") {
      // Case A: existing contribution found and accepted.
      setRecoveryStep("alreadyAccepted");
      setResult({
        status: "accepted",
        message: "Contribution already accepted.",
        ceremony_id: ceremonyId,
        participant_id: pid,
        contribution: {
          id: statusRes.body.contribution_id,
          contribution_hash: statusRes.body.contribution_hash,
        },
        submitted_hash: statusRes.body.contribution_hash,
      });
      onSubmitted?.();
      return;
    }

    if (statusRes.status === 200 && statusRes.body?.status === "DUPLICATE") {
      // Existing duplicate — the canonical was already accepted.
      setRecoveryStep("alreadyAccepted");
      setResult({
        status: "duplicate",
        message: "Contribution already processed as duplicate.",
        ceremony_id: ceremonyId,
        participant_id: pid,
        contribution: {
          id: statusRes.body.contribution_id,
          contribution_hash: statusRes.body.contribution_hash,
        },
        submitted_hash: statusRes.body.contribution_hash,
      });
      onSubmitted?.();
      return;
    }

    if (statusRes.status === 200 && statusRes.body?.status === "CONFLICT") {
      // Case C: conflict detected.
      setRecoveryStep("conflictDetected");
      setResult({
        status: "conflict",
        message: "Conflict detected during recovery.",
        ceremony_id: ceremonyId,
        participant_id: pid,
        contribution: {
          id: statusRes.body.contribution_id,
          contribution_hash: statusRes.body.contribution_hash,
        },
        submitted_hash: statusRes.body.contribution_hash,
      });
      onSubmitted?.();
      return;
    }

    // Case B: NOT_FOUND — safely retry the same logical submission.
    setRecoveryStep("retrying");
    let retryRes;
    try {
      retryRes = await api.submitContribution(
        ceremonyId,
        attemptId,
        pid,
        contributionData,
        submissionKey,
      );
    } catch {
      setRecoveryStep("unrecoverable");
      setRecoveryReport({
        issue: "Safe retry could not reach the server.",
        manualSteps: [
          "1. Verify participant identity.",
          "2. Check ceremony status.",
          "3. Check whether a canonical contribution exists.",
          "4. Submit only if no canonical contribution exists.",
          "5. Run final verification.",
        ],
      });
      return;
    }

    if (retryRes.status === 0 || retryRes.body === null) {
      setRecoveryStep("unrecoverable");
      setRecoveryReport({
        issue: "Safe retry did not receive a response.",
        manualSteps: [
          "1. Verify participant identity.",
          "2. Check ceremony status.",
          "3. Check whether a canonical contribution exists.",
          "4. Submit only if no canonical contribution exists.",
          "5. Run final verification.",
        ],
      });
      return;
    }

    if (retryRes.status === 201 || retryRes.body?.status === "accepted") {
      setRecoveryStep("retryAccepted");
      setResult(retryRes.body);
      onSubmitted?.();
      return;
    }

    if (retryRes.body?.status === "duplicate") {
      setRecoveryStep("alreadyAccepted");
      setResult(retryRes.body);
      onSubmitted?.();
      return;
    }

    if (retryRes.body?.status === "conflict") {
      setRecoveryStep("conflictDetected");
      setResult(retryRes.body);
      onSubmitted?.();
      return;
    }

    // Case D: state cannot be determined.
    setRecoveryStep("unrecoverable");
    setRecoveryReport({
      issue: "Automatic recovery could not safely determine the submission state.",
      manualSteps: [
        "1. Verify participant identity.",
        "2. Check ceremony status.",
        "3. Check whether a canonical contribution exists.",
        "4. Resume the participant's ceremony attempt.",
        "5. Submit only if no canonical contribution exists.",
        "6. Run final verification.",
      ],
    });
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h3 className="text-base font-semibold text-slate-200">
        Submit Contribution
      </h3>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <div>
          <label className="block text-sm text-slate-400">Participant</label>
          <select
            value={participantId}
            onChange={(e) => setParticipantId(e.target.value)}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100"
          >
            {participants.length === 0 && (
              <option value="">No participants</option>
            )}
            {participants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} (id={p.id})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-slate-400">
            Contribution Data
          </label>
          <input
            type="text"
            value={data}
            onChange={(e) => setData(e.target.value)}
            placeholder="e.g. share-data-payload"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100"
          />
        </div>
        <button
          type="submit"
          disabled={!data || !participantId}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
        >
          Submit
        </button>
      </form>

      {error && (
        <p className="mt-3 text-sm text-red-400">{error}</p>
      )}

      {recoveryStep && RECOVERY_STEPS[recoveryStep] && (
        <div
          className={`mt-3 rounded border p-3 text-sm ${RECOVERY_STEPS[recoveryStep].style}`}
        >
          {RECOVERY_STEPS[recoveryStep].label}
        </div>
      )}

      {recoveryStep === "unrecoverable" && recoveryReport && (
        <div className="mt-3 rounded border border-red-500/40 bg-red-500/5 p-4">
          <h4 className="text-sm font-semibold text-red-300">
            Manual Recovery Steps
          </h4>
          <p className="mt-1 text-xs text-slate-400">
            {recoveryReport.issue}
          </p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-300">
            {recoveryReport.manualSteps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2">
            <StatusBadge status={result.status} />
            <span className="text-xs text-slate-500">
              HTTP {result.status === "accepted" ? "201" : result.status === "duplicate" ? "200" : "409"}
            </span>
          </div>

          {STATUS_MESSAGES[result.status] && (
            <div
              className={`rounded border p-3 text-sm ${STATUS_BANNERS[result.status]}`}
            >
              {STATUS_MESSAGES[result.status]}
            </div>
          )}

          <div className="rounded border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-400">
            <div>
              <span className="text-slate-500">Canonical contribution:</span>{" "}
              #{result.contribution.id}
            </div>
            <div>
              <span className="text-slate-500">Hash:</span>{" "}
              <code className="text-slate-300">
                {result.contribution.contribution_hash.substring(0, 16)}…
              </code>
            </div>
            <div>
              <span className="text-slate-500">Submitted hash:</span>{" "}
              <code className="text-slate-300">
                {result.submitted_hash.substring(0, 16)}…
              </code>
            </div>
          </div>

          <WhyRejected result={result} participants={participants} />
        </div>
      )}
    </div>
  );
}
