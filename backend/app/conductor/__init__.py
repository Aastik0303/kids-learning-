"""The Class Conductor: the thing that runs the class.

Before this package existed the server answered events. The client asked "what
do I say now?", got one message back, and nothing anywhere knew what phase the
lesson was in, what had already been tried, or what should happen if the child
simply stopped tapping. That is a commentator, not a teacher.

The conductor holds the lesson state on the server and decides the next step
itself. The decision half lives here and is pure Python:

- `phases.py` - the state machine: greet, set, I do, we do, you do, check,
  branch, close.
- `branch.py` - the Branch Decision Engine. Six outcomes, one fixed priority
  order, no model.
- `signals.py` - frustration, boredom and the idle ladder, as formulas.
- `scaffold.py` - how much help the child gets on this turn, and what the client
  is allowed to render.

`app/services/conductor_service.py` is the half that touches the database and
the voice. The split is the point: everything that decides is testable without a
network, and a model only ever writes the sentence a decision has already made.
"""
