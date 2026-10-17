import asyncio
from typing import List, Dict
from wrappers.base_wrapper import BaseWrapper

class Dispatcher:
    """Kayıtlı wrapper'lara istek gönderen dağıtıcı."""

    def __init__(self):
        self.wrappers: Dict[str, BaseWrapper] = {}

    def register_wrapper(self, name: str, wrapper: BaseWrapper):
        self.wrappers[name] = wrapper

    async def dispatch(self, target_wrapper_name: str, prompt: str) -> str:
        if target_wrapper_name not in self.wrappers:
            return f"Hata: {target_wrapper_name} wrapper'ı kayıtlı değil."

        wrapper = self.wrappers[target_wrapper_name]
        print(f"[Dispatcher] İstek gönderiliyor: {wrapper.name}...")
        return await wrapper.execute(prompt)

    async def dispatch_parallel(self, target_wrappers: List[str], prompt: str) -> Dict[str, str]:
        tasks = {name: self.wrappers[name].execute(prompt) 
                 for name in target_wrappers if name in self.wrappers}
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), results))