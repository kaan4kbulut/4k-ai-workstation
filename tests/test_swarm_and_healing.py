"""
Tests for core.software_swarm and core.auto_healing
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.software_swarm import SoftwareSwarm
from core.auto_healing import AutoHealingEngine
from core.workspace_builder import WorkspaceBuilder


class TestSoftwareSwarmAndAutoHealing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_software_swarm_phases_mocked(self):
        mock_router = MagicMock()
        mock_dispatcher = MagicMock()

        # PM aşaması için sahte yanıt
        pm_response = json.dumps({
            "project_title": "Test Projesi",
            "summary": "Kullanıcı test projesi",
            "features": ["Giriş Ekranı", "Veri Listeleme"],
            "user_roles": ["Admin"],
            "recommended_stack": {"backend": "FastAPI", "frontend": "HTML"},
        })

        # Mimar aşaması için sahte yanıt
        arch_response = json.dumps({
            "database_schema": "CREATE TABLE users (id INT);",
            "files": [
                {"path": "server.py", "purpose": "API"},
                {"path": "index.html", "purpose": "UI"},
            ],
            "startup_command": "python server.py",
        })

        # Geliştirici aşaması için sahte yanıt
        dev_response = (
            "### FILE: server.py\n```python\nprint('Server running')\n```\n\n"
            "### FILE: index.html\n```html\n<h1>Test</h1>\n```\n"
        )

        mock_dispatcher.dispatch_with_escalation.side_effect = [
            {"response": pm_response},
            {"response": arch_response},
            {"response": dev_response},
        ]

        swarm = SoftwareSwarm(router=mock_router, dispatcher=mock_dispatcher)

        result = swarm.run_full_pipeline(
            user_goal="Test web paneli yap",
            workspace_dir=self.workspace,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["pm_spec"]["project_title"], "Test Projesi")
        self.assertTrue(os.path.exists(os.path.join(self.workspace, "server.py")))
        self.assertTrue(os.path.exists(os.path.join(self.workspace, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(self.workspace, "requirements.txt")))

    def test_auto_healing_missing_package_detection(self):
        engine = AutoHealingEngine()
        err_msg = "ModuleNotFoundError: No module named 'fastapi'"
        pkg = engine._detect_missing_package(err_msg)
        self.assertEqual(pkg, "fastapi")

        err_msg_yaml = "ImportError: No module named 'yaml'"
        pkg_yaml = engine._detect_missing_package(err_msg_yaml)
        self.assertEqual(pkg_yaml, "pyyaml")

    def test_auto_healing_successful_command(self):
        engine = AutoHealingEngine()
        # Başarılı çalışan basit komut
        cmd = f'"{sys.executable}" -c "print(\'Hello 4K AI Workstation\')"'
        result = engine.execute_with_healing(cmd, self.workspace)
        self.assertTrue(result["success"])
        self.assertIn("Hello 4K AI Workstation", result["stdout"])

    def test_auto_healing_code_repair_flow(self):
        mock_router = MagicMock()
        mock_dispatcher = MagicMock()

        # Bozuk dosya oluştur
        bad_file = os.path.join(self.workspace, "bad_script.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("def broken_syntax(\n")  # Syntax error!

        # Model sahte onarım yanıtı
        repair_response = (
            "### FILE: bad_script.py\n"
            "```python\n"
            "def broken_syntax():\n"
            "    return 'repaired'\n"
            "print(broken_syntax())\n"
            "```\n"
        )
        mock_dispatcher.dispatch_with_escalation.return_value = {"response": repair_response}

        engine = AutoHealingEngine(router=mock_router, dispatcher=mock_dispatcher, max_attempts=2)

        # İlk çalıştırma hata verecek, ardından repair_code dosyayı düzeltecek ve 2. denemede geçecek
        cmd = f'"{sys.executable}" bad_script.py'
        result = engine.execute_with_healing(cmd, self.workspace)

        self.assertTrue(result["success"])
        self.assertTrue(result["healing_applied"])
        with open(bad_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("def broken_syntax():", content)


if __name__ == "__main__":
    unittest.main()
