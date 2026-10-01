"""Groq backend: calls Groq's OpenAI-compatible chat completions endpoint.

Groq hosts open-source models (Llama, Qwen, ...) on its own inference
hardware, free within generous rate limits, so this backend gets the "one
shared model, many roles" pipeline off local hardware entirely without
changing any agent code — every agent still only talks to the LLMClient
interface (models/llm_client.py).
"""
import time

import requests

from config import settings
from models.llm_client import USAGE, LLMClient, LLMQuotaExhaustedError, LLMTransportError


class GroqClient(LLMClient):
    def __init__(
        self,
        model: str = settings.GROQ_MODEL_NAME,
        base_url: str = settings.GROQ_BASE_URL,
        api_key: str = settings.GROQ_API_KEY,
        timeout: int = settings.REQUEST_TIMEOUT_SECONDS,
    ):
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at "
                "https://console.groq.com/keys and set it as an environment "
                "variable before running with LLM_PROVIDER=groq."
            )
        super().__init__(timeout=timeout)
        self.model = model
        self.base_url = base_url
        self.api_key = api_key

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = settings.MAX_TRANSPORT_RETRIES,
    ) -> str:
        """Single raw call to Groq's chat completions endpoint, JSON-mode,
        with backoff retries on transient transport failures. A 429 waits for
        the server-specified Retry-After duration instead of the short
        generic backoff — a rate-limit reset genuinely takes that long, so
        retrying sooner just wastes the attempt. Returns the raw content
        string."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    self.base_url, json=payload, headers=headers, timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage") or {}
                USAGE["prompt_tokens"] += usage.get("prompt_tokens", 0)
                USAGE["completion_tokens"] += usage.get("completion_tokens", 0)
                return data["choices"][0]["message"]["content"]
            except requests.HTTPError as e:
                last_error = e
                delay = self._retry_delay(e.response, attempt)
                if delay > settings.MAX_RATE_LIMIT_WAIT_SECONDS:
                    raise LLMQuotaExhaustedError(
                        f"Groq rate limit for {self.model} resets in {delay:.0f}s "
                        f"(likely a daily quota): {e}"
                    ) from e
                if attempt < max_retries - 1:
                    time.sleep(delay)
            except (requests.RequestException, KeyError, IndexError, ValueError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s...
        raise LLMTransportError(
            f"Groq call to {self.base_url} failed after {max_retries} attempts: {last_error}"
        )

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
            return 15.0  # Groq didn't send a Retry-After header — safe default
        return 2 ** attempt
