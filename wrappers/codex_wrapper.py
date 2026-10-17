"""OpenAI Codex CLI (ChatGPT aboneliği / API ile çalışan kod ajanı) sarmalayıcısı.

Codex CLI'ın etkileşimsiz (headless) alt komutu:

    codex exec -s read-only --skip-git-repo-check --ephemeral -

Prompt ``stdin`` üzerinden UTF-8 olarak gönderilir, böylece kabuk (shell)
kaçış/tırnak sorunları yaşanmaz. Son yanıt ``-o <dosya>`` veya ``stdout``
üzerinden güvenli biçimde okunur.
"""

from __future__ import annotations

import asyncio
import glob
import os
import shutil
import tempfile

from .base_wrapper import BaseWrapper


class CodexWrapper(BaseWrapper):
    """Yerel ``codex`` CLI'ını tek seferlik (non-interactive) modda çalıştırır."""

    def __init__(
        self,
        binary: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        sandbox: str = "read-only",
    ):
        super().__init__("Codex")
        self.binary = binary or self.detect_binary()
        self.model = model or os.environ.get("CODEX_MODEL")
        self.timeout = float(timeout or os.environ.get("CODEX_TIMEOUT", "180"))
        self.sandbox = sandbox

    @staticmethod
    def detect_binary() -> str | None:
        """Sistemde kurulu ``codex`` yürütülebilir dosyasını bulur."""
        explicit = os.environ.get("CODEX_BIN")
        if explicit and os.path.exists(explicit):
            return explicit

        found = shutil.which("codex")
        if found:
            return found

        candidates: list[str] = []
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA", "")
            roaming = os.environ.get("APPDATA", "")
            userprofile = os.environ.get("USERPROFILE", "")
            if local:
                candidates.append(
                    os.path.join(local, "Programs", "OpenAI", "Codex", "bin", "codex.exe")
                )
                candidates.extend(
                    sorted(
                        glob.glob(os.path.join(local, "OpenAI", "Codex", "bin", "*", "codex.exe")),
                        reverse=True,
                    )
                )
            if roaming:
                candidates.append(os.path.join(roaming, "npm", "codex.cmd"))
            if userprofile:
                candidates.append(
                    os.path.join(userprofile, ".codex", "plugins", ".plugin-appserver", "codex.exe")
                )
        candidates += [
            os.path.expanduser("~/.local/bin/codex"),
            "/usr/local/bin/codex",
            "/usr/bin/codex",
        ]
        return next((c for c in candidates if os.path.exists(c)), None)

    def is_available(self) -> bool:
        return bool(self.binary)

    def build_command(self, output_file: str | None = None) -> list[str]:
        """Headless ``codex exec`` çalıştırması için argüman listesini üretir."""
        command = [
            self.binary or "codex",
            "exec",
            "-s",
            self.sandbox,
            "--skip-git-repo-check",
            "--ephemeral",
            "--color",
            "never",
        ]
        if self.model:
            command += ["-m", self.model]
        if output_file:
            command += ["-o", output_file]
        command.append("-")
        return command

    @staticmethod
    def parse_output(
        stdout: bytes | str,
        stderr: bytes | str,
        last_message_text: str | None = None,
    ) -> str:
        """Codex çıktısından son mesajı ayıklar."""
        if last_message_text and last_message_text.strip():
            return last_message_text.strip()
        if isinstance(stdout, (bytes, bytearray)):
            stdout = stdout.decode("utf-8", errors="replace")
        return (stdout or "").strip()

    async def execute(self, prompt: str) -> str:
        if not self.binary:
            return (
                "Hata: Codex CLI bulunamadı. "
                "Kuruluysa CODEX_BIN ortam değişkenini ayarlayın."
            )

        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        # SIFIR HARCAMA KİLİDİ: Ücretli API anahtarlarını CLI ortamından temizle ($0.00 Kalkanı)
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
            env.pop(key, None)

        fd, out_path = tempfile.mkstemp(prefix="nexus_codex_", suffix=".txt")
        os.close(fd)

        try:
            try:
                cwd = getattr(self, "workspace", None)
                process = await asyncio.create_subprocess_exec(
                    *self.build_command(output_file=out_path),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=cwd if cwd and os.path.isdir(cwd) else None,
                )
            except OSError as exc:
                return f"Hata: Codex başlatılamadı: {exc}"

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(prompt.encode("utf-8")),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return f"Hata: Codex {self.timeout:.0f} saniyede yanıt vermedi."

            if process.returncode != 0:
                return f"Hata: Codex exit {process.returncode}."

            last_msg = None
            if os.path.exists(out_path):
                try:
                    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                        last_msg = f.read()
                except Exception:
                    last_msg = None

            response = self.parse_output(stdout, stderr, last_msg)
            if not response:
                return "Hata: Codex boş yanıt döndürdü."

            return response
        finally:
            try:
                if os.path.exists(out_path):
                    os.unlink(out_path)
            except Exception:
                pass

    async def check_quota(self) -> float:
        return 1.0
