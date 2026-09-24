"""Application entry point: builds the FastAPI app and wires the routes in."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text

from app.config import configure_logging, settings
from app.database import AsyncSessionLocal, Base, engine
from app.logic.retrieval import get_store
from app.models import *  # noqa: F401,F403  - register mappers before create_all
from app.routes import (
    extraction,
    health,
    jobs,
    materials,
    retrieval,
    search,
    standardized,
)
from app.services.jobs import reap_orphans, run_blocking
from app.services.materials import load_materials
from app.services.standardized import _index
from app.services.taxonomy import sync_to_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # The LoRA adapter is NOT loaded here. Extraction weights load on first use
    # (services/extraction.py), so this service still boots in a second and a
    # machine with no GPU fails the one request that needs one rather than
    # failing to start at all.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    # Jobs live in this process, so anything still marked RUNNING belongs to a
    # process that no longer exists. Fail those rows now rather than leave a
    # caller polling a task that will never finish.
    await reap_orphans()

    # The abbreviation taxonomy is baseline (curated defaults + the shipped
    # CSV) plus whatever has been added at runtime. Applying the stored layer
    # here is what makes every worker expand the same text: it used to live in
    # a module-level dict, so an addition reached one worker and no other.
    async with AsyncSessionLocal() as db:
        await sync_to_engine(db)

        # Clean vector store and ensure ONLY assigned materials exist in the vector DB
        try:
            store = get_store()
            if hasattr(store, "_points"):
                store._points.clear()
            else:
                store.ensure_collection(dimension=1024, recreate=True)

            all_materials = await load_materials(db)
            assigned_materials = [
                m for m in all_materials if m.national_id and str(m.national_id).strip()
            ]

            # Mark unassigned materials as awaiting indexing in PostgreSQL
            await db.execute(
                text("UPDATE material SET indexed_at = NULL, canonical_hash = NULL, embedding_version = NULL WHERE national_id IS NULL OR TRIM(national_id) = ''")
            )
            await db.commit()

            if assigned_materials:
                logger.info(
                    "Indexing %d assigned materials (NMM-*) into clean vector store...",
                    len(assigned_materials),
                )
                await _index(db, assigned_materials)
                await db.commit()
                logger.info(
                    "Clean vector store populated successfully with %d assigned points.",
                    len(assigned_materials),
                )
        except Exception as err:
            logger.warning("Vector store clean & sync on boot failed: %s", err)

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.project_name, version="0.1.0",
    docs_url="/docs", openapi_url="/openapi.json", lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(health.router, prefix=settings.api_v1_prefix)

# The order of the two /materials-adjacent routers matters: `materials` owns
# /{material_id}, which would otherwise swallow any literal path mounted after
# it, so every literal route on that prefix is declared before it in the file.
#
# No authentication dependency anywhere: api-service owns that, and every
# endpoint here is callable by any caller that can reach the port. THE SECURITY
# BOUNDARY IS THE NETWORK.
#
# The routers are the stages of the service, in order:
#
#   extraction    raw text or a raw file -> the standard format   (Phase 1)
#   standardized  standard format -> what is new -> the vector DB (the boundary)
#   materials     the master, read side
#   retrieval     the vector index itself
#   search        a query -> the index -> the Siamese reranker -> matches
for module in (extraction, standardized, materials, retrieval, search, jobs):
    app.include_router(module.router, prefix=settings.api_v1_prefix)
