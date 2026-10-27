@echo off
setlocal
cd /d "%~dp0"
echo Installs the reviewed, pinned Python dependencies into .venv only.
echo Chromium is optional and is not downloaded by this installer.
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12+ required'"
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install --require-hashes -r requirements.lock
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 exit /b 1
echo Installation complete. Use Launch.cmd.
pause
endlocal
