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
    # `llama-3.1-8b-instant` was decommissioned and every call came back 404,
    # so the guide fell back to its deterministic words on every single turn -
    # quietly, which is exactly how it is designed to fail.
    groq_model: str = "openai/gpt-oss-20b"
    # The AI Teacher playground's own model. Deliberately the biggest one the
    # account has: it is a sandbox, nothing it says reaches a child's real
    # progress, and a better explanation is worth the extra second there.
    groq_teacher_model: str = "openai/gpt-oss-120b"
    # Free HuggingFace sentence embeddings for the playground's retrieval. Small
    # (~90MB), downloaded once and cached; the retriever falls back to keyword
    # search if it cannot be loaded, so a machine with no network still works.
    playground_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # The guide's voice. Microsoft Edge's neural voices are free and need no key,
    # which is why they are the default: an install with nothing configured gets
    # a real voice rather than the browser's robot. One voice reads both scripts,
    # so an English sentence with Devanagari quoted inside it - which is how this
    # app narrates Hindi - is spoken properly without being cut into runs.
    edge_tts_voice: str = "hi-IN-SwaraNeural"
    edge_tts_rate: str = "+0%"
    edge_tts_pitch: str = "+0Hz"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model: str = ""
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    elevenlabs_output_format: str = "mp3_22050_32"
    elevenlabs_optimize_streaming_latency: str = "3"
    database_url: str = ""
    database_connect_timeout: int = 5
    # PBKDF2 rounds for a parent password. The OWASP floor for
    # PBKDF2-HMAC-SHA256; only the test suite turns it down.
    password_hash_rounds: int = 600_000
    # Fraction of teaching turns on which the policy tries a strategy its
    # table does not already favour. Small on purpose: this explores on
    # real children.
    policy_explore_rate: float = 0.08
    # The Planner Agent runs itself: a background sweep freezes today's plan for
    # every child who does not have one yet, so a plan exists before the child
    # opens the app rather than being built by their first request.
    planner_auto_run: bool = True
    planner_interval_seconds: int = 900
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
