#!/usr/bin/env python3
"""Gzip size of every built JS chunk for the bundle budgets (C11). Standard library only.

entry_js_gz_kb = the Vite entry chunk(s) plus every chunk they import statically (the JS a
first page load must fetch); total_js_gz_kb = every dist/assets/*.js.
"""

import argparse
import gzip
import json
import sys
from collections.abc import Sequence
from pathlib import Path


def gzip_bytes(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9, mtime=0))


def entry_files(manifest: dict[str, dict[str, object]]) -> set[str]:
    """Output files of the entry chunks and their static-import closure."""
    pending = [key for key, chunk in manifest.items() if chunk.get("isEntry") is True]
    seen_keys: set[str] = set()
    files: set[str] = set()
    while pending:
        key = pending.pop()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        chunk = manifest[key]
        file = str(chunk["file"])
        if file.endswith(".js"):
            files.add(file)
        imports = chunk.get("imports", [])
        if isinstance(imports, list):
            pending.extend(str(item) for item in imports)
    return files


def bundle_stats(dist: Path) -> dict[str, object]:
    manifest = json.loads((dist / ".vite" / "manifest.json").read_text(encoding="utf-8"))
    sizes = {f"assets/{p.name}": gzip_bytes(p) for p in sorted((dist / "assets").glob("*.js"))}
    entries = entry_files(manifest)
    if not entries:
        raise ValueError(f"no entry chunk in {dist / '.vite' / 'manifest.json'}")
    missing = sorted(entries - sizes.keys())
    if missing:
        raise ValueError(f"manifest names chunks missing from dist/assets: {missing}")
    return {
        "entry_js_gz_kb": round(sum(sizes[f] for f in entries) / 1024, 2),
        "total_js_gz_kb": round(sum(sizes.values()) / 1024, 2),
        "chunks": {name: round(size / 1024, 2) for name, size in sizes.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--out", type=Path, default=Path("bundle-stats.json"))
    args = parser.parse_args(argv)
    try:
        stats = bundle_stats(args.dist)
    except (OSError, ValueError, KeyError) as exc:
        print(f"bundle_stats: {exc}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"entry_js_gz_kb={stats['entry_js_gz_kb']} total_js_gz_kb={stats['total_js_gz_kb']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
