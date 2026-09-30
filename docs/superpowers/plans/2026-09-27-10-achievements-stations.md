# Achievements, Trophies & Stations Implementation Plan (Sub-plan 10)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every implementer, reviewer and fix-loop agent runs on Opus (master Global Constraints). Each task is one branch, one worktree and one PR in a `gh stack` (master §0 step 5).

**Goal:** Ship the declarative achievement engine (tiered milestone families plus one-off trophies, evaluated in recompute step s50, with rarity and progress APIs), the station analytics (clustered Wilson CIs, eras, separators, leaders, shrunken per-shooter deltas, wind × station) with their read APIs, the dev-only imagen trophy-art tool and art run, and the Trophy Room, Trophy Case, "Trophies earned today", "Your next trophy" and Stations UI.

**Architecture:** Achievement definitions live in `analytics/achievements/*.py` sibling modules that `register()` frozen `Achievement` dataclasses at import time. `registry.load_all()` discovers them with `pkgutil`, and `evaluate_all(ctx)` turns them into `Award`s over an `AchContext` (the C7 frames plus per-shooter day series, sliceable by date and shooter). Recompute step `s50_achievements` replaces `achievements_awarded` on every pipeline run. Routes read that table and compute tier progress per request from a `data_version`-cached context. Station analytics are pure pandas over station-sheet hits (never `rounds.score`), loaded with SQL over the C4 tables. The frontend adds two feature folders (`features/achievements`, `features/stations`) that plug into the C10 route, profile-section, event-section and home-widget globs. `tools/trophy_art/` is a separate uv project that never ships in an image.

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 (`text()` over C4 table names) · Pydantic v2 · pandas · numpy · pytest/pytest-cov/respx · React 19 · TypeScript (strict) · TanStack Query v5 · React Router v7 · ECharts (via Plan 07's `ChartFrame`) · openapi-fetch · Vitest + Testing Library + MSW · Playwright · tools: httpx, Pillow, PyYAML, respx.

**Spec:** /Users/bryanmoran/code/sunday-clays/docs/superpowers/specs/2026-09-27-sunday-clays-design.md

**Master:** /Users/bryanmoran/code/sunday-clays/docs/superpowers/plans/2026-09-27-00-master.md

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
Plan 10 owns none of the master Review Focus items. #1, #2 and #5 belong to Plans 03 and 08, #3 to Plan 02, and #4 to Plans 06 and 09. #4's tie and multi-round rules reach trophies, so item 2 below applies them to achievements. The five plan-specific items:

1. **Future data leaking into a trophy.** Examples: `perfect_month` awarded before the month's closing event exists or depending on a held day after it, `giant_killer` using `mu_after`, a PB compared against a same-day round. Every award uses only data dated on or before its award date, so the awards up to date D are identical with or without later events. Each T2, T3 and T4b definition has its own no-leak test (`test_no_leak[<code>]` in Tasks 2, 3 and 5). `test_progress_as_of_matches_sliced_context` (Task 1) covers progress.
2. **Ties and multi-round days in trophies.** Two rounds on one day count once (`personal_bests`, `comeback`). Tied winners both earn `first_win` (min rank). A tied station top score earns no `station_top_gun`, and a tied hardest station awards both stations. Tests: `test_personal_best_counts_once_per_day` (Task 2), `test_first_win_ties_count` and `test_comeback_once_per_day_uses_best_round` (Task 3), `test_tied_top_gun_gets_no_award` and `test_tied_hardest_stations_award_both` (Task 5).
3. **Missing inputs.** An event without an `event_weather` row, NaN `mu_before` (skill not computed yet), or a station entry whose name never matched a shooter (`shooter_id` NULL) → no award and no crash. Tests: `test_weather_trophies_skip_events_without_weather` and `test_giant_killer_skips_missing_ratings` (Task 3), `test_unmatched_station_entries_earn_nothing` (Task 5).
4. **Rollback or rebuild leaves stale trophies.** s50 replaces every row of `achievements_awarded` on each run, so a trophy whose supporting data was rolled back disappears. Test: `test_s50_replaces_previous_awards` (Task 1).
5. **Degenerate station statistics.** A station that everyone always cleans (p = 1), an empty selection after a filter, or a single cluster must not divide by zero, and the CI stays inside [0, 1]. Tests: `test_perfect_station_ci_stays_in_unit_interval` and `test_empty_selection_returns_no_stations` (Task 4).

## Decisions
Choices made where the master is silent or self-contradictory. Cross-plan auditors should check the ones marked (X), because they touch another plan's surface.

1. **Metal of 6+ tier families.** C12 says "level 1 bronze … 5+ diamond (families with 6+ tiers put the extra lowest tier(s) at bronze)". Its illustrative `Tier(3, 1000, GOLD, …)` contradicts that parenthetical. The normative rule wins: `metal_for(level, n) = METALS[max(0, level − 1 − max(0, n − 5))]`. So `clays_broken` 100/500/1000/2500/5000/10000 = bronze, bronze, silver, gold, platinum, diamond, and every 5+ tier family ends at exactly one diamond.
2. **`Award.details` default.** It uses `field(default_factory=dict, hash=False)`, because a dataclass cannot take a mutable `{}` default. The semantics match C12.
3. **Registry additions beyond C12.**
   - Functions: `metal_for`, `make_tiers(thresholds, unit, *, singular=None)`, `evaluate_one`, `get`, `all_achievements`, `Trophy`/`trophies()`/`trophy(code)` and `rarity_pct`.
   - `ProgressOut` is a Pydantic model defined in `registry.py`, so the API can reuse it.
   - Tier labels are `f"{threshold:,} {unit}"`, with the singular form used for threshold 1.
4. **Per-shooter separability.** Tiered `value` functions must depend only on the shooter's own rows plus the shared events frame. `progress()` evaluates them on `ctx.for_shooter(id).until(as_of)`, so a profile request never evaluates all 332 shooters. All C12 families satisfy this.
5. **(X) AchContext and Plan 06 dtypes.**
   - `AchContext` holds the C7 frames exactly as `frames.load_*` return them, plus a derived `event_ts` column (`pd.to_datetime(event_date)`). The frames are passed unchanged to Plan 06's `streaks()`, `held_event_dates()` and `assign_classes()`.
   - `build_context` calls `inspect.unwrap(frames.load_*)`. The pipeline bumps `data_version` only after all steps finish, so a `@cached_by_data_version` memo on a loader could otherwise hand s50 frames from before s10/s30 wrote this run's metrics. Plan 06 T1's decorator uses `functools.wraps` (and Plan 06 D4 has s10/s30 call `cache.clear_cache()` around their writes; s50 calls it before reading), so unwrapping is a belt-and-braces guarantee that does not depend on step order.
   - The route context is `@cached_by_data_version def cached_context(session)`. The decorator deep-copies non-frame values on every hit (Plan 06 D3), so each request gets its own copy of the one `AchContext` built per `data_version`, frames included; routes only derive new contexts from it (`for_shooter`, `until`).
6. **(X) Station hits are loaded by SQL over C4 table and column names**, not through ORM class names, which C4 does not fix. Plan 06 T1's `frames.load_station_hits` returns the same rows (`STATION_HIT_COLUMNS`) but no `display_name`, which Task 4 needs. Task 1 (`context.load_station_entries`, `STATION_COLUMNS` ⊂ Plan 06's `STATION_HIT_COLUMNS`, same `Int64` ids) and Task 4 (`stations.load_station_frame`) each own one small query, because they run in parallel and cannot share a module.
7. **(X) Plan 10 reads and writes its tables with `sqlalchemy.text()`** over C4 names: `rounds`, `events`, `station_hits`, `station_layouts`, `shooter_profiles`, `shooter_aliases`, `rules`, `event_weather` and `achievements_awarded`.
8. **Repeatable one-offs.** `welcome_back`, `comeback`, `perfect_month`, `giant_killer`, `class_up`, `station_top_gun` and `hardest_station_clean` can be earned once per day. Every other one-off is awarded once, at the shooter's first qualifying event. Holder counts and rarity count distinct shooters.
9. **Categories, names and descriptions** are as registered in Tasks 2, 3 and 5. `sub_gauge` is `conditions`, `personal_bests` is `scoring`, and `doubleheader`, `joined_club` and `both_disciplines` are `milestone`. `art_key` equals the family code everywhere.
10. **`anniversary_1`/`anniversary_5`.** Awarded at the first attended event whose distance from the shooter's first event is in [365·k − 7, 365·k + 7] days (k = 1 gives the master's 358–372).
11. **`events` and `big_year`** count every date with ≥1 round, held or not. This matches the odometer's `events`.
12. **`new_year`** goes to the attendees of the first held event of each calendar year. **`four_seasons`** groups dates by season-year (December → next year) using `frames.season_label`.
13. **Competition trophies.**
    - The field size is the number of distinct shooters with rounds that day.
    - `first_win` and `podium` read best rounds only.
    - For `giant_killer`, the killer must outrank every co-top-rated shooter, and rows with NaN `mu_before` are ignored.
    - For `class_up`, each attended event is compared with the shooter's previous attended event.
14. **Station trophies.**
    - `station_top_gun` needs ≥5 entries on that day's sheet. Each shooter competes with their best entry. Unmatched entries compete but cannot win. One award per shooter-day lists every station won.
    - `hardest_station_clean` computes hit % over every sheet entry, including unmatched ones, with exact rational ties.
    - `station_cleaner` counts only entries linked to a shooter.
15. **Station eras.**
    - Eras are per station, one per active `station_reset` rule.
    - `GET /api/stations?era=` takes `current` (default) or `all`. A station's current era = its number of resets with `effective_date` ≤ today (`settings.timezone`).
    - `GET /api/stations/{no}` and `GET /api/shooters/{id}/stations` always use every era.
16. **Station statistics.**
    - The shrinkage field `p_f` includes the shooter's own entries.
    - κ = 2 × the median `target_count` of the field entries at that station on those days.
    - The separator uses the sheet total computed before any filter.
    - Wind bands are ordered by their smallest gust, and events without `event_weather` are excluded.
    - Leaders: top 5 per station in the overview and top 10 in the detail, ordered by hit % desc, targets desc, shooter_id.
17. **(X) Response model names are prefixed** (`Trophy*`, `Station*`, `ShooterStation*`) to avoid OpenAPI component collisions with other plans. C8 path templates are kept literally (`{id}`, `{date}`, `{no}`, `{code}`) through `Path(alias=…)`.
18. **Rarity and recent unlocks.** Rarity is rounded to 1 dp over `count(DISTINCT shooter_id) FROM rounds`. `GET /api/achievements` returns the 20 most recent unlocks. Trophy codes are `family:level` for tiers and the family code for one-offs.
19. **Trophy art.**
    - Manifest keys are `<art_key>` for one-offs and `<art_key>-<metal>` for tiers. One-off fallback icons are tinted with the accent `#E8A77A`.
    - The tool is a uv project with `[tool.uv] package = false` and flat modules at `tools/trophy_art/*.py`.
    - It adds a `check` subcommand, which Task 7 uses to confirm manifest coverage.
    - The default model is `z-image` (txt2img, real negatives), with seeds 101/202/303/404, size 1024, and the Idempotency-Key metal field `''` for one-offs.
20. **(X) Frontend dependencies on Plan 07.**
    - ECharts options are built in feature-local pure modules (`features/*/chartOptions.ts`), as Plan 08 D12 does for its special charts: Plan 07 T5's generic builders (`barOption`, `lineOption`, `heatmapOption` over `TabularData` + opts) have no per-bar colours, CI markers, per-cell `n` labels or step lines. The builders in `components/charts/builders/` are never edited. These modules follow the C10 builder rules: typed input, no string `tooltip.formatter` (only `valueFormatter`), and unit tests. They register what they need with `echarts/core` `use()`, imported as `registerECharts` because `eslint-plugin-react-hooks` treats a bare `use(...)` call as a React hook.
    - API calls are `unwrap(api.GET(path, init))`: `unwrap<T>(res: Promise<{data?, error?, response}>): Promise<T>` receives the openapi-fetch promise and returns the data or throws `ApiError`. This is the form Plans 08 and 09 use.
    - MSW handlers use `*/api/...` patterns (any origin) and stay branch-free, as in Plan 08 D4. Plan 10 owns the defaults for `/api/achievements*`, `/api/shooters/:id/achievements`, `/api/events/:date/achievements`, `/api/stations*` and `/api/shooters/:id/stations`; none overlaps a Plan 08 handler (`/api/shooters/:id`, `/api/events/:date` match one path segment only). A query with no id yet uses TanStack v5 `skipToken` rather than `enabled` plus a dummy path param, so no unreachable fallback branch counts against coverage.
21. **(X) Frontend URL state and styling.**
    - Page controls (`cat`, `era`, `st`) live in the query string through Plan 07 T4's `useUrlState(key, codec, default)` with its `enumCodec` and `intCodec` (C10 URL state; Plan 07 D13: missing or invalid → default, writing the default deletes the key, history `replace`). No page hand-rolls a codec or calls `useSearchParams` itself.
    - The global round-type filter comes from Plan 07 T4's `useRoundTypes(): [RoundTypeValue[], setter]` in `src/lib/roundTypes.ts`, bound to `useUrlState('rt', roundTypesCodec)`, which drops unknown values. `features/stations/api.ts` calls `const [roundTypes] = useRoundTypes()` and never parses `rt` itself, so the app has one `rt` reader with one parse. Every in-app link (to events, shooters, achievements, stations, …) takes its target from `useRoundTypeLink(path: string): To` (same file, Plan 07 T2) rather than a bare path string, so `?rt=` survives navigation (C10); it is a hook, so list rows use a small link component that calls it.
    - UI uses plain elements styled with the Plan 07 T1 `@theme` utilities named after the Global Constraints tokens (`bg-surface`, `bg-elevated`, `text-text-muted`, `border-outline-variant`, `bg-primary`, `text-accent`, `bg-accent`, `border-accent`) rather than `components/ui/*`. Plan 11 T5 copies Task 8's `TrophyCard.tsx` markup verbatim when it wraps the card, so that file's markup stays exactly as written here.
    - Nav icons are `lucide-react` components (`Trophy`, `Target`), and `nav` is typed `NavItem[]` from Plan 01 T2's `src/app/registry.ts`, as in Plans 07–09. Route paths are relative children of the `/` root (`'achievements'`, `'achievements/:code'`, `'stations'`; Plan 01 Decision 15, followed by Plan 07 D1), while nav paths, links and test-only route trees stay absolute.
22. **(X) Glob exports.**
    - `profileSection` Trophy Case: id `trophy-case`, order 60.
    - Stations `profileSection`: id `stations`, order 70.
    - `eventSection`: id `trophies-today`, order 60.
    - `homeWidget`: id `next-trophy`, slot `me`, order 30. Its `Component` takes the host's `{meId: number | null}` prop (Plan 08 D5).
    - Each export is typed with its host's Plan 08 D5 type through `import type` (`ProfileSection` from `features/shooters/sections.ts`, `EventSection` from `features/events/sections.ts`, `HomeWidget` from `features/home/widgets.ts`), which is erased at build time, so `tsc` checks the shape and no host module is imported at runtime or edited.
    - Section components take the Plan 08 D5 host props: `{shooterId: number}` for profile sections and `{date: string}` for event sections.
    - Each section renders a root with its own `aria-label` (distinct from the host's title), and e2e specs target those labels. The hosts wrap profile and event sections in a `Card` titled `title`, and render `me` widgets only once a "That's me" profile has loaded (Plan 08 D5, D6).
23. **e2e scope.** The home "Your next trophy" widget depends on the per-device "That's me" choice, whose control belongs to Plan 08. It is covered by Vitest and MSW, not e2e.
24. **`perfect_month` counts the month's held events up to its closing event.** The master dates the award at the closing event, the first held event on or after L (M's last calendar Sunday): L itself when L was held, otherwise the next held event. C12 requires every award to use only data dated on or before its award date. Non-Sunday event dates do occur (C3 `non_sunday_date`; the fixture has 2019-01-14 and 2019-02-01). If a held non-Sunday falls after a held L inside M, an award dated L cannot also require attendance on that later day. The master's dating and C12 win: only M's held events dated on or before the closing event count toward M, and the ≥ 3 minimum counts the same events. Dating the award at M's last held event instead would still leak. With data cut at L the month looks complete, so the award appears on L and then moves once the later day arrives. Tests: `test_perfect_month_held_day_after_the_closing_sunday_cannot_change_it` and `test_perfect_month_held_monday_that_closes_the_month_counts` (Task 2).
25. **Commands as written pass the gates.**
    - Python code blocks are already `ruff format`-clean at the project line lengths (backend 100, `tools/trophy_art` 120), and they pass `ruff check` and `mypy --strict` as written. The only suppressions are `# noqa: RUF001` on the spec's display name "Above Average ×3" and `# noqa: S608` on three test-only f-string queries that interpolate module constants.
    - Frontend focused runs use `pnpm exec vitest run <paths>`, and full checks use `pnpm test --coverage`. Under pnpm 10, `pnpm test -- …` forwards a literal `--`, and Vitest then ignores the paths and `--coverage` (Plan 01 Decision 6).
26. **(X) Local UI e2e runs follow Plan 08 D24.** Plans 08, 09 and 10 UI tasks run concurrently in global Wave 4, and every Compose stack publishes host port 8080. Plan 08 D24 defines the isolation pattern and Plan 09 D23 adopts it. Task 8 (Step 9) and Task 9 (Step 7) use it too.
    - Each task builds its own backend and frontend image tags (`TAG=10-7` for Task 8, `TAG=10-8` for Task 9) before it takes the lock. It never builds the shared `:ci` tags, which a concurrent worktree could rebuild under a running stack. It runs Compose as project `sc-$TAG` with `IMAGE_TAG=$TAG`.
    - The task holds the machine-wide lock directory `/tmp/sunday-clays-e2e.lock` for exactly one stack lifetime. `mkdir` is atomic and portable, and macOS has no `flock`. An `EXIT` trap runs `dc down -v` and removes the lock, so a failing run still releases it. A lock with no `docker ps --filter publish=8080` container behind it is left from a crashed run and should be `rmdir`ed.
    - There is no separate port-8080 wait. Every stack that can run at the same time as these two tasks takes the same lock. Plan 11's stacks only poll the port with `lsof`, but Plan 11 is global Wave 5, which starts after every Plan 10 UI task has merged (master Global waves).
    - The blocks keep the `(cd frontend && pnpm exec playwright install chromium)` line that Plan 08 D24's first-run steps carry (Plan 08 T1 Step 2, Plan 09 Task 5 Step 2). It runs before the lock and does nothing when the browser is already installed.
    - The CI `e2e` job (C11) is unchanged. It builds and runs `IMAGE_TAG=ci` on its own runner.

## File Structure
Backend (`backend/`):
- `src/sunday_clays/analytics/achievements/__init__.py`: package marker. Never imports siblings.
- `src/sunday_clays/analytics/achievements/context.py`: `AchContext` (frames, `event_ts`, `until`, `for_shooter`, `shooter_days`, `held_dates`, `streaks_at`, `classes_at`), `load_station_entries`, `build_context`, `cached_context`, `empty_value_frame`.
- `src/sunday_clays/analytics/achievements/registry.py`: C12 types (`Metal`, `Category`, `Tier`, `Award`, `Achievement`), `Trophy`, `ProgressOut`, `register`, `load_all`, evaluation, progress, rarity, metals and tiers.
- `src/sunday_clays/analytics/achievements/participation.py`: milestone families and participation/calendar one-offs (Task 2).
- `src/sunday_clays/analytics/achievements/scores.py`: `round_score`, `comeback`, `above_average_3` (Task 3).
- `src/sunday_clays/analytics/achievements/conditions.py`: `sub_gauge` and the weather trophies (Task 3).
- `src/sunday_clays/analytics/achievements/competition.py`: `first_win`, `podium`, `giant_killer`, `class_up` (Task 3).
- `src/sunday_clays/analytics/achievements/stations.py`: `station_cleaner`, `hardest_station_clean`, `station_top_gun` (Task 5).
- `src/sunday_clays/analytics/steps/s50_achievements.py`: recompute step 50, which replaces `achievements_awarded`.
- `src/sunday_clays/analytics/stations.py`: station loaders and pure station statistics (Task 4).
- `src/sunday_clays/api/routes/achievements.py`: the 4 achievement endpoints and their response models.
- `src/sunday_clays/api/routes/stations.py`: the 3 station endpoints and their response models.
- Unit tests:
  - `tests/unit/analytics/achievements/conftest.py`: `CtxBuilder` and the `ctx_builder`, `isolated_registry` and `no_leak` fixtures.
  - `tests/unit/analytics/achievements/test_ach_{context,registry,participation,scores,conditions,competition,stations}.py`
  - `tests/unit/analytics/test_station_analytics.py`
- Integration tests:
  - `tests/integration/achievements/conftest.py`: `isolated_registry` and `toy_trophies` for the fx world.
  - `tests/integration/achievements/test_s50_achievements.py`, `test_achievements_routes.py`, `test_ach_participation_golden.py`, `test_ach_scoring_golden.py`, `test_ach_stations_golden.py`
  - `tests/integration/stations/test_station_routes.py`

Tools (`tools/trophy_art/`, Task 6 and Task 7):
- `pyproject.toml`, `uv.lock`, `.gitignore`: the standalone uv project.
- `manifest.yaml`: one prompt per art_key × metal.
- `selection.json`: the user's picks.
- `manifest.py`: manifest loading and target stems.
- `client.py`: the imagen HTTP client.
- `process.py`: medallion processing to WebP.
- `contact_sheet.py`: the HTML contact sheet.
- `cli.py`: the `generate|sheet|select|build|check` commands.
- `tests/test_{manifest,client,process,contact_sheet,cli}.py`, plus `tests/test_repo_art.py` (Task 7).
- `.github/workflows/ci.yml` (modified): the `tools` job, added to `ci-ok.needs`.

Frontend (`frontend/`):
- `src/features/achievements/`:
  - `metals.ts` and `components/TrophyIcon.tsx`: metal colours and the SVG fallback (Task 6).
  - `trophyArt.gen.ts`: the generated art manifest (empty in Task 6, filled in Task 7).
  - `api.ts`, `labels.ts`, `chartOptions.ts`, `mocks.ts`, `routes.tsx`
  - `components/TrophyCard.tsx`, `components/ProgressBar.tsx`
  - `pages/TrophyRoomPage.tsx`, `pages/TrophyDetailPage.tsx`
  - `TrophyCase.tsx` + `profileSection.tsx`, `TrophiesToday.tsx` + `eventSection.tsx`, `NextTrophy.tsx` + `homeWidget.tsx`
  - Tests next to each file (Task 8).
- `src/features/stations/`: `api.ts`, `format.ts`, `chartOptions.ts`, `mocks.ts`, `routes.tsx`, `pages/StationsPage.tsx`, `StationBreakdown.tsx` + `profileSection.tsx`, and tests (Task 9).
- `public/trophies/*.webp`: 256 px and `@128` medallions (Task 7).
- `e2e/achievements.spec.ts`, `e2e/stations.spec.ts`

## Waves
Master line (Plan 10): `Waves: {T1, T4a, T5} → {T2, T3, T4b, T8 (after Plan 08 T2a)} → {T6 (needs user), T7 (after Plan 08 T1, T2a, T4)}.`

In this plan's task numbers: {Task 1, Task 4, Task 6} → {Task 2, Task 3, Task 5, Task 9 (after Plan 08 T2a)} → {Task 7 (needs user), Task 8 (after Plan 08 T1, T2a, T4)}. Global wave: Wave 4. Nothing waits on Task 7, because `TrophyIcon` falls back to SVG.

---

### Task 1: Achievement framework, s50 step and achievement routes (master Plan 10 T1)

**Context:** This task builds the achievement engine every other trophy task plugs into. It ships no real trophies: tests register toy achievements into an isolated registry.
- Contract: C12 (types, `register`, `load_all`, `evaluate_all`, `progress`), C6 (recompute step order 50), C8 (the four achievement endpoints) and C7 (frames, no-leak).
- TDD for every change.
- Backend coverage must stay ≥90% lines and branches.
- `ruff check`, `ruff format --check` and `mypy --strict src` must be clean.
- Unit tests never touch the DB. Integration tests use the committed-fixtures world (`fx_session`, `fx_viewer_client`) and must not run the worker.

**Branch:** `task/10-1-achievement-framework`

**Depends on:**
- Plan 06 T1 (`frames`, `cache`, autouse cache-clear fixture), T2 (s10 metrics), T4 (`classes.assign_classes`), T6 (`streaks`).
- Plan 05 T3 (`event_weather` columns in `load_rounds`).
- Plan 03 T6 (`fx_session`) and T7 (`pipeline`).
- Plan 04 T1 (`fx_viewer_client`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/achievements/__init__.py`
- Create: `backend/src/sunday_clays/analytics/achievements/context.py`
- Create: `backend/src/sunday_clays/analytics/achievements/registry.py`
- Create: `backend/src/sunday_clays/analytics/steps/s50_achievements.py`
- Create: `backend/src/sunday_clays/api/routes/achievements.py`
- Test: `backend/tests/unit/analytics/achievements/conftest.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_context.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_registry.py`
- Test: `backend/tests/integration/achievements/conftest.py`
- Test: `backend/tests/integration/achievements/test_s50_achievements.py`
- Test: `backend/tests/integration/achievements/test_achievements_routes.py`

**Interfaces:**
- Consumes (exact):
  - `sunday_clays.analytics.frames` (Plan 06 T1; every date is a `datetime.date` object, object dtype; every loader is `@cached_by_data_version`, whose wrapper uses `functools.wraps`, so `inspect.unwrap` reaches the plain loader):
    - `ROUND_COLUMNS`: the C7 round columns, then `gauge` (NULL `gauge_class` → `"unspecified"`) and `held` (= the event's `results_complete`).
    - `EVENT_COLUMNS`: the C4 `events` columns (`event_date, round_type, round_type_source, head_count, n_rounds, n_shooters, has_scores, has_stations, results_complete`), then the `event_metrics` columns (`n, median, mean, stdev, top_score, difficulty`), then the `event_weather` columns (`temp_f, apparent_f, precip_in, wind_mph, gust_mph, wind_dir_deg, cloud_pct, humidity_pct, pressure_hpa, condition`).
    - `load_rounds(session) -> pd.DataFrame` with columns `ROUND_COLUMNS`. `is_best_round` is a plain bool (False until s10 runs); `event_rank` is float, NaN for non-best rounds; metric and weather columns are NaN until computed.
    - `load_events(session) -> pd.DataFrame` with columns `EVENT_COLUMNS`.
    - `load_rating_history(session) -> pd.DataFrame`: `RATING_COLUMNS` = `[shooter_id, event_date, mu, var]`.
  - `sunday_clays.analytics.streaks`:
    - `held_event_dates(events: pd.DataFrame, as_of: date | None) -> list[date]`
    - `streaks(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date | None) -> pd.DataFrame[shooter_id, current_streak, longest_streak]`
  - `sunday_clays.analytics.classes.assign_classes(history: pd.DataFrame, rounds: pd.DataFrame, as_of: date) -> pd.DataFrame[shooter_id, mu, klass]`
  - `sunday_clays.analytics.cache.cached_by_data_version`, used as `@cached_by_data_version def f(session: Session) -> T`.
  - `sunday_clays.analytics.pipeline.RecomputeStep(name: str, order: int, run: Callable[[Session], None])` and `discover_steps() -> list[RecomputeStep]`.
  - `sunday_clays.db.get_session`
  - `sunday_clays.domain.errors.NotFoundError(code: str, message: str)` (404).
  - pytest fixtures: `fx_session`, `fx_viewer_client`, and the autouse cache clear.
- Produces (later tasks rely on these exact names):
  - `context.py`:
    - `STATION_COLUMNS = ("event_date", "station_no", "target_count", "sheet_id", "entry_row", "shooter_id", "round_id", "hits")`
    - `class AchContext` (frozen dataclass):
      - Fields: `rounds`, `events`, `station_hits`, `rating_history`, `as_of: date | None`. Every frame carries an extra `event_ts: datetime64` column.
      - `from_frames(*, rounds, events, station_hits, rating_history, as_of=None) -> AchContext`
      - `until(as_of: date | None) -> AchContext`
      - `for_shooter(shooter_id: int) -> AchContext`
      - `shooter_days -> pd.DataFrame`: one row per (shooter, date), columns `shooter_id, event_ts, event_date, n_rounds, day_best, day_sum, best_round_id, n_events, cum_rounds, cum_sum, prior_rounds, prior_sum, prior_best, prev_ts, prev_day_best`, sorted by shooter then date. `prior_*` covers earlier dates only.
      - `held_dates() -> list[date]`
      - `streaks_at(day: date) -> pd.DataFrame`
      - `classes_at(day: date) -> pd.DataFrame`
    - `empty_value_frame() -> pd.DataFrame`
    - `load_station_entries(session) -> pd.DataFrame`
    - `build_context(session) -> AchContext`
    - `cached_context(session) -> AchContext`
  - `registry.py`:
    - C12 `Metal`, `Category`, `Tier`, `Award`, `Achievement`, `register`, `load_all`, `evaluate_all`, `progress`
    - `metal_for(level: int, n_tiers: int) -> Metal`
    - `make_tiers(thresholds: Sequence[int], unit: str, *, singular: str | None = None) -> tuple[Tier, ...]`
    - `evaluate_one(a: Achievement, ctx: AchContext) -> list[Award]`
    - `get(code: str) -> Achievement` (raises `KeyError`)
    - `all_achievements() -> list[Achievement]`
    - `@dataclass(frozen=True) class Trophy: code: str; achievement: Achievement; tier: Tier | None`
    - `trophies() -> list[Trophy]`
    - `trophy(code: str) -> Trophy | None`
    - `rarity_pct(holders: int, n_shooters: int) -> float`
    - `class ProgressOut(BaseModel)`: `code, name, description, category, art_key, value, earned_level, earned_metal, earned_label, next_level, next_threshold, next_label, next_metal, fraction`
  - `analytics/steps/s50_achievements.py`: `STEP = RecomputeStep(name="achievements", order=50, run=run)`. `run` calls `cache.clear_cache()` before reading: a memo entry could otherwise be keyed at an uncommitted `data_version` from a rolled-back worker transaction.
  - `api/routes/achievements.py`:
    - `GET /api/achievements -> AchievementsOut{n_shooters, trophies: list[TrophyOut], recent: list[TrophyAwardOut]}`
    - `GET /api/achievements/{code} -> AchievementDetailOut{trophy, holders: list[TrophyHolderOut]}`
    - `GET /api/shooters/{id}/achievements -> ShooterAchievementsOut{shooter_id, display_name, earned: list[EarnedTrophyOut], progress: list[ProgressOut], locked: list[LockedTrophyOut]}`
    - `GET /api/events/{date}/achievements -> EventAchievementsOut{event_date, awards: list[TrophyAwardOut]}`
    - Error codes (404): `achievement_not_found`, `shooter_not_found`, `event_not_found`.
  - Test fixtures in `tests/unit/analytics/achievements/conftest.py`:
    - `ctx_builder` returns the `CtxBuilder` class. Its methods are `.round(shooter_id, event_date, score, **cols)`, `.event(event_date, **cols)`, `.station(shooter_id, event_date, station_no, hits, *, entry_row, target_count=7, round_id=None)`, `.rating(shooter_id, event_date, mu, var=4.0)` and `.build() -> AchContext`. Its rounds and events frames carry exactly Plan 06's `frames.ROUND_COLUMNS` and `frames.EVENT_COLUMNS`.
    - `isolated_registry`
    - `no_leak(code, ctx, cut) -> tuple[int, int]`, returning the number of awards on or before the cut and after it.

- [ ] **Step 1: Write the shared unit-test fixtures and the failing context tests**

Create `backend/tests/unit/analytics/achievements/conftest.py`:

```python
"""Shared fixtures for achievement unit tests (no DB).

CtxBuilder produces frames shaped like frames.load_* output: Plan 06's ROUND_COLUMNS and
EVENT_COLUMNS, event_date as datetime.date. Registry imports are local to the fixtures so context
tests run before registry.py exists.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.achievements.context import STATION_COLUMNS, AchContext
from sunday_clays.analytics.frames import EVENT_COLUMNS, ROUND_COLUMNS

# Round columns that frames.load_rounds takes from the event's event_weather row.
_WEATHER = (
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "condition",
)
_METRICS = (
    "field_median",
    "adjusted",
    "percentile",
    "expected",
    "residual",
    "mu_before",
    "mu_after",
)
_DERIVED = ("ordinal", "is_best_round", "event_rank")


class CtxBuilder:
    """Fluent builder: rounds, events (weather keys ride on events), station entries, ratings."""

    def __init__(self) -> None:
        self._rounds: list[dict[str, Any]] = []
        self._events: dict[date, dict[str, Any]] = {}
        self._stations: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []

    def round(self, shooter_id: int, event_date: date, score: int, **cols: Any) -> CtxBuilder:
        self._rounds.append(
            {"shooter_id": shooter_id, "event_date": event_date, "score": score, **cols}
        )
        return self

    def event(self, event_date: date, **cols: Any) -> CtxBuilder:
        self._events.setdefault(event_date, {}).update(cols)
        return self

    def station(
        self,
        shooter_id: int | None,
        event_date: date,
        station_no: int,
        hits: int,
        *,
        entry_row: int,
        target_count: int = 7,
        round_id: int | None = None,
    ) -> CtxBuilder:
        self._stations.append(
            {
                "event_date": event_date,
                "station_no": station_no,
                "target_count": target_count,
                "sheet_id": 1,
                "entry_row": entry_row,
                "shooter_id": shooter_id,
                "round_id": round_id,
                "hits": hits,
            }
        )
        return self

    def rating(self, shooter_id: int, event_date: date, mu: float, var: float = 4.0) -> CtxBuilder:
        self._history.append(
            {"shooter_id": shooter_id, "event_date": event_date, "mu": mu, "var": var}
        )
        return self

    def build(self) -> AchContext:
        events = self._events_frame()
        return AchContext.from_frames(
            rounds=self._rounds_frame(events),
            events=events,
            station_hits=self._stations_frame(),
            rating_history=pd.DataFrame(
                self._history, columns=["shooter_id", "event_date", "mu", "var"]
            ),
        )

    def _events_frame(self) -> pd.DataFrame:
        """Plan 06 EVENT_COLUMNS: event_metrics and event_weather columns start NaN."""
        dates = sorted({r["event_date"] for r in self._rounds} | set(self._events))
        rows: list[dict[str, Any]] = []
        for day in dates:
            same_day = [r for r in self._rounds if r["event_date"] == day]
            row: dict[str, Any] = dict.fromkeys(EVENT_COLUMNS, np.nan)
            row.update(
                {
                    "event_date": day,
                    "round_type": "unknown",
                    "round_type_source": "none",
                    "n_rounds": len(same_day),
                    "n_shooters": len({r["shooter_id"] for r in same_day}),
                    "has_scores": bool(same_day),
                    "has_stations": any(s["event_date"] == day for s in self._stations),
                    "results_complete": bool(same_day),
                    "condition": None,
                }
            )
            row.update(self._events.get(day, {}))
            rows.append(row)
        return pd.DataFrame(rows, columns=list(EVENT_COLUMNS))

    def _rounds_frame(self, events: pd.DataFrame) -> pd.DataFrame:
        """Plan 06 ROUND_COLUMNS: `held` mirrors the event's results_complete; `gauge` derived."""
        by_date = events.set_index("event_date")
        rows: list[dict[str, Any]] = []
        for round_id, given in enumerate(self._rounds, start=1):
            sid, day = given["shooter_id"], given["event_date"]
            row: dict[str, Any] = {
                "round_id": round_id,
                "event_date": day,
                "shooter_id": sid,
                "name_key": f"shooter {sid}",
                "display_name": f"Shooter {sid}",
                "ordinal": np.nan,
                "score": given["score"],
                "gauge_class": None,
                "status": "member",
                "shooter_status": "member",
                "round_type": by_date.at[day, "round_type"],
                "event_rank": np.nan,
                "is_best_round": False,
                "held": bool(by_date.at[day, "results_complete"]),
            }
            row.update(dict.fromkeys(_METRICS, np.nan))
            row.update({key: by_date.at[day, key] for key in _WEATHER})
            row.update({k: v for k, v in given.items() if k not in _DERIVED})
            rows.append(row)
        frame = pd.DataFrame(rows, columns=[c for c in ROUND_COLUMNS if c != "gauge"])
        if frame.empty:
            return frame.assign(gauge=pd.Series(dtype=object))[list(ROUND_COLUMNS)]
        ordered = frame.sort_values(["score", "round_id"], ascending=[False, True])
        frame["ordinal"] = ordered.groupby(["event_date", "shooter_id", "name_key"]).cumcount() + 1
        best = (
            frame.sort_values(["score", "name_key", "ordinal"], ascending=[False, True, True])
            .groupby(["event_date", "shooter_id"])
            .head(1)
            .index
        )
        frame["is_best_round"] = frame.index.isin(best)
        frame["event_rank"] = (
            frame[frame["is_best_round"]]
            .groupby("event_date")["score"]
            .rank(method="min", ascending=False)
        )
        for index, given in zip(frame.index, self._rounds, strict=True):
            for key in _DERIVED:
                if key in given:
                    frame.at[index, key] = given[key]
        frame["gauge"] = frame["gauge_class"].fillna("unspecified")
        return frame[list(ROUND_COLUMNS)]

    def _stations_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame(self._stations, columns=list(STATION_COLUMNS))
        for column in ("shooter_id", "round_id"):
            frame[column] = frame[column].astype("Int64")
        return frame


@pytest.fixture
def ctx_builder() -> type[CtxBuilder]:
    return CtxBuilder


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """An empty registry for toy achievements. Real modules are imported first so that a later
    load_all() never re-imports them into the temporary dict."""
    from sunday_clays.analytics.achievements import registry

    registry.load_all()
    fresh: dict[str, Any] = {}
    monkeypatch.setattr(registry, "_REGISTRY", fresh)
    return fresh


def _award_key(award: Any) -> tuple[Any, ...]:
    details = json.dumps(dict(award.details), sort_keys=True, default=str)
    return (award.shooter_id, award.code, award.event_date, award.round_id, details)


def _value_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[["shooter_id", "event_date", "value"]].copy()
    out["shooter_id"] = out["shooter_id"].astype("int64")
    out["event_date"] = pd.to_datetime(out["event_date"])
    out["value"] = out["value"].astype(float)
    return out.sort_values(["shooter_id", "event_date"]).reset_index(drop=True)


@pytest.fixture
def no_leak() -> Callable[[str, AchContext, date], tuple[int, int]]:
    """Asserts that `code` awards (and, if tiered, its value series) up to `cut` are identical when
    computed on the full context or on ctx.until(cut). Returns (#awards <= cut, #awards > cut)."""
    from sunday_clays.analytics.achievements import registry

    def check(code: str, ctx: AchContext, cut: date) -> tuple[int, int]:
        achievement = registry.get(code)
        full = registry.evaluate_one(achievement, ctx)
        before = sorted(_award_key(w) for w in full if w.event_date <= cut)
        sliced = sorted(_award_key(w) for w in registry.evaluate_one(achievement, ctx.until(cut)))
        assert before == sliced
        if achievement.value is not None:
            full_values = _value_frame(achievement.value(ctx))
            cut_values = _value_frame(achievement.value(ctx.until(cut)))
            kept = full_values[full_values["event_date"] <= pd.Timestamp(cut)].reset_index(
                drop=True
            )
            pd.testing.assert_frame_equal(kept, cut_values)
        return len(before), len(full) - len(before)

    return check
```

Create `backend/tests/unit/analytics/achievements/test_ach_context.py`:

```python
"""AchContext slicing and per-shooter day series (Plan 10 T1)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def test_until_drops_later_rows_from_every_frame(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(1, sun(1), 41)
        .round(1, sun(2), 42)
        .station(1, sun(2), 4, 7, entry_row=10)
        .rating(1, sun(2), 31.0)
        .event(sun(3), has_scores=False, results_complete=False, head_count=12)
        .build()
    )
    cut = ctx.until(sun(1))
    assert sorted(set(cut.rounds["event_date"])) == [sun(0), sun(1)]
    assert sorted(set(cut.events["event_date"])) == [sun(0), sun(1)]
    assert cut.station_hits.empty
    assert cut.rating_history.empty
    assert cut.as_of == sun(1)


def test_until_none_returns_same_context(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 40).build()
    assert ctx.until(None) is ctx


def test_shooter_days_prior_columns_use_earlier_dates_only(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(1, sun(0), 44)
        .round(1, sun(1), 30)
        .round(1, sun(2), 47)
        .build()
    )
    days = ctx.shooter_days
    assert list(days["event_date"]) == [sun(0), sun(1), sun(2)]
    assert list(days["n_rounds"]) == [2, 1, 1]
    assert list(days["day_best"]) == [44, 30, 47]
    assert list(days["day_sum"]) == [84, 30, 47]
    assert list(days["n_events"]) == [1, 2, 3]
    assert list(days["cum_rounds"]) == [2, 3, 4]
    assert list(days["prior_rounds"]) == [0, 2, 3]
    assert list(days["prior_sum"]) == [0, 84, 114]
    assert pd.isna(days["prior_best"].iloc[0])
    assert list(days["prior_best"].iloc[1:]) == [44.0, 44.0]
    assert pd.isna(days["prev_day_best"].iloc[0])
    assert list(days["prev_day_best"].iloc[1:]) == [44.0, 30.0]
    assert pd.isna(days["prev_ts"].iloc[0])
    assert days["prev_ts"].iloc[2] == pd.Timestamp(sun(1))


def test_best_round_id_prefers_higher_score_then_lower_ordinal(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 38)  # round 1
        .round(1, sun(0), 45)  # round 2: best
        .round(2, sun(0), 40)  # round 3: ordinal 1, best on the tie
        .round(2, sun(0), 40)  # round 4: ordinal 2
        .build()
    )
    days = ctx.shooter_days.set_index("shooter_id")
    assert days.loc[1, "best_round_id"] == 2
    assert days.loc[2, "best_round_id"] == 3


def test_for_shooter_keeps_every_event(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(2, sun(1), 41)
        .station(2, sun(1), 4, 7, entry_row=10)
        .station(None, sun(1), 4, 3, entry_row=11)
        .rating(2, sun(1), 30.0)
        .build()
    )
    own = ctx.for_shooter(1)
    assert set(own.rounds["shooter_id"]) == {1}
    assert sorted(own.events["event_date"]) == [sun(0), sun(1)]
    assert own.station_hits.empty
    assert own.rating_history.empty
    assert list(ctx.for_shooter(2).station_hits["entry_row"]) == [10]


def test_from_frames_accepts_datetime64_event_dates(ctx_builder):
    base = ctx_builder().round(1, sun(0), 40).build()
    ctx = AchContext.from_frames(
        rounds=base.rounds.drop(columns=["event_ts"]).assign(
            event_date=pd.to_datetime(base.rounds["event_date"])
        ),
        events=base.events.drop(columns=["event_ts"]),
        station_hits=base.station_hits.drop(columns=["event_ts"]),
        rating_history=base.rating_history.drop(columns=["event_ts"]),
    )
    assert list(ctx.shooter_days["event_date"]) == [sun(0)]


def test_held_dates_skip_incomplete_events(ctx_builder):
    ctx = (
        ctx_builder()
        .round(1, sun(0), 40)
        .round(1, sun(1), 40)
        .event(sun(1), results_complete=False)
        .build()
    )
    assert ctx.held_dates() == [sun(0)]


def test_shooter_days_of_empty_context_has_typed_columns(ctx_builder):
    days = ctx_builder().build().shooter_days
    assert days.empty
    assert str(days["event_ts"].dtype).startswith("datetime64")
```

- [ ] **Step 2: Run the context tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_context.py -v`
Expected: FAIL. Collection stops with `ImportError while loading conftest … ModuleNotFoundError: No module named 'sunday_clays.analytics.achievements'`.

- [ ] **Step 3: Implement the context**

Create `backend/src/sunday_clays/analytics/achievements/__init__.py`:

```python
"""Achievements & trophies (C12).

Definitions live in sibling modules discovered by registry.load_all().
"""
```

Create `backend/src/sunday_clays/analytics/achievements/context.py`:

```python
"""AchContext (C12): the frames achievement definitions read, sliceable by date and by shooter."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.classes import assign_classes
from sunday_clays.analytics.streaks import held_event_dates, streaks

STATION_COLUMNS: tuple[str, ...] = (
    "event_date",
    "station_no",
    "target_count",
    "sheet_id",
    "entry_row",
    "shooter_id",
    "round_id",
    "hits",
)

_DAY_DTYPES: dict[str, str] = {
    "shooter_id": "int64",
    "event_ts": "datetime64[ns]",
    "event_date": "object",
    "n_rounds": "int64",
    "day_best": "int64",
    "day_sum": "int64",
    "best_round_id": "int64",
    "n_events": "int64",
    "cum_rounds": "int64",
    "cum_sum": "int64",
    "prior_rounds": "int64",
    "prior_sum": "int64",
    "prior_best": "float64",
    "prev_ts": "datetime64[ns]",
    "prev_day_best": "float64",
}
_VALUE_DTYPES: dict[str, str] = {
    "shooter_id": "int64",
    "event_date": "datetime64[ns]",
    "value": "float64",
}

_STATION_SQL = text(
    """
    SELECT h.event_date, h.station_no, l.target_count, h.sheet_id, h.entry_row,
           h.shooter_id, h.round_id, h.hits
    FROM station_hits h
    JOIN station_layouts l ON l.event_date = h.event_date AND l.station_no = h.station_no
    ORDER BY h.event_date, h.entry_row, h.station_no
    """
)


def _empty(dtypes: Mapping[str, str]) -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in dtypes.items()})


def empty_value_frame() -> pd.DataFrame:
    """The empty long frame [shooter_id, event_date, value] a tiered value function returns."""
    return _empty(_VALUE_DTYPES)


def _with_ts(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["event_ts"] = pd.to_datetime(out["event_date"])
    return out


def _cut(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    return frame[frame["event_ts"] <= pd.Timestamp(as_of)]


def _shooter_days(rounds: pd.DataFrame) -> pd.DataFrame:
    if rounds.empty:
        return _empty(_DAY_DTYPES)
    ordered = rounds.sort_values(
        ["shooter_id", "event_ts", "score", "name_key", "ordinal"],
        ascending=[True, True, False, True, True],
        kind="stable",
    )
    days = (
        ordered.groupby(["shooter_id", "event_ts"], sort=True)
        .agg(
            n_rounds=("score", "size"),
            day_best=("score", "max"),
            day_sum=("score", "sum"),
            best_round_id=("round_id", "first"),
        )
        .reset_index()
    )
    days["event_date"] = days["event_ts"].dt.date
    by_shooter = days.groupby("shooter_id", sort=False)
    days["n_events"] = by_shooter.cumcount() + 1
    days["cum_rounds"] = by_shooter["n_rounds"].cumsum()
    days["cum_sum"] = by_shooter["day_sum"].cumsum()
    days["prior_rounds"] = days["cum_rounds"] - days["n_rounds"]
    days["prior_sum"] = days["cum_sum"] - days["day_sum"]
    days["prior_best"] = by_shooter["day_best"].transform(lambda s: s.cummax().shift(1))
    days["prev_ts"] = by_shooter["event_ts"].shift(1)
    days["prev_day_best"] = by_shooter["day_best"].shift(1).astype(float)
    return days[list(_DAY_DTYPES)]


@dataclass(frozen=True, eq=False)
class AchContext:
    """Frames as frames.load_* return them, each with an extra `event_ts` (datetime64) column."""

    rounds: pd.DataFrame
    events: pd.DataFrame
    station_hits: pd.DataFrame
    rating_history: pd.DataFrame
    as_of: date | None = None
    _memo: dict[Any, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_frames(
        cls,
        *,
        rounds: pd.DataFrame,
        events: pd.DataFrame,
        station_hits: pd.DataFrame,
        rating_history: pd.DataFrame,
        as_of: date | None = None,
    ) -> AchContext:
        return cls(
            rounds=_with_ts(rounds),
            events=_with_ts(events),
            station_hits=_with_ts(station_hits),
            rating_history=_with_ts(rating_history),
            as_of=as_of,
        )

    def until(self, as_of: date | None) -> AchContext:
        """Only data dated <= as_of (None → this context unchanged)."""
        if as_of is None:
            return self
        return AchContext(
            rounds=_cut(self.rounds, as_of),
            events=_cut(self.events, as_of),
            station_hits=_cut(self.station_hits, as_of),
            rating_history=_cut(self.rating_history, as_of),
            as_of=as_of,
        )

    def for_shooter(self, shooter_id: int) -> AchContext:
        """One shooter's rows; events stay whole (held events are club-wide)."""
        linked = self.station_hits["shooter_id"].eq(shooter_id).fillna(False).astype(bool)
        return AchContext(
            rounds=self.rounds[self.rounds["shooter_id"] == shooter_id],
            events=self.events,
            station_hits=self.station_hits[linked],
            rating_history=self.rating_history[self.rating_history["shooter_id"] == shooter_id],
            as_of=self.as_of,
        )

    @property
    def shooter_days(self) -> pd.DataFrame:
        cached: pd.DataFrame | None = self._memo.get("shooter_days")
        if cached is None:
            cached = _shooter_days(self.rounds)
            self._memo["shooter_days"] = cached
        return cached

    def held_dates(self) -> list[date]:
        return sorted(held_event_dates(self.events, self.as_of))

    def streaks_at(self, day: date) -> pd.DataFrame:
        key = ("streaks", day)
        if key not in self._memo:
            self._memo[key] = streaks(self.rounds, self.events, day)
        result: pd.DataFrame = self._memo[key]
        return result

    def classes_at(self, day: date) -> pd.DataFrame:
        key = ("classes", day)
        if key not in self._memo:
            self._memo[key] = assign_classes(self.rating_history, self.rounds, day)
        result: pd.DataFrame = self._memo[key]
        return result


def load_station_entries(session: Session) -> pd.DataFrame:
    """station_hits joined to its layout's target_count; shooter_id/round_id are nullable Int64."""
    rows = [dict(r) for r in session.execute(_STATION_SQL).mappings()]
    frame = pd.DataFrame(rows, columns=list(STATION_COLUMNS))
    for column in ("shooter_id", "round_id"):
        frame[column] = frame[column].astype("Int64")
    return frame


def build_context(session: Session) -> AchContext:
    """Fresh frames for s50. Loaders are unwrapped so a @cached_by_data_version memo can never
    return frames from before s10/s30 wrote this pipeline run's metrics (data_version is bumped
    only after the last step)."""
    return AchContext.from_frames(
        rounds=inspect.unwrap(frames.load_rounds)(session),
        events=inspect.unwrap(frames.load_events)(session),
        station_hits=load_station_entries(session),
        rating_history=inspect.unwrap(frames.load_rating_history)(session),
    )


@cached_by_data_version
def cached_context(session: Session) -> AchContext:
    """The context the read routes use; rebuilt once per data_version."""
    return build_context(session)
```

- [ ] **Step 4: Run the context tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_context.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Write the failing registry tests**

Create `backend/tests/unit/analytics/achievements/test_ach_registry.py`:

```python
"""Registry: metals, tiers, registration, evaluation rules, progress, discovery (Plan 10 T1)."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import achievements as achievements_pkg
from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category, Metal, Tier


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def rounds_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"],
            "event_date": days["event_ts"],
            "value": days["cum_rounds"].astype(float),
        }
    )


def forty_plus(code: str) -> Callable[[AchContext], Iterator[Award]]:
    def evaluate(ctx: AchContext) -> Iterator[Award]:
        hits = ctx.rounds[ctx.rounds["score"] >= 40].sort_values("round_id")
        for sid, day, rid in zip(
            hits["shooter_id"], hits["event_date"], hits["round_id"], strict=True
        ):
            yield Award(int(sid), code, day, int(rid), {"score": 40})

    return evaluate


def toy_tiered(code: str = "toy_rounds") -> Achievement:
    return Achievement(
        code=code,
        name="Toy Rounds",
        description="Rounds shot.",
        category=Category.MILESTONE,
        art_key=code,
        tiers=registry.make_tiers((1, 2, 5), "rounds", singular="round"),
        value=rounds_value,
    )


def toy_one_off(code: str = "toy_forty", *, repeatable: bool = False) -> Achievement:
    return Achievement(
        code=code,
        name="Toy Forty",
        description="Shot 40+.",
        category=Category.SCORING,
        art_key=code,
        evaluate=forty_plus(code),
        repeatable=repeatable,
    )


@pytest.mark.parametrize(
    ("n_tiers", "expected"),
    [
        (3, [Metal.BRONZE, Metal.SILVER, Metal.GOLD]),
        (4, [Metal.BRONZE, Metal.SILVER, Metal.GOLD, Metal.PLATINUM]),
        (5, [Metal.BRONZE, Metal.SILVER, Metal.GOLD, Metal.PLATINUM, Metal.DIAMOND]),
        (6, [Metal.BRONZE, Metal.BRONZE, Metal.SILVER, Metal.GOLD, Metal.PLATINUM, Metal.DIAMOND]),
        (8, [Metal.BRONZE] * 4 + [Metal.SILVER, Metal.GOLD, Metal.PLATINUM, Metal.DIAMOND]),
    ],
)
def test_metal_for_puts_extra_lowest_tiers_at_bronze(n_tiers, expected):
    assert [registry.metal_for(level, n_tiers) for level in range(1, n_tiers + 1)] == expected


def test_make_tiers_formats_labels_with_thousands_and_singular():
    assert registry.make_tiers((1, 1000, 10000), "events", singular="event") == (
        Tier(1, 1.0, Metal.BRONZE, "1 event"),
        Tier(2, 1000.0, Metal.SILVER, "1,000 events"),
        Tier(3, 10000.0, Metal.GOLD, "10,000 events"),
    )


def test_register_rejects_duplicate_code(isolated_registry):
    registry.register(toy_tiered())
    with pytest.raises(ValueError, match="duplicate"):
        registry.register(toy_tiered())


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        (
            Achievement(
                code="",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
                evaluate=forty_plus(""),
            ),
            "invalid achievement code",
        ),
        (
            Achievement(
                code="a:b",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
                evaluate=forty_plus("a:b"),
            ),
            "invalid achievement code",
        ),
        (
            Achievement(
                code="tiered_without_value",
                name="x",
                description="x",
                category=Category.MILESTONE,
                art_key="x",
                tiers=registry.make_tiers((1,), "x"),
            ),
            "needs a value function",
        ),
        (
            Achievement(
                code="one_off_without_evaluate",
                name="x",
                description="x",
                category=Category.SCORING,
                art_key="x",
            ),
            "needs an evaluate function",
        ),
    ],
)
def test_register_rejects_malformed_definitions(isolated_registry, bad, match):
    with pytest.raises(ValueError, match=match):
        registry.register(bad)


def test_get_unknown_code_raises_key_error(isolated_registry):
    with pytest.raises(KeyError, match="nope"):
        registry.get("nope")


def test_evaluate_all_awards_every_crossed_tier_at_first_event(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    ctx = (
        ctx_builder()
        .round(1, sun(0), 30)
        .round(1, sun(0), 31)
        .round(1, sun(1), 32)
        .round(2, sun(1), 33)
        .build()
    )
    got = [
        (w.event_date, w.code, w.shooter_id, w.round_id, dict(w.details))
        for w in registry.evaluate_all(ctx)
    ]
    assert got == [
        (sun(0), "toy_rounds:1", 1, None, {"value": 2.0, "threshold": 1.0}),
        (sun(0), "toy_rounds:2", 1, None, {"value": 2.0, "threshold": 2.0}),
        (sun(1), "toy_rounds:1", 2, None, {"value": 1.0, "threshold": 1.0}),
    ]


def forty_ctx(ctx_builder):
    return (
        ctx_builder()
        .round(1, sun(0), 45)
        .round(1, sun(0), 41)
        .round(1, sun(2), 42)
        .round(2, sun(1), 39)
        .build()
    )


def test_non_repeatable_one_off_keeps_only_first_award(isolated_registry, ctx_builder):
    registry.register(toy_one_off())
    got = [
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_all(forty_ctx(ctx_builder))
    ]
    assert got == [(1, sun(0), 1)]


def test_repeatable_one_off_keeps_one_award_per_day(isolated_registry, ctx_builder):
    registry.register(toy_one_off(repeatable=True))
    got = [
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_all(forty_ctx(ctx_builder))
    ]
    assert got == [(1, sun(0), 1), (1, sun(2), 3)]


def test_one_off_returning_a_foreign_code_is_rejected(isolated_registry, ctx_builder):
    registry.register(
        Achievement(
            code="toy_bad",
            name="x",
            description="x",
            category=Category.SCORING,
            art_key="x",
            evaluate=forty_plus("other"),
        )
    )
    with pytest.raises(ValueError, match="other"):
        registry.evaluate_all(ctx_builder().round(1, sun(0), 45).build())


def test_evaluate_all_orders_by_date_then_code_then_shooter(isolated_registry, ctx_builder):
    registry.register(toy_one_off("toy_b"))
    registry.register(toy_one_off("toy_a"))
    ctx = ctx_builder().round(2, sun(0), 45).round(1, sun(0), 44).round(3, sun(1), 50).build()
    assert [(w.event_date, w.code, w.shooter_id) for w in registry.evaluate_all(ctx)] == [
        (sun(0), "toy_a", 1),
        (sun(0), "toy_a", 2),
        (sun(0), "toy_b", 1),
        (sun(0), "toy_b", 2),
        (sun(1), "toy_a", 3),
        (sun(1), "toy_b", 3),
    ]


def test_progress_reports_next_tier_and_fraction(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    registry.register(toy_one_off())
    ctx = ctx_builder().round(1, sun(0), 30).round(1, sun(0), 31).round(1, sun(1), 32).build()
    [p] = registry.progress(ctx, 1, None)
    assert (p.code, p.value, p.earned_level, p.earned_metal, p.earned_label) == (
        "toy_rounds",
        3.0,
        2,
        Metal.SILVER,
        "2 rounds",
    )
    assert (p.next_level, p.next_threshold, p.next_label, p.next_metal) == (
        3,
        5.0,
        "5 rounds",
        Metal.GOLD,
    )
    assert p.fraction == pytest.approx(0.6)


def test_progress_of_a_maxed_family_has_no_next_tier(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    builder = ctx_builder()
    for i in range(6):
        builder.round(1, sun(i), 30)
    [p] = registry.progress(builder.build(), 1, None)
    assert (
        p.value,
        p.earned_level,
        p.earned_metal,
        p.next_level,
        p.next_threshold,
        p.fraction,
    ) == (
        6.0,
        3,
        Metal.GOLD,
        None,
        None,
        1.0,
    )


def test_progress_for_a_shooter_without_rounds_starts_at_zero(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    [p] = registry.progress(ctx_builder().round(1, sun(0), 30).build(), 99, None)
    assert (p.value, p.earned_level, p.earned_metal, p.earned_label, p.next_level, p.fraction) == (
        0.0,
        0,
        None,
        None,
        1,
        0.0,
    )


def test_progress_as_of_matches_sliced_context(isolated_registry, ctx_builder):
    registry.register(toy_tiered())
    ctx = (
        ctx_builder()
        .round(1, sun(0), 30)
        .round(1, sun(0), 31)
        .round(1, sun(1), 32)
        .round(1, sun(2), 33)
        .round(1, sun(2), 34)
        .round(1, sun(2), 35)
        .build()
    )
    assert registry.progress(ctx, 1, sun(0)) == registry.progress(ctx.until(sun(0)), 1, None)
    [p] = registry.progress(ctx, 1, sun(0))
    assert p.value == 2.0


def test_trophies_list_tiers_and_one_offs_in_category_order(isolated_registry):
    registry.register(toy_one_off())
    registry.register(toy_tiered())
    assert [t.code for t in registry.trophies()] == [
        "toy_rounds:1",
        "toy_rounds:2",
        "toy_rounds:3",
        "toy_forty",
    ]
    found = registry.trophy("toy_rounds:2")
    assert found is not None
    assert found.tier is not None
    assert found.tier.label == "2 rounds"
    assert registry.trophy("toy_rounds:9") is None


@pytest.mark.parametrize(
    ("holders", "n_shooters", "pct"), [(65, 332, 19.6), (1, 3, 33.3), (0, 0, 0.0)]
)
def test_rarity_pct_rounds_to_one_decimal(holders, n_shooters, pct):
    assert registry.rarity_pct(holders, n_shooters) == pct


def test_load_all_imports_new_sibling_modules(isolated_registry, tmp_path, monkeypatch):
    (tmp_path / "toy_sibling.py").write_text(
        "from sunday_clays.analytics.achievements.registry import Achievement, Category, register\n"
        "register(Achievement(code='toy_sibling', name='Toy', description='Toy.', "
        "category=Category.CALENDAR, art_key='toy_sibling', evaluate=lambda ctx: iter(())))\n"
    )
    monkeypatch.setattr(achievements_pkg, "__path__", [str(tmp_path)])
    try:
        registry.load_all()
        assert "toy_sibling" in isolated_registry
    finally:
        sys.modules.pop("sunday_clays.analytics.achievements.toy_sibling", None)
```

- [ ] **Step 6: Run the registry tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_registry.py -v`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.analytics.achievements.registry'`.

- [ ] **Step 7: Implement the registry**

Create `backend/src/sunday_clays/analytics/achievements/registry.py`:

```python
"""Achievement registry (C12): trophy definitions, tier metals, evaluation and tier progress.

Definitions live in sibling modules (participation, scores, conditions, competition, stations)
that call `register` at import time; `load_all` imports them. Tiered `value` functions must be
per-shooter separable (a shooter's series depends only on their own rows and the shared events
frame), because `progress` evaluates them on `ctx.for_shooter(shooter_id)`.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd
from pydantic import BaseModel

from sunday_clays.analytics.achievements.context import AchContext

_PACKAGE = "sunday_clays.analytics.achievements"
_SKIP_MODULES = frozenset({"registry", "context"})


class Metal(StrEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


class Category(StrEnum):
    MILESTONE = "milestone"
    SCORING = "scoring"
    CALENDAR = "calendar"
    CONDITIONS = "conditions"
    STATIONS = "stations"
    COMPETITION = "competition"


_METALS: tuple[Metal, ...] = tuple(Metal)
_CATEGORY_ORDER: dict[Category, int] = {category: i for i, category in enumerate(Category)}


@dataclass(frozen=True)
class Tier:
    level: int
    threshold: float
    metal: Metal
    label: str


@dataclass(frozen=True)
class Award:
    shooter_id: int
    code: str
    event_date: date
    round_id: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class Achievement:
    code: str
    name: str
    description: str
    category: Category
    art_key: str
    tiers: tuple[Tier, ...] = ()
    value: Callable[[AchContext], pd.DataFrame] | None = None
    evaluate: Callable[[AchContext], Iterable[Award]] | None = None
    repeatable: bool = False


@dataclass(frozen=True)
class Trophy:
    """One collectible trophy.

    A tier of a family (code `family:level`) or a one-off (the family code).
    """

    code: str
    achievement: Achievement
    tier: Tier | None


class ProgressOut(BaseModel):
    code: str
    name: str
    description: str
    category: Category
    art_key: str
    value: float
    earned_level: int
    earned_metal: Metal | None
    earned_label: str | None
    next_level: int | None
    next_threshold: float | None
    next_label: str | None
    next_metal: Metal | None
    fraction: float


_REGISTRY: dict[str, Achievement] = {}


def metal_for(level: int, n_tiers: int) -> Metal:
    """Level 1 bronze … 5 diamond; families with 6+ tiers put the extra lowest tiers at bronze."""
    extra = max(0, n_tiers - len(_METALS))
    return _METALS[max(0, level - 1 - extra)]


def make_tiers(
    thresholds: Sequence[int], unit: str, *, singular: str | None = None
) -> tuple[Tier, ...]:
    n_tiers = len(thresholds)
    return tuple(
        Tier(
            level=level,
            threshold=float(threshold),
            metal=metal_for(level, n_tiers),
            label=f"{threshold:,} {singular if threshold == 1 and singular else unit}",
        )
        for level, threshold in enumerate(thresholds, start=1)
    )


def register(a: Achievement) -> Achievement:
    if not a.code or ":" in a.code:
        raise ValueError(f"invalid achievement code {a.code!r}")
    if a.code in _REGISTRY:
        raise ValueError(f"duplicate achievement code {a.code!r}")
    if a.tiers and a.value is None:
        raise ValueError(f"tiered achievement {a.code!r} needs a value function")
    if not a.tiers and a.evaluate is None:
        raise ValueError(f"one-off achievement {a.code!r} needs an evaluate function")
    _REGISTRY[a.code] = a
    return a


def load_all() -> None:
    package = importlib.import_module(_PACKAGE)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name not in _SKIP_MODULES:
            importlib.import_module(f"{_PACKAGE}.{info.name}")


def all_achievements() -> list[Achievement]:
    """Every registered achievement, in category order, then registration order."""
    load_all()
    return sorted(_REGISTRY.values(), key=lambda a: _CATEGORY_ORDER[a.category])


def get(code: str) -> Achievement:
    load_all()
    try:
        return _REGISTRY[code]
    except KeyError:
        raise KeyError(f"unknown achievement {code!r}") from None


def trophies() -> list[Trophy]:
    out: list[Trophy] = []
    for a in all_achievements():
        if a.tiers:
            out.extend(Trophy(f"{a.code}:{tier.level}", a, tier) for tier in a.tiers)
        else:
            out.append(Trophy(a.code, a, None))
    return out


def trophy(code: str) -> Trophy | None:
    return next((t for t in trophies() if t.code == code), None)


def rarity_pct(holders: int, n_shooters: int) -> float:
    """Percent of shooters with >= 1 round who hold a trophy, 1 dp."""
    return round(100.0 * holders / n_shooters, 1) if n_shooters > 0 else 0.0


def _tier_awards(a: Achievement, ctx: AchContext) -> list[Award]:
    if a.value is None:
        raise ValueError(f"tiered achievement {a.code!r} has no value function")
    frame = a.value(ctx)
    if frame.empty:
        return []
    ordered = frame.assign(event_ts=pd.to_datetime(frame["event_date"])).sort_values(
        ["shooter_id", "event_ts"], kind="stable"
    )
    awards: list[Award] = []
    for tier in a.tiers:
        crossed = (
            ordered[ordered["value"] >= tier.threshold].groupby("shooter_id", sort=True).head(1)
        )
        for sid, ts, value in zip(
            crossed["shooter_id"], crossed["event_ts"], crossed["value"], strict=True
        ):
            awards.append(
                Award(
                    int(sid),
                    f"{a.code}:{tier.level}",
                    ts.date(),
                    None,
                    {"value": float(value), "threshold": tier.threshold},
                )
            )
    return awards


def _one_off_awards(a: Achievement, ctx: AchContext) -> list[Award]:
    if a.evaluate is None:
        raise ValueError(f"one-off achievement {a.code!r} has no evaluate function")
    raw = list(a.evaluate(ctx))
    for award in raw:
        if award.code != a.code:
            raise ValueError(f"{a.code!r} evaluate returned an award for {award.code!r}")
    seen_days: set[tuple[int, date]] = set()
    seen_shooters: set[int] = set()
    kept: list[Award] = []
    for award in sorted(raw, key=lambda w: (w.shooter_id, w.event_date)):
        if (award.shooter_id, award.event_date) in seen_days:
            continue
        if not a.repeatable and award.shooter_id in seen_shooters:
            continue
        seen_days.add((award.shooter_id, award.event_date))
        seen_shooters.add(award.shooter_id)
        kept.append(award)
    return kept


def evaluate_one(a: Achievement, ctx: AchContext) -> list[Award]:
    """Tiered: `code:level` at the first event whose value >= threshold (every crossed tier on
    that event). One-off: at most one award per shooter-day; non-repeatable keeps the first."""
    return _tier_awards(a, ctx) if a.tiers else _one_off_awards(a, ctx)


def evaluate_all(ctx: AchContext) -> list[Award]:
    awards = [award for a in all_achievements() for award in evaluate_one(a, ctx)]
    return sorted(awards, key=lambda w: (w.event_date, w.code, w.shooter_id))


def progress(ctx: AchContext, shooter_id: int, as_of: date | None) -> list[ProgressOut]:
    """Per tiered family: current value (as of `as_of`), highest tier earned, next tier."""
    own = ctx.for_shooter(shooter_id).until(as_of)
    out: list[ProgressOut] = []
    for a in all_achievements():
        if not a.tiers or a.value is None:
            continue
        frame = a.value(own)
        current = float(frame["value"].max()) if not frame.empty else 0.0
        earned = [tier for tier in a.tiers if current >= tier.threshold]
        top = earned[-1] if earned else None
        nxt = next((tier for tier in a.tiers if current < tier.threshold), None)
        out.append(
            ProgressOut(
                code=a.code,
                name=a.name,
                description=a.description,
                category=a.category,
                art_key=a.art_key,
                value=current,
                earned_level=top.level if top else 0,
                earned_metal=top.metal if top else None,
                earned_label=top.label if top else None,
                next_level=nxt.level if nxt else None,
                next_threshold=nxt.threshold if nxt else None,
                next_label=nxt.label if nxt else None,
                next_metal=nxt.metal if nxt else None,
                fraction=1.0 if nxt is None else min(1.0, max(0.0, current / nxt.threshold)),
            )
        )
    return out
```

- [ ] **Step 8: Run the registry tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements -v`
Expected: PASS (context and registry tests all green).

- [ ] **Step 9: Write the failing s50 integration tests**

Create `backend/tests/integration/achievements/conftest.py`:

```python
"""Fixtures for achievement integration tests in the committed-fixtures (fx) world."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd
import pytest

from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Achievement]:
    registry.load_all()
    fresh: dict[str, Achievement] = {}
    monkeypatch.setattr(registry, "_REGISTRY", fresh)
    return fresh


def _events_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"],
            "event_date": days["event_ts"],
            "value": days["n_events"].astype(float),
        }
    )


def _perfect_round(ctx: AchContext) -> Iterator[Award]:
    perfect = ctx.rounds[ctx.rounds["score"] == 50]
    for sid, ts, rid in zip(
        perfect["shooter_id"], perfect["event_ts"], perfect["round_id"], strict=True
    ):
        yield Award(int(sid), "toy_perfect", ts.date(), int(rid), {})


@pytest.fixture
def toy_trophies(isolated_registry: dict[str, Achievement]) -> dict[str, Achievement]:
    """Two toys: tiered toy_events (1 / 10 events) and one-off toy_perfect (first 50)."""
    registry.register(
        Achievement(
            code="toy_events",
            name="Toy Events",
            description="Events attended.",
            category=Category.MILESTONE,
            art_key="toy_events",
            tiers=registry.make_tiers((1, 10), "events", singular="event"),
            value=_events_value,
        )
    )
    registry.register(
        Achievement(
            code="toy_perfect",
            name="Toy Perfect",
            description="Shot a 50.",
            category=Category.SCORING,
            art_key="toy_perfect",
            evaluate=_perfect_round,
        )
    )
    return isolated_registry
```

Create `backend/tests/integration/achievements/test_s50_achievements.py`:

```python
"""Recompute step s50 writes achievements_awarded (Plan 10 T1)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from sunday_clays.analytics.achievements.context import build_context
from sunday_clays.analytics.achievements.registry import evaluate_all
from sunday_clays.analytics.pipeline import discover_steps
from sunday_clays.analytics.steps.s50_achievements import STEP


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def test_step_is_discovered_at_order_50():
    assert ("achievements", 50) in [(s.name, s.order) for s in discover_steps()]


def test_build_context_reads_fixture_frames(fx_session):
    ctx = build_context(fx_session)
    assert len(ctx.rounds) == 7480
    assert len(ctx.events) == 360
    assert len(ctx.station_hits) == 259
    assert set(ctx.station_hits["target_count"]) == {7, 8}
    assert ctx.station_hits["shooter_id"].notna().all()


def test_s50_writes_every_evaluated_award(fx_session, toy_trophies):
    STEP.run(fx_session)
    stored = sorted(
        tuple(row)
        for row in fx_session.execute(
            text("SELECT shooter_id, code, event_date, round_id FROM achievements_awarded")
        ).all()
    )
    expected = sorted(
        (w.shooter_id, w.code, w.event_date, w.round_id)
        for w in evaluate_all(build_context(fx_session))
    )
    assert stored == expected
    ten_plus = scalar(
        fx_session,
        "SELECT count(*) FROM (SELECT shooter_id FROM rounds GROUP BY shooter_id "
        "HAVING count(DISTINCT event_date) >= 10) h",
    )
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'toy_events:2'")
        == ten_plus
        == 107
    )
    perfect = scalar(fx_session, "SELECT count(DISTINCT shooter_id) FROM rounds WHERE score = 50")
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'toy_perfect'")
        == perfect
        == 4
    )


def test_s50_replaces_previous_awards(fx_session, toy_trophies):
    shooter_id = scalar(fx_session, "SELECT min(shooter_id) FROM rounds")
    fx_session.execute(
        text(
            "INSERT INTO achievements_awarded (shooter_id, code, event_date, round_id, details) "
            "VALUES (:s, 'stale_code', DATE '2026-09-13', NULL, CAST('{}' AS jsonb))"
        ),
        {"s": shooter_id},
    )
    STEP.run(fx_session)
    first_run = scalar(fx_session, "SELECT count(*) FROM achievements_awarded")
    STEP.run(fx_session)
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'stale_code'")
        == 0
    )
    assert scalar(fx_session, "SELECT count(*) FROM achievements_awarded") == first_run
```

- [ ] **Step 10: Run the s50 tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/achievements/test_s50_achievements.py -v`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.analytics.steps.s50_achievements'`.

- [ ] **Step 11: Implement the s50 step**

Create `backend/src/sunday_clays/analytics/steps/s50_achievements.py`:

```python
"""Recompute step 50 (C6): evaluate every registered achievement and replace achievements_awarded.

Replacing (not merging) is what keeps rollbacks honest: a trophy whose data vanished disappears.
"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import build_context
from sunday_clays.analytics.achievements.registry import evaluate_all
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.pipeline import RecomputeStep

_INSERT = text(
    "INSERT INTO achievements_awarded (shooter_id, code, event_date, round_id, details) "
    "VALUES (:shooter_id, :code, :event_date, :round_id, CAST(:details AS jsonb))"
)


def run(session: Session) -> None:
    clear_cache()  # a memo entry may be keyed at a rolled-back run's uncommitted data_version
    awards = evaluate_all(build_context(session))
    session.execute(text("DELETE FROM achievements_awarded"))
    if awards:
        session.execute(
            _INSERT,
            [
                {
                    "shooter_id": award.shooter_id,
                    "code": award.code,
                    "event_date": award.event_date,
                    "round_id": award.round_id,
                    "details": json.dumps(dict(award.details), sort_keys=True),
                }
                for award in awards
            ],
        )


STEP = RecomputeStep(name="achievements", order=50, run=run)
```

- [ ] **Step 12: Run the s50 tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/achievements/test_s50_achievements.py -v`
Expected: PASS (4 passed).

- [ ] **Step 13: Write the failing route tests**

Create `backend/tests/integration/achievements/test_achievements_routes.py`:

```python
"""Achievement read endpoints over the fx world with toy trophies (Plan 10 T1)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from sunday_clays.analytics.steps.s50_achievements import STEP


@pytest.fixture
def awarded(fx_session, toy_trophies) -> None:
    STEP.run(fx_session)


def rows(session: Any, sql: str, **params: Any) -> list[Any]:
    return list(session.execute(text(sql), params).all())


def test_list_achievements_counts_holders_and_rarity(fx_viewer_client, awarded):
    body = fx_viewer_client.get("/api/achievements").json()
    assert body["n_shooters"] == 332
    by_code = {t["code"]: t for t in body["trophies"]}
    assert list(by_code) == ["toy_events:1", "toy_events:2", "toy_perfect"]
    tier = by_code["toy_events:2"]
    assert (
        tier["family"],
        tier["metal"],
        tier["level"],
        tier["label"],
        tier["holders"],
        tier["rarity_pct"],
    ) == (
        "toy_events",
        "silver",
        2,
        "10 events",
        107,
        32.2,
    )
    assert by_code["toy_perfect"]["metal"] is None
    assert by_code["toy_perfect"]["holders"] == 4
    assert len(body["recent"]) == 20
    assert body["recent"][0]["event_date"] == max(t["last_awarded"] for t in body["trophies"])


def test_achievement_detail_lists_holders_with_first_dates(fx_viewer_client, fx_session, awarded):
    body = fx_viewer_client.get("/api/achievements/toy_perfect").json()
    expected = {
        int(sid): first.isoformat()
        for sid, first in rows(
            fx_session,
            "SELECT shooter_id, min(event_date) FROM rounds WHERE score = 50 GROUP BY shooter_id",
        )
    }
    assert {h["shooter_id"]: h["first_date"] for h in body["holders"]} == expected
    assert all(h["count"] == 1 and h["dates"] == [h["first_date"]] for h in body["holders"])
    assert body["trophy"]["code"] == "toy_perfect"


def test_tier_code_with_colon_resolves(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/achievements/toy_events:2")
    assert response.status_code == 200
    assert len(response.json()["holders"]) == 107


def test_unknown_achievement_is_404(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/achievements/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "achievement_not_found"


def test_shooter_achievements_report_earned_progress_and_locked(
    fx_viewer_client, fx_session, awarded
):
    [(shooter_id, first)] = rows(
        fx_session,
        "SELECT shooter_id, min(event_date) FROM rounds "
        "WHERE shooter_id NOT IN (SELECT shooter_id FROM rounds WHERE score = 50) "
        "GROUP BY shooter_id HAVING count(DISTINCT event_date) = 3 ORDER BY shooter_id LIMIT 1",
    )
    body = fx_viewer_client.get(f"/api/shooters/{shooter_id}/achievements").json()
    assert [(e["code"], e["first_date"], e["count"]) for e in body["earned"]] == [
        ("toy_events:1", first.isoformat(), 1)
    ]
    [p] = body["progress"]
    assert (
        p["value"],
        p["earned_level"],
        p["next_level"],
        p["next_threshold"],
        p["next_label"],
    ) == (
        3.0,
        1,
        2,
        10.0,
        "10 events",
    )
    assert p["fraction"] == pytest.approx(0.3)
    assert [locked["code"] for locked in body["locked"]] == ["toy_perfect"]


def test_most_frequent_shooter_has_maxed_progress(fx_viewer_client, fx_session, awarded):
    [(shooter_id, n_events)] = rows(
        fx_session,
        "SELECT shooter_id, count(DISTINCT event_date) AS n FROM rounds GROUP BY shooter_id "
        "ORDER BY n DESC, shooter_id LIMIT 1",
    )
    [p] = fx_viewer_client.get(f"/api/shooters/{shooter_id}/achievements").json()["progress"]
    assert (p["value"], p["earned_level"], p["next_level"], p["fraction"]) == (
        float(n_events),
        2,
        None,
        1.0,
    )


def test_unknown_shooter_is_404(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/shooters/999999/achievements")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


def test_event_achievements_list_that_days_awards(fx_viewer_client, fx_session, awarded):
    [(day,)] = rows(fx_session, "SELECT max(event_date) FROM achievements_awarded")
    [(expected,)] = rows(
        fx_session, "SELECT count(*) FROM achievements_awarded WHERE event_date = :d", d=day
    )
    body = fx_viewer_client.get(f"/api/events/{day.isoformat()}/achievements").json()
    assert body["event_date"] == day.isoformat()
    assert len(body["awards"]) == expected > 0
    assert all(a["event_date"] == day.isoformat() for a in body["awards"])


def test_event_achievements_unknown_date_is_404(fx_viewer_client, awarded):
    response = fx_viewer_client.get("/api/events/2026-09-14/achievements")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "event_not_found"
```

- [ ] **Step 14: Run the route tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/achievements/test_achievements_routes.py -v`
Expected: FAIL. The first test gets 404 instead of 200 because no router serves `/api/achievements`, so `KeyError: 'n_shooters'`.

- [ ] **Step 15: Implement the achievement routes**

Create `backend/src/sunday_clays/api/routes/achievements.py`:

```python
"""Achievement read endpoints (C8, Plan 10 T1): Trophy Room, trophy holders, a shooter's Trophy
Case and the trophies earned at one event. Awards come from achievements_awarded (written by
recompute step s50); tier progress is computed per request from the data_version-cached context.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from sunday_clays.analytics.achievements.context import cached_context
from sunday_clays.analytics.achievements.registry import (
    Category,
    Metal,
    ProgressOut,
    Trophy,
    progress,
    rarity_pct,
    trophies,
    trophy,
)
from sunday_clays.db import get_session
from sunday_clays.domain.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["achievements"])

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
RECENT_LIMIT = 20

_AWARDS_SQL = """
    SELECT a.shooter_id, p.display_name, p.status AS shooter_status, a.code,
           a.event_date, a.round_id, a.details
    FROM achievements_awarded a
    JOIN shooter_profiles p ON p.shooter_id = a.shooter_id
"""


class TrophyOut(BaseModel):
    code: str
    family: str
    name: str
    description: str
    category: Category
    art_key: str
    metal: Metal | None
    level: int | None
    threshold: float | None
    label: str | None
    repeatable: bool
    holders: int
    rarity_pct: float
    last_awarded: date | None


class TrophyAwardOut(BaseModel):
    shooter_id: int
    display_name: str
    code: str
    family: str
    name: str
    label: str | None
    metal: Metal | None
    art_key: str
    event_date: date
    round_id: int | None
    details: dict[str, Any]


class AchievementsOut(BaseModel):
    n_shooters: int
    trophies: list[TrophyOut]
    recent: list[TrophyAwardOut]


class TrophyHolderOut(BaseModel):
    shooter_id: int
    display_name: str
    shooter_status: str
    first_date: date
    count: int
    dates: list[date]


class AchievementDetailOut(BaseModel):
    trophy: TrophyOut
    holders: list[TrophyHolderOut]


class EarnedTrophyOut(BaseModel):
    code: str
    family: str
    name: str
    description: str
    category: Category
    art_key: str
    metal: Metal | None
    level: int | None
    label: str | None
    first_date: date
    count: int
    dates: list[date]


class LockedTrophyOut(BaseModel):
    code: str
    name: str
    description: str
    category: Category
    art_key: str
    rarity_pct: float


class ShooterAchievementsOut(BaseModel):
    shooter_id: int
    display_name: str
    earned: list[EarnedTrophyOut]
    progress: list[ProgressOut]
    locked: list[LockedTrophyOut]


class EventAchievementsOut(BaseModel):
    event_date: date
    awards: list[TrophyAwardOut]


def _n_shooters(session: Session) -> int:
    return int(session.execute(text("SELECT count(DISTINCT shooter_id) FROM rounds")).scalar_one())


def _holder_stats(session: Session) -> dict[str, tuple[int, date | None]]:
    result = session.execute(
        text(
            "SELECT code, count(DISTINCT shooter_id) AS holders, max(event_date) AS last_awarded "
            "FROM achievements_awarded GROUP BY code"
        )
    ).mappings()
    return {str(r["code"]): (int(r["holders"]), r["last_awarded"]) for r in result}


def _trophy_out(
    t: Trophy, stats: Mapping[str, tuple[int, date | None]], n_shooters: int
) -> TrophyOut:
    holders, last = stats.get(t.code, (0, None))
    a = t.achievement
    return TrophyOut(
        code=t.code,
        family=a.code,
        name=a.name,
        description=a.description,
        category=a.category,
        art_key=a.art_key,
        metal=t.tier.metal if t.tier else None,
        level=t.tier.level if t.tier else None,
        threshold=t.tier.threshold if t.tier else None,
        label=t.tier.label if t.tier else None,
        repeatable=a.repeatable,
        holders=holders,
        rarity_pct=rarity_pct(holders, n_shooters),
        last_awarded=last,
    )


def _award_out(row: RowMapping, t: Trophy) -> TrophyAwardOut:
    return TrophyAwardOut(
        shooter_id=int(row["shooter_id"]),
        display_name=str(row["display_name"]),
        code=t.code,
        family=t.achievement.code,
        name=t.achievement.name,
        label=t.tier.label if t.tier else None,
        metal=t.tier.metal if t.tier else None,
        art_key=t.achievement.art_key,
        event_date=row["event_date"],
        round_id=row["round_id"],
        details=dict(row["details"] or {}),
    )


@router.get("/achievements", response_model=AchievementsOut)
def list_achievements(session: SessionDep) -> AchievementsOut:
    n_shooters = _n_shooters(session)
    stats = _holder_stats(session)
    catalog = {t.code: t for t in trophies()}
    recent = session.execute(
        text(
            _AWARDS_SQL + " WHERE a.code = ANY(:codes)"
            " ORDER BY a.event_date DESC, a.code, a.shooter_id LIMIT :n"
        ),
        {"codes": list(catalog), "n": RECENT_LIMIT},
    ).mappings()
    return AchievementsOut(
        n_shooters=n_shooters,
        trophies=[_trophy_out(t, stats, n_shooters) for t in catalog.values()],
        recent=[_award_out(r, catalog[str(r["code"])]) for r in recent],
    )


@router.get("/achievements/{code}", response_model=AchievementDetailOut)
def get_achievement(code: str, session: SessionDep) -> AchievementDetailOut:
    found = trophy(code)
    if found is None:
        raise NotFoundError("achievement_not_found", f"No trophy with code {code!r}")
    result = session.execute(
        text(
            _AWARDS_SQL
            + " WHERE a.code = :code ORDER BY a.event_date, p.display_name, a.shooter_id"
        ),
        {"code": code},
    ).mappings()
    holders: dict[int, TrophyHolderOut] = {}
    for r in result:
        shooter_id = int(r["shooter_id"])
        holder = holders.get(shooter_id)
        if holder is None:
            holders[shooter_id] = TrophyHolderOut(
                shooter_id=shooter_id,
                display_name=str(r["display_name"]),
                shooter_status=str(r["shooter_status"]),
                first_date=r["event_date"],
                count=1,
                dates=[r["event_date"]],
            )
        else:
            holder.count += 1
            holder.dates.append(r["event_date"])
    return AchievementDetailOut(
        trophy=_trophy_out(found, _holder_stats(session), _n_shooters(session)),
        holders=list(holders.values()),
    )


@router.get("/shooters/{id}/achievements", response_model=ShooterAchievementsOut)
def get_shooter_achievements(
    shooter_id: Annotated[int, Path(alias="id")], session: SessionDep
) -> ShooterAchievementsOut:
    display_name = session.execute(
        text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :id"), {"id": shooter_id}
    ).scalar_one_or_none()
    if display_name is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    catalog = {t.code: t for t in trophies()}
    dates_by_code: dict[str, list[date]] = {}
    for r in session.execute(
        text(
            "SELECT code, event_date FROM achievements_awarded"
            " WHERE shooter_id = :id ORDER BY event_date, code"
        ),
        {"id": shooter_id},
    ).mappings():
        if r["code"] in catalog:
            dates_by_code.setdefault(str(r["code"]), []).append(r["event_date"])
    earned = []
    for code, days in dates_by_code.items():
        t = catalog[code]
        earned.append(
            EarnedTrophyOut(
                code=code,
                family=t.achievement.code,
                name=t.achievement.name,
                description=t.achievement.description,
                category=t.achievement.category,
                art_key=t.achievement.art_key,
                metal=t.tier.metal if t.tier else None,
                level=t.tier.level if t.tier else None,
                label=t.tier.label if t.tier else None,
                first_date=days[0],
                count=len(days),
                dates=days,
            )
        )
    stats = _holder_stats(session)
    n_shooters = _n_shooters(session)
    locked = [
        LockedTrophyOut(
            code=t.code,
            name=t.achievement.name,
            description=t.achievement.description,
            category=t.achievement.category,
            art_key=t.achievement.art_key,
            rarity_pct=rarity_pct(stats.get(t.code, (0, None))[0], n_shooters),
        )
        for t in catalog.values()
        if t.tier is None and t.code not in dates_by_code
    ]
    return ShooterAchievementsOut(
        shooter_id=shooter_id,
        display_name=str(display_name),
        earned=earned,
        progress=progress(cached_context(session), shooter_id, None),
        locked=locked,
    )


@router.get("/events/{date}/achievements", response_model=EventAchievementsOut)
def get_event_achievements(
    event_date: Annotated[date, Path(alias="date")], session: SessionDep
) -> EventAchievementsOut:
    exists = session.execute(
        text("SELECT 1 FROM events WHERE event_date = :d"), {"d": event_date}
    ).first()
    if exists is None:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    catalog = {t.code: t for t in trophies()}
    result = session.execute(
        text(_AWARDS_SQL + " WHERE a.event_date = :d ORDER BY p.display_name, a.code"),
        {"d": event_date},
    ).mappings()
    return EventAchievementsOut(
        event_date=event_date,
        awards=[_award_out(r, catalog[str(r["code"])]) for r in result if r["code"] in catalog],
    )
```

- [ ] **Step 16: Run the route tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/achievements -v`
Expected: PASS (s50 and route tests all green).

- [ ] **Step 17: Run the full backend suite with lint, types and coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: PASS. Ruff and mypy are clean, every test passes, and coverage is ≥90% lines and branches (`fail_under=90`). If `ruff format --check` reports files, run `uv run ruff format .` and re-run. The `export_openapi` test must stay green, which proves the new route module imports without env or DB.

- [ ] **Step 18: Commit**

```bash
git add backend/src/sunday_clays/analytics/achievements backend/src/sunday_clays/analytics/steps/s50_achievements.py \
  backend/src/sunday_clays/api/routes/achievements.py backend/tests/unit/analytics/achievements \
  backend/tests/integration/achievements
git commit -m "feat(achievements): add achievement registry, context, s50 step and trophy routes" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Milestone families and participation trophies (master Plan 10 T2)

**Context:** This task adds the non-ranking milestone families and the participation and calendar one-offs.
- Contract: C12 tiered families and one-off codes, and C7 held events and `streaks()`. `iron_streak` must call `streaks()` through `ctx.streaks_at(day)` and never reimplement it.
- "Prior", "earlier" and "previous" always mean earlier **dates**.
- Every definition has its own no-leak test.
- `left_censored` shooters are NOT excluded from `anniversary_*` or the `events` tiers (C4); no Plan 10 trophy excludes them.
- Coverage stays ≥90% lines and branches, and ruff and mypy stay clean.

**Branch:** `task/10-2-milestone-trophies`

**Depends on:** Plan 10 T1 (and, through T1, Plan 06 T1 `frames.season_label` and Plan 06 T6 `streaks`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/achievements/participation.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_participation.py`
- Test: `backend/tests/integration/achievements/test_ach_participation_golden.py`

**Interfaces:**
- Consumes (from Task 1):
  - `AchContext`: `.shooter_days`, `.held_dates()`, `.streaks_at(day)`, `.rounds`.
  - `empty_value_frame()`
  - `Achievement`, `Award`, `Category`, `make_tiers`, `register`, `registry.get`, `registry.evaluate_one`
  - Unit fixtures `ctx_builder` and `no_leak`.
  - From Plan 06 T1: `sunday_clays.analytics.frames.season_label(event_date: date) -> str` (winter Dec–Feb, spring, summer, fall).
- Produces the registered achievements below. Names, descriptions and categories are exactly as in the code in Step 5.

| Code | Kind | Category | Rule |
|---|---|---|---|
| `clays_broken` | tiers 100/500/1000/2500/5000/10000 "clays broken" | milestone | Σ score |
| `clays_thrown` | tiers 500/1000/2500/5000/10000 "clays thrown" | milestone | rounds × 50 |
| `events` | tiers 1/10/25/50/100/150/200/250 "events" | milestone | dates with ≥ 1 round |
| `years_active` | tiers 2/3/5/7 "years" | milestone | distinct calendar years |
| `big_year` | tiers 20/30/40 "events in one year" | milestone | max events in one calendar year so far |
| `iron_streak` | tiers 4/8/12/26 "straight events" | milestone | `streaks().longest_streak` |
| `personal_bests` | tiers 1/5/10 "personal bests" | scoring | days whose best round beats every earlier-dated round, ≥ 5 earlier rounds |
| `doubleheader` | one-off | milestone | ≥ 2 rounds on one date |
| `new_year` | one-off | calendar | attended the first held event of a calendar year |
| `anniversary_1` / `anniversary_5` | one-off | calendar | attended 365·k ± 7 days after first event |
| `welcome_back` | repeatable | calendar | ≥ 180 days since previous round |
| `joined_club` | one-off | milestone | `member` round after an earlier-dated `guest` round |
| `both_disciplines` | one-off | milestone | shot `sporting` and `super_sporting` days |
| `four_seasons` | one-off | calendar | all 4 seasons in one season-year (Dec → next year) |
| `perfect_month` | repeatable | calendar | month with ≥ 3 held events, all attended; dated at the closing event = first held event ≥ the month's last calendar Sunday; only the month's held events up to the closing event count (Decision 24) |

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/unit/analytics/achievements/test_ach_participation.py`:

```python
"""Participation trophies (Plan 10 T2): milestone families and calendar one-offs."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry
from sunday_clays.analytics.achievements.participation import last_sunday


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def value_series(code, ctx, shooter_id):
    frame = registry.get(code).value(ctx)
    return list(frame[frame["shooter_id"] == shooter_id]["value"])


# ---- scenarios (also reused by the no-leak tests) ----------------------------------------


def clays_broken_ctx(b):
    return (
        b()
        .round(1, sun(0), 40)
        .round(1, sun(0), 45)
        .round(1, sun(1), 20)
        .round(2, sun(1), 50)
        .build()
    )


def thrown_ctx(b):
    builder = b()
    for i in range(5):
        builder.round(1, sun(i), 30).round(1, sun(i), 31)
    builder.round(2, sun(0), 30)
    return builder.build()


def events_ctx(b):
    builder = b().round(1, sun(0), 30)  # a second round on the first date is still one event
    for i in range(10):
        builder.round(1, sun(i), 31)
    return builder.build()


def years_ctx(b):
    return (
        b()
        .round(1, date(2024, 12, 29), 30)
        .round(1, date(2025, 1, 5), 30)
        .round(1, date(2025, 6, 1), 30)
        .round(1, date(2026, 1, 4), 30)
        .build()
    )


def big_year_ctx(b):
    builder = b()
    for i in range(20):
        builder.round(1, date(2025, 1, 5) + timedelta(weeks=i), 30)
    for i in range(19):
        builder.round(2, date(2024, 1, 7) + timedelta(weeks=i), 30)
        builder.round(2, date(2025, 1, 5) + timedelta(weeks=i), 30)
    return builder.build()


NON_HELD = sun(2) + timedelta(days=3)


def streak_ctx(b):
    builder = b().event(NON_HELD, results_complete=False).round(1, NON_HELD, 30)
    for i in range(4):
        builder.round(1, sun(i), 30)  # also attends the non-held date
        builder.round(3, sun(i), 30)  # skips the non-held date: still 4 straight held events
    for i in (0, 1, 3, 4, 5):
        builder.round(2, sun(i), 30)  # misses sun(2): longest run is 3
    return builder.build()


def pb_ctx(b):
    builder = b()
    for i, score in enumerate([30, 31, 32, 33, 34]):
        builder.round(1, sun(i), score)
    builder.round(1, sun(5), 35).round(1, sun(6), 35).round(1, sun(7), 36).round(1, sun(7), 37)
    builder.round(2, sun(0), 40).round(2, sun(1), 45)
    return builder.build()


def doubleheader_ctx(b):
    return (
        b()
        .round(1, sun(0), 30)
        .round(1, sun(1), 30)
        .round(1, sun(1), 31)
        .round(1, sun(2), 30)
        .round(1, sun(2), 32)
        .round(2, sun(1), 30)
        .build()
    )


def new_year_ctx(b):
    return (
        b()
        .event(date(2025, 1, 5), results_complete=False)
        .round(2, date(2025, 1, 5), 30)
        .round(1, date(2025, 1, 12), 30)
        .round(1, date(2026, 1, 4), 30)
        .round(2, date(2026, 1, 4), 30)
        .build()
    )


FIRST = date(2024, 1, 7)


def anniversary_ctx(b):
    return (
        b()
        .round(1, FIRST, 30)
        .round(1, FIRST + timedelta(days=358), 30)
        .round(2, FIRST, 30)
        .round(2, FIRST + timedelta(days=357), 30)
        .round(2, FIRST + timedelta(days=373), 30)
        .round(3, FIRST, 30)
        .round(3, FIRST + timedelta(days=372), 30)
        .round(4, FIRST, 30)
        .round(4, FIRST + timedelta(days=365 * 5 + 7), 30)
        .build()
    )


W0 = sun(0)
W1 = W0 + timedelta(days=179)
W2 = W1 + timedelta(days=180)
W3 = W2 + timedelta(days=7)
W4 = W3 + timedelta(days=200)


def welcome_ctx(b):
    builder = b()
    for day in (W0, W1, W2, W3, W4):
        builder.round(1, day, 30)
    return builder.build()


def joined_ctx(b):
    return (
        b()
        .round(1, sun(0), 30, status="guest")  # round 1
        .round(1, sun(1), 30)  # round 2
        .round(2, sun(0), 30, status="guest")  # round 3
        .round(2, sun(0), 31)  # round 4: same day as the guest round, does not count
        .round(2, sun(1), 30)  # round 5
        .round(3, sun(0), 30)  # round 6
        .round(3, sun(1), 30, status="guest")  # round 7
        .round(3, sun(2), 30)  # round 8
        .round(4, sun(0), 30)
        .round(4, sun(1), 30)
        .build()
    )


def disciplines_ctx(b):
    return (
        b()
        .event(sun(0), round_type="sporting")
        .event(sun(1), round_type="unknown")
        .event(sun(2), round_type="super_sporting")
        .round(1, sun(0), 30)
        .round(1, sun(2), 30)
        .round(2, sun(0), 30)
        .round(2, sun(1), 30)
        .build()
    )


def seasons_ctx(b):
    return (
        b()
        .round(1, date(2024, 12, 29), 30)  # December counts toward 2025's winter
        .round(1, date(2025, 4, 6), 30)
        .round(1, date(2025, 7, 6), 30)
        .round(1, date(2025, 10, 5), 30)
        .round(2, date(2025, 4, 6), 30)
        .round(2, date(2025, 7, 6), 30)
        .round(2, date(2025, 10, 5), 30)
        .round(2, date(2025, 12, 7), 30)  # counts toward 2026's winter, not 2025's
        .build()
    )


MARCH = [date(2025, 3, d) for d in (2, 9, 16, 23)]
MARCH_30 = date(2025, 3, 30)
MARCH_31 = date(2025, 3, 31)  # a Monday: non-Sunday event dates do occur (C3 non_sunday_date)
APRIL_6 = date(2025, 4, 6)


def month_ctx(b, *, last_sunday_held, april_held):
    builder = b()
    for day in MARCH:
        builder.round(1, day, 30).round(2, day, 30)
    builder.round(3, MARCH[0], 30).round(3, MARCH[1], 30).round(3, MARCH[3], 30)  # misses 3/16
    if last_sunday_held:
        builder.round(1, MARCH_30, 30).round(2, MARCH_30, 30)
    else:
        builder.event(MARCH_30, results_complete=False).round(4, MARCH_30, 30)
    if april_held:
        builder.round(4, APRIL_6, 30)
    # February: only 2 held events
    builder.round(5, date(2025, 2, 2), 30).round(5, date(2025, 2, 9), 30)
    return builder.build()


def late_monday_ctx(b, *, last_sunday_held):
    builder = b()
    for day in MARCH:
        builder.round(1, day, 30).round(2, day, 30)
    if last_sunday_held:
        builder.round(1, MARCH_30, 30).round(2, MARCH_30, 30)
    return builder.round(2, MARCH_31, 30).build()  # only shooter 2 shoots the Monday


# ---- families ------------------------------------------------------------------------------


def test_clays_broken_crosses_at_first_event_over_threshold(ctx_builder):
    ctx = clays_broken_ctx(ctx_builder)
    assert awards("clays_broken", ctx) == [(1, "clays_broken:1", sun(1))]
    assert value_series("clays_broken", ctx, 1) == [85.0, 105.0]


def test_clays_thrown_counts_fifty_per_round(ctx_builder):
    assert awards("clays_thrown", thrown_ctx(ctx_builder)) == [(1, "clays_thrown:1", sun(4))]


def test_events_counts_dates_not_rounds(ctx_builder):
    assert awards("events", events_ctx(ctx_builder)) == [
        (1, "events:1", sun(0)),
        (1, "events:2", sun(9)),
    ]


def test_years_active_counts_distinct_calendar_years(ctx_builder):
    ctx = years_ctx(ctx_builder)
    assert awards("years_active", ctx) == [
        (1, "years_active:1", date(2025, 1, 5)),
        (1, "years_active:2", date(2026, 1, 4)),
    ]
    assert value_series("years_active", ctx, 1) == [1.0, 2.0, 2.0, 3.0]


def test_big_year_needs_twenty_events_in_one_calendar_year(ctx_builder):
    ctx = big_year_ctx(ctx_builder)
    assert awards("big_year", ctx) == [(1, "big_year:1", date(2025, 5, 18))]
    assert max(value_series("big_year", ctx, 2)) == 19.0


def test_iron_streak_counts_consecutive_held_events(ctx_builder):
    assert awards("iron_streak", streak_ctx(ctx_builder)) == [
        (1, "iron_streak:1", sun(3)),
        (3, "iron_streak:1", sun(3)),
    ]


def test_personal_best_counts_once_per_day(ctx_builder):
    ctx = pb_ctx(ctx_builder)
    assert value_series("personal_bests", ctx, 1) == [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 2.0]
    assert value_series("personal_bests", ctx, 2) == [0.0, 0.0]
    assert awards("personal_bests", ctx) == [(1, "personal_bests:1", sun(5))]


# ---- one-offs --------------------------------------------------------------------------------


def test_doubleheader_awarded_on_first_two_round_day(ctx_builder):
    assert awards("doubleheader", doubleheader_ctx(ctx_builder)) == [(1, "doubleheader", sun(1))]


def test_new_year_uses_first_held_event_of_the_year(ctx_builder):
    assert awards("new_year", new_year_ctx(ctx_builder)) == [
        (1, "new_year", date(2025, 1, 12)),
        (2, "new_year", date(2026, 1, 4)),
    ]


def test_anniversary_1_window_is_358_to_372_days(ctx_builder):
    assert awards("anniversary_1", anniversary_ctx(ctx_builder)) == [
        (1, "anniversary_1", FIRST + timedelta(days=358)),
        (3, "anniversary_1", FIRST + timedelta(days=372)),
    ]


def test_anniversary_5_window_is_a_week_either_side(ctx_builder):
    assert awards("anniversary_5", anniversary_ctx(ctx_builder)) == [
        (4, "anniversary_5", FIRST + timedelta(days=365 * 5 + 7))
    ]


def test_welcome_back_after_180_days_is_repeatable(ctx_builder):
    assert awards("welcome_back", welcome_ctx(ctx_builder)) == [
        (1, "welcome_back", W2),
        (1, "welcome_back", W4),
    ]


def test_joined_club_needs_a_guest_round_on_an_earlier_date(ctx_builder):
    got = {
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_one(registry.get("joined_club"), joined_ctx(ctx_builder))
    }
    assert got == {(1, sun(1), 2), (2, sun(1), 5), (3, sun(2), 8)}


def test_joined_club_without_any_guest_rounds_awards_nothing(ctx_builder):
    assert awards("joined_club", ctx_builder().round(1, sun(0), 30).build()) == []


def test_both_disciplines_dated_when_second_type_is_shot(ctx_builder):
    assert awards("both_disciplines", disciplines_ctx(ctx_builder)) == [
        (1, "both_disciplines", sun(2))
    ]


def test_both_disciplines_needs_known_round_types(ctx_builder):
    assert awards("both_disciplines", ctx_builder().round(1, sun(0), 30).build()) == []


def test_four_seasons_counts_december_toward_next_year(ctx_builder):
    assert awards("four_seasons", seasons_ctx(ctx_builder)) == [
        (1, "four_seasons", date(2025, 10, 5))
    ]


@pytest.mark.parametrize(
    ("year", "month", "expected"),
    [(2025, 3, date(2025, 3, 30)), (2025, 2, date(2025, 2, 23)), (2025, 8, date(2025, 8, 31))],
)
def test_last_sunday_of_month(year, month, expected):
    assert last_sunday(year, month) == expected


def test_perfect_month_closes_on_last_sunday_when_held(ctx_builder):
    ctx = month_ctx(ctx_builder, last_sunday_held=True, april_held=False)
    got = [
        (w.shooter_id, w.event_date, dict(w.details))
        for w in registry.evaluate_one(registry.get("perfect_month"), ctx)
    ]
    assert got == [(1, MARCH_30, {"month": "2025-03"}), (2, MARCH_30, {"month": "2025-03"})]


def test_perfect_month_closes_on_next_held_event_when_last_sunday_not_held(ctx_builder):
    ctx = month_ctx(ctx_builder, last_sunday_held=False, april_held=True)
    assert awards("perfect_month", ctx) == [
        (1, "perfect_month", APRIL_6),
        (2, "perfect_month", APRIL_6),
    ]


def test_perfect_month_not_awarded_while_month_is_open(ctx_builder):
    ctx = month_ctx(ctx_builder, last_sunday_held=False, april_held=False)
    assert awards("perfect_month", ctx) == []


def test_perfect_month_held_day_after_the_closing_sunday_cannot_change_it(ctx_builder, no_leak):
    # 3/30 closes March, so the award on 3/30 must not depend on who shoots the later Monday 3/31.
    ctx = late_monday_ctx(ctx_builder, last_sunday_held=True)
    assert awards("perfect_month", ctx) == [
        (1, "perfect_month", MARCH_30),
        (2, "perfect_month", MARCH_30),
    ]
    assert no_leak("perfect_month", ctx, MARCH_30) == (2, 0)


def test_perfect_month_held_monday_that_closes_the_month_counts(ctx_builder):
    # 3/30 is not an event, so the Monday 3/31 closes March and is one of its held events.
    ctx = late_monday_ctx(ctx_builder, last_sunday_held=False)
    assert awards("perfect_month", ctx) == [(2, "perfect_month", MARCH_31)]


def test_every_family_handles_a_shooter_with_no_rounds(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 30).build().for_shooter(99)
    for code in (
        "clays_broken",
        "clays_thrown",
        "events",
        "years_active",
        "big_year",
        "iron_streak",
        "personal_bests",
    ):
        assert registry.get(code).value(ctx).empty
    for code in (
        "doubleheader",
        "new_year",
        "anniversary_1",
        "welcome_back",
        "four_seasons",
        "perfect_month",
    ):
        assert awards(code, ctx) == []


# ---- no-leak (C12: each definition gets its own) ---------------------------------------------


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("clays_broken", clays_broken_ctx, sun(0)),
        ("clays_thrown", thrown_ctx, sun(3)),
        ("events", events_ctx, sun(5)),
        ("years_active", years_ctx, date(2025, 6, 1)),
        ("big_year", big_year_ctx, date(2025, 5, 11)),
        ("iron_streak", streak_ctx, sun(2)),
        ("personal_bests", pb_ctx, sun(4)),
        ("doubleheader", doubleheader_ctx, sun(0)),
        ("new_year", new_year_ctx, date(2025, 6, 1)),
        ("anniversary_1", anniversary_ctx, FIRST + timedelta(days=300)),
        ("anniversary_5", anniversary_ctx, FIRST + timedelta(days=400)),
        ("welcome_back", welcome_ctx, W2 - timedelta(days=1)),
        ("joined_club", joined_ctx, sun(0)),
        ("both_disciplines", disciplines_ctx, sun(1)),
        ("four_seasons", seasons_ctx, date(2025, 7, 6)),
        (
            "perfect_month",
            lambda b: month_ctx(b, last_sunday_held=False, april_held=True),
            MARCH_30,
        ),
        ("perfect_month", lambda b: late_monday_ctx(b, last_sunday_held=False), MARCH_30),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0  # the scenario has awards after the cut, so a leak would be visible
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_participation.py -v`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.analytics.achievements.participation'`, raised by the `last_sunday` import.

- [ ] **Step 3: Write the failing golden test**

Create `backend/tests/integration/achievements/test_ach_participation_golden.py`:

```python
"""Participation trophies on the committed fixtures (Plan 10 T2 golden).

Expected holder counts are derived from the raw `rounds` table with SQL, never from the achievement
code. The fx world ran the whole pipeline (incl. s50) once per pytest run.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

FAMILY_SQL = {
    "clays_broken": "sum(score)",
    "clays_thrown": "count(*) * 50",
    "events": "count(DISTINCT event_date)",
    "years_active": "count(DISTINCT extract(year FROM event_date))",
}
THRESHOLDS = {
    "clays_broken": (100, 500, 1000, 2500, 5000, 10000),
    "clays_thrown": (500, 1000, 2500, 5000, 10000),
    "events": (1, 10, 25, 50, 100, 150, 200, 250),
    "years_active": (2, 3, 5, 7),
}


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def awarded(session: Any, code: str) -> int:
    return scalar(session, "SELECT count(*) FROM achievements_awarded WHERE code = :c", c=code)


@pytest.mark.parametrize(
    ("family", "level", "threshold"),
    [
        (family, level, t)
        for family, ts in THRESHOLDS.items()
        for level, t in enumerate(ts, start=1)
    ],
)
def test_family_holder_counts_match_raw_rounds(fx_session, family, level, threshold):
    # FAMILY_SQL holds module constants only; the threshold is a bound parameter.
    holders = (
        "SELECT count(*) FROM (SELECT shooter_id FROM rounds GROUP BY shooter_id "  # noqa: S608
        f"HAVING {FAMILY_SQL[family]} >= :t) h"
    )
    expected = scalar(fx_session, holders, t=threshold)
    assert awarded(fx_session, f"{family}:{level}") == expected


@pytest.mark.parametrize(("level", "threshold"), [(1, 20), (2, 30), (3, 40)])
def test_big_year_holder_counts_match_raw_rounds(fx_session, level, threshold):
    expected = scalar(
        fx_session,
        "SELECT count(*) FROM (SELECT shooter_id FROM ("
        "SELECT shooter_id, extract(year FROM event_date) AS y, "
        "count(DISTINCT event_date) AS n FROM rounds GROUP BY 1, 2) per_year "
        "GROUP BY shooter_id HAVING max(n) >= :t) h",
        t=threshold,
    )
    assert awarded(fx_session, f"big_year:{level}") == expected


def test_documented_anchor_counts(fx_session):
    # Hand-checked against the raw workbook when this plan was written (332 identity keys).
    assert awarded(fx_session, "clays_broken:3") == 65
    assert awarded(fx_session, "events:2") == 107


def test_clays_broken_awards_are_dated_at_first_crossing(fx_session):
    expected = dict(
        fx_session.execute(
            text(
                "SELECT shooter_id, min(event_date) FROM ("
                " SELECT shooter_id, event_date,"
                "  sum(day_sum) OVER (PARTITION BY shooter_id ORDER BY event_date) AS running"
                " FROM (SELECT shooter_id, event_date, sum(score) AS day_sum"
                "  FROM rounds GROUP BY 1, 2) d"
                ") c WHERE running >= 1000 GROUP BY shooter_id"
            )
        ).all()
    )
    got = dict(
        fx_session.execute(
            text(
                "SELECT shooter_id, event_date FROM achievements_awarded "
                "WHERE code = 'clays_broken:3'"
            )
        ).all()
    )
    assert got == expected


def test_doubleheader_holders_match_raw_rounds(fx_session):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT shooter_id) FROM (SELECT shooter_id, event_date FROM rounds "
        "GROUP BY 1, 2 HAVING count(*) >= 2) d",
    )
    assert awarded(fx_session, "doubleheader") == expected


def test_joined_club_holders_match_raw_rounds(fx_session):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT m.shooter_id) FROM rounds m JOIN rounds g "
        "ON g.shooter_id = m.shooter_id AND g.event_date < m.event_date "
        "WHERE m.status = 'member' AND g.status = 'guest'",
    )
    assert awarded(fx_session, "joined_club") == expected


def test_welcome_back_awards_match_raw_gaps(fx_session):
    gaps = (
        "SELECT shooter_id, event_date - lag(event_date) "
        "OVER (PARTITION BY shooter_id ORDER BY event_date) AS gap "
        "FROM (SELECT DISTINCT shooter_id, event_date FROM rounds) d"
    )
    # `gaps` is the constant above; nothing user-supplied reaches these f-strings.
    returns = f"SELECT count(*) FROM ({gaps}) g WHERE gap >= 180"  # noqa: S608
    returners = f"SELECT count(DISTINCT shooter_id) FROM ({gaps}) g WHERE gap >= 180"  # noqa: S608
    awarded_shooters = (
        "SELECT count(DISTINCT shooter_id) FROM achievements_awarded WHERE code = 'welcome_back'"
    )
    assert awarded(fx_session, "welcome_back") == scalar(fx_session, returns)
    assert scalar(fx_session, awarded_shooters) == scalar(fx_session, returners)
```

- [ ] **Step 4: Run the golden test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/achievements/test_ach_participation_golden.py -v`
Expected: FAIL. `test_documented_anchor_counts` fails with `assert 0 == 65`, and the family counts fail with `0 == <expected>`, because no participation achievement is registered yet.

- [ ] **Step 5: Implement the participation trophies**

Create `backend/src/sunday_clays/analytics/achievements/participation.py`:

```python
"""Participation trophies (C12, Plan 10 T2): non-ranking milestone families and calendar /
participation one-offs. Every definition reads only data dated on or before its award date."""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterator
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext, empty_value_frame
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    make_tiers,
    register,
)
from sunday_clays.analytics.frames import season_label

TARGETS_PER_ROUND = 50
PB_MIN_PRIOR_ROUNDS = 5
WELCOME_BACK_DAYS = 180
ANNIVERSARY_WINDOW_DAYS = 7
PERFECT_MONTH_MIN_EVENTS = 3


def _series(days: pd.DataFrame, values: pd.Series) -> pd.DataFrame:
    if days.empty:
        return empty_value_frame()
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"].to_numpy(),
            "event_date": days["event_ts"].to_numpy(),
            "value": values.to_numpy(dtype=float),
        }
    )


# ---- tiered value functions (cumulative value after each attended date) ---------------------


def clays_broken_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return _series(days, days["cum_sum"])


def clays_thrown_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return _series(days, days["cum_rounds"] * TARGETS_PER_ROUND)


def events_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    return _series(days, days["n_events"])


def years_active_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    keys = pd.DataFrame({"shooter_id": days["shooter_id"], "year": days["event_ts"].dt.year})
    first_in_year = (~keys.duplicated()).astype(int)
    return _series(days, first_in_year.groupby(days["shooter_id"]).cumsum())


def big_year_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    year = days["event_ts"].dt.year
    in_year = days.groupby([days["shooter_id"], year]).cumcount() + 1
    return _series(days, in_year.groupby(days["shooter_id"]).cummax())


def iron_streak_value(ctx: AchContext) -> pd.DataFrame:
    """Longest run of consecutive held events attended, from analytics.streaks.streaks() (C7)."""
    days = ctx.shooter_days
    if days.empty:
        return empty_value_frame()
    parts: list[pd.DataFrame] = []
    for day in sorted(set(days["event_date"])):
        longest = ctx.streaks_at(day).set_index("shooter_id")["longest_streak"]
        attending = days[days["event_date"] == day]
        parts.append(
            pd.DataFrame(
                {
                    "shooter_id": attending["shooter_id"].to_numpy(),
                    "event_date": attending["event_ts"].to_numpy(),
                    "value": attending["shooter_id"].map(longest).fillna(0).to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def personal_bests_value(ctx: AchContext) -> pd.DataFrame:
    """New PBs: the day's best round beats every round on earlier dates (>= 5 of them).

    At most one per day, however many rounds the shooter shot that day."""
    days = ctx.shooter_days
    new_pb = (
        (days["prior_rounds"] >= PB_MIN_PRIOR_ROUNDS) & (days["day_best"] > days["prior_best"])
    ).astype(int)
    return _series(days, new_pb.groupby(days["shooter_id"]).cumsum())


# ---- one-offs ---------------------------------------------------------------------------------


def _doubleheader(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    hits = days[days["n_rounds"] >= 2]
    for sid, day, n in zip(hits["shooter_id"], hits["event_date"], hits["n_rounds"], strict=True):
        yield Award(int(sid), "doubleheader", day, None, {"rounds": int(n)})


def _new_year(ctx: AchContext) -> Iterator[Award]:
    first_held: dict[int, date] = {}
    for day in ctx.held_dates():
        first_held.setdefault(day.year, day)
    days = ctx.shooter_days
    hits = days[days["event_date"].isin(set(first_held.values()))]
    for sid, day, rid in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], strict=True
    ):
        yield Award(int(sid), "new_year", day, int(rid), {"year": day.year})


def _anniversary(years: int) -> Callable[[AchContext], Iterator[Award]]:
    code = f"anniversary_{years}"
    low = 365 * years - ANNIVERSARY_WINDOW_DAYS
    high = 365 * years + ANNIVERSARY_WINDOW_DAYS

    def evaluate(ctx: AchContext) -> Iterator[Award]:
        days = ctx.shooter_days
        since_first = (
            days["event_ts"] - days.groupby("shooter_id")["event_ts"].transform("min")
        ).dt.days
        hits = days[(since_first >= low) & (since_first <= high)]
        for sid, day in zip(hits["shooter_id"], hits["event_date"], strict=True):
            yield Award(int(sid), code, day, None, {"years": years})

    return evaluate


def _welcome_back(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    gap = (days["event_ts"] - days["prev_ts"]).dt.days
    back = gap >= WELCOME_BACK_DAYS
    hits = days[back]
    for sid, day, rid, away in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], gap[back], strict=True
    ):
        yield Award(int(sid), "welcome_back", day, int(rid), {"days_away": int(away)})


def _joined_club(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    first_guest = rounds[rounds["status"] == "guest"].groupby("shooter_id")["event_ts"].min()
    if first_guest.empty:
        return
    members = rounds[rounds["status"] == "member"].sort_values(
        ["shooter_id", "event_ts", "ordinal"], kind="stable"
    )
    later = members[members["event_ts"] > pd.to_datetime(members["shooter_id"].map(first_guest))]
    first = later.groupby("shooter_id", sort=True).head(1)
    for sid, ts, rid in zip(first["shooter_id"], first["event_ts"], first["round_id"], strict=True):
        yield Award(int(sid), "joined_club", ts.date(), int(rid), {})


def _both_disciplines(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    typed = rounds[rounds["round_type"].isin(["sporting", "super_sporting"])]
    if typed.empty:
        return
    firsts = (
        typed.groupby(["shooter_id", "round_type"])["event_ts"]
        .min()
        .unstack()
        .reindex(columns=["sporting", "super_sporting"])
        .dropna()
    )
    for sid, sporting, super_sporting in zip(
        firsts.index, firsts["sporting"], firsts["super_sporting"], strict=True
    ):
        yield Award(int(sid), "both_disciplines", max(sporting, super_sporting).date(), None, {})


def _four_seasons(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    if days.empty:
        return
    frame = pd.DataFrame(
        {
            "shooter_id": days["shooter_id"],
            "event_ts": days["event_ts"],
            "event_date": days["event_date"],
        }
    )
    frame["season_year"] = frame["event_ts"].dt.year + (frame["event_ts"].dt.month == 12).astype(
        int
    )
    frame["season"] = [season_label(day) for day in frame["event_date"]]
    new_season = (~frame.duplicated(["shooter_id", "season_year", "season"])).astype(int)
    frame["n_seasons"] = new_season.groupby([frame["shooter_id"], frame["season_year"]]).cumsum()
    first = frame[frame["n_seasons"] >= 4].groupby("shooter_id", sort=True).head(1)
    for sid, day, season_year in zip(
        first["shooter_id"], first["event_date"], first["season_year"], strict=True
    ):
        yield Award(int(sid), "four_seasons", day, None, {"season_year": int(season_year)})


def last_sunday(year: int, month: int) -> date:
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() + 1) % 7)


def _perfect_month(ctx: AchContext) -> Iterator[Award]:
    """Month M with >= 3 held events, every one attended.

    Dated at the closing event: the first held event on or after M's last calendar Sunday L
    (L itself when L was held). Only M's held events up to the closing event count, so a held
    non-Sunday after a held L cannot change an award already dated L (no leak, never moves)."""
    held = ctx.held_dates()
    days = ctx.shooter_days
    attendees: dict[date, set[int]] = {}
    for sid, day in zip(days["shooter_id"], days["event_date"], strict=True):
        attendees.setdefault(day, set()).add(int(sid))
    months: dict[tuple[int, int], list[date]] = {}
    for day in held:
        months.setdefault((day.year, day.month), []).append(day)
    for (year, month), month_days in sorted(months.items()):
        cutoff = last_sunday(year, month)
        closing = next((day for day in held if day >= cutoff), None)
        if closing is None:
            continue
        counted = [day for day in month_days if day <= closing]
        if len(counted) < PERFECT_MONTH_MIN_EVENTS:
            continue
        perfect = set(attendees.get(counted[0], set()))
        for day in counted[1:]:
            perfect &= attendees.get(day, set())
        for sid in sorted(perfect):
            yield Award(sid, "perfect_month", closing, None, {"month": f"{year:04d}-{month:02d}"})


# ---- registration -----------------------------------------------------------------------------

register(
    Achievement(
        code="clays_broken",
        name="Clays Broken",
        description="Lifetime targets broken (the sum of every round's score).",
        category=Category.MILESTONE,
        art_key="clays_broken",
        tiers=make_tiers((100, 500, 1000, 2500, 5000, 10000), "clays broken"),
        value=clays_broken_value,
    )
)
register(
    Achievement(
        code="clays_thrown",
        name="Clays Thrown",
        description="Lifetime targets thrown at you: 50 per round.",
        category=Category.MILESTONE,
        art_key="clays_thrown",
        tiers=make_tiers((500, 1000, 2500, 5000, 10000), "clays thrown"),
        value=clays_thrown_value,
    )
)
register(
    Achievement(
        code="events",
        name="Events Attended",
        description="Sundays with at least one recorded round.",
        category=Category.MILESTONE,
        art_key="events",
        tiers=make_tiers((1, 10, 25, 50, 100, 150, 200, 250), "events", singular="event"),
        value=events_value,
    )
)
register(
    Achievement(
        code="years_active",
        name="Years Active",
        description="Distinct calendar years with at least one round.",
        category=Category.MILESTONE,
        art_key="years_active",
        tiers=make_tiers((2, 3, 5, 7), "years"),
        value=years_active_value,
    )
)
register(
    Achievement(
        code="big_year",
        name="Big Year",
        description="Most events attended in a single calendar year.",
        category=Category.MILESTONE,
        art_key="big_year",
        tiers=make_tiers((20, 30, 40), "events in one year"),
        value=big_year_value,
    )
)
register(
    Achievement(
        code="iron_streak",
        name="Iron Streak",
        description=(
            "Consecutive held events attended; attendance-only dates neither extend nor break it."
        ),
        category=Category.MILESTONE,
        art_key="iron_streak",
        tiers=make_tiers((4, 8, 12, 26), "straight events"),
        value=iron_streak_value,
    )
)
register(
    Achievement(
        code="personal_bests",
        name="Personal Bests",
        description="Days whose best round beat every earlier round (after at least 5 rounds).",
        category=Category.SCORING,
        art_key="personal_bests",
        tiers=make_tiers((1, 5, 10), "personal bests", singular="personal best"),
        value=personal_bests_value,
    )
)
register(
    Achievement(
        code="doubleheader",
        name="Doubleheader",
        description="Shot two rounds on the same Sunday.",
        category=Category.MILESTONE,
        art_key="doubleheader",
        evaluate=_doubleheader,
    )
)
register(
    Achievement(
        code="new_year",
        name="New Year's Shooter",
        description="Shot the first held event of a calendar year.",
        category=Category.CALENDAR,
        art_key="new_year",
        evaluate=_new_year,
    )
)
register(
    Achievement(
        code="anniversary_1",
        name="One-Year Anniversary",
        description="Shot within a week of the first anniversary of your first event.",
        category=Category.CALENDAR,
        art_key="anniversary_1",
        evaluate=_anniversary(1),
    )
)
register(
    Achievement(
        code="anniversary_5",
        name="Five-Year Anniversary",
        description="Shot within a week of the fifth anniversary of your first event.",
        category=Category.CALENDAR,
        art_key="anniversary_5",
        evaluate=_anniversary(5),
    )
)
register(
    Achievement(
        code="welcome_back",
        name="Welcome Back",
        description="Returned after 180 or more days away.",
        category=Category.CALENDAR,
        art_key="welcome_back",
        evaluate=_welcome_back,
        repeatable=True,
    )
)
register(
    Achievement(
        code="joined_club",
        name="Joined the Club",
        description="Shot as a member after first shooting as a guest.",
        category=Category.MILESTONE,
        art_key="joined_club",
        evaluate=_joined_club,
    )
)
register(
    Achievement(
        code="both_disciplines",
        name="Both Disciplines",
        description="Shot both a sporting and a super sporting day.",
        category=Category.MILESTONE,
        art_key="both_disciplines",
        evaluate=_both_disciplines,
    )
)
register(
    Achievement(
        code="four_seasons",
        name="Four Seasons",
        description=(
            "Shot in winter, spring, summer and fall of one year "
            "(December counts toward the next winter)."
        ),
        category=Category.CALENDAR,
        art_key="four_seasons",
        evaluate=_four_seasons,
    )
)
register(
    Achievement(
        code="perfect_month",
        name="Perfect Month",
        description="Attended every held event of a month with three or more held events.",
        category=Category.CALENDAR,
        art_key="perfect_month",
        evaluate=_perfect_month,
        repeatable=True,
    )
)
```

- [ ] **Step 6: Run the unit and golden tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_participation.py tests/integration/achievements/test_ach_participation_golden.py -v`
Expected: PASS. Every unit test, every no-leak case and every golden count is green, including `clays_broken:3 == 65` and `events:2 == 107`.

- [ ] **Step 7: Run the full backend suite with lint, types and coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: PASS with coverage ≥90% lines and branches. Task 1's route and s50 tests must still pass: they use an isolated registry, so the new definitions do not change their expectations.

- [ ] **Step 8: Commit**

```bash
git add backend/src/sunday_clays/analytics/achievements/participation.py \
  backend/tests/unit/analytics/achievements/test_ach_participation.py \
  backend/tests/integration/achievements/test_ach_participation_golden.py
git commit -m "feat(achievements): add milestone families and participation trophies" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: Scoring, conditions and competition trophies (master Plan 10 T3)

> **Removed 2026-09-29:** `giant_killer` and `class_up` (and `AchContext.classes_at`) were dropped from the catalog. Every mention of them in this plan is historical.

**Context:** This task adds the scoring, weather/equipment and competition trophies.
- Contract:
  - C12: codes and "prior means earlier dates".
  - C7: full-field `event_rank` min-rank over best rounds, where ties share a rank. Achievements ignore every filter. Weather thresholds match condition `rain` (precip ≥ 0.02 in).
  - The master T3 bullet: exact thresholds, `giant_killer` uses `mu_before` (never `mu_after`), `class_up` uses `assign_classes(history, rounds, as_of=<this event's date>)`.
- `SxS` is an action, not a gauge, and never earns `sub_gauge`. `unknown_gauge_class` values never qualify.
- The `sub_gauge` golden's 17 holders are computed from the raw workbook rows: the distinct names on the 18 qualifying rows (`Sub-Gauge` 9, `28 Gauge` 8 including the one `29 Gauge` cell read as `28 Gauge`, `20 Gauge` 1, no `.410`; recounted with openpyxl on 2026-09-28).
- Every definition gets its own no-leak test.
- Coverage stays ≥90% lines and branches, and ruff and mypy stay clean.

**Branch:** `task/10-3-scoring-competition-trophies`

**Depends on:** Plan 10 T1 (and, through T1, Plan 06 T2 metrics, Plan 06 T4 `assign_classes` and skill columns, and Plan 05 T3 weather columns).

**Files:**
- Create: `backend/src/sunday_clays/analytics/achievements/scores.py`
- Create: `backend/src/sunday_clays/analytics/achievements/conditions.py`
- Create: `backend/src/sunday_clays/analytics/achievements/competition.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_scores.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_conditions.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_competition.py`
- Test: `backend/tests/integration/achievements/test_ach_scoring_golden.py`

**Interfaces:**
- Consumes (from Task 1):
  - `AchContext`: `.rounds`, whose C7 columns this task reads are `score`, `ordinal`, `gauge_class`, `event_rank`, `is_best_round`, `mu_before`, `temp_f`, `precip_in` and `gust_mph`. It also uses `.shooter_days` and `.classes_at(day)`.
  - `empty_value_frame`, `Achievement`, `Award`, `Category`, `make_tiers`, `register`, `registry.get`, `registry.evaluate_one`
  - Unit fixtures `ctx_builder` and `no_leak`.
- Produces the registered achievements below (exact names in the code).

| Code | Kind | Category | Rule |
|---|---|---|---|
| `round_score` | tiers 30/35/40/45/48/50 "in one round" | scoring | best single round so far |
| `comeback` | repeatable | scoring | day's best ≥ best at previous attended event + 15, ≥ 5 earlier rounds, once/day |
| `above_average_3` | one-off | scoring | 3 consecutive attended events whose best round > career average over earlier-dated rounds, each with ≥ 10 earlier rounds |
| `sub_gauge` | one-off | conditions | normalized gauge ∈ {`Sub-Gauge`, `20 Gauge`, `28 Gauge`, `.410`} |
| `rain` / `cold` / `heat` / `wind` | one-off | conditions | precip ≥ 0.02 in / temp < 35 °F / temp ≥ 85 °F / gust ≥ 20 mph |
| `all_weather` | one-off | conditions | holds rain, cold, heat and wind; dated when the fourth is earned |
| `mudder` | one-off | conditions | score ≥ 40 with precip ≥ 0.02 in |
| `first_win` | one-off | competition | best-round rank 1 (ties count), ≥ 5 shooters |
| `podium` | one-off | competition | best-round rank ≤ 3, ≥ 5 shooters |
| `giant_killer` | repeatable | competition | ranked strictly ahead of every top-`mu_before` shooter while own `mu_before` ≤ theirs − 3, ≥ 5 shooters |
| `class_up` | repeatable | competition | class at this event better than at the previous attended event, both non-null |

- [ ] **Step 1: Write the failing scoring tests**

Create `backend/tests/unit/analytics/achievements/test_ach_scores.py`:

```python
"""Scoring trophies (Plan 10 T3): round_score, comeback, above_average_3."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def round_score_ctx(b):
    return (
        b()
        .round(1, sun(0), 38)
        .round(1, sun(1), 33)
        .round(1, sun(2), 41)
        .round(2, sun(0), 29)
        .build()
    )


def comeback_ctx(b):
    builder = b()
    for sid in (1, 2, 3, 4):
        for i in range(4 if sid == 3 else 5):
            builder.round(sid, sun(i), 30)  # rounds 1-5 (s1), 6-10 (s2), 11-14 (s3), 15-19 (s4)
    # rounds 20, 21: 45 = 30 + 15 qualifies; 46 < 45 + 15 (sun(6) compares with sun(5), not sun(4))
    builder.round(1, sun(5), 45).round(1, sun(6), 46)
    builder.round(2, sun(5), 44)  # round 22: 44 < 30 + 15 (a gain of 14)
    builder.round(3, sun(4), 45)  # round 23: only 4 earlier rounds
    # rounds 24-27: both sun(5) rounds clear 30 + 15, one award on the best (46); sun(7) compares
    # with sun(6)'s 30, not the career best 46
    builder.round(4, sun(5), 45).round(4, sun(5), 46).round(4, sun(6), 30).round(4, sun(7), 45)
    return builder.build()


def above_ctx(b):
    builder = b()
    for i in range(10):
        builder.round(1, sun(i), 30)
    for i, score in zip(range(10, 16), [31, 32, 29, 33, 34, 35], strict=True):
        builder.round(1, sun(i), score)
    for i in range(9):
        builder.round(2, sun(i), 30)
    for i in range(9, 12):
        builder.round(2, sun(i), 40)  # sun(9) has only 9 earlier rounds, so the run is 2 long
    return builder.build()


def test_round_score_awards_each_crossed_tier(ctx_builder):
    assert awards("round_score", round_score_ctx(ctx_builder)) == [
        (1, "round_score:1", sun(0)),
        (1, "round_score:2", sun(0)),
        (1, "round_score:3", sun(2)),
    ]


def test_comeback_once_per_day_uses_best_round(ctx_builder):
    got = sorted(
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_one(registry.get("comeback"), comeback_ctx(ctx_builder))
    )
    assert got == [(1, sun(5), 20), (4, sun(5), 25), (4, sun(7), 27)]


def test_above_average_needs_three_straight_events_with_ten_prior_rounds(ctx_builder):
    assert awards("above_average_3", above_ctx(ctx_builder)) == [(1, "above_average_3", sun(15))]


def test_scoring_trophies_handle_an_empty_context(ctx_builder):
    ctx = ctx_builder().build()
    assert registry.get("round_score").value(ctx).empty
    assert awards("comeback", ctx) == []
    assert awards("above_average_3", ctx) == []


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("round_score", round_score_ctx, sun(1)),
        ("comeback", comeback_ctx, sun(6)),
        ("above_average_3", above_ctx, sun(14)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
```

- [ ] **Step 2: Write the failing conditions tests**

Create `backend/tests/unit/analytics/achievements/test_ach_conditions.py`:

```python
"""Conditions trophies (Plan 10 T3): sub_gauge, rain/cold/heat/wind, all_weather, mudder."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def gauge_ctx(b):
    return (
        b()
        .round(1, sun(0), 30, gauge_class="20 Gauge")
        .round(2, sun(0), 30, gauge_class="SxS")
        .round(3, sun(0), 30, gauge_class="12 Gauge")
        .round(4, sun(0), 30, gauge_class="Pump")  # an unknown_gauge_class value kept verbatim
        .round(5, sun(0), 30)  # not recorded
        .round(6, sun(1), 30, gauge_class=".410")
        .round(6, sun(2), 30, gauge_class="Sub-Gauge")
        .round(7, sun(3), 30, gauge_class="28 Gauge")
        .build()
    )


def weather_ctx(b):
    return (
        b()
        .event(sun(0), precip_in=0.02, temp_f=50.0, gust_mph=5.0)
        .event(sun(1), precip_in=0.019, temp_f=34.9, gust_mph=19.9)
        .event(sun(2), precip_in=0.0, temp_f=35.0, gust_mph=20.0)
        .event(sun(3), precip_in=0.0, temp_f=85.0, gust_mph=5.0)
        .event(sun(4), precip_in=0.0, temp_f=84.9, gust_mph=5.0)
        .event(sun(6), precip_in=0.5, temp_f=55.0, gust_mph=8.0)
        .round(1, sun(0), 30)
        .round(1, sun(1), 30)
        .round(1, sun(2), 30)
        .round(1, sun(3), 30)
        .round(2, sun(2), 30)
        .round(2, sun(4), 30)
        .round(2, sun(6), 42)
        .round(3, sun(5), 45)  # sun(5) has no event_weather row
        .build()
    )


def test_sub_gauge_accepts_only_sub_gauges(ctx_builder):
    assert awards("sub_gauge", gauge_ctx(ctx_builder)) == [
        (1, "sub_gauge", sun(0)),
        (6, "sub_gauge", sun(1)),
        (7, "sub_gauge", sun(3)),
    ]


def test_sxs_does_not_earn_sub_gauge(ctx_builder):
    assert awards("sub_gauge", ctx_builder().round(2, sun(0), 30, gauge_class="SxS").build()) == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("rain", [(1, "rain", sun(0)), (2, "rain", sun(6))]),
        ("cold", [(1, "cold", sun(1))]),
        ("heat", [(1, "heat", sun(3))]),
        ("wind", [(1, "wind", sun(2)), (2, "wind", sun(2))]),
        ("all_weather", [(1, "all_weather", sun(3))]),
        ("mudder", [(2, "mudder", sun(6))]),
    ],
)
def test_weather_trophy_thresholds(ctx_builder, code, expected):
    assert awards(code, weather_ctx(ctx_builder)) == expected


def test_weather_details_record_the_measurement(ctx_builder):
    [rain] = [
        w
        for w in registry.evaluate_one(registry.get("rain"), weather_ctx(ctx_builder))
        if w.shooter_id == 2
    ]
    assert (rain.round_id, dict(rain.details)) == (7, {"precip_in": 0.5})


def test_mudder_needs_forty_in_the_rain(ctx_builder):
    ctx = (
        ctx_builder()
        .event(sun(0), precip_in=0.02)
        .event(sun(1), precip_in=0.0)
        .round(1, sun(0), 40)
        .round(2, sun(0), 39)
        .round(3, sun(1), 45)
        .build()
    )
    got = [
        (w.shooter_id, w.event_date, w.round_id)
        for w in registry.evaluate_one(registry.get("mudder"), ctx)
    ]
    assert got == [(1, sun(0), 1)]


def test_weather_trophies_skip_events_without_weather(ctx_builder):
    ctx = weather_ctx(ctx_builder)
    for code in ("rain", "cold", "heat", "wind", "all_weather", "mudder"):
        assert all(w.shooter_id != 3 for w in registry.evaluate_one(registry.get(code), ctx))


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("sub_gauge", gauge_ctx, sun(1)),
        ("rain", weather_ctx, sun(2)),
        ("cold", weather_ctx, sun(0)),
        ("heat", weather_ctx, sun(2)),
        ("wind", weather_ctx, sun(1)),
        ("all_weather", weather_ctx, sun(2)),
        ("mudder", weather_ctx, sun(2)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
```

- [ ] **Step 3: Write the failing competition tests**

Create `backend/tests/unit/analytics/achievements/test_ach_competition.py`:

```python
"""Competition trophies (Plan 10 T3): first_win, podium, giant_killer, class_up."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def field(builder, day, scores, first_sid=1):
    for offset, score in enumerate(scores):
        builder.round(first_sid + offset, day, score)
    return builder


def win_ctx(b):
    builder = b()
    field(builder, sun(0), [45, 45, 40, 35, 30])  # shooters 1-5, a tie for first
    field(builder, sun(1), [44, 43, 42, 41])  # only 4 shooters
    # shooter 1 wins again; shooters 2-3 already have podiums
    field(builder, sun(2), [50, 20, 19, 18, 17])
    field(builder, sun(3), [30, 31, 32, 33, 49])  # shooter 5 wins
    return builder.build()


def giant_ctx(b):
    builder = b()
    nan = float("nan")
    for sid, score, mu in [
        (1, 43, 40.0),
        (2, 45, 37.0),
        (3, 44, 38.0),
        (4, 40, 30.0),
        (5, 30, nan),
    ]:
        builder.round(sid, sun(0), score, mu_before=mu)
    for sid, score, mu in [(1, 43, 40.0), (2, 45, 30.0), (3, 44, 38.0), (4, 40, 30.0)]:
        builder.round(sid, sun(1), score, mu_before=mu)  # only 4 shooters
    for sid, score, mu in [
        (1, 44, 40.0),
        (6, 30, 40.0),
        (2, 43, 36.0),
        (3, 45, 36.0),
        (4, 20, 30.0),
    ]:
        builder.round(sid, sun(2), score, mu_before=mu)  # two co-favourites at mu 40
    return builder.build()


MUS = {4: [40.0, 35.0, 30.0, 25.0], 5: [40.0, 35.0, 30.0, 45.0]}


def class_ctx(b):
    builder = b()
    for i in range(6):
        mus = MUS.get(i, [30.0, 30.0, 30.0, 30.0])
        for sid in (1, 2, 3, 4):
            builder.round(sid, sun(i), 30).rating(sid, sun(i), mus[sid - 1])
    return builder.build()


def test_first_win_ties_count(ctx_builder):
    assert awards("first_win", win_ctx(ctx_builder)) == [
        (1, "first_win", sun(0)),
        (2, "first_win", sun(0)),
        (5, "first_win", sun(3)),
    ]


def test_podium_needs_top_three_in_a_field_of_five(ctx_builder):
    assert awards("podium", win_ctx(ctx_builder)) == [
        (1, "podium", sun(0)),
        (2, "podium", sun(0)),
        (3, "podium", sun(0)),
        (4, "podium", sun(3)),
        (5, "podium", sun(3)),
    ]


def test_giant_killer_must_outrank_every_co_favourite(ctx_builder):
    assert awards("giant_killer", giant_ctx(ctx_builder)) == [
        (2, "giant_killer", sun(0)),
        (3, "giant_killer", sun(2)),
    ]


def test_giant_killer_details_name_the_giant(ctx_builder):
    [first] = [
        w
        for w in registry.evaluate_one(registry.get("giant_killer"), giant_ctx(ctx_builder))
        if w.event_date == sun(0)
    ]
    assert dict(first.details) == {"giant_shooter_id": 1, "giant_mu": 40.0, "mu": 37.0}


def test_giant_killer_skips_missing_ratings(ctx_builder):
    builder = ctx_builder()
    field(builder, sun(0), [45, 44, 43, 42, 41])  # mu_before is NaN everywhere
    assert awards("giant_killer", builder.build()) == []


def test_class_up_compares_with_previous_attended_event(ctx_builder):
    got = [
        (w.shooter_id, w.event_date, dict(w.details))
        for w in registry.evaluate_one(registry.get("class_up"), class_ctx(ctx_builder))
    ]
    assert got == [(4, sun(5), {"from": "C", "to": "A"})]


def test_competition_trophies_handle_an_empty_context(ctx_builder):
    ctx = ctx_builder().build()
    for code in ("first_win", "podium", "giant_killer", "class_up"):
        assert awards(code, ctx) == []


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("first_win", win_ctx, sun(2)),
        ("podium", win_ctx, sun(2)),
        ("giant_killer", giant_ctx, sun(1)),
        ("class_up", class_ctx, sun(4)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
```

Hand check of `class_ctx`, using the C7 class rules with 4 active shooters (q = 0, .25, .5, .75 → A, B, C, C):
- sun(4) is the first date with ≥5 rounds each. The classes by mu 40/35/30/25 are A/B/C/C, but the previous event (sun(3)) had no active shooters, so there is no award.
- At sun(5), shooter 4's mu of 45 ranks first: C → A. Shooters 1, 2 and 3 drop or stay.

- [ ] **Step 4: Run the three unit files to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_scores.py tests/unit/analytics/achievements/test_ach_conditions.py tests/unit/analytics/achievements/test_ach_competition.py -v`
Expected: FAIL. Every test fails with `KeyError: "unknown achievement 'round_score'"` (and likewise for `sub_gauge`, `first_win`, …).

- [ ] **Step 5: Write the failing golden test**

Create `backend/tests/integration/achievements/test_ach_scoring_golden.py`:

```python
"""Scoring/competition trophies on the committed fixtures (Plan 10 T3 golden)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

# Hand-checked against the raw workbook (C3 gauge normalization; 29 Gauge → 28 Gauge).
SUB_GAUGE_NAME_KEYS = {
    "waldrop quentin",
    "nickerson neal",
    "leavitt barry",
    "cadogan desmond",
    "crandall emmanuel",
    "eldridge tucker",
    "bellamont damon",
    "hadley ike",
    "isaacson abner",
    "abernathy preston",
    "kaplan noel",
    "yoder gavin",
    "hubbell alton",
    "kolmanov dmitri",
    "colburn iris",
    "dunleavy jasper",
    "hathaway doyle",
}


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def test_sub_gauge_holders_match_fixture(fx_session):
    keys = {
        key
        for (key,) in fx_session.execute(
            text(
                "SELECT r.name_key FROM achievements_awarded a JOIN rounds r ON r.id = a.round_id "
                "WHERE a.code = 'sub_gauge'"
            )
        ).all()
    }
    assert keys == SUB_GAUGE_NAME_KEYS
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'sub_gauge'")
        == 17
    )


@pytest.mark.parametrize(("code", "max_rank"), [("first_win", 1), ("podium", 3)])
def test_rank_trophy_holders_match_round_metrics(fx_session, code, max_rank):
    expected = scalar(
        fx_session,
        "SELECT count(DISTINCT r.shooter_id) FROM rounds r "
        "JOIN round_metrics m ON m.round_id = r.id "
        "WHERE m.is_best_round AND m.event_rank <= :rank AND r.event_date IN ("
        " SELECT event_date FROM rounds GROUP BY event_date"
        " HAVING count(DISTINCT shooter_id) >= 5)",
        rank=max_rank,
    )
    assert (
        scalar(fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = :c", c=code)
        == expected
        > 0
    )
```

- [ ] **Step 6: Run the golden test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/achievements/test_ach_scoring_golden.py -v`
Expected: FAIL with `assert set() == {'waldrop quentin', …}` and `0 == <expected>`.

- [ ] **Step 7: Implement the scoring trophies**

Create `backend/src/sunday_clays/analytics/achievements/scores.py`:

```python
"""Scoring trophies (C12, Plan 10 T3): best-round tiers, comebacks and above-average runs.

"Earlier" always means earlier dates (AchContext.shooter_days prior_* / prev_* columns)."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext, empty_value_frame
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    make_tiers,
    register,
)

COMEBACK_MIN_GAIN = 15
COMEBACK_MIN_PRIOR_ROUNDS = 5
ABOVE_AVERAGE_MIN_PRIOR_ROUNDS = 10
ABOVE_AVERAGE_RUN = 3


def round_score_value(ctx: AchContext) -> pd.DataFrame:
    days = ctx.shooter_days
    if days.empty:
        return empty_value_frame()
    best = days.groupby("shooter_id")["day_best"].cummax()
    return pd.DataFrame(
        {
            "shooter_id": days["shooter_id"].to_numpy(),
            "event_date": days["event_ts"].to_numpy(),
            "value": best.to_numpy(dtype=float),
        }
    )


def _comeback(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    hits = days[
        (days["prior_rounds"] >= COMEBACK_MIN_PRIOR_ROUNDS)
        & (days["day_best"] >= days["prev_day_best"] + COMEBACK_MIN_GAIN)
    ]
    for sid, day, rid, best, previous in zip(
        hits["shooter_id"],
        hits["event_date"],
        hits["best_round_id"],
        hits["day_best"],
        hits["prev_day_best"],
        strict=True,
    ):
        yield Award(
            int(sid), "comeback", day, int(rid), {"best": int(best), "previous_best": int(previous)}
        )


def _above_average_3(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    if days.empty:
        return
    prior_rounds = days["prior_rounds"]
    career_average = days["prior_sum"] / prior_rounds.where(prior_rounds > 0)
    qualifies = (prior_rounds >= ABOVE_AVERAGE_MIN_PRIOR_ROUNDS) & (
        days["day_best"] > career_average
    )
    run_id = (~qualifies).astype(int).groupby(days["shooter_id"]).cumsum()
    run_length = qualifies.astype(int).groupby([days["shooter_id"], run_id]).cumsum()
    hits = days[run_length >= ABOVE_AVERAGE_RUN]
    for sid, day, rid in zip(
        hits["shooter_id"], hits["event_date"], hits["best_round_id"], strict=True
    ):
        yield Award(int(sid), "above_average_3", day, int(rid), {})


register(
    Achievement(
        code="round_score",
        name="Round Score",
        description="Your best single round.",
        category=Category.SCORING,
        art_key="round_score",
        tiers=make_tiers((30, 35, 40, 45, 48, 50), "in one round"),
        value=round_score_value,
    )
)
register(
    Achievement(
        code="comeback",
        name="Comeback",
        description=(
            "Beat your previous event's best round by 15 or more (after at least 5 rounds)."
        ),
        category=Category.SCORING,
        art_key="comeback",
        evaluate=_comeback,
        repeatable=True,
    )
)
register(
    Achievement(
        code="above_average_3",
        name="Above Average ×3",  # noqa: RUF001
        description=(
            "Three events in a row with a best round above your career average "
            "(after at least 10 rounds)."
        ),
        category=Category.SCORING,
        art_key="above_average_3",
        evaluate=_above_average_3,
    )
)
```

- [ ] **Step 8: Implement the conditions trophies**

Create `backend/src/sunday_clays/analytics/achievements/conditions.py`:

```python
"""Conditions trophies (C12, Plan 10 T3): sub-gauge and weather.

Weather comes from the event's 10:00-12:00 event_weather aggregate (C7) via frames.load_rounds;
an event without it earns nothing."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category, register

# SxS is an action, not a gauge.
SUB_GAUGES = frozenset({"Sub-Gauge", "20 Gauge", "28 Gauge", ".410"})
RAIN_IN = 0.02
COLD_BELOW_F = 35.0
HEAT_AT_F = 85.0
WIND_GUST_MPH = 20.0
MUDDER_SCORE = 40
_MEASURE = {"rain": "precip_in", "cold": "temp_f", "heat": "temp_f", "wind": "gust_mph"}


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _masks(rounds: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "rain": _num(rounds["precip_in"]) >= RAIN_IN,
        "cold": _num(rounds["temp_f"]) < COLD_BELOW_F,
        "heat": _num(rounds["temp_f"]) >= HEAT_AT_F,
        "wind": _num(rounds["gust_mph"]) >= WIND_GUST_MPH,
    }


def _first_rounds(rounds: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Each shooter's first qualifying round: earliest date, then highest score, then ordinal."""
    hits = rounds[mask].sort_values(
        ["shooter_id", "event_ts", "score", "ordinal"],
        ascending=[True, True, False, True],
        kind="stable",
    )
    return hits.groupby("shooter_id", sort=True).head(1)


def _weather(code: str) -> Callable[[AchContext], Iterator[Award]]:
    measure = _MEASURE[code]

    def evaluate(ctx: AchContext) -> Iterator[Award]:
        first = _first_rounds(ctx.rounds, _masks(ctx.rounds)[code])
        for sid, ts, rid, value in zip(
            first["shooter_id"], first["event_ts"], first["round_id"], first[measure], strict=True
        ):
            yield Award(int(sid), code, ts.date(), int(rid), {measure: round(float(value), 2)})

    return evaluate


def _all_weather(ctx: AchContext) -> Iterator[Award]:
    masks = _masks(ctx.rounds)
    earned: dict[int, list[date]] = {}
    for code in ("rain", "cold", "heat", "wind"):
        first = _first_rounds(ctx.rounds, masks[code])
        for sid, ts in zip(first["shooter_id"], first["event_ts"], strict=True):
            earned.setdefault(int(sid), []).append(ts.date())
    for sid, days in sorted(earned.items()):
        if len(days) == 4:
            yield Award(sid, "all_weather", max(days), None, {})


def _mudder(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    first = _first_rounds(
        rounds, (rounds["score"] >= MUDDER_SCORE) & (_num(rounds["precip_in"]) >= RAIN_IN)
    )
    for sid, ts, rid, score, precip in zip(
        first["shooter_id"],
        first["event_ts"],
        first["round_id"],
        first["score"],
        first["precip_in"],
        strict=True,
    ):
        yield Award(
            int(sid),
            "mudder",
            ts.date(),
            int(rid),
            {"score": int(score), "precip_in": round(float(precip), 2)},
        )


def _sub_gauge(ctx: AchContext) -> Iterator[Award]:
    rounds = ctx.rounds
    first = _first_rounds(rounds, rounds["gauge_class"].isin(SUB_GAUGES))
    for sid, ts, rid, gauge in zip(
        first["shooter_id"], first["event_ts"], first["round_id"], first["gauge_class"], strict=True
    ):
        yield Award(int(sid), "sub_gauge", ts.date(), int(rid), {"gauge_class": str(gauge)})


register(
    Achievement(
        code="sub_gauge",
        name="Sub-Gauge",
        description="Shot a round with a 20, 28 or .410 gauge.",
        category=Category.CONDITIONS,
        art_key="sub_gauge",
        evaluate=_sub_gauge,
    )
)
register(
    Achievement(
        code="rain",
        name="Rain Shooter",
        description="Shot on a day with 0.02 in or more of rain between 10:00 and 12:00.",
        category=Category.CONDITIONS,
        art_key="rain",
        evaluate=_weather("rain"),
    )
)
register(
    Achievement(
        code="cold",
        name="Cold Shooter",
        description="Shot on a day colder than 35 °F.",
        category=Category.CONDITIONS,
        art_key="cold",
        evaluate=_weather("cold"),
    )
)
register(
    Achievement(
        code="heat",
        name="Heat Shooter",
        description="Shot on a day at 85 °F or hotter.",
        category=Category.CONDITIONS,
        art_key="heat",
        evaluate=_weather("heat"),
    )
)
register(
    Achievement(
        code="wind",
        name="Wind Shooter",
        description="Shot on a day with gusts of 20 mph or more.",
        category=Category.CONDITIONS,
        art_key="wind",
        evaluate=_weather("wind"),
    )
)
register(
    Achievement(
        code="all_weather",
        name="All-Weather",
        description="Earned Rain, Cold, Heat and Wind Shooter.",
        category=Category.CONDITIONS,
        art_key="all_weather",
        evaluate=_all_weather,
    )
)
register(
    Achievement(
        code="mudder",
        name="Mudder",
        description="Broke 40 or more in the rain.",
        category=Category.CONDITIONS,
        art_key="mudder",
        evaluate=_mudder,
    )
)
```

- [ ] **Step 9: Implement the competition trophies**

Create `backend/src/sunday_clays/analytics/achievements/competition.py`:

```python
"""Competition trophies (C12, Plan 10 T3): the only ranking-based trophies. Ranks are full-field
min ranks over best rounds (round_metrics.event_rank, C7), so ties share a rank; ratings are the
pre-event mu_before (mu_after would leak the result); achievements ignore every filter."""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext
from sunday_clays.analytics.achievements.registry import Achievement, Award, Category, register

MIN_FIELD = 5
GIANT_MARGIN = 3.0
_CLASS_ORDER = {"A": 4, "B": 3, "C": 2, "D": 1}


def _best_rounds_in_full_fields(ctx: AchContext) -> pd.DataFrame:
    rounds = ctx.rounds
    field_size = rounds.groupby("event_ts")["shooter_id"].transform("nunique")
    best = rounds["is_best_round"].eq(True)
    return rounds[best & (field_size >= MIN_FIELD)].sort_values(
        ["shooter_id", "event_ts"], kind="stable"
    )


def _first_win(ctx: AchContext) -> Iterator[Award]:
    best = _best_rounds_in_full_fields(ctx)
    wins = best[best["event_rank"] == 1]
    for sid, ts, rid in zip(wins["shooter_id"], wins["event_ts"], wins["round_id"], strict=True):
        yield Award(int(sid), "first_win", ts.date(), int(rid), {})


def _podium(ctx: AchContext) -> Iterator[Award]:
    best = _best_rounds_in_full_fields(ctx)
    podium = best[best["event_rank"] <= 3]
    for sid, ts, rid, rank in zip(
        podium["shooter_id"],
        podium["event_ts"],
        podium["round_id"],
        podium["event_rank"],
        strict=True,
    ):
        yield Award(int(sid), "podium", ts.date(), int(rid), {"rank": int(rank)})


def _giant_killer(ctx: AchContext) -> Iterator[Award]:
    best = _best_rounds_in_full_fields(ctx)
    rated = best[best["mu_before"].notna() & best["event_rank"].notna()]
    for ts in sorted(set(rated["event_ts"])):
        day = rated[rated["event_ts"] == ts]
        top_mu = float(day["mu_before"].max())
        giants = day[day["mu_before"] == top_mu]
        giant_rank = float(giants["event_rank"].min())
        giant_id = int(giants["shooter_id"].min())
        killers = day[
            (day["event_rank"] < giant_rank) & (day["mu_before"] <= top_mu - GIANT_MARGIN)
        ]
        for sid, rid, mu in zip(
            killers["shooter_id"], killers["round_id"], killers["mu_before"], strict=True
        ):
            yield Award(
                int(sid),
                "giant_killer",
                ts.date(),
                int(rid),
                {
                    "giant_shooter_id": giant_id,
                    "giant_mu": round(top_mu, 2),
                    "mu": round(float(mu), 2),
                },
            )


def _class_up(ctx: AchContext) -> Iterator[Award]:
    days = ctx.shooter_days
    if days.empty:
        return
    classes = {
        day: ctx.classes_at(day).set_index("shooter_id")["klass"]
        for day in sorted(set(days["event_date"]))
    }
    for sid, day, prev_ts, rid in zip(
        days["shooter_id"], days["event_date"], days["prev_ts"], days["best_round_id"], strict=True
    ):
        if pd.isna(prev_ts):
            continue
        now = classes[day].get(int(sid))
        before = classes[prev_ts.date()].get(int(sid))
        if (
            isinstance(now, str)
            and isinstance(before, str)
            and _CLASS_ORDER.get(now, 0) > _CLASS_ORDER.get(before, 0)
        ):
            yield Award(int(sid), "class_up", day, int(rid), {"from": before, "to": now})


register(
    Achievement(
        code="first_win",
        name="First Win",
        description="Top score of the day (ties count) with at least 5 shooters.",
        category=Category.COMPETITION,
        art_key="first_win",
        evaluate=_first_win,
    )
)
register(
    Achievement(
        code="podium",
        name="Podium",
        description="Finished in the top 3 (ties count) with at least 5 shooters.",
        category=Category.COMPETITION,
        art_key="podium",
        evaluate=_podium,
    )
)
register(
    Achievement(
        code="giant_killer",
        name="Giant Killer",
        description=(
            "Outshot the day's highest-rated shooter while rated at least 3 below them "
            "(5+ shooters)."
        ),
        category=Category.COMPETITION,
        art_key="giant_killer",
        evaluate=_giant_killer,
        repeatable=True,
    )
)
register(
    Achievement(
        code="class_up",
        name="Class Up",
        description="Moved up a rating class (D → C → B → A) since your previous event.",
        category=Category.COMPETITION,
        art_key="class_up",
        evaluate=_class_up,
        repeatable=True,
    )
)
```

- [ ] **Step 10: Run the unit and golden tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements tests/integration/achievements/test_ach_scoring_golden.py -v`
Expected: PASS. The three new unit files, their no-leak cases and the golden tests are green: sub_gauge has 17 holders with exactly the listed name keys, and first_win/podium match `round_metrics`.

- [ ] **Step 11: Run the full backend suite with lint, types and coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: PASS with coverage ≥90% lines and branches.

- [ ] **Step 12: Commit**

```bash
git add backend/src/sunday_clays/analytics/achievements/scores.py \
  backend/src/sunday_clays/analytics/achievements/conditions.py \
  backend/src/sunday_clays/analytics/achievements/competition.py \
  backend/tests/unit/analytics/achievements/test_ach_scores.py \
  backend/tests/unit/analytics/achievements/test_ach_conditions.py \
  backend/tests/unit/analytics/achievements/test_ach_competition.py \
  backend/tests/integration/achievements/test_ach_scoring_golden.py
git commit -m "feat(achievements): add scoring, conditions and competition trophies" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Station analytics and station routes (master Plan 10 T4a)

**Context:** This task builds the per-station statistics and the three station read endpoints.
- Every station stat reads station-sheet hits (`station_hits` joined to `station_layouts.target_count`), never `rounds.score`.
- One entry is a shooter-round: one sheet row (`event_date`, `entry_row`) at one station.
- Contract:
  - The master T4a bullet: Wilson CI with design effect, separator = centered item-rest Pearson, shrunken per-shooter delta, and wind × station inside `GET /api/stations/{no}`.
  - C7: the `round_type` filter via `frames.apply_round_type_filter` and gust bands via `frames.wind_band`.
  - C8: `GET /api/stations?era=&round_type=`, `GET /api/stations/{no}?round_type=` (incl. `wind: list[StationWindCellOut]`), `GET /api/shooters/{id}/stations?round_type=`.
- Unit tests use synthetic frames. The fixture has only 2 station events, so leaders are empty and every wind cell would be insufficient.
- Coverage stays ≥90% lines and branches, and ruff and mypy stay clean.

**Branch:** `task/10-4a-station-analytics`

**Depends on:**
- Plan 06 T1 (`frames.apply_round_type_filter`, `frames.wind_band`, `api/routes/_filters.round_type_param` and `_filters.today_local`).
- Plan 05 T3 (`event_weather`).
- Plan 03 T5 (`domain.rules.create_rule`, used by one integration test) and T6 (fx fixtures).
- Plan 04 T1 (`fx_viewer_client`).
- No Plan 10 task.

**Files:**
- Create: `backend/src/sunday_clays/analytics/stations.py`
- Create: `backend/src/sunday_clays/api/routes/stations.py`
- Test: `backend/tests/unit/analytics/test_station_analytics.py`
- Test: `backend/tests/integration/stations/test_station_routes.py`

**Interfaces:**
- Consumes (exact):
  - `frames.apply_round_type_filter(df: pd.DataFrame, round_types: Sequence[RoundType]) -> pd.DataFrame` (an empty list means no filter).
  - `frames.wind_band(gust_mph: float) -> str`
  - `api.routes._filters.round_type_param`, used as `round_types: list[RoundType] = round_type_param`.
  - `api.routes._filters.today_local(tz: str) -> date` (Plan 06 T1). Routes call it through the module (`_filters.today_local(settings.timezone)`), so tests can monkeypatch `_filters.today_local`, and "today" matches the `local_date` in the ETag.
  - `frames.wind_band` labels are `<10`, `10-20` and `20+` (Plan 06 T1; `None` for a missing gust).
  - `domain.round_type.RoundType`
  - `config.Settings` and `config.get_settings` (`.timezone`).
  - `db.get_session`
  - `domain.errors.NotFoundError`
  - `domain.rules.create_rule(session, rule_type, payload, note) -> int` and `RuleType.STATION_RESET` (tests only).
- Produces:
  - `analytics/stations.py`:
    - `EraSel = Literal["current", "all"]`
    - `STATION_FRAME_COLUMNS`
    - `add_sheet_totals(frame) -> frame`: adds `sheet_total`.
    - `load_station_frame(session) -> pd.DataFrame`: columns `event_date, station_no, target_count, sheet_id, entry_row, shooter_id (Int64), round_id (Int64), hits, round_type, display_name, sheet_total`.
    - `load_station_resets(session) -> pd.DataFrame[station_no, effective_date, note]`
    - `load_event_weather(session) -> pd.DataFrame[event_date, gust_mph]`
    - `wilson_ci(p, n_eff, z=1.96) -> tuple[float, float]`
    - `design_effect(hits, targets) -> float`
    - `HitStats` and `hit_stats(entries) -> HitStats`
    - `separator(entries) -> float | None`
    - `station_stats(frame) -> pd.DataFrame`: columns `station_no, hits, n_targets, n_rounds, n_events, hit_pct, ci_low, ci_high, deff, clean_rate, separator`.
    - `per_event_station_pct(frame) -> pd.DataFrame[event_date, station_no, hits, n_targets, hit_pct]`. **Task 5 uses this.**
    - `station_leaders(frame, *, limit) -> pd.DataFrame`
    - `shooter_station_matrix(frame) -> pd.DataFrame`
    - `shooter_station_deltas(frame, shooter_id) -> pd.DataFrame[station_no, hits, n, n_rounds, hit_pct, field_pct, delta]`
    - `current_eras(resets, today) -> dict[int, tuple[int, date | None]]`
    - `assign_eras(frame, resets, today) -> frame`: adds `era`, `era_start`, `current_era`.
    - `select_era(frame, era: EraSel) -> frame`
    - `era_stats(frame) -> pd.DataFrame`
    - `station_wind(station_hits, event_weather, era: EraSel) -> pd.DataFrame[station_no, band, band_order, hit_pct, ci_low, ci_high, n_targets, n_events, sufficient]`
    - `StationsOverview` and `stations_overview(frame, resets, *, era, round_types, today, leader_limit=5)`
    - `StationDetail` and `station_detail(frame, resets, weather, *, station_no, round_types, today, leader_limit=10)`
  - `api/routes/stations.py`:
    - `GET /api/stations -> StationsOut{era, n_events, stations: list[StationStatOut], by_event: list[StationEventPctOut], matrix: list[StationShooterCellOut], resets: list[StationResetOut]}`
    - `GET /api/stations/{no} -> StationDetailOut{station_no, eras: list[StationStatOut], by_event, leaders: list[StationLeaderOut], wind: list[StationWindCellOut], resets}`
    - `GET /api/shooters/{id}/stations -> ShooterStationsOut{shooter_id, stations: list[ShooterStationDeltaOut]}`
    - 404 codes `station_not_found` and `shooter_not_found`.
    - `StationStatOut` fields: `station_no, era: int | None, era_start: date | None, hits, n_targets, n_rounds, n_events, hit_pct, ci_low, ci_high, deff, clean_rate, separator (all float | None), leaders`.
    - `StationWindCellOut` fields: `band, band_order, hit_pct, ci_low, ci_high, n_targets, n_events, sufficient`.

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/unit/analytics/test_station_analytics.py`:

```python
"""Station analytics (Plan 10 T4a) on synthetic multi-event frames."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.frames import wind_band
from sunday_clays.analytics.stations import (
    add_sheet_totals,
    current_eras,
    hit_stats,
    shooter_station_deltas,
    station_detail,
    station_leaders,
    station_stats,
    station_wind,
    stations_overview,
    wilson_ci,
)
from sunday_clays.domain.round_type import RoundType

COLUMNS = ["event_date", "entry_row", "station_no", "shooter_id", "hits", "target_count"]
NO_RESETS = pd.DataFrame(columns=["station_no", "effective_date", "note"])
NO_WEATHER = pd.DataFrame(columns=["event_date", "gust_mph"])
D0 = date(2025, 1, 5)


def sun(i: int) -> date:
    return D0 + timedelta(weeks=i)


def frame(rows, *, round_type="unknown"):
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["sheet_id"] = 1
    df["round_id"] = pd.array([pd.NA] * len(df), dtype="Int64")
    df["shooter_id"] = df["shooter_id"].astype("Int64")
    df["round_type"] = round_type
    df["display_name"] = [None if pd.isna(s) else f"Shooter {s}" for s in df["shooter_id"]]
    return add_sheet_totals(df)


def separator_rows(n_per_event):
    rows = []
    for e in range(2):
        for k in range(n_per_event):
            skill = k + e
            for station_no, offset in ((4, 0), (5, 1), (6, 2)):
                hits = min(7, (skill + offset) // 2 + (1 if k % 3 == 0 else 0))
                rows.append((sun(e), k, station_no, 100 * e + k, hits, 7))
    return rows


def test_wilson_ci_matches_textbook_values():
    assert wilson_ci(0.5, 100) == pytest.approx((0.40383, 0.59617), abs=1e-5)
    assert wilson_ci(0.0, 10) == pytest.approx((0.0, 0.27754), abs=1e-5)
    assert wilson_ci(0.5, 0) == (0.0, 1.0)


def test_homogeneous_entries_have_design_effect_one():
    [stats] = station_stats(frame([(D0, r, 4, r, 5, 7) for r in range(10)])).to_dict("records")
    assert stats["deff"] == 1.0
    assert (stats["hits"], stats["n_targets"], stats["n_rounds"], stats["n_events"]) == (
        50,
        70,
        10,
        1,
    )
    assert (stats["ci_low"], stats["ci_high"]) == pytest.approx((0.599496, 0.806779), abs=1e-5)


def test_heterogeneous_entries_widen_the_interval():
    [stats] = station_stats(
        frame([(D0, r, 4, r, 7 if r < 5 else 0, 7) for r in range(10)])
    ).to_dict("records")
    assert stats["deff"] == pytest.approx(7.777778, abs=1e-5)
    assert (stats["ci_low"], stats["ci_high"]) == pytest.approx((0.226526, 0.773474), abs=1e-5)


def test_eight_events_switch_to_event_clusters():
    def rows(n_events):
        out = []
        for e in range(n_events):
            out += [(sun(e), 2 * e, 4, 2 * e, 7, 7), (sun(e), 2 * e + 1, 4, 2 * e + 1, 0, 7)]
        return out

    assert station_stats(frame(rows(7)))["deff"].iloc[0] == pytest.approx(7.538462, abs=1e-5)
    assert station_stats(frame(rows(8)))["deff"].iloc[0] == 1.0


def test_perfect_station_ci_stays_in_unit_interval():
    [stats] = station_stats(frame([(D0, r, 4, r, 7, 7) for r in range(10)])).to_dict("records")
    assert (stats["hit_pct"], stats["deff"], stats["clean_rate"]) == (1.0, 1.0, 1.0)
    assert stats["ci_high"] == pytest.approx(1.0)
    assert stats["ci_low"] == pytest.approx(0.947975, abs=1e-5)


def test_empty_selection_returns_no_stations():
    empty = frame([])
    assert station_stats(empty).empty
    stats = hit_stats(empty)
    assert (stats.hit_pct, stats.ci_low, stats.deff, stats.n_targets) == (None, None, None, 0)


def test_separator_is_item_rest_not_part_whole():
    df = frame(separator_rows(16))
    s4 = df[df["station_no"] == 4]
    total = df.groupby(["event_date", "entry_row"])["hits"].transform("sum")[s4.index]

    def centered(values):
        return values - values.groupby(s4["event_date"]).transform("mean")

    share = s4["hits"] / 7
    item_rest = np.corrcoef(centered(share), centered(total - s4["hits"]))[0, 1]
    part_whole = np.corrcoef(centered(share), centered(total))[0, 1]
    separator = station_stats(df).set_index("station_no").loc[4, "separator"]
    assert separator == pytest.approx(item_rest)
    assert separator < part_whole


def test_separator_needs_thirty_shooter_rounds():
    # 28 entries per station
    assert station_stats(frame(separator_rows(14)))["separator"].isna().all()


def test_one_round_delta_is_shrunk_toward_zero():
    df = frame([(D0, 1, 4, 1, 7, 7), (D0, 2, 4, 2, 0, 7), (sun(1), 1, 4, 2, 7, 7)])
    [row] = shooter_station_deltas(df, 1).to_dict("records")
    assert (
        row["station_no"],
        row["hits"],
        row["n"],
        row["n_rounds"],
        row["hit_pct"],
        row["field_pct"],
    ) == (
        4,
        7,
        7,
        1,
        1.0,
        0.5,
    )
    # (7 + 14·0.5)/(7 + 14) - 0.5; the raw delta would be 0.5
    assert row["delta"] == pytest.approx(1 / 6)


def test_leaders_need_three_appearances():
    rows = []
    for e in range(3):
        rows += [(sun(e), 1, 4, 1, 7 if e < 2 else 6, 7), (sun(e), 3, 4, 3, 5, 7)]
    rows += [(sun(e), 2, 4, 2, 7, 7) for e in range(2)]
    rows += [(sun(e), 9, 4, None, 7, 7) for e in range(3)]  # unmatched name never leads
    leaders = station_leaders(frame(rows), limit=5)
    assert list(zip(leaders["shooter_id"], leaders["hits"], leaders["n_rounds"], strict=True)) == [
        (1, 20, 3),
        (3, 15, 3),
    ]


def test_station_wind_bands_flag_insufficient_cells():
    rows = [(sun(e), 1, 4, 1, 5, 7) for e in range(8)]
    weather = pd.DataFrame(
        {"event_date": [sun(e) for e in range(7)], "gust_mph": [5.0] * 5 + [25.0] * 2}
    )
    cells = station_wind(frame(rows), weather, "all")
    assert list(cells["band"]) == [wind_band(5.0), wind_band(25.0)]
    assert list(cells["n_events"]) == [5, 2]
    assert list(cells["n_targets"]) == [35, 14]
    assert list(cells["sufficient"]) == [True, False]
    assert list(cells["hit_pct"]) == pytest.approx([5 / 7, 5 / 7])


def test_station_wind_without_weather_is_empty():
    assert station_wind(frame([(D0, 1, 4, 1, 5, 7)]), NO_WEATHER, "all").empty


def test_round_type_filter_restricts_rounds():
    df = pd.concat(
        [
            frame([(sun(0), 1, 4, 1, 7, 7), (sun(0), 2, 4, None, 3, 7)], round_type="sporting"),
            frame([(sun(1), 1, 4, 1, 3, 7)], round_type="super_sporting"),
        ],
        ignore_index=True,
    )
    sporting = stations_overview(
        df, NO_RESETS, era="all", round_types=[RoundType.SPORTING], today=sun(5)
    )
    assert sporting.n_events == 1
    assert list(sporting.stats["hits"]) == [10]
    assert list(sporting.by_event["hit_pct"]) == pytest.approx([10 / 14])
    assert list(sporting.matrix["shooter_id"]) == [1]  # the unmatched entry is not a matrix row
    everything = stations_overview(df, NO_RESETS, era="all", round_types=[], today=sun(5))
    assert everything.n_events == 2


ERA_ROWS = [
    (date(2025, 2, 2), 1, 4, 1, 3, 7),
    (date(2025, 3, 2), 1, 4, 1, 6, 7),
    (date(2025, 2, 2), 1, 5, 1, 4, 7),
    (date(2025, 3, 2), 1, 5, 1, 5, 7),
]
ERA_RESETS = pd.DataFrame(
    {
        "station_no": [4, 4],
        "effective_date": [date(2025, 3, 1), date(2025, 7, 1)],
        "note": ["new trap", "future"],
    }
)


def test_current_era_starts_at_latest_past_reset():
    today = date(2025, 6, 1)
    assert current_eras(ERA_RESETS, today) == {4: (1, date(2025, 3, 1))}
    current = stations_overview(
        frame(ERA_ROWS), ERA_RESETS, era="current", round_types=[], today=today
    )
    by_station = current.stats.set_index("station_no")
    assert by_station.loc[4, "hits"] == 6  # only the post-reset event
    assert by_station.loc[5, "hits"] == 9  # no resets logged: every event
    everything = stations_overview(
        frame(ERA_ROWS), ERA_RESETS, era="all", round_types=[], today=today
    )
    assert everything.stats.set_index("station_no").loc[4, "hits"] == 9


def test_station_detail_splits_eras():
    detail = station_detail(
        frame(ERA_ROWS),
        ERA_RESETS,
        NO_WEATHER,
        station_no=4,
        round_types=[],
        today=date(2025, 6, 1),
    )
    assert list(
        zip(detail.eras["era"], detail.eras["era_start"], detail.eras["hits"], strict=True)
    ) == [
        (0, None, 3),
        (1, date(2025, 3, 1), 6),
    ]
    assert list(detail.by_event["hits"]) == [3, 6]
    assert detail.wind.empty
    assert detail.leaders.empty
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/test_station_analytics.py -v`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.analytics.stations'`.

- [ ] **Step 3: Implement the station analytics**

Create `backend/src/sunday_clays/analytics/stations.py`:

```python
"""Station analytics (Plan 10 T4a).

Every statistic reads station-sheet hits (station_hits), never rounds.score. One entry is a
shooter-round: one sheet row (event_date, entry_row) at one station, with its own target_count.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Literal

import numpy as np
import numpy.typing as npt
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.frames import apply_round_type_filter, wind_band
from sunday_clays.domain.round_type import RoundType

EraSel = Literal["current", "all"]

Z95 = 1.96
EVENT_CLUSTER_MIN_EVENTS = 8
SEPARATOR_MIN_ROUNDS = 30
LEADER_MIN_APPEARANCES = 3
WIND_MIN_EVENTS = 5

STATION_FRAME_COLUMNS: tuple[str, ...] = (
    "event_date",
    "station_no",
    "target_count",
    "sheet_id",
    "entry_row",
    "shooter_id",
    "round_id",
    "hits",
    "round_type",
    "display_name",
)
STAT_COLUMNS: tuple[str, ...] = (
    "station_no",
    "hits",
    "n_targets",
    "n_rounds",
    "n_events",
    "hit_pct",
    "ci_low",
    "ci_high",
    "deff",
    "clean_rate",
    "separator",
)
WIND_COLUMNS: tuple[str, ...] = (
    "station_no",
    "band",
    "band_order",
    "hit_pct",
    "ci_low",
    "ci_high",
    "n_targets",
    "n_events",
    "sufficient",
)

_FRAME_SQL = text(
    """
    SELECT h.event_date, h.station_no, l.target_count, h.sheet_id, h.entry_row,
           h.shooter_id, h.round_id, h.hits, e.round_type, p.display_name
    FROM station_hits h
    JOIN station_layouts l ON l.event_date = h.event_date AND l.station_no = h.station_no
    JOIN events e ON e.event_date = h.event_date
    LEFT JOIN shooter_profiles p ON p.shooter_id = h.shooter_id
    ORDER BY h.event_date, h.entry_row, h.station_no
    """
)
_RESETS_SQL = text(
    "SELECT payload FROM rules WHERE rule_type = 'station_reset' AND active ORDER BY id"
)
_WEATHER_SQL = text("SELECT event_date, gust_mph FROM event_weather ORDER BY event_date")


# ---- loaders ----------------------------------------------------------------------------------


def add_sheet_totals(frame: pd.DataFrame) -> pd.DataFrame:
    """`sheet_total` = the entry's recomputed station-sheet total, taken before any filtering."""
    return frame.assign(
        sheet_total=frame.groupby(["event_date", "entry_row"])["hits"].transform("sum")
    )


def load_station_frame(session: Session) -> pd.DataFrame:
    rows = [dict(r) for r in session.execute(_FRAME_SQL).mappings()]
    frame = pd.DataFrame(rows, columns=list(STATION_FRAME_COLUMNS))
    for column in ("shooter_id", "round_id"):
        frame[column] = frame[column].astype("Int64")
    return add_sheet_totals(frame)


def load_station_resets(session: Session) -> pd.DataFrame:
    """Active station_reset rules (C5 payload {station_no, effective_date, note})."""
    rows = [
        {
            "station_no": int(payload["station_no"]),
            "effective_date": date.fromisoformat(str(payload["effective_date"])),
            "note": payload.get("note"),
        }
        for (payload,) in session.execute(_RESETS_SQL).all()
    ]
    return pd.DataFrame(rows, columns=["station_no", "effective_date", "note"])


def load_event_weather(session: Session) -> pd.DataFrame:
    rows = [dict(r) for r in session.execute(_WEATHER_SQL).mappings()]
    return pd.DataFrame(rows, columns=["event_date", "gust_mph"])


# ---- hit % with a clustered Wilson interval --------------------------------------------------


def wilson_ci(p: float, n_eff: float, z: float = Z95) -> tuple[float, float]:
    if n_eff <= 0:
        return (0.0, 1.0)
    z2 = z * z
    denom = 1.0 + z2 / n_eff
    center = (p + z2 / (2.0 * n_eff)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n_eff + z2 / (4.0 * n_eff * n_eff)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def design_effect(hits: npt.NDArray[np.float64], targets: npt.NDArray[np.float64]) -> float:
    """deff = max(1, V_cluster / V_binomial) with V_cluster = k/(k-1)·Σ(h_i - p·m_i)²/(Σm_i)²."""
    total = float(targets.sum())
    k = len(hits)
    if k < 2 or total <= 0.0:
        return 1.0
    p = float(hits.sum()) / total
    v_binomial = p * (1.0 - p) / total
    if v_binomial <= 0.0:
        return 1.0
    v_cluster = k / (k - 1) * float(((hits - p * targets) ** 2).sum()) / total**2
    return max(1.0, v_cluster / v_binomial)


@dataclass(frozen=True)
class HitStats:
    hits: int
    n_targets: int
    n_rounds: int
    n_events: int
    hit_pct: float | None
    ci_low: float | None
    ci_high: float | None
    deff: float | None


def hit_stats(entries: pd.DataFrame) -> HitStats:
    """p = Σhits/Σtargets; 95% Wilson CI on n_eff = Σtargets/deff. Clusters are shooter-rounds, or
    events once the selection spans >= 8 events."""
    n_targets = int(entries["target_count"].sum())
    n_events = int(entries["event_date"].nunique())
    hits = int(entries["hits"].sum())
    if n_targets == 0:
        return HitStats(hits, 0, len(entries), n_events, None, None, None, None)
    if n_events >= EVENT_CLUSTER_MIN_EVENTS:
        clusters = entries.groupby("event_date")[["hits", "target_count"]].sum()
    else:
        clusters = entries[["hits", "target_count"]]
    deff = design_effect(
        clusters["hits"].to_numpy(dtype=np.float64),
        clusters["target_count"].to_numpy(dtype=np.float64),
    )
    p = hits / n_targets
    low, high = wilson_ci(p, n_targets / deff)
    return HitStats(hits, n_targets, len(entries), n_events, p, low, high, deff)


def separator(entries: pd.DataFrame) -> float | None:
    """Pearson corr of hits/target vs (sheet total - hits), both centered within each event."""
    if len(entries) < SEPARATOR_MIN_ROUNDS:
        return None
    share = entries["hits"] / entries["target_count"]
    rest = entries["sheet_total"] - entries["hits"]
    x = share - share.groupby(entries["event_date"]).transform("mean")
    y = rest - rest.groupby(entries["event_date"]).transform("mean")
    denom = math.sqrt(float((x * x).sum()) * float((y * y).sum()))
    if denom == 0.0:
        return None
    return float((x * y).sum()) / denom


def _stat_row(station_no: int, entries: pd.DataFrame) -> dict[str, Any]:
    clean = float((entries["hits"] == entries["target_count"]).mean()) if len(entries) else None
    return {
        "station_no": station_no,
        **asdict(hit_stats(entries)),
        "clean_rate": clean,
        "separator": separator(entries),
    }


def station_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _stat_row(int(no), frame[frame["station_no"] == no])
        for no in sorted(frame["station_no"].unique())
    ]
    return pd.DataFrame(rows, columns=list(STAT_COLUMNS))


def per_event_station_pct(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        frame.groupby(["event_date", "station_no"], sort=True)[["hits", "target_count"]]
        .sum()
        .reset_index()
        .rename(columns={"target_count": "n_targets"})
    )
    grouped["hit_pct"] = grouped["hits"] / grouped["n_targets"]
    return grouped[["event_date", "station_no", "hits", "n_targets", "hit_pct"]]


# ---- shooters at stations ---------------------------------------------------------------------


def _linked(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["shooter_id"].notna()]


def station_leaders(frame: pd.DataFrame, *, limit: int) -> pd.DataFrame:
    columns = [
        "station_no",
        "shooter_id",
        "display_name",
        "hits",
        "n_targets",
        "n_rounds",
        "hit_pct",
    ]
    linked = _linked(frame)
    if linked.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        linked.groupby(["station_no", "shooter_id"], sort=True)
        .agg(
            display_name=("display_name", "first"),
            hits=("hits", "sum"),
            n_targets=("target_count", "sum"),
            n_rounds=("hits", "size"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["n_rounds"] >= LEADER_MIN_APPEARANCES].copy()
    grouped["hit_pct"] = grouped["hits"] / grouped["n_targets"]
    grouped = grouped.sort_values(
        ["station_no", "hit_pct", "n_targets", "shooter_id"],
        ascending=[True, False, False, True],
        kind="stable",
    )
    return grouped.groupby("station_no", sort=True).head(limit).reset_index(drop=True)[columns]


def shooter_station_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["shooter_id", "display_name", "station_no", "hits", "n_targets", "hit_pct"]
    linked = _linked(frame)
    if linked.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        linked.groupby(["shooter_id", "station_no"], sort=True)
        .agg(
            display_name=("display_name", "first"),
            hits=("hits", "sum"),
            n_targets=("target_count", "sum"),
        )
        .reset_index()
    )
    grouped["hit_pct"] = grouped["hits"] / grouped["n_targets"]
    return grouped[columns]


def shooter_station_deltas(frame: pd.DataFrame, shooter_id: int) -> pd.DataFrame:
    """Shrunken delta (h + κ·p_f)/(n + κ) - p_f; p_f = field hit % at s on the days the shooter
    shot s (the shooter included); κ = 2 x median target_count of those field entries."""
    columns = ["station_no", "hits", "n", "n_rounds", "hit_pct", "field_pct", "delta"]
    mine = frame[frame["shooter_id"].eq(shooter_id).fillna(False).astype(bool)]
    rows: list[dict[str, Any]] = []
    for no in sorted(mine["station_no"].unique()):
        own = mine[mine["station_no"] == no]
        field = frame[
            (frame["station_no"] == no) & frame["event_date"].isin(set(own["event_date"]))
        ]
        field_pct = float(field["hits"].sum()) / float(field["target_count"].sum())
        kappa = 2.0 * float(field["target_count"].median())
        hits = int(own["hits"].sum())
        n = int(own["target_count"].sum())
        rows.append(
            {
                "station_no": int(no),
                "hits": hits,
                "n": n,
                "n_rounds": len(own),
                "hit_pct": hits / n,
                "field_pct": field_pct,
                "delta": (hits + kappa * field_pct) / (n + kappa) - field_pct,
            }
        )
    return pd.DataFrame(rows, columns=columns)


# ---- eras -------------------------------------------------------------------------------------


def _reset_dates(resets: pd.DataFrame) -> dict[int, list[date]]:
    out: dict[int, list[date]] = {}
    for no, day in zip(resets["station_no"], resets["effective_date"], strict=True):
        out.setdefault(int(no), []).append(day)
    return {no: sorted(days) for no, days in out.items()}


def current_eras(resets: pd.DataFrame, today: date) -> dict[int, tuple[int, date | None]]:
    """station_no → (current era index, its start) for stations with at least one logged reset."""
    out: dict[int, tuple[int, date | None]] = {}
    for no, days in _reset_dates(resets).items():
        past = [day for day in days if day <= today]
        out[no] = (len(past), past[-1] if past else None)
    return out


def assign_eras(frame: pd.DataFrame, resets: pd.DataFrame, today: date) -> pd.DataFrame:
    by_station = _reset_dates(resets)
    current = current_eras(resets, today)
    eras: list[int] = []
    starts: list[date | None] = []
    currents: list[int] = []
    for no, day in zip(frame["station_no"], frame["event_date"], strict=True):
        past = [reset for reset in by_station.get(int(no), []) if reset <= day]
        eras.append(len(past))
        starts.append(past[-1] if past else None)
        currents.append(current.get(int(no), (0, None))[0])
    return frame.assign(
        era=eras,
        era_start=pd.Series(starts, index=frame.index, dtype=object),
        current_era=currents,
    )


def select_era(frame: pd.DataFrame, era: EraSel) -> pd.DataFrame:
    """`all` keeps every row; `current` keeps each station's current era.

    `current` needs the assign_eras columns."""
    if era == "all":
        return frame
    return frame[frame["era"] == frame["current_era"]]


def era_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for no in sorted(frame["station_no"].unique()):
        station = frame[frame["station_no"] == no]
        for era in sorted(station["era"].unique()):
            entries = station[station["era"] == era]
            rows.append(
                {
                    "era": int(era),
                    "era_start": entries["era_start"].iloc[0],
                    **_stat_row(int(no), entries),
                }
            )
    return pd.DataFrame(rows, columns=["era", "era_start", *STAT_COLUMNS])


# ---- wind x station ---------------------------------------------------------------------------


def station_wind(
    station_hits: pd.DataFrame, event_weather: pd.DataFrame, era: EraSel
) -> pd.DataFrame:
    """Hit % per station x C7 gust band (frames.wind_band); events without weather are excluded;
    `sufficient` = n_events >= 5."""
    frame = select_era(station_hits, era)
    gusts = {
        day: float(gust)
        for day, gust in zip(event_weather["event_date"], event_weather["gust_mph"], strict=True)
        if pd.notna(gust)
    }
    frame = frame[frame["event_date"].isin(set(gusts))]
    rows: list[dict[str, Any]] = []
    for no in sorted(frame["station_no"].unique()):
        station = frame[frame["station_no"] == no]
        bands = pd.Series(
            [wind_band(gusts[day]) for day in station["event_date"]], index=station.index
        )
        for band in bands.unique():
            entries = station[bands == band]
            stats = hit_stats(entries)
            rows.append(
                {
                    "station_no": int(no),
                    "band": str(band),
                    "band_order": min(gusts[day] for day in entries["event_date"]),
                    "hit_pct": stats.hit_pct,
                    "ci_low": stats.ci_low,
                    "ci_high": stats.ci_high,
                    "n_targets": stats.n_targets,
                    "n_events": stats.n_events,
                    "sufficient": stats.n_events >= WIND_MIN_EVENTS,
                }
            )
    out = pd.DataFrame(rows, columns=list(WIND_COLUMNS))
    return out.sort_values(["station_no", "band_order"], kind="stable").reset_index(drop=True)


# ---- compositions used by the routes ----------------------------------------------------------


@dataclass(frozen=True)
class StationsOverview:
    stats: pd.DataFrame
    by_event: pd.DataFrame
    matrix: pd.DataFrame
    leaders: pd.DataFrame
    n_events: int


def stations_overview(
    frame: pd.DataFrame,
    resets: pd.DataFrame,
    *,
    era: EraSel,
    round_types: Sequence[RoundType],
    today: date,
    leader_limit: int = 5,
) -> StationsOverview:
    selected = select_era(
        assign_eras(apply_round_type_filter(frame, round_types), resets, today), era
    )
    return StationsOverview(
        stats=station_stats(selected),
        by_event=per_event_station_pct(selected),
        matrix=shooter_station_matrix(selected),
        leaders=station_leaders(selected, limit=leader_limit),
        n_events=int(selected["event_date"].nunique()),
    )


@dataclass(frozen=True)
class StationDetail:
    eras: pd.DataFrame
    by_event: pd.DataFrame
    leaders: pd.DataFrame
    wind: pd.DataFrame


def station_detail(
    frame: pd.DataFrame,
    resets: pd.DataFrame,
    weather: pd.DataFrame,
    *,
    station_no: int,
    round_types: Sequence[RoundType],
    today: date,
    leader_limit: int = 10,
) -> StationDetail:
    with_eras = assign_eras(apply_round_type_filter(frame, round_types), resets, today)
    mine = with_eras[with_eras["station_no"] == station_no]
    return StationDetail(
        eras=era_stats(mine),
        by_event=per_event_station_pct(mine),
        leaders=station_leaders(mine, limit=leader_limit),
        wind=station_wind(mine, weather, "all"),
    )
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/test_station_analytics.py -v`
Expected: PASS (all tests green, including the textbook Wilson values and `separator < part_whole`).

- [ ] **Step 5: Write the failing route tests**

Create `backend/tests/integration/stations/test_station_routes.py`:

```python
"""Station endpoints over the committed fixtures (Plan 10 T4a).

Literal expectations were computed independently from
backend/tests/fixtures/stations_2026-09-27.xlsx with openpyxl (2 sheets, 37 entries, stations 4-10
with targets 7,7,7,7,7,7,8)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from sunday_clays.domain.rules import RuleType, create_rule


def scalar(session: Any, sql: str, **params: Any) -> Any:
    return session.execute(text(sql), params).scalar_one()


def test_station_overview_on_fixture(fx_viewer_client, fx_session):
    body = fx_viewer_client.get("/api/stations").json()
    assert (body["era"], body["n_events"], body["resets"]) == ("current", 2, [])
    stations = {s["station_no"]: s for s in body["stations"]}
    assert sorted(stations) == [4, 5, 6, 7, 8, 9, 10]
    nine = stations[9]
    assert (
        nine["hits"],
        nine["n_targets"],
        nine["n_rounds"],
        nine["n_events"],
        nine["clean_rate"],
    ) == (
        130,
        259,
        37,
        2,
        0.0,
    )
    assert (nine["era"], nine["era_start"], nine["leaders"]) == (0, None, [])
    assert nine["hit_pct"] == pytest.approx(130 / 259)
    assert (nine["ci_low"], nine["ci_high"]) == pytest.approx((0.432572, 0.571215), abs=1e-5)
    assert nine["deff"] == pytest.approx(1.321341, abs=1e-5)
    assert nine["separator"] == pytest.approx(0.615142, abs=1e-5)
    assert stations[10]["clean_rate"] == pytest.approx(4 / 37)
    assert stations[7]["deff"] == 1.0
    assert len(body["by_event"]) == 14
    linked = scalar(
        fx_session,
        "SELECT count(DISTINCT shooter_id) FROM station_hits WHERE shooter_id IS NOT NULL",
    )
    assert len(body["matrix"]) == 7 * linked


def test_stations_route_round_type_filter(fx_viewer_client):
    none = fx_viewer_client.get("/api/stations", params={"round_type": "sporting"}).json()
    assert (none["stations"], none["n_events"]) == ([], 0)
    both = fx_viewer_client.get(
        "/api/stations", params={"round_type": "super_sporting", "era": "all"}
    ).json()
    assert (both["era"], both["n_events"], both["stations"][0]["era"]) == ("all", 2, None)


def test_station_reset_splits_eras_on_fixture(fx_viewer_client, fx_session):
    create_rule(
        fx_session,
        RuleType.STATION_RESET,
        {"station_no": 9, "effective_date": "2026-09-10", "note": "new presentation"},
        None,
    )
    current = {s["station_no"]: s for s in fx_viewer_client.get("/api/stations").json()["stations"]}
    assert (
        current[9]["era"],
        current[9]["era_start"],
        current[9]["hits"],
        current[9]["n_targets"],
    ) == (
        1,
        "2026-09-10",
        44,
        91,
    )
    assert current[4]["n_targets"] == 259  # other stations keep every event
    detail = fx_viewer_client.get("/api/stations/9").json()
    assert [(e["era"], e["era_start"], e["hits"], e["n_targets"]) for e in detail["eras"]] == [
        (0, None, 86, 168),
        (1, "2026-09-10", 44, 91),
    ]
    assert detail["resets"] == [
        {"station_no": 9, "effective_date": "2026-09-10", "note": "new presentation"}
    ]


def test_station_detail_on_fixture(fx_viewer_client):
    body = fx_viewer_client.get("/api/stations/9").json()
    [era] = body["eras"]
    assert (era["era"], era["hits"], era["n_targets"]) == (0, 130, 259)
    assert [e["event_date"] for e in body["by_event"]] == ["2026-09-06", "2026-09-13"]
    assert body["wind"] == []  # the fx world has no event_weather rows
    assert body["leaders"] == []  # nobody has 3 appearances in 2 events


def test_unknown_station_is_404(fx_viewer_client):
    response = fx_viewer_client.get("/api/stations/99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "station_not_found"


def test_shooter_station_deltas_on_fixture(fx_viewer_client, fx_session):
    shooter_id = scalar(
        fx_session, "SELECT shooter_id FROM shooter_aliases WHERE name_key = 'hadley ike'"
    )
    body = fx_viewer_client.get(f"/api/shooters/{shooter_id}/stations").json()
    rows = {s["station_no"]: s for s in body["stations"]}
    assert sorted(rows) == [4, 5, 6, 7, 8, 9, 10]
    assert all(r["n_rounds"] == 2 for r in rows.values())
    assert rows[9]["n"] == 14
    assert rows[9]["field_pct"] == pytest.approx(130 / 259)


def test_shooter_stations_unknown_shooter_is_404(fx_viewer_client):
    response = fx_viewer_client.get("/api/shooters/999999/stations")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"
```

- [ ] **Step 6: Run the route tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/stations/test_station_routes.py -v`
Expected: FAIL. `/api/stations` returns 404 because no router exists yet, so the tests fail on `KeyError: 'era'` and on status assertions.

- [ ] **Step 7: Implement the station routes**

Create `backend/src/sunday_clays/api/routes/stations.py`:

```python
"""Station read endpoints (C8, Plan 10 T4a): overview with era and round-type filters, one station
(incl. wind x station), and a shooter's per-station deltas. All stats use station-sheet hits."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from datetime import date
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import stations as st
from sunday_clays.analytics.frames import apply_round_type_filter
from sunday_clays.api.routes import _filters
from sunday_clays.api.routes._filters import round_type_param
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter(prefix="/api", tags=["stations"])

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class StationLeaderOut(BaseModel):
    shooter_id: int
    display_name: str
    hits: int
    n_targets: int
    n_rounds: int
    hit_pct: float


class StationStatOut(BaseModel):
    station_no: int
    era: int | None
    era_start: date | None
    hits: int
    n_targets: int
    n_rounds: int
    n_events: int
    hit_pct: float | None
    ci_low: float | None
    ci_high: float | None
    deff: float | None
    clean_rate: float | None
    separator: float | None
    leaders: list[StationLeaderOut]


class StationEventPctOut(BaseModel):
    event_date: date
    station_no: int
    hits: int
    n_targets: int
    hit_pct: float


class StationShooterCellOut(BaseModel):
    shooter_id: int
    display_name: str
    station_no: int
    hits: int
    n_targets: int
    hit_pct: float


class StationResetOut(BaseModel):
    station_no: int
    effective_date: date
    note: str | None


class StationsOut(BaseModel):
    era: Literal["current", "all"]
    n_events: int
    stations: list[StationStatOut]
    by_event: list[StationEventPctOut]
    matrix: list[StationShooterCellOut]
    resets: list[StationResetOut]


class StationWindCellOut(BaseModel):
    band: str
    band_order: float
    hit_pct: float
    ci_low: float
    ci_high: float
    n_targets: int
    n_events: int
    sufficient: bool


class StationDetailOut(BaseModel):
    station_no: int
    eras: list[StationStatOut]
    by_event: list[StationEventPctOut]
    leaders: list[StationLeaderOut]
    wind: list[StationWindCellOut]
    resets: list[StationResetOut]


class ShooterStationDeltaOut(BaseModel):
    station_no: int
    hits: int
    n: int
    n_rounds: int
    hit_pct: float
    field_pct: float
    delta: float


class ShooterStationsOut(BaseModel):
    shooter_id: int
    stations: list[ShooterStationDeltaOut]


def _today(settings: Settings) -> date:
    """Today in the club timezone, through Plan 06's shared helper (tests monkeypatch it)."""
    return _filters.today_local(settings.timezone)


def _records(frame: pd.DataFrame) -> list[dict[Hashable, Any]]:
    return frame.to_dict("records")


def _opt(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def _leaders(frame: pd.DataFrame) -> dict[int, list[StationLeaderOut]]:
    out: dict[int, list[StationLeaderOut]] = {}
    for r in _records(frame):
        out.setdefault(int(r["station_no"]), []).append(
            StationLeaderOut(
                shooter_id=int(r["shooter_id"]),
                display_name=str(r["display_name"]),
                hits=int(r["hits"]),
                n_targets=int(r["n_targets"]),
                n_rounds=int(r["n_rounds"]),
                hit_pct=float(r["hit_pct"]),
            )
        )
    return out


def _stat_out(
    r: Mapping[Hashable, Any],
    *,
    era: int | None,
    era_start: date | None,
    leaders: list[StationLeaderOut],
) -> StationStatOut:
    return StationStatOut(
        station_no=int(r["station_no"]),
        era=era,
        era_start=era_start,
        hits=int(r["hits"]),
        n_targets=int(r["n_targets"]),
        n_rounds=int(r["n_rounds"]),
        n_events=int(r["n_events"]),
        hit_pct=_opt(r["hit_pct"]),
        ci_low=_opt(r["ci_low"]),
        ci_high=_opt(r["ci_high"]),
        deff=_opt(r["deff"]),
        clean_rate=_opt(r["clean_rate"]),
        separator=_opt(r["separator"]),
        leaders=leaders,
    )


def _events_out(frame: pd.DataFrame) -> list[StationEventPctOut]:
    return [
        StationEventPctOut(
            event_date=r["event_date"],
            station_no=int(r["station_no"]),
            hits=int(r["hits"]),
            n_targets=int(r["n_targets"]),
            hit_pct=float(r["hit_pct"]),
        )
        for r in _records(frame)
    ]


def _resets_out(resets: pd.DataFrame, station_no: int | None = None) -> list[StationResetOut]:
    return [
        StationResetOut(
            station_no=int(r["station_no"]), effective_date=r["effective_date"], note=r["note"]
        )
        for r in _records(resets)
        if station_no is None or int(r["station_no"]) == station_no
    ]


@router.get("/stations", response_model=StationsOut)
def get_stations(
    session: SessionDep,
    settings: SettingsDep,
    era: Literal["current", "all"] = "current",
    round_types: list[RoundType] = round_type_param,
) -> StationsOut:
    today = _today(settings)
    resets = st.load_station_resets(session)
    overview = st.stations_overview(
        st.load_station_frame(session), resets, era=era, round_types=round_types, today=today
    )
    current = st.current_eras(resets, today)
    leaders = _leaders(overview.leaders)
    stations: list[StationStatOut] = []
    for r in _records(overview.stats):
        no = int(r["station_no"])
        era_index: int | None = None
        era_start: date | None = None
        if era == "current":
            era_index, era_start = current.get(no, (0, None))
        stations.append(
            _stat_out(r, era=era_index, era_start=era_start, leaders=leaders.get(no, []))
        )
    matrix = [
        StationShooterCellOut(
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            station_no=int(r["station_no"]),
            hits=int(r["hits"]),
            n_targets=int(r["n_targets"]),
            hit_pct=float(r["hit_pct"]),
        )
        for r in _records(overview.matrix)
    ]
    return StationsOut(
        era=era,
        n_events=overview.n_events,
        stations=stations,
        by_event=_events_out(overview.by_event),
        matrix=matrix,
        resets=_resets_out(resets),
    )


@router.get("/stations/{no}", response_model=StationDetailOut)
def get_station(
    station_no: Annotated[int, Path(alias="no")],
    session: SessionDep,
    settings: SettingsDep,
    round_types: list[RoundType] = round_type_param,
) -> StationDetailOut:
    frame = st.load_station_frame(session)
    if not bool((frame["station_no"] == station_no).any()):
        raise NotFoundError("station_not_found", f"No station {station_no}")
    resets = st.load_station_resets(session)
    detail = st.station_detail(
        frame,
        resets,
        st.load_event_weather(session),
        station_no=station_no,
        round_types=round_types,
        today=_today(settings),
    )
    eras = [
        _stat_out(
            r,
            era=int(r["era"]),
            era_start=r["era_start"] if isinstance(r["era_start"], date) else None,
            leaders=[],
        )
        for r in _records(detail.eras)
    ]
    wind = [
        StationWindCellOut(
            band=str(r["band"]),
            band_order=float(r["band_order"]),
            hit_pct=float(r["hit_pct"]),
            ci_low=float(r["ci_low"]),
            ci_high=float(r["ci_high"]),
            n_targets=int(r["n_targets"]),
            n_events=int(r["n_events"]),
            sufficient=bool(r["sufficient"]),
        )
        for r in _records(detail.wind)
    ]
    return StationDetailOut(
        station_no=station_no,
        eras=eras,
        by_event=_events_out(detail.by_event),
        leaders=_leaders(detail.leaders).get(station_no, []),
        wind=wind,
        resets=_resets_out(resets, station_no),
    )


@router.get("/shooters/{id}/stations", response_model=ShooterStationsOut)
def get_shooter_stations(
    shooter_id: Annotated[int, Path(alias="id")],
    session: SessionDep,
    round_types: list[RoundType] = round_type_param,
) -> ShooterStationsOut:
    found = session.execute(
        text("SELECT 1 FROM shooter_profiles WHERE shooter_id = :id"), {"id": shooter_id}
    ).first()
    if found is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    frame = apply_round_type_filter(st.load_station_frame(session), round_types)
    return ShooterStationsOut(
        shooter_id=shooter_id,
        stations=[
            ShooterStationDeltaOut(
                station_no=int(r["station_no"]),
                hits=int(r["hits"]),
                n=int(r["n"]),
                n_rounds=int(r["n_rounds"]),
                hit_pct=float(r["hit_pct"]),
                field_pct=float(r["field_pct"]),
                delta=float(r["delta"]),
            )
            for r in _records(st.shooter_station_deltas(frame, shooter_id))
        ],
    )
```

- [ ] **Step 8: Run the route tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/stations/test_station_routes.py tests/unit/analytics/test_station_analytics.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full backend suite with lint, types and coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: PASS with coverage ≥90% lines and branches. Plan 04's runtime route auth matrix (`tests/integration/api/test_route_auth_matrix.py`) now also covers the three station routes, which must return 401 without a cookie.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/stations.py backend/src/sunday_clays/api/routes/stations.py \
  backend/tests/unit/analytics/test_station_analytics.py backend/tests/integration/stations/test_station_routes.py
git commit -m "feat(stations): add station analytics with clustered CIs, eras, wind and routes" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: Station trophies (master Plan 10 T4b)

**Context:** This task adds the station trophies, computed from station-sheet entries (`AchContext.station_hits`, loaded in Task 1).
- The hardest-station rule reuses Task 4's `per_event_station_pct`.
- Only entries linked to a shooter (`shooter_id` not NULL) can earn an award. Unmatched names still count toward a day's station hit % and the field size.
- Contract (master T4b):
  - `hardest_station_clean`: the day's hardest stations are every station whose hit % equals the day's minimum, and anyone who cleaned any of them earns it.
  - `station_top_gun`: needs ≥ 5 shooters that day and one sole top score at that station. A tie means no award.
- Every definition gets a no-leak test.
- Coverage stays ≥90% lines and branches, and ruff and mypy stay clean.

**Branch:** `task/10-4b-station-trophies`

**Depends on:** Plan 10 T1, Plan 10 T4a.

**Files:**
- Create: `backend/src/sunday_clays/analytics/achievements/stations.py`
- Test: `backend/tests/unit/analytics/achievements/test_ach_stations.py`
- Test: `backend/tests/integration/achievements/test_ach_stations_golden.py`

**Interfaces:**
- Consumes:
  - From Task 1: `AchContext.station_hits` (columns `event_date, station_no, target_count, sheet_id, entry_row, shooter_id (Int64), round_id (Int64), hits, event_ts`), `empty_value_frame`, `Achievement`, `Award`, `Category`, `make_tiers`, `register`, and the unit fixtures `ctx_builder` and `no_leak`.
  - From Task 4: `sunday_clays.analytics.stations.per_event_station_pct(frame) -> pd.DataFrame[event_date, station_no, hits, n_targets, hit_pct]`.
- Produces the registered achievements:
  - `station_cleaner`: tiers 1/5/10/25, "stations cleaned" / "station cleaned", category `stations`. The value is the cumulative count of linked entries with `hits == target_count`.
  - `hardest_station_clean`: repeatable, category `stations`. Details `{"stations": [..]}`.
  - `station_top_gun`: repeatable, category `stations`. One award per shooter-day, details `{"stations": [..]}`.

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/unit/analytics/achievements/test_ach_stations.py`:

```python
"""Station trophies (Plan 10 T4b): station_cleaner, hardest_station_clean, station_top_gun."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from sunday_clays.analytics.achievements import registry


def sun(i: int) -> date:
    return date(2025, 1, 5) + timedelta(weeks=i)


def awards(code, ctx):
    return sorted(
        (w.shooter_id, w.code, w.event_date) for w in registry.evaluate_one(registry.get(code), ctx)
    )


def with_stations(code, ctx):
    return sorted(
        (w.shooter_id, w.event_date, tuple(w.details["stations"]))
        for w in registry.evaluate_one(registry.get(code), ctx)
    )


def sheet(builder, day, entries):
    """entries: [(shooter_id or None, {station_no: hits})]; every station has 7 targets."""
    for entry_row, (shooter_id, hits_by_station) in enumerate(entries, start=10):
        for station_no, hits in hits_by_station.items():
            builder.station(shooter_id, day, station_no, hits, entry_row=entry_row)
    return builder


def cleaner_ctx(b):
    builder = b()
    sheet(builder, sun(0), [(1, {4: 7, 5: 7, 6: 3})])
    sheet(builder, sun(1), [(1, {4: 7, 5: 7, 6: 7}), (None, {4: 7}), (2, {4: 6})])
    return builder.build()


def hardest_ctx(b):
    builder = b()
    sheet(
        builder, sun(0), [(1, {4: 7, 5: 0, 6: 7}), (2, {4: 0, 5: 7, 6: 7}), (3, {4: 0, 5: 0, 6: 6})]
    )
    sheet(builder, sun(1), [(1, {4: 7, 5: 7, 6: 0}), (2, {4: 7, 5: 7, 6: 7})])
    return builder.build()


def top_gun_ctx(b):
    builder = b()
    sheet(
        builder,
        sun(0),
        [
            (1, {4: 7, 5: 6}),
            (2, {4: 6, 5: 6}),
            (3, {4: 6, 5: 5}),
            (4, {4: 5, 5: 4}),
            (5, {4: 5, 5: 3}),
        ],
    )
    # sun(1): only 4 entries on the sheet
    sheet(builder, sun(1), [(1, {4: 7}), (2, {4: 3}), (3, {4: 3}), (4, {4: 3})])
    # sun(2): the sole top score belongs to an unmatched entry
    sheet(builder, sun(2), [(None, {4: 7}), (2, {4: 6}), (3, {4: 5}), (4, {4: 5}), (5, {4: 5})])
    sheet(
        builder,
        sun(3),
        [
            (1, {4: 7, 6: 7}),
            (2, {4: 6, 6: 6}),
            (3, {4: 6, 6: 6}),
            (4, {4: 5, 6: 5}),
            (5, {4: 5, 6: 5}),
        ],
    )
    return builder.build()


def test_station_cleaner_counts_cleaned_stations(ctx_builder):
    assert awards("station_cleaner", cleaner_ctx(ctx_builder)) == [
        (1, "station_cleaner:1", sun(0)),
        (1, "station_cleaner:2", sun(1)),
    ]


def test_tied_hardest_stations_award_both(ctx_builder):
    assert with_stations("hardest_station_clean", hardest_ctx(ctx_builder)) == [
        (1, sun(0), (4,)),
        (2, sun(0), (5,)),
        (2, sun(1), (6,)),
    ]


def test_station_top_gun_awards_a_sole_top_score(ctx_builder):
    assert with_stations("station_top_gun", top_gun_ctx(ctx_builder))[0] == (1, sun(0), (4,))


def test_tied_top_gun_gets_no_award(ctx_builder):
    ctx = top_gun_ctx(ctx_builder)
    assert all(
        5 not in stations
        for _, day, stations in with_stations("station_top_gun", ctx)
        if day == sun(0)
    )


def test_top_gun_needs_five_on_the_sheet_and_a_matched_winner(ctx_builder):
    days = [day for _, day, _ in with_stations("station_top_gun", top_gun_ctx(ctx_builder))]
    assert sun(1) not in days
    assert sun(2) not in days


def test_top_gun_lists_every_station_won_that_day(ctx_builder):
    assert with_stations("station_top_gun", top_gun_ctx(ctx_builder)) == [
        (1, sun(0), (4,)),
        (1, sun(3), (4, 6)),
    ]


def test_unmatched_station_entries_earn_nothing(ctx_builder):
    # An unmatched entry (shooter_id NULL) cleans station 4 on cleaner_ctx's sun(1) and has the
    # sole top score on top_gun_ctx's sun(2); every award must still go to a linked shooter.
    for scenario, linked in ((cleaner_ctx, {1, 2}), (top_gun_ctx, {1, 2, 3, 4, 5})):
        ctx = scenario(ctx_builder)
        for code in ("station_cleaner", "hardest_station_clean", "station_top_gun"):
            winners = {w.shooter_id for w in registry.evaluate_one(registry.get(code), ctx)}
            assert winners <= linked, code
    top_gun_days = {day for _, day, _ in with_stations("station_top_gun", top_gun_ctx(ctx_builder))}
    assert sun(2) not in top_gun_days


def test_station_trophies_handle_contexts_without_station_data(ctx_builder):
    ctx = ctx_builder().round(1, sun(0), 30).build()
    assert registry.get("station_cleaner").value(ctx).empty
    assert awards("hardest_station_clean", ctx) == []
    assert awards("station_top_gun", ctx) == []


@pytest.mark.parametrize(
    ("code", "scenario", "cut"),
    [
        ("station_cleaner", cleaner_ctx, sun(0)),
        ("hardest_station_clean", hardest_ctx, sun(0)),
        ("station_top_gun", top_gun_ctx, sun(1)),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_no_leak(code, scenario, cut, ctx_builder, no_leak):
    _, after = no_leak(code, scenario(ctx_builder), cut)
    assert after > 0
```

Hand check of `hardest_ctx`:
- sun(0): stations 4 and 5 are both 7/21 and station 6 is 20/21. Both tie for hardest, so shooter 1 (cleaned 4) and shooter 2 (cleaned 5) earn it.
- sun(1): station 6 is hardest at 7/14 and only shooter 2 cleaned it.

- [ ] **Step 2: Run the unit tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_stations.py -v`
Expected: FAIL with `KeyError: "unknown achievement 'station_cleaner'"` (and likewise for the other two codes).

- [ ] **Step 3: Write the failing golden test**

Create `backend/tests/integration/achievements/test_ach_stations_golden.py`:

```python
"""Station trophies on the committed fixtures (Plan 10 T4b golden).

Hand-checked from backend/tests/fixtures/stations_2026-09-27.xlsx:
- On both days station 9 was hardest (86/168 on 09-06, 44/91 on 09-13 → 0.512 and 0.484) and
  nobody cleaned it.
- 2026-09-06 (24 entries) has no station with a sole top score.
- 2026-09-13 (13 entries) has sole top scores at station 4 (Kingsley, Teddy, 6), 5 (Abernathy, Preston, 7)
  and 10 (McGinnis, Alvin, 8).
- Grimsby, Gregor is the only shooter with 5 cleaned stations (all on 09-06).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def scalar(session: Any, sql: str, **params: Any) -> int:
    return int(session.execute(text(sql), params).scalar_one())


def name_keys(session: Any, code: str) -> set[tuple[str, str]]:
    return {
        (key, day.isoformat())
        for key, day in session.execute(
            text(
                "SELECT DISTINCT r.name_key, a.event_date FROM achievements_awarded a "
                "JOIN rounds r ON r.shooter_id = a.shooter_id WHERE a.code = :c"
            ),
            {"c": code},
        ).all()
    }


def test_station_top_guns_on_fixture(fx_session):
    assert name_keys(fx_session, "station_top_gun") == {
        ("kingsley teddy", "2026-09-13"),
        ("abernathy preston", "2026-09-13"),
        ("mcginnis alvin", "2026-09-13"),
    }
    stations = sorted(
        details["stations"][0]
        for (details,) in fx_session.execute(
            text("SELECT details FROM achievements_awarded WHERE code = 'station_top_gun'")
        ).all()
    )
    assert stations == [4, 5, 10]


def test_nobody_cleaned_the_hardest_station_on_fixture(fx_session):
    assert (
        scalar(
            fx_session,
            "SELECT count(*) FROM achievements_awarded WHERE code = 'hardest_station_clean'",
        )
        == 0
    )


def test_station_cleaner_holders_match_raw_station_hits(fx_session):
    cleaners = scalar(
        fx_session,
        "SELECT count(DISTINCT h.shooter_id) FROM station_hits h JOIN station_layouts l "
        "ON l.event_date = h.event_date AND l.station_no = h.station_no "
        "WHERE h.hits = l.target_count AND h.shooter_id IS NOT NULL",
    )
    assert (
        scalar(
            fx_session, "SELECT count(*) FROM achievements_awarded WHERE code = 'station_cleaner:1'"
        )
        == cleaners
    )
    assert name_keys(fx_session, "station_cleaner:2") == {("grimsby gregor", "2026-09-06")}
```

- [ ] **Step 4: Run the golden test to verify it fails**

Run: `cd backend && uv run pytest tests/integration/achievements/test_ach_stations_golden.py -v`
Expected: FAIL. `test_station_top_guns_on_fixture` gets `set() != {…}`, and the cleaner counts are `0 == 20`. `test_nobody_cleaned_the_hardest_station_on_fixture` passes trivially at this point. It is a guard for after implementation, not the red test.

- [ ] **Step 5: Implement the station trophies**

Create `backend/src/sunday_clays/analytics/achievements/stations.py`:

```python
"""Station trophies (C12, Plan 10 T4b), from station-sheet entries (AchContext.station_hits).

Only entries linked to a shooter earn awards; unmatched names still count toward a day's station
hit % and the number of entries on the sheet."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from fractions import Fraction

import pandas as pd

from sunday_clays.analytics.achievements.context import AchContext, empty_value_frame
from sunday_clays.analytics.achievements.registry import (
    Achievement,
    Award,
    Category,
    make_tiers,
    register,
)
from sunday_clays.analytics.stations import per_event_station_pct

TOP_GUN_MIN_ENTRIES = 5


def _as_date(value: object) -> date:
    return pd.Timestamp(str(value)).date()


def _linked(ctx: AchContext) -> pd.DataFrame:
    hits = ctx.station_hits
    return hits[hits["shooter_id"].notna()]


def station_cleaner_value(ctx: AchContext) -> pd.DataFrame:
    linked = _linked(ctx)
    if linked.empty:
        return empty_value_frame()
    cleaned = linked.assign(clean=(linked["hits"] == linked["target_count"]).astype(int))
    per_day = cleaned.groupby(["shooter_id", "event_ts"], sort=True)["clean"].sum().reset_index()
    per_day["value"] = per_day.groupby("shooter_id")["clean"].cumsum()
    return pd.DataFrame(
        {
            "shooter_id": per_day["shooter_id"].astype("int64").to_numpy(),
            "event_date": per_day["event_ts"].to_numpy(),
            "value": per_day["value"].to_numpy(dtype=float),
        }
    )


def _hardest_station_clean(ctx: AchContext) -> Iterator[Award]:
    hits = ctx.station_hits
    if hits.empty:
        return
    pct = per_event_station_pct(hits)
    for day in sorted(set(pct["event_date"])):
        today = pct[pct["event_date"] == day]
        rates = {
            int(no): Fraction(int(h), int(n))
            for no, h, n in zip(today["station_no"], today["hits"], today["n_targets"], strict=True)
        }
        lowest = min(rates.values())
        hardest = {no for no, rate in rates.items() if rate == lowest}
        cleaners = hits[
            (hits["event_date"] == day)
            & hits["station_no"].isin(hardest)
            & (hits["hits"] == hits["target_count"])
            & hits["shooter_id"].notna()
        ]
        for sid in sorted(set(cleaners["shooter_id"])):
            mine = cleaners[cleaners["shooter_id"] == sid]
            yield Award(
                int(sid),
                "hardest_station_clean",
                _as_date(day),
                None,
                {"stations": sorted({int(s) for s in mine["station_no"]})},
            )


def _station_top_gun(ctx: AchContext) -> Iterator[Award]:
    hits = ctx.station_hits
    won: dict[tuple[int, date], list[int]] = {}
    for day in sorted(set(hits["event_date"])):
        sheet = hits[hits["event_date"] == day]
        if sheet["entry_row"].nunique() < TOP_GUN_MIN_ENTRIES:
            continue
        for no in sorted(sheet["station_no"].unique()):
            station = sheet[sheet["station_no"] == no]
            who = (
                station["shooter_id"]
                .astype("Float64")
                .fillna(-station["entry_row"].astype("Float64"))
            )
            best = station["hits"].groupby(who).max()
            leaders = best[best == best.max()]
            if len(leaders) != 1 or float(leaders.index[0]) < 0:
                continue  # a tie, or an unmatched name on top
            won.setdefault((int(leaders.index[0]), _as_date(day)), []).append(int(no))
    for (sid, day), stations in sorted(won.items()):
        yield Award(sid, "station_top_gun", day, None, {"stations": sorted(stations)})


register(
    Achievement(
        code="station_cleaner",
        name="Station Cleaner",
        description="Stations cleaned: every target at the station broken.",
        category=Category.STATIONS,
        art_key="station_cleaner",
        tiers=make_tiers((1, 5, 10, 25), "stations cleaned", singular="station cleaned"),
        value=station_cleaner_value,
    )
)
register(
    Achievement(
        code="hardest_station_clean",
        name="Hardest Station Clean",
        description="Cleaned the day's hardest station.",
        category=Category.STATIONS,
        art_key="hardest_station_clean",
        evaluate=_hardest_station_clean,
        repeatable=True,
    )
)
register(
    Achievement(
        code="station_top_gun",
        name="Station Top Gun",
        description="Sole top score at a station on a sheet with at least 5 shooters.",
        category=Category.STATIONS,
        art_key="station_top_gun",
        evaluate=_station_top_gun,
        repeatable=True,
    )
)
```

`who` keys each entry by its shooter, or by the negated sheet row when the name is unmatched. A shooter with two entries that day competes with their best one, and an unmatched top score (negative key) blocks the award.

- [ ] **Step 6: Run the unit and golden tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics/achievements/test_ach_stations.py tests/integration/achievements/test_ach_stations_golden.py -v`
Expected: PASS. `station_cleaner:1` has 20 holders on the fixture, but the test asserts the SQL-derived value, not a literal.

- [ ] **Step 7: Run the full backend suite with lint, types and coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: PASS with coverage ≥90% lines and branches.

- [ ] **Step 8: Commit**

```bash
git add backend/src/sunday_clays/analytics/achievements/stations.py \
  backend/tests/unit/analytics/achievements/test_ach_stations.py \
  backend/tests/integration/achievements/test_ach_stations_golden.py
git commit -m "feat(achievements): add station cleaner, top gun and hardest-station trophies" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: Trophy art tool, TrophyIcon fallback and the CI `tools` job (master Plan 10 T5)

**Context:** This task builds the dev-only trophy-art pipeline. `tools/trophy_art/` is a standalone uv project with its own `pyproject.toml` and `uv.lock`, exempt from the Global Constraints dependency-ownership rule.
- It is excluded from app images: the root `.dockerignore` already lists `tools/`.
- It never runs against imagen in CI. All HTTP is mocked with respx.
- Contract: C12 trophy tool and art paths, Global Constraints (imagen at `https://imagen.thehalf.io`; credentials only from `IMAGEN_URL`/`IMAGEN_USERNAME`/`IMAGEN_PASSWORD` env, never committed), C11 (`tools` job in `ci-ok.needs`, enforced by `scripts/tests/test_ci_config.py`).
- The request fields come from `../imagen/src/imagen/api/schemas.py`:
  - `GenerationCreateIn{request: RequestIn, title}` plus the `Idempotency-Key` header.
  - `RequestIn{capability: "txt2img", model_key, prompt, negative_prompt, seed: str, width, height, batch}`. The seed travels as a string (imagen hazard H15).
  - Polling uses `GET /api/generations/{id}`; `state` ∈ queued/assigned/running/completed/failed/canceled, and `outputs[].bytes_url` locates the image.
  - Login is `POST /api/auth/login {username, password}`, which sets a session cookie.
- This task has no code dependency on Task 1: art keys and metals come from the C12 code list and Decision 1. It also adds the frontend `TrophyIcon` SVG fallback and an empty generated art manifest.
- Coverage: ≥90% for the tool; the frontend stays ≥90% lines and branches.

**Branch:** `task/10-5-trophy-art-tool`

**Depends on:** Plan 01 T2 (frontend skeleton) and T5 (`ci.yml`, `test_ci_config.py`). No Plan 10 task.

**Files:**
- Create: `tools/trophy_art/pyproject.toml`
- Create: `tools/trophy_art/uv.lock` (generated by `uv lock`)
- Create: `tools/trophy_art/.gitignore`
- Create: `tools/trophy_art/manifest.yaml`
- Create: `tools/trophy_art/selection.json`
- Create: `tools/trophy_art/manifest.py`
- Create: `tools/trophy_art/client.py`
- Create: `tools/trophy_art/process.py`
- Create: `tools/trophy_art/contact_sheet.py`
- Create: `tools/trophy_art/cli.py`
- Test: `tools/trophy_art/tests/test_manifest.py`, `tests/test_client.py`, `tests/test_process.py`, `tests/test_contact_sheet.py`, `tests/test_cli.py`
- Modify: `.github/workflows/ci.yml` (new `tools` job; `tools` added to `ci-ok.needs`)
- Create: `frontend/src/features/achievements/metals.ts`
- Create: `frontend/src/features/achievements/trophyArt.gen.ts`
- Create: `frontend/src/features/achievements/components/TrophyIcon.tsx`
- Test: `frontend/src/features/achievements/metals.test.ts`
- Test: `frontend/src/features/achievements/components/TrophyIcon.test.tsx`

**Interfaces:**
- Consumes: the imagen HTTP API described above; the Plan 01 T5 `ci.yml` (jobs `backend`, `frontend`, `ratchet`, `docker`, `stack-config`, `e2e`, `ci-ok`, `publish` in that order; `ci-ok` has the inline list `needs: [backend, frontend, ratchet, docker, stack-config, e2e]`; workflow-level `env: {UV_VERSION, PYTHON_VERSION}`; SHA-pinned `actions/checkout` and `astral-sh/setup-uv`) and its guard `scripts/tests/test_ci_config.py` (among the rules master C11 lists: `set(ci-ok.needs) == set(jobs) - {ci-ok, publish}`, no job-level `if:`, no `continue-on-error` on any job or step, `persist-credentials: false` on every checkout, every `uses:` pinned to a 40-hex SHA, `actions/*` included, every piped `run:` under `shell: bash`, and no two jobs saving the same `astral-sh/setup-uv` cache (same `cache-dependency-glob`, `python-version` and `cache-suffix`)).
- Produces:
  - The CLI, run from `tools/trophy_art`: `uv run python cli.py [--out DIR] [--manifest PATH] [--selection PATH] <command>`.
    - `generate [--only ART_KEY]`: writes `out/candidates/<stem>/<seed>.png`, is resumable, and exits 1 if any generation failed or 2 on missing credentials or a failed login.
    - `sheet`: writes `out/contact_sheet.html`.
    - `select <art_key> <metal|-> <seed>`: records the pick in `selection.json`.
    - `build [--repo-root PATH]`: writes `frontend/public/trophies/<stem>.webp` (256 px) and `<stem>@128.webp`, plus `frontend/src/features/achievements/trophyArt.gen.ts`.
    - `check KEYS_JSON`: takes a JSON list of `[art_key, metal|null]` and exits 1 when the manifest lacks one.
    - `<stem>` = `<art_key>` or `<art_key>-<metal>`.
  - `manifest.py`: `Target(art_key, metal, prompt, negative, model, seeds, size)` with `.stem`; `load_manifest(path) -> list[Target]`; `split_stem(stem) -> tuple[str, str | None]`; `METALS`.
  - `client.py`:
    - `idempotency_key(art_key, metal, prompt, model, seed) -> str`: sha256 of `art_key|metal|prompt|model|seed`, with `''` for a one-off's metal.
    - `GenerationSpec`
    - `ImagenClient(base_url, *, sleep, clock, poll_seconds=3.0, timeout_seconds=900.0)` with `.login`, `.create`, `.wait`, `.download_first_output`, `.generate` and `.close`.
    - `ImagenError`
  - `process.py`: `medallion(png: bytes, size: int) -> bytes` (WebP).
  - `contact_sheet.py`: `build_sheet(candidates_dir: Path) -> str`.
  - `frontend/src/features/achievements/`:
    - `metals.ts`: `type Metal`, `METAL_COLORS`, `ONE_OFF_COLOR`, `LOCKED_STYLE`, `artManifestKey(artKey, metal)`.
    - `trophyArt.gen.ts`: `trophyArt: Record<string, { src: string; src128: string }>`.
    - `components/TrophyIcon.tsx`: `TrophyIcon({artKey, metal, locked, size})`.
  - The manifest covers every C12 art target: 9 families × their metals = 38, plus 24 one-offs = 62 targets.

- [ ] **Step 1: Create the uv project and lock it**

Create `tools/trophy_art/pyproject.toml`:

```toml
[project]
name = "trophy-art"
version = "0.1.0"
description = "Dev-only imagen client and art pipeline for Sunday Clays trophies. Never shipped in an image."
requires-python = ">=3.13"
dependencies = ["httpx>=0.28", "pillow>=11.0", "pyyaml>=6.0.2"]

[dependency-groups]
dev = ["mypy>=1.13", "pytest>=8.3", "pytest-cov>=6.0", "respx>=0.22", "ruff>=0.8", "types-PyYAML>=6.0.12"]

[tool.uv]
package = false

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF"]

[tool.mypy]
strict = true
files = ["manifest.py", "client.py", "process.py", "contact_sheet.py", "cli.py"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "--cov=. --cov-branch --cov-report=term-missing --cov-fail-under=90"
filterwarnings = ["error"]

[tool.coverage.run]
omit = ["tests/*"]
```

Create `tools/trophy_art/.gitignore`:

```gitignore
out/
.coverage
```

Create `tools/trophy_art/selection.json`:

```json
{}
```

Run: `cd tools/trophy_art && uv lock && uv sync`
Expected: `uv.lock` is created and a `.venv` with httpx, pillow, pyyaml and the dev group is installed.

- [ ] **Step 2: Write the failing manifest tests**

Create `tools/trophy_art/tests/test_manifest.py`:

```python
from pathlib import Path

import pytest

from manifest import ManifestError, Target, load_manifest, split_stem

SAMPLE = """
style: "house style"
defaults: {model: z-image, size: 1024, seeds: [101, 202], negative: "no text"}
metal_phrases:
  bronze: "warm bronze finish"
  silver: "polished silver finish"
  gold: "gleaming gold finish"
  platinum: "brushed platinum finish"
  diamond: "platinum set with diamonds"
  one_off: "copper with orange enamel"
trophies:
  - {art_key: clays_broken, metals: [bronze, gold], prompt: "a shattered clay"}
  - {art_key: doubleheader, metals: [], prompt: "two clays", seeds: [7], negative: "blurry"}
"""

FAMILY_METALS = {
    "clays_broken": ("bronze", "silver", "gold", "platinum", "diamond"),
    "clays_thrown": ("bronze", "silver", "gold", "platinum", "diamond"),
    "events": ("bronze", "silver", "gold", "platinum", "diamond"),
    "years_active": ("bronze", "silver", "gold", "platinum"),
    "big_year": ("bronze", "silver", "gold"),
    "iron_streak": ("bronze", "silver", "gold", "platinum"),
    "round_score": ("bronze", "silver", "gold", "platinum", "diamond"),
    "station_cleaner": ("bronze", "silver", "gold", "platinum"),
    "personal_bests": ("bronze", "silver", "gold"),
}
ONE_OFFS = (
    "doubleheader",
    "new_year",
    "anniversary_1",
    "anniversary_5",
    "welcome_back",
    "joined_club",
    "both_disciplines",
    "four_seasons",
    "perfect_month",
    "sub_gauge",
    "rain",
    "cold",
    "heat",
    "wind",
    "all_weather",
    "mudder",
    "comeback",
    "above_average_3",
    "first_win",
    "podium",
    "giant_killer",
    "class_up",
    "station_top_gun",
    "hardest_station_clean",
)
HOUSE_STYLE = (
    "enamel-and-metal clay-shooting trophy medallion, centered, flat studio lighting, "
    "dark forest-green backdrop, no text"
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(text)
    return path


def test_targets_expand_metals_and_apply_defaults(tmp_path):
    assert load_manifest(write(tmp_path, SAMPLE)) == [
        Target(
            "clays_broken",
            "bronze",
            "house style, warm bronze finish, a shattered clay",
            "no text",
            "z-image",
            (101, 202),
            1024,
        ),
        Target(
            "clays_broken",
            "gold",
            "house style, gleaming gold finish, a shattered clay",
            "no text",
            "z-image",
            (101, 202),
            1024,
        ),
        Target(
            "doubleheader", None, "house style, copper with orange enamel, two clays", "blurry", "z-image", (7,), 1024
        ),
    ]


def test_stems_add_the_metal_suffix_only_for_tiers(tmp_path):
    assert [t.stem for t in load_manifest(write(tmp_path, SAMPLE))] == [
        "clays_broken-bronze",
        "clays_broken-gold",
        "doubleheader",
    ]


def test_unknown_metal_is_rejected(tmp_path):
    with pytest.raises(ManifestError, match="unknown metal 'copper'"):
        load_manifest(write(tmp_path, SAMPLE.replace("[bronze, gold]", "[copper]")))


def test_duplicate_target_is_rejected(tmp_path):
    with pytest.raises(ManifestError, match="duplicate target doubleheader"):
        load_manifest(write(tmp_path, SAMPLE + '  - {art_key: doubleheader, metals: [], prompt: "again"}\n'))


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("clays_broken-gold", ("clays_broken", "gold")),
        ("doubleheader", ("doubleheader", None)),
        ("above_average_3", ("above_average_3", None)),
    ],
)
def test_split_stem(stem, expected):
    assert split_stem(stem) == expected


def test_real_manifest_covers_every_c12_art_target():
    targets = load_manifest(Path(__file__).resolve().parents[1] / "manifest.yaml")
    expected = {(k, m) for k, metals in FAMILY_METALS.items() for m in metals} | {(k, None) for k in ONE_OFFS}
    assert len(expected) == 62
    assert {(t.art_key, t.metal) for t in targets} == expected
    assert all(t.seeds == (101, 202, 303, 404) and t.model == "z-image" and t.size == 1024 for t in targets)
    assert all(t.prompt.startswith(HOUSE_STYLE) for t in targets)
```

- [ ] **Step 3: Run the manifest tests to verify they fail**

Run: `cd tools/trophy_art && uv run pytest tests/test_manifest.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'manifest'`.

- [ ] **Step 4: Implement the manifest loader and write the manifest**

Create `tools/trophy_art/manifest.py`:

```python
"""manifest.yaml → generation targets: one per art_key x metal (metal None for one-offs)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

METALS = ("bronze", "silver", "gold", "platinum", "diamond")


class ManifestError(ValueError):
    """The manifest is malformed."""


@dataclass(frozen=True)
class Target:
    art_key: str
    metal: str | None
    prompt: str
    negative: str
    model: str
    seeds: tuple[int, ...]
    size: int

    @property
    def stem(self) -> str:
        return self.art_key if self.metal is None else f"{self.art_key}-{self.metal}"


def split_stem(stem: str) -> tuple[str, str | None]:
    art_key, _, metal = stem.rpartition("-")
    return (art_key, metal) if art_key and metal in METALS else (stem, None)


def load_manifest(path: Path) -> list[Target]:
    doc: dict[str, Any] = yaml.safe_load(path.read_text())
    style = str(doc["style"])
    defaults: dict[str, Any] = doc["defaults"]
    phrases: dict[str, str] = doc["metal_phrases"]
    targets: list[Target] = []
    seen: set[str] = set()
    for entry in doc["trophies"]:
        art_key = str(entry["art_key"])
        metals: list[str | None] = [str(m) for m in entry.get("metals", [])] or [None]
        for metal in metals:
            if metal is not None and metal not in METALS:
                raise ManifestError(f"{art_key}: unknown metal {metal!r}")
            target = Target(
                art_key=art_key,
                metal=metal,
                prompt=f"{style}, {phrases['one_off' if metal is None else metal]}, {entry['prompt']}",
                negative=str(entry.get("negative", defaults["negative"])),
                model=str(entry.get("model", defaults["model"])),
                seeds=tuple(int(s) for s in entry.get("seeds", defaults["seeds"])),
                size=int(entry.get("size", defaults["size"])),
            )
            if target.stem in seen:
                raise ManifestError(f"duplicate target {target.stem}")
            seen.add(target.stem)
            targets.append(target)
    return targets
```

Create `tools/trophy_art/manifest.yaml`:

```yaml
# One prompt per trophy; tiered families list the metals their tiers use (Plan 10 Decision 1).
# The full prompt is "<style>, <metal phrase>, <prompt>". Never put credentials here.
style: "enamel-and-metal clay-shooting trophy medallion, centered, flat studio lighting, dark forest-green backdrop, no text"
defaults:
  model: z-image
  size: 1024
  seeds: [101, 202, 303, 404]
  negative: "text, letters, numbers, words, watermark, logo, signature, border frame, people, hands, blurry, low quality"
metal_phrases:
  bronze: "warm bronze finish"
  silver: "polished silver finish"
  gold: "gleaming gold finish"
  platinum: "brushed platinum finish"
  diamond: "platinum set with sparkling diamonds"
  one_off: "burnished copper with orange enamel"
trophies:
  - art_key: clays_broken
    metals: [bronze, silver, gold, platinum, diamond]
    prompt: "an orange clay target shattering into flying fragments"
  - art_key: clays_thrown
    metals: [bronze, silver, gold, platinum, diamond]
    prompt: "an orange clay target launched in a high arc from a trap machine"
  - art_key: events
    metals: [bronze, silver, gold, platinum, diamond]
    prompt: "a sunrise over a sporting clays field with a shooting station post"
  - art_key: years_active
    metals: [bronze, silver, gold, platinum]
    prompt: "concentric growth rings like a tree stump with a clay target at the center"
  - art_key: big_year
    metals: [bronze, silver, gold]
    prompt: "a laurel wreath encircling a ring of small clay targets"
  - art_key: iron_streak
    metals: [bronze, silver, gold, platinum]
    prompt: "an unbroken iron chain whose links are clay targets"
  - art_key: round_score
    metals: [bronze, silver, gold, platinum, diamond]
    prompt: "a bullseye made of concentric rings of clay targets"
  - art_key: station_cleaner
    metals: [bronze, silver, gold, platinum]
    prompt: "a wooden shooting station cage with a sparkle of cleared targets"
  - art_key: personal_bests
    metals: [bronze, silver, gold]
    prompt: "an upward arrow built from clay target shards"
  - art_key: doubleheader
    prompt: "two clay targets side by side with two crossed shotgun shells"
  - art_key: new_year
    prompt: "fireworks bursting above a clay target at dawn"
  - art_key: anniversary_1
    prompt: "a single candle standing on a clay target"
  - art_key: anniversary_5
    prompt: "five candles standing on a clay target"
  - art_key: welcome_back
    prompt: "an open farm gate on a path leading to a shooting field"
  - art_key: joined_club
    prompt: "a handshake in front of a club crest shield"
  - art_key: both_disciplines
    prompt: "two crossed shotguns over two clay targets"
  - art_key: four_seasons
    prompt: "a clay target split into four quadrants of snow, blossom, sun and autumn leaves"
  - art_key: perfect_month
    prompt: "a full moon rising behind a clay target"
  - art_key: sub_gauge
    prompt: "a slim small-gauge shotgun shell standing upright"
  - art_key: rain
    prompt: "raindrops falling on a clay target"
  - art_key: cold
    prompt: "a frosted clay target hung with icicles"
  - art_key: heat
    prompt: "a blazing sun behind a clay target"
  - art_key: wind
    prompt: "swirling wind lines carrying a clay target"
  - art_key: all_weather
    prompt: "a sun, a rain cloud, a snowflake and a wind swirl circling a clay target"
  - art_key: mudder
    prompt: "a mud-splattered clay target and shotgun shell"
  - art_key: comeback
    prompt: "a phoenix rising from clay target shards"
  - art_key: above_average_3
    prompt: "three clay targets on ascending steps"
  - art_key: first_win
    prompt: "a laurel crown resting on a clay target"
  - art_key: podium
    prompt: "a three-step podium with a clay target on the top step"
  - art_key: giant_killer
    prompt: "a small shotgun shell standing over a toppled giant shell"
  - art_key: class_up
    prompt: "a rank chevron insignia above a clay target"
  - art_key: station_top_gun
    prompt: "a crosshair over a shooting station post with a star"
  - art_key: hardest_station_clean
    prompt: "a clean clay target on the summit of a jagged mountain peak"
```

- [ ] **Step 5: Run the manifest tests to verify they pass**

Run: `cd tools/trophy_art && uv run pytest tests/test_manifest.py -v --no-cov`
Expected: PASS (6 tests, 8 cases counting the parametrized ones).

- [ ] **Step 6: Write the failing client tests**

Create `tools/trophy_art/tests/test_client.py`:

```python
import hashlib
import json

import httpx
import pytest

from client import GenerationSpec, ImagenClient, ImagenError, idempotency_key

BASE = "https://imagen.test"
SPEC = GenerationSpec(
    art_key="clays_broken", metal="gold", prompt="p", negative="n", model="z-image", seed=11, size=1024
)
OUTPUT = {
    "ordinal": 0,
    "asset_id": "a1",
    "thumb_url": "/api/assets/a1/thumb?w=320",
    "bytes_url": "/api/assets/a1/bytes",
}


def generation(state, outputs=()):
    return {"id": "gen-1", "state": state, "outputs": list(outputs)}


def test_idempotency_key_is_sha256_of_the_joined_fields():
    assert (
        idempotency_key("clays_broken", "gold", "p", "z-image", 11)
        == hashlib.sha256(b"clays_broken|gold|p|z-image|11").hexdigest()
    )
    assert (
        idempotency_key("doubleheader", None, "p", "z-image", 11)
        == hashlib.sha256(b"doubleheader||p|z-image|11").hexdigest()
    )


@pytest.mark.respx(base_url=BASE)
def test_login_posts_credentials(respx_mock):
    route = respx_mock.post("/api/auth/login").mock(
        return_value=httpx.Response(200, json={"id": "u1", "username": "bryan", "is_admin": False})
    )
    ImagenClient(BASE).login("bryan", "secret")
    assert json.loads(route.calls.last.request.content) == {"username": "bryan", "password": "secret"}


@pytest.mark.respx(base_url=BASE)
def test_login_failure_raises(respx_mock):
    respx_mock.post("/api/auth/login").mock(return_value=httpx.Response(401))
    with pytest.raises(ImagenError, match="login failed: HTTP 401"):
        ImagenClient(BASE).login("bryan", "wrong")


@pytest.mark.respx(base_url=BASE)
def test_create_sends_request_fields_and_idempotency_key(respx_mock):
    route = respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    assert ImagenClient(BASE).create(SPEC) == "gen-1"
    sent = route.calls.last.request
    assert sent.headers["Idempotency-Key"] == hashlib.sha256(b"clays_broken|gold|p|z-image|11").hexdigest()
    assert json.loads(sent.content) == {
        "request": {
            "capability": "txt2img",
            "model_key": "z-image",
            "prompt": "p",
            "negative_prompt": "n",
            "seed": "11",
            "width": 1024,
            "height": 1024,
            "batch": 1,
        },
        "title": "trophy clays_broken gold seed 11",
    }


@pytest.mark.respx(base_url=BASE)
def test_replayed_create_returns_the_existing_generation(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(200, json=generation("completed")))
    assert ImagenClient(BASE).create(SPEC) == "gen-1"


@pytest.mark.respx(base_url=BASE)
def test_create_rejection_raises(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(422))
    with pytest.raises(ImagenError, match="create failed: HTTP 422"):
        ImagenClient(BASE).create(SPEC)


@pytest.mark.respx(base_url=BASE)
def test_wait_polls_until_terminal(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(
        side_effect=[
            httpx.Response(200, json=generation("queued")),
            httpx.Response(200, json=generation("running")),
            httpx.Response(200, json=generation("completed", [OUTPUT])),
        ]
    )
    sleeps: list[float] = []
    assert ImagenClient(BASE, sleep=sleeps.append).wait("gen-1")["state"] == "completed"
    assert sleeps == [3.0, 3.0]


@pytest.mark.respx(base_url=BASE)
def test_wait_times_out(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(return_value=httpx.Response(200, json=generation("running")))
    ticks = iter([0.0, 100.0, 1000.0])
    client = ImagenClient(BASE, sleep=lambda _: None, clock=lambda: next(ticks), timeout_seconds=900.0)
    with pytest.raises(ImagenError, match="timed out"):
        client.wait("gen-1")


@pytest.mark.respx(base_url=BASE)
def test_poll_error_raises(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(return_value=httpx.Response(500))
    with pytest.raises(ImagenError, match="poll failed: HTTP 500"):
        ImagenClient(BASE).wait("gen-1")


@pytest.mark.respx(base_url=BASE)
def test_generate_downloads_the_first_output(respx_mock):
    respx_mock.post("/api/generations").mock(return_value=httpx.Response(201, json=generation("queued")))
    respx_mock.get("/api/generations/gen-1").mock(
        return_value=httpx.Response(200, json=generation("completed", [OUTPUT]))
    )
    respx_mock.get("/api/assets/a1/bytes").mock(return_value=httpx.Response(200, content=b"PNGDATA"))
    client = ImagenClient(BASE)
    assert client.generate(SPEC) == b"PNGDATA"
    client.close()


@pytest.mark.respx(base_url=BASE)
def test_failed_generation_raises(respx_mock):
    respx_mock.get("/api/generations/gen-1").mock(return_value=httpx.Response(200, json=generation("failed")))
    client = ImagenClient(BASE)
    with pytest.raises(ImagenError, match="ended failed with 0 outputs"):
        client.download_first_output(client.wait("gen-1"))


@pytest.mark.respx(base_url=BASE)
def test_download_error_raises(respx_mock):
    respx_mock.get("/api/assets/a1/bytes").mock(return_value=httpx.Response(404))
    with pytest.raises(ImagenError, match="download failed: HTTP 404"):
        ImagenClient(BASE).download_first_output(generation("completed", [OUTPUT]))
```

- [ ] **Step 7: Run the client tests to verify they fail**

Run: `cd tools/trophy_art && uv run pytest tests/test_client.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'client'`.

- [ ] **Step 8: Implement the client**

Create `tools/trophy_art/client.py`:

```python
"""Minimal imagen client (dev-only; the app and CI never call imagen).

Fields follow ../imagen/src/imagen/api/schemas.py: POST /api/generations takes
GenerationCreateIn{request: RequestIn, title} with an Idempotency-Key header, and seeds travel as
strings (imagen hazard H15). GET /api/generations/{id} is polled until a terminal state, then the
first output's bytes_url is downloaded."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

TERMINAL_STATES = frozenset({"completed", "failed", "canceled"})


class ImagenError(RuntimeError):
    """A login, create, poll or download that did not succeed."""


def idempotency_key(art_key: str, metal: str | None, prompt: str, model: str, seed: int) -> str:
    return hashlib.sha256(f"{art_key}|{metal or ''}|{prompt}|{model}|{seed}".encode()).hexdigest()


@dataclass(frozen=True)
class GenerationSpec:
    art_key: str
    metal: str | None
    prompt: str
    negative: str
    model: str
    seed: int
    size: int


class ImagenClient:
    def __init__(
        self,
        base_url: str,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        poll_seconds: float = 3.0,
        timeout_seconds: float = 900.0,
    ) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=60.0)
        self._sleep = sleep
        self._clock = clock
        self._poll_seconds = poll_seconds
        self._timeout_seconds = timeout_seconds

    def close(self) -> None:
        self._http.close()

    def login(self, username: str, password: str) -> None:
        response = self._http.post("/api/auth/login", json={"username": username, "password": password})
        if response.status_code != 200:
            raise ImagenError(f"login failed: HTTP {response.status_code}")

    def create(self, spec: GenerationSpec) -> str:
        body = {
            "request": {
                "capability": "txt2img",
                "model_key": spec.model,
                "prompt": spec.prompt,
                "negative_prompt": spec.negative,
                "seed": str(spec.seed),
                "width": spec.size,
                "height": spec.size,
                "batch": 1,
            },
            "title": f"trophy {spec.art_key} {spec.metal or 'one-off'} seed {spec.seed}",
        }
        key = idempotency_key(spec.art_key, spec.metal, spec.prompt, spec.model, spec.seed)
        response = self._http.post("/api/generations", json=body, headers={"Idempotency-Key": key})
        if response.status_code not in (200, 201):
            raise ImagenError(f"create failed: HTTP {response.status_code}")
        return str(response.json()["id"])

    def wait(self, generation_id: str) -> dict[str, Any]:
        deadline = self._clock() + self._timeout_seconds
        while True:
            response = self._http.get(f"/api/generations/{generation_id}")
            if response.status_code != 200:
                raise ImagenError(f"poll failed: HTTP {response.status_code}")
            doc: dict[str, Any] = response.json()
            if doc["state"] in TERMINAL_STATES:
                return doc
            if self._clock() > deadline:
                raise ImagenError(f"generation {generation_id} timed out after {self._timeout_seconds:.0f} s")
            self._sleep(self._poll_seconds)

    def download_first_output(self, doc: dict[str, Any]) -> bytes:
        outputs: list[dict[str, Any]] = list(doc.get("outputs") or [])
        if doc["state"] != "completed" or not outputs:
            raise ImagenError(f"generation {doc['id']} ended {doc['state']} with {len(outputs)} outputs")
        response = self._http.get(str(outputs[0]["bytes_url"]))
        if response.status_code != 200:
            raise ImagenError(f"download failed: HTTP {response.status_code}")
        return response.content

    def generate(self, spec: GenerationSpec) -> bytes:
        return self.download_first_output(self.wait(self.create(spec)))
```

- [ ] **Step 9: Run the client tests to verify they pass**

Run: `cd tools/trophy_art && uv run pytest tests/test_client.py -v --no-cov`
Expected: PASS (12 tests).

- [ ] **Step 10: Write the failing processing and contact-sheet tests**

Create `tools/trophy_art/tests/test_process.py`:

```python
from io import BytesIO

from PIL import Image

from process import medallion


def to_png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_medallion_is_a_square_webp_with_transparent_corners():
    out = Image.open(BytesIO(medallion(to_png(Image.new("RGB", (300, 200), (200, 60, 40))), 256)))
    assert (out.format, out.size, out.mode) == ("WEBP", (256, 256), "RGBA")
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((128, 128))[3] == 255


def test_medallion_crops_the_centre_square():
    image = Image.new("RGB", (300, 200), (255, 0, 0))
    image.paste((0, 0, 255), (50, 0, 250, 200))  # the centred 200x200 square is blue, the margins red
    red, _, blue, alpha = Image.open(BytesIO(medallion(to_png(image), 128))).convert("RGBA").getpixel((16, 64))
    assert alpha == 255
    assert blue > 200 and red < 60


def test_small_size_is_128():
    assert Image.open(BytesIO(medallion(to_png(Image.new("RGB", (64, 64))), 128))).size == (128, 128)
```

Create `tools/trophy_art/tests/test_contact_sheet.py`:

```python
from contact_sheet import build_sheet


def test_sheet_lists_every_candidate_with_its_select_command(tmp_path):
    for stem, seeds in {"clays_broken-gold": [202, 101], "doubleheader": [101]}.items():
        (tmp_path / stem).mkdir()
        for seed in seeds:
            (tmp_path / stem / f"{seed}.png").write_bytes(b"x")
    html = build_sheet(tmp_path)
    assert html.index("candidates/clays_broken-gold/101.png") < html.index("candidates/clays_broken-gold/202.png")
    assert "python cli.py select clays_broken gold 101" in html
    assert "python cli.py select doubleheader - 101" in html


def test_sheet_escapes_names(tmp_path):
    (tmp_path / "<b>x").mkdir()
    (tmp_path / "<b>x" / "1.png").write_bytes(b"x")
    html = build_sheet(tmp_path)
    assert "<b>x" not in html
    assert "&lt;b&gt;x" in html
```

- [ ] **Step 11: Run them to verify they fail**

Run: `cd tools/trophy_art && uv run pytest tests/test_process.py tests/test_contact_sheet.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'process'` and `... 'contact_sheet'`.

- [ ] **Step 12: Implement processing and the contact sheet**

Create `tools/trophy_art/process.py`:

```python
"""Candidate PNG → circular medallion WebP: centred square crop, anti-aliased circular alpha."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

SUPERSAMPLE = 4


def square_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def circular_mask(size: int) -> Image.Image:
    big = size * SUPERSAMPLE
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def medallion(png: bytes, size: int) -> bytes:
    with Image.open(BytesIO(png)) as source:
        image = square_crop(source.convert("RGBA")).resize((size, size), Image.Resampling.LANCZOS)
    image.putalpha(circular_mask(size))
    out = BytesIO()
    image.save(out, format="WEBP", quality=90, method=6)
    return out.getvalue()
```

Create `tools/trophy_art/contact_sheet.py`:

```python
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
```

- [ ] **Step 13: Run them to verify they pass**

Run: `cd tools/trophy_art && uv run pytest tests/test_process.py tests/test_contact_sheet.py -v --no-cov`
Expected: PASS.

- [ ] **Step 14: Write the failing CLI tests**

Create `tools/trophy_art/tests/test_cli.py`:

```python
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

import cli

BASE = "https://imagen.test"
MANIFEST = """
style: "style"
defaults: {model: z-image, size: 64, seeds: [1, 2], negative: "n"}
metal_phrases: {bronze: b, silver: s, gold: g, platinum: p, diamond: d, one_off: o}
trophies:
  - {art_key: doubleheader, metals: [], prompt: "two clays"}
"""
OUTPUT = {"ordinal": 0, "asset_id": "a1", "thumb_url": "/t", "bytes_url": "/api/assets/a1/bytes"}


def png_bytes() -> bytes:
    out = BytesIO()
    Image.new("RGB", (64, 64), (200, 60, 40)).save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def paths(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(MANIFEST)
    selection = tmp_path / "selection.json"
    selection.write_text("{}\n")
    return {"manifest": manifest, "selection": selection, "out": tmp_path / "out", "repo": tmp_path / "repo"}


def run(paths, *args: str) -> int:
    return cli.main(
        [
            "--out",
            str(paths["out"]),
            "--manifest",
            str(paths["manifest"]),
            "--selection",
            str(paths["selection"]),
            *args,
        ]
    )


@pytest.fixture
def imagen_env(monkeypatch):
    monkeypatch.setenv("IMAGEN_URL", BASE)
    monkeypatch.setenv("IMAGEN_USERNAME", "bryan")
    monkeypatch.setenv("IMAGEN_PASSWORD", "secret")


def mock_imagen(respx_mock, state="completed"):
    respx_mock.post("/api/auth/login").mock(
        return_value=httpx.Response(200, json={"id": "u1", "username": "bryan", "is_admin": False})
    )
    create = respx_mock.post("/api/generations").mock(
        return_value=httpx.Response(201, json={"id": "g1", "state": "queued", "outputs": []})
    )
    outputs = [OUTPUT] if state == "completed" else []
    respx_mock.get("/api/generations/g1").mock(
        return_value=httpx.Response(200, json={"id": "g1", "state": state, "outputs": outputs})
    )
    respx_mock.get("/api/assets/a1/bytes").mock(return_value=httpx.Response(200, content=png_bytes()))
    return create


def test_generate_requires_credentials(paths, monkeypatch, capsys):
    monkeypatch.delenv("IMAGEN_USERNAME", raising=False)
    monkeypatch.delenv("IMAGEN_PASSWORD", raising=False)
    assert run(paths, "generate") == 2
    assert "IMAGEN_USERNAME and IMAGEN_PASSWORD" in capsys.readouterr().err


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_saves_each_seed_and_resumes(paths, imagen_env, respx_mock):
    create = mock_imagen(respx_mock)
    assert run(paths, "generate") == 0
    saved = sorted(p.name for p in (paths["out"] / "candidates" / "doubleheader").iterdir())
    assert saved == ["1.png", "2.png"]
    assert create.call_count == 2
    assert run(paths, "generate", "--only", "doubleheader") == 0
    assert create.call_count == 2  # existing candidates are never regenerated


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_only_filters_art_keys(paths, imagen_env, respx_mock):
    create = mock_imagen(respx_mock)
    assert run(paths, "generate", "--only", "rain") == 0
    assert create.call_count == 0


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_reports_failures_and_continues(paths, imagen_env, respx_mock, capsys):
    mock_imagen(respx_mock, state="failed")
    assert run(paths, "generate") == 1
    assert capsys.readouterr().err.count("ended failed") == 2


@pytest.mark.respx(base_url=BASE, assert_all_called=False)
def test_generate_stops_when_login_fails(paths, imagen_env, respx_mock, capsys):
    respx_mock.post("/api/auth/login").mock(return_value=httpx.Response(401))
    assert run(paths, "generate") == 2
    assert "login failed" in capsys.readouterr().err


def test_sheet_requires_candidates(paths):
    assert run(paths, "sheet") == 1


def test_sheet_writes_the_contact_sheet(paths):
    target = paths["out"] / "candidates" / "doubleheader"
    target.mkdir(parents=True)
    (target / "1.png").write_bytes(png_bytes())
    assert run(paths, "sheet") == 0
    assert "candidates/doubleheader/1.png" in (paths["out"] / "contact_sheet.html").read_text()


def test_select_records_a_pick(paths):
    target = paths["out"] / "candidates" / "clays_broken-gold"
    target.mkdir(parents=True)
    (target / "202.png").write_bytes(png_bytes())
    assert run(paths, "select", "clays_broken", "gold", "202") == 0
    assert json.loads(paths["selection"].read_text()) == {
        "clays_broken-gold": {"art_key": "clays_broken", "metal": "gold", "seed": 202}
    }


def test_select_rejects_missing_candidates_and_unknown_metals(paths):
    assert run(paths, "select", "doubleheader", "-", "9") == 1
    assert run(paths, "select", "doubleheader", "copper", "9") == 2


def test_build_writes_webp_pairs_and_the_ts_manifest(paths):
    target = paths["out"] / "candidates" / "doubleheader"
    target.mkdir(parents=True)
    (target / "1.png").write_bytes(png_bytes())
    assert run(paths, "select", "doubleheader", "-", "1") == 0
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 0
    public = paths["repo"] / "frontend" / "public" / "trophies"
    with Image.open(public / "doubleheader.webp") as large, Image.open(public / "doubleheader@128.webp") as small:
        assert (large.size, small.size) == ((256, 256), (128, 128))
    generated = (paths["repo"] / "frontend" / "src" / "features" / "achievements" / "trophyArt.gen.ts").read_text()
    assert (
        "'doubleheader': { src: '/trophies/doubleheader.webp', src128: '/trophies/doubleheader@128.webp' },"
        in generated
    )


def test_build_fails_when_a_selected_candidate_is_missing(paths):
    paths["selection"].write_text(json.dumps({"rain": {"art_key": "rain", "metal": None, "seed": 5}}))
    assert run(paths, "build", "--repo-root", str(paths["repo"])) == 1


def test_render_manifest_ts_without_art_is_an_empty_record():
    assert cli.render_manifest_ts([]) == (
        "// Generated by tools/trophy_art/cli.py build. Do not edit by hand.\n"
        "export const trophyArt: Record<string, { src: string; src128: string }> = {};\n"
    )


def test_check_reports_missing_targets(paths, tmp_path, capsys):
    keys = tmp_path / "keys.json"
    keys.write_text(json.dumps([["doubleheader", None], ["rain", None]]))
    assert run(paths, "check", str(keys)) == 1
    assert "missing manifest entry: rain -" in capsys.readouterr().out
    keys.write_text(json.dumps([["doubleheader", None]]))
    assert run(paths, "check", str(keys)) == 0


def test_default_paths_point_inside_the_tool():
    args = cli.build_parser().parse_args(["sheet"])
    assert args.manifest == Path(cli.__file__).resolve().parent / "manifest.yaml"
```

- [ ] **Step 15: Run the CLI tests to verify they fail**

Run: `cd tools/trophy_art && uv run pytest tests/test_cli.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'cli'`.

- [ ] **Step 16: Implement the CLI**

Create `tools/trophy_art/cli.py`:

```python
"""trophy-art CLI (run from tools/trophy_art):
generate → sheet → (the user picks) → select … → build. `check` confirms manifest coverage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from client import GenerationSpec, ImagenClient, ImagenError
from contact_sheet import build_sheet
from manifest import METALS, load_manifest
from process import medallion

HERE = Path(__file__).resolve().parent
DEFAULT_IMAGEN_URL = "https://imagen.thehalf.io"
_HEADER = "// Generated by tools/trophy_art/cli.py build. Do not edit by hand.\n"
_DECL = "export const trophyArt: Record<string, { src: string; src128: string }> = "


def render_manifest_ts(stems: Sequence[str]) -> str:
    if not stems:
        return _HEADER + _DECL + "{};\n"
    lines = [f"  '{s}': {{ src: '/trophies/{s}.webp', src128: '/trophies/{s}@128.webp' }}," for s in sorted(stems)]
    return _HEADER + _DECL + "{\n" + "\n".join(lines) + "\n};\n"


def _read_selection(path: Path) -> dict[str, dict[str, Any]]:
    selection: dict[str, dict[str, Any]] = json.loads(path.read_text())
    return selection


def _generate(args: argparse.Namespace) -> int:
    username = os.environ.get("IMAGEN_USERNAME")
    password = os.environ.get("IMAGEN_PASSWORD")
    if not username or not password:
        print("IMAGEN_USERNAME and IMAGEN_PASSWORD must be set in the environment", file=sys.stderr)
        return 2
    targets = [t for t in load_manifest(args.manifest) if args.only is None or t.art_key == args.only]
    client = ImagenClient(os.environ.get("IMAGEN_URL", DEFAULT_IMAGEN_URL))
    failures = 0
    try:
        client.login(username, password)
        for target in targets:
            for seed in target.seeds:
                path = args.out / "candidates" / target.stem / f"{seed}.png"
                if path.exists():
                    continue
                spec = GenerationSpec(
                    art_key=target.art_key,
                    metal=target.metal,
                    prompt=target.prompt,
                    negative=target.negative,
                    model=target.model,
                    seed=seed,
                    size=target.size,
                )
                try:
                    data = client.generate(spec)
                except ImagenError as exc:
                    failures += 1
                    print(f"{target.stem} seed {seed}: {exc}", file=sys.stderr)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                print(f"{target.stem} seed {seed}: saved {path}")
    except ImagenError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        client.close()
    return 1 if failures else 0


def _sheet(args: argparse.Namespace) -> int:
    candidates = args.out / "candidates"
    if not candidates.is_dir():
        print("no candidates yet: run generate first", file=sys.stderr)
        return 1
    sheet = args.out / "contact_sheet.html"
    sheet.write_text(build_sheet(candidates))
    print(f"wrote {sheet}")
    return 0


def _select(args: argparse.Namespace) -> int:
    metal = None if args.metal == "-" else str(args.metal)
    if metal is not None and metal not in METALS:
        print(f"metal must be one of {', '.join(METALS)} or '-'", file=sys.stderr)
        return 2
    stem = args.art_key if metal is None else f"{args.art_key}-{metal}"
    candidate = args.out / "candidates" / stem / f"{args.candidate}.png"
    if not candidate.exists():
        print(f"no candidate {candidate}", file=sys.stderr)
        return 1
    selection = _read_selection(args.selection)
    selection[stem] = {"art_key": args.art_key, "metal": metal, "seed": args.candidate}
    args.selection.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n")
    print(f"selected {stem} seed {args.candidate}")
    return 0


def _build(args: argparse.Namespace) -> int:
    selection = _read_selection(args.selection)
    public = args.repo_root / "frontend" / "public" / "trophies"
    public.mkdir(parents=True, exist_ok=True)
    for stem, pick in sorted(selection.items()):
        candidate = args.out / "candidates" / stem / f"{pick['seed']}.png"
        if not candidate.exists():
            print(f"missing candidate {candidate}", file=sys.stderr)
            return 1
        png = candidate.read_bytes()
        (public / f"{stem}.webp").write_bytes(medallion(png, 256))
        (public / f"{stem}@128.webp").write_bytes(medallion(png, 128))
    generated = args.repo_root / "frontend" / "src" / "features" / "achievements" / "trophyArt.gen.ts"
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text(render_manifest_ts(list(selection)))
    print(f"built {len(selection)} trophies into {public}")
    return 0


def _check(args: argparse.Namespace) -> int:
    wanted = {(str(k), None if m is None else str(m)) for k, m in json.loads(args.keys.read_text())}
    have = {(t.art_key, t.metal) for t in load_manifest(args.manifest)}
    missing = sorted(wanted - have, key=lambda km: (km[0], km[1] or ""))
    for art_key, metal in missing:
        print(f"missing manifest entry: {art_key} {metal or '-'}")
    if missing:
        return 1
    print(f"all {len(wanted)} art targets are in the manifest")
    return 0


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "generate": _generate,
    "sheet": _sheet,
    "select": _select,
    "build": _build,
    "check": _check,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trophy-art", description="Sunday Clays trophy art pipeline (dev-only).")
    parser.add_argument("--out", type=Path, default=HERE / "out")
    parser.add_argument("--manifest", type=Path, default=HERE / "manifest.yaml")
    parser.add_argument("--selection", type=Path, default=HERE / "selection.json")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate", help="create candidates on imagen (resumable)")
    generate.add_argument("--only", metavar="ART_KEY")
    sub.add_parser("sheet", help="write out/contact_sheet.html")
    select = sub.add_parser("select", help="record the user's pick")
    select.add_argument("art_key")
    select.add_argument("metal", help="bronze|silver|gold|platinum|diamond, or - for a one-off")
    select.add_argument("candidate", type=int, help="the picked candidate's seed")
    build = sub.add_parser("build", help="write WebP medallions and trophyArt.gen.ts")
    build.add_argument("--repo-root", type=Path, default=HERE.parent.parent)
    check = sub.add_parser("check", help="verify the manifest covers a JSON list of [art_key, metal|null]")
    check.add_argument("keys", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 17: Run the whole tool suite with lint, types and coverage**

Run: `cd tools/trophy_art && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: PASS. Ruff and mypy are clean, every test passes, and coverage is ≥90% lines and branches (`--cov-fail-under=90` in `addopts`). If `ruff format --check` lists files, run `uv run ruff format .` and re-run.

- [ ] **Step 18: Add the CI `tools` job, then watch the config test fail**

Plan 01 T5's `ci.yml` lists its jobs as `backend`, `frontend`, `ratchet`, `docker`, `stack-config`, `e2e`, `ci-ok` and, last, `publish`. Every job runs on `ubuntu-24.04` with a `timeout-minutes`, and every `astral-sh/setup-uv` step takes `version: ${{ env.UV_VERSION }}` and `python-version: ${{ env.PYTHON_VERSION }}` from the workflow-level `env:`. The new job follows the same conventions and goes directly above `ci-ok:`. It reuses the exact pinned `actions/checkout` and `astral-sh/setup-uv` SHAs (with their `# vX.Y.Z` comments, which dependabot reads) that the `backend` job already uses. The heredoc fills them in from the file itself, so no SHA is typed by hand, and `\${{` keeps the GitHub expressions literal:

```bash
CI=.github/workflows/ci.yml
CHECKOUT=$(grep -m1 -oE 'actions/checkout@[0-9a-f]{40}( # v[0-9][0-9.]*)?' "$CI")
SETUP_UV=$(grep -m1 -oE 'astral-sh/setup-uv@[0-9a-f]{40}( # v[0-9][0-9.]*)?' "$CI")
test -n "$CHECKOUT" && test -n "$SETUP_UV" && grep -qx '  ci-ok:' "$CI"
BLOCK=$(mktemp)
cat > "$BLOCK" <<EOF
  tools:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    defaults:
      run:
        working-directory: tools/trophy_art
    steps:
      - uses: ${CHECKOUT}
        with:
          persist-credentials: false
      - uses: ${SETUP_UV}
        with:
          version: \${{ env.UV_VERSION }}
          python-version: \${{ env.PYTHON_VERSION }}
          enable-cache: true
          cache-dependency-glob: tools/trophy_art/uv.lock
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy
      - run: uv run pytest

EOF
awk -v block="$BLOCK" '$0 == "  ci-ok:" { while ((getline line < block) > 0) print line } { print }' "$CI" > "$BLOCK.ci"
cat "$BLOCK.ci" > "$CI" && rm -f "$BLOCK" "$BLOCK.ci"
grep -c -x '  tools:' "$CI"
```

Expected: the last command prints `1`, and `git diff .github/workflows/ci.yml` shows the `tools` job inserted directly above `  ci-ok:` with no other change.

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_ci_config.py -v`
Expected: FAIL. `test_ci_ok_always_runs_and_needs_every_other_job` reports that `tools` is a job but not in `jobs['ci-ok']['needs']`.

- [ ] **Step 19: Add `tools` to `ci-ok.needs` and re-run**

Plan 01 T5 writes the `ci-ok` job's list inline as `needs: [backend, frontend, ratchet, docker, stack-config, e2e]` (C11; no other task adds a job). Append `tools` to it and leave `publish` unchanged. No `if:` goes on the `tools` job:

```bash
CI=.github/workflows/ci.yml
sed -i.bak 's/^    needs: \[backend, frontend, ratchet, docker, stack-config, e2e\]$/    needs: [backend, frontend, ratchet, docker, stack-config, e2e, tools]/' "$CI" && rm "$CI.bak"
grep -n -x '    needs: \[backend, frontend, ratchet, docker, stack-config, e2e, tools\]' "$CI"
```

Expected: `grep` prints exactly one line, the `ci-ok` job's `needs:`. If it prints nothing, the `ci-ok` list differs from Plan 01's: add `, tools` before its closing `]` by hand and re-run the `grep` with that list.

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests -v`
Expected: PASS. `test_ci_config.py` confirms `set(ci-ok.needs) == set(jobs) - {ci-ok, publish}`, the checkout step keeps `persist-credentials: false`, both `uses:` values are pinned to 40-hex SHAs, and the `tools` job's uv cache (keyed on `tools/trophy_art/uv.lock`) is not saved by any other job.

- [ ] **Step 20: Write the failing frontend tests**

Create `frontend/src/features/achievements/metals.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { artManifestKey, LOCKED_STYLE, METAL_COLORS } from './metals';

describe('metals', () => {
  it('builds manifest keys with a metal suffix only for tiers', () => {
    expect(artManifestKey('clays_broken', 'gold')).toBe('clays_broken-gold');
    expect(artManifestKey('doubleheader', null)).toBe('doubleheader');
  });

  it('uses the C12 metal colours and the locked style', () => {
    expect(METAL_COLORS).toEqual({
      bronze: '#C98B5B',
      silver: '#C9D1D6',
      gold: '#E3B34A',
      platinum: '#E6EEF2',
      diamond: '#9FD8E6',
    });
    expect(LOCKED_STYLE).toEqual({ opacity: 0.35, filter: 'grayscale(1)' });
  });
});
```

Create `frontend/src/features/achievements/components/TrophyIcon.test.tsx`:

```tsx
import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../trophyArt.gen', () => ({
  trophyArt: {
    'clays_broken-gold': {
      src: '/trophies/clays_broken-gold.webp',
      src128: '/trophies/clays_broken-gold@128.webp',
    },
    doubleheader: { src: '/trophies/doubleheader.webp', src128: '/trophies/doubleheader@128.webp' },
  },
}));

import { TrophyIcon } from './TrophyIcon';

describe('TrophyIcon', () => {
  it('uses the 256 px art when the manifest has the metal variant', () => {
    const { container } = render(
      <TrophyIcon artKey="clays_broken" metal="gold" locked={false} size={256} />,
    );
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', '/trophies/clays_broken-gold.webp');
    expect(img).toHaveAttribute('width', '256');
  });

  it('uses the 128 px art at small sizes', () => {
    const { container } = render(
      <TrophyIcon artKey="clays_broken" metal="gold" locked={false} size={48} />,
    );
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/trophies/clays_broken-gold@128.webp',
    );
  });

  it('looks up one-off art without a metal suffix', () => {
    const { container } = render(
      <TrophyIcon artKey="doubleheader" metal={null} locked={false} size={64} />,
    );
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/trophies/doubleheader@128.webp',
    );
  });

  it('falls back to an SVG trophy tinted with the metal colour', () => {
    const { container } = render(
      <TrophyIcon artKey="events" metal="diamond" locked={false} size={64} />,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('svg circle')).toHaveAttribute('stroke', '#9FD8E6');
  });

  it('tints one-off fallbacks with the accent', () => {
    const { container } = render(
      <TrophyIcon artKey="rain" metal={null} locked={false} size={64} />,
    );
    expect(container.querySelector('svg circle')).toHaveAttribute('stroke', '#E8A77A');
  });

  it('greys out locked trophies whether art exists or not', () => {
    const art = render(<TrophyIcon artKey="doubleheader" metal={null} locked size={64} />);
    expect(art.container.querySelector('img')).toHaveStyle({
      opacity: '0.35',
      filter: 'grayscale(1)',
    });
    const fallback = render(<TrophyIcon artKey="rain" metal={null} locked size={64} />);
    const svg = fallback.container.querySelector('svg');
    expect(svg?.style.opacity).toBe('0.35');
    expect(svg?.style.filter).toBe('grayscale(1)');
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements`
Expected: FAIL. Vitest reports `Failed to resolve import "./metals"` and `"./TrophyIcon"`.

- [ ] **Step 21: Implement the metals, the empty art manifest and TrophyIcon**

Create `frontend/src/features/achievements/metals.ts`:

```ts
export type Metal = 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond';

/** C12 metal colours, chosen for contrast on #1A4D2E / #2D5F3F. */
export const METAL_COLORS: Record<Metal, string> = {
  bronze: '#C98B5B',
  silver: '#C9D1D6',
  gold: '#E3B34A',
  platinum: '#E6EEF2',
  diamond: '#9FD8E6',
};

/** One-off trophies have no metal; they are tinted with the theme accent. */
export const ONE_OFF_COLOR = '#E8A77A';

/** C12: locked trophies render at 35% opacity in grayscale. */
export const LOCKED_STYLE = { opacity: 0.35, filter: 'grayscale(1)' } as const;

export function artManifestKey(artKey: string, metal: Metal | null): string {
  return metal === null ? artKey : `${artKey}-${metal}`;
}
```

Create `frontend/src/features/achievements/trophyArt.gen.ts`:

```ts
// Generated by tools/trophy_art/cli.py build. Do not edit by hand.
export const trophyArt: Record<string, { src: string; src128: string }> = {};
```

Create `frontend/src/features/achievements/components/TrophyIcon.tsx`:

```tsx
import type { CSSProperties } from 'react';
import type { Metal } from '../metals';
import { artManifestKey, LOCKED_STYLE, METAL_COLORS, ONE_OFF_COLOR } from '../metals';
import { trophyArt } from '../trophyArt.gen';

export interface TrophyIconProps {
  artKey: string;
  metal: Metal | null;
  locked: boolean;
  size: number;
}

/** Trophy art from the generated manifest; an inline SVG trophy tinted by metal when art is missing. */
export function TrophyIcon({ artKey, metal, locked, size }: TrophyIconProps) {
  const style: CSSProperties | undefined = locked ? LOCKED_STYLE : undefined;
  const art = trophyArt[artManifestKey(artKey, metal)];
  if (art) {
    return (
      <img
        src={size > 128 ? art.src : art.src128}
        width={size}
        height={size}
        alt=""
        style={style}
        className="shrink-0 rounded-full"
      />
    );
  }
  const color = metal === null ? ONE_OFF_COLOR : METAL_COLORS[metal];
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
      style={style}
      className="shrink-0"
    >
      <circle cx="32" cy="32" r="30" fill="#2D5F3F" stroke={color} strokeWidth="3" />
      <path d="M22 16h20v9a10 10 0 0 1-20 0z" fill={color} />
      <path
        d="M22 19h-5a5 5 0 0 0 5 7M42 19h5a5 5 0 0 1-5 7"
        fill="none"
        stroke={color}
        strokeWidth="2.5"
      />
      <rect x="29" y="35" width="6" height="7" fill={color} />
      <rect x="23" y="42" width="18" height="5" rx="1.5" fill={color} />
    </svg>
  );
}
```

- [ ] **Step 22: Run the frontend tests to verify they pass, then the full frontend checks**

Run: `cd frontend && pnpm exec vitest run src/features/achievements`
Expected: PASS (2 files, 8 tests).

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage`
Expected: PASS with 0 eslint warnings and frontend coverage ≥90% lines and branches. If prettier reports the new files, run `pnpm exec prettier --write src/features/achievements` and re-run.

- [ ] **Step 23: Commit**

```bash
git add tools/trophy_art .github/workflows/ci.yml frontend/src/features/achievements
git commit -m "feat(trophy-art): add imagen trophy art tool, TrophyIcon fallback and CI tools job" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: Trophy art run with the user's picks (master Plan 10 T6)

**Context:** This task is **human-in-the-loop**.
- The tool from Task 6 generates candidates on the user's imagen deployment (`https://imagen.thehalf.io`). The user picks one candidate per target from a contact sheet, and the tool builds committed WebP medallions plus `trophyArt.gen.ts`.
- **Stop and wait for the user's picks; never guess them.** If `IMAGEN_USERNAME`/`IMAGEN_PASSWORD` are not already exported in your environment, stop and report `BLOCKED`. Ask the user to export them; never ask for them in chat and never write them to a file, a command line in a committed script, or a log.
- Nothing waits on this task: `TrophyIcon` falls back to SVG until the art lands.
- The only production change is data: the committed art, `selection.json`, and any missing manifest prompts. The TDD red/green applies to the repo-consistency test in Step 6.

**Branch:** `task/10-6-trophy-art-run`

**Depends on:** Plan 10 T2, T3, T4b (every art_key registered) and T5 (the tool).

**Files:**
- Modify (only if Step 1 reports gaps): `tools/trophy_art/manifest.yaml` and `tools/trophy_art/tests/test_manifest.py` (`FAMILY_METALS`/`ONE_OFFS` and the expected count).
- Modify: `tools/trophy_art/selection.json`
- Create: `tools/trophy_art/tests/test_repo_art.py`
- Create: `frontend/public/trophies/*.webp` (a 256 px and a `@128` file per selected target)
- Modify: `frontend/src/features/achievements/trophyArt.gen.ts` (generated)

**Interfaces:**
- Consumes:
  - Task 1's `registry.all_achievements()`, whose `art_key` and `tiers[].metal` define the art targets.
  - Task 6's CLI (`check`, `generate`, `sheet`, `select`, `build`) and `manifest.load_manifest`.
- Produces: committed art at `frontend/public/trophies/<stem>.webp` and `<stem>@128.webp`, and a populated `trophyArt: Record<string, { src: string; src128: string }>` keyed by `<art_key>` or `<art_key>-<metal>`. `TrophyIcon` (Task 6) and every Task 8 surface pick these up with no code change.

- [ ] **Step 1: Confirm the manifest covers every registered art target**

```bash
mkdir -p tools/trophy_art/out
(cd backend && uv run python - > ../tools/trophy_art/out/art_keys.json) <<'PY'
import json
from sunday_clays.analytics.achievements import registry

achievements = registry.all_achievements()
keys = {(a.art_key, t.metal.value) for a in achievements for t in a.tiers}
keys |= {(a.art_key, None) for a in achievements if not a.tiers}
print(json.dumps(sorted(keys, key=lambda k: (k[0], k[1] or ""))))
PY
cd tools/trophy_art && uv run python cli.py check out/art_keys.json
```

Expected: `all 62 art targets are in the manifest` and exit 0.

If it prints `missing manifest entry: …` lines instead:
- Add one `trophies:` entry per missing art_key to `manifest.yaml`. For a tiered family, list its metals. Write a one-line subject in the house style: an object on a medallion, no text.
- Add the same keys to `FAMILY_METALS`/`ONE_OFFS` in `tests/test_manifest.py` and update the `len(expected)` literal.
- Re-run `check` until it exits 0, then run `uv run pytest` in `tools/trophy_art`.

- [ ] **Step 2: Smoke-test one family against imagen**

Run: `cd tools/trophy_art && uv run python cli.py generate --only clays_broken`
Expected: exit 0 and 20 files under `out/candidates/clays_broken-{bronze,silver,gold,platinum,diamond}/{101,202,303,404}.png`. `IMAGEN_URL` defaults to `https://imagen.thehalf.io`. A `login failed` or exit 2 means the credentials are missing or wrong: stop and report `BLOCKED`.

- [ ] **Step 3: Generate every candidate**

Run the command in the background, because 62 targets × 4 seeds is a long run: `cd tools/trophy_art && uv run python cli.py generate`. It is resumable: existing PNGs are skipped, and the Idempotency-Key makes a retried POST replay the same imagen row.
Expected: exit 0 and `out/candidates/` holding 62 directories of 4 PNGs each. If it exits 1, re-run the same command to retry only the failed candidates, and repeat until exit 0.

- [ ] **Step 4: Build the contact sheet and stop for the user's picks**

Run: `cd tools/trophy_art && uv run python cli.py sheet`
Expected: `wrote …/tools/trophy_art/out/contact_sheet.html`.

**STOP.** Report status `BLOCKED` with the absolute path of `contact_sheet.html` and ask the user to choose one seed per target. Every caption shows the exact `select` command. Do not continue until the controller relays the user's 62 picks. Never pick on the user's behalf.

- [ ] **Step 5: Record every pick**

For each relayed pick, run `cd tools/trophy_art && uv run python cli.py select <art_key> <metal or -> <seed>`, for example `uv run python cli.py select clays_broken gold 303` or `uv run python cli.py select doubleheader - 101`.
Expected: each prints `selected <stem> seed <seed>`. At the end `selection.json` has one entry per target (62).

- [ ] **Step 6: Write the failing repo-consistency test**

Create `tools/trophy_art/tests/test_repo_art.py`:

```python
"""The committed art matches the committed selection (Plan 10 T6)."""

import json
import re
from pathlib import Path

from manifest import load_manifest

TOOL = Path(__file__).resolve().parents[1]
REPO = TOOL.parents[1]
GENERATED = REPO / "frontend" / "src" / "features" / "achievements" / "trophyArt.gen.ts"
PUBLIC = REPO / "frontend" / "public"
ENTRY = re.compile(
    r"""['"]?([a-z0-9_]+(?:-[a-z]+)?)['"]?:\s*\{\s*src:\s*['"]([^'"]+)['"],\s*src128:\s*['"]([^'"]+)['"],?\s*\}"""
)


def generated_entries() -> dict[str, tuple[str, str]]:
    return {m.group(1): (m.group(2), m.group(3)) for m in ENTRY.finditer(GENERATED.read_text())}


def selection() -> dict[str, dict[str, object]]:
    return json.loads((TOOL / "selection.json").read_text())


def test_every_selected_trophy_is_built():
    assert sorted(generated_entries()) == sorted(selection())


def test_every_generated_entry_points_at_committed_files():
    for stem, (src, src128) in generated_entries().items():
        assert (src, src128) == (f"/trophies/{stem}.webp", f"/trophies/{stem}@128.webp")
        assert (PUBLIC / src.lstrip("/")).is_file()
        assert (PUBLIC / src128.lstrip("/")).is_file()


def test_selection_only_names_manifest_targets():
    assert set(selection()) <= {t.stem for t in load_manifest(TOOL / "manifest.yaml")}
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd tools/trophy_art && uv run pytest tests/test_repo_art.py -v --no-cov`
Expected: FAIL. `test_every_selected_trophy_is_built` reports `[] != ['above_average_3', …]`, because `trophyArt.gen.ts` is still the empty record from Task 6.

- [ ] **Step 8: Build the art and format the generated module**

```bash
cd tools/trophy_art && uv run python cli.py build
cd ../../frontend && pnpm exec prettier --write src/features/achievements/trophyArt.gen.ts
```

Expected: `built 62 trophies into …/frontend/public/trophies`, 124 WebP files in that directory, and a prettier-formatted `trophyArt.gen.ts` with 62 entries.

- [ ] **Step 9: Run the tool suite and the frontend checks**

Run: `cd tools/trophy_art && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`
Expected: PASS. The repo-art tests are now green, and coverage stays ≥90%.

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage && pnpm build`
Expected: PASS. The WebPs live in `public/`, so they add nothing to the JS bundle budgets (`ratchets/budgets.json` covers `dist/assets/*.js` only).

- [ ] **Step 10: Commit**

```bash
git add tools/trophy_art/selection.json tools/trophy_art/tests/test_repo_art.py tools/trophy_art/manifest.yaml \
  tools/trophy_art/tests/test_manifest.py frontend/public/trophies frontend/src/features/achievements/trophyArt.gen.ts
git commit -m "feat(trophy-art): add the user's selected trophy medallions" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

`git add` of an unmodified `manifest.yaml`/`test_manifest.py` is a no-op, so the same command works whether or not Step 1 added entries.

### Task 8: Trophy Room, Trophy Case, "Trophies earned today" and "Your next trophy" UI (master Plan 10 T7)

**Context:** This task builds the achievements UI. It plugs into the app only through the C10 globs:
- `features/achievements/routes.tsx`: routes plus nav order 70.
- `profileSection.tsx`: the Trophy Case.
- `eventSection.tsx`: "Trophies earned today", which is the event page's streak and milestone notables. Plan 06 T5 and Plan 08 T1 do not re-implement them.
- `homeWidget.tsx`: "Your next trophy", slot `me`.

Never edit `features/home/`, `features/events/`, `features/shooters/` or `router.tsx`.

Rules:
- Every data chart renders inside `ChartFrame`, and each page with charts gets one Vitest asserting that every chart exposes the Table and CSV controls (C10).
- Earned trophies render in metal colours and locked ones greyed with progress bars, e.g. "1,742 / 2,500 clays broken" (spec §4).
- The e2e spec runs at both viewports against the fixtures seeded by Plan 04 T2's `auth.setup.ts`.
- Global Constraints: dark-only theme tokens, min tap target 44 px, eslint `--max-warnings 0`, frontend coverage ≥90% lines and branches.
- JSX text avoids raw `'` and `"` (lint-safe typographic quotes).

**Branch:** `task/10-7-achievements-ui`

**Depends on:**
- Plan 10 T1 (API), T2, T3, T4b (real trophies in the seeded data) and T5 (`TrophyIcon`, `metals.ts`, `trophyArt.gen.ts`).
- Plan 07 T4 (`api`, `unwrap`, `useUrlState`, `enumCodec`) and T6 (`ChartFrame`, `components/charts/types.ts`); Plan 01 T2's `app/registry.ts` (`NavItem`).
- Plan 08 T1, T2a and T4, the event, profile and home glob hosts.

**Files:**
- Create: `frontend/src/features/achievements/api.ts`
- Create: `frontend/src/features/achievements/labels.ts`
- Create: `frontend/src/features/achievements/chartOptions.ts`
- Create: `frontend/src/features/achievements/mocks.ts`
- Create: `frontend/src/features/achievements/routes.tsx`
- Create: `frontend/src/features/achievements/components/TrophyCard.tsx`
- Create: `frontend/src/features/achievements/components/ProgressBar.tsx`
- Create: `frontend/src/features/achievements/pages/TrophyRoomPage.tsx`
- Create: `frontend/src/features/achievements/pages/TrophyDetailPage.tsx`
- Create: `frontend/src/features/achievements/TrophyCase.tsx`
- Create: `frontend/src/features/achievements/profileSection.tsx`
- Create: `frontend/src/features/achievements/TrophiesToday.tsx`
- Create: `frontend/src/features/achievements/eventSection.tsx`
- Create: `frontend/src/features/achievements/NextTrophy.tsx`
- Create: `frontend/src/features/achievements/homeWidget.tsx`
- Test: `frontend/src/features/achievements/labels.test.ts`, `chartOptions.test.ts`, `routes.test.tsx`, `sections.test.tsx`, `TrophyCase.test.tsx`, `TrophiesToday.test.tsx`, `NextTrophy.test.tsx`, `pages/TrophyRoomPage.test.tsx`, `pages/TrophyDetailPage.test.tsx`
- Test: `frontend/e2e/achievements.spec.ts`

**Interfaces:**
- Consumes (exact):
  - `api` (openapi-fetch `createClient<paths>`) and `unwrap<T>(res: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T>` from `src/api/client.ts`. It receives the openapi-fetch promise and returns the data or throws `ApiError`.
  - `components` from `src/api/schema.d.ts`: schemas `AchievementsOut`, `TrophyOut`, `TrophyAwardOut`, `AchievementDetailOut`, `TrophyHolderOut`, `ShooterAchievementsOut`, `EarnedTrophyOut`, `LockedTrophyOut`, `ProgressOut`, `EventAchievementsOut`, `Category`, `Metal`.
  - `ChartFrame` from `src/components/charts/ChartFrame.tsx`, with C10 props `{title, subtitle?, option, columns, rows, csvName, ariaLabel, urlKey, zoom?}`.
  - `type TabularData` from `src/components/charts/types.ts`.
  - `ChartFrame` renders a `Card` (a region named by `title`, whose `h2` holds the title) with three buttons named exactly `Table`, `CSV` and `Fullscreen` (Plan 07 D17), so each chart adds exactly one `/table/i` and one `/csv/i` button. Its view state lives in the query key `urlKey`, so no page state reuses one (Plan 10 keys: `rarity`, `holders`, `trophytl`).
  - `useUrlState<T>(key, codec, defaultValue): [T, (next: T) => void]` and `enumCodec<T extends string>(values)` from `src/lib/useUrlState.ts` (Plan 07 T4, D13: missing or invalid → default; writing the default deletes the key; history replace).
  - The Plan 08 D5 host types, imported with `import type` only: `ProfileSection` (`src/features/shooters/sections.ts`, `Component: FC<{ shooterId: number }>`), `EventSection` (`src/features/events/sections.ts`, `Component: FC<{ date: string }>`) and `HomeWidget` (`src/features/home/widgets.ts`, `{id, order, slot: 'main' | 'me', Component: FC<{ meId: number | null }>}`). Hosts sort by `order`, then `id`, wrap each profile/event section in a `Card` titled `title`, and render `me` widgets only once a "That's me" profile has loaded (Plan 08 D5, D6).
  - `type NavItem` from `src/app/registry.ts` (`{label, path, icon: LucideIcon, order, mobileTab?, adminOnly?}`).
  - `server` from `src/test/msw/server.ts`.
  - `test`/`expect` from `e2e/fixtures.ts`; the `mobile`/`desktop` projects use the viewer storage state seeded by the `setup` project (Plan 04 T2 seeds both fixture workbooks).
  - Plan 08 routes `/shooters/:id` and `/events/:date` (the e2e spec opens them).
  - Task 6's `TrophyIcon`, `METAL_COLORS` and `ONE_OFF_COLOR`.
- Produces:
  - Routes `/achievements` (Trophy Room) and `/achievements/:code` (trophy holders), declared as the relative children `achievements` and `achievements/:code` of the `/` root (Plan 01 Decision 15, which Plan 07 D1 follows), with nav `{label: 'Trophies', path: '/achievements', icon: Trophy, order: 70}` (nav paths and links stay absolute).
  - `profileSection: ProfileSection = {id: 'trophy-case', title: 'Trophy Case', order: 60, Component: TrophyCase}`
  - `eventSection: EventSection = {id: 'trophies-today', title: 'Trophies earned today', order: 60, Component: TrophiesToday}`
  - `homeWidget: HomeWidget = {id: 'next-trophy', order: 30, slot: 'me', Component: NextTrophy}`
  - `TrophyCard({ trophy }: { trophy: TrophyOut })` in `components/TrophyCard.tsx`, which Plan 11 T5 wraps in its share card.
  - Hooks `useAchievements`, `useAchievement(code)`, `useShooterAchievements(id | null)` and `useEventAchievements(date)`. Each `queryKey` starts with the API path.
  - MSW `handlers` and exported fixtures.

- [ ] **Step 1: Write the failing unit tests for labels and chart options**

Create `frontend/src/features/achievements/labels.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { CATEGORIES, CATEGORY_LABELS, formatCount, formatPct, trophyTitle } from './labels';

describe('labels', () => {
  it('titles tier trophies with their label and one-offs with their name', () => {
    expect(trophyTitle({ name: 'Clays Broken', label: '1,000 clays broken' })).toBe(
      'Clays Broken — 1,000 clays broken',
    );
    expect(trophyTitle({ name: 'First Win', label: null })).toBe('First Win');
  });

  it('lists the categories in the backend Category order with their labels', () => {
    expect(CATEGORIES.map((c) => CATEGORY_LABELS[c])).toEqual([
      'Milestones',
      'Scoring',
      'Calendar',
      'Conditions',
      'Stations',
      'Competition',
    ]);
  });

  it('formats counts and percentages', () => {
    expect(formatCount(1742)).toBe('1,742');
    expect(formatCount(2.6)).toBe('3');
    expect(formatPct(19.56)).toBe('19.6%');
  });
});
```

Create `frontend/src/features/achievements/chartOptions.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  cumulativeByDate,
  cumulativeLineOption,
  percentFormatter,
  rarityBarOption,
} from './chartOptions';

describe('rarityBarOption', () => {
  it('plots one bar per trophy in its metal colour', () => {
    const option = rarityBarOption([
      { label: 'Clays Broken — 1,000 clays broken', rarityPct: 19.6, color: '#C9D1D6' },
      { label: 'First Win', rarityPct: 36.1, color: '#E8A77A' },
    ]);
    expect(option.yAxis).toMatchObject({
      type: 'category',
      data: ['Clays Broken — 1,000 clays broken', 'First Win'],
    });
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'bar',
        data: [
          { value: 19.6, itemStyle: { color: '#C9D1D6' } },
          { value: 36.1, itemStyle: { color: '#E8A77A' } },
        ],
      }),
    ]);
    expect(option.tooltip).not.toHaveProperty('formatter');
  });
});

describe('percentFormatter', () => {
  it('formats numbers and falls back to a dash', () => {
    expect(percentFormatter(12.345)).toBe('12.3%');
    expect(percentFormatter('x')).toBe('—');
  });
});

describe('cumulativeByDate', () => {
  it('counts per date and accumulates in date order', () => {
    expect(cumulativeByDate(['2025-01-12', '2025-01-05', '2025-01-12'])).toEqual([
      { date: '2025-01-05', total: 1 },
      { date: '2025-01-12', total: 3 },
    ]);
  });
});

describe('cumulativeLineOption', () => {
  it('draws a step line over time', () => {
    const option = cumulativeLineOption([{ date: '2025-01-05', total: 1 }], 'Holders');
    expect(option.xAxis).toMatchObject({ type: 'time' });
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'line',
        name: 'Holders',
        step: 'end',
        data: [['2025-01-05', 1]],
      }),
    ]);
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements/labels.test.ts src/features/achievements/chartOptions.test.ts`
Expected: FAIL with `Failed to resolve import "./labels"` and `"./chartOptions"`.

- [ ] **Step 2: Implement labels and chart options**

Create `frontend/src/features/achievements/labels.ts`:

```ts
import type { components } from '../../api/schema';

export type Category = components['schemas']['Category'];

export const CATEGORY_LABELS: Record<Category, string> = {
  milestone: 'Milestones',
  scoring: 'Scoring',
  calendar: 'Calendar',
  conditions: 'Conditions',
  stations: 'Stations',
  competition: 'Competition',
};

export const CATEGORIES: readonly Category[] = [
  'milestone',
  'scoring',
  'calendar',
  'conditions',
  'stations',
  'competition',
];

export function trophyTitle(trophy: { name: string; label: string | null }): string {
  return trophy.label === null ? trophy.name : `${trophy.name} — ${trophy.label}`;
}

export function formatCount(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}

export function formatPct(pct: number): string {
  return `${pct.toFixed(1)}%`;
}
```

Create `frontend/src/features/achievements/chartOptions.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { use as registerECharts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

// Registration is idempotent; it guarantees these series types whatever EChart.tsx imports.
registerECharts([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

export interface RarityBar {
  label: string;
  rarityPct: number;
  color: string;
}

export interface CumulativePoint {
  date: string;
  total: number;
}

/** Tooltip value formatter; never builds HTML from data strings (C10). */
export function percentFormatter(value: unknown): string {
  return typeof value === 'number' ? `${value.toFixed(1)}%` : '—';
}

export function rarityBarOption(bars: RarityBar[]): EChartsOption {
  return {
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', inverse: true, data: bars.map((bar) => bar.label) },
    series: [
      {
        type: 'bar',
        name: 'Rarity',
        data: bars.map((bar) => ({ value: bar.rarityPct, itemStyle: { color: bar.color } })),
      },
    ],
  };
}

export function cumulativeByDate(dates: readonly string[]): CumulativePoint[] {
  const counts = new Map<string, number>();
  for (const date of dates) counts.set(date, (counts.get(date) ?? 0) + 1);
  let total = 0;
  return [...counts.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, n]) => {
      total += n;
      return { date, total };
    });
}

export function cumulativeLineOption(points: CumulativePoint[], seriesName: string): EChartsOption {
  return {
    grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'line',
        name: seriesName,
        step: 'end',
        showSymbol: false,
        data: points.map((point) => [point.date, point.total]),
      },
    ],
  };
}
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements/labels.test.ts src/features/achievements/chartOptions.test.ts`
Expected: PASS.

- [ ] **Step 3: Add the MSW mocks (test support only)**

Create `frontend/src/features/achievements/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';

type Schemas = components['schemas'];

const claysBroken1000: Schemas['TrophyOut'] = {
  code: 'clays_broken:3',
  family: 'clays_broken',
  name: 'Clays Broken',
  description: 'Lifetime targets broken (the sum of every round’s score).',
  category: 'milestone',
  art_key: 'clays_broken',
  metal: 'silver',
  level: 3,
  threshold: 1000,
  label: '1,000 clays broken',
  repeatable: false,
  holders: 65,
  rarity_pct: 19.6,
  last_awarded: '2026-09-13',
};

export const achievementsFixture: Schemas['AchievementsOut'] = {
  n_shooters: 332,
  trophies: [
    claysBroken1000,
    {
      code: 'first_win',
      family: 'first_win',
      name: 'First Win',
      description: 'Top score of the day (ties count) with at least 5 shooters.',
      category: 'competition',
      art_key: 'first_win',
      metal: null,
      level: null,
      threshold: null,
      label: null,
      repeatable: false,
      holders: 120,
      rarity_pct: 36.1,
      last_awarded: '2026-09-13',
    },
    {
      code: 'rain',
      family: 'rain',
      name: 'Rain Shooter',
      description: 'Shot on a day with 0.02 in or more of rain between 10:00 and 12:00.',
      category: 'conditions',
      art_key: 'rain',
      metal: null,
      level: null,
      threshold: null,
      label: null,
      repeatable: false,
      holders: 0,
      rarity_pct: 0,
      last_awarded: null,
    },
  ],
  recent: [
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      code: 'clays_broken:3',
      family: 'clays_broken',
      name: 'Clays Broken',
      label: '1,000 clays broken',
      metal: 'silver',
      art_key: 'clays_broken',
      event_date: '2026-09-13',
      round_id: null,
      details: { value: 1004, threshold: 1000 },
    },
  ],
};

export const trophyDetailFixture: Schemas['AchievementDetailOut'] = {
  trophy: claysBroken1000,
  holders: [
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      shooter_status: 'member',
      first_date: '2024-05-05',
      count: 1,
      dates: ['2024-05-05'],
    },
    {
      shooter_id: 40,
      display_name: 'Yoder, Gavin',
      shooter_status: 'deceased',
      first_date: '2025-02-02',
      count: 1,
      dates: ['2025-02-02'],
    },
  ],
};

export const shooterAchievementsFixture: Schemas['ShooterAchievementsOut'] = {
  shooter_id: 12,
  display_name: 'Hadley, Ike',
  earned: [
    {
      code: 'clays_broken:1',
      family: 'clays_broken',
      name: 'Clays Broken',
      description: 'Lifetime targets broken (the sum of every round’s score).',
      category: 'milestone',
      art_key: 'clays_broken',
      metal: 'bronze',
      level: 1,
      label: '100 clays broken',
      first_date: '2023-04-02',
      count: 1,
      dates: ['2023-04-02'],
    },
    {
      code: 'welcome_back',
      family: 'welcome_back',
      name: 'Welcome Back',
      description: 'Returned after 180 or more days away.',
      category: 'calendar',
      art_key: 'welcome_back',
      metal: null,
      level: null,
      label: null,
      first_date: '2024-03-03',
      count: 2,
      dates: ['2024-03-03', '2025-04-06'],
    },
  ],
  progress: [
    {
      code: 'clays_broken',
      name: 'Clays Broken',
      description: 'Lifetime targets broken (the sum of every round’s score).',
      category: 'milestone',
      art_key: 'clays_broken',
      value: 1742,
      earned_level: 3,
      earned_metal: 'silver',
      earned_label: '1,000 clays broken',
      next_level: 4,
      next_threshold: 2500,
      next_label: '2,500 clays broken',
      next_metal: 'gold',
      fraction: 0.6968,
    },
    {
      code: 'years_active',
      name: 'Years Active',
      description: 'Distinct calendar years with at least one round.',
      category: 'milestone',
      art_key: 'years_active',
      value: 7,
      earned_level: 4,
      earned_metal: 'platinum',
      earned_label: '7 years',
      next_level: null,
      next_threshold: null,
      next_label: null,
      next_metal: null,
      fraction: 1,
    },
    {
      code: 'events',
      name: 'Events Attended',
      description: 'Sundays with at least one recorded round.',
      category: 'milestone',
      art_key: 'events',
      value: 48,
      earned_level: 3,
      earned_metal: 'bronze',
      earned_label: '25 events',
      next_level: 4,
      next_threshold: 50,
      next_label: '50 events',
      next_metal: 'bronze',
      fraction: 0.96,
    },
    {
      code: 'round_score',
      name: 'Round Score',
      description: 'Your best single round.',
      category: 'scoring',
      art_key: 'round_score',
      value: 44,
      earned_level: 3,
      earned_metal: 'silver',
      earned_label: '40 in one round',
      next_level: 4,
      next_threshold: 45,
      next_label: '45 in one round',
      next_metal: 'gold',
      fraction: 0.9778,
    },
    {
      code: 'iron_streak',
      name: 'Iron Streak',
      description:
        'Consecutive held events attended; attendance-only dates neither extend nor break it.',
      category: 'milestone',
      art_key: 'iron_streak',
      value: 2,
      earned_level: 0,
      earned_metal: null,
      earned_label: null,
      next_level: 1,
      next_threshold: 4,
      next_label: '4 straight events',
      next_metal: 'bronze',
      fraction: 0.5,
    },
  ],
  locked: [
    {
      code: 'mudder',
      name: 'Mudder',
      description: 'Broke 40 or more in the rain.',
      category: 'conditions',
      art_key: 'mudder',
      rarity_pct: 3.3,
    },
  ],
};

export const eventAchievementsFixture: Schemas['EventAchievementsOut'] = {
  event_date: '2026-09-13',
  awards: [
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      code: 'station_top_gun',
      family: 'station_top_gun',
      name: 'Station Top Gun',
      label: null,
      metal: null,
      art_key: 'station_top_gun',
      event_date: '2026-09-13',
      round_id: null,
      details: { stations: [5] },
    },
    {
      shooter_id: 7,
      display_name: 'McGinnis, Alvin',
      code: 'events:5',
      family: 'events',
      name: 'Events Attended',
      label: '100 events',
      metal: 'silver',
      art_key: 'events',
      event_date: '2026-09-13',
      round_id: null,
      details: { value: 100, threshold: 100 },
    },
  ],
};

export const handlers = [
  http.get('*/api/achievements', () => HttpResponse.json(achievementsFixture)),
  http.get('*/api/achievements/:code', () => HttpResponse.json(trophyDetailFixture)),
  http.get('*/api/shooters/:id/achievements', () => HttpResponse.json(shooterAchievementsFixture)),
  http.get('*/api/events/:date/achievements', () => HttpResponse.json(eventAchievementsFixture)),
];
```

This step writes test support only: typed fixtures and MSW handlers, no production code. The hooks in `api.ts` are production code, so each is written in the GREEN step of the tests that need it: `useAchievements` and `useAchievement` in Step 5 for Step 4's page tests, and `useShooterAchievements` and `useEventAchievements` in Step 7 for Step 6's section and widget tests, which also cover the `skipToken` path of `useShooterAchievements(null)`.

Run: `cd frontend && pnpm typecheck`
Expected: PASS. This checks every mocked path and fixture field against the generated `schema.d.ts`.

- [ ] **Step 4: Write the failing Trophy Room and trophy detail page tests**

Create `frontend/src/features/achievements/pages/TrophyRoomPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { achievementsFixture } from '../mocks';
import { TrophyRoomPage } from './TrophyRoomPage';

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/achievements" element={<TrophyRoomPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function csvControls() {
  return [
    ...screen.queryAllByRole('button', { name: /csv/i }),
    ...screen.queryAllByRole('link', { name: /csv/i }),
  ];
}

describe('TrophyRoomPage', () => {
  it('lists every trophy with holders and rarity', async () => {
    renderAt('/achievements');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Trophy Room' }),
    ).toBeInTheDocument();
    const trophies = screen.getByRole('region', { name: 'Trophies' });
    expect(within(trophies).getAllByRole('listitem')).toHaveLength(3);
    expect(
      within(trophies).getByRole('link', {
        name: /Clays Broken.*1,000 clays broken.*65 holders · 19\.6%/,
      }),
    ).toHaveAttribute('href', '/achievements/clays_broken%3A3');
  });

  it('filters trophies by the category in the URL', async () => {
    renderAt('/achievements?cat=competition');
    const trophies = await screen.findByRole('region', { name: 'Trophies' });
    expect(within(trophies).getAllByRole('listitem')).toHaveLength(1);
    expect(within(trophies).getByRole('link', { name: /First Win/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Competition' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('switches category when a chip is pressed', async () => {
    const user = userEvent.setup();
    renderAt('/achievements');
    await user.click(await screen.findByRole('button', { name: 'Conditions' }));
    const conditions = screen.getByRole('region', { name: 'Trophies' });
    expect(within(conditions).getAllByRole('listitem')).toHaveLength(1);
    expect(within(conditions).getByRole('link', { name: /Rain Shooter/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'All' }));
    expect(
      within(screen.getByRole('region', { name: 'Trophies' })).getAllByRole('listitem'),
    ).toHaveLength(3);
  });

  it('links recent unlocks to shooter profiles', async () => {
    renderAt('/achievements');
    const recent = await screen.findByRole('region', { name: 'Recent unlocks' });
    expect(within(recent).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12',
    );
  });

  it('says so when nothing has been earned yet', async () => {
    server.use(
      http.get('*/api/achievements', () =>
        HttpResponse.json({ ...achievementsFixture, recent: [] }),
      ),
    );
    renderAt('/achievements');
    expect(await screen.findByText('No trophies have been earned yet.')).toBeInTheDocument();
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderAt('/achievements');
    await screen.findByRole('heading', { level: 1, name: 'Trophy Room' });
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    expect(csvControls()).toHaveLength(1);
  });

  it('shows an error when the API fails', async () => {
    server.use(http.get('*/api/achievements', () => new HttpResponse(null, { status: 500 })));
    renderAt('/achievements');
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the Trophy Room.');
  });
});
```

Create `frontend/src/features/achievements/pages/TrophyDetailPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { trophyDetailFixture } from '../mocks';
import { TrophyDetailPage } from './TrophyDetailPage';

function renderAt(url: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/achievements/:code" element={<TrophyDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophyDetailPage', () => {
  it('shows the trophy and every holder', async () => {
    renderAt('/achievements/clays_broken%3A3');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Clays Broken' }),
    ).toBeInTheDocument();
    expect(screen.getByText('1,000 clays broken')).toBeInTheDocument();
    const holders = screen.getByRole('list', { name: 'Holders' });
    expect(within(holders).getAllByRole('listitem')).toHaveLength(2);
    expect(within(holders).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12',
    );
    expect(within(holders).getByText('In memoriam')).toBeInTheDocument();
  });

  it('requests the decoded trophy code', async () => {
    let requested = '';
    server.use(
      http.get('*/api/achievements/:code', ({ params }) => {
        requested = decodeURIComponent(String(params.code));
        return HttpResponse.json(trophyDetailFixture);
      }),
    );
    renderAt('/achievements/clays_broken%3A3');
    await screen.findByRole('heading', { level: 1, name: 'Clays Broken' });
    expect(requested).toBe('clays_broken:3');
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderAt('/achievements/clays_broken%3A3');
    await screen.findByRole('heading', { level: 1, name: 'Clays Broken' });
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    expect([
      ...screen.queryAllByRole('button', { name: /csv/i }),
      ...screen.queryAllByRole('link', { name: /csv/i }),
    ]).toHaveLength(1);
  });

  it('says so when nobody holds the trophy', async () => {
    server.use(
      http.get('*/api/achievements/:code', () =>
        HttpResponse.json({ ...trophyDetailFixture, holders: [] }),
      ),
    );
    renderAt('/achievements/clays_broken%3A3');
    expect(await screen.findByText('Nobody holds this trophy yet.')).toBeInTheDocument();
  });

  it('shows an error for an unknown trophy', async () => {
    server.use(http.get('*/api/achievements/:code', () => new HttpResponse(null, { status: 404 })));
    renderAt('/achievements/nope');
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this trophy.');
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements/pages`
Expected: FAIL with `Failed to resolve import "./TrophyRoomPage"` and `"./TrophyDetailPage"`. `../api` does not exist yet either; the tests never import it directly, so Vitest names only the missing pages, and Step 5 writes the hooks together with the pages that call them.

- [ ] **Step 5: Implement the page hooks, the shared components and the two pages**

Create `frontend/src/features/achievements/api.ts` with the two hooks the pages call (Step 7 adds the section hooks, once Step 6's tests need them):

```ts
import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';

export function useAchievements() {
  return useQuery({
    queryKey: ['/api/achievements'],
    queryFn: () => unwrap(api.GET('/api/achievements')),
  });
}

export function useAchievement(code: string) {
  return useQuery({
    queryKey: ['/api/achievements/{code}', code],
    queryFn: () => unwrap(api.GET('/api/achievements/{code}', { params: { path: { code } } })),
  });
}
```

Create `frontend/src/features/achievements/components/ProgressBar.tsx`:

```tsx
export interface ProgressBarProps {
  value: number;
  max: number;
  label: string;
}

export function ProgressBar({ value, max, label }: ProgressBarProps) {
  // Tier thresholds are >= 1; Math.max only guards against a zero max.
  const pct = Math.min(100, Math.round((value / Math.max(max, 1)) * 100));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className="h-2 w-full overflow-hidden rounded-full bg-surface"
    >
      <div className="h-2 rounded-full bg-accent" style={{ width: `${pct}%` }} />
    </div>
  );
}
```

Create `frontend/src/features/achievements/components/TrophyCard.tsx`:

```tsx
import { Link } from 'react-router';
import type { components } from '../../../api/schema';
import { formatPct } from '../labels';
import { TrophyIcon } from './TrophyIcon';

type TrophyOut = components['schemas']['TrophyOut'];

export function TrophyCard({ trophy }: { trophy: TrophyOut }) {
  return (
    <Link
      to={`/achievements/${encodeURIComponent(trophy.code)}`}
      className="flex min-h-11 items-center gap-3 rounded-xl bg-elevated p-3"
    >
      <TrophyIcon
        artKey={trophy.art_key}
        metal={trophy.metal}
        locked={trophy.holders === 0}
        size={56}
      />
      <span className="flex flex-col">
        <span className="font-medium">{trophy.name}</span>
        {trophy.label === null ? null : (
          <span className="text-sm text-text-muted">{trophy.label}</span>
        )}
        <span className="text-xs text-text-muted">
          {trophy.holders} holders · {formatPct(trophy.rarity_pct)}
        </span>
      </span>
    </Link>
  );
}
```

Create `frontend/src/features/achievements/pages/TrophyRoomPage.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { enumCodec, useUrlState } from '../../../lib/useUrlState';
import { useAchievements } from '../api';
import { rarityBarOption } from '../chartOptions';
import { TrophyCard } from '../components/TrophyCard';
import { TrophyIcon } from '../components/TrophyIcon';
import type { Category } from '../labels';
import { CATEGORIES, CATEGORY_LABELS, trophyTitle } from '../labels';
import { METAL_COLORS, ONE_OFF_COLOR } from '../metals';

type CategoryFilter = Category | 'all';

/** `?cat=<category>` (C10 URL state); absent or unknown = every category. */
const CATEGORY_FILTER = enumCodec<CategoryFilter>(['all', ...CATEGORIES]);

const RARITY_COLUMNS: TabularData['columns'] = [
  { key: 'trophy', label: 'Trophy', type: 'string' },
  { key: 'category', label: 'Category', type: 'string' },
  { key: 'holders', label: 'Holders', type: 'int' },
  { key: 'rarity_pct', label: 'Rarity %', type: 'number' },
];

function CategoryButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-11 rounded-[20px] border px-4 ${active ? 'border-accent bg-primary text-text' : 'border-outline-variant text-text-muted'}`}
    >
      {children}
    </button>
  );
}

export function TrophyRoomPage() {
  // Writing the default ('all') deletes `cat` from the URL (Plan 07 useUrlState).
  const [filter, setFilter] = useUrlState<CategoryFilter>('cat', CATEGORY_FILTER, 'all');
  const category = filter === 'all' ? null : filter;
  const { data, isPending, isError } = useAchievements();

  if (isPending) return <p role="status">Loading trophies…</p>;
  if (isError) return <p role="alert">Could not load the Trophy Room.</p>;

  const shown =
    category === null ? data.trophies : data.trophies.filter((t) => t.category === category);
  const rows: TabularData['rows'] = shown.map((t) => ({
    trophy: trophyTitle(t),
    category: CATEGORY_LABELS[t.category],
    holders: t.holders,
    rarity_pct: t.rarity_pct,
  }));
  const bars = shown.map((t) => ({
    label: trophyTitle(t),
    rarityPct: t.rarity_pct,
    color: t.metal === null ? ONE_OFF_COLOR : METAL_COLORS[t.metal],
  }));

  return (
    <div className="flex flex-col gap-4 p-4">
      <header>
        <h1 className="text-2xl font-bold">Trophy Room</h1>
        <p className="text-text-muted">
          {data.trophies.length} trophies · {data.n_shooters} shooters with at least one round
        </p>
      </header>
      <div role="group" aria-label="Filter by category" className="flex flex-wrap gap-2">
        <CategoryButton
          active={category === null}
          onClick={() => {
            setFilter('all');
          }}
        >
          All
        </CategoryButton>
        {CATEGORIES.map((c) => (
          <CategoryButton
            key={c}
            active={category === c}
            onClick={() => {
              setFilter(c);
            }}
          >
            {CATEGORY_LABELS[c]}
          </CategoryButton>
        ))}
      </div>
      <ChartFrame
        title="Rarity"
        subtitle="Share of shooters who hold each trophy"
        option={rarityBarOption(bars)}
        columns={RARITY_COLUMNS}
        rows={rows}
        csvName="trophy-rarity"
        ariaLabel="Bar chart of trophy rarity"
        urlKey="rarity"
        zoom="none"
      />
      <section aria-label="Trophies">
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((t) => (
            <li key={t.code}>
              <TrophyCard trophy={t} />
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="recent-unlocks" className="flex flex-col gap-2">
        <h2 id="recent-unlocks" className="text-lg font-medium">
          Recent unlocks
        </h2>
        {data.recent.length === 0 ? (
          <p className="text-text-muted">No trophies have been earned yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.recent.map((a) => (
              <li
                key={`${a.shooter_id}-${a.code}-${a.event_date}`}
                className="flex min-h-11 items-center gap-3"
              >
                <TrophyIcon artKey={a.art_key} metal={a.metal} locked={false} size={32} />
                <span>
                  <Link to={`/shooters/${a.shooter_id}`} className="underline">
                    {a.display_name}
                  </Link>{' '}
                  earned {trophyTitle(a)} on <time dateTime={a.event_date}>{a.event_date}</time>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
```

Create `frontend/src/features/achievements/pages/TrophyDetailPage.tsx`:

```tsx
import { Link, useParams } from 'react-router';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { useAchievement } from '../api';
import { cumulativeByDate, cumulativeLineOption } from '../chartOptions';
import { TrophyIcon } from '../components/TrophyIcon';
import { formatPct } from '../labels';

const HOLDER_COLUMNS: TabularData['columns'] = [
  { key: 'date', label: 'Date', type: 'date' },
  { key: 'holders', label: 'Holders', type: 'int' },
];

export function TrophyDetailPage() {
  const { code = '' } = useParams();
  const { data, isPending, isError } = useAchievement(code);
  if (isPending) return <p role="status">Loading trophy…</p>;
  if (isError) return <p role="alert">Could not load this trophy.</p>;
  const { trophy, holders } = data;
  const points = cumulativeByDate(holders.map((h) => h.first_date));
  return (
    <div className="flex flex-col gap-4 p-4">
      <header className="flex items-center gap-4">
        <TrophyIcon
          artKey={trophy.art_key}
          metal={trophy.metal}
          locked={trophy.holders === 0}
          size={96}
        />
        <div>
          <h1 className="text-2xl font-bold">{trophy.name}</h1>
          {trophy.label === null ? null : <p className="text-lg">{trophy.label}</p>}
          <p className="text-text-muted">{trophy.description}</p>
          <p className="text-sm text-text-muted">
            {trophy.holders} holders · {formatPct(trophy.rarity_pct)} of shooters
          </p>
        </div>
      </header>
      <ChartFrame
        title="Holders over time"
        subtitle="Cumulative number of shooters holding this trophy"
        option={cumulativeLineOption(points, 'Holders')}
        columns={HOLDER_COLUMNS}
        rows={points.map((p) => ({ date: p.date, holders: p.total }))}
        csvName={`holders-${trophy.code.replace(':', '-')}`}
        ariaLabel="Line chart of holders over time"
        urlKey="holders"
        zoom="x"
      />
      <section aria-labelledby="holders-heading" className="flex flex-col gap-2">
        <h2 id="holders-heading" className="text-lg font-medium">
          Holders
        </h2>
        {holders.length === 0 ? (
          <p className="text-text-muted">Nobody holds this trophy yet.</p>
        ) : (
          <ul aria-label="Holders" className="flex flex-col gap-1">
            {holders.map((h) => (
              <li key={h.shooter_id} className="flex min-h-11 items-center justify-between gap-2">
                <Link to={`/shooters/${h.shooter_id}`} className="underline">
                  {h.display_name}
                </Link>
                {h.shooter_status === 'deceased' ? (
                  <span className="text-xs text-text-muted">In memoriam</span>
                ) : null}
                <span className="text-sm text-text-muted">
                  <time dateTime={h.first_date}>{h.first_date}</time>
                  {h.count > 1 ? ` · ×${h.count}` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements/pages`
Expected: PASS (12 tests).

- [ ] **Step 6: Write the failing section and widget tests**

Create `frontend/src/features/achievements/TrophyCase.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { shooterAchievementsFixture } from './mocks';
import { TrophyCase } from './TrophyCase';

function renderCase() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TrophyCase shooterId={12} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophyCase', () => {
  it('shows earned trophies with repeat counts', async () => {
    renderCase();
    const region = await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    expect(within(region).getByText('Welcome Back ×2')).toBeInTheDocument();
    expect(within(region).getByText('100 clays broken')).toBeInTheDocument();
  });

  it('shows progress toward each next tier', async () => {
    renderCase();
    expect(await screen.findByText('1,742 / 2,500 clays broken')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Clays Broken progress' })).toHaveAttribute(
      'aria-valuenow',
      '1742',
    );
    expect(screen.getByText('All tiers earned')).toBeInTheDocument();
  });

  it('greys out locked one-off trophies', async () => {
    renderCase();
    expect(await screen.findByText('Mudder')).toBeInTheDocument();
    expect(screen.getByText('Broke 40 or more in the rain.')).toBeInTheDocument();
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderCase();
    await screen.findByRole('region', { name: 'Trophy case for this shooter' });
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    expect([
      ...screen.queryAllByRole('button', { name: /csv/i }),
      ...screen.queryAllByRole('link', { name: /csv/i }),
    ]).toHaveLength(1);
  });

  it('encourages a shooter without trophies', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () =>
        HttpResponse.json({ ...shooterAchievementsFixture, earned: [] }),
      ),
    );
    renderCase();
    expect(await screen.findByText(/No trophies yet/)).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () => new HttpResponse(null, { status: 500 })),
    );
    renderCase();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/achievements/TrophiesToday.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { TrophiesToday } from './TrophiesToday';

function renderToday() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TrophiesToday date="2026-09-13" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TrophiesToday', () => {
  it('lists the trophies earned at the event', async () => {
    renderToday();
    const list = await screen.findByRole('list', { name: 'Trophies earned today' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[1]).toHaveTextContent('McGinnis, Alvin — Events Attended — 100 events');
    expect(within(list).getByRole('link', { name: 'Hadley, Ike' })).toHaveAttribute(
      'href',
      '/shooters/12',
    );
  });

  it('says so when no trophy was earned', async () => {
    server.use(
      http.get('*/api/events/:date/achievements', () =>
        HttpResponse.json({ event_date: '2026-09-13', awards: [] }),
      ),
    );
    renderToday();
    expect(await screen.findByText('No trophies were earned at this event.')).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/events/:date/achievements', () => new HttpResponse(null, { status: 404 })),
    );
    renderToday();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load trophies for this event.',
    );
  });
});
```

Create `frontend/src/features/achievements/NextTrophy.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { shooterAchievementsFixture } from './mocks';
import { NextTrophy } from './NextTrophy';

function renderWidget(meId: number | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NextTrophy meId={meId} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('NextTrophy', () => {
  it('asks the viewer to pick themselves first', () => {
    renderWidget(null);
    expect(screen.getByText(/see your next trophy/)).toBeInTheDocument();
  });

  it('lists the three tiers closest to done', async () => {
    renderWidget(12);
    const region = await screen.findByRole('region', { name: 'Your next trophy' });
    const items = within(region).getAllByRole('listitem');
    expect(
      items.map(
        (item) => within(item).getByText(/Round Score|Events Attended|Clays Broken/).textContent,
      ),
    ).toEqual(['Round Score', 'Events Attended', 'Clays Broken']);
    expect(within(region).getByText('1,742 / 2,500 clays broken')).toBeInTheDocument();
  });

  it('celebrates when every tier is earned', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () =>
        HttpResponse.json({
          ...shooterAchievementsFixture,
          progress: shooterAchievementsFixture.progress.filter((p) => p.next_threshold === null),
        }),
      ),
    );
    renderWidget(12);
    expect(await screen.findByText(/Every tier earned/)).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/achievements', () => new HttpResponse(null, { status: 500 })),
    );
    renderWidget(12);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/achievements/sections.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest';
import { eventSection } from './eventSection';
import { homeWidget } from './homeWidget';
import { NextTrophy } from './NextTrophy';
import { profileSection } from './profileSection';
import { TrophiesToday } from './TrophiesToday';
import { TrophyCase } from './TrophyCase';

describe('glob exports (C10)', () => {
  it('registers the Trophy Case as a profile section', () => {
    expect(profileSection).toEqual({
      id: 'trophy-case',
      title: 'Trophy Case',
      order: 60,
      Component: TrophyCase,
    });
  });

  it('registers Trophies earned today as an event section', () => {
    expect(eventSection).toEqual({
      id: 'trophies-today',
      title: 'Trophies earned today',
      order: 60,
      Component: TrophiesToday,
    });
  });

  it('registers Your next trophy in the home me slot', () => {
    expect(homeWidget).toEqual({ id: 'next-trophy', order: 30, slot: 'me', Component: NextTrophy });
  });
});
```

Create `frontend/src/features/achievements/routes.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('achievements routes', () => {
  it('lazily registers the Trophy Room and trophy pages', async () => {
    // Relative children of the `/` root (Plan 01 Decision 15); served at /achievements[/:code].
    expect(routes.map((route) => route.path)).toEqual(['achievements', 'achievements/:code']);
    for (const route of routes) {
      const lazy = route.lazy;
      expect(typeof lazy).toBe('function');
      if (typeof lazy === 'function') {
        const loaded = await lazy();
        expect(typeof loaded.Component).toBe('function');
      }
    }
  });

  it('adds the Trophies nav item at order 70', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Trophies', path: '/achievements', order: 70 }),
    ]);
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements`
Expected: FAIL. Five files fail on their first missing module: `Failed to resolve import "./TrophyCase"`, `"./TrophiesToday"` (twice: `TrophiesToday.test.tsx` and `sections.test.tsx`), `"./NextTrophy"` and `"./routes"`. The six files from Task 6 and Steps 1–5 still pass (`Test Files  5 failed | 6 passed (11)`).

- [ ] **Step 7: Implement the section hooks, the sections, widget and routes**

Replace `frontend/src/features/achievements/api.ts` with its final version, which adds `useShooterAchievements` (Trophy Case and "Your next trophy") and `useEventAchievements` ("Trophies earned today"):

```ts
import { skipToken, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';

export function useAchievements() {
  return useQuery({
    queryKey: ['/api/achievements'],
    queryFn: () => unwrap(api.GET('/api/achievements')),
  });
}

export function useAchievement(code: string) {
  return useQuery({
    queryKey: ['/api/achievements/{code}', code],
    queryFn: () => unwrap(api.GET('/api/achievements/{code}', { params: { path: { code } } })),
  });
}

/** `null` (no "That's me" choice yet) skips the request (TanStack v5 `skipToken`). */
export function useShooterAchievements(shooterId: number | null) {
  return useQuery({
    queryKey: ['/api/shooters/{id}/achievements', shooterId],
    queryFn:
      shooterId === null
        ? skipToken
        : () =>
            unwrap(
              api.GET('/api/shooters/{id}/achievements', { params: { path: { id: shooterId } } }),
            ),
  });
}

export function useEventAchievements(date: string) {
  return useQuery({
    queryKey: ['/api/events/{date}/achievements', date],
    queryFn: () =>
      unwrap(api.GET('/api/events/{date}/achievements', { params: { path: { date } } })),
  });
}
```

Create `frontend/src/features/achievements/TrophyCase.tsx`:

```tsx
import { ChartFrame } from '../../components/charts/ChartFrame';
import type { TabularData } from '../../components/charts/types';
import { useShooterAchievements } from './api';
import { cumulativeByDate, cumulativeLineOption } from './chartOptions';
import { ProgressBar } from './components/ProgressBar';
import { TrophyIcon } from './components/TrophyIcon';
import { formatCount, trophyTitle } from './labels';

const TIMELINE_COLUMNS: TabularData['columns'] = [
  { key: 'date', label: 'Date', type: 'date' },
  { key: 'trophy', label: 'Trophy', type: 'string' },
];

export function TrophyCase({ shooterId }: { shooterId: number }) {
  const { data, isPending, isError } = useShooterAchievements(shooterId);
  if (isPending) return <p role="status">Loading trophies…</p>;
  if (isError) return <p role="alert">Could not load the trophies for this shooter.</p>;
  const timeline = data.earned
    .flatMap((earned) => earned.dates.map((date) => ({ date, trophy: trophyTitle(earned) })))
    .sort((a, b) => a.date.localeCompare(b.date));
  const points = cumulativeByDate(timeline.map((row) => row.date));
  return (
    <section aria-label="Trophy case for this shooter" className="flex flex-col gap-4">
      <h3 className="text-lg font-medium">Earned trophies</h3>
      {data.earned.length === 0 ? (
        <p className="text-text-muted">No trophies yet — they come from showing up and shooting.</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.earned.map((earned) => (
            <li
              key={earned.code}
              className="flex min-h-11 items-center gap-3 rounded-xl bg-elevated p-3"
            >
              <TrophyIcon artKey={earned.art_key} metal={earned.metal} locked={false} size={48} />
              <span className="flex flex-col">
                <span className="font-medium">
                  {earned.count > 1 ? `${earned.name} ×${earned.count}` : earned.name}
                </span>
                {earned.label === null ? null : (
                  <span className="text-sm text-text-muted">{earned.label}</span>
                )}
                <time className="text-xs text-text-muted" dateTime={earned.first_date}>
                  {earned.first_date}
                </time>
              </span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="text-lg font-medium">Next tiers</h3>
      <ul className="flex flex-col gap-3">
        {data.progress.map((p) => (
          <li key={p.code} className="flex items-center gap-3">
            <TrophyIcon
              artKey={p.art_key}
              metal={p.next_metal ?? p.earned_metal}
              locked={p.next_level !== null}
              size={40}
            />
            <span className="flex flex-1 flex-col gap-1">
              <span className="font-medium">{p.name}</span>
              {p.next_threshold === null ? (
                <span className="text-sm text-accent">All tiers earned</span>
              ) : (
                <>
                  <ProgressBar
                    value={p.value}
                    max={p.next_threshold}
                    label={`${p.name} progress`}
                  />
                  <span className="text-sm text-text-muted">
                    {formatCount(p.value)} / {p.next_label}
                  </span>
                </>
              )}
            </span>
          </li>
        ))}
      </ul>
      <h3 className="text-lg font-medium">Locked</h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {data.locked.map((locked) => (
          <li key={locked.code} className="flex min-h-11 items-center gap-3">
            <TrophyIcon artKey={locked.art_key} metal={null} locked size={32} />
            <span className="flex flex-col">
              <span>{locked.name}</span>
              <span className="text-xs text-text-muted">{locked.description}</span>
            </span>
          </li>
        ))}
      </ul>
      <ChartFrame
        title="Trophy timeline"
        subtitle="Trophies earned over time"
        option={cumulativeLineOption(points, 'Trophies')}
        columns={TIMELINE_COLUMNS}
        rows={timeline}
        csvName={`trophies-${shooterId}`}
        ariaLabel="Line chart of trophies earned over time"
        urlKey="trophytl"
        zoom="x"
      />
    </section>
  );
}
```

Create `frontend/src/features/achievements/TrophiesToday.tsx`:

```tsx
import { Link } from 'react-router';
import { useEventAchievements } from './api';
import { TrophyIcon } from './components/TrophyIcon';
import { trophyTitle } from './labels';

export function TrophiesToday({ date }: { date: string }) {
  const { data, isPending, isError } = useEventAchievements(date);
  if (isPending) return <p role="status">Loading trophies…</p>;
  if (isError) return <p role="alert">Could not load trophies for this event.</p>;
  if (data.awards.length === 0)
    return <p className="text-text-muted">No trophies were earned at this event.</p>;
  return (
    <ul aria-label="Trophies earned today" className="flex flex-col gap-2">
      {data.awards.map((award) => (
        <li key={`${award.shooter_id}-${award.code}`} className="flex min-h-11 items-center gap-3">
          <TrophyIcon artKey={award.art_key} metal={award.metal} locked={false} size={32} />
          <span>
            <Link to={`/shooters/${award.shooter_id}`} className="underline">
              {award.display_name}
            </Link>{' '}
            — {trophyTitle(award)}
          </span>
        </li>
      ))}
    </ul>
  );
}
```

Create `frontend/src/features/achievements/NextTrophy.tsx`:

```tsx
import { useShooterAchievements } from './api';
import { ProgressBar } from './components/ProgressBar';
import { TrophyIcon } from './components/TrophyIcon';
import { formatCount } from './labels';

/** Home widget (slot `me`); the host passes the per-device "That's me" id (Plan 08 D5). */
export function NextTrophy({ meId }: { meId: number | null }) {
  const { data, isPending, isError } = useShooterAchievements(meId);
  if (meId === null) {
    return (
      <p className="text-text-muted">
        Tap “That’s me” on your shooter profile to see your next trophy.
      </p>
    );
  }
  if (isPending) return <p role="status">Loading your next trophy…</p>;
  if (isError) return <p role="alert">Could not load your trophies.</p>;
  const next = data.progress
    .flatMap((p) => (p.next_threshold === null ? [] : [{ ...p, next_threshold: p.next_threshold }]))
    .sort((a, b) => b.fraction - a.fraction || a.code.localeCompare(b.code))
    .slice(0, 3);
  return (
    <section aria-label="Your next trophy" className="flex flex-col gap-3">
      <h3 className="text-lg font-medium">Your next trophy</h3>
      {next.length === 0 ? (
        <p>Every tier earned — legendary.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {next.map((p) => (
            <li key={p.code} className="flex items-center gap-3">
              <TrophyIcon artKey={p.art_key} metal={p.next_metal} locked size={40} />
              <span className="flex flex-1 flex-col gap-1">
                <span className="font-medium">{p.name}</span>
                <ProgressBar value={p.value} max={p.next_threshold} label={`${p.name} progress`} />
                <span className="text-sm text-text-muted">
                  {formatCount(p.value)} / {p.next_label}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
```

Create `frontend/src/features/achievements/profileSection.tsx`:

```tsx
import type { ProfileSection } from '../shooters/sections';
import { TrophyCase } from './TrophyCase';

export const profileSection: ProfileSection = {
  id: 'trophy-case',
  title: 'Trophy Case',
  order: 60,
  Component: TrophyCase,
};
```

Create `frontend/src/features/achievements/eventSection.tsx`:

```tsx
import type { EventSection } from '../events/sections';
import { TrophiesToday } from './TrophiesToday';

export const eventSection: EventSection = {
  id: 'trophies-today',
  title: 'Trophies earned today',
  order: 60,
  Component: TrophiesToday,
};
```

Create `frontend/src/features/achievements/homeWidget.tsx`:

```tsx
import type { HomeWidget } from '../home/widgets';
import { NextTrophy } from './NextTrophy';

export const homeWidget: HomeWidget = {
  id: 'next-trophy',
  order: 30,
  slot: 'me',
  Component: NextTrophy,
};
```

The three host types come from Plan 08 D5 (`features/shooters/sections.ts`, `features/events/sections.ts`, `features/home/widgets.ts`). They are `import type`, erased at build time (`verbatimModuleSyntax`), so no achievements module imports a host module at runtime and nothing under those folders is edited (C10); `tsc` checks each export against its host's type.

Create `frontend/src/features/achievements/routes.tsx`:

```tsx
import { Trophy } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: 'achievements',
    lazy: async () => ({ Component: (await import('./pages/TrophyRoomPage')).TrophyRoomPage }),
  },
  {
    path: 'achievements/:code',
    lazy: async () => ({ Component: (await import('./pages/TrophyDetailPage')).TrophyDetailPage }),
  },
];

export const nav: NavItem[] = [{ label: 'Trophies', path: '/achievements', icon: Trophy, order: 70 }];
```

Run: `cd frontend && pnpm exec vitest run src/features/achievements`
Expected: PASS (every achievements test file green).

- [ ] **Step 8: Write the e2e spec**

Create `frontend/e2e/achievements.spec.ts`:

```ts
import { expect, test } from './fixtures';

test('Trophy Room lists trophies and filters by category', async ({ page }) => {
  await page.goto('/achievements');
  await expect(page.getByRole('heading', { level: 1, name: 'Trophy Room' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Clays Broken.*1,000 clays broken/ })).toBeVisible();
  await page.getByRole('button', { name: 'Competition' }).click();
  await expect(page).toHaveURL(/cat=competition/);
  await expect(page.getByRole('link', { name: /First Win/ })).toBeVisible();
  await expect(page.getByRole('link', { name: /Clays Broken/ })).toHaveCount(0);
});

test('trophy page lists every holder', async ({ page }) => {
  await page.goto('/achievements/clays_broken%3A3');
  await expect(page.getByRole('heading', { level: 1, name: 'Clays Broken' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Holders' }).getByRole('listitem')).toHaveCount(65);
});

test('a holder profile shows the Trophy Case', async ({ page }) => {
  const response = await page.request.get('/api/achievements/clays_broken%3A3');
  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { holders: { shooter_id: number }[] };
  const [holder] = body.holders;
  if (!holder) throw new Error('the seeded fixtures have no clays_broken:3 holder');
  await page.goto(`/shooters/${holder.shooter_id}`);
  const trophyCase = page.getByRole('region', { name: 'Trophy case for this shooter' });
  await expect(trophyCase.getByRole('heading', { name: 'Earned trophies' })).toBeVisible();
  await expect(trophyCase.getByText(/clays broken/).first()).toBeVisible();
});

test('the event page shows trophies earned that day', async ({ page }) => {
  await page.goto('/events/2026-09-13');
  await expect(page.getByRole('list', { name: 'Trophies earned today' })).toBeVisible();
});
```

The spec uses the `setup` project's storageState and runs under both the `mobile` (390×844) and `desktop` (1440×900) projects. The seeded fixtures produce 65 `clays_broken:3` holders (Task 2 golden) and three `station_top_gun` awards on 2026-09-13 (Task 5 golden), so both counts are stable.

- [ ] **Step 9: Run the full frontend checks and the e2e spec**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage && pnpm build`
Expected: PASS with 0 eslint warnings and frontend coverage ≥90% lines and branches. The achievements pages load as lazy chunks, so the entry chunk budget is unaffected. If prettier reports files, run `pnpm exec prettier --write src/features/achievements e2e/achievements.spec.ts` and re-run.

Run the e2e spec against the compose stack: the §0 step 4a T4 recipe, run with Plan 08 D24's per-task isolation (Decision 26). Plans 08, 09 and 10 UI tasks run concurrently in global Wave 4 from separate worktrees, and every Compose stack publishes host port 8080. So this task builds its own image tag `10-7` before it takes the lock (never the shared `:ci` tags, which a concurrent worktree could rebuild under a running stack), runs Compose as its own project `sc-10-7`, and serialises its stack with the machine-wide lock directory `/tmp/sunday-clays-e2e.lock` (`mkdir` is atomic and portable; macOS has no `flock`). The machine-wide lock is held for exactly one stack lifetime; the `EXIT` trap tears the stack down and releases the lock, even when a test fails; a lock with no `docker ps --filter publish=8080` container behind it is left from a crashed run and should be `rmdir`ed. Run from the worktree root (`rm -rf secrets` deletes only this worktree's generated, gitignored dev secrets, so the known e2e passwords are used):

```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=10-7
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
rm -rf secrets && VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
(cd frontend && pnpm exec playwright install chromium)
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/achievements.spec.ts --project=mobile --project=desktop)
```

Expected: `8 passed` (4 tests × 2 viewports), plus the `setup` project; then the trap removes the stack and the lock (`ls /tmp/sunday-clays-e2e.lock` → no such file). If your shell blocks a foreground `sleep`, run the whole block as one background or monitored command and read its output when it exits. The CI `e2e` job re-runs this on the PR.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/features/achievements frontend/e2e/achievements.spec.ts
git commit -m "feat(achievements): add Trophy Room, Trophy Case, event trophies and next-trophy widget" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 9: Stations page and the stations profile section (master Plan 10 T8)

**Context:** This task builds the stations UI:
- A `features/stations` page showing difficulty over time, the era split, leaders, a shooter × station heatmap, and wind × station cells. Insufficient wind cells are greyed out and labelled with `n_events`.
- A stations `profileSection.tsx` ("where you lose targets"). It hides deltas for stations the shooter has shot fewer than 2 times.

Rules:
- Every data chart renders in `ChartFrame`, and each page with charts has a Vitest asserting that every chart exposes the Table and CSV controls (C10).
- Hooks append the global round-type filter (`rt`) to every stations request and include it in the `queryKey` (C10).
- The e2e spec runs at both viewports. With `WEATHER_ENABLED=false` it asserts the wind empty state.
- Never edit `features/shooters/` or `router.tsx`.
- Min tap target 44 px, eslint `--max-warnings 0`, frontend coverage ≥90% lines and branches.

**Branch:** `task/10-8-stations-ui`

**Depends on:** Plan 10 T4a (API), Plan 07 T4 (`api`, `unwrap`, `useRoundTypes`, `useUrlState`, `enumCodec`, `intCodec`) and T6 (`ChartFrame`), Plan 08 T2a (profile glob host, `ProfileSection`).

**Files:**
- Create: `frontend/src/features/stations/api.ts`
- Create: `frontend/src/features/stations/format.ts`
- Create: `frontend/src/features/stations/chartOptions.ts`
- Create: `frontend/src/features/stations/mocks.ts`
- Create: `frontend/src/features/stations/routes.tsx`
- Create: `frontend/src/features/stations/pages/StationsPage.tsx`
- Create: `frontend/src/features/stations/StationBreakdown.tsx`
- Create: `frontend/src/features/stations/profileSection.tsx`
- Test: `frontend/src/features/stations/format.test.ts`, `chartOptions.test.ts`, `routes.test.tsx`, `StationBreakdown.test.tsx`, `pages/StationsPage.test.tsx`
- Test: `frontend/e2e/stations.spec.ts`

**Interfaces:**
- Consumes (exact):
  - `api`/`unwrap` from `src/api/client.ts`, called as `unwrap(api.GET(...))` (Decision 20).
  - `useRoundTypes(): [RoundTypeValue[], (next: RoundTypeValue[]) => void]` from `src/lib/roundTypes.ts` (Plan 07 T4), bound to `useUrlState('rt', roundTypesCodec)`; `rt=sporting,unknown` parses to `['sporting', 'unknown']` and unknown values are dropped.
  - `components['schemas']`: `StationsOut`, `StationStatOut`, `StationDetailOut`, `StationWindCellOut`, `StationLeaderOut`, `StationEventPctOut`, `StationShooterCellOut`, `ShooterStationsOut`, `ShooterStationDeltaOut`.
  - The API paths `/api/stations` (query `era`, `round_type[]`), `/api/stations/{no}` (query `round_type[]`) and `/api/shooters/{id}/stations` (query `round_type[]`).
  - `ChartFrame` and `TabularData` (C10). `ChartFrame` renders buttons named exactly `Table`, `CSV` and `Fullscreen` and keeps its view state in the query key `urlKey` (Plan 07 D17), so no page state reuses one (Plan 10 keys: `sthit`, `sttime`, `stmatrix`, `stera`, `stwind`, `stdelta`; page keys `era`, `st`, plus the global `rt`).
  - `useUrlState<T>(key, codec, defaultValue)`, `enumCodec<T extends string>(values)` and `intCodec` from `src/lib/useUrlState.ts` (Plan 07 T4, D13).
  - `type ProfileSection` from `src/features/shooters/sections.ts` (Plan 08 D5, `import type` only; the host wraps the section in a `Card` titled `title`) and `type NavItem` from `src/app/registry.ts`.
  - Wind-band labels from Plan 06's `frames.wind_band`: `<10`, `10-20`, `20+` (the API sends them as `StationWindCellOut.band`).
  - `server` from `src/test/msw/server.ts`.
  - `test`/`expect` from `e2e/fixtures.ts`; Plan 08 route `/shooters/:id` (the e2e spec opens it).
- Produces:
  - Route `/stations`, declared as the relative child `stations` of the `/` root (Plan 01 Decision 15), with nav `{label: 'Stations', path: '/stations', icon: Target, order: 80}` (nav paths and links stay absolute).
  - `profileSection: ProfileSection = {id: 'stations', title: 'Stations', order: 70, Component: StationBreakdown}`.
  - Hooks `useStations(era)`, `useStation(no | null)` and `useShooterStations(id)`, plus `type EraSel = 'current' | 'all'`. Each reads the global filter with Plan 07's `useRoundTypes()` and puts it in the request and the `queryKey`.
  - URL params `era` (`all` or absent = current) and `st` (selected station).

- [ ] **Step 1: Write the failing format and chart-option tests**

Create `frontend/src/features/stations/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { pct, signedPoints } from './format';

describe('format', () => {
  it('formats fractions as percentages with a dash for missing values', () => {
    expect(pct(0.501931)).toBe('50.2%');
    expect(pct(0)).toBe('0.0%');
    expect(pct(null)).toBe('—');
  });

  it('formats deltas as signed percentage points', () => {
    expect(signedPoints(0.048)).toBe('+4.8 pts');
    expect(signedPoints(-0.025)).toBe('-2.5 pts');
    expect(signedPoints(0)).toBe('0.0 pts');
  });
});
```

Create `frontend/src/features/stations/chartOptions.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  ACCENT,
  deltaBarOption,
  difficultyLineOption,
  eraBarOption,
  heatmapOption,
  hitPctBarOption,
  INSUFFICIENT_COLOR,
  LOSS_COLOR,
  percentFormatter,
  pointsFormatter,
  toPct,
  windBarOption,
} from './chartOptions';

describe('station chart options', () => {
  it('converts fractions to one-decimal percentages', () => {
    expect(toPct(0.501931)).toBe(50.2);
    expect(toPct(null)).toBeNull();
    expect(percentFormatter(50.2)).toBe('50.2%');
    expect(percentFormatter([1, 2])).toBe('—');
    expect(pointsFormatter(4.8)).toBe('+4.8 pts');
    expect(pointsFormatter(-2.5)).toBe('-2.5 pts');
    expect(pointsFormatter(null)).toBe('—');
  });

  it('plots hit % per station with CI markers', () => {
    const option = hitPctBarOption([
      { station: 9, hitPct: 0.501931, ciLow: 0.432572, ciHigh: 0.571215 },
    ]);
    expect(option.xAxis).toMatchObject({ type: 'category', data: ['St 9'] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: 'bar', data: [50.2] }),
      expect.objectContaining({ type: 'line', name: '95% CI low', data: [43.3] }),
      expect.objectContaining({ type: 'line', name: '95% CI high', data: [57.1] }),
    ]);
  });

  it('draws one difficulty line per station', () => {
    const option = difficultyLineOption([
      { date: '2026-09-06', station: 9, hitPct: 0.5119 },
      { date: '2026-09-13', station: 9, hitPct: 0.4835 },
      { date: '2026-09-06', station: 4, hitPct: 0.7143 },
    ]);
    expect(option.series).toEqual([
      expect.objectContaining({ type: 'line', name: 'St 4', data: [['2026-09-06', 71.4]] }),
      expect.objectContaining({
        type: 'line',
        name: 'St 9',
        data: [
          ['2026-09-06', 51.2],
          ['2026-09-13', 48.4],
        ],
      }),
    ]);
  });

  it('maps shooter × station cells onto a heatmap grid', () => {
    const option = heatmapOption([
      { shooter: 'Yoder, Gavin', station: 4, hitPct: 0.5 },
      { shooter: 'Hadley, Ike', station: 9, hitPct: 0.857143 },
    ]);
    expect(option.yAxis).toMatchObject({ data: ['Hadley, Ike', 'Yoder, Gavin'] });
    expect(option.xAxis).toMatchObject({ data: ['St 4', 'St 9'] });
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'heatmap',
        data: [
          [0, 1, 50],
          [1, 0, 85.7],
        ],
      }),
    ]);
  });

  it('plots one bar per era', () => {
    const option = eraBarOption([
      { label: 'Original setup', hitPct: 0.5119 },
      { label: 'Since 2026-09-10', hitPct: null },
    ]);
    expect(option.series).toEqual([expect.objectContaining({ type: 'bar', data: [51.2, null] })]);
  });

  it('greys out insufficient wind cells and labels every cell with n_events', () => {
    const option = windBarOption([
      { band: '<10', hitPct: 0.72, nEvents: 6, sufficient: true },
      { band: '20+', hitPct: 0.61, nEvents: 2, sufficient: false },
    ]);
    expect(option.series).toEqual([
      expect.objectContaining({
        data: [
          expect.objectContaining({
            value: 72,
            itemStyle: { color: ACCENT, opacity: 1 },
            label: expect.objectContaining({ formatter: 'n=6 events' }),
          }),
          expect.objectContaining({
            value: 61,
            itemStyle: { color: INSUFFICIENT_COLOR, opacity: 0.6 },
            label: expect.objectContaining({ formatter: 'n=2 events (too few)' }),
          }),
        ],
      }),
    ]);
  });

  it('colours losses and gains differently', () => {
    const option = deltaBarOption([
      { station: 4, delta: 0.048 },
      { station: 9, delta: -0.025 },
    ]);
    expect(option.series).toEqual([
      expect.objectContaining({
        data: [
          { value: 4.8, itemStyle: { color: ACCENT } },
          { value: -2.5, itemStyle: { color: LOSS_COLOR } },
        ],
      }),
    ]);
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/stations`
Expected: FAIL with `Failed to resolve import "./format"` and `"./chartOptions"`.

- [ ] **Step 2: Implement format and chart options**

Create `frontend/src/features/stations/format.ts`:

```ts
export function pct(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(1)}%`;
}

export function signedPoints(value: number): string {
  const points = value * 100;
  return `${points > 0 ? '+' : ''}${points.toFixed(1)} pts`;
}
```

Create `frontend/src/features/stations/chartOptions.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { BarChart, HeatmapChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { use as registerECharts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

// Registration is idempotent; it guarantees these series types whatever EChart.tsx imports.
registerECharts([
  BarChart,
  LineChart,
  HeatmapChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export const ACCENT = '#E8A77A';
export const INSUFFICIENT_COLOR = '#8A9A90';
export const LOSS_COLOR = '#DC2626';
const TEXT = '#FEFBF6';
const GRID = { left: 8, right: 16, top: 24, bottom: 8, containLabel: true };
const PERCENT_AXIS = {
  type: 'value' as const,
  min: 0,
  max: 100,
  axisLabel: { formatter: '{value}%' },
};

export function toPct(value: number | null): number | null {
  return value === null ? null : Math.round(value * 1000) / 10;
}

/** Tooltip value formatters; they never build HTML from data strings (C10). */
export function percentFormatter(value: unknown): string {
  return typeof value === 'number' ? `${value.toFixed(1)}%` : '—';
}

export function pointsFormatter(value: unknown): string {
  return typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(1)} pts` : '—';
}

export interface StationBar {
  station: number;
  hitPct: number | null;
  ciLow: number | null;
  ciHigh: number | null;
}

export function hitPctBarOption(bars: StationBar[]): EChartsOption {
  const ciMarker = {
    symbol: 'rect',
    symbolSize: [14, 2],
    lineStyle: { width: 0 },
    itemStyle: { color: TEXT },
  };
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'category', data: bars.map((bar) => `St ${bar.station}`) },
    yAxis: PERCENT_AXIS,
    series: [
      {
        type: 'bar',
        name: 'Hit %',
        data: bars.map((bar) => toPct(bar.hitPct)),
        itemStyle: { color: ACCENT },
      },
      { type: 'line', name: '95% CI low', data: bars.map((bar) => toPct(bar.ciLow)), ...ciMarker },
      {
        type: 'line',
        name: '95% CI high',
        data: bars.map((bar) => toPct(bar.ciHigh)),
        ...ciMarker,
      },
    ],
  };
}

export interface EventPoint {
  date: string;
  station: number;
  hitPct: number;
}

export function difficultyLineOption(points: EventPoint[]): EChartsOption {
  const stations = [...new Set(points.map((p) => p.station))].sort((a, b) => a - b);
  return {
    grid: { ...GRID, bottom: 40 },
    legend: { type: 'scroll', bottom: 0 },
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'time' },
    yAxis: PERCENT_AXIS,
    series: stations.map((station) => ({
      type: 'line' as const,
      name: `St ${station}`,
      showSymbol: true,
      data: points.filter((p) => p.station === station).map((p) => [p.date, toPct(p.hitPct)]),
    })),
  };
}

export interface MatrixCell {
  shooter: string;
  station: number;
  hitPct: number;
}

export function heatmapOption(cells: MatrixCell[]): EChartsOption {
  const shooters = [...new Set(cells.map((c) => c.shooter))].sort((a, b) => a.localeCompare(b));
  const stations = [...new Set(cells.map((c) => c.station))].sort((a, b) => a - b);
  return {
    grid: { ...GRID, bottom: 56 },
    tooltip: { position: 'top' },
    xAxis: { type: 'category', data: stations.map((s) => `St ${s}`), splitArea: { show: true } },
    yAxis: { type: 'category', data: shooters, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: 100,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#4A7C59', ACCENT] },
    },
    series: [
      {
        type: 'heatmap',
        name: 'Hit %',
        data: cells.map((c) => [
          stations.indexOf(c.station),
          shooters.indexOf(c.shooter),
          toPct(c.hitPct),
        ]),
      },
    ],
  };
}

export interface EraBar {
  label: string;
  hitPct: number | null;
}

export function eraBarOption(bars: EraBar[]): EChartsOption {
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'category', data: bars.map((bar) => bar.label) },
    yAxis: PERCENT_AXIS,
    series: [
      {
        type: 'bar',
        name: 'Hit %',
        data: bars.map((bar) => toPct(bar.hitPct)),
        itemStyle: { color: ACCENT },
      },
    ],
  };
}

export interface WindCell {
  band: string;
  hitPct: number;
  nEvents: number;
  sufficient: boolean;
}

export function windBarOption(cells: WindCell[]): EChartsOption {
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'category', data: cells.map((cell) => cell.band) },
    yAxis: PERCENT_AXIS,
    series: [
      {
        type: 'bar',
        name: 'Hit %',
        data: cells.map((cell) => ({
          value: toPct(cell.hitPct),
          itemStyle: {
            color: cell.sufficient ? ACCENT : INSUFFICIENT_COLOR,
            opacity: cell.sufficient ? 1 : 0.6,
          },
          label: {
            show: true,
            position: 'top' as const,
            formatter: cell.sufficient
              ? `n=${cell.nEvents} events`
              : `n=${cell.nEvents} events (too few)`,
          },
        })),
      },
    ],
  };
}

export interface DeltaBar {
  station: number;
  delta: number;
}

export function deltaBarOption(bars: DeltaBar[]): EChartsOption {
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: pointsFormatter },
    xAxis: { type: 'category', data: bars.map((bar) => `St ${bar.station}`) },
    yAxis: { type: 'value', axisLabel: { formatter: '{value} pts' } },
    series: [
      {
        type: 'bar',
        name: 'Versus the field',
        data: bars.map((bar) => ({
          value: Math.round(bar.delta * 1000) / 10,
          itemStyle: { color: bar.delta < 0 ? LOSS_COLOR : ACCENT },
        })),
      },
    ],
  };
}
```

Run: `cd frontend && pnpm exec vitest run src/features/stations`
Expected: PASS (format and chart-option tests).

- [ ] **Step 3: Add the MSW mocks (test support only)**

Create `frontend/src/features/stations/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import type { components } from '../../api/schema';

type Schemas = components['schemas'];

const four: Schemas['StationStatOut'] = {
  station_no: 4,
  era: 0,
  era_start: null,
  hits: 184,
  n_targets: 259,
  n_rounds: 37,
  n_events: 2,
  hit_pct: 0.710425,
  ci_low: 0.644151,
  ci_high: 0.768786,
  deff: 1.291872,
  clean_rate: 0.135135,
  separator: 0.32,
  leaders: [
    {
      shooter_id: 7,
      display_name: 'McGinnis, Alvin',
      hits: 20,
      n_targets: 21,
      n_rounds: 3,
      hit_pct: 0.952381,
    },
  ],
};

const nine: Schemas['StationStatOut'] = {
  station_no: 9,
  era: 0,
  era_start: null,
  hits: 130,
  n_targets: 259,
  n_rounds: 37,
  n_events: 2,
  hit_pct: 0.501931,
  ci_low: 0.432572,
  ci_high: 0.571215,
  deff: 1.321341,
  clean_rate: 0,
  separator: 0.615142,
  leaders: [],
};

export const stationsFixture: Schemas['StationsOut'] = {
  era: 'current',
  n_events: 2,
  stations: [four, nine],
  by_event: [
    { event_date: '2026-09-06', station_no: 4, hits: 120, n_targets: 168, hit_pct: 0.714286 },
    { event_date: '2026-09-06', station_no: 9, hits: 86, n_targets: 168, hit_pct: 0.511905 },
    { event_date: '2026-09-13', station_no: 4, hits: 64, n_targets: 91, hit_pct: 0.703297 },
    { event_date: '2026-09-13', station_no: 9, hits: 44, n_targets: 91, hit_pct: 0.483516 },
  ],
  matrix: [
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      station_no: 4,
      hits: 12,
      n_targets: 14,
      hit_pct: 0.857143,
    },
    {
      shooter_id: 12,
      display_name: 'Hadley, Ike',
      station_no: 9,
      hits: 7,
      n_targets: 14,
      hit_pct: 0.5,
    },
  ],
  resets: [],
};

export const stationDetailFixture: Schemas['StationDetailOut'] = {
  station_no: 4,
  eras: [
    {
      ...four,
      era: 0,
      era_start: null,
      hits: 120,
      n_targets: 168,
      n_rounds: 24,
      n_events: 1,
      hit_pct: 0.714286,
      leaders: [],
    },
    {
      ...four,
      era: 1,
      era_start: '2026-09-10',
      hits: 64,
      n_targets: 91,
      n_rounds: 13,
      n_events: 1,
      hit_pct: 0.703297,
      leaders: [],
    },
  ],
  by_event: [
    { event_date: '2026-09-06', station_no: 4, hits: 120, n_targets: 168, hit_pct: 0.714286 },
    { event_date: '2026-09-13', station_no: 4, hits: 64, n_targets: 91, hit_pct: 0.703297 },
  ],
  leaders: four.leaders,
  wind: [
    {
      band: '<10',
      band_order: 4.2,
      hit_pct: 0.72,
      ci_low: 0.65,
      ci_high: 0.78,
      n_targets: 280,
      n_events: 6,
      sufficient: true,
    },
    {
      band: '20+',
      band_order: 22.5,
      hit_pct: 0.61,
      ci_low: 0.48,
      ci_high: 0.72,
      n_targets: 70,
      n_events: 2,
      sufficient: false,
    },
  ],
  resets: [{ station_no: 4, effective_date: '2026-09-10', note: 'New trap angle' }],
};

export const shooterStationsFixture: Schemas['ShooterStationsOut'] = {
  shooter_id: 12,
  stations: [
    {
      station_no: 4,
      hits: 12,
      n: 14,
      n_rounds: 2,
      hit_pct: 0.857143,
      field_pct: 0.710425,
      delta: 0.048,
    },
    {
      station_no: 9,
      hits: 3,
      n: 7,
      n_rounds: 1,
      hit_pct: 0.428571,
      field_pct: 0.501931,
      delta: -0.025,
    },
  ],
};

export const handlers = [
  http.get('*/api/stations', () => HttpResponse.json(stationsFixture)),
  http.get('*/api/stations/:no', ({ params }) =>
    HttpResponse.json({ ...stationDetailFixture, station_no: Number(params.no) }),
  ),
  http.get('*/api/shooters/:id/stations', () => HttpResponse.json(shooterStationsFixture)),
];
```

This step writes test support only: typed fixtures and MSW handlers, no production code. The hooks in `api.ts` are production code, so they are written in Step 5 to make Step 4's failing tests pass. Step 4's tests then drive every hook through MSW, including the `rt` pass-through, the era switch and the `skipToken` path while the overview loads.

Run: `cd frontend && pnpm typecheck`
Expected: PASS. This checks every mocked path and fixture field against the generated `schema.d.ts`.

- [ ] **Step 4: Write the failing page, profile-section and route tests**

Create `frontend/src/features/stations/pages/StationsPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { stationDetailFixture, stationsFixture } from '../mocks';
import { StationsPage } from './StationsPage';

function renderAt(url = '/stations') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/stations" element={<StationsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('StationsPage', () => {
  it('summarises every station in a table', async () => {
    renderAt();
    const row = await screen.findByRole('row', { name: /^Station 9\b/ });
    expect(row).toHaveTextContent('50.2%');
    expect(row).toHaveTextContent('43.3%–57.1%');
    expect(row).toHaveTextContent('0.62');
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderAt();
    await screen.findByText('Wind × station 4');
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(5);
    expect([
      ...screen.queryAllByRole('button', { name: /csv/i }),
      ...screen.queryAllByRole('link', { name: /csv/i }),
    ]).toHaveLength(5);
  });

  it('labels each era by the reset that started it', async () => {
    const user = userEvent.setup();
    renderAt();
    await screen.findByText('Wind × station 4');
    for (const button of screen.getAllByRole('button', { name: /table/i })) {
      await user.click(button);
    }
    expect(screen.getByText('Original setup')).toBeInTheDocument();
    expect(screen.getByText('Since 2026-09-10')).toBeInTheDocument();
  });

  it('shows dashes where a station has too little data', async () => {
    server.use(
      http.get('*/api/stations', () =>
        HttpResponse.json({
          ...stationsFixture,
          stations: stationsFixture.stations.map((s) => ({
            ...s,
            hit_pct: null,
            ci_low: null,
            ci_high: null,
            clean_rate: null,
            separator: null,
          })),
        }),
      ),
    );
    renderAt();
    const row = await screen.findByRole('row', { name: /^Station 9\b/ });
    expect(row).not.toHaveTextContent('%');
    expect(within(row).getAllByText('—')).toHaveLength(4);
  });

  it('switches the detail panel to the chosen station', async () => {
    const user = userEvent.setup();
    renderAt();
    const picker = await screen.findByRole('group', { name: 'Choose a station' });
    await user.click(within(picker).getByRole('button', { name: 'Station 9' }));
    expect(await screen.findByText('Era split — Station 9')).toBeInTheDocument();
    expect(within(picker).getByRole('button', { name: 'Station 9' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('lists station leaders with links to their profiles', async () => {
    renderAt();
    const leaders = await screen.findByRole('region', { name: 'Station 4 leaders' });
    expect(within(leaders).getByRole('link', { name: 'McGinnis, Alvin' })).toHaveAttribute(
      'href',
      '/shooters/7',
    );
  });

  it('asks the API for every era when All eras is pressed', async () => {
    const eras: (string | null)[] = [];
    server.use(
      http.get('*/api/stations', ({ request }) => {
        eras.push(new URL(request.url).searchParams.get('era'));
        return HttpResponse.json(stationsFixture);
      }),
    );
    const user = userEvent.setup();
    renderAt();
    await user.click(await screen.findByRole('button', { name: 'All eras' }));
    await waitFor(() => {
      expect(eras).toContain('all');
    });
    expect(eras[0]).toBe('current');
    await user.click(screen.getByRole('button', { name: 'Current era' }));
    expect(screen.getByRole('button', { name: 'Current era' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('passes the global round-type filter to the API', async () => {
    const seen: string[][] = [];
    server.use(
      http.get('*/api/stations', ({ request }) => {
        seen.push(new URL(request.url).searchParams.getAll('round_type'));
        return HttpResponse.json(stationsFixture);
      }),
    );
    renderAt('/stations?rt=sporting,unknown');
    await screen.findByRole('heading', { level: 1, name: 'Stations' });
    expect(seen[0]).toEqual(['sporting', 'unknown']);
  });

  it('shows the weather empty state when a station has no wind cells', async () => {
    server.use(
      http.get('*/api/stations/:no', () =>
        HttpResponse.json({ ...stationDetailFixture, wind: [], leaders: [] }),
      ),
    );
    renderAt();
    expect(await screen.findByText('No weather data for station 4 yet.')).toBeInTheDocument();
    expect(
      screen.getByText('Nobody has shot this station 3 or more times yet.'),
    ).toBeInTheDocument();
  });

  it('shows an empty state when the filter removes every station', async () => {
    server.use(
      http.get('*/api/stations', () =>
        HttpResponse.json({ ...stationsFixture, stations: [], n_events: 0 }),
      ),
    );
    renderAt();
    expect(await screen.findByText('No station data for this filter.')).toBeInTheDocument();
  });

  it('shows an error when the station detail fails', async () => {
    server.use(http.get('*/api/stations/:no', () => new HttpResponse(null, { status: 500 })));
    renderAt();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load station 4.');
  });

  it('shows an error when the API fails', async () => {
    server.use(http.get('*/api/stations', () => new HttpResponse(null, { status: 500 })));
    renderAt();
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load station data.');
  });
});
```

Create `frontend/src/features/stations/StationBreakdown.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { shooterStationsFixture } from './mocks';
import { profileSection } from './profileSection';
import { StationBreakdown } from './StationBreakdown';

function renderBreakdown() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StationBreakdown shooterId={12} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('StationBreakdown', () => {
  it('shows deltas only for stations shot at least twice', async () => {
    renderBreakdown();
    expect(await screen.findByRole('row', { name: /^Station 4\b/ })).toHaveTextContent('+4.8 pts');
    const nine = screen.getByRole('row', { name: /^Station 9\b/ });
    expect(nine).toHaveTextContent('—');
    expect(nine).not.toHaveTextContent('pts');
  });

  it('exposes Table and CSV controls on every chart', async () => {
    renderBreakdown();
    await screen.findByRole('region', { name: 'Station breakdown for this shooter' });
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(1);
    expect([
      ...screen.queryAllByRole('button', { name: /csv/i }),
      ...screen.queryAllByRole('link', { name: /csv/i }),
    ]).toHaveLength(1);
  });

  it('explains when no station has two rounds yet', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({
          ...shooterStationsFixture,
          stations: shooterStationsFixture.stations.filter((s) => s.n_rounds < 2),
        }),
      ),
    );
    renderBreakdown();
    expect(
      await screen.findByText('Deltas appear once a station has been shot at least twice.'),
    ).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: /table/i })).toHaveLength(0);
  });

  it('says so when the shooter has no station sheets', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () =>
        HttpResponse.json({ shooter_id: 12, stations: [] }),
      ),
    );
    renderBreakdown();
    expect(await screen.findByText('No station sheets for this shooter yet.')).toBeInTheDocument();
  });

  it('shows an error when the API fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/stations', () => new HttpResponse(null, { status: 500 })),
    );
    renderBreakdown();
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not load the station breakdown.',
    );
  });

  it('registers as a profile section (C10)', () => {
    expect(profileSection).toEqual({
      id: 'stations',
      title: 'Stations',
      order: 70,
      Component: StationBreakdown,
    });
  });
});
```

Create `frontend/src/features/stations/routes.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('stations routes', () => {
  it('lazily registers the stations page', async () => {
    // A relative child of the `/` root (Plan 01 Decision 15); served at /stations.
    expect(routes.map((route) => route.path)).toEqual(['stations']);
    const lazy = routes[0]?.lazy;
    expect(typeof lazy).toBe('function');
    if (typeof lazy === 'function') {
      const loaded = await lazy();
      expect(typeof loaded.Component).toBe('function');
    }
  });

  it('adds the Stations nav item at order 80', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Stations', path: '/stations', order: 80 }),
    ]);
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/stations`
Expected: FAIL. Three files fail on their first missing module: `Failed to resolve import "./StationsPage"`, `"./profileSection"` (`StationBreakdown.test.tsx` imports it before `./StationBreakdown`) and `"./routes"`. The format and chart-option files still pass (`Test Files  3 failed | 2 passed (5)`). `./api` does not exist yet either; the tests never import it directly, so Vitest names only the missing modules, and Step 5 writes the hooks together with the page and section that call them.

- [ ] **Step 5: Implement the API hooks, the page, the profile section and the routes**

Create `frontend/src/features/stations/api.ts`:

```ts
import { keepPreviousData, skipToken, useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { useRoundTypes } from '../../lib/roundTypes';

export type EraSel = 'current' | 'all';

// `useRoundTypes()` is Plan 07 T4's global filter (C10 `rt` param, parsed by `roundTypesCodec`,
// unknown values dropped). Its value goes into every request and every queryKey (C10).

export function useStations(era: EraSel) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/stations', era, roundTypes],
    queryFn: () =>
      unwrap(api.GET('/api/stations', { params: { query: { era, round_type: roundTypes } } })),
    // Switching era keeps the previous overview on screen instead of a loading flash.
    placeholderData: keepPreviousData,
  });
}

/** `null` (overview still loading) skips the request (TanStack v5 `skipToken`). */
export function useStation(stationNo: number | null) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/stations/{no}', stationNo, roundTypes],
    queryFn:
      stationNo === null
        ? skipToken
        : () =>
            unwrap(
              api.GET('/api/stations/{no}', {
                params: { path: { no: stationNo }, query: { round_type: roundTypes } },
              }),
            ),
  });
}

export function useShooterStations(shooterId: number) {
  const [roundTypes] = useRoundTypes();
  return useQuery({
    queryKey: ['/api/shooters/{id}/stations', shooterId, roundTypes],
    queryFn: () =>
      unwrap(
        api.GET('/api/shooters/{id}/stations', {
          params: { path: { id: shooterId }, query: { round_type: roundTypes } },
        }),
      ),
  });
}
```

Create `frontend/src/features/stations/pages/StationsPage.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import type { components } from '../../../api/schema';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { TabularData } from '../../../components/charts/types';
import { enumCodec, intCodec, useUrlState } from '../../../lib/useUrlState';
import type { EraSel } from '../api';
import { useStation, useStations } from '../api';
import {
  difficultyLineOption,
  eraBarOption,
  heatmapOption,
  hitPctBarOption,
  windBarOption,
} from '../chartOptions';
import { pct } from '../format';

type StationStatOut = components['schemas']['StationStatOut'];
type StationDetailOut = components['schemas']['StationDetailOut'];

/** `?era=all` (absent = current) and `?st=<station_no>` (C10 URL state; invalid → default). */
const ERA_CODEC = enumCodec<EraSel>(['current', 'all']);
const NO_STATION = 0;

const STATION_COLUMNS: TabularData['columns'] = [
  { key: 'station', label: 'Station', type: 'int' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'ci_low', label: '95% CI low', type: 'number' },
  { key: 'ci_high', label: '95% CI high', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
  { key: 'n_rounds', label: 'Rounds', type: 'int' },
  { key: 'n_events', label: 'Events', type: 'int' },
];
const EVENT_COLUMNS: TabularData['columns'] = [
  { key: 'date', label: 'Event', type: 'date' },
  { key: 'station', label: 'Station', type: 'int' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
];
const MATRIX_COLUMNS: TabularData['columns'] = [
  { key: 'shooter', label: 'Shooter', type: 'string' },
  { key: 'station', label: 'Station', type: 'int' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
];
const ERA_COLUMNS: TabularData['columns'] = [
  { key: 'era', label: 'Era', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_targets', label: 'Targets', type: 'int' },
  { key: 'n_events', label: 'Events', type: 'int' },
];
const WIND_COLUMNS: TabularData['columns'] = [
  { key: 'band', label: 'Gust band', type: 'string' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'n_events', label: 'Events', type: 'int' },
  { key: 'sufficient', label: 'Enough events', type: 'string' },
];

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-11 rounded-[20px] border px-4 ${active ? 'border-accent bg-primary text-text' : 'border-outline-variant text-text-muted'}`}
    >
      {children}
    </button>
  );
}

function eraLabel(stat: StationStatOut): string {
  return stat.era_start === null ? 'Original setup' : `Since ${stat.era_start}`;
}

function SummaryTable({ stations }: { stations: StationStatOut[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Station summary</caption>
        <thead>
          <tr>
            <th scope="col">Station</th>
            <th scope="col">Hit %</th>
            <th scope="col">95% CI</th>
            <th scope="col">Clean rate</th>
            <th scope="col">Rounds</th>
            <th scope="col">Events</th>
            <th scope="col">Separator</th>
          </tr>
        </thead>
        <tbody>
          {stations.map((s) => (
            <tr key={s.station_no}>
              <th scope="row">Station {s.station_no}</th>
              <td>{pct(s.hit_pct)}</td>
              <td>
                {s.ci_low === null || s.ci_high === null
                  ? '—'
                  : `${pct(s.ci_low)}–${pct(s.ci_high)}`}
              </td>
              <td>{pct(s.clean_rate)}</td>
              <td>{s.n_rounds}</td>
              <td>{s.n_events}</td>
              <td>{s.separator === null ? '—' : s.separator.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StationDetail({ detail }: { detail: StationDetailOut }) {
  const no = detail.station_no;
  return (
    <div className="flex flex-col gap-4">
      <ChartFrame
        title={`Era split — Station ${no}`}
        subtitle="Hit % in each era between logged station resets"
        option={eraBarOption(detail.eras.map((e) => ({ label: eraLabel(e), hitPct: e.hit_pct })))}
        columns={ERA_COLUMNS}
        rows={detail.eras.map((e) => ({
          era: eraLabel(e),
          hit_pct: e.hit_pct,
          n_targets: e.n_targets,
          n_events: e.n_events,
        }))}
        csvName={`station-${no}-eras`}
        ariaLabel={`Bar chart of station ${no} hit % by era`}
        urlKey="stera"
        zoom="none"
      />
      {detail.wind.length === 0 ? (
        <p className="text-text-muted">No weather data for station {no} yet.</p>
      ) : (
        <ChartFrame
          title={`Wind × station ${no}`}
          subtitle="Hit % by gust band; grey bars have fewer than 5 events"
          option={windBarOption(
            detail.wind.map((w) => ({
              band: w.band,
              hitPct: w.hit_pct,
              nEvents: w.n_events,
              sufficient: w.sufficient,
            })),
          )}
          columns={WIND_COLUMNS}
          rows={detail.wind.map((w) => ({
            band: w.band,
            hit_pct: w.hit_pct,
            n_events: w.n_events,
            sufficient: w.sufficient ? 'yes' : 'no',
          }))}
          csvName={`station-${no}-wind`}
          ariaLabel={`Bar chart of station ${no} hit % by gust band`}
          urlKey="stwind"
          zoom="none"
        />
      )}
      <section aria-labelledby="station-leaders" className="flex flex-col gap-2">
        <h3 id="station-leaders" className="font-medium">
          Station {no} leaders
        </h3>
        {detail.leaders.length === 0 ? (
          <p className="text-text-muted">Nobody has shot this station 3 or more times yet.</p>
        ) : (
          <ol className="flex flex-col gap-1">
            {detail.leaders.map((leader) => (
              <li
                key={leader.shooter_id}
                className="flex min-h-11 items-center justify-between gap-2"
              >
                <Link to={`/shooters/${leader.shooter_id}`} className="underline">
                  {leader.display_name}
                </Link>
                <span className="text-sm text-text-muted">
                  {pct(leader.hit_pct)} · {leader.n_rounds} rounds
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export function StationsPage() {
  const [era, setEra] = useUrlState<EraSel>('era', ERA_CODEC, 'current');
  const [requested, setRequested] = useUrlState('st', intCodec, NO_STATION);
  const overview = useStations(era);
  const stationNos = overview.data?.stations.map((s) => s.station_no) ?? [];
  const selected = stationNos.includes(requested) ? requested : (stationNos[0] ?? null);
  const detail = useStation(selected);

  if (overview.isPending) return <p role="status">Loading stations…</p>;
  if (overview.isError) return <p role="alert">Could not load station data.</p>;
  const data = overview.data;

  return (
    <div className="flex flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Stations</h1>
        <div role="group" aria-label="Era" className="flex gap-2">
          <ToggleButton
            active={era === 'current'}
            onClick={() => {
              setEra('current');
            }}
          >
            Current era
          </ToggleButton>
          <ToggleButton
            active={era === 'all'}
            onClick={() => {
              setEra('all');
            }}
          >
            All eras
          </ToggleButton>
        </div>
      </header>
      {data.stations.length === 0 ? (
        <p className="text-text-muted">No station data for this filter.</p>
      ) : (
        <>
          <SummaryTable stations={data.stations} />
          <ChartFrame
            title="Hit % by station"
            subtitle="Station-sheet hits over targets, with 95% intervals"
            option={hitPctBarOption(
              data.stations.map((s) => ({
                station: s.station_no,
                hitPct: s.hit_pct,
                ciLow: s.ci_low,
                ciHigh: s.ci_high,
              })),
            )}
            columns={STATION_COLUMNS}
            rows={data.stations.map((s) => ({
              station: s.station_no,
              hit_pct: s.hit_pct,
              ci_low: s.ci_low,
              ci_high: s.ci_high,
              n_targets: s.n_targets,
              n_rounds: s.n_rounds,
              n_events: s.n_events,
            }))}
            csvName="station-hit-pct"
            ariaLabel="Bar chart of hit % by station"
            urlKey="sthit"
            zoom="none"
          />
          <ChartFrame
            title="Difficulty over time"
            subtitle="Hit % per station at each event; lower is harder"
            option={difficultyLineOption(
              data.by_event.map((e) => ({
                date: e.event_date,
                station: e.station_no,
                hitPct: e.hit_pct,
              })),
            )}
            columns={EVENT_COLUMNS}
            rows={data.by_event.map((e) => ({
              date: e.event_date,
              station: e.station_no,
              hit_pct: e.hit_pct,
              n_targets: e.n_targets,
            }))}
            csvName="station-difficulty"
            ariaLabel="Line chart of station hit % over time"
            urlKey="sttime"
            zoom="x"
          />
          <ChartFrame
            title="Shooter × station"
            subtitle="Each shooter’s hit % at each station"
            option={heatmapOption(
              data.matrix.map((c) => ({
                shooter: c.display_name,
                station: c.station_no,
                hitPct: c.hit_pct,
              })),
            )}
            columns={MATRIX_COLUMNS}
            rows={data.matrix.map((c) => ({
              shooter: c.display_name,
              station: c.station_no,
              hit_pct: c.hit_pct,
              n_targets: c.n_targets,
            }))}
            csvName="shooter-station-matrix"
            ariaLabel="Heatmap of hit % by shooter and station"
            urlKey="stmatrix"
            zoom="none"
          />
          <section aria-labelledby="station-detail-heading" className="flex flex-col gap-3">
            <h2 id="station-detail-heading" className="text-lg font-medium">
              Station detail
            </h2>
            <div role="group" aria-label="Choose a station" className="flex flex-wrap gap-2">
              {stationNos.map((no) => (
                <ToggleButton
                  key={no}
                  active={no === selected}
                  onClick={() => {
                    setRequested(no);
                  }}
                >
                  Station {no}
                </ToggleButton>
              ))}
            </div>
            {detail.isPending ? (
              <p role="status">Loading station {selected}…</p>
            ) : detail.isError ? (
              <p role="alert">Could not load station {selected}.</p>
            ) : (
              <StationDetail detail={detail.data} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
```

`<section aria-labelledby="station-leaders">` gives the leaders block the accessible region name "Station N leaders", which the page test uses.

Create `frontend/src/features/stations/StationBreakdown.tsx`:

```tsx
import { ChartFrame } from '../../components/charts/ChartFrame';
import type { TabularData } from '../../components/charts/types';
import { useShooterStations } from './api';
import { deltaBarOption } from './chartOptions';
import { pct, signedPoints } from './format';

const DELTA_COLUMNS: TabularData['columns'] = [
  { key: 'station', label: 'Station', type: 'int' },
  { key: 'hit_pct', label: 'Hit %', type: 'number' },
  { key: 'field_pct', label: 'Field hit %', type: 'number' },
  { key: 'delta', label: 'Versus field', type: 'number' },
  { key: 'rounds', label: 'Rounds', type: 'int' },
];

export function StationBreakdown({ shooterId }: { shooterId: number }) {
  const { data, isPending, isError } = useShooterStations(shooterId);
  if (isPending) return <p role="status">Loading station breakdown…</p>;
  if (isError) return <p role="alert">Could not load the station breakdown.</p>;
  const shown = data.stations.filter((s) => s.n_rounds >= 2);
  return (
    <section aria-label="Station breakdown for this shooter" className="flex flex-col gap-3">
      {data.stations.length === 0 ? (
        <p className="text-text-muted">No station sheets for this shooter yet.</p>
      ) : (
        <>
          {shown.length === 0 ? (
            <p className="text-text-muted">
              Deltas appear once a station has been shot at least twice.
            </p>
          ) : (
            <ChartFrame
              title="Where you lose targets"
              subtitle="Shrunken hit % minus the field’s on the same days, in percentage points"
              option={deltaBarOption(shown.map((s) => ({ station: s.station_no, delta: s.delta })))}
              columns={DELTA_COLUMNS}
              rows={shown.map((s) => ({
                station: s.station_no,
                hit_pct: s.hit_pct,
                field_pct: s.field_pct,
                delta: s.delta,
                rounds: s.n_rounds,
              }))}
              csvName={`shooter-${data.shooter_id}-stations`}
              ariaLabel="Bar chart of station hit % versus the field"
              urlKey="stdelta"
              zoom="none"
            />
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Station hit % for this shooter</caption>
              <thead>
                <tr>
                  <th scope="col">Station</th>
                  <th scope="col">Hit %</th>
                  <th scope="col">Field</th>
                  <th scope="col">Versus field</th>
                  <th scope="col">Rounds</th>
                </tr>
              </thead>
              <tbody>
                {data.stations.map((s) => (
                  <tr key={s.station_no}>
                    <th scope="row">Station {s.station_no}</th>
                    <td>{pct(s.hit_pct)}</td>
                    <td>{pct(s.field_pct)}</td>
                    <td>{s.n_rounds >= 2 ? signedPoints(s.delta) : '—'}</td>
                    <td>{s.n_rounds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
```

Create `frontend/src/features/stations/profileSection.tsx`:

```tsx
import type { ProfileSection } from '../shooters/sections';
import { StationBreakdown } from './StationBreakdown';

export const profileSection: ProfileSection = {
  id: 'stations',
  title: 'Stations',
  order: 70,
  Component: StationBreakdown,
};
```

`ProfileSection` is Plan 08 D5's host type (`import type`, erased at build time, so nothing under `features/shooters/` is imported at runtime or edited).

Create `frontend/src/features/stations/routes.tsx`:

```tsx
import { Target } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: 'stations',
    lazy: async () => ({ Component: (await import('./pages/StationsPage')).StationsPage }),
  },
];

export const nav: NavItem[] = [{ label: 'Stations', path: '/stations', icon: Target, order: 80 }];
```

Run: `cd frontend && pnpm exec vitest run src/features/stations`
Expected: PASS (every stations test file green).

- [ ] **Step 6: Write the e2e spec**

Create `frontend/e2e/stations.spec.ts`:

```ts
import { expect, test } from './fixtures';

test('stations page summarises every station', async ({ page }) => {
  await page.goto('/stations');
  await expect(page.getByRole('heading', { level: 1, name: 'Stations' })).toBeVisible();
  await expect(page.getByRole('row', { name: /^Station 9\b/ })).toContainText('50.2%');
  await expect(page.getByText('Hit % by station').first()).toBeVisible();
});

test('the era toggle is kept in the URL', async ({ page }) => {
  await page.goto('/stations');
  await page.getByRole('button', { name: 'All eras' }).click();
  await expect(page).toHaveURL(/era=all/);
  await expect(page.getByRole('row', { name: /^Station 9\b/ })).toContainText('50.2%');
});

test('station detail shows the weather empty state', async ({ page }) => {
  await page.goto('/stations');
  await page
    .getByRole('group', { name: 'Choose a station' })
    .getByRole('button', { name: 'Station 9' })
    .click();
  await expect(page).toHaveURL(/st=9/);
  await expect(page.getByText('No weather data for station 9 yet.')).toBeVisible();
});

test('a profile shows where the shooter loses targets', async ({ page }) => {
  const response = await page.request.get('/api/stations');
  expect(response.ok()).toBe(true);
  const body = (await response.json()) as { matrix: { shooter_id: number }[] };
  const [cell] = body.matrix;
  if (!cell) throw new Error('the seeded fixtures have no station matrix');
  await page.goto(`/shooters/${cell.shooter_id}`);
  await expect(
    page.getByRole('region', { name: 'Station breakdown for this shooter' }),
  ).toBeVisible();
});
```

The seeded station fixture gives station 9 a hit rate of 130/259 = 50.2% (Task 4 golden). `WEATHER_ENABLED=false` in `compose.test.yaml`, so the wind section always shows its empty state in e2e.

- [ ] **Step 7: Run the full frontend checks and the e2e spec**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage && pnpm build`
Expected: PASS with 0 eslint warnings and frontend coverage ≥90% lines and branches. The stations page is a lazy chunk, so the entry budget is unaffected. If prettier reports files, run `pnpm exec prettier --write src/features/stations e2e/stations.spec.ts` and re-run.

Run the e2e spec against the compose stack: the §0 step 4a T4 recipe, run with Plan 08 D24's per-task isolation (Decision 26). This task runs concurrently with the other Wave 4 UI tasks of Plans 08, 09 and 10 from separate worktrees, and every Compose stack publishes host port 8080. So it builds its own image tag `10-8` before it takes the lock (never the shared `:ci` tags, which a concurrent worktree could rebuild under a running stack), runs Compose as its own project `sc-10-8`, and serialises its stack with the machine-wide lock directory `/tmp/sunday-clays-e2e.lock` (`mkdir` is atomic and portable; macOS has no `flock`). The machine-wide lock is held for exactly one stack lifetime; the `EXIT` trap tears the stack down and releases the lock, even when a test fails; a lock with no `docker ps --filter publish=8080` container behind it is left from a crashed run and should be `rmdir`ed. Run from the worktree root (`rm -rf secrets` deletes only this worktree's generated, gitignored dev secrets, so the known e2e passwords are used):

```bash
ROOT="$(git rev-parse --show-toplevel)" && cd "$ROOT"
TAG=10-8
dc() { docker compose -p "sc-$TAG" -f "$ROOT/compose.yaml" -f "$ROOT/compose.test.yaml" "$@"; }
docker build -t "ghcr.io/gitgat/sunday-clays-backend:$TAG" backend
docker build -t "ghcr.io/gitgat/sunday-clays-frontend:$TAG" -f frontend/Dockerfile .
rm -rf secrets && VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
(cd frontend && pnpm exec playwright install chromium)
until mkdir /tmp/sunday-clays-e2e.lock 2>/dev/null; do sleep 5; done
trap 'dc down -v; rmdir /tmp/sunday-clays-e2e.lock' EXIT
IMAGE_TAG="$TAG" dc up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/stations.spec.ts --project=mobile --project=desktop)
```

Expected: `8 passed` (4 tests × 2 viewports), plus the `setup` project; then the trap removes the stack and the lock (`ls /tmp/sunday-clays-e2e.lock` → no such file). If your shell blocks a foreground `sleep`, run the whole block as one background or monitored command and read its output when it exits. The CI `e2e` job re-runs this on the PR.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/stations frontend/e2e/stations.spec.ts
git commit -m "feat(stations): add stations page with eras, heatmap and wind cells plus profile deltas" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
