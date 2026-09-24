# MATRIQ App Startup README

This guide is for running the local SIH-2026/MATRIQ stack on Windows.

## Services

| Service | Folder | Port | Purpose |
| --- | --- | ---: | --- |
| Frontend | `frontend` | `3000` | Next.js UI and NextAuth login |
| API service | `backend/api-service` | `8000` | Users, auth, material catalog API, frontend backend |
| AI service | `backend/ai-service` | `8001` | Extraction, duplicate check, search, vector/index APIs |
| PostgreSQL | Docker or local install | `5432` | Stores users/materials/jobs/sessions |
| Qdrant | Docker or cloud | `6333` | Vector store for AI search/indexing |

The frontend calls both:

- `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_AI_SERVICE_URL=http://localhost:8001`

## Default Local Passwords

These are development defaults only. Do not use them in production.

| Thing | Default |
| --- | --- |
| Postgres user | `sih` |
| Postgres password | `sih` |
| Postgres database from Docker Compose | `sih` |
| AI service database name | `numm_ai` |
| API JWT secret | `change-me-in-production` |
| NextAuth secret | `change-me-to-a-secure-random-string` |

There is no fixed app login password checked into the repo. Create a user from the signup page, or use the development fallback below.

## Development Login

Real login path:

1. Start PostgreSQL.
2. Start `api-service`.
3. Open `http://localhost:3000/auth/signup`.
4. Register with any email and a password of at least 6 characters.
5. Login at `http://localhost:3000/auth/login`.

Development fallback:

If `api-service` is offline or unreachable, the frontend credentials provider allows any email with any password of at least 6 characters.

Role selection in fallback mode:

- Email containing `national`, `director`, or `ministry` becomes `national_admin`.
- Any other email becomes `cpse_admin`.

Example fallback users:

- `national@test.local` / `password123`
- `cpse@test.local` / `password123`

Google login needs real local env values:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

## One-Time Setup

Run these from the repo root:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\api-service\requirements-dev.txt
pip install -r backend\ai-service\requirements-dev.txt
cd frontend
npm install
```

Optional ML dependencies for full extraction/Qwen model support:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
.\.venv\Scripts\Activate.ps1
pip install -r backend\ai-service\requirements-ml.txt
```

The app can still run without the optional ML packages. In that mode extraction may report that the LoRA model is disabled/unavailable.

## Environment Files

Create env files before running the stack.

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
Copy-Item .env.example .env -ErrorAction SilentlyContinue
Copy-Item backend\api-service\.env.example backend\api-service\.env -ErrorAction SilentlyContinue
Copy-Item backend\ai-service\.env.example backend\ai-service\.env -ErrorAction SilentlyContinue
Copy-Item frontend\.env.example frontend\.env.local -ErrorAction SilentlyContinue
```

Recommended `frontend\.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_AI_SERVICE_URL=http://localhost:8001
AUTH_SECRET=change-me-to-a-secure-random-string
NEXTAUTH_URL=http://localhost:3000
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

Recommended `backend\api-service\.env`:

```env
PROJECT_NAME="sih-2026 api-service"
ENVIRONMENT=development
DEBUG=true
API_V1_PREFIX=/api/v1
HOST=0.0.0.0
PORT=8000
DATABASE_URL=postgresql+asyncpg://sih:sih@localhost:5432/sih
SECRET_KEY=change-me-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
AI_SERVICE_URL=http://localhost:8001
AI_SERVICE_TIMEOUT=60.0
CORS_ORIGINS=["http://localhost:3000"]
```

Recommended local-demo `backend\ai-service\.env`:

```env
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8001
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=numm_ai
DB_USER=sih
DB_PASSWORD=sih
DB_SSL=false
DB_SSLMODE=prefer
EXTRACTION_ENABLED=false
LORA_ADAPTER_DIR=../pipeline-one/models/qwen2.5-3b-cpse-lora-v2
EMBEDDING_PROVIDER=deterministic
EMBEDDING_DIMENSION=1024
VECTOR_STORE=memory
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=material_embeddings
SEARCH_RERANKER_ENABLED=true
SIAMESE_MODEL_PATH=data/models/siamese-cpse-v1
```

Note: the current `frontend\.env.example` and `backend\ai-service\.env.example` contain visible merge separator text near the bottom. If you copy them manually, remove any separator lines such as `-----------------` before running the app.

## Start With Docker Infrastructure

Use Docker for PostgreSQL and Qdrant:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
docker compose up -d postgres qdrant
```

Check containers:

```powershell
docker compose ps
```

## Start Each Service

Open three PowerShell terminals.

Terminal 1: API service

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
.\.venv\Scripts\Activate.ps1
cd backend\api-service
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2: AI service

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
.\.venv\Scripts\Activate.ps1
cd backend\ai-service
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Terminal 3: Frontend

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026\frontend
npm run dev
```

## URLs

| URL | What it is |
| --- | --- |
| `http://localhost:3000` | Frontend |
| `http://localhost:3000/auth/login` | Login |
| `http://localhost:3000/auth/signup` | Signup |
| `http://localhost:8000/docs` | API service Swagger |
| `http://localhost:8001/docs` | AI service Swagger |
| `http://localhost:8000/health` | API service health |
| `http://localhost:8001/health` | AI service health |
| `http://localhost:8001/api/v1/retrieval/status` | AI index/vector status |
| `http://localhost:8001/api/v1/search/model/info` | AI search model status |

## Full Docker Compose Option

To run the full stack through Docker:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
docker compose up --build
```

Stop it:

```powershell
docker compose down
```

This is convenient, but for active frontend/backend development the three-terminal local mode is usually easier to debug.

## Common Checks

Check API service:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
```

Check AI service:

```powershell
curl http://localhost:8001/health
curl http://localhost:8001/api/v1/extract/info
curl http://localhost:8001/api/v1/retrieval/model/info
```

Check frontend env from behavior:

- If login always uses fallback, `api-service` is probably offline or `NEXT_PUBLIC_API_URL` is wrong.
- If upload/review AI actions fail, `ai-service` is probably offline or `NEXT_PUBLIC_AI_SERVICE_URL` is wrong.
- If material catalog pages are empty, confirm `api-service` can reach PostgreSQL and that materials have been ingested.

## Route Summary

API service on `:8000`:

- `GET /health`
- `GET /api/v1/health`
- `POST /api/v1/users`
- `POST /api/v1/users/login`
- `POST /api/v1/users/oauth`
- `GET /api/v1/users`
- `GET /api/v1/materials`
- `GET /api/v1/materials/organizations`
- `GET /api/v1/materials/quality`
- `POST /api/v1/materials/ingest`
- `POST /api/v1/materials/ingest/batch`

AI service on `:8001`:

- `GET /health`
- `GET /api/v1/health`
- `GET /api/v1/extract/info`
- `POST /api/v1/extract/text`
- `POST /api/v1/extract/csv`
- `GET /api/v1/extract/jobs/{job_id}`
- `GET /api/v1/extract/sessions`
- `GET /api/v1/extract/sessions/{session_id}`
- `PUT /api/v1/extract/records/{session_id}/{record_id}`
- `POST /api/v1/standardized/check`
- `POST /api/v1/standardized/add`
- `GET /api/v1/standardized/batches`
- `GET /api/v1/materials`
- `GET /api/v1/retrieval/status`
- `GET /api/v1/retrieval/model/info`
- `POST /api/v1/search`
- `GET /api/v1/search/model/info`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/cancel`

## Troubleshooting

Port already in use:

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :8001
netstat -ano | findstr :3000
```

Missing Python package:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
.\.venv\Scripts\Activate.ps1
pip install -r backend\api-service\requirements-dev.txt
pip install -r backend\ai-service\requirements-dev.txt
```

Database connection fails:

- Confirm Docker Postgres is running: `docker compose ps postgres`.
- Confirm `DATABASE_URL` in `backend\api-service\.env`.
- Confirm `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in `backend\ai-service\.env`.
- Docker Compose creates the `sih` database by default. The AI service expects `numm_ai`; the compose init script creates it for the AI service.

AI extraction says unavailable:

- This is expected when `EXTRACTION_ENABLED=false`.
- Install ML requirements and set `EXTRACTION_ENABLED=true` only when you want to run the LoRA extraction model locally.
- The LoRA adapter path should point to `backend\pipeline-one\models\qwen2.5-3b-cpse-lora-v2`.

Qdrant/search issues:

- For simple demos, `VECTOR_STORE=memory` works without Qdrant.
- For persistent vector search, run Qdrant and set `VECTOR_STORE=qdrant`.
- Local Qdrant URL is `http://127.0.0.1:6333`.

## Quick Happy Path

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
docker compose up -d postgres qdrant

.\.venv\Scripts\Activate.ps1
cd backend\ai-service
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

In a second terminal:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026
.\.venv\Scripts\Activate.ps1
cd backend\api-service
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In a third terminal:

```powershell
cd C:\Users\rakes\OneDrive\Desktop\sih-2026\frontend
npm run dev
```

Then open:

```text
http://localhost:3000
```
