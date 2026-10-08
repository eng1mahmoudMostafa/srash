"""رفع الصور على Catbox (https://catbox.moe) لتوفير مساحة السيرفر.

الفكرة: المستخدم يرفع الصورة -> ننظفها (تصغير + إزالة EXIF) ->
نرفعها على Catbox -> نخزن الرابط فقط في قاعدة البيانات.
النتيجة: صفر مساحة تخزين صور على PythonAnywhere.
"""
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

CATBOX_API_URL = "https://catbox.moe/user/api.php"
TIMEOUT = 25  # ثانية


def upload_to_catbox(file_bytes: bytes, filename: str = "image.jpg") -> str:
    """ارفع بايتات صورة على Catbox وأرجع الرابط المباشر.

    يرمي RuntimeError لو فشل الرفع (حتى يرى المستخدم رسالة واضحة).
    """
    import uuid

    boundary = f"----catbox{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="reqtype"\r\n\r\n'
        "fileupload\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        CATBOX_API_URL,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "srash-app/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="replace").strip()
    except Exception as exc:
        logger.warning("catbox upload failed: %s", exc)
        raise RuntimeError("تعذر رفع الصورة حالياً — حاول مجدداً بعد قليل.")

    if not text.startswith("https://files.catbox.moe/"):
        logger.warning("catbox unexpected response: %s", text[:200])
        raise RuntimeError("تعذر رفع الصورة حالياً — حاول مجدداً بعد قليل.")
    # تنظيف الرابط احترازياً
    parsed = urllib.parse.urlparse(text)
    if parsed.netloc != "files.catbox.moe":
        raise RuntimeError("تعذر رفع الصورة حالياً — حاول مجدداً بعد قليل.")
    return text
