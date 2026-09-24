"""The boundary contract: what counts as a standard-format row.

These are the rules that let Phase 1 and the vector half be written, deployed
and changed independently. If one of them stops holding, rows start entering
the master under the wrong CPSE or with attributes silently dropped, and
neither failure is visible until somebody reconciles a catalogue by hand.
"""

from __future__ import annotations

import pytest

from app.logic.standard_format import (
    CANONICAL_FIELDS,
    RowFormatError,
    parse_row,
    to_standard_dict,
)
from app.logic.standardize import cpse_code_for, to_material


def test_canonical_fields_come_from_the_extraction_engine():
    """Not a local list. The engine that produces the format defines it, so the
    producer and the consumer cannot drift apart."""
    from app.logic import extraction

    assert list(CANONICAL_FIELDS) == list(extraction.CANONICAL_FIELDS)
    assert len(CANONICAL_FIELDS) == 8


def test_canonical_keys_are_accepted():
    row = parse_row({
        "Company": "NTPC",
        "Item Description (Raw)": "BALL BEARING 6205 2RS",
        "Item Code / Legacy Ref": "1001",
        "Quantity": 5,
        "UOM": "NOS",
        "Part Number / OEM Number": "6205",
        "Make / Brand": "SKF",
        "Specifications / Dimensions": "25X52X15",
    }, 1)
    assert row.description == "BALL BEARING 6205 2RS"
    assert row.legacy_code == "1001"
    assert row.part_number == "6205"


def test_snake_case_keys_are_accepted():
    row = parse_row({
        "company": "NTPC", "description": "GATE VALVE 2 INCH",
        "legacy_code": "2002", "part_number": "GV-2", "make": "AUDCO",
    }, 1)
    assert row.description == "GATE VALVE 2 INCH"
    assert row.make == "AUDCO"


def test_na_means_absent_not_a_value():
    """The engine writes "NA" for anything it could not ground in the input.
    Storing that literally would put the string NA into the master and, worse,
    into the vector."""
    row = parse_row({
        "Company": "NTPC", "Item Description (Raw)": "HEX BOLT M12",
        "Make / Brand": "NA", "Part Number / OEM Number": "N/A",
        "Specifications / Dimensions": "none",
    }, 1)
    assert row.make == ""
    assert row.part_number == ""
    assert row.specifications == ""


def test_forwarder_provenance_keys_are_ignored_not_rejected():
    """A forwarded review session attaches _record_id and friends to every
    record. A row that carries provenance is not a malformed row."""
    row = parse_row({
        "Company": "NTPC", "Item Description (Raw)": "V-BELT C 120",
        "_record_id": "rec_0001", "_is_modified": True, "_raw_input": "vbelt c120",
    }, 1)
    assert row.description == "V-BELT C 120"


def test_a_row_without_a_description_is_refused():
    with pytest.raises(RowFormatError, match="Item Description"):
        parse_row({"Company": "NTPC", "Quantity": 3}, 1)


def test_a_row_without_a_company_is_refused():
    with pytest.raises(RowFormatError, match="Company"):
        parse_row({"Item Description (Raw)": "HEX BOLT M12"}, 1)


def test_default_company_attributes_a_row_the_model_could_not_ground():
    row = parse_row(
        {"Item Description (Raw)": "HEX BOLT M12", "Company": "NA"},
        1, default_company="CPCL",
    )
    assert row.company == "CPCL"


def test_unknown_keys_never_overwrite_a_resolved_field():
    resolved = to_standard_dict({
        "Item Description (Raw)": "REAL DESCRIPTION",
        "Some Vendor Column": "NOISE",
    })
    assert resolved["description"] == "REAL DESCRIPTION"


def test_cpse_code_is_derived_not_stored_twice():
    assert cpse_code_for("Coal India (BCCL)") == "BCCL"
    assert cpse_code_for("NTPC") == "NTPC"
    # Anything not in the table falls through to "letters only, first six".
    assert cpse_code_for("Some New Corporation Ltd") == "SOMENE"
    assert cpse_code_for("") == "UNK"


def test_quantity_survives_being_a_string_or_a_number():
    assert to_material(parse_row(
        {"Company": "NTPC", "Item Description (Raw)": "X", "Quantity": "12"}, 1
    )).quantity == 12.0
    assert to_material(parse_row(
        {"Company": "NTPC", "Item Description (Raw)": "X", "Quantity": 12}, 1
    )).quantity == 12.0


def test_an_unparseable_quantity_is_none_not_an_error():
    """A CPSE extract carries "approx 50" and "as required". Those are not
    quantities, but they are also not a reason to reject the article."""
    material = to_material(parse_row(
        {"Company": "NTPC", "Item Description (Raw)": "X", "Quantity": "as required"}, 1
    ))
    assert material.quantity is None


def test_attributes_render_under_canonical_names():
    material = to_material(parse_row({
        "Company": "NTPC", "Item Description (Raw)": "BALL BEARING 6205",
        "Make / Brand": "SKF", "Part Number / OEM Number": "NA",
    }, 1))
    assert material.attributes["Make / Brand"] == "SKF"
    assert "Part Number / OEM Number" not in material.attributes
