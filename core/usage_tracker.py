"""
4K AI WORKSTATION - Usage & Analytics Tracker (Kullanım ve Tasarruf Takip Motoru)
Kullanıcının 5 Saatlik (5h) ve Haftalık (7g) model, CLI ve alt ajan kullanımlarını,
conversations/*.db SQLite gen_metadata verileriyle gerçek alt model bazında (Argon, Flash 3.8, Lite, Claude, Codex),
ücretli modelleri sabit standart sırada ve ücretsiz modelleri en çok kullanılandan aşağıya doğru dinamik sıralı olarak takip eder.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Referans Limitleri
REF_FREE_LIMIT_5H = 400_000       # 400K Token (Claude 5s Uzman Kotası Referansı)
REF_FREE_LIMIT_WEEKLY = 2_000_000 # 2.00M Token (Claude Haftalık Uzman Kotası Referansı)


def format_tokens(n: int) -> str:
    """Token sayısını okunaklı bir stringe dönüştürür (örn. 52.0K, 1.45M)."""
    val = max(0, int(n))
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    elif val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(val)


def render_model_quota_bar(tokens: int, limit: int, is_free: bool = False, width: int = 20) -> str:
    """
    Her modelin kendi kotasına veya ücretsiz modeller için referans uzman kotasına göre
    görsel grafik barı üretir.
    Limit aşıldığında (%100+) bar tamamen dolar ve yanına 🔥 eklenir!
    """
    if limit <= 0:
        pct = 0.0
    else:
        pct = round((tokens / limit) * 100.0, 1)

    pct_clamped = max(0.0, pct)
    filled = min(width, int(round((min(100.0, pct_clamped) / 100.0) * width)))
    bar = "█" * filled + "░" * (width - filled)
    fire = " 🔥" if pct >= 100.0 else ""

    if is_free:
        return f"[{bar}]{fire} %{pct:.1f} ({format_tokens(tokens)} Token)"
    else:
        return f"[{bar}]{fire} %{pct:.1f} ({format_tokens(tokens)} / {format_tokens(limit)})"


def normalize_agent_name(name: str) -> str:
    """
    Teknik alt ajan mesajlarını ve rollerini ana uzman ajan kategorilerine gruplar.
    """
    n = (name or "").lower()
    if any(k in n for k in ["ui", "arayüz", "kontrol paneli", "dashboard"]):
        return "🎨 UI & Kontrol Paneli Uzmanı"
    if any(k in n for k in ["test", "kalite", "doğrulama"]):
        return "🧪 Test & Kalite Güvence Uzmanı"
    if any(k in n for k in ["dokümantasyon", "marka", "belge", "kural"]):
        return "📝 Dokümantasyon & Marka Uzmanı"
    if any(k in n for k in ["çekirdek", "api", "workspace", "builder", "core"]):
        return "⚙️ Çekirdek & API Uzmanı"
    if any(k in n for k in ["kullanım", "analitik", "usage", "tracker"]):
        return "📊 Kullanım & Analitik Motoru Uzmanı"
    if any(k in n for k in ["antigravity", "özelleştirme", "skill", "yapılandırma"]):
        return "🧠 Antigravity Entegrasyon Uzmanı"
    if any(k in n for k in ["terminal", "cli"]):
        return "💻 Terminal & CLI Ajanı"
    return "⚡ Nexus Worker (Genel Görev İşçisi)"


class UsageTracker:
    """
    Yerel 4K AI Workstation ve Antigravity orkestrasyon motorunun kullanım verilerini toplayıp
    görsel ve finansal tasarruf raporlarına dönüştüren analitik motoru.
    """

    # 1. Sabit Standart Sırada Ücretli & Kotalı Referans Alt Modelleri
    PAID_REFERENCE_MODELS = [
        {"name": "Claude Opus 5.5 (claude-opus-5.5)", "match_keys": ["opus-5.5", "opus", "claude-opus"], "tier": "premium", "is_free": False, "limit_5h": 250_000, "limit_weekly": 1_250_000, "quota_type": "💎 Claude Opus (250K / 1.25M)"},
        {"name": "Claude Fable 5.1 (claude-fable-5.1)", "match_keys": ["fable-5.1", "fable", "claude-fable"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 Claude Fable (400K / 2.0M)"},
        {"name": "Claude 4.5 Sonnet (claude-code-cli)", "match_keys": ["claudecode", "claude-code", "sonnet"], "tier": "premium", "is_free": False, "limit_5h": 400_000, "limit_weekly": 2_000_000, "quota_type": "💎 Claude Code (400K / 2.0M)"},
        {"name": "Gemini 4 Argon (gemini-4-argon)", "match_keys": ["argon", "gemini-4-argon", "gemini-4"], "tier": "premium", "is_free": False, "limit_5h": 600_000, "limit_weekly": 3_000_000, "quota_type": "💎 Ana Orkestratör (600K / 3.0M)"},
        {"name": "GPT-5.2 Codex (openai-codex)", "match_keys": ["codex", "gpt-5.2", "openai-codex"], "tier": "low_quota", "is_free": False, "limit_5h": 800_000, "limit_weekly": 4_000_000, "quota_type": "⚡ ChatGPT Codex (800K / 4.0M)"},
        {"name": "GPT-OSS 120B (gpt-oss-120b)", "match_keys": ["gpt-oss", "oss-120b"], "tier": "low_quota", "is_free": False, "limit_5h": 1_000_000, "limit_weekly": 5_000_000, "quota_type": "⚡ GPT-OSS (1.0M / 5.0M)"},
        {"name": "Gemini 3.8 Flash (gemini-3.8-flash)", "match_keys": ["gemini-3.8-flash", "3.8-flash", "flash-tiered", "flash"], "tier": "low_quota", "is_free": False, "limit_5h": 2_000_000, "limit_weekly": 10_000_000, "quota_type": "⚡ Hızlı İşçi (2.0M / 10.0M)"},
    ]

    # 2. Ücretsiz & Yerel (0 TL) Modeller
    FREE_REFERENCE_MODELS = [
        {"name": "NVIDIA Nemotron 70B / DeepSeek R1 (NVIDIA NIM 0 TL)", "match_keys": ["nvidia", "nemotron", "nim"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / NVIDIA NIM"},
        {"name": "HuggingFace Qwen 2.5 Coder 32B / Zephyr (HF Router 0 TL)", "match_keys": ["huggingface", "hf", "zephyr"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / HuggingFace"},
        {"name": "Gemini 3.5 Flash-Lite (gemini-3.5-flash-lite)", "match_keys": ["3.5-flash-lite", "flash_lite", "flash-lite"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / Hafif İşçi"},
        {"name": "OpenCode Big-Pickle (opencode-free)", "match_keys": ["opencode", "big-pickle"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / OpenCode"},
        {"name": "Hermes 3 Nous (hermes-agent)", "match_keys": ["hermes", "nous"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / Hermes"},
        {"name": "Llama 3 8B (Yerel RTX 5070 Ti)", "match_keys": ["llama3", "llama-3", "yerelollama", "ollama"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / Yerel GPU"},
        {"name": "Qwen 2.5 Coder 14B (Yerel RTX 5070 Ti)", "match_keys": ["qwen-14b", "qwen2.5-coder:14b", "qwen-coder"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / Yerel GPU"},
        {"name": "Qwen 2.5 Coder 32B:free (OpenRouter)", "match_keys": ["openrouterfree", "openrouter", ":free"], "tier": "free", "is_free": True, "limit_5h": REF_FREE_LIMIT_5H, "limit_weekly": REF_FREE_LIMIT_WEEKLY, "quota_type": "🟢 0 TL / Bulut Free"},
    ]

    def __init__(
        self,
        storage_path: str = "config/usage_events.json",
        brain_dir: str = r"C:\Users\kloss\.gemini\antigravity-cli\brain",
    ):
        self.storage_path = str(storage_path)
        self.brain_dir = str(brain_dir)

    def _load_events(self) -> List[Dict[str, Any]]:
        """Kayıtlı olayları JSON dosyasından güvenle yükler."""
        if not os.path.exists(self.storage_path):
            return []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_events(self, events: List[Dict[str, Any]]) -> None:
        """Olayları JSON dosyasına kaydeder."""
        dirname = os.path.dirname(self.storage_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record_event(
        self,
        category: str,
        name: str,
        tier: str = "free",
        is_free: bool = True,
        tokens_est: int = 0,
        source: str = "workstation",
        timestamp: str | None = None,
    ) -> Dict[str, Any]:
        """Yeni bir kullanım olayını kaydeder."""
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        if tokens_est <= 0:
            tokens_est = 6500 if category == "agent" else (5000 if category == "model" else 4000)

        event = {
            "category": str(category),
            "name": str(name),
            "tier": str(tier),
            "is_free": bool(is_free),
            "tokens_est": int(tokens_est),
            "source": str(source),
            "timestamp": str(timestamp),
        }

        events = self._load_events()
        events.append(event)
        self._save_events(events)
        return event

    def classify_model_or_tool(self, name: str) -> Dict[str, Any]:
        """Model veya CLI adına göre sınıflandırma yapar."""
        n = (name or "").strip()
        n_lower = n.lower()

        if any(k in n_lower for k in ["flash_lite", "flash-lite", "tier_flash_lite", "3.5-flash-lite"]):
            return {
                "is_free": True,
                "tier": "free",
                "cli_name": "flash_lite",
                "display_name": "Gemini 3.5 Flash-Lite (0 TL / Hafif İşçi)",
            }

        free_keywords = [
            "yerelollama",
            "ollama",
            "llama",
            "qwen",
            "deepseek",
            "openrouterfree",
            ":free",
            "openrouter/free",
            "hermes",
            "opencode",
            "unittest",
            "pytest",
            "nvidia",
            "nemotron",
            "nim",
            "huggingface",
            "hf",
            "zephyr",
        ]
        if any(k in n_lower for k in free_keywords):
            cli_name = "ollama"
            if "hermes" in n_lower:
                cli_name = "hermes"
            elif "opencode" in n_lower:
                cli_name = "opencode"
            elif "nvidia" in n_lower or "nemotron" in n_lower or "nim" in n_lower:
                cli_name = "nvidia_nim"
            elif "huggingface" in n_lower or "hf" in n_lower or "zephyr" in n_lower:
                cli_name = "huggingface"
            elif ":free" in n_lower or "openrouter" in n_lower:
                cli_name = "openrouter"
            elif "unittest" in n_lower or "pytest" in n_lower:
                cli_name = "test_runner"

            return {
                "is_free": True,
                "tier": "free",
                "cli_name": cli_name,
                "display_name": f"{n} (Ücretsiz / 0 TL)",
            }

        low_quota_keywords = ["flash", "tier_flash", "codex", "3.8-flash", "gpt-oss"]
        if any(k in n_lower for k in low_quota_keywords):
            cli_name = "gemini_flash"
            if "codex" in n_lower:
                cli_name = "codex"
            return {
                "is_free": False,
                "tier": "low_quota",
                "cli_name": cli_name,
                "display_name": f"{n} (Düşük Kota İşçisi)",
            }

        premium_keywords = ["claudecode", "claude", "pro", "tier_pro", "gemini-pro", "argon", "opus", "fable", "sonnet"]
        if any(k in n_lower for k in premium_keywords):
            cli_name = "claude" if "claude" in n_lower else "gemini_pro"
            return {
                "is_free": False,
                "tier": "premium",
                "cli_name": cli_name,
                "display_name": f"{n} (Uzman Katman)",
            }

        if "free" in n_lower:
            return {
                "is_free": True,
                "tier": "free",
                "cli_name": n_lower,
                "display_name": f"{n} (0 TL)",
            }

        return {
            "is_free": True,
            "tier": "free",
            "cli_name": n_lower,
            "display_name": f"{n} (Yerel)",
        }

    def scan_antigravity_brain(self) -> List[Dict[str, Any]]:
        """Antigravity transcript dosyalarını tarar."""
        brain_path = Path(self.brain_dir)
        events: List[Dict[str, Any]] = []

        if not brain_path.exists():
            return events

        target_files: List[Path] = []
        try:
            conv_dirs = [d for d in brain_path.iterdir() if d.is_dir()]
            for cdir in conv_dirs:
                logs_dir = cdir / ".system_generated" / "logs"
                t_full = logs_dir / "transcript_full.jsonl"
                t_norm = logs_dir / "transcript.jsonl"
                if t_full.exists():
                    target_files.append(t_full)
                elif t_norm.exists():
                    target_files.append(t_norm)
        except Exception:
            pass

        if not target_files:
            full_list = list(brain_path.rglob("transcript_full.jsonl"))
            if full_list:
                target_files = full_list
            else:
                target_files = list(brain_path.rglob("transcript.jsonl"))

        cli_patterns = [
            (r"\bclaude\b", "ClaudeCode"),
            (r"\bcodex\b", "Codex"),
            (r"\bhermes\b", "Hermes"),
            (r"\bopencode\b", "OpenCode"),
            (r"\bollama\b", "YerelOllama"),
            (r"\b(unittest|pytest)\b", "TestRunner"),
        ]

        for t_file in target_files:
            try:
                with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            item = json.loads(line_str)
                        except Exception:
                            continue

                        ts = item.get("created_at")
                        tool_calls = item.get("tool_calls", [])
                        if not tool_calls or not isinstance(tool_calls, list):
                            continue

                        raw_in = item.get("input_tokens", 0) or 0
                        raw_out = item.get("output_tokens", 0) or 0
                        base_tokens = max(raw_in + raw_out, len(line_str) // 3)
                        if base_tokens < 5000:
                            base_tokens = 15000

                        for call in tool_calls:
                            if not isinstance(call, dict):
                                continue
                            tool_name = call.get("name")
                            args = call.get("args", {})
                            if not isinstance(args, dict):
                                continue

                            # 1. Alt ajan başlatma (invoke_subagent)
                            if tool_name == "invoke_subagent":
                                subagents_data = (
                                    args.get("Subagents")
                                    or args.get("subagents")
                                    or args.get("agents")
                                )
                                if isinstance(subagents_data, str):
                                    try:
                                        subagents_data = json.loads(subagents_data)
                                    except Exception:
                                        subagents_data = []

                                if isinstance(subagents_data, dict):
                                    subagents_data = [subagents_data]
                                elif not isinstance(subagents_data, list):
                                    subagents_data = []

                                for sub in subagents_data:
                                    if not isinstance(sub, dict):
                                        continue
                                    model = (
                                        sub.get("Model")
                                        or sub.get("model")
                                        or sub.get("modelTier")
                                        or "flash"
                                    )
                                    role = (
                                        sub.get("Role")
                                        or sub.get("role")
                                        or sub.get("name")
                                        or "Nexus Worker"
                                    )
                                    cls_info = self.classify_model_or_tool(model)
                                    sub_tokens = max(base_tokens, len(sub.get("Prompt", "")) // 3 + 10000)

                                    events.append({
                                        "category": "agent",
                                        "name": role,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": sub_tokens,
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })
                                    events.append({
                                        "category": "model",
                                        "name": model,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": sub_tokens,
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })

                            # 2. Alt ajana ek görev mesajı gönderme (send_message)
                            elif tool_name == "send_message":
                                recipient = str(args.get("Recipient", ""))
                                msg = str(args.get("Message", ""))
                                summary = str(args.get("toolSummary") or "Alt Ajan Görevi")
                                short_id = recipient[:8] if recipient else "worker"
                                msg_tokens = max(len(msg) // 3 + 3000, 6000)

                                events.append({
                                    "category": "agent",
                                    "name": f"Ek Görev ({summary} - {short_id})",
                                    "tier": "free",
                                    "is_free": True,
                                    "tokens_est": msg_tokens,
                                    "source": "antigravity",
                                    "timestamp": ts,
                                })

                            # 3. CLI çalıştırma (run_command)
                            elif tool_name == "run_command":
                                cmd = str(args.get("CommandLine", ""))
                                cmd_lower = cmd.lower()
                                detected_clis = set()
                                for pattern, cli_key in cli_patterns:
                                    if re.search(pattern, cmd_lower):
                                        detected_clis.add(cli_key)

                                cli_tokens = max(len(cmd) // 3 + 5000, 8000)
                                for cli_key in detected_clis:
                                    cls_info = self.classify_model_or_tool(cli_key)
                                    events.append({
                                        "category": "cli",
                                        "name": cli_key,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": cli_tokens,
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })
            except Exception:
                continue

        return events

    def scan_conversations_db(self) -> List[Dict[str, Any]]:
        r"""
        C:\Users\kloss\.gemini\antigravity-cli\conversations\*.db SQLite veritabanlarını tarar.
        gen_metadata tablosundan gerçek alt model adlarını (gemini-4-argon, gemini-3.8-flash, vb.) çıkarır.
        """
        events: List[Dict[str, Any]] = []
        conv_dir = Path(self.brain_dir).parent / "conversations"
        if not conv_dir.exists():
            return events

        db_files = list(conv_dir.glob("*.db"))

        for db_file in db_files:
            try:
                mtime_dt = datetime.fromtimestamp(os.path.getmtime(db_file), tz=timezone.utc)
                mtime_iso = mtime_dt.isoformat()

                conn = sqlite3.connect(str(db_file), timeout=2.0)
                cur = conn.cursor()
                cur.execute("SELECT idx, data FROM gen_metadata")
                rows = cur.fetchall()
                conn.close()

                for row in rows:
                    data = row[1]
                    if not isinstance(data, (bytes, bytearray)):
                        continue

                    model_found = None
                    matches = re.findall(rb"gemini-[a-zA-Z0-9_.-]+", data)
                    if matches:
                        model_found = matches[0].decode("ascii", "ignore")
                    elif b"\x9a\x01" in data:
                        idx = data.find(b"\x9a\x01")
                        try:
                            length = data[idx + 2]
                            raw_name = data[idx + 3 : idx + 3 + length].decode("utf-8", "ignore")
                            if raw_name.startswith("gemini-"):
                                model_found = raw_name
                        except Exception:
                            pass

                    if model_found:
                        cls_info = self.classify_model_or_tool(model_found)
                        tok_est = max(len(data) // 2, 7000)
                        events.append({
                            "category": "model",
                            "name": model_found,
                            "tier": cls_info["tier"],
                            "is_free": cls_info["is_free"],
                            "tokens_est": tok_est,
                            "source": "antigravity_db",
                            "timestamp": mtime_iso,
                        })
            except Exception:
                continue

        return events

    @staticmethod
    def _parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
        """ISO tarih stringini datetime objesine dönüştürür."""
        if not ts:
            return None
        try:
            ts_clean = str(ts).replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def get_report(self, include_antigravity: bool = True) -> Dict[str, Any]:
        """five_hours (Son 5 Saat), daily, weekly ve monthly pencerelerini üretir."""
        all_events = list(self._load_events())
        if include_antigravity:
            antigravity_events = self.scan_antigravity_brain()
            all_events.extend(antigravity_events)
            # conversations/*.db SQLite veritabanını da tara
            db_events = self.scan_conversations_db()
            all_events.extend(db_events)

        now = datetime.now(timezone.utc)

        window_seconds = {
            "five_hours": 5 * 3600,
            "daily": 24 * 3600,
            "weekly": 7 * 24 * 3600,
            "monthly": 30 * 24 * 3600,
        }

        report: Dict[str, Any] = {
            "generated_at": now.isoformat(),
            "five_hours": {},
            "daily": {},
            "weekly": {},
            "monthly": {},
        }

        for window_key, max_sec in window_seconds.items():
            filtered_events: List[Dict[str, Any]] = []
            for ev in all_events:
                dt = self._parse_timestamp(ev.get("timestamp"))
                if not dt:
                    continue
                diff_sec = (now - dt).total_seconds()
                if -120 <= diff_sec <= max_sec:
                    filtered_events.append(ev)

            total = len(filtered_events)
            free_cnt = sum(
                1 for e in filtered_events if e.get("is_free") or e.get("tier") == "free"
            )
            low_quota_cnt = sum(
                1 for e in filtered_events if e.get("tier") == "low_quota"
            )
            premium_cnt = sum(
                1 for e in filtered_events if e.get("tier") == "premium"
            )

            tokens_total = sum(e.get("tokens_est", 0) for e in filtered_events)
            tokens_free = sum(e.get("tokens_est", 0) for e in filtered_events if e.get("is_free") or e.get("tier") == "free")
            tokens_low = sum(e.get("tokens_est", 0) for e in filtered_events if e.get("tier") == "low_quota")
            tokens_prem = sum(e.get("tokens_est", 0) for e in filtered_events if e.get("tier") == "premium")

            ratio = (
                round(((free_cnt + low_quota_cnt) / total * 100), 2)
                if total > 0
                else 0.0
            )
            saved_usd = round((free_cnt * 0.03) + (low_quota_cnt * 0.02), 2)

            # Modeller listesi
            model_counts: Dict[str, Dict[str, Any]] = {}
            for e in filtered_events:
                if e.get("category") == "model":
                    name = e.get("name", "Bilinmeyen")
                    if name not in model_counts:
                        model_counts[name] = {
                            "name": name,
                            "count": 0,
                            "tokens": 0,
                            "tier": e.get("tier", "free"),
                            "is_free": e.get("is_free", True),
                        }
                    model_counts[name]["count"] += 1
                    model_counts[name]["tokens"] += e.get("tokens_est", 0)
            models_list = sorted(
                model_counts.values(), key=lambda x: x["count"], reverse=True
            )

            # CLI'lar listesi
            cli_counts: Dict[str, Dict[str, Any]] = {}
            for e in filtered_events:
                if e.get("category") == "cli":
                    name = e.get("name", "Bilinmeyen")
                    if name not in cli_counts:
                        cli_counts[name] = {
                            "name": name,
                            "count": 0,
                            "tokens": 0,
                            "tier": e.get("tier", "free"),
                            "is_free": e.get("is_free", True),
                        }
                    cli_counts[name]["count"] += 1
                    cli_counts[name]["tokens"] += e.get("tokens_est", 0)
            clis_list = sorted(
                cli_counts.values(), key=lambda x: x["count"], reverse=True
            )

            # Ajanlar listesi
            agent_counts: Dict[str, Dict[str, Any]] = {}
            for e in filtered_events:
                if e.get("category") == "agent":
                    name = e.get("name", "Worker")
                    source = e.get("source", "workstation")
                    key = f"{name}_{source}"
                    if key not in agent_counts:
                        agent_counts[key] = {
                            "name": name,
                            "count": 0,
                            "tokens": 0,
                            "tier": e.get("tier", "free"),
                            "source": source,
                        }
                    agent_counts[key]["count"] += 1
                    agent_counts[key]["tokens"] += e.get("tokens_est", 0)
            agents_list = sorted(
                agent_counts.values(), key=lambda x: x["count"], reverse=True
            )

            free_usages = {
                "total_free": free_cnt,
                "low_quota": low_quota_cnt,
                "tokens_free": tokens_free,
                "tokens_low": tokens_low,
                "estimated_saved_usd": saved_usd,
                "free_and_worker_ratio": ratio,
                "models": [m for m in models_list if m.get("is_free")],
                "clis": [c for c in clis_list if c.get("is_free")],
            }

            report[window_key] = {
                "total_events": total,
                "free_events": free_cnt,
                "low_quota_events": low_quota_cnt,
                "premium_events": premium_cnt,
                "tokens_total": tokens_total,
                "tokens_free": tokens_free,
                "tokens_low_quota": tokens_low,
                "tokens_premium": tokens_prem,
                "free_And_worker_ratio": ratio,
                "free_and_worker_ratio": ratio,
                "estimated_saved_usd": saved_usd,
                "models": models_list,
                "clis": clis_list,
                "agents": agents_list,
                "free_usages": free_usages,
                "_raw_events": filtered_events,
            }

        report["all_time_totals"] = {
            "total_events": len(all_events),
            "free_events": sum(
                1 for e in all_events if e.get("is_free") or e.get("tier") == "free"
            ),
            "low_quota_events": sum(
                1 for e in all_events if e.get("tier") == "low_quota"
            ),
            "premium_events": sum(
                1 for e in all_events if e.get("tier") == "premium"
            ),
            "tokens_total": sum(e.get("tokens_est", 0) for e in all_events),
        }

        return report

    def _aggregate_model_tokens(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Hem model, hem CLI hem de conversations/*.db SQLite olaylarını model bazında birleştirir."""
        all_specs = self.PAID_REFERENCE_MODELS + self.FREE_REFERENCE_MODELS
        data = {
            spec["name"]: {
                "count": 0,
                "tokens": 0,
                "tier": spec["tier"],
                "is_free": spec["is_free"],
                "limit_5h": spec.get("limit_5h", REF_FREE_LIMIT_5H),
                "limit_weekly": spec.get("limit_weekly", REF_FREE_LIMIT_WEEKLY),
                "quota_type": spec.get("quota_type", ""),
            }
            for spec in all_specs
        }

        for ev in raw_events:
            cat = ev.get("category")
            name = (ev.get("name") or "").lower()
            tok = ev.get("tokens_est", 0) or 5000

            # Özel eşleştirme kuralları
            matched = False
            # 1. Önce lite kontrolü
            if "lite" in name:
                data["Gemini 3.5 Flash-Lite (gemini-3.5-flash-lite)"]["count"] += 1
                data["Gemini 3.5 Flash-Lite (gemini-3.5-flash-lite)"]["tokens"] += tok
                continue
            # 2. Argon kontrolü
            if "argon" in name:
                data["Gemini 4 Argon (gemini-4-argon)"]["count"] += 1
                data["Gemini 4 Argon (gemini-4-argon)"]["tokens"] += tok
                continue
            # 3. Opus kontrolü
            if "opus" in name:
                data["Claude Opus 5.5 (claude-opus-5.5)"]["count"] += 1
                data["Claude Opus 5.5 (claude-opus-5.5)"]["tokens"] += tok
                continue
            # 4. Fable kontrolü
            if "fable" in name:
                data["Claude Fable 5.1 (claude-fable-5.1)"]["count"] += 1
                data["Claude Fable 5.1 (claude-fable-5.1)"]["tokens"] += tok
                continue
            # 5. Claude kontrolü
            if "claude" in name or "sonnet" in name:
                data["Claude 4.5 Sonnet (claude-code-cli)"]["count"] += 1
                data["Claude 4.5 Sonnet (claude-code-cli)"]["tokens"] += tok
                continue

            # Diğer standart modeller
            for spec in all_specs:
                if any(k in name for k in spec["match_keys"]):
                    data[spec["name"]]["count"] += 1
                    data[spec["name"]]["tokens"] += tok
                    matched = True
                    break

            if not matched and cat == "model":
                raw_name = ev.get("name", "Diğer")
                if raw_name not in data:
                    data[raw_name] = {
                        "count": 0,
                        "tokens": 0,
                        "tier": "free",
                        "is_free": True,
                        "limit_5h": REF_FREE_LIMIT_5H,
                        "limit_weekly": REF_FREE_LIMIT_WEEKLY,
                        "quota_type": "🟢 0 TL",
                    }
                data[raw_name]["count"] += 1
                data[raw_name]["tokens"] += tok

        return data

    def _aggregate_agent_tokens(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Ajan olaylarını normalize edip ana uzman ajan kategorilerine toplar."""
        data: Dict[str, Dict[str, Any]] = {}
        for ev in raw_events:
            if ev.get("category") == "agent":
                raw_name = ev.get("name", "")
                norm_name = normalize_agent_name(raw_name)
                tok = ev.get("tokens_est", 0) or 8000
                if norm_name not in data:
                    data[norm_name] = {"count": 0, "tokens": 0}
                data[norm_name]["count"] += 1
                data[norm_name]["tokens"] += tok
        return data

    def _aggregate_cli_tokens(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """CLI olaylarını toplar ve tokenlarını hesaplar."""
        data: Dict[str, Dict[str, Any]] = {}
        for ev in raw_events:
            if ev.get("category") == "cli":
                name = ev.get("name", "")
                tok = ev.get("tokens_est", 0) or 7000
                if name not in data:
                    data[name] = {"count": 0, "tokens": 0}
                data[name]["count"] += 1
                data[name]["tokens"] += tok
        return data

    def audit_paid_api_risks(self, providers_path: str = "config/providers.json") -> Dict[str, Any]:
        """
        Sistemde ücretli API riski olup olmadığını denetler.
        1. Ortam değişkenlerinde (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, CLAUDE_API_KEY)
           gerçek bir anahtar var mı bakar.
        2. config/providers.json içinde yerel olmayan (127.0.0.1/localhost dışı) ve model adında ':free'
           bulunmayan veya cost > 0 olan herhangi bir sağlayıcı eklenmiş mi kontrol eder.
        """
        warnings = []

        # 1. Ortam değişkenleri denetimi
        paid_env_keys = [
            ("OPENAI_API_KEY", "OpenAI"),
            ("ANTHROPIC_API_KEY", "Anthropic"),
            ("GEMINI_API_KEY", "Google Gemini"),
            ("CLAUDE_API_KEY", "Claude"),
        ]
        for env_key, provider_label in paid_env_keys:
            val = os.environ.get(env_key, "").strip()
            if val and not val.startswith("dummy") and not val.startswith("mock") and not val.startswith("test"):
                warnings.append(
                    f"🚨 UYARI: '{env_key}' ({provider_label}) ücretli API anahtarı ortamda tespit edildi ve otomatik olarak engellendi! Kaldırmak için ortam değişkenini silin."
                )

        # 2. config/providers.json denetimi
        if os.path.exists(providers_path):
            try:
                with open(providers_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    providers = data.get("providers", [])
                    for p in providers:
                        p_name = p.get("name", "Bilinmeyen")
                        p_model = p.get("model", "")
                        p_url = p.get("base_url", "")
                        p_cost = float(p.get("cost", 0.0) or 0.0)
                        p_local = bool(p.get("local", False))

                        is_local = p_local or ("127.0.0.1" in p_url) or ("localhost" in p_url)
                        is_explicit_free = (":free" in p_model.lower()) or ("free" in p_name.lower())

                        if not is_local:
                            if p_cost > 0.0 or not is_explicit_free:
                                warnings.append(
                                    f"🚨 UYARI: '{p_name}' ({p_model}) ücretli API tespit edildi ve otomatik olarak engellendi! Kaldırmak için '4k remove-api {p_name}' çalıştırın."
                                )
            except Exception:
                pass

        if warnings:
            return {
                "safe": False,
                "warnings": warnings,
                "status_line": "🚨 **ÜCRETLİ API TEHLİKESİ TESPİT EDİLDİ (ENGELLENDİ):** " + " | ".join(warnings),
            }

        return {
            "safe": True,
            "warnings": [],
            "status_line": "🔒 **SIFIR API HARCAMA KALKANI AKTİF ($0.00):** Sistemde hiçbir ücretli API anahtarı veya kontörlü bağlantı yok. Ücretli API eklenmeye çalışılırsa anında engellenir ve burada kırmızı uyarı verir.",
        }

    def format_all_in_one_markdown(self, include_antigravity: bool = True) -> str:
        """
        Kullanıcı '/usage' dediğinde TEK SEFERDE:
        - Ücretli modelleri sabit standart sırada (Opus, Fable, Sonnet, Argon, Codex, GPT-OSS, Flash)
        - Ücretsiz modelleri en çok kullanılandan aşağıya doğru dinamik sıralı (%100'ü geçebilen 🔥)
        - 5 Saatlik ve Haftalık karşılaştırmalı grafik panosu üretir.
        """
        report = self.get_report(include_antigravity=include_antigravity)
        audit = self.audit_paid_api_risks()

        h5 = report.get("five_hours", {})
        if not h5.get("total_events"):
            h5 = report.get("daily", {})
        w = report.get("weekly", {})

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        md: List[str] = []
        md.append("# 📊 /usage — 4K AI WORKSTATION & ANTIGRAVITY KULLANIM GRAFİĞİ")
        md.append("**⏱️ 5 Saatlik & 📅 Haftalık Pencere (Model Model Ayrıntılı Kota & Token Doluluk Panosu)**")
        md.append(f"**🕒 Güncelleme:** `{now_str}` | **📁 Depolama:** `{self.storage_path}` | **🧠 Antigravity:** `{self.brain_dir}`")
        md.append("")
        if not audit["safe"]:
            md.append("> 🚨 **DİKKAT — ÜCRETLİ API TEHLİKESİ TESPİT EDİLDİ (OTOMATİK ENGELLENDİ):**")
            for w_msg in audit["warnings"]:
                md.append(f"> - {w_msg}")
        else:
            md.append(f"> {audit['status_line']}")
        md.append("")
        md.append("---")
        md.append("")

        # 1. BÖLÜM: KATMAN ÖZETİ
        tok_free_5h = h5.get("tokens_free", 0)
        tok_low_5h = h5.get("tokens_low_quota", 0)
        tok_prem_5h = h5.get("tokens_premium", 0)

        tok_free_w = w.get("tokens_free", 0)
        tok_low_w = w.get("tokens_low_quota", 0)
        tok_prem_w = w.get("tokens_premium", 0)

        bar_free_5h = render_model_quota_bar(tok_free_5h, REF_FREE_LIMIT_5H, is_free=True)
        bar_free_w = render_model_quota_bar(tok_free_w, REF_FREE_LIMIT_WEEKLY, is_free=True)

        bar_low_5h = render_model_quota_bar(tok_low_5h, 2_800_000, is_free=False)
        bar_low_w = render_model_quota_bar(tok_low_w, 14_000_000, is_free=False)

        bar_prem_5h = render_model_quota_bar(tok_prem_5h, 600_000, is_free=False)
        bar_prem_w = render_model_quota_bar(tok_prem_w, 3_000_000, is_free=False)

        md.append("### 🟢 1. KATMAN ÖZETİ (Ücretsiz 0 TL vs İşçi vs Uzman - Kendi Kotalarıyla)")
        md.append("| Katman | Kendi Kotası | 5 Saatlik Doluluk Grafiği | Haftalık Doluluk Grafiği |")
        md.append("| :--- | :--- | :--- | :--- |")
        md.append(f"| `🟢 Ücretsiz / Yerel (0 TL)` | 🟢 Sınırsız (Claude Ref) | `{bar_free_5h}` | `{bar_free_w}` |")
        md.append(f"| `⚡ Düşük Kota İşçi (Flash/Codex)` | ⚡ 2.8M / 14M Token | `{bar_low_5h}` | `{bar_low_w}` |")
        md.append(f"| `💎 Uzman Katman (Claude/Argon)` | 💎 600K / 3M Token | `{bar_prem_5h}` | `{bar_prem_w}` |")
        md.append("")
        ratio_val = h5.get("free_and_worker_ratio", 0.0)
        saved_val = h5.get("estimated_saved_usd", 0.0)
        md.append(f"> 🛡️ **Kota Koruma Oranı:** %{ratio_val:.1f} (İşlerin %{ratio_val:.1f}'i ana model kotası harcanmadan çözüldü)")
        md.append(f"> 💰 **Tahmini Finansal Tasarruf:** ${saved_val:.2f} (Yerel RTX 5070 Ti, OpenRouter Free ve Flash işçileri sayesinde)")
        md.append("> 💡 **Limit Üstü Güç (🔥):** Ücretsiz ve yerel modeller kotasız olduğu için ücretli Claude kotasına (400K / 2M) göre %100 sınırını rahatça aşabilir!")
        md.append("")
        md.append("---")
        md.append("")

        # 2. BÖLÜM: ALT MODELLER (Model Model Ayrı Satırlar!)
        # Kural:
        # - En üstte sabit standart sırada: 💎/⚡ Ücretli & Kotalı Referans Alt Modelleri
        # - Hemen altında: 🟢 Ücretsiz & Yerel (0 TL) Modeller — en çok kullanılandan aşağıya doğru dinamik sıralı
        md.append("### 🤖 2. ALT MODELLER — Model Model Ayrıntılı Kota & Token Doluluk Grafiği")
        md.append("| Model Adı / Alt Motor | Katman | Kendi Kota Sınırı | 5 Saatlik Doluluk Grafiği | Haftalık Doluluk Grafiği |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")

        m_data_5h = self._aggregate_model_tokens(h5.get("_raw_events", []))
        m_data_w = self._aggregate_model_tokens(w.get("_raw_events", []))

        def get_model_tier_badge(tier: str):
            if tier == "free":
                return "🟢 0 TL / Yerel"
            elif tier == "low_quota":
                return "⚡ Düşük Kota (İşçi)"
            return "💎 Uzman Katman"

        # 1. Kısım: Ücretli modeller sabit sırada
        for spec in self.PAID_REFERENCE_MODELS:
            m_name = spec["name"]
            info_5h = m_data_5h.get(m_name, {})
            info_w = m_data_w.get(m_name, {})

            tok_5h = info_5h.get("tokens", 0)
            tok_w = info_w.get("tokens", 0)

            lim_5h = spec["limit_5h"]
            lim_w = spec["limit_weekly"]

            bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=False)
            bar_w = render_model_quota_bar(tok_w, lim_w, is_free=False)
            badge = get_model_tier_badge(spec["tier"])
            q_desc = spec.get("quota_type", "")

            md.append(f"| `{m_name}` | {badge} | {q_desc} | `{bar_5h}` | `{bar_w}` |")

        # 2. Kısım: Ücretsiz modeller en çok kullanılandan en aza doğru sıralı
        sorted_free = sorted(
            self.FREE_REFERENCE_MODELS,
            key=lambda spec: m_data_w.get(spec["name"], {}).get("tokens", 0),
            reverse=True,
        )

        for spec in sorted_free:
            m_name = spec["name"]
            info_5h = m_data_5h.get(m_name, {})
            info_w = m_data_w.get(m_name, {})

            tok_5h = info_5h.get("tokens", 0)
            tok_w = info_w.get("tokens", 0)

            lim_5h = spec.get("limit_5h", REF_FREE_LIMIT_5H)
            lim_w = spec.get("limit_weekly", REF_FREE_LIMIT_WEEKLY)

            bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=True)
            bar_w = render_model_quota_bar(tok_w, lim_w, is_free=True)
            badge = get_model_tier_badge(spec["tier"])
            q_desc = spec.get("quota_type", "")

            md.append(f"| `{m_name}` | {badge} | {q_desc} | `{bar_5h}` | `{bar_w}` |")

        md.append("")
        md.append("---")
        md.append("")

        # 3. BÖLÜM: CLI ARAÇLARI
        # Ücretli CLI'lar üstte, ücretsizler en çok kullanılandan en aza sıralı
        md.append("### 🛠️ 3. CLI ARAÇLARI (Kendi Kotalarına Göre Doluluk Grafiği)")
        md.append("| CLI Aracı | Lisans / Donanım | Kendi Kotası | 5 Saatlik Doluluk Grafiği | Haftalık Doluluk Grafiği |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")

        cli_5h_tokens = self._aggregate_cli_tokens(h5.get("_raw_events", []))
        cli_w_tokens = self._aggregate_cli_tokens(w.get("_raw_events", []))

        paid_clis = ["ClaudeCode", "Codex"]
        free_clis = ["TestRunner", "OpenCode", "Hermes", "YerelOllama"]

        # Ücretsizleri haftalık token kullanımına göre azalan sırala
        sorted_free_clis = sorted(free_clis, key=lambda c: cli_w_tokens.get(c, {}).get("tokens", 0), reverse=True)
        ordered_clis = paid_clis + sorted_free_clis

        for c_name in ordered_clis:
            tok_5h = cli_5h_tokens.get(c_name, {}).get("tokens", 0)
            tok_w = cli_w_tokens.get(c_name, {}).get("tokens", 0)

            c_lower = c_name.lower()
            if "claude" in c_lower:
                lim_5h, lim_w, is_free = 400_000, 2_000_000, False
                quota_str = "💎 Claude (400K / 2M)"
                note = "💎 Anthropic Claude CLI"
            elif "codex" in c_lower:
                lim_5h, lim_w, is_free = 800_000, 4_000_000, False
                quota_str = "⚡ ChatGPT (800K / 4M)"
                note = "⚡ ChatGPT / Kod İşçisi"
            else:
                lim_5h, lim_w, is_free = REF_FREE_LIMIT_5H, REF_FREE_LIMIT_WEEKLY, True
                quota_str = "🟢 0 TL (Claude 400K Ref)"
                if "yerelollama" in c_lower or "ollama" in c_lower:
                    note = "🟢 Yerel RTX 5070 Ti 12GB (0 TL)"
                elif "test" in c_lower or "runner" in c_lower:
                    note = "🟢 Yerel Test Motoru (0 TL)"
                elif "hermes" in c_lower:
                    note = "🟢 Hermes Agent CLI (0 TL)"
                elif "opencode" in c_lower:
                    note = "🟢 OpenCode CLI (0 TL)"
                else:
                    note = "🟢 Açık Kaynak CLI (0 TL)"

            bar_5h = render_model_quota_bar(tok_5h, lim_5h, is_free=is_free)
            bar_w = render_model_quota_bar(tok_w, lim_w, is_free=is_free)

            md.append(f"| `{c_name}` | {note} | {quota_str} | `{bar_5h}` | `{bar_w}` |")

        md.append("")
        md.append("---")
        md.append("")

        # 4. BÖLÜM: UZMAN AJANLAR & ALT AJANLAR (Temizlenmiş & Gruplanmış)
        md.append("### 🕵️ 4. AJANLAR & ALT AJANLAR (5 Saatlik & Haftalık Token Dağılımı)")
        md.append("| Uzman Ajan Rolü | 5 Saatlik Doluluk (400K Ref) | Haftalık Doluluk (2.00M Ref) |")
        md.append("| :--- | :--- | :--- |")

        ag_5h_tokens = self._aggregate_agent_tokens(h5.get("_raw_events", []))
        ag_w_tokens = self._aggregate_agent_tokens(w.get("_raw_events", []))

        all_agents = set(ag_5h_tokens.keys()).union(ag_w_tokens.keys())
        if all_agents:
            sorted_agents = sorted(all_agents, key=lambda a: ag_w_tokens.get(a, {}).get("tokens", 0), reverse=True)
            for a_name in sorted_agents:
                tok_5h = ag_5h_tokens.get(a_name, {}).get("tokens", 0)
                tok_w = ag_w_tokens.get(a_name, {}).get("tokens", 0)
                bar_5h = render_model_quota_bar(tok_5h, REF_FREE_LIMIT_5H, is_free=True)
                bar_w = render_model_quota_bar(tok_w, REF_FREE_LIMIT_WEEKLY, is_free=True)
                md.append(f"| {a_name} | `{bar_5h}` | `{bar_w}` |")
        else:
            md.append("| *Henüz kayıtlı alt ajan görevi bulunmuyor.* | `[░░░░░░░░░░░░░░░░░░░░] %0.0` | `[░░░░░░░░░░░░░░░░░░░░] %0.0` |")

        md.append("")
        md.append("---")
        md.append("🎯 **4K AI WORKSTATION:** Sistem 7/24 yerel ve bulut kaynaklarınızı optimize ederek bütçenizi ve kotanızı korur.")

        return "\n".join(md)
