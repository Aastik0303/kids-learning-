"""The lesson's state machine.

    greet -> set -> i_do -> we_do -> you_do -> check -> branch -> ...
                      ^                                   |
                      +------------- re_explain ----------+
                                                          |
                                                    advance / end
                                                          v
                                                        close

Every phase is a row value, not a client state. A refresh, a second tab or a
crash resumes the same phase, because the client never held it in the first
place.

Two rules about `we_do` that are easy to get wrong:

- It costs **no new authored content**. WE DO is the same activity as YOU DO,
  served with the scaffolding turned up - the guide points, narrates along, and
  the child does it with help.
- It is skipped for `lesson_flow == "complete"` topics. Those are a designed
  sequence - meet the letter, find it, say it, write it - that already carries
  its own I-do and you-do. Injecting another WE DO would break the method.
"""

from enum import Enum


class Phase(str, Enum):
    GREET = "greet"
    SET = "set"
    I_DO = "i_do"
    WE_DO = "we_do"
    YOU_DO = "you_do"
    CHECK = "check"
    BRANCH = "branch"
    CLOSE = "close"


# The phases in which the child is looking at an activity rather than at the
# guide talking. Used to decide whether a directive carries one.
ACTIVITY_PHASES = (Phase.I_DO, Phase.WE_DO, Phase.YOU_DO)

# Where the child is expected to answer. The others are the guide's turn, and a
# directive from them asks for nothing but a moment's attention.
ANSWER_PHASES = (Phase.YOU_DO,)


def opening_phase(*, returning: bool) -> Phase:
    """A child who has been here before is greeted; a fresh lesson states its aim.

    The greeting exists to carry continuity - "yesterday you finished shapes" -
    so it is skipped where there is nothing to be continuous with.
    """
    return Phase.GREET if returning else Phase.SET


def after_intro(phase: Phase) -> Phase:
    return Phase.SET if phase == Phase.GREET else Phase.I_DO


def teaching_sequence(*, lesson_flow: str, needs_answer: bool) -> tuple[Phase, ...]:
    """The phases one activity is played through.

    A presentational card - a letter being shown, a song - is I DO and nothing
    else: there is nothing to check, so asking would be asking about a question
    that was never posed.
    """
    if not needs_answer:
        return (Phase.I_DO,)
    if lesson_flow == "complete":
        return (Phase.I_DO, Phase.YOU_DO)
    return (Phase.I_DO, Phase.WE_DO, Phase.YOU_DO)


def next_in_sequence(sequence: tuple[Phase, ...], current: Phase) -> Phase | None:
    """The next teaching phase for this activity, or None when it is the child's
    turn to be checked."""
    if current not in sequence:
        return sequence[0] if sequence else None
    index = sequence.index(current)
    return sequence[index + 1] if index + 1 < len(sequence) else None


def scaffold_for_phase(phase: Phase, *, base: int) -> int:
    """How much support each phase carries.

    WE DO is deliberately heavy - the point is doing it together - and YOU DO
    fades it back to whatever the child has earned. This is the scaffolding fade
    in two lines: support is a property of the phase, not a setting someone
    forgot to turn off.
    """
    if phase == Phase.WE_DO:
        return max(base, 3)
    if phase == Phase.I_DO:
        return 4
    return base


__all__ = [
    "ACTIVITY_PHASES",
    "ANSWER_PHASES",
    "Phase",
    "after_intro",
    "next_in_sequence",
    "opening_phase",
    "scaffold_for_phase",
    "teaching_sequence",
]
