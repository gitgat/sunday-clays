"""Build an out/ folder with one read Sunday, as scan + read would leave it."""

import json
from pathlib import Path

from PIL import Image

OFFICIALS = [
    {"name": "Testerson, Ann", "hits": 22, "note": None, "gauge": None},
    {"name": "Fakeman, Bo", "hits": 21, "note": None, "gauge": None},
    {"name": "Mockley, Cy", "hits": 20, "note": None, "gauge": "28 Gauge"},
]


def record(block, name_read, matched, official, tots, status, reasons=(), event_total=None):
    return {
        "id": f"p6-b{block}",
        "page": 6,
        "block": block,
        "name_read": name_read,
        "tots": tots,
        "event_total": sum(t or 0 for t in tots) if event_total is None else event_total,
        "malf": "",
        "tries": 1,
        "matched": matched,
        "official": official,
        "sum": sum(t or 0 for t in tots),
        "status": status,
        "reasons": list(reasons),
    }


def make_out(tmp_path: Path, iso="2026-05-31", readings=None) -> Path:
    out = tmp_path / "out"
    root = out / "sundays" / iso
    (root / "blocks").mkdir(parents=True)
    readings = (
        [
            record(1, "Ann Testerson", "Testerson, Ann", 22, [7, 7, 8], "ok"),
            record(2, "Bo Fakeman", "Fakeman, Bo", 21, [7, 7, 3], "review", ["sheet_vs_official"]),
            record(3, "Cy Mocklee", "Mockley, Cy", 20, [7, None], "review", ["station_count", "tot_missing"], 14),
            record(4, "Nobody <b>", None, None, [1, 1, 1], "review", ["no_official_match"]),
        ]
        if readings is None
        else readings
    )
    meta = {
        "date": iso,
        "layout": [[2, 7], [4, 7], [7, 8]],
        "presentations": {"2": [{"reps": 1, "presentation": "SINGLE", "traps": "A", "targets": 1}]},
        "officials": OFFICIALS,
        "blocks": [r["id"] for r in readings] + ["p6-b5"],
    }
    (root / "sunday.json").write_text(json.dumps(meta))
    (root / "readings.json").write_text(json.dumps(readings))
    for r in readings:
        for suffix in ("", "-tot"):
            Image.new("RGB", (4, 4), "white").save(root / "blocks" / f"{r['id']}{suffix}.png")
    return out
