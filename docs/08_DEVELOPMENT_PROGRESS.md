# 08 · Development Progress & Architectural Evolution

Smart India Hackathon 2026 · Problem Statement **26099**  
_AI-Driven Standardization and Harmonization of Material Codes Across CPSEs_  
Ministry of Petroleum & Natural Gas · Chennai Petroleum Corporation Limited (CPCL)

---

## 1. Executive Summary of Progress

This document records the engineering progress, architectural decisions, and verification results across the **Frontend (Next.js 16)**, **Backend AI Service (:8001)**, and **Backend API Service (:8000)** with **Neon PostgreSQL**.

| Subsystem | Previous State | Current Progress & Verified State | Primary Impact |
| :--- | :--- | :--- | :--- |
| **Frontend Database** | Direct MongoDB Atlas connection with unhandled `ECONNREFUSED` rejections | **Completely Removed from Frontend**: Zero DB dependencies on Next.js. Stateless JWT auth. | High stability, zero unhandled rejections, strict separation of concerns |
| **Backend Database** | Local Postgres stub or default container | **Neon Serverless PostgreSQL**: Automatic URL normalization (`postgresql+asyncpg://`), SSL enforcement, and connection pool recycling. | Cloud-native serverless PostgreSQL, scalable connection pooling |
| **Backend API Service (:8000)** | Disconnected routes, broken session engine, and missing material models | **Stabilized & Live**: Complete `materials_master` catalog, batch ingestion engine, robust connection pooling, 100% test pass rate. | Operational master material catalog with high-performance persistence |
| **`/upload` Route** | Scaffold with mock data, demo toggles, and artificial timeouts | **Live Ingestion Studio**: Directly connected to Qwen2.5-3B CPSE LoRA extraction, polling jobs, and vector duplicate checks. **Zero demo data**. | Real catalog ingestion, live model inference, CPSE schema standardization |
| **Visual Design & Typography** | Generic system fonts or distorted weights | **Consistent Signature Aesthetic**: Harmonized with landing page using `var(--font-heading)` (`Instrument_Serif` at `fontWeight: 400`) and lime-sage gradient accent. | Premium design, high readability, eliminates faux-bolding |


---

## 2. Frontend Modernization & `/upload` Studio

The `/upload` route (`frontend/app/upload/page.tsx`) has been transformed from a static UI into an interactive ingestion studio wired directly to `backend/ai-service` (`http://localhost:8001`).

### A. Live AI Service Integration
- **Batch CSV/Excel Ingestion**:
  - Endpoint: `POST /api/v1/extract/csv?wait=10`
  - Long-running jobs return HTTP `202 Accepted` with a `job_id`.
  - Real-time client polling (`GET /api/v1/extract/jobs/{job_id}`) visualizes row-by-row extraction progress.
  - Generates a review session (`session_id`) containing standardized canonical attributes.
- **Interactive Single-Item Playground**:
  - Endpoint: `POST /api/v1/extract/text`
  - Real-time attribute extraction for ad-hoc unstructured ERP strings.
  - Displays predicted canonical attributes with copy-to-clipboard JSON capabilities.
- **Vector Duplicate Detection**:
  - Endpoint: `POST /api/v1/standardized/check`
  - Checks extracted items against the indexed vector embeddings to flag duplicate or equivalent candidates.
- **Historical Session Browser**:
  - Endpoint: `GET /api/v1/extract/sessions`
  - Allows reloading previous extraction sessions for review.

### B. Strict Removal of Demo & Mock Data
- **Eliminated Simulated Fallbacks**:
  - Removed all fallback timeouts (`setTimeout`) and mock records (`MOCK_SIMULATED_RECORDS`).
  - Removed the "Demo Mode" toggle from the UI.
  - Buttons are disabled when the backend is offline or when no file is provided, with prominent status indicators guiding the user to start the backend (`python server.py`).
- **Clean Column Template**:
  - Replaced pre-filled sample rows with a clean, header-only CSV template download:
    ```csv
    Company,Item Code / Legacy Ref,Item Description (Raw),Quantity,UOM,Part Number / OEM Number,Make / Brand,Specifications / Dimensions
    ```
- **Blank Playground Initialization**:
  - Single-item playground starts with an empty input string (`""`) with an informative placeholder rather than dummy pre-filled text.

### C. Design & Typography Alignment
- Aligned typography strictly with the landing page design tokens:
  - Font: `var(--font-heading)` (`Instrument_Serif`)
  - Weight: Explicitly `400` (prevents browser faux-bold glyph distortion)
  - Color Accent: Gradient text using `linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)`.

---

## 3. Database Architecture Decoupling (Neon on Backend)

Direct database connections have been **completely excised from the Next.js frontend**, delegating all data persistence strictly to the backend services powered by **Neon PostgreSQL**.

### A. Frontend Database Removal
1. **Removed MongoDB Drivers & Config**:
   - Removed `MONGODB_URI` from `frontend/.env`.
   - Deleted `frontend/lib/mongodb.ts`.
   - Removed `"mongodb": "^7.6.0"` from `frontend/package.json`.
   - **Result**: Fixed the recurring `Unhandled Rejection: Error: querySrv ECONNREFUSED _mongodb._tcp.sih.k5fo2ag.mongodb.net` error during build and SSR.
2. **Stateless JWT NextAuth (`frontend/lib/auth.ts`)**:
   - Removed database operations from `signIn` callback.
   - Removed session persistence from `jwt` callback; session state is managed via secure, signed JWT tokens.
   - Credentials authorization delegates verification to the backend API (`http://localhost:8000/api/v1/users/login`).
3. **Backend-Delegated User Registration (`frontend/app/api/auth/register/route.ts`)**:
   - Proxies user registration requests to `POST ${NEXT_PUBLIC_API_URL}/api/v1/users` on the backend without any direct database queries in Next.js.

### B. Backend Neon PostgreSQL Support
1. **Automatic Connection Normalization (`backend/api-service/app/core/config.py`)**:
   - Added `parse_database_url` validator to automatically adapt raw Neon dashboard connection strings:
     - Normalizes `postgresql://` and `postgres://` to `postgresql+asyncpg://`.
     - Strips asyncpg-incompatible parameters (`sslmode`, `channel_binding`) from query strings to prevent driver crashes while maintaining SSL requirements.
   - Defaults cleanly to local verified database `postgresql+asyncpg://sih:sih@127.0.0.1:5432/numm_ai`.
2. **Dynamic SSL & Pool Resilience (`backend/api-service/app/db/session.py`)**:
   - Automatically injects `connect_args={"ssl": "require"}` whenever connecting to Neon (`neon.tech`) or any remote SSL PostgreSQL instance.
   - Configures connection pool recycling (`pool_pre_ping=True`, `pool_recycle=300`) to prevent dropped connection errors with serverless databases.
   - Supports transparent SQLite fallback (`connect_args={"check_same_thread": False}`) for testing and development.
3. **AI Service Adaptability (`backend/ai-service/app/config.py`)**:
   - `sqlalchemy_url` property and `sslmode` normalized to automatically accept Neon URLs and require SSL encryption.

---

## 4. Backend API Service & Master Material Catalog Architecture

The backend API service (`backend/api-service`, port `:8000`) acts as the central data gateway between the Next.js frontend, persistent PostgreSQL database, and AI microservices.

### A. Data Layer (`app/models/material.py` & `app/db/session.py`)
- **`Material` Entity (`materials_master`)**:
  - Implemented using SQLAlchemy 2.0 with platform-independent `Uuid` primary keys.
  - Comprehensive CPSE schema fields: `organization`, `legacy_code`, `description`, `uom`, `item_name`, `part_number`, `manufacturer`, `equipment_compatibility`, `material_type`, `category`, `specification`, `source_file`, `source_row`.
  - Composite indexing on `(organization, legacy_code)` for sub-millisecond lookups and deduplication.
  - Automatic table creation integrated into FastAPI's `lifespan` handler.

### B. Batch Ingestion Engine (`app/services/material_ingestion.py`)
- **`MaterialIngestionService.ingest_batch`**:
  - Supports streaming CSV (with UTF-8 BOM tolerance) and JSON array payloads.
  - Resilient column mapping accommodating both official CPSE nomenclature (`Item Description (Raw)`, `Item Code / Legacy Ref`, `Make / Brand`, etc.) and internal database fields.
  - Idempotent upsert logic updating existing records in-place without generating orphan duplicates.
  - Produces structured `MaterialIngestionResponse` tracking accepted, duplicate, and rejected records with line-numbered error items.

### C. Master Catalog API Endpoints (`app/api/routes/materials.py`)
- `POST /api/v1/materials/ingest`: Batch dataset upload with schema validation and persistence.
- `GET /api/v1/materials`: Multi-parameter paginated catalog browsing:
  - Dual pagination convention support (page/page_size and limit/offset).
  - Case-insensitive CPSE organization filtering.
  - Full-text keyword search across legacy codes, descriptions, item names, part numbers, manufacturers, and categories.
  - Deterministic sorting by `created_at DESC, id DESC`.
- `GET /api/v1/materials/organizations`: Returns distinct sorted list of CPSE organizations.
- `GET /api/v1/materials/quality`: Computes deterministic completeness metrics (missing UOM, missing manufacturer, missing part number, missing category).
- `GET /api/v1/materials/{material_id}`: Single material record retrieval.

---

## 5. System Verification & Test Status

All components across the repository have been systematically verified and pass all test suites:

### A. Frontend Verification
1. **TypeScript Compilation**:
   ```bash
   npx tsc --noEmit
   # Exit code: 0 (0 errors)
   ```
2. **Production Build**:
   ```bash
   npm run build
   # Exit code: 0 (All 14 static and dynamic routes compiled successfully)
   ```
3. **Database Decoupling**:
   - Confirmed `Unhandled Rejection: Error: querySrv ECONNREFUSED` completely eliminated.

### B. Backend API Service Verification (:8000)
1. **Automated Pytest Suite**:
   ```bash
   pytest tests/
   # ============================= 18 passed in 11.82s =============================
   # - tests/test_health.py (4 passed: liveness, services readiness, degraded fallbacks)
   # - tests/test_materials_master.py (12 passed: pagination, search, filters, quality, ingestion)
   # - tests/test_users.py (2 passed: user creation, duplicate conflicts)
   ```
2. **Live Service Health & Readiness**:
   ```bash
   GET http://127.0.0.1:8000/health
   # 200 OK -> {"status": "ok", "service": "api-service", "version": "0.1.0"}

   GET http://127.0.0.1:8000/health/services
   # 200 OK -> {"status": "ok", "dependencies": {"database": {"status": "healthy", "latency_ms": 4.11}}}

   GET http://127.0.0.1:8000/api/v1/materials
   # 200 OK -> {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 1}
   ```

### C. Backend AI Service Verification (:8001)
- Verified all 8 unit tests in `backend/ai-service` passed:
  - CMRL loss calculation, selective selector, buyer search, and health endpoints.
- Validated asyncpg timezone-safe naive UTC timestamps in job orchestration.

### D. Pipeline One Verification
- Fine-tuned Qwen2.5-3B CPSE LoRA adapter verified on CUDA RTX 3050 (2.03 GB VRAM).
- Live text extraction endpoint `/api/v1/extract/text` verified operational.

