import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  fetchMe,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "./api/endpoints";
import { playNotifySound, unlockSound } from "./sound";
import { registerServiceWorker } from "./push";

// تحميل كل صفحة عند الحاجة فقط — الحزمة الأولية تصغر والصفحة الرئيسية تظهر أسرع.
const Home = lazy(() => import("./pages/Home"));
const Register = lazy(() => import("./pages/Register"));
const Login = lazy(() => import("./pages/Login"));
const PublicProfile = lazy(() => import("./pages/PublicProfile"));
const Inbox = lazy(() => import("./pages/Inbox"));
const Sent = lazy(() => import("./pages/Sent"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const Subscribe = lazy(() => import("./pages/Subscribe"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RouteFallback() {
  return (
    <section className="card">
      <p className="hint">جارٍ التحميل...</p>
    </section>
  );
}

// شريط انتظار عام يظهر أعلى الشاشة مع أي طلب يستغرق وقتًا في الموقع كله
function GlobalBusy() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let timer = null;
    const onBusy = (e) => {
      if (e.detail) {
        // لا تُظهره إلا إذا استمر الانتظار قليلًا (يمنع الوميض في الطلبات السريعة)
        if (!timer) timer = setTimeout(() => setVisible(true), 350);
      } else {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        setVisible(false);
      }
    };
    window.addEventListener("srash:busy", onBusy);
    return () => {
      window.removeEventListener("srash:busy", onBusy);
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!visible) return null;
  return (
    <div className="global-busy" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true"></span>
      <span>انتظر جاري التحميل... وصلِّ على النبي ﷺ</span>
    </div>
  );
}

// إشعارات ثابتة أعلى الشاشة (نجاح/خطأ) — تظهر فورًا مهما كان موضع التمرير،
// فلا يحتاج المستخدم على الموبايل أن يسحب الصفحة للأعلى لرؤيتها.
function Toasts() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    let seq = 0;
    const onToast = (e) => {
      const detail = e.detail || {};
      if (!detail.text) return;
      const id = ++seq;
      setItems((prev) => [
        ...prev,
        {
          id,
          text: String(detail.text),
          type: detail.type === "err" ? "err" : "ok",
        },
      ]);
      window.setTimeout(() => {
        setItems((prev) => prev.filter((t) => t.id !== id));
      }, 4500);
    };
    window.addEventListener("srash:toast", onToast);
    return () => window.removeEventListener("srash:toast", onToast);
  }, []);

  if (!items.length) return null;
  return (
    <div className="toasts" role="status" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast ${t.type === "err" ? "toast-err" : ""}`}>
          {t.text}
        </div>
      ))}
    </div>
  );
}

// جرس الإشعارات داخل التطبيق: عدّاد غير مقروءات + قائمة منسدلة.
// يعرض نوع الإشعار فقط (وصلك رسالة جديدة) دون أي محتوى — الخصوصية أولًا.
function NotificationsBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const btnRef = useRef(null);
  const [ddPos, setDdPos] = useState(null);
  const lastUnread = useRef(null);

  // موضع القائمة يُحسب من الزر نفسه ثم يُقصّ داخل حدود الشاشة — فلا تخرج
  // عن حافة الهاتف أبدًا مهما كان موضع الزر أو طول رابط الحساب.
  function placeDropdown() {
    const el = btnRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth || document.documentElement.clientWidth;
    const width = Math.min(300, Math.max(220, vw - 24));
    let left = rect.left + rect.width / 2 - width / 2;
    left = Math.max(12, Math.min(left, vw - width - 12));
    setDdPos({ left, top: rect.bottom + 8, width });
  }

  function toggleOpen() {
    setOpen((v) => {
      if (!v) placeDropdown();
      return !v;
    });
  }

  const load = useCallback(() => {
    fetchNotifications()
      .then((res) => {
        const count = Number(res.data?.unread) || 0;
        // صوت عند وصول إشعار جديد (أول تحميل يضبط العدّاد بصمت)
        if (lastUnread.current !== null && count > lastUnread.current) {
          playNotifySound();
        }
        lastUnread.current = count;
        setItems(res.data?.results || []);
        setUnread(count);
      })
      .catch(() => {
        /* صامت: الجرس إضافة تجميلية ولا يجب أن يزعج المستخدم بأخطاء */
      });
  }, []);

  useEffect(() => {
    load();
    const onBellPush = () => load();
    window.addEventListener("srash:refresh-bell", onBellPush);
    const timer = window.setInterval(load, 15000); // تحديث دوري كل دقيقة
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("srash:refresh-bell", onBellPush);
    };
  }, [load]);

  // إغلاق القائمة عند النقر خارجها
  useEffect(() => {
    if (!open) return undefined;
    const onDocClick = (e) => {
      if (!e.target || !e.target.closest || !e.target.closest(".bell-wrap")) {
        setOpen(false);
      }
    };
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  // القائمة مثبّتة بالنسبة للشاشة (position: fixed) فأغلقها عند التمرير
  // أو تغيير المقاس حتى لا تطفو بعيدًا عن زرها.
  useEffect(() => {
    if (!open) return undefined;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, { passive: true });
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  async function onItemClick(n) {
    setOpen(false);
    try {
      if (!n.is_read) await markNotificationRead(n.id);
    } catch {
      /* فشل التعليم لا يمنع فتح صندوق الرسائل */
    }
    navigate("/inbox");
  }

  async function markAll() {
    try {
      await markAllNotificationsRead();
      setUnread(0);
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {
      /* تجاهل */
    }
  }

  return (
    <div className="bell-wrap">
      <button
        type="button"
        ref={btnRef}
        className="bell-btn"
        onClick={toggleOpen}
        title="الإشعارات"
        aria-label={unread ? `الإشعارات (${unread} غير مقروءة)` : "الإشعارات"}
        aria-expanded={open}
        aria-haspopup="true"
      >
        🔔
        {unread > 0 && (
          <span className="bell-badge">{unread > 99 ? "99+" : unread}</span>
        )}
      </button>
      {open && (
        <div
          className="bell-dd"
          role="menu"
          style={
            ddPos
              ? {
                  position: "fixed",
                  left: `${ddPos.left}px`,
                  top: `${ddPos.top}px`,
                  width: `${ddPos.width}px`,
                }
              : undefined
          }
        >
          <div className="bell-dd-head">
            <strong>الإشعارات</strong>
            <button
              type="button"
              className="linklike"
              onClick={markAll}
              disabled={!unread}
            >
              تحديد الكل كمقروء
            </button>
          </div>
          {items.length === 0 ? (
            <p className="hint bell-empty">لا توجد إشعارات بعد.</p>
          ) : (
            <ul className="bell-list">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={`bell-item ${n.is_read ? "" : "bell-unread"}`}
                    onClick={() => onItemClick(n)}
                    role="menuitem"
                  >
                    💬 وصلك رسالة جديدة
                    <span className="hint">
                      {" "}
                      · {new Date(n.created_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function Nav() {
  const [theme, setTheme] = useState(() => {
    try {
      return (
        document.documentElement.getAttribute("data-theme") ||
        localStorage.getItem("srash-theme") ||
        "light"
      );
    } catch {
      return "light";
    }
  });
  const location = useLocation();
  const [me, setMe] = useState(null);
  const [copied, setCopied] = useState(false);

  // جلب بيانات المستخدم الحالي لعرض رابط صفحته في كل الصفحات.
  // إعادة الجلب مع كل تغيّر مسار: بعد الدخول أو التسجيل أو الخروج تتحدّث
  // الواجهة (الجرس + رابط صفحتي) فورًا بدون تحديث الصفحة يدويًا.
  useEffect(() => {
    let alive = true;
    fetchMe()
      .then((res) => alive && setMe(res.data))
      .catch((err) => {
        // نُخرج المستخدم من الحساب فقط عند رفض مصادقة حقيقي (401/403 JSON).
        // صفحة HTML أو عطل شبكة أو 5xx مؤقت لا يعني أن الجلسة انتهت —
        // هذا بالضبط ما كان يُظهر "سجّل دخولك" للمستخدم صاحب الحساب.
        if (alive && (!err || err.isAuthError)) setMe(null);
      });
    return () => {
      alive = false;
    };
  }, [location.pathname]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("srash-theme", next);
    } catch {
      /* localStorage غير متاح — يكفي هذه الجلسة */
    }
  }

  function copyLink() {
    if (!me?.shareable_url) return;
    const done = () => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(me.shareable_url).then(done).catch(() => {});
    } else {
      const ta = document.createElement("textarea");
      ta.value = me.shareable_url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      done();
    }
  }

  return (
    <nav className="nav">
      <NavLink to="/" end>الصفحة الرئيسية</NavLink>
      <NavLink to="/inbox">الرسائل</NavLink>
      <NavLink to="/sent">المرسلة</NavLink>
      <NavLink to="/settings">الإعدادات</NavLink>
      <div className="nav-auth">
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          title={theme === "dark" ? "التحويل للوضع النهاري" : "التحويل للوضع الليلي"}
          aria-label="تبديل الثيم"
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
        {me && <NotificationsBell />}
        {me ? (
          <div className="nav-mylink">
            <NavLink
              to={`/u/${me.username}`}
              className="nav-mylink-url"
              dir="ltr"
              title="افتح صفحتي"
            >
              {me.shareable_url || `srashapp.pythonanywhere.com/u/${me.username}`}
            </NavLink>
            <button
              type="button"
              className="nav-copy"
              onClick={copyLink}
              title={copied ? "تم النسخ" : "نسخ رابط صفحتك"}
              aria-label="نسخ رابط صفحتك"
            >
              {copied ? "✓ تم النسخ" : "📋 نسخ الرابط"}
            </button>
          </div>
        ) : (
          <>
            <NavLink to="/login">دخول</NavLink>
            <NavLink to="/register">حساب جديد</NavLink>
          </>
        )}
      </div>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <p>صراحة بلا كذب — استقبل رسائلك المجهولة بصراحة وأمان.</p>
      <p>
        جميع الحقوق محفوظة © {new Date().getFullYear()} —{" "}
        <strong className="designer-name">تصميم محمود مصطفي محمود</strong>
      </p>
    </footer>
  );
}

export default function App() {
  // صوت التنبيه: (1) رسالة Push والموقع مفتوح تصل من عامل الخدمة عبر
  // postMessage؛ (2) قفل الصوت عند أول تفاعل من المستخدم (سياسة المتصفحات
  // تمنع التشغيل التلقائي قبل أي نقرة).
  useEffect(() => {
    unlockSound();
    const onFirstInteraction = () => unlockSound();
    window.addEventListener("pointerdown", onFirstInteraction);
    window.addEventListener("keydown", onFirstInteraction);

    const onSwMessage = (e) => {
      if (e.data && e.data.type === "srash:new-message") {
        playNotifySound();
        // الرسالة وصلت فعلًا: حدّث الجرس والقائمة فورًا بدل انتظار دورة
        // الـ polling — هذا هو إصلاح "لازم أحدث الصفحة عشان الرسالة تظهر".
        window.dispatchEvent(new CustomEvent("srash:refresh-bell"));
        window.dispatchEvent(new CustomEvent("srash:refresh-inbox"));
      }
    };
    if ("serviceWorker" in navigator) {
      // سجّل عامل الخدمة عند بدء التطبيق — بدونه لا يصل أي postMessage
      // ولا يُشغَّل أي صوت عبر مسار الـ Push.
      registerServiceWorker().catch(() => {});
      navigator.serviceWorker.addEventListener("message", onSwMessage);
    }
    return () => {
      window.removeEventListener("pointerdown", onFirstInteraction);
      window.removeEventListener("keydown", onFirstInteraction);
      if ("serviceWorker" in navigator) {
        navigator.serviceWorker.removeEventListener("message", onSwMessage);
      }
    };
  }, []);

  return (
    <div className="app">
      <GlobalBusy />
      <Toasts />
      <Nav />
      <main>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/register" element={<Register />} />
            <Route path="/login" element={<Login />} />
            <Route path="/u/:username" element={<PublicProfile />} />
            <Route path="/inbox" element={<Inbox />} />
            <Route path="/sent" element={<Sent />} />
            <Route path="/settings" element={<SettingsPage />} />
      <Route path="/subscribe" element={<Subscribe />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}