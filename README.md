# 🚀 Nexus AI Studio

**Nexus AI Studio**, yerel modeller (Ollama), bulut API sağlayıcıları (OpenRouter, HuggingFace, Perplexity, OpenAI, Groq) ve abonelik tabanlı CLI ajanlarını (**Hermes**, **OpenAI Codex**, **Claude Code**, **OpenCode**, **Antigravity**) tek bir merkezden yöneten akıllı yapay zeka orkestratörüdür.

---

## ✨ Temel Özellikler

1. **Akıllı Yönlendirme Motoru (`core/router.py`):**
   - Gelen görevin zorluk derecesini (1–10) ve yetenek etiketlerini (`chat`, `code`, `search`, `reasoning`, `agentic`) analiz eder.
   - Kotaları (`core/quota_manager.py`) ve maliyetleri gözeterek göreve en uygun çalışan modeli/ajanı otomatik seçer.
2. **CLI Ajanları & Abonelik Orkestrasyonu (`core/cli_registry.py` & `wrappers/`):**
   - Bilgisayarınızda kurulu olan CLI araçlarını (`Ollama`, `Hermes`, `Codex`, `Claude Code`, `OpenCode`, `Antigravity`, `Cursor`) otomatik tespit eder ve etkileşimsiz (headless) modda çalıştırır.
3. **Paralel Görev Fabrikası (`core/planner.py` & `core/parallel_executor.py`):**
   - Karmaşık görevleri alt görevlere (Mimari, Kodlama, Dokümantasyon) böler ve farklı modellere aynı anda (`asyncio.gather`) dağıtarak hızlandırır.
4. **Donanım Tespiti & Cihaz Benchmark'ı (`core/hardware.py` & `core/benchmark.py`):**
   - İşlemci çekirdeği, gerçek fiziksel RAM (Windows `GlobalMemoryStatusEx`) ve GPU VRAM (`nvidia-smi`) değerlerini okuyarak cihazınıza en uygun yerel modelleri önerir.
5. **Model Kütüphanecisi (`core/librarian.py`) & Teknoloji Gözcüsü (`core/tech_scout.py`):**
   - Modelleri Kodlama, Akıl Yürütme, Sohbet, Hız ve Maliyet Verimliliği kriterlerine göre puanlar; yerel Ollama modellerini (`/api/tags`) tarar ve sistem iyileştirme önerileri üretir.

---

## 📂 Proje Yapısı

```text
nexus_ai_studio/
├── config/
│   ├── providers.json          # Aktif OpenAI-uyumlu sağlayıcılar
│   └── providers.example.json  # OpenRouter, Perplexity, HF örnek şablonu
├── core/
│   ├── benchmark.py            # CPU ve Disk G/Ç hız testi
│   ├── cli_registry.py         # CLI ajan keşfi ve otomatik kayıt
│   ├── dispatcher.py           # İstek dağıtıcı (tekli & paralel)
│   ├── hardware.py             # RAM / GPU VRAM tespiti ve yerel model önerisi
│   ├── librarian.py            # Faz 4: Model Kütüphanecisi & Yetenek Matrisi
│   ├── parallel_executor.py    # Faz 3: Eşzamanlı alt görev yürütücü
│   ├── planner.py              # Faz 3: Görev parçalayıcı (Task Decomposer)
│   ├── provider_config.py      # JSON sağlayıcı yapılandırma yükleyici
│   ├── quota_manager.py        # Kalıcı kota ve kullanım takibi
│   ├── router.py               # Faz 2: Yetenek ve maliyet bazlı yönlendirici
│   └── tech_scout.py           # Faz 5: Teknoloji Gözcüsü & sistem analizi
├── ui/
│   ├── server.py               # FastAPI arka uç sunucusu (:8000)
│   └── app.py                  # Streamlit kontrol paneli (:8501)
├── wrappers/
│   ├── base_wrapper.py         # Soyut wrapper temel sınıfı
│   ├── ollama_wrapper.py       # Yerel Ollama HTTP API sarmalayıcısı
│   ├── hermes_wrapper.py       # Hermes CLI headless sarmalayıcısı
│   ├── codex_wrapper.py        # OpenAI Codex CLI (codex exec) sarmalayıcısı
│   ├── claude_code_wrapper.py  # Claude Code CLI (claude -p) sarmalayıcısı
│   ├── opencode_wrapper.py     # OpenCode CLI (opencode run) sarmalayıcısı
│   └── openai_compatible_wrapper.py # Genel OpenAI-uyumlu HTTP sarmalayıcısı
├── tests/                      # Çevrimdışı birim testleri (51 test)
├── setup.ps1                   # Tek komutla .venv kurulumu ve test doğrulama
└── run.ps1                     # Tek komutla FastAPI + Streamlit başlatma
```

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum ve Test Doğrulama
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### 2. Sunucu ve Kontrol Panelini Başlatma
```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```
- **API Sunucusu:** `http://127.0.0.1:8000` (`/status`, `/cli/tools`, `/hardware/info`, `/hardware/recommend`, `/librarian/catalog`, `/scout/report`)
- **Kontrol Paneli (UI):** `http://localhost:8501`

### 3. Testleri Çalıştırma
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
