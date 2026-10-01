"""Local-only backend: serves the dashboard and streams real pipeline runs
over Server-Sent Events.

SAFETY: binds to 127.0.0.1 only (see __main__) — never expose this on 0.0.0.0
or the public internet. The Testing Agent executes generated code as a real
subprocess; that's a reasonable risk to accept on your own machine and a bad
one to accept from strangers on the internet.

Usage:
    pip install fastapi uvicorn
    python api.py
    # then open http://127.0.0.1:8000
"""
import io
import json
import os
import re
import uuid
import zipfile

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from graph.build_graph import build_graph
from schemas.state import ProjectState
from tools.filesystem import resolve_in_workspace

app = FastAPI(title="AI Dev Team API")

DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")

# Serves the actual files the pipeline writes (same directory swe_node and
# docs_node write to) at real URLs, e.g. /workspace/cli.py — so the dashboard
# can link to the real generated files instead of only holding JS-side
# copies of what streamed over SSE.
WORKSPACE_DIR = settings.workspace_dir()
os.makedirs(WORKSPACE_DIR, exist_ok=True)
app.mount("/workspace", StaticFiles(directory=WORKSPACE_DIR), name="workspace")


@app.get("/")
def dashboard():
    return FileResponse(DASHBOARD_PATH)


_UNSAFE_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_.-]+")


@app.get("/download.zip")
def download_workspace_zip(
    files: list[str] = Query(default=[]),
    name: str = Query(default="workspace"),
):
    """Bundles exactly the given files (the dashboard passes the file list
    for the run just completed) into a zip — not everything that has ever
    accumulated in the workspace across past runs, since nothing clears that
    directory between runs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel_path in files:
            # Skips anything that escapes the workspace ("../", absolute paths).
            full_path = resolve_in_workspace(WORKSPACE_DIR, rel_path)
            if full_path and os.path.isfile(full_path):
                zf.write(full_path, rel_path)
    buf.seek(0)

    safe_name = _UNSAFE_NAME_CHARS.sub("-", name).strip("-.") or "workspace"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@app.get("/runs")
def start_run(request: str = Query(..., min_length=1)):
    """Streams one pipeline run as Server-Sent Events. Each AgentMessage the
    real graph produces becomes one `type: "message"` event (same payload
    shape as the Pydantic schema that produced it — ProjectPlan,
    ImplementationSummary, TestReport, ReviewReport, DocumentationOutput),
    interleaved with `type: "state"` snapshots of the task list so the
    frontend never has to guess at status."""

    def event_stream():
        graph = build_graph(checkpointer=None)
        initial_state = ProjectState.new(user_request=request)
        config = {
            "configurable": {"thread_id": str(uuid.uuid4())},
            "recursion_limit": 100,
        }

        seen = 0
        final_state = None
        try:
            for update in graph.stream(initial_state, config=config, stream_mode="values"):
                state = ProjectState.model_validate(update)
                final_state = state

                for msg in state.messages[seen:]:
                    yield _sse({
                        "type": "message",
                        "sender": msg.sender,
                        "message_type": msg.message_type.value,
                        "payload": msg.payload,
                    })
                seen = len(state.messages)

                yield _sse({
                    "type": "state",
                    "project_status": state.project_status.value,
                    "current_task_id": state.current_task_id,
                    "tasks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "status": t.status.value,
                            "acceptance_criteria": [
                                {"id": c.id, "description": c.description} for c in t.acceptance_criteria
                            ],
                        }
                        for t in state.tasks
                    ],
                })
        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        yield _sse({
            "type": "done",
            "project_status": final_state.project_status.value if final_state else None,
            "final_summary": final_state.final_summary if final_state else None,
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
