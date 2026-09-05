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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    const res = await api.submitContribution(
      ceremonyId,
      attemptId,
      parseInt(participantId, 10),
      data,
    );

    if (res.status === 404 || res.status === 400 || res.status === 422) {
      setError(res.body?.detail || "Submission failed.");
      return;
    }

    setResult(res.body);
    onSubmitted?.();
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
        </div>
      )}
    </div>
  );
}
