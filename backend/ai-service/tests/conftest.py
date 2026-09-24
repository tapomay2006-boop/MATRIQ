"""Shared fixtures.

Two rules the whole suite depends on:

  * **No network.** `Settings` reads .env, so a developer pointing
    VECTOR_STORE at a Qdrant Cloud cluster would otherwise turn every check in
    the API tests into a ~500 ms round-trip and make a green suite depend on
    someone else's uptime. The in-memory store is exact search over the same
    interface, so it is also the more honest default; Qdrant itself is covered
    by tests/test_qdrant_integration.py, which is opt-in precisely so the
    dependency is chosen rather than inherited.

  * **No model weights.** `EXTRACTION_ENABLED=false` keeps the 3B adapter out
    of the suite, and the embedding provider stays on the seeded hash. Both are
    the shipped defaults, so the tests exercise the configuration a fresh
    checkout actually runs.

Everything else is real: sessions, records, the abbreviation taxonomy, batches
and materials are all rows in the per-test SQLite database, so a test that
passes here exercises the same storage Postgres will.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture(scope="session", autouse=True)
def _hermetic() -> Any:
    """Keep the default suite off the network and off the GPU."""
    from app.config import settings
    from app.logic import retrieval
    from app.services import reranker

    original = (
        settings.vector_store,
        settings.extraction_enabled,
        settings.embedding_provider,
        settings.siamese_model_path,
    )
    settings.vector_store = os.getenv("TEST_VECTOR_STORE", "memory")
    settings.extraction_enabled = False
    settings.embedding_provider = "deterministic"
    # A checkpoint someone trained locally must not leak into the suite: the
    # search tests install their own reranker, and the default is "none".
    settings.siamese_model_path = "data/models/__no_such_checkpoint__"
    reranker.set_reranker(None)
    retrieval.get_store(refresh=True)
    yield
    (
        settings.vector_store,
        settings.extraction_enabled,
        settings.embedding_provider,
        settings.siamese_model_path,
    ) = original
    reranker.set_reranker(None)
    retrieval.get_store(refresh=True)


@pytest.fixture(scope="session", autouse=True)
def _jobs_run_inline() -> Any:
    """Let the API tests see job results without polling.

    The long-running endpoints answer 202 + a job id by default. That is the
    point of them, and tests/test_jobs.py exercises exactly that. Everywhere
    else the job machinery is incidental, so the default wait is raised and
    those endpoints answer 200 with the finished payload.
    """
    from app.config import settings

    original = settings.job_default_wait_seconds
    settings.job_default_wait_seconds = 60.0
    yield
    settings.job_default_wait_seconds = original


@pytest.fixture
def client(tmp_path) -> Any:
    """A TestClient on its own SQLite database and its own empty vector store."""
    import app.config as config_module
    import app.database as db_module
    import app.main as main_module
    from app.logic import retrieval

    config_module.settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"

    engine = create_async_engine(config_module.settings.database_url, future=True)
    db_module.engine = engine
    db_module.AsyncSessionLocal = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    main_module.engine = engine

    # A fresh store per test: the in-memory one is a process-wide singleton, so
    # without this every test would see the vectors the previous test added.
    retrieval.get_store(refresh=True)

    with TestClient(main_module.app) as test_client:
        yield test_client

    retrieval.get_store(refresh=True)


def standard_row(description: str, **overrides) -> dict[str, Any]:
    """One row in standard format, keyed exactly as Phase 1 emits it.

    `Item Code / Legacy Ref` defaults to a per-description value rather than a
    constant: material_id derives from (CPSE, legacy code), so a shared code
    would give two test rows the SAME id and the second would be reported as a
    duplicate of the first for the wrong reason.
    """
    row = {
        "Company": "NTPC",
        "Item Description (Raw)": description,
        "Item Code / Legacy Ref": f"M-{abs(hash(description)) % 100000}",
        "Quantity": 10,
        "UOM": "NOS",
        "Part Number / OEM Number": "NA",
        "Make / Brand": "NA",
        "Specifications / Dimensions": "NA",
    }
    row.update(overrides)
    return row
