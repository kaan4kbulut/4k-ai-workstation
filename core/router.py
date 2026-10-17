from typing import Dict, List, Iterable
from dataclasses import dataclass, field
from core.quota_manager import QuotaManager


STRENGTH_KEYWORDS: Dict[str, List[str]] = {
    "search": ["search", "latest", "news", "current", "today", "güncel", "haber", "arama", "bugün", "araştır"],
    "reasoning": ["architecture", "optimize", "security", "design", "plan", "complex", "mimari", "güvenlik", "tasarım", "analiz"],
    "code": ["code", "bug", "fix", "function", "refactor", "implement", "compile", "kod", "hata", "fonksiyon", "derle", "düzelt"],
    "agentic": ["build", "create", "deploy", "automate", "project", "uygulama", "oluştur", "kurulum", "otomatik"],
}


@dataclass
class ModelTier:
    name: str
    capability_score: int
    cost_per_token: float
    is_local: bool
    strengths: frozenset[str] = field(default_factory=frozenset)


class IntelligentRouter:
    def __init__(self, quota_manager: QuotaManager | None = None):
        self.quota_manager = quota_manager or QuotaManager()
        self.tiers: Dict[str, ModelTier] = {
            "Ollama": ModelTier("Ollama", 5, 0.0, True, frozenset({"chat", "cheap", "local", "general"})),
            "Hermes": ModelTier("Hermes", 8, 0.02, False, frozenset({"code", "agentic"})),
            "Codex": ModelTier("Codex", 7, 0.01, False, frozenset({"code", "agentic"})),
            "Claude": ModelTier("Claude", 10, 0.05, False, frozenset({"code", "chat", "reasoning"})),
        }

    def register_tier(
        self,
        name: str,
        capability_score: int,
        cost_per_token: float = 0.0,
        is_local: bool = False,
        strengths: Iterable[str] = (),
    ) -> None:
        """Yeni bir sağlayıcıyı yönlendirme tablosuna ekler."""
        self.tiers[name] = ModelTier(
            name, capability_score, cost_per_token, is_local, frozenset(strengths)
        )

    async def triage_task(self, prompt: str) -> int:
        """İsteğin karmaşıklığını 1-10 arasında puanlar."""
        prompt_lower = prompt.lower()
        if any(
            word in prompt_lower
            for word in [
                "architecture",
                "complex",
                "optimize",
                "rewrite",
                "security",
                "mimari",
                "karmaşık",
                "güvenlik",
                "ölçeklenebilir",
            ]
        ):
            return 9
        if any(
            word in prompt_lower
            for word in ["fix", "bug", "function", "code", "kod", "fonksiyon", "hata", "düzelt", "refactor"]
        ):
            return 6
        return 3

    async def classify_task(self, prompt: str) -> set[str]:
        """İsteğin gerektirdiği yetenek etiketlerini tahmin eder (ör. {"code"})."""
        prompt_lower = prompt.lower()
        tags = {
            tag
            for tag, words in STRENGTH_KEYWORDS.items()
            if any(word in prompt_lower for word in words)
        }
        return tags or {"chat"}

    async def rank_escalation_chain(
        self, prompt: str, available_names: Iterable[str] | None = None
    ) -> List[str]:
        """Görev için en uygun ilk modelden başlayarak hata durumunda yükseltilecek (escalation) model zincirini döndürür."""
        complexity = await self.triage_task(prompt)
        task_tags = await self.classify_task(prompt)
        allowed = set(self.tiers) if available_names is None else set(available_names)

        eligible_models = [
            name
            for name, tier in self.tiers.items()
            if name in allowed
            and tier.capability_score >= complexity
            and self.quota_manager.has_quota(name)
        ]

        preferred = [name for name in eligible_models if self.tiers[name].strengths & task_tags]
        primary_pool = preferred or eligible_models

        ordered_primary = sorted(
            primary_pool,
            key=lambda x: (self.tiers[x].cost_per_token, -self.tiers[x].capability_score),
        )

        # Eskalasyon yedeği olarak diğer tüm kotası uygun bağlı modelleri yetenek sırasıyla ekle
        remaining = [
            name
            for name in self.tiers
            if name in allowed
            and name not in ordered_primary
            and self.quota_manager.has_quota(name)
        ]
        ordered_remaining = sorted(
            remaining,
            key=lambda x: (-self.tiers[x].capability_score, self.tiers[x].cost_per_token),
        )

        chain = ordered_primary + ordered_remaining
        return chain if chain else ["Ollama"]

    async def select_best_model(
        self, prompt: str, available_names: Iterable[str] | None = None
    ) -> str:
        """Göreve uygun, yeterince yetenekli ve kotası kalan en ucuz modeli seçer."""
        chain = await self.rank_escalation_chain(prompt, available_names)
        return chain[0]
