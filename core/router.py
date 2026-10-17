import asyncio
from typing import Dict, Any, List, Iterable
from dataclasses import dataclass
from core.quota_manager import QuotaManager

@dataclass
class ModelTier:
    name: str
    capability_score: int
    cost_per_token: float
    is_local: bool

class IntelligentRouter:
    def __init__(self):
        self.quota_manager = QuotaManager()
        self.tiers = {
            "Ollama": ModelTier("Ollama", capability_score=5, cost_per_token=0.0, is_local=True),
            "Hermes": ModelTier("Hermes", capability_score=8, cost_per_token=0.02, is_local=False),
            "Codex": ModelTier("Codex", capability_score=7, cost_per_token=0.01, is_local=False),
            "Claude": ModelTier("Claude", capability_score=10, cost_per_token=0.05, is_local=False),
        }

    async def triage_task(self, prompt: str) -> int:
        prompt_lower = prompt.lower()
        if any(word in prompt_lower for word in ["architecture", "complex", "optimize", "rewrite", "security"]):
            return 9
        if any(word in prompt_lower for word in ["fix", "bug", "function", "code"]):
            return 6
        return 3

    async def select_best_model(self, prompt: str, available_names: Iterable[str] | None = None) -> str:
        """Yeterince yetenekli ve kotası kalan en ucuz modeli seçer.

        `available_names`, seçimi gerçekten kayıtlı wrapper'ı olan modellerle
        sınırlar. Bu verilmezse router, hiçbir wrapper'ın uygulamadığı bir modeli
        seçebilir ve istek dağıtım aşamasında başarısız olur.
        """
        complexity = await self.triage_task(prompt)

        allowed = set(self.tiers) if available_names is None else set(available_names)

        # Karmaşıklığı karşılayan VE kotası olan VE bağlı olan modelleri süz
        eligible_models = [
            name for name, tier in self.tiers.items()
            if name in allowed
            and tier.capability_score >= complexity
            and self.quota_manager.has_quota(name)
        ]

        if not eligible_models:
            # Geri düşme: karmaşıklığa bakmadan kotası olan herhangi bir model
            available_models = [
                name for name in self.tiers
                if name in allowed and self.quota_manager.has_quota(name)
            ]
            if available_models:
                return sorted(available_models, key=lambda x: -self.tiers[x].capability_score)[0]
            return "Ollama"  # Mutlak geri düşme

        sorted_models = sorted(
            eligible_models, 
            key=lambda x: (self.tiers[x].cost_per_token, -self.tiers[x].capability_score)
        )
        
        return sorted_models[0]