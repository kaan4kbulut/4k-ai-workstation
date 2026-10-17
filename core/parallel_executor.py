"""Faz 3: Paralel Yürütücü ve Çoklu Ajan Sentezleyici (Mixture-of-Agents Aggregator).

Her alt görevi yetenek ve maliyet açısından en uygun modele eşzamanlı dağıtır,
ardından tüm ajanların çıktılarını tek bir bütünleşik yanıtta sentezler.
"""

from __future__ import annotations

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

        output: Dict[int, Dict[str, str]] = {}
        for item, model, response in zip(sub_tasks, models, responses):
            entry = {
                "model": model,
                "response": response if isinstance(response, str) else f"Hata: {response}",
            }
            if "title" in item:
                entry["title"] = str(item["title"])
            if "type" in item:
                entry["type"] = str(item["type"])
            output[item["id"]] = entry
        return output

    @staticmethod
    def build_fallback_synthesis(
        original_prompt: str,
        sub_tasks: List[Dict],
        results: Dict[int, Dict[str, str]],
    ) -> str:
        """LLM sentezleyici kullanılamadığında alt görev çıktılarını bütünleşik raporda birleştirir."""
        sections = [f"### 🎯 Birleştirilmiş Görev Çıktısı\n**Ana İstek:** {original_prompt}\n"]
        task_map = {item["id"]: item for item in sub_tasks}
        for task_id, res in results.items():
            meta = task_map.get(task_id, {})
            title = meta.get("title") or f"Alt Görev {task_id}"
            sections.append(
                f"#### {task_id}. {title} *(Model: `{res.get('model')}`)*\n{res.get('response', '')}\n"
            )
        return "\n".join(sections).strip()

    async def synthesize_results(
        self,
        original_prompt: str,
        sub_tasks: List[Dict],
        results: Dict[int, Dict[str, str]],
        synthesizer_model: str | None = None,
    ) -> Dict[str, str]:
        """Paralel çalışan modellerin çıktılarını tek bir nihai yanıtta sentezler (Aggregator)."""
        if not results:
            return {"model": "none", "response": ""}

        available = list(self.dispatcher.wrappers.keys())
        target_model = synthesizer_model
        if not target_model or target_model == "auto" or target_model not in self.dispatcher.wrappers:
            target_model = await self.router.select_best_model(original_prompt, available)

        parts_text = []
        task_map = {item["id"]: item for item in sub_tasks}
        for tid, res in results.items():
            title = task_map.get(tid, {}).get("title", f"Alt Görev {tid}")
            parts_text.append(
                f"--- Alt Görev {tid}: {title} (Model: {res['model']}) ---\n{res['response']}"
            )

        synth_prompt = (
            "Aşağıda bir ana görevin paralel çalışan farklı yapay zeka modelleri tarafından "
            "üretilmiş alt görev çıktıları yer alıyor. Bu çıktıları tekrarsız, tutarlı ve "
            "doğrudan kullanılabilir tek bir nihai Türkçe yanıtta birleştir:\n\n"
            f"ANA GÖREV: {original_prompt}\n\n"
            + "\n\n".join(parts_text)
        )

        if target_model in self.dispatcher.wrappers:
            raw = await self.dispatcher.dispatch(target_model, synth_prompt)
            if raw and not raw.startswith("Hata:"):
                return {"model": target_model, "response": raw}

        return {
            "model": "Aggregator (Yerel Birleştirici)",
            "response": self.build_fallback_synthesis(original_prompt, sub_tasks, results),
        }
