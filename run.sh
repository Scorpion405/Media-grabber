#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -f ".shortcut_created" ]; then
    PROJECT_DIR="$(pwd)"
    if [[ "$OSTYPE" == "darwin"* ]] && [ -d "$HOME/Desktop" ]; then
        osascript -e "tell application \"Finder\" to make alias file to POSIX file \"$PROJECT_DIR/run.sh\" at POSIX file \"$HOME/Desktop\"" >/dev/null 2>&1 \
            && touch ".shortcut_created" && echo "Created a shortcut to run.sh on your Desktop."
    elif [ -d "$HOME/Desktop" ]; then
        cat > "$HOME/Desktop/Media Grabber.desktop" << DESKTOPEOF
[Desktop Entry]
Type=Application
Name=Media Grabber
Exec=bash "$PROJECT_DIR/run.sh"
Path=$PROJECT_DIR
Terminal=true
DESKTOPEOF
        chmod +x "$HOME/Desktop/Media Grabber.desktop" 2>/dev/null
        touch ".shortcut_created" && echo "Created a \"Media Grabber\" shortcut on your Desktop."
    fi
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Checking dependencies..."
pip install -r requirements.txt --quiet --disable-pip-version-check

echo "Checking for yt-dlp updates..."
pip install -U yt-dlp --quiet --disable-pip-version-check

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo ""
    echo "WARNING: ffmpeg not found on PATH. MP3/MP4 conversion will fail."
    echo "Install it with: brew install ffmpeg   (macOS)"
    echo "             or: sudo apt install ffmpeg   (Linux)"
    echo ""
fi

if ! command -v aria2c >/dev/null 2>&1; then
    echo ""
    echo "TIP: Install aria2 for faster multi-connection downloads:"
    echo "     brew install aria2       (macOS)"
    echo "     sudo apt install aria2   (Linux)"
    echo "     (optional — the app works without it, just slower)"
    echo ""
else
    echo "aria2c found — using multi-connection downloads for extra speed."
fi

echo "Starting Media Grabber at http://localhost:5000"

# open the browser after a short delay, once the server is likely up
(
    sleep 2
    if command -v open >/dev/null 2>&1; then
        open http://localhost:5000        # macOS
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:5000    # Linux
    fi
) &

python app.py
