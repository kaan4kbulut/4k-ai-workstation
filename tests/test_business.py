import pytest

from workstation.business import Business


async def test_ledger_summary(db):
    b = Business(db)
    await b.add_entry("gelir", 1000, "satış")
    await b.add_entry("gider", 250.5, "sunucu")
    await b.add_entry("gider", 10, "api", currency="USD")
    s = await b.summary()
    assert s["by_currency"]["TRY"]["net"] == pytest.approx(749.5)
    assert s["by_currency"]["USD"]["net"] == pytest.approx(-10)
    with pytest.raises(ValueError):
        await b.add_entry("gelir", -5)


async def test_tasks_cycle(db):
    b = Business(db)
    tid = await b.add_task("Fatura kes")
    assert await b.advance_task(tid) == "devam ediyor"
    assert await b.advance_task(tid) == "tamamlandı"
    await b.delete_task(tid)
    assert await b.tasks() == []


async def test_quota_ratio(db):
    b = Business(db)
    for p in ("ollama/x", "ollama/x", "ollama/x", "claude"):
        db.execute_sync("INSERT INTO usage(ts, provider, model, tokens_in, tokens_out) VALUES(strftime('%s','now'),?,?,1,1)", (p, ""))
    assert await b.quota_saved_ratio() == pytest.approx(0.75)
