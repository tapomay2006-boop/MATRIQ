"""Does the Siamese stage actually improve retrieval? Measure it.

Every query in the evaluation file names the article(s) it should find, as a
pattern over the corpus's group keys (training/pairs.py::group_key). The
corpus is embedded with the LIVE provider into the exact in-memory store -
the ground truth Qdrant approximates - and each query is run twice through
the same pool of top-K candidates:

    Qdrant-only          ordered by the retrieval cosine
    Qdrant + Siamese     the same K, reranked by the fused score

and once more by the Siamese score alone, so the weights can be judged. The
identifier stage is not part of this: it is exact lookup in Postgres, and
tests/test_search.py pins it.

Reported per ordering: hit rate at 1 / 5 / final_k (was a relevant article in
the top N), MRR (1 / rank of the first relevant one), precision at final_k,
and - for the match decision - precision / recall / F1 of "level == high"
against relevance over the whole pool. `calibrate` sweeps the fused score for
the threshold that maximises that F1, which is what SEARCH_MATCH_THRESHOLD
should be set from.

Two honesty guards. With EMBEDDING_PROVIDER=deterministic the numbers are
noise and the report says so at the top. With a `held_out_groups` list from
the training run, the queries whose targets the model never saw are reported
separately, so a good number cannot be memorisation.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings
from app.logic.embedding import EmbeddingProvider
from app.logic.query import prepare
from app.logic.ranking import BY_VECTOR, MatchLevel, RankedCandidate, ScoringPolicy, rank
from app.logic.retrieval import BlockingFilter, InMemoryVectorStore
from app.logic.siamese import best_f1_threshold
from app.logic.standardize import StandardMaterial
from app.services.indexing import build_points
from app.services.reranker import Reranker, candidate_text
from app.training.pairs import group_key

__all__ = ["EvalQuery", "build_index", "evaluate", "load_queries", "render"]


@dataclass(frozen=True)
class EvalQuery:
    query: str
    expected_pattern: str
    """A regex over group keys. Empty means: nothing in the corpus is relevant."""
    expect: str = "high"
    """The level a relevant row DESERVES for this query: `high` for a query
    that names one article, `possible` for one that names a family (`V BELT`)
    - where a high-confidence match would be over-claiming - and `none` when
    nothing is relevant. The ranking metrics use every query; the match
    P / R / F1 counts only queries that expect `high` or `none`, because a
    `possible` is the correct answer for the others, not a miss."""
    note: str = ""


def load_queries(path: str | Path) -> list[EvalQuery]:
    out: list[EvalQuery] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            query = (row.get("query") or "").strip()
            if not query:
                continue
            pattern = (row.get("expected_pattern") or "").strip()
            expect = (row.get("expect") or "").strip().lower() or ("high" if pattern else "none")
            if expect not in {"high", "possible", "none"}:
                raise ValueError(f"{path}: expect must be high|possible|none, got {expect!r}")
            out.append(EvalQuery(
                query=query, expected_pattern=pattern, expect=expect,
                note=(row.get("note") or "").strip(),
            ))
    return out


def build_index(
    materials: Sequence[StandardMaterial], provider: EmbeddingProvider
) -> InMemoryVectorStore:
    """The corpus, embedded exactly as POST /standardized/add would embed it."""
    store = InMemoryVectorStore()
    store.ensure_collection(dimension=provider.dimension)
    store.upsert(build_points(list(materials), provider))
    return store


def _relevant(materials: Sequence[StandardMaterial], pattern: str) -> set[str]:
    if not pattern:
        return set()
    regex = re.compile(pattern, re.IGNORECASE)
    return {m.material_id for m in materials if regex.search(group_key(m.description))}


@dataclass
class _Ordering:
    """Accumulates ranking metrics for one way of ordering the pool."""

    name: str
    hit_at_1: list[float] = field(default_factory=list)
    hit_at_5: list[float] = field(default_factory=list)
    hit_at_k: list[float] = field(default_factory=list)
    mrr: list[float] = field(default_factory=list)
    precision_at_k: list[float] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    labels: list[int] = field(default_factory=list)
    predicted_high: list[bool] = field(default_factory=list)
    false_positive_queries: list[str] = field(default_factory=list)

    def observe(
        self, ordered: Sequence[RankedCandidate], relevant: set[str], final_k: int, query: str,
        *, count_match: bool = True,
    ) -> None:
        ids = [c.material_id for c in ordered]
        ranks = [i for i, material_id in enumerate(ids, start=1) if material_id in relevant]
        first = ranks[0] if ranks else None
        if relevant:
            self.hit_at_1.append(1.0 if first == 1 else 0.0)
            self.hit_at_5.append(1.0 if first is not None and first <= 5 else 0.0)
            self.hit_at_k.append(1.0 if first is not None and first <= final_k else 0.0)
            self.mrr.append(1.0 / first if first else 0.0)
            top = ids[:final_k]
            self.precision_at_k.append(
                sum(1 for m in top if m in relevant) / len(top) if top else 0.0
            )
        if not count_match:
            return
        for candidate in ordered:
            self.scores.append(candidate.final_score)
            self.labels.append(1 if candidate.material_id in relevant else 0)
            self.predicted_high.append(candidate.level is MatchLevel.HIGH)
        if not relevant and any(c.level is MatchLevel.HIGH for c in ordered):
            self.false_positive_queries.append(query)

    def summary(self) -> dict[str, Any]:
        labels = np.asarray(self.labels, dtype=np.int64)
        predicted = np.asarray(self.predicted_high, dtype=bool)
        tp = int((predicted & (labels == 1)).sum())
        fp = int((predicted & (labels == 0)).sum())
        fn = int((~predicted & (labels == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        threshold, best = best_f1_threshold(np.asarray(self.scores), labels)
        return {
            "queries_with_relevant": len(self.mrr),
            "hit_at_1": _mean(self.hit_at_1),
            "hit_at_5": _mean(self.hit_at_5),
            "hit_at_final_k": _mean(self.hit_at_k),
            "mrr": _mean(self.mrr),
            "precision_at_final_k": _mean(self.precision_at_k),
            "match_precision": round(precision, 4),
            "match_recall": round(recall, 4),
            "match_f1": round(f1, 4),
            "match_true_positives": tp,
            "match_false_positives": fp,
            "match_false_negatives": fn,
            "false_positive_queries": self.false_positive_queries,
            "calibration": {"best_threshold": round(threshold, 4), **best},
        }


def _mean(values: Sequence[float]) -> float | None:
    return round(float(np.mean(values)), 4) if values else None


def evaluate(
    materials: Sequence[StandardMaterial],
    queries: Sequence[EvalQuery],
    *,
    provider: EmbeddingProvider,
    store: InMemoryVectorStore,
    reranker: Reranker | None,
    policy: ScoringPolicy,
    top_k: int,
    final_k: int,
    held_out_groups: Sequence[str] = (),
) -> dict[str, Any]:
    by_id = {m.material_id: m for m in materials}
    held = set(held_out_groups)
    info = provider.info()

    orderings = {
        "qdrant_only": _Ordering("qdrant_only"),
        "qdrant_plus_siamese": _Ordering("qdrant_plus_siamese"),
        "siamese_only": _Ordering("siamese_only"),
    }
    unseen = {name: _Ordering(name) for name in orderings}
    pool_recall: list[float] = []
    per_query: list[dict[str, Any]] = []

    qdrant_policy = ScoringPolicy(
        qdrant_weight=1.0, siamese_weight=0.0,
        match_threshold=policy.match_threshold, possible_threshold=policy.possible_threshold,
        reranker_applied=False,
    )
    siamese_policy = ScoringPolicy(
        qdrant_weight=0.0, siamese_weight=1.0,
        match_threshold=policy.match_threshold, possible_threshold=policy.possible_threshold,
        reranker_applied=reranker is not None,
    )

    for item in queries:
        prepared = prepare(item.query)
        relevant = _relevant(materials, item.expected_pattern)
        relevant_groups = {group_key(by_id[m].description) for m in relevant}
        is_unseen = bool(relevant_groups) and relevant_groups <= held

        vector = provider.embed([prepared.text], kind="query")[0]
        retrieved = store.search(
            vector, top_k=top_k, block=BlockingFilter(embedding_version=settings.embedding_version),
        )
        if relevant:
            pool_recall.append(
                sum(1 for c in retrieved if c.material_id in relevant) / len(relevant)
            )

        def fresh(hits=retrieved) -> list[RankedCandidate]:
            return [
                RankedCandidate(
                    material_id=c.material_id, qdrant_score=c.embedding_score,
                    matched_by=[BY_VECTOR],
                )
                for c in hits
            ]

        siamese_scores: np.ndarray | None = None
        if reranker is not None and retrieved:
            texts = [candidate_text(by_id[c.material_id]) for c in retrieved]
            siamese_scores = reranker.score_pairs(prepared.text, texts)

        results: dict[str, list[RankedCandidate]] = {}
        results["qdrant_only"] = rank(fresh(), qdrant_policy)
        for name, pol in (("qdrant_plus_siamese", policy), ("siamese_only", siamese_policy)):
            candidates = fresh()
            if siamese_scores is not None:
                for candidate, score in zip(candidates, siamese_scores, strict=True):
                    candidate.siamese_score = float(score)
            results[name] = rank(candidates, pol)

        count_match = item.expect != "possible"
        for name, ordered in results.items():
            orderings[name].observe(ordered, relevant, final_k, item.query, count_match=count_match)
            if is_unseen:
                unseen[name].observe(
                    ordered, relevant, final_k, item.query, count_match=count_match
                )

        def top(ordered: list[RankedCandidate], wanted=relevant) -> list[dict[str, Any]]:
            return [
                {
                    "material_id": c.material_id,
                    "description": by_id[c.material_id].description[:60],
                    "relevant": c.material_id in wanted,
                    "qdrant": None if c.qdrant_score is None else round(c.qdrant_score, 3),
                    "siamese": None if c.siamese_score is None else round(c.siamese_score, 3),
                    "final": c.final_score,
                    "level": str(c.level),
                }
                for c in ordered[:3]
            ]

        per_query.append({
            "query": item.query,
            "expect": item.expect,
            "note": item.note,
            "relevant": len(relevant),
            "unseen_in_training": is_unseen,
            "in_pool": sum(1 for c in retrieved if c.material_id in relevant),
            "qdrant_only": top(results["qdrant_only"]),
            "qdrant_plus_siamese": top(results["qdrant_plus_siamese"]),
        })

    return {
        "embedding": {
            "model": info.model_name, "is_fallback": info.is_fallback, "detail": info.detail,
        },
        "reranker_applied": reranker is not None,
        "reranker": getattr(reranker, "name", None),
        "corpus": {"materials": len(materials), "held_out_groups": len(held)},
        "queries": len(queries),
        "queries_expecting_possible": sum(1 for q in queries if q.expect == "possible"),
        "top_k": top_k,
        "final_k": final_k,
        "weights": {"qdrant": policy.qdrant_weight, "siamese": policy.siamese_weight},
        "thresholds": {"match": policy.match_threshold, "possible": policy.possible_threshold},
        "pool_recall_at_top_k": _mean(pool_recall),
        "all_queries": {name: o.summary() for name, o in orderings.items()},
        "unseen_article_queries": {name: o.summary() for name, o in unseen.items()},
        "per_query": per_query,
    }


def render(report: dict[str, Any]) -> str:
    """A short, readable table. The JSON has everything else."""
    lines: list[str] = []
    embedding = report["embedding"]
    if embedding["is_fallback"]:
        lines.append(
            "!! EMBEDDING_PROVIDER is the seeded-hash fallback: retrieval numbers below "
            "are NOISE. Set EMBEDDING_PROVIDER=qwen3 for a real measurement."
        )
    if not report["reranker_applied"]:
        lines.append("!! No reranker loaded: the Siamese columns equal Qdrant-only.")
    lines.append(
        f"corpus {report['corpus']['materials']} materials, {report['queries']} queries, "
        f"top_k {report['top_k']}, final_k {report['final_k']}, "
        f"weights qdrant {report['weights']['qdrant']} / siamese {report['weights']['siamese']}, "
        f"pool recall@top_k {report['pool_recall_at_top_k']}"
    )
    columns = ("hit_at_1", "hit_at_5", "mrr", "precision_at_final_k",
               "match_precision", "match_recall", "match_f1")
    for section in ("all_queries", "unseen_article_queries"):
        block = report[section]
        count = next(iter(block.values()))["queries_with_relevant"]
        lines.append("")
        lines.append(f"[{section}] ({count} queries with a relevant article)")
        lines.append(f"{'ordering':22}" + "".join(f"{c:>16}" for c in columns) + f"{'cal.thr':>10}")
        for name, summary in block.items():
            row = f"{name:22}"
            for column in columns:
                value = summary[column]
                row += f"{'-' if value is None else value:>16}"
            row += f"{summary['calibration']['best_threshold']:>10}"
            lines.append(row)
        fps = block["qdrant_plus_siamese"]["false_positive_queries"]
        if fps:
            lines.append(f"  high-confidence matches on queries with NO relevant article: {fps}")
    return "\n".join(lines)


def save(report: dict[str, Any], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2), encoding="utf-8")
