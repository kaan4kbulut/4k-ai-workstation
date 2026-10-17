"""OpenCode CLI sarmalayıcısı.

OpenCode CLI'ın etkileşimsiz (headless) alt komutu:

    opencode-cli run --format default "<prompt>"

Sistemde kurulu ``opencode`` / ``opencode-cli.exe`` yürütülebilir dosyasını
otomatik bulur ve yanıtı ``stdout`` üzerinden döndürür.
"""

from __future__ import annotations

import asyncio
import glob
import os
import shutil

from .base_wrapper import BaseWrapper


class OpenCodeWrapper(BaseWrapper):
    """Yerel ``opencode`` / ``opencode-cli`` aracını tek seferlik çalıştırır."""

    def __init__(
        self,
        binary: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        super().__init__("OpenCode")
        self.binary = binary or self.detect_binary()
        self.model = model or os.environ.get("OPENCODE_MODEL")
        self.timeout = float(timeout or os.environ.get("OPENCODE_TIMEOUT", "180"))

    @staticmethod
    def detect_binary() -> str | None:
        """Sistemde kurulu ``opencode`` / ``opencode-cli`` ikilisini bulur."""
        explicit = os.environ.get("OPENCODE_BIN")
        if explicit and os.path.exists(explicit):
            return explicit

        for cmd_name in ("opencode", "opencode-cli"):
            found = shutil.which(cmd_name)
            if found:
                return found

        candidates: list[str] = []
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA", "")
            roaming = os.environ.get("APPDATA", "")
            if local:
                candidates.append(
                    os.path.join(local, "Programs", "@opencodedesktop", "resources", "opencode-cli.exe")
                )
            if roaming:
                candidates.extend(
                    sorted(
                        glob.glob(
                            os.path.join(roaming, "ai.opencode.desktop", "cli", "*", "opencode-cli.exe")
                        ),
                        reverse=True,
                    )
                )
                candidates.append(os.path.join(roaming, "npm", "opencode.cmd"))
        candidates += [
            os.path.expanduser("~/.local/bin/opencode"),
            "/usr/local/bin/opencode",
            "/usr/bin/opencode",
        ]
        return next((c for c in candidates if os.path.exists(c)), None)

    def is_available(self) -> bool:
        return bool(self.binary)

    def build_command(self, prompt: str) -> list[str]:
        command = [
            self.binary or "opencode",
            "run",
            "--format",
            "default",
        ]
        if self.model:
            command += ["-m", self.model]
        command.append(prompt)
        return command

    @staticmethod
    def parse_output(stdout: bytes | str, stderr: bytes | str) -> str:
        if isinstance(stdout, (bytes, bytearray)):
            stdout = stdout.decode("utf-8", errors="replace")
        return (stdout or "").strip()

    async def execute(self, prompt: str) -> str:
        if not self.binary:
            return (
                "Hata: OpenCode CLI bulunamadı. "
                "Kuruluysa OPENCODE_BIN ortam değişkenini ayarlayın."
            )

        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        # SIFIR HARCAMA KİLİDİ: Ücretli API anahtarlarını CLI ortamından temizle ($0.00 Kalkanı)
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
            env.pop(key, None)

        try:
            cwd = getattr(self, "workspace", None)
            process = await asyncio.create_subprocess_exec(
                *self.build_command(prompt),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd if cwd and os.path.isdir(cwd) else None,
            )
        except OSError as exc:
            return f"Hata: OpenCode başlatılamadı: {exc}"

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Hata: OpenCode {self.timeout:.0f} saniyede yanıt vermedi."

        response = self.parse_output(stdout, stderr)
        if not response:
            if process.returncode != 0:
                detail = (stderr or b"").decode("utf-8", errors="replace").strip()
                return f"Hata: OpenCode exit {process.returncode}: {detail[:200]}"
            return "Hata: OpenCode boş yanıt döndürdü."

        return response

    async def check_quota(self) -> float:
        return 1.0
