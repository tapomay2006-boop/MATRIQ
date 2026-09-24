#!/usr/bin/env python
"""Train the Siamese reranker on labelled CPSE material pairs.

    .venv/bin/python scripts/train_siamese.py \\
        --corpus ../pipeline-one/CPSE_SIH26099.csv \\
        --pairs data/training/seed_pairs.csv \\
        --output data/models/siamese-cpse-v1

Pairs come from two places, either or both:

  --pairs FILE     query_material,candidate_material,label  (repeatable)
  --corpus FILE    a standard-format CSV; pairs are generated from it, with a
                   fraction of ARTICLES held out for validation (--holdout)

The best epoch by validation F1 is saved to --output together with the
threshold it calibrated and what it measured. The service loads that
directory through SIAMESE_MODEL_PATH; nothing here touches the running
service, the master or the Qdrant index.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.training.pairs import (  # noqa: E402
    generate_pairs,
    load_corpus,
    load_pairs,
    write_pairs,
)
from app.training.train_siamese import TrainingConfig, random_split, train  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--pairs", action="append", default=[], help="labelled pair CSV (repeatable)"
    )
    parser.add_argument("--corpus", help="standard-format CSV to generate pairs from")
    parser.add_argument("--output", default=settings.siamese_model_path)
    parser.add_argument("--backbone", default=settings.siamese_base_model)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--margin", type=float, default=1.0)
    parser.add_argument("--projection-dim", type=int, default=256)
    parser.add_argument("--max-length", type=int, default=96)
    parser.add_argument(
        "--holdout",
        type=float,
        default=0.25,
        help="fraction of corpus ARTICLES kept for validation",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=0.2,
        help="row-wise split for --pairs files, which carry no article",
    )
    parser.add_argument("--positives-per-row", type=int, default=6)
    parser.add_argument("--negatives-per-row", type=int, default=7)
    parser.add_argument(
        "--freeze-backbone", action="store_true", help="train the projection head only"
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--export-pairs", help="also write every generated pair to this CSV")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s"
    )
    log = logging.getLogger("train_siamese")

    if not args.pairs and not args.corpus:
        parser.error("give --pairs and/or --corpus")

    train_pairs, val_pairs = [], []
    held_out: list[str] = []
    provenance: dict = {"pair_files": args.pairs, "corpus": args.corpus}

    for file in args.pairs:
        rows = load_pairs(file)
        tr, va = random_split(rows, fraction=args.val_fraction, seed=args.seed)
        log.info("%s: %d pairs -> %d train / %d val", file, len(rows), len(tr), len(va))
        train_pairs += tr
        val_pairs += va

    if args.corpus:
        materials = load_corpus(args.corpus)
        split = generate_pairs(
            materials,
            seed=args.seed,
            holdout_fraction=args.holdout,
            positives_per_row=args.positives_per_row,
            negatives_per_row=args.negatives_per_row,
        )
        held_out = split.held_out_groups
        log.info(
            "%s: %d materials, %d articles, %d held out -> %d train / %d val pairs",
            args.corpus,
            len(materials),
            split.groups,
            len(held_out),
            len(split.train),
            len(split.validation),
        )
        train_pairs += split.train
        val_pairs += split.validation
        provenance["corpus_articles"] = split.groups
        provenance["held_out_groups"] = held_out

    if args.export_pairs:
        count = write_pairs([*train_pairs, *val_pairs], args.export_pairs)
        log.info("wrote %d pairs to %s", count, args.export_pairs)

    if not val_pairs:
        train_pairs, val_pairs = random_split(
            train_pairs, fraction=args.val_fraction, seed=args.seed
        )

    config = TrainingConfig(
        output_dir=args.output,
        backbone=args.backbone,
        projection_dim=args.projection_dim,
        max_length=args.max_length,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        margin=args.margin,
        freeze_backbone=args.freeze_backbone,
        device=args.device,
        seed=args.seed,
    )
    result = train(train_pairs, val_pairs, config, extra_metadata=provenance)

    output = Path(args.output)
    (output / "held_out_groups.json").write_text(json.dumps(held_out, indent=2), encoding="utf-8")
    log.info(
        "done in %.0fs: best epoch %d, pair threshold %.4f, val %s -> %s",
        result.seconds,
        result.best_epoch,
        result.best_threshold,
        result.best_metrics,
        output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
