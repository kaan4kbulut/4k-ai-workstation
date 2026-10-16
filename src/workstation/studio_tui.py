"""⚡ 4K AI WORKSTATION — Textual tabanlı görsel terminal stüdyosu."""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

from rich.markdown import Markdown as RichMarkdown
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    Markdown,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from . import config
from .engine import ProviderError
from .sync import GOOGLE_SETUP_HELP
from .workstation import Workstation

GEAR_OPTIONS = [(label, key) for key, label in config.GEARS.items()]
TIER_LABEL = {"local": "🖥️ yerel", "free": "🆓 ücretsiz", "subscription": "💳 abonelik"}


def fmt_ts(ts: float | None) -> str:
    if not ts:
        return "-"
    return dt.datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")


def fmt_money(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ConfirmScreen(ModalScreen[bool]):
    """Geri alınamaz işlemler için onay penceresi."""

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.question, id="confirm-q")
            with Horizontal(id="confirm-buttons"):
                yield Button("Evet", variant="error", id="yes")
                yield Button("Vazgeç", variant="primary", id="no")

    @on(Button.Pressed)
    def answer(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class StudioApp(App):
    CSS_PATH = "studio.tcss"
    TITLE = f"{config.APP_NAME} {config.APP_VERSION}"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Çıkış", priority=True),
        Binding("f1", "tab('tab-desk')", "Masa"),
        Binding("f2", "tab('tab-chat')", "Sohbet"),
        Binding("f3", "tab('tab-radar')", "Radar"),
        Binding("f4", "tab('tab-project')", "Proje"),
        Binding("f5", "tab('tab-business')", "İş"),
        Binding("f6", "tab('tab-sync')", "Sync"),
        Binding("ctrl+r", "refresh_all", "Yenile"),
    ]

    def __init__(self, workstation: Workstation | None = None) -> None:
        super().__init__()
        self.ws = workstation or Workstation()
        self.active_jobs: dict[str, float] = {}
        self.project_ids: list[int] = []
        self.ticket_ids: list[int] = []
        self.ledger_ids: list[int] = []
        self.task_ids: list[int] = []
        self.selected_project: int | None = None

    # ------------------------------------------------------------------ düzen
    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static(self._title_text(False), id="title")
            yield Label("Vites:", id="gear-label")
            yield Select(GEAR_OPTIONS, value=config.DEFAULT_GEAR, allow_blank=False, id="gear")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static("🌐 [b]Bağlı Cihazlar[/b]", classes="side-title")
                yield Static("Taranıyor…", id="nodes")
                yield Static("🔄 [b]Senkron Durumu[/b]", classes="side-title")
                yield Static("-", id="sync-state")
                yield Static("⚙️ [b]Aktif İşler[/b]", classes="side-title")
                yield Static("Boşta", id="jobs")
            with TabbedContent(id="tabs", initial="tab-desk"):
                with TabPane("💻 Çalışma Masası", id="tab-desk"):
                    yield from self._compose_desk()
                with TabPane("💬 Sohbet & Engine", id="tab-chat"):
                    yield from self._compose_chat()
                with TabPane("🔍 AI Radar & Arama", id="tab-radar"):
                    yield from self._compose_radar()
                with TabPane("📦 AI Project", id="tab-project"):
                    yield from self._compose_project()
                with TabPane("🏢 AI Business", id="tab-business"):
                    yield from self._compose_business()
                with TabPane("🔄 SYNC & Cihazlar", id="tab-sync"):
                    yield from self._compose_sync()
        yield Footer()

    def _compose_desk(self) -> ComposeResult:
        with VerticalScroll():
            with Horizontal(classes="toolbar"):
                yield Button("🔄 Yeniden Tara", id="rescan")
                yield Button("♻️ Cooldown Sıfırla", id="reset-cooldown")
            with Horizontal(id="desk-top"):
                yield Static("Sistem taranıyor…", id="sysinfo", classes="card")
                yield Static("", id="quota", classes="card")
            yield Label("Model Sağlayıcıları", classes="section")
            yield DataTable(id="providers", cursor_type="row", zebra_stripes=True)
            yield Label("Son Model Çağrıları", classes="section")
            yield DataTable(id="recent-usage", cursor_type="row", zebra_stripes=True)

    def _compose_chat(self) -> ComposeResult:
        yield RichLog(id="chat-log", wrap=True, markup=True, highlight=False)
        yield Static("", id="chat-status")
        with Horizontal(classes="inputbar"):
            yield Input(placeholder="Mesajınızı yazın ve Enter'a basın…", id="chat-input")
            yield Button("Gönder", variant="primary", id="chat-send")
            yield Button("🧹 Temizle", id="chat-clear")

    def _compose_radar(self) -> ComposeResult:
        with Horizontal(classes="inputbar"):
            yield Select(
                [("⚡ Hızlı", "quick"), ("🕵️ Derin Araştırma", "deep"), ("🐙 GitHub Trend", "github")],
                value="quick", allow_blank=False, id="radar-mode",
            )
            yield Input(placeholder="Ne aramak istiyorsunuz? (GitHub modunda konu: ai-agents, llm, memory, mcp)",
                        id="radar-input")
            yield Button("Ara", variant="primary", id="radar-go")
        with VerticalScroll(id="radar-scroll"):
            yield Markdown("Bir arama yapın. **Derin Araştırma** sayfaları indirip ENGINE ile kaynaklı Türkçe rapor üretir.",
                           id="radar-out")

    def _compose_project(self) -> ComposeResult:
        with Horizontal(id="project-top"):
            with Vertical(id="idea-box"):
                yield Label("💡 Fikrinizi doğal dille anlatın", classes="section")
                yield TextArea(id="idea-input")
                yield Button("🧠 Analiz Et & Biletlere Böl", variant="primary", id="idea-go")
            with Vertical(id="project-lists"):
                yield Label("Projeler", classes="section")
                yield DataTable(id="projects", cursor_type="row", zebra_stripes=True)
                yield Label("Biletler", classes="section")
                yield DataTable(id="tickets", cursor_type="row", zebra_stripes=True)
                with Horizontal(classes="toolbar"):
                    yield Button("🌿 Worktree Aç", id="ticket-open")
                    yield Button("✅ Bileti Kapat", id="ticket-close")
        with VerticalScroll(id="feasibility-scroll"):
            yield Markdown("Bir proje seçin veya yeni fikir girin.", id="feasibility")

    def _compose_business(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("", id="biz-summary", classes="card")
            yield Label("Gelir / Gider Ekle", classes="section")
            with Horizontal(classes="inputbar"):
                yield Select([("➕ Gelir", "gelir"), ("➖ Gider", "gider")], value="gider",
                             allow_blank=False, id="biz-type")
                yield Input(placeholder="Tutar", id="biz-amount", type="number")
                yield Select([("TRY", "TRY"), ("USD", "USD"), ("EUR", "EUR")], value="TRY",
                             allow_blank=False, id="biz-currency")
                yield Input(placeholder="Kategori", id="biz-category")
                yield Input(placeholder="Not", id="biz-note")
                yield Select([("Projesiz", 0)], value=0, allow_blank=False, id="biz-project")
                yield Button("Ekle", variant="primary", id="biz-add")
            yield DataTable(id="ledger", cursor_type="row", zebra_stripes=True)
            yield Button("🗑️ Seçili Kaydı Sil", id="biz-del")
            yield Label("Operasyonel Görevler (satıra Enter → durum ilerlet)", classes="section")
            with Horizontal(classes="inputbar"):
                yield Input(placeholder="Yeni görev", id="task-input")
                yield Button("Görev Ekle", id="task-add")
                yield Button("🗑️ Görevi Sil", id="task-del")
            yield DataTable(id="tasks", cursor_type="row", zebra_stripes=True)
            yield Label("Proje Bütçeleri", classes="section")
            yield DataTable(id="budgets", cursor_type="row", zebra_stripes=True)
            yield Label("Token / Kota Kullanımı (30 gün)", classes="section")
            yield DataTable(id="token-costs", cursor_type="row", zebra_stripes=True)

    def _compose_sync(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("", id="cloud-card", classes="card")
            with Horizontal(classes="toolbar"):
                yield Button("🔑 Google ile Bağlan", id="g-connect", variant="primary")
                yield Button("☁️ Şimdi Yedekle", id="g-backup")
                yield Button("⏮️ En Yeni Yedeği Geri Yükle", id="g-restore", variant="warning")
                yield Button("🚪 Google Çıkış", id="g-logout")
            with Horizontal(classes="toolbar"):
                yield Button("🌐 Uzaktan Erişim API'sini Başlat", id="api-toggle")
                yield Static("", id="api-info")
            yield Label("Tailscale Cihaz Ağı", classes="section")
            yield DataTable(id="node-table", cursor_type="row", zebra_stripes=True)
            yield Label("Senkron Günlüğü", classes="section")
            yield DataTable(id="sync-log", cursor_type="row", zebra_stripes=True)
            yield Markdown("", id="sync-help")

    # ------------------------------------------------------------- başlangıç
    async def on_mount(self) -> None:
        self.query_one("#providers", DataTable).add_columns("Sağlayıcı", "Tür", "Durum", "Son Hata")
        self.query_one("#recent-usage", DataTable).add_columns("Zaman", "Sağlayıcı", "Model", "Girdi tok.", "Çıktı tok.")
        self.query_one("#projects", DataTable).add_columns("ID", "Proje", "Durum", "Biletler")
        self.query_one("#tickets", DataTable).add_columns("ID", "Başlık", "Durum", "Dal")
        self.query_one("#ledger", DataTable).add_columns("Tarih", "Tür", "Tutar", "Kategori", "Proje", "Not")
        self.query_one("#tasks", DataTable).add_columns("ID", "Görev", "Durum", "Proje")
        self.query_one("#budgets", DataTable).add_columns("Proje", "Bütçe", "Harcanan", "Gelir")
        self.query_one("#token-costs", DataTable).add_columns("Sağlayıcı", "Tür", "Çağrı", "Girdi tok.", "Çıktı tok.", "Maliyet $")
        self.query_one("#node-table", DataTable).add_columns("Cihaz", "IP", "OS", "Durum", "Son Görülme")
        self.query_one("#sync-log", DataTable).add_columns("Zaman", "İşlem", "Durum", "Detay")

        gear = await self.ws.engine.get_gear()
        self.query_one("#gear", Select).value = gear
        self.query_one("#chat-log", RichLog).write(
            Text.from_markup("[b cyan]4K AI ENGINE[/] hazır. Vitese göre en uygun model otomatik seçilir. "
                             "Küçük işler yerelde, büyük mimari/kodlama işleri aboneliklerde çalışır.\n")
        )
        await self.load_chat_history()
        self.run_discovery()
        self.refresh_sync()
        await self.refresh_projects()
        await self.refresh_business()
        await self.refresh_sync_panel()
        self.set_interval(30, self.refresh_sync)
        self.set_interval(10, self.refresh_desk_tables)

    def _title_text(self, sync_active: bool) -> Text:
        state = "[b green]SYNC Aktif[/]" if sync_active else "[b yellow]SYNC Pasif[/]"
        return Text.from_markup(f"⚡ [b]{config.APP_NAME}[/] {config.APP_VERSION} [{state}]")

    def action_tab(self, tab: str) -> None:
        self.query_one("#tabs", TabbedContent).active = tab

    @on(TabbedContent.TabActivated, "#tabs")
    def focus_tab_input(self, event: TabbedContent.TabActivated) -> None:
        target = {"tab-chat": "#chat-input", "tab-radar": "#radar-input", "tab-project": "#idea-input"}
        if sel := target.get(event.pane.id or ""):
            self.query_one(sel).focus()

    async def action_refresh_all(self) -> None:
        self.run_discovery(force=True)
        self.refresh_sync()
        await self.refresh_projects()
        await self.refresh_business()
        await self.refresh_sync_panel()

    # -------------------------------------------------------- aktif işler
    def _job(self, name: str, on: bool) -> None:
        if on:
            self.active_jobs[name] = time.monotonic()
        else:
            self.active_jobs.pop(name, None)
        text = "\n".join(f"⏳ {n}" for n in self.active_jobs) or "Boşta"
        self.query_one("#jobs", Static).update(text)

    # ---------------------------------------------------------- vites
    @on(Select.Changed, "#gear")
    async def gear_changed(self, event: Select.Changed) -> None:
        if event.value in config.GEARS and event.value != await self.ws.engine.get_gear():
            await self.ws.engine.set_gear(event.value)
            self.notify(f"Vites: {config.GEARS[event.value]}")
            await self.refresh_desk_tables()

    # ----------------------------------------------------- çalışma masası
    @work(exclusive=True, group="discover", exit_on_error=False)
    async def run_discovery(self, force: bool = False) -> None:
        self._job("Donanım keşfi", True)
        try:
            info = await self.ws.engine.discover(force=force)
        finally:
            self._job("Donanım keşfi", False)
        t = Table.grid(padding=(0, 2))
        t.add_column(style="bold cyan")
        t.add_column()
        t.add_row("Cihaz", info["host"])
        t.add_row("OS", info["os"])
        t.add_row("CPU", f"{info['cpu']} ({info['cores']} çekirdek)")
        t.add_row("RAM", f"{info['ram_gb']} GB")
        t.add_row("GPU", "\n".join(f"{g['name']} — {g['vram_gb']} GB VRAM" for g in info["gpus"]) or "—")
        t.add_row("Ollama", f"{'🟢' if info['ollama_online'] else '🔴'} {len(info['ollama_models'])} model")
        t.add_row("CLI Ajanları", ", ".join(info["cli_agents"]) or "—")
        t.add_row("Ücretsiz API", ", ".join(info["free_apis"]) or "— (GROQ/OPENROUTER/GEMINI_API_KEY)")
        self.query_one("#sysinfo", Static).update(t)
        await self.refresh_desk_tables()

    async def refresh_desk_tables(self) -> None:
        now = time.time()
        table = self.query_one("#providers", DataTable)
        table.clear()
        known = {p.label() for p in self.ws.engine.providers}
        for r in await self.ws.engine.cooldown_status():
            if r["name"] not in known:
                continue
            if (r["cooldown_until"] or 0) > now:
                state = f"🧊 cooldown {int((r['cooldown_until'] - now) / 60) + 1} dk"
            else:
                state = "✅ hazır"
            table.add_row(r["name"], TIER_LABEL.get(r["kind"], r["kind"]), state, (r["last_error"] or "")[:60])

        usage = self.query_one("#recent-usage", DataTable)
        usage.clear()
        for r in await self.ws.db.fetchall("SELECT * FROM usage ORDER BY id DESC LIMIT 10"):
            usage.add_row(fmt_ts(r["ts"]), r["provider"], r["model"] or "-", str(r["tokens_in"]), str(r["tokens_out"]))

        gear = await self.ws.engine.get_gear()
        saved = await self.ws.business.quota_saved_ratio()
        small = " → ".join(p.label() for p in self.ws.engine.plan_route(gear, "small")[:3]) or "—"
        large = " → ".join(p.label() for p in self.ws.engine.plan_route(gear, "large")[:3]) or "—"
        self.query_one("#quota", Static).update(Text.from_markup(
            f"[b]Vites:[/] {config.GEARS[gear]}\n"
            f"[b]Kota tasarrufu (30g):[/] %{saved * 100:.0f} çağrı yerel/ücretsiz\n\n"
            f"[b]Küçük iş rotası:[/]\n{small}\n\n[b]Büyük iş rotası:[/]\n{large}"
        ))

    @on(Button.Pressed, "#rescan")
    def rescan(self) -> None:
        self.run_discovery(force=True)

    @on(Button.Pressed, "#reset-cooldown")
    async def reset_cooldown(self) -> None:
        await self.ws.engine.reset_cooldowns()
        self.notify("Tüm cooldown'lar sıfırlandı")
        await self.refresh_desk_tables()

    # ------------------------------------------------------------- sohbet
    async def load_chat_history(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        for r in await self.ws.db.fetchall("SELECT * FROM (SELECT * FROM chat_history ORDER BY id DESC LIMIT 20) ORDER BY id"):
            self._write_chat(r["role"], r["content"], r["provider"])
        if log.lines:
            log.write(Text("── önceki oturum ──", style="dim"))

    def _write_chat(self, role: str, content: str, provider: str | None = None) -> None:
        log = self.query_one("#chat-log", RichLog)
        if role == "user":
            log.write(Text.from_markup(f"\n[b green]🧑 Siz:[/] ") + Text(content))
        else:
            log.write(Text.from_markup(f"\n[b cyan]🤖 {provider or 'Asistan'}:[/]"))
            log.write(RichMarkdown(content))

    @on(Input.Submitted, "#chat-input")
    @on(Button.Pressed, "#chat-send")
    def chat_submit(self) -> None:
        inp = self.query_one("#chat-input", Input)
        msg = inp.value.strip()
        if not msg:
            return
        inp.value = ""
        self._write_chat("user", msg)
        self.send_chat(msg)

    @work(exclusive=True, group="chat", exit_on_error=False)
    async def send_chat(self, msg: str) -> None:
        status = self.query_one("#chat-status", Static)
        status.update("🧠 Düşünüyor…")
        self._job("Sohbet yanıtı", True)
        try:
            reply = await self.ws.engine.chat(msg)
        except ProviderError as e:
            self.query_one("#chat-log", RichLog).write(Text(f"⚠️ {e}", style="red"))
            status.update("")
            return
        finally:
            self._job("Sohbet yanıtı", False)
        self._write_chat("assistant", reply.text, reply.label)
        fallback = f" · {len(reply.attempts)} yedeğe geçiş" if reply.attempts else ""
        status.update(f"{config.GEARS[reply.gear]} · {TIER_LABEL.get(reply.tier, reply.tier)} · "
                      f"{reply.label} · {reply.elapsed:.1f} sn{fallback}")
        await self.refresh_desk_tables()

    @on(Button.Pressed, "#chat-clear")
    async def chat_clear(self) -> None:
        await self.ws.engine.clear_chat()
        self.query_one("#chat-log", RichLog).clear()
        self.notify("Sohbet geçmişi temizlendi")

    # -------------------------------------------------------------- radar
    @on(Input.Submitted, "#radar-input")
    @on(Button.Pressed, "#radar-go")
    def radar_submit(self) -> None:
        query = self.query_one("#radar-input", Input).value.strip()
        mode = self.query_one("#radar-mode", Select).value
        if not query and mode != "github":
            self.notify("Arama sorgusu girin", severity="warning")
            return
        self.run_radar(mode, query or "ai-agents")

    @work(exclusive=True, group="radar", exit_on_error=False)
    async def run_radar(self, mode: str, query: str) -> None:
        out = self.query_one("#radar-out", Markdown)
        self._job("Radar araması", True)
        try:
            if mode == "quick":
                await out.update("⏳ Aranıyor…")
                report = await self.ws.radar.quick_search(query)
            elif mode == "deep":
                steps: list[str] = []

                def progress(msg: str) -> None:
                    steps.append(msg)
                    self.call_later(out.update, "\n\n".join(steps))

                progress("⏳ Derin araştırma başladı")
                report = await self.ws.radar.deep_research(query, progress=progress)
            else:
                await out.update("⏳ GitHub taranıyor…")
                repos = await self.ws.radar.github_trends(query)
                rows = "\n".join(
                    f"| [{r['name']}]({r['url']}) | ⭐ {r['stars']} | {r['lang']} | {r['created']} | "
                    f"{r['desc'].replace('|', '/')} |" for r in repos
                )
                report = (f"## 🐙 GitHub Trend: `{query}` (son 7 gün)\n\n"
                          "| Depo | Yıldız | Dil | Tarih | Açıklama |\n|---|---|---|---|---|\n" + rows
                          if repos else f"`{query}` için yeni proje bulunamadı.")
            await out.update(report)
        except Exception as e:
            await out.update(f"⚠️ **Hata:** {e}")
        finally:
            self._job("Radar araması", False)

    # ------------------------------------------------------------ project
    async def refresh_projects(self) -> None:
        projects = await self.ws.projects.list_projects()
        table = self.query_one("#projects", DataTable)
        table.clear()
        self.project_ids = []
        for p in projects:
            self.project_ids.append(p["id"])
            table.add_row(str(p["id"]), p["name"], p["status"], f"{p['done']}/{p['ticket_count']}")
        self.query_one("#biz-project", Select).set_options(
            [("Projesiz", 0)] + [(p["name"], p["id"]) for p in projects]
        )
        self.query_one("#biz-project", Select).value = 0
        if self.selected_project:
            await self.show_project(self.selected_project)

    async def show_project(self, project_id: int) -> None:
        self.selected_project = project_id
        p = await self.ws.projects.get_project(project_id)
        if not p:
            return
        await self.query_one("#feasibility", Markdown).update(
            (p["feasibility_md"] or "") + f"\n\n📁 `{p['repo_path']}`"
        )
        table = self.query_one("#tickets", DataTable)
        table.clear()
        self.ticket_ids = []
        for t in await self.ws.projects.list_tickets(project_id):
            self.ticket_ids.append(t["id"])
            table.add_row(str(t["id"]), t["title"], t["status"], t["branch"] or "-")

    @on(DataTable.RowHighlighted, "#projects")
    async def project_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if 0 <= event.cursor_row < len(self.project_ids):
            pid = self.project_ids[event.cursor_row]
            if pid != self.selected_project:
                await self.show_project(pid)

    @on(Button.Pressed, "#idea-go")
    def idea_submit(self) -> None:
        idea = self.query_one("#idea-input", TextArea).text.strip()
        if len(idea) < 10:
            self.notify("Fikrinizi biraz daha detaylı anlatın", severity="warning")
            return
        self.run_idea(idea)

    @work(exclusive=True, group="project", exit_on_error=False)
    async def run_idea(self, idea: str) -> None:
        md = self.query_one("#feasibility", Markdown)
        await md.update("⏳ **Fikir analiz ediliyor…** Büyük iş olarak sınıflandırıldı; vitese göre en güçlü model kullanılıyor.")
        self._job("Fikir analizi", True)
        try:
            pid, analysis = await self.ws.projects.submit_idea(idea)
        except Exception as e:
            await md.update(f"⚠️ **Hata:** {e}")
            return
        finally:
            self._job("Fikir analizi", False)
        self.query_one("#idea-input", TextArea).text = ""
        self.selected_project = pid
        await self.refresh_projects()
        self.notify(f"✅ '{analysis.name}' oluşturuldu: {len(analysis.tickets)} bilet")

    def _selected(self, table_id: str, ids: list[int]) -> int | None:
        table = self.query_one(table_id, DataTable)
        if table.row_count == 0 or not (0 <= table.cursor_row < len(ids)):
            return None
        return ids[table.cursor_row]

    @on(Button.Pressed, "#ticket-open")
    async def ticket_open(self) -> None:
        tid = self._selected("#tickets", self.ticket_ids)
        if tid is None:
            self.notify("Önce bir bilet seçin", severity="warning")
            return
        try:
            path = await self.ws.projects.open_worktree(tid)
        except Exception as e:
            self.notify(f"Worktree açılamadı: {e}", severity="error")
            return
        self.copy_to_clipboard(path)
        self.notify(f"🌿 Worktree hazır (yol panoya kopyalandı):\n{path}", timeout=8)
        await self.show_project(self.selected_project)
        await self.refresh_projects()

    @on(Button.Pressed, "#ticket-close")
    async def ticket_close(self) -> None:
        tid = self._selected("#tickets", self.ticket_ids)
        if tid is None:
            self.notify("Önce bir bilet seçin", severity="warning")
            return
        try:
            await self.ws.projects.close_ticket(tid)
        except Exception as e:
            self.notify(f"Kapatılamadı (commit edilmemiş değişiklik olabilir): {e}", severity="error")
            return
        self.notify("✅ Bilet tamamlandı (dal korunuyor)")
        await self.refresh_projects()

    # ----------------------------------------------------------- business
    async def refresh_business(self) -> None:
        biz = self.ws.business
        summary = await biz.summary()
        lines = []
        for cur, v in summary["by_currency"].items():
            color = "green" if v["net"] >= 0 else "red"
            lines.append(f"[b]{cur}[/]  Gelir: [green]{fmt_money(v['gelir'])}[/]  "
                         f"Gider: [red]{fmt_money(v['gider'])}[/]  Net: [b {color}]{fmt_money(v['net'])}[/]")
        month = {(r["currency"], r["type"]): r["total"] for r in summary["this_month"]}
        if month:
            lines.append("[dim]Bu ay: " + ", ".join(f"{c} {t} {fmt_money(v)}" for (c, t), v in month.items()) + "[/]")
        self.query_one("#biz-summary", Static).update(
            Text.from_markup("🏢 [b]Finansal Özet[/]\n" + ("\n".join(lines) or "Henüz kayıt yok."))
        )

        ledger = self.query_one("#ledger", DataTable)
        ledger.clear()
        self.ledger_ids = []
        for e in await biz.entries():
            self.ledger_ids.append(e["id"])
            sign = "[green]+[/]" if e["type"] == "gelir" else "[red]-[/]"
            ledger.add_row(fmt_ts(e["ts"]), e["type"], Text.from_markup(f"{sign}{fmt_money(e['amount'])} {e['currency']}"),
                           e["category"] or "-", e["project"] or "-", e["note"] or "")

        tasks = self.query_one("#tasks", DataTable)
        tasks.clear()
        self.task_ids = []
        icon = {"yapılacak": "⬜", "devam ediyor": "🔶", "tamamlandı": "✅"}
        for t in await biz.tasks():
            self.task_ids.append(t["id"])
            tasks.add_row(str(t["id"]), t["title"], f"{icon.get(t['status'], '')} {t['status']}", t["project"] or "-")

        budgets = self.query_one("#budgets", DataTable)
        budgets.clear()
        for b in await biz.project_budgets():
            budgets.add_row(b["name"], fmt_money(b["budget"] or 0), fmt_money(b["spent"]), fmt_money(b["earned"]))

        costs = self.query_one("#token-costs", DataTable)
        costs.clear()
        for c in await biz.token_costs():
            costs.add_row(c["provider"], c["tier"], str(c["calls"]), str(c["tin"] or 0), str(c["tout"] or 0), f"{c['cost']:.4f}")

    @on(Button.Pressed, "#biz-add")
    async def biz_add(self) -> None:
        try:
            amount = float(self.query_one("#biz-amount", Input).value.replace(",", "."))
            project = self.query_one("#biz-project", Select).value
            await self.ws.business.add_entry(
                self.query_one("#biz-type", Select).value,
                amount,
                self.query_one("#biz-category", Input).value.strip() or "genel",
                self.query_one("#biz-note", Input).value.strip(),
                project_id=project or None,
                currency=self.query_one("#biz-currency", Select).value,
            )
        except ValueError as e:
            self.notify(f"Geçersiz giriş: {e}", severity="error")
            return
        for i in ("#biz-amount", "#biz-category", "#biz-note"):
            self.query_one(i, Input).value = ""
        self.notify("💰 Kayıt eklendi")
        await self.refresh_business()

    @on(Button.Pressed, "#biz-del")
    async def biz_del(self) -> None:
        eid = self._selected("#ledger", self.ledger_ids)
        if eid is not None:
            await self.ws.business.delete_entry(eid)
            await self.refresh_business()

    @on(Input.Submitted, "#task-input")
    @on(Button.Pressed, "#task-add")
    async def task_add(self) -> None:
        inp = self.query_one("#task-input", Input)
        if not inp.value.strip():
            return
        await self.ws.business.add_task(inp.value, project_id=self.selected_project)
        inp.value = ""
        await self.refresh_business()

    @on(DataTable.RowSelected, "#tasks")
    async def task_advance(self, event: DataTable.RowSelected) -> None:
        if 0 <= event.cursor_row < len(self.task_ids):
            new = await self.ws.business.advance_task(self.task_ids[event.cursor_row])
            self.notify(f"Görev durumu: {new}")
            await self.refresh_business()

    @on(Button.Pressed, "#task-del")
    async def task_del(self) -> None:
        tid = self._selected("#tasks", self.task_ids)
        if tid is not None:
            await self.ws.business.delete_task(tid)
            await self.refresh_business()

    # --------------------------------------------------------------- sync
    @work(exclusive=True, group="sync-refresh", exit_on_error=False)
    async def refresh_sync(self) -> None:
        status = await self.ws.sync.refresh()
        nodes = status["nodes"]
        if not status["installed"]:
            text = "[yellow]Tailscale kurulu değil[/]"
        elif not status["running"]:
            text = "[yellow]Tailscale kapalı[/]\n`tailscale up`"
        else:
            text = "\n".join(
                f"{'🟢' if n['online'] else '⚫'} {n['name']}{' (bu cihaz)' if n['self'] else ''}\n   [dim]{n['ip']} · {n['os']}[/]"
                for n in nodes
            )
        self.query_one("#nodes", Static).update(Text.from_markup(text))
        await self._update_sync_state(status)
        table = self.query_one("#node-table", DataTable)
        table.clear()
        for n in nodes:
            table.add_row(n["name"] + (" ⭐" if n["self"] else ""), n["ip"], n["os"],
                          "🟢 çevrimiçi" if n["online"] else "⚫ çevrimdışı", n["last_seen"])

    async def _update_sync_state(self, status: dict | None = None) -> None:
        status = status or self.ws.sync.last_status
        cloud = self.ws.sync.cloud_state()
        last = await self.ws.db.get_setting("last_backup")
        email = await self.ws.db.get_setting("google_email") or ""
        active = bool(status.get("running")) or cloud == "bağlı"
        self.query_one("#title", Static).update(self._title_text(active))
        self.query_one("#sync-state", Static).update(Text.from_markup(
            f"Tailscale: {'🟢' if status.get('running') else '🔴'}\n"
            f"Google: {'🟢 ' + email if cloud == 'bağlı' else '🔴 ' + cloud}\n"
            f"Son yedek: {fmt_ts(float(last)) if last else 'hiç'}\n"
            f"API: {'🟢 açık' if self.ws.api.running else '⚫ kapalı'}"
        ))

    async def refresh_sync_panel(self) -> None:
        cloud = self.ws.sync.cloud_state()
        email = await self.ws.db.get_setting("google_email") or ""
        local = len(list(config.BACKUP_DIR.glob("4k-backup-*.tar.gz")))
        self.query_one("#cloud-card", Static).update(Text.from_markup(
            f"☁️ [b]Google Drive:[/] {cloud} {email}\n"
            f"💾 [b]Yerel yedekler:[/] {local} adet — {config.BACKUP_DIR}\n"
            f"🗄️ [b]Durum veritabanı:[/] {self.ws.db.path}\n"
            f"🖥️ [b]Bu cihaz:[/] {config.DEVICE_NAME}"
        ))
        await self.query_one("#sync-help", Markdown).update(GOOGLE_SETUP_HELP if cloud == "yapılandırılmadı" else "")
        log = self.query_one("#sync-log", DataTable)
        log.clear()
        for r in await self.ws.sync.log():
            log.add_row(fmt_ts(r["ts"]), r["action"], r["status"], (r["detail"] or "")[:80])
        await self._update_sync_state()

    @on(Button.Pressed, "#g-connect")
    def g_connect(self) -> None:
        if not self.ws.sync.drive.configured():
            self.notify(f"Önce client_secret.json dosyasını {config.GOOGLE_CLIENT_SECRET} konumuna koyun",
                        severity="warning", timeout=8)
            return
        self.run_google_connect()

    @work(exclusive=True, group="sync", exit_on_error=False)
    async def run_google_connect(self) -> None:
        self._job("Google girişi", True)
        self.notify("Tarayıcıda Google izin sayfası açılıyor…")
        try:
            email = await self.ws.sync.connect_google()
            self.notify(f"✅ Google hesabı bağlandı: {email}")
        except Exception as e:
            self.notify(f"Google bağlantısı başarısız: {e}", severity="error")
        finally:
            self._job("Google girişi", False)
            await self.refresh_sync_panel()

    @on(Button.Pressed, "#g-backup")
    def g_backup(self) -> None:
        self.run_backup()

    @work(exclusive=True, group="sync", exit_on_error=False)
    async def run_backup(self) -> None:
        self._job("Yedekleme", True)
        try:
            res = await self.ws.sync.backup()
            where = "yerel + ☁️ Google Drive" if res["cloud"] else "yalnızca yerel"
            self.notify(f"✅ Yedek alındı ({where}):\n{Path(res['local']).name}")
        except Exception as e:
            self.notify(str(e), severity="error", timeout=10)
        finally:
            self._job("Yedekleme", False)
            await self.refresh_sync_panel()

    @on(Button.Pressed, "#g-restore")
    def g_restore(self) -> None:
        def done(ok: bool | None) -> None:
            if ok:
                self.run_restore()

        self.push_screen(ConfirmScreen(
            "En yeni yedek geri yüklenecek. Mevcut veritabanı ve projeler klasörü değiştirilecek\n"
            "(önce otomatik 'pre-restore' yedeği alınır). Devam edilsin mi?"), done)

    @work(exclusive=True, group="sync", exit_on_error=False)
    async def run_restore(self) -> None:
        self._job("Geri yükleme", True)
        try:
            res = await self.ws.sync.restore_latest()
            self.notify(f"✅ {res['source']} yedek geri yüklendi: {res['name']}")
            await self.action_refresh_all()
        except Exception as e:
            self.notify(f"Geri yükleme başarısız: {e}", severity="error", timeout=10)
        finally:
            self._job("Geri yükleme", False)
            await self.refresh_sync_panel()

    @on(Button.Pressed, "#g-logout")
    async def g_logout(self) -> None:
        await self.ws.sync.disconnect_google()
        self.notify("Google hesabı bağlantısı kaldırıldı")
        await self.refresh_sync_panel()

    @on(Button.Pressed, "#api-toggle")
    async def api_toggle(self, event: Button.Pressed) -> None:
        info = self.query_one("#api-info", Static)
        if self.ws.api.running:
            await self.ws.api.stop()
            event.button.label = "🌐 Uzaktan Erişim API'sini Başlat"
            info.update("")
        else:
            try:
                url = await self.ws.api.start()
            except Exception as e:
                self.notify(str(e), severity="error")
                return
            token = await self.ws.sync.api_token()
            event.button.label = "⏹️ API'yi Durdur"
            info.update(Text.from_markup(f"  [b green]{url}[/]  token: [b]{token}[/]"))
            self.notify(f"API açık: {url}\nİstek başlığı: Authorization: Bearer <token>", timeout=10)
        await self._update_sync_state()

    async def on_unmount(self) -> None:
        await self.ws.shutdown()
