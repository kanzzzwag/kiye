from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str = "change-me"
    database_url: str = "sqlite:///./data/forte.db"
    # "rq" uses Redis + a separate worker process; "thread" runs jobs inside the API (no Redis needed)
    queue_mode: str = "thread"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "./data/storage"
    max_upload_mb: int = 500
    max_video_sec: int = 600
    job_timeout_sec: int = 270  # jury limit is 300 s
    model_version: str = "stub-0.1"

    class Config:
        env_file = ".env"


settings = Settings()
