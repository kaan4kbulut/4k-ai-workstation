"""
4K AI WORKSTATION - Usage & Analytics Tracker (Kullanım ve Tasarruf Takip Motoru)
Kullanıcının günlük, haftalık ve aylık model, CLI ve ajan kullanımlarını,
ücretsiz katman tasarruflarını ve Antigravity alt ajan etkileşimlerini takip eder.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


class UsageTracker:
    """
    Yerel 4K AI Workstation ve Antigravity orkestrasyon motorunun kullanım verilerini toplayıp
    görsel ve finansal tasarruf raporlarına dönüştüren analitik motoru.
    """

    DEFAULT_REGISTERED_MODELS = [
        {"name": "YerelOllama (llama3)", "model_key": "YerelOllama", "tier": "free", "is_free": True},
        {"name": "OpenRouterFree (qwen-2.5-coder:free)", "model_key": "OpenRouterFree", "tier": "free", "is_free": True},
        {"name": "flash_lite", "model_key": "flash_lite", "tier": "free", "is_free": True},
        {"name": "Hermes", "model_key": "Hermes", "tier": "free", "is_free": True},
        {"name": "OpenCode", "model_key": "OpenCode", "tier": "free", "is_free": True},
        {"name": "flash", "model_key": "flash", "tier": "low_quota", "is_free": False},
        {"name": "Codex", "model_key": "Codex", "tier": "low_quota", "is_free": False},
        {"name": "ClaudeCode", "model_key": "ClaudeCode", "tier": "premium", "is_free": False},
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
        """
        Yeni bir kullanım olayını kaydeder.
        category: 'model', 'cli', 'agent'
        tier: 'free' (0 TL), 'low_quota' (Düşük Kota İşçi), 'premium' (Uzman Katman)
        """
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

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
        """
        Verilen model/CLI adına göre otomatik olarak:
        {"is_free": bool, "tier": str, "cli_name": str, "display_name": str} döndürür.
        """
        n = (name or "").strip()
        n_lower = n.lower()

        # 1. Öncelik: flash_lite kontrolü (flash kelimesinden önce kontrol edilmeli)
        if any(k in n_lower for k in ["flash_lite", "flash-lite", "tier_flash_lite"]):
            return {
                "is_free": True,
                "tier": "free",
                "cli_name": "flash_lite",
                "display_name": "Gemini Flash-Lite (0 TL / Kota Dostu)",
            }

        # 2. Ücretsiz (0 TL) Modeller & Araçlar
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
        ]
        if any(k in n_lower for k in free_keywords):
            cli_name = "ollama"
            if "hermes" in n_lower:
                cli_name = "hermes"
            elif "opencode" in n_lower:
                cli_name = "opencode"
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

        # 3. Düşük Kota / Yüksek Verimli İşçiler (low_quota)
        low_quota_keywords = ["flash", "tier_flash", "codex"]
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

        # 4. Premium / Uzman Katman (premium)
        premium_keywords = ["claudecode", "claude", "pro", "tier_pro", "gemini-pro"]
        if any(k in n_lower for k in premium_keywords):
            cli_name = "claude" if "claude" in n_lower else "gemini_pro"
            return {
                "is_free": False,
                "tier": "premium",
                "cli_name": cli_name,
                "display_name": f"{n} (Uzman Katman)",
            }

        # Varsayılan
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
        """
        self.brain_dir altındaki konuşma klasörlerini tarar.
        Varsa ÖNCE transcript_full.jsonl dosyasını (kısaltılmamış), yoksa transcript.jsonl'i okur.
        invoke_subagent, send_message ve run_command araç çağrılarını yakalar.
        """
        brain_path = Path(self.brain_dir)
        events: List[Dict[str, Any]] = []

        if not brain_path.exists():
            return events

        # Her konuşma klasörü için tek dosya seç (önce transcript_full.jsonl, yoksa transcript.jsonl)
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

        # Klasör iterasyonunda bulunamazsa genel tarama yap
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

                                    # Ajan olayı
                                    events.append({
                                        "category": "agent",
                                        "name": role,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": item.get("input_tokens", 0) + item.get("output_tokens", 0),
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })
                                    # Model olayı
                                    events.append({
                                        "category": "model",
                                        "name": model,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": item.get("input_tokens", 0) + item.get("output_tokens", 0),
                                        "source": "antigravity",
                                        "timestamp": ts,
                                    })

                            # 2. Alt ajana ek görev / yönerge mesajı gönderme (send_message)
                            elif tool_name == "send_message":
                                recipient = str(args.get("Recipient", ""))
                                msg = str(args.get("Message", ""))
                                summary = str(args.get("toolSummary") or "Alt Ajan Görevi")
                                short_id = recipient[:8] if recipient else "worker"
                                events.append({
                                    "category": "agent",
                                    "name": f"Ek Görev ({summary} - {short_id})",
                                    "tier": "free",
                                    "is_free": True,
                                    "tokens_est": len(msg) // 4,
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

                                for cli_key in detected_clis:
                                    cls_info = self.classify_model_or_tool(cli_key)
                                    events.append({
                                        "category": "cli",
                                        "name": cli_key,
                                        "tier": cls_info["tier"],
                                        "is_free": cls_info["is_free"],
                                        "tokens_est": 0,
                                        "source": "antigravity",
                                        "timestamp": ts,
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

    def _load_quotas_dict(self) -> Dict[str, Any]:
        """data/quotas.json ve config/quotas.json dosyalarındaki kotaları okur."""
        quotas: Dict[str, Any] = {}
        for p in ["data/quotas.json", "config/quotas.json"]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            quotas.update(data)
                except Exception:
                    pass
        return quotas

    def get_report(self, include_antigravity: bool = True) -> Dict[str, Any]:
        """
        Hem yerel workstation olaylarını hem de Antigravity olaylarını birleştirerek
        daily (24 saat), weekly (7 gün) ve monthly (30 gün) analiz raporu üretir.
        """
        all_events = list(self._load_events())
        if include_antigravity:
            antigravity_events = self.scan_antigravity_brain()
            all_events.extend(antigravity_events)

        now = datetime.now(timezone.utc)

        window_seconds = {
            "daily": 24 * 3600,
            "weekly": 7 * 24 * 3600,
            "monthly": 30 * 24 * 3600,
        }

        report: Dict[str, Any] = {
            "generated_at": now.isoformat(),
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
                            "tier": e.get("tier", "free"),
                            "is_free": e.get("is_free", True),
                        }
                    model_counts[name]["count"] += 1
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
                            "tier": e.get("tier", "free"),
                            "is_free": e.get("is_free", True),
                        }
                    cli_counts[name]["count"] += 1
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
                            "tier": e.get("tier", "free"),
                            "source": source,
                        }
                    agent_counts[key]["count"] += 1
            agents_list = sorted(
                agent_counts.values(), key=lambda x: x["count"], reverse=True
            )

            free_usages = {
                "total_free": free_cnt,
                "low_quota": low_quota_cnt,
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
                "free_And_worker_ratio": ratio,
                "free_and_worker_ratio": ratio,
                "estimated_saved_usd": saved_usd,
                "models": models_list,
                "clis": clis_list,
                "agents": agents_list,
                "free_usages": free_usages,
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
        }

        return report

    def format_all_in_one_markdown(self, include_antigravity: bool = True) -> str:
        """
        Kullanıcı 'usage' yazdığında TEK SEFERDE hem Günlük, hem Haftalık,
        hem Aylık özeti, tasarruf tablosunu, model/CLI ve alt ajan dağılımlarını
        okunabilir zengin Markdown formatında döndürür.
        """
        report = self.get_report(include_antigravity=include_antigravity)
        d = report.get("daily", {})
        w = report.get("weekly", {})
        m = report.get("monthly", {})
        quotas = self._load_quotas_dict()

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        md: List[str] = []
        md.append("# 🖥️ 4K AI WORKSTATION")
        md.append("## 📊 KULLANIM, AJAN VE TASARRUF TAKİP RAPORU (ALL-IN-ONE)")
        md.append(f"**🕒 Rapor Üretim Zamanı:** `{now_str}`")
        md.append(f"**📁 Depolama:** `{self.storage_path}` | **🧠 Antigravity:** `{self.brain_dir}`")
        md.append("")

        # 1. BÖLÜM: Ücretsiz Kullanımlar ve Tasarruf Tablosu
        md.append("### 🟢 1. Ücretsiz (0 TL) Kullanımlar & Tasarruf Tablosu")
        md.append(
            "| Dönem | Toplam İşlem | 🟢 Ücretsiz (0 TL) | ⚡ Düşük Kota (İşçi) | 💎 Uzman Katman | 🛡️ Kota Koruma Oranı | 💰 Tahmini Tasarruf |"
        )
        md.append(
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |"
        )
        md.append(
            f"| **Günlük (Son 24 Saat)** | {d.get('total_events', 0)} | {d.get('free_events', 0)} | {d.get('low_quota_events', 0)} | {d.get('premium_events', 0)} | **%{d.get('free_and_worker_ratio', 0.0)}** | **${d.get('estimated_saved_usd', 0.0):.2f}** |"
        )
        md.append(
            f"| **Haftalık (Son 7 Gün)** | {w.get('total_events', 0)} | {w.get('free_events', 0)} | {w.get('low_quota_events', 0)} | {w.get('premium_events', 0)} | **%{w.get('free_and_worker_ratio', 0.0)}** | **${w.get('estimated_saved_usd', 0.0):.2f}** |"
        )
        md.append(
            f"| **Aylık (Son 30 Gün)** | {m.get('total_events', 0)} | {m.get('free_events', 0)} | {m.get('low_quota_events', 0)} | {m.get('premium_events', 0)} | **%{m.get('free_and_worker_ratio', 0.0)}** | **${m.get('estimated_saved_usd', 0.0):.2f}** |"
        )
        md.append("")
        md.append(
            "> 💡 **Sıfır Abonelik Sigortası (0 TL Tasarruf Kalkanı):** "
            "Yerel RTX 5070 Ti (Ollama), OpenRouter Free modeller, Hermes ve OpenCode CLI ve Kota Dostu Flash alt ajanları "
            "sayesinde ana model kotalarınız harcanmadan işlemleriniz tamamlanmaktadır."
        )
        md.append("")

        # 2. BÖLÜM: Model Karşılaştırma Tablosu (Tüm Kayıtlı Modeller & Kalan Kotalar Dahil)
        md.append("### 🤖 2. Hangi Model Ne Kadar Kullanıldı? (Günlük | Haftalık | Aylık)")
        md.append("| Model Adı / Sağlayıcı | Katman | Kalan Kota Durumu | Günlük (24s) | Haftalık (7g) | Aylık (30g) |")
        md.append("| :--- | :--- | :--- | :---: | :---: | :---: |")

        # Gerçek kullanım sayılarını haritalandır
        d_map: Dict[str, int] = {}
        for item in d.get("models", []):
            d_map[item["name"].lower()] = item["count"]
            d_map[item["name"]] = item["count"]

        w_map: Dict[str, int] = {}
        for item in w.get("models", []):
            w_map[item["name"].lower()] = item["count"]
            w_map[item["name"]] = item["count"]

        m_map: Dict[str, int] = {}
        for item in m.get("models", []):
            m_map[item["name"].lower()] = item["count"]
            m_map[item["name"]] = item["count"]

        # Varsayılan modeller ve kota durumu
        quota_labels = {
            "YerelOllama": ("🟢 0 TL / Yerel", "🟢 Sınırsız (RTX 5070 Ti 12GB)"),
            "OpenRouterFree": ("🟢 0 TL / Ücretsiz", "🟢 Sınırsız (0 TL)"),
            "flash_lite": ("🟢 0 TL / Kota Dostu", "🟢 Yüksek Kapasite (0 TL)"),
            "Hermes": ("🟢 0 TL / CLI", "🟢 198 / 200 istek kaldı"),
            "OpenCode": ("🟢 0 TL / CLI", "🟢 Sınırsız (0 TL)"),
            "flash": ("⚡ Düşük Kota (İşçi)", "⚡ Aktif İşçi Havuzu"),
            "Codex": ("⚡ Düşük Kota (İşçi)", "⚡ 100 / 100 istek kaldı"),
            "ClaudeCode": ("💎 Uzman Katman", "💎 50 / 50 istek kaldı"),
        }

        # quotas.json'dan gerçek kalan kotaları güncelle
        for q_name, q_val in quotas.items():
            if isinstance(q_val, dict) and "limit" in q_val and "used" in q_val:
                rem = max(0, q_val["limit"] - q_val["used"])
                unit = q_val.get("unit", "istek")
                matched_key = None
                if "ollama" in q_name.lower():
                    matched_key = "YerelOllama"
                elif "codex" in q_name.lower():
                    matched_key = "Codex"
                elif "claude" in q_name.lower():
                    matched_key = "ClaudeCode"
                elif "hermes" in q_name.lower():
                    matched_key = "Hermes"

                if matched_key and matched_key in quota_labels:
                    tier_str, _ = quota_labels[matched_key]
                    quota_labels[matched_key] = (tier_str, f"⚡ {rem} / {q_val['limit']} {unit} kaldı")

        displayed_keys = set()
        for reg in self.DEFAULT_REGISTERED_MODELS:
            m_disp = reg["name"]
            m_key = reg["model_key"]
            displayed_keys.add(m_key.lower())
            displayed_keys.add(m_disp.lower())

            tier_badge, quota_status = quota_labels.get(
                m_key, ("🟢 Ücretsiz", "Aktif")
            )

            # Sayımları bul (anahtar adı veya model adı ile)
            c_d = d_map.get(m_key.lower(), d_map.get(m_key, d_map.get(m_disp, 0)))
            c_w = w_map.get(m_key.lower(), w_map.get(m_key, w_map.get(m_disp, 0)))
            c_m = m_map.get(m_key.lower(), m_map.get(m_key, m_map.get(m_disp, 0)))

            md.append(
                f"| `{m_disp}` | {tier_badge} | {quota_status} | {c_d} | {c_w} | {c_m} |"
            )

        # Standart listede olmayan ekstra modeller varsa onları da ekle
        for item in m.get("models", []) + w.get("models", []) + d.get("models", []):
            name = item["name"]
            if name.lower() not in displayed_keys and name not in displayed_keys:
                displayed_keys.add(name.lower())
                cls_info = self.classify_model_or_tool(name)
                t_badge = "🟢 0 TL / Ücretsiz"
                if cls_info["tier"] == "low_quota":
                    t_badge = "⚡ Düşük Kota (İşçi)"
                elif cls_info["tier"] == "premium":
                    t_badge = "💎 Uzman Katman"

                c_d = d_map.get(name, 0)
                c_w = w_map.get(name, 0)
                c_m = m_map.get(name, 0)
                md.append(
                    f"| `{name}` | {t_badge} | 🟢 Çalışma Zamanı | {c_d} | {c_w} | {c_m} |"
                )

        md.append("")

        # 3. BÖLÜM: CLI Araçları Karşılaştırma Tablosu
        md.append("### 🛠️ 3. Hangi CLI Aracı Ne Kadar Kullanıldı? (Günlük | Haftalık | Aylık)")
        all_cli_names = set()
        for item in d.get("clis", []) + w.get("clis", []) + m.get("clis", []):
            all_cli_names.add(item["name"])

        # Standart CLI araçlarını ekle
        standard_clis = ["YerelOllama", "Hermes", "OpenCode", "Codex", "ClaudeCode", "TestRunner"]
        for sc in standard_clis:
            all_cli_names.add(sc)

        md.append("| CLI Aracı | Lisans / Donanım | Günlük (24s) | Haftalık (7g) | Aylık (30g) |")
        md.append("| :--- | :--- | :---: | :---: | :---: |")

        d_cli_map = {item["name"]: item["count"] for item in d.get("clis", [])}
        w_cli_map = {item["name"]: item["count"] for item in w.get("clis", [])}
        m_cli_map = {item["name"]: item["count"] for item in m.get("clis", [])}

        sorted_clis = sorted(
            all_cli_names, key=lambda name: m_cli_map.get(name, 0), reverse=True
        )
        for c_name in sorted_clis:
            note = "🟢 Yerel / Açık Kaynak (0 TL)"
            if c_name.lower() in ["yerelollama", "ollama"]:
                note = "🟢 Yerel RTX 5070 Ti 12GB (0 TL)"
            elif "codex" in c_name.lower():
                note = "⚡ ChatGPT / Kod İşçisi"
            elif "claude" in c_name.lower():
                note = "💎 Claude Code (Uzman)"
            elif "hermes" in c_name.lower():
                note = "🟢 Hermes Agent CLI (0 TL)"
            elif "opencode" in c_name.lower():
                note = "🟢 OpenCode CLI (0 TL)"
            elif "test" in c_name.lower() or "runner" in c_name.lower():
                note = "🟢 Yerel Python Test Motoru (0 TL)"

            md.append(
                f"| `{c_name}` | {note} | {d_cli_map.get(c_name, 0)} | {w_cli_map.get(c_name, 0)} | {m_cli_map.get(c_name, 0)} |"
            )
        md.append("")

        # 4. BÖLÜM: Ajan ve Alt Ajan Görev Dağılımı Tablosu
        md.append("### 🕵️ 4. Hangi Ajan / Alt Ajan Ne Kadar Kullanıldı? (Günlük | Haftalık | Aylık)")
        all_agent_names = set()
        for item in d.get("agents", []) + w.get("agents", []) + m.get("agents", []):
            all_agent_names.add(item["name"])

        if all_agent_names:
            md.append("| Ajan Rolü | Kaynak | Günlük (24s) | Haftalık (7g) | Aylık (30g) |")
            md.append("| :--- | :--- | :---: | :---: | :---: |")

            d_ag_map = {item["name"]: item["count"] for item in d.get("agents", [])}
            w_ag_map = {item["name"]: item["count"] for item in w.get("agents", [])}
            m_ag_map = {item["name"]: item["count"] for item in m.get("agents", [])}

            sorted_agents = sorted(
                all_agent_names, key=lambda name: m_ag_map.get(name, 0), reverse=True
            )
            for a_name in sorted_agents:
                md.append(
                    f"| `{a_name}` | Antigravity / Workstation | {d_ag_map.get(a_name, 0)} | {w_ag_map.get(a_name, 0)} | {m_ag_map.get(a_name, 0)} |"
                )
        else:
            md.append("*Henüz kayıtlı alt ajan görevi bulunmuyor.*")

        md.append("")
        md.append("---")
        md.append("🎯 **4K AI WORKSTATION:** Sistem 7/24 yerel ve bulut kaynaklarınızı optimize ederek bütçenizi ve kotanızı korur.")

        return "\n".join(md)
