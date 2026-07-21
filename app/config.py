from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://media_user:media_pass@localhost:5432/media_pipeline"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Analysis thresholds (tunable without code changes)
    blur_threshold: float = 100.0
    low_brightness_threshold: float = 50.0
    high_brightness_threshold: float = 220.0
    min_image_width: int = 320
    min_image_height: int = 240
    duplicate_hamming_distance: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
