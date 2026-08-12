async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.detail || body.error || "请求失败，请稍后重试");
    error.status = response.status;
    throw error;
  }
  return body;
}

export const api = {
  me: () => request("/v1/auth/me"),
  login: (username, password) => request("/v1/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  register: (username, password, email) => request("/v1/auth/register", { method: "POST", body: JSON.stringify({ username, password, email }) }),
  logout: () => request("/v1/auth/logout", { method: "POST" }),
  requestPasswordReset: (email) => request("/v1/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email }) }),
  confirmPasswordReset: (token, password) => request("/v1/auth/password-reset/confirm", { method: "POST", body: JSON.stringify({ token, password }) }),
  resendVerification: () => request("/v1/auth/verify-email/resend", { method: "POST" }),
  adminUsers: () => request("/v1/admin/users"),
  updateRoles: (userId, roles) => request(`/v1/admin/users/${userId}/roles`, { method: "PUT", body: JSON.stringify({ roles }) }),
  dashboard: () => request("/v1/workspace/dashboard"),
  evidence: (symbol) => request(`/v1/research/evidence?symbol=${encodeURIComponent(symbol)}`),
  addWatch: (symbol) => request("/v1/workspace/watchlist", { method: "POST", body: JSON.stringify({ symbol }) }),
  removeWatch: (symbol) => request(`/v1/workspace/watchlist/${encodeURIComponent(symbol)}`, { method: "DELETE" }),
  status: () => request("/v1/status"),
};
