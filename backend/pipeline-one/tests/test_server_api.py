"""
test_server_api.py - Unit and endpoint tests for Pipeline 1 FastAPI server.
"""

import os
import io
import sys
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure backend/pipeline-one is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, engine, session_store, forwarder

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["model"] == "qwen2.5-3b-cpse-lora-v2"
    assert "device" in data


def test_extract_text_flow():
    # Mock inference engine to avoid heavy model execution during unit test
    with patch.object(engine, "extract_single") as mock_extract:
        mock_extract.return_value = {
            "Company": "BHEL",
            "Item Description (Raw)": "PUMP SHAFT 50MM",
            "Item Code / Legacy Ref": "BHEL-99231",
            "Quantity": 3,
            "UOM": "NOS",
            "Part Number / OEM Number": "PS-50",
            "Make / Brand": "BHEL",
            "Specifications / Dimensions": "Dia: 50mm",
        }

        res = client.post("/api/v1/extract/text", json={"text": "BHEL PUMP SHAFT 50MM 3 NOS"})
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "record" in data
        rec = data["record"]
        assert rec["current"]["Company"] == "BHEL"
        assert rec["current"]["Quantity"] == 3
        assert rec["is_modified"] is False

        # Test Editing Record
        sess_id = data["session_id"]
        rec_id = rec["record_id"]
        edit_res = client.put(f"/api/v1/records/{sess_id}/{rec_id}", json={"quantity": 10, "uom": "SET"})
        assert edit_res.status_code == 200
        updated = edit_res.json()["record"]
        assert updated["current"]["Quantity"] == 10
        assert updated["current"]["UOM"] == "SET"
        assert updated["is_modified"] is True
        assert updated["status"] == "reviewed"


def test_extract_csv_flow():
    with patch.object(engine, "extract_single") as mock_extract:
        mock_extract.side_effect = [
            {"Company": "ONGC", "Item Description (Raw)": "GATE VALVE", "Quantity": 5, "UOM": "NOS"},
            {"Company": "NTPC", "Item Description (Raw)": "PIPE TEE", "Quantity": 20, "UOM": "NOS"},
        ]

        csv_content = (
            "RAW_CATALOG_TEXT\n"
            "ONGC GATE VALVE 5 NOS\n"
            "NTPC PIPE TEE 20 NOS\n"
        )
        files = {"file": ("test_catalog.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
        res = client.post("/api/v1/extract/csv", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["total_records"] == 2
        assert len(data["records"]) == 2
        assert data["records"][0]["current"]["Company"] == "ONGC"
        assert data["records"][1]["current"]["Company"] == "NTPC"


def test_extract_csv_multi_column_row_synthesis():
    import pandas as pd
    from app import row_to_composite_text

    # Test unit row_to_composite_text
    row_series = pd.Series({
        "item_name": "BALL VALVE 1 INCH SS316",
        "company": "BHEL",
        "qty": 10,
        "uom": "NOS",
        "make": "L&T",
        "extra_info": "High Pressure 1000 WOG",
        "empty_col": None,
        "Unnamed: 6": "unnamed value",
    })
    composite = row_to_composite_text(row_series)
    assert "BALL VALVE 1 INCH SS316." in composite
    assert "company: BHEL." in composite
    assert "qty: 10." in composite
    assert "uom: NOS." in composite
    assert "make: L&T." in composite
    assert "extra_info: High Pressure 1000 WOG." in composite
    assert "Unnamed" not in composite
    assert "empty_col" not in composite

    # Test API endpoint handling multi-column CSV
    with patch.object(engine, "extract_single") as mock_extract:
        mock_extract.return_value = {
            "Company": "BHEL",
            "Item Description (Raw)": "BALL VALVE 1 INCH SS316",
            "Item Code / Legacy Ref": "NA",
            "Quantity": 10,
            "UOM": "NOS",
            "Part Number / OEM Number": "NA",
            "Make / Brand": "L&T",
            "Specifications / Dimensions": "High Pressure 1000 WOG",
        }

        multi_csv = (
            "Item_Name,Company,Qty,UOM,Make,PO_No\n"
            "BALL VALVE 1 INCH SS316,BHEL,10,NOS,L&T,PO-98765\n"
        )
        files = {"file": ("vendor_tender.csv", io.BytesIO(multi_csv.encode("utf-8")), "text/csv")}
        res = client.post("/api/v1/extract/csv", files=files)
        assert res.status_code == 200
        data = res.json()
        assert "Composite Whole Row (6 columns)" in data["text_column_used"]
        assert data["total_records"] == 1
        
        # Verify that extract_single received the combined multi-attribute input string
        called_arg = mock_extract.call_args[0][0]
        assert "BALL VALVE 1 INCH SS316." in called_arg
        assert "Company: BHEL." in called_arg
        assert "Qty: 10." in called_arg
        assert "PO_No: PO-98765." in called_arg


def test_add_abbreviation_api():
    res = client.post("/api/v1/taxonomy/abbreviations", json={
        "raw": "TEST_ABBR",
        "expansion": "TEST EXPANSION TERM",
        "persist": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["raw"] == "TEST_ABBR"
    assert data["expansion"] == "TEST EXPANSION TERM"


def test_forward_pipeline_flow(tmp_path):
    # Setup dummy session
    session = session_store.create_session("text", [{"Company": "GAIL", "Item Description (Raw)": "PIPE"}])
    forwarder.output_dir = str(tmp_path)

    res = client.post("/api/v1/pipeline/forward", json={"session_id": session.session_id})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["record_count"] == 1
    assert os.path.exists(data["json_path"])


def test_ui_and_static_files():
    res = client.get("/")
    assert res.status_code == 200
    assert "CPSE Material Master Studio" in res.text

    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200
    assert "var(--bg-primary)" in css_res.text

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "handleExtractSingle" in js_res.text

