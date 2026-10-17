from typing import Dict, List, Iterable
from dataclasses import dataclass, field
from core.quota_manager import QuotaManager


# İsteğin hangi yeteneği gerektirdiğini kabaca tahmin etmek için anahtar
# kelimeler. Prototip düzeyinde sezgiseldir; ileride bir sınıflandırıcı model
# (Librarian) ile değiştirilebilir.
STRENGTH_KEYWORDS: Dict[str, List[str]] = {
    "search": ["search", "latest", "news", "current", "today", "güncel", "haber", "arama", "bugün"],
    "reasoning": ["architecture", "optimize", "security", "design", "plan", "complex", "mimari", "güvenlik", "tasarım"],
    "code": ["code", "bug", "fix", "function", "refactor", "implement", "compile", "kod", "hata", "fonksiyon", "derle"],
    "agentic": ["build", "create", "deploy", "automate", "project", "uygulama", "oluştur", "kurulum", "otomatik"],
}


@dataclass
class ModelTier:
    name: str
    capability_score: int
    cost_per_token: float
    is_local: bool
    # Modelin güçlü olduğu işler: {"chat", "code", "search", "agentic", "cheap", ...}
    strengths: frozenset[str] = field(default_factory=frozenset)


class IntelligentRouter:
    def __init__(self):
        self.quota_manager = QuotaManager()
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
        """Yeni bir sağlayıcıyı yönlendirme tablosuna ekler.

        Bir wrapper kaydedildiğinde çağrılmalıdır; aksi halde router o modeli
        ``auto`` modunda seçemez (yalnızca açıkça ``model=<ad>`` verilirse
        kullanılır).
        """
        self.tiers[name] = ModelTier(
            name, capability_score, cost_per_token, is_local, frozenset(strengths)
        )

    async def triage_task(self, prompt: str) -> int:
        """İsteğin karmaşıklığını 1-10 arasında puanlar."""
        prompt_lower = prompt.lower()
        if any(word in prompt_lower for word in ["architecture", "complex", "optimize", "rewrite", "security"]):
            return 9
        if any(word in prompt_lower for word in ["fix", "bug", "function", "code"]):
            return 6
        return 3

    async def classify_task(self, prompt: str) -> set[str]:
        """İsteğin gerektirdiği yetenek etiketlerini tahmin eder (ör. {"code"}).

        Hiçbiri eşleşmezse genel sohbet kabul edilir: ``{"chat"}``.
        """
        prompt_lower = prompt.lower()
        tags = {
            tag
            for tag, words in STRENGTH_KEYWORDS.items()
            if any(word in prompt_lower for word in words)
        }
        return tags or {"chat"}

    async def select_best_model(
        self, prompt: str, available_names: Iterable[str] | None = None
    ) -> str:
        """Göreve uygun, yeterince yetenekli ve kotası kalan en ucuz modeli seçer.

        `available_names`, seçimi gerçekten kayıtlı wrapper'ı olan modellerle
        sınırlar. Bu verilmezse router, hiçbir wrapper'ın uygulamadığı bir modeli
        seçebilir ve istek dağıtım aşamasında başarısız olur.

        Seçim sırası:
        1. Karmaşıklığı karşılayan + kotası olan + bağlı olan modeller süzülür.
        2. Görev etiketiyle (code/search/...) örtüşen **güçlere** sahip modeller
           öne alınır (ör. kod işi → Claude Code/Hermes).
        3. Kalanlar arasında en ucuz, eşitlikte en yetenekli olan seçilir.
        """
        complexity = await self.triage_task(prompt)
        task_tags = await self.classify_task(prompt)

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

        # Görev etiketiyle örtüşen güçlere sahip modelleri öne al
        preferred = [name for name in eligible_models if self.tiers[name].strengths & task_tags]
        candidates = preferred or eligible_models

        return sorted(
            candidates,
            key=lambda x: (self.tiers[x].cost_per_token, -self.tiers[x].capability_score),
        )[0]
