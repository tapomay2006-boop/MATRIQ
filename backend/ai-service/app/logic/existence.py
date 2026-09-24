"""Does this standardized row already exist in the vector embedding DB?

The one question `POST /standardized/check` answers, isolated from HTTP, from
the database and from the store so it can be reasoned about and tested on its
own.

Three signals, strongest first. The order is the whole design:

1. **Same material id.** `material_id` is `{CPSE}-{legacy code}` (logic/
   identity.py), so a CPSE re-uploading its own catalogue collides here on the
   first row. Exact, free, and independent of the embedding model.

2. **Same canonical hash.** Different legacy code, identical embedded text -
   the same article entered twice under two internal codes. Also exact, and
   also independent of the model, because the hash is taken over the text the
   model is *given*, not over what it returns.

3. **A near neighbour in the vector DB above `existence_threshold`.** This is
   the semantic case: the same article described in different words. It is the
   only signal that can be wrong, so it carries its score and its neighbour's
   id into the response and a human can see exactly why a row was held back.

A row that survives all three is NEW.

Note what this is NOT. It is not the matcher. The matcher decides a
*relationship* between two materials for a reviewer (EXACT_DUPLICATE,
NEAR_DUPLICATE, ...) using typed attribute comparison, hard rules and
calibration. This decides one thing only: whether a row is worth embedding.
Keeping them apart is why `existence_threshold` is its own setting and why
nothing in this module imports the matcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = ["ExistenceStatus", "RowVerdict", "decide"]


class ExistenceStatus(StrEnum):
    NEW = "NEW"
    """Not in the vector embedding DB. This is the material to add."""

    ALREADY_EXISTS = "ALREADY_EXISTS"
    """Present already, by id, by canonical hash, or by vector similarity."""

    DUPLICATE_IN_BATCH = "DUPLICATE_IN_BATCH"
    """New to the DB, but an earlier row of THIS payload is the same article.
    Held back so one request cannot insert the same material twice."""

    INVALID = "INVALID"
    """Not a usable standard-format row. Never silently dropped."""


#: Why a row was judged to exist. Display strings - never parsed by a caller.
BY_MATERIAL_ID = "MATERIAL_ID"
BY_CANONICAL_HASH = "CANONICAL_HASH"
BY_VECTOR_SIMILARITY = "VECTOR_SIMILARITY"


@dataclass(frozen=True)
class Neighbour:
    material_id: str
    score: float


@dataclass
class RowVerdict:
    row_number: int
    status: ExistenceStatus
    description: str = ""
    category: str = "UNCLASSIFIED"
    material_id: str | None = None
    """The id this row WOULD get. Present on every valid row, including the
    ones already in the index - that is how a caller finds the record it
    collided with."""

    canonical_text: str | None = None
    """Exactly what would be embedded for this row. Named for the hash it
    feeds, and returned so a NEW verdict can be checked by eye."""

    matched_material_id: str | None = None
    matched_by: str | None = None
    similarity: float | None = None
    duplicate_of_row: int | None = None
    reason: str = ""
    neighbours: list[Neighbour] = field(default_factory=list)
    error: str | None = None

    @property
    def is_new(self) -> bool:
        return self.status is ExistenceStatus.NEW


def decide(
    *,
    row_number: int,
    material_id: str,
    canonical_hash: str,
    description: str,
    category: str,
    canonical_text: str,
    known_ids: set[str],
    known_hashes: dict[str, str],
    batch_hashes: dict[str, int],
    neighbours: list[Neighbour],
    threshold: float,
) -> RowVerdict:
    """Judge one standardized row against the index and against its own batch.

    `known_ids` and `known_hashes` describe what the master already holds;
    `batch_hashes` maps the canonical hash of each earlier row of this same
    payload to its row number.

    In-batch duplication is judged on the canonical hash alone, never on the
    material id. Two rows sharing a CPSE and a legacy code but describing
    different articles are a known condition of real CPSE extracts - the
    identity scheme resolves them with a content suffix (logic/identity.py) -
    and calling the second one a duplicate would silently discard a material.
    """
    base = RowVerdict(
        row_number=row_number,
        status=ExistenceStatus.NEW,
        description=description,
        category=category,
        material_id=material_id,
        canonical_text=canonical_text,
        neighbours=neighbours,
    )

    # 1. Already indexed, by identity.
    if material_id in known_ids:
        base.status = ExistenceStatus.ALREADY_EXISTS
        base.matched_material_id = material_id
        base.matched_by = BY_MATERIAL_ID
        base.similarity = 1.0
        base.reason = (
            f"Material {material_id} is already in the master and the vector "
            f"embedding DB. Same CPSE, same legacy code."
        )
        return base

    # 2. Already indexed, by embedded text.
    twin = known_hashes.get(canonical_hash)
    if twin is not None:
        base.status = ExistenceStatus.ALREADY_EXISTS
        base.matched_material_id = twin
        base.matched_by = BY_CANONICAL_HASH
        base.similarity = 1.0
        base.reason = (
            f"Identical to {twin}: the text that gets embedded is byte-for-byte "
            f"the same, so this row would produce a duplicate vector."
        )
        return base

    # 3. The same article twice inside this one payload.
    first = batch_hashes.get(canonical_hash)
    if first is not None:
        base.status = ExistenceStatus.DUPLICATE_IN_BATCH
        base.duplicate_of_row = first
        base.similarity = 1.0
        base.reason = (
            f"Same article as row {first} of this request. Only the first copy "
            f"is treated as new material."
        )
        return base

    # 4. The semantic case: a near neighbour already in the vector DB.
    best = neighbours[0] if neighbours else None
    if best is not None and best.score >= threshold:
        base.status = ExistenceStatus.ALREADY_EXISTS
        base.matched_material_id = best.material_id
        base.matched_by = BY_VECTOR_SIMILARITY
        base.similarity = round(best.score, 4)
        base.reason = (
            f"Nearest vector is {best.material_id} at cosine "
            f"{best.score:.4f}, at or above the {threshold:.2f} existence "
            f"threshold."
        )
        return base

    if best is not None:
        base.similarity = round(best.score, 4)
        base.reason = (
            f"New material. Nearest existing vector is {best.material_id} at "
            f"cosine {best.score:.4f}, below the {threshold:.2f} threshold."
        )
    else:
        base.reason = "New material. Nothing comparable in the vector embedding DB."
    return base
