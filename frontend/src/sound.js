// صوت تنبيه الرسائل الجديدة — "دينج" قصير لطيف.
// يُشغَّل عند وصول إشعار جديد (جرس التطبيق أو رسالة Push والموقع مفتوح).

let lastPlayedAt = 0;
// نفس الحدث قد يصل من مسارين (Push + تحديث الجرس الدوري) — امنع التكرار
// خلال 3 ثوانٍ حتى لا يُسمع صوتان لرسالة واحدة.
const DEDUPE_MS = 3000;

// عنصر صوت مشترك مُحمَّل مسبقًا: إنشاؤه مرة واحدة عند أول تفاعل يجعل
// التشغيل اللاحق موثوقًا (إنشاء new Audio لحظة وصول الإشعار — والمستخدم
// لم يلمس الصفحة منذ زمن — هو ما كان يجعل المتصفح يرفض التشغيل بصمت).
let sharedAudio = null;

function getAudio() {
  if (!sharedAudio) {
    sharedAudio = new Audio("/notify.wav");
    sharedAudio.preload = "auto";
    sharedAudio.volume = 0.7;
    try {
      sharedAudio.load();
    } catch {
      /* تجاهل */
    }
  }
  return sharedAudio;
}

export function playNotifySound() {
  const now = Date.now();
  if (now - lastPlayedAt < DEDUPE_MS) return;
  lastPlayedAt = now;
  try {
    const audio = getAudio();
    try {
      audio.currentTime = 0;
    } catch {
      /* تجاهل */
    }
    const p = audio.play();
    if (p && typeof p.catch === "function") {
      p.catch(() => {
        /* المتصفح يمنع الصوت قبل أول تفاعل — unlockSound يتولى الباقي */
      });
    }
  } catch {
    /* لا شيء: الصوت إضافة ولا يجوز أن يكسر أي شاشة */
  }
}

// المتصفحات تمنع تشغيل الصوت قبل أول لمسة/نقرة من المستخدم — نفتح القفل
// عند أول تفاعل على الصفحة (idempotent: يُستدعى كل نقرة لكن بلا تكلفة).
// يُحمَّل ملف الصوت هنا أيضًا حتى يكون جاهزًا لحظة وصول أول إشعار.
export function unlockSound() {
  try {
    getAudio();
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
      const ctx = new Ctx();
      if (ctx.state === "suspended") ctx.resume();
    }
  } catch {
    /* تجاهل */
  }
}