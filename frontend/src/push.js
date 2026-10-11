import { fetchPushKey, subscribePush, unsubscribePush } from "./api/endpoints";

// Web Push helpers — الإشعارات الفورية تحل محل البريد الإلكتروني تمامًا.
// The VAPID public key comes from the backend (/notifications/push/key/)
// so there is zero per-environment frontend configuration.

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function pushSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    window.isSecureContext
  );
}

export async function registerServiceWorker() {
  return navigator.serviceWorker.register("/sw.js", { scope: "/" });
}

// true if THIS device already has an active push subscription.
export async function deviceSubscribed() {
  if (!pushSupported()) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return Boolean(sub);
  } catch {
    return false;
  }
}

// Subscribe this device: SW + permission + push subscription + tell server.
export async function enablePush() {
  if (!pushSupported()) {
    throw new Error("المتصفح لا يدعم الإشعارات الفورية — جرّب متصفحًا آخر.");
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("لم يُسمح بعرض الإشعارات — فعّل الإشعارات من إعدادات المتصفح.");
  }
  const reg = await registerServiceWorker();
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    const keyRes = await fetchPushKey();
    if (!keyRes.data?.enabled || !keyRes.data?.public_key) {
      throw new Error("الإشعارات غير مفعّلة على الخادم حاليًا.");
    }
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyRes.data.public_key),
    });
  }
  // Send the raw subscription shape the serializer expects
  // ({endpoint, keys:{p256dh, auth}}) — getSubscription() serializes to it.
  await subscribePush(sub.toJSON());
  return true;
}

// Unsubscribe this device from both the browser and the server.
export async function disablePush() {
  if (!pushSupported()) return false;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg ? await reg.pushManager.getSubscription() : null;
    if (!sub) return false;
    await unsubscribePush(sub.endpoint);
    await sub.unsubscribe();
    return true;
  } catch {
    return false;
  }
}
