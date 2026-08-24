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

import json
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
        "model": model_name(),
        "messages": [
            *({"role": "system", "content": text} for text in request.system),
            *({"role": "user", "content": text} for text in request.user),
        ],
        "temperature": request.temperature,
        "max_completion_tokens": request.max_tokens,
    }
    if request.json_object:
        body["response_format"] = {"type": "json_object"}

    try:
        response = httpx.post(
            PROVIDER_ENDPOINTS[provider_name()],
            headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        _breaker.record_failure(time.monotonic())
        logger.warning("Model call failed (%s); falling back to the deterministic path", type(exc).__name__)
        raise LLMUnavailable(str(exc)) from exc

    _breaker.record_success()
    if not isinstance(content, str) or not content.strip():
        raise LLMUnavailable("the provider returned an empty message")
    return content


def chat_json(request: ChatRequest) -> dict:
    """`chat()` for callers that want the decoded object rather than the text."""
    decoded = json.loads(chat(request))
    if not isinstance(decoded, dict):
        raise LLMUnavailable("the provider returned JSON that was not an object")
    return decoded
