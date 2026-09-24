"""Background jobs: the contract that replaced "wait and hope".

The failure this exists to prevent is specific. A long endpoint ran
synchronously, the client gave up at 60 seconds, the server kept working, and
nothing anywhere could say whether the work had finished, failed, or was still
going. These tests pin the three properties that fix that: the work is
addressable by id, its outcome is readable afterwards, and a rejection stays a
rejection rather than becoming an opaque 500.
"""

from __future__ import annotations

import time

import pytest

from tests.conftest import standard_row

ROWS = [
    standard_row("BALL BEARING 6205 2RS", **{"Item Code / Legacy Ref": "1001"}),
    standard_row("V-BELT SEC C 120 INCH", **{"Item Code / Legacy Ref": "1002"}),
]


@pytest.fixture
def no_inline_wait():
    """Turn off the inline wait so the deferred path is what gets exercised."""
    import app.config as config_module

    original = config_module.settings.job_default_wait_seconds
    config_module.settings.job_default_wait_seconds = 0.0
    yield
    config_module.settings.job_default_wait_seconds = original


def _poll(client, job_id, timeout=30.0):
    """Poll until terminal, the way a real client would."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}", params={"wait": 5}).json()
        if body["terminal"]:
            return body
    raise AssertionError(f"job {job_id} never reached a terminal state")


def test_a_deferred_endpoint_returns_202_and_a_pollable_job(client, no_inline_wait):
    response = client.post("/api/v1/standardized/check", json={"rows": ROWS})
    assert response.status_code == 202

    body = response.json()
    assert body["status"] in {"QUEUED", "RUNNING"}
    assert body["kind"] == "STANDARDIZED_CHECK"
    assert response.headers["Location"].endswith(f"/jobs/{body['id']}")
    assert response.headers["X-Job-Id"] == body["id"]

    finished = _poll(client, body["id"])
    assert finished["status"] == "SUCCEEDED"
    assert finished["result"]["new_rows"] == 2


def test_waiting_long_enough_returns_the_payload_inline(client, no_inline_wait):
    """A caller happy to wait sees the work, not a wrapper around it."""
    response = client.post(
        "/api/v1/standardized/check", json={"rows": ROWS}, params={"wait": 30}
    )
    assert response.status_code == 200
    assert response.json()["new_rows"] == 2
    assert response.headers["X-Job-Id"]


def test_a_bad_request_stays_a_400_not_an_opaque_500(client, no_inline_wait):
    """Moving work into the background must not downgrade "your batch does not
    exist" into "something went wrong"."""
    response = client.post(
        "/api/v1/standardized/add",
        json={"batch_id": "does-not-exist"},
        params={"wait": 30},
    )
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


def test_a_failed_job_records_why(client, no_inline_wait):
    response = client.post(
        "/api/v1/standardized/add", json={"batch_id": "does-not-exist"}
    )
    job_id = response.headers["X-Job-Id"]

    finished = _poll(client, job_id)
    assert finished["status"] == "FAILED"
    assert finished["error_status"] == 404
    assert "does-not-exist" in finished["error"]


def test_jobs_are_listable_and_carry_their_kind(client, no_inline_wait):
    client.post("/api/v1/standardized/check", json={"rows": ROWS}, params={"wait": 30})
    listed = client.get("/api/v1/jobs").json()
    assert listed
    assert listed[0]["kind"] == "STANDARDIZED_CHECK"


def test_an_unknown_job_is_a_404(client):
    assert client.get("/api/v1/jobs/nope").status_code == 404
