"""
Tests for workstation_cli
"""

import sys
import unittest
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from workstation_cli import build_engine, handle_command


class TestWorkstationCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Motorun hazır olduğunu doğrula
        cls.engine = build_engine()

    def test_handle_command_help(self):
        output = handle_command("help", self.engine)
        self.assertIsInstance(output, str)
        self.assertIn("4K AI WORKSTATION TERMİNAL KOMUTLARI", output)
        self.assertIn("usage", output)
        self.assertIn("status", output)
        self.assertIn("parallel", output)
        self.assertIn("build", output)

    def test_handle_command_usage(self):
        output = handle_command("usage", self.engine)
        self.assertIsInstance(output, str)
        self.assertTrue(len(output.strip()) > 0)
        # UsageTracker format_all_in_one_markdown çıktısında bulunan temel başlık ve göstergeler
        self.assertTrue(
            "KULLANIM" in output.upper()
            or "RAPOR" in output.upper()
            or "GÜNLÜK" in output.upper()
            or "HAFTALIK" in output.upper()
            or "TASARRUF" in output.upper()
        )

    def test_handle_command_status(self):
        output = handle_command("status", self.engine)
        self.assertIsInstance(output, str)
        self.assertIn("4K AI WORKSTATION - SİSTEM VE ÇALIŞMA DURUMU", output)
        self.assertIn("DONANIM:", output)
        self.assertIn("KURULU CLI AJANLARI:", output)
        self.assertIn("KAYITLI ÇALIŞMA MOTORLARI", output)
        self.assertIn("KOTA VE MODEL KULLANIM DURUMU:", output)

    def test_handle_command_empty(self):
        output = handle_command("", self.engine)
        self.assertEqual(output, "")

    def test_handle_command_turkish_aliases(self):
        yardim_output = handle_command("yardım", self.engine)
        self.assertIn("4K AI WORKSTATION TERMİNAL KOMUTLARI", yardim_output)

        durum_output = handle_command("durum", self.engine)
        self.assertIn("4K AI WORKSTATION - SİSTEM VE ÇALIŞMA DURUMU", durum_output)


if __name__ == "__main__":
    unittest.main()
