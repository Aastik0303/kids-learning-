import random

from app.schemas.avatar import AvatarPayload


CORRECT_MESSAGES = [
    "Nice work! You found it.",
    "Amazing! That is right.",
    "Great job!",
    "Well done! You did it.",
    "Hooray! That is correct.",
    "Wonderful work!",
    "Great listening!",
    "Super work!",
    "Nice counting!",
    "Awesome work!",
    "Excellent effort.",
    "Fantastic! Here comes the next one.",
]

HINT_MESSAGES = [
    "Good try. Look slowly and try once more.",
    "Almost! Take another careful look.",
    "Almost. Let us look at this together.",
    "So close! Think about it one more time.",
    "Good try. Look carefully again.",
    "Keep going! You are getting closer.",
    "Hmm, not that one. Let us try once more.",
    "Let us try again. You can do this!",
]

COMPLETE_MESSAGES = [
    "Level complete. Wonderful work!",
    "All done! Nice work.",
    "You finished! What an achievement.",
    "Stage complete! Great effort.",
]


def learning_avatar(
    *,
    is_correct: bool | None,
    feedback: str,
    tutor_response: str = "",
    complete: bool = False,
    next_stage_unlocked: bool = False,
    recommended_practice: bool = False,
) -> AvatarPayload:
    if complete:
        if next_stage_unlocked:
            effect = "level_unlock"
            state = "celebrating"
        else:
            effect = "confetti"
            state = "celebrating"
        return AvatarPayload(
            state=state,
            message=feedback or random.choice(COMPLETE_MESSAGES),
            animationEffect=effect,
        )
    if is_correct is True:
        return AvatarPayload(
            state="celebrating",
            message=feedback or random.choice(CORRECT_MESSAGES),
            animationEffect="star_burst",
        )
    if is_correct is False:
        if recommended_practice:
            return AvatarPayload(
                state="encouraging",
                message=feedback or "Let us practise this one together.",
                animationEffect="gentle_hint",
            )
        return AvatarPayload(
            state="thinking",
            message=feedback or random.choice(HINT_MESSAGES),
            animationEffect="gentle_hint",
        )
    return AvatarPayload(
        state="storytelling",
        message=tutor_response or "Let us begin.",
        animationEffect="story_transition",
    )
