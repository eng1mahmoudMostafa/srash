import { useCallback, useEffect, useState } from "react";
import { fetchCsrf, handleError } from "../api/client";
import { deleteForRecipient, fetchMe, fetchSent } from "../api/endpoints";

export default function Sent() {
  const [messages, setMessages] = useState([]);
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    fetchSent()
      .then((res) => setMessages(res.data.results))
      .catch((err) => setError(handleError(err) || "لا يمكن عرض الرسائل المرسلة."));
  }, []);

  useEffect(() => {
    fetchMe()
      .then((res) => setMe(res.data))
      .catch(() => setMe(null));
    load();
  }, [load]);

  async function removeFromRecipient(id) {
    if (!window.confirm("سيتم حذف هذه الرسالة من صندوق المستخدم الآخر أيضًا. متأكد؟")) {
      return;
    }
    try {
      await fetchCsrf();
      await deleteForRecipient(id);
      setNotice("تم حذف الرسالة من الطرف الآخر بنجاح.");
      await load();
    } catch (err) {
      setError(handleError(err));
    }
  }

  return (
    <section>
      <h1 className="profile-title">
        الرسائل التي أرسلتها
        {me?.is_verified && <span className="badge-verified">✔ موثق</span>}
      </h1>
      {error && <p className="error">{error}</p>}
      {notice && <p className="success-box">{notice}</p>}
      {messages.length === 0 ? (
        <div className="card">
          <p className="hint">لم ترسل أي رسائل بعد.</p>
          <p className="hint">
            ابحث عن صديق بكتابة اسمه في الصفحة الرئيسية وأرسل أول رسالة صراحة!
          </p>
        </div>
      ) : (
        messages.map((m) => (
          <article key={m.id} className="card">
            <p className="sender-line">
              📨 إلى: <strong>{m.recipient_username}</strong>
              {m.is_read ? (
                <span className="hint"> — تمت القراءة ✔</span>
              ) : (
                <span className="hint"> — لم تُقرأ بعد</span>
              )}
            </p>
            <p className="msg-body">{m.message}</p>
            <p className="hint">{new Date(m.created_at).toLocaleString()}</p>

            {/* ---- رد المستقبِل (يظهر للمرسل فقط) ---- */}
            {m.reply ? (
              <div className="reply-box reply-from-recipient">
                <p className="reply-title">↩️ رد من {m.recipient_username}:</p>
                <p className="msg-body">{m.reply}</p>
                <p className="hint">{m.replied_at ? new Date(m.replied_at).toLocaleString() : ""}</p>
              </div>
            ) : null}

            <div className="row">
              <button onClick={() => removeFromRecipient(m.id)}>
                🗑 حذف من الطرف الآخر
              </button>
              {m.has_image && (
                <button
                  onClick={() =>
                    window.open(`/api/messages/${m.id}/image/`, "_blank")
                  }
                >
                  🖼 فتح الصورة
                </button>
              )}
            </div>
            <p className="hint">
              💡 خيار الحذف من صندوق الطرف الآخر ميزة ضمن الاشتراك الموثق —
              فعّله من الإعدادات إن لم يكن مفعّلًا.
            </p>
          </article>
        ))
      )}
    </section>
  );
}
