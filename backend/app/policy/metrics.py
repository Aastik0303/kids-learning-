"""What the policy did, in a shape something can add up later.

Two outputs from one call, on purpose:

- a **structured log line** on the `saksham.policy` logger, one JSON-shaped
  record per event, so a log shipper can aggregate without anybody writing a
  dashboard first;
- an **in-process counter table**, readable through `snapshot()`, so
  `/policy/health` can answer "what has this worker been doing" without a log
  search, and so the tests can assert on it.

The counters are per worker and reset on restart. That is deliberate: they are a
liveness view, not the record. The record is `policy_episodes`, which is on disk
and is what the offline evaluation reads.
"""

import json
import logging
import threading
from collections import Counter, defaultdict


logger = logging.getLogger("saksham.policy")

# Event names. Stable strings - they end up as dashboard series.
DECISION = "policy.decision"
EXPLORE = "policy.explore"
EXPLOIT = "policy.exploit"
FALLBACK = "policy.fallback"
ELIGIBILITY_REMOVED = "policy.eligibility_removed"
REWARD = "policy.reward"
PROBE = "policy.probe"
LEAK_VERDICT = "policy.leak_verdict"
Q_UPDATE = "policy.q_update"
DB_ERROR = "policy.db_error"
SELECTION_ERROR = "policy.selection_error"
SHADOW = "policy.shadow"

_lock = threading.Lock()
_counters: Counter[str] = Counter()
_sums: dict[str, float] = defaultdict(float)
_observations: Counter[str] = Counter()


def _key(event: str, **labels: object) -> str:
    if not labels:
        return event
    parts = ",".join(f"{name}={value}" for name, value in sorted(labels.items()) if value is not None)
    return f"{event}|{parts}"


def count(event: str, **labels: object) -> None:
    """One thing happened."""
    with _lock:
        _counters[_key(event, **labels)] += 1
    logger.info("%s", json.dumps({"event": event, **{k: _plain(v) for k, v in labels.items()}}))


def observe(event: str, value: float, **labels: object) -> None:
    """One thing happened and it had a size - a reward, a Q-value, a delay."""
    key = _key(event, **labels)
    with _lock:
        _observations[key] += 1
        _sums[key] += float(value)
    logger.info(
        "%s", json.dumps({"event": event, "value": round(float(value), 4), **{k: _plain(v) for k, v in labels.items()}})
    )


def _plain(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def snapshot() -> dict:
    """Everything this worker has counted, plus the means it can compute.

    `means` is where the retention, transfer, failure and leak rates come from:
    each is a counter over a total, and both halves are already here.
    """
    with _lock:
        counters = dict(_counters)
        sums = dict(_sums)
        observations = dict(_observations)
    means = {
        key: round(sums[key] / observations[key], 4)
        for key in sums
        if observations.get(key)
    }
    return {"counters": counters, "means": means, "observations": observations}


def reset() -> None:
    """For the tests, and for a worker that wants a clean window."""
    with _lock:
        _counters.clear()
        _sums.clear()
        _observations.clear()


def _labels_of(key: str) -> set[str]:
    """The `name=value` tokens a counter key carries, as a set.

    A key is `event|a=1,b=2` and `_key` sorts the labels, so the position of any
    one of them depends on what else was passed alongside it. Reading a label
    back by string prefix therefore only works when the event was counted with
    that label and no other - and every event here carries several. That is what
    made `probe_pass_rate` and `answer_leak_rate` report a flat 0.0 however many
    probes had passed or answers had leaked: the lookups were
    `policy.probe|passed=True` and `policy.leak_verdict|kind=leak`, and the real
    keys were `policy.probe|episodes=2,kind=day2,passed=True` and
    `policy.leak_verdict|kind=leak,strategy=S1_TELL`. Membership, not prefix.
    """
    _, _, labels = key.partition("|")
    return set(labels.split(",")) if labels else set()


def rates() -> dict:
    """The handful of ratios a person actually reads, derived from the counters.

    Anything that cannot be computed yet is absent rather than zero - an
    exploration rate of 0.0 on a worker that has served no turns is a lie that
    looks like a healthy number, and so is a leak rate of 0.0 on a worker whose
    lookup never matched anything.
    """
    snap = snapshot()
    counters = snap["counters"]

    def total(event: str, **labels: object) -> int:
        wanted = {f"{name}={value}" for name, value in labels.items()}
        return sum(
            value
            for key, value in counters.items()
            if key.partition("|")[0] == event and wanted <= _labels_of(key)
        )

    decisions = total(DECISION)
    probes = total(PROBE)
    out: dict[str, float] = {}
    if decisions:
        out["exploration_rate"] = round(total(EXPLORE) / decisions, 4)
        out["exploitation_rate"] = round(total(EXPLOIT) / decisions, 4)
        out["fallback_rate"] = round(total(FALLBACK) / decisions, 4)
    if probes:
        out["probe_pass_rate"] = round(total(PROBE, passed=True) / probes, 4)
    leaks = total(LEAK_VERDICT)
    if leaks:
        out["answer_leak_rate"] = round(total(LEAK_VERDICT, kind="leak") / leaks, 4)
    mean_reward = snap["means"].get(REWARD)
    if mean_reward is not None:
        out["average_reward"] = mean_reward
    return out


__all__ = [
    "DB_ERROR",
    "DECISION",
    "ELIGIBILITY_REMOVED",
    "EXPLOIT",
    "EXPLORE",
    "FALLBACK",
    "LEAK_VERDICT",
    "PROBE",
    "Q_UPDATE",
    "REWARD",
    "SELECTION_ERROR",
    "SHADOW",
    "count",
    "observe",
    "rates",
    "reset",
    "snapshot",
]
