"""Documentation Agent: writes README/changelog/docstring updates for all
completed tasks and produces the final user-facing summary. Runs once, after
the Project Manager has determined no tasks remain in progress."""
import os
from datetime import datetime

from agents.base import BaseAgent
from config import settings
from schemas.state import ProjectState, ProjectStatus
from schemas.documentation import DocumentationOutput
from schemas.messages import AgentMessage, MessageType
from utils import context as ctx

SENDER = "documentation"

def _write_docs_to_disk(output: DocumentationOutput) -> None:
    workspace = settings.workspace_dir()
    os.makedirs(workspace, exist_ok=True)

    if output.readme_updates:
        readme_path = os.path.join(workspace, "README.md")
        with open(readme_path, "a", encoding="utf-8") as f:
            f.write("\n\n" + output.readme_updates + "\n")

    if output.changelog_entries:
        changelog_path = os.path.join(workspace, "CHANGELOG.md")
        date = datetime.now().strftime("%Y-%m-%d")
        with open(changelog_path, "a", encoding="utf-8") as f:
            f.write(f"\n## {date}\n")
            for entry in output.changelog_entries:
                f.write(f"- {entry}\n")


def docs_node(state: ProjectState) -> dict:
    agent = BaseAgent("documentation.md")
    prompt_ctx = ctx.docs_context(state)

    result: DocumentationOutput = agent.run(
        prompt_ctx, output_model=DocumentationOutput, temperature=state.config.temperature_docs
    )

    _write_docs_to_disk(result)

    msg = AgentMessage(
        sender=SENDER,
        message_type=MessageType.documentation,
        payload=result.model_dump(mode="json"),
    )

    return {
        "documentation": result,
        "final_summary": result.user_summary,
        "project_status": ProjectStatus.complete,
        "messages": state.append_message(msg),
    }
