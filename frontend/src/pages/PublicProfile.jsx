import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchCsrf, handleError } from "../api/client";
import { fetchMe, fetchPublicProfile, sendMessage } from "../api/endpoints";
import ShareRow from "../components/ShareRow";

// رسائل جاهزة للبدء السريع — بضغطة واحدة تُملأ رسالة صريحة ولبقة.
const SUGGESTIONS = [
  {
    label: "تحية صراحة 👋",
    text: "السلام عليكم.. كنت حابب أقولك إنك إنسان جميل، وافتكرتك النهاردة فقلت أكتب أول صراحة 💚",
  },
  {
    label: "شكر كبير 🌹",
    text: "بقالي فترة عايز أشكرك على وقوفك معايا في أصعب وقت، حتى ولو معرفتش اللي بيشكرك مين 🤍",
  },
  {
    label: "دعوة طيبة 🤲",
    text: "ربنا يجعلك دايماً في سعادة ويهديك لكل خير.. بجد أنا مبسوط إني بشوفك ناجح ✨",
  },
  {
    label: "سؤال صريح ❓",
    text: "سؤال صراحة بلا كذب: إيه أكتر حاجة ميّزت بيها نفسك في الفترة اللي فاتت؟ 😄",
  },
  {
    label: "رسالة تشجيع 💪",
    text: "عايزك تعرف إن في ناس كتير بتشجعك وبتدعي ليك من غير ما تحس بيها.. كمّل وربنا معاك 🔥",
  },
  {
    label: "أول رسالة 😅",
    text: "دي أول رسالة أكتبها على المنصة دي.. قلت أبدأها بصراحة: أنت إنسان مختلف وبجد 🌟",
  },
];

export default function PublicProfile() {
  const { username } = useParams();
  const [profile, setProfile] = useState(null);
  const [me, setMe] = useState(null);
  const [meLoaded, setMeLoaded] = useState(false);
  const [message, setMessage] = useState("");
  const [senderName, setSenderName] = useState("");
  const [image, setImage] = useState(null);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchPublicProfile(username)
      .then((res) => setProfile(res.data))
      .catch((err) => setError(handleError(err) || "المستخدم غير موجود."));
    fetchMe()
      .then((res) => setMe(res.data))
      .catch(() => setMe(null))
      .finally(() => setMeLoaded(true));
  }, [username]);

  const isLoggedIn = Boolean(me);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await fetchCsrf();
      await sendMessage(username, message, senderName.trim(), image);
      setSent(true);
    } catch (err) {
      setError(handleError(err));
    }
  }

  if (!profile) {
    return (
      <section className="card">
        {error ? <p className="error">{error}</p> : "جارٍ التحميل..."}
      </section>
    );
  }

  return (
    <section className="card">
      <div className="profile-head">
        {profile.avatar_url ? (
          <img className="avatar avatar-lg" src={profile.avatar_url} alt="صورة الحساب" />
        ) : (
          <div className="avatar avatar-lg avatar-fallback">
            {(profile.display_name || profile.username || "؟").charAt(0)}
          </div>
        )}
        <div>
          <h1 className="profile-title">
            {profile.display_name || profile.username}
            {profile.is_verified && (
              <span className="badge-verified" title="حساب موثق بمشتراك مدفوع">
                ✔ موثق
              </span>
            )}
          </h1>
          {profile.bio && <p className="lead">{profile.bio}</p>}
          {profile.last_seen_human && (
            <p className="hint">
              {profile.online ? "🟢 متصل الآن" : `👁 ${profile.last_seen_human}`}
            </p>
          )}
        </div>
      </div>
      {isLoggedIn && me?.username === username && (
        <div className="share-box">
          <p className="hint">
            أنت صاحب هذه الصفحة — شارك رابطك ليصلك المزيد من الرسائل المجهولة:
          </p>
          <ShareRow
            url={window.location.href}
            title={`ابعتلي رسالة صراحة مشفرة 💬 — ${profile.display_name || profile.username}`}
          />
        </div>
      )}
      {!profile.can_receive ? (
        <p className="hint">أوقف هذا المستخدم مؤقتًا استقبال الرسائل المجهولة.</p>
      ) : sent ? (
        <div className="success-box">
          <p>✅ تم إرسال رسالتك بنجاح.</p>
          <button
            onClick={() => {
              setSent(false);
              setMessage("");
              setSenderName("");
              setImage(null);
            }}
          >
            إرسال رسالة أخرى
          </button>
        </div>
      ) : meLoaded && !isLoggedIn ? (
        <div className="card">
          <p className="lead">
            🔐 الإرسال متاح لأصحاب الحسابات فقط — أنشئ حسابك المجاني أولًا.
          </p>
          <p className="hint">
            رسالتك تبقى مجهولة تمامًا للمستلم: لا يظهر اسمك ولا اسم مستخدمك
            إلا لصاحب الصفحة إذا كان مشتركًا موثقًا.
          </p>
          <div className="row">
            <Link to="/register">
              <button type="button">إنشاء حساب</button>
            </Link>
            <Link to="/login">
              <button type="button">تسجيل الدخول</button>
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="form">
          <div className="chips">
            <span className="hint">💡 رسائل جاهزة — اختر واحدة وعدّل عليها:</span>
            <div className="chips-row">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.text}
                  type="button"
                  className="chip"
                  onClick={() =>
                    setMessage(message ? `${message}\n${s.text}` : s.text)
                  }
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <label>
            اكتب رسالتك المجهولة
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={10000}
              rows={6}
              required
            />
            <span className="hint">
              {message.length.toLocaleString("ar-EG")} / 10,000
            </span>
          </label>
          <label>
            اسمك (اختياري تمامًا)
            <input
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              maxLength={60}
              placeholder="اتركه فارغًا للبقاء مجهولًا تمامًا"
            />
            <span className="hint">
              إن كتبت اسمك الحقيقي فلن يظهر إلا لصاحب الصفحة إذا كان مشتركًا
              موثقًا. اسمك اختياري — التسجيل باسم حقيقي (اسمين بحروف فقط).
            </span>
          </label>
          <label>
            إرفاق صورة (اختياري)
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) =>
                setImage(e.target.files ? e.target.files[0] : null)
              }
            />
            <span className="hint">
              تُفتح للمستلم فقط، وتُحذف منها بيانات الموقع (EXIF) تلقائيًا.
            </span>
          </label>
          {error && <p className="error">{error}</p>}
          <button type="submit">إرسال مجهول</button>
          <p className="hint">
            رسالتك تبقى مجهولة للمستلم: لا يظهر اسمك ولا اسم مستخدمك إلا لصاحب
            الصفحة إذا كان مشتركًا موثقًا. لا نحفظ عنوان IP مع الرسالة إطلاقًا.
          </p>
        </form>
      )}
    </section>
  );
}