"""Builds the compiled LangGraph app. Wiring only — all business logic lives
in agents/*.py, all routing logic lives in graph/routing.py."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from schemas.state import ProjectState
from agents.project_manager import pm_plan_node, pm_check_node
from agents.software_engineer import swe_node
from agents.testing import testing_node
from agents.qa_reviewer import qa_node
from agents.documentation import docs_node
from graph.routing import route_after_pm_plan, route_after_swe, route_after_qa, route_after_pm_check


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    graph = StateGraph(ProjectState)

    graph.add_node("pm_plan", pm_plan_node)
    graph.add_node("swe", swe_node)
    graph.add_node("testing", testing_node)
    graph.add_node("qa", qa_node)
    graph.add_node("pm_check", pm_check_node)
    graph.add_node("docs", docs_node)

    graph.add_edge(START, "pm_plan")
    graph.add_conditional_edges("pm_plan", route_after_pm_plan, {"swe": "swe", "docs": "docs"})

    graph.add_conditional_edges(
        "swe", route_after_swe, {"testing": "testing", "pm_plan": "pm_plan", "pm_check": "pm_check"}
    )
    graph.add_edge("testing", "qa")  # unconditional: testing never decides routing, only writes evidence
    graph.add_conditional_edges(
        "qa", route_after_qa, {"swe": "swe", "pm_check": "pm_check"}
    )
    graph.add_conditional_edges(
        "pm_check",
        route_after_pm_check,
        {"pm_plan": "pm_plan", "swe": "swe", "docs": "docs"},
    )
    graph.add_edge("docs", END)

    return graph.compile(checkpointer=checkpointer)
