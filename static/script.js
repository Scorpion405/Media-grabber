// ---------- DOM refs ----------

const form = document.getElementById("download-form");
const submitBtn = document.getElementById("submit-btn");
const formatSelect = document.getElementById("format");
const qualitySelect = document.getElementById("quality");
const qualityField = document.getElementById("quality-field");
const urlInput = document.getElementById("url");
const subsRow = document.getElementById("subs-row");
const embedSubsCheckbox = document.getElementById("embed-subs");
const useCookiesCheckbox = document.getElementById("use-cookies");
const cookieBrowserSelect = document.getElementById("cookie-browser");

const batchToggleBtn = document.getElementById("batch-toggle-btn");
const batchTextarea = document.getElementById("batch-urls");

const historyToggleBtn = document.getElementById("history-toggle-btn");
const historyPanel = document.getElementById("history-panel");
const historyList = document.getElementById("history-list");
const clearHistoryBtn = document.getElementById("clear-history-btn");

// single-item flow elements
const statusArea = document.getElementById("status-area");
const statusText = document.getElementById("status-text");
const progressFill = document.getElementById("progress-fill");
const cancelBtn = document.getElementById("cancel-btn");
const resultArea = document.getElementById("result-area");
const resultTitle = document.getElementById("result-title");
const resultMeta = document.getElementById("result-meta");
const resultLink = document.getElementById("result-link");
const errorText = document.getElementById("error-text");

// preview elements
const previewArea = document.getElementById("preview-area");
const previewThumb = document.getElementById("preview-thumb");
const previewTitle = document.getElementById("preview-title");
const previewMeta = document.getElementById("preview-meta");
const previewLoading = document.getElementById("preview-loading");

// playlist flow elements
const playlistPanel = document.getElementById("playlist-panel");
const playlistLoading = document.getElementById("playlist-loading");
const playlistCount = document.getElementById("playlist-count");
const playlistItemsEl = document.getElementById("playlist-items");
const selectAllBtn = document.getElementById("select-all-btn");
const selectNoneBtn = document.getElementById("select-none-btn");
const playlistDownloads = document.getElementById("playlist-downloads");

const MP3_QUALITIES = [
  { value: "320", label: "320 kbps" },
  { value: "192", label: "192 kbps" },
  { value: "128", label: "128 kbps" },
];

const MP4_QUALITIES = [
  { value: "2160p", label: "4K (2160p)" },
  { value: "1440p", label: "1440p" },
  { value: "1080p", label: "1080p" },
  { value: "720p", label: "720p" },
  { value: "480p", label: "480p" },
];

let playlistItems = []; // [{id, title, url, checked}]
let inputMode = "single"; // "single" | "playlist" | "batch"
let debounceTimer = null;
let playlistLoadToken = 0;
let previewLoadToken = 0;
let currentSingleJobId = null;

// ---------- Small utilities ----------

function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return "";
  const units = ["B", "KB", "MB", "GB"];
  let val = bytes;
  let i = 0;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(val < 10 && i > 0 ? 1 : 0)} ${units[i]}`;
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function isYouTubePlaylist(url) {
  const isYouTube = url.includes("youtube.com") || url.includes("youtu.be");
  const looksLikePlaylist = url.includes("list=") || url.includes("/playlist");
  return isYouTube && looksLikePlaylist;
}

function currentCookiesBrowser() {
  return useCookiesCheckbox.checked ? cookieBrowserSelect.value : null;
}

// ---------- Remembered format/quality ----------

function loadRememberedChoices() {
  const savedFormat = localStorage.getItem("mg_format");
  if (savedFormat) formatSelect.value = savedFormat;
  refreshQualityOptions();
  const savedQuality = localStorage.getItem("mg_quality_" + formatSelect.value);
  if (savedQuality) qualitySelect.value = savedQuality;
}

formatSelect.addEventListener("change", () => {
  localStorage.setItem("mg_format", formatSelect.value);
  refreshQualityOptions();
  subsRow.classList.toggle("hidden", formatSelect.value !== "mp4");
  const savedQuality = localStorage.getItem("mg_quality_" + formatSelect.value);
  if (savedQuality) qualitySelect.value = savedQuality;
  syncSegmentedUI();
});

qualitySelect.addEventListener("change", () => {
  localStorage.setItem("mg_quality_" + formatSelect.value, qualitySelect.value);
});

function refreshQualityOptions() {
  if (formatSelect.value === "image") {
    qualityField.classList.add("hidden");
    subsRow.classList.add("hidden");
    return;
  }
  qualityField.classList.remove("hidden");
  subsRow.classList.toggle("hidden", formatSelect.value !== "mp4");
  const opts = formatSelect.value === "mp3" ? MP3_QUALITIES : MP4_QUALITIES;
  qualitySelect.innerHTML = opts
    .map((o) => `<option value="${o.value}">${o.label}</option>`)
    .join("");
}

// ---------- Segmented format control (MP3 / MP4 / Image buttons) ----------
// The visible buttons drive the hidden <select id="format">, which stays
// the single source of truth everything else (quality options, subtitles
// row, submit logic) already reads from.

const segmentButtons = document.querySelectorAll(".segment");

function syncSegmentedUI() {
  segmentButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.value === formatSelect.value);
  });
}

segmentButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (formatSelect.value === btn.dataset.value) return;
    formatSelect.value = btn.dataset.value;
    formatSelect.dispatchEvent(new Event("change"));
  });
});

// ---------- Activity indicator (header dot) ----------
// Uses a counter rather than a plain flag because playlist/batch rows
// download concurrently — the dot should stay lit until the LAST one finishes.

const signalDot = document.getElementById("signal-dot");
let activeJobCount = 0;

function setActivity(isActive) {
  if (signalDot) signalDot.classList.toggle("active", isActive);
}

function beginActivity() {
  activeJobCount++;
  setActivity(true);
}

function endActivity() {
  activeJobCount = Math.max(0, activeJobCount - 1);
  if (activeJobCount === 0) setActivity(false);
}

loadRememberedChoices();
syncSegmentedUI();
subsRow.classList.toggle("hidden", formatSelect.value !== "mp4");

// ---------- Cookie login toggle ----------

useCookiesCheckbox.addEventListener("change", () => {
  cookieBrowserSelect.classList.toggle("hidden", !useCookiesCheckbox.checked);
});

// ---------- Batch paste toggle ----------

batchToggleBtn.addEventListener("click", () => {
  const goingToBatch = inputMode !== "batch";
  inputMode = goingToBatch ? "batch" : "single";
  urlInput.classList.toggle("hidden", goingToBatch);
  batchTextarea.classList.toggle("hidden", !goingToBatch);
  batchToggleBtn.textContent = goingToBatch ? "[ single link instead ]" : "[ multiple links ]";
  resetPreview();
  resetPlaylistUI();
});

// ---------- Reset helpers ----------

function resetSingleUI() {
  statusArea.classList.add("hidden");
  resultArea.classList.add("hidden");
  errorText.classList.add("hidden");
  progressFill.style.width = "0%";
}

function resetPlaylistUI() {
  playlistPanel.classList.add("hidden");
  playlistDownloads.classList.add("hidden");
  playlistDownloads.innerHTML = "";
  playlistLoading.classList.add("hidden");
  playlistItems = [];
  if (inputMode === "playlist") inputMode = "single";
}

function resetPreview() {
  previewArea.classList.add("hidden");
  previewLoading.classList.add("hidden");
  previewThumb.classList.add("hidden");
  previewThumb.src = "";
  previewTitle.textContent = "";
  previewMeta.textContent = "";
}

function showError(msg) {
  errorText.textContent = msg;
  errorText.classList.remove("hidden");
  statusArea.classList.add("hidden");
  submitBtn.disabled = false;
  submitBtn.textContent = "Download";
}

// ---------- Single-item preview ----------

async function loadPreview(url) {
  const myToken = ++previewLoadToken;
  resetPreview();
  previewLoading.classList.remove("hidden");

  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, cookies_browser: currentCookiesBrowser() }),
    });
    const data = await res.json();
    if (myToken !== previewLoadToken) return;

    previewLoading.classList.add("hidden");
    if (data.error) return; // fail silently — this is a nice-to-have

    previewTitle.textContent = data.title;
    const metaParts = [];
    if (data.uploader) metaParts.push(data.uploader);
    if (data.duration) metaParts.push(formatDuration(data.duration));
    if (data.filesize) metaParts.push(`~${formatBytes(data.filesize)}`);
    previewMeta.textContent = metaParts.join(" · ");

    if (data.thumbnail) {
      previewThumb.src = data.thumbnail;
      previewThumb.classList.remove("hidden");
    }
    previewArea.classList.remove("hidden");
  } catch (err) {
    if (myToken !== previewLoadToken) return;
    previewLoading.classList.add("hidden");
  }
}

// ---------- Playlist checklist ----------

function renderPlaylistItems(title) {
  playlistCount.textContent = `${title} — ${playlistItems.length} video${playlistItems.length === 1 ? "" : "s"}`;
  playlistItemsEl.innerHTML = playlistItems
    .map(
      (item, i) => `
      <label class="playlist-item">
        <input type="checkbox" data-index="${i}" ${item.checked ? "checked" : ""}>
        <span>${item.title}</span>
      </label>`
    )
    .join("");

  playlistItemsEl.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      playlistItems[idx].checked = e.target.checked;
    });
  });

  playlistPanel.classList.remove("hidden");
}

selectAllBtn.addEventListener("click", () => {
  playlistItems.forEach((it) => (it.checked = true));
  playlistItemsEl.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = true));
});

selectNoneBtn.addEventListener("click", () => {
  playlistItems.forEach((it) => (it.checked = false));
  playlistItemsEl.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = false));
});

async function loadPlaylist(url, attempt = 1) {
  const token = ++playlistLoadToken;
  resetPlaylistUI();
  inputMode = "playlist";
  playlistLoading.classList.remove("hidden");

  try {
    const res = await fetch("/api/playlist/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, cookies_browser: currentCookiesBrowser() }),
    });
    const data = await res.json();
    if (token !== playlistLoadToken) return;

    playlistLoading.classList.add("hidden");

    if (data.error) {
      if (attempt < 2) {
        setTimeout(() => loadPlaylist(url, attempt + 1), 1000);
        return;
      }
      showError(data.error);
      inputMode = "single";
      return;
    }

    playlistItems = data.items.map((it) => ({ ...it, checked: true }));
    renderPlaylistItems(data.playlist_title);
  } catch (err) {
    if (token !== playlistLoadToken) return;
    if (attempt < 2) {
      setTimeout(() => loadPlaylist(url, attempt + 1), 1000);
      return;
    }
    playlistLoading.classList.add("hidden");
    showError("Could not load playlist. Is app.py running?");
    inputMode = "single";
  }
}

urlInput.addEventListener("input", () => {
  const val = urlInput.value.trim();
  clearTimeout(debounceTimer);

  if (isYouTubePlaylist(val)) {
    previewLoadToken++;
    resetPreview();
    debounceTimer = setTimeout(() => loadPlaylist(val), 600);
  } else {
    playlistLoadToken++;
    resetPlaylistUI();
    if (val) {
      debounceTimer = setTimeout(() => loadPreview(val), 500);
    } else {
      previewLoadToken++;
      resetPreview();
    }
  }
});

// ---------- Generic job polling ----------

function pollJob(jobId, { onProgress, onDone, onError }) {
  return new Promise((resolve) => {
    function tick() {
      fetch(`/api/progress/${jobId}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.error && data.status !== "cancelled") {
            onError(data.error);
            resolve();
            return;
          }
          if (data.status === "downloading") {
            let text = `Downloading… ${data.percent ?? 0}%`;
            if (data.total_bytes) {
              text += ` (${formatBytes(data.downloaded_bytes || 0)} / ${formatBytes(data.total_bytes)})`;
            }
            onProgress(data.percent ?? 0, text);
            setTimeout(tick, 1000);
          } else if (data.status === "processing") {
            onProgress(100, "Converting…");
            setTimeout(tick, 1000);
          } else if (data.status === "queued") {
            onProgress(0, "Starting…");
            setTimeout(tick, 1000);
          } else if (data.status === "done") {
            onDone(data);
            resolve();
          } else if (data.status === "cancelled") {
            onError("Cancelled");
            resolve();
          } else if (data.status === "error") {
            onError(data.error || "Something went wrong.");
            resolve();
          } else {
            setTimeout(tick, 1000);
          }
        })
        .catch(() => {
          onError("Lost connection to local server.");
          resolve();
        });
    }
    tick();
  });
}

function cancelJob(jobId) {
  if (!jobId) return;
  fetch(`/api/cancel/${jobId}`, { method: "POST" }).catch(() => {});
}

// ---------- Download history (localStorage) ----------

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem("mg_history") || "[]");
  } catch {
    return [];
  }
}

function saveToHistory(entry) {
  const history = loadHistory();
  history.unshift(entry);
  localStorage.setItem("mg_history", JSON.stringify(history.slice(0, 50)));
}

function renderHistory() {
  const history = loadHistory();
  if (history.length === 0) {
    historyList.innerHTML = `<p class="hint">No downloads yet.</p>`;
    return;
  }
  historyList.innerHTML = history
    .map(
      (h) => `
      <div class="history-item">
        <span class="history-item-title">${h.title}</span>
        <span class="history-item-meta">${h.size_bytes != null ? formatBytes(h.size_bytes) : ""}</span>
        <a class="link-btn" href="/api/downloads/${encodeURIComponent(h.filename)}" download>Save</a>
      </div>`
    )
    .join("");
}

const historyBackdrop = document.getElementById("history-backdrop");
const historyCloseBtn = document.getElementById("history-close-btn");

function openHistoryDrawer() {
  historyPanel.classList.remove("hidden");
  historyBackdrop.classList.remove("hidden");
  // force a reflow so the removed "hidden" (display:none) is applied
  // before adding "open" — otherwise the slide-in transition won't play
  void historyPanel.offsetWidth;
  historyPanel.classList.add("open");
  historyBackdrop.classList.add("open");
  renderHistory();
}

function closeHistoryDrawer() {
  historyPanel.classList.remove("open");
  historyBackdrop.classList.remove("open");
}

historyToggleBtn.addEventListener("click", openHistoryDrawer);
historyCloseBtn.addEventListener("click", closeHistoryDrawer);
historyBackdrop.addEventListener("click", closeHistoryDrawer);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeHistoryDrawer();
});

clearHistoryBtn.addEventListener("click", () => {
  localStorage.removeItem("mg_history");
  renderHistory();
});

// ---------- Auto-save trigger ----------

function triggerAutoSave(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ---------- Single-item download ----------

async function startSingleDownload(url, format, quality) {
  resetSingleUI();
  submitBtn.disabled = true;
  submitBtn.textContent = "Working…";
  statusArea.classList.remove("hidden");
  statusText.textContent = "Starting…";
  cancelBtn.classList.remove("hidden");
  beginActivity();

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url, format, quality,
        embed_subs: embedSubsCheckbox.checked,
        cookies_browser: currentCookiesBrowser(),
      }),
    });
    const data = await res.json();
    if (data.error) {
      endActivity();
      showError(data.error);
      return;
    }

    currentSingleJobId = data.job_id;

    pollJob(data.job_id, {
      onProgress: (pct, text) => {
        statusText.textContent = text;
        progressFill.style.width = `${pct}%`;
      },
      onDone: (doneData) => {
        statusArea.classList.add("hidden");
        resultArea.classList.remove("hidden");
        resultTitle.textContent = doneData.title || "Done";
        resultMeta.textContent = doneData.size_bytes != null ? formatBytes(doneData.size_bytes) : "";
        const fileUrl = `/api/file/${data.job_id}`;
        resultLink.href = fileUrl;
        resultLink.setAttribute("download", doneData.filename || "");
        submitBtn.disabled = false;
        submitBtn.textContent = "Download";
        endActivity();
        triggerAutoSave(fileUrl, doneData.filename);
        saveToHistory({
          title: doneData.title || "Untitled",
          filename: doneData.filename,
          size_bytes: doneData.size_bytes,
        });
      },
      onError: (msg) => {
        endActivity();
        showError(msg);
      },
    });
  } catch (err) {
    endActivity();
    showError("Could not reach local server. Is app.py running?");
  }
}

cancelBtn.addEventListener("click", () => cancelJob(currentSingleJobId));

// ---------- Playlist / batch: one row per item ----------

function createDownloadRow(title) {
  const row = document.createElement("div");
  row.className = "download-row";
  row.innerHTML = `
    <p class="download-row-title">${title}</p>
    <p class="download-row-status">Starting…</p>
    <div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div>
    <div class="download-row-actions">
      <a class="button-link hidden" href="#" download>Save</a>
      <button type="button" class="link-btn row-cancel-btn">Cancel</button>
    </div>
  `;
  return {
    el: row,
    titleEl: row.querySelector(".download-row-title"),
    statusEl: row.querySelector(".download-row-status"),
    barEl: row.querySelector(".progress-fill"),
    linkEl: row.querySelector(".button-link"),
    cancelBtnEl: row.querySelector(".row-cancel-btn"),
  };
}

async function startPlaylistDownload(items, format, quality) {
  playlistDownloads.innerHTML = "";
  playlistDownloads.classList.remove("hidden");
  const list = document.createElement("div");
  list.className = "playlist-downloads-list";
  playlistDownloads.appendChild(list);

  submitBtn.disabled = true;
  submitBtn.textContent = "Working…";

  for (const item of items) {
    const row = createDownloadRow(item.title);
    list.appendChild(row.el);

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: item.url, format, quality,
          embed_subs: embedSubsCheckbox.checked,
          cookies_browser: currentCookiesBrowser(),
        }),
      });
      const data = await res.json();

      if (data.error) {
        row.el.classList.add("errored");
        row.statusEl.textContent = data.error;
        row.cancelBtnEl.classList.add("hidden");
        continue;
      }

      beginActivity(); // this row now has a real job running

      row.cancelBtnEl.addEventListener("click", () => {
        cancelJob(data.job_id);
        row.cancelBtnEl.classList.add("hidden");
      });

      pollJob(data.job_id, {
        onProgress: (pct, text) => {
          row.statusEl.textContent = text;
          row.barEl.style.width = `${pct}%`;
        },
        onDone: (doneData) => {
          row.statusEl.textContent = doneData.size_bytes != null ? `Done · ${formatBytes(doneData.size_bytes)}` : "Done";
          row.barEl.style.width = "100%";
          if (doneData.title) row.titleEl.textContent = doneData.title;
          const fileUrl = `/api/file/${data.job_id}`;
          row.linkEl.href = fileUrl;
          row.linkEl.setAttribute("download", doneData.filename || "");
          row.linkEl.classList.remove("hidden");
          row.cancelBtnEl.classList.add("hidden");
          endActivity();
          triggerAutoSave(fileUrl, doneData.filename);
          saveToHistory({
            title: doneData.title || item.title,
            filename: doneData.filename,
            size_bytes: doneData.size_bytes,
          });
        },
        onError: (msg) => {
          row.el.classList.add(msg === "Cancelled" ? "cancelled" : "errored");
          row.statusEl.textContent = msg;
          row.cancelBtnEl.classList.add("hidden");
          endActivity();
        },
      });
    } catch (err) {
      row.el.classList.add("errored");
      row.statusEl.textContent = "Could not reach local server.";
      row.cancelBtnEl.classList.add("hidden");
    }
  }

  submitBtn.disabled = false;
  submitBtn.textContent = "Download";
}

// ---------- Form submit ----------

form.addEventListener("submit", (e) => {
  e.preventDefault();
  resetSingleUI();
  errorText.classList.add("hidden");

  const format = formatSelect.value;
  const quality = qualitySelect.value;

  if (inputMode === "playlist" && playlistItems.length > 0) {
    const selected = playlistItems.filter((it) => it.checked);
    if (selected.length === 0) {
      showError("Select at least one video.");
      return;
    }
    startPlaylistDownload(selected, format, quality);
  } else if (inputMode === "batch") {
    const lines = batchTextarea.value
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length === 0) {
      showError("Paste at least one link.");
      return;
    }
    const items = lines.map((url) => ({
      title: url.length > 60 ? url.slice(0, 57) + "…" : url,
      url,
    }));
    startPlaylistDownload(items, format, quality);
  } else {
    const url = urlInput.value.trim();
    startSingleDownload(url, format, quality);
  }
});
