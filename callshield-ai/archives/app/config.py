from pydantic_settings import BaseSettings
from functools import lru_cache


class Config(BaseSettings):
    APP_NAME: str = "CallShield AI"
    APP_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Audio settings
    TARGET_SR: int = 16000
    CHUNK_DURATION_S: float = 2.0
    VAD_AGGRESSIVENESS: int = 2

    # Model paths (will download on first use if needed)
    DEEPFAKE_MODEL: str = "speechbrain/anti-spoofing-AASIST"
    SPEAKER_MODEL: str = "speechbrain/embedding-comparison"
    WHISPER_MODEL: str = "base"

    # Risk thresholds
    RISK_LOW_THRESHOLD: float = 35.0
    RISK_MEDIUM_THRESHOLD: float = 65.0

    # Scoring weights
    WEIGHT_DEEPFAKE: float = 0.40
    WEIGHT_SCAM_TEXT: float = 0.30
    WEIGHT_IDENTITY: float = 0.20
    WEIGHT_VERIFY: float = 0.10

    class Config:
        env_file = ".env"


@lru_cache()
def get_config():
    return Config()
