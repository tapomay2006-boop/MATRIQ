"""Final ranking and the match decision. Pure: no model, no store, no HTTP.

Two scores reach this module for every candidate, and neither is trusted alone:

  qdrant_score    cosine between the Qwen3 *retrieval* vectors. Good at
                  finding the neighbourhood, poor at telling `C-120` from
                  `C-125` inside it - both are "a V belt" to a general
                  embedding, and in practice everything in one material family
                  scores in a narrow band near the top.
  siamese_score   cosine between the *reranker's* projections of the query
                  and the candidate, trained on labelled CPSE pairs to pull
                  the same article together and push different articles apart.
                  Absent when the reranker is not loaded.

`final_score` is a weighted sum, `alpha * qdrant + beta * siamese`, with the
weights configurable and `alpha + beta = 1`. The two are on the same scale
(both cosines) but are not calibrated against each other, which is why the
weights exist and why the shipped default leans on the Siamese score:
`scripts/evaluate_search.py` measures both orderings on the evaluation set
and the README records what it found. A candidate with no Siamese score
ranks on its Qdrant score alone and says so.

The match decision is three-way, not a boolean, because "probably" is a real
answer a reviewer needs to see:

  high        at or above `match_threshold`  - safe to treat as the same article
  possible    at or above `possible_threshold` - show it, let a human decide
  none        below both

Without the reranker a result can never be `high`. A general-purpose
embedding has not earned that claim on this domain, and a demo running without
the trained stage must not look like one running with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "BY_IDENTIFIER",
    "BY_VECTOR",
    "MatchLevel",
    "MatchSource",
    "RankedCandidate",
    "ScoringPolicy",
    "fuse",
    "rank",
]


class MatchLevel(StrEnum):
    HIGH = "high"
    POSSIBLE = "possible"
    NONE = "none"


class MatchSource(StrEnum):
    """What DECIDED the level. Kept apart from the scores so that an exact
    code hit sitting next to a low Siamese score reads as what it is: a rule
    fired, not a model that was confident."""

    EXACT_IDENTIFIER = "exact_identifier"
    SIAMESE = "siamese"
    RETRIEVAL_ONLY = "retrieval_only"
    NONE = "none"


#: How a candidate entered the pool. Display strings; a candidate may carry both.
BY_IDENTIFIER = "identifier"
BY_VECTOR = "vector"


@dataclass(frozen=True)
class ScoringPolicy:
    qdrant_weight: float
    siamese_weight: float
    match_threshold: float
    possible_threshold: float
    reranker_applied: bool

    def __post_init__(self) -> None:
        if not (0.0 <= self.qdrant_weight <= 1.0 and 0.0 <= self.siamese_weight <= 1.0):
            raise ValueError("Score weights must be in [0, 1].")
        if abs(self.qdrant_weight + self.siamese_weight - 1.0) > 1e-6:
            raise ValueError(
                f"QDRANT_WEIGHT + SIAMESE_WEIGHT must be 1, got "
                f"{self.qdrant_weight} + {self.siamese_weight}."
            )
        if self.possible_threshold > self.match_threshold:
            raise ValueError("possible_threshold cannot exceed match_threshold.")


@dataclass
class RankedCandidate:
    material_id: str
    qdrant_score: float | None = None
    siamese_score: float | None = None
    matched_by: list[str] = field(default_factory=list)
    identifier_field: str | None = None
    """Which stored field an identifier token matched, when one did."""
    identifier_token: str | None = None
    final_score: float = 0.0
    level: MatchLevel = MatchLevel.NONE
    source: MatchSource = MatchSource.NONE

    @property
    def identifier_hit(self) -> bool:
        return BY_IDENTIFIER in self.matched_by


def fuse(
    qdrant_score: float | None, siamese_score: float | None, policy: ScoringPolicy
) -> float:
    """One number to sort by.

    Both inputs are cosines; the Siamese one is clipped at zero because a
    negative projection similarity means "different", and letting it drag the
    sum below the Qdrant floor would only reorder the tail. A candidate that
    reached the pool by identifier alone may have no Qdrant score at all
    (`identifier_only` queries skip the vector stage); it then ranks on what it
    has.
    """
    q = None if qdrant_score is None else max(0.0, min(1.0, float(qdrant_score)))
    s = None if siamese_score is None else max(0.0, min(1.0, float(siamese_score)))
    if q is None and s is None:
        return 0.0
    if s is None:
        return q  # type: ignore[return-value]
    if q is None:
        return s
    return policy.qdrant_weight * q + policy.siamese_weight * s


def _classify(
    candidate: RankedCandidate, policy: ScoringPolicy
) -> tuple[MatchLevel, MatchSource]:
    if candidate.identifier_hit:
        # An exact code match is a RULE, not a similarity: the strongest signal
        # the service has, and model-independent. HIGH whatever the scores
        # say - and the source says so, so a low Siamese score beside it is
        # read correctly.
        return MatchLevel.HIGH, MatchSource.EXACT_IDENTIFIER
    score = candidate.final_score
    if score >= policy.match_threshold:
        if policy.reranker_applied:
            return MatchLevel.HIGH, MatchSource.SIAMESE
        return MatchLevel.POSSIBLE, MatchSource.RETRIEVAL_ONLY
    if score >= policy.possible_threshold:
        source = MatchSource.SIAMESE if policy.reranker_applied else MatchSource.RETRIEVAL_ONLY
        return MatchLevel.POSSIBLE, source
    return MatchLevel.NONE, MatchSource.NONE


def rank(candidates: list[RankedCandidate], policy: ScoringPolicy) -> list[RankedCandidate]:
    """Score, classify and order.

    Identifier hits first, then by final score, then - so that a pure-Siamese
    configuration still has a deterministic order among equal pair scores -
    by the retrieval score.
    """
    for candidate in candidates:
        candidate.final_score = round(
            fuse(candidate.qdrant_score, candidate.siamese_score, policy), 4
        )
        candidate.level, candidate.source = _classify(candidate, policy)
    return sorted(
        candidates,
        key=lambda c: (
            c.identifier_hit, c.final_score, c.qdrant_score or 0.0, c.material_id,
        ),
        reverse=True,
    )
