import asyncio
from typing import List, Dict
from core.dispatcher import Dispatcher
from core.router import IntelligentRouter

class ParallelExecutor:
    def __init__(self, dispatcher: Dispatcher, router: IntelligentRouter):
        self.dispatcher = dispatcher
        self.router = router

    async def run_parallel(self, sub_tasks: List[Dict]) -> Dict[int, str]:
        print(f"[Executor] Running {len(sub_tasks)} tasks in parallel...")
        
        tasks = []
        task_ids = []

        for item in sub_tasks:
            # Determine the best model for each sub-task
            model = await self.router.select_best_model(item['task'])
            print(f"  - Task {item['id']} assigned to {model}")
            
            tasks.append(self.dispatcher.dispatch(model, item['task']))
            task_ids.append(item['id'])

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return dict(zip(task_ids, results))