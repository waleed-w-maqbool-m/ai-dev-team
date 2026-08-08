"""All routing decisions are plain Python reading structured state fields —
never a second LLM call interpreting free text. This is what keeps the graph
deterministic on a small model (architecture doc, Section 1 & 14)."""
from schemas.state import ProjectState, ProjectStatus
from schemas.task import TaskStatus


def route_after_swe(state: ProjectState) -> str:
    """SWE either implemented the task, hit the clarification cap (task now
    blocked_needs_human — go straight to pm_check to move on), or requested
    clarification while still under the cap (go to pm_plan, which resolves
    it and re-plans; see agents/project_manager.py's reclarify branch).
    A successful implementation goes to the Testing Agent before QA, so QA
    reviews with executed evidence in hand rather than by inspection alone."""
    task = state.get_current_task()
    if task.status == TaskStatus.blocked_needs_human:
        return "pm_check"
    if state.project_status == ProjectStatus.blocked_on_clarification:
        return "pm_plan"
    return "testing"


def route_after_qa(state: ProjectState) -> str:
    task = state.get_current_task()
    # qa_node already resolved pass / fail-under-cap / fail-cap-reached into
    # task.status (done / in_progress / blocked_needs_human respectively) —
    # routing just reads that, it never re-derives the cap check.
    if task.status.value == "in_progress":
        return "swe"  # fail, still under the retry cap
    return "pm_check"  # done, or blocked_needs_human


def route_after_pm_check(state: ProjectState) -> str:
    if state.project_status == ProjectStatus.blocked_on_clarification:
        if state.clarification_rounds >= state.config.max_clarification_rounds:
            # Cap reached: PM must proceed with its best assumption rather
            # than loop forever (architecture doc, Section 10).
            return "docs" if not state.has_remaining_tasks() else "swe"
        return "pm_plan"

    if state.has_remaining_tasks():
        return "swe"

    return "docs"
