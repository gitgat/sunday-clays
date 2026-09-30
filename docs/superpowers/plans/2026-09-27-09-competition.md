# Plan 09 — Competition: Leaderboards, Season Points, Classes, Records and the Time Machine

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> One task = one branch/worktree = one PR (master §0 step 5); every implementer and reviewer runs on Opus.

**Goal:** Ship the competition layer of sundayclays.claysmasher.com — time-sliceable leaderboards for every C7
period × metric × filter, season championship points, A–D classes, the Records page and the leaderboard time machine
(bar-chart race + bump chart) — as tested backend analytics, typed viewer APIs and three frontend pages.

**Architecture:** Pure pandas functions over the Plan 06 C7 frames (`analytics/leaderboards.py`, `points.py`,
`records.py`, `leaderboard_history.py`) compute every board from the full-field `round_metrics` ranks, sliced by
`as_of` (each with a no-leak test) and memoized per `data_version` through `@cached_by_data_version`. Four
auto-discovered viewer routers (`leaderboards`, `classes`, `records`, `leaderboard_history`) expose them as Pydantic
models. Three registry-discovered React features (`leaderboards`, `records`, `race`) render them through Plan 07's
`ChartFrame` and chart builders, with every control persisted in the URL.

**Tech Stack:** Python 3.13 · pandas · FastAPI · Pydantic v2 · SQLAlchemy 2 · pytest (Plan 01/03/04 fixtures) ·
React 19 · TypeScript (strict) · TanStack Query v5 · React Router v7 · openapi-fetch · ECharts through the Plan 07
builders · Vitest + Testing Library + MSW · Playwright.

**Spec:** `/Users/bryanmoran/code/sunday-clays/docs/superpowers/specs/2026-09-27-sunday-clays-design.md` (§4
"Leaderboards & time machine", the Records page; §5 UX).

**Master:** `/Users/bryanmoran/code/sunday-clays/docs/superpowers/plans/2026-09-27-00-master.md` (Architecture
Contract C1–C12; this plan implements the "Plan 09 — Competition" task list).

## Global Constraints
- Python `3.13`; Node `22` LTS; Postgres `17`; package managers `uv` (backend) and `pnpm` (frontend); lockfiles committed.
- Dependency ownership: Plan 01 T1 (backend) and T2 (frontend) declare the complete Phase-1 dependency set; later tasks never change `[project].dependencies`/`[dependency-groups]` in `backend/pyproject.toml`, `dependencies`/`devDependencies` in `frontend/package.json`, `uv.lock` or `pnpm-lock.yaml` (tool-config sections and scripts may change); a truly new package first lands in a controller `chore(deps): add <pkg>` PR (branch `chore/deps-<pkg>`, manifest + lockfile only) that the task rebases onto; lockfile rebase conflicts are never hand-merged — backend `git checkout origin/main -- backend/uv.lock && (cd backend && uv lock)`, frontend `pnpm install` — then commit (documented in CONTRIBUTING.md, Plan 01 T5); `tools/trophy_art` has its own `pyproject.toml` and is exempt.
- Coverage floor **90% lines AND 90% branches**, backend and frontend measured separately; ratchet may only rise.
- Lint/type: `ruff check` + `ruff format --check` + `mypy --strict` (backend); `eslint` (typescript-eslint strict) + `tsc --noEmit` + `prettier --check` (frontend); warnings held at 0 (`eslint --max-warnings 0`; ruff has no warning level).
- TDD: every production change starts from a failing test (superpowers:test-driven-development).
- Every round is 50 targets; `score` is an int in `0..50`.
- Round type values exactly: `sporting`, `super_sporting`, `unknown`. Rule: any station that day with an odd `target_count` ⇒ `super_sporting`; station data with all even ⇒ `sporting`; no station data ⇒ `unknown`; admin override wins.
- Shooter status values exactly: `member`, `guest`, `deceased`.
- Event dates are SQL `date` (no tz). Weather rows are keyed by local `America/Los_Angeles` wall-clock timestamps. The event window is 10:00–12:00 local and uses the hourly stamps 10:00, 11:00 and 12:00; C7 gives the per-field rules. Stored timestamps are `timestamptz` UTC.
- Units: °F, mph and inches, stored and displayed. Pressure is the one exception: it is stored in hPa (`pressure_hpa`) and displayed in inHg (hPa × 0.02953, 2 dp) via `lib/format.ts:formatPressure` (Plan 07 T4).
- Theme (ClaySmasher defaultBrand): surface `#1A4D2E`, elevated `#2D5F3F`, primary `#9E5530`, primary-container `#C76D3F`, accent `#E8A77A`, text `#FEFBF6`, text-muted `#D4E7DD`, outline `#D1E7DA`, outline-variant `#4A7C59`, error `#FEE2E2`, error-container `#DC2626`; font Roboto; radii card 12px, button 20px, sheet 16px. Dark-only UI.
- Viewports: mobile `390×844` and desktop `1440×900` are both first-class; every page has an e2e check at both.
- Host `sundayclays.claysmasher.com`; compose services exactly `caddy`, `api`, `worker`, `db`, `backup`; configuration only via env vars and `*_FILE` Docker secrets; no host bind mounts in `compose.yaml`. In the Swarm, TLS terminates at the existing Traefik (`traefik_public` external network, labels `traefik.http.routers.sundayclays.rule=Host(\`sundayclays.claysmasher.com\`)`, `entrypoints=websecure`, `tls.certresolver=cloudflare`); Caddy listens on plain `:80` inside the stack.
- Trophy art comes from imagen at `https://imagen.thehalf.io` via the dev-only tool `tools/trophy_art/` (credentials from env `IMAGEN_URL`, `IMAGEN_USERNAME`, `IMAGEN_PASSWORD`, never committed); the running app and CI never call imagen.
- Auth: exactly two roles, `viewer` and `admin` (admin ⊇ viewer); passwords supplied as argon2 hashes via secrets.
- Do NOT add a Claude code-review GitHub workflow.
- Branch per task `task/<NN>-<T>-<slug>` (NN = sub-plan, T = task); controller-only branches `chore/ratchet-wave-<N>` (the only branches that may change `ratchets/`); Conventional Commits; commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Agents: every implementer, reviewer, fix-loop escalation, plan author, critic and verifier runs on Opus — never pass a cheaper `model` to Agent or workflow `agent()`, whatever a skill's model-selection guidance says.
- PR topology: each dependency chain is one GitHub stacked PR stack (`gh stack`, extension `github/gh-stack`, installed 2026-09-27 on gh 2.101.0); independent chains are separate stacks off `main`; `ci.yml`'s `pull_request` trigger has no `branches:` filter so mid-stack PRs (whose base is another stack branch) run full CI.
- Migrations must be expand/contract compatible with the previous release's code (`api` runs `alembic upgrade head` on start, before uvicorn).
- Test fixtures are the real workbooks at `backend/tests/fixtures/scores_2026-09-27.xlsx` and `backend/tests/fixtures/stations_2026-09-27.xlsx` (copies of the originals; originals stay at repo root until the user deletes them).
- Wave 3 carries for UI tasks: every data chart renders in `ChartFrame`/`ChartCard` (Plan 07 T6), and each page's chart test uses `expectChartControls` from `src/test/charts.ts`; in-app links use `useRoundTypeLink`/`useRoundTypeHref` (`lib/roundTypes.ts`). Fixture facts: 7,480 rounds, 332 shooters, 360 events (310 held); gauge Sub-Gauge 9, 28 Gauge 8. Known gap, parked at the Wave 3 final review: the fullscreen view does not show ChartCard's chips or the truncation note.

## Review Focus
1. **Ties and multi-round days** in ranks, leaderboards, season points and achievements → shared "min" rank, best-round rule (exactly one best round per (event_date, shooter_id), also across merged aliases), deterministic ordering (score desc, then name_key, then ordinal). Owner: Plan 06 Task 2 (`test_ties_share_min_rank`, `test_best_round_used_for_rank`, `test_merged_aliases_same_day_single_best_round`) and Plan 09 Task 2 (`test_tied_finish_shares_points`).
   In this plan: Task 2 `test_tied_finish_shares_points`; also Task 1 `test_ties_share_min_rank_and_order_by_name_key`
   and `test_wins_and_podiums_count_best_rounds_only`, Task 2 `test_season_points_count_only_best_round_per_event`.
2. **A filter that silently re-ranks the field.** Filtering by status, gauge or round type must only choose which
   rounds and shooters count; wins, podiums and season points keep the full-field `event_rank`, so a guest who won still
   costs the runner-up member the win. Tests: Task 1 `test_filtered_wins_use_full_field_rank`, Task 2
   `test_season_points_under_gauge_filter_keep_full_field_rank`.
3. **A shooter whose status changed** (guest → member, or an admin `set_status` override) must appear on exactly one
   status board, under the current status, with all their rounds. Tests: Task 1
   `test_status_filter_reads_shooter_status_not_row_status` (unit) and
   `test_status_filter_uses_current_status_and_set_status_override` (API, committed fixtures + a real rule + rebuild).
4. **Early-season and thin boards.** In January most shooters have one or two rounds; a fixed threshold would blank the
   board. The season threshold scales with events held, and the page says "Needs ≥N rounds · M qualify" or shows an
   empty state instead of a blank table. Tests: Task 1 `test_season_threshold_scales_early_year` (fixture 2024-01-28 →
   1), Task 5 Vitest `shows the minimum-rounds note` and `shows an empty state when nobody qualifies`.
5. **The time machine leaking the future.** A board or record as of D must be identical whether or not later Sundays
   exist; each history frame must equal the board as of that date; season points reset on Jan 1. Tests: Task 1
   `test_leaderboard_no_leak`, Task 2 `test_class_table_no_leak`, Task 3 `test_records_no_leak`, Task 4 `test_history_frames_match_leaderboard_as_of`,
   `test_history_points_reset_jan1`, `test_history_no_leak`.

## Decisions
Choices made here where the master is silent. Cross-plan auditors: D3, D11, D12, D17, D18 and D23 are the names and shapes
other plans consume or provide.

- **D1 Task map.** Task 1 = T1 (`task/09-1-leaderboards`), Task 2 = T2 (`task/09-2-season-points-classes`), Task 3 =
  T3 (`task/09-3-records`), Task 4 = T4 (`task/09-4-leaderboard-history`), Task 5 = T5a
  (`task/09-5a-leaderboards-page`), Task 6 = T5b (`task/09-5b-records-page`), Task 7 = T6 (`task/09-6-race`).
- **D2 No imports between unconnected tasks.** Task 3 runs beside Task 1, so records code reads the Plan 06 loaders
  directly and its unit tests carry their own small frame helper. Tasks 5, 6 and 7 have no dependency edge between them,
  so each feature owns its `api.ts`, label/format helpers and MSW mocks. Task 2 and Task 4 import Task 1's module;
  Task 4 relies on Task 2's `LeaderboardMetric.SEASON_POINTS`.
- **D3 Frame dates and columns.** Plan 09 normalizes every frame's `event_date` to `datetime.date`
  (`pd.to_datetime(col).dt.date`) when it builds its frames (`make_leaderboard_frames`, `compute_records`), so
  comparisons with `as_of: date` hold whatever dtype Plan 06's loaders return; synthetic test frames use
  `datetime.date`. `make_leaderboard_frames` also coerces `event_rank`/`adjusted` to float and `is_best_round` to
  plain bool (`<NA>` → `False`), because nullable `Int64`/`boolean` columns make `astype(int)` raise on `<NA>`
  (`test_make_frames_normalizes_loader_dtypes`). Columns read: `load_rounds` per C7 (incl. the derived `gauge`), `load_events` → `event_date`,
  `has_scores`, `results_complete`, `round_type`; `load_rating_history` → `shooter_id`, `event_date`, `mu`.
- **D4 Boards list every eligible shooter.** Rows = shooters with `n_rounds ≥ min_rounds_applied` after filters,
  including 0 values for `wins`/`podiums`; `n_eligible = len(rows)`; the API returns every row (at most one per
  shooter, no paging).
- **D5 Thresholds where C7 says "–".** `wins`, `podiums`, `events`, `rounds` and `season_points` (and `best_score`,
  whose C7 threshold is 1) report `min_rounds_applied = 1`: one counted round in the period puts a shooter on the
  board. `rating` reports 5 (C7 Activity). `most_improved` reports 5 for season/rolling_12 (its "≥10 rounds before the
  period" rule applies on top) and 15 for all_time. `avg_adjusted` counts only rounds with a non-null `adjusted`
  (held events) for both the mean and the threshold.
- **D6 Ranking and order.** Values are rounded to 2 dp, then min-ranked (ties share, the next rank skips). Rows sort by
  value desc, then the shooter's `sort_key` (smallest `name_key` among their rounds), then `shooter_id`. Every metric is
  "higher is better" (`most_improved` Δ may be negative).
- **D7 Rating-derived boards and filters.** `rating` = the rows of `classes.assign_classes(history, rounds, as_of)` with
  a non-null class (the single C7 "active at as_of" definition), value = mu; `period` is ignored (a rating is a
  point-in-time value). `rating` and `most_improved` are computed from all rounds and ratings (C7 "Rating … ignore all
  filters"): `round_type` and `gauge` never change them, while `status` still selects which shooters are listed (a
  shooter attribute that never splits a shooter, C7 Status). The page says so when those filters are set.
- **D8 `most_improved`.** Period start = Jan 1 (season) or `as_of − 363 d` (rolling_12). Start mu = the shooter's last
  `rating_history.mu` strictly before the start; for all_time, the mu at the event of the shooter's 10th round (rounds
  ordered by `event_date`, `ordinal`). End mu = the last mu ≤ `as_of`. `n_rounds` = rounds inside the period
  (all_time: rounds ≤ `as_of`).
- **D9 Season threshold E** counts `has_scores` events in [Jan 1, as_of] regardless of the round-type filter.
- **D10 Deceased shooters** are never excluded; `status=deceased` selects them like any other status. Tests: Task 1
  `test_deceased_shooters_stay_on_boards`, Task 2 `test_classes_include_deceased_shooters_while_active`, Task 3
  `test_deceased_shooters_keep_their_records`.
- **D11 `LeaderboardOut`** = `{period, metric, as_of, min_rounds_applied, n_eligible, event_dates, rows: [{rank,
  shooter_id, display_name, status, value, n_rounds}]}`. `event_dates` lists every has_scores event date ascending so
  the time-machine slider snaps to events without depending on Plan 06's `/api/events` item schema. `status` is the
  current `shooter_status` (nullable). `value` is a float for every metric.
- **D12 API defaults and shapes.** "Today" is always Plan 06 T1's `_filters.today_local(settings.timezone)`, called
  through the module (`_filters.resolve_as_of(as_of, tz)` for an optional `as_of`), never a route's own
  `datetime.now()`, so the default-date API tests monkeypatch `_filters.today_local` instead of racing the wall clock
  across local midnight. `GET /api/leaderboards`: `period=season`, `metric=avg_score`, `as_of` = today in
  `settings.timezone`; `gauge` is any string ≤ 40 chars (unknown values give empty boards); `status` ∈
  member/guest/deceased (else 422). `GET /api/leaderboards/history`: `period=season`, `metric=season_points`, `top=10`
  (1–50), `to` = today, `from` = Jan 1 of `to`'s year; `from > to` → 400 `invalid_range`; frame rows are exactly
  `{shooter_id, display_name, status, value, rank}` (C8) = the first `top` rows of the sorted board (ties at the cut
  follow D6). `GET /api/classes?as_of=` (default today) → `ClassesOut{as_of, n_active, rows: [{shooter_id,
  display_name, status, mu, klass}]}` sorted by mu desc, then shooter_id. `GET /api/records` has no `as_of` (C8) and
  uses today.
- **D13 Records.** Top 10 each for `highest_scores`, `biggest_adjusted`, `biggest_jumps`, `most_events`,
  `longest_streaks`, `highest_ratings`; `perfect_rounds` lists every 50. Round records sort by value desc, earliest
  date, `sort_key`, `ordinal` and min-rank on value. A "week-over-week jump" is the day's best round minus the
  shooter's best round at the immediately preceding has_scores event (among the filtered round types) when they shot
  both; only positive jumps count. Longest streak = `streaks()` over the filtered rounds and events. Highest rating =
  each shooter's peak published `mu` (earliest date of that peak); ratings ignore the round-type filter. Records include
  rounds at non-held score dates (C7: they count toward PBs).
- **D14 Route paths.** Each router is a bare `APIRouter()` and writes the full path (`@router.get("/api/leaderboards")`),
  exactly as Plan 06's routers do (`@router.get("/api/meta")`): Plan 01 T1's `create_app()` includes every discovered
  router with no prefix (`app.include_router(router)`, which Plan 04 T1 turns into
  `app.include_router(router, dependencies=role_dependencies(name))`, still with no prefix). Plan 01's `health.py` is
  not a model for this: it carries its own `APIRouter(prefix="/api")` with `@router.get("/health")`. Tasks 1 and 3 Step
  0 check `create_app()`'s `include_router` call, not the health decorator.
- **D15 Response models** are Pydantic models with `ConfigDict(from_attributes=True)`, built from the analytics
  modules' frozen dataclasses. `ShooterStatus = Literal["member", "guest", "deceased"]` lives in
  `analytics/leaderboards.py`.
- **D16 Backend test layout.** Unit tests of Tasks 1, 2 and 4 live in `backend/tests/unit/analytics/competition/` and
  share its `conftest.py` (`FrameBuilder`, fixtures `fb` and `make_builder`); Task 3's live in
  `backend/tests/unit/analytics/records/test_records_unit.py` (D2). API tests use `fx_viewer_client` and `fx_session`
  (committed fixture world, Plan 03 T6 / Plan 04 T1) and `viewer_client` (empty DB). Every test file basename is unique
  in the tree.
- **D17 Plan 07 names consumed by the UI tasks.** They started from the assumptions Plan 08 records in its Decision
  D22 and are reconciled here against Plan 07's written Decisions and Task 1; where the two differ, Plan 07 wins
  (the round-type hook, the `EmptyState` props and the race/bump builder input below). `renderWithProviders(ui, {
  route?, path?, queryClient?, role? })` (Plan 07 D9: fresh QueryClient with retries off, a `createMemoryRouter` at
  `route` with `ui` mounted at path `'*'`, the session query seeded as `'viewer'`; returns RTL's result plus `{ user,
  queryClient, router }`); `server` (MSW, `src/test/msw/server.ts`) and a `handlers` export per feature `mocks.ts`,
  merged by Plan 01 T2's `import.meta.glob<{ handlers: RequestHandler[] }>` in `src/test/msw/handlers.ts`; `api` +
  `unwrap<T>(request: Promise<FetchResult<T>>): Promise<T>` with `FetchResult<T> = { data?: T; error?: unknown;
  response: Response }`; `useUrlState<T>(key, codec: Codec<T>, defaultValue): [T, (next: T) => void]` with
  `Codec<T> = { parse: (raw: string) => T | null; serialize: (value: T) => string }` (Plan 07 D13; `null` → default;
  this plan's local `UrlCodec<T>`, whose `parse` never returns `null`, is assignable to it);
  `useRoundTypes(): [RoundTypeValue[], (next: RoundTypeValue[]) => void]` from
  `src/lib/roundTypes.ts` (Plan 07 D12: every `features/*/api.ts` hook reads `const [rt] = useRoundTypes()`; `[]` = no
  filter; `rt` is a comma list, Plan 07 D14), consumed as `const [roundTypes] = useRoundTypes()`; `useRoundTypeLink(path:
  string): To` (same file, Plan 07 T2), which every in-app link (to events, shooters, …) uses instead of a bare path
  string so `?rt=` survives navigation (C10; a hook, so list rows use a small link component that calls it) —
  `components/layout/RoundTypeFilter.tsx` exports only the `RoundTypeFilter` component; `NavItem` (`{ label, path,
  icon: LucideIcon, order, mobileTab?, adminOnly? }`); `Card({ title?, subtitle?, actions?, className?, children? })`
  (a `<section>` region named by its title when it has one), `Chip({ selected?, onClick?, children })` (a `<button
  aria-pressed>`), `EmptyState({ title, description?, action?, icon? })` (it renders the description `<p>` whenever
  `description !== undefined`, so callers pass `undefined`, never `null`, for "no description"), `Skeleton({
  className? })`; `ChartFrame` with exactly the C10 props plus Plan 07 D17's optional `controls`, `height`, `rowHref`,
  rendering a `Card` region named by `title` with buttons named `Table`, `CSV` and `Fullscreen`; `TabularData`,
  `TabularRow`; `barOption(data: TabularData, opts: BarOpts)` with `BarOpts = { x: string; y: string[]; seriesBy?:
  string; horizontal?: boolean; stack?: boolean; yName?: string; labels?: boolean }` (`horizontal` puts the categories
  on the y axis, first row at the top — Plan 07's documented mode for shooter names). `barOption` keeps one category
  per distinct label, so two shooters with the same display name (first-name-only guests are event-scoped shooters,
  spec §2) would collapse into one bar: per Plan 07 D18, charts label a display name held by more than one
  `shooter_id` as `<name> #<id>` (as `race.ts` does), which Tasks 5 and 6 do through their own `chartRows` helper. The
  race and bump builders take Plan 07 D16's typed input `LeaderboardFrame = { date: string; rows: { id: number |
  string; name: string; value: number; rank: number }[] }` (exported by `src/components/charts/types.ts`):
  `raceOption(frame: LeaderboardFrame, opts?: RaceOpts)` (one frame: a sorted horizontal bar chart; repeated names get
  ` #<id>`) and `bumpOption(frames: readonly LeaderboardFrame[], opts?: BumpOpts)` (inverted rank axis, one line per
  shooter); Task 7's `toLeaderboardFrame` maps each `LeaderboardHistoryOut` frame onto it (numeric ids). Each UI task's
  Step 0 greps these names and shapes and adapts only its own call sites.
- **D18 Frontend response types** come from `paths` through `JsonOf` (as Plan 08 D3); enum types derive from response
  fields (`LeaderboardOut['metric']`), so no generated schema component name is assumed.
- **D19 URL state and nav.** Leaderboards: `period`, `metric`, `as_of`, `gauge`, `status`; race: `period`, `metric`,
  `year`; records: only the global `rt`. The race's frame position is component state (writing the URL about once a
  second during playback would flood browser history). Nav: Leaderboards order 30 with `mobileTab` (C10), Records 120,
  Race 130; icons `Trophy`, `Medal`, `Flag` (lucide-react).
- **D20 Race page.** Frames = `GET /api/leaderboards/history?period&metric&top=10&from=<Y>-01-01&to=<Y>-12-31`; years
  offered = 2020 (the first scored season) … the current year; the page opens on the latest frame; Play from the last
  frame restarts at the first; one frame per 1.2 s; the bump chart spans every frame's top 10.
- **D21 Leaderboards page.** Class badges come from `GET /api/classes?as_of=` at the same `as_of` (classes ignore
  filters); the top-10 bar chart is the page's one data chart; standings rows link to `/shooters/{id}`; "Needs ≥N
  rounds · M qualify" shows when `min_rounds_applied > 1`. The time-machine slider always reports the event date it
  points at, the newest event included; only the "Latest" button clears `as_of` (= today). Between Jan 1 and the
  first Sunday of a year the season board as of today is empty, and the previous season's final event must still be
  reachable from the slider.
- **D22 Fixture facts used by golden tests** (computed from `backend/tests/fixtures/scores_2026-09-27.xlsx` with pandas,
  not guessed):
  - 311 scored events, 2020-01-05 … 2026-09-27; the only 2024 events up to 2024-01-28 are 01-07 and 01-28 (season
    threshold 1, 34 shooters); Sept 2026 scored events 09-06, 09-13, 09-27; the first 2026 event is 01-04.
  - All-time best round: four shooters with a 50, then 49. All-time wins top 3: 62, 45, 29. All-time `avg_score`: 88
    eligible (≥15 rounds), top 45.02. Rolling-12 `avg_score` at 2026-09-27: 49 eligible (≥8).
  - Super sporting events (2026-09-06, 2026-09-13): 32 shooters, 37 rounds, at most 2 per shooter, top score 48, no 50;
    5 shooters attended both.
  - `amberson edith`: 35 rounds, every one recorded as Guest.
  - `lennox stan`: 43 rounds on 43 dates, 2020-02-16 … 2024-12-08, every one recorded as Deceased (`lennox stanley` is a
    separate, unmerged 4-round shooter); all-time `avg_score` Σ1,755/43 → 40.81, rank 16 of 88 (neighbours 40.83 and
    40.65, so 2-dp rounding cannot tie); 2 rounds in (2023-12-10, 2024-12-08] (2024-05-26, 2024-12-08), so active at
    2024-12-08; none in (2025-09-28, 2026-09-27], so inactive at 2026-09-27.
  - Season points 2026 as of 2026-09-27: 191, 139, 129, 111, 111, 111 (the 7th row ranks 7); the 2025 season as of
    2025-12-28 is led on 254; the 2026-01-04 frame is led on 11.
  - Active at 2026-09-27: 83 shooters → classes A 13, B 29, C 29, D 12.
  - Perfect rounds: 2021-01-17, 2022-12-04, 2023-08-06, 2024-02-25, 2024-11-10, 2025-08-03; highest scores top 10 = six
    50s then four 49s; most events 285; longest held-event streak 56; biggest adjusted +18.0 on 2026-06-07; biggest
    jump 11 → 41 (2021-03-14 → 2021-03-21).
- **D23 Local e2e runs share the machine-wide lock of Plan 08 D24.** Plans 08, 09 and 10 UI tasks run concurrently in
  global Wave 4 and every Compose stack publishes host port 8080. Each Plan 09 UI task therefore builds its own image
  tag (`TAG=09-5a`, `09-5b`, `09-6`), runs Compose as project `sc-$TAG`, and holds the lock directory
  `/tmp/sunday-clays-e2e.lock` (`mkdir` is atomic; macOS has no `flock`) for exactly one stack lifetime; an `EXIT` trap
  runs `down -v` and removes the lock, so a failing RED run still releases it. Images are built before the lock is
  taken. A lock with no `docker ps --filter publish=8080` container behind it is left over from a crashed run: `rmdir`
  it.

## Waves
Waves: {T1, T3} → {T2, T5b} → {T4, T5a} → {T6}.

(Task 1 = T1, Task 2 = T2, Task 3 = T3, Task 4 = T4, Task 5 = T5a, Task 6 = T5b, Task 7 = T6. Globally all of Plan 09
runs in master Wave 4, after Plan 06 has merged; the UI tasks also need Plan 07.)

## File Structure
Backend (`backend/`):
- `src/sunday_clays/analytics/leaderboards.py` — leaderboard engine: periods, thresholds, metrics, filters, ranking,
  cached frame loader (Task 1); season-points wiring and the class table (Task 2).
- `src/sunday_clays/analytics/points.py` — season championship points per best round (Task 2).
- `src/sunday_clays/analytics/records.py` — club records (Task 3).
- `src/sunday_clays/analytics/leaderboard_history.py` — time-machine frames (Task 4).
- `src/sunday_clays/api/routes/leaderboards.py` — `GET /api/leaderboards` (Task 1).
- `src/sunday_clays/api/routes/classes.py` — `GET /api/classes` (Task 2).
- `src/sunday_clays/api/routes/records.py` — `GET /api/records` (Task 3).
- `src/sunday_clays/api/routes/leaderboard_history.py` — `GET /api/leaderboards/history` (Task 4).
- `tests/unit/analytics/competition/conftest.py` — `FrameBuilder` synthetic C7 frames + fixtures (Task 1).
- `tests/unit/analytics/competition/test_leaderboard_periods.py`, `test_leaderboard_metrics.py`,
  `test_leaderboard_ratings.py`, `test_leaderboard_no_leak.py` — engine unit tests (Task 1).
- `tests/unit/analytics/competition/test_points.py`, `test_class_table.py` — Task 2 unit tests.
- `tests/unit/analytics/competition/test_leaderboard_history.py` — Task 4 unit tests.
- `tests/unit/analytics/records/test_records_unit.py` — Task 3 unit tests.
- `tests/integration/api/test_leaderboards_api.py` (Task 1), `test_season_points_api.py`, `test_classes_api.py`
  (Task 2), `test_records_api.py` (Task 3), `test_leaderboard_history_api.py` (Task 4) — API tests.

Frontend (`frontend/`):
- `src/features/leaderboards/` (Task 5): `routes.tsx` (route + nav), `api.ts` (hooks/types), `labels.ts` (labels,
  formatting, URL codecs, slider snapping, `chartRows`), `components/TimeMachine.tsx`, `components/StandingsTable.tsx`,
  `pages/LeaderboardsPage.tsx`, `mocks.ts`, tests `labels.test.ts`, `components/TimeMachine.test.tsx`,
  `pages/LeaderboardsPage.test.tsx`, `routes.test.ts`; `e2e/leaderboards.spec.ts`.
- `src/features/records/` (Task 6): `routes.tsx`, `api.ts`, `format.ts` (formatters, `chartRows`), `components/RecordSections.tsx`,
  `pages/RecordsPage.tsx`, `mocks.ts`, tests `format.test.ts`, `pages/RecordsPage.test.tsx`, `routes.test.ts`;
  `e2e/records.spec.ts`.
- `src/features/race/` (Task 7): `routes.tsx`, `api.ts`, `labels.ts`, `transforms.ts` (history → TabularData for
  ChartFrame tables/CSV, and → Plan 07's `LeaderboardFrame` for the race/bump builders),
  `usePlayer.ts` (play/pause/scrub cursor), `components/RaceView.tsx`, `pages/RacePage.tsx`, `mocks.ts`, tests
  `labels.test.ts`, `transforms.test.ts`, `usePlayer.test.ts`, `components/RaceView.test.tsx`,
  `pages/RacePage.test.tsx`, `routes.test.ts`; `e2e/race.spec.ts`.

---

### Task 1: Leaderboard engine and GET /api/leaderboards (master Plan 09 T1)

**Files:**
- Create: `backend/src/sunday_clays/analytics/leaderboards.py`
- Create: `backend/src/sunday_clays/api/routes/leaderboards.py`
- Test: `backend/tests/unit/analytics/competition/conftest.py`
- Test: `backend/tests/unit/analytics/competition/test_leaderboard_periods.py`
- Test: `backend/tests/unit/analytics/competition/test_leaderboard_metrics.py`
- Test: `backend/tests/unit/analytics/competition/test_leaderboard_ratings.py`
- Test: `backend/tests/unit/analytics/competition/test_leaderboard_no_leak.py`
- Test: `backend/tests/integration/api/test_leaderboards_api.py`

**Interfaces:**
- Consumes (Plan 06 unless noted):
  - `sunday_clays.analytics.frames`: `load_rounds(session) -> pd.DataFrame` (C7 columns incl. `gauge`,
    `shooter_status`, `event_rank`, `is_best_round`, `adjusted`), `load_events(session) -> pd.DataFrame`,
    `load_rating_history(session) -> pd.DataFrame`, `apply_round_type_filter(df, round_types: Sequence[RoundType]) ->
    pd.DataFrame`.
  - `sunday_clays.analytics.cache.cached_by_data_version` (decorator over `f(session, *hashable_args)`).
  - `sunday_clays.analytics.classes.assign_classes(history, rounds, as_of) -> pd.DataFrame[shooter_id, mu, klass]`.
  - `sunday_clays.api.routes._filters` (imported as a module, D12): `round_type_param` (`Query(default=[],
    alias='round_type')`), `today_local(tz: str) -> date`, `resolve_as_of(as_of: date | None, tz: str) -> date`
    (tests monkeypatch `_filters.today_local`).
  - `sunday_clays.domain.round_type.RoundType` (Plan 03 T2); `sunday_clays.domain.rules.RuleType`, `create_rule`
    (Plan 03 T5); `sunday_clays.domain.rebuild.rebuild_live` (Plan 03 T4).
  - `sunday_clays.config.Settings`, `get_settings` (`timezone`); `sunday_clays.db.get_session` (Plan 01 T1).
  - pytest fixtures `fx_viewer_client`, `fx_session`, `viewer_client` (Plan 03 T6, Plan 04 T1); the autouse cache-clear
    fixture (Plan 06 T1).
- Produces (`sunday_clays.analytics.leaderboards`, used by Tasks 2 and 4):
  - `ShooterStatus = Literal["member", "guest", "deceased"]`
  - `class LeaderboardPeriod(StrEnum)`: `SEASON="season"`, `ROLLING_12="rolling_12"`, `ALL_TIME="all_time"`
  - `class LeaderboardMetric(StrEnum)`: `AVG_SCORE`, `AVG_ADJUSTED`, `BEST_SCORE`, `WINS`, `PODIUMS`, `EVENTS`,
    `ROUNDS`, `RATING`, `MOST_IMPROVED` (values = lower-case names; Task 2 adds `SEASON_POINTS="season_points"`)
  - `@dataclass(frozen=True) class LeaderboardFilters: round_types: tuple[RoundType, ...] = (); gauge: str | None =
    None; status: ShooterStatus | None = None`; `NO_FILTERS = LeaderboardFilters()`
  - `@dataclass(frozen=True) class LeaderboardFrames: rounds; events; history; shooters` (all `pd.DataFrame`;
    `shooters` = `shooter_id, display_name, status, sort_key`)
  - `@dataclass(frozen=True) class LeaderboardRow: rank: int; shooter_id: int; display_name: str; status: str | None;
    value: float; n_rounds: int`
  - `@dataclass(frozen=True) class Leaderboard: period; metric; as_of: date; min_rounds_applied: int; rows:
    pd.DataFrame` with `n_eligible -> int` and `records(top: int | None = None) -> list[LeaderboardRow]`
  - `make_leaderboard_frames(rounds, events, history) -> LeaderboardFrames`;
    `scored_event_dates(events) -> list[date]`; `period_bounds(period, as_of) -> tuple[date | None, date]`;
    `season_min_rounds(events, as_of) -> int`; `min_rounds_for(metric, period, events, as_of) -> int`
  - `ROUND_METRICS: dict[LeaderboardMetric, Callable[[pd.DataFrame], pd.DataFrame]]` (each returns `shooter_id,
    value, n_rounds`; Task 2 adds the `SEASON_POINTS` entry)
  - `leaderboard(frames, period, metric, as_of, filters=NO_FILTERS) -> Leaderboard`
  - `@cached_by_data_version load_leaderboard_frames(session) -> LeaderboardFrames` and
    `@cached_by_data_version leaderboard_for(session, period, metric, as_of, filters) -> Leaderboard`
  - `GET /api/leaderboards?period=&metric=&as_of=&round_type=&gauge=&status=` → `LeaderboardOut` (D11, D12)
  - Test support: `tests/unit/analytics/competition/conftest.py` fixtures `fb -> FrameBuilder` and
    `make_builder -> type[FrameBuilder]` (session-scoped).

**Branch:** `task/09-1-leaderboards`

**Depends on:** Plan 06 T1 (frames, cache, `_filters`, cache-clear fixture), Plan 06 T2 (`round_metrics` ranks), Plan
06 T4 (`classes.assign_classes`, `rating_history`); through them Plan 03 T4–T6 and Plan 04 T1 (rules, rebuild,
`fx_*`/`viewer_client` fixtures).

- [ ] **Step 0: Confirm the consumed names**

Run (from the worktree root):
```bash
cd backend
grep -nE "^def (load_rounds|load_events|load_rating_history|apply_round_type_filter)\(" src/sunday_clays/analytics/frames.py
grep -nE "^def cached_by_data_version\b" src/sunday_clays/analytics/cache.py
grep -nE "^def assign_classes\(" src/sunday_clays/analytics/classes.py
grep -nE "^(round_type_param|def (today_local|resolve_as_of)\()" src/sunday_clays/api/routes/_filters.py
grep -n "include_router" src/sunday_clays/api/app.py
grep -nE '@router\.get\("/api/' src/sunday_clays/api/routes/meta.py
grep -nE "def (fx_viewer_client|fx_session|viewer_client)\(" tests/conftest.py
grep -nE "^def (create_rule|rebuild_live)\(" src/sunday_clays/domain/rules.py src/sunday_clays/domain/rebuild.py
ls tests/unit/analytics
```
Expected: every grep prints a match (three in `_filters.py`; `cached_by_data_version` is declared with PEP 695
generics, `def cached_by_data_version[**P, R](`); `create_app()` calls `app.include_router(router, …)` with no
`prefix=` and Plan 06's `meta.py` declares the full path `@router.get("/api/meta")` (D14). Read the bodies of
`load_events` and `load_rating_history` and confirm the columns listed in D3. Only if `create_app()` passes
`prefix="/api"` to `include_router`, drop `/api` from this task's route decorator. If `tests/unit/analytics` contains an
`__init__.py`, also create an empty `__init__.py` in `tests/unit/analytics/competition/`. If any other consumed name or
signature differs, adapt only this task's call sites and list the mapping in your report.

- [ ] **Step 1: Write the test frame builder and the failing period/threshold tests**

Create `backend/tests/unit/analytics/competition/conftest.py`:
```python
"""Synthetic C7 frames for the Plan 09 competition unit tests (no DB)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import LeaderboardFrames, make_leaderboard_frames

ROUND_COLUMNS = [
    "round_id", "event_date", "shooter_id", "name_key", "display_name", "ordinal", "score",
    "gauge_class", "status", "shooter_status", "round_type", "field_median", "adjusted",
    "event_rank", "is_best_round", "percentile", "expected", "residual", "mu_before",
    "mu_after", "temp_f", "apparent_f", "precip_in", "wind_mph", "gust_mph", "wind_dir_deg",
    "cloud_pct", "condition", "gauge",
]  # fmt: skip
EVENT_COLUMNS = [
    "event_date", "round_type", "round_type_source", "head_count", "n_rounds", "n_shooters",
    "has_scores", "has_stations", "results_complete",
]  # fmt: skip
HISTORY_COLUMNS = ["shooter_id", "event_date", "mu", "var"]


@dataclass
class FrameBuilder:
    """Builds C7-shaped rounds/events/history frames.

    Ranks, best rounds, field medians and adjusted scores are derived per event the way
    C7 defines them (best round = highest score then ordinal; min-rank over best rounds;
    median over all rounds; NULL adjusted at non-held events) unless a round overrides them.
    """

    shooters: dict[int, tuple[str, str, str | None]] = field(default_factory=dict)
    round_rows: list[dict[str, Any]] = field(default_factory=list)
    event_rows: dict[date, dict[str, Any]] = field(default_factory=dict)
    history_rows: list[dict[str, Any]] = field(default_factory=list)

    def shooter(self, shooter_id: int, name: str, status: str | None = "member") -> FrameBuilder:
        key = " ".join(name.casefold().replace(",", " ").split())
        self.shooters[shooter_id] = (name, key, status)
        return self

    def event(
        self,
        event_date: date,
        *,
        round_type: str = "unknown",
        has_scores: bool = True,
        held: bool = True,
    ) -> FrameBuilder:
        self.event_rows[event_date] = {
            "event_date": event_date,
            "round_type": round_type,
            "round_type_source": "none" if round_type == "unknown" else "stations",
            "head_count": None,
            "n_rounds": 0,
            "n_shooters": 0,
            "has_scores": has_scores,
            "has_stations": round_type != "unknown",
            "results_complete": has_scores and held,
        }
        return self

    def round(
        self,
        event_date: date,
        shooter_id: int,
        score: int,
        *,
        ordinal: int = 1,
        row_status: str | None = None,
        gauge_class: str | None = None,
        **overrides: Any,
    ) -> FrameBuilder:
        if event_date not in self.event_rows:
            self.event(event_date)
        name, key, status = self.shooters[shooter_id]
        self.round_rows.append(
            {
                "event_date": event_date,
                "shooter_id": shooter_id,
                "name_key": key,
                "display_name": name,
                "ordinal": ordinal,
                "score": score,
                "gauge_class": gauge_class,
                "status": row_status if row_status is not None else status,
                "shooter_status": status,
                "overrides": overrides,
            }
        )
        return self

    def day(self, event_date: date, scores: dict[int, int], **event_kw: Any) -> FrameBuilder:
        self.event(event_date, **event_kw)
        for shooter_id, score in scores.items():
            self.round(event_date, shooter_id, score)
        return self

    def rating(
        self, shooter_id: int, event_date: date, mu: float, var: float = 4.0
    ) -> FrameBuilder:
        self.history_rows.append(
            {"shooter_id": shooter_id, "event_date": event_date, "mu": mu, "var": var}
        )
        return self

    def rounds(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for round_id, raw in enumerate(self.round_rows, start=1):
            row: dict[str, Any] = dict.fromkeys(ROUND_COLUMNS)
            row.update({k: v for k, v in raw.items() if k != "overrides"})
            row["round_id"] = round_id
            row["round_type"] = self.event_rows[raw["event_date"]]["round_type"]
            rows.append(row)
        self._derive_event_fields(rows)
        for row, raw in zip(rows, self.round_rows, strict=True):
            row.update(raw["overrides"])
        frame = pd.DataFrame(rows, columns=ROUND_COLUMNS)
        frame["event_rank"] = frame["event_rank"].astype(float)
        frame["adjusted"] = frame["adjusted"].astype(float)
        frame["gauge"] = frame["gauge_class"].fillna("unspecified")
        return frame

    def _derive_event_fields(self, rows: list[dict[str, Any]]) -> None:
        by_date: dict[date, list[dict[str, Any]]] = {}
        for row in rows:
            by_date.setdefault(row["event_date"], []).append(row)
        for day, day_rows in by_date.items():
            held = bool(self.event_rows[day]["results_complete"])
            median = float(statistics.median(r["score"] for r in day_rows))
            best: dict[int, dict[str, Any]] = {}
            for r in sorted(day_rows, key=lambda r: (-r["score"], r["name_key"], r["ordinal"])):
                best.setdefault(r["shooter_id"], r)
            best_scores = [r["score"] for r in best.values()]
            for r in day_rows:
                is_best = best[r["shooter_id"]] is r
                r["is_best_round"] = is_best
                r["event_rank"] = 1 + sum(s > r["score"] for s in best_scores) if is_best else None
                r["field_median"] = median if held else None
                r["adjusted"] = r["score"] - median if held else None

    def events(self) -> pd.DataFrame:
        return pd.DataFrame(
            [self.event_rows[d] for d in sorted(self.event_rows)], columns=EVENT_COLUMNS
        )

    def history(self) -> pd.DataFrame:
        return pd.DataFrame(self.history_rows, columns=HISTORY_COLUMNS)

    def frames(self) -> LeaderboardFrames:
        return make_leaderboard_frames(self.rounds(), self.events(), self.history())


@pytest.fixture
def fb() -> FrameBuilder:
    return FrameBuilder()


@pytest.fixture(scope="session")
def make_builder() -> type[FrameBuilder]:
    return FrameBuilder
```

Create `backend/tests/unit/analytics/competition/test_leaderboard_periods.py`:
```python
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import (
    LeaderboardMetric,
    LeaderboardPeriod,
    make_leaderboard_frames,
    min_rounds_for,
    period_bounds,
    scored_event_dates,
    season_min_rounds,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder


def test_rolling12_has_52_sundays() -> None:
    as_of = date(2026, 9, 27)
    start, end = period_bounds(LeaderboardPeriod.ROLLING_12, as_of)
    assert (start, end) == (date(2025, 9, 29), as_of)
    days = [date(2025, 9, 29) + timedelta(days=i) for i in range(364)]
    assert sum(1 for d in days if d.weekday() == 6) == 52


def test_season_starts_jan_1_and_all_time_has_no_start() -> None:
    assert period_bounds(LeaderboardPeriod.SEASON, date(2026, 3, 1)) == (
        date(2026, 1, 1),
        date(2026, 3, 1),
    )
    assert period_bounds(LeaderboardPeriod.ALL_TIME, date(2026, 3, 1)) == (None, date(2026, 3, 1))


@pytest.mark.parametrize(
    ("n_events", "expected"),
    [(0, 1), (1, 1), (2, 1), (3, 2), (5, 2), (6, 3), (8, 4), (10, 4), (11, 5), (13, 5), (40, 5)],
)
def test_season_threshold_formula(fb: FrameBuilder, n_events: int, expected: int) -> None:
    for week in range(n_events):
        fb.event(date(2026, 1, 4) + timedelta(weeks=week))
    assert season_min_rounds(fb.events(), date(2026, 12, 31)) == expected


def test_season_threshold_scales_early_year_unit(fb: FrameBuilder) -> None:
    fb.event(date(2023, 12, 31))  # previous season: ignored
    fb.event(date(2024, 1, 7))
    fb.event(date(2024, 1, 14), has_scores=False)  # attendance only: ignored
    fb.event(date(2024, 1, 28))
    fb.event(date(2024, 2, 4))  # after as_of: ignored
    fb.event(date(2024, 2, 11))
    assert season_min_rounds(fb.events(), date(2024, 1, 28)) == 1
    assert season_min_rounds(fb.events(), date(2024, 2, 11)) == 2


@pytest.mark.parametrize(
    ("metric", "period", "expected"),
    [
        (LeaderboardMetric.AVG_SCORE, LeaderboardPeriod.ROLLING_12, 8),
        (LeaderboardMetric.AVG_SCORE, LeaderboardPeriod.ALL_TIME, 15),
        (LeaderboardMetric.AVG_ADJUSTED, LeaderboardPeriod.ROLLING_12, 8),
        (LeaderboardMetric.AVG_ADJUSTED, LeaderboardPeriod.ALL_TIME, 15),
        (LeaderboardMetric.BEST_SCORE, LeaderboardPeriod.ALL_TIME, 1),
        (LeaderboardMetric.WINS, LeaderboardPeriod.SEASON, 1),
        (LeaderboardMetric.RATING, LeaderboardPeriod.SEASON, 5),
        (LeaderboardMetric.MOST_IMPROVED, LeaderboardPeriod.SEASON, 5),
        (LeaderboardMetric.MOST_IMPROVED, LeaderboardPeriod.ROLLING_12, 5),
        (LeaderboardMetric.MOST_IMPROVED, LeaderboardPeriod.ALL_TIME, 15),
    ],
)
def test_min_rounds_per_metric_and_period(
    fb: FrameBuilder, metric: LeaderboardMetric, period: LeaderboardPeriod, expected: int
) -> None:
    assert min_rounds_for(metric, period, fb.events(), date(2026, 6, 7)) == expected


def test_season_average_threshold_uses_season_formula(fb: FrameBuilder) -> None:
    for week in range(3):
        fb.event(date(2026, 1, 4) + timedelta(weeks=week))
    assert (
        min_rounds_for(
            LeaderboardMetric.AVG_SCORE, LeaderboardPeriod.SEASON, fb.events(), date(2026, 1, 18)
        )
        == 2
    )


def test_scored_event_dates_lists_has_scores_events_ascending(fb: FrameBuilder) -> None:
    fb.event(date(2026, 1, 18)).event(date(2026, 1, 4)).event(date(2026, 1, 11), has_scores=False)
    assert scored_event_dates(fb.events()) == [date(2026, 1, 4), date(2026, 1, 18)]


def test_make_frames_normalizes_loader_dtypes(fb: FrameBuilder) -> None:
    day = date(2026, 1, 4)
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").day(day, {1: 45, 2: 40})
    fb.round(day, 2, 30, ordinal=2)
    rounds = fb.rounds().convert_dtypes()  # nullable Int64/boolean/<NA>, as a DB loader may return
    rounds["event_date"] = pd.to_datetime(rounds["event_date"])  # datetime64, not date objects
    frames = make_leaderboard_frames(rounds, fb.events(), fb.history())
    assert frames.rounds["event_date"].tolist() == [day, day, day]
    assert frames.rounds["is_best_round"].tolist() == [True, True, False]
    assert frames.rounds["event_rank"].tolist()[:2] == [1.0, 2.0]
    assert math.isnan(frames.rounds["event_rank"].iloc[2])
    assert frames.rounds["adjusted"].tolist() == [5.0, 0.0, -10.0]
```

- [ ] **Step 2: Run the period tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_periods.py -v`
Expected: ERROR — `ImportError while loading conftest …` with
`ModuleNotFoundError: No module named 'sunday_clays.analytics.leaderboards'`.

- [ ] **Step 3: Create the leaderboards module with periods, thresholds and frames**

Create `backend/src/sunday_clays/analytics/leaderboards.py` (the imports used by Steps 7, 11 and 15 are included now;
`ruff` runs in Step 17):
```python
"""Leaderboards (C7): period x metric x filters, time-sliced by ``as_of``.

Pure over the C7 frames; ``load_leaderboard_frames``/``leaderboard_for`` are the only
DB-facing functions and are memoized by ``data_version``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Literal

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.classes import assign_classes
from sunday_clays.analytics.frames import (
    apply_round_type_filter,
    load_events,
    load_rating_history,
    load_rounds,
)
from sunday_clays.domain.round_type import RoundType

ShooterStatus = Literal["member", "guest", "deceased"]

ROLLING_DAYS = 364
ACTIVE_MIN_ROUNDS = 5
IMPROVED_MIN_BEFORE = 10
IMPROVED_MIN_INSIDE = 5
IMPROVED_ALL_TIME_MIN = 15
ROW_COLUMNS = ["rank", "shooter_id", "display_name", "status", "value", "n_rounds"]


class LeaderboardPeriod(StrEnum):
    SEASON = "season"
    ROLLING_12 = "rolling_12"
    ALL_TIME = "all_time"


class LeaderboardMetric(StrEnum):
    AVG_SCORE = "avg_score"
    AVG_ADJUSTED = "avg_adjusted"
    BEST_SCORE = "best_score"
    WINS = "wins"
    PODIUMS = "podiums"
    EVENTS = "events"
    ROUNDS = "rounds"
    RATING = "rating"
    MOST_IMPROVED = "most_improved"


@dataclass(frozen=True)
class LeaderboardFrames:
    rounds: pd.DataFrame  # C7 load_rounds columns, event_date as datetime.date
    events: pd.DataFrame  # C7 load_events columns, event_date as datetime.date
    history: pd.DataFrame  # C7 load_rating_history columns, event_date as datetime.date
    shooters: pd.DataFrame  # shooter_id, display_name, status, sort_key


def _with_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["event_date"] = pd.to_datetime(out["event_date"]).dt.date
    return out


def _normalized_rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    """Dates as ``datetime.date``; nullable loader dtypes (Int64/boolean/<NA>) as float/bool."""
    out = _with_dates(rounds)
    out["event_rank"] = pd.to_numeric(out["event_rank"], errors="coerce").astype(float)
    out["adjusted"] = pd.to_numeric(out["adjusted"], errors="coerce").astype(float)
    out["is_best_round"] = out["is_best_round"].eq(True).fillna(False).astype(bool)
    return out


def make_leaderboard_frames(
    rounds: pd.DataFrame, events: pd.DataFrame, history: pd.DataFrame
) -> LeaderboardFrames:
    dated = _normalized_rounds(rounds)
    shooters = dated.groupby("shooter_id", as_index=False).agg(
        display_name=("display_name", "first"),
        status=("shooter_status", "first"),
        sort_key=("name_key", "min"),
    )
    return LeaderboardFrames(
        rounds=dated, events=_with_dates(events), history=_with_dates(history), shooters=shooters
    )


def scored_event_dates(events: pd.DataFrame) -> list[date]:
    return sorted(set(events.loc[events["has_scores"].eq(True), "event_date"]))


def period_bounds(period: LeaderboardPeriod, as_of: date) -> tuple[date | None, date]:
    if period is LeaderboardPeriod.SEASON:
        return date(as_of.year, 1, 1), as_of
    if period is LeaderboardPeriod.ROLLING_12:
        return as_of - timedelta(days=ROLLING_DAYS - 1), as_of
    return None, as_of


def season_min_rounds(events: pd.DataFrame, as_of: date) -> int:
    start = date(as_of.year, 1, 1)
    in_season = events[
        events["has_scores"].eq(True)
        & (events["event_date"] >= start)
        & (events["event_date"] <= as_of)
    ]
    n_events = int(in_season["event_date"].nunique())
    return min(5, max(1, math.ceil(0.4 * n_events)))


_AVERAGE_MIN_ROUNDS = {LeaderboardPeriod.ROLLING_12: 8, LeaderboardPeriod.ALL_TIME: 15}


def min_rounds_for(
    metric: LeaderboardMetric, period: LeaderboardPeriod, events: pd.DataFrame, as_of: date
) -> int:
    if metric in (LeaderboardMetric.AVG_SCORE, LeaderboardMetric.AVG_ADJUSTED):
        if period is LeaderboardPeriod.SEASON:
            return season_min_rounds(events, as_of)
        return _AVERAGE_MIN_ROUNDS[period]
    if metric is LeaderboardMetric.RATING:
        return ACTIVE_MIN_ROUNDS
    if metric is LeaderboardMetric.MOST_IMPROVED:
        if period is LeaderboardPeriod.ALL_TIME:
            return IMPROVED_ALL_TIME_MIN
        return IMPROVED_MIN_INSIDE
    return 1
```

- [ ] **Step 4: Run the period tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_periods.py -v`
Expected: PASS — 27 passed.

- [ ] **Step 5: Write the failing round-metric tests**

Create `backend/tests/unit/analytics/competition/test_leaderboard_metrics.py`:
```python
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sunday_clays.analytics.leaderboards import (
    Leaderboard,
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    LeaderboardRow,
    leaderboard,
)
from sunday_clays.domain.round_type import RoundType

if TYPE_CHECKING:
    from conftest import FrameBuilder

D1, D2, D3 = date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)
ALL = LeaderboardPeriod.ALL_TIME
SEASON = LeaderboardPeriod.SEASON


def values(board: Leaderboard) -> dict[int, float]:
    return dict(zip(board.rows["shooter_id"], board.rows["value"], strict=True))


def test_avg_score_counts_every_round_of_multi_round_days(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D1, 1, 30, ordinal=2).round(D2, 1, 35)
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.AVG_SCORE, D2)
    assert board.records() == [
        LeaderboardRow(
            rank=1, shooter_id=1, display_name="Ace, Amy", status="member", value=35.0, n_rounds=3
        )
    ]


def test_avg_adjusted_skips_non_held_events(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 40, 2: 30})  # median 35 -> +5 / -5
    fb.day(D2, {1: 20}, held=False)  # adjusted NULL at a non-held event
    frames = fb.frames()
    adjusted = leaderboard(frames, SEASON, LeaderboardMetric.AVG_ADJUSTED, D2)
    assert values(adjusted) == {1: 5.0, 2: -5.0}
    assert adjusted.rows["n_rounds"].tolist() == [1, 1]
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.AVG_SCORE, D2))[1] == 30.0


def test_best_score_is_max_single_round(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").day(D1, {1: 41}).day(D2, {1: 47}).day(D3, {1: 39})
    assert values(leaderboard(fb.frames(), ALL, LeaderboardMetric.BEST_SCORE, D3)) == {1: 47.0}


def test_wins_and_podiums_count_best_rounds_only(fb: FrameBuilder) -> None:
    for sid, name in [(1, "Ace, Amy"), (2, "Bee, Bob"), (3, "Cy, Cal"), (4, "Dee, Dot")]:
        fb.shooter(sid, name)
    fb.day(D1, {1: 45, 2: 40, 3: 35, 4: 20}).round(D1, 1, 44, ordinal=2)
    frames = fb.frames()
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.WINS, D1)) == {
        1: 1.0, 2: 0.0, 3: 0.0, 4: 0.0,
    }  # fmt: skip
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.PODIUMS, D1)) == {
        1: 1.0, 2: 1.0, 3: 1.0, 4: 0.0,
    }  # fmt: skip


def test_events_counts_distinct_dates_and_rounds_counts_rows(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D1, 1, 38, ordinal=2).round(D2, 1, 35)
    frames = fb.frames()
    assert values(leaderboard(frames, ALL, LeaderboardMetric.EVENTS, D2)) == {1: 2.0}
    assert values(leaderboard(frames, ALL, LeaderboardMetric.ROUNDS, D2)) == {1: 3.0}


def test_ties_share_min_rank_and_order_by_name_key(fb: FrameBuilder) -> None:
    fb.shooter(1, "Zed, Al").shooter(2, "Abe, Bo").shooter(3, "Cy, Di")
    fb.day(D1, {1: 45, 2: 45, 3: 40})
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.BEST_SCORE, D1)
    assert board.rows[["shooter_id", "rank"]].values.tolist() == [[2, 1], [1, 1], [3, 3]]


def test_threshold_drops_shooters_below_min_rounds(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    for week in range(8):
        fb.round(date(2026, 1, 4) + timedelta(weeks=week), 1, 40)
    for week in range(7):
        fb.round(date(2026, 1, 4) + timedelta(weeks=week), 2, 45)
    board = leaderboard(
        fb.frames(), LeaderboardPeriod.ROLLING_12, LeaderboardMetric.AVG_SCORE, date(2026, 3, 1)
    )
    assert (board.min_rounds_applied, board.n_eligible) == (8, 1)
    assert values(board) == {1: 40.0}


def test_filtered_wins_use_full_field_rank(fb: FrameBuilder) -> None:
    fb.shooter(1, "Guest, Gus", status="guest").shooter(2, "Member, Meg", status="member")
    fb.day(D1, {1: 45, 2: 44})
    frames = fb.frames()
    members = leaderboard(
        frames, SEASON, LeaderboardMetric.WINS, D1, LeaderboardFilters(status="member")
    )
    assert values(members) == {2: 0.0}
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.WINS, D1)) == {1: 1.0, 2: 0.0}


def test_status_filter_reads_shooter_status_not_row_status(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy", status="member").shooter(2, "Bee, Bob", status="guest")
    fb.round(D1, 1, 40, row_status="guest").round(D1, 2, 30)
    frames = fb.frames()
    member = LeaderboardFilters(status="member")
    guest = LeaderboardFilters(status="guest")
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.ROUNDS, D1, member)) == {1: 1.0}
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.ROUNDS, D1, guest)) == {2: 1.0}


def test_gauge_filter_matches_unspecified_for_null_gauge(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.round(D1, 1, 40).round(D2, 1, 30, gauge_class="Sub-Gauge")
    frames = fb.frames()
    unspecified = LeaderboardFilters(gauge="unspecified")
    sub = LeaderboardFilters(gauge="Sub-Gauge")
    assert values(leaderboard(frames, ALL, LeaderboardMetric.AVG_SCORE, D2, unspecified)) == {}
    assert values(leaderboard(frames, ALL, LeaderboardMetric.BEST_SCORE, D2, unspecified)) == {
        1: 40.0
    }
    assert values(leaderboard(frames, ALL, LeaderboardMetric.BEST_SCORE, D2, sub)) == {1: 30.0}


def test_round_type_filter_counts_only_matching_events(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    fb.day(D1, {1: 40}, round_type="sporting").day(D2, {1: 30}, round_type="super_sporting")
    only_sporting = LeaderboardFilters(round_types=(RoundType.SPORTING,))
    board = leaderboard(fb.frames(), ALL, LeaderboardMetric.ROUNDS, D2, only_sporting)
    assert values(board) == {1: 1.0}


def test_values_are_rounded_to_two_decimals(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").day(D1, {1: 40}).day(D2, {1: 41}).day(D3, {1: 41})
    assert values(leaderboard(fb.frames(), SEASON, LeaderboardMetric.AVG_SCORE, D3)) == {1: 40.67}


def test_rolling12_window_counts_52_weekly_rounds(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy")
    first = date(2025, 9, 28)  # exactly 364 days before as_of: outside (as_of - 364d, as_of]
    for week in range(53):
        fb.round(first + timedelta(weeks=week), 1, 40)
    board = leaderboard(
        fb.frames(), LeaderboardPeriod.ROLLING_12, LeaderboardMetric.ROUNDS, date(2026, 9, 27)
    )
    assert board.rows["value"].tolist() == [52.0]
```

- [ ] **Step 6: Run the round-metric tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_metrics.py -v`
Expected: ERROR during collection — `ImportError: cannot import name 'Leaderboard' from
'sunday_clays.analytics.leaderboards'`.

- [ ] **Step 7: Add filters, round metrics, ranking and `leaderboard`**

Append to `backend/src/sunday_clays/analytics/leaderboards.py`:
```python
@dataclass(frozen=True)
class LeaderboardFilters:
    round_types: tuple[RoundType, ...] = ()
    gauge: str | None = None
    status: ShooterStatus | None = None


NO_FILTERS = LeaderboardFilters()


@dataclass(frozen=True)
class LeaderboardRow:
    rank: int
    shooter_id: int
    display_name: str
    status: str | None
    value: float
    n_rounds: int


@dataclass(frozen=True)
class Leaderboard:
    period: LeaderboardPeriod
    metric: LeaderboardMetric
    as_of: date
    min_rounds_applied: int
    rows: pd.DataFrame  # ROW_COLUMNS, best first

    @property
    def n_eligible(self) -> int:
        return len(self.rows)

    def records(self, top: int | None = None) -> list[LeaderboardRow]:
        frame = self.rows if top is None else self.rows.head(top)
        return [
            LeaderboardRow(
                rank=int(rec["rank"]),
                shooter_id=int(rec["shooter_id"]),
                display_name=str(rec["display_name"]),
                status=None if pd.isna(rec["status"]) else str(rec["status"]),
                value=float(rec["value"]),
                n_rounds=int(rec["n_rounds"]),
            )
            for rec in frame.to_dict("records")
        ]


def _window(df: pd.DataFrame, start: date | None, end: date) -> pd.DataFrame:
    mask = df["event_date"] <= end
    if start is not None:
        mask &= df["event_date"] >= start
    return df[mask]


def _round_filters(rounds: pd.DataFrame, filters: LeaderboardFilters) -> pd.DataFrame:
    out = apply_round_type_filter(rounds, filters.round_types)
    if filters.gauge is not None:
        out = out[out["gauge"] == filters.gauge]
    return out


def _agg(rounds: pd.DataFrame, column: str, how: str) -> pd.DataFrame:
    return rounds.groupby("shooter_id", as_index=False).agg(
        value=(column, how), n_rounds=(column, "size")
    )


def _avg_score(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "score", "mean")


def _avg_adjusted(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds[rounds["adjusted"].notna()], "adjusted", "mean")


def _best_score(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "score", "max")


def _events(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "event_date", "nunique")


def _rounds(rounds: pd.DataFrame) -> pd.DataFrame:
    return _agg(rounds, "score", "size")


def _finishes(rounds: pd.DataFrame, max_rank: int) -> pd.DataFrame:
    hit = rounds["is_best_round"].eq(True) & rounds["event_rank"].le(max_rank)
    return _agg(rounds.assign(finish=hit.astype(int)), "finish", "sum")


def _wins(rounds: pd.DataFrame) -> pd.DataFrame:
    return _finishes(rounds, 1)


def _podiums(rounds: pd.DataFrame) -> pd.DataFrame:
    return _finishes(rounds, 3)


ROUND_METRICS: dict[LeaderboardMetric, Callable[[pd.DataFrame], pd.DataFrame]] = {
    LeaderboardMetric.AVG_SCORE: _avg_score,
    LeaderboardMetric.AVG_ADJUSTED: _avg_adjusted,
    LeaderboardMetric.BEST_SCORE: _best_score,
    LeaderboardMetric.WINS: _wins,
    LeaderboardMetric.PODIUMS: _podiums,
    LeaderboardMetric.EVENTS: _events,
    LeaderboardMetric.ROUNDS: _rounds,
}


def _finalize(
    body: pd.DataFrame, shooters: pd.DataFrame, min_rounds: int, status: str | None
) -> pd.DataFrame:
    rows = body[body["n_rounds"] >= min_rounds].merge(shooters, on="shooter_id", how="left")
    if status is not None:
        rows = rows[rows["status"] == status]
    rows = rows.assign(value=rows["value"].astype(float).round(2))
    rows = rows.sort_values(
        ["value", "sort_key", "shooter_id"], ascending=[False, True, True], kind="mergesort"
    )
    rows = rows.assign(rank=rows["value"].rank(method="min", ascending=False).astype(int))
    return rows[ROW_COLUMNS].reset_index(drop=True)


def leaderboard(
    frames: LeaderboardFrames,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    as_of: date,
    filters: LeaderboardFilters = NO_FILTERS,
) -> Leaderboard:
    min_rounds = min_rounds_for(metric, period, frames.events, as_of)
    start, end = period_bounds(period, as_of)
    body = ROUND_METRICS[metric](_round_filters(_window(frames.rounds, start, end), filters))
    rows = _finalize(body, frames.shooters, min_rounds, filters.status)
    return Leaderboard(period, metric, as_of, min_rounds, rows)
```

- [ ] **Step 8: Run the period and round-metric tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_periods.py tests/unit/analytics/competition/test_leaderboard_metrics.py -v`
Expected: PASS — 40 passed.

- [ ] **Step 9: Write the failing rating, most-improved and no-leak tests**

Create `backend/tests/unit/analytics/competition/test_leaderboard_ratings.py`:
```python
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sunday_clays.analytics.leaderboards import (
    Leaderboard,
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
    make_leaderboard_frames,
)
from sunday_clays.domain.round_type import RoundType

if TYPE_CHECKING:
    from conftest import FrameBuilder

ALL = LeaderboardPeriod.ALL_TIME
SEASON = LeaderboardPeriod.SEASON


def values(board: Leaderboard) -> dict[int, float]:
    return dict(zip(board.rows["shooter_id"], board.rows["value"], strict=True))


def _rated(fb: FrameBuilder, sid: int, start: date, n: int, mu: float) -> None:
    for week in range(n):
        day = start + timedelta(weeks=week)
        fb.round(day, sid, 40)
        fb.rating(sid, day, mu + week)


def test_rating_lists_active_shooters_and_ignores_round_filters(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").shooter(3, "Cy, Cal")
    fb.shooter(4, "Dee, Dot", status="guest")
    _rated(fb, 1, date(2026, 1, 4), 5, 30.0)  # active, mu 34 at its 5th event
    _rated(fb, 2, date(2026, 1, 4), 4, 40.0)  # only 4 rounds: inactive
    _rated(fb, 3, date(2024, 1, 7), 6, 45.0)  # nothing in the last 364 days: inactive
    _rated(fb, 4, date(2026, 1, 4), 5, 20.0)  # active guest
    frames = fb.frames()
    as_of = date(2026, 3, 1)
    board = leaderboard(frames, SEASON, LeaderboardMetric.RATING, as_of)
    assert values(board) == {1: 34.0, 4: 24.0}
    assert board.min_rounds_applied == 5
    no_sporting = LeaderboardFilters(round_types=(RoundType.SPORTING,), gauge="SxS")
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.RATING, as_of, no_sporting)) == {
        1: 34.0,
        4: 24.0,
    }
    members = LeaderboardFilters(status="member")
    assert values(leaderboard(frames, SEASON, LeaderboardMetric.RATING, as_of, members)) == {
        1: 34.0
    }


def _weekly(fb: FrameBuilder, sid: int, start: date, n: int, score: int, mu: float) -> None:
    for week in range(n):
        day = start + timedelta(weeks=week)
        fb.round(day, sid, score).rating(sid, day, mu)


def test_most_improved_excludes_prior_washout(fb: FrameBuilder) -> None:
    fb.shooter(1, "Washout, Wes").shooter(2, "Regular, Rae").shooter(3, "Short, Sam")
    before, inside = date(2025, 1, 5), date(2026, 1, 4)
    _weekly(fb, 1, before, 4, 10, 15.0)  # only 4 rounds before the season: not eligible
    _weekly(fb, 2, before, 10, 30, 30.0)
    _weekly(fb, 3, before, 12, 30, 30.0)
    _weekly(fb, 1, inside, 6, 45, 40.0)  # +25 would top the board if the washout counted
    _weekly(fb, 2, inside, 5, 35, 33.5)
    _weekly(fb, 3, inside, 4, 45, 44.0)  # only 4 rounds inside the season: not eligible
    board = leaderboard(fb.frames(), SEASON, LeaderboardMetric.MOST_IMPROVED, date(2026, 3, 1))
    assert values(board) == {2: 3.5}
    assert board.rows["n_rounds"].tolist() == [5]


def test_most_improved_all_time_starts_after_tenth_round(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    start = date(2025, 1, 5)
    for week in range(15):
        day = start + timedelta(weeks=week)
        fb.round(day, 1, 40).rating(1, day, 20.0 + week)  # mu after 10th round = 29, last = 34
    for week in range(14):  # 14 rounds < 15: not eligible
        day = start + timedelta(weeks=week)
        fb.round(day, 2, 40).rating(2, day, 10.0 + 3 * week)
    board = leaderboard(fb.frames(), ALL, LeaderboardMetric.MOST_IMPROVED, date(2026, 1, 4))
    assert values(board) == {1: 5.0}
    assert board.min_rounds_applied == 15


def test_empty_frames_give_empty_board(fb: FrameBuilder) -> None:
    frames = make_leaderboard_frames(fb.rounds(), fb.events(), fb.history())
    for metric in LeaderboardMetric:
        board = leaderboard(frames, ALL, metric, date(2026, 1, 4))
        assert board.n_eligible == 0
        assert board.records() == []
```

Create `backend/tests/unit/analytics/competition/test_leaderboard_no_leak.py` (it parametrizes over every
`LeaderboardMetric`, so Task 2's `season_points` is covered automatically):
```python
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd
import pytest

from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardFrames,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder

AS_OF = date(2026, 3, 1)
FIRST = date(2024, 10, 6)


def _season(fb: FrameBuilder, weeks: int, start: date) -> None:
    for week in range(weeks):
        day = start + timedelta(weeks=week)
        for sid in (1, 2, 3):
            score = 30 + (sid * 7 + week * 3) % 15
            fb.round(day, sid, score)
            fb.rating(sid, day, 28.0 + sid + 0.1 * week)
        if week % 3 == 0:
            fb.round(day, 1, 25, ordinal=2)


def _build(fb: FrameBuilder, *, with_future: bool) -> FrameBuilder:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob", status="guest").shooter(3, "Cy, Cal")
    fb.shooter(4, "Late, Lou")
    _season(fb, 73, FIRST)  # 2024-10-06 .. 2026-02-22
    if with_future:
        _season(fb, 10, date(2026, 3, 8))
        for week in range(10):
            day = date(2026, 3, 8) + timedelta(weeks=week)
            fb.round(day, 4, 50).rating(4, day, 45.0)
    return fb


@pytest.fixture(scope="module")
def worlds(make_builder: type[FrameBuilder]) -> tuple[LeaderboardFrames, LeaderboardFrames]:
    past = _build(make_builder(), with_future=False).frames()
    full = _build(make_builder(), with_future=True).frames()
    return past, full


@pytest.mark.parametrize("metric", list(LeaderboardMetric))
@pytest.mark.parametrize("period", list(LeaderboardPeriod))
@pytest.mark.parametrize(
    "filters", [LeaderboardFilters(), LeaderboardFilters(status="member", gauge="unspecified")]
)
def test_leaderboard_no_leak(
    worlds: tuple[LeaderboardFrames, LeaderboardFrames],
    metric: LeaderboardMetric,
    period: LeaderboardPeriod,
    filters: LeaderboardFilters,
) -> None:
    past = leaderboard(worlds[0], period, metric, AS_OF, filters)
    full = leaderboard(worlds[1], period, metric, AS_OF, filters)
    assert past.min_rounds_applied == full.min_rounds_applied
    pd.testing.assert_frame_equal(past.rows, full.rows)
    assert past.n_eligible > 0
```

- [ ] **Step 10: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_ratings.py tests/unit/analytics/competition/test_leaderboard_no_leak.py -v`
Expected: FAIL — 16 failed, 42 passed; every failure is `KeyError: <LeaderboardMetric.RATING: 'rating'>` or
`KeyError: <LeaderboardMetric.MOST_IMPROVED: 'most_improved'>` raised from `ROUND_METRICS[metric]`.

- [ ] **Step 11: Add the rating and most-improved boards**

Append to `backend/src/sunday_clays/analytics/leaderboards.py`:
```python
def _rating(frames: LeaderboardFrames, as_of: date) -> pd.DataFrame:
    classes = assign_classes(frames.history, frames.rounds, as_of)
    active = classes.loc[classes["klass"].notna(), ["shooter_id", "mu"]]
    counts = _rounds(frames.rounds[frames.rounds["event_date"] <= as_of])
    return active.rename(columns={"mu": "value"}).merge(
        counts[["shooter_id", "n_rounds"]], on="shooter_id", how="inner"
    )


def _most_improved(
    frames: LeaderboardFrames, period: LeaderboardPeriod, as_of: date
) -> pd.DataFrame:
    rounds = frames.rounds[frames.rounds["event_date"] <= as_of]
    history = frames.history[frames.history["event_date"] <= as_of].sort_values(
        ["shooter_id", "event_date"], kind="mergesort"
    )
    end_mu = history.groupby("shooter_id")["mu"].last()
    start, _ = period_bounds(period, as_of)
    if start is None:
        ordered = rounds.sort_values(["shooter_id", "event_date", "ordinal"], kind="mergesort")
        nth = ordered.assign(k=ordered.groupby("shooter_id").cumcount() + 1)
        tenth = nth.loc[nth["k"] == IMPROVED_MIN_BEFORE, ["shooter_id", "event_date"]]
        start_mu = tenth.merge(history, on=["shooter_id", "event_date"]).set_index("shooter_id")[
            "mu"
        ]
        n_rounds = rounds.groupby("shooter_id").size()
        eligible = set(n_rounds[n_rounds >= IMPROVED_ALL_TIME_MIN].index)
    else:
        n_before = rounds[rounds["event_date"] < start].groupby("shooter_id").size()
        n_rounds = rounds[rounds["event_date"] >= start].groupby("shooter_id").size()
        start_mu = history[history["event_date"] < start].groupby("shooter_id")["mu"].last()
        eligible = set(n_before[n_before >= IMPROVED_MIN_BEFORE].index) & set(
            n_rounds[n_rounds >= IMPROVED_MIN_INSIDE].index
        )
    delta = (end_mu - start_mu).dropna()
    delta = delta[delta.index.isin(sorted(eligible))]
    return pd.DataFrame(
        {
            "shooter_id": delta.index.astype(int),
            "value": delta.to_numpy(dtype=float),
            "n_rounds": [int(n_rounds[sid]) for sid in delta.index],
        }
    )
```

Replace the whole `leaderboard` function (added in Step 7) with:
```python
def leaderboard(
    frames: LeaderboardFrames,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    as_of: date,
    filters: LeaderboardFilters = NO_FILTERS,
) -> Leaderboard:
    min_rounds = min_rounds_for(metric, period, frames.events, as_of)
    if metric is LeaderboardMetric.RATING:
        body = _rating(frames, as_of)
    elif metric is LeaderboardMetric.MOST_IMPROVED:
        body = _most_improved(frames, period, as_of)
    else:
        start, end = period_bounds(period, as_of)
        body = ROUND_METRICS[metric](_round_filters(_window(frames.rounds, start, end), filters))
    rows = _finalize(body, frames.shooters, min_rounds, filters.status)
    return Leaderboard(period, metric, as_of, min_rounds, rows)
```

- [ ] **Step 12: Run every unit test of the engine to verify it passes**

Run: `cd backend && uv run pytest tests/unit/analytics/competition -v`
Expected: PASS — 98 passed (27 periods + 13 metrics + 4 ratings + 54 no-leak).

- [ ] **Step 13: Write the failing API tests**

Create `backend/tests/integration/api/test_leaderboards_api.py`:
```python
"""GET /api/leaderboards against the committed fixture world (golden values: Decision D22)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.routes import _filters
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule


def board(client: TestClient, **params: str) -> dict[str, Any]:
    response = client.get("/api/leaderboards", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_season_threshold_scales_early_year(fx_viewer_client: TestClient) -> None:
    body = board(fx_viewer_client, period="season", metric="avg_score", as_of="2024-01-28")
    assert body["min_rounds_applied"] == 1
    assert body["n_eligible"] == 34
    assert len(body["rows"]) == 34


def test_all_time_best_score_ties_share_rank_one(fx_viewer_client: TestClient) -> None:
    rows = board(fx_viewer_client, period="all_time", metric="best_score", as_of="2026-09-27")[
        "rows"
    ]
    assert [(r["rank"], r["value"]) for r in rows[:5]] == [(1, 50.0)] * 4 + [(5, 49.0)]


def test_fixture_golden_boards(fx_viewer_client: TestClient) -> None:
    wins = board(fx_viewer_client, period="all_time", metric="wins", as_of="2026-09-27")
    assert [r["value"] for r in wins["rows"][:3]] == [62.0, 45.0, 29.0]
    average = board(fx_viewer_client, period="all_time", metric="avg_score", as_of="2026-09-27")
    assert (average["min_rounds_applied"], average["n_eligible"]) == (15, 88)
    assert average["rows"][0]["value"] == 45.02
    rolling = board(fx_viewer_client, period="rolling_12", metric="avg_score", as_of="2026-09-27")
    assert (rolling["min_rounds_applied"], rolling["n_eligible"]) == (8, 49)


def test_round_type_filter_restricts_leaderboard_rounds(fx_viewer_client: TestClient) -> None:
    body = board(
        fx_viewer_client,
        period="all_time",
        metric="rounds",
        as_of="2026-09-27",
        round_type="super_sporting",
    )
    assert body["n_eligible"] == 32
    assert max(r["value"] for r in body["rows"]) == 2.0
    assert sum(r["value"] for r in body["rows"]) == 37.0


def test_status_filter_uses_current_status_and_set_status_override(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    shooter_id = fx_session.execute(
        text("SELECT shooter_id FROM shooter_aliases WHERE name_key = 'amberson edith'")
    ).scalar_one()
    params = {"period": "all_time", "metric": "avg_score", "as_of": "2026-09-27"}

    def listed(status: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = board(fx_viewer_client, status=status, **params)["rows"]
        return rows

    assert shooter_id in {r["shooter_id"] for r in listed("guest")}
    assert shooter_id not in {r["shooter_id"] for r in listed("member")}
    create_rule(
        fx_session, RuleType.SET_STATUS, {"shooter_id": shooter_id, "status": "member"}, None
    )
    rebuild_live(fx_session)
    assert shooter_id not in {r["shooter_id"] for r in listed("guest")}
    row = next(r for r in listed("member") if r["shooter_id"] == shooter_id)
    assert (row["status"], row["n_rounds"]) == ("member", 35)


def test_deceased_shooters_stay_on_boards(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    lennox = fx_session.execute(
        text("SELECT shooter_id FROM shooter_aliases WHERE name_key = 'lennox stan'")
    ).scalar_one()
    average = board(fx_viewer_client, period="all_time", metric="avg_score", as_of="2026-09-27")
    row = next(r for r in average["rows"] if r["shooter_id"] == lennox)
    assert (row["status"], row["rank"], row["value"]) == ("deceased", 16, 40.81)
    events = board(fx_viewer_client, period="all_time", metric="events", as_of="2026-09-27")
    assert lennox in {r["shooter_id"] for r in events["rows"]}
    then = board(fx_viewer_client, period="season", metric="rating", as_of="2024-12-08")
    assert lennox in {r["shooter_id"] for r in then["rows"]}
    now = board(fx_viewer_client, period="season", metric="rating", as_of="2026-09-27")
    assert lennox not in {r["shooter_id"] for r in now["rows"]}


def test_event_dates_list_every_scored_event(fx_viewer_client: TestClient) -> None:
    dates = board(fx_viewer_client, as_of="2026-09-27")["event_dates"]
    assert (len(dates), dates[0], dates[-1]) == (311, "2020-01-05", "2026-09-27")


def test_as_of_defaults_to_today_in_club_timezone(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    zones: list[str] = []

    def today_in(tz: str) -> date:
        zones.append(tz)
        return date(2026, 9, 27)

    monkeypatch.setattr(_filters, "today_local", today_in)
    body = board(viewer_client)
    assert body["as_of"] == "2026-09-27"
    assert set(zones) == {"America/Los_Angeles"}
    assert (body["period"], body["metric"], body["min_rounds_applied"]) == (
        "season",
        "avg_score",
        1,
    )
    assert (body["rows"], body["event_dates"], body["n_eligible"]) == ([], [], 0)


@pytest.mark.parametrize(
    "params",
    [{"metric": "bogus"}, {"period": "decade"}, {"status": "vip"}, {"round_type": "trap"}],
)
def test_invalid_query_values_are_rejected(
    viewer_client: TestClient, params: dict[str, str]
) -> None:
    assert viewer_client.get("/api/leaderboards", params=params).status_code == 422
```

- [ ] **Step 14: Run the API tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/api/test_leaderboards_api.py -v` (needs Docker for the
testcontainers Postgres, or `TEST_DATABASE_URL`)
Expected: FAIL — 12 failed; every request returns 404 (no `/api/leaderboards` route yet), e.g.
`AssertionError: {"detail":"Not Found"}` / `assert 404 == 422`.

- [ ] **Step 15: Add the cached loaders and the route**

Append to `backend/src/sunday_clays/analytics/leaderboards.py`:
```python
@cached_by_data_version
def load_leaderboard_frames(session: Session) -> LeaderboardFrames:
    return make_leaderboard_frames(
        load_rounds(session), load_events(session), load_rating_history(session)
    )


@cached_by_data_version
def leaderboard_for(
    session: Session,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    as_of: date,
    filters: LeaderboardFilters,
) -> Leaderboard:
    return leaderboard(load_leaderboard_frames(session), period, metric, as_of, filters)
```

Create `backend/src/sunday_clays/api/routes/leaderboards.py`:
```python
"""GET /api/leaderboards (C8): one leaderboard, time-sliced by as_of."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    ShooterStatus,
    leaderboard_for,
    load_leaderboard_frames,
    scored_event_dates,
)
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class LeaderboardRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    status: str | None
    value: float
    n_rounds: int


class LeaderboardOut(BaseModel):
    period: LeaderboardPeriod
    metric: LeaderboardMetric
    as_of: date
    min_rounds_applied: int
    n_eligible: int
    event_dates: list[date]
    rows: list[LeaderboardRowOut]


@router.get("/api/leaderboards", response_model=LeaderboardOut)
def get_leaderboard(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    period: LeaderboardPeriod = LeaderboardPeriod.SEASON,
    metric: LeaderboardMetric = LeaderboardMetric.AVG_SCORE,
    as_of: date | None = None,
    round_types: list[RoundType] = _filters.round_type_param,
    gauge: Annotated[str | None, Query(max_length=40)] = None,
    status: ShooterStatus | None = None,
) -> LeaderboardOut:
    day = _filters.resolve_as_of(as_of, settings.timezone)
    filters = LeaderboardFilters(round_types=tuple(round_types), gauge=gauge, status=status)
    board = leaderboard_for(session, period, metric, day, filters)
    return LeaderboardOut(
        period=board.period,
        metric=board.metric,
        as_of=board.as_of,
        min_rounds_applied=board.min_rounds_applied,
        n_eligible=board.n_eligible,
        event_dates=scored_event_dates(load_leaderboard_frames(session).events),
        rows=[LeaderboardRowOut.model_validate(row) for row in board.records()],
    )
```

- [ ] **Step 16: Run the API tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/api/test_leaderboards_api.py -v`
Expected: PASS — 12 passed.

- [ ] **Step 17: Format, then run the full backend gate**

Run:
```bash
cd backend
uv run ruff format src/sunday_clays/analytics/leaderboards.py src/sunday_clays/api/routes/leaderboards.py tests/unit/analytics/competition tests/integration/api/test_leaderboards_api.py
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch
```
Expected: ruff and mypy report no issues; every test passes, including Plan 04's
`tests/integration/api/test_route_auth_matrix.py`, which now also walks `GET /api/leaderboards` (401 without a
cookie); coverage stays ≥ 90 (the configured `fail_under`), with `leaderboards.py` fully covered by the unit and API
tests above.

- [ ] **Step 18: Commit**

```bash
git add backend/src/sunday_clays/analytics/leaderboards.py backend/src/sunday_clays/api/routes/leaderboards.py backend/tests/unit/analytics/competition backend/tests/integration/api/test_leaderboards_api.py
git commit -F - <<'EOF'
feat(leaderboards): add leaderboard engine and GET /api/leaderboards

Every C7 period x metric with thresholds, round-type/gauge/status filters,
full-field ranks, as_of time slicing and no-leak tests.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 2: Season championship points and GET /api/classes (master Plan 09 T2)

**Files:**
- Create: `backend/src/sunday_clays/analytics/points.py`
- Modify: `backend/src/sunday_clays/analytics/leaderboards.py` (import `season_points`; add
  `LeaderboardMetric.SEASON_POINTS` and its `ROUND_METRICS` entry; append `ClassRow`, `class_table`,
  `class_table_for`)
- Create: `backend/src/sunday_clays/api/routes/classes.py`
- Test: `backend/tests/unit/analytics/competition/test_points.py`
- Test: `backend/tests/unit/analytics/competition/test_class_table.py`
- Test: `backend/tests/integration/api/test_season_points_api.py`
- Test: `backend/tests/integration/api/test_classes_api.py`

**Interfaces:**
- Consumes: everything Task 1 produces in `sunday_clays.analytics.leaderboards` (`LeaderboardMetric`,
  `ROUND_METRICS`, `LeaderboardFrames`, `load_leaderboard_frames`, `leaderboard`, the `fb` fixture);
  `sunday_clays.analytics.classes.assign_classes(history, rounds, as_of) -> pd.DataFrame[shooter_id, mu, klass]`
  (Plan 06 T4); `cached_by_data_version` (Plan 06 T1); `sunday_clays.api.routes._filters.resolve_as_of(as_of: date |
  None, tz: str) -> date` and `today_local(tz: str) -> date` (Plan 06 T1; imported as a module, tests monkeypatch
  `_filters.today_local`, D12); `Settings`/`get_settings`, `get_session` (Plan 01 T1); fixtures `fx_viewer_client`,
  `viewer_client`, `make_builder`.
- Produces:
  - `sunday_clays.analytics.points`: `POINTS_BY_RANK: Mapping[int, int]` (`{1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7:
    2, 8: 1}`), `PARTICIPATION_POINTS = 1`, `points_for_rank(rank: int) -> int`,
    `event_points(rounds: pd.DataFrame) -> pd.DataFrame[event_date, shooter_id, event_rank, points]` (one row per best
    round), `season_points(rounds: pd.DataFrame) -> pd.DataFrame[shooter_id, value, n_rounds]`.
  - `LeaderboardMetric.SEASON_POINTS = "season_points"` (so `GET /api/leaderboards?metric=season_points` and Task 4's
    history default work).
  - `sunday_clays.analytics.leaderboards`: `@dataclass(frozen=True) class ClassRow: shooter_id: int; display_name:
    str; status: str | None; mu: float; klass: str`; `class_table(frames: LeaderboardFrames, as_of: date) ->
    tuple[ClassRow, ...]` (active shooters, mu desc then shooter_id); `@cached_by_data_version
    class_table_for(session, as_of: date) -> tuple[ClassRow, ...]`.
  - `GET /api/classes?as_of=` → `ClassesOut{as_of: date, n_active: int, rows: list[ClassRowOut{shooter_id: int,
    display_name: str, status: str | None, mu: float, klass: Literal["A", "B", "C", "D"]}]}` (Task 5 reads it for class
    badges).

**Branch:** `task/09-2-season-points-classes`

**Depends on:** Plan 09 T1; Plan 06 T4 (`assign_classes`).

- [ ] **Step 0: Confirm the consumed names**

Run:
```bash
cd backend
grep -nE "^(ROUND_METRICS|class LeaderboardMetric|def load_leaderboard_frames|def leaderboard)\b" src/sunday_clays/analytics/leaderboards.py
grep -nE "^def assign_classes\(" src/sunday_clays/analytics/classes.py
grep -nE "^def (today_local|resolve_as_of)\(" src/sunday_clays/api/routes/_filters.py
```
Expected: four matches in `leaderboards.py`, one in `classes.py` and two in `_filters.py`. If a name differs, adapt only this task's call
sites and list the mapping in your report.

- [ ] **Step 1: Write the failing season-points tests**

Create `backend/tests/unit/analytics/competition/test_points.py`:
```python
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
)
from sunday_clays.analytics.points import event_points, points_for_rank, season_points

if TYPE_CHECKING:
    from conftest import FrameBuilder

D1, D2 = date(2026, 1, 4), date(2026, 1, 11)


@pytest.mark.parametrize(
    ("rank", "points"),
    [(1, 11), (2, 9), (3, 7), (4, 6), (5, 5), (6, 4), (7, 3), (8, 2), (9, 1), (30, 1)],
)
def test_points_for_rank_includes_participation(rank: int, points: int) -> None:
    assert points_for_rank(rank) == points


def test_tied_finish_shares_points(fb: FrameBuilder) -> None:
    for sid, name in [(1, "Ace, Amy"), (2, "Bee, Bob"), (3, "Cy, Cal"), (4, "Dee, Dot")]:
        fb.shooter(sid, name)
    fb.day(D1, {1: 45, 2: 45, 3: 44, 4: 43})
    pts = event_points(fb.rounds())
    assert dict(zip(pts["shooter_id"], pts["points"], strict=True)) == {1: 11, 2: 11, 3: 7, 4: 6}
    board = leaderboard(fb.frames(), LeaderboardPeriod.SEASON, LeaderboardMetric.SEASON_POINTS, D1)
    assert board.rows[["shooter_id", "rank", "value"]].values.tolist() == [
        [1, 1, 11.0],
        [2, 1, 11.0],
        [3, 3, 7.0],
        [4, 4, 6.0],
    ]


def test_season_points_count_only_best_round_per_event(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.day(D1, {1: 45, 2: 40}).round(D1, 1, 30, ordinal=2).day(D2, {2: 41, 1: 39})
    body = season_points(fb.rounds())
    assert dict(zip(body["shooter_id"], body["value"], strict=True)) == {1: 11 + 9, 2: 9 + 11}
    assert dict(zip(body["shooter_id"], body["n_rounds"], strict=True)) == {1: 2, 2: 2}


def test_season_points_under_gauge_filter_keep_full_field_rank(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
    fb.round(D1, 1, 45).round(D1, 2, 40, gauge_class="Sub-Gauge")
    board = leaderboard(
        fb.frames(),
        LeaderboardPeriod.SEASON,
        LeaderboardMetric.SEASON_POINTS,
        D1,
        LeaderboardFilters(gauge="Sub-Gauge"),
    )
    assert board.rows[["shooter_id", "rank", "value"]].values.tolist() == [[2, 1, 9.0]]
```

Create `backend/tests/integration/api/test_season_points_api.py`:
```python
"""GET /api/leaderboards?metric=season_points on the committed fixtures (Decision D22)."""

from fastapi.testclient import TestClient


def test_season_points_2026_golden(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.get(
        "/api/leaderboards",
        params={"period": "season", "metric": "season_points", "as_of": "2026-09-27"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["min_rounds_applied"] == 1
    assert [(r["rank"], r["value"]) for r in body["rows"][:6]] == [
        (1, 191.0),
        (2, 139.0),
        (3, 129.0),
        (4, 111.0),
        (4, 111.0),
        (4, 111.0),
    ]
    assert body["rows"][6]["rank"] == 7
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_points.py tests/integration/api/test_season_points_api.py -v`
Expected: FAIL — `test_points.py` errors during collection with
`ModuleNotFoundError: No module named 'sunday_clays.analytics.points'`; `test_season_points_2026_golden` fails with a
422 (`season_points` is not yet a `LeaderboardMetric`).

- [ ] **Step 3: Add season points and wire them into the leaderboard**

Create `backend/src/sunday_clays/analytics/points.py`:
```python
"""Season championship points (C7): 10-8-6-5-4-3-2-1 by best-round rank, +1 per event."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

POINTS_BY_RANK: Mapping[int, int] = {1: 10, 2: 8, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2, 8: 1}
PARTICIPATION_POINTS = 1


def points_for_rank(rank: int) -> int:
    return POINTS_BY_RANK.get(rank, 0) + PARTICIPATION_POINTS


def event_points(rounds: pd.DataFrame) -> pd.DataFrame:
    best = rounds[rounds["is_best_round"].eq(True) & rounds["event_rank"].notna()]
    ranks = best["event_rank"].astype(int)
    return pd.DataFrame(
        {
            "event_date": best["event_date"].to_numpy(),
            "shooter_id": best["shooter_id"].to_numpy(),
            "event_rank": ranks.to_numpy(),
            "points": [points_for_rank(int(r)) for r in ranks],
        }
    )


def season_points(rounds: pd.DataFrame) -> pd.DataFrame:
    return (
        event_points(rounds)
        .groupby("shooter_id", as_index=False)
        .agg(value=("points", "sum"), n_rounds=("points", "size"))
    )
```

In `backend/src/sunday_clays/analytics/leaderboards.py` make three edits:
1. After `from sunday_clays.analytics.frames import (...)` add
   `from sunday_clays.analytics.points import season_points`.
2. Add a last member to `LeaderboardMetric`: `SEASON_POINTS = "season_points"` (after `MOST_IMPROVED`).
3. Add a last entry to `ROUND_METRICS`: `LeaderboardMetric.SEASON_POINTS: season_points,`.

`min_rounds_for` already returns 1 for it (Decision D5), and `test_leaderboard_no_leak` and
`test_empty_frames_give_empty_board` iterate over every metric, so they now cover `season_points` too.

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/competition tests/integration/api/test_season_points_api.py -v`
Expected: PASS — 118 passed (117 unit: the Task 1 suite now includes 6 `season_points` no-leak cases, plus 13
points tests; 1 API test).

- [ ] **Step 5: Write the failing class tests**

Create `backend/tests/unit/analytics/competition/test_class_table.py`:
```python
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sunday_clays.analytics.leaderboards import ClassRow, class_table

if TYPE_CHECKING:
    from conftest import FrameBuilder


def test_class_table_orders_active_shooters_by_mu(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob", status="guest").shooter(3, "Cy, Cal")
    fb.shooter(4, "Dee, Dot")
    start = date(2026, 1, 4)
    for week in range(5):
        day = start + timedelta(weeks=week)
        for sid, mu in ((1, 30.0), (2, 40.0), (3, 35.0)):
            fb.round(day, sid, 40).rating(sid, day, mu + week)
    fb.round(start, 4, 45).rating(4, start, 50.0)  # a single round: not active
    assert class_table(fb.frames(), date(2026, 2, 1)) == (
        ClassRow(shooter_id=2, display_name="Bee, Bob", status="guest", mu=44.0, klass="A"),
        ClassRow(shooter_id=3, display_name="Cy, Cal", status="member", mu=39.0, klass="B"),
        ClassRow(shooter_id=1, display_name="Ace, Amy", status="member", mu=34.0, klass="C"),
    )


def test_class_table_is_empty_without_active_shooters(fb: FrameBuilder) -> None:
    fb.shooter(1, "Ace, Amy").round(date(2026, 1, 4), 1, 40).rating(1, date(2026, 1, 4), 30.0)
    assert class_table(fb.frames(), date(2026, 1, 4)) == ()


def test_class_table_no_leak(make_builder: type[FrameBuilder]) -> None:
    def build(weeks: int) -> FrameBuilder:
        fb = make_builder().shooter(1, "Ace, Amy").shooter(2, "Bee, Bob")
        for week in range(weeks):
            day = date(2026, 1, 4) + timedelta(weeks=week)
            for sid in (1, 2):
                fb.round(day, sid, 40).rating(sid, day, 30.0 + sid + week)
        return fb

    past = class_table(build(5).frames(), date(2026, 2, 1))
    assert past == class_table(build(10).frames(), date(2026, 2, 1))
    assert len(past) == 2
```

Create `backend/tests/integration/api/test_classes_api.py`:
```python
"""GET /api/classes (C7 classes; golden counts from Decision D22)."""

from collections import Counter
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.routes import _filters


def test_classes_split_active_shooters_by_rating(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.get("/api/classes", params={"as_of": "2026-09-27"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["as_of"], body["n_active"]) == ("2026-09-27", 83)
    assert Counter(r["klass"] for r in body["rows"]) == {"A": 13, "B": 29, "C": 29, "D": 12}
    mus = [r["mu"] for r in body["rows"]]
    assert mus == sorted(mus, reverse=True)
    assert [r["klass"] for r in body["rows"]] == sorted(r["klass"] for r in body["rows"])


def test_classes_default_to_today_on_an_empty_database(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2026, 9, 27))
    body = viewer_client.get("/api/classes").json()
    assert body == {"as_of": "2026-09-27", "n_active": 0, "rows": []}


def test_classes_include_deceased_shooters_while_active(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    lennox = fx_session.execute(
        text("SELECT shooter_id FROM shooter_aliases WHERE name_key = 'lennox stan'")
    ).scalar_one()
    then = fx_viewer_client.get("/api/classes", params={"as_of": "2024-12-08"}).json()
    assert [r["status"] for r in then["rows"] if r["shooter_id"] == lennox] == ["deceased"]
    now = fx_viewer_client.get("/api/classes", params={"as_of": "2026-09-27"}).json()
    assert lennox not in {r["shooter_id"] for r in now["rows"]}
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_class_table.py tests/integration/api/test_classes_api.py -v`
Expected: FAIL — `test_class_table.py` errors during collection with
`ImportError: cannot import name 'ClassRow' from 'sunday_clays.analytics.leaderboards'`; all three API tests get 404
(`test_classes_include_deceased_shooters_while_active` then fails with `KeyError: 'rows'`).

- [ ] **Step 7: Add the class table and the route**

Append to `backend/src/sunday_clays/analytics/leaderboards.py`:
```python
@dataclass(frozen=True)
class ClassRow:
    shooter_id: int
    display_name: str
    status: str | None
    mu: float
    klass: str


def class_table(frames: LeaderboardFrames, as_of: date) -> tuple[ClassRow, ...]:
    classes = assign_classes(frames.history, frames.rounds, as_of)
    active = classes[classes["klass"].notna()].merge(frames.shooters, on="shooter_id", how="left")
    active = active.sort_values(["mu", "shooter_id"], ascending=[False, True], kind="mergesort")
    return tuple(
        ClassRow(
            shooter_id=int(rec["shooter_id"]),
            display_name=str(rec["display_name"]),
            status=None if pd.isna(rec["status"]) else str(rec["status"]),
            mu=round(float(rec["mu"]), 2),
            klass=str(rec["klass"]),
        )
        for rec in active.to_dict("records")
    )


@cached_by_data_version
def class_table_for(session: Session, as_of: date) -> tuple[ClassRow, ...]:
    return class_table(load_leaderboard_frames(session), as_of)
```

Create `backend/src/sunday_clays/api/routes/classes.py`:
```python
"""GET /api/classes (C7 classes A-D; ignores every filter)."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from sunday_clays.analytics.leaderboards import class_table_for
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session

router = APIRouter()


class ClassRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shooter_id: int
    display_name: str
    status: str | None
    mu: float
    klass: Literal["A", "B", "C", "D"]


class ClassesOut(BaseModel):
    as_of: date
    n_active: int
    rows: list[ClassRowOut]


@router.get("/api/classes", response_model=ClassesOut)
def get_classes(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: date | None = None,
) -> ClassesOut:
    day = _filters.resolve_as_of(as_of, settings.timezone)
    rows = class_table_for(session, day)
    return ClassesOut(
        as_of=day, n_active=len(rows), rows=[ClassRowOut.model_validate(r) for r in rows]
    )
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_class_table.py tests/integration/api/test_classes_api.py -v`
Expected: PASS — 6 passed (3 unit, including the C7 no-leak test `test_class_table_no_leak`, + 3 API).

- [ ] **Step 9: Format, then run the full backend gate**

Run:
```bash
cd backend
uv run ruff format src/sunday_clays/analytics src/sunday_clays/api/routes/classes.py tests/unit/analytics/competition tests/integration/api/test_season_points_api.py tests/integration/api/test_classes_api.py
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch
```
Expected: ruff and mypy clean; every test passes (the Plan 04 route matrix now also walks `GET /api/classes`); coverage
≥ 90.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/points.py backend/src/sunday_clays/analytics/leaderboards.py backend/src/sunday_clays/api/routes/classes.py backend/tests/unit/analytics/competition/test_points.py backend/tests/unit/analytics/competition/test_class_table.py backend/tests/integration/api/test_season_points_api.py backend/tests/integration/api/test_classes_api.py
git commit -F - <<'EOF'
feat(leaderboards): add season points and GET /api/classes

Season championship points (10-8-6-5-4-3-2-1 +1 by full-field best-round rank,
ties share the shared rank's points) as leaderboard metric season_points, and
the A-D class table as of any date.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 3: Club records and GET /api/records (master Plan 09 T3)

**Files:**
- Create: `backend/src/sunday_clays/analytics/records.py`
- Create: `backend/src/sunday_clays/api/routes/records.py`
- Test: `backend/tests/unit/analytics/records/test_records_unit.py`
- Test: `backend/tests/integration/api/test_records_api.py`

**Interfaces:**
- Consumes (Plan 06): `sunday_clays.analytics.frames.load_rounds`, `load_events`, `load_rating_history`,
  `apply_round_type_filter(df, round_types)`; `sunday_clays.analytics.streaks.streaks(rounds, events, as_of) ->
  pd.DataFrame[shooter_id, current_streak, longest_streak]` (Plan 06 T6); `cached_by_data_version`;
  `sunday_clays.api.routes._filters` (imported as a module, D12): `round_type_param`, `today_local(tz: str) -> date`
  (tests monkeypatch `_filters.today_local`). Also `RoundType` (Plan 03 T2), `Settings`/`get_settings`,
  `get_session` (Plan 01 T1); fixtures `fx_viewer_client`, `viewer_client`.
- Produces (`sunday_clays.analytics.records`):
  - `RECORD_LIMIT = 10`, `PERFECT_SCORE = 50`
  - frozen dataclasses `RoundRecord(rank: int, shooter_id: int, display_name: str, event_date: date, value: float)`,
    `JumpRecord(rank, shooter_id, display_name, event_date: date, prev_event_date: date, from_score: int, to_score:
    int, value: float)`, `ShooterRecord(rank, shooter_id, display_name, value: float)`, `RatingRecord(rank,
    shooter_id, display_name, event_date: date, value: float)`, `Records(as_of: date, highest_scores:
    tuple[RoundRecord, ...], perfect_rounds: tuple[RoundRecord, ...], biggest_adjusted: tuple[RoundRecord, ...],
    biggest_jumps: tuple[JumpRecord, ...], most_events: tuple[ShooterRecord, ...], longest_streaks:
    tuple[ShooterRecord, ...], highest_ratings: tuple[RatingRecord, ...])`
  - `compute_records(rounds, events, history, *, as_of: date, round_types: Sequence[RoundType] = (), limit: int =
    RECORD_LIMIT) -> Records`
  - `@cached_by_data_version records_for(session, as_of: date, round_types: tuple[RoundType, ...]) -> Records`
  - `GET /api/records?round_type=` → `RecordsOut{as_of, highest_scores: list[RecordRoundOut], perfect_rounds:
    list[RecordRoundOut], biggest_adjusted: list[RecordRoundOut], biggest_jumps: list[RecordJumpOut], most_events:
    list[RecordShooterOut], longest_streaks: list[RecordShooterOut], highest_ratings: list[RecordRatingOut]}`, each
    `*Out` with exactly the fields of the matching dataclass (Task 6 reads them).

**Branch:** `task/09-3-records`

**Depends on:** Plan 06 T1 (frames, cache, `_filters`), T2 (`adjusted`), T4 (`rating_history`), T6 (`streaks`).

- [ ] **Step 0: Confirm the consumed names**

Run:
```bash
cd backend
grep -nE "^def (load_rounds|load_events|load_rating_history|apply_round_type_filter)\(" src/sunday_clays/analytics/frames.py
grep -nE "^def streaks\(" src/sunday_clays/analytics/streaks.py
grep -nE "^(round_type_param|def today_local\()" src/sunday_clays/api/routes/_filters.py
grep -n "include_router" src/sunday_clays/api/app.py
ls tests/unit/analytics
```
Expected: every grep matches (two in `_filters.py`); `streaks` takes `(rounds, events, as_of)` and returns a `longest_streak` column;
`create_app()` calls `app.include_router(router, …)` with no `prefix=` (D14; only if it passes `prefix="/api"`, drop
`/api` from this task's decorator). If `tests/unit/analytics`
contains an `__init__.py`, create an empty `__init__.py` in `tests/unit/analytics/records/` too. Adapt only this task's
call sites to any other difference and list it in your report.

- [ ] **Step 1: Write the failing records unit tests**

Create `backend/tests/unit/analytics/records/test_records_unit.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from sunday_clays.analytics.records import (
    JumpRecord,
    RatingRecord,
    Records,
    RoundRecord,
    ShooterRecord,
    compute_records,
)
from sunday_clays.domain.round_type import RoundType

NAMES = {1: "Ace, Amy", 2: "Bee, Bob", 3: "Cy, Cal"}
ROUND_COLUMNS = [
    "round_id", "event_date", "shooter_id", "name_key", "display_name", "ordinal", "score",
    "gauge_class", "status", "shooter_status", "round_type", "field_median", "adjusted",
    "event_rank", "is_best_round", "percentile", "expected", "residual", "mu_before",
    "mu_after", "temp_f", "apparent_f", "precip_in", "wind_mph", "gust_mph", "wind_dir_deg",
    "cloud_pct", "condition", "gauge",
]  # fmt: skip
EVENT_COLUMNS = [
    "event_date", "round_type", "round_type_source", "head_count", "n_rounds", "n_shooters",
    "has_scores", "has_stations", "results_complete",
]  # fmt: skip
D = [date(2026, 1, 4) + timedelta(weeks=i) for i in range(8)]


@dataclass
class World:
    """Minimal C7-shaped frames for records: rounds, events, rating history."""

    round_rows: list[dict[str, Any]] = field(default_factory=list)
    event_rows: dict[date, dict[str, Any]] = field(default_factory=dict)
    history_rows: list[dict[str, Any]] = field(default_factory=list)

    def event(
        self, day: date, *, round_type: str = "unknown", held: bool = True, scores: bool = True
    ) -> World:
        self.event_rows[day] = dict.fromkeys(EVENT_COLUMNS) | {
            "event_date": day,
            "round_type": round_type,
            "has_scores": scores,
            "results_complete": scores and held,
        }
        return self

    def shot(
        self, day: date, sid: int, score: int, *, ordinal: int = 1, adjusted: float | None = None
    ) -> World:
        if day not in self.event_rows:
            self.event(day)
        self.round_rows.append(
            dict.fromkeys(ROUND_COLUMNS)
            | {
                "round_id": len(self.round_rows) + 1,
                "event_date": day,
                "shooter_id": sid,
                "name_key": NAMES[sid].casefold().replace(",", ""),
                "display_name": NAMES[sid],
                "ordinal": ordinal,
                "score": score,
                "adjusted": adjusted,
                "shooter_status": "member",
                "round_type": self.event_rows[day]["round_type"],
                "gauge": "unspecified",
            }
        )
        return self

    def rating(self, sid: int, day: date, mu: float) -> World:
        self.history_rows.append({"shooter_id": sid, "event_date": day, "mu": mu, "var": 4.0})
        return self

    def records(self, as_of: date = D[-1], **kw: Any) -> Records:
        rounds = pd.DataFrame(self.round_rows, columns=ROUND_COLUMNS)
        rounds["adjusted"] = rounds["adjusted"].astype(float)
        events = pd.DataFrame(
            [self.event_rows[d] for d in sorted(self.event_rows)], columns=EVENT_COLUMNS
        )
        history = pd.DataFrame(self.history_rows, columns=["shooter_id", "event_date", "mu", "var"])
        return compute_records(rounds, events, history, as_of=as_of, **kw)


def test_highest_scores_order_by_value_then_earliest_date() -> None:
    w = World().shot(D[1], 1, 48).shot(D[2], 2, 50).shot(D[0], 3, 48)
    assert w.records().highest_scores == (
        RoundRecord(rank=1, shooter_id=2, display_name="Bee, Bob", event_date=D[2], value=50.0),
        RoundRecord(rank=2, shooter_id=3, display_name="Cy, Cal", event_date=D[0], value=48.0),
        RoundRecord(rank=2, shooter_id=1, display_name="Ace, Amy", event_date=D[1], value=48.0),
    )


def test_perfect_rounds_list_every_50_beyond_the_limit() -> None:
    w = World().shot(D[0], 1, 50).shot(D[1], 2, 50).shot(D[1], 3, 49)
    records = w.records(limit=1)
    assert [r.shooter_id for r in records.highest_scores] == [1]
    assert [(r.shooter_id, r.event_date) for r in records.perfect_rounds] == [(1, D[0]), (2, D[1])]


def test_biggest_adjusted_ignores_rounds_without_adjusted() -> None:
    w = World().shot(D[0], 1, 45, adjusted=9.5).shot(D[0], 2, 30, adjusted=-5.5).shot(D[1], 3, 50)
    assert [(r.shooter_id, r.value) for r in w.records().biggest_adjusted] == [(1, 9.5), (2, -5.5)]


def test_biggest_jump_needs_consecutive_scored_events() -> None:
    w = World()
    w.shot(D[0], 1, 20).shot(D[1], 1, 35).shot(D[3], 1, 49)  # D[1] -> D[3] skips D[2]
    w.shot(D[0], 2, 30).shot(D[1], 2, 31).shot(D[2], 2, 29).shot(D[3], 2, 40)
    w.shot(D[1], 2, 36, ordinal=2)  # the day's best round (36) is what counts
    w.event(D[4], scores=False)  # attendance-only events are not in the sequence
    w.shot(D[5], 2, 45)
    assert w.records().biggest_jumps == (
        JumpRecord(
            rank=1, shooter_id=1, display_name="Ace, Amy", event_date=D[1],
            prev_event_date=D[0], from_score=20, to_score=35, value=15.0,
        ),
        JumpRecord(
            rank=2, shooter_id=2, display_name="Bee, Bob", event_date=D[3],
            prev_event_date=D[2], from_score=29, to_score=40, value=11.0,
        ),
        JumpRecord(
            rank=3, shooter_id=2, display_name="Bee, Bob", event_date=D[1],
            prev_event_date=D[0], from_score=30, to_score=36, value=6.0,
        ),
        JumpRecord(
            rank=4, shooter_id=2, display_name="Bee, Bob", event_date=D[5],
            prev_event_date=D[3], from_score=40, to_score=45, value=5.0,
        ),
    )  # fmt: skip


def test_most_events_counts_distinct_dates() -> None:
    w = World().shot(D[0], 1, 40).shot(D[0], 1, 30, ordinal=2).shot(D[1], 1, 41).shot(D[0], 2, 45)
    assert w.records().most_events == (
        ShooterRecord(rank=1, shooter_id=1, display_name="Ace, Amy", value=2.0),
        ShooterRecord(rank=2, shooter_id=2, display_name="Bee, Bob", value=1.0),
    )


def test_deceased_shooters_keep_their_records() -> None:
    w = World().shot(D[0], 1, 44).shot(D[0], 2, 50).shot(D[1], 2, 46)
    for row in w.round_rows:
        if row["shooter_id"] == 2:
            row["status"] = row["shooter_status"] = "deceased"
    records = w.records()
    assert records.highest_scores[0] == RoundRecord(
        rank=1, shooter_id=2, display_name="Bee, Bob", event_date=D[0], value=50.0
    )
    assert [(r.shooter_id, r.event_date) for r in records.perfect_rounds] == [(2, D[0])]
    assert records.most_events[0] == ShooterRecord(
        rank=1, shooter_id=2, display_name="Bee, Bob", value=2.0
    )


def test_longest_streaks_skip_non_held_events() -> None:
    w = World().shot(D[0], 1, 40).shot(D[1], 1, 40)
    w.event(D[2], held=False).shot(D[2], 2, 30)  # not held: neither extends nor breaks
    w.shot(D[3], 1, 40).shot(D[4], 2, 41)
    assert [(r.shooter_id, r.value) for r in w.records().longest_streaks] == [(1, 3.0), (2, 1.0)]


def test_highest_ratings_take_each_shooters_peak() -> None:
    w = World().shot(D[0], 1, 40).shot(D[0], 2, 30)
    w.rating(1, D[0], 30.0).rating(1, D[1], 35.004).rating(1, D[2], 33.0).rating(2, D[0], 31.0)
    assert w.records().highest_ratings == (
        RatingRecord(rank=1, shooter_id=1, display_name="Ace, Amy", event_date=D[1], value=35.0),
        RatingRecord(rank=2, shooter_id=2, display_name="Bee, Bob", event_date=D[0], value=31.0),
    )


def test_records_round_type_filter_limits_events() -> None:
    w = World().event(D[0], round_type="sporting").event(D[1], round_type="super_sporting")
    w.shot(D[0], 1, 44).shot(D[1], 1, 47).shot(D[1], 2, 40)
    records = w.records(round_types=(RoundType.SPORTING,))
    assert [(r.shooter_id, r.value) for r in records.highest_scores] == [(1, 44.0)]
    assert [(r.shooter_id, r.value) for r in records.most_events] == [(1, 1.0)]


def test_records_no_leak() -> None:
    def build(future: bool) -> World:
        w = World()
        for i, day in enumerate(D[:4]):
            w.shot(day, 1, 35 + i, adjusted=float(i)).shot(day, 2, 40 - i).rating(1, day, 30.0 + i)
        if future:
            for day in D[4:]:
                w.shot(day, 1, 50, adjusted=20.0).shot(day, 3, 49).rating(1, day, 45.0)
        return w

    assert build(False).records(as_of=D[3]) == build(True).records(as_of=D[3])


def test_records_on_empty_frames_are_empty() -> None:
    records = World().records()
    assert records.highest_scores == ()
    assert records.biggest_jumps == ()
    assert records.longest_streaks == ()
    assert records.highest_ratings == ()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/records/test_records_unit.py -v`
Expected: ERROR during collection — `ModuleNotFoundError: No module named 'sunday_clays.analytics.records'`.

- [ ] **Step 3: Implement the records module**

Create `backend/src/sunday_clays/analytics/records.py` (`records_for` and the loader imports it needs are used in
Step 7; `ruff` runs in Step 9):
```python
"""Club records (Plan 09 T3): pure over the C7 frames, round-type filtered, sliced by as_of."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.frames import (
    apply_round_type_filter,
    load_events,
    load_rating_history,
    load_rounds,
)
from sunday_clays.analytics.streaks import streaks
from sunday_clays.domain.round_type import RoundType

RECORD_LIMIT = 10
PERFECT_SCORE = 50


@dataclass(frozen=True)
class RoundRecord:
    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


@dataclass(frozen=True)
class JumpRecord:
    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    prev_event_date: date
    from_score: int
    to_score: int
    value: float


@dataclass(frozen=True)
class ShooterRecord:
    rank: int
    shooter_id: int
    display_name: str
    value: float


@dataclass(frozen=True)
class RatingRecord:
    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


@dataclass(frozen=True)
class Records:
    as_of: date
    highest_scores: tuple[RoundRecord, ...]
    perfect_rounds: tuple[RoundRecord, ...]
    biggest_adjusted: tuple[RoundRecord, ...]
    biggest_jumps: tuple[JumpRecord, ...]
    most_events: tuple[ShooterRecord, ...]
    longest_streaks: tuple[ShooterRecord, ...]
    highest_ratings: tuple[RatingRecord, ...]


def _with_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["event_date"] = pd.to_datetime(out["event_date"]).dt.date
    return out


def _ranked(df: pd.DataFrame, order: list[str], limit: int | None) -> list[dict[Any, Any]]:
    """Sort by ``order`` (first key descending, the rest ascending), min-rank on value."""
    ascending = [False] + [True] * (len(order) - 1)
    out = df.assign(value=df["value"].astype(float).round(2))
    out = out.sort_values(order, ascending=ascending, kind="mergesort")
    out = out.assign(rank=out["value"].rank(method="min", ascending=False).astype(int))
    if limit is not None:
        out = out.head(limit)
    return out.to_dict("records")


def _round_records(
    rounds: pd.DataFrame, values: pd.Series, names: pd.DataFrame, limit: int | None
) -> tuple[RoundRecord, ...]:
    df = rounds[["shooter_id", "event_date", "ordinal"]].assign(value=values.to_numpy())
    df = df.merge(names, on="shooter_id", how="left")
    return tuple(
        RoundRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            event_date=r["event_date"],
            value=float(r["value"]),
        )
        for r in _ranked(df, ["value", "event_date", "sort_key", "ordinal"], limit)
    )


def _shooter_records(
    values: pd.DataFrame, names: pd.DataFrame, limit: int
) -> tuple[ShooterRecord, ...]:
    df = values.merge(names, on="shooter_id", how="left")
    return tuple(
        ShooterRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            value=float(r["value"]),
        )
        for r in _ranked(df, ["value", "sort_key", "shooter_id"], limit)
    )


def _jumps(
    rounds: pd.DataFrame, events: pd.DataFrame, names: pd.DataFrame, limit: int
) -> tuple[JumpRecord, ...]:
    order = sorted(set(events.loc[events["has_scores"].eq(True), "event_date"]))
    position = {day: i for i, day in enumerate(order)}
    best = rounds.groupby(["shooter_id", "event_date"], as_index=False).agg(score=("score", "max"))
    best = best[best["event_date"].isin(order)]
    best = best.assign(pos=best["event_date"].map(position)).sort_values(
        ["shooter_id", "pos"], kind="mergesort"
    )
    by_shooter = best.groupby("shooter_id")
    best = best.assign(
        prev_pos=by_shooter["pos"].shift(),
        prev_score=by_shooter["score"].shift(),
        prev_date=by_shooter["event_date"].shift(),
    )
    jumps = best[(best["pos"] - best["prev_pos"]).eq(1)]
    jumps = jumps.assign(value=jumps["score"] - jumps["prev_score"])
    jumps = jumps[jumps["value"] > 0].merge(names, on="shooter_id", how="left")
    return tuple(
        JumpRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            event_date=r["event_date"],
            prev_event_date=r["prev_date"],
            from_score=int(r["prev_score"]),
            to_score=int(r["score"]),
            value=float(r["value"]),
        )
        for r in _ranked(jumps, ["value", "event_date", "sort_key"], limit)
    )


def _highest_ratings(
    history: pd.DataFrame, names: pd.DataFrame, limit: int
) -> tuple[RatingRecord, ...]:
    peaks = (
        history.sort_values(["shooter_id", "mu", "event_date"], ascending=[True, False, True])
        .groupby("shooter_id")
        .head(1)
    )
    df = peaks[["shooter_id", "event_date"]].assign(value=peaks["mu"].to_numpy())
    df = df.merge(names, on="shooter_id", how="left")
    return tuple(
        RatingRecord(
            rank=int(r["rank"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            event_date=r["event_date"],
            value=float(r["value"]),
        )
        for r in _ranked(df, ["value", "event_date", "sort_key"], limit)
    )


def compute_records(
    rounds: pd.DataFrame,
    events: pd.DataFrame,
    history: pd.DataFrame,
    *,
    as_of: date,
    round_types: Sequence[RoundType] = (),
    limit: int = RECORD_LIMIT,
) -> Records:
    all_rounds = _with_dates(rounds)
    names = all_rounds.groupby("shooter_id", as_index=False).agg(
        display_name=("display_name", "first"), sort_key=("name_key", "min")
    )
    dated_events = _with_dates(events)
    past_rounds = apply_round_type_filter(
        all_rounds[all_rounds["event_date"] <= as_of], round_types
    )
    past_events = apply_round_type_filter(
        dated_events[dated_events["event_date"] <= as_of], round_types
    )
    dated_history = _with_dates(history)
    past_history = dated_history[dated_history["event_date"] <= as_of]
    perfect = past_rounds[past_rounds["score"] == PERFECT_SCORE]
    adjusted = past_rounds[past_rounds["adjusted"].notna()]
    attended = past_rounds.groupby("shooter_id", as_index=False).agg(
        value=("event_date", "nunique")
    )
    streak = streaks(past_rounds, past_events, as_of)
    longest = streak.loc[streak["longest_streak"] > 0, ["shooter_id", "longest_streak"]].rename(
        columns={"longest_streak": "value"}
    )
    return Records(
        as_of=as_of,
        highest_scores=_round_records(past_rounds, past_rounds["score"], names, limit),
        perfect_rounds=_round_records(perfect, perfect["score"], names, None),
        biggest_adjusted=_round_records(adjusted, adjusted["adjusted"], names, limit),
        biggest_jumps=_jumps(past_rounds, past_events, names, limit),
        most_events=_shooter_records(attended, names, limit),
        longest_streaks=_shooter_records(longest, names, limit),
        highest_ratings=_highest_ratings(past_history, names, limit),
    )
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/records/test_records_unit.py -v`
Expected: PASS — 11 passed.

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/integration/api/test_records_api.py`:
```python
"""GET /api/records on the committed fixtures (golden values: Decision D22)."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters

LISTS = (
    "highest_scores",
    "perfect_rounds",
    "biggest_adjusted",
    "biggest_jumps",
    "most_events",
    "longest_streaks",
    "highest_ratings",
)


def records(client: TestClient, **params: str) -> dict[str, Any]:
    response = client.get("/api/records", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_records_golden(fx_viewer_client: TestClient) -> None:
    body = records(fx_viewer_client)
    assert [r["event_date"] for r in body["perfect_rounds"]] == [
        "2021-01-17",
        "2022-12-04",
        "2023-08-06",
        "2024-02-25",
        "2024-11-10",
        "2025-08-03",
    ]
    assert [(r["rank"], r["value"]) for r in body["highest_scores"]] == [(1, 50.0)] * 6 + [
        (7, 49.0)
    ] * 4
    assert body["most_events"][0]["value"] == 285.0
    assert body["longest_streaks"][0]["value"] == 56.0
    top = body["biggest_adjusted"][0]
    assert (top["value"], top["event_date"]) == (18.0, "2026-06-07")
    jump = body["biggest_jumps"][0]
    assert (
        jump["prev_event_date"],
        jump["event_date"],
        jump["from_score"],
        jump["to_score"],
        jump["value"],
    ) == ("2021-03-14", "2021-03-21", 11, 41, 30.0)
    ratings = [r["value"] for r in body["highest_ratings"]]
    assert len(ratings) == 10
    assert ratings == sorted(ratings, reverse=True)


def test_round_type_filter_restricts_rounds(fx_viewer_client: TestClient) -> None:
    body = records(fx_viewer_client, round_type="super_sporting")
    allowed = {"2026-09-06", "2026-09-13"}
    assert {r["event_date"] for r in body["highest_scores"]} <= allowed
    assert body["highest_scores"][0]["value"] == 48.0
    assert body["perfect_rounds"] == []
    assert max(r["value"] for r in body["most_events"]) == 2.0
    assert max(r["value"] for r in body["longest_streaks"]) == 2.0
    assert all({j["prev_event_date"], j["event_date"]} <= allowed for j in body["biggest_jumps"])
    assert body["highest_ratings"] == records(fx_viewer_client)["highest_ratings"]


def test_records_on_an_empty_database(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2026, 9, 27))
    body = records(viewer_client)
    assert body["as_of"] == "2026-09-27"
    assert all(body[key] == [] for key in LISTS)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/integration/api/test_records_api.py -v`
Expected: FAIL — 3 failed, each `AssertionError: {"detail":"Not Found"}` (no `/api/records` route yet).

- [ ] **Step 7: Add the cached loader and the route**

Append to `backend/src/sunday_clays/analytics/records.py`:
```python
@cached_by_data_version
def records_for(session: Session, as_of: date, round_types: tuple[RoundType, ...]) -> Records:
    return compute_records(
        load_rounds(session),
        load_events(session),
        load_rating_history(session),
        as_of=as_of,
        round_types=round_types,
    )
```

Create `backend/src/sunday_clays/api/routes/records.py`:
```python
"""GET /api/records (Plan 09 T3): club records as of today, round-type filterable."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from sunday_clays.analytics.records import records_for
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class RecordRoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


class RecordJumpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    prev_event_date: date
    from_score: int
    to_score: int
    value: float


class RecordShooterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    value: float


class RecordRatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rank: int
    shooter_id: int
    display_name: str
    event_date: date
    value: float


class RecordsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of: date
    highest_scores: list[RecordRoundOut]
    perfect_rounds: list[RecordRoundOut]
    biggest_adjusted: list[RecordRoundOut]
    biggest_jumps: list[RecordJumpOut]
    most_events: list[RecordShooterOut]
    longest_streaks: list[RecordShooterOut]
    highest_ratings: list[RecordRatingOut]


@router.get("/api/records", response_model=RecordsOut)
def get_records(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    round_types: list[RoundType] = _filters.round_type_param,
) -> RecordsOut:
    today = _filters.today_local(settings.timezone)
    return RecordsOut.model_validate(records_for(session, today, tuple(round_types)))
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/integration/api/test_records_api.py tests/unit/analytics/records -v`
Expected: PASS — 14 passed (3 API + 11 unit).

- [ ] **Step 9: Format, then run the full backend gate**

Run:
```bash
cd backend
uv run ruff format src/sunday_clays/analytics/records.py src/sunday_clays/api/routes/records.py tests/unit/analytics/records tests/integration/api/test_records_api.py
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch
```
Expected: ruff and mypy clean; every test passes (the Plan 04 route matrix now also walks `GET /api/records`); coverage
≥ 90.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/records.py backend/src/sunday_clays/api/routes/records.py backend/tests/unit/analytics/records backend/tests/integration/api/test_records_api.py
git commit -F - <<'EOF'
feat(records): add club records and GET /api/records

Highest scores, perfect 50s, biggest day vs the field, biggest week-over-week
jumps, most events, longest streaks (via streaks()) and highest rating ever,
filterable by round type and sliced by as_of.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 4: Leaderboard history (time machine) and GET /api/leaderboards/history (master Plan 09 T4)

**Files:**
- Create: `backend/src/sunday_clays/analytics/leaderboard_history.py`
- Create: `backend/src/sunday_clays/api/routes/leaderboard_history.py`
- Test: `backend/tests/unit/analytics/competition/test_leaderboard_history.py`
- Test: `backend/tests/integration/api/test_leaderboard_history_api.py`

This task never edits `analytics/leaderboards.py` or `routes/leaderboards.py` (master T4).

**Interfaces:**
- Consumes (Task 1 and Task 2, `sunday_clays.analytics.leaderboards`): `NO_FILTERS`, `LeaderboardFilters`,
  `LeaderboardFrames`, `LeaderboardMetric` (incl. `SEASON_POINTS`), `LeaderboardPeriod`, `LeaderboardRow`,
  `ShooterStatus`, `leaderboard(frames, period, metric, as_of, filters) -> Leaderboard` (with
  `records(top) -> list[LeaderboardRow]`), `load_leaderboard_frames(session)`, `scored_event_dates(events)`; the `fb`
  and `make_builder` fixtures. Also `cached_by_data_version` and `sunday_clays.api.routes._filters` (Plan 06 T1,
  imported as a module, D12: `round_type_param`, `today_local(tz: str) -> date`; tests monkeypatch
  `_filters.today_local`), `DomainError` (Plan 01 T1, → 400), `RoundType`, `Settings`/`get_settings`, `get_session`;
  fixtures `fx_viewer_client`, `viewer_client`.
- Produces (`sunday_clays.analytics.leaderboard_history`):
  - `@dataclass(frozen=True) class HistoryFrame: event_date: date; rows: tuple[LeaderboardRow, ...]`
  - `history_dates(events: pd.DataFrame, date_from: date, date_to: date) -> list[date]` (has_scores events in range)
  - `leaderboard_history(frames, period, metric, *, top: int, date_from: date, date_to: date, filters=NO_FILTERS) ->
    tuple[HistoryFrame, ...]`
  - `@cached_by_data_version leaderboard_history_for(session, period, metric, top, date_from, date_to, filters) ->
    tuple[HistoryFrame, ...]`
  - `GET /api/leaderboards/history?period=&metric=&top=&from=&to=&round_type=&gauge=&status=` →
    `LeaderboardHistoryOut{period, metric, frames: list[LeaderboardHistoryFrameOut{event_date: date, rows:
    list[LeaderboardHistoryRowOut{shooter_id: int, display_name: str, status: str | None, value: float, rank:
    int}]}]}` exactly per C8 (defaults and errors: Decision D12). Task 7 reads it.

**Branch:** `task/09-4-leaderboard-history`

**Depends on:** Plan 09 T1, T2.

- [ ] **Step 0: Confirm the consumed names**

Run:
```bash
cd backend
grep -nE "SEASON_POINTS|^def (leaderboard|load_leaderboard_frames|scored_event_dates)\(|^NO_FILTERS" src/sunday_clays/analytics/leaderboards.py
grep -nE "^class DomainError" src/sunday_clays/domain/errors.py
grep -nE "^(round_type_param|def today_local\()" src/sunday_clays/api/routes/_filters.py
```
Expected: `SEASON_POINTS` appears (Task 2 merged or is below this layer in the stack), plus the three functions,
`NO_FILTERS`, `DomainError`, `round_type_param` and `today_local`. Adapt only this task's call sites to any
difference and list it in your report.

- [ ] **Step 1: Write the failing history unit tests**

Create `backend/tests/unit/analytics/competition/test_leaderboard_history.py`:
```python
from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from sunday_clays.analytics.leaderboard_history import history_dates, leaderboard_history
from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    leaderboard,
)

if TYPE_CHECKING:
    from conftest import FrameBuilder

SEASON = LeaderboardPeriod.SEASON
POINTS = LeaderboardMetric.SEASON_POINTS


def _three_shooters(fb: FrameBuilder) -> FrameBuilder:
    return fb.shooter(1, "Ace, Amy").shooter(2, "Bee, Bob").shooter(3, "Cy, Cal", status="guest")


def test_history_frames_match_leaderboard_as_of(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    days = [date(2026, 1, 4), date(2026, 1, 11), date(2026, 1, 18)]
    fb.day(days[0], {1: 45, 2: 40, 3: 30}).day(days[1], {2: 44, 3: 43}).day(days[2], {3: 49, 1: 20})
    frames = fb.frames()
    history = leaderboard_history(frames, SEASON, POINTS, top=2, date_from=days[0], date_to=days[2])
    assert [f.event_date for f in history] == days
    assert [[(r.shooter_id, r.value, r.rank) for r in f.rows] for f in history] == [
        [(1, 11.0, 1), (2, 9.0, 2)],
        [(2, 20.0, 1), (3, 16.0, 2)],
        [(3, 27.0, 1), (1, 20.0, 2)],
    ]
    filters = LeaderboardFilters(status="member")
    filtered = leaderboard_history(
        frames, SEASON, POINTS, top=2, date_from=days[0], date_to=days[2], filters=filters
    )
    for frame in filtered:
        expected = leaderboard(frames, SEASON, POINTS, frame.event_date, filters).records(2)
        assert list(frame.rows) == expected


def test_history_points_reset_jan1(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    fb.day(date(2025, 12, 21), {1: 45, 2: 40}).day(date(2025, 12, 28), {1: 45, 2: 40})
    fb.day(date(2026, 1, 4), {2: 44, 1: 43})
    history = leaderboard_history(
        fb.frames(), SEASON, POINTS, top=5, date_from=date(2025, 12, 28), date_to=date(2026, 1, 4)
    )
    assert [(f.event_date, [(r.shooter_id, r.value) for r in f.rows]) for f in history] == [
        (date(2025, 12, 28), [(1, 22.0), (2, 18.0)]),
        (date(2026, 1, 4), [(2, 11.0), (1, 9.0)]),
    ]


def test_history_has_one_frame_per_scored_event_in_range(fb: FrameBuilder) -> None:
    _three_shooters(fb)
    fb.day(date(2026, 1, 4), {1: 40})
    fb.event(date(2026, 1, 11), has_scores=False)  # attendance only: no frame
    fb.day(date(2026, 1, 18), {1: 41}).day(date(2026, 1, 25), {1: 42})
    assert history_dates(fb.events(), date(2026, 1, 5), date(2026, 1, 25)) == [
        date(2026, 1, 18),
        date(2026, 1, 25),
    ]


def test_history_no_leak(make_builder: type[FrameBuilder]) -> None:
    def build(extra_weeks: int) -> FrameBuilder:
        fb = _three_shooters(make_builder())
        for week in range(6 + extra_weeks):
            fb.day(date(2026, 1, 4) + timedelta(weeks=week), {1: 40 + week % 3, 2: 41, 3: 39})
        return fb

    kwargs = {"top": 3, "date_from": date(2026, 1, 1), "date_to": date(2026, 2, 8)}
    past = leaderboard_history(build(0).frames(), SEASON, POINTS, **kwargs)
    full = leaderboard_history(build(4).frames(), SEASON, POINTS, **kwargs)
    assert past == full
    assert len(past) == 6
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_history.py -v`
Expected: ERROR during collection — `ModuleNotFoundError: No module named
'sunday_clays.analytics.leaderboard_history'`.

- [ ] **Step 3: Implement the history module**

Create `backend/src/sunday_clays/analytics/leaderboard_history.py`:
```python
"""Leaderboard time machine (C8 ``/api/leaderboards/history``).

One frame per has_scores event in [date_from, date_to]; each frame is the top-N rows of
``leaderboard(period, metric, as_of=event_date, same filters)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.leaderboards import (
    NO_FILTERS,
    LeaderboardFilters,
    LeaderboardFrames,
    LeaderboardMetric,
    LeaderboardPeriod,
    LeaderboardRow,
    leaderboard,
    load_leaderboard_frames,
    scored_event_dates,
)


@dataclass(frozen=True)
class HistoryFrame:
    event_date: date
    rows: tuple[LeaderboardRow, ...]


def history_dates(events: pd.DataFrame, date_from: date, date_to: date) -> list[date]:
    return [d for d in scored_event_dates(events) if date_from <= d <= date_to]


def leaderboard_history(
    frames: LeaderboardFrames,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    *,
    top: int,
    date_from: date,
    date_to: date,
    filters: LeaderboardFilters = NO_FILTERS,
) -> tuple[HistoryFrame, ...]:
    return tuple(
        HistoryFrame(
            event_date=day,
            rows=tuple(leaderboard(frames, period, metric, day, filters).records(top)),
        )
        for day in history_dates(frames.events, date_from, date_to)
    )


@cached_by_data_version
def leaderboard_history_for(
    session: Session,
    period: LeaderboardPeriod,
    metric: LeaderboardMetric,
    top: int,
    date_from: date,
    date_to: date,
    filters: LeaderboardFilters,
) -> tuple[HistoryFrame, ...]:
    return leaderboard_history(
        load_leaderboard_frames(session),
        period,
        metric,
        top=top,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
    )
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/competition/test_leaderboard_history.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/integration/api/test_leaderboard_history_api.py`:
```python
"""GET /api/leaderboards/history (C8) on the committed fixtures and an empty database."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters

ROW_KEYS = ("shooter_id", "display_name", "status", "value", "rank")


def history(client: TestClient, params: dict[str, str]) -> dict[str, Any]:
    response = client.get("/api/leaderboards/history", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_history_frames_match_the_leaderboard_endpoint(fx_viewer_client: TestClient) -> None:
    body = history(fx_viewer_client, {"top": "5", "from": "2026-09-01", "to": "2026-09-30"})
    assert (body["period"], body["metric"]) == ("season", "season_points")
    assert [f["event_date"] for f in body["frames"]] == ["2026-09-06", "2026-09-13", "2026-09-27"]
    for frame in body["frames"]:
        board = fx_viewer_client.get(
            "/api/leaderboards",
            params={"period": "season", "metric": "season_points", "as_of": frame["event_date"]},
        ).json()
        assert frame["rows"] == [{key: row[key] for key in ROW_KEYS} for row in board["rows"][:5]]
    assert body["frames"][-1]["rows"][0]["value"] == 191.0


def test_history_points_reset_jan1_on_the_fixture(fx_viewer_client: TestClient) -> None:
    body = history(fx_viewer_client, {"from": "2025-12-28", "to": "2026-01-04"})
    assert [(f["event_date"], f["rows"][0]["value"]) for f in body["frames"]] == [
        ("2025-12-28", 254.0),
        ("2026-01-04", 11.0),
    ]


def test_history_passes_filters_to_every_frame(fx_viewer_client: TestClient) -> None:
    params = {
        "period": "all_time",
        "metric": "rounds",
        "top": "50",
        "from": "2026-09-01",
        "to": "2026-09-30",
        "round_type": "super_sporting",
    }
    frames = history(fx_viewer_client, params)["frames"]
    assert [f["event_date"] for f in frames] == ["2026-09-06", "2026-09-13", "2026-09-27"]
    last = frames[-1]["rows"]
    assert (len(last), sum(r["value"] for r in last)) == (32, 37.0)


def test_history_defaults_to_this_season_up_to_today(
    fx_viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: date(2026, 1, 4))
    frames = history(fx_viewer_client, {})["frames"]
    assert [(f["event_date"], f["rows"][0]["value"]) for f in frames] == [("2026-01-04", 11.0)]
    assert len(frames[0]["rows"]) == 10


def test_history_defaults_on_an_empty_database(viewer_client: TestClient) -> None:
    assert history(viewer_client, {}) == {
        "period": "season",
        "metric": "season_points",
        "frames": [],
    }


def test_history_rejects_an_inverted_range(viewer_client: TestClient) -> None:
    response = viewer_client.get(
        "/api/leaderboards/history", params={"from": "2026-02-01", "to": "2026-01-01"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


@pytest.mark.parametrize("top", ["0", "51"])
def test_history_top_is_bounded(viewer_client: TestClient, top: str) -> None:
    assert viewer_client.get("/api/leaderboards/history", params={"top": top}).status_code == 422
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/integration/api/test_leaderboard_history_api.py -v`
Expected: FAIL — 8 failed; every request returns 404 (no `/api/leaderboards/history` route yet).

- [ ] **Step 7: Add the route**

Create `backend/src/sunday_clays/api/routes/leaderboard_history.py`:
```python
"""GET /api/leaderboards/history (C8): the time-machine frames behind the race page."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from sunday_clays.analytics.leaderboard_history import leaderboard_history_for
from sunday_clays.analytics.leaderboards import (
    LeaderboardFilters,
    LeaderboardMetric,
    LeaderboardPeriod,
    ShooterStatus,
)
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()


class LeaderboardHistoryRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shooter_id: int
    display_name: str
    status: str | None
    value: float
    rank: int


class LeaderboardHistoryFrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_date: date
    rows: list[LeaderboardHistoryRowOut]


class LeaderboardHistoryOut(BaseModel):
    period: LeaderboardPeriod
    metric: LeaderboardMetric
    frames: list[LeaderboardHistoryFrameOut]


@router.get("/api/leaderboards/history", response_model=LeaderboardHistoryOut)
def get_leaderboard_history(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    period: LeaderboardPeriod = LeaderboardPeriod.SEASON,
    metric: LeaderboardMetric = LeaderboardMetric.SEASON_POINTS,
    top: Annotated[int, Query(ge=1, le=50)] = 10,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    round_types: list[RoundType] = _filters.round_type_param,
    gauge: Annotated[str | None, Query(max_length=40)] = None,
    status: ShooterStatus | None = None,
) -> LeaderboardHistoryOut:
    end = date_to or _filters.today_local(settings.timezone)
    start = date_from or date(end.year, 1, 1)
    if start > end:
        raise DomainError("invalid_range", "'from' must be on or before 'to'")
    filters = LeaderboardFilters(round_types=tuple(round_types), gauge=gauge, status=status)
    frames = leaderboard_history_for(session, period, metric, top, start, end, filters)
    return LeaderboardHistoryOut(
        period=period,
        metric=metric,
        frames=[LeaderboardHistoryFrameOut.model_validate(frame) for frame in frames],
    )
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/integration/api/test_leaderboard_history_api.py tests/unit/analytics/competition/test_leaderboard_history.py -v`
Expected: PASS — 12 passed (8 API + 4 unit).

- [ ] **Step 9: Format, then run the full backend gate**

Run:
```bash
cd backend
uv run ruff format src/sunday_clays/analytics/leaderboard_history.py src/sunday_clays/api/routes/leaderboard_history.py tests/unit/analytics/competition/test_leaderboard_history.py tests/integration/api/test_leaderboard_history_api.py
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch
```
Expected: ruff and mypy clean; every test passes (the Plan 04 route matrix now also walks
`GET /api/leaderboards/history`); coverage ≥ 90.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/leaderboard_history.py backend/src/sunday_clays/api/routes/leaderboard_history.py backend/tests/unit/analytics/competition/test_leaderboard_history.py backend/tests/integration/api/test_leaderboard_history_api.py
git commit -F - <<'EOF'
feat(leaderboards): add GET /api/leaderboards/history time machine

One frame per scored event in [from, to], each the top-N rows of the leaderboard
as of that date with the same filters; season points reset on Jan 1.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 5: Leaderboards page with filters, class badges and the time-machine slider (master Plan 09 T5a)

**Files:**
- Create: `frontend/src/features/leaderboards/labels.ts`, `labels.test.ts`
- Create: `frontend/src/features/leaderboards/components/TimeMachine.tsx`, `components/TimeMachine.test.tsx`
- Create: `frontend/src/features/leaderboards/api.ts`
- Create: `frontend/src/features/leaderboards/mocks.ts`
- Create: `frontend/src/features/leaderboards/components/StandingsTable.tsx`
- Create: `frontend/src/features/leaderboards/pages/LeaderboardsPage.tsx`, `pages/LeaderboardsPage.test.tsx`
- Create: `frontend/src/features/leaderboards/routes.tsx`, `routes.test.ts`
- Create: `frontend/e2e/leaderboards.spec.ts`

**Interfaces:**
- Consumes (Plan 07, names per Decision D17): `api`, `unwrap` (`src/api/client.ts`); `paths`
  (`src/api/schema.d.ts`, generated); `useUrlState` (`src/lib/useUrlState.ts`); `useRoundTypes():
  [RoundTypeValue[], (next: RoundTypeValue[]) => void]` (`src/lib/roundTypes.ts`, Plan 07 T4 D12); `NavItem`
  (`src/app/registry.ts`); `Card`, `Chip`, `EmptyState({ title, description?, action?, icon? })`, `Skeleton`
  (`src/components/ui/`, Plan 07 T1); `ChartFrame`; `TabularData`, `TabularRow` (`src/components/charts/types.ts`);
  `barOption(data: TabularData, opts: BarOpts)` with `BarOpts = { x; y; seriesBy?; horizontal?; stack?; yName?;
  labels? }` (`src/components/charts/builders/bar.ts`; one category per distinct label, D17); `renderWithProviders`
  (`src/test/render.tsx`); `server` (`src/test/msw/server.ts`); e2e `test`/`expect` (`e2e/fixtures.ts`).
- Consumes (Plan 09 Tasks 1–2, via `paths`): `GET /api/leaderboards` → `{ period; metric; as_of: string;
  min_rounds_applied: number; n_eligible: number; event_dates: string[]; rows: { rank: number; shooter_id: number;
  display_name: string; status: string | null; value: number; n_rounds: number }[] }`; `GET /api/classes?as_of=` →
  `{ as_of: string; n_active: number; rows: { shooter_id: number; display_name: string; status: string | null; mu:
  number; klass: 'A' | 'B' | 'C' | 'D' }[] }`.
- Produces: route `/leaderboards` and nav `{ label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30,
  mobileTab: true }` (C10); `features/leaderboards/api.ts`: `useLeaderboard(q: LeaderboardQuery)`,
  `useClasses(asOf: string | null)` and types `LeaderboardOut`, `LeaderboardRowOut`, `LeaderboardPeriod`,
  `LeaderboardMetric`, `ClassesOut`, `ShooterStatus`, `LeaderboardQuery`; MSW handlers for `*/api/leaderboards` and
  `*/api/classes`.

**Branch:** `task/09-5a-leaderboards-page`

**Depends on:** Plan 09 T1, T2; Plan 07 T1 (UI kit), T2 (layout, `RoundTypeFilter`), T4 (client, `useUrlState`,
`useRoundTypes`), T5 (builders), T6 (`ChartFrame`); Plan 04 T2 (e2e fixture seed).

- [ ] **Step 0: Confirm the consumed Plan 07 names**

Run (from the worktree root):
```bash
cd frontend
for sym in renderWithProviders server api unwrap useUrlState useRoundTypes ChartFrame barOption TabularData TabularRow NavItem Card Chip EmptyState Skeleton; do
  printf '%-20s %s\n' "$sym" "$(grep -rlE "export (default )?(async )?(function|const|class|type|interface) $sym\b" src | head -1)"
done
grep -nE "export (const|\{).*(test|expect)" e2e/fixtures.ts
sed -n '1,40p' src/lib/useUrlState.ts
sed -n '1,60p' src/lib/roundTypes.ts
grep -nE "description\?:" src/components/ui/EmptyState.tsx
grep -nE "horizontal\?:" src/components/charts/builders/bar.ts
```
Expected: every symbol prints a file path (`useRoundTypes` → `src/lib/roundTypes.ts`); `BarOpts` has `horizontal?:`;
`useUrlState`'s codec has `parse`/`serialize`; `useRoundTypes()` returns a `[roundTypes, setRoundTypes]` tuple bound to the comma-list URL key
`rt` (`?rt=super_sporting`, Plan 07 D14); `EmptyState` has a `description?:` prop (it has no `message` prop);
`e2e/fixtures.ts` exports `test` and `expect`. If a name, prop, tuple or codec shape differs, use the merged
name/shape in this task's files only (never in Plan 07's files) and list the mapping in your report; never
re-implement the `rt` parser here. If `rt` uses another encoding, write that encoding wherever this task's tests and
e2e spec use `rt=super_sporting`.

- [ ] **Step 1: Write the failing e2e spec**

Create `frontend/e2e/leaderboards.spec.ts` (fixture facts: Decision D22):
```ts
import { expect, test } from './fixtures';

test('the Leaderboards nav entry opens the page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Leaderboards' }).first().click();
  await expect(page).toHaveURL(/\/leaderboards/);
  await expect(page.getByRole('heading', { level: 1, name: 'Leaderboards' })).toBeVisible();
});

test('all-time best round ties the four perfect rounds for first', async ({ page }) => {
  await page.goto('/leaderboards?period=all_time&metric=best_score');
  const rows = page.getByRole('table', { name: 'Leaderboard standings' }).locator('tbody tr');
  for (const i of [0, 1, 2, 3]) {
    await expect(rows.nth(i).locator('td').nth(0)).toHaveText('1');
    await expect(rows.nth(i).locator('td').nth(2)).toHaveText('50');
  }
  await expect(rows.nth(4).locator('td').nth(0)).toHaveText('5');
});

test('the time machine replays the 2025 season points final', async ({ page }) => {
  await page.goto('/leaderboards?period=season&metric=season_points&as_of=2025-12-28');
  await expect(page.getByText('As of Dec 28, 2025')).toBeVisible();
  const first = page.getByRole('table', { name: 'Leaderboard standings' }).locator('tbody tr').first();
  await expect(first.locator('td').nth(2)).toHaveText('254');
});

test('the leaders chart offers table and CSV views', async ({ page }) => {
  await page.goto('/leaderboards?period=all_time&metric=wins');
  await expect(page.getByRole('button', { name: /table/i }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /csv/i }).first()).toBeVisible();
});
```

- [ ] **Step 2: Run the e2e spec against the current stack to verify it fails**

Plans 08, 09 and 10 UI tasks run concurrently in Wave 4 and every stack publishes host port 8080, so this task builds
its own image tag (`09-5a`, never `ci`, so a concurrent worktree cannot swap images under this run), runs Compose as its
own project `sc-09-5a` and holds the machine-wide lock directory `/tmp/sunday-clays-e2e.lock` of Plan 08 D24 for exactly
one stack lifetime (Decision D23). The `EXIT` trap tears the stack down and releases the lock even though this run
fails. A lock with no `docker ps --filter publish=8080` container behind it is left over from a crashed run: `rmdir` it.
Run from the worktree root (`rm -rf secrets` deletes only this worktree's generated, gitignored dev secrets so the
known e2e passwords are used):
```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=09-5a
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
rm -rf secrets && VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
(cd frontend && pnpm exec playwright install chromium)
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/leaderboards.spec.ts)
```
(If your shell blocks a foreground `sleep`, run the whole block as a background or monitored command and read its
output when it exits.)
Expected: FAIL in both `mobile` and `desktop` — no `Leaderboards` link and no `/leaderboards` route exist yet; then the
trap removes the stack and the lock (`ls /tmp/sunday-clays-e2e.lock` → no such file).

- [ ] **Step 3: Write the failing label, formatting and codec tests**

Create `frontend/src/features/leaderboards/labels.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import {
  chartRows,
  formatEventDate,
  formatValue,
  metricLabel,
  oneOf,
  optionalDate,
  optionalOneOf,
  snapIndex,
} from './labels';

describe('chartRows', () => {
  it('keeps unique names and suffixes a display name shared by two shooters with the id', () => {
    expect(
      chartRows([
        { shooter_id: 4, display_name: 'Desmond', value: 12 },
        { shooter_id: 7, display_name: 'Ace, Amy', value: 11 },
        { shooter_id: 9, display_name: 'Desmond', value: 11 },
      ]),
    ).toEqual([
      { display_name: 'Jim #4', value: 12 },
      { display_name: 'Ace, Amy', value: 11 },
      { display_name: 'Jim #9', value: 11 },
    ]);
  });
});

describe('formatValue', () => {
  it.each([
    ['avg_score', 43.017, '43.02'],
    ['rating', 38.5, '38.50'],
    ['avg_adjusted', 3.25, '+3.25'],
    ['avg_adjusted', -1.5, '-1.50'],
    ['most_improved', 0, '0.00'],
    ['wins', 62, '62'],
    ['season_points', 191, '191'],
  ] as const)('%s %d → %s', (metric, value, text) => {
    expect(formatValue(metric, value)).toBe(text);
  });
});

describe('labels', () => {
  it('names metrics for headers', () => {
    expect(metricLabel('season_points')).toBe('Season points');
  });

  it('formats ISO event dates without shifting the day', () => {
    expect(formatEventDate('2026-09-27')).toBe('Sep 27, 2026');
    expect(formatEventDate('2025-12-28')).toBe('Dec 28, 2025');
  });
});

describe('snapIndex', () => {
  const dates = ['2026-09-06', '2026-09-13', '2026-09-27'];

  it.each([
    [null, 2],
    ['2026-09-13', 1],
    ['2026-09-20', 1],
    ['2026-01-01', 0],
    ['2027-01-01', 2],
  ])('as_of %s → index %d', (asOf, index) => {
    expect(snapIndex(dates, asOf)).toBe(index);
  });

  it('is 0 without dates', () => {
    expect(snapIndex([], null)).toBe(0);
  });
});

describe('codecs', () => {
  it('oneOf falls back for unknown values', () => {
    const codec = oneOf(['season', 'all_time'] as const, 'season');
    expect(codec.parse('all_time')).toBe('all_time');
    expect(codec.parse('bogus')).toBe('season');
    expect(codec.serialize('all_time')).toBe('all_time');
  });

  it('optionalOneOf maps unknown and empty values to null', () => {
    const codec = optionalOneOf(['member', 'guest'] as const);
    expect(codec.parse('guest')).toBe('guest');
    expect(codec.parse('')).toBeNull();
    expect(codec.serialize(null)).toBe('');
    expect(codec.serialize('member')).toBe('member');
  });

  it('optionalDate accepts only ISO dates', () => {
    expect(optionalDate.parse('2025-12-28')).toBe('2025-12-28');
    expect(optionalDate.parse('12/28/2025')).toBeNull();
    expect(optionalDate.serialize(null)).toBe('');
    expect(optionalDate.serialize('2025-12-28')).toBe('2025-12-28');
  });
});
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/labels.test.ts`
Expected: FAIL — `Failed to resolve import "./labels" from "src/features/leaderboards/labels.test.ts"`.

- [ ] **Step 5: Implement the labels module**

Create `frontend/src/features/leaderboards/labels.ts` (its type-only import of `./api` resolves once Step 13 creates
`api.ts`; Vitest erases type-only imports, and `tsc` runs at Step 19):
```ts
import type { TabularRow } from '../../components/charts/types';
import type { LeaderboardMetric, LeaderboardPeriod, ShooterStatus } from './api';

/** Assignable to Plan 07's `Codec<T>` (`useUrlState`); `parse` here never returns null. */
export interface UrlCodec<T> {
  parse: (raw: string) => T;
  serialize: (value: T) => string;
}

export interface Option<T> {
  value: T;
  label: string;
}

export const PERIODS: readonly Option<LeaderboardPeriod>[] = [
  { value: 'season', label: 'Season' },
  { value: 'rolling_12', label: 'Last 12 months' },
  { value: 'all_time', label: 'All time' },
];

export const METRICS: readonly Option<LeaderboardMetric>[] = [
  { value: 'avg_score', label: 'Average' },
  { value: 'avg_adjusted', label: 'Avg vs field' },
  { value: 'best_score', label: 'Best round' },
  { value: 'wins', label: 'Wins' },
  { value: 'podiums', label: 'Podiums' },
  { value: 'events', label: 'Events' },
  { value: 'rounds', label: 'Rounds' },
  { value: 'rating', label: 'Rating' },
  { value: 'most_improved', label: 'Most improved' },
  { value: 'season_points', label: 'Season points' },
];

export const STATUSES: readonly Option<ShooterStatus>[] = [
  { value: 'member', label: 'Members' },
  { value: 'guest', label: 'Guests' },
  { value: 'deceased', label: 'In memoriam' },
];

export const GAUGES: readonly Option<string>[] = [
  { value: '12 Gauge', label: '12 gauge' },
  { value: '20 Gauge', label: '20 gauge' },
  { value: '28 Gauge', label: '28 gauge' },
  { value: '.410', label: '.410' },
  { value: 'Sub-Gauge', label: 'Sub-gauge' },
  { value: 'SxS', label: 'SxS' },
  { value: 'unspecified', label: 'Not recorded' },
];

/** Rating-based boards ignore the round-type and gauge filters (C7). */
export const RATING_METRICS: readonly LeaderboardMetric[] = ['rating', 'most_improved'];

export function metricLabel(metric: LeaderboardMetric): string {
  return METRICS.find((m) => m.value === metric)?.label ?? metric;
}

/**
 * Bar-chart rows. `barOption` keeps one category per distinct label, so a display name held by two shooters (e.g.
 * first-name-only guests) is charted as `<name> #<id>`, as Plan 07's `race.ts` does (Plan 07 D18).
 */
export function chartRows(
  rows: readonly { shooter_id: number; display_name: string; value: number }[],
): TabularRow[] {
  const names = rows.map((row) => row.display_name);
  return rows.map((row) => ({
    display_name:
      names.indexOf(row.display_name) === names.lastIndexOf(row.display_name)
        ? row.display_name
        : `${row.display_name} #${String(row.shooter_id)}`,
    value: row.value,
  }));
}

export function formatValue(metric: LeaderboardMetric, value: number): string {
  switch (metric) {
    case 'avg_score':
    case 'rating':
      return value.toFixed(2);
    case 'avg_adjusted':
    case 'most_improved':
      return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
    default:
      return String(Math.round(value));
  }
}

export function formatEventDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** Index of the last event date on or before `asOf`; `null` means the latest event. */
export function snapIndex(dates: readonly string[], asOf: string | null): number {
  if (asOf === null) return Math.max(0, dates.length - 1);
  let index = 0;
  dates.forEach((date, i) => {
    if (date <= asOf) index = i;
  });
  return index;
}

export function oneOf<T extends string>(values: readonly T[], fallback: T): UrlCodec<T> {
  const isMember = (raw: string): raw is T => (values as readonly string[]).includes(raw);
  return {
    parse: (raw) => (isMember(raw) ? raw : fallback),
    serialize: (value) => value,
  };
}

export function optionalOneOf<T extends string>(values: readonly T[]): UrlCodec<T | null> {
  const isMember = (raw: string): raw is T => (values as readonly string[]).includes(raw);
  return {
    parse: (raw) => (isMember(raw) ? raw : null),
    serialize: (value) => value ?? '',
  };
}

export const optionalDate: UrlCodec<string | null> = {
  parse: (raw) => (/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null),
  serialize: (value) => value ?? '',
};
```

- [ ] **Step 6: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/labels.test.ts`
Expected: PASS — 19 tests passed.

- [ ] **Step 7: Write the failing time-machine tests**

Create `frontend/src/features/leaderboards/components/TimeMachine.test.tsx`:
```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TimeMachine } from './TimeMachine';

const DATES = ['2026-09-06', '2026-09-13', '2026-09-27'];

describe('TimeMachine', () => {
  it('sits on the latest event when no as_of is chosen', () => {
    render(<TimeMachine dates={DATES} asOf={null} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Time machine')).toHaveValue('2');
    expect(screen.getByText('Latest', { selector: 'output' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Latest' })).toBeDisabled();
  });

  it('snaps a between-events as_of to the previous event', () => {
    render(<TimeMachine dates={DATES} asOf="2026-09-20" onChange={vi.fn()} />);
    expect(screen.getByLabelText('Time machine')).toHaveValue('1');
    expect(screen.getByText('As of Sep 13, 2026')).toBeInTheDocument();
  });

  it('reports the event date under the slider', () => {
    const onChange = vi.fn();
    render(<TimeMachine dates={DATES} asOf={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Time machine'), { target: { value: '0' } });
    expect(onChange).toHaveBeenLastCalledWith('2026-09-06');
  });

  it('reports the newest event date from the slider and null only from Latest', () => {
    const onChange = vi.fn();
    render(<TimeMachine dates={DATES} asOf="2026-09-06" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Time machine'), { target: { value: '2' } });
    expect(onChange).toHaveBeenLastCalledWith('2026-09-27');
    onChange.mockClear();
    fireEvent.click(screen.getByRole('button', { name: 'Latest' }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('renders nothing without event dates', () => {
    const { container } = render(<TimeMachine dates={[]} asOf={null} onChange={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 8: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/components/TimeMachine.test.tsx`
Expected: FAIL — `Failed to resolve import "./TimeMachine"`.

- [ ] **Step 9: Implement the time machine**

Create `frontend/src/features/leaderboards/components/TimeMachine.tsx`:
```tsx
import { formatEventDate, snapIndex } from '../labels';

export interface TimeMachineProps {
  /** Every has_scores event date, ascending (LeaderboardOut.event_dates). */
  dates: readonly string[];
  /** Selected as_of; null means "latest". */
  asOf: string | null;
  onChange: (asOf: string | null) => void;
}

export function TimeMachine({ dates, asOf, onChange }: TimeMachineProps) {
  const first = dates[0];
  if (first === undefined) return null;
  const last = dates.length - 1;
  const index = snapIndex(dates, asOf);
  const shown = dates[index] ?? first;
  return (
    <div className="flex flex-col gap-2 rounded-card bg-elevated p-3">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor="leaderboard-as-of" className="text-sm text-text-muted">
          Time machine
        </label>
        <output htmlFor="leaderboard-as-of" className="font-medium">
          {asOf === null ? 'Latest' : `As of ${formatEventDate(shown)}`}
        </output>
      </div>
      <input
        id="leaderboard-as-of"
        type="range"
        min={0}
        max={last}
        step={1}
        value={index}
        aria-valuetext={formatEventDate(shown)}
        onChange={(event) => {
          // Always the event under the thumb (D21): only "Latest" clears as_of to today.
          onChange(dates[Number(event.currentTarget.value)] ?? null);
        }}
        className="min-h-11 w-full accent-primary"
      />
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>{formatEventDate(first)}</span>
        <button
          type="button"
          onClick={() => {
            onChange(null);
          }}
          disabled={asOf === null}
          className="min-h-11 rounded-button px-3 text-accent disabled:opacity-40"
        >
          Latest
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 10: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/components/TimeMachine.test.tsx`
Expected: PASS — 5 tests passed.

- [ ] **Step 11: Write the MSW fixtures and the failing page tests**

Create `frontend/src/features/leaderboards/mocks.ts` (merged into the global MSW handlers by glob, C10):
```ts
import { http, HttpResponse } from 'msw';

import type { ClassesOut, LeaderboardOut } from './api';

export const leaderboardFixture: LeaderboardOut = {
  period: 'season',
  metric: 'avg_score',
  as_of: '2026-09-27',
  min_rounds_applied: 5,
  n_eligible: 3,
  event_dates: ['2026-09-06', '2026-09-13', '2026-09-27'],
  rows: [
    {
      rank: 1,
      shooter_id: 7,
      display_name: 'Ace, Amy',
      status: 'member',
      value: 45.02,
      n_rounds: 12,
    },
    {
      rank: 2,
      shooter_id: 3,
      display_name: 'Bee, Bob',
      status: 'member',
      value: 44.5,
      n_rounds: 20,
    },
    { rank: 2, shooter_id: 9, display_name: 'Cy, Cal', status: 'guest', value: 44.5, n_rounds: 9 },
  ],
};

export const classesFixture: ClassesOut = {
  as_of: '2026-09-27',
  n_active: 2,
  rows: [
    { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', mu: 44.1, klass: 'A' },
    { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', mu: 41.9, klass: 'B' },
  ],
};

export const handlers = [
  http.get('*/api/leaderboards', () => HttpResponse.json(leaderboardFixture)),
  http.get('*/api/classes', () => HttpResponse.json(classesFixture)),
];
```

Create `frontend/src/features/leaderboards/pages/LeaderboardsPage.test.tsx`:
```tsx
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { LeaderboardOut } from '../api';
import { leaderboardFixture } from '../mocks';
import { LeaderboardsPage } from './LeaderboardsPage';

function captureRequests(body: LeaderboardOut = leaderboardFixture): URL[] {
  const seen: URL[] = [];
  server.use(
    http.get('*/api/leaderboards', ({ request }) => {
      seen.push(new URL(request.url));
      return HttpResponse.json(body);
    }),
  );
  return seen;
}

function lastRequest(seen: URL[]): URLSearchParams {
  const last = seen.at(-1);
  if (last === undefined) throw new Error('no /api/leaderboards request yet');
  return last.searchParams;
}

async function standingsRows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole('table', { name: 'Leaderboard standings' });
  return within(table).getAllByRole('row').slice(1);
}

function cellTexts(row: HTMLElement | undefined): (string | null)[] {
  if (row === undefined) throw new Error('row missing');
  return within(row)
    .getAllByRole('cell')
    .map((cell) => cell.textContent);
}

describe('LeaderboardsPage', () => {
  it('lists standings with shared ranks, formatted values and class badges', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    expect(await screen.findByLabelText('Class B')).toBeInTheDocument();
    const rows = await standingsRows();
    expect(rows.map((row) => cellTexts(row)[0])).toEqual(['1', '2', '2']);
    expect(cellTexts(rows[0])).toEqual(['1', 'Ace, AmyA', '45.02', '12']);
    expect(within(rows[2] ?? document.body).queryByLabelText(/^Class/)).toBeNull();
    expect(screen.getByRole('link', { name: /Ace, Amy/ })).toHaveAttribute('href', '/shooters/7');
  });

  it('sends period, metric, gauge and status from the controls', async () => {
    const seen = captureRequests();
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    expect(lastRequest(seen).get('period')).toBe('season');
    expect(lastRequest(seen).get('metric')).toBe('avg_score');
    await user.click(screen.getByRole('button', { name: 'All time' }));
    await user.click(screen.getByRole('button', { name: 'Wins' }));
    await user.selectOptions(screen.getByLabelText('Gauge'), 'Not recorded');
    await user.selectOptions(screen.getByLabelText('Shooters'), 'Members');
    await waitFor(() => {
      expect(lastRequest(seen).get('status')).toBe('member');
    });
    const params = lastRequest(seen);
    expect(params.get('period')).toBe('all_time');
    expect(params.get('metric')).toBe('wins');
    expect(params.get('gauge')).toBe('unspecified');
  });

  it('forwards the global round-type filter', async () => {
    const seen = captureRequests();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?rt=super_sporting' });
    await standingsRows();
    expect(lastRequest(seen).getAll('round_type')).toEqual(['super_sporting']);
  });

  it('shows the minimum-rounds note', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    expect(await screen.findByText('Needs ≥5 rounds · 3 qualify')).toBeInTheDocument();
  });

  it('hides the minimum-rounds note when one round is enough', async () => {
    captureRequests({ ...leaderboardFixture, min_rounds_applied: 1 });
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?metric=wins' });
    await standingsRows();
    expect(screen.queryByText(/^Needs ≥/)).toBeNull();
  });

  it('moves the time machine to an earlier event and back to latest', async () => {
    const seen = captureRequests();
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    fireEvent.change(screen.getByLabelText('Time machine'), { target: { value: '0' } });
    await waitFor(() => {
      expect(lastRequest(seen).get('as_of')).toBe('2026-09-06');
    });
    expect(screen.getByText('As of Sep 6, 2026')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Latest' }));
    await waitFor(() => {
      expect(lastRequest(seen).get('as_of')).toBeNull();
    });
  });

  it('explains that ratings ignore round-type and gauge filters', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?metric=rating&gauge=SxS' });
    expect(
      await screen.findByText('Ratings ignore the round-type and gauge filters.'),
    ).toBeInTheDocument();
  });

  it('shows an empty state when nobody qualifies', async () => {
    captureRequests({ ...leaderboardFixture, rows: [], n_eligible: 0 });
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    expect(await screen.findByText('No one qualifies yet')).toBeInTheDocument();
    expect(screen.getByText('Needs ≥5 rounds · 0 qualify')).toBeInTheDocument();
  });

  it('shows an error state when the API fails', async () => {
    server.use(http.get('*/api/leaderboards', () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    expect(await screen.findByText('Leaderboard unavailable')).toBeInTheDocument();
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(1);
  });
});
```

- [ ] **Step 12: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/pages/LeaderboardsPage.test.tsx`
Expected: FAIL — `Failed to resolve import "./LeaderboardsPage"`.

- [ ] **Step 13: Implement the hooks, the standings table and the page**

Create `frontend/src/features/leaderboards/api.ts`:
```ts
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type LeaderboardOut = JsonOf<paths['/api/leaderboards']['get']>;
export type LeaderboardRowOut = LeaderboardOut['rows'][number];
export type LeaderboardPeriod = LeaderboardOut['period'];
export type LeaderboardMetric = LeaderboardOut['metric'];
export type ClassesOut = JsonOf<paths['/api/classes']['get']>;
export type ShooterStatus = 'member' | 'guest' | 'deceased';

export interface LeaderboardQuery {
  period: LeaderboardPeriod;
  metric: LeaderboardMetric;
  asOf: string | null;
  gauge: string | null;
  status: ShooterStatus | null;
}

export function useLeaderboard({ period, metric, asOf, gauge, status }: LeaderboardQuery) {
  const [roundTypes] = useRoundTypes();
  const query = {
    period,
    metric,
    as_of: asOf ?? undefined,
    gauge: gauge ?? undefined,
    status: status ?? undefined,
    round_type: roundTypes.length > 0 ? roundTypes : undefined,
  };
  return useQuery({
    queryKey: ['/api/leaderboards', query],
    queryFn: () => unwrap(api.GET('/api/leaderboards', { params: { query } })),
    placeholderData: keepPreviousData,
  });
}

export function useClasses(asOf: string | null) {
  const query = { as_of: asOf ?? undefined };
  return useQuery({
    queryKey: ['/api/classes', query],
    queryFn: () => unwrap(api.GET('/api/classes', { params: { query } })),
  });
}
```

Create `frontend/src/features/leaderboards/components/StandingsTable.tsx`:
```tsx
import { Link } from 'react-router';

import type { LeaderboardMetric, LeaderboardRowOut } from '../api';
import { formatValue, metricLabel } from '../labels';

export interface StandingsTableProps {
  rows: readonly LeaderboardRowOut[];
  metric: LeaderboardMetric;
  /** shooter_id → class letter from GET /api/classes at the same as_of. */
  classes: ReadonlyMap<number, string>;
}

export function StandingsTable({ rows, metric, classes }: StandingsTableProps) {
  return (
    <table aria-label="Leaderboard standings" className="w-full text-left text-sm">
      <thead className="text-text-muted">
        <tr>
          <th scope="col" className="w-12 py-2">
            #
          </th>
          <th scope="col">Shooter</th>
          <th scope="col" className="text-right">
            {metricLabel(metric)}
          </th>
          <th scope="col" className="text-right">
            Rounds
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const klass = classes.get(row.shooter_id);
          return (
            <tr key={row.shooter_id} className="border-t border-outline-variant">
              <td className="py-2 tabular-nums">{row.rank}</td>
              <td>
                <Link
                  to={`/shooters/${String(row.shooter_id)}`}
                  className="inline-flex min-h-11 items-center gap-2 hover:text-accent"
                >
                  {row.display_name}
                  {klass !== undefined && (
                    <span
                      aria-label={`Class ${klass}`}
                      className="rounded-button bg-primary-container px-2 text-xs font-bold"
                    >
                      {klass}
                    </span>
                  )}
                </Link>
              </td>
              <td className="text-right tabular-nums">{formatValue(metric, row.value)}</td>
              <td className="text-right tabular-nums text-text-muted">{row.n_rounds}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

Create `frontend/src/features/leaderboards/pages/LeaderboardsPage.tsx`:
```tsx
import { useMemo } from 'react';

import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRoundTypes } from '../../../lib/roundTypes';
import { useUrlState } from '../../../lib/useUrlState';
import {
  type LeaderboardMetric,
  type LeaderboardOut,
  type LeaderboardPeriod,
  type ShooterStatus,
  useClasses,
  useLeaderboard,
} from '../api';
import { StandingsTable } from '../components/StandingsTable';
import { TimeMachine } from '../components/TimeMachine';
import {
  GAUGES,
  METRICS,
  PERIODS,
  RATING_METRICS,
  STATUSES,
  chartRows,
  metricLabel,
  oneOf,
  optionalDate,
  optionalOneOf,
} from '../labels';

const PERIOD_CODEC = oneOf(
  PERIODS.map((p) => p.value),
  'season',
);
const METRIC_CODEC = oneOf(
  METRICS.map((m) => m.value),
  'avg_score',
);
const GAUGE_CODEC = optionalOneOf(GAUGES.map((g) => g.value));
const STATUS_CODEC = optionalOneOf(STATUSES.map((s) => s.value));
const CHART_TOP = 10;

/** `undefined` (not null) when one round is enough: EmptyState renders its description for any other value. */
function needsNote(board: LeaderboardOut): string | undefined {
  return board.min_rounds_applied > 1
    ? `Needs ≥${String(board.min_rounds_applied)} rounds · ${String(board.n_eligible)} qualify`
    : undefined;
}

export function LeaderboardsPage() {
  const [period, setPeriod] = useUrlState<LeaderboardPeriod>('period', PERIOD_CODEC, 'season');
  const [metric, setMetric] = useUrlState<LeaderboardMetric>('metric', METRIC_CODEC, 'avg_score');
  const [asOf, setAsOf] = useUrlState<string | null>('as_of', optionalDate, null);
  const [gauge, setGauge] = useUrlState<string | null>('gauge', GAUGE_CODEC, null);
  const [status, setStatus] = useUrlState<ShooterStatus | null>('status', STATUS_CODEC, null);
  const [roundTypes] = useRoundTypes();
  const board = useLeaderboard({ period, metric, asOf, gauge, status });
  const classes = useClasses(asOf);
  const data = board.data;

  const classMap = useMemo(
    () => new Map((classes.data?.rows ?? []).map((row) => [row.shooter_id, row.klass])),
    [classes.data],
  );
  const chart = useMemo<TabularData>(
    () => ({
      columns: [
        { key: 'display_name', label: 'Shooter', type: 'string' },
        { key: 'value', label: metricLabel(metric), type: 'number' },
      ],
      rows: chartRows((data?.rows ?? []).slice(0, CHART_TOP)),
    }),
    [data, metric],
  );
  const ratingIgnoresFilters =
    RATING_METRICS.includes(metric) && (gauge !== null || roundTypes.length > 0);

  let content;
  if (board.isError) {
    content = <EmptyState title="Leaderboard unavailable" description="Try again in a moment." />;
  } else if (data === undefined) {
    content = <Skeleton className="h-64" />;
  } else if (data.rows.length === 0) {
    content = <EmptyState title="No one qualifies yet" description={needsNote(data)} />;
  } else {
    const note = needsNote(data);
    content = (
      <>
        {note !== undefined && <p className="text-sm text-text-muted">{note}</p>}
        <ChartFrame
          title={`Top ${String(chart.rows.length)} · ${metricLabel(metric)}`}
          option={barOption(chart, { x: 'display_name', y: ['value'], horizontal: true })}
          columns={chart.columns}
          rows={chart.rows}
          csvName={`leaderboard-${period}-${metric}`}
          ariaLabel={`${metricLabel(metric)} leaders`}
          urlKey="lb-chart"
        />
        <Card>
          <StandingsTable rows={data.rows} metric={metric} classes={classMap} />
        </Card>
      </>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-bold">Leaderboards</h1>
      <div role="group" aria-label="Period" className="flex flex-wrap gap-2">
        {PERIODS.map((p) => (
          <Chip
            key={p.value}
            selected={p.value === period}
            onClick={() => {
              setPeriod(p.value);
            }}
          >
            {p.label}
          </Chip>
        ))}
      </div>
      <div role="group" aria-label="Metric" className="flex gap-2 overflow-x-auto pb-1">
        {METRICS.map((m) => (
          <Chip
            key={m.value}
            selected={m.value === metric}
            onClick={() => {
              setMetric(m.value);
            }}
          >
            {m.label}
          </Chip>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Gauge
          <select
            value={gauge ?? ''}
            onChange={(event) => {
              setGauge(GAUGE_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            <option value="">All gauges</option>
            {GAUGES.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Shooters
          <select
            value={status ?? ''}
            onChange={(event) => {
              setStatus(STATUS_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            <option value="">Everyone</option>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <TimeMachine dates={data?.event_dates ?? []} asOf={asOf} onChange={setAsOf} />
      {ratingIgnoresFilters && (
        <p role="note" className="text-sm text-text-muted">
          Ratings ignore the round-type and gauge filters.
        </p>
      )}
      {content}
    </div>
  );
}
```

- [ ] **Step 14: Run the page tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards`
Expected: PASS — 34 tests passed (19 labels + 5 time machine + 10 page).

- [ ] **Step 15: Write the failing route test**

Create `frontend/src/features/leaderboards/routes.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import { LeaderboardsPage } from './pages/LeaderboardsPage';
import { routes } from './routes';

describe('leaderboards routes', () => {
  it('lazily loads LeaderboardsPage at /leaderboards', async () => {
    const [route] = routes;
    expect(route?.path).toBe('/leaderboards');
    if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
    await expect(route.lazy()).resolves.toMatchObject({ Component: LeaderboardsPage });
  });
});
```

- [ ] **Step 16: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/routes.test.ts`
Expected: FAIL — `Failed to resolve import "./routes"`.

- [ ] **Step 17: Register the route and the nav entry**

Create `frontend/src/features/leaderboards/routes.tsx` (collected by `app/registry.ts`; `router.tsx` is never edited,
C10):
```tsx
import { Trophy } from 'lucide-react';
import type { RouteObject } from 'react-router';

import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/leaderboards',
    lazy: async () => {
      const { LeaderboardsPage } = await import('./pages/LeaderboardsPage');
      return { Component: LeaderboardsPage };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30, mobileTab: true },
];
```

- [ ] **Step 18: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/leaderboards/routes.test.ts`
Expected: PASS — 1 test passed.

- [ ] **Step 19: Format, then run the full frontend gate**

Run:
```bash
cd frontend
pnpm exec prettier --write src/features/leaderboards e2e/leaderboards.spec.ts
pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage
```
Expected: eslint (0 warnings), `tsc` and prettier clean — `typecheck` regenerates `schema.d.ts` from the backend, so a
missing or renamed `LeaderboardOut`/`ClassesOut` field is a cross-plan mismatch to report, not to rename locally; every
Vitest file passes, including Plan 07's registry test (Leaderboards is one of the four mobile tabs, order 30); coverage
≥ 90% lines and branches for the whole frontend.

- [ ] **Step 20: Rebuild both images and run the e2e spec to verify it passes**

Run from the worktree root: the same tag and Compose project as Step 2 (whose `secrets/` are reused as is), both
images rebuilt first, then a fresh stack under the machine-wide e2e lock (Decision D23; the `setup` project re-seeds the
fixtures), torn down by the `EXIT` trap:
```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=09-5a
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/leaderboards.spec.ts)
```
(The foreground-`sleep` note from Step 2 applies here too.)
Expected: all 8 `leaderboards.spec.ts` tests pass (4 tests × `mobile` and `desktop`); Playwright's summary also counts
the `setup` project's tests as passed, so the total is higher than 8; 0 failed. The trap then removes the stack and
the lock.

- [ ] **Step 21: Commit**

```bash
git add frontend/src/features/leaderboards frontend/e2e/leaderboards.spec.ts
git commit -F - <<'EOF'
feat(leaderboards): add leaderboards page with time-machine slider

Period/metric chips, gauge and status filters, the global round-type filter,
class badges, a "Needs >=N rounds" note and a top-10 chart, all in the URL.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 6: Records page (master Plan 09 T5b)

**Files:**
- Create: `frontend/src/features/records/format.ts`, `format.test.ts`
- Create: `frontend/src/features/records/api.ts`
- Create: `frontend/src/features/records/mocks.ts`
- Create: `frontend/src/features/records/components/RecordSections.tsx`
- Create: `frontend/src/features/records/pages/RecordsPage.tsx`, `pages/RecordsPage.test.tsx`
- Create: `frontend/src/features/records/routes.tsx`, `routes.test.ts`
- Create: `frontend/e2e/records.spec.ts`

This is a separate feature folder from Task 5, so the two never touch the same file (master T5b).

**Interfaces:**
- Consumes (Plan 07, names per Decision D17): `api`, `unwrap`, `paths`, `useRoundTypes(): [RoundTypeValue[], (next:
  RoundTypeValue[]) => void]` (`src/lib/roundTypes.ts`), `NavItem`, `Card`, `EmptyState({ title, description?,
  action?, icon? })`, `Skeleton`, `ChartFrame`, `TabularData`, `TabularRow`, `barOption(data: TabularData, opts:
  BarOpts)` (`horizontal?` for shooter names; one category per distinct label, D17), `renderWithProviders`, `server`,
  e2e `test`/`expect`.
- Consumes (Plan 09 Task 3, via `paths`): `GET /api/records?round_type=` → `{ as_of: string; highest_scores:
  RecordRound[]; perfect_rounds: RecordRound[]; biggest_adjusted: RecordRound[]; biggest_jumps: { rank: number;
  shooter_id: number; display_name: string; event_date: string; prev_event_date: string; from_score: number; to_score:
  number; value: number }[]; most_events: RecordShooter[]; longest_streaks: RecordShooter[]; highest_ratings:
  RecordRound[] }` with `RecordRound = { rank: number; shooter_id: number; display_name: string; event_date: string;
  value: number }` and `RecordShooter = { rank: number; shooter_id: number; display_name: string; value: number }`.
- Produces: route `/records` and nav `{ label: 'Records', path: '/records', icon: Medal, order: 120 }` (C10);
  `features/records/api.ts`: `useRecords()` and types `RecordsOut`, `RecordRoundOut`, `RecordJumpOut`,
  `RecordShooterOut`, `RecordRatingOut`; MSW handler for `*/api/records`.

**Branch:** `task/09-5b-records-page`

**Depends on:** Plan 09 T3; Plan 07 T1, T2, T4 (`useRoundTypes`), T5, T6; Plan 04 T2 (e2e fixture seed).

- [ ] **Step 0: Confirm the consumed Plan 07 names**

Run (from the worktree root):
```bash
cd frontend
for sym in renderWithProviders server api unwrap useRoundTypes ChartFrame barOption TabularData TabularRow NavItem Card EmptyState Skeleton; do
  printf '%-20s %s\n' "$sym" "$(grep -rlE "export (default )?(async )?(function|const|class|type|interface) $sym\b" src | head -1)"
done
grep -nE "export (const|\{).*(test|expect)" e2e/fixtures.ts
sed -n '1,60p' src/lib/roundTypes.ts
grep -nE "description\?:" src/components/ui/EmptyState.tsx
grep -nE "horizontal\?:" src/components/charts/builders/bar.ts
```
Expected: every symbol prints a file path (`useRoundTypes` → `src/lib/roundTypes.ts`); `BarOpts` has `horizontal?:`;
`useRoundTypes()` returns a `[roundTypes, setRoundTypes]` tuple bound to the comma-list URL key `rt` (Plan 07 D14);
`EmptyState` has a
`description?:` prop (no `message` prop); `e2e/fixtures.ts` exports `test` and `expect`. If a name, prop or tuple
shape differs, use the merged name/shape in this task's files only and list the mapping in your report; never
re-implement the `rt` parser here. If `rt` uses another encoding, write that encoding wherever this task's tests and
e2e spec use `rt=super_sporting`.

- [ ] **Step 1: Write the failing e2e spec**

Create `frontend/e2e/records.spec.ts` (fixture facts: Decision D22):
```ts
import { expect, test } from './fixtures';

test('records list the six perfect rounds and the top score', async ({ page }) => {
  await page.goto('/records');
  await expect(page.getByRole('heading', { level: 1, name: 'Records' })).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Perfect 50s' }).getByRole('listitem'),
  ).toHaveCount(6);
  const top = page.getByRole('table', { name: 'Highest scores' }).locator('tbody tr').first();
  await expect(top.locator('td').nth(2)).toHaveText('50');
  await expect(
    page.getByRole('region', { name: 'Most events' }).getByRole('button', { name: /csv/i }),
  ).toBeVisible();
});

test('the super sporting filter narrows records to the two super sporting Sundays', async ({
  page,
}) => {
  await page.goto('/records?rt=super_sporting');
  await expect(
    page.getByRole('region', { name: 'Perfect 50s' }).getByText('None yet'),
  ).toBeVisible();
  const top = page.getByRole('table', { name: 'Highest scores' }).locator('tbody tr').first();
  await expect(top.locator('td').nth(2)).toHaveText('48');
});
```

- [ ] **Step 2: Run the e2e spec against the current stack to verify it fails**

Plans 08, 09 and 10 UI tasks run concurrently in Wave 4 and every stack publishes host port 8080, so this task builds
its own image tag (`09-5b`, never `ci`), runs Compose as its own project `sc-09-5b` and holds the machine-wide lock
directory `/tmp/sunday-clays-e2e.lock` of Plan 08 D24 for exactly one stack lifetime (Decision D23). The `EXIT` trap
tears the stack down and releases the lock even though this run fails. A lock with no `docker ps --filter
publish=8080` container behind it is left over from a crashed run: `rmdir` it. Run from the worktree root (`rm -rf
secrets` deletes only this worktree's generated, gitignored dev secrets):
```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=09-5b
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
rm -rf secrets && VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
(cd frontend && pnpm exec playwright install chromium)
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/records.spec.ts)
```
(If your shell blocks a foreground `sleep`, run the whole block as a background or monitored command and read its
output when it exits.)
Expected: FAIL in both `mobile` and `desktop` — no `Records` heading (no `/records` route yet); then the trap removes the
stack and the lock.

- [ ] **Step 3: Write the failing formatting tests**

Create `frontend/src/features/records/format.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import { chartRows, formatEventDate, formatRating, formatSigned } from './format';

describe('chartRows', () => {
  it('keeps unique names and suffixes a display name shared by two shooters with the id', () => {
    expect(
      chartRows([
        { shooter_id: 4, display_name: 'Desmond', value: 12 },
        { shooter_id: 7, display_name: 'Ace, Amy', value: 11 },
        { shooter_id: 9, display_name: 'Desmond', value: 11 },
      ]),
    ).toEqual([
      { display_name: 'Jim #4', value: 12 },
      { display_name: 'Ace, Amy', value: 11 },
      { display_name: 'Jim #9', value: 11 },
    ]);
  });
});

describe('records formatting', () => {
  it('formats ISO dates without shifting the day', () => {
    expect(formatEventDate('2021-01-17')).toBe('Jan 17, 2021');
  });

  it.each([
    [18, '+18.0'],
    [-5.5, '-5.5'],
    [0, '0.0'],
  ])('signs %d as %s', (value, text) => {
    expect(formatSigned(value)).toBe(text);
  });

  it('shows ratings to one decimal', () => {
    expect(formatRating(47.256)).toBe('47.3');
  });
});
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/records/format.test.ts`
Expected: FAIL — `Failed to resolve import "./format"`.

- [ ] **Step 5: Implement the formatting helpers**

Create `frontend/src/features/records/format.ts`:
```ts
import type { TabularRow } from '../../components/charts/types';

/**
 * Bar-chart rows. `barOption` keeps one category per distinct label, so a display name held by two shooters (e.g.
 * first-name-only guests) is charted as `<name> #<id>`, as Plan 07's `race.ts` does (Plan 07 D18).
 */
export function chartRows(
  rows: readonly { shooter_id: number; display_name: string; value: number }[],
): TabularRow[] {
  const names = rows.map((row) => row.display_name);
  return rows.map((row) => ({
    display_name:
      names.indexOf(row.display_name) === names.lastIndexOf(row.display_name)
        ? row.display_name
        : `${row.display_name} #${String(row.shooter_id)}`,
    value: row.value,
  }));
}

export function formatEventDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function formatSigned(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
}

export function formatRating(value: number): string {
  return value.toFixed(1);
}
```

- [ ] **Step 6: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/records/format.test.ts`
Expected: PASS — 6 tests passed.

- [ ] **Step 7: Write the MSW fixtures and the failing page tests**

Create `frontend/src/features/records/mocks.ts`:
```ts
import { http, HttpResponse } from 'msw';

import type { RecordsOut } from './api';

export const recordsFixture: RecordsOut = {
  as_of: '2026-09-27',
  highest_scores: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2021-01-17', value: 50 },
    { rank: 1, shooter_id: 3, display_name: 'Bee, Bob', event_date: '2022-12-04', value: 50 },
    { rank: 3, shooter_id: 9, display_name: 'Cy, Cal', event_date: '2021-03-28', value: 49 },
  ],
  perfect_rounds: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2021-01-17', value: 50 },
    { rank: 1, shooter_id: 3, display_name: 'Bee, Bob', event_date: '2022-12-04', value: 50 },
  ],
  biggest_adjusted: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2026-06-07', value: 18 },
  ],
  biggest_jumps: [
    {
      rank: 1,
      shooter_id: 9,
      display_name: 'Cy, Cal',
      event_date: '2021-03-21',
      prev_event_date: '2021-03-14',
      from_score: 11,
      to_score: 41,
      value: 30,
    },
  ],
  most_events: [
    { rank: 1, shooter_id: 3, display_name: 'Bee, Bob', value: 285 },
    { rank: 2, shooter_id: 7, display_name: 'Ace, Amy', value: 267 },
  ],
  longest_streaks: [{ rank: 1, shooter_id: 3, display_name: 'Bee, Bob', value: 56 }],
  highest_ratings: [
    { rank: 1, shooter_id: 7, display_name: 'Ace, Amy', event_date: '2024-03-10', value: 47.256 },
  ],
};

export const handlers = [http.get('*/api/records', () => HttpResponse.json(recordsFixture))];
```

Create `frontend/src/features/records/pages/RecordsPage.test.tsx`:
```tsx
import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { recordsFixture } from '../mocks';
import { RecordsPage } from './RecordsPage';

describe('RecordsPage', () => {
  it('shows every record section', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    expect(await screen.findByRole('heading', { name: 'Highest scores' })).toBeInTheDocument();
    for (const title of [
      'Perfect 50s',
      'Biggest day vs the field',
      'Biggest week-over-week jumps',
      'Most events',
      'Longest streaks',
      'Highest rating ever',
    ]) {
      expect(screen.getByRole('region', { name: title })).toBeInTheDocument();
    }
  });

  it('ranks highest scores with shared ranks and links shooter and event', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const table = await screen.findByRole('table', { name: 'Highest scores' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell')[0]?.textContent)).toEqual([
      '1',
      '1',
      '3',
    ]);
    const first = rows[0] ?? table;
    expect(within(first).getByRole('link', { name: 'Ace, Amy' })).toHaveAttribute(
      'href',
      '/shooters/7',
    );
    expect(within(first).getByRole('link', { name: 'Jan 17, 2021' })).toHaveAttribute(
      'href',
      '/events/2021-01-17',
    );
  });

  it('lists every perfect round and formats the other records', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const perfect = await screen.findByRole('region', { name: 'Perfect 50s' });
    expect(within(perfect).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('+18.0')).toBeInTheDocument();
    expect(screen.getByText('11 → 41 (+30)')).toBeInTheDocument();
    expect(screen.getByText('47.3')).toBeInTheDocument();
  });

  it('forwards the global round-type filter', async () => {
    const seen: URL[] = [];
    server.use(
      http.get('*/api/records', ({ request }) => {
        seen.push(new URL(request.url));
        return HttpResponse.json(recordsFixture);
      }),
    );
    renderWithProviders(<RecordsPage />, { route: '/records?rt=super_sporting' });
    await screen.findByRole('table', { name: 'Highest scores' });
    expect(seen.at(-1)?.searchParams.getAll('round_type')).toEqual(['super_sporting']);
  });

  it('says None yet for empty record lists', async () => {
    server.use(
      http.get('*/api/records', () =>
        HttpResponse.json({
          ...recordsFixture,
          perfect_rounds: [],
          most_events: [],
          biggest_jumps: [],
          highest_ratings: [],
          highest_scores: [],
          biggest_adjusted: [],
          longest_streaks: [],
        }),
      ),
    );
    renderWithProviders(<RecordsPage />, { route: '/records' });
    const perfect = await screen.findByRole('region', { name: 'Perfect 50s' });
    expect(within(perfect).getByText('None yet')).toBeInTheDocument();
    expect(screen.getAllByText('None yet')).toHaveLength(7);
  });

  it('shows an error state when the API fails', async () => {
    server.use(http.get('*/api/records', () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<RecordsPage />, { route: '/records' });
    expect(await screen.findByText('Records unavailable')).toBeInTheDocument();
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<RecordsPage />, { route: '/records' });
    await screen.findByRole('region', { name: 'Most events' });
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(2);
  });
});
```

- [ ] **Step 8: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/records/pages/RecordsPage.test.tsx`
Expected: FAIL — `Failed to resolve import "./RecordsPage"`.

- [ ] **Step 9: Implement the hook, the record sections and the page**

Create `frontend/src/features/records/api.ts`:
```ts
import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type RecordsOut = JsonOf<paths['/api/records']['get']>;
export type RecordRoundOut = RecordsOut['highest_scores'][number];
export type RecordJumpOut = RecordsOut['biggest_jumps'][number];
export type RecordShooterOut = RecordsOut['most_events'][number];
export type RecordRatingOut = RecordsOut['highest_ratings'][number];

export function useRecords() {
  const [roundTypes] = useRoundTypes();
  const query = { round_type: roundTypes.length > 0 ? roundTypes : undefined };
  return useQuery({
    queryKey: ['/api/records', query],
    queryFn: () => unwrap(api.GET('/api/records', { params: { query } })),
  });
}
```

Create `frontend/src/features/records/components/RecordSections.tsx`:
```tsx
import type { ReactNode } from 'react';
import { Link } from 'react-router';

import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import type { RecordJumpOut, RecordRatingOut, RecordRoundOut, RecordShooterOut } from '../api';
import { chartRows, formatEventDate, formatRating } from '../format';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-4">
      <section aria-label={title} className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">{title}</h2>
        {children}
      </section>
    </Card>
  );
}

function NoneYet() {
  return <p className="text-sm text-text-muted">None yet</p>;
}

/**
 * Round records carry no ordinal, and one shooter can hold two same-day rounds in a list (the fixture has 39 second
 * rounds, e.g. two 40/40 rounds on 2026-08-30), so the list position keeps the React key unique.
 */
function rowKey(index: number, shooterId: number, eventDate: string): string {
  return `${String(index)}-${String(shooterId)}-${eventDate}`;
}

function ShooterLink({ id, name }: { id: number; name: string }) {
  return (
    <Link
      to={`/shooters/${String(id)}`}
      className="inline-flex min-h-11 items-center hover:text-accent"
    >
      {name}
    </Link>
  );
}

function EventLink({ date }: { date: string }) {
  return (
    <Link to={`/events/${date}`} className="inline-flex min-h-11 items-center hover:text-accent">
      {formatEventDate(date)}
    </Link>
  );
}

export function RoundRecordTable({
  title,
  valueLabel,
  rows,
  format,
}: {
  title: string;
  valueLabel: string;
  rows: readonly RecordRoundOut[];
  format: (value: number) => string;
}) {
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <table aria-label={title} className="w-full text-left text-sm">
          <thead className="text-text-muted">
            <tr>
              <th scope="col">#</th>
              <th scope="col">Shooter</th>
              <th scope="col" className="text-right">
                {valueLabel}
              </th>
              <th scope="col" className="text-right">
                Date
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={rowKey(i, row.shooter_id, row.event_date)}
                className="border-t border-outline-variant"
              >
                <td className="tabular-nums">{row.rank}</td>
                <td>
                  <ShooterLink id={row.shooter_id} name={row.display_name} />
                </td>
                <td className="text-right tabular-nums">{format(row.value)}</td>
                <td className="text-right">
                  <EventLink date={row.event_date} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export function PerfectRounds({ rows }: { rows: readonly RecordRoundOut[] }) {
  return (
    <Section title="Perfect 50s">
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <ul className="flex flex-col">
          {rows.map((row, i) => (
            <li
              key={rowKey(i, row.shooter_id, row.event_date)}
              className="flex items-center justify-between gap-2"
            >
              <ShooterLink id={row.shooter_id} name={row.display_name} />
              <EventLink date={row.event_date} />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export function JumpTable({ rows }: { rows: readonly RecordJumpOut[] }) {
  const title = 'Biggest week-over-week jumps';
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <table aria-label={title} className="w-full text-left text-sm">
          <thead className="text-text-muted">
            <tr>
              <th scope="col">#</th>
              <th scope="col">Shooter</th>
              <th scope="col" className="text-right">
                Jump
              </th>
              <th scope="col" className="text-right">
                Date
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${String(row.shooter_id)}-${row.event_date}`}
                className="border-t border-outline-variant"
              >
                <td className="tabular-nums">{row.rank}</td>
                <td>
                  <ShooterLink id={row.shooter_id} name={row.display_name} />
                </td>
                <td className="text-right tabular-nums">
                  {`${String(row.from_score)} → ${String(row.to_score)} (+${String(row.value)})`}
                </td>
                <td className="text-right">
                  <EventLink date={row.event_date} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export function RatingTable({ rows }: { rows: readonly RecordRatingOut[] }) {
  const title = 'Highest rating ever';
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <table aria-label={title} className="w-full text-left text-sm">
          <thead className="text-text-muted">
            <tr>
              <th scope="col">#</th>
              <th scope="col">Shooter</th>
              <th scope="col" className="text-right">
                Rating
              </th>
              <th scope="col" className="text-right">
                Date
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.shooter_id} className="border-t border-outline-variant">
                <td className="tabular-nums">{row.rank}</td>
                <td>
                  <ShooterLink id={row.shooter_id} name={row.display_name} />
                </td>
                <td className="text-right tabular-nums">{formatRating(row.value)}</td>
                <td className="text-right">
                  <EventLink date={row.event_date} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

export function ShooterRecordChart({
  title,
  valueLabel,
  rows,
  urlKey,
}: {
  title: string;
  valueLabel: string;
  rows: readonly RecordShooterOut[];
  urlKey: string;
}) {
  const data: TabularData = {
    columns: [
      { key: 'display_name', label: 'Shooter', type: 'string' },
      { key: 'value', label: valueLabel, type: 'int' },
    ],
    rows: chartRows(rows),
  };
  // The chart gets its own title: if ChartFrame renders a region named by its title (as Plan 07's Card does), reusing
  // `title` would give two regions named e.g. "Most events" and break getByRole('region', { name: title }).
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <NoneYet />
      ) : (
        <ChartFrame
          title={`Top ${String(rows.length)} · ${valueLabel}`}
          option={barOption(data, { x: 'display_name', y: ['value'], horizontal: true })}
          columns={data.columns}
          rows={data.rows}
          csvName={`records-${urlKey}`}
          ariaLabel={`${title} bar chart`}
          urlKey={urlKey}
        />
      )}
    </Section>
  );
}
```

Create `frontend/src/features/records/pages/RecordsPage.tsx`:
```tsx
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useRecords } from '../api';
import {
  JumpTable,
  PerfectRounds,
  RatingTable,
  RoundRecordTable,
  ShooterRecordChart,
} from '../components/RecordSections';
import { formatSigned } from '../format';

export function RecordsPage() {
  const records = useRecords();
  const data = records.data;

  let content;
  if (records.isError) {
    content = <EmptyState title="Records unavailable" description="Try again in a moment." />;
  } else if (data === undefined) {
    content = <Skeleton className="h-64" />;
  } else {
    content = (
      <div className="grid gap-4 lg:grid-cols-2">
        <RoundRecordTable
          title="Highest scores"
          valueLabel="Score"
          rows={data.highest_scores}
          format={(value) => String(value)}
        />
        <PerfectRounds rows={data.perfect_rounds} />
        <RoundRecordTable
          title="Biggest day vs the field"
          valueLabel="vs median"
          rows={data.biggest_adjusted}
          format={formatSigned}
        />
        <JumpTable rows={data.biggest_jumps} />
        <ShooterRecordChart
          title="Most events"
          valueLabel="Events"
          rows={data.most_events}
          urlKey="rec-events"
        />
        <ShooterRecordChart
          title="Longest streaks"
          valueLabel="Consecutive events"
          rows={data.longest_streaks}
          urlKey="rec-streaks"
        />
        <RatingTable rows={data.highest_ratings} />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-bold">Records</h1>
      {content}
    </div>
  );
}
```

- [ ] **Step 10: Run the records tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/records`
Expected: PASS — 13 tests passed (6 formatting + 7 page).

- [ ] **Step 11: Write the failing route test**

Create `frontend/src/features/records/routes.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import { RecordsPage } from './pages/RecordsPage';
import { routes } from './routes';

describe('records routes', () => {
  it('lazily loads RecordsPage at /records', async () => {
    const [route] = routes;
    expect(route?.path).toBe('/records');
    if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
    await expect(route.lazy()).resolves.toMatchObject({ Component: RecordsPage });
  });
});
```

- [ ] **Step 12: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/records/routes.test.ts`
Expected: FAIL — `Failed to resolve import "./routes"`.

- [ ] **Step 13: Register the route and the nav entry**

Create `frontend/src/features/records/routes.tsx`:
```tsx
import { Medal } from 'lucide-react';
import type { RouteObject } from 'react-router';

import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/records',
    lazy: async () => {
      const { RecordsPage } = await import('./pages/RecordsPage');
      return { Component: RecordsPage };
    },
  },
];

export const nav: NavItem[] = [{ label: 'Records', path: '/records', icon: Medal, order: 120 }];
```

- [ ] **Step 14: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/records/routes.test.ts`
Expected: PASS — 1 test passed.

- [ ] **Step 15: Format, then run the full frontend gate**

Run:
```bash
cd frontend
pnpm exec prettier --write src/features/records e2e/records.spec.ts
pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage
```
Expected: eslint (0 warnings), `tsc` and prettier clean (a missing `RecordsOut` field in the regenerated schema is a
cross-plan mismatch to report); every Vitest file passes, including Plan 07's registry test; coverage ≥ 90% lines and
branches for the whole frontend.

- [ ] **Step 16: Rebuild both images and run the e2e spec to verify it passes**

Run from the worktree root: the same tag and Compose project as Step 2 (whose `secrets/` are reused as is), both
images rebuilt first, then a fresh stack under the machine-wide e2e lock (Decision D23; the `setup` project re-seeds the
fixtures), torn down by the `EXIT` trap:
```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=09-5b
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/records.spec.ts)
```
(The foreground-`sleep` note from Step 2 applies here too.)
Expected: all 4 `records.spec.ts` tests pass (2 tests × `mobile` and `desktop`); Playwright's summary also counts the
`setup` project's tests as passed, so the total is higher than 4; 0 failed. The trap then removes the stack and the
lock.

- [ ] **Step 17: Commit**

```bash
git add frontend/src/features/records frontend/e2e/records.spec.ts
git commit -F - <<'EOF'
feat(records): add records page

Highest scores, perfect 50s, biggest day vs the field, week-over-week jumps,
most events and longest streaks charts, and highest rating ever, following the
global round-type filter.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 7: Race page — bar-chart race and bump chart with play/pause/scrub (master Plan 09 T6)

**Files:**
- Create: `frontend/src/features/race/labels.ts`, `labels.test.ts`
- Create: `frontend/src/features/race/transforms.ts`, `transforms.test.ts`
- Create: `frontend/src/features/race/usePlayer.ts`, `usePlayer.test.ts`
- Create: `frontend/src/features/race/api.ts`
- Create: `frontend/src/features/race/mocks.ts`
- Create: `frontend/src/features/race/components/RaceView.tsx`, `components/RaceView.test.tsx`
- Create: `frontend/src/features/race/pages/RacePage.tsx`, `pages/RacePage.test.tsx`
- Create: `frontend/src/features/race/routes.tsx`, `routes.test.ts`
- Create: `frontend/e2e/race.spec.ts`

Plan 07 T5's `race.ts` and `bump.ts` builders are used as they are and never edited (master T6).

**Stable racer names.** `raceOption` de-duplicates names within one frame (` #<id>`), so two namesakes who share only
some frames would see a bar renamed mid-race (`Jim` → `Jim #7`), which breaks the bar's animation. Names are therefore
disambiguated across ALL frames first: `racerNames(frames)` gives each shooter id one chart name for the whole race
(`<name> #<id>` when that display name belongs to more than one `shooter_id` in any frame), and `toLeaderboardFrame`
uses it before `raceOption`/`bumpOption` are called. Verify the animation by watching it play (Step 24), not only
through tests.

**No zoom on the race.** The race `ChartFrame` passes `zoom="none"`; `defaultZoom` would otherwise give the horizontal
race bars `'y'` zoom (Plan 07 D17).

**Interfaces:**
- Consumes (Plan 07, names per Decision D17): `api`, `unwrap`, `paths`, `useUrlState`, `useRoundTypes():
  [RoundTypeValue[], (next: RoundTypeValue[]) => void]` (`src/lib/roundTypes.ts`), `NavItem`, `Chip`,
  `EmptyState({ title, description?, action?, icon? })`, `Skeleton`, `ChartFrame`, `TabularData` and `LeaderboardFrame
  = { date: string; rows: { id: number | string; name: string; value: number; rank: number }[] }` (both from
  `src/components/charts/types.ts`, Plan 07 D16; this task always passes numeric ids), `raceOption(frame:
  LeaderboardFrame, opts?: RaceOpts): EChartsOption` (`src/components/charts/builders/race.ts`; `RaceOpts = { top?;
  valueName?; durationMs? }`, default top 10; repeated names get ` #<id>`), `bumpOption(frames: readonly
  LeaderboardFrame[], opts?: BumpOpts): EChartsOption` (`src/components/charts/builders/bump.ts`; `BumpOpts = { top?
  }`, default 10), `renderWithProviders`, `server`, e2e `test`/`expect`.
- Consumes (Plan 09 Task 4, via `paths`): `GET /api/leaderboards/history?period&metric&top&from&to&round_type` →
  `{ period; metric; frames: { event_date: string; rows: { shooter_id: number; display_name: string; status: string |
  null; value: number; rank: number }[] }[] }`.
- Produces: route `/race` and nav `{ label: 'Race', path: '/race', icon: Flag, order: 130 }` (C10);
  `features/race/api.ts`: `useLeaderboardHistory(q: RaceQuery)` and types `LeaderboardHistoryOut`, `HistoryFrame`,
  `LeaderboardPeriod`, `LeaderboardMetric`, `RaceQuery`; `transforms.ts`: `racerNames(frames: readonly HistoryFrame[]):
  ReadonlyMap<number, string>` (one chart name per shooter id across all frames), `toLeaderboardFrame(frame:
  HistoryFrame, names: ReadonlyMap<number, string>): LeaderboardFrame` (builder input), `frameTable(frame:
  HistoryFrame | undefined, valueLabel: string): TabularData`
  and `bumpTable(frames: readonly HistoryFrame[]): TabularData` (ChartFrame table/CSV rows); `usePlayer.ts`:
  `usePlayer(frameCount: number, intervalMs = PLAY_INTERVAL_MS): Player` with `Player = { index; playing; play;
  pause; seek }`; MSW handler for `*/api/leaderboards/history`.

**Branch:** `task/09-6-race`

**Depends on:** Plan 09 T4; Plan 07 T1, T2, T4 (`useRoundTypes`), T5 (`race.ts`, `bump.ts`, `LeaderboardFrame`), T6;
Plan 04 T2 (e2e fixture seed).

- [ ] **Step 0: Confirm the consumed Plan 07 names**

Run (from the worktree root):
```bash
cd frontend
for sym in renderWithProviders server api unwrap useUrlState useRoundTypes ChartFrame raceOption bumpOption TabularData LeaderboardFrame NavItem Chip EmptyState Skeleton; do
  printf '%-20s %s\n' "$sym" "$(grep -rlE "export (default )?(async )?(function|const|class|type|interface) $sym\b" src | head -1)"
done
grep -nE -A6 "export (interface|type) LeaderboardFrame\b" src/components/charts/types.ts
grep -nE -A4 "export function (raceOption|bumpOption)\(" src/components/charts/builders/race.ts src/components/charts/builders/bump.ts
grep -nE "export (const|\{).*(test|expect)" e2e/fixtures.ts
sed -n '1,40p' src/lib/useUrlState.ts
sed -n '1,60p' src/lib/roundTypes.ts
grep -nE "description\?:" src/components/ui/EmptyState.tsx
```
Expected: every symbol prints a file path (`useRoundTypes` → `src/lib/roundTypes.ts`, `LeaderboardFrame` →
`src/components/charts/types.ts`); `LeaderboardFrame` has `date` and `rows` of `{ id: number | string, name, value,
rank }` (Plan 07 D16); `raceOption`'s first parameter is one `LeaderboardFrame` and `bumpOption`'s is an array of them,
each with only an optional second parameter (`opts: RaceOpts = {}` / `opts: BumpOpts = {}`); `useUrlState`'s codec has
`parse`/`serialize`; `useRoundTypes()` returns a
`[roundTypes, setRoundTypes]` tuple bound to the comma-list URL key `rt` (Plan 07 D14); `EmptyState` has a
`description?:` prop (no `message` prop). If a builder's export name or a `LeaderboardFrame` field is named
differently, adapt `toLeaderboardFrame` (and its test) and the two builder calls in `RaceView.tsx` only; if a builder
requires an options argument, fill it from the metric `label` in `RaceView` or `RACE_TOP` from `../labels`, in
`RaceView.tsx` only. If `useRoundTypes`' tuple shape differs, adapt only this task's destructuring; never
re-implement the `rt` parser here. List every mapping in your report. If `rt` uses another encoding, write that
encoding where `RacePage.test.tsx` uses `rt=sporting`.

- [ ] **Step 1: Write the failing e2e spec**

Create `frontend/e2e/race.spec.ts` (fixture facts: Decision D22 — the 2026 season's first event is 2026-01-04, its
latest 2026-09-27, where the points leader has 191):
```ts
import { expect, test } from './fixtures';

test('the 2026 season race ends on Sep 27 with the points leader on 191', async ({ page }) => {
  await page.goto('/race?year=2026');
  await expect(page.getByRole('heading', { level: 1, name: 'Race' })).toBeVisible();
  await expect(page.locator('output').filter({ hasText: 'Sep 27, 2026' })).toBeVisible();
  await expect(
    page.getByRole('list', { name: 'Standings' }).getByRole('listitem').first(),
  ).toContainText('191');
  await expect(page.getByRole('button', { name: /csv/i }).first()).toBeVisible();
});

test('play restarts the race from the first Sunday of the season', async ({ page }) => {
  await page.goto('/race?year=2026');
  await page.getByRole('button', { name: 'Play' }).click();
  await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible();
  await expect(page.locator('output').filter({ hasText: /Jan (4|11), 2026/ })).toBeVisible();
});
```

- [ ] **Step 2: Run the e2e spec against the current stack to verify it fails**

Plans 08, 09 and 10 UI tasks run concurrently in Wave 4 and every stack publishes host port 8080, so this task builds
its own image tag (`09-6`, never `ci`), runs Compose as its own project `sc-09-6` and holds the machine-wide lock
directory `/tmp/sunday-clays-e2e.lock` of Plan 08 D24 for exactly one stack lifetime (Decision D23). The `EXIT` trap
tears the stack down and releases the lock even though this run fails. A lock with no `docker ps --filter
publish=8080` container behind it is left over from a crashed run: `rmdir` it. Run from the worktree root (`rm -rf
secrets` deletes only this worktree's generated, gitignored dev secrets):
```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=09-6
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
rm -rf secrets && VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
(cd frontend && pnpm exec playwright install chromium)
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/race.spec.ts)
```
(If your shell blocks a foreground `sleep`, run the whole block as a background or monitored command and read its
output when it exits.)
Expected: FAIL in both `mobile` and `desktop` — no `Race` heading (no `/race` route yet); then the trap removes the
stack and the lock.

- [ ] **Step 3: Write the failing label tests**

Create `frontend/src/features/race/labels.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import { formatEventDate, formatValue, metricLabel, oneOf, seasonYears, yearCodec } from './labels';

describe('race labels', () => {
  it('lists seasons newest first back to 2020', () => {
    expect(seasonYears(2022)).toEqual([2022, 2021, 2020]);
  });

  it('parses only known years', () => {
    const codec = yearCodec(2026);
    expect(codec.parse('2024')).toBe(2024);
    expect(codec.parse('2019')).toBe(2026);
    expect(codec.parse('2031')).toBe(2026);
    expect(codec.parse('abc')).toBe(2026);
    expect(codec.serialize(2025)).toBe('2025');
  });

  it('falls back for unknown enum values', () => {
    const codec = oneOf(['season', 'all_time'] as const, 'season');
    expect(codec.parse('all_time')).toBe('all_time');
    expect(codec.parse('nope')).toBe('season');
    expect(codec.serialize('season')).toBe('season');
  });

  it.each([
    ['season_points', 191, '191'],
    ['avg_score', 43.017, '43.02'],
    ['most_improved', 2.5, '+2.50'],
    ['avg_adjusted', -1, '-1.00'],
  ] as const)('formats %s %d as %s', (metric, value, text) => {
    expect(formatValue(metric, value)).toBe(text);
  });

  it('labels metrics and dates', () => {
    expect(metricLabel('wins')).toBe('Wins');
    expect(formatEventDate('2026-09-27')).toBe('Sep 27, 2026');
  });
});
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/race/labels.test.ts`
Expected: FAIL — `Failed to resolve import "./labels"`.

- [ ] **Step 5: Implement the labels module**

Create `frontend/src/features/race/labels.ts` (its type-only import of `./api` resolves once Step 17 creates `api.ts`):
```ts
import type { LeaderboardMetric, LeaderboardPeriod } from './api';

/** Assignable to Plan 07's `Codec<T>` (`useUrlState`); `parse` here never returns null. */
export interface UrlCodec<T> {
  parse: (raw: string) => T;
  serialize: (value: T) => string;
}

export const FIRST_SEASON = 2020;
export const RACE_TOP = 10;

export const PERIODS: readonly { value: LeaderboardPeriod; label: string }[] = [
  { value: 'season', label: 'Season' },
  { value: 'rolling_12', label: 'Last 12 months' },
  { value: 'all_time', label: 'All time' },
];

export const METRICS: readonly { value: LeaderboardMetric; label: string }[] = [
  { value: 'season_points', label: 'Season points' },
  { value: 'wins', label: 'Wins' },
  { value: 'podiums', label: 'Podiums' },
  { value: 'avg_score', label: 'Average' },
  { value: 'avg_adjusted', label: 'Avg vs field' },
  { value: 'best_score', label: 'Best round' },
  { value: 'events', label: 'Events' },
  { value: 'rounds', label: 'Rounds' },
  { value: 'rating', label: 'Rating' },
  { value: 'most_improved', label: 'Most improved' },
];

export function metricLabel(metric: LeaderboardMetric): string {
  return METRICS.find((m) => m.value === metric)?.label ?? metric;
}

export function formatValue(metric: LeaderboardMetric, value: number): string {
  switch (metric) {
    case 'avg_score':
    case 'rating':
      return value.toFixed(2);
    case 'avg_adjusted':
    case 'most_improved':
      return `${value > 0 ? '+' : ''}${value.toFixed(2)}`;
    default:
      return String(Math.round(value));
  }
}

export function formatEventDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function seasonYears(currentYear: number): number[] {
  const years: number[] = [];
  for (let year = currentYear; year >= FIRST_SEASON; year -= 1) years.push(year);
  return years;
}

export function oneOf<T extends string>(values: readonly T[], fallback: T): UrlCodec<T> {
  const isMember = (raw: string): raw is T => (values as readonly string[]).includes(raw);
  return {
    parse: (raw) => (isMember(raw) ? raw : fallback),
    serialize: (value) => value,
  };
}

export function yearCodec(currentYear: number): UrlCodec<number> {
  return {
    parse: (raw) => {
      const year = Number(raw);
      return Number.isInteger(year) && year >= FIRST_SEASON && year <= currentYear
        ? year
        : currentYear;
    },
    serialize: (value) => String(value),
  };
}
```

- [ ] **Step 6: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/race/labels.test.ts`
Expected: PASS — 8 tests passed.

- [ ] **Step 7: Write the failing transform tests**

Create `frontend/src/features/race/transforms.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import type { HistoryFrame } from './api';
import { bumpTable, frameTable, racerNames, toLeaderboardFrame } from './transforms';

const JAN_11: HistoryFrame = {
  event_date: '2026-01-11',
  rows: [
    { shooter_id: 2, display_name: 'Bee, Bob', status: 'guest', value: 20, rank: 1 },
    { shooter_id: 1, display_name: 'Ace, Amy', status: 'member', value: 20, rank: 1 },
  ],
};

const FRAMES: HistoryFrame[] = [
  {
    event_date: '2026-01-04',
    rows: [
      { shooter_id: 1, display_name: 'Ace, Amy', status: 'member', value: 11, rank: 1 },
      { shooter_id: 2, display_name: 'Bee, Bob', status: 'guest', value: 9, rank: 2 },
    ],
  },
  JAN_11,
];

describe('racerNames', () => {
  it('gives namesakes one #id name in every frame, even frames where only one of them appears', () => {
    const jim = (shooter_id: number, value: number, rank: number) => ({
      shooter_id,
      display_name: 'Desmond',
      status: 'guest',
      value,
      rank,
    });
    const alone: HistoryFrame = { event_date: '2026-01-04', rows: [jim(7, 10, 1)] };
    const both: HistoryFrame = { event_date: '2026-01-11', rows: [jim(7, 18, 1), jim(9, 10, 2)] };
    const names = racerNames([alone, both]);
    expect(names.get(7)).toBe('Jim #7');
    expect(names.get(9)).toBe('Jim #9');
    expect(toLeaderboardFrame(alone, names).rows.map((r) => r.name)).toEqual(['Jim #7']);
    expect(racerNames(FRAMES).get(1)).toBe('Ace, Amy');
  });
});

describe('toLeaderboardFrame', () => {
  it("maps a history frame onto the race/bump builders' LeaderboardFrame, keeping API order and shared ranks", () => {
    expect(toLeaderboardFrame(JAN_11, racerNames(FRAMES))).toEqual({
      date: '2026-01-11',
      rows: [
        { id: 2, name: 'Bee, Bob', value: 20, rank: 1 },
        { id: 1, name: 'Ace, Amy', value: 20, rank: 1 },
      ],
    });
  });
});

describe('frameTable', () => {
  it('turns one frame into shooter/value rows in API order', () => {
    expect(frameTable(FRAMES[1], 'Season points')).toEqual({
      columns: [
        { key: 'display_name', label: 'Shooter', type: 'string' },
        { key: 'value', label: 'Season points', type: 'number' },
      ],
      rows: [
        { display_name: 'Bee, Bob', value: 20 },
        { display_name: 'Ace, Amy', value: 20 },
      ],
    });
  });

  it('is empty without a frame', () => {
    expect(frameTable(undefined, 'Wins').rows).toEqual([]);
  });
});

describe('bumpTable', () => {
  it('lists every frame row with its event date and shared rank', () => {
    expect(bumpTable(FRAMES).rows).toEqual([
      { event_date: '2026-01-04', display_name: 'Ace, Amy', rank: 1 },
      { event_date: '2026-01-04', display_name: 'Bee, Bob', rank: 2 },
      { event_date: '2026-01-11', display_name: 'Bee, Bob', rank: 1 },
      { event_date: '2026-01-11', display_name: 'Ace, Amy', rank: 1 },
    ]);
  });
});
```

- [ ] **Step 8: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/race/transforms.test.ts`
Expected: FAIL — `Failed to resolve import "./transforms"`.

- [ ] **Step 9: Implement the transforms**

Create `frontend/src/features/race/transforms.ts`:
```ts
import type { LeaderboardFrame, TabularData } from '../../components/charts/types';
import type { HistoryFrame } from './api';

/**
 * One chart name per shooter across ALL frames: a display name held by more than one shooter_id
 * anywhere in the race becomes `<name> #<id>` in every frame, so raceOption's per-frame
 * de-duplication never renames a bar mid-race.
 */
export function racerNames(frames: readonly HistoryFrame[]): ReadonlyMap<number, string> {
  const idsByName = new Map<string, Set<number>>();
  for (const frame of frames) {
    for (const r of frame.rows) {
      const ids = idsByName.get(r.display_name) ?? new Set<number>();
      ids.add(r.shooter_id);
      idsByName.set(r.display_name, ids);
    }
  }
  const names = new Map<number, string>();
  for (const [name, ids] of idsByName) {
    for (const id of ids) names.set(id, ids.size > 1 ? `${name} #${id}` : name);
  }
  return names;
}

/** A LeaderboardHistoryOut frame as Plan 07's typed race/bump builder input (D17; rows keep the API order). */
export function toLeaderboardFrame(
  frame: HistoryFrame,
  names: ReadonlyMap<number, string>,
): LeaderboardFrame {
  return {
    date: frame.event_date,
    rows: frame.rows.map((r) => ({
      id: r.shooter_id,
      name: names.get(r.shooter_id) ?? r.display_name,
      value: r.value,
      rank: r.rank,
    })),
  };
}

/** One frame of the race as a bar table for ChartFrame's table/CSV: shooter → value (already ordered by the API). */
export function frameTable(frame: HistoryFrame | undefined, valueLabel: string): TabularData {
  return {
    columns: [
      { key: 'display_name', label: 'Shooter', type: 'string' },
      { key: 'value', label: valueLabel, type: 'number' },
    ],
    rows: (frame?.rows ?? []).map((row) => ({ display_name: row.display_name, value: row.value })),
  };
}

/** Every frame's top-N as long rows for the bump chart's table/CSV: event date × shooter → rank. */
export function bumpTable(frames: readonly HistoryFrame[]): TabularData {
  return {
    columns: [
      { key: 'event_date', label: 'Event', type: 'date' },
      { key: 'display_name', label: 'Shooter', type: 'string' },
      { key: 'rank', label: 'Rank', type: 'int' },
    ],
    rows: frames.flatMap((frame) =>
      frame.rows.map((row) => ({
        event_date: frame.event_date,
        display_name: row.display_name,
        rank: row.rank,
      })),
    ),
  };
}
```

- [ ] **Step 10: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/race/transforms.test.ts`
Expected: PASS — 5 tests passed.

- [ ] **Step 11: Write the failing player tests**

Create `frontend/src/features/race/usePlayer.test.ts`:
```ts
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PLAY_INTERVAL_MS, usePlayer } from './usePlayer';

describe('usePlayer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts paused on the latest frame', () => {
    const { result } = renderHook(() => usePlayer(4));
    expect(result.current.index).toBe(3);
    expect(result.current.playing).toBe(false);
  });

  it('plays from the first frame when started at the end and stops on the last frame', () => {
    const { result } = renderHook(() => usePlayer(3));
    act(() => {
      result.current.play();
    });
    expect(result.current.index).toBe(0);
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(1);
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(2);
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(2);
    expect(result.current.playing).toBe(false);
  });

  it('pause stops advancing and play resumes from the current frame', () => {
    const { result } = renderHook(() => usePlayer(5));
    act(() => {
      result.current.seek(1);
    });
    act(() => {
      result.current.play();
    });
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS);
    });
    expect(result.current.index).toBe(2);
    act(() => {
      result.current.pause();
    });
    act(() => {
      vi.advanceTimersByTime(PLAY_INTERVAL_MS * 3);
    });
    expect(result.current.index).toBe(2);
  });

  it('seek clamps to the frame range and pauses', () => {
    const { result } = renderHook(() => usePlayer(3));
    act(() => {
      result.current.play();
    });
    act(() => {
      result.current.seek(9);
    });
    expect(result.current).toMatchObject({ index: 2, playing: false });
    act(() => {
      result.current.seek(-4);
    });
    expect(result.current.index).toBe(0);
  });

  it('handles an empty history', () => {
    const { result } = renderHook(() => usePlayer(0));
    expect(result.current.index).toBe(0);
  });
});
```

- [ ] **Step 12: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/race/usePlayer.test.ts`
Expected: FAIL — `Failed to resolve import "./usePlayer"`.

- [ ] **Step 13: Implement the player**

Create `frontend/src/features/race/usePlayer.ts` (state changes happen only in event handlers and the timer callback,
never synchronously inside an effect, so the react-hooks rules stay clean):
```ts
import { useEffect, useState } from 'react';

export const PLAY_INTERVAL_MS = 1200;

export interface Player {
  index: number;
  playing: boolean;
  play: () => void;
  pause: () => void;
  seek: (index: number) => void;
}

/** Frame cursor for the race: starts on the latest frame; Play from the end restarts at 0. */
export function usePlayer(frameCount: number, intervalMs = PLAY_INTERVAL_MS): Player {
  const last = Math.max(0, frameCount - 1);
  const [picked, setPicked] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const index = picked === null ? last : Math.min(picked, last);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = window.setTimeout(() => {
      if (index >= last) setPlaying(false);
      else setPicked(index + 1);
    }, intervalMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [playing, index, last, intervalMs]);

  return {
    index,
    playing,
    play: () => {
      if (index >= last) setPicked(0);
      setPlaying(true);
    },
    pause: () => {
      setPlaying(false);
    },
    seek: (next) => {
      setPlaying(false);
      setPicked(Math.min(Math.max(next, 0), last));
    },
  };
}
```

- [ ] **Step 14: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/race/usePlayer.test.ts`
Expected: PASS — 5 tests passed.

- [ ] **Step 15: Write the MSW fixtures and the failing view/page tests**

Create `frontend/src/features/race/mocks.ts`:
```ts
import { http, HttpResponse } from 'msw';

import type { LeaderboardHistoryOut } from './api';

export const historyFixture: LeaderboardHistoryOut = {
  period: 'season',
  metric: 'season_points',
  frames: [
    {
      event_date: '2026-09-06',
      rows: [
        { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', value: 11, rank: 1 },
        { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', value: 9, rank: 2 },
      ],
    },
    {
      event_date: '2026-09-13',
      rows: [
        { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', value: 20, rank: 1 },
        { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', value: 18, rank: 2 },
      ],
    },
    {
      event_date: '2026-09-27',
      rows: [
        { shooter_id: 3, display_name: 'Bee, Bob', status: 'member', value: 29, rank: 1 },
        { shooter_id: 7, display_name: 'Ace, Amy', status: 'member', value: 29, rank: 1 },
      ],
    },
  ],
};

export const handlers = [
  http.get('*/api/leaderboards/history', () => HttpResponse.json(historyFixture)),
];
```

Create `frontend/src/features/race/components/RaceView.test.tsx`:
```tsx
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RaceView } from './RaceView';

describe('RaceView', () => {
  it('renders nothing without frames', () => {
    const { container } = render(<RaceView frames={[]} metric="wins" />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

Create `frontend/src/features/race/pages/RacePage.test.tsx`:
```tsx
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { LeaderboardHistoryOut } from '../api';
import { historyFixture } from '../mocks';
import { RacePage } from './RacePage';

function captureRequests(body: LeaderboardHistoryOut = historyFixture): URL[] {
  const seen: URL[] = [];
  server.use(
    http.get('*/api/leaderboards/history', ({ request }) => {
      seen.push(new URL(request.url));
      return HttpResponse.json(body);
    }),
  );
  return seen;
}

function standings(): string[] {
  return within(screen.getByRole('list', { name: 'Standings' }))
    .getAllByRole('listitem')
    .map((item) => item.textContent);
}

describe('RacePage', () => {
  it('asks for the season points race of the chosen year', async () => {
    const seen = captureRequests();
    renderWithProviders(<RacePage />, { route: '/race?year=2026&rt=sporting' });
    await screen.findByRole('list', { name: 'Standings' });
    const params = seen.at(-1)?.searchParams;
    expect(params?.get('period')).toBe('season');
    expect(params?.get('metric')).toBe('season_points');
    expect(params?.get('top')).toBe('10');
    expect(params?.get('from')).toBe('2026-01-01');
    expect(params?.get('to')).toBe('2026-12-31');
    expect(params?.getAll('round_type')).toEqual(['sporting']);
  });

  it('opens on the latest frame and scrubs to earlier ones', async () => {
    renderWithProviders(<RacePage />, { route: '/race?year=2026' });
    await screen.findByRole('list', { name: 'Standings' });
    expect(screen.getByText('Sep 27, 2026', { selector: 'output' })).toBeInTheDocument();
    expect(standings()).toEqual(['1Bee, Bob29', '1Ace, Amy29']);
    fireEvent.change(screen.getByLabelText('Race position'), { target: { value: '0' } });
    expect(screen.getByText('Sep 6, 2026', { selector: 'output' })).toBeInTheDocument();
    expect(standings()).toEqual(['1Ace, Amy11', '2Bee, Bob9']);
  });

  it('toggles between play and pause', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RacePage />, { route: '/race?year=2026' });
    await user.click(await screen.findByRole('button', { name: 'Play' }));
    expect(screen.getByText('Sep 6, 2026', { selector: 'output' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Pause' }));
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
  });

  it('changes metric, period and year through the URL-backed controls', async () => {
    const seen = captureRequests();
    const user = userEvent.setup();
    renderWithProviders(<RacePage />, { route: '/race?year=2026' });
    await screen.findByRole('list', { name: 'Standings' });
    await user.selectOptions(screen.getByLabelText('Metric'), 'Wins');
    await user.click(screen.getByRole('button', { name: 'All time' }));
    await user.selectOptions(screen.getByLabelText('Year'), '2025');
    await waitFor(() => {
      expect(seen.at(-1)?.searchParams.get('from')).toBe('2025-01-01');
    });
    expect(seen.at(-1)?.searchParams.get('metric')).toBe('wins');
    expect(seen.at(-1)?.searchParams.get('period')).toBe('all_time');
  });

  it('shows an empty state for a season without events', async () => {
    captureRequests({ ...historyFixture, frames: [] });
    renderWithProviders(<RacePage />, { route: '/race?year=2026' });
    expect(await screen.findByText('No events in 2026')).toBeInTheDocument();
  });

  it('shows an error state when the API fails', async () => {
    server.use(
      http.get('*/api/leaderboards/history', () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<RacePage />, { route: '/race?year=2026' });
    expect(await screen.findByText('Race unavailable')).toBeInTheDocument();
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<RacePage />, { route: '/race?year=2026' });
    await screen.findByRole('list', { name: 'Standings' });
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(2);
  });
});
```

- [ ] **Step 16: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/race/components src/features/race/pages`
Expected: FAIL — `Failed to resolve import "./RaceView"` and `Failed to resolve import "./RacePage"`.

- [ ] **Step 17: Implement the hook, the race view and the page**

Create `frontend/src/features/race/api.ts`:
```ts
import { useQuery } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useRoundTypes } from '../../lib/roundTypes';

type JsonOf<Op> = Op extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : never;

export type LeaderboardHistoryOut = JsonOf<paths['/api/leaderboards/history']['get']>;
export type HistoryFrame = LeaderboardHistoryOut['frames'][number];
export type LeaderboardPeriod = LeaderboardHistoryOut['period'];
export type LeaderboardMetric = LeaderboardHistoryOut['metric'];

export interface RaceQuery {
  period: LeaderboardPeriod;
  metric: LeaderboardMetric;
  year: number;
  top: number;
}

export function useLeaderboardHistory({ period, metric, year, top }: RaceQuery) {
  const [roundTypes] = useRoundTypes();
  const query = {
    period,
    metric,
    top,
    from: `${String(year)}-01-01`,
    to: `${String(year)}-12-31`,
    round_type: roundTypes.length > 0 ? roundTypes : undefined,
  };
  return useQuery({
    queryKey: ['/api/leaderboards/history', query],
    queryFn: () => unwrap(api.GET('/api/leaderboards/history', { params: { query } })),
  });
}
```

Create `frontend/src/features/race/components/RaceView.tsx`:
```tsx
import { Pause, Play } from 'lucide-react';

import { bumpOption } from '../../../components/charts/builders/bump';
import { raceOption } from '../../../components/charts/builders/race';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { HistoryFrame, LeaderboardMetric } from '../api';
import { formatEventDate, formatValue, metricLabel } from '../labels';
import { bumpTable, frameTable, racerNames, toLeaderboardFrame } from '../transforms';
import { usePlayer } from '../usePlayer';

export interface RaceViewProps {
  frames: readonly HistoryFrame[];
  metric: LeaderboardMetric;
}

export function RaceView({ frames, metric }: RaceViewProps) {
  const player = usePlayer(frames.length);
  const frame = frames[player.index];
  if (frame === undefined) return null;
  const label = metricLabel(metric);
  // Builders draw from Plan 07's LeaderboardFrame; ChartFrame's table and CSV use the TabularData versions.
  // Names are fixed across the whole race, so a bar is never renamed mid-race.
  const names = racerNames(frames);
  const race = frameTable(frame, label);
  const bump = bumpTable(frames);
  const last = Math.max(0, frames.length - 1);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 rounded-card bg-elevated p-3">
        <button
          type="button"
          onClick={player.playing ? player.pause : player.play}
          className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button bg-primary px-4"
        >
          {player.playing ? <Pause aria-hidden size={18} /> : <Play aria-hidden size={18} />}
          {player.playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={last}
          step={1}
          value={player.index}
          aria-label="Race position"
          aria-valuetext={formatEventDate(frame.event_date)}
          onChange={(event) => {
            player.seek(Number(event.currentTarget.value));
          }}
          className="min-h-11 flex-1 accent-primary"
        />
        <output className="min-w-28 text-right font-medium">
          {formatEventDate(frame.event_date)}
        </output>
      </div>
      <ChartFrame
        title={`${label} race`}
        subtitle={`After ${formatEventDate(frame.event_date)}`}
        option={raceOption(toLeaderboardFrame(frame, names))}
        columns={race.columns}
        rows={race.rows}
        csvName={`race-${metric}-${frame.event_date}`}
        ariaLabel={`${label} race bar chart`}
        urlKey="race-bars"
        zoom="none"
      />
      <ol aria-label="Standings" className="flex flex-col text-sm">
        {frame.rows.map((row) => (
          <li
            key={row.shooter_id}
            className="flex min-h-11 items-center justify-between border-t border-outline-variant"
          >
            <span>
              <span className="mr-2 tabular-nums text-text-muted">{row.rank}</span>
              {row.display_name}
            </span>
            <span className="tabular-nums">{formatValue(metric, row.value)}</span>
          </li>
        ))}
      </ol>
      <ChartFrame
        title="Rank over time"
        option={bumpOption(frames.map((f) => toLeaderboardFrame(f, names)))}
        columns={bump.columns}
        rows={bump.rows}
        csvName={`race-ranks-${metric}`}
        ariaLabel={`${label} rank bump chart`}
        urlKey="race-bump"
      />
    </div>
  );
}
```

Create `frontend/src/features/race/pages/RacePage.tsx` (the `key` on `RaceView` resets the player when the period,
metric or year changes, so it reopens on the latest frame without a state-reset effect):
```tsx
import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useUrlState } from '../../../lib/useUrlState';
import { type LeaderboardMetric, type LeaderboardPeriod, useLeaderboardHistory } from '../api';
import { RaceView } from '../components/RaceView';
import { METRICS, PERIODS, RACE_TOP, oneOf, seasonYears, yearCodec } from '../labels';

const CURRENT_YEAR = new Date().getFullYear();
const PERIOD_CODEC = oneOf(
  PERIODS.map((p) => p.value),
  'season',
);
const METRIC_CODEC = oneOf(
  METRICS.map((m) => m.value),
  'season_points',
);
const YEAR_CODEC = yearCodec(CURRENT_YEAR);

export function RacePage() {
  const [period, setPeriod] = useUrlState<LeaderboardPeriod>('period', PERIOD_CODEC, 'season');
  const [metric, setMetric] = useUrlState<LeaderboardMetric>(
    'metric',
    METRIC_CODEC,
    'season_points',
  );
  const [year, setYear] = useUrlState<number>('year', YEAR_CODEC, CURRENT_YEAR);
  const history = useLeaderboardHistory({ period, metric, year, top: RACE_TOP });
  const frames = history.data?.frames;

  let content;
  if (history.isError) {
    content = <EmptyState title="Race unavailable" description="Try again in a moment." />;
  } else if (frames === undefined) {
    content = <Skeleton className="h-96" />;
  } else if (frames.length === 0) {
    content = (
      <EmptyState title={`No events in ${String(year)}`} description="Pick another season." />
    );
  } else {
    content = (
      <RaceView key={`${period}|${metric}|${String(year)}`} frames={frames} metric={metric} />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
      <h1 className="text-2xl font-bold">Race</h1>
      <div className="flex flex-wrap items-end gap-3">
        <div role="group" aria-label="Period" className="flex flex-wrap gap-2">
          {PERIODS.map((p) => (
            <Chip
              key={p.value}
              selected={p.value === period}
              onClick={() => {
                setPeriod(p.value);
              }}
            >
              {p.label}
            </Chip>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-sm">
          Metric
          <select
            value={metric}
            onChange={(event) => {
              setMetric(METRIC_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            {METRICS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Year
          <select
            value={String(year)}
            onChange={(event) => {
              setYear(YEAR_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            {seasonYears(CURRENT_YEAR).map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>
      {content}
    </div>
  );
}
```

- [ ] **Step 18: Run the race tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/race`
Expected: PASS — 26 tests passed (8 labels + 5 transforms + 5 player + 1 view + 7 page).

- [ ] **Step 19: Write the failing route test**

Create `frontend/src/features/race/routes.test.ts`:
```ts
import { describe, expect, it } from 'vitest';

import { RacePage } from './pages/RacePage';
import { routes } from './routes';

describe('race routes', () => {
  it('lazily loads RacePage at /race', async () => {
    const [route] = routes;
    expect(route?.path).toBe('/race');
    if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
    await expect(route.lazy()).resolves.toMatchObject({ Component: RacePage });
  });
});
```

- [ ] **Step 20: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/race/routes.test.ts`
Expected: FAIL — `Failed to resolve import "./routes"`.

- [ ] **Step 21: Register the route and the nav entry**

Create `frontend/src/features/race/routes.tsx`:
```tsx
import { Flag } from 'lucide-react';
import type { RouteObject } from 'react-router';

import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/race',
    lazy: async () => {
      const { RacePage } = await import('./pages/RacePage');
      return { Component: RacePage };
    },
  },
];

export const nav: NavItem[] = [{ label: 'Race', path: '/race', icon: Flag, order: 130 }];
```

- [ ] **Step 22: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/race/routes.test.ts`
Expected: PASS — 1 test passed.

- [ ] **Step 23: Format, then run the full frontend gate**

Run:
```bash
cd frontend
pnpm exec prettier --write src/features/race e2e/race.spec.ts
pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage
```
Expected: eslint (0 warnings), `tsc` and prettier clean (a missing `LeaderboardHistoryOut` field in the regenerated
schema is a cross-plan mismatch to report); every Vitest file passes, including Plan 07's registry test; coverage ≥ 90%
lines and branches for the whole frontend; the entry-chunk budget is unaffected because the page is lazy-loaded.

- [ ] **Step 24: Rebuild both images and run the e2e spec to verify it passes**

Run from the worktree root: the same tag and Compose project as Step 2 (whose `secrets/` are reused as is), both
images rebuilt first, then a fresh stack under the machine-wide e2e lock (Decision D23; the `setup` project re-seeds the
fixtures), torn down by the `EXIT` trap:
```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=09-6
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/race.spec.ts)
```
(The foreground-`sleep` note from Step 2 applies here too.)
Expected: all 4 `race.spec.ts` tests pass (2 tests × `mobile` and `desktop`); Playwright's summary also counts the
`setup` project's tests as passed, so the total is higher than 4; 0 failed. The trap then removes the stack and the
lock.

Also verify the animation visually, because Vitest cannot see it: before the script exits and the trap tears the
stack down, add a headed run (`pnpm exec playwright test e2e/race.spec.ts --headed --project desktop`) or take
screenshots a few frames apart after pressing Play on `/race?year=2026`, and watch the race play. Bars must slide
between places under unchanged labels; a bar that vanishes and re-enters under a new label is a failure. Report what
you saw.

- [ ] **Step 25: Commit**

```bash
git add frontend/src/features/race frontend/e2e/race.spec.ts
git commit -F - <<'EOF'
feat(race): add leaderboard race and bump chart page

Plays the /api/leaderboards/history frames (default: season points of the
chosen year) with play/pause/scrub, a live standings list and a rank bump chart.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
