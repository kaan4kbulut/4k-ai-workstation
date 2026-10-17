"""Donanım tespiti ve yerel model önerisi.

Bu modül, sistem bilgilerini toplayıp (CPU çekirdeği, RAM, GPU VRAM) Ollama ile
kullanılmaya uygun yerel model önerileri üretir. Ağ erişimi gerekmez.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SystemInfo:
    os_name: str
    cpu_cores: int
    ram_gb: float
    gpu_name: str | None = None
    gpu_vram_gb: float | None = None


@dataclass
class ModelRecommendation:
    model: str
    reason: str
    fit: str  # "ideal" | "uygun" | "sınırlı"


def _get_cpu_cores() -> int:
    try:
        import multiprocessing

        return multiprocessing.cpu_count() or 4
    except Exception:
        return os.cpu_count() or 4


def _get_ram_gb() -> float:
    # psutil varsa ondan al
    try:
        import psutil  # type: ignore

        total_bytes = psutil.virtual_memory().total
        return round(total_bytes / (1024**3), 2)
    except Exception:
        pass

    # Windows: wmic
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                m = re.search(r"TotalPhysicalMemory=(\d+)", result.stdout)
                if m:
                    return round(int(m.group(1)) / (1024**3), 2)
        except Exception:
            pass

    # Linux/macOS: /proc/meminfo veya sysctl
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        m = re.findall(r"(\d+)", line)
                        if m:
                            return round(int(m[0]) * 1024 / (1024**3), 2)
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            m = re.findall(r"(\d+)", result.stdout)
            if m:
                return round(int(m[0]) / (1024**3), 2)
    except Exception:
        pass

    return 8.0


def _detect_gpu() -> tuple[str | None, float | None]:
    # nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            line = result.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            name = parts[0] if parts else None
            vram_mb = int(parts[1]) if len(parts) > 1 else 0
            return name, round(vram_mb / 1024, 2)
    except Exception:
        pass

    return None, None


def get_system_info() -> SystemInfo:
    gpu_name, gpu_vram = _detect_gpu()
    return SystemInfo(
        os_name=platform.system(),
        cpu_cores=_get_cpu_cores(),
        ram_gb=_get_ram_gb(),
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram,
    )


def recommend_local_models(info: SystemInfo | None = None) -> List[ModelRecommendation]:
    if info is None:
        info = get_system_info()

    recs: List[ModelRecommendation] = []

    vram = info.gpu_vram_gb or 0.0
    ram = info.ram_gb

    # Çok hafif (hemen çalıştırılabilir)
    recs.append(ModelRecommendation("llama3.2:3b", "Çok hafif, hızlı, CPU'da bile rahat", "uygun"))
    recs.append(ModelRecommendation("mistral:7b", "Dengeli kalite/hız", "uygun"))

    if ram >= 8.0:
        recs.append(ModelRecommendation("llama3:8b", "Dengeli, çoğu göreve yeterli", "uygun"))
    if ram >= 12.0:
        recs.append(ModelRecommendation("llama3.1:8b", "Daha kararlı, biraz daha ağır", "uygun"))
    if ram >= 16.0 or vram >= 8.0:
        recs.append(ModelRecommendation("llama3:70b", "Çok güçlü ama kaynak harcar", "sınırlı"))
    if vram >= 6.0:
        recs.append(ModelRecommendation("deepseek-coder:6.7b", "GPU ile kod yazmada iyi", "uygun"))
    if vram >= 8.0:
        recs.append(ModelRecommendation("gemma2:9b", "GPU ile dengeli, akıcı", "ideal"))

    # Tekrarsız kalsın
    seen = set()
    unique = []
    for r in recs:
        if r.model not in seen:
            seen.add(r.model)
            unique.append(r)
    return unique
