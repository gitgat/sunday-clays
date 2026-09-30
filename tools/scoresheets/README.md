# scoresheets

Dev-only tool that backfills station-level scores from the weekly "Sunday Clays Update" PDFs using a local
vision model. The app and CI never call the model, and nothing here is shipped in an image (`tools/` is in
`.dockerignore`). PDFs, block images, model replies and workbooks contain member names, so everything is
written under the gitignored `out/` folder. Never commit any of it.

Needs `pdftotext` and `pdftoppm` (poppler) and a local OpenAI-compatible model server (Unsloth Studio).

```sh
cd tools/scoresheets
uv sync
export VLM_API_KEY=...   # the local server's bearer token
uv run cli.py run "/path/to/2026-05-31 Sunday Clays Update.pdf"
```

Steps (each also runs alone; all take `--out DIR`, default `out/`):

| command | does |
| --- | --- |
| `scan PDF...` | dedupes by Sunday date, parses the typed results and course, cuts the six blocks per scoresheet page |
| `read [--jobs N] [--date D]` | reads each block (name, Tot column, Event Total), retries, checks; responses cached in `out/cache` |
| `review` | writes `out/review.html` for every flagged block; "Save decisions" downloads `review-decisions.json` |
| `apply-review FILE` | merges saved decisions (range checks still apply, and an accepted shooter's station totals must add up to their spreadsheet score) |
| `export` | `out/stations_backfill.xlsx` (ok and accepted shooters whose station totals equal their spreadsheet score), `out/report.csv`, `out/presentations.json` |
| `verify` | runs the backend station parser on the workbook; fails on any ERROR finding |
| `run PDF...` | scan, read, export and the review page, then a summary |

`--skip-date YYYY-MM-DD` (scan, run) leaves out a Sunday that was not held. 2025-11-16 (a PDF but no scores) is
always skipped.

Official scores come from the scores workbook: `--scores FILE` (a global option, before the command) reads its
"ALL SCORE DETAIL" sheet (Name, Score Shot, Event), and those rows, names exactly as in the workbook, are the
official results for their Sunday. A shooter with two rounds has two rows and their sheets match one each. Without
`--scores` the backend test fixture is used when it exists. The typed results table is only a fallback for a Sunday
the workbook has no rows for.

When the PDF has no typed course sheet (the course is a picture), `read` finds the course page (the page after
the results), asks the model for the stations and targets, and accepts the answer only if the targets add up to 50
and the station labels are distinct (3 tries). Otherwise the Sunday is `course_unreadable` and is left out. A Sunday
with no course at all (no typed sheet and no course picture) is left out as `no_course`; both show in `report.csv`
as `sunday_skipped` and in the export summary.

A station label may carry a letter: a course with both 7 and 7A has two separate stations, 7A sorts after 7, and
both are read, checked and exported (the station workbook's `STATION #` header row holds `7` and `7A`; the app's
parser keeps them as separate stations).

**The scores spreadsheet is authoritative.** A shooter's station totals must add up exactly to their spreadsheet
(official) score. `apply-review` refuses to accept a decision that does not ("station totals add to N, spreadsheet
score is M"), and `export` leaves such a shooter out of the workbook, reports them as `sheet_vs_official` in
`report.csv` and prints the same message.

The course page is the first page after the results with a little typed text (the footer). A page with no text
at all is a blank scoresheet, never the course.

A sheet that adds up to its own written Event Total but differs from the official score goes straight to review
(`sheet_vs_official`) without retries; it can only leave review by being edited so it adds up to the official score
(or skipped). Decisions kept across re-reads are tied to the source PDF's sha256: if a
Sunday is re-scanned from a different PDF, its kept decisions are dropped and its blocks read again. Decisions
saved before shas were stored get the current sha on the next `read`. `export` leaves out (and reports as
`stale`) any reading taken from a different PDF than the one now scanned.

## Claude engine (`--engine claude`)

`uv run cli.py --engine claude run "<pdf>"` (or `read`) reads each scoresheet PAGE with one call to the local
`claude` CLI in print mode with NO tools (`claude -p --model opus --input-format stream-json --output-format
stream-json --verbose --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}' --setting-sources ""`),
using your Claude subscription. The page image goes in inline as base64 on stdin (one stream-json user message),
the call runs in an empty temp folder, and the model has no Read tool or file path. Each call's `total_cost_usd`
is kept in its cache entry and the summed cost is printed at the end of `read`. Only the CLI is used: no
Anthropic API calls, no API keys. `CLAUDE_BIN` sets the path to the
CLI (default `claude`); `--claude-model` picks the model (default `opus`); `--jobs N` reads N pages at once
(default 4 for Claude, 1 for Gemma). The default engine stays `gemma`. Options go before the command.

- `scan` now also keeps each whole scoresheet page as `out/sundays/<date>/pages/pN.png`. A scan made before this
  needs `scan` run again; `read --engine claude` says so and stops.
- The reply's `slot` 1..6 is the block id `pN-b<slot>` (left to right, then top to bottom, the same order as the
  block crops). A slot Claude leaves out is a blank block.
- Replies are cached under `out/claude-cache` by sha256 of the page image, prompt, model and attempt, so a rerun
  is free. A reply that is not usable page JSON is dropped from the cache (so a rerun asks again). A bad reply is
  retried once; a page that still fails marks its blocks `review` with reason
  `engine_error`. The course picture, when there is no typed course sheet, is read the same way (one call, same
  50-target rule). The end of `read` prints calls, cached calls and the summed `total_cost_usd`.
- The station numbers Claude reads in the Stn column must match the course; a different one gives the block
  `station_mismatch` for review. A `not logged in` result stops the run (exit 2) whatever the CLI's exit code.
- The same checks apply. Second opinion: when a Claude reading fails the checks and an earlier Gemma reading of
  the block is cached in `out/cache` (the server is never called) and passes every check, it is adopted only if
  its Event Total equals Claude's (`source` `gemma_second_opinion`). When both pass but differ on any station the
  block is `review` with reason `engines_disagree`, and `review.html` shows both readings. `report.csv` has a
  `source` column (`claude`, `gemma`, `gemma_second_opinion`).

Official scores are never changed. A sheet that is self-consistent but differs from the official score is
flagged `sheet_vs_official` for a person to decide.

Environment: `VLM_URL` (default `http://127.0.0.1:8888/v1/chat/completions`), `VLM_MODEL` (default
`unsloth/gemma-4-26B-A4B-it-GGUF`), `VLM_API_KEY`. Requests always send `enable_thinking: false`.

Re-running `read` keeps blocks you already accepted or skipped in review (they are not read again).

Tests: `uv run pytest` (no network, no model). One test runs the real backend station parser on an exported
workbook; it needs `backend/` and `uv` and is skipped without them (CI runs it).
