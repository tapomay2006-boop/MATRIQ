# 01 · System Architecture

> Scope: the whole picture — who uses the system, what they do, which service
> handles each step, and how a material travels from a CPSE spreadsheet to a
> national code.
>
> Build status is marked throughout: **Built** (`ai-service`), _Planned_
> (`api-service`, frontend).

---

## 1. The problem

Several CPSEs each maintain their own material master. The same bearing is
`DEEP GROOVE BALL BEARING 6205 2RS` at one, `BRG BALL DP GRV 6205-2RS SKF` at
another, and `Bearing,Ball,6205 2RS (URGENT)` at a third. Nobody can say how much
of the national inventory is the same thing under different names.

Deduplication is the visible goal. The real deliverable is a **defensible**
answer: for any two codes, a verdict plus the evidence for it, in language a
materials engineer can argue with.

---

## 2. Who uses it

| Actor                  | Works at      | Does                                                                                   |
| ---------------------- | ------------- | -------------------------------------------------------------------------------------- |
| **CPSE uploader**      | One CPSE      | Submits the material extract; fixes what the quality report flags                      |
| **CPSE reviewer**      | One CPSE      | Decides duplicate candidates involving their own materials                             |
| **CPSE admin**         | One CPSE      | Manages that CPSE's users                                                              |
| **National reviewer**  | NUMM / CPCL   | Decides cross-CPSE pairs; issues national codes                                        |
| **National admin**     | NUMM / CPCL   | Manages CPSEs, roles, and the domain configuration CSVs                                |
| **Materials engineer** | Domain expert | Owns attribute **roles** and the gold labels — the two inputs every verdict depends on |
| **Viewer**             | Any CPSE      | Read-only dashboards and exports                                                       |

The materials engineer is the actor most easily forgotten and the most
important. They do not use a screen to approve pairs; they edit
`category_attributes.csv` to say that `thread_size` is identity-defining and
`finish` is not. Every automated verdict in the system is downstream of that
judgement — see [03 §9](03_ML_ARCHITECTURE.md).

---

## 3. The end-to-end journey

```
 ┌──────────┐
 │ uploader │ 1. upload CPSE extract (CSV/XLSX)
 └────┬─────┘
      ▼
 ┌───────────────────────────────────────────────────────────┐
 │ api-service      Planned                                  │
 │   authenticate · check role · store batch verbatim        │
 │   sha256 → is this the same file again?                   │
 └────┬──────────────────────────────────────────────────────┘
      │ 2. handoff
      ▼
 ┌───────────────────────────────────────────────────────────┐
 │ ai-service       Built                                    │
 │   PHASE 1  clean · classify · normalize · extract         │
 │            + data-quality flags (nothing corrected)       │
 └────┬──────────────────────────────────────────────────────┘
      │ 3. quality report back
      ▼
 ┌──────────┐
 │ uploader │  "286 rows have an implausible UOM" — fix at source
 └────┬─────┘
      │ 4. run matching
      ▼
 ┌───────────────────────────────────────────────────────────┐
 │ ai-service       Built                                    │
 │   PHASE 2  block · compare · score · rules · verdict      │
 │            EXACT / NEAR / FUNCTIONAL / NOT_EQUIVALENT     │
 │            + reason + matched/conflicting/missing         │
 └────┬──────────────────────────────────────────────────────┘
      │ 5. verdicts + evidence
      ▼
 ┌───────────────────────────────────────────────────────────┐
 │ api-service      Planned                                  │
 │   create review tasks, evidence pinned onto the task      │
 │   route: same-CPSE → CPSE reviewer                        │
 │          cross-CPSE → national reviewer                   │
 └────┬──────────────────────────────────────────────────────┘
      ▼
 ┌──────────┐  6. sees both descriptions, the matched and conflicting
 │ reviewer │     attributes, and the one-sentence reason
 └────┬─────┘     approve · reject · need more info
      ▼
 ┌───────────────────────────────────────────────────────────┐
 │ api-service      Planned                                  │
 │   7. issue or link NUMM-BEARING-000001                    │
 │      every CPSE's legacy code preserved in code_mapping   │
 └────┬──────────────────────────────────────────────────────┘
      ▼
   exports · dashboards · the national material master
```

Step 3 is easy to skip and shouldn't be. The quality report is a deliverable in
its own right: it tells a CPSE what is wrong with its master data regardless of
whether any duplicate is ever merged.

---

## 4. Request paths

### Upload · _api-service half planned_

```
browser ──► api-service  POST /api/v1/uploads   (multipart, bearer token)
              │  authenticate, require CPSE_UPLOADER
              │  sha256, header check, INSERT upload_batch + upload_row
              └─ 202 Accepted { batch_id }

            forwards the file ──► ai-service  POST /api/v1/extract/csv
                                    └─ 202 { job_id, total_rows }
                                  poll GET /api/v1/extract/jobs/{job_id}
                                    ◄── processed_rows / total_rows
                                    ◄── completed + the review session
              batch status ⇒ STANDARDIZED
```

The raw row is stored **before** anything is validated, so a failed extraction
never costs the CPSE its upload. Extraction is a background job on the
`ai-service` side too, so neither service holds a request open for the minutes
a 3B model needs.

### Admitting material · **Built end-to-end on `ai-service`**

```
reviewed session ──► POST /api/v1/standardized/check {"session_id": "..."}
                       ◄── { has_new_data, new_rows, existing_rows,
                             new_material: [...], batch_id }
                       nothing written

                 ──► POST /api/v1/standardized/add   {"batch_id": "..."}
                       ◄── { added, indexed, material_ids }
                       Postgres + Qdrant, one transaction
```

`check` writes nothing, so a reviewer sees what would change before it does.
`add` re-checks, so a stale batch cannot create a duplicate.

### Inspecting one material · **Built end-to-end on `ai-service`**

```
browser ──► api-service  GET /api/v1/materials/{id}/matches
              │  authorize: may this user see this material?
              └──► ai-service  GET /api/v1/materials/{id}/matches?top_k=10
                     block → compare → score → rules → decide, live
                   ◄── candidates + reason + matched/conflicting/missing
              filter fields the caller's CPSE may not see
            ◄── the same verdict, unaltered
```

`ai-service` runs the engine live here rather than reading stored results, so a
change to the domain CSVs is visible on the next request.

### Reviewing · _Planned_

```
browser ──► api-service  POST /api/v1/reviews/{task_id}
              { decision: APPROVED, comment: "Confirmed, same SKF part." }
              │  authorize, check required_approvals
              │  INSERT review_decision, advance task state
              │  if approved and complete ⇒ issue/link national code
              └─ INSERT audit_event
```

`api-service` never recomputes the verdict. It records what a human decided about
what `ai-service` said.

---

## 5. Runtime topology

```
┌──────────────────────────────────────────────────────────────────┐
│  frontend        Next.js 16                              :3000   │
│                  upload · quality report · review queue          │
│                  ── Planned (scaffold only)                      │
├──────────────────────────────────────────────────────────────────┤
│  api-service     FastAPI · business state                :8000   │
│                  auth · RBAC · CPSE isolation · uploads          │
│                  review workflow · national codes · audit        │
│                  ── Planned (scaffold only)                      │
├──────────────────────────────────────────────────────────────────┤
│  ai-service      FastAPI · the whole ML pipeline         :8001   │
│                  S1–S7 + retrieval + matching, CPU-only, offline │
│                  ── BUILT. 141 tests.                            │
├──────────────────────────────────────────────────────────────────┤
│  postgres        both services, separate databases       :5432   │
│                  ai-service → numm_ai · api-service → sih        │
│                  connection supplied as DB_HOST/DB_NAME/… parts  │
│                  ── the source of truth                          │
├──────────────────────────────────────────────────────────────────┤
│  qdrant          vector index for ANN retrieval          :6333   │
│                  reachable only from ai-service                  │
│                  ── derived state; rebuildable from Postgres     │
└──────────────────────────────────────────────────────────────────┘

     browser ──► api-service ──► ai-service ──► qdrant
                      │               │
                      └──► postgres ◄─┘
```

The frontend talks **only** to `api-service`. `api-service` is the **only**
client of `ai-service`. That single boundary is why `:8001` must not be published
in a real deployment. Where it cannot be guaranteed,
`ai-service` authenticates nobody; the network is the boundary
on every route except `/health` — defence in depth, not a user model.

There is a vector database and an in-process embedding model; there is still no
model _server_, no queue and no object store. Models load once at startup and
stay warm, and everything runs on CPU with the network unplugged.

**Qdrant is derived state.** Every vector is reproducible from
`material.canonical_text` by re-running the active model, so deleting the whole
index is a job to re-run rather than an incident. No business decision reads from
it except candidate _retrieval_, and no field exists only in a Qdrant payload —
commercially sensitive columns are deliberately absent from it.

### Who owns what

| Service       | Owns                                                                                                                  | Must never own                                                                                   |
| ------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `ai-service`  | Standardization, extraction, quality flags, matching, rules, metrics, review workflow engine, national master mapping | **All** authentication and authorisation — it has no user model, no roles and no caller identity; an optional `actor` label in the request body is recorded for the audit trail |
| `api-service` | Gateway user authentication, user sessions, UI proxying                                                               | Any matching logic                                                                               |
| `frontend`    | Presentation, review UI, dashboards                                                                                   | Any decision logic                                                                               |

> 📌 **Architectural Note**: For service independence and end-to-end integration testing, `ai-service` implements the complete backend governance capabilities (company review queues, national review queues, 4-role RBAC enforcement via `auth.py`, and national material code mapping). `api-service` acts as the user session gateway and proxies requests with user context headers.

---

## 6. Inside `ai-service`: extraction, then the vector DB

Two halves and one seam. The seam is the **standard format**: the eight
canonical CPSE attributes. Left of it is Phase 1 and belongs to a fine-tuned
model; right of it is the vector embedding DB.

```
   Raw CSV / XLSX / TXT — a CPSE catalogue, however it is laid out
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ PHASE 1 — app/logic/extraction.py                             │
│           VENDORED from backend/pipeline-one                  │
│                                                               │
│  Qwen2.5-3B + qwen2.5-3b-cpse-lora-v2, 4-bit NF4, ~2.0 GB     │
│  VRAM, CPU bfloat16 fallback. Off by default.                 │
│                                                               │
│  row_to_composite_text  every populated cell of a row folded  │
│                         into one string. THIS IS WHY THERE IS │
│                         NO COLUMN INFERENCE ANYWHERE: rather  │
│                         than guessing which column holds a    │
│                         description, the model reads the lot. │
│                                                               │
│  generate + parse       ChatML, greedy, max 256 tokens; a     │
│                         four-step JSON repair ladder          │
│                                                               │
│  ground_attributes      DISCARDS anything the model produced  │
│                         that the input text does not contain. │
│                         This is what makes a generative       │
│                         extractor safe near a national        │
│                         register.                             │
│                                                               │
│  Runs as a background job. Chunks of five (the engine clears  │
│  the CUDA cache every fifth record), each chunk committed as  │
│  it lands: progress is visible AND durable, and a run that    │
│  dies at row 217 keeps those 217.                             │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
   review session — extraction_session + extraction_record
   `predicted` kept beside `current`, so a human correction never
   erases what the model said. Nothing here is in the master yet.
        │
        ▼
╔═══════════════════════════════════════════════════════════════╗
║ THE STANDARD FORMAT — app/logic/standard_format.py            ║
║                                                               ║
║  Company · Item Description (Raw) · Item Code / Legacy Ref ·  ║
║  Quantity · UOM · Part Number / OEM Number · Make / Brand ·   ║
║  Specifications / Dimensions                                  ║
║                                                               ║
║  "NA" means ABSENT, not a value.                              ║
╚═══════════════════════════════════════════════════════════════╝
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ THE BOUNDARY — app/logic/existence.py                         │
│                POST /standardized/check                       │
│                                                               │
│  Is this row already in the vector embedding DB?              │
│                                                               │
│   1. same material_id      {CPSE}-{legacy code}       exact   │
│   2. same canonical_hash   the embedded text matches  exact   │
│   3. same hash earlier in this payload                exact   │
│   4. nearest vector >= EXISTENCE_THRESHOLD (0.90)     fuzzy   │
│                                                               │
│  Exact signals first, because they cannot be wrong. Only (4)  │
│  can, so it carries its score and its neighbour's id into the │
│  response and a human can see why a row was held back.        │
│                                                               │
│  Writes nothing. Stages the new rows against a batch_id.      │
└───────────────────────────────────────────────────────────────┘
        │
   ┌────┴─────────────────────────┐
   │                              │
ALREADY_EXISTS                   NEW
   │                              │
   ▼                              ▼
ignored              POST /standardized/add
                              │
        ┌─────────────────────┴─────────────────────┐
        ▼          ONE TRANSACTION                  ▼
   Postgres                                    Qdrant
   app/models/material.py              app/logic/retrieval.py
   ALL EIGHT attributes                FIVE of the eight, + a vector

   Written together or not at all. There is no rebuild endpoint, so a
   store that will not take the vectors fails the add and writes nothing:
   a row in the master without a vector could never be embedded, and
   every later check would keep calling it new.
```

### Why only five of the eight are embedded

`Company`, `Item Code / Legacy Ref` and `Quantity` are excluded from the
vector, and each exclusion is the difference between finding a duplicate and
missing it:

- **Company** — finding the same article in *another CPSE's* master is the
  entire point of §1. Put the company name in the vector and NTPC's bearing and
  BHEL's identical bearing embed differently, so they never surface together.
- **Item Code / Legacy Ref** — a CPSE's own internal code. Two CPSEs holding
  the same physical part have different codes *by definition*, and a CPSE
  re-coding its master would make every row look new.
- **Quantity** — stock level, not identity. Five of a bearing and five thousand
  of it are the same bearing.

None is lost. `Company` and the legacy code are what `material_id` is built
from, `cpse_code` travels in the vector payload, and all eight are on the row.

**Postgres is the record; Qdrant is a derived index.** Not a staging area: the
three attributes above exist nowhere else.

### The category

A 25-rule keyword table over the description gives every row a family —
`BEARING`, `VALVE`, `FILTER`, … or `UNCLASSIFIED` (100% coverage on the
reference corpus). It is a filter, a payload field the coming search will use,
and an optional blocking key for the duplicate check — **off by default**,
because a row the table puts in the wrong family would never be compared
against its own duplicate.

It is deliberately absent from the embedded text, so a keyword rule can never
move a vector.

### What is deliberately not here

There is no relationship verdict, no rule engine and no matcher. `ai-service`
answers exactly one question about an incoming row — is it worth embedding —
and search over the resulting index is **not built yet**.
[04](04_RETRIEVAL_AND_MATCHER_INTERFACE.md) and
[05](05_MATCHING_AND_RULE_ENGINE.md) describe the removed stack and carry the
reasoning worth revisiting when search is designed.

Detail: [`backend/ai-service/README.md`](../backend/ai-service/README.md) and
[`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md).

---

## 7. Why the pipeline is not a black box

Three properties, each of which costs something:

**Attributes, not just similarity.** A dense vector says two strings are close.
It cannot say _why_, and it cannot be overruled on a specific technical ground.
Extracting `nominal_size`, `bearing_number`, `grade`, `thread_size` as typed
fields makes both possible. The cost is that extraction must be maintained per
category.

**Roles on attributes.** `IDENTITY_DEFINING`, `DISCRIMINATING`, `DESCRIPTIVE`.
A colour difference between two identical bolts is noise; a thread-size
difference is disqualifying. Encoding that as a role, in a CSV, means a
materials engineer changes system behaviour without a code change.

**A third comparison state.** `MISSING` is not `CONFLICT`. Most of this dataset
is incomplete, and treating silence as disagreement would reject nearly every
true duplicate.

---

## 8. Technology choices

| Concern              | Choice                               | Reason                                                                                                                                                   |
| -------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API                  | **FastAPI + Pydantic v2**            | Typed request/response models that generate the OpenAPI contract the frontend consumes.                                                                  |
| ORM                  | **SQLAlchemy 2 async**               | `Mapped[...]` typing, dialect-neutral — the tests run the same models on in-memory SQLite.                                                               |
| Database             | **Postgres 18 + asyncpg**            | Each service owns its own database, never a shared schema. Configured as discrete `DB_*` parts, with `DATABASE_URL` as an override for hosted providers. |
| TLS                  | **libpq sslmode, passed to asyncpg** | `disable`/`allow`/`prefer`/`require`/`verify-*`. Defaults to `prefer`, so a local server still negotiates TLSv1.3.                                       |
| Text similarity      | **RapidFuzz** `token_set_ratio`      | Order-insensitive, tolerant of the token soup in procurement text, no model download. It contributes 0.10 of the score — a tie-breaker, not evidence.    |
| Attribute extraction | **Regex from CSV config**            | Auditable and editable by a domain expert. Every extracted value traces to the pattern that produced it.                                                 |
| Config               | **CSV files under `data/config/`**   | Domain rules are data, not Python. Diffable, reviewable, editable in Excel.                                                                              |
| Frontend             | **Next.js 16, React 19**             | Scaffold present; the review UI is the substantial piece still to build.                                                                                 |

### Deliberately not used

| Not used                                      | Why                                                                                                                                                             |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Qdrant / any vector DB**                    | Nothing is embedded. Blocking on category already reduces the search space; a vector index would add an operational dependency for no gain at this corpus size. |
| **Qwen3-Embedding-0.6B / any neural encoder** | Requires torch (~2 GB), wants a GPU, and its output cannot be defended to an engineer. Removed on instruction.                                                  |
| **FAISS**                                     | A library, not a service: no persistence semantics, no filtered search. Moot once embeddings were dropped.                                                      |
| **spaCy**                                     | Nothing here needs POS tags or NER. Regex over a fixed vocabulary is more predictable and reviewable.                                                           |
| **Pint**                                      | Unit conversion is not the problem; unit _reliability_ is. This dataset's UOM column is randomised, so conversion would formalise noise.                        |
| **Redis / RQ**                                | Jobs are asyncio tasks in the `ai-service` process, bounded by `MAX_CONCURRENT_JOBS`. Adequate for one worker; revisit when a second uvicorn worker is needed, since two processes mean two queues. Replacing `_spawn` is the whole change. |
| **MinIO**                                     | No object-storage requirement.                                                                                                                                  |
| **Any paid embedding API**                    | Offline operation is a hard requirement.                                                                                                                        |

---

## 9. What the dataset forced

`CPSE_SIH26099.csv` was profiled before any matching logic was written. Findings
that changed the design:

| Finding                                                                      | Consequence                                                                                  |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Part Number is 98% synthetic (`PN-####-X`)                                   | Not used as an identity signal.                                                              |
| UOM is randomised — one bearing appears with 8 different units               | The UOM rule is **advisory only**. If it could veto, every true duplicate would be rejected. |
| Make/Brand is randomised (a bearing attributed to "PHILIPS")                 | Not used as an identity signal.                                                              |
| Specifications column does not correlate with the description                | Attributes are extracted from the **description**, not the spec column.                      |
| Legacy code `116045321` is used by Coal India CCL for two different bearings | `material_id` is `{CPSE}-{source_row:06d}`, not the legacy code.                             |
| 0/30 field consistency within known-identical items                          | Structure had to come from text, and no field could be trusted alone.                        |

This is why the scorer weights structural agreement at 0.90 and lexical
similarity at 0.10, and why UOM was demoted from a veto to a flag.

---

## 10. Explainability contract

Every stored match carries:

```
confidence_score        the number
confidence_kind         "heuristic_confidence" — never "probability"
relationship_type       the final verdict
proposed_before_rules   what the score alone would have said
hard_rule_status        PASS / REVIEW / REJECT
reason                  one sentence naming the deciding evidence
matched_attributes      [...]
conflicting_attributes  [...]  with both sides' values
missing_attributes      [...]
rules_triggered         [...]
matcher_version         "deterministic-v1"
rule_version            "rules-v1"
pipeline_version        "pipeline-v1"
```

`proposed_before_rules` alongside `relationship_type` is what makes the rule
engine auditable: you can see exactly which pairs the rules pulled down and why.

These fields must reach the reviewer's screen intact. `api-service` passes them
through and does not recompute them — see [02 §9](02_BACKEND_ARCHITECTURE.md).

---

## 11. Deltas from the solution-design PDF

| #   | PDF says                                                 | Built instead                                                                                            | Why                                                                                                                                                                                                              |
| --- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Vector search in pgvector, Qdrant as the production path | **No vector search at all**                                                                              | Category blocking already bounds the candidate set. Embeddings would add a dependency and remove explainability without improving the verdict.                                                                   |
| D2  | `BAAI/bge-small-en-v1.5`, 384-d                          | **No embedding model**                                                                                   | No labelled data exists to validate that a learned representation beats attribute comparison here, and a similarity number cannot be defended to an engineer.                                                    |
| D3  | Redis + RQ for async batch matching                      | **Synchronous**                                                                                          | 404 rows produce ~4k comparisons in seconds.                                                                                                                                                                     |
| D4  | MinIO for artefacts                                      | **Removed**                                                                                              | No object-storage requirement.                                                                                                                                                                                   |
| D5  | ML logic in `api-service`                                | **All ML in `ai-service`**                                                                               | `api-service` stays a business-state service; the ML pipeline is independently testable and replaceable.                                                                                                         |
| D6  | UOM mismatch disqualifies a pair                         | **Advisory flag**                                                                                        | The dataset's UOM column is unreliable; a veto would reject nearly every true duplicate.                                                                                                                         |
| D7  | Trained Siamese / CMRL matcher                           | **Deterministic matcher, with learned fusion + isotonic calibration behind the same `Matcher` protocol** | No _independent_ labelled corpus exists. The models fit cleanly but on circular labels, so `Score.kind` distinguishes the three claims rather than hiding them. See [04](04_RETRIEVAL_AND_MATCHER_INTERFACE.md). |
| D8  | `bge-small-en-v1.5` (384-d) + pgvector                   | **`Qwen/Qwen3-Embedding-0.6B` (1024-d) + Qdrant**                                                        | Stronger retrieval, native multilingual coverage for Indian-English, and filtered ANN where the filter constrains the traversal rather than post-filtering. Dimension is config, not a schema assumption.        |
| D9  | Top-K = 50                                               | **Top-K = 10**                                                                                           | With category + UOM blocking and a stronger encoder the true match sits in the first few positions; second-stage cost drops 5×. `top_k` is configuration.                                                        |

---

## 12. Repository layout

```
sih-2026/
├── backend/
│   ├── ai-service/          FastAPI · Phase 1 + the vector DB       :8001
│   │   ├── app/
│   │   │   ├── main.py      builds the app, mounts five routers
│   │   │   ├── config.py    settings (.env) + logging
│   │   │   ├── database.py  engine, session, Base
│   │   │   ├── routes/      1. HTTP in, HTTP out
│   │   │   │                extraction · standardized · materials ·
│   │   │   │                retrieval · jobs · health
│   │   │   ├── schemas/     2. request/response models
│   │   │   ├── services/    3. the work
│   │   │   ├── models/      4. seven tables (below)
│   │   │   └── logic/       the algorithms: no HTTP, no DB
│   │   │       ├── extraction.py       VENDORED from pipeline-one
│   │   │       ├── standard_format.py  the 8-attribute contract
│   │   │       ├── standardize.py      a row -> what we store
│   │   │       ├── category.py         the material family
│   │   │       ├── existence.py        already in the vector DB?
│   │   │       ├── embedding.py        what gets embedded
│   │   │       ├── retrieval.py        the vector store
│   │   │       └── identity.py         material_id
│   │   ├── data/config/     abbreviations.csv — the CPSE taxonomy
│   │   └── tests/           141 tests (+10 Qdrant, opt-in)
│   ├── api-service/         FastAPI scaffold · not implemented      :8000
│   └── pipeline-one/        Phase 1 as its own service, the seed
│                            corpus, and the LoRA weights (195 MB)
├── frontend/                Next.js                                 :3000
└── docs/                    this set
```

Seven tables: `extraction_session`, `extraction_record`, `abbreviation`
(Phase 1 working state), `standardization_batch` (what was offered and
admitted), `material`, `audit_log`, `job`.

Each layer only talks to the one below it: a route never runs SQL, a service
never knows about HTTP, and `logic/` imports nothing from the rest of the app.

### The vendored files

`logic/extraction.py` and the `/extract` API surface are **copies** of
`pipeline-one`'s `inference_engine.py` and `app.py`. Copies, not forks:
behaviour must stay identical, the only local edits are two paths marked
`[AI-SERVICE]`, and both files are excluded from ruff so `cp` stays a clean
re-sync.

The **weights are not copied**. The adapter is 195 MB and is already tracked
under `backend/pipeline-one/models/`, so `LORA_ADAPTER_DIR` points at it.

`session_store.py` is deliberately not vendored — review sessions are rows in
Postgres here, because a process-local dict listed nothing after a restart and
was invisible to a second worker.

This is the one place in the repository where the same code exists twice, and
it is a deliberate trade: `ai-service` must be deployable without a
`pipeline-one` checkout on disk, and a cross-directory import of a hyphenated,
non-package directory is worse than a copy with a stated re-sync rule.

---

**Next:** [02 · Backend Architecture — `api-service`](02_BACKEND_ARCHITECTURE.md)
