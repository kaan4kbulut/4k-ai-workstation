import asyncio
from typing import List, Dict
from wrappers.base_wrapper import BaseWrapper

class Dispatcher:
    def __init__(self):
        self.wrappers: Dict[str, BaseWrapper] = {}

    def register_wrapper(self, name: str, wrapper: BaseWrapper):
        self.wrappers[name] = wrapper

    async def dispatch(self, target_wrapper_name: str, prompt: str) -> str:
        if target_wrapper_name not in self.wrappers:
            return f"Error: Wrapper {target_wrapper_name} not registered."
        
        wrapper = self.wrappers[target_wrapper_name]
        print(f"[Dispatcher] Sending request to {wrapper.name}...")
        return await wrapper.execute(prompt)

    async def dispatch_parallel(self, target_wrappers: List[str], prompt: str) -> Dict[str, str]:
        tasks = {name: self.wrappers[name].execute(prompt) 
                 for name in target_wrappers if name in self.wrappers}
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), results))