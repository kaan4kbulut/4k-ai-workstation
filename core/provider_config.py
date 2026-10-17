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
import sys
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


def is_provider_zero_cost_allowed(
    base_url: str,
    model: str,
    cost: float = 0.0,
    is_local: bool = False,
) -> bool:
    """
    Sıfır API Harcaması Kalkanı:
    Maliyeti 0'dan büyük olan veya yerel olmayıp :free taşımayan sağlayıcıları reddeder.
    """
    if cost > 0.0:
        return False
    b = (base_url or "").lower().strip()
    m = (model or "").lower().strip()
    is_local_url = (
        "127.0.0.1" in b
        or "localhost" in b
        or "::1" in b
        or "0.0.0.0" in b
    )
    if is_local or is_local_url:
        return True
    if ":free" in m:
        return True
    return False


def parse_providers(data: dict) -> list[ProviderConfig]:
    """Ham JSON sözlüğünü :class:`ProviderConfig` listesine çevirir.
    Ücretli veya izin verilmeyen bulut sağlayıcıları $0.00 Kalkanı ile otomatik elenir.
    """
    configs: list[ProviderConfig] = []
    for raw in data.get("providers", []):
        base_url = raw.get("base_url", "")
        model = raw.get("model", "")
        cost = float(raw.get("cost", 0.0))
        is_local = bool(raw.get("local", False))

        if not is_provider_zero_cost_allowed(base_url, model, cost, is_local):
            continue

        configs.append(
            ProviderConfig(
                name=raw["name"],
                base_url=base_url,
                model=model,
                api_key=_resolve_api_key(raw),
                timeout=float(raw.get("timeout", 120)),
                capability_score=int(raw.get("capability", 6)),
                cost_per_token=0.0,
                is_local=is_local,
                strengths=tuple(raw.get("strengths", [])),
            )
        )
    return configs


def load_provider_configs(path: str | None = None) -> list[ProviderConfig]:
    """Yapılandırma dosyasını okur. Ücretli modeller Sıfır Harcama Kalkanı ile filtrelenir."""
    path = path or os.environ.get("NEXUS_PROVIDERS") or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        configs = parse_providers(json.load(handle))

    filtered: list[ProviderConfig] = []
    for c in configs:
        if is_provider_zero_cost_allowed(c.base_url, c.model, c.cost_per_token, c.is_local):
            c.cost_per_token = 0.0  # Zorunlu 0.0 TL
            filtered.append(c)
    return filtered


def load_custom_providers(path: str | None = None) -> list[ProviderConfig]:
    """Özel sağlayıcıları yükler (load_provider_configs alias)."""
    return load_provider_configs(path)


def build_wrapper(config: ProviderConfig) -> OpenAICompatibleWrapper:
    """Bir :class:`ProviderConfig`'ten çalışır wrapper üretir."""
    return OpenAICompatibleWrapper(
        name=config.name,
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout=config.timeout,
    )


def upsert_provider_config(entry: dict, path: str | None = None) -> list[ProviderConfig]:
    """Yeni bir sağlayıcıyı config/providers.json dosyasına ekler veya günceller.
    Ücretli sağlayıcılar ($0.00 Kalkanı) tarafından reddedilir.
    """
    cost = float(entry.get("cost", 0.0))
    base_url = entry.get("base_url", "")
    model = entry.get("model", "")
    is_local = bool(entry.get("local", False))

    if not is_provider_zero_cost_allowed(base_url, model, cost, is_local):
        raise ValueError(
            "🔒 SIFIR HARCAMA KİLİDİ: Ücretli sağlayıcı eklenemez ($0.00 Kalkanı). "
            "Yalnızca yerel veya model adında ':free' bulunan 0 TL modeller kabul edilir."
        )

    entry["cost"] = 0.0  # Zorunlu sıfır maliyet

    path = path or os.environ.get("NEXUS_PROVIDERS") or DEFAULT_CONFIG_PATH
    data: dict = {"providers": []}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            data = {"providers": []}

    providers = [p for p in data.get("providers", []) if p.get("name") != entry.get("name")]
    providers.append(entry)
    data["providers"] = providers

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return parse_providers(data)


def delete_provider_config(name: str, path: str | None = None) -> list[ProviderConfig]:
    """Belirtilen sağlayıcıyı config/providers.json dosyasından siler."""
    path = path or os.environ.get("NEXUS_PROVIDERS") or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data["providers"] = [p for p in data.get("providers", []) if p.get("name") != name]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return parse_providers(data)

