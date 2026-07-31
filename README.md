# Media Grabber (local)

A local web app for downloading YouTube, Instagram, Facebook, X/Twitter, and
TikTok videos as MP3 or MP4. Frontend is plain HTML/CSS/JS; the backend is a
small Flask server that drives yt-dlp + ffmpeg.

## Quick start (after first-time setup below)

Once Python and ffmpeg are installed, you don't need to retype setup commands
each time — just run the launch script:

- **Windows**: double-click `run.bat`
- **Mac / Linux**: `./run.sh` from the project folder

Either one creates the virtual environment on first run, installs/updates
dependencies, checks that ffmpeg is on PATH, and starts the server at
**http://localhost:5000**. After the first run, it's just double-click →
open browser.

---

## Windows setup

### 1. Install Python

If you don't already have Python, download it from https://www.python.org/downloads/.
On the first install screen, check **"Add python.exe to PATH"** before installing.

### 2. Install ffmpeg (required for MP3 extraction and MP4 merging)

```
winget install ffmpeg
```

Close and reopen your terminal after installing (PATH won't update in the
current window). Verify with:

```
ffmpeg -version
```

If `winget` isn't available, download a build from
https://www.gyan.dev/ffmpeg/builds/ (grab "release essentials"), extract it
to e.g. `C:\ffmpeg`, and add `C:\ffmpeg\bin` to your PATH via
**Environment Variables → Path → New**.

### 3. Set up the Python environment

```
cd yt-dlp-app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

If `python` isn't recognized, try `py` instead (`py -m venv venv`).

### 4. Run it

```
python app.py
```

Open **http://localhost:5000** in your browser.

### 5. Use it

1. Paste a link from YouTube, Instagram, Facebook, X, or TikTok.
2. Pick MP3 (audio) or MP4 (video) and a quality.
3. Hit Download — you'll see a live progress bar, then a save link when it's done.

---

## Linux setup

### 1. Install ffmpeg

```bash
sudo apt install ffmpeg
```

### 2. Set up the Python environment

```bash
cd yt-dlp-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run it

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## macOS setup

### 1. Install ffmpeg

```bash
brew install ffmpeg
```

### 2. Set up the Python environment

```bash
cd yt-dlp-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run it

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## Notes

- yt-dlp auto-detects the platform from the URL — no per-site config needed.
- Private/login-gated content (private IG accounts, friends-only FB posts, etc.)
  generally won't work without extra auth setup (cookies) — this app is built
  for public content.
- To access this from your phone on the same Wi-Fi, change the last line of
  `app.py` to `app.run(host="0.0.0.0", port=5000)` and visit
  `http://<your-computer's-local-ip>:5000` from your phone.
- yt-dlp is updated frequently as platforms change their internals. If
  downloads start failing, run `pip install -U yt-dlp` first — that fixes it
  90% of the time.
- This is for personal use with content you have the right to download.
  Redistributing downloaded content can run into copyright/ToS issues
  depending on the platform and the content.
