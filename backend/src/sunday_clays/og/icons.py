"""Write the PWA icons from the mark: ``uv run python -m sunday_clays.og.icons <folder>`` (D9)."""

import argparse
from pathlib import Path
from typing import Final

from PIL import Image

from sunday_clays.og.logo import GREEN, draw_mark

#: file name -> (size in px, maskable: full-bleed green with the mark inside the 80% safe zone)
ICONS: Final[dict[str, tuple[int, bool]]] = {
    "icon-192.png": (192, False),
    "icon-512.png": (512, False),
    "maskable-512.png": (512, True),
    "apple-touch-icon.png": (180, True),  # iOS rounds the corners itself
    "favicon-32.png": (32, False),
}


def _icon(size: int, maskable: bool) -> Image.Image:
    if not maskable:
        return draw_mark(size)
    canvas = Image.new("RGBA", (size, size), GREEN)
    inner = round(size * 0.8)
    offset = (size - inner) // 2
    mark = draw_mark(inner, background=False)
    canvas.alpha_composite(mark, (offset, offset))
    return canvas


def write_icons(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (size, maskable) in ICONS.items():
        path = out_dir / name
        _icon(size, maskable).save(path, format="PNG")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the Sunday Clays PWA icons.")
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    for path in write_icons(args.out_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
