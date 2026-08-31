// أزرار المشاركة السريعة لرابط صفحة «صراحة» على المنصات الشهيرة.
import { useState } from "react";

/**
 * url: الرابط المراد مشاركته (رابط صفحة المستخدم).
 * title: نص قصير يُلحق بالنص (اختياري).
 */
export default function ShareRow({ url, title = "" }) {
  const [copied, setCopied] = useState(false);

  const shareText = title || "ابعتلي رسالة صراحة مجهولة 💬";

  const openShare = (href) => {
    window.open(href, "_blank", "noopener,noreferrer,width=700,height=520");
  };

  function copyLink() {
    const done = () => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done).catch(() => {});
    } else {
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      done();
    }
  }

  return (
    <div className="share-row">
      <button
        type="button"
        className="share-btn share-wa"
        onClick={() =>
          openShare(`https://wa.me/?text=${encodeURIComponent(shareText + "\n" + url)}`)
        }
      >
        واتساب
      </button>
      <button
        type="button"
        className="share-btn share-tg"
        onClick={() =>
          openShare(
            `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(shareText)}`
          )
        }
      >
        تليجرام
      </button>
      <button
        type="button"
        className="share-btn share-x"
        onClick={() =>
          openShare(
            `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(shareText)}`
          )
        }
      >
        إكس
      </button>
      <button
        type="button"
        className="share-btn share-fb"
        onClick={() =>
          openShare(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`)
        }
      >
        فيسبوك
      </button>
      <button type="button" className="share-btn share-copy" onClick={copyLink}>
        {copied ? "✓ تم النسخ" : "نسخ الرابط"}
      </button>
    </div>
  );
}