"""End-to-end test of the full graph with the LLM layer mocked out.

This does NOT require a running Ollama server. It monkeypatches
BaseAgent.run (the single seam every agent calls through) with a scripted
fake that simulates: a Software Engineer clarification round, a QA
fail-then-pass cycle, a two-task dependency chain, and final documentation —
which together exercise every conditional edge in the graph.
"""
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
    n = call_counts[name]

    if output_model is ProjectPlan:
        return ProjectPlan(
            overview="Build a two-step demo pipeline.",
            tasks=[
                Task(
                    id="T1",
                    title="Set up project skeleton",
                    description="Create the base module.",
                    acceptance_criteria=[AcceptanceCriterion(id="AC1", description="File exists")],
                ),
                Task(
                    id="T2",
                    title="Add feature on top of T1",
                    description="Add the feature.",
                    depends_on=["T1"],
                    acceptance_criteria=[AcceptanceCriterion(id="AC1", description="Feature works")],
                ),
            ],
        )

    if output_model is ImplementationSummary:
        ctx_data = json.loads(context)
        task_id = ctx_data["task"]["id"]
        if task_id == "T1" and n == 1:
            # First attempt at T1 asks a clarifying question.
            return ImplementationSummary(
                task_id=task_id,
                needs_clarification=True,
                clarification_question="Which base language should be used?",
            )
        return ImplementationSummary(
            task_id=task_id,
            files_changed=[
                FileChange(path=f"{task_id.lower()}.py", action=FileAction.create, content="# implementation\n")
            ],
            summary=f"Implemented {task_id}.",
        )

    if output_model is ReviewReport:
        ctx_data = json.loads(context)
        task_id = ctx_data["task"]["id"]
        if task_id == "T1" and n == 1:
            # First QA pass on T1 fails once, to exercise the retry loop.
            return ReviewReport(
                task_id=task_id,
                status="fail",
                findings=[CriterionFinding(criterion_id="AC1", met=False, note="file missing")],
                required_fixes=["Actually create the file"],
                summary="Not done yet.",
            )
        return ReviewReport(
            task_id=task_id,
            status="pass",
            findings=[CriterionFinding(criterion_id="AC1", met=True, note="looks good")],
            summary="Meets criteria.",
        )

    if output_model is PMCheckOutput:
        ctx_data = json.loads(context)
        remaining = [
            t for t in ctx_data["tasks"] if t["status"] in ("pending", "in_progress", "in_review")
        ]
        if remaining:
            return PMCheckOutput(project_status="in_progress", next_task_id=remaining[0]["id"])
        return PMCheckOutput(project_status="documenting", notes="all tasks resolved")

    if output_model is DocumentationOutput:
        return DocumentationOutput(
            readme_updates="## New Feature\nAdded T1 and T2.",
            changelog_entries=["Added T1", "Added T2"],
            docstring_updates={"t1.py": '"""T1 module."""'},
            user_summary="Both tasks completed successfully.",
        )

    raise AssertionError(f"Unexpected output_model requested: {name}")


def test_full_pipeline_happy_path(monkeypatch, isolated_workspace):
    call_counts.clear()
    monkeypatch.setattr(base_module.BaseAgent, "run", fake_run)  # the single LLM seam

    app = build_graph(checkpointer=None)
    initial_state = ProjectState.new(user_request="Build a two-step demo pipeline.")
    result_dict = app.invoke(initial_state, config={"configurable": {"thread_id": "test-1"}})
    final_state = ProjectState.model_validate(result_dict)

    assert final_state.project_status == ProjectStatus.complete, "project should complete"
    assert final_state.get_task("T1").status == TaskStatus.done
    assert final_state.get_task("T2").status == TaskStatus.done
    assert final_state.clarification_rounds == 1, "expected exactly one clarification round"
    assert final_state.review_iterations.get("T1") == 1, "expected exactly one QA-fail on T1"
    assert final_state.documentation is not None
    assert final_state.final_summary
    assert [m.message_type.value for m in final_state.messages] == [
        "plan", "clarification_request", "plan",
        "implementation", "test_report", "review",   # T1 fails QA once
        "implementation", "test_report", "review", "status",
        "implementation", "test_report", "review", "status",
        "documentation",
    ]

    for name in ["t1.py", "t2.py", "README.md", "CHANGELOG.md"]:
        assert (isolated_workspace / name).exists(), name
