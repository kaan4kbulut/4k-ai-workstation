"""Sağlayıcı yapılandırmasını dosyadan yükler.

``config/providers.json`` (veya ``NEXUS_PROVIDERS`` ortam değişkeniyle
belirtilen yol) OpenAI uyumlu sağlayıcıları tanımlar. Kod yazmadan yeni bir
servis eklemek için bu dosya yeterlidir.

Örnek (``config/providers.example.json``):

    {
      "providers": [
        {
          "name": "OpenRouter",
          "base_url": "https://openrouter.ai/api/v1",
          "model": "openai/gpt-4o-mini",
          "api_key_env": "OPENROUTER_API_KEY",
          "capability": 9,
          "cost": 0.02,
          "strengths": ["chat", "reasoning"]
        }
      ]
    }

API anahtarı güvenlik için dosyada tutulmak zorunda değildir; ``api_key_env``
alanı bir ortam değişkeninin adını verir.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from wrappers.openai_compatible_wrapper import OpenAICompatibleWrapper

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "providers.json")


@dataclass
class ProviderConfig:
    """Tek bir sağlayıcının tanımı."""

    name: str
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 120.0
    capability_score: int = 6
    cost_per_token: float = 0.0
    is_local: bool = False
    strengths: tuple[str, ...] = ()


def _resolve_api_key(raw: dict) -> str | None:
    if raw.get("api_key"):
        return raw["api_key"]
    env_name = raw.get("api_key_env")
    if env_name:
        return os.environ.get(env_name)
    return None


def parse_providers(data: dict) -> list[ProviderConfig]:
    """Ham JSON sözlüğünü :class:`ProviderConfig` listesine çevirir."""
    configs: list[ProviderConfig] = []
    for raw in data.get("providers", []):
        configs.append(
            ProviderConfig(
                name=raw["name"],
                base_url=raw["base_url"],
                model=raw["model"],
                api_key=_resolve_api_key(raw),
                timeout=float(raw.get("timeout", 120)),
                capability_score=int(raw.get("capability", 6)),
                cost_per_token=float(raw.get("cost", 0.0)),
                is_local=bool(raw.get("local", False)),
                strengths=tuple(raw.get("strengths", [])),
            )
        )
    return configs


def load_provider_configs(path: str | None = None) -> list[ProviderConfig]:
    """Yapılandırma dosyasını okur. Dosya yoksa boş liste döner."""
    path = path or os.environ.get("NEXUS_PROVIDERS") or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return parse_providers(json.load(handle))


def build_wrapper(config: ProviderConfig) -> OpenAICompatibleWrapper:
    """Bir :class:`ProviderConfig`'ten çalışır wrapper üretir."""
    return OpenAICompatibleWrapper(
        name=config.name,
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout=config.timeout,
    )
