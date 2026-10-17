"""Faz 4: Model Kütüphanecisi (Model Librarian) ve Yetenek Matrisi (Capability Matrix).

Bu modül:
1. Güncel açık kaynak (yerel Ollama), bulut ve CLI ajan modellerini
   kategorilere göre (Kodlama, Akıl Yürütme, Sohbet, Hız, Maliyet Verimliliği)
   1-10 ölçeğinde puanlar.
2. Yerel Ollama sunucusunu (`/api/tags`) sorgulayarak bilgisayarda halihazırda
   indirili olan modelleri tespit eder ve katalogla eşleştirir.
3. Görev tipine ve donanım sınırlarına (VRAM / RAM) göre en uygun modelleri
   sıralar ve `data/model_catalog.json` dosyasında günceller.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import List

import httpx


@dataclass
class ModelScoreCard:
    """Bir modelin yetenek matrisi ve donanım gereksinimi kartı."""

    id: str
    provider: str  # "Ollama" | "CLI" | "OpenRouter" | "Cloud"
    is_free_or_local: bool
    min_vram_gb: float
    min_ram_gb: float
    coding: int
    reasoning: int
    chat: int
    speed: int
    cost_efficiency: int
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    installed_locally: bool = False

    def composite_score(self, task_type: str = "general") -> float:
        """Görev tipine göre ağırlıklı toplam puan (0-10) hesaplar."""
        t = task_type.lower()
        if t in ("code", "coding", "kod", "kodlama"):
            return round(self.coding * 0.55 + self.reasoning * 0.25 + self.speed * 0.1 + self.cost_efficiency * 0.1, 2)
        if t in ("reasoning", "architecture", "mimari", "analiz"):
            return round(self.reasoning * 0.60 + self.coding * 0.25 + self.cost_efficiency * 0.15, 2)
        if t in ("chat", "sohbet", "docs"):
            return round(self.chat * 0.50 + self.speed * 0.25 + self.cost_efficiency * 0.25, 2)
        if t in ("fast", "cheap", "ucuz", "hızlı"):
            return round(self.cost_efficiency * 0.50 + self.speed * 0.35 + self.chat * 0.15, 2)
        return round(
            (self.coding + self.reasoning + self.chat + self.speed + self.cost_efficiency) / 5.0,
            2,
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["overall_score"] = self.composite_score("general")
        return data


DEFAULT_CATALOG: list[ModelScoreCard] = [
    ModelScoreCard(
        id="qwen2.5-coder:14b",
        provider="Ollama",
        is_free_or_local=True,
        min_vram_gb=10.0,
        min_ram_gb=16.0,
        coding=9,
        reasoning=8,
        chat=8,
        speed=8,
        cost_efficiency=10,
        tags=["code", "local", "cheap"],
        notes="12 GB VRAM'li GPU'lar (örn. RTX 5070 Ti) için en güçlü yerel kodlama modeli",
    ),
    ModelScoreCard(
        id="deepseek-r1:14b",
        provider="Ollama",
        is_free_or_local=True,
        min_vram_gb=10.0,
        min_ram_gb=16.0,
        coding=8,
        reasoning=9,
        chat=7,
        speed=7,
        cost_efficiency=10,
        tags=["reasoning", "code", "local", "cheap"],
        notes="Yerel derin akıl yürütme (Chain-of-Thought) ve algoritma analizi",
    ),
    ModelScoreCard(
        id="llama3.1:8b",
        provider="Ollama",
        is_free_or_local=True,
        min_vram_gb=6.0,
        min_ram_gb=12.0,
        coding=7,
        reasoning=7,
        chat=8,
        speed=9,
        cost_efficiency=10,
        tags=["chat", "local", "cheap"],
        notes="Hızlı, genel amaçlı yerel sohbet ve özetleme modeli",
    ),
    ModelScoreCard(
        id="llama3:latest",
        provider="Ollama",
        is_free_or_local=True,
        min_vram_gb=5.0,
        min_ram_gb=8.0,
        coding=7,
        reasoning=7,
        chat=8,
        speed=9,
        cost_efficiency=10,
        tags=["chat", "local", "cheap"],
        notes="Standart Llama 3 8B yerel model",
    ),
    ModelScoreCard(
        id="gemma2:9b",
        provider="Ollama",
        is_free_or_local=True,
        min_vram_gb=7.0,
        min_ram_gb=12.0,
        coding=7,
        reasoning=8,
        chat=9,
        speed=8,
        cost_efficiency=10,
        tags=["chat", "reasoning", "local"],
        notes="Doğal dil kalitesi ve Türkçe/İngilizce sohbet başarımı yüksek",
    ),
    ModelScoreCard(
        id="claude-code-cli",
        provider="CLI (Claude)",
        is_free_or_local=False,
        min_vram_gb=0.0,
        min_ram_gb=2.0,
        coding=10,
        reasoning=10,
        chat=9,
        speed=7,
        cost_efficiency=6,
        tags=["code", "reasoning", "agentic"],
        notes="Karmaşık mimari, çoklu dosya refaktör ve kritik hata ayıklama",
    ),
    ModelScoreCard(
        id="codex-cli",
        provider="CLI (Codex)",
        is_free_or_local=False,
        min_vram_gb=0.0,
        min_ram_gb=2.0,
        coding=9,
        reasoning=9,
        chat=8,
        speed=8,
        cost_efficiency=8,
        tags=["code", "agentic"],
        notes="ChatGPT aboneliğiyle çalışan hızlı kod inceleme ve uygulama ajanı",
    ),
    ModelScoreCard(
        id="hermes-cli",
        provider="CLI (Hermes)",
        is_free_or_local=True,
        min_vram_gb=0.0,
        min_ram_gb=2.0,
        coding=8,
        reasoning=8,
        chat=8,
        speed=8,
        cost_efficiency=9,
        tags=["code", "agentic"],
        notes="Çok adımlı araç çağıran otonom ajan",
    ),
    ModelScoreCard(
        id="opencode-cli",
        provider="CLI (OpenCode)",
        is_free_or_local=True,
        min_vram_gb=0.0,
        min_ram_gb=2.0,
        coding=8,
        reasoning=8,
        chat=8,
        speed=8,
        cost_efficiency=9,
        tags=["code", "agentic", "chat"],
        notes="Çoklu sağlayıcı destekli yerel CLI kodlama ajanı",
    ),
]


class ModelLibrarian:
    """Modelleri keşfeder, puanlar ve görev tipine göre en iyilerini önerir."""

    def __init__(
        self,
        catalog_file: str = "data/model_catalog.json",
        ollama_host: str | None = None,
    ):
        self.catalog_file = catalog_file
        self.ollama_host = (
            ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
        ).rstrip("/")
        self.catalog: list[ModelScoreCard] = [
            ModelScoreCard(**asdict(card)) for card in DEFAULT_CATALOG
        ]

    async def fetch_installed_ollama_models(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> list[str]:
        """Yerel Ollama sunucusunda indirili olan model adlarını döndürür."""
        try:
            async with httpx.AsyncClient(timeout=2.5, transport=transport) as client:
                res = await client.get(f"{self.ollama_host}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    async def refresh_catalog(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> list[ModelScoreCard]:
        """Yerel Ollama modellerini tarar, kataloğu günceller ve diske kaydeder."""
        installed = await self.fetch_installed_ollama_models(transport=transport)
        installed_set = set(installed)

        known_ids = {card.id for card in self.catalog}
        for card in self.catalog:
            card.installed_locally = (
                card.id in installed_set
                or card.id.split(":")[0] in {m.split(":")[0] for m in installed_set}
            )

        # Katalogda olmayan ama Ollama'da kurulu olan modelleri de ekle
        for model_name in installed:
            if model_name not in known_ids:
                self.catalog.append(
                    ModelScoreCard(
                        id=model_name,
                        provider="Ollama",
                        is_free_or_local=True,
                        min_vram_gb=4.0,
                        min_ram_gb=8.0,
                        coding=7,
                        reasoning=7,
                        chat=8,
                        speed=8,
                        cost_efficiency=10,
                        tags=["chat", "local", "cheap"],
                        notes="Yerel Ollama üzerinde kurulu model",
                        installed_locally=True,
                    )
                )

        self.save_catalog()
        return self.catalog

    def save_catalog(self) -> None:
        os.makedirs(os.path.dirname(self.catalog_file) or ".", exist_ok=True)
        payload = [card.to_dict() for card in self.catalog]
        with open(self.catalog_file, "w", encoding="utf-8") as f:
            json.dump({"models": payload}, f, indent=2, ensure_ascii=False)

    def rank_models_for_task(
        self,
        task_type: str = "general",
        max_vram_gb: float | None = None,
        only_free_or_local: bool = False,
    ) -> list[dict]:
        """Verilen görev tipi ve donanım sınırına göre modelleri en yüksek puandan sıralar."""
        candidates = []
        for card in self.catalog:
            if only_free_or_local and not card.is_free_or_local:
                continue
            if max_vram_gb is not None and card.min_vram_gb > max_vram_gb:
                continue
            entry = card.to_dict()
            entry["task_score"] = card.composite_score(task_type)
            candidates.append(entry)

        return sorted(
            candidates,
            key=lambda x: (-x["task_score"], -int(x["installed_locally"]), -x["cost_efficiency"]),
        )
