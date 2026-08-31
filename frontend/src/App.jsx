import { useEffect, useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import Home from "./pages/Home";
import Register from "./pages/Register";
import Login from "./pages/Login";
import PublicProfile from "./pages/PublicProfile";
import Inbox from "./pages/Inbox";
import Sent from "./pages/Sent";
import SettingsPage from "./pages/Settings";

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

function Nav() {
  const [theme, setTheme] = useState(() => {
    try {
      return (
        document.documentElement.getAttribute("data-theme") ||
        localStorage.getItem("srash-theme") ||
        "dark"
      );
    } catch {
      return "dark";
    }
  });

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
        <NavLink to="/login">دخول</NavLink>
        <NavLink to="/register">حساب جديد</NavLink>
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
        <strong>البشمهندس محمود مصطفى</strong>
      </p>
    </footer>
  );
}

export default function App() {
  return (
    <div className="app">
      <GlobalBusy />
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<Login />} />
          <Route path="/u/:username" element={<PublicProfile />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/sent" element={<Sent />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}