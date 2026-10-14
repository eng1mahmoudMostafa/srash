import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { fetchSubscriptionStatus, subscribe } from "../api/endpoints";
import { toast } from "../toast";

const PAY_NUMBER = "01142634188";

export default function Subscribe() {
  const [sub, setSub] = useState(null);
  const [transferNote, setTransferNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchSubscriptionStatus()
      .then((res) => setSub(res.data))
      .catch((err) => setError(handleError(err) || "لا يمكن تحميل حالة الاشتراك."));
  }, []);

  useEffect(() => load(), [load]);

  const copyNumber = () => {
    const done = () => toast("تم نسخ رقم التحويل ✅");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(PAY_NUMBER).then(done).catch(() => {});
    } else {
      const ta = document.createElement("textarea");
      ta.value = PAY_NUMBER;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      done();
    }
  };

  const openInstaPay = () => {
    window.location.href = "instapay://";
    window.setTimeout(() => {
      toast(
        "لو لم يفتح تطبيق إنستاباي تلقائيًا، افتحه يدويًا وحوّل على الرقم الموضح."
      );
    }, 1500);
  };

  async function doSubscribe() {
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      await subscribe(transferNote.trim());
      toast("تم إنشاء طلب الاشتراك ✅");
      setTransferNote("");
      load();
    } catch (err) {
      const m = handleError(err);
      setError(m);
      toast(m, "err");
    } finally {
      setBusy(false);
    }
  }

  const price = sub?.price_egp ?? 50;
  const activeSub =
    sub && sub.results ? sub.results.find((s) => s.status === "active") : null;

  return (
    <section>
      {error && <p className="error">{error}</p>}

      {busy && (
        <div className="busy-banner" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true"></span>
          <span>انتظر جارٍ الإرسال... وصلِّ على النبي ﷺ</span>
        </div>
      )}

      <section className="card premium-box">
        <h2 className="section-title">
          ⭐ الاشتراك الموثق — {price} جنيه / شهر
        </h2>
        <ul>
          <li>✔ شارة «موثق» على صفحتك العامة وصندوق رسائلك.</li>
          <li>🔒 كشف اسم المرسل واسم مستخدمه في المنصة مع كل رسالة.</li>
          <li>🗑 حذف أي رسالة أرسلتها من صندوق الطرف الآخر.</li>
          <li>💚 دعم استمرار المنصة وتطويرها.</li>
        </ul>
        {sub?.slots && (
          <p className="hint">
            🎟 العدد المتاح اليوم: {sub.slots.day_remaining} من{" "}
            {sub.slots.day_limit} — هذا الشهر: {sub.slots.month_remaining} من{" "}
            {sub.slots.month_limit}
          </p>
        )}
        <p className="hint">
          ⏳ يمكنك إرسال طلب اشتراك مرة واحدة كل 12 ساعة — تأكد من تحويل المبلغ
          وكتابة رقم العملية قبل الإرسال.
        </p>

        {sub?.is_verified || activeSub ? (
          <p className="success-box">
            اشتراكك نشط ✅
            {activeSub?.remaining_days != null &&
              ` (متبقٍ ${activeSub.remaining_days} يوم)`}
          </p>
        ) : (
          <>
            <div className="pay-methods">
              <div className="row">
                <span>فودافون كاش:</span>
                <strong className="pay-number" dir="ltr">
                  {PAY_NUMBER}
                </strong>
                <button type="button" onClick={copyNumber}>
                  📋 نسخ الرقم
                </button>
              </div>
              <div className="row">
                <button type="button" onClick={openInstaPay}>
                  💳 الدفع بإنستاباي — افتح التطبيق
                </button>
              </div>
              <p className="hint">
                زر إنستاباي ينقلك لتطبيق إنستاباي على هاتفك — لو لم يُفتح تلقائيًا
                افتح التطبيق يدويًا وحوّل على نفس الرقم أعلاه.
              </p>
            </div>
            {sub?.payment_info && <p className="hint">{sub.payment_info}</p>}
            <label>
              رقم عملية التحويل
              <input
                value={transferNote}
                onChange={(e) => setTransferNote(e.target.value)}
                maxLength={120}
                placeholder="مثال: 987654321"
              />
              <span className="hint">
                اكتب هنا رقم العملية الذي يظهر لك بعد إتمام التحويل ليتحقق منه
                المشرف.
              </span>
            </label>
            <button disabled={busy} type="button" onClick={doSubscribe}>
              اشترك الآن — {price} جنيه شهريًا
            </button>
          </>
        )}
      </section>

      <p className="hint" style={{ marginTop: 12 }}>
        <Link to="/settings">← الرجوع إلى الإعدادات</Link>
      </p>
    </section>
  );
}
