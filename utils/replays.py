"""Recorded runs, in the format the web console replays.

A replay is one JSON file: run metadata plus the exact AgentMessage list the
pipeline produced. Three places hold them:

- memory/replays/            runs from the web console and main.py (local only)
- bench/runs/**/replay.json   benchmark runs (written by bench/worker.py)
- frontend/public/replays/   runs published with the static site (committed)
"""
import glob
import json
import os
import re
from datetime import datetime, timezone

from config import settings

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_DIR = os.path.join(ROOT, "memory", "replays")
BENCH_GLOB = os.path.join(ROOT, "bench", "runs", "*", "*", "replay.json")
PUBLISHED_DIR = os.path.join(ROOT, "frontend", "public", "replays")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def current_model() -> tuple[str, str]:
    provider = settings.LLM_PROVIDER
    model = settings.GROQ_MODEL_NAME if provider == "groq" else settings.MODEL_NAME
    return provider, model


def build_replay(
    replay_id: str,
    request: str,
    messages: list[dict],
    *,
    source: str,
    provider: str | None = None,
    model: str | None = None,
    final_status: str | None = None,
    tasks_planned: int | None = None,
    tasks_done: int | None = None,
    note: str | None = None,
    hidden_tests: dict | None = None,
) -> dict:
    recorded_at = messages[0].get("timestamp") if messages else None
    return {
        "id": replay_id,
        "request": request,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "source": source,
        "note": note,
        "final_status": final_status,
        "tasks_planned": tasks_planned,
        "tasks_done": tasks_done,
        "message_count": len(messages),
        "hidden_tests": hidden_tests,
        "messages": messages,
    }


def replay_from_state(replay_id: str, state, *, source: str, note: str | None = None) -> dict:
    """Builds a replay from a final ProjectState."""
    provider, model = current_model()
    return build_replay(
        replay_id,
        state.user_request,
        [m.model_dump(mode="json") for m in state.messages],
        source=source,
        provider=provider,
        model=model,
        final_status=state.project_status.value,
        tasks_planned=len(state.tasks),
        tasks_done=sum(t.status.value == "done" for t in state.tasks),
        note=note,
    )


def save_replay(replay: dict, directory: str = LOCAL_DIR, filename: str | None = None) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename or f"{replay['id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(replay, f, ensure_ascii=False)
    return path


def _all_paths() -> list[str]:
    paths = sorted(glob.glob(os.path.join(PUBLISHED_DIR, "*.json")))
    paths += sorted(glob.glob(os.path.join(LOCAL_DIR, "*.json")))
    paths += sorted(glob.glob(BENCH_GLOB))
    return [p for p in paths if os.path.basename(p) != "index.json"]


def _read(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def meta(replay: dict) -> dict:
    return {k: v for k, v in replay.items() if k != "messages"}


def list_replays() -> list[dict]:
    seen: dict[str, dict] = {}
    for path in _all_paths():
        replay = _read(path)
        if replay and replay.get("id") and replay["id"] not in seen:
            seen[replay["id"]] = meta(replay)
    return sorted(seen.values(), key=lambda r: r.get("recorded_at") or "", reverse=True)


def load_replay(replay_id: str) -> dict | None:
    if not _SAFE_ID.match(replay_id):
        return None
    for path in _all_paths():
        replay = _read(path)
        if replay and replay.get("id") == replay_id:
            return replay
    return None
