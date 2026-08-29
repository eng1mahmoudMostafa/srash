import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import {
  deleteMessage,
  fetchInbox,
  fetchMe,
  readMessage,
  reportMessage,
} from "../api/endpoints";

export default function Inbox() {
  const [messages, setMessages] = useState([]);
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    fetchInbox()
      .then((res) => setMessages(res.data.results))
      .catch((err) => setError(handleError(err) || "لا يمكن عرض الرسائل."));
  }, []);

  useEffect(() => {
    fetchMe()
      .then((res) => setMe(res.data))
      .catch(() => setMe(null));
    load();
  }, [load]);

  async function markRead(id) {
    try {
      await readMessage(id);
      await load();
    } catch (err) {
      setError(handleError(err));
    }
  }

  async function remove(id) {
    try {
      await fetchCsrf();
      await deleteMessage(id);
      await load();
    } catch (err) {
      setError(handleError(err));
    }
  }

  return (
    <section>
      <h1 className="profile-title">
        {me ? `رسائلك يا ${me.username}` : "الرسائل"}
        {me?.is_verified && <span className="badge-verified">✔ موثق</span>}
      </h1>
      {me && (
        <p className="hint">
          رابط صفحتك: <a href={me.shareable_url}>{me.shareable_url}</a>
        </p>
      )}
      {error && <p className="error">{error}</p>}
      {messages.length === 0 ? (
        <div className="card">
          <p className="hint">لا توجد رسائل.</p>
          <p className="hint">
            شارك رابطك ليبدأ الآخرون بإرسال رسائل مجهولة إليك.
          </p>
        </div>
      ) : (
        messages.map((m) => (
          <article key={m.id} className={`card ${m.is_read ? "" : "unread"}`}>
            {m.sender_name || m.sender_username ? (
              <p className="sender-line">
                ✍️ المرسل: <strong>{m.sender_name || "بدون اسم"}</strong>
                {m.sender_username && (
                  <span className="hint"> @{m.sender_username}</span>
                )}
              </p>
            ) : m.has_sender_name || m.has_sender_username ? (
              <p className="sender-line locked">
                🔒 المرسل معروف عند التفعيل —{" "}
                <Link to="/settings">فعّل الاشتراك الموثق لكشف اسمه واسم مستخدمه</Link>
              </p>
            ) : (
              <p className="sender-line">🎭 مرسل مجهول</p>
            )}
            <p className="msg-body">{m.message}</p>
            <p className="hint">{new Date(m.created_at).toLocaleString()}</p>
            <div className="row">
              {!m.is_read && <button onClick={() => markRead(m.id)}>قرأتها</button>}
              <button onClick={() => remove(m.id)}>حذف</button>
              <button
                onClick={() =>
                  reportMessage(m.id, "spam")
                    .then(() => alert("تم الإبلاغ"))
                    .catch((e) => setError(handleError(e)))
                }
              >
                إبلاغ
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
          </article>
        ))
      )}
    </section>
  );
}