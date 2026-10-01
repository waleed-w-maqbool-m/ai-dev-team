"""Builds the role-scoped context each agent receives.

Centralizing this (rather than letting each agent module pull whatever it
wants from ProjectState) is what keeps the "who sees what" policy auditable
in one file, per the architecture doc's context-passing design (Section 13).
"""
import json

from schemas.messages import MessageType
from schemas.state import ProjectState
from schemas.task import Task


def latest_implementation_payload(state: ProjectState, task_id: str) -> dict:
    """The most recent ImplementationSummary payload for a task — shared by
    the Testing Agent (what to execute) and QA (what to review), so both
    agents look at the same submitted diff."""
    for msg in reversed(state.messages):
        if msg.message_type == MessageType.implementation and msg.payload.get("task_id") == task_id:
            return msg.payload
    return {"files_changed": []}


def _task_brief(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "depends_on": task.depends_on,
    }


def pm_planning_context(state: ProjectState) -> str:
    """PM sees: the original request. Used for initial planning only."""
    return json.dumps({"user_request": state.user_request}, indent=2)


def pm_reclarify_context(state: ProjectState) -> str:
    """PM sees: the original request + the outstanding clarification question."""
    return json.dumps(
        {
            "user_request": state.user_request,
            "pending_clarification": state.pending_clarification,
            "clarification_rounds_so_far": state.clarification_rounds,
        },
        indent=2,
    )


def pm_check_context(state: ProjectState) -> str:
    """PM sees: full task list + status, and the latest QA report if present."""
    task = state.get_current_task()
    latest_review = task.latest_review() if task else None
    return json.dumps(
        {
            "tasks": [_task_brief(t) for t in state.tasks],
            "current_task_id": state.current_task_id,
            "latest_review": latest_review.model_dump() if latest_review else None,
        },
        indent=2,
    )


def swe_context(state: ProjectState) -> str:
    """SWE sees: only its assigned task, plus required_fixes on retry —
    not the full review history, per the doc's context-minimization rule."""
    task = state.get_current_task()
    latest_review = task.latest_review()
    required_fixes = latest_review.required_fixes if latest_review and latest_review.status == "fail" else []
    return json.dumps(
        {
            "task": {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "acceptance_criteria": [
                    {"id": c.id, "description": c.description} for c in task.acceptance_criteria
                ],
            },
            "required_fixes": required_fixes,
            "is_retry": bool(required_fixes),
        },
        indent=2,
    )


def qa_context(state: ProjectState, files_changed: list[dict]) -> str:
    """QA sees: the task's acceptance criteria + the SWE's current diff —
    not prior failed attempts, so it always judges the current code fresh —
    plus the Testing Agent's executed evidence for this same diff, so QA's
    verdict is evidence-based rather than purely by inspection."""
    task = state.get_current_task()
    return json.dumps(
        {
            "task": {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "acceptance_criteria": [
                    {"id": c.id, "description": c.description} for c in task.acceptance_criteria
                ],
            },
            "files_changed": files_changed,
            "test_report": task.test_report.model_dump() if task.test_report else None,
        },
        indent=2,
    )


def docs_context(state: ProjectState) -> str:
    """Docs sees: completed tasks + their implementation summaries only —
    not raw diffs, to keep docs focused on user-facing behavior."""
    done_tasks = [t for t in state.tasks if t.status.value == "done"]
    summaries = []
    for msg in state.messages:
        if msg.message_type.value == "implementation" and msg.payload.get("task_id") in {
            t.id for t in done_tasks
        }:
            summaries.append(msg.payload)
    return json.dumps(
        {
            "user_request": state.user_request,
            "completed_tasks": [_task_brief(t) for t in done_tasks],
            "implementation_summaries": summaries,
        },
        indent=2,
    )
