@echo off
setlocal
cd /d %~dp0

where tesseract >nul 2>nul
if %ERRORLEVEL%==0 (
  echo [OCR] Tesseract est deja installe.
  exit /b 0
)
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  echo [OCR] Tesseract detecte dans Program Files.
  exit /b 0
)

where winget >nul 2>nul
if not %ERRORLEVEL%==0 (
  echo [OCR] winget indisponible. Installez Tesseract OCR puis relancez CADUCEUS.
  exit /b 10
)

echo [OCR] Installation automatique de Tesseract OCR pour le traitement des images/scans...
winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements
if not %ERRORLEVEL%==0 (
  echo [OCR] Installation automatique non terminee. Les documents natifs restent utilisables.
  exit /b 10
)

echo [OCR] Installation terminee.
exit /b 0
