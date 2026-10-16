import time

import pytest

from workstation.engine import (
    Engine,
    Provider,
    ProviderError,
    classify_task,
    compress_context,
)


class FakeProvider(Provider):
    def __init__(self, name, tier, strength=1, fail=None, fits_gpu=True):
        self.name = name
        self.model = ""
        self.tier = tier
        self.strength = strength
        self.fail = fail
        self.fits_gpu = fits_gpu
        self.calls = 0

    async def complete(self, prompt, system=None):
        self.calls += 1
        if self.fail:
            raise self.fail
        return f"yanıt:{self.name}"


def make_engine(db, providers):
    e = Engine(db)
    e.providers = providers
    e._discovered = True
    for p in providers:
        db.execute_sync("INSERT INTO providers(name, kind, available) VALUES(?,?,1)", (p.label(), p.tier))
    return e


def test_classify_task():
    assert classify_task("merhaba nasılsın") == "small"
    assert classify_task("Bu servis için mimari tasarla") == "large"
    assert classify_task("x" * 2000) == "large"


def test_compress_context_keeps_recent():
    hist = [{"role": "user", "content": f"mesaj {i}"} for i in range(20)]
    ctx = compress_context(hist, keep_last=4)
    assert "mesaj 19" in ctx and "[Önceki konuşma özeti]" in ctx
    assert ctx.count("user:") >= 4


def test_route_by_gear(db):
    local = FakeProvider("ollama/a", "local", 5)
    sub = FakeProvider("claude", "subscription", 10)
    e = make_engine(db, [local, sub])
    assert [p.name for p in e.plan_route("ekonomik", "large")] == ["ollama/a"]
    assert [p.name for p in e.plan_route("dengeli", "small")] == ["ollama/a", "claude"]
    assert [p.name for p in e.plan_route("dengeli", "large")] == ["claude", "ollama/a"]
    assert e.plan_route("tam", "small")[0].name == "claude"


async def test_fallback_and_cooldown(db):
    sub = FakeProvider("claude", "subscription", 10, fail=ProviderError("429", quota=True))
    local = FakeProvider("ollama/a", "local", 5)
    e = make_engine(db, [local, sub])
    reply = await e.ask("mimari tasarla", gear="tam")
    assert reply.provider == "ollama/a"
    assert len(reply.attempts) == 1
    row = db.fetchone_sync("SELECT cooldown_until FROM providers WHERE name='claude'")
    assert row["cooldown_until"] > time.time() + 25 * 60
    # Cooldown'daki sağlayıcı bir sonraki istekte atlanır.
    await e.ask("mimari tasarla", gear="tam")
    assert sub.calls == 1
    usage = db.fetchall_sync("SELECT provider FROM usage")
    assert [u["provider"] for u in usage] == ["ollama/a", "ollama/a"]


async def test_all_fail_raises(db):
    e = make_engine(db, [FakeProvider("ollama/a", "local", fail=ProviderError("bozuk"))])
    with pytest.raises(ProviderError):
        await e.ask("selam")


async def test_economic_without_local_raises(db):
    e = make_engine(db, [FakeProvider("claude", "subscription")])
    with pytest.raises(ProviderError, match="Kullanılabilir model yok"):
        await e.ask("selam", gear="ekonomik")


async def test_gear_persisted(db):
    e = make_engine(db, [])
    assert await e.get_gear() == "dengeli"
    await e.set_gear("tam")
    assert await e.get_gear() == "tam"
    with pytest.raises(ValueError):
        await e.set_gear("turbo")
