"""🧠 4K AI ENGINE — donanım/sağlayıcı keşfi, 3 vitesli akıllı yönlendirici ve fallback sistemi."""

from __future__ import annotations

import asyncio
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import config
from .db import Database

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
QUOTA_RE = re.compile(
    r"(429|rate.?limit|quota|usage limit|too many requests|limit reached|kota|exceeded)", re.I
)
HEAVY_KEYWORDS = (
    "mimari", "architecture", "refactor", "kod yaz", "kodla", "debug", "hata ayıkla",
    "implement", "uygula", "tasarla", "design", "algoritma", "fizibilite", "analiz et",
    "test yaz", "optimize", "veritabanı şeması", "api", "class ", "def ", "function",
)
NON_CHAT_MODEL = re.compile(r"(embed|ocr|whisper|rerank|clip|vision-only)", re.I)


class ProviderError(Exception):
    def __init__(self, message: str, quota: bool = False) -> None:
        super().__init__(message)
        self.quota = quota


@dataclass
class Reply:
    text: str
    provider: str
    model: str
    gear: str
    tier: str
    attempts: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def label(self) -> str:
        return self.provider if not self.model or self.model in self.provider else f"{self.provider} {self.model}"


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Sağlayıcılar
# ---------------------------------------------------------------------------
class Provider(ABC):
    name: str
    model: str
    tier: str  # "local" | "free" | "subscription"
    strength: int = 1  # büyük işler için tercih sıralaması

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str: ...

    def label(self) -> str:
        return f"{self.name}:{self.model}" if self.model else self.name


class OllamaProvider(Provider):
    tier = "local"

    def __init__(self, model: str, size_gb: float, fits_gpu: bool) -> None:
        self.model = model
        self.size_gb = size_gb
        self.fits_gpu = fits_gpu
        self.name = f"ollama/{model}"
        # GPU'ya sığan modeller hızlıdır; sığmayanlar güçlü ama yavaştır.
        self.strength = int(size_gb) + (5 if fits_gpu else 0)

    def label(self) -> str:
        return self.name

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            async with httpx.AsyncClient(timeout=config.LOCAL_MODEL_TIMEOUT) as client:
                r = await client.post(
                    f"{config.OLLAMA_URL}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                )
        except httpx.TimeoutException as e:
            raise ProviderError(f"Ollama zaman aşımı ({self.model})") from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama bağlantı hatası: {e}") from e
        if r.status_code == 429:
            raise ProviderError("Ollama 429", quota=True)
        if r.status_code >= 400:
            raise ProviderError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        content = r.json().get("message", {}).get("content", "")
        return THINK_RE.sub("", content).strip()


class OpenAICompatProvider(Provider):
    tier = "free"

    def __init__(self, name: str, base_url: str, api_key: str, model: str, strength: int = 4) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.strength = strength

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages},
                )
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name} bağlantı hatası: {e}") from e
        if r.status_code == 429:
            raise ProviderError(f"{self.name} kota (429)", quota=True)
        if r.status_code >= 400:
            raise ProviderError(f"{self.name} HTTP {r.status_code}: {r.text[:200]}")
        return THINK_RE.sub("", r.json()["choices"][0]["message"]["content"]).strip()


@dataclass(frozen=True)
class CLISpec:
    name: str
    binary: str
    args: tuple[str, ...]  # "{prompt}" yer tutucusu içerir
    strength: int


CLI_AGENTS: tuple[CLISpec, ...] = (
    CLISpec("claude", "claude", ("-p", "{prompt}", "--output-format", "text"), 10),
    CLISpec("codex", "codex", ("exec", "--skip-git-repo-check", "{prompt}"), 9),
    CLISpec("antigravity", "agy", ("-p", "{prompt}"), 8),
    CLISpec("gemini", "gemini", ("-p", "{prompt}"), 8),
    CLISpec("grok", "grok", ("-p", "{prompt}"), 7),
    CLISpec("opencode", "opencode", ("run", "{prompt}"), 6),
)


class CLIProvider(Provider):
    tier = "subscription"

    def __init__(self, spec: CLISpec, path: str) -> None:
        self.spec = spec
        self.path = path
        self.name = spec.name
        self.model = ""
        self.strength = spec.strength

    async def complete(self, prompt: str, system: str | None = None) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        args = [a.replace("{prompt}", full) for a in self.spec.args]
        # Ajanlar çalışma dizinindeki dosyalara dokunmasın diye nötr bir dizinde çalıştırılır.
        cwd = config.HOME / "agent_sandbox"
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            proc = await asyncio.create_subprocess_exec(
                self.path, *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
            )
        except OSError as e:
            raise ProviderError(f"{self.name} başlatılamadı: {e}") from e
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=config.CLI_AGENT_TIMEOUT)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            await proc.wait()
            raise ProviderError(f"{self.name} zaman aşımı") from None
        stdout = out.decode(errors="replace").strip()
        stderr = err.decode(errors="replace").strip()
        if proc.returncode != 0:
            msg = (stderr or stdout)[-400:]
            raise ProviderError(f"{self.name} çıkış kodu {proc.returncode}: {msg}", quota=bool(QUOTA_RE.search(msg)))
        if not stdout:
            raise ProviderError(f"{self.name} boş yanıt döndürdü", quota=bool(QUOTA_RE.search(stderr)))
        return strip_ansi(stdout)


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


# ---------------------------------------------------------------------------
# Keşif
# ---------------------------------------------------------------------------
async def _run(cmd: list[str], timeout: float = config.DISCOVERY_TIMEOUT) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (asyncio.TimeoutError, OSError):
        return None
    return out.decode(errors="replace").strip() if proc.returncode == 0 else None


def _ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / 1024**3, 1)
    except Exception:
        return 0.0


def _cpu_name() -> str:
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass
    elif sys.platform == "darwin":
        try:
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3)
            if out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return platform.processor() or platform.machine()


async def discover_gpu() -> list[dict[str, Any]]:
    out = await _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"])
    gpus = []
    for line in (out or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            try:
                gpus.append({"name": parts[0], "vram_gb": round(int(parts[1]) / 1024, 1),
                             "used_gb": round(int(parts[2]) / 1024, 1)})
            except ValueError:
                continue
    return gpus


async def discover_ollama() -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=config.DISCOVERY_TIMEOUT) as client:
            r = await client.get(f"{config.OLLAMA_URL}/api/tags")
            r.raise_for_status()
    except (httpx.HTTPError, ValueError):
        return []
    return [
        {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)}
        for m in r.json().get("models", [])
    ]


def discover_cli_agents() -> list[tuple[CLISpec, str]]:
    found = []
    for spec in CLI_AGENTS:
        path = shutil.which(spec.binary)
        if path:
            found.append((spec, path))
    return found


def discover_free_apis() -> list[OpenAICompatProvider]:
    apis = []
    if key := os.environ.get("GROQ_API_KEY"):
        apis.append(OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", key,
                                         os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), 6))
    if key := os.environ.get("OPENROUTER_API_KEY"):
        apis.append(OpenAICompatProvider("openrouter", "https://openrouter.ai/api/v1", key,
                                         os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"), 5))
    if key := os.environ.get("GEMINI_API_KEY"):
        apis.append(OpenAICompatProvider("gemini-api", "https://generativelanguage.googleapis.com/v1beta/openai", key,
                                         os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), 7))
    return apis


# ---------------------------------------------------------------------------
# Yönlendirici
# ---------------------------------------------------------------------------
def classify_task(prompt: str) -> str:
    """'small' veya 'large' döndürür."""
    low = prompt.lower()
    if len(prompt) > 1200 or "```" in prompt:
        return "large"
    if any(k in low for k in HEAVY_KEYWORDS):
        return "large"
    return "small"


def compress_context(history: list[dict[str, str]], keep_last: int = 6, summary_chars: int = 1500) -> str:
    """Eski mesajları kısa özet satırlarına indirger, son N mesajı aynen korur."""
    if not history:
        return ""
    older, recent = history[:-keep_last], history[-keep_last:]
    parts = []
    if older:
        lines, used = [], 0
        for m in reversed(older):
            line = f"- {m['role']}: {m['content'][:160].replace(chr(10), ' ')}"
            if used + len(line) > summary_chars:
                break
            lines.append(line)
            used += len(line)
        parts.append("[Önceki konuşma özeti]\n" + "\n".join(reversed(lines)))
    parts.append("[Son mesajlar]\n" + "\n".join(f"{m['role']}: {m['content']}" for m in recent))
    return "\n\n".join(parts)


SYSTEM_PROMPT = (
    "Sen 4K AI WORKSTATION asistanısın. Kullanıcıya her zaman Türkçe, net ve uygulanabilir "
    "yanıtlar ver. Gerektiğinde Markdown kullan."
)


class Engine:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.providers: list[Provider] = []
        self.system: dict[str, Any] = {}
        self._discovered = False
        self._discover_lock = asyncio.Lock()

    # --- keşif ------------------------------------------------------------
    async def discover(self, force: bool = False) -> dict[str, Any]:
        async with self._discover_lock:
            if self._discovered and not force:
                return self.system
            gpus, models = await asyncio.gather(discover_gpu(), discover_ollama())
            vram = max((g["vram_gb"] for g in gpus), default=0.0)
            providers: list[Provider] = []
            for m in models:
                if NON_CHAT_MODEL.search(m["name"]):
                    continue
                providers.append(OllamaProvider(m["name"], m["size_gb"], fits_gpu=0 < m["size_gb"] <= vram * 1.05))
            providers.extend(discover_free_apis())
            for spec, path in discover_cli_agents():
                providers.append(CLIProvider(spec, path))
            self.providers = providers
            self.system = {
                "os": f"{platform.system()} {platform.release()}",
                "host": config.DEVICE_NAME,
                "cpu": _cpu_name(),
                "cores": os.cpu_count() or 0,
                "ram_gb": _ram_gb(),
                "gpus": gpus,
                "ollama_models": models,
                "ollama_online": bool(models),
                "cli_agents": [p.name for p in providers if p.tier == "subscription"],
                "free_apis": [p.name for p in providers if p.tier == "free"],
            }
            for p in providers:
                await self.db.execute(
                    "INSERT INTO providers(name, kind, available) VALUES(?,?,1) "
                    "ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, available=1",
                    (p.label(), p.tier),
                )
            self._discovered = True
            return self.system

    # --- vites ------------------------------------------------------------
    async def get_gear(self) -> str:
        gear = await self.db.get_setting("gear", config.DEFAULT_GEAR)
        return gear if gear in config.GEARS else config.DEFAULT_GEAR

    async def set_gear(self, gear: str) -> None:
        if gear not in config.GEARS:
            raise ValueError(f"Bilinmeyen vites: {gear}")
        await self.db.set_setting("gear", gear)

    async def _cooldowns(self) -> dict[str, float]:
        rows = await self.db.fetchall("SELECT name, cooldown_until FROM providers WHERE cooldown_until > ?", (time.time(),))
        return {r["name"]: r["cooldown_until"] for r in rows}

    async def cooldown_status(self) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT name, kind, cooldown_until, last_error FROM providers ORDER BY kind, name"
        )

    def plan_route(self, gear: str, size: str, cooling: set[str] | None = None) -> list[Provider]:
        """Vitese ve iş boyutuna göre sağlayıcı sırasını belirler."""
        cooling = cooling or set()
        live = [p for p in self.providers if p.label() not in cooling]
        local_fast = sorted([p for p in live if p.tier == "local" and getattr(p, "fits_gpu", False)],
                            key=lambda p: p.strength, reverse=(size == "large"))
        local_slow = sorted([p for p in live if p.tier == "local" and not getattr(p, "fits_gpu", False)],
                            key=lambda p: p.strength, reverse=True)
        local = local_fast + local_slow
        free = sorted([p for p in live if p.tier == "free"], key=lambda p: p.strength, reverse=True)
        subs = sorted([p for p in live if p.tier == "subscription"], key=lambda p: p.strength, reverse=True)

        if gear == "ekonomik":
            return local + free
        if gear == "tam":
            return subs + free + local
        # dengeli
        if size == "large":
            return subs + free + local
        return local + free + subs

    async def _record(self, provider: Provider, prompt: str, text: str, project_id: int | None) -> None:
        await self.db.execute(
            "INSERT INTO usage(ts, provider, model, tokens_in, tokens_out, cost_usd, project_id) VALUES(?,?,?,?,?,?,?)",
            (time.time(), provider.name, provider.model, estimate_tokens(prompt), estimate_tokens(text), 0.0, project_id),
        )

    async def _fail(self, provider: Provider, err: ProviderError) -> None:
        until = time.time() + config.COOLDOWN_SECONDS
        await self.db.execute(
            "UPDATE providers SET cooldown_until=?, last_error=? WHERE name=?",
            (until, str(err)[:300], provider.label()),
        )

    async def ask(
        self,
        prompt: str,
        history: list[dict[str, str]] | None = None,
        size: str | None = None,
        gear: str | None = None,
        system: str | None = SYSTEM_PROMPT,
        project_id: int | None = None,
    ) -> Reply:
        await self.discover()
        gear = gear or await self.get_gear()
        size = size or classify_task(prompt)
        context = compress_context(history or [])
        full_prompt = f"{context}\n\n[Yeni mesaj]\n{prompt}" if context else prompt
        route = self.plan_route(gear, size, set((await self._cooldowns()).keys()))
        if not route:
            raise ProviderError(
                "Kullanılabilir model yok. Ollama'yı başlatın (`ollama serve`) veya bir CLI ajanı kurun"
                + (" ya da vitesi yükseltin." if gear == "ekonomik" else ".")
            )
        attempts: list[str] = []
        start = time.monotonic()
        for provider in route:
            try:
                text = await provider.complete(full_prompt, system=system)
            except ProviderError as e:
                attempts.append(f"{provider.label()} ✗ {e}")
                await self._fail(provider, e)
                continue
            await self._record(provider, full_prompt, text, project_id)
            return Reply(text=text, provider=provider.name, model=provider.model, gear=gear,
                         tier=provider.tier, attempts=attempts, elapsed=time.monotonic() - start)
        raise ProviderError("Tüm modeller başarısız oldu:\n" + "\n".join(attempts))

    async def chat(self, message: str) -> Reply:
        rows = await self.db.fetchall("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT 30")
        history = list(reversed(rows))
        await self.db.execute("INSERT INTO chat_history(ts, role, content) VALUES(?,?,?)",
                              (time.time(), "user", message))
        reply = await self.ask(message, history=history)
        await self.db.execute("INSERT INTO chat_history(ts, role, content, provider) VALUES(?,?,?,?)",
                              (time.time(), "assistant", reply.text, reply.provider))
        return reply

    async def clear_chat(self) -> None:
        await self.db.execute("DELETE FROM chat_history")

    async def reset_cooldowns(self) -> None:
        await self.db.execute("UPDATE providers SET cooldown_until=0, last_error=NULL")
