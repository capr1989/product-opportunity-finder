@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Install.cmd first.
  pause
  exit /b 1
)
echo Downloads Playwright's official Chromium into this project's data folder.
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0data\browsers"
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 exit /b 1
echo Browser installation complete. Restart the dashboard if it is already open.
pause
endlocal
