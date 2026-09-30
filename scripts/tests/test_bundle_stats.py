import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bundle_stats.py"


def build_dist(root: Path) -> Path:
    """A fake Vite dist: entry -> static shared chunk; a lazy route chunk; a CSS file."""
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / ".vite").mkdir()
    (dist / "assets" / "index-a1.js").write_bytes(os.urandom(20 * 1024))
    (dist / "assets" / "shared-b2.js").write_bytes(os.urandom(10 * 1024))
    (dist / "assets" / "HomePage-c3.js").write_bytes(b"a" * 200_000)
    (dist / "assets" / "index-d4.css").write_bytes(os.urandom(50 * 1024))
    manifest = {
        "index.html": {
            "file": "assets/index-a1.js",
            "isEntry": True,
            "imports": ["_shared-b2.js"],
            "dynamicImports": ["src/features/home/pages/HomePage.tsx"],
            "css": ["assets/index-d4.css"],
        },
        "_shared-b2.js": {"file": "assets/shared-b2.js", "imports": ["index.html"]},
        "src/features/home/pages/HomePage.tsx": {
            "file": "assets/HomePage-c3.js",
            "isDynamicEntry": True,
            "imports": ["index.html", "_shared-b2.js"],
        },
    }
    (dist / ".vite" / "manifest.json").write_text(json.dumps(manifest))
    return dist


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_entry_counts_entry_and_static_imports_but_not_lazy_chunks(tmp_path: Path) -> None:
    dist = build_dist(tmp_path)
    out = tmp_path / "bundle-stats.json"

    result = run(f"--dist={dist}", f"--out={out}")

    assert result.returncode == 0, result.stderr
    stats = json.loads(out.read_text())
    assert 30.0 <= stats["entry_js_gz_kb"] <= 30.2
    assert stats["total_js_gz_kb"] - stats["entry_js_gz_kb"] < 1.0
    assert stats["chunks"]["assets/HomePage-c3.js"] < 1.0
    assert "assets/index-d4.css" not in stats["chunks"]


def test_manifest_without_an_entry_is_an_error(tmp_path: Path) -> None:
    dist = build_dist(tmp_path)
    (dist / ".vite" / "manifest.json").write_text(json.dumps({"x.js": {"file": "assets/x.js"}}))

    result = run(f"--dist={dist}", f"--out={tmp_path / 'o.json'}")

    assert result.returncode == 2
    assert "no entry chunk" in result.stderr


def test_manifest_naming_a_missing_chunk_is_an_error(tmp_path: Path) -> None:
    dist = build_dist(tmp_path)
    (dist / "assets" / "shared-b2.js").unlink()

    result = run(f"--dist={dist}", f"--out={tmp_path / 'o.json'}")

    assert result.returncode == 2
    assert "assets/shared-b2.js" in result.stderr


def test_missing_dist_is_an_error(tmp_path: Path) -> None:
    result = run(f"--dist={tmp_path / 'nope'}", f"--out={tmp_path / 'o.json'}")

    assert result.returncode == 2
    assert "bundle_stats:" in result.stderr
    assert "nope" in result.stderr
