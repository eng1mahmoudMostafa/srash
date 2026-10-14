import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { toast } from "../toast";
import {
  changePassword,
  fetchMe,
  fetchMyProfile,
  fetchSettings,
  logout,
  patchMyProfile,
  patchSettings,
  removeAvatar,
  toggleAnonymous,
  uploadAvatar,
} from "../api/endpoints";
import { deviceSubscribed, disablePush, enablePush, pushSupported } from "../push";

export default function SettingsPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);

  const [me, setMe] = useState(null);
  const [profile, setProfile] = useState(null);
  const [settings, setSettings] = useState(null);

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // إشعارات فورية (Web Push) على هذا الجهاز — بديل البريد الإلكتروني
  const [pushOn, setPushOn] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  // تغيير كلمة المرور (قسم مستقل بمشغله الخاص حتى لا يعطّل غيره)
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [pwError, setPwError] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const load = useCallback(() => {
    fetchMe()
      .then((res) => setMe(res.data))
      .catch(() => {});
    fetchMyProfile()
      .then((res) => setProfile(res.data))
      .catch(() => {});
    fetchSettings()
      .then((res) => setSettings(res.data))
      .catch((err) => setError(handleError(err) || "لا يمكن تحميل الإعدادات."));
  }, []);

  useEffect(() => load(), [load]);

  // حالة اشتراك هذا الجهاز في الإشعارات الفورية (بديل البريد الإلكتروني)
  useEffect(() => {
    deviceSubscribed()
      .then((on) => setPushOn(Boolean(on)))
      .catch(() => {});
  }, []);

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

  // تفعيل/إيقاف الإشعارات الفورية (Web Push) على هذا الجهاز — بديل البريد
  async function togglePushDevice() {
    setPushBusy(true);
    try {
      if (pushOn) {
        await disablePush();
        setPushOn(false);
        toast("تم إيقاف الإشعارات على هذا الجهاز.");
      } else {
        await enablePush();
        setPushOn(true);
        toast("🔔 تم تفعيل الإشعارات الفورية على هذا الجهاز.");
      }
    } catch (err) {
      const m = err?.response ? handleError(err) : err.message;
      toast(m, "err");
    } finally {
      setPushBusy(false);
    }
  }

  const savePrivacy = (e) => {
    e.preventDefault();
    run(async () => {
      const res = await patchSettings({
        allow_anonymous: settings.allow_anonymous,
        gap_minutes: Number(settings.gap_minutes) || 0,
        push_notifications: settings.push_notifications,
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
      {/* ---- الإشعارات الفورية ---- */}
      <section className="card">
        <h2 className="section-title">🔔 الإشعارات الفورية</h2>
        <p className="hint">
          تنبيه فوري على هذا الجهاز أول ما تصل رسالة مجهولة — يعمل حتى والموقع
          مغلق تمامًا، ودون أي محتوى للرسالة. (بديل البريد الإلكتروني تمامًا.)
        </p>
        {!pushSupported() ? (
          <p className="error">
            متصفحك لا يدعم الإشعارات الفورية — استخدم Chrome أو Firefox على
            الهاتف. يبقى الجرس 🔔 داخل الموقع يعمل في كل الحالات.
          </p>
        ) : (
          <div className="row">
            <button
              type="button"
              disabled={pushBusy}
              onClick={togglePushDevice}
            >
              {pushBusy
                ? "جارٍ التفعيل..."
                : pushOn
                  ? "🔕 إيقاف إشعارات هذا الجهاز"
                  : "🔔 تفعيل الإشعارات على هذا الجهاز"}
            </button>
            <span className="hint">
              {pushOn ? "مفعّلة على هذا الجهاز ✅" : "معطّلة على هذا الجهاز"}
            </span>
          </div>
        )}
        <p className="hint">
          💡 على الموبايل: بعد التفعيل، افتح قائمة المتصفح ⋮ ثم «تثبيت
          التطبيق / إضافة إلى الشاشة الرئيسية» — الإشعارات تصل حينها كنبّهات
          نظام حتى والمتصفح مغلق. يمكنك دائمًا سحب الإذن من إعدادات المتصفح —
          لن يتأثر استلام رسائلك.
        </p>
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
          نسيتها؟ <Link to="/forgot-password">استعدها بسؤال الأمان</Link> من
          صفحة تسجيل الدخول.
        </p>
      </section>

      {/* ---- الاشتراك الموثق (صفحة مستقلة) ---- */}
      <section className="card premium-box">
        <h2 className="section-title">⭐ الاشتراك الموثق</h2>
        <ul>
          <li>✔ شارة «موثق» على صفحتك العامة وصندوق رسائلك.</li>
          <li>🔒 كشف اسم المرسل واسم مستخدمه في المنصة مع كل رسالة.</li>
          <li>🗑 حذف أي رسالة أرسلتها من صندوق الطرف الآخر.</li>
          <li>💚 دعم استمرار المنصة وتطويرها.</li>
        </ul>
        {me?.is_verified && (
          <p className="success-box">حسابك موثق ✅</p>
        )}
        <p>
          <Link className="button-link" to="/subscribe">
            {me?.is_verified ? "إدارة الاشتراك" : "اشترك الآن"} — 50 جنيه / شهر →
          </Link>
        </p>
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
              checked={settings.push_notifications}
              onChange={(e) =>
                setSettings({ ...settings, push_notifications: e.target.checked })
              }
            />
            إشعار فوري عند وصول رسالة جديدة (على أجهزتك المُفعّل عليها الإشعارات)
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