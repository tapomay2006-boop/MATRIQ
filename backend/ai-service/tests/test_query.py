"""What a search query becomes before anything is embedded or looked up.

Two properties are load-bearing: technical tokens survive preprocessing
untouched, and identifier detection is conservative - a bare `6205` is a
bearing size, not a code.
"""

from __future__ import annotations

import pytest

from app.logic.query import (
    identifier_tokens,
    identifier_variants,
    is_identifier_like,
    prepare,
    preprocess,
)


@pytest.mark.parametrize(
    "token", ["120", "1200", "6205", "M10", "C", "DN50", "1200MM", "415V", "2KW"]
)
def test_technical_parameters_are_not_identifiers(token):
    assert is_identifier_like(token) is False


@pytest.mark.parametrize(
    "token", ["M-55321", "224411", "NTPC-M-55321", "MAT4285270", "NMM-00000042", "PN-2409-B"]
)
def test_codes_are_identifiers(token):
    assert is_identifier_like(token) is True


def test_preprocess_keeps_numbers_units_and_codes():
    text = preprocess("V BELT C 120, length 1200 mm, width 17 mm, hex bolt M10 x 50, DN50")
    for kept in ("C 120", "1200 MM", "17 MM", "M10 X 50", "DN50"):
        assert kept in text


def test_preprocess_expands_the_same_abbreviations_phase_one_does():
    assert preprocess("brg ball rad 6205 2rs") == "BEARING BALL RADIAL 6205 2RS"


def test_preprocess_drops_trailing_procurement_noise_only():
    assert preprocess("gate valve 2 inch - URGENT REQ") == "GATE VALVE 2 INCH"
    assert preprocess("v belt c-120 **OEM ONLY**") == "V BELT C-120"


def test_preprocess_of_nothing_is_empty():
    assert preprocess("") == ""
    assert preprocess("   \n ") == ""
    assert prepare("  ").is_empty


def test_identifier_only_query():
    assert prepare("M-55321").identifier_only is True
    assert prepare("NTPC-M-55321 224411").identifier_only is True
    assert prepare("V belt C 120 M-55321").identifier_only is False
    assert prepare("V BELT").identifier_only is False


def test_identifiers_are_pulled_from_mixed_text_in_order():
    prepared = prepare("V belt C section, 1200mm, conveyor drive, NTPC code M-55321 or 224411")
    assert prepared.identifiers == ["M-55321", "224411"]
    assert identifier_tokens("nothing here 120 mm") == []


def test_identifier_variants_cover_how_material_ids_are_built():
    """`M-55321` is stored as legacy code `M-55321` and material id `NTPC-M55321`."""
    assert "M55321" in identifier_variants("M-55321")
    assert "NTPC-M55321" in identifier_variants("NTPC-M-55321")
    assert identifier_variants("224411") == ["224411"]
