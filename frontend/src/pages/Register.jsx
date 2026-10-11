import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { register } from "../api/endpoints";
import { toast } from "../toast";

export default function Register() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [securityQuestion, setSecurityQuestion] = useState("");
  const [securityAnswer, setSecurityAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      await register(
        username,
        password,
        fullName.trim(),
        securityQuestion.trim(),
        securityAnswer.trim()
      );
      toast("✅ تم إنشاء حسابك بنجاح.");
      navigate("/inbox");
    } catch (err) {
      const m = handleError(err);
      setError(m);
      toast(m, "err");
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
          سؤال استعادة كلمة المرور (إجباري)
          <input
            value={securityQuestion}
            onChange={(e) => setSecurityQuestion(e.target.value)}
            maxLength={200}
            required
            placeholder="مثال: ما اسم مدرستي الابتدائية؟"
          />
          <span className="hint">
            لو نسيت كلمة المرور هذا هو السؤال الوحيد الذي سيُطلب لك — اكتب
            سؤالًا واضحًا منتهيًا بعلامة استفهام (لا يقل عن 10 أحرف).
          </span>
        </label>
        <label>
          الإجابة على سؤال الاستعادة (إجباري)
          <input
            value={securityAnswer}
            onChange={(e) => setSecurityAnswer(e.target.value)}
            maxLength={100}
            required
            placeholder="مثال: النور"
          />
          <span className="hint">
            تُحفَظ مُشفَّرة (لا يراها أحد) — اكتبها كما ستتذكرها، فالاختلاف
            البسيط في الكتابة العربية لا يمنع الاستعادة.
          </span>
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ الإنشاء..." : "إنشاء الحساب"}
        </button>
      </form>
    </section>
  );
}