# 🚀 Nexus AI Studio

Akıllı bir **AI orkestratörü ve model geçidi**. Birden fazla LLM sağlayıcısını
(yerel ve bulut) yönetir; görevleri karmaşıklığına göre yönlendirir, kotaları
takip eder ve alt görevleri paralel çalıştırır.

> **Durum:** çalışan MVP. FastAPI arka ucu + Streamlit paneli + Ollama ve Hermes
> wrapper'ları uçtan uca doğrulandı. `Claude`/`Codex` katmanları tanımlı ama
> henüz wrapper'ları yok.

## 📁 Proje Yapısı
- `/core`: Sistemin beyni.
    - `dispatcher.py`: İstekleri kayıtlı model wrapper'larına gönderir (tekli veya paralel).
    - `router.py`: Bir istek için en uygun modeli seçer (karmaşıklık + maliyet + kota).
    - `quota_manager.py`: Model başına kullanım limitlerini `data/quotas.json`'da tutar.
    - `planner.py`: Karmaşık bir isteği daha küçük alt görevlere böler.
    - `parallel_executor.py`: Alt görevleri `asyncio.gather` ile eşzamanlı çalıştırır.
- `/ui`
    - `server.py`: FastAPI arka ucu (`/health`, `/status`, `/query`).
    - `app.py`: Streamlit kontrol paneli.
- `/wrappers`
    - `base_wrapper.py`: Tüm wrapper'lar için soyut temel sınıf.
    - `ollama_wrapper.py`: Ollama HTTP API'si üzerinden yerel modeller.
    - `hermes_wrapper.py`: Hermes ajan CLI'ı (headless, tek seferlik).
- `/tests`: Birim testleri (ağ veya LLM gerektirmez).
- `/data`: Kalıcı kota durumu (git tarafından yok sayılır).

## 🛠️ Kurulum

**Python 3.12+** gerekir (3.14 ile test edildi). Kurulu değilse:

```powershell
winget install --scope user Python.Python.3.14
```

Ardından sanal ortamı oluşturup bağımlılıkları kur — tek komut:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Bu komut `.venv` oluşturur, `requirements.txt`'i kurar ve testleri çalıştırır.

<details>
<summary>Elle kurulum (eşdeğeri)</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
</details>

## ▶️ Çalıştırma

Tek komut hem arka ucu hem paneli başlatır:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Sonra http://localhost:8501 adresini aç. İkisini durdurmak için Ctrl+C.

<details>
<summary>İki servisi elle çalıştırma</summary>

**Terminal 1 — arka uç**
```powershell
.\.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — panel**
```powershell
.\.venv\Scripts\python.exe -m streamlit run ui/app.py
```
</details>

## 🔧 Yapılandırma (ortam değişkenleri)

| Değişken | Varsayılan | Anlamı |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama sunucu adresi |
| `OLLAMA_MODEL` | `llama3` | Ollama wrapper'ının kullandığı model |
| `OLLAMA_TIMEOUT` | `120` | İstek başına zaman aşımı (saniye) |
| `HERMES_BIN` | otomatik bulunur | `hermes` çalıştırılabilir dosyasının yolu |
| `HERMES_MODEL` | (Hermes varsayılanı) | Hermes için isteğe bağlı model |
| `HERMES_TIMEOUT` | `300` | Hermes alt süreç zaman aşımı (sn) |
| `HERMES_MAX_TURNS` | `6` | Hermes ajan tur bütçesi |
| `HERMES_RUN_BUDGET` | `180` | Hermes toplam süre bütçesi (sn) |

Ollama wrapper'ı için modelin yerelde kurulu olması gerekir:

```bash
ollama pull llama3
```

### Hermes entegrasyonu

Hermes CLI'ı bulunduğunda (`HERMES_BIN`, `PATH` veya
`%LOCALAPPDATA%\hermes\bin\hermes.exe`) otomatik kaydedilir. Her istek şunu çalıştırır:

```
hermes chat --query-file - -Q --max-turns N --run-budget S
```

İstek, stdin üzerinden verilir (`--query-file -`), böylece shell tarafından
yorumlanmaz. `-Q` ile stdout'a yalnızca düz final yanıt gelir; `session_id`
bilgisi stderr'e düşer. `--yolo` bilinçli olarak asla kullanılmaz; böylece
Hermes gözetimsiz/geri dönüşsüz işlem yapmak yerine onay sorar.

## 🧪 Testler

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Testler çevrimdışı çalışır — LLM veya ağ erişimi gerekmez.

## 📡 API

| Yöntem | Yol | Açıklama |
| --- | --- | --- |
| GET | `/health` | Servis ayakta mı (canlılık kontrolü) |
| GET | `/status` | Kayıtlı modeller + kota özeti |
| POST | `/query` | `{prompt, model: "auto"\|"Ollama"\|"Hermes", parallel: bool}` |

Örnek:

```bash
curl -X POST http://127.0.0.1:8000/query ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"Merhaba de\", \"model\": \"auto\", \"parallel\": false}"
```

## 📈 Mevcut Durum

- [x] **Çekirdek altyapı:** modüler wrapper sistemi + dispatcher
- [x] **Akıllı yönlendirme:** triage + yetenek/maliyet bazlı seçim
- [x] **Kota yönetimi:** kalıcı kullanım takibi + otomatik geri düşme
- [x] **Panel:** çalışan Streamlit arayüzü + API köprüsü
- [x] **Paralellik:** görev bölme + eşzamanlı çalıştırma
- [x] **CLI ajan wrapper'ı:** Hermes (headless, tek seferlik)
- [ ] **Bulut/CLI wrapper'ları:** Claude Code, Codex, Antigravity
- [ ] **Cihaz benchmark'ı / model önerisi**
- [ ] **Librarian** (model keşfi ve puanlama) ve **Tech Scout** (kendini güncelleme)

> CLI ajan wrapper'ları yalnızca aracı çalıştırıp stdout'u okur — etkileşimsiz
> modu olan her ajan (ör. `hermes chat -q "..." -Q`) takılabilir. OpenAI uyumlu
> uç nokta sunan sağlayıcılar (`hermes proxy` gibi) ortak bir istemci
> wrapper'ını yeniden kullanabilir.

## ⏭️ Sonraki Adımlar

1. Bulut sağlayıcıları ve CLI ajanları için gerçek wrapper'lar ekle.
2. En uygun yerel modeli önermek için cihaz benchmark'ı ekle.
3. Otomatik model keşfi ve puanlama için `Librarian` ajanını kur.
4. Kendini güncelleme için `Tech Scout`'u uygula.
