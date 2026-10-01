"""Ollama backend: calls a local Ollama server's /api/chat endpoint.

One of possibly several LLMClient implementations (see models/factory.py) —
this file only knows how to talk to Ollama; the schema-validate-and-retry
loop it inherits from LLMClient is shared with every other backend.
"""
import json
import time

import requests

from config import settings
from models.llm_client import USAGE, LLMClient, LLMTransportError


class OllamaClient(LLMClient):
    def __init__(
        self,
        model: str = settings.MODEL_NAME,
        base_url: str = settings.OLLAMA_CHAT_ENDPOINT,
        timeout: int = settings.REQUEST_TIMEOUT_SECONDS,
    ):
        super().__init__(timeout=timeout)
        self.model = model
        self.base_url = base_url

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = settings.MAX_TRANSPORT_RETRIES,
    ) -> str:
        """Single raw call to Ollama's /api/chat, JSON-mode, with backoff retries
        on transient transport failures. Returns the raw content string."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        }

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(self.base_url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                USAGE["prompt_tokens"] += data.get("prompt_eval_count", 0)
                USAGE["completion_tokens"] += data.get("eval_count", 0)
                return data["message"]["content"]
            except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s...
        raise LLMTransportError(
            f"Ollama call to {self.base_url} failed after {max_retries} attempts: {last_error}"
        )
