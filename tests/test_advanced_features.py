"""Nexus AI Studio gelişmiş modülleri için kapsamlı birim testleri.

Test Edilen Modüller:
1. core/planner.py (TaskPlanner)
2. core/parallel_executor.py (ParallelExecutor)
3. core/router.py (IntelligentRouter) & core/dispatcher.py (Dispatcher)
4. core/session_memory.py (SessionMemory)
5. core/provider_config.py & core/quota_manager.py
6. core/benchmark.py, core/librarian.py, core/tech_scout.py

Tüm testler ağa çıkmadan (httpx.MockTransport ve tempfile ile) izole şekilde çalışır.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest

import httpx

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.benchmark import llm_benchmark, pull_ollama_model
from core.dispatcher import Dispatcher
from core.hardware import SystemInfo
from core.librarian import ModelLibrarian, ModelScoreCard
from core.parallel_executor import ParallelExecutor
from core.planner import TaskPlanner
from core.provider_config import (
    ProviderConfig,
    delete_provider_config,
    load_provider_configs,
    parse_providers,
    upsert_provider_config,
)
from core.quota_manager import QuotaManager
from core.router import IntelligentRouter
from core.session_memory import SessionMemory
from core.tech_scout import TechScout
from wrappers.base_wrapper import BaseWrapper


class MockWrapper(BaseWrapper):
    """Birim testler için bellek içi kontrollü sahte wrapper."""

    def __init__(
        self,
        name: str,
        response: str = "ok",
        should_fail: bool = False,
        error_message: str = "Hata: Mock hata oluştu",
    ):
        super().__init__(name)
        self.response = response
        self.should_fail = should_fail
        self.error_message = error_message
        self.call_count = 0
        self.last_prompt: str | None = None

    async def execute(self, prompt: str) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        if self.should_fail:
            return self.error_message
        return self.response

    async def check_quota(self) -> float:
        return 1.0


class TaskPlannerAdvancedTests(unittest.TestCase):
    """core/planner.py (TaskPlanner) testleri."""

    def test_parse_llm_plan_valid_json_and_markdown(self):
        # 1) Standart geçerli JSON
        raw_json = json.dumps(
            [
                {
                    "id": 1,
                    "title": "Mimari Tasarım",
                    "task": "Sistem mimarisini ve veritabanı şemasını planla",
                    "complexity": 9,
                    "type": "architecture",
                },
                {
                    "id": 2,
                    "title": "API Geliştirme",
                    "task": "FastAPI auth ve CRUD endpointlerini kodla",
                    "complexity": 7,
                    "type": "code",
                },
            ]
        )
        plan = TaskPlanner.parse_llm_plan(raw_json)
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan), 2)
        self.assertEqual(plan[0]["id"], 1)
        self.assertEqual(plan[0]["type"], "architecture")
        self.assertEqual(plan[1]["title"], "API Geliştirme")

        # 2) Markdown kod bloğu içine sarılmış JSON
        markdown_json = (
            "Elbette, işte belirlediğim alt görevler:\n"
            "```json\n"
            "[\n"
            '  {"id": 10, "task": "Sistem dokümantasyonunu ve kullanım kılavuzunu hazırla"}\n'
            "]\n"
            "```\n"
            "Umarım bu plan işinize yarar."
        )
        plan_md = TaskPlanner.parse_llm_plan(markdown_json)
        self.assertIsNotNone(plan_md)
        self.assertEqual(len(plan_md), 1)
        self.assertEqual(plan_md[0]["id"], 10)
        self.assertEqual(plan_md[0]["type"], "docs")
        self.assertEqual(plan_md[0]["complexity"], 3)

    def test_parse_llm_plan_invalid_inputs_return_none(self):
        # Boş metin, hata mesajı veya geçersiz JSON None dönmeli
        self.assertIsNone(TaskPlanner.parse_llm_plan(""))
        self.assertIsNone(TaskPlanner.parse_llm_plan("Hata: Model yanıt veremedi."))
        self.assertIsNone(TaskPlanner.parse_llm_plan("Bu sadece düz bir yanıttır."))
        self.assertIsNone(TaskPlanner.parse_llm_plan("[]"))
        self.assertIsNone(TaskPlanner.parse_llm_plan("[{'invalid_key': 123}]"))

    def test_decompose_multiline_and_bullet_points(self):
        planner = TaskPlanner()

        # Numaralı liste
        prompt_numbered = (
            "1. PostgreSQL şemasını ve mimarisini tasarla\n"
            "2. Kullanıcı CRUD endpointlerini kodla\n"
            "3. Rapor dokümantasyonunu hazırla"
        )
        subtasks_num = asyncio.run(planner.decompose(prompt_numbered))
        self.assertEqual(len(subtasks_num), 3)
        self.assertEqual(subtasks_num[0]["id"], 1)
        self.assertEqual(subtasks_num[0]["type"], "architecture")
        self.assertEqual(subtasks_num[1]["id"], 2)
        self.assertEqual(subtasks_num[1]["type"], "code")
        self.assertEqual(subtasks_num[2]["id"], 3)
        self.assertEqual(subtasks_num[2]["type"], "docs")

        # Madde işaretli liste (- / * / •)
        prompt_bullets = (
            "- Güncel AI modellerini internetten araştır\n"
            "- Modelleri sisteme bağlayan kodu uygula"
        )
        subtasks_bullets = asyncio.run(planner.decompose(prompt_bullets))
        self.assertEqual(len(subtasks_bullets), 2)
        self.assertEqual(subtasks_bullets[0]["type"], "search")
        self.assertEqual(subtasks_bullets[1]["type"], "code")

    def test_decompose_conjunction_ve(self):
        planner = TaskPlanner()
        prompt_ve = (
            "PostgreSQL veritabanı şemasını tasarla ve FastAPI kimlik doğrulama endpointlerini kodla"
        )
        subtasks = asyncio.run(planner.decompose(prompt_ve))
        self.assertGreaterEqual(len(subtasks), 2)
        self.assertIn("şemasını tasarla", subtasks[0]["task"])
        self.assertIn("endpointlerini kodla", subtasks[1]["task"])
        self.assertEqual(subtasks[0]["type"], "architecture")
        self.assertEqual(subtasks[1]["type"], "code")

    def test_decompose_with_llm_success_and_fallback(self):
        planner = TaskPlanner()
        dispatcher = Dispatcher()

        # 1) LLM başarılı JSON döndüğünde
        valid_llm_plan = json.dumps(
            [
                {
                    "id": 1,
                    "title": "Veri Katmanı",
                    "task": "SQLAlchemy modellerini kodla",
                    "complexity": 7,
                    "type": "code",
                }
            ]
        )
        dispatcher.register_wrapper("Ollama", MockWrapper("Ollama", response=valid_llm_plan))
        plan = asyncio.run(planner.decompose_with_llm("Örnek istek", dispatcher, "Ollama"))
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["title"], "Veri Katmanı")

        # 2) LLM hata döndürdüğünde kural tabanlı decompose'a düşmeli
        failing_dispatcher = Dispatcher()
        failing_dispatcher.register_wrapper(
            "Ollama", MockWrapper("Ollama", should_fail=True, error_message="Hata: Model meşgul")
        )
        fallback_plan = asyncio.run(
            planner.decompose_with_llm(
                "1. Birinci adım\n2. İkinci adım", failing_dispatcher, "Ollama"
            )
        )
        self.assertEqual(len(fallback_plan), 2)
        self.assertEqual(fallback_plan[0]["task"], "Birinci adım")


class ParallelExecutorSynthesisTests(unittest.TestCase):
    """core/parallel_executor.py (ParallelExecutor) testleri."""

    def test_build_fallback_synthesis(self):
        sub_tasks = [
            {"id": 1, "title": "Mimari Planlama", "task": "Sistem mimarisini hazırla"},
            {"id": 2, "title": "Kodlama", "task": "Ana fonksiyonları kodla"},
        ]
        results = {
            1: {"model": "Claude", "response": "Mimari şema ve güvenlik katmanı tasarlandı."},
            2: {"model": "Codex", "response": "FastAPI router kodları tamamlandı."},
        }
        fallback = ParallelExecutor.build_fallback_synthesis(
            "E-ticaret platformu kur", sub_tasks, results
        )

        self.assertIn("### 🎯 Birleştirilmiş Görev Çıktısı", fallback)
        self.assertIn("**Ana İstek:** E-ticaret platformu kur", fallback)
        self.assertIn("1. Mimari Planlama *(Model: `Claude`)*", fallback)
        self.assertIn("Mimari şema ve güvenlik katmanı tasarlandı.", fallback)
        self.assertIn("2. Kodlama *(Model: `Codex`)*", fallback)
        self.assertIn("FastAPI router kodları tamamlandı.", fallback)

    def test_synthesize_results_empty(self):
        dispatcher = Dispatcher()
        router = IntelligentRouter()
        executor = ParallelExecutor(dispatcher, router)

        res = asyncio.run(executor.synthesize_results("test", [], {}))
        self.assertEqual(res, {"model": "none", "response": ""})

    def test_synthesize_results_llm_success(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper(
            "SynthesizerModel",
            MockWrapper("SynthesizerModel", response="Tüm ajanların birleştirilmiş nihai çıktısı."),
        )
        router = IntelligentRouter()
        executor = ParallelExecutor(dispatcher, router)

        sub_tasks = [{"id": 1, "title": "Test Görev", "task": "Test"}]
        results = {1: {"model": "Ollama", "response": "Alt görev tamamlandı."}}

        res = asyncio.run(
            executor.synthesize_results(
                original_prompt="Test projesi",
                sub_tasks=sub_tasks,
                results=results,
                synthesizer_model="SynthesizerModel",
            )
        )
        self.assertEqual(res["model"], "SynthesizerModel")
        self.assertEqual(res["response"], "Tüm ajanların birleştirilmiş nihai çıktısı.")

    def test_synthesize_results_fallback_on_error(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper(
            "SynthesizerModel",
            MockWrapper("SynthesizerModel", should_fail=True, error_message="Hata: Model hatası"),
        )
        router = IntelligentRouter()
        executor = ParallelExecutor(dispatcher, router)

        sub_tasks = [{"id": 1, "title": "Görev 1", "task": "Birinci iş"}]
        results = {1: {"model": "Ollama", "response": "İş yapıldı."}}

        res = asyncio.run(
            executor.synthesize_results(
                original_prompt="Genel görev",
                sub_tasks=sub_tasks,
                results=results,
                synthesizer_model="SynthesizerModel",
            )
        )
        self.assertEqual(res["model"], "Aggregator (Yerel Birleştirici)")
        self.assertIn("### 🎯 Birleştirilmiş Görev Çıktısı", res["response"])
        self.assertIn("1. Görev 1 *(Model: `Ollama`)*", res["response"])


class EscalationRoutingAndDispatchTests(unittest.TestCase):
    """core/router.py & core/dispatcher.py eskalasyon zinciri testleri."""

    def test_rank_escalation_chain_ordering(self):
        router = IntelligentRouter()

        # Kodlama isteği (karmaşıklık 6, 'code' yeteneği eşleşmesi)
        # Model tablosu:
        # Ollama: yetenek 5 (baraj altı, yedek havuza gider)
        # Codex: yetenek 7, maliyet 0.01, 'code'
        # Hermes: yetenek 8, maliyet 0.02, 'code'
        # Claude: yetenek 10, maliyet 0.05, 'code'
        # Sıralama: maliyet artan (Codex, Hermes, Claude) + kalanlar yetenek azalan (Ollama)
        chain = asyncio.run(
            router.rank_escalation_chain("Python kodundaki hatayı fix et ve fonksiyonu yaz")
        )
        self.assertEqual(chain, ["Codex", "Hermes", "Claude", "Ollama"])

        # Sadece izin verilen modellerle sınırlama
        chain_filtered = asyncio.run(
            router.rank_escalation_chain(
                "Python kodundaki hatayı fix et", available_names=["Ollama", "Hermes"]
            )
        )
        self.assertEqual(chain_filtered, ["Hermes", "Ollama"])

    def test_dispatch_with_escalation_first_fails_second_succeeds(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper(
            "PrimaryModel",
            MockWrapper("PrimaryModel", should_fail=True, error_message="Hata: 503 Servis Dışı"),
        )
        dispatcher.register_wrapper(
            "BackupModel",
            MockWrapper("BackupModel", response="İkinci model başarıyla tamamladı."),
        )

        candidates = ["PrimaryModel", "BackupModel"]
        res = asyncio.run(dispatcher.dispatch_with_escalation(candidates, "Veritabanını tasarla"))

        self.assertEqual(res["model"], "BackupModel")
        self.assertEqual(res["response"], "İkinci model başarıyla tamamladı.")
        self.assertTrue(res["escalated"])
        self.assertEqual(len(res["attempts"]), 2)
        self.assertEqual(res["attempts"][0]["model"], "PrimaryModel")
        self.assertEqual(res["attempts"][0]["status"], "error")
        self.assertIn("503", res["attempts"][0]["detail"])
        self.assertEqual(res["attempts"][1]["model"], "BackupModel")
        self.assertEqual(res["attempts"][1]["status"], "ok")

    def test_dispatch_with_escalation_first_succeeds_no_escalation(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper("ModelA", MockWrapper("ModelA", response="İlk seferde başarılı."))
        dispatcher.register_wrapper("ModelB", MockWrapper("ModelB", response="İkinci model yanıtı."))

        res = asyncio.run(dispatcher.dispatch_with_escalation(["ModelA", "ModelB"], "Selam"))
        self.assertEqual(res["model"], "ModelA")
        self.assertEqual(res["response"], "İlk seferde başarılı.")
        self.assertFalse(res["escalated"])
        self.assertEqual(len(res["attempts"]), 1)
        self.assertEqual(res["attempts"][0]["status"], "ok")

    def test_dispatch_with_escalation_all_fail(self):
        dispatcher = Dispatcher()
        dispatcher.register_wrapper("ModelA", MockWrapper("ModelA", should_fail=True, error_message="Hata: A çöktü"))
        dispatcher.register_wrapper("ModelB", MockWrapper("ModelB", should_fail=True, error_message="Hata: B çöktü"))

        res = asyncio.run(dispatcher.dispatch_with_escalation(["ModelA", "ModelB"], "Görev"))
        self.assertEqual(res["model"], "ModelB")
        self.assertTrue(res["escalated"])
        self.assertEqual(len(res["attempts"]), 2)
        self.assertTrue(res["response"].startswith("Hata:"))


class SessionMemoryTests(unittest.TestCase):
    """core/session_memory.py (SessionMemory) testleri."""

    def test_session_memory_full_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = os.path.join(tmpdir, "sessions.json")
            memory = SessionMemory(storage_file=storage_path, max_context_turns=2)

            # Başlangıçta oturum boş
            self.assertEqual(memory.get_history("proje_1"), [])
            self.assertEqual(memory.build_contextual_prompt("proje_1", "İlk soru"), "İlk soru")

            # 1. Tur ekle
            memory.append_turn(
                session_id="proje_1",
                user_prompt="PostgreSQL nedir?",
                assistant_response="İlişkisel bir veritabanı yönetim sistemidir.",
                model_used="Ollama",
            )
            history = memory.get_history("proje_1")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["user"], "PostgreSQL nedir?")
            self.assertEqual(history[0]["assistant"], "İlişkisel bir veritabanı yönetim sistemidir.")
            self.assertEqual(history[0]["model"], "Ollama")
            self.assertIn("timestamp", history[0])

            # Diske kalıcı yazıldığını doğrula
            memory_reloaded = SessionMemory(storage_file=storage_path, max_context_turns=2)
            self.assertEqual(len(memory_reloaded.get_history("proje_1")), 1)

            # 2. ve 3. Turları ekle
            memory.append_turn("proje_1", "Tablo nasıl oluşturulur?", "CREATE TABLE ile.", "Codex")
            memory.append_turn("proje_1", "İndeks nasıl eklenir?", "CREATE INDEX ile.", "Claude")

            # max_context_turns=2 olduğundan son 2 tur bağlama dahil edilmeli (1. tur elenmeli)
            contextual = memory.build_contextual_prompt("proje_1", "Performansı nasıl optimize ederim?")
            self.assertIn("[Önceki Konuşma Bağlamı]", contextual)
            self.assertNotIn("PostgreSQL nedir?", contextual)
            self.assertIn("Tablo nasıl oluşturulur?", contextual)
            self.assertIn("İndeks nasıl eklenir?", contextual)
            self.assertIn("[Yeni İstek]\nPerformansı nasıl optimize ederim?", contextual)

            # Oturumu temizle
            memory.clear_session("proje_1")
            self.assertEqual(memory.get_history("proje_1"), [])
            re_check = SessionMemory(storage_file=storage_path)
            self.assertEqual(re_check.get_history("proje_1"), [])
            self.assertIn("proje_1", memory.list_sessions())


class ProviderConfigAndQuotaTests(unittest.TestCase):
    """core/provider_config.py & core/quota_manager.py testleri."""

    def test_upsert_and_delete_provider_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "providers.json")

            # 1) Yeni sağlayıcı ekle
            groq_entry = {
                "name": "Groq",
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "api_key": "gsk_test123",
                "capability": 9,
                "cost": 0.01,
                "strengths": ["chat", "code"],
            }
            configs = upsert_provider_config(groq_entry, path=cfg_path)
            self.assertEqual(len(configs), 1)
            self.assertEqual(configs[0].name, "Groq")
            self.assertEqual(configs[0].model, "llama-3.3-70b-versatile")
            self.assertEqual(configs[0].capability_score, 9)

            # 2) Sağlayıcıyı güncelle (modelini değiştir, liste uzunluğu 1 kalmalı)
            groq_entry_updated = dict(groq_entry)
            groq_entry_updated["model"] = "mixtral-8x7b-32768"
            configs_updated = upsert_provider_config(groq_entry_updated, path=cfg_path)
            self.assertEqual(len(configs_updated), 1)
            self.assertEqual(configs_updated[0].model, "mixtral-8x7b-32768")

            # 3) İkinci bir sağlayıcı ekle
            openrouter_entry = {
                "name": "OpenRouterCustom",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "anthropic/claude-3.5-sonnet",
            }
            configs_two = upsert_provider_config(openrouter_entry, path=cfg_path)
            self.assertEqual(len(configs_two), 2)

            # 4) Sağlayıcıyı sil
            configs_after_delete = delete_provider_config("Groq", path=cfg_path)
            self.assertEqual(len(configs_after_delete), 1)
            self.assertEqual(configs_after_delete[0].name, "OpenRouterCustom")

            # Dosyadan tekrar yükleyerek kalıcılığı doğrula
            persisted = load_provider_configs(path=cfg_path)
            self.assertEqual(len(persisted), 1)
            self.assertEqual(persisted[0].name, "OpenRouterCustom")

    def test_set_quota_limit_and_reset_quota(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            quota_path = os.path.join(tmpdir, "quotas.json")
            qm = QuotaManager(quota_file=quota_path)

            # Limit güncelleme
            qm.set_quota_limit("Ollama", 500)
            self.assertEqual(qm.get_quota_status()["Ollama"]["limit"], 500)

            # Yeni bir modele kota tanımlama
            qm.set_quota_limit("DeepSeek", 300)
            self.assertEqual(qm.get_quota_status()["DeepSeek"]["limit"], 300)

            # Kota tüketimi
            qm.consume_quota("Ollama")
            qm.consume_quota("Ollama")
            qm.consume_quota("DeepSeek")
            self.assertEqual(qm.get_quota_status()["Ollama"]["used"], 2)
            self.assertEqual(qm.get_quota_status()["DeepSeek"]["used"], 1)

            # Tek bir modelin kotasını sıfırlama
            qm.reset_quota("Ollama")
            self.assertEqual(qm.get_quota_status()["Ollama"]["used"], 0)
            self.assertEqual(qm.get_quota_status()["DeepSeek"]["used"], 1)

            # Tüm kotaları topluca sıfırlama
            qm.reset_quota()
            self.assertEqual(qm.get_quota_status()["DeepSeek"]["used"], 0)

            # Dosyadan yüklenen yeni örnekle diske yazıldığını doğrula
            qm_reloaded = QuotaManager(quota_file=quota_path)
            self.assertEqual(qm_reloaded.get_quota_status()["Ollama"]["limit"], 500)
            self.assertEqual(qm_reloaded.get_quota_status()["DeepSeek"]["limit"], 300)
            self.assertEqual(qm_reloaded.get_quota_status()["DeepSeek"]["used"], 0)


class BenchmarkLibrarianScoutMockTests(unittest.TestCase):
    """core/benchmark.py, core/librarian.py, core/tech_scout.py için MockTransport testleri."""

    def test_llm_benchmark_mock_transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/generate":
                return httpx.Response(
                    200,
                    json={
                        "model": "llama3",
                        "response": "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15",
                        "eval_count": 30,
                        "eval_duration": 1_000_000_000,
                        "prompt_eval_duration": 120_000_000,
                        "total_duration": 1_120_000_000,
                    },
                )
            return httpx.Response(404, text="Bulunamadı")

        transport = httpx.MockTransport(handler)
        result = asyncio.run(
            llm_benchmark(
                model="llama3",
                ollama_host="http://mock-ollama:11434",
                transport=transport,
            )
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["model"], "llama3")
        self.assertEqual(result["tokens_per_sec"], 30.0)
        self.assertEqual(result["ttft_ms"], 120.0)
        self.assertEqual(result["total_ms"], 1120.0)
        self.assertEqual(result["generated_tokens"], 30)
        self.assertIn("1, 2, 3", result["sample_output"])

    def test_pull_ollama_model_mock_transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/pull":
                return httpx.Response(200, json={"status": "success"})
            return httpx.Response(404, text="Bulunamadı")

        transport = httpx.MockTransport(handler)
        result = asyncio.run(
            pull_ollama_model(
                model="qwen2.5-coder:14b",
                ollama_host="http://mock-ollama:11434",
                transport=transport,
            )
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["model"], "qwen2.5-coder:14b")
        self.assertEqual(result["detail"], "success")

    def test_fetch_openrouter_free_models_mock_transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "openrouter.ai" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "meta-llama/llama-3.3-70b-instruct:free",
                                "description": "Ücretsiz açık kaynak model",
                                "pricing": {"prompt": "0", "completion": "0"},
                                "context_length": 65536,
                            },
                            {
                                "id": "openai/gpt-4o",
                                "description": "Ücretli model",
                                "pricing": {"prompt": "0.005", "completion": "0.015"},
                                "context_length": 128000,
                            },
                        ]
                    },
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        librarian = ModelLibrarian()
        models = asyncio.run(librarian.fetch_openrouter_free_models(transport=transport))

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "meta-llama/llama-3.3-70b-instruct:free")
        self.assertTrue(models[0].is_free_or_local)
        self.assertEqual(models[0].provider, "OpenRouter (Ücretsiz Bulut)")
        self.assertIn("cheap", models[0].tags)
        self.assertIn("cloud", models[0].tags)

    def test_fetch_huggingface_trending_models_mock_transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "huggingface.co" in str(request.url):
                return httpx.Response(
                    200,
                    json=[
                        {
                            "id": "bartowski/Qwen2.5-Coder-14B-Instruct-GGUF",
                            "likes": 520,
                            "downloads": 18500,
                        }
                    ],
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        librarian = ModelLibrarian()
        models = asyncio.run(librarian.fetch_huggingface_trending_models(transport=transport))

        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "bartowski/Qwen2.5-Coder-14B-Instruct-GGUF")
        self.assertEqual(models[0].provider, "HuggingFace (Trend GGUF)")
        self.assertTrue(models[0].is_free_or_local)
        self.assertIn("gguf", models[0].tags)
        self.assertIn("code", models[0].tags)
        self.assertEqual(models[0].min_vram_gb, 10.5)

    def test_fetch_github_ai_trends_mock_transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "api.github.com" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "full_name": "modelcontextprotocol/python-sdk",
                                "description": "Python SDK for MCP",
                                "stargazers_count": 9500,
                                "html_url": "https://github.com/modelcontextprotocol/python-sdk",
                                "topics": ["mcp", "ai-agents", "llm-routing"],
                            }
                        ]
                    },
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        scout = TechScout()
        repos = asyncio.run(scout.fetch_github_ai_trends(transport=transport))

        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]["full_name"], "modelcontextprotocol/python-sdk")
        self.assertEqual(repos[0]["stars"], 9500)
        self.assertEqual(repos[0]["url"], "https://github.com/modelcontextprotocol/python-sdk")
        self.assertIn("mcp", repos[0]["topics"])

    def test_full_scout_report_mock_transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "api.github.com" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "items": [
                            {
                                "full_name": "modelcontextprotocol/python-sdk",
                                "description": "Python SDK for MCP",
                                "stargazers_count": 9500,
                                "html_url": "https://github.com/modelcontextprotocol/python-sdk",
                                "topics": ["mcp", "ai-agents"],
                            }
                        ]
                    },
                )
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        scout = TechScout()

        # 1) Canlı/online modda GitHub trendleri dahil rapor
        report_online = asyncio.run(
            scout.full_scout_report(include_online=True, transport=transport)
        )
        self.assertIn("summary", report_online)
        self.assertIn("packages", report_online)
        self.assertIn("findings", report_online)
        self.assertIn("github_trends", report_online)
        self.assertEqual(len(report_online["github_trends"]), 1)
        self.assertEqual(
            report_online["github_trends"][0]["full_name"], "modelcontextprotocol/python-sdk"
        )

        # 2) Çevrimdışı modda github_trends boş liste olmalı
        report_offline = asyncio.run(scout.full_scout_report(include_online=False))
        self.assertEqual(report_offline["github_trends"], [])


if __name__ == "__main__":
    unittest.main()
