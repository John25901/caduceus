@echo off
setlocal
cd /d %~dp0
set "CADUCEUS_SHARED_VENV=%LOCALAPPDATA%\CADUCEUS\venv"
if not "%CADUCEUS_VENV%"=="" set "CADUCEUS_SHARED_VENV=%CADUCEUS_VENV%"

echo ===============================================
echo CADUCEUS - installation initiale UNE SEULE FOIS
echo Environnement : %CADUCEUS_SHARED_VENV%
echo ===============================================

if not exist "%CADUCEUS_SHARED_VENV%\Scripts\python.exe" (
  python -m venv "%CADUCEUS_SHARED_VENV%"
  if errorlevel 1 goto :error
)
call "%CADUCEUS_SHARED_VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo [OK] Installation terminee. A l'avenir, utilisez seulement run_caduceus.bat
pause
exit /b 0

:error
echo [ERREUR] Installation interrompue.
pause
exit /b 1
