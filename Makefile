.PHONY: help install install-frontend install-api install-ai install-ml dev dev-frontend dev-api dev-ai test test-api test-ai lint format up down logs clean extract-info model-info index-status

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-frontend install-api install-ai ## Install every workspace

install-frontend: ## Install frontend dependencies
	cd frontend && npm install

install-api: ## Create api-service venv and install dependencies
	cd backend/api-service && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

install-ai: ## Create ai-service venv and install dependencies
	cd backend/ai-service && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

install-ml: ## Add the LoRA extractor + Qwen3 embeddings to ai-service (several GB; optional)
	cd backend/ai-service && .venv/bin/pip install -r requirements-ml.txt

dev-frontend: ## Run the Next.js dev server
	cd frontend && npm run dev

dev-api: ## Run api-service with reload
	cd backend/api-service && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-ai: ## Run ai-service (extraction + vector DB) with reload
	cd backend/ai-service && .venv/bin/uvicorn app.main:app --reload --port 8001

test: test-api test-ai ## Run every backend test suite

test-ai: ## Run ai-service tests
	cd backend/ai-service && .venv/bin/pytest

test-api: ## Run api-service tests
	cd backend/api-service && .venv/bin/pytest

lint: ## Lint every workspace
	cd frontend && npm run lint
	cd backend/api-service && .venv/bin/ruff check .
	cd backend/ai-service && .venv/bin/ruff check .

format: ## Format the Python workspaces
	cd backend/api-service && .venv/bin/ruff format .
	cd backend/ai-service && .venv/bin/ruff format .

up: ## Start the full stack with Docker Compose
	docker compose up --build

down: ## Stop the stack
	docker compose down

logs: ## Tail Docker Compose logs
	docker compose logs -f

index-status: ## Index completeness and store connectivity
	cd backend/ai-service && .venv/bin/python -c "import httpx; print(httpx.get('http://localhost:8001/api/v1/retrieval/status', timeout=30).json())"

extract-info: ## Show whether the LoRA adapter is loaded, and from where
	cd backend/ai-service && .venv/bin/python -c "import httpx; print(httpx.get('http://localhost:8001/api/v1/extract/info', timeout=30).json())"

model-info: ## Show which embedding provider is actually live
	cd backend/ai-service && .venv/bin/python -c "import httpx; print(httpx.get('http://localhost:8001/api/v1/retrieval/model/info', timeout=30).json())"

clean: ## Remove build and cache artefacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	rm -rf frontend/.next
