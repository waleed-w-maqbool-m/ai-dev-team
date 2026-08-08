"""Project Manager: planning mode and status-check mode.

Both modes share the same role but use different prompts/schemas, so they're
implemented as two node functions rather than one node with a branching flag —
this keeps the graph's edges simple conditionals (Section 2/14 of the
architecture doc).
"""
from agents.base import BaseAgent
from schemas.state import ProjectState, ProjectStatus
from schemas.plan import ProjectPlan, PMCheckOutput
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

    first_task = plan.tasks[0] if plan.tasks else None

    return {
        "tasks": plan.tasks,
        "current_task_id": first_task.id if first_task else None,
        "project_status": ProjectStatus.in_progress if plan.tasks else ProjectStatus.blocked_on_clarification,
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

    updates: dict = {
        "project_status": ProjectStatus(result.project_status),
        "messages": state.append_message(msg),
    }

    if result.project_status == ProjectStatus.blocked_on_clarification.value:
        updates["pending_clarification"] = result.notes
        updates["clarification_rounds"] = state.clarification_rounds + 1
    elif result.next_task_id:
        updates["current_task_id"] = result.next_task_id

    return updates
