# 🚀 4K AI WORKSTATION

**4K AI WORKSTATION**, yerel yapay zeka modelleri (**Ollama**), bulut API sağlayıcıları (**OpenRouter**, **HuggingFace**, **Perplexity**, **OpenAI**, **Groq**) ve işletim sisteminde kurulu abonelik tabanlı CLI ajanlarını (**Hermes**, **OpenAI Codex**, **Claude Code**, **OpenCode**, **Antigravity**) tek bir çatı altında birleştiren, kendi kendine yeten akıllı yapay zeka orkestrasyon platformudur.

---

## 🌟 Tamamlanan Çekirdek Sistemler

4K AI WORKSTATION, çoklu yapay zeka modelleri ve otonom CLI ajanları arasında kesintisiz işbirliği sağlayan 6 ana mimari sistem üzerine inşa edilmiştir:

### 1. 🧠 LLM Görev Parçalayıcı & Mixture-of-Agents (MoA) Sentezleyici
- **Modüller:** `core/planner.py` & `core/parallel_executor.py`
- **LLM Destekli Parçalama (`decompose_with_llm`):** Kullanıcıdan gelen karmaşık istekleri (örneğin "Mikroservis mimarisi kur, kodla ve dokümante et") aktif bir LLM yardımıyla JSON şemasında 2-5 bağımsız alt göreve (`architecture`, `code`, `search`, `docs`) böler. Çevrimdışı durumlarda kural tabanlı yapısal ayrıştırıcıya güvenle geri düşer.
- **Paralel Yürütme (`run_parallel`):** Her alt görevi zorluk derecesi, görev etiketi ve maliyetine göre en uygun modele eşzamanlı (`asyncio.gather`) dağıtır.
- **MoA Sentezleyici (`synthesize_results`):** Farklı modeller tarafından üretilen alt görev yanıtlarını üst seviye bir sentezleyici model (Aggregator) üzerinden geçirerek tekrarsız, tutarlı ve eksiksiz tek bir Türkçe nihai yanıta dönüştürür.

### 2. 🛡️ Otomatik Eskalasyon Zinciri (Automatic Escalation & Failover)
- **Modüller:** `core/router.py` & `core/dispatcher.py`
- **Hiyerarşik Sıralama (`rank_escalation_chain`):** Bir görev için en uygun birincil modelden başlayarak, yetenek ve kota kriterlerine göre sıralı bir eskalasyon zinciri oluşturur.
- **Kesintisiz Geçiş (`dispatch_with_escalation`):** İstek gönderilen ilk model hata verir, zaman aşımına uğrar veya kota sınırına takılırsa süreç kesilmez; sistem isteği otomatik olarak zincirdeki bir sonraki üst seviye modele yükseltir (failover). Hangi modellerin denendiği `attempts` dizisiyle şeffaf şekilde raporlanır.

### 3. 📚 Canlı OpenRouter & HuggingFace Tarayan Librarian (Model Kütüphanecisi)
- **Modül:** `core/librarian.py`
- **Canlı OpenRouter Taraması (`fetch_openrouter_free_models`):** OpenRouter genel API'sini (`/api/v1/models`) canlı sorgulayarak sıfır maliyetli (`:free`, 0 prompt/completion ücreti) güncel bulut modellerini, bağlam uzunluklarını ve yeteneklerini kataloğa dahil eder.
- **Canlı HuggingFace Taraması (`fetch_huggingface_trending_models`):** Hugging Face Model Hub üzerinden son 7 günün en popüler GGUF modellerini beğeni ve indirme istatistikleriyle birlikte listeler.
- **Dinamik Puanlama & Donanım Filtresi:** Modelleri Kodlama, Akıl Yürütme, Sohbet, Hız ve Maliyet Verimliliği eksenlerinde puanlar; yerel GPU VRAM ve sistem RAM kapasitesine göre filtreler.

### 4. 🔭 Canlı GitHub Tarayan Tech Scout (Teknoloji Gözcüsü)
- **Modül:** `core/tech_scout.py`
- **Canlı Trend Keşfi (`fetch_trending_ai_repos`):** GitHub API üzerinden son 30 gün içinde yıldız alan açık kaynak AI orkestrasyon, otonom ajan ve LLM araçlarını canlı tarar.
- **Kişiselleştirilmiş Sistem İyileştirme:** Bilgisayarın gerçek donanımını (örneğin RTX 5070 Ti 12 GB VRAM) ve kurulu CLI araçlarını analiz ederek, atıl kalan kaynaklar için eyleme dönüştürülebilir terminal komutları (`ollama pull qwen2.5-coder:14b`, CLI kurulum komutları) önerir.

### 5. ⚡ Gerçek LLM Token/sn Benchmark & Tek Tıkla Model İndirme
- **Modül:** `core/benchmark.py`
- **Canlı LLM Hız Testi (`llm_benchmark`):** Yerel Ollama sunucusunda çalışan modeller üzerinde gerçek üretim hızı (**Tokens/saniye**), **İlk Token Süresi (TTFT ms)** ve **Toplam Yanıt Süresi (ms)** ölçümü yapar.
- **Tek Tıkla Model İndirme (`pull_ollama_model`):** Donanım ve Librarian önerileri doğrultusunda Ollama arka planına (`/api/pull`) model indirme komutunu gönderir.
- **Sistem Performans Testi:** İşlemci matematiksel işlem gücü (`cpu_score`) ve disk okuma/yazma hızını (`disk_io_score`) 1-100 ölçeğinde puanlar.

### 6. 💬 Çok Turlu Sohbet Hafızası ve Arayüzden Sağlayıcı/Kota Yönetimi
- **Modüller:** `core/session_memory.py`, `core/provider_config.py`, `core/quota_manager.py`
- **Kalıcı Oturum Hafızası (`SessionMemory`):** Kullanıcı konuşmalarını oturum kimliği (`session_id`) bazında `data/sessions.json` dosyasında saklar; yeni istemlere önceki turları bağlam olarak otomatik ekler (`build_contextual_prompt`).
- **Dinamik Sağlayıcı Yönetimi:** OpenRouter, HuggingFace, Perplexity, OpenAI, Groq gibi OpenAI-uyumlu sağlayıcıları sunucuyu yeniden başlatmadan API veya arayüz üzerinden ekleme, güncelleme ve silme imkanı sağlar (`config/providers.json`).
- **Granüler Kota Yönetimi:** Model bazında günlük istek kotalarını belirleme, kalan kullanım haklarını izleme ve tek tıkla sayaç sıfırlama desteği sunar (`data/quotas.json`).

### 7. 🏗️ Otomatik Proje/Dosya İnşa Motoru (Workspace Builder)
- **Modül:** `core/workspace_builder.py`
- **Otomatik Proje Üretimi (`POST /workspace/build`):** Kullanıcı istemlerini ve mimari gereksinimleri analiz ederek tam ve çalışır projeler üretir.
- **Çoklu Dosya Ayrıştırma (`extract_files_from_response`):** `### FILE: <path>` veya JSON formatındaki LLM yanıtlarını ayrıştırır ve hedef çalışma alanına (`workspace`) güvenle yazar.

---

## 📂 Proje Dizin Yapısı

```text
nexus_ai_studio/
├── config/
│   ├── providers.json               # Aktif harici API sağlayıcıları (OpenRouter, Groq vb.)
│   └── providers.example.json       # Örnek sağlayıcı şablonu
├── core/
│   ├── benchmark.py                 # CPU/Disk testi, gerçek LLM Token/sn testi ve model indirme
│   ├── cli_registry.py              # Sistemde kurulu CLI ajanlarının otomatik keşfi
│   ├── dispatcher.py                # İstek dağıtıcı ve otomatik eskalasyon yöneticisi
│   ├── hardware.py                  # Win11 GlobalMemoryStatusEx RAM & GPU VRAM tespiti
│   ├── librarian.py                 # Model kütüphanecisi, OpenRouter & HF canlı tarayıcısı
│   ├── parallel_executor.py         # Paralel yürütücü & Mixture-of-Agents sentezleyici
│   ├── planner.py                   # LLM destekli görev parçalayıcı (Task Decomposer)
│   ├── provider_config.py           # Dinamik sağlayıcı yükleme, ekleme ve silme
│   ├── quota_manager.py             # Kalıcı model kullanım ve kota yönetimi
│   ├── router.py                    # Akıllı yönlendirici ve eskalasyon zinciri üretici
│   ├── session_memory.py            # Çok turlu oturum ve konuşma geçmişi hafızası
│   └── tech_scout.py                # Sistem analizi ve canlı GitHub AI kütüphane gözcüsü
├── ui/
│   ├── server.py                    # FastAPI REST API arka uç sunucusu (:8000)
│   └── app.py                       # Streamlit etkileşimli kontrol paneli (:8501)
├── wrappers/
│   ├── base_wrapper.py              # Temel soyut wrapper sınıfı
│   ├── ollama_wrapper.py            # Yerel Ollama REST API sarmalayıcısı
│   ├── hermes_wrapper.py            # Hermes CLI headless sarmalayıcısı
│   ├── codex_wrapper.py             # OpenAI Codex CLI (`codex exec`) sarmalayıcısı
│   ├── claude_code_wrapper.py       # Claude Code CLI (`claude -p`) sarmalayıcısı
│   ├── opencode_wrapper.py          # OpenCode CLI (`opencode run`) sarmalayıcısı
│   └── openai_compatible_wrapper.py # Genel OpenAI-uyumlu bulut sarmalayıcısı
├── tests/                           # Kapsamlı çevrimdışı birim testleri (51 test)
├── setup.ps1                        # Sanal ortam kurulum ve doğrulama betiği
└── run.ps1                          # Backend ve Dashboard tek komut başlatıcı
```

---

## 🔌 RESTful API Uç Noktaları

4K AI WORKSTATION arka uç sunucusu (`http://127.0.0.1:8000`) aşağıdaki kapsamlı REST API arayüzünü sunar:

### 1. Sistem ve Durum
| Yöntem | Uç Nokta | Açıklama |
|---|---|---|
| `GET` | `/health` | Sunucu sağlık durumunu döndürür (`{"status": "ok"}`). |
| `GET` | `/status` | Çevrimiçi durum, kayıtlı model listesi, kotalar ve oturum listesini döndürür. |

### 2. Yürütme ve Akıllı Orkestrasyon
| Yöntem | Uç Nokta | Parametreler & Gövde | Açıklama |
|---|---|---|---|
| `POST` | `/query` | `QueryRequest`: `{ "prompt": str, "model": "auto"\|str, "parallel": bool, "synthesize": bool, "use_llm_planner": bool, "session_id": str, "use_memory": bool, "workspace": str }` | İstekleri akıllı yönlendirici, otomatik eskalasyon, LLM tabanlı paralel parçalama ve MoA sentezleme ile işler. |

### 3. CLI Ajanları & Abonelikler
| Yöntem | Uç Nokta | Açıklama |
|---|---|---|
| `GET` | `/cli/tools` | Sistemde kurulu olan ve desteklenen CLI ajanlarının (Hermes, Codex, Claude Code, OpenCode) durumunu listeler. |

### 4. Sağlayıcı (Provider) Yönetimi
| Yöntem | Uç Nokta | Parametreler & Gövde | Açıklama |
|---|---|---|---|
| `GET` | `/providers` | - | Aktif OpenAI-uyumlu sağlayıcıları listeler. |
| `POST` | `/providers` | `ProviderUpsertRequest`: `{ "name", "base_url", "model", "api_key", "capability", "cost", "strengths" }` | Yeni sağlayıcı ekler veya günceller; çalışma zamanında hemen aktifleştirir. |
| `DELETE` | `/providers/{name}` | URL path: `name` | Belirtilen sağlayıcıyı sistemden ve yapılandırmadan kaldırır. |

### 5. Kota Yönetimi
| Yöntem | Uç Nokta | Parametreler & Gövde | Açıklama |
|---|---|---|---|
| `POST` | `/quotas/limit` | `QuotaLimitRequest`: `{ "model": str, "limit": int }` | Belirli bir modelin günlük kota limitini ayarlar. |
| `POST` | `/quotas/reset` | `QuotaResetRequest`: `{ "model": str \| null }` | Belirli bir modelin veya tüm modellerin kota sayacını sıfırlar. |

### 6. Sohbet Hafızası & Oturumlar
| Yöntem | Uç Nokta | Açıklama |
|---|---|---|
| `GET` | `/sessions` | Kayıtlı tüm oturum kimliklerini listeler. |
| `GET` | `/sessions/{session_id}` | Belirtilen oturumun konuşma geçmişini döndürür. |
| `DELETE` | `/sessions/{session_id}` | Belirtilen oturumun hafıza geçmişini temizler. |

### 7. Donanım & Benchmark
| Yöntem | Uç Nokta | Açıklama |
|---|---|---|
| `GET` | `/hardware/info` | CPU çekirdeği, gerçek RAM (GB) ve GPU VRAM (GB) değerlerini döndürür. |
| `GET` | `/hardware/recommend` | Donanıma en uygun yerel model önerilerini döndürür. |
| `GET` | `/hardware/benchmark` | CPU ve Disk G/Ç sentetik hız skorlarını (1-100) döndürür. |
| `POST` | `/hardware/llm-benchmark` | `{ "model": "llama3" }` — Yerel model için gerçek **Token/saniye**, **TTFT** ve gecikme testi yapar. |
| `POST` | `/hardware/pull-model` | `{ "model": "qwen2.5-coder:14b" }` — Modeli arka planda Ollama'ya indirme isteği gönderir. |

### 8. Model Kütüphanecisi (Librarian) & Teknoloji Gözcüsü (Tech Scout)
| Yöntem | Uç Nokta | Query Parametreleri | Açıklama |
|---|---|---|---|
| `GET` | `/librarian/catalog` | `task_type=general\|coding\|reasoning\|chat\|fast`, `only_free=bool`, `include_online=bool` | Donanım sınırlarına göre puanlanmış model kataloğunu; istenirse canlı OpenRouter ve HuggingFace modellerini döndürür. |
| `GET` | `/scout/report` | `include_online=bool` | Donanım verimliliği, eksik araçlar ve istenirse trend GitHub AI kütüphanelerini içeren denetim raporu üretir. |

### 9. Proje ve Çalışma Alanı İnşası (Workspace Builder)
| Yöntem | Uç Nokta | Parametreler & Gövde | Açıklama |
|---|---|---|---|
| `POST` | `/workspace/build` | `WorkspaceBuildRequest`: `{ "prompt": str, "workspace": str, "model": "auto"|str }` | LLM çıktılarından çoklu dosya bloklarını (`### FILE: <path>` / JSON) ayrıştırıp hedef çalışma alanına (`core/workspace_builder.py` - Otomatik Proje/Dosya İnşa Motoru) güvenli ve eksiksiz şekilde otomatik yazar. |

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum ve Doğrulama
Tek bir komutla sanal ortamı (`.venv`) kurabilir, bağımlılıkları yükleyebilir ve birim testlerini çalıştırabilirsiniz:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### 2. Sunucu ve Kontrol Panelini Başlatma
Arka uç API sunucusu (`FastAPI`) ve kullanıcı arayüzünü (`Streamlit`) eşzamanlı olarak başlatmak için:
```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```
- **REST API Sunucusu:** `http://127.0.0.1:8000`
- **Streamlit Kontrol Paneli:** `http://localhost:8501`

*(Not: `run.ps1` betiği `--server.headless true` ve `--browser.gatherUsageStats false` bayraklarıyla yapılandırılmıştır; ilk açılışta e-posta sorma ekranına takılmadan doğrudan paneli açar).*

### 3. Testleri Çalıştırma
Tüm çekirdek orkestrasyon, eskalasyon, yönlendirme ve CLI testlerini çevrimdışı çalıştırmak için:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
*(Toplam 51 birim testi ağ bağlantısından bağımsız olarak hatasız geçmektedir).*
