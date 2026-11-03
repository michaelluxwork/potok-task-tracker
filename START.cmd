@echo off
setlocal
cd /d "%~dp0"
set "TRACKER_PUBLIC="
set "TRACKER_STATE_DIR="
set "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost"
set "PORT=4350"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 goto fail
.venv\Scripts\python.exe manage.py collectstatic --noinput
if errorlevel 1 goto fail
echo.
echo Potok: http://127.0.0.1:4350/
echo Register an account, or use existing local demo access from .state\demo-access.txt
echo Press Ctrl+C to stop.
start "" "http://127.0.0.1:4350/"
.venv\Scripts\python.exe serve.py
goto end
:fail
echo Setup failed. See the error above and README.md.
pause
:end
endlocal
