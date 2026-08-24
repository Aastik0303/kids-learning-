"""Frustration, boredom and silence, as numbers rather than opinions.

A model asked "does this child look frustrated?" gives an answer that cannot be
reproduced, cannot be tested, and cannot be corrected except by rewriting a
prompt and hoping. A formula can be read, asserted on, and fixed by changing one
weight. That is the whole argument for these being arithmetic.

The idle ladder is here for the same reason: what happens when a child says
nothing for forty seconds is a decision, and the server takes it. The client is
told the timeout and what to report when it fires - it does not choose.
"""

from dataclasses import dataclass


# The weights add to 1.0. Attempts on the current question dominate, because
# that is the signal that is actually about this moment; the rest are context.
WEIGHT_ATTEMPTS = 0.30
WEIGHT_RECENT_WRONG = 0.25
WEIGHT_RETRY_BURST = 0.20
WEIGHT_SILENCE = 0.15
WEIGHT_MODALITY_FAILURE = 0.10

# A tap inside this window is not an answer, it is a jab at the screen.
RETRY_BURST_MS = 3000

# Five right in a row, answered fast, is a child being under-asked.
BOREDOM_STREAK = 5
BOREDOM_LATENCY_RATIO = 0.40

SIMPLIFY_AT = 0.50
END_KINDLY_AT = 0.75


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class SessionSignals:
    """What one sitting has looked like so far, from server-side counters."""

    attempts_on_current: int = 0
    recent_answers: tuple[bool, ...] = ()
    retry_burst_count: int = 0
    answers_counted: int = 0
    idle_rungs_hit: int = 0
    idle_rungs_available: int = 5
    unresolved_speech: int = 0
    speech_attempts: int = 0
    consecutive_correct: int = 0
    average_latency_ms: float = 0.0
    band_median_latency_ms: float = 0.0


def frustration(signals: SessionSignals) -> float:
    """0.0 is a happy child; 1.0 means stop now.

    Read the terms as a sentence: this question has gone wrong repeatedly, the
    last few answers have gone wrong too, the taps are getting faster and
    less considered, the child has started going quiet, and the microphone keeps
    failing them.
    """
    recent = signals.recent_answers[-6:]
    recent_correct_rate = (sum(1 for ok in recent if ok) / len(recent)) if recent else 1.0
    retry_burst_ratio = (
        signals.retry_burst_count / signals.answers_counted if signals.answers_counted else 0.0
    )
    silence_ratio = (
        signals.idle_rungs_hit / signals.idle_rungs_available if signals.idle_rungs_available else 0.0
    )
    modality_failure_ratio = (
        signals.unresolved_speech / signals.speech_attempts if signals.speech_attempts else 0.0
    )

    score = (
        WEIGHT_ATTEMPTS * _clamp(signals.attempts_on_current / 4)
        + WEIGHT_RECENT_WRONG * _clamp(1 - recent_correct_rate)
        + WEIGHT_RETRY_BURST * _clamp(retry_burst_ratio)
        + WEIGHT_SILENCE * _clamp(silence_ratio)
        + WEIGHT_MODALITY_FAILURE * _clamp(modality_failure_ratio)
    )
    return round(_clamp(score), 2)


def is_bored(signals: SessionSignals) -> bool:
    """A long correct streak answered quickly means the questions are too easy.

    Boredom and frustration are opposite failures of the same thing - the
    difficulty is wrong - and a class that only watches for one of them loses
    the child who finds it trivial just as surely.
    """
    if signals.consecutive_correct < BOREDOM_STREAK:
        return False
    if not signals.band_median_latency_ms:
        return True
    return signals.average_latency_ms < signals.band_median_latency_ms * BOREDOM_LATENCY_RATIO


# --------------------------------------------------------------------------
# The idle ladder
# --------------------------------------------------------------------------

# What each rung does. Exactly one of the five asks a model for words; the rest
# are templates over content the server already holds, which is what lets this
# run on every screen without spending the session's AI budget on silence.
IDLE_RUNGS = (
    ("repeat_instruction", False),
    ("authored_hint", False),
    ("re_explain_simpler", True),
    ("do_together", False),
    ("offer_something_easier", False),
)


def idle_timeout_ms(thresholds: list[int], rung: int) -> int:
    """How long to wait before the next rung, from the manifest's own numbers.

    Play Group waits twelve seconds and Upper KG eight, because a two-year-old
    takes longer to decide to touch the screen at all. These come from
    `experience_modes[*].idle_thresholds_seconds`, never from a constant here.
    """
    if not thresholds:
        return 15000
    index = max(0, min(rung, len(thresholds) - 1))
    return int(thresholds[index] * 1000)


def idle_action(rung: int) -> tuple[str, bool]:
    """The action for a rung, and whether it needs the model."""
    index = max(0, min(rung, len(IDLE_RUNGS) - 1))
    return IDLE_RUNGS[index]


def next_idle_rung(rung: int) -> int:
    return min(rung + 1, len(IDLE_RUNGS))


__all__ = [
    "END_KINDLY_AT",
    "IDLE_RUNGS",
    "SIMPLIFY_AT",
    "SessionSignals",
    "frustration",
    "idle_action",
    "idle_timeout_ms",
    "is_bored",
    "next_idle_rung",
]
