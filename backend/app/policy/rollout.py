"""Who the learned policy is allowed to teach today, and the switch that stops it.

Three arms, and a child is in exactly one of them for a given configuration:

- **ladder** - the hand-written repair ladder decides and nothing is recorded as
  a learned decision. This is the permanent fallback and the day-one default;
- **shadow** - the ladder still decides and the child is taught by it, but the
  learned policy's choice is computed and written beside it. Nothing the child
  experiences changes, and the two columns can be compared afterwards;
- **rl** - the learned policy decides.

The arm is a stable hash of the child id against `policy_rollout_fraction`, so
the ladder `0 -> 0.05 -> 0.10 -> 0.25 -> 0.50 -> 1.0` moves whole cohorts and a
child does not flip arms between two turns of one sitting. `child_id` is hashed
and never stored in the RL state - the state key is still
`mode|mastery|rung|spent`, and this module is the only place the identity is
looked at at all.

The kill switch is `POLICY_MODE=off`, plus a process-local `disable()` that the
health breaker trips on its own. Either one takes every child back to the
ladder without a code change.
"""

import hashlib
import threading
import time
from dataclasses import dataclass

from app.config import get_settings


LADDER = "ladder"
SHADOW = "shadow"
RL = "rl"

# The steps the rollout is expected to walk. Nothing enforces them - the setting
# is a float - but they are named so a runbook can refer to them.
ROLLOUT_STEPS = (0.0, 0.05, 0.10, 0.25, 0.50, 1.0)

_lock = threading.Lock()
_disabled_until: float = 0.0
_disabled_reason: str = ""


@dataclass(frozen=True)
class Arm:
    name: str
    reason: str = ""

    @property
    def teaches(self) -> bool:
        """Whether the learned policy's choice is the one the child hears."""
        return self.name == RL

    @property
    def records(self) -> bool:
        """Whether an episode is written. Shadow records; the ladder does not."""
        return self.name in (RL, SHADOW)


def bucket(child_id: str) -> float:
    """A stable number in [0, 1) for one child.

    blake2b rather than `hash()`, which is salted per process in Python 3 and
    would put the same child in a different arm on every worker.
    """
    digest = hashlib.blake2b(str(child_id).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


def disable(reason: str, *, seconds: int | None = None) -> None:
    """Take the learned policy out of the loop on this worker.

    Called by the health breaker after repeated failures, and available to an
    operator through the admin endpoint. It expires, so a transient database
    outage does not leave the policy switched off until somebody notices.
    """
    global _disabled_until, _disabled_reason
    cooldown = seconds if seconds is not None else get_settings().policy_breaker_cooldown_seconds
    with _lock:
        _disabled_until = time.monotonic() + max(0, cooldown)
        _disabled_reason = reason


def enable() -> None:
    global _disabled_until, _disabled_reason
    with _lock:
        _disabled_until = 0.0
        _disabled_reason = ""


def disabled_reason() -> str:
    with _lock:
        if _disabled_until and time.monotonic() < _disabled_until:
            return _disabled_reason
    return ""


def arm_for(child_id: str | None) -> Arm:
    """Which arm this child is in right now."""
    tripped = disabled_reason()
    if tripped:
        return Arm(LADDER, reason=f"disabled:{tripped}")

    mode = (get_settings().policy_mode or "shadow").strip().lower()
    if mode == "off":
        return Arm(LADDER, reason="mode_off")
    if not child_id:
        # No learner behind the request - the demo payloads and the tests. There
        # is nobody to record an episode against.
        return Arm(LADDER, reason="no_child")
    if mode == "shadow":
        return Arm(SHADOW, reason="mode_shadow")

    fraction = max(0.0, min(1.0, get_settings().policy_rollout_fraction))
    if bucket(child_id) < fraction:
        return Arm(RL, reason=f"rollout:{fraction}")
    return Arm(SHADOW, reason=f"holdout:{fraction}")


def explore_rate(arm: Arm) -> float:
    """How much exploration this arm gets.

    Zero unless the learned policy is actually teaching: exploring in shadow
    would make the shadow column a record of a policy nobody is running, and
    exploring while disabled is the thing being switched off.
    """
    if not arm.teaches:
        return 0.0
    settings = get_settings()
    rate = max(0.0, min(1.0, settings.policy_explore_rate))
    if rate <= 0:
        return 0.0
    return max(rate, max(0.0, min(1.0, settings.policy_explore_min)))


__all__ = [
    "Arm",
    "LADDER",
    "RL",
    "ROLLOUT_STEPS",
    "SHADOW",
    "arm_for",
    "bucket",
    "disable",
    "disabled_reason",
    "enable",
    "explore_rate",
]
