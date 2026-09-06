from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # `extra="ignore"` so a key left over in somebody's `.env` - an
    # `ELEVENLABS_*` line from before there was one voice, say - is skipped
    # rather than refusing to start the server.
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: str = "development"
    llm_provider: str = "none"
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
    # The guide's voice, and the only one. Microsoft Edge's neural voices are
    # free and need no key, so every install sounds the same and none of them
    # falls back to the browser's robot. One voice reads both scripts,
    # so an English sentence with Devanagari quoted inside it - which is how this
    # app narrates Hindi - is spoken properly without being cut into runs.
    edge_tts_voice: str = "hi-IN-SwaraNeural"
    edge_tts_rate: str = "+0%"
    edge_tts_pitch: str = "+0Hz"
    database_url: str = ""
    database_connect_timeout: int = 5
    # The key that signs a parent's session token. `JWT_SECRET` in the
    # environment and nowhere else: a signing key with a default value is the
    # same as no signature at all, so outside development an unset secret makes
    # `/auth/login` refuse rather than fall back to something guessable.
    # Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
    jwt_secret: str = ""
    # HS256 - one server signs and the same server verifies, so there is no
    # second party who needs a public key. The verifier pins this; a token is
    # never allowed to name its own algorithm.
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "saksham-iq"
    jwt_audience: str = "saksham-iq-app"
    # Thirty days, matching `learners.SESSION_TTL`, so the signature and the
    # `auth_sessions` row it names stop being valid at the same moment. A
    # parent signs in on the family tablet and is not asked again next week.
    jwt_ttl_minutes: int = 60 * 24 * 30

    # PBKDF2 rounds for a parent password. The OWASP floor for
    # PBKDF2-HMAC-SHA256; only the test suite turns it down.
    password_hash_rounds: int = 600_000
    # Fraction of teaching turns on which the policy tries a strategy its
    # table does not already favour. Small on purpose: this explores on
    # real children.
    policy_explore_rate: float = 0.08
    # A floor under exploration, applied only while exploration is on at all.
    # A table that has learned a strong preference in one state would otherwise
    # never try the eighth strategy again, and a state whose best action drifts
    # (a new manifest, a re-authored level) would never notice.
    policy_explore_min: float = 0.0
    # The kill switch, readable without a redeploy: `POLICY_MODE=off` in the
    # environment and a restart of one worker takes the learned policy out of
    # the loop entirely, and every turn is served by the hand-written ladder.
    #
    #   off     - the ladder decides, nothing is written, no Q update is read
    #   shadow  - the ladder decides and the child is taught by it; the learned
    #             policy's choice is recorded beside it for comparison only
    #   on      - the learned policy decides for the rolled-out fraction of
    #             children, and the ladder for the rest
    policy_mode: str = "shadow"
    # What fraction of children the learned policy actually teaches while
    # `policy_mode` is "on". The rollout ladder is 0 -> 0.05 -> 0.10 -> 0.25 ->
    # 0.50 -> 1.0, and the bucket is a stable hash of the child id, so a child
    # does not move between arms from one turn to the next.
    policy_rollout_fraction: float = 0.0
    # How many consecutive database or selection failures take the policy out of
    # the loop on their own. It comes back after `policy_breaker_cooldown_seconds`.
    policy_breaker_threshold: int = 5
    policy_breaker_cooldown_seconds: int = 300
    # The shared secret `POST /policy/disable` wants outside development. The
    # kill switch has to work without a deploy, which means it is an HTTP
    # endpoint, which means it was reachable by anybody who could reach the API
    # at all. Empty in development so the switch stays one curl away; set in
    # every other environment, and the endpoint refuses without it.
    policy_admin_token: str = ""
    # --- retention tests ------------------------------------------------
    # A concept taught today becomes eligible for a deterministic retention test
    # this many days later. The scheduler owns *when* - never the policy - so
    # this is the one number that decides it, and it is here rather than in the
    # policy package for exactly that reason.
    retention_test_delay_days: int = 2
    # How many due retention tests one sitting opens with. The rest stay due and
    # are asked at the start of the next sitting: a four-year-old who is handed
    # nine questions about last week before today's lesson has been given a test,
    # not a class.
    retention_tests_per_sitting: int = 3
    # What a settled retention test pays the teaching episode that earned it.
    # Configurable because these four numbers are the whole reward function and
    # tuning them must not need a code change; they are read through
    # `app/policy/reward.py` and nowhere else.
    reward_retention_pass: float = 1.0
    reward_transfer_bonus: float = 0.35
    penalty_retention_fail: float = 0.5
    penalty_answer_leak: float = 1.5
    # The Planner Agent runs itself: a background sweep freezes today's plan for
    # every child who does not have one yet, so a plan exists before the child
    # opens the app rather than being built by their first request.
    planner_auto_run: bool = True
    planner_interval_seconds: int = 900
    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
