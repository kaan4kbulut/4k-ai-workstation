"""Nexus AI Studio çekirdeği için birim testleri.

Bu testler ağ bağlantısı ve LLM olmadan çalışır: Ollama wrapper'ı yerine
bellek içi sahte (fake) bir uygulama kullanılır.

Çalıştırma:  python -m unittest discover -s tests -v
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dispatcher import Dispatcher  # noqa: E402
from core.parallel_executor import ParallelExecutor  # noqa: E402
from core.planner import TaskPlanner  # noqa: E402
from core.provider_config import (  # noqa: E402
    ProviderConfig,
    build_wrapper,
    load_provider_configs,
    parse_providers,
)
from core.quota_manager import QuotaManager  # noqa: E402
from core.router import IntelligentRouter  # noqa: E402
from wrappers.base_wrapper import BaseWrapper  # noqa: E402
from wrappers.hermes_wrapper import HermesWrapper  # noqa: E402
from wrappers.openai_compatible_wrapper import OpenAICompatibleWrapper  # noqa: E402


class FakeWrapper(BaseWrapper):
    """Bellek içi sahte wrapper; gerçek bir araca ihtiyaç duymaz."""

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
        self.assertIn("kayıtlı değil", result)

    def test_dispatch_parallel_collects_all_results(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper("A", FakeWrapper("A", "a"))
        dispatcher.register_wrapper("B", FakeWrapper("B", "b"))

        results = asyncio.run(dispatcher.dispatch_parallel(["A", "B"], "hi"))

        self.assertEqual(results, {"A": "a:hi", "B": "b:hi"})


class RouterTests(unittest.TestCase):
    def setUp(self):
        # Kota durumunu izole et; testler data/quotas.json'a bağlı kalmasın.
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
        """Regresyon: router, yalnızca Ollama bağlıyken bile Claude'u seçiyordu."""
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
        """Ollama (yetenek 5) karmaşıklığı 6 olan kod isteğini karşılayamaz."""
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

    def test_classify_task_detects_code_and_search(self):
        router = IntelligentRouter()
        self.assertIn("code", asyncio.run(router.classify_task("fix this bug")))
        self.assertIn("search", asyncio.run(router.classify_task("bugünkü güncel haberleri getir")))
        self.assertEqual(asyncio.run(router.classify_task("merhaba")), {"chat"})

    def test_strength_preference_routes_search_to_search_model(self):
        """Arama isteği, 'search' gücü olan modele gitmeli (ucuz yerel yerine)."""
        router = IntelligentRouter()
        router.register_tier("Perplexity", capability_score=6, cost_per_token=0.0, strengths={"search"})
        self.assertEqual(
            asyncio.run(
                router.select_best_model("bugünkü güncel haberleri getir", ["Ollama", "Perplexity"])
            ),
            "Perplexity",
        )

    def test_generic_chat_still_prefers_cheap_local(self):
        router = IntelligentRouter()
        router.register_tier("Perplexity", capability_score=6, cost_per_token=0.0, strengths={"search"})
        self.assertEqual(
            asyncio.run(router.select_best_model("merhaba", ["Ollama", "Perplexity"])),
            "Ollama",
        )

    def test_registered_tier_becomes_auto_selectable(self):
        router = IntelligentRouter()
        router.register_tier("ChatGPT", capability_score=10, cost_per_token=0.03, strengths={"chat", "reasoning"})
        self.assertEqual(
            asyncio.run(router.select_best_model("optimize security architecture", ["ChatGPT"])),
            "ChatGPT",
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
        """Regresyon: executor, wrapper'ı olmayan Claude'u seçiyordu."""
        dispatcher = Dispatcher()
        dispatcher.register_wrapper("Ollama", FakeWrapper("Ollama", "done"))
        executor = ParallelExecutor(dispatcher, IntelligentRouter())

        results = asyncio.run(
            executor.run_parallel([{"id": 1, "task": "optimize security architecture"}])
        )

        self.assertEqual(results[1]["model"], "Ollama")
        self.assertNotIn("kayıtlı değil", results[1]["response"])


class HermesWrapperTests(unittest.TestCase):
    def test_build_command_is_headless_and_stdin_based(self):
        wrapper = HermesWrapper(binary="hermes.exe", max_turns=3, run_budget=60)
        command = wrapper.build_command()

        self.assertEqual(command[0], "hermes.exe")
        self.assertIn("chat", command)
        self.assertIn("--query-file", command)  # istek stdin'den, argv'den değil
        self.assertIn("-", command)
        self.assertIn("-Q", command)  # sessiz: yalnızca final yanıt
        self.assertNotIn("--yolo", command)  # asla gözetimsiz çalıştırma
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
        wrapper.binary = None  # Hermes kurulu olmayan bir makineyi taklit et

        result = asyncio.run(wrapper.execute("hi"))

        self.assertIn("bulunamadı", result)

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
        """Mevcut bir quotas.json, sonradan eklenen wrapper'ları gizlememeli."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({"Ollama": {"limit": 10, "used": 4, "unit": "requests"}}, f)

        manager = QuotaManager(self.path)

        self.assertEqual(manager.quotas["Ollama"]["used"], 4)  # sayaç korundu
        self.assertIn("Hermes", manager.quotas)  # yeni model alındı


class OpenAICompatibleWrapperTests(unittest.TestCase):
    """Genel HTTP wrapper'ı, sahte taşıma ile ağa çıkmadan test eder."""

    def _wrapper(self, handler, api_key=None):
        transport = httpx.MockTransport(handler)
        return OpenAICompatibleWrapper(
            name="TestProvider",
            base_url="https://api.example.com/v1",
            model="test-model",
            api_key=api_key,
            transport=transport,
        )

    def test_execute_parses_openai_response_and_sends_auth(self):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            captured["auth"] = request.headers.get("authorization")
            body = json.loads(request.read().decode("utf-8"))
            captured["model"] = body["model"]
            captured["messages"] = body["messages"]
            return httpx.Response(200, json={"choices": [{"message": {"content": "MERHABA"}}]})

        result = asyncio.run(self._wrapper(handler, api_key="secret").execute("selam"))

        self.assertEqual(result, "MERHABA")
        self.assertTrue(captured["url"].endswith("/chat/completions"))
        self.assertEqual(captured["auth"], "Bearer secret")
        self.assertEqual(captured["model"], "test-model")
        self.assertEqual(captured["messages"], [{"role": "user", "content": "selam"}])

    def test_no_authorization_header_without_key(self):
        captured = {}

        def handler(request):
            captured["auth"] = request.headers.get("authorization")
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        asyncio.run(self._wrapper(handler).execute("selam"))

        self.assertIsNone(captured["auth"])

    def test_missing_key_reports_turkish_error(self):
        def handler(request):
            return httpx.Response(401, json={"error": "unauthorized"})

        result = asyncio.run(self._wrapper(handler).execute("selam"))

        self.assertIn("kimlik doğrulama", result)

    def test_connection_error_reports_turkish_error(self):
        def handler(request):
            raise httpx.ConnectError("boom")

        result = asyncio.run(self._wrapper(handler).execute("selam"))

        self.assertIn("ulaşılamadı", result)

    def test_unexpected_shape_reports_error(self):
        def handler(request):
            return httpx.Response(200, json={"nope": True})

        result = asyncio.run(self._wrapper(handler).execute("x"))

        self.assertIn("beklenmeyen", result)


class ProviderConfigTests(unittest.TestCase):
    def test_parse_providers_reads_metadata_and_env_key(self):
        os.environ["TEST_PROVIDER_KEY"] = "env-secret"
        try:
            configs = parse_providers(
                {
                    "providers": [
                        {
                            "name": "OpenRouter",
                            "base_url": "https://openrouter.ai/api/v1",
                            "model": "openai/gpt-4o-mini:free",
                            "api_key_env": "TEST_PROVIDER_KEY",
                            "capability": 9,
                            "cost": 0.0,
                            "strengths": ["chat", "reasoning"],
                        }
                    ]
                }
            )
        finally:
            del os.environ["TEST_PROVIDER_KEY"]

        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.name, "OpenRouter")
        self.assertEqual(config.api_key, "env-secret")
        self.assertEqual(config.capability_score, 9)
        self.assertEqual(config.strengths, ("chat", "reasoning"))

    def test_load_provider_configs_missing_file_is_empty(self):
        self.assertEqual(load_provider_configs("does-not-exist.json"), [])

    def test_load_provider_configs_reads_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "providers.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "providers": [
                            {
                                "name": "YerelOllama",
                                "base_url": "http://127.0.0.1:11434/v1",
                                "model": "llama3",
                            }
                        ]
                    },
                    handle,
                )

            configs = load_provider_configs(path)

            self.assertEqual(len(configs), 1)
            self.assertEqual(configs[0].name, "YerelOllama")
            self.assertIsNone(configs[0].api_key)  # anahtar verilmedi

    def test_build_wrapper_returns_openai_wrapper(self):
        wrapper = build_wrapper(
            ProviderConfig(name="P", base_url="https://x/v1", model="m", api_key="k")
        )
        self.assertIsInstance(wrapper, OpenAICompatibleWrapper)
        self.assertEqual(wrapper.name, "P")
        self.assertEqual(wrapper.model_name, "m")


if __name__ == "__main__":
    unittest.main()
