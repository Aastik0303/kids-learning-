from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8")

    env: str = "development"
    llm_provider: str = "none"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model: str = ""
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_output_format: str = "mp3_22050_32"
    elevenlabs_optimize_streaming_latency: str = "3"
    database_url: str = ""
    database_connect_timeout: int = 5
    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"

    @property
    def elevenlabs_selected_model(self) -> str:
        return self.elevenlabs_model or self.elevenlabs_model_id

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
