@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Install.cmd first using Python 3.12 or newer.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:8501"
".venv\Scripts\python.exe" -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true
endlocal
