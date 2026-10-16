"""Giriş noktası: `./4k` (TUI), `./4k --doctor`, `./4k --serve`, `./4k --backup`, `./4k --restore`."""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from . import config

console = Console()


async def doctor() -> int:
    from .sync import tailscale_status
    from .workstation import Workstation

    ws = Workstation()
    with console.status("Sistem taranıyor…"):
        info, ts = await asyncio.gather(ws.engine.discover(), tailscale_status())
    t = Table(title=f"⚡ {config.APP_NAME} {config.APP_VERSION} — Sistem Teşhisi", show_header=False)
    t.add_row("Cihaz", info["host"])
    t.add_row("İşletim Sistemi", info["os"])
    t.add_row("CPU", f"{info['cpu']} ({info['cores']} çekirdek)")
    t.add_row("RAM", f"{info['ram_gb']} GB")
    t.add_row("GPU", ", ".join(f"{g['name']} ({g['vram_gb']} GB)" for g in info["gpus"]) or "—")
    t.add_row("Ollama", ", ".join(m["name"] for m in info["ollama_models"]) or "çevrimdışı")
    t.add_row("CLI Ajanları", ", ".join(info["cli_agents"]) or "—")
    t.add_row("Ücretsiz API", ", ".join(info["free_apis"]) or "—")
    t.add_row("Tailscale", f"{'çalışıyor' if ts['running'] else 'kapalı'} — {len(ts['nodes'])} cihaz")
    t.add_row("Google Drive", ws.sync.cloud_state())
    t.add_row("Vites", config.GEARS[await ws.engine.get_gear()])
    t.add_row("Veritabanı", str(ws.db.path))
    console.print(t)
    order = ws.engine.plan_route(await ws.engine.get_gear(), "small")
    console.print("Küçük iş rotası: " + " → ".join(p.label() for p in order[:5]))
    order = ws.engine.plan_route(await ws.engine.get_gear(), "large")
    console.print("Büyük iş rotası: " + " → ".join(p.label() for p in order[:5]))
    await ws.shutdown()
    return 0


async def serve(host: str | None) -> int:
    from .workstation import Workstation

    ws = Workstation()
    url = await ws.api.start(host)
    console.print(f"🌐 API: {url}  —  Token: [bold]{await ws.sync.api_token()}[/]")
    console.print("Durdurmak için Ctrl+C")
    try:
        await ws.api.task
    except asyncio.CancelledError:
        pass
    finally:
        await ws.shutdown()
    return 0


async def backup() -> int:
    from .workstation import Workstation

    ws = Workstation()
    res = await ws.sync.backup()
    console.print(f"✅ Yerel: {res['local']}\n☁️  Bulut: {res['cloud'] or 'bağlı değil'}")
    await ws.shutdown()
    return 0


async def restore() -> int:
    from .workstation import Workstation

    ws = Workstation()
    res = await ws.sync.restore_latest()
    console.print(f"✅ Geri yüklendi ({res['source']}): {res['name']} — kaynak cihaz: {res.get('device')}")
    await ws.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="4k", description=f"{config.APP_NAME} {config.APP_VERSION}")
    parser.add_argument("--doctor", action="store_true", help="donanım ve sağlayıcı keşfini göster")
    parser.add_argument("--serve", action="store_true", help="uzaktan erişim API'sini başlat")
    parser.add_argument("--host", help="API dinleme adresi (varsayılan: Tailscale IP)")
    parser.add_argument("--backup", action="store_true", help="yedek al (Google bağlıysa buluta da)")
    parser.add_argument("--restore", action="store_true", help="en yeni yedeği geri yükle")
    parser.add_argument("--desktop-backend", action="store_true", help="masaüstü uygulaması için yerel API")
    parser.add_argument("--port", type=int, default=0, help="--desktop-backend dinleme portu")
    args = parser.parse_args()

    if args.desktop_backend:
        from .server import run

        return run(args.port or config.API_PORT)

    try:
        if args.doctor:
            return asyncio.run(doctor())
        if args.serve:
            return asyncio.run(serve(args.host))
        if args.backup:
            return asyncio.run(backup())
        if args.restore:
            return asyncio.run(restore())
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        console.print(f"[red]Hata:[/] {e}")
        return 1

    from .studio_tui import StudioApp

    StudioApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
