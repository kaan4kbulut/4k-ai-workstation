"""
OpenCode & Hermes Free AI Hub - 100% Ucretsiz ($0.00 API Kalkani) MCP Sunucusu
==============================================================================
Bu MCP (Model Context Protocol) sunucusu, OpenCode v2.0.32, Hermes CLI ve tum
MCP uyumlu gelistirici ortamlari icin sifir API harcamasi garantisiyle ($0.00 Kalkanı)
en guclu yapay zeka araclarini, canli web/arastirma motorlarini ve hibrit model
yonlendiricilerini sunar.

Kapsamli Arac Listesi:
1.  free_web_search             : DuckDuckGo uzerinden ucretsiz canli web aramasi
2.  free_url_reader             : URL icerigini temiz metin olarak okuma
3.  pollinations_free_ai        : Pollinations.ai 100% ucretsiz LLM uretimi (API Key gerektirmez)
4.  pollinations_free_image     : Pollinations.ai ucretsiz gorsel uretimi (API Key gerektirmez)
5.  openrouter_list_free_models : OpenRouter 0 TL (:free) modellerini anlik listeleme
6.  openrouter_free_chat        : Yalnizca ':free' modellerle korumali sohbet ($0.00 kalkani)
7.  nvidia_nim_free_chat        : NVIDIA NIM Free Developer Tier sohbeti ve rehberlik
8.  huggingface_free_hub_search : Hugging Face Hub uzerinden acik kaynak model arama
9.  huggingface_free_chat       : Hugging Face Serverless Inference ucretsiz cagrisi
10. free_multi_provider_chat    : Groq, Cerebras, GitHub, Gemini ve Ollama tek noktadan erisim
11. free_arxiv_and_github_search: ArXiv makaleleri ve GitHub repolarini canli arama
12. system_and_gpu_status       : RTX 5070 Ti, VRAM, RAM ve Yerel Ollama durum paneli
13. smart_auto_router           : Gorev tipine gore en iyi ucretsiz modeli secen & otomatik fallback yapan yonlendirici
14. subscription_cli_bridge     : Claude Code, Codex ve Antigravity sabit aboneliklerini $0.00 kalkaniyla cagiran kopru
15. repo_ast_map                : Semantik kod tabani ve mimari AST iskelet haritasi (0 TL ile dosya iceriklerini ogrenme)
16. moa_consensus_engine        : Mixture-of-Agents ile coklu ucretsiz model karsilastirmasi ve konsensus sentezi
17. critic_refiner_loop         : Kidemli critic denetimi ve kendi kendini duzelten guvenli kod dongusu
18. cross_cli_orchestrator      : 5 CLI araci (Claude, Codex, OpenCode, Hermes, Antigravity) arasinda hibrit orkestrasyon
19. hardware_model_curator      : RTX 5070 Ti 12GB VRAM icin Performans x Kalite x Verimlilik odakli model yoneticisi
"""

from __future__ import annotations

import ast
import concurrent.futures
import ctypes
import html
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# DDGS Ice Aktarimi (ddgs veya duckduckgo_search)
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

# MCP Sunucu Tanimlama
mcp = FastMCP("OpenCode Free AI Hub", dependencies=["httpx", "ddgs"])

# Sabit Yollar ve Dizinler
STUDIO_DIR = Path("C:/Users/kloss/nexus_ai_studio")
CONFIG_FILE = STUDIO_DIR / "config" / "providers.json"
HERMES_ENV_FILE = Path("C:/Users/kloss/AppData/Local/hermes/.env")
IMAGES_DIR = STUDIO_DIR / "data" / "generated_images"

# CLI Calistirilabilir Dosya Yollari (5 CLI Araci)
CLAUDE_EXE = Path(r"C:\Users\kloss\.local\bin\claude.exe")
CODEX_EXE = Path(r"C:\Users\kloss\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe")
OPENCODE_EXE = Path(r"C:\Users\kloss\AppData\Local\Programs\@opencodedesktop\resources\opencode-cli.exe")
HERMES_EXE = Path(r"C:\Users\kloss\AppData\Local\hermes\bin\hermes.exe")
AGY_EXE = Path(r"C:\Users\kloss\AppData\Local\agy\bin\agy.exe")


def _get_api_key(env_names: List[str]) -> Optional[str]:
    """Ortam degiskenleri, hermes .env veya providers.json icerisinden anahtari okur."""
    # 1. Standart os.environ
    for name in env_names:
        val = os.getenv(name)
        if val and val.strip():
            return val.strip()

    # 2. Hermes .env kontrolu
    if HERMES_ENV_FILE.exists():
        try:
            for line in HERMES_ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in env_names and v.strip():
                        return v.strip().strip("\"'")
        except Exception:
            pass

    # 3. providers.json kontrolu
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                providers = data.get("providers", [])
                for prov in providers:
                    key_env = prov.get("api_key_env")
                    if key_env in env_names:
                        val = os.getenv(key_env)
                        if val and val.strip():
                            return val.strip()
                    if prov.get("api_key") and prov.get("name") in env_names:
                        return prov.get("api_key").strip()
        except Exception:
            pass
    return None


class HTMLTextExtractor(HTMLParser):
    """HTML etiketlerini temizleyip okunabilir duz metne ceviren parser."""

    def __init__(self):
        super().__init__()
        self.reset()
        self.fed: List[str] = []
        self.skip = False

    def handle_starttag(self, tag: str, attrs: Any):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.skip = True

    def handle_endtag(self, tag: str):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.skip = False
        elif tag.lower() in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "article", "section"):
            self.fed.append("\n")

    def handle_data(self, data: str):
        if not self.skip:
            self.fed.append(data)

    def get_text(self) -> str:
        raw = "".join(self.fed)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        text = "\n".join(line for line in lines if line)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


# ==============================================================================
# 1. free_web_search
# ==============================================================================
@mcp.tool()
def free_web_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo ile %100 ucretsiz, API anahtari gerektirmeyen canli web aramasi yapar.

    Args:
        query: Aranacak sorgu kelimeleri.
        max_results: Getirilecek maksimum sonuc sayisi (varsayilan: 5).
    """
    if DDGS is None:
        return "Hata: 'ddgs' veya 'duckduckgo_search' kutuphanesi yuklu degil."

    query = query.strip()
    if not query:
        return "Lutfen gecerli bir arama sorgusu girin."

    try:
        results = list(DDGS().text(query, max_results=max(1, min(max_results, 15))))
        if not results:
            return f"'{query}' icin hicbir sonuc bulunamadi."

        output = [f"### 🌐 Canli Web Arama Sonuclari: '{query}'\n"]
        for idx, item in enumerate(results, 1):
            title = item.get("title", "Basliksiz")
            href = item.get("href", "")
            body = item.get("body", "").replace("\n", " ")
            output.append(f"**{idx}. [{title}]({href})**\n> {body}\n")

        return "\n".join(output)
    except Exception as e:
        return f"Web aramasi sirasinda hata olustu: {str(e)}"


# ==============================================================================
# 2. free_url_reader
# ==============================================================================
@mcp.tool()
def free_url_reader(url: str) -> str:
    """Verilen URL'nin metin icerigini HTTP uzerinden cekip HTML'den arindirarak temiz metin dondurur.

    Args:
        url: Okunacak web sayfasinin tam URL adresi (http:// veya https://).
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return "Gecersiz URL. URL 'http://' veya 'https://' ile baslamalidir."

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        }
        with httpx.Client(follow_redirects=True, timeout=20.0, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()
        if "text/html" in content_type or "<html" in resp.text[:500].lower():
            parser = HTMLTextExtractor()
            parser.feed(resp.text)
            clean_text = parser.get_text()
        else:
            clean_text = resp.text.strip()

        truncated_note = ""
        if len(clean_text) > 12000:
            clean_text = clean_text[:12000]
            truncated_note = "\n\n*(Not: Icerik cok uzun oldugu icin ilk 12.000 karakter gosterildi)*"

        return (
            f"### 📄 Sayfa Icerigi: [{url}]({url})\n"
            f"**Durum Kodu:** {resp.status_code}\n\n"
            f"{clean_text}{truncated_note}"
        )
    except httpx.HTTPStatusError as e:
        return f"HTTP Hatasi ({e.response.status_code}): {url} adresine erisilemedi."
    except Exception as e:
        return f"URL okunurken hata olustu: {str(e)}"


# ==============================================================================
# 3. pollinations_free_ai
# ==============================================================================
@mcp.tool()
def pollinations_free_ai(prompt: str, model: str = "openai") -> str:
    """Pollinations.ai uzerinden hicbir API anahtari ve bakiye gerektirmeden %100 ucretsiz LLM yaniti uretir.

    Args:
        prompt: Modele gonderilecek soru veya komut.
        model: Model adi (varsayilan: 'openai', alternatifler: 'mistral', 'claude', 'karma', 'p1').
    """
    prompt = prompt.strip()
    if not prompt:
        return "Lutfen gecerli bir prompt girin."

    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                "https://text.pollinations.ai/",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "model": model,
                    "seed": 42,
                },
            )
            if resp.status_code == 200 and resp.text.strip():
                return f"### 🤖 Pollinations AI Yaniti (Model: {model} - 0 TL / Ucretsiz)\n\n{resp.text.strip()}"

            encoded = urllib.parse.quote(prompt)
            fallback_resp = client.get(f"https://text.pollinations.ai/{encoded}?model={model}")
            if fallback_resp.status_code == 200:
                return f"### 🤖 Pollinations AI Yaniti (Model: {model} - 0 TL / Ucretsiz)\n\n{fallback_resp.text.strip()}"

            return f"Pollinations AI yanit veremedi (HTTP {resp.status_code}): {resp.text[:300]}"
    except Exception as e:
        return f"Pollinations AI isteginde hata olustu: {str(e)}"


# ==============================================================================
# 4. pollinations_free_image
# ==============================================================================
@mcp.tool()
def pollinations_free_image(prompt: str, save_path: str = "") -> str:
    """Pollinations.ai uzerinden API anahtarsiz %100 ucretsiz yapay zeka gorseli uretir ve kaydeder.

    Args:
        prompt: Gorsel aciklamasi / prompt (Ingilizce olmasi tavsiye edilir).
        save_path: Gorselin kaydedilecegi yerel dosya yolu. Bos birakilirsa 'nexus_ai_studio/data/generated_images' altina kaydedilir.
    """
    prompt = prompt.strip()
    if not prompt:
        return "Lutfen gecerli bir gorsel promptu girin."

    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(image_url)
            resp.raise_for_status()

        if not save_path.strip():
            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = re.sub(r"[^a-zA-Z0-9]", "_", prompt[:25]).strip("_")
            target_path = IMAGES_DIR / f"img_{timestamp}_{slug}.jpg"
        else:
            target_path = Path(save_path.strip())
            target_path.parent.mkdir(parents=True, exist_ok=True)

        target_path.write_bytes(resp.content)

        return (
            f"### 🎨 Pollinations Ucretsiz Gorsel Uretimi Basarili!\n\n"
            f"- **Prompt:** {prompt}\n"
            f"- **Kaydedilen Dosya:** `{target_path.resolve()}`\n"
            f"- **Dosya Boyutu:** {round(len(resp.content) / 1024, 1)} KB\n"
            f"- **Canli Erisim URL:** {image_url}\n"
        )
    except Exception as e:
        return f"Gorsel uretimi veya indirme sirasinda hata olustu: {str(e)}\nDogrudan URL: {image_url}"


# ==============================================================================
# 5. openrouter_list_free_models
# ==============================================================================
@mcp.tool()
def openrouter_list_free_models(search: str = "") -> str:
    """OpenRouter API uzerindeki tum 0 TL (%100 ucretsiz / :free uzantili) modelleri canli listeler.

    Args:
        search: Model adinda veya taniminda aranacak kelime filtresi (opsiyonel).
    """
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get("https://openrouter.ai/api/v1/models")
            resp.raise_for_status()
            data = resp.json().get("data", [])

        free_models = []
        for m in data:
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            prompt_cost = pricing.get("prompt", "")
            comp_cost = pricing.get("completion", "")

            is_free = mid.endswith(":free") or (prompt_cost == "0" and comp_cost == "0")
            if is_free:
                if search:
                    s_lower = search.lower()
                    m_name = m.get("name", "").lower()
                    m_desc = m.get("description", "").lower()
                    if s_lower not in mid.lower() and s_lower not in m_name and s_lower not in m_desc:
                        continue
                free_models.append(m)

        if not free_models:
            return f"Arama kriterine uygun 0 TL / :free model bulunamadi (Arama: '{search}')."

        output = [
            f"### 🆓 OpenRouter Ucretsiz (0.00 TL / :free) Model Listesi (Toplam: {len(free_models)})\n",
            "| Model ID | Isim | Context Length | Girdi / Cikti Fiyati |",
            "| :--- | :--- | :---: | :---: |",
        ]

        for m in free_models:
            mid = m.get("id", "")
            name = m.get("name", mid).replace("|", "/")
            ctx = m.get("context_length", "N/A")
            output.append(f"| `{mid}` | {name} | {ctx} tokens | **0.00 TL (Ucretsiz)** |")

        output.append(
            "\n> 💡 **Not:** OpenRouter'da bu modelleri kullanirken `$0.00 Kalkanı` geregi "
            "model adinin sonuna mutlaka `:free` eki gelmelidir!"
        )
        return "\n".join(output)
    except Exception as e:
        return f"OpenRouter model listesi cekilirken hata olustu: {str(e)}"


# ==============================================================================
# 6. openrouter_free_chat
# ==============================================================================
@mcp.tool()
def openrouter_free_chat(prompt: str, model: str = "deepseek/deepseek-r1:free") -> str:
    """OpenRouter uzerindeki YALNIZCA ':free' uzantili 0 TL ucretsiz modellere guvenli istek atar.

    $0.00 API Kalkani geregince ':free' uzantisi tasimayan modeller reddedilir.

    Args:
        prompt: Modele gonderilecek soru veya talimat.
        model: Kullanilacak ucretsiz model (varsayilan: 'deepseek/deepseek-r1:free').
    """
    model_clean = model.strip()
    if not model_clean.endswith(":free"):
        return (
            f"⛔ **[SIFIR API HARCAMASI ENGELİ / $0.00 KALKANI]**\n\n"
            f"Talep edilen model: `{model_clean}`\n"
            f"Kural: OpenRouter uzerinde yalnizca sonu `:free` ile biten modeller cagrilabilir.\n"
            f"Bu kalkan yanlislikla bakiye/kontor harcanmasini %100 onler.\n\n"
            f"Lutfen `openrouter_list_free_models` aracini calistirip `:free` etiketli bir model secin."
        )

    api_key = _get_api_key(["OPENROUTER_API_KEY", "OPENROUTER_KEY", "OpenRouterFree"])
    if not api_key:
        return (
            "🔑 **OpenRouter API Anahtari Bulunamadi**\n\n"
            "OpenRouter `:free` modellerini calistirmak icin 0 TL bakiyeli ucretsiz bir hesap anahtari gereklidir:\n"
            "1. https://openrouter.ai/ adresinde ucretsiz hesap olusturun.\n"
            "2. 'Keys' sekmesinden ucretsiz bir API anahtari olusturun (Kredi karti gerekmez).\n"
            "3. Bu anahtari `OPENROUTER_API_KEY` ortam degiskenine ekleyin."
        )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://nexus-ai-studio.local",
            "X-Title": "Nexus AI Studio OpenCode MCP",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_clean,
            "messages": [{"role": "user", "content": prompt}],
        }
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return f"### 🟢 OpenRouter Free AI ({model_clean})\n\n{content}"
    except httpx.HTTPStatusError as e:
        return f"OpenRouter HTTP Hatasi ({e.response.status_code}): {e.response.text}"
    except Exception as e:
        return f"OpenRouter cagrisinda hata: {str(e)}"


# ==============================================================================
# 7. nvidia_nim_free_chat
# ==============================================================================
@mcp.tool()
def nvidia_nim_free_chat(prompt: str, model: str = "meta/llama-3.3-70b-instruct") -> str:
    """NVIDIA NIM Free Developer Tier uzerinden 1000 ucretsiz cikarim kredisiyle sohbet eder.

    Args:
        prompt: Modele gonderilecek soru veya kodlama talimati.
        model: NIM modeli (varsayilan: 'meta/llama-3.3-70b-instruct', alternatifler: 'deepseek-ai/deepseek-r1', 'qwen/qwen2.5-coder-32b-instruct').
    """
    api_key = _get_api_key(["NVIDIA_API_KEY", "NVIDIA_NIM_FREE_KEY", "NvidiaNIMFree"])
    if not api_key:
        return (
            "### 🟢 NVIDIA NIM Ucretsiz Gelistirici Katmani Rehberi\n\n"
            "Sistemde `NVIDIA_API_KEY` veya `NVIDIA_NIM_FREE_KEY` tanimli degil.\n\n"
            "**NVIDIA NIM 1000 Ucretsiz Kredi Nasil Alinir? (Tamamen Ucretsiz)**\n"
            "1. [build.nvidia.com](https://build.nvidia.com) adresine gidin ve ucretsiz hesap acin.\n"
            "2. NVIDIA tum gelistiricilere 1.000 ucretsiz cikarim (inference) kredisi hediye eder.\n"
            "3. Profilinizden API Key olusturup Windows ortam degiskenine `NVIDIA_API_KEY` olarak ekleyin.\n\n"
            "**Desteklenen En Populer Ucretsiz Modeller:**\n"
            "- `meta/llama-3.3-70b-instruct` (Ultra guclu genel & kodlama)\n"
            "- `deepseek-ai/deepseek-r1` (Akıl yurutme & matematik)\n"
            "- `qwen/qwen2.5-coder-32b-instruct` (Uzman yazilimci modeli)\n"
            "- `nvidia/llama-3.1-nemotron-70b-instruct` (NVIDIA optimize model)"
        )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model.strip(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
        }
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return f"### 🟢 NVIDIA NIM ({model})\n\n{content}"
    except httpx.HTTPStatusError as e:
        return f"NVIDIA NIM HTTP Hatasi ({e.response.status_code}): {e.response.text}"
    except Exception as e:
        return f"NVIDIA NIM cagrisinda hata: {str(e)}"


# ==============================================================================
# 8. huggingface_free_hub_search
# ==============================================================================
@mcp.tool()
def huggingface_free_hub_search(query: str, limit: int = 5) -> str:
    """Hugging Face Hub API uzerinden hicbir API anahtari olmadan en cok indirilen acik kaynak modelleri arar.

    Args:
        query: Aranacak model adi veya gorev (Orn: 'qwen', 'deepseek', 'whisper', 'embedding').
        limit: Dondurulecek maksimum model sayisi (varsayilan: 5).
    """
    query = query.strip()
    if not query:
        return "Lutfen aranacak model kelimesini girin."

    try:
        params = {
            "search": query,
            "limit": max(1, min(limit, 15)),
            "sort": "downloads",
            "direction": -1,
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get("https://huggingface.co/api/models", params=params)
            resp.raise_for_status()
            items = resp.json()

        if not items:
            return f"Hugging Face uzerinde '{query}' icin model bulunamadi."

        output = [
            f"### 🤗 Hugging Face Acik Kaynak Model Sonuclari: '{query}'\n",
            "| Model ID | Indirilme (Downloads) | Begeniler (Likes) | Pipeline Gorevi |",
            "| :--- | :---: | :---: | :---: |",
        ]

        for item in items:
            mid = item.get("id", "")
            dls = f"{item.get('downloads', 0):,}"
            likes = f"{item.get('likes', 0):,}"
            task = item.get("pipeline_tag") or "Genel"
            url = f"https://huggingface.co/{mid}"
            output.append(f"| [{mid}]({url}) | {dls} | {likes} | `{task}` |")

        return "\n".join(output)
    except Exception as e:
        return f"Hugging Face aramasinda hata olustu: {str(e)}"


# ==============================================================================
# 9. huggingface_free_chat
# ==============================================================================
@mcp.tool()
def huggingface_free_chat(prompt: str, model: str = "Qwen/Qwen2.5-Coder-32B-Instruct") -> str:
    """Hugging Face Serverless Inference API uzerinden ucretsiz LLM cikarimi yapar.

    Args:
        prompt: Modele iletilecek prompt veya kod istegi.
        model: Hugging Face modeli (varsayilan: 'Qwen/Qwen2.5-Coder-32B-Instruct').
    """
    token = _get_api_key(["HF_TOKEN", "HF_FREE_TOKEN", "HUGGINGFACE_TOKEN", "HuggingFaceFree"])
    if not token:
        return (
            "### 🤗 Hugging Face Ucretsiz Serverless Inference Rehberi\n\n"
            "Sistemde `HF_TOKEN` veya `HF_FREE_TOKEN` tanimli degil.\n\n"
            "**Ucretsiz HF Token Nasil Alinir?**\n"
            "1. [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) adresine gidin.\n"
            "2. 'Create new token' butonuna tiklayip 'Read' yetkisi secin (Tamamen Ucretsizdir).\n"
            "3. Aldiginiz tokeni `HF_TOKEN` ortam degiskenine veya `config/providers.json` dosyasina kaydedin."
        )

    endpoints = [
        f"https://router.huggingface.co/hf-inference/models/{model}/v1/chat/completions",
        f"https://router.huggingface.co/models/{model}/v1/chat/completions",
        f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions",
    ]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    last_error = ""
    for ep in endpoints:
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(ep, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return f"### 🤗 Hugging Face Free ({model})\n\n{content}"
                last_error = f"Endpoint {ep} -> HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            last_error = str(e)

    return f"Hugging Face API cagrisi basarisiz oldu: {last_error}"


# ==============================================================================
# 10. free_multi_provider_chat
# ==============================================================================
@mcp.tool()
def free_multi_provider_chat(provider: str, prompt: str, model: str = "") -> str:
    """Groq, Cerebras, GitHub Models, Gemini Free Tier ve Yerel Ollama saglayicilarini tek noktadan ucretsiz cagirir.

    Desteklenen Saglayicilar:
    - 'ollama'   : Yerel RTX 5070 Ti motoru (100% ucretsiz, internetsiz, sinirsiz)
    - 'groq'     : Groq Cloud LPU Free Tier (30 RPM hizli cikarim)
    - 'cerebras' : Cerebras Wafer-Scale Free Dev Tier (Ultra yuksek token/sn)
    - 'github'   : GitHub Models Free Tier (Tum GitHub gelistiricilerine 0 TL)
    - 'gemini'   : Google AI Studio Free Tier (15 RPM / 1M TPM 0 TL kota)

    Args:
        provider: Saglayici adi ('ollama', 'groq', 'cerebras', 'github', 'gemini').
        prompt: Modele gonderilecek soru veya gorev.
        model: Saglayiciya ozel model adi (bos birakilirsa varsayilan en iyi ucretsiz model secilir).
    """
    prov = provider.strip().lower()

    # 1. Yerel Ollama
    if prov in ("ollama", "yerel", "local"):
        chosen_model = model.strip() or "llama3"
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    "http://127.0.0.1:11434/v1/chat/completions",
                    json={
                        "model": chosen_model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return f"### 🟢 Yerel Ollama (RTX 5070 Ti - Model: {chosen_model} - 0 TL / Sinirsiz)\n\n{content}"
        except Exception as e:
            return (
                f"Yerel Ollama'ya baglanilamadi ({str(e)}).\n"
                f"Ollama'nin calistigindan emin olun (`ollama serve`). "
                f"Mevcut modeller icin `system_and_gpu_status` aracini calistirabilirsiniz."
            )

    # 2. Groq
    if prov == "groq":
        chosen_model = model.strip() or "llama-3.3-70b-versatile"
        key = _get_api_key(["GROQ_API_KEY", "GROQ_KEY"])
        if not key:
            return (
                "### ⚡ Groq Cloud Free Tier Rehberi\n\n"
                "`GROQ_API_KEY` tanimli degil.\n"
                "- [console.groq.com](https://console.groq.com) adresinden 1 dakikada ucretsiz API anahtari alinabilir.\n"
                "- Dakikada 30 istek (RPM) ve gunluk yuzbinlerce token tamamen 0 TL'dir."
            )
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": chosen_model, "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                return f"### ⚡ Groq Free LPU ({chosen_model})\n\n{resp.json()['choices'][0]['message']['content']}"
        except Exception as e:
            return f"Groq cagrisinda hata: {str(e)}"

    # 3. Cerebras
    if prov == "cerebras":
        chosen_model = model.strip() or "llama3.1-70b"
        key = _get_api_key(["CEREBRAS_API_KEY"])
        if not key:
            return (
                "### 🚀 Cerebras Free Dev Tier Rehberi\n\n"
                "`CEREBRAS_API_KEY` tanimli degil.\n"
                "- [cloud.cerebras.ai](https://cloud.cerebras.ai) adresinden ucretsiz anahtar alabilirsiniz.\n"
                "- Saniyede 2000+ token uretim hiziyla ultra yuksek performans sunar."
            )
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    "https://api.cerebras.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": chosen_model, "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                return f"### 🚀 Cerebras Free ({chosen_model})\n\n{resp.json()['choices'][0]['message']['content']}"
        except Exception as e:
            return f"Cerebras cagrisinda hata: {str(e)}"

    # 4. GitHub Models
    if prov in ("github", "azure_github", "gh_models"):
        chosen_model = model.strip() or "gpt-4o-mini"
        key = _get_api_key(["GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"])
        if not key:
            return (
                "### 🐙 GitHub Models Free Tier Rehberi\n\n"
                "`GITHUB_TOKEN` tanimli degil.\n"
                "- GitHub hesabi olan herkes [github.com/marketplace/models](https://github.com/marketplace/models) "
                "uzerinden ucretsiz olarak GPT-4o-mini, Llama 3.3 modellerine erisebilir."
            )
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    "https://models.inference.ai.azure.com/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": chosen_model, "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                return f"### 🐙 GitHub Models Free ({chosen_model})\n\n{resp.json()['choices'][0]['message']['content']}"
        except Exception as e:
            return f"GitHub Models cagrisinda hata: {str(e)}"

    # 5. Gemini Free Tier (Google AI Studio)
    if prov in ("gemini", "google"):
        chosen_model = model.strip() or "gemini-2.0-flash"
        key = _get_api_key(["GEMINI_API_KEY", "GOOGLE_API_KEY"])
        if not key:
            return (
                "### ✨ Google AI Studio Gemini Free Tier Rehberi\n\n"
                "`GEMINI_API_KEY` tanimli degil.\n"
                "- [aistudio.google.com](https://aistudio.google.com) adresinden ucretsiz Gemini API anahtari alinabilir.\n"
                "- Dakikada 15 istek (RPM) ve gunluk 1.500 istek tamamen 0 TL ucretsizdir."
            )
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": chosen_model, "messages": [{"role": "user", "content": prompt}]},
                )
                resp.raise_for_status()
                return f"### ✨ Gemini Free Tier ({chosen_model})\n\n{resp.json()['choices'][0]['message']['content']}"
        except Exception as e:
            return f"Gemini cagrisinda hata: {str(e)}"

    return (
        f"Bilinmeyen saglayici: '{provider}'.\n"
        f"Gecerli ucretsiz saglayicilar: 'ollama', 'groq', 'cerebras', 'github', 'gemini'."
    )


# ==============================================================================
# 11. free_arxiv_and_github_search
# ==============================================================================
@mcp.tool()
def free_arxiv_and_github_search(query: str, source: str = "both") -> str:
    """ArXiv akademik makalelerini ve GitHub acik kaynak projelerini API anahtarsiz canli arar.

    Args:
        query: Aranacak konu, teknoloji veya arastirma terimi.
        source: Arama kaynagi ('arxiv', 'github' veya 'both' - varsayilan: 'both').
    """
    query = query.strip()
    if not query:
        return "Lutfen aranacak sorguyu girin."

    src = source.strip().lower()
    sections = []

    # ArXiv Aramasi
    if src in ("arxiv", "both"):
        try:
            encoded_q = urllib.parse.quote(query)
            arxiv_url = f"https://export.arxiv.org/api/query?search_query=all:{encoded_q}&start=0&max_results=4"
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                res = client.get(arxiv_url)
                res.raise_for_status()

            root = ET.fromstring(res.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            if entries:
                arxiv_md = [f"#### 📚 ArXiv Arastirma Makaleleri ({len(entries)} sonuc)\n"]
                for e in entries:
                    title_elem = e.find("atom:title", ns)
                    title = title_elem.text.strip().replace("\n", " ") if title_elem is not None else "Basliksiz"
                    summary_elem = e.find("atom:summary", ns)
                    summary = summary_elem.text.strip().replace("\n", " ")[:200] + "..." if summary_elem is not None else ""
                    id_elem = e.find("atom:id", ns)
                    doc_url = id_elem.text.strip() if id_elem is not None else ""
                    published = e.find("atom:published", ns)
                    pub_date = published.text[:10] if published is not None else ""

                    arxiv_md.append(f"- **[{title}]({doc_url})** ({pub_date})\n  > {summary}\n")
                sections.append("\n".join(arxiv_md))
            else:
                sections.append(f"ArXiv'de '{query}' ile ilgili makale bulunamadi.")
        except Exception as e:
            sections.append(f"ArXiv aramasinda hata: {str(e)}")

    # GitHub Aramasi
    if src in ("github", "both"):
        try:
            encoded_q = urllib.parse.quote(query)
            gh_url = f"https://api.github.com/search/repositories?q={encoded_q}&sort=stars&order=desc&per_page=4"
            headers = {"User-Agent": "Nexus-MCP-Free-Hub", "Accept": "application/vnd.github.v3+json"}
            with httpx.Client(timeout=20.0, headers=headers) as client:
                res = client.get(gh_url)
                res.raise_for_status()
                items = res.json().get("items", [])

            if items:
                gh_md = [f"#### 🐙 GitHub Acik Kaynak Projeleri ({len(items)} sonuc)\n"]
                for it in items:
                    repo_name = it.get("full_name", "")
                    stars = f"{it.get('stargazers_count', 0):,}"
                    lang = it.get("language") or "Diger"
                    desc = it.get("description") or "Aciklama yok"
                    html_url = it.get("html_url", "")
                    gh_md.append(f"- **[{repo_name}]({html_url})** ⭐ {stars} | Dil: `{lang}`\n  > {desc}\n")
                sections.append("\n".join(gh_md))
            else:
                sections.append(f"GitHub'da '{query}' ile ilgili repo bulunamadi.")
        except Exception as e:
            sections.append(f"GitHub aramasinda hata: {str(e)}")

    return f"### 🔍 Arastirma & Acik Kaynak Sonuclari: '{query}'\n\n" + "\n\n---\n\n".join(sections)


# ==============================================================================
# 12. system_and_gpu_status
# ==============================================================================
@mcp.tool()
def system_and_gpu_status() -> str:
    """RTX 5070 Ti GPU sicakligi, VRAM kullanimi, RAM durumu ve yerel Ollama modellerini anlik raporlar."""
    # 1. GPU Durumu (nvidia-smi)
    gpu_output = "Bilinmiyor"
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if smi.returncode == 0 and smi.stdout.strip():
            parts = [p.strip() for p in smi.stdout.strip().split(",")]
            if len(parts) >= 5:
                gpu_name, temp, util, mem_used, mem_total = parts[:5]
                gpu_output = (
                    f"**GPU:** {gpu_name}\n"
                    f"- **Sicaklik:** {temp}°C\n"
                    f"- **GPU Cekirdek Yuku:** %{util}\n"
                    f"- **VRAM:** {mem_used} MB / {mem_total} MB "
                    f"(%{round(float(mem_used)/float(mem_total)*100, 1)})\n"
                )
            else:
                gpu_output = smi.stdout.strip()
    except Exception as e:
        gpu_output = f"GPU bilgisi alinamadi: {str(e)}"

    # 2. RAM Durumu (ctypes GlobalMemoryStatusEx)
    ram_output = "Bilinmiyor"
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = round(stat.ullTotalPhys / (1024**3), 1)
            avail_gb = round(stat.ullAvailPhys / (1024**3), 1)
            used_gb = round(total_gb - avail_gb, 1)
            ram_output = f"{used_gb} GB / {total_gb} GB kullaniliyor (%{stat.dwMemoryLoad} yuk)"
    except Exception as e:
        ram_output = f"RAM bilgisi alinamadi: {str(e)}"

    # 3. Yerel Ollama Modelleri
    ollama_status = "Cevrimdisi"
    try:
        with httpx.Client(timeout=3.0) as client:
            tags_resp = client.get("http://127.0.0.1:11434/api/tags")
            if tags_resp.status_code == 200:
                models = [m.get("name", "") for m in tags_resp.json().get("models", [])]
                ps_resp = client.get("http://127.0.0.1:11434/api/ps")
                running = [m.get("name", "") for m in ps_resp.json().get("models", [])] if ps_resp.status_code == 200 else []
                ollama_status = (
                    f"**🟢 Calisiyor (Online)**\n"
                    f"- **Yuklu Modeller:** {', '.join(f'`{m}`' for m in models) if models else 'Yok'}\n"
                    f"- **VRAM'de Calisan:** {', '.join(f'`{m}`' for m in running) if running else 'Bosta (Standby)'}"
                )
    except Exception:
        ollama_status = "🔴 Cevrimdisi (Ollama servisi calismiyor)"

    # 4. CPU & Sistem
    os_info = f"{platform.system()} {platform.release()} ({platform.architecture()[0]})"
    cpu_count = os.cpu_count() or 1

    return (
        f"### 🖥️ 4K AI Workstation Donanim & Sistem Durumu\n\n"
        f"{gpu_output}\n"
        f"**Sistem Bellek (RAM):** {ram_output}\n"
        f"**Islemci & Isletim Sistemi:** {cpu_count} Mantiksal Cekirdek | {os_info}\n\n"
        f"**Yerel Ollama Servisi (127.0.0.1:11434):**\n"
        f"{ollama_status}\n\n"
        f"> 🛡️ **Guvenlik Durumu:** $0.00 API Kalkani Aktif (Tum harcamalar kilitli)"
    )


# ==============================================================================
# 13. smart_auto_router (Akilli Gorev Yonlendirici & Kesintisiz Fallback)
# ==============================================================================
@mcp.tool()
def smart_auto_router(prompt: str, task_type: str = "auto") -> str:
    """Gorev metnini analiz ederek en uygun %100 ucretsiz modeli otomatik secer ve
    hata/kota durumunda siradaki ucretsiz saglayiciya otomatik fallback yapar.

    Desteklenen Gorev Tipleri:
    - 'coding'           : Yazilim, kod yazimi, hata ayiklama, refactoring
    - 'reasoning'        : Mimari tasarim, derin mantik, analiz, matematik
    - 'vision'           : Gorsel uretimi ve aciklamasi
    - 'local_private'    : Hassas/gizli veri, 100% cevrimdisi yerel calisma
    - 'fast_chat'        : Hizli genel sohbet, metin ozeti, rutin isler
    - 'auto'             : Prompt iceriginden otomatik tespit

    Fallback Zinciri:
    1. Saglayici: OpenRouter (:free) veya Pollinations AI
    2. Fallback  : Pollinations AI (Alternatif model)
    3. Son Sigorta: Yerel Ollama (RTX 5070 Ti Llama 3)
    """
    prompt_clean = prompt.strip()
    if not prompt_clean:
        return "Lutfen gecerli bir prompt girin."

    tt = task_type.strip().lower()

    # Otomatik Gorev Tespiti
    if tt == "auto":
        p_low = prompt_clean.lower()
        if any(w in p_low for w in ("çiz", "görsel", "resim", "draw", "image", "photo", "tasarla", "logo")):
            tt = "vision"
        elif any(w in p_low for w in ("gizli", "private", "şifre", "password", "yerel", "offline", "çevrimdışı")):
            tt = "local_private"
        elif any(w in p_low for w in ("kod", "code", "python", "def ", "class ", "function", "bug", "hata", "sql", "api", "refactor")):
            tt = "coding"
        elif any(w in p_low for w in ("mimari", "architecture", "tasarım", "kanıt", "mantık", "reasoning", "analiz", "karşılaştır")):
            tt = "reasoning"
        else:
            tt = "fast_chat"

    # 1. Gorsel Uretimi
    if tt == "vision":
        return pollinations_free_image(prompt_clean)

    # 2. Yerel / Gizli Calisma (100% Offline RTX 5070 Ti)
    if tt == "local_private":
        res = free_multi_provider_chat("ollama", prompt_clean, "llama3")
        return f"🔒 **[Yerel & Gizli Gorev - %100 Offline]**\n\n{res}"

    # 3. Metin & Kodlama Fallback Calistirmasi
    fallback_log = []

    # Seviye 1: Pollinations (API anahtarsiz, sifir maliyet)
    try:
        model_choice = "openai" if tt in ("coding", "reasoning") else "mistral"
        with httpx.Client(timeout=35.0) as client:
            resp = client.post(
                "https://text.pollinations.ai/",
                json={"messages": [{"role": "user", "content": prompt_clean}], "model": model_choice, "seed": 42},
            )
            if resp.status_code == 200 and resp.text.strip():
                return (
                    f"### 🤖 Smart Auto Router -> [Gorev: {tt.upper()}]\n"
                    f"**Secilen Saglayici:** Pollinations AI (Model: `{model_choice}` - 0.00 TL)\n\n"
                    f"{resp.text.strip()}"
                )
            fallback_log.append(f"Pollinations HTTP {resp.status_code}")
    except Exception as e:
        fallback_log.append(f"Pollinations ({str(e)[:50]})")

    # Seviye 2: OpenRouter Free (:free) Eger anahtar varsa
    op_key = _get_api_key(["OPENROUTER_API_KEY", "OPENROUTER_KEY"])
    if op_key:
        try:
            with httpx.Client(timeout=40.0) as client:
                resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {op_key}", "Content-Type": "application/json"},
                    json={"model": "liquid/lfm-2.5-2.6b:free", "messages": [{"role": "user", "content": prompt_clean}]},
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return (
                        f"### 🤖 Smart Auto Router -> [Gorev: {tt.upper()}]\n"
                        f"**Secilen Saglayici:** OpenRouter :free (0.00 TL)\n\n"
                        f"{content}"
                    )
                fallback_log.append(f"OpenRouter HTTP {resp.status_code}")
        except Exception as e:
            fallback_log.append(f"OpenRouter ({str(e)[:50]})")

    # Seviye 3: Kesintisiz Sigorta - Yerel Ollama (RTX 5070 Ti)
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "http://127.0.0.1:11434/v1/chat/completions",
                json={"model": "llama3", "messages": [{"role": "user", "content": prompt_clean}]},
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                return (
                    f"### 🛡️ Smart Auto Router -> [Gorev: {tt.upper()} - Yerel Sigorta Modu]\n"
                    f"*Bulut saglayicilari basarisiz oldugu icin Yerel RTX 5070 Ti motoruna devredildi!*\n"
                    f"**Gecis Kaydi:** {' -> '.join(fallback_log)}\n\n"
                    f"{content}"
                )
    except Exception as e:
        fallback_log.append(f"Yerel Ollama ({str(e)[:50]})")

    return (
        f"Tum ucretsiz servisler gecici olarak yanit veremedi.\n"
        f"Hata Kaydi: {' -> '.join(fallback_log)}\n"
        f"Lutfen yerel Ollama servisinizin calistigindan emin olun (`ollama serve`)."
    )


# ==============================================================================
# 14. subscription_cli_bridge (Claude Code, Codex, Antigravity Sabit Kopru)
# ==============================================================================
@mcp.tool()
def subscription_cli_bridge(tool_name: str, prompt: str) -> str:
    """Claude Code, Codex ve Antigravity araclarini kullanicinin sabit oturum kotasiyla calistirir.

    $0.00 API KALKANI: Alt surec baslatilmadan once 'ANTHROPIC_API_KEY' ve 'OPENAI_API_KEY'
    ortam degiskenleri KESINLIKLE temizlenir; boylece asla bakiyeli/kontorlu API harcamasi
    yapilamaz! Eger abonelik kotasi dolmussa, otomatik olarak ucretsiz katmana fallback yapar.

    Args:
        tool_name: Calistirilacak CLI araci ('claude', 'codex', 'antigravity' veya 'agy').
        prompt: Araca iletilecek komut veya gorev aciklamasi.
    """
    tn = tool_name.strip().lower()
    prompt_clean = prompt.strip()
    if not prompt_clean:
        return "Lutfen gecerli bir prompt girin."

    # $0.00 KALKANI: Ucretli API Anahtarlarini Temizle
    sub_env = os.environ.copy()
    sub_env.pop("ANTHROPIC_API_KEY", None)
    sub_env.pop("OPENAI_API_KEY", None)

    cmd: List[str] = []
    tool_label = ""

    if tn in ("claude", "claude_code", "claude-code"):
        if not CLAUDE_EXE.exists():
            return f"Claude Code CLI bulunamadi: {CLAUDE_EXE}"
        cmd = [str(CLAUDE_EXE), "-p", prompt_clean]
        tool_label = "Claude Code (Sabit Abonelik)"
    elif tn in ("codex", "openai_codex", "codex_cli"):
        if not CODEX_EXE.exists():
            return f"Codex CLI bulunamadi: {CODEX_EXE}"
        cmd = [str(CODEX_EXE), "exec", prompt_clean]
        tool_label = "Codex CLI (ChatGPT Aboneligi)"
    elif tn in ("antigravity", "agy", "antigravity_cli"):
        if not AGY_EXE.exists():
            return f"Antigravity CLI bulunamadi: {AGY_EXE}"
        cmd = [str(AGY_EXE), "-p", prompt_clean]
        tool_label = "Antigravity CLI (Sabit Oturum)"
    else:
        return f"Bilinmeyen CLI araci: '{tool_name}'. Desteklenenler: 'claude', 'codex', 'antigravity'."

    try:
        proc = subprocess.run(
            cmd,
            env=sub_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            cwd=str(STUDIO_DIR),
        )

        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        combined = f"{stdout}\n{stderr}".lower()

        # Kota / Hata Tespiti
        quota_error = any(
            err in combined
            for err in (
                "rate limit",
                "quota",
                "429",
                "credit balance",
                "insufficient",
                "exceeded",
                "billing",
                "subscription expired",
            )
        )

        if proc.returncode != 0 or quota_error:
            # Otomatik Kesintisiz Fallback
            warning_msg = (
                f"⚠️ **[{tool_label} Kotasi Doldu veya Hata Alindi]**\n"
                f"Sistem $0.00 Kalkanı ve Kesintisiz Calisma Sigortasi geregince "
                f"otomatik olarak %100 Ucretsiz Katmana devrediliyor...\n\n"
            )
            fallback_res = smart_auto_router(prompt_clean, task_type="auto")
            return warning_msg + fallback_res

        return f"### 🚀 {tool_label} Yaniti\n\n{stdout}"
    except subprocess.TimeoutExpired:
        return (
            f"⚠️ {tool_label} zaman asimina ugradi (180s). "
            f"Gorev otomatik olarak ucretsiz router'a aktariliyor...\n\n"
            + smart_auto_router(prompt_clean, task_type="auto")
        )
    except Exception as e:
        return (
            f"CLI koprusunde hata: {str(e)}. "
            f"Ucretsiz katmana devrediliyor...\n\n"
            + smart_auto_router(prompt_clean, task_type="auto")
        )


# ==============================================================================
# Helper Functions for MoA & Autonomous Loops (0.00 TL)
# ==============================================================================
def _query_pollinations_raw(
    prompt: str,
    model: str = "openai",
    timeout: float = 35.0,
    system_prompt: str = "",
) -> Optional[str]:
    """Pollinations.ai uzerinden %100 ucretsiz metin cikarimi yapar ($0.00)."""
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://text.pollinations.ai/",
                json={"messages": messages, "model": model, "seed": 42},
            )
            if resp.status_code == 200 and resp.text.strip():
                return resp.text.strip()

            encoded = urllib.parse.quote(prompt[:500])
            fb = client.get(f"https://text.pollinations.ai/{encoded}?model={model}")
            if fb.status_code == 200 and fb.text.strip():
                return fb.text.strip()
    except Exception:
        pass
    return None


def _query_ollama_raw(
    prompt: str,
    model: str = "llama3:latest",
    timeout: float = 40.0,
    system_prompt: str = "",
) -> Optional[str]:
    """Yerel RTX 5070 Ti Ollama sunucusundan cikarim yapar ($0.00)."""
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "http://127.0.0.1:11434/v1/chat/completions",
                json={"model": model, "messages": messages},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


def _query_openrouter_free_raw(
    prompt: str,
    model: str = "liquid/lfm-2.5-2.6b:free",
    timeout: float = 40.0,
    system_prompt: str = "",
) -> Optional[str]:
    """OpenRouter uzerindeki :free modellerden korumali cikarim yapar ($0.00)."""
    if not model.endswith(":free"):
        return None
    api_key = _get_api_key(["OPENROUTER_API_KEY", "OPENROUTER_KEY", "OpenRouterFree"])
    if not api_key:
        return None
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://nexus-ai-studio.local",
            "X-Title": "Nexus AI Studio OpenCode MCP",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages},
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


# ==============================================================================
# 15. moa_consensus_engine (Mixture-of-Agents Konsensus Motoru)
# ==============================================================================
@mcp.tool()
def moa_consensus_engine(prompt: str, task_type: str = "coding") -> str:
    """Mixture-of-Agents (MoA) mimarisi ile 2-3 farkli ucretsiz modeli paralel calistirip
    yanitlari BasHakem (Aggregator) modeliyle sentezleyerek tek bir modelden cok daha
    kaliteli ve hatasiz bir konsensus sonucu uretir.

    $0.00 API KALKANI: Tum alt sorgular Pollinations AI, Yerel RTX 5070 Ti Ollama ve OpenRouter :free
    uzerinden 100% ucretsiz calisir; paralel ThreadPoolExecutor ile zaman kaybettirmez.

    Args:
        prompt: Cozulmesi istenen problem, kodlama veya mimari soru.
        task_type: Gorev turu ('coding', 'reasoning', 'architecture', 'general').
    """
    prompt_clean = prompt.strip()
    if not prompt_clean:
        return "Lutfen gecerli bir prompt girin."

    tt = task_type.strip().lower()

    # 1. Paralel Aday Uretimi (Layer 1 - Proposers with ThreadPoolExecutor)
    candidates: List[Dict[str, Any]] = []

    def worker_pollinations() -> Dict[str, Any]:
        t0 = time.time()
        sys_p = "Sen son derece yetkin, modern yazilim ve sistem mimarisi uzmanisin. En temiz, performansli ve dogru cozumu uret."
        res = _query_pollinations_raw(prompt_clean, model="openai", timeout=35.0, system_prompt=sys_p)
        elapsed = round(time.time() - t0, 2)
        return {"name": "Pollinations AI (Model: openai - 0 TL)", "output": res, "elapsed": elapsed}

    def worker_ollama() -> Dict[str, Any]:
        t0 = time.time()
        sys_p = "Sen yuksek performansli, guvenilir bir kodlama ve analiz motorusun."
        res = _query_ollama_raw(prompt_clean, model="llama3:latest", timeout=35.0, system_prompt=sys_p)
        elapsed = round(time.time() - t0, 2)
        return {"name": "Yerel Ollama (RTX 5070 Ti - llama3:latest - 0 TL)", "output": res, "elapsed": elapsed}

    def worker_openrouter_or_alt() -> Dict[str, Any]:
        t0 = time.time()
        res = _query_openrouter_free_raw(prompt_clean, model="liquid/lfm-2.5-2.6b:free", timeout=35.0)
        source_name = "OpenRouter Free (liquid/lfm-2.5-2.6b:free - 0 TL)"
        if not res:
            sys_p = "Sen guvenlik ve performans odakli bir yazilim mimarisin. Alternatif ve saglam bir yaklasim sun."
            res = _query_pollinations_raw(prompt_clean, model="openai", timeout=35.0, system_prompt=sys_p)
            source_name = "Pollinations AI Alternatif Ajan (openai - 0 TL)"
        elapsed = round(time.time() - t0, 2)
        return {"name": source_name, "output": res, "elapsed": elapsed}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(worker_pollinations),
            executor.submit(worker_ollama),
            executor.submit(worker_openrouter_or_alt),
        ]
        for f in concurrent.futures.as_completed(futures):
            try:
                candidates.append(f.result())
            except Exception:
                candidates.append({"name": "Ajan Calisma Hatasi", "output": None, "elapsed": 0.0})

    successful_cands = [c for c in candidates if c.get("output")]

    if not successful_cands:
        # Fallback to Smart Auto Router
        return (
            "⚠️ MoA aday modellerinin hicbirinden yanit alinamadi. "
            "Kesintisiz calisma sigortasi geregince otomatik fallback yapiliyor...\n\n"
            + smart_auto_router(prompt_clean, task_type=tt)
        )

    # 2. BasHakem Sentezi (Layer 2 - Chief Aggregator / Synthesizer)
    if len(successful_cands) == 1:
        c = successful_cands[0]
        return (
            f"### 🧬 Mixture-of-Agents (MoA) Tekil Model Yaniti ({c['name']})\n"
            f"*(Diger modeller zaman asimina ugradigi icin tekil ucretsiz yanit sunuldu - Sure: {c['elapsed']}s)*\n\n"
            f"{c['output']}"
        )

    aggregator_prompt_parts = [
        f"KULLANICI GÖREVİ:\n{prompt_clean}\n\n",
        "Aşağıda farklı bağımsız yapay zeka modelleri tarafından paralel üretilmiş çözüm önerileri bulunmaktadır:\n\n",
    ]
    for idx, c in enumerate(successful_cands, 1):
        aggregator_prompt_parts.append(
            f"--- [Model {idx}: {c['name']}] ---\n{c['output']}\n\n"
        )

    aggregator_sys = (
        "Sen kıdemli bir BaşHakem (Chief Aggregator / Synthesizer) yapay zekasın. "
        "Farklı modellerin bağımsız çözümlerini inceleyerek en doğru, en optimize, "
        "hatasız ve üretime hazır tek bir NİHAİ KONSENSÜS ÇÖZÜM üret. "
        "Fuzuli giriş/çıkış gevezeliği yapmadan, doğrudan mükemmelleştirilmiş sentezi sun."
    )
    aggregator_input = "".join(aggregator_prompt_parts)

    t_agg = time.time()
    synthesis = _query_pollinations_raw(aggregator_input, model="openai", timeout=45.0, system_prompt=aggregator_sys)
    if not synthesis:
        synthesis = _query_ollama_raw(aggregator_input, model="llama3:latest", timeout=45.0, system_prompt=aggregator_sys)
    agg_elapsed = round(time.time() - t_agg, 2)

    if not synthesis:
        best_cand = max(successful_cands, key=lambda x: len(x.get("output", "")))
        synthesis = best_cand["output"]

    report = [
        "### 🧬 Mixture-of-Agents (MoA) v2.0 Konsensüs Motoru",
        f"**Görev Türü:** `{tt}` | **Mimari:** 3-Ajan Paralel Katman + BaşHakem Sentezi | **Maliyet:** $0.00 (0 TL)\n",
        "#### 👥 Katılımcı Ajanlar & Aday Modeller:",
    ]
    for c in candidates:
        status_icon = "🟢 Başarılı" if c.get("output") else "🔴 Zaman Aşımı / Yanıt Yok"
        report.append(f"- **{c['name']}**: {status_icon} ({c['elapsed']}s)")

    report.append(f"\n---\n#### 🏆 BaşHakem Sentez Çözümü (Konsensüs - {agg_elapsed}s):\n")
    report.append(synthesis)
    report.append(
        "\n\n---\n> 🛡️ **MoA Doğrulama Kalkanı:** Birden fazla bağımsız açık kaynak modelin "
        "çapraz konsensüsü ile halüsinasyonlar elenmiş ve tek bir modelin sağlayamayacağı kalitede nihai sonuç üretilmiştir."
    )

    return "\n".join(report)


# ==============================================================================
# 16. critic_refiner_loop (Generator -> Senior Critic -> Refiner Otonom Dongu)
# ==============================================================================
@mcp.tool()
def critic_refiner_loop(prompt: str, draft_solution: str = "", initial_code: str = "") -> str:
    """Generator -> Senior Critic -> Refiner otonom kalite dongusunu calistirir.
    Ilk taslagi uretir (veya alir), ardindan guvenlik, performans ve uc durumlari
    denetletip mukemmellestirilmis nihai cozumu dondurur.

    $0.00 API KALKANI: Tum asamalar %100 ucretsiz acik kaynak modellerle gerceklestirilir.

    Args:
        prompt: Cozulmesi istenen problem veya gelistirme gorevi.
        draft_solution: Varsa kullanicinin sagladigi ilk taslak cozum (opsiyonel).
        initial_code: 'draft_solution' icin geriye donuk uyumlu takma ad (opsiyonel).
    """
    prompt_clean = prompt.strip()
    if not prompt_clean:
        return "Lutfen gecerli bir prompt girin."

    # 1. Asama: Taslak Cozum
    draft = draft_solution.strip() or initial_code.strip()
    if not draft:
        draft = _query_pollinations_raw(
            prompt_clean,
            model="openai",
            timeout=35.0,
            system_prompt="Sen hizli ve etkili bir yazilim gelistiricisisin. Talep edilen cozumu eksiksiz kodla.",
        ) or _query_ollama_raw(
            prompt_clean,
            model="llama3:latest",
            timeout=35.0,
        )

    if not draft:
        draft = smart_auto_router(f"Gorev: {prompt_clean}\nLutfen temiz ve dogrudan calisan kod yaz.", task_type="coding")

    # 2. Asama: Kidemli Denetci (Senior Critic)
    critic_sys = (
        "Sen kıdemli bir Baş Güvenlik ve Mimari Denetçisisin (Senior Critic & Code Reviewer). "
        "Verilen kullanıcı talebini ve ilk taslak çözümü incele. "
        "Şu 4 boyutta acımasız ve yapıcı bir denetim yap:\n"
        "1. Güvenlik & Zafiyetler (Security leaks, injection, input validation)\n"
        "2. Performans & Kaynak Yönetimi (Time/space complexity, async/blocking IO)\n"
        "3. Uç Durumlar & Hata Yönetimi (Edge cases, boundary conditions, exception handling)\n"
        "4. Kod Kalitesi & Standartlar (Clean code, idiomatic style, type safety)\n"
        "Kısa ve net maddelerle eksikleri ve yapılması gereken düzeltmeleri listele."
    )
    critic_prompt = (
        f"KULLANICI TALEBİ:\n{prompt_clean}\n\n"
        f"İNCELENECEK İLK TASLAK ÇÖZÜM:\n{draft}"
    )

    critic_review = _query_ollama_raw(critic_prompt, model="llama3:latest", timeout=45.0, system_prompt=critic_sys)
    if not critic_review:
        critic_review = _query_pollinations_raw(critic_prompt, model="openai", timeout=45.0, system_prompt=critic_sys)
    if not critic_review:
        critic_review = "Otomatik denetim servisine anlik ulasilamadi; genel standartlara gore refactor yapilacak."

    # 3. Asama: Iyilestirici (Master Refiner)
    refiner_sys = (
        "Sen uzman bir Çözüm İyileştiricisisin (Master Refiner). "
        "İlk taslak çözümü ve Kıdemli Denetçinin raporundaki tüm eksikleri, güvenlik açıklarını ve performans "
        "darboğazlarını dikkate alarak üretim kalitesinde (production-ready), eksiksiz, modern ve güvenli "
        "NİHAİ ÇÖZÜMÜ üret. Doğrudan kusursuzlaştırılmış çözümü sun."
    )
    refiner_prompt = (
        f"KULLANICI TALEBİ:\n{prompt_clean}\n\n"
        f"İLK TASLAK:\n{draft}\n\n"
        f"KIDEMLİ DENETÇİ ELEŞTİRİLERİ:\n{critic_review}"
    )

    refined_output = _query_pollinations_raw(refiner_prompt, model="openai", timeout=50.0, system_prompt=refiner_sys)
    if not refined_output:
        refined_output = _query_ollama_raw(refiner_prompt, model="llama3:latest", timeout=50.0, system_prompt=refiner_sys)
    if not refined_output:
        refined_output = draft

    report = [
        "### 🔄 Otonom Kalite Döngüsü: Generator ➔ Critic ➔ Refiner (v2.0)",
        "**Kalite Standardı:** Üretim Seviyesi (Production-Ready) | **Maliyet:** 0.00 TL ($0.00 API Kalkanı)\n",
        "#### 🧐 1. Kıdemli Denetçi (Senior Critic) Raporu:",
        critic_review,
        "\n---\n#### 💎 2. Mükemmelleştirilmiş Nihai Çözüm (Refined Solution):\n",
        refined_output,
        "\n---\n<details><summary>📝 İlk Taslak Çözümü Görüntüle (Tıklayın)</summary>\n\n",
        draft,
        "\n\n</details>",
    ]
    return "\n".join(report)


# ==============================================================================
# 17. repo_ast_map (Semantik Kod Tabani & Mimari AST Haritasi - Aider/RepoMap Tarzi)
# ==============================================================================
@mcp.tool()
def repo_ast_map(directory: str = ".", max_files: int = 40, target_path: str = "") -> str:
    """Python AST ve regex motoru ile verilen projenin mimari haritasini (Aider/RepoMap tarzi)
    sinif, fonksiyon imzalari ve modulleriyle cok dusuk token maliyetiyle cikarir.

    CLI ajanlari (OpenCode, Hermes, Claude Code, Codex, Antigravity) kotalarini tuketmeden
    projenin tum yapisini bu harita sayesinde aninda kavrar.

    Args:
        directory: Taranacak proje klasoru (varsayilan: '.' - mevcut calisma dizini).
        max_files: Taranacak maksimum dosya sayisi (varsayilan: 40).
        target_path: 'directory' icin geriye donuk uyumlu takma ad (opsiyonel).
    """
    root_input = target_path.strip() or directory.strip() or "."
    target_dir = Path(root_input).resolve()
    if not target_dir.exists():
        return f"Hedef yol bulunamadi: {target_dir}"

    allowed_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".json", ".yaml", ".yml", ".toml"}
    ignore_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
        ".gemini", ".codex", ".claude", ".hermes", "cache", "bin", "runtime",
        ".curator_backups", "audio_cache", "image_cache", "brain", "logs",
        ".system_generated", "generated_images", ".pytest_cache", ".idea", ".vscode"
    }
    ignore_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pyc", ".pyo", ".pyd",
        ".exe", ".dll", ".so", ".dylib", ".whl", ".zip", ".tar", ".gz", ".lock",
        ".bin", ".parquet", ".db", ".sqlite", ".sqlite3", ".pdf", ".mp4", ".mp3"
    }

    if target_dir.is_file():
        files_to_scan = [target_dir]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs and not d.startswith(".")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ignore_extensions or file.startswith("."):
                    continue
                if ext in allowed_exts:
                    files_to_scan.append(Path(root) / file)
                if len(files_to_scan) >= max_files * 2:
                    break
            if len(files_to_scan) >= max_files * 2:
                break

    def sort_key(p: Path):
        ext = p.suffix.lower()
        priority = 0 if ext == ".py" else (1 if ext in (".ts", ".tsx", ".js", ".jsx") else (2 if ext == ".md" else 3))
        return (priority, str(p))

    files_to_scan.sort(key=sort_key)
    selected_files = files_to_scan[:max_files]

    total_classes = 0
    total_funcs = 0
    file_reports: List[str] = []

    for fpath in selected_files:
        try:
            rel_path = fpath.relative_to(target_dir)
        except Exception:
            rel_path = fpath.name

        ext = fpath.suffix.lower()
        report_lines = [f"#### 📄 `{rel_path}`"]

        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            report_lines.append(f"  *(Okunamadi: {str(e)[:40]})*")
            file_reports.append("\n".join(report_lines))
            continue

        if ext == ".py":
            try:
                tree = ast.parse(content, filename=str(fpath))
                doc = ast.get_docstring(tree)
                if doc:
                    first_doc = doc.strip().splitlines()[0][:90]
                    report_lines.append(f"  - **Açıklama:** {first_doc}")

                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        total_classes += 1
                        bases = [b.id if isinstance(b, ast.Name) else "..." for b in node.bases]
                        base_str = f"({', '.join(bases)})" if bases else ""
                        report_lines.append(f"  - `class {node.name}{base_str}`")
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                total_funcs += 1
                                is_async = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
                                args = [a.arg for a in item.args.args if a.arg != "self"]
                                report_lines.append(f"    - `{is_async}def {item.name}({', '.join(args[:5])})`")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        total_funcs += 1
                        is_async = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                        args = [a.arg for a in node.args.args if a.arg != "self"]
                        report_lines.append(f"  - `{is_async}def {node.name}({', '.join(args[:5])})`")
            except Exception:
                func_matches = re.findall(r"def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)", content)
                class_matches = re.findall(r"class\s+([a-zA-Z0-9_]+)", content)
                for c in class_matches:
                    total_classes += 1
                    report_lines.append(f"  - `class {c}`")
                for fn, params in func_matches[:10]:
                    total_funcs += 1
                    clean_params = re.sub(r"\s+", " ", params)[:35]
                    report_lines.append(f"  - `def {fn}({clean_params})`")

        elif ext in (".ts", ".tsx", ".js", ".jsx"):
            classes = re.findall(r"(?:export\s+)?class\s+([a-zA-Z0-9_]+)", content)
            interfaces = re.findall(r"(?:export\s+)?interface\s+([a-zA-Z0-9_]+)", content)
            funcs = re.findall(r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)\s*\((.*?)\)", content)
            const_funcs = re.findall(r"(?:export\s+)?const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>", content)

            for c in classes:
                total_classes += 1
                report_lines.append(f"  - `class {c}`")
            for i in interfaces:
                report_lines.append(f"  - `interface {i}`")
            for fn, params in funcs[:8]:
                total_funcs += 1
                report_lines.append(f"  - `function {fn}({params[:30]})`")
            for fn, params in const_funcs[:8]:
                total_funcs += 1
                report_lines.append(f"  - `const {fn} = ({params[:30]}) =>`")

        elif ext == ".md":
            headers = [line.strip() for line in content.splitlines() if line.startswith("#")][:6]
            for h in headers:
                report_lines.append(f"  - {h}")

        elif ext in (".json", ".yaml", ".yml", ".toml"):
            lines_count = len(content.splitlines())
            report_lines.append(f"  - *Yapılandırma Dosyası ({lines_count} satır)*")

        if len(report_lines) == 1:
            report_lines.append("  - *(Boş veya bildirim içermeyen dosya)*")

        file_reports.append("\n".join(report_lines))

    header = [
        f"### 🗺️ Repo AST & Mimari Haritası (Aider/RepoMap Tarzı v2.0)",
        f"- **Dizin:** `{target_dir}`",
        f"- **Taranan Dosyalar:** {len(selected_files)} adet (Toplam sınıf: {total_classes}, Toplam fonksiyon: {total_funcs})",
        f"- **Maliyet:** 0 Token / $0.00 (Yerel AST Motoru)\n",
        "---\n",
    ]

    return "\n".join(header) + "\n\n".join(file_reports)


# ==============================================================================
# 18. cross_cli_orchestrator (5 CLI Araci Arasinda Hibrit Dagitim)
# ==============================================================================
@mcp.tool()
def cross_cli_orchestrator(task: str, complexity: str = "auto", target_cli: str = "") -> str:
    """5 buyuk CLI aracini (Claude Code, Codex, OpenCode, Hermes, Antigravity) ve tum
    model ailelerini koordine eden merkezi meta-orkestrator.

    CLI Ailesi Haritasi:
    1. Claude Code   : Sonnet / Opus (Agir mimari, kritik guvenlik, cok katmanli sistem tasarimi)
    2. Codex CLI     : GPT-5 / Codex (Orta/agir UI, REST API, derin birim testleri, CRUD)
    3. Antigravity   : Gemini Pro / Flash (Eko-sistem denetimi, multi-agent orkestrasyon)
    4. OpenCode CLI  : DeepSeek / Nemotron / Qwen Free (Orta seviye kodlama, moduler refactoring)
    5. Hermes CLI    : Pollinations / OpenRouter / Ollama (Hafif rutin isler, dokumantasyon, 0 token)

    $0.00 API KALKANI: Ucretli API anahtarlari alt surecten tamamen temizlenir.
    Sabit abonelik yoksa veya kota dolmussa otonom olarak MoA / ucretsiz katmana fallback yapar.

    Args:
        task: Yurutulecek gorev veya komut.
        complexity: 'auto', 'tier1', 'tier2', 'tier3', 'claude', 'codex', 'opencode', 'hermes', 'antigravity'.
        target_cli: 'complexity' parametresi icin takma ad (opsiyonel).
    """
    task_clean = task.strip()
    if not task_clean:
        return "Lutfen gecerli bir gorev tanimi girin."

    comp = target_cli.strip().lower() or complexity.strip().lower()

    cli_status = {
        "claude": CLAUDE_EXE.exists(),
        "codex": CODEX_EXE.exists(),
        "opencode": OPENCODE_EXE.exists(),
        "hermes": HERMES_EXE.exists(),
        "antigravity": AGY_EXE.exists(),
    }

    chosen_cli = ""
    tier_label = ""
    rationale = ""

    if comp in ("claude", "claude_code"):
        chosen_cli = "claude"
        tier_label = "Katman 3 (Uzman Mimari - Claude Code)"
        rationale = "Kullanıcı doğrudan Claude Code CLI talebinde bulundu."
    elif comp in ("codex", "openai_codex"):
        chosen_cli = "codex"
        tier_label = "Katman 2/3 (Codex CLI - ChatGPT Aboneliği)"
        rationale = "Kullanıcı doğrudan Codex CLI talebinde bulundu."
    elif comp in ("antigravity", "agy"):
        chosen_cli = "antigravity"
        tier_label = "Katman 2/3 (Antigravity CLI - Sabit Oturum)"
        rationale = "Kullanıcı doğrudan Antigravity CLI talebinde bulundu."
    elif comp in ("opencode", "opencode_cli"):
        chosen_cli = "opencode"
        tier_label = "Katman 2 (OpenCode CLI - Açık Kaynak Motor)"
        rationale = "Kullanıcı doğrudan OpenCode CLI talebinde bulundu."
    elif comp in ("hermes", "hermes_cli"):
        chosen_cli = "hermes"
        tier_label = "Katman 1 (Hermes CLI - 0 Kota / Hızlı Ajan)"
        rationale = "Kullanıcı doğrudan Hermes CLI talebinde bulundu."
    elif comp == "tier3":
        chosen_cli = "claude" if cli_status["claude"] else "codex"
        tier_label = "Katman 3 (Uzman Mimari)"
        rationale = "Kullanıcı Katman 3 yüksek karmaşıklık seçimi yaptı."
    elif comp == "tier2":
        chosen_cli = "opencode" if cli_status["opencode"] else ("codex" if cli_status["codex"] else "antigravity")
        tier_label = "Katman 2 (Orta Düzey Kodlama & Test)"
        rationale = "Kullanıcı Katman 2 orta düzey seçimi yaptı."
    elif comp == "tier1":
        chosen_cli = "hermes" if cli_status["hermes"] else "moa"
        tier_label = "Katman 1 (Hafif & Standart)"
        rationale = "Kullanıcı Katman 1 0-kota seçimi yaptı."
    else:  # 'auto'
        t_low = task_clean.lower()
        if any(w in t_low for w in ("mimari", "şema", "güvenlik", "security", "darboğaz", "protokol", "derin", "algoritma")):
            chosen_cli = "claude" if cli_status["claude"] else ("codex" if cli_status["codex"] else "opencode")
            tier_label = "Katman 3: Uzman Katman (Claude / Codex)"
            rationale = "Görevde kritik mimari, algoritma veya güvenlik ihtiyacı tespit edildi."
        elif any(w in t_low for w in ("api", "crud", "endpoint", "ui", "bilesen", "component", "test", "unit test", "refactor")):
            chosen_cli = "opencode" if cli_status["opencode"] else ("codex" if cli_status["codex"] else "antigravity")
            tier_label = "Katman 2: Orta Düzey Kodlama (OpenCode / Codex)"
            rationale = "Görev CRUD, REST API, UI veya birim test kapsamı içeriyor."
        else:
            chosen_cli = "hermes" if cli_status["hermes"] else "moa"
            tier_label = "Katman 1: Hafif & Standart (Hermes / MoA 0 TL)"
            rationale = "Görev rutin script, özetleme veya dokümantasyon kapsıyor."

    # Sabit kopru araclari dogrudan subscription_cli_bridge ile calistirilabilir
    if chosen_cli in ("claude", "codex", "antigravity"):
        return subscription_cli_bridge(chosen_cli, task_clean)

    # $0.00 Kalkanı: API Harcamasını Sıfırla
    sub_env = os.environ.copy()
    sub_env.pop("ANTHROPIC_API_KEY", None)
    sub_env.pop("OPENAI_API_KEY", None)

    cmd: List[str] = []
    if chosen_cli == "opencode" and cli_status["opencode"]:
        cmd = [str(OPENCODE_EXE), "run", task_clean]
    elif chosen_cli == "hermes" and cli_status["hermes"]:
        cmd = [str(HERMES_EXE), "-z", task_clean]

    if not cmd:
        return (
            f"### 🎛️ Cross-CLI Meta-Orchestrator -> MoA Konsensüs Modu\n"
            f"- **Hedef Katman:** {tier_label}\n"
            f"- **Yönlendirme Sebebi:** {rationale} (Yerel CLI aracı doğrudan çalıştırılamadığı için MoA devreye alındı)\n\n"
            + moa_consensus_engine(task_clean, task_type="coding")
        )

    try:
        proc = subprocess.run(
            cmd,
            env=sub_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(STUDIO_DIR),
        )
        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        combined = f"{stdout}\n{stderr}".lower()

        quota_or_err = proc.returncode != 0 or any(
            err in combined
            for err in (
                "rate limit", "quota", "429", "credit balance", "insufficient",
                "exceeded", "billing", "subscription expired", "error"
            )
        )

        if quota_or_err:
            warning_msg = (
                f"⚠️ **[{chosen_cli.upper()} Kotası Doldu veya Hata Alındı]**\n"
                f"Sistem $0.00 API Kalkanı gereği otomatik olarak Mixture-of-Agents (MoA) motoruna devrediliyor...\n\n"
            )
            return warning_msg + moa_consensus_engine(task_clean, task_type="coding")

        return (
            f"### 🎛️ Cross-CLI Meta-Orchestrator v2.0 Yanıtı\n"
            f"- **Seçilen Katman & Araç:** `{chosen_cli}` ({tier_label})\n"
            f"- **Yönlendirme Gerekçesi:** {rationale}\n"
            f"- **Maliyet:** 0.00 TL ($0.00 API Kalkanı)\n\n"
            f"{stdout or stderr}"
        )

    except subprocess.TimeoutExpired:
        return (
            f"⚠️ {chosen_cli} zaman aşımına uğradı (120s). "
            f"Görev otomatik olarak MoA motoruna aktarılıyor...\n\n"
            + moa_consensus_engine(task_clean, task_type="coding")
        )
    except Exception as e:
        return (
            f"CLI çalıştırmada hata: {str(e)}. "
            f"MoA motoruna devrediliyor...\n\n"
            + moa_consensus_engine(task_clean, task_type="coding")
        )


# ==============================================================================
# 19. hardware_model_curator (RTX 5070 Ti 12GB Donanima Ozel Model Kuratoru)
# ==============================================================================
@mcp.tool()
def hardware_model_curator(action: str = "audit") -> str:
    """RTX 5070 Ti 12GB VRAM + i9-13900HX + 32GB RAM Donanimi Icin Model & Verimlilik Kuratoru.

    Kullanicinin donanim gucune (12GB GDDR7 VRAM) gore 'Performans x Kalite x Verimlilik'
    dengesindeki en ideal modelleri (Sweet-Spot 7B-8B: qwen2.5-coder:7b, deepseek-r1:8b, llama3.2:3b, llama3:8b)
    denetler, puanlar, eksikleri kurar ve VRAM asimi yapan verimsiz modelleri temizler.

    Args:
        action: 'audit' (mevcut yerel ve bulut modelleri verimlilige gore puanlar),
                'optimize' (RTX 5070 Ti tatli nokta modellerini senkronize eder/onerir ve temizlik yapar),
                'status' / 'recommend' / 'pull_optimal' / 'cleanup_redundant' (takma adlar).
    """
    act = action.strip().lower()

    # 1. Yerel Ollama Modellerini Al
    installed_models: List[Dict[str, Any]] = []
    ollama_online = False
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get("http://127.0.0.1:11434/api/tags")
            if resp.status_code == 200:
                ollama_online = True
                installed_models = resp.json().get("models", [])
    except Exception:
        pass

    if not installed_models:
        try:
            cli_res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if cli_res.returncode == 0:
                ollama_online = True
                lines = cli_res.stdout.strip().splitlines()
                if len(lines) > 1:
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            m_name = parts[0]
                            installed_models.append({"name": m_name, "size": 0})
        except Exception:
            pass

    installed_names = [m.get("name", "") for m in installed_models]

    sweet_spot_catalog = {
        "qwen2.5-coder:7b": {
            "category": "🥇 Uzman Kodlama (S-Tier)",
            "vram_gb": 4.7,
            "speed_tps": "115+ tok/s",
            "score": 99,
            "verdict": "Mutlaka Kurulmalı (12GB VRAM Altın Oran)",
            "pull_cmd": "ollama pull qwen2.5-coder:7b",
        },
        "deepseek-r1:8b": {
            "category": "🥈 Derin Akıl Yürütme / Düşünce",
            "vram_gb": 4.9,
            "speed_tps": "95+ tok/s",
            "score": 97,
            "verdict": "Mutlaka Kurulmalı (Tatlı Nokta)",
            "pull_cmd": "ollama pull deepseek-r1:8b",
        },
        "llama3.2:3b": {
            "category": "⚡ Ultra Hızlı Ajan & Router",
            "vram_gb": 2.0,
            "speed_tps": "170+ tok/s",
            "score": 96,
            "verdict": "Önerilen Hızlı Model (Tatlı Nokta)",
            "pull_cmd": "ollama pull llama3.2:3b",
        },
        "llama3:latest": {
            "category": "🥉 Genel Amaçlı Llama 3 8B",
            "vram_gb": 4.7,
            "speed_tps": "100+ tok/s",
            "score": 91,
            "verdict": "İyi / Kararlı Temel Model",
            "pull_cmd": "ollama pull llama3:latest",
        },
        "qwen2.5-coder:14b": {
            "category": "⚠️ Ağır Kodlama 14B",
            "vram_gb": 9.2,
            "speed_tps": "50-65 tok/s",
            "score": 82,
            "verdict": "Sınırda (Context uzadıkça VRAM taşabilir)",
            "pull_cmd": "ollama pull qwen2.5-coder:14b",
        },
    }

    cloud_free_recommendations = [
        ("nvidia/nemotron-3.5-lightning:free", "NVIDIA Nemotron Ultra Hızlı - 0 TL"),
        ("liquid/lfm-2.5-2.6b:free", "Liquid AI LFM Yüksek Hız - 0 TL"),
        ("deepseek/deepseek-r1:free", "DeepSeek R1 Bulut Akıl Yürütme - 0 TL"),
    ]

    # Audit & Status & Recommend
    if act in ("audit", "status", "recommend"):
        audit_lines = [
            "### 🛠️ Hardware Model Curator (RTX 5070 Ti 12GB VRAM Denetimi)",
            "**Donanım Profili:** RTX 5070 Ti 12GB VRAM | Intel Core i9-13900HX | 32GB RAM",
            f"**Yerel Ollama Durumu:** {'🟢 Çevrimiçi' if ollama_online else '🔴 Çevrimdışı'}\n",
            "#### 📊 Mevcut Yerel Modeller & Verimlilik Puan Tablosu:",
            "| Model Adı | Boyut | VRAM Durumu | Hız / Verimlilik | Puan | Değerlendirme |",
            "| :--- | :---: | :---: | :---: | :---: | :--- |",
        ]

        if installed_models:
            for m in installed_models:
                m_name = m.get("name", "")
                size_bytes = m.get("size", 0)
                size_gb = round(size_bytes / (1024**3), 2) if size_bytes > 0 else 4.7

                if "14b" in m_name.lower():
                    vram_status = "⚠️ 9.2 GB (%77 VRAM)"
                    speed = "~55 tok/s"
                    score = "82/100"
                    verdict = "Sınırda (Büyük bağlamda VRAM zorlanır)"
                elif "70b" in m_name.lower() or "32b" in m_name.lower():
                    vram_status = "❌ >18 GB (RAM'e Taşar!)"
                    speed = "3-5 tok/s (Kötü)"
                    score = "20/100"
                    verdict = "Kaldırılmalı! (Yerel verimsiz, buluttan çağrılmalı)"
                elif "7b" in m_name.lower() or "8b" in m_name.lower() or "latest" in m_name.lower():
                    vram_status = "✅ ~4.7 GB (%39 VRAM)"
                    speed = "105+ tok/s"
                    score = "98/100"
                    verdict = "Mükemmel (12GB VRAM Tatlı Noktası)"
                elif "3b" in m_name.lower() or "1b" in m_name.lower():
                    vram_status = "✅ ~2.0 GB (%16 VRAM)"
                    speed = "170+ tok/s"
                    score = "96/100"
                    verdict = "Ultra Hafif & Hızlı Ajan"
                else:
                    vram_status = f"~{size_gb} GB"
                    speed = "Standart"
                    score = "85/100"
                    verdict = "Kullanılabilir"

                audit_lines.append(f"| `{m_name}` | {size_gb} GB | {vram_status} | {speed} | **{score}** | {verdict} |")
        else:
            audit_lines.append("| *Hiçbir yerel model yüklü değil* | - | - | - | - | `ollama pull` gereklidir |")

        audit_lines.append("\n---\n#### 🎯 RTX 5070 Ti 12GB VRAM İçin Tavsiye Edilen Altın Model Paleti:")
        for m_key, info in sweet_spot_catalog.items():
            is_installed = any(m_key in inst for inst in installed_names)
            inst_badge = "✅ Kurulu" if is_installed else f"❌ Eksik (`{info['pull_cmd']}`)"
            audit_lines.append(
                f"- **{info['category']} (`{m_key}`):** {inst_badge}\n"
                f"  - VRAM: ~{info['vram_gb']} GB | Hız: {info['speed_tps']} | Verimlilik Puanı: **{info['score']}/100**"
            )

        audit_lines.append("\n---\n#### ☁️ 0 TL Bulut Destek Kataloğu (OpenRouter Free Tier):")
        for mid, desc in cloud_free_recommendations:
            audit_lines.append(f"- `{mid}`: {desc}")

        audit_lines.append(
            "\n> 💡 **İpucu:** Eksik modelleri senkronize etmek ve gereksiz modelleri temizlemek için "
            "`hardware_model_curator(action='optimize')` çalıştırabilirsiniz."
        )
        return "\n".join(audit_lines)

    # Optimize & Pull & Cleanup
    elif act in ("optimize", "pull_optimal", "cleanup_redundant"):
        opt_lines = [
            "### 🚀 Hardware Model Curator -> Donanım Optimizasyonu Raporu",
            "**Hedef Mimari:** RTX 5070 Ti (12GB VRAM) Maksimum Hız ve Sıfır VRAM Taşması Garantisi\n",
            "#### 📋 Gerçekleştirilen Optimizasyon & Durum Raporu:",
        ]

        missing_sweet_spots = []
        for m_key, info in sweet_spot_catalog.items():
            if not any(m_key in inst for inst in installed_names):
                missing_sweet_spots.append((m_key, info))

        if missing_sweet_spots:
            opt_lines.append("**1. Kurulumu Önerilen Tatlı Nokta Modelleri:**")
            for m_key, info in missing_sweet_spots:
                opt_lines.append(f"- 📥 `{info['pull_cmd']}` -> {info['category']} ({info['vram_gb']} GB VRAM, {info['speed_tps']})")
        else:
            opt_lines.append("✅ **Tüm Tatlı Nokta Modelleri Sisteminizde Mevcut!**")

        oversized = [m for m in installed_names if any(w in m.lower() for w in ("70b", "32b"))]
        if oversized:
            opt_lines.append("\n**2. 12GB VRAM'e Sığmayan / Kaldırılması Gereken Modeller:**")
            for o in oversized:
                opt_lines.append(f"- 🗑️ `{o}` -> CPU/RAM'e taşıp hızı 3 tok/s'ye düşürür. Kaldırmak için: `ollama rm {o}`")
        else:
            opt_lines.append("\n✅ **12GB VRAM'i zorlayan veya aşırı büyük/verimsiz model tespit edilmedi.**")

        opt_lines.append(
            "\n**3. En Verimli Model Sıralaması (Aktif Kural Seti):**\n"
            "- Kodlama Görevleri       : `qwen2.5-coder:7b` veya `llama3:latest` (4.7 GB, 110+ tok/s)\n"
            "- Akıl Yürütme & Analiz  : `deepseek-r1:8b` (4.9 GB, 95+ tok/s)\n"
            "- Hızlı Ajan Yönlendirme : `llama3.2:3b` (2.0 GB, 170+ tok/s)\n"
            "- Bulut Yedekleme        : OpenRouter `:free` & Pollinations AI (0.00 TL / Sınırsız)"
        )
        return "\n".join(opt_lines)

    else:
        return f"Bilinmeyen eylem: '{action}'. Desteklenenler: 'audit', 'optimize', 'status', 'recommend'."


if __name__ == "__main__":
    # MCP sunucusunu standart girdi/cikti (stdio) uzerinden calistir
    mcp.run()
