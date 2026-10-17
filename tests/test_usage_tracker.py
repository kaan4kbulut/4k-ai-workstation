"""
Tests for core.usage_tracker.UsageTracker
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.usage_tracker import UsageTracker


class TestUsageTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = os.path.join(self.temp_dir.name, "events.json")
        self.brain_dir = os.path.join(self.temp_dir.name, "brain")
        os.makedirs(self.brain_dir, exist_ok=True)
        self.tracker = UsageTracker(
            storage_path=self.storage_file, brain_dir=self.brain_dir
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_classify_model_or_tool(self):
        # Ücretsiz / 0 TL katmanı
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
            "MODEL_TIER_FLASH_LITE",
        ]
        for name in free_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertTrue(
                cls_info["is_free"], f"{name} should be is_free=True"
            )
            self.assertEqual(
                cls_info["tier"], "free", f"{name} should have tier='free'"
            )

        # Düşük Kota (low_quota) katmanı
        low_quota_models = ["flash", "MODEL_TIER_FLASH", "Codex"]
        for name in low_quota_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertFalse(
                cls_info["is_free"], f"{name} should be is_free=False"
            )
            self.assertEqual(
                cls_info["tier"], "low_quota", f"{name} should have tier='low_quota'"
            )

        # Premium / Uzman katmanı
        premium_models = ["ClaudeCode", "claude", "pro", "MODEL_TIER_PRO"]
        for name in premium_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertFalse(
                cls_info["is_free"], f"{name} should be is_free=False"
            )
            self.assertEqual(
                cls_info["tier"], "premium", f"{name} should have tier='premium'"
            )

    def test_record_and_timeframe_filtering(self):
        now = datetime.now(timezone.utc)

        # 1. Olay: 2 saat önce (Günlük, Haftalık, Aylık hepsine dahil olmalı)
        t_2h = (now - timedelta(hours=2)).isoformat()
        self.tracker.record_event(
            category="model",
            name="llama3",
            tier="free",
            is_free=True,
            timestamp=t_2h,
        )

        # 2. Olay: 3 gün önce (Haftalık ve Aylık dahil olmalı, Günlük'te OLMAMALI)
        t_3d = (now - timedelta(days=3)).isoformat()
        self.tracker.record_event(
            category="cli",
            name="Codex",
            tier="low_quota",
            is_free=False,
            timestamp=t_3d,
        )

        # 3. Olay: 15 gün önce (Sadece Aylık dahil olmalı, Günlük ve Haftalık'ta OLMAMALI)
        t_15d = (now - timedelta(days=15)).isoformat()
        self.tracker.record_event(
            category="model",
            name="claude",
            tier="premium",
            is_free=False,
            timestamp=t_15d,
        )

        # 4. Olay: 45 gün önce (Hiçbir pencereye dahil olmamalı)
        t_45d = (now - timedelta(days=45)).isoformat()
        self.tracker.record_event(
            category="model",
            name="qwen",
            tier="free",
            is_free=True,
            timestamp=t_45d,
        )

        report = self.tracker.get_report(include_antigravity=False)

        # Günlük kontrol (Sadece 2 saat önceki olay olmalı)
        self.assertEqual(report["daily"]["total_events"], 1)
        self.assertEqual(report["daily"]["free_events"], 1)
        self.assertEqual(report["daily"]["low_quota_events"], 0)
        self.assertEqual(report["daily"]["premium_events"], 0)
        self.assertEqual(len(report["daily"]["models"]), 1)
        self.assertEqual(report["daily"]["models"][0]["name"], "llama3")

        # Haftalık kontrol (2 saat önceki + 3 gün önceki = 2 olay)
        self.assertEqual(report["weekly"]["total_events"], 2)
        self.assertEqual(report["weekly"]["free_events"], 1)
        self.assertEqual(report["weekly"]["low_quota_events"], 1)
        self.assertEqual(report["weekly"]["premium_events"], 0)

        # Aylık kontrol (2 saatlik + 3 günlük + 15 günlük = 3 olay)
        self.assertEqual(report["monthly"]["total_events"], 3)
        self.assertEqual(report["monthly"]["free_events"], 1)
        self.assertEqual(report["monthly"]["low_quota_events"], 1)
        self.assertEqual(report["monthly"]["premium_events"], 1)

    def test_savings_and_ratio_calculation(self):
        now = datetime.now(timezone.utc)
        # 10 adet free olay ekle
        for i in range(10):
            self.tracker.record_event(
                category="model",
                name=f"free_model_{i}",
                tier="free",
                is_free=True,
                timestamp=now.isoformat(),
            )

        # 5 adet low_quota (işçi) olay ekle
        for i in range(5):
            self.tracker.record_event(
                category="model",
                name=f"flash_{i}",
                tier="low_quota",
                is_free=False,
                timestamp=now.isoformat(),
            )

        # 5 adet premium olay ekle
        for i in range(5):
            self.tracker.record_event(
                category="model",
                name=f"claude_{i}",
                tier="premium",
                is_free=False,
                timestamp=now.isoformat(),
            )

        report = self.tracker.get_report(include_antigravity=False)
        daily = report["daily"]

        self.assertEqual(daily["total_events"], 20)
        self.assertEqual(daily["free_events"], 10)
        self.assertEqual(daily["low_quota_events"], 5)
        self.assertEqual(daily["premium_events"], 5)

        # Oran: (10 free + 5 low_quota) / 20 * 100 = %75.0
        self.assertEqual(daily["free_And_worker_ratio"], 75.0)
        self.assertEqual(daily["free_and_worker_ratio"], 75.0)

        # Tasarruf: (10 * 0.03) + (5 * 0.02) = 0.30 + 0.10 = 0.40 USD
        self.assertAlmostEqual(daily["estimated_saved_usd"], 0.40, places=2)

    def test_scan_antigravity_brain(self):
        now = datetime.now(timezone.utc).isoformat()
        conv_dir = os.path.join(
            self.brain_dir, "fake-conv-123", ".system_generated", "logs"
        )
        os.makedirs(conv_dir, exist_ok=True)
        # transcript_full.jsonl dosyası oluştur
        transcript_file = os.path.join(conv_dir, "transcript_full.jsonl")

        lines = [
            # invoke_subagent satırı
            json.dumps({
                "step_index": 1,
                "created_at": now,
                "input_tokens": 1000,
                "output_tokens": 200,
                "tool_calls": [
                    {
                        "name": "invoke_subagent",
                        "args": {
                            "Subagents": json.dumps([
                                {"Role": "UI Uzmanı", "Model": "flash"},
                                {"Role": "Test Uzmanı", "Model": "flash_lite"},
                            ])
                        },
                    }
                ],
            }),
            # send_message satırı
            json.dumps({
                "step_index": 2,
                "created_at": now,
                "tool_calls": [
                    {
                        "name": "send_message",
                        "args": {
                            "Recipient": "subagent-12345",
                            "Message": "Lütfen testleri çalıştır",
                            "toolSummary": "Test Yönergesi",
                        },
                    }
                ],
            }),
            # run_command satırı
            json.dumps({
                "step_index": 3,
                "created_at": now,
                "tool_calls": [
                    {
                        "name": "run_command",
                        "args": {
                            "CommandLine": "codex exec 'fix bug' && python -m unittest tests/test_core.py"
                        },
                    }
                ],
            }),
        ]

        with open(transcript_file, "w", encoding="utf-8") as f:
            for l in lines:
                f.write(l + "\n")

        events = self.tracker.scan_antigravity_brain()
        self.assertTrue(len(events) >= 6)

        categories = [e["category"] for e in events]
        self.assertIn("agent", categories)
        self.assertIn("model", categories)
        self.assertIn("cli", categories)

        agent_names = [e["name"] for e in events if e["category"] == "agent"]
        self.assertIn("UI Uzmanı", agent_names)
        self.assertIn("Test Uzmanı", agent_names)
        self.assertTrue(any("Test Yönergesi" in name for name in agent_names))

        cli_names = [e["name"] for e in events if e["category"] == "cli"]
        self.assertIn("Codex", cli_names)
        self.assertIn("TestRunner", cli_names)

    def test_format_all_in_one_markdown(self):
        now = datetime.now(timezone.utc).isoformat()
        self.tracker.record_event(
            category="model",
            name="llama3",
            tier="free",
            is_free=True,
            timestamp=now,
        )
        self.tracker.record_event(
            category="cli",
            name="YerelOllama",
            tier="free",
            is_free=True,
            timestamp=now,
        )
        self.tracker.record_event(
            category="agent",
            name="Nexus Worker",
            tier="free",
            is_free=True,
            timestamp=now,
        )

        md = self.tracker.format_all_in_one_markdown(include_antigravity=False)
        self.assertIsInstance(md, str)

        # Markalama testi: "NEXUS AI STUDIO" bulunmamalı, "🖥️ 4K AI WORKSTATION" bulunmalı
        self.assertNotIn("NEXUS AI STUDIO", md)
        self.assertNotIn("Nexus AI Studio", md)
        self.assertIn("🖥️ 4K AI WORKSTATION", md)

        # Tablolar
        self.assertIn("🟢 1. Ücretsiz (0 TL) Kullanımlar & Tasarruf Tablosu", md)
        self.assertIn("🤖 2. Hangi Model Ne Kadar Kullanıldı?", md)
        self.assertIn("🛠️ 3. Hangi CLI Aracı Ne Kadar Kullanıldı?", md)
        self.assertIn("🕵️ 4. Hangi Ajan / Alt Ajan Ne Kadar Kullanıldı?", md)

        # Kayıtlı modellerin tabloda varlığı
        self.assertIn("YerelOllama (llama3)", md)
        self.assertIn("OpenRouterFree (qwen-2.5-coder:free)", md)
        self.assertIn("flash", md)
        self.assertIn("ClaudeCode", md)


if __name__ == "__main__":
    unittest.main()
