"""Gerçek asenkron dağıtıcıyla çevrimdışı üretim ve onarım regresyonları."""

import asyncio
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.auto_healing import AutoHealingEngine
from core.dispatcher import Dispatcher
from core.quota_manager import QuotaManager
from core.router import IntelligentRouter
from core.software_swarm import SoftwareSwarm
from wrappers.base_wrapper import BaseWrapper
from workstation_cli import handle_command_async


class ScriptedWrapper(BaseWrapper):
    def __init__(self, replies):
        super().__init__("Offline")
        self.replies = iter(replies)
        self.calls = []

    async def execute(self, prompt):
        await asyncio.sleep(0)
        self.calls.append((prompt, threading.get_ident()))
        return next(self.replies)

    async def check_quota(self):
        return 1.0


class RecordingRouter(IntelligentRouter):
    def __init__(self, quota_manager):
        super().__init__(quota_manager)
        self.available_calls = []

    async def rank_escalation_chain(self, prompt, available_names=None):
        self.available_calls.append(list(available_names))
        return await super().rank_escalation_chain(prompt, available_names)


class PipelineAsyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.router = RecordingRouter(QuotaManager(str(self.root / "quotas.json")))
        self.router.register_tier("Offline", 10, strengths=["code", "reasoning"])
        self.dispatcher = Dispatcher()

    def register(self, replies):
        wrapper = ScriptedWrapper(replies)
        self.dispatcher.register_wrapper("Offline", wrapper)
        return wrapper

    def pipeline_replies(self):
        return [
            json.dumps({"project_title": "Async Test", "summary": "offline", "features": []}),
            json.dumps({"files": [{"path": "main.py", "purpose": "test"}],
                        "startup_command": "python main.py"}),
            "### FILE: main.py\n```python\nprint('pipeline-ok')\n```\n",
        ]

    def test_sync_pipeline_awaits_real_router_and_dispatcher(self):
        wrapper = self.register(self.pipeline_replies())
        swarm = SoftwareSwarm(router=self.router, dispatcher=self.dispatcher)
        result = swarm.run_full_pipeline("Test oluştur", str(self.root))
        self.assertEqual(result["pm_spec"]["project_title"], "Async Test")
        self.assertEqual((self.root / "main.py").read_text().strip(), "print('pipeline-ok')")
        self.assertEqual(len(wrapper.calls), 3)
        self.assertTrue(all(isinstance(prompt, str) for prompt, _ in wrapper.calls))
        self.assertEqual(self.router.available_calls, [["Offline"]] * 3)

    def test_healing_awaits_repair_and_reruns_actual_script(self):
        (self.root / "main.py").write_text("print(\n", encoding="utf-8")
        wrapper = self.register([
            "### FILE: main.py\n```python\nprint('repaired-ok')\n```\n"
        ])
        healing = AutoHealingEngine(router=self.router, dispatcher=self.dispatcher, max_attempts=2)
        result = healing.execute_with_healing(f'"{sys.executable}" main.py', str(self.root))
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], 2)
        self.assertIn("repaired-ok", result["stdout"])
        self.assertIn("SyntaxError", wrapper.calls[0][0])
        self.assertEqual(self.router.available_calls, [["Offline"]])

    def test_exhausted_dispatch_does_not_fabricate_successful_project(self):
        self.register(["Hata: offline unavailable"])
        swarm = SoftwareSwarm(router=self.router, dispatcher=self.dispatcher)
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            swarm.run_full_pipeline("Test", str(self.root))
        self.assertFalse((self.root / "requirements.txt").exists())

    def test_no_registered_provider_fails_without_output(self):
        swarm = SoftwareSwarm(router=self.router, dispatcher=self.dispatcher)
        with self.assertRaises(RuntimeError):
            swarm.run_full_pipeline("Test", str(self.root))
        self.assertEqual(self.router.available_calls, [[]])

    def test_registered_preferred_model_can_escalate_to_other_registered_model(self):
        failed = ScriptedWrapper(["Hata: try fallback"])
        self.dispatcher.register_wrapper("First", failed)
        wrapper = self.register(["fallback-ok"])
        swarm = SoftwareSwarm(router=self.router, dispatcher=self.dispatcher)
        self.assertEqual(swarm._dispatch_call("test", preferred_model="First"), "fallback-ok")
        self.assertEqual(len(failed.calls), 1)
        self.assertEqual(len(wrapper.calls), 1)
        with self.assertRaisesRegex(ValueError, "kayıtlı değil"):
            swarm._dispatch_call("test", preferred_model="Missing")

    def test_async_cli_runs_sync_pipeline_in_worker_thread(self):
        wrapper = self.register(self.pipeline_replies())
        engine = SimpleNamespace(
            software_swarm=SoftwareSwarm(router=self.router, dispatcher=self.dispatcher),
            auto_healing=AutoHealingEngine(router=self.router, dispatcher=self.dispatcher),
        )
        main_thread = threading.get_ident()
        with patch("workstation_cli.Path.home", return_value=self.root):
            result = asyncio.run(handle_command_async("oto offline_demo", engine))
        self.assertIn("Async Test", result)
        self.assertEqual(len(wrapper.calls), 3)
        self.assertTrue(all(thread != main_thread for _, thread in wrapper.calls))

    def test_async_cli_existing_project_runs_repair_in_worker_thread(self):
        project = self.root / "projects" / "demo"
        project.mkdir(parents=True)
        (project / "main.py").write_text("print(\n", encoding="utf-8")
        wrapper = self.register(["### FILE: main.py\n```python\nprint('run-ok')\n```\n"])
        engine = SimpleNamespace(
            auto_healing=AutoHealingEngine(router=self.router, dispatcher=self.dispatcher),
        )
        main_thread = threading.get_ident()
        with patch("workstation_cli.Path.home", return_value=self.root):
            result = asyncio.run(handle_command_async("calistir demo", engine))
        self.assertIn("run-ok", result)
        self.assertNotEqual(wrapper.calls[0][1], main_thread)


if __name__ == "__main__":
    unittest.main()
