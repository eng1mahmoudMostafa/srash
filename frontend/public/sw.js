/* Service Worker — Web Push for صراحة.
   Shows the "new message" notification (never the content: the server only
   sends a generic title/body) and focuses/opens /inbox on click. */
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
    tag: data.tag || "srash-new-message",
    renotify: false,
    dir: "rtl",
    lang: "ar",
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
      for (const c of windows) c.postMessage({ type: "srash:new-message" });
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
