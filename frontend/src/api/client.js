import axios from "axios";

// Backend base URL, configurable via .env / .env.development (VITE_API_URL).
const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({ baseURL });

// Token is kept in memory (a module variable), not localStorage, so it
// disappears on a full page reload/tab close rather than sitting in
// browser storage indefinitely.
let token = null;
export function setToken(t) {
  token = t;
}
export function getToken() {
  return token;
}

api.interceptors.request.use((config) => {
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Let the auth context register a handler for "the session just ended"
// (expired/invalid token) without api/client.js needing to know about React.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && onUnauthorized) onUnauthorized();
    return Promise.reject(err);
  }
);

// Pulls FastAPI's error shape into a plain string for display.
export function apiErrorMessage(err, fallback = "Something went wrong. Please try again.") {
  const detail = err?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(" ");
  }
  return fallback;
}
