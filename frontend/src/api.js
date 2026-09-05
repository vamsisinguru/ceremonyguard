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
};
