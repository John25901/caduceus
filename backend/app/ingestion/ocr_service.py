from __future__ import annotations

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


class TesseractOCR:
    """Thin, lazy OCR adapter.

    Tesseract is deliberately external to the Python environment: CADUCEUS can
    process native PDF/Office files without it and only uses OCR for scanned
    pages/images. This keeps normal startup and RAM usage low.
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

    def _lang(self) -> str:
        st = self.status()
        available = set(st.languages)
        desired = [x for x in ("fra", "eng") if x in available]
        return "+".join(desired) if desired else "eng"

    def image_to_text(self, image) -> str:
        if not self.status().available:
            raise RuntimeError(self.status().reason or "OCR Tesseract indisponible")
        import pytesseract

        return pytesseract.image_to_string(image, lang=self._lang(), config="--oem 1 --psm 6")

    def image_to_data(self, image):
        if not self.status().available:
            raise RuntimeError(self.status().reason or "OCR Tesseract indisponible")
        import pytesseract

        return pytesseract.image_to_data(
            image,
            lang=self._lang(),
            config="--oem 1 --psm 6",
            output_type=pytesseract.Output.DATAFRAME,
        )
