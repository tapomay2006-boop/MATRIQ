"""The boundary the whole service turns on.

    standard format -> check -> new material -> add -> vector embedding DB
                          |
                          +--> already in the vector DB: ignored

Two properties are load-bearing and everything else here supports them:

1. A row already in the vector embedding DB can never be added again, by any
   route, including a caller that skips the check or replays a stale batch.
2. When nothing is new, that is an ANSWER - `has_new_data: false` with a
   sentence saying so - not an error and not an empty 200 the caller has to
   interpret.
"""

from __future__ import annotations

import pytest

from tests.conftest import standard_row

BEARING = standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "1001"})
VALVE = standard_row("GATE VALVE 2 INCH CS 150#", **{
    "Company": "BHEL", "Item Code / Legacy Ref": "2002",
})
FILTER = standard_row("LUBE OIL FILTER CUMMINS KTA19", **{
    "Company": "ONGC", "Item Code / Legacy Ref": "3003",
})


def check(client, rows, **extra):
    """Rows given directly, or `rows=None` plus `session_id=...`."""
    payload = dict(extra) if rows is None else {"rows": rows, **extra}
    response = client.post("/api/v1/standardized/check", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def add(client, **payload):
    return client.post("/api/v1/standardized/add", json=payload)


# --------------------------------------------------------------------------
# Check
# --------------------------------------------------------------------------

def test_an_empty_index_makes_every_row_new(client):
    body = check(client, [BEARING, VALVE, FILTER])
    assert body["has_new_data"] is True
    assert body["new_rows"] == 3
    assert body["existing_rows"] == 0
    assert len(body["new_material"]) == 3


def test_check_writes_nothing(client):
    check(client, [BEARING, VALVE])
    assert client.get("/api/v1/materials").json()["items"] == []


def test_the_response_carries_only_the_new_rows(client):
    """The brief's example: 10 in, 8 already there, 2 come back."""
    rows = [standard_row(f"HEX BOLT M{n} X 50 HT") for n in range(1, 11)]
    first = check(client, rows[:8])
    assert add(client, batch_id=first["batch_id"]).json()["added"] == 8

    second = check(client, rows)
    assert second["total_rows"] == 10
    assert second["existing_rows"] == 8
    assert second["new_rows"] == 2
    assert len(second["new_material"]) == 2
    assert {m["description"] for m in second["new_material"]} == {
        "HEX BOLT M9 X 50 HT", "HEX BOLT M10 X 50 HT",
    }


def test_all_rows_present_is_reported_as_no_new_data(client):
    body = check(client, [BEARING, VALVE])
    add(client, batch_id=body["batch_id"])

    again = check(client, [BEARING, VALVE])
    assert again["has_new_data"] is False
    assert again["new_rows"] == 0
    assert again["new_material"] == []
    assert "No new data" in again["message"]
    assert "already available in the vector embedding DB" in again["message"]


def test_an_existing_row_names_what_it_collided_with(client):
    body = check(client, [BEARING])
    add(client, batch_id=body["batch_id"])

    row = check(client, [BEARING])["rows"][0]
    assert row["status"] == "ALREADY_EXISTS"
    assert row["matched_material_id"] == "NTPC-1001"
    assert row["matched_by"] == "MATERIAL_ID"
    assert row["reason"]


def test_the_same_article_under_a_different_legacy_code_is_caught_by_hash(client):
    """Different internal code, identical text: the second row would produce
    the same vector, so it adds nothing."""
    body = check(client, [BEARING])
    add(client, batch_id=body["batch_id"])

    twin = dict(BEARING)
    twin["Item Code / Legacy Ref"] = "9999"
    row = check(client, [twin])["rows"][0]
    assert row["status"] == "ALREADY_EXISTS"
    assert row["matched_by"] == "CANONICAL_HASH"
    assert row["matched_material_id"] == "NTPC-1001"


def test_a_repeat_inside_one_payload_is_held_back(client):
    body = check(client, [BEARING, dict(BEARING)])
    assert body["new_rows"] == 1
    assert body["duplicate_rows_in_batch"] == 1
    assert body["rows"][1]["status"] == "DUPLICATE_IN_BATCH"
    assert body["rows"][1]["duplicate_of_row"] == 1


def test_an_unreadable_row_is_quarantined_not_dropped(client):
    body = check(client, [{"Company": "NTPC", "Quantity": 4}, BEARING])
    assert body["invalid_rows"] == 1
    assert body["new_rows"] == 1
    assert body["rows"][0]["status"] == "INVALID"
    assert "Item Description" in body["rows"][0]["error"]
    # Every row sent comes back, so a caller can reconcile by row number.
    assert [r["row_number"] for r in body["rows"]] == [1, 2]


def test_a_forwarder_envelope_is_accepted_verbatim(client):
    """`records` is `rows` under the name pipeline-one's forwarder uses, so
    NEXT_PIPELINE_URL can point straight at this endpoint."""
    response = client.post("/api/v1/standardized/check", json={
        "source_pipeline": "pipeline-one",
        "records": [BEARING, VALVE],
    })
    assert response.status_code == 200
    assert response.json()["new_rows"] == 2


def test_session_id_and_rows_together_are_refused(client):
    """With a session_id the rows come from the session, so a second list could
    silently disagree with what a human actually reviewed."""
    response = client.post("/api/v1/standardized/check", json={
        "session_id": "sess_123", "rows": [BEARING],
    })
    assert response.status_code == 422


def test_an_unknown_session_id_is_a_404(client):
    response = client.post(
        "/api/v1/standardized/check", json={"session_id": "sess_nope"}
    )
    assert response.status_code == 404
    assert "sess_nope" in response.json()["detail"]


def test_rows_and_records_together_are_refused(client):
    response = client.post("/api/v1/standardized/check", json={
        "rows": [BEARING], "records": [VALVE],
    })
    assert response.status_code == 422


def test_an_empty_payload_is_refused(client):
    assert client.post("/api/v1/standardized/check", json={"rows": []}).status_code == 422


def test_default_company_rescues_rows_the_model_could_not_attribute(client):
    rows = [{"Item Description (Raw)": "HEX BOLT M12 X 50 HT", "Company": "NA"}]
    assert check(client, rows)["invalid_rows"] == 1
    assert check(client, rows, default_company="CPCL")["new_rows"] == 1


# --------------------------------------------------------------------------
# Add
# --------------------------------------------------------------------------

def test_add_writes_and_indexes_the_new_rows(client):
    body = check(client, [BEARING, VALVE, FILTER])
    result = add(client, batch_id=body["batch_id"]).json()

    assert result["added"] == 3
    assert result["indexed"] == 3
    assert sorted(result["material_ids"]) == ["BHEL-2002", "NTPC-1001", "ONGC-3003"]

    stored = client.get("/api/v1/materials").json()["items"]
    assert len(stored) == 3
    assert all(row["indexed"] for row in stored)
    assert all(row["batch_id"] == body["batch_id"] for row in stored)


def test_the_id_the_check_promised_is_the_id_add_stores(client):
    body = check(client, [BEARING, VALVE])
    promised = {row["material_id"] for row in body["new_material"]}
    stored = set(add(client, batch_id=body["batch_id"]).json()["material_ids"])
    assert promised == stored


def test_a_batch_can_only_be_added_once(client):
    body = check(client, [BEARING])
    assert add(client, batch_id=body["batch_id"]).status_code == 200
    replay = add(client, batch_id=body["batch_id"])
    assert replay.status_code == 409
    assert "already been added" in replay.json()["detail"]


def test_an_unknown_batch_is_a_404(client):
    assert add(client, batch_id="does-not-exist").status_code == 404


def test_add_rechecks_rather_than_trusting_the_batch(client):
    """A batch is a snapshot. If the same article was indexed by someone else
    in between, the stale batch must not write a second copy."""
    stale = check(client, [BEARING, VALVE])
    other = check(client, [BEARING])
    assert add(client, batch_id=other["batch_id"]).json()["added"] == 1

    result = add(client, batch_id=stale["batch_id"]).json()
    assert result["added"] == 1
    assert result["skipped_existing"] == 1
    assert result["material_ids"] == ["BHEL-2002"]
    assert client.get("/api/v1/materials").json()["total"] == 2


def test_add_with_rows_checks_before_writing(client):
    """The standalone path carries the same guarantee as batch_id."""
    assert add(client, rows=[BEARING, VALVE]).json()["added"] == 2
    second = add(client, rows=[BEARING, VALVE, FILTER]).json()
    assert second["added"] == 1
    assert second["skipped_existing"] == 2
    assert client.get("/api/v1/materials").json()["total"] == 3


def test_adding_nothing_new_is_a_200_that_says_so(client):
    first = check(client, [BEARING])
    add(client, batch_id=first["batch_id"])

    response = add(client, rows=[BEARING])
    assert response.status_code == 200
    body = response.json()
    assert body["added"] == 0
    assert body["skipped_existing"] == 1
    assert "No new data" in body["message"]


def test_batch_id_and_rows_together_are_refused(client):
    response = add(client, batch_id="x", rows=[BEARING])
    assert response.status_code == 422


def test_neither_batch_id_nor_rows_is_refused(client):
    assert client.post("/api/v1/standardized/add", json={}).status_code == 422


def test_an_unwritable_vector_store_adds_nothing_at_all(client):
    """There is no rebuild endpoint, so a row in the master without a vector
    could never be embedded and every later check would keep calling it new.
    The master and the index are written together or not at all."""
    from app.logic import retrieval

    class Refuses:
        def ensure_collection(self, **_):
            raise RuntimeError("connection refused")

    original = retrieval._store
    retrieval._store = Refuses()
    try:
        response = add(client, rows=[BEARING, VALVE])
    finally:
        retrieval._store = original

    assert response.status_code == 503
    assert "Nothing was added" in response.json()["detail"]
    assert client.get("/api/v1/materials").json()["items"] == []


def test_source_row_continues_rather_than_restarting_per_batch(client):
    """Every payload has a row 1; the master must not have three of them."""
    add(client, rows=[BEARING])
    add(client, rows=[VALVE])
    add(client, rows=[FILTER])
    rows = client.get("/api/v1/materials").json()["items"]
    assert sorted(row["source_row"] for row in rows) == [1, 2, 3]


# --------------------------------------------------------------------------
# The audit trail
# --------------------------------------------------------------------------

def test_a_batch_records_the_split_it_decided(client):
    body = check(client, [BEARING, dict(BEARING), {"Company": "NTPC"}])
    add(client, batch_id=body["batch_id"])

    batch = client.get(f"/api/v1/standardized/batches/{body['batch_id']}").json()
    assert batch["status"] == "ADDED"
    assert batch["total_rows"] == 3
    assert batch["new_rows"] == 1
    assert batch["duplicate_rows"] == 1
    assert batch["invalid_rows"] == 1
    assert batch["added_rows"] == 1
    assert len(batch["rows"]) == 3


def test_batches_are_listed_newest_first(client):
    check(client, [BEARING])
    check(client, [VALVE])
    listed = client.get("/api/v1/standardized/batches").json()
    assert len(listed) == 2


def test_an_unknown_batch_id_is_a_404(client):
    assert client.get("/api/v1/standardized/batches/nope").status_code == 404


# --------------------------------------------------------------------------
# A reviewed extraction session, checked in one call
# --------------------------------------------------------------------------

@pytest.fixture
def fake_model(monkeypatch):
    """Turn Phase 1 on with the model stubbed out.

    Everything except the 3B forward pass is real: the route, the session and
    record rows, the review edit, and the hand-off to the boundary. The weights
    are the one thing a test has no business loading.
    """
    import app.config as config_module
    from app.services import extraction

    canned: list[dict] = []

    def _batch(texts):
        return [dict(canned[i % len(canned)]) for i in range(len(texts))]

    monkeypatch.setattr(config_module.settings, "extraction_enabled", True)
    monkeypatch.setattr(extraction, "extract_batch", _batch)
    monkeypatch.setattr(extraction, "extract_one", lambda text: dict(canned[0]))
    return canned


def _upload(client, fake_model, records):
    """Run POST /extract/csv with the model returning `records`."""
    fake_model.clear()
    fake_model.extend(records)
    csv_body = "Mat Txt\n" + "\n".join(f"raw row {i}" for i in range(len(records)))
    response = client.post(
        "/api/v1/extract/csv",
        files={"file": ("cat.csv", csv_body, "text/csv")},
        data={"max_rows": str(len(records))},
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_a_session_id_is_checked_like_any_other_rows(client, fake_model):
    """There is no forward endpoint: looking a session up and calling the
    check IS the check, so the check takes the session id directly."""
    session_id = _upload(client, fake_model, [dict(BEARING), dict(VALVE)])

    body = check(client, None, session_id=session_id)
    assert body["new_rows"] == 2
    assert body["total_rows"] == 2
    assert client.get("/api/v1/materials").json()["items"] == []  # still writes nothing


def test_a_session_survives_in_the_database_not_a_process_dict(client, fake_model):
    """The failure this replaced: the listing read a per-process dict, so it
    came back empty after a restart while the JSON sat on disk."""
    session_id = _upload(client, fake_model, [dict(BEARING)])

    listed = client.get("/api/v1/extract/sessions").json()
    assert [s["session_id"] for s in listed] == [session_id]
    assert listed[0]["total_records"] == 1
    assert listed[0]["adapter"] == "qwen2.5-3b-cpse-lora-v2"

    fetched = client.get(f"/api/v1/extract/sessions/{session_id}").json()
    assert fetched["records"][0]["record_id"] == "rec_0001"
    assert fetched["records"][0]["raw_input"] == "raw row 0"


def test_the_correction_is_what_gets_checked_not_the_prediction(client, fake_model):
    """The whole point of a review session is that a human fixed what the
    model got wrong. `current` must reach the master; `predicted` must not."""
    session_id = _upload(
        client, fake_model, [dict(BEARING, **{"Make / Brand": "WRONGCO"})]
    )
    edit = client.put(
        f"/api/v1/extract/records/{session_id}/rec_0001",
        json={"Make / Brand": "SKF"},
    ).json()["record"]

    assert edit["current"]["Make / Brand"] == "SKF"
    assert edit["predicted"]["Make / Brand"] == "WRONGCO"
    assert edit["is_modified"] is True

    body = check(client, None, session_id=session_id)
    assert "SKF" in body["rows"][0]["embedded_text"]
    assert "WRONGCO" not in body["rows"][0]["embedded_text"]

    add(client, batch_id=body["batch_id"])
    assert client.get("/api/v1/materials/NTPC-1001").json()["make"] == "SKF"


def test_a_correction_is_accepted_under_any_spelling(client, fake_model):
    session_id = _upload(client, fake_model, [dict(BEARING)])
    edit = client.put(
        f"/api/v1/extract/records/{session_id}/rec_0001",
        json={"make_brand": "FAG", "qty": "42"},
    ).json()["record"]
    assert edit["current"]["Make / Brand"] == "FAG"
    assert edit["current"]["Quantity"] == "42"


def test_clearing_a_cell_stores_na_not_an_empty_string(client, fake_model):
    """The session keeps reading the way the engine's own output does."""
    session_id = _upload(client, fake_model, [dict(BEARING)])
    edit = client.put(
        f"/api/v1/extract/records/{session_id}/rec_0001",
        json={"Make / Brand": ""},
    ).json()["record"]
    assert edit["current"]["Make / Brand"] == "NA"


def test_session_status_tracks_the_review(client, fake_model):
    session_id = _upload(client, fake_model, [dict(BEARING)])
    assert client.get(f"/api/v1/extract/sessions/{session_id}").json()["status"] == (
        "PENDING_REVIEW"
    )

    client.put(f"/api/v1/extract/records/{session_id}/rec_0001", json={"UOM": "SET"})
    assert client.get(f"/api/v1/extract/sessions/{session_id}").json()["status"] == (
        "REVIEWED"
    )

    check(client, None, session_id=session_id)
    assert client.get(f"/api/v1/extract/sessions/{session_id}").json()["status"] == (
        "CHECKED"
    )


def test_a_session_batch_records_where_it_came_from(client, fake_model):
    session_id = _upload(client, fake_model, [dict(BEARING)])
    body = check(client, None, session_id=session_id)

    batch = client.get(f"/api/v1/standardized/batches/{body['batch_id']}").json()
    assert batch["source"] == "extraction"
    assert batch["source_session_id"] == session_id


def test_rows_from_a_session_carry_the_adapter_as_provenance(client, fake_model):
    """A row Phase 1 produced records which adapter read it. A row posted
    directly records nothing rather than claiming an adapter it never saw."""
    session_id = _upload(client, fake_model, [dict(BEARING)])
    body = check(client, None, session_id=session_id)
    add(client, batch_id=body["batch_id"])
    assert client.get("/api/v1/materials/NTPC-1001").json()["extraction_model"] == (
        "qwen2.5-3b-cpse-lora-v2"
    )

    add(client, rows=[VALVE])
    assert client.get("/api/v1/materials/BHEL-2002").json()["extraction_model"] is None


# --------------------------------------------------------------------------
# What Postgres holds, and for how long
# --------------------------------------------------------------------------

def test_the_staged_copy_is_dropped_once_the_rows_are_in_the_master(client):
    """A batch stages every row it judged new, so `add` writes this service's
    decision rather than a list the client hands back. Once those rows are in
    `material` the copy is a second, stale copy of the master."""
    body = check(client, [BEARING, VALVE])
    staged = client.get(f"/api/v1/standardized/batches/{body['batch_id']}").json()
    assert len(staged["new_material"]) == 2
    assert staged["material_ids"] == []

    add(client, batch_id=body["batch_id"])

    settled = client.get(f"/api/v1/standardized/batches/{body['batch_id']}").json()
    assert settled["new_material"] == []
    assert sorted(settled["material_ids"]) == ["BHEL-2002", "NTPC-1001"]
    # The verdicts stay: they are why each row was judged, and exist nowhere else.
    assert len(settled["rows"]) == 2


def test_the_master_keeps_everything_the_vector_does_not(client):
    """Postgres is the record; the index is derived over five of the eight
    attributes. Quantity and the legacy code are in neither the embedded text
    nor the vector payload, so the master is the only place they exist."""
    body = check(client, [BEARING])
    add(client, batch_id=body["batch_id"])

    stored = client.get("/api/v1/materials/NTPC-1001").json()
    assert stored["quantity"] == 10
    assert stored["legacy_code"] == "1001"
    assert stored["company"] == "NTPC"

    embedded = body["rows"][0]["embedded_text"]
    assert "1001" not in embedded
    assert "NTPC" not in embedded


def test_an_abandoned_check_is_pruned_after_its_retention(client):
    """A preview nobody acted on holds a full copy of every row it judged."""
    from datetime import timedelta

    import anyio
    from sqlalchemy import select

    import app.config as config_module
    import app.database as db_module
    from app.logic.clock import utcnow
    from app.models.standardized import StandardizationBatch

    abandoned = check(client, [BEARING])["batch_id"]
    kept = check(client, [VALVE])["batch_id"]
    add(client, batch_id=kept)

    async def _age_everything():
        async with db_module.AsyncSessionLocal() as db:
            old = utcnow() - timedelta(days=config_module.settings.batch_retention_days + 1)
            for batch in (await db.execute(select(StandardizationBatch))).scalars():
                batch.created_at = old
            await db.commit()

    anyio.run(_age_everything)

    # Any new check prunes opportunistically - no scheduler.
    check(client, [FILTER])

    listed = {b["id"] for b in client.get("/api/v1/standardized/batches").json()}
    assert abandoned not in listed          # CHECKED and stale -> gone
    assert kept in listed                   # ADDED -> the audit trail, kept


def test_pruning_can_be_switched_off(client, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "batch_retention_days", 0)
    abandoned = check(client, [BEARING])["batch_id"]
    check(client, [VALVE])

    listed = {b["id"] for b in client.get("/api/v1/standardized/batches").json()}
    assert abandoned in listed
