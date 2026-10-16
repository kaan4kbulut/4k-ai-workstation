#!/usr/bin/env bash
# Linux (Arch gibi deb tabanlı olmayan dağıtımlar dahil): derlenmiş uygulamayı kullanıcıya kurar,
# uygulama menüsü girdisi ve masaüstü simgesi oluşturur. Root gerektirmez.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNPACKED="$ROOT/dist/linux-unpacked"
if [ ! -x "$UNPACKED/4k-ai-workstation" ]; then
  echo "Derlenmiş uygulama bulunamadı. Önce: npm run dist:linux" >&2
  exit 1
fi

# AppImage yerine açılmış klasör kurulur: FUSE (libfuse2) gerektirmez ve daha hızlı açılır.
DEST="$HOME/.local/share/4k-ai-workstation"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
APPS="$HOME/.local/share/applications"
mkdir -p "$ICON_DIR" "$APPS" "$HOME/.local/bin"

rm -rf "$DEST.new"
cp -a "$UNPACKED" "$DEST.new"
rm -rf "$DEST"
mv "$DEST.new" "$DEST"
install -m 644 "$ROOT/desktop/assets/icon.png" "$ICON_DIR/4k-ai-workstation.png"
ln -sf "$DEST/4k-ai-workstation" "$HOME/.local/bin/4k-ai-workstation"

ENTRY="[Desktop Entry]
Type=Application
Name=4K AI Workstation
Comment=Yapay zeka çalışma masası
Exec=$DEST/4k-ai-workstation %U
Icon=4k-ai-workstation
Terminal=false
Categories=Development;
StartupWMClass=4k-ai-workstation"

printf '%s\n' "$ENTRY" > "$APPS/4k-ai-workstation.desktop"
chmod +x "$APPS/4k-ai-workstation.desktop"

DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ] && [ "$DESKTOP_DIR" != "$HOME" ]; then
  cp "$APPS/4k-ai-workstation.desktop" "$DESKTOP_DIR/"
  chmod +x "$DESKTOP_DIR/4k-ai-workstation.desktop"
  echo "✓ Masaüstü simgesi: $DESKTOP_DIR/4k-ai-workstation.desktop"
fi
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" >/dev/null 2>&1 || true

echo "✓ Kuruldu: $DEST"
echo "✓ Uygulama menüsü: 4K AI Workstation  ·  Terminal: 4k-ai-workstation"
