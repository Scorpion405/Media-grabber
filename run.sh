#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Checking dependencies..."
pip install -r requirements.txt --quiet --disable-pip-version-check

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo ""
    echo "WARNING: ffmpeg not found on PATH. MP3/MP4 conversion will fail."
    echo "Install it with: brew install ffmpeg   (macOS)"
    echo "             or: sudo apt install ffmpeg   (Linux)"
    echo ""
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
