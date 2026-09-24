"""The standard format: what Phase 1 produces and the vector half consumes.

    raw text --[ logic/extraction.py ]--> STANDARD FORMAT --> vector embedding DB

The standard format is eight canonical CPSE attributes. This module is the
contract for them, and nothing else. It knows:

  * the eight field names, imported from the extraction engine itself so the
    producer and the consumer cannot drift apart;
  * every spelling of those names this service will accept - canonical,
    snake_case, and the engine's own alias table;
  * that the engine writes the string ``"NA"`` for an attribute it could not
    ground in the input, which means *absent*, not a value.

Rows arrive here two ways and only two: as JSON on POST /standardized/check,
or straight from the extraction engine in the same process. Both hand over the
same eight attributes, so both go through `parse_row`.

What this module does NOT do is guess. Deciding that a column called `Mat Txt`
holds a description is Phase 1's job and happens before any of this runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.logic.extraction import CANONICAL_FIELDS, KEY_MAP

__all__ = [
    "CANONICAL_FIELDS",
    "FIELD_BY_ALIAS",
    "normalize_key",
    "RowFormatError",
    "STANDARD_FIELDS",
    "StandardRow",
    "normalize_value",
    "parse_row",
    "to_standard_dict",
]


class RowFormatError(ValueError):
    """A row is not in standard format. Always the caller's fault (400/422)."""


#: canonical display name -> the StandardRow field it fills.
_CANONICAL_TO_FIELD = {
    "Company": "company",
    "Item Description (Raw)": "description",
    "Item Code / Legacy Ref": "legacy_code",
    "Quantity": "quantity",
    "UOM": "uom",
    "Part Number / OEM Number": "part_number",
    "Make / Brand": "make",
    "Specifications / Dimensions": "specifications",
}

#: The eight fields of a standard row, in StandardRow terms.
STANDARD_FIELDS = tuple(_CANONICAL_TO_FIELD.values())


def normalize_key(key: str) -> str:
    """Fold a JSON key to its comparison form.

    `"Item Description (Raw)"`, `"item_description_raw"` and
    `"ITEM DESCRIPTION RAW"` are the same key. Punctuation carries no meaning
    in a header, so it is dropped rather than enumerated.
    """
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _build_alias_table() -> dict[str, str]:
    table: dict[str, str] = {}

    # 1. The canonical names and the StandardRow field names themselves.
    for canonical, field in _CANONICAL_TO_FIELD.items():
        table[normalize_key(canonical)] = field
        table[normalize_key(field)] = field

    # 2. The extraction engine's own alias table, so anything it resolves is
    #    accepted here too. Its keys ARE the canonical names.
    for canonical, aliases in KEY_MAP.items():
        field = _CANONICAL_TO_FIELD.get(canonical)
        if field is None:
            continue
        for alias in aliases:
            table.setdefault(normalize_key(alias), field)

    # 3. The handful of shorthands a hand-written client reaches for. Kept
    #    short on purpose: this is a contract, not header inference. Guessing
    #    what an unknown header means is Phase 1's job, and Phase 1 has already
    #    run by the time a row gets here.
    for alias, field in {
        "cpse": "company", "organisation": "company", "organization": "company",
        "desc": "description", "itemdescription": "description",
        "legacycode": "legacy_code", "itemcode": "legacy_code",
        "qty": "quantity",
        "unit": "uom", "unitofmeasure": "uom",
        "partno": "part_number", "partnumber": "part_number", "oem": "part_number",
        "brand": "make", "manufacturer": "make",
        "specs": "specifications", "specification": "specifications",
        "dimensions": "specifications",
    }.items():
        table.setdefault(alias, field)

    return table


#: Every accepted spelling -> the StandardRow field it fills.
FIELD_BY_ALIAS: dict[str, str] = _build_alias_table()

#: What Phase 1 writes when it could not ground an attribute in the input
#: text. They mean "absent", so they are flattened to "" on entry rather than
#: travelling into the master as literal values - and, more to the point,
#: rather than contributing the token "NA" to a vector.
_ABSENT = {"", "na", "n/a", "nan", "none", "null", "-", "unknown"}


def normalize_value(value: Any) -> str:
    """Coerce one standard-format cell to a trimmed string, absent -> ""."""
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _ABSENT else text


def to_standard_dict(payload: dict[str, Any]) -> dict[str, str]:
    """Resolve an incoming row's keys onto the eight standard fields.

    Unrecognised keys are ignored rather than rejected: a forwarded review
    session attaches `_record_id`, `_is_modified` and `_raw_input` to every
    record, and a row that carries provenance is not a malformed row.
    """
    if not isinstance(payload, dict):
        raise RowFormatError(
            f"A standard-format row must be an object, got {type(payload).__name__}."
        )

    resolved: dict[str, str] = {field: "" for field in STANDARD_FIELDS}
    for key, value in payload.items():
        field = FIELD_BY_ALIAS.get(normalize_key(str(key)))
        if field is None or resolved[field]:
            continue
        resolved[field] = normalize_value(value)
    return resolved


@dataclass
class StandardRow:
    """One row in standard format, parsed and trimmed. Absent fields are "".

    The same eight attributes the extraction engine emits, in the field names
    the rest of the service uses. Nothing is renamed twice: this is the only
    translation between the canonical display names and the code.
    """

    source_row: int
    company: str
    description: str
    legacy_code: str = ""
    quantity: str = ""
    uom: str = ""
    part_number: str = ""
    make: str = ""
    specifications: str = ""


def parse_row(
    payload: dict[str, Any],
    source_row: int,
    *,
    default_company: str = "",
) -> StandardRow:
    """One incoming row -> a StandardRow, or RowFormatError.

    Two fields are required and the rest are not, which mirrors what the
    extraction engine can and cannot guarantee. It grounds every attribute in
    the input text and writes "NA" for anything the text did not contain, so a
    sparse row is normal and is stored sparse. A row with no description is
    not sparse - it is a row that never carried an article at all.
    """
    values = to_standard_dict(payload)
    company = values["company"] or normalize_value(default_company)

    if not values["description"]:
        raise RowFormatError(
            "Item Description (Raw) is empty; the row cannot be identified. "
            "Phase 1 grounds this field in the source text, so an empty one "
            "means the row never carried a description."
        )
    if not company:
        raise RowFormatError(
            "Company is empty and no default_company was given; the row cannot "
            "be attributed to a CPSE."
        )

    return StandardRow(
        source_row=source_row,
        company=company,
        description=values["description"],
        legacy_code=values["legacy_code"],
        quantity=values["quantity"],
        uom=values["uom"],
        part_number=values["part_number"],
        make=values["make"],
        specifications=values["specifications"],
    )
