# ai-service

**Phase 1 extraction, the vector embedding DB, and search over it.**

Raw CPSE catalogue text goes in; standardized material rows come out and land
in a vector index, with anything already there rejected at the door. A query -
a code, a name, a spec, a sentence - comes back as the existing materials it
refers to, ranked and labelled.

```
                 Raw CSV / XLSX / TXT
                          │
                          ▼
              ┌───────────────────────┐
              │  PHASE 1              │   POST /extract/csv
              │  Qwen2.5-3B           │   POST /extract/text
              │  + qwen2.5-3b-        │
              │    cpse-lora-v2       │   vendored from pipeline-one
              └───────────┬───────────┘   runs as a pollable job
                          │
                          ▼
                  Standard Format
              (8 canonical CPSE attributes)
                          │
                          ▼
              ┌───────────────────────┐
              │  THE BOUNDARY         │   POST /standardized/check
              │  Is this row already  │
              │  in the vector DB?    │
              └───────────┬───────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
       Already available         New material
              │                       │
              ▼                       ▼
           ignored          POST /standardized/add
                                      │
                                      ▼
                        Postgres + Qdrant, one transaction
```

Search over that index is `POST /search` — see [Search](#search) below.

**Full API:** [API_SPECIFICATION.md](API_SPECIFICATION.md) — 24 endpoints.

---

## The eight canonical CPSE attributes

The standard format, and the contract between the two halves of this service.

| Attribute | Example | In the vector? |
| :--- | :--- | :--- |
| Company | `Coal India (BCCL)`, `ONGC` | no — see below |
| Item Description (Raw) | `BALL VALVE 1 INCH SS316 1000 WOG PTFE SEAT` | **yes** |
| Item Code / Legacy Ref | `BHEL-868460` | no |
| Quantity | `13751` | no |
| UOM | `NOS`, `MTR`, `KGS`, `SET` | **yes** |
| Part Number / OEM Number | `PN-2409-B` | **yes** |
| Make / Brand | `SKF`, `FLEETGUARD` | **yes** |
| Specifications / Dimensions | `Dim: 238mm, Mat: Rubber` | **yes** |

All eight are stored. Only five are embedded, and the three that are not are
the point of the whole design:

- **Company** — finding the same article in *another CPSE's* master is what
  this system exists to do. Put the company name in the vector and NTPC's
  bearing and BHEL's identical bearing embed differently, so they never
  surface as duplicates.
- **Item Code / Legacy Ref** — a CPSE's own internal code. Two CPSEs holding
  the same physical part have different codes by definition, and a CPSE
  re-coding its master would make every row look new.
- **Quantity** — stock level, not identity. Five of a bearing and five
  thousand of it are the same bearing.

None of it is lost: `Company` and the legacy code are what `material_id` is
built from, and `cpse_code` travels in the vector payload.

### The ninth value: `category`

Derived from the description by a 25-rule keyword table
([logic/category.py](app/logic/category.py)) — `BEARING`, `VALVE`, `FILTER`, …
or `UNCLASSIFIED`. 100% coverage on the reference corpus.

It is a **filter and an optional blocking key, not an attribute**. It is
deliberately absent from the embedded text, so a keyword rule can never move a
vector — and so adding it changed no stored `canonical_hash`, which matters
because there is no reindex endpoint to repair one.

---

## Quick start

```bash
make install-ai          # or: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
make dev-ai              # http://localhost:8001/docs
```

That runs the **vector half only**: no model weights, no torch, no download.
`/extract/*` answers 503 and says exactly why. That is the shipped default and
every test passes in it — but with `EXTRACTION_ENABLED=false` there is no way
to put material in, because Phase 1 is the only entry point.

> **Port check.** `ai-service` is 8001, `api-service` is 8000. Running
> `api-service` on 8001 gives 404 on every route here — its only paths are
> `/api/v1/ai/infer`, `/api/v1/users` and `/health`.

### Turning Phase 1 on

```bash
make install-ml          # torch, transformers, peft, accelerate, bitsandbytes
```

```ini
EXTRACTION_ENABLED=true
LORA_ADAPTER_DIR=../pipeline-one/models/qwen2.5-3b-cpse-lora-v2
```

The weights are **not** copied into this service. They are 195 MB and are
already tracked under `backend/pipeline-one/models/`, so the config points at
them. If that checkout is not present, download
`qwen2.5-3b-cpse-lora-v2.zip` from the
[GitHub release](https://github.com/SangikGhosh/sih-2026/releases/tag/finetunned_model)
and unzip it wherever `LORA_ADAPTER_DIR` points.

`GET /api/v1/extract/info` always reports the live state — mode, adapter path,
whether the weights are actually on disk, and which device they loaded on. A
demo can never claim fine-tuned extraction it is not doing.

Loading is **lazy**: the adapter is constructed on the first extraction, not at
startup, so the service still boots in a second and a machine with no GPU fails
the one request that needs one rather than failing to start.

---

## The flow, end to end

There is **one way in**, and this is it. No seed loader, no direct-import
endpoint, no reindex: every material in the master arrived through Phase 1 and
was admitted by the check.

```bash
# 1. Raw file -> standard format. Returns a job id immediately; writes nothing.
curl -F 'file=@catalogue.xlsx' -F 'max_rows=100' \
     localhost:8001/api/v1/extract/csv
#    -> 202 {"id": "abc123", "params": {"total_rows": 500}, ...}

# 2. Poll every 1-2s while the model works.
curl localhost:8001/api/v1/extract/jobs/abc123
#    -> {"status": "processing", "processed_rows": 320, "total_rows": 500,
#        "session_id": "sess_123"}
#    -> {"status": "completed",  "processed_rows": 500, "total_rows": 500,
#        "result": { ... }}

# 3. Correct whatever the model got wrong. `predicted` is kept alongside.
curl -X PUT localhost:8001/api/v1/extract/records/sess_123/rec_0004 \
     -H 'Content-Type: application/json' \
     -d '{"Make / Brand": "SKF"}'

# 4. Ask the boundary which rows are new. Still writes nothing.
curl -X POST localhost:8001/api/v1/standardized/check \
     -H 'Content-Type: application/json' \
     -d '{"session_id": "sess_123"}'
#    -> {"has_new_data": true, "new_rows": 2, "existing_rows": 8,
#        "new_material": [ ... only the 2 ... ], "batch_id": "8f3c"}

# 5. Index exactly those two.
curl -X POST localhost:8001/api/v1/standardized/add \
     -H 'Content-Type: application/json' \
     -d '{"batch_id": "8f3c"}'
```

Step 4 takes the rows three ways and they all end in the same check — which is
why there is no separate "forward" endpoint: looking a session up and calling
the check *is* the check.

```jsonc
{"session_id": "sess_123"}   // a reviewed extraction session
{"rows":    [ ... ]}         // the rows directly
{"records": [ ... ]}         // pipeline-one's forwarder envelope, verbatim
```

So a `pipeline-one` server running elsewhere points `NEXT_PIPELINE_URL` at
`POST /api/v1/standardized/check` and needs no adapter in between.

### When nothing is new

That is an **answer**, not an error:

```json
{
  "has_new_data": false,
  "new_rows": 0,
  "existing_rows": 10,
  "new_material": [],
  "message": "No new data. All 10 row(s) are already available in the vector embedding DB."
}
```

---

## How "already exists" is decided

[app/logic/existence.py](app/logic/existence.py), in this order. The order is
the design.

| # | Signal | Model-independent? |
| :-- | :--- | :--- |
| 1 | Same `material_id` — same CPSE, same legacy code | yes |
| 2 | Same `canonical_hash` — the embedded text is byte-identical | yes |
| 3 | An earlier row of *this same payload* has that hash | yes |
| 4 | Nearest vector at or above `EXISTENCE_THRESHOLD` (0.90) | no |

The three exact signals come first precisely because they cannot be wrong. Only
signal 4 can, so it carries its score and its neighbour's id into the response
and a human can see why a row was held back.

If the vector store is unreachable, signals 1–3 still decide and the response
says the check ran degraded. A check that refuses to answer because Qdrant is
down is worse than one that answers with less evidence and admits it.

**This is not a matcher.** It answers one question — is this row worth
embedding — and nothing else.

---

## Search

`POST /api/v1/search` takes **any** description of a material and returns the
existing materials it refers to. There is no fixed set of fields:

```jsonc
{"query": "M-55321"}                                            // a code
{"query": "V BELT"}                                             // a name
{"query": "V BELT C 120"}                                       // name + parameters
{"query": "industrial V belt C section approximately 1200 mm"}  // a sentence
{"query": "V belt C 120 length 1200 mm NTPC M-55321"}           // all of it
{"query": "V BELT C 120", "top_k": 20, "final_k": 5}            // the knobs
```

### Two stages of retrieval, one stage of judgement

```
                       query
                         │
                         ▼
               logic/query.prepare        upper-case, collapse, the same abbreviation
                         │                table Phase 1 applies; numbers, units and
                         │                codes untouched; identifier tokens pulled out
             ┌───────────┴───────────┐
             ▼                       ▼
      exact lookup             Qwen3 query vector
      Postgres: national id,         │
      material id, legacy code,      ▼
      part number              vector store  ──►  top-K candidates     (SEARCH_TOP_K)
             │                       │
             └───────────┬───────────┘
                         ▼
                  candidate pool ──► rows from Postgres
                         │
                         ▼
         ┌───────────────────────────────┐
         │        SIAMESE RERANKER       │   (query, candidate) x K, ONE batch
         │  query ──► shared encoder ──► A │
         │  cand  ──► SAME WEIGHTS   ──► B │   score = cosine(A, B)
         └───────────────┬───────────────┘
                         ▼
       final_score = 0.3 x qdrant + 0.7 x siamese       (SEARCH_QDRANT_WEIGHT / _SIAMESE_WEIGHT)
                         ▼
       high / possible / none                          (SEARCH_MATCH_THRESHOLD / _POSSIBLE_THRESHOLD)
                         ▼
                   final_k results                      (SEARCH_FINAL_K)
```

**A code is looked up, not embedded.** `M-55321`, `224411`, `NTPC-M-55321`,
`NMM-00000042` are matched exactly against the master — the legacy code and
part number live only in Postgres, not in the Qdrant payload — under every
spelling `material_id` might have been built with. An exact hit is a `high`
match whatever the models say, and a query that was *nothing but* identifiers
skips the vector stage when they are found. A bare `6205` or `120` is a
parameter, not a code, and is never looked up: a coincidental legacy code
would otherwise turn an unrelated row into an exact match.

**The reranker only ever sees the K candidates.** Never the corpus. Twenty
pairs are one forward pass — ~15 ms on a CPU.

### The two models, kept apart

| | Retrieval | Reranking |
| :--- | :--- | :--- |
| Model | `Qwen3-Embedding-0.6B`, 0.6 B params | `all-MiniLM-L6-v2` + projection head, 23 M params |
| Trained here? | no — pretrained, never touched | yes — fine-tuned on labelled CPSE pairs |
| Sees | the whole index | the top-K pool |
| Good at | finding the family | `C-120` vs `C-125` inside it |
| Output | `qdrant_score` | `siamese_score` |

Introducing the reranker changed nothing about how materials are embedded or
stored. The Qdrant vectors, `canonical_hash`, the existence check and the
ingestion path are exactly as they were.

### Why the weights lean on the Siamese score

Both scores are cosines, so they share a scale, but they are not calibrated
against each other. On the reference corpus the Qwen3 cosine puts a true
match at ~0.68 and a **near-miss article** (`V BELT C 125` against the C-120
belts) at ~0.70 — it cannot tell them apart. The trained Siamese score puts
the same two at ~0.95 and ~0.3. So `final_score` weights the Siamese score
0.7 and the retrieval score 0.3: enough retrieval signal to keep the family
ordering stable, enough Siamese signal for the number that decides.

### The match decision is three-way

| `match_level` | Means | `match` |
| :--- | :--- | :--- |
| `high` | `final_score >= SEARCH_MATCH_THRESHOLD` (or an exact identifier hit) | `true` |
| `possible` | `>= SEARCH_POSSIBLE_THRESHOLD` — shown, a reviewer decides | `false` |
| `none` | below both — returned so the caller sees what the nearest thing was | `false` |

**Without the reranker no result can be `high`.** If there is no trained
checkpoint at `SIAMESE_MODEL_PATH`, torch is not installed, or the model
fails on a query, the search still answers — ordered by the Qdrant score,
`siamese_score: null`, `pipeline.reranker_applied: false` with the reason —
but the best it will claim is `possible`. A general-purpose embedding has not
earned more on this domain, and a demo without the trained stage must not
look like one with it. `GET /search/model/info` reports which state is live.

### Training the reranker

Training and inference are separate. Nothing a request does trains anything.

```bash
make install-ml                          # torch + transformers, once
.venv/bin/python scripts/train_siamese.py \
    --corpus ../pipeline-one/CPSE_SIH26099.csv \
    --pairs  data/training/seed_pairs.csv \
    --output data/models/siamese-cpse-v1   # ~1 min on a GPU, ~10 min on a CPU
```

```
labelled pairs ──► Dataset ──► DataLoader ──► shared encoder ──► A, B
                                                   │
                        contrastive loss on ||A − B||  (Hadsell, margin 1.0)
                                                   │
                                   backward ──► AdamW ──► weights
                                                   │
             validation each epoch: pair scores ──► best-F1 threshold ──► P / R / F1
                                                   │
                                     best epoch ──► config.json + backbone/ + head.pt
```

Pairs come from two places. `data/training/seed_pairs.csv` is hand-written —
`query_material,candidate_material,label` with `1` = same article, `0` =
different, and an optional `relation` column (`SAME_ARTICLE`,
`NEAR_DUPLICATE`, `DIFFERENT_NUMBER`, ...) carried through so the format does
not change when the labels get finer. `--corpus` generates the rest from a
standard-format CSV: rows describing the same article are positives, plus the
spellings people actually type (`C-120` / `C120` / `C 120`, `BRG` for
`BEARING`, a dropped word, a swapped order, a sentence around the name); the
negatives that matter are the **number- and letter-perturbed twins** — `6205`
against `6206`, `6305`, `C 120` against `B 120` — because that is exactly what
the retrieval embedding cannot see. A quarter of the *articles* are held out
of training entirely, so validation measures materials the model never saw.

Every knob is a flag: `--epochs --batch-size --lr --margin --holdout
--freeze-backbone --device`. The checkpoint records the threshold it
calibrated and the metrics it reached; `GET /search/model/info` shows them.

### Does the Siamese stage help? Measured, not assumed

`scripts/evaluate_search.py` embeds the reference corpus with the live
provider into the exact in-memory store, runs every query in
`data/evaluation/search_queries.csv` through the same top-20 pool three ways,
and compares. 71 queries: the examples from the brief, abbreviations,
paraphrases, three unrelated queries, and **twenty near-miss articles** that
do not exist in the corpus (`V BELT C 125`, `BALL BEARING 6206`,
`GATE VALVE 3 INCH 800#`, ...). Numbers below are from
`EMBEDDING_PROVIDER=qwen3`, checkpoint `siamese-cpse-v1`, weights 0.3 / 0.7.

| | hit@1 | MRR | match P | match R | match F1 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Qdrant only (threshold calibrated to its own best, 0.58) | 1.00 | 1.00 | 0.70 | 0.95 | **0.81** |
| Qdrant + Siamese (threshold 0.75) | 1.00 | 1.00 | 0.95 | 0.92 | **0.94** |
| Siamese only (threshold 0.81) | 1.00 | 1.00 | 0.94 | 0.92 | 0.93 |
| Qdrant + Siamese, held-out articles only (10 queries) | 1.00 | 1.00 | 1.00 | 0.92 | 0.96 |
| Qdrant only (threshold calibrated to its own best, 0.59) | 1.00 | 1.00 | 0.70 | 0.94 | **0.80** |
| Qdrant + Siamese (threshold 0.75) | 1.00 | 1.00 | 0.91 | 0.89 | **0.903** |
| Qdrant + Siamese (calibrated threshold 0.72) | 1.00 | 1.00 | 0.90 | 0.92 | **0.911** |
| Siamese only (threshold 0.77) | 0.98 | 0.99 | 0.90 | 0.92 | 0.91 |
| Qdrant + Siamese, held-out articles only (10 queries, thr 0.75) | 1.00 | 1.00 | 1.00 | 0.72 | 0.84 |

Stated plainly:

- **Ranking did not improve, because it could not.** On this corpus — 404
  rows, 34 articles, mostly synthetic repeats — Qwen3 alone already puts a
  relevant row first for every query. The reranker keeps that (hit@1 1.00)
  and does not break it.
  relevant row first for every query (hit@1 1.00, MRR 1.00). The fused stage
  preserves this top-1 retrieval performance while outperforming Siamese-only
  (which drops to hit@1 0.9792).
- **The match decision improved substantially.** The retrieval cosine cannot
  separate a true match from a near-miss article, so a threshold that keeps
  recall admits near-misses: precision 0.70. The Siamese score can: precision
  0.95 at the same recall. Of the 20 near-miss queries, 15 come back `none`,
  5 `possible`, and 3 still slip through as `high` (`M20` for `M24`, `100W`
  for `200W`, `0-10` for `0-100`). Of the three unrelated queries, none is a
  match at any level.
  0.91 at the same recall. Of the 20 near-miss queries, `V BELT C 125` against
  C-120 achieves a final score of 0.7449 (< 0.75) and correctly returns
  `possible` rather than `high`. At threshold 0.75, only 5 near-miss queries
  cross into `high` (e.g. `BALL BEARING 6305 2RS`, `TAPER ROLLER BEARING 32219`),
  and at threshold 0.80 this drops to just 2/20 (10%). All three unrelated queries
  return `none`.
- **The corpus is small and the model is young.** 34 articles is not a
  material master. Retrain on real pairs — a reviewer's accepted and rejected
  suggestions are exactly the training format — and recalibrate. Both
  thresholds are settings because they belong to the (model, weights) pair
  they were measured on.

### Reindexing

To populate or refresh Qdrant Cloud / local index with Qwen3 embeddings:

```bash
# Dry run: checks count, dimensions, refusal if fallback provider
.venv/bin/python scripts/reindex.py

# Apply: computes embeddings, overwrites deterministic point IDs in Qdrant, updates Postgres
.venv/bin/python scripts/reindex.py --apply
```

### Response Schema & Inspection

The response includes rich provenance for each candidate and stage:
- **Per hit**: `match_source` (`exact_identifier`, `siamese`, `retrieval_only`, `none`), `identifier_match` (boolean), `identifier_match_type` (`exact`), `identifier_matched_field` (`national_id`, `material_id`, `legacy_code`, `part_number`), `identifier_token`.
- **Pipeline info**: `embedding_model`, `embedding_version`, `embedding_is_fallback`, `embedding_error`, `vector_store`, `store_error`, `top_k`, `final_k`, `reranker_applied`, `reranker_model`, `reranker_detail`, `degraded`, `warnings`.

```bash
EMBEDDING_PROVIDER=qwen3 .venv/bin/python scripts/evaluate_search.py \
    --corpus ../pipeline-one/CPSE_SIH26099.csv --calibrate
```

`--calibrate` prints the threshold that maximises match F1 for the configured
weights — that is where `SEARCH_MATCH_THRESHOLD` comes from. With
`EMBEDDING_PROVIDER=deterministic` the report says at the top that its
retrieval numbers are noise.

---

## Guarantees

- **`check` writes nothing.** A caller sees what would change before it does.
- **`add` cannot create a duplicate.** It takes a `batch_id`, so the rows
  written are the rows *this service* judged new, and it re-checks them anyway:
  a batch is a snapshot, and someone else may have indexed the same article in
  between.
- **A batch is added once.** A replay is a 409, not a second copy.
- **The master and the index are written together or not at all.** `add`
  upserts the vectors *inside* its transaction, so a store that cannot be
  written fails the whole call with a 503 and adds nothing. There is no rebuild
  endpoint, and that is exactly why: a row in the master without a vector could
  never be embedded, and every later check would keep calling it new.
- **A long extraction never blocks the request.** `/extract/csv` and
  `/extract/text` return a job id and run in the background; rows land in the
  session as they are produced, so progress is both visible and durable, and a
  run that dies at row 217 keeps those 217. `?wait=` restores the old inline
  behaviour for a caller that would rather block.
- **Nothing is silently dropped.** An unreadable row comes back as `INVALID`
  with its row number and the reason. A row that vanishes without a trace is
  indistinguishable from one that was never sent.
- **Nothing claims to be what it is not.** `GET /extract/info`,
  `GET /retrieval/model/info` and `GET /search/model/info` report the live
  model state, so a demo can never claim fine-tuned extraction, Qwen3-quality
  vectors or Siamese-reranked matches it is not producing. A search without
  the reranker says so in every response and never returns a `high` match.
- **Search never trains.** The reranker is loaded on first use from a
  checkpoint `scripts/train_siamese.py` wrote; a request cannot change it.

---

## Layout

```
app/
  logic/                  algorithms — no HTTP, no database
    extraction.py         VENDORED from pipeline-one/inference_engine.py
    standard_format.py    the 8-attribute contract and its alias table
    standardize.py        a standard row -> the record we store
    category.py           the material family: a filter and a blocking key
    existence.py          is this row already in the vector DB?
    embedding.py          what gets embedded, and the providers
    retrieval.py          the vector store (Qdrant / in-memory)
    identity.py           material_id
    query.py              a search query: preprocessing, identifier tokens
    siamese.py            the Siamese reranker: shared encoder, loss, save/load
    ranking.py            score fusion and the three-way match decision
  services/               business logic — talks to models, calls logic
    extraction.py         the LoRA lifecycle + the background extraction job
    sessions.py           review sessions, in Postgres
    taxonomy.py           the abbreviation table, in Postgres
    standardized.py       the boundary: check, then add
    materials.py          the master
    indexing.py           building a vector, and index state
    search.py             identifiers + vectors -> pool -> rerank -> results
    reranker.py           the Siamese model's lifecycle; candidate text
    jobs.py               the in-process job runner
  training/               never imported by a request
    pairs.py              labelled pairs: read, generate, split by article
    train_siamese.py      the training loop
    evaluate.py           Qdrant-only vs Qdrant + Siamese
  routes/                 HTTP only: read request, call service, return
  schemas/                request/response models
  models/                 seven tables (below)
scripts/
  train_siamese.py        -> data/models/<checkpoint>   (gitignored)
  evaluate_search.py      -> data/evaluation/report.json
data/
  training/seed_pairs.csv        hand-labelled pairs
  evaluation/search_queries.csv  queries -> the article(s) they should find
```

### The schema

| Table | Holds |
| :--- | :--- |
| `extraction_session` | one Phase 1 run: source, adapter, status, job |
| `extraction_record` | one row per record — `predicted` beside `current` |
| `abbreviation` | CPSE taxonomy added at runtime, and who added it |
| `standardization_batch` | what was offered, what was admitted, and why |
| `material` | one standard-format row + its vector state |
| `audit_log` | what changed the master, and who said so |
| `job` | background work that outlives its request |

The first three are Phase 1 working state; nothing in them is part of the
master until `POST /standardized/add` accepts it.

**Postgres is the record. Qdrant is a derived index over five of the eight
attributes.** Not a staging area — `Quantity`, `Item Code / Legacy Ref` and the
company name exist nowhere else.

### The vendored files

`logic/extraction.py` is a copy of pipeline-one's `inference_engine.py`, and
the `/extract` API surface — including `row_to_composite_text` — is a copy of
its `app.py`. Copies, not forks; behaviour must stay identical.

**Re-sync rule:** if the pipeline-one file changes, copy it over again and
re-apply the local edits, which are marked `[AI-SERVICE]` and are only paths.
Both vendored files are excluded from ruff for the same reason.

`session_store.py` is deliberately **not** vendored. Its storage — a
process-local dict whose `list_sessions()` never read the disk fallback — is
right for a single-process Review Studio and wrong for a service with a
database and more than one worker: the listing came back empty after every
restart, and a session created on one worker was invisible to the other. The
*API shape* is unchanged, so a client reads the same JSON; only the storage is
this service's.

The same reasoning moved the runtime abbreviation taxonomy into a table.
`expand_abbreviations` stays vendored — that is the algorithm — but an addition
is a row, not a CSV append to a module-level dict only one worker could see.

`row_to_composite_text` is why there is no column inference anywhere in this
service: rather than guessing which column holds a description, every populated
cell of a row is written as `Header: value` and the model reads the lot. A
vendor export with columns nobody has seen before degrades into a longer
sentence, not into a rejected file.

---

## Configuration

Everything is in [.env.example](.env.example), commented. The ones that matter:

| Setting | Default | Why |
| :--- | :--- | :--- |
| `EXTRACTION_ENABLED` | `false` | Phase 1 needs several GB of wheels and a GPU. Off, the vector half runs alone and says so. |
| `EMBEDDING_PROVIDER` | `deterministic` | Seeded hash — stable vectors, **no semantic signal**. `qwen3` is the real model. |
| `VECTOR_STORE` | `memory` | Dies with the process while Postgres keeps the rows, and nothing can reconcile them. Use `qdrant` for data you intend to keep. |
| `EXISTENCE_THRESHOLD` | `0.90` | The one tunable that decides what enters the master. Too low drops new material; too high fills the index with re-uploads. |
| `EXISTENCE_BLOCK_BY_CATEGORY` | `false` | Blocking is faster but a misclassified row is never compared against its own duplicate. Turn on when the table has earned trust on your data. |
| `BATCH_RETENTION_DAYS` | `7` | How long a check nobody acted on is kept. `ADDED` batches are never pruned. |
| `SEARCH_TOP_K` / `SEARCH_FINAL_K` | `20` / `5` | Candidates the reranker scores; results returned. |
| `SIAMESE_MODEL_PATH` | `data/models/siamese-cpse-v1` | The trained reranker. Absent → search answers without it and says so. |
| `SEARCH_QDRANT_WEIGHT` / `SEARCH_SIAMESE_WEIGHT` | `0.3` / `0.7` | `final_score` split. Sum to 1. |
| `SEARCH_MATCH_THRESHOLD` / `SEARCH_POSSIBLE_THRESHOLD` | `0.75` / `0.55` | `high` / `possible` on `final_score`. Calibrated on the reference corpus; recalibrate after a retrain. |

---

## Tests

```bash
make test-ai             # 226 tests (+10 Qdrant integration and 6 Siamese, opt-in)
```

Hermetic by default: in-memory vector store, seeded-hash embeddings, no model
weights. The search tests install a token-overlap stand-in for the reranker,
so the pipeline — identifiers, reranking, fusion, the match levels, every
degradation path — is exercised without torch; `tests/test_siamese.py` covers
the real model and skips unless torch and the cached backbone are present. That is the configuration a fresh checkout actually runs, so the suite
exercises it rather than a setup nobody has. Everything else is real —
sessions, records, the taxonomy, batches and materials are all rows in a
per-test SQLite database.

`tests/test_qdrant_integration.py` is opt-in — set `QDRANT_TEST_URL` — so the
dependency is chosen rather than inherited.

---

## Known limits

Stated plainly, because none of them is hidden by the code:

1. **Jobs live in this process.** Two workers do not share a queue, and a
   restart marks in-flight work `FAILED` rather than leaving a caller polling a
   task that no longer exists. Every job kind is safe to resubmit. Moving to
   Celery or RQ means replacing `_spawn` and leaving the Job row, the routes
   and the polling contract exactly as they are.
2. **There is no reindex.** A vector store restored from an old snapshot cannot
   be reconciled — only delete-and-re-offer, row by row.
3. **`DELETE /materials/{id}` is permanent.** No soft delete; it is the only
   irreversible operation here.
4. **The reranker was trained on 34 articles.** Enough to show the stage
   works and to calibrate it honestly (see [Search](#search)); not a material
   master. Three of twenty near-miss queries still come back `high`. Retrain
   on reviewed pairs and recalibrate before trusting `match: true` unattended.
5. **Search does not use the blocking keys yet.** `category` and
   `uom_dimension` are in the payload and indexed; the query is not classified
   into a family, so every search traverses the whole index. That is sublinear
   and fine at this size; a `category` filter on the request is the obvious
   next step and needs no reindex.

---

## Authentication

There is none, and there is no user model: no roles, no caller identity, no
headers read to decide anything. `api-service` owns all of that.

`requested_by` / `actor` are free-text labels recorded on the audit trail.
Unverified — a label, never an authorisation.

**The security boundary is the network. Do not route port 8001 publicly.**
