"""The planner: what this child should do today, decided in pure Python.

The graph lives in `graph.py`. It is the *scheduler* half of the two roles in
`docs/AGENT-FLOW.md` - it never teaches, never grades, and never decides whether
a skill is mastered. It takes the topics `plan_service` has already declared
legal for today - one level from each of the child's subjects - and puts them in
the order a sitting should run in.

**No language model is involved.** There was one, and it was taken out: ordering
a handful of known topics is a small decision with a rule that can be read, and
an answer that has to be validated before it can be trusted is worth less than
one that was right by construction. `daily_plans.source` is always
`deterministic`.
"""

from app.ai.planner.graph import PlannerResult, plan_today

__all__ = ["PlannerResult", "plan_today"]
