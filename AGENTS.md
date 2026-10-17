# AGENTS.md

## 🔒 KIRMIZI ÇİZGİ: SIFIR API HARCAMASI KİLİDİ ($0.00 API KALKANI)
- Ne Antigravity ne de 4K AI WORKSTATION **ASLA VE ASLA ücretli (kullandıkça öde / kontörlü / bakiyeli) bir API üzerinden harcama yapamaz!**
- API üzerinden yalnızca **%100 Ücretsiz (`0.00 TL`)** kaynaklar (`http://127.0.0.1:11434` Yerel Ollama ve `:free` etiketli OpenRouter ücretsiz modelleri) çağrılabilir.
- CLI araçları (`Claude Code`, `Codex`, `Hermes`, `OpenCode`) asla `ANTHROPIC_API_KEY` veya `OPENAI_API_KEY` ile bakiyeli API modunda çalıştırılmaz; yalnızca ücretsiz modda veya kullanıcının mevcut sabit oturumuyla (ekstra 1 kuruş bile yazmadan) çalışır.

---

Bu dosya, bu projede çalışan tüm ajanlar (OpenCode, Hermes vb.) için kuralları
tanımlar.

## İletişim dili

- Kullanıcıyla **her zaman Türkçe** iletişim kur.
- Yanıtlar, açıklamalar, özetler, sorular ve uyarılar Türkçe olsun.
- Teknik terimler, dosya adları, komutlar, değişken adları ve kod İngilizce
  kalabilir; ancak bunların etrafındaki açıklama Türkçe olmalı.
- Kullanıcıya gösterilen metinler (README, PROGRESS.md, arayüz etiketleri)
  Türkçe tutulmalı.
- Commit mesajları Türkçe yazılır.

## Proje: 4K AI WORKSTATION

Birden fazla LLM sağlayıcısını (yerel + bulut + CLI ajanları) tek yerden yöneten
orkestratör.

### Ortam
- Python 3.14 (`.venv` sanal ortamı).
- Bağımlılıklar: `requirements.txt`.
- Kurulum: `powershell -ExecutionPolicy Bypass -File .\setup.ps1`
- Çalıştırma (sunucu + panel): `powershell -ExecutionPolicy Bypass -File .\run.ps1`
- Testler: `.\.venv\Scripts\python.exe -m unittest discover -s tests`

### Mimari
- `core/` — `dispatcher.py`, `router.py`, `planner.py`,
  `parallel_executor.py`, `quota_manager.py`
- `ui/` — `server.py` (FastAPI), `app.py` (Streamlit)
- `wrappers/` — `base_wrapper.py`, `ollama_wrapper.py`, `hermes_wrapper.py`
- `tests/` — çevrimdışı birim testleri (LLM/ağ gerekmez)

### Kurallar
- Yeni bir model/araç eklemek: `BaseWrapper`'dan türet + `register_wrapper`.
- Router yalnızca **kayıtlı** wrapper'ları seçmeli (`available_names`).
- `--yolo` benzeri gözetimsiz/geri dönüşsüz bayraklar kullanılmaz.
- Değişiklikten sonra testler çalıştırılır ve commit edilir.

## Antigravity ile Entegre 3 Katmanlı Orkestrasyon

4K AI WORKSTATION, maliyet ve performans dengesini optimize etmek için Antigravity ile entegre 3 katmanlı hiyerarşik yönlendirme mimarisi uygular:

### 1. Katman 1: Ücretsiz / Hafif Temel Katman (Triage & Rutin İşler)
- **Bileşenler ve Modeller:**
  - Yerel Ollama (örn. `llama3`, `deepseek-coder`)
  - OpenRouter Free (örn. `qwen/qwen-2.5-coder-32b-instruct:free`)
  - Flash-Lite
- **İşlev:** Temel sohbet, hızlı ön sınıflandırma, rutin kod tamamlama, küçük refaktörler ve basit soru-cevap.
- **Kural:** Maliyeti sıfır tutmak için tüm rutin istekler öncelikle bu katmanda karşılanır.

### 2. Katman 2: Paralel Çalışma & Özel Görev Katmanı (Uzman Ajanlar)
- **Bileşenler ve Modeller:**
  - Paralel Flash Ajanları (Google Flash)
  - Codex / Kod Ajanları
  - Hermes Agent
  - OpenCode Interpreter
- **İşlev:** `Planner` ile alt adımlara ayrılan karmaşık görevlerin `ParallelExecutor` ile paralel işlenmesi, araç/CLI kullanımı, orta-ileri düzey kod geliştirme ve analiz.
- **Kural:** Çok adımlı iş akışları ve alt görevler bağımsız paralel ajanlara bölünerek eşzamanlı yürütülür.

### 3. Katman 3: Üst Düzey Akıl Yürütme & Otomatik Eskalasyon (Kritik & Zor Görevler)
- **Bileşenler ve Modeller:**
  - Claude Code
  - Gemini Pro / GPT-4o sınıfı gelişmiş modeller
- **İşlev:** Derin mimari kararlar, kapsamlı hata ayıklama (debugging), güvenlik denetimleri ve karmaşık sistem tasarımı.
- **Otomatik Eskalasyon Zinciri:**
  - Katman 1 veya Katman 2'deki modeller hata verdiğinde, zaman aşımına uğradığında veya kota tükendiğinde `dispatcher.dispatch_with_escalation` devreye girer.
  - İstek otomatik olarak zincirdeki bir sonraki üst modele (Katman 3 / Pro) yükseltilir (failover/escalation).
  - Kullanıcıya hangi modellerin denendiği şeffaf olarak raporlanır.

