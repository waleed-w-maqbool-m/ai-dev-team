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
import json
import os
import uuid

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse

from graph.build_graph import build_graph
from schemas.state import ProjectState

app = FastAPI(title="AI Dev Team API")

DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard", "index.html")


@app.get("/")
def dashboard():
    return FileResponse(DASHBOARD_PATH)


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
