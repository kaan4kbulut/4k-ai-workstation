"""Anthropic Claude Code CLI (Claude Pro/Max aboneliği veya API) sarmalayıcısı.

Claude Code CLI'ın etkileşimsiz (headless) komutu:

    claude -p --output-format text

Prompt ``stdin`` üzerinden UTF-8 olarak iletilir ve saf metin yanıt ``stdout``
üzerinden okunur.
"""

from __future__ import annotations

import asyncio
import os
import shutil

from .base_wrapper import BaseWrapper


class ClaudeCodeWrapper(BaseWrapper):
    """Yerel ``claude`` (Claude Code CLI) aracını headless modda çalıştırır."""

    def __init__(
        self,
        binary: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_turns: int | None = None,
    ):
        super().__init__("Claude")
        self.binary = binary or self.detect_binary()
        self.model = model or os.environ.get("CLAUDE_MODEL")
        self.timeout = float(timeout or os.environ.get("CLAUDE_TIMEOUT", "180"))
        self.max_turns = int(max_turns) if max_turns else None

    @staticmethod
    def detect_binary() -> str | None:
        """Sistemde kurulu ``claude`` CLI yürütülebilir dosyasını bulur."""
        explicit = os.environ.get("CLAUDE_BIN")
        if explicit and os.path.exists(explicit):
            return explicit

        for cmd_name in ("claude", "claude-code"):
            found = shutil.which(cmd_name)
            if found:
                return found

        candidates: list[str] = []
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA", "")
            roaming = os.environ.get("APPDATA", "")
            userprofile = os.environ.get("USERPROFILE", "")
            if roaming:
                candidates += [
                    os.path.join(roaming, "npm", "claude.cmd"),
                    os.path.join(roaming, "npm", "claude.exe"),
                ]
            if local:
                candidates += [
                    os.path.join(local, "Programs", "claude", "claude.exe"),
                    os.path.join(local, "AnthropicClaude", "claude.exe"),
                ]
            if userprofile:
                candidates += [
                    os.path.join(userprofile, ".local", "bin", "claude.exe"),
                    os.path.join(userprofile, ".claude", "local", "claude.exe"),
                ]
        candidates += [
            os.path.expanduser("~/.local/bin/claude"),
            os.path.expanduser("~/.claude/local/claude"),
            "/usr/local/bin/claude",
            "/usr/bin/claude",
        ]
        return next((c for c in candidates if os.path.exists(c)), None)

    def is_available(self) -> bool:
        return bool(self.binary)

    def build_command(self) -> list[str]:
        """Headless ``claude -p`` çalıştırması için argüman listesini üretir."""
        command = [
            self.binary or "claude",
            "-p",
            "--output-format",
            "text",
        ]
        if self.model:
            command += ["--model", self.model]
        if self.max_turns:
            command += ["--max-turns", str(self.max_turns)]
        return command

    @staticmethod
    def parse_output(stdout: bytes | str, stderr: bytes | str) -> str:
        if isinstance(stdout, (bytes, bytearray)):
            stdout = stdout.decode("utf-8", errors="replace")
        return (stdout or "").strip()

    async def execute(self, prompt: str) -> str:
        if not self.binary:
            return (
                "Hata: Claude Code CLI bulunamadı. "
                "Kurmak için 'npm install -g @anthropic-ai/claude-code' çalıştırın "
                "veya CLAUDE_BIN ortam değişkenini ayarlayın."
            )

        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        # SIFIR HARCAMA KİLİDİ: Ücretli API anahtarlarını CLI ortamından temizle ($0.00 Kalkanı)
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
            env.pop(key, None)

        try:
            cwd = getattr(self, "workspace", None)
            process = await asyncio.create_subprocess_exec(
                *self.build_command(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd if cwd and os.path.isdir(cwd) else None,
            )
        except OSError as exc:
            return f"Hata: Claude Code başlatılamadı: {exc}"

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Hata: Claude Code {self.timeout:.0f} saniyede yanıt vermedi."

        response = self.parse_output(stdout, stderr)
        if not response:
            if process.returncode != 0:
                detail = (stderr or b"").decode("utf-8", errors="replace").strip()
                return f"Hata: Claude Code exit {process.returncode}: {detail[:200]}"
            return "Hata: Claude Code boş yanıt döndürdü."

        return response

    async def check_quota(self) -> float:
        return 1.0
