"""The provider-independent parts of the LLM layer: schema-validated retries,
usage counting, and Groq's rate-limit handling — with the network mocked."""
import pytest
import requests
from pydantic import BaseModel

from models import groq_client
from models.groq_client import GroqClient
from models.llm_client import USAGE, LLMClient, LLMQuotaExhaustedError, LLMSchemaError


class Answer(BaseModel):
    value: int


class ScriptedClient(LLMClient):
    def __init__(self, replies):
        super().__init__()
        self.replies = list(replies)
        self.prompts = []

    def call(self, system_prompt, user_prompt, temperature=0.2, max_retries=3):
        self.prompts.append(user_prompt)
        return self.replies.pop(0)


def test_invalid_output_is_reprompted_with_the_error_and_counted():
    USAGE.clear()
    client = ScriptedClient(["not json", '{"value": "nope"}', '{"value": 7}'])
    assert client.call_structured("sys", "question", Answer).value == 7
    assert "CORRECTION REQUIRED" in client.prompts[1]
    assert USAGE["calls"] == 3
    assert USAGE["schema_retries"] == 2


def test_gives_up_after_the_schema_retry_cap():
    client = ScriptedClient(["{}"] * 10)
    with pytest.raises(LLMSchemaError):
        client.call_structured("sys", "q", Answer, max_schema_retries=2)
    assert len(client.prompts) == 3


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._body


def _ok(content):
    return FakeResponse(200, {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    })


def test_groq_waits_out_a_short_rate_limit_and_counts_tokens(monkeypatch):
    USAGE.clear()
    responses = [FakeResponse(429, headers={"Retry-After": "2"}), _ok('{"value": 1}')]
    sleeps = []
    monkeypatch.setattr(groq_client.requests, "post", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(groq_client.time, "sleep", sleeps.append)

    assert GroqClient(api_key="k").call("s", "u") == '{"value": 1}'
    assert sleeps == [2.0]
    assert USAGE["prompt_tokens"] == 100 and USAGE["completion_tokens"] == 20


def test_groq_fails_fast_when_the_quota_resets_hours_from_now(monkeypatch):
    monkeypatch.setattr(groq_client.requests, "post",
                        lambda *a, **k: FakeResponse(429, headers={"Retry-After": "5400"}))
    monkeypatch.setattr(groq_client.time, "sleep", lambda s: pytest.fail(f"slept {s}s"))
    with pytest.raises(LLMQuotaExhaustedError):
        GroqClient(api_key="k").call("s", "u")
