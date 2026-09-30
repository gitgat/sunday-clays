"""The local review page for blocks the checks flagged, and applying the decisions saved from it."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import export

ACCEPTED = "accepted"
SKIPPED = "skipped"

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scoresheet review</title>
<style>
body{{font:15px/1.4 system-ui,sans-serif;margin:0 auto;max-width:960px;padding:16px;background:#fafaf7;color:#1c1c1a}}
.card{{border:1px solid #c9c9c0;border-radius:8px;padding:12px;margin:0 0 16px;background:#fff}}
.card img{{max-width:100%;height:auto;border:1px solid #ddd}}
.tot img{{max-height:280px;width:auto}}
.reasons{{color:#8a3b00;font-weight:600}}
.tots label{{display:inline-block;margin:0 8px 4px 0}}
.tots input{{width:3em}}
.bad{{outline:2px solid #b00020}}
.sum{{font-weight:700}}
button.save{{position:sticky;bottom:8px;padding:10px 18px;font-size:16px}}
</style></head><body>
<h1>Scoresheet review</h1>
<p>{count} blocks need a look. Fix the numbers to match the sheet, then choose Accept or Skip. Official scores are never changed.</p>
{cards}
<button class="save" id="save">Save decisions</button>
<script>
const cards = [...document.querySelectorAll('.card')];
function refresh(card) {{
  let sum = 0, ok = true;
  card.querySelectorAll('.tots input').forEach(i => {{
    const v = i.value.trim() === '' ? NaN : Number(i.value);
    const good = Number.isInteger(v) && v >= 0 && v <= Number(i.dataset.max);
    i.classList.toggle('bad', !good);
    ok = ok && good;
    if (good) sum += v;
  }});
  card.querySelector('.sum').textContent = sum;
  card.dataset.valid = ok ? '1' : '0';
}}
cards.forEach(card => {{
  card.querySelectorAll('.tots input').forEach(i => i.addEventListener('input', () => refresh(card)));
  refresh(card);
}});
document.getElementById('save').addEventListener('click', () => {{
  const decisions = [];
  for (const card of cards) {{
    const choice = card.querySelector('input[type=radio]:checked');
    if (!choice) continue;
    if (choice.value === 'accept' && card.dataset.valid !== '1') {{
      alert('Fix the highlighted numbers in ' + card.dataset.id + ' (' + card.dataset.date + ') before accepting.');
      return;
    }}
    decisions.push({{
      date: card.dataset.date, id: card.dataset.id, action: choice.value,
      name: card.querySelector('.name').value.trim(),
      tots: [...card.querySelectorAll('.tots input')].map(i => Number(i.value)),
    }});
  }}
  const blob = new Blob([JSON.stringify({{decisions}}, null, 1)], {{type: 'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'review-decisions.json';
  a.click();
}});
</script></body></html>
"""


def _engines(record: dict[str, Any]) -> str:
    """Which engine read the block and, when there is one, the other engine's reading, so a person can compare."""
    lines = []
    if "claude" in record:  # a Gemma reading was adopted: show what Claude read
        lines.append(f"Claude read: {record['claude']['tots']}, Event Total {record['claude']['event_total']}")
    if "gemma" in record:
        lines.append(f"Gemma read: {record['gemma']['tots']}, Event Total {record['gemma']['event_total']}")
    source = record.get("source")
    if source is None and not lines:
        return ""
    head = f"Read by: {html.escape(str(source or 'gemma'))}."
    return f'<p class="engines">{head} {html.escape("; ".join(lines))}</p>'


def _card(root: Path, out: Path, meta: dict[str, Any], record: dict[str, Any]) -> str:
    esc = html.escape
    rel = (root / "blocks").relative_to(out).as_posix()
    block_id = str(record["id"])
    inputs = "".join(
        f'<label>Stn {stn} (0 to {tgt}) <input type="number" min="0" max="{tgt}" data-max="{tgt}" '
        f'value="{"" if index >= len(record["tots"]) or record["tots"][index] is None else record["tots"][index]}"></label>'
        for index, (stn, tgt) in enumerate(meta["layout"])
    )
    official = (
        "no matching results row"
        if record["official"] is None
        else f"{esc(str(record['matched']))}: {record['official']}"
    )
    options = "".join(f'<option value="{esc(str(row["name"]))}">' for row in meta["officials"])
    name = record["matched"] or record["name_read"]
    return (
        f'<div class="card" data-date="{esc(meta["date"])}" data-id="{esc(block_id)}">'
        f"<h2>Sunday {esc(meta['date'])}, page {record['page']} block {record['block']}</h2>"
        f'<p class="reasons">{esc(", ".join(record["reasons"]))}</p>'
        f'<img src="{esc(rel)}/{esc(block_id)}.png" alt="Scoresheet block">'
        f'<div class="tot"><img src="{esc(rel)}/{esc(block_id)}-tot.png" alt="Tot column"></div>'
        f'<p>Read as "{esc(record["name_read"])}", Event Total written {record["event_total"]}. Official: {official}.</p>'
        f"{_engines(record)}"
        f'<p>Name (as in the official results) <input class="name" list="names-{esc(meta["date"])}" size="28" value="{esc(name)}">'
        f'<datalist id="names-{esc(meta["date"])}">{options}</datalist></p>'
        f'<div class="tots">{inputs}</div>'
        f'<p>Sum <span class="sum">0</span></p>'
        f'<label><input type="radio" name="d-{esc(meta["date"])}-{esc(block_id)}" value="accept"> Accept</label> '
        f'<label><input type="radio" name="d-{esc(meta["date"])}-{esc(block_id)}" value="skip"> Skip</label>'
        "</div>"
    )


def build_review(out: Path) -> tuple[Path, int]:
    """Write out/review.html listing every block still marked review; returns the path and the block count."""
    cards: list[str] = []
    for sunday in sorted((out / "sundays").glob("*/readings.json")):
        root = sunday.parent
        meta = json.loads((root / "sunday.json").read_text())
        for record in json.loads(sunday.read_text()):
            if record["status"] == "review":
                cards.append(_card(root, out, meta, record))
    path = out / "review.html"
    path.write_text(_PAGE.format(count=len(cards), cards="\n".join(cards)))
    return path, len(cards)


def apply_review(out: Path, decisions_file: Path) -> tuple[int, list[str]]:
    """Merge saved decisions into the readings. Returns (decisions applied, problems); a problem skips only its decision."""
    decisions = json.loads(decisions_file.read_text())["decisions"]
    applied = 0
    problems: list[str] = []
    loaded: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for decision in decisions:
        date = str(decision["date"])
        label = f"{date} {decision['id']}"
        root = out / "sundays" / date
        if not (root / "readings.json").exists():
            problems.append(f"{label}: no readings for that Sunday")
            continue
        if date not in loaded:
            loaded[date] = (
                json.loads((root / "sunday.json").read_text()),
                json.loads((root / "readings.json").read_text()),
            )
        meta, readings = loaded[date]
        record = next((r for r in readings if r["id"] == decision["id"]), None)
        if record is None:
            problems.append(f"{label}: no such block")
        elif decision["action"] == "skip":
            record["status"] = SKIPPED
            applied += 1
        elif decision["action"] != "accept":
            problems.append(f"{label}: unknown action {decision['action']!r}")
        else:
            problem = _accept(meta, readings, record, str(decision["name"]), decision["tots"])
            if problem:
                problems.append(f"{label}: {problem}")
            else:
                applied += 1
    for date, (_, readings) in loaded.items():
        (out / "sundays" / date / "readings.json").write_text(json.dumps(readings, indent=1))
    return applied, problems


def _accept(
    meta: dict[str, Any], readings: list[dict[str, Any]], record: dict[str, Any], name: str, tots: object
) -> str:
    """Accept an edited reading if it still passes the range checks; returns the problem, or '' when applied."""
    targets = [pair[1] for pair in meta["layout"]]
    if not isinstance(tots, list) or len(tots) != len(targets):
        return f"needs {len(targets)} station numbers"
    if not all(
        isinstance(t, int) and not isinstance(t, bool) and 0 <= t <= m for t, m in zip(tots, targets, strict=True)
    ):
        return "a station number is outside 0 to its target count"
    rows = [o for o in meta["officials"] if o["name"].casefold() == name.casefold()]
    if not rows:
        return f"'{name}' is not a name in that Sunday's results"
    free = rows
    for other in readings:  # a shooter with two rounds has two rows; each sheet uses up one
        if other is not record and other["status"] in ("ok", ACCEPTED) and other["matched"] == rows[0]["name"]:
            free = _without_one(free, other["official"])
    if not free:
        return f"'{rows[0]['name']}' already has a sheet on that Sunday"
    official = next((o for o in free if o["hits"] == sum(tots)), None)
    if official is None:  # the spreadsheet score is authoritative: the station totals must add up to it
        return export.sum_problem(sum(tots), " or ".join(str(o["hits"]) for o in free))
    record.update(tots=list(tots), sum=sum(tots), matched=official["name"], official=official["hits"], status=ACCEPTED)
    return ""


def _without_one(rows: list[dict[str, Any]], hits: int) -> list[dict[str, Any]]:
    """`rows` less the one a sheet used (the row with its score; if the workbook changed since, the first)."""
    index = next((i for i, row in enumerate(rows) if row["hits"] == hits), 0)
    return rows[:index] + rows[index + 1 :]
