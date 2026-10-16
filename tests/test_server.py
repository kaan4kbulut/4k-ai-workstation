from fastapi.testclient import TestClient

from workstation.server import create_app
from workstation.workstation import Workstation


def make_client(tmp_path):
    ws = Workstation(tmp_path / "state.db")
    ws.engine._discovered = True  # testte gerçek donanım/ağ taraması yapma
    ws.engine.system = {"host": "test"}
    return TestClient(create_app(ws, "gizli"))


def test_auth_and_ledger(tmp_path):
    with make_client(tmp_path) as c:
        assert c.get("/health").json()["ok"] is True
        assert c.get("/api/projects").status_code == 401
        h = {"X-4K-Token": "gizli"}
        assert c.post("/api/ledger", json={"type": "gelir", "amount": 250}, headers=h).status_code == 200
        bad = c.post("/api/ledger", json={"type": "x", "amount": 1}, headers=h)
        assert bad.status_code == 400 and "gelir" in bad.json()["detail"]
        assert c.get("/api/business", headers=h).json()["summary"]["by_currency"]["TRY"]["net"] == 250


def test_gear_and_tasks(tmp_path):
    with make_client(tmp_path) as c:
        h = {"X-4K-Token": "gizli"}
        assert c.put("/api/gear", json={"gear": "tam"}, headers=h).status_code == 200
        assert c.put("/api/gear", json={"gear": "turbo"}, headers=h).status_code == 400
        tid = c.post("/api/tasks", json={"title": "Fatura"}, headers=h).json()["id"]
        assert c.post(f"/api/tasks/{tid}/advance", headers=h).json()["status"] == "devam ediyor"
