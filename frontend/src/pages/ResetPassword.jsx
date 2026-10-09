import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { resetPassword } from "../api/endpoints";
import { toast } from "../toast";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("t") || "";
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("كلمتا المرور غير متطابقتين.");
      return;
    }
    setBusy(true);
    try {
      await fetchCsrf();
      await resetPassword(token, password);
      toast("✅ تم تعيين كلمة المرور الجديدة — سجّل دخولك بها الآن.");
      navigate("/login");
    } catch (err) {
      const m = handleError(err);
      setError(m);
      toast(m, "err");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <section className="card">
        <h1>إعادة تعيين كلمة المرور</h1>
        <p className="error">
          رابط إعادة التعيين غير صالح — لم يصل معه رمز صالح. اطلب رابطًا جديدًا.
        </p>
        <p className="hint">
          <Link to="/forgot-password">طلب رابط استعادة جديد</Link>
        </p>
      </section>
    );
  }

  return (
    <section className="card">
      <h1>تعيين كلمة مرور جديدة</h1>
      <p className="hint">الرابط صالح لمدة ساعة واحدة فقط.</p>
      <form onSubmit={onSubmit} className="form">
        <label>
          كلمة المرور الجديدة
          <input
            type="password"
            dir="ltr"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
        </label>
        <label>
          تأكيد كلمة المرور الجديدة
          <input
            type="password"
            dir="ltr"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            autoComplete="new-password"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ الحفظ..." : "تعيين كلمة المرور"}
        </button>
      </form>
      <p className="hint">
        <Link to="/forgot-password">إعادة إرسال رابط جديد</Link>
      </p>
    </section>
  );
}