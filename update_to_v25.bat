@echo off
setlocal
cd /d %~dp0

echo ===============================================
echo CADUCEUS V2.5 - Mise a jour Sprint 5
echo Aucune reinstallation de requirements.txt
echo ===============================================

echo [1/2] Verification du moteur OCR Windows...
call install_ocr_windows.bat
if %ERRORLEVEL%==10 echo [!] OCR non installe automatiquement. CADUCEUS continuera avec les documents natifs.

echo [2/2] Mise a jour terminee.
echo Lancez maintenant run_caduceus.bat
pause
