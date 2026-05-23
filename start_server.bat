@echo off
echo Starting Git Dashboard...

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python to run this dashboard.
    pause
    exit /b
)

:: Install dependencies
echo Checking/Installing dependencies...
pip install -r requirements.txt --quiet

:: Start server in background (or just start and open browser)
echo Starting Flask server on http://127.0.0.1:5000
start "" "http://127.0.0.1:5000"
python app.py

pause