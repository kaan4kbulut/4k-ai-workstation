"""📦 4K AI PROJECT — fikir analizi, fizibilite raporu ve git worktree tabanlı geliştirme biletleri."""

from __future__ import annotations

import asyncio
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, ValidationError

from . import config
from .db import Database

if TYPE_CHECKING:
    from .engine import Engine


class TicketSpec(BaseModel):
    title: str
    description: str = ""


class IdeaAnalysis(BaseModel):
    name: str = Field(default="yeni-proje")
    summary: str = ""
    feasibility_score: int = Field(default=5, ge=0, le=10)
    risks: list[str] = Field(default_factory=list)
    stack: list[str] = Field(default_factory=list)
    tickets: list[TicketSpec] = Field(default_factory=list)

    def to_markdown(self) -> str:
        bar = "█" * self.feasibility_score + "░" * (10 - self.feasibility_score)
        lines = [
            f"# 📦 {self.name}",
            "",
            f"**Fizibilite:** `{bar}` {self.feasibility_score}/10",
            "",
            "## Özet",
            self.summary or "-",
            "",
            "## Teknoloji Yığını",
            *(f"- {s}" for s in self.stack or ["-"]),
            "",
            "## Riskler",
            *(f"- ⚠️ {r}" for r in self.risks or ["-"]),
            "",
            "## Biletler",
            *(f"{i}. **{t.title}** — {t.description}" for i, t in enumerate(self.tickets, 1)),
        ]
        return "\n".join(lines)


ANALYSIS_PROMPT = """Bir yazılım ürün yöneticisi ve kıdemli mimar olarak aşağıdaki fikri analiz et.
YALNIZCA geçerli JSON döndür, başka metin yazma. Şema:
{{
  "name": "kisa-kebab-case-proje-adi",
  "summary": "2-4 cümlelik Türkçe özet",
  "feasibility_score": 0-10 arası tam sayı,
  "risks": ["risk 1", "..."],
  "stack": ["teknoloji 1", "..."],
  "tickets": [{{"title": "kısa görev başlığı", "description": "kabul kriterleriyle açıklama"}}]
}}
Biletler bağımsız geliştirilebilir, 3-8 adet, sıralı olsun.

FİKİR:
{idea}
"""

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def slugify(text: str, max_len: int = 40) -> str:
    text = text.replace("ı", "i").replace("İ", "i")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].strip("-") or "proje"


def parse_analysis(raw: str, idea: str) -> IdeaAnalysis:
    """Model çıktısından JSON'u ayıklar; başarısız olursa tek biletli güvenli bir analiz döndürür."""
    match = JSON_RE.search(raw.replace("```json", "").replace("```", ""))
    if match:
        try:
            data = json.loads(match.group(0))
            analysis = IdeaAnalysis.model_validate(data)
            analysis.name = slugify(analysis.name)
            if not analysis.tickets:
                analysis.tickets = [TicketSpec(title="MVP", description=idea[:300])]
            return analysis
        except (json.JSONDecodeError, ValidationError):
            pass
    return IdeaAnalysis(
        name=slugify(idea[:40]),
        summary=raw.strip()[:1500] or idea,
        feasibility_score=5,
        tickets=[TicketSpec(title="MVP", description=idea[:300])],
    )


async def _git(*args: str, cwd: Path) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", *args, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {err.decode(errors='replace').strip()}")
    return out.decode(errors="replace").strip()


class ProjectManager:
    def __init__(self, db: Database, engine: Engine | None = None, root: Path | None = None) -> None:
        self.db = db
        self.engine = engine
        self.root = root or config.PROJECTS_DIR

    async def analyze_idea(self, idea: str) -> IdeaAnalysis:
        if not self.engine:
            return parse_analysis("", idea)
        reply = await self.engine.ask(ANALYSIS_PROMPT.format(idea=idea), size="large", system=None)
        return parse_analysis(reply.text, idea)

    async def create_project(self, idea: str, analysis: IdeaAnalysis) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        name = analysis.name
        repo = self.root / name
        n = 2
        while repo.exists():
            repo = self.root / f"{name}-{n}"
            n += 1
        repo.mkdir(parents=True)
        (repo / "README.md").write_text(analysis.to_markdown() + "\n", encoding="utf-8")
        await _git("init", "-q", "-b", "main", cwd=repo)
        await _git("add", "README.md", cwd=repo)
        await _git("-c", "user.name=4K Workstation", "-c", "user.email=4k@localhost",
                   "commit", "-q", "-m", "Proje başlatıldı: fizibilite raporu", cwd=repo)
        project_id = await self.db.execute(
            "INSERT INTO projects(ts, name, idea, feasibility_md, status, repo_path) VALUES(?,?,?,?,?,?)",
            (time.time(), repo.name, idea, analysis.to_markdown(), "geliştirme", str(repo)),
        )
        for t in analysis.tickets:
            await self.db.execute(
                "INSERT INTO tickets(project_id, title, description, status) VALUES(?,?,?,?)",
                (project_id, t.title, t.description, "açık"),
            )
        return project_id

    async def submit_idea(self, idea: str) -> tuple[int, IdeaAnalysis]:
        analysis = await self.analyze_idea(idea)
        return await self.create_project(idea, analysis), analysis

    async def list_projects(self) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT p.id, p.name, p.status, p.repo_path, p.budget, "
            "(SELECT COUNT(*) FROM tickets t WHERE t.project_id=p.id) AS ticket_count, "
            "(SELECT COUNT(*) FROM tickets t WHERE t.project_id=p.id AND t.status='tamamlandı') AS done "
            "FROM projects p ORDER BY p.id DESC"
        )

    async def get_project(self, project_id: int) -> dict[str, Any] | None:
        return await self.db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))

    async def list_tickets(self, project_id: int) -> list[dict[str, Any]]:
        return await self.db.fetchall("SELECT * FROM tickets WHERE project_id=? ORDER BY id", (project_id,))

    async def open_worktree(self, ticket_id: int) -> str:
        t = await self.db.fetchone(
            "SELECT t.*, p.repo_path FROM tickets t JOIN projects p ON p.id=t.project_id WHERE t.id=?",
            (ticket_id,),
        )
        if not t:
            raise ValueError("Bilet bulunamadı")
        if t["worktree_path"] and Path(t["worktree_path"]).exists():
            return t["worktree_path"]
        repo = Path(t["repo_path"])
        branch = f"ticket/{t['id']}-{slugify(t['title'], 30)}"
        wt = repo.parent / f"{repo.name}-wt" / f"{t['id']}-{slugify(t['title'], 30)}"
        wt.parent.mkdir(parents=True, exist_ok=True)
        await _git("worktree", "add", "-q", "-b", branch, str(wt), cwd=repo)
        (wt / "TICKET.md").write_text(f"# {t['title']}\n\n{t['description']}\n", encoding="utf-8")
        await _git("add", "TICKET.md", cwd=wt)
        await _git("-c", "user.name=4K Workstation", "-c", "user.email=4k@localhost",
                   "commit", "-q", "-m", f"Bilet #{t['id']}: {t['title']}", cwd=wt)
        await self.db.execute(
            "UPDATE tickets SET branch=?, worktree_path=?, status='devam ediyor' WHERE id=?",
            (branch, str(wt), ticket_id),
        )
        return str(wt)

    async def close_ticket(self, ticket_id: int, remove_worktree: bool = True) -> None:
        t = await self.db.fetchone(
            "SELECT t.*, p.repo_path FROM tickets t JOIN projects p ON p.id=t.project_id WHERE t.id=?",
            (ticket_id,),
        )
        if not t:
            raise ValueError("Bilet bulunamadı")
        if remove_worktree and t["worktree_path"] and Path(t["worktree_path"]).exists():
            await _git("worktree", "remove", t["worktree_path"], cwd=Path(t["repo_path"]))
        await self.db.execute(
            "UPDATE tickets SET status='tamamlandı', worktree_path=NULL WHERE id=?", (ticket_id,)
        )

    async def set_budget(self, project_id: int, budget: float) -> None:
        await self.db.execute("UPDATE projects SET budget=? WHERE id=?", (budget, project_id))
