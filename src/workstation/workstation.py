"""Tüm çekirdek modülleri tek bir nesnede birleştirir (TUI, CLI ve API ortak kullanır)."""

from __future__ import annotations

from pathlib import Path

from . import config
from .business import Business
from .db import Database
from .engine import Engine
from .project import ProjectManager
from .radar import Radar
from .sync import ApiServer, SyncManager


class Workstation:
    def __init__(self, db_path: Path | None = None) -> None:
        config.ensure_dirs()
        self.db = Database(db_path)
        self.engine = Engine(self.db)
        self.radar = Radar(self.db, self.engine)
        self.projects = ProjectManager(self.db, self.engine)
        self.business = Business(self.db)
        self.sync = SyncManager(self.db)
        self.api = ApiServer(self)

    async def shutdown(self) -> None:
        await self.api.stop()
        self.db.close()
