from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # secrets come only from the environment / .env; there is no usable default key
    api_key: str = ""
    database_url: str = "sqlite:///./data/forte.db"
    # "rq" uses Redis + a separate worker process; "thread" runs jobs inside the API (no Redis needed)
    queue_mode: str = "thread"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "./data/storage"
    max_upload_mb: int = 500
    max_video_sec: int = 600
    job_timeout_sec: int = 290  # jury limit is 300 s per video
    model_version: str = "rtdetr-r18-rules-1.0"
    # rate limit for POST /api/v1/analyze, per API key + client IP
    rate_limit_per_min: int = 20
    # extra origins allowed by CORS; empty = same origin only
    cors_origins: str = ""
    # load demo desks / employees / shifts on first start
    seed_demo: bool = True


settings = Settings()

if len(settings.api_key) < 16 or settings.api_key.startswith("change-me"):
    raise RuntimeError("API_KEY must be set in .env (at least 16 characters, not the example value)")
