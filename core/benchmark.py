"""Basit, çevrimdışı CPU benchmark'ı.

Amaç: hızlıca kabaca bir skor elde etmek. Ağ veya LLM gerekmez; testler de
geçici bir dizinde küçük bir dosya oluşturup oku/yazar.

Gerçek bir ölçüm değil — prototip amaçlı sezgisel bir skor.
"""

from __future__ import annotations

import math
import os
import tempfile
import time


def cpu_score() -> int:
    start = time.perf_counter()
    count = 10_000
    # Basit sayısal işlem (matematik yükü)
    for _ in range(count):
        _ = math.sqrt(1234.5678)
        _ = math.sin(0.1234)
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        return 0
    # Daha hızlı → daha yüksek skor
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
