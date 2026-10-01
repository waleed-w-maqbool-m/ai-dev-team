"""Verifies the QA retry cap: a task that keeps failing review gets marked
blocked_needs_human after max_review_iterations, and the pipeline still
reaches project_status=complete instead of looping forever."""
import json

import agents.base as base_module
from graph.build_graph import build_graph
from schemas.state import ProjectState, ProjectStatus
from schemas.task import Task, AcceptanceCriterion, TaskStatus
from schemas.plan import ProjectPlan, PMCheckOutput
from schemas.implementation import ImplementationSummary, FileChange, FileAction
from schemas.review import ReviewReport, CriterionFinding
from schemas.documentation import DocumentationOutput

call_counts: dict[str, int] = {}


def fake_run(self, context: str, output_model, temperature: float = 0.2):
    name = output_model.__name__
    call_counts[name] = call_counts.get(name, 0) + 1

    if output_model is ProjectPlan:
        return ProjectPlan(
            overview="Single always-failing task.",
            tasks=[
                Task(
                    id="T1",
                    title="Impossible task",
                    description="QA will always fail this.",
                    acceptance_criteria=[AcceptanceCriterion(id="AC1", description="Never actually met")],
                )
            ],
        )

    if output_model is ImplementationSummary:
        ctx_data = json.loads(context)
        return ImplementationSummary(
            task_id=ctx_data["task"]["id"],
            files_changed=[FileChange(path="t1.py", action=FileAction.create, content="# attempt\n")],
            summary="Attempted implementation.",
        )

    if output_model is ReviewReport:
        ctx_data = json.loads(context)
        # Always fail, no matter how many times we retry.
        return ReviewReport(
            task_id=ctx_data["task"]["id"],
            status="fail",
            findings=[CriterionFinding(criterion_id="AC1", met=False, note="still not met")],
            required_fixes=["Try again"],
            summary="Still failing.",
        )

    if output_model is PMCheckOutput:
        ctx_data = json.loads(context)
        remaining = [
            t for t in ctx_data["tasks"] if t["status"] in ("pending", "in_progress", "in_review")
        ]
        if remaining:
            return PMCheckOutput(project_status="in_progress", next_task_id=remaining[0]["id"])
        return PMCheckOutput(project_status="documenting", notes="wrapping up despite blocked task")

    if output_model is DocumentationOutput:
        return DocumentationOutput(
            readme_updates="Partial progress documented.",
            changelog_entries=["T1 attempted but not completed"],
            user_summary="T1 could not be completed automatically and needs human review.",
        )

    raise AssertionError(f"Unexpected output_model requested: {name}")


def test_review_cap_bounds_the_qa_loop(monkeypatch):
    call_counts.clear()
    monkeypatch.setattr(base_module.BaseAgent, "run", fake_run)

    app = build_graph(checkpointer=None)
    initial_state = ProjectState.new(user_request="Single always-failing task.")
    result_dict = app.invoke(
        initial_state,
        config={"configurable": {"thread_id": "test-cap"}, "recursion_limit": 100},
    )
    final_state = ProjectState.model_validate(result_dict)

    assert final_state.get_task("T1").status == TaskStatus.blocked_needs_human
    assert final_state.review_iterations["T1"] == final_state.config.max_review_iterations
    assert call_counts["ReviewReport"] == final_state.config.max_review_iterations, (
        "QA should stop being called once the cap is reached, not loop forever"
    )
    assert final_state.project_status == ProjectStatus.complete, (
        "pipeline must still finish (with the task left blocked) instead of hanging"
    )
