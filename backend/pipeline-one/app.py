"""
app.py - FastAPI application for Pipeline 1 (CPSE Material Master Extraction & Review Studio).
Strictly powered by the fine-tuned Qwen2.5-3B LoRA model (qwen2.5-3b-cpse-lora-v2).
"""

import os
import io
import re
import time
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ConfigDict
import pandas as pd

from inference_engine import QwenLoraEngine, CANONICAL_FIELDS
from session_store import SessionStore
from forwarder import PipelineForwarder

logger = logging.getLogger("pipeline_one")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"
SESSIONS_DIR = BASE_DIR / "sessions"

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Initialize core services
engine = QwenLoraEngine()
session_store = SessionStore(storage_dir=str(SESSIONS_DIR))
forwarder = PipelineForwarder(session_store=session_store, output_dir=str(OUTPUT_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Pipeline 1 API Server starting up...")
    logger.info(f"Model adapter path: {engine.adapter_dir}")
    logger.info("Pre-warming Qwen2.5-3B LoRA extraction engine...")
    engine.load_model()
    yield
    logger.info("Pipeline 1 API Server shutting down...")


app = FastAPI(
    title="CPSE Material Master Extraction API (Pipeline 1)",
    description="Fine-tuned Qwen2.5-3B LoRA attribute extraction with interactive review & downstream dispatch.",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for external frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Pydantic Request Models
class ExtractTextRequest(BaseModel):
    text: str = Field(..., description="Raw chaotic catalog / ERP material string")


class UpdateRecordRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    company: Optional[str] = None
    item_description_raw: Optional[str] = None
    item_code_legacy_ref: Optional[str] = None
    quantity: Optional[Any] = None
    uom: Optional[str] = None
    part_number_oem_number: Optional[str] = None
    make_brand: Optional[str] = None
    specifications_dimensions: Optional[str] = None



class ForwardPipelineRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier to forward")
    target_url: Optional[str] = Field(None, description="Optional downstream webhook destination URL")


class AbbreviationRequest(BaseModel):
    raw: str = Field(..., description="Abbreviation to expand e.g. VLV, ALM, PRV")
    expansion: str = Field(..., description="Canonical expanded technical term e.g. VALVE, ALUMINIUM")
    scope: Optional[str] = Field(None, description="Optional domain/equipment category scope")
    persist: Optional[bool] = Field(True, description="Whether to persist to disk")


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.get("/api/v1/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Healthcheck and device capability status."""
    return {
        "status": "ok",
        "service": "pipeline-one",
        "model": "qwen2.5-3b-cpse-lora-v2",
        "adapter_path": engine.adapter_dir,
        "device": engine.device,
        "device_name": engine.device_name,
        "vram_gb": engine.vram_gb,
        "active_sessions": len(session_store.list_sessions()),
    }


@app.post("/api/v1/extract/text", tags=["Extraction"])
def extract_single_text(payload: ExtractTextRequest) -> Dict[str, Any]:
    """Extract 8 canonical attributes from a single un-delimited ERP string."""
    raw_text = payload.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    logger.info("======================================================================")
    logger.info(">> [API ROUTE] POST /api/v1/extract/text received")
    try:
        record = engine.extract_single(raw_text)
        session = session_store.create_session(
            source_type="text",
            records=[record],
            raw_texts=[raw_text],
        )
        logger.info(f">> [API ROUTE] Created review session: {session.session_id}")
        logger.info("======================================================================")
        return {
            "session_id": session.session_id,
            "record": session.records[0],
        }
    except Exception as e:
        logger.exception("Error extracting single text")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


def row_to_composite_text(row: pd.Series) -> str:
    """
    Convert an entire multi-column CSV/Excel row into a single coherent composite string
    for LLM attribute extraction, preserving all provided column data.
    """
    desc_keys = [
        "item description (raw)", "item description", "description",
        "item_name", "item", "material_name", "material", "raw_catalog_text",
        "long text", "catalog text", "short text", "text"
    ]
    primary_desc = None
    other_pairs = []

    for col, val in row.items():
        if pd.isna(val) or val is None:
            continue
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ["nan", "none", "null", "unknown", "n/a", "na"]:
            continue
        col_name = str(col).strip()
        if re.match(r"^unnamed:\s*\d+$", col_name, re.IGNORECASE):
            continue

        if primary_desc is None and col_name.lower() in desc_keys:
            primary_desc = val_str
        else:
            other_pairs.append((col_name, val_str))

    parts = []
    if primary_desc:
        parts.append(f"{primary_desc.rstrip('.')}.")
    for col_name, val_str in other_pairs:
        parts.append(f"{col_name}: {val_str.rstrip('.')}.")

    if not parts:
        vals = [str(v).strip() for v in row.dropna().values if str(v).strip()]
        return " ".join(vals)

    return " ".join(parts)


@app.post("/api/v1/extract/csv", tags=["Extraction"])
async def extract_csv(
    file: UploadFile = File(...),
    text_column: Optional[str] = Form(None),
    max_rows: Optional[int] = Form(100),
) -> Dict[str, Any]:
    """
    Upload CSV/Excel file, auto-detect text column, and extract attributes batch-wise.
    Processes items sequentially to safeguard GPU memory.
    """
    contents = await file.read()
    filename = file.filename or "upload.csv"

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV/Excel file: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded file contains no rows.")

    # Limit rows if specified
    if max_rows and max_rows > 0:
        df = df.iloc[:max_rows]

    # Determine input text representation:
    # 1. If user explicitly requested a specific column that exists in df, use that column
    target_col = None
    if text_column and text_column.strip():
        req_col = text_column.strip()
        if req_col in df.columns:
            target_col = req_col
            raw_texts = df[target_col].fillna("").astype(str).tolist()
            logger.info(f"Using explicitly requested column '{target_col}' for extraction from {filename}")

    # 2. Otherwise: if multi-column CSV, synthesize each entire row into one composite attribute string
    if target_col is None:
        if len(df.columns) > 1:
            target_col = f"Composite Whole Row ({len(df.columns)} columns)"
            raw_texts = [row_to_composite_text(row) for _, row in df.iterrows()]
            logger.info(f"Multi-column CSV detected ({len(df.columns)} columns); synthesized whole rows into composite attributes for {filename}")
        else:
            target_col = str(df.columns[0])
            raw_texts = df[target_col].fillna("").astype(str).tolist()
            logger.info(f"Single-column CSV detected; using column '{target_col}' from {filename}")

    extracted_records = engine.extract_batch(raw_texts)

    session = session_store.create_session(
        source_type="csv",
        records=extracted_records,
        raw_texts=raw_texts,
        original_filename=filename,
    )

    return {
        "session_id": session.session_id,
        "source_file": filename,
        "text_column_used": target_col,
        "total_records": session.total_records,
        "records": session.records,
    }


@app.get("/api/v1/sessions", tags=["Review"])
def list_sessions() -> List[Dict[str, Any]]:
    """List all review sessions."""
    return session_store.list_sessions()


@app.get("/api/v1/sessions/{session_id}", tags=["Review"])
def get_session(session_id: str) -> Dict[str, Any]:
    """Fetch complete review session and all records."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "source_type": session.source_type,
        "total_records": session.total_records,
        "original_filename": session.original_filename,
        "records": session.records,
    }


@app.put("/api/v1/records/{session_id}/{record_id}", tags=["Review"])
def update_record(
    session_id: str,
    record_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update / correct any predicted attributes in a record.
    Marks record as modified and reviewed.
    """
    updated = session_store.update_record(session_id, record_id, payload)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"Record '{record_id}' in session '{session_id}' not found.",
        )
    return {
        "success": True,
        "record": updated,
    }


@app.post("/api/v1/pipeline/forward", tags=["Downstream"])
def forward_to_next_pipeline(payload: ForwardPipelineRequest) -> Dict[str, Any]:
    """
    Confirm reviewed records and send payload to downstream pipeline.
    Archives verified JSON and CSV to backend/pipeline-one/output/.
    """
    try:
        result = forwarder.forward_session(
            session_id=payload.session_id,
            target_url=payload.target_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error forwarding session")
        raise HTTPException(status_code=500, detail=f"Forwarding failed: {str(e)}")


@app.post("/api/v1/taxonomy/abbreviations", tags=["Taxonomy & Active Learning"])
def add_abbreviation(payload: AbbreviationRequest) -> Dict[str, Any]:
    """
    Active Learning: Dynamically register a new CPSE abbreviation mapping.
    Instantly updates abbreviation normalization engine without model retraining.
    """
    from inference_engine import register_abbreviation
    ok = register_abbreviation(
        raw=payload.raw,
        expansion=payload.expansion,
        scope=payload.scope or "",
        persist=payload.persist if payload.persist is not None else True
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid abbreviation or expansion provided")
    return {
        "success": True,
        "raw": payload.raw.strip().upper(),
        "expansion": payload.expansion.strip().upper(),
        "message": "Abbreviation successfully registered in CPSE taxonomy engine."
    }


# ==============================================================================
# UI Routes
# ==============================================================================

@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def serve_review_studio():
    """Serve Single-Page Review Studio Web UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        content={
            "message": "CPSE Pipeline 1 API Server running. Open /docs for Swagger UI.",
            "health": "/api/v1/health",
        }
    )
