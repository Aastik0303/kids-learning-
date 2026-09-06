"""What a retention result is worth, and nothing else.

This is the **reward system** as its own piece: it turns the verdict of a
retention test into a number, and it is the only place the four weights are
read. It has no database, no session, no clock and no opinion about *when* a
concept should be tested - that is the scheduler's - or about *whether* the
child was right - that is `stage.judge`'s, in pure Python, from the authored
key.

The weights themselves are the ones this project has always used, now settable
from the environment:

    retention pass   +1.00   REWARD_RETENTION_PASS
    transfer bonus   +0.35   REWARD_TRANSFER_BONUS
    retention fail   -0.50   PENALTY_RETENTION_FAIL
    answer leak      -1.50   PENALTY_ANSWER_LEAK

Two of them carry the whole design. The **positive terms can only be earned days
after the strategy was spent**, which is why a strategy that reaches today's
right answer by handing it over scores badly: it produces a correct answer on
the day and a failed retention test on the day after next. And the **leak
penalty is larger than a passed test pays**, so a turn that gives the answer
away cannot come out ahead even when the child then remembers it.

The transfer bonus is paid when the retention question is a *different* authored
question about the same concept from the one the child was taught with - "which
letter does Ant start with?" against "which letter does Apple start with?".
Remembering the same question is recall; answering a different one is the thing
the teaching was for.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


PASS = "pass"
FAIL = "fail"


@dataclass(frozen=True)
class Reward:
    """One reward, with the terms that built it kept beside the number.

    `terms` exists so a Q-value that moved a long way can be explained without
    re-deriving the arithmetic from four settings and a boolean.
    """

    value: float
    result: str
    terms: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.result == PASS


def weights() -> dict[str, float]:
    """The four numbers, as configured. Read fresh so a changed setting takes
    effect without a restart of anything but the settings cache."""
    settings = get_settings()
    return {
        "retention_pass": float(settings.reward_retention_pass),
        "transfer_bonus": float(settings.reward_transfer_bonus),
        "retention_fail": float(settings.penalty_retention_fail),
        "answer_leak": float(settings.penalty_answer_leak),
    }


def for_retention(
    *,
    passed: bool,
    transfer: bool = False,
    answer_leak_vetoed: bool = False,
) -> Reward:
    """What one settled retention test pays one teaching episode.

    `passed` is the deterministic judge's verdict and arrives from
    `stage.judge`; nothing in this module decides it. `transfer` says the test
    asked a different authored question from the one the episode taught with.
    `answer_leak_vetoed` is the episode's own record of having handed the answer
    over, classified at teaching time by `app/policy/leak.py`.
    """
    weight = weights()
    terms: list[str] = []
    value = 0.0

    if passed:
        value += weight["retention_pass"]
        terms.append(f"retention_pass +{weight['retention_pass']:.2f}")
        if transfer:
            value += weight["transfer_bonus"]
            terms.append(f"transfer +{weight['transfer_bonus']:.2f}")
    else:
        value -= weight["retention_fail"]
        terms.append(f"retention_fail -{weight['retention_fail']:.2f}")

    if answer_leak_vetoed:
        value -= weight["answer_leak"]
        terms.append(f"answer_leak -{weight['answer_leak']:.2f}")

    return Reward(value=value, result=PASS if passed else FAIL, terms=tuple(terms))


__all__ = ["FAIL", "PASS", "Reward", "for_retention", "weights"]
