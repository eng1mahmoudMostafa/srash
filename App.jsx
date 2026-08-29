import { Routes, Route, NavLink } from "react-router-dom";
import Home from "./pages/Home";
import Register from "./pages/Register";
import Login from "./pages/Login";
import PublicProfile from "./pages/PublicProfile";
import Inbox from "./pages/Inbox";
import SettingsPage from "./pages/Settings";

function Nav() {
  return (
    <nav className="nav">
      <NavLink to="/" end>الصفحة الرئيسية</NavLink>
      <NavLink to="/inbox">الرسائل</NavLink>
      <NavLink to="/settings">الإعدادات والتوثيق</NavLink>
      <div className="nav-auth">
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
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<Login />} />
          <Route path="/u/:username" element={<PublicProfile />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}