import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

#: libpq SSL modes, weakest first. asyncpg accepts these strings directly.
SSL_MODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")

_SERVICE_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _SERVICE_DIR / ".env"

os.environ.setdefault("TRITON_CACHE_DIR", str(_SERVICE_DIR / ".cache" / "triton"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    project_name: str = "NUMM AI Service"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8001

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "numm_ai"
    db_user: str = "sih"
    db_password: str = "sih"
    db_ssl: bool = False
    db_sslmode: str = "prefer"
    db_echo: bool = False

    database_url: str | None = None
    """Full SQLAlchemy URL. Overrides the DB_* parts when set, which is how the
    tests point at SQLite and how a hosted Postgres is supplied as one string."""

    config_dir: str = "data/config"
    """Holds abbreviations.csv, the CPSE domain taxonomy the extraction engine
    expands against. The only reference data this service still carries."""

    # --- Phase 1: raw text -> standard format (the vendored LoRA) --------
    extraction_enabled: bool = False
    """Load the fine-tuned Qwen2.5-3B + qwen2.5-3b-cpse-lora-v2 adapter.

    OFF by default, exactly like EMBEDDING_PROVIDER=deterministic: the
    vector-DB half of this service runs, demos and passes every test with no
    model weights present, and GET /extract/info always reports which state is
    live so nothing can silently claim fine-tuned extraction it is not doing.

    On, the extraction endpoints work and need torch, transformers and peft."""

    lora_adapter_dir: str = "../pipeline-one/models/qwen2.5-3b-cpse-lora-v2"
    """Where the LoRA weights are.

    NOT copied into this service: the adapter is 195 MB and is already tracked
    under backend/pipeline-one/models/, so duplicating it would double the
    repository to no purpose. The extraction CODE is vendored
    (app/logic/extraction.py); the weights are referenced.

    For a standalone ai-service image, set this to
    data/models/qwen2.5-3b-cpse-lora-v2 and unzip the GitHub release there."""

    base_model_name: str = "Qwen/Qwen2.5-3B-Instruct"
    extraction_max_new_tokens: int = 256

    # --- Retrieval (docs/03 §5, docs/05) ---------------------------------
    embedding_provider: str = "deterministic"
    """'qwen3' loads Qwen/Qwen3-Embedding-0.6B (torch); 'deterministic' is the
    seeded-hash fallback that keeps CI fast and makes the pipeline runnable
    without model weights. GET /model/info always reports which is live, so a
    demo can never silently claim Qwen3 quality on fallback vectors."""

    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_version: str = "qwen3-0.6b-v1"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32
    embedding_device: str = "cpu"

    vector_store: str = "memory"
    """'qdrant' or 'memory'. Memory is exact search over the same interface -
    correct, just O(N), which is fine at this corpus size and in tests."""

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "material_embeddings"
    qdrant_timeout: float = 10.0

    qdrant_api_key: str = ""
    """Required by Qdrant Cloud, ignored by a local container. Sent as the
    `api-key` header. Keep it in .env - it is a bearer credential: anyone
    holding it can read and delete every vector in the cluster."""

    qdrant_prefer_grpc: bool = False
    """gRPC is faster for bulk upsert but needs port 6334 open. REST over 443
    is what works everywhere, so it stays the default."""
    hnsw_m: int = 16
    hnsw_ef_construct: int = 128

    ann_enabled: bool = True
    """Reported by GET /retrieval/model/info and /search/model/info. Search
    (POST /search) runs on top of this index."""

    # --- Search / harmonization (POST /search) ---------------------------
    search_top_k: int = 20
    """Candidates the vector store returns for one query. This is the whole
    pool the Siamese reranker sees; it never scores anything Qdrant did not
    surface first. Twenty is enough for a single article to be in the pool
    even when a general embedding ranks it behind a dozen look-alikes."""

    search_final_k: int = 5
    """Results returned by default. A caller may ask for up to `search_top_k`."""

    search_max_top_k: int = 100
    """Ceiling on the `top_k` a caller may request. Every candidate above it
    costs a Postgres row and a reranker forward, and past a hundred the tail
    is noise."""

    search_reranker_enabled: bool = True
    """Load the trained Siamese reranker for POST /search.

    On, and no checkpoint at SIAMESE_MODEL_PATH (or no torch), the search
    still answers - ordered by the Qdrant score, `siamese_score` null, and
    the response says the reranker was not applied. Off, the same, but by
    choice. Either way a result can never be a high-confidence match without
    the reranker: GET /search/model/info reports which state is live."""

    siamese_model_path: str = "data/models/siamese-cpse-v1"
    """A directory written by scripts/train_siamese.py: config.json, the
    backbone and the projection head. Not tracked in git - train it, or
    unpack a release."""

    siamese_base_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    """The pretrained encoder the reranker is fine-tuned from. Used by the
    TRAINING script only; a saved checkpoint carries its own copy and loads
    with no network. Deliberately not the retrieval model: Qwen3-Embedding is
    0.6 B parameters and builds the index; this is 22 M and reranks twenty
    candidates per query."""

    siamese_device: str = "cpu"
    siamese_batch_size: int = 64
    """Texts per forward pass. A query plus its candidates is one batch, so
    this only matters when top_k exceeds it."""

    search_qdrant_weight: float = 0.3
    search_siamese_weight: float = 0.7
    """final_score = qdrant_weight * qdrant_score + siamese_weight * siamese_score.

    Must sum to 1. Both are cosines but from different spaces, so they are on
    the same scale without being calibrated against each other - which is why
    the split is a setting. The default leans on the trained stage because
    that is what the evaluation (scripts/evaluate_search.py, README) found:
    the retrieval cosine separates families, the Siamese cosine separates
    articles within one."""

    search_match_threshold: float = 0.75
    """final_score at or above which a result is a HIGH-confidence match.
    Only reachable when the reranker ran; without it the best a result can be
    is `possible`.

    0.75 is what `scripts/evaluate_search.py --calibrate` found maximised
    match F1 on the reference corpus with the shipped weights (README,
    "Search"). It is a starting point, not a law: recalibrate on your own
    evaluation queries after every retrain, and after any change to the
    weights - the number belongs to the pair (model, weights) it was
    measured on."""

    search_possible_threshold: float = 0.55
    """final_score at or above which a result is a POSSIBLE match - shown, and
    left to a reviewer. Below it the result is returned with `match: false`
    so a caller can still see what the nearest thing was. On the reference
    corpus, near-miss articles (`V BELT C 125` against C-120) land between
    the two thresholds, and unrelated queries land below this one."""

    # --- Background jobs -------------------------------------------------
    max_concurrent_jobs: int = 2
    """How many background jobs may run at once.

    These are CPU- and memory-heavy whole-corpus operations. Running an
    unbounded number concurrently converts a slow service into an unavailable
    one, so the queue is deliberately shallow."""

    job_default_wait_seconds: float = 0.0
    """Seconds a submitting endpoint waits inline before returning 202.

    0 means every heavy endpoint answers immediately with a job id. Raise it
    (a few seconds) if the clients are interactive and most jobs are small:
    a job that finishes inside the window is returned as a 200 with its result,
    and anything slower degrades to the 202 + poll path automatically."""

    job_max_wait_seconds: float = 60.0
    """Ceiling on the `wait` query parameter, whatever a caller asks for."""

    top_k: int = 10
    """Reported by GET /retrieval/model/info. POST /search uses SEARCH_TOP_K."""

    existence_threshold: float = 0.90
    """Cosine above which an incoming standardized row is judged to ALREADY
    EXIST in the vector embedding DB (POST /standardized/check).

    The one tunable that decides what enters the master. Too low and genuinely
    new material is silently dropped as a duplicate; too high and the index
    fills with re-uploads of the same article. 0.90 is deliberately strict:
    holding a real duplicate back costs a re-check, admitting one costs a
    reviewer."""

    national_id_prefix: str = "NMM"
    """The prefix on every national material id: NMM-00000001.

    Configuration for the *next* id issued. An id already on a row keeps the
    form it was issued in - it is an identifier, and identifiers do not change
    because a setting did."""

    national_id_digits: int = 8
    """Zero-padded width of the sequence part. Eight digits is ~100 million
    materials, and fixed width is what makes the ids sort correctly as strings."""

    existence_block_by_category: bool = False
    """Constrain the duplicate check to the incoming row's material family.

    OFF by default, and the default is the important part. Blocking narrows the
    ANN traversal, but a row the keyword table put in the wrong family would
    then never be compared against its own duplicate - and a missed duplicate
    is the failure this endpoint exists to prevent. An unblocked HNSW search is
    sublinear, so the speedup is real but secondary.

    Turn it on when the corpus is large enough for the scan to cost something
    AND the table in logic/category.py has earned trust on your data. Rows that
    classify UNCLASSIFIED are never blocked either way."""

    batch_retention_days: int = 7
    """How long a batch that was checked but never added is kept.

    A check stages its new rows in the batch so `add` writes what this service
    judged rather than what a client hands back. A batch nobody acted on is a
    preview that was abandoned, and it holds a full copy of every row it
    judged - so it is pruned rather than kept forever. Batches that WERE added
    are never pruned: they are the audit trail, and they are small, because the
    staged copy is dropped once the rows are in `material`.

    0 disables pruning."""

    existence_top_k: int = 5
    """Neighbours fetched per incoming row during the existence check. Only the
    best one can decide, but a short list makes the response explainable."""

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            url = self.database_url.strip()
            if url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://") :]
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://") :]
            if "sslmode=require" in url:
                url = url.replace("sslmode=require", "ssl=require")
            return url
        credentials = f"{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
        return (
            f"postgresql+asyncpg://{credentials}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sslmode(self) -> str:
        """DB_SSLMODE decides; DB_SSL=true or Neon connection raises anything weaker to 'require'."""
        """DB_SSLMODE decides; DB_SSL=true or Neon connection raises weaker to 'require'."""
        if self.database_url and ("neon.tech" in self.database_url or "ssl=" in self.database_url):
            return "require"
        mode = self.db_sslmode.strip().lower()
        if mode not in SSL_MODES:
            raise ValueError(f"DB_SSLMODE must be one of {SSL_MODES}, got {mode!r}")
        if self.db_ssl and mode in ("disable", "allow", "prefer"):
            return "require"
        return mode

    @property
    def connect_args(self) -> dict[str, object]:
        if self.sqlalchemy_url.startswith("sqlite"):
            return {}
        return {"ssl": self.sslmode}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def configure_logging() -> None:
    """Send app logs to stdout; DEBUG level when settings.debug is on."""
    level = logging.DEBUG if settings.debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
