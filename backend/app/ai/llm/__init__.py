"""The model client, one provider at a time, behind one function.

`from app.ai.llm import chat` is the only way anything in this codebase reaches
a language model.
"""

from app.ai.llm.client import ChatRequest, LLMUnavailable, chat, is_configured, provider_name, reset_breaker

__all__ = [
    "ChatRequest",
    "LLMUnavailable",
    "chat",
    "is_configured",
    "provider_name",
    "reset_breaker",
]
