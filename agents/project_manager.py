"""Project Manager: planning mode and status-check mode.

Both modes share the same role but use different prompts/schemas, so they're
implemented as two node functions rather than one node with a branching flag —
this keeps the graph's edges simple conditionals (Section 2/14 of the
architecture doc).
"""
from agents.base import BaseAgent
from schemas.state import ProjectState, ProjectStatus
from schemas.plan import ProjectPlan, PMCheckOutput
from schemas.task import TaskStatus
from schemas.messages import AgentMessage, MessageType
from utils import context as ctx

SENDER = "project_manager"


def pm_plan_node(state: ProjectState) -> dict:
    """Initial planning, or re-planning after a clarification round."""
    agent = BaseAgent("project_manager.md")

    if state.pending_clarification:
        # Re-planning branch: ask the same agent to resolve its own question
        # using the original request (per the prompt's "resolve it yourself"
        # instruction), then fall through to a normal plan.
        prompt_ctx = ctx.pm_reclarify_context(state)
    else:
        prompt_ctx = ctx.pm_planning_context(state)

    plan: ProjectPlan = agent.run(
        prompt_ctx, output_model=ProjectPlan, temperature=state.config.temperature_pm
    )

    msg = AgentMessage(
        sender=SENDER,
        message_type=MessageType.plan,
        payload=plan.model_dump(mode="json"),
    )

    # A fresh plan starts from scratch whatever the model echoed back for
    # status/history, and the first task must be one whose dependencies are
    # satisfiable — not just tasks[0].
    tasks = [
        t.model_copy(update={"status": TaskStatus.pending, "review_history": [], "test_report": None})
        for t in plan.tasks
    ]
    planned = state.model_copy(update={"tasks": tasks})
    tasks = planned.tasks_with_unrunnable_blocked()
    first_task = planned.model_copy(update={"tasks": tasks}).next_pending_task()

    return {
        "tasks": tasks,
        "current_task_id": first_task.id if first_task else None,
        "project_status": ProjectStatus.in_progress if first_task else ProjectStatus.documenting,
        "pending_clarification": None,
        "messages": state.append_message(msg),
    }


def pm_check_node(state: ProjectState) -> dict:
    """Post-review (or post-clarification-request) routing decision."""
    agent = BaseAgent("project_manager_check.md")
    prompt_ctx = ctx.pm_check_context(state)

    result: PMCheckOutput = agent.run(
        prompt_ctx, output_model=PMCheckOutput, temperature=state.config.temperature_pm
    )

    msg = AgentMessage(
        sender=SENDER,
        message_type=MessageType.status,
        payload=result.model_dump(mode="json"),
    )

    updates: dict = {"messages": state.append_message(msg)}

    if result.project_status == ProjectStatus.blocked_on_clarification.value:
        updates["project_status"] = ProjectStatus.blocked_on_clarification
        updates["pending_clarification"] = result.notes
        updates["clarification_rounds"] = state.clarification_rounds + 1
        return updates

    # The model's next_task_id and status are only a preference. Which task
    # runs next is checked against the dependency graph here, so a
    # hallucinated id, an already-done task, or "documenting" with work left
    # can't send the Engineer to the wrong place.
    tasks = state.tasks_with_unrunnable_blocked()
    next_task = state.model_copy(update={"tasks": tasks}).next_pending_task(preferred_id=result.next_task_id)
    updates["tasks"] = tasks
    if next_task:
        updates["project_status"] = ProjectStatus.in_progress
        updates["current_task_id"] = next_task.id
    else:
        updates["project_status"] = ProjectStatus.documenting
    return updates
