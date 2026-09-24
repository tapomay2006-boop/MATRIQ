"""Phase 1, as hosted here: the vendored engine and the endpoints around it.

The engine itself is pipeline-one's and is tested there. What is pinned here is
the part that is this service's responsibility: that the weights stay optional,
that the failure when they are absent is honest and actionable, and that the
pure functions the engine exposes behave the way the rest of the service
assumes when it reads their output.
"""

from __future__ import annotations

import time

import pandas as pd
import pytest

from app.logic import extraction as engine
from app.services import extraction as service

# --------------------------------------------------------------------------
# The vendored engine's pure parts
# --------------------------------------------------------------------------

def test_the_canonical_schema_is_eight_fields():
    assert len(engine.CANONICAL_FIELDS) == 8
    assert engine.CANONICAL_FIELDS[0] == "Company"
    assert engine.CANONICAL_FIELDS[1] == "Item Description (Raw)"


def test_resolve_canonical_dict_fills_every_field():
    """Whatever the model returns, downstream code sees all eight keys."""
    resolved = engine.resolve_canonical_dict({"Description": "BALL BEARING 6205"})
    assert set(resolved) == set(engine.CANONICAL_FIELDS)
    assert resolved["Item Description (Raw)"] == "BALL BEARING 6205"
    assert resolved["Make / Brand"] == "NA"


def test_abbreviations_expand_from_the_cpse_taxonomy():
    expanded = engine.expand_abbreviations("BRG BALL RAD 6205 2RS")
    assert "BEARING" in expanded
    assert "RADIAL" in expanded


def test_grounding_discards_what_the_input_never_said():
    """The guardrail that makes a generative extractor safe: a value the model
    produced but the source text does not contain is dropped, not stored."""
    grounded = engine.ground_attributes(
        "BALL BEARING 6205 2RS",
        {
            "Company": "NTPC",
            "Item Description (Raw)": "BALL BEARING 6205 2RS",
            "Item Code / Legacy Ref": "NA",
            "Quantity": "NA",
            "UOM": "NA",
            "Part Number / OEM Number": "INVENTED-999",
            "Make / Brand": "NA",
            "Specifications / Dimensions": "NA",
        },
    )
    assert grounded["Part Number / OEM Number"] == "NA"


def test_na_detection_covers_the_forms_a_model_emits():
    assert engine.is_na_val("NA")
    assert engine.is_na_val(None)
    assert engine.is_na_val("")
    assert not engine.is_na_val("SKF")


# --------------------------------------------------------------------------
# Whole-row folding, which is what removes the need for column inference
# --------------------------------------------------------------------------

def test_a_whole_row_folds_into_one_readable_string():
    from app.services.extraction import row_to_composite_text

    row = pd.Series({
        "Description": "BALL BEARING 6205 2RS",
        "Vendor": "SKF",
        "Qty": 5,
        "Unnamed: 4": "ignored",
        "Blank": None,
    })
    text = row_to_composite_text(row)
    assert text.startswith("BALL BEARING 6205 2RS.")
    assert "Vendor: SKF." in text
    assert "ignored" not in text
    assert "Blank" not in text


def test_a_row_with_no_recognisable_description_still_produces_text():
    """A file with columns nobody has seen before degrades into a longer
    sentence for the model to read, not into a rejected file."""
    from app.services.extraction import row_to_composite_text

    text = row_to_composite_text(pd.Series({"A": "GATE VALVE", "B": "2 INCH"}))
    assert "GATE VALVE" in text
    assert "2 INCH" in text


# --------------------------------------------------------------------------
# The weights stay optional, and say so
# --------------------------------------------------------------------------

def test_extraction_is_off_by_default(client):
    body = client.get("/api/v1/extract/info").json()
    assert body["enabled"] is False
    assert body["adapter"] == "qwen2.5-3b-cpse-lora-v2"
    assert body["vendored_from"] == "backend/pipeline-one/inference_engine.py"
    assert body["canonical_fields"] == list(engine.CANONICAL_FIELDS)


def test_extracting_while_disabled_is_a_503_that_says_what_to_do(client):
    """Moving the work into a background job must not downgrade "the adapter is
    not loaded" into an opaque 500."""
    response = client.post(
        "/api/v1/extract/text", json={"text": "BRG BALL 6205"}, params={"wait": 30}
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "EXTRACTION_ENABLED" in detail
    assert "/standardized/check" in detail


def test_an_empty_text_is_a_400_not_a_model_call(client):
    assert client.post("/api/v1/extract/text", json={"text": "   "}).status_code == 400


def test_the_adapter_is_referenced_not_copied():
    """195 MB of weights already tracked under pipeline-one. Duplicating them
    into this service would double the repository for nothing."""
    assert "pipeline-one" in str(service.adapter_dir())


def test_an_unknown_session_is_a_404(client):
    assert client.get("/api/v1/extract/sessions/nope").status_code == 404


def test_forwarding_an_unknown_session_is_a_404(client):
    response = client.post("/api/v1/extract/forward", json={"session_id": "nope"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# The abbreviation taxonomy, in Postgres
# --------------------------------------------------------------------------

def test_an_abbreviation_is_stored_and_applied(client):
    """Stored first, applied second. A mapping this process expands but has
    not stored would vanish on restart and was never true for any other
    worker."""
    response = client.post("/api/v1/extract/taxonomy/abbreviations", json={
        "raw": "zztest", "expansion": "zz test widget", "actor": "materials-eng",
    })
    assert response.status_code == 200
    assert response.json()["raw"] == "ZZTEST"
    assert response.json()["expansion"] == "ZZ TEST WIDGET"

    # It is in the database...
    listed = client.get("/api/v1/extract/taxonomy/abbreviations").json()
    entry = next(a for a in listed if a["raw"] == "ZZTEST")
    assert entry["expansion"] == "ZZ TEST WIDGET"
    assert entry["created_by"] == "materials-eng"

    # ...and the engine expands it now, not after a restart.
    assert "ZZ TEST WIDGET" in engine.expand_abbreviations("ZZTEST HOUSING")


def test_re_registering_corrects_rather_than_failing(client):
    """A taxonomy correction is the common case; refusing it would push people
    back to editing the CSV by hand."""
    client.post("/api/v1/extract/taxonomy/abbreviations",
                json={"raw": "QQV", "expansion": "WRONG EXPANSION"})
    client.post("/api/v1/extract/taxonomy/abbreviations",
                json={"raw": "QQV", "expansion": "QUICK QUARTER VALVE"})

    listed = client.get("/api/v1/extract/taxonomy/abbreviations").json()
    matches = [a for a in listed if a["raw"] == "QQV"]
    assert len(matches) == 1
    assert matches[0]["expansion"] == "QUICK QUARTER VALVE"
    assert "QUICK QUARTER VALVE" in engine.expand_abbreviations("QQV BODY")


def test_a_blank_abbreviation_is_refused(client):
    for body in ({"raw": "X", "expansion": "   "}, {"raw": "  ", "expansion": "Y"}):
        assert client.post(
            "/api/v1/extract/taxonomy/abbreviations", json=body
        ).status_code == 400


def test_the_taxonomy_change_is_audited(client):
    """A taxonomy edit is a domain decision, so it carries a name. The CSV
    append it replaced recorded nothing at all."""
    from sqlalchemy import select

    client.post("/api/v1/extract/taxonomy/abbreviations",
                json={"raw": "AUDT", "expansion": "AUDIT TEST", "actor": "asha"})

    import anyio

    import app.database as db_module
    from app.models.material import AuditLog

    async def _entries():
        async with db_module.AsyncSessionLocal() as db:
            rows = await db.execute(
                select(AuditLog).where(AuditLog.entity_id == "AUDT")
            )
            return [(r.action, r.actor) for r in rows.scalars().all()]

    assert anyio.run(_entries) == [("ADD_ABBREVIATION", "asha")]


def test_stored_abbreviations_are_applied_at_startup(client):
    """The reason it is a table: every worker picks the taxonomy up from the
    database, rather than each holding its own history."""
    from app.services import taxonomy

    client.post("/api/v1/extract/taxonomy/abbreviations",
                json={"raw": "STRT", "expansion": "STARTUP SYNC PROVEN"})

    # Wipe the live registry entry, as a freshly booted worker would have it.
    from app.logic import extraction as eng
    eng._ABBREVIATIONS_REGISTRY.pop("STRT", None)
    assert "STARTUP SYNC PROVEN" not in eng.expand_abbreviations("STRT PART")

    import anyio

    import app.database as db_module

    async def _sync():
        async with db_module.AsyncSessionLocal() as db:
            return await taxonomy.sync_to_engine(db)

    assert anyio.run(_sync) >= 1
    assert "STARTUP SYNC PROVEN" in eng.expand_abbreviations("STRT PART")


def test_extract_info_reports_what_is_stored(client):
    client.post("/api/v1/extract/taxonomy/abbreviations",
                json={"raw": "INFO", "expansion": "INFO TEST"})
    body = client.get("/api/v1/extract/info").json()
    assert body["abbreviations_learned"] >= 1
    assert body["sessions"] == 0


# --------------------------------------------------------------------------
# Extraction as a background job
# --------------------------------------------------------------------------

CSV_ROWS = 12
CSV_BODY = "Mat Txt,Werks\n" + "\n".join(
    f"raw row {i},NTPC" for i in range(CSV_ROWS)
)

CANNED = {
    "Company": "NTPC", "Item Description (Raw)": "BALL BEARING 6205 2RS",
    "Item Code / Legacy Ref": "1001", "Quantity": 5, "UOM": "NOS",
    "Make / Brand": "SKF", "Part Number / OEM Number": "6205",
    "Specifications / Dimensions": "25X52X15",
}


@pytest.fixture
def model(monkeypatch):
    """Phase 1 on, weights stubbed. Everything but the forward pass is real."""
    import app.config as config_module
    from app.services import extraction as service

    monkeypatch.setattr(config_module.settings, "extraction_enabled", True)
    monkeypatch.setattr(service, "extract_batch", lambda texts: [
        dict(CANNED) for _ in texts
    ])
    return service


def _poll(client, job_id, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/v1/extract/jobs/{job_id}").json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished")


def _submit_csv(client, rows=CSV_BODY, **data):
    return client.post(
        "/api/v1/extract/csv",
        files={"file": ("cat.csv", rows, "text/csv")},
        data={"max_rows": str(CSV_ROWS), **data},
        params={"wait": 0},
    )


def test_csv_returns_a_job_id_without_waiting_for_the_model(client, model):
    response = _submit_csv(client)
    assert response.status_code == 202

    body = response.json()
    assert body["id"]
    assert body["status"] in {"QUEUED", "RUNNING"}
    assert body["params"]["total_rows"] == CSV_ROWS
    assert response.headers["Location"].endswith(f"/jobs/{body['id']}")


def test_the_status_endpoint_reports_rows(client, model):
    job_id = _submit_csv(client).json()["id"]
    final = _poll(client, job_id)

    assert final["job_id"] == job_id
    assert final["status"] == "completed"
    assert final["processed_rows"] == CSV_ROWS
    assert final["total_rows"] == CSV_ROWS
    assert final["source_file"] == "cat.csv"
    assert final["session_id"]


def test_the_finished_result_is_the_original_synchronous_body(client, model):
    """The contract. `result` must be what this endpoint returned before it
    became a job - same keys, same record shape, same values."""
    job_id = _submit_csv(client).json()["id"]
    result = _poll(client, job_id)["result"]

    assert set(result) == {
        "session_id", "source_file", "text_column_used",
        "total_records", "records", "next_step",
    }
    assert result["source_file"] == "cat.csv"
    assert result["text_column_used"] == "Composite Whole Row (2 columns)"
    assert result["total_records"] == CSV_ROWS
    assert len(result["records"]) == CSV_ROWS

    record = result["records"][0]
    assert set(record) == {
        "record_id", "row_index", "raw_input",
        "predicted", "current", "is_modified", "status",
    }
    assert record["record_id"] == "rec_0001"
    assert record["row_index"] == 1
    assert record["raw_input"] == "Mat Txt: raw row 0. Werks: NTPC."
    assert record["predicted"] == CANNED
    assert record["current"] == CANNED
    assert record["is_modified"] is False
    assert record["status"] == "pending_review"


def test_waiting_inline_returns_that_same_body_directly(client, model):
    """A caller that was happy waiting keeps its old behaviour with ?wait=."""
    inline = client.post(
        "/api/v1/extract/csv",
        files={"file": ("cat.csv", CSV_BODY, "text/csv")},
        data={"max_rows": str(CSV_ROWS)},
        params={"wait": 30},
    )
    assert inline.status_code == 200

    job_id = _submit_csv(client).json()["id"]
    polled = _poll(client, job_id)["result"]

    # Identical but for the ids, which are per-session by construction.
    direct = inline.json()
    for body in (direct, polled):
        body.pop("session_id")
        body.pop("next_step")
    assert direct == polled


def test_text_extraction_is_a_job_too_and_keeps_its_body(client, model):
    response = client.post(
        "/api/v1/extract/text", json={"text": "brg ball 6205"}, params={"wait": 0}
    )
    assert response.status_code == 202

    final = _poll(client, response.json()["id"])
    assert final["processed_rows"] == 1
    assert final["total_rows"] == 1
    assert set(final["result"]) == {"session_id", "record"}
    assert final["result"]["record"]["record_id"] == "rec_0001"


def test_the_result_survives_a_late_poll(client, model):
    """The frontend must recover the result even if it polls after completion,
    or reloads the page an hour later."""
    job_id = _submit_csv(client).json()["id"]
    _poll(client, job_id)

    for _ in range(3):
        body = client.get(f"/api/v1/extract/jobs/{job_id}").json()
        assert body["status"] == "completed"
        assert body["result"]["total_records"] == CSV_ROWS


def test_records_land_in_the_session_as_they_are_extracted(client, model):
    """Incremental results, on the existing review session - no second store.
    The session exists before any row is done, so a poller can read what is
    finished without waiting for the rest."""
    job_id = _submit_csv(client).json()["id"]
    final = _poll(client, job_id)

    session = client.get(f"/api/v1/extract/sessions/{final['session_id']}").json()
    assert session["status"] == "PENDING_REVIEW"
    assert session["total_records"] == CSV_ROWS
    assert len(session["records"]) == CSV_ROWS
    assert session["job_id"] == job_id


def test_a_failure_is_reported_not_swallowed(client, model, monkeypatch):
    def boom(texts):
        raise RuntimeError("model blew up")

    monkeypatch.setattr(model, "extract_batch", boom)
    final = _poll(client, _submit_csv(client).json()["id"])

    assert final["status"] == "failed"
    assert "model blew up" in final["error"]
    assert final["total_rows"] == CSV_ROWS


def test_a_partial_failure_keeps_the_rows_it_managed(client, model, monkeypatch):
    """217 rows out of a model is 217 rows of real work; a transient failure
    must not cost the whole file."""
    calls = {"n": 0}

    def fail_on_third(texts):
        calls["n"] += 1
        if calls["n"] > 2:
            raise RuntimeError("died part way")
        return [dict(CANNED) for _ in texts]

    monkeypatch.setattr(model, "extract_batch", fail_on_third)
    final = _poll(client, _submit_csv(client).json()["id"])

    assert final["status"] == "failed"
    assert 0 < final["processed_rows"] < CSV_ROWS

    session = client.get(f"/api/v1/extract/sessions/{final['session_id']}").json()
    assert session["status"] == "FAILED"
    assert len(session["records"]) == final["processed_rows"]


def test_an_unparseable_file_is_still_a_400_on_upload(client, model):
    """Parsed in the request, so a bad file never becomes a failed job."""
    response = client.post(
        "/api/v1/extract/csv", files={"file": ("e.csv", "Header\n", "text/csv")}
    )
    assert response.status_code == 400


def test_many_extraction_jobs_can_run_at_once(client, model):
    ids = [_submit_csv(client).json()["id"] for _ in range(3)]
    assert len(set(ids)) == 3
    assert all(_poll(client, i)["status"] == "completed" for i in ids)


def test_an_unknown_extraction_job_is_a_404(client):
    assert client.get("/api/v1/extract/jobs/nope").status_code == 404


def test_a_non_extraction_job_is_not_served_here(client):
    """The status shape is row-based; pointing it at a reindex would be a lie."""
    submitted = client.post(
        "/api/v1/standardized/check",
        json={"rows": [{"Company": "NTPC", "Item Description (Raw)": "X"}]},
        params={"wait": 30},
    )
    job_id = submitted.headers["X-Job-Id"]
    response = client.get(f"/api/v1/extract/jobs/{job_id}")
    assert response.status_code == 404
    assert "not an extraction" in response.json()["detail"]


def test_the_generic_job_endpoint_reports_the_same_job(client, model):
    job_id = _submit_csv(client).json()["id"]
    _poll(client, job_id)

    generic = client.get(f"/api/v1/jobs/{job_id}").json()
    assert generic["kind"] == "EXTRACT_BATCH"
    assert generic["status"] == "SUCCEEDED"
    assert generic["progress_current"] == CSV_ROWS
    assert generic["result"]["total_records"] == CSV_ROWS
