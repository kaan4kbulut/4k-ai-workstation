"""Faz 5: Teknoloji Gözcüsü (Tech Scout) ve Sistem Evrim Analizörü.

Bu modül:
1. Sistemin mevcut donanımını (RAM/VRAM), kurulu CLI ajanlarını ve sağlayıcı
   yapılandırmasını denetler.
2. Eksik bileşenleri, kullanılmayan donanım kapasitesini (ör. 12 GB VRAM olup
   yalnızca 8B model kullanılması) ve açık kaynak AI orkestrasyon çözümlerini
   analiz ederek somut iyileştirme önerileri üretir.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List

from core.cli_registry import discover_cli_tools
from core.hardware import SystemInfo, get_system_info


@dataclass
class ScoutFinding:
    """Tek bir sistem veya teknoloji iyileştirme önerisi."""

    category: str  # "donanım" | "cli_ajan" | "mimari" | "açık_kaynak"
    priority: str  # "yüksek" | "orta" | "bilgi"
    title: str
    recommendation: str
    action_command: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class TechScout:
    """Sistemin durumunu analiz edip evrim/optimizasyon önerileri üretir."""

    def analyze_system(
        self,
        hw_info: SystemInfo | None = None,
        installed_ollama_models: List[str] | None = None,
    ) -> dict:
        if hw_info is None:
            hw_info = get_system_info()
        cli_tools = discover_cli_tools()
        installed_clis = [t.name for t in cli_tools if t.installed]
        missing_clis = [t for t in cli_tools if not t.installed]
        ollama_models = installed_ollama_models or []

        findings: list[ScoutFinding] = []

        # 1) Donanım kapasitesi ve yerel model uyumu
        vram = hw_info.gpu_vram_gb or 0.0
        if vram >= 11.0:
            has_14b = any("14b" in m.lower() for m in ollama_models)
            if not has_14b:
                findings.append(
                    ScoutFinding(
                        category="donanım",
                        priority="yüksek",
                        title=f"{hw_info.gpu_name or 'GPU'} ({vram:.1f} GB VRAM) tam kapasite kullanılmıyor",
                        recommendation=(
                            "Cihazınızda 12 GB sınıfı güçlü bir GPU var. Sadece 8B model yerine "
                            "kodlama için 'qwen2.5-coder:14b' ve akıl yürütme için 'deepseek-r1:14b' "
                            "modellerini yerel olarak sıfır maliyetle ve yüksek hızda çalıştırabilirsiniz."
                        ),
                        action_command="ollama pull qwen2.5-coder:14b",
                    )
                )

        # 2) Eksik CLI abonelik ajanları
        for missing in missing_clis:
            if missing.name == "Claude":
                findings.append(
                    ScoutFinding(
                        category="cli_ajan",
                        priority="orta",
                        title="Claude Code CLI kurulu değil (Claude masaüstü kurulu ama CLI eksik)",
                        recommendation=(
                            "Claude aboneliğinizi Nexus AI Studio üzerinden otomatik tetiklemek için "
                            "Claude Code CLI aracını kurabilirsiniz. Kurulduğunda sistem otomatik algılar."
                        ),
                        action_command=missing.install_hint,
                    )
                )

        # 3) Açık kaynak AI Orkestrasyon & Performans çözümleri
        findings.append(
            ScoutFinding(
                category="açık_kaynak",
                priority="orta",
                title="Anlamsal Yönlendirme (Semantic Routing & Embedding Triage)",
                recommendation=(
                    "Anahtar kelime tabanlı yönlendirmeye ek olarak yerel 'nomic-embed-text' "
                    "embedding modeli ile görev sınıflandırması (Semantic Router) yapılarak "
                    "yönlendirme isabeti %95+ seviyesine çıkarılabilir."
                ),
                action_command="ollama pull nomic-embed-text",
            )
        )
        findings.append(
            ScoutFinding(
                category="mimari",
                priority="bilgi",
                title="Çoklu Ajan Sentezi (Mixture-of-Agents / MoA)",
                recommendation=(
                    "Paralel yürütme (ParallelExecutor) çıktıları tek bir birleştirici model "
                    "(Aggregator) tarafından sentezlenerek birden fazla CLI ajanının ortak "
                    "nihai yanıt üretmesi sağlanır."
                ),
                action_command=None,
            )
        )

        return {
            "summary": {
                "installed_cli_count": len(installed_clis),
                "installed_clis": installed_clis,
                "gpu": hw_info.gpu_name,
                "vram_gb": hw_info.gpu_vram_gb,
                "ram_gb": hw_info.ram_gb,
                "findings_count": len(findings),
            },
            "findings": [f.to_dict() for f in findings],
        }
