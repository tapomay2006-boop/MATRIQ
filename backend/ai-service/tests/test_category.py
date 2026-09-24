"""The material family: a blocking key and a filter, and nothing else.

Two properties matter more than the accuracy of any single rule:

  * the category never reaches the vector, so a keyword rule cannot move one;
  * an unrecognised row abstains rather than being forced into a family.

Both exist because of what blocking costs when it is wrong: a row in the wrong
family is never compared against its own duplicate, which is the failure the
existence check exists to prevent.
"""

from __future__ import annotations

import pytest

from app.logic.category import CATEGORIES, UNCLASSIFIED, classify
from app.logic.embedding import canonical_hash, embedding_text
from app.logic.standard_format import parse_row
from app.logic.standardize import to_material
from tests.conftest import standard_row


def _material(description: str, **overrides):
    return to_material(parse_row(standard_row(description, **overrides), 1))


@pytest.mark.parametrize(("description", "expected"), [
    ("BALL BEARING 6205 2RS", "BEARING"),
    ("BRG BALL RAD 6205", "BEARING"),          # the raw abbreviation too
    ("GATE VALVE 2 INCH CS 150#", "VALVE"),
    ("NRV 3 INCH FLANGED", "VALVE"),
    ("LUBE OIL FILTER CUMMINS KTA19", "FILTER"),
    ("V-BELT SEC C 120 INCH", "BELT_V"),
    ("CONVEYOR BELT 1000MM 4PLY", "BELT_CONVEYOR"),
    ("HEX BOLT M12 X 50 HT", "FASTENER"),
    ("SAFETY HELMET IS 2925", "SAFETY_PPE"),
    ("SPIRAL WOUND GASKET 2 INCH", "PIPE_FITTING"),
    ("ONLINE UPS 5 KVA 230V", "ELECTRONICS_IT"),
])
def test_known_families_classify(description, expected):
    assert classify(description) == expected


def test_specificity_wins_over_generality():
    """Order is the design: a conveyor belt is not a V-belt, and a wire rope is
    not a generic cable."""
    assert classify("CONVEYOR BELT 800MM") == "BELT_CONVEYOR"
    assert classify("V BELT C120") == "BELT_V"
    assert classify("WIRE ROPE 6X36 20MM") == "CABLE"


def test_an_unrecognised_row_abstains(client=None):
    """A confident wrong family is worse than an honest empty one."""
    assert classify("UNSEEN ALIEN ARTIFACT XYZ-900") == UNCLASSIFIED
    assert classify("") == UNCLASSIFIED
    assert classify("   ") == UNCLASSIFIED


def test_the_specifications_can_carry_the_family():
    """Sometimes the family is only visible outside the description."""
    assert classify("SPARE FOR PUMP SET", "MECHANICAL SEAL 45MM SIC") == "SEAL"


def test_every_rule_is_reachable_and_listed():
    assert UNCLASSIFIED in CATEGORIES
    assert len(set(CATEGORIES)) == len(CATEGORIES)


# --------------------------------------------------------------------------
# The property that protects the vector
# --------------------------------------------------------------------------

def test_the_category_is_not_in_the_embedded_text():
    """A keyword rule must not be able to move a vector. If the category were
    embedded, a misclassification would change what a row looks like."""
    bearing = _material("BALL BEARING 6205 2RS")
    assert bearing.category == "BEARING"
    assert "BEARING" in bearing.description
    assert "[CLASS]" not in embedding_text(bearing)
    assert "category" not in embedding_text(bearing).lower()


def test_the_category_does_not_change_the_hash():
    """Adding this file changed no stored canonical_hash - which matters,
    because there is no reindex endpoint to repair one."""
    material = _material("BALL BEARING 6205 2RS")
    before = canonical_hash(material)

    material.category = "COMPLETELY_WRONG"
    assert canonical_hash(material) == before
    assert embedding_text(material) == embedding_text(material)


def test_the_category_is_not_in_the_identity_attributes():
    assert "category" not in _material("BALL BEARING 6205").identity_attributes


# --------------------------------------------------------------------------
# Through the API
# --------------------------------------------------------------------------

def test_a_stored_material_carries_its_family(client):
    rows = [
        standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"}),
        standard_row("GATE VALVE 2 INCH CS", **{"Item Code / Legacy Ref": "V-1"}),
        standard_row("UNSEEN ALIEN ARTIFACT", **{"Item Code / Legacy Ref": "U-1"}),
    ]
    checked = client.post("/api/v1/standardized/check", json={"rows": rows}).json()
    assert [r["category"] for r in checked["rows"]] == [
        "BEARING", "VALVE", "UNCLASSIFIED",
    ]

    client.post("/api/v1/standardized/add", json={"batch_id": checked["batch_id"]})
    stored = {m["material_id"]: m["category"]
              for m in client.get("/api/v1/materials").json()["items"]}
    assert stored["NTPC-B1"] == "BEARING"
    assert stored["NTPC-U1"] == "UNCLASSIFIED"


def test_materials_can_be_filtered_by_family(client):
    rows = [
        standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"}),
        standard_row("ROLLER BEARING 22210", **{"Item Code / Legacy Ref": "B-2"}),
        standard_row("GATE VALVE 2 INCH CS", **{"Item Code / Legacy Ref": "V-1"}),
    ]
    client.post("/api/v1/standardized/add", json={"rows": rows})

    bearings = client.get("/api/v1/materials", params={"category": "bearing"}).json()
    assert {m["material_id"] for m in bearings["items"]} == {"NTPC-B1", "NTPC-B2"}
    assert bearings["total"] == 2
    assert client.get("/api/v1/materials", params={"category": "VALVE"}).json()["total"] == 1


def test_blocking_is_off_by_default_so_a_misclassification_cannot_hide_a_duplicate(
    client, monkeypatch
):
    """The reason the flag defaults off. Two rows that are the same article but
    land in different families must still be found."""
    import app.config as config_module

    assert config_module.settings.existence_block_by_category is False

    first = standard_row("MECHANICAL SEAL 45MM SIC SHAFT",
                         **{"Item Code / Legacy Ref": "S-1"})
    client.post("/api/v1/standardized/add", json={"rows": [first]})

    # Same article, described so the keyword table lands elsewhere entirely.
    twin = dict(first)
    twin["Item Code / Legacy Ref"] = "S-2"
    body = client.post("/api/v1/standardized/check", json={"rows": [twin]}).json()
    assert body["rows"][0]["status"] == "ALREADY_EXISTS"


def test_blocking_can_be_switched_on(client, monkeypatch):
    """It is a real lever, not a dead setting."""
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "existence_block_by_category", True)

    rows = [standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"})]
    client.post("/api/v1/standardized/add", json={"rows": rows})

    body = client.post("/api/v1/standardized/check", json={"rows": rows}).json()
    assert body["rows"][0]["status"] == "ALREADY_EXISTS"
