# ai-service — API Specification

Base URL `http://localhost:8001` · prefix `/api/v1` · OpenAPI at `/docs`
**24 endpoints.**

**No authentication.** This service has no user model: no roles, no caller
identity, no headers read to decide anything. `api-service` owns all of that,
and every endpoint answers a completely empty request. `requested_by` / `actor`
fields are free-text labels recorded on the audit trail — never an
authorisation. **The security boundary is the network.**

---

## 1 · The shape of the service

```
             Raw CSV / XLSX / TXT
                      │
                      ▼
        ┌──────────────────────────────┐
        │  PHASE 1        /extract/*   │   Qwen2.5-3B + qwen2.5-3b-cpse-lora-v2
        │  background job, pollable    │   vendored from backend/pipeline-one
        └──────────────┬───────────────┘
                       ▼
              Standard Format  ·  8 canonical CPSE attributes
                       ▼
        ┌──────────────────────────────┐
        │  BOUNDARY  /standardized/*   │   is this row already indexed?
        └──────────────┬───────────────┘
              ┌────────┴────────┐
       already there          new material
              │                  │
           ignored               ▼
                       Postgres + Qdrant, one transaction
```

| Prefix | Stage | Writes the master? |
| :--- | :--- | :--- |
| `/extract` | Phase 1: raw text or a raw file → standard format | no |
| `/standardized` | the boundary: what is new → add it | `add` only |
| `/materials` | the master, read side (+ delete) | delete only |
| `/retrieval` | the state of the vector index | no — read-only |
| `/search` | a query → the index → the Siamese reranker → matches | no — read-only |
| `/jobs` | background work | no |

**Material enters the master in exactly one place: `POST /standardized/add`.**
There is no seed loader, no direct import and no reindex.

### The eight canonical attributes

`Company` · `Item Description (Raw)` · `Item Code / Legacy Ref` · `Quantity` ·
`UOM` · `Part Number / OEM Number` · `Make / Brand` ·
`Specifications / Dimensions`

All eight are stored. **Five are embedded.** `Company`, `Item Code / Legacy Ref`
and `Quantity` are excluded from the vector on purpose: finding the same article
in *another CPSE's* master is the point of the system, and two CPSEs holding one
physical part have different company names, different internal codes and
different stock levels. Put those in the vector and the duplicate never
surfaces.

A ninth value, `category`, is derived from the description (`BEARING`, `VALVE`,
`FILTER`, … or `UNCLASSIFIED`). It is a filter and an optional blocking key —
**not** an attribute, and never in the embedded text.

### Background jobs

`/extract/text`, `/extract/csv`, `/standardized/check` and `/standardized/add`
do work bounded by the size of the input rather than by an HTTP timeout, so
they run as jobs:

| Response | Meaning |
| :--- | :--- |
| `200` + the payload | finished within `?wait=` seconds. `X-Job-Id` header carries the id. |
| `202` + `JobOut` | still running. Poll the `Location` URL until `terminal` is true; the payload is then in `result`. |
| `4xx` / `5xx` | failed, **with the status it would have had synchronously** — a bad request stays a 400, it does not become an opaque 500. |

`?wait=` (0–`JOB_MAX_WAIT_SECONDS`) lets one endpoint serve both kinds of
caller. An interactive client passes a few seconds and usually gets its answer;
a batch client passes nothing, gets an id immediately, and polls.

---

# 2 · Extraction (Phase 1)

Vendored from `pipeline-one`. Runs a fine-tuned Qwen2.5-3B with the
`qwen2.5-3b-cpse-lora-v2` adapter in 4-bit NF4 (~2.0 GB VRAM), falling back to
multi-threaded CPU bfloat16.

**Off by default.** With `EXTRACTION_ENABLED=false` every endpoint that touches
the model answers `503` naming the setting and pointing at
`POST /standardized/check` as the alternative. Weights load lazily on first
use, so the service boots in a second either way.

## `GET /extract/info`

What Phase 1 this deployment is actually running.

```json
{
  "enabled": false,
  "loaded": false,
  "adapter": "qwen2.5-3b-cpse-lora-v2",
  "adapter_dir": "/srv/../pipeline-one/models/qwen2.5-3b-cpse-lora-v2",
  "adapter_present": true,
  "base_model": "Qwen/Qwen2.5-3B-Instruct",
  "max_new_tokens": 256,
  "canonical_fields": ["Company", "Item Description (Raw)", "..."],
  "vendored_from": "backend/pipeline-one/inference_engine.py",
  "sessions": 2,
  "abbreviations_learned": 7
}
```

Once loaded it also carries `device`, `device_name`, `vram_gb`. It never lies:
a demo cannot claim fine-tuned extraction while running with the flag off.

## `POST /extract/csv`

`multipart/form-data`. **Where a real CPSE catalogue enters**, and the longest
operation in the service — a 3B model doing generative extraction is minutes
for a few hundred rows. Runs as a **background job**.

```
POST /extract/csv         -> 202 {"id": "<job_id>", "params": {"total_rows": 500}}
GET  /extract/jobs/{id}   -> processed_rows / total_rows      (poll every 1-2s)
GET  /extract/jobs/{id}   -> status "completed", `result` is the body below
```

| Field | Default | |
| :--- | :--- | :--- |
| `file` | — | CSV, XLSX or XLS |
| `text_column` | — | Name a column explicitly. Omit it and see below. |
| `max_rows` | `100` | A 3B model: a thousand rows is minutes of GPU time. |
| `?wait=` | `0` | Block inline and return the finished body directly. |

**No column inference.** If `text_column` is omitted and the file has more than
one column, every populated cell of each row is folded into one string —
`description. Header: value. Header: value.` — and the model reads the lot. A
vendor export with columns nobody has seen before becomes a longer sentence,
not a rejected file.

The file is read and parsed **in the request**: that is what makes `total_rows`
known immediately, and it keeps an unparseable file a `400` on upload rather
than a job that fails a second later.

Rows are extracted in chunks of five — a multiple of five because the engine
clears the CUDA cache every fifth record — and each chunk is committed to the
session as it finishes. So `GET /extract/sessions/{session_id}` returns the
first 200 rows of a 500-row file without waiting for the other 300.

Completed `result`:

```json
{
  "session_id": "sess_1757...",
  "source_file": "catalogue.xlsx",
  "text_column_used": "Composite Whole Row (6 columns)",
  "total_records": 100,
  "records": [ "..." ],
  "next_step": "Correct any wrong cells with PUT /extract/records/... then POST /standardized/check with {\"session_id\": \"...\"}"
}
```

## `POST /extract/text`

One un-delimited ERP string → the eight canonical attributes. Also a job
(`total_rows: 1`); `?wait=` for the inline body.

```json
{ "text": "HEC BALL VALVE 1_INCH SS316 1000 WOG PTFESEAT BHEL-868460 6219 NOS CAT-438 AUDCO Dim: 226MM" }
```

```json
{
  "session_id": "sess_1757...",
  "record": {
    "record_id": "rec_0001",
    "row_index": 1,
    "raw_input": "HEC BALL VALVE 1_INCH ...",
    "predicted": { "Company": "HEC", "Item Description (Raw)": "BALL VALVE 1 INCH STAINLESS STEEL 316 ...", "...": "..." },
    "current":   { "...": "..." },
    "is_modified": false,
    "status": "pending_review"
  }
}
```

`400` if the text is blank. `503` if extraction is disabled — and that stays a
`503` through the job, rather than becoming an opaque 500.

## `GET /extract/jobs/{job_id}`

Progress of a background extraction, shaped for a client polling every 1–2s.

```json
{ "job_id": "abc123", "status": "processing", "processed_rows": 320, "total_rows": 500,
  "session_id": "sess_1757...", "source_file": "catalogue.xlsx" }
```

```json
{ "job_id": "abc123", "status": "completed", "processed_rows": 500, "total_rows": 500,
  "session_id": "sess_1757...", "result": { "...the body above, verbatim..." } }
```

```json
{ "job_id": "abc123", "status": "failed", "processed_rows": 217, "total_rows": 500,
  "error": "Extraction failed because ...", "error_status": 503 }
```

| Field | |
| :--- | :--- |
| `status` | `processing` · `completed` · `failed` · `cancelled` |
| `processed_rows` / `total_rows` | render `processed_rows / total_rows` |
| `session_id` | present as soon as the job opens its session — **before any row is done** |
| `result` | present once `completed`, and it **stays**: a client that polls late, or reloads, still gets the finished body |
| `error` / `error_status` | on failure. Rows already extracted are kept; the session is `FAILED` |

`404` if the job is unknown, or if it is not an extraction job — the shape is
row-based, so pointing it at a `STANDARDIZED_CHECK` would be a lie. The generic
`GET /jobs/{job_id}` reports the same job in the service's standard shape.

## `GET /extract/sessions` · `GET /extract/sessions/{session_id}`

List sessions (newest first, `?limit=`), or fetch one with every record —
prediction and correction side by side. `404` on an unknown id.

Sessions and records are rows in Postgres, so they survive a restart and read
the same on every worker.

| `status` | |
| :--- | :--- |
| `PROCESSING` | the job is still extracting into it |
| `PENDING_REVIEW` | extracted, nobody has touched it |
| `REVIEWED` | at least one record was corrected |
| `CHECKED` | offered to `POST /standardized/check` |
| `FAILED` | extraction stopped part way; the rows it managed are kept |

Never "confirmed": whether the rows were actually *added* is a property of the
batch, not of the session.

## `PUT /extract/records/{session_id}/{record_id}`

Correct one record. Accepts canonical names and snake_case alike.

```json
{ "Make / Brand": "SKF", "quantity": 6219 }
```

Sets `is_modified` and `status: "reviewed"`, leaves `predicted` untouched —
which is what makes a session usable later as training signal rather than only
as a fix. A single-row `UPDATE`, so two reviewers on the same 100-record
session cannot overwrite each other. Clearing a cell stores `"NA"`, the way the
engine writes an ungrounded attribute. `404` if the session or record is
unknown.

## `POST /extract/taxonomy/abbreviations`

Teach the CPSE taxonomy a new abbreviation without retraining.

```json
{ "raw": "VLV", "expansion": "VALVE", "scope": "", "actor": "materials-eng" }
```

Stored in Postgres and applied to this worker's live registry immediately;
every other worker picks it up at startup. Re-registering an existing `raw`
**updates** it — correcting a wrong mapping is the common case. Written to the
audit trail with `actor`. `400` on an empty pair.

The taxonomy has three layers, applied in order: the curated defaults in
`logic/extraction.py`, the shipped `data/config/abbreviations.csv`, and this
table on top.

## `GET /extract/taxonomy/abbreviations`

Everything added at runtime, with `created_by` and timestamps. `?limit=` 500.
**Not** the whole taxonomy — the two baseline layers are not listed here.

---

# 3 · The boundary

## The standard format

Every row is an object keyed by the eight canonical attributes, **or** their
snake_case equivalents, **or** anything in the extraction engine's own alias
table (`Item Code`, `Material Code`, `Qty`, `Part No`, `Brand`, …).

- `"NA"`, `"N/A"`, `null`, `""`, `"none"` all mean **absent**, not a value.
- Unrecognised keys are ignored, not rejected — a forwarded session attaches
  `_record_id` and `_is_modified`, and a row carrying provenance is not
  malformed.
- `Item Description (Raw)` and `Company` are required. `default_company`
  supplies the second when the model could not ground it.

## `POST /standardized/check`

**Which of these N rows are NOT already in the vector embedding DB?**

Three ways to say what to check. Exactly one; sending two is a `422`.

```jsonc
{"session_id": "sess_1757..."}    // a reviewed extraction session
{"rows":    [ {...}, {...} ]}     // the rows directly
{"records": [ {...}, {...} ]}     // pipeline-one's forwarder envelope, verbatim
```

With a `session_id` the rows are the session's **`current`** values — the
corrections, never the raw predictions — and the batch records
`source_session_id`, which is what stamps `extraction_model` on the row when it
is added. An unknown session is a `404`. There is no separate "forward"
endpoint: looking a session up and running the check would be the check under a
second name.

Optional alongside any of the three: `default_company`, `source_pipeline`,
`requested_by`.

**Writes nothing to the master.** Response:

```json
{
  "batch_id": "8f3c...",
  "has_new_data": true,
  "message": "2 of 10 row(s) are new material; 8 already exist in the vector embedding DB. POST /standardized/add with this batch_id to index the new ones.",

  "total_rows": 10,
  "new_rows": 2,
  "existing_rows": 8,
  "duplicate_rows_in_batch": 0,
  "invalid_rows": 0,

  "new_material": [ { "company": "GAIL", "description": "V-BELT SEC C 120 INCH", "...": "...", "row_number": 9, "material_id": "GAIL-4004" } ],

  "rows": [ {
    "row_number": 1,
    "status": "ALREADY_EXISTS",
    "description": "BALL BEARING 6205 2RS",
    "category": "BEARING",
    "material_id": "NTPC-1001",
    "embedded_text": "Item Description (Raw): BALL BEARING 6205 2RS\nUOM: NOS",
    "matched_material_id": "NTPC-1001",
    "matched_by": "MATERIAL_ID",
    "similarity": 1.0,
    "duplicate_of_row": null,
    "reason": "Material NTPC-1001 is already in the master and the vector embedding DB. Same CPSE, same legacy code.",
    "neighbours": [ { "material_id": "BHEL-77", "score": 0.81 } ],
    "error": null
  } ],

  "existence_threshold": 0.9,
  "vector_store": "qdrant",
  "embedding_provider": "Qwen/Qwen3-Embedding-0.6B",
  "indexed_total": 404
}
```

`new_material` answers *"which of my N rows are new"*. `rows` carries every row
sent, with its verdict, for audit.

### Row statuses

| `status` | Meaning |
| :--- | :--- |
| `NEW` | Not in the vector embedding DB. This is the material to add. |
| `ALREADY_EXISTS` | Present already — see `matched_by`. |
| `DUPLICATE_IN_BATCH` | New to the DB, but an earlier row of *this* payload is the same article. `duplicate_of_row` names it. |
| `INVALID` | Not usable standard format. `error` says why. Reported, never dropped. |

### How "already exists" is decided

Four signals, in this order. The order is the design: the exact ones cannot be
wrong, so they go first.

| # | `matched_by` | Signal | Can it be wrong? |
| :-- | :--- | :--- | :--- |
| 1 | `MATERIAL_ID` | Same CPSE, same legacy code | no |
| 2 | `CANONICAL_HASH` | The text that would be embedded is byte-identical | no |
| 3 | — | An earlier row of this same payload has that hash | no |
| 4 | `VECTOR_SIMILARITY` | Nearest vector ≥ `EXISTENCE_THRESHOLD` (0.90) | yes — hence `similarity` and `neighbours` |

**This is not a matcher.** It answers one question — is this row worth
embedding — and nothing else.

### When nothing is new

Not an error:

```json
{ "has_new_data": false, "new_rows": 0, "existing_rows": 10, "new_material": [],
  "message": "No new data. All 10 row(s) are already available in the vector embedding DB." }
```

### When the vector store is unreachable

Signals 1–3 still decide, `neighbours` come back empty, and `message` says the
check ran degraded — re-run before trusting a `NEW` verdict. A check that
refuses to answer because Qdrant is down is worse than one that answers with
less evidence and admits it.

## `POST /standardized/add`

**Add the new material to the vector embedding DB.**

```json
{ "batch_id": "8f3c...", "requested_by": "ops@cpcl" }
```

The rows written are the ones the check judged `NEW`, so a client cannot talk
this endpoint into re-indexing something that already exists.

`{"rows": [...]}` checks and adds in one call for a caller that skipped the
check. Exactly one of `batch_id` / `rows`; both, or neither, is a `422`.

Either way the rows are **re-checked here before anything is written**: a batch
is a snapshot, and someone else may have indexed the same article in between.

```json
{
  "batch_id": "8f3c...",
  "added": 2,
  "requested": 2,
  "skipped_existing": 0,
  "skipped_invalid": 0,
  "indexed": 2,
  "materials": [ { "material_id": "GAIL-4004", "row_number": 9, "description": "V-BELT SEC C 120 INCH", "cpse_code": "GAIL" } ],
  "material_ids": ["GAIL-4004", "IOCL-5005"],
  "message": "Added 2 new material row(s) to the master and the vector embedding DB."
}
```

- Nothing left to add → `200` with `added: 0` and a message saying why.
- A batch already added → **`409`**. Run a new check instead.
- Unknown batch → `404`.
- **Vector store unreachable → `503`, and nothing is written anywhere.** The
  upsert happens inside the transaction, so a store that will not take the
  vectors rolls the master write back too. `indexed` therefore always equals
  `added`.

  Deliberate: there is no rebuild endpoint, so a row written to the master
  without a vector could never be embedded, and every later check would keep
  calling it new while the master already held it.

## `GET /standardized/batches` · `GET /standardized/batches/{batch_id}`

The audit trail for what Phase 1 offered: counts per status, and — for one
batch — the recorded verdict for every row it carried.

`new_material` is the staged copy of the rows judged new, present only while
the batch is `CHECKED`. Once added, those rows live in `material` and the batch
carries `material_ids` instead: a second copy of the master would only let the
two drift.

A `CHECKED` batch nobody acted on is pruned after `BATCH_RETENTION_DAYS` (7).
`ADDED` batches are never pruned. `404` on an unknown id.

---

# 4 · The master

## `GET /materials`

| Query | |
| :--- | :--- |
| `cpse` | narrow to one CPSE code |
| `category` | narrow to one material family, e.g. `BEARING`, `VALVE` |
| `query` | substring over description, legacy code, material id — a way to find a row you already know about, **not** semantic search |
| `indexed` | `true` = has a vector, `false` = awaiting indexing |
| `limit` / `offset` | 1–500 / ≥0 |

Each row carries the eight attributes, `category`, `attributes` (the canonical
names, absent ones omitted — the same shape Phase 1 emits), plus `batch_id`,
`extraction_model`, `embedding_version`, `indexed`, `indexed_at`.

## `GET /materials/{material_id}` · `DELETE /materials/{material_id}`

Fetch one, or delete one and its vector. Delete takes `?actor=` — the one
irreversible operation here, so it is recorded on the audit trail.

```json
{ "material_id": "NTPC-1001", "deleted": true, "vector_deleted": true,
  "detail": "Removed from the master and the vector embedding DB." }
```

An unreachable store still deletes from Postgres and says so. That is the one
place the two are allowed to diverge, and it diverges in the safe direction:
the master is authoritative and it is the one that dropped the row.

---

# 5 · The vector index

Read-only. The index has exactly one writer — `POST /standardized/add` — and no
rebuild.

## `GET /retrieval/status`

`materials`, `indexed`, `awaiting_indexing`, `store`, `store_reachable`,
`store_error`, `provider`, `ann_enabled`. Computed from Postgres, so it stays
truthful when the store is down.

`awaiting_indexing` reports **drift, not queued work**. In normal operation it
is `0`, because add writes both stores or neither. A non-zero count means a
hand-edited row or a changed `EMBEDDING_VERSION`, and the only repair is to
delete the material and offer it again.

## `GET /retrieval/model/info`

Which embedding provider is live. `is_fallback: true` means the seeded hash —
stable vectors with **no semantic signal**. A demo can never silently claim
Qwen3 quality on fallback vectors.

---

# 6 · Search

## `POST /search`

Find the existing materials a free-form query refers to. No fixed fields.

```jsonc
{"query": "V BELT C 120"}
{"query": "M-55321"}
{"query": "industrial V belt C section approximately 1200 mm"}
{"query": "V belt C 120 length 1200 mm NTPC M-55321", "top_k": 20, "final_k": 5}
```

| Field | Default | |
| :--- | :--- | :--- |
| `query` | required | Up to 2000 characters. Empty after normalisation → `400`; blank → `422`. |
| `top_k` | `SEARCH_TOP_K` (20) | Candidates fetched from the vector store and reranked. Capped at `SEARCH_MAX_TOP_K`. |
| `final_k` | `SEARCH_FINAL_K` (5) | Results returned. Never more than `top_k`. |

The pipeline, in order: identifier-like tokens (`M-55321`, `224411`,
`NTPC-M-55321`, `NMM-00000042` — never a bare `6205` or `120`) are looked up
exactly in the master by national id, material id, legacy code and part
number; the normalised text is embedded with the live provider and searched in
the vector store for `top_k` candidates; every candidate is scored against the
query by the Siamese reranker in one batch; `final_score` fuses the two
(`SEARCH_QDRANT_WEIGHT × qdrant_score + SEARCH_SIAMESE_WEIGHT × siamese_score`)
and the `final_k` best come back with a three-way match level.

```jsonc
{
  "query": "V BELT C 120",
  "results": [
    {
      "national_id": "NMM-00000004",
      "material_id": "BHEL-224411",
      "cpse_code": "BHEL",
      "company": "BHEL",
      "legacy_code": "224411",
      "description": "BELT V C-120",
      "uom": "NOS",
      "part_number": "C120",
      "make": "PIX",
      "specifications": "C section V belt",
      "category": "BELT",
      "qdrant_score": 0.7712,          // retrieval cosine; null if the row entered by identifier only
      "siamese_score": 0.9851,         // Siamese pair score in [0, 1]; null if the reranker did not run
      "final_score": 0.921,            // the ranking key
      "match": true,                   // true only for "high"
      "match_level": "high",           // high | possible | none
      "matched_by": ["vector"]         // "identifier", "vector", or both
      "match_source": "siamese",       // exact_identifier | siamese | retrieval_only | none
      "matched_by": ["vector"],        // "identifier", "vector", or both
      "identifier_match": false,       // true if matched via exact identifier token
      "identifier_match_type": null,   // "exact" or null
      "identifier_matched_field": null,// national_id | material_id | legacy_code | part_number
      "identifier_token": null         // query token that matched
    }
  ],
  "total_candidates": 20,
  "best_match_level": "high",
  "message": "2 high-confidence match(es) and 1 possible.",
  "pipeline": {
    "normalized_query": "V BELT C 120",
    "identifiers": [],
    "identifier_only": false,
    "vector_search_ran": true,
    "embedding_model": "Qwen/Qwen3-Embedding-0.6B",
    "embedding_version": "qwen3-0.6b-v1",
    "embedding_is_fallback": false,
    "embedding_error": null,
    "vector_store": "qdrant",
    "store_error": null,
    "top_k": 20,
    "final_k": 5,
    "candidates_retrieved": 20,
    "identifier_hits": 0,
    "reranker_applied": true,
    "reranker_model": "sentence-transformers/all-MiniLM-L6-v2 + projection (siamese-v1)",
    "reranker_detail": "Applied to 20 candidate(s) in one batch.",
    "qdrant_weight": 0.3,
    "siamese_weight": 0.7,
    "match_threshold": 0.75,
    "possible_threshold": 0.55
    "possible_threshold": 0.55,
    "degraded": false,
    "warnings": []
  }
}
```

### Match levels

| `match_level` | When | `match` |
| :--- | :--- | :--- |
| `high` | `final_score ≥ SEARCH_MATCH_THRESHOLD`, **or** an exact identifier hit | `true` |
| `possible` | `≥ SEARCH_POSSIBLE_THRESHOLD` — a reviewer decides | `false` |
| `none` | below both — still returned, so the nearest thing is visible | `false` |

Identifier hits sort first. A query that is nothing but identifiers
(`"M-55321"`) skips the vector stage when they are found
(`vector_search_ran: false`); when they are not, it runs, because a code can
live inside a stored description.

### Degradation — every state is in the response, none is hidden

| State | Status | What comes back |
| :--- | :--- | :--- |
| No trained checkpoint / no torch / `SEARCH_RERANKER_ENABLED=false` | `200` | Ordered by `qdrant_score`, `siamese_score: null`, `reranker_applied: false` with the reason. **No result can be `high`.** |
| Reranker raises on a query | `200` | Same, `reranker_detail` carries the error. |
| Vector store returns nothing | `200` | `results: []`, `message` says so. |
| Vector store unreachable, an identifier matched | `200` | The identifier hits, `store_error` set, `message` says "identifier lookup only". |
| Vector store unreachable, nothing matched | `503` | Nothing to answer from. Retry when the store is back. |
| `EMBEDDING_PROVIDER=deterministic` | `200` | `embedding_is_fallback: true` — the retrieval scores carry no signal. |

## `GET /search/model/info`

Which models the search actually runs on, now: the retrieval provider (and
whether it is the seeded-hash fallback), the vector store, the Siamese
reranker — `available`, `model_path`, `device`, the pair threshold and
validation metrics recorded in its checkpoint, or the reason it is not loaded
— and the search settings in force. A demo cannot claim reranked results while
`reranker.available` is `false`.

The reranker is trained offline with `scripts/train_siamese.py` and evaluated
with `scripts/evaluate_search.py`; no request trains or changes it. See the
README, "Search".

---

# 7 · Jobs

`GET /jobs` · `GET /jobs/{job_id}` (`?wait=` to long-poll) ·
`POST /jobs/{job_id}/cancel`

`kind` is one of `EXTRACT_BATCH`, `STANDARDIZED_CHECK`, `STANDARDIZED_ADD`. For
extraction, `GET /extract/jobs/{job_id}` is the friendlier read. A job that
fails keeps the HTTP status it would have had synchronously in `error_status`.

Jobs live in this process: two workers do not share a queue, and a restart
marks anything still `RUNNING` as `FAILED` rather than leaving a caller polling
work that no longer exists. Every job kind here is safe to resubmit.

---

# 8 · Health

`GET /health` — unprefixed, and the only endpoint outside `/api/v1`.

```json
{ "status": "ok", "service": "ai-service", "version": "0.1.0", "environment": "development" }
```

---

# 9 · Errors

| Status | Means |
| :--- | :--- |
| `400` | The request is wrong — blank text, an unparseable file, an empty abbreviation. |
| `404` | Unknown id — job, session, record, batch, material. |
| `409` | The batch has already been added. Run a new check. |
| `422` | The body does not validate — two input modes at once, or none. |
| `503` | A dependency will not answer: the LoRA adapter is not loaded, or the vector store cannot be written. Nothing was written. |

A job that fails carries the status it would have had synchronously, so moving
work into the background never turns "your file is malformed" into "something
went wrong".
