FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt only: this image runs the vector half. Phase 1 needs torch,
# transformers and peft (requirements-ml.txt, several GB), so EXTRACTION_ENABLED
# stays false here and /extract/* answers 503 saying exactly that.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# The LoRA weights are NOT in this image. They are 195 MB and live in the
# backend/pipeline-one checkout, which compose mounts read-only at
# /srv/data/raw; LORA_ADAPTER_DIR points there. To build a self-contained
# extraction image, install requirements-ml.txt above and COPY the unzipped
# adapter into data/models/qwen2.5-3b-cpse-lora-v2.
COPY . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8001/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
