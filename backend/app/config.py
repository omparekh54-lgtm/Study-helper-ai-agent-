"""Application settings, loaded from environment variables (and a local .env in development)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core -----------------------------------------------------------------
    app_name: str = "StudyForge API"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./studyforge.db"

    # Comma-separated list of allowed browser origins, plus a regex for preview deployments.
    frontend_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    frontend_origin_regex: str = r"https://.*\.vercel\.app"

    # --- LLM providers ----------------------------------------------------------
    # "live" uses Gemini + Groq; "fake" uses a deterministic offline generator (tests / demos).
    llm_mode: str = "live"
    gemini_api_key: str = ""
    # Tried in order. Unavailable models are skipped automatically, and a model that runs out
    # of free quota hands over to the next one (each model has its own free-tier bucket).
    gemini_models: str = (
        "gemini-3.6-flash,gemini-flash-latest,gemini-3.5-flash,"
        "gemini-3.6-flash-lite,gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-2.5-flash-lite"
    )
    gemini_rpm: int = 5  # per model (free-tier Flash allows ~5 requests/minute each)
    # Gemini 3 "thinking" depth: minimal | low | medium | high ("" = model default). Low is much faster.
    gemini_thinking: str = "low"
    groq_api_key: str = ""
    groq_models: str = "openai/gpt-oss-120b,openai/gpt-oss-20b"
    groq_rpm: int = 25
    groq_tpm: int = 7500

    # --- Optional integrations ------------------------------------------------
    youtube_api_key: str = ""

    # --- Limits -----------------------------------------------------------------
    max_upload_mb: int = 20
    max_pages: int = 400
    max_chars: int = 450_000
    uploads_per_ip_per_hour: int = 6

    # --- Video ------------------------------------------------------------------
    # Videos are made automatically once a document's study kits are all ready (so they never slow
    # the kits down); a user asking for one on a topic page jumps the queue.
    auto_generate_videos: bool = True
    # How many topics are written in parallel (each goes to a different Gemini model).
    topic_concurrency: int = 3
    tts_voice: str = "en-US-AndrewNeural"
    video_width: int = 1280
    video_height: int = 720

    # --- Render keep-alive ----------------------------------------------------------
    # Render sets RENDER_EXTERNAL_URL automatically. While jobs are running we ping ourselves
    # so the free instance doesn't spin down mid-job.
    render_external_url: str = Field(default="", alias="RENDER_EXTERNAL_URL")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origins.split(",") if o.strip()]

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    @property
    def groq_model_list(self) -> list[str]:
        return [m.strip() for m in self.groq_models.split(",") if m.strip()]

    @property
    def is_fake_llm(self) -> bool:
        return self.llm_mode.lower() == "fake"


@lru_cache
def get_settings() -> Settings:
    return Settings()
