// CPSE Material Master Review Studio - Client Logic

let currentSession = null;
let allRecords = [];
let filteredRecords = [];

const SAMPLES = {
  1: "HEC BALL VALVE 1_INCH SS316 1000 WOG PTFESEAT BHEL-868460 6219 NOS CAT-438 AUDCO Dim: 226MM",
  2: "ONGC filter Lube_OIL-forCUMMINS Engine Kta19 IOCL-507869 13751 NOS PN-2409-B FLTGUARD as per stndrdis/iso specifications. Dim: 238mm,Mat: RUBBER.",
  3: "ntpc SAFETY sho mens BLACK_SZ9_LEATHER CE APPROVED 9231230354 435 PAIR CAT-903 BATA dim: 350mm, mat:-Brass."
};

document.addEventListener("DOMContentLoaded", () => {
  initHealthCheck();
  setupDropzone();
});

// 1. Healthcheck & System Capability
async function initHealthCheck() {
  try {
    const res = await fetch("/api/v1/health");
    if (res.ok) {
      const data = await res.json();
      const devText = document.getElementById("deviceText");
      if (devText) {
        if (data.device === "cuda") {
          devText.textContent = `GPU: ${data.device_name || "NVIDIA RTX"} (${data.vram_gb ? data.vram_gb + " GB VRAM" : "4-bit NF4"})`;
          devText.style.color = "#34d399";
        } else {
          devText.textContent = `CPU Mode (${data.device_name || "Multi-thread"})`;
          devText.style.color = "#60a5fa";
        }
      }
    }
  } catch (err) {
    console.warn("Could not reach health check endpoint:", err);
  }
}

// 2. Tab Navigation
function switchTab(mode) {
  const textBtn = document.getElementById("tabTextBtn");
  const csvBtn = document.getElementById("tabCsvBtn");
  const textSec = document.getElementById("textInputSection");
  const csvSec = document.getElementById("csvInputSection");

  if (mode === "text") {
    textBtn.classList.add("active");
    csvBtn.classList.remove("active");
    textSec.style.display = "block";
    csvSec.style.display = "none";
  } else {
    csvBtn.classList.add("active");
    textBtn.classList.remove("active");
    textSec.style.display = "none";
    csvSec.style.display = "block";
  }
}

function loadSample(id) {
  const textarea = document.getElementById("rawTextInput");
  if (textarea && SAMPLES[id]) {
    textarea.value = SAMPLES[id];
    showToast(`Loaded sample ${id}`, "success");
  }
}

// 3. Dropzone setup
function setupDropzone() {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(evt => {
    dropzone.addEventListener(evt, e => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(evt => {
    dropzone.addEventListener(evt, e => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const input = document.getElementById("csvFileInput");
      input.files = files;
      document.getElementById("selectedFileName").textContent = `Selected: ${files[0].name} (${Math.round(files[0].size / 1024)} KB)`;
    }
  });
}

function handleFileSelected(e) {
  const file = e.target.files[0];
  if (file) {
    document.getElementById("selectedFileName").textContent = `Selected: ${file.name} (${Math.round(file.size / 1024)} KB)`;
  }
}

// 4. Single Text Extraction
async function handleExtractSingle() {
  const textInput = document.getElementById("rawTextInput");
  const btn = document.getElementById("btnExtractSingle");
  const text = textInput.value.trim();

  if (!text) {
    showToast("Please enter or paste raw catalog text.", "error");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> <span>Extracting Attributes with Qwen LoRA...</span>`;

  try {
    const res = await fetch("/api/v1/extract/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Extraction failed");
    }

    currentSession = data.session_id;
    allRecords = [data.record];
    filteredRecords = [...allRecords];
    renderTable();
    updateBadges();
    showToast("Structured attributes extracted successfully!", "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>⚡ Extract Structured Attributes</span>`;
  }
}

// 5. Batch CSV Extraction
async function handleExtractCsv() {
  const fileInput = document.getElementById("csvFileInput");
  const colInput = document.getElementById("columnSelect");
  const maxRowsInput = document.getElementById("maxRowsInput");
  const btn = document.getElementById("btnExtractCsv");
  const progContainer = document.getElementById("progressBarContainer");
  const progressBar = document.getElementById("progressBar");

  if (!fileInput.files || fileInput.files.length === 0) {
    showToast("Please select or drop a CSV/Excel file.", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  if (colInput.value.trim()) {
    formData.append("text_column", colInput.value.trim());
  }
  if (maxRowsInput.value) {
    formData.append("max_rows", maxRowsInput.value);
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> <span>Processing CSV with LoRA (Low VRAM Mode)...</span>`;
  progContainer.style.display = "block";
  progressBar.style.width = "40%";

  try {
    const res = await fetch("/api/v1/extract/csv", {
      method: "POST",
      body: formData
    });

    progressBar.style.width = "85%";
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "CSV batch processing failed");
    }

    progressBar.style.width = "100%";
    currentSession = data.session_id;
    allRecords = data.records;
    filteredRecords = [...allRecords];
    renderTable();
    updateBadges();
    showToast(`Batch processed! Extracted ${data.total_records} records.`, "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>🚀 Process CSV Batch</span>`;
    setTimeout(() => {
      progContainer.style.display = "none";
      progressBar.style.width = "0%";
    }, 1200);
  }
}

// 6. Table Rendering & Inline Cell Editing
function renderTable() {
  const tbody = document.getElementById("recordsTableBody");
  if (!tbody) return;

  if (filteredRecords.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; color: var(--text-muted); padding: 2.5rem 1rem;">
          No matching records found.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filteredRecords.map((r, idx) => {
    const cur = r.current || {};
    const isMod = r.is_modified;
    const recId = r.record_id;

    return `
      <tr data-record-id="${recId}">
        <td style="color: var(--text-muted); font-weight: 600;">${idx + 1}</td>
        ${renderEditableCell(recId, "Company", cur["Company"], isMod)}
        ${renderEditableCell(recId, "Item Description (Raw)", cur["Item Description (Raw)"], isMod)}
        ${renderEditableCell(recId, "Item Code / Legacy Ref", cur["Item Code / Legacy Ref"], isMod)}
        ${renderEditableCell(recId, "Quantity", cur["Quantity"], isMod)}
        ${renderEditableCell(recId, "UOM", cur["UOM"], isMod)}
        ${renderEditableCell(recId, "Part Number / OEM Number", cur["Part Number / OEM Number"], isMod)}
        ${renderEditableCell(recId, "Make / Brand", cur["Make / Brand"], isMod)}
        ${renderEditableCell(recId, "Specifications / Dimensions", cur["Specifications / Dimensions"], isMod)}
        <td>
          <span class="badge ${r.status === 'forwarded' ? 'badge-blue' : (isMod ? 'badge-green' : 'badge-amber')}">
            ${r.status === 'forwarded' ? 'Forwarded' : (isMod ? 'Reviewed' : 'Pending')}
          </span>
        </td>
      </tr>
    `;
  }).join("");

  // Attach click listeners to editable cells
  document.querySelectorAll(".editable-cell").forEach(cell => {
    cell.addEventListener("click", onCellClicked);
  });
}

function renderEditableCell(recordId, fieldName, value, isRowModified) {
  const isNa = value === "na" || value === "NA" || value === null || value === undefined || value === "";
  const displayVal = isNa 
    ? `<span class="badge-na" style="display: inline-block; padding: 2px 7px; border-radius: 4px; background: rgba(255,255,255,0.06); color: var(--text-muted); font-size: 0.76rem; font-weight: 600; letter-spacing: 0.5px; border: 1px solid rgba(255,255,255,0.08);">NA</span>` 
    : value;
  return `
    <td class="editable-cell" data-record-id="${recordId}" data-field="${fieldName}" title="Click to edit ${fieldName}">
      <span class="cell-display">${displayVal}</span>
    </td>
  `;
}

function onCellClicked(e) {
  const cell = e.currentTarget;
  if (cell.querySelector(".cell-input")) return; // Already in edit mode

  const recordId = cell.getAttribute("data-record-id");
  const fieldName = cell.getAttribute("data-field");
  const span = cell.querySelector(".cell-display");
  const rawSpanText = span.textContent.trim();
  const currentVal = (rawSpanText === "null" || rawSpanText.toUpperCase() === "NA") ? "" : rawSpanText;

  const input = document.createElement("input");
  input.type = fieldName === "Quantity" ? "number" : "text";
  input.className = "cell-input";
  input.value = currentVal;
  input.style.width = "100%";

  cell.innerHTML = "";
  cell.appendChild(input);
  input.focus();

  const saveEdit = async () => {
    const newVal = input.value.trim();
    const effectiveVal = (newVal === "" || newVal.toUpperCase() === "NA") ? "NA" : newVal;
    const oldEffective = (currentVal === "" || currentVal.toUpperCase() === "NA") ? "NA" : currentVal;
    if (effectiveVal === oldEffective) {
      const disp = oldEffective === "NA" 
        ? `<span class="badge-na" style="display: inline-block; padding: 2px 7px; border-radius: 4px; background: rgba(255,255,255,0.06); color: var(--text-muted); font-size: 0.76rem; font-weight: 600; letter-spacing: 0.5px; border: 1px solid rgba(255,255,255,0.08);">NA</span>` 
        : oldEffective;
      cell.innerHTML = `<span class="cell-display">${disp}</span>`;
      return;
    }

    // Call API to persist edit
    try {
      const payload = {};
      if (fieldName === "Quantity") {
        payload[fieldName] = (newVal === "" || newVal.toUpperCase() === "NA") ? "NA" : parseInt(newVal);
      } else {
        payload[fieldName] = (newVal === "" || newVal.toUpperCase() === "NA") ? "NA" : newVal;
      }

      const res = await fetch(`/api/v1/records/${currentSession}/${recordId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error("Failed to save edit");
      }

      const updated = await res.json();
      // Update in-memory record
      const idx = allRecords.findIndex(r => r.record_id === recordId);
      if (idx !== -1) {
        allRecords[idx] = updated.record;
      }
      const fIdx = filteredRecords.findIndex(r => r.record_id === recordId);
      if (fIdx !== -1) {
        filteredRecords[fIdx] = updated.record;
      }

      const savedVal = updated.record?.current?.[fieldName] ?? effectiveVal;
      const disp = (savedVal === "na" || savedVal === null) 
        ? "<span style='color: var(--text-muted); font-style: italic;'>na</span>" 
        : savedVal;
      cell.innerHTML = `<span class="cell-display">${disp}</span>`;
      cell.classList.add("modified");
      updateBadges();
      showToast(`Updated ${fieldName} on #${recordId}`, "success");

      // Update row badge
      const row = cell.closest("tr");
      const statusBadge = row.querySelector("td:last-child .badge");
      if (statusBadge) {
        statusBadge.className = "badge badge-green";
        statusBadge.textContent = "Reviewed";
      }
    } catch (err) {
      showToast(err.message, "error");
      const disp = oldEffective === "na" ? "<span style='color: var(--text-muted); font-style: italic;'>na</span>" : oldEffective;
      cell.innerHTML = `<span class="cell-display">${disp}</span>`;
    }
  };

  input.addEventListener("blur", saveEdit);
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      input.blur();
    } else if (e.key === "Escape") {
      cell.innerHTML = `<span class="cell-display">${currentVal || "<span style='color: var(--text-muted); font-style: italic;'>null</span>"}</span>`;
    }
  });
}

// 7. Badges & Metrics
function updateBadges() {
  const sessionBadge = document.getElementById("sessionBadge");
  const countBadge = document.getElementById("recordCountBadge");
  const modBadge = document.getElementById("modifiedCountBadge");
  const forwardBtn = document.getElementById("btnForward");

  if (sessionBadge) {
    sessionBadge.textContent = currentSession ? `Session: ${currentSession}` : "No Active Session";
  }
  if (countBadge) {
    countBadge.textContent = `${allRecords.length} Records`;
  }
  if (modBadge) {
    const modifiedCount = allRecords.filter(r => r.is_modified).length;
    modBadge.textContent = `${modifiedCount} Edited`;
  }
  if (forwardBtn) {
    forwardBtn.disabled = allRecords.length === 0;
  }
}

// 8. Filter Records
function filterRecords(query) {
  const q = query.toLowerCase().trim();
  if (!q) {
    filteredRecords = [...allRecords];
  } else {
    filteredRecords = allRecords.filter(r => {
      const cur = r.current || {};
      return Object.values(cur).some(v => v !== null && String(v).toLowerCase().includes(q));
    });
  }
  renderTable();
}

// 9. Downstream Pipeline Forwarding
async function handleForwardPipeline() {
  if (!currentSession || allRecords.length === 0) {
    showToast("No active records to forward.", "error");
    return;
  }

  const targetUrlInput = document.getElementById("targetUrlInput");
  const btn = document.getElementById("btnForward");
  const targetUrl = targetUrlInput ? targetUrlInput.value.trim() : null;

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> <span>Dispatching to Next Pipeline...</span>`;

  try {
    const res = await fetch("/api/v1/pipeline/forward", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSession,
        target_url: targetUrl || null
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Pipeline dispatch failed");
    }

    // Mark all local records as forwarded
    allRecords.forEach(r => r.status = "forwarded");
    filteredRecords.forEach(r => r.status = "forwarded");
    renderTable();

    let msg = `Dispatched ${data.record_count} verified records! Archived to ${data.json_filename}`;
    if (data.http_status) {
      msg += ` (Webhook Response: HTTP ${data.http_status})`;
    }
    showToast(msg, "success");
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>🚀 Send to Next Pipeline</span>`;
  }
}

// 10. Direct File Exports (from memory)
function exportCurrentJSON() {
  if (allRecords.length === 0) {
    showToast("No records to export.", "error");
    return;
  }
  const payload = {
    session_id: currentSession,
    model: "qwen2.5-3b-cpse-lora-v2",
    record_count: allRecords.length,
    records: allRecords.map(r => r.current)
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  downloadBlob(blob, `verified_records_${currentSession || 'export'}.json`);
}

function exportCurrentCSV() {
  if (allRecords.length === 0) {
    showToast("No records to export.", "error");
    return;
  }
  const headers = [
    "Company", "Item Description (Raw)", "Item Code / Legacy Ref",
    "Quantity", "UOM", "Part Number / OEM Number", "Make / Brand", "Specifications / Dimensions"
  ];
  const rows = [headers.join(",")];

  allRecords.forEach(r => {
    const cur = r.current || {};
    const row = headers.map(h => {
      const val = cur[h] !== null && cur[h] !== undefined ? String(cur[h]) : "";
      return `"${val.replace(/"/g, '""')}"`;
    });
    rows.push(row.join(","));
  });

  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, `verified_records_${currentSession || 'export'}.csv`);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast(`Downloaded ${filename}`, "success");
}

// 11. Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span style="font-size: 1.1rem;">${type === "success" ? "✓" : (type === "error" ? "✕" : "ℹ")}</span>
    <span style="font-size: 0.85rem; font-weight: 500;">${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
