@echo off
setlocal
cd /d %~dp0
set "CADUCEUS_SHARED_VENV=%LOCALAPPDATA%\CADUCEUS\venv"
if not "%CADUCEUS_VENV%"=="" set "CADUCEUS_SHARED_VENV=%CADUCEUS_VENV%"

if exist "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat" (
  call "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat"
) else if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
) else (
  echo [ERREUR] Environnement CADUCEUS absent. Lancez setup_once.bat.
  pause
  exit /b 1
)

echo Verification des seules nouvelles dependances Sprint 3...
python -c "import fitz,pdfplumber,docx,pytesseract; from PIL import Image" >nul 2>&1
if %ERRORLEVEL%==0 (
  echo [OK] Dependances Sprint 3 deja presentes. Aucun pip install necessaire.
  goto :ocr
)

python -m pip install -r requirements-update-v2.3.txt
if errorlevel 1 goto :error

:ocr
python -c "import pytesseract; print(pytesseract.get_tesseract_version())" >nul 2>&1
if %ERRORLEVEL%==0 (
  echo [OK] Tesseract OCR detecte.
) else (
  echo [INFO] Tesseract OCR non detecte. Excel, CSV, TXT, Word et PDF natifs fonctionnent quand meme.
  echo        Installez Tesseract 5 puis, si necessaire, definissez TESSERACT_CMD.
)

echo.
echo [OK] Mise a niveau V2.3 terminee. Utilisez run_caduceus.bat.
pause
exit /b 0

:error
echo [ERREUR] Mise a niveau interrompue.
pause
exit /b 1
