"""Score fusion and the three-way match decision, in isolation."""

from __future__ import annotations

import pytest

from app.logic.ranking import (
    BY_IDENTIFIER,
    BY_VECTOR,
    MatchLevel,
    RankedCandidate,
    ScoringPolicy,
    fuse,
    rank,
)


def policy(**overrides) -> ScoringPolicy:
    base = dict(
        qdrant_weight=0.3, siamese_weight=0.7, match_threshold=0.8,
        possible_threshold=0.55, reranker_applied=True,
    )
    base.update(overrides)
    return ScoringPolicy(**base)


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        policy(qdrant_weight=0.5, siamese_weight=0.7)


def test_possible_threshold_cannot_exceed_match_threshold():
    with pytest.raises(ValueError):
        policy(match_threshold=0.5, possible_threshold=0.6)


def test_fuse_is_the_configured_weighted_sum():
    assert fuse(0.9, 0.5, policy()) == pytest.approx(0.3 * 0.9 + 0.7 * 0.5)


def test_fuse_falls_back_to_whichever_score_exists():
    assert fuse(0.9, None, policy()) == pytest.approx(0.9)
    assert fuse(None, 0.6, policy()) == pytest.approx(0.6)
    assert fuse(None, None, policy()) == 0.0


def test_fuse_clips_a_negative_siamese_cosine_at_zero():
    assert fuse(0.5, -0.4, policy()) == pytest.approx(0.15)


def test_rank_orders_by_final_score_and_classifies():
    ranked = rank([
        RankedCandidate("low", qdrant_score=0.9, siamese_score=0.1, matched_by=[BY_VECTOR]),
        RankedCandidate("high", qdrant_score=0.9, siamese_score=0.95, matched_by=[BY_VECTOR]),
        RankedCandidate("mid", qdrant_score=0.9, siamese_score=0.5, matched_by=[BY_VECTOR]),
    ], policy())
    assert [c.material_id for c in ranked] == ["high", "mid", "low"]
    assert [c.level for c in ranked] == [MatchLevel.HIGH, MatchLevel.POSSIBLE, MatchLevel.NONE]


def test_without_the_reranker_nothing_is_high_confidence():
    """A general embedding has not earned the claim, and a demo without the
    trained stage must not look like one with it."""
    ranked = rank(
        [RankedCandidate("x", qdrant_score=0.99, matched_by=[BY_VECTOR])],
        policy(reranker_applied=False),
    )
    assert ranked[0].level is MatchLevel.POSSIBLE
    assert ranked[0].siamese_score is None


def test_an_identifier_hit_is_high_and_first_whatever_the_scores_say():
    ranked = rank([
        RankedCandidate("semantic", qdrant_score=0.95, siamese_score=0.95, matched_by=[BY_VECTOR]),
        RankedCandidate("exact", qdrant_score=None, siamese_score=0.2, matched_by=[BY_IDENTIFIER]),
    ], policy())
    assert ranked[0].material_id == "exact"
    assert ranked[0].level is MatchLevel.HIGH
    assert ranked[1].level is MatchLevel.HIGH
