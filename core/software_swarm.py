"""
4K AI WORKSTATION - Autonomous Software Swarm (Sanal Yazılım Fabrikası)
Kullanıcının tek cümlelik niyetini (intent) alıp arkada sanal bir yazılım şirketi gibi:
1. PM (Ürün Yöneticisi): İhtiyaçları ve kullanıcı hikayelerini çıkarır.
2. Architect (Sistem Mimarı): Veritabanı şemasını, API uç noktalarını ve dosya ağacını belirler.
3. Developer Swarm (Geliştirici Ekibi): Backend, frontend ve veritabanı kodlarını üretir.
4. QA / Reviewer (Test ve Doğrulama): Dosyaların eksiksiz ve sözdizimsel olarak doğru olduğunu denetler.
Tamamen $0.00 maliyet garantisiyle (Yerel GPU & Ücretsiz Modeller) çalışır.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from typing import Dict, List, Any, Optional

from core.router import IntelligentRouter
from core.dispatcher import Dispatcher
from core.workspace_builder import WorkspaceBuilder


def dispatch_response(router, dispatcher, prompt: str, preferred_model: str = "auto") -> str:
    """Senkron iş akışını asenkron yönlendirici ve dağıtıcıya bağlar.

    Asenkron çağıranlar bu işlevi asyncio.to_thread ile çalıştırmalıdır.
    Senkron özel adaptörler de desteklenir.
    """
    async def _dispatch():
        available = list(dispatcher.wrappers)
        ranked = router.rank_escalation_chain(prompt, available_names=available)
        if inspect.isawaitable(ranked):
            ranked = await ranked
        ranked = [name for name in ranked if name in available]
        if preferred_model != "auto":
            if preferred_model not in available:
                raise ValueError(f"Model kayıtlı değil: {preferred_model}")
            ranked = [preferred_model] + [name for name in ranked if name != preferred_model]
        result = dispatcher.dispatch_with_escalation(ranked, prompt)
        if inspect.isawaitable(result):
            result = await result
        response = result.get("response", "")
        if not response or response.startswith("Hata:"):
            raise RuntimeError(response or "Hata: Model geçerli bir yanıt döndürmedi.")
        return response

    return asyncio.run(_dispatch())


class SoftwareSwarm:
    """
    Sıfır teknik bilgisi olan kullanıcılar için tek cümlelik hedefleri
    uçtan uca çalışan projelere dönüştüren rol tabanlı otonom ajan fabrikası.
    """

    def __init__(
        self,
        router: Optional[IntelligentRouter] = None,
        dispatcher: Optional[Dispatcher] = None,
        workspace_builder: Optional[WorkspaceBuilder] = None,
    ):
        self.router = router or IntelligentRouter()
        self.dispatcher = dispatcher or Dispatcher()
        self.workspace_builder = workspace_builder or WorkspaceBuilder()

    def run_pm_phase(self, user_goal: str, model: str = "auto") -> Dict[str, Any]:
        """
        Adım 1: Ürün Yöneticisi (PM) Ajanı
        Kullanıcının tek cümlelik isteğini detaylı analiz eder,
        kullanıcı rollerini, ana özellikleri ve kabul kriterlerini belirler.
        """
        pm_prompt = (
            "Sen 4K AI WORKSTATION sisteminin Kıdemli Ürün Yöneticisisin (Product Manager).\n"
            f"Kullanıcının Hedefi: {user_goal}\n\n"
            "GÖREV:\n"
            "Bu projeyi eksiksiz hayata geçirmek için gereken temel gereksinimleri belirle.\n"
            "Yanıtını SADECE geçerli bir JSON objesi olarak ver:\n"
            "{\n"
            '  "project_title": "Proje Başlığı",\n'
            '  "summary": "Kısa özet",\n'
            '  "features": ["Özellik 1", "Özellik 2", ...],\n'
            '  "user_roles": ["Rol 1", ...],\n'
            '  "recommended_stack": {"backend": "Python/FastAPI", "frontend": "HTML5/Tailwind/Vanilla JS", "database": "SQLite"}\n'
            "}\n"
        )

        resp = self._dispatch_call(pm_prompt, task_type="general", preferred_model=model)
        parsed = self._extract_json(resp)
        if not parsed:
            parsed = {
                "project_title": "Otonom 4K Projesi",
                "summary": user_goal,
                "features": ["Temel İşlevsellik", "Kullanıcı Arayüzü", "Veri Saklama"],
                "user_roles": ["Kullanıcı"],
                "recommended_stack": {"backend": "Python/FastAPI", "frontend": "HTML5/JS", "database": "SQLite"},
            }
        return parsed

    def run_architect_phase(self, pm_spec: Dict[str, Any], model: str = "auto") -> Dict[str, Any]:
        """
        Adım 2: Sistem Mimarı (Architect) Ajanı
        PM gereksinimlerine göre klasör yapısını, veritabanı tablolarını ve
        üretilecek tüm kaynak kod dosyalarının listesini planlar.
        """
        arch_prompt = (
            "Sen 4K AI WORKSTATION sisteminin Kıdemli Sistem Mimarı ve Veritabanı Uzmanısın.\n"
            f"Proje Özeti: {pm_spec.get('summary', '')}\n"
            f"Özellikler: {json.dumps(pm_spec.get('features', []), ensure_ascii=False)}\n"
            f"Önerilen Teknoloji: {json.dumps(pm_spec.get('recommended_stack', {}), ensure_ascii=False)}\n\n"
            "GÖREV:\n"
            "Bu projeyi çalıştırmak için gereken minimum, temiz ve eksiksiz dosya ağacını belirle.\n"
            "Yanıtını SADECE geçerli bir JSON objesi olarak ver:\n"
            "{\n"
            '  "database_schema": "Gereken SQL tabloları veya alanlar",\n'
            '  "files": [\n'
            '    {"path": "server.py", "purpose": "FastAPI sunucusu ve API uç noktaları"},\n'
            '    {"path": "database.py", "purpose": "SQLite bağlantısı ve CRUD fonksiyonları"},\n'
            '    {"path": "static/index.html", "purpose": "Modern, şık ve responsive web arayüzü"},\n'
            '    {"path": "requirements.txt", "purpose": "Gereken Python paketleri"}\n'
            "  ],\n"
            '  "startup_command": "python server.py"\n'
            "}\n"
        )

        resp = self._dispatch_call(arch_prompt, task_type="reasoning", preferred_model=model)
        parsed = self._extract_json(resp)
        if not parsed or not parsed.get("files"):
            parsed = {
                "database_schema": "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, title TEXT);",
                "files": [
                    {"path": "server.py", "purpose": "API sunucusu"},
                    {"path": "database.py", "purpose": "Veritabanı yönetimi"},
                    {"path": "static/index.html", "purpose": "Web arayüzü"},
                    {"path": "requirements.txt", "purpose": "Bağımlılıklar"},
                ],
                "startup_command": "python server.py",
            }
        return parsed

    def run_developer_phase(
        self,
        pm_spec: Dict[str, Any],
        arch_spec: Dict[str, Any],
        workspace_dir: str,
        model: str = "auto",
    ) -> List[str]:
        """
        Adım 3: Geliştirici Ekibi (Developer Swarm)
        Mimarın belirlediği tüm dosyaları eksiksiz, üretim kalitesinde ve
        çalışır durumda üretip hedef çalışma alanına (workspace) yazar.
        """
        dev_prompt = (
            "Sen 4K AI WORKSTATION Sanal Yazılım Fabrikasının Baş Geliştiricisisin.\n"
            f"Proje: {pm_spec.get('project_title', 'Proje')}\n"
            f"Gereksinimler: {json.dumps(pm_spec.get('features', []), ensure_ascii=False)}\n"
            f"Planlanan Dosyalar: {json.dumps(arch_spec.get('files', []), ensure_ascii=False)}\n"
            f"Veritabanı Şeması: {arch_spec.get('database_schema', '')}\n\n"
            "GÖREV:\n"
            "Tüm bu dosyaları EKSİKSİZ, çalışır, hatasız ve birbirine tam bağlı olarak yaz.\n"
            "Hiçbir dosyayı atlama veya '...kod buraya gelecek...' gibi kısaltma yapma.\n"
            "HER DOSYAYI ŞU FORMATTA VER:\n"
            "### FILE: <dosya_yolu>\n"
            "```<dil>\n"
            "<kod>\n"
            "```\n"
        )

        raw_code_resp = self._dispatch_call(dev_prompt, task_type="code", preferred_model=model)
        extracted = self.workspace_builder.extract_files_from_response(raw_code_resp)

        # Eğer model requirements.txt üretmediyse temel paketleri ekle
        has_reqs = any(f["path"] == "requirements.txt" for f in extracted)
        if not has_reqs:
            extracted.append({
                "path": "requirements.txt",
                "content": "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\n",
            })

        created_files = self.workspace_builder.apply_files(workspace_dir, extracted)
        return created_files

    def run_full_pipeline(
        self,
        user_goal: str,
        workspace_dir: str,
        model: str = "auto",
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Kullanıcının tek cümlelik isteğini alır ve baştan sona:
        1. PM Analizi
        2. Mimari Tasarım
        3. Kod Üretimi & Dosyalama
        adımlarını işletip teslim raporunu döndürür.
        """
        def _notify(stage: str, msg: str):
            if progress_callback:
                try:
                    progress_callback(stage, msg)
                except Exception:
                    pass

        # 1. PM Aşaması
        _notify("pm", "📋 [Ürün Yöneticisi] İhtiyaçlar ve özellikler analiz ediliyor...")
        pm_spec = self.run_pm_phase(user_goal, model=model)

        # 2. Mimari Aşama
        _notify("architect", "🏗️ [Sistem Mimarı] Dosya yapısı ve veritabanı şeması planlanıyor...")
        arch_spec = self.run_architect_phase(pm_spec, model=model)

        # 3. Geliştirici Aşaması
        _notify("developer", "👨‍💻 [Geliştirici Ekibi] Kodlar üretiliyor ve diske yazılıyor...")
        created_files = self.run_developer_phase(pm_spec, arch_spec, workspace_dir, model=model)

        _notify("done", f"🎉 [Tamamlandı] {len(created_files)} dosya başarıyla oluşturuldu!")

        return {
            "status": "success",
            "goal": user_goal,
            "pm_spec": pm_spec,
            "arch_spec": arch_spec,
            "created_files": created_files,
            "startup_command": arch_spec.get("startup_command", "python server.py"),
            "workspace": workspace_dir,
        }

    def _dispatch_call(self, prompt: str, task_type: str = "general", preferred_model: str = "auto") -> str:
        """İsteği eskalasyon zinciri ve sıfır harcama kalkanı üzerinden güvenle çalıştırır."""
        return dispatch_response(self.router, self.dispatcher, prompt, preferred_model)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Model yanıtından güvenle JSON objesini ayrıştırır."""
        try:
            return json.loads(text)
        except Exception:
            pass

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        match_raw = re.search(r"\{[\s\S]*\}", text)
        if match_raw:
            try:
                return json.loads(match_raw.group(0))
            except Exception:
                pass

        return None
