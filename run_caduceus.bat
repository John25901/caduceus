@echo off
setlocal
cd /d %~dp0

set "CADUCEUS_SHARED_VENV=%LOCALAPPDATA%\CADUCEUS\venv"
if not "%CADUCEUS_VENV%"=="" set "CADUCEUS_SHARED_VENV=%CADUCEUS_VENV%"

echo ===============================================
echo CADUCEUS V2.6 - Sprint 6 IA controlee
echo Environnement Python persistant - Docker NON requis
echo ===============================================

if exist "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat" (
  call "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat"
) else if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
  call venv\Scripts\activate.bat
) else (
  echo [ERREUR] Aucun environnement Python CADUCEUS trouve.
  echo Lancez UNE SEULE FOIS : setup_once.bat
  pause
  exit /b 1
)

if not exist data\reference\Code_SH_CAMCIS.xlsx (
  echo [ERREUR] Referentiel CAMCIS absent. Aucun fallback fictif ne sera utilise.
  pause
  exit /b 2
)

echo.
echo [1/4] Verification CAMCIS...
python -m scripts.bootstrap
set BOOTSTRAP_CODE=%ERRORLEVEL%
if %BOOTSTRAP_CODE%==2 (
  echo [ERREUR] Echec fatal du bootstrap des references.
  pause
  exit /b 3
)
if %BOOTSTRAP_CODE%==10 (
  echo [!] Couche semantique indisponible. Demarrage lexical + memoire validee.
  set CADUCEUS_AUTO_SYNC_INDEX=0
)
if not %BOOTSTRAP_CODE%==0 if not %BOOTSTRAP_CODE%==10 (
  echo [ERREUR] Bootstrap inattendu, code %BOOTSTRAP_CODE%.
  pause
  exit /b 4
)

echo.
echo [2/4] Verification OCR...
python -m scripts.ocr_bootstrap >nul 2>nul
if not %ERRORLEVEL%==0 echo [!] OCR image/scans non actif. Vous pouvez lancer install_ocr_windows.bat une seule fois.

echo.
echo [3/4] Demarrage API FastAPI...
start "CADUCEUS API" cmd /k "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"

echo [4/4] Attente de l'API avant ouverture de l'interface...
python -m scripts.wait_for_api http://127.0.0.1:8000/health 120
if not %ERRORLEVEL%==0 (
  echo [ERREUR] L'API n'a pas demarre correctement. Consultez la fenetre CADUCEUS API.
  pause
  exit /b 5
)

start "CADUCEUS UI" cmd /k "python -m streamlit run frontend/app.py"
echo.
echo [OK] CADUCEUS lance sur http://localhost:8501
