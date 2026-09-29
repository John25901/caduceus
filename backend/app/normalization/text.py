from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


_WS_RE = re.compile(r"\s+")
_DIGIT_RE = re.compile(r"\d")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    return _WS_RE.sub(" ", text)


def normalize_search_text(value: object) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _WS_RE.sub(" ", text).strip()


def normalize_hs_code(value: object) -> Optional[str]:
    """Return compact CAMCIS/HS identifier while preserving leading zeros.

    Examples:
      010121.00.000 -> 01012100000
      84414000000   -> 84414000000
    """
    raw = clean_text(value)
    if not raw:
        return None
    digits = "".join(_DIGIT_RE.findall(raw))
    if not digits:
        return None
    return digits


def display_hs_code(compact: str | None) -> str | None:
    """Render 11-digit CAMCIS code as 6.2.3 when possible."""
    if not compact:
        return None
    compact = normalize_hs_code(compact) or ""
    if len(compact) == 11:
        return f"{compact[:6]}.{compact[6:8]}.{compact[8:]}"
    return compact


def hs_hierarchy(compact: str | None) -> dict[str, str | None]:
    code = normalize_hs_code(compact)
    if not code:
        return {"chapter": None, "heading": None, "subheading6": None}
    return {
        "chapter": code[:2] if len(code) >= 2 else None,
        "heading": code[:4] if len(code) >= 4 else None,
        "subheading6": code[:6] if len(code) >= 6 else None,
    }
