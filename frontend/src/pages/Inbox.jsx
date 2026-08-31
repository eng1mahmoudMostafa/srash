import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import {
  deleteMessage,
  fetchInbox,
  fetchMe,
  readMessage,
  replyToMessage,
  reportMessage,
} from "../api/endpoints";

export default function Inbox() {
  const [messages, setMessages] = useState([]);
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");
  const [replyFor, setReplyFor] = useState(null); // id الرسالة الجاري الرد عليها
  const [replyText, setReplyText] = useState("");
  const [replyBusy, setReplyBusy] = useState(false);

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

  async function sendReply(id) {
    const text = replyText.trim();
    if (!text) return;
    setReplyBusy(true);
    try {
      await fetchCsrf();
      await replyToMessage(id, text);
      setReplyFor(null);
      setReplyText("");
      await load();
    } catch (err) {
      setError(handleError(err));
    } finally {
      setReplyBusy(false);
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

            {/* ---- رد المستقبِل ---- */}
            {m.reply ? (
              <div className="reply-box">
                <p className="reply-title">↩️ ردك على هذه الرسالة:</p>
                <p className="msg-body">{m.reply}</p>
                <p className="hint">{m.replied_at ? new Date(m.replied_at).toLocaleString() : ""}</p>
              </div>
            ) : null}

            {replyFor === m.id ? (
              <div className="reply-compose">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="اكتب ردك هنا... (سيصل للمرسل مشفرة — يستطيع قراءتها فقط)"
                  rows={3}
                  maxLength={2000}
                />
                <div className="row">
                  <button onClick={() => sendReply(m.id)} disabled={replyBusy || !replyText.trim()}>
                    {replyBusy ? "جاري الإرسال..." : "إرسال الرد ↩️"}
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      setReplyFor(null);
                      setReplyText("");
                    }}
                  >
                    إلغاء
                  </button>
                </div>
              </div>
            ) : null}

            <div className="row">
              {!m.is_read && <button onClick={() => markRead(m.id)}>قرأتها</button>}
              {!m.reply && (
                <button onClick={() => setReplyFor(replyFor === m.id ? null : m.id)}>
                  ↩️ رد
                </button>
              )}
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