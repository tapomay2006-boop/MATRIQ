"""The Siamese reranker's lifecycle: load once, report honestly, score pairs.

The model is loaded on first use, not at startup, exactly like the LoRA
adapter and the Qwen3 provider: the service boots in a second, and a machine
without torch or without a trained checkpoint fails nothing at boot - it
answers searches without the reranking stage and *says so* in every response
and in GET /search/model/info.

Unavailability is a state, not an exception. `get_reranker()` returns None
and `status()` carries the reason; the search service reads both. A failed
load is remembered so a missing checkpoint costs one attempt, not one per
request - `refresh=True` retries.

The text a candidate is scored on lives here too (`candidate_text`), because
training and inference must agree on it and this is the one module both import.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.config import settings
from app.logic.query import preprocess
from app.logic.standardize import StandardMaterial

logger = logging.getLogger(__name__)

__all__ = [
    "Reranker",
    "RerankerStatus",
    "candidate_text",
    "get_reranker",
    "set_reranker",
    "status",
]


def candidate_text(material: StandardMaterial) -> str:
    """What the reranker sees for a stored material.

    The same five identity attributes the retrieval vector is built from
    (`StandardMaterial.identity_attributes`), flattened to one line without
    their labels: a query is one line without labels, and the pair should
    differ in content, not in format. Description first, so a truncated long
    row loses its specifications tail rather than its name.

    The description goes through the query preprocessor - the same
    abbreviation table, the same noise strip. Phase 1 already applies it
    before a row is stored, so for those rows this is a no-op; for a row that
    arrived through POST /standardized/check directly it is what keeps both
    sides of the pair in one vocabulary. Training uses this same function,
    so what the model learned on is what it is asked about.
    """
    attributes = dict(material.identity_attributes)
    if "Item Description (Raw)" in attributes:
        attributes["Item Description (Raw)"] = preprocess(attributes["Item Description (Raw)"])
    return " | ".join(attributes.values())


class Reranker(Protocol):
    name: str

    def score_pairs(self, query: str, candidates: Sequence[str]) -> np.ndarray:
        """One score in [0, 1] per candidate, from ONE batched pass."""


@dataclass(frozen=True)
class RerankerStatus:
    enabled: bool
    available: bool
    model_path: str
    model_name: str | None
    device: str
    detail: str
    pair_threshold: float | None = None
    parameters: int | None = None
    metrics: dict | None = None
    backbone: str | None = None
    format_version: str | None = None
    projection_dim: int | None = None

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "model_path": self.model_path,
            "model_name": self.model_name,
            "backbone": self.backbone,
            "format_version": self.format_version,
            "projection_dim": self.projection_dim,
            "device": self.device,
            "detail": self.detail,
            "pair_threshold": self.pair_threshold,
            "parameters": self.parameters,
            "metrics": self.metrics,
        }


class SiameseReranker:
    """Adapts a loaded `SiameseModel` to the `Reranker` protocol."""

    def __init__(self, model, *, path: str) -> None:
        self._model = model
        self.path = path
        self.name = f"{model.config.backbone} + projection ({model.config.format_version})"

    def score_pairs(self, query: str, candidates: Sequence[str]) -> np.ndarray:
        return self._model.pair_scores(query, list(candidates))

    def status(self) -> RerankerStatus:
        config = self._model.config
        return RerankerStatus(
            enabled=True, available=True, model_path=self.path, model_name=self.name,
            device=str(self._model.device), detail="Loaded.",
            pair_threshold=config.pair_threshold, parameters=self._model.parameter_count,
            metrics=config.metrics or None, backbone=config.backbone,
            format_version=config.format_version, projection_dim=config.projection_dim,
        )


_reranker: Reranker | None = None
_attempted = False
_failure: str | None = None
_override: Reranker | None = None


def set_reranker(reranker: Reranker | None) -> None:
    """Install a reranker directly. For tests and for a caller that built one.

    `None` clears the override and the cached load, so the next `get_reranker`
    tries the configured checkpoint again.
    """
    global _override, _reranker, _attempted, _failure
    _override = reranker
    _reranker, _attempted, _failure = None, False, None


def get_reranker(*, refresh: bool = False) -> Reranker | None:
    """The reranker, or None with the reason recorded in `status()`."""
    global _reranker, _attempted, _failure
    if _override is not None:
        return _override
    if not settings.search_reranker_enabled:
        return None
    if _attempted and not refresh:
        return _reranker

    _attempted, _reranker, _failure = True, None, None
    path = Path(settings.siamese_model_path)
    if not (path / "config.json").exists():
        _failure = (
            f"No trained Siamese checkpoint at {path} - run "
            f"scripts/train_siamese.py, or set SIAMESE_MODEL_PATH."
        )
        logger.warning("Siamese reranker unavailable: %s", _failure)
        return None

    try:
        from app.logic.siamese import SiameseModel

        model = SiameseModel.load(
            path, device=settings.siamese_device, batch_size=settings.siamese_batch_size,
        )
    except Exception as exc:  # noqa: BLE001 - recorded and reported, never raised
        _failure = f"Could not load the Siamese checkpoint at {path}: {exc}"
        logger.warning("Siamese reranker unavailable: %s", _failure)
        return None

    _reranker = SiameseReranker(model, path=str(path))
    logger.info("Siamese reranker loaded from %s on %s", path, model.device)
    return _reranker


def status() -> RerankerStatus:
    """What GET /search/model/info reports. Triggers the load if not yet tried."""
    reranker = get_reranker()
    if isinstance(reranker, SiameseReranker):
        return reranker.status()
    if reranker is not None:
        return RerankerStatus(
            enabled=True, available=True, model_path="", model_name=reranker.name,
            device="", detail="Installed directly.",
        )
    if not settings.search_reranker_enabled:
        detail = "SEARCH_RERANKER_ENABLED=false. Results are ordered by the Qdrant score alone."
    else:
        detail = _failure or "Not loaded."
    return RerankerStatus(
        enabled=settings.search_reranker_enabled, available=False,
        model_path=settings.siamese_model_path, model_name=None,
        device=settings.siamese_device, detail=detail,
    )
