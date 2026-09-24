# 03 · ML Architecture — `ai-service`

> ## ⚠ Superseded — the seven-stage pipeline described here has been removed
>
> `ai-service` was restructured on 2026-09-10. Phase 1 (raw CSV/XLSX/TXT →
> the eight canonical CPSE attributes) now belongs to the fine-tuned
> **Qwen2.5-3B + `qwen2.5-3b-cpse-lora-v2`** extractor, vendored into
> `ai-service` from `backend/pipeline-one`. Everything downstream of the
> standard format is the **vector embedding DB**: check what is new, add only
> that.
>
> **Removed:** `clean.py`, `tokenize.py`, `units.py`, `extract.py`, `ner.py`, `llm.py`, `validate.py`, `classify.py`, `classifier.py`, `quality.py`, `reference.py` and the typed-attribute / category / canonical-text data model. They duplicated, less well, work the LoRA extractor already does — on text it had already processed.
>
> Current design: [`backend/ai-service/README.md`](../backend/ai-service/README.md)
> · API: [`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md)
>
> This document is kept for the design reasoning behind the removed stack,
> which is worth reading before search is built on top of the index. **It does
> not describe code that exists.**

---

> Scope: everything inside `backend/ai-service` — how it is layered, how a raw
> CPSE description becomes comparable structure, and what is stored.
>
> This service is **complete and tested**. Phase 2 (the matching decision itself)
> is large enough to have its own documents:
> [04 Retrieval & the Matcher Interface](04_RETRIEVAL_AND_MATCHER_INTERFACE.md)
> and [05 Matching & Rule Engine](05_MATCHING_AND_RULE_ENGINE.md).

---

## Part A — The service

### 1. What it owns

| Owns                                  | Does not own                  |
| ------------------------------------- | ----------------------------- |
| Standardization of a raw material row | Authentication, authorization |
| Attribute extraction and roles        | CPSE isolation                |
| Data-quality flagging                 | National code issuance        |
| Blocking, comparison, scoring, rules  | Review workflow state         |
| Evaluation metrics                    | Anything a user logs in to    |

Everything in the second column belongs to `api-service`
— see [02](02_BACKEND_ARCHITECTURE.md). Keeping this service free of auth is what
lets it be exercised, benchmarked and replaced without touching governance.

### 2. Layers

```
app/routes/          1. HTTP. Parses, validates, delegates. No domain logic.
        ↓
app/schemas/         2. Pydantic DTOs. The wire contract, decoupled from the ORM.
        ↓
app/services/        3. Orchestration. Owns the transaction. No HTTP, no rules.
        ↓
app/models/          4. SQLAlchemy tables. Structure only, no behaviour.

app/logic/           The algorithms. Pure functions over dataclasses:
                       S1-S7   clean · tokenize · units · extract ·
                               ner · llm · validate · classifier ·
                               standardize
                       retrieval  embedding · retrieval · candidates
                       matching   compare · score · rules · fusion ·
                                  calibration · matcher · explain
                       shared     enums · reference · versions

app/config.py        Settings (.env) + logging.  Depends on nothing.
app/database.py      Engine, session factory, declarative Base.
app/auth.py          caller attribution for the audit trail. Enforces nothing.
```

The dependency arrow only points down, and `routes/X.py` maps one-to-one onto
`services/X.py`. `app/logic/enums.py` is the one module everything may import;
it holds the enums and `cap_relationship`, and imports nothing from the
application itself.

| Layer      | Must not                                                                  |
| ---------- | ------------------------------------------------------------------------- |
| `routes`   | Contain a threshold, a rule, or a scoring decision                        |
| `services` | Raise `HTTPException`, or read `Request`                                  |
| `logic`    | Touch a database session, or read a file outside `app/logic/reference.py` |
| `models`   | Contain validation, computed verdicts, or business methods                |

`logic/` is allowed one exception: `embedding.py` and `retrieval.py` reach out
to a model and a vector store. Both sit behind protocols with in-process
fallbacks, so every other module in `logic/` stays a pure function and the whole
package remains testable without a network.

The purity of `logic/` is what makes the 273 tests fast and
meaningful: they exercise real matching decisions with no I/O and no fixtures
beyond in-memory dataclasses.

### 3. Package map

```
app/
├── core/
│   ├── config.py         Settings (pydantic-settings, .env-backed)
│   ├── domain.py         AttributeRole · Relationship · RuleStatus
│   │                     ComparisonState · Severity · cap_relationship
│   └── logging.py
├── db/
│   ├── base.py           DeclarativeBase
│   └── session.py        async engine + AsyncSessionLocal + get_db
├── pipeline/                                              ── Part B
│   ├── config.py         loads data/config/*.csv into typed specs
│   ├── cleaning.py       noise removal, abbreviation expansion, UOM normalization
│   ├── classification.py 22 ordered keyword rules → 21 families
│   ├── extraction.py     regex-driven typed attributes with roles
│   └── standardize.py    RawMaterial → StandardizedMaterial
├── matching/                                              ── docs 04, 05
│   ├── comparison.py     per-attribute MATCH / CONFLICT / MISSING
│   ├── scoring.py        Matcher protocol + DeterministicMatcher
│   ├── rules.py          five hard rules, advisory flag, verdict ceiling
│   └── engine.py         block · match · cluster · _decide
├── quality/
│   └── checks.py         UOM, description, identity coverage, part number
├── evaluation/
│   ├── ground_truth.py   gold-pair construction and CSV round-trip
│   └── metrics.py        precision / recall / F1 per relationship
├── models/                                                ── Part C
│   ├── material.py       material · standardized_material ·
│   │                     material_attribute · quality_flag
│   ├── matching.py       match_result · review · audit_log
│   └── ingest.py         import_job · quarantine_row · import_session
├── services/
│   ├── ingest.py         read_raw · standardize_all · persist · export_jsonl
│   ├── import_preview.py preview · duplicate detection · selective confirm
│   ├── materials.py      list · get · delete (with Qdrant vector cleanup)
│   └── matching_service.py  run_matching · summarise
├── schemas/
│   ├── common.py         HealthResponse and shared envelopes
│   └── material.py       MaterialOut · MatchResponse · EvaluationResponse ·
│                         ImportPreviewResponse · ImportConfirmResponse …
└── api/
    ├── router.py         mounts route modules under /api/v1
    └── routes/
        ├── health.py     GET /health
        └── materials.py  preview, confirm, browse, delete, ingest
```

### 4. Configuration

`app/config.py` is a single `Settings` class read from the environment or
`.env`. Nothing else in the codebase reads `os.environ`.

| Setting                                                       | Default                                      | Meaning                                                                                                           |
| ------------------------------------------------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `port`                                                        | `8001`                                       | Distinct from `api-service`'s 8000                                                                                |
| `db_host` · `db_port` · `db_name` · `db_user` · `db_password` | `127.0.0.1` · `5432` · `numm_ai` · `sih` · — | Postgres connection, supplied as parts                                                                            |
| `db_ssl` · `db_sslmode`                                       | `false` · `prefer`                           | TLS. `db_sslmode` decides; `db_ssl=true` raises anything weaker to `require`                                      |
| `db_echo`                                                     | `false`                                      | Log every SQL statement                                                                                           |
| `database_url`                                                | unset                                        | Full SQLAlchemy URL. **Overrides the `DB_*` parts** — how the tests reach SQLite and how a hosted URL is supplied |
| `config_dir`                                                  | `data/config`                                | Where the domain CSVs live                                                                                        |
| `raw_dataset_path`                                            | `../pipeline-one/CPSE_SIH26099.csv`          | **Opened read-only**                                                                                              |
| `ground_truth_path`                                           | `data/ground_truth/pairs.csv`                | Gold labels                                                                                                       |
| `top_k`                                                       | `10`                                         | Candidates returned per query                                                                                     |
| `exact_threshold`                                             | `0.90`                                       | Score at or above → proposes `EXACT_DUPLICATE`                                                                    |
| `near_threshold`                                              | `0.72`                                       | → proposes `NEAR_DUPLICATE`                                                                                       |
| `functional_threshold`                                        | `0.55`                                       | → proposes `FUNCTIONALLY_EQUIVALENT`                                                                              |
| `max_unclassified_rate`                                       | `0.50`                                       | Fraction of unclassified rows above which an import job is flagged `OUT_OF_DOMAIN`                                |
| `tier3_min_confidence`                                        | `0.55`                                       | Minimum cosine similarity to assign a family via Tier-3 zero-shot embeddings                                      |

Thresholds are proposals only. The rule engine can lower any of them, and
frequently does — see [05](05_MATCHING_AND_RULE_ENGINE.md).

#### Domain configuration is data

Five CSVs under `data/config/` change system behaviour without a code change:

| File                      | Rows | Controls                                                                                                                                |
| ------------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `category_attributes.csv` | 89   | Which attributes exist per category, their **role**, value type, unit, and the regex that extracts them (covers 24 material categories) |
| `class_descriptors.csv`   | 24   | Textual descriptions per category family used by the Tier-3 zero-shot embedding classifier                                              |
| `abbreviations.csv`       | 37   | `BRG → BEARING`, scoped per category prefix                                                                                             |
| `uom_rules.csv`           | 22   | Which UOMs are plausible for a category                                                                                                 |
| `uom_normalization.csv`   | 24   | `EA`, `PC`, `PCS` → `NOS`                                                                                                               |

`app/logic/reference.py` loads these once (`@lru_cache`) into frozen dataclasses.
Abbreviations are sorted longest-first so `GT VLV` beats `VLV`; scope is matched
by category **prefix**, so a `BELT` scope covers both `BELT_V` and
`BELT_CONVEYOR`.

---

## Part B — Phase 1: raw text to structure

### 5. The chain

```
raw description   "brg ball rad 6205 2rs for main store"
        │
        │  clean()
        ▼
description_clean "BEARING BALL RAD 6205 2RS"
        │         removed: ["STORE_NOTE"]  (kept as a flag, not discarded)
        │
        │  classify()
        ▼
category          "BEARING"  confidence 0.95  method KEYWORD
        │
        │  expand_abbreviations(scoped to category)
        ▼
description_normalized  "BEARING BALL RADIAL 6205 2RS"
        │
        │  extract(category schema)
        ▼
attributes        bearing_number = 6205   IDENTITY_DEFINING
                  bearing_type   = BALL   IDENTITY_DEFINING
                  seal_type      = 2RS    DISCRIMINATING
        │
        │  _build_canonical()
        ▼
canonical_text    "BEARING: bearing_number=6205; bearing_type=BALL; seal_type=2RS"
```

Classification runs **before** abbreviation expansion, which is why the
classification patterns include raw abbreviations (`BRG`, `VLV`) alongside the
expanded forms. Expansion needs a category to scope itself; classification must
therefore work on unexpanded text. That is the one ordering constraint in the
pipeline.

### 6. Cleaning — `app/logic/clean.py`

Unicode NFKC, HTML entity repair (`&#x0d;`), non-breaking spaces, upper-case,
then five noise patterns applied repeatedly until the text stops changing:

| Code            | Matches                           |
| --------------- | --------------------------------- |
| `URGENT_FLAG`   | `- URGENT REQ` at end             |
| `OEM_FLAG`      | `** OEM ONLY **` at end           |
| `BOQ_REF`       | `(BOQ12 REF)` at end              |
| `ATTACHED_SPEC` | `REQ AS PER ATTACHED SPEC` at end |
| `STORE_NOTE`    | `FOR MAIN STORE` at end           |

`clean()` returns `(text, removed_labels)`. The labels become a
`DESCRIPTION_NOISE` quality flag carrying the **original** string, so nothing is
lost — the raw description is a separate column and is never written to.

#### Abbreviation expansion

37 entries in `abbreviations.csv`, each with a scope. Longest raw form first, so
`GT VLV` expands before `VLV` can steal the `VLV`. Scope is matched as a
**category prefix**: an entry scoped to `BELT` applies to both `BELT_V` and
`BELT_CONVEYOR`. Unscoped entries apply everywhere.

An entry stays scoped when its meaning is genuinely ambiguous. `CS` is carbon
steel in a pipe fitting and cast steel elsewhere; expanding it globally would
manufacture false agreement, so it fires only inside the category where it is
unambiguous.

Expansion is bounded by `(?<![A-Z0-9])…(?![A-Z0-9])` rather than `\b`, so `AMP`
inside `AMPHENOL` is left alone.

#### UOM normalization

24 mappings onto a controlled list. The canonical count unit is `NOS`, so `EA`,
`EACH`, `PC`, `PCS`, `UNIT` and `NO` all collapse to it; `KG` → `KGS`,
`TON` → `MT`, `L`/`LTRS` → `LTR`, `M`/`MTRS` → `MTR`. Each mapping also carries a
dimension (`COUNT`, `MASS`, `VOLUME`, `LENGTH`, `PACKAGING`). An unknown value
returns `(None, None)` and produces a `UOM_UNRECOGNISED` flag. It is never
guessed into the nearest match.

### 7. Classification — `app/logic/classify.py`

25 ordered regex rules producing 24 families plus `UNCLASSIFIED`. First match
wins, so specific families sit above generic ones:

```
BEARING · SAFETY_SHOE · SEAL · O_RING · FILTER · VALVE · FASTENER
BELT_CONVEYOR · BELT_V · CABLE · PIPE_FITTING · MOTOR · PUMP · LUBRICANT
WELDING · HOSE · LIGHTING · ELECTRICAL · INSTRUMENT · GAS · CHEMICAL
MACHINE_PART · ELECTRONICS_IT · SAFETY_PPE · HARDWARE_TOOL
```

Ordering carries real domain content:

- `SEAL KIT` and `MECHANICAL SEAL` must beat generic checks; `O_RING` is evaluated before generic `SEAL`.
- `WIRE ROPE` must beat `CABLE`.
- `BELT_CONVEYOR` must beat `BELT_V`, because `CONVEYOR BELT` also contains
  `BELT`. These were one category until a V-belt matched a conveyor belt; the
  split is why they no longer do.

**Coverage on `CPSE_SIH26099.csv`: 404/404 rows, 0 unclassified.** 21 of the 24
families appear; `MOTOR`, `ELECTRONICS_IT`, etc. are ready for external datasets.

When nothing matches at Tier 1, the pipeline falls back to:

1. **Tier 2 (Fine-tuned / FastText classifier)**: if trained.
2. **Tier 3 (Zero-shot embedding similarity)**: compares description embedding against `class_descriptors.csv`. If cosine similarity exceeds `tier3_min_confidence` (0.55), the family is assigned.
3. If all tiers abstain, `classify()` returns `UNCLASSIFIED` with confidence `0.0`. When `unclassified_rate` on an ingested file exceeds 50% (`MAX_UNCLASSIFIED_RATE`), the import job is flagged `OUT_OF_DOMAIN`.

### 8. Attribute extraction — `app/logic/extract.py`

Every attribute is defined by a row in `data/config/category_attributes.csv`:

```
category, attribute, role, why_it_matters, value_type, unit, extraction_pattern
```

89 rows across 24 categories with attribute schemas. The extractor takes the
first non-empty capture group of the first match, normalises whitespace,
upper-cases, and — for `enum` types — collapses separators so `V-BELT` and
`V BELT` are the same value.

`number` types are parsed, including fractions (`3/4` → `0.75`), mixed fractions (`1 1/2"` or `1-1/2 IN` → `1.5`), and decimal quantities. Measurement units are resolved dynamically from the matched text or the schema, and physical quantities (`mm`, `inch`, `bar`, `psi`, `kw`, `hp`, `ampere`, `volt`) are converted to canonical SI values. Pipe nominal bore (`2"`, `2 IN`, `50 NB`, `DN50`, `50 MM`) resolves to canonical nominal millimeters. A numeric attribute whose value will not parse is dropped rather than stored as text.

Each extracted attribute carries `name`, `value`, `role`, `unit`,
`numeric_value`, `si_value`, `method`, `confidence` and `source_span`. The span is what makes
an extraction auditable: you can point at the characters it came from. Attribute comparison
in `app/logic/compare.py` uses SI dimension comparison first to avoid false conflicts between
differing unit notations.

#### Patterns are fragile, and that is visible

Three failures found during development, each fixed in the CSV rather than in
Python:

| Symptom                          | Cause                              | Fix                                                |
| -------------------------------- | ---------------------------------- | -------------------------------------------------- |
| `current_rating` never extracted | `AMP → AMPERE` expansion ran first | pattern became `(?:AMPERE\|AMP\|A)\b`              |
| `M16X65MM` gave no `thread_size` | no boundary after the digits       | `\bM\s?(\d{1,2})(?=[X\s]\|$)`                      |
| CSV failed to parse              | a regex containing `{4,5}`         | regenerate with `csv.writer` so quoting is correct |

### 9. Roles — the part that matters most

```python
class AttributeRole(StrEnum):
    IDENTITY_DEFINING = "IDENTITY_DEFINING"   # different value → different article
    DISCRIMINATING    = "DISCRIMINATING"      # different value → engineer decides
    DESCRIPTIVE       = "DESCRIPTIVE"         # different value → irrelevant
```

| Role                | Example                                         | Effect on a conflict                                  |
| ------------------- | ----------------------------------------------- | ----------------------------------------------------- |
| `IDENTITY_DEFINING` | `bearing_number`, `nominal_size`, `thread_size` | Pair rejected outright                                |
| `DISCRIMINATING`    | `seal_type`, `grade`, `pressure_class`          | Capped at `FUNCTIONALLY_EQUIVALENT`, routed to review |
| `DESCRIPTIVE`       | `colour`, `packaging`, `finish`                 | Ignored                                               |

The role assignment is a **domain judgement, not a technical one**, which is
exactly why it lives in a CSV a materials engineer can edit. The 60 current
assignments were made from the dataset and are **flagged for domain review** —
they are the single most valuable thing an expert can correct, because every
downstream verdict follows from them.

`missing_identity_attributes()` reports identity attributes the category schema
expects but extraction did not find. That list is what lets the matcher tell
_not stated_ from _different_.

### 10. Data quality — `app/logic/quality.py`

Findings are recorded; **nothing is corrected**. Every flag keeps `raw_value`.

| Code                         | Severity | Fires when                                            |
| ---------------------------- | -------- | ----------------------------------------------------- |
| `UOM_UNRECOGNISED`           | WARNING  | UOM not in the controlled list                        |
| `UOM_MISMATCH`               | WARNING  | UOM not plausible for the category                    |
| `DESCRIPTION_NOISE`          | INFO     | Procurement noise was stripped                        |
| `IRREGULAR_SPACING`          | INFO     | Repeated whitespace in the raw description            |
| `DESCRIPTION_TOO_SHORT`      | WARNING  | Cleaned text under 10 characters                      |
| `MISSING_IDENTITY_ATTRIBUTE` | WARNING  | Category expects an identity attribute that is absent |
| `PART_NUMBER_ABSENT`         | INFO     | No OEM part number, or a placeholder                  |

On the full 404-row extract:

```
UOM_MISMATCH                286
DESCRIPTION_NOISE           162
IRREGULAR_SPACING           161
PART_NUMBER_ABSENT          101
MISSING_IDENTITY_ATTRIBUTE   88
```

The worked example: a `SAFETY SHOE` issued in `KGS`. The correct unit is
obviously `PAIR`. The system does **not** change it. It records
`UOM_MISMATCH` with `raw_value="KGS"` and the note that `PAIR` is expected, and
leaves the decision to a human. Silently rewriting source data destroys the
audit trail and hides the underlying master-data problem, which is the thing the
CPSE actually needs to fix.

That 286 is not a bug in the checks. It is the dataset telling the truth about
itself, and it is why the UOM rule in Phase 2 is advisory only —
see [05 §4](05_MATCHING_AND_RULE_ENGINE.md).

### 10a. Two ways in

There are two ingest paths, and they differ in exactly one respect: **what they
delete**.

|            | `POST /materials/ingest`                        | `POST /ingest/by-reference`                                  |
| ---------- | ----------------------------------------------- | ------------------------------------------------------------ |
| Source     | `RAW_DATASET_PATH` on ai-service's own disk     | a file `api-service` stored in `UPLOAD_DIR`                  |
| Body       | none                                            | `{source, mode, original_filename, requested_by}`            |
| Deletes    | **every** material                              | `merge`: only the CPSEs in this file · `replace`: everything |
| Bad rows   | raises on a missing column; no row-level report | quarantined with row number, column and raw value            |
| Provenance | one `audit_log` row                             | an `import_job` row: sha256, counts, duration, CPSEs touched |
| Use        | development, demos, the fixed 404-row corpus    | real per-CPSE uploads                                        |

The legacy endpoint is kept deliberately. It is the fastest way to reload the
demo corpus, and nothing about the new path replaces that.

**Why `merge` exists.** `persist(replace=True)` wipes all four material tables.
With one hard-coded CSV that is correct; with real uploads it means CPSE-B's
file destroys CPSE-A's materials. `merge` narrows the blast radius to the CPSEs
actually present in the file being imported, which also makes re-uploading the
same CPSE idempotent rather than additive.

**Why by reference and not multipart.** `api-service` is where the user is
known, so the upload, its provenance and its access control belong there.
Sending the bytes on to ai-service would duplicate that responsibility and give
a file store to a service whose job is arithmetic. ai-service receives a name,
resolves it against `UPLOAD_DIR`, and refuses anything outside — see
[06 §27](06_API_SPECIFICATION.md).

---

### 10b. Two-Stage Interactive Ingestion & Lifecycle Management

Real enterprise master-data governance requires interactive review: inspecting incoming files before committing rows, detecting intra-batch duplicates, identifying existing database duplicates, and allowing reviewers to selectively confirm rows.

```
Incoming CSV (multipart / text / JSON)
        │
        ▼
POST /materials/import/preview
        ├─ 1. Header resolution (supports 8-column SIH schema + alias-mapped CSVs)
        ├─ 2. Standardization (cleaning, family classification, attribute extraction)
        ├─ 3. In-File Duplicate Detection (flags repeated rows within upload)
        ├─ 4. DB Duplicate Detection (scores candidates against existing materials)
        └─ 5. Non-destructive staging in import_sessions (24h TTL, 0 DB/Qdrant writes)
        │
        ▼
User Reviews Preview (toggles selections for duplicates & fresh items)
        │
        ▼
POST /materials/import/confirm
        ├─ 1. Validate session_id (active, unexpired, status=PENDING)
        ├─ 2. Filter rows by selected_rows
        ├─ 3. Persist chosen rows into materials, attributes, quality_flags
        ├─ 4. Compute embeddings & index directly into Qdrant vector store
        ├─ 5. Append-only audit log (action: IMPORT_CONFIRM)
        └─ 6. Mark session status = APPLIED
```

#### Duplicate Detection in Preview

1. **Intra-batch duplicates (`EXACT_DUPLICATE_IN_FILE`)**: When multiple rows in the same uploaded CSV share identical canonical texts, the first occurrence is treated as the primary row, while subsequent occurrences are flagged as `EXACT_DUPLICATE_IN_FILE`, pointing back to `duplicate_of_row` and deselected by default (`selected = False`).
2. **Database duplicates (`EXACT_DUPLICATE`, `NEAR_DUPLICATE`, `FUNCTIONALLY_EQUIVALENT`)**: Unique candidate rows are compared against existing database materials using the matching pipeline. Matches meeting threshold or rule criteria are tagged with `existing_material_id`, `match_reason`, and `confidence_score`, and deselected by default.
3. **Fresh items (`NEW`)**: Rows with neither in-file nor database collisions are marked `NEW` and pre-selected (`selected = True`).
4. **Invalid rows (`INVALID`)**: Rows missing vital identifiers or failing core parsing are marked `INVALID` with `error_message` and deselected.

#### Material Deletion with Vector Cleanup (`DELETE /materials/{material_id}`)

When an obsolete, incorrect, or duplicate material is deleted:

1. **Relational Cascades**: Deletes child rows in `material_attributes` and `quality_flags`.
2. **Graph Dependency Cleanup**: Removes associated rows in `match_results` and `reviews` where the material appears as either query or target, preventing foreign-key violations.
3. **Vector Store Synchronization**: Generates the material's deterministic UUIDv5 point ID (`generate_material_point_id(material_id)`) and deletes the corresponding vector from Qdrant.
4. **Audit Trail**: Appends a row to `audit_log` with action `MATERIAL_DELETED`.

---

### 11. What the numbers mean, and what they do not

Models **are** trained (`make train`): a linear classifier over embeddings, a
spaCy NER, fusion weights and an isotonic calibration curve. What is still
missing is _independent_ supervision, and that changes how every figure should
be read.

| Number                 | What it is                                                                                   | What it is not                                    |
| ---------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `category_confidence`  | `0.95` on a keyword hit, the model's probability on tiers 2-3, `0.0` on abstention           | a calibrated posterior on tier 1                  |
| attribute `confidence` | a constant per method: `0.9` regex/dict, `0.62` NER, `0.45` LLM, `0.9` inferred              | a learned per-value probability                   |
| match score            | `heuristic_confidence`, `learned_confidence` or `calibrated_probability` — `kind` says which | independently validated in any of the three cases |

**The one caveat that matters.** `data/ground_truth/pairs.csv` was derived from
the same extracted attributes the matcher compares, so fitting on it produced a
cross-validated F1 of 1.000 and an ECE of 0.000. Those are the signatures of
circularity, not of quality: the model learned to reproduce the heuristic. The
machinery is real and tested; the _numbers_ become meaningful only once a domain
expert labels pairs independently, including hard negatives. `scripts/train_fusion.py`
prints this warning on every run so it cannot be quietly forgotten.

Two measured findings in the same spirit, both reproducible:

- **ANN retrieval recovers 0 additional matches** on this 404-material corpus
  (`make ablation`). Category blocking is already exhaustive at this scale.
- **The UOM gate runs advisory** because 0% of attribute-identical groups in
  this corpus share a unit. Bearing `6205` appears as NOS, MT, MTR, BTL and SET.

Claiming otherwise would be the easiest way to make this system look better and
the fastest way to make it indefensible. When a labelled set exists, the
`Matcher` protocol is where a trained model attaches — the rules, the ranking,
the API and the explanation format do not change.

Phase 1 over 404 rows is well under a second on one CPU core: five regex
substitutions, one classification scan, up to a few dozen extraction patterns
per row. There is nothing to batch, nothing to load into memory and no warm-up.

---

## Part C — What is stored

### 12. The two invariants

**I1 — The raw row is written once and never updated.**
`material` holds exactly what the CPSE supplied. Standardization writes to
`standardized_material` and its children. Re-ingesting replaces derived rows; it
does not edit source rows. A CPSE can always be shown the string it sent.

**I2 — Corrections are flags, not edits.**
Every data-quality finding is a row in `quality_flag` carrying `raw_value`.
Nothing in the pipeline rewrites a supplied value. A wrong UOM stays wrong in the
data and becomes visible in the report.

Everything below follows from those two.

### 13. Schema

```
material  (raw, immutable)
    │ 1:1
standardized_material
    ├── 1:N  material_attribute
    └── 1:N  quality_flag

match_result
    └── 1:N  review

audit_log   (append-only, unlinked)
```

Seven tables. All primary keys are UUID strings, so rows can be generated
without a round-trip and merged across environments.

### 14. `material` — the raw row

| Column               | Type                             | Notes                                     |
| -------------------- | -------------------------------- | ----------------------------------------- |
| `id`                 | `String(36)` PK                  | UUID                                      |
| `material_id`        | `String(32)` **unique, indexed** | `{CPSE}-{source_row:06d}`                 |
| `source_row`         | `Integer`                        | 1-based line in the source CSV            |
| `cpse_code`          | `String(16)` indexed             | `NTPC`, `IOCL`, `CCL`, …                  |
| `cpse_name`          | `String(120)`                    | Company string as supplied                |
| `legacy_code`        | `String(64)` indexed             | **Not unique** — see below                |
| `description_raw`    | `Text`                           | Verbatim                                  |
| `uom_raw`            | `String(24)`                     | Verbatim                                  |
| `quantity`           | `Float`                          | `NULL` when unparseable                   |
| `part_number_raw`    | `String(80)`                     | Verbatim                                  |
| `manufacturer_raw`   | `String(80)`                     | Verbatim                                  |
| `specifications_raw` | `Text`                           | Verbatim, currently unused for extraction |
| `created_at`         | `DateTime`                       | Server default                            |

#### Why `material_id` is not the legacy code

Legacy code `116045321` appears twice in this dataset, used by Coal India (CCL)
for **two different bearings**. Making it the primary identifier would silently
merge two distinct articles before matching ever ran.

`material_id = f"{cpse_code}-{source_row:06d}"` is therefore derived from
provenance, not content: it is stable across re-ingests of the same file,
unique by construction, and readable (`CCL-000173`). `legacy_code` is indexed
but carries no uniqueness constraint, because the source data does not support
one.

`cpse_code_for()` maps known company strings through `CPSE_CODES` and falls back
to the first six letters of the upper-cased name, so an unrecognised CPSE
degrades to something readable rather than failing.

### 15. `standardized_material` — the derived row

| Column                   | Type                                | Notes                                |
| ------------------------ | ----------------------------------- | ------------------------------------ |
| `id`                     | `String(36)` PK                     |                                      |
| `material_id`            | FK → `material.material_id`, unique | 1:1                                  |
| `description_clean`      | `Text`                              | Noise removed                        |
| `description_normalized` | `Text`                              | Abbreviations expanded               |
| `canonical_text`         | `Text`                              | `CATEGORY: attr=value; attr=value`   |
| `category`               | `String(32)` indexed                | Blocking key                         |
| `category_confidence`    | `Float`                             | `0.95` keyword / `0.0` abstain       |
| `category_method`        | `String(16)`                        | `KEYWORD` / `ABSTAIN`                |
| `uom_normalized`         | `String(12)`                        | `NULL` if unrecognised               |
| `uom_dimension`          | `String(24)`                        | `COUNT`, `MASS`, `LENGTH`, …         |
| `missing_identity`       | `Text`                              | Comma-joined names, drives `MISSING` |
| `pipeline_version`       | `String(24)`                        | `pipeline-v1`                        |

`canonical_text` is attribute-ordered rather than word-ordered, so two CPSEs
writing the same bearing in different word order collapse to the same string.
It is a human-readable summary, not a matching key — matching compares the
attributes themselves.

`category` is indexed because it is the blocking key. Every candidate query
filters on it.

### 16. `material_attribute`

| Column            | Type                 | Notes                                      |
| ----------------- | -------------------- | ------------------------------------------ |
| `id`              | `String(36)` PK      |                                            |
| `standardized_id` | FK indexed           |                                            |
| `name`            | `String(48)`         | `bearing_number`, `nominal_size`           |
| `value`           | `String(160)`        | Normalised, upper-case                     |
| `numeric_value`   | `Float`              | Set for `number` types, fractions resolved |
| `unit`            | `String(16)`         | From the category schema                   |
| `role`            | `String(24)` indexed | The three-way role                         |
| `method`          | `String(16)`         | `REGEX`                                    |
| `confidence`      | `Float`              | `0.9` for a regex hit                      |

```sql
UNIQUE (standardized_id, name)        -- uq_attribute_per_material
INDEX  (name, value)                  -- ix_attribute_lookup
```

The unique constraint enforces one value per attribute per material — extraction
takes the first match, and storing a second would make comparison ambiguous.
`ix_attribute_lookup` supports the "which other materials state
`bearing_number=6205`?" query.

`role` is denormalised onto the row rather than joined from config at read time.
Config can change; a stored decision must remain explicable against the roles
that were in force when it was made.

### 17. `quality_flag`

| Column            | Type                 | Notes                               |
| ----------------- | -------------------- | ----------------------------------- |
| `id`              | `String(36)` PK      |                                     |
| `standardized_id` | FK indexed           |                                     |
| `code`            | `String(40)` indexed | `UOM_MISMATCH`, …                   |
| `severity`        | `String(12)`         | `INFO` / `WARNING` / `ERROR`        |
| `field`           | `String(32)`         | Which raw field is implicated       |
| `detail`          | `Text`               | Sentence a reviewer reads           |
| `raw_value`       | `Text`               | **The original value, always kept** |

`raw_value` is the enforcement of invariant I2. A `SAFETY SHOE` issued in `KGS`
produces a row with `raw_value = "KGS"` and a detail explaining that `PAIR` is
expected. The `uom_raw` column on `material` still says `KGS`. Nothing anywhere
says `PAIR`.

### 18. `match_result`

| Column                   | Type                 | Notes                                     |
| ------------------------ | -------------------- | ----------------------------------------- |
| `id`                     | `String(36)` PK      |                                           |
| `query_material_id`      | `String(32)` indexed |                                           |
| `candidate_material_id`  | `String(32)` indexed |                                           |
| `confidence_score`       | `Float`              | 0–1                                       |
| `confidence_kind`        | `String(32)`         | `heuristic_confidence`                    |
| `relationship_type`      | `String(32)` indexed | The final verdict                         |
| `hard_rule_status`       | `String(12)`         | `PASS` / `REVIEW` / `REJECT`              |
| `proposed_before_rules`  | `String(32)`         | What the score alone said                 |
| `reason`                 | `Text`               | One sentence naming the deciding evidence |
| `matched_attributes`     | `Text` JSON          | `["bearing_number", …]`                   |
| `conflicting_attributes` | `Text` JSON          | `[{name, role, left, right}, …]`          |
| `missing_attributes`     | `Text` JSON          |                                           |
| `rules_triggered`        | `Text` JSON          | Rule names                                |
| `matcher_version`        | `String(32)`         | `deterministic-v1`                        |
| `rule_version`           | `String(32)`         | `rules-v1`                                |
| `pipeline_version`       | `String(32)`         | `pipeline-v1`                             |
| `created_at`             | `DateTime`           |                                           |

```sql
INDEX (query_material_id, confidence_score)   -- ix_match_query
```

#### Why `confidence_kind` is a column

It would be trivial to call every number a probability. Three different things
can write to `confidence_score`, and they make three different claims:

| `confidence_kind`        | Means                                        |
| ------------------------ | -------------------------------------------- |
| `heuristic_confidence`   | a weighted sum under weights a person chose  |
| `learned_confidence`     | logistic regression fitted on labelled pairs |
| `calibrated_probability` | isotonic-mapped onto observed precision      |

Naming the kind in the row means a consumer — the UI, an export, a reviewer —
cannot mistake one for another, and means rows written before and after a model
was fitted stay distinguishable in the same table.

The distinction is doing real work here, because the calibration currently
available is fitted on labels derived from the same attributes the matcher
compares. A `calibrated_probability` of 0.93 on this corpus is calibrated
against a circular target, and only the `kind` plus the version stamps make
that recoverable later.

#### Why both `proposed_before_rules` and `relationship_type`

Together they make the rule engine auditable. `SELECT` where the two differ and
you have every pair the rules pulled down, with `reason` explaining each one.
Without the pre-rule value, a rejection is indistinguishable from a low score.

#### The three JSON columns

`matched` / `conflicting` / `missing` are the evidence a reviewer actually reads.
They are stored as JSON text rather than a join table because they are written
once, read whole, and never queried by element. `conflicting_attributes` keeps
**both sides' values** — `{"name": "nominal_size", "left": "50", "right": "80"}`
— so the disagreement is legible without re-fetching either material.

#### What is not stored

`run_matching` drops `NOT_EQUIVALENT` rows by default. Of the 4,030 candidates
that reach the top-k across 404 materials, 1,084 are `NOT_EQUIVALENT`, and no
reviewer acts on them. They are still **counted** and returned in the run
summary, so the distribution is visible without storing noise.
`keep_not_equivalent=True` overrides this for analysis.

Observed on a full run over 404 materials:

```
EXACT_DUPLICATE          2080
NEAR_DUPLICATE            856
FUNCTIONALLY_EQUIVALENT    10
NOT_EQUIVALENT           1084   (counted, not stored)
stored                   2946
```

### 19. `review` and `audit_log`

| `review`                                      | Type                 | Notes                                |
| --------------------------------------------- | -------------------- | ------------------------------------ |
| `id`                                          | `String(36)` PK      |                                      |
| `query_material_id` · `candidate_material_id` | `String(32)` indexed | **The pair reviewed**                |
| `relationship_at_review`                      | `String(32)`         | Verdict the reviewer was shown       |
| `confidence_at_review`                        | `Float`              |                                      |
| `reason_at_review`                            | `Text`               |                                      |
| `matcher_version` · `rule_version`            | `String(32)`         | Pinned                               |
| `match_result_id`                             | `String(36)` indexed | **Soft reference, no foreign key**   |
| `reviewer`                                    | `String(120)`        | **Caller-supplied, unverified**      |
| `decision`                                    | `String(32)`         | `APPROVED`, `REJECTED`, `NEEDS_INFO` |
| `comment`                                     | `Text`               |                                      |
| `decided_at`                                  | `DateTime`           |                                      |

A pair may carry several reviews; the history is kept rather than overwritten.
`reviewer` is a placeholder until `api-service` asserts an authenticated
identity — see §22.

**Why there is no foreign key to `match_result`.** Every matching run begins
`DELETE FROM match_result` and rebuilds the table, so a review pointing at a row
by id points at something that will not exist after the next run. The review
therefore names the **material pair** — which is stable — and pins the verdict,
score, reason and versions it was decided against.

This was found the hard way. The original schema carried a foreign key with an
ORM-level `cascade="all, delete-orphan"`, and two things hid the problem: SQLite
leaves `PRAGMA foreign_keys` off by default, and an ORM cascade does not run for
a Core bulk `delete()`. Moving to Postgres turned the next `match-all` after any
review into a `ForeignKeyViolationError` and a 500. The tests now enable
`PRAGMA foreign_keys=ON` so SQLite enforces what Postgres enforces.

`ON DELETE CASCADE` would also have stopped the crash — by deleting a human
decision on every re-run. That is the opposite of what this system promises.

| `audit_log`   | Type                 | Notes                                      |
| ------------- | -------------------- | ------------------------------------------ |
| `id`          | `String(36)` PK      |                                            |
| `actor`       | `String(120)`        | `system` or a reviewer                     |
| `action`      | `String(48)` indexed | `INGEST`, `MATCHING_RUN`, `MATCH_REVIEWED` |
| `entity_type` | `String(48)`         |                                            |
| `entity_id`   | `String(64)` indexed | Nullable — a corpus run has none           |
| `detail`      | `Text` JSON          | Counts, parameters                         |
| `occurred_at` | `DateTime`           |                                            |

Append-only **in intent**: nothing in the codebase updates or deletes a row.
That is a code convention, not yet a database constraint. On Postgres it should
become a `REVOKE UPDATE, DELETE` grant.

### 20. Configuration files, in full

Domain rules live in CSV under `data/config/` so a materials engineer can edit
them in Excel, and so a change is a reviewable diff.

**`category_attributes.csv`** — 60 rows, 13 categories

```csv
category,attribute,role,why_it_matters,value_type,unit,extraction_pattern
BEARING,bearing_number,IDENTITY_DEFINING,A 6205 is not a 6305,string,,\b(6[0-9]{3})\b
BEARING,seal_type,DISCRIMINATING,Sealing changes the application,enum,,\b(2RS|ZZ|RS|OPEN)\b
```

`why_it_matters` is not decoration. It is the sentence a reviewer sees when the
attribute causes a rejection, and it forces whoever adds a row to justify the
role they chose.

**These 60 role assignments are the highest-value target for domain review.**
Every verdict follows from them.

**`abbreviations.csv`** — 37 rows. Empty scope means global; a non-empty scope is
matched as a **category prefix**.

```csv
raw,expansion,scope
BRG,BEARING,
CS,CARBON STEEL,PIPE_FITTING
```

**`uom_rules.csv`** — 22 rows · **`uom_normalization.csv`** — 24 rows

```csv
category,allowed_uom,dimension,note
BEARING,NOS|SET|PAIR,COUNT,Bearings are counted individually or supplied as a set.
BELT_CONVEYOR,MTR|ROLL,LENGTH,Conveyor belting is issued by length.
```

```csv
raw,normalized,dimension
EA,NOS,COUNT
PCS,NOS,COUNT
KG,KGS,MASS
```

`NOS` is the canonical count unit, not `EACH`.

**`data/ground_truth/pairs.csv`** — 60 rows

```csv
left_material_id,right_material_id,label,rationale,source
CCL-000001,IOCL-000188,EXACT_DUPLICATE,Same bearing number and seal type,derived
NTPC-000031,BHEL-000204,NEEDS_EXPERT_REVIEW,Insufficient evidence either way,derived
```

Current distribution: 20 `EXACT_DUPLICATE`, 19 `NEAR_DUPLICATE`,
19 `NOT_EQUIVALENT`, 2 `NEEDS_EXPERT_REVIEW`. No `FUNCTIONALLY_EQUIVALENT` pair
was constructible from the attributes alone — that label requires a positive
interchangeability judgement, which is exactly the kind an expert must supply.

`NEEDS_EXPERT_REVIEW` pairs are **excluded from scoring** rather than guessed.

**Honest caveat, repeated in the API response:** these labels were derived from
the same attributes the matcher compares. The evaluation therefore measures
internal consistency, not independent accuracy. It becomes a real measurement
once a domain expert has reviewed and corrected the file.

---

## Part D — Running it

### 21. Request paths

**Ingest** — `POST /api/v1/materials/ingest`

```
route → services.ingest.read_raw(settings.raw_dataset_path)
            validates the eight required columns up front
      → standardize_all()      Phase 1 over every row, pure
      → persist(replace=True)  clears derived tables, inserts, one commit
      → returns counts + quality-flag histogram
```

Idempotent. Re-running replaces all derived rows; the raw CSV is untouched.

**Matching** — `POST /api/v1/materials/match-all`

```
route → ingest.load_standardized(session)     ORM rows → dataclasses
      → matching_service.run_matching()
            for each material: engine.match(material, corpus)
      → writes one AuditLog row for the run
```

**Single query** — `GET /api/v1/materials/{id}/matches` runs the engine live
rather than reading `match_result`, so a config change is visible immediately
without a re-run. The response carries the full explanation: signals, penalties,
rules triggered, and the attribute lists.

Async lazy loading is not available, so `load_standardized` eager-loads with
`selectinload` on both `attributes` and `quality_flags`. Forgetting this raises
`MissingGreenlet` at access time rather than at query time, which is why it is
loaded explicitly in one place.

### 22. Where authorization is not

There is none, deliberately. `ai-service` has no user model, no tokens and no
CPSE scoping. Two consequences worth stating plainly:

- `ai-service` must not be exposed publicly. In compose it is reachable on
  `:8001` for development; in any real deployment it sits behind `api-service`.
- The `reviewer` field on `POST /matches/{id}/review` is caller-supplied and
  unverified. It is a placeholder for an identity that `api-service` will assert.

### 23. Migrations

`Base.metadata.create_all` runs in the FastAPI lifespan. That is correct for an
throwaway database and wrong now that this runs on Postgres: it creates missing
tables and **silently ignores changed columns**, so a future schema change fails
at runtime instead of at migration time. Introducing Alembic is the outstanding
task here. (`api-service` already has it configured — see
[02](02_BACKEND_ARCHITECTURE.md).)

### 24. Testing

273 tests, no network, no external service, no model download.

| File                     | Covers                                                                      |
| ------------------------ | --------------------------------------------------------------------------- |
| `tests/test_pipeline.py` | 11 — cleaning, abbreviation scope, classification, extraction, standardize  |
| `tests/test_matching.py` | 14 — comparison states, each rule, scoring penalties, `_decide`, clustering |
| `tests/test_api.py`      | 10 — the nine endpoints end-to-end against an in-memory DB                  |
| `tests/test_health.py`   | 1                                                                           |

`tests/conftest.py` builds an async in-memory SQLite engine per test and
overrides `get_db`. The pipeline and matching tests construct
`StandardizedMaterial` dataclasses directly, so they assert on decisions rather
than on plumbing.

Lint is `ruff` with flake8-bugbear. `B008` is configured with
`extend-immutable-calls` for `fastapi.Depends`, which is a false positive there.

---

**Next:** [04 · Retrieval & the Matcher Interface](04_RETRIEVAL_AND_MATCHER_INTERFACE.md)
