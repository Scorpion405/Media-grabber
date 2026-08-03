# Media Grabber (local)

A local web app for downloading video/audio and photo posts from YouTube,
Instagram, Facebook, X/Twitter, TikTok, SoundCloud, Vimeo, Twitch, Reddit,
Dailymotion, Bandcamp, Tumblr, and Bilibili. Frontend is plain HTML/CSS/JS;
the backend is a small Flask server that drives yt-dlp + ffmpeg.

## Quick start (after first-time setup below)

Once Python and ffmpeg are installed, you don't need to retype setup commands
each time — just run the launch script:

- **Windows**: double-click `run.bat`
- **Mac / Linux**: `./run.sh` from the project folder

Either one creates the virtual environment on first run, installs/updates
dependencies (including yt-dlp itself, kept current automatically), checks
that ffmpeg is on PATH, and starts the server at **http://localhost:5000**.
The very first run also drops a **"Media Grabber" shortcut on your Desktop**
pointing at the launch script, so after that you don't even need the project
folder open — just double-click the shortcut.

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

## Speed

This app uses the same tricks download managers like FDM rely on:

- **Segmented downloads** — each file is split into pieces pulled over up to
  16 parallel connections at once, instead of one connection start-to-finish.
- **aria2c support (optional, recommended)** — if `aria2c` is installed, the
  app hands downloading off to it entirely for true multi-connection,
  segmented downloads (aria2c is what a lot of download managers, FDM
  included, are built on). Install it with `winget install aria2.aria2`
  (Windows), `brew install aria2` (macOS), or `sudo apt install aria2`
  (Linux) — `run.bat`/`run.sh` will tell you if it's missing and detect it
  automatically once it's installed, no config needed.
- **Parallel playlist downloads** — up to 3 videos/tracks download at the
  same time (each still using the segmented-download trick above). This cap
  keeps a large playlist from saturating your bandwidth or spawning dozens of
  ffmpeg processes at once; you can raise it by editing
  `MAX_CONCURRENT_DOWNLOADS` near the top of `app.py` if your connection can
  handle more.

## Features

- **Supported sites**: YouTube (incl. playlists), Instagram, Facebook, X/Twitter,
  TikTok, SoundCloud, Vimeo, Twitch, Reddit, Dailymotion, Bandcamp, Tumblr,
  Bilibili. yt-dlp auto-detects the platform from the URL — no per-site
  config needed.
- **YouTube playlists** — paste the link and the app fetches the video list
  automatically, showing a checklist so you can pick which ones to grab (all
  selected by default). Each video downloads on its own, with its own
  progress bar and its own auto-save.
- **Batch paste** — click "Paste multiple links" to switch the URL box to a
  textarea. Paste any mix of links (from different platforms, even) one per
  line, and each gets its own row — same as the playlist view.
- **Image / Post** downloads photo posts and carousels (Instagram, X,
  Facebook, TikTok photo mode). A single image saves as `.jpg`; a
  multi-image carousel saves as a `.zip`.
- **Title preview** — paste a single (non-playlist) link and a small card
  shows the title, thumbnail, uploader, duration, and approximate size
  before you commit to downloading.
- **ID3 tags + cover art** — MP3s are tagged with title/artist metadata and
  embedded cover art automatically.
- **Embedded subtitles** — check "Embed English subtitles" on an MP4
  download to bake in captions (falls back to YouTube's auto-captions if no
  manual subtitles exist).
- **Browser login (cookies)** — check "Use my browser's login" and pick your
  browser (Chrome/Firefox/Edge/Brave/Safari) to let yt-dlp read your existing
  logged-in session for private or restricted content. Requires that browser
  to be closed on Windows (locked cookie database) — not needed on macOS/Linux.
- **Cancel** — every download (single, playlist row, or batch row) has a
  Cancel button while it's in progress.
- **Download history** — click "History" to see your last 50 downloads with
  one-click re-save, stored locally in your browser and independent of
  whether the app has restarted since.
- **Auto-save** — finished files trigger your browser's save automatically;
  no need to click the link (though it's still there as a backup).
- **Remembered settings** — your last-used format and quality are
  remembered between sessions.
- To access this from your phone on the same Wi-Fi, change the last line of
  `app.py` to `app.run(host="0.0.0.0", port=5000, threaded=True)` and visit
  `http://<your-computer's-local-ip>:5000` from your phone.
- yt-dlp is updated frequently as platforms change their internals. If
  downloads start failing, run `pip install -U yt-dlp` first — that fixes it
  90% of the time.
- This is for personal use with content you have the right to download.
  Redistributing downloaded content can run into copyright/ToS issues
  depending on the platform and the content.
