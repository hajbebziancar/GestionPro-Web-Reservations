@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GestionPro - Site Web Reservations
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creation de l'environnement Python...
  %PY% -m venv .venv || goto :error
)
echo [2/3] Installation / verification des dependances...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :error
echo [3/3] Demarrage du site GestionPro...
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
goto :eof
:error
echo.
echo ERREUR: Python 3 est requis. Installez Python puis relancez ce fichier.
pause
