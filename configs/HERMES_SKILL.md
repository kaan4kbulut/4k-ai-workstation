# Hermes Skill - 4K Workstation Entegrasyon Yeteneği (HERMES_SKILL.md)

---
name: nexus-workstation
description: 4K AI WORKSTATION REST API ve free-ai-hub MCP sunucusuna erişim sağlayan otonom yetenek.
---

# 🚀 Nexus Workstation Orchestrator Skill

Bu yetenek, Hermes CLI'ın (`hermes`) yerel 4K AI WORKSTATION sunucusu (`http://127.0.0.1:8000`) ve `opencode_free_hub_mcp.py` MCP araçları ile etkileşime girmesini sağlar.

## 📡 Desteklenen Uç Noktalar

1. **Sorgu ve Eskalasyon:**
   - `POST http://127.0.0.1:8000/query`
   - Gövde:
     ```json
     {
       "prompt": "Görevin detaylı açıklaması",
       "model": "auto",
       "parallel": true,
       "synthesize": true
     }
     ```

2. **Donanım ve VRAM Durumu:**
   - `GET http://127.0.0.1:8000/hardware/info`
   - CPU çekirdekleri, sistem RAM'i ve GPU VRAM kapasitesini döndürür.

3. **5-CLI Sağlık Raporu:**
   - `GET http://127.0.0.1:8000/scout/report?include_online=true`
   - Tüm CLI ajanlarının sağlık durumunu ve güncel açık kaynak AI trendlerini listeler.

4. **Katalog ve Önerilen Modeller:**
   - `GET http://127.0.0.1:8000/librarian/catalog?only_free=true`
   - Sıfır maliyetli bulut ve yerel modelleri listeler.

## 💡 Kullanım Kalıpları
Hermes, ağır kodlama veya mimari gerektiren bir görev aldığında:
1. İsteği `/query` uç noktasına `model="auto"` ile iletir.
2. İş istasyonunun otomatik eskalasyon ve MoA sentezleyicisinden gelen nihai yanıtı kullanıcıya sunar.
