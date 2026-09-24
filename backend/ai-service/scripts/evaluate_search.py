#!/usr/bin/env python
"""Measure Qdrant-only against Qdrant + Siamese on real queries.

    EMBEDDING_PROVIDER=qwen3 .venv/bin/python scripts/evaluate_search.py \\
        --corpus ../pipeline-one/CPSE_SIH26099.csv \\
        --queries data/evaluation/search_queries.csv \\
        --model data/models/siamese-cpse-v1 \\
        --report data/evaluation/report.json

The corpus is embedded with the configured provider into the exact in-memory
store, every query is run through the same top-K pool three ways (retrieval
score, fused score, Siamese score), and the hit rate, MRR, precision and the
match-decision P/R/F1 are printed for each - split into all queries and the
queries whose target articles the model never saw in training, when the
checkpoint recorded which those were.

`--calibrate` prints the fused-score threshold that maximises match F1, which
is what SEARCH_MATCH_THRESHOLD should be set from. Nothing is written except
the report.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.logic.embedding import get_provider  # noqa: E402
from app.logic.ranking import ScoringPolicy  # noqa: E402
from app.training.evaluate import build_index, evaluate, load_queries, render, save  # noqa: E402
from app.training.pairs import load_corpus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--queries", default="data/evaluation/search_queries.csv")
    parser.add_argument("--model", default=settings.siamese_model_path)
    parser.add_argument(
        "--no-reranker", action="store_true", help="Qdrant-only, even if a checkpoint exists"
    )
    parser.add_argument("--top-k", type=int, default=settings.search_top_k)
    parser.add_argument("--final-k", type=int, default=settings.search_final_k)
    parser.add_argument("--qdrant-weight", type=float, default=settings.search_qdrant_weight)
    parser.add_argument("--siamese-weight", type=float, default=settings.search_siamese_weight)
    parser.add_argument("--match-threshold", type=float, default=settings.search_match_threshold)
    parser.add_argument(
        "--possible-threshold", type=float, default=settings.search_possible_threshold
    )
    parser.add_argument("--device", default=settings.siamese_device)
    parser.add_argument("--report", default="data/evaluation/report.json")
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s | %(message)s"
    )
    log = logging.getLogger("evaluate_search")

    materials = load_corpus(args.corpus)
    queries = load_queries(args.queries)
    provider = get_provider()
    log.info("embedding %d materials with %s", len(materials), provider.info().model_name)
    store = build_index(materials, provider)

    reranker = None
    held_out: list[str] = []
    if not args.no_reranker:
        settings.siamese_model_path = args.model
        settings.siamese_device = args.device
        from app.services import reranker as reranker_service

        reranker = reranker_service.get_reranker(refresh=True)
        if reranker is None:
            log.warning("no reranker: %s", reranker_service.status().detail)
        held_file = Path(args.model) / "held_out_groups.json"
        if held_file.exists():
            held_out = json.loads(held_file.read_text(encoding="utf-8"))

    policy = ScoringPolicy(
        qdrant_weight=args.qdrant_weight,
        siamese_weight=args.siamese_weight,
        match_threshold=args.match_threshold,
        possible_threshold=args.possible_threshold,
        reranker_applied=reranker is not None,
    )
    report = evaluate(
        materials,
        queries,
        provider=provider,
        store=store,
        reranker=reranker,
        policy=policy,
        top_k=args.top_k,
        final_k=args.final_k,
        held_out_groups=held_out,
    )
    save(report, args.report)
    print(render(report))
    print(f"\nfull report: {args.report}")

    if args.calibrate:
        print("\ncalibration (threshold maximising match F1 over the whole pool):")
        for name, summary in report["all_queries"].items():
            c = summary["calibration"]
            print(
                f"  {name:22} threshold {c['best_threshold']:.3f}  P {c['precision']:.3f}  "
                f"R {c['recall']:.3f}  F1 {c['f1']:.3f}"
            )
        fused = report["all_queries"]["qdrant_plus_siamese"]["calibration"]["best_threshold"]
        print(
            f"\n  -> SEARCH_MATCH_THRESHOLD={fused:.2f} for weights "
            f"{args.qdrant_weight}/{args.siamese_weight}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
