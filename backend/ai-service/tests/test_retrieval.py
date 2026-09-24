"""The vector index: the embedded text, the hash that guards it, and the store.

Search is built on top of this and is not implemented yet. What is pinned here
is the contract that search will rest on - cosine ordering, self-exclusion,
idempotent upsert, and the embedding-version guard that keeps an old generation
of vectors from leaking into a live result.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.config import settings
from app.logic.embedding import (
    DeterministicProvider,
    canonical_hash,
    embedding_text,
    get_provider,
)
from app.logic.retrieval import BlockingFilter, InMemoryVectorStore, MaterialPoint
from app.logic.standard_format import parse_row
from app.logic.standardize import to_material
from app.services.indexing import build_points
from tests.conftest import standard_row


def _material(description: str, **overrides):
    return to_material(parse_row(standard_row(description, **overrides), 1))


# --------------------------------------------------------------------------
# The provider
# --------------------------------------------------------------------------

def test_vectors_are_unit_length():
    """The provider L2-normalises, which is what makes cosine a dot product."""
    vectors = DeterministicProvider(dimension=64).embed(["a", "b", "c"])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-6)


def test_embedding_is_deterministic():
    provider = DeterministicProvider(dimension=32)
    assert np.array_equal(provider.embed(["same"]), provider.embed(["same"]))


def test_empty_input_returns_empty_matrix():
    assert DeterministicProvider(dimension=8).embed([]).shape == (0, 8)


def test_fallback_provider_declares_itself():
    """A demo must never claim Qwen3 quality while running the seeded hash."""
    info = get_provider(refresh=True).info()
    assert info.is_fallback is True
    assert "not meaningful" in info.detail or "no semantic signal" in info.detail


# --------------------------------------------------------------------------
# What gets embedded
# --------------------------------------------------------------------------

def test_embedded_text_is_the_identity_attributes():
    text = embedding_text(_material("BALL BEARING 6205 2RS", **{"Make / Brand": "SKF"}))
    assert "Item Description (Raw): BALL BEARING 6205 2RS" in text
    assert "Make / Brand: SKF" in text


def test_company_legacy_code_and_quantity_are_not_embedded():
    """Each of the three would break the thing the vector exists to do: find
    the same article in another CPSE's master. The company name, that CPSE's
    internal code and its stock level all differ between two copies of one
    physical part."""
    ntpc = _material("BALL BEARING 6205 2RS", **{
        "Company": "NTPC", "Item Code / Legacy Ref": "1001", "Quantity": 5,
    })
    bhel = _material("BALL BEARING 6205 2RS", **{
        "Company": "BHEL", "Item Code / Legacy Ref": "ZZ-77", "Quantity": 9000,
    })

    assert "NTPC" not in embedding_text(ntpc)
    assert "1001" not in embedding_text(ntpc)
    assert embedding_text(ntpc) == embedding_text(bhel)
    assert canonical_hash(ntpc) == canonical_hash(bhel)

    # ...and none of it is lost: identity still separates the two rows.
    assert ntpc.material_id != bhel.material_id
    assert ntpc.attributes["Company"] == "NTPC"
    assert ntpc.attributes["Quantity"] == "5"


def test_absent_attributes_are_omitted_not_written_as_na():
    """Phase 1 writes "NA" for what it could not ground. Letting that through
    would give every sparse row the same filler tokens, so rows would start
    matching on what they are MISSING."""
    text = embedding_text(_material("HEX BOLT M12"))
    assert "NA" not in text
    assert "Part Number" not in text


def test_attribute_order_is_fixed_not_payload_order():
    """Two producers spelling the same row in a different key order must embed
    to the same vector, or the duplicate check never fires."""
    forward = parse_row(
        {"Company": "NTPC", "Item Description (Raw)": "V-BELT C 120",
         "UOM": "NOS", "Make / Brand": "FENNER"}, 1
    )
    reversed_keys = parse_row(
        {"Make / Brand": "FENNER", "UOM": "NOS",
         "Item Description (Raw)": "V-BELT C 120", "Company": "NTPC"}, 1
    )
    assert embedding_text(to_material(forward)) == embedding_text(to_material(reversed_keys))


def test_canonical_hash_changes_when_the_text_changes():
    a = _material("BALL BEARING 6205 2RS")
    b = _material("BALL BEARING 6206 2RS")
    assert canonical_hash(a) != canonical_hash(b)


def test_canonical_hash_is_stable_for_the_same_row():
    row = standard_row("BALL BEARING 6205 2RS")
    assert canonical_hash(to_material(parse_row(row, 1))) == canonical_hash(
        to_material(parse_row(dict(row), 1))
    )


def test_build_points_carries_the_hash_and_the_version():
    points = build_points([_material("BALL BEARING 6205 2RS")])
    assert len(points) == 1
    assert points[0].canonical_hash
    assert points[0].embedding_version == settings.embedding_version


# --------------------------------------------------------------------------
# Vector store contract
# --------------------------------------------------------------------------

def _point(material_id, vector, *, category="BEARING", uom_dimension="COUNT"):
    return MaterialPoint(
        material_id=material_id, vector=np.asarray(vector, dtype=np.float32),
        category=category, cpse_code="NTPC", uom_dimension=uom_dimension,
        canonical_description=material_id, canonical_hash="h",
        embedding_version=settings.embedding_version,
    )


def test_search_ranks_by_cosine():
    store = InMemoryVectorStore()
    store.upsert([
        _point("A", [1.0, 0.0]),
        _point("B", [0.0, 1.0]),
        _point("C", [0.7071, 0.7071]),
    ])

    hits = store.search(
        np.array([1.0, 0.0], dtype=np.float32), top_k=3, block=BlockingFilter()
    )
    assert [h.material_id for h in hits] == ["A", "C", "B"]
    assert hits[0].embedding_score == pytest.approx(1.0, abs=1e-5)


def test_a_material_never_retrieves_itself():
    store = InMemoryVectorStore()
    store.upsert([_point("A", [1.0, 0.0]), _point("B", [0.9, 0.1])])

    hits = store.search(
        np.array([1.0, 0.0], dtype=np.float32), top_k=5,
        block=BlockingFilter(exclude_ids=("A",)),
    )
    assert [h.material_id for h in hits] == ["B"]


def test_incompatible_uom_dimension_is_excluded_from_the_search():
    """The UOM gate must constrain retrieval, not just scoring: a bolt counted
    in EA and one sold per KG are not the same stock item."""
    store = InMemoryVectorStore()
    store.upsert([
        _point("COUNT-1", [1.0, 0.0], uom_dimension="COUNT"),
        _point("MASS-1", [1.0, 0.0], uom_dimension="MASS"),
    ])

    hits = store.search(
        np.array([1.0, 0.0], dtype=np.float32), top_k=5,
        block=BlockingFilter(uom_dimensions=("COUNT",)),
    )
    assert [h.material_id for h in hits] == ["COUNT-1"]


def test_upsert_is_idempotent():
    """A retried batch must be harmless: point id derives from material_id."""
    store = InMemoryVectorStore()
    point = _point("A", [1.0, 0.0])
    store.upsert([point])
    store.upsert([point])
    assert store.count() == 1


def test_stale_embedding_version_is_not_retrieved():
    """After an EMBEDDING_VERSION change the old generation is still in the
    store. It must not leak into results alongside the new one."""
    store = InMemoryVectorStore()
    old = MaterialPoint(
        material_id="OLD", vector=np.array([1.0, 0.0], dtype=np.float32),
        category="BEARING", cpse_code="NTPC", uom_dimension="COUNT",
        canonical_description="old", canonical_hash="h", embedding_version="v0",
    )
    store.upsert([old, _point("NEW", [1.0, 0.0])])

    hits = store.search(
        np.array([1.0, 0.0], dtype=np.float32), top_k=5,
        block=BlockingFilter(embedding_version=settings.embedding_version),
    )
    assert [h.material_id for h in hits] == ["NEW"]


def test_delete_removes_the_point():
    store = InMemoryVectorStore()
    store.upsert([_point("A", [1.0, 0.0])])
    store.delete(["A"])
    assert store.count() == 0
