"""Local-only backend: serves the web console (frontend/dist), streams real
pipeline runs over Server-Sent Events, and serves recorded runs for replay.

SAFETY: binds to 127.0.0.1 only (see __main__) — never expose this on 0.0.0.0
or the public internet. The Testing Agent executes generated code; that's a
reasonable risk to accept on your own machine and a bad one to accept from
strangers on the internet.

Usage:
    cd frontend && npm install && npm run build && cd ..
    python api.py
    # then open http://127.0.0.1:8000
"""
import io
import json
import os
import re
import uuid
import zipfile

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from graph.build_graph import build_graph
from schemas.state import ProjectState
from tools.filesystem import resolve_in_workspace
from utils import replays

app = FastAPI(title="AI Dev Team API")
# Compresses the console bundle; Starlette never compresses text/event-stream,
# so live-run SSE events still arrive one at a time.
app.add_middleware(GZipMiddleware, minimum_size=1024)

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

# Serves the actual files the pipeline writes (same directory swe_node and
# docs_node write to) at real URLs, e.g. /workspace/cli.py.
WORKSPACE_DIR = settings.workspace_dir()
os.makedirs(WORKSPACE_DIR, exist_ok=True)
app.mount("/workspace", StaticFiles(directory=WORKSPACE_DIR), name="workspace")


@app.get("/api/health")
def health():
    """Whether a live run can actually start: Groq needs a key, Ollama needs
    a reachable server. The console disables "Run live" otherwise."""
    provider, model = replays.current_model()
    if provider == "groq":
        live = bool(settings.GROQ_API_KEY)
    else:
        try:
            live = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=1.5).ok
        except requests.RequestException:
            live = False
    return {"live": live, "provider": provider, "model": model}


@app.get("/api/replays")
def list_replays():
    return replays.list_replays()


@app.get("/api/replays/{replay_id}")
def get_replay(replay_id: str):
    replay = replays.load_replay(replay_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="No such replay")
    return replay


@app.get("/api/benchmark")
def benchmark():
    from bench.report import benchmark_json

    return benchmark_json()


_UNSAFE_NAME_CHARS = re.compile(r"[^a-zA-Z0-9_.-]+")


@app.get("/download.zip")
def download_workspace_zip(
    files: list[str] = Query(default=[]),
    name: str = Query(default="workspace"),
):
    """Bundles exactly the given files (the console passes the file list for
    the run just completed) into a zip — not everything that has ever
    accumulated in the workspace across past runs."""
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
    real graph produces becomes one `type: "message"` event, interleaved with
    `type: "state"` snapshots of the task list so the frontend never has to
    guess at status. The finished run is saved as a replay."""

    def event_stream():
        graph = build_graph(checkpointer=None)
        run_id = str(uuid.uuid4())
        initial_state = ProjectState.new(user_request=request)
        config = {
            "configurable": {"thread_id": run_id},
            "recursion_limit": settings.GRAPH_RECURSION_LIMIT,
        }

        seen = 0
        final_state = None
        error = None
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
                        "timestamp": msg.timestamp.isoformat(),
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
        except Exception as e:  # noqa: BLE001 — reported to the client, run still recorded
            error = str(e)
            yield _sse({"type": "error", "message": error})
        finally:
            if final_state and final_state.messages:
                replays.save_replay(replays.replay_from_state(
                    f"live-{run_id[:8]}", final_state, source="live",
                    note=f"Ended with an error: {error[:160]}" if error else None,
                ))

        if error is None:
            yield _sse({
                "type": "done",
                "project_status": final_state.project_status.value if final_state else None,
                "final_summary": final_state.final_summary if final_state else None,
            })

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- the web console (built frontend). Declared last so API routes win. ---

@app.get("/{full_path:path}", include_in_schema=False)
def console(full_path: str):
    if not os.path.isdir(DIST_DIR):
        return HTMLResponse(
            "<p style='font-family:system-ui;padding:24px'>The web console isn't built yet. "
            "Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>, then reload.</p>",
            status_code=503,
        )
    candidate = os.path.realpath(os.path.join(DIST_DIR, full_path))
    if full_path and candidate.startswith(os.path.realpath(DIST_DIR) + os.sep) and os.path.isfile(candidate):
        # Vite content-hashes everything under assets/, so it can be cached forever.
        immutable = full_path.startswith("assets/")
        return FileResponse(candidate, headers={"Cache-Control": "public, max-age=31536000, immutable"} if immutable else None)
    # Client-side routes (/theater, /library, ...) all load the app shell.
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
