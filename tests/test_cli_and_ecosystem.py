"""CLI sarmalayıcıları (Codex, Claude Code, OpenCode), Librarian ve Tech Scout testleri."""

import asyncio
import os
import tempfile
import unittest

import httpx

from core.cli_registry import discover_cli_tools, register_available_cli_wrappers
from core.dispatcher import Dispatcher
from core.hardware import SystemInfo, recommend_local_models
from core.librarian import ModelLibrarian
from core.router import IntelligentRouter
from core.tech_scout import TechScout
from wrappers.claude_code_wrapper import ClaudeCodeWrapper
from wrappers.codex_wrapper import CodexWrapper
from wrappers.opencode_wrapper import OpenCodeWrapper


class CLIWrappersTests(unittest.TestCase):
    def test_codex_build_command_and_parse(self):
        w = CodexWrapper(binary="/fake/codex", model="o3", sandbox="read-only")
        cmd = w.build_command(output_file="/tmp/out.txt")
        self.assertEqual(cmd[0], "/fake/codex")
        self.assertIn("exec", cmd)
        self.assertIn("-m", cmd)
        self.assertIn("o3", cmd)
        self.assertIn("-o", cmd)
        self.assertEqual(cmd[-1], "-")
        self.assertEqual(CodexWrapper.parse_output(b"raw", b"", "son mesaj\n"), "son mesaj")
        self.assertEqual(CodexWrapper.parse_output(b"yedek cikti\n", b"", None), "yedek cikti")

    def test_codex_missing_binary_returns_error(self):
        w = CodexWrapper(binary=None)
        w.binary = None
        res = asyncio.run(w.execute("test"))
        self.assertTrue(res.startswith("Hata:"))

    def test_claude_code_build_command_and_parse(self):
        w = ClaudeCodeWrapper(binary="/fake/claude", model="sonnet", max_turns=4)
        cmd = w.build_command()
        self.assertEqual(cmd[:4], ["/fake/claude", "-p", "--output-format", "text"])
        self.assertIn("--model", cmd)
        self.assertIn("sonnet", cmd)
        self.assertIn("--max-turns", cmd)
        self.assertEqual(ClaudeCodeWrapper.parse_output(b"merhaba\n", b""), "merhaba")

    def test_claude_code_missing_binary_returns_error(self):
        w = ClaudeCodeWrapper(binary=None)
        w.binary = None
        res = asyncio.run(w.execute("test"))
        self.assertTrue(res.startswith("Hata:"))

    def test_opencode_build_command_and_parse(self):
        w = OpenCodeWrapper(binary="/fake/opencode", model="opencode/big-pickle")
        cmd = w.build_command("merhaba")
        self.assertEqual(cmd[0], "/fake/opencode")
        self.assertIn("run", cmd)
        self.assertIn("-m", cmd)
        self.assertEqual(cmd[-1], "merhaba")
        self.assertEqual(OpenCodeWrapper.parse_output(b"yanit\n", b""), "yanit")

    def test_discover_cli_tools_returns_all_supported_tools(self):
        tools = discover_cli_tools()
        names = {t.name for t in tools}
        for expected in ("Ollama", "Hermes", "Codex", "Claude", "OpenCode", "Antigravity"):
            self.assertIn(expected, names)

    def test_register_available_cli_wrappers_registers_installed(self):
        dispatcher = Dispatcher()
        router = IntelligentRouter()
        registered = register_available_cli_wrappers(dispatcher, router)
        for name in registered:
            self.assertIn(name, dispatcher.wrappers)
            self.assertIn(name, router.tiers)


class LibrarianAndScoutTests(unittest.TestCase):
    def test_librarian_ranks_coding_models_higher_for_code_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = ModelLibrarian(catalog_file=os.path.join(tmp, "catalog.json"))
            ranked_code = lib.rank_models_for_task("coding", only_free_or_local=True)
            self.assertGreater(len(ranked_code), 0)
            self.assertEqual(ranked_code[0]["id"], "qwen2.5-coder:14b")

    def test_librarian_refresh_catalog_marks_installed_ollama_models(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"models": [{"name": "llama3:latest"}, {"name": "custom-local:7b"}]},
            )

        transport = httpx.MockTransport(handler)
        with tempfile.TemporaryDirectory() as tmp:
            cat_path = os.path.join(tmp, "catalog.json")
            lib = ModelLibrarian(catalog_file=cat_path)
            catalog = asyncio.run(lib.refresh_catalog(transport=transport))
            installed_ids = {c.id for c in catalog if c.installed_locally}
            self.assertIn("llama3:latest", installed_ids)
            self.assertIn("custom-local:7b", installed_ids)
            self.assertTrue(os.path.exists(cat_path))

    def test_hardware_12gb_vram_recommends_14b_models(self):
        info = SystemInfo(
            os_name="Windows",
            cpu_cores=16,
            ram_gb=31.71,
            gpu_name="NVIDIA GeForce RTX 5070 Ti Laptop GPU",
            gpu_vram_gb=11.94,
        )
        recs = recommend_local_models(info)
        models = [r.model for r in recs]
        self.assertIn("qwen2.5-coder:14b", models)
        self.assertIn("deepseek-r1:14b", models)

    def test_tech_scout_identifies_underutilized_12gb_gpu(self):
        info = SystemInfo(
            os_name="Windows",
            cpu_cores=16,
            ram_gb=31.71,
            gpu_name="NVIDIA GeForce RTX 5070 Ti Laptop GPU",
            gpu_vram_gb=11.94,
        )
        scout = TechScout()
        report = scout.analyze_system(hw_info=info, installed_ollama_models=["llama3:latest"])
        self.assertGreaterEqual(report["summary"]["findings_count"], 2)
        categories = {f["category"] for f in report["findings"]}
        self.assertIn("donanım", categories)


if __name__ == "__main__":
    unittest.main()
