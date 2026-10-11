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
let wavMissing = false;

function fallbackBeep() {
  // بديل أخير لو ملف notify.wav غير موجود/تالف: نغمة مذبذب قصيرة عبر
  // WebAudio حتى لا يبقى المستخدم في صمت تام أبدًا.
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.5, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.45);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch {
    /* تجاهل */
  }
}

function getAudio() {
  if (wavMissing) return null;
  if (!sharedAudio) {
    sharedAudio = new Audio("/notify.wav");
    sharedAudio.preload = "auto";
    sharedAudio.volume = 0.7;
    // لو الملف غير موجود/تالف: علّم وانتقل لصوت البديل بدل الصمت.
    sharedAudio.addEventListener(
      "error",
      () => {
        wavMissing = true;
        sharedAudio = null;
      },
      { once: true }
    );
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
    // ملف الصوت غير متاح → صوت بديل فوري حتى لا يبقى صمت تام.
    if (!audio) {
      fallbackBeep();
      return;
    }
    let usedFallback = false;
    const onErr = () => {
      usedFallback = true;
      wavMissing = true;
      sharedAudio = null;
      fallbackBeep();
    };
    audio.addEventListener("error", onErr, { once: true });
    try {
      audio.currentTime = 0;
    } catch {
      /* تجاهل */
    }
    const p = audio.play();
    if (p && typeof p.catch === "function") {
      p.catch(() => {
        // فشل التشغيل (الملف تالف أو المتصفح منع التشغيل): بديل فوري.
        audio.removeEventListener("error", onErr);
        if (!usedFallback) fallbackBeep();
      });
    }
  } catch {
    fallbackBeep();
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