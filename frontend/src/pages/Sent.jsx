import { useCallback, useEffect, useState } from "react";
import { fetchCsrf, handleError } from "../api/client";
import { deleteForRecipient, fetchMe, fetchSent } from "../api/endpoints";
import { toast } from "../toast";

export default function Sent() {
  const [messages, setMessages] = useState([]);
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // ترقيم الخادم: صفحة واحدة ثم إضافة الأقدم زر "عرض المزيد"
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback((pageNum = 1) => {
    return fetchSent(pageNum)
      .then((res) => {
        const results = (res.data && res.data.results) || [];
        setPage(pageNum);
        setHasNext(Boolean(res.data && res.data.has_next));
        setMessages((prev) => (pageNum === 1 ? results : [...prev, ...results]));
      })
      .catch((err) => setError(handleError(err) || "لا يمكن عرض الرسائل المرسلة."));
  }, []);

  function loadMore() {
    setLoadingMore(true);
    load(page + 1).finally(() => setLoadingMore(false));
  }

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
      toast("تم حذف الرسالة من الطرف الآخر بنجاح.");
      // الرسالة تختفي من قائمتين معًا (soft delete) — حذفها محليًا يحفظ ترقيمك
      setMessages((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      const m = handleError(err);
      setError(m);
      toast(m, "err");
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
      {hasNext && (
        <div className="row load-more-row">
          <button
            type="button"
            className="btn-ghost"
            onClick={loadMore}
            disabled={loadingMore}
          >
            {loadingMore ? "جارٍ التحميل..." : "عرض رسائل أقدم ⬇"}
          </button>
        </div>
      )}
    </section>
  );
}
