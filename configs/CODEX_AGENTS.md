# Codex CLI - $0.00 API Kalkanı & 5-CLI Orkestrasyon Yönergesi (CODEX_AGENTS.md)

Bu dosya, OpenAI Codex CLI'ın (`codex exec`) 5-CLI ekosistemi ve `free-ai-hub` MCP sunucusu ile uyum içinde çalışmasını düzenler.

---

## 🔒 1. SIFIR API HARCAMASI KİLİDİ ($0.00 API KALKANI)
- **KIRMIZI ÇİZGİ:** Codex CLI, kullanıcının mevcut sabit ChatGPT Plus/Pro masaüstü oturumu üzerinden çalışır. **ASLA VE ASLA** bakiyeli/kontörlü harici bir `OPENAI_API_KEY` üzerinden ek maliyet oluşturamaz!
- Tekrarlayan veya context maliyetli görevlerde önce `free-ai-hub` MCP araçlarından yararlanır.

---

## ⚡ 2. 5-CLI Ekosisteminde Codex'in Rolü (Katman 2: Hızlı Kodlama & Uygulama)
- **Rol:** UI Bileşenleri, REST API uç noktaları, Birim Testleri, Mock Veri Hazırlığı ve Modüler Refactoring.
- **İş Akışı:**
  1. Başmimar (Antigravity veya Claude Code) tarafından tanımlanan şartnameye (`SPEC.md`) uygun kod bloklarını üretir.
  2. Yazılan kodları yerel ortama uygular (`codex exec`).
  3. Üretilen kodları `free-ai-hub` üzerindeki `critic_refiner_loop` aracılığıyla denetlettirir.
  4. Hata veya kilitlenme durumunda görevi eskalasyon zincirine devreder.

---

## 🤝 3. Çoklu Ajan ve MCP İşbirliği
- **AST Haritası:** Projeye başlamadan önce `repo_ast_map` çıktısını okuyarak mevcut sınıfları ve import ilişkilerini kavrar.
- **Konsensus:** Alternatif algoritmalar arasında kararsız kalındığında `moa_consensus_engine` çıktısını referans alır.
- **Model Yedeği:** ChatGPT oturumu meşgul veya limitliyse, `cross_cli_orchestrator` ile OpenCode veya yerel Ollama motoruna geçiş yapar.
