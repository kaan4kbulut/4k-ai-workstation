"""
4K AI WORKSTATION - Usage CLI
Kullanıcı 'usage' yazdığında ekrana Günlük, Haftalık, Aylık tüm kullanım,
tasarruf ve ajan dağılımını zengin markdown olarak basar.
"""

import sys
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.usage_tracker import UsageTracker


def main():
    # Windows konsolunda UTF-8 çıktısı sağlamak için
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    tracker = UsageTracker()
    markdown_output = tracker.format_all_in_one_markdown(include_antigravity=True)
    print(markdown_output)


if __name__ == "__main__":
    main()
