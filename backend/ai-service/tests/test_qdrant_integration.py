"""Qdrant integration - opt-in, needs a live server.

    make up               # or: docker compose up -d qdrant
    QDRANT_TEST_URL=http://localhost:6333 pytest tests/test_qdrant_integration.py

Against Qdrant Cloud, add the key - the managed cluster refuses an anonymous
request, and the same ten tests then prove the contract holds over TLS as well
as over a loopback socket:

    QDRANT_TEST_URL=https://<cluster>.cloud.qdrant.io \
    QDRANT_TEST_API_KEY=<key> pytest tests/test_qdrant_integration.py

Skipped by default so the normal suite stays a 3-second, dependency-free run.
The in-memory store in test_retrieval.py covers the same contract; this file
exists because a protocol both implementations satisfy in theory can still
diverge in practice - filter translation and payload indexing are where that
happens.
"""

from __future__ import annotations

import os
import uuid

import numpy as np
import pytest

from app.config import settings
from app.logic.retrieval import BlockingFilter, MaterialPoint

QDRANT_URL = os.getenv("QDRANT_TEST_URL")
QDRANT_API_KEY = os.getenv("QDRANT_TEST_API_KEY")

pytestmark = pytest.mark.skipif(
    not QDRANT_URL, reason="set QDRANT_TEST_URL to run Qdrant integration tests"
)


@pytest.fixture
def store():
    from app.logic.retrieval import QdrantStore

    collection = f"test_{uuid.uuid4().hex[:8]}"
    # api_key is passed explicitly rather than read from settings, so this file
    # can point at a throwaway cluster without touching the service config.
    store = QdrantStore(url=QDRANT_URL, collection=collection, api_key=QDRANT_API_KEY)
    store.ensure_collection(dimension=4, recreate=True)
    yield store
    store._client.delete_collection(collection)


def _point(material_id, vector, *, category="BEARING", uom_dimension="COUNT", cpse="NTPC"):
    return MaterialPoint(
        material_id=material_id, vector=np.asarray(vector, dtype=np.float32),
        category=category, cpse_code=cpse, uom_dimension=uom_dimension,
        canonical_description=material_id, canonical_hash="h",
        embedding_version=settings.embedding_version,
    )


def test_upsert_and_count(store):
    store.upsert([_point("A", [1, 0, 0, 0]), _point("B", [0, 1, 0, 0])])
    assert store.count() == 2


def test_upsert_is_idempotent(store):
    """Point id derives from material_id, so a retried batch must not duplicate."""
    point = _point("A", [1, 0, 0, 0])
    store.upsert([point])
    store.upsert([point])
    assert store.count() == 1


def test_search_ranks_by_cosine(store):
    store.upsert([
        _point("A", [1, 0, 0, 0]),
        _point("B", [0, 1, 0, 0]),
        _point("C", [0.7071, 0.7071, 0, 0]),
    ])
    hits = store.search(
        np.array([1, 0, 0, 0], dtype=np.float32), top_k=3, block=BlockingFilter()
    )
    assert [h.material_id for h in hits] == ["A", "C", "B"]


def test_category_filter_constrains_the_traversal(store):
    """The filter must reach Qdrant, not be applied after the fact - otherwise
    top-K fills with wrong-category noise and the true match falls off."""
    store.upsert([
        _point("BRG-1", [1, 0, 0, 0], category="BEARING"),
        _point("BLT-1", [1, 0, 0, 0], category="FASTENER"),
        _point("BRG-2", [0.9, 0.1, 0, 0], category="BEARING"),
    ])
    hits = store.search(
        np.array([1, 0, 0, 0], dtype=np.float32), top_k=10,
        block=BlockingFilter(categories=("BEARING",)),
    )
    assert {h.material_id for h in hits} == {"BRG-1", "BRG-2"}


def test_uom_dimension_filter(store):
    store.upsert([
        _point("COUNT-1", [1, 0, 0, 0], uom_dimension="COUNT"),
        _point("MASS-1", [1, 0, 0, 0], uom_dimension="MASS"),
    ])
    hits = store.search(
        np.array([1, 0, 0, 0], dtype=np.float32), top_k=10,
        block=BlockingFilter(uom_dimensions=("COUNT",)),
    )
    assert [h.material_id for h in hits] == ["COUNT-1"]


def test_a_material_never_retrieves_itself(store):
    store.upsert([_point("A", [1, 0, 0, 0]), _point("B", [0.99, 0.01, 0, 0])])
    hits = store.search(
        np.array([1, 0, 0, 0], dtype=np.float32), top_k=10,
        block=BlockingFilter(exclude_ids=("A",)),
    )
    assert [h.material_id for h in hits] == ["B"]


def test_stale_embedding_version_is_not_retrieved(store):
    """During a reindex both generations coexist; the old must not leak."""
    old = MaterialPoint(
        material_id="OLD", vector=np.array([1, 0, 0, 0], dtype=np.float32),
        category="BEARING", cpse_code="NTPC", uom_dimension="COUNT",
        canonical_description="old", canonical_hash="h", embedding_version="v0",
    )
    store.upsert([old, _point("NEW", [1, 0, 0, 0])])
    hits = store.search(
        np.array([1, 0, 0, 0], dtype=np.float32), top_k=10,
        block=BlockingFilter(embedding_version=settings.embedding_version),
    )
    assert [h.material_id for h in hits] == ["NEW"]


def test_delete(store):
    store.upsert([_point("A", [1, 0, 0, 0]), _point("B", [0, 1, 0, 0])])
    store.delete(["A"])
    assert store.count() == 1


def test_count_honours_the_filter(store):
    store.upsert([
        _point("A", [1, 0, 0, 0], category="BEARING"),
        _point("B", [0, 1, 0, 0], category="FASTENER"),
    ])
    assert store.count(block=BlockingFilter(categories=("BEARING",))) == 1


def test_dimension_mismatch_fails_loudly(store):
    """Silently padding or truncating produces plausible, WRONG neighbours."""
    with pytest.raises(RuntimeError, match="Reindex"):
        store.ensure_collection(dimension=99, recreate=False)
