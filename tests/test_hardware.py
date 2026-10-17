"""Donanım ve benchmark testleri."""

import asyncio
import os
import tempfile
import unittest

from core.benchmark import benchmark, cpu_score, disk_io_score
from core.hardware import ModelRecommendation, get_system_info, recommend_local_models


class HardwareTests(unittest.TestCase):
    def test_get_system_info_returns_basic_fields(self):
        info = get_system_info()
        self.assertGreaterEqual(info.cpu_cores, 1)
        self.assertGreaterEqual(info.ram_gb, 0.1)
        self.assertIsInstance(info.os_name, str)

    def test_recommend_local_models_returns_unique_list(self):
        recs = recommend_local_models()
        self.assertGreaterEqual(len(recs), 1)
        models = [r.model for r in recs]
        self.assertEqual(len(models), len(set(models)))
        for r in recs:
            self.assertIn(r.fit, ("ideal", "uygun", "sınırlı"))
            self.assertTrue(r.reason)

    def test_recommend_local_models_accepts_custom_info(self):
        info = type("I", (), {"cpu_cores": 4, "ram_gb": 16.0, "gpu_name": "Test", "gpu_vram_gb": 8.0})()
        recs = recommend_local_models(info)
        self.assertTrue(any("gemma2:9b" in r.model or "8b" in r.model for r in recs))

    def test_cpu_score_is_in_range(self):
        score = cpu_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_disk_io_score_is_in_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            score = disk_io_score(tmp)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_benchmark_returns_dict(self):
        res = benchmark()
        self.assertIn("cpu_score", res)
        self.assertIn("disk_io_score", res)
        self.assertIsInstance(res["notes"], str)


if __name__ == "__main__":
    unittest.main()
