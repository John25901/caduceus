from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IngestionError(ValueError):
    code: str
    title: str
    message: str
    hints: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": "ingestion_error",
            "code": self.code,
            "title": self.title,
            "message": self.message,
            "hints": self.hints,
            "details": self.details,
        }


def ingestion_error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, IngestionError):
        return exc.as_dict()
    return {
        "type": "ingestion_error",
        "code": "DOCUMENT_INEXPLOITABLE",
        "title": "Document non exploitable",
        "message": "CGS n'a pas pu exploiter ce document de manière suffisamment fiable.",
        "hints": [
            "Vérifiez que le fichier n'est pas corrompu et qu'il s'ouvre normalement.",
            "Pour une image, privilégiez un cadrage droit, un bon contraste et une résolution suffisante.",
            "Si possible, fournissez le PDF ou le fichier Excel d'origine plutôt qu'une capture.",
        ],
        "details": {"technical_message": str(exc)},
    }
