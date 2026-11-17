"""The operator's view of the learned policy, and the switch that stops it.

Four read endpoints and one write. The write is the kill switch, and it exists
because the alternative - editing `POLICY_MODE` and restarting every worker - is
minutes of a child's lesson being taught by a policy somebody has already
decided is misbehaving. `POST /policy/disable` takes effect on the worker that
serves it, immediately, and expires on its own so a forgotten switch does not
freeze the rollout for a week.

Nothing here can change a mark, a star, an unlock or a certificate. The only
thing any of it moves is which teaching strategy gets chosen next.
"""

from hmac import compare_digest

from fastapi import APIRouter, Depends, Header

from app.config import Settings, get_settings
from app.db.session import get_session
from app.policy import evaluate, health, metrics, retention, reward, rollout
from app.services import retention_test_service
from app.services.errors import app_error


router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/health")
def policy_health() -> dict:
    """Mode, rollout fraction, breaker state and the derived rates.

    Cheap and safe to poll: it reads process-local counters and the settings, and
    opens no database session, so it still answers while the database is the
    thing that is broken - which is exactly when somebody is looking at it.
    """
    return health.status()


@router.get("/metrics")
def policy_metrics() -> dict:
    """The raw counters, for a scraper to aggregate.

    Per worker and reset on restart. The durable record is `policy_episodes`.
    """
    return {**metrics.snapshot(), "rates": metrics.rates()}


@router.get("/evaluation")
def policy_evaluation(session=Depends(get_session)) -> dict:
    """The three-way offline comparison: ladder, random, learned.

    Read `evaluate.py` before quoting the numbers. The verdict says "no
    difference demonstrated" until the evidence clears two standard errors, and
    that is the expected answer for a long time.
    """
    return evaluate.run(session).as_dict()


@router.get("/retention")
def policy_retention() -> dict:
    """The retention side of the loop: what pays the table, and how much is owed.

    Read-only and operator-facing. `pending` is the number of scheduled tests
    that have been created and not yet asked - a number that only grows means
    tests are being scheduled and the class is never serving them, which is the
    loop having quietly stopped learning without anything erroring.

    The weights are echoed back because they are settings, so the answer to
    "what is a passed retention test worth on this deployment?" is here rather
    than in somebody's memory of the defaults.
    """
    return {
        "delay_days": int(retention.delay().days),
        "tests_per_sitting": retention.per_sitting(),
        "pending": retention_test_service.pending_count(),
        "weights": reward.weights(),
    }


def _admin(settings: Settings, token: str) -> None:
    """Refuse a write that did not come with the operator's secret.

    The kill switch has to work without a deploy - that is the whole reason it
    is an endpoint - and that made it a state-changing route with no caller
    check on it at all: anything that could reach the API could take the learned
    policy out of the loop, or put it back, on that worker.

    In development the secret is empty and the switch stays one curl away, which
    is what it is for locally. Anywhere else `POLICY_ADMIN_TOKEN` must be set and
    must match, and an unset token means the endpoint is closed rather than open.
    """
    if settings.env.lower() == "development":
        return
    expected = (settings.policy_admin_token or "").strip()
    if not expected:
        raise app_error("POLICY_ADMIN_UNSET", "The policy switch is not configured.", 403)
    if not compare_digest(token.strip(), expected):
        raise app_error("POLICY_ADMIN_FORBIDDEN", "That is not the policy switch token.", 403)


@router.post("/disable")
def disable_policy(
    reason: str = "manual",
    x_policy_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Take the learned policy out of the loop on this worker.

    Every child goes back to the hand-written repair ladder. No lesson stops, no
    progress is lost, and the episodes already written stay where they are.
    """
    _admin(settings, x_policy_token)
    rollout.disable(f"manual:{reason}")
    return health.status()


@router.post("/enable")
def enable_policy(
    x_policy_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Clear a manual disable and reset the failure breaker.

    Development only. In production the switch expires by itself, and clearing
    it early is a deploy-time decision rather than a request.
    """
    if settings.env.lower() != "development":
        raise app_error("DEV_ONLY", "Re-enabling the policy is a deployment action.", 403)
    _admin(settings, x_policy_token)
    health.reset()
    return health.status()
