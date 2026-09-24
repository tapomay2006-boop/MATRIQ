from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.ai_client import ai_client

router = APIRouter(prefix="/ai", tags=["ai"])


class InferenceRequest(BaseModel):
    prompt: str
    metadata: dict[str, Any] = {}


@router.post("/infer")
async def infer(payload: InferenceRequest) -> dict[str, Any]:
    try:
        return await ai_client.infer(payload.model_dump())
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="ai-service unavailable"
        ) from exc
