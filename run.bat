@echo off
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create venv. Trying "py" instead...
        py -m venv venv
    )
)

call venv\Scripts\activate.bat

echo Checking dependencies...
pip install -r requirements.txt --quiet --disable-pip-version-check

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: ffmpeg not found on PATH. MP3/MP4 conversion will fail.
    echo Install it with: winget install ffmpeg
    echo.
)

echo Starting Media Grabber at http://localhost:5000

:: open the browser after a short delay, once the server is likely up
start "" /min cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

python app.py

pause
