"""How much help this turn carries, and what the client is allowed to render.

Scaffolding is the support a child gets, and the whole art of it is that it
comes *down*. S4 is the guide doing it while the child watches; S0 is the child
doing it alone. A lesson that never fades its scaffolding teaches a child to
wait for help.

One rule is not negotiable and is enforced structurally rather than by intent:
**the answer is never pointed at during YOU DO.** Pointing belongs to I DO and
WE DO, where the guide is demonstrating and the child is copying, and where the
attempt is recorded at a scaffold level the mastery roll-up already discounts
(`truth.SCAFFOLD_CREDIT`). In YOU DO the support is fewer choices and bigger
targets - never a finger on the right one.
"""

from dataclasses import dataclass, field

from app.conductor.phases import Phase


# Presentation floors. A frustrated child gets the simplest screen the age band
# allows, never a busier one.
MIN_CHOICES = 2
FRUSTRATION_SIMPLIFY_AT = 0.50

# Slowed narration for the youngest band and for anyone struggling. Below this
# the guide sounds broken rather than gentle.
SLOW_NARRATION = 0.85
NORMAL_NARRATION = 1.0


@dataclass(frozen=True)
class Scaffold:
    """The support block that travels with an activity."""

    level: int
    point_at: list[str] = field(default_factory=list)
    dim_others: bool = False
    demo_tap: bool = False
    options_shown: list[str] = field(default_factory=list)
    co_narrate: str = ""


@dataclass(frozen=True)
class Presentation:
    """What the screen looks like this turn. Server-decided, client-rendered."""

    choices_shown: int
    touch_target_px: int
    text_density: str
    decoration: str
    motion: str
    narration_speed: float


def trim_options(
    options: list[str],
    *,
    correct_answer: str | None,
    limit: int,
) -> list[str]:
    """Fewer choices, with the right one still among them.

    Trimming is done here and never by the client: a client that trimmed its own
    options could drop the answer and mark a child wrong for a question that had
    become impossible. The authored order is kept so the screen does not
    reshuffle under a child who is mid-decision.
    """
    if limit <= 0 or len(options) <= limit:
        return list(options)

    kept = [option for option in options if option == correct_answer][:1]
    for option in options:
        if len(kept) >= limit:
            break
        if option not in kept:
            kept.append(option)
    # Back into authored order: `kept` was built answer-first, and always
    # showing the answer in the same position is a pattern a four-year-old will
    # learn instead of the lesson.
    return [option for option in options if option in kept]


def build(
    *,
    phase: Phase,
    level: int,
    options: list[str],
    correct_answer: str | None,
    visual_targets: list[str],
    max_choices: int,
    co_narrate: str = "",
) -> Scaffold:
    """The scaffold block for this phase at this level."""
    demonstrating = phase in (Phase.I_DO, Phase.WE_DO)
    limit = MIN_CHOICES if level >= 3 else max_choices

    return Scaffold(
        level=level,
        # Only while demonstrating. See the module docstring: this is the answer
        # leak boundary, and it is a phase check rather than a promise.
        point_at=visual_targets[:1] if demonstrating and level >= 3 else [],
        dim_others=demonstrating and level >= 3 and len(visual_targets) > 1,
        # S4 shows the answer being tapped without submitting it. It is the last
        # rung before the conductor stops asking, and it belongs to WE DO only.
        demo_tap=phase == Phase.WE_DO and level >= 4,
        options_shown=trim_options(options, correct_answer=correct_answer, limit=limit),
        co_narrate=co_narrate if demonstrating else "",
    )


def presentation(
    *,
    touch_target_px: int,
    max_choices_per_screen: int,
    text_density: str,
    level: int,
    frustration_score: float,
    options_shown: int,
) -> Presentation:
    """The screen for this turn, from the age band and how it is going.

    The age band sets the floor - Play Group never gets four choices or small
    targets - and struggle only ever makes the screen simpler. Nothing here can
    make a screen busier than the manifest allows.
    """
    struggling = frustration_score >= FRUSTRATION_SIMPLIFY_AT or level >= 3
    return Presentation(
        choices_shown=min(options_shown or max_choices_per_screen, max_choices_per_screen),
        # A struggling child gets a bigger target, never a smaller one. The
        # floor is the band's own number.
        touch_target_px=int(touch_target_px * 1.25) if struggling else touch_target_px,
        text_density="none" if struggling else text_density,
        decoration="off" if struggling else "on",
        motion="reduced" if struggling else "normal",
        narration_speed=SLOW_NARRATION if struggling or text_density == "none" else NORMAL_NARRATION,
    )


__all__ = [
    "MIN_CHOICES",
    "Presentation",
    "Scaffold",
    "build",
    "presentation",
    "trim_options",
]
