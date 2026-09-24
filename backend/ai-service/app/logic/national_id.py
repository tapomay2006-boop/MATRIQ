"""The national material id: the one identifier the master owns.

    NMM-00000001
    NMM-00000002
    ...

Why it exists, and why `material_id` is not it
-----------------------------------------------
`material_id` is `{CPSE}-{legacy code}` - `NTPC-1001`, `CCL-116045321`. It is
built from each company's own material code, which is exactly the thing a
national register cannot rely on: every CPSE codes differently, a CPSE
re-coding its catalogue would give the same article a new id, and nothing about
`BHEL-868460` says it is the fourth bearing the nation has ever registered.

So every material is allocated a national id **by this service**, at the moment
it is admitted, before its vector is written. It is:

  * sequential   allocated from a database counter, so it is unique by
                 construction and reads in the order materials were admitted;
  * fixed-width  zero-padded to `NATIONAL_ID_DIGITS`, so ids sort as strings the
                 way they sort as numbers and a UI column never jitters;
  * immutable    assigned once, never derived from anything that can change.
                 The prefix is configuration, but an id already issued keeps
                 the form it was issued in;
  * opaque       deliberately NOT category-, CPSE- or year-coded. A category is
                 a keyword guess that can be wrong, and a wrong family baked
                 into a permanent identifier is a mistake nobody can fix.

It travels in the vector payload as well as on the row, so a neighbour that
search surfaces can be named nationally without a second lookup.

What it is not: part of the embedded text, part of `material_id`, or part of
any EXISTS / NEW verdict. It identifies; it does not decide.
"""

from __future__ import annotations

import re

from app.config import settings

__all__ = ["PATTERN", "format_national_id", "is_national_id", "parse_national_id"]


def format_national_id(sequence: int) -> str:
    """4 -> 'NMM-00000004'."""
    if sequence < 1:
        raise ValueError(f"A national id sequence starts at 1, got {sequence}.")
    return f"{settings.national_id_prefix}-{sequence:0{settings.national_id_digits}d}"


#: The shape of an id issued under the CURRENT configuration.
def PATTERN() -> re.Pattern[str]:  # noqa: N802 - reads as a constant at call sites
    return re.compile(
        rf"^{re.escape(settings.national_id_prefix)}-\d{{{settings.national_id_digits}}}$"
    )


def is_national_id(value: str) -> bool:
    """Was this string issued as a national id under the current settings?

    Strict on the configured prefix and width on purpose. `NTPC-1001` is a
    material id - a CPSE legacy code can be a bare run of digits - and a loose
    pattern would call it national. Lookups do not depend on this: `_find`
    checks both columns regardless, so an id issued under an earlier prefix is
    still found. This only decides which column to try first.
    """
    return bool(PATTERN().match(value or ""))


def parse_national_id(value: str) -> int | None:
    """'NMM-00000004' -> 4, or None if it is not one."""
    if not is_national_id(value):
        return None
    return int(value.rsplit("-", 1)[1])
