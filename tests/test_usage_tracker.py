"""
Tests for core.usage_tracker.UsageTracker
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.usage_tracker import (
    UsageTracker,
    format_tokens,
    render_model_quota_bar,
    REF_FREE_LIMIT_5H,
    REF_FREE_LIMIT_WEEKLY,
)


class TestUsageTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = os.path.join(self.temp_dir.name, "events.json")
        self.brain_dir = os.path.join(self.temp_dir.name, "brain")
        os.makedirs(self.brain_dir, exist_ok=True)
        self.conversations_dir = os.path.join(self.temp_dir.name, "conversations")
        os.makedirs(self.conversations_dir, exist_ok=True)

        self.tracker = UsageTracker(
            storage_path=self.storage_file, brain_dir=self.brain_dir
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_format_tokens_and_render_bar(self):
        self.assertEqual(format_tokens(500), "500")
        self.assertEqual(format_tokens(52_000), "52.0K")
        self.assertEqual(format_tokens(1_450_000), "1.45M")

        bar_claude = render_model_quota_bar(20_000, 400_000, is_free=False, width=20)
        self.assertIn("%5.0", bar_claude)
        self.assertIn("20.0K / 400.0K", bar_claude)
        self.assertNotIn("🔥", bar_claude)

        bar_free_over = render_model_quota_bar(600_000, 400_000, is_free=True, width=20)
        self.assertIn("%150.0", bar_free_over)
        self.assertIn("600.0K Token", bar_free_over)
        self.assertIn("🔥", bar_free_over)

        # Ücretli model kotayı aştığında ASLA %100'ü geçemez ve ASLA 🔥 alamaz
        bar_paid_over = render_model_quota_bar(600_000, 400_000, is_free=False, width=20)
        self.assertIn("%100.0", bar_paid_over)
        self.assertNotIn("%150.0", bar_paid_over)
        self.assertNotIn("🔥", bar_paid_over)

    def test_classify_model_or_tool(self):
        free_models = [
            "YerelOllama",
            "ollama",
            "llama3",
            "qwen",
            "deepseek",
            "OpenRouterFree",
            "meta-llama/llama-3-8b:free",
            "Hermes",
            "OpenCode",
            "flash_lite",
            "3.5-flash-lite",
            "MODEL_TIER_FLASH_LITE",
            "nvidia/llama-3.1-nemotron-70b-instruct:free",
            "Qwen/Qwen2.5-Coder-32B-Instruct:free",
            "huggingface-zephyr",
        ]
        for name in free_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertTrue(cls_info["is_free"], f"{name} should be is_free=True")
            self.assertEqual(cls_info["tier"], "free", f"{name} should have tier='free'")

        low_quota_models = ["flash", "MODEL_TIER_FLASH", "Codex", "3.8-flash", "gpt-oss"]
        for name in low_quota_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertFalse(cls_info["is_free"], f"{name} should be is_free=False")
            self.assertEqual(cls_info["tier"], "low_quota", f"{name} should have tier='low_quota'")

        premium_models = ["ClaudeCode", "claude", "pro", "MODEL_TIER_PRO", "argon", "opus", "fable"]
        for name in premium_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertFalse(cls_info["is_free"], f"{name} should be is_free=False")
            self.assertEqual(cls_info["tier"], "premium", f"{name} should have tier='premium'")

    def test_record_and_timeframe_filtering(self):
        now = datetime.now(timezone.utc)

        t_2h = (now - timedelta(hours=2)).isoformat()
        self.tracker.record_event(
            category="model",
            name="llama3",
            tier="free",
            is_free=True,
            tokens_est=10000,
            timestamp=t_2h,
        )

        t_10h = (now - timedelta(hours=10)).isoformat()
        self.tracker.record_event(
            category="cli",
            name="Codex",
            tier="low_quota",
            is_free=False,
            tokens_est=20000,
            timestamp=t_10h,
        )

        t_3d = (now - timedelta(days=3)).isoformat()
        self.tracker.record_event(
            category="cli",
            name="Codex",
            tier="low_quota",
            is_free=False,
            tokens_est=30000,
            timestamp=t_3d,
        )

        t_15d = (now - timedelta(days=15)).isoformat()
        self.tracker.record_event(
            category="model",
            name="claude",
            tier="premium",
            is_free=False,
            tokens_est=40000,
            timestamp=t_15d,
        )

        report = self.tracker.get_report(include_antigravity=False)

        self.assertEqual(report["five_hours"]["total_events"], 1)
        self.assertEqual(report["five_hours"]["free_events"], 1)
        self.assertEqual(report["five_hours"]["tokens_total"], 10000)

        self.assertEqual(report["daily"]["total_events"], 2)
        self.assertEqual(report["weekly"]["total_events"], 3)
        self.assertEqual(report["monthly"]["total_events"], 4)

    def test_scan_conversations_db(self):
        fake_db = os.path.join(self.conversations_dir, "test-conv-123.db")
        conn = sqlite3.connect(fake_db)
        cur = conn.cursor()
        cur.execute("CREATE TABLE gen_metadata (idx INTEGER PRIMARY KEY, data BLOB, size INTEGER)")

        blob_argon = b"\x00\x01\x9a\x01\x13gemini-4-argon-trial\xa2\x01\x05extra"
        blob_flash = b"\x00\x01\x9a\x01\x17gemini-3.8-flash-tiered\xa2\x01\x05extra"
        cur.execute("INSERT INTO gen_metadata (idx, data, size) VALUES (0, ?, ?)", (blob_argon, len(blob_argon)))
        cur.execute("INSERT INTO gen_metadata (idx, data, size) VALUES (1, ?, ?)", (blob_flash, len(blob_flash)))
        conn.commit()
        conn.close()

        events = self.tracker.scan_conversations_db()
        self.assertEqual(len(events), 2)
        names = [e["name"] for e in events]
        self.assertIn("gemini-4-argon-trial", names)
        self.assertIn("gemini-3.8-flash-tiered", names)
        self.assertEqual(events[0]["tokens_est"], 1100)
        self.assertEqual(events[1]["tokens_est"], 1100)

    def test_format_all_in_one_markdown(self):
        now = datetime.now(timezone.utc).isoformat()
        self.tracker.record_event(
            category="model",
            name="llama3",
            tier="free",
            is_free=True,
            tokens_est=600_000,
            timestamp=now,
        )
        self.tracker.record_event(
            category="model",
            name="claude",
            tier="premium",
            is_free=False,
            tokens_est=20_000,
            timestamp=now,
        )

        md = self.tracker.format_all_in_one_markdown(include_antigravity=False)
        self.assertIsInstance(md, str)

        self.assertNotIn("NEXUS AI STUDIO", md)
        self.assertNotIn("Nexus AI Studio", md)
        self.assertIn("4K AI WORKSTATION", md)

        # 2. MODELLER VE EFORLAR başlığı ve Sağlayıcı grupları
        self.assertIn("2. MODELLER VE EFORLAR", md)
        self.assertIn("Anthropic (Claude", md)
        self.assertIn("OpenAI Ailesi", md)
        self.assertIn("Google (Gemini", md)
        self.assertIn("Açık Kaynak", md)
        self.assertIn("Claude Opus 5.5", md)
        self.assertIn("Gemini 4 Argon", md)
        self.assertIn("Gemini 3.8 Flash", md)
        self.assertIn("Gemini 3.5 Flash-Lite", md)
        self.assertIn("NVIDIA Llama 3.1 Nemotron 70B:free", md)
        self.assertIn("HuggingFace", md)

        # Ücretli modellerin en üstte olduğunu teyit et (Opus'un indeksi Llama3'ten önce olmalı)
        idx_opus = md.find("Claude Opus 5.5")
        idx_llama = md.find("Llama 3 8B")
        self.assertTrue(idx_opus < idx_llama, "Ücretli referans modeller her zaman ücretsiz modellerden önce gelmeli!")

    def test_audit_paid_api_risks(self):
        # 1. Varsayılan güvenli ortam (geçici sahte providers.json ile)
        safe_providers = os.path.join(self.temp_dir.name, "safe_providers.json")
        with open(safe_providers, "w", encoding="utf-8") as f:
            json.dump({
                "providers": [
                    {"name": "YerelOllama", "base_url": "http://127.0.0.1:11434/v1", "model": "llama3", "cost": 0.0, "local": True},
                    {"name": "OpenRouterFree", "base_url": "https://openrouter.ai/api/v1", "model": "qwen:free", "cost": 0.0, "local": False}
                ]
            }, f)

        audit_clean = self.tracker.audit_paid_api_risks(providers_path=safe_providers)
        self.assertTrue(audit_clean["safe"])
        self.assertIn("SIFIR API HARCAMA KALKANI AKTİF", audit_clean["status_line"])

        # 2. Sahte ücretli ortam değişkeni eklendiğinde uyarı vermeli
        os.environ["OPENAI_API_KEY"] = "sk-paid-secret-key-12345"
        try:
            audit_env_risk = self.tracker.audit_paid_api_risks(providers_path=safe_providers)
            self.assertFalse(audit_env_risk["safe"])
            self.assertTrue(any("OPENAI_API_KEY" in w for w in audit_env_risk["warnings"]))
        finally:
            del os.environ["OPENAI_API_KEY"]

        # 3. Sahte ücretli sağlayıcı eklendiğinde uyarı vermeli
        risky_providers = os.path.join(self.temp_dir.name, "risky_providers.json")
        with open(risky_providers, "w", encoding="utf-8") as f:
            json.dump({
                "providers": [
                    {"name": "PaidOpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-4o", "cost": 0.03, "local": False}
                ]
            }, f)

        audit_provider_risk = self.tracker.audit_paid_api_risks(providers_path=risky_providers)
        self.assertFalse(audit_provider_risk["safe"])
        self.assertTrue(any("PaidOpenAI" in w for w in audit_provider_risk["warnings"]))


if __name__ == "__main__":
    unittest.main()
