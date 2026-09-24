"""The three /materials endpoints, each with one job.

    GET    /materials                 what the vector DB holds, ten at a time
    GET    /materials/{material_id}   one row by id
    DELETE /materials/{material_id}   remove it from the vector DB and the master

The listing is paginated with a total, because the whole point is that a
client never has to load the master to find out whether there is more. The
delete is vector-first and all-or-nothing, because there is no reindex.
"""

from __future__ import annotations

from tests.conftest import standard_row


def _seed(client, n: int, prefix: str = "M") -> list[str]:
    """Put n rows through the boundary. Returns their ids in source order."""
    rows = [
        standard_row(f"HEX BOLT M{i} X 50 HT GRADE 8.8",
                     **{"Item Code / Legacy Ref": f"{prefix}-{i}"})
        for i in range(1, n + 1)
    ]
    body = client.post("/api/v1/standardized/add", json={"rows": rows}).json()
    assert body["added"] == n, body
    return body["material_ids"]


# --------------------------------------------------------------------------
# GET /materials — the vector DB, ten at a time
# --------------------------------------------------------------------------

def test_an_empty_master_is_an_empty_first_page(client):
    page = client.get("/api/v1/materials").json()
    assert page == {
        "items": [], "total": 0, "unindexed": 0, "limit": 10, "offset": 0,
        "has_more": False, "next_offset": None,
    }


def test_ten_at_a_time_by_default(client):
    _seed(client, 23)

    page = client.get("/api/v1/materials").json()
    assert len(page["items"]) == 10
    assert page["total"] == 23
    assert page["limit"] == 10
    assert page["offset"] == 0
    assert page["has_more"] is True
    assert page["next_offset"] == 10


def test_walking_next_offset_visits_every_row_exactly_once(client):
    """The contract a client actually relies on: follow next_offset until it
    is null and you have seen everything, with no gaps and no repeats."""
    ids = set(_seed(client, 23))

    seen: list[str] = []
    offset = 0
    pages = 0
    while offset is not None:
        page = client.get("/api/v1/materials", params={"offset": offset}).json()
        seen.extend(m["material_id"] for m in page["items"])
        offset = page["next_offset"]
        pages += 1

    assert pages == 3                       # 10 + 10 + 3
    assert len(seen) == 23
    assert len(set(seen)) == 23
    assert set(seen) == ids


def test_the_last_page_says_so(client):
    _seed(client, 23)
    last = client.get("/api/v1/materials", params={"offset": 20}).json()
    assert len(last["items"]) == 3
    assert last["has_more"] is False
    assert last["next_offset"] is None


def test_pages_are_stable_and_ordered(client):
    """Two reads of the same page return the same rows in the same order, and
    consecutive pages do not overlap - otherwise a client scrolling a list
    would see rows jump."""
    _seed(client, 15)
    first_a = [m["material_id"] for m in client.get("/api/v1/materials").json()["items"]]
    first_b = [m["material_id"] for m in client.get("/api/v1/materials").json()["items"]]
    second = [m["material_id"] for m in
              client.get("/api/v1/materials", params={"offset": 10}).json()["items"]]

    assert first_a == first_b
    assert not set(first_a) & set(second)
    rows = [m["source_row"] for m in client.get("/api/v1/materials").json()["items"]]
    assert rows == sorted(rows)


def test_limit_is_honoured_and_capped(client):
    _seed(client, 12)
    assert len(client.get("/api/v1/materials", params={"limit": 5}).json()["items"]) == 5
    assert client.get("/api/v1/materials", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/materials", params={"limit": 501}).status_code == 422
    assert client.get("/api/v1/materials", params={"offset": -1}).status_code == 422


def test_an_offset_past_the_end_is_an_empty_page_not_an_error(client):
    _seed(client, 3)
    page = client.get("/api/v1/materials", params={"offset": 999}).json()
    assert page["items"] == []
    assert page["total"] == 3
    assert page["has_more"] is False


def test_every_added_row_is_in_the_vector_db(client):
    """`add` writes both stores or neither, so a row is a vector."""
    _seed(client, 4)
    page = client.get("/api/v1/materials").json()
    assert page["total"] == 4
    assert page["unindexed"] == 0
    assert all(m["indexed"] for m in page["items"])
    assert all(m["embedding_version"] for m in page["items"])

    assert client.get("/api/v1/materials", params={"indexed": "true"}).json()["total"] == 4
    assert client.get("/api/v1/materials", params={"indexed": "false"}).json()["total"] == 0


def test_a_row_without_a_vector_is_listed_not_hidden(client):
    """The regression this guards against: a row loaded by an earlier build has
    no vector stamp. Hiding it by default made a master of 405 rows read as
    empty. It must be listed, and flagged."""
    import anyio

    import app.database as db_module
    from app.models.material import Material

    _seed(client, 3)

    async def _unstamp_one():
        async with db_module.AsyncSessionLocal() as db:
            row = await db.get(Material, (await db.execute(
                __import__("sqlalchemy").select(Material.id)
                .where(Material.material_id == "NTPC-M2")
            )).scalar_one())
            row.indexed_at = None
            row.canonical_hash = None
            row.embedding_version = None
            await db.commit()

    anyio.run(_unstamp_one)

    page = client.get("/api/v1/materials").json()
    assert page["total"] == 3                     # still listed
    assert page["unindexed"] == 1                 # and flagged
    flags = {m["material_id"]: m["indexed"] for m in page["items"]}
    assert flags == {"NTPC-M1": True, "NTPC-M2": False, "NTPC-M3": True}

    assert client.get("/api/v1/materials", params={"indexed": "false"}).json()["total"] == 1
    assert client.get("/api/v1/materials", params={"indexed": "true"}).json()["total"] == 2


def test_filters_narrow_the_total_not_just_the_page(client):
    """`total` must reflect the filter, or a client would render a page count
    for rows it can never reach."""
    _seed(client, 12, prefix="N")
    # Three DIFFERENT valves: identical descriptions would be held back as
    # in-batch duplicates, which is the boundary doing its job.
    valves = [standard_row(f"GATE VALVE {size} INCH CS 150#", **{
        "Company": "BHEL", "Item Code / Legacy Ref": f"V-{size}"}) for size in (2, 3, 4)]
    client.post("/api/v1/standardized/add", json={"rows": valves})

    by_cpse = client.get("/api/v1/materials", params={"cpse": "bhel"}).json()
    assert by_cpse["total"] == 3
    assert {m["cpse_code"] for m in by_cpse["items"]} == {"BHEL"}

    by_family = client.get("/api/v1/materials", params={"category": "VALVE"}).json()
    assert by_family["total"] == 3

    by_text = client.get("/api/v1/materials", params={"query": "M7 X 50"}).json()
    assert by_text["total"] == 1
    assert by_text["items"][0]["material_id"] == "NTPC-N7"


# --------------------------------------------------------------------------
# GET /materials/{material_id}
# --------------------------------------------------------------------------

def test_one_material_by_id(client):
    _seed(client, 3)
    row = client.get("/api/v1/materials/NTPC-M2").json()

    assert row["material_id"] == "NTPC-M2"
    assert row["description"] == "HEX BOLT M2 X 50 HT GRADE 8.8"
    assert row["legacy_code"] == "M-2"
    assert row["company"] == "NTPC"
    assert row["cpse_code"] == "NTPC"
    assert row["category"] == "FASTENER"
    assert row["indexed"] is True
    assert set(row["attributes"]) >= {"Company", "Item Description (Raw)", "UOM"}


def test_an_unknown_id_is_a_404(client):
    assert client.get("/api/v1/materials/NOPE-1").status_code == 404
    assert client.get("/api/v1/materials/..%2F..%2Fetc").status_code == 404


# --------------------------------------------------------------------------
# DELETE /materials/{material_id}
# --------------------------------------------------------------------------

def test_delete_removes_the_vector_and_the_row(client):
    from app.logic import retrieval

    _seed(client, 3)
    store = retrieval.get_store()
    assert store.count() == 3

    response = client.delete("/api/v1/materials/NTPC-M2", params={"actor": "asha"})
    assert response.status_code == 200
    body = response.json()
    assert body["material_id"] == "NTPC-M2"
    assert body["national_id"].startswith("NMM-")
    assert body["deleted"] is True
    assert body["vector_deleted"] is True
    assert body["detail"] == "Removed from the vector embedding DB and the master."

    assert store.count() == 2                                       # the vector
    assert client.get("/api/v1/materials/NTPC-M2").status_code == 404  # the row
    assert client.get("/api/v1/materials").json()["total"] == 2


def test_a_deleted_material_can_be_offered_again_as_new(client):
    """Once it is gone from both stores, the boundary must not remember it."""
    _seed(client, 1)
    client.delete("/api/v1/materials/NTPC-M1")

    row = standard_row("HEX BOLT M1 X 50 HT GRADE 8.8", **{"Item Code / Legacy Ref": "M-1"})
    check = client.post("/api/v1/standardized/check", json={"rows": [row]}).json()
    assert check["has_new_data"] is True
    assert check["rows"][0]["status"] == "NEW"


def test_deleting_twice_is_a_404_the_second_time(client):
    _seed(client, 1)
    assert client.delete("/api/v1/materials/NTPC-M1").status_code == 200
    assert client.delete("/api/v1/materials/NTPC-M1").status_code == 404


def test_deleting_an_unknown_id_is_a_404(client):
    assert client.delete("/api/v1/materials/NOPE-1").status_code == 404


def test_delete_is_vector_first_and_all_or_nothing(client):
    """If the store refuses, nothing is deleted anywhere. A row in the master
    with its vector gone - or the reverse - could never be repaired, because
    there is no reindex."""
    from app.logic import retrieval

    _seed(client, 2)

    class Refuses:
        def delete(self, *_): raise RuntimeError("connection refused")

    keep, retrieval._store = retrieval._store, Refuses()
    try:
        response = client.delete("/api/v1/materials/NTPC-M1")
    finally:
        retrieval._store = keep

    assert response.status_code == 503
    assert "Nothing was deleted" in response.json()["detail"]
    assert client.get("/api/v1/materials/NTPC-M1").status_code == 200   # row intact
    assert retrieval.get_store().count() == 2                            # vector intact

    # And the retry, once the store is back, succeeds cleanly.
    assert client.delete("/api/v1/materials/NTPC-M1").status_code == 200
    assert retrieval.get_store().count() == 1


def test_delete_is_audited_with_the_actor(client):
    import anyio
    from sqlalchemy import select

    import app.database as db_module
    from app.models.material import AuditLog

    _seed(client, 1)
    client.delete("/api/v1/materials/NTPC-M1", params={"actor": "asha"})

    async def _entries():
        async with db_module.AsyncSessionLocal() as db:
            rows = await db.execute(
                select(AuditLog).where(AuditLog.action == "DELETE_MATERIAL")
            )
            return [(r.actor, r.entity_id) for r in rows.scalars().all()]

    assert anyio.run(_entries) == [("asha", "NTPC-M1")]
