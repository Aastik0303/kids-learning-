"""What the AI Teacher answers with.

One shape for every turn, like the conductor's directive: the client renders it
and reports what the child said. It decides nothing - not whether the answer was
right, not which of a question's three turns this is, not when the stage moves,
and not when the day is over. `expects: "done"` with `day_complete` is the server
saying the class is shut until tomorrow, and the client's whole job with it is to
say so.

**There is no score in here.** The points the AI Teacher used to keep are gone,
so a client that drew a number going up and down beside a four-year-old has
nothing left to draw it from. What is left is `questions_asked` of
`questions_per_stage` - progress through the five, and progress only.
"""

from pydantic import BaseModel


class TeacherTurnResponse(BaseModel):
    session_id: str
    child_id: str
    # --- where in the day and the stage this is, decided server-side -----
    # Which item of today's frozen plan this is, and how many the day holds.
    # A stage is a level out of the schedule, so these two numbers *are* the
    # schedule as the child sees it.
    stage: int
    stages_total: int = 0
    # How many of the stage's five questions have been settled, and how many
    # there are. Not a score: it only ever goes up, and a question that had to be
    # answered for the child counts the same as one they got.
    questions_asked: int
    questions_per_stage: int
    # --- what is being taught -------------------------------------------
    topic_id: str
    topic_title: str
    speech: str
    question: str
    # Which of the nine strategies this turn used, and whether the words came
    # from the model or from the notes themselves.
    strategy: str
    source: str
    # "embeddings" or "keyword" - which retriever answered.
    retrieval: str
    # Where in the lesson this turn is: "explain" / "say_it" / "draw" / "match"
    # / "quiz", and what the client should collect for it - "ready", "voice",
    # "trace" or "tap". The client renders the step; it never chooses one.
    step: str = "explain"
    expects: str = "ready"
    step_index: int = 0
    steps_total: int = 5
    # Which of the question's three turns this is. 1 asks it; 2 asks it again
    # with `is_hint` set, a deeper explanation and the choices to pick from;
    # 3 has `is_reveal` set, tells the child the answer and expects nothing back
    # but "ready". A reveal is never marked, because it was not a test.
    attempt: int = 1
    attempts_allowed: int = 2
    is_hint: bool = False
    is_reveal: bool = False
    # What to trace, on the drawing step.
    trace_target: str = ""
    # What the child may tap. Empty when the question wants a spoken answer.
    # Which one is right is never said here: the server marks the answer.
    options: list[str] = []
    # The picture beside the explanation, named rather than drawn: the kind
    # ("letter", "number", "count", "shape", "colour") and its value. Empty when
    # this turn has no picture. The client owns the SVG; nothing here is markup.
    visual_kind: str = ""
    visual_value: str = ""
    # The everyday things the author named beside this level, as asset tokens
    # the client draws - `apple` beside the letter A. The explanation itself is
    # spoken and not shown, so this is what the child actually looks at, and it
    # is never the answer to the question on the screen.
    example_items: list[str] = []
    # The everyday words the class may never illustrate while it speaks: the
    # examples belonging to this concept's *siblings*. A teacher explaining the
    # triangle says "not round like a ball" and the class was drawing the ball -
    # the circle's picture on the triangle's card. Whose picture a word is is
    # the server's to know; the client only has a table of pictures.
    not_examples: list[str] = []
    # This stage is a poem, not a level. Every fifth day one subject's level
    # steps aside for one: `step` is "poem", `expects` is always "ready", and
    # nothing about it is asked, marked, scored, unlocked or paid.
    is_poem: bool = False
    # --- the answer just given, when there was one -----------------------
    feedback: str = ""
    # Whether the answer just given was right. `None` on a turn that was not an
    # answer at all - including the one that settled a question by explaining it.
    is_correct: bool | None = None
    advanced: bool = False
    # --- the check-in on something taught two days ago --------------------
    # True when this turn is a retention test rather than a lesson: a concept
    # taught two days ago, asked about with a *different* question. `step` is
    # "retention" and the client renders it like any other question. Nothing
    # about answering it is marked into the stage or reaches a star; what it
    # moves is the Q-value of the teaching turn that earned it.
    is_retention_test: bool = False
    retention_test_id: str = ""
    # How many more check-ins the sitting opened with, after this one.
    retention_remaining: int = 0
    # --- the day, and what the last stage did to the Adventure map --------
    # Every stage of today's plan is through. There is nothing to answer and
    # nothing to open; the next lesson is tomorrow's.
    day_complete: bool = False
    # The level just finished passed, and what that unlocked. Decided by
    # `learning_service.award_topic_completion`, never here and never by a model.
    topic_completed: bool = False
    next_topic_unlocked: bool = False
    stars_earned: int = 0


class TeacherAnswerRequest(BaseModel):
    answer: str = ""


class TeacherAskRequest(BaseModel):
    """Something the child asked of their own accord, rather than an answer."""

    question: str = ""
