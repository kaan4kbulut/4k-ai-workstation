"""Unit tests for the Nexus AI Studio core.

These run without a network connection and without an LLM: the Ollama wrapper is
replaced by a fake in-memory implementation.

Run with:  python -m unittest discover -s tests -v
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dispatcher import Dispatcher  # noqa: E402
from core.parallel_executor import ParallelExecutor  # noqa: E402
from core.planner import TaskPlanner  # noqa: E402
from core.quota_manager import QuotaManager  # noqa: E402
from core.router import IntelligentRouter  # noqa: E402
from wrappers.base_wrapper import BaseWrapper  # noqa: E402
from wrappers.hermes_wrapper import HermesWrapper  # noqa: E402


class FakeWrapper(BaseWrapper):
    def __init__(self, name, answer="ok"):
        super().__init__(name)
        self.answer = answer
        self.calls = 0

    async def execute(self, prompt: str) -> str:
        self.calls += 1
        return f"{self.answer}:{prompt}"

    async def check_quota(self) -> float:
        return 1.0


class DispatcherTests(unittest.TestCase):
    def test_dispatch_routes_to_registered_wrapper(self):
        dispatcher = Dispatcher()
        wrapper = FakeWrapper("Ollama")
        dispatcher.register_wrapper("Ollama", wrapper)

        result = asyncio.run(dispatcher.dispatch("Ollama", "hi"))

        self.assertEqual(result, "ok:hi")
        self.assertEqual(wrapper.calls, 1)

    def test_dispatch_unknown_wrapper_returns_error(self):
        dispatcher = Dispatcher()
        result = asyncio.run(dispatcher.dispatch("Missing", "hi"))
        self.assertIn("not registered", result)

    def test_dispatch_parallel_collects_all_results(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper("A", FakeWrapper("A", "a"))
        dispatcher.register_wrapper("B", FakeWrapper("B", "b"))

        results = asyncio.run(dispatcher.dispatch_parallel(["A", "B"], "hi"))

        self.assertEqual(results, {"A": "a:hi", "B": "b:hi"})


class RouterTests(unittest.TestCase):
    def setUp(self):
        # Isolate quota state so tests do not depend on data/quotas.json.
        self._tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_simple_prompt_selects_cheapest_local_model(self):
        router = IntelligentRouter()
        self.assertEqual(asyncio.run(router.select_best_model("merhaba")), "Ollama")

    def test_complex_prompt_selects_most_capable_model(self):
        router = IntelligentRouter()
        self.assertEqual(
            asyncio.run(router.select_best_model("optimize security architecture")),
            "Claude",
        )

    def test_available_names_limits_the_choice(self):
        """Regression: the router used to pick Claude even when only Ollama was wired up."""
        router = IntelligentRouter()
        self.assertEqual(
            asyncio.run(router.select_best_model("optimize security architecture", ["Ollama"])),
            "Ollama",
        )

    def test_unknown_available_names_fall_back(self):
        router = IntelligentRouter()
        self.assertEqual(
            asyncio.run(router.select_best_model("merhaba", ["TotallyNewModel"])),
            "Ollama",
        )

    def test_hermes_is_chosen_for_code_when_ollama_is_too_weak(self):
        """Ollama (capability 5) cannot handle a complexity-6 coding prompt."""
        router = IntelligentRouter()
        self.assertEqual(
            asyncio.run(router.select_best_model("fix this bug", ["Ollama", "Hermes"])),
            "Hermes",
        )

    def test_free_local_model_wins_over_hermes_for_simple_prompts(self):
        router = IntelligentRouter()
        self.assertEqual(
            asyncio.run(router.select_best_model("merhaba", ["Ollama", "Hermes"])),
            "Ollama",
        )

    def test_exhausted_quota_falls_back(self):
        router = IntelligentRouter()
        router.quota_manager.quotas = {
            "Ollama": {"limit": 1, "used": 1, "unit": "requests"},
            "Codex": {"limit": 0, "used": 0, "unit": "requests"},
            "Claude": {"limit": 50, "used": 0, "unit": "requests"},
        }
        self.assertEqual(
            asyncio.run(router.select_best_model("optimize security architecture")),
            "Claude",
        )


class ParallelExecutorTests(unittest.TestCase):
    def test_parallel_run_reports_model_per_task(self):
        dispatcher = Dispatcher()
        wrapper = FakeWrapper("Ollama", "done")
        dispatcher.register_wrapper("Ollama", wrapper)

        router = IntelligentRouter()
        executor = ParallelExecutor(dispatcher, router)

        results = asyncio.run(
            executor.run_parallel(
                [{"id": 1, "task": "merhaba"}, {"id": 2, "task": "selam"}]
            )
        )

        self.assertEqual(results[1], {"model": "Ollama", "response": "done:merhaba"})
        self.assertEqual(results[2], {"model": "Ollama", "response": "done:selam"})
        self.assertEqual(wrapper.calls, 2)

    def test_parallel_run_does_not_route_to_unregistered_models(self):
        """Regression: executor used to pick Claude, which had no wrapper."""
        dispatcher = Dispatcher()
        dispatcher.register_wrapper("Ollama", FakeWrapper("Ollama", "done"))
        executor = ParallelExecutor(dispatcher, IntelligentRouter())

        results = asyncio.run(
            executor.run_parallel([{"id": 1, "task": "optimize security architecture"}])
        )

        self.assertEqual(results[1]["model"], "Ollama")
        self.assertNotIn("not registered", results[1]["response"])


class HermesWrapperTests(unittest.TestCase):
    def test_build_command_is_headless_and_stdin_based(self):
        wrapper = HermesWrapper(binary="hermes.exe", max_turns=3, run_budget=60)
        command = wrapper.build_command()

        self.assertEqual(command[0], "hermes.exe")
        self.assertIn("chat", command)
        self.assertIn("--query-file", command)  # prompt via stdin, not argv
        self.assertIn("-", command)
        self.assertIn("-Q", command)  # quiet: final response only
        self.assertNotIn("--yolo", command)  # never run unattended
        self.assertEqual(command[command.index("--max-turns") + 1], "3")
        self.assertEqual(command[command.index("--run-budget") + 1], "60")

    def test_build_command_includes_model_only_when_set(self):
        without = HermesWrapper(binary="hermes.exe", model=None).build_command()
        with_model = HermesWrapper(binary="hermes.exe", model="gpt-x").build_command()

        self.assertNotIn("-m", without)
        self.assertEqual(with_model[with_model.index("-m") + 1], "gpt-x")

    def test_parse_output_splits_response_and_session_id(self):
        response, session_id = HermesWrapper.parse_output(
            b"PONG\n", b"session_id: 20261017_152209_5f4d61\n"
        )

        self.assertEqual(response, "PONG")
        self.assertEqual(session_id, "20261017_152209_5f4d61")

    def test_parse_output_without_session_id(self):
        response, session_id = HermesWrapper.parse_output("hello", "")

        self.assertEqual(response, "hello")
        self.assertIsNone(session_id)

    def test_execute_without_binary_reports_error(self):
        wrapper = HermesWrapper(binary=None)
        wrapper.binary = None  # simulate a machine without Hermes installed

        result = asyncio.run(wrapper.execute("hi"))

        self.assertIn("bulunamadi", result)

    def test_is_available_reflects_binary(self):
        self.assertTrue(HermesWrapper(binary="hermes.exe").is_available())
        wrapper = HermesWrapper(binary=None)
        wrapper.binary = None
        self.assertFalse(wrapper.is_available())


class QuotaManagerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "data", "quotas.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_consume_persists_to_disk(self):
        manager = QuotaManager(self.path)
        manager.consume_quota("Claude")

        self.assertEqual(QuotaManager(self.path).quotas["Claude"]["used"], 1)

    def test_unknown_model_is_unlimited(self):
        manager = QuotaManager(self.path)
        self.assertTrue(manager.has_quota("SomeNewModel"))

    def test_new_models_are_merged_into_existing_file(self):
        """An existing quotas.json must not hide newly added wrappers."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"Ollama": {"limit": 10, "used": 4, "unit": "requests"}}, f)

        manager = QuotaManager(self.path)

        self.assertEqual(manager.quotas["Ollama"]["used"], 4)  # counter preserved
        self.assertIn("Hermes", manager.quotas)  # new model picked up


if __name__ == "__main__":
    unittest.main()
