"""Hermes agent wrapper.

Runs the local Hermes agent (Nous Research) as a headless, one-shot CLI call:

    hermes chat --query-file - -Q --max-turns N --run-budget S

The prompt is passed on stdin via ``--query-file -`` so it is never
shell-interpreted (quotes, ``$(...)`` and backticks survive verbatim). ``-Q``
runs in quiet mode: no banner, spinner or tool previews, only the final
response.

Verified output contract (Hermes v0.22.2):
    stdout -> the final response, plain text
    stderr -> ``session_id: <id>`` (used for ``--resume``)

Configuration (environment variables):
    HERMES_BIN         Path to the hermes executable. Auto-detected if unset.
    HERMES_MODEL       Optional model override (``-m``).
    HERMES_TIMEOUT     Subprocess timeout in seconds. Default: 300
    HERMES_MAX_TURNS   Agent turn budget. Default: 6
    HERMES_RUN_BUDGET  Agent wall-clock budget in seconds. Default: 180

Note: ``--yolo`` is deliberately never used, so Hermes keeps asking for
approval instead of taking unattended, irreversible actions.
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
        """Locate the hermes executable, or return None if it is not installed."""
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
        """The argv used for a headless one-shot run."""
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
        """Split Hermes output into (response, session_id)."""
        if isinstance(stdout, (bytes, bytearray)):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, (bytes, bytearray)):
            stderr = stderr.decode("utf-8", errors="replace")

        match = SESSION_ID_RE.search(stderr or "")
        return (stdout or "").strip(), (match.group(1) if match else None)

    async def execute(self, prompt: str) -> str:
        if not self.binary:
            return (
                "Error: Hermes calistirilabilir dosyasi bulunamadi. "
                "Kuruluysa HERMES_BIN ortam degiskenini ayarlayin."
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
            return f"Error: Hermes baslatilamadi: {exc}"

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return f"Error: Hermes {self.timeout:.0f} saniyede yanit vermedi."

        response, session_id = self.parse_output(stdout, stderr)
        if session_id:
            self.last_session_id = session_id

        if not response:
            if process.returncode != 0:
                detail = (stderr or b"").decode("utf-8", errors="replace").strip()
                return f"Error: Hermes exit {process.returncode}: {detail[:200]}"
            return "Error: Hermes bos yanit dondurdu."

        return response

    async def check_quota(self) -> float:
        # Hermes uses the operator's own provider credentials; the gateway does
        # not model that quota itself.
        return 1.0
