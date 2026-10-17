# Nexus AI Studio - Proje İlerlemesi

## Mevcut Durum
- **Durum:** Faz 1, Faz 2, Faz 3, Faz 4 (Librarian) ve Faz 5 (Tech Scout) tamamlandı ve doğrulandı.
- **Tamamlanma:** %100 (Çekirdek Platform + Çoklu CLI Abonelik Ajanları + Donanım/Benchmark + Librarian + Tech Scout)
- **Ana Proje Dizini:** `C:\Users\kloss\nexus_ai_studio` (OpenCode çalışma alanı `C:\Users\kloss\OneDrive\Belgeler\Varsayılan Proje` ile senkronize edildi, hatalı `Varsaylan Proje` klasörü temizlendi)
- **Ortam:** Python 3.14.7 + Git 2.55 kurulu, proje kendi `.venv` sanal ortamını kullanıyor.

## Giderilen Karmaşalar ve Kritik Hatalar (2026-10-17)
1. **3 Farklı Klasör Karmaşası Düzeltildi:**
   - Hermes projeyi `C:\Users\kloss\nexus_ai_studio` altında yarım ve bozuk bırakmıştı.
   - OpenCode (`big-pickle` modeli) dosyaları `Varsayılan Proje` dizinine kopyalarken Türkçe `ı` harfini düşürerek 3. bir klasör (`Varsaylan Proje`) oluşturmuştu.
   - Tüm geliştirmeler ve git geçmişi asıl `C:\Users\kloss\nexus_ai_studio` ve `C:\Users\kloss\OneDrive\Belgeler\Varsayılan Proje` dizinlerinde birleştirildi; hatalı `Varsaylan Proje` kopyası kaldırıldı.
2. **Windows 11 RAM Tespiti ve Benchmark Hatası Düzeltildi:**
   - `core/hardware.py` Windows 11'de kaldırılmış olan `wmic` komutuna güvendiği için 32 GB RAM'li cihazı `8.0 GB RAM` sanıyordu. `ctypes.windll.kernel32.GlobalMemoryStatusEx` ile gerçek donanım (**31.71 GB RAM + NVIDIA GeForce RTX 5070 Ti Laptop GPU 12 GB VRAM**) doğru okunur hale getirildi.
   - `core/benchmark.py` içinde sabit yazılmış `elapsed = 0.001` düzeltilip gerçek `time.perf_counter()` ölçümü eklendi.
3. **Tüm CLI Araçları ve Abonelik Ajanları Eklendi (`core/cli_registry.py` & `wrappers/`):**
   - **Hermes CLI** (`wrappers/hermes_wrapper.py`)
   - **OpenAI Codex CLI** (`wrappers/codex_wrapper.py` — `codex exec` headless modu)
   - **Claude Code CLI** (`wrappers/claude_code_wrapper.py` — `claude -p` headless modu)
   - **OpenCode CLI** (`wrappers/opencode_wrapper.py` — `opencode-cli run` headless modu)
   - **OpenAI-Uyumlu Bulut Sağlayıcıları** (`wrappers/openai_compatible_wrapper.py` + `config/providers.json` — OpenRouter, HuggingFace, Perplexity, Groq, OpenAI)
4. **Faz 4 (Model Librarian) ve Faz 5 (Tech Scout) Tamamlandı:**
   - `core/librarian.py`: Görev tipine (`coding`, `reasoning`, `chat`, `fast`) ve GPU VRAM sınırına göre modelleri puanlayan Yetenek Matrisi + yerel Ollama (`/api/tags`) keşfi.
   - `core/tech_scout.py`: Cihazın 12 GB VRAM kapasitesini, kurulu CLI araçlarını ve açık kaynak AI orkestrasyon iyileştirmelerini denetleyen Teknoloji Gözcüsü.

## Doğrulanmış Bileşenler
- [x] FastAPI sunucusu (`ui/server.py`): `/health`, `/status`, `/query`, `/cli/tools`, `/hardware/info`, `/hardware/recommend`, `/hardware/benchmark`, `/librarian/catalog`, `/scout/report`
- [x] Streamlit kontrol paneli (`ui/app.py`): 4 sekmeli Türkçe arayüz (Komut Merkezi, CLI Ajanları & Abonelikler, Model Kütüphanecisi, Teknoloji Gözcüsü)
- [x] Akıllı Yönlendirici (`core/router.py`): Zorluk derecesi + görev etiketi (`chat`, `code`, `search`, `reasoning`, `agentic`) + kota kontrolü
- [x] Paralel Yürütücü (`core/planner.py` + `core/parallel_executor.py`): Görevi alt parçalara bölüp farklı modellere eşzamanlı dağıtma
- [x] 51 çevrimdışı birim testi (`python -m unittest discover -s tests`) eksiksiz geçiyor.
