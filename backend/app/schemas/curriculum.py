"""Curriculum taxonomy shapes: class -> subject -> topic -> subtopic.

Subject maps to the "level" concept and topic maps to "lesson" in
docs/backend-architecture.md 3.2. The names here follow the CBSE syllabus so the
manifest and the API read the same way.
"""

from pydantic import BaseModel


class ExperienceMode(BaseModel):
    """Presentation rules for an age band. Enforced server-side, not suggested."""

    mode_id: str
    applies_to: list[str]
    touch_target_px: int
    max_choices_per_screen: int
    text_density: str
    voice: str
    idle_thresholds_seconds: list[int]


class Topic(BaseModel):
    topic_id: str
    subject_id: str
    class_id: str
    title: str
    icon: str = "⭐"
    sort_order: int
    subtopics: list[str] = []
    # One emoji per subtopic, in the same order, when the manifest authors them.
    # Empty means "no icons authored" — never a partial list, the loader rejects
    # a length mismatch so a card cannot pair a subtopic with someone else's icon.
    subtopic_icons: list[str] = []
    # One plain-language line per subtopic, in the same order, saying what the
    # subtopic actually means to a five-year-old and the grown-up beside them —
    # "Bada muh hamesha bade number ki taraf" for the > and < signs. Same
    # all-or-nothing rule as the icons above.
    subtopic_easy: list[str] = []
    # The whole topic in one friendly line, in the syllabus's own words. Sits
    # beside `objective`, which stays the grown-up summary of what is taught.
    easy_line: str | None = None
    activity_count: int = 0
    available: bool = False
    # Scoring is deterministic and data-driven. A topic may override the
    # defaults in the manifest; nothing here is decided by a model.
    passing_score: int = 80
    star_reward: int = 10
    # Set by the authored activity file, not the taxonomy.
    objective: str | None = None
    intro_message: str | None = None
    # How this topic is taught:
    #   digital        - fully teachable on screen
    #   hybrid         - screen introduces it, a physical action completes it
    #   parent_guided  - physical only; the app shows the grown-up a card
    delivery: str = "digital"
    # How much of the topic one lesson plays:
    #   sample    - the lesson keeps the teaching and samples the questions, so
    #               a long topic stays short and varies between visits
    #   complete  - every activity, in order. For a topic that is a designed
    #               sequence rather than a pool: meet the letter, find it, say
    #               it, write it. Sampling that would drop a step of the method.
    lesson_flow: str = "sample"
    # The language this topic is taught in, from its subject in the manifest.
    # The tutor and the guide answer in it, so a Hindi lesson is not narrated in
    # English. Not a UI setting: it belongs to the content, not the child.
    language: str = "en"


class Subject(BaseModel):
    subject_id: str
    class_id: str
    title: str
    # The child-facing name for the same subject — "Number Fun" for Basic
    # Mathematics. The syllabus title stays authoritative for grown-ups; this is
    # what a four-year-old is shown when the manifest gives one.
    fun_name: str | None = None
    # "en" unless the manifest says otherwise. A subject that teaches another
    # language declares it once, here, and everything downstream follows.
    language: str = "en"
    # Presentation lives in the manifest so adding a subject brings its look
    # with it, and the frontend keeps no curriculum names of its own.
    icon: str = "📚"
    accent: str = "leaf"
    # An exact brand colour for a subject that wants one. The accent above stays
    # the fallback, so a subject without a colour still renders in the palette.
    colour: str | None = None
    note: str | None = None
    # What the subject is, in a line a child can follow. `note` stays the
    # editorial note for a grown-up reading the manifest — why a subject was
    # regrouped — which is not the same thing and does not belong on a card.
    easy_line: str | None = None
    sort_order: int
    topic_count: int = 0
    subtopic_count: int = 0
    activity_count: int = 0
    available: bool = False
    topics: list[Topic] = []


class ClassSummary(BaseModel):
    class_id: str
    code: str
    title: str
    subtitle: str | None = None
    min_age: int
    max_age: int
    experience_mode: str
    sort_order: int
    pedagogy: str | None = None
    subject_count: int = 0
    topic_count: int = 0
    subtopic_count: int = 0
    activity_count: int = 0


class ClassDetail(ClassSummary):
    experience: ExperienceMode
    # Subjects dropped from the published syllabus by product decision, recorded
    # so a reader can tell a deliberate removal from a gap in extraction.
    removed_subjects: list[str] = []
    removed_subject_ids: list[str] = []
    subjects: list[Subject] = []


class CurriculumOverview(BaseModel):
    version: str
    source: str
    classes: list[ClassSummary] = []
    experience_modes: dict[str, ExperienceMode] = {}


class ClassResolution(BaseModel):
    """How the server decided which class a child belongs in."""

    class_id: str
    age_years: float
    resolved_from: str
    overridden: bool = False
    default_class_id: str | None = None


class TopicNotes(BaseModel):
    """One level's revision notes, for the Adventure map to show and say.

    Every line was typed by the person who wrote the syllabus - no model is
    anywhere upstream of this - so the same level reads the same on every
    afternoon, which is what a child going back over something actually needs.

    `lines` is both what is shown and what is read aloud. There is deliberately
    not a separate script: two versions of the same notes drift, and the one the
    child hears would stop being the one on the screen. `speech` is those lines
    joined, ready for the narrator.

    Nothing here is a lesson. Reading it marks nothing, scores nothing, unlocks
    nothing and does not move the day's plan.
    """

    topic_id: str
    title: str
    lines: list[str] = []
    # Asset tokens the client draws - the everyday things the author named
    # beside this level. Never a letter, number, shape or colour: those are the
    # lesson's own furniture rather than an example of it.
    example_items: list[str] = []
    # The picture of the concept itself, named rather than drawn: the client
    # owns the SVG. Empty when the app has no drawing for it.
    visual_kind: str = ""
    visual_value: str = ""
    speech: str = ""
    # False when the author has written nothing to revise from yet - a level
    # that is all tracing, or one still being authored. The page says so kindly
    # rather than inventing encouragement to fill the space.
    has_notes: bool = False


class GameOption(BaseModel):
    """One thing a child can tap in a level's game.

    `token` is the asset name the author wrote - the client turns it into a
    picture and draws nothing at all for one it has no artwork for. `label` is
    what the button says, the author's own words with their own emoji on it.
    """

    token: str
    label: str


class GameRound(BaseModel):
    """One asking, and which of its options is right.

    `answer` is an index, never a word: the server decided it with
    `stage.contains_answer`, the same rule the class uses to choose which
    options may be shown and to mark a tap. A game that shows the answer and
    then marks it wrong is worse than no game.
    """

    ask: str
    say: str
    options: list[GameOption] = []
    answer: int = 0


class LevelGame(BaseModel):
    """One playable game about one level, built from the authored syllabus."""

    topic_id: str
    game_id: str
    kind: str
    title: str
    blurb: str
    icon: str
    rounds: list[GameRound] = []
    # The matching game's pack: one token per pair, dealt twice by the client.
    tokens: list[str] = []


class TopicGames(BaseModel):
    """The games a level can offer, which is at most three and sometimes fewer.

    Nothing here is a lesson. Playing marks nothing, scores nothing, unlocks
    nothing and does not move the day's plan - the class is still the AI Teacher
    and the schedule still decides when a level is taught. A level whose author
    wrote too little comes back with fewer games rather than an invented one.
    """

    topic_id: str
    title: str
    games: list[LevelGame] = []


class ClassOverrideRequest(BaseModel):
    session_token: str
    class_id: str
