import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStats } from "../api/endpoints";

export default function Home() {
  const [username, setUsername] = useState("");
  const [userCount, setUserCount] = useState(null);

  useEffect(() => {
    fetchStats()
      .then((res) => setUserCount(res.data.user_count))
      .catch(() => setUserCount(null));
  }, []);

  return (
    <section className="card">
      <h1>صراحة بلا كذب</h1>
      <p className="lead">
        استقبل رسائل مجهولة بأمان وشارك رابطك — بلا كذب، بلا هوية.
      </p>
      {userCount !== null && (
        <p className="badge">👥 {userCount.toLocaleString("ar-EG")} مستخدم على المنصة</p>
      )}
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          if (username) window.location.href = `/u/${username}`;
        }}
      >
        <input
          placeholder="أدخل اسم المستخدم"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <button type="submit">فتح صفحتي</button>
      </form>
      <div className="row">
        <Link to="/register">أنشئ حسابك مجانًا</Link>
      </div>
    </section>
  );
}