"""Faz 3: Gerçek Görev Parçalayıcı (Task Planner / Decomposer).

Bu modül:
1. ``decompose_with_llm`` ile karmaşık bir görevi aktif bir LLM kullanarak
   JSON formatında bağımsız alt görevlere (mimari, kodlama, araştırma, test,
   dokümantasyon) ayırır.
2. LLM erişilemediğinde veya çevrimdışı modda ``decompose`` ile çok cümleli /
   maddeli / bağlaçlı istekleri yapısal olarak analiz edip her alt görevin
   zorluk derecesini (1-10) ve türünü (`architecture`, `code`, `search`, `docs`)
   belirler.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List


DECOMPOSE_SYSTEM_PROMPT = """Sen bir yazılım mimarı ve görev planlayıcısısın (Task Decomposer).
Kullanıcının verdiği karmaşık isteği paralel çalışabilecek 2 ila 5 bağımsız alt göreve böl.
Yanıt olarak SADECE geçerli bir JSON dizisi (array) döndür, başka hiçbir açıklama yazma.
Format:
[
  {"id": 1, "title": "Kısa başlık", "task": "Alt görevin detaylı talimatı", "complexity": 8, "type": "architecture"},
  {"id": 2, "title": "Kısa başlık", "task": "Alt görevin detaylı talimatı", "complexity": 7, "type": "code"}
]
Geçerli type değerleri: "architecture", "code", "search", "docs", "general".
"""


def _infer_subtask_metadata(text: str) -> tuple[int, str]:
    """Bir alt görev metninin karmaşıklığını (1-10) ve görev tipini tahmin eder."""
    lower = text.lower()
    if any(w in lower for w in ("mimari", "architecture", "şema", "schema", "tasarla", "design", "güvenlik", "security")):
        return 9, "architecture"
    if any(w in lower for w in ("araştır", "search", "güncel", "kaynak", "benchmark", "karşılaştır")):
        return 6, "search"
    if any(w in lower for w in ("dokümantasyon", "readme", "açıkla", "özetle", "docs", "rapor")):
        return 3, "docs"
    if any(w in lower for w in ("kod", "code", "uygula", "implement", "api", "endpoint", "fonksiyon", "test", "bug", "fix", "yaz")):
        return 7, "code"
    return 5, "general"


class TaskPlanner:
    """Karmaşık görevleri paralel yürütülebilir alt görevlere böler."""

    @staticmethod
    def parse_llm_plan(raw_output: str) -> List[Dict] | None:
        """LLM yanıtından JSON alt görev listesini güvenli şekilde ayıklar."""
        if not raw_output or raw_output.startswith("Hata:"):
            return None
        match = re.search(r"\[.*\]", raw_output, flags=re.DOTALL)
        candidate = match.group(0) if match else raw_output.strip()
        try:
            parsed = json.loads(candidate)
        except Exception:
            return None

        if not isinstance(parsed, list) or not parsed:
            return None

        cleaned: List[Dict] = []
        for idx, item in enumerate(parsed, start=1):
            if not isinstance(item, dict) or not item.get("task"):
                continue
            task_text = str(item["task"]).strip()
            default_comp, default_type = _infer_subtask_metadata(task_text)
            cleaned.append(
                {
                    "id": int(item.get("id", idx)),
                    "title": str(item.get("title") or f"Alt Görev {idx}"),
                    "task": task_text,
                    "complexity": max(1, min(10, int(item.get("complexity", default_comp)))),
                    "type": str(item.get("type", default_type)),
                }
            )
        return cleaned if cleaned else None

    async def decompose(self, prompt: str) -> List[Dict]:
        """Yapısal/kural tabanlı görev parçalama (çevrimdışı ve hızlı mod)."""
        print(f"[Planner] Görev bölünüyor: {prompt[:50]}...")
        cleaned_prompt = prompt.strip()

        # 1) Numaralı veya madde işaretli satırlar varsa doğrudan ayır
        lines = [
            re.sub(r"^(\d+[\.\)]\s*|[-*•]\s*)", "", line).strip()
            for line in cleaned_prompt.splitlines()
            if line.strip()
        ]
        if len(lines) >= 2:
            sub_tasks = []
            for idx, line in enumerate(lines[:6], start=1):
                comp, ttype = _infer_subtask_metadata(line)
                sub_tasks.append(
                    {
                        "id": idx,
                        "title": f"Adım {idx} ({ttype})",
                        "task": line,
                        "complexity": comp,
                        "type": ttype,
                    }
                )
            return sub_tasks

        # 2) Bağlaçlarla ("ve", "and", "ayrıca", ";") ayrılmış anlamlı parçalar varsa
        parts = [
            p.strip()
            for p in re.split(r"\s+(?:ve|and|ayrıca|sonra)\s+|;\s*", cleaned_prompt, flags=re.IGNORECASE)
            if len(p.strip()) >= 12
        ]
        if len(parts) >= 2 and (len(cleaned_prompt) > 40 or " ve " in cleaned_prompt.lower() or " and " in cleaned_prompt.lower()):
            sub_tasks = []
            for idx, part in enumerate(parts[:5], start=1):
                comp, ttype = _infer_subtask_metadata(part)
                sub_tasks.append(
                    {
                        "id": idx,
                        "title": f"Bölüm {idx} ({ttype})",
                        "task": f"Ana bağlam ({cleaned_prompt}) kapsamında şu alt görevi tamamla: {part}",
                        "complexity": comp,
                        "type": ttype,
                    }
                )
            return sub_tasks

        # 3) Uzun/karmaşık tek parça mühendislik isteği
        if len(cleaned_prompt) > 50 or " and " in cleaned_prompt.lower() or " ve " in cleaned_prompt.lower():
            return [
                {
                    "id": 1,
                    "title": "Mimari ve Teknik Tasarım",
                    "task": f"Analiz et ve sistem mimarisini/veri yapılarını planla: {cleaned_prompt}",
                    "complexity": 9,
                    "type": "architecture",
                },
                {
                    "id": 2,
                    "title": "Kod Uygulaması",
                    "task": f"Temel uygulama kodunu ve hata yönetimini yaz: {cleaned_prompt}",
                    "complexity": 7,
                    "type": "code",
                },
                {
                    "id": 3,
                    "title": "Test ve Dokümantasyon",
                    "task": f"Kullanım kılavuzu ve doğrulama senaryolarını oluştur: {cleaned_prompt}",
                    "complexity": 3,
                    "type": "docs",
                },
            ]

        return [{"id": 1, "title": "Genel Görev", "task": cleaned_prompt, "complexity": 5, "type": "general"}]

    async def decompose_with_llm(
        self,
        prompt: str,
        dispatcher,
        planner_model: str = "Ollama",
    ) -> List[Dict]:
        """Aktif bir LLM üzerinden görevi akıllı alt görevlere böler; başarısız olursa yapısal bölmeye düşer."""
        if planner_model in getattr(dispatcher, "wrappers", {}):
            full_prompt = f"{DECOMPOSE_SYSTEM_PROMPT}\n\nKullanıcı İsteği:\n{prompt}"
            try:
                raw = await dispatcher.dispatch(planner_model, full_prompt)
                parsed = self.parse_llm_plan(raw)
                if parsed:
                    return parsed
            except Exception:
                pass
        return await self.decompose(prompt)
