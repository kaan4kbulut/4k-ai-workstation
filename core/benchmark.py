"""Cihaz ve Yerel LLM Hız Benchmark'ı + Tek Tıkla Model İndirme.

Bu modül:
1. ``cpu_score`` ve ``disk_io_score`` ile hızlı çevrimdışı sistem skoru üretir.
2. ``llm_benchmark`` ile yerel Ollama üzerinde gerçek LLM çıkarım hızı
   (**Token/saniye**, **İlk Token Süresi / TTFT ms**, **Toplam Gecikme ms**)
   ölçümü yapar.
3. ``pull_ollama_model`` ile önerilen yerel modelleri (`/api/pull`) tek komutla
   indirir.
"""

from __future__ import annotations

import math
import os
import tempfile
import time

import httpx


def cpu_score() -> int:
    start = time.perf_counter()
    count = 10_000
    for _ in range(count):
        _ = math.sqrt(1234.5678)
        _ = math.sin(0.1234)
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        return 0
    score = max(1, min(100, int(count / elapsed / 100)))
    return score


def disk_io_score(tmpdir: str | None = None) -> int:
    if tmpdir is None:
        tmpdir = tempfile.gettempdir()

    path = os.path.join(tmpdir, f"nexus_bench_{os.getpid()}_{int(time.time()*1000)}.bin")
    data = b"x" * 64 * 1024  # 64KB
    start = time.perf_counter()
    try:
        with open(path, "wb") as f:
            for _ in range(16):  # 1MB toplam
                f.write(data)
            f.flush()
            os.fsync(f.fileno())
        with open(path, "rb") as f:
            _ = f.read()
        elapsed = max(0.0001, time.perf_counter() - start)
        size_mb = 1.0
        mb_per_sec = size_mb / elapsed
        return max(1, min(100, int(mb_per_sec / 5)))
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


def benchmark() -> dict:
    return {
        "cpu_score": cpu_score(),
        "disk_io_score": disk_io_score(),
        "notes": "Gerçek zamanlı CPU ve Disk G/Ç hız testi (1-100 ölçeği)",
    }


async def llm_benchmark(
    model: str | None = None,
    ollama_host: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Yerel Ollama üzerinde gerçek LLM üretim hızı (tokens/sn ve TTFT ms) ölçer."""
    host = (ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    target_model = model or os.environ.get("OLLAMA_MODEL") or "llama3"
    payload = {
        "model": target_model,
        "prompt": "1'den 15'e kadar sayıları aralarında virgül bırakarak yaz.",
        "stream": False,
    }
    wall_start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60.0, transport=transport) as client:
            res = await client.post(f"{host}/api/generate", json=payload)
    except Exception as exc:
        return {
            "status": "error",
            "model": target_model,
            "detail": f"Ollama sunucusuna ulaşılamadı: {exc}",
        }

    wall_ms = round((time.perf_counter() - wall_start) * 1000, 1)
    if res.status_code != 200:
        return {
            "status": "error",
            "model": target_model,
            "detail": f"HTTP {res.status_code}: {res.text[:200]}",
        }

    data = res.json()
    eval_count = int(data.get("eval_count") or 0)
    eval_duration_ns = int(data.get("eval_duration") or 0)
    prompt_eval_ns = int(data.get("prompt_eval_duration") or 0)
    total_duration_ns = int(data.get("total_duration") or 0)

    if eval_duration_ns > 0 and eval_count > 0:
        tokens_per_sec = round(eval_count / (eval_duration_ns / 1_000_000_000), 2)
    elif wall_ms > 0 and eval_count > 0:
        tokens_per_sec = round(eval_count / (wall_ms / 1000.0), 2)
    else:
        tokens_per_sec = 0.0

    ttft_ms = round(prompt_eval_ns / 1_000_000, 1) if prompt_eval_ns > 0 else 0.0
    total_ms = round(total_duration_ns / 1_000_000, 1) if total_duration_ns > 0 else wall_ms

    return {
        "status": "ok",
        "model": target_model,
        "tokens_per_sec": tokens_per_sec,
        "generated_tokens": eval_count,
        "ttft_ms": ttft_ms,
        "total_ms": total_ms,
        "sample_output": str(data.get("response", "")).strip()[:120],
    }


async def pull_ollama_model(
    model: str,
    ollama_host: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Yerel Ollama üzerinden belirtilen modeli indirir (/api/pull)."""
    host = (ollama_host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=600.0, transport=transport) as client:
            res = await client.post(
                f"{host}/api/pull",
                json={"name": model, "stream": False},
            )
            if res.status_code == 200:
                return {"status": "ok", "model": model, "detail": res.json().get("status", "success")}
            return {"status": "error", "model": model, "detail": res.text[:200]}
    except Exception as exc:
        return {"status": "error", "model": model, "detail": str(exc)}
