# 06 · API Specification

> ## ⚠ Part B is superseded
>
> `ai-service` was restructured on 2026-09-10. Its endpoints, request shapes
> and response models all changed: there is no `/materials/ingest`,
> `/ingest/by-reference`, `/materials/import/preview|confirm`,
> `/materials/{id}/matches`, `/materials/match-all`, `/materials/national/*`
> or `/materials/evaluation/*` any more.
>
> **The current `ai-service` API is
> [`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md).**
>
> Part A (`api-service`) is unaffected — it was always a specification to build
> against, and `api-service` itself was not touched by the restructure.

---

> Scope: the HTTP contracts of **both** services.
>
> **Part A — `api-service`** (`:8000`) is the public, authenticated surface the
> frontend talks to. It is _Planned_: the scaffold serves only `/health`, an
> in-memory `/users`, and a proxy route that points at a deleted endpoint. Treat
> Part A as a specification to build against, not as documentation of running
> code.
>
> **Part B — `ai-service`** (`:8001`) is **built, tested and working**. Every
> request and response in Part B is real output from the running service.

```
browser ──► api-service :8000 ──► ai-service :8001
            Part A, planned       Part B, built
```

`ai-service` is never called by the browser. It carries no _user_ model and
enforces no authorisation whatsoever — every endpoint is open to any caller that
can reach it. `:8000` is the only surface that should ever be published, and
`:8001` must never be routable from outside the internal network.

---

## Navigation & Services Overview

| Section                                                     | Target Service | Base URL                       | Status           | Description                                                                                  |
| ----------------------------------------------------------- | -------------- | ------------------------------ | ---------------- | -------------------------------------------------------------------------------------------- |
| [**Part A — `api-service`**](#part-a--api-service--planned) | `api-service`  | `http://localhost:8000/api/v1` | _Planned_        | Public authenticated gateway for frontend UI                                                 |
| [**Part B — `ai-service`**](#part-b--ai-service--built)     | `ai-service`   | `http://localhost:8001/api/v1` | **Built & Live** | 31 endpoints: standardization, NER, duplicates, matching, Qdrant, review queues & governance |

> 💡 **Dedicated Reference**: For a focused specification dedicated solely to the 31 built ML/AI and governance endpoints without Part A planned routes, see [**`docs/AI_SERVICE_API_SPECIFICATION.md`**](AI_SERVICE_API_SPECIFICATION.md) or [`backend/ai-service/API_SPECIFICATION.md`](../backend/ai-service/API_SPECIFICATION.md).

### Quick Jump to `ai-service` Endpoints (Part B)

- **Ingestion & CSV Preview**: [`POST /import/preview`](#15a-post-apiv1materialsimportpreview) · [`POST /import/confirm`](#15b-post-apiv1materialsimportconfirm) · [`POST /materials/ingest`](#15-post-apiv1materialsingest) · [`POST /ingest/by-reference`](#27-post-apiv1ingestby-reference) · [`GET /ingest/jobs`](#28-get-apiv1ingestjobs) · [`GET /ingest/jobs/{id}/errors`](#30-get-apiv1ingestjobsjob_iderrors)
- **Materials Master & Creation**: [`GET /materials`](#16-get-apiv1materials) · `POST /materials` · [`GET /materials/{id}`](#18-get-apiv1materialsmaterial_id) · `PUT /materials/{id}` · [`DELETE /materials/{id}`](#18a-delete-apiv1materialsmaterial_id) · [`GET /materials/quality`](#17-get-apiv1materialsquality) · `GET /materials/{id}/audit`
- **Governance & Review Queues**: `GET /materials/reviews/company-queue` · `POST /materials/{id}/company-review` · `GET /materials/reviews/national-queue` · `POST /materials/{id}/national-review`
- **Official National Master**: `GET /materials/national` · `GET /materials/national/{code}` · `POST /materials/national` · `POST /materials/national/map`
- **Matching & Candidate Review**: [`GET /materials/{id}/matches`](#19-get-apiv1materialsmaterial_idmatches) · [`POST /materials/match-all`](#20-post-apiv1materialsmatch-all) · [`POST /materials/matches/{id}/review`](#21-post-apiv1materialsmatchesmatch_idreview)
- **Evaluation & Gold Standard**: [`POST /ground-truth/build`](#22-post-apiv1materialsground-truthbuild) · [`GET /evaluation/report`](#23-get-apiv1materialsevaluationreport)
- **Vectors & Qdrant Cloud**: [`POST /retrieval/index`](#24-post-apiv1retrievalindex) · [`GET /retrieval/status`](#25-get-apiv1retrievalstatus) · [`GET /retrieval/model/info`](#26-get-apiv1retrievalmodelinfo)
- **Health**: [`GET /health`](#14-get-health)

---

## Part A — `api-service` · _Planned_

Base URL `http://localhost:8000`, prefix `/api/v1`.

### 1. What the scaffold actually serves today

| Method | Path                                   | State                                                                                            |
| ------ | -------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `GET`  | `/health`                              | Works                                                                                            |
| `POST` | `/api/v1/users`                        | Works, but writes to a module-level dict — data is lost on restart                               |
| `GET`  | `/api/v1/users` · `/api/v1/users/{id}` | Same                                                                                             |
| `POST` | `/api/v1/ai/infer`                     | **Broken.** Proxies to `ai-service` `/api/v1/inference/predict`, which was deleted. Returns 404. |

Everything from §2 onward does not exist yet. Section
[02 §11](02_BACKEND_ARCHITECTURE.md) gives the order to build it in.

### 2. Authentication · _Planned_

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email": "a.kumar@cpcl.co.in", "password": "..."}
```

```json
200
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "3f1c...", "email": "a.kumar@cpcl.co.in",
    "full_name": "A. Kumar", "role": "CPSE_REVIEWER",
    "cpse": {"id": "9a2e...", "code": "CCL", "name": "Coal India (CCL)"}
  }
}
```

Every subsequent request carries `Authorization: Bearer <token>`.
HS256, 24-hour expiry — the settings for this already exist in
`app/config.py`.

| Status | When                                                         |
| ------ | ------------------------------------------------------------ |
| `401`  | Missing, malformed or expired token; bad credentials         |
| `403`  | Authenticated, but the role or CPSE scope does not permit it |

`403` rather than `404` when a user asks for another CPSE's material: hiding
existence is not a requirement here, and a clear "not yours" is more useful to a
legitimate user who mistyped an id.

### 3. `POST /api/v1/uploads` · _Planned_

```http
POST /api/v1/uploads
Authorization: Bearer <token>          role: CPSE_UPLOADER
Content-Type: multipart/form-data

file=@ccl_master_2026Q1.csv
```

```json
202
{
  "batch_id": "b7f3...",
  "filename": "ccl_master_2026Q1.csv",
  "sha256": "9f2c...",
  "row_count": 404,
  "status": "RECEIVED",
  "duplicate_of": null
}
```

| Status | When                                                                      |
| ------ | ------------------------------------------------------------------------- |
| `202`  | Accepted; standardization runs in the background                          |
| `409`  | A batch with this `sha256` already exists — `duplicate_of` names it       |
| `413`  | File too large                                                            |
| `422`  | Required columns missing. **Nothing is stored**, and the error names them |

```json
422
{"detail": "Missing required columns: ['Make / Brand', 'UOM']"}
```

The eight required columns are the ones `ai-service` validates on ingest —
see §15.

### 4. `GET /api/v1/uploads/{batch_id}` · _Planned_

```json
{
  "batch_id": "b7f3...",
  "status": "STANDARDIZED",
  "row_count": 404,
  "received_at": "2026-03-14T09:21:04Z",
  "standardized_at": "2026-03-14T09:21:07Z",
  "categories": { "BEARING": 47, "ELECTRICAL": 39, "...": 0 },
  "quality_flags": {
    "UOM_MISMATCH": 286,
    "DESCRIPTION_NOISE": 162,
    "IRREGULAR_SPACING": 161,
    "PART_NUMBER_ABSENT": 101,
    "MISSING_IDENTITY_ATTRIBUTE": 88
  },
  "error": null
}
```

`status` moves `RECEIVED → STANDARDIZING → STANDARDIZED`, or `→ FAILED` with
`error` set. **Rows are retained on failure**, so a failed batch never has to be
re-uploaded.

The `categories` and `quality_flags` blocks are passed through from `ai-service`
§15 unchanged.

### 5. `GET /api/v1/materials` · _Planned_

Same shape as `ai-service` §16, with two differences:

- **Scoped.** A `CPSE_*` role sees only its own CPSE's materials, enforced in the
  repository layer, not in the route.
- **Filtered.** Fields another CPSE may not see (price, quantity, vendor) are
  removed before serialization.

| Query                         | Notes                                                    |
| ----------------------------- | -------------------------------------------------------- |
| `cpse`                        | Ignored for CPSE-scoped roles; honoured for `NATIONAL_*` |
| `category`, `limit`, `offset` | As `ai-service`                                          |
| `batch_id`                    | Restrict to one upload                                   |
| `flag`                        | e.g. `UOM_MISMATCH` — the quality worklist               |

### 6. `POST /api/v1/batches/{batch_id}/match` · _Planned_

```json
202
{"job_id": "j4a1...", "status": "QUEUED"}
```

Wraps `ai-service` §20. Asynchronous from the start: it takes seconds on 404
materials and minutes at scale, and a synchronous request would eventually time
out.

`GET /api/v1/jobs/{job_id}`:

```json
{
  "job_id": "j4a1...",
  "status": "SUCCEEDED",
  "started_at": "...",
  "finished_at": "...",
  "result": {
    "materials": 404,
    "stored": 2946,
    "EXACT_DUPLICATE": 2080,
    "NEAR_DUPLICATE": 856,
    "FUNCTIONALLY_EQUIVALENT": 10,
    "NOT_EQUIVALENT": 1084
  },
  "review_tasks_created": 2946
}
```

### 7. `GET /api/v1/reviews` · _Planned_

The review queue.

| Query          | Default | Notes                                                      |
| -------------- | ------- | ---------------------------------------------------------- |
| `state`        | `OPEN`  | `OPEN`, `NEEDS_INFO`, `APPROVED`, `REJECTED`, `SUPERSEDED` |
| `relationship` | —       | `NEAR_DUPLICATE`, `FUNCTIONALLY_EQUIVALENT`, …             |
| `cross_cpse`   | —       | `true` shows only pairs spanning two CPSEs                 |
| `assigned_to`  | —       | `me` for the caller's queue                                |

```json
{
  "total": 856,
  "tasks": [
    {
      "task_id": "t8c2...",
      "state": "OPEN",
      "relationship": "NEAR_DUPLICATE",
      "confidence_score": 1.0,
      "confidence_kind": "heuristic_confidence",
      "hard_rule_status": "PASS",
      "proposed_before_rules": "EXACT_DUPLICATE",
      "capped_by_rules": true,
      "reason": "No conflicts, but neither record states head_type, which the category treats as identity-defining.",
      "left": {
        "material_id": "IOCL-000017",
        "cpse_code": "IOCL",
        "description_raw": "high  tensile  bolt  m24  x  100mm  grade  8.8  galvanized   REQ AS PER ATTACHED SPEC"
      },
      "right": {
        "material_id": "CCL-000036",
        "cpse_code": "CCL",
        "description_raw": "high  tensile  bolt  m24  x  100mm  grade  8.8  galvanized **OEM ONLY**"
      },
      "matched_attributes": [
        "finish",
        "length",
        "material",
        "property_class",
        "thread_size"
      ],
      "conflicting_attributes": [],
      "missing_attributes": [],
      "advisories": [
        "Units of measure differ. Advisory: verify the issue unit."
      ],
      "required_approvals": 2,
      "approvals_recorded": 0
    }
  ]
}
```

Every explanatory field — `confidence_kind`, `proposed_before_rules`, `reason`,
the three attribute lists, `advisories` — is **pinned onto the task** when it is
created, not fetched live. A reviewer must see the evidence they were shown, and
`match-all` clears `match_result` on every run.

`required_approvals` is `2` for a cross-CPSE pair and `1` within one CPSE — see
[02 §4](02_BACKEND_ARCHITECTURE.md).

### 8. `POST /api/v1/reviews/{task_id}` · _Planned_

```json
{ "decision": "APPROVED", "comment": "Confirmed with vendor — same SKF part." }
```

```json
201
{
  "task_id": "t8c2...",
  "decision": "APPROVED",
  "state": "OPEN",
  "approvals_recorded": 1,
  "required_approvals": 2,
  "national_code": null
}
```

When the last required approval lands, `state` becomes `APPROVED` and
`national_code` is populated in the same response.

| Status | When                                                                |
| ------ | ------------------------------------------------------------------- |
| `201`  | Decision recorded                                                   |
| `403`  | Not a reviewer, or the pair does not touch the caller's CPSE        |
| `409`  | Task already `APPROVED`/`REJECTED`, or this user already decided it |

Unlike `ai-service` §21, `reviewer` is **not** a request field. It comes from the
token. That is the whole reason this endpoint exists separately.

### 9. `GET /api/v1/national-codes/{code}` · _Planned_

```json
{
  "code": "NUMM-BEARING-000001",
  "category": "BEARING",
  "canonical_description": "BEARING: bearing_number=6205; bearing_type=BALL; seal_type=2RS",
  "issued_at": "2026-03-14T11:02:55Z",
  "issued_by": "a.kumar@cpcl.co.in",
  "superseded_by": null,
  "mappings": [
    {
      "cpse_code": "CCL",
      "legacy_code": "116045321",
      "material_id": "CCL-000001",
      "linked_at": "2026-03-14T11:02:55Z",
      "unlinked_at": null
    },
    {
      "cpse_code": "BHEL",
      "legacy_code": "BRG-6205-A",
      "material_id": "BHEL-000071",
      "linked_at": "2026-03-14T11:02:55Z",
      "unlinked_at": null
    }
  ]
}
```

`mappings` is append-only. A legacy code is never overwritten or removed; a wrong
mapping is closed with `unlinked_at`. Every CPSE keeps querying its own master by
its own code forever.

`GET /api/v1/materials/{material_id}/national-code` resolves the other direction.

### 10. `GET /api/v1/exports/...` · _Planned_

| Path                           | Returns                                        |
| ------------------------------ | ---------------------------------------------- |
| `/exports/national-master.csv` | Every national code with its mappings          |
| `/exports/quality-report.csv`  | Every quality flag with its raw value          |
| `/exports/decisions.csv`       | Every review decision with actor and timestamp |

CSV and XLSX. Scoped like everything else: a CPSE role exports its own slice.

### 11. Errors · _Planned_

| Status | When                                                         |
| ------ | ------------------------------------------------------------ |
| `401`  | Not authenticated                                            |
| `403`  | Authenticated but not permitted, including cross-CPSE access |
| `404`  | Unknown id **within the caller's scope**                     |
| `409`  | Duplicate batch, or a decision on a closed task              |
| `413`  | Upload too large                                             |
| `422`  | Validation — missing columns, bad payload                    |
| `502`  | `ai-service` unreachable or erroring                         |

`502` is the one worth designing for: `api-service` must degrade to read-only
over already-stored results rather than failing the whole UI when `ai-service` is
down. The existing `ai.py` already maps `httpx.HTTPError` to `502` correctly.

### 12. What Part A does not do

- It never recomputes a verdict. Scores, relationships and reasons are stored as
  `ai-service` returned them.
- It never strips `confidence_kind`, the match `note` or the evaluation
  `caveat`. Those exist so nobody mistakes a heuristic for a probability.
- It never rewrites a CPSE's raw values. Corrections are flags, exactly as in
  [03 §12](03_ML_ARCHITECTURE.md).

---

## Part B — `ai-service` · **Built**

Base URL `http://localhost:8001`, prefix `/api/v1`. Interactive docs at `/docs`.

Every example below is real output from the running service against the 404-row
extract.

### 13. Endpoints (31 Operational Endpoints)

| Method   | Path                                              | Group      | Roles              | Purpose                                                           |
| -------- | ------------------------------------------------- | ---------- | ------------------ | ----------------------------------------------------------------- |
| `GET`    | `/health`                                         | System     | Any                | Service liveness check & version                                  |
| `POST`   | `/api/v1/materials/import/preview`                | Ingestion  | CMA, CMM, NMA, NMM | Preview CSV, in-file & DB duplicate check, stage session          |
| `POST`   | `/api/v1/materials/import/confirm`                | Ingestion  | CMA, CMM, NMA, NMM | Confirm & persist selected rows, index into Qdrant                |
| `POST`   | `/api/v1/materials/ingest`                        | Ingestion  | CMA, NMA, NMM      | Load the raw extract, run Phase 1 standardization                 |
| `POST`   | `/api/v1/ingest/by-reference`                     | Ingestion  | CMA, NMA, NMM      | Ingest a CSV already staged in storage                            |
| `GET`    | `/api/v1/ingest/jobs`                             | Ingestion  | Any                | Recent batch import jobs list                                     |
| `GET`    | `/api/v1/ingest/jobs/{job_id}`                    | Ingestion  | Any                | Single import job summary & metrics                               |
| `GET`    | `/api/v1/ingest/jobs/{job_id}/errors`             | Ingestion  | Any                | Quarantined unparseable row errors                                |
| `GET`    | `/api/v1/materials`                               | Materials  | Any                | Filtered search & pagination (scoped by CPSE/role)                |
| `POST`   | `/api/v1/materials`                               | Materials  | CMA, NMA, NMM      | Create single material, standardize via AI, enter review          |
| `GET`    | `/api/v1/materials/{material_id}`                 | Materials  | Any                | Material detail with standardized attributes & quality flags      |
| `PUT`    | `/api/v1/materials/{material_id}`                 | Materials  | CMA, NMA, NMM      | Data correction on draft/rejected/pending records                 |
| `DELETE` | `/api/v1/materials/{material_id}`                 | Materials  | CMA, NMA, NMM      | Delete material, cascade dependencies & Qdrant vector             |
| `GET`    | `/api/v1/materials/quality`                       | Materials  | Any                | Corpus-wide data-quality flag distribution                        |
| `GET`    | `/api/v1/materials/{material_id}/audit`           | Materials  | Any                | Complete immutable audit trail for a material                     |
| `GET`    | `/api/v1/materials/reviews/company-queue`         | Governance | CMM, CMA           | Pending materials review queue scoped to CPSE                     |
| `POST`   | `/api/v1/materials/{material_id}/company-review`  | Governance | CMM                | Company review decision (`APPROVE`, `REJECT`, `REQUEST_CHANGES`)  |
| `GET`    | `/api/v1/materials/reviews/national-queue`        | Governance | NMM, NMA           | National review queue (company-approved materials)                |
| `POST`   | `/api/v1/materials/{material_id}/national-review` | Governance | NMM                | Final national governance approval (`APPROVE`, `REJECT`, `MERGE`) |
| `GET`    | `/api/v1/materials/national`                      | Governance | Any                | List all official National Materials                              |
| `GET`    | `/api/v1/materials/national/{national_code}`      | Governance | Any                | National Material details and mapped CPSE items                   |
| `POST`   | `/api/v1/materials/national`                      | Governance | NMA, NMM           | Create canonical National Material master entry                   |
| `POST`   | `/api/v1/materials/national/map`                  | Governance | NMA, NMM           | Map CPSE material to official National Material code              |
| `GET`    | `/api/v1/materials/{material_id}/matches`         | Matching   | Any                | Match one material live (retrieval + rules + explanation)         |
| `POST`   | `/api/v1/materials/match-all`                     | Matching   | NMA, NMM           | Run pairwise matching across entire corpus                        |
| `POST`   | `/api/v1/materials/matches/{match_id}/review`     | Matching   | CMM, NMM           | Record human match equivalence decision                           |
| `POST`   | `/api/v1/materials/ground-truth/build`            | Evaluation | NMM                | Generate gold-standard evaluation set                             |
| `GET`    | `/api/v1/materials/evaluation/report`             | Evaluation | Any                | Precision/Recall/F1 evaluation report against gold standard       |
| `POST`   | `/api/v1/retrieval/index`                         | Vectors    | NMA, NMM           | Re-embed standardized corpus into vector index                    |
| `GET`    | `/api/v1/retrieval/status`                        | Vectors    | Any                | Vector store indexing progress & backend health                   |
| `GET`    | `/api/v1/retrieval/model/info`                    | Vectors    | Any                | Active embedding model inspection                                 |

**Security, Authentication & Role-Based Access Control (RBAC):**
`ai-service` enforces multi-tenant CPSE data isolation and governance separation of duties via context headers (provided directly or forwarded by the API Gateway):

`ai-service` reads **no caller headers at all** and has no user model — no roles, no identity, nothing to forward. Anything sent is ignored.

Actions worth attributing accept an optional **`actor`** label in the **request body**, recorded on the audit entry. It is unverified free text: a label on a record, never an identity and never a permission. `api-service` is where operations are restricted to a user's organization.

For full schemas, payload examples, state machine transitions, and curl walkthroughs, refer to [**`docs/AI_SERVICE_API_SPECIFICATION.md`**](AI_SERVICE_API_SPECIFICATION.md).

---

### 14. `GET /health`

```json
{
  "status": "ok",
  "service": "ai-service",
  "version": "0.1.0",
  "environment": "development"
}
```

---

### 15. `POST /api/v1/materials/ingest`

No body. Reads `settings.raw_dataset_path`, runs Phase 1 over every row,
replaces all derived rows, exports JSONL, writes an `INGEST` audit row.

**200**

```json
{
  "materials": 404,
  "categories": {
    "BEARING": 47,
    "ELECTRICAL": 39,
    "FILTER": 32,
    "LUBRICANT": 27,
    "VALVE": 26,
    "PIPE_FITTING": 26,
    "...": 0
  },
  "quality_flags": {
    "UOM_MISMATCH": 286,
    "DESCRIPTION_NOISE": 162,
    "IRREGULAR_SPACING": 161,
    "PART_NUMBER_ABSENT": 101,
    "MISSING_IDENTITY_ATTRIBUTE": 88
  }
}
```

**500** — the source CSV is missing a required column. The error names the
columns rather than failing row by row.

Idempotent. The source file is opened read-only and never written.

---

### 15a. `POST /api/v1/materials/import/preview`

Upload a CSV to preview standardized materials, detect intra-batch duplicates and matches against existing database materials, and stage the batch in a temporary session. **Does not write to the `materials` table or modify Qdrant**.

| Parameter / Field | Source | Default      | Description                                  |
| ----------------- | ------ | ------------ | -------------------------------------------- |
| `filename`        | Query  | `upload.csv` | Original filename or identifier              |
| `default_company` | Query  | `""`         | Fallback CPSE/company code if missing in row |

**Supported Request Payloads**:

- `multipart/form-data`: file field (e.g. `file=@data.csv`)
- `text/csv` / `application/octet-stream`: raw CSV string or bytes in the request body
- `application/json`: `{"source": "relative/path/to.csv"}` (resolved against `UPLOAD_DIR` or absolute path)

**Processing Steps**:

1. **Sanitization & Parsing**: Verifies CSV headers (supports standard 8-column layout as well as arbitrary schemas with standard aliases: `description`/`item_description`, `company`/`cpse_code`, `legacy_code`/`item_code`, `uom`/`unit`).
2. **Standardization**: Executes Phase 1 standardization (cleaning, category classification, attribute extraction).
3. **In-File Duplicate Detection**: Compares rows within the uploaded batch. Duplicates are flagged with `status: "EXACT_DUPLICATE_IN_FILE"`, `duplicate_of_row: <1-indexed row>`, and default `selected: false`.
4. **Database Duplicate Detection**: Matches unique candidate rows against existing database records. Matches are flagged as `EXACT_DUPLICATE`, `NEAR_DUPLICATE`, or `FUNCTIONALLY_EQUIVALENT` with `existing_material_id`, `confidence_score`, and default `selected: false`.
5. **Fresh Records**: Records with no conflicts are marked `status: "NEW"` with `selected: true`.
6. **Session Staging**: Serializes preview results to `import_sessions` with a 24-hour expiration TTL. Returns `session_id`.

**Response (200 OK)**:

```json
{
  "session_id": "8f3b610c-f236-4074-b5a8-48b495204481",
  "total_rows": 3,
  "new_materials": 1,
  "exact_duplicates_in_file": 1,
  "existing_matches": 1,
  "invalid_rows": 0,
  "rows": [
    {
      "row_number": 1,
      "original_description": "DEEP GROOVE BALL BEARING 6205 2RS SKF",
      "category": "BEARING",
      "canonical_text": "DEEP GROOVE BALL BEARING 6205 2RS SKF",
      "status": "NEW",
      "duplicate_of_row": null,
      "existing_material_id": null,
      "match_reason": null,
      "confidence_score": null,
      "selected": true,
      "error_message": null
    },
    {
      "row_number": 2,
      "original_description": "DEEP GROOVE BALL BEARING 6205 2RS SKF",
      "category": "BEARING",
      "canonical_text": "DEEP GROOVE BALL BEARING 6205 2RS SKF",
      "status": "EXACT_DUPLICATE_IN_FILE",
      "duplicate_of_row": 1,
      "existing_material_id": null,
      "match_reason": "Identical canonical text to row 1 in current file",
      "confidence_score": 1.0,
      "selected": false,
      "error_message": null
    },
    {
      "row_number": 3,
      "original_description": "BALL BEARING 6205-2RS1 SKF",
      "category": "BEARING",
      "canonical_text": "BALL BEARING 6205 2RS1 SKF",
      "status": "EXACT_DUPLICATE",
      "duplicate_of_row": null,
      "existing_material_id": "CCL-000001",
      "match_reason": "Database match: EXACT_DUPLICATE with CCL-000001 (score: 0.98)",
      "confidence_score": 0.98,
      "selected": false,
      "error_message": null
    }
  ]
}
```

---

### 15b. `POST /api/v1/materials/import/confirm`

Commits selected rows from an active preview session into the database and vector store.

**Request Body**:

```json
{
  "session_id": "8f3b610c-f236-4074-b5a8-48b495204481",
  "selected_rows": [1]
}
```

_Note: If `selected_rows` is empty or omitted, only rows with `selected: true` from the preview step are imported._

**Behavior**:

- Validates that `session_id` exists, has not expired, and has status `PENDING`.
- Inserts selected materials into `materials`, child attributes into `material_attributes`, and data-quality flags into `quality_flags`.
- Immediately computes embeddings and indexes the newly created materials into the Qdrant vector store (`materials` collection).
- Writes an append-only row to `audit_log` with action `IMPORT_CONFIRM`.
- Updates `import_sessions.status` to `APPLIED`.

**Response (200 OK)**:

```json
{
  "session_id": "8f3b610c-f236-4074-b5a8-48b495204481",
  "requested": 1,
  "imported": 1,
  "skipped": 2,
  "failed": 0,
  "material_ids": ["CCL-000405"]
}
```

**Errors**:

- `400`: Session expired, already applied, or invalid session ID.
- `404`: Session not found.

---

### 16. `GET /api/v1/materials`

| Query      | Default | Notes                            |
| ---------- | ------- | -------------------------------- |
| `cpse`     | —       | Case-insensitive, e.g. `ccl`     |
| `category` | —       | Case-insensitive, e.g. `bearing` |
| `limit`    | `50`    | 1–500                            |
| `offset`   | `0`     |                                  |

Returns `MaterialOut[]`, ordered by `source_row`.

```json
[
  {
    "material_id": "CCL-000001",
    "cpse_code": "CCL",
    "cpse_name": "Coal India (Central Coalfields Limited)",
    "legacy_code": "116045321",
    "description_raw": "brg ball rad 6205 2rs for main store",
    "description_normalized": "BEARING BALL RADIAL 6205 2RS",
    "canonical_text": "BEARING: bearing_number=6205; bearing_type=BALL; seal_type=2RS",
    "category": "BEARING",
    "category_confidence": 0.95,
    "uom_raw": "NOS",
    "uom_normalized": "NOS",
    "quantity": 50.0,
    "attributes": [
      {
        "name": "bearing_number",
        "value": "6205",
        "role": "IDENTITY_DEFINING",
        "unit": null,
        "numeric_value": null,
        "confidence": 0.9
      },
      {
        "name": "bearing_type",
        "value": "BALL",
        "role": "IDENTITY_DEFINING",
        "unit": null,
        "numeric_value": null,
        "confidence": 0.9
      },
      {
        "name": "seal_type",
        "value": "2RS",
        "role": "DISCRIMINATING",
        "unit": null,
        "numeric_value": null,
        "confidence": 0.9
      }
    ],
    "missing_identity": [],
    "quality_flags": [
      {
        "code": "DESCRIPTION_NOISE",
        "severity": "INFO",
        "field": "description",
        "detail": "Removed procurement noise: STORE_NOTE.",
        "raw_value": "brg ball rad 6205 2rs for main store"
      }
    ]
  }
]
```

`raw_value` on every flag carries the original string. Nothing was corrected.

---

### 17. `GET /api/v1/materials/quality`

```json
{
  "materials": 404,
  "flags": [
    { "code": "UOM_MISMATCH", "severity": "WARNING", "count": 286 },
    { "code": "DESCRIPTION_NOISE", "severity": "INFO", "count": 162 },
    { "code": "IRREGULAR_SPACING", "severity": "INFO", "count": 161 },
    { "code": "PART_NUMBER_ABSENT", "severity": "INFO", "count": 101 },
    { "code": "MISSING_IDENTITY_ATTRIBUTE", "severity": "WARNING", "count": 88 }
  ]
}
```

Sorted by count descending. This is the master-data-health report a CPSE acts on.

---

### 18. `GET /api/v1/materials/{material_id}`

`MaterialOut` as above. **404** with `Unknown material 'XXX'` if absent.

---

### 18a. `DELETE /api/v1/materials/{material_id}`

Completely deletes a material from PostgreSQL, cascades through dependent relational tables, removes its embedding vector from Qdrant, and writes an append-only audit record.

**Parameters**:

- `material_id` (path): The string identifier of the material (e.g. `CCL-000001`).

**Cascade & Cleanup Semantics**:

1. **Relational Cascades**: Deletes child rows from `material_attributes` and `quality_flags`.
2. **Dependent Cleanups**: Explicitly deletes associated records in `reviews` and `match_results` where this material is either `query_material_id` or `target_material_id` to prevent foreign key or reference orphaning.
3. **Primary Record**: Deletes the `materials` table row.
4. **Vector Index Cleanup**: Computes the deterministic UUIDv5 Qdrant point ID via `generate_material_point_id(material_id)` (using namespace `6ba7b810-9dad-11d1-80b4-00c04fd430c8`) and issues point deletion to Qdrant.
5. **Audit Trail**: Appends a row to `audit_log` with action `MATERIAL_DELETED` and metadata `{"material_id": material_id, "cpse": cpse_code}`.

**Response (200 OK)**:

```json
{
  "material_id": "CCL-000001",
  "deleted": true,
  "qdrant_deleted": true,
  "detail": "Material CCL-000001 deleted and removed from vector index"
}
```

**Errors**:

- `404 Not Found`: If `material_id` does not exist in the database: `{"detail": "Unknown material 'CCL-999999'"}`.

---

### 19. `GET /api/v1/materials/{material_id}/matches`

The most important endpoint. `top_k` (1–50) overrides `settings.top_k`.

Runs the engine **live** rather than reading `match_result`, so a change to
`data/config/*.csv` is visible on the next request without a re-run.

Real output for `GET /api/v1/materials/CCL-000001/matches?top_k=3`. The second
candidate is a real result for `CCL-000002`, included here to show a
rule-driven verdict alongside a clean one.

```json
{
  "query": { "...MaterialOut for CCL-000001..." },
  "compared": 46,
  "summary": {
    "EXACT_DUPLICATE": 3, "NEAR_DUPLICATE": 0,
    "FUNCTIONALLY_EQUIVALENT": 0, "NOT_EQUIVALENT": 0
  },
  "candidates": [
    {
      "material_id": "CCL-000056",
      "cpse_code": "CCL",
      "description_raw": "bearing  ball  radial  6205  2rs  skf/fag  make  only **OEM ONLY**",
      "relationship": "EXACT_DUPLICATE",
      "confidence_score": 1.0,
      "confidence_kind": "heuristic_confidence",
      "hard_rule_status": "PASS",
      "proposed_before_rules": "EXACT_DUPLICATE",
      "capped_by_rules": false,
      "reason": "All 3 comparable attributes agree, no conflicts, no missing identity evidence.",
      "matched_attributes": ["bearing_number", "bearing_type", "seal_type"],
      "conflicting_attributes": [],
      "missing_attributes": [],
      "rules_triggered": ["UOM"],
      "advisories": ["Units of measure differ. Advisory: verify the issue unit."]
    },
    {
      "material_id": "NTPC-000258",
      "cpse_code": "NTPC",
      "description_raw": "BEARING  BALL  RADIAL  6205  2RS  SKF/FAG  MAKE  ONLY **OEM ONLY**",
      "relationship": "FUNCTIONALLY_EQUIVALENT",
      "confidence_score": 0.6779,
      "confidence_kind": "heuristic_confidence",
      "hard_rule_status": "REVIEW",
      "proposed_before_rules": "FUNCTIONALLY_EQUIVALENT",
      "capped_by_rules": false,
      "reason": "Discriminating conflict (seal_type: 2RS1 vs 2RS). Needs engineer sign-off.",
      "matched_attributes": ["bearing_number", "bearing_type"],
      "conflicting_attributes": [
        {"name": "seal_type", "role": "DISCRIMINATING", "left": "2RS1", "right": "2RS"}
      ],
      "missing_attributes": [],
      "rules_triggered": ["DISCRIMINATING", "UOM"],
      "advisories": ["Units of measure differ. Advisory: verify the issue unit."]
    }
  ],
  "note": "confidence_score is a deterministic heuristic, not a calibrated probability. Hard rules can override it."
}
```

### Reading a candidate

| Field                                     | What it tells you                                                                                                                                                                                    |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `confidence_kind`                         | Which of three claims this number makes: `heuristic_confidence` (weighted structure), `learned_confidence` (fitted weights) or `calibrated_probability` (isotonic-mapped). Never bare `probability`. |
| `proposed_before_rules` vs `relationship` | Differ ⇒ the rules pulled the verdict down                                                                                                                                                           |
| `capped_by_rules`                         | The same fact as a boolean                                                                                                                                                                           |
| `reason`                                  | The specific evidence, naming attributes and both values                                                                                                                                             |
| `conflicting_attributes`                  | Both sides' values, so the disagreement is legible without refetching                                                                                                                                |
| `missing_attributes`                      | Stated on one side only. **Not** a conflict.                                                                                                                                                         |
| `inferred_attributes`                     | Agreement resting on a _derived_ value (e.g. bearing bore from an ISO designation). Corroborates identity; can never establish it alone.                                                             |
| `signals`                                 | Each signal's value. Multiplied by its weight and summed, these reproduce the raw score by hand.                                                                                                     |
| `penalties`                               | The multiplicative steps applied after — conflicts, missing identity, the UOM gate, calibration.                                                                                                     |
| `retrieved_by`                            | Which retrieval paths surfaced this candidate: `category_block`, `fingerprint`, `ann`, `trigram`.                                                                                                    |
| `explanation`                             | The full stored evidence object: signals, gates (shown even when they pass), the four attribute states, provenance and a generated narrative. Rendered verbatim; never recomputed.                   |
| `advisories`                              | Reported, never acted on. UOM findings live here by default.                                                                                                                                         |
| `note`                                    | Present on every response. Not removable.                                                                                                                                                            |

`signals`, `penalties` and `explanation` are persisted on `match_result` as well
as returned, because an explanation derived later from a changed model is not
the explanation that produced the decision.

Candidates are ordered by relationship rank first, score second.

---

### 20. `POST /api/v1/materials/match-all`

No body. Matches the whole corpus, clears and rewrites `match_result`, writes a
`MATCHING_RUN` audit row.

**200**

```json
{
  "materials": 404,
  "stored": 2946,
  "EXACT_DUPLICATE": 2080,
  "NEAR_DUPLICATE": 856,
  "FUNCTIONALLY_EQUIVALENT": 10,
  "NOT_EQUIVALENT": 1084
}
```

**409** — `No materials ingested yet.`

`NOT_EQUIVALENT` is counted but not stored: on this corpus it is the large
majority and no reviewer acts on it. `stored` is the sum of the other three.

Synchronous, a few seconds on 404 materials. If the corpus grows past the point
where a request timeout is plausible, this is the endpoint that becomes a job.

---

### 21. `POST /api/v1/materials/matches/{match_id}/review`

```json
{
  "reviewer": "a.kumar@cpcl.co.in",
  "decision": "APPROVED",
  "comment": "Confirmed, same SKF part."
}
```

**201**

```json
{
  "review_id": "b2df196e-…",
  "match_id": "d7bff2d8-…",
  "decision": "APPROVED",
  "pair": ["IOCL-000017", "CCL-000036"],
  "relationship_at_review": "NEAR_DUPLICATE"
}
```

The response echoes the pair and the verdict because the review stores those,
not a pointer to `match_result` — that table is rebuilt by every `match-all`.
See [03 §19](03_ML_ARCHITECTURE.md).

There is currently **no endpoint that exposes `match_result` ids**, so a caller
cannot discover a `match_id` through the API; it has to come from the database.
That gap belongs to `api-service`'s review queue (Part A §7).

**404** — unknown `match_id`.

`reviewer` is **caller-supplied and unverified**. It is a placeholder until
`api-service` asserts an authenticated identity. Reviews accumulate; a match may
carry several, and none is overwritten. Every review also writes a
`MATCH_REVIEWED` audit row.

---

### 22. `POST /api/v1/materials/ground-truth/build`

`target` (10–200, default 60). Writes `data/ground_truth/pairs.csv`.

```json
{
  "path": "data/ground_truth/pairs.csv",
  "pairs": 60,
  "labels": {
    "EXACT_DUPLICATE": 20,
    "NEAR_DUPLICATE": 19,
    "NOT_EQUIVALENT": 19,
    "NEEDS_EXPERT_REVIEW": 2
  }
}
```

Overwrites the file. If a domain expert has corrected it, **do not call this
again** — their corrections are the point of the file.

`NEEDS_EXPERT_REVIEW` is emitted where the available attributes do not support
either answer. Those pairs are excluded from scoring rather than guessed.

---

### 23. `GET /api/v1/materials/evaluation/report`

```json
{
  "evaluated": 58,
  "skipped": 2,
  "accuracy": 1.0,
  "macro_f1": 1.0,
  "per_label": [
    {
      "label": "EXACT_DUPLICATE",
      "support": 20,
      "predicted": 20,
      "precision": 1.0,
      "recall": 1.0,
      "f1": 1.0
    },
    {
      "label": "NEAR_DUPLICATE",
      "support": 19,
      "predicted": 19,
      "precision": 1.0,
      "recall": 1.0,
      "f1": 1.0
    },
    {
      "label": "NOT_EQUIVALENT",
      "support": 19,
      "predicted": 19,
      "precision": 1.0,
      "recall": 1.0,
      "f1": 1.0
    }
  ],
  "errors": [],
  "caveat": "Gold labels were derived from the same extracted attributes the matcher compares, so these figures show internal consistency. They are not an independent accuracy measurement until a domain expert reviews the labels."
}
```

**409** — no ground truth on disk; build it first.

`skipped` counts `NEEDS_EXPERT_REVIEW` pairs. `errors` lists up to 20
misclassifications with expected and actual labels.

**The `caveat` field is not decoration and must not be stripped when quoting
these numbers.** An accuracy of 1.000 here measures internal consistency —
the gold labels come from the same attributes the matcher compares. It becomes a
real measurement after expert review of `pairs.csv`.

---

### 24. `POST /api/v1/retrieval/index`

Embeds every material and upserts it into the vector store. Idempotent: a point
id derives from `material_id`, so a retried batch is harmless.

```
POST /api/v1/retrieval/index?force=false&recreate=false
```

| Query           | Effect                                                |
| --------------- | ----------------------------------------------------- |
| `force=true`    | Re-embed everything, not just rows whose text changed |
| `recreate=true` | Drop and rebuild the collection first                 |

```json
{
  "materials": 404,
  "embedded": 404,
  "skipped": 0,
  "provider": "Qwen/Qwen3-Embedding-0.6B",
  "embedding_version": "qwen3-0.6b-v1",
  "indexed_total": 404
}
```

Run it again unchanged and `embedded` is `0` with `skipped` at `404`. Staleness
is detected by `canonical_hash`, so editing a dictionary and re-running
re-embeds exactly the affected rows.

---

### 25. `GET /api/v1/retrieval/status`

```json
{
  "materials": 404,
  "indexed": 404,
  "awaiting_indexing": 0,
  "store": "qdrant",
  "store_reachable": true,
  "store_error": null,
  "provider": {
    "model_name": "Qwen/Qwen3-Embedding-0.6B",
    "model_version": "qwen3-0.6b-v1",
    "dimension": 1024,
    "is_fallback": false,
    "detail": "Loaded on cpu, batch 32."
  },
  "ann_enabled": true
}
```

`awaiting_indexing` is computed from Postgres, not from the vector store, so it
stays truthful when Qdrant is unreachable. Reporting `0` there because the store
was down would say "nothing to index" while 404 rows sat unindexed.

An unreachable store is reported (`store_reachable: false` with `store_error`),
never raised — a missing index is a normal state, not a crash.

---

### 26. `GET /api/v1/retrieval/model/info`

```json
{
  "model_name": "deterministic-hash",
  "model_version": "deterministic-v1",
  "dimension": 1024,
  "is_fallback": true,
  "detail": "Seeded-hash fallback. Vectors are stable but carry no semantic signal - retrieval recall is not meaningful on this provider.",
  "vector_store": "memory",
  "ann_enabled": true,
  "top_k": 10
}
```

**The reason this endpoint exists.** `EMBEDDING_PROVIDER=deterministic` is a
seeded hash: the pipeline runs and tests stay fast, but retrieval is
meaningless. That is a legitimate development mode and a dishonest demo mode, so
`is_fallback` makes the difference impossible to hide. A demo can never silently
claim Qwen3 quality on hash vectors.

---

### 27. `POST /api/v1/ingest/by-reference`

The path a real upload takes. `api-service` receives the file from a user,
writes it to the shared upload directory, and passes ai-service **the name, not
the bytes**.

```
user ──multipart──► api-service ──writes──► shared volume (UPLOAD_DIR)
                         │                        ▲
                         └── POST /ingest/by-reference ──┘
```

**Why by reference.** `api-service` is where the user is known, so uploads,
provenance and access control belong there. Streaming the same bytes into
ai-service would duplicate that responsibility and hand a file store to a
service whose job is arithmetic.

```json
POST /api/v1/ingest/by-reference
{
  "source": "20260909T110000-a1c9f3e2-cpcl-master.csv",
  "mode": "merge",
  "original_filename": "CPCL Material Master 2026.csv",
  "requested_by": "ravi@cpcl.co.in",
  "column_map": {
    "description": "Material_Description",
    "company": "Vendor"
  },
  "default_company": "CPCL"
}
```

| Field               | Meaning                                                                                                                                                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source`            | A name relative to `UPLOAD_DIR`, an absolute path inside it, or an `http(s)` URL when `ALLOW_REMOTE_REFERENCE=true`. **Anything resolving outside `UPLOAD_DIR` is refused.**                                                    |
| `mode`              | `merge` (default) or `replace` — see below                                                                                                                                                                                      |
| `original_filename` | What the human called it. Display only.                                                                                                                                                                                         |
| `requested_by`      | **Not verified.** ai-service has no user model; this is a label for the audit trail, never an authorisation.                                                                                                                    |
| `column_map`        | Optional explicit dictionary mapping canonical fields (`company`, `description`, `item_code`, `quantity`, `uom`, `part_number`, `make`, `specifications`) to the header names used in this file. Overrides automatic inference. |
| `default_company`   | Optional fallback string used when the CSV carries no company column, attributing rows to this CPSE instead of quarantining them.                                                                                               |

#### `merge` vs `replace` — the reason this endpoint exists

| Mode                | Deletes                                                                                   |
| ------------------- | ----------------------------------------------------------------------------------------- |
| `merge` _(default)_ | Only the CPSEs **present in this file**. CPSE-B's upload leaves CPSE-A's materials alone. |
| `replace`           | Every material, matching the legacy `POST /materials/ingest`.                             |

The legacy endpoint wipes all four material tables unconditionally. With one
hard-coded CSV that is fine; with real per-CPSE uploads it means the second
upload destroys the first. `merge` fixes exactly that, and re-uploading the same
CPSE's file is idempotent rather than additive.

#### Response — the import job

**200 in every outcome the caller can act on**, including rejection. A rejection
is a result, not a transport failure, and the job id is how a user is shown
which rows to fix.

```json
{
  "id": "3f2b8c14-...",
  "status": "PARTIAL",
  "source": "20260909T110000-a1c9f3e2-cpcl-master.csv",
  "resolved_path": "/srv/data/uploads/20260909T110000-a1c9f3e2-cpcl-master.csv",
  "original_filename": "CPCL Material Master 2026.csv",
  "content_sha256": "9d1f...",
  "size_bytes": 48213,
  "mode": "merge",
  "total_rows": 404,
  "valid_rows": 402,
  "error_rows": 2,
  "materials_written": 402,
  "unclassified_rows": 0,
  "cpse_codes": ["CCL"],
  "column_mapping": "{\"description\": \"Material_Description\", \"company\": \"Vendor\"}",
  "unmapped_columns": "[\"Remarks\", \"CostCenter\"]",
  "detail": "2 row(s) quarantined; 402 imported.",
  "requested_by": "ravi@cpcl.co.in",
  "duration_ms": 1843.7,
  "errors": [
    {
      "row_number": 57,
      "column_name": "Material_Description",
      "error_code": "DESCRIPTION_EMPTY",
      "message": "Description is empty; the row cannot be identified.",
      "raw_value": null
    }
  ]
}
```

| `status`        | Meaning                                                                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `COMPLETED`     | Every row imported.                                                                                                                               |
| `PARTIAL`       | Good rows imported, bad rows quarantined.                                                                                                         |
| `OUT_OF_DOMAIN` | Imported successfully and searchable by text, but unclassified rows exceed `MAX_UNCLASSIFIED_RATE` (50%) due to unrecognized category vocabulary. |
| `REJECTED`      | **Nothing imported.** Bad reference, bad file, missing description column, or >30% unreadable rows.                                               |
| `FAILED`        | An unexpected error.                                                                                                                              |

`errors` carries the first 20 quarantined rows; the full list is at
`/jobs/{id}/errors`.

#### What it refuses, and why

| Refused                                  | Reason                                                                                                                                                                    |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `../../../../etc/passwd`                 | An ingest endpoint that takes a caller-supplied path is an arbitrary-file-read primitive unless fenced. Every reference is `resolve()`d and checked against `UPLOAD_DIR`. |
| A symlink pointing outside `UPLOAD_DIR`  | `resolve()` follows symlinks, so containment is checked on the **real** destination, not the name.                                                                        |
| `http://…` by default                    | Fetching an arbitrary URL on request is SSRF — ai-service cannot tell who is asking. `ALLOW_REMOTE_REFERENCE` is off by default.                                          |
| A file over `MAX_REFERENCE_BYTES`        | Checked before reading, not after.                                                                                                                                        |
| A missing description column             | Without an identifiable description column (even after alias matching and `column_map`), there is nothing to standardize. The whole file is rejected.                     |
| Over `MAX_ROW_ERROR_RATE` bad rows (30%) | Importing the good 60% of a mis-mapped file corrupts the master quietly.                                                                                                  |

**Bad rows are quarantined, never dropped.** A row that vanishes without a trace
is indistinguishable from a row that was never sent.

---

### 28. `GET /api/v1/ingest/jobs`

```
GET /api/v1/ingest/jobs?limit=50
```

Recent jobs, newest first. **Job records are never deleted when materials are
re-imported** — the materials table is rebuilt per CPSE on every upload, but the
record of _what was attempted_ has to outlive that or a failed import becomes
invisible.

---

### 29. `GET /api/v1/ingest/jobs/{job_id}`

One job, with the first 20 quarantined rows. `404` for an unknown id.

---

### 30. `GET /api/v1/ingest/jobs/{job_id}/errors`

```
GET /api/v1/ingest/jobs/{job_id}/errors?limit=200
```

Every quarantined row, so a CPSE can be told exactly what to fix.

| `error_code`        | Meaning                                                        |
| ------------------- | -------------------------------------------------------------- |
| `DESCRIPTION_EMPTY` | The row cannot be identified.                                  |
| `COMPANY_EMPTY`     | The row cannot be attributed to a CPSE.                        |
| `ROW_UNREADABLE`    | The CSV row could not be parsed at all; the raw value is kept. |

---

### 31. Errors

| Status | When                                                            |
| ------ | --------------------------------------------------------------- |
| `400`  | Expired/applied `session_id` on confirm; unreadable CSV payload |
| `404`  | Unknown `material_id`, `match_id`, or `session_id`              |
| `409`  | Matching before ingest; evaluation before ground truth          |
| `422`  | FastAPI validation — bad `limit`, `top_k`, missing `reviewer`   |
| `500`  | Malformed source CSV or unhandled database error                |

FastAPI's default shape:

```json
{ "detail": "Unknown material 'CCL-999999'" }
```

---

### 32. A full session

```bash
# interactive preview, duplicate detection, and selective import
curl -X POST "localhost:8001/api/v1/materials/import/preview?filename=ccl_master.csv" \
     -F "file=@ccl_master.csv"

# confirm selective import of approved row numbers
curl -X POST localhost:8001/api/v1/materials/import/confirm \
     -H "Content-Type: application/json" \
     -d '{"session_id": "8f3b610c-f236-4074-b5a8-48b495204481", "selected_rows": [1, 3]}'

# delete a material and clean up its vector in Qdrant
curl -X DELETE localhost:8001/api/v1/materials/CCL-000001

# batch dataset ingestion (dev / demo corpus)
curl -X POST localhost:8001/api/v1/materials/ingest
curl localhost:8001/api/v1/materials/quality
curl "localhost:8001/api/v1/materials?category=bearing&limit=5"
curl localhost:8001/api/v1/materials/CCL-000012/matches?top_k=5
curl -X POST localhost:8001/api/v1/materials/match-all
curl -X POST localhost:8001/api/v1/materials/ground-truth/build
curl localhost:8001/api/v1/materials/evaluation/report

# ingest by reference (what api-service calls after a user upload)
curl -X POST localhost:8001/api/v1/ingest/by-reference \
     -H 'Content-Type: application/json' \
     -d '{"source":"cpcl-master.csv","mode":"merge","requested_by":"ravi@cpcl"}'
curl localhost:8001/api/v1/ingest/jobs
curl localhost:8001/api/v1/ingest/jobs/{job_id}/errors

# retrieval
curl -X POST localhost:8001/api/v1/retrieval/index
curl localhost:8001/api/v1/retrieval/status
curl localhost:8001/api/v1/retrieval/model/info
```

Or `make ingest`, `make match`, `make evaluate` from the repository root.

---

**Next:** [07 · Deployment](07_DEPLOYMENT.md)
