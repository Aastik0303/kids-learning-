from langgraph.graph import END, START, StateGraph

from app.graph.state import GuideState


def _identity(state: GuideState) -> GuideState:
    return state


def build_guide_graph():
    """Single Guide Agent LangGraph scaffold.

    The active HTTP path is app.services.guide_agent_service. This graph mirrors
    the intended production shape without adding multiple agents.
    """

    graph = StateGraph(GuideState)
    graph.add_node("validate_request", _identity)
    graph.add_node("build_guide_context", _identity)
    graph.add_node("little_learning_guide", _identity)
    graph.add_node("validate_json_output", _identity)
    graph.add_node("validate_ui_action", _identity)
    graph.add_node("safety_check", _identity)
    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "build_guide_context")
    graph.add_edge("build_guide_context", "little_learning_guide")
    graph.add_edge("little_learning_guide", "validate_json_output")
    graph.add_edge("validate_json_output", "validate_ui_action")
    graph.add_edge("validate_ui_action", "safety_check")
    graph.add_edge("safety_check", END)
    return graph.compile()
