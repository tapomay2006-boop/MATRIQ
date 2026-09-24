"""
inference_engine.py - Low-GPU Pressure Qwen2.5-3B LoRA Extraction Engine.
Strictly executes the fine-tuned LoRA adapter from train_qwen_lora.ipynb (qwen2.5-3b-cpse-lora-v2).
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# System Prompt instructing strict grounding and "na" for unprovided attributes
SCHEMA_SYSTEM_PROMPT = (
    "You are an expert industrial material master data analyst for Indian Central Public Sector Enterprises (CPSEs). "
    "Extract standardized inventory attributes strictly as valid JSON with these exact 8 keys:\n"
    "{\n"
    '  "Company": "CPSE organization name or NA",\n'
    '  "Item Description (Raw)": "core engineering description",\n'
    '  "Item Code / Legacy Ref": "material code or NA",\n'
    '  "Quantity": integer quantity number or NA,\n'
    '  "UOM": "unit of measure like NOS, LTR, KGS, SET or NA",\n'
    '  "Part Number / OEM Number": "part number or NA",\n'
    '  "Make / Brand": "manufacturer brand or NA",\n'
    '  "Specifications / Dimensions": "specs and dimensions or NA"\n'
    "}\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "1. Extract ONLY values explicitly present in the input text.\n"
    "2. If an attribute/value is NOT explicitly provided in the input text, you MUST set its value strictly to 'NA'.\n"
    "3. NEVER fabricate, guess, or hallucinate companies, material codes, part numbers, quantities, brands, or dimensions."
)

# Canonical field mapping dictionary
KEY_MAP = {
    "Company": [
        "Company", "company", "Organization", "organization", "CPSE", "cpse",
        "Company Name", "company_name"
    ],
    "Item Description (Raw)": [
        "Item Description (Raw)", "Item Description", "item_description",
        "Description", "description", "Item_Description", "Item", "item",
        "Item Name", "item_name"
    ],
    "Item Code / Legacy Ref": [
        "Item Code / Legacy Ref", "Item Code", "Item_Code", "item_code",
        "Material Code", "material_code", "Mat Code", "mat_code",
        "Legacy Ref", "Code", "code"
    ],
    "Quantity": ["Quantity", "quantity", "Qty", "qty"],
    "UOM": ["UOM", "uom", "Unit", "unit", "Unit of Measure", "Unit of Measurement"],
    "Part Number / OEM Number": [
        "Part Number / OEM Number", "Part Number", "part_number", "Part_Number",
        "Part No", "part_no", "P/N", "p/n", "OEM Number", "OEM Part Number"
    ],
    "Make / Brand": ["Make / Brand", "Make", "make", "Brand", "brand", "Manufacturer", "manufacturer"],
    "Specifications / Dimensions": [
        "Specifications / Dimensions", "Specifications", "specifications",
        "Dimensions", "dimensions", "Specs", "specs", "Specification", "specification"
    ],
}

CANONICAL_FIELDS = [
    "Company",
    "Item Description (Raw)",
    "Item Code / Legacy Ref",
    "Quantity",
    "UOM",
    "Part Number / OEM Number",
    "Make / Brand",
    "Specifications / Dimensions",
]

COMMON_UOMS = [
    "NOS", "SET", "LTR", "KGS", "MTR", "PAIR", "PCS", "PKT", "EA", "BAG",
    "BOX", "DRUM", "ROLL", "CAN", "BTL", "TON", "QUINTAL", "MTRS", "KG",
    "LITRE", "LITRES", "PIECES", "NUMBERS", "NO", "M", "MM"
]

BOILERPLATE_PHRASES = [
    r"as per standard(?:is/iso| is/iso| iso)? specifications?\.?",
    r"as per standard specifications?\.?",
    r"standard is/iso specifications?\.?",
    r"as per standard\.?",
    r"is/iso specifications?\.?"
]

# Curated domain abbreviation taxonomy for CPSE material master catalogs
DEFAULT_CPSE_ABBREVIATIONS = [
    # Valves & Piping
    ("GT VLV", "GATE VALVE"),
    ("BL VLV", "BALL VALVE"),
    ("CK VLV", "CHECK VALVE"),
    ("GL VLV", "GLOBE VALVE"),
    ("BF VLV", "BUTTERFLY VALVE"),
    ("PLG VLV", "PLUG VALVE"),
    ("NDL VLV", "NEEDLE VALVE"),
    ("VLV", "VALVE"),
    ("VLVS", "VALVES"),
    ("PRV", "PRESSURE RELIEF VALVE"),
    ("NRV", "NON RETURN VALVE"),
    ("PCV", "PRESSURE CONTROL VALVE"),
    ("TCV", "TEMPERATURE CONTROL VALVE"),
    ("FCV", "FLOW CONTROL VALVE"),
    ("FLG", "FLANGE"),
    ("FLGD", "FLANGED"),
    ("GSKT", "GASKET"),
    ("GSKTS", "GASKETS"),
    ("NB", "NOMINAL BORE"),
    ("OD", "OUTER DIAMETER"),
    ("ID", "INNER DIAMETER"),
    ("THK", "THICKNESS"),
    ("DIA", "DIAMETER"),
    ("NOM", "NOMINAL"),
    # Metallurgy / Materials
    ("ALM", "ALUMINIUM"),
    ("ALUM", "ALUMINIUM"),
    ("SS", "STAINLESS STEEL"),
    ("S.S.", "STAINLESS STEEL"),
    ("S.S", "STAINLESS STEEL"),
    ("CS", "CARBON STEEL"),
    ("C.S.", "CARBON STEEL"),
    ("C.S", "CARBON STEEL"),
    ("MS", "MILD STEEL"),
    ("M.S.", "MILD STEEL"),
    ("M.S", "MILD STEEL"),
    ("CI", "CAST IRON"),
    ("C.I.", "CAST IRON"),
    ("DI", "DUCTILE IRON"),
    ("GI", "GALVANIZED IRON"),
    ("G.I.", "GALVANIZED IRON"),
    ("BRS", "BRASS"),
    ("BRZ", "BRONZE"),
    ("COP", "COPPER"),
    ("GALV", "GALVANIZED"),
    ("UNGALV", "UNGALVANIZED"),
    # Mechanical & Rotating Equipment
    ("BRG", "BEARING"),
    ("BRGS", "BEARING"),
    ("RAD", "RADIAL"),
    ("SPHR", "SPHERICAL"),
    ("TPR", "TAPER"),
    ("PMP", "PUMP"),
    ("PMPS", "PUMPS"),
    ("MTR", "MOTOR"),
    ("MTRS", "MOTORS"),
    ("IMP", "IMPELLER"),
    ("CPLG", "COUPLING"),
    ("RDCR", "REDUCER"),
    ("SFT", "SHAFT"),
    # Fasteners & Hardware
    ("HT", "HIGH TENSILE"),
    ("HEX", "HEXAGONAL"),
    ("BLT", "BOLT"),
    ("BLTS", "BOLTS"),
    ("SCR", "SCREW"),
    ("SCRS", "SCREWS"),
    ("WSHR", "WASHER"),
    ("WSHRS", "WASHERS"),
    ("SHT", "SHEET"),
    ("PLT", "PLATE"),
    ("ROD", "ROD"),
    # Electrical & Instrumentation
    ("PH", "PHASE"),
    ("HP", "HORSEPOWER"),
    ("KW", "KILOWATT"),
    ("AMP", "AMPERE"),
    ("PRESS", "PRESSURE"),
    ("TEMP", "TEMPERATURE"),
    ("HYD", "HYDRAULIC"),
    ("PNEU", "PNEUMATIC"),
    ("LUB", "LUBRICATING"),
    ("HEMM", "HEAVY EARTH MOVING MACHINERY"),
    ("SEC", "SECTION"),
    ("DEF", "DIESEL EXHAUST FLUID"),
    ("EHV", "EXTRA HIGH VOLTAGE"),
    ("BELT V", "V BELT"),
]

_ABBREVIATIONS_REGISTRY: Dict[str, str] = {}
for raw_abbr, exp_abbr in DEFAULT_CPSE_ABBREVIATIONS:
    _ABBREVIATIONS_REGISTRY[raw_abbr.upper()] = exp_abbr.upper()

# Try loading additional definitions from data/config/abbreviations.csv if present
_abbrev_csv_path = Path(__file__).resolve().parent.parent / "ai-service" / "data" / "config" / "abbreviations.csv"
if _abbrev_csv_path.exists():
    try:
        import csv
        with open(_abbrev_csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r_raw = (row.get("raw") or "").strip().upper()
                r_exp = (row.get("expansion") or "").strip().upper()
                if r_raw and r_exp:
                    _ABBREVIATIONS_REGISTRY[r_raw] = r_exp
    except Exception as e:
        logger.warning(f"Could not load abbreviations.csv: {e}")


def expand_abbreviations(text: str, custom_dict: Optional[Dict[str, str]] = None) -> str:
    """
    Expand standard CPSE industrial abbreviations in text to canonical technical terms.
    Enforces strict word boundaries (preserves words like 'EVOLVE', 'ALMOST', 'ASSEMBLY').
    Safe fallback: preserves unknown / ambiguous abbreviations without corruption.
    """
    if not text or not isinstance(text, str):
        return text

    abbrevs = dict(_ABBREVIATIONS_REGISTRY)
    if custom_dict:
        for k, v in custom_dict.items():
            abbrevs[k.strip().upper()] = v.strip().upper()

    # Sort longest raw first so 'GT VLV' matches before 'VLV'
    sorted_items = sorted(abbrevs.items(), key=lambda x: len(x[0]), reverse=True)

    result = text
    # 1. Expand standard grade shorthand like SS316 -> STAINLESS STEEL 316
    result = re.sub(r"(?<![A-Za-z0-9])SS\s*([0-9]{3}[A-Za-z]?)(?![A-Za-z0-9])", r"STAINLESS STEEL \1", result, flags=re.IGNORECASE)
    result = re.sub(r"(?<![A-Za-z0-9])CS\s*([0-9]{2,}[A-Za-z]?)(?![A-Za-z0-9])", r"CARBON STEEL \1", result, flags=re.IGNORECASE)

    # 2. Expand known abbreviations with strict boundary matching
    for raw, expansion in sorted_items:
        escaped_raw = re.escape(raw)
        pattern = rf"(?<![A-Za-z0-9]){escaped_raw}(?![A-Za-z0-9])"
        result = re.sub(pattern, expansion, result, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", result).strip()


def register_abbreviation(raw: str, expansion: str, scope: str = "", persist: bool = True) -> bool:
    """
    Active learning registration: add or update an abbreviation mapping in-memory
    and optionally persist to data/config/abbreviations.csv.
    """
    raw_clean = raw.strip().upper()
    exp_clean = expansion.strip().upper()
    if not raw_clean or not exp_clean:
        return False

    _ABBREVIATIONS_REGISTRY[raw_clean] = exp_clean
    logger.info(f"Registered new abbreviation mapping: {raw_clean} -> {exp_clean}")

    if persist and _abbrev_csv_path.exists():
        try:
            import csv
            with open(_abbrev_csv_path, mode="a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([raw_clean, exp_clean, scope, "active_learning"])
            logger.info(f"Persisted abbreviation mapping to {_abbrev_csv_path}")
        except Exception as e:
            logger.warning(f"Could not append to abbreviations.csv: {e}")

    return True


def is_na_val(v: Any) -> bool:
    """Check if value represents an unprovided, empty, or null field."""
    if v is None:
        return True
    s = str(v).strip().lower()
    return s in ["", "na", "n/a", "none", "nan", "null", "unknown", "-", "none.", "n/a."]


def clean_condensed(s: str) -> str:
    """Strip all punctuation and whitespace for fuzzy containment checks."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def clean_str(v: Any) -> str:
    """Normalize string and strip null/empty/na equivalents."""
    if is_na_val(v):
        return ""
    return str(v).strip().lower().rstrip(".")


def token_f1(pred: str, true: str) -> float:
    """Calculate token-level F1 score between predicted and true descriptions."""
    p_tok = set(re.findall(r"\w+", clean_str(pred)))
    t_tok = set(re.findall(r"\w+", clean_str(true)))
    if not p_tok and not t_tok:
        return 1.0
    if not p_tok or not t_tok:
        return 0.0
    common = p_tok.intersection(t_tok)
    if not common:
        return 0.0
    prec = len(common) / len(p_tok)
    rec = len(common) / len(t_tok)
    return 2 * (prec * rec) / (prec + rec)


def get_canonical_value(pred_dict: dict, canonical_field: str) -> Any:
    """Extract and normalize a canonical field from raw model prediction dictionary."""
    if not isinstance(pred_dict, dict):
        return "NA"
    aliases = KEY_MAP.get(canonical_field, [canonical_field])
    for alias in aliases:
        if alias in pred_dict and pred_dict[alias] is not None:
            val = pred_dict[alias]
            if is_na_val(val):
                continue
            if canonical_field == "Quantity":
                if isinstance(val, dict):
                    val = val.get("Number") or val.get("number") or val.get("qty") or val.get("Quantity")
                if is_na_val(val):
                    continue
                if isinstance(val, (str, int, float)):
                    s_val = str(val).strip()
                    m = re.match(r"^(\d+(?:\.\d+)?)\s*(.*)", s_val)
                    if m:
                        try:
                            return int(float(m.group(1)))
                        except Exception:
                            return "NA"
                try:
                    return int(float(val))
                except Exception:
                    return "NA"
            if canonical_field == "UOM":
                if isinstance(val, dict):
                    val = val.get("Unit") or val.get("unit") or val.get("UOM")
                if is_na_val(val):
                    continue
                clean_uom = str(val).strip().upper()
                return clean_uom if clean_uom not in ["NONE", "NULL", "NAN", "N/A", "NA", ""] else "NA"
            return val

    if canonical_field == "UOM":
        for q_key in ["Quantity", "quantity", "Qty", "qty"]:
            if q_key in pred_dict and pred_dict[q_key] is not None:
                q_val = pred_dict[q_key]
                if isinstance(q_val, dict):
                    unit_v = q_val.get("Unit") or q_val.get("unit") or q_val.get("UOM")
                    if unit_v and not is_na_val(unit_v):
                        return str(unit_v).strip().upper()
                elif isinstance(q_val, str):
                    m = re.match(r"^\d+(?:\.\d+)?\s*(.+)$", q_val.strip())
                    if m and m.group(1):
                        cand = m.group(1).strip().upper()
                        if cand not in ["NONE", "NULL", "NAN", "N/A", "NA", ""]:
                            return cand
    return "NA"


def resolve_canonical_dict(raw_dict: dict) -> Dict[str, Any]:
    """Resolve raw predicted dictionary to the exact 8 canonical CPSE attributes with 'NA' defaults."""
    resolved = {}
    for field in CANONICAL_FIELDS:
        val = get_canonical_value(raw_dict, field)
        if is_na_val(val):
            val = "NA"
        resolved[field] = val
    return resolved


def isolate_core_description(
    raw_desc: str,
    grounded_attrs: Dict[str, Any],
    raw_input: str
) -> str:
    """
    Ensure Item Description contains specifically the core engineering item description,
    not the entire raw input containing company, item code, quantity, UOM, part number, brand, etc.
    """
    clean_desc = (raw_desc or "").strip()
    raw_clean = (raw_input or "").strip()
    if not clean_desc or is_na_val(clean_desc):
        clean_desc = raw_clean

    raw_lower = raw_clean.lower()
    for bp in BOILERPLATE_PHRASES:
        if not re.search(bp, raw_lower):
            clean_desc = re.sub(bp, "", clean_desc, flags=re.IGNORECASE).strip()

    # Strip explicit labeled prefixes in description
    clean_desc = re.sub(r"\b(?:company|org|cpse)\s*[:\-]\s*[^.;,\n]+[.;,]?", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(?:mat|item|material|legacy)?\s*code\s*[:\-]\s*[^.;,\n]+[.;,]?", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(?:qty|quantity)\s*[:\-]?\s*\d+\s*(?:[a-zA-Z]+)?[.;,]?", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(?:p/n|part\s*no|oem\s*no|cat\-)\s*[:\-]?\s*[^.;,\n]+[.;,]?", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(?:make|brand|mfg|manufacturer)\s*[:\-]\s*[^.;,\n]+[.;,]?", "", clean_desc, flags=re.IGNORECASE)
    clean_desc = re.sub(r"\b(?:dim|dims|dimensions?|specs?)\s*[:\-]\s*[^.;,\n]+[.;,]?", "", clean_desc, flags=re.IGNORECASE)

    # If the description contains the company name, strip it
    comp = grounded_attrs.get("Company")
    if comp and not is_na_val(comp):
        comp_str = str(comp).strip()
        clean_desc = re.sub(r"\b" + re.escape(comp_str) + r"\b", "", clean_desc, flags=re.IGNORECASE)
        for m in re.findall(r"\b[A-Za-z0-9]{3,}\b", comp_str):
            clean_desc = re.sub(r"\b" + re.escape(m) + r"\b", "", clean_desc, flags=re.IGNORECASE)

    # If the description contains the item code, strip it
    code = grounded_attrs.get("Item Code / Legacy Ref")
    if code and not is_na_val(code):
        clean_desc = re.sub(r"\b" + re.escape(str(code).strip()) + r"\b", "", clean_desc, flags=re.IGNORECASE)

    # If the description contains quantity + UOM, strip it
    qty = grounded_attrs.get("Quantity")
    uom = grounded_attrs.get("UOM")
    if qty and not is_na_val(qty) and uom and not is_na_val(uom):
        clean_desc = re.sub(r"\b" + re.escape(str(qty)) + r"\s*" + re.escape(str(uom)) + r"\b", "", clean_desc, flags=re.IGNORECASE)
    elif qty and not is_na_val(qty):
        clean_desc = re.sub(r"(?:^|\s)" + re.escape(str(qty)) + r"(?:\s|$|[.,;])", " ", clean_desc)

    # Strip standalone UOM if present
    if uom and not is_na_val(uom):
        clean_desc = re.sub(r"\b" + re.escape(str(uom)) + r"\b", "", clean_desc, flags=re.IGNORECASE)

    # Strip part number if distinct alphanumeric code
    pn = grounded_attrs.get("Part Number / OEM Number")
    if pn and not is_na_val(pn) and re.search(r"[A-Za-z]+[-_]\d+", str(pn)):
        clean_desc = re.sub(r"\b" + re.escape(str(pn).strip()) + r"\b", "", clean_desc, flags=re.IGNORECASE)

    # Strip specs if explicitly labeled
    specs = grounded_attrs.get("Specifications / Dimensions")
    if specs and not is_na_val(specs) and re.search(r"(?:dim|dimensions?|specs?|rating)\s*[:\-]", raw_clean, re.IGNORECASE):
        clean_desc = re.sub(r"\b" + re.escape(str(specs).strip()) + r"\b", "", clean_desc, flags=re.IGNORECASE)

    # Clean punctuation / whitespace
    clean_desc = re.sub(r"\s+", " ", clean_desc)
    clean_desc = re.sub(r"^[\s,.;:\-_/]+|[\s,.;:\-_/]+$", "", clean_desc).strip()

    return clean_desc if clean_desc else (raw_desc.strip() if raw_desc else raw_clean)


def ground_attributes(raw_input: str, pred_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strictly ground all predicted attributes against the user input text.
    If an attribute is not actually present or mentioned in raw_input, it is set to 'NA'.
    Takes abbreviation expansion into account so valid technical terms are not wiped out.
    """
    grounded = {}
    raw_clean = (raw_input or "").strip()
    if not raw_clean:
        return {f: "NA" for f in CANONICAL_FIELDS}

    raw_clean_expanded = expand_abbreviations(raw_clean)
    raw_lower = raw_clean.lower()
    raw_expanded_lower = raw_clean_expanded.lower()
    raw_condensed = clean_condensed(raw_clean)
    raw_condensed_expanded = clean_condensed(raw_clean_expanded)

    raw_words = set(re.findall(r"\b[a-zA-Z0-9_]+\b", raw_lower)).union(
        set(re.findall(r"\b[a-zA-Z0-9_]+\b", raw_expanded_lower))
    )

    # 1. Quantity & UOM (resolve first so quantity number isn't mistakenly used as code or part number)
    qty = pred_dict.get("Quantity")
    qty_resolved = "NA"
    if not is_na_val(qty):
        try:
            qty_num = int(float(qty))
            qty_str = str(qty_num)
            # Verify if this number appears as a distinct number in the raw input
            if re.search(r"\b" + re.escape(qty_str) + r"\b", raw_clean):
                qty_resolved = qty_num
            else:
                # Check explicit quantity pattern in raw text (e.g. Qty: 2590)
                m_qty = re.search(r"(?:qty|quantity)\s*[:\-]?\s*(\d+)", raw_lower)
                if m_qty:
                    qty_resolved = int(m_qty.group(1))
                else:
                    # Look for number immediately preceding a recognized UOM
                    m_uom_qty = re.search(r"\b(\d+)\s*(?:nos|set|ltr|kgs|mtr|pair|pcs|pkt|ea)\b", raw_lower)
                    if m_uom_qty:
                        qty_resolved = int(m_uom_qty.group(1))
                    else:
                        qty_resolved = "NA"
        except (ValueError, TypeError):
            qty_resolved = "NA"
    else:
        m_qty = re.search(r"(?:qty|quantity)\s*[:\-]?\s*(\d+)", raw_lower)
        if m_qty:
            qty_resolved = int(m_qty.group(1))
        else:
            m_uom_qty = re.search(r"\b(\d+)\s*(?:nos|set|ltr|kgs|mtr|pair|pcs|pkt|ea)\b", raw_lower)
            if m_uom_qty:
                qty_resolved = int(m_uom_qty.group(1))
            else:
                qty_resolved = "NA"

    grounded["Quantity"] = qty_resolved

    # 2. UOM
    uom = pred_dict.get("UOM")
    uom_resolved = "NA"
    if not is_na_val(uom):
        uom_str = str(uom).strip().upper()
        if re.search(r"\b" + re.escape(uom_str) + r"\b", raw_clean, re.IGNORECASE):
            uom_resolved = uom_str
    if uom_resolved == "NA":
        for cand in COMMON_UOMS:
            if cand in ["M", "MM", "NO"]:
                continue
            if re.search(r"\b" + re.escape(cand) + r"\b", raw_clean, re.IGNORECASE):
                uom_resolved = cand
                break
    grounded["UOM"] = uom_resolved

    # 3. Company
    comp = pred_dict.get("Company")
    if is_na_val(comp):
        grounded["Company"] = "NA"
    else:
        comp_str = str(comp).strip()
        comp_lower = comp_str.lower()
        comp_condensed = clean_condensed(comp_str)
        if comp_lower in raw_lower or (len(comp_condensed) >= 3 and (comp_condensed in raw_condensed or comp_condensed in raw_condensed_expanded)):
            grounded["Company"] = comp_str
        else:
            tokens = [t for t in re.findall(r"\b[a-zA-Z0-9]+\b", comp_lower) if len(t) >= 3]
            found = any(t in raw_words for t in tokens)
            grounded["Company"] = comp_str if found else "NA"

    def is_just_qty(val_str: str) -> bool:
        if qty_resolved != "NA" and str(qty_resolved) == val_str.strip():
            return True
        return False

    # 4. Item Code / Legacy Ref
    item_code = pred_dict.get("Item Code / Legacy Ref")
    if is_na_val(item_code):
        grounded["Item Code / Legacy Ref"] = "NA"
    else:
        code_str = str(item_code).strip()
        code_condensed = clean_condensed(code_str)
        if is_just_qty(code_str) and not re.search(r"(?:mat|item|material|legacy)\s*code", raw_lower):
            grounded["Item Code / Legacy Ref"] = "NA"
        elif code_condensed and len(code_condensed) >= 3 and code_condensed in raw_condensed:
            grounded["Item Code / Legacy Ref"] = code_str
        else:
            digits = re.findall(r"\d{4,}", code_str)
            if digits and any(d in raw_condensed for d in digits) and not any(d == str(qty_resolved) for d in digits):
                grounded["Item Code / Legacy Ref"] = code_str
            else:
                grounded["Item Code / Legacy Ref"] = "NA"

    # 5. Part Number / OEM Number
    pn = pred_dict.get("Part Number / OEM Number")
    if is_na_val(pn):
        grounded["Part Number / OEM Number"] = "NA"
    else:
        pn_str = str(pn).strip()
        pn_condensed = clean_condensed(pn_str)
        if is_just_qty(pn_str) and not re.search(r"(?:p/n|part\s*no|cat\-)", raw_lower):
            grounded["Part Number / OEM Number"] = "NA"
        elif pn_condensed and len(pn_condensed) >= 3 and pn_condensed in raw_condensed:
            grounded["Part Number / OEM Number"] = pn_str
        else:
            tokens = [t for t in re.findall(r"\b[a-zA-Z0-9]+\b", pn_str.lower()) if len(t) >= 3]
            if tokens and all(t in raw_words for t in tokens) and not (len(tokens) == 1 and str(qty_resolved) == tokens[0]):
                grounded["Part Number / OEM Number"] = pn_str
            else:
                grounded["Part Number / OEM Number"] = "NA"

    # 6. Make / Brand
    make = pred_dict.get("Make / Brand")
    if is_na_val(make):
        grounded["Make / Brand"] = "NA"
    else:
        make_str = str(make).strip()
        make_lower = make_str.lower()
        make_condensed = clean_condensed(make_str)
        is_comp_dup = (
            grounded.get("Company") != "NA" and
            clean_condensed(grounded["Company"]) == make_condensed
        )
        has_make_label = bool(re.search(r"(?:make|brand|mfg|oem|manufacturer)\s*[:\-]", raw_lower))

        if is_comp_dup and not has_make_label:
            grounded["Make / Brand"] = "NA"
        elif make_condensed and len(make_condensed) >= 3 and (make_condensed in raw_condensed or make_condensed in raw_condensed_expanded):
            if make_str.upper() in ["ONGC", "IOCL", "GAIL", "NTPC", "CIL", "BCCL", "BPCL", "HPCL", "CPCL"] and not has_make_label:
                grounded["Make / Brand"] = "NA"
            else:
                grounded["Make / Brand"] = make_str
        elif "any reputed" in make_lower and ("any reputed" in raw_lower or "any reputed" in raw_expanded_lower):
            grounded["Make / Brand"] = make_str
        else:
            tokens = [t for t in re.findall(r"\b[a-zA-Z0-9]+\b", make_lower) if len(t) >= 3]
            if tokens and all(t in raw_words for t in tokens):
                grounded["Make / Brand"] = make_str
            else:
                grounded["Make / Brand"] = "NA"

    # 7. Specifications / Dimensions
    specs = pred_dict.get("Specifications / Dimensions")
    specs_resolved = "NA"
    if not is_na_val(specs):
        specs_str = str(specs).strip()
        cleaned_specs = specs_str
        for bp in BOILERPLATE_PHRASES:
            if not re.search(bp, raw_lower):
                cleaned_specs = re.sub(bp, "", cleaned_specs, flags=re.IGNORECASE).strip()
        cleaned_specs = re.sub(r"^[\s,.;:]+|[\s,.;:]+$", "", cleaned_specs).strip()

        if cleaned_specs and not is_na_val(cleaned_specs):
            spec_tokens = [t for t in re.findall(r"\b[a-zA-Z0-9]+\b", cleaned_specs.lower()) if len(t) >= 2]
            matching_tokens = [t for t in spec_tokens if t in raw_words or t in raw_condensed or t in raw_condensed_expanded]
            if matching_tokens and len(matching_tokens) >= max(1, len(spec_tokens) // 2):
                specs_resolved = cleaned_specs

    if specs_resolved == "NA":
        # Check if raw text has explicit Dim / Specs / Rating phrases
        m_specs = re.search(r"(?:dim|dims|dimensions?|specs?|rating)\s*[:\-]\s*([^,\n;]+(?:,[^,\n;]+)*)", raw_clean, re.IGNORECASE)
        if m_specs:
            specs_resolved = m_specs.group(0).strip()

    grounded["Specifications / Dimensions"] = specs_resolved

    # 8. Item Description (Raw) - isolate specifically the core engineering item description
    desc = pred_dict.get("Item Description (Raw)")
    grounded["Item Description (Raw)"] = isolate_core_description(desc, grounded, raw_clean)

    # Return canonical dictionary ordered strictly by CANONICAL_FIELDS
    return {f: grounded.get(f, "NA") for f in CANONICAL_FIELDS}



class QwenLoraEngine:
    """
    Low-GPU-pressure inference engine for CPSE material extraction.
    Exclusively loads and runs the fine-tuned Qwen2.5-3B LoRA adapter.
    """

    def __init__(
        self,
        adapter_dir: Optional[str] = None,
        base_model_name: str = "Qwen/Qwen2.5-3B-Instruct",
        max_new_tokens: int = 256,
        cpu_threads: int = 8,
        max_gpu_memory: Optional[str] = None,
    ):
        self.base_model_name = base_model_name
        self.max_new_tokens = max_new_tokens
        self.cpu_threads = cpu_threads
        self.max_gpu_memory = max_gpu_memory

        # Locate adapter directory
        if adapter_dir:
            self.adapter_dir = adapter_dir
        else:
            default_path = Path(__file__).parent / "models" / "qwen2.5-3b-cpse-lora-v2"
            self.adapter_dir = str(default_path) if default_path.exists() else str(Path(__file__).parent / "models" / "qwen2.5-3b-cpse-lora")

        import threading
        self._lock = threading.Lock()
        self.model = None
        self.tokenizer = None
        self._loaded = False

        import torch
        has_cuda = torch.cuda.is_available()
        self.device = "cuda" if has_cuda else "cpu"
        if has_cuda:
            self.device_name = torch.cuda.get_device_name(0)
            self.total_vram_gb = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
        else:
            self.device_name = "CPU"
            self.total_vram_gb = 0.0
        self.vram_gb = 0.0

    def load_model(self) -> None:
        """
        Thread-safely load model and LoRA adapter with strict GPU safeguards.
        Uses 4-bit NF4 when CUDA is available to limit VRAM <= 2.2 GB.
        Caps CPU threads when on CPU.
        """
        with self._lock:
            if self._loaded:
                return

            import time
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel

            t_start = time.time()
            logger.info("======================================================================")
            logger.info(">> INITIALIZING QWEN2.5-3B CPSE EXTRACTION ENGINE")
            logger.info(f">> Base Model : {self.base_model_name}")
            logger.info(f">> LoRA Path  : {self.adapter_dir}")

            has_cuda = torch.cuda.is_available()
            self.device = "cuda" if has_cuda else "cpu"

            # 1. Load Tokenizer
            tokenizer_path = self.adapter_dir if os.path.exists(self.adapter_dir) else self.base_model_name
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.padding_side = "left"

            # 2. Resource-Guarded Base Model Loading
            if has_cuda:
                self.device_name = torch.cuda.get_device_name(0)
                total_vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
                logger.info(f">> Compute Device: GPU [CUDA] - {self.device_name} ({total_vram:.1f} GB VRAM)")
                logger.info(">> Enabling 4-bit NF4 Quantization (Memory Footprint ~2.0 GB VRAM)...")
                
                # Active memory purge before model allocation
                torch.cuda.empty_cache()
                
                from transformers import BitsAndBytesConfig
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                )

                # Hugging Face max_memory map: Utilize maximum available GPU headroom with safety buffer
                max_vram_val = self.max_gpu_memory or os.getenv("MAX_GPU_MEMORY")
                if not max_vram_val:
                    # Dynamically utilize maximum safe GPU VRAM leaving ~0.5 GB for CUDA context and activations
                    safe_headroom = max(2.2, round(total_vram - 0.5, 1))
                    max_vram_val = f"{safe_headroom}GiB"

                device_count = torch.cuda.device_count()
                max_memory_map = {i: max_vram_val for i in range(device_count)} if device_count > 0 else {0: max_vram_val}
                max_memory_map["cpu"] = "16GiB"
                logger.info(f">> Setting Hugging Face max_memory allocation map: {max_memory_map}")

                base_model = AutoModelForCausalLM.from_pretrained(
                    self.base_model_name,
                    quantization_config=bnb_config,
                    device_map="auto",
                    max_memory=max_memory_map,
                    trust_remote_code=True,
                )
            else:
                self.device_name = f"CPU ({self.cpu_threads} threads)"
                logger.info(f">> Compute Device: CPU with {self.cpu_threads} threads (bfloat16)...")
                try:
                    torch.set_num_threads(self.cpu_threads)
                except Exception:
                    pass
                base_model = AutoModelForCausalLM.from_pretrained(
                    self.base_model_name,
                    torch_dtype=torch.bfloat16,
                    device_map=None,
                    trust_remote_code=True,
                )

        # 3. Load LoRA Adapter
        if os.path.exists(self.adapter_dir):
            logger.info(f">> Attaching fine-tuned LoRA adapter from {self.adapter_dir}...")
            self.model = PeftModel.from_pretrained(base_model, self.adapter_dir)
        else:
            logger.warning(f"LoRA adapter directory not found at {self.adapter_dir}; running base model directly.")
            self.model = base_model

        self.model.eval()
        self._loaded = True

        if has_cuda:
            self.vram_gb = round(torch.cuda.memory_allocated() / 1024**3, 2)
            logger.info(f">> Model successfully loaded in {time.time() - t_start:.2f}s | VRAM Used: {self.vram_gb} GB")
        else:
            logger.info(f">> Model successfully loaded in {time.time() - t_start:.2f}s on CPU.")
        logger.info("======================================================================")

    def format_prompt(self, raw_text: str) -> str:
        """Construct prompt using ChatML format matching train_qwen_lora.ipynb."""
        messages = [
            {"role": "system", "content": SCHEMA_SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract attributes from this industrial material text:\n\n{raw_text.strip()}"}
        ]
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
            except Exception:
                pass

        return (
            f"<|im_start|>system\n{SCHEMA_SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\nExtract attributes from this industrial material text:\n\n{raw_text.strip()}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

    def extract_single(self, text: str) -> Dict[str, Any]:
        """Extract standardized CPSE attributes from a single messy text string."""
        if not text or not str(text).strip():
            return {f: "NA" for f in CANONICAL_FIELDS}

        self.load_model()
        import time
        import torch

        clean_input = text.strip()
        display_input = (clean_input[:75] + "...") if len(clean_input) > 75 else clean_input
        logger.info(f">> [INFERENCE START] Processing: \"{display_input}\"")
        logger.info(f">> Hardware Target : {self.device.upper()} ({self.device_name})")

        prompt = self.format_prompt(clean_input)
        inputs = self.tokenizer(prompt, return_tensors="pt")
        if self.device == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        t_gen_start = time.time()
        # Qwen EOS tokens: tokenizer EOS, <|im_end|> (151645), <|endoftext|> (151643)
        eos_ids = [self.tokenizer.eos_token_id, 151645, 151643]
        eos_ids = list(set([t for t in eos_ids if t is not None]))

        with self._lock:
            with torch.inference_mode():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    eos_token_id=eos_ids,
                    pad_token_id=self.tokenizer.pad_token_id,
                )

        elapsed = time.time() - t_gen_start
        input_len = inputs["input_ids"].shape[1]
        gen_tokens = outputs[0][input_len:]
        tok_count = len(gen_tokens)
        speed = tok_count / max(elapsed, 0.001)

        decoded = self.tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
        logger.info(f">> [INFERENCE COMPLETE] Generated {tok_count} tokens in {elapsed:.2f}s ({speed:.1f} tok/sec)")

        # Parse generated JSON
        clean_json = decoded
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()

        logger.info(f">> Raw Generated Output:\n{clean_json}")

        pred_dict = {}
        # 1. Direct JSON parse
        try:
            pred_dict = json.loads(clean_json)
        except Exception:
            pass

        # 2. Extract balanced outer braces
        if not pred_dict:
            m = re.search(r"(\{.*\})", clean_json, re.DOTALL)
            if m:
                try:
                    pred_dict = json.loads(m.group(1))
                except Exception:
                    pass

        # 3. Auto-close truncated JSON
        if not pred_dict and "{" in clean_json:
            trimmed = clean_json[clean_json.find("{"):].strip()
            if trimmed.count('"') % 2 != 0:
                trimmed += '"'
            open_braces = trimmed.count("{") - trimmed.count("}")
            if open_braces > 0:
                trimmed += "}" * open_braces
            try:
                pred_dict = json.loads(trimmed)
            except Exception:
                pass

        # 4. Fallback: regex key-value extraction for all canonical aliases
        if not pred_dict:
            for field, aliases in KEY_MAP.items():
                for alias in aliases:
                    pattern = rf'"{re.escape(alias)}"\s*:\s*(?:"([^"]*)"|(\d+(?:\.\d+)?)|(null))'
                    m = re.search(pattern, clean_json, re.IGNORECASE)
                    if m:
                        s_v, n_v, null_v = m.groups()
                        if s_v is not None:
                            pred_dict[field] = s_v
                            break
                        elif n_v is not None:
                            pred_dict[field] = float(n_v) if "." in n_v else int(n_v)
                            break
                        elif null_v is not None:
                            pred_dict[field] = None
                            break

        result = resolve_canonical_dict(pred_dict)
        # Apply strict text-grounding guardrail to eliminate hallucinated fields not in user text
        result = ground_attributes(clean_input, result)

        # Apply CPSE domain abbreviation standardization to eliminate catalog noise
        if result.get("Item Description (Raw)") and result["Item Description (Raw)"] != "NA":
            result["Item Description (Raw)"] = expand_abbreviations(result["Item Description (Raw)"])
        if result.get("Specifications / Dimensions") and result["Specifications / Dimensions"] != "NA":
            result["Specifications / Dimensions"] = expand_abbreviations(result["Specifications / Dimensions"])
        if result.get("Make / Brand") and result["Make / Brand"] != "NA":
            result["Make / Brand"] = expand_abbreviations(result["Make / Brand"])

        logger.info(">> Extracted Attributes (Grounded & Standardized):")
        for k, v in result.items():
            logger.info(f"   * {k:28}: {v}")
        return result

    def extract_batch(
        self,
        texts: List[str],
        callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Sequentially extract records with low GPU memory pressure and progress tracking.
        Clears CUDA cache periodically.
        """
        import torch
        results = []
        total = len(texts)
        logger.info(f">> [BATCH START] Extracting {total} items sequentially on {self.device.upper()}...")

        for i, text in enumerate(texts):
            logger.info(f">> [BATCH PROGRESS {i + 1}/{total}]")
            record = self.extract_single(text)
            results.append(record)

            if callback:
                try:
                    callback(i + 1, total, record)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

            # Active memory hygiene every 5 records
            if (i + 1) % 5 == 0 and torch.cuda.is_available():
                torch.cuda.empty_cache()

        logger.info(f">> [BATCH COMPLETE] Finished all {total} records successfully.")
        return results
