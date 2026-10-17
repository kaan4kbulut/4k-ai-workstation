"""OpenAI uyumlu HTTP sağlayıcılar için wrapper modülü.
`openai_compatible_wrapper.py` için takma ad (alias) ve dışa aktarım sağlar.
"""

from wrappers.openai_compatible_wrapper import (
    OpenAICompatibleWrapper,
    is_zero_cost_allowed,
)

__all__ = ["OpenAICompatibleWrapper", "is_zero_cost_allowed"]
