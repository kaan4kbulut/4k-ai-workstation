"""🔍 4K AI RADAR — reklamsız web araması, içerik kazıma ve GitHub trend avcısı."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import shutil
import subprocess
import time
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx
from bs4 import BeautifulSoup

from . import config
from .db import Database

if TYPE_CHECKING:
    from .engine import Engine

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
NOISE_TAGS = ("script", "style", "nav", "aside", "footer", "header", "form", "noscript", "iframe", "svg")
GITHUB_TOPICS = {
    "ai-agents": "topic:ai-agents",
    "llm": "topic:llm",
    "memory": "llm memory in:name,description,readme",
    "mcp": "topic:mcp",
}


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


def _ddgs_text(query: str, max_results: int) -> list[dict[str, Any]]:
    try:
        from ddgs import DDGS  # yeni paket adı
    except ImportError:  # pragma: no cover
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from duckduckgo_search import DDGS
    return list(DDGS().text(query, region="tr-tr", max_results=max_results) or [])


async def web_search(query: str, max_results: int = 5) -> list[SearchHit]:
    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_ddgs_text, query, max_results), timeout=25)
    except Exception as e:  # ağ / kısıtlama hataları
        raise RuntimeError(f"Arama başarısız: {e}") from e
    return [SearchHit(r.get("title", ""), r.get("href", ""), r.get("body", "")) for r in raw]


def clean_html(html: str, limit: int = 4000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for el in soup.select("[class*=ad-], [id*=ad-], [class*=advert], [class*=cookie], [class*=banner]"):
        el.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = " ".join(main.get_text(" ", strip=True).split())
    return text[:limit]


async def fetch_page(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(url, follow_redirects=True)
        if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
            return ""
        return clean_html(r.text)
    except (httpx.HTTPError, ValueError):
        return ""


def _format_sources(hits: list[SearchHit]) -> str:
    return "\n".join(f"{i}. [{h.title}]({h.url})" for i, h in enumerate(hits, 1))


class Radar:
    def __init__(self, db: Database, engine: Engine | None = None) -> None:
        self.db = db
        self.engine = engine

    async def _save(self, query: str, mode: str, report: str) -> None:
        await self.db.execute(
            "INSERT INTO searches(ts, query, mode, report) VALUES(?,?,?,?)",
            (time.time(), query, mode, report),
        )

    async def quick_search(self, query: str) -> str:
        hits = await web_search(query, 6)
        if not hits:
            return f"## ⚡ Hızlı Arama: {query}\n\nSonuç bulunamadı."
        body = "\n\n".join(f"**{i}. {h.title}**  \n{h.snippet}  \n🔗 {h.url}" for i, h in enumerate(hits, 1))
        report = f"## ⚡ Hızlı Arama: {query}\n\n{body}"
        await self._save(query, "hızlı", report)
        return report

    async def deep_research(self, query: str, progress=None) -> str:
        def step(msg: str) -> None:
            if progress:
                progress(msg)

        step("🔎 Kaynaklar aranıyor…")
        hits = await web_search(query, 8)
        if not hits:
            return f"## 🕵️ Derin Araştırma: {query}\n\nSonuç bulunamadı."
        step(f"📥 {min(len(hits), 5)} sayfa indiriliyor…")
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
            pages = await asyncio.gather(*(fetch_page(client, h.url) for h in hits[:5]))
        corpus = []
        for i, (h, text) in enumerate(zip(hits[:5], pages), 1):
            content = text or h.snippet
            corpus.append(f"[Kaynak {i}] {h.title} ({h.url})\n{content[:3000]}")
        sources = _format_sources(hits[:5])

        report = None
        if self.engine:
            step("🧠 ENGINE raporu sentezliyor…")
            prompt = (
                f"Aşağıdaki web kaynaklarını kullanarak '{query}' konusunda Türkçe, yapılandırılmış bir "
                "araştırma raporu yaz. Başlıklar: Özet, Ana Bulgular, Farklı Görüşler/Riskler, Sonuç. "
                "Her iddiadan sonra [Kaynak N] biçiminde atıf yap. Reklam ve alakasız içeriği yok say.\n\n"
                + "\n\n".join(corpus)
            )
            try:
                reply = await self.engine.ask(prompt, size="small")
                report = f"{reply.text}\n\n*Model: {reply.label}*"
            except Exception as e:
                step(f"⚠️ ENGINE kullanılamadı: {e}")
        if report is None:
            report = "\n\n".join(
                f"### {h.title}\n{(t or h.snippet)[:700]}…" for h, t in zip(hits[:5], pages)
            )
        final = f"## 🕵️ Derin Araştırma: {query}\n\n{report}\n\n### 📚 Kaynaklar\n{sources}"
        await self._save(query, "derin", final)
        return final

    async def github_trends(self, topic: str = "ai-agents", days: int = 7, limit: int = 15) -> list[dict[str, Any]]:
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        q = f"{GITHUB_TOPICS.get(topic, topic)} created:>{since}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "4k-workstation"}
        if token := await asyncio.to_thread(_github_token):
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers=headers) as client:
            r = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": limit},
            )
        if r.status_code == 403:
            raise RuntimeError("GitHub API limiti doldu. `gh auth login` ile giriş yaparsanız limit artar.")
        r.raise_for_status()
        return [
            {
                "name": it["full_name"],
                "stars": it["stargazers_count"],
                "lang": it.get("language") or "-",
                "desc": (it.get("description") or "")[:120],
                "url": it["html_url"],
                "created": it["created_at"][:10],
            }
            for it in r.json().get("items", [])
        ]

    async def history(self, limit: int = 20) -> list[dict[str, Any]]:
        return await self.db.fetchall("SELECT id, ts, query, mode FROM searches ORDER BY id DESC LIMIT ?", (limit,))


def _github_token() -> str | None:
    if tok := os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return tok
    if shutil.which("gh"):
        try:
            out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=5)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None
