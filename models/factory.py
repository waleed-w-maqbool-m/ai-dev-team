"""Selects the configured LLM backend. This is the one place that needs to
change to add a new provider — agents/base.py and every agent module depend
only on the LLMClient interface, never on a concrete provider class."""
from config import settings
from models.groq_client import GroqClient
from models.llm_client import LLMClient
from models.ollama_client import OllamaClient

_PROVIDERS = {
    "ollama": OllamaClient,
    "groq": GroqClient,
}


def get_client() -> LLMClient:
    try:
        client_cls = _PROVIDERS[settings.LLM_PROVIDER]
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r} "
            f"(expected one of {list(_PROVIDERS)})"
        ) from None
    return client_cls()
