#!/usr/bin/env python
"""Reindex materials from Postgres into Qdrant using the active embedding model.

    python scripts/reindex.py           # dry-run: prints what would be done
    python scripts/reindex.py --apply   # embeds and upserts vectors, updates Postgres

Deterministic point IDs (uuid5(material_id)) overwrite vectors in-place without
deleting the collection or points.
Refuses to run when the active provider is the deterministic fallback.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import update  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.logic.clock import utcnow  # noqa: E402
from app.logic.embedding import embedding_text, get_provider  # noqa: E402
from app.logic.retrieval import BlockingFilter, get_store  # noqa: E402
from app.models.material import Material  # noqa: E402
from app.services.indexing import build_points  # noqa: E402
from app.services.materials import load_materials  # noqa: E402

logger = logging.getLogger("reindex")


async def reindex(*, apply: bool = False, batch_size: int = 64) -> int:
    provider = get_provider()
    info = provider.info()

    if info.is_fallback:
        logger.error(
            "Refusing to reindex: active embedding provider is '%s' (fallback). "
            "Set EMBEDDING_PROVIDER=qwen3.",
            info.model_name,
        )
        return 1

    logger.info(
        "Provider: %s (version: %s, dimension: %d, device: %s)",
        info.model_name,
        info.model_version,
        info.dimension,
        settings.embedding_device,
    )
    logger.info("Store: %s (%s)", settings.vector_store, settings.qdrant_url)

    async with AsyncSessionLocal() as session:
        materials = await load_materials(session)

    if not materials:
        logger.warning("No materials found in Postgres to index.")
        return 0

    logger.info("Loaded %d materials from Postgres.", len(materials))

    if not apply:
        logger.info(
            "DRY-RUN: %d materials would be embedded with %s (%d-d) and upserted "
            "into '%s'. Pass --apply to execute.",
            len(materials),
            info.model_name,
            info.dimension,
            settings.qdrant_collection,
        )
        await engine.dispose()
        return 0

    logger.info("Embedding %d materials in batches...", len(materials))
    start_time = time.monotonic()
    points = build_points(materials, provider=provider)
    embed_duration = time.monotonic() - start_time
    logger.info("Embedded %d points in %.2fs.", len(points), embed_duration)

    store = get_store()
    logger.info(
        "Upserting %d points into collection '%s' (batch_size=%d)...",
        len(points),
        settings.qdrant_collection,
        batch_size,
    )
    upsert_start = time.monotonic()
    written = store.upsert(points, batch_size=batch_size)
    upsert_duration = time.monotonic() - upsert_start
    logger.info("Upserted %d points in %.2fs.", written, upsert_duration)

    logger.info("Updating Postgres material records...")
    now = utcnow()
    async with AsyncSessionLocal() as session:
        for point in points:
            await session.execute(
                update(Material)
                .where(Material.material_id == point.material_id)
                .values(
                    canonical_hash=point.canonical_hash,
                    embedding_version=point.embedding_version,
                    indexed_at=now,
                )
            )
        await session.commit()
    logger.info(
        "Updated %d Postgres rows with embedding version %s.",
        len(points),
        settings.embedding_version,
    )

    # Verification: query first material against the store
    test_material = materials[0]
    test_vector = provider.embed([embedding_text(test_material)], kind="document")[0]
    candidates = store.search(
        test_vector,
        top_k=5,
        block=BlockingFilter(embedding_version=settings.embedding_version),
    )

    if candidates and candidates[0].material_id == test_material.material_id:
        top_score = candidates[0].embedding_score
        logger.info(
            "Verification PASSED: %s retrieved at rank 1 with cosine=%.4f (expected ≈ 1.0)",
            test_material.material_id,
            top_score,
        )
        if top_score < 0.99:
            logger.warning(
                "Self-retrieval score %.4f is surprisingly low (<0.99). "
                "Please check index consistency.",
                top_score,
            )
    else:
        top_cand = candidates[0].material_id if candidates else "none"
        logger.error(
            "Verification FAILED: expected %s at rank 1, got %s",
            test_material.material_id,
            top_cand,
        )
        await engine.dispose()
        return 1

    await engine.dispose()
    logger.info("Reindex completed successfully in %.2fs total.", time.monotonic() - start_time)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--apply", action="store_true", help="execute reindex (default is dry-run)")
    parser.add_argument("--batch-size", type=int, default=64, help="upsert batch size (default 64)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    )

    return asyncio.run(reindex(apply=args.apply, batch_size=args.batch_size))


if __name__ == "__main__":
    sys.exit(main())

