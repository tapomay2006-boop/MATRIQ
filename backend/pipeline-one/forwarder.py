"""
forwarder.py - Dispatches verified records to downstream pipeline & local archive.
Exports timestamped JSON and CSV to backend/pipeline-one/output/ and posts to NEXT_PIPELINE_URL.
"""

import os
import json
import time
import logging
import pandas as pd
from typing import Dict, Any, Optional
from pathlib import Path
import httpx

from session_store import SessionStore

logger = logging.getLogger(__name__)


class PipelineForwarder:
    """Handles dispatching verified CPSE material records to the next pipeline."""

    def __init__(
        self,
        session_store: SessionStore,
        output_dir: Optional[str] = None,
        default_target_url: Optional[str] = None,
    ):
        self.session_store = session_store
        self.output_dir = output_dir or str(Path(__file__).parent / "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.default_target_url = default_target_url or os.getenv("NEXT_PIPELINE_URL")

    def forward_session(
        self,
        session_id: str,
        target_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Export verified records to disk and forward via HTTP POST to downstream pipeline.
        Marks session records as 'forwarded'.
        """
        session = self.session_store.get_session(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")

        # Compile verified data
        verified_records = []
        for r in session.records:
            cur = dict(r["current"])
            cur["_record_id"] = r["record_id"]
            cur["_is_modified"] = r.get("is_modified", False)
            cur["_raw_input"] = r.get("raw_input", "")
            verified_records.append(cur)

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        base_filename = f"verified_{session_id}_{timestamp_str}"
        json_path = os.path.join(self.output_dir, f"{base_filename}.json")
        csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")

        # 1. Archive JSON
        export_payload = {
            "source_pipeline": "pipeline-one",
            "model": "qwen2.5-3b-cpse-lora-v2",
            "session_id": session_id,
            "exported_at": time.time(),
            "record_count": len(verified_records),
            "records": verified_records,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2, ensure_ascii=False)

        # 2. Archive CSV
        df = pd.DataFrame([r["current"] for r in session.records])
        df.to_csv(csv_path, index=False)

        # 3. Mark records as forwarded
        for r in session.records:
            r["status"] = "forwarded"
        self.session_store._save_session_to_disk(session)

        # 4. Optional HTTP Dispatch to next pipeline
        dest_url = target_url or self.default_target_url
        http_status = None
        http_response = None
        http_error = None

        if dest_url:
            logger.info(f"Forwarding {len(verified_records)} records to next pipeline: {dest_url}")
            try:
                with httpx.Client(timeout=timeout_seconds) as client:
                    resp = client.post(dest_url, json=export_payload)
                    http_status = resp.status_code
                    try:
                        http_response = resp.json()
                    except Exception:
                        http_response = resp.text
            except Exception as e:
                logger.error(f"Failed to post to downstream pipeline {dest_url}: {e}")
                http_error = str(e)

        return {
            "success": True,
            "session_id": session_id,
            "record_count": len(verified_records),
            "target_url": dest_url,
            "http_status": http_status,
            "http_response": http_response,
            "http_error": http_error,
            "json_path": json_path,
            "csv_path": csv_path,
            "json_filename": os.path.basename(json_path),
            "csv_filename": os.path.basename(csv_path),
        }
