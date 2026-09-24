# 07 · Deployment

> ## ⚠ Partly superseded
>
> The compose topology, the Postgres/Qdrant configuration and the operational
> reasoning below are still correct. The **`ai-service` endpoints and settings
> are not**: it was restructured on 2026-09-10, and `match-all`,
> `/ingest/by-reference`, `/materials/ingest` and the whole matching stack are
> gone.
>
> The endpoints that replace them are in
> [`AI_SERVICE_API_SPECIFICATION.md`](AI_SERVICE_API_SPECIFICATION.md); the
> settings are in `backend/ai-service/.env.example`, which is the only place
> they are kept up to date.
>
> Deployment facts that changed and are worth having here:
>
> - **`EXTRACTION_ENABLED` is off by default.** The image built from
>   `requirements.txt` has no torch, so `/extract/*` answers 503 and the
>   vector half runs alone. Build from `requirements-ml.txt` to run Phase 1.
> - **The LoRA weights are not in the image.** They are 195 MB and live in the
>   `backend/pipeline-one` checkout, mounted read-only in compose;
>   `LORA_ADAPTER_DIR` points at them.
> - **Ports.** `ai-service` is 8001, `api-service` is 8000. Running
>   `api-service` on 8001 gives a 404 on every `ai-service` route.
> - **`VECTOR_STORE=memory` is dev-only now.** There is no reindex endpoint, so
>   an index that dies with the process can never be rebuilt from the Postgres
>   rows that survive it. Use `qdrant` for anything you intend to keep.
> - **Jobs are in-process.** Extraction, check and add run as asyncio tasks
>   bounded by `MAX_CONCURRENT_JOBS`. A restart marks in-flight work FAILED
>   rather than leaving a caller polling forever; every job kind is safe to
>   resubmit. More than one uvicorn worker means more than one queue.
> - **No filesystem state.** Review sessions and the abbreviation taxonomy are
>   Postgres rows, not files, so no volume is needed for either and both are
>   shared across workers.

---

> Scope: running the whole thing on one laptop, offline, and what changes when it
> stops being one laptop.

---

## 1. What has to be true

| Requirement | How it is met |
|---|---|
| Runs offline | No model download, no external API, no CDN at runtime |
| Runs on CPU | No torch, no CUDA, no GPU code path |
| Starts in seconds | Nothing to load into memory; the config CSVs are a few kilobytes |
| Reproducible | Deterministic pipeline — same input, same output, every time |
| No data leaves the machine | The raw CSV is read locally and never transmitted |

The heaviest dependency in the tree is `rapidfuzz`. Total install is under
100 MB.

---

## 2. Local, without Docker

```bash
cd backend/ai-service
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8001
```

`http://localhost:8001/docs`. Tables are created on startup in the Postgres
database named by `DB_NAME`.

From the repository root:

```bash
make install-ai      # venv + dependencies
make install-ml      # optional: torch + transformers for Qwen3 (~2 GB)
make dev-ai          # uvicorn, reload, :8001
make test-ai         # 141 tests
make lint            # ruff over both backends

make extract-info    # is the LoRA adapter loaded, and from where
make model-info      # which embedding provider is really live
make index-status    # index completeness and store connectivity
```

`ai-service` runs with **no optional dependency installed**: without torch the
extraction endpoints answer 503 and the embedding provider is the deterministic
seeded hash; without a Qdrant server the store is in-process exact search. All
three are honest fallbacks rather than silent degradation —
`GET /api/v1/extract/info` and `GET /api/v1/retrieval/model/info` always report
the live state.

There is no `make train` or `make ablation` any more: the classifier, NER,
fusion and calibration models they fitted belonged to the removed pipeline.

**Python 3.12.** Not 3.13 or 3.14 — some pinned dependencies do not yet have
wheels there and fall back to source builds that fail. If `uv` is available,
`uv venv --python 3.12` is the fast path.

---

## 3. Docker

```
postgres      :5432   source of truth, both services
api-service   :8000   scaffold, not implemented (doc 02)
ai-service    :8001   the ML pipeline
qdrant        :6333   vector index; derived state, rebuildable
frontend      :3000   Next.js
```

```bash
make up      # docker compose up --build
make logs
make down
```

### The shared upload directory

**There is no shared upload volume any more.** `ai-service` reads no files
from a directory a caller names: a catalogue is POSTed to
`/api/v1/extract/csv` as multipart and never touches disk, review sessions and
the abbreviation taxonomy are Postgres rows, and the only path in the config is
`LORA_ADAPTER_DIR`, which is read-only weights. The `UPLOAD_DIR` /
`ALLOW_REMOTE_REFERENCE` / `MAX_REFERENCE_BYTES` settings this section used to
describe are gone, and with them the SSRF and path-traversal surface they
carried.

## 4. Configuration

Every setting is an environment variable, read once by
`app/config.py`. Nothing else reads `os.environ`.

```bash
ENVIRONMENT=development
DEBUG=true
PORT=8001
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]

DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=numm_ai
DB_USER=sih
DB_PASSWORD=sih
DB_SSL=false
DB_SSLMODE=prefer
DB_ECHO=false
# DATABASE_URL=          # full URL; overrides the DB_* parts when set

CONFIG_DIR=data/config

# Phase 1 — off by default; the weights are referenced, not copied.
EXTRACTION_ENABLED=false
LORA_ADAPTER_DIR=../pipeline-one/models/qwen2.5-3b-cpse-lora-v2
BASE_MODEL_NAME=Qwen/Qwen2.5-3B-Instruct

# The boundary
EXISTENCE_THRESHOLD=0.90
EXISTENCE_TOP_K=5
EXISTENCE_BLOCK_BY_CATEGORY=false
BATCH_RETENTION_DAYS=7

TOP_K=10
```

`backend/ai-service/.env.example` is the only place these are kept up to date;
copy it to `.env` to override locally.

### TLS

`db_sslmode` takes the libpq modes, passed straight to asyncpg:

| Mode | Behaviour against a local server |
|---|---|
| `disable` | No TLS |
| `allow` | No TLS unless the server insists |
| `prefer` | **Default.** TLS if offered, plaintext otherwise. Negotiates TLSv1.3 locally |
| `require` | TLS, certificate not verified |
| `verify-ca` · `verify-full` | TLS with verification. Needs a root certificate at `~/.postgresql/root.crt` |

`db_ssl=true` is a convenience switch that raises `disable`/`allow`/`prefer` to
`require` without touching a stronger setting. An unrecognised mode raises at
startup rather than silently downgrading.

### Local Postgres setup

```bash
sudo -u postgres psql -f backend/ai-service/scripts/setup_postgres.sql
```

Creates role `sih` and database `numm_ai`. Idempotent. Under Compose the
equivalent runs from `scripts/init-db.sql`, mounted into the postgres
container's entrypoint — note that only fires on an **empty** data volume, so an
existing `postgres_data` volume needs the database created by hand.

`ai-service` gets its own database rather than sharing `api-service`'s. Two
services in one schema means one `alembic_version` table and two owners for it.

Alembic becomes necessary now —
`create_all` in the lifespan creates missing tables but silently ignores changed
columns — fine for a throwaway database, not fine for this one.

---

## 5. First run

```bash
# 1. A raw catalogue -> standard format. Returns a job id; poll it.
curl -F 'file=@catalogue.xlsx' localhost:8001/api/v1/extract/csv
curl localhost:8001/api/v1/extract/jobs/<job_id>

# 2. Which rows are NOT already in the vector embedding DB? Writes nothing.
curl -X POST localhost:8001/api/v1/standardized/check \
     -H 'Content-Type: application/json' -d '{"session_id": "sess_..."}'

# 3. Index only the new ones.
curl -X POST localhost:8001/api/v1/standardized/add \
     -H 'Content-Type: application/json' -d '{"batch_id": "..."}'

curl localhost:8001/api/v1/materials
curl localhost:8001/api/v1/retrieval/status
```

`check` is idempotent and writes nothing. `add` is not idempotent by design: a
batch can be added once and a replay is a 409, which is what stops a retried
request from creating a second copy.

---

## 6. Operations

**Backup is `pg_dump numm_ai`, and it is now the whole story.** Postgres holds
the master, the review sessions, the abbreviation taxonomy and the batch audit
trail; `data/config/abbreviations.csv` is the shipped baseline the taxonomy
sits on top of, and the LoRA weights live in the `pipeline-one` checkout.

The Qdrant collection is **not** independently recoverable: there is no reindex
endpoint, so back it up alongside Postgres or accept that a lost index means
deleting and re-offering each material. This is the trade that makes
`POST /standardized/add` all-or-nothing.

The old note said the database was regenerable from the CSVs
and the source extract; the CSVs are the only irreplaceable state, because they
carry human judgement.

**Changing domain behaviour** no longer needs a restart for the piece that
changes most: `POST /api/v1/extract/taxonomy/abbreviations` writes an
abbreviation to Postgres and applies it to the live registry, and every other
worker picks it up at startup. Editing `data/config/abbreviations.csv` still
works for the shipped baseline and does need a restart.

Rows carry `pipeline_version`, `extraction_model` and `embedding_version`, so a
material can always be traced to the adapter that read it and the model that
embedded it. A retrained adapter changes what a description means, which is
exactly why the stamp is on the row.

**Logs** are structured JSON via `configure_logging()` in `app/config.py`,
called from the lifespan.

**Health** is `GET /health` — liveness only, and deliberately unauthenticated so
a probe never needs a secret.

There is now something to be unready for: the embedding model loads once at
startup and the vector store may be unreachable. Rather than a readiness probe,
`GET /api/v1/retrieval/status` reports it directly — `store_reachable`,
`indexed`, `awaiting_indexing`, and which provider is live. `awaiting_indexing`
is computed from Postgres, so it stays truthful even when Qdrant is down; it
would be worse to answer "nothing to index" while 404 rows sit unindexed.

A dimension mismatch between the collection and the active provider is a **hard
failure at startup**, never a silent truncation — padding a vector produces
plausible, wrong neighbours.

---

## 7. Security posture

`ai-service` has no authorization and no CPSE scoping. That is deliberate — both
belong to `api-service` ([02](02_BACKEND_ARCHITECTURE.md)), and implementing
them twice would mean two versions of one security rule with the weaker one
deciding. Consequences:

- **Do not expose `:8001` publicly.** In compose it is published for development.
  In any real deployment it sits behind `api-service` on an internal network, and
  the port publication should be removed.
- **There is no second line of defence.** `ai-service` authenticates and
  authorises nobody: every endpoint answers any caller that reaches the port,
  including an anonymous one. The network is the whole boundary. Anything that
  can reach `:8001` can read every CPSE's master and approve national codes.
- `reviewer` on the review endpoint is caller-supplied and unverified.
- CORS defaults to localhost origins. Set `CORS_ORIGINS` explicitly anywhere
  else.
- **Qdrant must not be published either.** It holds no commercially sensitive
  fields by design — price, vendor and quantity are deliberately absent from the
  payload — but it is reachable without credentials.
- **Nothing leaves the deployment.** Models run locally and the LLM fallback,
  when enabled at all, talks only to a local Ollama. A national material master
  must not post procurement data to a third-party API.
- `SECRET_KEY` in compose defaults to `change-me-in-production`. It belongs to
  `api-service` and is unused today.
- `audit_log` is append-only by convention, not by grant. On Postgres,
  `REVOKE UPDATE, DELETE` on that table.

---

## 8. Scale

Current: 404 materials in the reference corpus, a Postgres database of a few
megabytes, and a vector index of the same order. The expensive operation is
Phase 1 — a 3B model at a few seconds per row — and it is already a background
job.

| Growth | What breaks first | Response |
|---|---|---|
| More than one uvicorn worker | Jobs are per-process — two queues, not one | Replace `_spawn` in `services/jobs.py` with Celery or RQ; the Job row, the routes and the polling contract stay as they are |
| A restart during a long extraction | In-flight work is marked FAILED | Resubmit — every job kind is safe to run again |
| ~100k materials | `create_all` schema drift | Alembic migrations |
| The unblocked duplicate check gets slow | Every incoming row is compared against the whole index | `EXISTENCE_BLOCK_BY_CATEGORY=true` — the payload field is already indexed, so no reindex is needed |
| A lost Qdrant collection | Nothing can rebuild it | Back it up with Postgres; there is no reindex endpoint by design |

None of these are near at 404 materials. Stating the trigger for each is more
useful than pre-building for them.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `404` on every `/api/v1/extract/*` route | `api-service` is running on port 8001 | `ai-service` is 8001, `api-service` is 8000 — check which uvicorn is bound |
| `MissingGreenlet` on attribute access | Async lazy load | Eager-load with `selectinload` — `sessions.get_session` already does |
| `503` from `/extract/*` | `EXTRACTION_ENABLED=false`, or torch/peft missing, or the adapter not on disk | `GET /api/v1/extract/info` says which of the three |
| `503` from `/standardized/add` | The vector store cannot be written | Nothing was written; retry when the store is reachable |
| `409` from `/standardized/add` | The batch has already been added | Run a new check |
| `GET /extract/sessions` returns `[]` after a restart | Fixed — sessions are Postgres rows. If you still see it, an old build is running |
| Pip build failures on install | Python 3.13/3.14 | Recreate the venv on 3.12 |
| Ruff `B008` on `Depends(...)` | flake8-bugbear false positive | Already handled by `extend-immutable-calls` in `pyproject.toml` |

---

**Back to:** [00 · Index](00_INDEX.md)
