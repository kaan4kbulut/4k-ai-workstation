from workstation import config, sync
from workstation.db import Database


def test_backup_restore_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    (tmp_path / "projects" / "demo").mkdir(parents=True)
    (tmp_path / "projects" / "demo" / "a.txt").write_text("merhaba")

    db = Database(tmp_path / "state.db")
    db.set_setting_sync("k", "v1")
    archive = sync.build_backup_archive(db)

    db.set_setting_sync("k", "v2")
    (tmp_path / "projects" / "demo" / "a.txt").write_text("değişti")
    manifest = sync.restore_backup_archive(db, archive)

    assert manifest["device"] == config.DEVICE_NAME
    assert db.get_setting_sync("k") == "v1"
    assert (tmp_path / "projects" / "demo" / "a.txt").read_text() == "merhaba"
    assert list((tmp_path / "backups" / "pre-restore").glob("*.tar.gz"))
    db.close()


async def test_tailscale_missing(monkeypatch):
    monkeypatch.setattr(sync.shutil, "which", lambda _: None)
    st = await sync.tailscale_status()
    assert st == {"installed": False, "running": False, "self": None, "nodes": []}
