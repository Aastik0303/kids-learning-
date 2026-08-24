"""Retention probes, and the reward they pay days later.

This is the half of the learning-to-teach loop that lives outside the guide. The
rule it exists to keep is the one in `CLAUDE.md`: a teaching strategy is never
paid for the answer the child gave in the same breath. It is paid when the skill
is still there two days later, and again at seven.

The sequence, for one skill:

1. the child is taught - `teaching_policy_service` writes an episode with no
   reward and no probe;
2. the child answers correctly - a day-2 probe is scheduled, and every unpaid
   episode for that skill is attached to it;
3. two days later the child meets that skill again. That attempt *is* the probe:
   it resolves, pays every attached episode, and the Q-table moves;
4. a passed day-2 probe schedules the day-7 one, so a strategy that only held
   for 48 hours is separated from one that held for a week.

Step 3 is why a strategy that reaches today's right answer by handing it over
scores badly: it produces a correct attempt today and a failed probe on Tuesday.
"""

from datetime import datetime, timezone
from uuid import UUID

from app.db.repositories import policy
from app.db.session import session_scope


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _child_uuid(child_id: str) -> UUID | None:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        return None


def on_attempt(
    *,
    child_id: str,
    skill_id: str,
    form_signature: str,
    is_correct: bool,
    now: datetime | None = None,
) -> dict:
    """Settle whatever this attempt answers, then schedule what it earns.

    Returns a small summary - which probe kinds settled, whether one was
    scheduled - so the caller can log it and the tests can assert on it without
    reaching into the database.
    """
    child_uuid = _child_uuid(child_id)
    if child_uuid is None:
        return {"settled": [], "scheduled": None}

    moment = now or _now()
    settled: list[str] = []
    scheduled: str | None = None

    with session_scope() as session:
        probe = policy.open_probe(session, child_id=child_uuid, skill_id=skill_id)

        if probe is not None and probe.due_at <= moment:
            # The probe remembered the form the skill was taught in. Passing it
            # in a *different* form is evidence of transfer rather than of
            # recall, and only that earns the bonus - so the column is cleared
            # when the child was asked the same way twice.
            taught_form = probe.form_signature
            probe.form_signature = form_signature if form_signature and form_signature != taught_form else ""
            policy.settle_probe(session, probe, was_correct=is_correct, now=moment)
            settled.append(probe.kind)

            if is_correct and probe.kind == "day2":
                # It held for two days. Ask again at seven, in the form it was
                # just answered in, so the next probe can test transfer too.
                follow_up = policy.schedule_probe(
                    session,
                    child_id=child_uuid,
                    skill_id=skill_id,
                    kind="day7",
                    form_signature=form_signature or taught_form,
                    now=moment,
                )
                policy.attach_probe(session, child_id=child_uuid, skill_id=skill_id, probe=follow_up)
                scheduled = "day7"

        still_open = policy.open_probe(session, child_id=child_uuid, skill_id=skill_id)
        if is_correct and scheduled is None and still_open is None:
            fresh = policy.schedule_probe(
                session,
                child_id=child_uuid,
                skill_id=skill_id,
                kind="day2",
                form_signature=form_signature or "",
                now=moment,
            )
            policy.attach_probe(session, child_id=child_uuid, skill_id=skill_id, probe=fresh)
            scheduled = "day2"

    return {"settled": settled, "scheduled": scheduled}
