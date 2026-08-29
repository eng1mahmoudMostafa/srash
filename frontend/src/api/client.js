import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL || "/api";

export const api = axios.create({
  baseURL,
  withCredentials: true, // send the session & csrf cookies
});

// Django validates CSRF for state-changing requests; the token is exposed in
// the (non-HttpOnly) csrfcookie so we read it and send it as a header.
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (method !== "get" && method !== "head" && method !== "options") {
    const token = getCsrfToken();
    if (token) config.headers["X-CSRFToken"] = token;
  }
  return config;
});

// If a mutation ever fails with a stale CSRF token (e.g. right after
// login/register rotates the token), refresh it once and retry — this
// removes the whole class of "CSRF Failed" errors in the UI.
api.interceptors.response.use(undefined, async (error) => {
  const status = error.response?.status;
  const detail = String(error.response?.data?.detail || "");
  const config = error.config;
  if (
    status === 403 &&
    /csrf/i.test(detail) &&
    config &&
    !config._csrfRetried
  ) {
    config._csrfRetried = true;
    try {
      await api.get("/auth/csrf/");
      const token = getCsrfToken();
      if (token) config.headers["X-CSRFToken"] = token;
      return api.request(config);
    } catch {
      /* fall through to the original error */
    }
  }
  throw error;
});

export async function fetchCsrf() {
  // GET /api/auth/csrf/ sets the CSRF cookie (used before first mutation).
  await api.get("/auth/csrf/");
}

export function handleError(error) {
  if (error.response) {
    const data = error.response.data;
    const msg = flattenError(data);
    if (msg) {
      if (/csrf/i.test(msg)) {
        return "انتهت صلاحية رمز الأمان — حاول مرة أخرى أو أعد تحميل الصفحة.";
      }
      return msg;
    }
  }
  return "حدث خطأ غير متوقع.";
}

// DRF returns nested field errors like {"email": ["رسالة"]} or
// {"non_field_errors": [...]}. Flatten them into one readable line.
function flattenError(data) {
  if (data == null) return null;
  if (typeof data === "string") return data;
  if (Array.isArray(data)) {
    return data.map((x) => flattenError(x) || "").join(" ").trim() || null;
  }
  if (typeof data === "object") {
    if (typeof data.detail === "string") return data.detail;
    const parts = [];
    for (const value of Object.values(data)) {
      const m = flattenError(value);
      if (m) parts.push(m);
    }
    if (parts.length) return parts.join(" ");
  }
  return null;
}