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
        self.tracker = UsageTracker(
            storage_path=self.storage_file, brain_dir=self.brain_dir
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_format_tokens_and_render_bar(self):
        self.assertEqual(format_tokens(500), "500")
        self.assertEqual(format_tokens(52_000), "52.0K")
        self.assertEqual(format_tokens(1_450_000), "1.45M")

        # Ücretli model barı (örn. Claude: 20K / 400K -> %5.0)
        bar_claude = render_model_quota_bar(20_000, 400_000, is_free=False, width=20)
        self.assertIn("%5.0", bar_claude)
        self.assertIn("20.0K / 400.0K", bar_claude)
        self.assertNotIn("🔥", bar_claude)

        # Ücretsiz model barı (örn. 600K / 400K -> %150.0 ve 🔥)
        bar_free_over = render_model_quota_bar(600_000, 400_000, is_free=True, width=20)
        self.assertIn("%150.0", bar_free_over)
        self.assertIn("600.0K Token", bar_free_over)
        self.assertIn("🔥", bar_free_over)

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
            "MODEL_TIER_FLASH_LITE",
        ]
        for name in free_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertTrue(cls_info["is_free"], f"{name} should be is_free=True")
            self.assertEqual(cls_info["tier"], "free", f"{name} should have tier='free'")

        low_quota_models = ["flash", "MODEL_TIER_FLASH", "Codex"]
        for name in low_quota_models:
            cls_info = self.tracker.classify_model_or_tool(name)
            self.assertFalse(cls_info["is_free"], f"{name} should be is_free=False")
            self.assertEqual(cls_info["tier"], "low_quota", f"{name} should have tier='low_quota'")

        premium_models = ["ClaudeCode", "claude", "pro", "MODEL_TIER_PRO"]
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

    def test_savings_and_ratio_calculation(self):
        now = datetime.now(timezone.utc)
        for i in range(10):
            self.tracker.record_event(
                category="model",
                name=f"free_model_{i}",
                tier="free",
                is_free=True,
                tokens_est=5000,
                timestamp=now.isoformat(),
            )

        for i in range(5):
            self.tracker.record_event(
                category="model",
                name=f"flash_{i}",
                tier="low_quota",
                is_free=False,
                tokens_est=5000,
                timestamp=now.isoformat(),
            )

        for i in range(5):
            self.tracker.record_event(
                category="model",
                name=f"claude_{i}",
                tier="premium",
                is_free=False,
                tokens_est=5000,
                timestamp=now.isoformat(),
            )

        report = self.tracker.get_report(include_antigravity=False)
        daily = report["daily"]

        self.assertEqual(daily["total_events"], 20)
        self.assertEqual(daily["free_events"], 10)
        self.assertEqual(daily["low_quota_events"], 5)
        self.assertEqual(daily["premium_events"], 5)
        self.assertEqual(daily["free_And_worker_ratio"], 75.0)
        self.assertAlmostEqual(daily["estimated_saved_usd"], 0.40, places=2)

    def test_scan_antigravity_brain(self):
        now = datetime.now(timezone.utc).isoformat()
        conv_dir = os.path.join(
            self.brain_dir, "fake-conv-123", ".system_generated", "logs"
        )
        os.makedirs(conv_dir, exist_ok=True)
        transcript_file = os.path.join(conv_dir, "transcript_full.jsonl")

        lines = [
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

        self.assertIn("1. KATMAN ÖZETİ", md)
        self.assertIn("2. MODELLER", md)
        self.assertIn("3. CLI ARAÇLARI", md)
        self.assertIn("4. AJANLAR & ALT AJANLAR", md)

        # 600K ücretsiz token > 400K Claude referansı -> %150.0 ve 🔥 olmalı!
        self.assertIn("🔥", md)


if __name__ == "__main__":
    unittest.main()
