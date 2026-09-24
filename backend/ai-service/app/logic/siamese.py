"""The Siamese reranker: one shared encoder, a pair, a similarity.

                     Shared encoder
                    ┌──────────────┐
    Query ─────────►│  backbone    │──► embedding A ─┐
                    │  mean-pool   │                 ├─► cosine ─► score
    Candidate ─────►│  projection  │──► embedding B ─┘
                    │ SAME WEIGHTS │
                    └──────────────┘

This is NOT the retrieval model. Qwen3-Embedding-0.6B builds the Qdrant index
and finds the neighbourhood (logic/embedding.py); it is 0.6 B parameters, is
never fine-tuned here, and its vectors are never touched by anything in this
file. The reranker is a separate, small, pretrained text encoder - by default
`sentence-transformers/all-MiniLM-L6-v2`, 22 M parameters - with a trainable
projection head on top, fine-tuned on labelled CPSE material pairs to tell
`V BELT C 120` from `V BELT C 125`. Small on purpose: it runs over twenty
candidates per query, on a CPU if that is what there is.

Shared weights are structural, not a convention: `SiameseEncoder` is one
`nn.Module`, and `pair_scores` pushes queries and candidates through that one
module in a single batch. There is no second encoder to drift.

Everything torch is imported inside the classes, exactly as the Qwen3
provider does it, so the module is importable - and `services/reranker.py`
can report "not available" - on a machine without torch.

Checkpoint layout (a directory):

    config.json    backbone name, projection size, pooling, max length,
                   the calibrated pair threshold and the validation metrics
    backbone/      tokenizer + backbone weights, `save_pretrained`, so a
                   trained model loads with no network access
    head.pt        the projection head
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

__all__ = [
    "SIAMESE_FORMAT_VERSION",
    "ContrastiveLoss",
    "SiameseConfig",
    "SiameseEncoder",
    "SiameseModel",
    "best_f1_threshold",
    "cosine_to_score",
    "load_config",
]

SIAMESE_FORMAT_VERSION = "siamese-v1"


@dataclass
class SiameseConfig:
    backbone: str = "sentence-transformers/all-MiniLM-L6-v2"
    projection_dim: int = 256
    max_length: int = 96
    pooling: str = "mean"
    format_version: str = SIAMESE_FORMAT_VERSION

    #: The pair-score threshold the training run calibrated on its validation
    #: split (best F1), and what it measured there. Informational at inference
    #: - `SEARCH_MATCH_THRESHOLD` decides - but recorded so the number a
    #: deployment uses can be traced to the run that produced it.
    pair_threshold: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    trained_on: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def load_config(path: Path) -> SiameseConfig:
    data = json.loads((path / "config.json").read_text(encoding="utf-8"))
    known = {k: v for k, v in data.items() if k in SiameseConfig.__dataclass_fields__}
    return SiameseConfig(**known)


def cosine_to_score(cosine: np.ndarray) -> np.ndarray:
    """The reported Siamese score is the cosine itself, clipped to [0, 1].

    A negative cosine between projections means "different"; reporting it as
    zero keeps the number on the same scale as the Qdrant score and stops a
    weighted sum from going negative. Not a probability - calibrated
    thresholds, not the number's face value, decide a match.
    """
    return np.clip(cosine, 0.0, 1.0).astype(np.float32)


def _torch():
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - exercised on torch-free CI
        raise RuntimeError(
            "The Siamese reranker needs torch and transformers: "
            "pip install -r requirements-ml.txt"
        ) from exc
    return torch


class SiameseEncoder:
    """The shared encoder. Built lazily as a real `torch.nn.Module` subclass.

    Declared this way rather than as `class SiameseEncoder(nn.Module)` at
    import time so that importing this module does not import torch.
    `SiameseEncoder.build(...)` returns the module.
    """

    @staticmethod
    def build(config: SiameseConfig, *, backbone_path: str | Path | None = None):
        torch = _torch()
        from torch import nn
        from transformers import AutoModel, AutoTokenizer

        class _Encoder(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                source = str(backbone_path or config.backbone)
                self.tokenizer = AutoTokenizer.from_pretrained(source)
                self.backbone = AutoModel.from_pretrained(source)
                hidden = int(self.backbone.config.hidden_size)
                self.head = nn.Sequential(
                    nn.Linear(hidden, hidden),
                    nn.GELU(),
                    nn.Linear(hidden, config.projection_dim),
                )
                self.max_length = config.max_length

            def tokenize(self, texts: Sequence[str]):
                return self.tokenizer(
                    list(texts), padding=True, truncation=True,
                    max_length=self.max_length, return_tensors="pt",
                )

            def forward(self, input_ids, attention_mask):
                hidden = self.backbone(
                    input_ids=input_ids, attention_mask=attention_mask
                ).last_hidden_state
                # Mean pooling over real tokens - what MiniLM-family models
                # are trained for, and robust to the short, code-heavy strings
                # this domain is made of.
                mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-6)
                projected = self.head(pooled)
                return torch.nn.functional.normalize(projected, p=2, dim=-1)

        return _Encoder()


class ContrastiveLoss:
    """Hadsell et al. (2006), on the L2 distance between unit embeddings.

        y = 1:  d^2                    pull the pair together
        y = 0:  max(0, margin - d)^2   push it apart, but only until `margin`

    With unit vectors d^2 = 2 - 2 cos, so a margin of 1.0 says a non-matching
    pair is "far enough" once its cosine is at or below 0.5. That is what makes
    the pair score thresholdable rather than merely ordered.
    """

    def __init__(self, margin: float = 1.0) -> None:
        self.margin = float(margin)

    def __call__(self, a, b, labels):
        torch = _torch()
        distance = torch.norm(a - b, p=2, dim=-1)
        positive = labels * distance.pow(2)
        negative = (1.0 - labels) * torch.clamp(self.margin - distance, min=0.0).pow(2)
        return (positive + negative).mean()


class SiameseModel:
    """A trained (or about-to-be-trained) Siamese encoder with pair scoring.

    `encode` and `pair_scores` are inference; `module` exposes the encoder for
    the training loop. Both sides of every pair go through `module` - there is
    nothing else they could go through.
    """

    def __init__(
        self,
        config: SiameseConfig,
        *,
        device: str = "cpu",
        batch_size: int = 64,
        backbone_path: str | Path | None = None,
    ) -> None:
        torch = _torch()
        self.config = config
        self.batch_size = max(1, int(batch_size))
        self.device = torch.device(device if device != "auto" else (
            "cuda" if torch.cuda.is_available() else "cpu"
        ))
        self.module = SiameseEncoder.build(config, backbone_path=backbone_path).to(self.device)

    # --- inference -------------------------------------------------------

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """L2-normalised projections, shape (len(texts), projection_dim)."""
        torch = _torch()
        if not texts:
            return np.empty((0, self.config.projection_dim), dtype=np.float32)
        self.module.eval()
        chunks: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, len(texts), self.batch_size):
                batch = self.module.tokenize(texts[start : start + self.batch_size])
                batch = {k: v.to(self.device) for k, v in batch.items()}
                out = self.module(batch["input_ids"], batch["attention_mask"])
                chunks.append(out.float().cpu().numpy())
        return np.vstack(chunks)

    def pair_scores(self, query: str, candidates: Sequence[str]) -> np.ndarray:
        """One query against many candidates, in ONE batched pass.

        The query is encoded once alongside the candidates - `[query] +
        candidates` is a single input to the shared encoder - and the pair
        similarity is the cosine of the query row against every candidate row.
        Twenty candidates cost one forward, not twenty.
        """
        if not candidates:
            return np.empty((0,), dtype=np.float32)
        embeddings = self.encode([query, *candidates])
        cosine = embeddings[1:] @ embeddings[0]
        return cosine_to_score(cosine)

    def pairwise(self, left: Sequence[str], right: Sequence[str]) -> np.ndarray:
        """Score aligned pairs (left[i], right[i]). Used by evaluation."""
        if len(left) != len(right):
            raise ValueError("left and right must be the same length")
        if not left:
            return np.empty((0,), dtype=np.float32)
        a = self.encode(left)
        b = self.encode(right)
        return cosine_to_score(np.einsum("ij,ij->i", a, b))

    # --- persistence -----------------------------------------------------

    def save(self, path: str | Path) -> Path:
        torch = _torch()
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text(self.config.to_json(), encoding="utf-8")
        self.module.tokenizer.save_pretrained(target / "backbone")
        self.module.backbone.save_pretrained(target / "backbone")
        torch.save(self.module.head.state_dict(), target / "head.pt")
        return target

    @classmethod
    def load(
        cls, path: str | Path, *, device: str = "cpu", batch_size: int = 64
    ) -> SiameseModel:
        torch = _torch()
        source = Path(path)
        if not (source / "config.json").exists():
            raise FileNotFoundError(f"No Siamese checkpoint at {source} (config.json missing).")
        config = load_config(source)
        if config.format_version != SIAMESE_FORMAT_VERSION:
            raise RuntimeError(
                f"Checkpoint {source} is format {config.format_version!r}; this "
                f"service reads {SIAMESE_FORMAT_VERSION!r}. Retrain."
            )
        model = cls(
            config, device=device, batch_size=batch_size,
            backbone_path=source / "backbone",
        )
        state = torch.load(source / "head.pt", map_location=model.device)
        model.module.head.load_state_dict(state)
        model.module.eval()
        return model

    @property
    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.module.parameters())


def best_f1_threshold(scores: np.ndarray, labels: np.ndarray) -> tuple[float, dict[str, float]]:
    """The threshold that maximises F1 on labelled pair scores, and its metrics.

    Shared by the training loop (validation calibration) and the evaluation
    script. Sweeps the observed scores rather than a fixed grid, so the answer
    is exact for the data it was given.
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    if scores.size == 0:
        return 0.5, {"precision": 0.0, "recall": 0.0, "f1": 0.0, "accuracy": 0.0}

    best_threshold, best = 0.5, {"precision": 0.0, "recall": 0.0, "f1": -1.0, "accuracy": 0.0}
    positives = int(labels.sum())
    for threshold in np.unique(np.concatenate([scores, [0.0, 1.0]])):
        predicted = scores >= threshold
        tp = int((predicted & (labels == 1)).sum())
        fp = int((predicted & (labels == 0)).sum())
        fn = positives - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        accuracy = float((predicted == (labels == 1)).mean())
        if f1 > best["f1"] or (math.isclose(f1, best["f1"]) and threshold > best_threshold):
            best_threshold = float(threshold)
            best = {
                "precision": round(precision, 4), "recall": round(recall, 4),
                "f1": round(f1, 4), "accuracy": round(accuracy, 4),
            }
    return best_threshold, best
