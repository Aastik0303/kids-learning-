"""The Planner Agent: what this child should do today.

The graph lives in `graph.py`. It is the *scheduler* half of the two agents in
`docs/AGENT-FLOW.md` - it never teaches, never grades, and never decides whether
a skill is mastered. It picks an order for a list of topics the deterministic
layer has already declared legal, and the order it returns is validated against
that list before anything is written.
"""

from app.ai.planner.graph import PlannerResult, plan_today

__all__ = ["PlannerResult", "plan_today"]
