# SIH 2026 Unified Material Intelligence Platform — Architecture & Phase 0 Guide

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js)                   │
│   Port: 3000                                                │
│   Auth: NextAuth (JWT sessions, MongoDB Atlas, Google OAuth)│
│   API Client: lib/api/client.ts                             │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP (/api/v1/...)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 API Service (FastAPI)                       │
│   Port: 8000                                                │
│   Responsibilities: Gateway, Validation, DB, Orchestration │
│   Database: PostgreSQL / SQLAlchemy / Alembic               │
│   AI Client: app/services/ai_client.py                      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Internal HTTP (/api/v1/...)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 AI Service (FastAPI)                        │
│   Port: 8001                                                │
│   Responsibilities: Embeddings, Similarity, Classification  │
│   Ownership: AI/ML Teammates (Read-Only / Untouched)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Service Responsibilities & Boundaries

| Service | Technology | Port | Core Responsibilities |
| :--- | :--- | :--- | :--- |
| **Frontend** | Next.js 16 (App Router, Turbopack) | `3000` | Landing page, user authentication, UI routing, centralized API client (`lib/api/client.ts`), and domain views (`/dashboard`, `/materials`, `/matching`, `/reviews`, `/analytics`). |
| **API Service** | Python 3.13 / FastAPI | `8000` | API routing under `/api/v1/`, request validation via Pydantic, database persistence via SQLAlchemy/Alembic, orchestration with `ai_client.py`, standard error handling, and health probes. |
| **AI Service** | Python 3.13 / FastAPI | `8001` | ML inference engine, embedding extraction, and similarity computation. Owned by AI/ML teammates. |

---

## 3. Environment Variables

### Root / Global (`.env.example`)
- `API_SERVICE_PORT=8000`
- `AI_SERVICE_PORT=8001`
- `FRONTEND_PORT=3000`

### Frontend (`frontend/.env.local` / `frontend/.env.example`)
- `NEXT_PUBLIC_API_URL`: Base URL of the API Service (e.g. `http://localhost:8000`)
- `AUTH_SECRET`: NextAuth session encryption secret
- `NEXTAUTH_URL`: Canonical URL for auth callbacks (`http://localhost:3000`)
- `MONGODB_URI`: MongoDB connection URI for user/session storage
- `GOOGLE_CLIENT_ID`: Google OAuth 2.0 client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth 2.0 client secret

### API Service (`backend/api-service/.env.example`)
- `PROJECT_NAME`: Service display name
- `ENVIRONMENT`: Runtime environment (`development`, `production`)
- `DEBUG`: Boolean flag for debug logging
- `PORT`: Service port (`8000`)
- `DATABASE_URL`: Async SQLAlchemy PostgreSQL connection string
- `AI_SERVICE_URL`: Base URL of the AI Service (`http://localhost:8001`)
- `AI_SERVICE_TIMEOUT`: AI request timeout in seconds (default: `60.0`)
- `CORS_ORIGINS`: Allowed CORS origins JSON list (e.g. `["http://localhost:3000"]`)

---

## 4. Health Endpoints

### API Service (`http://localhost:8000`)
- **`GET /health`** or **`GET /api/v1/health`**:
  Basic liveness probe confirming API service is running.
  ```json
  {
    "status": "ok",
    "service": "api-service",
    "version": "0.1.0",
    "environment": "development"
  }
  ```
- **`GET /api/v1/health/services`**:
  Deep readiness probe inspecting database connectivity (`SELECT 1`) and AI service connectivity (`ai_client.check_health()`). If AI service or database is offline, returns a meaningful degraded/unavailable status code without crashing.
  ```json
  {
    "status": "healthy",
    "service": "api-service",
    "version": "0.1.0",
    "environment": "development",
    "dependencies": {
      "database": {
        "status": "healthy",
        "latency_ms": 2.15
      },
      "ai_service": {
        "status": "healthy",
        "latency_ms": 4.82
      }
    }
  }
  ```

---

## 5. Development & Testing Commands

### Run API Service
```bash
cd backend/api-service
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Frontend
```bash
cd frontend
npm run dev
```

### Run Tests
- **API Service Unit Tests**:
  ```bash
  cd backend/api-service
  pytest tests/
  ```
- **Frontend Build & Type Check**:
  ```bash
  cd frontend
  npm run build
  ```

