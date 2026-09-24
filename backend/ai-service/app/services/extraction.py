"""Phase 1, hosted in this service: the LoRA engine's lifecycle and batching.

`logic/extraction.py` is the engine itself, vendored from pipeline-one. This
module owns the two things a service has to decide that a library should not:

  * **When the weights load.** On first use, not at startup. ai-service boots
    in a second and must keep doing so; a 3B model on a machine that has no
    GPU should fail the one request that needs it, not the whole process.
  * **Whether they load at all.** `EXTRACTION_ENABLED=false` (the default)
    keeps torch, transformers and peft out of the critical path entirely, so
    the vector-DB half of the service runs, demos and tests with no model
    weights present - the same rule `EMBEDDING_PROVIDER=deterministic`
    follows. `GET /extract/info` always reports which state is live, so a demo
    can never claim fine-tuned extraction while running without it.

The adapter weights are NOT copied into this service. They are 195 MB and are
already tracked under `backend/pipeline-one/models/`, so `LORA_ADAPTER_DIR`
points at them by default. Set it to `data/models/qwen2.5-3b-cpse-lora-v2` and
unzip the release there instead when ai-service ships as a standalone image.
"""

from __future__ import annotations

import io
import logging
import re
import threading
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logic.extraction import CANONICAL_FIELDS

logger = logging.getLogger(__name__)

__all__ = [
    "EXTRACT_CHUNK_SIZE",
    "ExtractionUnavailable",
    "read_upload",
    "row_to_composite_text",
    "run_extraction",
    "adapter_dir",
    "extract_batch",
    "extract_one",
    "info",
    "register_abbreviation",
    "reset",
]

ADAPTER_NAME = "qwen2.5-3b-cpse-lora-v2"

_SERVICE_ROOT = Path(__file__).resolve().parent.parent.parent

_engine: Any | None = None
_lock = threading.Lock()

class ExtractionUnavailable(RuntimeError):
    """Phase 1 was asked for and cannot answer. Reported as 503, never 500."""


def adapter_dir() -> Path:
    configured = Path(settings.lora_adapter_dir)
    if configured.is_absolute():
        return configured
    return (_SERVICE_ROOT / configured).resolve()


def reset() -> None:
    """Drop the loaded engine. For tests and for a config change at runtime."""
    global _engine
    with _lock:
        _engine = None


def _engine_or_raise() -> Any:
    global _engine
    if _engine is not None:
        return _engine

    if not settings.extraction_enabled:
        raise ExtractionUnavailable(
            "EXTRACTION_ENABLED=false: this service is running its vector-DB "
            "half only and will not load the LoRA adapter. Send standard-format "
            "rows to POST /standardized/check instead, or set "
            "EXTRACTION_ENABLED=true (needs torch, transformers and peft - see "
            "requirements-ml.txt) to extract them here."
        )

    with _lock:
        if _engine is not None:
            return _engine

        target = adapter_dir()
        if not target.is_dir():
            raise ExtractionUnavailable(
                f"The LoRA adapter is not at {target}. It is not copied into "
                f"this service - it is 195 MB and already lives under "
                f"backend/pipeline-one/models/. Point LORA_ADAPTER_DIR at it, "
                f"or download {ADAPTER_NAME}.zip from the project's GitHub "
                f"release and unzip it there."
            )

        from app.logic.extraction import QwenLoraEngine

        try:
            _engine = QwenLoraEngine(
                adapter_dir=str(target),
                base_model_name=settings.base_model_name,
                max_new_tokens=settings.extraction_max_new_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - a missing torch is a 503
            raise ExtractionUnavailable(
                f"Could not construct the extraction engine: {exc}. It needs "
                f"torch, transformers and peft: pip install -r requirements-ml.txt"
            ) from exc

        logger.info(
            "LoRA extraction engine ready | adapter=%s device=%s",
            target, getattr(_engine, "device", "?"),
        )
        return _engine


def extract_one(text: str) -> dict[str, Any]:
    """One raw ERP string -> the eight canonical attributes."""
    try:
        return _engine_or_raise().extract_single(text)
    except ExtractionUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractionUnavailable(f"Extraction failed: {exc}") from exc


def extract_batch(texts: list[str]) -> list[dict[str, Any]]:
    """Many strings, sequentially.

    Sequential on purpose, and that is the engine's design, not a shortcut:
    records are processed one at a time with the CUDA cache cleared every five
    so a 4 GB card does not OOM halfway through a catalogue.
    """
    if not texts:
        return []
    try:
        return list(_engine_or_raise().extract_batch(texts))
    except ExtractionUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExtractionUnavailable(f"Batch extraction failed: {exc}") from exc


def register_abbreviation(
    raw: str, expansion: str, *, scope: str = "", persist: bool = True
) -> bool:
    """Teach the taxonomy a new CPSE abbreviation, without retraining.

    Writes through to `data/config/abbreviations.csv`, which is the same table
    the engine loads at import. Active learning at the cheapest possible price:
    a dictionary entry a domain expert controls, applied to every subsequent
    extraction.
    """
    from app.logic.extraction import register_abbreviation as _register

    return _register(raw=raw, expansion=expansion, scope=scope, persist=persist)


def info() -> dict[str, Any]:
    """What Phase 1 this deployment is actually running. Never lies."""
    target = adapter_dir()
    detail: dict[str, Any] = {
        "enabled": bool(settings.extraction_enabled),
        "loaded": _engine is not None,
        "adapter": ADAPTER_NAME,
        "adapter_dir": str(target),
        "adapter_present": target.is_dir(),
        "base_model": settings.base_model_name,
        "max_new_tokens": settings.extraction_max_new_tokens,
        "canonical_fields": list(CANONICAL_FIELDS),
        "vendored_from": "backend/pipeline-one/inference_engine.py",
    }
    if _engine is not None:
        detail["device"] = getattr(_engine, "device", None)
        detail["device_name"] = getattr(_engine, "device_name", None)
        detail["vram_gb"] = getattr(_engine, "vram_gb", None)
        detail["total_vram_gb"] = getattr(_engine, "total_vram_gb", None)
    return detail


# --------------------------------------------------------------------------
# Reading an upload
# --------------------------------------------------------------------------

def row_to_composite_text(row) -> str:
    """Fold an entire spreadsheet row into one coherent string for the model.

    VENDORED from pipeline-one's app.py, unchanged. This is the step that makes
    column inference unnecessary: rather than guessing which column holds the
    description, every populated cell is written as `Header: value` behind the
    one cell that looks like a description, and the model reads the lot. A
    vendor export with columns nobody has seen before degrades into a longer
    sentence, not into a rejected file.
    """
    import pandas as pd

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


def read_upload(
    contents: bytes,
    filename: str,
    *,
    text_column: str | None = None,
    max_rows: int | None = 100,
) -> tuple[list[str], str]:
    """An uploaded file -> the strings to run the model over, and how they were built.

    Deliberately synchronous and deliberately done in the *request*, not in the
    background job: it is fast, it is what tells the caller how many rows there
    are, and a file that will not parse should be a 400 on the upload rather
    than a job that fails a second later.
    """
    import pandas as pd

    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            frame = pd.read_excel(io.BytesIO(contents))
        else:
            frame = pd.read_csv(io.BytesIO(contents))
    except Exception as exc:  # noqa: BLE001 - a bad file is the caller's problem
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"Failed to parse CSV/Excel file: {exc}",
        ) from exc

    if frame.empty:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST, "The file contains no rows."
        )

    if max_rows and max_rows > 0:
        frame = frame.iloc[:max_rows]

    # 1. An explicitly named column wins, when it exists.
    if text_column and text_column.strip() and text_column.strip() in frame.columns:
        column = text_column.strip()
        logger.info("Using requested column %r from %s", column, filename)
        return frame[column].fillna("").astype(str).tolist(), column

    # 2. Otherwise fold whole rows, so no column has to be identified at all.
    if len(frame.columns) > 1:
        logger.info(
            "Multi-column file (%d columns); synthesised composite rows from %s",
            len(frame.columns), filename,
        )
        return (
            [row_to_composite_text(row) for _, row in frame.iterrows()],
            f"Composite Whole Row ({len(frame.columns)} columns)",
        )

    column = str(frame.columns[0])
    return frame[column].fillna("").astype(str).tolist(), column


# --------------------------------------------------------------------------
# The background job
# --------------------------------------------------------------------------

#: Records handed to the engine per call.
#:
#: A multiple of five, and that is not arbitrary: the vendored `extract_batch`
#: clears the CUDA cache every fifth record, so chunking at 1 would silently
#: disable the memory hygiene that keeps a 4 GB card alive on a long file.
#:
#: Five is also the progress granularity - 100 updates over a 500-row file,
#: which is far finer than a client polling every 1-2 seconds can use.
EXTRACT_CHUNK_SIZE = 5


async def run_extraction(
    db: AsyncSession,
    context,
    *,
    texts: list[str],
    source_type: str,
    column_label: str | None = None,
    original_filename: str | None = None,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """Extract every string into a review session, reporting progress as it goes.

    The model call is unchanged - this still hands whole slices to the vendored
    `extract_batch`. What changed is only that the slices are taken on the event
    loop instead of in one blocking call, which buys three things for free:

      * progress a client can watch, committed per chunk;
      * records that land in the session as they are produced, so a poller can
        read the first 200 rows of a 500-row file without waiting for the rest;
      * a cancellation check between chunks.

    A failure part way leaves the session FAILED with the records it managed,
    and re-raises so the job records the error rather than swallowing it.
    """
    from app.services import sessions
    from app.services.jobs import run_blocking

    total = len(texts)
    session = await sessions.create_pending(
        db,
        source_type=source_type,
        total_records=total,
        original_filename=original_filename,
        adapter=ADAPTER_NAME,
        requested_by=requested_by,
        job_id=context.job_id,
    )
    await context.progress(db, 0, total, f"extracting {total} record(s)")

    try:
        for start in range(0, total, EXTRACT_CHUNK_SIZE):
            context.raise_if_cancelled()
            chunk = texts[start : start + EXTRACT_CHUNK_SIZE]

            try:
                records = await run_blocking(extract_batch, chunk)
            except ExtractionUnavailable as exc:
                # A missing adapter is a 503, not a 500, and moving the work
                # into the background must not downgrade that to "something
                # went wrong". The job runner keeps the status an HTTPException
                # carries, so the poller sees the same code and the same
                # message it would have got synchronously.
                raise HTTPException(
                    http_status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)
                ) from exc

            await sessions.append_records(
                db, session.id, records, chunk, start_index=start
            )
            done = min(start + len(chunk), total)
            await context.progress(db, done, total, f"extracted {done}/{total}")
    except Exception:
        await sessions.fail(db, session.id)
        raise

    await sessions.finish(db, session.id)
    stored = await sessions.get_session(db, session.id)

    if source_type == "text":
        # The single-record shape, unchanged.
        return {
            "session_id": stored.id,
            "record": sessions.record_to_dict(stored.records[0]),
        }

    return {
        "session_id": stored.id,
        "source_file": original_filename,
        "text_column_used": column_label,
        "total_records": stored.total_records,
        "records": [sessions.record_to_dict(r) for r in stored.records],
        "next_step": (
            f"Correct any wrong cells with PUT /extract/records/{stored.id}/"
            f"{{record_id}}, then POST /standardized/check with "
            f'{{"session_id": "{stored.id}"}} to find out which rows are new '
            f"material."
        ),
    }
