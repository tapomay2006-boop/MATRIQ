"""The material family, used as a blocking key and a filter. Nothing else.

    BALL BEARING 6205 2RS  ->  BEARING
    GATE VALVE 2 INCH CS   ->  VALVE
    UNSEEN ALIEN ARTIFACT  ->  UNCLASSIFIED

Keyword rules over the description. Deterministic, ordered, and small enough
that a materials engineer can read the whole table and argue with it - which is
the only kind of classifier worth having here, because of what this value is
allowed to affect.

What the category IS
--------------------
  * a payload field on every vector, so a search can say "bearings only";
  * a filter on GET /materials;
  * an optional blocking key for the existence check (off by default - see
    `EXISTENCE_BLOCK_BY_CATEGORY`).

What the category is NOT
------------------------
  * **not part of the embedded text.** It deliberately does not reach
    `embedding_text`, so it cannot move a vector and a misclassification cannot
    change which rows look alike. It also means adding this file changed no
    existing `canonical_hash` - which matters, because there is no reindex
    endpoint to repair one.
  * **not identity.** `material_id` does not derive from it.
  * **not a verdict.** Nothing decides EXISTS or NEW on the strength of it.

Abstaining is a real answer. A row this table does not recognise is
UNCLASSIFIED, not forced into the nearest family, because a confident wrong
family is worse than an honest empty one: with blocking on, it is precisely
what stops a duplicate from ever being compared to its twin.
"""

from __future__ import annotations

import re

__all__ = ["CATEGORIES", "UNCLASSIFIED", "classify"]

UNCLASSIFIED = "UNCLASSIFIED"

#: Order matters: the first match wins, so specific families sit above generic
#: ones. WIRE ROPE must beat CABLE; SEAL KIT must beat the bare O-RING check;
#: CONVEYOR BELT must beat V-BELT, which must beat a lone BELT.
#:
#: Patterns include the raw CPSE abbreviations (BRG, VLV, GSKT) as well as the
#: expanded words, so a description classifies whether or not the abbreviation
#: taxonomy has been applied to it.
RULES: list[tuple[str, str]] = [
    ("BEARING", r"\b(BRG|BRGS|BEARING|BEARINGS)\b"),
    ("SAFETY_SHOE", r"\bSAFETY\s+SHOE\b|\bSHOE\b"),
    ("O_RING", r"\bO\s*-?\s*RING\b|\bORING\b"),
    ("SEAL", r"\b(MECHANICAL\s+SEAL|SEAL\s+KIT|GLAND\s+PACKING|GLAND|OIL\s+SEAL|SEAL)\b"),
    ("FILTER", r"\bFILTER\b"),
    ("VALVE", r"\b(VALVE|VLV|VLVS|PRV|NRV|PCV|TCV|FCV)\b"),
    ("FASTENER", r"\b(BOLT|BLT|NUT|SCREW|SCR|WASHER|WSHR|STUD)\b"),
    ("BELT_CONVEYOR", r"\bCONVEYOR\s+BELT\b|\bBELT\b.*\bCONVEYOR\b"),
    ("BELT_V", r"\bV\s*-?\s*BELT\b|\bBELT\s+V\b|\bBELT\b"),
    ("CABLE", r"\bWIRE\s+ROPE\b|\bCABLE\b|\bXLPE\b"),
    ("PIPE_FITTING", r"\b(GASKET|GSKT|FLANGE|FLG|ELBOW|TEE|REDUCER|RDCR|TUBE|PIPE)\b"),
    ("MOTOR", r"\b(MOTOR|MTR)\b"),
    ("PUMP", r"\b(PUMP|PMP)\b"),
    ("LUBRICANT", r"\b(OIL|GREASE|LUBRICAT)\w*\b"),
    ("WELDING", r"\bWELDING\s+ELECTRODE\b|\bELECTRODE\b"),
    ("HOSE", r"\bHOSE\b"),
    ("LIGHTING", r"\b(LED|FLOOD\s+LIGHT|LAMP|LUMINAIRE)\b"),
    ("ELECTRICAL", r"\b(MCB|MCCB|CONTACTOR|RELAY|BREAKER|HEATER)\b"),
    ("INSTRUMENT", r"\b(PRESSURE\s+GAUGE|GAUGE|TRANSMITTER|THERMOMETER)\b"),
    ("GAS", r"\b(OXYGEN|NITROGEN|ACETYLENE)\b.*\bCYLINDER\b|\bCYLINDER\s+REFILL\b"),
    ("CHEMICAL", r"\bDIESEL\s+EXHAUST\s+FLUID\b|\bDEF\b|\bAUS\s*32\b"),
    ("MACHINE_PART", r"\bTRACK\s+CHAIN\b|\bDOZER\b|\bASSEMBLY\b"),
    ("ELECTRONICS_IT",
     r"\b(UPS|ROUTER|ETHERNET\s+SWITCH|NETWORK\s+SWITCH|SERVER|POWER\s+SUPPLY|SMPS|BATTERY)\b"),
    ("SAFETY_PPE",
     r"\b(HELMET|HARD\s+HAT|GOGGLES|FACE\s+SHIELD|SAFETY\s+GLOVES|SAFETY\s+HARNESS|EAR\s*PLUG)\b"),
    ("HARDWARE_TOOL",
     r"\b(SPANNER|WRENCH|SOCKET\s+WRENCH|DRILL\s+BIT|PLIERS|SCREWDRIVER|CUTTING\s+DISC)\b"),
]

_COMPILED = [(name, re.compile(pattern, re.I)) for name, pattern in RULES]

#: Every family this table can produce, plus the abstention. What a UI filters on.
CATEGORIES: tuple[str, ...] = tuple(name for name, _ in RULES) + (UNCLASSIFIED,)


def classify(*parts: str) -> str:
    """The first family whose pattern appears, or UNCLASSIFIED.

    Takes several fields because a family is sometimes only visible in the
    specifications - `SEAL KIT` in the description, `VITON` in the specs - and
    joining them costs nothing.
    """
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return UNCLASSIFIED

    for category, pattern in _COMPILED:
        if pattern.search(text):
            return category
    return UNCLASSIFIED
