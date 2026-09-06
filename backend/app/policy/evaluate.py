"""Offline evaluation: is the learned policy actually better than the ladder?

Read this before believing any claim that it is.

The data is `policy_episodes`, and every row of it was produced by whichever
policy was live at the time. Comparing a counterfactual policy against that log
honestly means one thing: **the replay estimator**. For each settled episode we
ask what the candidate policy would have chosen in that state, out of the same
eligible set; if it matches what was actually spent, the episode's real reward
counts towards that candidate, and if it does not, the episode tells us nothing
about the candidate and is skipped. The estimate is then the mean reward over
the matched episodes only, and `coverage` says how much of the log that was.

This is unbiased when the logging policy was stochastic over the matched
actions, which is what the exploration rate buys, and it is *not* unbiased for
a purely greedy log. Both facts are reported rather than smoothed over:
`report.warnings` says so out loud when coverage is thin or exploration was off.

`verdict()` will not call a winner unless three things hold at once:

- both arms have at least `MIN_EPISODES` matched episodes;
- the mean-reward difference clears two standard errors of the difference;
- the candidate is not leaking more answers than the baseline.

Anything less prints "no difference demonstrated", which is the honest reading
of almost every early result and is the whole reason this module exists. A
policy that teaches four-year-olds does not get the benefit of the doubt.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.repositories import policy as policy_repo
from app.policy import actions, eligibility, selector


# Below this many matched episodes per arm, no comparison is reported at all.
# Nine actions and a discretised state space is a small problem, but a mean over
# thirty rewards that range from -2.0 to +1.35 is still noise.
MIN_EPISODES = 30

LADDER = "ladder"
RANDOM = "random"
LEARNED = "qlearning"


@dataclass
class ArmResult:
    name: str
    matched: int = 0
    total_reward: float = 0.0
    d2_passes: int = 0
    d2_total: int = 0
    d7_passes: int = 0
    d7_total: int = 0
    transfers: int = 0
    failures: int = 0
    leaks: int = 0
    rewards: list[float] = field(default_factory=list)
    strategies: dict[str, int] = field(default_factory=dict)

    @property
    def mean_reward(self) -> float | None:
        return (self.total_reward / self.matched) if self.matched else None

    @property
    def standard_error(self) -> float | None:
        if self.matched < 2:
            return None
        mean = self.total_reward / self.matched
        variance = sum((r - mean) ** 2 for r in self.rewards) / (self.matched - 1)
        return math.sqrt(variance / self.matched)

    def _rate(self, hits: int, total: int) -> float | None:
        return round(hits / total, 4) if total else None

    def summary(self) -> dict:
        return {
            "arm": self.name,
            "matched_episodes": self.matched,
            "mean_reward": round(self.mean_reward, 4) if self.mean_reward is not None else None,
            "standard_error": round(self.standard_error, 4) if self.standard_error else None,
            "d2_retention": self._rate(self.d2_passes, self.d2_total),
            "d7_retention": self._rate(self.d7_passes, self.d7_total),
            "transfer_rate": self._rate(self.transfers, self.matched),
            "failure_rate": self._rate(self.failures, self.matched),
            "answer_leak_rate": self._rate(self.leaks, self.matched),
            "strategy_distribution": dict(sorted(self.strategies.items())),
        }


@dataclass
class Report:
    arms: dict[str, ArmResult]
    episodes: int
    warnings: list[str] = field(default_factory=list)

    def coverage(self, name: str) -> float | None:
        arm = self.arms.get(name)
        if arm is None or not self.episodes:
            return None
        return round(arm.matched / self.episodes, 4)

    def verdict(self) -> dict:
        """Defined here, implemented below - the module function is the one to
        read, and this is the form the report renders with."""
        return verdict(self)

    def as_dict(self) -> dict:
        return {
            "settled_episodes": self.episodes,
            "arms": {name: arm.summary() for name, arm in self.arms.items()},
            "coverage": {name: self.coverage(name) for name in self.arms},
            "verdict": self.verdict(),
            "warnings": self.warnings,
        }


def _context_for(episode) -> eligibility.TurnContext:
    """Rebuild the turn's eligibility context from what the episode recorded.

    `spent` is not stored as a list, only as a count, so the exact spent set
    cannot be reconstructed - which is why the candidate policies are replayed
    against the *episode's own* eligible superset rather than against a guess.
    The action actually taken is guaranteed to be in it, and that is what the
    match test needs.
    """
    mode = "early" if (episode.state_key or "").startswith("early") else "standard"
    return eligibility.TurnContext(experience_mode=mode, rung=episode.rung or 0, spent=())


def _candidate_actions(episode) -> list[str]:
    allowed = eligibility.decide(_context_for(episode)).allowed
    # The action that was really spent must be a candidate, or no episode ever
    # matches and every arm reports zero.
    if episode.action not in allowed:
        allowed = [*allowed, episode.action]
    return allowed


def _ladder_action(episode, allowed: list[str]) -> str:
    mode = "early" if (episode.state_key or "").startswith("early") else "standard"
    preferred = actions.ladder_prior_for(mode).get(episode.rung or 0, ())
    chosen, _ = selector.choose(legal=allowed, stats={}, preferred=preferred, explore_rate=0.0)
    return chosen


def _learned_action(session: Session, episode, allowed: list[str]) -> str:
    mode = "early" if (episode.state_key or "").startswith("early") else "standard"
    preferred = actions.ladder_prior_for(mode).get(episode.rung or 0, ())
    stats = policy_repo.action_stats(session, state_key=episode.state_key)
    chosen, _ = selector.choose(legal=allowed, stats=stats, preferred=preferred, explore_rate=0.0)
    return chosen


def _credit(arm: ArmResult, episode) -> None:
    arm.matched += 1
    reward = float(episode.reward or 0.0)
    arm.total_reward += reward
    arm.rewards.append(reward)
    arm.strategies[episode.action] = arm.strategies.get(episode.action, 0) + 1
    if episode.probe_kind == "day2":
        arm.d2_total += 1
        arm.d2_passes += 1 if episode.probe_passed else 0
    elif episode.probe_kind == "day7":
        arm.d7_total += 1
        arm.d7_passes += 1 if episode.probe_passed else 0
    if episode.probe_passed is False:
        arm.failures += 1
    # Transfer is the bonus the probe paid for being asked in a different form.
    if episode.probe_passed and reward > policy_repo.REWARD_RETENTION_PASS:
        arm.transfers += 1
    if episode.answer_leak_vetoed:
        arm.leaks += 1


def run(session: Session, *, since: datetime | None = None, seed: int = 7) -> Report:
    """Replay the three policies over the settled episodes."""
    episodes = policy_repo.settled_episodes(session, since=since)
    rng = random.Random(seed)
    arms = {name: ArmResult(name) for name in (LADDER, RANDOM, LEARNED)}

    explored_any = False
    for episode in episodes:
        explored_any = explored_any or bool(episode.explored)
        allowed = _candidate_actions(episode)
        proposals = {
            LADDER: _ladder_action(episode, allowed),
            RANDOM: rng.choice(allowed),
            LEARNED: _learned_action(session, episode, allowed),
        }
        for name, proposed in proposals.items():
            if proposed == episode.action:
                _credit(arms[name], episode)

    report = Report(arms=arms, episodes=len(episodes))
    if not episodes:
        report.warnings.append("No settled episodes yet - nothing can be concluded.")
    if not explored_any and episodes:
        report.warnings.append(
            "The log contains no exploration, so the replay estimate is biased towards "
            "whichever policy generated it. Treat every number here as descriptive."
        )
    for name, arm in arms.items():
        if arm.matched < MIN_EPISODES:
            report.warnings.append(
                f"{name}: only {arm.matched} matched episodes, below the {MIN_EPISODES} floor."
            )
    return report


def verdict(report: Report, *, candidate: str = LEARNED, baseline: str = LADDER) -> dict:
    """Whether the candidate has actually been shown to be better. Usually not."""
    a, b = report.arms.get(candidate), report.arms.get(baseline)
    if a is None or b is None:
        return {"conclusion": "unknown", "reason": "missing arm"}
    if a.matched < MIN_EPISODES or b.matched < MIN_EPISODES:
        return {
            "conclusion": "no difference demonstrated",
            "reason": f"not enough matched episodes ({candidate}={a.matched}, {baseline}={b.matched})",
        }

    mean_a, mean_b = a.mean_reward or 0.0, b.mean_reward or 0.0
    se_a, se_b = a.standard_error or 0.0, b.standard_error or 0.0
    combined = math.sqrt(se_a**2 + se_b**2)
    difference = mean_a - mean_b

    leak_a = a.leaks / a.matched if a.matched else 0.0
    leak_b = b.leaks / b.matched if b.matched else 0.0
    if leak_a > leak_b:
        return {
            "conclusion": "candidate rejected",
            "reason": f"{candidate} leaks the answer more often ({leak_a:.3f} vs {leak_b:.3f})",
            "reward_difference": round(difference, 4),
        }
    if combined and difference > 2 * combined:
        return {
            "conclusion": f"{candidate} better",
            "reason": f"reward +{difference:.4f}, over two standard errors ({combined:.4f})",
            "reward_difference": round(difference, 4),
        }
    return {
        "conclusion": "no difference demonstrated",
        "reason": f"reward difference {difference:.4f} is inside the noise ({2 * combined:.4f})",
        "reward_difference": round(difference, 4),
    }


def main() -> None:  # pragma: no cover - operator entry point
    import json

    from app.db.session import session_scope

    with session_scope() as session:
        print(json.dumps(run(session).as_dict(), indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["LADDER", "LEARNED", "MIN_EPISODES", "RANDOM", "ArmResult", "Report", "run", "verdict"]
