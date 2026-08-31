from pydantic import BaseModel

from app.schemas.avatar import AvatarPayload


class Activity(BaseModel):
    activity_id: str
    type: str
    prompt: str
    visual_items: list[str] = []
    options: list[str] = []
    # One emoji per option, in the same order, when the author wrote them. A
    # two-year-old reads the picture on the button long before the word beside
    # it, so these are content and not decoration; an empty list means the
    # author wrote none, never a partial list.
    option_emojis: list[str] = []
    # Null for watch/listen/trace activities, which have no right answer.
    correct_answer: str | None = None
    hint: str = ""
    difficulty: str = "easy"
    # Filled by the loader from the evaluator registry so the client never has
    # to infer how an activity is answered from its type name.
    answer_kind: str = "choice"

    # --- optional authoring fields -------------------------------------
    # The skill this activity practises, used to weight practice selection.
    skill_id: str | None = None
    # Extra spellings accepted for a spoken answer, e.g. "a" / "aa" / "ah".
    accept: list[str] = []
    min_similarity: float | None = None
    # A prompt with no single right answer, e.g. "tell me your name".
    open_ended: bool = False
    # Trace activities: what to draw and how close is close enough. Judged on
    # the device from the gesture, never by a model.
    trace_target: str | None = None
    min_accuracy: float | None = None
    # Shown to the grown-up for a physical-world activity.
    parent_note: str | None = None


class LearningStartRequest(BaseModel):
    child_id: str
    topic_id: str


class LearningAnswerRequest(BaseModel):
    session_id: str
    answer: str


class LearningResponse(BaseModel):
    session_id: str
    child_id: str
    class_id: str
    subject_id: str
    topic_id: str
    topic_title: str
    experience_mode: str
    tutor_response: str
    activity: Activity | None = None
    activity_index: int = 0
    activity_total: int = 0
    is_correct: bool | None = None
    attempt_number: int = 0
    feedback: str = ""
    stars_earned: int = 0
    current_score: int = 0
    topic_completed: bool = False
    next_topic_id: str | None = None
    next_topic_unlocked: bool = False
    recommended_practice: bool = False
    question_changed: bool = False
    complete: bool = False
    avatar: AvatarPayload | None = None
