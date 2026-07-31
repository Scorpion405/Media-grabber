"""
Local media downloader — backend
Wraps yt-dlp (+ ffmpeg) to support YouTube, Instagram, Facebook, X/Twitter, TikTok.
Frontend is plain HTML/CSS/JS; this is just the engine.
"""

import os
import re
import shutil
import uuid
import threading
import traceback

from flask import Flask, request, jsonify, send_from_directory, abort
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")

# In-memory job store: job_id -> dict(status, percent, filename, error, title)
JOBS = {}
JOBS_LOCK = threading.Lock()

SUPPORTED_HOSTS = [
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "tiktok.com",
]


def is_supported_url(url: str) -> bool:
    return any(host in url for host in SUPPORTED_HOSTS)


def safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\-. ]", "_", name).strip()
    return name[:150] if len(name) > 150 else name


def make_progress_hook(job_id):
    def hook(d):
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    job["percent"] = round(downloaded / total * 100, 1)
                job["status"] = "downloading"
            elif d["status"] == "finished":
                job["status"] = "processing"  # ffmpeg merge/convert step
    return hook


def run_download(job_id, url, media_format, quality):
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "progress_hooks": [make_progress_hook(job_id)],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # --- speed tuning ---
        "concurrent_fragment_downloads": 8,  # pull multiple chunks of a video at once
        "http_chunk_size": 10 * 1024 * 1024,  # 10MB chunks, helps throttled connections
    }

    # If aria2c is installed, hand off downloading to it — it does
    # multi-connection downloads per file and is noticeably faster than
    # yt-dlp's built-in downloader on most connections.
    if shutil.which("aria2c"):
        ydl_opts["external_downloader"] = "aria2c"
        ydl_opts["external_downloader_args"] = {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M"]
        }

    if media_format == "mp3":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,  # e.g. "320", "192", "128"
        }]
        # let ffmpeg use multiple threads for the audio encode
        ydl_opts["postprocessor_args"] = {"ffmpeg": ["-threads", "0"]}
    else:  # mp4
        height = quality.rstrip("p")  # "1080p" -> "1080"
        ydl_opts["format"] = (
            f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={height}][ext=mp4]/best"
        )
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", job_id)

        # Find the produced file (extension may vary slightly before postprocessing)
        produced = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(job_id):
                produced = f
                break

        if not produced:
            raise FileNotFoundError("Output file not found after download")

        final_name = f"{safe_filename(title)}.{media_format}"
        final_path = os.path.join(DOWNLOAD_DIR, final_name)

        # avoid collisions
        counter = 1
        base_final_name = final_name
        while os.path.exists(final_path) and produced != final_name:
            final_name = f"{safe_filename(title)}_{counter}.{media_format}"
            final_path = os.path.join(DOWNLOAD_DIR, final_name)
            counter += 1

        os.rename(os.path.join(DOWNLOAD_DIR, produced), final_path)

        with JOBS_LOCK:
            JOBS[job_id].update(
                status="done", percent=100, filename=final_name, title=title
            )

    except Exception as e:
        traceback.print_exc()
        with JOBS_LOCK:
            JOBS[job_id].update(status="error", error=str(e))


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    media_format = data.get("format", "mp3")
    quality = data.get("quality", "320" if media_format == "mp3" else "1080p")

    if not url:
        return jsonify(error="No URL provided"), 400
    if not is_supported_url(url):
        return jsonify(error="Unsupported URL. Use a YouTube, Instagram, Facebook, X, or TikTok link."), 400
    if media_format not in ("mp3", "mp4"):
        return jsonify(error="format must be mp3 or mp4"), 400

    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "queued", "percent": 0, "filename": None, "error": None}

    t = threading.Thread(target=run_download, args=(job_id, url, media_format, quality), daemon=True)
    t.start()

    return jsonify(job_id=job_id)


@app.route("/api/progress/<job_id>")
def progress(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify(error="Unknown job"), 404
        return jsonify(**job)


@app.route("/api/file/<job_id>")
def get_file(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job or job.get("status") != "done":
            abort(404)
        filename = job["filename"]
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    # bind to 0.0.0.0 if you want it reachable from your phone on the same network
    app.run(host="127.0.0.1", port=5000, debug=True)
