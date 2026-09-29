from backend.app.ingestion.ocr_service import TesseractOCR


def main() -> int:
    st = TesseractOCR().status()
    if st.available:
        print(f"[OCR] OK - {st.engine}")
        return 0
    print(f"[OCR] moteur Tesseract absent: {st.reason or 'non détecté'}")
    return 10


if __name__ == "__main__":
    raise SystemExit(main())
