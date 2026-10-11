import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { recoveryConfirm, recoveryStart } from "../api/endpoints";
import { toast } from "../toast";

// الاستعادة بسؤال الأمان المسجَّل عند إنشاء الحساب — بدون أي بريد إلكتروني.
export default function ForgotPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [username, setUsername] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function askQuestion(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      const res = await recoveryStart(username.trim());
      if (!res.data?.recoverable) {
        throw new Error(
          "لا يوجد حساب بهذا الاسم يمكن استعادته — تأكد من اسم المستخدم."
        );
      }
      setQuestion(res.data.security_question);
      setStep(2);
    } catch (err) {
      const m = err?.response ? handleError(err) : err.message;
      setError(m);
      toast(m, "err");
    } finally {
      setBusy(false);
    }
  }

  async function confirmAnswer(e) {
    e.preventDefault();
    setError("");
    if (password !== password2) {
      setError("كلمتا المرور غير متطابقتين.");
      return;
    }
    setBusy(true);
    try {
      await fetchCsrf();
      await recoveryConfirm(username.trim(), answer.trim(), password);
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

  if (step === 2) {
    return (
      <section className="card">
        <h1>الإجابة على سؤالك</h1>
        <p className="hint">
          سؤالك المسجَّل: <strong>{question}</strong>
        </p>
        <form onSubmit={confirmAnswer} className="form">
          <label>
            إجابتك
            <input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              required
              autoComplete="off"
            />
            <span className="hint">اكتبها كما سجلتها عند إنشاء الحساب.</span>
          </label>
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
              value={password2}
              onChange={(e) => setPassword2(e.target.value)}
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
          <button
            type="button"
            className="linklike"
            onClick={() => {
              setStep(1);
              setError("");
            }}
          >
            رجوع
          </button>{" "}
          — <Link to="/login">تسجيل الدخول</Link>
        </p>
      </section>
    );
  }

  return (
    <section className="card">
      <h1>استعادة كلمة المرور</h1>
      <p className="hint">
        اكتب اسم المستخدم الخاص بك — سنعرض لك سؤال الأمان الذي اخترته عند إنشاء
        الحساب. لا نستخدم أي بريد إلكتروني.
      </p>
      <form onSubmit={askQuestion} className="form">
        <label>
          اسم المستخدم
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ البحث..." : "متابعة"}
        </button>
      </form>
      <p className="hint">
        <Link to="/login">تذكّرتها؟ العودة إلى تسجيل الدخول</Link>
      </p>
    </section>
  );
}