"""The learned teaching policy: its action space, its state, and its selector.

Nothing in this package talks to a model or to the network. The policy chooses
*which of nine hand-written teaching strategies to spend*; the wording of the
turn is written either by the deterministic guide or, when a provider is
configured, by the LLM under the chosen strategy. What is learned here is the
choice, never the correctness of an answer.
"""
