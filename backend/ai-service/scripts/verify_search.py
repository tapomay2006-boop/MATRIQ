#!/usr/bin/env python
"""Verify GET /search/model/info and POST /search for the 10 target queries."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

QUERIES = [
    "M-55321",
    "NTPC-M55321",
    "C-120",
    "V BELT",
    "V BELT C 120",
    "a belt that is c-120",
    "industrial V belt C section approximately 120 inch used for power transmission",
    "M-55321 V BELT C 120",
    "V BELT C 125",
    "some completely unrelated material",
]


async def run():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=60.0
    ) as client:
        print("=" * 80)
        print("1. GET /api/v1/search/model/info")
        print("=" * 80)
        resp = await client.get("/api/v1/search/model/info")
        assert resp.status_code == 200, f"Failed: {resp.status_code} {resp.text}"
        info = resp.json()
        print(json.dumps(info, indent=2))

        print("\n" + "=" * 80)
        print("2. POST /api/v1/search for 10 Target Queries")
        print("=" * 80)

        for i, q in enumerate(QUERIES, 1):
            print(f"\n[{i}/10] Query: {q!r}")
            res = await client.post("/api/v1/search", json={"query": q, "top_k": 20, "final_k": 5})
            assert res.status_code == 200, f"Query failed {q}: {res.status_code} {res.text}"
            data = res.json()
            pipeline = data.get("pipeline", {})
            results = data.get("results", [])

            print(f"  Best match level: {data.get('best_match_level')}")
            print(f"  Total candidates: {data.get('total_candidates')}")
            print(
                f"  Pipeline: vector_ran={pipeline.get('vector_search_ran')} "
                f"reranker_applied={pipeline.get('reranker_applied')} "
                f"degraded={pipeline.get('degraded')}"
            )
            if pipeline.get("identifiers"):
                print(f"  Identifiers detected: {pipeline.get('identifiers')}")

            if not results:
                print("  NO RESULTS RETURNED")
                continue

            for rank, hit in enumerate(results[:3], 1):
                qd = (
                    f"{hit['qdrant_score']:.4f}"
                    if hit.get("qdrant_score") is not None
                    else "null"
                )
                sm = (
                    f"{hit['siamese_score']:.4f}"
                    if hit.get("siamese_score") is not None
                    else "null"
                )
                print(
                    f"  Rank {rank}: {hit['material_id']} | "
                    f"final={hit['final_score']:.4f} | "
                    f"qdrant={qd} | "
                    f"siamese={sm} | "
                    f"level={hit['match_level']} | "
                    f"source={hit['match_source']} | "
                    f"matched_by={hit['matched_by']}"
                )
                print(f"          Desc: {hit['description']}")
                if hit.get("identifier_match"):
                    print(
                        f"          Ident Match: token={hit.get('identifier_token')} "
                        f"field={hit.get('identifier_matched_field')}"
                    )


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
