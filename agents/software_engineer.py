"""Software Engineer: implements the current task, or escalates a clarification
request to the PM if the task is genuinely unimplementable as specified."""
import os

from agents.base import BaseAgent
from schemas.state import ProjectState, ProjectStatus
from schemas.task import TaskStatus
from schemas.implementation import ImplementationSummary
from schemas.messages import AgentMessage, MessageType
from tools.filesystem import apply_file_changes
from utils import context as ctx

SENDER = "software_engineer"

# Where implemented file changes are written. Override via env var for a
# real project checkout; defaults to a local workspace subfolder so the
# system is runnable out of the box.
TARGET_PROJECT_DIR = os.environ.get("AI_TEAM_WORKSPACE", os.path.join(os.getcwd(), "workspace"))


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

    apply_file_changes(TARGET_PROJECT_DIR, result.files_changed)

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
