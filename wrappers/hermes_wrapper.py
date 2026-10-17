"""Hermes ajanı wrapper'ı.

Yerel Hermes ajanını (Nous Research) headless, tek seferlik bir CLI çağrısı
olarak çalıştırır:

    hermes chat --query-file - -Q --max-turns N --run-budget S

İstek, `--query-file -` ile stdin üzerinden verilir; böylece shell tarafından
yorumlanmaz (tırnaklar, `$(...)` ve backtick'ler aynen korunur). `-Q` sessiz
moddur: banner, spinner veya araç önizlemesi yok; yalnızca final yanıt gelir.

Doğrulanan çıktı sözleşmesi (Hermes v0.22.2):
    stdout -> final yanıt, düz metin
    stderr -> ``session_id: <id>`` (``--resume`` için kullanılır)

Yapılandırma (ortam değişkenleri):
    HERMES_BIN         hermes çalıştırılabilir dosyasının yolu. Boşsa otomatik bulunur.
    HERMES_MODEL       İsteğe bağlı model geçersiz kılma (``-m``).
    HERMES_TIMEOUT     Alt süreç zaman aşımı (saniye). Varsayılan: 300
    HERMES_MAX_TURNS   Ajan tur bütçesi. Varsayılan: 6
    HERMES_RUN_BUDGET  Ajan toplam süre bütçesi (saniye). Varsayılan: 180

Not: ``--yolo`` bilinçli olarak asla kullanılmaz; böylece Hermes gözetimsiz,
geri dönüşsüz işlemler yapmak yerine onay sormaya devam eder.
"""

import asyncio
import os
import re
import shutil

from .base_wrapper import BaseWrapper

SESSION_ID_RE = re.compile(r"session_id:\s*(\S+)")


class HermesWrapper(BaseWrapper):
    def __init__(
        self,
        name: str = "Hermes",
        binary: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_turns: int | None = None,
        run_budget: int | None = None,
    ):
        super().__init__(name)
        self.binary = binary or self.detect_binary()
        self.model = model or os.environ.get("HERMES_MODEL") or None
        self.timeout = float(timeout or os.environ.get("HERMES_TIMEOUT", "300"))
        self.max_turns = int(max_turns or os.environ.get("HERMES_MAX_TURNS", "6"))
        self.run_budget = int(run_budget or os.environ.get("HERMES_RUN_BUDGET", "180"))
        self.last_session_id: str | None = None

    @staticmethod
    def detect_binary() -> str | None:
        """hermes çalıştırılabilir dosyasını bulur; kurulu değilse None döndürür."""
        explicit = os.environ.get("HERMES_BIN")
        if explicit and os.path.exists(explicit):
            return explicit

        found = shutil.which("hermes")
        if found:
            return found

        candidates = []
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA")
            if local:
                candidates += [
                    os.path.join(local, "hermes", "bin", "hermes.exe"),
                    os.path.join(local, "hermes", "bin", "hermes.cmd"),
                ]
        candidates += [
            os.path.expanduser("~/.local/bin/hermes"),
            "/usr/local/bin/hermes",
            "/usr/bin/hermes",
        ]
        return next((c for c in candidates if os.path.exists(c)), None)

    def is_available(self) -> bool:
        return bool(self.binary)

    def build_command(self) -> list[str]:
        """Headless tek seferlik çalıştırma için argv listesi."""
        command = [
            self.binary,
            "chat",
            "--query-file",
            "-",
            "-Q",
            "--max-turns",
            str(self.max_turns),
            "--run-budget",
            str(self.run_budget),
        ]
        if self.model:
            command += ["-m", self.model]
        return command

    @staticmethod
    def parse_output(stdout: bytes | str, stderr: bytes | str) -> tuple[str, str | None]:
        """Hermes çıktısını (yanıt, session_id) olarak ayırır."""
        if isinstance(stdout, (bytes, bytearray)):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, (bytes, bytearray)):
            stderr = stderr.decode("utf-8", errors="replace")

        match = SESSION_ID_RE.search(stderr or "")
        return (stdout or "").strip(), (match.group(1) if match else None)

    async def execute(self, prompt: str) -> str:
        if not self.binary:
            return (
                "Hata: Hermes çalıştırılabilir dosyası bulunamadı. "
                "Kuruluysa HERMES_BIN ortam değişkenini ayarlayın."
            )

        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            process = await asyncio.create_subprocess_exec(
                *self.build_command(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            return f"Hata: Hermes başlatılamadı: {exc}"

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Hata: Hermes {self.timeout:.0f} saniyede yanıt vermedi."

        response, session_id = self.parse_output(stdout, stderr)
        if session_id:
            self.last_session_id = session_id

        if not response:
            if process.returncode != 0:
                detail = (stderr or b"").decode("utf-8", errors="replace").strip()
                return f"Hata: Hermes exit {process.returncode}: {detail[:200]}"
            return "Hata: Hermes boş yanıt döndürdü."

        return response

    async def check_quota(self) -> float:
        # Hermes, kullanıcının kendi sağlayıcı kimlik bilgilerini kullanır;
        # geçit bu kotayı kendisi modellemez.
        return 1.0
