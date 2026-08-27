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

Phase = Literal["greet", "set", "i_do", "say_it", "we_do", "you_do", "check", "branch", "close"]


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
    # The recogniser's other guesses at the same utterance, best first. A child
    # saying "A" is very often the second alternative and the first is a word
    # the recogniser preferred; handing them all over costs nothing and rescues
    # answers that would otherwise be scored as a mishearing.
    alternatives: list[str] = Field(default_factory=list, max_length=5)


class ConductorOpenRequest(BaseModel):
    """How the class is opened. Empty for the child's own class.

    `topic_id` is only ever sent by the Adventure map, where a grown-up has
    picked a level to sit through. It says *which* topic to conduct; it does not
    bypass the day's plan, and it is not a child-facing choice.
    """

    topic_id: str | None = None


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


class ListenBlock(BaseModel):
    """Set whenever the microphone should be open for this turn.

    The client opens the mic because this says to, closes it on `timeout_ms`
    from `next_input`, and reports what it heard. It decides nothing else: not
    whether the child was right, not whether to ask again, and not what silence
    meant. `expect` is a hint for the recogniser and for the child's own screen
    - never a thing to check the transcript against on the device.
    """

    active: bool = False
    # The thing the child is being asked to say, as it should be shown: "A".
    expect: str = ""
    # Words to bias the recogniser towards. Never contains the answer to a
    # question - the mic is only ever open on a teaching card or on an activity
    # whose answer is spoken by design.
    contextual_strings: list[str] = Field(default_factory=list)
    language: str = "en"
    # Which try this is, and how many there will be. The client shows neither;
    # they are here so a session can be read back.
    attempt: int = 0
    max_attempts: int = 2
    # A child who is not going to speak is never trapped: after this the client
    # reports `idle` and the server decides what the silence meant.
    hold_open_ms: int = 8000


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
    listen: ListenBlock = Field(default_factory=ListenBlock)
    progress: ProgressBlock = Field(default_factory=ProgressBlock)
    # Set when the guide is talking and nothing is expected of the child, so the
    # class carries on by itself. This is what removes the "next" button.
    auto_advance_in_ms: int | None = None
    close: CloseBlock | None = None
    # Diagnostics for the parent surface and the tests. Never rendered to a child.
    branch: str | None = None
    teaching_strategy: str | None = None
    # What the conductor made of an utterance that was not an answer -
    # "dont_know", "chatter", "distress". Diagnostics, like `branch`.
    heard_as: str | None = None
