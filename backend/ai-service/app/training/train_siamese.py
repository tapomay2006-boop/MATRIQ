"""Training the Siamese reranker.

    labelled pairs
        │
        ▼
    PairDataset ──► DataLoader (batches of (query, candidate, label))
        │
        ▼
    shared encoder ──► embedding A, embedding B     (ONE module, both sides)
        │
        ▼
    contrastive loss on ||A - B||
        │
        ▼
    backward ──► AdamW ──► updated weights
        │
        ▼
    validation each epoch: pair scores ──► best-F1 threshold ──► P / R / F1
        │                                  (overall F1, and how many number-
        │                                   perturbed twins fall below it)
        ▼
    checkpoint the best epoch, with its threshold and metrics in config.json

Never run by a request. `scripts/train_siamese.py` is the entry point; the
service only ever *loads* what this writes.

Two learning rates on purpose: the backbone is pretrained and moves gently,
the projection head is random and has to move. `freeze_backbone` trains the
head alone - a few seconds on a CPU, and a fair baseline to beat.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from app.logic.siamese import (
    ContrastiveLoss,
    SiameseConfig,
    SiameseModel,
    best_f1_threshold,
)
from app.training.pairs import Pair

logger = logging.getLogger(__name__)

__all__ = ["TrainingConfig", "TrainingResult", "random_split", "train"]


@dataclass
class TrainingConfig:
    output_dir: str
    backbone: str = "sentence-transformers/all-MiniLM-L6-v2"
    projection_dim: int = 256
    max_length: int = 96
    epochs: int = 4
    batch_size: int = 32
    learning_rate: float = 3e-5
    """Backbone learning rate. The head uses `head_lr_multiplier` times this."""
    head_lr_multiplier: float = 20.0
    weight_decay: float = 0.01
    margin: float = 1.0
    freeze_backbone: bool = False
    device: str = "auto"
    seed: int = 7
    eval_batch_size: int = 128

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrainingResult:
    output_dir: str
    best_epoch: int
    best_threshold: float
    best_metrics: dict[str, float]
    history: list[dict] = field(default_factory=list)
    train_pairs: int = 0
    validation_pairs: int = 0
    seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def random_split(
    pairs: Sequence[Pair], *, fraction: float, seed: int
) -> tuple[list[Pair], list[Pair]]:
    """A plain row-wise split, for pair files that carry no group. Pairs that
    DO carry one are split by group in `pairs.generate_pairs`; this is the
    fallback, and it is the weaker of the two because both sides of a
    validation pair may have been seen in training under another spelling."""
    rows = list(pairs)
    rng = random.Random(seed)
    rng.shuffle(rows)
    held = int(round(len(rows) * fraction))
    return rows[held:], rows[:held]


def _torch():
    import torch

    return torch


def _evaluate(
    model: SiameseModel, pairs: Sequence[Pair], *, batch_size: int
) -> tuple[np.ndarray, np.ndarray]:
    original = model.batch_size
    model.batch_size = batch_size
    try:
        scores = model.pairwise([p.query for p in pairs], [p.candidate for p in pairs])
    finally:
        model.batch_size = original
    labels = np.asarray([p.label for p in pairs], dtype=np.int64)
    return scores, labels


def train(
    train_pairs: Sequence[Pair],
    val_pairs: Sequence[Pair],
    config: TrainingConfig,
    *,
    extra_metadata: dict | None = None,
) -> TrainingResult:
    torch = _torch()
    from torch.utils.data import DataLoader, Dataset

    if not train_pairs:
        raise ValueError("No training pairs.")
    if not val_pairs:
        raise ValueError("No validation pairs; split some off before calling train().")

    torch.manual_seed(config.seed)
    random.seed(config.seed)
    np.random.seed(config.seed)

    class PairDataset(Dataset):
        def __init__(self, rows: Sequence[Pair]) -> None:
            self.rows = list(rows)

        def __len__(self) -> int:
            return len(self.rows)

        def __getitem__(self, index: int) -> tuple[str, str, float]:
            pair = self.rows[index]
            return pair.query, pair.candidate, float(pair.label)

    def collate(batch):
        queries, candidates, labels = zip(*batch, strict=True)
        return list(queries), list(candidates), torch.tensor(labels, dtype=torch.float32)

    loader = DataLoader(
        PairDataset(train_pairs), batch_size=config.batch_size, shuffle=True,
        collate_fn=collate, drop_last=False,
    )

    siamese_config = SiameseConfig(
        backbone=config.backbone, projection_dim=config.projection_dim,
        max_length=config.max_length,
    )
    model = SiameseModel(siamese_config, device=config.device, batch_size=config.eval_batch_size)
    module = model.module
    loss_fn = ContrastiveLoss(config.margin)

    head_lr = config.learning_rate * config.head_lr_multiplier
    if config.freeze_backbone:
        for parameter in module.backbone.parameters():
            parameter.requires_grad_(False)
        groups = [{"params": module.head.parameters(), "lr": head_lr}]
    else:
        groups = [
            {"params": module.backbone.parameters(), "lr": config.learning_rate},
            {"params": module.head.parameters(), "lr": head_lr},
        ]
    optimizer = torch.optim.AdamW(groups, weight_decay=config.weight_decay)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = TrainingResult(
        output_dir=str(output_dir), best_epoch=0, best_threshold=0.5,
        best_metrics={"f1": -1.0}, train_pairs=len(train_pairs), validation_pairs=len(val_pairs),
    )
    started = time.perf_counter()
    logger.info(
        "Training %s on %d pairs (%d val), %d epoch(s), batch %d, device %s, backbone %s",
        config.backbone, len(train_pairs), len(val_pairs), config.epochs, config.batch_size,
        model.device, "frozen" if config.freeze_backbone else "fine-tuned",
    )

    for epoch in range(1, config.epochs + 1):
        module.train()
        total, batches = 0.0, 0
        for queries, candidates, labels in loader:
            # Both sides through the SAME module. One tokenizer call each so
            # padding is per side, but the weights are identical by
            # construction - there is only one set.
            tq = {k: v.to(model.device) for k, v in module.tokenize(queries).items()}
            tc = {k: v.to(model.device) for k, v in module.tokenize(candidates).items()}
            a = module(tq["input_ids"], tq["attention_mask"])
            b = module(tc["input_ids"], tc["attention_mask"])
            loss = loss_fn(a, b, labels.to(model.device))
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(module.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item())
            batches += 1

        scores, labels_np = _evaluate(model, val_pairs, batch_size=config.eval_batch_size)
        threshold, metrics = best_f1_threshold(scores, labels_np)
        positives = scores[labels_np == 1]
        negatives = scores[labels_np == 0]

        # The whole validation set is mostly easy negatives - other articles -
        # and F1 over it barely moves between epochs. What a reranker is FOR
        # is the near-miss: the same description with one number changed. So
        # the perturbed twins get their own number - the fraction of them
        # scored BELOW the operating threshold - and the checkpoint is chosen
        # on the mean of overall F1 and that rejection rate.
        twins = np.asarray([p.relation == "DIFFERENT_NUMBER" for p in val_pairs], dtype=bool)
        if twins.any():
            hard_rejection = float((scores[twins] < threshold).mean())
        else:
            hard_rejection = metrics["f1"]
        metrics = {**metrics, "hard_rejection": round(hard_rejection, 4)}
        selection = round((metrics["f1"] + hard_rejection) / 2, 4)

        record = {
            "epoch": epoch,
            "train_loss": round(total / max(1, batches), 5),
            "val_threshold": round(threshold, 4),
            "val_mean_positive": round(float(positives.mean()), 4) if positives.size else None,
            "val_mean_negative": round(float(negatives.mean()), 4) if negatives.size else None,
            **{f"val_{k}": v for k, v in metrics.items()},
            "selection": selection,
        }
        result.history.append(record)
        logger.info("epoch %d: %s", epoch, json.dumps(record))

        if selection > result.best_metrics.get("selection", -1.0):
            metrics = {**metrics, "selection": selection}
            result.best_epoch = epoch
            result.best_threshold = threshold
            result.best_metrics = metrics
            model.config.pair_threshold = round(threshold, 4)
            model.config.metrics = {
                "epoch": epoch, **metrics,
                "mean_positive": record["val_mean_positive"],
                "mean_negative": record["val_mean_negative"],
            }
            model.config.trained_on = {
                "train_pairs": len(train_pairs),
                "validation_pairs": len(val_pairs),
                "training": config.to_dict(),
                **(extra_metadata or {}),
            }
            model.save(output_dir)
            logger.info(
                "Saved best checkpoint (epoch %d, F1 %.4f, twin rejection %.4f) to %s",
                epoch, metrics["f1"], hard_rejection, output_dir,
            )

    result.seconds = round(time.perf_counter() - started, 1)
    (output_dir / "training_result.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    return result
