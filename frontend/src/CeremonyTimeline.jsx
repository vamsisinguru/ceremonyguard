import { useMemo, useState } from "react";
import StatusBadge from "./StatusBadge.jsx";

// Map audit event_type → human-readable title + timeline status category.
const EVENT_INFO = {
  ceremony_created: { title: "Ceremony Created", category: "info" },
  ceremony_status_updated: { title: "Ceremony Status Updated", category: "info" },
  participant_created: { title: "Participant Joined", category: "info" },
  attempt_created: { title: "Attempt Created", category: "info" },
  contribution_submitted: { title: "Contribution Accepted", category: "accepted" },
  CONTRIBUTION_DUPLICATE: { title: "Duplicate Contribution", category: "duplicate" },
  CONTRIBUTION_CONFLICT: { title: "Conflicting Contribution", category: "conflict" },
  CEREMONY_RECOVERY_STARTED: { title: "Recovery Started", category: "recovery" },
  PARTICIPANT_RECOVERY_RESUMED: { title: "Recovery Resume", category: "recovery" },
  FINAL_RESULT_GENERATED: { title: "Final Result Generated", category: "verification" },
  FINAL_RESULT_VERIFIED: { title: "Final Verification Succeeded", category: "verified" },
  FINAL_RESULT_VERIFICATION_FAILED: {
    title: "Final Verification Failed",
    category: "failed",
  },
  // Smart Monitoring events
  SUBMISSION_RECOVERY_STARTED: { title: "Submission Recovery Started", category: "recovery" },
  SUBMISSION_STATUS_CHECKED: { title: "Submission Status Checked", category: "recovery" },
  SUBMISSION_ALREADY_ACCEPTED: { title: "Existing Contribution Found", category: "accepted" },
  SUBMISSION_RETRY_ACCEPTED: { title: "Safe Retry Accepted", category: "accepted" },
  SUBMISSION_RECOVERY_FAILED: { title: "Recovery Failed", category: "failed" },
  MANUAL_ACTION_REQUIRED: { title: "Manual Action Required", category: "conflict" },
};

const CATEGORY_BADGE = {
  info: null,
  accepted: "accepted",
  duplicate: "duplicate",
  conflict: "conflict",
  recovery: "recovering",
  verification: "verified",
  verified: "verified",
  failed: "verification_failed",
};

const CATEGORY_ICON = {
  info: "•",
  accepted: "✓",
  duplicate: "⚠",
  conflict: "✕",
  recovery: "↻",
  verification: "✓",
  verified: "✓",
  failed: "✕",
};

const CATEGORY_ICON_COLOR = {
  info: "text-slate-400",
  accepted: "text-emerald-400",
  duplicate: "text-amber-400",
  conflict: "text-red-400",
  recovery: "text-sky-400",
  verification: "text-emerald-400",
  verified: "text-emerald-400",
  failed: "text-red-400",
};

const FILTERS = [
  { key: "all", label: "All Events" },
  { key: "contributions", label: "Contributions" },
  { key: "problems", label: "Problems" },
  { key: "recovery", label: "Recovery" },
  { key: "verification", label: "Verification" },
];

function matchesFilter(category, filter) {
  switch (filter) {
    case "all":
      return true;
    case "contributions":
      return category === "accepted";
    case "problems":
      return category === "duplicate" || category === "conflict" || category === "failed";
    case "recovery":
      return category === "recovery";
    case "verification":
      return category === "verification" || category === "verified" || category === "failed";
    default:
      return true;
  }
}

// Extract a short explanation from the audit message + event info.
function buildExplanation(event, info) {
  const msg = event.message || "";
  if (info.category === "duplicate") {
    return "The same participant submitted a contribution with an identical SHA-256 fingerprint. The original canonical contribution was retained.";
  }
  if (info.category === "conflict") {
    if (event.event_type === "MANUAL_ACTION_REQUIRED") {
      return "Automatic recovery was not safe. Manual steps are required to resolve the submission.";
    }
    return "The same participant submitted a contribution with different data (different SHA-256 fingerprint). The original canonical contribution was retained and the new submission was rejected.";
  }
  if (info.category === "recovery") {
    if (event.event_type === "SUBMISSION_RECOVERY_STARTED") {
      return "The system began checking whether a submission was received after a connection interruption.";
    }
    if (event.event_type === "SUBMISSION_STATUS_CHECKED") {
      return "The system checked the submission status using the logical submission identifier.";
    }
    return msg || "Recovery action for an incomplete ceremony.";
  }
  if (event.event_type === "SUBMISSION_ALREADY_ACCEPTED") {
    return "An existing accepted contribution was found. No new contribution was created.";
  }
  if (event.event_type === "SUBMISSION_RETRY_ACCEPTED") {
    return "The same logical submission was safely retried and accepted. No duplicate canonical contribution was created.";
  }
  if (info.category === "verified") {
    return "The canonical contribution set is unchanged since finalization. The final result is valid.";
  }
  if (info.category === "failed") {
    if (event.event_type === "SUBMISSION_RECOVERY_FAILED") {
      return "Automatic recovery could not safely determine the submission state. Manual action is required.";
    }
    return "The canonical contribution set has changed since finalization. The final result is no longer valid.";
  }
  return msg;
}

export default function CeremonyTimeline({ auditEvents, participants, attempts }) {
  const [filter, setFilter] = useState("all");

  const participantMap = useMemo(() => {
    const m = new Map();
    participants.forEach((p) => m.set(p.id, p.name));
    return m;
  }, [participants]);

  const attemptMap = useMemo(() => {
    const m = new Map();
    attempts.forEach((a) => m.set(a.id, a.attempt_number));
    return m;
  }, [attempts]);

  // Chronological order (oldest first); UI shows newest at bottom.
  const ordered = useMemo(
    () => [...auditEvents].sort((a, b) => a.id - b.id),
    [auditEvents],
  );

  const filtered = useMemo(
    () =>
      ordered.filter((e) => {
        const info = EVENT_INFO[e.event_type] || { title: e.event_type, category: "info" };
        return matchesFilter(info.category, filter);
      }),
    [ordered, filter],
  );

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-200">Ceremony Timeline</h2>
        <span className="text-xs text-slate-500">
          {filtered.length} event{filtered.length === 1 ? "" : "s"}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        A chronological visualization of the existing audit trail for this ceremony.
      </p>

      {/* Filters */}
      <div className="mt-3 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded border px-2.5 py-1 text-xs ${
              filter === f.key
                ? "border-indigo-500 bg-indigo-600/20 text-indigo-200"
                : "border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Timeline */}
      {filtered.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">No events for this filter.</p>
      ) : (
        <ol className="mt-4 space-y-0">
          {filtered.map((e, idx) => {
            const info = EVENT_INFO[e.event_type] || {
              title: e.event_type,
              category: "info",
            };
            const isLast = idx === filtered.length - 1;
            const participantName = e.participant_id
              ? participantMap.get(e.participant_id) || `#${e.participant_id}`
              : null;
            const explanation = buildExplanation(e, info);
            const badge = CATEGORY_BADGE[info.category];

            return (
              <li key={e.id} className="flex gap-3">
                {/* Icon + connector line */}
                <div className="flex flex-col items-center">
                  <span
                    className={`text-lg leading-none ${CATEGORY_ICON_COLOR[info.category]}`}
                    aria-hidden="true"
                  >
                    {CATEGORY_ICON[info.category]}
                  </span>
                  {!isLast && (
                    <span
                      className="mt-1 w-px flex-1 bg-slate-700"
                      aria-hidden="true"
                    />
                  )}
                </div>

                {/* Content */}
                <div className={`flex-1 ${isLast ? "" : "pb-4"}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">
                      {info.title}
                    </span>
                    {badge && <StatusBadge status={badge} />}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-slate-500">
                    {participantName && (
                      <span>
                        <span className="text-slate-600">Participant:</span>{" "}
                        {participantName}
                      </span>
                    )}
                    <span>
                      <span className="text-slate-600">Event:</span>{" "}
                      <code className="text-indigo-300">{e.event_type}</code>
                    </span>
                    <span>
                      <span className="text-slate-600">When:</span> {e.created_at}
                    </span>
                  </div>
                  {explanation && (
                    <p className="mt-1 text-xs text-slate-400">{explanation}</p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
