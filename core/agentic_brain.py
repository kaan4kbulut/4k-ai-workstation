"""
4K AI WORKSTATION - Autonomous Agentic Brain (Araç Kullanan Canlı Ajan Aklı)
Modellere sadece metin yazdırmaz; onlara gerçek 'organlar ve aletler' verir:
1. search_web(query): Canlı internete çıkıp arama yapar ve güncel bilgiyi getirir.
2. read_file(path): Bilgisayardaki dosyaları okur.
3. write_file(path, content): Bilgisayarda dosya oluşturur veya günceller.
4. run_terminal(cmd): Bilgisayarda komut çalıştırır.
5. list_directory(path): Klasör içeriğini listeler.
ReAct (Thought -> Action -> Observation -> Final Answer) döngüsüyle çalışır.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Any, Optional
import urllib.parse
import urllib.request

from core.router import IntelligentRouter
from core.dispatcher import Dispatcher


class AgenticTools:
    """Ajanın bilgisayarda ve internette gerçekten eylem yapmasını sağlayan araçlar."""

    @staticmethod
    def search_web(query: str, max_results: int = 5) -> str:
        """İnternette canlı arama yapar (DuckDuckGo HTML / Instant API üzerinden 0 TL)."""
        try:
            encoded_query = urllib.parse.quote_plus(query)
            # DuckDuckGo HTML Lite arama
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8", errors="ignore")

            # Basit temizleme ve snippet çıkarma
            snippets = []
            matches = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            titles = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', html, re.DOTALL)

            for i in range(min(len(matches), max_results)):
                clean_snippet = re.sub(r"<[^>]+>", "", matches[i]).strip()
                clean_url = re.sub(r"<[^>]+>", "", titles[i]).strip() if i < len(titles) else ""
                snippets.append(f"[{i+1}] {clean_snippet} (Kaynak: {clean_url})")

            if snippets:
                return "\n\n".join(snippets)

            # Fallback: Abstract API
            api_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"
            req_api = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_api, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                abstract = data.get("AbstractText", "")
                if abstract:
                    return f"Özet: {abstract}"

            return f"'{query}' için internet araması yapıldı fakat sonuç snippet'ı ayrıştırılamadı."
        except Exception as e:
            return f"İnternet arama hatası: {e}"

    @staticmethod
    def read_file(path: str) -> str:
        """Belirtilen dosyanın içeriğini okur."""
        try:
            clean_path = os.path.abspath(path.strip("\"'"))
            if not os.path.exists(clean_path):
                return f"Hata: Dosya bulunamadı -> {clean_path}"
            with open(clean_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(15000)  # Aşırı büyük dosyaları sınırla
            return content
        except Exception as e:
            return f"Dosya okuma hatası: {e}"

    @staticmethod
    def write_file(path: str, content: str) -> str:
        """Belirtilen dosyayı oluşturur veya üzerine yazar."""
        try:
            clean_path = os.path.abspath(path.strip("\"'"))
            os.makedirs(os.path.dirname(clean_path), exist_ok=True)
            with open(clean_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Başarılı: '{clean_path}' dosyası yazıldı ({len(content)} karakter)."
        except Exception as e:
            return f"Dosya yazma hatası: {e}"

    @staticmethod
    def list_directory(path: str = ".") -> str:
        """Belirtilen klasörün içeriğini listeler."""
        try:
            clean_path = os.path.abspath(path.strip("\"'"))
            if not os.path.exists(clean_path):
                return f"Hata: Klasör bulunamadı -> {clean_path}"
            items = os.listdir(clean_path)
            lines = [f"Klasör: {clean_path}"]
            for it in items[:40]:
                full = os.path.join(clean_path, it)
                is_dir = "[KLASÖR]" if os.path.isdir(full) else "[DOSYA]"
                lines.append(f"  {is_dir:<9} {it}")
            return "\n".join(lines)
        except Exception as e:
            return f"Klasör listeleme hatası: {e}"

    @staticmethod
    def run_terminal(cmd: str, cwd: str = ".") -> str:
        """Terminalde komut çalıştırıp sonucunu döner."""
        try:
            clean_cwd = os.path.abspath(cwd.strip("\"'"))
            proc = subprocess.run(
                cmd,
                cwd=clean_cwd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=30,
            )
            out = proc.stdout.strip()
            err = proc.stderr.strip()
            return out if out else (f"Hata / Çıktı: {err}" if err else "Komut başarıyla çalıştı (Çıktı yok).")
        except Exception as e:
            return f"Komut çalıştırma hatası: {e}"


class AgenticBrain:
    """
    Canlı Araç Çağırma (Tool Calling) ve Karar Verme Motoru.
    Kullanıcının niyetini anlar, gerekirse internette arama yapar,
    dosya okur/yazar, komut çalıştırır ve nihai akıllı yanıtı verir.
    """

    TOOL_DEFINITIONS = """
KULLANABİLECEĞİN CANLI ARAÇLAR (TOOLS):
1. search_web(query="arama terimi") -> Canlı internette arama yapar. Güncel haber, bilgi veya teknoloji aramak için KESİNLİKLE bunu çağır.
2. read_file(path="dosya_yolu") -> Belirtilen dosyayı okur.
3. write_file(path="dosya_yolu", content="kod veya metin") -> Dosya yazar.
4. list_directory(path="klasor_yolu") -> Klasördeki dosyaları listeler.
5. run_terminal(cmd="komut", cwd=".") -> Terminalde komut çalıştırır.

ARAÇ ÇAĞIRMA KURALI:
Eğer bir araca ihtiyacın varsa, yanıtında ŞU BLOK FORMATINI KULLAN:
ACTION: <araç_adı>
ARGS: {"argüman_adı": "değeri"}

Örnek:
ACTION: search_web
ARGS: {"query": "güncel borsa istanbul btc fiyatı"}

Eğer araca ihtiyacın yoksa veya aracı çalıştırdıktan sonra nihai cevabı veriyorsan doğrudan Türkçe konuşarak yanıtla.
"""

    def __init__(self, router: Optional[IntelligentRouter] = None, dispatcher: Optional[Dispatcher] = None):
        self.router = router or IntelligentRouter()
        self.dispatcher = dispatcher or Dispatcher()
        self.tools = AgenticTools()

    async def think_and_act(
        self,
        user_prompt: str,
        workspace_dir: str = ".",
        max_turns: int = 4,
        progress_callback: Optional[Any] = None,
    ) -> str:
        """
        ReAct Döngüsü: Düşün -> Eylem Yap -> Sonucu Gör -> Yanıtla
        """
        def _notify(msg: str):
            if progress_callback:
                try:
                    progress_callback(msg)
                except Exception:
                    pass

        conversation_history = [
            f"KULLANICI: {user_prompt}\n\n{self.TOOL_DEFINITIONS}\nÇalışma Dizini: {os.path.abspath(workspace_dir)}"
        ]

        for turn in range(max_turns):
            current_context = "\n\n".join(conversation_history)
            
            # Modeli çağır
            ranked = self.router.rank_escalation_chain(user_prompt, preferred_model="auto")
            res = self.dispatcher.dispatch_with_escalation(current_context, ranked)
            model_response = res.get("response", "").strip()

            # Model bir ACTION çağırdı mı?
            action_match = re.search(r"ACTION:\s*([a-zA-Z0-9_]+)", model_response)
            args_match = re.search(r"ARGS:\s*(\{.*?\})", model_response, re.DOTALL)

            if not action_match:
                # Model eylem yapmadı, doğrudan nihai cevabı verdi
                return model_response

            tool_name = action_match.group(1).strip()
            raw_args = args_match.group(1).strip() if args_match else "{}"

            try:
                tool_args = json.loads(raw_args)
            except Exception:
                tool_args = {}

            _notify(f"🛠️ [Ajan Eylemi] {tool_name} aracı çalıştırılıyor: {tool_args}...")

            # Aracı gerçekten çalıştır!
            observation = self._execute_tool(tool_name, tool_args, workspace_dir)
            _notify(f"👀 [Gözlem Alındı] Sonuç bağlama eklendi.")

            conversation_history.append(f"AJAN EYLEMİ: {tool_name}({tool_args})")
            conversation_history.append(f"GÖZLEM (SONUÇ):\n{observation}\n\nŞimdi bu sonuca göre nihai Türkçe yanıtını ver veya gerekirse başka bir araç çağır.")

        # Son turda nihai yanıtı al
        final_prompt = "\n\n".join(conversation_history) + "\n\nLütfen tüm bu gözlemlere dayanarak kullanıcıya kapsamlı nihai yanıtını ver."
        ranked = self.router.rank_escalation_chain(user_prompt, preferred_model="auto")
        final_res = self.dispatcher.dispatch_with_escalation(final_prompt, ranked)
        return final_res.get("response", "Yanıt üretilemedi.")

    def _execute_tool(self, tool_name: str, args: Dict[str, Any], workspace: str) -> str:
        """Aracı gerçekten sistemde yürütür."""
        if tool_name == "search_web":
            q = args.get("query", "")
            return self.tools.search_web(q)
        elif tool_name == "read_file":
            p = args.get("path", "")
            return self.tools.read_file(p)
        elif tool_name == "write_file":
            p = args.get("path", "")
            c = args.get("content", "")
            return self.tools.write_file(p, c)
        elif tool_name == "list_directory":
            p = args.get("path", workspace)
            return self.tools.list_directory(p)
        elif tool_name == "run_terminal":
            cmd = args.get("cmd", "")
            cwd = args.get("cwd", workspace)
            return self.tools.run_terminal(cmd, cwd)
        else:
            return f"Bilinmeyen araç: '{tool_name}'."
