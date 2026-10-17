from abc import ABC, abstractmethod

class BaseWrapper(ABC):
    """
    Base class for all CLI tool wrappers.
    Every new tool (Claude Code, Ollama, etc.) must inherit from this.
    """
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, prompt: str) -> str:
        """Execute the tool and return the output."""
        pass

    @abstractmethod
    async def check_quota(self) -> float:
        """Check remaining quota (0.0 to 1.0)."""
        pass