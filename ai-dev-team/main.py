"""Entry point.

Usage:
    python main.py "Build a CLI tool that converts CSV files to JSON."

Requires a local Ollama server running the configured model, e.g.:
    ollama pull qwen3:8b
    ollama serve
"""
import os
import sys
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver

from config import settings
from graph.build_graph import build_graph
from schemas.state import ProjectState
from utils.logging import log_all


def run(user_request: str, thread_id: str | None = None) -> ProjectState:
    thread_id = thread_id or str(uuid.uuid4())
    os.makedirs(os.path.dirname(settings.MEMORY_DB_PATH), exist_ok=True)

    with SqliteSaver.from_conn_string(settings.MEMORY_DB_PATH) as checkpointer:
        app = build_graph(checkpointer=checkpointer)
        initial_state = ProjectState.new(user_request=user_request)
        config = {"configurable": {"thread_id": thread_id}}
        result = app.invoke(initial_state, config=config)
        final_state = ProjectState.model_validate(result)

    log_all(thread_id, final_state.messages)
    return final_state


def _print_summary(state: ProjectState) -> None:
    print("\n" + "=" * 60)
    print(f"Project status: {state.project_status.value}")
    print("=" * 60)
    for task in state.tasks:
        print(f"  [{task.status.value:>20}] {task.id}: {task.title}")
    if state.final_summary:
        print("\n--- Summary ---")
        print(state.final_summary)
    print(f"\nWorkspace: {os.environ.get('AI_TEAM_WORKSPACE', os.path.join(os.getcwd(), 'workspace'))}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python main.py "<your project request>"')
        sys.exit(1)

    request = " ".join(sys.argv[1:])
    final_state = run(request)
    _print_summary(final_state)
