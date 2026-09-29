@echo off
setlocal
cd /d %~dp0
set "CADUCEUS_SHARED_VENV=%LOCALAPPDATA%\CADUCEUS\venv"
if not "%CADUCEUS_VENV%"=="" set "CADUCEUS_SHARED_VENV=%CADUCEUS_VENV%"
if not exist "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat" (
  echo [ERREUR] Environnement absent. Lancez setup_once.bat.
  pause
  exit /b 1
)
call "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat"
echo Mise a jour explicite des dependances CADUCEUS...
python -m pip install -r requirements.txt
pause
