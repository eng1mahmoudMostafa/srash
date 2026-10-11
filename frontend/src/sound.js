// صوت تنبيه الرسائل الجديدة — "دينج" قصير لطيف.
// يُشغَّل عند وصول إشعار جديد (جرس التطبيق أو رسالة Push والموقع مفتوح).

let lastPlayedAt = 0;
// نفس الحدث قد يصل من مسارين (Push + تحديث الجرس الدوري) — امنع التكرار
// خلال 3 ثوانٍ حتى لا يُسمع صوتان لرسالة واحدة.
const DEDUPE_MS = 3000;

export function playNotifySound() {
  const now = Date.now();
  if (now - lastPlayedAt < DEDUPE_MS) return;
  lastPlayedAt = now;
  try {
    const audio = new Audio("/notify.wav");
    audio.volume = 0.7;
    audio.play().catch(() => {
      /* المتصفح يمنع الصوت قبل أول تفاعل — unlockSound يتولى الباقي */
    });
  } catch {
    /* لا شيء: الصوت إضافة ولا يجوز أن يكسر أي شاشة */
  }
}

// المتصفحات تمنع تشغيل الصوت قبل أول لمسة/نقرة من المستخدم — نفتح القفل
// عند أول تفاعل على الصفحة (idempotent: يُستدعى كل نقرة لكن بلا تكلفة).
export function unlockSound() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
      const ctx = new Ctx();
      if (ctx.state === "suspended") ctx.resume();
    }
  } catch {
    /* تجاهل */
  }
}