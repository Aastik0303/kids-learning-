"""The Branch Decision Engine: advance, re-explain, or step away.

This is the question the whole project is built around - "aage badhun ya dobara
samjhaun" - and it is answered here in pure Python, from server state only.

Six outcomes and never a seventh. The priority order is fixed, and it is the
order rather than the conditions that carries the safety argument:

1. `END_KINDLY` first, because a child must never be stuck. A stuck
   three-year-old is being taught that learning feels bad, and no amount of
   good teaching later undoes that.
2. `SWITCH_MODALITY` next, so a microphone that cannot hear a small voice is not
   mistaken for a child who cannot answer.
3. `PREREQUISITE`, because re-explaining five to a child who does not have three
   is re-explaining the wrong thing.
4. `SIMPLIFY`, then `RE_EXPLAIN`, then `ADVANCE`.

No import in this module reaches `app.ai`, `app.services` or a model client, and
`tests/test_conductor.py` asserts that on the import graph.
"""

from dataclasses import dataclass, field
from enum import Enum


class Branch(str, Enum):
    ADVANCE = "advance"
    RE_EXPLAIN = "re_explain"
    SIMPLIFY = "simplify"
    PREREQUISITE = "prerequisite"
    SWITCH_MODALITY = "switch_modality"
    END_KINDLY = "end_kindly"


# A correct answer that took more than one try still advances, but only once the
# skill is holding up. Below this the child repeats the question in a new form
# rather than moving on with a shaky grip on it.
ADVANCE_MASTERY_FLOOR = 0.60

# Four tries is the ceiling on one question. The fourth is not a fifth chance;
# it is the turn the conductor stops asking.
MAX_ATTEMPTS_ON_ONE_QUESTION = 4

# Where "re-explain" stops and "make it easier" starts.
SIMPLIFY_AT_ATTEMPT = 3

FRUSTRATION_END_THRESHOLD = 0.75
FRUSTRATION_SIMPLIFY_THRESHOLD = 0.50

# A skill whose foundation is this weak is not the skill to be teaching.
PREREQUISITE_FLOOR = 0.40

# How far past the planned length a sitting may run before it is closed warmly.
SESSION_OVERRUN_FACTOR = 1.25

# Two speech results the recogniser could not resolve is a microphone problem.
UNRESOLVED_SPEECH_LIMIT = 2


@dataclass(frozen=True)
class BranchInput:
    """Everything the decision is allowed to see. All of it is server state.

    Nothing here is taken from the client's own account of the turn: the client
    reports keystrokes and taps, and a client that could report its attempt
    count could ask to be advanced.
    """

    is_correct: bool
    attempts_on_current: int
    skill_mastery: float
    consecutive_correct: int = 0
    frustration_score: float = 0.0
    ladder_rungs_used: tuple[str, ...] = ()
    scaffold_level: int = 0
    minutes_in_session: float = 0.0
    target_minutes: float = 10.0
    modality: str = "tap"
    unresolved_speech_streak: int = 0
    prerequisite_mastery: float | None = None
    age_band: str = "standard"
    response_latency_ms: int = 0


@dataclass(frozen=True)
class BranchOutcome:
    decision: Branch
    # Why, in one machine-readable token. Written to the lesson state and read
    # back in the parent digest, so "why did it stop?" has an answer that is not
    # someone's reconstruction.
    reason: str
    scaffold_delta: int = 0
    notes: dict = field(default_factory=dict)

    @property
    def teaches_again(self) -> bool:
        return self.decision in (Branch.RE_EXPLAIN, Branch.SIMPLIFY, Branch.PREREQUISITE)


def decide(state: BranchInput) -> BranchOutcome:
    """Pick exactly one of the six. First rule that matches wins."""

    # 1. Safety. A child is never left in front of a question they cannot do.
    if state.attempts_on_current >= MAX_ATTEMPTS_ON_ONE_QUESTION and not state.is_correct:
        return BranchOutcome(Branch.END_KINDLY, reason="attempts_exhausted")
    if state.frustration_score >= FRUSTRATION_END_THRESHOLD:
        return BranchOutcome(Branch.END_KINDLY, reason="frustration")
    if state.minutes_in_session > state.target_minutes * SESSION_OVERRUN_FACTOR:
        return BranchOutcome(Branch.END_KINDLY, reason="session_overrun")

    # 2. An input problem is not a learning problem.
    if state.modality == "voice" and state.unresolved_speech_streak >= UNRESOLVED_SPEECH_LIMIT:
        return BranchOutcome(
            Branch.SWITCH_MODALITY, reason="speech_unresolved", notes={"modality": "tap"}
        )

    # 3. Do not teach a thing whose foundation is missing. Checked before the
    #    repair ladder, because otherwise the ladder re-explains the wrong skill
    #    four times and then gives up on a child who was never taught the first
    #    half of it.
    if (
        not state.is_correct
        and state.prerequisite_mastery is not None
        and state.prerequisite_mastery < PREREQUISITE_FLOOR
    ):
        return BranchOutcome(Branch.PREREQUISITE, reason="prerequisite_weak", scaffold_delta=1)

    if state.is_correct:
        # First try, or a skill that is already holding: move on.
        if state.attempts_on_current == 0 or state.skill_mastery >= ADVANCE_MASTERY_FLOOR:
            return BranchOutcome(Branch.ADVANCE, reason="correct")
        # Right at last, but the skill is not there yet. Another question on the
        # same skill, with the support left where it is.
        return BranchOutcome(Branch.ADVANCE, reason="correct_after_help", notes={"reteach_soon": True})

    # 4. Third try: stop adding words, start taking things away.
    if state.attempts_on_current >= SIMPLIFY_AT_ATTEMPT or state.frustration_score >= FRUSTRATION_SIMPLIFY_THRESHOLD:
        return BranchOutcome(Branch.SIMPLIFY, reason="attempts_high", scaffold_delta=1)

    # 5. Explain it again, differently. The rung and the strategy are chosen
    #    elsewhere; this only says that the question stays and the support goes up.
    return BranchOutcome(Branch.RE_EXPLAIN, reason="incorrect", scaffold_delta=1)


def target_minutes_for(age_band: str) -> float:
    """How long a sitting is meant to be, by age band.

    Two-year-olds do not have ten minutes of attention and being asked for it is
    how a lesson turns into a chore.
    """
    return 6.0 if age_band == "early" else 10.0


__all__ = [
    "ADVANCE_MASTERY_FLOOR",
    "Branch",
    "BranchInput",
    "BranchOutcome",
    "MAX_ATTEMPTS_ON_ONE_QUESTION",
    "PREREQUISITE_FLOOR",
    "decide",
    "target_minutes_for",
]
