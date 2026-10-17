import asyncio
from typing import Dict, List

from core.dispatcher import Dispatcher
from core.router import IntelligentRouter


class ParallelExecutor:
    def __init__(self, dispatcher: Dispatcher, router: IntelligentRouter):
        self.dispatcher = dispatcher
        self.router = router

    async def run_parallel(self, sub_tasks: List[Dict]) -> Dict[int, Dict[str, str]]:
        """Run every sub-task on its own best model, concurrently.

        Returns a mapping of task id to `{"model": ..., "response": ...}` so the
        caller knows which model actually handled each sub-task (needed for
        accurate quota accounting).
        """
        print(f"[Executor] Running {len(sub_tasks)} tasks in parallel...")

        available = list(self.dispatcher.wrappers.keys())

        models = await asyncio.gather(
            *(self.router.select_best_model(item["task"], available) for item in sub_tasks)
        )

        for item, model in zip(sub_tasks, models):
            print(f"  - Task {item['id']} assigned to {model}")

        responses = await asyncio.gather(
            *(self.dispatcher.dispatch(model, item["task"]) for item, model in zip(sub_tasks, models)),
            return_exceptions=True,
        )

        return {
            item["id"]: {
                "model": model,
                "response": response if isinstance(response, str) else f"Error: {response}",
            }
            for item, model, response in zip(sub_tasks, models, responses)
        }
