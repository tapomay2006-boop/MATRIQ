"""Vector store: the only abstraction over Qdrant.

Blocking is not a post-filter applied to ANN results - it constrains the search
itself, or the top-K fills with same-category-but-wrong-article noise and the
true match falls off the list (docs/05 §4.2).

    Postgres is the source of truth. Qdrant is derived state.
    If it is deleted entirely, nothing of value is lost: every vector is
    reproducible from canonical text by re-running the active model.
    Rebuild is a job, not an incident.  (docs/05 §7.1)

Consequences enforced here: no business decision reads from this module except
candidate *retrieval*, and no field exists only in a payload.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from app.config import settings

#: Payload keys that must be indexed for filtered ANN to stay fast.
INDEXED_PAYLOAD_KEYS = (
    "category",
    "cpse_code",
    "uom_dimension",
    "embedding_version",
    # Not a blocking key - this one carries the self-exclusion filter, which
    # every single search sends ("a material must never match itself").
    # A local container will happily filter an unindexed field with a full
    # scan; Qdrant Cloud runs strict mode and rejects the query outright, so
    # omitting this index works on a laptop and 400s in production.
    "material_id",
)


@dataclass(frozen=True)
class MaterialPoint:
    """One material's vector plus the projection needed to *block*.

    The payload is a projection, never the record. Unit rate, vendor and
    quantity are deliberately absent: per-CPSE price confidentiality is the
    adoption-critical control, so that data stays in Postgres behind repository
    scoping (docs/05 §4.1).
    """

    material_id: str
    vector: np.ndarray
    cpse_code: str
    canonical_description: str
    canonical_hash: str
    embedding_version: str = field(default_factory=lambda: settings.embedding_version)

    #: The identifier the national master owns (logic/national_id.py). In the
    #: payload so a neighbour search surfaces can be named nationally without a
    #: Postgres round-trip. Never part of the vector.
    national_id: str | None = None

    #: Blocking keys. Both are unset today: nothing upstream classifies a row
    #: or normalises its unit any more, so every point carries the same empty
    #: value and `BlockingFilter` is effectively a no-op on them. They are kept
    #: - as payload, as indexed Qdrant fields and in the filter below - because
    #: the search that will use them is the next thing to be built, and adding
    #: an indexed payload field to a live collection later means recreating it.
    category: str = ""
    uom_dimension: str | None = None

    def payload(self) -> dict[str, object]:
        return {
            "material_id": self.material_id,
            "national_id": self.national_id,
            "category": self.category,
            "cpse_code": self.cpse_code,
            "uom_dimension": self.uom_dimension,
            "canonical_description": self.canonical_description,
            "canonical_hash": self.canonical_hash,
            "embedding_version": self.embedding_version,
        }


@dataclass(frozen=True)
class BlockingFilter:
    """What may legitimately be compared.

    Cross-CPSE is deliberately NOT filtered out: finding duplicates across
    CPSEs is the entire point, and the same query finds intra-CPSE duplicates,
    which are often the highest-value early win (docs/05 §5.1).
    """

    categories: tuple[str, ...] = ()
    uom_dimensions: tuple[str, ...] = ()
    exclude_ids: tuple[str, ...] = ()
    embedding_version: str | None = None

    def accepts(self, point: MaterialPoint) -> bool:
        if point.material_id in self.exclude_ids:
            return False
        if self.categories and point.category not in self.categories:
            return False
        if self.uom_dimensions and point.uom_dimension not in self.uom_dimensions:
            return False
        if self.embedding_version and point.embedding_version != self.embedding_version:
            return False
        return True


@dataclass(frozen=True)
class RetrievedCandidate:
    material_id: str
    embedding_score: float
    category: str
    cpse_code: str


#: Queries per `query_batch_points` call. Bounded by request size, not by
#: compute: every query carries a full float32 vector, so 128 x 1024 dims is
#: about 512 KB on the wire - large enough to amortise the round-trip, small
#: enough to stay well inside the default body limit.
BATCH_QUERY_SIZE = 128


class VectorStore(Protocol):
    def ensure_collection(self, *, dimension: int, recreate: bool = False) -> None: ...

    def upsert(self, points: Sequence[MaterialPoint], *, batch_size: int = 256) -> int: ...

    def search(
        self,
        vector: np.ndarray,
        *,
        top_k: int = 10,
        block: BlockingFilter,
        score_threshold: float | None = None,
    ) -> list[RetrievedCandidate]: ...

    def search_batch(
        self,
        vectors: Sequence[np.ndarray],
        *,
        top_k: int = 10,
        blocks: Sequence[BlockingFilter],
        score_threshold: float | None = None,
    ) -> list[list[RetrievedCandidate]]:
        """Answer many queries in as few round-trips as the backend allows.

        Exists because the caller-side loop was the single largest cost in the
        service: one HTTPS call per material against a hosted Qdrant measured
        257 ms warm, so matching a 404-row corpus spent 104 seconds waiting on
        the network and 0.9 seconds computing. Batching collapses that to a
        handful of calls. Returns one result list per input vector, in order.
        """
        ...

    def delete(self, material_ids: Sequence[str]) -> None: ...

    def count(self, *, block: BlockingFilter | None = None) -> int: ...


class InMemoryVectorStore:
    """Exact search over the same interface.

    Not an approximation of Qdrant - it is the ground truth Qdrant approximates,
    which makes it the right thing to test recall against. O(N) per query, which
    is irrelevant at this corpus size and unacceptable at a national one.
    """

    def __init__(self) -> None:
        self._points: dict[str, MaterialPoint] = {}

    def ensure_collection(self, *, dimension: int, recreate: bool = False) -> None:
        if recreate:
            self._points.clear()

    def upsert(self, points: Sequence[MaterialPoint], *, batch_size: int = 256) -> int:
        for point in points:
            self._points[point.material_id] = point
        return len(points)

    def search(
        self,
        vector: np.ndarray,
        *,
        top_k: int = 10,
        block: BlockingFilter,
        score_threshold: float | None = None,
    ) -> list[RetrievedCandidate]:
        eligible = [p for p in self._points.values() if block.accepts(p)]
        if not eligible:
            return []

        matrix = np.vstack([p.vector for p in eligible])
        # Vectors are L2-normalised at generation, so cosine is a dot product.
        scores = matrix @ vector.astype(np.float32)

        order = np.argsort(-scores)[:top_k]
        out: list[RetrievedCandidate] = []
        for index in order:
            score = float(scores[index])
            if score_threshold is not None and score < score_threshold:
                continue
            point = eligible[index]
            out.append(RetrievedCandidate(
                material_id=point.material_id, embedding_score=score,
                category=point.category, cpse_code=point.cpse_code,
            ))
        return out

    def search_batch(
        self,
        vectors: Sequence[np.ndarray],
        *,
        top_k: int = 10,
        blocks: Sequence[BlockingFilter],
        score_threshold: float | None = None,
    ) -> list[list[RetrievedCandidate]]:
        """A loop, and correctly so: there is no round-trip to amortise here."""
        return [
            self.search(v, top_k=top_k, block=b, score_threshold=score_threshold)
            for v, b in zip(vectors, blocks, strict=True)
        ]

    def delete(self, material_ids: Sequence[str]) -> None:
        for material_id in material_ids:
            self._points.pop(material_id, None)

    def count(self, *, block: BlockingFilter | None = None) -> int:
        if block is None:
            return len(self._points)
        return sum(1 for p in self._points.values() if block.accepts(p))


class QdrantStore:
    """Filtered ANN. The filter is part of the traversal, not a WHERE clause."""

    def __init__(
        self,
        url: str | None = None,
        collection: str | None = None,
        *,
        api_key: str | None = None,
    ) -> None:
        from qdrant_client import QdrantClient

        self.collection = collection or settings.qdrant_collection
        key = api_key if api_key is not None else settings.qdrant_api_key

        # A managed cluster needs the key and speaks HTTPS; a local container
        # needs neither. One client construction covers both, because an empty
        # key is simply not sent.
        self._client = QdrantClient(
            url=url or settings.qdrant_url,
            api_key=key or None,
            timeout=settings.qdrant_timeout,
            prefer_grpc=settings.qdrant_prefer_grpc,
        )

    def ensure_collection(self, *, dimension: int, recreate: bool = False) -> None:
        from qdrant_client import models as qm

        exists = self._client.collection_exists(self.collection)
        if exists and not recreate:
            info = self._client.get_collection(self.collection)
            live = info.config.params.vectors.size
            if live != dimension:
                # Never silently truncate or pad - that yields plausible, wrong
                # neighbours. Fail loudly at boot (docs/05 §8).
                raise RuntimeError(
                    f"Collection {self.collection!r} is {live}-d but the active "
                    f"provider is {dimension}-d. Reindex into a new collection."
                )
            return

        if exists:
            self._client.delete_collection(self.collection)

        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=dimension, distance=qm.Distance.COSINE),
            hnsw_config=qm.HnswConfigDiff(
                m=settings.hnsw_m,
                ef_construct=settings.hnsw_ef_construct,
                full_scan_threshold=10_000,
            ),
            optimizers_config=qm.OptimizersConfigDiff(default_segment_number=2),
        )
        for key in INDEXED_PAYLOAD_KEYS:
            # Filtered ANN is only fast if the filter fields are indexed.
            self._client.create_payload_index(
                collection_name=self.collection,
                field_name=key,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )

    def _to_filter(self, block: BlockingFilter):
        from qdrant_client import models as qm

        must: list[object] = []
        if block.categories:
            must.append(qm.FieldCondition(
                key="category", match=qm.MatchAny(any=list(block.categories))
            ))
        if block.uom_dimensions:
            must.append(qm.FieldCondition(
                key="uom_dimension", match=qm.MatchAny(any=list(block.uom_dimensions))
            ))
        if block.embedding_version:
            must.append(qm.FieldCondition(
                key="embedding_version",
                match=qm.MatchValue(value=block.embedding_version),
            ))

        must_not: list[object] = []
        if block.exclude_ids:
            must_not.append(qm.FieldCondition(
                key="material_id", match=qm.MatchAny(any=list(block.exclude_ids))
            ))
        return qm.Filter(must=must or None, must_not=must_not or None)

    @staticmethod
    def _point_id(material_id: str) -> str:
        """Qdrant ids must be a UUID or an int; material_id is neither.

        Deriving it deterministically keeps upsert idempotent, so a retried
        batch is harmless.
        """
        import uuid

        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"material:{material_id}"))

    def upsert(self, points: Sequence[MaterialPoint], *, batch_size: int = 256) -> int:
        from qdrant_client import models as qm

        written = 0
        for start in range(0, len(points), batch_size):
            chunk = points[start : start + batch_size]
            self._client.upsert(
                collection_name=self.collection,
                points=[
                    qm.PointStruct(
                        id=self._point_id(p.material_id),
                        vector=p.vector.astype(np.float32).tolist(),
                        payload=p.payload(),
                    )
                    for p in chunk
                ],
            )
            written += len(chunk)
        return written

    def search(
        self,
        vector: np.ndarray,
        *,
        top_k: int = 10,
        block: BlockingFilter,
        score_threshold: float | None = None,
    ) -> list[RetrievedCandidate]:
        hits = self._client.query_points(
            collection_name=self.collection,
            query=vector.astype(np.float32).tolist(),
            query_filter=self._to_filter(block),
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        ).points
        return [
            RetrievedCandidate(
                material_id=str(h.payload["material_id"]),
                embedding_score=float(h.score),
                category=str(h.payload.get("category", "")),
                cpse_code=str(h.payload.get("cpse_code", "")),
            )
            for h in hits
        ]

    def search_batch(
        self,
        vectors: Sequence[np.ndarray],
        *,
        top_k: int = 10,
        blocks: Sequence[BlockingFilter],
        score_threshold: float | None = None,
    ) -> list[list[RetrievedCandidate]]:
        """One HTTP call per chunk instead of one per query.

        `query_batch_points` is the whole reason this method exists: against a
        hosted cluster the per-call latency dominates everything else, so the
        chunk size is about staying under the request size limit, not about
        compute.
        """
        from qdrant_client import models as qm

        if not vectors:
            return []

        requests = [
            qm.QueryRequest(
                query=v.astype(np.float32).tolist(),
                filter=self._to_filter(b),
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            )
            for v, b in zip(vectors, blocks, strict=True)
        ]

        out: list[list[RetrievedCandidate]] = []
        for start in range(0, len(requests), BATCH_QUERY_SIZE):
            chunk = requests[start : start + BATCH_QUERY_SIZE]
            responses = self._client.query_batch_points(
                collection_name=self.collection, requests=chunk
            )
            for response in responses:
                out.append([
                    RetrievedCandidate(
                        material_id=str(h.payload["material_id"]),
                        embedding_score=float(h.score),
                        category=str(h.payload.get("category", "")),
                        cpse_code=str(h.payload.get("cpse_code", "")),
                    )
                    for h in response.points
                ])
        return out

    def delete(self, material_ids: Sequence[str]) -> None:
        from qdrant_client import models as qm

        self._client.delete(
            collection_name=self.collection,
            points_selector=qm.PointIdsList(
                points=[self._point_id(m) for m in material_ids]
            ),
        )

    def count(self, *, block: BlockingFilter | None = None) -> int:
        result = self._client.count(
            collection_name=self.collection,
            count_filter=self._to_filter(block) if block else None,
            exact=True,
        )
        return int(result.count)


_store: VectorStore | None = None


def get_store(*, refresh: bool = False) -> VectorStore:
    global _store
    if _store is not None and not refresh:
        return _store
    if settings.vector_store == "qdrant":
        try:
            _store = QdrantStore()
        except ImportError as exc:
            raise RuntimeError(
                "VECTOR_STORE=qdrant needs qdrant-client: pip install qdrant-client"
            ) from exc
    else:
        _store = InMemoryVectorStore()
    return _store
