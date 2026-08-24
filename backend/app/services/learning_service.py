"""Topic-level learning sessions.

A lesson is one topic from the manifest. Correctness, scoring, stars and topic
unlocking are all deterministic: the evaluator registry decides right or wrong,
the topic's own passing score decides completion. No model is consulted for any
of it.
"""

import random
from uuid import UUID, uuid4

from app.schemas.child import ChildProfile
from app.schemas.curriculum import Topic
from app.schemas.learning import Activity, LearningAnswerRequest, LearningResponse, LearningStartRequest
from app.db.repositories import awards
from app.db.session import session_scope
from app.services import (
    activity_evaluators,
    child_store,
    curriculum_service,
    plan_service,
    retention_service,
)
from app.services.avatar_service import learning_avatar
from app.services.child_service import (
    get_child_record,
    refresh_certificate_eligibility,
    subject_progress,
)
from app.services.content_generator import get_content_generator
from app.config import get_settings
from app.services.errors import app_error
from app.services.history_service import record_attempt
from app.services.learning_memory_service import record_completed_lesson

# One sitting, in flight. This is the only thing about a lesson that is still
# kept in memory, and it is the right thing to keep there: it is the cursor into
# a lesson the child is playing right now, and it is rebuilt by starting the
# topic again. Everything a restart must not lose - the answers, the mastery
# they moved, the stars, the unlock board, the certificate - is written to the
# database as it happens.
_active_lessons: dict[str, dict] = {}

CORRECT_FEEDBACK = [
    "Great work! Here is the next one.",
    "Well done! Let us keep going.",
    "You got it! On to the next question.",
    "Brilliant! Ready for the next one?",
    "Wonderful! Here comes another.",
    "Amazing work! Next question coming up.",
    "Superb! Let us try the next one.",
    "Nice work! Keep going.",
]

TOPIC_COMPLETE_SUCCESS = [
    "Wonderful work! This topic is complete.",
    "You finished the topic! Great effort.",
    "Topic done! What an achievement.",
    "All complete! You were fantastic.",
]

TOPIC_COMPLETE_NEEDS_PRACTICE = [
    "Let us practise this one a little more.",
    "You tried hard! A little more practice will help.",
    "Almost there! Let us practise and come back stronger.",
]

WRONG_ATTEMPT_2 = [
    "Almost there! Let us look again with fresh eyes. ",
    "You are so close! Let us try once more. ",
    "Almost. Keep going! ",
    "Do not worry. Let us look at this together. ",
]

WRONG_ATTEMPT_3_PLUS = [
    "Good try. We can practise this together slowly.",
    "No worries! Let us break it down step by step.",
    "Take your time. We will get there together.",
]

STARS_PER_CORRECT = 3
PERFECT_SCORE_BONUS = 3

# How many activities one lesson plays. A topic carries many more than this on
# purpose — see `_lesson_activities`.
LESSON_LENGTH = 6


def lesson_activities(topic: Topic, seed: str) -> list[Activity]:
    """One lesson is a sample of its topic, not the whole of it.

    A topic holds many examples of the same skill so that the adventure and
    Practice can ask different questions about it. Playing every one of them in
    a single sitting would make a lesson far too long for a two-year-old, so a
    lesson keeps the topic's teaching and samples its questions, always in the
    authored order. Coming back to the topic seeds differently and meets
    different questions.

    Teaching cards — "this is B, B is for ball" — are the spine of the lesson
    and are never sampled away while a question still fits. Dropping one would
    ask a child about a letter nobody showed them.
    """
    activities = curriculum_service.get_activities(topic.topic_id)
    if topic.lesson_flow == "complete" or len(activities) <= LESSON_LENGTH:
        # A "complete" topic is a method, not a pool: meet the letter, find it,
        # say it, write it. Dropping any step would leave the method half taught,
        # so the whole sequence is played and the level passes only at its end.
        return activities

    rng = random.Random(seed)
    teaching = [a for a in activities if not activity_evaluators.requires_answer(a.type)]
    questions = [a for a in activities if activity_evaluators.requires_answer(a.type)]

    if len(teaching) < LESSON_LENGTH and questions:
        keep = {a.activity_id for a in teaching}
        keep |= {a.activity_id for a in rng.sample(questions, LESSON_LENGTH - len(teaching))}
    else:
        # A topic that is almost all watching and doing has no spine to protect.
        keep = {a.activity_id for a in rng.sample(activities, LESSON_LENGTH)}
    return [a for a in activities if a.activity_id in keep]


def _session_activities(session: dict) -> list[Activity]:
    """The activities this session drew when it started, in order."""
    by_id = {a.activity_id: a for a in curriculum_service.get_activities(session["topic_id"])}
    return [by_id[activity_id] for activity_id in session["activity_ids"] if activity_id in by_id]


def skill_slug(topic: Topic) -> str:
    return f"{topic.subject_id}:{topic.topic_id}"


def forms_available(topic: Topic) -> int:
    """Distinct question forms the curriculum holds for this topic.

    The mastery gate asks for two forms where two exist and one where only one
    does. This is where "how many exist" is known - the repository deliberately
    does not read the curriculum - so it is counted here and stored on the row.
    """
    types = {
        activity.type
        for activity in curriculum_service.get_activities(topic.topic_id)
        if activity_evaluators.requires_answer(activity.type)
    }
    return max(1, len(types))


def _check_access(child: dict, topic: Topic) -> None:
    if topic.class_id != child["class_id"]:
        raise app_error("LOCKED_STAGE", "That topic belongs to a different class.", 403)
    if not topic.available:
        raise app_error(
            "TOPIC_NOT_READY",
            "This topic is still being prepared. Let us try another one.",
            409,
        )
    if topic.topic_id not in subject_progress(child, topic.subject_id)["unlocked_topics"]:
        raise app_error("LOCKED_STAGE", "This topic is not unlocked yet.", 403)

    # Unlocked is not the same as today's. Finishing a level opens the next one,
    # and the next one is in tomorrow's plan - so the child comes back to it
    # tomorrow instead of running through a subject in one sitting.
    gate = plan_service.may_open(ChildProfile(**child), topic.topic_id)
    if not gate.allowed:
        raise app_error("NOT_TODAYS_PLAN", gate.message, 403)


def _next_topic(topic: Topic) -> Topic | None:
    """The next topic in the same subject, by sort order."""
    subject = curriculum_service.get_subject(topic.subject_id)
    ordered = subject.topics
    index = next(i for i, t in enumerate(ordered) if t.topic_id == topic.topic_id)
    return ordered[index + 1] if index + 1 < len(ordered) else None


def start_learning(payload: LearningStartRequest) -> LearningResponse:
    """Open a sitting on one topic.

    The child record is written back before the response is returned: the
    services above mutate the record in place, exactly as they did when it was a
    dictionary, and this is what makes the mutation outlive the process.
    """
    response = _start_learning(payload)
    child_store.save(get_child_record(payload.child_id))
    return response


def _start_learning(payload: LearningStartRequest) -> LearningResponse:
    child = get_child_record(payload.child_id)
    topic = curriculum_service.get_topic(payload.topic_id)
    _check_access(child, topic)

    session_id = f"learn_{uuid4()}"
    activities = lesson_activities(topic, session_id)
    _active_lessons[session_id] = {
        "session_id": session_id,
        "child_id": payload.child_id,
        "class_id": topic.class_id,
        "subject_id": topic.subject_id,
        "topic_id": topic.topic_id,
        "activity_ids": [activity.activity_id for activity in activities],
        "activity_index": 0,
        "attempt_number": 0,
        "correct_count": 0,
        "correct_streak": 0,
        "topic_completed": False,
    }

    child["current_subject_id"] = topic.subject_id
    child["current_topic_id"] = topic.topic_id
    progress = subject_progress(child, topic.subject_id)
    progress["current_topic_id"] = topic.topic_id

    generator = get_content_generator(get_settings().llm_provider)
    # A Hindi lesson is introduced in Hindi. The language comes from the
    # subject in the manifest, so this needs no per-subject special case.
    tutor_response = generator.tutor_intro(child["name"], topic.title, topic.language)
    return _response(
        _active_lessons[session_id],
        topic,
        activity=activities[0],
        tutor_response=tutor_response,
    )


def continue_learning(session_id: str) -> LearningResponse:
    session = _session(session_id)
    topic = curriculum_service.get_topic(session["topic_id"])
    activities = _session_activities(session)
    activity = None if session["topic_completed"] else activities[session["activity_index"]]
    return _response(session, topic, activity=activity)


def retry_learning(session_id: str) -> LearningResponse:
    return continue_learning(session_id)


def _session(session_id: str) -> dict:
    session = _active_lessons.get(session_id)
    if not session:
        raise app_error("EXPIRED_LEARNING_SESSION", "Let us start this topic again.", 404)
    return session


def answer_learning(payload: LearningAnswerRequest) -> LearningResponse:
    """Grade one answer. Stars, unlocks and the certificate all move under here,
    so the record is saved once, on the way out, whichever branch answered."""
    response = _answer_learning(payload)
    child_store.save(get_child_record(response.child_id))
    return response


def _answer_learning(payload: LearningAnswerRequest) -> LearningResponse:
    session = _session(payload.session_id)
    if session["topic_completed"]:
        return continue_learning(payload.session_id)

    child = get_child_record(session["child_id"])
    topic = curriculum_service.get_topic(session["topic_id"])
    activities = _session_activities(session)
    activity = activities[session["activity_index"]]

    is_correct, normalized_answer = activity_evaluators.evaluate(
        activity_evaluators.EvaluationInput(
            activity_type=activity.type,
            correct_answer=activity.correct_answer or "",
            options=activity.options,
            answer=payload.answer,
            accepted_answers=tuple(activity.accept),
            open_ended=activity.open_ended,
        )
    )

    next_attempt_number = 0 if is_correct else session["attempt_number"] + 1
    skill_id = skill_slug(topic)
    record_attempt(
        child_id=session["child_id"],
        session_id=session["session_id"],
        activity_id=activity.activity_id,
        topic=topic.topic_id,
        skill=skill_id,
        level_id=topic.subject_id,
        child_answer=normalized_answer,
        is_correct=is_correct,
        attempt_number=next_attempt_number,
        # The question's *form*, not its id. Two forms of the same skill are
        # what the mastery gate asks for, and what makes a passed retention
        # probe evidence of transfer rather than of recall.
        form_signature=activity.type,
        forms_available=forms_available(topic),
    )
    # A correct answer schedules the probe that will pay for however the child
    # was taught this skill; an answer to a probe that has come due settles it.
    # Neither happens inside this turn: the reward is deliberately days late.
    retention_service.on_attempt(
        child_id=session["child_id"],
        skill_id=skill_id,
        form_signature=activity.type,
        is_correct=is_correct,
    )

    if is_correct:
        child["stars"] += STARS_PER_CORRECT
        session["correct_count"] += 1
        session["correct_streak"] += 1
        session["attempt_number"] = 0
        session["activity_index"] += 1
        if session["activity_index"] >= len(activities):
            return _complete_topic(session, child, topic, activities, stars_earned=STARS_PER_CORRECT)

        streak = session["correct_streak"]
        feedback = random.choice(CORRECT_FEEDBACK)
        if streak >= 3:
            feedback = f"{feedback} {streak} correct in a row!"
        return _response(
            session,
            topic,
            activity=activities[session["activity_index"]],
            is_correct=True,
            feedback=feedback,
            stars_earned=STARS_PER_CORRECT,
        )

    session["attempt_number"] += 1
    session["correct_streak"] = 0

    if session["attempt_number"] >= 4:
        mark_weak(child, topic)
        session["attempt_number"] = 0
        session["activity_index"] = (session["activity_index"] + 1) % len(activities)
        return _response(
            session,
            topic,
            activity=activities[session["activity_index"]],
            is_correct=False,
            feedback="Let us try a different question now.",
            recommended_practice=True,
            question_changed=True,
        )

    generator = get_content_generator(get_settings().llm_provider)
    if session["attempt_number"] == 1:
        feedback = generator.hint(activity.hint, topic.language)
    elif session["attempt_number"] == 2:
        feedback = random.choice(WRONG_ATTEMPT_2) + activity.hint
    else:
        mark_weak(child, topic)
        feedback = random.choice(WRONG_ATTEMPT_3_PLUS)

    return _response(
        session,
        topic,
        activity=activity,
        is_correct=False,
        feedback=feedback,
        recommended_practice=session["attempt_number"] >= 3,
    )


def mark_weak(child: dict, topic: Topic) -> None:
    skill = skill_slug(topic)
    if skill not in child["weak_skills"]:
        child["weak_skills"].append(skill)


def _complete_topic(
    session: dict,
    child: dict,
    topic: Topic,
    activities: list[Activity],
    stars_earned: int,
) -> LearningResponse:
    score = round((session["correct_count"] / len(activities)) * 100)
    session["score"] = score
    award = award_topic_completion(child, topic, score=score)
    session["topic_completed"] = award["passed"]

    return _response(
        session,
        topic,
        activity=None,
        is_correct=True,
        feedback=award["feedback"],
        stars_earned=stars_earned + award["topic_reward"] + award["perfect_bonus"],
        topic_completed=award["passed"],
        next_topic_id=award["next_topic_id"],
        next_topic_unlocked=award["next_topic_unlocked"],
        recommended_practice=award["recommended_practice"],
        complete=True,
    )


def award_topic_completion(child: dict, topic: Topic, *, score: int) -> dict:
    """Score a finished lesson: stars, completion, the next topic, the certificate.

    Extracted so the Conductor can end a lesson through exactly the same code the
    older `/learning` endpoints use. Two implementations of "did this topic
    pass?" would be two answers to the only question the child actually cares
    about, and one of them would drift.

    Every line of it is deterministic - the topic's own `passing_score` decides,
    the manifest's `star_reward` pays, and the next topic in sort order opens. No
    model is consulted, here or anywhere upstream.
    """
    progress = subject_progress(child, topic.subject_id)
    progress["scores"][topic.topic_id] = score
    passed = score >= topic.passing_score

    topic_reward = 0
    perfect_bonus = 0
    next_topic_unlocked = False
    next_topic = _next_topic(topic)

    if score == 100:
        perfect_bonus = PERFECT_SCORE_BONUS
        child["stars"] += perfect_bonus

    if passed:
        if topic.topic_id not in progress["completed_topics"]:
            progress["completed_topics"].append(topic.topic_id)
        topic_reward = topic.star_reward
        child["stars"] += topic_reward

        if next_topic is not None:
            if next_topic.topic_id not in progress["unlocked_topics"]:
                progress["unlocked_topics"].append(next_topic.topic_id)
                next_topic_unlocked = True
            progress["current_topic_id"] = next_topic.topic_id
            child["current_topic_id"] = next_topic.topic_id
        else:
            _complete_subject(child, topic.subject_id)

        record_completed_lesson(
            child_id=child["child_id"],
            subject_id=topic.subject_id,
            topic_id=topic.topic_id,
            title=topic.title,
            score=score,
        )
        _refresh_certificate(child)
        feedback = (
            "All correct! Every answer was right."
            if score == 100
            else random.choice(TOPIC_COMPLETE_SUCCESS)
        )
        recommended_practice = 70 <= score < 80
    else:
        mark_weak(child, topic)
        feedback = random.choice(TOPIC_COMPLETE_NEEDS_PRACTICE)
        recommended_practice = True

    return {
        "passed": passed,
        "score": score,
        "topic_reward": topic_reward,
        "perfect_bonus": perfect_bonus,
        "next_topic_id": next_topic.topic_id if next_topic else None,
        "next_topic_unlocked": next_topic_unlocked,
        "feedback": feedback,
        "recommended_practice": recommended_practice,
    }


def _complete_subject(child: dict, subject_id: str) -> None:
    """A subject is finished when its last playable topic passes."""
    subject = curriculum_service.get_subject(subject_id)
    progress = subject_progress(child, subject_id)
    playable = [t.topic_id for t in subject.topics if t.available]
    if not playable or not all(t in progress["completed_topics"] for t in playable):
        return
    if subject_id not in child["completed_subjects"]:
        child["completed_subjects"].append(subject_id)
    badge = f"{subject.title} Explorer"
    if badge not in child["rewards"]:
        child["rewards"].append(badge)


def _refresh_certificate(child: dict) -> None:
    """Issue the class certificate once every playable topic is complete.

    Eligibility is a pure function of the child's own completed topics -
    `refresh_certificate_eligibility` - and the row is written from that verdict.
    No model is consulted, here or upstream of here.
    """
    if not refresh_certificate_eligibility(child):
        return
    detail = curriculum_service.get_class(child["class_id"])
    with session_scope() as session:
        awards.issue(
            session,
            child_id=UUID(child["child_id"]),
            subject_id=child["class_id"],
            title=f"Completed the {detail.title} curriculum",
        )


def seed_demo_child(child_id: str) -> dict:
    """Development helper: unlock and complete every playable topic in the
    child's class so the later screens can be demonstrated."""
    child = get_child_record(child_id)
    detail = curriculum_service.get_class(child["class_id"])
    for subject in detail.subjects:
        progress = subject_progress(child, subject.subject_id)
        playable = [t.topic_id for t in subject.topics if t.available]
        progress["unlocked_topics"] = [t.topic_id for t in subject.topics]
        progress["completed_topics"] = list(playable)
        progress["scores"] = {topic_id: 100 for topic_id in playable}
        progress["current_topic_id"] = subject.topics[-1].topic_id if subject.topics else None
        if playable:
            _complete_subject(child, subject.subject_id)
    child["stars"] = max(child["stars"], 80)
    _refresh_certificate(child)
    child_store.save(child)
    from app.services.child_service import get_child

    return get_child(child_id).model_dump()


def _response(
    session: dict,
    topic: Topic,
    activity: Activity | None,
    tutor_response: str | None = None,
    is_correct: bool | None = None,
    feedback: str = "",
    stars_earned: int = 0,
    topic_completed: bool = False,
    next_topic_id: str | None = None,
    next_topic_unlocked: bool = False,
    recommended_practice: bool = False,
    question_changed: bool = False,
    complete: bool = False,
) -> LearningResponse:
    # Out of the lesson the child is actually playing, not the whole topic.
    total = len(session.get("activity_ids") or ()) or topic.activity_count or 1
    score = session.get("score", round((session["correct_count"] / total) * 100))
    intro = tutor_response or f"Let us look at {topic.title}."
    mode = curriculum_service.experience_mode_for_class(topic.class_id)
    return LearningResponse(
        session_id=session["session_id"],
        child_id=session["child_id"],
        class_id=topic.class_id,
        subject_id=topic.subject_id,
        topic_id=topic.topic_id,
        topic_title=topic.title,
        experience_mode=mode.mode_id,
        tutor_response=intro,
        activity=activity,
        activity_index=min(session["activity_index"], total),
        activity_total=total,
        is_correct=is_correct,
        attempt_number=session["attempt_number"],
        feedback=feedback,
        stars_earned=stars_earned,
        current_score=score,
        topic_completed=topic_completed,
        next_topic_id=next_topic_id,
        next_topic_unlocked=next_topic_unlocked,
        recommended_practice=recommended_practice,
        question_changed=question_changed,
        complete=complete,
        avatar=learning_avatar(
            is_correct=is_correct,
            feedback=feedback,
            tutor_response=intro,
            complete=complete,
            next_stage_unlocked=next_topic_unlocked,
            recommended_practice=recommended_practice,
        ),
    )
