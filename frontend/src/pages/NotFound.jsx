import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="card not-found">
      <p className="notfound-code">404</p>
      <h1>الصفحة غير موجودة</h1>
      <p className="hint">
        الرابط الذي فتحته غير صحيح، أو أن الصفحة حُذفت أو تم نقلها.
      </p>
      <div className="row">
        <Link to="/">🏠 الصفحة الرئيسية</Link>
        <Link to="/inbox">💬 صندوق الرسائل</Link>
      </div>
    </section>
  );
}