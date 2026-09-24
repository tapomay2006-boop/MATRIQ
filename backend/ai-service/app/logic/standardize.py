"""The standard-format record, and the text that gets embedded from it.

There is no processing chain here any more. The chain that used to live in this
module -

    clean() -> classify() -> expand_abbreviations() -> extract() -> canonical

- did the same work as Phase 1, on text Phase 1 had already been through, and
is gone. Cleaning, abbreviation expansion and attribute extraction now happen
once, in `logic/extraction.py`, and what reaches this module is the finished
eight-attribute record.

So a `StandardMaterial` is exactly those eight attributes plus an id. Nothing
is derived, because there is nothing left to derive: the row arrives already
standardized, and the next step is the vector.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.logic.category import classify
from app.logic.identity import material_key
from app.logic.versions import PIPELINE_VERSION

__all__ = ["CPSE_CODES", "StandardMaterial", "cpse_code_for", "to_material"]

#: The CPSEs in the reference corpus whose display name does not reduce to a
#: usable code by the general rule below. Everything else falls through to it.
CPSE_CODES = {
    "NTPC": "NTPC", "BHEL": "BHEL", "IOCL": "IOCL", "GAIL": "GAIL", "ONGC": "ONGC",
    "HEC": "HEC", "Coal India (Central Coalfields Limited)": "CCL",
    "Coal India (BCCL)": "BCCL",
}


def cpse_code_for(company: str) -> str:
    """"Coal India (BCCL)" -> "BCCL". A short, stable tenant key."""
    if company in CPSE_CODES:
        return CPSE_CODES[company]
    return re.sub(r"[^A-Z]", "", company.upper())[:6] or "UNK"


@dataclass
class StandardMaterial:
    """One row in standard format: the eight canonical CPSE attributes.

    `material_id` is a BASE key when this is built. Uniqueness is a property of
    the batch, so `assign_material_ids()` runs over the whole batch afterwards
    to resolve collisions - see logic/identity.py.
    """

    material_id: str
    source_row: int

    cpse_code: str
    company: str
    description: str
    legacy_code: str
    quantity: float | None
    uom: str
    part_number: str
    make: str
    specifications: str

    national_id: str | None = None
    """Allocated by the service at admission - see logic/national_id.py. None
    until then, and never derived from the row's own contents."""

    category: str = "UNCLASSIFIED"
    """The material family. A blocking key and a filter, and nothing else -
    see logic/category.py. Deliberately absent from `identity_attributes`, so
    it never reaches the vector and a misclassification cannot move one."""

    pipeline_version: str = PIPELINE_VERSION
    extraction_model: str | None = None
    """Which Phase 1 adapter produced this row. A retrained adapter changes what
    a description means, and that has to be visible on the row."""

    #: The attributes that say WHICH ARTICLE this is. Everything else on the
    #: row is bookkeeping about one CPSE's copy of it.
    IDENTITY_FIELDS = (
        "Item Description (Raw)",
        "Part Number / OEM Number",
        "Make / Brand",
        "Specifications / Dimensions",
        "UOM",
    )

    @property
    def attributes(self) -> dict[str, str]:
        """All eight fields under their canonical names, absent ones dropped.

        The row as Phase 1 emitted it, for storage and for the API. Empty
        values are omitted rather than written as "NA": an absent attribute is
        not a value, and rendering it as one would let two rows look alike on
        the strength of what they are both missing.
        """
        pairs = {
            "Company": self.company,
            "Item Description (Raw)": self.description,
            "Item Code / Legacy Ref": self.legacy_code,
            "Quantity": "" if self.quantity is None else _format_quantity(self.quantity),
            "UOM": self.uom,
            "Part Number / OEM Number": self.part_number,
            "Make / Brand": self.make,
            "Specifications / Dimensions": self.specifications,
        }
        return {k: v for k, v in pairs.items() if v}

    @property
    def identity_attributes(self) -> dict[str, str]:
        """Only the attributes that identify the ARTICLE. This is what is embedded.

        Three of the eight are deliberately excluded, and each exclusion is the
        difference between finding a duplicate and missing it:

          Company                 finding the same article in another CPSE's
                                  master is the entire point of the system. If
                                  the company name is in the vector, NTPC's
                                  bearing and BHEL's identical bearing embed
                                  differently and never surface as duplicates.

          Item Code / Legacy Ref  a CPSE's own internal code. Two CPSEs holding
                                  the same physical part have different codes by
                                  definition, and the same CPSE re-coding its
                                  master would make every row look new.

          Quantity                stock level, not identity. Five of a bearing
                                  and five thousand of it are the same bearing.

        None of the three is lost: Company and the legacy code are what
        `material_id` is built from, `cpse_code` travels in the vector payload,
        and all eight are stored on the row.
        """
        return {
            name: value
            for name, value in self.attributes.items()
            if name in self.IDENTITY_FIELDS
        }


def _format_quantity(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def to_material(raw, *, extraction_model: str | None = None) -> StandardMaterial:
    """A parsed standard-format row -> the record this service stores.

    `raw` is a `StandardRow` from logic/standard_format.py. The only work done
    here is deriving the CPSE code and the base material id; every attribute is
    carried through exactly as Phase 1 wrote it, because a national master that
    silently edits what a CPSE submitted cannot be reconciled with the CPSE's
    own books.
    """
    code = cpse_code_for(raw.company)
    try:
        quantity = float(raw.quantity) if raw.quantity else None
    except (TypeError, ValueError):
        quantity = None

    return StandardMaterial(
        material_id=material_key(code, raw.legacy_code, raw.description),
        category=classify(raw.description, raw.specifications),
        source_row=raw.source_row,
        cpse_code=code,
        company=raw.company,
        description=raw.description,
        legacy_code=raw.legacy_code,
        quantity=quantity,
        uom=raw.uom,
        part_number=raw.part_number,
        make=raw.make,
        specifications=raw.specifications,
        extraction_model=extraction_model,
    )
