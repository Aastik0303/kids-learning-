"""Retrieval for the AI Teacher playground.

Two sources go into one index, embedded with a free HuggingFace
sentence-transformer and searched by cosine similarity:

* **`data/playground/teacher_notes.md`** - how to teach these things: what a
  letter's sound is, how to count with a child, what to say when it does not
  land.
* **the syllabus itself** - `data/curriculum/activities/*.json`, one passage per
  topic: its objective, what it covers, and the lines the author actually wrote
  to teach it. Without this the bot knew how to teach but not *what this class
  teaches*, and would happily explain a letter the syllabus does not reach for
  another year.

**The answer keys are left out on purpose.** A topic's passage carries prompts
and hints and nothing else: `correct_answer`, `accept` and `options` never enter
the index, because everything in it is handed to a model that is about to talk
to the child, and a model holding the answer key is a model that can give it
away while explaining.

Three more things are deliberate:

**The index is built lazily and cached.** Loading the embedding model costs a
few seconds the first time (and a ~90MB download the very first time), and that
must not happen inside a child's turn if it can be helped; the first call to
`search` pays it and every call after is a matrix multiply.

**There is a keyword fallback, and it is not an afterthought.** A machine with
no network, or one where torch will not import, still has to be able to run the
playground. `search` falls back to scoring chunks by word overlap, which is
worse but never absent. `backend()` says which one answered.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.config import get_settings


logger = logging.getLogger(__name__)

NOTES_PATH = Path(__file__).resolve().parents[1] / "data" / "playground" / "teacher_notes.md"

# How many passages go into one prompt. Three is enough to teach one thing from
# and short enough that the model cannot wander off into the whole file.
DEFAULT_TOP_K = 3


@dataclass(frozen=True)
class Passage:
    """One retrievable piece, named by the heading it sits under.

    `source` says where it came from - "notes" for the teaching notes, "syllabus"
    for a topic out of the authored curriculum - so a turn can be read back and
    the two told apart.
    """

    heading: str
    text: str
    source: str = "notes"
    # "overview", "teach", "draw", "match", "count", "quiz" - what this passage
    # is about doing, so a step of the lesson can ask for the part it needs.
    kind: str = ""
    class_id: str = ""
    subject_id: str = ""
    topic_id: str = ""
    skill_id: str = ""

    @property
    def content(self) -> str:
        return f"{self.heading}\n{self.text}"


@dataclass(frozen=True)
class Hit:
    passage: Passage
    score: float


_lock = Lock()
_passages: list[Passage] | None = None
_vectors = None  # numpy array, or None when the embedding model is unavailable
_model = None
_backend = "keyword"


def _split(markdown: str) -> list[Passage]:
    """Chunk on `##` headings: the notes are already written one idea per section."""
    passages: list[Passage] = []
    heading = "AI Teacher notes"
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            passages.append(Passage(heading=heading, text=text))

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            heading = line[3:].strip()
            body = []
            continue
        if line.startswith("# ") or line.strip() == "---":
            continue
        body.append(line)
    flush()
    return passages


# The authored syllabus. One passage per topic; the answer keys are stripped.
ACTIVITIES_DIR = Path(__file__).resolve().parents[1] / "data" / "curriculum" / "activities"

# A ceiling on one passage, for a runaway author. A passage is one skill now,
# not one topic, so this is rarely reached.
MAX_PASSAGE_CHARS = 600


def _syllabus_passages() -> list[Passage]:
    """The shipped syllabus, one passage per skill rather than one per topic.

    A topic used to be a single 700-character blob, which is the wrong shape for
    retrieval twice over: the one interesting sentence about the letter A was
    buried among ten others, and a search could not tell "how A is taught" from
    "how A is written". Each topic now yields:

    * an **overview** passage - what the topic is for, and what it covers;
    * one **teaching** passage per skill the author wrote for it, carrying that
      skill's own lines and the kind of task they belong to.

    `kind` and `skill_id` travel with the passage so a step of the lesson can ask
    for the part it needs - the writing lines while the child is drawing, the
    matching lines while they are choosing.
    """
    passages: list[Passage] = []
    if not ACTIVITIES_DIR.exists():  # pragma: no cover - a stripped checkout
        return passages

    for path in sorted(ACTIVITIES_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):  # pragma: no cover - authored content
            logger.warning("Could not read %s for the playground index", path.name)
            continue

        class_id = str(raw.get("class_id") or path.stem)
        class_title = raw.get("title") or class_id
        for subject in raw.get("subjects") or []:
            subject_id = str(subject.get("subject_id") or "")
            subject_title = subject.get("title") or subject_id
            for topic in raw_topics(subject):
                passages.extend(
                    _topic_passages(topic, class_id, class_title, subject_id, subject_title)
                )
    return passages


def raw_topics(subject: dict) -> list[dict]:
    return [topic for topic in (subject.get("topics") or []) if isinstance(topic, dict)]


# Whether a line already finishes itself. The check looks *behind* any trailing
# emoji: "Let us draw lines! ✏️" is a finished sentence, and a full stop stuck on
# after the crayon is not what the author wrote.
_TRAILING_DECOR = re.compile(r"[^\w.?!।]+$")


def _ends_a_sentence(text: str) -> bool:
    core = _TRAILING_DECOR.sub("", text.strip())
    return bool(core) and core[-1] in ".?!।"


def _topic_passages(
    topic: dict, class_id: str, class_title: str, subject_id: str, subject_title: str
) -> list[Passage]:
    topic_id = str(topic.get("topic_id") or "")
    title = topic.get("title") or topic_id
    where = f"{class_title} · {subject_title} · {title}"

    def make(text: str, *, kind: str, skill_id: str = "", heading: str = "") -> Passage | None:
        body = text.strip()
        if not body:
            return None
        return Passage(
            heading=heading or where,
            text=body[:MAX_PASSAGE_CHARS],
            source="syllabus",
            kind=kind,
            class_id=class_id,
            subject_id=subject_id,
            topic_id=topic_id,
            skill_id=skill_id,
        )

    passages: list[Passage] = []

    # The objective is a syllabus line and rarely ends in a full stop; the intro
    # is a sentence spoken to the child. Joined with a bare space they read as
    # one run-on - "joining dots Let us draw lines!" - so the objective is
    # finished off before the two are put together.
    overview = " ".join(
        part if _ends_a_sentence(part) else f"{part}."
        for part in (
            (topic.get("objective") or "").strip(),
            (topic.get("intro_message") or "").strip(),
        )
        if part
    )
    first = make(overview or f"This topic is {title}.", kind="overview")
    if first:
        passages.append(first)

    # Grouped by the skill they teach: a letter's three cards - meet it, hear
    # it, write it - belong together and are retrieved together.
    by_skill: dict[str, dict] = {}
    order: list[str] = []
    for activity in topic.get("activities") or []:
        skill_id = str(activity.get("skill_id") or activity.get("activity_id") or "")
        if skill_id not in by_skill:
            by_skill[skill_id] = {"lines": [], "kinds": set()}
            order.append(skill_id)
        bucket = by_skill[skill_id]
        for key in ("prompt", "hint"):
            # Prompts and hints only: `correct_answer`, `accept` and `options`
            # are the answer key and never enter the index.
            value = (activity.get(key) or "").strip()
            if value and value not in bucket["lines"]:
                bucket["lines"].append(value)
        kind = _task_kind(activity)
        if kind:
            bucket["kinds"].add(kind)

    for skill_id in order:
        bucket = by_skill[skill_id]
        kinds = sorted(bucket["kinds"])
        made = make(
            f"[{', '.join(kinds) or 'teach'}] {' '.join(bucket['lines'])}",
            kind=kinds[0] if kinds else "teach",
            skill_id=skill_id,
            heading=f"{where} · {skill_id or 'teaching'}",
        )
        if made:
            passages.append(made)

    return passages


def _task_kind(activity: dict) -> str:
    """What kind of doing an authored activity is. The lesson steps use these."""
    activity_type = (activity.get("type") or "").lower()
    if activity.get("trace_target") or "trace" in activity_type or "write" in activity_type:
        return "draw"
    if activity_type.startswith("introduce") or not activity.get("correct_answer"):
        return "teach"
    if "count" in activity_type:
        return "count"
    if "match" in activity_type or activity.get("options"):
        return "match"
    return "quiz"


def _load_passages() -> list[Passage]:
    return _split(NOTES_PATH.read_text(encoding="utf-8")) + _syllabus_passages()


def _load_model():
    """The free HuggingFace embedder, or None if it cannot be had."""
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:  # pragma: no cover - depends on the machine, not the code
        logger.warning("sentence-transformers is unavailable; retrieval falls back to keywords")
        return None
    try:
        return SentenceTransformer(get_settings().playground_embedding_model)
    except Exception:  # pragma: no cover - offline, or no cached model
        logger.warning("The embedding model could not be loaded; retrieval falls back to keywords")
        return None


def _build() -> None:
    global _passages, _vectors, _model, _backend
    if _passages is not None:
        return
    passages = _load_passages()
    model = _load_model()
    vectors = None
    backend = "keyword"
    if model is not None:
        try:
            import numpy as np

            raw = model.encode([passage.content for passage in passages])
            matrix = np.asarray(raw, dtype="float32")
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            vectors = matrix / np.clip(norms, 1e-9, None)
            backend = "embeddings"
        except Exception:  # pragma: no cover - a broken install, not a code path
            logger.exception("Embedding the notes failed; retrieval falls back to keywords")
            vectors = None

    _passages, _vectors, _model, _backend = passages, vectors, model, backend


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9ऀ-ॿ]+", text.lower()) if len(word) > 1}


def _keyword_hits(query: str, passages: list[Passage], top_k: int) -> list[Hit]:
    """Word overlap, weighted so a rare word counts for more than a common one."""
    wanted = _tokens(query)
    if not wanted:
        return [Hit(passage=passage, score=0.0) for passage in passages[:top_k]]

    document_count = len(passages) or 1
    frequency: dict[str, int] = {}
    for passage in passages:
        for token in _tokens(passage.content):
            frequency[token] = frequency.get(token, 0) + 1

    scored: list[Hit] = []
    for passage in passages:
        present = _tokens(passage.content)
        score = sum(
            math.log(1 + document_count / frequency.get(token, 1)) for token in wanted & present
        )
        scored.append(Hit(passage=passage, score=score))
    scored.sort(key=lambda hit: hit.score, reverse=True)
    return scored[:top_k]


def search(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    topic_id: str = "",
    kinds: tuple[str, ...] = (),
) -> list[Hit]:
    """The passages closest to what is being taught, best first.

    A turn never waits for the index. If the warm-up thread is still loading the
    embedding model - the first half-minute after a restart - this answers from
    keywords over the same notes rather than queueing behind it. Slightly worse
    passages beat a child watching a spinner for thirty seconds.
    """
    if not _lock.acquire(blocking=False):
        return _keyword_hits(query, _passages or _load_passages(), top_k)
    try:
        _build()
        passages = _passages or []
        vectors = _vectors
        model = _model
    finally:
        _lock.release()

    if not passages:
        return []

    # Scoping, when the caller knows what it wants: a step of a lesson asks for
    # this topic's writing lines, not for the best passage in the whole syllabus.
    # Always widened back out if the filter leaves nothing, because a step with
    # no passage at all teaches nothing.
    keep = _scoped(passages, vectors, topic_id=topic_id, kinds=kinds)
    if keep is not None:
        passages, vectors = keep

    if vectors is None or model is None:
        return _keyword_hits(query, passages, top_k)

    try:
        import numpy as np

        raw = model.encode([query])
        vector = np.asarray(raw, dtype="float32")[0]
        vector = vector / max(float(np.linalg.norm(vector)), 1e-9)
        scores = vectors @ vector
        order = np.argsort(-scores)[:top_k]
        return [Hit(passage=passages[index], score=float(scores[index])) for index in order]
    except Exception:  # pragma: no cover - a runtime problem, not a code path
        logger.exception("Embedded search failed; falling back to keywords for this turn")
        return _keyword_hits(query, passages, top_k)


def _scoped(passages, vectors, *, topic_id: str, kinds: tuple[str, ...]):
    """The subset a step asked for, or None when it asked for everything."""
    if not topic_id and not kinds:
        return None

    indexes = [
        index
        for index, passage in enumerate(passages)
        if (not topic_id or passage.topic_id == topic_id or passage.source == "notes")
        and (not kinds or passage.kind in kinds or passage.source == "notes")
    ]
    if not indexes:
        return None

    kept = [passages[index] for index in indexes]
    if vectors is None:
        return kept, None
    return kept, vectors[indexes]


def context_for(query: str, *, top_k: int = DEFAULT_TOP_K) -> str:
    """The retrieved passages as one block, ready to go into a prompt."""
    return "\n\n".join(hit.passage.content for hit in search(query, top_k=top_k))


def topic_kinds(topic_id: str) -> set[str]:
    """Which kinds of task the syllabus authored for this topic.

    The lesson uses it to leave out a step that makes no sense: a colours topic
    has nothing to trace, and asking a child to draw "red" would be the app
    talking to itself.
    """
    if not topic_id:
        return set()
    passages = _passages if _passages is not None else _load_passages()
    return {
        passage.kind
        for passage in passages
        if passage.topic_id == topic_id and passage.kind and passage.kind != "overview"
    }


def backend() -> str:
    """"embeddings" or "keyword" - which one is answering right now.

    Never waits for the index either: this is a label on a directive, and a turn
    that blocked for half a minute to find out what to call itself would be the
    warm-up cost sneaking back in through the back door.
    """
    if not _lock.acquire(blocking=False):
        return _backend
    try:
        _build()
        return _backend
    finally:
        _lock.release()


def warm() -> None:
    """Build the index now, off the request path.

    Loading the embedding model takes seconds - the very first time, a download -
    and paying that inside a child's first turn made the AI Teacher tab sit on
    "Waking the teacher up..." for a quarter of a minute. The server does it at
    boot instead, in a thread, so a failure here costs nothing: `search` builds
    it on demand anyway and falls back to keywords.
    """
    try:
        with _lock:
            _build()
        logger.info("Playground retrieval ready (%s)", _backend)
    except Exception:  # pragma: no cover - warming must never take the app down
        logger.exception("Warming the playground index failed; it will build on first use")


def reset() -> None:
    """Drop the index. Tests use it; nothing in a request does."""
    global _passages, _vectors, _model, _backend
    with _lock:
        _passages, _vectors, _model, _backend = None, None, None, "keyword"


__all__ = ["DEFAULT_TOP_K", "Hit", "Passage", "backend", "context_for", "reset", "search", "topic_kinds", "warm"]
