"""build/icon.svg'den uygulama simgelerini üretir: build/icon.png (1024), desktop/assets/icon.png (512)
ve build/icon.ico (16–256 px). ICO, içine PNG gömülmüş standart kap olarak elle yazılır; bazı
ImageMagick sürümleri .ico yerine düz PNG ürettiği için electron-builder onu reddediyordu.

Kullanım: python packaging/make_icons.py   (rsvg-convert gerekir)
"""

from __future__ import annotations

import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "build" / "icon.svg"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int, out: Path) -> bytes:
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), str(SVG), "-o", str(out)], check=True)
    return out.read_bytes()


def write_ico(images: list[tuple[int, bytes]], dest: Path) -> None:
    header = struct.pack("<HHH", 0, 1, len(images))
    entries, blobs = b"", b""
    offset = 6 + 16 * len(images)
    for size, data in images:
        dim = 0 if size >= 256 else size  # 0, ICO biçiminde 256 demektir
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    dest.write_bytes(header + entries + blobs)


def main() -> None:
    render(1024, ROOT / "build" / "icon.png")
    render(512, ROOT / "desktop" / "assets" / "icon.png")
    with tempfile.TemporaryDirectory() as tmp:
        images = [(s, render(s, Path(tmp) / f"{s}.png")) for s in ICO_SIZES]
    write_ico(images, ROOT / "build" / "icon.ico")
    print("✓ build/icon.png, desktop/assets/icon.png, build/icon.ico")


if __name__ == "__main__":
    main()
