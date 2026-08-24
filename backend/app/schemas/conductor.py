"""One response shape for the whole class: `ConductorDirective`.

The app used to answer a lesson turn from four places - `learning/answer`,
`practice/answer`, `agent/guide`, `companion/session/event` - which between them
decided three different things in three different ways, and left the client to
assemble a lesson out of the pieces. The conductor answers with one object every
time, and the client renders it.

Everything a client needs to know is in here, including what to do when the
child does nothing: `next_input.on_timeout` names the event to report back, so
even silence is a decision the server has already taken.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.avatar import AvatarPayload
from app.schemas.guide import GuideVisualAction
from app.schemas.learning import Activity


InputKind = Literal["tap", "voice", "trace", "idle", "doubt", "ready"]

Phase = Literal["greet", "set", "i_do", "we_do", "you_do", "check", "branch", "close"]


class ConductorInput(BaseModel):
    """What the child just did. The client reports; it does not interpret.

    `answer` is empty for `idle` and `ready`. `latency_ms` is how long the child
    took to respond, which feeds the frustration score - it is advisory, and
    nothing that decides correctness or progress reads it.
    """

    kind: InputKind = "tap"
    answer: str = ""
    latency_ms: int = Field(default=0, ge=0, le=600_000)
    # Speech confidence, when the input came from the microphone. Below the
    # recogniser's own floor the turn counts as unresolved - a microphone
    # problem - rather than as a wrong answer.
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class ScaffoldBlock(BaseModel):
    """How much help travels with this activity."""

    level: int = Field(default=0, ge=0, le=4)
    point_at: list[str] = Field(default_factory=list)
    dim_others: bool = False
    # Shows the answer being tapped without submitting it. WE DO only.
    demo_tap: bool = False
    # The options the client may render, already trimmed server-side. A client
    # may not add to this list or trim it further.
    options_shown: list[str] = Field(default_factory=list)
    co_narrate: str = ""


class PresentationBlock(BaseModel):
    """The screen for this turn, decided from the age band and how it is going."""

    choices_shown: int = 2
    touch_target_px: int = 64
    text_density: str = "none"
    decoration: str = "on"
    motion: str = "normal"
    narration_speed: float = 1.0


class SpeechBlock(BaseModel):
    text: str = ""
    language: str = "en"
    speak: bool = True
    voice_speed: float = 1.0
    # "template" or "llm" - so a session can be read back and the model's
    # contribution separated from the app's own words.
    source: Literal["template", "llm"] = "template"


class NextInput(BaseModel):
    """What the client should wait for, and what to report if it never comes.

    The timeout comes from the manifest's own `idle_thresholds_seconds` for the
    age band, and `on_timeout` is the input kind to send back. The client runs a
    timer; the server decides what silence means.
    """

    expects: InputKind = "tap"
    timeout_ms: int = 15000
    on_timeout: InputKind = "idle"


class ProgressBlock(BaseModel):
    """Progress as a child can read it: a bag with things in it, not a percentage."""

    shape: str = "bag"
    filled: int = 0
    total: int = 0


class CloseBlock(BaseModel):
    """Set only on the last directive of a sitting."""

    # "day_complete" is not the same as "completed": the sitting did not end,
    # the day did. The child has finished everything today's plan holds, and the
    # next level opens tomorrow rather than now.
    reason: Literal["completed", "day_complete", "end_kindly", "paused", "session_overrun"] = "completed"
    stars_earned: int = 0
    topic_completed: bool = False
    revisit_skill_id: str | None = None


class ConductorDirective(BaseModel):
    session_id: str
    child_id: str
    topic_id: str
    phase: Phase
    activity: Activity | None = None
    scaffold: ScaffoldBlock = Field(default_factory=ScaffoldBlock)
    presentation: PresentationBlock = Field(default_factory=PresentationBlock)
    speech: SpeechBlock = Field(default_factory=SpeechBlock)
    avatar: AvatarPayload
    visual_action: GuideVisualAction = Field(default_factory=GuideVisualAction)
    next_input: NextInput = Field(default_factory=NextInput)
    progress: ProgressBlock = Field(default_factory=ProgressBlock)
    # Set when the guide is talking and nothing is expected of the child, so the
    # class carries on by itself. This is what removes the "next" button.
    auto_advance_in_ms: int | None = None
    close: CloseBlock | None = None
    # Diagnostics for the parent surface and the tests. Never rendered to a child.
    branch: str | None = None
    teaching_strategy: str | None = None
