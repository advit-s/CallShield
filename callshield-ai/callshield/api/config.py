from pydantic_settings import BaseSettings
from functools import lru_cache

class Config(BaseSettings):
    APP_NAME: str = "CallShield AI"
    APP_VERSION: str = "2.1.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"


@lru_cache()
def get_config():
    return Config()