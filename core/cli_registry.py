"""Sistemde kurulu yapay zeka CLI araçlarını ve abonelik ajanlarını keşfeder.

Bu modül, kullanıcının bilgisayarında kurulu olan CLI araçlarını (Hermes,
Codex, Claude Code, OpenCode, Ollama, Antigravity, Cursor) otomatik tarar,
durumlarını raporlar ve çalışmaya hazır olanları Dispatcher + Router'a
kaydeder.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass

from core.dispatcher import Dispatcher
from core.router import IntelligentRouter
from wrappers.claude_code_wrapper import ClaudeCodeWrapper
from wrappers.codex_wrapper import CodexWrapper
from wrappers.hermes_wrapper import HermesWrapper
from wrappers.opencode_wrapper import OpenCodeWrapper


@dataclass
class CLIToolStatus:
    """Tek bir CLI aracının sistemdeki kurulum ve abonelik durumu."""

    name: str
    installed: bool
    binary_path: str | None
    subscription_type: str
    role: str
    strengths: list[str]
    install_hint: str

    def to_dict(self) -> dict:
        return asdict(self)


def _detect_ollama_binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidate = os.path.join(local, "Programs", "Ollama", "ollama.exe")
            if os.path.exists(candidate):
                return candidate
    return None


def _detect_agy_binary() -> str | None:
    for name in ("agy", "antigravity"):
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidate = os.path.join(local, "agy", "bin", "agy.exe")
            if os.path.exists(candidate):
                return candidate
    return None


def _detect_cursor_binary() -> str | None:
    found = shutil.which("cursor")
    if found:
        return found
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidate = os.path.join(
                local, "Programs", "cursor", "resources", "app", "bin", "cursor.cmd"
            )
            if os.path.exists(candidate):
                return candidate
    return None


def discover_cli_tools() -> list[CLIToolStatus]:
    """Bilgisayardaki tüm desteklenen AI CLI araçlarını tarar ve durumlarını döndürür."""
    ollama_bin = _detect_ollama_binary()
    hermes_bin = HermesWrapper.detect_binary()
    codex_bin = CodexWrapper.detect_binary()
    claude_bin = ClaudeCodeWrapper.detect_binary()
    opencode_bin = OpenCodeWrapper.detect_binary()
    agy_bin = _detect_agy_binary()
    cursor_bin = _detect_cursor_binary()

    return [
        CLIToolStatus(
            name="Ollama",
            installed=bool(ollama_bin),
            binary_path=ollama_bin,
            subscription_type="Ücretsiz / Yerel Çalışma Zamanı",
            role="Hızlı ve ücretsiz yerel LLM çıkarımı (llama3, qwen2.5-coder vb.)",
            strengths=["chat", "cheap", "local"],
            install_hint="winget install Ollama.Ollama",
        ),
        CLIToolStatus(
            name="Hermes",
            installed=bool(hermes_bin),
            binary_path=hermes_bin,
            subscription_type="Nous / OpenRouter / Yerel Proxy Ajanı",
            role="Headless ajan görevleri, çok adımlı araç kullanımı",
            strengths=["code", "agentic"],
            install_hint="Hermes kurulum paketi (%LOCALAPPDATA%\\hermes)",
        ),
        CLIToolStatus(
            name="Codex",
            installed=bool(codex_bin),
            binary_path=codex_bin,
            subscription_type="ChatGPT Plus / Pro / API Aboneliği",
            role="Kod inceleme, algoritma ve uygulama geliştirme (codex exec)",
            strengths=["code", "agentic"],
            install_hint="npm install -g @openai/codex veya OpenAI Codex masaüstü",
        ),
        CLIToolStatus(
            name="Claude",
            installed=bool(claude_bin),
            binary_path=claude_bin,
            subscription_type="Claude Pro / Max / Anthropic API Aboneliği",
            role="Karmaşık mimari tasarım, derin akıl yürütme ve kod yazımı (claude -p)",
            strengths=["code", "reasoning", "agentic"],
            install_hint="npm install -g @anthropic-ai/claude-code",
        ),
        CLIToolStatus(
            name="OpenCode",
            installed=bool(opencode_bin),
            binary_path=opencode_bin,
            subscription_type="OpenCode Sağlayıcıları / Çoklu Model Ajanı",
            role="Çoklu sağlayıcı üzerinden otonom kodlama ve düzenleme (opencode run)",
            strengths=["code", "agentic", "chat"],
            install_hint="OpenCode masaüstü uygulaması veya CLI",
        ),
        CLIToolStatus(
            name="Antigravity",
            installed=bool(agy_bin),
            binary_path=agy_bin,
            subscription_type="Google Antigravity Aboneliği",
            role="Gelişmiş otonom ajan geliştirme ortamı (agy)",
            strengths=["code", "reasoning", "agentic"],
            install_hint="Antigravity CLI (%LOCALAPPDATA%\\agy\\bin\\agy.exe)",
        ),
        CLIToolStatus(
            name="Cursor",
            installed=bool(cursor_bin),
            binary_path=cursor_bin,
            subscription_type="Cursor Pro / Ücretsiz",
            role="Yapay zeka destekli IDE ve kod editörü",
            strengths=["code"],
            install_hint="https://cursor.com",
        ),
    ]


def register_available_cli_wrappers(
    dispatcher: Dispatcher,
    router: IntelligentRouter,
) -> list[str]:
    """Sistemde kurulu olan CLI wrapper'larını Dispatcher ve Router'a kaydeder."""
    registered: list[str] = []

    cli_candidates = [
        ("Hermes", HermesWrapper(), 8, 0.02, False, ("code", "agentic")),
        ("Codex", CodexWrapper(), 8, 0.02, False, ("code", "agentic")),
        ("Claude", ClaudeCodeWrapper(), 10, 0.05, False, ("code", "reasoning", "agentic")),
        ("OpenCode", OpenCodeWrapper(), 8, 0.01, False, ("code", "agentic", "chat")),
    ]

    for name, wrapper, cap, cost, is_local, strengths in cli_candidates:
        if wrapper.is_available():
            dispatcher.register_wrapper(name, wrapper)
            router.register_tier(
                name,
                capability_score=cap,
                cost_per_token=cost,
                is_local=is_local,
                strengths=strengths,
            )
            registered.append(name)

    return registered
