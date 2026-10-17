# Nexus AI Studio - Project Progress

## Current State
- **Status:** Phase 1 (Core Engine + UI) — çalışır durumda
- **Completion:** ~%30 (Faz 1 tamam, Faz 2 kısmen tamam)

> Not: Bu dosya daha önce `%5` yazıyordu ama ajan kullanıcıya `%25` demişti.
> Bu tutarsızlık 2026-10-17'de giderildi ve dosya gerçek duruma göre güncellendi.

## Doğrulanmış Durum (2026-10-17)
- [x] FastAPI sunucusu (`ui/server.py`) ayakta: `/health`, `/status`, `/query`
- [x] Streamlit paneli (`ui/app.py`) sözdizimi hatası düzeltildi, çalışıyor
- [x] Ollama wrapper gerçek LLM yanıtı döndürüyor (`llama3` ile uçtan uca test edildi)
- [x] Router: karmaşık görev → güçlü model, basit görev → yerel/ucuz model
- [x] Kota yöneticisi: `data/quotas.json` üzerinden kalıcı sayaç, otomatik düşme
- [x] Paralel yürütme: görev bölme + `asyncio.gather` ile eşzamanlı çalıştırma
- [x] 12 birim testi geçiyor (`python -m unittest discover -s tests`)

## Bu Oturumda Düzeltilen Hatalar
1. `ui/app.py`: çift `if st.button(...)` satırı → IndentationError (dosya hiç çalışmıyordu).
2. `ui/app.py`: `is_parallel` tanımsızdı → NameError.
3. `wrappers/ollama_wrapper.py`: `ollama run` alt süreci model yoksa donuyordu ve sessizce
   çok GB'lık indirme başlatıyordu. HTTP API + timeout + anlaşılır hata mesajına çevrildi.
4. Router kayıtlı olmayan modeli (Claude/Codex) seçiyordu → istek "Wrapper not registered"
   ile düşüyordu. Artık `select_best_model(prompt, available_names)` yalnızca gerçekten
   bağlı modelleri seçiyor.
5. Paralel akışta kota her zaman "Ollama"ya yazılıyordu (gerçek model bilinmiyordu).
   Executor artık görev başına kullanılan modeli döndürüyor.

## Eksikler / Yapılacaklar
- [ ] Gerçek CLI ajanları: Claude Code, Codex, Antigravity wrapper'ları (projenin asıl amacı)
- [ ] Cihaz testi / benchmark ve otomatik model önerisi (asıl istenen özellik)
- [ ] Bulut hesap/API anahtarı yönetimi (kullanıcının "tüm hesaplarımı bir araya getir" isteği)
- [ ] Faz 4: Librarian (yeni model keşfi + puanlama)
- [ ] Faz 5: Tech Scout (kendi kendini güncelleme)
- [ ] Şu an `Codex` ve `Claude` tier'ları tanımlı ama **hiç wrapper'ı yok**
- [ ] Geliştirme ortamı: makinede sistem Python'u ve Git kurulu değil

## Architectural Notes
- Plugin tabanlı wrapper mimarisi; yeni model eklemek = yeni dosya + `register_wrapper`.
- Core, model implementasyonlarından ayrık (`BaseWrapper` soyutlaması).
- Konfigürasyon ortam değişkenleriyle: `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.

## Handover Seal
- **Last Session Date:** 2026-10-17 (OpenCode ile sürdürüldü)
- **Status:** Çalışan MVP
- **Ready for:** Faz 2 kalanı (gerçek bulut/CLI wrapper'ları) ve Faz 3 entegrasyonu
