import { useState } from "react";
import StatusBadge from "./StatusBadge.jsx";
import { api } from "./api.js";

export default function RecoverySection({ ceremonyId, recoveryStatus, onUpdated }) {
  const [resumeParticipantId, setResumeParticipantId] = useState("");
  const [resumeData, setResumeData] = useState("");
  const [resumeResult, setResumeResult] = useState(null);
  const [error, setError] = useState(null);

  const handleStartRecovery = async () => {
    setError(null);
    setResumeResult(null);
    const res = await api.startRecovery(ceremonyId);
    if (res.status !== 200) {
      setError(res.body?.detail || "Failed to start recovery.");
      return;
    }
    onUpdated?.();
  };

  const handleResume = async (e) => {
    e.preventDefault();
    setError(null);
    setResumeResult(null);
    if (!resumeParticipantId || !resumeData) return;
    const res = await api.resumeParticipant(
      ceremonyId,
      parseInt(resumeParticipantId, 10),
      resumeData,
    );
    if (res.status === 404 || res.status === 400 || res.status === 422) {
      setError(res.body?.detail || "Resume failed.");
      return;
    }
    setResumeResult(res.body);
    onUpdated?.();
  };

  if (!recoveryStatus) return null;

  const incomplete = recoveryStatus.incomplete_participants || [];
  const complete = recoveryStatus.complete_participants || [];
  const isRecovering = recoveryStatus.ceremony_status === "recovering";

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-200">Recovery</h2>
        <div className="flex items-center gap-2">
          <StatusBadge
            status={
              recoveryStatus.ready
                ? "ready"
                : isRecovering
                  ? "recovering"
                  : "incomplete"
            }
          />
          <span className="text-xs text-slate-500">
            {recoveryStatus.participants_with_contribution}/
            {recoveryStatus.total_participants} participants
          </span>
        </div>
      </div>

      {recoveryStatus.ready ? (
        <p className="mt-3 text-sm text-emerald-300">
          All participants have canonical contributions. Ceremony is ready for
          final verification.
        </p>
      ) : (
        <>
          <p className="mt-3 text-sm text-slate-400">
            {incomplete.length} participant(s) still need to submit a canonical
            contribution.
          </p>
          {!isRecovering && (
            <button
              onClick={handleStartRecovery}
              className="mt-3 rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
            >
              Start Recovery
            </button>
          )}
        </>
      )}

      {/* Incomplete participants */}
      {incomplete.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-medium text-slate-300">
            Incomplete Participants
          </h3>
          <ul className="mt-2 space-y-1">
            {incomplete.map((p) => (
              <li
                key={p.participant_id}
                className="flex items-center justify-between rounded border border-amber-500/30 bg-amber-500/5 px-3 py-1.5 text-sm"
              >
                <span className="text-slate-200">{p.participant_name}</span>
                <StatusBadge status="incomplete" />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Complete participants */}
      {complete.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-medium text-slate-300">
            Complete Participants
          </h3>
          <ul className="mt-2 space-y-1">
            {complete.map((p) => (
              <li
                key={p.participant_id}
                className="flex items-center justify-between rounded border border-emerald-500/30 bg-emerald-500/5 px-3 py-1.5 text-sm"
              >
                <span className="text-slate-200">
                  {p.participant_name}{" "}
                  <span className="text-xs text-slate-500">
                    (Contribution #{p.contribution_id}, Attempt #{p.attempt_id})
                  </span>
                </span>
                <StatusBadge status="accepted" />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Resume form */}
      {isRecovering && incomplete.length > 0 && (
        <form onSubmit={handleResume} className="mt-4 space-y-3 rounded border border-slate-800 bg-slate-950/40 p-4">
          <h3 className="text-sm font-medium text-slate-300">Resume Contribution</h3>
          <div>
            <label className="block text-sm text-slate-400">Participant</label>
            <select
              value={resumeParticipantId}
              onChange={(e) => setResumeParticipantId(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100"
            >
              <option value="">Select participant</option>
              {incomplete.map((p) => (
                <option key={p.participant_id} value={p.participant_id}>
                  {p.participant_name} (id={p.participant_id})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-400">Contribution Data</label>
            <input
              type="text"
              value={resumeData}
              onChange={(e) => setResumeData(e.target.value)}
              placeholder="e.g. recovered-share-data"
              className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100"
            />
          </div>
          <button
            type="submit"
            disabled={!resumeParticipantId || !resumeData}
            className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40"
          >
            Resume
          </button>
        </form>
      )}

      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

      {resumeResult && (
        <div className="mt-3 rounded border border-slate-800 bg-slate-950/50 p-3 text-sm">
          <div className="flex items-center gap-2">
            <StatusBadge status={resumeResult.submission_status} />
            <span className="text-xs text-slate-500">
              HTTP {resumeResult.submission_status === "accepted" ? "201" : resumeResult.submission_status === "duplicate" ? "200" : "409"}
            </span>
          </div>
          <p className="mt-2 text-slate-400">{resumeResult.message}</p>
        </div>
      )}
    </section>
  );
}
