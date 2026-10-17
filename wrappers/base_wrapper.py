from abc import ABC, abstractmethod

class BaseWrapper(ABC):
    """
    Tüm CLI araç wrapper'ları için temel sınıf.
    Yeni bir araç (Claude Code, Ollama vb.) bu sınıftan türetilmelidir.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, prompt: str) -> str:
        """Aracı çalıştırır ve çıktıyı döndürür."""
        pass

    @abstractmethod
    async def check_quota(self) -> float:
        """Kalan kotayı döndürür (0.0 ile 1.0 arası)."""
        pass