"""🏢 4K AI BUSINESS — bütçe, gelir-gider, token maliyeti ve operasyonel görev yönetimi."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from .db import Database

# 1M token başına USD. Abonelik CLI'leri ve yerel modeller doğrudan ücret üretmez (kota tüketir).
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "groq": (0.0, 0.0),
    "openrouter": (0.0, 0.0),
    "gemini-api": (0.0, 0.0),
}
SUBSCRIPTION_PROVIDERS = {"claude", "codex", "antigravity", "gemini", "grok", "opencode"}
TASK_STATUSES = ("yapılacak", "devam ediyor", "tamamlandı")


class Business:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- gelir / gider ---------------------------------------------------
    async def add_entry(self, type_: str, amount: float, category: str = "genel", note: str = "",
                        project_id: int | None = None, currency: str = "TRY") -> int:
        if type_ not in ("gelir", "gider"):
            raise ValueError("Tür 'gelir' veya 'gider' olmalı")
        if amount <= 0:
            raise ValueError("Tutar pozitif olmalı")
        return await self.db.execute(
            "INSERT INTO ledger(ts, project_id, type, amount, currency, category, note) VALUES(?,?,?,?,?,?,?)",
            (time.time(), project_id, type_, amount, currency, category, note),
        )

    async def delete_entry(self, entry_id: int) -> None:
        await self.db.execute("DELETE FROM ledger WHERE id=?", (entry_id,))

    async def entries(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT l.*, p.name AS project FROM ledger l LEFT JOIN projects p ON p.id=l.project_id "
            "ORDER BY l.ts DESC LIMIT ?", (limit,)
        )

    async def summary(self) -> dict[str, Any]:
        rows = await self.db.fetchall(
            "SELECT currency, type, SUM(amount) AS total FROM ledger GROUP BY currency, type"
        )
        by_currency: dict[str, dict[str, float]] = {}
        for r in rows:
            c = by_currency.setdefault(r["currency"], {"gelir": 0.0, "gider": 0.0})
            c[r["type"]] = r["total"] or 0.0
        for c in by_currency.values():
            c["net"] = c["gelir"] - c["gider"]

        month_start = dt.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        monthly = await self.db.fetchall(
            "SELECT currency, type, SUM(amount) AS total FROM ledger WHERE ts>=? GROUP BY currency, type",
            (month_start,),
        )
        return {"by_currency": by_currency, "this_month": monthly}

    async def project_budgets(self) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT p.id, p.name, p.budget, "
            "COALESCE((SELECT SUM(amount) FROM ledger WHERE project_id=p.id AND type='gider'),0) AS spent, "
            "COALESCE((SELECT SUM(amount) FROM ledger WHERE project_id=p.id AND type='gelir'),0) AS earned "
            "FROM projects p ORDER BY p.id DESC"
        )

    # --- token maliyeti ---------------------------------------------------
    async def token_costs(self, days: int = 30) -> list[dict[str, Any]]:
        since = time.time() - days * 86400
        rows = await self.db.fetchall(
            "SELECT provider, COUNT(*) AS calls, SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, "
            "SUM(cost_usd) AS cost FROM usage WHERE ts>=? GROUP BY provider ORDER BY calls DESC",
            (since,),
        )
        for r in rows:
            pin, pout = PRICE_PER_MTOK.get(r["provider"], (0.0, 0.0))
            r["cost"] = (r["cost"] or 0.0) + ((r["tin"] or 0) * pin + (r["tout"] or 0) * pout) / 1e6
            if r["provider"] in SUBSCRIPTION_PROVIDERS:
                r["tier"] = "abonelik (kota)"
            elif r["provider"].startswith("ollama/"):
                r["tier"] = "yerel (ücretsiz)"
            else:
                r["tier"] = "API"
        return rows

    async def quota_saved_ratio(self, days: int = 30) -> float:
        """Yerel/ücretsiz modellere yönlendirilen çağrıların oranı (abonelik kotası tasarrufu)."""
        rows = await self.token_costs(days)
        total = sum(r["calls"] for r in rows)
        if not total:
            return 0.0
        subs = sum(r["calls"] for r in rows if r["tier"].startswith("abonelik"))
        return 1 - subs / total

    # --- görevler ---------------------------------------------------------
    async def add_task(self, title: str, project_id: int | None = None, due: str | None = None) -> int:
        if not title.strip():
            raise ValueError("Görev başlığı boş olamaz")
        return await self.db.execute(
            "INSERT INTO tasks(ts, project_id, title, status, due) VALUES(?,?,?,?,?)",
            (time.time(), project_id, title.strip(), "yapılacak", due),
        )

    async def tasks(self) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT t.*, p.name AS project FROM tasks t LEFT JOIN projects p ON p.id=t.project_id "
            "ORDER BY CASE t.status WHEN 'devam ediyor' THEN 0 WHEN 'yapılacak' THEN 1 ELSE 2 END, t.id DESC"
        )

    async def advance_task(self, task_id: int) -> str:
        row = await self.db.fetchone("SELECT status FROM tasks WHERE id=?", (task_id,))
        if not row:
            raise ValueError("Görev bulunamadı")
        idx = TASK_STATUSES.index(row["status"]) if row["status"] in TASK_STATUSES else 0
        new = TASK_STATUSES[(idx + 1) % len(TASK_STATUSES)]
        await self.db.execute("UPDATE tasks SET status=? WHERE id=?", (new, task_id))
        return new

    async def delete_task(self, task_id: int) -> None:
        await self.db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
