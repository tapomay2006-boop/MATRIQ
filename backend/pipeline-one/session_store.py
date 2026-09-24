"""
session_store.py - Thread-safe review session and record store for Pipeline 1.
Tracks original model predictions, human edits, and review statuses.
"""

import os
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from threading import RLock


@dataclass
class RecordItem:
    record_id: str
    row_index: int
    raw_input: str
    predicted: Dict[str, Any]
    current: Dict[str, Any]
    is_modified: bool = False
    status: str = "pending_review"  # pending_review, reviewed, forwarded


@dataclass
class Session:
    session_id: str
    created_at: float
    source_type: str  # text, csv
    total_records: int
    original_filename: Optional[str] = None
    records: List[Dict[str, Any]] = field(default_factory=list)


class SessionStore:
    """In-memory and file-backed session manager for human review & editing."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir
        if self.storage_dir:
            os.makedirs(self.storage_dir, exist_ok=True)
        self._sessions: Dict[str, Session] = {}
        self._lock = RLock()


    def create_session(
        self,
        source_type: str,
        records: List[Dict[str, Any]],
        raw_texts: Optional[List[str]] = None,
        original_filename: Optional[str] = None,
    ) -> Session:
        """Initialize a new review session from extracted records."""
        with self._lock:
            session_id = f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            record_items = []

            for idx, rec in enumerate(records):
                rec_id = f"rec_{idx + 1:04d}"
                raw = raw_texts[idx] if (raw_texts and idx < len(raw_texts)) else ""
                # If raw is empty, build a readable synthetic prompt representation
                if not raw:
                    parts = [str(v) for k, v in rec.items() if v]
                    raw = " | ".join(parts)

                item = RecordItem(
                    record_id=rec_id,
                    row_index=idx + 1,
                    raw_input=raw,
                    predicted=dict(rec),
                    current=dict(rec),
                    is_modified=False,
                    status="pending_review",
                )
                record_items.append(asdict(item))

            session = Session(
                session_id=session_id,
                created_at=time.time(),
                source_type=source_type,
                total_records=len(record_items),
                original_filename=original_filename,
                records=record_items,
            )
            self._sessions[session_id] = session
            self._save_session_to_disk(session)
            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Fetch session by ID."""
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            # Try loading from disk if configured
            if self.storage_dir:
                file_path = os.path.join(self.storage_dir, f"{session_id}.json")
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            session = Session(**data)
                            self._sessions[session_id] = session
                            return session
                    except Exception:
                        return None
            return None

    def update_record(
        self,
        session_id: str,
        record_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Update specific attributes in a record.
        Marks record as modified and updates status to 'reviewed'.
        """
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return None

            for item in session.records:
                if item["record_id"] == record_id:
                    # Apply canonical field updates
                    for k, v in updates.items():
                        # Support both canonical naming and snake_case variants
                        canonical_k = k
                        if k == "item_description_raw":
                            canonical_k = "Item Description (Raw)"
                        elif k == "item_code_legacy_ref":
                            canonical_k = "Item Code / Legacy Ref"
                        elif k == "part_number_oem_number":
                            canonical_k = "Part Number / OEM Number"
                        elif k == "make_brand":
                            canonical_k = "Make / Brand"
                        elif k == "specifications_dimensions":
                            canonical_k = "Specifications / Dimensions"
                        elif k.lower() == "company":
                            canonical_k = "Company"
                        elif k.lower() == "quantity":
                            canonical_k = "Quantity"
                        elif k.lower() == "uom":
                            canonical_k = "UOM"

                        # Normalize null/empty/na to 'NA'
                        if v is None or str(v).strip().lower() in ["none", "null", "", "na", "n/a", "unknown"]:
                            v = "NA"

                        # Type casting for Quantity
                        if canonical_k == "Quantity" and v != "NA":
                            try:
                                v = int(float(v))
                            except Exception:
                                v = "NA"

                        item["current"][canonical_k] = v

                    item["is_modified"] = True
                    item["status"] = "reviewed"
                    self._save_session_to_disk(session)
                    return item

            return None

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List summary of all sessions."""
        with self._lock:
            summaries = []
            for s in self._sessions.values():
                summaries.append({
                    "session_id": s.session_id,
                    "created_at": s.created_at,
                    "source_type": s.source_type,
                    "total_records": s.total_records,
                    "original_filename": s.original_filename,
                })
            return sorted(summaries, key=lambda x: x["created_at"], reverse=True)

    def _save_session_to_disk(self, session: Session) -> None:
        """Persist session JSON to disk if storage_dir is active."""
        if not self.storage_dir:
            return
        try:
            file_path = os.path.join(self.storage_dir, f"{session.session_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(asdict(session), f, indent=2, ensure_ascii=False)
        except Exception:
            pass
