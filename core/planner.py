import asyncio
from typing import List, Dict

class TaskPlanner:
    def __init__(self):
        # Gerçek sürümde burada isteği bölmek için üst seviye bir LLM kullanılır.
        pass

    async def decompose(self, prompt: str) -> List[Dict]:
        """
        Karmaşık bir isteği daha küçük, bağımsız alt görevlere böler.
        """
        print(f"[Planner] Görev bölünüyor: {prompt[:50]}...")

        # Prototip için basitleştirilmiş bölme mantığı:
        # İstek uzunsa veya "ve" içeriyorsa parçala.
        if len(prompt) > 50 or " and " in prompt.lower() or " ve " in prompt.lower():
            return [
                {"id": 1, "task": f"Analiz et ve planla: {prompt}", "complexity": 9, "type": "architecture"},
                {"id": 2, "task": f"Temel mantığı uygula: {prompt}", "complexity": 6, "type": "code"},
                {"id": 3, "task": f"Dokümantasyon oluştur: {prompt}", "complexity": 3, "type": "docs"},
            ]

        return [{"id": 1, "task": prompt, "complexity": 5, "type": "general"}]
