import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import {
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
  const [emailNotice, setEmailNotice] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

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

  async function run(action, okMessage) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fetchCsrf();
      await action();
      if (okMessage) setNotice(okMessage);
      load();
    } catch (err) {
      setError(handleError(err));
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

  const saveEmail = (e) => {
    e.preventDefault();
    const value = emailInput.trim();
    if (!value) {
      setEmailError("اكتب بريدك الإلكتروني أولًا.");
      setEmailNotice("");
      return;
    }
    setBusy(true);
    setEmailError("");
    setEmailNotice("");
    fetchCsrf()
      .then(() => updateEmail(value))
      .then(() => {
        setEmailNotice("✅ تم ربط بريدك الإلكتروني بحسابك بنجاح.");
        load();
      })
      .catch((err) => {
        const m = handleError(err);
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
    run(
      () =>
        patchSettings({
          allow_anonymous: settings.allow_anonymous,
          gap_minutes: Number(settings.gap_minutes) || 0,
          notify_new_message: settings.notify_new_message,
        }),
      "تم حفظ إعدادات الخصوصية."
    );
  };

  const toggle = () => run(() => toggleAnonymous(), null);

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
      {notice && <p className="success-box">{notice}</p>}

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
          {emailNotice && <p className="success-box">{emailNotice}</p>}
        </form>
      </section>

      {/* ---- الاشتراك الموثق ---- */}
      <section className="card premium-box">
        <h2 className="section-title">⭐ الاشتراك الموثق — 100 جنيه / شهر</h2>
        <ul>
          <li>✔ شارة «موثق» على صفحتك العامة وصندوق رسائلك.</li>
          <li>🔒 كشف اسم المرسل واسم مستخدمه في المنصة مع كل رسالة.</li>
          <li>💚 دعم استمرار المنصة وتطويرها.</li>
        </ul>
        {sub?.is_verified || activeSub ? (
          <p className="success-box">
            اشتراكك نشط ✅
            {activeSub?.remaining_days != null && ` (متبقٍ ${activeSub.remaining_days} يوم)`}
          </p>
        ) : (
          <>
            {sub?.payment_info && <p className="hint">{sub.payment_info}</p>}
            <label>
              رقم عملية التحويل / ملاحظة (اختياري)
              <input
                value={transferNote}
                onChange={(e) => setTransferNote(e.target.value)}
                maxLength={120}
              />
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
          <button onClick={toggle} type="button" disabled={busy}>
            إيقاف/استئناف استقبال الرسائل
          </button>
          <button onClick={signOut} type="button" className="danger">
            تسجيل الخروج
          </button>
        </div>
      </section>
    </section>
  );
}