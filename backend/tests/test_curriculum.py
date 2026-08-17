"""Curriculum migration (docs/ops/OP-07) acceptance tests.

The manifest is the only curriculum source. These tests assert the taxonomy
loads, the age bands resolve exactly at their boundaries, malformed content
fails fast with a named error, and adding a topic needs no code change.
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import activity_evaluators, curriculum_service
from app.services.curriculum_service import CurriculumManifestError

EXPECTED_CLASSES = ["playgroup", "nursery", "lkg", "ukg"]
EXPECTED_SUBJECTS = 20
EXPECTED_TOPICS = 122
EXPECTED_SUBTOPICS = 436


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_curriculum():
    """Every test starts from the curriculum as it is on disk."""
    curriculum_service.reload_curriculum()
    yield
    curriculum_service.reload_curriculum()


def parent_token(client: TestClient, email: str) -> str:
    auth = client.post(
        "/auth/register", json={"name": "Parent", "email": email, "password": "demo1234"}
    )
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    return auth.json()["session_token"]


def make_child(client: TestClient, email: str, birth_year: int, birth_month: int = 6):
    token = parent_token(client, email)
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": birth_year,
            "birth_month": birth_month,
            "preferred_language": "English",
        },
    )
    assert child.status_code == 200, child.json()
    return token, child.json()


# --------------------------------------------------------------------------
# taxonomy
# --------------------------------------------------------------------------


def test_all_classes_subjects_and_topics_load(client: TestClient):
    classes = client.get("/curriculum/classes").json()
    assert [c["class_id"] for c in classes] == EXPECTED_CLASSES
    assert sum(c["subject_count"] for c in classes) == EXPECTED_SUBJECTS
    assert sum(c["topic_count"] for c in classes) == EXPECTED_TOPICS
    assert sum(c["subtopic_count"] for c in classes) == EXPECTED_SUBTOPICS


def test_per_class_counts_match_the_published_syllabus(client: TestClient):
    counts = {
        c["class_id"]: (c["subject_count"], c["topic_count"])
        for c in client.get("/curriculum/classes").json()
    }
    assert counts == {
        # Play Group teaches three subjects by product decision: English, Early
        # Mathematics and General Awareness. The other three published subjects
        # are recorded under `removed_subjects`. General Awareness delivers its
        # six published topics as fourteen levels of three things each, so a
        # two-year-old meets one thing at a time and a level fits one sitting.
        "playgroup": (3, 24),
        # Nursery's published units become levels: the two counting units are
        # four number levels, Capital Letters plus Small Letters are thirteen Aa
        # levels, and restored Hindi adds a sixth subject of nine letter levels
        # plus its oral work. No published subtopic is lost — see the subject
        # notes in the manifest.
        "nursery": (6, 52),
        # LKG's published four subjects plus Art & Writing, which is a delivery
        # decision rather than a published subject: it gathers the pre-writing
        # strokes and the letter writing that the syllabus files under English,
        # so every drawing step lives in one place. No published subtopic moves
        # out of the class, which is why the subtopic total is unchanged.
        "lkg": (5, 23),
        # UKG's published five subjects plus Rhymes, which the syllabus lists
        # alongside them rather than inside one. Maths delivers its published
        # Numbers (1-200) unit as three topics and English its one list of
        # sixteen points as five, so a sitting is one idea; Rhymes is four short
        # singing levels rather than one topic of eleven rhymes.
        "ukg": (6, 23),
    }


def test_hindi_is_taught_in_nursery_and_ukg(client: TestClient):
    """Both Hindi subjects were removed by an earlier product decision and
    restored on request: Nursery's orally, UKG's with writing and matras. Play
    Group and LKG never published one."""
    with_hindi = []
    for class_id in EXPECTED_CLASSES:
        detail = client.get(f"/curriculum/classes/{class_id}").json()
        titles = " ".join(subject["title"] for subject in detail["subjects"]).lower()
        if "hindi" in titles:
            with_hindi.append(class_id)
    assert with_hindi == ["nursery", "ukg"]


def test_nursery_hindi_is_no_longer_recorded_as_removed(client: TestClient):
    nursery = client.get("/curriculum/classes/nursery").json()
    assert nursery["removed_subjects"] == []
    assert nursery["removed_subject_ids"] == []
    assert "nur_hindi" in [s["subject_id"] for s in nursery["subjects"]]


def test_ukg_hindi_is_no_longer_recorded_as_removed(client: TestClient):
    ukg = client.get("/curriculum/classes/ukg").json()
    assert ukg["removed_subjects"] == []
    assert ukg["removed_subject_ids"] == []
    assert "ukg_language" in [s["subject_id"] for s in ukg["subjects"]]


def test_lkg_subjects_carry_a_child_facing_name_and_an_exact_colour(client: TestClient):
    """The syllabus title stays authoritative for a grown-up; `fun_name` is what a
    four-year-old is shown. Both travel with the manifest, so the frontend still
    holds no curriculum names of its own."""
    subjects = {s["subject_id"]: s for s in client.get("/curriculum/classes/lkg").json()["subjects"]}
    assert subjects["lkg_maths"]["title"] == "Basic Mathematics"
    assert subjects["lkg_maths"]["fun_name"] == "Number Fun 🔢"
    assert subjects["lkg_maths"]["colour"] == "#FF6B6B"
    # A subject that authors neither still renders, from its accent alone.
    playgroup = client.get("/curriculum/classes/playgroup").json()["subjects"][0]
    assert playgroup["fun_name"] is None and playgroup["colour"] is None


def test_ukg_explains_every_subject_topic_and_point_in_plain_words(client: TestClient):
    """UKG is the class where the syllabus itself supplies a plain line for every
    point it publishes. Those lines are what the adventure and Practice show, so
    a missing one is a card that explains nothing."""
    subjects = client.get("/curriculum/classes/ukg").json()["subjects"]
    for subject in subjects:
        assert subject["easy_line"], subject["subject_id"]
        for topic in subject["topics"]:
            assert topic["easy_line"], topic["topic_id"]
            assert len(topic["subtopic_easy"]) == len(topic["subtopics"]), topic["topic_id"]

    maths = next(s for s in subjects if s["subject_id"] == "ukg_maths")
    assert maths["fun_name"] == "Number Fun 🔢"
    signs = next(t for t in maths["topics"] if t["topic_id"] == "ukg_maths_addsub")
    position = signs["subtopics"].index("Putting Signs like '>', '<' and '='")
    assert signs["subtopic_easy"][position] == "Bada muh hamesha bade number ki taraf"


def test_ukg_covers_every_point_the_syllabus_publishes(client: TestClient):
    """The published totals per subject, which is what regrouping has to preserve:
    a topic may gather several points, but none of them may go missing."""
    subjects = {s["subject_id"]: s for s in client.get("/curriculum/classes/ukg").json()["subjects"]}
    points = {
        subject_id: sum(len(t["subtopics"]) for t in subject["topics"])
        for subject_id, subject in subjects.items()
    }
    assert points == {
        "ukg_english": 16,
        "ukg_maths": 36,
        "ukg_evs": 5,
        "ukg_ga": 19,
        "ukg_language": 6,
        "ukg_rhymes": 11,
    }


def test_subtopic_icons_pair_up_one_for_one(client: TestClient):
    """A card draws a subtopic beside its own emoji, so a partial list would pair
    a subtopic with the icon belonging to the one before it."""
    for subject in client.get("/curriculum/classes/lkg").json()["subjects"]:
        for topic in subject["topics"]:
            assert len(topic["subtopic_icons"]) == len(topic["subtopics"]), topic["topic_id"]


def test_topic_ids_are_unique_across_the_whole_curriculum():
    seen = set()
    for detail in curriculum_service._curriculum().classes:
        for subject in detail.subjects:
            for topic in subject.topics:
                assert topic.topic_id not in seen
                seen.add(topic.topic_id)
    assert len(seen) == EXPECTED_TOPICS


# --------------------------------------------------------------------------
# experience modes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "class_id,mode,target,choices,text",
    [
        ("playgroup", "early", 96, 3, "none"),
        ("nursery", "early", 96, 3, "none"),
        ("lkg", "standard", 64, 4, "short_words"),
        ("ukg", "standard", 64, 4, "short_words"),
    ],
)
def test_experience_mode_per_class(client, class_id, mode, target, choices, text):
    experience = client.get(f"/curriculum/classes/{class_id}/experience").json()
    assert experience["mode_id"] == mode
    assert experience["touch_target_px"] == target
    assert experience["max_choices_per_screen"] == choices
    assert experience["text_density"] == text


def test_idle_rungs_match_the_two_modes(client: TestClient):
    modes = client.get("/curriculum").json()["experience_modes"]
    assert modes["early"]["idle_thresholds_seconds"] == [12, 25, 40, 60, 80]
    assert modes["standard"]["idle_thresholds_seconds"] == [8, 18, 30, 45, 60]


# --------------------------------------------------------------------------
# age -> class
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "age,expected",
    [
        (0.0, "playgroup"),
        (2.0, "playgroup"),
        (2.99, "playgroup"),
        (3.0, "nursery"),      # boundary
        (3.99, "nursery"),
        (4.0, "lkg"),          # boundary
        (4.99, "lkg"),
        (5.0, "ukg"),          # boundary
        (5.99, "ukg"),
        (9.0, "ukg"),          # above the oldest band
    ],
)
def test_age_resolves_to_the_right_class(age, expected):
    assert curriculum_service.resolve_class(age) == expected


def test_age_is_derived_from_birth_month_on_the_server():
    today = date(2026, 8, 15)
    assert curriculum_service.age_years(2022, 8, today) == 4.0
    assert curriculum_service.age_years(2022, 9, today) == pytest.approx(3.9167, abs=1e-3)


def test_a_future_birth_date_is_rejected():
    with pytest.raises(Exception) as exc:
        curriculum_service.age_years(2030, 1, date(2026, 8, 15))
    assert exc.value.detail["code"] == "INVALID_BIRTH_DATE"


def test_child_class_comes_from_birth_date_not_the_client(client: TestClient):
    _, child = make_child(client, "band@example.com", birth_year=date.today().year - 4)
    assert child["class_id"] == "lkg"
    assert child["default_class_id"] == "lkg"
    assert child["experience_mode"] == "standard"
    assert child["class_override"] is None


# --------------------------------------------------------------------------
# parent override
# --------------------------------------------------------------------------


def test_parent_can_override_to_an_adjacent_class(client: TestClient):
    token, child = make_child(client, "adj@example.com", birth_year=date.today().year - 4)
    response = client.put(
        f"/curriculum/children/{child['child_id']}/class",
        json={"session_token": token, "class_id": "nursery"},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["class_id"] == "nursery"
    assert updated["class_override"] == "nursery"
    assert updated["default_class_id"] == "lkg"
    # Nursery is an `early` class, so the presentation mode follows.
    assert updated["experience_mode"] == "early"


def test_parent_cannot_skip_a_class(client: TestClient):
    token, child = make_child(client, "skip@example.com", birth_year=date.today().year - 4)
    response = client.put(
        f"/curriculum/children/{child['child_id']}/class",
        json={"session_token": token, "class_id": "playgroup"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CLASS_NOT_ADJACENT"


def test_override_options_are_anchored_on_the_age_derived_class(client: TestClient):
    token, child = make_child(client, "anchor@example.com", birth_year=date.today().year - 4)
    client.put(
        f"/curriculum/children/{child['child_id']}/class",
        json={"session_token": token, "class_id": "nursery"},
    )
    options = client.get(f"/curriculum/children/{child['child_id']}/class-options").json()
    # Still anchored on lkg, so an override cannot be walked down repeatedly.
    assert sorted(o["class_id"] for o in options) == ["lkg", "nursery", "ukg"]


def test_a_child_cannot_change_their_own_class(client: TestClient):
    _, child = make_child(client, "nochange@example.com", birth_year=date.today().year - 4)
    # The child app holds no session token. Without a parent's token the call fails.
    response = client.put(
        f"/curriculum/children/{child['child_id']}/class",
        json={"session_token": "not-a-real-token", "class_id": "nursery"},
    )
    assert response.status_code in (401, 404)
    assert client.get(f"/children/{child['child_id']}").json()["class_id"] == "lkg"


def test_clearing_the_override_returns_the_child_to_their_age_class(client: TestClient):
    token, child = make_child(client, "clear@example.com", birth_year=date.today().year - 4)
    client.put(
        f"/curriculum/children/{child['child_id']}/class",
        json={"session_token": token, "class_id": "nursery"},
    )
    response = client.request(
        "DELETE",
        f"/curriculum/children/{child['child_id']}/class",
        params={"session_token": token},
    )
    assert response.status_code == 200
    assert response.json()["class_id"] == "lkg"
    assert response.json()["class_override"] is None


# --------------------------------------------------------------------------
# fail fast
# --------------------------------------------------------------------------


def write_manifest(tmp_path, monkeypatch, manifest: dict):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(curriculum_service, "MANIFEST_PATH", path)
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", tmp_path / "activities")
    curriculum_service._curriculum.cache_clear()


def minimal_manifest() -> dict:
    return {
        "version": "test",
        "source": "test",
        "experience_modes": {
            "early": {
                "applies_to": ["alpha"],
                "touch_target_px": 96,
                "max_choices_per_screen": 3,
                "text_density": "none",
                "voice": "always",
                "idle_thresholds_seconds": [12, 25],
            }
        },
        "classes": [
            {
                "class_id": "alpha",
                "code": "A",
                "title": "Alpha",
                "min_age": 2,
                "max_age": 3,
                "experience_mode": "early",
                "sort_order": 1,
                "subjects": [
                    {
                        "subject_id": "alpha_maths",
                        "title": "Maths",
                        "sort_order": 1,
                        "topics": [
                            {
                                "topic_id": "alpha_maths_colours",
                                "title": "Colours",
                                "sort_order": 1,
                                "subtopics": ["Red"],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_a_valid_minimal_manifest_loads(tmp_path, monkeypatch):
    write_manifest(tmp_path, monkeypatch, minimal_manifest())
    assert curriculum_service.class_ids() == ["alpha"]


def test_missing_required_field_fails_fast_and_names_it(tmp_path, monkeypatch):
    manifest = minimal_manifest()
    del manifest["classes"][0]["title"]
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "title" in str(exc.value) and "alpha" in str(exc.value)


def test_unknown_experience_mode_fails_fast(tmp_path, monkeypatch):
    manifest = minimal_manifest()
    manifest["classes"][0]["experience_mode"] = "turbo"
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "turbo" in str(exc.value)


def test_duplicate_topic_id_fails_fast(tmp_path, monkeypatch):
    manifest = minimal_manifest()
    topics = manifest["classes"][0]["subjects"][0]["topics"]
    topics.append({**topics[0], "sort_order": 2})
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "duplicate topic_id" in str(exc.value)


def test_non_contiguous_age_bands_fail_fast(tmp_path, monkeypatch):
    manifest = minimal_manifest()
    manifest["experience_modes"]["early"]["applies_to"].append("beta")
    second = json.loads(json.dumps(manifest["classes"][0]))
    second.update({"class_id": "beta", "code": "B", "title": "Beta", "min_age": 5, "max_age": 6, "sort_order": 2})
    second["subjects"][0]["subject_id"] = "beta_maths"
    second["subjects"][0]["topics"][0]["topic_id"] = "beta_maths_colours"
    manifest["classes"].append(second)
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "not contiguous" in str(exc.value)


def test_a_topic_with_no_subtopics_fails_fast(tmp_path, monkeypatch):
    manifest = minimal_manifest()
    manifest["classes"][0]["subjects"][0]["topics"][0]["subtopics"] = []
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError):
        curriculum_service.load_curriculum()


def test_subtopic_icons_that_do_not_line_up_fail_fast(tmp_path, monkeypatch):
    manifest = minimal_manifest()
    topic = manifest["classes"][0]["subjects"][0]["topics"][0]
    topic["subtopics"] = ["Red", "Blue"]
    topic["subtopic_icons"] = ["🔴"]
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "subtopic_icons" in str(exc.value)


def test_a_subject_colour_that_is_not_hex_fails_fast(tmp_path, monkeypatch):
    """A typo here would reach the browser as an unstyled card."""
    manifest = minimal_manifest()
    manifest["classes"][0]["subjects"][0]["colour"] = "reddish"
    write_manifest(tmp_path, monkeypatch, manifest)
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "hex" in str(exc.value)


def test_malformed_json_fails_fast(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(curriculum_service, "MANIFEST_PATH", path)
    curriculum_service._curriculum.cache_clear()
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "not valid JSON" in str(exc.value)


# --------------------------------------------------------------------------
# activity files
# --------------------------------------------------------------------------


def write_activities(tmp_path, monkeypatch, manifest: dict, payload: dict, name: str):
    activities_dir = tmp_path / "activities"
    activities_dir.mkdir(exist_ok=True)
    (activities_dir / name).write_text(json.dumps(payload), encoding="utf-8")
    write_manifest(tmp_path, monkeypatch, manifest)


def good_activity(**overrides) -> dict:
    activity = {
        "activity_id": "a1",
        "type": "identify_colour",
        "prompt": "Tap red.",
        "options": ["red", "blue"],
        "correct_answer": "red",
        "hint": "Red like a strawberry.",
    }
    activity.update(overrides)
    return activity


def test_authored_activities_make_a_topic_available(tmp_path, monkeypatch):
    write_activities(
        tmp_path,
        monkeypatch,
        minimal_manifest(),
        {"subject_id": "alpha_maths", "topics": {"alpha_maths_colours": [good_activity()]}},
        "alpha_maths.json",
    )
    topic = curriculum_service.get_topic("alpha_maths_colours")
    assert topic.available is True
    assert topic.activity_count == 1


def test_unregistered_activity_type_is_rejected_by_name(tmp_path, monkeypatch):
    write_activities(
        tmp_path,
        monkeypatch,
        minimal_manifest(),
        {
            "subject_id": "alpha_maths",
            "topics": {"alpha_maths_colours": [good_activity(type="interpretive_dance")]},
        },
        "alpha_maths.json",
    )
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "interpretive_dance" in str(exc.value)
    assert "no registered evaluator" in str(exc.value)


def test_activity_for_an_unknown_topic_is_rejected(tmp_path, monkeypatch):
    write_activities(
        tmp_path,
        monkeypatch,
        minimal_manifest(),
        {"subject_id": "alpha_maths", "topics": {"nope": [good_activity()]}},
        "alpha_maths.json",
    )
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "nope" in str(exc.value)


def test_correct_answer_outside_the_options_is_rejected(tmp_path, monkeypatch):
    write_activities(
        tmp_path,
        monkeypatch,
        minimal_manifest(),
        {
            "subject_id": "alpha_maths",
            "topics": {"alpha_maths_colours": [good_activity(correct_answer="green")]},
        },
        "alpha_maths.json",
    )
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "is not among the options" in str(exc.value)


def test_too_many_choices_for_the_class_mode_is_rejected(tmp_path, monkeypatch):
    """`early` allows three choices per screen. Four is an authoring error."""
    write_activities(
        tmp_path,
        monkeypatch,
        minimal_manifest(),
        {
            "subject_id": "alpha_maths",
            "topics": {
                "alpha_maths_colours": [
                    good_activity(options=["red", "blue", "green", "yellow"])
                ]
            },
        },
        "alpha_maths.json",
    )
    with pytest.raises(CurriculumManifestError) as exc:
        curriculum_service.load_curriculum()
    assert "at most 3" in str(exc.value)


def test_every_registered_type_has_a_callable_evaluator():
    for activity_type in activity_evaluators.registered_types():
        assert callable(activity_evaluators.EVALUATORS[activity_type])


# --------------------------------------------------------------------------
# data-driven extension
# --------------------------------------------------------------------------


def test_adding_a_topic_needs_only_a_manifest_edit(tmp_path, monkeypatch):
    """OP-07: adding a subject or topic requires zero code changes."""
    manifest = minimal_manifest()
    before = len(manifest["classes"][0]["subjects"][0]["topics"])

    manifest["classes"][0]["subjects"][0]["topics"].append(
        {
            "topic_id": "alpha_maths_shapes",
            "title": "Shapes",
            "sort_order": 2,
            "subtopics": ["Circle", "Square"],
        }
    )
    manifest["classes"][0]["subjects"].append(
        {
            "subject_id": "alpha_music",
            "title": "Music",
            "sort_order": 2,
            "topics": [
                {"topic_id": "alpha_music_songs", "title": "Songs", "sort_order": 1, "subtopics": ["Clap"]}
            ],
        }
    )
    write_manifest(tmp_path, monkeypatch, manifest)

    detail = curriculum_service.get_class("alpha")
    assert detail.subject_count == 2
    assert len(detail.subjects[0].topics) == before + 1
    # The new topic is a first-class citizen: reachable by id, with its subtopics.
    assert curriculum_service.get_topic("alpha_maths_shapes").subtopics == ["Circle", "Square"]
    assert curriculum_service.get_subject("alpha_music").title == "Music"


def test_topics_and_subjects_are_served_in_manifest_sort_order(client: TestClient):
    detail = client.get("/curriculum/classes/playgroup").json()
    assert [s["sort_order"] for s in detail["subjects"]] == sorted(
        s["sort_order"] for s in detail["subjects"]
    )
    for subject in detail["subjects"]:
        orders = [t["sort_order"] for t in subject["topics"]]
        assert orders == sorted(orders)


def test_unknown_ids_are_honest_404s(client: TestClient):
    assert client.get("/curriculum/classes/kg9").status_code == 404
    assert client.get("/curriculum/subjects/nope").status_code == 404
    assert client.get("/curriculum/topics/nope").status_code == 404
