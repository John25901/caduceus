@echo off
setlocal
cd /d %~dp0
set "CADUCEUS_SHARED_VENV=%LOCALAPPDATA%\CADUCEUS\venv"
if not "%CADUCEUS_VENV%"=="" set "CADUCEUS_SHARED_VENV=%CADUCEUS_VENV%"
if exist "%CADUCEUS_SHARED_VENV%\Scripts\python.exe" (
  "%CADUCEUS_SHARED_VENV%\Scripts\python.exe" -m scripts.configure_ai
) else if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m scripts.configure_ai
) else if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe -m scripts.configure_ai
) else (
  echo [ERREUR] Environnement Python CADUCEUS introuvable. Lancez setup_once.bat une seule fois.
  pause
  exit /b 1
)
pause
