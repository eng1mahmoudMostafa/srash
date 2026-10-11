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
function isHtmlPayload(error) {
  const data = error.response?.data;
  if (typeof data === "string" && /^\s*<(!doctype|html)/i.test(data)) return true;
  const headers = error.response?.headers || {};
  const ctype = String(headers["content-type"] || headers["Content-Type"] || "");
  return ctype.includes("text/html") && typeof data === "string";
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

api.interceptors.response.use(undefined, async (error) => {
  // وسم نوع الخطأ حتى لا تعامل الأعطال العابرة (صفحة HTML من الخادم،
  // انقطاع شبكة، 5xx أثناء إعادة التشغيل) نفس معاملة "انتهت الجلسة".
  error.isHtmlPage = isHtmlPayload(error);
  const status = error.response?.status;
  const detail = String(error.response?.data?.detail || "");
  // رفض مصادقة حقيقي فقط: 401 أو 403 برسالة "غير مُسجّل" من JSON.
  error.isAuthError =
    status === 401 ||
    (status === 403 &&
      /not authenticated|authentication credentials were not provided/i.test(detail));

  const config = error.config;
  const method = (config?.method || "get").toLowerCase();
  const safeMethod = method === "get" || method === "head";
  // الخادم قد يرد بصفحة HTML (DisallowedHost / 502 أثناء Reload على
  // PythonAnywhere / خطأ 500) بدل JSON — نعيد المحاولة مرة واحدة للطلبات
  // الآمنة بدل عرض خطأ أحمر إجباري فورًا.
  const transient =
    !error.response ||
    error.isHtmlPage ||
    status === 500 ||
    status === 502 ||
    status === 503 ||
    status === 504;
  if (safeMethod && transient && config && !config._transientRetried) {
    config._transientRetried = true;
    await delay(700);
    return api.request(config);
  }
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

// ---- مؤشر الانتظار العام ----
// يتتبع عدد الطلبات الجارية الآن ويبث حدثًا للواجهة لتُظهر شريط "جاري التحميل"
let pending = 0;
function notifyBusy() {
  window.dispatchEvent(new CustomEvent("srash:busy", { detail: pending > 0 }));
}

api.interceptors.request.use((config) => {
  pending += 1;
  notifyBusy();
  return config;
});

api.interceptors.response.use(
  (response) => {
    pending = Math.max(0, pending - 1);
    notifyBusy();
    return response;
  },
  (error) => {
    pending = Math.max(0, pending - 1);
    notifyBusy();
    throw error;
  }
);

export async function fetchCsrf() {
  // GET /api/auth/csrf/ sets the CSRF cookie (used before first mutation).
  await api.get("/auth/csrf/");
}

export function handleError(error) {
  if (error.response) {
    const data = error.response.data;
    const msg = flattenError(data);
    if (msg) {
      // The server/proxy may answer with an HTML error page (e.g. Django's
      // 404/500 page when an endpoint doesn't exist yet). Never dump raw
      // HTML into the UI — show a readable message instead. The client
      // already retried once automatically, so don't ask for a hard reload.
      if (/^\s*<(!doctype|html)/i.test(msg)) {
        return "تعذّر إتمام الطلب مؤقتًا — تحقق من اتصالك بالإنترنت وحاول مرة أخرى بعد لحظات.";
      }
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