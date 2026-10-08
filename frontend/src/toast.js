// إشعار عام يظهر في أعلى الشاشة (ثابت) — يراه المستخدم فورًا مهما كان موضعه
// في الصفحة، فلا يحتاج على الموبايل لسحب الصفحة للأعلى لرؤيته.
// يعتمد على نفس نمط الأحداث المفتوح المستخدم في شريط الانتظار (srash:busy).
export function toast(text, type = "ok") {
  if (!text) return;
  window.dispatchEvent(
    new CustomEvent("srash:toast", { detail: { text: String(text), type } })
  );
}
