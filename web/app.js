const scoreForm = document.querySelector("#score-form");
const scoreResult = document.querySelector("#score-result");
const scoreError = document.querySelector("#score-error");
const batchForm = document.querySelector("#batch-form");
const batchError = document.querySelector("#batch-error");
const batchJob = document.querySelector("#batch-job");
const fileInput = document.querySelector("#csv-file");
const uploadZone = document.querySelector("#upload-zone");
const resultsSection = document.querySelector("#batch-results");
const resultsBody = document.querySelector("#results-body");
const toast = document.querySelector("#toast");
let latestResults = [];
let toastTimer;
let aiExplanationsEnabled = false;

const asNumber = (value) => Number(value);
const formatPercent = (probability) => `${(probability * 100).toFixed(1)}%`;
const tierClass = (tier) => `tier-${String(tier).toLowerCase()}`;
const safeText = (value) => String(value ?? "");

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function showError(element, message) {
  element.textContent = message;
  element.hidden = false;
}

function clearError(element) {
  element.textContent = "";
  element.hidden = true;
}

async function responseError(response) {
  try {
    const payload = await response.json();
    const detail = payload.detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => `${(item.loc || []).slice(-1)[0] || "Input"}: ${item.msg}`).join(" · ");
    }
    return detail || `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

function setButtonBusy(button, busy, busyLabel) {
  const label = button.querySelector(".button-label");
  if (!button.dataset.originalLabel && label) button.dataset.originalLabel = label.textContent;
  button.disabled = busy;
  button.style.opacity = busy ? ".7" : "1";
  if (label) label.textContent = busy ? busyLabel : button.dataset.originalLabel;
}

function paintScore(result, payload) {
  const probability = Math.max(0, Math.min(1, Number(result.churn_probability_90d)));
  const percent = formatPercent(probability);
  const tier = safeText(result.risk_tier);
  const summaries = {
    Low: "Keep the relationship warm and maintain your regular cadence.",
    Medium: "Check in on goals and look for changes in the account plan.",
    High: "Prioritize a timely conversation with this account.",
  };
  const color = tier === "High" ? "#df766d" : tier === "Medium" ? "#e6ac4c" : "#42ad8d";
  scoreResult.innerHTML = `
    <div class="result-gauge ${tierClass(tier)}" style="--tier-color:${color};--score-angle:${probability * 360}deg"><strong>${percent}</strong></div>
    <div class="result-copy"><span class="result-kicker">90-DAY CHURN PROBABILITY</span><h3>${escapeHtml(safeText(result.account_id))}</h3><p>${escapeHtml(summaries[tier] || "Review this account with your Customer Success context.")}</p></div>
    <span class="result-tier ${tierClass(tier)}">${escapeHtml(tier)} risk</span>
    <div class="ai-action-row"><button class="button ai-button" type="button" ${aiExplanationsEnabled ? "" : "disabled"}>✦ Generate AI explanation</button><span>${aiExplanationsEnabled ? "Creates a CS summary and suggested next action" : "Set OPENAI_API_KEY on the backend to enable"}</span></div>`;
  scoreResult.hidden = false;
  scoreResult.querySelector(".ai-button").addEventListener("click", () => requestExplanation(payload));
  scoreResult.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function requestExplanation(payload) {
  const button = scoreResult.querySelector(".ai-button");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Generating explanation…";
  try {
    const response = await fetch("/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const result = await response.json();
    renderExplanation(result.explanation);
  } catch (error) {
    showError(scoreError, error.message || "Could not generate an AI explanation.");
  } finally {
    button.textContent = original;
    button.disabled = !aiExplanationsEnabled;
  }
}

function renderExplanation(explanation) {
  scoreResult.querySelector(".ai-insight")?.remove();
  const section = document.createElement("section");
  section.className = "ai-insight";
  const title = document.createElement("div");
  title.className = "ai-insight-title";
  title.innerHTML = "<span>✦</span> AI-generated CS context";
  const summary = document.createElement("p");
  summary.textContent = explanation.summary;
  section.append(title, summary);
  if (explanation.context_signals?.length) {
    const list = document.createElement("ul");
    for (const signal of explanation.context_signals) {
      const item = document.createElement("li");
      item.textContent = signal;
      list.append(item);
    }
    section.append(list);
  }
  const action = document.createElement("p");
  action.className = "ai-next-action";
  action.textContent = `Suggested next action: ${explanation.recommended_action}`;
  const limitation = document.createElement("small");
  limitation.textContent = explanation.limitation;
  section.append(action, limitation);
  scoreResult.append(section);
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

scoreForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError(scoreError);
  const submit = scoreForm.querySelector("button[type=submit]");
  const values = Object.fromEntries(new FormData(scoreForm).entries());
  const payload = {
    ...values,
    tenure_days: asNumber(values.tenure_days),
    seats_at_signup: asNumber(values.seats_at_signup),
  };
  setButtonBusy(submit, true, "Scoring account…");
  try {
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await responseError(response));
    paintScore(await response.json(), payload);
  } catch (error) {
    showError(scoreError, error.message || "Could not reach the scoring service.");
  } finally {
    setButtonBusy(submit, false);
  }
});

function updateFileLabel() {
  const file = fileInput.files?.[0];
  const title = document.querySelector("#upload-title");
  const detail = document.querySelector("#upload-detail");
  const fileName = document.querySelector("#upload-file");
  uploadZone.classList.toggle("has-file", Boolean(file));
  if (file) {
    title.textContent = "CSV ready to score";
    detail.textContent = "Click here to choose a different file";
    fileName.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
    fileName.hidden = false;
  } else {
    title.textContent = "Drop your CSV here";
    detail.innerHTML = "or <em>browse files</em> · up to 10,000 accounts";
    fileName.hidden = true;
  }
}
fileInput.addEventListener("change", updateFileLabel);

uploadZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  uploadZone.classList.add("drag-over");
});
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", (event) => {
  event.preventDefault();
  uploadZone.classList.remove("drag-over");
  const file = event.dataTransfer.files?.[0];
  if (file && file.name.toLowerCase().endsWith(".csv")) {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    updateFileLabel();
  } else if (file) {
    showError(batchError, "Choose a .csv file to start batch scoring.");
  }
});

function setJobMessage(state, text, isDone = false) {
  batchJob.innerHTML = `<span class="${isDone ? "job-done" : "job-spinner"}">${isDone ? "✓" : ""}</span><span>${escapeHtml(text)}</span>`;
  batchJob.hidden = false;
}

async function pollJob(jobId, attempt = 0) {
  if (attempt > 120) throw new Error("This job is taking longer than expected. Check again in a moment.");
  const response = await fetch(`/batch-scoring/${encodeURIComponent(jobId)}`);
  if (!response.ok) throw new Error(await responseError(response));
  const job = await response.json();
  if (job.status === "failed") throw new Error(job.error || "Batch scoring failed.");
  if (job.status !== "completed") {
    setJobMessage(job.status, `Scoring ${job.row_count.toLocaleString()} accounts · ${job.status}…`);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    return pollJob(jobId, attempt + 1);
  }
  latestResults = job.results || [];
  setJobMessage("completed", `${latestResults.length.toLocaleString()} accounts scored successfully.`, true);
  renderResults(latestResults);
  showToast("Batch scores are ready to review.");
}

batchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError(batchError);
  const file = fileInput.files?.[0];
  if (!file) {
    showError(batchError, "Choose a CSV file first.");
    return;
  }
  const submit = batchForm.querySelector("button[type=submit]");
  setButtonBusy(submit, true, "Uploading and scoring…");
  batchJob.hidden = false;
  setJobMessage("queued", "Uploading your account list…");
  try {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/batch-scoring", { method: "POST", body: form });
    if (!response.ok) throw new Error(await responseError(response));
    const job = await response.json();
    setJobMessage(job.status, "File received. Preparing the scoring job…");
    await pollJob(job.job_id);
  } catch (error) {
    showError(batchError, error.message || "Could not submit the batch job.");
    setJobMessage("failed", "The batch job could not be completed.", true);
  } finally {
    setButtonBusy(submit, false);
  }
});

function nextStepFor(tier) {
  if (tier === "High") return "Prioritize an account conversation";
  if (tier === "Medium") return "Review goals and engagement";
  return "Continue regular success cadence";
}

function renderResults(results) {
  resultsBody.replaceChildren();
  for (const row of results) {
    const probability = Math.max(0, Math.min(1, Number(row.churn_probability_90d)));
    const tier = safeText(row.risk_tier);
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(safeText(row.account_id))}</td><td><div class="prob-cell"><span class="prob-track" style="--tier-color:${tier === "High" ? "#df766d" : tier === "Medium" ? "#e6ac4c" : "#42ad8d"}"><i style="width:${probability * 100}%"></i></span><span class="prob-number">${formatPercent(probability)}</span></div></td><td><span class="result-tier ${tierClass(tier)}">${escapeHtml(tier)}</span></td><td class="next-step">${escapeHtml(nextStepFor(tier))}</td>`;
    resultsBody.append(tr);
  }
  document.querySelector("#results-summary").textContent = `${results.length.toLocaleString()} accounts · Sorted by risk tier and probability`;
  resultsSection.hidden = false;
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function downloadCsv(filename, rows) {
  const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = rows.map((row) => row.map(quote).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

document.querySelector("#download-template").addEventListener("click", () => {
  downloadCsv("account-scoring-template.csv", [["account_id", "tenure_days", "plan", "seats_at_signup", "region", "industry", "channel"], ["acct-001", 420, "team", 24, "EMEA", "software", "partner"]]);
});

document.querySelector("#download-results").addEventListener("click", () => {
  if (!latestResults.length) return;
  downloadCsv("account-health-scores.csv", [["account_id", "churn_probability_90d", "risk_tier"], ...latestResults.map((row) => [row.account_id, row.churn_probability_90d, row.risk_tier])]);
});

document.querySelector(".notice-close").addEventListener("click", () => {
  document.querySelector(".notice-bar").remove();
});

async function checkApi() {
  const status = document.querySelector(".live-status");
  try {
    const response = await fetch("/health", { cache: "no-store" });
    if (!response.ok) throw new Error("offline");
    const health = await response.json();
    aiExplanationsEnabled = Boolean(health.openai_explanations_enabled);
    status.innerHTML = "<i></i> Scoring API connected";
    status.classList.remove("offline");
  } catch {
    status.innerHTML = "<i></i> Scoring API offline";
    status.classList.add("offline");
  }
}
checkApi();
