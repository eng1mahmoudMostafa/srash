import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { toast } from "../toast";
import {
  changePassword,
  fetchMe,
  fetchMyProfile,
  fetchSettings,
  fetchSubscriptionStatus,
  logout,
  patchMyProfile,
  patchSettings,
  removeAvatar,
  sendVerificationEmail,
  subscribe,
  toggleAnonymous,
  updateEmail,
  uploadAvatar,
} from "../api/endpoints";

export default function SettingsPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);

  const [me, setMe] = useState(null);
  const [profile, setProfile] = useState(null);
  const [sub, setSub] = useState(null);
  const [settings, setSettings] = useState(null);

  const [emailInput, setEmailInput] = useState("");
  const [transferNote, setTransferNote] = useState("");
  const [emailError, setEmailError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // تغيير كلمة المرور (قسم مستقل بمشغله الخاص حتى لا يعطّل غيره)
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [pwError, setPwError] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const load = useCallback(() => {
    fetchMe()
      .then((res) => {
        setMe(res.data);
        setEmailInput(res.data.email || "");
      })
      .catch(() => {});
    fetchMyProfile()
      .then((res) => setProfile(res.data))
      .catch(() => {});
    fetchSubscriptionStatus()
      .then((res) => setSub(res.data))
      .catch(() => {});
    fetchSettings()
      .then((res) => setSettings(res.data))
      .catch((err) => setError(handleError(err) || "لا يمكن تحميل الإعدادات."));
  }, []);

  useEffect(() => load(), [load]);

  // نسخ رقم التحويل (فودافون كاش) إلى الحافظة
  const copyNumber = () => {
    const num = "01142634188";
    const done = () => toast("تم نسخ رقم التحويل ✅");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(num).then(done).catch(() => {});
    } else {
      const ta = document.createElement("textarea");
      ta.value = num;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      done();
    }
  };

  // فتح تطبيق إنستاباي على هاتف المستخدم (deep link)
  const openInstaPay = () => {
    window.location.href = "instapay://";
    window.setTimeout(() => {
      toast(
        "لو لم يفتح تطبيق إنستاباي تلقائيًا، افتحه يدويًا وحوّل على الرقم الموضح."
      );
    }, 1500);
  };

  async function run(action, okMessage) {
    setBusy(true);
    setError("");
    try {
      await fetchCsrf();
      await action();
      if (okMessage) {
        toast(okMessage);
      }
      load();
    } catch (err) {
      const m = handleError(err);
      setError(m);
      toast(m, "err");
    } finally {
      setBusy(false);
    }
  }

  const saveProfile = (e) => {
    e.preventDefault();
    run(
      () =>
        patchMyProfile({
          display_name: profile.display_name,
          bio: profile.bio,
        }),
      "تم حفظ الملف الشخصي."
    );
  };

  const onAvatarPick = (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) run(() => uploadAvatar(file), "تم تحديث صورة الحساب.");
  };

  // تغيير كلمة المرور وهو مسجّل الدخول (يحتاج كلمة المرور الحالية)
  async function changePw(e) {
    e.preventDefault();
    setPwError("");
    if (newPw !== newPw2) {
      setPwError("كلمتا المرور الجديدتان غير متطابقتين.");
      return;
    }
    setPwBusy(true);
    try {
      await fetchCsrf();
      await changePassword(oldPw, newPw);
      setOldPw("");
      setNewPw("");
      setNewPw2("");
      toast("🔑 تم تغيير كلمة المرور بنجاح.");
    } catch (err) {
      const m = handleError(err);
      setPwError(m);
      toast(m, "err");
    } finally {
      setPwBusy(false);
    }
  }

  const saveEmail = (e) => {
    e.preventDefault();
    const value = emailInput.trim();
    if (!value) {
      setEmailError("اكتب بريدك الإلكتروني أولًا.");
      return;
    }
    setBusy(true);
    setEmailError("");
    fetchCsrf()
      .then(() => updateEmail(value))
      .then(() => {
        toast("✅ تم ربط بريدك الإلكتروني بحسابك بنجاح.");
        load();
      })
      .catch((err) => {
        const m = handleError(err);
        toast(m, "err");
        setEmailError(
          /مستخدم بالفعل/.test(m)
            ? m +
                " — إن كان حسابًا قديمًا أنشأته سابقًا بنفس البريد فسجّل الدخول به، أو استخدم بريدًا آخر."
            : m
        );
      })
      .finally(() => setBusy(false));
  };

  const verifyEmail = () =>
    run(() => sendVerificationEmail(), "تم إرسال رابط التوثيق إلى بريدك.");

  const doSubscribe = () =>
    run(() => subscribe(transferNote.trim()), "تم إنشاء طلب الاشتراك.");

  const savePrivacy = (e) => {
    e.preventDefault();
    run(async () => {
      const res = await patchSettings({
        allow_anonymous: settings.allow_anonymous,
        gap_minutes: Number(settings.gap_minutes) || 0,
        notify_new_message: settings.notify_new_message,
      });
      // مزامنة فورية: checkbox الخصوصية = زر استقبال الرسائل
      const val = res?.data?.allow_anonymous;
      if (typeof val === "boolean") {
        setMe((prev) => (prev ? { ...prev, accept_anonymous: val } : prev));
      }
    }, "تم حفظ إعدادات الخصوصية.");
  };

  const toggle = () =>
    run(async () => {
      const res = await toggleAnonymous();
      // حدّث حالة الشاشة فوراً من رد السيرفر حتى يرى المستخدم التغيير
      const val = res?.data?.accept_anonymous;
      if (typeof val === "boolean") {
        setMe((prev) => (prev ? { ...prev, accept_anonymous: val } : prev));
        // مزامنة checkbox الخصوصية فوراً حتى لا يتعارض مع الحالة
        setSettings((prev) =>
          prev ? { ...prev, allow_anonymous: val } : prev
        );
        toast(
          val ? "تم تفعيل استقبال الرسائل ✅" : "تم إيقاف استقبال الرسائل مؤقتاً ⏸️"
        );
      }
    }, null);

  async function signOut() {
    try {
      await fetchCsrf();
      await logout();
    } finally {
      navigate("/");
    }
  }

  if (!settings) {
    return (
      <section className="card">
        {error ? <p className="error">{error}</p> : "جارٍ التحميل..."}
      </section>
    );
  }

  const activeSub =
    sub && sub.results ? sub.results.find((s) => s.status === "active") : null;

  return (
    <section>
      {error && <p className="error">{error}</p>}

      {/* ---- مؤشر جاري التعديل ---- */}
      {busy && (
        <div className="busy-banner" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true"></span>
          <span>انتظر جارٍ التعديل... وصلِّ على النبي ﷺ</span>
        </div>
      )}

      {/* ---- الملف الشخصي ---- */}
      <section className="card">
        <h1>الملف الشخصي</h1>
        {profile && (
          <>
            <div className="profile-head">
              {profile.avatar_url ? (
                <img className="avatar avatar-lg" src={profile.avatar_url} alt="صورة الحساب" />
              ) : (
                <div className="avatar avatar-lg avatar-fallback">
                  {(profile.display_name || profile.username || "؟").charAt(0)}
                </div>
              )}
              <div>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={onAvatarPick}
                  disabled={busy}
                />
                {profile.avatar_url && (
                  <button
                    type="button"
                    className="danger"
                    disabled={busy}
                    onClick={() =>
                      run(() => removeAvatar(), "تمت إزالة صورة الحساب.")
                    }
                  >
                    🗑 إزالة الصورة
                  </button>
                )}
                <p className="hint">JPG / PNG / WEBP — تُقص وتُصغَّر تلقائيًا إلى 512×512.</p>
              </div>
            </div>
            <form onSubmit={saveProfile} className="form">
              <label>
                الاسم الحقيقي (يظهر في صفحتك العامة)
                <input
                  value={profile.display_name}
                  onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
                  maxLength={60}
                  required
                />
                <span className="hint">حروف عربية أو إنجليزية فقط — الاسم الأول والأخير، بدون أرقام أو رموز.</span>
              </label>
              <label>
                نبذة قصيرة
                <textarea
                  value={profile.bio}
                  onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
                  rows={3}
                  maxLength={500}
                />
              </label>
              <button disabled={busy} type="submit">حفظ الملف الشخصي</button>
            </form>
          </>
        )}
      </section>
      {/* ---- البريد الإلكتروني ---- */}
      <section className="card">
        <h2 className="section-title">البريد الإلكتروني</h2>
        {me && (
          <p className="hint">
            الحالة:{" "}
            {me.email
              ? me.email_verified
                ? "✔ موثق"
                : "غير موثق بعد"
              : "لا يوجد بريد مسجل"}
          </p>
        )}
        <form onSubmit={saveEmail} className="form">
          <label>
            بريدك الإلكتروني
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="name@example.com"
            />
            <span className="hint">لتصلك إشعارات وصول رسائل جديدة (دون محتواها) ورابط توثيق بريدك.</span>
          </label>
          <div className="row">
            <button disabled={busy} type="submit">حفظ البريد</button>
            <button
              disabled={busy || !me?.email || me?.email_verified}
              type="button"
              onClick={verifyEmail}
            >
              أرسل رابط التوثيق
            </button>
          </div>
          {emailError && (
            <p className="error warn-email" role="alert">{emailError}</p>
          )}
        </form>
      </section>

      {/* ---- تغيير كلمة المرور ---- */}
      <section className="card">
        <h2 className="section-title">🔑 تغيير كلمة المرور</h2>
        <form onSubmit={changePw} className="form">
          <label>
            كلمة المرور الحالية
            <input
              type="password"
              dir="ltr"
              value={oldPw}
              onChange={(e) => setOldPw(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          <label>
            كلمة المرور الجديدة
            <input
              type="password"
              dir="ltr"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          <label>
            تأكيد كلمة المرور الجديدة
            <input
              type="password"
              dir="ltr"
              value={newPw2}
              onChange={(e) => setNewPw2(e.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          {pwError && (
            <p className="error" role="alert">
              {pwError}
            </p>
          )}
          <button disabled={pwBusy} type="submit">
            {pwBusy ? "جارٍ الحفظ..." : "تغيير كلمة المرور"}
          </button>
        </form>
        <p className="hint">
          نسيتها؟ <Link to="/forgot-password">استعدها عبر بريدك</Link> من
          صفحة تسجيل الدخول.
        </p>
      </section>

      {/* ---- الاشتراك الموثق ---- */}
      <section className="card premium-box">
        <h2 className="section-title">⭐ الاشتراك الموثق — 100 جنيه / شهر</h2>
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
            {activeSub?.remaining_days != null && ` (متبقٍ ${activeSub.remaining_days} يوم)`}
          </p>
        ) : (
          <>
            <div className="pay-methods">
              <div className="row">
                <span>فودافون كاش:</span>
                <strong className="pay-number" dir="ltr">01142634188</strong>
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
                زر إنستاباي ينقلك لتطبيق إنستاباي على هاتفك — لو لم يُفتح
                تلقائيًا افتح التطبيق يدويًا وحوّل على نفس الرقم أعلاه.
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
              اشترك الآن — 100 جنيه شهريًا
            </button>
          </>
        )}
      </section>

      {/* ---- الخصوصية ---- */}
      <section className="card">
        <h2 className="section-title">الخصوصية ومكافحة الإساءة</h2>
        <form onSubmit={savePrivacy} className="form">
          <label className="check">
            <input
              type="checkbox"
              checked={settings.allow_anonymous}
              onChange={(e) =>
                setSettings({ ...settings, allow_anonymous: e.target.checked })
              }
            />
            السماح باستقبال الرسائل المجهولة
          </label>
          <label>
            الفجوة الزمنية بين الرسائل من نفس المصدر (بالدقائق)
            <input
              type="number"
              min="0"
              value={settings.gap_minutes}
              onChange={(e) =>
                setSettings({ ...settings, gap_minutes: e.target.value })
              }
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={settings.notify_new_message}
              onChange={(e) =>
                setSettings({ ...settings, notify_new_message: e.target.checked })
              }
            />
            إشعار عند وصول رسالة جديدة (يتطلب بريدًا مسجلًا)
          </label>
          <button disabled={busy} type="submit">حفظ إعدادات الخصوصية</button>
        </form>
        <div className="row">
          <div className="toggle-status">
            <span className="hint">حالة الاستقبال الآن:</span>{" "}
            <strong>
              {me?.accept_anonymous === false
                ? "⏸️ متوقف مؤقتاً"
                : "✅ يعمل ويستقبل الرسائل"}
            </strong>
          </div>
          <button onClick={toggle} type="button" disabled={busy}>
            {me?.accept_anonymous === false
              ? "▶️ تفعيل استقبال الرسائل"
              : "⏸️ إيقاف استقبال الرسائل مؤقتاً"}
          </button>
          <button onClick={signOut} type="button" className="danger">
            تسجيل الخروج
          </button>
        </div>
      </section>
    </section>
  );
}