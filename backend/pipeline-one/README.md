# Pipeline 1: Industrial Material Master Attribute Extractor & Review Studio

> **Air-Gapped, Fine-Tuned Qwen2.5-3B LoRA Extraction Server & Interactive Review Studio**

Pipeline 1 transforms chaotic, un-delimited industrial catalog and ERP text from Indian Central Public Sector Enterprises (CPSEs) into standardized 8-attribute structured inventory records using a dedicated fine-tuned Qwen2.5-3B LoRA model (`qwen2.5-3b-cpse-lora-v2`).

It features a **low-GPU-pressure FastAPI server** (~2.0 GB VRAM in 4-bit NF4), an **interactive spreadsheet-style Review Studio Web UI**, inline cell editing to correct LLM predictions, and automated downstream handoff to Pipeline 2 via webhooks and verified staging files.

---

## Quick Start Guide

### 1. Prerequisites
- **Operating System**: Windows 10/11 or Linux
- **Python**: **Python 3.12** *(recommended for official PyTorch CUDA 12.4 support)*
- **GPU (Recommended)**: NVIDIA GPU with $\ge 4\text{ GB}$ VRAM (e.g. GeForce RTX 3050/3060/4060) or CPU fallback

---

### 2. Download Fine-Tuned Model Weights (GitHub Release)

Because model weights exceed GitHub's 100MB repository file limit, they are hosted on GitHub Releases:

🔗 **GitHub Release Link**: [https://github.com/SangikGhosh/sih-2026/releases/tag/finetunned_model](https://github.com/SangikGhosh/sih-2026/releases/tag/finetunned_model)

#### Step-by-Step Setup:
1. Open the release page: **[https://github.com/SangikGhosh/sih-2026/releases/tag/finetunned_model](https://github.com/SangikGhosh/sih-2026/releases/tag/finetunned_model)**
2. Download `qwen2.5-3b-cpse-lora-v2.zip` from the release assets.
3. Unzip the archive and place the folder directly inside `backend/pipeline-one/models/`.

#### Expected Directory Layout:
```
backend/pipeline-one/models/
└── qwen2.5-3b-cpse-lora-v2/
    ├── adapter_config.json
    ├── adapter_model.safetensors
    ├── chat_template.jinja
    ├── tokenizer.json
    ├── tokenizer_config.json
    └── README.md
```

#### Automated PowerShell Command:
```powershell
# Run from project root:
Invoke-WebRequest -Uri "https://github.com/SangikGhosh/sih-2026/releases/download/finetunned_model/qwen2.5-3b-cpse-lora-v2.zip" -OutFile "backend\pipeline-one\models\qwen2.5-3b-cpse-lora-v2.zip"
Expand-Archive -Path "backend\pipeline-one\models\qwen2.5-3b-cpse-lora-v2.zip" -DestinationPath "backend\pipeline-one\models" -Force
Remove-Item "backend\pipeline-one\models\qwen2.5-3b-cpse-lora-v2.zip"
```

---

### 3. Environment Setup

If you already have the repository's `.venv` installed, simply activate it:

#### Windows PowerShell:
```powershell
# From project root:
.\.venv\Scripts\Activate.ps1
```

#### Windows Command Prompt (cmd.exe):
```cmd
.\.venv\Scripts\activate.bat
```

#### First-time Setup / Fresh Environment:
If you are setting up on a fresh machine or reinstalling dependencies:
```powershell
# Using uv (fastest, recommended):
uv venv .venv --python 3.12
uv pip install torch --index-url https://download.pytorch.org/whl/cu124 --python .venv\Scripts\python.exe
uv pip install transformers peft accelerate bitsandbytes fastapi uvicorn pandas openpyxl python-multipart httpx pytest --python .venv\Scripts\python.exe

# Or using standard pip:
py -3.12 -m venv .venv
.\.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install transformers peft accelerate bitsandbytes fastapi uvicorn pandas openpyxl python-multipart httpx pytest
```

---

### 4. Start the Server

```powershell
# 1. Navigate to the pipeline directory
cd backend/pipeline-one

# 2. Launch the server on port 8001
python server.py --port 8001
```

#### Command Line Options:
```powershell
# Custom port and host
python server.py --host 0.0.0.0 --port 8001

# Enable auto-reload on code changes (development)
python server.py --port 8001 --reload
```

---

### 5. Access the Application

Once started, the server exposes the following interfaces:

| Interface | URL | Purpose |
| :--- | :--- | :--- |
| **Review Studio Web UI** | [http://localhost:8001/](http://localhost:8001/) | Interactive human-in-the-loop review spreadsheet |
| **Interactive API Docs** | [http://localhost:8001/docs](http://localhost:8001/docs) | Swagger UI for testing REST endpoints |
| **System Health & GPU Check** | [http://localhost:8001/api/v1/health](http://localhost:8001/api/v1/health) | Live hardware and VRAM allocation status |

---

## How to Use the Review Studio

1. **Check Hardware Status**:
   - Look at the header badge at the top right of the Web UI.
   - When CUDA is active, it glows green: `GPU: NVIDIA GeForce RTX 3050 Laptop GPU (2.03 GB VRAM)`.
2. **Extract Single ERP Text**:
   - Enter raw messy catalog text in the textarea, or click one of the quick sample chips (*HEC Ball Valve*, *ONGC Lube Oil Filter*, *NTPC Safety Shoe*).
   - Click **`⚡ Extract Structured Attributes`**.
   - Watch real-time token generation logs and extraction metrics stream in your terminal.
3. **Extract Batch CSV / Excel**:
   - Switch to the **Batch CSV / Excel** tab.
   - Drag & drop a CSV/Excel file or click to browse. The server auto-detects columns like `RAW_CATALOG_TEXT`, `Item Description (Raw)`, etc.
   - Set an optional row limit (default: 100 rows).
   - Click **`⚡ Extract Batch Records`** to process records sequentially with low VRAM footprint.
4. **Review & Inline Edit**:
   - Double-click or click any table cell to modify incorrect or missing values.
   - Edited cells highlight in soft emerald green and display an `edited` badge.
5. **Confirm & Forward to Pipeline 2**:
   - Click **`📤 Confirm & Forward to Next Pipeline`** to dispatch confirmed records to `NEXT_PIPELINE_URL`.
   - Verified records are automatically archived to `backend/pipeline-one/output/` in both JSON and CSV formats.

---

## API Usage Examples

### 1. Healthcheck
```bash
curl http://127.0.0.1:8001/api/v1/health
```
```json
{
  "status": "ok",
  "service": "pipeline-one",
  "model": "qwen2.5-3b-cpse-lora-v2",
  "device": "cuda",
  "device_name": "NVIDIA GeForce RTX 3050 Laptop GPU",
  "vram_gb": 2.03,
  "active_sessions": 2
}
```

### 2. Single Text Extraction
```bash
curl -X POST http://127.0.0.1:8001/api/v1/extract/text \
  -H "Content-Type: application/json" \
  -d '{"text": "HEC BALL VALVE 1_INCH SS316 1000 WOG PTFESEAT BHEL-868460 6219 NOS CAT-438 AUDCO Dim: 226MM"}'
```

#### Python Example:
```python
import httpx

payload = {
    "text": "ONGC filter Lube_OIL-forCUMMINS Engine Kta19 IOCL-507869 13751 NOS PN-2409-B FLTGUARD Dim: 238mm,Mat: RUBBER."
}
response = httpx.post("http://127.0.0.1:8001/api/v1/extract/text", json=payload, timeout=60.0)
record = response.json()["record"]["current"]
print(record)
```

---

## Target 8 Canonical CPSE Attributes

| Attribute | Description | Example |
| :--- | :--- | :--- |
| **Company** | CPSE Organization Name | `Coal India (BCCL)`, `ONGC`, `NTPC`, `BHEL`, `GAIL` |
| **Item Description (Raw)** | Core engineering noun description | `BALL VALVE 1 INCH SS316 1000 WOG PTFE SEAT` |
| **Item Code / Legacy Ref** | CPSE material code / legacy ref | `BHEL-868460`, `9231230354`, `IOCL-507869` |
| **Quantity** | Numeric stock quantity (integer) | `13751`, `435`, `6219` |
| **UOM** | Standardized Unit of Measure | `NOS`, `MTR`, `KGS`, `SET`, `PAIR`, `EA` |
| **Part Number / OEM Number** | OEM / Manufacturer part number | `PN-2409-B`, `CAT-903`, `6205` |
| **Make / Brand** | Manufacturer or Brand | `SKF`, `BATA`, `FLEETGUARD`, `AUDCO` |
| **Specifications / Dimensions** | Technical specs, dimensions, material | `Dim: 238mm, Mat: Rubber` |

---

## Hardware & Resource Safeguards

To ensure system stability and avoid GPU Out-of-Memory (OOM) errors:
- **4-bit NF4 Quantization**: Base model loaded via `BitsAndBytesConfig` in 4-bit NF4. Model VRAM usage is strictly **$\le 2.2\text{ GB}$**, leaving ample headroom on 4 GB GPUs.
- **Sequential Micro-Batching**: Batch CSV extractions run sequentially with active CUDA cache clearing (`torch.cuda.empty_cache()`) every 5 records.
- **Controlled Generation**: `max_new_tokens=256` with greedy decoding (`do_sample=False`) and explicit ChatML stop token handling (`<|im_end|>`).
- **CPU Fallback**: Automatically falls back to multi-threaded CPU execution (`bfloat16`) if no CUDA GPU is detected.

---

## Running Automated Tests

Run the full pytest suite from the project root:
```powershell
d:\project\sih-2026\.venv\Scripts\pytest.exe backend\pipeline-one\tests -v
```

All 13 tests validate:
- Canonical dictionary key resolution & normalization.
- Token-level F1 accuracy metric calculation.
- FastAPI REST endpoints (`/health`, `/extract/text`, `/extract/csv`, `/forward`).
- Review session creation, cell modification, and downstream webhook dispatch.

---

## Troubleshooting

### 1. `[WinError 10048] Address already in use`
Port 8001 is being held by another process. Run:
```powershell
Get-NetTCPConnection -LocalPort 8001 | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
```

### 2. Verify CUDA Availability
Check if your GPU is detected:
```powershell
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
Ensure you are using the virtual environment `.venv` where `torch==2.6.0+cu124` is installed.
