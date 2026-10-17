"""Faz 5: Teknoloji Gözcüsü (Tech Scout) ve Canlı Açık Kaynak Keşif Motoru.

Bu modül:
1. Sistemin mevcut donanımını (RAM/VRAM), kurulu CLI ajanlarını, Python
   kütüphanelerini ve sağlayıcı yapılandırmasını denetler.
2. İnternet üzerinden **GitHub Search API** (`https://api.github.com/search/repositories`)
   kullanarak yapay zeka orkestrasyonu, LLM yönlendirme (routing), MCP ve otonom
   ajan ekosistemindeki güncel açık kaynak projeleri canlı olarak keşfeder.
3. Eksik bileşenleri ve donanım optimizasyonlarını somut komutlarla raporlar.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import asdict, dataclass
from typing import List

import httpx

from core.cli_registry import discover_cli_tools
from core.hardware import SystemInfo, get_system_info


@dataclass
class ScoutFinding:
    """Tek bir sistem veya teknoloji iyileştirme önerisi."""

    category: str  # "donanım" | "cli_ajan" | "mimari" | "açık_kaynak" | "paket"
    priority: str  # "yüksek" | "orta" | "bilgi"
    title: str
    recommendation: str
    action_command: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class TechScout:
    """Sistemin durumunu analiz edip canlı açık kaynak ve donanım önerileri üretir."""

    @staticmethod
    def check_python_packages() -> list[dict]:
        """Temel ve isteğe bağlı Python paketlerinin kurulum durumunu kontrol eder."""
        packages = [
            ("fastapi", True, "API Sunucusu"),
            ("uvicorn", True, "ASGI Çalışma Zamanı"),
            ("streamlit", True, "Web Kontrol Paneli"),
            ("httpx", True, "Asenkron HTTP İstemcisi"),
            ("pydantic", True, "Veri Doğrulama"),
            ("psutil", False, "Gelişmiş Donanım/Bellek Telemetrisi"),
        ]
        result = []
        for pkg_name, required, role in packages:
            try:
                ver = importlib.metadata.version(pkg_name)
                installed = True
            except importlib.metadata.PackageNotFoundError:
                ver = None
                installed = False
            result.append(
                {
                    "package": pkg_name,
                    "installed": installed,
                    "version": ver,
                    "required": required,
                    "role": role,
                }
            )
        return result

    async def fetch_github_ai_trends(
        self,
        limit: int = 6,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> list[dict]:
        """GitHub genel API'sinden güncel açık kaynak AI orkestrasyon / MCP / LLM projelerini canlı çeker."""
        repos: list[dict] = []
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "NexusAIStudio-TechScout/1.0",
        }
        try:
            async with httpx.AsyncClient(timeout=6.0, transport=transport, headers=headers) as client:
                res = await client.get(
                    "https://api.github.com/search/repositories",
                    params={
                        "q": "topic:mcp OR topic:llm-routing OR topic:ai-agents language:Python",
                        "sort": "stars",
                        "order": "desc",
                        "per_page": str(limit),
                    },
                )
                if res.status_code != 200:
                    return []
                for item in res.json().get("items", [])[:limit]:
                    repos.append(
                        {
                            "full_name": item.get("full_name", ""),
                            "description": item.get("description") or "",
                            "stars": int(item.get("stargazers_count", 0)),
                            "url": item.get("html_url", ""),
                            "topics": (item.get("topics") or [])[:5],
                        }
                    )
        except Exception:
            pass
        return repos

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
        packages = self.check_python_packages()

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
            findings.append(
                ScoutFinding(
                    category="cli_ajan",
                    priority="orta",
                    title=f"{missing.name} CLI kurulu değil",
                    recommendation=(
                        f"{missing.subscription_type} aboneliğinizi Nexus AI Studio üzerinden "
                        f"otomatik tetiklemek için {missing.name} aracını kurabilirsiniz."
                    ),
                    action_command=missing.install_hint,
                )
            )

        # 3) İsteğe bağlı telemetri paketi kontrolü
        psutil_pkg = next((p for p in packages if p["package"] == "psutil"), None)
        if psutil_pkg and not psutil_pkg["installed"]:
            findings.append(
                ScoutFinding(
                    category="paket",
                    priority="bilgi",
                    title="Gelişmiş sistem telemetrisi için 'psutil' kurulabilir",
                    recommendation=(
                        "Anlık CPU yükü ve kullanılabilir RAM takibini hızlandırmak için "
                        "psutil kütüphanesi sanal ortama eklenebilir."
                    ),
                    action_command=".\\.venv\\Scripts\\python.exe -m pip install psutil",
                )
            )

        # 4) Açık kaynak AI Orkestrasyon & Performans çözümleri
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
                title="Çoklu Ajan Sentezi (Mixture-of-Agents / MoA Aktif)",
                recommendation=(
                    "Paralel yürütme (ParallelExecutor) çıktıları artık birleştirici model "
                    "(Aggregator) tarafından sentezlenerek birden fazla CLI ajanının ortak "
                    "nihai yanıt üretmesi sağlanmaktadır."
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
            "packages": packages,
            "findings": [f.to_dict() for f in findings],
        }

    async def full_scout_report(
        self,
        hw_info: SystemInfo | None = None,
        installed_ollama_models: List[str] | None = None,
        include_online: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> dict:
        """Yerel sistem analizini ve (istenirse) canlı GitHub açık kaynak AI trendlerini birleştirir."""
        report = self.analyze_system(hw_info=hw_info, installed_ollama_models=installed_ollama_models)
        if include_online:
            report["github_trends"] = await self.fetch_github_ai_trends(transport=transport)
        else:
            report["github_trends"] = []
        return report
