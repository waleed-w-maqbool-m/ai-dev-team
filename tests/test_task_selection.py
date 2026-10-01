"""Which task runs next is decided against the dependency graph, never by
trusting the PM model's free-form answer. These runs feed the PM bad
suggestions and impossible plans, and check that the run still finishes."""
import json

import pytest

import agents.base as base_module
from graph.build_graph import build_graph
from schemas.documentation import DocumentationOutput
from schemas.implementation import FileAction, FileChange, ImplementationSummary
from schemas.plan import PMCheckOutput, ProjectPlan
from schemas.review import ReviewReport
from schemas.state import ProjectState, ProjectStatus
from schemas.task import AcceptanceCriterion, Task, TaskStatus


def _task(task_id: str, depends_on: list[str] | None = None, **extra) -> Task:
    return Task(
        id=task_id,
        title=f"Task {task_id}",
        description="n/a",
        depends_on=depends_on or [],
        acceptance_criteria=[AcceptanceCriterion(id="AC1", description="works")],
        **extra,
    )


def _run(monkeypatch, tasks, pm_check=None, qa_passes=lambda task_id: True):
    """Runs the real graph with a scripted LLM. Returns (final state, ids of
    tasks the Engineer was asked to implement, in order)."""
    implemented: list[str] = []

    def fake_run(self, context, output_model, temperature=0.2):
        if output_model is ProjectPlan:
            return ProjectPlan(overview="test", tasks=tasks)
        if output_model is ImplementationSummary:
            task_id = json.loads(context)["task"]["id"]
            implemented.append(task_id)
            return ImplementationSummary(
                task_id=task_id,
                files_changed=[FileChange(path=f"{task_id.lower()}.py", action=FileAction.create, content="x = 1\n")],
            )
        if output_model is ReviewReport:
            task_id = json.loads(context)["task"]["id"]
            return ReviewReport(task_id=task_id, status="pass" if qa_passes(task_id) else "fail",
                                required_fixes=[] if qa_passes(task_id) else ["fix it"])
        if output_model is PMCheckOutput:
            return pm_check() if pm_check else PMCheckOutput(project_status="in_progress")
        if output_model is DocumentationOutput:
            return DocumentationOutput(readme_updates="", changelog_entries=[], user_summary="done")
        raise AssertionError(output_model)

    monkeypatch.setattr(base_module.BaseAgent, "run", fake_run)
    app = build_graph(checkpointer=None)
    result = app.invoke(
        ProjectState.new(user_request="test"),
        config={"configurable": {"thread_id": "t"}, "recursion_limit": 60},
    )
    return ProjectState.model_validate(result), implemented


def test_pm_suggesting_a_done_task_does_not_redo_it(monkeypatch):
    state, implemented = _run(
        monkeypatch,
        [_task("T1"), _task("T2", ["T1"])],
        pm_check=lambda: PMCheckOutput(project_status="in_progress", next_task_id="T1"),
    )
    assert implemented == ["T1", "T2"]
    assert state.project_status == ProjectStatus.complete


@pytest.mark.parametrize("bad_id", ["T99", "", None])
def test_pm_suggesting_an_unknown_task_falls_back_to_a_runnable_one(monkeypatch, bad_id):
    state, implemented = _run(
        monkeypatch,
        [_task("T1"), _task("T2", ["T1"])],
        pm_check=lambda: PMCheckOutput(project_status="in_progress", next_task_id=bad_id),
    )
    assert implemented == ["T1", "T2"]
    assert all(t.status == TaskStatus.done for t in state.tasks)


def test_pm_declaring_done_early_or_inventing_a_status_does_not_skip_work(monkeypatch):
    for status in ["documenting", "done", "complete!!"]:
        state, implemented = _run(
            monkeypatch,
            [_task("T1"), _task("T2")],
            pm_check=lambda: PMCheckOutput(project_status=status),
        )
        assert implemented == ["T1", "T2"], status
        assert state.project_status == ProjectStatus.complete


def test_tasks_depending_on_a_blocked_task_are_set_aside_not_looped(monkeypatch):
    state, implemented = _run(
        monkeypatch,
        [_task("T1"), _task("T2", ["T1"]), _task("T3", ["T2"])],
        qa_passes=lambda task_id: task_id != "T1",
    )
    assert implemented == ["T1"] * state.config.max_review_iterations
    assert [t.status for t in state.tasks] == [TaskStatus.blocked_needs_human] * 3
    assert state.project_status == ProjectStatus.complete


def test_dependency_cycle_finishes_without_running_anything(monkeypatch):
    state, implemented = _run(monkeypatch, [_task("T1", ["T2"]), _task("T2", ["T1"])])
    assert implemented == []
    assert all(t.status == TaskStatus.blocked_needs_human for t in state.tasks)
    assert state.project_status == ProjectStatus.complete


def test_empty_plan_goes_straight_to_docs(monkeypatch):
    state, implemented = _run(monkeypatch, [])
    assert implemented == []
    assert state.project_status == ProjectStatus.complete


def test_first_task_is_the_first_runnable_one_not_list_order(monkeypatch):
    _, implemented = _run(monkeypatch, [_task("T2", ["T1"]), _task("T1")])
    assert implemented == ["T1", "T2"]


def test_plan_echoing_done_status_is_reset_to_pending(monkeypatch):
    _, implemented = _run(monkeypatch, [_task("T1", status=TaskStatus.done), _task("T2", ["T1"])])
    assert implemented == ["T1", "T2"]
