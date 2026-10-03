@echo off
cd /d "%~dp0"
if not exist donnees_apercu mkdir donnees_apercu
set GP_MOBILE_TOKEN=apercu-local-android
set GP_PC_TOKEN=apercu-local-pc
set GP_RELAY_DB=%~dp0donnees_apercu\mobile.sqlite3
set PORT=8766
start "" http://localhost:8766/mobile/
echo Apercu local uniquement. Pas de connexion aux donnees reelles sans installation.
echo Cle Android pour cet apercu : apercu-local-android
where py >nul 2>nul
if %errorlevel%==0 (py -3 relay.py) else (python relay.py)
pause
