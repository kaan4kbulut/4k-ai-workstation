"""OpenAI uyumlu HTTP sağlayıcılar için genel wrapper.

OpenAI'nin ``/chat/completions`` şemasını konuşan **her** servis bu tek sınıfla
bağlanır. Yani OpenRouter, HuggingFace Router, Perplexity, OpenAI, Groq ve hatta
yerel Ollama'nın ``/v1`` ucu aynı kodu kullanır:

    POST {base_url}/chat/completions
    Authorization: Bearer <api_key>        (anahtar varsa)
    {"model": "<model>", "messages": [{"role": "user", "content": "<prompt>"}]}

Yanıt: ``choices[0].message.content``.

Yapılandırma kod yazmadan, ``config/providers.json`` üzerinden yapılır
(bkz. ``core/provider_config.py`` ve ``config/providers.example.json``). API
anahtarı dosyada tutulmak zorunda değildir; ``api_key_env`` ile bir ortam
değişkeninin adı verilebilir.

Not: Bu wrapper sağlayıcının kendi faturalandırmasını modellemez
(``check_quota`` her zaman 1.0 döner); gerçek limit o servisin sorumluluğundadır.
"""

from __future__ import annotations

import httpx

from .base_wrapper import BaseWrapper


class OpenAICompatibleWrapper(BaseWrapper):
    """OpenAI uyumlu bir uç noktayı tek biçimde çağıran wrapper."""

    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        super().__init__(name)
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.api_key = api_key
        self.timeout = timeout
        # Testlerde sahte bir taşıma (MockTransport) enjekte etmek için.
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def execute(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.ConnectError as exc:
            return f"Hata: {self.name} sunucusuna ulaşılamadı ({self.base_url}). {exc}"
        except httpx.TimeoutException:
            return (
                f"Hata: {self.name} {self.timeout:.0f} saniyede yanıt vermedi "
                f"(model: {self.model_name})."
            )

        if response.status_code == 401:
            return f"Hata: {self.name} kimlik doğrulama başarısız (401). API anahtarını kontrol et."
        if response.status_code == 404:
            return f"Hata: '{self.model_name}' modeli {self.name} üzerinde bulunamadı."
        if response.status_code >= 400:
            return f"Hata: {self.name} HTTP {response.status_code}: {response.text[:200]}"

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError):
            return f"Hata: {self.name} beklenmeyen yanıt biçimi: {response.text[:200]}"

        if content is None:
            return f"Hata: {self.name} boş içerik döndürdü (model: {self.model_name})."
        return content

    async def check_quota(self) -> float:
        # Sağlayıcının faturalandırmasını geçit modellemez.
        return 1.0
