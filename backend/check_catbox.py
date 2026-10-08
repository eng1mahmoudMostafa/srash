"""تشخيص سريع لرفع صور — يتشغل من كونسول PythonAnywhere:

    cd ~/srash/backend && CATBOX_USERHASH=<hash> python3 check_catbox.py          # Catbox بس
    cd ~/srash/backend && CATBOX_USERHASH=<hash> python3 check_catbox.py --full   # كل الخدمات

بيطبع الرابط لو الرفع شغال، أو كود/رسالة الخطأ لكل خدمة.
مفيش سر في الملف — الـ userhash والـ IMGBB_KEY بيتقروا من متغيرات البيئة.
"""
import base64
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.catbox import upload_to_catbox  # noqa: E402

# صورة JPEG حقيقية صغيرة (1×1 بكسل)
TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
    "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
    "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
    "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iii"
    "gD//2Q=="
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def _post(url: str, body: bytes, headers: dict, tag: str, timeout: int = 12) -> None:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace").strip()
            print(f"{tag} -> {resp.status}: {text[:200]}")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace").strip()
        print(f"{tag} -> HTTP {exc.code}: {text[:200]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{tag} -> {type(exc).__name__}: {str(exc)[:200]}")


def _multipart(fields: dict, filename: str, file_bytes: bytes, file_field: str = "file") -> tuple[bytes, dict]:
    """يبني multipart/form-data ويعيد (الجسم، الهيدرز)."""
    boundary = "----x" + uuid.uuid4().hex
    body = b""
    for name, value in fields.items():
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{filename}"\r\nContent-Type: image/jpeg\r\n\r\n'
    ).encode()
    body += file_bytes + f"\r\n--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": UA}


def diag() -> None:
    data = base64.b64decode(TINY_JPEG_B64)
    userhash = os.environ.get("CATBOX_USERHASH", "").strip()
    print(f"CATBOX_USERHASH = {'set (' + str(len(userhash)) + ' chars)' if userhash else 'EMPTY (anonymous)'}")
    print(f"IMGBB_KEY = {'set' if os.environ.get('IMGBB_KEY', '').strip() else 'EMPTY (will skip)'}")
    print("-" * 60)

    # 1) Catbox بـ userhash
    body, headers = _multipart({"reqtype": "fileupload", "userhash": userhash}, "t.jpg", data, "fileToUpload")
    _post("https://catbox.moe/user/api.php", body, headers, "catbox +userhash")

    # 2) Catbox مجهول (من غير حقل userhash خالص — زي التوثيق الرسمي)
    body, headers = _multipart({"reqtype": "fileupload"}, "t.jpg", data, "fileToUpload")
    _post("https://catbox.moe/user/api.php", body, headers, "catbox anonymous")

    # 3) 0x0.st (لو رجع يقبل الرفع)
    body, headers = _multipart({}, "t.jpg", data)
    _post("https://0x0.st", body, headers, "0x0.st")

    # 4) ImgBB (لو المفتاح مضبوط)
    imgbb_key = os.environ.get("IMGBB_KEY", "").strip()
    if imgbb_key:
        body, headers = _multipart({}, "t.jpg", data, "image")
        _post(f"https://api.imgbb.com/1/upload?key={imgbb_key}", body, headers, "imgbb")
    print("-" * 60)
    print("Done - paste the full output back.")


def main() -> int:
    if "--full" in sys.argv:
        diag()
        return 0
    hash_value = os.environ.get("CATBOX_USERHASH", "").strip()
    print(
        "CATBOX_USERHASH = "
        + (f"set ({len(hash_value)} chars)" if hash_value else "EMPTY (anonymous)")
    )
    t0 = time.time()
    try:
        url = upload_to_catbox(base64.b64decode(TINY_JPEG_B64), "check.jpg")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1
    print(f"OK: {url} ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

