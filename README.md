# ⚡ 4K AI WORKSTATION

Yerel modeller (Ollama), abonelik CLI ajanları (Claude Code, Codex, Antigravity, Grok, OpenCode) ve ücretsiz API'ler
arasında kotayı koruyarak yönlendiren; arama, proje, iş ve senkron modüllerini tek yerde toplayan yapay zeka çalışma masası.

| Modül | İçerik |
|---|---|
| 🧠 ENGINE | Donanım/sağlayıcı keşfi, 🟢 Ekonomik · 🔵 Dengeli · 🔴 Tam Güç vitesleri, 429'da 30 dk cooldown ile yedeğe geçiş |
| 🔍 RADAR | Reklamsız web araması, kaynaklı Türkçe derin araştırma raporu, GitHub trend avcısı |
| 📦 PROJECT | Fikirden fizibilite raporu ve biletler; her bilet ayrı `git worktree` |
| 🏢 BUSINESS | Gelir/gider, proje bütçeleri, görevler, token/kota kullanımı |
| 🔄 SYNC | Tailscale cihaz ağı, uzaktan erişim API'si, Google Drive yedekleme/geri yükleme |

## Kurulum

[Releases](https://github.com/kaan4kbulut/4k-ai-workstation/releases) sayfasından işletim sisteminize uygun dosyayı indirin:

| Sistem | Dosya | Kurulum |
|---|---|---|
| Windows | `.exe` veya `.msi` | Çift tıklayın. İmzasız olduğu için SmartScreen uyarısında **Ek bilgi → Yine de çalıştır**. |
| macOS (Apple Silicon) | `.dmg` | Uygulamayı Applications'a sürükleyin. İlk açılışta **sağ tık → Aç**; açılmazsa `xattr -cr "/Applications/4K AI Workstation.app"` |
| Arch Linux | `.pkg.tar.xz` | `sudo pacman -U 4K-AI-Workstation-*.pkg.tar.xz` |
| Ubuntu / Debian | `.deb` | Çift tıklayın ya da `sudo apt install ./4K-AI-Workstation-*.deb` |
| Diğer Linux | `.AppImage` | `chmod +x` ve çalıştırın (libfuse2 gerekir) |

Veriler `~/.4k/` altında tutulur. Google Drive yedeklemesi için uygulamanın SYNC sekmesindeki adımları izleyin.

## Geliştirme

Gereksinimler: [uv](https://docs.astral.sh/uv/), Node.js 22+.

```bash
uv sync && npm install
./4k                 # terminal arayüzü (Textual)
npm run dev          # masaüstü uygulaması
npm test             # testler
npm run dist         # bu işletim sistemi için kurulum dosyaları (dist/)
```

Üç platformun kurulum dosyaları, `v*` etiketi gönderildiğinde GitHub Actions ile üretilip Releases'e eklenir:

```bash
git tag v1.0.1 && git push --tags
```
