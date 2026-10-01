"""Provider-agnostic LLM transport interface.

Every concrete backend (Ollama, Groq, ...) implements `call()` against this
same contract. `call_structured()` — the schema-validate-and-retry loop that
makes a non-frontier model usable in a deterministic pipeline (architecture
doc, Section 4/9) — is implemented once here so it isn't duplicated per
provider.
"""
import json
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from config import settings

T = TypeVar("T", bound=BaseModel)


class LLMTransportError(RuntimeError):
    """Raised when a provider call fails after all transport retries."""


class LLMSchemaError(RuntimeError):
    """Raised when the model's output can't be validated after all schema retries."""


class LLMClient(ABC):
    """One shared model, many roles (architecture doc, Section 1): every agent
    calls the same client instance with a different system prompt, schema,
    and temperature. Swapping providers means swapping which LLMClient
    subclass gets constructed (see models/factory.py) — no agent code
    changes, since every agent only ever talks to this interface."""

    def __init__(self, timeout: int = settings.REQUEST_TIMEOUT_SECONDS):
        self.timeout = timeout

    @abstractmethod
    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = settings.MAX_TRANSPORT_RETRIES,
    ) -> str:
        """Single call to the provider, JSON-mode, with backoff retries on
        transient transport failures. Returns the raw content string."""

    def call_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_model: type[T],
        temperature: float = 0.2,
        max_schema_retries: int = settings.MAX_SCHEMA_RETRIES,
    ) -> T:
        """Calls the model and validates the JSON response against `output_model`.
        On invalid JSON or a Pydantic ValidationError, re-prompts with the error
        appended so the model can self-correct, up to `max_schema_retries` times."""
        prompt = user_prompt
        last_error: Exception | None = None

        for attempt in range(max_schema_retries + 1):
            raw = self.call(system_prompt, prompt, temperature=temperature)
            try:
                parsed = json.loads(raw)
                return output_model.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                prompt = (
                    f"{user_prompt}\n\n"
                    f"--- CORRECTION REQUIRED ---\n"
                    f"Your previous response failed validation with this error:\n{e}\n"
                    f"Return ONLY a single valid JSON object matching the required "
                    f"schema. No markdown, no commentary, no code fences."
                )

        raise LLMSchemaError(
            f"Model output failed schema validation for {output_model.__name__} "
            f"after {max_schema_retries + 1} attempts: {last_error}"
        )
