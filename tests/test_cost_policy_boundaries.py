"""Gerçek ağ çağrısı yapmadan maliyet politikasının güven sınırları."""

import asyncio
import unittest

import httpx

from core.provider_config import is_provider_zero_cost_allowed, parse_providers
from wrappers.openai_compatible_wrapper import OpenAICompatibleWrapper, is_zero_cost_allowed


class TestCostPolicyBoundaries(unittest.TestCase):
    def test_spoofed_hosts_and_local_flags_cannot_allow_remote_endpoints(self):
        for url in (
            "https://localhost.example.org/v1", "https://example.org/localhost",
            "https://127.0.0.1.example.org/v1", "https://example.org/?host=127.0.0.1",
            "http://localhost@example.org/v1", "file:///localhost/v1",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_zero_cost_allowed(url, "llama3"))
                self.assertFalse(is_provider_zero_cost_allowed(url, "llama3", is_local=True))

    def test_free_label_only_valid_on_exact_openrouter_endpoint(self):
        for url, model in (
            ("https://integrate.api.nvidia.com/v1", "model:free"),
            ("https://router.huggingface.co/v1", "model:free"),
            ("https://openrouter.ai.example.org/api/v1", "model:free"),
            ("http://openrouter.ai/api/v1", "model:free"),
            ("https://openrouter.ai/api/v1", "model:free-paid"),
            ("https://openrouter.ai/api/v1", ":free"),
        ):
            with self.subTest(url=url, model=model):
                self.assertFalse(is_zero_cost_allowed(url, model))
        self.assertTrue(is_zero_cost_allowed("http://[::1]:11434/v1", "llama3"))

    def test_invalid_declared_costs_cannot_bypass_check(self):
        for cost in (float("nan"), float("inf"), -1, 0.01):
            self.assertFalse(is_provider_zero_cost_allowed("http://localhost:11434/v1", "llama3", cost))

    def test_real_transport_is_not_a_policy_bypass(self):
        transport = httpx.AsyncHTTPTransport()
        try:
            self.assertFalse(is_zero_cost_allowed("https://api.openai.com/v1", "model", transport))
            wrapper = OpenAICompatibleWrapper("Paid", "https://api.openai.com/v1", "model", transport=transport)
            self.assertTrue(asyncio.run(wrapper.execute("hi")).startswith("Hata:"))
        finally:
            asyncio.run(transport.aclose())

    def test_remote_local_flag_does_not_mislabel_router_tier(self):
        configs = parse_providers({"providers": [{"name": "Free", "base_url": "https://openrouter.ai/api/v1", "model": "model:free", "local": True}]})
        self.assertFalse(configs[0].is_local)
