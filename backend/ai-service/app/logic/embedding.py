"""Embedding providers, and what gets embedded.

The vector has two jobs here, and both are retrieval: decide whether an
incoming standard-format row is *the same article* as something already in
the index (`POST /standardized/check`), and find the top-K candidates for a
free-form query (`POST /search`, services/search.py) - which a separate,
trained Siamese model then reranks (logic/siamese.py). Nothing about what is
embedded or how changed for search to exist.

Two implementations behind one protocol. Qwen3 is the real model; the
deterministic provider is a seeded hash that makes similarity *meaningless* but
the pipeline *exercisable*, so the whole check/add flow runs in seconds with no
1.2 GB download. `GET /retrieval/model/info` always reports which one answered,
so a demo can never claim Qwen3 quality on fallback vectors.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from app.config import settings
from app.logic.standardize import StandardMaterial

EmbedKind = Literal["document", "query"]

#: Qwen3 is instruction-aware: a domain prefix measurably sharpens same-domain
#: retrieval. Documents and queries must be encoded consistently or quality
#: degrades silently (docs/05 §2.1).
INSTRUCTIONS = {
    "document": "Represent this industrial material specification for retrieval: ",
    "query": (
        "Instruct: Given a material specification, retrieve the same physical "
        "article described differently.\nQuery: "
    ),
}


@dataclass(frozen=True)
class ProviderInfo:
    model_name: str
    model_version: str
    dimension: int
    is_fallback: bool
    detail: str


class EmbeddingProvider(Protocol):
    model_name: str
    model_version: str
    dimension: int

    def embed(
        self, texts: Sequence[str], *, kind: EmbedKind = "document"
    ) -> np.ndarray:
        """L2-normalised float32, shape (len(texts), dimension)."""

    def info(self) -> ProviderInfo: ...


# --------------------------------------------------------------------------
# What gets embedded
# --------------------------------------------------------------------------

def embedding_text(material: StandardMaterial) -> str:
    """What actually gets embedded: the attributes that identify the article.

    Five of the eight, in a fixed order. Company, the CPSE's internal legacy
    code and the stock quantity are excluded - `StandardMaterial.
    identity_attributes` explains why each one would break cross-CPSE
    duplicate detection if it were in the vector.

    Fixed order, not the order the keys arrived in: two producers spelling the
    same row differently must produce the same string, or two identical
    articles embed to two different vectors and the duplicate check never
    fires.

    Absent attributes are omitted rather than written as "NA". Phase 1 emits
    "NA" for anything it could not ground, and letting those through would give
    every sparse row the same handful of filler tokens - rows would start
    matching on what they are *missing*, which is the one similarity that
    carries no information at all.
    """
    return "\n".join(
        f"{name}: {value}" for name, value in material.identity_attributes.items()
    )


def canonical_hash(material: StandardMaterial) -> str:
    """Detects a stale vector whose source text has since changed.

    Hashed over the embedded text, not the raw description, because that is
    exactly what determines the vector. It doubles as the exact-duplicate
    signal in the existence check: two rows with the same hash would produce
    the same vector, so the second one adds nothing.
    """
    payload = f"{settings.embedding_version}|{embedding_text(material)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------

def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # A zero vector has no direction; leave it rather than dividing by zero.
    norms[norms == 0.0] = 1.0
    return (matrix / norms).astype(np.float32)


class DeterministicProvider:
    """Seeded hash -> stable unit vector. Same text always gives same vector.

    Retrieval quality is meaningless by construction, and that is the point:
    it is honest about being a stand-in rather than degrading quietly.
    """

    model_name = "deterministic-hash"
    model_version = "deterministic-v1"

    def __init__(self, dimension: int | None = None) -> None:
        self.dimension = dimension or settings.embedding_dimension

    def embed(
        self, texts: Sequence[str], *, kind: EmbedKind = "document"
    ) -> np.ndarray:
        out = np.empty((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            seed = int.from_bytes(
                hashlib.sha256(text.encode("utf-8")).digest()[:8], "big"
            )
            rng = np.random.default_rng(seed)
            out[i] = rng.standard_normal(self.dimension, dtype=np.float32)
        return _l2_normalise(out)

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            model_name=self.model_name,
            model_version=self.model_version,
            dimension=self.dimension,
            is_fallback=True,
            detail=(
                "Seeded-hash fallback. Vectors are stable but carry no semantic "
                "signal - retrieval recall is not meaningful on this provider."
            ),
        )


class Qwen3EmbeddingProvider:
    """Qwen/Qwen3-Embedding-0.6B, loaded ONCE at startup. Never per request."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.model_name = model_name or settings.embedding_model
        self.model_version = settings.embedding_version
        self._torch = torch
        self._device = device or settings.embedding_device
        self._batch_size = batch_size or settings.embedding_batch_size

        # torch oversubscribes cores by default and batch throughput collapses.
        torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, padding_side="left")
        self._model = AutoModel.from_pretrained(self.model_name).to(self._device).eval()
        self.dimension = int(self._model.config.hidden_size)

        if self.dimension != settings.embedding_dimension:
            # Never silently truncate or pad: that produces plausible, wrong
            # neighbours (docs/05 §8).
            raise RuntimeError(
                f"{self.model_name} is {self.dimension}-d but EMBEDDING_DIMENSION "
                f"is {settings.embedding_dimension}. Fix the config and reindex."
            )

    def _pool(self, hidden, mask):
        """Last-token pooling, which is what Qwen3-Embedding is trained for."""
        left_padded = mask[:, -1].sum() == mask.shape[0]
        if left_padded:
            return hidden[:, -1]
        lengths = mask.sum(dim=1) - 1
        return hidden[self._torch.arange(hidden.shape[0]), lengths]

    def embed(
        self, texts: Sequence[str], *, kind: EmbedKind = "document"
    ) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        prefix = INSTRUCTIONS[kind]
        prepared = [prefix + t for t in texts]
        chunks: list[np.ndarray] = []

        with self._torch.inference_mode():
            for start in range(0, len(prepared), self._batch_size):
                batch = prepared[start : start + self._batch_size]
                encoded = self._tokenizer(
                    batch, padding=True, truncation=True,
                    max_length=512, return_tensors="pt",
                ).to(self._device)
                output = self._model(**encoded)
                pooled = self._pool(output.last_hidden_state, encoded["attention_mask"])
                chunks.append(pooled.float().cpu().numpy())

        return _l2_normalise(np.vstack(chunks))

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            model_name=self.model_name,
            model_version=self.model_version,
            dimension=self.dimension,
            is_fallback=False,
            detail=f"Loaded on {self._device}, batch {self._batch_size}.",
        )


_provider: EmbeddingProvider | None = None


def get_provider(*, refresh: bool = False) -> EmbeddingProvider:
    """Process-wide singleton. Falls back loudly, never silently."""
    global _provider
    if _provider is not None and not refresh:
        return _provider

    if settings.embedding_provider == "qwen3":
        try:
            _provider = Qwen3EmbeddingProvider()
        except ImportError as exc:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=qwen3 needs torch and transformers: "
                "pip install -r requirements-ml.txt"
            ) from exc
    else:
        _provider = DeterministicProvider()
    return _provider
