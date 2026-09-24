"""The national id: the one identifier the master owns.

    material_id   {CPSE}-{legacy code}   the CPSE's identity for the row
    national_id   NMM-00000001           the nation's

Every property here exists because of the difference between those two: a
CPSE can re-code its catalogue, two CPSEs code the same article differently,
and neither is a fact about the article itself. The national id is allocated
by this service, at admission, before the vector is written, and it never
derives from anything a CPSE controls.
"""

from __future__ import annotations

import pytest

from app.logic.national_id import format_national_id, is_national_id, parse_national_id
from tests.conftest import standard_row


def _add(client, rows):
    body = client.post("/api/v1/standardized/add", json={"rows": rows}).json()
    assert body["added"] == len(rows), body
    return body


# --------------------------------------------------------------------------
# The pattern
# --------------------------------------------------------------------------

def test_the_pattern_is_prefix_dash_zero_padded_sequence():
    assert format_national_id(1) == "NMM-00000001"
    assert format_national_id(42) == "NMM-00000042"
    assert format_national_id(99_999_999) == "NMM-99999999"


def test_ids_sort_as_strings_the_way_they_sort_as_numbers():
    """Fixed width is what makes a UI column stay put."""
    ids = [format_national_id(n) for n in (9, 10, 100, 2, 1)]
    assert sorted(ids) == [format_national_id(n) for n in (1, 2, 9, 10, 100)]


def test_a_sequence_starts_at_one():
    with pytest.raises(ValueError):
        format_national_id(0)


def test_national_and_material_ids_are_told_apart():
    """`NTPC-1001` is a material id even though its code is all digits. The
    predicate is strict on the configured prefix so it cannot be fooled."""
    assert is_national_id("NMM-00000001")
    assert parse_national_id("NMM-00000042") == 42
    assert not is_national_id("NTPC-1001")
    assert not is_national_id("NTPC-00000001")     # right shape, wrong prefix
    assert not is_national_id("NMM-1")             # right prefix, wrong width
    assert not is_national_id("CCL-116045321-7d31c0")
    assert parse_national_id("NTPC-1001") is None


def test_an_id_issued_under_an_old_prefix_is_still_found(client, monkeypatch):
    """The lookup checks both columns regardless of the pattern check, so a
    prefix change never orphans ids already issued."""
    import app.config as config_module

    _add(client, [standard_row("A ITEM", **{"Item Code / Legacy Ref": "1"})])
    monkeypatch.setattr(config_module.settings, "national_id_prefix", "IND")

    assert not is_national_id("NMM-00000001")                       # no longer current
    assert client.get("/api/v1/materials/NMM-00000001").status_code == 200   # still found


def test_the_prefix_is_configuration(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "national_id_prefix", "IND")
    monkeypatch.setattr(config_module.settings, "national_id_digits", 6)
    assert format_national_id(7) == "IND-000007"


# --------------------------------------------------------------------------
# Allocation
# --------------------------------------------------------------------------

def test_every_admitted_row_gets_one(client):
    body = _add(client, [
        standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"}),
        standard_row("GATE VALVE 2 INCH CS",
                     **{"Company": "BHEL", "Item Code / Legacy Ref": "V-1"}),
    ])
    assert body["national_ids"] == ["NMM-00000001", "NMM-00000002"]
    assert [m["national_id"] for m in body["materials"]] == body["national_ids"]


def test_ids_are_sequential_across_batches(client):
    """The counter is the master's, not the batch's: the second batch carries
    on from where the first stopped."""
    _add(client, [standard_row("A ITEM", **{"Item Code / Legacy Ref": "1"})])
    second = _add(client, [
        standard_row("B ITEM", **{"Item Code / Legacy Ref": "2"}),
        standard_row("C ITEM", **{"Item Code / Legacy Ref": "3"}),
    ])
    assert second["national_ids"] == ["NMM-00000002", "NMM-00000003"]


def test_ids_are_unique_and_never_reused(client):
    """A deleted material's id is retired, not recycled. Reissuing it would
    let an old reference point at a different article."""
    _add(client, [standard_row("A ITEM", **{"Item Code / Legacy Ref": "1"})])
    client.delete("/api/v1/materials/NTPC-1")

    again = _add(client, [standard_row("A ITEM", **{"Item Code / Legacy Ref": "1"})])
    assert again["national_ids"] == ["NMM-00000002"]

    listed = client.get("/api/v1/materials").json()["items"]
    assert len({m["national_id"] for m in listed}) == len(listed)


def test_the_id_does_not_depend_on_the_cpse_or_its_code(client):
    """Two CPSEs, wildly different coding styles, one sequence."""
    body = _add(client, [
        standard_row("ITEM ONE", **{"Company": "NTPC", "Item Code / Legacy Ref": "1001"}),
        standard_row("ITEM TWO", **{"Company": "Coal India (BCCL)",
                                    "Item Code / Legacy Ref": "116045321"}),
        standard_row("ITEM THREE", **{"Company": "HEC", "Item Code / Legacy Ref": "N/A"}),
    ])
    assert body["material_ids"][0].startswith("NTPC-")
    assert body["material_ids"][1].startswith("BCCL-")
    assert body["material_ids"][2].startswith("HEC-X")        # no code -> content hash
    assert body["national_ids"] == ["NMM-00000001", "NMM-00000002", "NMM-00000003"]


def test_a_failed_add_issues_no_visible_id(client):
    """The allocation is inside the transaction. If the vector store refuses
    the write, the row is rolled back and no material carries the id."""
    from app.logic import retrieval

    class Refuses:
        def ensure_collection(self, **_): raise RuntimeError("connection refused")

    keep, retrieval._store = retrieval._store, Refuses()
    try:
        response = client.post("/api/v1/standardized/add", json={
            "rows": [standard_row("DOOMED", **{"Item Code / Legacy Ref": "D-1"})],
        })
    finally:
        retrieval._store = keep
    assert response.status_code == 503
    assert client.get("/api/v1/materials").json()["total"] == 0


# --------------------------------------------------------------------------
# Where it lives
# --------------------------------------------------------------------------

def test_it_is_on_the_row_and_in_the_vector_payload(client):
    """Stored before the vector is written, and travelling with it."""
    from app.logic import retrieval

    _add(client, [standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"})])

    row = client.get("/api/v1/materials/NTPC-B1").json()
    assert row["national_id"] == "NMM-00000001"

    point = retrieval.get_store()._points["NTPC-B1"]
    assert point.national_id == "NMM-00000001"
    assert point.payload()["national_id"] == "NMM-00000001"


def test_it_is_not_in_the_embedded_text(client):
    """An identifier must not move a vector."""
    _add(client, [standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"})])
    from app.logic import retrieval

    assert "NMM" not in retrieval.get_store()._points["NTPC-B1"].canonical_description


def test_a_material_can_be_fetched_by_either_identity(client):
    _add(client, [standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"})])

    by_material = client.get("/api/v1/materials/NTPC-B1").json()
    by_national = client.get("/api/v1/materials/NMM-00000001").json()
    assert by_material == by_national
    assert by_national["material_id"] == "NTPC-B1"
    assert by_national["national_id"] == "NMM-00000001"


def test_a_material_can_be_deleted_by_national_id(client):
    from app.logic import retrieval

    _add(client, [standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "B-1"})])
    response = client.delete("/api/v1/materials/NMM-00000001")
    assert response.status_code == 200
    assert response.json()["material_id"] == "NTPC-B1"
    assert response.json()["national_id"] == "NMM-00000001"
    assert retrieval.get_store().count() == 0


def test_the_listing_is_in_national_order_and_filterable_by_it(client):
    _add(client, [
        standard_row("Z ITEM", **{"Item Code / Legacy Ref": "9"}),
        standard_row("A ITEM", **{"Item Code / Legacy Ref": "1"}),
    ])
    page = client.get("/api/v1/materials").json()
    assert [m["national_id"] for m in page["items"]] == ["NMM-00000001", "NMM-00000002"]

    one = client.get("/api/v1/materials", params={"national_id": "NMM-00000002"}).json()
    assert one["total"] == 1
    assert one["items"][0]["description"] == "A ITEM"

    found = client.get("/api/v1/materials", params={"query": "nmm-00000001"}).json()
    assert found["total"] == 1


def test_the_id_is_audited_on_add_and_delete(client):
    import anyio
    from sqlalchemy import select

    import app.database as db_module
    from app.models.material import AuditLog

    _add(client, [standard_row("A ITEM", **{"Item Code / Legacy Ref": "1"})])
    client.delete("/api/v1/materials/NMM-00000001", params={"actor": "asha"})

    async def _details():
        async with db_module.AsyncSessionLocal() as db:
            rows = await db.execute(select(AuditLog).order_by(AuditLog.occurred_at))
            return [(r.action, r.detail) for r in rows.scalars().all()]

    entries = anyio.run(_details)
    assert any(a == "ADD_NEW_MATERIAL" and "NMM-00000001" in d for a, d in entries)
    assert any(a == "DELETE_MATERIAL" and "NMM-00000001" in d for a, d in entries)
