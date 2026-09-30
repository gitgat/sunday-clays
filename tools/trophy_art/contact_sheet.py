"""HTML contact sheet of candidates (out/candidates/<stem>/<seed>.png) for the user to pick from."""

from __future__ import annotations

import html
from pathlib import Path

from manifest import split_stem

_HEAD = (
    "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Trophy candidates</title>"
    "<style>body{background:#1A4D2E;color:#FEFBF6;font-family:Roboto,sans-serif;margin:24px}"
    ".grid{display:flex;flex-wrap:wrap;gap:16px}figure{margin:0;width:192px}"
    "img{border-radius:50%;background:#2D5F3F}figcaption{font-size:12px;word-break:break-all}</style>"
    "</head><body><h1>Trophy candidates</h1>"
)
_TAIL = "</body></html>\n"


def build_sheet(candidates_dir: Path) -> str:
    sections: list[str] = []
    for target in sorted(p for p in candidates_dir.iterdir() if p.is_dir()):
        art_key, metal = split_stem(target.name)
        figures: list[str] = []
        for png in sorted(target.glob("*.png"), key=lambda p: int(p.stem)):
            command = f"python cli.py select {art_key} {metal or '-'} {png.stem}"
            src = html.escape(f"candidates/{target.name}/{png.name}")
            figures.append(
                f"<figure><img src='{src}' width='192' height='192' alt=''>"
                f"<figcaption>seed {html.escape(png.stem)} · <code>{html.escape(command)}</code></figcaption></figure>"
            )
        sections.append(
            f"<section><h2>{html.escape(target.name)}</h2><div class='grid'>{''.join(figures)}</div></section>"
        )
    return _HEAD + "\n".join(sections) + _TAIL
