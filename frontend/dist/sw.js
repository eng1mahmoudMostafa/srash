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
      // لو في تاب مفتوح: الصفحة تشغّل صوت التنبيه (notify.wav) فنكتم إشعار
      // النظام لئلا يُسمع صوتان. ولو الموقع مقفول، صوت النظام هو التنبيه.
      if (windows.length > 0) options.silent = true;
      for (const c of windows) c.postMessage({ type: "srash:new-message" });
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
