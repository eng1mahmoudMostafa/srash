import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { register } from "../api/endpoints";
import { toast } from "../toast";

// نفس الأسئلة الجاهزة في الخادم — ضغطة واحدة بدل الكتابة.
const PRESET_QUESTIONS = [
  "ما اسم مدرستك الابتدائية؟",
  "ما اسم أول حيوان أليف امتلكته؟",
  "ما اسم المدينة التي وُلدت فيها؟",
  "ما اسم أفضل صديق لك في الطفولة؟",
  "ما هو اسم والدك؟",
  "ما اسم شارع الحي الذي نشأت فيه؟",
];

export default function Register() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [securityQuestion, setSecurityQuestion] = useState(PRESET_QUESTIONS[0]);
  const [securityAnswer, setSecurityAnswer] = useState("");
  const [showName, setShowName] = useState(false);
  const [fullName, setFullName] = useState("");
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
            minLength={8}
          />
          <span className="hint">8 أحرف على الأقل.</span>
        </label>
        <label>
          سؤال استعادة كلمة المرور
          <select
            value={securityQuestion}
            onChange={(e) => setSecurityQuestion(e.target.value)}
            required
          >
            {PRESET_QUESTIONS.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
          <span className="hint">
            لو نسيت كلمة المرور سيُطلب هذا السؤال — اختَر سؤالًا تتذكر إجابته.
          </span>
        </label>
        <label>
          الإجابة
          <input
            value={securityAnswer}
            onChange={(e) => setSecurityAnswer(e.target.value)}
            maxLength={100}
            required
            placeholder="مثال: النور"
          />
          <span className="hint">
            تُحفَظ مُشفَّرة (لا يراها أحد) — الاختلاف البسيط في الكتابة العربية لا يمنع
            الاستعادة.
          </span>
        </label>

        {!showName ? (
          <button type="button" className="link-btn" onClick={() => setShowName(true)}>
            + إضافة اسم للعرض (اختياري)
          </button>
        ) : (
          <label>
            الاسم المعروض (اختياري)
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              maxLength={60}
              placeholder="مثال: محمود مصطفى"
            />
            <span className="hint">
              حروف عربية أو إنجليزية فقط، بدون أرقام أو رموز. لو تركته فارغًا سيظهر اسم
              المستخدم.
            </span>
          </label>
        )}

        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ الإنشاء..." : "إنشاء الحساب"}
        </button>
      </form>
    </section>
  );
}
