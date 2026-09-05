import { useState } from "react";
import StatusBadge from "./StatusBadge.jsx";
import { api } from "./api.js";

export default function FinalVerificationSection({
  ceremonyId,
  verification,
  onUpdated,
}) {
  const [error, setError] = useState(null);

  const handleFinalize = async () => {
    setError(null);
    const res = await api.finalizeCeremony(ceremonyId);
    if (res.status !== 200) {
      setError(res.body?.detail || "Finalization failed.");
      return;
    }
    onUpdated?.();
  };

  const handleVerify = async () => {
    setError(null);
    const res = await api.verifyCeremony(ceremonyId);
    if (res.status !== 200) {
      setError(res.body?.detail || "Verification failed.");
      return;
    }
    onUpdated?.();
  };

  if (!verification) return null;

  const {
    ready,
    generated,
    verified,
    verification_status,
    canonical_contributions = [],
    final_digest,
    contribution_digest,
    participant_count,
    message,
  } = verification;

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-200">
          Final Verification
        </h2>
        <div className="flex items-center gap-2">
          <StatusBadge status={verification_status} />
          {ready && (
            <span className="text-xs text-slate-500">
              {canonical_contributions.length} canonical contributions
            </span>
          )}
        </div>
      </div>

      <p className="mt-3 text-sm text-slate-400">{message}</p>

      {/* Readiness */}
      <div className="mt-3 flex items-center gap-2 text-sm">
        <span className="text-slate-500">Ceremony Ready:</span>
        <StatusBadge status={ready ? "ready" : "not_ready"} />
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        <button
          onClick={handleFinalize}
          disabled={!ready}
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
        >
          {generated ? "Re-finalize" : "Finalize"}
        </button>
        <button
          onClick={handleVerify}
          disabled={!generated}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
        >
          Verify
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      {/* Canonical contributions list */}
      {canonical_contributions.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-medium text-slate-300">
            Canonical Contributions
          </h3>
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="pb-2 pr-4">Participant</th>
                <th className="pb-2 pr-4">Contribution</th>
                <th className="pb-2 pr-4">Attempt</th>
                <th className="pb-2 pr-4">Hash</th>
              </tr>
            </thead>
            <tbody>
              {canonical_contributions.map((c) => (
                <tr key={c.contribution_id} className="border-t border-slate-800/60">
                  <td className="py-2 pr-4 text-slate-200">
                    {c.participant_name}
                  </td>
                  <td className="py-2 pr-4 text-slate-400">
                    #{c.contribution_id}
                  </td>
                  <td className="py-2 pr-4 text-slate-400">
                    #{c.attempt_id}
                  </td>
                  <td className="py-2 pr-4">
                    <code className="text-xs text-slate-500">
                      {c.contribution_hash.substring(0, 16)}…
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Final result details */}
      {generated && (
        <div className="mt-4 rounded border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="text-slate-500">Generated:</span>
            <span className="text-emerald-300">YES</span>
            <span className="text-slate-500 ml-4">Verification:</span>
            <span className={verified ? "text-emerald-300" : "text-red-300"}>
              {verified ? "VALID" : "FAILED"}
            </span>
          </div>
          {participant_count != null && (
            <div className="mt-1">
              <span className="text-slate-500">Participant count:</span>{" "}
              {participant_count}
            </div>
          )}
          {final_digest && (
            <div className="mt-1">
              <span className="text-slate-500">Final digest:</span>{" "}
              <code className="text-slate-300">{final_digest.substring(0, 24)}…</code>
            </div>
          )}
          {contribution_digest && (
            <div className="mt-1">
              <span className="text-slate-500">Contribution digest:</span>{" "}
              <code className="text-slate-300">
                {contribution_digest.substring(0, 24)}…
              </code>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
