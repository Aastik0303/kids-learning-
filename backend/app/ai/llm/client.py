"""One provider-agnostic call, with a circuit breaker in front of it.

The Groq call used to sit in the middle of `guide_agent_service`, which meant
the guide owned an HTTP client, a timeout, a model name and a JSON envelope as
well as its teaching logic - and adding a second provider meant editing the
teacher. It lives here now, and the guide asks for a completion.

Two behaviours matter more than the transport:

**Failure is normal and quiet.** Every caller has a deterministic answer ready.
`chat()` raises `LLMUnavailable` for a missing key, an unknown provider, a
timeout, an HTTP error or a malformed body, and the caller falls back. Nothing
here retries: a child is waiting, and the fallback is already good.

**The breaker stops a dead provider from costing every turn six seconds.** After
three consecutive failures the client stops calling out for a minute and fails
immediately, so an outage degrades the class to the deterministic guide instead
of stalling it. One success closes it again.
"""

import logging
import time
from dataclasses import dataclass, field

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)

# A child watching a blank screen gives up long before a slow model answers.
REQUEST_TIMEOUT_SECONDS = 6.0

BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 60.0

PROVIDER_ENDPOINTS = {"groq": "https://api.groq.com/openai/v1/chat/completions"}

# One connection, kept open, shared by every call.
#
# `httpx.post(...)` builds an SSL context, resolves, connects and shakes hands
# on every single call, and on this machine that measured 1.5-2.3s per turn
# against 0.5-0.9s through a pooled client - while Groq's own reported
# processing time was a quarter of a second. That gap was most of what "the AI
# is slow" meant: a child watching a blank screen for a second and a half of
# handshake before the model had even been asked.
#
# Built lazily so importing this module never touches the network, and kept for
# the life of the process. `httpx.Client` is thread-safe, which is what the
# worker threads underneath the sync endpoints need.
_client: httpx.Client | None = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            # Per-request timeouts are passed at the call site; this is only the
            # default for anything that does not name one.
            timeout=REQUEST_TIMEOUT_SECONDS,
            limits=httpx.Limits(max_keepalive_connections=4, keepalive_expiry=300.0),
        )
    return _client


class LLMUnavailable(RuntimeError):
    """The model could not answer. Every caller has a fallback for this."""


@dataclass
class ChatRequest:
    """One completion. `system` is the standing instruction, `user` the turn."""

    system: list[str] = field(default_factory=list)
    user: list[str] = field(default_factory=list)
    temperature: float = 0.4
    max_tokens: int = 300
    json_object: bool = True
    # A caller that needs a different model from the app's default one. The AI
    # Teacher playground uses the big model on purpose - it is a sandbox where a
    # slower, better answer is worth more than a fast one - while the class keeps
    # the small fast model a waiting child needs.
    model: str = ""
    # Seconds to wait. The default is the class's: a child is watching a screen
    # and the fallback is already good. A caller with nobody waiting - the
    # playground - may ask for more.
    timeout: float = 0.0
    # How much of the budget a reasoning model may spend thinking before it
    # answers. Empty leaves the provider's default. This matters more than it
    # sounds: gpt-oss on Groq spent its whole 500-token budget reasoning and
    # returned an empty body, which the provider then rejected as invalid JSON -
    # so the teacher fell back to templates on every other turn.
    reasoning_effort: str = ""


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float = 0.0

    def is_open(self, now: float) -> bool:
        return self.failures >= BREAKER_THRESHOLD and (now - self.opened_at) < BREAKER_COOLDOWN_SECONDS

    def record_failure(self, now: float) -> None:
        self.failures += 1
        if self.failures >= BREAKER_THRESHOLD:
            self.opened_at = now

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = 0.0


_breaker = _Breaker()


def reset_breaker() -> None:
    """Close the breaker. Called by the tests and by a deliberate restart."""
    _breaker.record_success()


def provider_name() -> str:
    return get_settings().llm_provider.strip().lower()


def api_key() -> str:
    settings = get_settings()
    return {"groq": settings.groq_api_key}.get(provider_name(), "")


def is_configured() -> bool:
    """Whether a real call is possible at all: known provider, key present."""
    return provider_name() in PROVIDER_ENDPOINTS and bool(api_key())


def model_name() -> str:
    return get_settings().groq_model


def chat(request: ChatRequest) -> str:
    """Return the model's message content, or raise `LLMUnavailable`."""
    if not is_configured():
        raise LLMUnavailable(f"no usable provider configured (llm_provider={provider_name() or 'none'})")

    now = time.monotonic()
    if _breaker.is_open(now):
        raise LLMUnavailable("provider circuit breaker is open")

    body: dict = {
        "model": request.model or model_name(),
        "messages": [
            *({"role": "system", "content": text} for text in request.system),
            *({"role": "user", "content": text} for text in request.user),
        ],
        "temperature": request.temperature,
        "max_completion_tokens": request.max_tokens,
    }
    if request.json_object:
        body["response_format"] = {"type": "json_object"}
    if request.reasoning_effort:
        body["reasoning_effort"] = request.reasoning_effort

    try:
        response = _http().post(
            PROVIDER_ENDPOINTS[provider_name()],
            headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
            json=body,
            timeout=request.timeout or REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        _breaker.record_failure(time.monotonic())
        # The status and the provider's own words, not just the exception class.
        # "Model call failed (HTTPStatusError)" was true and told nobody whether
        # the key was wrong, the model was gone or the account was rate limited.
        detail = ""
        if isinstance(exc, httpx.HTTPStatusError):
            detail = f" {exc.response.status_code}: {exc.response.text[:200]}"
        logger.warning(
            "Model call failed (%s)%s; falling back to the deterministic path",
            type(exc).__name__,
            detail,
        )
        raise LLMUnavailable(str(exc)) from exc

    # An empty body is a failure, and it has to be counted as one *before* the
    # breaker is told anything. Recording the success first meant the one
    # failure mode this breaker was written for - a reasoning model that spends
    # its whole budget thinking and returns nothing, which the provider then
    # rejects - reset the counter on every call, so the breaker never opened and
    # every turn went on paying a full round trip to a provider that could not
    # answer.
    if not isinstance(content, str) or not content.strip():
        _breaker.record_failure(time.monotonic())
        logger.warning("The model returned an empty message; falling back to the deterministic path")
        raise LLMUnavailable("the provider returned an empty message")

    _breaker.record_success()
    return content
