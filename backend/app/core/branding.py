from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BORDEAUX = "#982040"
BORDEAUX_DARK = "#74172F"
CHARCOAL = "#2F3136"
GRAY = "#6D7076"
LIGHT = "#F5F5F6"

ROOT = Path(__file__).resolve().parents[3]
OFFICIAL_LOGO_PATH = ROOT / "assets" / "creativ_group_logo.png"


def _font(size: int, *, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _generated_logo_png(*, compact: bool = False) -> bytes:
    """Fallback corporate lockup used until the exact official PNG is supplied.

    The generated mark deliberately uses only the validated CREATIV GROUP wordmark
    and the platform initials; it does not attempt to recreate an unavailable
    proprietary emblem.
    """
    width, height = ((720, 170) if not compact else (520, 128))
    scale = height / 170
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    pad = int(12 * scale)
    mark = int(132 * scale)
    radius = int(24 * scale)
    x0, y0 = pad, int(18 * scale)
    x1, y1 = x0 + mark, y0 + mark
    draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=BORDEAUX)

    # Minimal CG monogram: neutral fallback, not presented as the official emblem.
    mono_font = _font(max(28, int(52 * scale)), bold=True)
    bbox = draw.textbbox((0, 0), "CG", font=mono_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x0 + (mark - tw) / 2, y0 + (mark - th) / 2 - int(4 * scale)), "CG", font=mono_font, fill="white")

    tx = x1 + int(24 * scale)
    title_font = _font(max(24, int(38 * scale)), bold=True)
    sub_font = _font(max(14, int(20 * scale)), bold=False)
    draw.text((tx, int(34 * scale)), "CREATIV GROUP", font=title_font, fill=CHARCOAL)
    draw.text((tx, int(88 * scale)), "SARL", font=title_font, fill=BORDEAUX)
    if not compact:
        draw.text((tx, int(132 * scale)), "CGS - Harmonisation Douaniere", font=sub_font, fill=GRAY)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def brand_logo_png(*, compact: bool = False) -> bytes:
    """Return the official logo file when present, otherwise a safe CGS lockup."""
    if OFFICIAL_LOGO_PATH.exists():
        try:
            return OFFICIAL_LOGO_PATH.read_bytes()
        except Exception:
            pass
    return _generated_logo_png(compact=compact)


def brand_logo_data_uri(*, compact: bool = False) -> str:
    encoded = base64.b64encode(brand_logo_png(compact=compact)).decode("ascii")
    return f"data:image/png;base64,{encoded}"
