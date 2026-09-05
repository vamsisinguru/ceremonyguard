const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  return { status: res.status, body };
}

export const api = {
  // Health
  health: () => request("/health"),

  // Ceremonies
  listCeremonies: () => request("/ceremonies"),
  createCeremony: (name) =>
    request("/ceremonies", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  getCeremony: (id) => request(`/ceremonies/${id}`),
  updateCeremonyStatus: (id, status) =>
    request(`/ceremonies/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  // Participants
  listParticipants: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/participants`),
  createParticipant: (ceremonyId, name) =>
    request(`/ceremonies/${ceremonyId}/participants`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  // Attempts
  listAttempts: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/attempts`),
  createAttempt: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/attempts`, { method: "POST" }),

  // Contributions
  listContributions: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/contributions`),
  submitContribution: (ceremonyId, attemptId, participantId, data) =>
    request(
      `/ceremonies/${ceremonyId}/attempts/${attemptId}/contributions`,
      {
        method: "POST",
        body: JSON.stringify({
          participant_id: participantId,
          contribution_data: data,
        }),
      },
    ),

  // Audit
  listAuditEvents: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/audit`),

  // Phase 4 — Recovery
  getRecoveryStatus: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/recovery/status`),
  startRecovery: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/recovery/start`, { method: "POST" }),
  resumeParticipant: (ceremonyId, participantId, data) =>
    request(`/ceremonies/${ceremonyId}/recovery/resume`, {
      method: "POST",
      body: JSON.stringify({
        participant_id: participantId,
        contribution_data: data,
      }),
    }),

  // Phase 4 — Final Verification
  getVerification: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/verification`),
  finalizeCeremony: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/finalize`, { method: "POST" }),
  verifyCeremony: (ceremonyId) =>
    request(`/ceremonies/${ceremonyId}/verify`, { method: "POST" }),
};
