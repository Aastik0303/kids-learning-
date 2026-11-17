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

    # --- Google Sign-In --------------------------------------------------
    # The OAuth client id from Google Cloud, and the only audience a Google ID
    # token is ever accepted for. A verifier that does not pin the audience
    # accepts a token minted for somebody else's app, which is the whole of the
    # attack; so an unset id turns the feature off rather than loosening it.
    # The web client needs the same value as NEXT_PUBLIC_GOOGLE_CLIENT_ID.
    google_client_id: str = ""
    # Where Google publishes the public keys its ID tokens are signed with.
    # Fetched over HTTPS and cached by the verifier; Google rotates them.
    google_jwks_url: str = "https://www.googleapis.com/oauth2/v3/certs"

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
    # --- email (SMTP) ----------------------------------------------------
    # The mailer. Two things are sent from this app and both of them are the
    # difference between an account being reachable and not: the sign-in code,
    # and the password-reset link. An unconfigured host means neither can be
    # sent, which `mailer.configured` reports and the callers act on.
    #
    # `smtp_port` decides how the connection is secured, because that is how
    # every mail provider documents it: 465 is implicit TLS (SMTPS) and 587 is
    # STARTTLS on a plain socket that is then upgraded. Port 25 unencrypted is
    # not offered - a sign-in code in cleartext across the internet is not a
    # second factor.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    # What the parent sees it came from. Gmail and most providers rewrite this
    # to the authenticated account unless the address is a verified alias.
    smtp_from_email: str = ""
    smtp_from_name: str = "Saksham IQ"
    # Seconds. Sign-in waits on this, so it is short enough that a dead mail
    # server is an error the parent can read rather than a spinner.
    smtp_timeout_seconds: int = 10

    # Where the reset link in the email points. The web app's own page, so this
    # is a frontend origin and not this API's: the parent clicks it, chooses a
    # password on the site, and the site calls back here.
    password_reset_url: str = "http://localhost:5000/forgot-password"

    # --- sign-in code (OTP) ----------------------------------------------
    # A second factor on password sign-in: the password proves what they know,
    # the emailed code proves they still hold the address the account is on.
    # Google sign-in is deliberately exempt - Google has already proved the
    # address, with its own second factor, and a code on top is friction that
    # buys nothing.
    auth_otp_enabled: bool = True
    auth_otp_length: int = 6
    # Ten minutes. Long enough to find the email on another device, short
    # enough that a code read over someone's shoulder goes stale.
    auth_otp_ttl_minutes: int = 10
    # Wrong guesses before the challenge dies and the parent signs in again.
    # A six-digit code is a million guesses; five is what keeps it that way.
    auth_otp_max_attempts: int = 5
    # Seconds before "send it again" does anything, and how many times. The
    # cooldown is what stops the button being a way to send someone mail.
    auth_otp_resend_cooldown_seconds: int = 60
    auth_otp_max_sends: int = 4

    # --- rate limiting ---------------------------------------------------
    # Per caller per minute, by route class. A caller is their bearer token when
    # they are signed in and their IP address when they are not - see
    # `app/services/rate_limit.py` for why that split exists, and why there is
    # an IP ceiling over the top of it.
    #
    # These are deliberately well above what the app itself does: the point is
    # to stop a runaway client, a scraper and a bill, not to ration a class.
    # Every one of them is read per request, so changing one needs a restart and
    # not a deploy.
    rate_limit_enabled: bool = True
    # Signing in and registering. Low because it is the surface worth attacking;
    # password guessing is counted separately and per account in `auth_service`.
    rate_limit_auth_per_minute: int = 30
    # Teaching turns. A child's turn takes seconds, so this is many times what a
    # real sitting can use, and it still caps what one caller can spend on the
    # model.
    rate_limit_ai_per_minute: int = 120
    # Speech: every one of these synthesises audio, so it is CPU this instance
    # does not have spare.
    rate_limit_speech_per_minute: int = 60
    # Plans, curriculum, progress. Cheap and cached, and asked for in bursts as
    # a page loads.
    rate_limit_read_per_minute: int = 300
    # The ceiling, per IP, whatever the route. Nobody using the app reaches it;
    # it is what stops a caller minting a new token to get a new bucket.
    rate_limit_ip_per_minute: int = 600
    # Whether `X-Forwarded-For` may be believed. True behind Render, Vercel or
    # any proxy that appends to it - without this every request in the world
    # shares the proxy's own address and therefore one bucket. False where
    # nothing sits in front of this server, because there the header is written
    # by the client and says whatever they like.
    rate_limit_trust_forwarded_for: bool = True
    # How many proxies sit in front of this server and append to
    # `X-Forwarded-For`. The address believed is that many entries from the
    # right, because everything to the left of it was written by the client.
    # One on Render; two with a CDN such as Cloudflare in front of it.
    rate_limit_proxy_hops: int = 1

    # --- response caching ------------------------------------------------
    # How long a browser may reuse an authored-content response before asking
    # again. It always revalidates after this, and is answered with 304 and no
    # body when nothing changed, so a deploy is visible within the minute.
    content_cache_max_age_seconds: int = 60

    # --- connection pool -------------------------------------------------
    # PostgreSQL only; SQLite does not pool. Sized for a small instance: enough
    # connections to serve concurrent requests, few enough that a managed
    # Postgres with a low connection cap is not exhausted by two workers.
    database_pool_size: int = 5
    database_max_overflow: int = 5
    # Seconds a request waits for a connection before giving up. Shorter than
    # the client's own timeout on purpose: a request that will not be answered
    # in time should fail and say so rather than hold a worker.
    database_pool_timeout: int = 10
    # Recycled well inside the idle timeout of a managed Postgres. Neon and
    # friends close an idle connection on their side without telling anybody,
    # and the first query on it then fails - `pool_pre_ping` catches that at the
    # cost of a round trip per checkout, and this avoids most of them.
    database_pool_recycle_seconds: int = 1800

    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"

    @property
    def google_sign_in_enabled(self) -> bool:
        """Whether the Google button is offered at all.

        No client id means no pinned audience, and a verifier with no audience
        to pin cannot tell this app's tokens from another app's - so the
        feature is off rather than open."""
        return bool(self.google_client_id.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
