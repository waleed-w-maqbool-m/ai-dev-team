"""Writes every AgentMessage to a rotating-by-run JSONL log file.

This is deliberately separate from the SQLite checkpointer: the checkpointer
exists for resumability, this exists so a human can `tail -f` or grep a
specific run's decisions after the fact.
"""
import json
import os
from datetime import datetime

from config import settings
from schemas.messages import AgentMessage


def log_message(thread_id: str, message: AgentMessage) -> None:
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_path = os.path.join(settings.LOG_DIR, f"{thread_id}.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message.model_dump(mode="json")) + "\n")


def log_all(thread_id: str, messages: list[AgentMessage]) -> None:
    """Convenience for logging a full state's message history at once
    (e.g. called from main.py after a run completes)."""
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_path = os.path.join(settings.LOG_DIR, f"{thread_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
    with open(log_path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m.model_dump(mode="json")) + "\n")
