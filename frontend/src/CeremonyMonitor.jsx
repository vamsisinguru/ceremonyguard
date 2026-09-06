import { useEffect, useState, useCallback } from "react";
import StatusBadge from "./StatusBadge.jsx";
import { api } from "./api.js";

// Map monitor submission_state to a display icon.
const STATE_ICON = {
  accepted: "✓",
  missing: "○",
  recovering: "↻",
  conflict: "✕",
  duplicate: "⚠",
};

const STATE_ICON_COLOR = {
  accepted: "text-emerald-400",
  missing: "text-amber-400",
  recovering: "text-sky-400",
  conflict: "text-red-400",
  duplicate: "text-amber-400",
};

export default function CeremonyMonitor({ ceremonyId, onUpdated }) {
  const [monitor, setMonitor] = useState(null);
  const [report, setReport] = useState(null);
  const [reportParticipantId, setReportParticipantId] = useState("");
  const [loading, setLoading] = useState(false);

  const loadMonitor = useCallback(async () => {
    if (!ceremonyId) return;
    const res = await api.getMonitor(ceremonyId);
    if (res.status === 200) {
      setMonitor(res.body);
    } else {
      setMonitor(null);
    }
  }, [ceremonyId]);

  useEffect(() => {
    loadMonitor();
  }, [loadMonitor]);

  const handleGenerateReport = async (e) => {
    e.preventDefault();
    if (!reportParticipantId) return;
    setLoading(true);
    setReport(null);
    const res = await api.generateRecoveryReport(
      ceremonyId,
      parseInt(reportParticipantId, 10),
    );
    setLoading(false);
    if (res.status === 200) {
      setReport(res.body);
      onUpdated?.();
      await loadMonitor();
    } else {
      setReport({
        error: res.body?.detail || "Failed to generate recovery report.",
      });
    }
  };

  if (!monitor) {
    return (
      <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
        <h2 className="text-base font-semibold text-slate-200">
          Ceremony Monitor
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Monitoring data unavailable.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-200">
          Ceremony Monitor
        </h2>
        <button
          onClick={loadMonitor}
          className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs text-slate-400 hover:border-slate-600"
        >
          Refresh
        </button>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Server-side ceremony state monitoring. This does not monitor your
        physical internet connection.
      </p>

      {/* Overall status */}
      <div className="mt-3 flex items-center gap-2">
        <StatusBadge status={monitor.monitor_status} />
        <span className="text-xs text-slate-500">
          {monitor.participants_with_contribution}/{monitor.total_participants} participants submitted
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-400">{monitor.message}</p>

      {/* Per-participant table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500">
              <th className="pb-2 pr-4">Participant</th>
              <th className="pb-2 pr-4">State</th>
              <th className="pb-2 pr-4">Contribution</th>
              <th className="pb-2 pr-4">Issues</th>
            </tr>
          </thead>
          <tbody>
            {monitor.participants.map((p) => (
              <tr key={p.participant_id} className="border-t border-slate-800/60">
                <td className="py-2 pr-4 text-slate-200">
                  <span className={`mr-1.5 ${STATE_ICON_COLOR[p.submission_state] || "text-slate-500"}`}>
                    {STATE_ICON[p.submission_state] || "•"}
                  </span>
                  {p.participant_name}
                </td>
                <td className="py-2 pr-4">
                  <StatusBadge status={p.submission_state} />
                </td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {p.contribution_id ? `#${p.contribution_id}` : "—"}
                </td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {p.issues.length > 0 ? p.issues.join("; ") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Issues summary */}
      {monitor.issues.length > 0 && (
        <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/5 p-3">
          <h3 className="text-xs font-semibold text-amber-300">Issues</h3>
          <ul className="mt-1 space-y-0.5 text-xs text-amber-200/80">
            {monitor.issues.map((issue, i) => (
              <li key={i}>• {issue}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recovery report generator */}
      <div className="mt-4 border-t border-slate-800 pt-4">
        <h3 className="text-sm font-semibold text-slate-200">
          Generate Recovery Report
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Generate an incident report for a participant with an unresolved
          submission.
        </p>
        <form onSubmit={handleGenerateReport} className="mt-2 flex gap-2">
          <select
            value={reportParticipantId}
            onChange={(e) => setReportParticipantId(e.target.value)}
            className="flex-1 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100"
          >
            <option value="">Select participant...</option>
            {monitor.participants.map((p) => (
              <option key={p.participant_id} value={p.participant_id}>
                {p.participant_name} (id={p.participant_id})
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={!reportParticipantId || loading}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
          >
            {loading ? "Generating..." : "Generate Report"}
          </button>
        </form>
      </div>

      {/* Recovery report display */}
      {report && !report.error && (
        <div className="mt-4 rounded border border-slate-700 bg-slate-950/70 p-4">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-200">
              Ceremony Recovery Report
            </h3>
            <StatusBadge status={report.recovery_status} />
          </div>

          <div className="mt-3 space-y-2 text-xs">
            <div>
              <span className="text-slate-500">Ceremony:</span>{" "}
              <span className="text-slate-200">#{report.ceremony_id} {report.ceremony_name}</span>
            </div>
            <div>
              <span className="text-slate-500">Participant:</span>{" "}
              <span className="text-slate-200">{report.participant_name}</span>
            </div>
            {report.attempt_id && (
              <div>
                <span className="text-slate-500">Attempt:</span>{" "}
                <span className="text-slate-200">#{report.attempt_id}</span>
              </div>
            )}
            <div>
              <span className="text-slate-500">Issue:</span>{" "}
              <span className="text-slate-300">{report.issue}</span>
            </div>
            <div>
              <span className="text-slate-500">Detected state:</span>{" "}
              <span className="text-slate-300">{report.detected_state}</span>
            </div>
            <div>
              <span className="text-slate-500">Automatic action:</span>{" "}
              <span className="text-slate-300">{report.automatic_action}</span>
            </div>
            <div>
              <span className="text-slate-500">Duplicate created:</span>{" "}
              <span className={report.duplicate_created ? "text-amber-300" : "text-emerald-300"}>
                {report.duplicate_created ? "YES" : "NO"}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Canonical contribution changed:</span>{" "}
              <span className={report.canonical_contribution_changed ? "text-red-300" : "text-emerald-300"}>
                {report.canonical_contribution_changed ? "YES" : "NO"}
              </span>
            </div>
            <div>
              <span className="text-slate-500">Ceremony ready:</span>{" "}
              <span className={report.ceremony_ready ? "text-emerald-300" : "text-amber-300"}>
                {report.ceremony_ready ? "YES" : "NO"}
              </span>
            </div>
            {report.contribution_id && (
              <div>
                <span className="text-slate-500">Contribution:</span>{" "}
                <span className="text-slate-200">#{report.contribution_id}</span>
              </div>
            )}
          </div>

          <p className="mt-3 text-sm text-slate-300">{report.message}</p>

          {report.manual_steps.length > 0 && (
            <div className="mt-3 rounded border border-red-500/30 bg-red-500/5 p-3">
              <h4 className="text-xs font-semibold text-red-300">
                Manual Action Required
              </h4>
              <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-xs text-slate-300">
                {report.manual_steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {report?.error && (
        <p className="mt-3 text-sm text-red-400">{report.error}</p>
      )}
    </section>
  );
}
