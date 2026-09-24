"""POST /search: identifiers, names, parameters, sentences, and every way it
can fail without crashing.

Hermetic like the rest of the suite: the seeded-hash embedding, the in-memory
store, and - because the trained Siamese model needs torch and a checkpoint -
a stand-in reranker that scores token overlap. It is not the model; it is
enough to prove the pipeline reranks, fuses, classifies and degrades the way
the service promises. The real model is covered by tests/test_siamese.py.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from app.config import settings
from app.services import reranker as reranker_service
from tests.conftest import standard_row

_TOKEN = re.compile(r"[A-Z0-9]+")


class OverlapReranker:
    """Overlap coefficient over alphanumeric tokens. Stands in for the model."""

    name = "overlap-stand-in"
    calls: list[int]

    def __init__(self) -> None:
        self.calls = []

    def score_pairs(self, query: str, candidates) -> np.ndarray:
        self.calls.append(len(candidates))
        q = set(_TOKEN.findall(query.upper()))
        out = []
        for candidate in candidates:
            c = set(_TOKEN.findall(candidate.upper()))
            out.append(len(q & c) / min(len(q), len(c)) if q and c else 0.0)
        return np.asarray(out, dtype=np.float32)


class ExplodingReranker:
    name = "explodes"

    def score_pairs(self, query, candidates):
        raise RuntimeError("CUDA fell over")


ROWS = [
    standard_row("V-BELT SEC C, NOM L 120 INCH", **{
        "Company": "NTPC", "Item Code / Legacy Ref": "M-55321",
        "Part Number / OEM Number": "C-120", "Make / Brand": "FENNER",
    }),
    standard_row("BELT V C-120", **{
        "Company": "BHEL", "Item Code / Legacy Ref": "224411",
        "Part Number / OEM Number": "C120", "Make / Brand": "PIX",
    }),
    standard_row("V BELT C 125", **{"Company": "NTPC", "Item Code / Legacy Ref": "M-55399"}),
    standard_row("HEX BOLT M10 X 50", **{"Company": "BHEL", "Item Code / Legacy Ref": "778899"}),
    standard_row("BALL BEARING 6205 2RS", **{"Company": "ONGC", "Item Code / Legacy Ref": "1001"}),
    standard_row("GATE VALVE 2 INCH 800#", **{"Company": "GAIL", "Item Code / Legacy Ref": "2002"}),
]


@pytest.fixture
def reranker():
    stand_in = OverlapReranker()
    reranker_service.set_reranker(stand_in)
    yield stand_in
    reranker_service.set_reranker(None)


@pytest.fixture
def seeded(client):
    response = client.post("/api/v1/standardized/add", json={"rows": ROWS})
    assert response.status_code == 200, response.text
    assert response.json()["added"] == len(ROWS)
    return client


def search(client, query, **extra):
    response = client.post("/api/v1/search", json={"query": query, **extra})
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------

def test_a_legacy_code_is_an_exact_lookup(seeded, reranker):
    body = search(seeded, "M-55321")
    top = body["results"][0]
    assert top["material_id"] == "NTPC-M55321"
    assert top["legacy_code"] == "M-55321"
    assert top["matched_by"] == ["identifier"]
    assert top["match"] is True and top["match_level"] == "high"
    assert top["match_source"] == "exact_identifier"
    assert top["identifier_match"] is True
    assert top["identifier_match_type"] == "exact"
    assert top["identifier_matched_field"] == "legacy_code"
    assert top["identifier_token"] == "M-55321"
    assert body["pipeline"]["identifier_only"] is True
    assert body["pipeline"]["vector_search_ran"] is False
    assert body["pipeline"]["identifier_hits"] == 1


def test_a_bare_numeric_code_and_a_prefixed_one_are_found(seeded, reranker):
    assert search(seeded, "224411")["results"][0]["material_id"] == "BHEL-224411"
    assert search(seeded, "ntpc-m-55321")["results"][0]["material_id"] == "NTPC-M55321"
    direct = search(seeded, "NTPC-M55321")["results"][0]
    assert direct["material_id"] == "NTPC-M55321"
    assert direct["identifier_matched_field"] == "material_id"


def test_a_part_number_is_an_exact_identifier_match(seeded, reranker):
    body = search(seeded, "C-120")
    fields = {r["material_id"]: r["identifier_matched_field"] for r in body["results"]
              if r["identifier_match"]}
    assert fields == {"NTPC-M55321": "part_number", "BHEL-224411": "part_number"}
    assert all(r["match_source"] == "exact_identifier" for r in body["results"][:2])


def test_an_exact_identifier_with_a_low_siamese_score_is_labelled_as_a_rule(seeded):
    """`a belt that is c-120`: the part number matches, the model is unsure.
    The response must say the rule fired - never present 0.2 as confidence."""

    class Unsure:
        name = "unsure"

        def score_pairs(self, query, candidates):
            return np.full(len(candidates), 0.2, dtype=np.float32)

    reranker_service.set_reranker(Unsure())
    try:
        body = search(seeded, "a belt that is c-120")
    finally:
        reranker_service.set_reranker(None)
    top = body["results"][0]
    assert top["material_id"] in {"NTPC-M55321", "BHEL-224411"}
    assert top["part_number"] in {"C-120", "C120"}
    assert top["siamese_score"] == pytest.approx(0.2)
    assert top["match_level"] == "high"
    assert top["match_source"] == "exact_identifier"
    assert top["identifier_match"] is True
    assert set(top["matched_by"]) == {"identifier", "vector"}
    assert "by exact identifier" in body["message"]


def test_a_high_siamese_score_without_an_identifier_is_labelled_siamese(
    seeded, reranker, monkeypatch
):
    monkeypatch.setattr(settings, "search_match_threshold", 0.5)
    monkeypatch.setattr(settings, "search_possible_threshold", 0.3)
    top = search(seeded, "V BELT C 120")["results"][0]
    assert top["identifier_match"] is False
    assert top["identifier_matched_field"] is None
    assert top["match_level"] == "high"
    assert top["match_source"] == "siamese"


def test_a_national_id_is_found(seeded, reranker):
    national = seeded.get("/api/v1/materials/NTPC-M55321").json()["national_id"]
    body = search(seeded, national)
    assert body["results"][0]["national_id"] == national
    assert body["results"][0]["matched_by"] == ["identifier"]


def test_an_unknown_identifier_falls_through_to_the_vector_stage(seeded, reranker):
    body = search(seeded, "M-99999")
    assert body["pipeline"]["identifier_hits"] == 0
    assert body["pipeline"]["vector_search_ran"] is True
    assert body["best_match_level"] != "high"


# --------------------------------------------------------------------------
# Names, parameters, sentences
# --------------------------------------------------------------------------

def test_a_name_alone_returns_the_family(seeded, reranker):
    body = search(seeded, "V BELT")
    assert body["pipeline"]["reranker_applied"] is True
    top_three = [r["description"] for r in body["results"][:3]]
    assert all("BELT" in d for d in top_three)
    assert body["results"][0]["siamese_score"] is not None


def test_parameters_make_the_ranking_specific(seeded, reranker):
    body = search(seeded, "V BELT C 120")
    ids = [r["material_id"] for r in body["results"]]
    assert set(ids[:2]) == {"NTPC-M55321", "BHEL-224411"}
    assert ids.index("NTPC-M55399") > 1  # the C 125 belt is behind both C 120s
    bolt = next(r for r in body["results"] if r["material_id"] == "BHEL-778899")
    assert bolt["match_level"] == "none"
    for hit in body["results"]:
        assert hit["final_score"] == pytest.approx(
            0.3 * max(0.0, hit["qdrant_score"]) + 0.7 * hit["siamese_score"], abs=1e-3
        )


def test_a_sentence_still_finds_the_belt(seeded, reranker):
    body = search(seeded, "industrial V belt C section approximately 1200 mm")
    assert "BELT" in body["results"][0]["description"]


def test_a_mixed_query_combines_identifier_and_vector(seeded, reranker):
    body = search(seeded, "V belt C 120 M-55321")
    top = body["results"][0]
    assert top["material_id"] == "NTPC-M55321"
    assert set(top["matched_by"]) == {"identifier", "vector"}
    assert top["qdrant_score"] is not None and top["siamese_score"] is not None
    assert body["pipeline"]["identifier_only"] is False
    assert body["pipeline"]["vector_search_ran"] is True


def test_an_unrelated_query_is_not_a_match(seeded, reranker):
    body = search(seeded, "some completely unrelated material")
    assert body["best_match_level"] == "none"
    assert all(r["match"] is False for r in body["results"])
    assert "none a confident match" in body["message"]


def test_the_reranker_is_called_once_per_query_with_the_whole_pool(seeded, reranker):
    search(seeded, "V BELT C 120")
    assert reranker.calls == [len(ROWS)]


def test_top_k_and_final_k_are_honoured(seeded, reranker):
    body = search(seeded, "V BELT", top_k=3, final_k=2)
    assert len(body["results"]) == 2
    assert body["pipeline"]["top_k"] == 3
    assert body["total_candidates"] == 3
    clipped = search(seeded, "V BELT", top_k=2, final_k=50)
    assert clipped["pipeline"]["final_k"] == 2


# --------------------------------------------------------------------------
# Failure and degradation
# --------------------------------------------------------------------------

def test_an_empty_query_is_refused(client, reranker):
    assert client.post("/api/v1/search", json={"query": ""}).status_code == 422
    assert client.post("/api/v1/search", json={"query": "   "}).status_code == 422
    assert client.post("/api/v1/search", json={}).status_code == 422


def test_an_empty_index_answers_with_no_results(client, reranker):
    body = search(client, "V BELT C 120")
    assert body["results"] == []
    assert body["best_match_level"] == "none"
    assert "no candidates" in body["message"]


def test_without_the_reranker_results_are_ordered_by_qdrant_and_capped(seeded, monkeypatch):
    reranker_service.set_reranker(None)
    monkeypatch.setattr(settings, "search_match_threshold", 0.0)
    monkeypatch.setattr(settings, "search_possible_threshold", 0.0)
    body = search(seeded, "V BELT C 120")
    assert body["pipeline"]["reranker_applied"] is False
    assert "No trained Siamese checkpoint" in body["pipeline"]["reranker_detail"]
    assert all(r["siamese_score"] is None for r in body["results"])
    assert all(r["match_level"] == "possible" for r in body["results"])
    assert body["best_match_level"] == "possible"
    assert "not applied" in body["message"]
    scores = [r["qdrant_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_with_the_reranker_the_same_thresholds_allow_high(seeded, reranker, monkeypatch):
    monkeypatch.setattr(settings, "search_match_threshold", 0.0)
    monkeypatch.setattr(settings, "search_possible_threshold", 0.0)
    assert search(seeded, "V BELT C 120")["best_match_level"] == "high"


def test_a_reranker_that_raises_degrades_instead_of_failing(seeded):
    reranker_service.set_reranker(ExplodingReranker())
    try:
        body = search(seeded, "V BELT C 120")
    finally:
        reranker_service.set_reranker(None)
    assert body["pipeline"]["reranker_applied"] is False
    assert "CUDA fell over" in body["pipeline"]["reranker_detail"]
    assert len(body["results"]) == 5


def test_reranker_disabled_by_configuration(seeded, monkeypatch):
    monkeypatch.setattr(settings, "search_reranker_enabled", False)
    reranker_service.set_reranker(None)
    body = search(seeded, "V BELT")
    assert body["pipeline"]["reranker_applied"] is False
    assert "SEARCH_RERANKER_ENABLED=false" in body["pipeline"]["reranker_detail"]


def test_an_unreachable_store_is_a_503_without_an_identifier(seeded, reranker, monkeypatch):
    from app.logic import retrieval

    class Down:
        def search(self, *_, **__):
            raise ConnectionError("qdrant is down")

    monkeypatch.setattr(retrieval, "_store", Down())
    response = seeded.post("/api/v1/search", json={"query": "V BELT C 120"})
    assert response.status_code == 503
    assert "qdrant is down" in response.json()["detail"]


def test_an_unreachable_store_still_answers_an_identifier(seeded, reranker, monkeypatch):
    from app.logic import retrieval

    class Down:
        def search(self, *_, **__):
            raise ConnectionError("qdrant is down")

    monkeypatch.setattr(retrieval, "_store", Down())
    body = search(seeded, "V belt C 120 M-55321")
    assert body["results"][0]["material_id"] == "NTPC-M55321"
    assert body["pipeline"]["store_error"] == "qdrant is down"
    assert "identifier lookup only" in body["message"]


def test_duplicate_candidates_are_scored_once(seeded, reranker, monkeypatch):
    """A store that returns the same id twice, and an id that is also an
    identifier hit, are one candidate each."""
    from app.logic import retrieval

    real = retrieval.get_store()

    class Doubling:
        def search(self, *args, **kwargs):
            hits = real.search(*args, **kwargs)
            return hits + hits

    monkeypatch.setattr(retrieval, "_store", Doubling())
    body = search(seeded, "V BELT C 120 M-55321", top_k=20, final_k=20)
    ids = [r["material_id"] for r in body["results"]]
    assert len(ids) == len(set(ids)) == len(ROWS)
    assert body["pipeline"]["candidates_retrieved"] == 2 * len(ROWS)
    assert reranker.calls == [len(ROWS)]


def _break_embedding(monkeypatch):
    from app.logic import embedding
    from app.services import search as search_service

    def broken(**_):
        raise RuntimeError("EMBEDDING_PROVIDER=qwen3 needs torch")

    monkeypatch.setattr(embedding, "get_provider", broken)
    monkeypatch.setattr(search_service, "get_provider", broken)


def test_an_unloadable_embedding_model_is_a_503_without_an_identifier(
    seeded, reranker, monkeypatch
):
    _break_embedding(monkeypatch)
    response = seeded.post("/api/v1/search", json={"query": "V BELT C 120"})
    assert response.status_code == 503
    assert "embedding model could not be loaded" in response.json()["detail"]
    assert "needs torch" in response.json()["detail"]


def test_an_unloadable_embedding_model_still_answers_an_identifier(
    seeded, reranker, monkeypatch
):
    _break_embedding(monkeypatch)
    body = search(seeded, "V belt C 120 M-55321")
    assert body["results"][0]["material_id"] == "NTPC-M55321"
    assert body["pipeline"]["embedding_error"] is not None
    assert body["pipeline"]["degraded"] is True
    assert any("Embedding model unavailable" in w for w in body["pipeline"]["warnings"])
    assert "identifier lookup only" in body["message"]
    info = seeded.get("/api/v1/search/model/info").json()
    assert info["embedding"]["available"] is False
    assert "needs torch" in info["embedding"]["error"]
    assert info["degraded"] is True


def test_the_fallback_embedding_is_declared_degraded(seeded, reranker):
    body = search(seeded, "V BELT")
    assert body["pipeline"]["embedding_is_fallback"] is True
    assert body["pipeline"]["degraded"] is True
    assert any("seeded-hash fallback" in w for w in body["pipeline"]["warnings"])


def test_model_info_reports_the_live_state(client):
    reranker_service.set_reranker(None)
    body = client.get("/api/v1/search/model/info").json()
    assert body["embedding"]["available"] is True
    assert body["embedding"]["is_fallback"] is True
    assert body["embedding"]["dimension"] == settings.embedding_dimension
    assert body["degraded"] is True
    assert body["reranker"]["available"] is False
    assert "No trained Siamese checkpoint" in body["reranker"]["detail"]
    assert body["search"]["qdrant_weight"] + body["search"]["siamese_weight"] == pytest.approx(1.0)
