"""Ollama wrapper.

Talks to a local Ollama server over its HTTP API instead of shelling out to
`ollama run`, which used to block (and silently start a multi-GB model pull)
whenever the requested model was not installed.

Configuration (environment variables):
    OLLAMA_HOST         Base URL of the Ollama server. Default: http://127.0.0.1:11434
    OLLAMA_MODEL        Default model name. Default: llama3
    OLLAMA_TIMEOUT      Per-request timeout in seconds. Default: 120
"""

import os

import httpx

from .base_wrapper import BaseWrapper


class OllamaQueryError(RuntimeError):
    """Raised when the Ollama server cannot answer a request."""


class OllamaWrapper(BaseWrapper):
    def __init__(self, model_name: str | None = None):
        super().__init__("Ollama")
        self.host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model_name = model_name or os.environ.get("OLLAMA_MODEL", "llama3")
        self.timeout = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

    async def list_models(self) -> list[str]:
        """Return the names of the models installed on the Ollama server."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.host}/api/tags")
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]

    async def execute(self, prompt: str) -> str:
        payload = {"model": self.model_name, "prompt": prompt, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.host}/api/generate", json=payload)
        except httpx.ConnectError as exc:
            return f"Error: Ollama sunucusuna ulaşılamadı ({self.host}). Ollama çalışıyor mu? ({exc})"
        except httpx.TimeoutException:
            return f"Error: Ollama {self.timeout:.0f} saniyede yanıt vermedi (model: {self.model_name})."

        if response.status_code == 404:
            return (
                f"Error: '{self.model_name}' modeli kurulu değil. "
                f"Kurmak için: ollama pull {self.model_name}"
            )
        if response.status_code >= 400:
            return f"Error: Ollama HTTP {response.status_code}: {response.text[:200]}"

        return response.json().get("response", "").strip()

    async def check_quota(self) -> float:
        # Local models have unlimited quota.
        return 1.0
