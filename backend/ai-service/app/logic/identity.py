"""Stable material identity.

    The old scheme was  f"{cpse}-{source_row:06d}"  ->  "CCL-000001"

Two failures, both invisible on a 404-row fixture and both fatal at scale:

1. **Row-position dependent.** Re-uploading the same file with rows in a
   different order gives the same physical materials *different* ids. Every
   stored review, mapping and match_result then points at nothing.
2. **Capped at 999,999 rows per CPSE**, silently colliding above that.

What replaces it. The natural key a CPSE already owns is its own material
code, so the id is:

    {CPSE}-{legacy code}                      CCL-116045321

That is stable across re-upload, order-independent, and readable. Two problems
have to be handled, and the fixture contains an example of the first:

  * **The legacy code is not always unique.** `CCL / 116045321` appears twice
    in the real extract, on two different bearings. Colliding keys get a
    deterministic suffix derived from the description, applied to *every*
    member of the group so the result does not depend on which row came first.

  * **The legacy code is sometimes absent** ("", "N/A"). Those fall back to a
    content hash, which is at least stable for an unchanged row.

The trade-off, stated plainly: for a colliding or code-less row, editing the
description changes its id. That is the price of having no unique key in the
source data, and it is confined to the rows that actually lack one.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING

from app.logic.versions import IDENTITY_SCHEME_VERSION as _IDENTITY_SCHEME_VERSION

if TYPE_CHECKING:  # pragma: no cover
    from app.logic.standardize import StandardMaterial

__all__ = [
    "IDENTITY_SCHEME_VERSION",
    "assign_material_ids",
    "content_fingerprint",
    "material_key",
    "normalize_legacy_code",
]

#: Re-exported from versions.py, which is the single source of every stamp.
#: It travels on every match_result via VersionStamp.identity_scheme.
IDENTITY_SCHEME_VERSION = _IDENTITY_SCHEME_VERSION

#: Placeholders CPSEs use to mean "no code". Treated as absent, not as a value.
_PLACEHOLDERS = {"", "-", "N/A", "NA", "NAN", "NONE", "NULL", "0", "TBD", "XXX"}

_NON_KEY = re.compile(r"[^A-Z0-9]+")

#: Keep ids inside the column width with room for a suffix.
_MAX_LEGACY = 28
_SUFFIX_LEN = 6


def normalize_legacy_code(raw: str | None) -> str | None:
    """Upper-case and strip punctuation. Returns None for a placeholder.

    `116045321`, `1160-45321` and `116045321 ` all normalise to the same key,
    because a CPSE re-exporting its master should not create a new material.
    """
    value = (raw or "").strip().upper()
    if value in _PLACEHOLDERS:
        return None
    cleaned = _NON_KEY.sub("", value)
    if not cleaned or cleaned in _PLACEHOLDERS:
        return None
    return cleaned[:_MAX_LEGACY]


def content_fingerprint(*parts: str | None) -> str:
    """A short, stable hash of the row's identifying text."""
    payload = "\x1f".join((p or "").strip().upper() for p in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:_SUFFIX_LEN]


def material_key(cpse_code: str, legacy_code: str | None, description: str) -> str:
    """The base id, before collisions are resolved.

    A row with a usable legacy code gets a readable key. A row without one gets
    an `X`-prefixed content hash, so it is still stable across re-upload as long
    as the row itself does not change.
    """
    legacy = normalize_legacy_code(legacy_code)
    if legacy is None:
        return f"{cpse_code}-X{content_fingerprint(description)}"
    return f"{cpse_code}-{legacy}"


def assign_material_ids(materials: Iterable[StandardMaterial]) -> dict[str, int]:
    """Give every material a unique, order-independent id, in place.

    Runs over a whole batch because uniqueness is a property of the batch, not
    of a single row. Returns a small report so a caller can surface how many keys
    had to be disambiguated - a CPSE with thousands of colliding codes has a
    data problem worth telling them about.
    """
    items = list(materials)
    groups: dict[str, list[StandardMaterial]] = defaultdict(list)
    for material in items:
        groups[material.material_id].append(material)

    collided_keys = 0
    collided_rows = 0

    for key, members in groups.items():
        if len(members) == 1:
            continue

        collided_keys += 1
        collided_rows += len(members)

        # Suffix EVERY member, not just the later ones, so the id of the first
        # row does not depend on whether a duplicate happened to exist.
        used: dict[str, int] = {}
        for material in members:
            suffix = content_fingerprint(material.description)
            candidate = f"{key}-{suffix}"

            # Genuinely identical rows (same code, same description) cannot be
            # told apart by content. Fall back to a stable ordinal.
            seen = used.get(candidate, 0)
            used[candidate] = seen + 1
            material.material_id = candidate if seen == 0 else f"{candidate}-{seen + 1}"

    return {
        "materials": len(items),
        "distinct_keys": len(groups),
        "collided_keys": collided_keys,
        "collided_rows": collided_rows,
    }
