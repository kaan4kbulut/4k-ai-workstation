"""
4K AI WORKSTATION - Terminal Komut Merkezi (Terminal Modu)
Tarayıcı veya görsel arayüze ihtiyaç duymadan doğrudan terminalde çalışan
kendi kendine yeten hibrit yapay zeka orkestrasyon motoru.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Windows konsolunda UTF-8 çıktısı ve renklendirme desteği
try:
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr.encoding != "utf-8":
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Çekirdek modülleri içe aktar
from core.dispatcher import Dispatcher
CLIOrchestrator = Dispatcher

from core.router import IntelligentRouter
ModelRouter = IntelligentRouter

from core.quota_manager import QuotaManager
from core.planner import TaskPlanner
from core.parallel_executor import ParallelExecutor
from core.session_memory import SessionMemory
from core.workspace_builder import WorkspaceBuilder
from core.usage_tracker import UsageTracker
import core.hardware as hardware
import core.benchmark as benchmark
from core.librarian import ModelLibrarian
from core.tech_scout import TechScout
import core.cli_registry as cli_registry
from core.cli_registry import discover_cli_tools, register_available_cli_wrappers
import core.provider_config as provider_config
from core.provider_config import load_provider_configs, build_wrapper
from wrappers.ollama_wrapper import OllamaWrapper
import wrappers


from core.software_swarm import SoftwareSwarm
from core.auto_healing import AutoHealingEngine


class WorkstationEngine:
    """
    4K AI WORKSTATION Çekirdek Motoru.
    Yerel Ollama, CLI ajanları ve yapılandırılmış harici sağlayıcıları birleştirir.
    """

    def __init__(self):
        self.quota_manager = QuotaManager()
        self.dispatcher = Dispatcher()
        self.router = IntelligentRouter(quota_manager=self.quota_manager)
        self.planner = TaskPlanner()
        self.executor = ParallelExecutor(self.dispatcher, self.router)
        self.librarian = ModelLibrarian()
        self.tech_scout = TechScout()
        self.session_memory = SessionMemory()
        self.usage_tracker = UsageTracker()
        self.workspace_builder = WorkspaceBuilder()
        self.software_swarm = SoftwareSwarm(
            router=self.router,
            dispatcher=self.dispatcher,
            workspace_builder=self.workspace_builder,
        )
        self.auto_healing = AutoHealingEngine(
            router=self.router,
            dispatcher=self.dispatcher,
            workspace_builder=self.workspace_builder,
        )
        self.registered_clis: List[str] = []
        self.loaded_providers: List[str] = []


_GLOBAL_ENGINE: Optional[WorkstationEngine] = None


def build_engine() -> WorkstationEngine:
    """
    4K AI WORKSTATION çekirdek motorunu kurar ve yapılandırır:
    1. Varsayılan Ollama sarmalayıcısını kaydeder.
    2. Sistemde kurulu CLI ajanlarını (Hermes, OpenCode, Codex, Claude Code) kaydeder.
    3. config/providers.json içindeki sağlayıcıları (YerelOllama, OpenRouterFree vb.) kaydeder.
    """
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is not None:
        return _GLOBAL_ENGINE

    engine = WorkstationEngine()

    # 1. Varsayılan yerel Ollama sarmalayıcısı
    engine.dispatcher.register_wrapper("Ollama", OllamaWrapper())

    # 2. Sistemde kurulu CLI ajanlarını otomatik keşfet ve kaydet
    engine.registered_clis = register_available_cli_wrappers(engine.dispatcher, engine.router)

    # 3. providers.json içindeki sağlayıcıları kaydet
    try:
        for cfg in load_provider_configs():
            engine.dispatcher.register_wrapper(cfg.name, build_wrapper(cfg))
            engine.router.register_tier(
                cfg.name,
                capability_score=cfg.capability_score,
                cost_per_token=cfg.cost_per_token,
                is_local=cfg.is_local,
                strengths=cfg.strengths,
            )
            engine.loaded_providers.append(cfg.name)
    except Exception as exc:
        print(f"[Uyarı] Sağlayıcılar yüklenirken hata: {exc}", file=sys.stderr)

    _GLOBAL_ENGINE = engine
    return engine


async def handle_command_async(cmd_line: str, engine: Optional[WorkstationEngine] = None) -> str:
    """
    Kullanıcının girdiği komut satırını asenkron olarak işler ve formatlı yanıt döndürür.
    """
    if engine is None:
        engine = build_engine()

    raw = cmd_line.strip()
    if not raw:
        return ""

    lower_raw = raw.lower()
    first_token = lower_raw.split()[0] if lower_raw.split() else ""

    # 1. USAGE / KULLANIM
    if lower_raw in ("usage", "kullanım", "kullanim"):
        return engine.usage_tracker.format_all_in_one_markdown(include_antigravity=True)

    # 2. STATUS / DURUM
    if lower_raw in ("status", "durum"):
        info = hardware.get_system_info()
        cli_tools = discover_cli_tools()
        active_wrappers = list(engine.dispatcher.wrappers.keys())
        quotas = engine.quota_manager.quotas

        lines = [
            "================================================================================",
            "📊 4K AI WORKSTATION - SİSTEM VE ÇALIŞMA DURUMU",
            "================================================================================",
            "🖥️  DONANIM:",
            f"   • GPU        : {info.gpu_name or 'NVIDIA GPU Tespit Edilemedi'} ({info.gpu_vram_gb or 0.0:.1f} GB VRAM)",
            f"   • Sistem RAM : {info.ram_gb:.1f} GB RAM",
            f"   • İşlemci    : {info.cpu_cores} Çekirdek ({info.os_name})",
            "",
            "🛠️  KURULU CLI AJANLARI:",
        ]
        for ct in cli_tools:
            status_icon = "🟢 [KURULU]" if ct.installed else "⚪ [YOK]"
            lines.append(f"   • {ct.name:<12}: {status_icon} -> {ct.binary_path or 'Bulunamadı'}")

        lines.extend([
            "",
            f"🤖 KAYITLI ÇALIŞMA MOTORLARI ({len(active_wrappers)} Adet):",
            f"   {', '.join(active_wrappers)}",
            "",
            "📈 KOTA VE MODEL KULLANIM DURUMU:",
        ])
        for qm, qinfo in quotas.items():
            used = qinfo.get("used", 0)
            lim = qinfo.get("limit")
            lim_str = f"{lim}" if lim is not None else "Sınırsız (0 TL / Yerel)"
            lines.append(f"   • {qm:<20}: {used} istek kullanıldı (Limit: {lim_str})")

        lines.append("================================================================================")
        return "\n".join(lines)

    # 3. PARALLEL <GÖREV>
    if first_token == "parallel":
        task_desc = raw[len("parallel"):].strip()
        if not task_desc:
            return "❌ Hata: 'parallel <görev>' formatında bir görev belirtmelisiniz.\nÖrnek: parallel Kullanıcı giriş ve ödeme modüllerini tasarla"

        sub_tasks = await engine.planner.decompose_with_llm(task_desc, engine.dispatcher, engine.router)
        results = await engine.executor.run_parallel(sub_tasks)

        for st in sub_tasks:
            assigned = st.get("assigned_model", "Ollama")
            engine.quota_manager.consume_quota(assigned)
            info = engine.usage_tracker.classify_model_or_tool(assigned)
            engine.usage_tracker.record_event(
                category="model",
                name=assigned,
                tier=info["tier"],
                is_free=info["is_free"],
                source="terminal_parallel",
            )

        synthesis = None
        if len(sub_tasks) > 1:
            synthesis = await engine.executor.synthesize_results(task_desc, sub_tasks, results)
            if synthesis:
                s_name = synthesis["model"]
                engine.quota_manager.consume_quota(s_name)
                s_info = engine.usage_tracker.classify_model_or_tool(s_name)
                engine.usage_tracker.record_event(
                    category="model",
                    name=s_name,
                    tier=s_info["tier"],
                    is_free=s_info["is_free"],
                    source="terminal_synthesis",
                )

        final_text = (
            synthesis["response"]
            if synthesis
            else "\n\n".join(r["response"] for r in results.values())
        )

        out_lines = [
            f"⚡ [PARALEL YÜRÜTME & MOA SENTEZİ] ({len(sub_tasks)} Alt Görev Eşzamanlı İşlendi)",
            "--------------------------------------------------------------------------------",
        ]
        for st in sub_tasks:
            out_lines.append(f"  • Alt Görev {st.get('id')}: {st.get('description')} -> [Model: {st.get('assigned_model')}]")
        out_lines.append("--------------------------------------------------------------------------------")
        out_lines.append(final_text)
        return "\n".join(out_lines)

    # 4. OTO / OTONOM <GÖREV VEYA PROJE FİKRİ> (Sıfır Bilgiyle Uçtan Uca Otonom Fabrika)
    if first_token in ("oto", "otonom", "auto"):
        goal_text = raw.split(maxsplit=1)[1].strip() if len(raw.split(maxsplit=1)) > 1 else ""
        if not goal_text:
            return (
                "❌ Hata: 'oto <hedef veya proje fikri>' formatında çağırmalısınız.\n"
                "Örnek: oto Çalışanların izin talep ettiği ve yöneticinin onayladığı SQLite tabanlı web paneli yap"
            )

        # Proje adını hedeften otomatik türet
        safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", goal_text[:30].strip()).strip("_").lower()
        if not safe_name:
            safe_name = "otonom_proje"
        base_projects_dir = os.path.join(str(Path.home()), "projects")
        os.makedirs(base_projects_dir, exist_ok=True)
        target_dir = os.path.join(base_projects_dir, safe_name)
        os.makedirs(target_dir, exist_ok=True)

        print(f"\n🚀 [4K AI WORKSTATION - OTONOM YAZILIM FABRİKASI BAŞLATILDI]")
        print(f"📁 Proje Hedef Klasörü: {target_dir}")
        print("--------------------------------------------------------------------------------")

        def _print_stage(stage: str, msg: str):
            print(f"   {msg}")

        # 1. Swarm ile Projeyi Üret
        swarm_res = engine.software_swarm.run_full_pipeline(
            user_goal=goal_text,
            workspace_dir=target_dir,
            model="auto",
            progress_callback=_print_stage,
        )

        startup_cmd = swarm_res.get("startup_command", "python server.py")

        # 2. Auto-Healing ile Projeyi Çalıştır ve Hataları Otomatik Onar
        print("--------------------------------------------------------------------------------")
        print("🧪 [Self-Healing & Doğrulama] Uygulama test ediliyor...")
        heal_res = engine.auto_healing.execute_with_healing(
            command=startup_cmd,
            workspace_dir=target_dir,
            timeout_seconds=8,
            progress_callback=_print_stage,
        )

        out_lines = [
            "",
            "================================================================================",
            "🎉 TEBRİKLER! OTONOM PROJENİZ BAŞARIYLA TAMAMLANDI VE ÇALIŞIR DURUMDA TESLİM EDİLDİ",
            "================================================================================",
            f"📌 Proje Başlığı   : {swarm_res['pm_spec'].get('project_title', 'Otonom Proje')}",
            f"📁 Proje Konumu    : {target_dir}",
            f"🛠️ Oluşturulanlar  : {len(swarm_res.get('created_files', []))} dosya diske yazıldı",
            f"⚡ Başlatma Komutu : {startup_cmd}",
        ]
        if heal_res.get("healing_applied"):
            out_lines.append(f"🔄 Kendi Kendini Onarma: {len(heal_res.get('healing_history', []))} hata arka planda otomatik düzeltildi.")

        out_lines.extend([
            "👉 Çalıştırmak İçin: 'calistir " + safe_name + "' yazabilirsiniz.",
            "================================================================================",
        ])
        return "\n".join(out_lines)

    # 5. PROJELER / PROJECTS
    if lower_raw in ("projeler", "projects", "projelerim"):
        base_projects_dir = os.path.join(str(Path.home()), "projects")
        if not os.path.exists(base_projects_dir):
            return f"📂 Henüz oluşturulmuş proje bulunmuyor ({base_projects_dir}).\nYeni proje üretmek için: 'oto <hedefiniz>'"

        entries = [
            d for d in os.listdir(base_projects_dir)
            if os.path.isdir(os.path.join(base_projects_dir, d))
        ]
        if not entries:
            return f"📂 Henüz oluşturulmuş proje bulunmuyor ({base_projects_dir}).\nYeni proje üretmek için: 'oto <hedefiniz>'"

        lines = [
            "================================================================================",
            f"📂 4K AI WORKSTATION - YÖNETİLEN PROJELER ({base_projects_dir})",
            "================================================================================",
        ]
        for p in entries:
            p_path = os.path.join(base_projects_dir, p)
            file_count = len([f for f in os.listdir(p_path) if os.path.isfile(os.path.join(p_path, f))])
            lines.append(f"   • {p:<25} ({file_count} dosya) -> Komut: 'calistir {p}'")
        lines.append("================================================================================")
        return "\n".join(lines)

    # 6. CALISTIR <PROJE_ADI>
    if first_token in ("calistir", "çalıştır", "start", "run") and len(raw.split()) > 1:
        p_name = raw.split(maxsplit=1)[1].strip().strip("\"'")
        base_projects_dir = os.path.join(str(Path.home()), "projects")
        p_path = os.path.join(base_projects_dir, p_name)
        if not os.path.exists(p_path):
            if os.path.exists(p_name):
                p_path = p_name
            else:
                return f"❌ Proje bulunamadı: '{p_name}'. Mevcut projeleri görmek için 'projeler' yazın."

        # Başlatılacak dosyayı bul (server.py, main.py, app.py)
        startup_file = "server.py"
        for candidate in ["server.py", "main.py", "app.py", "run.py"]:
            if os.path.exists(os.path.join(p_path, candidate)):
                startup_file = candidate
                break

        cmd = f"python {startup_file}"
        print(f"⚡ [Auto-Healing] '{p_name}' projesi başlatılıyor ve denetleniyor...")
        heal_res = engine.auto_healing.execute_with_healing(cmd, p_path, timeout_seconds=10)

        if heal_res["success"]:
            return f"✅ '{p_name}' projesi hatasız çalıştırıldı!\nÇıktı:\n{heal_res.get('stdout', '')}"
        else:
            return f"⚠️ '{p_name}' çalıştırılırken sorun çıktı:\n{heal_res.get('last_error', '')}"

    # 7. BUILD <HEDEF_KLASÖR> <GÖREV>
    if first_token == "build":
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            return "❌ Hata: 'build <hedef_klasör> <görev>' formatında çağrılmalıdır.\nÖrnek: build C:\\Users\\kloss\\my_project FastAPI tabanlı mini auth servisi oluştur"

        target_dir = parts[1].strip("\"'")
        task_desc = parts[2].strip()

        project_prompt = WorkspaceBuilder.build_project_prompt(task_desc)
        available = list(engine.dispatcher.wrappers.keys())
        chain = await engine.router.rank_escalation_chain(project_prompt, available)

        esc_result = await engine.dispatcher.dispatch_with_escalation(
            chain, project_prompt, workspace=target_dir
        )
        model_used = esc_result["model"]
        resp_text = esc_result["response"]

        engine.quota_manager.consume_quota(model_used)
        m_info = engine.usage_tracker.classify_model_or_tool(model_used)
        engine.usage_tracker.record_event(
            category="model",
            name=model_used,
            tier=m_info["tier"],
            is_free=m_info["is_free"],
            source="terminal_build",
        )

        files = WorkspaceBuilder.extract_files_from_response(resp_text)
        written_files = WorkspaceBuilder.apply_files(target_dir, files)

        out_lines = [
            "🏗️  [4K AI WORKSTATION - ÇALIŞMA ALANI İNŞASI TAMAMLANDI]",
            f"   • Hedef Klasör : {target_dir}",
            f"   • Üretici Model: {model_used} (Katman: {m_info['tier']})",
            f"   • Dosya Sayısı : {len(written_files)} dosya diske yazıldı",
            "--------------------------------------------------------------------------------",
        ]
        if written_files:
            for wf in written_files:
                out_lines.append(f"   [+] {wf}")
        else:
            out_lines.append("   ⚠️ Dosya bloğu ayrıştırılamadı. Model çıktısı doğrudan aşağıdadır:")
            out_lines.append(resp_text)

        return "\n".join(out_lines)

    # 5. BENCHMARK
    if lower_raw in ("benchmark", "test", "hiztesti"):
        lines = [
            "⚡ 4K AI WORKSTATION - DONANIM VE SİSTEM HIZ PERFORMANSI",
            "--------------------------------------------------------------------------------",
        ]
        c_score = benchmark.cpu_score()
        d_score = benchmark.disk_io_score()
        lines.append(f"  • Sentetik CPU Skoru     : {c_score} / 100")
        lines.append(f"  • Disk Okuma/Yazma Skoru : {d_score} / 100")

        # Yerel model benchmark dene
        lines.append("  • Yerel LLM Benchmark'ı çalıştırılıyor...")
        try:
            llm_res = await benchmark.llm_benchmark("qwen2.5-coder:14b")
            lines.append(f"    - Model         : {llm_res.get('model')}")
            lines.append(f"    - Üretim Hızı   : {llm_res.get('tokens_per_second', 0):.2f} Token/saniye")
            lines.append(f"    - İlk Token TTFT: {llm_res.get('ttft_ms', 0):.1f} ms")
            lines.append(f"    - Toplam Süre   : {llm_res.get('total_duration_ms', 0):.1f} ms")
        except Exception:
            try:
                llm_res = await benchmark.llm_benchmark("llama3")
                lines.append(f"    - Model         : {llm_res.get('model')}")
                lines.append(f"    - Üretim Hızı   : {llm_res.get('tokens_per_second', 0):.2f} Token/saniye")
                lines.append(f"    - İlk Token TTFT: {llm_res.get('ttft_ms', 0):.1f} ms")
            except Exception as e:
                lines.append(f"    - Ollama çevrimdışı veya test modeli bulunamadı ({e})")

        lines.append("--------------------------------------------------------------------------------")
        return "\n".join(lines)

    # 6. LIBRARIAN / MODELS
    if lower_raw in ("librarian", "models", "modeller"):
        ranked = engine.librarian.rank_models_for_task(task_type="general", max_vram_gb=12.0)
        lines = [
            "📚 4K AI WORKSTATION - DONANIMA VE GÖREVE UYGUN MODEL KATALOĞU (12 GB VRAM UYUMLU)",
            "--------------------------------------------------------------------------------",
            f"{'Model':<26} {'Sağlayıcı':<16} {'Puan':<6} {'Kod':<4} {'Mantık':<6} {'Hız':<4} {'Durum'}",
            "--------------------------------------------------------------------------------",
        ]
        for m in ranked[:12]:
            installed_str = "🟢 Kurulu" if m.get("installed_locally") else "⚪ Mevcut"
            lines.append(
                f"{m.get('id', ''):<26} {m.get('provider', ''):<16} {m.get('task_score', 0):<6.1f} "
                f"{m.get('coding', 0):<4} {m.get('reasoning', 0):<6} {m.get('speed', 0):<4} {installed_str}"
            )
        lines.append("--------------------------------------------------------------------------------")
        return "\n".join(lines)

    # 7. SCOUT
    if lower_raw in ("scout", "gozcu", "gözcü"):
        report = await engine.tech_scout.full_scout_report(include_online=False)
        summary = report.get("summary", {})
        findings = report.get("findings", [])

        lines = [
            "🔭 4K AI WORKSTATION - TEKNOLOJİ GÖZCÜSÜ DENETİM RAPORU",
            "--------------------------------------------------------------------------------",
            f"Donanım: {summary.get('gpu')} • {summary.get('vram_gb', 0):.1f} GB VRAM • {summary.get('ram_gb', 0):.1f} GB RAM",
            f"Kurulu CLI Ajanları: {', '.join(summary.get('installed_clis', []))}",
            "--------------------------------------------------------------------------------",
            "ÖNERİLER VE İYİLEŞTİRMELER:",
        ]
        for f in findings:
            prio = f.get("priority", "orta").upper()
            lines.append(f"\n[{prio}] {f.get('title')}")
            lines.append(f"  Tavsiye : {f.get('recommendation')}")
            if f.get("action_command"):
                lines.append(f"  Komut   : {f.get('action_command')}")
        return "\n".join(lines)

    # 8. HELP / YARDIM
    if lower_raw in ("help", "yardım", "yardim", "?"):
        return """
================================================================================
💡 4K AI WORKSTATION TERMİNAL KOMUTLARI
================================================================================
  🚀 OTONOM YAZILIM FABRİKASI & PROJE YÖNETİMİ:
  • oto <hedefiniz>           : Sıfır teknik bilgiyle projeyi PM, Mimar, Coder ve
                                Test ajanlarıyla otonom üretir, test eder ve linkini verir.
                                Örn: oto Çalışan izin takip web paneli yap
  • projeler / projects       : Bilgisayarınızdaki yönetilen tüm projeleri listeler.
  • calistir <proje_adı>      : Belirtilen projeyi kendi kendini onararak (Self-Healing)
                                arka planda hatasız şekilde başlatır.
  • parallel <görev>          : Görevi alt adımlara böler, eşzamanlı çalıştırır
                                ve MoA sentezleyicisi ile birleştirip sunar.
  • build <klasör> <görev>    : İstenen projeyi/modülü eksiksiz kodlar ve belirtilen
                                klasöre güvenle dosya olarak kaydeder.

  📊 SİSTEM, KOTA VE SAĞLAYICI DENETİMİ:
  • usage / kullanım          : 5 Saatlik & Haftalık firma bazlı (Google, Claude,
                                OpenAI, Yerel) doluluk ve $0.00 kota tasarruf tablosu.
  • status / durum            : Donanım (RTX 5070 Ti VRAM, RAM), kurulu CLI ajanları
                                ve aktif sağlayıcı durumlarını gösterir.
  • benchmark                 : CPU, Disk ve yerel GPU LLM hız testini çalıştırır.
  • models / librarian        : Donanımınıza (12GB VRAM) en uygun modelleri listeler.
  • scout                     : Açık kaynak ve sistem iyileştirme raporunu gösterir.

  💬 DOĞAL DİLLE SOHBET & GÖREV:
  • <herhangi bir soru/istek> : Otomatik Bilişsel Yönlendirici en doğru modeli ($0.00)
                                seçerek doğrudan yanıtlar ve işinizi halleder.
  • exit / çıkış              : Terminal Komut Merkezinden çıkar.
================================================================================
"""

    # 9. DİĞER TÜM GÖREV VE SORULAR (OTOMATİK ESKALASYON VE SOHBET)
    prompt = raw
    effective_prompt = engine.session_memory.build_contextual_prompt("terminal_session", prompt)
    available = list(engine.dispatcher.wrappers.keys())

    chain = await engine.router.rank_escalation_chain(effective_prompt, available)
    esc_result = await engine.dispatcher.dispatch_with_escalation(chain, effective_prompt)

    model_used = esc_result["model"]
    result_text = esc_result["response"]

    engine.quota_manager.consume_quota(model_used)
    m_info = engine.usage_tracker.classify_model_or_tool(model_used)
    engine.usage_tracker.record_event(
        category="model",
        name=model_used,
        tier=m_info["tier"],
        is_free=m_info["is_free"],
        source="terminal",
    )
    engine.session_memory.append_turn("terminal_session", prompt, result_text, model_used)

    tier_label = m_info["tier"].upper()
    free_label = "Ücretsiz (0 TL)" if m_info["is_free"] else "Kota / Abonelik"
    header = f"[{model_used} | Katman: {tier_label} | {free_label}]"

    return f"{header}\n\n{result_text}"


def handle_command(cmd_line: str, engine: Optional[WorkstationEngine] = None) -> str:
    """handle_command_async sarmalayıcısı (senkron CLI çağrıları için)."""
    return asyncio.run(handle_command_async(cmd_line, engine))


def interactive_repl():
    """Etkileşimli Terminal Komut Merkezi (REPL) Döngüsü."""
    engine = build_engine()
    info = hardware.get_system_info()

    banner = f"""
================================================================================
🖥️  4K AI WORKSTATION TERMİNAL (Sıfır Abonelik & Hibrit Orkestratör)
================================================================================
Donanım : {info.gpu_name or 'NVIDIA GPU'} ({info.gpu_vram_gb or 0.0:.1f} GB VRAM) • {info.ram_gb:.1f} GB RAM
Modeller: {len(engine.dispatcher.wrappers)} aktif motor ({', '.join(engine.dispatcher.wrappers.keys())})
Yardım  : 'help' veya 'yardım' | Kullanım Raporu: 'usage' | Durum: 'status'
Çıkış   : 'exit' veya 'çıkış'
================================================================================
"""
    print(banner)

    while True:
        try:
            cmd = input("4K-WORKSTATION> ").strip()
            if not cmd:
                continue
            if cmd.lower() in ("exit", "çıkış", "cikis", "quit", "q"):
                print("👋 4K AI WORKSTATION Terminalinden çıkıldı. İyi çalışmalar!")
                break

            output = handle_command(cmd, engine)
            print(f"\n{output}\n")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 4K AI WORKSTATION sonlandırıldı.")
            break
        except Exception as exc:
            print(f"\n❌ Hata oluştu: {exc}\n", file=sys.stderr)


def main():
    args = sys.argv[1:]
    if args:
        cmd_line = " ".join(args)
        out = handle_command(cmd_line)
        print(out)
    else:
        interactive_repl()


if __name__ == "__main__":
    main()
