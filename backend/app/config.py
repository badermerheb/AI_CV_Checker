from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str = ""
    # gemini-3.5-flash free tier caps at 20 requests/day; the lite model has
    # a far higher daily quota, which ingestion + evals need.
    gemini_model: str = "gemini-3.1-flash-lite"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""  # only needed for Qdrant Cloud


settings = Settings()
