import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { register } from "../api/endpoints";

export default function Register() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      await register(username, password, email.trim(), fullName.trim());
      navigate("/inbox");
    } catch (err) {
      setError(handleError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h1>إنشاء حساب</h1>
      <form onSubmit={onSubmit} className="form">
        <label>
          الاسم الحقيقي (إجباري)
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            maxLength={60}
            required
            placeholder="مثال: محمود مصطفى"
          />
          <span className="hint">
            الاسم الأول والأخير — حروف عربية أو إنجليزية فقط، بدون أرقام أو
            رموز. يظهر في صفحتك العامة ومع رسائلك للمعتمدين.
          </span>
        </label>
        <label>
          اسم المستخدم
          <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          <span className="hint">رابطك العام سيصبح: /u/{username || "اسم-المستخدم"}</span>
        </label>
        <label>
          كلمة المرور
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <label>
          البريد الإلكتروني
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@example.com"
          />
          <span className="hint">
            لتصلك إشعارات وصول رسائل جديدة (دون محتواها) ورابط توثيق بريدك.
          </span>
        </label>
        {!email.trim() && (
          <p className="error warn-email" role="alert">
            ⚠️ لن تعرف أنك تلقيت رسالة حتى تربط بريدك الإلكتروني الخاص بحسابك —
            اتركه الآن وستتمكن من ربطه لاحقًا من الإعدادات.
          </p>
        )}
        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ الإنشاء..." : "إنشاء الحساب"}
        </button>
      </form>
    </section>
  );
}