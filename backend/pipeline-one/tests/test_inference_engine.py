"""
test_inference_engine.py - Unit tests for Qwen2.5-3B LoRA Inference Engine & Canonical Mapping.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure backend/pipeline-one is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from inference_engine import QwenLoraEngine, KEY_MAP, resolve_canonical_dict, clean_str, token_f1


def test_clean_str():
    assert clean_str("  Coal India (BCCL). ") == "coal india (bccl)"
    assert clean_str("NaN") == ""
    assert clean_str("null") == ""
    assert clean_str(None) == ""


def test_token_f1():
    assert token_f1("BALL VALVE 1 INCH", "ball valve 1 inch") == 1.0
    assert token_f1("", "") == 1.0
    assert token_f1("BALL VALVE", "GATE VALVE") > 0.0
    assert token_f1("ALPHA", "BETA") == 0.0


def test_resolve_canonical_dict():
    raw_pred = {
        "Company": "NTPC",
        "Item Description": "BALL VALVE 1 INCH",
        "Item Code": "BHEL-12345",
        "Qty": "500 NOS",
        "Part Number": "CAT-100",
        "Make": "AUDCO",
        "Specs": "Dim: 25mm"
    }
    canonical = resolve_canonical_dict(raw_pred)
    assert canonical["Company"] == "NTPC"
    assert canonical["Item Description (Raw)"] == "BALL VALVE 1 INCH"
    assert canonical["Item Code / Legacy Ref"] == "BHEL-12345"
    assert canonical["Quantity"] == 500
    assert canonical["UOM"] == "NOS"
    assert canonical["Part Number / OEM Number"] == "CAT-100"
    assert canonical["Make / Brand"] == "AUDCO"
    assert canonical["Specifications / Dimensions"] == "Dim: 25mm"


def test_resolve_canonical_dict_with_nested_qty():
    raw_pred = {
        "Company": "ONGC",
        "Item Description (Raw)": "GASKET RUBBER",
        "Quantity": {"Number": 25, "Unit": "SET"}
    }
    canonical = resolve_canonical_dict(raw_pred)
    assert canonical["Company"] == "ONGC"
    assert canonical["Item Description (Raw)"] == "GASKET RUBBER"
    assert canonical["Quantity"] == 25
    assert canonical["UOM"] == "SET"
    # Unmentioned fields must be "NA"
    assert canonical["Item Code / Legacy Ref"] == "NA"
    assert canonical["Part Number / OEM Number"] == "NA"
    assert canonical["Make / Brand"] == "NA"
    assert canonical["Specifications / Dimensions"] == "NA"


def test_engine_extract_single():
    engine = QwenLoraEngine(adapter_dir="backend/pipeline-one/models/qwen2.5-3b-cpse-lora-v2")
    engine.tokenizer = MagicMock()
    engine.model = MagicMock()
    # Mock tokenizer output format
    engine.tokenizer.return_value = {"input_ids": MagicMock(shape=[1, 10])}
    engine.model.generate.return_value = [[0] * 20]
    engine.tokenizer.decode.return_value = '{"Company": "ONGC", "Item Description (Raw)": "GASKET", "Quantity": 10, "UOM": "NOS"}'
    engine.load_model = MagicMock()

    result = engine.extract_single("ONGC GASKET 10 NOS")
    assert result["Company"] == "ONGC"
    assert result["Item Description (Raw)"] == "GASKET"
    assert result["Quantity"] == 10
    assert result["UOM"] == "NOS"
    # Fields not in text must be "NA"
    assert result["Item Code / Legacy Ref"] == "NA"
    assert result["Part Number / OEM Number"] == "NA"
    assert result["Make / Brand"] == "NA"
    assert result["Specifications / Dimensions"] == "NA"


def test_engine_eliminates_hallucinated_attributes():
    engine = QwenLoraEngine(adapter_dir="backend/pipeline-one/models/qwen2.5-3b-cpse-lora-v2")
    engine.tokenizer = MagicMock()
    engine.model = MagicMock()
    engine.tokenizer.return_value = {"input_ids": MagicMock(shape=[1, 10])}
    engine.model.generate.return_value = [[0] * 20]
    # Simulate model hallucinating fields not present in user text
    engine.tokenizer.decode.return_value = json.dumps({
        "Company": "GAIL",
        "Item Description (Raw)": "BALL VALVE 1 INCH SS316 1000 WOG",
        "Item Code / Legacy Ref": "NTPC-254798",
        "Quantity": 11411,
        "UOM": "NOS",
        "Part Number / OEM Number": "CAT-500",
        "Make / Brand": "L&T",
        "Specifications / Dimensions": "As per standard IS/ISO specifications. 120mm, Mat: MS.."
    })
    engine.load_model = MagicMock()

    # User input contains NO company, NO item code, NO quantity, NO uom, NO part number, NO make
    result = engine.extract_single("BALL VALVE 1 INCH SS316 1000 WOG")
    assert result["Company"] == "NA"
    assert result["Item Code / Legacy Ref"] == "NA"
    assert result["Quantity"] == "NA"
    assert result["UOM"] == "NA"
    assert result["Part Number / OEM Number"] == "NA"
    assert result["Make / Brand"] == "NA"
    # Description is preserved and standardized
    assert "BALL VALVE" in result["Item Description (Raw)"]


def test_isolate_core_description_from_raw_input():
    engine = QwenLoraEngine(adapter_dir="backend/pipeline-one/models/qwen2.5-3b-cpse-lora-v2")
    engine.tokenizer = MagicMock()
    engine.model = MagicMock()
    engine.tokenizer.return_value = {"input_ids": MagicMock(shape=[1, 10])}
    engine.model.generate.return_value = [[0] * 20]
    # Simulate model echoing entire input into Item Description (Raw)
    raw_input = "ONGC filter Lube_OIL 13751 NOS"
    engine.tokenizer.decode.return_value = json.dumps({
        "Company": "ONGC",
        "Item Description (Raw)": raw_input,
        "Item Code / Legacy Ref": "NA",
        "Quantity": 13751,
        "UOM": "NOS",
        "Part Number / OEM Number": "NA",
        "Make / Brand": "NA",
        "Specifications / Dimensions": "NA"
    })
    engine.load_model = MagicMock()

    result = engine.extract_single(raw_input)
    assert result["Company"] == "ONGC"
    assert result["Quantity"] == 13751
    assert result["UOM"] == "NOS"
    # Specifically core item description, not the raw input with ONGC and 13751 NOS
    assert result["Item Description (Raw)"] == "filter Lube_OIL"


def test_expand_abbreviations_known_dictionary():
    from inference_engine import expand_abbreviations

    # Standard CPSE abbreviations
    text = "VLV GT VLV ALM FLG SS CS BRG GSKT"
    expanded = expand_abbreviations(text)
    assert "GATE VALVE" in expanded
    assert "ALUMINIUM" in expanded
    assert "FLANGE" in expanded
    assert "STAINLESS STEEL" in expanded
    assert "CARBON STEEL" in expanded
    assert "BEARING" in expanded
    assert "GASKET" in expanded

    # Boundary safety: should NOT replace parts of words like 'EVOLVE' or 'ALMOST'
    assert expand_abbreviations("DO NOT EVOLVE ALMOST ANYTHING") == "DO NOT EVOLVE ALMOST ANYTHING"


def test_expand_abbreviations_safe_preservation():
    from inference_engine import expand_abbreviations

    # Unknown or ambiguous code should be safely preserved
    text = "CUSTOM CODE UNKNOWN_XYZ-99"
    assert expand_abbreviations(text) == "CUSTOM CODE UNKNOWN_XYZ-99"


def test_engine_extract_single_standardizes_abbreviations():
    engine = QwenLoraEngine(adapter_dir="backend/pipeline-one/models/qwen2.5-3b-cpse-lora-v2")
    engine.tokenizer = MagicMock()
    engine.model = MagicMock()
    engine.tokenizer.return_value = {"input_ids": MagicMock(shape=[1, 10])}
    engine.model.generate.return_value = [[0] * 20]
    engine.tokenizer.decode.return_value = json.dumps({
        "Company": "BHEL",
        "Item Description (Raw)": "GT VLV 2 INCH ALM",
        "Item Code / Legacy Ref": "NA",
        "Quantity": 5,
        "UOM": "NOS",
        "Part Number / OEM Number": "NA",
        "Make / Brand": "NA",
        "Specifications / Dimensions": "BODY SS316"
    })
    engine.load_model = MagicMock()

    result = engine.extract_single("BHEL GT VLV 2 INCH ALM BODY SS316 5 NOS")
    assert result["Company"] == "BHEL"
    # "GT VLV" -> "GATE VALVE", "ALM" -> "ALUMINIUM"
    assert "GATE VALVE" in result["Item Description (Raw)"]
    assert "ALUMINIUM" in result["Item Description (Raw)"]
    # "SS" -> "STAINLESS STEEL"
    assert "STAINLESS STEEL" in result["Specifications / Dimensions"]


def test_register_abbreviation_active_learning():
    from inference_engine import register_abbreviation, expand_abbreviations

    register_abbreviation("CUST_VALV", "CUSTOM ROTARY VALVE", persist=False)
    assert expand_abbreviations("PART CUST_VALV 50MM") == "PART CUSTOM ROTARY VALVE 50MM"



