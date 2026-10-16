"""Python arka ucunu PyInstaller ile tek klasörlük bir ikiliye paketler.

Çıktı: build/backend/4k-backend/  (electron-builder bunu `resources/backend` olarak kopyalar)
PyInstaller çapraz derleme yapamaz; her işletim sistemi kendi ikilisini üretmelidir.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "build" / "backend"
WORK = ROOT / "build" / "pyinstaller"
NAME = "4k-backend"

HIDDEN_IMPORTS = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "workstation.server",
]
COLLECT_ALL = ["ddgs", "google_auth_oauthlib"]
EXCLUDES = ["textual", "tkinter", "pytest"]


def main() -> int:
    # Windows konsolu varsayılan olarak cp1252 kullanır; ▶ ✓ ✗ gibi karakterler orada çöker.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    shutil.rmtree(DIST, ignore_errors=True)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(ROOT / "packaging" / "backend_entry.py"),
        "--name", NAME,
        "--onedir",
        "--noconfirm",
        "--clean",
        "--console",
        "--paths", str(ROOT / "src"),
        "--distpath", str(DIST),
        "--workpath", str(WORK),
        "--specpath", str(WORK),
    ]
    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    for pkg in COLLECT_ALL:
        cmd += ["--collect-all", pkg]
    # Özel kanca, googleapiclient'in tüm Google API tanımlarını (~110 MB) paketlemesini engeller.
    cmd += ["--additional-hooks-dir", str(ROOT / "packaging" / "hooks")]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    print("▶", " ".join(cmd), flush=True)
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc:
        return rc
    exe = DIST / NAME / (NAME + (".exe" if sys.platform == "win32" else ""))
    if not exe.exists():
        print(f"✗ Beklenen ikili bulunamadı: {exe}", file=sys.stderr)
        return 1
    print(f"✓ Arka uç hazır: {exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
