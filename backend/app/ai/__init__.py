"""Everything that talks to a language model, and nothing that decides anything.

The boundary this package draws is the one rule the project does not move: a
model writes *wording*. It never grades an answer, awards a star, unlocks a
topic or issues a certificate. `app/services/activity_evaluators.py` and
`app/db/repositories/truth.py` do those in pure Python and import nothing from
here - a check `tests/test_policy_wiring.py` makes on the import graph itself.
"""
