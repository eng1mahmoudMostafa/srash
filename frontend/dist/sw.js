/* Service Worker — Web Push for صراحة.
   Shows the "new message" notification (never the content: the server only
   sends a generic title/body) and focuses/opens /inbox on click. */
self.addEventListener("install", () => {
  // فعّل النسخة الجديدة فورًا حتى لا يبقى عامل قديم عالق عند المستخدمين.
  try {
    self.skipWaiting();
  } catch {
    /* تجاهل */
  }
});

self.addEventListener("activate", (event) => {
  // سيطر على الصفحات المفتوحة فورًا حتى تصلها رسائل postMessage.
  event.waitUntil(
    (async () => {
      try {
        await self.clients.claim();
      } catch {
        /* تجاهل */
      }
    })()
  );
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "صراحة";
  const options = {
    body: data.body || "لديك رسالة مجهولة جديدة 📩",
    // tag فريد لكل رسالة + renotify: رسالتان متتاليتان والموقع مقفول كانت
    // الثانية تستبدل الأولى بصمت (نفس الـ tag وrenotify:false) فتضيع.
    tag: data.tag || `srash-new-message-${Date.now()}`,
    renotify: true,
    dir: "rtl",
    lang: "ar",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    vibrate: [200, 100, 200],
    data: { url: data.url || "/inbox" },
  };
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      // لو في تاب مرئي فعلًا: الصفحة تشغّل صوت التنبيه (notify.wav) فنكتم
      // إشعار النظام لئلا يُسمع صوتان. أما لو كل التابات مخفية/مصغّرة —
      // وحالة الموبايل الشائعة: الشاشة مطفية — فصوت الصفحة لن يُسمع أصلًا
      // (المتصفح يمنع صوت التاب المخفي)، لذا صوت النظام هو التنبيه الوحيد
      // ويجب ألا نكتمه.
      let anyVisible = false;
      for (const c of windows) {
        try {
          if (c.visibilityState === "visible") anyVisible = true;
        } catch {
          /* بعض المتصفحات لا تدعم visibilityState على الـ client */
        }
      }
      // بثّ للتابات المفتوحة (إن وجدت) لتشغيل الصوت والتحديث الفوري —
      // مغلّف بـ try: مراسلة عميل غير خاضع للسيطرة قد ترمي استثناءً،
      // ويجب ألا يمنع ذلك ظهور إشعار النظام أبدًا.
      for (const c of windows) {
        try {
          c.postMessage({ type: "srash:new-message" });
        } catch {
          /* تجاهل */
        }
      }
      // Fallback للمتصفحات التي لا تدعم visibilityState: لو لم نستطع
      // التأكد من وجود تاب مرئي، لا نكتم — صوت زائد أفضل من صمت تام.
      if (anyVisible) options.silent = true;
      await self.registration.showNotification(title, options);
    })()
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/inbox";
  event.waitUntil(
    (async () => {
      const all = await clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      for (const client of all) {
        if ("focus" in client) return client.focus();
      }
      return clients.openWindow(target);
    })()
  );
});
