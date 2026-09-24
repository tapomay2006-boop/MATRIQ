# sih-2026
# National Unified Material Master (NUMM) · SIH-2026

Monorepo for the Smart India Hackathon 2026 project.
[![SIH-2026](https://img.shields.io/badge/SIH-2026-Problem%20Statement%2026099-blue.svg)](https://www.sih.gov.in)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant%20Cloud-red.svg)](https://qdrant.tech)
[![PyTorch](https://img.shields.io/badge/PyTorch-CUDA%20Accelerated-orange.svg)](https://pytorch.org)
[![Tests](https://img.shields.io/badge/Tests-242%20Passed-brightgreen.svg)]()

**Problem Statement 26099** — AI-Driven Standardization and Harmonization of
Material Codes Across CPSEs · Ministry of Petroleum & Natural Gas · CPCL.
> **AI-Driven Standardization and Harmonization of Material Codes Across Central Public Sector Enterprises (CPSEs)**  
> *Ministry of Petroleum & Natural Gas · CPCL · Smart India Hackathon 2026*

Several CPSEs each keep their own material master. The same bearing is
`DEEP GROOVE BALL BEARING 6205 2RS` in one and `BRG BALL DP GRV 6205-2RS SKF` in
another. This system decides, for any two codes, whether they are the same
article — and shows the evidence for the answer.
Comprehensive architecture guide for the Siamese Network and two-stage search is available at:  
👉 **[SIAMESE_SEARCH_ARCHITECTURE_GUIDE.md](SIAMESE_SEARCH_ARCHITECTURE_GUIDE.md)**

## Architecture
---

Specified in [`docs/`](docs/00_INDEX.md), which describes the system **as built**
and marks where a section describes something designed but not yet implemented.
## 1. System Overview

| Doc | Covers | Status |
| --- | --- | --- |
| [01 System](docs/01_SYSTEM_ARCHITECTURE.md) | Actors, the end-to-end journey, request paths, topology, technology decisions | Mixed |
| [02 Backend](docs/02_BACKEND_ARCHITECTURE.md) | **`api-service`** — auth, RBAC, CPSE isolation, uploads, review workflow, national codes | Planned |
| [03 ML](docs/03_ML_ARCHITECTURE.md) | The seven-stage deterministic pipeline | **Superseded** |
| [04 Retrieval & matcher](docs/04_RETRIEVAL_AND_MATCHER_INTERFACE.md) | Qwen3 embeddings and Qdrant ANN — retrieval stands, the matcher half does not | Part superseded |
| [05 Matching & rules](docs/05_MATCHING_AND_RULE_ENGINE.md) | The five rules and the four-way verdict | **Superseded** |
| [06 API](docs/06_API_SPECIFICATION.md) | Part A `api-service` (planned) · Part B `ai-service` (superseded) | Mixed |
| [**AI Service API**](docs/AI_SERVICE_API_SPECIFICATION.md) | **`ai-service` as it is today** — extraction, the boundary, the vector DB | **Built** |
| [07 Deployment](docs/07_DEPLOYMENT.md) | Compose topology, configuration, operations, scale triggers | Built |
| [08 Progress](docs/08_DEVELOPMENT_PROGRESS.md) | Frontend modernization, live AI integration, DB decoupling & Neon Postgres | **Built** |
Across Indian CPSEs (e.g. NTPC, BHEL, Coal India, GAIL, IOCL, ONGC), the same industrial spare part is purchased and stored under wildly inconsistent descriptions and proprietary codes:
- **BHEL:** `BELT V C-120` (Legacy Code: `224411`)
- **NTPC:** `V-BELT SEC C, NOM L 120 INCH` (Legacy Code: `M-55321`)
- **Coal India (BCCL):** `v belt c-120 fenner pix only for crusher drive - URGENT REQ` (Legacy Code: `MAT6833850`)

## Layout
This platform solves cross-enterprise material deduplication and search via a unified, two-stage AI architecture:
1. **Extraction & Normalization (Phase 1):** Fine-tuned `Qwen2.5-3B-Instruct` with LoRA adapter (`qwen2.5-3b-cpse-lora-v2`) parses unstructured catalogues into 8 canonical procurement attributes.
2. **Deterministic Lookup (Stage 0):** Exact code/identifier resolution in PostgreSQL (`material_id`, `legacy_code`, `part_number`, `national_id`).
3. **Coarse Dense Retrieval (Stage 1):** 1024-dimensional semantic retrieval with `Qwen/Qwen3-Embedding-0.6B` and Qdrant Cloud HNSW index to retrieve Top-20 family candidates in ~5ms.
4. **Fine-Grained Siamese Reranking (Stage 2):** Fine-tuned Siamese Metric Network (`data/models/siamese-cpse-v1`, MiniLM-L6 backbone with 256-d metric projection head) scores the 20 candidates in a single tensor pass to discriminate subtle dimensional parameters (e.g. distinguishing `C-120` from near-miss `C-125`).

---

## 2. Project Layout

```
sih-2026/
├── frontend/                 Next.js 16 (TypeScript, Tailwind CSS 4, App Router, Stateless JWT)
├── frontend/                     # Next.js 16 (React 19, Tailwind CSS 4, Lucide Icons)
├── backend/
│   ├── api-service/          FastAPI — business state, RBAC, users, Neon PostgreSQL
│   ├── ai-service/           FastAPI — Phase 1 extraction + the vector embedding DB
│   └── pipeline-one/         Phase 1 as its own service, the seed corpus,
│                             and the qwen2.5-3b-cpse-lora-v2 weights (195 MB)
├── docker-compose.yml
└── Makefile
│   ├── api-service/              # FastAPI — Business logic, auth, RBAC, reviews (Port 8000)
│   ├── ai-service/               # FastAPI — ML core, vector search, Siamese reranker (Port 8001)
│   │   ├── app/
│   │   │   ├── logic/            # Pure algorithms (query prep, ranking, siamese, embedding)
│   │   │   ├── routes/           # REST endpoints (/search, /materials, /retrieval, /extract)
│   │   │   ├── services/         # Orchestration (search, reranker, indexing, materials)
│   │   │   └── training/         # Training pipeline, pair generation, evaluate
│   │   ├── data/                 # Training pairs, evaluation queries, checkpoints
│   │   └── scripts/              # CLI tools: reindex.py, train_siamese.py, evaluate_search.py
│   └── pipeline-one/             # Phase 1 LoRA weights & raw CPSE corpus (CPSE_SIH26099.csv)
├── docs/                         # Specifications & engineering documentation
├── docker-compose.yml            # Container orchestration
├── SIAMESE_SEARCH_ARCHITECTURE_GUIDE.md  # Deep-dive presentation & math guide
└── Makefile                      # Build and run targets
```

## Services
---

| Service      | Stack                          | Port | Status |
| ------------ | ------------------------------ | ---- | ------ |
| frontend     | Next.js 16, React 19, Stateless JWT, Tailwind CSS 4 | 3000 | **Built** — Live /upload & studio |
| api-service  | FastAPI, SQLAlchemy 2, Neon Postgres (asyncpg) | 8000 | Built — Neon connected, User persistence |
| ai-service   | FastAPI, SQLAlchemy 2, Qwen2.5-3B LoRA, Qwen3 + Qdrant | 8001 | **Built** — 141 tests |
| qdrant       | Vector store for ANN retrieval | 6333 | Running |
## 3. Quick Start & Running the Services

The frontend talks only to `api-service`. `api-service` is the single client of
`ai-service`, so the ML service stays behind one boundary.
### Prerequisites
- Python 3.12+ (Python 3.14 venv tested)
- PostgreSQL 15+ (Running locally on `127.0.0.1:5432` or Neon Cloud)
- Qdrant Cloud cluster or local container on port `6333`
- NVIDIA GPU with CUDA recommended (GTX 1650 or higher)

**`ai-service` authenticates nobody** — `api-service` owns users, roles and CPSE
scoping, and every `ai-service` endpoint is callable by any caller that can
reach the port. The network *is* the security boundary: never expose `:8001`
publicly.
### Setup & Launch
```bash
# 1. Clone the repository and enter directory
git clone <repo-url> && cd sih-2026

## Quick start
# 2. Configure environment files
cp backend/ai-service/.env.example backend/ai-service/.env
# Update DB credentials and Qdrant Cloud keys in backend/ai-service/.env

```bash
cp .env.example .env
docker compose up --build
# 3. Synchronize database schema (adds any missing columns)
cd backend/ai-service
.venv/bin/python scripts/sync_schema.py --apply

# 4. Start the AI Service
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Without Docker:
The service is now active on **`http://localhost:8001`**.  
Interactive Swagger documentation: **`http://localhost:8001/docs`**.

```bash
make install          # frontend npm install + a venv per backend service
make dev-ai           # the ML pipeline on :8001
make dev-frontend
---

## 4. Search API Reference: `localhost:8001/api/v1/search`

The primary search endpoint accepts free-form text: part numbers, legacy codes, descriptive specifications, colloquial engineering phrasing, or sentences.

### Endpoint
- **URL:** `http://localhost:8001/api/v1/search`
- **Supported Methods:** `POST` (Primary), `GET` (Browser convenience)

---

### A. POST Search Request

#### Request Format
```http
POST /api/v1/search HTTP/1.1
Host: localhost:8001
Content-Type: application/json

{
  "query": "V BELT C 120",
  "top_k": 20,
  "final_k": 5
}
```

`ai-service` needs **Python 3.12**. Copy the env examples first:
| Parameter | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `query` | `string` | **Yes** | — | Free-form query (up to 2000 chars): code, name, sentence, or parameters. |
| `top_k` | `integer` | No | `20` | Candidate pool size retrieved from Qdrant and evaluated by the Siamese model (max 100). |
| `final_k` | `integer` | No | `5` | Number of final ranked results returned. |

```bash
cp backend/ai-service/.env.example backend/ai-service/.env
cp backend/api-service/.env.example backend/api-service/.env
cp frontend/.env.example frontend/.env.local
---

### B. GET Search Request (Browser Friendly)

You can query directly in a web browser address bar:
```http
GET /api/v1/search?query=V+BELT+C+120&top_k=20&final_k=5 HTTP/1.1
Host: localhost:8001
```
*(Or shorthand: `GET /api/v1/search?q=C-120`)*

## Running the pipeline
If `GET /api/v1/search` is opened without parameters, it returns an informative 200 response with endpoint schema, example links, and documentation pointers.

`ai-service` has **one way in**: a raw catalogue through the fine-tuned
`qwen2.5-3b-cpse-lora-v2` adapter, then the vector-DB check. Phase 1 is off by
default, so turn it on first — `make install-ml`, then
`EXTRACTION_ENABLED=true`; see
[backend/ai-service/README.md](backend/ai-service/README.md).
---

```bash
make extract-info  # whether the LoRA adapter is loaded, and from where
make model-info    # which embedding provider is really live
make index-status  # index completeness and store connectivity
### C. Search Response Schema

```jsonc
{
  "query": "V BELT C 120",
  "results": [
    {
      "national_id": null,
      "material_id": "BHEL-224411",
      "cpse_code": "BHEL",
      "company": "BHEL",
      "legacy_code": "224411",
      "description": "BELT V C-120",
      "uom": "NOS",
      "part_number": "C120",
      "make": "PIX",
      "specifications": "C section V belt",
      "category": "UNCLASSIFIED",
      "qdrant_score": 0.7711,          // Coarse retrieval cosine (null if pure code hit)
      "siamese_score": 0.9619,         // Siamese fine-grained score [0, 1]
      "final_score": 0.9047,           // Weighted fusion: 0.3*qdrant + 0.7*siamese
      "match": true,                   // True only if match_level == "high"
      "match_level": "high",           // "high" | "possible" | "none"
      "match_source": "siamese",       // "exact_identifier" | "siamese" | "retrieval_only" | "none"
      "matched_by": ["vector"],        // How it reached pool: ["identifier"], ["vector"], or both
      "identifier_match": false,       // True if matched via code token
      "identifier_match_type": null,   // "exact" or null
      "identifier_matched_field": null,// "legacy_code" | "material_id" | "part_number" | "national_id"
      "identifier_token": null         // Matched token (e.g. "M-55321")
    }
  ],
  "total_candidates": 20,
  "best_match_level": "high",
  "message": "3 high-confidence match(es) and 2 possible.",
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
    "possible_threshold": 0.55,
    "degraded": false,
    "warnings": []
  }
}
```

Or directly — full contract in
[AI_SERVICE_API_SPECIFICATION.md](docs/AI_SERVICE_API_SPECIFICATION.md):
---

```bash
# Phase 1: a raw catalogue -> the eight canonical CPSE attributes
curl -F 'file=@catalogue.xlsx' localhost:8001/api/v1/extract/csv
### D. Match Decision Rules

# The boundary: which rows are NOT already in the vector embedding DB?
# Takes a reviewed session id, or the rows directly.
curl -X POST localhost:8001/api/v1/standardized/check \
     -H 'Content-Type: application/json' -d '{"session_id": "sess_..."}'
The ranking engine classifies matches into 3 confidence bands:

# Add only the new ones
curl -X POST localhost:8001/api/v1/standardized/add \
     -H 'Content-Type: application/json' -d '{"batch_id": "..."}'
```
            Final Score >= 0.75  ────────►  HIGH MATCH (match: true)
                                            Automated harmonization recommended.
                                            (Also triggered by exact identifier hits)

curl        localhost:8001/api/v1/materials
curl        localhost:8001/api/v1/retrieval/status
      0.55 <= Final Score < 0.75 ────────►  POSSIBLE MATCH (match: false)
                                            Surfaced in UI for human reviewer.

            Final Score < 0.55   ────────►  NONE (match: false)
                                            Nearest neighbour only. No match.
```

Extraction is a background job: `POST /extract/csv` returns a `job_id`, and
`GET /extract/jobs/{job_id}` reports `processed_rows / total_rows` while it
runs. Full contract in
[AI_SERVICE_API_SPECIFICATION.md](docs/AI_SERVICE_API_SPECIFICATION.md).
---

## Tests
### E. Search Pipeline Telemetry: `GET /api/v1/search/model/info`

Inspect live retrieval and reranker model state:
```bash
make test             # both backend suites
make test-ai          # 141 tests (+10 Qdrant integration, opt-in)
make lint
curl -s http://localhost:8001/api/v1/search/model/info | jq .
```
Response verifies model name, dimension (1024), device (CUDA), pair validation metrics, and degradation flags.

The Qdrant integration tests are skipped unless a server is running:
---

## 5. Machine Learning Pipeline & CLI Tools

All ML lifecycle operations are completely decoupled from runtime HTTP serving.

### 1. Vector Reindexing (`scripts/reindex.py`)
Computes Qwen3 embeddings for all materials in Postgres and upserts them to Qdrant Cloud using deterministic UUID5 point IDs:
```bash
docker compose up -d qdrant
cd backend/ai-service && QDRANT_TEST_URL=http://localhost:6333 .venv/bin/pytest
# Dry run: verifies database connection, point counts, and dimensions
.venv/bin/python scripts/reindex.py

# Apply: computes embeddings on GPU, updates Postgres & Qdrant Cloud
.venv/bin/python scripts/reindex.py --apply
```

## Two things to know before reading the code
### 2. Siamese Network Training (`scripts/train_siamese.py`)
Trains the Siamese cross-reranker on positive and hard-negative pairs:
```bash
.venv/bin/python scripts/train_siamese.py \
    --corpus ../pipeline-one/CPSE_SIH26099.csv \
    --pairs  data/training/seed_pairs.csv \
    --output data/models/siamese-cpse-v1 \
    --epochs 5 \
    --batch-size 32 \
    --lr 1.5e-5 \
    --margin 1.3 \
    --device cuda
```

**The raw data is never modified.** `backend/pipeline-one/CPSE_SIH26099.csv` is
opened read-only, and mounted `:ro` in Docker. What a CPSE submitted is stored
verbatim — a national master that silently edits its inputs cannot be
reconciled against a CPSE's own books.
### 3. Search Quality & Calibration Sweep (`scripts/evaluate_search.py`)
Evaluates retrieval and reranking metrics over 71 benchmark queries:
```bash
EMBEDDING_PROVIDER=qwen3 .venv/bin/python scripts/evaluate_search.py \
    --corpus ../pipeline-one/CPSE_SIH26099.csv \
    --queries data/evaluation/search_queries.csv \
    --model data/models/siamese-cpse-v1 \
    --calibrate \
    --device cuda
```

**Both models are optional, and the service says which is live.** Phase 1
(`qwen2.5-3b-cpse-lora-v2`) and the Qwen3 embedding provider are both off by
default: `ai-service` runs, demos and passes every test with no weights on
disk. `GET /api/v1/extract/info` and `GET /api/v1/retrieval/model/info` always
report the real state, so a demo can never claim fine-tuned extraction or
Qwen3-quality vectors it is not actually producing.
#### Verified Evaluation Benchmark:
| Model / Pipeline | Hit@1 | MRR | Match Precision | Match Recall | Match F1 | Calibrated Threshold |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qdrant Only** (Retrieval Baseline) | 1.000 | 1.000 | 0.701 | 0.943 | **0.804** | 0.589 |
| **Siamese Only** (Reranker Alone) | 0.979 | 0.990 | 0.897 | 0.915 | **0.906** | 0.771 |
| **Qdrant + Siamese** (Default Thr 0.75) | **1.000** | **1.000** | **0.911** | **0.895** | **0.903** | 0.750 |
| **Qdrant + Siamese** (Calibrated Thr 0.72) | **1.000** | **1.000** | **0.899** | **0.924** | **0.911** | 0.719 |

**Some code exists twice, deliberately.** `ai-service/app/logic/extraction.py`
and its `/extract` API surface are copies of `pipeline-one`'s
`inference_engine.py` and `app.py`. Copies, not forks — the only local edits
are two paths marked `[AI-SERVICE]`, and the re-sync rule is in the file
headers. The weights are *not* copied: they stay in `pipeline-one` and are
referenced by path. `session_store.py` is deliberately not vendored — review
sessions are Postgres rows here, because a process-local dict listed nothing
after a restart.
- **Near-Miss Discrimination:** The Siamese reranker scores near-miss `V BELT C 125` at `0.7449` (< 0.75), cleanly avoiding a false-high match.
- **Conversational Queries:** `a belt that is c-120` scores `0.9579` against C-120 (Target $\ge 0.85$ passed).

**Search is not built.** `ai-service` fills the vector index and answers one
question about an incoming row — is it already there. Searching that index is
the next piece of work.
---

**There is no rebuild.** The master and the vector index are written in one
transaction by `POST /standardized/add`, so a store that cannot be written
fails the add and writes nothing. That is why there is no reindex endpoint: a
row in the master without a vector could never be embedded, and every later
check would keep calling it new.
## 6. Testing & Code Quality

```bash
# Run Ruff lint check (100% clean)
.venv/bin/ruff check .

# Run full pytest test suite (242 passed)
.venv/bin/pytest -q

# Verify live search against all 10 benchmark queries
.venv/bin/python scripts/verify_search.py
```

---

## 7. Presentation & Architecture Defense

For a complete breakdown of the Contrastive Loss mathematics, Siamese weight sharing, and defense Q&A for the hackathon jury, see:  
📘 **[SIAMESE_SEARCH_ARCHITECTURE_GUIDE.md](SIAMESE_SEARCH_ARCHITECTURE_GUIDE.md)**.
