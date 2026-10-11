"""Generate srash brand icons (PNG + favicon) from the SVG identity.

Identity: dark-navy rounded square + white speech bubble with green
Arabic letter Seen (ص) + gold notification dot.
Needs: pip install pillow (already in backend .venv).
Run:  python frontend/scripts/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent  # frontend/
PUBLIC = ROOT / "public"
DIST = ROOT / "dist"

BG_TOP = (22, 35, 63)      # #16233f
BG_BOTTOM = (10, 15, 30)   # #0a0f1e
GREEN = (22, 163, 74)      # #16a34a bubble letter
GOLD = (233, 196, 106)     # #e9c46a dot
WHITE = (255, 255, 255)

AR_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arabtype.ttf",
    r"C:\Windows\Fonts\Candarab.ttf",
    r"C:\Windows\Fonts\ARABSQ.TTF",
    r"C:\Windows\Fonts\arial.ttf",
]


def load_ar_font(size: int):
    for p in AR_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_icon(size: int = 512) -> Image.Image:
    s = size
    k = s / 512.0  # scale factor vs the SVG viewBox

    # --- background: diagonal-ish gradient (vertical blend is enough) ---
    bg = Image.new("RGB", (s, s))
    px = bg.load()
    for y in range(s):
        t = y / max(s - 1, 1)
        r = round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        for x in range(s):
            px[x, y] = (r, g, b)
    img = bg.convert("RGBA")

    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    # soft green glow top-right
    for i, alpha in ((150, 26), (110, 40), (70, 60)):
        r = int(190 * k) + i
        gd.ellipse([s - r, -r // 3, s + r // 3, r], fill=(34, 197, 94, alpha))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)

    # --- white speech bubble ---
    bx0, by0, bx1, by1 = [int(v * k) for v in (92, 132, 420, 344)]
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=int(60 * k), fill=WHITE)
    tail = [(int(168 * k), int(336 * k)), (int(146 * k), int(404 * k)), (int(238 * k), int(340 * k))]
    d.polygon(tail, fill=WHITE)

    # --- letter Seen, centered in the bubble ---
    font = load_ar_font(int(150 * k))
    cx = (bx0 + bx1) / 2
    cy = (by0 + by1) / 2
    try:
        bbox = d.textbbox((0, 0), "ص", font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1] - 6 * k),
               "ص", font=font, fill=GREEN)
    except Exception:
        d.text((cx - 40 * k, by0 + 20 * k), "ص", font=font, fill=GREEN)

    # --- gold notification dot with dark ring ---
    dot_c = (int(392 * k), int(120 * k))
    dot_r = int(34 * k)
    ring_w = max(int(10 * k), 2)
    d.ellipse([dot_c[0] - dot_r, dot_c[1] - dot_r,
               dot_c[0] + dot_r, dot_c[1] + dot_r], fill=GOLD)
    d.ellipse([dot_c[0] - dot_r, dot_c[1] - dot_r,
               dot_c[0] + dot_r, dot_c[1] + dot_r],
              outline=BG_BOTTOM, width=ring_w)

    # --- rounded outer corners ---
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, s, s], radius=int(120 * k), fill=255)
    img.putalpha(mask)
    return img


def main() -> None:
    big = draw_icon(512)
    small = big.resize((192, 192), Image.LANCZOS)
    tiny32 = big.resize((32, 32), Image.LANCZOS)
    tiny16 = big.resize((16, 16), Image.LANCZOS)
    for folder in (PUBLIC, DIST):
        folder.mkdir(parents=True, exist_ok=True)
        big.save(folder / "icon-512.png")
        small.save(folder / "icon-192.png")
    # favicon.ico (multi-size) so /favicon.ico stops falling back to index.html
    for folder in (PUBLIC, DIST):
        tiny32.save(folder / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                    append_images=[tiny16])
    print("icons written:",
          *[str(p) for p in [PUBLIC / "icon-512.png", PUBLIC / "icon-192.png",
                             PUBLIC / "favicon.ico"]], sep="\n  ")


if __name__ == "__main__":
    main()
