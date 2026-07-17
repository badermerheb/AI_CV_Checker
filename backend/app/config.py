from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str = ""
    # gemini-3.5-flash free tier caps at 20 requests/day; the lite model has
    # a far higher daily quota, which ingestion + evals need.
    gemini_model: str = "gemini-3.1-flash-lite"
    # Judge for RAGAS evals. Older models (gemini-2.0-flash) now have ZERO free-tier
    # quota, so the judge shares the lite model; its daily quota covers both.
    ragas_judge_model: str = "gemini-3.1-flash-lite"

    # Retrieval pipeline (the API serves the full pipeline; evals override these)
    retrieval_mode: str = "hybrid"  # "dense" | "hybrid"
    rerank: bool = True
    routing: bool = True
    fetch_k: int = 20  # candidates fetched before reranking
    # MiniLM reranks 20 pairs ~10x faster than BAAI/bge-reranker-base on CPU with
    # comparable top-5 quality on this corpus; set RERANK_MODEL to swap.
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""  # only needed for Qdrant Cloud

    # Comma-separated origins allowed by CORS (the deployed frontend's URL in prod).
    allowed_origins: str = "http://localhost:5173"

    # Postgres connection string (Neon/Supabase). Empty = local SQLite fallback,
    # so dev needs zero setup.
    database_url: str = ""

    # The shared read-only "demo" workspace: uploads to it are rejected unless
    # this is set (used only when seeding the demo corpus).
    allow_demo_writes: bool = False


settings = Settings()
