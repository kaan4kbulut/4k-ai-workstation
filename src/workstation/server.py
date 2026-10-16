"""Masaüstü uygulamasının arka ucu: tüm çekirdek modülleri REST API olarak sunar.

Electron ana süreci bu sunucuyu `--desktop-backend --port N` ile başlatır ve
`FOURK_DESKTOP_TOKEN` ortam değişkeniyle paylaşılan bir token gönderir. Sunucu yalnızca
127.0.0.1'e bağlanır; stdin kapandığında (ana süreç öldüğünde) kendini kapatır.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import config
from .engine import ProviderError
from .sync import GOOGLE_SETUP_HELP, list_local_backups
from .workstation import Workstation


class ChatIn(BaseModel):
    message: str


class QueryIn(BaseModel):
    query: str


class GearIn(BaseModel):
    gear: str


class IdeaIn(BaseModel):
    idea: str


class LedgerIn(BaseModel):
    type: str
    amount: float
    category: str = "genel"
    note: str = ""
    currency: str = "TRY"
    project_id: int | None = None


class TaskIn(BaseModel):
    title: str
    project_id: int | None = None


class BudgetIn(BaseModel):
    budget: float


def create_app(ws: Workstation, token: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        asyncio.create_task(ws.engine.discover())
        yield
        await ws.shutdown()

    app = FastAPI(title="4K AI WORKSTATION Desktop API", version=config.APP_VERSION, lifespan=lifespan)

    async def auth(x_4k_token: str = Header(default="")) -> None:
        if not secrets.compare_digest(x_4k_token, token):
            raise HTTPException(status_code=401, detail="Yetkisiz istek")

    @app.exception_handler(ProviderError)
    async def provider_error(_: Request, exc: ProviderError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RuntimeError)
    async def runtime_error(_: Request, exc: RuntimeError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.get("/health")
    async def health():
        return {"ok": True, "version": config.APP_VERSION}

    deps = [Depends(auth)]

    # ------------------------------------------------------------ genel durum
    @app.get("/api/overview", dependencies=deps)
    async def overview():
        system = await ws.engine.discover()
        gear = await ws.engine.get_gear()
        now = time.time()
        known = {p.label() for p in ws.engine.providers}
        providers = [
            {**r, "cooling": (r["cooldown_until"] or 0) > now,
             "cooldown_min": max(0, int(((r["cooldown_until"] or 0) - now) / 60) + 1)}
            for r in await ws.engine.cooldown_status() if r["name"] in known
        ]
        return {
            "app": {"name": config.APP_NAME, "version": config.APP_VERSION, "device": config.DEVICE_NAME},
            "system": system,
            "gear": gear,
            "gears": config.GEARS,
            "routes": {
                "small": [p.label() for p in ws.engine.plan_route(gear, "small")[:4]],
                "large": [p.label() for p in ws.engine.plan_route(gear, "large")[:4]],
            },
            "quota_saved": await ws.business.quota_saved_ratio(),
            "providers": providers,
            "usage": await ws.db.fetchall("SELECT * FROM usage ORDER BY id DESC LIMIT 12"),
        }

    @app.post("/api/discover", dependencies=deps)
    async def discover():
        return await ws.engine.discover(force=True)

    @app.put("/api/gear", dependencies=deps)
    async def set_gear(body: GearIn):
        await ws.engine.set_gear(body.gear)
        return {"gear": body.gear}

    @app.post("/api/cooldowns/reset", dependencies=deps)
    async def reset_cooldowns():
        await ws.engine.reset_cooldowns()
        return {"ok": True}

    # ------------------------------------------------------------------ sohbet
    @app.get("/api/chat", dependencies=deps)
    async def chat_history():
        return await ws.db.fetchall(
            "SELECT * FROM (SELECT * FROM chat_history ORDER BY id DESC LIMIT 50) ORDER BY id"
        )

    @app.post("/api/chat", dependencies=deps)
    async def chat(body: ChatIn):
        if not body.message.strip():
            raise ValueError("Mesaj boş olamaz")
        r = await ws.engine.chat(body.message)
        return {"text": r.text, "label": r.label, "tier": r.tier, "gear": r.gear,
                "attempts": r.attempts, "elapsed": r.elapsed}

    @app.delete("/api/chat", dependencies=deps)
    async def chat_clear():
        await ws.engine.clear_chat()
        return {"ok": True}

    # ------------------------------------------------------------------- radar
    @app.post("/api/radar/quick", dependencies=deps)
    async def radar_quick(body: QueryIn):
        return {"report": await ws.radar.quick_search(body.query)}

    @app.post("/api/radar/deep", dependencies=deps)
    async def radar_deep(body: QueryIn):
        return {"report": await ws.radar.deep_research(body.query)}

    @app.get("/api/radar/github", dependencies=deps)
    async def radar_github(topic: str = "ai-agents"):
        return await ws.radar.github_trends(topic)

    @app.get("/api/radar/history", dependencies=deps)
    async def radar_history():
        return await ws.radar.history()

    # ----------------------------------------------------------------- project
    @app.get("/api/projects", dependencies=deps)
    async def projects():
        return await ws.projects.list_projects()

    @app.get("/api/projects/{project_id}", dependencies=deps)
    async def project(project_id: int):
        p = await ws.projects.get_project(project_id)
        if not p:
            raise HTTPException(404, "Proje bulunamadı")
        return {**p, "tickets": await ws.projects.list_tickets(project_id)}

    @app.post("/api/projects", dependencies=deps)
    async def create_project(body: IdeaIn):
        if len(body.idea.strip()) < 10:
            raise ValueError("Fikrinizi biraz daha detaylı anlatın")
        pid, analysis = await ws.projects.submit_idea(body.idea.strip())
        return {"id": pid, "name": analysis.name, "tickets": len(analysis.tickets)}

    @app.put("/api/projects/{project_id}/budget", dependencies=deps)
    async def set_budget(project_id: int, body: BudgetIn):
        await ws.projects.set_budget(project_id, body.budget)
        return {"ok": True}

    @app.post("/api/tickets/{ticket_id}/worktree", dependencies=deps)
    async def open_worktree(ticket_id: int):
        return {"path": await ws.projects.open_worktree(ticket_id)}

    @app.post("/api/tickets/{ticket_id}/close", dependencies=deps)
    async def close_ticket(ticket_id: int):
        await ws.projects.close_ticket(ticket_id)
        return {"ok": True}

    # ---------------------------------------------------------------- business
    @app.get("/api/business", dependencies=deps)
    async def business():
        b = ws.business
        return {
            "summary": await b.summary(),
            "entries": await b.entries(),
            "tasks": await b.tasks(),
            "budgets": await b.project_budgets(),
            "token_costs": await b.token_costs(),
        }

    @app.post("/api/ledger", dependencies=deps)
    async def add_ledger(body: LedgerIn):
        return {"id": await ws.business.add_entry(body.type, body.amount, body.category or "genel", body.note,
                                                  body.project_id, body.currency)}

    @app.delete("/api/ledger/{entry_id}", dependencies=deps)
    async def delete_ledger(entry_id: int):
        await ws.business.delete_entry(entry_id)
        return {"ok": True}

    @app.post("/api/tasks", dependencies=deps)
    async def add_task(body: TaskIn):
        return {"id": await ws.business.add_task(body.title, body.project_id)}

    @app.post("/api/tasks/{task_id}/advance", dependencies=deps)
    async def advance_task(task_id: int):
        return {"status": await ws.business.advance_task(task_id)}

    @app.delete("/api/tasks/{task_id}", dependencies=deps)
    async def delete_task(task_id: int):
        await ws.business.delete_task(task_id)
        return {"ok": True}

    # -------------------------------------------------------------------- sync
    @app.get("/api/sync", dependencies=deps)
    async def sync_state(refresh: bool = True):
        status = await ws.sync.refresh() if refresh or not ws.sync.last_status else ws.sync.last_status
        cloud = ws.sync.cloud_state()
        last = await ws.db.get_setting("last_backup")
        return {
            "tailscale": status,
            "cloud": cloud,
            "email": await ws.db.get_setting("google_email") or "",
            "last_backup": float(last) if last else None,
            "local_backups": len(list_local_backups()),
            "backup_dir": str(config.BACKUP_DIR),
            "db_path": str(ws.db.path),
            "client_secret_path": str(config.GOOGLE_CLIENT_SECRET),
            "setup_help": GOOGLE_SETUP_HELP if cloud == "yapılandırılmadı" else "",
            "log": await ws.sync.log(),
            "remote_api": {"running": ws.api.running, "url": ws.api.url if ws.api.running else None,
                           "token": await ws.sync.api_token() if ws.api.running else None},
        }

    @app.post("/api/sync/google/connect", dependencies=deps)
    async def google_connect():
        if not ws.sync.drive.configured():
            raise ValueError(f"Önce client_secret.json dosyasını {config.GOOGLE_CLIENT_SECRET} konumuna koyun")
        return {"email": await ws.sync.connect_google()}

    @app.post("/api/sync/google/disconnect", dependencies=deps)
    async def google_disconnect():
        await ws.sync.disconnect_google()
        return {"ok": True}

    @app.post("/api/sync/backup", dependencies=deps)
    async def backup():
        return await ws.sync.backup()

    @app.post("/api/sync/restore", dependencies=deps)
    async def restore():
        return await ws.sync.restore_latest()

    @app.post("/api/sync/remote/start", dependencies=deps)
    async def remote_start():
        return {"url": await ws.api.start(), "token": await ws.sync.api_token()}

    @app.post("/api/sync/remote/stop", dependencies=deps)
    async def remote_stop():
        await ws.api.stop()
        return {"ok": True}

    return app


def _exit_when_parent_dies() -> None:
    """Electron stdin'i bir boru olarak açar; ana süreç ölünce EOF gelir ve arka uç kapanır."""

    def watch() -> None:
        try:
            while sys.stdin.read(1024):
                pass
        except (OSError, ValueError):
            pass
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def run(port: int, watch_stdin: bool = True) -> int:
    import uvicorn

    token = os.environ.get("FOURK_DESKTOP_TOKEN") or secrets.token_urlsafe(24)
    if watch_stdin and not sys.stdin.isatty():
        _exit_when_parent_dies()
    ws = Workstation()
    uvicorn.run(create_app(ws, token), host="127.0.0.1", port=port, log_level="warning")
    return 0
