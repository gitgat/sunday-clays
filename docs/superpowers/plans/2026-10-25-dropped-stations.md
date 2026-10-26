# Thrown-out Stations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect a thrown-out station on its own, keep that Sunday's official results counting with a `*`, and keep the free targets out of every score and station statistic, with every affected explainer saying so.
**Architecture:** Migration 0010 adds `events.stats_excluded` and `station_layouts.dropped`/`dropped_source`. `rebuild_live` sets them from a pure detector in `domain/thrown_out.py` plus a `station_drop` admin rule. The flags flow through the shared frames (`stat_rounds`, `stat_events`, `live_station_hits`, `load_thrown_out`) to each consumer, which filters per its class (counts / score stats / station stats). The API exposes an explicit `stats_excluded`/`thrown_out`/`dropped`/`n_excluded`, and the frontend draws the `*`, hollow points, a `thrown_out` CSV column and explainer lines from shared helpers.
**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / Alembic / pandas (uv, pytest, ruff, mypy --strict); React + TypeScript + ECharts (pnpm, Vitest, MSW, Playwright); Postgres; Docker multi-arch images.
**Spec:** docs/superpowers/specs/2026-10-25-dropped-stations-design.md (appendix: 2026-10-25-dropped-stations-inventory.md)

## Global Constraints

- TDD on every task: write the test, run it, paste the RED output, implement, paste the GREEN output. No implementation before a pasted RED.
- Reviewers re-run each task's new tests on the task's base commit to prove they fail there. Tests marked **guard** pin behaviour that must not change and are expected to pass on base.
- Never edit `ratchets/`. `git diff --quiet origin/main -- ratchets/` must exit 0 at the end.
- Invented names only in tests, fixtures and copy (e.g. "Hadley, Ike", "Ace, Amy"); never a real name.
- User copy uses neutral pronouns (never he/she/his/her) and no "class"/"event" where the explainer and insight lints ban it; server copy says "a station thrown out", never "drop"/"dropped".
- Migration 0010 is expand-only: new columns with server defaults, no NOT NULL change to existing columns, so the previous release keeps running during rollout.
- Multi-arch images (amd64 + arm64) are built by CI as today; no Dockerfile, compose or volume change.
- Conventional Commits; every commit message ends with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `openapi.json` and `frontend/src/api/schema.d.ts` are gitignored: regenerate with `pnpm gen:api` (from local backend source; `pnpm typecheck` runs it) and never `git add` them.
- One owner per edit: the ownership notes in the contract are binding. A task that finds it needs another task's edit stops and reports instead of duplicating it.
- Backend gate after every backend task: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src`. Frontend gate after every frontend change: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`.

### Interface contract

Branch feat/dropped-stations. Spec: docs/superpowers/specs/2026-10-25-dropped-stations-design.md. Inventory: docs/superpowers/specs/2026-10-25-dropped-stations-inventory.md. Plan: docs/superpowers/plans/2026-10-25-dropped-stations.md.

Where this contract and the spec differ, the contract wins (recap line, Sunday banner, `RecapOut.thrown_out` type, no `stats_excluded` on `PbOut`/`RecordRoundOut`).

#### Backend

##### Schema (T1a) — `backend/migrations/versions/0010_thrown_out_stations.py`, `revision = "0010"`, `down_revision = "0009"`, expand-only
- `station_layouts.dropped BOOLEAN NOT NULL DEFAULT false`
- `station_layouts.dropped_source TEXT NULL`, CHECK `ck_station_layouts_dropped_source`: `dropped_source IN ('auto','override')`
- `events.stats_excluded BOOLEAN NOT NULL DEFAULT false`
- ORM (`models/live.py`): `Event.stats_excluded: bool`, `StationLayout.dropped: bool`, `StationLayout.dropped_source: str | None`

##### Detection and copy (T1b) — `backend/src/sunday_clays/domain/thrown_out.py` (stdlib only)
```python
MIN_DROP_ENTRIES: Final = 8          # the one documented place for the threshold
SUNDAY_THROWN_OUT: Final = "A station was thrown out this Sunday"

@dataclass(frozen=True)
class ThrownOut:
    station_label: str | None      # None = Sunday-level override
    target_count: int | None       # None when station_label is None
    credited: bool                 # entries exist and every entry has hits == target_count
    source: Literal["auto", "override"]

def detect_thrown_out(
    hits: Mapping[tuple[date, str], Sequence[int]],               # every entry's hits, linked or not
    target_counts: Mapping[tuple[date, str], int],                 # insertion order = layout order
    overrides: Mapping[tuple[date, str | None], tuple[int, bool]], # ActiveRules.station_drops
    special_dates: Collection[date],
) -> dict[date, tuple[ThrownOut, ...]]

def thrown_out_phrase(items: Sequence[ThrownOut]) -> str
```
Rules:
- Auto: `len(entries) >= MIN_DROP_ENTRIES` and every entry `== target_count` (an entry is one sheet row, so a second-round row counts as its own entry).
- Special dates are skipped entirely: no auto item, and overrides on them produce nothing (rebuild reports them).
- Override `(d, label) -> (rule_id, True)` forces the station on (source `override`, `credited` computed from the hits; no entries means `credited=False`); `(d, label) -> (rule_id, False)` forces it off.
- A station override whose label is not in that date's layout produces no item.
- `(d, None) -> (rule_id, True)` appends `ThrownOut(None, None, False, "override")` after the station items.
- Return: ascending dates, only dates with ≥ 1 item; station items in layout order, the Sunday-level item last.

##### Copy — exact strings (backend `thrown_out_phrase` and frontend `thrownOutPhrase` MUST return identical text)
- one station, credited: `Station 11 was thrown out; everyone was credited 7/7`
- one station, not credited: `Station 11 was thrown out`
- several stations (labels in order, no Oxford comma): `Stations 4 and 11 were thrown out`, `Stations 3, 4 and 11 were thrown out`; if ALL listed stations are credited append `; everyone was credited in full`
- Sunday-level item only, or an empty list: `A station was thrown out this Sunday` (`SUNDAY_THROWN_OUT`)
- Sunday-level item together with station items: ignore the Sunday-level item
- Recap email line: `{phrase}, so this week's scores aren't used in averages, PBs or station stats.`
- ClaySmasher Notes: the phrase as-is, between the source note and the class: `Imported from Sunday Clays; <phrase>; class: <gauge>`
- Sunday-page banner (`thrownOutBanner`): `{phrase}. Today's results and standings count, marked *. These scores are left out of averages, PBs and station stats.`
- DataIssue (rebuild): `Station {label} on {d} looks thrown out (every shooter perfect). It's marked * and left out of stats. Override in Rules if that's wrong.`
- Preview finding: `Station {label} on {d} looks thrown out (every shooter perfect). It will be marked * and left out of stats. Override in Rules if that's wrong.`
- Server copy (insight headlines, how bullets) never contains `*` or a star glyph and never "drop"/"dropped"/"event"; say "a station thrown out".

##### Rules (T1a) — `domain/rules.py`
- `RuleType.STATION_DROP = "station_drop"`
- `class StationDropPayload(_Payload): event_date: date; station_label: str | None = None; dropped: bool`. A label is normalized with `parse_label` (`" 7a "` → `"7A"`); a non-label raises `"{label!r} is not a station number or label like 7A"`; `station_label is None and dropped is False` raises `"A Sunday-level rule can only mark a Sunday as thrown out"`. No reason field.
- `ActiveRules.station_drops: dict[tuple[date, str | None], tuple[int, bool]]` (last field; newest active rule wins per key).

##### Rebuild (T1c) — `domain/rebuild.py`
- `_staged_station_hits(session, sources) -> dict[tuple[date, str], list[int]]` from `ImportStationHit` (every entry, linked or not).
- `rebuild_live`: `thrown_out = detect_thrown_out(station_hits, target_counts, rules.station_drops, specials.keys())`; `overridden = {(d, label) with a station rule on a regular Sunday whose label is in the layout}`.
- `_write_events(..., thrown_out: Mapping[date, tuple[ThrownOut, ...]] | None = None)` sets `stats_excluded = d in (thrown_out or {})` and reports unmatched `station_drop` rules as `rule_target_missing` (warning), details `{rule_id, event_date, station_label, dropped}`:
  - station: `Rule {id} targets Station {label} on {d}, which has no such station on a regular Sunday`
  - Sunday-level, or any rule on a special date: `Rule {id} marks {d} as thrown out, which has no regular Sunday`
- `_write_station_data(..., thrown_out=None, overridden: AbstractSet[tuple[date, str]] = frozenset())`: `dropped = label in that date's items`; `dropped_source = 'override'` if `(d, label) in overridden` (a station forced off stores `dropped=False, dropped_source='override'`), else `'auto'` if dropped, else NULL. The `StationLayout` insert uses `render_nulls=True` (one statement).
- DataIssue `station_thrown_out`, severity `info`, `event_date=d`, details `{"station_label", "n_entries", "target_count"}` — only for `source == "auto"` items.
- Import preview finding `station_dropped`, `Severity.INFO`, `sheet` = tab name, auto detection only (no overrides: importing rules into `imports.py` is circular). Code in `domain/imports.py:PREVIEW_STATION_CODES` and frontend `admin/components/FindingsList.tsx:STATION_CODES` (both owned by T1c).

##### Frames (T2a) — `analytics/frames.py`
- `ROUND_COLUMNS += "stats_excluded"` (SQL `e.stats_excluded`), `EVENT_COLUMNS += "stats_excluded"` (`_EVENTS_SQL` and `_CALENDAR_SQL`; `CALENDAR_COLUMNS` inherits), `STATION_HIT_COLUMNS += "dropped"` (SQL `l.dropped` in `_STATION_HITS_SQL` **and** `_SPECIAL_STATION_HITS_SQL`); all bool-cast.
- `stat_rounds(rounds)`, `stat_events(events)`, `live_station_hits(hits) -> pd.DataFrame`: keep rows where `~df[col].eq(True)`; NaN counts as kept; a frame without the column is returned unchanged.
- `calendar_from_events` sets `stats_excluded = False` when the input lacks it; `appearances_from_rounds` is unchanged (attendance never carries the flag).
- `load_thrown_out(session: Session) -> dict[date, tuple[ThrownOut, ...]]`, `@cached_by_data_version`, regular Sundays only:
  - station item per dropped layout: `ThrownOut(label, target_count, credited=n_hits > 0 and all(hits == target_count), source=dropped_source or "auto")`, layout order
  - Sunday-level item `ThrownOut(None, None, False, "override")` only for a `stats_excluded` Sunday with no dropped layout
  - dates ascending
- Test builders: `build_rounds`/`make_rounds` and `build_events`/`make_events` default `stats_excluded=False`; `LiveSeed.event(..., stats_excluded: bool = False)` (T2a owns; T6b reuses).

##### Skill and metrics (T2c)
- `skill._prepare` and `steps/s30_skill.py` burn-in treat `held & ~stats_excluded.eq(True)` as held for the model only (no update, state carried, `expected`/`residual`/`difficulty` NaN).
- `metrics.compute_round_metrics` keeps `field_median`, `event_rank`, `percentile`, `is_best_round`; sets `adjusted = NaN` where `stats_excluded`. `event_metrics` n/median/mean/top_score stay whole.

##### Duplicate SQL readers (one owner each)
| Reader | Change | Owner |
|---|---|---|
| `stations._FRAME_SQL`, `STATION_FRAME_COLUMNS += "dropped"`, `load_station_frame` | returns live rows only (`dropped` bool column kept, all False), `sheet_total` summed after the drop; `/api/stations/{label}` 404s (`station_not_found`) for a label seen only thrown out, with no route change | T4a |
| `achievements/context._STATION_SQL`, `STATION_COLUMNS += "dropped"`, `station_frame` | `load_station_entries` unfiltered; `AchContext.from_frames` applies `live_station_hits` (covers s50 and `insights/trophies._next_trophy`) | T4c |
| `weather_effects._WEATHER_EVENTS_SQL`, `_EVENT_COLUMNS += "stats_excluded"` | `WeatherEvent.stats_excluded` | T3c |
| `yir._EVENTS_SQL`, `_EVENT_COLUMNS += "stats_excluded"` | | T3d |
| `predictions._scored_events` | **unchanged**: attendance probabilities keep counting a thrown-out Sunday; skill-based predictions are excluded through the skill change | — |
| `claysmasher._STATIONS_SQL` | **unchanged**: the export stays as recorded; Notes come from `load_thrown_out` | — |

##### Achievements (T4b) — `AchContext.shooter_days` columns, in this order
`shooter_id, event_ts, event_date, stats_excluded, n_rounds, day_best, day_sum, best_round_id, n_events, cum_rounds, cum_sum, prior_rounds, prior_n_s, prior_sum_s, prior_best_s, prev_ts, prev_day_best_s`
- `stats_excluded` bool (day-level any); `prior_n_s`/`prior_sum_s` int64 over earlier non-excluded days; `prior_best_s`/`prev_day_best_s` float64 (best of earlier non-excluded days / of the last such day).
- **Removed:** `prior_sum`, `prior_best`, `prev_day_best`. `n_rounds`/`cum_rounds`/`cum_sum`/`prior_rounds`/`n_events` span all rounds.
- `CtxBuilder.event(day, stats_excluded=...)` (default False, copied onto rounds); `CtxBuilder.station(..., dropped=False)` (T4c).

##### Insights (T5a–T5e)
- `insights/context.Day`: add `stats_excluded: bool = False`, `prior_n_s: int`, `prior_sum_s: int`, `prior_best_s: int | None`, property `prior_mean_s = prior_sum_s / prior_n_s if prior_n_s else None`. **Removed:** `prior_best`, `prior_sum`, property `prior_mean`. `prior_rounds`, `targets`, `k`, `rounds_through` stay all-rounds. `pf.targets-milestone` reads `d.targets - sum(d.scores)` (clays broken before the day, all rounds).
- `Sunday.stats_excluded: bool = False`; `InsightFrames.scored_histories: Mapping[int, tuple[Day, ...]]`, `InsightFrames.scored_sundays: tuple[Sunday, ...]` (cached); `scored_only(days) -> tuple[Day, ...]`; `anchor_days(fr, scope, *, scored=False)`, `evergreen_days(fr, scope, *, scored=False)` (activity gates on every round, yields scored days); `streaks.run_facts(..., scored=False)`.
- `templates.THROWN_OUT_ROUNDS_HOW` = `Sundays with a station thrown out (marked *) are left out.` and `templates.THROWN_OUT_STATION_HOW` = `A station thrown out on the day is left out.` (these two how lines are the only server text allowed to quote the client's `*`, because they describe it); `templates.THROWN_OUT_RECAP_HOW` = `A station was thrown out this Sunday. Its results count; its scores stay out of averages and PBs.`
- New how keys: `pf.first-since["score"]`, `ev.new-faces["strong"]`; `home.sunday-recap` variant `flags + "x"` on a thrown-out Sunday (same headline, how ends with `THROWN_OUT_RECAP_HOW`).
- `anchors.trend_rows` gains `thrown_out: bool`; on such a row `score/adjusted/pb/so_far/roll10/roll20` are None. `proof.py` unchanged.
- Recap facts (T5e): station feats/course stations use `live_station_hits`; `scores_context`/`improvement` say nothing on, and skip, a thrown-out Sunday.

##### Analytics area fields
- `leaderboards.SCORE_STAT_METRICS = frozenset({AVG_SCORE, AVG_ADJUSTED, BEST_SCORE})`; `scaled_min_rounds`/`custom_min_rounds` count only scored Sundays; count boards and `RATING_GAIN` eligibility count everything (T3a).
- Records: score records read `stat_rounds`; `_jumps` skips (neighbours adjacent); attendance/streaks/rating floor count everything (T3a).
- `profile.event_values` numbers `k` over every held Sunday, excluded Sundays plot no value; `splits()` omits a key with no scored round (T3b).
- `EventTrend`/`EventTrendOut.stats_excluded: bool`; `top_score_rolling8`/`median_rolling8: float | None` (None on the excluded row) (T3c).
- yir: `YearTotals.n_excluded`, `ShooterTotals.n_excluded` (last positional fields), `TopRound.stats_excluded: bool = False`, `OnThisDayItem.stats_excluded: bool` (T3d).
- `explorer.engine.STAT_METRICS = frozenset({SCORE, ADJUSTED, RESIDUAL, RATING, DIFFICULTY})` filtered server-side before every filter (so `min_rounds` counts scored rounds); **exception (found in T5d):** `score` with `agg=sum` is clays broken, a count, so it keeps thrown-out Sundays and fills `thrown_out_dates` like a count metric (`engine._is_stat(spec)`); HIT_PCT uses `live_station_hits`; `min_score` on count metrics counts official scores. `explorer.spec.QueryResult.thrown_out_dates: list[str]` (default `[]`, required in the OpenAPI schema): ISO dates of thrown-out Sundays among the rows, filled only for a non-`STAT_METRICS`, non-HIT_PCT metric grouped by `Dim.EVENT` (T6a).

##### API — response fields (required in OpenAPI; `json_schema_serialization_defaults_required=True` where a default exists)
- `class ThrownOutOut(BaseModel): station_label: str | None; target_count: int | None; credited: bool` and `thrown_out_out(items: Sequence[ThrownOut]) -> list[ThrownOutOut]` in `api/routes/events.py` (T6b)
- `stats_excluded: bool` on `EventSummaryOut`, `EventDetailOut`, `EventResultOut`, `WinnerOut`, `AttendanceOut` (T6b); `ShooterRoundOut` (T6c); `EventTrendOut`, `WeatherEventOut` (T3c); `YirTopRoundOut`, `OnThisDayItemOut` (T3d)
- `thrown_out: list[ThrownOutOut]` on `EventSummaryOut`, `EventDetailOut`, `RecapOut` (T6b)
- `dropped: bool` on `StationLayoutOut` (T6b)
- `n_excluded: int` on `ShooterStatsOut`, `SplitOut` (T3b); `YirTotalsOut`, `YirShooterTotalsOut` (T3d)
- `thrown_out_dates: list[str]` on `QueryResult` (T6a)
- `EventDetailOut.vs_prev` is None on a thrown-out Sunday; the next Sunday compares with the last non-excluded one (T6b). `event_notables` adds no PB on a thrown-out Sunday and compares later PBs with scored rounds only, while the ≥ 5 earlier rounds gate counts all rounds (T3b).
- ClaySmasher: `ExportRound.thrown_out: str | None = None` (last field); export values as recorded (T6b).
- Not added: `PbOut.stats_excluded`, `RecordRoundOut.stats_excluded`.
- The backend task that changes a schema field also adds that field to every typed frontend mock literal `pnpm typecheck` flags (no component change).

##### Test fixtures
- `backend/tests/conftest.py` (T2a): `THROWN_OUT_SUNDAY = date(2026, 10, 25)`, `THROWN_OUT_LABEL = "11"`, `THROWN_OUT_DATES` (10 Sundays 2026-08-23 … 2026-10-25), `THROWN_OUT_NAMES` (9 invented names), `THROWN_OUT_STATIONS = (5, 6, 7, 8, 9, 10, 11)`, `THROWN_OUT_TARGETS = (7, 7, 7, 7, 7, 8, 7)`, `thrown_out_hits(i, j)`, fixtures `fx_thrown_out_engine` (session), `fx_thrown_out_session`, `fx_thrown_out_client`, `fx_thrown_out_viewer_client`, `fx_thrown_out_admin_client`.
- World values: 10/25 scores Hadley 43, Abernathy 41, Birch 39, Kim 37, Crane 35, Kaplan 35, Ellis 31, Ace 29, Devlin 27 (median 35, top 43); Hadley's best before 10/25 is 41; Hadley's 10/25 sheet total without Station 11 is 36; Station 11 hits 427/630 with 10/25, 364/567 without; the station frame keeps 621 of 630 rows; every shooter attended all 10 Sundays.
- Builders: competition `FrameBuilder.event(stats_excluded=False)`; records `World.event(excluded=False)`; insights `World.sunday(day, stats_excluded=True)`, `World.station(..., dropped=True)`; `_station_sheet(..., dropped=())` in `test_events_routes.py`; `integration/domain/conftest._stations_workbook(stations: Sequence[int | str])`.

#### Frontend
- `frontend/src/features/events/thrownOut.ts` (T7a): `type ThrownOut = components['schemas']['ThrownOutOut']`; `thrownOutPhrase(items: readonly ThrownOut[]): string` (copy above; `[]` → `SUNDAY_THROWN_OUT`); `SUNDAY_THROWN_OUT`; `thrownOutBanner(items)`; `excludedNote(n: number): string | null` (`null` for 0, else `` `${n} round${n === 1 ? '' : 's'} marked * not in the average` ``); `THROWN_OUT_RECAP_LINE` (same text as `templates.THROWN_OUT_RECAP_HOW`).
- `frontend/src/components/ui/ThrownOutMark.tsx` (T7a): `ThrownOutMark({ phrase }: { phrase: string })` renders `<span className="ml-0.5 text-text-muted" title={phrase}><span aria-hidden="true">*</span><span className="sr-only"> {phrase}</span></span>`. A plain asterisk, never a star glyph.
- `frontend/src/components/charts/builders/thrownOut.ts` (T7a): `THROWN_OUT_COLUMN = { key: 'thrown_out', label: 'Thrown out', type: 'string' }`, `thrownOutCell(excluded): 'yes' | ''`, `hollowPoint(value, excluded)` (`{ value, symbol: 'emptyCircle', symbolSize: 8 }`), `hollowSeries(option, seriesNames, excluded)`, `thrownOutAxisTooltip(excludedDates: ReadonlySet<string>)`.
- `frontend/src/components/charts/thrownOutCopy.ts` (created by T8a only):
  - `THROWN_OUT_ROUNDS = 'Sundays with a station thrown out (marked *) are left out.'`
  - `THROWN_OUT_STATION = 'A station thrown out on the day is left out.'`
  - `THROWN_OUT_COUNTS = 'Sundays with a station thrown out count here, marked *.'`
  - `THROWN_OUT_HOLLOW = 'A hollow point is a Sunday with a station thrown out.'`
  - `thrownOutLineFor(metric: string): string` (T8b): ROUNDS for `avg_score | avg_adjusted | best_score | rating_gain`, else COUNTS
- Glossary term id `'thrown-out-station'`, term `Thrown-out station` (glossary/terms.ts, modelled on `special-shoot`); `GLOSSARY_TRIGGERS['thrown-out-station'] = /\bthrown[- ]out\b/i` (T8a). `raceExplainer(key, mode, metric)` (T8b).
- Chart CSV column `thrown_out` (`'yes'`/`''`) wherever round or Sunday rows appear; a thrown-out row stays in the CSV/table even where it is left out of the drawn line or points.
- Component props: `ResultsTable.phrase?: string`, `SundayCalendarOpts.thrownOut?: string` (column key), `LastResult.thrownOut: boolean`.
- Admin (T7b): rule type `station_drop` labelled `Thrown-out station`; `RulePayload = Record<string, string | number | boolean | null>` (rules.ts and admin-identity/api.ts); `DROPPED_OPTIONS`; `RuleFields.dropped: '' | 'yes' | 'no'`.

#### Process
- TDD: every task pastes the failing output (RED) then the passing output (GREEN). Reviewers re-run the new tests on the task's base to prove they fail there (tests marked "guard" are expected to pass on base). Commands: backend `cd backend && uv run pytest <path> -q`; frontend `cd frontend && pnpm vitest run <path>`; full gates per CONTRIBUTING.md.
- `pnpm gen:api` (run by `pnpm typecheck`) exports the schema from local backend source; no running backend is needed. `openapi.json` and `frontend/src/api/schema.d.ts` are gitignored and never committed.
- Never edit `ratchets/`. Never add real names (invented names only). Neutral pronouns. Conventional Commits; every commit ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Lettered stations (7A) end to end** — layout `4, 5, 6, 7, 7A, 8, 9` with every 7A entry perfect gives layout `("7A", True, "auto")`, message "Station 7A on 2026-09-13 …" and `stats_excluded`; a rule `"7a"` matches 7A with source `override`; a rule `"07"` matches only `7`; `/api/stations/7A` 404s while `/api/stations/7` is 200; the heatmap header reads `Stn 7A * (6)`. Tests: T1c, T4a, T7c.
2. **Doubleheaders on a thrown-out Sunday** — 7 shooters plus one second-round row make 8 entries, so the station is thrown out (n_entries 8); a shooter with two rounds that Sunday has `n_rounds` counting both and `n_excluded == 2` (profile and splits); both rounds add to the "≥ 5 earlier rounds" PB count. Tests: T1c, T6c, T3b, T3d.
3. **A shooter whose only rounds fell on the thrown-out Sunday** — profile `avg/median/best` None with `n_excluded == 1`, odometer `hit_pct` None, `pbs == []`; on the ROUNDS and WINS boards but not AVG_SCORE; YIR `avg_score` None with `n_excluded == 1`; the hero shows "—" with "1 round marked * not in the average". Tests: T6c, T3d, T7e.
4. **Count kinds and trophies still fire on the excluded Sunday** — `ev.close-finish`, `ev.new-faces` (welcome), `pf.targets-milestone`, `pf.wins`, `pf.podium-run` still anchor on it; the `clays_broken`, `events`, `doubleheader` and `first_win` trophies still award on it; the chart-proof world still has a count kind on that day. Tests: T5c, T4b, T5d.
5. **The real 10/25 case through the routes** — on `fx_thrown_out_viewer_client`: Hadley's PBs top out at 41 (not 43) with `n_excluded == 1`; no 43 in records; `/api/events/2026-10-25` is flagged with `thrown_out == [{"station_label": "11", "target_count": 7, "credited": true}]` and `vs_prev` null; Station 11 shows 364/567; the latest `/api/events` item is flagged; season points and the race equal a run with the flags cleared. Test: T6d.

## Execution order

Each numbered row starts after every earlier row is merged. Tasks joined by `∥` touch independent files and may run as parallel lanes; `→` is sequential inside a lane. T2b from the drafts no longer exists: its column-only edits moved to their owners and its reader tests were folded into T3c, T3d, T4a and T4c.

1. T1a ∥ T1b
2. T1c
3. T2a
4. T2c
5. T3a ∥ T3b ∥ T3c ∥ T3d ∥ T4a ∥ (T4b → T4c) ∥ T6a — backend analytics lanes (T6a, the Explorer engine, runs here so T5d can use it). T3b, T3c, T3d and T6a each regenerate types and touch different frontend mock files; rebase and re-run `pnpm typecheck` before merging the second and later of them.
6. (T5a → T5b → T5c → T5d → T5e) ∥ (T6b → T6c → T6d) — insights lane needs T4c (insights `World.station`), T3c (`first_round_scores`) and T6a; API lane needs T3b (`event_notables`), T4a (station frame) and T3a.
7. T7a — after every backend task.
8. T7b ∥ T7c ∥ T7d ∥ T7e
9. T8a → T8b → T8c → T8d
10. T9 — ops and rollout, last.

---

### Task T1a: Schema flags and the `station_drop` rule type

**Depends on:** nothing.

**Files:**
- Create: `backend/migrations/versions/0010_thrown_out_stations.py`
- Modify: `backend/src/sunday_clays/models/live.py:30-54` (Event), `:97-104` (StationLayout)
- Modify: `backend/src/sunday_clays/domain/rules.py:58-66` (RuleType), `:140-154` (payload + `PAYLOAD_MODELS`), `:157-169` (`ActiveRules`), `:263-282` (`load_active_rules`)
- Test: `backend/tests/unit/domain/test_station_drop_payload.py` (new), `backend/tests/integration/models/test_schema_0001.py` (roundtrip at :266-290, new tests after :697), `backend/tests/integration/domain/test_overlay_rules.py` (parametrize at :67-79, new test after :303)

**Interfaces:**
- Consumes: `parse_label` from `sunday_clays.station_label`.
- Produces: the three columns and CHECK `ck_station_layouts_dropped_source`; `Event.stats_excluded`, `StationLayout.dropped`, `StationLayout.dropped_source`; `RuleType.STATION_DROP`; `StationDropPayload`; `ActiveRules.station_drops`.

- [ ] **Step 1: Write the failing tests**

`test_station_drop_payload.py`:
```python
def test_station_drop_is_a_rule_type_with_its_payload_model() -> None:
    assert RuleType("station_drop") is RuleType.STATION_DROP
    assert PAYLOAD_MODELS[RuleType.STATION_DROP] is StationDropPayload

def test_station_drop_payload_normalizes_the_label() -> None:
    p = StationDropPayload.model_validate({"event_date": "2026-10-25", "station_label": " 7a ", "dropped": True})
    assert (p.event_date, p.station_label, p.dropped) == (date(2026, 10, 25), "7A", True)

def test_station_drop_payload_rejects_a_non_label() -> None:
    with pytest.raises(ValidationError, match="is not a station number or label like 7A"):
        StationDropPayload.model_validate({"event_date": "2026-10-25", "station_label": "Total", "dropped": True})

def test_a_sunday_level_payload_can_only_mark_thrown_out() -> None:
    with pytest.raises(ValidationError, match="A Sunday-level rule can only mark a Sunday as thrown out"):
        StationDropPayload.model_validate({"event_date": "2026-10-25", "dropped": False})
    p = StationDropPayload.model_validate({"event_date": "2026-10-25", "dropped": True})
    assert p.model_dump(mode="json") == {"event_date": "2026-10-25", "station_label": None, "dropped": True}
```
`test_overlay_rules.py`, two rows in the `test_create_rule_rejects_invalid_payloads` parametrize (:67):
```python
(RuleType.STATION_DROP, {"event_date": "2026-10-25", "station_label": None, "dropped": False},
 "A Sunday-level rule can only mark a Sunday as thrown out"),
(RuleType.STATION_DROP, {"event_date": "2026-10-25", "station_label": "11", "dropped": True, "reason": "x"}, "reason"),
```
and a new test:
```python
def test_station_drop_rules_load_newest_per_station_and_sunday(session: Session) -> None:
    create_rule(session, RuleType.STATION_DROP, {"event_date": "2026-10-25", "station_label": "11", "dropped": True}, None)
    newer = create_rule(session, RuleType.STATION_DROP, {"event_date": "2026-10-25", "station_label": "11", "dropped": False}, None)
    sunday = create_rule(session, RuleType.STATION_DROP, {"event_date": "2026-01-11", "dropped": True}, None)
    gone = create_rule(session, RuleType.STATION_DROP, {"event_date": "2026-10-18", "station_label": "4", "dropped": True}, None)
    deactivate_rule(session, gone)
    assert load_active_rules(session).station_drops == {
        (date(2026, 10, 25), "11"): (newer, False),
        (date(2026, 1, 11), None): (sunday, True),
    }
```
`test_schema_0001.py`: in `test_upgrade_downgrade_roundtrip` (:266), before the existing `_alembic(scratch_engine, "downgrade", "0008")`, add `_alembic(scratch_engine, "downgrade", "0009")` and `assert _tables(scratch_engine) == C4_TABLES | {"alembic_version"}`. New tests:
```python
def test_0010_defaults_the_flags_off_and_checks_dropped_source(scratch_engine: Engine) -> None:
    _alembic(scratch_engine, "upgrade", "0009")
    with scratch_engine.begin() as conn:
        conn.execute(text(f"{EVENT_INSERT}) VALUES ('2026-10-18', 'sporting', 'none', 0, 0, false, false, false)"))
        conn.execute(text("INSERT INTO station_layouts (event_date, station_label, station_no, target_count,"
                          " source_import_id) VALUES ('2026-10-18', '11', 11, 7, 1)"))
    _alembic(scratch_engine, "upgrade", "head")
    with scratch_engine.begin() as conn:  # the previous release writes no flags
        conn.execute(text(f"{EVENT_INSERT}) VALUES ('2026-10-25', 'sporting', 'none', 0, 0, false, false, false)"))
        events = conn.execute(text("SELECT event_date::text, stats_excluded FROM events ORDER BY 1")).all()
        layouts = conn.execute(text("SELECT dropped, dropped_source FROM station_layouts")).all()
    assert [tuple(r) for r in events] == [("2026-10-18", False), ("2026-10-25", False)]
    assert [tuple(r) for r in layouts] == [(False, None)]
    with pytest.raises(IntegrityError, match="ck_station_layouts_dropped_source"), scratch_engine.begin() as conn:
        conn.execute(text("UPDATE station_layouts SET dropped_source = 'manual'"))

def test_0010_downgrade_removes_the_flags(scratch_engine: Engine) -> None:
    _alembic(scratch_engine, "upgrade", "head")
    _alembic(scratch_engine, "downgrade", "0009")
    with scratch_engine.connect() as conn:
        assert conn.execute(text("SELECT column_name FROM information_schema.columns WHERE column_name IN"
                                 " ('stats_excluded', 'dropped', 'dropped_source')")).all() == []
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/domain/test_station_drop_payload.py tests/integration/models/test_schema_0001.py tests/integration/domain/test_overlay_rules.py -q`. Expected: `ImportError: cannot import name 'StationDropPayload'`; `UndefinedColumn: stats_excluded` in `test_0010_*`; the roundtrip fails at `downgrade 0009` (0009 is head); `AttributeError: STATION_DROP` in the overlay tests.

- [ ] **Step 3: Implement**

- Migration: docstring says expand-only (the previous release never writes the flags; the defaults keep its rebuild correct). `upgrade` adds `events.stats_excluded` and `station_layouts.dropped` as `sa.Boolean(), server_default=sa.text("false"), nullable=False`, `station_layouts.dropped_source` as `sa.Text(), nullable=True`, then `op.create_check_constraint(op.f("ck_station_layouts_dropped_source"), "station_layouts", "dropped_source IN ('auto', 'override')")`. `downgrade` reverses in reverse order.
- `models/live.py`: `Event.stats_excluded: Mapped[bool]` (`Boolean, nullable=False, server_default=text("false")`); `StationLayout.__table_args__ = (CheckConstraint("dropped_source IN ('auto', 'override')", name=conv("ck_station_layouts_dropped_source")),)`; `StationLayout.dropped: Mapped[bool]` (same default); `StationLayout.dropped_source: Mapped[str | None] = mapped_column(Text, nullable=True)`.
- `rules.py`: `STATION_DROP = "station_drop"`; `class StationDropPayload(_Payload)` with `event_date: date`, `station_label: str | None = None`, `dropped: bool` and an `@model_validator(mode="after")` that normalizes a given label with `parse_label` (None → `ValueError(f"{self.station_label!r} is not a station number or label like 7A")`) and raises `ValueError("A Sunday-level rule can only mark a Sunday as thrown out")` for no label with `dropped=False`; a `PAYLOAD_MODELS` entry; `station_drops` as the last `ActiveRules` field; `load_active_rules` builds `ActiveRules([], [], {}, {}, {}, {})` and a `STATION_DROP` branch sets `rules.station_drops[(p.event_date, p.station_label)] = (rule_id, p.dropped)`.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2: all pass, including the existing `test_checks_match_models`, `test_server_defaults_match_models` and `alembic check` tests. Then the backend gate.

- [ ] **Step 5: Commit**

`git add backend/migrations/versions/0010_thrown_out_stations.py backend/src/sunday_clays/models/live.py backend/src/sunday_clays/domain/rules.py backend/tests/unit/domain/test_station_drop_payload.py backend/tests/integration/models/test_schema_0001.py backend/tests/integration/domain/test_overlay_rules.py` — `feat(model): thrown-out station flags (migration 0010) and station_drop rule type` (+ trailer).

---

### Task T1b: Pure detection and shared copy (`domain/thrown_out.py`)

**Depends on:** nothing.

**Files:**
- Create: `backend/src/sunday_clays/domain/thrown_out.py`
- Test: `backend/tests/unit/domain/test_thrown_out.py` (new)

**Interfaces:**
- Consumes: stdlib only.
- Produces: `MIN_DROP_ENTRIES`, `SUNDAY_THROWN_OUT`, `ThrownOut`, `detect_thrown_out`, `thrown_out_phrase`, exactly as in the contract.

- [ ] **Step 1: Write the failing tests**

```python
D, E = date(2026, 10, 25), date(2026, 1, 11)
TARGETS = {(D, "4"): 7, (D, "10"): 8, (D, "11"): 7}   # layout order
MIXED = {(D, "4"): [7, 6, 5] * 3, (D, "10"): [8, 7] * 4}
T = ThrownOut

def test_every_entry_perfect_on_eight_entries_is_thrown_out() -> None:
    assert MIN_DROP_ENTRIES == 8
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 8}, TARGETS, {}, ()) == {D: (T("11", 7, True, "auto"),)}

def test_seven_entries_are_below_the_threshold() -> None:
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 7}, TARGETS, {}, ()) == {}

def test_one_entry_short_of_perfect_is_not_thrown_out() -> None:
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 19 + [6]}, TARGETS, {}, ()) == {}

def test_a_special_sunday_is_skipped_even_with_overrides() -> None:
    overrides = {(D, "4"): (3, True), (D, None): (4, True)}
    assert detect_thrown_out({**MIXED, (D, "11"): [7] * 20}, TARGETS, overrides, {D}) == {}

def test_override_on_forces_a_station_and_says_whether_it_was_credited() -> None:
    got = detect_thrown_out({**MIXED, (D, "11"): [7] * 20}, TARGETS, {(D, "4"): (5, True)}, ())
    assert got == {D: (T("4", 7, False, "override"), T("11", 7, True, "auto"))}

def test_override_on_a_station_with_no_entries_is_not_credited() -> None:
    got = detect_thrown_out({(D, "4"): [7] * 3}, TARGETS, {(D, "10"): (6, True)}, ())
    assert got == {D: (T("10", 8, False, "override"),)}

def test_override_off_clears_an_auto_station() -> None:
    assert detect_thrown_out({(D, "11"): [7] * 20}, TARGETS, {(D, "11"): (7, False)}, ()) == {}

def test_an_override_for_a_station_not_in_the_layout_adds_nothing() -> None:
    assert detect_thrown_out({}, TARGETS, {(D, "12"): (8, True)}, ()) == {}

def test_sunday_level_override_adds_an_unnamed_item_last_and_dates_sort() -> None:
    got = detect_thrown_out({(D, "11"): [7] * 20}, TARGETS, {(D, None): (9, True), (E, None): (10, True)}, ())
    assert list(got) == [E, D]
    assert got[D] == (T("11", 7, True, "auto"), T(None, None, False, "override"))
    assert got[E] == (T(None, None, False, "override"),)

@pytest.mark.parametrize(("items", "phrase"), [
    ([T("11", 7, True, "auto")], "Station 11 was thrown out; everyone was credited 7/7"),
    ([T("11", 7, False, "override")], "Station 11 was thrown out"),
    ([T("4", 7, True, "auto"), T("11", 7, True, "auto")], "Stations 4 and 11 were thrown out; everyone was credited in full"),
    ([T("3", 7, True, "auto"), T("4", 7, False, "override"), T("11", 7, True, "auto")], "Stations 3, 4 and 11 were thrown out"),
    ([T(None, None, False, "override")], "A station was thrown out this Sunday"),
    ([T("7A", 6, True, "auto"), T(None, None, False, "override")], "Station 7A was thrown out; everyone was credited 6/6"),
    ([], "A station was thrown out this Sunday"),
])
def test_thrown_out_phrase(items: list[ThrownOut], phrase: str) -> None:
    assert thrown_out_phrase(items) == phrase
    assert SUNDAY_THROWN_OUT == "A station was thrown out this Sunday"
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/domain/test_thrown_out.py -q`. Expected: `ModuleNotFoundError: No module named 'sunday_clays.domain.thrown_out'`.

- [ ] **Step 3: Implement**

Signatures exactly as the contract. The `MIN_DROP_ENTRIES` docstring is the single documented place for the threshold (real turnouts 13 to 40; the rule fires twice in production, 2026-10-25 St 11 and 2026-01-11 St 10). `detect_thrown_out` groups `target_counts` keys by date in insertion order, skips special dates, decides each station (override wins; else auto), appends the Sunday-level item for a `(d, None) → True` override, and returns ascending dates with ≥ 1 item. `thrown_out_phrase` returns `SUNDAY_THROWN_OUT` when there is no station item (including `[]`), else the one/several-station forms from the contract.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2: 16 passed. Then the backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/domain/thrown_out.py backend/tests/unit/domain/test_thrown_out.py` — `feat(domain): detect thrown-out stations and build their shared copy` (+ trailer).

---

### Task T1c: Rebuild wiring, `station_thrown_out` issue, rule-target issues and the `station_dropped` preview finding

**Depends on:** T1a, T1b.

**Files:**
- Modify: `backend/src/sunday_clays/domain/rebuild.py` — imports (:33-39); `rebuild_live` (:96-127); `_write_events` (:344-418: `thrown_out` kwarg, the `stats_excluded` row key at :389, the rule-target loop after :415); `_write_station_data` (:442-463); new `_staged_station_hits` and `_thrown_out_issues` after :341
- Modify: `backend/src/sunday_clays/domain/imports.py:64-66` (`PREVIEW_STATION_CODES`), `:553-610` (`_preview_stations`)
- Modify: `backend/tests/integration/domain/conftest.py:72-75` (`_stations_workbook(stations: Sequence[int | str] = …)`, annotation only)
- Modify: `frontend/src/features/admin/components/FindingsList.tsx:6-10` (`STATION_CODES`; T1c owns it)
- Test: `backend/tests/integration/domain/test_rebuild_thrown_out.py` (new), `backend/tests/integration/domain/test_overlay_rules.py:654-711` (deactivation parametrize), `frontend/src/features/admin/components/FindingsList.test.tsx`

**Interfaces:**
- Consumes: `detect_thrown_out`, `ThrownOut` (T1b); `ActiveRules.station_drops` and the ORM columns (T1a).
- Produces: `_staged_station_hits`, `_write_events(..., thrown_out=None)`, `_write_station_data(..., thrown_out=None, overridden=frozenset())`, live `events.stats_excluded` / `station_layouts.dropped` / `dropped_source`, DataIssue `station_thrown_out`, preview finding `station_dropped` (contract §Rebuild).

- [ ] **Step 1: Write the failing tests**

`test_rebuild_thrown_out.py` uses `session`, `scores_workbook`, `stations_workbook`, `special_workbook`, `mark_committed`, `count_queries`. Constants: `D1, D2 = date(2026, 9, 6), date(2026, 9, 13)`; `LAYOUT = (7, 7, 7, 7, 7, 7, 8)`; `CLEAN4 = (7, 5, 5, 5, 5, 5, 5)` (37); `NAMES = ["Hadley, Ike", "Devlin, Sid", "Crenshaw, Noel", "Kaplan, Noel", "Kim, Pat", "Pruett, Luther", "Linwood, Luther", "Abernathy, Preston"]`; `MSG4 = "Station 4 on 2026-09-13 looks thrown out (every shooter perfect). It's marked * and left out of stats. Override in Rules if that's wrong."`. Helpers: `_live(sheet, extra_scores=(), rules=(), stations=(4, 5, 6, 7, 8, 9, 10))` commits `scores_workbook([(n, sum(h), D2) for n, h in sheet if n != "Nobody, New"] + list(extra_scores))` and `stations_workbook([("9 13 26", D2, LAYOUT, sheet)], stations)`, creates each rule as `(RuleType.STATION_DROP, payload)` and runs `rebuild_live`; `_layouts(session)` returns `(label, dropped, dropped_source)` by `station_no, station_label`; `_issues(session, code)` by id.

```python
def test_a_station_every_entry_cleaned_is_thrown_out_and_still_counts(...):
    # _live(sheet=[(n, CLEAN4) for n in NAMES], extra_scores=[("Hadley, Ike", 30, D1)]) inside count_queries
    assert session.get(Event, D2).stats_excluded is True and session.get(Event, D1).stats_excluded is False
    assert _layouts(session) == [("4", True, "auto"), *[(str(n), False, None) for n in range(5, 11)]]
    [issue] = _issues(session, "station_thrown_out")
    assert (issue.severity, issue.event_date, issue.shooter_id, issue.message, issue.details) == (
        "info", D2, None, MSG4, {"station_label": "4", "n_entries": 8, "target_count": 7})
    assert session.scalars(select(Round.score).where(Round.event_date == D2)).all() == [37] * 8
    assert session.get(Event, D2).results_complete is True
    assert session.get(ShooterProfile, lookup_shooter(session, "hadley ike")).n_rounds == 2
    assert sum(s.startswith("INSERT INTO station_layouts") for s in statements) == 1

def test_seven_entries_are_not_enough(...):            # sheet = [(n, CLEAN4) for n in NAMES[:7]]
    assert session.get(Event, D2).stats_excluded is False
    assert _issues(session, "station_thrown_out") == []

def test_a_second_round_entry_counts_toward_the_eight_entries(...):  # Review Focus 2
    # sheet = [(n, CLEAN4) for n in NAMES[:7]] + [(NAMES[0], CLEAN4)]: 7 shooters, Hadley shot twice
    assert session.get(Event, D2).stats_excluded is True
    [issue] = _issues(session, "station_thrown_out")
    assert issue.details["n_entries"] == 8

@pytest.mark.parametrize(("hit", "dropped"), [(7, True), (6, False)])
def test_an_unlinked_entry_counts_toward_the_rule(..., hit: int, dropped: bool):
    # sheet = [(n, CLEAN4) for n in NAMES[:7]] + [("Nobody, New", (hit, 4, 4, 4, 4, 4, 4))]
    assert session.get(Event, D2).stats_excluded is dropped
    assert _layouts(session)[0] == ("4", dropped, "auto" if dropped else None)

def test_override_off_keeps_an_auto_station_in_stats(...):   # rules=[{"event_date": "2026-09-13", "station_label": "4", "dropped": False}]
    assert session.get(Event, D2).stats_excluded is False
    assert _layouts(session)[0] == ("4", False, "override")
    assert _issues(session, "station_thrown_out") == []

def test_override_on_marks_a_station_that_was_not_all_perfect(...):  # sheet=[(n, (5,)*7) for n in NAMES[:2]], rule station "5" True
    assert session.get(Event, D2).stats_excluded is True
    assert _layouts(session)[1] == ("5", True, "override")
    assert _issues(session, "station_thrown_out") == []

LETTERED = (4, 5, 6, 7, "7A", 8, 9)
CLEAN7A = (5, 5, 5, 5, 7, 5, 5)

def test_a_lettered_station_is_detected_and_named(...):  # Review Focus 1: _live([(n, CLEAN7A) for n in NAMES], stations=LETTERED)
    assert session.get(Event, D2).stats_excluded is True
    assert [r for r in _layouts(session) if r[0] in ("7", "7A")] == [("7", False, None), ("7A", True, "auto")]
    [issue] = _issues(session, "station_thrown_out")
    assert issue.message.startswith("Station 7A on 2026-09-13 looks thrown out")

def test_a_lower_case_rule_matches_the_lettered_station(...):  # sheet=[(n, (5,)*7) for n in NAMES[:2]], LETTERED, rule {"station_label": "7a", "dropped": True}
    assert [r for r in _layouts(session) if r[0] in ("7", "7A")] == [("7", False, None), ("7A", True, "override")]

def test_a_rule_for_07_touches_only_station_7(...):  # [(n, CLEAN7A) for n in NAMES], LETTERED, rule {"station_label": "07", "dropped": False}
    assert [r for r in _layouts(session) if r[0] in ("7", "7A")] == [("7", False, "override"), ("7A", True, "auto")]
    assert session.get(Event, D2).stats_excluded is True

def test_a_sunday_level_override_excludes_a_sunday_without_a_sheet(...):  # rules=[{"event_date": "2026-09-06", "dropped": True}], extra_scores=[("Hadley, Ike", 30, D1)]
    assert (session.get(Event, D1).stats_excluded, session.get(Event, D1).has_stations) == (True, False)
    assert session.get(Event, D2).stats_excluded is False

def test_unmatched_station_drop_rules_are_reported(...):  # rules: station "12" on 2026-09-13 (r12); Sunday-level on 2026-09-20, no Sunday (r20)
    a, b = _issues(session, "rule_target_missing")
    assert (a.event_date, a.message, a.details) == (D2,
        f"Rule {r12} targets Station 12 on 2026-09-13, which has no such station on a regular Sunday",
        {"rule_id": r12, "event_date": "2026-09-13", "station_label": "12", "dropped": True})
    assert (b.event_date, b.message) == (date(2026, 9, 20), f"Rule {r20} marks 2026-09-20 as thrown out, which has no regular Sunday")

def test_a_special_sunday_is_never_thrown_out(...):
    # commit scores_workbook([("Hadley, Ike", 41, D2)]) and special_workbook([(n, (6,) + (5,) * 9) for n in NAMES]);
    # rule {"event_date": "2026-09-20", "dropped": True}; rebuild_live
    assert session.get(Event, date(2026, 9, 20)).stats_excluded is False
    assert {(d, s) for _, d, s in _layouts(session)} == {(False, None)}
    assert _issues(session, "station_thrown_out") == []
    [missing] = _issues(session, "rule_target_missing")
    assert missing.message == f"Rule {rid} marks 2026-09-20 as thrown out, which has no regular Sunday"

def test_the_stations_preview_flags_a_station_that_looks_thrown_out(...):
    # commit the scores for NAMES at 37 on D2, rebuild, then stage_import (no commit) of the CLEAN4 tab
    assert "station_dropped" in PREVIEW_STATION_CODES
    assert [(f.code, f.severity, f.sheet, f.event_date, f.message) for f in preview.findings if f.code == "station_dropped"] == [
        ("station_dropped", Severity.INFO, "9 13 26", D2,
         "Station 4 on 2026-09-13 looks thrown out (every shooter perfect). "
         "It will be marked * and left out of stats. Override in Rules if that's wrong.")]
```
`test_overlay_rules.py`, a `pytest.param` after the `alias_name` one (:704-710):
```python
pytest.param(RuleType.STATION_DROP, lambda _: {"event_date": "2026-09-13", "station_label": "4", "dropped": True},
             {"events", "station_layouts"}, id="station_drop"),
```
`FindingsList.test.tsx`, inside `describe('groupFindings')`:
```ts
it('puts a thrown-out station finding under Station vs score', () => {
  const groups = groupFindings([{ code: 'station_dropped', severity: 'info', message: 'Station 4 looks thrown out' }]);
  expect(groups.station.map((f) => f.code)).toEqual(['station_dropped']);
  expect(groups.other).toEqual([]);
});
```

- [ ] **Step 2: Run to verify RED**

Backend: `cd backend && uv run pytest tests/integration/domain/test_rebuild_thrown_out.py tests/integration/domain/test_overlay_rules.py -q` — new tests fail with `assert False is True` on `stats_excluded` or an empty issue list; the `station_drop` deactivation case fails with `set() == {'events', 'station_layouts'}`. Frontend: `cd frontend && pnpm vitest run src/features/admin/components/FindingsList.test.tsx` — `expected [] to deeply equal ['station_dropped']`.

- [ ] **Step 3: Implement**

`rebuild.py`:
1. `_staged_station_hits(session, sources)`: select `ImportStationHit.sheet_id, station_label, hits` for `sheet_id IN sources.values()`, ordered by `sheet_id, row_number, station_no, station_label`; map sheet → date; return `{(d, label): [hits, ...]}` (every entry row, linked or not; the docstring says "entries", not "shooters", because a second-round row is its own entry).
2. `rebuild_live`, after `layouts = ...` (:120): build `station_hits`, `target_counts = {(d, e.label): e.target_count for d, entries in layouts.items() for e, _ in entries}`, `thrown_out = detect_thrown_out(station_hits, target_counts, rules.station_drops, specials.keys())` and `overridden = {(d, label) for (d, label) in rules.station_drops if label is not None and d not in specials and (d, label) in target_counts}`. Pass `thrown_out=thrown_out` to `_write_events`, `thrown_out=thrown_out, overridden=overridden` to `_write_station_data`, then `issues.extend(_thrown_out_issues(thrown_out, station_hits))`.
3. `_write_events`: `excluded = thrown_out or {}`; row key `"stats_excluded": d in excluded`. After the `round_types` loop, walk `sorted(rules.station_drops.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))`: a station key is missing when `d in specials` or `(d, label)` is not in that date's layout; a Sunday key when `d in specials` or `d not in event_dates`; emit the `rule_target_missing` warning with the contract messages and details.
4. `_write_station_data`: `on = {i.station_label for i in (thrown_out or {}).get(d, ())}`; row keys `"dropped": entry.label in on` and `"dropped_source"` (`'override'` if `(d, entry.label) in overridden`, else `'auto'` if dropped, else None); the insert becomes `insert(StationLayout).execution_options(render_nulls=True)`.
5. `_thrown_out_issues(thrown_out, hits) -> list[DataIssue]`: one per `source == "auto"` item, code `station_thrown_out`, `info`, the contract message, details `{"station_label", "n_entries": len(hits[(d, label)]), "target_count"}`.

`imports.py`: add `"station_dropped"` to `PREVIEW_STATION_CODES`. In `_preview_stations`, from the non-special parsed sheets build `hits`, `targets` (layout order) and `tab_of = {date: sheet_name}`; call `detect_thrown_out(hits, targets, {}, specials.keys())`; emit `Finding("station_dropped", Severity.INFO, <preview message>, sheet=tab_of[d], event_date=d)`; return `[*ignored, *dropped, *_station_findings(...)]`.

`FindingsList.tsx`: add `'station_dropped'` to `STATION_CODES`. `integration/domain/conftest.py`: widen the `stations` annotation to `Sequence[int | str]`.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (all pass). Regression, unchanged and green: `cd backend && uv run pytest tests/integration/domain/test_rebuild_live.py tests/integration/domain/test_rebuild_special.py -q` (the fixture world has no all-perfect station: at most 6 of 24 entries on 2026-09-06, 3 of 13 on 2026-09-13; `RebuildReport(n_issues=2)` holds; `test_station_lookups_take_a_fixed_number_of_queries` (:470) holds because both sides include the one new query). Backend gate; `cd frontend && pnpm lint && pnpm typecheck`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/domain/rebuild.py backend/src/sunday_clays/domain/imports.py backend/tests/integration/domain/conftest.py backend/tests/integration/domain/test_rebuild_thrown_out.py backend/tests/integration/domain/test_overlay_rules.py frontend/src/features/admin/components/FindingsList.tsx frontend/src/features/admin/components/FindingsList.test.tsx` — `feat(rebuild): mark thrown-out stations and Sundays, report them, flag them in the import preview` (+ trailer).

---

### Task T2a: Frame flags, frame helpers, `load_thrown_out` and the thrown-out test world

**Depends on:** T1c (the world only gets its flags through detection).

**Files:**
- Modify: `backend/src/sunday_clays/analytics/frames.py:24-55` (ROUND_COLUMNS), `:56-82` (EVENT_COLUMNS), `:83-95` (STATION_HIT_COLUMNS), `:134-189` (`_ROUNDS_SQL`, `_EVENTS_SQL`, `_CALENDAR_SQL`, `_STATION_HITS_SQL`, `_SPECIAL_STATION_HITS_SQL`), `:272` (rounds `bools=`), `:296` (`_EVENT_BOOLS`), `:349-359` (`_station_frame`), `:402-408` (`calendar_from_events`), new helpers and loader after `:408`
- Modify: `backend/tests/conftest.py` (append after line 529, the end of the file; copy the `fx_special_*` pattern at :486-529)
- Modify: `backend/tests/unit/analytics_core/conftest.py:36-45` (`build_rounds`), `:74-81` (`build_events`)
- Modify: `backend/tests/integration/analytics_core/conftest.py:40-70` (`LiveSeed.event`; T2a owns this kwarg)
- Test: `backend/tests/unit/analytics_core/test_frame_helpers.py` (append), `backend/tests/integration/analytics_core/test_frame_loaders.py` (append), `backend/tests/integration/thrown_out/test_thrown_out_world.py` (new)

**Interfaces:**
- Consumes: T1a columns, `domain.thrown_out.ThrownOut`, T1c detection.
- Produces: the frame columns, `stat_rounds`, `stat_events`, `live_station_hits`, `load_thrown_out(session)`, `calendar_from_events` default, builder defaults, `LiveSeed.event(stats_excluded=False)`, and the `THROWN_OUT_*` world and `fx_thrown_out_*` fixtures (contract §Frames, §Test fixtures).

- [ ] **Step 1: Write the failing tests and the world fixture**

Append to `backend/tests/conftest.py` (invented names, exact data):
```python
# --- Thrown-out stations T2a: a synthetic world with one thrown-out Sunday --------------------
THROWN_OUT_SUNDAY = date(2026, 10, 25)
THROWN_OUT_LABEL = "11"
THROWN_OUT_DATES: tuple[date, ...] = tuple(date(2026, 8, 23) + timedelta(weeks=j) for j in range(10))
THROWN_OUT_NAMES: tuple[str, ...] = (
    "Hadley, Ike", "Kaplan, Noel", "Devlin, Sid", "Abernathy, Preston", "Kim, Pat",
    "Ace, Amy", "Birch, Lou", "Crane, Dot", "Ellis, Fay",
)
THROWN_OUT_STATIONS: tuple[int, ...] = (5, 6, 7, 8, 9, 10, 11)
THROWN_OUT_TARGETS: tuple[int, ...] = (7, 7, 7, 7, 7, 8, 7)

def thrown_out_hits(i: int, j: int) -> tuple[int, ...]:
    """Shooter i's hits on Sunday j; Station 11 on THROWN_OUT_SUNDAY is credited in full."""
    return tuple(
        t if THROWN_OUT_DATES[j] == THROWN_OUT_SUNDAY and s == 11
        else max(0, t - (i * 3 + j * 5 + k * 7) % 4 - i % 3)
        for k, (s, t) in enumerate(zip(THROWN_OUT_STATIONS, THROWN_OUT_TARGETS, strict=True))
    )
```
- `_thrown_out_uploads() -> list[tuple[str, bytes]]` builds two openpyxl workbooks like `_special_workbook`: `"scores_2026-10-25.xlsx"` with sheet `"ALL SCORE DETAIL"` (header `["Name", "Score Shot", "Event", "Status", "Class"]`, one row `[name, sum(hits), d, "Member", None]` per (j, i)) and `"Attendance History"` (`["Date", "Count", "Median"]`, then `[d, 9, statistics.median(scores)]`); and `"stations_2026-10-25.xlsx"` with one tab per Sunday titled `f"{d.month} {d.day} {d:%y}"` in the `tests/unit/ingest/builders_stations.py:station_sheet` row layout (`["Event Date"]`, `[d]`, `[]`, `["STATION #", *THROWN_OUT_STATIONS, "Total"]`, `["TARGET COUNT", *THROWN_OUT_TARGETS, "=SUM(B5:H5)"]`, `[]`, `["Median Hits"]`, `[]`, `["Name", "Station Hits"]`, then `[name, *hits]`).
- `_shift_weather(session, source: date, targets: Sequence[date])` inserts the `WEATHER_FIXTURE` rows whose `ts_local` starts with `source.isoformat()`, date swapped per target, same `fetched_at` as `load_weather_fixture`.
- Fixtures: session-scoped `fx_thrown_out_engine(engine)`:
  ```python
  with _build_world(engine, "fx_thrown_out", _thrown_out_uploads()) as world:
      with Session(world) as setup:
          _shift_weather(setup, date(2026, 9, 27), [date(2026, 9, 20), date(2026, 10, 4),
                         date(2026, 10, 11), date(2026, 10, 18), THROWN_OUT_SUNDAY])
          run_pipeline(setup)
          setup.commit()
      yield world
  ```
  then `fx_thrown_out_session` (`_rolled_back_session`), `fx_thrown_out_client`, `fx_thrown_out_viewer_client`, `fx_thrown_out_admin_client`, copied from `fx_special_*`. Add `timedelta` and `statistics` imports.

`test_thrown_out_world.py` redeclares `THROWN_OUT_SUNDAY = date(2026, 10, 25)` locally (as `tests/integration/special/test_special_world.py` does with `SPECIAL`) and imports `ThrownOut`, `frames`, `clear_cache`:
```python
def test_the_thrown_out_world_has_ten_sundays_and_credited_scores(fx_thrown_out_session):  # guard: world shape
    s = fx_thrown_out_session
    assert s.execute(select(func.count()).select_from(Event)).scalar_one() == 10
    assert s.execute(select(func.count()).select_from(Round)).scalar_one() == 90
    day = s.execute(select(Shooter.display_name, Round.score).join(Shooter, Shooter.id == Round.shooter_id)
        .where(Round.event_date == THROWN_OUT_SUNDAY).order_by(Round.score.desc(), Shooter.display_name)).all()
    assert [tuple(r) for r in day] == [("Hadley, Ike", 43), ("Abernathy, Preston", 41), ("Birch, Lou", 39),
        ("Kim, Pat", 37), ("Crane, Dot", 35), ("Kaplan, Noel", 35), ("Ellis, Fay", 31), ("Ace, Amy", 29),
        ("Devlin, Sid", 27)]
    assert s.execute(text("SELECT count(*) FROM event_weather")).scalar_one() == 10

def test_frames_carry_the_thrown_out_flags(fx_thrown_out_session):
    s = fx_thrown_out_session
    rounds = frames.load_rounds(s)
    assert rounds["stats_excluded"].dtype == bool and int(rounds["stats_excluded"].sum()) == 9
    assert set(rounds.loc[rounds["stats_excluded"], "event_date"]) == {THROWN_OUT_SUNDAY}
    for loader in (frames.load_events, frames.load_calendar):
        ev = loader(s)
        assert ev.loc[ev["stats_excluded"], "event_date"].tolist() == [THROWN_OUT_SUNDAY]
    hits = frames.load_station_hits(s)
    assert len(hits) == 630 and hits["dropped"].dtype == bool
    dropped = hits[hits["dropped"]]
    assert set(zip(dropped["event_date"], dropped["station_label"])) == {(THROWN_OUT_SUNDAY, "11")}
    assert dropped["hits"].tolist() == [7] * 9

def test_load_thrown_out_reads_the_auto_drop(fx_thrown_out_session):
    assert frames.load_thrown_out(fx_thrown_out_session) == {THROWN_OUT_SUNDAY: (ThrownOut("11", 7, True, "auto"),)}

def test_load_thrown_out_reads_overrides_and_sunday_level_flags(fx_thrown_out_session):
    s = fx_thrown_out_session
    s.execute(text("UPDATE station_layouts SET dropped = true, dropped_source = 'override'"
                   " WHERE event_date = '2026-10-11' AND station_label = '5'"))
    s.execute(text("UPDATE events SET stats_excluded = true WHERE event_date IN ('2026-10-11', '2026-10-18')"))
    clear_cache()
    got = frames.load_thrown_out(s)
    assert got[date(2026, 10, 11)] == (ThrownOut("5", 7, False, "override"),)
    assert got[date(2026, 10, 18)] == (ThrownOut(None, None, False, "override"),)
    assert list(got) == [date(2026, 10, 11), date(2026, 10, 18), THROWN_OUT_SUNDAY]
```
Append to `test_frame_helpers.py` (`D18, D25 = date(2026, 10, 18), date(2026, 10, 25)`):
```python
def test_stat_rounds_leaves_out_rounds_of_a_thrown_out_sunday(make_rounds):
    rounds = make_rounds([(D18, 1, 40), (D18, 2, 30), (D25, 1, 45), (D25, 2, 31)])
    assert rounds["stats_excluded"].tolist() == [False] * 4
    rounds["stats_excluded"] = rounds["event_date"].eq(D25)
    assert frames.stat_rounds(rounds)[["event_date", "score"]].values.tolist() == [[D18, 40], [D18, 30]]
    assert len(frames.stat_rounds(rounds.assign(stats_excluded=math.nan))) == 4
    assert len(frames.stat_rounds(rounds.drop(columns="stats_excluded"))) == 4

def test_stat_events_and_live_station_hits(make_events):
    events = make_events([D18, {"event_date": D25, "stats_excluded": True}])
    assert frames.stat_events(events)["event_date"].tolist() == [D18]
    hits = pd.DataFrame({"station_label": ["10", "11"], "hits": [5, 7], "dropped": [False, True]})
    assert frames.live_station_hits(hits)["station_label"].tolist() == ["10"]

def test_calendar_from_events_defaults_stats_excluded(make_events):
    assert frames.calendar_from_events(make_events([D18]).drop(columns="stats_excluded"))["stats_excluded"].tolist() == [False]
    assert frames.calendar_from_events(make_events([{"event_date": D25, "stats_excluded": True}]))["stats_excluded"].tolist() == [True]
```
Append to `test_frame_loaders.py`:
```python
def test_load_rounds_reads_stats_excluded(seed, session):
    ann = seed.shooter("Oakley, Ann")
    seed.event(date(2026, 10, 25), stats_excluded=True)
    seed.round(date(2026, 10, 25), ann, 40)
    seed.round(date(2026, 11, 1), ann, 38)
    seed.finish()
    assert frames.load_rounds(session)["stats_excluded"].tolist() == [True, False]
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics_core/test_frame_helpers.py tests/integration/analytics_core/test_frame_loaders.py tests/integration/thrown_out/test_thrown_out_world.py -q`. Expected: `KeyError: 'stats_excluded'` from the builders; `AttributeError: module 'sunday_clays.analytics.frames' has no attribute 'stat_rounds'` (and `load_thrown_out`); `TypeError: LiveSeed.event() got an unexpected keyword argument 'stats_excluded'`; `KeyError: 'dropped'`. The world-shape guard passes.

- [ ] **Step 3: Implement**

- SQL: `e.stats_excluded` in `_ROUNDS_SQL`, `_EVENTS_SQL`, `_CALENDAR_SQL`; `l.dropped` in `_STATION_HITS_SQL` and `_SPECIAL_STATION_HITS_SQL`; append the names to the three tuples.
- Casts: rounds `bools=("is_best_round", "held", "stats_excluded")`; `_EVENT_BOOLS += ("stats_excluded",)`; `_station_frame` `bools=("dropped",)`.
- Helpers: `stat_rounds(rounds)` returns `rounds` when the column is absent, else `rounds[~rounds["stats_excluded"].eq(True)]`; `stat_events` the same; `live_station_hits` on `"dropped"`.
- `calendar_from_events`: add `stats_excluded = False` when missing. `appearances_from_rounds` unchanged.
- `load_thrown_out(session)` (`@cached_by_data_version`) runs two module SQL constants:
  ```sql
  -- _THROWN_OUT_STATIONS_SQL
  SELECT l.event_date, l.station_label, l.target_count, l.dropped_source,
         count(h.hits) AS n_hits, coalesce(bool_and(h.hits = l.target_count), false) AS all_full
  FROM station_layouts l JOIN events e ON e.event_date = l.event_date
  LEFT JOIN station_hits h ON h.event_date = l.event_date AND h.station_label = l.station_label
  WHERE l.dropped AND e.kind = 'regular'
  GROUP BY l.event_date, l.station_no, l.station_label, l.target_count, l.dropped_source
  ORDER BY l.event_date, l.station_no, l.station_label
  -- _THROWN_OUT_SUNDAYS_SQL
  SELECT e.event_date FROM events e
  WHERE e.stats_excluded AND e.kind = 'regular'
    AND NOT EXISTS (SELECT 1 FROM station_layouts l WHERE l.event_date = e.event_date AND l.dropped)
  ```
  and builds the items per the contract, dates ascending.
- Builders: `build_rounds` `merged.setdefault("stats_excluded", False)`; `build_events` `row.setdefault("stats_excluded", False)`. `LiveSeed.event` gains `stats_excluded: bool = False` written to the `stats_excluded` column (bind `:se`).

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (all pass). Regression: `cd backend && uv run pytest tests/unit/analytics_core tests/integration/analytics_core tests/integration/special tests/unit/analytics -q` (`test_the_calendar_is_the_events_plus_the_special_sunday` needs `_CALENDAR_SQL` to carry the column). Backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/frames.py backend/tests/conftest.py backend/tests/unit/analytics_core/conftest.py backend/tests/unit/analytics_core/test_frame_helpers.py backend/tests/integration/analytics_core/conftest.py backend/tests/integration/analytics_core/test_frame_loaders.py backend/tests/integration/thrown_out/test_thrown_out_world.py` — `feat(analytics): carry thrown-out flags through the frames, add stat helpers and a thrown-out test world` (+ trailer).

---

### Task T2c: Skill model and round metrics skip thrown-out Sundays (D5)

**Depends on:** T2a.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/skill.py:130-153` (`_prepare`, :144), `:263-270` (`run_skill_model` docstring)
- Modify: `backend/src/sunday_clays/analytics/steps/s30_skill.py:83`
- Modify: `backend/src/sunday_clays/analytics/metrics.py:58-94` (`compute_round_metrics`, :90)
- Test: `backend/tests/unit/analytics_core/test_skill_model.py`, `test_round_metrics.py` (append), `backend/tests/integration/analytics_core/test_s30_skill_step.py` (append), `backend/tests/integration/thrown_out/test_thrown_out_skill_metrics.py` (new)

**Interfaces:**
- Consumes: `ROUND_COLUMNS.stats_excluded`, `make_rounds`, `fx_thrown_out_session` (T2a).
- Produces: on a `stats_excluded` Sunday `expected`/`residual`/`adjusted` NULL, `mu_before == mu_after`, `event_metrics.difficulty` NULL; `field_median`/`event_rank`/`percentile`/`is_best_round` and the day's n/median/mean/top kept; burn-in counts `held & ~stats_excluded`.

- [ ] **Step 1: Write the failing tests**

```python
# test_skill_model.py
def test_thrown_out_event_is_skipped_like_a_non_held_event(make_rounds):
    d2, d3 = D + timedelta(days=14), D + timedelta(days=28)
    specs = [(D, 1, 35), (D, 2, 30), (d2, 1, 44), (d2, 2, 37), (d3, 1, 36), (d3, 2, 29)]
    excluded = make_rounds(specs)
    excluded["stats_excluded"] = excluded["event_date"].eq(d2)
    not_held = make_rounds(specs)
    not_held["held"] = not_held["event_date"].ne(d2)
    got, want = run_skill_model(excluded), run_skill_model(not_held)
    pd.testing.assert_frame_equal(got.rounds, want.rounds)
    pd.testing.assert_frame_equal(got.events, want.events)
    pd.testing.assert_frame_equal(got.history, want.history)
    assert math.isnan(got.events.set_index("event_date").loc[d2, "difficulty"])

def test_nan_stats_excluded_counts_the_event(make_rounds):  # guard: bool(nan) must not exclude
    rounds = make_rounds([(D, 1, 35), (D, 2, 30)])
    pd.testing.assert_frame_equal(run_skill_model(rounds.assign(stats_excluded=math.nan)).rounds, run_skill_model(rounds).rounds)

# test_round_metrics.py
def test_thrown_out_event_keeps_median_rank_and_percentile_but_not_adjusted(make_rounds):
    m = _by_id(compute_round_metrics(make_rounds([(D0, 1, 40), (D0, 2, 30)], stats_excluded=True)))
    assert [m[1]["field_median"], m[2]["field_median"]] == [35.0, 35.0]
    assert [m[1]["event_rank"], m[2]["event_rank"]] == [1.0, 2.0]
    assert [m[1]["percentile"], m[2]["percentile"]] == [1.0, 0.0]
    assert [m[1]["is_best_round"], m[2]["is_best_round"]] == [True, True]
    assert math.isnan(m[1]["adjusted"]) and math.isnan(m[2]["adjusted"])

def test_round_metrics_without_the_flag_column_count_every_round(make_rounds):  # guard
    m = _by_id(compute_round_metrics(make_rounds([(D0, 1, 40), (D0, 2, 30)]).drop(columns="stats_excluded")))
    assert [m[1]["adjusted"], m[2]["adjusted"]] == [5.0, -5.0]

# test_s30_skill_step.py
def test_s30_burn_in_does_not_count_a_thrown_out_sunday(seed, session, monkeypatch):
    _seed_past_burn_in(seed, skill.BURN_IN_HELD_EVENTS + 1)
    session.execute(text("UPDATE events SET stats_excluded = true WHERE event_date = :d"), {"d": D2})
    seed.bump()
    monkeypatch.setattr(skill, "CALIBRATION_GRID", {"obs_var": (12.0,), "drift_var_per_week": (0.05,),
        "difficulty_var": (2.0,), "prior_mu": (30.0,), "prior_var": (49.0,)})
    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)
    assert _stored_params(session) is None
    assert _history_count(session) == 2 * (skill.BURN_IN_HELD_EVENTS + 1)

# test_thrown_out_skill_metrics.py
def test_thrown_out_sunday_keeps_official_metrics_without_adjusted_or_skill(fx_thrown_out_session):
    s = fx_thrown_out_session
    rounds = frames.load_rounds(s)
    day = rounds[rounds["event_date"] == THROWN_OUT_SUNDAY]
    assert day["field_median"].tolist() == [35.0] * 9
    assert day["adjusted"].isna().all() and day["expected"].isna().all() and day["residual"].isna().all()
    assert (day["mu_before"] == day["mu_after"]).all()
    hadley = day[day["display_name"] == "Hadley, Ike"].iloc[0]
    assert (hadley["event_rank"], hadley["percentile"], bool(hadley["is_best_round"])) == (1.0, 1.0, True)
    prev = rounds[(rounds["event_date"] == date(2026, 10, 18)) & (rounds["display_name"] == "Hadley, Ike")].iloc[0]
    assert prev["adjusted"] == 7.0 and not math.isnan(prev["residual"])
    events = frames.load_events(s).set_index("event_date")
    assert math.isnan(events.loc[THROWN_OUT_SUNDAY, "difficulty"])
    assert not math.isnan(events.loc[date(2026, 10, 18), "difficulty"])
    assert (events.loc[THROWN_OUT_SUNDAY, "median"], events.loc[THROWN_OUT_SUNDAY, "top_score"]) == (35.0, 43.0)
    assert s.execute(text("SELECT value FROM app_state WHERE key = 'skill_params'")).scalar_one_or_none() is not None
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics_core/test_skill_model.py tests/unit/analytics_core/test_round_metrics.py tests/integration/analytics_core/test_s30_skill_step.py tests/integration/thrown_out/test_thrown_out_skill_metrics.py -q`. Expected: `DataFrame.iloc[:, ...] values are different` in the skip test; `adjusted` 5.0 in the round-metrics test; params stored in the s30 test; `adjusted` 8.0 and residual not NaN in the world test. The two guards pass.

- [ ] **Step 3: Implement**

- `skill.py`: module-level `_excluded(group) -> bool` (`"stats_excluded" in group.columns and bool(group["stats_excluded"].eq(True).iloc[0])`); `_prepare` uses `held=bool(group["held"].iloc[0]) and not _excluded(group)`; the `run_skill_model` docstring adds "an optional `stats_excluded` column; a thrown-out event is treated like a non-held one".
- `s30_skill.py:83`: `counted = rounds["held"] & ~rounds["stats_excluded"].eq(True)`; burn-in uses `rounds.loc[counted, "event_date"].nunique() > skill.BURN_IN_HELD_EVENTS`; docstring "Thrown-out Sundays are not counted."
- `metrics.py`: `excluded` = the flag (`eq(True)`, all False when the column is absent); `"adjusted": (rounds["score"] - median).where(held & ~excluded)`; docstring "adjusted: NaN when not held or stats_excluded; field_median, ranks and percentile are kept on a thrown-out Sunday".

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (all pass). Regression: `cd backend && uv run pytest tests/unit/analytics_core tests/integration/analytics_core tests/integration/extras tests/integration/special -q` (`test_fx_pipeline_calibrates_on_the_real_fixture` unchanged). Backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/skill.py backend/src/sunday_clays/analytics/steps/s30_skill.py backend/src/sunday_clays/analytics/metrics.py backend/tests/unit/analytics_core/test_skill_model.py backend/tests/unit/analytics_core/test_round_metrics.py backend/tests/integration/analytics_core/test_s30_skill_step.py backend/tests/integration/thrown_out/test_thrown_out_skill_metrics.py` — `feat(analytics): skill and adjusted scores skip thrown-out Sundays` (+ trailer).

---

### Task T3a: Leaderboards, leaderboard history and records leave out thrown-out Sundays

**Depends on:** T2c.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/leaderboards.py:20-26` (imports), `:136-160` (`scaled_min_rounds`, `custom_min_rounds`), `:426-450` (`leaderboard`)
- Modify: `backend/src/sunday_clays/analytics/records.py:14-21` (imports), `:261-296` (`compute_records`)
- Modify: `backend/tests/unit/analytics/competition/conftest.py:15-25` (column lists), `:52-73` (`event`), `:113-148` (`rounds`, `_derive_event_fields`)
- Modify: `backend/tests/unit/analytics/records/test_records_unit.py:20-30` (column lists), `:41-78` (`World.event`, `World.shot`)
- Test: `backend/tests/unit/analytics/competition/test_leaderboard_thrown_out.py` (new), `backend/tests/unit/analytics/records/test_records_unit.py` (append)

**Interfaces:**
- Consumes: `stat_rounds`, `stat_events`, the `stats_excluded` columns (T2a); NULL `adjusted` (T2c).
- Produces: `leaderboards.SCORE_STAT_METRICS`; `FrameBuilder.event(..., stats_excluded=False)` (also through `day(**event_kw)`); records `World.event(..., excluded=False)`.

- [ ] **Step 1: Write the failing tests**

Builders first: competition `conftest.py` appends `"stats_excluded"` to `ROUND_COLUMNS` and `EVENT_COLUMNS`; `event()` stores `stats_excluded`; `rounds()` copies it onto each row; `_derive_event_fields` sets `adjusted = None` on an excluded event (mirrors D5). `test_records_unit.py` appends the column to both lists; `World.event(excluded=False)` sets it; `World.shot` copies it from the event row.

`test_leaderboard_thrown_out.py`:
```python
D1, D2, D3 = date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)
SEASON = LeaderboardPeriod.SEASON
M = LeaderboardMetric

def values(board): return dict(zip(board.rows["shooter_id"], board.rows["value"], strict=True))

def test_score_boards_leave_out_a_thrown_out_sunday_and_count_boards_keep_it(fb):
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 40, 2: 30}).day(D2, {1: 50, 2: 20}, stats_excluded=True).day(D3, {1: 44, 2: 36})
    frames = fb.frames()
    avg = leaderboard(frames, SEASON, M.AVG_SCORE, D3)
    assert values(avg) == {1: 42.0, 2: 33.0} and avg.rows["n_rounds"].tolist() == [2, 2]
    assert values(leaderboard(frames, SEASON, M.BEST_SCORE, D3)) == {1: 44.0, 2: 36.0}
    assert values(leaderboard(frames, SEASON, M.AVG_ADJUSTED, D3)) == {1: 4.5, 2: -4.5}
    assert values(leaderboard(frames, SEASON, M.WINS, D3)) == {1: 3.0, 2: 0.0}
    assert values(leaderboard(frames, SEASON, M.ROUNDS, D3)) == {1: 3.0, 2: 3.0}
    assert values(leaderboard(frames, SEASON, M.EVENTS, D3)) == {1: 3.0, 2: 3.0}

def test_the_average_board_minimum_counts_only_sundays_in_the_average(fb):
    fb.shooter(1, "Ace, Amy")
    days = [D1 + timedelta(weeks=i) for i in range(5)]
    for i, d in enumerate(days):
        fb.day(d, {1: 40}, stats_excluded=i in (1, 2, 3))
    events = fb.events()
    assert scaled_min_rounds(events, SEASON, days[-1]) == 1   # E = 2 (5 would give 2)
    assert custom_min_rounds(events, days[0], days[-1]) == 1

def test_rating_gain_eligibility_counts_thrown_out_rounds(fb):  # guard
    fb.shooter(1, "Ace, Amy")
    before = [date(2025, 10, 5) + timedelta(weeks=i) for i in range(10)]
    inside = [date(2026, 2, 15), date(2026, 2, 22), date(2026, 3, 1)]
    for i, d in enumerate(before + inside):
        fb.day(d, {1: 40}, stats_excluded=i == 4)
    fb.rating(1, before[-1], 30.0).rating(1, inside[-1], 33.0)
    board = leaderboard(fb.frames(), SEASON, M.RATING_GAIN, inside[-1])
    assert [(r.shooter_id, r.value, r.n_rounds) for r in board.records()] == [(1, 3.0, 3)]

def test_history_keeps_a_frame_for_a_thrown_out_sunday(fb):
    fb.shooter(1, "Ace, Amy").day(D1, {1: 40}).day(D2, {1: 50}, stats_excluded=True).day(D3, {1: 44})
    history = leaderboard_history(fb.frames(), SEASON, M.AVG_SCORE, top=3, date_from=D1, date_to=D3)
    assert [f.event_date for f in history] == [D1, D2, D3]
    assert [[(r.value, r.n_rounds) for r in f.rows] for f in history] == [[(40.0, 1)], [(40.0, 1)], [(42.0, 2)]]
```
`test_records_unit.py`:
```python
def test_thrown_out_sundays_leave_score_records_but_keep_attendance() -> None:
    w = World().event(D[1], excluded=True)
    w.shot(D[0], 1, 40, adjusted=1.0).shot(D[1], 1, 50).shot(D[2], 1, 46, adjusted=2.0)
    r = w.records()
    assert [x.value for x in r.highest_scores] == [46.0, 40.0]
    assert r.perfect_rounds == ()
    assert [x.value for x in r.biggest_adjusted] == [2.0, 1.0]
    assert [(j.prev_event_date, j.event_date, j.value) for j in r.biggest_jumps] == [(D[0], D[2], 6.0)]
    assert [x.value for x in r.most_events] == [3.0]
    assert [x.value for x in r.longest_streaks] == [3.0]

def test_the_rating_record_floor_counts_thrown_out_rounds() -> None:  # guard
    w = _five_rounds(World().event(D[2], excluded=True), 1)
    w.rating(1, D[4], 33.0)
    assert [(r.shooter_id, r.event_date, r.value) for r in w.records().highest_ratings] == [(1, D[4], 33.0)]
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_thrown_out.py tests/unit/analytics/records/test_records_unit.py -q`. Expected: `{1: 44.666…}` vs `{1: 42.0, …}`; `2 != 1`; history frame 2 shows `(45.0, 2)`; records `[50.0, 46.0, 40.0]` and the jump `(D[0], D[1], 10.0)`. The two guards pass.

- [ ] **Step 3: Implement**

- `leaderboards.py`: import `stat_events`, `stat_rounds`; add `SCORE_STAT_METRICS`; `scaled_min_rounds` and `custom_min_rounds` start with `events = stat_events(events)`; in `leaderboard()`'s round branch, `window = _round_filters(_window(frames.rounds, start, end), filters)`, then `window = stat_rounds(window)` when `metric in SCORE_STAT_METRICS`. `_rating_gain`, the EVENTS appearances branch and count metrics are unchanged. `leaderboard_history.py` needs no change.
- `records.py` `compute_records`: `scored = stat_rounds(past_rounds)` feeds `perfect`, `adjusted` and the score records; `jumps = _jumps(scored, stat_events(past_events), names, limit)`; `names`, `attended`, `streak` and `_highest_ratings` keep all rounds.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/competition tests/unit/analytics/records tests/integration/api/test_leaderboards_api.py tests/integration/api/test_leaderboard_history_api.py tests/integration/api/test_records_api.py -q` (all pass). Backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/leaderboards.py backend/src/sunday_clays/analytics/records.py backend/tests/unit/analytics/competition/conftest.py backend/tests/unit/analytics/competition/test_leaderboard_thrown_out.py backend/tests/unit/analytics/records/test_records_unit.py` — `feat(analytics): leaderboards and records leave out thrown-out Sundays` (+ trailer).

---

### Task T3b: Profile stats, splits, odometer, PBs, Sunday notables and the summary card

**Depends on:** T2c. Owns `shooters.py` stats (`ShooterStatsOut`/`SplitOut.n_excluded`, `shooter_stats`, `odometer`, `personal_bests`, `splits`) and `events.py:event_notables`.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/profile.py:77-169` (`floor_ceiling`, `bad_day_rate`, `form`, `event_values`, `rust_effect`)
- Modify: `backend/src/sunday_clays/api/routes/shooters.py:68-77` (`ShooterStatsOut`), `:162-169` (`SplitOut`), `:193-206`, `:209-234`, `:237-264`, `:297-317`
- Modify: `backend/src/sunday_clays/api/routes/events.py:333-358` (`event_notables`)
- Modify: `backend/src/sunday_clays/analytics/summary.py:68-79` (`_pbs_set`), `:94-130` (`compute_summary`)
- Modify: `backend/tests/unit/analytics/test_shooter_summary.py:18-49` (`frames_for`, `run` gain `excluded`)
- Modify (typed mocks `pnpm typecheck` flags for `n_excluded`): `frontend/src/features/shooters/mocks.ts`, `frontend/src/features/home/mocks.ts` and the inline literals it names
- Test: `backend/tests/unit/analytics_core/test_thrown_out_shooter_stats.py` (new), `backend/tests/unit/analytics/test_shooter_summary.py` (append)

**Interfaces:**
- Consumes: `stat_rounds`; the `stats_excluded`/`held` round columns; `personal_best.is_new_pb` (unchanged).
- Produces: `ShooterStatsOut.n_excluded`, `SplitOut.n_excluded`; `event_values` numbering; `splits()` omitting an unscored key; odometer `hit_pct` over scored rounds; PBs never from an excluded Sunday; notables per the contract.

- [ ] **Step 1: Write the failing tests**

`test_thrown_out_shooter_stats.py` (`make_rounds`; imports from `api.routes.shooters`, `api.routes.events`, `analytics.profile`):
```python
AS_OF = date(2026, 9, 27)
AUG30, SEP6, SEP13, SEP20 = date(2026, 8, 30), date(2026, 9, 6), date(2026, 9, 13), date(2026, 9, 20)

def _profile_rounds(make_rounds):
    return make_rounds([
        {"event_date": AUG30, "shooter_id": 1, "score": 50, "stats_excluded": True, "is_best_round": True, "event_rank": 2.0, "percentile": 75.0},
        {"event_date": SEP6, "shooter_id": 1, "score": 40, "is_best_round": True, "event_rank": 1.0, "percentile": 100.0, "adjusted": 5.0},
        {"event_date": SEP13, "shooter_id": 1, "score": 50, "stats_excluded": True, "is_best_round": True, "event_rank": 1.0, "percentile": 100.0},
        {"event_date": SEP20, "shooter_id": 1, "score": 30, "is_best_round": True, "event_rank": 3.0, "percentile": 50.0, "adjusted": -5.0},
    ], stats_excluded=False)

def test_shooter_stats_keep_official_counts_and_leave_scores_out(make_rounds):
    s = shooter_stats(_profile_rounds(make_rounds))
    assert (s.n_rounds, s.n_events, s.n_excluded) == (4, 4, 2)
    assert (s.avg_score, s.median_score, s.best_score, s.avg_adjusted) == (35.0, 35.0, 40, 0.0)
    assert (s.wins, s.podiums, s.avg_percentile) == (2, 4, 81.25)

def test_splits_count_every_round_and_drop_a_key_with_none_in_the_average(make_rounds):
    rounds = _profile_rounds(make_rounds)
    assert splits(rounds, SplitBy.YEAR) == [SplitOut(key="2026", n_rounds=4, n_events=4, n_excluded=2, avg=35.0, median=35.0, best=40, avg_adjusted=0.0)]
    assert splits(rounds, SplitBy.MONTH) == [SplitOut(key="2026-09", n_rounds=3, n_events=3, n_excluded=1, avg=35.0, median=35.0, best=40, avg_adjusted=0.0)]

def test_odometer_counts_clays_but_hit_rate_and_pbs_leave_thrown_out_sundays(make_rounds):
    rounds = _profile_rounds(make_rounds)
    o = odometer(rounds, None, 0)
    assert (o.clays_thrown, o.clays_broken, o.rounds, o.hit_pct) == (200, 170, 4, 0.7)
    assert [(p.scope, p.key, p.score, p.event_date) for p in personal_bests(rounds)] == [("overall", "all", 40, SEP6), ("year", "2026", 40, SEP6)]
    assert personal_bests(rounds.loc[rounds["stats_excluded"]]) == []

def test_shooter_insights_keep_placings_and_leave_scores_out(make_rounds):
    history = pd.DataFrame(columns=["shooter_id", "event_date", "mu", "var"])
    shooters = pd.DataFrame({"shooter_id": [1], "left_censored": [False]})
    ins = profile.shooter_insights(_profile_rounds(make_rounds), history, shooters, 1, AS_OF)
    assert (ins.n_rounds, ins.wins, ins.podiums, ins.avg_percentile) == (4, 2, 4, 81.25)
    assert (ins.floor, ins.ceiling, ins.recent_n) == (pytest.approx(31.0), pytest.approx(39.0), 2)

def test_learning_curve_k_counts_a_thrown_out_sunday_but_plots_no_value(make_rounds):
    rounds = make_rounds([
        {"event_date": SEP6, "shooter_id": 1, "score": 40, "adjusted": 2.0},
        {"event_date": SEP13, "shooter_id": 1, "score": 50, "stats_excluded": True},
        {"event_date": SEP20, "shooter_id": 1, "score": 44, "adjusted": 4.0},
    ], stats_excluded=False)
    curve = profile.learning_curve(rounds, pd.DataFrame({"shooter_id": [1], "left_censored": [False]}), 1)
    assert [(p.k, p.value) for p in curve] == [(1, 2.0), (3, 4.0)]

def test_residual_stats_and_rust_skip_thrown_out_rounds_but_not_the_attendance(make_rounds):
    day = lambda w: date(2026, 1, 4) + timedelta(weeks=w)
    five = [{"event_date": day(w), "shooter_id": 1, "score": 40, "residual": r} for w, r in zip(range(5), (0.0, 0.0, 0.0, 0.0, -6.0), strict=True)]
    late = {"event_date": day(5), "shooter_id": 1, "score": 50, "residual": -10.0, "stats_excluded": True}
    rounds = make_rounds([*five, late], stats_excluded=False)
    assert profile.bad_day_rate(rounds) == pytest.approx(0.2)
    assert profile.form(rounds) == (pytest.approx(-1.2), "steady")
    rust = make_rounds([
        {"event_date": day(0), "shooter_id": 1, "score": 40, "residual": 2.0},
        {"event_date": day(5), "shooter_id": 1, "score": 40, "residual": -4.0},
        {"event_date": day(6), "shooter_id": 1, "score": 50, "residual": 10.0, "stats_excluded": True},
        {"event_date": day(7), "shooter_id": 1, "score": 40, "residual": 0.0},
    ], stats_excluded=False)
    assert profile.rust_effect(rust) == (pytest.approx(-5.0), 1)
    no_layoff = make_rounds([
        {"event_date": day(0), "shooter_id": 2, "score": 40, "residual": 0.0},
        {"event_date": day(3), "shooter_id": 2, "score": 50, "stats_excluded": True},
        {"event_date": day(4), "shooter_id": 2, "score": 40, "residual": 3.0},
    ], stats_excluded=False)
    assert profile.rust_effect(no_layoff) == (None, 0)  # guard part: day 3 is attendance, no 28-day gap

def test_pb_notables_skip_a_thrown_out_sunday_and_its_score(make_rounds):
    days = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(7)]
    rounds = make_rounds([{"event_date": d, "shooter_id": 1, "score": s, "stats_excluded": i == 5}
                          for i, (d, s) in enumerate(zip(days, (40, 40, 40, 40, 40, 50, 45), strict=True))], is_best_round=True)
    shooters = pd.DataFrame({"shooter_id": [1], "display_name": ["Hadley, Ike"], "first_event": [days[0]], "left_censored": [False]})
    assert event_notables(rounds, shooters, days[5]) == []
    assert [(n.kind, n.detail) for n in event_notables(rounds, shooters, days[6])] == [("pb", "New personal best 45 (was 40)")]
```
`test_shooter_summary.py`: `frames_for` and `run` gain `excluded: tuple[int, ...] = ()`; `frames_for` sets `rounds["stats_excluded"] = [d in {sunday(i) for i in excluded} for d in rounds["event_date"]]`. Append:
```python
def test_a_thrown_out_sunday_counts_as_rounds_but_not_in_average_best_or_pbs() -> None:
    history = {0: [40], 1: [40], 2: [40], 3: [40], 4: [40], 5: [50], 6: [45], 7: [47]}
    result = run(history, None, sunday(7), excluded=(5,))
    assert (result.sundays, result.rounds) == (8, 8)
    assert result.average == 41.7
    assert result.best == summary.BestRound(47, sunday(7))
    assert result.pbs_set == 2

def test_both_doubleheader_rounds_on_a_thrown_out_sunday_count_toward_the_pb_gate() -> None:  # Review Focus 2
    history = {0: [40], 1: [40], 2: [40], 3: [50, 49], 4: [45]}
    result = run(history, None, sunday(4), excluded=(3,))
    assert (result.sundays, result.rounds, result.pbs_set) == (5, 6, 1)
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics_core/test_thrown_out_shooter_stats.py tests/unit/analytics/test_shooter_summary.py -q`. Expected: Pydantic rejects `n_excluded`; `hit_pct` 0.85; curve `k` `[1, 2]`; `bad_day_rate` 0.333; a day-5 notable `pb 50 (was 40)`; summary `average 42.8`, `pbs_set 1` and, for the doubleheader, `pbs_set 0`. Only the `no_layoff` assertion holds on base.

- [ ] **Step 3: Implement**

- `profile.py`: `floor_ceiling`, `bad_day_rate`, `form` start with `rounds = stat_rounds(rounds)`; `event_values` counts rows where `adjusted.notna() | (held.eq(True) & stats_excluded.eq(True))`, groups mean `adjusted` per (shooter, date), sets `k = cumcount() + 1`, then drops NaN values; `rust_effect` keeps `_post_layoff_mask` over all rows and uses `has_residual = residual.notna() & ~stats_excluded.eq(True)`; `shooter_insights` unchanged.
- `shooters.py`: `n_excluded: int` after `n_events` in both models; `shooter_stats` reads averages/median/best/avg_adjusted from `scored = frames.stat_rounds(rounds)` (None when empty) and placings from all rounds, `n_excluded = len(rounds) - len(scored)`; `splits` skips a group whose `scored` is empty, `n_rounds`/`n_events` from the group; `odometer` `hit_pct = None if scored.empty else scored.score.sum() / (len(scored) * TARGETS_PER_ROUND)`; `personal_bests` starts with `rounds = frames.stat_rounds(rounds)`.
- `events.py:event_notables`: no PB notables when the day is excluded; `n_prior` = all earlier rounds per shooter; `previous` = max over `frames.stat_rounds(earlier)` (None if none). First-timers unchanged.
- `summary.py`: `compute_summary` reads `average`/`best` from `stat_rounds(window)`, `rounds=len(window)`; `_pbs_set` on an all-excluded day adds `len(scores)` to `n_before` and continues without testing or updating `best_before`.
- Frontend: `cd frontend && pnpm typecheck`; add `n_excluded: 0` to each literal it names; no component change.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics_core tests/unit/analytics/test_shooter_summary.py tests/integration/analytics_core/test_shooters_routes.py tests/integration/analytics_core/test_shooter_insights_route.py tests/integration/analytics_core/test_events_routes.py tests/integration/api/test_shooter_summary_api.py -q`; backend gate; `cd frontend && pnpm typecheck && pnpm lint && pnpm exec vitest --run`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/profile.py backend/src/sunday_clays/analytics/summary.py backend/src/sunday_clays/api/routes/shooters.py backend/src/sunday_clays/api/routes/events.py backend/tests/unit/analytics_core/test_thrown_out_shooter_stats.py backend/tests/unit/analytics/test_shooter_summary.py frontend/src` — `feat(analytics): profile stats, PBs and summary leave out thrown-out Sundays` (+ trailer).

---

### Task T3c: Club trends, first rounds and weather effects (attendance probabilities unchanged)

**Depends on:** T2c. Owns the weather SQL/columns, `WeatherEvent(Out).stats_excluded`, `EventTrend(Out)`.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/club_insights.py:70-78` (`EventTrend`), `:271-295` (`event_trends`), `:298-314` (`seasonality`)
- Modify: `backend/src/sunday_clays/api/routes/club_insights.py:64-71` (`EventTrendOut`)
- Modify: `backend/src/sunday_clays/analytics/cohorts.py:102-117` (`first_round_scores`)
- Modify: `backend/src/sunday_clays/analytics/weather_effects.py:61-85` (`_WEATHER_EVENTS_SQL`, `_EVENT_COLUMNS`), `:154-177` (`WeatherEvent`), `:211-220` (`fit_club_model`), `:263-270` (`band_summary`), `:353-356` (`shooter_sensitivity`), `:391-423` (`weather_event_rows`), `:431-439` (`load_weather_events`)
- Modify: `backend/src/sunday_clays/api/routes/weather.py:20-42` (`WeatherEventOut`)
- Modify: `backend/tests/unit/analytics/test_first_round_scores.py:8-9` (`_rounds`), `backend/tests/unit/extras/test_extras_weather_effects.py:31-57,327-345` (`_events` base, `_sensitivity_rounds`)
- Modify (typed mocks for `stats_excluded`): `frontend/src/features/weather/mocks.ts` (`event()` :4), `frontend/src/features/club/mocks.ts` (trend events), inline literals `pnpm typecheck` names; `frontend/src/features/club/charts.ts:110,112` only if typecheck flags them (see Step 3)
- Test: `backend/tests/unit/analytics_core/test_club_thrown_out.py` (new), appends to the two unit files above, `backend/tests/integration/thrown_out/test_thrown_out_weather.py` (new), `backend/tests/integration/extras/test_extras_weather_routes.py`, `backend/tests/integration/analytics_core/test_club_insights_routes.py`

**Interfaces:**
- Consumes: `stat_rounds`, `stat_events`, the `stats_excluded` columns (T2a); `fx_thrown_out_session` (T2a).
- Produces: `EventTrend`/`EventTrendOut.stats_excluded`, rolling fields `float | None`; `WeatherEvent`/`WeatherEventOut.stats_excluded`; `weather_effects._EVENT_COLUMNS += "stats_excluded"`. `predictions._scored_events` and `attendance_probs` are **not** changed.

- [ ] **Step 1: Write the failing tests**

`test_club_thrown_out.py`:
```python
W = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(3)]

def _events(make_events):
    return make_events([
        {"event_date": W[0], "top_score": 40.0, "median": 30.0, "difficulty": 1.0, "stats_excluded": False},
        {"event_date": W[1], "top_score": 50.0, "median": 40.0, "difficulty": math.nan, "stats_excluded": True},
        {"event_date": W[2], "top_score": 44.0, "median": 34.0, "difficulty": 3.0, "stats_excluded": False},
    ])

def test_event_trends_keep_the_sunday_marked_but_out_of_every_rolling_line(make_events):
    trend = ci.event_trends(_events(make_events), W[2])
    assert [(t.event_date, t.stats_excluded, t.top_score, t.top_score_rolling8, t.median_rolling8, t.difficulty_rolling8) for t in trend] == [
        (W[0], False, 40, 40.0, 30.0, 1.0), (W[1], True, 50, None, None, None), (W[2], False, 44, 42.0, 32.0, 2.0)]
    assert EventTrendOut.model_validate(asdict(trend[1])).stats_excluded is True

def test_seasonality_counts_the_sunday_but_leaves_its_median_out(make_events):
    jan = ci.seasonality(_events(make_events), W[2])[0]
    assert (jan.month, jan.n_events, jan.mean_median) == (1, 3, 32.0)
```
`test_first_round_scores.py`: `_rounds` pads 3-tuples with `False` and gains `"stats_excluded"`. Append:
```python
def test_a_shooter_whose_first_sunday_was_thrown_out_is_left_out() -> None:
    rounds = _rounds((1, date(2025, 1, 5), 50, True), (1, date(2025, 1, 12), 33), (2, date(2025, 1, 12), 28))
    assert first_round_scores(rounds, None, None) == [28]
```
`test_extras_weather_effects.py`: add `"stats_excluded": False` to the `_events` base dict and to each `_sensitivity_rounds` row. Append:
```python
def test_band_summary_leaves_out_a_thrown_out_sunday() -> None:
    events = _events([{"temp_f": 60.0, "difficulty": 1.0}, {"temp_f": 61.0, "difficulty": float("nan"), "stats_excluded": True}])
    rounds = pd.DataFrame({"event_date": events["event_date"].tolist(), "score": [40, 50]})
    temp = [s for s in band_summary(events, rounds) if s.dimension == "temp_band"]
    assert [(s.band, s.n_events, s.n_rounds, s.mean_score, s.mean_difficulty) for s in temp] == [(frames.temp_band(60.0), 1, 1, 40.0, 1.0)]

def test_fit_ignores_thrown_out_sundays() -> None:
    events = _events([{"temp_f": t, "difficulty": 0.1 * t} for t in (40.0, 50.0, 60.0, 70.0)]
                     + [{"temp_f": 55.0, "difficulty": 9.0, "stats_excluded": True}])
    model = fit_club_model(events, ("temp_f",))
    assert model is not None and model.n_events == 4 and model.coef == pytest.approx((0.0, 0.1))

def test_sensitivity_leaves_out_thrown_out_rounds() -> None:
    rounds = _sensitivity_rounds({1: (10, 0.1)})
    rounds.loc[rounds.index[-1], "stats_excluded"] = True
    assert shooter_sensitivity(rounds, SCALES).shooters == ()

def test_weather_rows_keep_the_official_numbers_and_flag_the_sunday() -> None:
    events = _events([{}, {"stats_excluded": True, "median": 40.0, "top_score": 50.0}])
    days = events["event_date"].tolist()
    rows = weather_event_rows(events, pd.DataFrame({"event_date": [days[1], days[1]], "score": [50, 30]}))
    assert [(r.stats_excluded, r.n_rounds, r.median, r.top_score) for r in rows] == [(False, 0, 35.0, 45), (True, 2, 40.0, 50)]
    assert WeatherEventOut.model_validate(asdict(rows[1])).stats_excluded is True
```
`test_thrown_out_weather.py` (reader tests folded from the old T2b; local `THROWN_OUT_SUNDAY`):
```python
def test_weather_event_frame_carries_stats_excluded(fx_thrown_out_session):
    weather = weather_effects.load_weather_events(fx_thrown_out_session)
    assert len(weather) == 10
    assert weather.loc[weather["stats_excluded"], "event_date"].tolist() == [THROWN_OUT_SUNDAY]

def test_attendance_probabilities_still_count_the_thrown_out_sunday(fx_thrown_out_session):  # guard (spec §4)
    s = fx_thrown_out_session
    probs = predictions.attendance_probs(frames.load_rounds(s), predictions._scored_events(s), date(2026, 11, 1))
    assert len(probs) == 9 and set(probs.values()) == {10 / 13}
```
Route tests (pass-through, moved here from the API lane):
```python
# test_extras_weather_routes.py
def test_weather_events_flag_a_thrown_out_sunday(fx_session, fx_viewer_client):
    _add_seven(fx_session)
    fx_session.execute(text("UPDATE events SET stats_excluded = true WHERE event_date = '2026-09-13'"))
    clear_cache()
    by_date = {r["event_date"]: r for r in fx_viewer_client.get("/api/weather/events").json()}
    assert (by_date["2026-09-13"]["stats_excluded"], by_date["2026-09-27"]["stats_excluded"]) == (True, False)

# test_club_insights_routes.py
def test_trends_keep_a_thrown_out_sunday_flagged(fx_session, fx_viewer_client):
    fx_session.execute(text("UPDATE events SET stats_excluded = true WHERE event_date = '2026-09-13'"))
    clear_cache()
    events = {e["event_date"]: e for e in fx_viewer_client.get("/api/club/trends").json()["events"]}
    assert (events["2026-09-13"]["stats_excluded"], events["2026-09-27"]["stats_excluded"]) == (True, False)
    assert events["2026-09-13"]["median_rolling8"] is None
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics_core/test_club_thrown_out.py tests/unit/analytics/test_first_round_scores.py tests/unit/extras/test_extras_weather_effects.py tests/integration/thrown_out/test_thrown_out_weather.py tests/integration/extras/test_extras_weather_routes.py tests/integration/analytics_core/test_club_insights_routes.py -q`. Expected: `EventTrend` has no `stats_excluded`; `mean_median` 34.666…; first rounds `[28, 50]`; `band_summary` `(…, 2, 2, 45.0, 1.0)`; `n_events` 5; sensitivity lists shooter 1; `KeyError: 'stats_excluded'` on the weather frame and routes. The attendance guard passes.

- [ ] **Step 3: Implement**

- `club_insights.py`: `EventTrend.stats_excluded: bool`, rolling fields `float | None`; `event_trends` computes the rolling-8 over `held.loc[~excluded]` and reindexes so excluded rows map to None; `seasonality` means read `stat_events(in_month)["median"].dropna()` while `n_events` and head counts stay. `regulars`, `guest_conversion`, `parity`, `yearly_trends` unchanged.
- `api/routes/club_insights.py` `EventTrendOut`: `stats_excluded: bool`; rolling fields `float | None`.
- `cohorts.first_round_scores`: after `firsts = …`, `firsts = firsts.loc[~firsts["stats_excluded"].eq(True)]` (the first date still comes from all rounds: no fallback to the second Sunday).
- `weather_effects.py`: `_WEATHER_EVENTS_SQL` selects `e.stats_excluded` after `e.results_complete`, `_EVENT_COLUMNS` matches, `load_weather_events` casts `.eq(True)`; `fit_club_model` starts with `events = frames.stat_events(events)` (covers `club_regression`, `predictions.choose_difficulty`, `effects().model`); `band_summary` uses `scored = frames.stat_events(events[events["has_scores"].astype(bool)])`; `shooter_sensitivity` uses `frames.stat_rounds(rounds).dropna(subset=needed)`; `WeatherEvent.stats_excluded` from the row, official median/top kept. `turnout`, `z_scales`, `Effects.n_events` unchanged.
- `api/routes/weather.py` `WeatherEventOut.stats_excluded: bool`.
- Frontend: `cd frontend && pnpm typecheck`; add `stats_excluded: false` to the literals it names. If it flags `club/charts.ts` `round1(e.median_rolling8)`/`round1(e.top_score_rolling8)` (now nullable), switch those two calls to the existing null-safe `r1`; nothing else in the component changes.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics_core tests/unit/analytics/test_first_round_scores.py tests/unit/extras tests/integration/thrown_out tests/integration/analytics_core/test_club_insights_routes.py tests/integration/analytics_core/test_club_first_rounds.py tests/integration/extras/test_extras_weather_routes.py tests/integration/extras/test_extras_predictions_route.py -q`; backend gate; `cd frontend && pnpm typecheck && pnpm lint && pnpm exec vitest --run`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/club_insights.py backend/src/sunday_clays/api/routes/club_insights.py backend/src/sunday_clays/analytics/cohorts.py backend/src/sunday_clays/analytics/weather_effects.py backend/src/sunday_clays/api/routes/weather.py backend/tests/unit/analytics_core/test_club_thrown_out.py backend/tests/unit/analytics/test_first_round_scores.py backend/tests/unit/extras/test_extras_weather_effects.py backend/tests/integration/thrown_out/test_thrown_out_weather.py backend/tests/integration/extras/test_extras_weather_routes.py backend/tests/integration/analytics_core/test_club_insights_routes.py frontend/src` — `feat(analytics): club trends and weather effects leave out thrown-out Sundays` (+ trailer).

---

### Task T3d: Year in Review and On this day

**Depends on:** T2c. Owns the yir SQL/columns and the Yir Out fields.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/yir.py:23-41` (`_EVENTS_SQL`, `_EVENT_COLUMNS`), `:65-177` (dataclasses), `:198-211` (`year_totals`), `:229-269` (`club_year`), `:272-281` (`pb_days`), `:284-296` (`_shooter_totals`), `:304-352` (`shooter_year`), `:362-394` (`on_this_day`), `:431-457` (`load_yir_frames`)
- Modify: `backend/src/sunday_clays/api/routes/yir.py:26-41` (`YirTotalsOut`, `YirTopRoundOut`), `:73-79` (`YirShooterTotalsOut`), `:119-127` (`OnThisDayItemOut`)
- Modify: `backend/tests/unit/extras/test_extras_yir.py:5` (`timedelta`), `:42-87` (`_world` gains `thrown_out`), `:136,146,163,204,213,222,233` (append `, 0` to each positional `YearTotals(...)`/`ShooterTotals(...)`)
- Modify (typed mocks): `frontend/src/features/yir/mocks.ts` and the inline literals `pnpm typecheck` names
- Test: `backend/tests/unit/extras/test_extras_yir.py` (append), `backend/tests/integration/thrown_out/test_thrown_out_yir.py` (new), `backend/tests/integration/extras/test_extras_yir_routes.py`

**Interfaces:**
- Consumes: `stat_rounds`, `stat_events`, the `stats_excluded` columns.
- Produces: `YearTotals.n_excluded`, `ShooterTotals.n_excluded` (last positional), `TopRound.stats_excluded = False`, `OnThisDayItem.stats_excluded`; `YirTotalsOut.n_excluded`, `YirShooterTotalsOut.n_excluded`, `YirTopRoundOut.stats_excluded`, `OnThisDayItemOut.stats_excluded`; `yir._EVENT_COLUMNS += "stats_excluded"`.

- [ ] **Step 1: Write the failing tests**

`_world` gains `thrown_out: frozenset[date] = frozenset()` and sets `stats_excluded` on its rounds and events. Append:
```python
TO = _world(
    [(B1, 1, 40, True, 1.0), (B1, 2, 30, True, 2.0), (B2, 1, 50, True, 1.0), (B2, 2, 49, True, 2.0),
     (B4, 1, 44, True, 2.0), (B4, 2, 45, True, 1.0)],
    [(B1, True, True, 10.0, 35.0, 1.0), (B2, True, True, 12.0, 49.5, NAN), (B4, True, True, 14.0, 44.5, -1.0)],
    thrown_out=frozenset({B2}),
)

def test_club_year_counts_a_thrown_out_sunday_but_leaves_its_scores_out() -> None:
    year = club_year(TO, 2025)
    assert year.totals == YearTotals(2025, 3, 3, 6, 2, 300, 258, 39.75, 2)
    assert year.perfect_rounds == 0
    assert year.top_rounds == (TopRound(2, "Baker, Bo", B4, 45),)
    assert year.months[0] == MonthStat(month=1, events=2, rounds=4, avg_score=35.0)
    assert (year.hardest, year.easiest) == (EventStat(B1, 1.0), EventStat(B4, -1.0))
    out = YirClubOut.model_validate({**asdict(year), "years": [2025]})
    assert (out.totals.n_excluded, out.top_rounds[0].stats_excluded) == (2, False)

def test_shooter_year_counts_wins_but_leaves_out_the_score() -> None:
    year = shooter_year(TO, 1, 2025)
    assert year.totals == ShooterTotals(2025, 3, 3, 150, 134, 42.0, 1)
    assert year.best == TopRound(1, "Able, Al", B4, 44)
    assert (year.wins, year.podiums) == (2, 3)
    assert year.months[0] == ShooterMonth(month=1, rounds=2, avg_score=40.0, club_avg_score=35.0)
    assert YirShooterOut.model_validate(asdict(year)).totals.n_excluded == 1

def test_a_shooter_whose_only_round_was_thrown_out_has_no_average() -> None:  # Review Focus 3
    only = _world([(B1, 1, 40, True, 1.0), (B2, 3, 45, True, 2.0)],
                  [(B1, True, True, 10.0, 40.0, 1.0), (B2, True, True, 12.0, 45.0, NAN)], thrown_out=frozenset({B2}))
    totals = shooter_year(only, 3, 2025).totals
    assert (totals.rounds, totals.n_excluded, totals.avg_score) == (1, 1, None)

def test_pb_days_count_thrown_out_rounds_as_earlier_but_never_as_a_pb() -> None:
    days = [date(2025, 1, 5) + timedelta(weeks=i) for i in range(8)]
    rounds = pd.DataFrame({"event_date": days, "score": [40, 40, 40, 40, 40, 50, 45, 47],
                           "stats_excluded": [False] * 5 + [True, False, False]})
    assert pb_days(rounds) == (PbDay(days[6], 45), PbDay(days[7], 47))

def test_pb_days_count_both_doubleheader_rounds_of_a_thrown_out_sunday() -> None:  # Review Focus 2
    d = [date(2025, 1, 5) + timedelta(weeks=i) for i in range(5)]
    rounds = pd.DataFrame({"event_date": [d[0], d[1], d[2], d[3], d[3], d[4]], "score": [40, 40, 40, 50, 49, 45],
                           "stats_excluded": [False, False, False, True, True, False]})
    assert pb_days(rounds) == (PbDay(d[4], 45),)

def test_on_this_day_flags_a_thrown_out_sunday_with_its_official_numbers() -> None:
    items = on_this_day(TO, date(2026, 1, 19))
    assert [(i.years_ago, i.event_date, i.stats_excluded, i.top_score, i.median) for i in items] == [(1, B2, True, 50, 49.5)]
    assert items[0].winners == (Winner(1, "Able, Al", 50),)
    assert OnThisDayItemOut.model_validate(asdict(items[0])).stats_excluded is True
```
`test_thrown_out_yir.py`:
```python
def test_yir_event_frame_carries_stats_excluded(fx_thrown_out_session):
    events = load_yir_frames(fx_thrown_out_session).events
    assert events.loc[events["stats_excluded"], "event_date"].tolist() == [THROWN_OUT_SUNDAY]
```
`test_extras_yir_routes.py` (moved here from the API lane):
```python
EXCLUDED = "2026-09-13"

def test_yir_counts_a_thrown_out_sunday_and_says_how_many_rounds_are_left_out(fx_session, fx_viewer_client):
    before = _ok(fx_viewer_client, "/api/yir/2026")["totals"]
    ike = fx_session.execute(text("SELECT shooter_id FROM rounds WHERE event_date = :d AND name_key = 'hadley ike'"), {"d": EXCLUDED}).scalar_one()
    ike_rounds = fx_session.execute(text("SELECT count(*) FROM rounds WHERE event_date = :d AND shooter_id = :s"), {"d": EXCLUDED, "s": ike}).scalar_one()
    fx_session.execute(text("UPDATE events SET stats_excluded = true WHERE event_date = :d"), {"d": EXCLUDED})
    clear_cache()
    club = _ok(fx_viewer_client, "/api/yir/2026")
    assert (club["totals"]["rounds"], club["totals"]["n_excluded"]) == (before["rounds"], 13)
    assert {r["stats_excluded"] for r in club["top_rounds"]} <= {False}
    assert _ok(fx_viewer_client, f"/api/yir/2026/shooters/{ike}")["totals"]["n_excluded"] == ike_rounds
    (item, *_) = _ok(fx_viewer_client, "/api/on-this-day", {"date": "2027-09-13"})["items"]
    assert (item["event_date"], item["stats_excluded"]) == (EXCLUDED, True)
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/extras/test_extras_yir.py tests/integration/thrown_out/test_thrown_out_yir.py tests/integration/extras/test_extras_yir_routes.py -q`. Expected: `TypeError: … takes 9 positional arguments but 10 were given` (8 for `ShooterTotals`) on old and new assertions; `pb_days` `(PbDay(days[5], 50),)` and, for the doubleheader, `()`; no `stats_excluded` on `OnThisDayItem`; `KeyError: 'stats_excluded'` on the frame and `'n_excluded'` on the route.

- [ ] **Step 3: Implement** (in `yir.py` unless noted)

- Loading: `_EVENTS_SQL` selects `e.stats_excluded` before `e.kind`, `_EVENT_COLUMNS` matches; `load_yir_frames` keeps the rounds column and casts `events["stats_excluded"].eq(True)`.
- Dataclasses: `n_excluded: int` last on `YearTotals`/`ShooterTotals`; `TopRound.stats_excluded: bool = False`; `OnThisDayItem.stats_excluded: bool`.
- `year_totals`/`_shooter_totals`: `avg_score = _mean(stat_rounds(r)["score"])`, `n_excluded = len(r) - len(scored)`; rounds, clays, events official.
- `club_year`: `top` and `perfect_rounds` from `stat_rounds(rounds)`; `MonthStat.avg_score` from `stat_rounds(group)` with `rounds=len(group)`; `held = stat_events(events[events["results_complete"].astype(bool)])`.
- `pb_days`: on an all-excluded day, `earlier_count += len(group)` and continue.
- `shooter_year`: `top` from `stat_rounds(mine)`; month averages from `stat_rounds`; wins, podiums, `best_finish`, `attendance_rank` unchanged.
- `on_this_day`: `stats_excluded=bool(event["stats_excluded"])`; official numbers kept.
- `api/routes/yir.py`: the four Out fields.
- Frontend: `cd frontend && pnpm typecheck`; add `n_excluded: 0` / `stats_excluded: false` where it flags.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 plus `tests/integration/extras/test_extras_yir_routes.py` in full (all pass); backend gate; `cd frontend && pnpm typecheck && pnpm lint && pnpm exec vitest --run`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/yir.py backend/src/sunday_clays/api/routes/yir.py backend/tests/unit/extras/test_extras_yir.py backend/tests/integration/thrown_out/test_thrown_out_yir.py backend/tests/integration/extras/test_extras_yir_routes.py frontend/src` — `feat(analytics): Year in Review and On this day leave out thrown-out Sundays` (+ trailer).

---

### Task T4a: Station stats leave out thrown-out stations (and the station 404)

**Depends on:** T2a. Sole owner of `stations.py` (`_FRAME_SQL`, `STATION_FRAME_COLUMNS`, `load_station_frame`) and of the `/api/stations/{label}` 404 behaviour; `routes/stations.py` is not edited by any task.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/stations.py:21` (import), `:35-47` (`STATION_FRAME_COLUMNS`), `:77-88` (`_FRAME_SQL`), `:98-110` (`add_sheet_totals` docstring, `load_station_frame`)
- Test: `backend/tests/unit/analytics/test_station_analytics.py` (append), `backend/tests/integration/stations/test_station_dropped.py` (new), `backend/tests/integration/thrown_out/test_thrown_out_stations.py` (new)

**Interfaces:**
- Consumes: `frames.live_station_hits`, `station_layouts.dropped`, `fx_thrown_out_session`.
- Produces: `STATION_FRAME_COLUMNS` ends with `"dropped"`; `load_station_frame(session)` returns live rows only (bool `dropped`, all False), `sheet_total` summed after the drop. Every `/api/stations*` route inherits this; a label seen only thrown out is missing from `stations`, `by_event` and `matrix`, and `/api/stations/{label}` returns the existing `station_not_found` 404 (`routes/stations.py:332`).

- [ ] **Step 1: Write the failing tests**

`test_station_analytics.py`:
```python
class _Rows:
    def __init__(self, rows): self._rows = rows
    def execute(self, _sql): return self
    def mappings(self): return self._rows

def _row(entry_row, label, hits, dropped):
    return {"event_date": D0, "station_no": int(label), "station_label": label, "target_count": 7, "sheet_id": 1,
            "entry_row": entry_row, "shooter_id": entry_row, "round_id": None, "hits": hits,
            "round_type": "sporting", "display_name": f"Shooter {entry_row}", "dropped": dropped}

def test_load_station_frame_leaves_a_dropped_station_out_before_sheet_totals():
    got = load_station_frame(_Rows([_row(1, "4", 5, False), _row(1, "11", 7, True), _row(2, "4", 3, False), _row(2, "11", 7, True)]))
    assert list(got["station_label"]) == ["4", "4"]
    assert list(got["sheet_total"]) == [5, 3]
    assert str(got["dropped"].dtype) == "bool"
    assert STATION_FRAME_COLUMNS[-1] == "dropped"
```
`test_station_dropped.py` (fixture world: two station Sundays; station 9 is 86/168 over 24 entries on the first and 44/91 over 13 on the second, see `test_station_routes.py:63-80`):
```python
def _first_day(s): return s.execute(text("SELECT min(event_date) FROM station_layouts")).scalar_one()

def test_a_dropped_station_leaves_station_stats(fx_viewer_client, fx_session):
    first = _first_day(fx_session)
    fx_session.execute(text("UPDATE station_layouts SET dropped = true WHERE station_label = '9' AND event_date = :d"), {"d": first})
    body = fx_viewer_client.get("/api/stations").json()
    st = {s["station_no"]: s for s in body["stations"]}
    assert (st[9]["hits"], st[9]["n_targets"], st[9]["n_rounds"], st[9]["n_events"]) == (44, 91, 13, 1)
    assert st[4]["n_events"] == 2 and body["n_events"] == 2
    assert (first.isoformat(), "9") not in {(e["event_date"], e["label"]) for e in body["by_event"]}
    assert first.isoformat() not in {e["event_date"] for e in fx_viewer_client.get("/api/stations/9").json()["by_event"]}

def test_a_station_seen_only_thrown_out_is_not_listed_and_404s(fx_viewer_client, fx_session):
    fx_session.execute(text("UPDATE station_layouts SET dropped = true WHERE station_label = '10'"))
    body = fx_viewer_client.get("/api/stations").json()
    assert "10" not in {s["label"] for s in body["stations"]}
    assert all(c["label"] != "10" for c in body["matrix"])
    response = fx_viewer_client.get("/api/stations/10")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "station_not_found")
    assert fx_viewer_client.get("/api/stations/9").status_code == 200

def test_a_lettered_station_seen_only_thrown_out_404s(fx_viewer_client, fx_session):  # Review Focus 1
    first = _first_day(fx_session)
    fx_session.execute(text(
        "INSERT INTO station_layouts (event_date, station_label, station_no, target_count, source_import_id, dropped, dropped_source)"
        " SELECT event_date, '7A', station_no, target_count, source_import_id, true, 'auto'"
        " FROM station_layouts WHERE event_date = :d AND station_label = '7'"), {"d": first})
    fx_session.execute(text(
        "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id, entry_row, name_key, shooter_id, round_id, hits)"
        " SELECT h.event_date, h.station_no, '7A', h.sheet_id, h.entry_row, h.name_key, h.shooter_id, h.round_id, l.target_count"
        " FROM station_hits h JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = '7A'"
        " WHERE h.event_date = :d AND h.station_label = '7'"), {"d": first})
    assert fx_viewer_client.get("/api/stations/7A").status_code == 404
    assert fx_viewer_client.get("/api/stations/7").status_code == 200
```
`test_thrown_out_stations.py` (folded from the old T2b; local `THROWN_OUT_SUNDAY`):
```python
def test_station_page_frame_leaves_out_the_thrown_out_station(fx_thrown_out_session):
    frame = load_station_frame(fx_thrown_out_session)
    assert "dropped" in frame.columns and not frame["dropped"].any() and len(frame) == 621
    assert not ((frame["event_date"] == THROWN_OUT_SUNDAY) & (frame["station_label"] == "11")).any()
    hadley = frame[(frame["event_date"] == THROWN_OUT_SUNDAY) & (frame["display_name"] == "Hadley, Ike")]
    assert hadley["sheet_total"].unique().tolist() == [36]
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/test_station_analytics.py::test_load_station_frame_leaves_a_dropped_station_out_before_sheet_totals tests/integration/stations/test_station_dropped.py tests/integration/thrown_out/test_thrown_out_stations.py -q`. Expected: the unit test sees `['4', '11', '4', '11']` (`dropped` is not a frame column); `(130, 259, 37, 2) != (44, 91, 13, 1)`; `"10"` still listed with 200 instead of 404; `/api/stations/7A` 200; `assert "dropped" in frame.columns` fails.

- [ ] **Step 3: Implement** (`stations.py` only)

Append `"dropped"` to `STATION_FRAME_COLUMNS`; add `, l.dropped` to `_FRAME_SQL` (keep `WHERE e.kind = 'regular'`); in `load_station_frame`, after the Int64 casts, `frame["dropped"] = frame["dropped"].eq(True)` and `return add_sheet_totals(live_station_hits(frame))` (import from `frames`); `add_sheet_totals` docstring: "`sheet_total` = the entry's recomputed station-sheet total over live (not thrown-out) stations, taken before any other filtering." The separator (`stations.py:212`) and `_coverage` then use live stations only, deliberately.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/test_station_analytics.py tests/integration/stations tests/integration/thrown_out tests/integration/special/test_special_frames.py -q` (all pass); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/stations.py backend/tests/unit/analytics/test_station_analytics.py backend/tests/integration/stations/test_station_dropped.py backend/tests/integration/thrown_out/test_thrown_out_stations.py` — `feat(stations): leave thrown-out stations out of station stats` (+ trailer).

---

### Task T4b: Achievements shooter-day split and score trophies

**Depends on:** T2c.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/achievements/context.py:37-53` (`_DAY_DTYPES`), `:101-129` (`_shooter_days`)
- Modify: `backend/src/sunday_clays/analytics/achievements/scores.py:3` (docstring), `:26-74` (`round_score_value`, `_comeback`, `_above_average_3`)
- Modify: `backend/src/sunday_clays/analytics/achievements/participation.py:102-110` (`personal_bests_value`)
- Modify: `backend/src/sunday_clays/analytics/achievements/conditions.py:74-93` (`_mudder`)
- Modify: `backend/tests/unit/analytics/achievements/conftest.py:160-176,181-203,205-231` (`CtxBuilder._calendar/_events_frame/_rounds_frame`)
- Test: `backend/tests/unit/analytics/achievements/test_ach_context.py:47-69,138-154`, `test_ach_scores.py`, `test_ach_participation.py`, `test_ach_conditions.py`, `test_ach_competition.py` (append)

**Interfaces:**
- Consumes: the `stats_excluded` round/event/calendar columns.
- Produces: `AchContext.shooter_days` in the contract's column order with `prior_n_s`, `prior_sum_s`, `prior_best_s`, `prev_day_best_s`; `prior_sum`, `prior_best`, `prev_day_best` removed; `CtxBuilder.event(day, stats_excluded=…)`.

- [ ] **Step 1: Write the failing tests**

`test_ach_context.py`: in `test_shooter_days_prior_columns_use_earlier_dates_only` (:65-69) rename to the new columns with the same values (`prior_sum_s == [0, 84, 114]`, `prior_best_s[1:] == [44.0, 44.0]`, `prev_day_best_s[1:] == [44.0, 30.0]`), add `prior_n_s == [0, 2, 3]` and `stats_excluded == [False] * 3`; replace `DAY_DTYPES` (:138-154) with the contract order (`stats_excluded` bool, `prior_n_s`/`prior_sum_s` int64, `prior_best_s`/`prev_day_best_s` float64). Add:
```python
def test_shooter_days_score_prefixes_skip_an_excluded_sunday(ctx_builder):
    ctx = (ctx_builder().event(sun(1), stats_excluded=True)
           .round(1, sun(0), 40).round(1, sun(1), 50).round(1, sun(2), 35).round(1, sun(3), 45).build())
    d = ctx.shooter_days
    assert list(d["stats_excluded"]) == [False, True, False, False]
    assert list(d["prior_rounds"]) == [0, 1, 2, 3]
    assert list(d["cum_sum"]) == [40, 90, 125, 170]
    assert list(d["prior_n_s"]) == [0, 1, 1, 2]
    assert list(d["prior_sum_s"]) == [0, 40, 40, 75]
    assert list(d["prior_best_s"].iloc[1:]) == [40.0, 40.0, 40.0]
    assert list(d["prev_day_best_s"].iloc[1:]) == [40.0, 40.0, 35.0]
    assert not {"prior_sum", "prior_best", "prev_day_best"} & set(d.columns)
```
`test_ach_scores.py`:
```python
def excluded_round_score_ctx(b):
    return (b().event(sun(1), stats_excluded=True)
            .round(1, sun(0), 38).round(1, sun(1), 50).round(1, sun(2), 41).round(2, sun(1), 50).build())

def test_round_score_ignores_an_excluded_sunday(ctx_builder):
    ctx = excluded_round_score_ctx(ctx_builder)
    assert awards("round_score", ctx) == [(1, "round_score:1", sun(0)), (1, "round_score:2", sun(0)), (1, "round_score:3", sun(2))]
    assert list(registry.get("round_score").value(ctx)["event_date"]) == [pd.Timestamp(sun(0)), pd.Timestamp(sun(2))]
    [item] = [p for p in registry.progress(ctx, 2, None) if p.code == "round_score"]
    assert item.value == 0.0

def excluded_comeback_ctx(b):
    builder = b().event(sun(5), stats_excluded=True)
    for i in range(5): builder.round(1, sun(i), 30)
    return builder.round(1, sun(5), 50).round(1, sun(6), 45).build()

def test_comeback_skips_back_over_an_excluded_sunday(ctx_builder):
    got = [(w.event_date, w.round_id, dict(w.details)) for w in registry.evaluate_one(registry.get("comeback"), excluded_comeback_ctx(ctx_builder))]
    assert got == [(sun(6), 7, {"best": 45, "previous_best": 30})]

def excluded_above_ctx(b):
    builder = b().event(sun(11), stats_excluded=True)
    for sid in (1, 2):
        for i in range(10): builder.round(sid, sun(i), 30)
    builder.round(1, sun(10), 31).round(1, sun(11), 20).round(1, sun(12), 32).round(1, sun(13), 33)
    builder.round(2, sun(10), 31).round(2, sun(11), 50).round(2, sun(12), 32)
    return builder.build()

def test_above_average_run_skips_an_excluded_sunday_and_never_counts_it(ctx_builder):
    assert awards("above_average_3", excluded_above_ctx(ctx_builder)) == [(1, "above_average_3", sun(13))]
```
and add `("round_score", excluded_round_score_ctx, sun(1))`, `("comeback", excluded_comeback_ctx, sun(5))`, `("above_average_3", excluded_above_ctx, sun(12))` to the existing `test_no_leak` parametrize.

`test_ach_participation.py`:
```python
def test_personal_bests_skip_an_excluded_sunday_but_its_round_counts_toward_five(ctx_builder):
    b = ctx_builder().event(sun(5), stats_excluded=True).event(sun(4), stats_excluded=True)
    for i in range(4): b.round(1, sun(i), 30).round(2, sun(i), 30)
    b.round(1, sun(4), 30).round(1, sun(5), 50).round(1, sun(6), 40)
    b.round(2, sun(4), 30).round(2, sun(6), 40)
    ctx = b.build()
    assert value_series("personal_bests", ctx, 1) == [0.0] * 6 + [1.0]
    assert value_series("personal_bests", ctx, 2) == [0.0] * 5 + [1.0]

def test_clays_broken_and_thrown_count_an_excluded_sunday(ctx_builder):
    ctx = ctx_builder().event(sun(1), stats_excluded=True).round(1, sun(0), 40).round(1, sun(1), 50).build()
    assert value_series("clays_broken", ctx, 1) == [40.0, 90.0]
    assert value_series("clays_thrown", ctx, 1) == [50.0, 100.0]

@pytest.mark.parametrize(("code", "make", "day"), [("events", events_ctx, None), ("doubleheader", doubleheader_ctx, sun(1))])
def test_count_trophies_still_award_on_an_excluded_sunday(ctx_builder, code, make, day):  # Review Focus 4 (guard)
    plain = awards(code, make(ctx_builder))
    award_day = day or plain[-1][2]
    assert plain and award_day in {d for _, _, d in plain}
    assert awards(code, make(ctx_builder, excluded=(award_day,))) == plain
```
`events_ctx` and `doubleheader_ctx` gain `excluded: tuple[date, ...] = ()`, calling `.event(d, stats_excluded=True)` for each first. `test_ach_competition.py` does the same for its first-win ctx (`first_win`) and adds the matching guard; `test_ach_conditions.py`:
```python
def test_mudder_is_not_awarded_on_an_excluded_sunday_but_rain_is(ctx_builder):
    ctx = (ctx_builder().event(sun(0), precip_in=0.02, stats_excluded=True)
           .event(sun(1), precip_in=0.5).round(1, sun(0), 45).round(1, sun(1), 41).build())
    assert awards("mudder", ctx) == [(1, "mudder", sun(1))]
    assert awards("rain", ctx) == [(1, "rain", sun(0))]
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/achievements -q`. Expected: `KeyError: 'prior_n_s'`/`'stats_excluded'` in the context tests; award assertions fail (`round_score:4` still at `sun(1)`, `comeback` at `sun(5)`, `mudder` at `sun(0)`); `TypeError: … unexpected keyword argument 'stats_excluded'` until the builder change. The count-trophy guards pass once the builder accepts the flag.

- [ ] **Step 3: Implement**

- `conftest.py`: `_events_frame` base row `"stats_excluded": False`; `_rounds_frame` copies the event flag; `_calendar` special row `stats_excluded=False`.
- `context._shooter_days`: `.agg(..., stats_excluded=("stats_excluded", "any"))`; `scored = ~days["stats_excluded"]`; `n_s = n_rounds.where(scored, 0)`, `sum_s = day_sum.where(scored, 0)`, `best_s = day_best.where(scored).astype(float)`; per shooter `prior_n_s = cumsum(n_s) - n_s`, `prior_sum_s = cumsum(sum_s) - sum_s`, `prior_best_s = best_s.transform(lambda s: s.cummax().ffill().shift(1))`, `prev_day_best_s = best_s.transform(lambda s: s.ffill().shift(1))` (the `ffill` is needed because `cummax` leaves NaN at excluded rows); delete `prior_sum`, `prior_best`, `prev_day_best`; `_DAY_DTYPES` in contract order.
- `scores.round_score_value` on `days[~days["stats_excluded"]]` (a shooter with only excluded Sundays has progress 0.0); `_comeback` mask `~stats_excluded & (prior_rounds >= 5) & (day_best >= prev_day_best_s + 15)` with `previous_best` from `prev_day_best_s`; `_above_average_3` runs on the scored days only with `career_average = prior_sum_s / prior_n_s.where(prior_n_s > 0)` and the gate `prior_rounds >= 10`; module docstring: scores read the score-only `*_s` prefixes, so a Sunday with a station thrown out is skipped.
- `participation.personal_bests_value`: `~stats_excluded & (prior_rounds >= PB_MIN_PRIOR_ROUNDS) & (day_best > prior_best_s)`.
- `conditions._mudder`: add `& ~rounds["stats_excluded"]`; rain/cold/heat/wind/all_weather/sub_gauge unchanged.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/achievements tests/integration/achievements -q` (all pass; goldens unchanged); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/achievements/context.py backend/src/sunday_clays/analytics/achievements/scores.py backend/src/sunday_clays/analytics/achievements/participation.py backend/src/sunday_clays/analytics/achievements/conditions.py backend/tests/unit/analytics/achievements/` — `feat(achievements): keep thrown-out Sundays out of score trophies` (+ trailer).

---

### Task T4c: Station trophies and `STATION_COLUMNS`

**Depends on:** T4b (same `context.py` and achievements `conftest.py`). Sole owner of `achievements/context.py` station reading (`STATION_COLUMNS`, `_STATION_SQL`, `from_frames`, `station_frame`) and of the insights `World.station` `dropped` key.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/achievements/context.py:19-29` (`STATION_COLUMNS`), `:69-79` (`_STATION_SQL`), `:172-197` (`from_frames`, `AchContext` docstring), `:260-271` (`station_frame`)
- Modify: `backend/tests/unit/analytics/achievements/conftest.py:83-107` (`CtxBuilder.station`)
- Modify: `backend/tests/unit/analytics/insights/conftest.py:117-135` (`World.station`, one key)
- Test: `backend/tests/unit/analytics/achievements/test_ach_context.py:183-235`, `test_ach_stations.py` (append), `backend/tests/integration/achievements/test_s50_achievements.py` (append), `backend/tests/integration/thrown_out/test_thrown_out_trophies.py` (new)

**Interfaces:**
- Consumes: `frames.live_station_hits`, `STATION_HIT_COLUMNS.dropped` (T2a).
- Produces: `STATION_COLUMNS` ends with `"dropped"` (bool); `load_station_entries` unfiltered; `AchContext.from_frames` applies `live_station_hits`, so the three station trophies, `progress`, `cached_context` and `insights/trophies._next_trophy` (:203-206) never see a thrown-out station; `CtxBuilder.station(..., dropped=False)`; insights `World.station` writes `"dropped": cols.get("dropped", False)`.

- [ ] **Step 1: Write the failing tests**

`test_ach_context.py`: add `"dropped": "bool"` to `STATION_DTYPES` and `"dropped": False` to each `_RowsSession` row (:215-227); add
```python
def test_from_frames_leaves_dropped_station_entries_out(ctx_builder):
    ctx = (ctx_builder().station(1, sun(0), 4, 5, entry_row=10).station(1, sun(0), 11, 7, entry_row=10, dropped=True).build())
    assert list(ctx.station_hits["station_label"]) == ["4"]
    assert STATION_COLUMNS[-1] == "dropped"
```
`test_ach_stations.py` (`sheet()` gains `dropped: frozenset = frozenset()` of labels, passed as `dropped=str(station_no) in dropped`):
```python
def test_a_dropped_station_is_never_cleaned(ctx_builder):
    ctx = sheet(ctx_builder(), sun(0), [(1, {4: 7, 6: 7})], dropped=frozenset({"6"})).build()
    assert awards("station_cleaner", ctx) == [(1, "station_cleaner:1", sun(0))]
    assert registry.get("station_cleaner").value(ctx)["value"].tolist() == [1.0]

def test_the_hardest_station_is_picked_from_live_stations_only(ctx_builder):
    ctx = sheet(ctx_builder(), sun(0), [(1, {4: 7, 5: 7, 6: 0}), (2, {4: 6, 5: 7, 6: 7}), (3, {4: 5, 5: 6, 6: 0})],
                dropped=frozenset({"6"})).build()
    assert with_stations("hardest_station_clean", ctx) == [(1, sun(0), ("4",))]

def test_a_dropped_station_has_no_top_gun(ctx_builder):
    entries = [(1, {4: 6, 6: 7}), (2, {4: 6, 6: 5}), (3, {4: 6, 6: 5}), (4, {4: 5, 6: 5}), (5, {4: 5, 6: 5})]
    assert awards("station_top_gun", sheet(ctx_builder(), sun(0), entries, dropped=frozenset({"6"})).build()) == []
```
`test_s50_achievements.py`:
```python
def test_build_context_leaves_a_dropped_station_out(fx_session):
    first = fx_session.execute(text("SELECT min(event_date) FROM station_layouts")).scalar_one()
    fx_session.execute(text("UPDATE station_layouts SET dropped = true WHERE station_label = '9' AND event_date = :d"), {"d": first})
    assert int(load_station_entries(fx_session)["dropped"].sum()) == 24
    live = build_context(fx_session).station_hits
    assert len(live) == 259 - 24
    assert not ((live["station_label"] == "9") & (live["event_date"] == first)).any()
```
`test_thrown_out_trophies.py` (folded from the old T2b):
```python
def test_trophy_entries_carry_the_flag_and_the_context_leaves_it_out(fx_thrown_out_session):
    entries = load_station_entries(fx_thrown_out_session)
    assert list(entries.columns) == list(STATION_COLUMNS)
    assert entries["dropped"].dtype == bool and int(entries["dropped"].sum()) == 9
    ctx = build_context(fx_thrown_out_session)
    assert len(ctx.station_hits) == 621 and not ctx.station_hits["dropped"].any()
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/achievements tests/integration/achievements/test_s50_achievements.py tests/integration/thrown_out/test_thrown_out_trophies.py -q`. Expected: `TypeError: station() got an unexpected keyword argument 'dropped'`; `STATION_DTYPES` mismatch; `KeyError: 'dropped'` in the s50 and world tests.

- [ ] **Step 3: Implement**

Append `"dropped"` to `STATION_COLUMNS`; `, l.dropped` in `_STATION_SQL` (keep `WHERE e.kind = 'regular'`); `station_frame` adds `frame["dropped"] = frame["dropped"].eq(True)` (NaN from synthetic frames → False); `from_frames` uses `station_hits=_with_ts(frames.live_station_hits(station_hits))` and the `AchContext` docstring says "`station_hits` leaves out stations thrown out on the day"; `CtxBuilder.station` keyword `dropped: bool = False`; insights `World.station` adds the `dropped` key. `achievements/stations.py` unchanged.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/achievements tests/unit/analytics/insights tests/integration/achievements tests/integration/thrown_out tests/integration/special/test_special_frames.py -q` (all pass); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/achievements/context.py backend/tests/unit/analytics/achievements/ backend/tests/unit/analytics/insights/conftest.py backend/tests/integration/achievements/test_s50_achievements.py backend/tests/integration/thrown_out/test_thrown_out_trophies.py` — `feat(achievements): no station trophies from a thrown-out station` (+ trailer).

---

### Task T6a: Explorer engine leaves thrown-out Sundays and stations out of statistics

**Depends on:** T2c. Runs in row 5 so that T5d can rely on it.

**Files:**
- Modify: `backend/src/sunday_clays/explorer/engine.py:141-146` (new constant), `:274-306` (`_units`), `:320-365` (`run_query`), `:374-383` (`load_explorer_frames`)
- Modify: `backend/src/sunday_clays/explorer/spec.py:85-89` (`QueryResult`)
- Modify: `backend/tests/unit/explorer/conftest.py:59-131`, `backend/tests/unit/explorer/test_explorer_loader.py:17-78`
- Modify (typed mocks for `thrown_out_dates`): `frontend/src/features/explorer/mocks.ts` and the literals `pnpm typecheck` names (including `frontend/src/components/charts/explore.test.ts`)
- Test: `backend/tests/unit/explorer/test_explorer_thrown_out.py` (new)

**Interfaces:**
- Consumes: `stat_rounds`, `stat_events`, `live_station_hits`, the flag columns.
- Produces: `explorer.engine.STAT_METRICS`; `ExplorerFrames.events.stats_excluded`; `QueryResult.thrown_out_dates: list[str]` (contract §Analytics area fields).

- [ ] **Step 1: Write the failing tests**

`conftest.py`: `"stats_excluded": False` in every `make_frames()` row dict, `events.insert(4, "stats_excluded", False)` after the `difficulty` insert, `station_hits["dropped"] = False`. `test_explorer_loader.py`: stub `rounds` gains `"stats_excluded": [False] * 3`, `events` `[False] * 2`, `hits` `"dropped": [False]`; the pinned list in `test_loader_adds_weather_bands_and_keeps_missing_weather_missing` becomes `["event_date", "round_type", "head_count", "difficulty", "stats_excluded", *engine.WEATHER_COLUMNS, "temp_band", "wind_band", "precip_band"]`.

`test_explorer_thrown_out.py`:
```python
E2 = date(2025, 3, 2)

def _thrown_out(frames: ExplorerFrames) -> ExplorerFrames:
    """E2 is a Sunday with a station thrown out; station 10 is a thrown-out station."""
    return replace(frames,
        rounds=frames.rounds.assign(stats_excluded=frames.rounds["event_date"].eq(E2)),
        events=frames.events.assign(stats_excluded=frames.events["event_date"].eq(E2)),
        station_hits=frames.station_hits.assign(dropped=frames.station_hits["station_label"].eq("10")))

def _values(rows, key): return {r[key]: r["value"] for r in rows}

def test_score_metrics_leave_out_a_thrown_out_sunday(frames):
    f = _thrown_out(frames)
    overall = run_query(f, QuerySpec(metric=Metric.SCORE))
    assert overall.rows[0]["value"] == pytest.approx(38.0)  # (40+30+36+39+45)/5
    assert (overall.rows[0]["n"], overall.n_rounds) == (5, 5)
    for metric in (Metric.SCORE, Metric.ADJUSTED, Metric.RESIDUAL, Metric.RATING):
        assert [r["event"] for r in run_query(f, QuerySpec(metric=metric, group_by=[Dim.EVENT])).rows] == ["2024-12-01", "2025-07-06"], metric
    difficulty = run_query(f, QuerySpec(metric=Metric.DIFFICULTY, group_by=[Dim.EVENT]))
    assert [r["event"] for r in difficulty.rows] == ["2024-12-01", "2025-07-06", "2025-11-02"]

def test_count_metrics_keep_a_thrown_out_sunday(frames):  # guard
    f = _thrown_out(frames)
    assert run_query(f, QuerySpec(metric=Metric.ROUNDS)).rows[0]["value"] == 9
    assert _values(run_query(f, QuerySpec(metric=Metric.SHOOTERS, group_by=[Dim.EVENT])).rows, "event") == {"2024-12-01": 3, "2025-03-02": 3, "2025-07-06": 2}
    assert _values(run_query(f, QuerySpec(metric=Metric.WINS, group_by=[Dim.SHOOTER])).rows, "shooter_id") == {1: 2, 2: 0, 3: 1}
    assert _values(run_query(f, QuerySpec(metric=Metric.ATTENDANCE, agg=Agg.SUM, group_by=[Dim.EVENT])).rows, "event")["2025-03-02"] == 4.0

def test_min_score_counts_official_scores_but_not_score_stats(frames):
    f = _thrown_out(frames)
    assert run_query(f, QuerySpec(metric=Metric.ROUNDS, filters=Filters(min_score=40))).rows[0]["value"] == 4
    assert run_query(f, QuerySpec(metric=Metric.SCORE, agg=Agg.COUNT, filters=Filters(min_score=40))).rows[0]["value"] == 2

def test_min_rounds_on_a_score_metric_counts_only_scored_rounds(frames):
    result = run_query(_thrown_out(frames), QuerySpec(metric=Metric.SCORE, group_by=[Dim.SHOOTER], filters=Filters(min_rounds=2)))
    assert _values(result.rows, "shooter_id") == {1: pytest.approx(39.5), 3: pytest.approx(40.5)}

def test_hit_pct_leaves_out_a_thrown_out_station(frames):
    f = _thrown_out(frames)
    assert _values(run_query(f, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.STATION])).rows, "station") == {"4": pytest.approx(100 * 12 / 14)}
    overall = run_query(f, QuerySpec(metric=Metric.HIT_PCT))
    assert overall.rows[0]["value"] == pytest.approx(100 * 12 / 14) and (overall.rows[0]["n"], overall.n_rounds) == (2, 2)

def test_count_rows_by_sunday_list_the_thrown_out_dates(frames):
    f = _thrown_out(frames)
    assert run_query(f, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.EVENT])).thrown_out_dates == ["2025-03-02"]
    assert run_query(f, QuerySpec(metric=Metric.SCORE, group_by=[Dim.EVENT])).thrown_out_dates == []
    assert run_query(f, QuerySpec(metric=Metric.ROUNDS)).thrown_out_dates == []
    assert run_query(f, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.EVENT])).thrown_out_dates == []
    assert "thrown_out_dates" in create_app().openapi()["components"]["schemas"]["QueryResult"]["required"]
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/explorer -q`. Expected: `38.333… != 38.0`; shooter 2 still present under `min_rounds`; station `"10"` present; `4 != 2` for `min_score`; `stats_excluded` missing from the loader columns; `AttributeError: 'QueryResult' object has no attribute 'thrown_out_dates'`. The count guard passes.

- [ ] **Step 3: Implement**

- `engine.py`: after `ROUND_METRICS_FOR_MIN_SCORE`, `STAT_METRICS: Final = frozenset({Metric.SCORE, Metric.ADJUSTED, Metric.RESIDUAL, Metric.RATING, Metric.DIFFICULTY})` with the comment `# Score statistics leave out Sundays with a station thrown out (spec D8); counts keep them.`
- `_units`: event metrics use `fr.stat_events(frames.events)` for `STAT_METRICS` before `_filter_events`; round metrics filter `fr.stat_rounds(frames.rounds)` for `STAT_METRICS` before `_filter_rounds` (so `min_rounds` counts scored rounds); HIT_PCT uses `fr.live_station_hits(frames.station_hits)` before the `round_id` notna filter. `_validate` unchanged.
- `run_query`: when `spec.metric not in STAT_METRICS`, `spec.metric is not Metric.HIT_PCT` and `Dim.EVENT in spec.group_by`, set `thrown_out_dates = sorted({r["event"] for r in rows} & excluded)` where `excluded` is the ISO dates of `frames.events` rows with `stats_excluded`; else `[]`.
- `load_explorer_frames`: events select `["event_date", "round_type", "head_count", "difficulty", "stats_excluded", *WEATHER_COLUMNS]`.
- `spec.py`: `QueryResult` gains `thrown_out_dates: list[str] = Field(default_factory=list)` with `model_config = ConfigDict(json_schema_serialization_defaults_required=True)`.
- Frontend: `cd frontend && pnpm typecheck`; add `thrown_out_dates: []` to each `QueryResult` literal it names.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/explorer tests/integration/explorer tests/integration/insights/test_chart_proof.py tests/integration/api/test_explore_route.py -q` (all pass); backend gate; `cd frontend && pnpm typecheck && pnpm lint && pnpm exec vitest --run`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/explorer/engine.py backend/src/sunday_clays/explorer/spec.py backend/tests/unit/explorer/conftest.py backend/tests/unit/explorer/test_explorer_loader.py backend/tests/unit/explorer/test_explorer_thrown_out.py frontend/src` — `feat(explorer): leave thrown-out Sundays out of score metrics and thrown-out stations out of hit %` (+ trailer).

---

### Task T5a: Insight context — score-only prefixes, Sunday flag, scored views, how lines

**Depends on:** T2c, T4c (insights `World.station` already writes `dropped`).

**Files:**
- Modify: `backend/src/sunday_clays/analytics/insights/context.py:55-90` (Day), `:100-118` (Sunday), `:129-260` (InsightFrames), `:276-312` (`_build_sundays`), `:315-375` (`_build_histories`, recurrence at :338-366), `:404-430` (`anchor_days`/`evergreen_days`), `:444-446` (next to `held_only`), `:489-500` (`own_tier`)
- Modify (readers of the removed fields, renamed in this task so the tree compiles): `insights/milestones.py:63-64,94,101,232-235,686,800-802`, `insights/streaks.py:234`, `insights/peaks.py:554`, `insights/journeys.py:253`, `insights/anchors.py:68`
- Modify: `backend/src/sunday_clays/analytics/insights/templates.py:377` (append three constants)
- Modify: `backend/tests/unit/analytics/insights/conftest.py:72-75,140-208` (World `_event_frame`/`_round_frame`; `station()` already done by T4c)
- Modify: `backend/tests/unit/analytics/insights/test_infrastructure.py:192-193`, `test_context.py:27-28`, `test_kinds_streaks.py:70` (rename to the `_s` fields; values unchanged)
- Test: `backend/tests/unit/analytics/insights/test_context.py`

**Interfaces:**
- Consumes: the `stats_excluded`/`dropped` frame columns (T2a); NULL `adjusted` from `compute_round_metrics` (T2c).
- Produces: `Day.stats_excluded`, `Day.prior_n_s`, `Day.prior_sum_s`, `Day.prior_best_s`, property `Day.prior_mean_s`; **removed** `Day.prior_best`, `Day.prior_sum`, `Day.prior_mean`; `Sunday.stats_excluded`; `InsightFrames.scored_histories`, `scored_sundays`; `scored_only`; `anchor_days(..., scored=False)`, `evergreen_days(..., scored=False)`; `templates.THROWN_OUT_ROUNDS_HOW`, `THROWN_OUT_STATION_HOW`, `THROWN_OUT_RECAP_HOW`; World `sunday(day, stats_excluded=True)`.

- [ ] **Step 1: Write the failing tests** (`test_context.py`; import `anchor_days`, `scored_only`, `own_tier`, `evergreen_days`, `Scope`, the three templates, `lint_clauses`, `plain`, `render`)

```python
def test_score_prefixes_skip_a_thrown_out_sunday_but_gates_count_it(make_world, sun):
    world = make_world().series(1, 0, [30, 48, 35, 36]).crowd(sun(1), [40, 40, 40])
    days = world.sunday(sun(1), stats_excluded=True).frames().histories[1]
    assert [d.stats_excluded for d in days] == [False, True, False, False]
    assert [d.prior_rounds for d in days] == [0, 1, 2, 3]
    assert [d.prior_n_s for d in days] == [0, 1, 1, 2]
    assert [d.prior_sum_s for d in days] == [0, 30, 30, 65]
    assert [d.prior_best_s for d in days] == [None, 30, 30, 35]
    assert [d.prior_mean_s for d in days] == [None, 30.0, 30.0, 32.5]
    assert [d.targets for d in days] == [30, 78, 113, 149]
    assert [d.k for d in days] == [1, 2, 3, 4]
    assert days[1].adjusted is None
    assert not any(hasattr(days[0], f) for f in ("prior_best", "prior_sum", "prior_mean"))

def test_sundays_carry_the_flag_and_scored_views_leave_them_out(make_world, sun):
    fr = make_world().series(1, 0, [30, 48, 35]).sunday(sun(1), stats_excluded=True).frames()
    assert [s.stats_excluded for s in fr.sundays] == [False, True, False]
    assert [s.date for s in fr.scored_sundays] == [sun(0), sun(2)]
    assert [d.date for d in fr.scored_histories[1]] == [sun(0), sun(2)]
    assert [d.date for d in scored_only(fr.histories[1])] == [sun(0), sun(2)]
    scope = Scope(sundays=frozenset(fr.held_dates()), as_of=sun(2))
    assert [ds[i].date for i, ds in anchor_days(fr, scope)] == [sun(0), sun(1), sun(2)]
    assert [ds[i].date for i, ds in anchor_days(fr, scope, scored=True)] == [sun(0), sun(2)]

def test_evergreen_scored_days_keep_the_activity_gate_on_every_round(make_world, sun):
    fr = make_world().series(1, 0, [30, 31, 48, 33, 34]).sunday(sun(2), stats_excluded=True).frames()
    [(sid, days)] = list(evergreen_days(fr, Scope(sundays=frozenset(), as_of=sun(4)), scored=True))
    assert sid == 1 and [d.score for d in days] == [30, 31, 33, 34] and days[-1].rounds_through == 5

def test_own_tier_reads_scored_rounds_only(make_world, sun):
    assert own_tier(make_world().series(1, 0, [38] * 9 + [45]).frames().histories[1]) == 45
    out = make_world().series(1, 0, [38] * 9 + [45]).sunday(sun(9), stats_excluded=True)
    assert own_tier(out.frames().histories[1]) is None

def test_world_marks_a_thrown_out_sunday(make_world, sun):
    fr = make_world().round(1, sun(0), 40).sunday(sun(0), stats_excluded=True).frames()
    assert fr.events["stats_excluded"].tolist() == [True]
    assert fr.rounds["stats_excluded"].tolist() == [True]

def test_thrown_out_how_lines_pass_the_insight_lints():
    for t in (THROWN_OUT_ROUNDS_HOW, THROWN_OUT_STATION_HOW, THROWN_OUT_RECAP_HOW):
        assert lint_clauses(t.third, force_named=True) == []
        assert t.you is not None and lint_clauses(t.you, force_named=True) == []
    assert plain(render(THROWN_OUT_ROUNDS_HOW, {}, {})) == "Sundays with a station thrown out (marked *) are left out."
    assert plain(render(THROWN_OUT_STATION_HOW, {}, {})) == "A station thrown out on the day is left out."
    assert plain(render(THROWN_OUT_RECAP_HOW, {}, {})) == (
        "A station was thrown out this Sunday. Its results count; its scores stay out of averages and PBs.")
```
Existing tests renamed: `test_context.py:27-28` → `prior_best_s == [None, 30, 40]`, `prior_sum_s == [0, 30, 90]`; `test_infrastructure.py:192-193` → `prior_mean_s`; `test_kinds_streaks.py:70` → `days[11].prior_mean_s == sum(scores[:11]) / 11`.

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/insights/test_context.py tests/unit/analytics/insights/test_infrastructure.py tests/unit/analytics/insights/test_kinds_streaks.py -q`. Expected: `ImportError: cannot import name 'scored_only'` (then `AttributeError: 'Day' object has no attribute 'prior_best_s'` once stubbed); `KeyError: 'stats_excluded'` in the World test.

- [ ] **Step 3: Implement**

- World: `_event_frame` sets `stats_excluded=False` before applying cols (so `sunday(day, stats_excluded=True)` overrides); `_round_frame` maps `stats_excluded` from events by date into `base` before `compute_round_metrics(base)` and keeps it as bool.
- `context.py`: `_flag(value) -> bool` (NaN/None/NA → False); `Day` fields per Produces, removing `prior_best`/`prior_sum`/`prior_mean`; `_build_histories` sets `stats_excluded=_flag(top.get("stats_excluded"))` and the recurrences from `prev`: `prior_n_s = prev.prior_n_s + (0 if prev.stats_excluded else prev.n_rounds)`, `prior_sum_s = prev.prior_sum_s + (0 if prev.stats_excluded else sum(prev.scores))`, `prior_best_s = prev.prior_best_s if prev.stats_excluded else max(prev.score, prev.prior_best_s if prev.prior_best_s is not None else prev.score)` (None/0 with no prev); `targets = (prev.targets if prev else 0) + sum(scores)`; `_build_sundays` sets `stats_excluded`; `scored_only` next to `held_only`; cached `scored_histories`/`scored_sundays`; `anchor_days(scored=True)` iterates `scored_histories` (still `day.held`); `evergreen_days(scored=True)` runs the deceased/active/guest gates on the full `history_until`, then yields `scored_only(days)` and skips an empty one; `own_tier` uses `scored_only(days)[-52:]`.
- Reader renames (behaviour per name): `milestones.is_pb`/`_pb`/`_tied_best`/`_first_tier` → `prior_best_s`; `_tied_best`/`_back_strong` `usual` → `prior_mean_s`; `streaks.above_own_average` → `prior_mean_s` (docstring "mean of every scored round on earlier dates"); `peaks._season_best` → `prior_best_s`; `journeys._targets_milestone` → `d.targets - sum(d.scores) >= level` (clays broken before the day; a count, so all rounds); `anchors.trend_rows` `so_far` → `prior_mean_s`.
- `templates.py`: `THROWN_OUT_ROUNDS_HOW`, `THROWN_OUT_STATION_HOW`, `THROWN_OUT_RECAP_HOW`, each `T(named(<text>), you=named(<text>))` with the contract text.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/insights tests/integration/insights -q` (all pass; `test_days_carry_prefix_values_over_earlier_dates_only` unchanged apart from the rename; goldens unchanged); `git grep -nE "\.prior_(best|sum|mean)\b" backend/src` prints nothing; backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/insights/{context,templates,milestones,streaks,peaks,journeys,anchors}.py backend/tests/unit/analytics/insights/{conftest,test_context,test_infrastructure,test_kinds_streaks}.py` — `feat(insights): score-only prefixes and scored views for thrown-out Sundays` (+ trailer).

---

### Task T5b: Shooter score kinds skip thrown-out Sundays (+ how line)

**Depends on:** T5a.

**Files:**
- Modify: `insights/milestones.py:59-65` (`is_pb`), `:92-105` (`_pb`), `:229-250` (`_tied_best`), `:676-705` (`_back_strong`), `:797-820` (`_first_tier`), `:924-927` (`_reached`); how dicts `:191`, `:302`, `:774`, `:879`, `:1030`
- Modify: `insights/peaks.py:84`, `:192`, `:544`; how dicts `:147`, `:284`, `:385`, `:500`, `:618`, `:742`
- Modify: `insights/form.py:296`, `:415`, `:532`; how dicts `:133`, `:254`, `:368`, `:495`, `:611`, `:749`
- Modify: `insights/tiers.py:97-124`, `:223-246`, `:342-369`; how dicts `:166`, `:299`, `:422`
- Modify: `insights/streaks.py:64-104` (`run_facts`), `:125`, `:237-246`, `:370-386`, `:469-496`; how dicts `:187`, `:304`, `:427`, `:551`
- Modify: `insights/conditions.py` how dicts `:152`, `:233`, `:410`, `:532`; `insights/season.py` how dicts `:462`, `:564`, `:673`
- Modify: `insights/attendance.py:443-473` (`_year_wrapped`), how `:526`; `insights/recap.py:171-222` (`_sunday_recap`, flag `p`)
- Test: `backend/tests/unit/analytics/insights/test_thrown_out_kinds.py` (new)

**Interfaces:**
- Consumes: T5a.
- Produces: `streaks.run_facts(..., scored=False)`; `is_pb(day)` False on a thrown-out day; tables `ROUNDS_HOW`/`STATION_HOW` in `test_thrown_out_kinds.py` (T5c extends them).

- [ ] **Step 1: Write the failing tests** (`test_thrown_out_kinds.py`; fixtures `make_world`, `sun`, `run`)

```python
ROUNDS_HOW: dict[str, tuple[str, ...]] = {
    "pf.pb": ("", "profile", "rollup"), "pf.tied-best": ("", "rollup"), "pf.first-tier": ("",),
    "pf.first-since": ("score",), "pf.back-strong": ("score",),
    "pf.best-stretch": ("", "rollup"), "pf.average-milestone": ("", "rollup"),
    "pf.season-best": ("",), "pf.best-day-vs-field": ("",), "pf.rating-high": ("",),
    "pf.learning-curve": ("",), "pf.hot-form": ("",), "pf.beat-own-usual": ("", "rollup"),
    "pf.up-on-usual": ("",), "pf.year-up": ("",), "pf.years-up-run": ("",),
    "pf.gaining-on-field": ("two_years", "career"), "pf.wet-strength": ("",),
    "pf.weather-steady": ("",), "pf.best-temp": ("",), "pf.tough-days": ("",),
    "pf.beat-field-streak": ("", "rollup"), "pf.above-own-avg-streak": ("", "rollup"),
    "pf.tier-run": ("", "rollup"), "pf.three-rising": ("", "rollup"),
    "pf.high-round-count": ("", "rollup"), "pf.more-high-rounds": ("", "rollup"),
    "pf.low-end-rising": ("",), "pf.year-wrapped": ("",),
    "lb.most-improved": ("",), "pf.rank-climb": ("",), "pf.top-of-club": ("",),
}
STATION_HOW: dict[str, tuple[str, ...]] = {}

@pytest.mark.parametrize(("kind_id", "variants"), sorted(ROUNDS_HOW.items()))
def test_score_kinds_say_thrown_out_sundays_are_left_out(kind_id, variants):
    for v in variants:
        assert registry.get(kind_id).how[v][-1] is THROWN_OUT_ROUNDS_HOW

def test_count_variants_do_not_claim_the_rounds_line():
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("pf.first-since").how[""]
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("pf.back-strong").how[""]
    assert registry.get("pf.first-since").how["score"][:-1] == registry.get("pf.first-since").how[""]

def test_pb_skips_a_thrown_out_sunday_and_beats_only_scored_rounds(make_world, sun, run):
    fr = make_world().series(1, 0, [30, 31, 32, 33, 34, 50, 40]).sunday(sun(5), stats_excluded=True).frames()
    facts = [f for f in run("pf.pb", fr) if f.variant == ""]
    assert [(f.anchor_date, f.params["new"], f.params["old"], f.params["old_date"]) for f in facts] == [(sun(6), 40, 34, sun(4))]
    assert is_pb(fr.histories[1][5]) is False

def test_first_tier_compares_with_the_best_scored_round(make_world, sun, run):
    fr = make_world().series(1, 0, [30] * 10 + [45, 41]).sunday(sun(10), stats_excluded=True).frames()
    assert [(f.anchor_date, f.params["level"]) for f in run("pf.first-tier", fr)] == [(sun(11), 40)]

def test_three_rising_skips_the_thrown_out_sunday_without_breaking(make_world, sun, run):
    fr = make_world().series(1, 0, [30] * 20 + [31, 20, 33, 36]).sunday(sun(21), stats_excluded=True).frames()
    facts = [f for f in run("pf.three-rising", fr) if f.variant == ""]
    assert [(f.anchor_date, f.params["a"], f.params["b"], f.params["c"], f.params["d2"]) for f in facts] == [(sun(23), 31, 33, 36, sun(22))]

def test_year_wrapped_counts_every_sunday_but_best_is_scored_only(make_world, sun, run):
    scores = [30] * 49
    scores[20] = 49
    (fact,) = run("pf.year-wrapped", make_world().series(1, 0, scores).sunday(sun(20), stats_excluded=True).frames())
    assert (fact.params["sundays"], fact.params["targets"], fact.params["best"]) == (49, 1489, 30)
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/insights/test_thrown_out_kinds.py -q`. Expected: the how-table tests fail (last bullet is not `THROWN_OUT_ROUNDS_HOW`; `KeyError: 'score'`); pb yields `sun(5)` too; first-tier `(sun(10), 45)`; three-rising `a == 20`; year-wrapped `best == 49`.

- [ ] **Step 3: Implement**

- `milestones.py`: `is_pb` gains `not day.stats_excluded and …`; `_pb`, `_tied_best`, `_first_tier` pass `scored=True` to both loops (so `first_reached(days[:i], …)` reads scored days); `_reached(day, "score", level)` returns `not day.stats_excluded and day.score >= level`; `_back_strong` `show_score = not d.stats_excluded and usual is not None and d.score >= usual`.
- `scored=True` in `peaks._best_stretch`, `_average_milestone`, `_season_best`; `form._up_on_usual`, `_year_up`, `_years_up_run`; all three tiers kinds.
- `streaks.py`: `run_facts` forwards `scored` to `anchor_days`/`evergreen_days`; `_beat_field`, `_own_avg`, `_tier_run`, `_three_rising` pass `scored=True`.
- `attendance._year_wrapped`: `best` over `[d for d in in_year if not d.stats_excluded]` (skip when empty); `sundays`, `targets` over `in_year`.
- `recap._sunday_recap`: flag `p` only when `sunday.difficulty is not None and not sunday.stats_excluded`.
- How bullets: append `THROWN_OUT_ROUNDS_HOW` last on every variant in `ROUNDS_HOW`; `pf.first-since` gets a new key `"score": (*how[""], THROWN_OUT_ROUNDS_HOW)` used by its score variant; `pf.back-strong` appends only to `how["score"]`; `pf.tier-run` keeps `how[""][0]` first.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/insights -q` (all pass, including `test_registry.py`); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/insights/{milestones,peaks,form,tiers,streaks,conditions,season,attendance,recap}.py backend/tests/unit/analytics/insights/test_thrown_out_kinds.py` — `feat(insights): shooter score kinds leave thrown-out Sundays out` (+ trailer).

---

### Task T5c: Sunday, club, record and station kinds, the recap-card line, and count kinds that still fire

**Depends on:** T5b.

**Files:**
- Modify: `insights/sunday.py:219-277` (`_rain_day`), `:372-393` (`_how_it_played`), `:472-503` (`_toughest_since`), `:562-600` (`_week_jump`), `:674-703` (`_record_watch`), `:782-809` (`_top_score`), `:872-879` (`first_rounds_before`), `:882-918` (`_new_faces`); how dicts `:155`, `:336`, `:439`, `:530`, `:641`, `:759`, `:842`, `:966`
- Modify: `insights/records.py:45-52` (`waits`), `:75`, `:127` (drought anchors), `:221-243` (`_perfect_rarity`); how dicts `:106`, `:192`, `:281`
- Modify: `insights/community.py:341-357`, how `:403`; `insights/club.py:226-237` (`_difficulty_split`), how `:305`, `:439`; `insights/stations.py:46-48` (`entries_to`), how `:124`, `:252`
- Modify: `insights/recap.py:171-222` (`_sunday_recap` variant), `:236-275` (`_all_flags` use, `templates`/`how` of `home.sunday-recap`)
- Test: `backend/tests/unit/analytics/insights/test_thrown_out_kinds.py` (extend)

**Interfaces:**
- Consumes: T5a, T5b tables; `frames.stat_rounds`, `frames.live_station_hits`.
- Produces: `entries_to(fr, day)` live rows only; `first_rounds_before` leaves out a shooter whose first Sunday was thrown out; `home.sunday-recap` emits variant `flags + "x"` on a thrown-out Sunday (same headline template), whose how ends with `THROWN_OUT_RECAP_HOW`; new how key `ev.new-faces["strong"]`.

- [ ] **Step 1: Write the failing tests** (append)

Add to `ROUNDS_HOW`:
```python
    "cl.rain-scores": ("",), "cl.weather-scoreboard": ("",), "cl.club-one-shooter": ("",),
    "rec.drought-clock": ("",), "ev.drought-ended": ("",), "rec.perfect-rarity": ("",),
    "ev.spotlight": ("",), "ev.rain-day": ("",), "ev.how-it-played": ("",),
    "ev.toughest-since": ("",), "ev.week-jump": ("",), "ev.record-watch": ("",),
    "ev.top-score": ("",), "ev.new-faces": ("strong",),
```
set `STATION_HOW = {"st.hardest-easiest": ("",), "pf.station-best": ("",)}` and add:
```python
@pytest.mark.parametrize(("kind_id", "variants"), sorted(STATION_HOW.items()))
def test_station_kinds_say_a_thrown_out_station_is_left_out(kind_id, variants):
    for v in variants:
        assert registry.get(kind_id).how[v][-1] is THROWN_OUT_STATION_HOW

def test_new_faces_welcome_keeps_no_rounds_line():
    assert THROWN_OUT_ROUNDS_HOW not in registry.get("ev.new-faces").how[""]

def test_record_watch_skips_a_thrown_out_top(make_world, sun, run):
    fr = make_world().crowd(sun(0), [46, 40]).crowd(sun(1), [50, 40]).crowd(sun(2), [48, 40]).sunday(sun(1), stats_excluded=True).frames()
    assert [(f.anchor_date, f.variant, f.params["record"]) for f in run("ev.record-watch", fr)] == [(sun(2), "new", 46)]

def test_drought_wait_runs_through_a_thrown_out_49(make_world, sun, run):
    w = make_world()
    for i in range(21):
        w.crowd(sun(i), [{0: 49, 10: 50, 20: 49}.get(i, 40), 35])
    fr = w.sunday(sun(10), stats_excluded=True).frames()
    assert [(f.anchor_date, f.params["last"]) for f in run("ev.drought-ended", fr)] == [(sun(20), sun(0))]

def test_how_it_played_says_nothing_on_a_thrown_out_sunday(make_world, sun, run):
    assert run("ev.how-it-played", make_world().crowd(sun(0), [40, 30]).sunday(sun(0), difficulty=4.0, stats_excluded=True).frames()) == []

def test_first_rounds_pool_leaves_out_a_thrown_out_first_sunday(make_world, sun):
    w = make_world().round(1, sun(0), 30).round(2, sun(9), 45).round(3, sun(10), 20).round(1, sun(11), 30)
    assert first_rounds_before(w.sunday(sun(9), stats_excluded=True).frames(), sun(11)) == [20]

def test_club_one_shooter_average_leaves_out_thrown_out_rounds(make_world, sun, run):
    (fact,) = run("cl.club-one-shooter", make_world().series(1, 0, [40, 40, 40, 50, 40, 40]).sunday(sun(3), stats_excluded=True).frames())
    assert (fact.params["avg"], fact.params["n"]) == (40.0, 1)

def test_perfect_rarity_counts_scored_rounds_only(make_world, sun, run):
    w = make_world().round(1, sun(0), 50).round(2, sun(1), 50).round(1, sun(2), 40)
    (fact,) = run("rec.perfect-rarity", w.sunday(sun(1), stats_excluded=True).frames())
    assert (fact.params["perfect"], fact.params["rounds"]) == (1, 2)

def test_rain_split_leaves_out_a_thrown_out_sunday(make_world, sun):
    w = make_world().crowd(sun(0), [40]).crowd(sun(1), [40])
    w.sunday(sun(0), difficulty=1.0, precip_in=0.3).sunday(sun(1), difficulty=5.0, precip_in=0.3, stats_excluded=True)
    assert _difficulty_split(w.frames().sundays, "precip_band", "wet") == ([1.0], [])

def test_station_entries_leave_out_a_dropped_station(make_world, sun):
    w = make_world().round(1, sun(0), 40)
    w.station(1, sun(0), 11, 7, target_count=7, dropped=True).station(1, sun(0), 3, 5, target_count=7)
    assert entries_to(w.frames(), sun(0))["station_label"].tolist() == ["3"]

def test_the_sunday_recap_discloses_a_thrown_out_sunday(make_world, sun, run):
    w = make_world().crowd(sun(0), [45, 40, 35, 30]).sunday(sun(0), temp_f=60.0, gust_mph=5.0)
    plain_fact = [f for f in run("home.sunday-recap", w.frames()) if f.anchor_date == sun(0)]
    assert plain_fact and "x" not in plain_fact[0].variant
    (fact,) = [f for f in run("home.sunday-recap", w.sunday(sun(0), stats_excluded=True).frames()) if f.anchor_date == sun(0)]
    assert fact.variant == plain_fact[0].variant.replace("p", "") + "x"
    kind = registry.get("home.sunday-recap")
    assert kind.how[fact.variant][-1] is THROWN_OUT_RECAP_HOW
    assert THROWN_OUT_RECAP_HOW not in kind.how.get(plain_fact[0].variant, kind.how[""])
    assert "*" not in plain(render(kind.templates[fact.variant][0], fact.params, {}))

COUNT_KINDS = ("ev.close-finish", "ev.new-faces", "pf.targets-milestone", "pf.wins", "pf.podium-run")

@pytest.mark.parametrize("kind_id", COUNT_KINDS)
def test_count_kinds_still_anchor_on_a_thrown_out_sunday(kind_id, count_world, sun, run):  # Review Focus 4 (guard)
    k = count_world.k
    assert sun(k) in {f.anchor_date for f in run(kind_id, count_world.frames())}
    facts = [f for f in run(kind_id, count_world.sunday(sun(k), stats_excluded=True).frames()) if f.anchor_date == sun(k)]
    assert facts
    if kind_id == "ev.new-faces":
        assert {f.variant for f in facts} == {"welcome"}
```
`count_world` is a module fixture: a World where `sun(k)` (k = 12) has a close finish (top two within 1), one first-timer, a shooter crossing 1,000 clays broken that day, a win for a shooter with earlier wins and a third podium in a row, and enough earlier Sundays for each kind's gates; it exposes `.k`. Its first assertion stops the test passing vacuously.

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/insights/test_thrown_out_kinds.py -q`. Expected: the new how rows fail; record-watch returns the `sun(1)` "new" fact; drought-ended `[]`; how-it-played one fact; pool `[45, 20]`; avg `41.7`; perfect `2`; split includes `5.0`; stations `["3", "11"]`; the recap variant has no `"x"`. The count-kind guards pass.

- [ ] **Step 3: Implement**

- `sunday.py`: `_record_watch` iterates `fr.scored_sundays`; `_top_score` skips an excluded Sunday and its `earlier` pool requires `not s.stats_excluded`; `_how_it_played` skips `sunday.stats_excluded`; `_toughest_since` skips an excluded anchor and `prev` requires `not s.stats_excluded`; `_week_jump` uses `anchor_days(fr, scope, scored=True)`; `first_rounds_before` adds `and not days[0].stats_excluded`; `_new_faces` computes `strong` only when `not sunday.stats_excluded`; `_rain_day` sets `played` only when `not sunday.stats_excluded`.
- `records.py`: `waits` sets `last` from non-excluded Sundays only; `_drought_clock`/`_drought_ended` skip `sunday.stats_excluded`; `_perfect_rarity` reads `frames.stat_rounds(fr.rounds)`.
- `community._club_one_shooter` and `club._difficulty_split` skip `s.stats_excluded`. `stations.entries_to` filters `frames.live_station_hits(fr.stations)`.
- `recap.py`: `_sunday_recap` appends `"x"` to `flags` when `sunday.stats_excluded` (after the existing parts, not counted in `slots`); `templates = {f: (_recap_template(f),) for f in _all_flags()} | {f + "x": (_recap_template(f),) for f in _all_flags()}`; `how = {"": BASE} | {f + "x": (*BASE, THROWN_OUT_RECAP_HOW) for f in _all_flags()}` where `BASE` is today's two bullets. The headline never carries `*`; update any pinned recap variant count deliberately (×2).
- How bullets: `THROWN_OUT_ROUNDS_HOW` on the listed tuples; `ev.new-faces` gets `"strong": (*how[""], THROWN_OUT_ROUNDS_HOW)`; `THROWN_OUT_STATION_HOW` on both station kinds.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/insights tests/integration/insights -q` (all pass); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/insights/{sunday,records,community,club,stations,recap}.py backend/tests/unit/analytics/insights/test_thrown_out_kinds.py` — `feat(insights): Sunday, record and station kinds leave thrown-out data out; the recap says so` (+ trailer).

---

### Task T5d: Anchors and chart proof with a thrown-out Sunday

**Depends on:** T5c, T6a (Explorer engine) and T3c (`first_round_scores`). Hard dependency: the proof test must be green in this task; if an Explorer link still disagrees, stop and report against T6a rather than merging red.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/insights/anchors.py:56-77` (`trend_rows`), `:166-181` (`highest_rows`), `:255-269` (`station_rows`)
- Test: `backend/tests/unit/analytics/insights/test_anchor_rows.py`, `backend/tests/integration/insights/test_chart_proof.py`

**Interfaces:**
- Consumes: T5a–T5c; `stat_rounds`, `live_station_hits`; T6a; T3c; T2c.
- Produces: `trend_rows` column `thrown_out: bool`, with `score/adjusted/pb/so_far/roll10/roll20` None on that row. No `proof.py` change.

- [ ] **Step 1: Write the failing tests**

`test_anchor_rows.py`:
```python
def test_trend_rows_keep_the_thrown_out_point_out_of_every_line(make_world, sun):
    fr = make_world().series(1, 0, [30, 50, 34]).sunday(sun(1), stats_excluded=True).frames()
    trend = anchors.trend_rows(fr, link("/shooters/1", "trend", sun(0), sun(20)))
    assert trend["thrown_out"].tolist() == [False, True, False]
    assert trend["score"].fillna(-1).tolist() == [30.0, -1.0, 34.0]
    assert trend["pb"].fillna(-1).tolist() == [30.0, -1.0, 34.0]
    assert trend["so_far"].fillna(-1).tolist() == [-1.0, -1.0, 30.0]

def test_trend_rolling_average_skips_the_thrown_out_round(make_world, sun):
    fr = make_world().series(1, 0, [30 + i for i in range(11)]).sunday(sun(5), stats_excluded=True).frames()
    trend = anchors.trend_rows(fr, link("/shooters/1", "trend", sun(0), sun(20)))
    assert pd.isna(trend["roll10"].iloc[9]) and trend["roll10"].iloc[10] == pytest.approx(35.0)

def test_highest_stations_and_first_rounds_leave_out_thrown_out_data(make_world, sun):
    w = make_world().round(1, sun(0), 45).round(2, sun(1), 30).round(1, sun(2), 49).round(3, sun(3), 50)
    w.sunday(sun(0), stats_excluded=True).sunday(sun(3), stats_excluded=True)
    w.station(1, sun(2), 11, 7, target_count=7, dropped=True).station(1, sun(2), 3, 4, target_count=8)
    fr, window = w.frames(), (sun(0), sun(20))
    assert anchors.highest_rows(fr, link("/records", "rec-highest", *window))["value"].tolist() == [49]
    rows = anchors.station_rows(fr, link("/stations", "sthit", *window))
    assert (rows["station"].tolist(), rows["value"].tolist()) == (["3"], [50.0])
    firsts = anchors.first_round_rows(fr, link("/club", "first-rounds", *window))
    assert (firsts["score"].tolist(), firsts["value"].tolist()) == (["30"], [1])
```
`test_chart_proof.py`: move the existing loop into `_problems(pairs, fr, ex) -> list[str]` and add:
```python
SCORE_ANCHORED = {"pf.pb", "pf.tied-best", "pf.first-tier", "ev.record-watch", "ev.top-score",
                  "ev.drought-ended", "ev.spotlight", "ev.how-it-played", "ev.toughest-since"}
COUNT_ANCHORED = {"ev.close-finish", "ev.new-faces", "pf.targets-milestone", "pf.wins", "pf.podium-run",
                  "pf.sunday-milestone", "home.sunday-recap"}

def test_chart_links_prove_their_numbers_with_a_thrown_out_sunday(fx_session):
    fr0, ex0 = build_frames(fx_session), explorer_engine.load_explorer_frames(fx_session)
    day = fr0.held_dates()[-3]
    fr, ex = _thrown_out(fr0, ex0, day)
    pairs = apply_rollups(evaluate_all(fr))
    on_day = {p.kind.id for p in pairs if p.fact.anchor_date == day}
    assert on_day & SCORE_ANCHORED == set()
    assert on_day & COUNT_ANCHORED  # Review Focus 4: counts still fire on that day
    problems = _problems(_sample(pairs), fr, ex)
    assert problems == [], "\n".join(problems)
```
`_thrown_out` sets `stats_excluded=True` on that day's rows of `fr0.rounds`, `fr0.events` and `ex0.rounds`/`ex0.events`, sets `adjusted`/`residual`/`expected` NaN on those rounds and `difficulty` NaN on that day's event rows (mirrors D5), and rebuilds with `InsightFrames.from_frames(...)` and `dataclasses.replace(ex0, ...)`.

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/insights/test_anchor_rows.py -q` — `KeyError: 'thrown_out'`, highest `[45, 49, 50]`, stations include `"11"`. `uv run pytest tests/integration/insights/test_chart_proof.py -q` — proof mismatches on trend links spanning the day.

- [ ] **Step 3: Implement**

`trend_rows` builds `scores` from non-excluded days; an excluded day gives `{"event": …, "score": None, "adjusted": None, "pb": None, "so_far": None, "roll10": None, "roll20": None, "thrown_out": True}`; other rows add `"thrown_out": False` and read `pb`/`roll*` from the scored list. `highest_rows` iterates `frames.stat_rounds(fr.rounds)`; `station_rows` reads `frames.live_station_hits(fr.stations)`.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/insights tests/integration/insights/test_chart_proof.py -q` (all green, no skips); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/insights/anchors.py backend/tests/unit/analytics/insights/test_anchor_rows.py backend/tests/integration/insights/test_chart_proof.py` — `feat(insights): anchors and chart proof agree on thrown-out Sundays` (+ trailer).

---

### Task T5e: Recap facts and email eligibility

**Depends on:** T5c. Backend recap facts only: `RecapOut.thrown_out` and its API tests belong to T6b; the `format.ts` email line belongs to T7d.

**Files:**
- Modify: `backend/src/sunday_clays/analytics/recap_facts.py:213-218` (`FactSource.__init__` station map), `:352-396` (`_scores_context`), `:617-646` (`_gain`/`_improvement`)
- Test: `backend/tests/unit/analytics/insights/test_recap_facts.py`, `backend/tests/unit/analytics/insights/test_recap_week.py`

**Interfaces:**
- Consumes: T5a–T5c; `frames.live_station_hits`; `scored_only`.
- Produces: recap facts per the contract (§Insights, recap facts).

- [ ] **Step 1: Write the failing tests**

`test_recap_facts.py`:
```python
def test_station_feats_leave_out_a_thrown_out_station(make_world: Any) -> None:
    world = weekly(make_world, 1)
    world.shooter(1, "Hadley, Ike")
    for sid in (1, 2, 3, 4):
        world.round(sid, FIRST, 40)
        world.station(sid, FIRST, 11, 7, entry_row=sid, target_count=7, dropped=True)
    add_entry(world, FIRST, 1, 1, [16, 16, 16, 16, 5, 5])
    for sid in (2, 3, 4):
        add_entry(world, FIRST, sid, sid, [5] * 6)
    assert texts(world.frames(), FIRST, "station_feats") == ["Ike Hadley broke every target at 4 of 6 stations."]

def test_course_stations_never_name_a_thrown_out_station(make_world: Any) -> None:
    world = stations_world(make_world, {3: [10] * 9 + [8], 5: [13] * 10})
    for entry in range(1, 11):
        world.station(entry, FIRST, 11, 16, entry_row=entry, target_count=16, dropped=True)
    assert texts(world.frames(), FIRST, "course_stations") == ["Toughest station: Station 3, 61% of targets broken. Easiest: Station 5, 81%."]

def test_scores_context_skips_and_forgets_a_thrown_out_sunday(make_world: Any) -> None:
    fr = weekly(make_world, 30, score=lambda i: {5: 47, 29: 45}.get(i, 40),
                event=lambda i: {"stats_excluded": True} if i == 5 else {}).frames()
    assert texts(fr, wk(FIRST, 5), "scores_context") == []
    assert texts(fr, wk(FIRST, 29), "scores_context") == ["The middle score of 45 was the highest on record."]

def test_improvement_skips_and_forgets_a_thrown_out_round(make_world: Any) -> None:
    world = weekly(make_world, 122, event=lambda i: {"stats_excluded": True} if i == 120 else {})
    world.shooter(1, "Hadley, Ike")
    for i in range(122):
        world.round(1, wk(FIRST, i), 50 if i == 120 else 40 if i >= 100 else 36)
    fr = world.frames()
    assert texts(fr, wk(FIRST, 120), "improvement") == []
    assert texts(fr, wk(FIRST, 121), "improvement") == ["Ike Hadley's average over the last 20 rounds is up 4.0 targets compared with a year ago."]
```
`test_recap_week.py`:
```python
COUNT_KINDS = frozenset({"pf.shooter-anniversary", "pf.sunday-milestone"})

def test_every_email_score_kind_leaves_thrown_out_sundays_out() -> None:
    for kind_id, variants in ELIGIBLE.items():
        kind = registry.get(kind_id)
        for v in variants - {"rollup"}:
            assert kind_id in COUNT_KINDS or THROWN_OUT_ROUNDS_HOW in (kind.how.get(v) or kind.how[""]), (kind_id, v)
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/unit/analytics/insights/test_recap_facts.py tests/unit/analytics/insights/test_recap_week.py -q`. Expected: station feats `5 of 7` plus `4 shooters broke every target at Station 11.`; course stations `Easiest: Station 11, 100%`; scores_context `since February 2024`; improvement fires on week 120. The eligibility test passes if T5b/T5c covered every email kind (it pins that).

- [ ] **Step 3: Implement**

`recap_facts.py`: `self._stations` groups `frames.live_station_hits(fr.stations)` (fixes `_course_stations` and `_station_feats`); `_scores_context` returns `[]` when `today.stats_excluded` and its `prior` requires `not s.stats_excluded`; `_improvement` returns `[]` when `today.stats_excluded`; `_gain` receives `scored_only(fr.history_until(sid, today.date))`. `_on_this_day` (:463) is unchanged: a year-ago top score is an official count. `recap_insights.py` unchanged.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/unit/analytics/insights tests/integration/insights/test_recap_week_world.py -q` (all pass); backend gate.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/analytics/recap_facts.py backend/tests/unit/analytics/insights/test_recap_facts.py backend/tests/unit/analytics/insights/test_recap_week.py` — `feat(recap): thrown-out stations and Sundays leave the recap facts` (+ trailer).

---

### Task T6b: Sunday-level API flags (events, attendance, recap, ClaySmasher Notes)

**Depends on:** T2c, T3b (`event_notables`), T4a. Owns `ThrownOutOut`/`thrown_out_out`, the events/attendance flags, `RecapOut.thrown_out` and its API tests, and ClaySmasher `ExportRound.thrown_out` + Notes. Reuses T2a's `LiveSeed.event(stats_excluded=…)`; does not edit `stations.py`, `routes/stations.py` or `event_notables`.

**Files:**
- Modify: `backend/src/sunday_clays/api/routes/events.py:24-27` (WinnerOut), `:30-51` (EventSummaryOut), `:54-71` (EventResultOut), `:87-90` (StationLayoutOut), `:130-156` (EventDetailOut), `:163-173` (`_winners`), `:176-215` (`list_events`), `:218-269` (`_special_results`, `_results`), `:289-330` (`_stations`), `:391-437` (`get_event`)
- Modify: `backend/src/sunday_clays/api/routes/club.py:60-72` (AttendanceOut), `:198-214` (`club_attendance`)
- Modify: `backend/src/sunday_clays/api/routes/admin_recap.py:42-62` (RecapOut), `:156-174` (`get_recap` return)
- Modify: `backend/src/sunday_clays/api/routes/_claysmasher.py:61-76` (ExportRound), `:118-123` (`_notes`); `backend/src/sunday_clays/api/routes/claysmasher.py:74-106` (`_rounds`)
- Modify: `backend/tests/integration/analytics_core/test_events_routes.py:304-342` (`_station_sheet` gains `dropped`), `:344-362` (pinned layout dicts); `backend/tests/integration/analytics_core/test_club_routes.py:70-81,171-220` (pinned AttendanceOut properties and bodies); `backend/tests/unit/api/test_claysmasher_helpers.py:64-74` (`_round` helper)
- Modify (typed mocks for the fields below): `frontend/src/features/events/mocks.ts` (`scored`/`stationWeek` spreads), `home/mocks.ts`, `club/mocks.ts`, `admin-recap/mocks.ts` (`thrown_out: []` on `regularRecap` and `specialRecap`), plus each inline literal `pnpm typecheck` names
- Test: the files above, `backend/tests/integration/analytics_core/test_claysmasher_export_route.py`, `backend/tests/integration/api/test_admin_recap_api.py`, `backend/tests/integration/api/test_thrown_out_schema.py` (new)

**Interfaces:**
- Consumes: `frames.load_thrown_out(session)`, the frame flags, `domain.thrown_out.thrown_out_phrase`, `LiveSeed.event(stats_excluded=…)` (T2a).
- Produces: `ThrownOutOut`, `thrown_out_out(items)`; `stats_excluded` on `EventSummaryOut`, `EventDetailOut`, `EventResultOut`, `WinnerOut`, `AttendanceOut`; `thrown_out` on `EventSummaryOut`, `EventDetailOut`, `RecapOut`; `StationLayoutOut.dropped`; `ExportRound.thrown_out`.

- [ ] **Step 1: Write the failing tests**

Scaffolding: `_station_sheet` gains `dropped: Collection[int | str] = ()` and inserts `dropped = str(parse_label(station)) in {str(parse_label(s)) for s in dropped}`; `test_station_matrix_keeps_unlinked_entries` layout dicts gain `"dropped": False`; `test_club_openapi_paths_and_response_schemas` AttendanceOut properties gain `"stats_excluded"` after `"target_total"`; the 3 dicts of `test_attendance_lists_every_event_with_head_count_and_rows` gain `"stats_excluded": False`.

`test_events_routes.py` (D1 = 2026-08-30, D2 = 2026-09-06, D3 = 2026-09-13):
```python
def test_a_thrown_out_sunday_counts_with_its_station_named(seed, viewer_client):
    ike, amy = seed.shooter("Hadley, Ike"), seed.shooter("Ace, Amy")
    seed.event(D2, stats_excluded=True, has_stations=True)
    ids = {d: (seed.round(d, ike, a), seed.round(d, amy, b)) for d, a, b in ((D1, 40, 30), (D2, 45, 41), (D3, 44, 38))}
    _station_sheet(seed.session, D2, {10: 8, 11: 7},
                   [(1, "hadley ike", ike, ids[D2][0], (6, 7)), (2, "ace amy", amy, ids[D2][1], (5, 7))], dropped=(11,))
    seed.finish(); seed.analyze()
    listed = {e["event_date"]: e for e in viewer_client.get("/api/events").json()}
    out = listed["2026-09-06"]
    assert (out["stats_excluded"], out["top_score"]) == (True, 45)
    assert out["thrown_out"] == [{"station_label": "11", "target_count": 7, "credited": True}]
    assert [(w["display_name"], w["stats_excluded"]) for w in out["winners"]] == [("Hadley, Ike", True)]
    assert (listed["2026-08-30"]["stats_excluded"], listed["2026-08-30"]["thrown_out"]) == (False, [])
    assert listed["2026-08-30"]["winners"][0]["stats_excluded"] is False
    detail = viewer_client.get(f"/api/events/{D2}").json()
    assert (detail["stats_excluded"], detail["vs_prev"]) == (True, None)
    assert detail["thrown_out"] == out["thrown_out"]
    assert [(r["score"], r["event_rank"], r["stats_excluded"]) for r in detail["results"]] == [(45, 1, True), (41, 2, True)]
    assert [(s["label"], s["dropped"]) for s in detail["stations"]["layout"]] == [("10", False), ("11", True)]
    after = viewer_client.get(f"/api/events/{D3}").json()["vs_prev"]
    assert (after["prev_date"], after["top_score_delta"], after["median_delta"]) == ("2026-08-30", 4, 6.0)

def test_a_sunday_level_rule_marks_the_sunday_without_a_station(seed, viewer_client):
    ike = seed.shooter("Hadley, Ike")
    seed.event(D2, stats_excluded=True)
    seed.round(D2, ike, 44)
    seed.finish(); seed.analyze()
    (out,) = viewer_client.get("/api/events").json()
    assert out["thrown_out"] == [{"station_label": None, "target_count": None, "credited": False}]
    (day,) = viewer_client.get("/api/club/attendance").json()
    assert day["stats_excluded"] is True

def test_notables_skip_a_thrown_out_sunday(seed, viewer_client):  # guard: route-level check of T3b
    ike = seed.shooter("Hadley, Ike")
    later = D3 + timedelta(days=7)
    seed.event(D2, stats_excluded=True)
    seed.event(later, stats_excluded=True)
    for week, score in zip(range(1, 6), (48, 39, 38, 37, 36), strict=True):  # week 1 = D2
        seed.round(D3 - timedelta(days=7 * week), ike, score)
    seed.round(D3, ike, 45)
    seed.round(later, ike, 50)
    seed.finish(); seed.analyze()
    assert [(n["kind"], n["detail"]) for n in viewer_client.get(f"/api/events/{D3}").json()["notables"]] == [("pb", "New personal best 45 (was 39)")]
    assert viewer_client.get(f"/api/events/{later}").json()["notables"] == []
```
`test_claysmasher_helpers.py`: `_round` gains `thrown_out: str | None = None` (7th field); add
```python
def test_notes_name_a_thrown_out_station_before_the_gauge_class() -> None:
    phrase = "Station 11 was thrown out; everyone was credited 7/7"
    (record,) = _records(render_csv([_round(gauge_class="20 Gauge", thrown_out=phrase)], SPORTING, "Ace, Amy"))
    assert record["Notes"] == "Imported from Sunday Clays; Station 11 was thrown out; everyone was credited 7/7; class: 20 Gauge"
    assert record["Total Hits"] == "41"
```
`test_claysmasher_export_route.py`:
```python
def test_a_thrown_out_sunday_is_exported_as_recorded_with_a_note(seed, session, viewer_client):
    amy = seed.shooter("Ace, Amy")
    seed.event(D1, stats_excluded=True, has_stations=True)
    rid = seed.round(D1, amy, 43)
    _station_entry(session, D1, rid, amy, "ace amy", SPORTING, (6, 7, 5, 6, 5, 8, 6))
    session.execute(text("UPDATE station_layouts SET dropped = true, dropped_source = 'auto' WHERE event_date = :d AND station_label = '10'"), {"d": D1})
    seed.finish()
    (record,) = _records(_export(viewer_client, amy)[SPORTING_CSV])
    assert (record["Total Hits"], record["Total Targets"]) == ("43", "50")
    assert record["Notes"] == "Imported from Sunday Clays; Station 10 was thrown out; everyone was credited 6/6"
```
`test_admin_recap_api.py` (merged from the old T5e and T6b drafts):
```python
def test_a_thrown_out_sunday_lists_its_station(fx_admin_client, fx_session):
    fx_session.execute(text("UPDATE station_layouts SET dropped = true, dropped_source = 'override' WHERE event_date = '2026-09-13' AND station_label = '9'"))
    fx_session.execute(text("UPDATE events SET stats_excluded = true WHERE event_date = '2026-09-13'"))
    clear_cache()
    assert fx_admin_client.get("/api/admin/recap/2026-09-13").json()["thrown_out"] == [{"station_label": "9", "target_count": 7, "credited": False}]

def test_recaps_without_a_thrown_out_station_list_none(fx_admin_client):
    for day in (LATEST, SPECIAL):
        assert fx_admin_client.get(f"/api/admin/recap/{day}").json()["thrown_out"] == []
```
`test_thrown_out_schema.py`:
```python
FIELDS = [("EventSummaryOut", "stats_excluded"), ("EventSummaryOut", "thrown_out"), ("EventDetailOut", "stats_excluded"),
          ("EventDetailOut", "thrown_out"), ("EventResultOut", "stats_excluded"), ("WinnerOut", "stats_excluded"),
          ("AttendanceOut", "stats_excluded"), ("StationLayoutOut", "dropped"), ("RecapOut", "thrown_out"),
          ("ThrownOutOut", "station_label"), ("ThrownOutOut", "target_count"), ("ThrownOutOut", "credited")]

@pytest.mark.parametrize(("model", "field"), FIELDS)
def test_thrown_out_fields_are_required_in_the_openapi_schema(model: str, field: str) -> None:
    assert field in create_app().openapi()["components"]["schemas"][model]["required"]
```

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/integration/analytics_core/test_events_routes.py tests/integration/analytics_core/test_club_routes.py tests/integration/analytics_core/test_claysmasher_export_route.py tests/unit/api/test_claysmasher_helpers.py tests/integration/api/test_admin_recap_api.py tests/integration/api/test_thrown_out_schema.py -q`. Expected: `KeyError: 'stats_excluded'`/`'thrown_out'`/`'dropped'`; `KeyError: 'ThrownOutOut'`; `TypeError` on the 7th `ExportRound` argument; the pinned layout and attendance dicts lack the new keys. The notables guard passes.

- [ ] **Step 3: Implement**

- `events.py`: `ThrownOutOut` and `thrown_out_out(items)`; `EventSummaryOut`/`EventDetailOut` (already `json_schema_serialization_defaults_required=True`) gain `stats_excluded: bool = False` and `thrown_out: list[ThrownOutOut] = Field(default_factory=list)`; `WinnerOut`/`EventResultOut` gain a required `stats_excluded: bool`; `StationLayoutOut.dropped: bool`. `_winners`/`_results` read `bool(r["stats_excluded"])`, `_special_results` sets False. `list_events` and `get_event` call `frames.load_thrown_out(session)` once and pass `thrown_out=thrown_out_out(thrown.get(d, ()))`. `_stations` layout selects `dropped`. `get_event`: `vs_prev=None if special or excluded else _vs_prev(regular.loc[~regular["stats_excluded"]], event)`.
- `club.py`: `AttendanceOut.stats_excluded: bool = False` after `target_total`; `club_attendance` passes it.
- `admin_recap.py`: `RecapOut.thrown_out: list[ThrownOutOut]` (required, after `rounds`); `get_recap` passes `thrown_out_out(frames.load_thrown_out(session).get(event_date, ()))` (a special Sunday has none).
- `_claysmasher.py`: `ExportRound.thrown_out: str | None = None` (last field, "the thrown_out_phrase for the round's Sunday"); `_notes` joins `SOURCE_NOTE`, the phrase if any, and `class: …` if any with `"; "`. `claysmasher.py:_rounds`: `phrases = {d: thrown_out_phrase(items) for d, items in frames.load_thrown_out(session).items()}`, `thrown_out=phrases.get(r.event_date)` (one memoised call; query count flat). `_STATIONS_SQL` unchanged: the export stays as recorded.
- Frontend: `cd frontend && pnpm typecheck` (runs `gen:api` from local source; it first fails with `Property 'stats_excluded' | 'thrown_out' | 'dropped' is missing`); add `stats_excluded: false`, `thrown_out: []`, `dropped: false` to each literal it names; no component change.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 plus `tests/integration/special tests/integration/api/test_page_cache.py tests/unit/api tests/integration/stations -q` (all pass); backend gate; `cd frontend && pnpm typecheck && pnpm lint && pnpm exec vitest --run`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/api/routes/{events,club,admin_recap,claysmasher,_claysmasher}.py backend/tests/integration/analytics_core/{test_events_routes,test_club_routes,test_claysmasher_export_route}.py backend/tests/unit/api/test_claysmasher_helpers.py backend/tests/integration/api/{test_admin_recap_api,test_thrown_out_schema}.py frontend/src` — `feat(api): flag thrown-out Sundays and stations on Sunday, attendance, recap and ClaySmasher routes` (+ trailer).

---

### Task T6c: Shooter rounds flag and club score numbers

**Depends on:** T6b (schema test file), T3b (shooter stats), T3a (boards). Keeps only `ShooterRoundOut`/`get_shooter_rounds` and the club routes; the shooter stats, splits, odometer and PBs were done by T3b, the Yir/weather/trend fields by T3c/T3d.

**Files:**
- Modify: `backend/src/sunday_clays/api/routes/shooters.py:118-135` (ShooterRoundOut), `:418-447` (`get_shooter_rounds`)
- Modify: `backend/src/sunday_clays/api/routes/club.py:151-195` (`club_summary`), `:240-254` (`club_distribution`)
- Modify (typed mocks for `ShooterRoundOut.stats_excluded`): `frontend/src/features/shooters/mocks.ts`, `home/mocks.ts` and inline literals in `shooters/charts.test.ts`, `home/components/MePanel.test.tsx`, `shooters/components/ProfileCharts.test.tsx`, as `pnpm typecheck` names them
- Test: `backend/tests/integration/analytics_core/test_shooters_routes.py`, `backend/tests/integration/analytics_core/test_club_routes.py`, `backend/tests/integration/api/test_thrown_out_schema.py` (append)

**Interfaces:**
- Consumes: `frames.stat_rounds`, `LiveSeed.event(stats_excluded=…)`, T3b's stats.
- Produces: `ShooterRoundOut.stats_excluded: bool`; club summary and distribution over scored rounds.

- [ ] **Step 1: Write the failing tests**

`test_shooters_routes.py` (TODAY = 2026-09-27, `W[k]` = k weeks back):
```python
def test_a_thrown_out_sunday_counts_but_stays_out_of_shooter_stats(seed, viewer_client):
    ike = seed.shooter("Hadley, Ike")
    for d in (W[7], W[1]):
        seed.event(d, stats_excluded=True)
    for d, score in ((W[7], 50), (W[3], 30), (W[2], 34), (W[1], 49), (W[0], 38)):
        seed.round(d, ike, score)
    seed.finish(); seed.analyze()
    body = viewer_client.get(f"/api/shooters/{ike}").json()
    stats = body["stats"]
    assert (stats["n_rounds"], stats["n_events"], stats["n_excluded"]) == (5, 5, 2)
    assert (stats["avg_score"], stats["median_score"], stats["best_score"]) == (34.0, 34.0, 38)
    assert (stats["wins"], stats["podiums"]) == (5, 5)
    odo = body["odometer"]
    assert (odo["rounds"], odo["clays_thrown"], odo["clays_broken"]) == (5, 250, 201)
    assert odo["hit_pct"] == pytest.approx(102 / 150)
    assert [(p["scope"], p["key"], p["score"], p["event_date"]) for p in body["pbs"]] == [
        ("overall", "all", 38, W[0].isoformat()), ("year", "2026", 38, W[0].isoformat())]
    window = viewer_client.get(f"/api/shooters/{ike}", params={"since": W[2].isoformat()}).json()["window_stats"]
    assert (window["n_rounds"], window["n_excluded"], window["avg_score"]) == (3, 1, 36.0)
    assert [r["stats_excluded"] for r in viewer_client.get(f"/api/shooters/{ike}/rounds").json()] == [True, False, False, True, False]
    months = viewer_client.get(f"/api/shooters/{ike}/splits", params={"by": "month"}).json()
    assert [(s["key"], s["n_rounds"], s["n_excluded"], s["avg"], s["best"]) for s in months] == [("2026-09", 4, 1, 34.0, 38)]

def test_both_doubleheader_rounds_of_a_thrown_out_sunday_count(seed, viewer_client):  # Review Focus 2
    ike = seed.shooter("Hadley, Ike")
    seed.event(W[1], stats_excluded=True)
    seed.round(W[2], ike, 30)
    seed.round(W[1], ike, 44, ordinal=1)
    seed.round(W[1], ike, 41, ordinal=2)
    seed.finish(); seed.analyze()
    stats = viewer_client.get(f"/api/shooters/{ike}").json()["stats"]
    assert (stats["n_rounds"], stats["n_events"], stats["n_excluded"], stats["avg_score"]) == (3, 2, 2, 30.0)
    (month,) = viewer_client.get(f"/api/shooters/{ike}/splits", params={"by": "month"}).json()
    assert (month["n_rounds"], month["n_excluded"]) == (3, 2)

def test_a_shooter_whose_only_round_was_thrown_out_has_counts_but_no_averages(seed, viewer_client):  # Review Focus 3
    ike, amy = seed.shooter("Hadley, Ike"), seed.shooter("Ace, Amy")
    seed.event(W[1], stats_excluded=True)
    seed.round(W[2], ike, 30)
    seed.round(W[1], ike, 35)
    seed.round(W[1], amy, 44)
    seed.finish(); seed.analyze()
    body = viewer_client.get(f"/api/shooters/{amy}", params={"since": W[1].isoformat()}).json()
    window = body["window_stats"]
    assert (window["n_rounds"], window["n_excluded"], window["avg_score"], window["median_score"], window["best_score"]) == (1, 1, None, None, None)
    assert body["odometer"]["hit_pct"] is None and body["pbs"] == []
    board = lambda metric: {r["shooter_id"] for r in viewer_client.get("/api/leaderboards", params={"period": "season", "metric": metric, "as_of": TODAY.isoformat()}).json()["rows"]}
    assert amy in board("rounds") and amy in board("wins") and amy not in board("avg_score")
```
`test_club_routes.py` (D2 = 2026-09-06, D3 = 2026-09-13):
```python
def test_club_score_numbers_leave_out_a_thrown_out_sunday(seed, viewer_client):
    ike, amy = seed.shooter("Hadley, Ike"), seed.shooter("Ace, Amy")
    seed.event(D3, stats_excluded=True)
    for d, a, b in ((D2, 40, 30), (D3, 50, 48)):
        seed.round(d, ike, a); seed.round(d, amy, b)
    seed.finish()
    s = viewer_client.get("/api/club/summary").json()
    assert (s["n_rounds"], s["clays_thrown"], s["clays_broken"]) == (4, 200, 168)
    assert (s["avg_score"], s["median_score"], s["top_score"], s["n_perfect"]) == (35.0, 35.0, 40, 0)
    (year,) = viewer_client.get("/api/club/distribution").json()
    assert (year["key"], year["n"], year["mean"], year["counts"][50]) == ("2026", 2, 35.0, 0)
```
`test_thrown_out_schema.py`: append `("ShooterRoundOut", "stats_excluded")`, plus guard rows (already green from T3b/T3c/T3d/T6a) `("ShooterStatsOut", "n_excluded")`, `("SplitOut", "n_excluded")`, `("YirTotalsOut", "n_excluded")`, `("YirShooterTotalsOut", "n_excluded")`, `("YirTopRoundOut", "stats_excluded")`, `("OnThisDayItemOut", "stats_excluded")`, `("WeatherEventOut", "stats_excluded")`, `("EventTrendOut", "stats_excluded")`, `("QueryResult", "thrown_out_dates")`.

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/integration/analytics_core/test_shooters_routes.py tests/integration/analytics_core/test_club_routes.py tests/integration/api/test_thrown_out_schema.py -q`. Expected: `KeyError: 'stats_excluded'` on the rounds list and the `ShooterRoundOut` schema row; club `avg_score 42.0 != 35.0`. The shooter stats assertions, the doubleheader and only-round tests already pass after T3b/T3a (guards at route level); the appended schema guard rows pass.

- [ ] **Step 3: Implement**

- `shooters.py`: `ShooterRoundOut.stats_excluded: bool`; `get_shooter_rounds` passes `bool(r["stats_excluded"])`.
- `club.py`: `club_summary` takes `avg_score`/`median_score`/`top_score`/`n_perfect` from `frames.stat_rounds(rounds)["score"]` (None when empty), `n_rounds`/`clays_thrown`/`clays_broken`/`status_by_year` unchanged; `club_distribution` returns `score_distribution(frames.stat_rounds(in_window(rounds, since, as_of)))`.
- Frontend: `cd frontend && pnpm typecheck`; add `stats_excluded: false` to each `ShooterRound` literal it names.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 plus `tests/integration/analytics_core tests/integration/extras tests/integration/special -q`; backend gate; `cd frontend && pnpm typecheck && pnpm lint && pnpm exec vitest --run`.

- [ ] **Step 5: Commit**

`git add backend/src/sunday_clays/api/routes/{shooters,club}.py backend/tests/integration/analytics_core/{test_shooters_routes,test_club_routes}.py backend/tests/integration/api/test_thrown_out_schema.py frontend/src` — `feat(api): flag thrown-out rounds on the profile and keep them out of club score numbers` (+ trailer).

---

### Task T6d: The 10/25 case through the routes (thrown-out world)

**Depends on:** T6c (and so T3a, T3b, T4a, T6b).

**Files:**
- Test: `backend/tests/integration/thrown_out/test_thrown_out_routes.py` (new)

**Interfaces:**
- Consumes: `fx_thrown_out_viewer_client`, `fx_thrown_out_session`, `clear_cache`; every route field above.
- Produces: nothing new — an end-to-end backend check of Review Focus 5 (one count, one stat, one station, one ordered sequence, one prefix gate on the synthetic world, spec §7).

- [ ] **Step 1: Write the failing tests**

```python
SUNDAY, FIRST = "2026-10-25", "2026-08-23"
WINDOW = {"since": FIRST, "as_of": SUNDAY}

def _hadley(s):
    return s.execute(text("SELECT shooter_id FROM rounds WHERE event_date = :d AND name_key = 'hadley ike'"), {"d": SUNDAY}).scalar_one()

def test_the_thrown_out_sunday_is_flagged_and_named(fx_thrown_out_viewer_client):
    c = fx_thrown_out_viewer_client
    detail = c.get(f"/api/events/{SUNDAY}").json()
    assert detail["stats_excluded"] is True and detail["vs_prev"] is None
    assert detail["thrown_out"] == [{"station_label": "11", "target_count": 7, "credited": True}]
    assert (detail["top_score"], detail["median"]) == (43, 35.0)          # count: the official numbers stand
    listed = c.get("/api/events").json()                                   # date order; the latest is last
    assert (listed[-1]["event_date"], listed[-1]["stats_excluded"]) == (SUNDAY, True)

def test_scores_and_pbs_leave_the_free_targets_out(fx_thrown_out_viewer_client, fx_thrown_out_session):
    c = fx_thrown_out_viewer_client
    body = c.get(f"/api/shooters/{_hadley(fx_thrown_out_session)}").json()
    assert body["stats"]["n_excluded"] == 1 and body["stats"]["n_rounds"] == 10
    assert max(p["score"] for p in body["pbs"]) == 41                      # stat + prefix gate: 43 is not a PB
    assert 43.0 not in [r["value"] for r in c.get("/api/records", params=WINDOW).json()["highest_scores"]]

def test_station_11_counts_only_real_shooting(fx_thrown_out_viewer_client):
    stations = fx_thrown_out_viewer_client.get("/api/stations", params=WINDOW).json()["stations"]
    st11 = next(s for s in stations if s["label"] == "11")
    assert (st11["hits"], st11["n_targets"]) == (364, 567)

def test_standings_and_the_race_are_unchanged_by_the_flag(fx_thrown_out_viewer_client, fx_thrown_out_session):  # guard
    c, s = fx_thrown_out_viewer_client, fx_thrown_out_session
    points = {"period": "ytd", "metric": "season_points", "as_of": SUNDAY}
    race = {"period": "ytd", "metric": "season_points", "top": 10, "from": FIRST, "to": SUNDAY}
    before = (c.get("/api/leaderboards", params=points).json()["rows"], c.get("/api/leaderboards/history", params=race).json())
    s.execute(text("UPDATE events SET stats_excluded = false"))
    s.execute(text("UPDATE station_layouts SET dropped = false, dropped_source = NULL"))
    clear_cache()
    after = (c.get("/api/leaderboards", params=points).json()["rows"], c.get("/api/leaderboards/history", params=race).json())
    assert before == after
```
(`/api/leaderboards/history` takes `from`/`to` as query aliases, `leaderboard_history.py:55-56`.)

- [ ] **Step 2: Run to verify RED**

On T6d's base the first three tests pass, because every behaviour they check is already delivered; they are an integration net, not new behaviour. To show they bite, run the file on the T2c commit in a throwaway worktree: `git worktree add ../t6d-red <T2c commit> && cp backend/tests/integration/thrown_out/test_thrown_out_routes.py ../t6d-red/backend/tests/integration/thrown_out/ && (cd ../t6d-red/backend && uv run pytest tests/integration/thrown_out/test_thrown_out_routes.py -q)` — expected failures `KeyError: 'stats_excluded'`/`'thrown_out'`, `assert 43 == 41` on the PB max, `43.0 in highest_scores`, `(427, 630) != (364, 567)`; the standings guard passes there too. Paste that output as RED, then `git worktree remove ../t6d-red`.

- [ ] **Step 3: Implement**

No production code. If any assertion fails on T6d's base, the bug belongs to the owning task (events T6b, PBs T3b, records T3a, stations T4a); report it there instead of patching here.

- [ ] **Step 4: Run to verify GREEN**

`cd backend && uv run pytest tests/integration/thrown_out -q` (all pass); backend gate.

- [ ] **Step 5: Commit**

`git add backend/tests/integration/thrown_out/test_thrown_out_routes.py` — `test(api): the thrown-out world through the routes` (+ trailer).

---

### Task T7a: Shared thrown-out helpers and thrown-out mock fixtures

**Depends on:** every backend task (T1a–T6d). The backend tasks already added the new required fields to the existing typed mocks; T7a adds only the new thrown-out mocks.

**Files:**
- Create: `frontend/src/features/events/thrownOut.ts`, `frontend/src/components/ui/ThrownOutMark.tsx`, `frontend/src/components/charts/builders/thrownOut.ts`
- Modify: `frontend/src/features/events/mocks.ts` (new exports after `:450`)
- Test: `frontend/src/features/events/thrownOut.test.ts`, `frontend/src/components/ui/ThrownOutMark.test.tsx`, `frontend/src/components/charts/builders/thrownOut.test.ts` (all new)

**Interfaces:**
- Consumes: `components['schemas']['ThrownOutOut']` and the fields from the backend tasks; contract §Copy.
- Produces: `thrownOut.ts` (`ThrownOut`, `thrownOutPhrase`, `SUNDAY_THROWN_OUT`, `thrownOutBanner`, `excludedNote`, `THROWN_OUT_RECAP_LINE`); `ThrownOutMark`; `builders/thrownOut.ts` (`THROWN_OUT_COLUMN`, `thrownOutCell`, `hollowPoint`, `hollowSeries`, `thrownOutAxisTooltip`); mocks `THROWN_OUT_10: ThrownOut = { station_label: '10', target_count: 8, credited: true }`, `thrownOutDetail: EventDetail`, `thrownOutSummary: EventSummary`.

- [ ] **Step 1: Write the failing tests**

```ts
// events/thrownOut.test.ts
const st = (station_label: string, target_count: number, credited = true): ThrownOut => ({ station_label, target_count, credited });
const SUNDAY: ThrownOut = { station_label: null, target_count: null, credited: false };
it.each<[ThrownOut[], string]>([
  [[st('11', 7)], 'Station 11 was thrown out; everyone was credited 7/7'],
  [[st('11', 7, false)], 'Station 11 was thrown out'],
  [[st('4', 7), st('11', 7)], 'Stations 4 and 11 were thrown out; everyone was credited in full'],
  [[st('4', 7, false), st('11', 7)], 'Stations 4 and 11 were thrown out'],
  [[st('3', 7, false), st('4', 7), st('11', 7)], 'Stations 3, 4 and 11 were thrown out'],
  [[SUNDAY], 'A station was thrown out this Sunday'],
  [[st('7A', 6), SUNDAY], 'Station 7A was thrown out; everyone was credited 6/6'],
  [[], 'A station was thrown out this Sunday'],
])('thrownOutPhrase(%j) is %s', (items, want) => expect(thrownOutPhrase(items)).toBe(want));
it('builds the Sunday banner from the phrase', () =>
  expect(thrownOutBanner([st('11', 7)])).toBe(
    "Station 11 was thrown out; everyone was credited 7/7. Today's results and standings count, marked *. These scores are left out of averages, PBs and station stats."));
it.each([[0, null], [1, '1 round marked * not in the average'], [2, '2 rounds marked * not in the average']])(
  'excludedNote(%i)', (n, want) => expect(excludedNote(n)).toBe(want));
it('pins the recap line the server sends', () =>
  expect(THROWN_OUT_RECAP_LINE).toBe('A station was thrown out this Sunday. Its results count; its scores stay out of averages and PBs.'));
it('uses no banned word', () =>
  expect([thrownOutPhrase([SUNDAY]), thrownOutBanner([st('4', 7), st('11', 7)]), excludedNote(2), THROWN_OUT_RECAP_LINE].join(' ')).not.toMatch(BANNED_WORDS));

// ui/ThrownOutMark.test.tsx
it('shows a plain muted asterisk with the phrase as title and screen-reader text', () => {
  render(<p>43<ThrownOutMark phrase="Station 11 was thrown out" /></p>);
  const mark = screen.getByTitle('Station 11 was thrown out');
  expect(mark).toHaveClass('ml-0.5', 'text-text-muted');
  expect(mark.querySelector('[aria-hidden="true"]')).toHaveTextContent(/^\*$/);
  expect(mark.querySelector('.sr-only')).toHaveTextContent('Station 11 was thrown out');
  expect(screen.getByText(/^43/).textContent).toBe('43* Station 11 was thrown out');
});

// builders/thrownOut.test.ts
it('marks a thrown-out row yes, others blank', () => { expect(thrownOutCell(true)).toBe('yes'); expect(thrownOutCell(false)).toBe(''); });
it('makes only thrown-out points hollow', () => {
  expect(hollowPoint(43, true)).toEqual({ value: 43, symbol: 'emptyCircle', symbolSize: 8 });
  expect(hollowPoint(43, false)).toBe(43);
});
it('hollows the named series at the flagged indices only, without mutating', () => {
  const option = { series: [{ name: 'A', type: 'line', data: [1, 2] }, { name: 'B', type: 'line', data: [3, 4] }] };
  expect(hollowSeries(option, ['A'], [false, true]).series).toEqual([
    { name: 'A', type: 'line', data: [1, { value: 2, symbol: 'emptyCircle', symbolSize: 8 }] },
    { name: 'B', type: 'line', data: [3, 4] }]);
  expect(option.series[0]?.data).toEqual([1, 2]);
});
it('stars the tooltip header of a thrown-out date, on category and time axes', () => {
  const f = thrownOutAxisTooltip(new Set(['2026-10-25']));
  expect(f([{ axisValue: '2026-10-25', axisValueLabel: '2026-10-25', marker: '', seriesName: 'Score', value: 43 }])).toBe('2026-10-25 *<br/>Score: 43');
  expect(f([{ axisValue: '2026-10-04', axisValueLabel: '2026-10-04', marker: '', seriesName: 'Score', value: 40 }])).toBe('2026-10-04<br/>Score: 40');
  expect(f([{ axisValue: Date.UTC(2026, 9, 25), axisValueLabel: 'Oct 25', marker: '', seriesName: 'Middle score', value: ['2026-10-25', 34] },
            { axisValue: Date.UTC(2026, 9, 25), axisValueLabel: 'Oct 25', marker: '', seriesName: 'Top score', value: ['2026-10-25', null] }])).toBe('Oct 25 *<br/>Middle score: 34');
});
```

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/features/events/thrownOut.test.ts src/components/ui/ThrownOutMark.test.tsx src/components/charts/builders/thrownOut.test.ts` — fails to resolve `./thrownOut`, `./ThrownOutMark`, `./thrownOut`.

- [ ] **Step 3: Implement**

- `pnpm gen:api` (runs `export_openapi` from local backend source; no running backend needed) so `ThrownOutOut` is in `schema.d.ts`.
- `thrownOutPhrase`: station items (`station_label !== null`) in order; none → `SUNDAY_THROWN_OUT`; one → `Station ${l} was thrown out` + `; everyone was credited ${t}/${t}` when credited; several → `Stations a, b and c were thrown out` + `; everyone was credited in full` when all credited. `thrownOutBanner` and `excludedNote` per the contract.
- `thrownOutAxisTooltip`: key from the first param's `axisValue` (number → `new Date(v).toISOString().slice(0, 10)`, else `String(v)`); header `escapeHtml(axisValueLabel)` + `' *'` when the key is in the set; lines `${marker}${escapeHtml(seriesName)}: ${escapeHtml(v)}` with `v` the last array element, skipping null/undefined; joined with `<br/>`.
- `hollowSeries` maps `option.series` and replaces `data[i]` with `hollowPoint(data[i], excluded[i])` on the named series only.
- Mocks: `THROWN_OUT_10`; `thrownOutDetail = { ...eventDetail, event_date: '2026-10-25', stats_excluded: true, thrown_out: [THROWN_OUT_10], difficulty: null, vs_prev: null, results: eventDetail.results.map((r) => ({ ...r, stats_excluded: true, adjusted: null, rating_delta: null })), stations: { ...stations, layout: layout.map((s) => ({ ...s, dropped: s.label === '10' })) } }`; `thrownOutSummary = { ...eventSummaries[1], event_date: '2026-10-25', stats_excluded: true, thrown_out: [THROWN_OUT_10] }`, kept out of `eventSummaries`.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (all pass); `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test` green with no other test changed.

- [ ] **Step 5: Commit**

`git add frontend/src/features/events/thrownOut.ts frontend/src/features/events/thrownOut.test.ts frontend/src/components/ui/ThrownOutMark.tsx frontend/src/components/ui/ThrownOutMark.test.tsx frontend/src/components/charts/builders/thrownOut.ts frontend/src/components/charts/builders/thrownOut.test.ts frontend/src/features/events/mocks.ts` — `feat(frontend): thrown-out phrase, * mark, chart helpers and mocks` (+ trailer).

---

### Task T7b: Admin `station_drop` rule

**Depends on:** T7a. (`FindingsList` `station_dropped` belongs to T1c.)

**Files:**
- Modify: `frontend/src/features/admin-identity/rules.ts:3-25` (types, labels), `:35-65` (fields), `:84-128` (payload)
- Modify: `frontend/src/features/admin-identity/api.ts:69-73` (body `payload` type)
- Modify: `frontend/src/features/admin-identity/components/Fields.tsx:70` (new options const), `components/RuleCreateForm.tsx:16-119`
- Modify: `frontend/e2e/admin-identity.spec.ts:41` (`toHaveCount(8)` → `toHaveCount(9)`)
- Test: `frontend/src/features/admin-identity/rules.test.ts`, `frontend/src/features/admin-identity/components/RuleCreateForm.test.tsx`

**Interfaces:**
- Consumes: backend `StationDropPayload`.
- Produces: `RuleType` `'station_drop'` labelled `'Thrown-out station'`; `RuleFields.dropped`; `RulePayload`; `DROPPED_OPTIONS`.

- [ ] **Step 1: Write the failing tests**

```ts
// rules.test.ts: the RULE_TYPES test becomes 'offers exactly the nine C5 rule types…'; its sorted list gains 'station_drop' (between 'set_status' and 'station_reset')
// valid it.each (tuple type RulePayload):
['station_drop', { eventDate: '2026-10-25', stationNo: '11', dropped: 'yes' }, { event_date: '2026-10-25', station_label: '11', dropped: true }],
['station_drop', { eventDate: '2026-01-11', stationNo: ' 7a ', dropped: 'no' }, { event_date: '2026-01-11', station_label: '7A', dropped: false }],
['station_drop', { eventDate: '2026-10-25', stationNo: '', dropped: 'yes' }, { event_date: '2026-10-25', station_label: null, dropped: true }],
// invalid it.each:
['station_drop', { stationNo: '11', dropped: 'yes' }],
['station_drop', { eventDate: '2026-10-25', stationNo: '11' }],
['station_drop', { eventDate: '2026-10-25', stationNo: '', dropped: 'no' }],
['station_drop', { eventDate: '2026-10-25', stationNo: 'A7', dropped: 'yes' }],
it('labels the new rule', () => expect(RULE_LABELS.station_drop).toBe('Thrown-out station'));

// RuleCreateForm.test.tsx: 'offers the eight rule types…' becomes 'offers the nine rule types…' with toHaveLength(9)
it('station_drop takes a Sunday, an optional station and whether it was thrown out', async () => {
  const user = userEvent.setup();
  renderWithProviders(<RuleCreateForm />);
  await chooseType(user, 'station_drop');
  fireEvent.change(screen.getByLabelText('Sunday'), { target: { value: '2026-10-25' } });
  await user.type(screen.getByLabelText('Station (like 7 or 7A; blank for the whole Sunday)'), '11');
  await user.selectOptions(screen.getByLabelText('Thrown out?'), 'yes');
  await create(user);
  expect(created).toEqual([{ rule_type: 'station_drop', payload: { event_date: '2026-10-25', station_label: '11', dropped: true }, note: null }]);
});
```

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/features/admin-identity` — the nine-type, label, payload and form assertions fail.

- [ ] **Step 3: Implement**

`rules.ts`: `'station_drop'` after `'station_reset'` in `RULE_TYPES`, `RULE_LABELS.station_drop = 'Thrown-out station'`, `dropped: ''` in `EMPTY_FIELDS`; the `station_drop` case reads `label = f.stationNo.trim() === '' ? null : stationLabel(f.stationNo)` and returns null for an empty `eventDate`, `dropped === ''`, a non-blank station that does not parse, or a blank station with `'no'`; else `{ event_date, station_label: label, dropped: f.dropped === 'yes' }`. `api.ts`: body `payload: RulePayload`. `Fields.tsx`: `DROPPED_OPTIONS = [{ value: '', label: 'Choose…' }, { value: 'yes', label: 'Thrown out' }, { value: 'no', label: 'Not thrown out' }]`. `RuleCreateForm.tsx` case: `TextField label="Sunday" type="date"` (`eventDate`), `TextField label="Station (like 7 or 7A; blank for the whole Sunday)"` (`stationNo`, upper-cased like `station_reset`), `SelectField label="Thrown out?" options={DROPPED_OPTIONS}` (`dropped`). `admin-identity.spec.ts:41` → `toHaveCount(9)`.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (pass); frontend gate. (The e2e spec runs in T8c/T8d.)

- [ ] **Step 5: Commit**

`git add frontend/src/features/admin-identity frontend/e2e/admin-identity.spec.ts` — `feat(admin): thrown-out station rule` (+ trailer).

---

### Task T7c: Sunday page, results table, station heatmap, Sunday list and calendar

**Depends on:** T7a.

**Files:**
- Modify: `frontend/src/features/events/pages/EventDetailPage.tsx:105-171` (`ScoredEvent`), `:236` (VsPrev)
- Modify: `frontend/src/features/events/components/ResultsTable.tsx:38-116`, `components/EventList.tsx:40-50`, `components/SeasonCalendar.tsx:46-56,120-130`
- Modify: `frontend/src/features/events/charts.ts:28-73` (`stationLongData`, `stationMatrixModel`)
- Test: `frontend/src/features/events/pages/EventDetailPage.test.tsx`, `components/ResultsTable.test.tsx`, `charts.test.ts`, `components/EventList.test.tsx`, `components/SeasonCalendar.test.tsx`

**Interfaces:**
- Consumes: T7a helpers and mocks; `EventDetail.stats_excluded/thrown_out`, `EventResult.stats_excluded`, `layout[].dropped`.
- Produces: `ResultsTable` prop `phrase?: string` (default `SUNDAY_THROWN_OUT`).

- [ ] **Step 1: Write the failing tests**

```ts
// EventDetailPage.test.tsx
it('a Sunday with a station thrown out shows the banner, starred official numbers and no difficulty or comparison', async () => {
  renderEvent(thrownOutDetail);
  const results = await screen.findByRole('table', { name: 'Results' });
  expect(screen.getByRole('note')).toHaveTextContent(
    "Station 10 was thrown out; everyone was credited 8/8. Today's results and standings count, marked *. These scores are left out of averages, PBs and station stats.");
  expect(screen.getAllByTitle('Station 10 was thrown out; everyone was credited 8/8').length).toBeGreaterThanOrEqual(2 + thrownOutDetail.results.length);
  expect(screen.queryByText('Difficulty')).toBeNull();
  expect(screen.queryByRole('region', { name: 'vs previous Sunday' })).toBeNull();
  const cells = within(within(results).getByRole('row', { name: /Nordquist, Sherman/ })).getAllByRole('cell');
  expect(cells[2]).toHaveTextContent('42* Station 10 was thrown out; everyone was credited 8/8');
  expect(cells[3]).toHaveTextContent('—');
  expect(cells.at(-1)).toHaveTextContent('—');
});
it('a normal Sunday has no thrown-out note', async () => {
  renderEvent(eventDetail);
  await screen.findByRole('table', { name: 'Results' });
  expect(screen.queryByTitle(/thrown out/)).toBeNull();
});

// charts.test.ts
describe('a thrown-out station', () => {
  const dropped: StationMatrix = { ...matrix, layout: [
    { label: '4', station_no: 4, target_count: 7, dropped: false },
    { label: '10', station_no: 10, target_count: 8, dropped: true }] };
  it('stars the column, reads "credited" in every cell and greys the heatmap column', () => {
    const model = stationMatrixModel(dropped, results);
    expect(model.columns[2]).toEqual({ key: 's10', label: 'Stn 10 * (8)', type: 'string' });
    expect(model.rows.map((r) => r.s10)).toEqual(['credited', 'credited', 'credited', 'credited']);
    const option = model.option as { xAxis: { data: string[] }; series: { markArea?: unknown }[] };
    expect(option.xAxis.data).toEqual(['Stn 4', 'Stn 10 *']);
    expect(option.series[0]?.markArea).toEqual({ silent: true, itemStyle: { color: colors.outlineVariant },
      data: [[{ xAxis: 'Stn 10 *' }, { xAxis: 'Stn 10 *' }]] });
    expect(stationLongData(dropped).rows.filter((r) => r.station === 'Stn 10 *').map((r) => r.hits)).toEqual([null, null, null, null]);
  });
  it('keeps a lettered thrown-out label', () => {  // Review Focus 1
    const lettered: StationMatrix = { ...matrix, layout: [{ label: '7A', station_no: 7, target_count: 6, dropped: true }] };
    expect(stationMatrixModel(lettered, results).columns[1]?.label).toBe('Stn 7A * (6)');
  });
  it('a normal layout has no grey column', () =>
    expect((stationMatrixModel(matrix, results).option as { series: { markArea?: unknown }[] }).series[0]?.markArea).toBeUndefined());
});

// EventList.test.tsx
it('stars a Sunday with a station thrown out, naming it for screen readers', () => {
  renderWithProviders(<EventList year={2026} events={[thrownOutSummary]} />);
  expect(screen.getByRole('link', { name: /Oct 25, 2026.*Station 10 was thrown out; everyone was credited 8\/8/ })).toBeInTheDocument();
  expect(summaryLine(thrownOutSummary)).not.toContain('*');
});

// SeasonCalendar.test.tsx
it('labels and titles a Sunday with a station thrown out, with a visible *', () => {
  expect(cellLabel(thrownOutSummary)).toBe(`Oct 25, 2026 — ${thrownOutSummary.n_shooters} shooters · Station 10 was thrown out; everyone was credited 8/8`);
  renderWithProviders(<SeasonCalendar year={2026} events={[thrownOutSummary]} />);
  const cell = screen.getByRole('link', { name: cellLabel(thrownOutSummary) });
  expect(cell).toHaveAttribute('title', cellLabel(thrownOutSummary));
  expect(cell).toHaveTextContent('25*');
});
```

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/features/events` — no note, the Difficulty tile still shows, the column reads `Stn 10 (8)`, no `markArea`, the cell label has no phrase.

- [ ] **Step 3: Implement**

- `ScoredEvent`: `phrase = thrownOutPhrase(event.thrown_out)`; when `event.stats_excluded`, `<p role="note" className="rounded-card border border-accent p-3">{thrownOutBanner(event.thrown_out)}</p>` above the partial-results note; Median and Top score render `<>{formatScore(x)}<ThrownOutMark phrase={phrase} /></>`; the Difficulty `Stat` renders only when `!event.stats_excluded`; `ResultsTable phrase={phrase} complete={event.results_complete && !event.stats_excluded}`; `:236` VsPrevCard condition adds `&& !event.stats_excluded`.
- `ResultsTable`: score cell `{r.score}{r.stats_excluded && <ThrownOutMark phrase={phrase} />}` (adjusted is already null → '—').
- `charts.ts`: a dropped layout item gives column `{ key: \`s${label}\`, label: \`Stn ${label} * (${t})\`, type: 'string' }` and cell `'credited'` on every row; `stationLongData` names it `Stn ${label} *` with `hits: null`; `stationMatrixModel` adds to the heatmap series `markArea: { silent: true, itemStyle: { color: colors.outlineVariant }, data: dropped.map((l) => [{ xAxis: l }, { xAxis: l }]) }` only when some station is dropped.
- `EventList`: after the summary `<span>`, `{e.stats_excluded && <ThrownOutMark phrase={thrownOutPhrase(e.thrown_out)} />}`.
- `SeasonCalendar`: the scored branch of `cellLabel` appends `` ` · ${thrownOutPhrase(e.thrown_out)}` `` when excluded; the scored `<Link>` gets `title={event.stats_excluded ? cellLabel(event) : undefined}` and renders `{dayOfMonth}{event.stats_excluded && <span aria-hidden="true">*</span>}`.

- [ ] **Step 4: Run to verify GREEN**

`cd frontend && pnpm vitest run src/features/events` (pass, existing tests unchanged); frontend gate.

- [ ] **Step 5: Commit**

`git add frontend/src/features/events` — `feat(events): thrown-out banner, starred results, greyed heatmap column, hidden difficulty and comparison` (+ trailer).

---

### Task T7d: Home, recap card, share, On this day, YIR, recap email, club, weather and Explore

**Depends on:** T7a. Owns the `admin-recap/format.ts` email line.

**Files:**
- Modify: `frontend/src/features/home/components/LatestEventCard.tsx:80-101`, `MePanel.tsx:18-39,55-58`, `ClubPulse.tsx:21-33`, `TurnoutChart.tsx:16-31`
- Modify: `frontend/src/features/insights/components/RecapCard.tsx:19-48`
- Modify: `frontend/src/features/share/components/EventShareCard.tsx:23-39`
- Modify: `frontend/src/features/yir/components/OnThisDayCard.tsx:49-56`, `yir/pages/YirClubPage.tsx:14-38`, `yir/pages/YirShooterPage.tsx:19-50`
- Modify: `frontend/src/features/admin-recap/format.ts:50-65`
- Modify: `frontend/src/features/club/charts.ts:31-50,98-144`
- Modify: `frontend/src/features/weather/charts.ts:50-97` (`difficultyFitChart`), `:99-104` (`windRoseChart`), `frontend/src/features/weather/conditions.ts:38-46` (`summarize`)
- Modify: `frontend/src/components/charts/explore.ts:132-137` (`toTabular`)
- Test: `home/components/{LatestEventCard,MePanel,ClubPulse,TurnoutChart}.test.tsx`, `insights/components/RecapCard.test.tsx`, `share/components/EventShareCard.test.tsx`, `yir/components/OnThisDayCard.test.tsx`, `yir/pages/{YirClubPage,YirShooterPage}.test.tsx`, `admin-recap/format.test.ts`, `club/charts.test.ts`, `weather/{charts,conditions}.test.ts`, `components/charts/explore.test.ts`

**Interfaces:**
- Consumes: T7a; `Recap.thrown_out`, `OnThisDayItem.stats_excluded`, `YirTotals.n_excluded`, `EventTrend.stats_excluded` (rolling fields nullable), `AttendancePoint.stats_excluded`, `WeatherEvent.stats_excluded`, `QueryResult.thrown_out_dates`, the `home.sunday-recap` how line.
- Produces: `LastResult.thrownOut`; `pulseStats(...).seasonHigh` skips excluded Sundays; `toTabular` adds `thrown_out` when the server lists dates.

- [ ] **Step 1: Write the failing tests**

```ts
// MePanel.test.tsx: the two existing lastResult toEqual objects gain `thrownOut: false`
it('stars a thrown-out last Sunday and shows no rating move', () =>
  expect(lastResult([{ ...latest, stats_excluded: true, mu_before: 35, mu_after: 35.4 }])).toEqual(
    { date: latest.event_date, score: latest.score, rank: latest.event_rank, ratingMove: null, thrownOut: true }));
// ClubPulse.test.tsx
it('leaves a Sunday with a station thrown out out of the high score, but counts it as scored', () => {
  const week = seasonEvents[0] as EventSummary;
  expect(pulseStats([...seasonEvents, { ...week, event_date: '2026-09-20', top_score: 50, stats_excluded: true }])).toMatchObject({ scored: 4, seasonHigh: 49 });
});
// LatestEventCard.test.tsx
it('stars the winner score, median and top score of a Sunday with a station thrown out', async () => {
  server.use(http.get('*/api/events/:date', () => HttpResponse.json({ ...latestEvent, stats_excluded: true, thrown_out: [{ station_label: '11', target_count: 7, credited: true }] })));
  renderWithProviders(<LatestEventCard />);
  await screen.findByText(/^Winner/);
  expect(screen.getAllByTitle('Station 11 was thrown out; everyone was credited 7/7')).toHaveLength(3);
});
// RecapCard.test.tsx
it('discloses a thrown-out Sunday from its how line', () => {
  const how = [...recapInsight.how, [{ t: 'text', v: THROWN_OUT_RECAP_LINE }]];
  renderWithProviders(<RecapCard insight={{ ...recapInsight, how }} />);
  expect(screen.getByTitle(SUNDAY_THROWN_OUT)).toBeInTheDocument();
  expect(screen.getByText(THROWN_OUT_RECAP_LINE)).toBeInTheDocument();
});
it('a normal recap has no mark', () => {
  renderWithProviders(<RecapCard insight={recapInsight} />);
  expect(screen.queryByTitle(SUNDAY_THROWN_OUT)).toBeNull();
});
// EventShareCard.test.tsx
it('stars the median and scores and footnotes a station thrown out', () => {
  render(<EventShareCard event={thrownOutDetail} />);
  expect(screen.getByText(/median 34\*/)).toBeInTheDocument();
  expect(screen.getByText('42*')).toBeInTheDocument();
  expect(screen.getByText('* Station 10 was thrown out; everyone was credited 8/8.')).toBeInTheDocument();
});
// OnThisDayCard.test.tsx
it('stars a past Sunday with a station thrown out', async () => {
  const [first, ...rest] = ON_THIS_DAY.items;
  server.use(http.get('*/api/on-this-day', () => HttpResponse.json({ ...ON_THIS_DAY, items: [{ ...first, stats_excluded: true }, ...rest] })));
  renderWithProviders(<OnThisDayCard />);
  expect(await screen.findByTitle('A station was thrown out this Sunday')).toBeInTheDocument();
});
// YirClubPage.test.tsx (YirShooterPage.test.tsx the same with YIR_GRIMSBY_2025 and its route)
it('says how many rounds marked * are not in the average', async () => {
  server.use(http.get('*/api/yir/:year', () => HttpResponse.json({ ...YIR_2025, totals: { ...YIR_2025.totals, n_excluded: 20 } })));
  renderYear(2025);
  expect(await screen.findByText('20 rounds marked * not in the average')).toBeInTheDocument();
});
// admin-recap/format.test.ts
it('opens with the thrown-out line on a Sunday with a station thrown out', () => {
  const line = "Station 11 was thrown out; everyone was credited 7/7, so this week's scores aren't used in averages, PBs or station stats.";
  const r = { ...regularRecap, thrown_out: [{ station_label: '11', target_count: 7, credited: true }] };
  expect(formatRecap(r).text).toContain(`Sunday, September 27, 2026\n\n${line}\nTurnout: 24 came out`);
  expect(formatRecap(r).markdown).toContain(`${line}\n\nTurnout:`);
  expect(formatRecap({ ...specialRecap, thrown_out: r.thrown_out }).text).toContain(line);
  for (const text of allStrings(Object.values(formatRecap(r)))) { expect(text).not.toMatch(OUTSIDER_BANNED); expect(text).not.toMatch(BANNED_WORDS); }
});
// club/charts.test.ts: the 'score trend and difficulty' row toEquals and the attendanceModel rows/labels gain thrown_out: '' / 'Thrown out'
it.each([
  ['attendanceModel', () => attendanceModel(clubAttendance.map((p, i) => ({ ...p, stats_excluded: i === 0 })))],
  ['scoreTrendModel', () => scoreTrendModel(clubTrends.events.map((e) => ({ ...e, stats_excluded: e.event_date === '2026-09-06' })))],
  ['difficultyModel', () => difficultyModel(clubTrends.events.map((e) => ({ ...e, stats_excluded: e.event_date === '2026-09-06' })))],
])('%s exports a thrown_out column', (_, build) => {
  const m = build();
  expect(m.columns.at(-1)).toEqual({ key: 'thrown_out', label: 'Thrown out', type: 'string' });
  expect(m.rows.filter((r) => r.thrown_out === 'yes')).toHaveLength(1);
});
it('draws a thrown-out Sunday hollow on the score trend and leaves its rolling value empty', () => {
  const events = clubTrends.events.map((e) => e.event_date === '2026-09-06'
    ? { ...e, stats_excluded: true, median_rolling8: null, top_score_rolling8: null } : e);
  const m = scoreTrendModel(events);
  const series = m.option.series as { name: string; data: unknown[] }[];
  expect(series.find((s) => s.name === 'Middle score')?.data[0]).toEqual({ value: ['2026-09-06', 36], symbol: 'emptyCircle', symbolSize: 8 });
  expect(m.rows[0]?.median_rolling8).toBeNull();
  expect(series.find((s) => s.name === 'Middle score (8-Sunday average)')?.data[0]).toEqual(['2026-09-06', null]);
});
// TurnoutChart.test.tsx
it('exports a thrown_out column', () => {
  const m = turnoutModel([...seasonEvents, { ...(seasonEvents[0] as EventSummary), event_date: '2026-09-20', stats_excluded: true }]);
  expect(m.columns.at(-1)?.key).toBe('thrown_out');
  expect(m.rows.find((r) => r.event_date === '2026-09-20')?.thrown_out).toBe('yes');
});
// weather/conditions.test.ts and charts.test.ts
it('leaves a Sunday with a station thrown out out of the means but counts it', () => {
  const e = WEATHER_EVENTS[0] as WeatherEvent;
  expect(summarize([{ ...e, median: 30, difficulty: 1 }, { ...e, median: 50, difficulty: 9, stats_excluded: true }])).toEqual({ events: 2, meanMedian: 30, meanDifficulty: 1 });
});
it('wind rose leaves out a Sunday with a station thrown out', () => {
  const e = { ...(WEATHER_EVENTS[0] as WeatherEvent), wind_dir_deg: 0, median: 30 };
  expect(windRoseChart([e, { ...e, median: 50, stats_excluded: true }]).data.rows[0]).toEqual({ sector: 'N', events: 1, median: 30 });
});
it('the difficulty fit keeps a thrown-out Sunday in its table, flagged, but not as a point', () => {
  const e = WEATHER_EVENTS[0] as WeatherEvent;
  const chart = difficultyFitChart([{ ...e, event_date: '2026-10-18', difficulty: 1.5 }, { ...e, event_date: '2026-10-25', difficulty: null, stats_excluded: true }], null, 'temp_f');
  expect(chart.data.columns.at(-1)).toEqual({ key: 'thrown_out', label: 'Thrown out', type: 'string' });
  expect(chart.data.rows.map((r) => [r.event_date, r.difficulty, r.thrown_out])).toEqual([['2026-10-18', 1.5, ''], ['2026-10-25', null, 'yes']]);
  expect((chart.option.series as { name: string; data: unknown[] }[])[0]?.data).toHaveLength(1);
});
// components/charts/explore.test.ts
it('adds a thrown_out column for the Sundays the server lists', () => {
  const t = toTabular({ columns: [{ key: 'event', label: 'Sunday', type: 'date' }, { key: 'value', label: 'Rounds', type: 'int' }],
    rows: [{ event: '2026-10-25', value: 20 }, { event: '2026-10-18', value: 22 }], n_rounds: 42, truncated: false, thrown_out_dates: ['2026-10-25'] });
  expect(t.columns.at(-1)).toEqual({ key: 'thrown_out', label: 'Thrown out', type: 'string' });
  expect(t.rows.map((r) => r.thrown_out)).toEqual(['yes', '']);
});
it('adds nothing when no Sunday is listed', () =>
  expect(toTabular({ columns: [], rows: [], n_rounds: 0, truncated: false, thrown_out_dates: [] }).columns).toEqual([]));
```

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/features/home src/features/insights/components/RecapCard.test.tsx src/features/share src/features/yir src/features/admin-recap src/features/club src/features/weather src/components/charts/explore.test.ts` — `thrownOut` missing; high score 50; no titles, no line, no column; the difficulty-fit table has one row; the rolling series has no null entry.

- [ ] **Step 3: Implement**

- MePanel: `lastResult` sets `thrownOut: best.stats_excluded` and `ratingMove: null` when excluded; `LastResultView` renders `{result.score}{result.thrownOut && <ThrownOutMark phrase={SUNDAY_THROWN_OUT} />}` before the rank.
- `pulseStats`: `tops` from `scored.filter((e) => !e.stats_excluded)`.
- `LatestEventBody`: the winner line, Median and Top score append `<ThrownOutMark phrase={thrownOutPhrase(event.thrown_out)} />` when excluded.
- `RecapCard`: `thrownOut = insight.how.some((b) => b.map((s) => s.v).join('') === THROWN_OUT_RECAP_LINE)`; when true, the headline `<p>` ends with `<ThrownOutMark phrase={SUNDAY_THROWN_OUT} />` and a `<p className="text-xs text-text-muted">{THROWN_OUT_RECAP_LINE}</p>` follows it. (The server text carries no `*`; the mark is added here.)
- `EventShareCard`, when excluded: `` ` · median ${event.median}*` ``, each score `` `${r.score}*` ``, and after the `<ol>` `<p className="text-xs text-text-muted">{`* ${thrownOutPhrase(event.thrown_out)}.`}</p>` (plain text, no sr-only spans).
- `OnThisDayCard`: `{describe(item)}{item.stats_excluded && <ThrownOutMark phrase={SUNDAY_THROWN_OUT} />}`.
- YIR pages: after the totals `</dl>`, render `excludedNote(totals.n_excluded)` in a muted `<p>` when not null.
- `formatRecap`: when `r.thrown_out.length > 0`, `intro.unshift(\`${thrownOutPhrase(r.thrown_out)}, so this week's scores aren't used in averages, PBs or station stats.\`)` in both the regular and special branches.
- Club/home charts: `attendanceModel`, `scoreTrendModel`, `difficultyModel`, `turnoutModel` append `THROWN_OUT_COLUMN` with `thrown_out: thrownOutCell(x.stats_excluded)`; `scoreTrendModel` keeps `r1` for the nullable rolling fields, wraps its option with `hollowSeries(option, ['Middle score', 'Top score'], rows.map((r) => r.thrown_out === 'yes'))` and uses `tooltip: { trigger: 'axis', formatter: thrownOutAxisTooltip(<excluded dates>) }`.
- Weather: `windRoseChart` skips `e.stats_excluded`; `summarize` keeps `events: scored.length` and computes both means over the non-excluded; `difficultyFitChart` adds `THROWN_OUT_COLUMN`, keeps every thrown-out event as a table row `{ event_date, x, difficulty: null, thrown_out: 'yes' }` (other rows `thrown_out: ''`, rows in date order) while the scatter and the model line use only the plotted points.
- `toTabular`: when `result.thrown_out_dates.length > 0` and an `event` column exists, append `THROWN_OUT_COLUMN` and `thrown_out: thrownOutCell(dates.has(String(row.event).slice(0, 10)))`.

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (pass); frontend gate.

- [ ] **Step 5: Commit**

`git add frontend/src/features/home frontend/src/features/insights/components frontend/src/features/share frontend/src/features/yir frontend/src/features/admin-recap frontend/src/features/club frontend/src/features/weather frontend/src/components/charts/explore.ts frontend/src/components/charts/explore.test.ts` — `feat(frontend): * on home, recap, share, On this day and YIR; club, weather and Explore skip thrown-out Sundays and flag them in CSV` (+ trailer).

---

### Task T7e: Profile charts and stats leave out thrown-out rounds

**Depends on:** T7a.

**Files:**
- Modify: `frontend/src/features/shooters/charts.ts:81-97` (`pbRoundIds`), `:117-136` (`trendLineByDate`), `:142-205` (`trendModel`), `:211-246` (`finishesModel`), `:257-300` (`distributionModel`), `:357-398` (`attendanceModel`), `:440-480` (`toughDaysModel`)
- Modify: `frontend/src/components/charts/builders/sundayCalendar.ts:6-16,33-75,119-130`
- Modify: `frontend/src/features/shooters/components/ProfileHero.tsx:76-80,104-108`
- Test: `frontend/src/features/shooters/charts.test.ts`, `frontend/src/components/charts/builders/sundayCalendar.test.ts`, `frontend/src/features/shooters/components/ProfileHero.test.tsx`

**Interfaces:**
- Consumes: T7a; `ShooterRound.stats_excluded`, `ShooterStats.n_excluded`, `window_stats.n_excluded`.
- Produces: `SundayCalendarOpts.thrownOut?: string`; the trend, finishes, calendar and tough-days models carry a `thrown_out` column.

- [ ] **Step 1: Write the failing tests**

```ts
// shooters/charts.test.ts — the 5th earlier round is the thrown-out 49: it counts toward the 5 (D8) but is not a best to beat
const gate = [
  round({ round_id: 11, event_date: '2026-03-01', score: 30 }), round({ round_id: 12, event_date: '2026-03-08', score: 31 }),
  round({ round_id: 13, event_date: '2026-03-15', score: 32 }), round({ round_id: 14, event_date: '2026-03-22', score: 33 }),
  round({ round_id: 15, event_date: '2026-03-29', score: 49, stats_excluded: true }), round({ round_id: 16, event_date: '2026-04-05', score: 34 }),
];
it('a thrown-out round counts toward the 5 earlier rounds but is never a PB or the best to beat', () => expect([...pbRoundIds(gate)]).toEqual([16]));
it('the trend lines skip a thrown-out Sunday', () => {
  expect([...trendLineByDate(gate, 'pb').values()]).toEqual([30, 31, 32, 33, null, 34]);
  expect(trendLineByDate(gate, 'so_far').get('2026-04-05')).toBe(31.5);
});
it('plots a thrown-out round hollow, stars its tooltip and exports it', () => {
  const m = trendModel(gate);
  expect(m.columns.at(-1)).toEqual({ key: 'thrown_out', label: 'Thrown out', type: 'string' });
  expect(m.rows.map((r) => r.thrown_out)).toEqual(['', '', '', '', 'yes', '']);
  const [score] = m.option.series as LineSeries[];
  expect(score?.data[4]).toEqual({ value: 49, symbol: 'emptyCircle', symbolSize: 8 });
  const tip = (m.option.tooltip as { formatter: (p: unknown) => string }).formatter;
  expect(tip([{ axisValue: '2026-03-29', axisValueLabel: '2026-03-29', marker: '', seriesName: 'Score', value: 49 }])).toBe('2026-03-29 *<br/>Score: 49');
});
it('a thrown-out Sunday still has a place on the finishes chart, drawn hollow', () => {
  const m = finishesModel([{ ...history[0], event_date: '2026-03-29', event_rank: 4, percentile: 0.8, stats_excluded: true }] as typeof history);
  expect(m.rows).toEqual([{ event_date: '2026-03-29', place: 4, thrown_out: 'yes' }]);
  expect((m.option.series as LineSeries[])[0]?.data[0]).toEqual({ value: 4, symbol: 'emptyCircle', symbolSize: 8 });
});
it('your score shares leave out thrown-out rounds', () => {
  const rows = distributionModel([round({ score: 30 }), round({ score: 30 }), round({ score: 49, stats_excluded: true })], []).rows;
  expect(rows.find((r) => r.score === 30)?.you_pct).toBe(100);
  expect(rows.find((r) => r.score === 49)?.you_pct).toBe(0);
});
it('the calendar keeps the official best score of a thrown-out Sunday and flags it', () =>
  expect(attendanceModel([round({ event_date: '2025-11-09', score: 43, stats_excluded: true })], [], 2025).rows).toEqual([{ date: '2025-11-09', state: 'shot', score: 43, thrown_out: 'yes' }]));
it('PbTable early counts still include thrown-out rounds (D8)', () => expect(roundsBefore(gate, '2026-04-05')).toBe(5));
it('tough days keep a thrown-out Sunday in the table, flagged, but not as a point', () => {
  const m = toughDaysModel([round({ event_date: '2026-03-22', adjusted: 2 }), round({ event_date: '2026-03-29', adjusted: null, stats_excluded: true })],
    [{ event: '2026-03-22', value: 1 }]);
  expect(m.rows).toEqual([{ event_date: '2026-03-22', difficulty: 1, adjusted: 2, thrown_out: '' },
                          { event_date: '2026-03-29', difficulty: null, adjusted: null, thrown_out: 'yes' }]);
  expect((m.option.series as { data: unknown[] }[])[0]?.data).toHaveLength(1);
});
// existing finishesModel rows gain thrown_out: ''; the 'lists Sunday, state and best score' labels become ['Sunday', 'State', 'Best score', 'Thrown out']; existing toughDaysModel rows gain thrown_out: ''

// builders/sundayCalendar.test.ts
it('stars a thrown-out shot cell and its tooltip', () => {
  const data = { columns: [{ key: 'd', label: 'Sunday', type: 'date' as const }, { key: 's', label: 'Best', type: 'int' as const },
    { key: 'st', label: 'State', type: 'string' as const }, { key: 't', label: 'Thrown out', type: 'string' as const }],
    rows: [{ d: '2025-11-09', s: 43, st: 'shot', t: 'yes' }] };
  const o = sundayCalendarOption(data, { date: 'd', value: 's', state: 'st', thrownOut: 't', year: 2025 });
  const shot = (o.series as { data: { thrownOut: boolean }[]; label: { formatter: (p: unknown) => string } }[])[0];
  expect(shot?.label.formatter({ value: [1, 10, 43], data: shot.data[0] })).toBe('43*');
  expect((o.tooltip as { formatter: (p: unknown) => string }).formatter({ seriesName: 'Shot', data: shot?.data[0] }))
    .toBe('Sunday 2025-11-09<br/>Best score: 43 *<br/>A station was thrown out this Sunday');
});

// ProfileHero.test.tsx
it('says how many rounds marked * are not in the averages', async () => {
  renderWithProviders(<ProfileHero shooter={{ ...hadleyDetail, stats: { ...hadleyDetail.stats, n_excluded: 2 } }} isPlaceholderData={false} />);
  expect(await screen.findByText('2 rounds marked * not in the average')).toBeInTheDocument();
});
it('shows a dash and the note when the only round in the window was thrown out', async () => {  // Review Focus 3
  const window_stats = { ...hadleyDetail.stats, n_rounds: 1, n_events: 1, n_excluded: 1, avg_score: null, median_score: null, best_score: null, avg_adjusted: null };
  renderWithProviders(<ProfileHero shooter={{ ...hadleyDetail, window_stats }} isPlaceholderData={false} />, { route: '/shooters/1?since=2026-10-25' });
  expect(await screen.findByText('1 round marked * not in the average')).toBeInTheDocument();
  expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1);
});
```

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/features/shooters src/components/charts/builders/sundayCalendar.test.ts` — `pbRoundIds` `[]`; the pb line reads 49; new columns and hints missing; tough-days drops the flagged row.

- [ ] **Step 3: Implement**

- `pbRoundIds`: an all-excluded day neither adds a PB nor updates `best`; `earlier += day.length` still.
- `trendLineByDate`: an excluded date sets `null` and pushes nothing into `bests`/`before`; the insight line series gets `connectNulls: true`.
- `trendModel`: rows gain `thrown_out`; `THROWN_OUT_COLUMN` last; score data `rows.map((r) => hollowPoint(r.score, r.thrown_out === 'yes'))`; tooltip `{ trigger: 'axis', formatter: thrownOutAxisTooltip(excludedDates) }`.
- `finishesModel`: rows gain `thrown_out`; `THROWN_OUT_COLUMN`; Place data `hollowPoint(place, excluded)`; same tooltip. `isFinish` unchanged (percentile still set).
- `distributionModel`: counts and denominator from `rounds.filter((r) => !r.stats_excluded)`.
- `attendanceModel`: a shot day is flagged when any round that day is excluded; rows gain `thrown_out` (special/missed `''`); `THROWN_OUT_COLUMN`; pass `thrownOut: 'thrown_out'`.
- `toughDaysModel`: a best round with `stats_excluded` becomes the row `{ event_date, difficulty: null, adjusted: null, thrown_out: 'yes' }`; other rows `thrown_out: ''`; `THROWN_OUT_COLUMN` last; `scatterOption` receives only the rows with both numbers.
- `sundayCalendarOption`: `CellItem.thrownOut` from `row[opts.thrownOut] === 'yes'`; the Shot label formatter returns `` `${score}*` `` when set; the Shot tooltip appends `` ` *<br/>${SUNDAY_THROWN_OUT}` `` after the best score.
- `ProfileHero`: the lifetime and window Average stats get `hint={excludedNote(n_excluded) ?? undefined}`; a null average already renders "—".

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (pass); frontend gate; `cd frontend && pnpm test --coverage` (lines and branches ≥ 90%).

- [ ] **Step 5: Commit**

`git add frontend/src/features/shooters frontend/src/components/charts/builders/sundayCalendar.ts frontend/src/components/charts/builders/sundayCalendar.test.ts` — `feat(shooters): thrown-out rounds plot hollow with *, skip PBs, lines and shares, export thrown_out` (+ trailer).

---

### Task T8a: Shared thrown-out copy, glossary term and every static explainer

**Depends on:** T7b–T7e (copy must match the shipped `*`, hollow points and greyed column). Sole creator of `thrownOutCopy.ts`.

**Files:**
- Create: `frontend/src/components/charts/thrownOutCopy.ts`, `frontend/src/components/charts/thrownOutCopy.test.ts`
- Modify: `frontend/src/features/glossary/terms.ts` (union + entry between `streak` and `time-window`), `glossary/triggers.ts`, `glossary/terms.test.ts`, `glossary/explainerLint.test.ts`
- Modify: `frontend/src/features/{events,home,stations,shooters,club,weather,yir,predictions,achievements,summary}/explainers.ts`, `frontend/src/features/summary/explainers.test.ts`
- Test: `thrownOutCopy.test.ts`, the glossary tests, every `features/*/explainers.test.ts` (word caps, banned words, pins)

**Interfaces:**
- Consumes: contract strings; glossary id `'thrown-out-station'`.
- Produces: `THROWN_OUT_ROUNDS`, `THROWN_OUT_STATION`, `THROWN_OUT_COUNTS`, `THROWN_OUT_HOLLOW`; `GlossaryTermId` `'thrown-out-station'`; `GLOSSARY_TRIGGERS['thrown-out-station'] = /\bthrown[- ]out\b/i`.

- [ ] **Step 1: Write the failing tests**

`thrownOutCopy.test.ts`:
```ts
import { describe, expect, it } from 'vitest';
import { explainers as achievements } from '../../features/achievements/explainers';
import { explainers as club } from '../../features/club/explainers';
import { eventExplainers } from '../../features/events/explainers';
import { homeExplainers } from '../../features/home/explainers';
import { explainers as predictions } from '../../features/predictions/explainers';
import { explainers as shooters } from '../../features/shooters/explainers';
import { explainers as stations } from '../../features/stations/explainers';
import { explainers as summary } from '../../features/summary/explainers';
import { explainers as weather } from '../../features/weather/explainers';
import { explainers as yir } from '../../features/yir/explainers';
import { THROWN_OUT_COUNTS, THROWN_OUT_HOLLOW, THROWN_OUT_ROUNDS, THROWN_OUT_STATION } from './thrownOutCopy';
import type { Explainer } from './types';

type Book = Record<string, Explainer>;
const text = (book: Book, key: string) => {
  const e = book[key];
  return [e?.what ?? '', ...(e?.read ?? []), ...(e?.computed ?? [])].join(' ');
};
const R = THROWN_OUT_ROUNDS, C = THROWN_OUT_COUNTS, H = THROWN_OUT_HOLLOW;
const CASES: [string, Book, string, string[]][] = [
  ['events', eventExplainers, R, ['difficulty', 'vsPrev']],
  ['events', eventExplainers, C, ['calendar', 'results', 'median', 'topScore']],
  ['home', homeExplainers, R, ['pulseHigh']],
  ['home', homeExplainers, C, ['latestMedian', 'latestTop', 'meLast', 'meOdometer']],
  ['stations', stations, THROWN_OUT_STATION, Object.keys(stations)],
  ['shooters', shooters, R, ['rating', 'trend', 'dist', 'learn', 'splits', 'tough-days', 'hero-average', 'hero-median', 'hero-best', 'win-average', 'win-best', 'odometer', 'floor-ceiling', 'bad-day', 'form', 'peak', 'rust', 'pbs']],
  ['shooters', shooters, C, ['finishes', 'cal', 'hero-rounds', 'win-rounds', 'odometer', 'wins', 'field-beaten']],
  ['shooters', shooters, H, ['trend', 'finishes']],
  ['club', club, R, ['dist', 'scores', 'diff', 'first-rounds']],
  ['club', club, C, ['stat-clays', 'parity']],
  ['club', club, H, ['scores']],
  ['weather', weather, R, ['wf', 'wr', 'wb', 'ws', 'conditions', 'profile-sensitivity']],
  ['yir', yir, R, ['glance', 'highlights', 'leaders', 'clubMonths', 'shooterYear', 'shooterBest', 'shooterMonths']],
  ['yir', yir, C, ['glance', 'leaders', 'shooterYear', 'onThisDay']],
  ['predictions', predictions, R, ['next-sunday']],
  ['achievements', achievements, R, ['trophy-progress', 'next-trophy']],
  ['achievements', achievements, C, ['trophy-progress']],
  ['summary', summary, R, ['summary-card']],
  ['summary', summary, C, ['summary-card']],
];

describe('thrown-out disclosure', () => {
  it('pins the shared lines', () => {
    expect(THROWN_OUT_ROUNDS).toBe('Sundays with a station thrown out (marked *) are left out.');
    expect(THROWN_OUT_STATION).toBe('A station thrown out on the day is left out.');
    expect(THROWN_OUT_COUNTS).toBe('Sundays with a station thrown out count here, marked *.');
    expect(THROWN_OUT_HOLLOW).toBe('A hollow point is a Sunday with a station thrown out.');
  });
  it.each(CASES)('%s: every listed explainer says the line and lists the term', (_f, book, line, keys) => {
    for (const key of keys) {
      expect(text(book, key), key).toContain(line);
      expect(book[key]?.terms, key).toContain('thrown-out-station');
    }
  });
  it('leaves turnout and count-only explainers alone', () => {
    for (const key of ['shooters', 'headCount', 'stations', 'weather', 'special', 'notables']) expect(text(eventExplainers, key), key).not.toMatch(/thrown out/);
    for (const key of ['pulse', 'pulseHeld', 'pulseTurnout', 'latestShooters']) expect(text(homeExplainers, key), key).not.toMatch(/thrown out/);
    expect(text(weather, 'wt')).not.toMatch(/thrown out/);
  });
  it('no longer defines an average as clays broken divided by rounds', () => {
    for (const [book, key] of [[yir, 'glance'], [yir, 'shooterYear'], [shooters, 'odometer'], [club, 'stat-clays']] as const)
      expect(text(book, key), key).not.toMatch(/clays broken divided by rounds/i);
    expect(yir.glance.computed).toContain(`Average score: the scores added up and divided by the rounds they come from. ${R}`);
    expect(yir.shooterYear.computed).toContain(`Average: the scores added up and divided by the rounds they come from. ${R}`);
    expect(shooters.odometer.computed).toContain(`Hit rate = broken ÷ thrown. ${R}`);
    expect(shooters.odometer.computed).toContain(`Clays thrown = rounds × 50. Clays broken = all your scores added up. ${C}`);
  });
  it('says the thrown-out heatmap column is greyed and credited', () =>
    expect(eventExplainers.stn.read).toContain('A station thrown out that day is greyed, marked * and reads "credited".'));
});
```
`glossary/terms.test.ts`: title `'has the 16 terms of the spec, sorted by id'`, `toHaveLength(16)`; "looks a term up by id" adds `expect(termById('thrown-out-station').term).toBe('Thrown-out station');`. `explainerLint.test.ts` "flags a trigger…" adds `expect(missingTerms({ what: 'Station 9 was thrown out.', computed: ['x'] })).toEqual(['thrown-out-station']);`. `summary/explainers.test.ts:8-14` pinned terms become `['special-shoot', 'personal-best', 'streak', 'round-types', 'time-window', 'thrown-out-station']`.

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/components/charts/thrownOutCopy.test.ts src/features/glossary src/features/summary/explainers.test.ts` — `Failed to resolve import "./thrownOutCopy"`, `expected [...] to have a length of 16 but got 15`, `missingTerms` returns `[]`, the summary terms differ.

- [ ] **Step 3: Implement**

- `thrownOutCopy.ts`: the four constants as pinned.
- Glossary entry `{ id: 'thrown-out-station', term: 'Thrown-out station', definition: 'A station the club threw out on the day, with every shooter usually given full credit on it. That Sunday’s results, standings, race points, Sundays shot and clays broken still count, marked *. Its scores stay out of averages, personal bests, records and trends, and the station stays out of station stats.' }`; trigger `/\bthrown[- ]out\b/i`.
- Every explainer below also gets `'thrown-out-station'` in `terms`. "Append X" = X goes last in `computed`. Replacements are exact old → new strings (`R`/`C`/`H` are the constants; the word caps stay at 95, never raised):
  - **events** — `calendar`: `'One square per Sunday, plus any shoot on another day.'` → `'One square per Sunday, plus shoots on other days.'`; `'The year is set with the arrows at the top. A custom time window opens on the year it ends in.'` → `'Arrows at the top set the year; a custom time window opens on the year it ends in.'`; append C. `stn`: `'Each cell is the targets broken at that station, straight from the station sheet.'` → `'Each cell is the targets broken at that station.'`; add read line `'A station thrown out that day is greyed, marked * and reads "credited".'` (no `THROWN_OUT_STATION` here: the column stays visible). `results`: `'"Vs middle score" of +5.0 means 5 targets above the middle score that day.'` → `'+5.0 vs middle score means 5 targets above it.'`; `'Vs middle score = the round\'s score minus the middle score (median) of every round that day. "—" on partial-results Sundays.'` → `'Vs middle score = score minus the median of every round that day; "—" on partial results or with a station thrown out.'`; append C. `median`, `topScore`: append C. `difficulty`: what `'How much harder or easier the course played than a typical Sunday of the past year, allowing for who showed up.'` → `'How much harder or easier the course played than a typical recent Sunday, allowing for who came.'`; `'+2.0 (harder) means shooters broke about 2 fewer targets than usual for them.'` → `'+2.0 (harder) means about 2 fewer targets than usual.'`; `'Negative is easier. 0.0 is typical. A low median with new shooters does not make a hard day.'` → `'Negative is easier; 0.0 is typical. New shooters alone do not make a hard day.'`; `'Small fields are pulled toward 0.0. "—" for partial results.'` → `'Small fields lean toward 0.0. "—" for partial results.'`; append R. `vsPrev`: append R.
  - **home** — `pulseHigh`: append R. `latestMedian`, `latestTop`: append C. `meLast`: what `'Your most recent Sunday: the date, your best score, where it placed and how your rating moved.'` → `'Your latest Sunday: the date, your best score, its place and how your rating moved.'`; `'Rating move is how much that Sunday changed your rating, our skill estimate out of 50.'` → `'Rating move is how much that Sunday changed your rating (skill estimate out of 50).'`; `'Rating move = rating after minus rating before, to 0.1. "—" means the Sunday had partial results, so ratings did not move.'` → `'Rating move = rating after minus rating before, to 0.1; "—" when ratings did not move.'`; append C. `meOdometer`: append C (its "special shoots included" pin stays).
  - **stations** — import `THROWN_OUT_STATION` and append it to all 9 entries (the `/only Sundays with a station sheet/` pin stays).
  - **shooters** — append R to `rating`, `tough-days`, `hero-median`, `hero-best`, `win-average`, `win-best`, `pbs`, `bad-day`, `form`, `peak`, `rust`; `learn` appends `` `${R} They still count in the Sunday numbering.` ``. Append C to `cal`, `hero-rounds`, `win-rounds`, `wins`, `field-beaten`. `trend`: add read H, append `` `Lines and PB pins: ${R}` ``. `finishes`: add read H, append C. `dist`: `'Every round counts, including second rounds and Sundays with incomplete results.'` → `` `Second rounds and Sundays with incomplete results count. ${R}` ``. `splits`: `'Average = your scores in the group divided by the rounds in it. Every round inside the time window counts; the round-type filter applies.'` → `` `Average = your scores in the group divided by the rounds in it. Rounds inside the time window count; the round-type filter applies. ${R}` ``. `hero-average`: `'All your scores added up, divided by your rounds.'` → `` `Your scores added up, divided by the rounds they come from. ${R}` ``. `odometer`: `'Clays thrown = rounds × 50. Clays broken = all your scores added up. Hit rate = broken ÷ thrown.'` → two lines `` `Clays thrown = rounds × 50. Clays broken = all your scores added up. ${C}` `` and `` `Hit rate = broken ÷ thrown. ${R}` ``. `floor-ceiling`: `'Every round counts. Needs at least 8 rounds. The round-type filter does not apply.'` → `` `Needs at least 8 rounds. The round-type filter does not apply. ${R}` ``. The pinned "Opens on the time window…" sentences stay.
  - **club** — append R to `dist`, `diff`, `first-rounds`. `scores`: add read H; `'Sundays with full results, up to today. Every round counts, second rounds and both round types included.'` → `'Sundays with full results, up to today. Second rounds and both round types count.'`; append R. `stat-clays`: append C. `parity`: append `` `Wins: ${C}` ``. `club-milestone`, `club-milestones`, `ctot` untouched (their pinned terms hold).
  - **weather** — append R to `wf`, `wr`, `wb`, `conditions`. `ws`: `'Every round counts and the round-type filter does not apply.'` → `'Second rounds count and the round-type filter does not apply.'`; append R. `profile-sensitivity`: `'Estimates are pulled toward zero when you have few rounds. Every round counts, all history is used and the round-type filter does not apply.'` → `'Estimates are pulled toward zero when you have few rounds. Second rounds count, all history is used and the round-type filter does not apply.'`; append R. `wt` untouched (the `'The round-type filter applies.'` and `'all history'` pins hold).
  - **yir** — `glance`: `'Clays broken: the sum of every round’s score. Average score: clays broken divided by rounds.'` → two lines `` `Clays broken: the sum of every round’s score. ${C}` `` and `` `Average score: the scores added up and divided by the rounds they come from. ${R}` ``. `shooterYear`: `'Sundays: different days with a round. Rounds: 50-target rounds, second rounds included. Average: clays broken divided by rounds.'` → `` `Sundays: different days with a round. Rounds: 50-target rounds, second rounds included. ${C}` `` and `` `Average: the scores added up and divided by the rounds they come from. ${R}` ``. `highlights`: insert `` `Top round, perfect 50s, hardest and easiest Sunday: ${R}` `` right after the line starting `'Hardest and easiest Sunday: of the Sundays with complete results'`. `leaders`: append `` `Best average: ${R}` `` and `` `Most Sundays, most wins and points: ${C}` ``. `clubMonths`: append `` `The average line: ${R}` ``. `shooterBest`: append `` `Best round and personal bests: ${R}` ``, terms `['personal-best', 'thrown-out-station']`. `shooterMonths`: append R. `onThisDay`: append C.
  - **predictions** `next-sunday`: append R. **achievements** `trophy-progress`: append `` `Best round: ${R}` `` and `` `Clays broken and Sundays attended: ${C}` ``; `next-trophy`: append `` `Best-round trophies: ${R}` ``.
  - **summary** `summary-card`: `'Rounds, average, best round and personal bests use regular rounds only, all round types.'` → `` `Rounds count every regular round, all round types. ${C}` `` and `` `Average, best round and personal bests use regular rounds only. ${R}` ``.

- [ ] **Step 4: Run to verify GREEN**

`cd frontend && pnpm vitest run src/components/charts/thrownOutCopy.test.ts src/features/glossary src/features/*/explainers.test.ts` (all pass, including the events/home `toBeLessThanOrEqual(95)` caps — counted totals: events `difficulty` 94, `calendar` 95, `stn` 95, `results` 95, home `meLast` 94, `meOdometer` 93); frontend gate.

- [ ] **Step 5: Commit**

`git add frontend/src/components/charts/thrownOutCopy.ts frontend/src/components/charts/thrownOutCopy.test.ts frontend/src/features/glossary frontend/src/features/{events,home,stations,shooters,club,weather,yir,predictions,achievements,summary}/explainers*.ts` — `feat(explainers): disclose thrown-out stations in every static explainer` (+ trailer).

---

### Task T8b: Run-time explainers per metric (leaderboards, race, Explorer, records)

**Depends on:** T8a.

**Files:**
- Modify: `frontend/src/components/charts/thrownOutCopy.ts` (add `thrownOutLineFor`), `thrownOutCopy.test.ts`
- Modify: `frontend/src/features/leaderboards/explainers.ts:119-158`; `frontend/src/features/race/explainers.ts:1-58`, `race/components/RaceView.tsx:164,191`; `frontend/src/features/explorer/explainers.ts:116-138`; `frontend/src/features/records/explainers.ts:17-55`, `records/components/RecordSections.tsx:335,355,375,399`; `frontend/src/features/glossary/explainerLint.test.ts:86-90`
- Test: `leaderboards/explainers.test.ts`, `race/explainers.test.ts:31,41,44,53,56,59`, `explorer/explainers.test.ts`, `records/explainers.test.ts`, `records/pages/RecordsPage.test.tsx`

**Interfaces:**
- Consumes: T8a constants and term.
- Produces: `thrownOutLineFor(metric: string): string`; `raceExplainer(key: 'race-bars' | 'race-bump', mode: RaceMode, metric: LeaderboardMetric): Explainer`.

- [ ] **Step 1: Write the failing tests**

```ts
// thrownOutCopy.test.ts
it('picks the line for a leaderboard or race measure', () => {
  for (const m of ['avg_score', 'avg_adjusted', 'best_score', 'rating_gain']) expect(thrownOutLineFor(m), m).toBe(THROWN_OUT_ROUNDS);
  for (const m of ['wins', 'podiums', 'events', 'rounds', 'season_points']) expect(thrownOutLineFor(m), m).toBe(THROWN_OUT_COUNTS);
});
// leaderboards/explainers.test.ts
it('says per measure whether thrown-out Sundays count, on every kind of board', () => {
  for (const metric of METRICS) for (const kind of KINDS) {
    const entry = boardExplainer(metric.value, kind);
    const line = ['avg_score', 'avg_adjusted', 'best_score', 'rating_gain'].includes(metric.value) ? THROWN_OUT_ROUNDS : THROWN_OUT_COUNTS;
    expect(entry.computed, `${metric.value} ${kind}`).toContain(line);
    expect(entry.computed).not.toContain(line === THROWN_OUT_ROUNDS ? THROWN_OUT_COUNTS : THROWN_OUT_ROUNDS);
    expect(entry.terms).toContain('thrown-out-station');
  }
  expect(explainers['lb-movers']?.computed).toContain(THROWN_OUT_ROUNDS);
});
// race/explainers.test.ts: existing calls gain a third arg 'season_points' (lines 31, 41, 44, 53, 56, 59), plus
it('discloses thrown-out Sundays for the chosen measure, just before the mode line', () => {
  const avg = raceExplainer('race-bars', 'rolling_12', 'avg_score');
  expect(avg.computed.at(-2)).toBe(THROWN_OUT_ROUNDS);
  expect(raceExplainer('race-bump', 'ytd', 'season_points').computed.at(-2)).toBe(THROWN_OUT_COUNTS);
  expect(avg.terms).toEqual(['thrown-out-station', 'time-window']);
});
// explorer/explainers.test.ts
const LINE: Record<Metric, string> = { score: THROWN_OUT_ROUNDS, adjusted: THROWN_OUT_ROUNDS, residual: THROWN_OUT_ROUNDS, rating: THROWN_OUT_ROUNDS,
  difficulty: THROWN_OUT_ROUNDS, hit_pct: THROWN_OUT_STATION, rounds: THROWN_OUT_COUNTS, shooters: THROWN_OUT_COUNTS, attendance: THROWN_OUT_COUNTS, wins: THROWN_OUT_COUNTS };
it.each(METRICS)('%s says how thrown-out stations are handled', (metric) => {
  for (const scope of ['windowed', 'all-time', undefined] as const) {
    const entry = explorerExplainer(metric, scope);
    expect(entry.computed).toContain(LINE[metric]);
    expect(entry.terms).toContain('thrown-out-station');
  }
});
// records/explainers.test.ts
it('says which records count thrown-out Sundays', () => {
  const range = { since: '2024-01-07', asOf: '2024-12-29' };
  expect(recordsExplainer('rec-events', range).computed).toContain(THROWN_OUT_COUNTS);
  expect(recordsExplainer('rec-streaks', range).computed).toContain(THROWN_OUT_COUNTS);
  const highest = recordsExplainer('rec-highest', range);
  expect(highest.computed).toContain(THROWN_OUT_ROUNDS);
  expect(highest.computed.join(' ')).not.toContain('Every round counts');
  for (const key of ['rec-events', 'rec-streaks', 'rec-highest']) expect(recordsExplainer(key, range).terms, key).toContain('thrown-out-station');
});
// records/pages/RecordsPage.test.tsx (inside describe 'RecordsPage')
it('says the score records leave thrown-out Sundays out', async () => {
  renderWithProviders(<RecordsPage />, { route: '/records' });
  await screen.findByRole('table', { name: 'Highest scores' });
  for (const name of ['Perfect 50s', 'Biggest day vs the field', 'Biggest jump from one Sunday to the next', 'Highest rating in these dates']) {
    expect(within(screen.getByRole('region', { name })).getByText(/Sundays with a station thrown out \(marked \*\) are left out\.$/), name).toBeVisible();
  }
});
```
`explainerLint.test.ts:86-90`: the race loop becomes `for (const metric of boardMetrics) built.push([\`${key} ${mode} ${metric}\`, raceExplainer(key, mode, metric)]);`.

- [ ] **Step 2: Run to verify RED**

`cd frontend && pnpm vitest run src/components/charts/thrownOutCopy.test.ts src/features/leaderboards src/features/race src/features/explorer/explainers.test.ts src/features/records src/features/glossary` — `thrownOutLineFor is not a function`; `expected [...] to include 'Sundays with a station thrown out (marked *) are left out.'`; race `.at(-2)` mismatch; records subtitles not found.

- [ ] **Step 3: Implement**

`thrownOutLineFor`: a `ReadonlySet` of the four score metrics; it takes `string` because `leaderboards/api.ts:14` and `race/api.ts:14` each define their own `LeaderboardMetric`. `boardExplainer`: `computed: [...base.computed, ...measure, thrownOutLineFor(metric), PERIOD_COMPUTED[kind], WINDOW_LINE]` and `mergeTerms(..., 'thrown-out-station')` (`computed[0]` stays pinned); `lb-movers` appends `THROWN_OUT_ROUNDS` and the term. `raceExplainer`: `computed: [...base.computed, thrownOutLineFor(metric), MODE_COMPUTED[mode]]`, `terms: mergeTerms(base.terms, 'time-window', 'thrown-out-station')`; RaceView passes `metric` at :164 and :191. `explorerExplainer`: a local `EXPLORE_THROWN_OUT: Record<Metric, string>` with the `LINE` mapping, inserted after `...copy.computed` and before the scope line, plus the term. **Amended after T5d:** the engine treats `score` + `sum` as a count, so `explorerExplainer` also takes the aggregation and uses `THROWN_OUT_COUNTS` for `score` with `sum` (add that case to the test). Records: `rec-events`/`rec-streaks` append `THROWN_OUT_COUNTS`; `rec-highest` `'Every round counts, second rounds on doubleheader Sundays too.'` → `'Second rounds on doubleheader Sundays count too.'` and appends `THROWN_OUT_ROUNDS`; the term on all three. `RecordSections.tsx`: append `` ` ${THROWN_OUT_ROUNDS}` `` at the end of the four subtitle strings (PerfectRounds after its existing ending, so `/newest first\. The latest 10 of 14\./` still matches).

- [ ] **Step 4: Run to verify GREEN**

Re-run Step 2 (pass); frontend gate (typecheck confirms the RaceView call sites).

- [ ] **Step 5: Commit**

`git add frontend/src/components/charts/thrownOutCopy.ts frontend/src/components/charts/thrownOutCopy.test.ts frontend/src/features/{leaderboards,race,explorer,records,glossary}` — `feat(explainers): pick the thrown-out line per metric on boards, race, Explorer and records` (+ trailer).

---

### Task T8c: E2E for a thrown-out station on a fixture Sunday

**Depends on:** T8b (and through it every task).

**Files:**
- Modify: `frontend/e2e/auth.setup.ts:42-82`
- Create: `frontend/e2e/thrown-out.spec.ts`

**Interfaces:**
- Consumes: `POST /api/admin/rules` `{rule_type: 'station_drop', payload, note}` → `{rule_id, job_id}`; `GET /api/events/{date}`; `GET /api/records`; `thrownOutPhrase`; `ThrownOutMark` titles; the banner `role="note"`; T8a/T8b constants.
- Produces: an active `station_drop` rule for 2026-09-06 Station 9 on every e2e stack. No fixture Sunday auto-detects (2026-09-06 has at most 6 of 24 perfect on any station), so the rule forces it and the phrase is `Station 9 was thrown out` (not credited).

- [ ] **Step 1: Write the failing test**

```ts
import { expect, test } from './fixtures';
import { THROWN_OUT_COUNTS, THROWN_OUT_ROUNDS } from '../src/components/charts/thrownOutCopy';
import { thrownOutPhrase, type ThrownOut } from '../src/features/events/thrownOut';

const DAY = '2026-09-06';
interface Detail { stats_excluded: boolean; thrown_out: ThrownOut[]; stations: { layout: { label: string; dropped: boolean }[] } | null; results: { shooter_id: number }[] }

test('the API marks the Sunday and its station', async ({ request }) => {
  const detail = (await (await request.get(`/api/events/${DAY}`)).json()) as Detail;
  expect(detail.stats_excluded).toBe(true);
  expect(detail.thrown_out).toEqual([{ station_label: '9', target_count: 7, credited: false }]);
  expect(detail.stations?.layout.find((s) => s.label === '9')?.dropped).toBe(true);
  const records = (await (await request.get(`/api/records?since=${DAY}&as_of=${DAY}`)).json()) as { highest_scores: unknown[]; totals: Record<string, number> };
  expect(records.highest_scores).toEqual([]);
  expect(records.totals.most_events).toBe(new Set(detail.results.map((r) => r.shooter_id)).size);
});

test('the Sunday page shows the banner, the * and the counts line', async ({ page, request }) => {
  const detail = (await (await request.get(`/api/events/${DAY}`)).json()) as Detail;
  const phrase = thrownOutPhrase(detail.thrown_out);
  expect(phrase).toBe('Station 9 was thrown out');
  await page.goto(`/events/${DAY}`);
  await expect(page.getByRole('note').filter({ hasText: phrase })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Results' }).getByTitle(phrase)).toHaveCount(detail.results.length);
  await page.getByRole('button', { name: 'About these results' }).click();
  await expect(page.getByText(THROWN_OUT_COUNTS)).toBeVisible();
});

test('a score board says thrown-out Sundays are left out, a points board says they count', async ({ page }) => {
  for (const [metric, line] of [['avg_score', THROWN_OUT_ROUNDS], ['season_points', THROWN_OUT_COUNTS]] as const) {
    await page.goto(`/leaderboards?metric=${metric}`);
    const chart = page.getByRole('region', { name: /^Top \d+ · / });
    await chart.getByRole('button', { name: 'About this chart' }).click();
    await expect(chart.getByText(line)).toBeVisible();
  }
});
```

- [ ] **Step 2: Run to verify RED**

Fresh stack: `VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh && IMAGE_TAG=local docker compose -f compose.yaml -f compose.test.yaml down -v && IMAGE_TAG=local docker compose -f compose.yaml -f compose.test.yaml up -d --build --wait`; then `cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/thrown-out.spec.ts --project=desktop` — `expect(received).toBe(true)  Received: false` on `stats_excluded` (no rule yet).

- [ ] **Step 3: Implement**

`auth.setup.ts`: `async function ensureStationDrop(request: APIRequestContext): Promise<void>` — `GET /api/admin/rules`; return if a row is `active && rule_type === 'station_drop' && payload.event_date === '2026-09-06'`; else POST `{ rule_type: 'station_drop', payload: { event_date: '2026-09-06', station_label: '9', dropped: true }, note: 'e2e: thrown-out station' }`, expect 200, `waitForJob(request, job_id)`. Call it right after `seedFixtureImports(request)` (L81).

- [ ] **Step 4: Run to verify GREEN**

Re-run the Step 2 Playwright command (3 passed plus setup); then the full suite on both projects `E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test` (including `admin-identity.spec.ts` with 9 rule types; no other spec may depend on 2026-09-06 counting in stats — if one does, read its expected values from the API instead of pinning them); frontend gate.

- [ ] **Step 5: Commit**

`git add frontend/e2e/auth.setup.ts frontend/e2e/thrown-out.spec.ts` — `test(e2e): a station_drop rule on 2026-09-06 shows the banner, the * and the explainer lines` (+ trailer).

---

### Task T8d: Backend goldens and the final full gate

**Depends on:** every other code task. No other task edits `backend/tests/golden/*` or `test_rebuild_live.py:EVENT_COLUMNS`.

**Files:**
- Modify: `backend/tests/integration/domain/test_rebuild_live.py:39-48` (`EVENT_COLUMNS`), `:158-160` (snapshot hash)
- Modify: `backend/tests/golden/rebuild_events.json`

**Interfaces:**
- Consumes: `Event.stats_excluded`.
- Produces: the fx-world snapshot with `stats_excluded`.

- [ ] **Step 1: Write the failing test**

Add `"stats_excluded",` as the last item of `EVENT_COLUMNS` in `test_rebuild_live.py` ("the snapshot holds them all").

- [ ] **Step 2: Run to verify RED**

`cd backend && uv run pytest tests/integration/domain/test_rebuild_live.py::test_fixtures_rebuild_matches_golden_events_snapshot -q` — `AssertionError` on `assert got == snap` (every event dict has an extra `'stats_excluded': False`).

- [ ] **Step 3: Implement**

- Regenerate deliberately: `cd backend && python3 -c "import json,pathlib;p=pathlib.Path('tests/golden/rebuild_events.json');d=json.loads(p.read_text());[e.__setitem__('stats_excluded',False) for e in d];p.write_text(json.dumps(d,separators=(',',':'),sort_keys=True)+'\n')"`.
- Hash: `python3 -c "import json,hashlib;d=json.load(open('tests/golden/rebuild_events.json'));print(hashlib.sha256(json.dumps(d,separators=(',',':'),sort_keys=True).encode()).hexdigest())"`; paste it in place of the hash at `:158-160`.
- Review the diff: all 360 events gain `"stats_excluded":false` and nothing else. Every other golden stays byte-identical; if one differs, stop and send the fix to the task that changed the behaviour — never regenerate it here.

- [ ] **Step 4: Run to verify GREEN, then the full gate**

- Goldens: `cd backend && uv run pytest tests/integration/domain/test_rebuild_live.py tests/integration/insights/test_golden_counts.py tests/unit/analytics/insights/test_anchor_export.py tests/integration/achievements/test_ach_scoring_golden.py tests/integration/achievements/test_ach_participation_golden.py tests/integration/api/test_records_api.py tests/integration/api/test_season_points_api.py tests/unit/ingest -q`; `git diff --stat -- backend/tests/golden` lists only `rebuild_events.json`.
- Backend: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch` (lines and branches ≥ 90%).
- Frontend: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage` (≥ 90%).
- Repo scripts: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests`.
- E2E on a fresh stack (T8c Step 2 commands), then `cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test`.
- `git diff --quiet origin/main -- ratchets/` exits 0.
- `git grep -n -iE "\b(drop|dropped|events?)\b" -- backend/src/sunday_clays/analytics/insights/templates.py` shows no new hit in the thrown-out lines; `uv run pytest tests -k lints -q` passes.
- `git status --porcelain | grep -E "openapi.json|schema.d.ts"` prints nothing staged.

- [ ] **Step 5: Commit**

`git add backend/tests/integration/domain/test_rebuild_live.py backend/tests/golden/rebuild_events.json` — `test(golden): record stats_excluded in the rebuild events snapshot` (+ trailer).

---

### Task T9: Ops — deploy, rebuild and verify the two real Sundays

**Depends on:** T8d, the PR merged to `main`.

**Files:**
- None in the repo. Snapshots go to the session scratchpad (`before/`, `after/` JSON files), never committed.

**Interfaces:**
- Consumes: CI multi-arch images, the deployer (GHCR → registry.thehalf.io mirror → `sundayclays` stack), `POST /api/admin/recompute`, `GET /api/admin/data-issues`, `POST /api/admin/rules`, the public routes.
- Produces: production with both thrown-out Sundays flagged, and a recorded before/after comparison.

Note: `POST /api/admin/recompute` only re-runs the pipeline (`jobs/handlers.py:44`); `rebuild_live` runs only in the `rebuild` job (`jobs/rebuild_handler.py:16`), which imports, rules and merges enqueue. Spec §8's "rebuild runs on deploy or by admin recompute" is therefore not true as written, so Step 3 enqueues a rebuild explicitly.

- [ ] **Step 1: Write the failing check (snapshot before deploy)**

With a viewer session against production, save to the scratchpad `before/`: `/api/leaderboards?period=ytd&metric=season_points&as_of=2026-10-25`, `/api/leaderboards/history?period=ytd&metric=season_points&top=500&from=2026-01-01&to=2026-10-25`, `/api/events/2026-10-25`, `/api/events/2026-01-11`, `/api/stations?since=2026-01-01&as_of=2026-10-25`, and an admin `/api/admin/data-issues`. The check script (`after == before` for the three standings/race files; `stats_excluded is True` and a `thrown_out` item on both Sundays; Station 11 on 10/25 and Station 10 on 1/11 absent from `by_event`; exactly two `station_thrown_out` issues) is written now.

- [ ] **Step 2: Run to verify RED**

Run the check against `before/` as both sides: the flag and issue assertions fail (`KeyError: 'stats_excluded'` on the old release, zero `station_thrown_out` issues). Paste it.

- [ ] **Step 3: Implement (deploy and rebuild)**

1. Merge the PR to `main`; wait for CI to build and push the amd64+arm64 images (if CI is billing-blocked, stop and tell the owner).
2. Wait for the deployer to mirror to registry.thehalf.io and update the `sundayclays` stack; confirm the backend logs show migration `0010` applied (expand-only; the old release kept running meanwhile).
3. Enqueue one rebuild without changing data, from the backend container: `docker exec <sundayclays backend task> python -c "from sunday_clays.db import get_session; from sunday_clays.jobs.queue import enqueue; s = next(get_session()); print(enqueue(s, 'rebuild', dedupe_key='rebuild')); s.commit()"`; then poll `/api/admin/jobs/{id}` until it is done.
4. Ask the owner whether 2026-01-11 Station 10 really was thrown out. If not, `POST /api/admin/rules` `{ "rule_type": "station_drop", "payload": { "event_date": "2026-01-11", "station_label": "10", "dropped": false }, "note": "not thrown out" }` (it enqueues its own rebuild; wait for it), and the check then expects one `station_thrown_out` issue and 1/11 unflagged.

- [ ] **Step 4: Run to verify GREEN**

Save the same URLs to `after/` and run the check: both Sundays (or 10/25 only, after the rule) show `stats_excluded`, the banner and `*` on their pages; the two stations are gone from station stats; spot check: the 10/25 top score is not a PB and is not in `/api/records` `highest_scores`; averages differ from `before/` only by leaving those Sundays out; the standings and race files are equal; `/api/admin/data-issues` lists two `station_thrown_out` info issues with the contract message. Also open `/events/2026-10-25`, `/stations/11`, a profile and the leaderboards on a phone width and a desktop.

- [ ] **Step 5: Commit**

Nothing to commit. Post the check output and the before/after diff summary to the owner; record the 1/11 decision.
