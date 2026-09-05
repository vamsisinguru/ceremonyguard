import { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import StatusBadge from "./StatusBadge.jsx";
import ContributionForm from "./ContributionForm.jsx";
import RecoverySection from "./RecoverySection.jsx";
import FinalVerificationSection from "./FinalVerificationSection.jsx";

export default function App() {
  const [health, setHealth] = useState(null);
  const [ceremonies, setCeremonies] = useState([]);
  const [selectedCeremony, setSelectedCeremony] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [attempts, setAttempts] = useState([]);
  const [contributions, setContributions] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [recoveryStatus, setRecoveryStatus] = useState(null);
  const [verification, setVerification] = useState(null);
  const [newCeremonyName, setNewCeremonyName] = useState("");
  const [newParticipantName, setNewParticipantName] = useState("");

  // ---- Health check ----
  const checkHealth = useCallback(async () => {
    const res = await api.health();
    if (res.status === 200) setHealth(res.body);
  }, []);

  // ---- Load ceremonies ----
  const loadCeremonies = useCallback(async () => {
    const res = await api.listCeremonies();
    if (res.status === 200) setCeremonies(res.body);
  }, []);

  useEffect(() => {
    checkHealth();
    loadCeremonies();
  }, [checkHealth, loadCeremonies]);

  // ---- Load ceremony detail ----
  const loadCeremonyDetail = useCallback(async (id) => {
    const [pRes, aRes, cRes, auditRes, recRes, verRes] = await Promise.all([
      api.listParticipants(id),
      api.listAttempts(id),
      api.listContributions(id),
      api.listAuditEvents(id),
      api.getRecoveryStatus(id),
      api.getVerification(id),
    ]);
    setParticipants(pRes.status === 200 ? pRes.body : []);
    setAttempts(aRes.status === 200 ? aRes.body : []);
    setContributions(cRes.status === 200 ? cRes.body : []);
    setAuditEvents(auditRes.status === 200 ? auditRes.body : []);
    setRecoveryStatus(recRes.status === 200 ? recRes.body : null);
    setVerification(verRes.status === 200 ? verRes.body : null);
  }, []);

  useEffect(() => {
    if (selectedCeremony) {
      loadCeremonyDetail(selectedCeremony.id);
    } else {
      setParticipants([]);
      setAttempts([]);
      setContributions([]);
      setAuditEvents([]);
      setRecoveryStatus(null);
      setVerification(null);
    }
  }, [selectedCeremony, loadCeremonyDetail]);

  const handleCreateCeremony = async (e) => {
    e.preventDefault();
    if (!newCeremonyName.trim()) return;
    const res = await api.createCeremony(newCeremonyName.trim());
    if (res.status === 201) {
      setNewCeremonyName("");
      await loadCeremonies();
      setSelectedCeremony(res.body);
    }
  };

  const handleCreateParticipant = async (e) => {
    e.preventDefault();
    if (!newParticipantName.trim() || !selectedCeremony) return;
    const res = await api.createParticipant(
      selectedCeremony.id,
      newParticipantName.trim(),
    );
    if (res.status === 201) {
      setNewParticipantName("");
      await loadCeremonyDetail(selectedCeremony.id);
    }
  };

  const handleCreateAttempt = async () => {
    if (!selectedCeremony) return;
    const res = await api.createAttempt(selectedCeremony.id);
    if (res.status === 201) {
      await loadCeremonyDetail(selectedCeremony.id);
    }
  };

  const refresh = () => {
    if (selectedCeremony) loadCeremonyDetail(selectedCeremony.id);
  };

  const latestAttempt = attempts[attempts.length - 1] || null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 px-8 py-6">
        <h1 className="text-3xl font-bold tracking-tight">CeremonyGuard</h1>
        <p className="mt-1 text-slate-400">
          Multi-Party Ceremony Consistency System
        </p>
        <div className="mt-3 flex items-center gap-2 text-sm">
          {health ? (
            <>
              <span className="inline-flex items-center rounded-full border border-emerald-500/40 bg-emerald-500/20 px-2.5 py-0.5 text-xs font-medium text-emerald-300">
                Backend connected
              </span>
              <span className="text-slate-500">
                {health.app} · {health.environment}
              </span>
            </>
          ) : (
            <span className="text-slate-500">Backend connection pending</span>
          )}
        </div>
      </header>

      <main className="flex-1 px-8 py-8 space-y-6">
        {/* Ceremony selector / creator */}
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-200">Ceremonies</h2>
            <form onSubmit={handleCreateCeremony} className="flex gap-2">
              <input
                type="text"
                value={newCeremonyName}
                onChange={(e) => setNewCeremonyName(e.target.value)}
                placeholder="New ceremony name"
                className="rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100"
              />
              <button
                type="submit"
                className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Create
              </button>
            </form>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {ceremonies.length === 0 && (
              <p className="text-sm text-slate-500">No ceremonies yet.</p>
            )}
            {ceremonies.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedCeremony(c)}
                className={`rounded border px-3 py-1.5 text-sm ${
                  selectedCeremony?.id === c.id
                    ? "border-indigo-500 bg-indigo-600/20 text-indigo-200"
                    : "border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-600"
                }`}
              >
                {c.name} #{c.id}
              </button>
            ))}
          </div>
        </section>

        {selectedCeremony && (
          <>
            {/* Participants & Attempts */}
            <div className="grid gap-6 md:grid-cols-2">
              <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                <h2 className="text-base font-semibold text-slate-200">
                  Participants
                </h2>
                <form
                  onSubmit={handleCreateParticipant}
                  className="mt-3 flex gap-2"
                >
                  <input
                    type="text"
                    value={newParticipantName}
                    onChange={(e) => setNewParticipantName(e.target.value)}
                    placeholder="Participant name"
                    className="flex-1 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm text-slate-100"
                  />
                  <button
                    type="submit"
                    className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
                  >
                    Add
                  </button>
                </form>
                <ul className="mt-3 space-y-1">
                  {participants.length === 0 && (
                    <li className="text-sm text-slate-500">
                      No participants yet.
                    </li>
                  )}
                  {participants.map((p) => (
                    <li
                      key={p.id}
                      className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/40 px-3 py-1.5 text-sm"
                    >
                      <span className="text-slate-200">{p.name}</span>
                      <span className="text-xs text-slate-500">
                        id={p.id}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-slate-200">
                    Attempts
                  </h2>
                  <button
                    onClick={handleCreateAttempt}
                    className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
                  >
                    New Attempt
                  </button>
                </div>
                <ul className="mt-3 space-y-1">
                  {attempts.length === 0 && (
                    <li className="text-sm text-slate-500">
                      No attempts yet.
                    </li>
                  )}
                  {attempts.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/40 px-3 py-1.5 text-sm"
                    >
                      <span className="text-slate-200">
                        Attempt #{a.attempt_number}
                      </span>
                      <span className="text-xs text-slate-500">
                        id={a.id}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            {/* Contribution form */}
            {latestAttempt && participants.length > 0 && (
              <ContributionForm
                ceremonyId={selectedCeremony.id}
                attemptId={latestAttempt.id}
                participants={participants}
                onSubmitted={refresh}
              />
            )}

            {/* Contributions list */}
            <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
              <h2 className="text-base font-semibold text-slate-200">
                Contributions
              </h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500">
                      <th className="pb-2 pr-4">ID</th>
                      <th className="pb-2 pr-4">Participant</th>
                      <th className="pb-2 pr-4">Attempt</th>
                      <th className="pb-2 pr-4">Hash</th>
                      <th className="pb-2 pr-4">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contributions.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="py-3 text-slate-500"
                        >
                          No contributions yet.
                        </td>
                      </tr>
                    )}
                    {contributions.map((c) => {
                      const p = participants.find(
                        (pp) => pp.id === c.participant_id,
                      );
                      return (
                        <tr
                          key={c.id}
                          className="border-t border-slate-800/60"
                        >
                          <td className="py-2 pr-4 text-slate-400">
                            #{c.id}
                          </td>
                          <td className="py-2 pr-4 text-slate-200">
                            {p?.name || `#${c.participant_id}`}
                          </td>
                          <td className="py-2 pr-4 text-slate-400">
                            #{c.attempt_id}
                          </td>
                          <td className="py-2 pr-4">
                            <code className="text-xs text-slate-500">
                              {c.contribution_hash.substring(0, 16)}…
                            </code>
                          </td>
                          <td className="py-2 pr-4">
                            <StatusBadge status={c.status} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Phase 4 — Recovery */}
            <RecoverySection
              ceremonyId={selectedCeremony.id}
              recoveryStatus={recoveryStatus}
              onUpdated={refresh}
            />

            {/* Phase 4 — Final Verification */}
            <FinalVerificationSection
              ceremonyId={selectedCeremony.id}
              verification={verification}
              onUpdated={refresh}
            />

            {/* Audit trail */}
            <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
              <h2 className="text-base font-semibold text-slate-200">
                Audit Trail
              </h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500">
                      <th className="pb-2 pr-4">ID</th>
                      <th className="pb-2 pr-4">Participant</th>
                      <th className="pb-2 pr-4">Event</th>
                      <th className="pb-2 pr-4">Message</th>
                      <th className="pb-2 pr-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditEvents.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="py-3 text-slate-500"
                        >
                          No audit events yet.
                        </td>
                      </tr>
                    )}
                    {auditEvents.map((e) => {
                      const p = participants.find(
                        (pp) => pp.id === e.participant_id,
                      );
                      return (
                        <tr
                          key={e.id}
                          className="border-t border-slate-800/60"
                        >
                          <td className="py-2 pr-4 text-slate-400">
                            #{e.id}
                          </td>
                          <td className="py-2 pr-4 text-slate-300">
                            {p?.name || (e.participant_id ? `#${e.participant_id}` : "—")}
                          </td>
                          <td className="py-2 pr-4">
                            <code className="text-xs text-indigo-300">
                              {e.event_type}
                            </code>
                          </td>
                          <td className="py-2 pr-4 text-slate-400">
                            {e.message}
                          </td>
                          <td className="py-2 pr-4 text-xs text-slate-500">
                            {e.created_at}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </main>

      <footer className="border-t border-slate-800 px-8 py-4 text-sm text-slate-500">
        Phase 4 &middot; Recovery &amp; Final Verification
      </footer>
    </div>
  );
}
