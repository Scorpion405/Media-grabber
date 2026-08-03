"""
Local media downloader — backend
Wraps yt-dlp (+ ffmpeg) to support YouTube (incl. playlists), Instagram,
Facebook, X/Twitter, TikTok, SoundCloud, Vimeo, Twitch, Reddit, Dailymotion,
Bandcamp, Tumblr, and Bilibili.
Handles video (MP4, with optional embedded subtitles), audio (MP3, with
ID3 tags + embedded cover art), and image posts/carousels (JPG or ZIP).
Frontend is plain HTML/CSS/JS; this is just the engine.
"""

import os
import re
import shutil
import uuid
import threading
import traceback
import zipfile

import requests
from flask import Flask, request, jsonify, send_from_directory, abort
import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")

# In-memory job store: job_id -> dict(status, percent, filename, error, title)
JOBS = {}
JOBS_LOCK = threading.Lock()

# job_ids the user has asked to cancel — checked inside the progress hook
CANCELLED_JOBS = set()
CANCELLED_LOCK = threading.Lock()

# Caps how many videos/tracks can be actively downloading at once (e.g. when
# several playlist/batch items kick off together). Each one still uses
# multiple parallel connections internally (see build_ydl_opts) — this is
# the outer layer, like FDM's "N simultaneous downloads" queue limit.
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)

SUPPORTED_HOSTS = [
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "tiktok.com",
    "soundcloud.com",
    "vimeo.com",
    "twitch.tv",
    "reddit.com", "redd.it",
    "dailymotion.com",
    "bandcamp.com",
    "tumblr.com",
    "bilibili.com",
]

IMAGE_EXTS = ("jpg", "jpeg", "png", "webp")


class JobCancelled(Exception):
    pass


def request_cancel(job_id):
    with CANCELLED_LOCK:
        CANCELLED_JOBS.add(job_id)


def is_cancelled(job_id):
    with CANCELLED_LOCK:
        return job_id in CANCELLED_JOBS


def clear_cancel_flag(job_id):
    with CANCELLED_LOCK:
        CANCELLED_JOBS.discard(job_id)


def is_supported_url(url: str) -> bool:
    return any(host in url for host in SUPPORTED_HOSTS)


def is_youtube_playlist(url: str) -> bool:
    is_youtube = "youtube.com" in url or "youtu.be" in url
    looks_like_playlist = "list=" in url or "/playlist" in url
    return is_youtube and looks_like_playlist


def safe_filename(name: str) -> str:
    # Only strip characters that are actually illegal in filenames
    # (Windows' rule set is the strictest, so it covers Mac/Linux too) —
    # titles very commonly contain (), [], ', &, which shouldn't be mangled.
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(".")
    return name[:150] if len(name) > 150 else name


def dedupe_path(path, current_path):
    """If `path` already exists (and isn't the file we're about to move
    there), append a counter until it's free."""
    if not os.path.exists(path) or path == current_path:
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    candidate = f"{base}_{counter}{ext}"
    while os.path.exists(candidate):
        counter += 1
        candidate = f"{base}_{counter}{ext}"
    return candidate


def make_progress_hook(job_id):
    def hook(d):
        if is_cancelled(job_id):
            raise JobCancelled("Cancelled by user")
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    job["percent"] = round(downloaded / total * 100, 1)
                    job["total_bytes"] = total
                job["downloaded_bytes"] = downloaded
                job["status"] = "downloading"
            elif d["status"] == "finished":
                job["status"] = "processing"  # ffmpeg merge/convert step
    return hook


def build_ydl_opts(outtmpl, media_format, quality, progress_hook=None,
                    embed_subs=False, cookies_browser=None):
    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # --- speed tuning ---
        # Splits a single file into multiple pieces pulled over parallel
        # connections at once — the same trick FDM/aria2c use for
        # segmented downloading.
        "concurrent_fragment_downloads": 16,
        "http_chunk_size": 5 * 1024 * 1024,
    }
    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]
    if cookies_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_browser,)

    # If aria2c is installed, hand off downloading to it — multi-connection
    # downloads per file, noticeably faster than yt-dlp's built-in downloader.
    if shutil.which("aria2c"):
        ydl_opts["external_downloader"] = "aria2c"
        ydl_opts["external_downloader_args"] = {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M"]
        }

    if media_format == "mp3":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["writethumbnail"] = True
        ydl_opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality},
            {"key": "FFmpegMetadata"},   # embeds title/artist/etc as ID3 tags
            {"key": "EmbedThumbnail"},   # embeds cover art from the thumbnail
        ]
        ydl_opts["postprocessor_args"] = {"ffmpeg": ["-threads", "0"]}
    else:  # mp4
        height = quality.rstrip("p")
        ydl_opts["format"] = (
            f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={height}][ext=mp4]/best"
        )
        ydl_opts["merge_output_format"] = "mp4"
        if embed_subs:
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True  # fall back to auto captions
            ydl_opts["subtitleslangs"] = ["en"]
            ydl_opts["embedsubtitles"] = True

    return ydl_opts


def download_media_file(tmp_id, url, media_format, quality, progress_hook=None,
                         embed_subs=False, cookies_browser=None):
    """Downloads a single video/audio item via yt-dlp. Returns
    (final_path, title). Raises on failure or cancellation."""
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{tmp_id}.%(ext)s")
    ydl_opts = build_ydl_opts(outtmpl, media_format, quality, progress_hook,
                               embed_subs, cookies_browser)

    with DOWNLOAD_SEMAPHORE:
        if is_cancelled(tmp_id):
            raise JobCancelled("Cancelled by user")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", tmp_id)

    # prefer a file matching the target extension (avoids grabbing a
    # leftover thumbnail/subtitle temp file instead of the real output)
    produced = None
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(tmp_id) and f.endswith(f".{media_format}"):
            produced = f
            break
    if not produced:
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(tmp_id):
                produced = f
                break
    if not produced:
        raise FileNotFoundError("Output file not found after download")

    final_name = f"{safe_filename(title)}.{media_format}"
    final_path = os.path.join(DOWNLOAD_DIR, final_name)
    final_path = dedupe_path(final_path, os.path.join(DOWNLOAD_DIR, produced))
    os.rename(os.path.join(DOWNLOAD_DIR, produced), final_path)

    # clean up any orphaned temp files (leftover thumbnails, partial subs)
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(tmp_id):
            try:
                os.remove(os.path.join(DOWNLOAD_DIR, f))
            except OSError:
                pass

    return final_path, title


def cleanup_job_files(job_id):
    """Removes any leftover files in DOWNLOAD_DIR that start with this
    job's id — partial .part downloads, orphaned thumbnails/subs, etc.
    Safe to call after cancellation or an error, since on the success
    path the real output has already been renamed away from this prefix."""
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(job_id):
            try:
                os.remove(os.path.join(DOWNLOAD_DIR, f))
            except OSError:
                pass


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def friendly_error(e: Exception) -> str:
    msg = ANSI_ESCAPE_RE.sub("", str(e)).strip()
    if "no video formats" in msg.lower():
        return "This looks like a photo post, not a video — try the \u201cImage / Post\u201d option instead."
    return msg


def run_download(job_id, url, media_format, quality, embed_subs=False, cookies_browser=None):
    if media_format == "image":
        run_image_download(job_id, url, cookies_browser)
    else:
        run_video_download(job_id, url, media_format, quality, embed_subs, cookies_browser)


def run_video_download(job_id, url, media_format, quality, embed_subs=False, cookies_browser=None):
    try:
        hook = make_progress_hook(job_id)
        final_path, title = download_media_file(
            job_id, url, media_format, quality, progress_hook=hook,
            embed_subs=embed_subs, cookies_browser=cookies_browser,
        )
        size_bytes = os.path.getsize(final_path) if os.path.exists(final_path) else None
        with JOBS_LOCK:
            JOBS[job_id].update(
                status="done", percent=100, filename=os.path.basename(final_path),
                title=title, size_bytes=size_bytes,
            )
    except JobCancelled:
        cleanup_job_files(job_id)
        with JOBS_LOCK:
            JOBS[job_id].update(status="cancelled", error="Cancelled")
    except Exception as e:
        cleanup_job_files(job_id)
        traceback.print_exc()
        with JOBS_LOCK:
            JOBS[job_id].update(status="error", error=friendly_error(e))
    finally:
        clear_cancel_flag(job_id)


def collect_image_urls(info):
    """Pull direct image URLs out of a yt-dlp info dict — handles a single
    photo post and multi-image carousels (Instagram, X, etc.)."""
    entries = info.get("entries") if info.get("_type") == "playlist" else [info]
    image_urls = []
    for entry in entries:
        if not entry:
            continue
        candidate = None
        if entry.get("ext") in IMAGE_EXTS and entry.get("url"):
            candidate = entry["url"]
        else:
            for f in entry.get("formats") or []:
                if f.get("ext") in IMAGE_EXTS and f.get("url"):
                    candidate = f["url"]
            if not candidate and entry.get("thumbnail"):
                candidate = entry["thumbnail"]
        if candidate:
            image_urls.append(candidate)
    return image_urls


def run_image_download(job_id, url, cookies_browser=None):
    try:
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "downloading"

        probe_opts = {
            "quiet": True, "no_warnings": True, "noplaylist": False,
            # Some extractors (Instagram in particular) hard-fail extraction
            # itself for a single (non-carousel) photo post with "there is
            # no video in this post" — even though we only want the image
            # and never touch video. This downgrades that to a warning so
            # extraction still completes; the actual photo URL ends up in
            # info['thumbnail'] afterward, which collect_image_urls() reads.
            "ignore_no_formats_error": True,
        }
        if cookies_browser:
            probe_opts["cookiesfrombrowser"] = (cookies_browser,)
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or info.get("id") or job_id
        image_urls = collect_image_urls(info)

        if not image_urls:
            raise ValueError("No images found in this post — it may be video-only.")

        saved_paths = []
        total = len(image_urls)
        for i, img_url in enumerate(image_urls):
            if is_cancelled(job_id):
                raise JobCancelled("Cancelled by user")

            ext = img_url.split("?")[0].rsplit(".", 1)[-1].lower()
            if ext not in IMAGE_EXTS:
                ext = "jpg"
            local_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_{i}.{ext}")

            with requests.get(img_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        f.write(chunk)

            saved_paths.append(local_path)
            with JOBS_LOCK:
                JOBS[job_id]["percent"] = round((i + 1) / total * 100, 1)

        with JOBS_LOCK:
            JOBS[job_id]["status"] = "processing"

        if len(saved_paths) == 1:
            ext = saved_paths[0].rsplit(".", 1)[-1]
            final_name = safe_filename(f"{title}.{ext}")
            final_path = dedupe_path(os.path.join(DOWNLOAD_DIR, final_name), saved_paths[0])
            os.rename(saved_paths[0], final_path)
        else:
            final_name = safe_filename(f"{title}.zip")
            final_path = dedupe_path(os.path.join(DOWNLOAD_DIR, final_name), None)
            with zipfile.ZipFile(final_path, "w") as zf:
                for p in saved_paths:
                    zf.write(p, arcname=os.path.basename(p))
            for p in saved_paths:
                os.remove(p)

        size_bytes = os.path.getsize(final_path) if os.path.exists(final_path) else None
        with JOBS_LOCK:
            JOBS[job_id].update(
                status="done", percent=100,
                filename=os.path.basename(final_path), title=title, size_bytes=size_bytes,
            )

    except JobCancelled:
        cleanup_job_files(job_id)
        with JOBS_LOCK:
            JOBS[job_id].update(status="cancelled", error="Cancelled")
    except Exception as e:
        cleanup_job_files(job_id)
        traceback.print_exc()
        with JOBS_LOCK:
            JOBS[job_id].update(status="error", error=friendly_error(e))
    finally:
        clear_cancel_flag(job_id)


def estimate_source_size(info):
    """Best-effort size estimate from yt-dlp's metadata — this reflects the
    source stream(s), not the final converted file (MP3 conversion in
    particular can end up smaller or larger), so it's shown as approximate."""
    size = info.get("filesize") or info.get("filesize_approx")
    if size:
        return size

    total = 0
    found = False
    for f in info.get("requested_formats") or []:
        s = f.get("filesize") or f.get("filesize_approx")
        if s:
            total += s
            found = True
    if found:
        return total

    candidates = [
        f.get("filesize") or f.get("filesize_approx")
        for f in (info.get("formats") or [])
        if f.get("filesize") or f.get("filesize_approx")
    ]
    return max(candidates) if candidates else None


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/preview", methods=["POST"])
def preview():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    cookies_browser = data.get("cookies_browser") or None

    if not url:
        return jsonify(error="No URL provided"), 400
    if not is_supported_url(url):
        return jsonify(error="Unsupported URL"), 400
    if is_youtube_playlist(url):
        return jsonify(error="This is a playlist — use the playlist view instead."), 400

    try:
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "ignore_no_formats_error": True}
        if cookies_browser:
            opts["cookiesfrombrowser"] = (cookies_browser,)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or info.get("id") or "Untitled"
        thumbnail = info.get("thumbnail")
        duration = info.get("duration")
        uploader = info.get("uploader") or info.get("channel") or info.get("uploader_id")
        filesize = estimate_source_size(info)

        return jsonify(
            title=title, thumbnail=thumbnail, duration=duration,
            uploader=uploader, filesize=filesize,
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify(error=friendly_error(e)), 500


@app.route("/api/playlist/info", methods=["POST"])
def playlist_info():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    cookies_browser = data.get("cookies_browser") or None

    if not url:
        return jsonify(error="No URL provided"), 400
    if not is_youtube_playlist(url):
        return jsonify(error="That doesn't look like a playlist URL."), 400

    try:
        probe_opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}
        if cookies_browser:
            probe_opts["cookiesfrombrowser"] = (cookies_browser,)
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = [e for e in (info.get("entries") or []) if e]
        items = []
        for e in entries:
            vid_id = e.get("id")
            vid_url = e.get("url") or (
                f"https://www.youtube.com/watch?v={vid_id}" if vid_id else None
            )
            if not vid_url:
                continue
            items.append({
                "id": vid_id,
                "title": e.get("title") or vid_id,
                "url": vid_url,
                "duration": e.get("duration"),
            })

        if not items:
            return jsonify(error="No videos found in this playlist."), 400

        return jsonify(playlist_title=info.get("title") or "Playlist", items=items)

    except Exception as e:
        traceback.print_exc()
        return jsonify(error=friendly_error(e)), 500


@app.route("/api/download", methods=["POST"])
def start_download():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    media_format = data.get("format", "mp3")
    quality = data.get("quality", "320" if media_format == "mp3" else "1080p")
    embed_subs = bool(data.get("embed_subs")) and media_format == "mp4"
    cookies_browser = data.get("cookies_browser") or None

    if not url:
        return jsonify(error="No URL provided"), 400
    if not is_supported_url(url):
        return jsonify(error="Unsupported URL."), 400
    if media_format not in ("mp3", "mp4", "image"):
        return jsonify(error="format must be mp3, mp4, or image"), 400
    if is_youtube_playlist(url):
        return jsonify(error="That's a playlist link — pick individual videos from the playlist list instead."), 400

    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "queued", "percent": 0, "filename": None, "error": None}

    t = threading.Thread(
        target=run_download,
        args=(job_id, url, media_format, quality, embed_subs, cookies_browser),
        daemon=True,
    )
    t.start()

    return jsonify(job_id=job_id)


@app.route("/api/cancel/<job_id>", methods=["POST"])
def cancel_job(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify(error="Unknown job"), 404
    request_cancel(job_id)
    return jsonify(ok=True)


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


@app.route("/api/downloads/<path:filename>")
def get_downloaded_file(filename):
    """Serves any file already sitting in the downloads folder by name —
    used for history re-download, which survives server restarts (job IDs
    from a previous run session don't)."""
    safe_name = os.path.basename(filename)  # block path traversal
    file_path = os.path.join(DOWNLOAD_DIR, safe_name)
    if not os.path.exists(file_path):
        abort(404)
    return send_from_directory(DOWNLOAD_DIR, safe_name, as_attachment=True)


if __name__ == "__main__":
    # threaded=True lets the dev server handle multiple requests at once —
    # without it, polling several playlist/batch items' progress (or loading
    # a new playlist while downloads are running) can queue up and stall.
    # bind to 0.0.0.0 if you want it reachable from your phone on the same network
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
