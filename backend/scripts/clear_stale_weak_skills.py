"""One-off repair: take finished levels off the weak list, and re-freeze today.

Why this exists. `learning_service.mark_weak` appended a skill to
`child["weak_skills"]` and nothing anywhere ever removed one, so the first level
a child struggled with became that subject's permanent answer to "what is
today?" - `plan_service._candidates` prefers a weak level over new ground.
Letter A was failed once, taught again and passed - the star paid, letter B
unlocked on the map - and the schedule went on serving A every morning, in
every subject at once, with everything behind it unreachable.

`learning_service.clear_weak` fixes it from here on: a level that passes comes
off the list. It cannot fix a record that is already stuck, because the flag is
only cleared by the *next* pass. This script does that once, for every child:
a topic that is in the subject's `completed_topics` has passed, so its weak flag
is spent.

It then deletes today's frozen plans, because a plan is frozen per child per day
and would otherwise go on holding the old choice until tomorrow morning.

    cd backend && python -m scripts.clear_stale_weak_skills          # report only
    cd backend && python -m scripts.clear_stale_weak_skills --apply  # write it

Safe to run twice: the second run finds nothing to clear.
"""

import argparse
from datetime import date

from sqlalchemy import select

from app.db.models import Child, DailyPlan
from app.db.session import session_scope
from app.services import child_store


def _stale(record: dict) -> list[str]:
    """The weak skills whose level this child has already finished."""
    completed = {
        f"{subject_id}:{topic_id}"
        for subject_id, progress in (record.get("subject_progress") or {}).items()
        for topic_id in (progress.get("completed_topics") or [])
    }
    return [skill for skill in (record.get("weak_skills") or []) if skill in completed]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the changes")
    args = parser.parse_args()

    with session_scope() as session:
        child_ids = [str(child_id) for child_id in session.scalars(select(Child.id)).all()]

    cleared = 0
    for child_id in child_ids:
        record = child_store.find(child_id)
        if record is None:
            continue
        stale = _stale(record)
        if not stale:
            continue
        print(f"{record.get('name', child_id)} ({child_id}): {', '.join(stale)}")
        cleared += len(stale)
        if args.apply:
            record["weak_skills"] = [
                skill for skill in record["weak_skills"] if skill not in stale
            ]
            child_store.save(record)

    if not args.apply:
        print(f"\n{cleared} stale weak skill(s) found. Re-run with --apply to clear them.")
        return

    # Today's plan was frozen before the fix, so it still holds the old choice.
    # Deleting it lets the next read of the day rebuild it from the repaired
    # record; nothing is lost, because a plan is a choice and not a result.
    with session_scope() as session:
        plans = list(session.scalars(select(DailyPlan).where(DailyPlan.plan_date == date.today())))
        for plan in plans:
            session.delete(plan)
    child_store.reset_cache()
    print(f"\nCleared {cleared} stale weak skill(s); dropped {len(plans)} of today's plans.")


if __name__ == "__main__":
    main()
