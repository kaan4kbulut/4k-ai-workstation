import subprocess

from workstation.project import ProjectManager, parse_analysis, slugify

RAW = """Tabii! ```json
{"name": "Akıllı Çiftlik", "summary": "IoT sensörleri", "feasibility_score": 7,
 "risks": ["donanım maliyeti"], "stack": ["Python"],
 "tickets": [{"title": "Sensör API", "description": "REST"}, {"title": "Panel", "description": "TUI"}]}
```"""


def test_slugify_turkish():
    assert slugify("Akıllı Çiftlik Ğüşö") == "akilli-ciftlik-guso"


def test_parse_analysis_valid():
    a = parse_analysis(RAW, "fikir")
    assert a.name == "akilli-ciftlik"
    assert a.feasibility_score == 7
    assert len(a.tickets) == 2


def test_parse_analysis_garbage_fallback():
    a = parse_analysis("model saçmaladı", "Bir sohbet botu yap")
    assert len(a.tickets) == 1 and a.tickets[0].title == "MVP"


async def test_project_worktree_flow(db, tmp_path):
    pm = ProjectManager(db, engine=None, root=tmp_path / "projects")
    pid = await pm.create_project("fikir", parse_analysis(RAW, "fikir"))
    p = await pm.get_project(pid)
    tickets = await pm.list_tickets(pid)
    assert len(tickets) == 2
    wt = await pm.open_worktree(tickets[0]["id"])
    assert (tmp_path / "projects" / "akilli-ciftlik-wt").exists()
    branches = subprocess.run(["git", "branch"], cwd=p["repo_path"], capture_output=True, text=True).stdout
    assert "ticket/" in branches
    await pm.close_ticket(tickets[0]["id"])
    t = (await pm.list_tickets(pid))[0]
    assert t["status"] == "tamamlandı" and t["worktree_path"] is None
    assert not __import__("os").path.exists(wt)
