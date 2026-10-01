"""Runs one pipeline end to end and prints a JSON summary as the last line
of stdout. bench/run.py spawns this once per task, so every run gets a fresh
process: clean usage counters, and its own AI_TEAM_WORKSPACE and LLM
settings from the environment.

Usage: python -m bench.worker MESSAGES_LOG_PATH < request.txt
"""
import json
import os
import sys
import time


def main():
    log_path = sys.argv[1]
    request = sys.stdin.read()

    # Imported after argv/stdin handling so settings see the env bench/run.py set.
    from config import settings
    from graph.build_graph import build_graph
    from models.llm_client import USAGE, LLMQuotaExhaustedError
    from schemas.state import ProjectState
    from schemas.task import TaskStatus

    app = build_graph(checkpointer=None)
    config = {"configurable": {"thread_id": "bench"}, "recursion_limit": settings.GRAPH_RECURSION_LIMIT}
    state = ProjectState.new(user_request=request)
    error, quota_exhausted = None, False
    start = time.monotonic()
    try:
        # stream() rather than invoke() so a failure mid-run still leaves the
        # last good state to report on.
        for update in app.stream(state, config=config, stream_mode="values"):
            state = ProjectState.model_validate(update)
    except LLMQuotaExhaustedError as e:
        error, quota_exhausted = str(e), True
    except Exception as e:  # noqa: BLE001 — any failure is a data point, not a crash
        error = f"{type(e).__name__}: {e}"
    elapsed = time.monotonic() - start

    with open(log_path, "w", encoding="utf-8") as f:
        for msg in state.messages:
            f.write(json.dumps(msg.model_dump(mode="json")) + "\n")

    # The same run as a replay for the web console: bench/runs/<config>/<task>-r<k>/replay.json
    from utils import replays
    run_dir = os.path.dirname(os.path.abspath(log_path))
    replay_id = f"bench-{os.path.basename(os.path.dirname(run_dir))}-{os.path.basename(run_dir)}"
    if state.messages:
        replays.save_replay(
            replays.replay_from_state(replay_id, state, source="bench", note=f"Ended with an error: {error[:160]}" if error else None),
            directory=run_dir, filename="replay.json",
        )

    types = [m.message_type.value for m in state.messages]
    test_fails = sum(1 for m in state.messages if m.message_type.value == "test_report" and m.payload.get("status") == "fail")
    summary = {
        "project_status": state.project_status.value,
        "tasks_planned": len(state.tasks),
        "tasks_done": sum(t.status == TaskStatus.done for t in state.tasks),
        "tasks_blocked": sum(t.status == TaskStatus.blocked_needs_human for t in state.tasks),
        "qa_rejections": sum(state.review_iterations.values()),
        "testing_failures": test_fails,
        "clarification_rounds": state.clarification_rounds,
        "implementations": types.count("implementation"),
        "llm_calls": USAGE["calls"],
        "schema_retries": USAGE["schema_retries"],
        "prompt_tokens": USAGE["prompt_tokens"],
        "completion_tokens": USAGE["completion_tokens"],
        "seconds": round(elapsed, 1),
        "error": error,
        "quota_exhausted": quota_exhausted,
    }
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
