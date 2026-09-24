"""
test_session_forwarder.py - Unit tests for SessionStore and PipelineForwarder.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure backend/pipeline-one is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from session_store import SessionStore
from forwarder import PipelineForwarder


def test_session_store_lifecycle(tmp_path):
    store = SessionStore(storage_dir=str(tmp_path))
    records = [
        {"Company": "HEC", "Item Description (Raw)": "BALL VALVE 1 INCH", "Quantity": 5, "UOM": "NOS"},
        {"Company": "ONGC", "Item Description (Raw)": "FLANGE SS316", "Quantity": 12, "UOM": "NOS"}
    ]
    session = store.create_session(source_type="csv", records=records, original_filename="test.csv")

    assert session.session_id.startswith("sess_")
    assert session.total_records == 2
    assert len(session.records) == 2

    # Verify retrieval
    retrieved = store.get_session(session.session_id)
    assert retrieved is not None
    assert retrieved.original_filename == "test.csv"

    # Verify record update
    rec1 = session.records[0]
    rec_id = rec1["record_id"]
    updated = store.update_record(session.session_id, rec_id, {"Quantity": 50, "UOM": "SET"})
    assert updated is not None
    assert updated["current"]["Quantity"] == 50
    assert updated["current"]["UOM"] == "SET"
    assert updated["is_modified"] is True
    assert updated["status"] == "reviewed"

    # Original predicted values remain preserved
    assert updated["predicted"]["Quantity"] == 5
    assert updated["predicted"]["UOM"] == "NOS"


def test_pipeline_forwarder_local_export(tmp_path):
    store = SessionStore(storage_dir=str(tmp_path))
    records = [{"Company": "NTPC", "Item Description (Raw)": "PIPE ELBOW", "Quantity": 10, "UOM": "NOS"}]
    session = store.create_session(source_type="text", records=records)

    output_dir = tmp_path / "output"
    forwarder = PipelineForwarder(session_store=store, output_dir=str(output_dir))

    res = forwarder.forward_session(session.session_id)
    assert res["success"] is True
    assert res["record_count"] == 1
    assert os.path.exists(res["json_path"])
    assert os.path.exists(res["csv_path"])

    # Check that session records marked as forwarded
    updated_session = store.get_session(session.session_id)
    assert updated_session.records[0]["status"] == "forwarded"


import httpx

@patch.object(httpx.Client, "post")
def test_pipeline_forwarder_with_webhook(mock_post, tmp_path):
    store = SessionStore(storage_dir=str(tmp_path))
    records = [{"Company": "GAIL", "Item Description (Raw)": "GAS REGULATOR", "Quantity": 2, "UOM": "NOS"}]
    session = store.create_session(source_type="text", records=records)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "received", "batch_id": "b_123"}
    mock_post.return_value = mock_resp

    forwarder = PipelineForwarder(session_store=store, output_dir=str(tmp_path / "output"))
    res = forwarder.forward_session(session.session_id, target_url="http://mock-next-pipeline:8000/api/ingest")

    assert res["success"] is True
    assert res["target_url"] == "http://mock-next-pipeline:8000/api/ingest"
    assert res["http_status"] == 200
    mock_post.assert_called_once()

