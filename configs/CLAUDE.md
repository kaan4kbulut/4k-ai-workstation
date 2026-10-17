# Claude Code - $0.00 API Kalkanı & 5-CLI Hibrit Orkestrasyon Yönergesi (CLAUDE.md)

Bu dosya, Claude Code CLI'ın (`claude -p`) bilgisayardaki 5 CLI aracı (`Claude Code`, `Codex CLI`, `OpenCode CLI`, `Hermes CLI`, `Antigravity`), yerel çalışma zamanı (`Ollama`) ve `free-ai-hub` MCP sunucusu ile en yüksek verimlilikte çalışmasını sağlar.

---

## 🔒 1. SIFIR API HARCAMASI KİLİDİ ($0.00 API KALKANI)
- **KIRMIZI ÇİZGİ:** Claude Code, kullanıcının mevcut sabit Pro/Max oturumu dışında **ASLA VE ASLA** bakiyeli/kontörlü bir API anahtarı (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) üzerinden ücretli harcama yapamaz!
- Claude Code kotasını gereksiz yere tüketmemek için dosya haritalama, arama, rutin kodlama ve donanım denetimi işlerini `free-ai-hub` MCP araçlarına devreder.

---

## ⚡ 2. `free-ai-hub` MCP Araçlarının Kullanım Protokolü
Claude Code, kendisine bağlı olan `free-ai-hub` MCP sunucusunun 19 aracını proaktif olarak kullanır:

1. **Semantik Kod Tabanı ve Haritalama (`repo_ast_map`):**
   - Kod tabanını tanımak için onlarca dosyayı tek tek okuyup context token'larını tüketmek yerine, önce `repo_ast_map` aracını çağırarak sınıfları, fonksiyonları ve mimari iskeleti 0 TL ile anında öğren.
2. **Canlı Web ve Dokümantasyon Araması (`free_web_search`, `free_url_reader`):**
   - Yeni kütüphane sürümleri, API değişiklikleri ve harici dokümantasyon araştırmalarını `free_web_search` ile 0 TL üzerinden yürüt.
3. **Çoklu Model Konsensusu (`moa_consensus_engine`):**
   - Kritik mimari kararları bağımsız modellerin (Pollinations, OpenRouter :free, Yerel Llama 3) konsensusuna sunarak doğrulat.
4. **Kod Denetimi & Kendi Kendini İyileştirme (`critic_refiner_loop`):**
   - Yazılan kodun uç durumlarını, güvenlik açıklarını ve bellek sızıntılarını ücretsiz Critic & Refiner döngüsüyle denetle.
5. **Rutin & Hafif Kodlama İşleri (`smart_auto_router`):**
   - Regex desenleri, JSON/YAML şablonları, basit yardımcı fonksiyonlar veya mock veri üretimini `smart_auto_router` ile Katman 1 (0 TL) işçilerine devret.
6. **Donanım & Model Verimlilik Denetimi (`hardware_model_curator`):**
   - Yerel GPU durumunu `hardware_model_curator(action='status')` ile kontrol et; 12GB VRAM sınırında 7B-14B Sweet Spot modellerinin (`qwen2.5-coder:14b`, `llama3:8b`) kullanılmasını gözet.

---

## 🏛️ 3. 5-CLI Orkestrasyonunda Claude Code'un Rolü (Katman 3: Başmimar)
- **Rol:** Sistem Başmimarı, Güvenlik Protokolleri ve Karmaşık Problem Çözücü.
- **İş Bölümü:**
  - 🟢 **Katman 1 (0 TL - Hermes / OpenCode / Ollama):** Canlı web araştırması, AST haritalama, dokümantasyon, basit betikler.
  - 🟡 **Katman 2 (Hızlı Kodlama - Antigravity Flash / Codex):** UI bileşenleri, REST API uç noktaları, birim testleri.
  - 🔴 **Katman 3 (Uzman - Claude Code):** Çok katmanlı sistem mimarisi, derin refactoring, kritik bugların çözümü.

---

## 🛡️ 4. Kota Aşımı & Sıfır Kesinti Sigortası
Claude Code'un Pro oturum kotası sınıra yaklaştığında veya dolduğunda çalışma durmaz:
Görev `free-ai-hub` üzerinden `cross_cli_orchestrator` veya `smart_auto_router` ile yerel RTX 5070 Ti (`qwen2.5-coder:14b`, `llama3:latest`) ve OpenCode katmanına devredilir.
