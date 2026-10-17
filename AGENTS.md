# AGENTS.md

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

## Proje: Nexus AI Studio

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
