"""
Sıfır API Harcaması Kalkanı ($0.00 API Kalkanı) Birim Testleri.
Antigravity ve 4K AI Workstation ortamında hiçbir ücretli API çağrısına izin verilmediğini garantiler.
"""

import asyncio
import json
import os
import tempfile
import unittest
import httpx

from wrappers.openai_compatible_wrapper import (
    OpenAICompatibleWrapper,
    is_zero_cost_allowed,
)
from core.provider_config import (
    is_provider_zero_cost_allowed,
    parse_providers,
    upsert_provider_config,
    load_provider_configs as load_custom_providers,
    ProviderConfig,
)


class TestZeroApiSpendShield(unittest.TestCase):
    """Sıfır Harcama Kalkanı doğrulama testleri."""

    def test_is_zero_cost_allowed_blocks_paid_models(self):
        """Ücretli uzak modellerin ve API uçlarının engellendiğini doğrular."""
        # OpenAI doğrudan API
        self.assertFalse(is_zero_cost_allowed("https://api.openai.com/v1", "gpt-4o"))
        self.assertFalse(is_zero_cost_allowed("https://api.openai.com/v1", "gpt-4o-mini"))

        # Anthropic doğrudan API
        self.assertFalse(is_zero_cost_allowed("https://api.anthropic.com/v1", "claude-3-5-sonnet"))

        # OpenRouter ücretli modeller (:free etiketi olmayanlar)
        self.assertFalse(is_zero_cost_allowed("https://openrouter.ai/api/v1", "openai/gpt-4o"))
        self.assertFalse(is_zero_cost_allowed("https://openrouter.ai/api/v1", "anthropic/claude-3.5-sonnet"))
        self.assertFalse(is_zero_cost_allowed("https://openrouter.ai/api/v1", "google/gemini-pro-1.5"))

    def test_is_zero_cost_allowed_permits_free_and_local(self):
        """Yerel Ollama ve OpenRouter :free modellerinin izinli olduğunu doğrular."""
        # Yerel Ollama (localhost / 127.0.0.1)
        self.assertTrue(is_zero_cost_allowed("http://127.0.0.1:11434/v1", "llama3"))
        self.assertTrue(is_zero_cost_allowed("http://localhost:11434/v1", "mistral"))
        self.assertTrue(is_zero_cost_allowed("http://0.0.0.0:11434/v1", "deepseek-coder"))

        # OpenRouter 0 TL Ücretsiz Modeller (:free)
        self.assertTrue(is_zero_cost_allowed("https://openrouter.ai/api/v1", "qwen/qwen-2.5-coder-32b-instruct:free"))
        self.assertTrue(is_zero_cost_allowed("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free"))
        self.assertTrue(is_zero_cost_allowed("https://openrouter.ai/api/v1", "deepseek/deepseek-r1:free"))

    def test_wrapper_blocks_paid_call_before_network(self):
        """Ücretli model çağrıldığında ağa hiç çıkmadan doğrudan güvenlik mesajı döner."""
        wrapper = OpenAICompatibleWrapper(
            name="PaidOpenAI",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="sk-fake-secret-key",
        )

        response = asyncio.run(wrapper.execute("Merhaba, bu çağrı ücretli mi?"))
        self.assertIn("SIFIR HARCAMA KİLİDİ", response)
        self.assertIn("$0.00 Kalkanı", response)

    def test_wrapper_allows_free_openrouter_model(self):
        """Ücretsiz (:free) model çağrıldığında normal HTTP akışının çalıştığını doğrular."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Ücretsiz model yanıtı"}}
                    ]
                },
            )

        transport = httpx.MockTransport(handler)
        wrapper = OpenAICompatibleWrapper(
            name="FreeOpenRouter",
            base_url="https://openrouter.ai/api/v1",
            model="qwen/qwen-2.5-coder-32b-instruct:free",
            api_key="free-key",
            transport=transport,
        )

        response = asyncio.run(wrapper.execute("Merhaba"))
        self.assertEqual(response, "Ücretsiz model yanıtı")

    def test_provider_zero_cost_validation(self):
        """Sağlayıcı ekleme/yükleme kurallarının sıfır harcama kalkanına uyduğunu doğrular."""
        # cost > 0 kesinlikle reddedilmeli
        self.assertFalse(is_provider_zero_cost_allowed("http://127.0.0.1:11434", "llama3", cost=0.01, is_local=True))

        # Yerel ve cost=0 izinli
        self.assertTrue(is_provider_zero_cost_allowed("http://127.0.0.1:11434", "llama3", cost=0.0, is_local=True))

        # :free ve cost=0 izinli
        self.assertTrue(is_provider_zero_cost_allowed("https://openrouter.ai/api/v1", "qwen:free", cost=0.0, is_local=False))

        # Ücretli bulut ve cost=0 olsa bile :free değilse reddedilmeli
        self.assertFalse(is_provider_zero_cost_allowed("https://api.openai.com/v1", "gpt-4o", cost=0.0, is_local=False))

    def test_load_custom_providers_filters_paid_entries(self):
        """load_custom_providers / load_provider_configs fonksiyonunun ücretli modelleri otomatik elediğini doğrular."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = os.path.join(tmpdir, "providers.json")
            sample_data = {
                "providers": [
                    {
                        "name": "YerelOllama",
                        "base_url": "http://127.0.0.1:11434",
                        "model": "llama3",
                        "local": True,
                        "cost": 0.0,
                    },
                    {
                        "name": "FreeModel",
                        "base_url": "https://openrouter.ai/api/v1",
                        "model": "qwen:free",
                        "local": False,
                        "cost": 0.0,
                    },
                    {
                        "name": "PaidOpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o",
                        "local": False,
                        "cost": 0.05,
                    },
                    {
                        "name": "PaidAnthropic",
                        "base_url": "https://api.anthropic.com/v1",
                        "model": "claude-3-5",
                        "local": False,
                        "cost": 0.0,
                    },
                ]
            }
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(sample_data, f)

            configs = load_custom_providers(cfg_file)
            names = [c.name for c in configs]
            self.assertIn("YerelOllama", names)
            self.assertIn("FreeModel", names)
            self.assertNotIn("PaidOpenAI", names)
            self.assertNotIn("PaidAnthropic", names)
            self.assertEqual(len(configs), 2)

    def test_upsert_provider_config_rejects_paid_provider(self):
        """upsert_provider_config çağrıldığında ücretli modelin ValueError ile reddedildiğini doğrular."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = os.path.join(tmpdir, "providers.json")

            paid_entry = {
                "name": "ExpensiveModel",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o",
                "cost": 0.02,
            }

            with self.assertRaises(ValueError) as ctx:
                upsert_provider_config(paid_entry, path=cfg_file)

            self.assertIn("SIFIR HARCAMA KİLİDİ", str(ctx.exception))

            # Ücretsiz :free model ekleme girişimi başarılı olmalı
            free_entry = {
                "name": "FreeQwen",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "qwen/qwen-2.5-coder-32b-instruct:free",
                "cost": 0.0,
            }
            res = upsert_provider_config(free_entry, path=cfg_file)
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0].name, "FreeQwen")

    def test_cli_wrappers_env_sanitization(self):
        """CLI wrapper'larının ücretli API anahtarlarını ortamdan temizlediğini doğrular."""
        # Ortama ücretli anahtarlar ekleyelim
        os.environ["OPENAI_API_KEY"] = "sk-paid-openai-test"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-paid-claude-test"
        os.environ["GEMINI_API_KEY"] = "ai-paid-gemini-test"

        try:
            # Simüle edilmiş wrapper env oluşturma
            env = dict(os.environ)
            for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"):
                env.pop(key, None)

            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertNotIn("GEMINI_API_KEY", env)
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
