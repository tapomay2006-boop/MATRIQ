"""Labelled material pairs: the Siamese model's only input.

    query_material,candidate_material,label
    V BELT C 120,V-BELT C-120,1
    V BELT C 120,V BELT C 125,0

Two sources, and both end as the same `Pair`:

  * a CSV a person wrote or reviewed (`load_pairs`);
  * a standard-format corpus (`generate_pairs`), where rows describing the
    same article are positives and rows describing different ones are
    negatives - plus the augmentations that make a model robust to how people
    actually type: `C-120` / `C120` / `C 120`, `BRG` for `BEARING`, a dropped
    word, a swapped word order, a sentence around the name. The negatives that
    matter most are the ones that differ by a number - `6205` against `6206` -
    because that is exactly what a general embedding cannot see.

Labels are 0/1 today. `Pair.relation` is carried through so a later dataset
can say EXACT_DUPLICATE / NEAR_DUPLICATE / FUNCTIONALLY_EQUIVALENT / DIFFERENT
without changing the file format: `label` stays the binary target, `relation`
is the finer name when a source has one.

Held-out groups: `generate_pairs` can keep a fraction of *articles* (not rows)
out of training entirely, so validation and evaluation measure generalisation
to materials the model never saw, not memorisation of the ones it did.
"""

from __future__ import annotations

import csv
import random
import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.logic.extraction import expand_abbreviations
from app.logic.identity import assign_material_ids
from app.logic.query import preprocess
from app.logic.standard_format import RowFormatError, parse_row
from app.logic.standardize import StandardMaterial, to_material
from app.services.reranker import candidate_text

__all__ = [
    "Pair",
    "PairSplit",
    "generate_pairs",
    "group_key",
    "load_corpus",
    "load_pairs",
    "split_groups",
    "write_pairs",
]

PAIR_COLUMNS = ("query_material", "candidate_material", "label")


@dataclass(frozen=True)
class Pair:
    query: str
    candidate: str
    label: int
    relation: str = ""
    """Finer-grained relationship when known. Empty for binary sources."""
    group: str = ""
    """The article the pair is about, for group-wise splits. Empty for CSV pairs."""
    source: str = ""


# --------------------------------------------------------------------------
# Reading and writing
# --------------------------------------------------------------------------

def load_pairs(path: str | Path, *, source: str | None = None) -> list[Pair]:
    """Read `query_material,candidate_material,label[,relation]`."""
    file = Path(path)
    out: list[Pair] = []
    with file.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in PAIR_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{file}: missing column(s) {missing}; expected {PAIR_COLUMNS}")
        for number, row in enumerate(reader, start=2):
            query = (row.get("query_material") or "").strip()
            candidate = (row.get("candidate_material") or "").strip()
            raw_label = (row.get("label") or "").strip()
            if not query or not candidate:
                continue
            if raw_label not in {"0", "1"}:
                raise ValueError(f"{file}:{number}: label must be 0 or 1, got {raw_label!r}")
            out.append(Pair(
                query=query, candidate=candidate, label=int(raw_label),
                relation=(row.get("relation") or "").strip(),
                group=(row.get("group") or "").strip(),
                source=source or file.name,
            ))
    return out


def write_pairs(pairs: Iterable[Pair], path: str | Path) -> int:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([*PAIR_COLUMNS, "relation", "group", "source"])
        for pair in pairs:
            writer.writerow([
                pair.query, pair.candidate, pair.label, pair.relation, pair.group, pair.source,
            ])
            count += 1
    return count


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------

def load_corpus(path: str | Path) -> list[StandardMaterial]:
    """A standard-format CSV (the eight canonical columns) -> materials.

    Goes through the same `parse_row` / `to_material` / `assign_material_ids`
    the service uses, so the ids and attributes here are the ones the master
    would hold for the same file. Unreadable rows are skipped, not fatal:
    training data is allowed to be imperfect, the master is not.
    """
    materials: list[StandardMaterial] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=1):
            try:
                materials.append(to_material(parse_row(row, number)))
            except RowFormatError:
                continue
    assign_material_ids(materials)
    return materials


_NOISE = re.compile(
    r"\s*(?:-\s*URGENT\s+REQ|\*\*OEM\s+ONLY\*\*|\(BOQ\d*\s+REF\)|REQ\s+AS\s+PER\s+ATTACHED\s+SPEC)\s*$",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def group_key(description: str) -> str:
    """Which article a description is about, for the purpose of labelling.

    Procurement noise stripped, abbreviations expanded, case and punctuation
    folded - so `V BELT C-120 - URGENT REQ` and `v belt c-120 **OEM ONLY**`
    are one article. Two genuinely different descriptions of one article
    (`BELT V C-120` and `V-BELT SEC C, NOM L 120 INCH`) are NOT merged by
    this: that knowledge is a person's, and it belongs in the seed pairs.
    """
    text = _NOISE.sub("", description or "")
    text = expand_abbreviations(text.upper())
    return _NON_ALNUM.sub(" ", text.lower()).strip()


def _numbers(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"\d+(?:\.\d+)?", text))


def _negatives_allowed(a: str, b: str) -> bool:
    """May two different groups be labelled DIFFERENT with confidence?

    Not when one's numbers are a subset of the other's: `BALL BEARING 6205`
    against `BEARING BALL RADIAL 6205 2RS` may well be the same article, and a
    generated label that says otherwise would teach the model the wrong
    thing. Such pairs are simply not generated; a person can add them to the
    seed file with the label they deserve.
    """
    na, nb = _numbers(a), _numbers(b)
    if not na and not nb:
        return True
    return not (na <= nb or nb <= na)


# --------------------------------------------------------------------------
# Augmentation
# --------------------------------------------------------------------------

#: Expansions a user may well type in the short form. The reverse of the
#: abbreviation table, for the entries that are unambiguous in reverse.
_CONTRACTIONS = [
    ("BEARING", "BRG"), ("VALVE", "VLV"), ("STAINLESS STEEL", "SS"),
    ("MILD STEEL", "MS"), ("CARBON STEEL", "CS"), ("HYDRAULIC", "HYD"),
    ("GASKET", "GSKT"), ("FLANGE", "FLG"), ("HEXAGONAL", "HEX"),
    ("NOMINAL BORE", "NB"), ("DIAMETER", "DIA"), ("THICKNESS", "THK"),
    ("SECTION", "SEC"), ("RADIAL", "RAD"), ("TAPER", "TPR"),
    ("SPHERICAL", "SPHR"), ("GALVANIZED", "GALV"), ("LUBRICATING", "LUB"),
    ("ELECTRODE", "ELECT"), ("ASSEMBLY", "ASSY"), ("HIGH TENSILE", "HT"),
    ("PRESSURE", "PR"), ("CYLINDER", "CYL"), ("TRANSFORMER", "TRF"),
    ("SUBMERSIBLE", "SUBM"), ("INDUSTRIAL", "IND"), ("STANDARD", "STD"),
]

_SENTENCES = [
    "I NEED A {}", "LOOKING FOR {}", "REQUIRED {} URGENTLY", "{} FOR PLANT MAINTENANCE",
    "PLEASE FIND {}", "SPARE {} FOR STORES", "{} AS PER ATTACHED SPEC", "{} SUPPLY AND DELIVERY",
    "SEARCH {}", "ITEM {}", "MATERIAL {}", "{} QTY 10 NOS", "DO WE HAVE {}", "IS THERE A {}",
    "{} FOR CRUSHER DRIVE", "{} FOR CONVEYOR", "SOMETHING LIKE {}", "{} OR EQUIVALENT",
]

#: The name and the parameters, separated by the words people put between
#: them: "A BELT THAT IS C-120", "BEARING OF SIZE 6205". `{0}` is the name
#: (the words before the first number), `{1}` the rest.
_SPLIT_TEMPLATES = [
    "A {0} THAT IS {1}", "{0} WHICH IS {1}", "{0} OF SIZE {1}", "{0} TYPE {1}",
    "{0} MODEL {1}", "{1} {0}", "{0} - {1}", "{0}, {1}", "WHICH {0} IS {1}", "{0} SPEC {1}",
]

#: Things nobody would look for in a CPSE material master. A negative against
#: a random corpus row for every row, so "different domain" scores near zero
#: rather than wherever a general encoder happens to put it.
_UNRELATED = [
    "OFFICE CHAIR REVOLVING", "PRINTER TONER CARTRIDGE", "SOME COMPLETELY UNRELATED MATERIAL",
    "A4 COPIER PAPER 75 GSM", "WALL CLOCK QUARTZ", "TEA BAGS 100 PACK", "DESKTOP COMPUTER I5",
    "COTTON BED SHEET DOUBLE", "LIQUID HAND WASH 5 LTR", "WHITEBOARD MARKER BLUE",
    "STEEL ALMIRAH 6 FEET", "VISITOR REGISTER 200 PAGES", "CEILING FAN 1200MM",
    "MOBILE PHONE CHARGER TYPE C", "PLASTIC DUSTBIN 60 LTR", "CANTEEN DINNER PLATE STEEL",
    "STAPLER PINS 24/6", "GARDEN HOSE PIPE 1/2 INCH 30 M", "FIRST AID KIT BOX",
    "LAPTOP BAG 15 INCH", "TABLE LAMP LED 5W", "NOTEBOOK 200 PAGES RULED",
]

_CODE = re.compile(r"\b([A-Z]{1,3})-?(\d{2,6})([A-Z]{0,3})\b")
_DIGIT_RUN = re.compile(r"\d+")


def _code_variants(text: str, rng: random.Random) -> list[str]:
    """`C-120` -> `C120`, `C 120`; `6205-2RS` -> `6205 2RS`, `62052RS`."""
    out: set[str] = set()
    if "-" in text:
        out.add(text.replace("-", ""))
        out.add(text.replace("-", " "))
    for match in _CODE.finditer(text):
        letters, digits, tail = match.groups()
        forms = (
            f"{letters}{digits}{tail}", f"{letters} {digits}{tail}", f"{letters}-{digits}{tail}",
        )
        for form in forms:
            if form != match.group(0):
                out.add(text[: match.start()] + form + text[match.end():])
    if " X " in text:
        out.add(text.replace(" X ", "X"))
    if "MM" in text:
        out.add(re.sub(r"(\d)MM", r"\1 MM", text))
    out.discard(text)
    variants = sorted(out)
    rng.shuffle(variants)
    return variants[:2]


def _contract(text: str, rng: random.Random) -> str | None:
    present = [(long, short) for long, short in _CONTRACTIONS if long in text]
    if not present:
        return None
    long, short = rng.choice(present)
    return text.replace(long, short, 1)


def _drop_token(text: str, rng: random.Random) -> str | None:
    tokens = text.split()
    droppable = [i for i, t in enumerate(tokens) if not any(ch.isdigit() for ch in t)]
    if len(tokens) < 4 or not droppable:
        return None
    del tokens[rng.choice(droppable)]
    return " ".join(tokens)


def _swap_order(text: str) -> str | None:
    tokens = text.split()
    if len(tokens) < 3:
        return None
    tokens[0], tokens[1] = tokens[1], tokens[0]
    return " ".join(tokens)


def _name_only(text: str) -> str | None:
    """The leading words before the first number: `TAPER ROLLER BEARING`."""
    tokens = text.split()
    head: list[str] = []
    for index, token in enumerate(tokens):
        if any(ch.isdigit() for ch in token):
            break
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if len(token) == 1 and following[:1].isdigit():
            break  # `C` in `V BELT C 120` is a size class, not part of the name
        head.append(token)
    if 2 <= len(head) < len(tokens):
        return " ".join(head)
    return None


_LETTER_CODE = re.compile(r"(?<![A-Z])([A-Z])(?=-?\d)|(?<![A-Z0-9])([A-WYZ])(?![A-Z0-9])")


_SPEC_UNITS = {
    "INCH", "IN", "MM", "CM", "M", "MTR", "METERS", "KG", "KGS", "POLE", "POLES",
    "AMP", "AMPERE", "AMPS", "A", "V", "VOLT", "VOLTS", "KV", "W", "KW", "HP",
    "HZ", "BAR", "PSI", "NB", "OD", "ID", "R2", "R1", "GRADE", "DEG", "LTR",
    "LINKS", "NOS", "WOG", "PTFE", "SEAT", "SS316", "SS304", "DIA", "PHASE", "SECTION",
    "C", "CURVE", "CLASS", "THK", "A105",
}


def _keep_leading_numbers(text: str, rng: random.Random) -> str | None:
    """`TAPER ROLLER BEARING 32218 J2/Q` -> `TAPER ROLLER BEARING 32218`;
    `MCB 4 POLE 63 AMPERE C CURVE 10KA` -> `MCB 4 POLE 63 AMPERE`. A query that
    carries the identifying number and drops the trailing extras is the same
    article. Unlike a name-only query, the number is there and it agrees."""
    tokens = text.split()
    numeric = [i for i, t in enumerate(tokens) if any(ch.isdigit() for ch in t)]
    if not numeric:
        return None
    cut = rng.choice(numeric[:2]) + 1
    filtered = []
    for idx in numeric:
        tok = tokens[idx].upper().rstrip("#,")
        if re.match(r"^[A-Z]\d+/[A-Z]$", tok) or tok in {"2RS", "10KA", "C3"}:
            continue
        filtered.append(idx)
    if not filtered:
        filtered = numeric

    if len(filtered) >= 2 and filtered[1] - filtered[0] <= 3:
        target = rng.choice([filtered[0], filtered[1]]) if rng.random() < 0.5 else filtered[1]
    else:
        target = filtered[0]

    cut = target + 1
    while cut < len(tokens):
        tok_clean = tokens[cut].upper().rstrip("#,")
        if tok_clean in _SPEC_UNITS or tok_clean.startswith("R2"):
            cut += 1
        else:
            break

    if cut >= len(tokens):
        return None
    return " ".join(tokens[:cut])
    res = " ".join(tokens[:cut]).rstrip(" xX-")
    if len(res.split()) < 3:
        return None
    return res


def _drop_qualifier(text: str) -> str | None:
    """`V BELT C 120` -> `BELT C 120`; `TAPER ROLLER BEARING 32218` -> `ROLLER
    BEARING 32218`. People search by the family noun and the number; the
    model must not depend on the first word being there."""
    tokens = text.split()
    head = _name_only(text)
    if head is None or len(head.split()) < 2:
        return None
    return " ".join(tokens[1:])


def _split_phrase(text: str, rng: random.Random) -> str | None:
    """The name and the parameters with a connective between them."""
    head = _name_only(text)
    if head is None:
        return None
    tail = text[len(head):].strip(" ,-")
    if not tail:
        return None
    return rng.choice(_SPLIT_TEMPLATES).format(head, tail)


def _perturb_number(text: str, rng: random.Random) -> str | None:
    """A different article: one number changed. `6205` -> `6206`, `120` -> `125`.

    Three kinds of change, because a model that only ever saw `+1` learns
    only `+1`: the whole value moved up or down, a single digit swapped in
    place (`6205` -> `6305`, `7018` -> `6018`), and a value halved or
    doubled. All are things a neighbouring catalogue entry actually looks
    like.
    """
    runs = list(_DIGIT_RUN.finditer(text))
    if not runs:
        return None
    match = rng.choice(runs)
    digits = match.group(0)
    value = int(digits)
    kind = rng.random()
    if kind < 0.4:
        delta = rng.choice([1, 2, 4, 5, 10, 25, 50, 100])
        new = value + delta if rng.random() < 0.5 or value - delta < 1 else value - delta
        replacement = str(new).zfill(len(digits)) if digits.startswith("0") else str(new)
    elif kind < 0.8 and len(digits) >= 2:
        position = rng.randrange(len(digits))
        original = digits[position]
        options = [d for d in "0123456789" if d != original and not (position == 0 and d == "0")]
        replacement = digits[:position] + rng.choice(options) + digits[position + 1 :]
    else:
        new = max(1, value * 2 if rng.random() < 0.5 else value // 2)
        replacement = str(new) if new != value else str(value + 1)
    if replacement == digits:
        return None
    return text[: match.start()] + replacement + text[match.end():]


def _perturb_letter(text: str, rng: random.Random) -> str | None:
    """A different article: one letter code changed. `C 120` -> `B 120`,
    `M24` -> `M20` is a number; `M24` -> `N24`, `R2` -> `R1` is a letter or
    a size class. Standalone letters and letter prefixes of codes only, so a
    word is never turned into a misspelling."""
    matches = [m for m in _LETTER_CODE.finditer(text)]
    if not matches:
        return None
    match = rng.choice(matches)
    letter = match.group(0)
    neighbours = [c for c in "ABCDEFGHJKLMNPRSTVXZ" if c != letter]
    replacement = rng.choice(neighbours)
    return text[: match.start()] + replacement + text[match.end():]


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

@dataclass
class PairSplit:
    train: list[Pair] = field(default_factory=list)
    validation: list[Pair] = field(default_factory=list)
    held_out_groups: list[str] = field(default_factory=list)
    groups: int = 0


def split_groups(
    groups: Sequence[str], *, holdout_fraction: float, seed: int
) -> tuple[list[str], list[str]]:
    """Articles, not rows, go to one side or the other."""
    keys = sorted(set(groups))
    rng = random.Random(seed)
    rng.shuffle(keys)
    held = max(0, int(round(len(keys) * holdout_fraction)))
    if holdout_fraction > 0 and len(keys) >= 2:
        held = max(1, held)
    return keys[held:], keys[:held]


def _candidate(material: StandardMaterial) -> str:
    """The candidate side exactly as the reranker will see a stored row."""
    return candidate_text(material)


def generate_pairs(
    materials: Sequence[StandardMaterial],
    *,
    seed: int = 7,
    holdout_fraction: float = 0.25,
    positives_per_row: int = 6,
    negatives_per_row: int = 7,
    hard_negatives_per_row: int = 3,
) -> PairSplit:
    """Labelled pairs from a corpus, split by article.

    For every row: positives are augmented spellings of its own description
    against its own candidate text, and other rows of the same article
    against it; negatives are its number- and letter-perturbed twins (hard:
    `hard_negatives_per_row` of them plus one letter change), then rows from
    other articles that the number rule allows, up to `negatives_per_row`.
    """
    rng = random.Random(seed)
    by_group: dict[str, list[StandardMaterial]] = defaultdict(list)
    for material in materials:
        by_group[group_key(material.description)].append(material)

    train_groups, held_groups = split_groups(
        list(by_group), holdout_fraction=holdout_fraction, seed=seed
    )
    held = set(held_groups)
    split = PairSplit(held_out_groups=sorted(held), groups=len(by_group))
    group_list = list(by_group)

    for group, rows in by_group.items():
        target = split.validation if group in held else split.train
        for material in rows:
            query_base = preprocess(material.description)
            cand = _candidate(material)

            # --- positives -------------------------------------------
            variants: list[str] = [query_base]
            variants += _code_variants(query_base, rng)
            short_clean = _keep_leading_numbers(query_base, rng)
            if short_clean:
                variants.append(short_clean)
                dropped_short = _drop_qualifier(short_clean)
                if dropped_short:
                    variants.append(dropped_short)
                split_short = _split_phrase(short_clean, rng)
                if split_short:
                    variants.append(split_short)
            if material.part_number and not material.part_number.startswith("PN-"):
                pn = material.part_number
                lead = material.description.split()[0].replace("-", " ")
                cat_name = material.category.replace("_", " ")
                for form in (f"{lead} {pn}", f"{cat_name} {pn}", pn):
                    variants.append(form)
                    variants.extend(_code_variants(form, rng))
                    dropped_f = _drop_qualifier(form)
                    if dropped_f:
                        variants.append(dropped_f)
                    split_f = _split_phrase(form, rng)
                    if split_f:
                        variants.append(split_f)
            for maker in (_contract, _drop_token, _split_phrase, _keep_leading_numbers):
                made = maker(query_base, rng)
                if made:
                    variants.append(made)
            # Deliberately NOT `_name_only`: labelling `V BELT` a match for the
            # C-120 belt teaches the model that a missing number is fine, and
            # it then forgives a WRONG one too. A name-only query still ranks
            # the family first without that label - the family scores ~0.9
            # and everything else ~0 - and its level is decided by the
            # threshold, which is where "possible" belongs.
            for maker in (_swap_order, _drop_qualifier):
                made = maker(query_base)
                if made:
                    variants.append(made)
            variants.append(rng.choice(_SENTENCES).format(query_base))
            dropped = _drop_qualifier(query_base)
            if dropped:
                # The two failure modes seen in practice, together: no
                # qualifier AND a sentence around it.
                variants.append(rng.choice(_SENTENCES).format(dropped))
            rng.shuffle(variants)
            seen: set[str] = set()
            kept = 0
            for variant in variants:
                if variant in seen:
                    continue
                seen.add(variant)
                target.append(Pair(variant, cand, 1, "SAME_ARTICLE", group, "corpus"))
                kept += 1
                if kept >= positives_per_row:
                    break
            # Another row of the same article, when there is one.
            others = [r for r in rows if r is not material]
            if others:
                other = rng.choice(others)
                target.append(
                    Pair(query_base, _candidate(other), 1, "SAME_ARTICLE", group, "corpus")
                )

            # --- negatives -------------------------------------------
            negatives = 0
            hard: set[str] = set()
            sources_to_perturb = [query_base]
            if short_clean and short_clean != query_base:
                sources_to_perturb.append(short_clean)
            for v in variants:
                if len(v.split()) <= 4 and v not in sources_to_perturb:
                    sources_to_perturb.append(v)

            for _ in range(12):
                src = rng.choice(sources_to_perturb)
                perturbed = _perturb_number(src, rng)
                if perturbed and perturbed != src:
                    hard.add(perturbed)
                    for cv in _code_variants(perturbed, rng):
                        hard.add(cv)
                if len(hard) >= hard_negatives_per_row:
                    break

            src = rng.choice(sources_to_perturb)
            lettered = _perturb_letter(src, rng)
            if lettered and lettered != src:
                hard.add(lettered)
                for cv in _code_variants(lettered, rng):
                    hard.add(cv)
            for perturbed in sorted(hard):
                target.append(Pair(perturbed, cand, 0, "DIFFERENT_NUMBER", group, "corpus"))
                negatives += 1
            target.append(Pair(rng.choice(_UNRELATED), cand, 0, "UNRELATED", group, "corpus"))
            attempts = 0
            while negatives < negatives_per_row and attempts < 20:
                attempts += 1
                other_group = rng.choice(group_list)
                if other_group == group:
                    continue
                # Keep the split clean: a validation pair must not touch a
                # training article on either side, and vice versa.
                if (other_group in held) != (group in held):
                    continue
                if not _negatives_allowed(group, other_group):
                    continue
                other = rng.choice(by_group[other_group])
                target.append(Pair(query_base, _candidate(other), 0, "DIFFERENT", group, "corpus"))
                negatives += 1

    rng.shuffle(split.train)
    rng.shuffle(split.validation)
    return split
