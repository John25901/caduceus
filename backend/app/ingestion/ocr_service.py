from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OCRStatus:
    available: bool
    engine: str
    executable: str | None
    languages: tuple[str, ...]
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "engine": self.engine,
            "executable": self.executable,
            "languages": list(self.languages),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OCRReadResult:
    text: str
    confidence: float
    strategy: str
    psm: int
    token_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "confidence": round(self.confidence, 2),
            "strategy": self.strategy,
            "psm": self.psm,
            "token_count": self.token_count,
            "text_chars": len(self.text),
        }


class TesseractOCR:
    """Lazy OCR adapter with a lightweight quality-recovery pipeline.

    The application remains native-first. OCR is only invoked for image/scanned
    inputs. For difficult images, a small number of deterministic preprocessing
    variants are tested and the best Tesseract result is selected from measured
    OCR confidence; no generative model is used to invent unreadable content.
    """

    def __init__(self) -> None:
        self._status: OCRStatus | None = None

    def status(self) -> OCRStatus:
        if self._status is not None:
            return self._status
        try:
            import pytesseract
        except Exception as exc:  # pragma: no cover - environment dependent
            self._status = OCRStatus(False, "tesseract", None, (), f"pytesseract indisponible: {exc}")
            return self._status

        explicit = os.getenv("TESSERACT_CMD") or os.getenv("CADUCEUS_TESSERACT_CMD")
        executable = explicit or shutil.which("tesseract")
        if not executable and os.name == "nt":
            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            executable = next((x for x in candidates if x and os.path.exists(x)), None)
        if executable:
            pytesseract.pytesseract.tesseract_cmd = executable
        try:
            version = str(pytesseract.get_tesseract_version())
            langs = tuple(sorted(set(pytesseract.get_languages(config=""))))
            self._status = OCRStatus(True, f"tesseract {version.splitlines()[0]}", executable, langs)
        except Exception as exc:  # pragma: no cover - environment dependent
            self._status = OCRStatus(False, "tesseract", executable, (), str(exc))
        return self._status

    def reset_status(self) -> None:
        """Allow a process to re-detect Tesseract after a local installation."""
        self._status = None

    def _lang(self) -> str:
        st = self.status()
        available = set(st.languages)
        desired = [x for x in ("fra", "eng") if x in available]
        return "+".join(desired) if desired else "eng"

    @staticmethod
    def _to_rgb(image):
        from PIL import Image, ImageOps

        try:
            image.seek(0)
        except Exception:
            pass
        image = ImageOps.exif_transpose(image)
        if image.mode in {"RGBA", "LA"} or ("transparency" in getattr(image, "info", {})):
            rgba = image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, "white")
            bg.alpha_composite(rgba)
            return bg.convert("RGB")
        return image.convert("RGB")

    @staticmethod
    def _resize_for_ocr(image):
        """Upscale small screenshots and cap huge scans to control latency/RAM."""
        from PIL import Image

        w, h = image.size
        longest = max(w, h)
        if longest < 2200:
            # Supplier screenshots and messaging-app images often need stronger
            # enlargement before Tesseract can separate small glyphs.
            scale = min(4.0, 2200.0 / max(1, longest))
            return image.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
        if longest > 3600:
            scale = 3600.0 / longest
            return image.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
        return image

    @staticmethod
    def _otsu_threshold(gray) -> int:
        hist = gray.histogram()[:256]
        total = sum(hist)
        if total <= 0:
            return 180
        sum_total = sum(i * count for i, count in enumerate(hist))
        sum_bg = 0.0
        weight_bg = 0
        best_var = -1.0
        best = 180
        for i, count in enumerate(hist):
            weight_bg += count
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break
            sum_bg += i * count
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg
            between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if between > best_var:
                best_var = between
                best = i
        return max(80, min(220, best))

    def _variants(self, image):
        from PIL import ImageFilter, ImageOps

        rgb = self._resize_for_ocr(self._to_rgb(image))
        gray = ImageOps.grayscale(rgb)
        contrast = ImageOps.autocontrast(gray, cutoff=1)
        enhanced = contrast.filter(ImageFilter.UnsharpMask(radius=1.6, percent=190, threshold=2))
        denoised = contrast.filter(ImageFilter.MedianFilter(size=3)).filter(
            ImageFilter.UnsharpMask(radius=1.3, percent=175, threshold=2)
        )
        threshold = self._otsu_threshold(contrast)
        binary = contrast.point(lambda x: 255 if x > threshold else 0, mode="1").convert("L")
        return [
            ("enhanced", enhanced),
            ("denoised", denoised),
            ("binary", binary),
        ]

    @staticmethod
    def _frame_text(data) -> tuple[str, float, int]:
        """Rebuild line-oriented text and compute mean confidence from Tesseract data."""
        if data is None or getattr(data, "empty", True):
            return "", 0.0, 0

        df = data.copy()
        if "text" not in df.columns or "conf" not in df.columns:
            return "", 0.0, 0
        df["text"] = df["text"].fillna("").astype(str).str.strip()
        try:
            df["conf_num"] = df["conf"].astype(float)
        except Exception:
            import pandas as pd
            df["conf_num"] = pd.to_numeric(df["conf"], errors="coerce")

        tokens = df[(df["text"] != "") & (df["conf_num"].fillna(-1) >= 0)]
        if tokens.empty:
            return "", 0.0, 0

        group_cols = [c for c in ("page_num", "block_num", "par_num", "line_num") if c in tokens.columns]
        if group_cols:
            lines = []
            for _, group in tokens.groupby(group_cols, sort=False):
                line = " ".join(x for x in group["text"].tolist() if x).strip()
                if line:
                    lines.append(line)
            text = "\n".join(lines)
        else:
            text = " ".join(tokens["text"].tolist())

        conf = float(tokens["conf_num"].mean()) if len(tokens) else 0.0
        if not math.isfinite(conf):
            conf = 0.0
        return text.strip(), max(0.0, min(100.0, conf)), int(len(tokens))

    def _read_once(self, image, *, strategy: str, psm: int) -> OCRReadResult:
        if not self.status().available:
            raise RuntimeError(self.status().reason or "OCR Tesseract indisponible")
        import pytesseract

        timeout = max(10, int(os.getenv("CADUCEUS_OCR_TIMEOUT_SECONDS", "60")))
        data = pytesseract.image_to_data(
            image,
            lang=self._lang(),
            config=f"--oem 1 --psm {psm} -c preserve_interword_spaces=1",
            output_type=pytesseract.Output.DATAFRAME,
            timeout=timeout,
        )
        text, confidence, tokens = self._frame_text(data)
        return OCRReadResult(text=text, confidence=confidence, strategy=strategy, psm=psm, token_count=tokens)

    @staticmethod
    def _quality_score(result: OCRReadResult) -> float:
        # Confidence dominates; token count/text volume only break close ties.
        return result.confidence + min(result.token_count, 80) * 0.12 + min(len(result.text), 1200) / 300.0

    def read_best(self, image) -> OCRReadResult:
        if not self.status().available:
            raise RuntimeError(self.status().reason or "OCR Tesseract indisponible")

        variants = self._variants(image)
        attempts: list[OCRReadResult] = []

        # Fast path: most supplier scans work after contrast + sharpening.
        first = self._read_once(variants[0][1], strategy=variants[0][0], psm=6)
        attempts.append(first)
        if first.confidence >= 72 and first.token_count >= 10 and len(first.text) >= 50:
            return first

        # Recovery path for blurred screenshots, sparse invoices and low contrast.
        # PSM 3/4 are important for supplier tables where columns/blocks do not
        # follow a single uniform text flow; PSM 11 recovers sparse labels.
        plan = [
            (variants[0], 4),
            (variants[0], 11),
            (variants[1], 3),
            (variants[1], 6),
            (variants[2], 6),
        ]
        for (strategy, variant), psm in plan:
            try:
                candidate = self._read_once(variant, strategy=strategy, psm=psm)
                attempts.append(candidate)
                if candidate.confidence >= 80 and candidate.token_count >= 12 and len(candidate.text) >= 80:
                    break
            except Exception:
                continue

        return max(attempts, key=self._quality_score)

    def image_to_text(self, image) -> str:
        return self.read_best(image).text

    def image_to_data(self, image):
        if not self.status().available:
            raise RuntimeError(self.status().reason or "OCR Tesseract indisponible")
        import pytesseract

        normalized = self._variants(image)[0][1]
        return pytesseract.image_to_data(
            normalized,
            lang=self._lang(),
            config="--oem 1 --psm 6 -c preserve_interword_spaces=1",
            output_type=pytesseract.Output.DATAFRAME,
            timeout=max(10, int(os.getenv("CADUCEUS_OCR_TIMEOUT_SECONDS", "60"))),
        )
