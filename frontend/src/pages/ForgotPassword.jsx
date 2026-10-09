import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { forgotPassword } from "../api/endpoints";
import { toast } from "../toast";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // الاستجابة موحّدة من الخادم (لا تكشف إن كان البريد مسجّلًا أم لا)
  const [sent, setSent] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      await forgotPassword(email.trim());
      setSent(true);
      toast("تم — إن كان البريد مسجّلًا فسيصلك رابط الاستعادة قريبًا.");
    } catch (err) {
      const m = handleError(err);
      setError(m);
      toast(m, "err");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <section className="card">
        <h1>استعادة كلمة المرور</h1>
        <div className="success-box">
          إذا كان <span dir="ltr">{email}</span> مسجّلًا عندنا، فقد أرسلنا إليه
          رابطًا لإعادة تعيين كلمة المرور (صالح لمدة ساعة واحدة فقط). تحقّق من
          بريد الوارد وصندوق المزعجات.
        </div>
        <p className="hint">
          لم يصل الرابط؟ تأكد من كتابة البريد الصحيح ثم{" "}
          <button
            type="button"
            className="linklike"
            onClick={onSubmit}
            disabled={busy}
          >
            أعد الإرسال
          </button>
        </p>
        <p className="hint">
          <Link to="/login">العودة إلى تسجيل الدخول</Link>
        </p>
      </section>
    );
  }

  return (
    <section className="card">
      <h1>نسيت كلمة المرور؟</h1>
      <p className="hint">
        اكتب بريدك المسجّل وسنرسل لك رابطًا آمنًا لتعيين كلمة مرور جديدة.
      </p>
      <form onSubmit={onSubmit} className="form">
        <label>
          البريد الإلكتروني
          <input
            type="email"
            dir="ltr"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            placeholder="name@example.com"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ الإرسال..." : "أرسل رابط الاستعادة"}
        </button>
      </form>
      <p className="hint">
        <Link to="/login">تذكّرتها؟ العودة إلى تسجيل الدخول</Link>
      </p>
    </section>
  );
}