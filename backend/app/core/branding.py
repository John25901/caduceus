from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFile, ImageFont, ImageOps

from backend.app.core.official_logo_data import OFFICIAL_CREATIV_LOGO_B64

BORDEAUX = "#A02041"
BORDEAUX_DARK = "#7D1933"
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
    """Last-resort fallback if both official logo sources are unavailable."""
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
    """Return the official CREATIV GROUP logo.

    Priority:
    1. validated repository asset (allows a future high-resolution replacement);
    2. exact logo supplied by the product owner and embedded in the application;
    3. conservative generated lockup as a last resort.
    """
    if OFFICIAL_LOGO_PATH.exists():
        try:
            return OFFICIAL_LOGO_PATH.read_bytes()
        except Exception:
            pass
    try:
        data = base64.b64decode(OFFICIAL_CREATIV_LOGO_B64, validate=True)
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            # Re-encode through Pillow. This normalizes the embedded PNG and avoids
            # compatibility issues with strict Office PNG parsers.
            previous = ImageFile.LOAD_TRUNCATED_IMAGES
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            try:
                embedded = Image.open(io.BytesIO(data))
                embedded.load()
                embedded = embedded.convert("RGBA")
                out = io.BytesIO()
                embedded.save(out, format="PNG", optimize=True)
                return out.getvalue()
            finally:
                ImageFile.LOAD_TRUNCATED_IMAGES = previous
    except Exception:
        pass
    return _generated_logo_png(compact=compact)


def brand_logo_image(*, compact: bool = False) -> Image.Image:
    image = Image.open(io.BytesIO(brand_logo_png(compact=compact)))
    try:
        image.seek(0)
    except Exception:
        pass
    return ImageOps.exif_transpose(image).convert("RGBA")


def brand_favicon_image(size: int = 64) -> Image.Image:
    """Square favicon derived from the official logo for the browser tab."""
    source = brand_logo_image(compact=True)
    bbox = source.getbbox()
    if bbox:
        source = source.crop(bbox)
    source.thumbnail((size - 8, size - 8), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    x = (size - source.width) // 2
    y = (size - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas


def brand_logo_data_uri(*, compact: bool = False) -> str:
    encoded = base64.b64encode(brand_logo_png(compact=compact)).decode("ascii")
    return f"data:image/png;base64,{encoded}"
