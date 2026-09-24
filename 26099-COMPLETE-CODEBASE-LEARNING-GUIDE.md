# 26099 — Complete Codebase Learning Guide

> **Who this is for.** You own the `ai-service` and its machine-learning
> functionality. This document assumes you know *no* technical concept in
> advance, and teaches the actual repository — not a generic architecture.
>
> **Scope.** `ai-service` in full. `api-service` and `frontend` appear only
> where `ai-service` touches them.
>
> **Source of truth.** Every claim below was checked against the code in this
> repository. Where the code and a README disagree, the code wins and the
> disagreement is recorded in [Part 35](#part-35--unknown--unclear--potential-issues).

**Legend used throughout:**

| Mark | Meaning |
|---|---|
| 🔴 | Must understand to work on this service |
| 🟡 | Should understand soon |
| 🟢 | Can safely postpone |

---

## Table of contents

| Part | Title |
|---|---|
| [1](#part-1--project-overview) | Project overview |
| [2](#part-2--complete-architecture) | Complete architecture |
| [3](#part-3--complete-folder-structure) | Complete folder structure |
| [4](#part-4--file-by-file-map) | File-by-file map |
| [5](#part-5--api-service-the-boundary-only) | api-service (the boundary only) |
| [6](#part-6--database) | Database |
| [7](#part-7--orm--database-access) | ORM / database access |
| [8](#part-8--pydantic--schemas) | Pydantic / schemas |
| [9](#part-9--ai-service-the-complete-pipeline) | AI-service: the complete pipeline |
| [10](#part-10--nlp) | NLP |
| [11](#part-11--embeddings) | Embeddings |
| [12](#part-12--llm) | LLM |
| [13](#part-13--matching-engine) | Matching engine |
| [14](#part-14--candidate-generation) | Candidate generation |
| [15](#part-15--material-data-flow) | Material data flow |
| [16](#part-16--important-data-structures) | Important data structures |
| [17](#part-17--python-concepts-used) | Python concepts used |
| [18](#part-18--python-libraries) | Python libraries |
| [19](#part-19--docker) | Docker |
| [20](#part-20--environment-variables) | Environment variables |
| [21](#part-21--configuration) | Configuration |
| [22](#part-22--error-handling) | Error handling |
| [23](#part-23--logging) | Logging |
| [24](#part-24--testing) | Testing |
| [25](#part-25--performance) | Performance |
| [26](#part-26--security) | Security |
| [27](#part-27--complete-request-flows) | Complete request flows |
| [28](#part-28--dependency-graph) | Dependency graph |
| [29](#part-29--what-happens-when-i-run-the-project) | What happens when I run the project |
| [30](#part-30--what-happens-when-i-send-this-api-request) | What happens on an API request |
| [31](#part-31--beginner-glossary) | Beginner glossary |
| [32](#part-32--learning-order) | Learning order |
| [33](#part-33--module-by-module-tutoring-plan) | Module-by-module tutoring plan |
| [34](#part-34--do-not-learn-this-yet) | Do not learn this yet |
| [35](#part-35--unknown--unclear--potential-issues) | Unknown / unclear / potential issues |
| [36](#part-36--claude-generated-code-warning) | Claude-generated code warning |
| [37](#part-37--cheat-sheet) | Cheat sheet |
| [38](#part-38--final-one-page-mental-model) | Final one-page mental model |

---

# PART 1 — Project Overview

## 1.1 The problem, in plain language

India has many **CPSEs** — Central Public Sector Enterprises. Think NTPC
(power), IOCL (oil), BHEL (heavy engineering), Coal India. Each one buys
physical things: bearings, bolts, cables, valves, safety shoes.

Each CPSE keeps its own list of everything it can buy. That list is called a
**material master**. Every row in it is a **material record**, and every row has
a **material code** — a short string like `M-55321` that the organisation uses
internally to refer to that thing.

Here is the problem. Two CPSEs buy **the same physical bearing**, but:

```
CPSE: Coal India (CCL)      code 116045321   "brg ball rad 6205 2rs for main store"
CPSE: BHEL                  code 224411      "BEARING, BALL, 6205-2RS1"
```

To a human engineer these are obviously nearly the same bearing. To a computer
comparing text, they share almost no characters. So:

- Nobody can answer *"does another CPSE already stock this?"*
- Nobody can combine demand to negotiate a better price.
- The same thing is stored, counted and reordered many times over.

**What this system does:** given any two material records from any CPSEs, decide
what their relationship is, and *show the evidence for the answer*.

## 1.2 Why the codes differ (this is not anyone's mistake)

1. **Codes are internal keys.** `M-55321` was never meant to mean anything
   outside the organisation that assigned it.
2. **Description fields are short.** In SAP (the ERP most CPSEs use) the short
   description field is 40 characters. An engineer forced to fit
   *"Hexagon head bolt, M10 × 50 mm, stainless steel grade 304"* into 40
   characters abbreviates — and everyone abbreviates differently.
3. **Different cataloguing habits.** `BOLT HEX HD M10X50 SS304` versus
   `SS304 HEXAGONAL BOLT 10MM X 50MM`.
4. **Different units.** One counts cable in metres, another in rolls.

## 1.3 What the input actually looks like

The real file in this repository is
[`backend/pipeline-one/CPSE_SIH26099.csv`](backend/pipeline-one/CPSE_SIH26099.csv)
— **404 data rows**, 8 CPSEs, 8 columns:

```
Company, Item Description (Raw), Item Code / Legacy Ref, Quantity, UOM,
Part Number / OEM Number, Make / Brand, Specifications / Dimensions
```

Two real rows:

```
Coal India (Central Coalfields Limited),brg ball rad 6205 2rs for main store,116045321,50,NOS,6205-2RS,SKF,ID 25mm OD 52mm W 15mm
Coal India (Central Coalfields Limited),"BEARING, BALL, 6205-2RS1",116045321,20,NOS,6205-2RS1,FAG,Radial deep groove ball bearing
```

The CPSEs present in the corpus: `BCCL`, `BHEL`, `CCL`, `GAIL`, `HEC`, `IOCL`,
`NTPC`, `ONGC`.

> **This file is opened read-only and is never modified.** It is mounted `:ro`
> in Docker ([`docker-compose.yml`](docker-compose.yml)). Every correction the
> system makes is a *flag stored next to* the original value, never an edit.

## 1.4 The four answers the system can give

Everything in this project exists to produce one of four verdicts. They are
defined as a Python enum in
[`app/logic/enums.py`](backend/ai-service/app/logic/enums.py):

```python
class Relationship(StrEnum):
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    FUNCTIONALLY_EQUIVALENT = "FUNCTIONALLY_EQUIVALENT"
    NOT_EQUIVALENT = "NOT_EQUIVALENT"
```

| Verdict | Plain meaning | What a human should do |
|---|---|---|
| `EXACT_DUPLICATE` | The same physical article. Every identifying property matches. | Merge them under one national code. |
| `NEAR_DUPLICATE` | Almost certainly the same, but one record is *silent* about something. | Ask the CPSE to confirm the missing property. |
| `FUNCTIONALLY_EQUIVALENT` | Different articles that do the same job. | Record as interchangeable — **never merge**. |
| `NOT_EQUIVALENT` | Genuinely different, even if the text looks similar. | Reject. |

### Why the fourth one is the dangerous case

`HEX BOLT M10X50 SS304` and `HEX BOLT M10X50 SS316` differ by **one character**.
A pure text-similarity system scores them ~0.98 and calls them the same. But
SS304 and SS316 are different steels with different corrosion resistance.
Putting the wrong one into a refinery is a safety event.

**This single fact shapes the whole architecture.** Text similarity is only
allowed to *suggest which pairs to look at*. The actual decision is made by
comparing extracted engineering properties, and hard rules can veto any score.

## 1.5 Your example, traced

```
CPSE A   Material Code: M-55321   Description: V-BELT SEC C, NOM L 120 INCH
CPSE B   Material Code: 224411    Description: BELT V C-120
```

This exact pair is a real test in
[`tests/test_matching.py`](backend/ai-service/tests/test_matching.py):

```python
def test_same_bolt_different_wording_is_an_exact_duplicate(build):
    a = build("V-BELT SEC C, NOM L 120 INCH", company="NTPC")
    b = build("BELT V C-120", company="BHEL", source_row=2)
    relationship, score, rules, _ = verdict(a, b)
    assert relationship is Relationship.EXACT_DUPLICATE
```

Step by step, with the file that does each step:

| # | Step | File | `V-BELT SEC C, NOM L 120 INCH` becomes |
|---|---|---|---|
| 1 | Clean | [`logic/clean.py`](backend/ai-service/app/logic/clean.py) | `V-BELT SEC C NOM L 120 INCH` (uppercased, punctuation normalised) |
| 2 | Tokenize | [`logic/tokenize.py`](backend/ai-service/app/logic/tokenize.py) | `120 INCH` protected as one measurement token |
| 3 | Classify (pass 1) | [`logic/classify.py`](backend/ai-service/app/logic/classify.py) | category = `BELT_V` (matched the word `BELT`) |
| 4 | Expand abbreviations | [`logic/clean.py`](backend/ai-service/app/logic/clean.py) | `SEC` → `SECTION`, `NOM L` → `NOMINAL LENGTH` |
| 5 | Extract attributes | [`logic/extract.py`](backend/ai-service/app/logic/extract.py) | `belt_type=V`, `belt_section=C`, `nominal_length=120` |
| 6 | Validate + infer | [`logic/validate.py`](backend/ai-service/app/logic/validate.py) | all values in range → `status=PRESENT` |
| 7 | Classify (pass 2) | [`logic/classifier.py`](backend/ai-service/app/logic/classifier.py) | still `BELT_V` |
| 8 | Canonical form | [`logic/standardize.py`](backend/ai-service/app/logic/standardize.py) | `BELT_V: belt_section=C; belt_type=V; nominal_length=120` |

`BELT V C-120` runs through the same eight steps and lands on **the same
canonical string**. That is the whole trick: two different sentences converge on
one structured representation *before* anything is compared.

Then:

| # | Step | File | Result |
|---|---|---|---|
| 9 | Compare | [`logic/compare.py`](backend/ai-service/app/logic/compare.py) | every attribute `MATCH`, none `CONFLICT`, none `MISSING` |
| 10 | Score | [`logic/score.py`](backend/ai-service/app/logic/score.py) | `identity_agreement=1.0` … total ≈ 0.95 |
| 11 | Rules | [`logic/rules.py`](backend/ai-service/app/logic/rules.py) | all five rules `PASS` |
| 12 | Decide | [`logic/matcher.py::_decide`](backend/ai-service/app/logic/matcher.py) | `EXACT_DUPLICATE` |

## 1.6 What the final output represents

For each pair the system stores a row in the `match_result` table containing the
verdict, the confidence number, **the arithmetic behind that number**, the
attribute-by-attribute comparison, which rules fired, and eight version stamps
identifying exactly which code produced it.

That last part matters more than it sounds. A national material code, once
published, may appear in a contract. Years later somebody must be able to ask
*"why did the system say these were the same?"* and get a real answer.

---

# PART 2 — Complete Architecture

## 2.1 The real architecture in this repository

```
                        ┌──────────────────────────┐
                        │  Browser / curl / tests  │
                        └────────────┬─────────────┘
                                     │  HTTP + JSON
                                     ▼
                        ┌──────────────────────────┐
                        │  frontend  (Next.js 16)  │  :3000
                        │  SCAFFOLD ONLY           │
                        └────────────┬─────────────┘
                                     │
                                     ▼
                        ┌──────────────────────────┐
                        │  api-service  (FastAPI)  │  :8000
                        │  SCAFFOLD — NOT BUILT    │
                        │  will own: auth, RBAC,   │
                        │  uploads, review, codes  │
                        └────────────┬─────────────┘
                                     │  httpx, async HTTP
                                     │  app/services/ai_client.py
                                     ▼
        ┌────────────────────────────────────────────────────────┐
        │  ai-service   (FastAPI)                        :8001   │
        │  ★ THIS IS YOUR SERVICE — fully built, 138 tests ★     │
        │                                                        │
        │  routes/  →  schemas/  →  services/  →  models/        │
        │                    ↓                                   │
        │                 logic/   (all the ML: 22 modules)      │
        └───────┬─────────────────────────────────┬──────────────┘
                │ SQLAlchemy async                │ qdrant-client
                ▼                                 ▼
     ┌────────────────────┐            ┌────────────────────┐
     │  PostgreSQL 16     │            │  Qdrant  v1.19     │  :6333
     │  db: numm_ai       │            │  collection:       │
     │  SOURCE OF TRUTH   │            │  material_embeddings│
     └────────────────────┘            │  DERIVED STATE     │
                                       └────────────────────┘

   In-process, loaded once at first use (no separate model server):
     • Qwen/Qwen3-Embedding-0.6B  (PyTorch + transformers)   1024-d vectors
     • scikit-learn LogisticRegression  (category classifier)
     • spaCy NER  (attribute extraction, step 4)
     • scikit-learn IsotonicRegression  (confidence calibration)

   Optional, OFF by default:
     • Ollama @ :11434  →  qwen2.5:3b-instruct  (LLM extraction fallback)
```

## 2.2 Service-by-service

### `ai-service` 🔴 — your service

| Question | Answer |
|---|---|
| **Why it exists** | To turn messy text into comparable engineering structure, and to decide relationships between materials. |
| **What it owns** | Standardization, attribute extraction, classification, embeddings, the vector index, matching, rules, verdicts, explanations, evaluation metrics. |
| **What it must never own** | Users, roles, permissions, CPSE data isolation, national code issuance. Those are `api-service`'s. |
| **What enters** | HTTP requests from `api-service`; the raw CSV from disk. |
| **What leaves** | JSON: standardized materials, match verdicts with explanations, quality reports, evaluation metrics. |
| **Databases** | Owns `numm_ai` in PostgreSQL, and the `material_embeddings` collection in Qdrant. |
| **Communication** | Synchronous HTTP in. Synchronous SQL and Qdrant calls out. **No queue, no background workers.** |

### `api-service` 🟢 — a scaffold you mostly ignore

Read [Part 5](#part-5--api-service-the-boundary-only). The only thing that
matters to you: it is the intended sole client of `ai-service`, and its client
code is currently **broken** — see [Part 35](#part-35--unknown--unclear--potential-issues).

### PostgreSQL 🔴 — the source of truth

Two separate databases inside one server:
`sih` for `api-service`, `numm_ai` for `ai-service`. They never share a schema.
[`scripts/init-db.sql`](backend/ai-service/scripts/init-db.sql) creates
`numm_ai` when the compose volume is first initialised.

### Qdrant 🟡 — derived state

Stores one 1024-number vector per material. The critical property, enforced
throughout [`logic/retrieval.py`](backend/ai-service/app/logic/retrieval.py):

> **If Qdrant is deleted entirely, nothing of value is lost.** Every vector is
> reproducible from `canonical_text` in PostgreSQL by re-running the model.

No business decision reads from Qdrant except *candidate retrieval*, and no
field exists only in a Qdrant payload. Price, vendor and quantity are
deliberately absent from it.

## 2.3 Synchronous vs asynchronous — an honest note

Beginners often assume "async" means background jobs. It does not here.

- Every route in `ai-service` is `async def`, and every database call is
  `await`ed. That is **async I/O**: while one request waits on the database,
  Python can serve another. See [Part 17](#part-17--python-concepts-used).
- **There are no background jobs, no queue, no Celery, no workers.**
  `POST /api/v1/materials/match-all` runs the entire corpus match *inside the
  request* and does not return until finished.

---

# PART 3 — Complete Folder Structure

## 3.1 The real tree

```
sih-2026/
├── 26099-COMPLETE-CODEBASE-LEARNING-GUIDE.md   ← this file
├── README.md
├── Makefile                       one-line commands for everything
├── docker-compose.yml             5 services: postgres, api, qdrant, ai, frontend
├── .env.example                   root-level compose variables
├── .editorconfig
├── .github/workflows/ci.yml       lint + tests on every push
│
├── docs/                          architecture set (00–07)
│   ├── 00_INDEX.md                start here; the five commitments
│   ├── 01_SYSTEM_ARCHITECTURE.md  actors, topology, technology deltas
│   ├── 02_BACKEND_ARCHITECTURE.md api-service — PLANNED, not built
│   ├── 03_ML_ARCHITECTURE.md      ★ your service, stage by stage
│   ├── 04_RETRIEVAL_AND_MATCHER_INTERFACE.md  ★ blocking, embeddings, score
│   ├── 05_MATCHING_AND_RULE_ENGINE.md         ★ the five rules
│   ├── 06_API_SPECIFICATION.md    Part B = ai-service endpoints
│   └── 07_DEPLOYMENT.md           compose, config, operations
│
├── backend/
│   ├── pipeline-one/              ← RAW DATA, read-only
│   │   ├── CPSE_SIH26099.csv      404 rows, the real corpus
│   │   ├── raw_sap_data_chaotic.csv   17 rows (see Part 35)
│   │   ├── schema.json
│   │   └── extractor.ipynb        Jupyter notebook (see Part 35)
│   │
│   ├── api-service/               NOT YOUR SERVICE — scaffold
│   │   ├── app/{api,core,db,models,schemas,services}/
│   │   ├── alembic/               migration tool, no migrations written
│   │   └── tests/
│   │
│   └── ai-service/                ★★★ YOUR SERVICE ★★★
│       ├── app/
│       │   ├── main.py            builds the FastAPI app
│       │   ├── config.py          ALL 51 settings + logging setup
│       │   ├── database.py        engine, session, Base
│       │   ├── auth.py            X-Internal-Key check
│       │   │
│       │   ├── routes/            LAYER 1 — HTTP in, HTTP out
│       │   │   ├── health.py
│       │   │   ├── materials.py   ingest, list, get one, quality
│       │   │   ├── matching.py    match one, match all, review
│       │   │   ├── evaluation.py  ground truth, score report
│       │   │   ├── retrieval.py   index, status, model info
│       │   │   └── ingest.py      ingest-by-reference + import jobs
│       │   │
│       │   ├── schemas/           LAYER 2 — request/response shapes
│       │   │   ├── common.py      HealthResponse
│       │   │   └── material.py    9 Pydantic models
│       │   │
│       │   ├── services/          LAYER 3 — the work
│       │   │   ├── ingest.py      CSV → standardize → DB
│       │   │   ├── materials.py   read side + schema mapper
│       │   │   ├── matching.py    match one/all, review
│       │   │   ├── evaluation.py  gold set + report
│       │   │   ├── indexing.py    embed + upsert + reconcile
│       │   │   └── reference_ingest.py  a CSV api-service already stored
│       │   │
│       │   ├── models/            LAYER 4 — database tables
│       │   │   ├── material.py    material, standardized_material,
│       │   │   │                  material_attribute, quality_flag
│       │   │   ├── matching.py    match_result, review, audit_log
│       │   │   └── ingest.py      import_job, import_row_error
│       │   │
│       │   └── logic/             ★ THE ML — pure Python, no HTTP, no DB
│       │       ├── enums.py       shared vocabulary
│       │       ├── versions.py    8 version stamps
│       │       ├── reference.py   loads the CSV config
│       │       │
│       │       ├── clean.py       S1 + S3
│       │       ├── tokenize.py    S2
│       │       ├── units.py       S4  (Pint)
│       │       ├── extract.py     S5  regex + dictionary
│       │       ├── ner.py         S5  step 4 (spaCy)
│       │       ├── llm.py         S5  step 5 (Ollama, OFF)
│       │       ├── validate.py    S5  6 rules + INFERRED
│       │       ├── classify.py    S6  tier 1 keywords
│       │       ├── classifier.py  S6  tiers 2–3 + two-pass
│       │       ├── quality.py     data-quality flags
│       │       ├── standardize.py S7  orchestrates S1–S7
│       │       │
│       │       ├── embedding.py   Qwen3 + deterministic fallback
│       │       ├── retrieval.py   Qdrant + in-memory VectorStore
│       │       ├── candidates.py  union recall
│       │       │
│       │       ├── compare.py     attribute-by-attribute comparison
│       │       ├── score.py       the scoring formula
│       │       ├── fusion.py      learned weights + calibrated wrapper
│       │       ├── calibration.py isotonic regression
│       │       ├── rules.py       the 5 hard rules
│       │       ├── matcher.py     blocking + verdict + clustering
│       │       ├── explain.py     the stored evidence object
│       │       ├── ground_truth.py gold-label generator
│       │       └── metrics.py     precision / recall / F1
│       │
│       ├── data/
│       │   ├── config/            ★ DOMAIN KNOWLEDGE AS CSV
│       │   │   ├── category_attributes.csv   60 rows — the most important file
│       │   │   ├── abbreviations.csv         36 rows
│       │   │   ├── uom_normalization.csv     44 rows
│       │   │   ├── uom_rules.csv             21 rows
│       │   │   └── class_descriptors.csv     22 rows (zero-shot)
│       │   ├── ground_truth/pairs.csv        60 gold labels
│       │   ├── uploads/          ← files api-service stores for us to read
│       │   ├── models/            trained artefacts (gitignored)
│       │   └── standardized/materials.jsonl  export output
│       │
│       ├── scripts/
│       │   ├── train_classifier.py
│       │   ├── train_ner.py
│       │   ├── train_fusion.py
│       │   ├── ablation.py        ★ measures what ANN actually adds
│       │   ├── init-db.sql
│       │   └── setup_postgres.sql
│       │
│       ├── tests/                 138 tests + 10 opt-in Qdrant tests
│       ├── Dockerfile
│       ├── requirements.txt       runtime
│       ├── requirements-dev.txt   + pytest, ruff, mypy
│       ├── requirements-ml.txt    + torch, transformers (~2 GB)
│       ├── pyproject.toml         ruff + pytest config
│       └── .env.example
│
└── frontend/                      Next.js scaffold, one status page
```

## 3.2 Why each ai-service folder exists

### `app/routes/` 🔴

**Why:** to translate HTTP into function calls and back. Nothing else.

**What belongs here:** reading query parameters, calling one service function,
turning `None` into a 404. **No SQL. No thresholds. No scoring.**

A whole route, from [`routes/materials.py`](backend/ai-service/app/routes/materials.py):

```python
@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(
    material_id: str, session: AsyncSession = Depends(get_db)
) -> MaterialOut:
    found = await materials.get_material(session, material_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown material {material_id!r}")
    return found
```

**Depended on by:** `app/main.py` only.

### `app/schemas/` 🔴

**Why:** to define exactly what JSON goes in and out, and to validate it
automatically. See [Part 8](#part-8--pydantic--schemas).

**Depended on by:** `routes/` and `services/`.

### `app/services/` 🔴

**Why:** the actual work — talk to the database, call the algorithms, return a
schema. Services know nothing about HTTP: they return `None` for "not found"
and let the route decide the status code.

**Depended on by:** `routes/`.

### `app/models/` 🔴

**Why:** one Python class per database table.

**Depended on by:** `services/`.

### `app/logic/` 🔴🔴 — where you will spend most of your time

**Why:** every algorithm, as **pure functions**. No database session, no HTTP
request, no file reads except through `reference.py`.

**Why that purity matters:** it is the reason 138 tests run in ~13 seconds with
no database and no model download.

**One deliberate exception:** `embedding.py` and `retrieval.py` reach out to a
model and a vector store. Both sit behind *protocols* with in-process fallbacks,
so the rest of `logic/` stays pure.

### `data/config/` 🔴 — domain knowledge, not code

**Why:** so a materials engineer can improve the system without a developer.

> The docs make a strong claim here, and it is worth internalising: *changing the
> embedding model might move F1 by a point; adding 50 missing abbreviations for a
> new family can move recall by ten.*


---

# PART 4 — File-by-File Map

Every source file in `ai-service`. Line counts are real.

## 4.1 Application shell

### `app/main.py` (33 lines) 🔴

```
Purpose:      Build the FastAPI application object and mount the routes.
Called by:    uvicorn (the web server) — `uvicorn app.main:app`
Calls:        app.config, app.database, app.models, app.routes, app.auth
Important:    `lifespan()` async context manager, `app` (the FastAPI instance)
Inputs:       none (module import)
Outputs:      a configured FastAPI application
DB:           creates all tables at startup via Base.metadata.create_all
External API: none
AI/ML:        none directly
Concepts:     🔴 async context manager, decorators, ASGI
```

The whole startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield                       # ← the app serves requests here
    await engine.dispose()
```

Everything **before** `yield` runs once at startup; everything **after** runs at
shutdown. `create_all` creates any table that does not exist yet — this project
does **not** use migrations for `ai-service`.

### `app/config.py` (170 lines) 🔴

```
Purpose:      All 51 settings, read from environment/.env, plus logging setup.
Called by:    almost every module (19 imports — the most imported module)
Calls:        pydantic_settings
Important:    class Settings, settings (module-level singleton),
              get_settings() (@lru_cache), configure_logging()
Inputs:       environment variables and backend/ai-service/.env
Outputs:      one validated `settings` object
Concepts:     🔴 Pydantic Settings, @property, @lru_cache
```

Two computed properties worth reading:

```python
@property
def sqlalchemy_url(self) -> str:
    if self.database_url:                    # one full URL wins if given
        return self.database_url
    credentials = f"{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
    return f"postgresql+asyncpg://{credentials}@{self.db_host}:{self.db_port}/{self.db_name}"

@property
def sslmode(self) -> str:
    """DB_SSLMODE decides; DB_SSL=true raises anything weaker to 'require'."""
```

### `app/database.py` (35 lines) 🔴

```
Purpose:      One async engine, one session factory, one declarative Base.
Called by:    models/, services/, routes/ (via Depends(get_db))
Important:    Base, engine, AsyncSessionLocal, get_db()
Concepts:     🔴 SQLAlchemy async engine, dependency injection, async generator
```

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request."""
    async with AsyncSessionLocal() as session:
        yield session
```

### `app/auth.py` (48 lines) 🟡

```
Purpose:      Verify the X-Internal-Key header on internal calls.
Called by:    app/main.py, as a router-level dependency
Important:    verify_internal_key()
Concepts:     🟡 FastAPI Header dependency, hmac.compare_digest
```

Two design points: it is a **no-op unless `REQUIRE_INTERNAL_KEY=true`**, and it
**fails closed** — flag on with no key configured returns 500, never "allow all".
It uses `hmac.compare_digest` because a normal `==` returns early on the first
wrong byte, leaking the key to anyone who can time responses.

## 4.2 `app/logic/` — the ML core

### `logic/enums.py` (74 lines) 🔴

```
Purpose:      Shared vocabulary. The one module everything may import.
Called by:    12 modules
Important:    AttributeRole, Relationship, RuleStatus, ComparisonState,
              AttributeStatus, ExtractionMethod, Severity,
              RELATIONSHIP_RANK, cap_relationship()
Dependencies: none from this app — deliberately
```

The most important function in the file:

```python
def cap_relationship(proposed: Relationship, ceiling: Relationship | None) -> Relationship:
    if ceiling is None:
        return proposed
    return proposed if RELATIONSHIP_RANK[proposed] <= RELATIONSHIP_RANK[ceiling] else ceiling
```

**Rules may only lower a verdict, never raise it.** That is enforced here, once.

### `logic/versions.py` (66 lines) 🟡

```
Purpose:      Single source of the 8 version stamps stored with every decision.
Called by:    explain.py, services/matching.py, standardize.py
Important:    PIPELINE_VERSION, TOKENIZER_VERSION, DICTIONARY_VERSION,
              RULE_VERSION, MATCHER_VERSION, TAXONOMY_VERSION,
              VersionStamp, current()
```

### `logic/reference.py` (122 lines) 🔴

```
Purpose:      Load the 4 driving CSVs into frozen dataclasses, once.
Called by:    9 modules
Important:    AttributeSpec, CategorySpec, PipelineConfig, load_config()
Inputs:       data/config/*.csv
Outputs:      one PipelineConfig
Concepts:     🔴 @lru_cache, frozen dataclass, csv.DictReader
```

`load_config` is `@lru_cache`d, so the CSVs are parsed **once per process**.
Note this detail:

```python
# Longest first so "GT VLV" wins over "VLV".
abbreviations.sort(key=lambda x: len(x[0]), reverse=True)
```

### `logic/clean.py` (66 lines) — stages S1 + S3 🔴

```
Purpose:      Strip procurement noise (S1); expand abbreviations (S3);
              map a raw UOM through the controlled list.
Called by:    standardize.py
Important:    NOISE_PATTERNS, clean(), expand_abbreviations(), normalize_uom()
Inputs:       raw description string
Outputs:      (cleaned_text, list_of_removed_noise_labels)
```

The five noise patterns are real strings from the dataset:
`- URGENT REQ`, `**OEM ONLY**`, `(BOQ1 REF)`, `REQ AS PER ATTACHED SPEC`,
`FOR MAIN STORE`.

Abbreviation expansion is **category-scoped**, which prevents a real bug:

```python
if scope and not (category or "").startswith(scope):
    continue
```

`CS` means carbon steel in piping and cast steel in valves. Rather than guess,
an unscoped ambiguous abbreviation is left untouched.

### `logic/tokenize.py` (176 lines) — stage S2 🔴

```
Purpose:      Split text without destroying engineering designations.
Called by:    standardize.py
Important:    PROTECTED (13 regex patterns), Token, tokenize(), retokenize()
Inputs:       cleaned text
Outputs:      list[Token] with character offsets, or a respaced string
```

| Input | A normal tokenizer | This one |
|---|---|---|
| `M16X50` | `M16X50` or `M`,`16`,`X`,`50` | `M16` · `X` · `50` |
| `1/2"` | `1`,`/`,`2`,`"` | `1/2"` (one token) |
| `SS-304` | `SS`,`304` | `SS304` |

**Why this module exists at all:** before it, abbreviation expansion ran as a
blind regex over the raw string and turned `SS-304` into
`STAINLESS STEEL-304`. There is now a regression test for exactly that.

### `logic/units.py` (362 lines) — stage S4 🔴

```
Purpose:      Parse measurements and resolve units, using Pint for real
              dimensional analysis.
Called by:    extract.py, compare.py, validate.py
Important:    registry(), Quantity, UomResolution, parse_quantity(),
              parse_pipe_size(), resolve_uom(), dimensions_compatible(),
              conversion_factor(), NOMINAL_BORE_MM
Concepts:     🔴 Pint units, dimensional analysis, @lru_cache
```

Three outcomes for any raw unit, and the third is not an error:

| Outcome | Example | Consequence |
|---|---|---|
| `CANONICAL` | `NOS` → `NOS` | comparable |
| `CONVERTIBLE` | `G` → `KGS`, factor `0.001` | comparable through the factor |
| `PACKAGING` | `ROLL`, `DRUM` | preserved and **flagged**, never silently converted |

`dimensions_compatible()` **is** the UOM gate — dimension is a type, so `EA` vs
`MM` cannot be compared by accident.

Note the domain subtlety in `parse_pipe_size()`: `2"` as a *pipe size* is DN50
(50 mm nominal), not 50.8 mm. A 2-inch **bolt** really is 50.8 mm, so the two
readings are separate functions on purpose.

### `logic/extract.py` (130 lines) — stage S5, steps 1–2 🔴

```
Purpose:      Pull typed attributes out of text using the CSV-driven patterns.
Called by:    standardize.py
Important:    ExtractedAttribute (the central dataclass), extract(),
              missing_identity_attributes()
Inputs:       normalized text + category + PipelineConfig
Outputs:      list[ExtractedAttribute]
```

`ExtractedAttribute` is the most important data structure in the service:

```python
@dataclass(frozen=True)
class ExtractedAttribute:
    name: str                      # "thread_size"
    value: str                     # "M16"
    role: AttributeRole            # IDENTITY_DEFINING | DISCRIMINATING | DESCRIPTIVE
    unit: str | None
    numeric_value: float | None
    method: str                    # REGEX | DICT | NER | LLM | INFERRED | ...
    confidence: float
    source_span: tuple[int, int] | None   # where in the text it came from
    raw_value: str | None                 # what the CPSE actually wrote
    si_value: float | None                # normalised for comparison
    status: AttributeStatus               # PRESENT | MISSING | INFERRED | INVALID
    note: str | None
```

### `logic/ner.py` (137 lines) — stage S5, step 4 🟡

```
Purpose:      Catch attributes the regexes miss, using a small spaCy model.
Called by:    standardize.py
Important:    NerExtractor, get_ner(), ner_attributes(), build_training_examples()
AI/ML:        spaCy NER, trained by scripts/train_ner.py
```

**Gap-filling only** — it never overwrites a pattern extraction, because a
deterministic match is better evidence than a model's guess. Confidence is fixed
at `0.62`, below the `0.9` a regex gets.

### `logic/llm.py` (186 lines) — stage S5, step 5 🟢

```
Purpose:      Last-resort extraction for records nothing else could parse.
Called by:    standardize.py
Important:    build_prompt(), extract_with_llm(), llm_attributes(), coverage()
External API: Ollama at OLLAMA_URL (local only)
Status:       OFF BY DEFAULT (USE_LLM_FALLBACK=false)
```

See [Part 12](#part-12--llm).

### `logic/validate.py` (212 lines) — stage S5 tail 🔴

```
Purpose:      Six validation rules, plus rule-based inference.
Called by:    standardize.py
Important:    VALIDATION_RULES, RANGES, GRADE_IMPLIES_MATERIAL,
              apply_inference(), validate_attributes()
```

**Nothing is deleted.** A suspect value is *demoted* (confidence lowered, note
attached) or marked `INVALID` — because a deleted value is invisible to a
reviewer, and an `INVALID` one is shown with its reason.

`apply_inference()` derives values nobody wrote:

```python
# 6205 → bore 25 mm, via ISO 15 bore code (05 × 5 mm)
```

Such values get `status=INFERRED`, reduced weight, the rule cited — and can
**never** be the sole basis of an `EXACT_DUPLICATE`.

### `logic/classify.py` (60 lines) — stage S6, tier 1 🔴

```
Purpose:      Assign a material family from keyword rules.
Important:    RULES (22 ordered patterns), UNCLASSIFIED, Classification, classify()
```

Order matters and the comment says why:

```python
# Order matters: the first match wins, so put specific families above generic
# ones. WIRE ROPE must beat CABLE, SEAL KIT must beat the generic O-RING check.
```

Returns `UNCLASSIFIED` with confidence `0.0` rather than guessing.
**Abstention is a feature** — a forced wrong class silently breaks blocking.

### `logic/classifier.py` (244 lines) — stage S6, tiers 2–3 🟡

```
Purpose:      Embedding-based classification when keywords abstain, plus the
              two-pass refinement.
Important:    ClassifierBundle, load_descriptors(), classify_text(),
              classify_two_pass(), train_linear_classifier(),
              TIER2_MIN_CONFIDENCE=0.55, TIER3_MIN_CONFIDENCE=0.30
AI/ML:        scikit-learn LogisticRegression; zero-shot via embedded descriptors
```

### `logic/quality.py` (75 lines) 🟡

```
Purpose:      Emit data-quality flags. Never corrects anything.
Important:    QualityFlag, check_uom(), check_description(),
              check_identity_coverage(), check_part_number()
```

Flag codes: `UOM_UNRECOGNISED`, `UOM_MISMATCH`, `DESCRIPTION_NOISE`,
`IRREGULAR_SPACING`, `DESCRIPTION_TOO_SHORT`, `MISSING_IDENTITY_ATTRIBUTE`,
`PART_NUMBER_ABSENT`.

### `logic/standardize.py` (189 lines) — stage S7 + orchestrator 🔴🔴

```
Purpose:      Run S1–S7 in order. THE function to read first.
Called by:    services/ingest.py, every training script, most tests
Important:    RawMaterial, StandardizedMaterial, standardize(), cpse_code_for()
Inputs:       one RawMaterial + PipelineConfig
Outputs:      one StandardizedMaterial
```

### `logic/embedding.py` (246 lines) 🔴

See [Part 11](#part-11--embeddings).

### `logic/retrieval.py` (343 lines) 🔴

See [Part 14](#part-14--candidate-generation).

### `logic/candidates.py` (182 lines) 🔴

```
Purpose:      Union four retrieval paths into one candidate set.
Important:    UnionRetriever, BlockOnlyRetriever, CandidateSet,
              _fingerprint_candidates(), _trigram_candidates()
```

### `logic/compare.py` (173 lines) 🔴🔴

```
Purpose:      Attribute-by-attribute comparison — the evidence everything else
              is computed from.
Important:    AttributeComparison, ComparisonResult, compare(),
              LOW_TRUST_METHODS, INFERRED_WEIGHT = 0.5
```

Four states, not two:

```python
AGREE     both PRESENT, equal            → MATCH
CONFLICT  both PRESENT, unequal          → gate candidate
MISSING   absent on one or both sides    → NEVER agreement, NEVER conflict
INFERRED  at least one side derived      → reduced weight
```

### `logic/score.py` (153 lines) 🔴🔴

See [Part 13](#part-13--matching-engine).

### `logic/fusion.py` (165 lines) + `logic/calibration.py` (133 lines) 🟡

See [Part 13.6](#136-layer-7--learned-fusion-and-calibration).

### `logic/rules.py` (139 lines) 🔴🔴

See [Part 13.4](#134-the-five-rules).

### `logic/matcher.py` (285 lines) 🔴🔴

```
Purpose:      Tie everything together: retrieve → compare → score → rules →
              verdict → explanation. Also clustering.
Important:    MatchingEngine, Candidate, MatchOutcome, Retriever protocol,
              _propose(), _decide(), build_engine()
```

### `logic/explain.py` (214 lines) 🟡

```
Purpose:      Build the stored evidence object a reviewer reads.
Important:    build_explanation(), narrate(), _signal_rows(), _gate_rows()
```

### `logic/ground_truth.py` (192 lines) + `logic/metrics.py` (121 lines) 🟡

```
ground_truth.py: generates 60 gold pairs from 5 construction rules,
                 marking undecidable pairs NEEDS_EXPERT_REVIEW.
metrics.py:      precision / recall / F1 / confusion matrix; excludes
                 NEEDS_EXPERT_REVIEW rather than counting them as misses.
```

## 4.3 `app/services/`

| File | Lines | Key functions | Talks to |
|---|---|---|---|
| `ingest.py` | 209 | `read_raw`, `standardize_all`, `persist`, `load_standardized`, `export_jsonl`, `ingest_dataset` | CSV, Postgres |
| `materials.py` | 72 | `to_out`, `list_materials`, `get_material`, `quality_summary` | Postgres |
| `matching.py` | 184 | `run_matching`, `match_one`, `match_all`, `review_match`, `summarise` | Postgres |
| `evaluation.py` | 41 | `build_ground_truth`, `report` | Postgres, CSV |
| `indexing.py` | 163 | `build_points`, `reindex`, `index_status`, `_stale_ids` | Postgres, Qdrant |
| `reference_ingest.py` | 375 | `resolve_reference`, `parse_csv`, `ingest_from_reference`, `_delete_for_cpses` | disk/HTTP, Postgres |

`load_standardized()` in `ingest.py` deserves attention — it rebuilds the
in-memory `StandardizedMaterial` objects from the database, and contains this:

```python
# Eager-load the children: lazy loading cannot run inside the async session.
.options(
    selectinload(StandardizedMaterialRow.attributes),
    selectinload(StandardizedMaterialRow.quality_flags),
)
```

That is an **N+1 query fix** and an async-correctness fix at once. See
[Part 25](#part-25--performance).

## 4.4 `app/routes/` and `app/models/`

| File | Lines | Endpoints / tables |
|---|---|---|
| `routes/health.py` | 14 | `GET /health` |
| `routes/materials.py` | 46 | ingest, list, quality, get one |
| `routes/matching.py` | 45 | matches, match-all, review |
| `routes/evaluation.py` | 32 | ground-truth/build, evaluation/report |
| `routes/retrieval.py` | 48 | index, status, model/info |
| `routes/ingest.py` | 108 | by-reference, jobs, job, job errors |
| `models/material.py` | 128 | `material`, `standardized_material`, `material_attribute`, `quality_flag` |
| `models/matching.py` | 108 | `match_result`, `review`, `audit_log` |
| `models/ingest.py` | 108 | `import_job`, `import_row_error` |

## 4.5 `scripts/`

| File | Lines | What it produces |
|---|---|---|
| `train_classifier.py` | 46 | `data/models/classifier_linear.joblib` |
| `train_ner.py` | 85 | `data/models/ner/` |
| `train_fusion.py` | 126 | `fusion_weights.json` + `calibration_isotonic.json` |
| `ablation.py` | 136 | a printed report — **no artefact** |

---

# PART 5 — api-service (the boundary only)

You do not own this service. This section covers only what you must know.

## 5.1 What is FastAPI, and what is an API? 🔴

**An API** is a way for one program to call another over a network instead of
by importing it.

**HTTP** is the protocol they use. Every request has a **method** and a **path**:

| Method | Convention | Example here |
|---|---|---|
| `GET` | read something, change nothing | `GET /api/v1/materials/quality` |
| `POST` | do something / create something | `POST /api/v1/materials/ingest` |
| `PUT`/`PATCH` | replace / partially update | *not used in ai-service* |
| `DELETE` | remove | *not used in ai-service* |

**Status codes** are the reply's headline:

| Code | Meaning | Where ai-service returns it |
|---|---|---|
| 200 | OK | normal success |
| 201 | Created | `POST .../review` |
| 401 | Unauthenticated | bad/missing `X-Internal-Key` |
| 404 | Not found | unknown material or match id |
| 409 | Conflict | `match-all` with nothing ingested |
| 422 | Unprocessable | Pydantic validation failed (automatic) |
| 500 | Server error | auth required but no key configured |

**JSON** is the text format for the data.

**FastAPI** is the Python library that maps a URL to a function, validates the
incoming JSON against a Pydantic schema, and generates live documentation at
`/docs`.

## 5.2 The one thing that connects the two services

[`backend/api-service/app/services/ai_client.py`](backend/api-service/app/services/ai_client.py):

```python
class AIServiceClient:
    async def health(self) -> dict[str, Any]:
        ...GET /health...

    async def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...POST /api/v1/inference/predict...
```

> ⚠️ **`infer()` is broken.** `ai-service` has 13 endpoints and
> `/api/v1/inference/predict` is not one of them. Calling
> `POST /api/v1/ai/infer` on `api-service` will always fail with 502.
> Recorded in [Part 35](#part-35--unknown--unclear--potential-issues).

`health()` works.

## 5.3 api-service status, honestly

`api-service` has: a health route, an in-memory user list, and the AI client.
It has **no** authentication, no database tables of substance, no migrations
written (`alembic/versions/` contains only `.gitkeep`), no upload, no review
workflow, and no national-code issuance. Everything in
[`docs/02_BACKEND_ARCHITECTURE.md`](docs/02_BACKEND_ARCHITECTURE.md) is a
specification, not a description.

**Consequence for you:** the review endpoint on `ai-service`
(`POST .../review`) takes a `reviewer` string from the caller and does not
verify it. That is correct given the architecture, and it is why `:8001` must
never be public. The same applies to `requested_by` on ingest-by-reference.

### What api-service still owes the ingest flow 🟡

`POST /api/v1/ingest/by-reference` is built and tested on the ai-service side.
The half that calls it is **not built**, and is owned by another developer:

| Piece | Status |
|---|---|
| ai-service reads a stored file by name | ✅ built |
| `import_job` / `import_row_error` provenance | ✅ built |
| api-service endpoint accepting `multipart/form-data` | ❌ not built |
| api-service writing the bytes into the shared `UPLOAD_DIR` | ❌ not built |
| `ai_client.ingest_by_reference()` | ❌ not built |
| The shared volume in `docker-compose.yml` | ❌ not wired |

Until that exists, exercise the endpoint by dropping a CSV into
`backend/ai-service/data/uploads/` and calling it directly.


---

# PART 6 — Database

## 6.1 Concepts from zero 🔴

| Term | Plain meaning | In this project |
|---|---|---|
| **PostgreSQL** | A program that stores data on disk and answers questions about it in SQL. | Version 16, in Docker. |
| **Database** | A named container of tables. | `numm_ai` (yours), `sih` (api-service's). |
| **Table** | A grid. Like one sheet in Excel. | `material`, `match_result`, … |
| **Row** | One record — one line of the grid. | one CPSE material. |
| **Column** | One field, with a fixed type. | `description_raw TEXT`. |
| **Primary key** | The column that uniquely identifies a row. | `id` (a UUID string). |
| **Foreign key** | A column pointing at another table's primary key. | `standardized_material.material_id` → `material.material_id`. |
| **Index** | A lookup structure that makes searching fast. | `ix_match_query`. |
| **Transaction** | A group of writes that all succeed or all fail. | one `session` = one transaction. |
| **Migration** | A versioned script that changes the schema. | **Not used in ai-service** — see below. |

> 🔴 **`ai-service` has no migrations.** Tables are created by
> `Base.metadata.create_all` at startup (`app/main.py`). `create_all` only
> creates *missing* tables — it **never alters an existing one**. So if you add
> a column to a model, you must drop the table (or the whole database) for it to
> appear. `api-service` has Alembic installed but zero migrations written.

## 6.2 The nine tables

```
                        material                        ← the raw CPSE row, never edited
                        ├─ id (PK, uuid)
                        ├─ material_id (UNIQUE)  "CCL-000001"
                        ├─ cpse_code, cpse_name, legacy_code
                        ├─ description_raw       ← NEVER MODIFIED
                        ├─ uom_raw, quantity, part_number_raw,
                        │  manufacturer_raw, specifications_raw
                        └─ created_at
                             │ 1
                             │
                             ▼ 1
              standardized_material                     ← everything derived
              ├─ id (PK)
              ├─ material_id (FK → material.material_id, UNIQUE)
              ├─ description_clean / _normalized / canonical_text
              ├─ category, category_confidence, category_method
              ├─ uom_normalized, uom_dimension
              ├─ missing_identity (JSON string)
              ├─ pipeline_version
              └─ canonical_hash, embedding_version, indexed_at   ← vector state
                   │ 1                        │ 1
                   ▼ n                        ▼ n
        material_attribute            quality_flag
        ├─ standardized_id (FK)       ├─ standardized_id (FK)
        ├─ name, value                ├─ code, severity
        ├─ numeric_value, unit        ├─ field, detail
        ├─ role, method, confidence   └─ raw_value
        └─ UNIQUE(standardized_id, name)


        match_result          ← REBUILT ON EVERY RUN (deleted then re-inserted)
        ├─ query_material_id, candidate_material_id
        ├─ confidence_score, confidence_kind
        ├─ relationship_type, hard_rule_status, proposed_before_rules, reason
        ├─ matched_ / conflicting_ / missing_ / inferred_attributes  (JSON)
        ├─ rules_triggered, signals, penalties, retrieved_by         (JSON)
        ├─ explanation                                              (JSON)
        └─ 8 version stamps

        review                ← A HUMAN DECISION. Survives every re-run.
        ├─ query_material_id, candidate_material_id
        ├─ relationship_at_review, confidence_at_review, reason_at_review
        ├─ matcher_version, rule_version
        ├─ match_result_id    ← soft reference, NO foreign key
        └─ reviewer, decision, comment, decided_at

        audit_log             ← append-only
        └─ actor, action, entity_type, entity_id, detail, occurred_at
```

## 6.3 The two design decisions worth understanding 🔴

### Why `review` has no foreign key to `match_result`

`match_result` is **ephemeral**. `run_matching()` starts with:

```python
await session.execute(delete(MatchResult))
```

Every matching run deletes the whole table and rebuilds it. If `review` had a
foreign key into it, re-running matching would either fail or cascade-delete
human decisions. So `review` copies the evidence it was made against
(`relationship_at_review`, `confidence_at_review`, `reason_at_review`) at
decision time, and keeps only a soft `match_result_id` string.

There is a test for exactly this in `tests/test_api.py`:

```python
def test_review_survives_a_rematch(client):
    """Re-running matching used to violate review's foreign key and 500."""
```

### Why raw and derived live in separate tables

`material` is written once at ingest and never updated. Every derived value
lands in `standardized_material` and its children. A CPSE can therefore always
see exactly what it sent, and re-running the pipeline never risks the original.

## 6.4 Indexes actually defined

| Index | Table | Why |
|---|---|---|
| `ix_match_query` | `match_result` | `(query_material_id, confidence_score)` — fetch one material's ranked matches |
| `ix_review_pair` | `review` | `(query_material_id, candidate_material_id)` |
| `ix_attribute_lookup` | `material_attribute` | `(name, value)` — "everything where grade = SS316" |
| `uq_attribute_per_material` | `material_attribute` | UNIQUE `(standardized_id, name)` — one value per attribute |
| plus single-column indexes | many | `material_id`, `cpse_code`, `category`, `canonical_hash`, `indexed_at`, … |

---

# PART 7 — ORM / Database Access

## 7.1 What an ORM is 🔴

Without an ORM you write SQL strings and get tuples back:

```python
rows = await conn.execute("SELECT description_raw FROM material WHERE cpse_code = 'NTPC'")
```

With an **ORM** (Object-Relational Mapper) you define a Python class per table
and work with objects:

```python
rows = await session.execute(select(Material).where(Material.cpse_code == "NTPC"))
```

This project uses **SQLAlchemy 2.0** in async mode with the **asyncpg** driver
(and **aiosqlite** for tests).

## 7.2 The vocabulary, mapped to this code

| Term | What it is | Where |
|---|---|---|
| **Model** | A class mapped to a table | `class Material(Base)` in `models/material.py` |
| **Base** | The parent every model inherits | `app/database.py` |
| **Engine** | The connection pool | `engine = create_async_engine(...)` |
| **Session** | One unit of work / one transaction | `AsyncSessionLocal()` |
| **`select()`** | Build a SELECT | `select(Material).where(...)` |
| **`session.add()`** | Stage an INSERT | `session.add(Material(...))` |
| **`session.execute()`** | Run a statement | everywhere |
| **`commit()`** | Make changes permanent | `await session.commit()` |
| **`rollback()`** | Undo | automatic on exception via `async with` |
| **`delete()`** | Build a DELETE | `delete(MatchResult)` |
| **`update()`** | Build an UPDATE | `services/indexing.py` |

## 7.3 A real read, line by line

From `services/materials.py`:

```python
async def quality_summary(session: AsyncSession) -> dict:
    rows = (await session.execute(
        select(QualityFlagRow.code, QualityFlagRow.severity, func.count())
        .group_by(QualityFlagRow.code, QualityFlagRow.severity)
    )).all()
    total = (await session.execute(select(func.count()).select_from(Material))).scalar_one()
```

| Piece | Meaning |
|---|---|
| `select(A, B, func.count())` | `SELECT code, severity, COUNT(*)` |
| `.group_by(...)` | `GROUP BY code, severity` |
| `await session.execute(...)` | send it, suspend until the DB replies |
| `.all()` | all rows as tuples |
| `.scalar_one()` | exactly one row, one column — raises if not |

## 7.4 Async database access 🔴

`async` here means: while this request waits on PostgreSQL, the same Python
process can serve other requests. It does **not** mean parallel threads.

Three consequences visible in the code:

1. Every DB call is `await`ed.
2. `get_db()` is an **async generator** — FastAPI runs it, takes the yielded
   session, and closes it after the response.
3. **Lazy loading is impossible.** In sync SQLAlchemy, touching
   `row.attributes` silently issues another query. Async cannot do that, which
   is why `load_standardized()` uses `selectinload` — see the comment in
   `services/ingest.py`.

## 7.5 Transactions in practice

```python
async with AsyncSessionLocal() as session:   # transaction begins
    session.add(review)
    session.add(AuditLog(...))
    await session.commit()                    # both rows land together
```

If an exception is raised before `commit()`, the `async with` block rolls back
everything. In `services/matching.py::review_match` the `Review` row and its
`AuditLog` row commit together — you cannot get one without the other.

---

# PART 8 — Pydantic / Schemas

## 8.1 What Pydantic is and why it exists 🔴

**Pydantic** turns a Python class with type hints into a validator.

```python
class ReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    comment: str | None = None
```

Post `{"reviewer": "", "decision": "APPROVED"}` and FastAPI returns **422**
automatically with a message naming the field. You wrote no validation code.

| Term | Meaning |
|---|---|
| **Deserialization** | JSON text → Python object (incoming) |
| **Serialization** | Python object → JSON text (outgoing) |
| **Validation** | Checking types and constraints during deserialization |
| **Type hint** | `reviewer: str` — Pydantic *enforces* these at runtime |

## 8.2 Why schemas exist separately from models

| | `app/models/` (SQLAlchemy) | `app/schemas/` (Pydantic) |
|---|---|---|
| Represents | a database table | the JSON contract |
| Changing it | changes the schema on disk | changes the API |

Keeping them apart means you can rename a column without breaking every client,
and you can hide internal columns from the API.

## 8.3 Every schema in this service

### `schemas/common.py`

```
Schema:     HealthResponse
Purpose:    the /health payload
Fields:     status: str · service: str · version: str · environment: str
Used by:    routes/health.py
```

### `schemas/material.py` — nine models

```
Schema:     AttributeOut
Purpose:    one extracted attribute, as the API shows it
Fields:     name, value, role: str, unit: str|None,
            numeric_value: float|None, confidence: float
Used by:    MaterialOut
```

```
Schema:     QualityFlagOut
Fields:     code, severity, field, detail, raw_value: str|None
Used by:    MaterialOut
```

```
Schema:     MaterialOut
Purpose:    one standardized material
Fields:     material_id, cpse_code, cpse_name, legacy_code,
            description_raw, description_normalized, canonical_text,
            category, category_confidence: float,
            uom_raw, uom_normalized: str|None, quantity: float|None,
            attributes: list[AttributeOut],
            missing_identity: list[str],
            quality_flags: list[QualityFlagOut]
Validation: types only
Used by:    GET /materials, GET /materials/{id}, MatchResponse.query
Built by:   services/materials.py::to_out()
```

```
Schema:     CandidateOut          ← the richest one; 20 fields
Purpose:    one scored candidate with its full evidence
Fields:     material_id, cpse_code, description_raw,
            relationship, confidence_score: float, confidence_kind,
            hard_rule_status, proposed_before_rules, capped_by_rules: bool,
            reason,
            matched_attributes / conflicting_attributes /
            missing_attributes / inferred_attributes / rules_triggered /
            advisories,
            signals: dict[str, float],      ← the arithmetic
            penalties: list[str],
            retrieved_by: list[str],
            explanation: dict               ← the stored evidence object
Used by:    MatchResponse
```

```
Schema:     MatchResponse
Fields:     query: MaterialOut, candidates: list[CandidateOut],
            compared: int, summary: dict[str, int],
            note: str  ← a DEFAULT VALUE that always ships:
                       "confidence_score is a deterministic heuristic, not a
                        calibrated probability. Hard rules can override it."
```

```
Schema:     IngestResponse      materials: int, categories: dict, quality_flags: dict
Schema:     MatchRunResponse    materials, stored, EXACT_DUPLICATE, NEAR_DUPLICATE,
                                FUNCTIONALLY_EQUIVALENT, NOT_EQUIVALENT  (all int)
Schema:     ReviewRequest       reviewer, decision (min_length=1), comment
Schema:     EvaluationResponse  evaluated, skipped, accuracy, macro_f1,
                                per_label: list[dict], errors: list[dict],
                                caveat: str  ← another always-present default
```

### `schemas/ingest.py` — three models

```
Schema:     IngestByReferenceRequest
Purpose:    what api-service sends after storing an uploaded file
Fields:     source: str (1..2048)
            mode: Literal["merge", "replace"] = "merge"
            original_filename: str | None (<=255)
            requested_by: str | None (<=120)
Validation: `mode` is a Literal, so "obliterate" is a 422 before any code runs
Used by:    routes/ingest.py
```

```
Schema:     ImportJobOut
Purpose:    the provenance record — returned on SUCCESS AND ON REJECTION
Fields:     id, status, source, resolved_path, original_filename,
            content_sha256, size_bytes, mode,
            total_rows, valid_rows, error_rows, materials_written,
            cpse_codes: list[str], detail, requested_by,
            duration_ms, created_at, errors: list[ImportRowErrorOut]
```

```
Schema:     ImportRowErrorOut
Fields:     row_number, column_name, error_code, message, raw_value
```

## 8.4 The connection you should hold in your head 🔴

```
JSON body
   ↓  FastAPI reads it
Pydantic schema (schemas/material.py)     ← 422 here if invalid
   ↓  passed as a typed object
Service function (services/matching.py)
   ↓
SQLAlchemy model (models/matching.py)
   ↓
PostgreSQL
```

---

# PART 9 — AI-Service: the complete pipeline

## 9.1 The actual pipeline

Two phases. **Phase A** runs once per material at ingest. **Phase B** runs per
candidate pair.

```
PHASE A — understand ONE material          app/logic/standardize.py::standardize()

  Two entry points feed this, differing ONLY in what they delete:
    POST /materials/ingest        reads RAW_DATASET_PATH, wipes everything
    POST /ingest/by-reference     reads UPLOAD_DIR, merge = per-CPSE replace

  Raw CSV row  ("brg ball rad 6205 2rs for main store")
        │
   S1   ▼  clean.py::clean()
        │     NFKC unicode · uppercase · strip 5 noise patterns
        │     → "BRG BALL RAD 6205 2RS"           + removed=["STORE_NOTE"]
   S2   ▼  tokenize.py::retokenize()
        │     protect M16X50, 1/2", SS-304 · split dimensions
        │     → "BRG BALL RAD 6205 2RS"
   S6a  ▼  classifier.py::classify_text()        ← PASS 1 (provisional)
        │     tier 1 keywords → BEARING (conf 0.95)
        │     the class chooses which extraction grammar applies
   S3   ▼  clean.py::expand_abbreviations()
        │     BRG→BEARING, RAD→RADIAL  (scoped to BEARING)
        │     → "BEARING BALL RADIAL 6205 2RS"
   S4   ▼  units.py  (used inside extraction)
        │     value + unit + SI + original literal; Pint dimensions
   S5.1 ▼  extract.py::extract()                 regex + gazetteer
        │     bearing_number=6205, bearing_type=BALL, seal_type=2RS
   S5.4 ▼  ner.py::ner_attributes()              spaCy — GAPS ONLY
   S5.5 ▼  llm.py::llm_attributes()              OFF by default
   S5.6 ▼  validate.py::apply_inference()
        │     6205 → bore=25 MM  status=INFERRED  "ISO 15 bore code 05 x 5 mm"
   S5.7 ▼  validate.py::validate_attributes()    6 rules; demote, never delete
   S6b  ▼  classifier.py::classify_two_pass()    ← PASS 2 (refine with attributes)
   S7   ▼  standardize.py::_build_canonical()
        │     → "BEARING: bearing_number=6205; bearing_type=BALL;
        │        bore=25 MM; seal_type=2RS"
        ▼
   StandardizedMaterial   +  quality_flags[]  +  missing_identity[]


PHASE B — compare TWO materials             app/logic/matcher.py::MatchingEngine.match()

   query material
        │
   R    ▼  candidates.py::UnionRetriever.retrieve()
        │     ┌ category_block   same category (exhaustive here)
        │     ├ fingerprint      identical identity attrs, O(1) hash
        │     ├ ann              Qwen3 → Qdrant, ACROSS categories
        │     └ trigram          RapidFuzz, catches typos
        │     union — may only ADD candidates, never remove
        │
   for each candidate:
   C    ▼  compare.py::compare()      MATCH / CONFLICT / MISSING / INFERRED
   S    ▼  score.py or fusion.py      weighted sum × penalties × G_uom
   RU   ▼  rules.py::evaluate()       5 rules; may only LOWER the verdict
   D    ▼  matcher.py::_decide()      the four-way verdict
   E    ▼  explain.py::build_explanation()
        ▼
   Candidate(relationship, score, comparison, rules, reason, explanation)
        ▼
   ranked by (relationship rank, score) — a high-scoring NOT_EQUIVALENT can
   never outrank a genuine near duplicate
```

## 9.2 The one architectural rule 🔴🔴

> **Semantics propose. Rules dispose.**

The embedding decides *which pairs to look at*. It never decides *what the
relationship is*. There is a test that enforces this — `test_retrieval_does_not_
change_the_verdict` in `tests/test_retrieval.py` runs the same pair through both
retrievers and asserts an identical relationship and identical score.

## 9.3 What is learned vs what is coded

| Component | Nature | Why |
|---|---|---|
| Cleaning, tokenising, units, fingerprints | **Deterministic** | must be reproducible and auditable |
| Attribute extraction | rules + dictionaries, ML-assisted | rules give precision *and* explanations |
| Classification | learned + zero-shot fallback | genuinely pattern recognition |
| Candidate retrieval | learned representation + ANN | only embeddings solve "different words, same thing" |
| Fusion + calibration | learned, **linear and inspectable** | fits data while staying explainable |
| **Hard gates** | **Deterministic** | **safety cannot be probabilistic** |
| Final approval | **Human** | accountability cannot be delegated to a model |

The guard-rail, from `docs/03` §6.1 and enforced in `fusion.py`:

> **A model must never be able to learn its way past a safety rule.**

`LearnedFusionMatcher.score()` re-applies the multiplicative penalties *on top
of* whatever the fitted model produced, so an identity conflict survives any
weighting. `test_a_learned_model_cannot_learn_past_a_penalty` proves it by
setting every coefficient to 50.0 and asserting the score still collapses.


---

# PART 10 — NLP

Only techniques that actually exist in this code.

## 10.1 Unicode normalisation + case folding 🔴

**What:** make visually identical text byte-identical.
**Why:** `"` and `”` are different characters; so are a normal space and a
non-breaking space.

**File:** `app/logic/clean.py::clean()`

```python
text = unicodedata.normalize("NFKC", description or "")
text = text.replace("&#x0d;", " ").replace("\xa0", " ")
text = text.upper()
```

**In:** `brg ball rad 6205 2rs` → **Out:** `BRG BALL RAD 6205 2RS`

> NFKC = "Normalization Form Compatibility Composition". It rewrites
> compatibility characters (`ﬁ` → `fi`) into canonical ones.

## 10.2 Noise removal by stop-pattern 🔴

**What:** delete procurement boilerplate that carries no engineering meaning.
**Why:** `- URGENT REQ` says nothing about the bearing.

**File:** `clean.py`, `NOISE_PATTERNS` — five regexes, all anchored to end-of-string:

```python
("URGENT_FLAG",   r"\s*-\s*URGENT\s+REQ\b\s*$"),
("OEM_FLAG",      r"\s*\*\*\s*OEM\s+ONLY\s*\*\*\s*$"),
("BOQ_REF",       r"\s*\(\s*BOQ\d*\s*REF\s*\)\s*$"),
("ATTACHED_SPEC", r"\s*REQ\s+AS\s+PER\s+ATTACHED\s+SPEC\b\s*$"),
("STORE_NOTE",    r"\s+FOR\s+MAIN\s+STORE\b\s*$"),
```

**Every removal is recorded** and becomes a `DESCRIPTION_NOISE` quality flag.
Nothing disappears silently.

## 10.3 Domain-aware tokenization 🔴

**What:** splitting text into tokens.
**Why here:** standard tokenizers destroy engineering notation.

**File:** `app/logic/tokenize.py` — 13 `PROTECTED` patterns matched *before* any
splitting, longest and most specific first.

| Pattern | Catches |
|---|---|
| `FRACTION_INCH` | `1/2"`, `3/4 IN` |
| `DECIMAL_INCH` | `2.5"`, `2"` |
| `INCH_UNIT` | `4IN`, `2 INCH` |
| `GRADE_SEP` | `SS-304` → `SS304` |
| `THREAD_DIM` | `M16X50` → `M16` · `X` · `50` |
| `CORE_AREA` | `3CX2.5SQMM` |
| `PRESSURE_CLASS` | `150#` |
| `NOMINAL_BORE` | `DN50`, `50NB` |
| `DESIGNATION` | `6205-2RS` |
| `NUM_UNIT` | `50MM`, `1.1KV` |

**Tokens carry character offsets** (`Token.start`, `Token.end`), which is what
lets the UI later highlight where a value came from.

## 10.4 Abbreviation expansion (a dictionary, not stemming) 🔴

**What:** replace a domain shorthand with its full form.
**Why:** `BRG` and `BEARING` must become the same token.

**File:** `clean.py::expand_abbreviations()`, driven by
`data/config/abbreviations.csv` (36 entries).

```python
for raw, expansion, scope in config.abbreviations:
    if scope and not (category or "").startswith(scope):
        continue                                     # ← category-scoped
    result = re.sub(rf"(?<![A-Z0-9]){re.escape(raw)}(?![A-Z0-9])", expansion, result)
```

Two subtleties:

1. **Longest-first ordering** (sorted in `reference.py`) so `GT VLV` wins over `VLV`.
2. **The lookaround guards** `(?<![A-Z0-9])` and `(?![A-Z0-9])` stop `RAD` from
   matching inside `RADIAL`.

> **There is no stemming and no lemmatization in this project.** A curated
> dictionary is used instead, because `BEARINGS → BEARING` is safe but a general
> stemmer would also do `BEARING → BEAR`.

> **There are no stopwords either.** Every token in a 40-character material
> description carries signal.

## 10.5 Unit normalization 🔴

Covered in [Part 4](#logicunitspy-362-lines--stage-s4) and
[Part 13](#part-13--matching-engine). File: `app/logic/units.py`, library:
**Pint**.

The key idea: **dimension is a type.** `dimensions_compatible("EA", "MM")` is
`False` not because someone wrote an if-statement, but because Pint knows a
count and a length are different dimensions.

## 10.6 Attribute extraction (regex + gazetteer) 🔴

**What:** turn prose into named, typed values.
**File:** `app/logic/extract.py`, patterns in `data/config/category_attributes.csv`.

One real config row:

```
BEARING,bearing_number,IDENTITY_DEFINING,"ISO designation fixes bore series and
geometry. A different number is a different bearing.",string,,"\b(\d{4,5})\b"
```

Columns: `category, attribute, role, why_it_matters, value_type, unit,
extraction_pattern`.

**Adding an attribute to a family is a CSV edit, not a code change.** That is the
single most important extensibility property of this service.

`_first_group()` handles a subtlety: if a pattern has capture groups, the first
non-empty group is the value; otherwise the whole match is.

## 10.7 Named Entity Recognition (spaCy) 🟡

**What:** a model that labels spans of text with categories.
**Why here:** to catch phrasings the regexes do not cover.

**File:** `app/logic/ner.py`; trained by `scripts/train_ner.py`.

**Trained by distant supervision** — the regex extractor already produces values
*with character spans*, and those spans are free training labels.

Measured on this repository: **297 training examples, 40 labels, held-out span
precision 0.831 / recall 0.682 / F1 0.749.**

Demonstrated behaviour on a phrasing the patterns miss:

```
"ISOLATION DEVICE BALL PATTERN NOMINAL 50 RATING 150 BODY WCB"
   patterns: [('body_material', 'WCB')]
   NER adds: [('pressure_class', '150', 0.62)]
```

## 10.8 Fuzzy matching (RapidFuzz) 🔴

**What:** how similar are two strings, tolerating typos and reordering.

Used in **two** places:

1. **A scoring signal** — `score.py`:
   ```python
   lexical = fuzz.token_set_ratio(left.description_normalized,
                                  right.description_normalized) / 100.0
   ```
   `token_set_ratio` splits both strings into word sets and compares them, so it
   is insensitive to word order.

2. **A retrieval path** — `candidates.py::_trigram_candidates()`, with
   `TRIGRAM_CUTOFF = 70.0` and `TRIGRAM_LIMIT = 10`. This is the stand-in for
   PostgreSQL's `pg_trgm`; it catches `STANLESS` for `STAINLESS` and finds
   `6205-2RS` far more reliably than cosine similarity does.

**Lexical similarity is deliberately weighted at only 0.10** — see Part 13.

## 10.9 Semantic similarity (embeddings) 🔴

See [Part 11](#part-11--embeddings).

---

# PART 11 — Embeddings

## 11.1 From zero 🔴

**A vector is a list of numbers.** `[0.12, -0.31, 0.82, ...]`. That is all.

**Why turn text into numbers?** Computers can measure distance between numbers.
They cannot measure "meaning" between strings.

```
"BEARING BALL 6205"
        ↓  embedding model (a neural network)
[0.021, -0.118, 0.334, ... ]      ← 1024 numbers in this project
```

**An embedding** is a vector positioned so that *similar meanings land near each
other*. `"BEARING BALL 6205"` and `"BALL BEARING 6205"` end up close together
even though the strings differ.

**Dimensions** = how many numbers. This project uses **1024**.

### Cosine similarity — intuition, then maths, then code

**Intuition.** Think of each vector as an arrow from the origin. Cosine
similarity asks: *do these two arrows point the same way?* It ignores how long
they are — only direction matters.

- Same direction → 1.0
- Perpendicular → 0.0
- Opposite → −1.0

**Maths.**

```
cos(A, B) = (A · B) / (‖A‖ × ‖B‖)

where A · B = a₁b₁ + a₂b₂ + ... + a₁₀₂₄b₁₀₂₄     (the dot product)
      ‖A‖   = sqrt(a₁² + a₂² + ... )              (the length)
```

**The shortcut this project uses.** If every vector is first scaled to length 1
(**L2 normalisation**), then `‖A‖ = ‖B‖ = 1`, so the formula collapses to just
the dot product. That is why `embedding.py` normalises at generation time:

```python
def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0     # a zero vector has no direction
    return (matrix / norms).astype(np.float32)
```

and why the in-memory store can do this:

```python
# Vectors are L2-normalised at generation, so cosine is a dot product.
scores = matrix @ vector.astype(np.float32)
```

`@` is NumPy's matrix-multiply. One line computes the similarity of the query
against *every* stored vector at once.

> **Euclidean distance** (straight-line distance) is **not used** in this
> project. Qdrant is configured with `Distance.COSINE`.

## 11.2 The exact model

```
Model:        Qwen/Qwen3-Embedding-0.6B
Library:      transformers (Hugging Face) + torch (PyTorch)
Dimensions:   1024   (verified: model.config.hidden_size == 1024)
Parameters:   ~0.6 billion
Device:       CPU
Batch size:   32
Licence:      Apache 2.0 — free, self-hosted, no API cost, no data egress
File:         app/logic/embedding.py::Qwen3EmbeddingProvider
```

## 11.3 The two providers 🔴

The code defines a **Protocol** (an interface) and two implementations:

```python
class EmbeddingProvider(Protocol):
    model_name: str
    model_version: str
    dimension: int
    def embed(self, texts, *, kind="document") -> np.ndarray: ...
    def info(self) -> ProviderInfo: ...
```

| Implementation | When | What it does |
|---|---|---|
| `Qwen3EmbeddingProvider` | `EMBEDDING_PROVIDER=qwen3` | the real model |
| `DeterministicProvider` | **default** | seeded hash → a stable but **meaningless** vector |

**Why a fake provider exists:** so the pipeline is exercisable without a 1.2 GB
download. Tests run in ~13 seconds. Retrieval quality is meaningless on it — and
the code says so out loud:

```python
detail=("Seeded-hash fallback. Vectors are stable but carry no semantic "
        "signal - retrieval recall is not meaningful on this provider.")
```

`GET /api/v1/retrieval/model/info` always reports `is_fallback`, so **a demo can
never silently claim Qwen3 quality on hash vectors.**

## 11.4 Model loading

```python
@lru_cache(maxsize=1)   # ← equivalent pattern via the module-level _provider
def get_provider(*, refresh: bool = False) -> EmbeddingProvider:
```

Loaded **once per process**, on first use, and kept warm. Never per request.

```python
self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, padding_side="left")
self._model = AutoModel.from_pretrained(self.model_name).to(self._device).eval()
self.dimension = int(self._model.config.hidden_size)

if self.dimension != settings.embedding_dimension:
    raise RuntimeError(...)   # never silently truncate or pad
```

That last check matters: padding or truncating a vector produces *plausible,
wrong neighbours*. Better to fail at startup.

## 11.5 What actually gets embedded 🔴

**The canonical form, never the raw text.** `embedding.py::embedding_text()`:

```
BEARING: bearing_number=6205; bearing_type=BALL; bore=25 MM; seal_type=2RS
[CLASS] BEARING
[ATTR]  bearing_number=6205; bearing_type=BALL; seal_type=2RS
[UOM]   NOS
```

Two deliberate choices:

1. **Normalisation happens before the encoder sees the text.** The model does
   not have to learn that `GSKT` means gasket — the dictionary already said so.
   Two records from different CPSEs converge on the same canonical string
   *before* the model is involved.
2. **`DESCRIPTIVE` attributes are excluded** from the `[ATTR]` block. Packaging
   and colour add tokens without adding retrieval signal, and dilute the vector.

## 11.6 Instruction prefixes and pooling 🟡

Qwen3-Embedding is *instruction-aware*, so documents and queries get different
prefixes:

```python
INSTRUCTIONS = {
    "document": "Represent this industrial material specification for retrieval: ",
    "query": ("Instruct: Given a material specification, retrieve the same physical "
              "article described differently.\nQuery: "),
}
```

> **They must be used consistently.** Embedding a document with the query prefix
> silently degrades retrieval — no error, just worse results.

**Pooling** turns the model's per-token outputs into one vector. Qwen3-Embedding
is trained for **last-token pooling**:

```python
def _pool(self, hidden, mask):
    left_padded = mask[:, -1].sum() == mask.shape[0]
    if left_padded:
        return hidden[:, -1]
    lengths = mask.sum(dim=1) - 1
    return hidden[self._torch.arange(hidden.shape[0]), lengths]
```

## 11.7 Batching, caching, staleness

- **Batching:** 32 texts per forward pass (`EMBEDDING_BATCH_SIZE`).
  `torch.inference_mode()` disables gradient tracking — inference only.
- **Caching:** the provider is a process-wide singleton. Vectors are cached *in
  Qdrant*, not in memory.
- **Staleness:** `canonical_hash()` is a SHA-1 over
  `embedding_version | embedding_text`. If a dictionary changes, the hash
  changes, and `services/indexing.py::_stale_ids()` finds exactly the affected
  rows. Re-running `POST /retrieval/index` re-embeds only those.

## 11.8 Error handling

| Failure | Behaviour |
|---|---|
| torch not installed, `EMBEDDING_PROVIDER=qwen3` | `RuntimeError` naming `requirements-ml.txt` |
| model dimension ≠ configured dimension | `RuntimeError` at load — never pad |
| Qdrant collection dimension mismatch | `RuntimeError` at `ensure_collection` |
| Qdrant unreachable | reported in `/retrieval/status`, never raised |
| empty input | returns an empty `(0, dim)` array, no crash |


---

# PART 12 — LLM

## 12.1 Concepts 🟡

| Term | Meaning |
|---|---|
| **LLM** | Large Language Model. Predicts the next token; can follow instructions written in prose. |
| **vs embedding model** | An embedding model outputs *one vector per text*. An LLM outputs *text*. Different jobs. |
| **Inference** | Running a trained model to get an answer (no learning happens). |
| **Token** | A chunk of text, roughly ¾ of a word. Models see tokens, not characters. |
| **Prompt** | The text you send. |
| **System prompt** | Instructions about *how to behave*. Here it is folded into one prompt. |
| **Temperature** | Randomness. `0.0` = as deterministic as the model gets. |
| **Structured output** | Forcing the reply into a machine-parseable shape (JSON here). |

## 12.2 The decision this project made 🔴

> **No LLM on the critical path.**

`USE_LLM_FALLBACK` defaults to **`False`**, and there is a test asserting it:

```python
def test_llm_fallback_is_off_by_default():
    assert settings.use_llm_fallback is False
```

The reasons, from `docs/03` and `app/logic/llm.py`:

1. **Auditability** — a national register must explain a decision years later.
2. **Determinism** — the same pair must not get different verdicts on different days.
3. It is **not better** at this task than regexes plus a cross-encoder, and is far
   more expensive on CPU.

The LLM is allowed exactly one job: extracting attributes from the ~3% of
descriptions nothing else could parse.

## 12.3 The complete integration

```
Caller:          app/logic/standardize.py, via llm.py::llm_attributes()
Model:           qwen2.5:3b-instruct        (LLM_MODEL)
Provider:        Ollama, running locally    (OLLAMA_URL, default :11434)
Endpoint:        POST {OLLAMA_URL}/api/generate
Transport:       httpx (synchronous)
Input:           normalized text + category + PipelineConfig + already-found attrs
Trigger:         ONLY when identity coverage < LLM_MIN_COVERAGE (0.5)
Expected format: a JSON object keyed by this category's attribute names
Parsing:         regex for the first {...} block, then json.loads
Validation:      keys outside the category schema are DISCARDED;
                 then the normal validate_attributes() rules run
Retry logic:     NONE — one attempt
Timeout:         LLM_TIMEOUT (30.0 s)
Failure:         raises LlmUnavailable internally; llm_attributes() returns []
Output tagging:  method=LLM, confidence=0.45, source_span=None
```

### The request

```python
httpx.post(
    f"{settings.ollama_url.rstrip('/')}/api/generate",
    json={
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",                              # Ollama's JSON mode
        "options": {"temperature": 0.0, "seed": 42},   # deterministic
    },
    timeout=timeout,
)
```

### The prompt (generated per category)

```
You extract structured attributes from industrial material descriptions.
Return ONLY a JSON object, no prose.

Category: BEARING
Attributes to look for:
  bearing_number (string)
  bearing_type (enum)
  seal_type (string)
  clearance (string)
  manufacturer (string)
  bore (number, in mm)

Rules:
  - Use ONLY the attribute names listed above.
  - Omit any attribute the description does not state. Do NOT guess.
  - Copy values as written; do not convert units.
  - An omitted attribute is correct when the text is silent.

Description: BRG 6205

JSON:
```

Note `"Omit any attribute the description does not state. Do NOT guess."` — that
is the `MISSING is not DIFFERENT` principle pushed into the prompt itself.

### The four safety constraints 🔴

1. **Schema-constrained** — anything outside `spec.attributes` is dropped:
   ```python
   if key not in schema or key in known or value in (None, "", []):
       continue
   ```
2. **Validated identically** — LLM output goes through the same
   `validate_attributes()` as everything else.
3. **Marked and discounted** — `method=LLM`, `confidence=0.45`, plus a note.
4. **Never identity-defining for auto-approval** — `source_span=None`, and
   `compare.py::LOW_TRUST_METHODS` contains `"LLM"` and `"NER"`. If *every*
   agreeing identity attribute is low-trust, `matcher.py::_decide()` caps the
   verdict at `NEAR_DUPLICATE`:

   ```
   "Identity agreement rests only on model-extracted values (...); no
    deterministically extracted identity attribute agrees on both sides."
   ```

### Failure behaviour, verified

```
flag off            -> []                       (never raises)
flag on, no ollama  -> LlmUnavailable: [Errno 111] Connection refused
gap-filling wrapper -> []                       (swallows it)
```

Ollama being down degrades the pipeline; it does not break it.

---

# PART 13 — Matching Engine

## 13.1 The order of operations

```
compare()   →  score()   →  evaluate()  →  _decide()
 evidence      a number     five rules     the verdict
```

Rules run **after** scoring and can only **lower** the outcome.

## 13.2 The comparison — four states 🔴

`app/logic/compare.py::compare()`:

```python
if a is None or b is None:              state = MISSING
elif not a.is_usable or not b.is_usable: state = MISSING   # INVALID counts as absent
elif _values_equal(a, b):
    state = INFERRED if (a.is_inferred or b.is_inferred) else MATCH
else:                                    state = CONFLICT
```

Numeric attributes compare on `numeric_value` (so `3/4` equals `0.75`);
everything else compares on the normalised string.

Derived signals:

```python
comparable         = len(matched) + len(conflicting) + len(inferred)   # MISSING excluded
match_ratio        = (len(matched) + 0.5 * len(inferred)) / comparable
identity_agreement = (identity_matches + 0.5 * identity_inferred) / identity_total
completeness       = comparable / len(attributes)
```

> **`MISSING` is in neither the numerator nor the denominator** of `match_ratio`
> and `identity_agreement`. It is not evidence for and not evidence against; it
> only lowers `completeness`, which is a statement about *how much was knowable*.

## 13.3 The scoring formula 🔴🔴

`app/logic/score.py`. Weights:

```python
WEIGHTS = {
    "identity_agreement":     0.45,
    "attribute_match_ratio":  0.20,
    "completeness":           0.10,
    "category_match":         0.15,
    "lexical":                0.10,     # RapidFuzz token_set_ratio
}
```

Penalties, applied **multiplicatively**:

```python
IDENTITY_CONFLICT_PENALTY       = 0.15   # raised to the power of the conflict count
DISCRIMINATING_CONFLICT_PENALTY = 0.75
MISSING_IDENTITY_PENALTY        = 0.80
```

The full computation:

```
raw   = Σ (weight × signal)                       # additive evidence
value = raw
      × 0.15^(identity conflicts)
      × 0.75^(discriminating conflicts)
      × 0.80^(missing identity attributes)
      × G_uom                                     # the UOM gate
value = clamp(value, 0.0, 1.0)
```

### Why penalties multiply rather than subtract

Two identity conflicts give `0.15² = 0.0225` — an order of magnitude worse than
one. A subtractive penalty would floor at zero and lose that distinction.

### Why structure carries 0.90 and text only 0.10

Two CPSEs describing the same bolt share almost no wording.
`HEX BOLT M16X65 GR8.8` and `BOLT HEXAGONAL 16MM X 65MM GRADE 8.8` have low
token overlap and are the same article. **Lexical similarity is a tie-breaker,
not evidence.**

The docs record that this was *corrected during development*: at a lexical
weight of 0.25, verified duplicates scored 0.855 and fell short of the 0.90
exact threshold.

### The UOM gate — three modes 🟡

```python
G_uom:  strict    → 0.0 on dimensional incompatibility
        damp      → 0.6
        advisory  → 1.0    ← DEFAULT
```

**Why advisory is the default here, with evidence.** Measured on this corpus:
**0% of attribute-identical material groups share a UOM.** Bearing `6205`
appears as `NOS`, `MT`, `MTR`, `BTL` and `SET`. The unit column carries no
signal. Measured effect of each mode on the 404-row corpus:

| Mode | EXACT | NEAR | NOT_EQUIVALENT |
|---|---|---|---|
| `advisory` | 1960 | 976 | 1084 |
| `damp` | 528 | 2408 | 1092 |
| `strict` | 528 | 248 | 3250 |

The mechanism exists for data where UOM is trustworthy; `UOM_GATE_MODE` raises it.

## 13.4 The five rules 🔴🔴

`app/logic/rules.py::evaluate()` runs all five and collects `RuleOutcome`s.

| Rule | Fires when | Status | Ceiling |
|---|---|---|---|
| `CATEGORY` | either side `UNCLASSIFIED` | `REVIEW` | `NEAR_DUPLICATE` |
| `CATEGORY` | categories differ | `REJECT` | `NOT_EQUIVALENT` |
| `IDENTITY_CONFLICT` | any IDENTITY attribute present on both sides with different values | `REJECT` | `NOT_EQUIVALENT` |
| `IDENTITY_EVIDENCE` | an IDENTITY attribute stated on one side only | `REVIEW` | `NEAR_DUPLICATE` |
| `DISCRIMINATING` | a DISCRIMINATING attribute conflicts | `REVIEW` | `FUNCTIONALLY_EQUIVALENT` |
| `UOM` | units incompatible | `REVIEW`, **advisory** | none |

**`advisory=True` findings are reported but never change the verdict:**

```python
@property
def binding(self) -> list[RuleOutcome]:
    return [o for o in self.outcomes if not o.advisory]
```

The ceiling is the **strictest** of all binding ceilings:

```python
return min(ceilings, key=lambda r: RELATIONSHIP_RANK[r])
```

And `reason` deliberately reports the finding that *actually changed* the
verdict, not merely the first one — the docs note that a downgraded pair once
cited the UOM advisory rather than the identity conflict that really caused it.

## 13.5 The verdict — exact conditions 🔴🔴

Step 1, `_propose()` — thresholds from `app/config.py`:

```python
if score >= 0.90:  EXACT_DUPLICATE          # settings.exact_threshold
if score >= 0.72:  NEAR_DUPLICATE           # settings.near_threshold
if score >= 0.55:  FUNCTIONALLY_EQUIVALENT  # settings.functional_threshold
else:              NOT_EQUIVALENT
```

Step 2, `_decide()` applies four independent caps **in order**:

```
1. if rules.rejected                       → NOT_EQUIVALENT
2. final = cap_relationship(proposed, rules.ceiling)     # rules may only lower

3. EXACT_DUPLICATE requires COMPLETE evidence:
   if identity_conflicts OR identity_missing OR schema_missing
                                           → NEAR_DUPLICATE

4. EXACT_DUPLICATE cannot rest only on model-extracted values:
   if every agreeing identity attribute is low-trust (NER/LLM)
                                           → NEAR_DUPLICATE

5. EXACT_DUPLICATE cannot rest only on derived values:
   if every agreeing identity attribute is INFERRED
                                           → NEAR_DUPLICATE

6. FUNCTIONALLY_EQUIVALENT is a POSITIVE claim, not a low score:
   unless a rule explicitly set that ceiling →
       NEAR_DUPLICATE if no conflicts, else NOT_EQUIVALENT
```

### So, precisely:

**`EXACT_DUPLICATE` requires all of:**
- score ≥ 0.90
- no rule rejected
- no rule ceiling below EXACT
- zero identity conflicts
- zero identity attributes missing on either side
- zero identity attributes the category expects that *neither* side states
- at least one agreeing identity attribute that is deterministically extracted
  and stated (not NER/LLM, not INFERRED)

**`NEAR_DUPLICATE`:** score ≥ 0.72, no conflicts, but evidence is incomplete —
or a stricter verdict was capped down to it.

**`FUNCTIONALLY_EQUIVALENT`:** only when a rule *explicitly* set that ceiling
(currently only the `DISCRIMINATING` rule). A merely low score never earns it.

**`NOT_EQUIVALENT`:** a rule rejected, or score < 0.55, or a demoted
FUNCTIONALLY_EQUIVALENT with conflicts.

> Note the asymmetry: **confidence alone can never buy `EXACT_DUPLICATE`.**
> This is the concrete implementation of "a false merge is the dangerous error".

## 13.6 Layer 7 — learned fusion and calibration 🟡

`app/logic/fusion.py` provides two wrappers, both satisfying the same `Matcher`
protocol, so `MatchingEngine(matcher=...)` is the whole integration.

| Class | `Score.kind` | What the number means |
|---|---|---|
| `DeterministicMatcher` | `heuristic_confidence` | a weighted sum under weights a person chose |
| `LearnedFusionMatcher` | `learned_confidence` | logistic regression over the same signals |
| `CalibratedMatcher` | `calibrated_probability` | isotonic-mapped onto observed precision |

`build_matcher()` picks whichever artefacts exist in `data/models/`, degrading in
a stated order.

**Calibration** (`app/logic/calibration.py`) fits isotonic regression, which is
**monotone** — it can change what a score *means* but never reorders candidates.

**Measured on this repository:**

```
usable pairs   58   positives 39   negatives 19
cross-val F1   1.000 +/- 0.000
calibration    ECE 0.0049 -> 0.0000

fitted weights (vs the hand-picked priors):
  identity_agreement       prior 0.45   fitted +2.106
  attribute_match_ratio    prior 0.20   fitted +2.057
  completeness             prior 0.10   fitted +0.811
  category_match           prior 0.15   fitted +0.182
  lexical                  prior 0.10   fitted +1.214
```

> 🔴 **Read that F1 of 1.000 as a warning, not a result.**
> `data/ground_truth/pairs.csv` was generated by `logic/ground_truth.py` from
> **the same extracted attributes the matcher compares**. Training on it teaches
> a model to reproduce the heuristic. `scripts/train_fusion.py` prints this
> caveat on every run. Real supervision needs engineer-confirmed pairs with hard
> negatives — two bearings differing only in seal type, two valves only in
> pressure class.

## 13.7 Ranking

```python
candidates.sort(key=lambda c: (RELATIONSHIP_RANK[c.relationship], c.score.value),
                reverse=True)
```

Relationship rank **first**, score second — so a high-scoring `NOT_EQUIVALENT`
can never outrank a genuine near duplicate.

## 13.8 Clustering 🟢

`matcher.py::cluster()` implements union-find (connected components) with path
compression over pairs at or above a given relationship. Returns groups of size
> 1. Currently **not exposed by any endpoint**.

---

# PART 14 — Candidate Generation

## 14.1 The problem

404 materials → 81,406 unordered pairs. At national scale (3M materials) it is
~10¹³ pairs. Comparing everything is impossible, so you must *narrow the field
first*.

## 14.2 The four paths, unioned 🔴

`app/logic/candidates.py::UnionRetriever.retrieve()`:

| Path | Finds | Cost | Implementation |
|---|---|---|---|
| **Category block** | same-family candidates | O(k) | list comprehension on `category` |
| **Exact fingerprint** | identical identity attributes, different wording | O(1) hash | `canonical_hash` equality |
| **ANN** | semantic neighbours **across** categories | ~5–20 ms | Qwen3 → Qdrant filtered search |
| **Trigram** | typos, terse codes, OEM part numbers | µs | RapidFuzz, cutoff 70, limit 10 |

> **The union may only ADD candidates, never remove one.** Asserted by
> `test_union_is_a_superset_of_blocking`.

### Blocking

```python
if query.category == UNCLASSIFIED:
    blocked = [m for m in corpus if m.material_id != query.material_id]
else:
    blocked = [m for m in corpus
               if m.material_id != query.material_id and m.category == query.category]
```

An **unclassified query blocks against nothing** and is compared to the whole
corpus. That is the safe direction — rather than hiding a record because the
classifier abstained, compare it widely and let the `CATEGORY` rule cap it at
`NEAR_DUPLICATE`.

> **Blocking is a recall boundary.** A material misclassified into the wrong
> family will never be compared against its true duplicate. That is the single
> largest source of missed matches in this design, and it is why classification
> abstains instead of guessing.

### The fingerprint guard 🔴

```python
if query.missing_identity or not query.attributes:
    return []
```

A fingerprint is emitted **only when every identity attribute the category
expects is present**. Otherwise two under-specified records would collide and
produce a false exact match — the precise failure this system exists to prevent.

### What ANN is actually for here

Category blocking is already **exhaustive inside a category** on this corpus
(404 materials / 21 categories ≈ 19 comparisons per query). So ANN cannot add
anything *within* a block. Its job is recovering from **classification error**,
which is why it deliberately does **not** filter by category:

```python
block = BlockingFilter(
    uom_dimensions=(query.uom_dimension,) if query.uom_dimension else (),
    exclude_ids=(query.material_id,),
    embedding_version=settings.embedding_version,
)
```

## 14.3 The vector store 🔴

`app/logic/retrieval.py` defines a `VectorStore` protocol and two backends:

| Backend | Search | Use |
|---|---|---|
| `InMemoryVectorStore` | exact, O(N) | default; tests; the ground truth ANN approximates |
| `QdrantStore` | approximate (HNSW), filtered | production |

Qdrant configuration:

```python
VectorParams(size=1024, distance=Distance.COSINE)
HnswConfigDiff(m=16, ef_construct=128, full_scan_threshold=10_000)
OptimizersConfigDiff(default_segment_number=2)
```

**HNSW** = Hierarchical Navigable Small World, a graph index that finds
approximate nearest neighbours in roughly logarithmic time instead of scanning
everything. `m` is how many links each node keeps; `ef_construct` is how hard it
searches while building.

**Payload indexes** are created on `category`, `cpse_code`, `uom_dimension`,
`embedding_version` and `material_id`, because filtered ANN is only fast if the
filter fields are indexed — and the filter must constrain the *traversal*, not
post-filter the results.

The last one is a different kind of entry from the other four. `material_id` is
not a blocking key; it carries the self-exclusion filter that every single
search sends, because a material must never retrieve itself. Section 14.3a
explains why it was missing until a cloud cluster refused the query.

**Top-K = 10** (`settings.top_k`).

## 14.3a Running against Qdrant Cloud 🟡

Everything above describes a Qdrant server. Nothing in it says *where* that
server runs, and that is deliberate — `QdrantStore` talks to a container on your
laptop and to a managed cluster with the same code. Two settings choose:

```bash
QDRANT_URL=https://<cluster-id>.<region>.aws.cloud.qdrant.io
QDRANT_API_KEY=[REDACTED SECRET]
```

A managed cluster serves REST on port 443, so no port is needed in the URL
(`:6333` also works and is what the client logs). A local container has no
authentication whatsoever; its key is empty, and an empty key is simply not
sent — hence one client construction for both:

```python
self._client = QdrantClient(
    url=url or settings.qdrant_url,
    api_key=key or None,          # empty -> omitted -> local container is happy
    timeout=settings.qdrant_timeout,
    prefer_grpc=settings.qdrant_prefer_grpc,
)
```

### What an API key actually is here 🔴

It is a **bearer credential**: possession is the whole of the authorisation.
There is no user behind it, no per-collection scope, no audit of who used it.
Anyone holding this string can read every vector, overwrite them, or delete the
collection. Treat it exactly as you would a database password:

- it lives in `.env`, which is gitignored;
- it never appears in `.env.example`, a Dockerfile, a compose file, a doc, or
  this guide — which is why the value above reads `[REDACTED SECRET]`;
- if it is ever pasted into a chat, a ticket, or a screenshot, **rotate it**.
  Revoking and reissuing is a two-click operation in the console, and there is
  no way to discover whether someone read it in the meantime.

### The bug the cloud found 🔴

This is the most instructive part of the exercise. The ten Qdrant integration
tests passed against the local container for weeks. Pointed at Qdrant Cloud,
nine passed and one failed:

```
400 Bad Request: Index required but not found for "material_id"
       of one of the following types: [keyword]
```

The managed cluster runs **strict mode**; the local container does not. Given a
filter on a payload field with no index, a local Qdrant shrugs and does a full
scan — slow, but correct, so nothing complains. Cloud refuses the query
outright.

The failing test was `test_a_material_never_retrieves_itself`, and it was not a
test problem. Every search in the system filters on `material_id`, so on a
managed cluster *every search would have failed* — in production, on a corpus
where the full scan would have been ruinous anyway.

The lesson is not "Qdrant Cloud is stricter". It is that a permissive
environment hides real defects, and the only reliable way to find them is to run
your tests against the thing you will actually deploy on:

```bash
QDRANT_TEST_URL=$QDRANT_URL QDRANT_TEST_API_KEY=$QDRANT_API_KEY \
  pytest tests/test_qdrant_integration.py
```

### Latency 🟡

Measured against a `ca-central-1` cluster from India:

| Operation | Local container | Qdrant Cloud |
|---|---|---|
| First search (TLS handshake) | ~5 ms | ~1,050 ms |
| Subsequent search | ~5 ms | ~490 ms |
| Indexing 404 materials | seconds | seconds (batched 256/request) |

Half a second per query is irrelevant for one lookup and decisive for match-all
over a large corpus — which is one more reason that path belongs in a background
job. Note that *upserts* barely suffer, because they are batched: 404 materials
is two round-trips, not 404.

`QDRANT_PREFER_GRPC=true` lowers per-call overhead but needs port 6334 open.
REST over 443 traverses every corporate proxy, so it stays the default.

### Why the test suite ignores your `.env` 🟡

`Settings` reads `.env`, so once `VECTOR_STORE=qdrant` points at a cloud
cluster, every search inside the API tests becomes a half-second network call.
Measured, that took `pytest -q` from **23 seconds to 7 minutes 36 seconds** —
and, worse, made a green test suite depend on someone else's uptime.

`tests/conftest.py` therefore pins the store to `memory` for the default run:

```python
@pytest.fixture(scope="session", autouse=True)
def _hermetic_vector_store():
    requested = os.getenv("TEST_VECTOR_STORE", "memory")
    settings.vector_store = requested
    retrieval.get_store(refresh=True)
```

This is a general principle worth taking away: **a test suite should not
silently inherit a developer's deployment configuration.** The in-memory store
is also the exact-search reference that the ANN path is defined against, so the
hermetic choice is the more meaningful one. Qdrant is still covered — by
`tests/test_qdrant_integration.py`, which is opt-in so the dependency is
*chosen* rather than inherited, and by `TEST_VECTOR_STORE=qdrant pytest -q`
when you want the whole suite to run against a real store.

### Verified end to end 🟢

Ingest → real Qwen3 embeddings → index into the cloud → search:

```
status  -> {'materials': 404, 'indexed': 404, 'awaiting_indexing': 0,
            'store': 'qdrant', 'store_reachable': True, 'store_error': None,
            'provider': {'model_name': 'Qwen/Qwen3-Embedding-0.6B',
                         'is_fallback': False}}

query 'ball bearing 6205 2rs'        -> 0.6975 BHEL BEARING
                                        0.6954 CCL  BEARING
query 'hex head bolt m16 stainless'  -> 0.6608 BCCL FASTENER
query 'gate valve 150mm cast iron'   -> 0.4917 ONGC VALVE
```

`is_fallback: False` is the proof these are real Qwen3 vectors and not the
deterministic hash provider, and the top hits crossing CPSE boundaries within
the right category is the whole point of the layer.

## 14.4 The measured result — read this 🔴

`make ablation`, run with the real Qwen3 model on this corpus:

```
corpus                404 materials, 21 categories
provider              Qwen/Qwen3-Embedding-0.6B (qwen3-0.6b-v1), 1024-d

candidates compared
  blocking only            9,356
  blocking + ANN + trgm   11,334   (1.21x)

pairs at NEAR_DUPLICATE or better
  blocking only            1,763
  with retrieval           1,763
  recovered                    0
  lost                         0
```

**ANN recovers nothing on this corpus today.** It surfaced ~2,000 extra
candidate pairs and the second stage correctly rejected every one. So it costs
work and adds no recall at this scale — while introducing no false positives
either.

That is the honest finding. The layer is kept because the *triggers* for it are
cheap to hold: a single category exceeding ~5,000 members, or descriptions
(other languages, transliteration, free-form vendor text) that keyword rules
cannot classify. Re-run `make ablation` when the corpus grows; a non-zero
`recovered` count is the signal it has begun to matter.

## 14.5 Keeping Postgres and Qdrant consistent 🟡

Qdrant gives no transactional consistency with PostgreSQL, so the gap is closed
explicitly rather than hoped away:

| Mechanism | Handles |
|---|---|
| `canonical_hash` in the payload and the DB | a stale vector whose source text changed |
| `indexed_at IS NULL` | everything awaiting indexing, in one query |
| `_stale_ids()` | compares stored hash + version against current |
| idempotent upsert | point id = `uuid5(material_id)`; a retried batch is harmless |
| startup dimension check | mismatch fails loudly rather than returning nonsense |


---

# PART 15 — Material Data Flow

One real material, `CCL-000001`, from CSV to verdict. Every step names the file
and function.

```
STEP 1 — the CSV row exists on disk
   backend/pipeline-one/CPSE_SIH26099.csv, line 2
   "Coal India (Central Coalfields Limited),brg ball rad 6205 2rs for main
    store,116045321,50,NOS,6205-2RS,SKF,ID 25mm OD 52mm W 15mm"

STEP 2 — HTTP request arrives
   POST /api/v1/materials/ingest
   app/routes/materials.py::ingest_dataset()

STEP 3 — read the file
   app/services/ingest.py::read_raw(settings.raw_dataset_path)
     · validates REQUIRED_COLUMNS (8 names) — raises if any is missing
     · csv.DictReader with encoding="utf-8-sig"  (strips a BOM if present)
     · RawMaterial.from_csv_row(row, i)   → source_row = 1
   OUT: list[RawMaterial], 404 items

STEP 4 — run the pipeline on every row
   app/services/ingest.py::standardize_all()
     → app/logic/standardize.py::standardize(raw, config)   ← per row

   4a  clean.py::clean()
       "brg ball rad 6205 2rs for main store"
       → "BRG BALL RAD 6205 2RS"        removed=["STORE_NOTE"]

   4b  tokenize.py::retokenize()        → "BRG BALL RAD 6205 2RS"

   4c  classifier.py::classify_text()   → BEARING (KEYWORD, 0.95)   PASS 1

   4d  clean.py::expand_abbreviations(text, config, "BEARING")
       BRG→BEARING, RAD→RADIAL
       → "BEARING BALL RADIAL 6205 2RS"

   4e  extract.py::extract()
       bearing_number = "6205"   IDENTITY_DEFINING  REGEX  span(17,21)
       bearing_type   = "BALL"   IDENTITY_DEFINING  DICT   span(8,12)
       seal_type      = "2RS"    DISCRIMINATING     REGEX  span(22,25)

   4f  ner.py::ner_attributes()         → []  (patterns already found everything)
   4g  llm.py::llm_attributes()         → []  (flag off)

   4h  validate.py::apply_inference()
       bore = "25 MM"  INFERRED  conf 0.90
       note "Derived from designation 6205 (ISO 15 bore code 05 x 5 mm); not stated."

   4i  validate.py::validate_attributes()   all 6 rules pass

   4j  classifier.py::classify_two_pass()   → still BEARING

   4k  clean.py::normalize_uom("NOS")   → ("NOS", "COUNT")

   4l  quality.py  ×4 checks
       DESCRIPTION_NOISE (INFO) — "Removed procurement noise: STORE_NOTE."

   4m  standardize.py::_build_canonical()
       "BEARING: bearing_number=6205; bearing_type=BALL; bore=25 MM; seal_type=2RS"

   4n  material_id = f"{cpse_code}-{source_row:06d}"  → "CCL-000001"

   OUT: StandardizedMaterial

STEP 5 — write to PostgreSQL
   app/services/ingest.py::persist()
     · DELETEs all four tables first (replace=True) — ingest is a full reload
     · INSERT material                 (raw, never touched again)
     · INSERT standardized_material    (derived)
     · INSERT material_attribute × 4
     · INSERT quality_flag × 1
     · await session.commit()

STEP 6 — export + audit
   export_jsonl()  → data/standardized/materials.jsonl
   AuditLog(actor="system", action="INGEST", ...)

STEP 7 — embed and index
   POST /api/v1/retrieval/index  →  app/services/indexing.py::reindex()
     · load_standardized(session)          rebuild objects from the DB
     · _stale_ids()                        which rows need re-embedding
     · build_points()  → embedding.embed([embedding_text(m)], kind="document")
     · store.upsert(points)                → Qdrant, id = uuid5(material_id)
     · UPDATE standardized_material SET canonical_hash, embedding_version, indexed_at

STEP 8 — match
   GET /api/v1/materials/CCL-000001/matches
   app/routes/matching.py → services/matching.py::match_one()
     · load_standardized()
     · build_engine()                      picks learned/calibrated if trained
     · MatchingEngine.match(query, corpus)
         - UnionRetriever.retrieve()       → ~50 candidates
         - for each: compare → score → evaluate → _decide → build_explanation
         - sort, take top_k

   RESULT for CCL-000001 (measured):
     CCL-000056     EXACT_DUPLICATE   0.954
     BHEL-000071    EXACT_DUPLICATE   0.954
     CCL-000118     EXACT_DUPLICATE   0.954

STEP 9 — persist all matches
   POST /api/v1/materials/match-all → services/matching.py::run_matching()
     · DELETE FROM match_result            (rebuilt every run)
     · for every material × every candidate: _to_row() → session.add()
     · NOT_EQUIVALENT is DROPPED by default (keep_not_equivalent=False)
       — on 404 materials they are the large majority and add nothing a
         reviewer acts on
     · measured: materials=404, stored=2946, exact=1951, near=985

STEP 10 — human decision
   POST /api/v1/materials/matches/{id}/review
   services/matching.py::review_match()
     · pins relationship_at_review / confidence_at_review / reason_at_review
     · INSERT review + INSERT audit_log, one transaction

STEP 11 — national code issuance
   ✗ NOT IMPLEMENTED. Belongs to api-service, which is a scaffold.
```

---

# PART 16 — Important Data Structures

## 16.1 Enums — `app/logic/enums.py` 🔴

| Enum | Values | Why it exists |
|---|---|---|
| `AttributeRole` | IDENTITY_DEFINING, DISCRIMINATING, DESCRIPTIVE | decides whether a conflict is a veto, a penalty or ignored |
| `Relationship` | EXACT_DUPLICATE, NEAR_DUPLICATE, FUNCTIONALLY_EQUIVALENT, NOT_EQUIVALENT | the four answers |
| `RuleStatus` | PASS, REVIEW, REJECT | what a rule concluded |
| `ComparisonState` | MATCH, CONFLICT, MISSING, INFERRED | four states, never two |
| `AttributeStatus` | PRESENT, MISSING, INFERRED, INVALID | how much to trust a value |
| `ExtractionMethod` | REGEX, DICT, GRAMMAR, NER, LLM, INFERRED, HUMAN, DEFAULT | where a value came from |
| `Severity` | INFO, WARNING, ERROR | quality-flag seriousness |

All are `StrEnum`, so `AttributeRole.IDENTITY_DEFINING == "IDENTITY_DEFINING"`
is `True` — they serialise to JSON and compare against strings without fuss.

`RELATIONSHIP_RANK` is the ordering that makes "rules may only lower a verdict"
expressible:

```python
RELATIONSHIP_RANK = {
    Relationship.NOT_EQUIVALENT: 0,
    Relationship.FUNCTIONALLY_EQUIVALENT: 1,
    Relationship.NEAR_DUPLICATE: 2,
    Relationship.EXACT_DUPLICATE: 3,
}
```

## 16.2 Dataclasses 🔴

| Dataclass | File | Frozen? | Role |
|---|---|---|---|
| `RawMaterial` | standardize.py | no | one CSV row, exactly as supplied |
| `StandardizedMaterial` | standardize.py | no | **the central object** — everything derived |
| `ExtractedAttribute` | extract.py | **yes** | one typed attribute with provenance |
| `QualityFlag` | quality.py | yes | one data-quality finding |
| `Classification` | classify.py | yes | category + confidence + method |
| `AttributeSpec` / `CategorySpec` | reference.py | yes | the CSV config, parsed |
| `PipelineConfig` | reference.py | no | all config in one object |
| `AttributeComparison` / `ComparisonResult` | compare.py | yes / no | per-attribute evidence |
| `Score` | score.py | yes | value + kind + version + signals + penalties |
| `RuleOutcome` / `RuleVerdict` | rules.py | yes / no | one rule's finding / all five |
| `Candidate` / `MatchOutcome` | matcher.py | no | a scored pair / a ranked set |
| `Token` | tokenize.py | yes | text + offsets + protected flag |
| `Quantity` / `UomResolution` | units.py | yes | a measurement / a resolved unit |
| `MaterialPoint` / `BlockingFilter` / `RetrievedCandidate` | retrieval.py | yes | vector + payload / a filter / a hit |
| `CandidateSet` | candidates.py | no | union result + provenance per path |
| `ProviderInfo` | embedding.py | yes | which model answered |
| `CalibrationCurve` | calibration.py | yes | the isotonic knots |
| `VersionStamp` | versions.py | yes | the 8 stamps |
| `GoldPair` | ground_truth.py | no | one labelled pair |
| `RowError` / `ParseResult` | reference_ingest.py | yes / no | one quarantined row / a parsed file |
| `LabelMetrics` / `EvaluationReport` | metrics.py | no | precision/recall/F1 |

**Why `frozen=True` on so many:** an immutable object cannot be modified by
accident three call-frames away. To change one you use
`dataclasses.replace(attr, confidence=0.35)`, which produces a *new* object —
which is exactly what `validate.py` does.

## 16.3 Protocols (interfaces) 🟡

```python
class Matcher(Protocol):            # score.py
    version: str
    def score(self, left, right, comparison) -> Score: ...

class EmbeddingProvider(Protocol):  # embedding.py
    def embed(self, texts, *, kind="document") -> np.ndarray: ...

class VectorStore(Protocol):        # retrieval.py
    def upsert(...); def search(...); def delete(...); def count(...)

class Retriever(Protocol):          # matcher.py
    def retrieve(self, query, corpus) -> CandidateSet: ...
```

A `Protocol` is **structural typing**: any class with the right methods
satisfies it — no inheritance needed. These four are the seams where you swap
implementations without touching anything else.

## 16.4 SQLAlchemy models

Seven, covered in [Part 6](#part-6--database).

## 16.5 Pydantic DTOs

Ten, covered in [Part 8](#part-8--pydantic--schemas).

---

# PART 17 — Python Concepts Used

Only concepts that genuinely appear in this repository.

## Beginner 🔴

```
Concept:  f-strings
Why:      building ids and messages
File:     app/logic/standardize.py
Example:  material_id=f"{code}-{raw.source_row:06d}"      → "CCL-000001"
```

```
Concept:  list / dict / set comprehensions
Why:      the codebase prefers them to loops throughout
File:     app/logic/candidates.py
Example:  blocked = [m for m in corpus if m.category == query.category]
```

```
Concept:  dictionaries as lookup tables
Why:      config that is data, not branching code
File:     app/logic/units.py
Example:  _UOM_TO_PINT = {"EA": "piece", "NOS": "piece", ...}
```

```
Concept:  exceptions and try/except
Why:      degrade instead of crash
File:     app/logic/llm.py
Example:  except Exception as exc: raise LlmUnavailable(str(exc)) from exc
```

```
Concept:  ternary expressions
File:     app/logic/compare.py
Example:  state = INFERRED if (a.is_inferred or b.is_inferred) else MATCH
```

## Intermediate 🔴

```
Concept:  type hints
Why:      Pydantic and FastAPI ENFORCE them at runtime; they are not comments
File:     everywhere
Example:  def compare(left: StandardizedMaterial, right: StandardizedMaterial) -> ComparisonResult
```

```
Concept:  dataclasses
Why:      a class with fields, without writing __init__ / __repr__ / __eq__
File:     app/logic/extract.py
Example:  @dataclass(frozen=True)
          class ExtractedAttribute: ...
```

```
Concept:  dataclasses.replace()
Why:      "change" a frozen object by making a new one
File:     app/logic/validate.py
Example:  return replace(attribute, status=AttributeStatus.INVALID, note=...)
```

```
Concept:  @property
Why:      a computed value that reads like a field
File:     app/logic/compare.py
Example:  @property
          def match_ratio(self) -> float: ...
```

```
Concept:  decorators
Why:      FastAPI routing, caching
File:     app/routes/materials.py, app/logic/reference.py
Example:  @router.get("/{material_id}", response_model=MaterialOut)
          @lru_cache
```

```
Concept:  async / await
Why:      serve other requests while waiting on the database
File:     every route and service
Example:  materials = await load_standardized(session)
```

```
Concept:  async context managers
Why:      guarantee cleanup even on error
File:     app/database.py
Example:  async with AsyncSessionLocal() as session:
              yield session
```

```
Concept:  async generators
Why:      FastAPI dependencies that need teardown
File:     app/database.py::get_db  (yields once, then closes)
```

```
Concept:  StrEnum
Why:      an enum that IS a string — serialises straight to JSON
File:     app/logic/enums.py
```

```
Concept:  dependency injection
Why:      routes declare what they need; FastAPI supplies it
File:     app/routes/*.py
Example:  session: AsyncSession = Depends(get_db)
```

## Advanced 🟡

```
Concept:  typing.Protocol (structural typing)
Why:      swap implementations without inheritance
File:     app/logic/score.py, embedding.py, retrieval.py, matcher.py
```

```
Concept:  singleton via module-level state
Why:      load a 1.2 GB model once per process
File:     app/logic/embedding.py
Example:  _provider: EmbeddingProvider | None = None
          def get_provider(*, refresh=False): ...
```

```
Concept:  lazy imports inside functions
Why:      keep torch out of a process that will never use it
File:     app/logic/embedding.py::Qwen3EmbeddingProvider.__init__
Example:  import torch          # inside __init__, not at module top
```

```
Concept:  union-find with path compression
Why:      group materials into duplicate clusters
File:     app/logic/matcher.py::cluster()
Example:  while parent[x] != x:
              parent[x] = parent[parent[x]]
              x = parent[x]
```

```
Concept:  TYPE_CHECKING guard
Why:      import a type for annotations without a runtime circular import
File:     app/logic/explain.py
Example:  if TYPE_CHECKING:
              from app.logic.rules import RuleVerdict
```

```
Concept:  NumPy vectorised operations
Why:      compare one vector against thousands in one operation
File:     app/logic/retrieval.py
Example:  scores = matrix @ vector          # NOT a Python loop
```

---

# PART 18 — Python Libraries

## Web / API

```
Library:   fastapi (>=0.118.0)
Purpose:   web framework — routing, validation, OpenAPI docs
Used in:   app/main.py, app/routes/*, app/auth.py
APIs used: FastAPI, APIRouter, Depends, HTTPException, Query, Header, status
If removed: no HTTP interface at all
```

```
Library:   uvicorn[standard]
Purpose:   the ASGI server that actually listens on a TCP port
Used in:   Dockerfile CMD, Makefile dev-ai
If removed: nothing serves requests
```

```
Library:   httpx (>=0.28.0)
Purpose:   HTTP client
Used in:   app/logic/llm.py (Ollama); tests via TestClient
If removed: LLM fallback breaks; tests break
```

## Database

```
Library:   sqlalchemy (>=2.0.43)
Purpose:   the ORM
Used in:   app/database.py, app/models/*, every service
APIs used: DeclarativeBase, Mapped, mapped_column, relationship,
           select, delete, update, func, selectinload, create_async_engine
If removed: rewrite every query as raw SQL
```

```
Library:   asyncpg (>=0.30.0)      the async PostgreSQL driver (production)
Library:   aiosqlite (>=0.20.0)    the async SQLite driver (tests)
Library:   greenlet (>=3.0.0)      SQLAlchemy's async bridge — never imported
                                   directly, but the async ORM fails without it
```

```
Library:   pydantic (>=2.11.0) / pydantic-settings (>=2.10.0)
Purpose:   validation + settings from environment
Used in:   app/schemas/*, app/config.py
If removed: no request validation, no typed configuration
```

## AI / ML

```
Library:   torch (>=2.4.0)                          [requirements-ml.txt — OPTIONAL]
Purpose:   the neural-network runtime
Used in:   app/logic/embedding.py, lazily imported
APIs used: inference_mode, set_num_threads, arange
If removed: EMBEDDING_PROVIDER=qwen3 raises; deterministic fallback still works
```

```
Library:   transformers (>=4.51.0)                  [requirements-ml.txt — OPTIONAL]
Purpose:   load Hugging Face models
Used in:   app/logic/embedding.py
APIs used: AutoTokenizer.from_pretrained, AutoModel.from_pretrained
```

```
Library:   qdrant-client (>=1.12.0)
Purpose:   talk to the Qdrant vector database
Used in:   app/logic/retrieval.py, lazily imported
APIs used: QdrantClient, VectorParams, Distance, HnswConfigDiff, PointStruct,
           Filter, FieldCondition, MatchAny, MatchValue, PayloadSchemaType
If removed: VECTOR_STORE=memory still works
```

```
Library:   numpy (>=2.0.0)
Purpose:   vector arithmetic
Used in:   embedding.py, retrieval.py, calibration.py, scripts/ablation.py
APIs used: ndarray, linalg.norm, vstack, argsort, @ (matmul), interp
If removed: no embeddings, no similarity
```

```
Library:   scikit-learn (>=1.5.0)
Purpose:   the classical-ML models
Used in:   classifier.py (LogisticRegression), calibration.py
           (IsotonicRegression), scripts/train_*.py (train_test_split,
           cross_val_score)
If removed: classifier tiers 2–3 and calibration are gone; heuristics remain
```

```
Library:   joblib (>=1.4.0)
Purpose:   save/load the fitted sklearn model to disk
Used in:   app/logic/classifier.py, scripts/train_classifier.py
```

```
Library:   spacy (>=3.7.0)
Purpose:   the NER model (extraction step 4)
Used in:   app/logic/ner.py, scripts/train_ner.py
APIs used: spacy.blank, add_pipe("ner"), Example.from_dict, minibatch, to_disk
If removed: USE_NER has no effect; patterns still run
```

## NLP / text

```
Library:   rapidfuzz (>=3.9.0)
Purpose:   fast fuzzy string similarity
Used in:   score.py (lexical signal), candidates.py (trigram retrieval)
APIs used: fuzz.token_set_ratio, process.extract
If removed: the lexical signal and one retrieval path disappear
```

```
Library:   pint (>=0.24)
Purpose:   units with real dimensional analysis
Used in:   app/logic/units.py
APIs used: UnitRegistry, define, Quantity, dimensionality, to_base_units, to
If removed: the UOM gate degrades to string comparison — EA vs MM would
            compare "equal enough" by accident
```

## Standard library worth naming 🟡

`csv`, `re`, `hashlib`, `json`, `unicodedata`, `dataclasses`, `enum`,
`functools.lru_cache`, `pathlib.Path`, `datetime`, `uuid`, `itertools`,
`random`, `collections.Counter/defaultdict`, `hmac`, `contextlib`.

## Testing / DevOps

```
Library:   pytest (>=8.4.0) + pytest-asyncio (>=1.2.0)
Purpose:   the test framework; asyncio_mode = "auto" in pyproject.toml means
           async test functions need no decorator
```

```
Library:   ruff (>=0.14.0)     linter + formatter; line-length 100;
                               rules E, F, I, UP, B
Library:   mypy (>=1.18.0)     static type checker — installed, and NOT wired
                               into CI (see Part 35)
```

> **Declared but never imported:** `tenacity>=9.1.0` in `pyproject.toml`. See
> [Part 35](#part-35--unknown--unclear--potential-issues).


---

# PART 19 — Docker

## 19.1 Concepts 🟡

| Term | Plain meaning |
|---|---|
| **Image** | A frozen snapshot of a filesystem plus a start command. A recipe's output. |
| **Container** | A running instance of an image. Many containers, one image. |
| **Dockerfile** | The recipe that builds an image. |
| **Layer** | One instruction in a Dockerfile. Layers are cached — this is why `COPY requirements.txt` comes *before* `COPY . .`: changing your code does not force a dependency reinstall. |
| **Port** | `"8001:8001"` = host port : container port. |
| **Volume** | Storage that outlives the container. |
| **Environment variable** | Configuration passed in from outside. |
| **Docker Compose** | Runs several containers together with one command. |
| **Service** | One named container in a compose file. |

## 19.2 The ai-service Dockerfile

```dockerfile
FROM python:3.12-slim AS base            # ← 3.12 exactly; see Part 35

ENV PYTHONUNBUFFERED=1                   # logs appear immediately, not buffered
    PYTHONDONTWRITEBYTECODE=1            # no .pyc clutter
    PIP_NO_CACHE_DIR=1                   # smaller image

WORKDIR /srv

RUN apt-get install build-essential curl # build-essential: compile wheels
                                         # curl: used by HEALTHCHECK

COPY requirements.txt ./                 # ← cached layer
RUN pip install -r requirements.txt

COPY . .                                 # ← changes often, so it comes last

EXPOSE 8001

HEALTHCHECK CMD curl -fsS http://localhost:8001/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

> Note it installs `requirements.txt`, **not** `requirements-ml.txt`. The image
> therefore ships **without torch**, and runs on the deterministic provider by
> default. That is why `docker-compose.yml` sets
> `EMBEDDING_PROVIDER: ${EMBEDDING_PROVIDER:-deterministic}`.

`.dockerignore` excludes `__pycache__`, `.venv`, `.env`, caches and `tests/`.

## 19.3 The five compose services

```yaml
postgres:      postgres:16-alpine
               volume postgres_data
               mounts scripts/init-db.sql into docker-entrypoint-initdb.d/
               healthcheck: pg_isready

api-service:   built from backend/api-service
               DATABASE_URL → postgres:5432/sih
               AI_SERVICE_URL → http://ai-service:8001
               depends_on: postgres healthy
               mounts source for --reload

qdrant:        qdrant/qdrant:v1.19.0
               volume qdrant-data
               healthcheck uses a bash /dev/tcp probe because the image
               has no curl

ai-service:    built from backend/ai-service
               DB_* → postgres, database numm_ai
               RAW_DATASET_PATH → /srv/data/raw/CPSE_SIH26099.csv
               EMBEDDING_PROVIDER / VECTOR_STORE / QDRANT_URL /
               QDRANT_API_KEY / ANN_ENABLED
               mounts ./backend/pipeline-one → /srv/data/raw  :ro   ← READ-ONLY
               depends_on: postgres healthy AND qdrant healthy

frontend:      Next.js, NEXT_PUBLIC_API_URL → localhost:8000
```

## 19.4 Startup order

```
docker compose up
      │
      ├─ postgres starts → runs init-db.sql (first boot only) → healthcheck passes
      ├─ qdrant starts   → healthcheck passes
      │
      ├─ api-service waits for postgres, then starts
      ├─ ai-service  waits for BOTH, then starts
      │                  ↓
      │            uvicorn → app/main.py → lifespan → create_all → ready
      └─ frontend waits for api-service
```

> ⚠️ **Qdrant version upgrades are not seamless.** The storage format changed
> between v1.12 and v1.19; the newer server refuses to read the older volume and
> the container crash-loops. Because the index is derived state the fix is
> one-line:
> ```bash
> docker compose down qdrant
> docker volume rm sih-2026_qdrant-data
> docker compose up -d qdrant && make index
> ```

---

# PART 20 — Environment Variables

Every variable referenced anywhere. `ai-service` reads all of these through
`app/config.py` — **nothing else in the service reads `os.environ`**.

| Variable | Purpose | Used by | Required? | Type / default |
|---|---|---|---|---|
| `ENVIRONMENT` | label shown by `/health` | ai-service | no | str `development` |
| `DEBUG` | DEBUG-level logging | ai-service | no | bool `true` |
| `HOST` / `PORT` | bind address | ai-service | no | str / int `8001` |
| `API_V1_PREFIX` | route prefix | ai-service | no | str `/api/v1` |
| `CORS_ORIGINS` | allowed browser origins | ai-service | no | list, localhost only |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` | connection parts | ai-service | no | `127.0.0.1` / `5432` / `numm_ai` / `sih` |
| `DB_PASSWORD` | database password | ai-service | **yes in prod** | `[REDACTED SECRET]` |
| `DB_SSL` / `DB_SSLMODE` | TLS to Postgres | ai-service | no | bool `false` / str `prefer` |
| `DB_ECHO` | log every SQL statement | ai-service | no | bool `false` |
| `DATABASE_URL` | full URL, overrides the `DB_*` parts | ai-service, api-service | no | str / None |
| `CONFIG_DIR` | where the CSVs live | ai-service | no | `data/config` |
| `RAW_DATASET_PATH` | the CPSE extract | ai-service | no | `../pipeline-one/CPSE_SIH26099.csv` |
| `GROUND_TRUTH_PATH` | gold labels | ai-service | no | `data/ground_truth/pairs.csv` |
| `STANDARDIZED_EXPORT_PATH` | JSONL export | ai-service | no | `data/standardized/materials.jsonl` |
| `UPLOAD_DIR` | the **only** directory a reference may resolve inside | ai-service | no | `data/uploads` |
| `ALLOW_REMOTE_REFERENCE` | permit `http(s)://` sources — SSRF risk | ai-service | no | bool **`false`** |
| `REMOTE_FETCH_TIMEOUT` | seconds, remote fetch | ai-service | no | float `30.0` |
| `MAX_REFERENCE_BYTES` | refuse a bigger file | ai-service | no | int `104857600` (100 MB) |
| `MAX_ROW_ERROR_RATE` | above this, reject the whole file | ai-service | no | float `0.30` |
| `EMBEDDING_PROVIDER` | `qwen3` or `deterministic` | ai-service | no | `deterministic` |
| `EMBEDDING_MODEL` | HF model id | ai-service | no | `Qwen/Qwen3-Embedding-0.6B` |
| `EMBEDDING_VERSION` | stamp on every vector | ai-service | no | `qwen3-0.6b-v1` |
| `EMBEDDING_DIMENSION` | must match the model | ai-service | no | int `1024` |
| `EMBEDDING_BATCH_SIZE` | texts per forward pass | ai-service | no | int `32` |
| `EMBEDDING_DEVICE` | `cpu` / `cuda` | ai-service | no | `cpu` |
| `VECTOR_STORE` | `qdrant` or `memory` | ai-service | no | `memory` |
| `QDRANT_URL` | server address — local container, or a Qdrant Cloud endpoint | ai-service | no | `http://127.0.0.1:6333` |
| `QDRANT_API_KEY` | **secret.** Required by Qdrant Cloud, ignored by a local container | ai-service | only for Cloud | empty |
| `QDRANT_COLLECTION` | collection name | ai-service | no | `material_embeddings` |
| `QDRANT_TIMEOUT` | seconds per request; raise to ~30 for Cloud | ai-service | no | float `10.0` |
| `QDRANT_PREFER_GRPC` | gRPC on port 6334 instead of REST | ai-service | no | bool `false` |
| `HNSW_M` / `HNSW_EF_CONSTRUCT` | index tuning | ai-service | no | int `16` / `128` |
| `ANN_ENABLED` | enable the ANN path | ai-service | no | bool `true` |
| `UOM_GATE_MODE` | `advisory`/`damp`/`strict` | ai-service | no | `advisory` |
| `UOM_DAMP_FACTOR` | the damping multiplier | ai-service | no | float `0.6` |
| `CLASSIFIER_USE_EMBEDDINGS` | enable tiers 2–3 | ai-service | no | bool `true` |
| `MODEL_DIR` | trained artefacts | ai-service | no | `data/models` |
| `USE_NER` | extraction step 4 | ai-service | no | bool `true` |
| `USE_LLM_FALLBACK` | extraction step 5 | ai-service | no | bool **`false`** |
| `LLM_MODEL` | Ollama model tag | ai-service | no | `qwen2.5:3b-instruct` |
| `LLM_TIMEOUT` / `LLM_MIN_COVERAGE` | LLM guards | ai-service | no | float `30.0` / `0.5` |
| `OLLAMA_URL` | local LLM server | ai-service | no | `http://127.0.0.1:11434` |
| `USE_LEARNED_FUSION` / `USE_CALIBRATION` | layer 7 | ai-service | no | bool `true` / `true` |
| `TOP_K` | candidates per query | ai-service | no | int `10` |
| `EXACT_THRESHOLD` | ≥ → EXACT | ai-service | no | float `0.90` |
| `NEAR_THRESHOLD` | ≥ → NEAR | ai-service | no | float `0.72` |
| `FUNCTIONAL_THRESHOLD` | ≥ → FUNCTIONAL | ai-service | no | float `0.55` |
| `REQUIRE_INTERNAL_KEY` | enforce the header | ai-service | no | bool `false` |
| `INTERNAL_API_KEY` | the shared secret | ai-service | if flag on | `[REDACTED SECRET]` |
| `PROJECT_NAME` | title in `/docs` | ai-service | no | `NUMM AI Service` |
| `QDRANT_TEST_URL` | opt into Qdrant tests | tests only | no | unset |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | compose Postgres | compose | no | `sih` / `[REDACTED SECRET]` / `sih` / `5432` |
| `AI_DB_NAME` | ai-service's database | compose | no | `numm_ai` |
| `API_SERVICE_PORT` / `AI_SERVICE_PORT` / `QDRANT_PORT` / `FRONTEND_PORT` | published ports | compose | no | 8000 / 8001 / 6333 / 3000 |
| `SECRET_KEY` | api-service JWT signing | api-service | yes in prod | `[REDACTED SECRET]` |
| `AI_SERVICE_URL` | where ai-service lives | api-service | no | `http://localhost:8001` |
| `AI_SERVICE_TIMEOUT` | client timeout | api-service | no | float `60.0` |
| `NEXT_PUBLIC_API_URL` | browser → api-service | frontend | no | `http://localhost:8000` |

**Total: 56 settings on the `Settings` class.**

> ⚠️ `backend/ai-service/.env` exists on disk and is gitignored. Its contents are
> not reproduced here. Real secrets: `[REDACTED SECRET]`.

---

# PART 21 — Configuration

## 21.1 The three layers, in precedence order 🔴

```
1. Environment variables          (highest — docker-compose sets these)
2. backend/ai-service/.env        (loaded by pydantic-settings)
3. Defaults in app/config.py      (lowest)
```

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
        protected_namespaces=(),
    )
```

- `extra="ignore"` — an unknown variable in `.env` is silently ignored rather
  than crashing the service.
- `protected_namespaces=()` — allows fields starting with `model_` (like
  `model_dir`), which Pydantic normally reserves.

Field names map to variables by **upper-casing**: `embedding_provider` ←
`EMBEDDING_PROVIDER`.

## 21.2 Domain configuration — the CSVs 🔴

This is the part that makes the service extensible without Python.

| File | Rows | Drives |
|---|---|---|
| `category_attributes.csv` | 60 | **the most important file** — what to extract and what role each attribute has |
| `abbreviations.csv` | 36 | S3 expansion, category-scoped |
| `uom_normalization.csv` | 44 | raw unit → canonical unit + dimension |
| `uom_rules.csv` | 21 | which units a family may legitimately use |
| `class_descriptors.csv` | 22 | the sentences powering zero-shot classification |

Loaded once by `reference.py::load_config()` (`@lru_cache`).

**Role distribution across the 60 attribute rows:** 43 `IDENTITY_DEFINING`,
15 `DISCRIMINATING`, 3 `DESCRIPTIVE`. 14 of the 22 categories have attribute
schemas; the other 8 have UOM rules only.

> 🔴 **`category_attributes.csv` has not been reviewed by a materials engineer.**
> Whether `thread_size` is identity-defining and `finish` is not decides every
> verdict in that category. This is the highest-leverage file in the repository
> and the first thing a domain expert should look at.

## 21.3 Model configuration

Trained artefacts live in `data/models/` (gitignored):

```
classifier_linear.joblib    88 KB   sklearn LogisticRegression
calibration_isotonic.json    3.5 KB  101 (x, y) knots + version + ECE
fusion_weights.json          297 B   5 coefficients + intercept
ner/                                 a spaCy model directory
```

All four are **optional**. Missing artefacts mean the service falls back to
keywords, hand-picked weights and raw scores — and `Score.kind` says so.

## 21.4 Logging configuration

`app/config.py::configure_logging()`, called from the lifespan:

```python
level = logging.DEBUG if settings.debug else logging.INFO
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s"))
root.handlers.clear()
root.addHandler(handler)
```

---

# PART 22 — Error Handling

## 22.1 The layering rule 🔴

```
logic/     raises plain Python exceptions, or returns None / []
services/  returns None for "not found" — NEVER raises HTTPException
routes/    turns None into HTTPException with a status code
```

A service raising `HTTPException` would make it untestable outside a web
request, and would leak HTTP into the algorithms.

## 22.2 Every error path

| Situation | Where handled | Result |
|---|---|---|
| Unknown material id | `routes/materials.py` | 404 |
| Unknown match id | `routes/matching.py` | 404 |
| `match-all` with nothing ingested | `routes/matching.py` | 409 |
| No ground truth built yet | `routes/evaluation.py` catches `FileNotFoundError` | 409 with a message telling you which endpoint to call first |
| Bad/missing `X-Internal-Key` | `app/auth.py` | 401 |
| Auth required but no key configured | `app/auth.py` | 500 — **fails closed** |
| Invalid request body | Pydantic, automatic | 422 |
| CSV missing a required column | `services/ingest.py::read_raw` | `ValueError` → 500 |
| torch missing, `qwen3` requested | `embedding.py::get_provider` | `RuntimeError` naming `requirements-ml.txt` |
| Model/collection dimension mismatch | `embedding.py`, `retrieval.py` | `RuntimeError` — never pads |
| Qdrant unreachable | `services/indexing.py::index_status` | caught, reported as `store_reachable: false` |
| Qdrant unreachable at match time | `matcher.py::build_engine` | caught, falls back to `BlockOnlyRetriever` |
| Ollama unreachable | `llm.py` | `LlmUnavailable` → `[]` |
| Corrupt trained model file | `classifier.py`, `fusion.py`, `calibration.py` | caught, falls back to untrained |
| Unparseable UOM conversion | `units.py::resolve_uom` | returns `kind="UNKNOWN"` with a note — **refuses to default to factor 1.0** |
| A reference resolving outside `UPLOAD_DIR` | `reference_ingest.py::resolve_reference` | `ReferenceError` → job `REJECTED`, **still recorded** |
| A remote URL with `ALLOW_REMOTE_REFERENCE=false` | same | `ReferenceError` naming SSRF as the reason |
| A missing CSV column | `reference_ingest.py::parse_csv` | rejects the whole file — one bad column is a mapping error, not N bad rows |
| An individually bad row | same | quarantined as `ImportRowError`, the good rows still import |
| More than 30% bad rows | `ingest_from_reference` | `REJECTED`, nothing imported |
| Non-UTF-8 bytes | `parse_csv` | `ReferenceError` telling the user to re-export as UTF-8 |

## 22.3 Two patterns worth copying 🟡

**Fail closed on security:**

```python
if not expected:
    raise HTTPException(500, "REQUIRE_INTERNAL_KEY is on but INTERNAL_API_KEY is unset.")
```

**Refuse rather than guess a number:**

```python
if factor is None:
    # defaulting to 1.0 would silently corrupt every quantity in that column
    return UomResolution(key, canonical, dim, None, "UNKNOWN", "...add to the registry...")
```

## 22.4 What is missing 🟡

- **No retry anywhere.** No `tenacity` usage despite the dependency; the LLM
  call gets exactly one attempt.
- **No custom exception hierarchy.** The docs describe RFC 9457
  `problem+json` responses; the code returns FastAPI's default
  `{"detail": "..."}`.
- **Bare `except Exception`** appears in ~8 places. Each is annotated with
  `# noqa: BLE001` and a reason, and all are genuine "degrade, don't crash"
  boundaries — but they will also swallow a programming bug.

---

# PART 23 — Logging

## 23.1 What exists

```python
# app/config.py
def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()      # ← replace uvicorn's default handlers
    root.addHandler(handler)
    root.setLevel(level)
```

**Log levels:** DEBUG < INFO < WARNING < ERROR < CRITICAL. Setting the level to
INFO hides DEBUG messages.

**Where logs go:** stdout. In Docker that means `docker compose logs -f ai-service`.

## 23.2 Honest assessment 🟡

> **`ai-service` has almost no application logging of its own.** There is not a
> single `logger.info(...)` call in `app/`. What you see is uvicorn's request log
> and SQLAlchemy's output when `DB_ECHO=true`.

The docs describe "structured JSON logs" and request-ID correlation. **Neither
is implemented.** Recorded in [Part 35](#part-35--unknown--unclear--potential-issues).

The observability that *does* exist is different in kind, and arguably better
for this domain: every decision **persists its own evidence** — `signals`,
`penalties`, `explanation` and eight version stamps on every `match_result` row.
You debug a verdict by reading the row, not by grepping logs.

## 23.3 Debugging points that actually work 🔴

| Question | How to answer it |
|---|---|
| What SQL is running? | `DB_ECHO=true` |
| Which embedding provider is live? | `GET /api/v1/retrieval/model/info` |
| Is the vector index complete? | `GET /api/v1/retrieval/status` |
| Why did this pair get this verdict? | read `explanation` on the `match_result` row |
| Which code version produced it? | the 8 version stamps on the same row |
| What did the pipeline do to one description? | call `standardize()` directly in a REPL |
| Does ANN help? | `make ablation` |

---

# PART 24 — Testing

## 24.1 The suite

| File | Tests | Covers |
|---|---|---|
| `tests/conftest.py` | — | shared fixtures: `config`, `build` |
| `test_health.py` | 1 | `/health` |
| `test_pipeline.py` | 11 | cleaning, classification, extraction, UOM flags |
| `test_matching.py` | 14 | comparison, rules, the four verdicts |
| `test_pipeline_stages.py` | 23 | S2 tokenize, S4 Pint, S5 validate/infer, S6 tiers |
| `test_retrieval.py` | 17 | embedding contract, vector store, union recall |
| `test_layer7.py` | 20 | calibration, fusion, explanation, auth, LLM |
| `test_api.py` | 15 | end-to-end HTTP against the real 404-row corpus |
| `test_reference_ingest.py` | 30 | reference resolution, row quarantine, per-CPSE merge, HTTP end-to-end |
| `test_qdrant_integration.py` | 10 | **opt-in** — needs a live Qdrant |

**Totals: 138 tests run by default (10 more with Qdrant), in ~13 seconds.**

## 24.2 Fixtures 🔴

A **fixture** is a named piece of setup pytest injects into any test that asks
for it by parameter name.

```python
@pytest.fixture(scope="session")     # built once for the whole run
def config():
    return load_config("data/config")

@pytest.fixture
def build(config):                   # a FACTORY fixture — returns a function
    def _build(description: str, **overrides):
        return standardize(make_raw(description, **overrides), config)
    return _build
```

Usage reads beautifully:

```python
def test_different_thread_size_is_rejected(build):
    a = build("HIGH TENSILE BOLT M16 X 100MM GRADE 8.8")
    b = build("HIGH TENSILE BOLT M24 X 100MM GRADE 8.8", source_row=2)
    assert verdict(a, b)[0] is Relationship.NOT_EQUIVALENT
```

## 24.3 The test database

`tests/test_api.py` swaps in **SQLite** at runtime:

```python
db = tmp_path_factory.mktemp("db") / "test.db"
config_module.settings.database_url = f"sqlite+aiosqlite:///{db}"
session_module.engine = create_async_engine(config_module.settings.database_url, future=True)

# SQLite leaves foreign keys unenforced by default, which once hid a
# constraint violation that only appeared on Postgres. Turn them on.
@event.listens_for(session_module.engine.sync_engine, "connect")
def _enforce_foreign_keys(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
```

That comment records a real bug that a weaker test setup would have hidden.

## 24.4 Mocks and opt-in tests

There are **no mocking libraries**. Instead the code has real, simple
alternatives behind protocols: `DeterministicProvider` instead of Qwen3,
`InMemoryVectorStore` instead of Qdrant. That is why the suite is fast without
`unittest.mock`.

```python
QDRANT_URL = os.getenv("QDRANT_TEST_URL")
pytestmark = pytest.mark.skipif(
    not QDRANT_URL, reason="set QDRANT_TEST_URL to run Qdrant integration tests"
)
```

## 24.5 Running them

```bash
make test-ai                                   # 138 tests
cd backend/ai-service && .venv/bin/pytest -q

# one file / one test
.venv/bin/pytest tests/test_matching.py -q
.venv/bin/pytest tests/test_layer7.py::test_calibration_is_monotone -q

# with the Qdrant integration suite
docker compose up -d qdrant
QDRANT_TEST_URL=http://localhost:6333 .venv/bin/pytest -q      # 148

make lint                                      # ruff
```

## 24.6 Gaps 🟡

| Untested / thin | Risk |
|---|---|
| `app/logic/llm.py` — the **success** path | never exercised against a live Ollama; only failure paths are tested |
| `app/logic/ner.py` — `build_training_examples()` | no unit test |
| `app/logic/ground_truth.py` | the 5 construction rules have no direct test |
| `app/logic/metrics.py` | precision/recall arithmetic is untested |
| `app/logic/matcher.py::cluster()` | union-find has **no test at all** |
| `services/indexing.py::reindex(recreate=True)` | untested |
| `app/logic/explain.py::narrate()` | only lightly asserted |
| Concurrency | no test runs two requests at once |
| Postgres | every test runs on SQLite; nothing tests the real database |

---

# PART 25 — Performance

## 25.1 Measured numbers on this repository

| Operation | Measured |
|---|---|
| Full test suite | ~12 s |
| Ingest 404 rows (pipeline + DB) | a few seconds |
| Embed 404 texts, Qwen3, CPU, batch 32 | ~1–2 min |
| Embed 404 texts, deterministic | < 1 s |
| `match-all` over 404 materials | ~2,946 rows stored |
| Candidates compared, blocking only | 9,356 |
| Candidates compared, with union retrieval | 11,334 (1.21×) |

## 25.2 The optimisations that exist, and why 🔴

**Blocking** — `candidates.py`. Turns O(N²) into O(N·k). 81,406 possible pairs
become ~9,356 comparisons. This is the single biggest one.

**`@lru_cache` on config loading** — `reference.py::load_config`. The five CSVs
are parsed once per process, not per request.

**Model singleton** — `embedding.py::get_provider`. A 1.2 GB model loads once.
Loading per request would make the service unusable.

**Batching** — 32 texts per forward pass. One large matrix multiply beats 32
small ones.

**L2-normalise once, at generation** — so every later similarity is a dot
product rather than a division.

**Vectorised search** — `InMemoryVectorStore.search` does `matrix @ vector`,
comparing against every stored vector in one NumPy operation instead of a Python
loop.

**`selectinload` — the N+1 fix** 🔴:

```python
.options(
    selectinload(StandardizedMaterialRow.attributes),
    selectinload(StandardizedMaterialRow.quality_flags),
)
```

Without it, loading 404 materials and touching each one's attributes would issue
1 + 404 + 404 = **809 queries**. With it: **3**. (In async SQLAlchemy it is not
merely slow without this — it raises.)

**`torch.inference_mode()`** — disables gradient tracking, which saves memory
and time during inference.

**HNSW** — approximate nearest neighbour in ~log time instead of a full scan.

## 25.3 Where the bottlenecks actually are 🟡

1. **`POST /materials/match-all` is fully synchronous.** It matches the whole
   corpus inside one HTTP request. At 404 materials that is fine. At 100,000 it
   would time out. There is no job queue — the docs describe one; it does not
   exist.
2. **Query embedding is one text at a time.** `UnionRetriever._ann_candidates`
   calls `provider.embed([...])` per query. Matching 404 materials with Qwen3
   means 404 separate forward passes — this is why the Qwen3 ablation took
   minutes.
3. **`load_standardized()` loads the entire corpus into memory** on every
   matching request. Fine at 404 rows; not at a million.
4. **`cluster()` is O(N²) in matching calls** — it calls `match()` for every
   material.
5. **No caching layer.** No Redis, no in-process result cache. Every request
   recomputes.

## 25.4 CPU / GPU

Everything is CPU-only by default (`EMBEDDING_DEVICE=cpu`). The code sets:

```python
# torch oversubscribes cores by default and batch throughput collapses.
torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))
```

Setting `EMBEDDING_DEVICE=cuda` would use a GPU if one and a CUDA torch build
were present — **untested in this repository.**

---

# PART 26 — Security

## 26.1 Implemented ✅

| Control | Where | Detail |
|---|---|---|
| **Internal-key auth** | `app/auth.py` | optional `X-Internal-Key`, constant-time compare, fails closed, `/health` exempt |
| **Input validation** | Pydantic, every route | types, `min_length`, `Query(ge=…, le=…)` |
| **SQL injection prevention** | SQLAlchemy | every query is parameterised; **no f-string SQL anywhere** |
| **Read-only raw data** | `docker-compose.yml` | `./backend/pipeline-one:/srv/data/raw:ro` |
| **CORS allowlist** | `app/main.py` | `settings.cors_origins`, localhost by default |
| **Secrets out of git** | `.gitignore` | `.env` ignored, `.env.example` committed |
| **No data egress** | by design | models are local; the LLM talks only to a local Ollama |
| **Append-only audit** | `models/matching.py` | `audit_log` is only ever inserted into |
| **Pagination limits** | `routes/materials.py` | `Query(50, ge=1, le=500)` caps response size |
| **Path-traversal fence** | `reference_ingest.py::resolve_reference` | every reference is `resolve()`d and must sit inside `UPLOAD_DIR`; symlinks out are refused because `resolve()` follows them |
| **SSRF off by default** | same | `http(s)://` sources need `ALLOW_REMOTE_REFERENCE=true` |
| **Ingest size cap** | same | `MAX_REFERENCE_BYTES`, checked before reading |
| **Non-secret payloads in Qdrant** | `retrieval.py` | price, vendor and quantity deliberately absent |

## 26.2 Not implemented ❌ — and why that is (mostly) correct

| Missing | Status |
|---|---|
| Users, JWT, RBAC, CPSE row-scoping | **Correct.** These belong to `api-service`; two implementations of one security rule means the weaker one decides. |
| Rate limiting | Not implemented anywhere. |
| File-upload validation | No upload endpoint exists in `ai-service`. |
| TLS | Terminated upstream; not in this service. |
| `reviewer` verification | The review endpoint trusts the caller's string. Correct given the boundary — and a reason `:8001` must not be public. |
| Qdrant authentication | Qdrant is unauthenticated. Do not publish `:6333`. |
| Audit-log immutability at the DB level | Append-only by convention, **not** by revoked UPDATE/DELETE grants. |

## 26.3 The one thing to remember 🔴

> `ai-service` must never be exposed publicly. It has no user model by design.
> Where the network boundary cannot be guaranteed, set
> `REQUIRE_INTERNAL_KEY=true` — defence in depth, not a user model.


---

# PART 27 — Complete Request Flows

## Flow A — Material ingestion

```
POST /api/v1/materials/ingest          (no body)
 │
 ├─ app/main.py                 router dependency: verify_internal_key
 │                              (no-op unless REQUIRE_INTERNAL_KEY)
 ├─ app/routes/materials.py::ingest_dataset
 │     session = Depends(get_db)        ← one transaction opens
 │
 └─ app/services/ingest.py::ingest_dataset(session)
       ├─ read_raw(settings.raw_dataset_path)
       │     validates 8 REQUIRED_COLUMNS, raises ValueError if any is missing
       │     → 404 RawMaterial
       ├─ standardize_all(raws)
       │     → logic/standardize.py::standardize() × 404   (all of S1–S7)
       ├─ persist(session, raws, standardized)
       │     DELETE ×4 tables, then INSERT material / standardized_material /
       │     material_attribute / quality_flag, then commit
       ├─ export_jsonl(standardized, settings.standardized_export_path)
       ├─ session.add(AuditLog(action="INGEST", ...))
       ├─ await session.commit()
       └─ count categories and flags
 │
 └─ IngestResponse  →  200
    {"materials": 404, "categories": {"BEARING": 47, ...},
     "quality_flags": {"DESCRIPTION_NOISE": 12, ...}}
```

## Flow A2 — Material ingestion by reference (the real upload path)

```
A user uploads a CSV to api-service (NOT BUILT — another developer owns it).
api-service writes the bytes into the shared UPLOAD_DIR and calls:

POST /api/v1/ingest/by-reference
     {"source": "20260909T110000-a1c9-cpcl.csv", "mode": "merge",
      "original_filename": "CPCL Master 2026.csv", "requested_by": "ravi@cpcl"}
 │
 ├─ Pydantic validates IngestByReferenceRequest
 │     mode is Literal["merge","replace"] → "obliterate" is a 422
 ├─ app/routes/ingest.py::ingest_by_reference
 │
 └─ app/services/reference_ingest.py::ingest_from_reference()
       ├─ ImportJob(status="RUNNING") is created up front
       │
       ├─ resolve_reference(source)              ← THE SECURITY BOUNDARY
       │     · http(s)? only if ALLOW_REMOTE_REFERENCE (default off — SSRF)
       │     · else: (UPLOAD_DIR / source).resolve()
       │     · resolve() follows symlinks, so containment is checked on the
       │       REAL destination — a symlink out of UPLOAD_DIR is refused too
       │     · must exist, be a file, be non-empty, be under MAX_REFERENCE_BYTES
       │     · anything else → ReferenceError → job REJECTED, still recorded
       │
       ├─ read_reference_bytes() → sha256 recorded on the job
       │
       ├─ parse_csv(payload)
       │     · utf-8-sig (strips Excel's BOM)
       │     · a missing required column rejects the WHOLE file
       │     · per row: empty description → DESCRIPTION_EMPTY
       │                empty company     → COMPANY_EMPTY
       │                unparseable       → ROW_UNREADABLE (raw value kept)
       │     · bad rows are QUARANTINED, never dropped
       │
       ├─ if error_rate > MAX_ROW_ERROR_RATE (30%) → REJECTED, nothing imported
       │     (importing the good 60% of a mis-mapped file corrupts it quietly)
       │
       ├─ standardize() × valid rows          ← the same S1–S7 as Flow A
       ├─ cpse_codes = {cpse_code_for(row.company) for row in rows}
       │
       ├─ mode == "merge"   → _delete_for_cpses(cpse_codes)
       │                      deletes ONLY those CPSEs' rows, children first
       │   mode == "replace" → wipes all four material tables
       │
       ├─ persist_rows(...)                   ← shared with the legacy path
       ├─ ImportRowError × quarantined rows
       ├─ AuditLog(action="INGEST_BY_REFERENCE")
       └─ commit
 │
 └─ 200 with the ImportJob — even when REJECTED. A rejection is a result the
    caller must show a user, not a transport failure.
```

**The one line that makes multi-CPSE upload possible:**

```python
await _delete_for_cpses(session, set(cpse_codes))   # merge
```

versus the legacy path's

```python
await session.execute(delete(Material))              # everything
```

## Flow B — Duplicate detection

```
GET /api/v1/materials/CCL-000001/matches?top_k=5
 │
 ├─ app/routes/matching.py::match_material
 └─ app/services/matching.py::match_one(session, material_id, top_k)
       ├─ load_standardized(session)          rebuild 404 objects (3 queries)
       ├─ find the query material; None → route raises 404
       ├─ build_engine(top_k=top_k)
       │     · settings.ann_enabled?
       │     · store.count() > 0?     → UnionRetriever, else BlockOnlyRetriever
       │     · build_matcher(): learned? calibrated? → sets Score.kind
       └─ MatchingEngine.match(query, materials, top_k=top_k)
             ├─ retriever.retrieve(query, corpus)
             │     category_block ∪ fingerprint ∪ ann ∪ trigram
             ├─ for each candidate:
             │     compare()   → ComparisonResult  (MATCH/CONFLICT/MISSING/INFERRED)
             │     score()     → Score(value, kind, signals, penalties)
             │     evaluate()  → RuleVerdict (5 rules)
             │     _decide()   → (relationship, proposed, reason)
             │     build_explanation() → the stored evidence dict
             ├─ sort by (RELATIONSHIP_RANK, score) descending
             └─ take top_k
 │
 └─ MatchResponse → 200
```

## Flow C — Match approval

```
POST /api/v1/materials/matches/{match_id}/review
     {"reviewer": "a.kumar@cpcl.co.in", "decision": "APPROVED", "comment": "Same part."}
 │
 ├─ Pydantic validates against ReviewRequest    (min_length=1 → 422 if empty)
 ├─ app/routes/matching.py::review_match
 └─ app/services/matching.py::review_match(session, match_id, payload)
       ├─ session.get(MatchResult, match_id)    → None ⇒ route raises 404
       ├─ build Review, PINNING the evidence:
       │     relationship_at_review, confidence_at_review, reason_at_review,
       │     matcher_version, rule_version
       │     (match_result is rebuilt by every run; the decision must outlive it)
       ├─ session.add(review)
       ├─ session.add(AuditLog(action="MATCH_REVIEWED", ...))
       └─ await session.commit()                ← both rows, one transaction
 │
 └─ 201 Created
```

## Flow D — Indexing (ai-service specific)

```
POST /api/v1/retrieval/index?force=false&recreate=false
 │
 └─ app/services/indexing.py::reindex(session, force, recreate)
       ├─ load_standardized(session)
       ├─ get_provider()                        loads Qwen3 once, or the fallback
       ├─ get_store()                           QdrantStore or InMemoryVectorStore
       ├─ store.ensure_collection(dimension=provider.dimension, recreate=recreate)
       │     → RuntimeError if an existing collection has a different dimension
       ├─ _stale_ids(session, materials)        canonical_hash / version mismatch
       │                                         or indexed_at IS NULL
       ├─ build_points(pending, provider)       ONE batched embed call
       ├─ store.upsert(points, batch_size=256)  id = uuid5(material_id) ⇒ idempotent
       ├─ UPDATE standardized_material SET canonical_hash, embedding_version, indexed_at
       └─ await session.commit()
 │
 └─ 200  {"materials": 404, "embedded": 404, "skipped": 0,
          "provider": "...", "indexed_total": 404}
```

---

# PART 28 — Dependency Graph

## 28.1 ai-service (your service)

```
uvicorn
  │
  └── app/main.py
        ├── app/config.py ──────────── pydantic-settings ← .env / environment
        ├── app/database.py ────────── app/config.py
        │                              SQLAlchemy async engine
        ├── app/auth.py ────────────── app/config.py
        ├── app/models/  (import * registers every mapper before create_all)
        │     ├── models/material.py ── app/database.py (Base)
        │     └── models/matching.py ── app/database.py (Base)
        │
        └── app/routes/
              ├── health.py ────────── schemas/common.py
              ├── materials.py ─────── schemas/material.py
              │                        services/ingest.py, services/materials.py
              ├── matching.py ──────── services/matching.py
              ├── evaluation.py ────── services/evaluation.py
              └── retrieval.py ─────── services/indexing.py

                    ↓ services depend downward only ↓

app/services/
  ├── ingest.py ────── logic/standardize.py, logic/reference.py, models/*
  ├── materials.py ─── services/ingest.py, models/material.py, schemas/material.py
  ├── matching.py ──── logic/matcher.py, logic/versions.py, models/matching.py
  ├── evaluation.py ── logic/ground_truth.py, logic/metrics.py
  └── indexing.py ──── logic/embedding.py, logic/retrieval.py, models/material.py

                    ↓ logic depends on logic and NOTHING above ↓

app/logic/
  enums.py            ← imports NOTHING from this app  (the foundation)
  versions.py         ← config
  reference.py        ← config, enums                  (loads the CSVs)

  clean.py            ← reference
  tokenize.py         ← versions
  units.py            ← reference                      (Pint)
  classify.py         ← (nothing)
  extract.py          ← enums, reference, units
  ner.py              ← config, enums, extract, reference     (spaCy)
  llm.py              ← config, enums, extract, reference     (httpx → Ollama)
  validate.py         ← enums, extract, reference, units
  quality.py          ← enums, reference
  classifier.py       ← config, classify, embedding           (sklearn)
  standardize.py      ← classify(er), clean, extract, ner, llm,
                        quality, reference, tokenize, validate, versions
        ↑
        └── THE ORCHESTRATOR for Phase A

  embedding.py        ← config, standardize, enums            (torch/transformers)
  retrieval.py        ← config                                (qdrant-client)
  candidates.py       ← config, classify, embedding, retrieval, standardize

  compare.py          ← enums, standardize, units
  score.py            ← config, compare, standardize          (rapidfuzz)
  calibration.py      ← config                                (sklearn isotonic)
  fusion.py           ← config, calibration, compare, score, standardize
  rules.py            ← classify, compare, enums
  explain.py          ← compare, enums, score, versions
  matcher.py          ← config, candidates, compare, enums, explain,
                        fusion, rules, score, standardize
        ↑
        └── THE ORCHESTRATOR for Phase B

  ground_truth.py     ← enums, standardize
  metrics.py          ← compare, ground_truth, matcher, rules, score, standardize
```

**The rule this enforces:** arrows only point downward. `logic/` never imports
from `services/`, `routes/`, or `models/`. That is why every algorithm is
testable without a database.

## 28.2 api-service (for context only)

```
app/main.py
  ├── app/core/config.py
  ├── app/core/logging.py
  ├── app/db/session.py ── app/db/base.py
  └── app/api/router.py
        ├── routes/health.py
        ├── routes/users.py ──── schemas/user.py, models/user.py  (IN-MEMORY dict)
        └── routes/ai.py ─────── services/ai_client.py ──httpx──► ai-service
```

---

# PART 29 — What Happens When I Run the Project?

## 29.1 `docker compose up`

```
1. Docker reads docker-compose.yml, builds any image that changed.

2. postgres starts
   · first boot only: runs /docker-entrypoint-initdb.d/10-numm-ai.sql
     → CREATE DATABASE numm_ai
   · healthcheck: pg_isready every 10 s until it passes

3. qdrant starts
   · healthcheck: a bash /dev/tcp probe on 6333

4. api-service starts        (waits for postgres healthy)

5. ai-service starts         (waits for postgres AND qdrant healthy)
   │
   └─ CMD: uvicorn app.main:app --host 0.0.0.0 --port 8001
        │
        ├─ Python imports app/main.py
        │    ├─ imports app.config      → Settings() reads env + .env
        │    │                            ← IF a required value is malformed,
        │    │                              the process dies HERE, before serving
        │    ├─ imports app.database    → create_async_engine(...)
        │    │                            (no connection is opened yet)
        │    ├─ imports app.models      → registers all 7 mappers
        │    └─ imports app.routes      → each route module imports its services,
        │                                 which import logic/…
        │       ⚠ NOTE: importing does NOT load Qwen3 or spaCy. Those load
        │         lazily on first use.
        │
        ├─ FastAPI(...) is constructed
        ├─ CORSMiddleware is added
        ├─ routers are mounted (health open; the rest behind verify_internal_key)
        │
        └─ uvicorn calls lifespan():
             ├─ configure_logging()
             ├─ async with engine.begin():        ← FIRST actual DB connection
             │     await connection.run_sync(Base.metadata.create_all)
             │     → creates the 7 tables if they do not exist
             ├─ yield                              ← SERVER IS NOW READY
             └─ (on shutdown) await engine.dispose()

6. frontend starts           (waits for api-service)
```

**Ready state:** `http://localhost:8001/docs` renders, `/health` returns 200,
and the database has 7 empty tables. **No material data exists yet** — you must
call `/materials/ingest`.

## 29.2 Without Docker

```bash
make install-ai        # python3 -m venv .venv && pip install -r requirements-dev.txt
make install-ml        # OPTIONAL: torch + transformers (~2 GB)
cp backend/ai-service/.env.example backend/ai-service/.env
sudo -u postgres psql -f backend/ai-service/scripts/setup_postgres.sql
make dev-ai            # uvicorn --reload --port 8001
```

## 29.3 When models actually load 🔴

| Artefact | Loads at | Trigger |
|---|---|---|
| Settings | import time | always |
| Database tables | lifespan startup | always |
| Qwen3 (~1.2 GB) | **first use** | first `get_provider()` call — i.e. first index or ANN retrieval |
| spaCy NER | **first use** | first `get_ner()` — i.e. first `standardize()` |
| sklearn classifier | **first use** | first `_bundle()` |
| calibration + fusion | **first use** | first `build_matcher()` |

**Startup is fast because nothing ML loads at startup.** The first request that
needs a model pays the cost.

## 29.4 A full working session

```bash
docker compose up -d
curl -X POST localhost:8001/api/v1/materials/ingest        # 404 materials
curl -X POST localhost:8001/api/v1/retrieval/index         # embed + upsert
curl localhost:8001/api/v1/materials/quality
curl localhost:8001/api/v1/materials/CCL-000001/matches
curl -X POST localhost:8001/api/v1/materials/match-all     # persist all matches
curl -X POST localhost:8001/api/v1/materials/ground-truth/build
curl localhost:8001/api/v1/materials/evaluation/report
```

---

# PART 30 — What Happens When I Send This API Request?

The most important endpoint in the service, traced completely.

```http
GET /api/v1/materials/CCL-000001/matches?top_k=5
```

### Step 1 — uvicorn → ASGI

uvicorn parses the HTTP request and hands FastAPI an ASGI `scope` dict.

### Step 2 — routing

FastAPI matches the path against registered routes. `app/main.py` mounted the
matching router with `prefix=settings.api_v1_prefix` (`/api/v1`), and
`routes/matching.py` declares `prefix="/materials"`, so the full pattern is
`/api/v1/materials/{material_id}/matches`.

> **Route order matters.** `/materials/{material_id}` is registered before
> `/materials/{material_id}/matches`, but they have different segment counts so
> there is no shadowing. `/materials/quality` is registered *before*
> `/materials/{material_id}` on purpose — otherwise `quality` would be captured
> as a material id.

### Step 3 — dependencies resolve

```python
async def match_material(
    material_id: str,                                    # from the path
    top_k: int | None = Query(None, ge=1, le=50),        # validated: 1..50
    session: AsyncSession = Depends(get_db),             # a fresh session
) -> MatchResponse:
```

- `verify_internal_key` runs first (router-level dependency). No-op by default.
- `top_k=999` → **422** before your code runs.
- `get_db()` opens `AsyncSessionLocal()`.

### Step 4 — the route delegates

```python
result = await matching.match_one(session, material_id, top_k=top_k)
if result is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown material {material_id!r}")
return result
```

Four lines. That is the whole route.

### Step 5 — `services/matching.py::match_one`

```python
materials = await load_standardized(session)          # 3 SQL queries (selectinload)
query = next((m for m in materials if m.material_id == material_id), None)
if query is None:
    return None                                       # ← service returns None, not 404
outcome = build_engine(top_k=top_k).match(query, materials, top_k=top_k)
```

### Step 6 — `build_engine()` decides what is available

```python
if not settings.ann_enabled:            → BlockOnlyRetriever
store = get_store();  provider = get_provider()
indexed = store.count()                 (exceptions → indexed = 0)
if indexed == 0:                        → BlockOnlyRetriever
else:                                   → UnionRetriever(provider, store)
matcher = build_matcher()               → Deterministic | Learned | Calibrated
```

### Step 7 — `MatchingEngine.match()`

```
retrieved = retriever.retrieve(query, corpus)
    category_block : ~19 same-category materials
    fingerprint    : identity-hash equals
    ann            : embed the query → Qdrant top-10, filtered by UOM dimension
    trigram        : RapidFuzz top-10 over description_normalized
    → union, deduplicated by material_id           (measured: ~50 candidates)

for other in candidates:
    comparison   = compare(query, other)
    score        = matcher.score(query, other, comparison)
    rules        = evaluate(query.category, other.category, comparison)
    shared_missing = sorted(set(query.missing_identity) & set(other.missing_identity))
    relationship, proposed, reason = _decide(score, rules, comparison, shared_missing)
    explanation  = build_explanation(...)
    → Candidate(...)

sort by (RELATIONSHIP_RANK[relationship], score.value) descending
take top_k
```

### Step 8 — build the response

`services/matching.py` maps every `Candidate` into a `CandidateOut` and wraps it
in `MatchResponse`, with the query rendered by `services/materials.py::to_out()`.

### Step 9 — FastAPI serialises

Pydantic converts the model to JSON. The `note` field ships automatically
because it has a default value.

### Step 10 — teardown

`get_db()`'s `async with` block closes the session. No commit — this was a read.

### The actual response (abridged)

```json
{
  "query": { "material_id": "CCL-000001", "category": "BEARING", "...": "..." },
  "compared": 50,
  "summary": {"EXACT_DUPLICATE": 12, "NEAR_DUPLICATE": 6,
              "FUNCTIONALLY_EQUIVALENT": 0, "NOT_EQUIVALENT": 32},
  "candidates": [
    {
      "material_id": "CCL-000056",
      "relationship": "EXACT_DUPLICATE",
      "confidence_score": 0.954,
      "confidence_kind": "calibrated_probability",
      "hard_rule_status": "PASS",
      "capped_by_rules": false,
      "reason": "All 3 comparable attributes agree, no conflicts, no missing identity evidence.",
      "matched_attributes": ["bearing_number", "bearing_type", "seal_type"],
      "inferred_attributes": ["bore"],
      "signals": {"identity_agreement": 1.0, "attribute_match_ratio": 0.875,
                  "completeness": 1.0, "category_match": 1.0, "lexical": 1.0},
      "penalties": ["calibrated 0.902 -> 0.932 (isotonic-v1, n=58, ECE=0.0)"],
      "retrieved_by": ["ann", "category_block", "trigram"],
      "explanation": {
        "verdict": "EXACT_DUPLICATE",
        "confidence_band": "HIGH",
        "signals": [{"name": "Identity agreement", "value": 1.0,
                     "weight": 0.45, "contribution": 0.45}, "..."],
        "gates": [{"name": "UOM compatibility", "status": "PASS",
                   "detail": "Dimensionally compatible."}, "..."],
        "attributes": {"conflict": [], "agree": ["..."], "inferred": ["..."],
                       "missing": []},
        "provenance": {"pipeline_version": "pipeline-v2", "matcher_version": "...",
                       "embedding_version": "...", "...": "..."},
        "narrative": "Both records classify as BEARING. 3 comparable attributes agree..."
      }
    }
  ],
  "note": "confidence_score is a deterministic heuristic, not a calibrated probability. Hard rules can override it."
}
```


---

# PART 31 — Beginner Glossary

Simple meaning first, then the technical one.

## Web and APIs

**API** — *Simple:* a way for one program to ask another program to do
something. *Technical:* a defined contract of operations exposed over a
transport.

**REST** — *Simple:* a style where URLs name things and HTTP methods say what to
do to them. *Technical:* resource-oriented architecture using HTTP verbs and
status codes.

**HTTP** — *Simple:* the language browsers and servers speak. *Technical:* a
request/response protocol over TCP; a request has a method, path, headers, body.

**JSON** — *Simple:* a text way of writing nested data. *Technical:* JavaScript
Object Notation; objects, arrays, strings, numbers, booleans, null.

**Endpoint** — *Simple:* one URL your program answers. *Technical:* a
(method, path) pair bound to a handler. `ai-service` has **13**.

**FastAPI** — *Simple:* the Python library that turns functions into endpoints.
*Technical:* an ASGI framework using type hints for validation and OpenAPI
generation.

**ASGI** — *Simple:* the plug between a web server and an async Python app.
*Technical:* Asynchronous Server Gateway Interface.

**uvicorn** — *Simple:* the program that actually listens on port 8001.
*Technical:* an ASGI server.

**Middleware** — *Simple:* code that wraps every request. *Technical:* a layer
in the ASGI chain. Here: `CORSMiddleware`.

**CORS** — *Simple:* the browser rule that a page from site A cannot call site B
unless B allows it. *Technical:* Cross-Origin Resource Sharing.

**Dependency injection** — *Simple:* a function declares what it needs and the
framework supplies it. *Technical:* `Depends(get_db)`.

**Status code** — *Simple:* a number saying how it went. *Technical:* 2xx
success, 4xx caller's fault, 5xx server's fault.

## Data and database

**PostgreSQL** — *Simple:* the program that stores your data. *Technical:* an
open-source relational database. Version 16 here.

**SQL** — *Simple:* the language for asking a database questions.
*Technical:* Structured Query Language.

**Table / row / column** — *Simple:* a grid / one line / one field.

**Primary key** — *Simple:* the column that uniquely identifies a row.

**Foreign key** — *Simple:* a column pointing at another table's primary key.

**Index** — *Simple:* the book's index — a shortcut so the database does not
read every row.

**Transaction** — *Simple:* all-or-nothing. *Technical:* ACID unit of work.

**Migration** — *Simple:* a versioned script that changes the schema.
*Technical:* **not used in ai-service** — `create_all` is used instead.

**ORM** — *Simple:* lets you use Python objects instead of SQL strings.
*Technical:* Object-Relational Mapper. SQLAlchemy 2.0 here.

**Session** — *Simple:* one conversation with the database. *Technical:* a unit
of work that tracks objects and wraps a transaction.

**N+1 query** — *Simple:* accidentally running one query per row.
*Technical:* solved here with `selectinload`.

**Repository (pattern)** — *Simple:* a class that owns all queries for one
entity. *Technical:* **planned in `api-service`; `ai-service` puts queries
directly in services.**

**Service layer** — *Simple:* where the actual work lives, between HTTP and the
database. *Technical:* `app/services/`.

## Validation

**Pydantic** — *Simple:* checks incoming data matches the shape you declared.
*Technical:* a runtime validation library driven by type hints.

**Schema** — *Simple:* the declared shape of some data. *Technical:* here, a
`BaseModel` subclass.

**Serialization / deserialization** — *Simple:* object → JSON / JSON → object.

**Type hint** — *Simple:* a note saying what type a variable holds.
*Technical:* normally ignored at runtime — but Pydantic and FastAPI **enforce**
them.

## NLP and ML

**NLP** — *Simple:* getting computers to work with human language.
*Technical:* Natural Language Processing.

**Token** — *Simple:* a piece of text — roughly a word. *Technical:* the unit a
tokenizer emits. `M16X50` → `M16` · `X` · `50` here.

**Tokenization** — *Simple:* splitting text into pieces.

**Regex** — *Simple:* a pattern for finding text. *Technical:* regular
expression. This project is full of them, and they live in **CSV files**, not
code.

**Gazetteer** — *Simple:* a list of known words to look for. *Technical:* a
closed-vocabulary dictionary lookup.

**Stemming / lemmatization** — *Simple:* cutting words to a root form.
*Technical:* **deliberately not used here** — a curated dictionary is safer for
engineering vocabulary.

**Stopwords** — *Simple:* common words usually thrown away.
*Technical:* **not used here** — every token in a 40-character description
carries signal.

**Fuzzy matching** — *Simple:* how similar two strings look, allowing typos.
*Technical:* RapidFuzz `token_set_ratio` here.

**Embedding** — *Simple:* turning text into a list of numbers that captures
meaning. *Technical:* a dense vector from a neural network.

**Vector** — *Simple:* a list of numbers. *Technical:* a point in n-dimensional
space; 1024 dimensions here.

**Dimension** — *Simple:* how many numbers are in the vector.

**Cosine similarity** — *Simple:* do these two arrows point the same way?
*Technical:* `(A·B)/(‖A‖‖B‖)`, which is just `A·B` for unit vectors.

**Euclidean distance** — *Simple:* straight-line distance.
*Technical:* **not used** — Qdrant is configured with `Distance.COSINE`.

**L2 normalisation** — *Simple:* scaling a vector to length 1.

**Semantic similarity** — *Simple:* similar in meaning, not in spelling.

**Vector database** — *Simple:* a database that finds "nearest" vectors fast.
*Technical:* Qdrant here.

**ANN** — *Simple:* find *almost* the nearest neighbours, much faster.
*Technical:* Approximate Nearest Neighbour.

**HNSW** — *Simple:* the graph structure that makes ANN fast.
*Technical:* Hierarchical Navigable Small World.

**Blocking** — *Simple:* only compare things in the same family.
*Technical:* the standard entity-resolution technique for avoiding O(N²).

**Candidate generation** — *Simple:* picking the short list worth comparing.

**Top-K** — *Simple:* keep the best K results. K = 10 here.

**Duplicate detection / entity resolution** — *Simple:* deciding whether two
records describe the same thing.

**LLM** — *Simple:* a model that reads and writes text.
*Technical:* Large Language Model. Here: `qwen2.5:3b-instruct`, **off by
default**.

**Inference** — *Simple:* using a trained model to get an answer.

**Prompt** — *Simple:* the instructions you give an LLM.

**Temperature** — *Simple:* randomness. 0.0 here.

**Transformer** — *Simple:* the neural architecture behind modern language
models. *Technical:* attention-based; both Qwen models are transformers.

**Hugging Face** — *Simple:* where models are downloaded from.
*Technical:* the `transformers` library + the Model Hub.

**PyTorch (torch)** — *Simple:* the engine that runs neural networks.

**NumPy** — *Simple:* fast arrays and maths.

**scikit-learn** — *Simple:* classical ML — regression, classification.
*Technical:* `LogisticRegression`, `IsotonicRegression` here.

**spaCy** — *Simple:* an NLP library; used here for NER.

**NER** — *Simple:* finding and labelling names/values in text.
*Technical:* Named Entity Recognition.

**Distant supervision** — *Simple:* using existing rules to auto-label training
data. *Technical:* how the NER here was trained — regex spans became labels.

**Calibration** — *Simple:* making "0.9" actually mean "right 90% of the time".
*Technical:* isotonic regression here.

**ECE** — *Simple:* how far off your confidence is. *Technical:* Expected
Calibration Error.

**Precision / recall / F1** — *Simple:* of what you flagged, how much was right /
of what was there, how much you found / their harmonic mean.

**Ablation study** — *Simple:* turn a component off and measure what changes.
*Technical:* `make ablation`.

**Cross-validation** — *Simple:* train on part of the data, test on the rest,
repeatedly.

## Python and infrastructure

**async / await** — *Simple:* let other work happen while waiting.
*Technical:* cooperative concurrency on one thread.

**Coroutine** — *Simple:* a function that can pause. *Technical:* what
`async def` produces.

**Context manager** — *Simple:* guaranteed setup and cleanup.
*Technical:* `with` / `async with`.

**Decorator** — *Simple:* `@something` above a function that changes it.

**Dataclass** — *Simple:* a class that is mostly fields.

**Enum** — *Simple:* a fixed set of named values.

**Protocol** — *Simple:* "any class with these methods will do".
*Technical:* structural typing (PEP 544).

**Docker** — *Simple:* ship an app with its whole environment.

**Image / container** — *Simple:* the recipe's output / a running copy.

**Volume** — *Simple:* storage that survives the container.

**Docker Compose** — *Simple:* run several containers together.

**Environment variable** — *Simple:* configuration from outside the code.

**JWT** — *Simple:* a signed token proving who you are.
*Technical:* **planned in `api-service`, not implemented anywhere yet.**

---

# PART 32 — Learning Order

Dependency-aware. Do not skip levels — each one uses the previous.

### LEVEL 0 — Python fundamentals 🔴

- **Prerequisites:** none.
- **Learn:** functions, classes, `list`/`dict`/`set`, comprehensions,
  `try`/`except`, imports, f-strings, type hints, `dataclass`, `Enum`.
- **Files:** [`app/logic/enums.py`](backend/ai-service/app/logic/enums.py) (74 lines — read it end to end),
  [`app/logic/classify.py`](backend/ai-service/app/logic/classify.py) (60 lines).
- **Before moving on:** you can explain what `@dataclass(frozen=True)` does and
  why `StrEnum` is used instead of a plain class.
- **Exercise:** add a new category to `classify.py`'s `RULES` (e.g. `PAINT` with
  pattern `\bPAINT\b|\bPRIMER\b`) and prove it works in a REPL.

### LEVEL 1 — The pure pipeline, no web, no database 🔴

- **Prerequisites:** Level 0.
- **Learn:** regex basics, CSV-driven configuration, pure functions.
- **Files:** `logic/clean.py` → `logic/tokenize.py` → `logic/reference.py` →
  `logic/extract.py` → `logic/standardize.py`, plus `data/config/*.csv`.
- **Understand:** how one CSV row becomes a `StandardizedMaterial`.
- **Exercise:**
  ```python
  from app.logic.reference import load_config
  from app.logic.standardize import RawMaterial, standardize
  c = load_config("data/config")
  m = standardize(RawMaterial(source_row=1, company="NTPC",
      description="HEX BOLT M16X50 SS-304", legacy_code="L", quantity="1",
      uom="NOS", part_number="", make="", specifications=""), c)
  print(m.canonical_text)
  for a in m.attributes: print(a.name, a.value, a.role, a.status)
  ```
  Then add an attribute to `category_attributes.csv` and watch it appear.

### LEVEL 2 — Comparison, rules, verdicts 🔴

- **Prerequisites:** Level 1.
- **Learn:** the four comparison states; why `MISSING ≠ DIFFERENT`.
- **Files:** `logic/compare.py` → `logic/score.py` → `logic/rules.py` →
  `logic/matcher.py::_decide`.
- **Before moving on:** you can list, without looking, the six conditions
  required for `EXACT_DUPLICATE`.
- **Exercise:** run `tests/test_matching.py` and change
  `EXACT_THRESHOLD` to `0.99`. Which tests fail, and why?

### LEVEL 3 — Pytest 🔴

- **Files:** `tests/conftest.py`, `tests/test_pipeline.py`, `tests/test_matching.py`.
- **Learn:** fixtures, `assert`, parametrize, `-k` filtering.
- **Exercise:** write a test proving `HEX BOLT M16X50 SS304` vs
  `HEX BOLT M16X50 SS316` is `NOT_EQUIVALENT`.

### LEVEL 4 — SQL and PostgreSQL 🔴

- **Learn:** tables, keys, joins, indexes, transactions.
- **Files:** `scripts/setup_postgres.sql`, `app/models/material.py`.
- **Exercise:** `psql numm_ai` and run
  `SELECT category, COUNT(*) FROM standardized_material GROUP BY category;`

### LEVEL 5 — SQLAlchemy and async 🔴

- **Prerequisites:** Levels 0, 4.
- **Learn:** models, sessions, `select`, `commit`, `async`/`await`, why
  `selectinload` is mandatory here.
- **Files:** `app/database.py`, `app/models/*`, `app/services/ingest.py`.
- **Before moving on:** you can explain why `review` has no foreign key to
  `match_result`.

### LEVEL 6 — Pydantic and FastAPI 🔴

- **Prerequisites:** Level 5.
- **Files:** `app/schemas/material.py`, `app/routes/materials.py`, `app/main.py`.
- **Exercise:** add `GET /api/v1/materials/{id}/attributes` returning just the
  attribute list. You will touch a route, a service, and possibly a schema —
  which teaches you the layering.

### LEVEL 7 — Vectors and embeddings 🔴

- **Prerequisites:** Levels 0–2.
- **Learn:** what a vector is, cosine similarity, L2 normalisation, NumPy basics.
- **Files:** `logic/embedding.py`, then `logic/retrieval.py`.
- **Exercise:**
  ```python
  from app.logic.embedding import DeterministicProvider
  import numpy as np
  p = DeterministicProvider(dimension=8)
  v = p.embed(["BEARING BALL 6205", "BALL BEARING 6205"])
  print(np.linalg.norm(v, axis=1))    # both 1.0 — why?
  print(v[0] @ v[1])                  # cosine similarity, as a dot product
  ```

### LEVEL 8 — Candidate generation 🟡

- **Files:** `logic/candidates.py`, `scripts/ablation.py`.
- **Understand:** why blocking is a *recall boundary*; why ANN deliberately does
  not filter by category.
- **Exercise:** `make ablation`, then set `ANN_ENABLED=false` and compare.

### LEVEL 9 — The trained models 🟡

- **Prerequisites:** Level 7.
- **Files:** `logic/classifier.py`, `logic/calibration.py`, `logic/fusion.py`,
  `scripts/train_*.py`.
- **Understand:** why an F1 of 1.000 here is a warning, not a result.
- **Exercise:** `make train`, then read `data/models/fusion_weights.json` and
  compare the fitted coefficients against `WEIGHTS` in `score.py`.

### LEVEL 10 — The LLM path 🟢

- **Files:** `logic/llm.py`, `tests/test_layer7.py` (the LLM tests).
- **Understand:** the four safety constraints; why it is off by default.

### LEVEL 11 — Docker and deployment 🟡

- **Files:** `Dockerfile`, `docker-compose.yml`, `Makefile`, `.github/workflows/ci.yml`.
- **Exercise:** `docker compose up`, ingest, index, match, all through curl.

### LEVEL 12 — Extend it 🟢

Pick one: add a material family end-to-end (CSV + descriptor + test); expose
`cluster()` as an endpoint; write the missing `metrics.py` tests.

---

# PART 33 — Module-by-Module Tutoring Plan

### Module 1 — Domain and vocabulary

```
Purpose:       Understand the problem before any code.
Prerequisites: none
Files:         docs/00_INDEX.md, docs/01_SYSTEM_ARCHITECTURE.md,
               backend/pipeline-one/CPSE_SIH26099.csv,
               app/logic/enums.py
Concepts:      material master, CPSE, the four verdicts, attribute roles
Understand:    why MISSING ≠ DIFFERENT; why a false merge is the dangerous error
Questions:     · What are the four relationships and what does each mean?
               · What are the three attribute roles and what does a conflict do
                 in each?
               · Why can rules only LOWER a verdict?
Exercise:      Open the CSV. Find two rows you believe are the same bearing.
               Write down which properties prove it.
Difficulty:    ★☆☆☆☆
```

### Module 2 — Configuration as data

```
Purpose:       See that domain knowledge lives in CSV, not Python.
Prerequisites: Module 1
Files:         data/config/*.csv, app/logic/reference.py
Concepts:      CSV parsing, frozen dataclasses, @lru_cache
Understand:    AttributeSpec / CategorySpec / PipelineConfig; role assignment
Questions:     · Where do the extraction regexes live?
               · Why are abbreviations sorted longest-first?
               · What does `scope` do in abbreviations.csv?
Exercise:      Add a WELDING row to category_attributes.csv with an
               `electrode_size` attribute and prove it extracts.
Difficulty:    ★★☆☆☆
```

### Module 3 — Phase A: understanding one material

```
Purpose:       Trace S1–S7 completely.
Prerequisites: Modules 1–2
Files:         clean.py, tokenize.py, units.py, extract.py, validate.py,
               classify.py, classifier.py, quality.py, standardize.py
Concepts:      regex, Unicode NFKC, Pint dimensions, INFERRED values
Understand:    why tokenize runs BEFORE expand; why nothing is ever deleted
Questions:     · What bug does tokenize.py exist to prevent?
               · What are the three outcomes of resolve_uom()?
               · Why is a derived bore marked INFERRED rather than PRESENT?
Exercise:      Run standardize() on 5 descriptions you invent, including one
               deliberately malformed. Explain every quality flag.
Difficulty:    ★★★☆☆
```

### Module 4 — Phase B: comparing two materials

```
Purpose:       Understand how a verdict is produced.
Prerequisites: Module 3
Files:         compare.py, score.py, rules.py, matcher.py, explain.py
Concepts:      weighted sum, multiplicative penalties, rule ceilings
Understand:    the six conditions for EXACT_DUPLICATE
Questions:     · Why do penalties multiply instead of subtract?
               · Why is lexical similarity only 0.10?
               · What does cap_relationship() guarantee?
               · Why can a merely low score never earn FUNCTIONALLY_EQUIVALENT?
Exercise:      Hand-compute the score for two materials, then assert it matches
               `signals` in the API response.
Difficulty:    ★★★★☆
```

### Module 5 — Persistence

```
Purpose:       Learn how results reach PostgreSQL.
Prerequisites: SQL basics (Level 4)
Files:         app/database.py, app/models/*, app/services/ingest.py
Concepts:      ORM, session, transaction, selectinload, N+1
Understand:    raw vs derived tables; why review has no FK
Questions:     · What does create_all NOT do?
               · Why is match_result deleted on every run?
               · What breaks without selectinload?
Exercise:      Add a column to StandardizedMaterialRow. Discover why it does not
               appear until you drop the table.
Difficulty:    ★★★☆☆
```

### Module 6 — The HTTP surface

```
Purpose:       Connect the pipeline to the outside world.
Prerequisites: Module 5
Files:         app/main.py, app/routes/*, app/schemas/*, app/auth.py
Concepts:      FastAPI, Pydantic, dependency injection, status codes
Understand:    the four layers and what each may NOT do
Questions:     · Why does a service return None instead of raising 404?
               · Why is /materials/quality registered before /materials/{id}?
               · Why does auth fail closed?
Exercise:      Add GET /api/v1/materials/{id}/attributes end to end, with a test.
Difficulty:    ★★★☆☆
```

### Module 7 — Embeddings and the vector store

```
Purpose:       Understand semantic retrieval.
Prerequisites: Module 4
Files:         embedding.py, retrieval.py, services/indexing.py
Concepts:      vectors, cosine, L2 norm, HNSW, protocols, singletons
Understand:    why the canonical form is embedded, not the raw text
Questions:     · Why does DeterministicProvider exist?
               · Why does is_fallback matter for a demo?
               · What is canonical_hash for?
               · Why must a dimension mismatch fail loudly?
Exercise:      Index with the deterministic provider, then with qwen3, and
               compare the neighbours for CCL-000001.
Difficulty:    ★★★★☆
```

### Module 8 — Candidate generation and the ablation

```
Purpose:       Understand why the corpus is not compared pairwise.
Prerequisites: Module 7
Files:         candidates.py, scripts/ablation.py
Concepts:      blocking, union recall, fingerprints, trigram
Questions:     · Why does the ANN path NOT filter by category?
               · Why does an unclassified query block against nothing?
               · Why does a fingerprint require complete identity attributes?
Exercise:      make ablation. Explain in one paragraph why `recovered` is 0.
Difficulty:    ★★★★☆
```

### Module 9 — The trained layer

```
Purpose:       Understand what is learned and what is not.
Prerequisites: Modules 4, 7
Files:         classifier.py, calibration.py, fusion.py, scripts/train_*.py
Concepts:      logistic regression, isotonic regression, ECE, distant supervision
Understand:    why circular labels produce F1 = 1.000
Questions:     · What are the three confidence_kind values and how do they differ?
               · Why is the fusion model kept LINEAR?
               · How does the code stop a model learning past a safety rule?
Exercise:      make train. Read the printed caveat. Explain it in your own words.
Difficulty:    ★★★★★
```

### Module 10 — LLM, security, operations

```
Purpose:       The remaining pieces.
Prerequisites: Modules 6, 9
Files:         llm.py, auth.py, Dockerfile, docker-compose.yml, Makefile
Concepts:      prompting, structured output, constant-time compare, Docker
Questions:     · What are the four constraints on LLM output?
               · Why must ai-service never be public?
               · What happens if Qdrant is deleted?
Exercise:      Bring the whole stack up in Docker and run a full session.
Difficulty:    ★★★☆☆
```

---

# PART 34 — Do Not Learn This Yet

Postpone these. They will not help you understand the core system, and each is a
rabbit hole.

| Topic | Why postpone |
|---|---|
| **PyTorch internals** (autograd, custom layers) | You never train a neural network here. You *call* one. `AutoModel.from_pretrained` + `inference_mode` is the entire surface you need. |
| **Transformer architecture** (attention maths) | Interesting, irrelevant to modifying this code. Treat the embedding model as "text in, 1024 numbers out". |
| **HNSW internals** | You configure `m` and `ef_construct`; you never implement the graph. |
| **Advanced async internals** (event loops, tasks, gather) | The code only uses `async def` + `await` + `async with`. No `gather`, no `create_task`, no custom loops. |
| **Docker networking, multi-stage builds** | One simple Dockerfile, one compose file, default bridge network. |
| **Alembic / migrations** | `ai-service` has none. `api-service` has zero migrations written. |
| **api-service in depth** | It is a scaffold. Only `ai_client.py` matters to you — and it is broken. |
| **Frontend / Next.js / React** | One status page. Not your responsibility. |
| **SQLAlchemy relationship loading strategies** | Learn `selectinload` and why it is required. Skip lazy/joined/subquery for now. |
| **Pydantic v2 internals** (validators, serializers) | These schemas use plain fields and `Field(min_length=…)`. Nothing custom. |
| **Ollama / local LLM serving** | The feature is off by default and the system is designed to work without it. |
| **spaCy pipeline internals** | You call a trained model and read `doc.ents`. |
| **Isotonic regression maths** | Understand *what* calibration is for; the monotone-fitting algorithm can wait. |
| **Qdrant clustering / sharding / quantisation** | Single node, 404 vectors. |


---

# PART 35 — Unknown / Unclear / Potential Issues

Documented, **not fixed**. Verify before changing anything.

## 35.1 Confirmed bugs 🔴

**1. `api-service` calls an endpoint that does not exist.**
`backend/api-service/app/services/ai_client.py::infer()` posts to
`/api/v1/inference/predict`. `ai-service` has 13 endpoints and that is not one.
`POST /api/v1/ai/infer` on `api-service` will always return 502.
*Verify before removing:* is any client calling it? (The frontend does not.)

**2. `EMBEDDING_PROVIDER=auto` is not a valid value.**
The root [`.env.example`](.env.example) sets `EMBEDDING_PROVIDER=auto`, but
`embedding.py::get_provider()` only tests `== "qwen3"`. Anything else — including
`auto` — silently becomes the deterministic hash provider. A demo started from
that file would think it was running Qwen3 and would not be. Note
`docker-compose.yml` correctly uses `deterministic`.

**3. `api-service` users are stored in an in-memory dict.**
`backend/api-service/app/api/routes/users.py`. Restart the process, lose the
users. Documented in `docs/02` as a known defect.

## 35.2 Dead code — verify before removing 🟡

> Possibly unused / dead code — verify before removing.

| Symbol | File | Evidence |
|---|---|---|
| `_SPLIT_ON` | `app/logic/tokenize.py` | defined, never referenced |
| `identity_evidence()` | `app/logic/validate.py` | defined, never called |
| `identity_summary()` | `app/logic/explain.py` | defined, never called |
| `uom_gate_blocks_auto_approval()` | `app/logic/score.py` | defined, never called — **the auto-approval block it implements is therefore not wired in** |
| `tenacity>=9.1.0` | `pyproject.toml` | declared, never imported. There is no retry logic anywhere. |
| `backend/pipeline-one/raw_sap_data_chaotic.csv` | 17 rows | nothing reads it |
| `backend/pipeline-one/extractor.ipynb` | notebook | nothing in the service reads it |
| `backend/pipeline-one/schema.json` | | nothing reads it |
| `data/standardized/materials.jsonl` | | written by `export_jsonl`, **never read back** |
| `matcher.py::cluster()` | | implemented and correct, exposed by no endpoint and covered by no test |

## 35.3 Documentation that overstates the code 🟡

| Claim | Reality |
|---|---|
| `docs/07` — "structured JSON logs" | Logging is plain-text via `logging.Formatter`. Not JSON. |
| `docs/07`, `docs/05` — request-ID correlation | Not implemented. No request IDs anywhere. |
| `docs/06` — RFC 9457 `problem+json` errors | FastAPI's default `{"detail": "..."}` is used. |
| Blueprint — a job queue / workers | None. `match-all` is fully synchronous. |
| Blueprint — cross-encoder re-ranking | **Not implemented.** No cross-encoder anywhere. |
| `pyproject.toml` includes mypy | mypy is **not** in CI; `.github/workflows/ci.yml` runs only `ruff` and `pytest`. |

## 35.4 Design tensions worth knowing 🟡

**The UOM rule is advisory in two places, differently.**
`rules.py::_uom_rule` hard-codes `advisory=True`, while `score.py::uom_gate_factor`
honours `UOM_GATE_MODE`. Setting `UOM_GATE_MODE=strict` therefore damps the
*score* but the *rule* stays advisory. These two mechanisms are not linked, and
`uom_gate_blocks_auto_approval()` — which would link them — is never called.

**The LEGACY ingest is a full reload, not an upsert.**
`services/ingest.py::persist(replace=True)` deletes all four material tables
before inserting, so `POST /materials/ingest` with a second CPSE file replaces
the first. This is still true and is kept deliberately — it is the fastest way
to reload the demo corpus.

`POST /ingest/by-reference` with `mode=merge` (the default) is the fix:
`reference_ingest.py::_delete_for_cpses()` deletes only the CPSEs present in
the file being imported. Note it is a **per-CPSE replace, not a row-level
upsert** — `material_id` is derived from row position (`{cpse}-{source_row:06d}`),
so a row-level merge would need a stable business key first. Re-uploading the
same CPSE is idempotent; interleaving two files for the *same* CPSE is not
supported.

**The api-service half of the upload flow does not exist.** The ai-service
endpoint is built and tested, but nothing calls it: no upload endpoint, no
`ai_client.ingest_by_reference()`, no shared volume in compose. See Part 5.3.

**`match-all` drops `NOT_EQUIVALENT` by default.**
```python
if candidate.relationship is Relationship.NOT_EQUIVALENT and not keep_not_equivalent:
    continue
```
Justified in the code (they are the large majority and add nothing a reviewer
acts on) — but it means `match_result` is not a complete record of what was
compared.

**Thresholds are global, not per-category.**
`EXACT_THRESHOLD` etc. are single floats in `Settings`. The blueprint specifies
per-taxonomy-node thresholds with a `threshold_policy` table. Not built.

**No `policy_version` stamp.** The blueprint requires routing decisions to record
which thresholds were in force. Eight stamps are recorded; the threshold values
are not among them.

## 35.5 Hard-coded values that should probably be configuration 🟡

| Value | File | Note |
|---|---|---|
| `WEIGHTS` (5 floats) | `score.py` | module constants; the *learned* versions go to a file, the priors do not |
| `IDENTITY_CONFLICT_PENALTY = 0.15` etc. | `score.py` | module constants |
| `INFERRED_WEIGHT = 0.5` | `compare.py` | class attribute |
| `TRIGRAM_CUTOFF = 70.0`, `TRIGRAM_LIMIT = 10` | `candidates.py` | module constants |
| `NER_CONFIDENCE = 0.62`, `LLM_CONFIDENCE = 0.45` | `ner.py`, `llm.py` | module constants |
| `TIER2_MIN_CONFIDENCE = 0.55`, `TIER3_MIN_CONFIDENCE = 0.30` | `classifier.py` | module constants |
| `RANGES` (10 attribute ranges) | `validate.py` | should arguably be in the CSV alongside the attributes |
| `GRADE_IMPLIES_MATERIAL` | `validate.py` | domain knowledge in Python, not CSV |
| `NOMINAL_BORE_MM` (24 sizes) | `units.py` | domain knowledge in Python |
| `CPSE_CODES` | `standardize.py` | 8 hard-coded company-name mappings |
| `_ATTRIBUTE_SIGNATURES` | `classifier.py` | 3 hard-coded signatures |
| `ITERATIONS = 30` | `scripts/train_ner.py` | training epochs |

**The pattern:** the project's stated principle is "dictionaries are data, not
code", and the *extraction patterns* genuinely follow it. But scoring weights,
penalties, ranges and several domain tables are still Python constants.

## 35.6 Missing validation 🟡

- `reviewer` and `decision` on `POST .../review` are free strings. `decision`
  accepts anything — `"BANANA"` is stored happily. There is no enum.
- `POST /materials/ingest` takes no parameters; the path comes from settings.
  You cannot ingest a different file without changing configuration.
- No maximum on corpus size anywhere. `load_standardized()` will happily try to
  load a million rows into memory.

## 35.7 Duplicated logic 🟡

- **Blocking is implemented twice** — `BlockOnlyRetriever.retrieve()` and
  `UnionRetriever.retrieve()` contain the same category-block comprehension.
- **`MatchingEngine.block()` is now a thin wrapper** that discards the
  provenance from `CandidateSet`. It exists for backwards compatibility.
- **`clean.py::normalize_uom()` and `units.py::resolve_uom()` overlap.**
  `standardize.py` still calls the simpler `normalize_uom`; the richer
  `resolve_uom` (with `kind` and `factor`) is used by tests and is **not** on the
  main pipeline path.

## 35.8 TODOs

`grep -rn "TODO\|FIXME\|XXX\|HACK" backend/ai-service/app` → **no matches.**
There are no TODO comments in the service.

## 35.9 Things I could not determine from the code

- Whether the 404-row CSV is real CPSE data or synthetic. The UOM column is
  distributed almost uniformly across 9 values with **0% agreement within
  attribute-identical groups**, which is consistent with random assignment — but
  the file's provenance is not recorded anywhere. *Unable to determine from the
  current code.*
- Whether `EMBEDDING_DEVICE=cuda` works. No GPU code path is tested.
- Whether the LLM fallback produces useful output. The success path has never
  been run against a live Ollama in this repository.

---

# PART 36 — Claude-Generated Code Warning

Parts that look harder than they are.

### 1. `Protocol` classes 🟡

**Why it looks complicated:** `class Matcher(Protocol)` with method bodies that
are just `...`.

**What it actually does:** documents a shape. Any class with a `score()` method
of the right signature *is* a `Matcher` — no inheritance, no registration.

**Simpler mental model:** a job description. "If you can do these things, you can
have this job."

### 2. `@lru_cache` on functions that take no arguments 🟡

**Why it looks complicated:** caching something that takes no input seems pointless.

**What it does:** turns the function into a **lazy singleton**. The first call
computes; every later call returns the same object.

**Simpler mental model:** "compute this once, then remember it forever."

### 3. Lazy imports inside `__init__` 🟡

```python
def __init__(self, ...):
    import torch
    from transformers import AutoModel, AutoTokenizer
```

**Why it looks wrong:** imports belong at the top of a file.

**What it does:** keeps a 2 GB library out of a process that will never use it.
`ai-service` runs fine with no torch installed *because* this import is here and
not at module level.

**Simpler mental model:** "only unpack the heavy toolbox if someone actually asks
for it."

### 4. `dataclasses.replace()` everywhere in `validate.py` 🟡

**Why it looks complicated:** why not `attribute.confidence = 0.35`?

**What it does:** the dataclass is `frozen=True`, so it cannot be mutated.
`replace()` makes a **copy** with one field changed.

**Simpler mental model:** photocopy the form, change one box, keep the original.

**Why it was done this way:** an immutable object cannot be corrupted by code
three call-frames away.

### 5. The `matrix @ vector` line 🟡

```python
scores = matrix @ vector.astype(np.float32)
```

**Why it looks like magic:** one symbol doing a lot.

**What it does:** `@` is matrix multiplication. `matrix` is (N × 1024),
`vector` is (1024,), so the result is (N,) — the similarity of the query against
every stored material, in one operation.

**Simpler mental model:** "compare against all of them at once instead of
looping."

**Why:** a Python loop over 404 × 1024 multiplications is thousands of times
slower.

### 6. Union-find in `cluster()` 🟢

```python
def find(x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]     # ← path compression
        x = parent[x]
    return x
```

**Why it looks complicated:** self-referential dictionary with a re-assignment
inside the loop.

**What it does:** groups items into clusters. `parent` maps each item to a
"leader". `find` walks up to the leader, flattening the chain as it goes.

**Simpler mental model:** everyone points at their boss; keep asking "who's your
boss?" until you reach someone who is their own boss. Path compression = "and
while I'm here, let me point you straight at the top."

### 7. `_first_group()` in `extract.py` 🟡

**What it does:** a regex may or may not have capture groups. If it has none,
the whole match is the value; if it has some, the first non-empty one is.

**Simpler mental model:** "take the highlighted part if there is one, otherwise
the whole thing."

### 8. The `lifespan` async context manager 🟡

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    ...setup...
    yield
    ...teardown...
```

**Simpler mental model:** everything before `yield` is "before the doors open";
everything after is "after the last customer leaves".

### 9. Chained `@property` computations in `ComparisonResult` 🟡

`comparable` uses `matched`/`conflicting`/`inferred`; `match_ratio` uses
`comparable`; `identity_agreement` filters by role. Each recomputes on access.

**Why it looks complicated:** nothing is stored; every access re-filters the list.

**Why it is fine:** the lists have at most ~10 items. Clarity beats
micro-optimisation here.

### 10. The `Score.kind` / `matcher_version` string juggling 🟡

**Why it looks over-engineered:** why not just return a float?

**What it protects:** three different things can produce that number, and they
make three different claims about the world. A reviewer shown `0.93` deserves to
know whether it means "weighted sum" or "93% of pairs like this really were matches".

**Simpler mental model:** a food label. The number is the calories; the `kind` is
whether it was measured or estimated.

### 11. `settings` as a module-level singleton 🟡

```python
settings = get_settings()      # runs at import time
```

**Why it looks risky:** global mutable state.

**What it means practically:** tests mutate it directly
(`settings.use_llm_fallback = True`) and must reset it in a `finally` block.
Several tests in `test_layer7.py` do exactly that. **If you write a test that
changes a setting, reset it.**


---

# PART 37 — Cheat Sheet

```
PROJECT
  Smart India Hackathon 2026 · Problem Statement 26099
  AI-Driven Standardization and Harmonization of Material Codes Across CPSEs
  Ministry of Petroleum & Natural Gas · CPCL

SERVICES
  frontend      Next.js 16          :3000   scaffold
  api-service   FastAPI             :8000   scaffold, NOT implemented
  ai-service    FastAPI             :8001   ★ YOURS — complete, 138 tests
  postgres      PostgreSQL 16       :5432   source of truth
  qdrant        Qdrant v1.19.0      :6333   derived vector index

DATABASE
  numm_ai (ai-service) · sih (api-service)
  7 tables: material · standardized_material · material_attribute ·
            quality_flag · match_result · review · audit_log
  No migrations — Base.metadata.create_all at startup

AI PIPELINE
  Phase A (per material)  clean → tokenize → classify(1) → expand → units →
                          extract → NER → LLM(off) → infer → validate →
                          classify(2) → canonical + fingerprint
  Phase B (per pair)      retrieve → compare → score → rules → decide → explain

EMBEDDING MODEL
  Qwen/Qwen3-Embedding-0.6B · 1024-d · CPU · batch 32 · L2-normalised
  Fallback: DeterministicProvider (seeded hash, MEANINGLESS retrieval)
  Which is live:  GET /api/v1/retrieval/model/info  →  is_fallback

LLM
  qwen2.5:3b-instruct via Ollama · OFF BY DEFAULT · extraction fallback only
  Constraints: schema-constrained · validated · confidence 0.45 · never
               identity-defining for auto-approval

MATCHING METHOD
  weighted structural agreement (0.90) + lexical (0.10),
  multiplicative penalties, hard rules with veto power
  WEIGHTS   identity_agreement .45 · match_ratio .20 · category .15 ·
            completeness .10 · lexical .10
  PENALTIES identity_conflict 0.15^n · discriminating 0.75^n · missing 0.80^n
  THRESHOLDS  ≥0.90 EXACT · ≥0.72 NEAR · ≥0.55 FUNCTIONAL · else NOT_EQUIVALENT
  RULES     CATEGORY · IDENTITY_CONFLICT · IDENTITY_EVIDENCE ·
            DISCRIMINATING · UOM (advisory)

IMPORTANT ENDPOINTS
  GET  /health
  POST /api/v1/materials/ingest                 legacy: reads disk, wipes all
  POST /api/v1/ingest/by-reference              real: api-service stored it
  GET  /api/v1/ingest/jobs
  GET  /api/v1/ingest/jobs/{job_id}
  GET  /api/v1/ingest/jobs/{job_id}/errors
  GET  /api/v1/materials?cpse=&category=&limit=&offset=
  GET  /api/v1/materials/quality
  GET  /api/v1/materials/{id}
  GET  /api/v1/materials/{id}/matches?top_k=
  POST /api/v1/materials/match-all
  POST /api/v1/materials/matches/{match_id}/review
  POST /api/v1/materials/ground-truth/build?target=
  GET  /api/v1/materials/evaluation/report
  POST /api/v1/retrieval/index?force=&recreate=
  GET  /api/v1/retrieval/status
  GET  /api/v1/retrieval/model/info

IMPORTANT COMMANDS
  make install-ai     venv + dependencies
  make install-ml     + torch/transformers (~2 GB, optional)
  make dev-ai         uvicorn --reload :8001
  make test-ai        138 tests
  make lint           ruff
  make ingest         load the 404-row extract
  make index          embed into the vector store
  make match          match the corpus
  make evaluate       score against gold labels
  make train          fit classifier + NER + fusion + calibration
  make ablation       measure what ANN adds
  make model-info     which provider is live

DOCKER
  docker compose up --build
  docker compose up -d qdrant
  docker compose logs -f ai-service
  docker compose down
  docker volume rm sih-2026_qdrant-data     # after a Qdrant major upgrade

TESTS
  cd backend/ai-service && .venv/bin/pytest -q
  .venv/bin/pytest tests/test_matching.py -q
  QDRANT_TEST_URL=http://localhost:6333 .venv/bin/pytest -q      # 148

KEY ENVIRONMENT VARIABLES
  EMBEDDING_PROVIDER   deterministic | qwen3
  VECTOR_STORE         memory | qdrant
  ANN_ENABLED          true
  UOM_GATE_MODE        advisory | damp | strict
  USE_NER              true
  USE_LLM_FALLBACK     false        ← keep it false
  UPLOAD_DIR           data/uploads  the only referenceable directory
  ALLOW_REMOTE_REFERENCE false      ← SSRF; keep it false
  MAX_ROW_ERROR_RATE   0.30
  USE_LEARNED_FUSION   true
  USE_CALIBRATION      true
  TOP_K                10
  EXACT/NEAR/FUNCTIONAL_THRESHOLD   0.90 / 0.72 / 0.55
  REQUIRE_INTERNAL_KEY false
  DB_HOST/DB_NAME/DB_USER/DB_PASSWORD

FILES YOU WILL EDIT MOST
  data/config/category_attributes.csv    what to extract, and its role
  data/config/abbreviations.csv          domain shorthand
  app/logic/classify.py                  keyword rules for families
  app/logic/score.py                     weights and penalties
  app/logic/rules.py                     the hard gates

MEASURED FACTS (this repository)
  corpus                404 materials · 8 CPSEs · 21 categories present
  attributes extracted  995
  rows with quality flags  367
  match-all             2,946 stored · 1,951 exact · 985 near
  endpoints             17 (13 + 4 ingest-by-reference)
  tests                 138 (+10 opt-in Qdrant)
  ANN ablation          recovered 0 · lost 0
  NER held-out          P 0.831 · R 0.682 · F1 0.749
  fusion cross-val F1   1.000  ← a WARNING (circular labels), not a result
  UOM signal            0% of attribute-identical groups share a unit
```

---

# PART 38 — Final One-Page Mental Model

Read this before studying anything else, and again afterwards.

---

**The problem.** Eight public-sector companies each keep their own list of
things they buy. The same ball bearing is `brg ball rad 6205 2rs` in one list and
`BEARING, BALL, 6205-2RS1` in another. Nobody can tell they are the same, so the
country buys, stores and counts the same bearing many times over.

**What the system does.** It reads those lists and decides, for any two rows,
whether they are the *same article*, *almost the same*, *interchangeable*, or
*genuinely different* — and it shows the evidence.

**The api-service** is meant to own people and process: logins, permissions,
uploads, the review queue, issuing national codes. **It is a scaffold. It does
not do these things yet.**

**The ai-service — yours — is responsible for all the understanding.** It takes a
messy 40-character description and turns it into engineering structure:
`bearing_number=6205`, `bearing_type=BALL`, `seal_type=2RS`. Every extracted
property carries a **role**: identity-defining (a conflict means different
material), discriminating (a conflict needs an engineer), or descriptive
(ignore it). That role table lives in a CSV a materials engineer can edit.

**The database stores** the raw CPSE row exactly as sent — never modified — and
every derived value beside it. Corrections are *flags next to* the original, not
edits. Human decisions are stored so they survive every re-run of the matcher.

**Embeddings are used to** find which pairs are *worth looking at*. Text becomes
1024 numbers, and similar meanings land near each other, so `BEARING BALL 6205`
finds `BALL BEARING 6205` even though the strings differ. Qdrant stores those
vectors and searches them fast.

> **The embedding never decides anything.** It only nominates candidates. This is
> the single most important design rule in the project, and there is a test that
> enforces it.

**The matching engine decides.** It compares the extracted properties one by
one — agree, conflict, missing, or derived — turns that into a number, and then
lets five hard rules review it. **Rules can only lower a verdict, never raise
it.** A grade conflict between SS304 and SS316 forces `NOT_EQUIVALENT` no matter
how similar the text looks, because putting the wrong steel into a refinery is a
safety event and a missed saving is not.

**Crucially, "missing" is not "different".** If one record says nothing about the
seal type, that is not evidence of disagreement — it lowers confidence and
blocks the strongest verdict, but it never counts as a conflict.

**The LLM is used for** almost nothing, on purpose. It is off by default. Its
only permitted job is guessing attributes from the small fraction of
descriptions that no rule could parse — and even then its output is validated
like everything else, marked as low-trust, and forbidden from being the sole
basis of a merge. A national register has to explain its decisions years later,
and a language model cannot be audited or replayed.

**The final result** is a verdict, a confidence number that says what kind of
number it is, the full attribute-by-attribute evidence, which rules fired, and
eight version stamps naming exactly which code produced it — all stored, so the
decision can be defended long after everyone has forgotten it.

**And the honest part.** Three of the fancier capabilities — semantic retrieval,
the NER model, the classifier's learned tiers — are built, correct, tested, and
currently **add nothing measurable on this 404-row corpus**, because keyword
rules and category blocking already cover it. The trained fusion model reports a
perfect F1, which is a *warning*, not an achievement: it was trained on labels
derived from the very attributes it compares. All of this is written down in the
code, in the docs, and in `make ablation`, because a system that overstates
itself is worse than one that does less.

---

*Generated from the repository at `feat/sangik-develop`. Every file path,
number, formula and measurement in this document was verified against the code.*
