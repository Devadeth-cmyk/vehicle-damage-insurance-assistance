from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str = "Vehicle Damage Insurance AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./vehicle_insurance.db"

    SECRET_KEY: str = "CHANGE_THIS_SECRET_KEY"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    UPLOAD_DIR: str = "../uploads"
    GENERATED_DIR: str = "../generated"

    # ------------------------------------------------------------------
    # AI model weights.
    # Relative paths are resolved against the backend root folder (the one
    # containing `app/`), NOT the current working directory. The loader also
    # tries a few sensible fallbacks (see app/ai/model_loader.py).
    # ------------------------------------------------------------------
    DAMAGE_MODEL_PATH: str = "./models/damage/best.pt"
    PARTS_MODEL_PATH: str = "./models/parts/parts.pt"
    SEVERITY_MODEL_PATH: Optional[str] = "./models/severity/best.pt"

    # ------------------------------------------------------------------
    # Inference thresholds - identical to the validated pipeline
    # (backend.zip: 0.35 for damage / parts / severity).
    # ------------------------------------------------------------------
    # None -> use the Ultralytics default, exactly like the validated pipeline.
    IMG_SIZE: Optional[int] = None
    DAMAGE_CONF: float = 0.35
    PARTS_CONF: float = 0.35
    SEVERITY_CONF: float = 0.35

    # Default vehicle segment for the AI indicative repair range
    # (economy | mid-range | luxury).
    VEHICLE_SEGMENT_DEFAULT: str = "economy"

    MAX_UPLOAD_SIZE_MB: int = 20

    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,"
        "http://127.0.0.1:5175,http://127.0.0.1:3000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
