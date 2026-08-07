from typing import TypedDict


class GuideState(TypedDict, total=False):
    session_id: str
    child_id: str
    mode: str
    event: str
    route: str
    screen: str
    feature: str
    age_group: str
    preferred_language: str
    available_actions: list[str]
    available_targets: list[str]
    activity_id: str
    topic: str
    concept: str
    prompt: str
    options: list[str]
    correct_answer: str
    child_answer: str
    attempt_number: int
    current_world: str
    current_level: str
    weak_skills: list[str]
    message: str
    strategy: str
    ui_action: dict
    avatar: dict
    safety_status: str
    error: str
