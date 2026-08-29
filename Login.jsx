import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { login } from "../api/endpoints";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      await login(username, password);
      navigate("/inbox");
    } catch (err) {
      setError(handleError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h1>تسجيل الدخول</h1>
      <form onSubmit={onSubmit} className="form">
        <label>
          اسم المستخدم
          <input value={username} onChange={(e) => setUsername(e.target.value)} required />
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
        {error && <p className="error">{error}</p>}
        <button disabled={busy} type="submit">
          {busy ? "جارٍ الدخول..." : "دخول"}
        </button>
      </form>
    </section>
  );
}