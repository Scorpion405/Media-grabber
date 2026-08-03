@echo off
cd /d "%~dp0"

if not exist ".shortcut_created" (
    powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Media Grabber.lnk')); $s.TargetPath='%~dp0run.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='shell32.dll,13'; $s.Save()" >nul 2>nul
    if not errorlevel 1 (
        echo. > ".shortcut_created"
        echo Created a "Media Grabber" shortcut on your Desktop.
    )
)

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

echo Checking for yt-dlp updates...
pip install -U yt-dlp --quiet --disable-pip-version-check

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: ffmpeg not found on PATH. MP3/MP4 conversion will fail.
    echo Install it with: winget install ffmpeg
    echo.
)

where aria2c >nul 2>nul
if errorlevel 1 (
    echo.
    echo TIP: Install aria2 for faster multi-connection downloads:
    echo      winget install aria2.aria2
    echo      ^(optional — the app works without it, just slower^)
    echo.
) else (
    echo aria2c found — using multi-connection downloads for extra speed.
)

echo Starting Media Grabber at http://localhost:5000

:: open the browser after a short delay, once the server is likely up
start "" /min cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

python app.py

pause
