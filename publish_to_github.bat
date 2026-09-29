@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul || (
  echo Git n'est pas installe ou pas dans le PATH.
  pause
  exit /b 1
)

echo.
echo === CADUCEUS - publication GitHub ===
echo Creez d'abord un depot GitHub VIDE et prive.
echo Exemple: https://github.com/votre-compte/caduceus.git
echo.
set /p REPO_URL=URL du depot GitHub: 
if "%REPO_URL%"=="" exit /b 1

if not exist .git git init
git add .
git diff --cached --quiet
if errorlevel 1 git commit -m "CADUCEUS V2.6 deploy"
git branch -M main

git remote get-url origin >nul 2>nul
if errorlevel 1 (
  git remote add origin "%REPO_URL%"
) else (
  git remote set-url origin "%REPO_URL%"
)

git push -u origin main
if errorlevel 1 (
  echo.
  echo Echec du push. Verifiez votre authentification GitHub.
  pause
  exit /b 1
)

echo.
echo Publication terminee. Vous pouvez maintenant deployer streamlit_app.py sur Streamlit Community Cloud.
pause
