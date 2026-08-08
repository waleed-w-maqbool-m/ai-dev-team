"""Shared agent lifecycle: slice (done by caller) -> render -> invoke -> validate -> commit.

Every concrete agent is a thin subclass (or just a function) that supplies a
prompt file, an output schema, and a temperature. This file implements the
parts that would otherwise be duplicated four times.
"""
import os
from typing import TypeVar

from pydantic import BaseModel

from config import settings
from models.factory import get_client
from models.llm_client import LLMClient

T = TypeVar("T", bound=BaseModel)


def load_prompt(filename: str) -> str:
    path = os.path.join(settings.PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def schema_instruction(output_model: type[BaseModel]) -> str:
    """Renders the target Pydantic schema as a JSON-schema block appended to
    the user prompt. Repeating the schema in the user turn (not just the
    system prompt) measurably improves small-model JSON conformance."""
    schema = output_model.model_json_schema()
    return (
        "\n\n--- REQUIRED OUTPUT SCHEMA (JSON) ---\n"
        f"{schema}\n"
        "Respond with a single JSON object matching this schema exactly. "
        "No markdown, no prose, no code fences — JSON only."
    )


class BaseAgent:
    """Not meant to be used polymorphically across agents with different
    output types at the type level — kept intentionally simple. Each concrete
    agent module composes these pieces directly in its node function."""

    def __init__(self, prompt_file: str, client: LLMClient | None = None):
        self.system_prompt = load_prompt(prompt_file)
        self.client = client or get_client()

    def run(
        self,
        context: str,
        output_model: type[T],
        temperature: float = 0.2,
    ) -> T:
        user_prompt = context + schema_instruction(output_model)
        return self.client.call_structured(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            output_model=output_model,
            temperature=temperature,
        )
