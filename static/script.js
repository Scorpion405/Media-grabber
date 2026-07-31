const form = document.getElementById("download-form");
const submitBtn = document.getElementById("submit-btn");
const formatSelect = document.getElementById("format");
const qualitySelect = document.getElementById("quality");
const statusArea = document.getElementById("status-area");
const statusText = document.getElementById("status-text");
const progressFill = document.getElementById("progress-fill");
const resultArea = document.getElementById("result-area");
const resultTitle = document.getElementById("result-title");
const resultLink = document.getElementById("result-link");
const errorText = document.getElementById("error-text");

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

function refreshQualityOptions() {
  const opts = formatSelect.value === "mp3" ? MP3_QUALITIES : MP4_QUALITIES;
  qualitySelect.innerHTML = opts
    .map((o) => `<option value="${o.value}">${o.label}</option>`)
    .join("");
}

formatSelect.addEventListener("change", refreshQualityOptions);
refreshQualityOptions();

function resetUI() {
  statusArea.classList.add("hidden");
  resultArea.classList.add("hidden");
  errorText.classList.add("hidden");
  progressFill.style.width = "0%";
}

function showError(msg) {
  errorText.textContent = msg;
  errorText.classList.remove("hidden");
  statusArea.classList.add("hidden");
  submitBtn.disabled = false;
  submitBtn.textContent = "Download";
}

async function pollProgress(jobId) {
  try {
    const res = await fetch(`/api/progress/${jobId}`);
    const data = await res.json();

    if (data.error) {
      showError(data.error);
      return;
    }

    if (data.status === "downloading") {
      statusText.textContent = `Downloading… ${data.percent ?? 0}%`;
      progressFill.style.width = `${data.percent ?? 0}%`;
    } else if (data.status === "processing") {
      statusText.textContent = "Converting…";
      progressFill.style.width = "100%";
    } else if (data.status === "queued") {
      statusText.textContent = "Starting…";
    } else if (data.status === "done") {
      statusArea.classList.add("hidden");
      resultArea.classList.remove("hidden");
      resultTitle.textContent = data.title || "Done";
      resultLink.href = `/api/file/${jobId}`;
      resultLink.setAttribute("download", data.filename);
      submitBtn.disabled = false;
      submitBtn.textContent = "Download";
      return; // stop polling
    } else if (data.status === "error") {
      showError(data.error || "Something went wrong.");
      return;
    }

    setTimeout(() => pollProgress(jobId), 1000);
  } catch (err) {
    showError("Lost connection to local server.");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  resetUI();

  const url = document.getElementById("url").value.trim();
  const format = formatSelect.value;
  const quality = qualitySelect.value;

  submitBtn.disabled = true;
  submitBtn.textContent = "Working…";
  statusArea.classList.remove("hidden");
  statusText.textContent = "Starting…";

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, format, quality }),
    });
    const data = await res.json();

    if (data.error) {
      showError(data.error);
      return;
    }

    pollProgress(data.job_id);
  } catch (err) {
    showError("Could not reach local server. Is app.py running?");
  }
});
