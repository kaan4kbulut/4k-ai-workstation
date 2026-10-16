"""🔄 4K AI SYNC — Tailscale cihaz ağı, uzaktan erişim API'si ve Google Drive bulut yedekleme."""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import json
import secrets
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import config
from .db import Database

if TYPE_CHECKING:
    from .workstation import Workstation

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_FOLDER = "4K_Workstation"


# ---------------------------------------------------------------------------
# Tailscale
# ---------------------------------------------------------------------------
async def tailscale_status() -> dict[str, Any]:
    if not shutil.which("tailscale"):
        return {"installed": False, "running": False, "self": None, "nodes": []}
    try:
        proc = await asyncio.create_subprocess_exec(
            "tailscale", "status", "--json",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=config.DISCOVERY_TIMEOUT)
        data = json.loads(out or b"{}")
    except (asyncio.TimeoutError, OSError, json.JSONDecodeError):
        return {"installed": True, "running": False, "self": None, "nodes": []}

    def node(n: dict[str, Any], is_self: bool = False) -> dict[str, Any]:
        ips = n.get("TailscaleIPs") or []
        return {
            "name": n.get("HostName") or n.get("DNSName", "?").split(".")[0],
            "ip": next((ip for ip in ips if "." in ip), ips[0] if ips else "-"),
            "os": n.get("OS", "?"),
            "online": bool(n.get("Online")) or is_self,
            "last_seen": "şimdi" if is_self or n.get("Online") else (n.get("LastSeen") or "-")[:16].replace("T", " "),
            "self": is_self,
        }

    me = node(data["Self"], True) if data.get("Self") else None
    nodes = ([me] if me else []) + [node(p) for p in (data.get("Peer") or {}).values()]
    return {
        "installed": True,
        "running": data.get("BackendState") == "Running",
        "self": me,
        "nodes": nodes,
    }


async def refresh_nodes(db: Database) -> dict[str, Any]:
    status = await tailscale_status()
    for n in status["nodes"]:
        await db.execute(
            "INSERT INTO nodes(name, ip, os, online, last_seen) VALUES(?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET ip=excluded.ip, os=excluded.os, online=excluded.online, "
            "last_seen=excluded.last_seen",
            (n["name"], n["ip"], n["os"], int(n["online"]), n["last_seen"]),
        )
    return status


# ---------------------------------------------------------------------------
# Yerel yedekleme paketi
# ---------------------------------------------------------------------------
def build_backup_archive(db: Database, dest_dir: Path | None = None) -> Path:
    """DB anlık görüntüsü + projeler klasörünü tek bir .tar.gz paketine koyar."""
    dest_dir = dest_dir or config.BACKUP_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = dest_dir / f"4k-backup-{config.DEVICE_NAME}-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        snap = db.snapshot_sync(Path(tmp) / config.DB_PATH.name)
        manifest = {"device": config.DEVICE_NAME, "created": stamp, "version": config.APP_VERSION,
                    "projects_dir": str(config.PROJECTS_DIR)}
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(snap, arcname=config.DB_PATH.name)
            data = json.dumps(manifest, ensure_ascii=False).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            if config.PROJECTS_DIR.exists():
                tar.add(config.PROJECTS_DIR, arcname="projects")
    return archive


def restore_backup_archive(db: Database, archive: Path) -> dict[str, Any]:
    """Paketi açar; mevcut projeler klasörünün üzerine yazmadan önce yedeğini alır."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp_path, filter="data")
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        db_file = tmp_path / config.DB_PATH.name
        if not db_file.exists():
            raise RuntimeError("Yedek paketinde veritabanı yok")
        # Geri yüklemeden önce mevcut durumu güvenceye al.
        build_backup_archive(db, config.BACKUP_DIR / "pre-restore")
        db.restore_from_sync(db_file)
        src_projects = tmp_path / "projects"
        if src_projects.exists():
            if config.PROJECTS_DIR.exists():
                shutil.rmtree(config.PROJECTS_DIR)
            shutil.copytree(src_projects, config.PROJECTS_DIR, symlinks=True)
        # Proje yolları başka cihazdan geliyorsa yeni konuma eşle.
        old_root = manifest.get("projects_dir")
        if old_root and old_root != str(config.PROJECTS_DIR):
            db.execute_sync("UPDATE projects SET repo_path=REPLACE(repo_path, ?, ?)", (old_root, str(config.PROJECTS_DIR)))
            db.execute_sync("UPDATE tickets SET worktree_path=REPLACE(worktree_path, ?, ?)", (old_root, str(config.PROJECTS_DIR)))
    return manifest


def list_local_backups() -> list[Path]:
    return sorted(config.BACKUP_DIR.glob("4k-backup-*.tar.gz"), reverse=True)


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------
GOOGLE_SETUP_HELP = f"""### Google Drive senkronizasyonu yapılandırılmadı

1. https://console.cloud.google.com/ → yeni proje oluşturun.
2. **APIs & Services → Library** bölümünden **Google Drive API**'yi etkinleştirin.
3. **OAuth consent screen**'i (External, test kullanıcısı olarak kendi hesabınız) ayarlayın.
4. **Credentials → Create credentials → OAuth client ID → Desktop app** seçin.
5. İndirilen JSON dosyasını şuraya kaydedin:
   `{config.GOOGLE_CLIENT_SECRET}`
6. Bu sekmede **🔑 Google ile Bağlan** butonuna basın; tarayıcıda izin verin.

Yalnızca uygulamanın kendi oluşturduğu dosyalara erişim (`drive.file`) istenir.
"""


class GoogleDrive:
    def __init__(self) -> None:
        self._service = None

    @staticmethod
    def configured() -> bool:
        return config.GOOGLE_CLIENT_SECRET.exists()

    @staticmethod
    def connected() -> bool:
        return config.GOOGLE_TOKEN.exists()

    def _credentials(self, interactive: bool):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if config.GOOGLE_TOKEN.exists():
            creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN), DRIVE_SCOPES)
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif interactive:
            if not self.configured():
                raise RuntimeError("client_secret.json bulunamadı")
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(str(config.GOOGLE_CLIENT_SECRET), DRIVE_SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300)
        else:
            raise RuntimeError("Google hesabı bağlı değil")
        config.GOOGLE_TOKEN.write_text(creds.to_json())
        config.GOOGLE_TOKEN.chmod(0o600)
        return creds

    def connect_sync(self) -> str:
        creds = self._credentials(interactive=True)
        self._service = None
        svc = self._drive(creds)
        about = svc.about().get(fields="user(emailAddress)").execute()
        return about["user"]["emailAddress"]

    def disconnect(self) -> None:
        config.GOOGLE_TOKEN.unlink(missing_ok=True)
        self._service = None

    def _drive(self, creds=None):
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("drive", "v3", credentials=creds or self._credentials(False), cache_discovery=False)
        return self._service

    def _folder_id(self) -> str:
        svc = self._drive()
        q = f"name='{DRIVE_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        found = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
        if found:
            return found[0]["id"]
        meta = {"name": DRIVE_FOLDER, "mimeType": "application/vnd.google-apps.folder"}
        return svc.files().create(body=meta, fields="id").execute()["id"]

    def upload_sync(self, archive: Path) -> str:
        from googleapiclient.http import MediaFileUpload

        svc = self._drive()
        media = MediaFileUpload(str(archive), mimetype="application/gzip", resumable=True)
        meta = {"name": archive.name, "parents": [self._folder_id()]}
        return svc.files().create(body=meta, media_body=media, fields="id").execute()["id"]

    def list_backups_sync(self) -> list[dict[str, Any]]:
        svc = self._drive()
        q = f"'{self._folder_id()}' in parents and trashed=false and name contains '4k-backup-'"
        return svc.files().list(q=q, orderBy="createdTime desc", pageSize=50,
                                fields="files(id,name,size,createdTime)").execute().get("files", [])

    def download_sync(self, file_id: str, dest: Path) -> Path:
        from googleapiclient.http import MediaIoBaseDownload

        svc = self._drive()
        request = svc.files().get_media(fileId=file_id)
        with open(dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return dest


class SyncManager:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.drive = GoogleDrive()
        self.last_status: dict[str, Any] = {}

    async def refresh(self) -> dict[str, Any]:
        self.last_status = await refresh_nodes(self.db)
        return self.last_status

    def cloud_state(self) -> str:
        if self.drive.connected():
            return "bağlı"
        if self.drive.configured():
            return "hazır (giriş bekliyor)"
        return "yapılandırılmadı"

    async def connect_google(self) -> str:
        email = await asyncio.wait_for(asyncio.to_thread(self.drive.connect_sync), timeout=320)
        await self.db.set_setting("google_email", email)
        await self.db.log_sync("google-bağlan", "ok", email)
        return email

    async def disconnect_google(self) -> None:
        self.drive.disconnect()
        await self.db.set_setting("google_email", "")

    async def backup(self, cloud: bool = True) -> dict[str, Any]:
        archive = await asyncio.to_thread(build_backup_archive, self.db)
        result: dict[str, Any] = {"local": str(archive), "cloud": None}
        if cloud and self.drive.connected():
            try:
                result["cloud"] = await asyncio.wait_for(asyncio.to_thread(self.drive.upload_sync, archive), timeout=600)
            except Exception as e:
                await self.db.log_sync("yedekle", "hata", str(e))
                raise RuntimeError(f"Yerel yedek alındı ({archive.name}) ama buluta yüklenemedi: {e}") from e
        await self.db.set_setting("last_backup", str(time.time()))
        await self.db.log_sync("yedekle", "ok", f"{archive.name} bulut={'evet' if result['cloud'] else 'hayır'}")
        return result

    async def cloud_backups(self) -> list[dict[str, Any]]:
        if not self.drive.connected():
            return []
        return await asyncio.to_thread(self.drive.list_backups_sync)

    async def restore_latest(self) -> dict[str, Any]:
        """Önce buluttaki, yoksa yereldeki en yeni yedeği geri yükler."""
        if self.drive.connected():
            files = await self.cloud_backups()
            if files:
                tmp = Path(tempfile.mkdtemp()) / files[0]["name"]
                await asyncio.to_thread(self.drive.download_sync, files[0]["id"], tmp)
                manifest = await asyncio.to_thread(restore_backup_archive, self.db, tmp)
                shutil.rmtree(tmp.parent, ignore_errors=True)
                await self.db.log_sync("geri-yükle", "ok", f"bulut: {files[0]['name']}")
                return {"source": "bulut", "name": files[0]["name"], **manifest}
        local = list_local_backups()
        if not local:
            raise RuntimeError("Geri yüklenecek yedek bulunamadı")
        manifest = await asyncio.to_thread(restore_backup_archive, self.db, local[0])
        await self.db.log_sync("geri-yükle", "ok", f"yerel: {local[0].name}")
        return {"source": "yerel", "name": local[0].name, **manifest}

    async def log(self, limit: int = 15) -> list[dict[str, Any]]:
        return await self.db.fetchall("SELECT * FROM sync_log ORDER BY id DESC LIMIT ?", (limit,))

    async def api_token(self) -> str:
        tok = await self.db.get_setting("api_token")
        if not tok:
            tok = secrets.token_urlsafe(24)
            await self.db.set_setting("api_token", tok)
        return tok


# ---------------------------------------------------------------------------
# Uzaktan erişim API'si (FastAPI)
# ---------------------------------------------------------------------------
def create_api(ws: Workstation):
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel

    app = FastAPI(title="4K AI WORKSTATION API", version=config.APP_VERSION)

    async def auth(authorization: str = Header(default="")) -> None:
        token = await ws.sync.api_token()
        if not secrets.compare_digest(authorization.removeprefix("Bearer ").strip(), token):
            raise HTTPException(status_code=401, detail="Geçersiz token")

    class ChatIn(BaseModel):
        message: str

    class SearchIn(BaseModel):
        query: str
        deep: bool = False

    @app.get("/status", dependencies=[Depends(auth)])
    async def status():
        return {"device": config.DEVICE_NAME, "gear": await ws.engine.get_gear(),
                "system": await ws.engine.discover(), "cloud": ws.sync.cloud_state()}

    @app.post("/chat", dependencies=[Depends(auth)])
    async def chat(body: ChatIn):
        reply = await ws.engine.chat(body.message)
        return {"text": reply.text, "provider": reply.provider, "model": reply.model}

    @app.post("/search", dependencies=[Depends(auth)])
    async def search(body: SearchIn):
        report = await (ws.radar.deep_research(body.query) if body.deep else ws.radar.quick_search(body.query))
        return {"report": report}

    @app.get("/projects", dependencies=[Depends(auth)])
    async def projects():
        return await ws.projects.list_projects()

    @app.get("/ledger", dependencies=[Depends(auth)])
    async def ledger():
        return {"summary": await ws.business.summary(), "entries": await ws.business.entries(50)}

    return app


def _free_port(host: str, start: int, tries: int = 20) -> int | None:
    import socket

    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    return None


class ApiServer:
    """TUI içinden başlatılabilen arka plan uvicorn sunucusu."""

    def __init__(self, ws: Workstation) -> None:
        self.ws = ws
        self.server = None
        self.task: asyncio.Task | None = None
        self.host: str | None = None
        self.port: int = config.API_PORT

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(self, host: str | None = None) -> str:
        import uvicorn

        if self.running:
            return self.url
        if host is None:
            ts = await tailscale_status()
            host = ts["self"]["ip"] if ts.get("running") and ts.get("self") else "127.0.0.1"
        port = _free_port(host, config.API_PORT)
        if port is None:
            raise RuntimeError(f"{host} üzerinde {config.API_PORT}-{config.API_PORT + 20} aralığında boş port yok")
        self.host, self.port = host, port
        cfg = uvicorn.Config(create_api(self.ws), host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(cfg)
        self.server.install_signal_handlers = lambda: None  # TUI'nin sinyallerine dokunma
        self.task = asyncio.create_task(self._serve())
        await asyncio.sleep(0.5)
        if self.task.done():
            raise RuntimeError(f"API sunucusu başlatılamadı ({host}:{port})")
        return self.url

    async def _serve(self) -> None:
        try:
            await self.server.serve()
        except SystemExit:  # uvicorn bağlanamayınca sys.exit çağırır
            pass

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    async def stop(self) -> None:
        if self.server and self.running:
            self.server.should_exit = True
            await asyncio.wait_for(self.task, timeout=5)
        self.task = None
