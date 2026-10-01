"""Software Engineer: implements the current task, or escalates a clarification
request to the PM if the task is genuinely unimplementable as specified."""
from agents.base import BaseAgent
from config import settings
from schemas.state import ProjectState, ProjectStatus
from schemas.task import TaskStatus
from schemas.implementation import ImplementationSummary
from schemas.messages import AgentMessage, MessageType
from tools.filesystem import apply_file_changes
from utils import context as ctx

SENDER = "software_engineer"

def swe_node(state: ProjectState) -> dict:
    agent = BaseAgent("software_engineer.md")
    task = state.get_current_task()
    prompt_ctx = ctx.swe_context(state)

    result: ImplementationSummary = agent.run(
        prompt_ctx, output_model=ImplementationSummary, temperature=state.config.temperature_swe
    )

    if result.needs_clarification:
        msg = AgentMessage(
            sender=SENDER,
            message_type=MessageType.clarification_request,
            payload={"task_id": task.id, "question": result.clarification_question},
        )

        if state.clarification_rounds >= state.config.max_clarification_rounds:
            # Cap reached (architecture doc, Section 10): stop asking and let
            # the PM move on rather than loop forever. This task is left for
            # human review; project_status is untouched so routing sends us
            # straight to pm_check, not back through pm_plan.
            updated_task = task.model_copy(update={"status": TaskStatus.blocked_needs_human})
            return {
                "tasks": state.with_task_updated(updated_task),
                "messages": state.append_message(msg),
            }

        return {
            "project_status": ProjectStatus.blocked_on_clarification,
            "pending_clarification": result.clarification_question,
            "clarification_rounds": state.clarification_rounds + 1,
            "messages": state.append_message(msg),
        }

    applied, rejected = apply_file_changes(settings.workspace_dir(), result.files_changed)
    if rejected:
        # Only what actually landed on disk goes into the message, so the
        # Testing Agent and QA judge the real diff; QA also sees why the rest
        # is missing and can send it back.
        result = result.model_copy(update={
            "files_changed": applied,
            "summary": (
                f"{result.summary}\n\n[pipeline] Rejected paths outside the "
                f"workspace: {', '.join(rejected)}"
            ),
        })

    updated_task = task.model_copy(update={"status": TaskStatus.in_review})

    msg = AgentMessage(
        sender=SENDER,
        message_type=MessageType.implementation,
        payload=result.model_dump(mode="json"),
    )

    return {
        "tasks": state.with_task_updated(updated_task),
        "messages": state.append_message(msg),
    }
