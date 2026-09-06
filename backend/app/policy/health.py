"""The automatic half of the kill switch.

`rollout.disable()` is the switch; this is the thing that pulls it without
anybody watching. It counts consecutive failures of the learned path - a
database that will not answer, a selection that raised - and after
`policy_breaker_threshold` of them in a row it takes the policy out of the loop
for the cooldown and every child goes back to the hand-written ladder.

Consecutive, not a rate: one failed turn in a hundred is a blip and the fallback
already handled it kindly; five in a row is an outage, and continuing to open a
database session per teaching turn against a database that is down adds a
connect timeout to every child's screen.

Nothing here can stop a lesson. The breaker only ever changes *which policy
chooses a strategy*, and the ladder is always able to choose one.
"""

import threading

from app.config import get_settings
from app.policy import metrics, rollout


_lock = threading.Lock()
_consecutive_failures = 0


def record_success() -> None:
    global _consecutive_failures
    with _lock:
        _consecutive_failures = 0


def record_failure(kind: str) -> int:
    """Note a failure of the learned path and trip the breaker if it is time.

    `kind` is `db` or `selection`; both are counted separately for the metrics
    and together for the breaker, because from the child's side they are the
    same event - the learned policy could not answer.
    """
    global _consecutive_failures
    metrics.count(metrics.DB_ERROR if kind == "db" else metrics.SELECTION_ERROR, kind=kind)
    with _lock:
        _consecutive_failures += 1
        failures = _consecutive_failures
        threshold = max(1, get_settings().policy_breaker_threshold)
        tripped = failures >= threshold
    if tripped:
        rollout.disable(f"{kind}_failures", seconds=get_settings().policy_breaker_cooldown_seconds)
        metrics.count(metrics.FALLBACK, reason="breaker_tripped", kind=kind)
    return failures


def consecutive_failures() -> int:
    with _lock:
        return _consecutive_failures


def reset() -> None:
    """Clear the breaker and re-enable the policy. Tests and the admin path."""
    global _consecutive_failures
    with _lock:
        _consecutive_failures = 0
    rollout.enable()


def status() -> dict:
    """What `/policy/health` reports."""
    settings = get_settings()
    return {
        "mode": settings.policy_mode,
        "rollout_fraction": settings.policy_rollout_fraction,
        "explore_rate": settings.policy_explore_rate,
        "explore_min": settings.policy_explore_min,
        "consecutive_failures": consecutive_failures(),
        "breaker_threshold": settings.policy_breaker_threshold,
        "disabled_reason": rollout.disabled_reason(),
        "rates": metrics.rates(),
    }


__all__ = ["consecutive_failures", "record_failure", "record_success", "reset", "status"]
