"""Yollar, sabitler ve zaman aşımı değerleri. Hiçbir ayar zorunlu değildir (Zero-Config)."""

from __future__ import annotations

import os
import socket
from pathlib import Path

APP_NAME = "4K AI WORKSTATION"
APP_VERSION = "v1.0"

HOME = Path(os.environ.get("FOURK_HOME", Path.home() / ".4k")).expanduser()
DB_PATH = HOME / "4k_workstation_state.db"
PROJECTS_DIR = Path(os.environ.get("FOURK_PROJECTS", HOME / "projects")).expanduser()
BACKUP_DIR = HOME / "backups"
GOOGLE_CLIENT_SECRET = HOME / "client_secret.json"
GOOGLE_TOKEN = HOME / "google_token.json"

DEVICE_NAME = socket.gethostname()

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = f"http://{OLLAMA_URL}"

# Zaman aşımları (saniye)
DISCOVERY_TIMEOUT = 5.0
HTTP_TIMEOUT = 10.0
LOCAL_MODEL_TIMEOUT = 180.0
CLI_AGENT_TIMEOUT = 300.0

COOLDOWN_SECONDS = 30 * 60

API_PORT = int(os.environ.get("FOURK_API_PORT", "8765"))

GEARS = {
    "ekonomik": "🟢 Ekonomik",
    "dengeli": "🔵 Dengeli",
    "tam": "🔴 Tam Güç",
}
DEFAULT_GEAR = "dengeli"


def ensure_dirs() -> None:
    for d in (HOME, PROJECTS_DIR, BACKUP_DIR):
        d.mkdir(parents=True, exist_ok=True)
