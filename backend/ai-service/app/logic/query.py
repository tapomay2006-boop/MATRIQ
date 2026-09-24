"""What a search query is, before it is embedded or compared.

A query is whatever a user typed: a material code, a name, a name with
parameters, a sentence, or all of them at once. Nothing here forces it into a
schema. Two things are done to it, and only two:

1. **Preprocessing** - the same light normalisation Phase 1 applies to a stored
   description (upper-case, collapse whitespace, expand CPSE abbreviations), so
   that "brg ball 6205" and the indexed "BEARING BALL 6205" are compared in the
   same vocabulary. Technical tokens survive untouched: `120`, `1200 MM`, `M10`,
   `6205`, `DN50`, `C` are what identify a material and are never stripped.

2. **Identifier extraction** - tokens that look like a material code
   (`M-55321`, `224411`, `NTPC-M-55321`, `MAT4285270`, `NMM-00000042`) are
   pulled out so the service can try an exact lookup before, or instead of,
   treating them as natural language. A code is not a word; embedding it and
   hoping for a near neighbour is the wrong tool.

Pure functions. No model, no database, no HTTP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.logic.extraction import expand_abbreviations
from app.logic.identity import normalize_legacy_code

__all__ = [
    "PreparedQuery",
    "identifier_variants",
    "identifier_tokens",
    "is_identifier_like",
    "prepare",
    "preprocess",
]

_WHITESPACE = re.compile(r"\s+")

#: Trailing procurement noise that some catalogues append to a description and
#: a user might paste back in. Removed at the END only, so a term that happens
#: to contain one of these words mid-sentence is left alone.
_TRAILING_NOISE = re.compile(
    r"\s*(?:-\s*URGENT\s+REQ|\*\*OEM\s+ONLY\*\*|\(BOQ\d*\s+REF\)|REQ\s+AS\s+PER\s+ATTACHED\s+SPEC)\s*$",
    re.IGNORECASE,
)

#: A token that may be a material code: letters/digits/hyphens/slashes only,
#: at least one digit, and not a plain measurement. Split on whitespace and on
#: the punctuation that separates clauses, never on hyphens - `M-55321` is one
#: token.
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/_.]*[A-Za-z0-9]|[A-Za-z0-9]")

#: Units that make a digit-bearing token a measurement, not a code: `1200MM`,
#: `2KW`, `415V`, `1/2INCH`, `6X36`.
_UNIT_SUFFIX = re.compile(
    r"^\d+(?:[./]\d+)?(?:MM|CM|M|MTR|INCH|IN|FT|KG|KGS|G|LTR|L|W|KW|HP|V|KV|A|AMP|MA|"
    r"HZ|BAR|PSI|NB|OD|ID|X\d+|K|RPM|DEG|C|F|%)$",
    re.IGNORECASE,
)


def preprocess(query: str) -> str:
    """The text that is embedded and compared. Light on purpose.

    Upper-case, whitespace collapsed, trailing catalogue noise dropped, and the
    CPSE abbreviation table applied - the same table Phase 1 applies to every
    stored description, so both sides of a comparison speak the same words.
    Numbers, codes, dimensions and units are left exactly as typed.
    """
    text = _WHITESPACE.sub(" ", (query or "")).strip()
    text = _TRAILING_NOISE.sub("", text).strip()
    if not text:
        return ""
    text = expand_abbreviations(text.upper())
    return _WHITESPACE.sub(" ", text).strip()


def is_identifier_like(token: str) -> bool:
    """Could this token be a material, legacy, part or national code?

    Deliberately conservative. A code has a digit in it and is either long
    enough (5+ characters: `224411`, `MAT4285270`) or mixes letters, digits and
    a separator (`M-55321`, `PN-2409-B`). Short bare numbers like `6205`, `120`
    or `1200` are technical parameters and are NOT identifiers: looking them up
    would find a legacy code by coincidence and call an unrelated material an
    exact match. Measurements (`1200MM`, `415V`) are never identifiers either.
    """
    if not token or not any(ch.isdigit() for ch in token):
        return False
    if _UNIT_SUFFIX.match(token):
        return False
    compact = re.sub(r"[^A-Za-z0-9]", "", token)
    if len(compact) < 4:
        return False
    has_alpha = any(ch.isalpha() for ch in compact)
    has_separator = any(ch in "-/_." for ch in token)
    if has_alpha and has_separator:
        return True
    if has_alpha and len(compact) >= 5:
        return True
    return compact.isdigit() and len(compact) >= 5


def identifier_tokens(query: str) -> list[str]:
    """The identifier-like tokens of a query, upper-cased, in order, deduplicated."""
    seen: list[str] = []
    for match in _TOKEN.finditer(query or ""):
        token = match.group(0).strip(".")
        if is_identifier_like(token):
            upper = token.upper()
            if upper not in seen:
                seen.append(upper)
    return seen


def identifier_variants(token: str) -> list[str]:
    """Every spelling under which a stored row might carry this identifier.

    `M-55321` is stored as legacy code `M-55321`, as material id
    `NTPC-M55321` (logic/identity.py strips punctuation from the legacy part),
    and might be typed as `NTPC-M-55321`, `m55321` or `NTPC M-55321`. The
    variants cover: the token as typed, its punctuation-free form, and - when a
    CPSE-style prefix is present - the prefix joined to the normalised
    remainder, which is exactly how material ids are built.
    """
    upper = (token or "").strip().upper()
    if not upper:
        return []
    out: list[str] = [upper]
    normalised = normalize_legacy_code(upper)
    if normalised and normalised not in out:
        out.append(normalised)
    if "-" in upper:
        prefix, rest = upper.split("-", 1)
        rest_norm = normalize_legacy_code(rest)
        if prefix.isalpha() and rest_norm:
            joined = f"{prefix}-{rest_norm}"
            if joined not in out:
                out.append(joined)
    return out


@dataclass(frozen=True)
class PreparedQuery:
    raw: str
    text: str
    """The preprocessed text: what gets embedded and what the reranker sees."""

    identifiers: list[str] = field(default_factory=list)
    """Identifier-like tokens, for the exact-lookup stage."""

    @property
    def is_empty(self) -> bool:
        return not self.text

    @property
    def identifier_only(self) -> bool:
        """Nothing but identifiers, e.g. `M-55321` or `NTPC-M-55321 224411`.

        Such a query has no descriptive content to embed. If the exact lookup
        finds the rows, the vector stage has nothing to add; if it finds
        nothing, the vector stage still runs, because a code can legitimately
        live inside a stored description (`O-RING P/N 87654321`).
        """
        if not self.identifiers:
            return False
        remainder = self.text
        for token in self.identifiers:
            remainder = remainder.replace(token, " ")
        return not re.search(r"[A-Za-z]{2,}|\d", remainder)


def prepare(query: str) -> PreparedQuery:
    text = preprocess(query)
    return PreparedQuery(raw=query, text=text, identifiers=identifier_tokens(text))
