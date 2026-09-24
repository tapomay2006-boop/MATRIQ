"""The rule that decides what enters the vector embedding DB.

Isolated from HTTP, the database and the store, because it is the one piece of
judgement in the service and everything else is plumbing around it.

The precedence order is the design, not an implementation detail: two exact
signals that are independent of the embedding model come first, then the batch,
then the one signal that can be wrong. A change to that order changes which
rows enter the master.
"""

from __future__ import annotations

from app.logic.existence import (
    BY_CANONICAL_HASH,
    BY_MATERIAL_ID,
    BY_VECTOR_SIMILARITY,
    ExistenceStatus,
    Neighbour,
    decide,
)


def verdict(**overrides):
    kwargs = {
        "row_number": 1,
        "material_id": "NTPC-1001",
        "canonical_hash": "abc",
        "description": "BALL BEARING 6205 2RS",
        "category": "BEARING",
        "canonical_text": "Item Description (Raw): BALL BEARING 6205 2RS",
        "known_ids": set(),
        "known_hashes": {},
        "batch_hashes": {},
        "neighbours": [],
        "threshold": 0.90,
    }
    kwargs.update(overrides)
    return decide(**kwargs)


def test_nothing_comparable_is_new():
    result = verdict()
    assert result.status is ExistenceStatus.NEW
    assert result.is_new
    assert result.matched_material_id is None
    assert "Nothing comparable" in result.reason


def test_a_known_material_id_wins_first():
    result = verdict(known_ids={"NTPC-1001"})
    assert result.status is ExistenceStatus.ALREADY_EXISTS
    assert result.matched_by == BY_MATERIAL_ID
    assert result.similarity == 1.0


def test_a_known_canonical_hash_is_caught_even_under_a_new_id():
    """Same article, different internal code: the row would produce a vector
    that already exists."""
    result = verdict(known_hashes={"abc": "BHEL-7"})
    assert result.status is ExistenceStatus.ALREADY_EXISTS
    assert result.matched_by == BY_CANONICAL_HASH
    assert result.matched_material_id == "BHEL-7"


def test_a_repeat_within_the_batch_points_at_the_first_row():
    result = verdict(row_number=5, batch_hashes={"abc": 2})
    assert result.status is ExistenceStatus.DUPLICATE_IN_BATCH
    assert result.duplicate_of_row == 2


def test_a_near_neighbour_at_the_threshold_counts_as_existing():
    result = verdict(neighbours=[Neighbour("NTPC-9", 0.90)])
    assert result.status is ExistenceStatus.ALREADY_EXISTS
    assert result.matched_by == BY_VECTOR_SIMILARITY
    assert result.similarity == 0.90


def test_just_below_the_threshold_is_new_and_says_what_it_nearly_matched():
    result = verdict(neighbours=[Neighbour("NTPC-9", 0.8999)])
    assert result.status is ExistenceStatus.NEW
    assert result.similarity == 0.8999
    assert "NTPC-9" in result.reason
    assert "below" in result.reason


def test_an_exact_signal_beats_a_weak_vector_score():
    """The id is exact and model-independent; a low cosine must not overturn it."""
    result = verdict(known_ids={"NTPC-1001"}, neighbours=[Neighbour("OTHER", 0.1)])
    assert result.matched_by == BY_MATERIAL_ID


def test_batch_duplication_is_judged_on_the_hash_not_the_id():
    """Two rows sharing a CPSE and a legacy code but describing different
    articles are a real condition of CPSE extracts. Calling the second a
    duplicate would silently discard a material; the identity scheme separates
    them with a content suffix instead."""
    result = verdict(batch_hashes={"a-different-hash": 2})
    assert result.status is ExistenceStatus.NEW


def test_the_neighbours_travel_with_the_verdict_as_evidence():
    hits = [Neighbour("A", 0.7), Neighbour("B", 0.6)]
    assert verdict(neighbours=hits).neighbours == hits
