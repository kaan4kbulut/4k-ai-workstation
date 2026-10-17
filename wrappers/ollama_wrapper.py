"""Ollama wrapper'ı.

Yerel Ollama sunucusuyla, `ollama run` komutunu kabuktan çağırmak yerine HTTP
API'si üzerinden konuşur. Eski yöntem, istenen model kurulu değilse donuyor ve
sessizce çok GB'lık bir model indirmesi başlatıyordu.

Yapılandırma (ortam değişkenleri):
    OLLAMA_HOST         Ollama sunucu adresi. Varsayılan: http://127.0.0.1:11434
    OLLAMA_MODEL        Varsayılan model adı. Varsayılan: llama3
    OLLAMA_TIMEOUT      İstek başına zaman aşımı (saniye). Varsayılan: 120
"""

import os

import httpx

from .base_wrapper import BaseWrapper


class OllamaQueryError(RuntimeError):
    """Ollama sunucusu bir isteği yanıtlayamadığında fırlatılır."""


class OllamaWrapper(BaseWrapper):
    def __init__(self, model_name: str | None = None):
        super().__init__("Ollama")
        self.host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model_name = model_name or os.environ.get("OLLAMA_MODEL", "llama3")
        self.timeout = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

    async def list_models(self) -> list[str]:
        """Ollama sunucusunda kurulu modellerin adlarını döndürür."""
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
            return f"Hata: Ollama sunucusuna ulaşılamadı ({self.host}). Ollama çalışıyor mu? ({exc})"
        except httpx.TimeoutException:
            return f"Hata: Ollama {self.timeout:.0f} saniyede yanıt vermedi (model: {self.model_name})."

        if response.status_code == 404:
            return (
                f"Hata: '{self.model_name}' modeli kurulu değil. "
                f"Kurmak için: ollama pull {self.model_name}"
            )
        if response.status_code >= 400:
            return f"Hata: Ollama HTTP {response.status_code}: {response.text[:200]}"

        return response.json().get("response", "").strip()

    async def check_quota(self) -> float:
        # Yerel modellerin kotası sınırsızdır.
        return 1.0
