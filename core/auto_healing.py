"""
4K AI WORKSTATION - Auto-Healing Engine (Kendi Kendini Onaran Motor)
Projeyi çalıştırırken veya test ederken terminalde oluşan hataları (Traceback, import hatası,
port çakışması, sözdizimi hatası) kullanıcıya hissettirmeden yakalar, analiz eder,
otomatik olarak düzeltir (yama uygular) ve sistemi çalışır duruma getirir.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from typing import Dict, List, Any, Optional

from core.router import IntelligentRouter
from core.dispatcher import Dispatcher
from core.workspace_builder import WorkspaceBuilder
from core.software_swarm import dispatch_response


class AutoHealingEngine:
    """
    Terminal çıktılarını dinleyip otomatik hata ayıklayan ve kendi kendini
    onaran (self-healing) otonom motor.
    """

    def __init__(
        self,
        router: Optional[IntelligentRouter] = None,
        dispatcher: Optional[Dispatcher] = None,
        workspace_builder: Optional[WorkspaceBuilder] = None,
        max_attempts: int = 3,
    ):
        self.router = router or IntelligentRouter()
        self.dispatcher = dispatcher or Dispatcher()
        self.workspace_builder = workspace_builder or WorkspaceBuilder()
        self.max_attempts = max_attempts

    def execute_with_healing(
        self,
        command: str,
        workspace_dir: str,
        timeout_seconds: int = 15,
        progress_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Komutu çalıştırır. Hata verirse otomatik onarım döngüsünü başlatır.
        En fazla max_attempts kez düzeltme dener.
        """
        def _notify(stage: str, msg: str):
            if progress_callback:
                try:
                    progress_callback(stage, msg)
                except Exception:
                    pass

        attempts = 0
        healing_history: List[Dict[str, Any]] = []

        while attempts < self.max_attempts:
            attempts += 1
            _notify("running", f"⚡ [Çalıştırma] '{command}' başlatılıyor (Deneme {attempts}/{self.max_attempts})...")

            result = self._run_command(command, workspace_dir, timeout_seconds=timeout_seconds)

            if result["success"]:
                _notify("success", f"✅ [Başarılı] Uygulama hatasız şekilde çalıştı!")
                return {
                    "success": True,
                    "attempts": attempts,
                    "healing_applied": bool(healing_history),
                    "healing_history": healing_history,
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                }

            # Hata çıktı! Onarım gerek
            error_text = result["stderr"] or result["stdout"]
            _notify("error_detected", f"⚠️ [Hata Yakalandı] {self._summarize_error(error_text)}")

            # 1. Eksik kütüphane mi? (ModuleNotFoundError / ImportError)
            missing_pkg = self._detect_missing_package(error_text)
            if missing_pkg:
                _notify("healing", f"📦 [Otomatik Kurulum] Eksik paket tespit edildi: '{missing_pkg}'. Kuruluyor...")
                install_res = self._install_package(missing_pkg, workspace_dir)
                healing_history.append({
                    "attempt": attempts,
                    "action": "package_install",
                    "package": missing_pkg,
                    "success": install_res["success"],
                })
                continue

            # 2. Kod içi hata (SyntaxError, AttributeError, ValueError vb.)
            _notify("healing", "🛠️ [Kod Onarımı] Yapay zeka hatayı analiz ediyor ve otomatik yama hazırlıyor...")
            fix_res = self._repair_code(error_text, workspace_dir)
            healing_history.append({
                "attempt": attempts,
                "action": "code_patch",
                "repaired_files": fix_res.get("repaired_files", []),
                "summary": fix_res.get("summary", ""),
            })

        _notify("failed", "🚨 [Maksimum Deneme Aşıldı] Hata otomatik olarak tamamen giderilemedi.")
        return {
            "success": False,
            "attempts": attempts,
            "healing_applied": bool(healing_history),
            "healing_history": healing_history,
            "last_error": error_text,
        }

    def _run_command(self, command: str, cwd: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        """Belirtilen komutu güvenle çalıştırır ve çıktısını yakalar."""
        try:
            cmd_str = command.strip()
            # Eğer komut python veya python3 ile başlıyorsa mevcut venv python yolunu kullan
            if cmd_str.startswith("python ") or cmd_str.startswith("python3 "):
                cmd_str = f'"{sys.executable}" ' + cmd_str.split(" ", 1)[1]

            proc = subprocess.Popen(
                cmd_str,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=timeout_seconds)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                exit_code = 0

            # Gerçek hata kontrolü
            has_error = (exit_code != 0) or any(
                k in (stderr or "") for k in ["Traceback (most recent call last):", "SyntaxError:", "ModuleNotFoundError:", "OperationalError:"]
            )

            return {
                "success": not has_error,
                "exit_code": exit_code,
                "stdout": stdout or "",
                "stderr": stderr or "",
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _detect_missing_package(self, error_text: str) -> Optional[str]:
        """ModuleNotFoundError veya ImportError içinden paket adını bulur."""
        match = re.search(r"No module named\s+['\"]([^'\"]+)['\"]", error_text)
        if match:
            pkg = match.group(1).split(".")[0]
            # Yaygın paket adı dönüştürmeleri
            mapping = {
                "dotenv": "python-dotenv",
                "yaml": "pyyaml",
                "PIL": "pillow",
                "cv2": "opencv-python",
                "bs4": "beautifulsoup4",
                "jwt": "pyjwt",
                "psycopg2": "psycopg2-binary",
            }
            return mapping.get(pkg, pkg)
        return None

    def _install_package(self, package_name: str, cwd: str) -> Dict[str, Any]:
        """Eksik paketi izole ortama kurar."""
        try:
            cmd = [sys.executable, "-m", "pip", "install", package_name]
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
            return {"success": proc.returncode == 0, "output": proc.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _repair_code(self, error_text: str, workspace_dir: str) -> Dict[str, Any]:
        """Hata mesajını ve mevcut dosyaları inceleyip düzeltilmiş kod yamasını uygular."""
        # Workspace içindeki kaynak kod dosyalarını topla
        source_files = {}
        for root, _, files in os.walk(workspace_dir):
            for file in files:
                if file.endswith((".py", ".js", ".html", ".json", ".sql")):
                    rel_path = os.path.relpath(os.path.join(root, file), workspace_dir)
                    try:
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            source_files[rel_path] = f.read()
                    except Exception:
                        pass

        repair_prompt = (
            "Sen 4K AI WORKSTATION Kendi Kendini Onaran (Self-Healing) Baş Mühendisisin.\n"
            f"ÇALIŞMA DİZİNİNDEKİ HATA METNİ:\n{error_text}\n\n"
            f"MEVCUT DOSYALAR:\n{json.dumps(source_files, ensure_ascii=False)}\n\n"
            "GÖREV:\n"
            "Bu hatayı tamamen çözecek düzeltmeleri yap.\n"
            "Sadece DEĞİŞTİRİLMESİ GEREKEN dosyaları şu formatta ver:\n"
            "### FILE: <dosya_yolu>\n"
            "```<dil>\n"
            "<düzeltilmiş_tam_kod>\n"
            "```\n"
        )

        resp = dispatch_response(self.router, self.dispatcher, repair_prompt)

        extracted = self.workspace_builder.extract_files_from_response(resp)
        repaired_files = self.workspace_builder.apply_files(workspace_dir, extracted)

        return {
            "success": bool(repaired_files),
            "repaired_files": repaired_files,
            "summary": f"{len(repaired_files)} dosya otomatik onarıldı.",
        }

    @staticmethod
    def _summarize_error(error_text: str) -> str:
        """Uzun hata metninden en can alıcı satırı çıkarır."""
        lines = [line.strip() for line in error_text.splitlines() if line.strip()]
        for line in reversed(lines):
            if any(k in line for k in ["Error:", "Exception:", "Traceback", "Failed"]):
                return line
        return lines[-1] if lines else "Bilinmeyen hata"
