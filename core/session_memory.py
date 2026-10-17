"""Çok turlu sohbet ve görev hafızası (Session Memory).

Kullanıcının Komut Merkezi'nde yaptığı konuşmaları oturum bazında (`session_id`)
kalıcı olarak `data/sessions.json` dosyasında saklar ve yeni isteklere önceki
konuşma bağlamını ekler.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List


class SessionMemory:
    def __init__(self, storage_file: str = "data/sessions.json", max_context_turns: int = 6):
        self.storage_file = storage_file
        self.max_context_turns = max_context_turns
        self.sessions: Dict[str, List[Dict]] = self._load()

    def _load(self) -> Dict[str, List[Dict]]:
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {"varsayilan": []}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_file) or ".", exist_ok=True)
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, indent=2, ensure_ascii=False)

    def list_sessions(self) -> List[str]:
        if not self.sessions:
            self.sessions["varsayilan"] = []
        return list(self.sessions.keys())

    def get_history(self, session_id: str = "varsayilan") -> List[Dict]:
        return list(self.sessions.get(session_id, []))

    def append_turn(
        self,
        session_id: str,
        user_prompt: str,
        assistant_response: str,
        model_used: str,
    ) -> None:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(
            {
                "timestamp": int(time.time()),
                "user": user_prompt,
                "assistant": assistant_response,
                "model": model_used,
            }
        )
        self._save()

    def clear_session(self, session_id: str = "varsayilan") -> None:
        self.sessions[session_id] = []
        self._save()

    def build_contextual_prompt(self, session_id: str, new_prompt: str) -> str:
        """Önceki konuşma turlarını yeni isteğin başına bağlam olarak ekler."""
        history = self.sessions.get(session_id, [])
        if not history:
            return new_prompt
        recent = history[-self.max_context_turns :]
        lines = ["[Önceki Konuşma Bağlamı]"]
        for turn in recent:
            u = str(turn.get("user", "")).strip()
            a = str(turn.get("assistant", "")).strip()[:600]
            lines.append(f"Kullanıcı: {u}\nAsistan ({turn.get('model', 'AI')}): {a}")
        lines.append(f"\n[Yeni İstek]\n{new_prompt}")
        return "\n\n".join(lines)
