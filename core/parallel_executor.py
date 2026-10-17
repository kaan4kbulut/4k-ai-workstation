import asyncio
from typing import Dict, List

from core.dispatcher import Dispatcher
from core.router import IntelligentRouter


class ParallelExecutor:
    def __init__(self, dispatcher: Dispatcher, router: IntelligentRouter):
        self.dispatcher = dispatcher
        self.router = router

    async def run_parallel(self, sub_tasks: List[Dict]) -> Dict[int, Dict[str, str]]:
        """Her alt görevi kendi en uygun modelinde eşzamanlı çalıştırır.

        Görev kimliğinden `{"model": ..., "response": ...}` değerine bir sözlük
        döndürür; böylece çağıran taraf her alt görevi hangi modelin işlediğini
        bilir (doğru kota muhasebesi için gereklidir).
        """
        print(f"[Executor] {len(sub_tasks)} görev paralel çalıştırılıyor...")

        available = list(self.dispatcher.wrappers.keys())

        models = await asyncio.gather(
            *(self.router.select_best_model(item["task"], available) for item in sub_tasks)
        )

        for item, model in zip(sub_tasks, models):
            print(f"  - Görev {item['id']} -> {model}")

        responses = await asyncio.gather(
            *(self.dispatcher.dispatch(model, item["task"]) for item, model in zip(sub_tasks, models)),
            return_exceptions=True,
        )

        return {
            item["id"]: {
                "model": model,
                "response": response if isinstance(response, str) else f"Hata: {response}",
            }
            for item, model, response in zip(sub_tasks, models, responses)
        }
