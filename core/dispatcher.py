import asyncio
import os
from typing import Any, Dict, List
from wrappers.base_wrapper import BaseWrapper


class Dispatcher:
    """Kayıtlı wrapper'lara istek gönderen ve hata durumunda otomatik eskalasyon yapan dağıtıcı."""

    def __init__(self):
        self.wrappers: Dict[str, BaseWrapper] = {}

    def register_wrapper(self, name: str, wrapper: BaseWrapper):
        self.wrappers[name] = wrapper

    async def dispatch(
        self,
        target_wrapper_name: str,
        prompt: str,
        workspace: str | None = None,
    ) -> str:
        if target_wrapper_name not in self.wrappers:
            return f"Hata: {target_wrapper_name} wrapper'ı kayıtlı değil."

        wrapper = self.wrappers[target_wrapper_name]
        if workspace and os.path.isdir(workspace):
            setattr(wrapper, "workspace", workspace)
        print(f"[Dispatcher] İstek gönderiliyor: {wrapper.name}...")
        return await wrapper.execute(prompt)

    async def dispatch_with_escalation(
        self,
        candidate_models: List[str],
        prompt: str,
        workspace: str | None = None,
    ) -> Dict[str, Any]:
        """Aday modelleri sırayla dener; ilk model hata verirse bir üst modele yükseltir (escalation)."""
        attempts: List[Dict[str, str]] = []
        valid_candidates = [m for m in candidate_models if m in self.wrappers]
        if not valid_candidates and self.wrappers:
            valid_candidates = [next(iter(self.wrappers.keys()))]

        for model_name in valid_candidates:
            try:
                response = await self.dispatch(model_name, prompt, workspace=workspace)
            except Exception as exc:
                response = f"Hata: {exc}"

            if response and not response.startswith("Hata:"):
                attempts.append({"model": model_name, "status": "ok", "success": True})
                return {
                    "model": model_name,
                    "response": response,
                    "escalated": len(attempts) > 1,
                    "attempts": attempts,
                }
            detail_msg = response[:160]
            attempts.append(
                {
                    "model": model_name,
                    "status": "error",
                    "success": False,
                    "detail": detail_msg,
                    "error": detail_msg,
                }
            )
            print(f"[Dispatcher] {model_name} başarısız oldu, bir üst modele yükseltiliyor...")

        last_model = valid_candidates[-1] if valid_candidates else "Ollama"
        last_err = attempts[-1].get("detail", "Hata: Kullanılabilir model bulunamadı.") if attempts else "Hata: Model yok."
        return {
            "model": last_model,
            "response": last_err,
            "escalated": len(attempts) > 1,
            "attempts": attempts,
        }

    async def dispatch_parallel(self, target_wrappers: List[str], prompt: str) -> Dict[str, str]:
        tasks = {
            name: self.wrappers[name].execute(prompt)
            for name in target_wrappers
            if name in self.wrappers
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), results))