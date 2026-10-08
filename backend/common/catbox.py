"""رفع الصور على Catbox (https://catbox.moe) لتوفير مساحة السيرفر.

الفكرة: المستخدم يرفع الصورة -> ننظفها (تصغير + إزالة EXIF) ->
نرفعها على Catbox -> نخزن الرابط فقط في قاعدة البيانات.
النتيجة: صفر مساحة تخزين صور على PythonAnywhere.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import uuid

logger = logging.getLogger(__name__)

CATBOX_API_URL = "https://catbox.moe/user/api.php"
TIMEOUT = 8  # ثانية — يبقى زمن المحاولات كلهًا أقل من مهلة طلب السيرفر (~30ث)
UPLOAD_RETRIES = 3        # محاولة إعادة الرفع في حال فشل مؤقت
BACKOFF_BASE = 1.0        # ثانية (مضاعفة كل محاولة)

CRLF = chr(13) + chr(10)
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
IMGBB_API_URL = "https://api.imgbb.com/1/upload"
# مهلة طلب السيرفر ~30 ثانية — لو استهلكنا أغلبها على Catbox (أوقات اتصال
# بطيئة) نقف ونسمح بالتخزين المحلي بدل تجاوز المهلة والقتل.
IMG_HOST_BUDGET = 20.0


def _post_catbox(file_bytes: bytes, filename: str) -> str:
    """ارفع بايتات صورة على Catbox وأرجع الرابط المباشر، أو ارفع خطأ."""
    boundary = f"----catbox{uuid.uuid4().hex}"
    body = (
        f"--{boundary}{CRLF}"
        f'Content-Disposition: form-data; name="reqtype"{CRLF}{CRLF}'
        f"fileupload{CRLF}"
        f"--{boundary}{CRLF}"
        # هوية المُرفِع: من IP سيرفرات (زي PythonAnywhere) Catbox بيرفض
        # الرفع المجهول بـ 412 "Invalid uploader" — لازم userhash حقيقي
        # بتاع حساب مجاني. نقرؤه من متغير البيئة CATBOX_USERHASH عشان
        # متتحطش في الريبو (الـ userhash سر: أي حد معاه يقدر يحذف الصور).
        # لو المتغير مش مضبوط نبعته فاضي (رفع مجهول — شغال من IPs عادية).
        f'Content-Disposition: form-data; name="userhash"{CRLF}{CRLF}'
        f"{os.environ.get('CATBOX_USERHASH', '').strip()}{CRLF}"
        f"--{boundary}{CRLF}"
        f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"{CRLF}'
        f"Content-Type: image/jpeg{CRLF}{CRLF}"
    ).encode() + file_bytes + f"{CRLF}--{boundary}--{CRLF}".encode()

    req = urllib.request.Request(
        CATBOX_API_URL,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            # UA بتاع بوت + Catbox بيرجّع 412 — نبعت UA زي المتصفحات.
            "User-Agent": BROWSER_UA,
            "Accept": "*/*",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        text = resp.read().decode("utf-8", errors="replace").strip()

    if not text.startswith("https://files.catbox.moe/"):
        raise RuntimeError(f"تعذر رفع الصورة: استجابة غير متوقعة ({text[:64]})")
    parsed = urllib.parse.urlparse(text)
    if parsed.netloc != "files.catbox.moe":
        raise RuntimeError("تعذر رفع الصورة: رابط غير متوقع")
    return text


def _post_imgbb(file_bytes: bytes, filename: str) -> str:
    """ارفع بايتات صورة على ImgBB (بديل مجاني حين يحجب Catbox الـ IP) وارجع الرابط.

    يرمي Exception لو المفتاح ناقص أو الطلب فشل — المتصل يقرر الخطوة التالية.
    """
    key = os.environ.get("IMGBB_KEY", "").strip()
    if not key:
        raise RuntimeError("IMGBB_KEY غير مضبوط")
    boundary = f"----imgbb{uuid.uuid4().hex}"
    body = (
        f"--{boundary}{CRLF}"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"{CRLF}'
        f"Content-Type: image/jpeg{CRLF}{CRLF}"
    ).encode() + file_bytes + f"{CRLF}--{boundary}--{CRLF}".encode()

    req = urllib.request.Request(
        f"{IMGBB_API_URL}?key={urllib.parse.quote(key)}",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": BROWSER_UA,
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    try:
        url = str(json.loads(text)["data"]["url"])
    except Exception:
        raise RuntimeError(
            f"تعذر رفع الصورة على ImgBB: استجابة غير متوقعة ({text[:64]})"
        )
    if not url.startswith("https://i.ibb.co/"):
        raise RuntimeError("تعذر رفع الصورة على ImgBB: رابط غير متوقع")
    return url


def upload_to_catbox(file_bytes: bytes, filename: str = "image.jpg") -> str:
    """ارفع صورة وارجع رابط دائم: Catbox أولًا، ثم ImgBB لو IMGBB_KEY مضبوط.

    تعيد Raise RuntimeError إذا فشل المضيفان — أي نداء يخزن الصورة محليًا.
    """
    started = time.monotonic()
    last_error = None
    for attempt in range(1, UPLOAD_RETRIES + 1):
        try:
            return _post_catbox(file_bytes, filename)
        except Exception as exc:
            last_error = exc
            logger.warning(
                "catbox upload attempt %d/%d failed: %s",
                attempt,
                UPLOAD_RETRIES,
                exc,
            )
            if attempt < UPLOAD_RETRIES:
                time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))

    # Catbox فشل (منه 412 "Invalid uploader" لو الـ IP داتا سنتر): لو ImgBB
    # مضبوط وفيه وقت متبقٍ قبل مهلة الطلب (~30 ث) نجربه قبل التخزين المحلي.
    if os.environ.get("IMGBB_KEY", "").strip():
        if time.monotonic() - started < IMG_HOST_BUDGET:
            logger.info("catbox failed (%s) — trying ImgBB fallback", last_error)
            try:
                return _post_imgbb(file_bytes, filename)
            except Exception as exc:
                last_error = exc
                logger.warning("imgbb fallback failed: %s", exc)
        else:
            logger.warning("imgbb fallback skipped (time budget used up)")

    logger.error(
        "image upload permanently failed after %d attempts: %s",
        UPLOAD_RETRIES,
        last_error,
    )
    raise RuntimeError("تعذر رفع الصورة حالياً — حاول مجدداً بعد قليل.")