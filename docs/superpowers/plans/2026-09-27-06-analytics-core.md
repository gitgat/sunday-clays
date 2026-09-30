# Analytics Core & Read APIs Implementation Plan (Plan 06)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Every implementer and reviewer runs on Opus (master Global Constraints). Each task is one branch/worktree/PR;
> the task text is self-contained because the SDD task-brief script hands an implementer only its own task.

**Goal:** Turn the rebuilt live tables into analytics: memoized DataFrame loaders, field metrics (best round, min-rank,
percentile), the dynamic Gaussian skill model with calibration and predictions, classes, streaks, cohorts, shooter and
club insights, plus every Plan 06 read endpoint (`/api/meta`, events, shooters, insights, club) behind a
data_version-aware ETag/Cache-Control middleware.

**Architecture:** Pure pandas/numpy functions in `sunday_clays/analytics/` operate on frames produced by
`analytics/frames.py` loaders (SQL `text()` over the C4 tables, memoized per `data_version` by `analytics/cache.py`).
Two recompute steps (`s10_metrics`, `s30_skill`) write `round_metrics`, `event_metrics`, `rating_history` and
`app_state.skill_*`; read routes in `api/routes/` compose cached frames with pure functions and return typed `*Out`
models; `api/etag.py` adds Cache-Control on every `/api` response and weak ETags/304s on eligible GETs.

**Tech Stack:** Python 3.13 · FastAPI (Starlette `BaseHTTPMiddleware`) · SQLAlchemy 2 Core `text()` · psycopg 3 ·
pandas 3 · numpy 2 · pytest + pytest-cov + testcontainers (Postgres 17) · ruff · mypy --strict (pandas-stubs).

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

## Review Focus
1. **Ties and multi-round days** in ranks, leaderboards, season points and achievements → shared "min" rank, best-round rule (exactly one best round per (event_date, shooter_id), also across merged aliases), deterministic ordering (score desc, then name_key, then ordinal). Owner: Plan 06 Task 2 (`test_ties_share_min_rank`, `test_best_round_used_for_rank`, `test_merged_aliases_same_day_single_best_round`) and Plan 09 Task 2 (`test_tied_finish_shares_points`).
2. **Stale memo inside one recompute run** — `run_pipeline` bumps `data_version` only after all steps, so a later step (s30 after s10, Plan 10's s50 reading s30's `mu_before`) must never read a memoized pre-write frame → every Plan 06 step clears the memo before reading and after writing. Owner: Task 2 (`test_s10_leaves_no_stale_memo`), Task 4 (`test_s30_leaves_no_stale_memo`).
3. **Stale or wrong 304s** — after a rebuild, an app upgrade or midnight the ETag must change; auth/admin responses are never cached; a 401/404 never becomes a 304; 403/413 middleware rejections still carry Cache-Control. Owner: Task 1 (`test_data_version_bump_changes_etag`, `test_app_version_change_changes_etag`, `test_local_date_change_changes_etag`, `test_me_after_logout_is_401_not_304`, `test_401_is_never_turned_into_304`, `test_middleware_rejections_still_get_cache_control`).
4. **Empty slices** — an attendance-only event, a shooter whose rounds are all filtered out by `round_type`, or empty live tables return empty lists / `null` fields, never a 500. Owner: Task 5 (`test_event_detail_attendance_only`), Task 6 (`test_round_type_filter_restricts_rounds`, `round_type=unknown` case), Task 2 (`test_s10_on_empty_live_tables`), Task 4 (`test_s30_on_empty_live_tables`).
5. **Time-machine leakage** — every `as_of`/date-sliced result is identical whether or not later events exist. Owner: Task 3 (`test_no_leak_fixed_params`), Task 4 (`test_classes_no_leak`), Task 6 (`test_as_of_limits_and_no_leak`), Task 8 (`test_insights_no_leak`), Task 9 (`test_regulars_no_leak`, `test_trends_no_leak`).

## Decisions
Choices made where the master is silent (for cross-plan auditors):
1. **Modules beyond C1:** `api/etag.py` (`CacheHeadersMiddleware`; C8 says only "ETag middleware (Plan 06 T1)"), `api/routes/meta.py` (C8 lists `GET /api/meta` for Plan 06; C1 names no module) and `api/routes/_convert.py` (shared pandas→Python converters; `_` prefix so router discovery skips it). Task 1 edits `api/app.py` once to register the middleware — a middleware, not a route (C2 forbids editing `app.py` to add routes); it is added last so it runs outermost.
2. **ETag middleware:** reads `data_version` once per eligible request *before* calling the route (so a tag is never newer than its body), through the same callable FastAPI would use — `app.dependency_overrides.get(get_session, get_session)` entered as a context manager (relies on C2's zero-argument `get_session()` generator) and `app.dependency_overrides.get(get_settings, get_settings)()`; `local_date` = `_filters.today_local(settings.timezone)`; sorted query = `urlencode(sorted(query_params.multi_items()))`; `If-None-Match` is compared weakly over a comma list and `*` matches; a 304 carries `ETag` + `Cache-Control` and an empty body; paths outside `/api` get no header.
3. **Cache:** key `(fn, args, sorted kwargs, bind URL database, data_version)`, where `fn` is the function object itself (nested functions or lambdas sharing a `__qualname__` never share entries); unhashable arguments raise `TypeError` (callers pass tuples); every call returns a copy, on a miss and on every hit: DataFrame/Series via `.copy()`, any other result via `copy.deepcopy`; `read_data_version()` delegates to Plan 03 T7's `analytics.pipeline.get_data_version` (0 when the key is absent; Plan 03 Decision 18 names it as the reader Plan 06's cache and ETag use), so the counter has one reader and one writer (`bump_data_version`); LRU eviction beyond 256 entries; `clear_cache()`. The ETag middleware skips the `data_version` read for a request without a session cookie (every eligible path needs a viewer, so it can never be a 200), and the catch-all 500 sends its own `Cache-Control: no-store` (Starlette serves it outside every user middleware).
4. **Steps and the memo:** `s10_metrics` and `s30_skill` call `clear_cache()` before reading and after writing (Review Focus 2). Plan 10's s50 then reads fresh frames.
5. **Frames:** dates are `datetime.date` objects (object dtype), never datetime64. `load_rounds` = the C7 columns + `gauge` (C7) + `held` (= `events.results_complete`, needed because C7's `compute_round_metrics(rounds)` and `run_skill_model(rounds)` take only a rounds frame). `is_best_round` is a plain bool, `False` until s10 has run (not NaN); other metric/weather columns are NaN until computed. `load_events` = events + event_metrics + event_weather columns (`EVENT_COLUMNS`). `load_station_hits` adds `target_count` and `round_type`, nullable ids as `Int64`. New loader `load_shooters` (shooter_profiles). All loaders are `@cached_by_data_version`.
6. **Weather bands:** labels temp `<40`, `40-55`, `55-70`, `70-85`, `85+`; wind `<10`, `10-20`, `20+`; precip `dry`, `wet`; missing input → `None`; ordered constants `TEMP_BANDS`, `WIND_BANDS`, `PRECIP_BANDS`, `SEASONS`. Shooter splits key rounds without weather as `no_data`. `precip_band` compares `round(precip_in, 3) >= 0.02`: Plan 05 T3's Produces requires consumers of the float4 `event_weather.precip_in` to round to 3 dp before thresholding (its Decision 11, option (b), since Plan 03 T1 keeps C4's `real`), so the band always agrees with the `rain` condition label (test value `0.019999999552965164` → `wet`). The temperature and gust thresholds are integers, exact in float4, and need no rounding.
7. **Metrics:** `percentile` is NULL for non-best rounds too; `compute_event_metrics` writes a row for every scored event (held or not): `n` = rounds, sample stdev (NULL when n = 1), `difficulty` NULL until s30.
8. **Skill `expected`:** C7 step 4 writes `expected = mu_i + d_-i + L_t` and says "the L_t terms cancel, so the residual is unchanged"; that only holds when the published rating `mu_i + L_t` is combined with the level-relative LOO day effect `d_-i − L_t`, so `expected = mu_i + d_-i` (score units) and the residual is the raw-model residual. This matches `predict` (`mu + level − difficulty`, difficulty = `−(d − L)`). Validated against C7's fixture numbers: default params score −2.9105 per shooter-day, the best `DEFAULT_GRID` point −2.9087 (C7: ≈ −2.911 / −2.909).
9. **Skill level:** L = 0.0 before the first held event; at a non-held event L = the window mean if the window holds any held event, else the previous L; `mu_before` and `mu_after` both use the event's L_t; `current_level` = L at the last event (0.0 for an empty frame).
10. **`run_skill_model(rounds, params: SkillParams = DEFAULT_PARAMS)`** with `DEFAULT_PARAMS = SkillParams()`: ruff B008 rejects a call in a default; the value equals C7's `SkillParams()`.
11. **`calibrate`:** `itertools.product` over `GRID_KEYS = ("obs_var", "drift_var_per_week", "difficulty_var", "prior_mu", "prior_var")`, each key's values sorted ascending, best point = `max(candidates, key=log-likelihood)` (max() keeps the first of equal maxima, so ties go to the lexicographically first point; no `assert`, which ruff S101 rejects in src/); burn-in = first 8 held events of the frame; a grid missing a key raises `KeyError`.
12. **`predict`:** shooters absent from `state` start at `(prior_mu, prior_var)`; a shooter missing from a given `attend_prob` gets 1.0; simulated score = `rint(expected + skill deviation + noise + shared day effect)` clipped to 0..50 (an integer `level` shift leaves p_win/p_podium bit-identical for a fixed seed); p_* are NaN for a shooter who never attends in the simulations; `p_outright` is not implemented (C7: "if wanted").
13. **C7 optional items not implemented:** `newcomer_drift_var_per_week`, nulling burn-in difficulty.
14. **s30 params storage:** `app_state.skill_params` = `dataclasses.asdict(SkillParams)` (six floats); a stored value missing any field, holding a non-finite number, or failing `SkillParams` validation (ValueError) counts as absent (`load_params` returns None; recalibrate and overwrite); calibrated params are stored only when the rounds hold more than `BURN_IN_HELD_EVENTS` (8) held event dates — with none scored, calibration is a tie at 0.0 and its first grid point is used for that run without being stored (master T4 said "store the result"; this narrows it so a stations-only first import or a recompute on an empty DB cannot pin degenerate params; the master T4 line now matches); `skill_level` is a JSON number.
15. **Classes:** `assign_classes` returns only active, rated shooters (callers left-join; absent = inactive); `classes.active_shooter_ids(rounds, as_of) -> set[int]` is exported (used by `/api/shooters?active=`, available to Plan 09's rating board).
16. **Events API:** list sorted by date ascending with `winners` (every best round with rank 1); results sorted by score desc, display_name, ordinal; `rating_delta = mu_after − mu_before`; PB notable = C12 `personal_bests` rule (day's best round > every round on earlier dates, with ≥5 rounds on earlier dates); `first_timer` = `shooter_profiles.first_event == date` and not left_censored; `upset` = a winner whose `mu_before` min-rank among that day's best rounds is ≥4 with ≥5 shooters (`value` = that rank); `vs_prev` = previous held event, deltas this − prev (None when either side is null); `weather` null without an event_weather row; `stations` null without station_hits; unknown date → 404 `event_not_found`.
17. **Shooters API:** `stats` and `pbs` honour `round_type`; `odometer` is lifetime and unfiltered, streaks from `streaks(all_rounds, events, today)`; `favorite_month` = month-of-year with the most distinct event dates (ties → lowest month); `trophies` = count of `achievements_awarded` rows; PBs = overall + per calendar year, dated at the first date the score was reached; `current_mu`/`current_var` = last rating_history row; `?active=true|false` filters on C7 Activity as of today; `q` = case-insensitive substring of display_name; unknown id → 404 `shooter_not_found`.
18. **Club API:** `summary.shooters_by_status` counts distinct shooters by current `shooter_status`; `summary.status_by_year` counts rounds by per-row `status` plus `unrecorded_rounds`; `attendance` lists every event; cohorts = calendar year of a shooter's first round (left_censored excluded), retention per year offset, `n_returned` = members with ≥2 event dates; distribution = per-year n/mean/median/P10/P25/P75/P90 (numpy linear) plus a 51-bin histogram; `by` accepts only `year` for distribution and parity (else 422).
19. **Insights:** `form` needs ≥5 rounds with a residual (else null); `bad_day_rate` over all rounds ≤ as_of with a residual; learning-curve value per held event = mean `adjusted` of that day's rounds, `k` counts held events; rust gaps are measured between any attended dates and "first round after a gap" = every round of the first event after a ≥28-day gap (3+ Sundays missed; user decision 2026-09-29, was 42); club rust pools all shooters; milestones = C12 `events` tiers (1/10/25/50/100/150/200/250), projected date = `as_of + 7·ceil(to_go / weekly_rate)` (null when the 26-week rate is 0).
20. **Club insights:** regulars exclude current-status deceased; "0 events in the last 90 days" = no round at all in (as_of − 90d, as_of]; a shooter may be both core and lapsed (independent definitions); conversion counts new guests by the year of the first guest round and conversions by the year of the first member round dated after it; parity counts every event with a rank-1 best round, held or not, a tie gives every tied shooter a win, top-3 share = wins of the three biggest winners / all wins, favorite = the single highest `mu_before` among the day's best rounds (events without any `mu_before`, or whose highest `mu_before` is tied so there is no single favorite, are left out of that rate); trends use as_of = today, YTD = Jan 1 .. as_of's month/day (Feb 29 → Feb 28 only in a non-leap year), `ytd_events_yoy` = fractional change of YTD held events vs calendar year − 1 (null when year − 1 held none in that window), rolling means over the last 8 held events (min 1), seasonality over held events.
21. **Test layout:** Plan 06 tests live in `backend/tests/unit/analytics_core/` and `backend/tests/integration/analytics_core/` (each with its own `conftest.py`) plus `backend/tests/unit/api/test_etag_helpers.py` and `test_route_convert.py`, so no other plan's conftest is edited and every test module basename is unique. Integration tests seed live tables with SQL over C4 table/column names (Plan 03's ORM class names are not part of the contract) through the `seed` fixture, and use the C2 `fx_*` world for fixture goldens whose numbers were computed independently from the workbooks.
22. **Route style:** `Annotated[Session, Depends(get_session, scope="function")]` / `Annotated[Settings, Depends(get_settings)]` parameters (B008-safe), `round_types: list[RoundType] = round_type_param`, every read endpoint returns a Pydantic `*Out` model. Path templates are the C8 literals `/api/events/{date}` and `/api/shooters/{id}…`, bound to descriptive arguments with `Path(alias=…)` (`event_date: Annotated[date, Path(alias="date")]`, `shooter_id: Annotated[int, Path(alias="id")]`) — the convention of Plan 04 D2 — so the generated OpenAPI keys are exactly the ones Plan 08 (its D3), Plan 10 and Plan 11 index; Tasks 5, 6 and 8 each pin their keys with a `create_app().openapi()` test.
23. **Cross-plan notes (no action here):** (a) Starlette ≥1.x `TestClient` emits `StarletteDeprecationWarning` ("install `httpx2`") when only `httpx` is installed; Plan 01 T1 already declares `httpx2` in its dev group (its Decision 3), so `filterwarnings = ["error"]` is safe. (b) `real` columns are float4, so tests compare DB floats with `pytest.approx`. (c) C8 fixes paths and model names, not field names, so the `*Out` models in Tasks 1 and 5–9 (fully specified and tested here) are the field-level source of truth for Plan 08's Consumes lists, TS types and MSW mocks — e.g. `MetaOut.first_event_date/last_event_date`, 404 codes `event_not_found`/`shooter_not_found`, `StationEntryOut.hits: list[{station_no, hits}]` (score via `round_id` → `results`), `ShooterDetailOut.stats`, `PbOut{scope, key, score, event_date, round_id}`, `RatingOut{shooter_id, points, current_mu, peak_mu, peak_date}`, `MilestoneOut`, `ClubSummaryOut.status_by_year`, `CohortOut.retention`, `RegularsOut`, `ConversionYearOut`, `ParityYearOut`, `YearTrendOut.events_held/unique_shooters/ytd_events_yoy`, `MonthTrendOut.n_events/mean_median`; rating changes on the event page are `EventResultOut.rating_delta` (there is no `rating_gain` notable).
24. **Wave independence:** Tasks 5–9 share no files and import nothing from one another, so the last wave can merge in any order. Task 9 therefore selects held events straight from the C4 `results_complete` column (`club_insights._held_events`) instead of importing Task 6's `streaks.held_event_dates`; C7's single-implementation rule is about `streaks()`, which Task 9 does not need. Task 8's fixture test finds its shooter with SQL on `shooter_profiles` instead of calling Task 6's `GET /api/shooters`.

## File Structure
All paths under `backend/`. Task numbers in brackets.

| File | Responsibility |
|---|---|
| `src/sunday_clays/analytics/cache.py` [1] | `@cached_by_data_version` memo, `read_data_version`, `clear_cache` |
| `src/sunday_clays/analytics/frames.py` [1] | frame loaders, band/season helpers, round-type filter, `db_records` |
| `src/sunday_clays/api/routes/_filters.py` [1] | `round_type_param`, `today_local`, `resolve_as_of` |
| `src/sunday_clays/api/routes/_convert.py` [1] | `is_missing`, `opt_float/opt_int/opt_str`, `rows` |
| `src/sunday_clays/api/etag.py` [1] | `CacheHeadersMiddleware` + pure ETag helpers |
| `src/sunday_clays/api/routes/meta.py` [1] | `GET /api/meta` |
| `src/sunday_clays/api/app.py` [1, modify] | register `CacheHeadersMiddleware` last |
| `tests/conftest.py` [1, modify] | autouse fixture clearing the analytics memo |
| `src/sunday_clays/analytics/metrics.py` [2] | best round, min-rank, percentile, adjusted; event metrics |
| `src/sunday_clays/analytics/steps/s10_metrics.py` [2] | recompute step 10 |
| `src/sunday_clays/analytics/skill.py` [3] | skill model, `calibrate`, `predict` |
| `src/sunday_clays/analytics/classes.py` [4] | C7 Activity + A/B/C/D classes |
| `src/sunday_clays/analytics/steps/s30_skill.py` [4] | recompute step 30 (params, skill columns, difficulty, history, level) |
| `src/sunday_clays/api/routes/events.py` [5] | `GET /api/events`, `GET /api/events/{date}` |
| `src/sunday_clays/analytics/streaks.py` [6] | `held_event_dates`, `streaks` |
| `src/sunday_clays/api/routes/shooters.py` [6] | shooter list, detail + odometer + PBs, rounds, rating, splits |
| `src/sunday_clays/analytics/cohorts.py` [7] | newcomer cohorts, retention, returns |
| `src/sunday_clays/api/routes/club.py` [7] | club summary, attendance, cohorts, distribution |
| `src/sunday_clays/analytics/profile.py` [8] | shooter insights as of a date |
| `src/sunday_clays/api/routes/shooter_insights.py` [8] | `GET /api/shooters/{id}/insights` |
| `src/sunday_clays/analytics/club_insights.py` [9] | regulars/lapsed, conversion, parity, trends |
| `src/sunday_clays/api/routes/club_insights.py` [9] | regulars, conversion, parity, trends endpoints |
| `tests/unit/analytics_core/conftest.py` [1] | `make_rounds` / `make_events` synthetic frame builders |
| `tests/integration/analytics_core/conftest.py` [1; 4 adds `analyze()`] | `seed` fixture (`LiveSeed`) writing live tables directly |
| `tests/unit/analytics_core/test_*.py`, `tests/integration/analytics_core/test_*.py`, `tests/unit/api/test_{etag_helpers,route_convert}.py` | per-task tests named in each task |

## Waves
Waves: {T1 (after Plan 04 T2)} → {T2, T3} → {T4} → {T5, T6, T7, T8, T9}.

In the last wave, Tasks 5–9 touch disjoint files and import nothing from one another (Decision 24).

Task N below is master Plan 06 TN (N = 1..9). Every Run and verification command is written from the worktree root
and starts with `cd backend && `; commit steps are root-relative (`git add backend/…`). Integration tests need
Postgres: Docker running (the C2 `engine` fixture starts a `postgres:17` testcontainer) or `TEST_DATABASE_URL`; never
point two worktrees at one shared `TEST_DATABASE_URL`. Each task repeats this under **Test environment**, because the
SDD task-brief script hands an implementer only its own task text.

---

### Task 1: Frames, data_version cache, ETag/Cache-Control middleware and /api/meta (master Plan 06 T1)

**Branch:** `task/06-1-frames-cache-etag-meta`

**Depends on:** Plan 04 T2 (its ETag tests call the admin import/job routes); via Plan 06: Plan 03 T6, T7 and Plan 04 T1.

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/cache.py`
- Create: `backend/src/sunday_clays/analytics/frames.py`
- Create: `backend/src/sunday_clays/api/routes/_convert.py`
- Create: `backend/src/sunday_clays/api/routes/_filters.py`
- Create: `backend/src/sunday_clays/api/etag.py`
- Create: `backend/src/sunday_clays/api/routes/meta.py`
- Modify: `backend/src/sunday_clays/api/app.py` (register `CacheHeadersMiddleware` as the last middleware)
- Modify: `backend/tests/conftest.py` (autouse `_clear_analytics_cache` fixture, C2)
- Test: `backend/tests/unit/analytics_core/test_cache_memo.py`
- Test: `backend/tests/unit/analytics_core/conftest.py` (frame builders used by Tasks 1–9)
- Test: `backend/tests/unit/analytics_core/test_frame_helpers.py`
- Test: `backend/tests/integration/analytics_core/conftest.py` (`seed` fixture used by Tasks 1–9)
- Test: `backend/tests/integration/analytics_core/test_frame_loaders.py`
- Test: `backend/tests/unit/api/test_route_convert.py`
- Test: `backend/tests/unit/api/test_etag_helpers.py`
- Test: `backend/tests/integration/analytics_core/test_meta_route.py`
- Test: `backend/tests/integration/analytics_core/test_etag_middleware.py`

**Interfaces:**
- Consumes:
  - C2: `sunday_clays.db.get_session() -> Iterator[Session]` (zero-argument FastAPI dependency); `sunday_clays.config.Settings` (`app_version: str = "dev"`, `timezone: str`) and `get_settings() -> Settings` (an `lru_cache`); `create_app()` in `api/app.py` (Plan 01 T1; reads no settings; Plan 04 T1 added the role wiring and `app.add_middleware(CsrfGuardMiddleware)` directly after `app.add_middleware(BodySizeLimitMiddleware)`). Conftest fixtures by owner: Plan 01 T1 `session`, `client` (settings from env via `test_settings`, no `get_settings` override; its `get_session` override is a zero-argument generator yielding `session` inside a per-request savepoint), `stations_bytes`; Plan 03 T6 `fx_session` (the `fx_client` world); Plan 04 T1 `viewer_client`, `admin_client` (separate logged-in `TestClient`s on the `client` app, its `get_settings` override removed, settings from env via `auth_env`) and `fx_viewer_client` (the same over `fx_client`).
  - C5: `sunday_clays.domain.round_type.RoundType` (`SPORTING`, `SUPER_SPORTING`, `UNKNOWN`).
  - C6: `sunday_clays.jobs.queue.enqueue(session, kind: str, payload: dict | None = None, *, run_after=None, dedupe_key=None) -> int` (test only); Plan 03 T7 (its Decision 18) `sunday_clays.analytics.pipeline.get_data_version(session) -> int` (0 when absent; `cache.read_data_version` delegates to it) and `bump_data_version(session) -> int` (atomic upsert of the JSON-number counter, starts at 1; the test `seed` fixture and the ETag tests bump through it).
  - C8 (Plan 04): `GET/POST /api/admin/imports`, `GET /api/admin/jobs/{id}` (`JobOut.status`), `POST /api/auth/login|logout`, `GET /api/auth/me`, cookie `sc_session`, `CsrfGuardMiddleware` 403 for a foreign `Origin`.
  - C4 tables/columns: `events`, `rounds`, `shooters`, `shooter_profiles`, `round_metrics`, `event_metrics`, `event_weather`, `station_layouts`, `station_hits`, `rating_history`, `app_state`, `jobs`.
  - Plan 05 T3: `event_weather` rows written by step s20 (float4 measurements rounded at write time; `condition` ∈ `rain`, `windy`, `overcast`, `partly_cloudy`, `clear`; `source` ∈ `archive`, `forecast`; `wind_dir_deg` NULL for a calm window). Its Produces rule: round `precip_in` to 3 dp before comparing it with 0.02 in.
- Produces:
  - `sunday_clays.analytics.cache`: `MAX_ENTRIES = 256`; `read_data_version(session: Session) -> int` (delegates to `pipeline.get_data_version`); `clear_cache() -> None`; `cached_by_data_version[**P, R](fn: Callable[Concatenate[Session, P], R]) -> Callable[Concatenate[Session, P], R]`.
  - `sunday_clays.analytics.frames`: `ROUND_COLUMNS`, `EVENT_COLUMNS`, `STATION_HIT_COLUMNS`, `RATING_COLUMNS`, `SHOOTER_COLUMNS` (tuples of column names); `TEMP_BANDS`, `WIND_BANDS`, `PRECIP_BANDS`, `SEASONS`, `WET_PRECIP_IN = 0.02`, `UNSPECIFIED_GAUGE = "unspecified"`; cached loaders `load_rounds(session) -> pd.DataFrame`, `load_events(session)`, `load_station_hits(session)`, `load_rating_history(session)`, `load_shooters(session)`; `temp_band(temp_f: float | None) -> str | None`, `wind_band(gust_mph: float | None) -> str | None`, `precip_band(precip_in: float | None) -> str | None` (rounds to 3 dp before comparing with `WET_PRECIP_IN`, per Plan 05 T3), `season_label(event_date: date) -> str`, `apply_round_type_filter(df: pd.DataFrame, round_types: Sequence[RoundType]) -> pd.DataFrame`, `db_records(df: pd.DataFrame) -> list[dict[str, object]]`.
  - `sunday_clays.api.routes._filters`: `round_type_param = Query(default=[], alias="round_type")` (declare `round_types: list[RoundType] = round_type_param`); `today_local(tz: str) -> date`; `resolve_as_of(as_of: date | None, tz: str) -> date`. Routes must call `today_local` through this module (tests monkeypatch `_filters.today_local`).
  - `sunday_clays.api.routes._convert`: `is_missing(value: object) -> bool`, `opt_float(value: object) -> float | None`, `opt_int(value: object) -> int | None`, `opt_str(value: object) -> str | None`, `rows(df: pd.DataFrame) -> list[dict[str, Any]]`.
  - `sunday_clays.api.etag`: `CacheHeadersMiddleware`; `etag_eligible(method: str, path: str) -> bool`; `cache_control_for(path: str) -> str | None`; `compute_etag(app_version: str, data_version: int, local_date: str, path: str, query: str) -> str`; `if_none_match_matches(header: str | None, etag: str) -> bool`.
  - `GET /api/meta` → `MetaOut{app_version, data_version, first_event_date, last_event_date, first_score_date, last_score_date, n_events, n_scored_events, n_held_events, n_station_events, n_rounds, n_shooters, last_rebuild_at}`.
  - Test support: fixtures `make_rounds(specs, **defaults) -> pd.DataFrame` and `make_events(specs) -> pd.DataFrame` (unit); fixture `seed` → `LiveSeed` with `shooter(name, *, status="member", left_censored=False) -> int`, `event(d, *, held=True, head_count=None, round_type="unknown", has_scores=True, has_stations=False) -> None`, `round(d, shooter_id, score, *, name_key=None, ordinal=None, gauge_class=None, status="member") -> int`, `weather(d, *, temp_f=55.0, gust_mph=5.0, precip_in=0.0, cloud_pct=20.0, condition="clear") -> None`, `finish() -> None` (fills `events.n_rounds/n_shooters` and `shooter_profiles`, bumps `data_version`), `bump() -> None`.

- [ ] **Step 1: Write the failing cache tests**

Create `backend/tests/unit/analytics_core/test_cache_memo.py`:

```python
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from sunday_clays.analytics import cache


class FakeSession:
    """Just enough of a Session for the memo key: bind URL database + data_version."""

    def __init__(self, database: str = "db1", data_version: int = 1) -> None:
        self.database = database
        self.data_version = data_version

    def get_bind(self) -> SimpleNamespace:
        url = SimpleNamespace(database=self.database)
        return SimpleNamespace(engine=SimpleNamespace(url=url))


@pytest.fixture(autouse=True)
def _fake_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "read_data_version", lambda s: s.data_version)


def _counted() -> tuple[list[int], Callable[..., pd.DataFrame]]:
    calls: list[int] = []

    @cache.cached_by_data_version
    def square(session: Any, x: Any) -> pd.DataFrame:
        calls.append(x)
        return pd.DataFrame({"x": [x * x]})

    return calls, square


def test_same_args_same_version_hits_memo() -> None:
    calls, square = _counted()
    assert square(FakeSession(), 3)["x"].tolist() == [9]
    assert square(FakeSession(), 3)["x"].tolist() == [9]
    assert calls == [3]


def test_new_data_version_or_database_or_args_recomputes() -> None:
    calls, square = _counted()
    square(FakeSession(), 3)
    square(FakeSession(data_version=2), 3)
    square(FakeSession(database="db1_fx"), 3)
    square(FakeSession(), 4)
    assert calls == [3, 3, 3, 4]


def test_returned_frames_are_copies() -> None:
    _, square = _counted()
    first = square(FakeSession(), 3)
    first.loc[0, "x"] = -1
    assert square(FakeSession(), 3)["x"].tolist() == [9]


def test_clear_cache_forces_recompute() -> None:
    calls, square = _counted()
    square(FakeSession(), 3)
    cache.clear_cache()
    square(FakeSession(), 3)
    assert calls == [3, 3]


def test_lru_evicts_oldest_beyond_256_entries() -> None:
    calls, square = _counted()
    for x in range(cache.MAX_ENTRIES + 1):
        square(FakeSession(), x)
    square(FakeSession(), cache.MAX_ENTRIES)  # newest: still cached
    square(FakeSession(), 0)  # oldest: evicted, recomputed
    assert calls.count(cache.MAX_ENTRIES) == 1
    assert calls.count(0) == 2


def test_non_frame_values_are_returned_as_is() -> None:
    @cache.cached_by_data_version
    def label(session: Any, x: int) -> str:
        return f"v{x}"

    assert label(FakeSession(), 2) == "v2"
    assert label(FakeSession(), 2) == "v2"


def test_unhashable_argument_is_rejected() -> None:
    _, square = _counted()
    with pytest.raises(TypeError):
        square(FakeSession(), [1, 2])
```

- [ ] **Step 2: Run the cache tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_cache_memo.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.analytics.cache'`.

- [ ] **Step 3: Implement `analytics/cache.py`**

Create `backend/src/sunday_clays/analytics/cache.py` (the `sunday_clays.analytics` package and `analytics/pipeline.py` with `get_data_version`/`bump_data_version` already exist from Plan 03 T7; `pipeline.py` imports only `sunday_clays.models`, so importing it here creates no cycle):

```python
"""Per-process memo for pure loaders/aggregations, keyed by data_version (C7)."""

import functools
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Concatenate, cast

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version

MAX_ENTRIES = 256

_memo: OrderedDict[tuple[Hashable, ...], object] = OrderedDict()
_lock = threading.Lock()


def read_data_version(session: Session) -> int:
    """Current `app_state.data_version`; 0 before the first rebuild.

    Delegates to Plan 03 T7's `pipeline.get_data_version`, the single reader of the
    counter that `bump_data_version` writes. The memo and the ETag middleware call it
    through this module so tests can monkeypatch `cache.read_data_version`.
    """
    return get_data_version(session)


def clear_cache() -> None:
    """Drop every memoized value in this process."""
    with _lock:
        _memo.clear()


def _database_name(session: Session) -> str:
    return str(session.get_bind().engine.url.database)


def _copy_out(value: object) -> object:
    if isinstance(value, pd.DataFrame | pd.Series):
        return value.copy()
    return value


def cached_by_data_version[**P, R](
    fn: Callable[Concatenate[Session, P], R],
) -> Callable[Concatenate[Session, P], R]:
    """Memoize `fn(session, *args)` per (fn, args, database, data_version); LRU 256.

    Arguments after the session must be hashable (pass tuples, never lists) and date
    arguments must already be resolved (never None). DataFrames/Series are copied on the
    way out so callers may mutate what they get.
    """

    @functools.wraps(fn)
    def wrapper(session: Session, /, *args: P.args, **kwargs: P.kwargs) -> R:
        key: tuple[Hashable, ...] = (
            fn.__module__,
            fn.__qualname__,
            args,
            tuple(sorted(kwargs.items())),
            _database_name(session),
            read_data_version(session),
        )
        with _lock:
            if key in _memo:
                _memo.move_to_end(key)
                return cast(R, _copy_out(_memo[key]))
        value = fn(session, *args, **kwargs)
        with _lock:
            _memo[key] = value
            while len(_memo) > MAX_ENTRIES:
                _memo.popitem(last=False)
        return cast(R, _copy_out(value))

    return wrapper
```

- [ ] **Step 4: Run the cache tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_cache_memo.py -v`
Expected: PASS — 7 passed.

- [ ] **Step 5: Add the autouse memo-clearing fixture (C2)**

In `backend/tests/conftest.py`, add this import to the existing import block (keep ruff's isort order):

```python
from sunday_clays.analytics.cache import clear_cache
```

and append this fixture at the end of the file:

```python
@pytest.fixture(autouse=True)
def _clear_analytics_cache() -> None:
    """C2: every test starts with an empty analytics memo (Plan 06 T1)."""
    clear_cache()
```

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_cache_memo.py -q`
Expected: PASS — 7 passed.

- [ ] **Step 6: Write the failing frame tests (builders, pure helpers, loaders)**

Create `backend/tests/unit/analytics_core/conftest.py` (synthetic frames for every Plan 06 unit test):

```python
"""Synthetic frame builders for Plan 06 unit tests (no DB)."""

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics import frames

RoundSpec = tuple[date, int, int] | Mapping[str, object]


def build_rounds(specs: Sequence[RoundSpec], **defaults: object) -> pd.DataFrame:
    """A frame shaped like `frames.load_rounds`.

    Each spec is an (event_date, shooter_id, score) tuple or a dict of columns.
    Defaults: name_key "s<id>", display_name "Shooter <id>", held True, round_type
    "unknown", status/shooter_status "member", gauge_class None, metrics/weather NaN,
    is_best_round False, round_id 1..n, ordinal 1..k per (event_date, name_key) by
    score desc then input order.
    """
    rows: list[dict[str, object]] = []
    for i, spec in enumerate(specs):
        row: dict[str, object] = (
            {"event_date": spec[0], "shooter_id": spec[1], "score": spec[2]}
            if isinstance(spec, tuple)
            else dict(spec)
        )
        merged = {**defaults, **row}
        sid = merged["shooter_id"]
        merged.setdefault("round_id", i + 1)
        merged.setdefault("name_key", f"s{sid}")
        merged.setdefault("display_name", f"Shooter {sid}")
        merged.setdefault("held", True)
        merged.setdefault("round_type", "unknown")
        merged.setdefault("status", "member")
        merged.setdefault("shooter_status", merged["status"])
        merged.setdefault("gauge_class", None)
        merged.setdefault("is_best_round", False)
        merged["_pos"] = i
        rows.append(merged)
    df = pd.DataFrame(rows)
    if "ordinal" not in df.columns:
        df["ordinal"] = math.nan
    auto = df["ordinal"].isna()
    if auto.any():
        ranked = (
            df.sort_values(["score", "_pos"], ascending=[False, True])
            .groupby(["event_date", "name_key"])
            .cumcount()
            + 1
        )
        df.loc[auto, "ordinal"] = ranked[auto]
    df["ordinal"] = df["ordinal"].astype("int64")
    for column in frames.ROUND_COLUMNS:
        if column not in df.columns:
            df[column] = math.nan
    df["gauge"] = df["gauge_class"].where(
        df["gauge_class"].notna(), frames.UNSPECIFIED_GAUGE
    )
    return (
        df.drop(columns="_pos")
        .sort_values(["event_date", "shooter_id", "ordinal"])
        .reset_index(drop=True)
    )


def build_events(specs: Sequence[date | Mapping[str, object]]) -> pd.DataFrame:
    """A frame shaped like `frames.load_events`; defaults: held, scored, NaN metrics."""
    rows: list[dict[str, object]] = []
    for spec in specs:
        row: dict[str, object] = (
            {"event_date": spec} if isinstance(spec, date) else dict(spec)
        )
        row.setdefault("results_complete", True)
        row.setdefault("has_scores", True)
        row.setdefault("has_stations", False)
        row.setdefault("round_type", "unknown")
        row.setdefault("round_type_source", "none")
        row.setdefault("n_rounds", 0)
        row.setdefault("n_shooters", 0)
        rows.append(row)
    df = pd.DataFrame(rows)
    for column in frames.EVENT_COLUMNS:
        if column not in df.columns:
            df[column] = math.nan
    return (
        df[list(frames.EVENT_COLUMNS)].sort_values("event_date").reset_index(drop=True)
    )


@pytest.fixture
def make_rounds() -> Callable[..., pd.DataFrame]:
    return build_rounds


@pytest.fixture
def make_events() -> Callable[..., pd.DataFrame]:
    return build_events
```

Create `backend/tests/unit/analytics_core/test_frame_helpers.py`:

```python
import math
from collections.abc import Callable
from datetime import date

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics import frames
from sunday_clays.domain.round_type import RoundType


@pytest.mark.parametrize(
    ("temp_f", "band"),
    [
        (None, None),
        (math.nan, None),
        (-5.0, "<40"),
        (39.99, "<40"),
        (40.0, "40-55"),
        (54.9, "40-55"),
        (55.0, "55-70"),
        (69.9, "55-70"),
        (70.0, "70-85"),
        (84.9, "70-85"),
        (85.0, "85+"),
        (101.0, "85+"),
    ],
)
def test_temp_band_half_open_edges(temp_f: float | None, band: str | None) -> None:
    assert frames.temp_band(temp_f) == band


@pytest.mark.parametrize(
    ("gust", "band"),
    [
        (None, None),
        (math.nan, None),
        (0.0, "<10"),
        (9.99, "<10"),
        (10.0, "10-20"),
        (19.99, "10-20"),
        (20.0, "20+"),
        (45.0, "20+"),
    ],
)
def test_wind_band_uses_gust_edges(gust: float | None, band: str | None) -> None:
    assert frames.wind_band(gust) == band


@pytest.mark.parametrize(
    ("precip", "band"),
    [
        (None, None),
        (math.nan, None),
        (0.0, "dry"),
        (0.019, "dry"),
        (0.02, "wet"),
        # a stored float4 0.02 read through a binary cursor or a ::float8 cast (Plan 05
        # Decision 11): rounded to 3 dp first, so it stays on the wet side like `rain`
        (0.019999999552965164, "wet"),
        (1.3, "wet"),
    ],
)
def test_precip_band_threshold_is_two_hundredths(
    precip: float | None, band: str | None
) -> None:
    assert frames.precip_band(precip) == band


def test_band_orders_list_every_label_once() -> None:
    labels = {frames.temp_band(t) for t in (0, 45, 60, 75, 90)}
    assert labels == set(frames.TEMP_BANDS)
    assert {frames.wind_band(g) for g in (0, 15, 30)} == set(frames.WIND_BANDS)
    assert {frames.precip_band(p) for p in (0, 1)} == set(frames.PRECIP_BANDS)


@pytest.mark.parametrize(
    ("month", "season"),
    [
        (12, "winter"),
        (1, "winter"),
        (2, "winter"),
        (3, "spring"),
        (5, "spring"),
        (6, "summer"),
        (8, "summer"),
        (9, "fall"),
        (11, "fall"),
    ],
)
def test_season_label_december_is_winter(month: int, season: str) -> None:
    assert frames.season_label(date(2025, month, 7)) == season


def _typed(make_rounds: Callable[..., pd.DataFrame]) -> pd.DataFrame:
    return make_rounds(
        [
            {
                "event_date": date(2026, 9, 6),
                "shooter_id": 1,
                "score": 30,
                "round_type": "sporting",
            },
            {
                "event_date": date(2026, 9, 13),
                "shooter_id": 1,
                "score": 31,
                "round_type": "super_sporting",
            },
            {"event_date": date(2026, 9, 20), "shooter_id": 1, "score": 32},
        ]
    )


def test_round_type_filter_empty_list_keeps_everything(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    kept = frames.apply_round_type_filter(_typed(make_rounds), [])
    assert kept["score"].tolist() == [30, 31, 32]


def test_round_type_filter_keeps_only_listed_types(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    kept = frames.apply_round_type_filter(
        _typed(make_rounds), [RoundType.SUPER_SPORTING, RoundType.UNKNOWN]
    )
    assert kept["score"].tolist() == [31, 32]


def test_builder_matches_load_rounds_columns(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    built = make_rounds([(date(2026, 9, 6), 1, 30), (date(2026, 9, 6), 1, 35)])
    assert set(frames.ROUND_COLUMNS) <= set(built.columns)
    assert built["ordinal"].tolist() == [1, 2]
    assert built.loc[built["ordinal"] == 1, "score"].item() == 35
    assert built["gauge"].tolist() == ["unspecified", "unspecified"]


def test_db_records_maps_missing_values_to_none_and_numpy_to_python() -> None:
    df = pd.DataFrame(
        {
            "a": pd.array([1, None], dtype="Int64"),
            "b": [1.5, math.nan],
            "c": ["x", None],
            "d": [True, False],
        }
    )
    records = frames.db_records(df)
    assert records == [
        {"a": 1, "b": 1.5, "c": "x", "d": True},
        {"a": None, "b": None, "c": None, "d": False},
    ]
    assert type(records[0]["a"]) is int
    assert type(records[1]["d"]) is bool
    boxed = pd.DataFrame(
        {"n": pd.Series([np.int64(3), np.float64("nan")], dtype=object)}
    )
    assert frames.db_records(boxed) == [{"n": 3}, {"n": None}]
```

Create `backend/tests/integration/analytics_core/conftest.py` (seeds live tables the way `rebuild_live` would, without imports):

```python
"""Plan 06 integration helpers: seed live tables directly (no imports, no rebuild)."""

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version


class LiveSeed:
    """Writes events/rounds/shooter_profiles/event_weather rows like rebuild_live."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._profiles: dict[int, tuple[str, str, bool]] = {}
        self._keys: dict[int, str] = {}
        self._events: set[date] = set()
        self._row = 0

    def shooter(
        self, name: str, *, status: str = "member", left_censored: bool = False
    ) -> int:
        sid = int(
            self.session.execute(
                text(
                    "INSERT INTO shooters (display_name, created_at)"
                    " VALUES (:n, now()) RETURNING id"
                ),
                {"n": name},
            ).scalar_one()
        )
        self._profiles[sid] = (name, status, left_censored)
        self._keys[sid] = name.casefold().replace(",", "")
        return sid

    def event(
        self,
        d: date,
        *,
        held: bool = True,
        head_count: int | None = None,
        round_type: str = "unknown",
        has_scores: bool = True,
        has_stations: bool = False,
    ) -> None:
        source = "none" if round_type == "unknown" else "override"
        self.session.execute(
            text(
                "INSERT INTO events (event_date, round_type, round_type_source,"
                " head_count, n_rounds, n_shooters, has_scores, has_stations,"
                " results_complete)"
                " VALUES (:d, :rt, :src, :hc, 0, 0, :hs, :hst, :rc)"
            ),
            {
                "d": d,
                "rt": round_type,
                "src": source,
                "hc": head_count,
                "hs": has_scores,
                "hst": has_stations,
                "rc": held,
            },
        )
        self._events.add(d)

    def round(
        self,
        d: date,
        shooter_id: int,
        score: int,
        *,
        name_key: str | None = None,
        ordinal: int | None = None,
        gauge_class: str | None = None,
        status: str | None = "member",
    ) -> int:
        if d not in self._events:
            self.event(d)
        key = name_key if name_key is not None else self._keys[shooter_id]
        if ordinal is None:
            ordinal = 1 + int(
                self.session.execute(
                    text(
                        "SELECT count(*) FROM rounds"
                        " WHERE event_date = :d AND name_key = :k"
                    ),
                    {"d": d, "k": key},
                ).scalar_one()
            )
        self._row += 1
        return int(
            self.session.execute(
                text(
                    "INSERT INTO rounds (event_date, shooter_id, name_key, ordinal,"
                    " score, gauge_class, status, source_row)"
                    " VALUES (:d, :s, :k, :o, :sc, :g, :st, :row) RETURNING id"
                ),
                {
                    "d": d,
                    "s": shooter_id,
                    "k": key,
                    "o": ordinal,
                    "sc": score,
                    "g": gauge_class,
                    "st": status,
                    "row": self._row,
                },
            ).scalar_one()
        )

    def weather(
        self,
        d: date,
        *,
        temp_f: float = 55.0,
        gust_mph: float = 5.0,
        precip_in: float = 0.0,
        cloud_pct: float = 20.0,
        condition: str = "clear",
    ) -> None:
        self.session.execute(
            text(
                "INSERT INTO event_weather (event_date, temp_f, apparent_f, precip_in,"
                " wind_mph, gust_mph, wind_dir_deg, cloud_pct, humidity_pct,"
                " pressure_hpa, condition, source)"
                " VALUES (:d, :t, :t, :p, :w, :g, 180, :c, 60, 1015, :cond, 'archive')"
            ),
            {
                "d": d,
                "t": temp_f,
                "p": precip_in,
                "w": gust_mph / 2,
                "g": gust_mph,
                "c": cloud_pct,
                "cond": condition,
            },
        )

    def finish(self) -> None:
        """Fill events.n_rounds/n_shooters and shooter_profiles; bump data_version."""
        self.session.execute(
            text(
                "UPDATE events e SET n_rounds = c.n, n_shooters = c.s"
                " FROM (SELECT event_date, count(*) AS n,"
                " count(DISTINCT shooter_id) AS s FROM rounds GROUP BY event_date) c"
                " WHERE e.event_date = c.event_date"
            )
        )
        self.session.execute(text("DELETE FROM shooter_profiles"))
        for sid, (name, status, left_censored) in self._profiles.items():
            self.session.execute(
                text(
                    "INSERT INTO shooter_profiles (shooter_id, display_name, status,"
                    " first_event, last_event, n_rounds, n_events, left_censored)"
                    " SELECT :s, :n, :st, min(event_date), max(event_date), count(*),"
                    " count(DISTINCT event_date), :lc FROM rounds WHERE shooter_id = :s"
                    " HAVING count(*) > 0"
                ),
                {"s": sid, "n": name, "st": status, "lc": left_censored},
            )
        self.bump()

    def bump(self) -> None:
        """Advance `app_state.data_version` the way rebuild/run_pipeline do (Plan 03 T7)."""
        bump_data_version(self.session)


@pytest.fixture
def seed(session: Session) -> LiveSeed:
    return LiveSeed(session)
```

Create `backend/tests/integration/analytics_core/test_frame_loaders.py` (fixture numbers: 24 + 13 station entries × 7 stations; Hadley, Ike 2026-09-13 station total 36 — computed from `stations_2026-09-27.xlsx`):

```python
import math
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames

D1 = date(2026, 9, 6)
D2 = date(2026, 9, 13)


def test_load_rounds_columns_and_values(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann", status="guest")
    bob = seed.shooter("Pratt, Bob", status="deceased")
    seed.event(D1, round_type="super_sporting")
    seed.round(D1, ann, 41, gauge_class="Sub-Gauge", status="guest")
    seed.round(D1, bob, 38, status="member")
    seed.weather(D1, temp_f=48.0, gust_mph=22.0, precip_in=0.05, condition="rain")
    seed.finish()

    df = frames.load_rounds(session)

    assert list(df.columns) == list(frames.ROUND_COLUMNS)
    ann_row = df[df["shooter_id"] == ann].iloc[0]
    assert ann_row["event_date"] == D1
    assert ann_row["display_name"] == "Oakley, Ann"
    assert ann_row["score"] == 41
    assert ann_row["gauge"] == "Sub-Gauge"
    assert ann_row["round_type"] == "super_sporting"
    assert bool(ann_row["held"]) is True
    assert ann_row["temp_f"] == 48.0
    assert ann_row["condition"] == "rain"
    assert math.isnan(ann_row["field_median"])
    assert bool(ann_row["is_best_round"]) is False
    bob_row = df[df["shooter_id"] == bob].iloc[0]
    assert bob_row["gauge"] == "unspecified"
    assert bob_row["status"] == "member"
    assert bob_row["shooter_status"] == "deceased"


def test_load_rounds_reads_round_metrics_when_present(
    seed: Any, session: Session
) -> None:
    ann = seed.shooter("Oakley, Ann")
    rid = seed.round(D1, ann, 41)
    seed.finish()
    session.execute(
        text(
            "INSERT INTO round_metrics (round_id, field_median, adjusted, event_rank,"
            " is_best_round, percentile) VALUES (:r, 41, 0, 1, true, 1.0)"
        ),
        {"r": rid},
    )
    seed.bump()

    row = frames.load_rounds(session).iloc[0]

    assert row["event_rank"] == 1.0
    assert bool(row["is_best_round"]) is True


def test_load_events_joins_metrics_and_weather(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(D1, head_count=12)
    seed.event(D2, held=False, has_scores=False, head_count=9)
    seed.round(D1, ann, 30)
    seed.weather(D1, temp_f=61.0)
    seed.finish()

    ev = frames.load_events(session)

    assert list(ev.columns) == list(frames.EVENT_COLUMNS)
    assert ev["event_date"].tolist() == [D1, D2]
    assert ev["head_count"].tolist() == [12.0, 9.0]
    assert ev["n_rounds"].tolist() == [1, 0]
    assert ev["results_complete"].tolist() == [True, False]
    assert ev["temp_f"].iloc[0] == 61.0
    assert math.isnan(ev["temp_f"].iloc[1])


def test_load_shooters_and_empty_rating_history(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann", left_censored=True)
    seed.round(D1, ann, 30)
    seed.round(D2, ann, 33)
    seed.finish()

    shooters = frames.load_shooters(session)
    history = frames.load_rating_history(session)

    assert shooters.to_dict(orient="records") == [
        {
            "shooter_id": ann,
            "display_name": "Oakley, Ann",
            "status": "member",
            "first_event": D1,
            "last_event": D2,
            "n_rounds": 2,
            "n_events": 2,
            "left_censored": True,
        },
    ]
    assert list(history.columns) == ["shooter_id", "event_date", "mu", "var"]
    assert history.empty


def test_loaders_are_memoized_until_data_version_changes(
    seed: Any, session: Session
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D1, ann, 30)
    seed.finish()
    assert len(frames.load_rounds(session)) == 1

    seed.round(D2, ann, 31)
    session.execute(
        text("UPDATE events SET n_rounds = 1 WHERE event_date = :d"), {"d": D2}
    )
    assert len(frames.load_rounds(session)) == 1  # same data_version: memo hit

    seed.finish()
    assert len(frames.load_rounds(session)) == 2


def test_load_station_hits_on_committed_fixtures(fx_session: Session) -> None:
    hits = frames.load_station_hits(fx_session)

    assert list(hits.columns) == list(frames.STATION_HIT_COLUMNS)
    assert len(hits) == 259  # (24 + 13) entries x 7 stations
    assert sorted(set(hits["event_date"])) == [D1, D2]
    assert set(hits["round_type"]) == {"super_sporting"}
    hadley = hits[(hits["event_date"] == D2) & (hits["name_key"] == "hadley ike")]
    assert hadley["hits"].sum() == 36
    assert hadley["target_count"].tolist() == [7, 7, 7, 7, 7, 7, 8]
```

- [ ] **Step 7: Run the frame tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_frame_helpers.py tests/integration/analytics_core/test_frame_loaders.py -v`
Expected: ERROR — `ImportError while loading conftest ... ModuleNotFoundError: No module named 'sunday_clays.analytics.frames'`.

- [ ] **Step 8: Implement `analytics/frames.py`**

Create `backend/src/sunday_clays/analytics/frames.py`:

```python
"""DataFrame loaders over the live/analytics tables and shared frame helpers (C7)."""

import math
from collections.abc import Sequence
from datetime import date

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.domain.round_type import RoundType

TEMP_BANDS: tuple[str, ...] = ("<40", "40-55", "55-70", "70-85", "85+")
WIND_BANDS: tuple[str, ...] = ("<10", "10-20", "20+")
PRECIP_BANDS: tuple[str, ...] = ("dry", "wet")
SEASONS: tuple[str, ...] = ("winter", "spring", "summer", "fall")
WET_PRECIP_IN = 0.02
UNSPECIFIED_GAUGE = "unspecified"

ROUND_COLUMNS: tuple[str, ...] = (
    "round_id",
    "event_date",
    "shooter_id",
    "name_key",
    "display_name",
    "ordinal",
    "score",
    "gauge_class",
    "status",
    "shooter_status",
    "round_type",
    "field_median",
    "adjusted",
    "event_rank",
    "is_best_round",
    "percentile",
    "expected",
    "residual",
    "mu_before",
    "mu_after",
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "condition",
    "gauge",
    "held",
)
EVENT_COLUMNS: tuple[str, ...] = (
    "event_date",
    "round_type",
    "round_type_source",
    "head_count",
    "n_rounds",
    "n_shooters",
    "has_scores",
    "has_stations",
    "results_complete",
    "n",
    "median",
    "mean",
    "stdev",
    "top_score",
    "difficulty",
    "temp_f",
    "apparent_f",
    "precip_in",
    "wind_mph",
    "gust_mph",
    "wind_dir_deg",
    "cloud_pct",
    "humidity_pct",
    "pressure_hpa",
    "condition",
)
STATION_HIT_COLUMNS: tuple[str, ...] = (
    "event_date",
    "station_no",
    "target_count",
    "sheet_id",
    "entry_row",
    "name_key",
    "shooter_id",
    "round_id",
    "hits",
    "round_type",
)
RATING_COLUMNS: tuple[str, ...] = ("shooter_id", "event_date", "mu", "var")
SHOOTER_COLUMNS: tuple[str, ...] = (
    "shooter_id",
    "display_name",
    "status",
    "first_event",
    "last_event",
    "n_rounds",
    "n_events",
    "left_censored",
)

_ROUNDS_SQL = """
SELECT r.id AS round_id, r.event_date, r.shooter_id, r.name_key, p.display_name,
       r.ordinal, r.score, r.gauge_class, r.status, p.status AS shooter_status,
       e.round_type, m.field_median, m.adjusted, m.event_rank, m.is_best_round,
       m.percentile, m.expected, m.residual, m.mu_before, m.mu_after, w.temp_f,
       w.apparent_f, w.precip_in, w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct,
       w.condition, e.results_complete AS held
FROM rounds r
JOIN events e ON e.event_date = r.event_date
JOIN shooter_profiles p ON p.shooter_id = r.shooter_id
LEFT JOIN round_metrics m ON m.round_id = r.id
LEFT JOIN event_weather w ON w.event_date = r.event_date
ORDER BY r.event_date, r.shooter_id, r.name_key, r.ordinal
"""
_EVENTS_SQL = """
SELECT e.event_date, e.round_type, e.round_type_source, e.head_count, e.n_rounds,
       e.n_shooters, e.has_scores, e.has_stations, e.results_complete, m.n, m.median,
       m.mean, m.stdev, m.top_score, m.difficulty, w.temp_f, w.apparent_f, w.precip_in,
       w.wind_mph, w.gust_mph, w.wind_dir_deg, w.cloud_pct, w.humidity_pct,
       w.pressure_hpa, w.condition
FROM events e
LEFT JOIN event_metrics m ON m.event_date = e.event_date
LEFT JOIN event_weather w ON w.event_date = e.event_date
ORDER BY e.event_date
"""
_STATION_HITS_SQL = """
SELECT h.event_date, h.station_no, l.target_count, h.sheet_id, h.entry_row, h.name_key,
       h.shooter_id, h.round_id, h.hits, e.round_type
FROM station_hits h
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_no = h.station_no
JOIN events e ON e.event_date = h.event_date
ORDER BY h.event_date, h.entry_row, h.station_no
"""
_RATING_SQL = """
SELECT shooter_id, event_date, mu, var FROM rating_history
ORDER BY shooter_id, event_date
"""
_SHOOTERS_SQL = """
SELECT shooter_id, display_name, status, first_event, last_event, n_rounds, n_events,
       left_censored
FROM shooter_profiles ORDER BY shooter_id
"""


def _frame(
    session: Session,
    sql: str,
    columns: Sequence[str],
    *,
    ints: Sequence[str] = (),
    nullable_ints: Sequence[str] = (),
    floats: Sequence[str] = (),
    bools: Sequence[str] = (),
) -> pd.DataFrame:
    rows = [dict(r) for r in session.execute(text(sql)).mappings()]
    df = pd.DataFrame(rows, columns=list(columns))
    for c in ints:
        df[c] = df[c].astype("int64")
    for c in nullable_ints:
        df[c] = df[c].astype("Int64")
    for c in floats:
        df[c] = df[c].astype("float64")
    for c in bools:
        df[c] = df[c].eq(True)
    return df


@cached_by_data_version
def load_rounds(session: Session) -> pd.DataFrame:
    """One row per live round with metrics, weather and derived `gauge`/`held`.

    Dates are `datetime.date` objects. Metric/weather columns are NaN until computed;
    `is_best_round` is False until s10 has run; `held` = the event's `results_complete`.
    """
    df = _frame(
        session,
        _ROUNDS_SQL,
        [c for c in ROUND_COLUMNS if c != "gauge"],
        ints=("round_id", "shooter_id", "ordinal", "score"),
        floats=(
            "field_median",
            "adjusted",
            "event_rank",
            "percentile",
            "expected",
            "residual",
            "mu_before",
            "mu_after",
            "temp_f",
            "apparent_f",
            "precip_in",
            "wind_mph",
            "gust_mph",
            "wind_dir_deg",
            "cloud_pct",
        ),
        bools=("is_best_round", "held"),
    )
    df["gauge"] = df["gauge_class"].where(df["gauge_class"].notna(), UNSPECIFIED_GAUGE)
    return df[list(ROUND_COLUMNS)]


@cached_by_data_version
def load_events(session: Session) -> pd.DataFrame:
    """Each `events` row plus event_metrics/event_weather columns (NaN if absent)."""
    return _frame(
        session,
        _EVENTS_SQL,
        EVENT_COLUMNS,
        ints=("n_rounds", "n_shooters"),
        floats=(
            "head_count",
            "n",
            "median",
            "mean",
            "stdev",
            "top_score",
            "difficulty",
            "temp_f",
            "apparent_f",
            "precip_in",
            "wind_mph",
            "gust_mph",
            "wind_dir_deg",
            "cloud_pct",
            "humidity_pct",
            "pressure_hpa",
        ),
        bools=("has_scores", "has_stations", "results_complete"),
    )


@cached_by_data_version
def load_station_hits(session: Session) -> pd.DataFrame:
    """station_hits rows with the station's target_count and the event round_type."""
    return _frame(
        session,
        _STATION_HITS_SQL,
        STATION_HIT_COLUMNS,
        ints=("station_no", "target_count", "sheet_id", "entry_row", "hits"),
        nullable_ints=("shooter_id", "round_id"),
    )


@cached_by_data_version
def load_rating_history(session: Session) -> pd.DataFrame:
    """rating_history by (shooter_id, event_date); `mu` on the published scale."""
    return _frame(
        session, _RATING_SQL, RATING_COLUMNS, ints=("shooter_id",), floats=("mu", "var")
    )


@cached_by_data_version
def load_shooters(session: Session) -> pd.DataFrame:
    """shooter_profiles as a frame (current status incl. overrides, left_censored)."""
    return _frame(
        session,
        _SHOOTERS_SQL,
        SHOOTER_COLUMNS,
        ints=("shooter_id", "n_rounds", "n_events"),
        bools=("left_censored",),
    )


def _is_missing(value: float | None) -> bool:
    return value is None or math.isnan(value)


def temp_band(temp_f: float | None) -> str | None:
    """C7 temperature band, half-open [lo, hi): <40, 40-55, 55-70, 70-85, 85+ (°F)."""
    if temp_f is None or _is_missing(temp_f):
        return None
    if temp_f < 40:
        return "<40"
    if temp_f < 55:
        return "40-55"
    if temp_f < 70:
        return "55-70"
    if temp_f < 85:
        return "70-85"
    return "85+"


def wind_band(gust_mph: float | None) -> str | None:
    """C7 wind band by gust: <10, 10-20, 20+ (mph)."""
    if gust_mph is None or _is_missing(gust_mph):
        return None
    if gust_mph < 10:
        return "<10"
    if gust_mph < 20:
        return "10-20"
    return "20+"


def precip_band(precip_in: float | None) -> str | None:
    """C7 precipitation band: dry (< 0.02 in) or wet (>= 0.02 in).

    `event_weather.precip_in` is float4 (C4 `real`), stored rounded to 3 dp (Plan 05); a
    binary read returns a stored 0.02 as 0.019999999552965164. Rounding to 3 dp before
    the comparison keeps the band on the same side as the `rain` condition label.
    """
    if precip_in is None or _is_missing(precip_in):
        return None
    return "wet" if round(precip_in, 3) >= WET_PRECIP_IN else "dry"


def season_label(event_date: date) -> str:
    """Month season: winter Dec-Feb, spring Mar-May, summer Jun-Aug, fall Sep-Nov."""
    return SEASONS[(event_date.month % 12) // 3]


def apply_round_type_filter(
    df: pd.DataFrame, round_types: Sequence[RoundType]
) -> pd.DataFrame:
    """Keep rows whose event `round_type` is in `round_types`; empty = no filter."""
    if not round_types:
        return df
    return df.loc[df["round_type"].isin([rt.value for rt in round_types])]


def db_records(df: pd.DataFrame) -> list[dict[str, object]]:
    """Rows as dicts with NaN/NA mapped to None (for SQL parameters).

    `DataFrame.to_dict(orient="records")` already unboxes numpy scalars.
    """
    return [
        {str(k): _plain(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def _plain(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
```

- [ ] **Step 9: Run the frame tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_frame_helpers.py tests/integration/analytics_core/test_frame_loaders.py -v`
Expected: PASS — 47 passed (41 unit + 6 integration).

- [ ] **Step 10: Write the failing converter tests**

Create `backend/tests/unit/api/test_route_convert.py`:

```python
import math

import numpy as np
import pandas as pd
import pytest

from sunday_clays.api.routes._convert import is_missing, opt_float, opt_int, opt_str


@pytest.mark.parametrize("value", [None, pd.NA, math.nan, np.float64("nan")])
def test_missing_values_become_none(value: object) -> None:
    assert is_missing(value)
    assert opt_float(value) is None
    assert opt_int(value) is None
    assert opt_str(value) is None


def test_present_values_become_plain_python() -> None:
    assert opt_float(np.float64(1.5)) == 1.5
    assert type(opt_float(np.int64(2))) is float
    assert opt_int(np.float64(3.0)) == 3
    assert type(opt_int(np.int64(3))) is int
    assert opt_str("x") == "x"
    assert not is_missing(0.0)
```

- [ ] **Step 11: Run the converter tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/api/test_route_convert.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.api.routes._convert'`.

- [ ] **Step 12: Implement `api/routes/_convert.py`**

Create `backend/src/sunday_clays/api/routes/_convert.py`:

```python
"""pandas/numpy scalars -> plain Python for read routes (skipped by discovery)."""

import math
from typing import Any, SupportsFloat, SupportsInt, cast

import pandas as pd


def is_missing(value: object) -> bool:
    """None, pd.NA and float NaN (incl. numpy.float64) count as missing."""
    if value is None or value is pd.NA:
        return True
    return isinstance(value, float) and math.isnan(value)


def opt_float(value: object) -> float | None:
    return None if is_missing(value) else float(cast(SupportsFloat, value))


def opt_int(value: object) -> int | None:
    return None if is_missing(value) else int(cast(SupportsInt, value))


def opt_str(value: object) -> str | None:
    return None if is_missing(value) else str(value)


def rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame rows as dicts keyed by column name."""
    return [{str(k): v for k, v in row.items()} for row in df.to_dict(orient="records")]
```

- [ ] **Step 13: Run the converter tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/api/test_route_convert.py -v`
Expected: PASS — 5 passed.

- [ ] **Step 14: Write the failing ETag, Cache-Control and /api/meta tests**

Create `backend/tests/unit/api/test_etag_helpers.py` (the digest literal is `sha1("/api/meta?a=1&b=2")[:16]`, computed independently):

```python
import pytest

from sunday_clays.api import etag


@pytest.mark.parametrize(
    ("method", "path", "eligible"),
    [
        ("GET", "/api/meta", True),
        ("GET", "/api/events/2026-09-13", True),
        ("HEAD", "/api/meta", False),
        ("POST", "/api/explore", False),
        ("GET", "/api/health", False),
        ("GET", "/api/auth/me", False),
        ("GET", "/api/admin/imports", False),
        ("GET", "/api/predictions/next", False),
        ("GET", "/index.html", False),
    ],
)
def test_etag_eligibility(method: str, path: str, eligible: bool) -> None:
    assert etag.etag_eligible(method, path) is eligible


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("/api/meta", "private, no-cache"),
        ("/api/health", "private, no-cache"),
        ("/api/auth/me", "no-store"),
        ("/api/admin/jobs/1", "no-store"),
        ("/assets/app.js", None),
    ],
)
def test_cache_control_by_path(path: str, value: str | None) -> None:
    assert etag.cache_control_for(path) == value


def test_compute_etag_shape_and_inputs() -> None:
    tag = etag.compute_etag("1.2.0", 7, "2026-09-27", "/api/meta", "a=1&b=2")
    # sha1("/api/meta?a=1&b=2")[:16], computed independently
    assert tag == 'W/"1.2.0-7-2026-09-27-d416113a7944bb51"'
    assert etag.compute_etag("1.2.1", 7, "2026-09-27", "/api/meta", "a=1&b=2") != tag
    assert etag.compute_etag("1.2.0", 8, "2026-09-27", "/api/meta", "a=1&b=2") != tag
    assert etag.compute_etag("1.2.0", 7, "2026-09-28", "/api/meta", "a=1&b=2") != tag
    assert etag.compute_etag("1.2.0", 7, "2026-09-27", "/api/meta", "a=1&b=3") != tag


@pytest.mark.parametrize(
    ("header", "matches"),
    [
        (None, False),
        ("", False),
        ('W/"x-1"', True),
        ('"x-1"', True),
        ('W/"x-2", W/"x-1"', True),
        ('W/"x-2"', False),
        ("*", True),
    ],
)
def test_if_none_match_weak_comparison(header: str | None, matches: bool) -> None:
    assert etag.if_none_match_matches(header, 'W/"x-1"') is matches
```

Create `backend/tests/integration/analytics_core/test_meta_route.py` (fixture numbers from the master golden: 360 events, 311 scored, 310 held, 2 station events, 7,480 rounds, 332 shooters):

```python
from datetime import date
from typing import Any

from fastapi.testclient import TestClient


def test_meta_counts_seeded_world(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    seed.event(date(2026, 8, 30), held=False, has_scores=False, head_count=5)
    seed.round(date(2026, 9, 6), ann, 40)
    seed.round(date(2026, 9, 6), bob, 35)
    seed.round(date(2026, 9, 13), ann, 42)
    seed.finish()

    body = viewer_client.get("/api/meta").json()

    assert body["data_version"] >= 1
    assert body["first_event_date"] == "2026-08-30"
    assert body["last_event_date"] == "2026-09-13"
    assert body["first_score_date"] == "2026-09-06"
    assert body["n_events"] == 3
    assert body["n_scored_events"] == 2
    assert body["n_held_events"] == 2
    assert body["n_rounds"] == 3
    assert body["n_shooters"] == 2


def test_meta_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/meta").json()

    assert body["first_event_date"] == "2018-12-30"
    assert body["last_score_date"] == "2026-09-27"
    assert body["n_events"] == 360
    assert body["n_scored_events"] == 311
    assert body["n_held_events"] == 310
    assert body["n_station_events"] == 2
    assert body["n_rounds"] == 7480
    assert body["n_shooters"] == 332
```

Create `backend/tests/integration/analytics_core/test_etag_middleware.py`:

```python
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.api.routes import _filters
from sunday_clays.config import get_settings
from sunday_clays.jobs.queue import enqueue

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_viewer_get_gets_weak_etag_and_304_on_match(viewer_client: TestClient) -> None:
    first = viewer_client.get("/api/meta")
    assert first.status_code == 200
    tag = first.headers["etag"]
    assert tag.startswith('W/"')
    assert first.headers["cache-control"] == "private, no-cache"

    again = viewer_client.get("/api/meta", headers={"If-None-Match": tag})

    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == tag


def test_query_string_order_does_not_change_etag(viewer_client: TestClient) -> None:
    a = viewer_client.get("/api/meta?b=2&a=1").headers["etag"]
    b = viewer_client.get("/api/meta?a=1&b=2").headers["etag"]
    c = viewer_client.get("/api/meta?a=1&b=3").headers["etag"]
    assert a == b
    assert c != a


def test_data_version_bump_changes_etag(
    viewer_client: TestClient, session: Session
) -> None:
    before = viewer_client.get("/api/meta").headers["etag"]
    bump_data_version(session)  # what rebuild_live and run_pipeline do (Plan 03 T7)

    after = viewer_client.get("/api/meta", headers={"If-None-Match": before})

    assert after.status_code == 200
    assert after.headers["etag"] != before


def test_app_version_change_changes_etag(viewer_client: TestClient) -> None:
    app: Any = viewer_client.app
    before = viewer_client.get("/api/meta").headers["etag"]
    base = app.dependency_overrides.get(get_settings, get_settings)()
    bumped = base.model_copy(update={"app_version": f"{base.app_version}-next"})
    app.dependency_overrides[get_settings] = lambda: bumped

    after = viewer_client.get("/api/meta", headers={"If-None-Match": before})

    assert after.status_code == 200
    assert after.headers["etag"] != before


def test_local_date_change_changes_etag(
    viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = viewer_client.get("/api/meta").headers["etag"]
    real = _filters.today_local
    monkeypatch.setattr(_filters, "today_local", lambda tz: real(tz).replace(year=2099))

    after = viewer_client.get("/api/meta", headers={"If-None-Match": before})

    assert after.status_code == 200
    assert after.headers["etag"] != before


def test_health_has_no_etag(client: TestClient) -> None:
    r = client.get("/api/health", headers={"If-None-Match": "*"})
    assert r.status_code == 200
    assert "etag" not in r.headers
    assert r.headers["cache-control"] == "private, no-cache"


def test_non_api_paths_get_no_cache_headers(client: TestClient) -> None:
    r = client.get("/index.html", headers={"If-None-Match": "*"})
    assert r.status_code == 404
    assert "cache-control" not in r.headers
    assert "etag" not in r.headers


def test_middleware_rejections_still_get_cache_control(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert r.headers["cache-control"] == "no-store"

    # Content-Length 300,002 > the 262,144-byte limit for non-import /api paths (C2).
    big = client.post(
        "/api/auth/login",
        content=b"{" + b" " * 300_000 + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert big.status_code == 413
    assert big.headers["cache-control"] == "no-store"


def test_401_is_never_turned_into_304(client: TestClient) -> None:
    r = client.get("/api/meta", headers={"If-None-Match": "*"})
    assert r.status_code == 401
    assert "etag" not in r.headers


def test_404_is_never_turned_into_304(viewer_client: TestClient) -> None:
    r = viewer_client.get("/api/no-such-route", headers={"If-None-Match": "*"})
    assert r.status_code == 404
    assert "etag" not in r.headers


def test_staging_an_import_changes_admin_imports_list(
    admin_client: TestClient, stations_bytes: bytes
) -> None:
    before = admin_client.get("/api/admin/imports")
    assert before.status_code == 200
    assert "etag" not in before.headers
    assert before.headers["cache-control"] == "no-store"
    meta_tag = admin_client.get("/api/meta").headers["etag"]

    staged = admin_client.post(
        "/api/admin/imports", files={"file": ("stations.xlsx", stations_bytes, XLSX)}
    )
    assert staged.is_success
    after = admin_client.get(
        "/api/admin/imports", headers={"If-None-Match": f"{meta_tag}, *"}
    )

    assert after.status_code == 200
    assert len(after.json()) == len(before.json()) + 1


def test_admin_job_status_is_never_cached(
    admin_client: TestClient, session: Session
) -> None:
    job_id = enqueue(session, "etag_probe")
    seen = []
    for status in ("queued", "running", "failed"):
        session.execute(
            text("UPDATE jobs SET status = :s WHERE id = :i"),
            {"s": status, "i": job_id},
        )
        r = admin_client.get(
            f"/api/admin/jobs/{job_id}", headers={"If-None-Match": "*"}
        )
        assert r.status_code == 200
        assert "etag" not in r.headers
        seen.append(r.json()["status"])
    assert seen == ["queued", "running", "failed"]


def test_me_after_logout_is_401_not_304(viewer_client: TestClient) -> None:
    assert viewer_client.get("/api/auth/me").json()["role"] == "viewer"
    viewer_client.post("/api/auth/logout")

    r = viewer_client.get("/api/auth/me", headers={"If-None-Match": "*"})

    assert r.status_code == 401
    assert r.headers["cache-control"] == "no-store"


def test_me_after_admin_logout_then_viewer_login_is_viewer(
    request: pytest.FixtureRequest,
) -> None:
    viewer: TestClient = request.getfixturevalue("viewer_client")
    viewer_cookie = viewer.cookies.get("sc_session")
    admin: TestClient = request.getfixturevalue("admin_client")
    assert admin.get("/api/auth/me").json()["role"] == "admin"
    admin.post("/api/auth/logout")

    r = admin.get(
        "/api/auth/me",
        headers={"Cookie": f"sc_session={viewer_cookie}", "If-None-Match": "*"},
    )

    assert r.status_code == 200
    assert r.json()["role"] == "viewer"
    assert "etag" not in r.headers
```

(The last test grabs the viewer cookie before requesting `admin_client`, so it works whether or not the two C2 fixtures share one TestClient.)

- [ ] **Step 15: Run the ETag/meta tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/api/test_etag_helpers.py tests/integration/analytics_core/test_meta_route.py tests/integration/analytics_core/test_etag_middleware.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sunday_clays.api.etag'` (unit file) and `ImportError: cannot import name '_filters'` (middleware file); the meta tests fail with `KeyError` on the 404 body because `/api/meta` is not routed.

- [ ] **Step 16: Implement `_filters.py`, `etag.py` and `meta.py`**

Create `backend/src/sunday_clays/api/routes/_filters.py`:

```python
"""Shared query parameters and date helpers for read routes (skipped by discovery)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import Query

round_type_param = Query(default=[], alias="round_type")


def today_local(tz: str) -> date:
    """Today's date in the club's timezone (C2 `settings.timezone`)."""
    return datetime.now(ZoneInfo(tz)).date()


def resolve_as_of(as_of: date | None, tz: str) -> date:
    """C7: `as_of=None` means today in the club timezone (before any cached call)."""
    return as_of if as_of is not None else today_local(tz)
```

Create `backend/src/sunday_clays/api/etag.py`:

```python
"""Cache-Control + weak ETag middleware for GET /api responses (C8)."""

import contextlib
import hashlib
from collections.abc import Callable, Iterator
from typing import cast
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from sunday_clays.analytics.cache import read_data_version
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session

NO_ETAG_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/",
    "/api/admin/",
    "/api/predictions/",
)
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/")


def etag_eligible(method: str, path: str) -> bool:
    """GET under /api/, except health, auth, admin and predictions."""
    return (
        method == "GET"
        and path.startswith("/api/")
        and not path.startswith(NO_ETAG_PREFIXES)
    )


def cache_control_for(path: str) -> str | None:
    """`no-store` for auth/admin, `private, no-cache` for other /api paths."""
    if path.startswith(NO_STORE_PREFIXES):
        return "no-store"
    if path == "/api" or path.startswith("/api/"):
        return "private, no-cache"
    return None


def compute_etag(
    app_version: str, data_version: int, local_date: str, path: str, query: str
) -> str:
    """W/"<app_version>-<data_version>-<local_date>-<sha1(path?sorted query)[:16]>"."""
    # A cache key, not a security digest: usedforsecurity=False keeps ruff S324 clean.
    digest = hashlib.sha1(f"{path}?{query}".encode(), usedforsecurity=False).hexdigest()[:16]
    return f'W/"{app_version}-{data_version}-{local_date}-{digest}"'


def if_none_match_matches(header: str | None, etag: str) -> bool:
    """Weak comparison against a comma-separated If-None-Match list; `*` matches."""
    if not header:
        return False
    opaque = etag.removeprefix("W/")
    for candidate in header.split(","):
        tag = candidate.strip()
        if tag == "*" or tag.removeprefix("W/") == opaque:
            return True
    return False


def sorted_query(request: Request) -> str:
    return urlencode(sorted(request.query_params.multi_items()))


def _dependency[T](app: FastAPI, dependency: Callable[[], T]) -> Callable[[], T]:
    """The callable FastAPI would use for `dependency`, honouring test overrides."""
    return cast(Callable[[], T], app.dependency_overrides.get(dependency, dependency))


def _versions(app: FastAPI) -> tuple[Settings, int]:
    settings = _dependency(app, get_settings)()
    provider = cast(Callable[[], Iterator[Session]], _dependency(app, get_session))
    with contextlib.contextmanager(provider)() as session:
        data_version = read_data_version(session)
    return settings, data_version


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """Cache-Control on every /api response; weak ETag (+304) on eligible GET 200s.

    data_version is read once per eligible request, before the route runs, so the tag
    can only be older than the body, never newer. The route always runs; nothing
    short-circuits.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        versions: tuple[Settings, int] | None = None
        if etag_eligible(request.method, path):
            versions = await run_in_threadpool(_versions, cast(FastAPI, request.app))
        response = await call_next(request)
        cache_control = cache_control_for(path)
        if cache_control is not None:
            response.headers["Cache-Control"] = cache_control
        if versions is None or response.status_code != 200:
            return response
        settings, data_version = versions
        etag = compute_etag(
            settings.app_version,
            data_version,
            _filters.today_local(settings.timezone).isoformat(),
            path,
            sorted_query(request),
        )
        if if_none_match_matches(request.headers.get("if-none-match"), etag):
            return Response(
                status_code=304,
                headers={
                    "ETag": etag,
                    "Cache-Control": cache_control or "private, no-cache",
                },
            )
        response.headers["ETag"] = etag
        return response
```

Create `backend/src/sunday_clays/api/routes/meta.py`:

```python
"""GET /api/meta: data_version, date range and live-table counts."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import read_data_version
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session

router = APIRouter()

_COUNTS_SQL = """
SELECT
  (SELECT min(event_date) FROM events) AS first_event_date,
  (SELECT max(event_date) FROM events) AS last_event_date,
  (SELECT min(event_date) FROM events WHERE has_scores) AS first_score_date,
  (SELECT max(event_date) FROM events WHERE has_scores) AS last_score_date,
  (SELECT count(*) FROM events) AS n_events,
  (SELECT count(*) FROM events WHERE has_scores) AS n_scored_events,
  (SELECT count(*) FROM events WHERE results_complete) AS n_held_events,
  (SELECT count(*) FROM events WHERE has_stations) AS n_station_events,
  (SELECT count(*) FROM rounds) AS n_rounds,
  (SELECT count(*) FROM shooter_profiles) AS n_shooters,
  (SELECT value #>> '{}' FROM app_state WHERE key = 'last_rebuild_at')
    AS last_rebuild_at
"""


class MetaOut(BaseModel):
    app_version: str
    data_version: int
    first_event_date: date | None
    last_event_date: date | None
    first_score_date: date | None
    last_score_date: date | None
    n_events: int
    n_scored_events: int
    n_held_events: int
    n_station_events: int
    n_rounds: int
    n_shooters: int
    last_rebuild_at: datetime | None


@router.get("/api/meta")
def get_meta(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MetaOut:
    row = session.execute(text(_COUNTS_SQL)).mappings().one()
    return MetaOut(
        app_version=settings.app_version, data_version=read_data_version(session), **row
    )
```

- [ ] **Step 17: Register the middleware in `create_app()`**

In `backend/src/sunday_clays/api/app.py` add the import next to the other `sunday_clays.api` imports:

```python
from sunday_clays.api.etag import CacheHeadersMiddleware
```

and inside `create_app()`, after every existing `app.add_middleware(...)` call (Plan 01 T1's `BodySizeLimitMiddleware`, Plan 04 T1's `CsrfGuardMiddleware`), add this as the LAST middleware registration:

```python
    # Last registered = outermost: 403/413 replies from inner middlewares also get
    # Cache-Control (Plan 06 T1, C8).
    app.add_middleware(CacheHeadersMiddleware)
```

Change nothing else in `app.py` (no route wiring; `meta.py` is picked up by `discover_routers()` and protected by `require_viewer`).

- [ ] **Step 18: Run the ETag/meta tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/api/test_etag_helpers.py tests/integration/analytics_core/test_meta_route.py tests/integration/analytics_core/test_etag_middleware.py -v`
Expected: PASS — 38 passed (22 + 2 + 14).

- [ ] **Step 19: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: ruff/mypy report no issues; the whole suite passes (including Plan 04 T1's `test_route_auth_matrix.py`, which now also walks `/api/meta` → 401 without a cookie, 401 with `If-None-Match: *`); total coverage ≥ 90% lines and branches; `analytics/cache.py`, `analytics/frames.py`, `api/etag.py`, `api/routes/_convert.py`, `api/routes/_filters.py` and `api/routes/meta.py` each show 100%.

- [ ] **Step 20: Commit**

```bash
git add backend/src/sunday_clays/analytics/cache.py backend/src/sunday_clays/analytics/frames.py \
  backend/src/sunday_clays/api/etag.py backend/src/sunday_clays/api/routes/_filters.py \
  backend/src/sunday_clays/api/routes/_convert.py backend/src/sunday_clays/api/routes/meta.py \
  backend/src/sunday_clays/api/app.py backend/tests/conftest.py \
  backend/tests/unit/analytics_core backend/tests/unit/api/test_etag_helpers.py \
  backend/tests/unit/api/test_route_convert.py backend/tests/integration/analytics_core
git commit -m "feat(analytics): frames, data_version memo, ETag middleware and /api/meta

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 2: Round and event metrics + recompute step s10 (master Plan 06 T2)

**Branch:** `task/06-2-metrics-s10`

**Depends on:** Plan 06 T1.

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/metrics.py`
- Create: `backend/src/sunday_clays/analytics/steps/s10_metrics.py`
- Test: `backend/tests/unit/analytics_core/test_round_metrics.py`
- Test: `backend/tests/integration/analytics_core/test_s10_metrics_step.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_rounds(session) -> pd.DataFrame` (columns incl. `round_id, event_date, shooter_id, name_key, ordinal, score, held`, `is_best_round` bool), `frames.db_records(df) -> list[dict[str, object]]`, `cache.clear_cache() -> None`; unit fixture `make_rounds(specs, **defaults)` (tuple specs `(event_date, shooter_id, score)` or dicts; defaults `name_key "s<id>"`, `held True`, `round_id 1..n`, auto `ordinal`); integration fixture `seed` (`shooter`, `round`, `finish`).
  - C6: `sunday_clays.analytics.pipeline.RecomputeStep(name: str, order: int, run: Callable[[Session], None])`, `discover_steps() -> list[RecomputeStep]` (every module in `analytics/steps/` exposes `STEP`).
  - C5: `sunday_clays.domain.rules.RuleType.HIDE_ROUND`, `create_rule(session, rule_type, payload: dict, note: str | None) -> int` (fills `raw_score`), `sunday_clays.domain.rebuild.rebuild_live(session) -> RebuildReport`; C2 fixture `fx_session`.
  - C4 tables `round_metrics(round_id, field_median, adjusted, event_rank, is_best_round, percentile, ...)`, `event_metrics(event_date, n, median, mean, stdev, top_score, difficulty)`.
- Produces:
  - `sunday_clays.analytics.metrics`: `ROUND_METRIC_COLUMNS`, `EVENT_METRIC_COLUMNS`, `BEST_ROUND_ORDER`; `best_round_mask(rounds: pd.DataFrame) -> pd.Series` (one True per (event_date, shooter_id): score desc, then name_key, then ordinal); `compute_round_metrics(rounds: pd.DataFrame) -> pd.DataFrame` (→ `round_id, field_median, adjusted, event_rank, is_best_round, percentile`, one row per input round); `compute_event_metrics(rounds: pd.DataFrame) -> pd.DataFrame` (→ `event_date, n, median, mean, stdev, top_score, difficulty` with `difficulty` NaN).
  - `sunday_clays.analytics.steps.s10_metrics`: `run(session: Session) -> None`; `STEP = RecomputeStep(name="metrics", order=10, run=run)`. It deletes and rewrites `round_metrics` (skill columns NULL until s30) and `event_metrics`, and calls `clear_cache()` before reading and after writing (Review Focus 2).

- [ ] **Step 1: Write the failing metric tests**

Create `backend/tests/unit/analytics_core/test_round_metrics.py`:

```python
import math
from collections.abc import Callable
from datetime import date

import pandas as pd

from sunday_clays.analytics.metrics import compute_event_metrics, compute_round_metrics

D = date(2026, 9, 13)
D0 = date(2026, 9, 6)


def _by_id(metrics: pd.DataFrame) -> dict[int, dict[str, object]]:
    return {int(r["round_id"]): r for r in metrics.to_dict(orient="records")}


def test_ties_share_min_rank(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D, 1, 45), (D, 2, 45), (D, 3, 40), (D, 4, 38)])

    m = _by_id(compute_round_metrics(rounds))

    assert [m[i]["event_rank"] for i in (1, 2, 3, 4)] == [1.0, 1.0, 3.0, 4.0]
    # average ranks 1.5, 1.5, 3, 4 over n_best = 4 -> (4 - r) / 3
    assert math.isclose(m[1]["percentile"], 2.5 / 3)
    assert math.isclose(m[2]["percentile"], 2.5 / 3)
    assert math.isclose(m[3]["percentile"], 1 / 3)
    assert m[4]["percentile"] == 0.0


def test_best_round_used_for_rank(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds(
        [
            {"event_date": D, "shooter_id": 1, "score": 30, "round_id": 10},
            {"event_date": D, "shooter_id": 1, "score": 44, "round_id": 11},
            {"event_date": D, "shooter_id": 2, "score": 42, "round_id": 12},
        ]
    )

    m = _by_id(compute_round_metrics(rounds))

    assert m[11]["is_best_round"] is True
    assert m[11]["event_rank"] == 1.0
    assert m[10]["is_best_round"] is False
    assert math.isnan(m[10]["event_rank"])
    assert math.isnan(m[10]["percentile"])
    assert m[12]["event_rank"] == 2.0
    # median of all three rounds (30, 42, 44) is 42; both of shooter 1's rounds count
    assert [m[i]["field_median"] for i in (10, 11, 12)] == [42.0, 42.0, 42.0]
    assert [m[i]["adjusted"] for i in (10, 11, 12)] == [-12.0, 2.0, 0.0]
    assert m[11]["percentile"] == 1.0
    assert m[12]["percentile"] == 0.0


def test_merged_aliases_same_day_single_best_round(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {
                "event_date": D,
                "shooter_id": 7,
                "score": 40,
                "name_key": "tarleton amos",
                "ordinal": 1,
                "round_id": 1,
            },
            {
                "event_date": D,
                "shooter_id": 7,
                "score": 40,
                "name_key": "tarleton wylie",
                "ordinal": 1,
                "round_id": 2,
            },
            {"event_date": D, "shooter_id": 8, "score": 39, "round_id": 3},
        ]
    )

    m = _by_id(compute_round_metrics(rounds))

    assert [m[i]["is_best_round"] for i in (1, 2, 3)] == [False, True, True]
    assert m[2]["event_rank"] == 1.0
    assert m[3]["event_rank"] == 2.0
    # n_best counts distinct shooters (2), not rounds (3)
    assert m[3]["percentile"] == 0.0


def test_equal_scores_same_name_key_pick_lowest_ordinal(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {
                "event_date": D,
                "shooter_id": 5,
                "score": 40,
                "ordinal": 2,
                "round_id": 1,
            },
            {
                "event_date": D,
                "shooter_id": 5,
                "score": 40,
                "ordinal": 1,
                "round_id": 2,
            },
        ]
    )

    m = _by_id(compute_round_metrics(rounds))

    assert [m[1]["is_best_round"], m[2]["is_best_round"]] == [False, True]


def test_non_held_event_has_ranks_but_no_field_metrics(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(D0, 1, 40), (D0, 2, 30)], held=False)

    m = _by_id(compute_round_metrics(rounds))

    assert [m[1]["event_rank"], m[2]["event_rank"]] == [1.0, 2.0]
    assert all(
        math.isnan(m[i][c])
        for i in (1, 2)
        for c in ("field_median", "adjusted", "percentile")
    )


def test_single_shooter_percentile_is_one(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    m = _by_id(compute_round_metrics(make_rounds([(D, 1, 20)])))
    assert m[1]["percentile"] == 1.0
    assert m[1]["event_rank"] == 1.0


def test_ranks_are_per_event(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D0, 1, 20), (D0, 2, 25), (D, 1, 30), (D, 2, 10)])

    metrics = compute_round_metrics(rounds)
    joined = rounds[["round_id", "event_date", "shooter_id"]].merge(
        metrics, on="round_id"
    )
    ranks = {(r.event_date, r.shooter_id): r.event_rank for r in joined.itertuples()}

    assert ranks == {(D0, 1): 2.0, (D0, 2): 1.0, (D, 1): 1.0, (D, 2): 2.0}


def test_empty_frames_have_the_output_columns(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    empty = make_rounds([(D, 1, 20)]).iloc[0:0]
    assert list(compute_round_metrics(empty).columns) == [
        "round_id",
        "field_median",
        "adjusted",
        "event_rank",
        "is_best_round",
        "percentile",
    ]
    assert compute_event_metrics(empty).empty


def test_event_metrics_per_event(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D0, 1, 20), (D0, 2, 30), (D0, 1, 40), (D, 3, 25)])

    ev = compute_event_metrics(rounds).set_index("event_date")

    assert ev.loc[D0, "n"] == 3
    assert ev.loc[D0, "median"] == 30.0
    assert ev.loc[D0, "mean"] == 30.0
    assert ev.loc[D0, "stdev"] == 10.0
    assert ev.loc[D0, "top_score"] == 40
    assert ev.loc[D, "n"] == 1
    assert math.isnan(ev.loc[D, "stdev"])
    assert ev["difficulty"].isna().all()
```

- [ ] **Step 2: Run the metric tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_round_metrics.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.analytics.metrics'`.

- [ ] **Step 3: Implement `analytics/metrics.py`**

Create `backend/src/sunday_clays/analytics/metrics.py`:

```python
"""Per-round and per-event field metrics (C7): best round, rank, percentile."""

import pandas as pd

ROUND_METRIC_COLUMNS: tuple[str, ...] = (
    "round_id",
    "field_median",
    "adjusted",
    "event_rank",
    "is_best_round",
    "percentile",
)
EVENT_METRIC_COLUMNS: tuple[str, ...] = (
    "event_date",
    "n",
    "median",
    "mean",
    "stdev",
    "top_score",
    "difficulty",
)
BEST_ROUND_ORDER: tuple[str, ...] = (
    "event_date",
    "shooter_id",
    "score",
    "name_key",
    "ordinal",
)


def best_round_mask(rounds: pd.DataFrame) -> pd.Series:
    """One True per (event_date, shooter_id): score desc, then name_key, ordinal."""
    ordered = rounds.sort_values(
        list(BEST_ROUND_ORDER),
        ascending=[True, True, False, True, True],
        kind="mergesort",
    )
    first = ~ordered.duplicated(["event_date", "shooter_id"], keep="first")
    return first.reindex(rounds.index)


def compute_round_metrics(rounds: pd.DataFrame) -> pd.DataFrame:
    """Field metrics for every round.

    Input columns: round_id, event_date, shooter_id, name_key, ordinal, score, held.
    Output columns: ROUND_METRIC_COLUMNS, one row per input round (same order).
    - field_median/adjusted: median of all rounds that day / score - median; NaN when
      the event is not held.
    - is_best_round: first round per (event_date, shooter_id) by score desc, name_key,
      ordinal.
    - event_rank: min-rank of best rounds by score (ties share); NaN for other rounds.
    - percentile: (n_best - average rank) / (n_best - 1), 1.0 when n_best == 1; NaN for
      non-best rounds and at non-held events.
    """
    if rounds.empty:
        return pd.DataFrame(
            {c: pd.Series(dtype="float64") for c in ROUND_METRIC_COLUMNS}
        )
    held = rounds["held"].astype(bool)
    median = rounds.groupby("event_date")["score"].transform("median").astype("float64")
    best = best_round_mask(rounds)
    best_scores = rounds.loc[best, ["event_date", "score"]]
    by_event = best_scores.groupby("event_date")["score"]
    rank_min = by_event.rank(method="min", ascending=False)
    rank_avg = by_event.rank(method="average", ascending=False)
    n_best = by_event.transform("size").astype("float64")
    denominator = (n_best - 1).where(n_best > 1)
    percentile = ((n_best - rank_avg) / denominator).where(n_best > 1, 1.0)
    percentile = percentile.where(held.loc[best])
    return pd.DataFrame(
        {
            "round_id": rounds["round_id"],
            "field_median": median.where(held),
            "adjusted": (rounds["score"] - median).where(held),
            "event_rank": rank_min.reindex(rounds.index),
            "is_best_round": best,
            "percentile": percentile.reindex(rounds.index),
        }
    ).reset_index(drop=True)


def compute_event_metrics(rounds: pd.DataFrame) -> pd.DataFrame:
    """Per scored event: n rounds, median, mean, sample stdev (NaN for n=1), top score.

    `difficulty` is NaN here; the s30 skill step fills it.
    """
    if rounds.empty:
        return pd.DataFrame(
            {c: pd.Series(dtype="float64") for c in EVENT_METRIC_COLUMNS}
        )
    scores = rounds.groupby("event_date")["score"]
    out = pd.DataFrame(
        {
            "n": scores.size(),
            "median": scores.median().astype("float64"),
            "mean": scores.mean(),
            "stdev": scores.std(ddof=1),
            "top_score": scores.max(),
        }
    ).reset_index()
    out["difficulty"] = float("nan")
    return out[list(EVENT_METRIC_COLUMNS)]
```

- [ ] **Step 4: Run the metric tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_round_metrics.py -v`
Expected: PASS — 9 passed.

- [ ] **Step 5: Write the failing s10 step tests**

Create `backend/tests/integration/analytics_core/test_s10_metrics_step.py`. The fixture case is computed from `scores_2026-09-27.xlsx`: on 2020-03-01 "ackerly alton" shot 48 (ordinal 1) and 43 (ordinal 2) among 40 shooters; with the 48 hidden, his 43 is his best round and ranks 5th (47, 46, 46, 44 ahead), and "hamlin ethan" (47) wins.

```python
from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.pipeline import discover_steps
from sunday_clays.analytics.steps import s10_metrics
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule

D = date(2026, 9, 13)


def test_s10_is_discovered_at_order_10() -> None:
    steps = {s.name: s.order for s in discover_steps()}
    assert steps["metrics"] == 10


def test_s10_writes_round_and_event_metrics(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    a1 = seed.round(D, ann, 44)
    a2 = seed.round(D, ann, 30)
    b1 = seed.round(D, bob, 42)
    seed.finish()

    s10_metrics.STEP.run(session)

    rows = session.execute(
        text(
            "SELECT round_id, field_median, adjusted, event_rank, is_best_round,"
            " percentile"
            " FROM round_metrics ORDER BY round_id"
        )
    ).all()
    assert [tuple(r) for r in rows] == [
        (a1, 42.0, 2.0, 1, True, 1.0),
        (a2, 42.0, -12.0, None, False, None),
        (b1, 42.0, 0.0, 2, True, 0.0),
    ]
    event = session.execute(
        text("SELECT n, median, mean, top_score, difficulty FROM event_metrics")
    ).one()
    # event_metrics.mean is `real` (float4)
    assert tuple(event) == (3, 42.0, pytest.approx(116 / 3, rel=1e-6), 44, None)


def test_s10_leaves_no_stale_memo(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D, ann, 40)
    seed.finish()
    assert not frames.load_rounds(session)["is_best_round"].any()  # memoized, pre-s10

    # run_pipeline bumps data_version only after all steps, so nothing bumps it here
    s10_metrics.STEP.run(session)

    assert frames.load_rounds(session)["is_best_round"].tolist() == [True]


def test_s10_rerun_replaces_rows(seed: Any, session: Session) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D, ann, 40)
    seed.finish()
    s10_metrics.STEP.run(session)
    s10_metrics.STEP.run(session)
    assert session.execute(text("SELECT count(*) FROM round_metrics")).scalar_one() == 1
    assert session.execute(text("SELECT count(*) FROM event_metrics")).scalar_one() == 1


def test_s10_on_empty_live_tables(session: Session) -> None:
    s10_metrics.STEP.run(session)
    assert session.execute(text("SELECT count(*) FROM round_metrics")).scalar_one() == 0


def test_hide_best_round_promotes_other_round(fx_session: Session) -> None:
    # 2020-03-01: "ackerly alton" shot 48 (ordinal 1) and 43 (ordinal 2); 40 shooters.
    create_rule(
        fx_session,
        RuleType.HIDE_ROUND,
        {"event_date": "2020-03-01", "name_key": "ackerly alton", "ordinal": 1},
        "test: hide best round",
    )
    rebuild_live(fx_session)

    s10_metrics.STEP.run(fx_session)

    rows = fx_session.execute(
        text(
            "SELECT r.ordinal, r.score, m.is_best_round, m.event_rank FROM rounds r"
            " JOIN round_metrics m ON m.round_id = r.id"
            " WHERE r.event_date = '2020-03-01' AND r.name_key = 'ackerly alton'"
        )
    ).all()
    assert [tuple(r) for r in rows] == [(2, 43, True, 5)]
    leader = fx_session.execute(
        text(
            "SELECT r.name_key FROM rounds r JOIN round_metrics m ON m.round_id = r.id"
            " WHERE r.event_date = '2020-03-01' AND m.event_rank = 1"
        )
    ).scalar_one()
    assert leader == "hamlin ethan"
```

(`rebuild_live` inside `fx_session` runs in the per-test savepoint and is rolled back at teardown; it neither runs the worker nor opens its own `SessionFactory`, as C2 requires for `fx_*` tests.)

- [ ] **Step 6: Run the s10 tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_s10_metrics_step.py -v`
Expected: collection ERROR — `ImportError: cannot import name 's10_metrics' from 'sunday_clays.analytics.steps'`.

- [ ] **Step 7: Implement `steps/s10_metrics.py`**

Create `backend/src/sunday_clays/analytics/steps/s10_metrics.py`:

```python
"""Recompute step 10: round_metrics field columns and event_metrics (C6/C7)."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.metrics import compute_event_metrics, compute_round_metrics
from sunday_clays.analytics.pipeline import RecomputeStep

_INSERT_ROUND_METRICS = """
INSERT INTO round_metrics
    (round_id, field_median, adjusted, event_rank, is_best_round, percentile)
VALUES (:round_id, :field_median, :adjusted, :event_rank, :is_best_round, :percentile)
"""
_INSERT_EVENT_METRICS = """
INSERT INTO event_metrics (event_date, n, median, mean, stdev, top_score, difficulty)
VALUES (:event_date, :n, :median, :mean, :stdev, :top_score, :difficulty)
"""


def run(session: Session) -> None:
    """Rewrite round_metrics (skill columns NULL until s30) and event_metrics."""
    clear_cache()
    rounds = frames.load_rounds(session)
    round_metrics = compute_round_metrics(rounds)
    round_metrics["event_rank"] = round_metrics["event_rank"].astype("Int64")
    event_metrics = compute_event_metrics(rounds)
    session.execute(text("DELETE FROM round_metrics"))
    session.execute(text("DELETE FROM event_metrics"))
    if not round_metrics.empty:
        session.execute(text(_INSERT_ROUND_METRICS), frames.db_records(round_metrics))
        session.execute(text(_INSERT_EVENT_METRICS), frames.db_records(event_metrics))
    clear_cache()


STEP = RecomputeStep(name="metrics", order=10, run=run)
```

- [ ] **Step 8: Run the s10 tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_s10_metrics_step.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 9: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass (the `fx_engine` pipeline now also runs s10); coverage ≥ 90% lines and branches, with `analytics/metrics.py` and `analytics/steps/s10_metrics.py` at 100%.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/metrics.py \
  backend/src/sunday_clays/analytics/steps/s10_metrics.py \
  backend/tests/unit/analytics_core/test_round_metrics.py \
  backend/tests/integration/analytics_core/test_s10_metrics_step.py
git commit -m "feat(analytics): best-round ranks, percentiles and recompute step s10

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 3: Skill model — filter, calibration and predictions (master Plan 06 T3)

**Branch:** `task/06-3-skill-model`

**Depends on:** Plan 06 T1. Runs in parallel with Task 2 (disjoint files).

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/skill.py`
- Test: `backend/tests/unit/analytics_core/test_skill_model.py`
- Test: `backend/tests/unit/analytics_core/test_skill_calibrate_predict.py`

**Interfaces:**
- Consumes: Task 1 unit fixture `make_rounds(specs, **defaults) -> pd.DataFrame` (tuple specs `(event_date, shooter_id, score)` or dicts; defaults `name_key "s<id>"`, `held True`, `round_id 1..n`, auto `ordinal`). Pure module: no DB, no other Plan 06 code.
- Produces (`sunday_clays.analytics.skill`, C7 names verbatim plus the extras marked *):
  - `DEFAULT_GRID` (270 points) and `CALIBRATION_GRID` (27 points) exactly as C7; `GRID_KEYS`* = `("obs_var", "drift_var_per_week", "difficulty_var", "prior_mu", "prior_var")`; `BURN_IN_HELD_EVENTS = 8`*; `LEVEL_WINDOW = timedelta(days=364)`*; `ROUND_OUTPUT_COLUMNS`*, `EVENT_OUTPUT_COLUMNS`*, `HISTORY_COLUMNS`*, `PREDICTION_COLUMNS`*.
  - `@dataclass(frozen=True) class SkillParams: prior_mu: float = 30.0; prior_var: float = 49.0; obs_var: float = 14.0; drift_var_per_week: float = 0.3; difficulty_var: float = 4.0; max_var: float = 49.0`; `DEFAULT_PARAMS = SkillParams()`*.
  - `@dataclass(frozen=True) class SkillResult: rounds: pd.DataFrame` (round_id, expected, residual, mu_before, var_before, mu_after, var_after; mu_* on the published scale) `; events: pd.DataFrame` (event_date, difficulty (published), d_raw, level) `; history: pd.DataFrame` (shooter_id, event_date, mu (published), var) `; final_state: dict[int, tuple[float, float, date]]` (raw scale) `; current_level: float`.
  - `run_skill_model(rounds: pd.DataFrame, params: SkillParams = DEFAULT_PARAMS) -> SkillResult` — required input columns `round_id, event_date, shooter_id, name_key, ordinal, score, held`.
  - `calibrate(rounds: pd.DataFrame, grid: Mapping[str, Sequence[float]] = DEFAULT_GRID) -> SkillParams`.
  - `predict(state: Mapping[int, tuple[float, float, date]], shooter_ids: Sequence[int], on: date, params: SkillParams, level: float, difficulty: float | None = None, difficulty_sd: float = 0.0, attend_prob: Mapping[int, float] | None = None, n_sims: int = 10_000, seed: int = 0) -> pd.DataFrame` → `shooter_id, attend_prob, expected, sd, p_win, p_podium`.
  - Semantics the tests pin (C7 + Decisions 8–13): per held event, `R_i = obs_var/k_i`, `w_i = 1/(var_i + R_i)`, `P = Σw + 1/difficulty_var`, `d = Σ w r / P`, `d_-i = (D − w_i r_i)/(P − w_i)`, `K_i = var_i/(var_i + R_i + 1/(P − w_i))`, `mu_i += K_i(ȳ_i − mu_i − d_-i)`, `var_i *= (1 − K_i)`; `expected = mu_i + d_-i` (= published `mu_before` − published leave-one-out difficulty), `residual = y − expected`. C7 step 4's literal `mu_i + d_-i + L_t` is not what to build: its own "the L_t terms cancel, so the residual is unchanged" holds only for this form (Decision 8), and `predict`'s `expected = mu + level − difficulty` agrees with it; published rating `mu + L_t`, difficulty `−(d_t − L_t)`, `L_t` = mean raw `d` over held events in `(t − 364d, t]`; non-held events carry drift-inflated state forward with NaN expected/residual/difficulty.

- [ ] **Step 1: Write the failing filter tests**

Create `backend/tests/unit/analytics_core/test_skill_model.py`. `test_update_equals_closed_form_loo` checks the filter against an independent joint-Gaussian posterior (C7 step 5's closed form); do NOT add any test that residual means by ordinal ≈ 0 (ordinals are sorted by score, so a ±1.9 split is inherent).

```python
import math
from collections.abc import Callable
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.skill import SkillParams, run_skill_model

D = date(2026, 1, 4)


def simulate(
    seed: int,
    n_shooters: int,
    n_events: int,
    *,
    drift: float = 0.0,
    obs_var: float = 14.0,
    difficulty_var: float = 4.0,
    attend: float = 0.6,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Weekly held events; skills ~ N(30, 49) random-walking with `drift` per week."""
    rng = np.random.default_rng(seed)
    skills = rng.normal(30.0, 7.0, n_shooters)
    rows = []
    for t in range(n_events):
        if t:
            skills = skills + rng.normal(0.0, math.sqrt(drift), n_shooters)
        day = rng.normal(0.0, math.sqrt(difficulty_var))
        for s in np.flatnonzero(rng.random(n_shooters) < attend):
            y = np.clip(
                np.rint(skills[s] + day + rng.normal(0.0, math.sqrt(obs_var))), 0, 50
            )
            rows.append(
                (
                    len(rows) + 1,
                    D + timedelta(days=7 * t),
                    int(s) + 1,
                    f"s{s + 1}",
                    1,
                    int(y),
                    True,
                )
            )
    columns = [
        "round_id",
        "event_date",
        "shooter_id",
        "name_key",
        "ordinal",
        "score",
        "held",
    ]
    return pd.DataFrame(rows, columns=columns), skills


def test_update_equals_closed_form_loo(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    # One held event, three new shooters; shooter 1 shot two rounds.
    rounds = make_rounds(
        [
            {"event_date": D, "shooter_id": 1, "score": 40, "round_id": 1},
            {"event_date": D, "shooter_id": 1, "score": 34, "round_id": 2},
            {"event_date": D, "shooter_id": 2, "score": 28, "round_id": 3},
            {"event_date": D, "shooter_id": 3, "score": 33, "round_id": 4},
        ]
    )
    p = SkillParams()
    result = run_skill_model(rounds, p)

    # Independent joint-Gaussian posterior over theta = (mu1, mu2, mu3, d);
    # one design row per round.
    design = np.array(
        [[1, 0, 0, 1], [1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1]], dtype=float
    )
    y = np.array([40.0, 34.0, 28.0, 33.0])
    prior_mean = np.array([30.0, 30.0, 30.0, 0.0])
    prior_prec = np.diag([1 / 49, 1 / 49, 1 / 49, 1 / 4])

    def posterior(rows: list[int]) -> tuple[np.ndarray, np.ndarray]:
        h = design[rows]
        cov = np.linalg.inv(prior_prec + h.T @ h / p.obs_var)
        return cov @ (prior_prec @ prior_mean + h.T @ y[rows] / p.obs_var), cov

    mean, cov = posterior([0, 1, 2, 3])
    level = result.events["level"].iloc[0]
    by_round = result.rounds.set_index("round_id")
    assert result.events["d_raw"].iloc[0] == pytest.approx(mean[3])
    for rid, j in ((1, 0), (3, 1), (4, 2)):
        assert by_round.loc[rid, "mu_after"] - level == pytest.approx(mean[j])
        assert by_round.loc[rid, "var_after"] == pytest.approx(cov[j, j])
    # expected = mu_i + E[d | everyone else's rounds]
    d_without = {
        1: posterior([2, 3])[0][3],
        3: posterior([0, 1, 3])[0][3],
        4: posterior([0, 1, 2])[0][3],
    }
    for rid, d_loo in d_without.items():
        assert by_round.loc[rid, "expected"] == pytest.approx(30.0 + d_loo)
    assert by_round.loc[2, "expected"] == pytest.approx(30.0 + d_without[1])


def test_same_day_rounds_share_pre_event_state(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            (D, 1, 35),
            (D, 2, 30),
            (D + timedelta(days=7), 1, 44),
            (D + timedelta(days=7), 1, 38),
            (D + timedelta(days=7), 2, 31),
        ]
    )
    out = run_skill_model(rounds).rounds.merge(
        rounds[["round_id", "event_date", "shooter_id"]]
    )
    pair = out[(out["shooter_id"] == 1) & (out["event_date"] == D + timedelta(days=7))]

    assert len(pair) == 2
    for column in ("mu_before", "var_before", "mu_after", "var_after", "expected"):
        assert pair[column].nunique() == 1
    assert pair["residual"].max() - pair["residual"].min() == pytest.approx(6.0)


def test_published_difficulty_sign_and_centering(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rng = np.random.default_rng(7)
    specs = []
    for week in range(60):
        bump = 8 if week == 59 else 0
        for shooter in range(1, 11):
            specs.append(
                (
                    D + timedelta(days=7 * week),
                    shooter,
                    25 + shooter + bump + int(rng.integers(-2, 3)),
                )
            )
    events = run_skill_model(make_rounds(specs)).events

    assert events["difficulty"].iloc[-1] < -3  # everyone shot 8 higher: an easy day
    for i, row in events.iterrows():
        window = events[
            (events["event_date"] > row["event_date"] - timedelta(days=364))
            & (events.index <= i)
        ]
        assert row["level"] == pytest.approx(window["d_raw"].mean())
        assert row["difficulty"] == pytest.approx(-(row["d_raw"] - row["level"]))
    assert len(window) == 52  # the window really drops events older than 364 days


def test_non_held_event_carries_state_forward(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d2, d3 = D + timedelta(days=14), D + timedelta(days=28)
    rounds = make_rounds(
        [
            (D, 1, 35),
            (D, 2, 30),
            {"event_date": d2, "shooter_id": 1, "score": 20, "held": False},
            (d3, 1, 36),
            (d3, 2, 29),
        ]
    )
    p = SkillParams()
    result = run_skill_model(rounds, p)
    out = result.rounds.merge(rounds[["round_id", "event_date", "shooter_id"]])
    first = out[(out["shooter_id"] == 1) & (out["event_date"] == D)].iloc[0]
    carried = out[out["event_date"] == d2].iloc[0]
    third = out[(out["shooter_id"] == 1) & (out["event_date"] == d3)].iloc[0]
    events = result.events.set_index("event_date")

    assert math.isnan(carried["expected"])
    assert math.isnan(carried["residual"])
    assert (
        carried["mu_before"] == carried["mu_after"] == pytest.approx(first["mu_after"])
    )
    assert carried["var_before"] == pytest.approx(
        first["var_after"] + 2 * p.drift_var_per_week
    )
    assert carried["var_after"] == carried["var_before"]
    assert math.isnan(events.loc[d2, "difficulty"])
    assert events.loc[d2, "level"] == events.loc[D, "level"]
    assert third["var_before"] == pytest.approx(
        carried["var_after"] + 2 * p.drift_var_per_week
    )
    history = result.history[result.history["shooter_id"] == 1]
    assert history["event_date"].tolist() == [D, d2, d3]


def test_level_is_zero_until_the_first_held_event(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [{"event_date": D, "shooter_id": 1, "score": 30, "held": False}]
    )
    result = run_skill_model(rounds)
    assert result.events["level"].tolist() == [0.0]
    assert result.current_level == 0.0
    assert result.history["mu"].tolist() == [30.0]  # prior_mu + level 0


def test_variance_is_capped_at_max_var(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    later = D + timedelta(days=7 * 520)
    rounds = make_rounds([(D, 1, 35), (D, 2, 30), (later, 1, 36), (later, 2, 31)])
    out = run_skill_model(rounds).rounds.merge(rounds[["round_id", "event_date"]])
    assert (out[out["event_date"] == later]["var_before"] == 49.0).all()


def test_history_and_final_state(make_rounds: Callable[..., pd.DataFrame]) -> None:
    rounds = make_rounds([(D, 1, 35), (D, 2, 30), (D + timedelta(days=7), 1, 40)])
    result = run_skill_model(rounds)
    merged = result.rounds.merge(rounds[["round_id", "event_date", "shooter_id"]])
    last = merged.iloc[-1]
    level = result.current_level

    mu, var, last_date = result.final_state[1]
    assert last_date == D + timedelta(days=7)
    assert mu + level == pytest.approx(last["mu_after"])
    assert var == pytest.approx(last["var_after"])
    assert result.final_state[2][2] == D
    assert level == result.events["level"].iloc[-1]
    assert len(result.history) == 3


def test_empty_rounds_give_empty_result(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    result = run_skill_model(make_rounds([(D, 1, 30)]).iloc[0:0])
    assert result.rounds.empty
    assert result.events.empty
    assert result.history.empty
    assert result.final_state == {}
    assert result.current_level == 0.0


def test_no_leak_fixed_params(make_rounds: Callable[..., pd.DataFrame]) -> None:
    past, _ = simulate(3, 12, 30)
    future, _ = simulate(4, 12, 10)
    cutoff = past["event_date"].max()
    future = future.assign(
        round_id=future["round_id"] + 10_000,
        event_date=[d + timedelta(days=7 * 40) for d in future["event_date"]],
    )
    alone = run_skill_model(past)
    extended = run_skill_model(pd.concat([past, future], ignore_index=True))

    def upto(result_frame: pd.DataFrame, key: str) -> pd.DataFrame:
        return result_frame.sort_values(key).reset_index(drop=True)

    pd.testing.assert_frame_equal(
        upto(alone.rounds, "round_id"),
        upto(extended.rounds[extended.rounds["round_id"] < 10_000], "round_id"),
    )
    pd.testing.assert_frame_equal(
        alone.events, extended.events[extended.events["event_date"] <= cutoff]
    )
    pd.testing.assert_frame_equal(
        alone.history,
        extended.history[extended.history["event_date"] <= cutoff].reset_index(
            drop=True
        ),
    )


def test_synthetic_skills_recovered() -> None:
    rounds, skills = simulate(0, 30, 120)
    result = run_skill_model(rounds)
    published = np.array(
        [
            result.final_state[s + 1][0] + result.current_level
            for s in range(len(skills))
        ]
    )
    assert np.abs(published - skills).mean() < 1.6
    assert np.corrcoef(published, skills)[0, 1] > 0.95
```

- [ ] **Step 2: Write the failing calibration and prediction tests**

Create `backend/tests/unit/analytics_core/test_skill_calibrate_predict.py` (the simulated populations are drawn from the model itself; the three parametrized cases recover their generating point exactly and each calibration takes ~0.3 s):

```python
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from sunday_clays.analytics.skill import (
    CALIBRATION_GRID,
    SkillParams,
    calibrate,
    predict,
    run_skill_model,
)

D = date(2026, 1, 4)
ON = date(2026, 10, 4)


def simulate(
    seed: int,
    n_shooters: int,
    n_events: int,
    *,
    drift: float,
    obs_var: float,
    difficulty_var: float,
    attend: float = 0.6,
) -> pd.DataFrame:
    """Data drawn from the model itself: N(30, 49) skills, weekly held events."""
    rng = np.random.default_rng(seed)
    skills = rng.normal(30.0, 7.0, n_shooters)
    rows = []
    for t in range(n_events):
        if t:
            skills = skills + rng.normal(0.0, math.sqrt(drift), n_shooters)
        day = rng.normal(0.0, math.sqrt(difficulty_var))
        for s in np.flatnonzero(rng.random(n_shooters) < attend):
            y = np.clip(
                np.rint(skills[s] + day + rng.normal(0.0, math.sqrt(obs_var))), 0, 50
            )
            rows.append(
                (
                    len(rows) + 1,
                    D + timedelta(days=7 * t),
                    int(s) + 1,
                    f"s{s + 1}",
                    1,
                    int(y),
                    True,
                )
            )
    columns = [
        "round_id",
        "event_date",
        "shooter_id",
        "name_key",
        "ordinal",
        "score",
        "held",
    ]
    return pd.DataFrame(rows, columns=columns)


@pytest.mark.parametrize(
    ("obs_var", "drift", "difficulty_var"),
    [(14.0, 0.15, 4.0), (16.0, 0.05, 9.0), (12.0, 0.3, 2.0)],
)
def test_calibrate_recovers_generating_params(
    obs_var: float, drift: float, difficulty_var: float
) -> None:
    rounds = simulate(
        200, 60, 150, drift=drift, obs_var=obs_var, difficulty_var=difficulty_var
    )

    best = calibrate(rounds, CALIBRATION_GRID)

    assert (best.obs_var, best.drift_var_per_week, best.difficulty_var) == (
        obs_var,
        drift,
        difficulty_var,
    )
    assert (best.prior_mu, best.prior_var, best.max_var) == (30.0, 49.0, 49.0)


def test_calibrate_ties_keep_lexicographically_first_point() -> None:
    # 8 held events are all burn-in, so every grid point scores 0.0.
    rounds = simulate(1, 10, 8, drift=0.15, obs_var=14.0, difficulty_var=4.0)
    grid = {**CALIBRATION_GRID, "obs_var": (16, 12), "prior_var": (49, 36)}

    best = calibrate(rounds, grid)

    assert best == SkillParams(
        prior_mu=30.0,
        prior_var=36.0,
        obs_var=12.0,
        drift_var_per_week=0.05,
        difficulty_var=2.0,
        max_var=36.0,
    )


def _state(
    *items: tuple[int, float, float, date],
) -> dict[int, tuple[float, float, date]]:
    return {sid: (mu, var, last) for sid, mu, var, last in items}


TINY = SkillParams(obs_var=1e-6, drift_var_per_week=0.0)


def test_predict_expected_and_sd_formula() -> None:
    p = SkillParams()
    state = _state(
        (1, 30.0, 1.0, ON - timedelta(days=70)),
        (3, 25.0, 40.0, ON - timedelta(days=700)),
    )

    out = predict(
        state,
        [1, 2, 3],
        ON,
        p,
        level=1.5,
        difficulty=2.0,
        difficulty_sd=3.0,
        n_sims=200,
    ).set_index("shooter_id")

    assert out.loc[1, "expected"] == pytest.approx(30.0 + 1.5 - 2.0)
    assert out.loc[1, "sd"] == pytest.approx(math.sqrt(1.0 + 0.3 * 10 + 14.0 + 9.0))
    assert out.loc[2, "expected"] == pytest.approx(30.0 + 1.5 - 2.0)  # unknown -> prior
    assert out.loc[2, "sd"] == pytest.approx(math.sqrt(49.0 + 14.0 + 9.0))
    # shooter 3's variance is capped at max_var (= prior_var 49)
    assert out.loc[3, "sd"] == pytest.approx(math.sqrt(49.0 + 14.0 + 9.0))
    assert out["attend_prob"].tolist() == [1.0, 1.0, 1.0]
    no_difficulty = predict(state, [1], ON, p, level=1.5, n_sims=10)
    assert no_difficulty["expected"].iloc[0] == pytest.approx(31.5)


def test_predict_ties_count_as_wins() -> None:
    state = _state((1, 35.0, 1e-6, ON), (2, 35.0, 1e-6, ON))
    out = predict(state, [1, 2], ON, TINY, level=0.0, n_sims=500)
    assert out["p_win"].tolist() == [1.0, 1.0]
    assert out["p_podium"].tolist() == [1.0, 1.0]


def test_predict_attendance_scales_field() -> None:
    state = _state((1, 30.0, 1e-6, ON), (2, 45.0, 1e-6, ON), (3, 44.0, 1e-6, ON))
    everyone = predict(state, [1, 2, 3], ON, TINY, level=0.0, n_sims=500)
    alone = predict(
        state,
        [1, 2, 3],
        ON,
        TINY,
        level=0.0,
        n_sims=500,
        attend_prob={1: 1.0, 2: 0.0, 3: 0.0},
    )

    assert everyone["p_win"].iloc[0] == 0.0
    assert alone["p_win"].iloc[0] == 1.0
    assert alone["attend_prob"].tolist() == [1.0, 0.0, 0.0]
    # shooter 2 never attends, so its conditional odds are undefined
    assert math.isnan(alone["p_win"].iloc[1])


def test_predict_podium_counts_strictly_better_shooters() -> None:
    state = _state(
        (1, 40.0, 1e-6, ON),
        (2, 35.0, 1e-6, ON),
        (3, 30.0, 1e-6, ON),
        (4, 25.0, 1e-6, ON),
    )
    out = predict(state, [1, 2, 3, 4], ON, TINY, level=0.0, n_sims=200)
    assert out["p_podium"].tolist() == [1.0, 1.0, 1.0, 0.0]
    assert out["p_win"].tolist() == [1.0, 0.0, 0.0, 0.0]


def test_predict_one_shared_day_effect_per_simulation() -> None:
    state = _state((1, 30.0, 1e-6, ON), (2, 31.0, 1e-6, ON))
    out = predict(state, [1, 2], ON, TINY, level=0.0, difficulty_sd=10.0, n_sims=4000)
    # A shared effect keeps the 1-point gap; shooter 1 only ties when both clip at 50.
    assert out["p_win"].iloc[1] == 1.0
    assert out["p_win"].iloc[0] < 0.1


def test_predict_integer_level_shift_leaves_odds_unchanged() -> None:
    state = _state((1, 30.0, 4.0, ON), (2, 28.0, 4.0, ON), (3, 26.0, 9.0, ON))
    base = predict(state, [1, 2, 3], ON, SkillParams(), level=0.0, n_sims=3000, seed=5)
    shifted = predict(
        state, [1, 2, 3], ON, SkillParams(), level=3.0, n_sims=3000, seed=5
    )
    assert shifted["p_win"].tolist() == base["p_win"].tolist()
    assert shifted["p_podium"].tolist() == base["p_podium"].tolist()
    assert (shifted["expected"] - base["expected"]).tolist() == [3.0, 3.0, 3.0]


def test_predict_is_seeded() -> None:
    state = _state((1, 30.0, 4.0, ON), (2, 29.0, 4.0, ON))
    a = predict(state, [1, 2], ON, SkillParams(), level=0.0, n_sims=2000, seed=1)
    b = predict(state, [1, 2], ON, SkillParams(), level=0.0, n_sims=2000, seed=1)
    c = predict(state, [1, 2], ON, SkillParams(), level=0.0, n_sims=2000, seed=2)
    pd.testing.assert_frame_equal(a, b)
    assert a["p_win"].tolist() != c["p_win"].tolist()


def test_predict_single_and_no_shooters() -> None:
    solo = predict(
        _state((1, 30.0, 4.0, ON)), [1], ON, SkillParams(), level=0.0, n_sims=100
    )
    assert solo["p_win"].tolist() == [1.0]
    empty = predict({}, [], ON, SkillParams(), level=0.0)
    assert empty.empty
    assert list(empty.columns) == [
        "shooter_id",
        "attend_prob",
        "expected",
        "sd",
        "p_win",
        "p_podium",
    ]


def test_predict_expected_matches_recent_scores() -> None:
    rounds = simulate(102, 40, 100, drift=0.0, obs_var=14.0, difficulty_var=4.0)
    result = run_skill_model(rounds)
    last = rounds["event_date"].max()
    recent = rounds[rounds["event_date"] > last - timedelta(days=7 * 20)]

    out = predict(
        result.final_state,
        sorted(rounds["shooter_id"].unique()),
        last + timedelta(days=7),
        SkillParams(),
        level=result.current_level,
    )

    assert abs(out["expected"].mean() - recent["score"].mean()) < 0.5
```

- [ ] **Step 3: Run the skill tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_skill_model.py tests/unit/analytics_core/test_skill_calibrate_predict.py -v`
Expected: collection ERROR in both files — `ModuleNotFoundError: No module named 'sunday_clays.analytics.skill'`.

- [ ] **Step 4: Implement `analytics/skill.py`**

Create `backend/src/sunday_clays/analytics/skill.py`:

```python
"""Dynamic Gaussian skill model (C7): per-shooter Kalman filter, leave-one-out days.

Model: score = skill(shooter, t) + day(t) + noise. The filter runs on the RAW scale;
published values add the level L_t (mean raw day effect over held events in
(t - 364d, t]): rating = mu + L_t, difficulty = -(d_t - L_t) (positive = harder than a
typical recent day). expected = mu_i + d_-i = published rating minus published
leave-one-out difficulty, so residual = score - expected is the raw-model residual.
"""

import itertools
import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

DEFAULT_GRID: dict[str, tuple[float, ...]] = {
    "obs_var": (10, 12, 14, 16, 20),
    "drift_var_per_week": (0.05, 0.15, 0.3),
    "difficulty_var": (2, 4, 9),
    "prior_mu": (28, 30, 32),
    "prior_var": (36, 49),
}
CALIBRATION_GRID: dict[str, tuple[float, ...]] = {
    "obs_var": (12, 14, 16),
    "drift_var_per_week": (0.05, 0.15, 0.3),
    "difficulty_var": (2, 4, 9),
    "prior_mu": (30,),
    "prior_var": (49,),
}
GRID_KEYS: tuple[str, ...] = (
    "obs_var",
    "drift_var_per_week",
    "difficulty_var",
    "prior_mu",
    "prior_var",
)
BURN_IN_HELD_EVENTS = 8
LEVEL_WINDOW = timedelta(days=364)
MIN_SCORE = 0
MAX_SCORE = 50

ROUND_OUTPUT_COLUMNS: tuple[str, ...] = (
    "round_id",
    "expected",
    "residual",
    "mu_before",
    "var_before",
    "mu_after",
    "var_after",
)
EVENT_OUTPUT_COLUMNS: tuple[str, ...] = ("event_date", "difficulty", "d_raw", "level")
HISTORY_COLUMNS: tuple[str, ...] = ("shooter_id", "event_date", "mu", "var")
PREDICTION_COLUMNS: tuple[str, ...] = (
    "shooter_id",
    "attend_prob",
    "expected",
    "sd",
    "p_win",
    "p_podium",
)


@dataclass(frozen=True)
class SkillParams:
    prior_mu: float = 30.0
    prior_var: float = 49.0
    obs_var: float = 14.0
    drift_var_per_week: float = 0.3
    difficulty_var: float = 4.0
    max_var: float = 49.0


DEFAULT_PARAMS = SkillParams()


@dataclass(frozen=True)
class SkillResult:
    rounds: pd.DataFrame  # ROUND_OUTPUT_COLUMNS (published scale for mu_*)
    events: pd.DataFrame  # EVENT_OUTPUT_COLUMNS
    history: pd.DataFrame  # HISTORY_COLUMNS (published mu)
    # shooter -> (mu, var, last_date) on the raw scale
    final_state: dict[int, tuple[float, float, date]]
    current_level: float  # L at the last event


@dataclass(frozen=True)
class _Event:
    event_date: date
    held: bool
    round_ids: IntArray
    scores: FloatArray
    round_shooter: IntArray  # index into `shooters` for each round
    shooters: tuple[int, ...]
    counts: FloatArray  # k_i
    means: FloatArray  # mean score of shooter i that day


@dataclass
class _Collected:
    rounds: list[pd.DataFrame]
    events: list[tuple[date, float, float, float]]
    history: list[pd.DataFrame]


def _prepare(rounds: pd.DataFrame) -> list[_Event]:
    """Group rounds by event; shooters ascending, rounds by (name_key, ordinal)."""
    ordered = rounds.sort_values(
        ["event_date", "shooter_id", "name_key", "ordinal"], kind="mergesort"
    )
    events: list[_Event] = []
    for event_date, group in ordered.groupby("event_date", sort=True):
        shooter_ids = group["shooter_id"].to_numpy(dtype=np.int64)
        unique, inverse, counts = np.unique(
            shooter_ids, return_inverse=True, return_counts=True
        )
        scores = group["score"].to_numpy(dtype=np.float64)
        sums = np.bincount(inverse, weights=scores)
        events.append(
            _Event(
                event_date=cast(date, event_date),
                held=bool(group["held"].iloc[0]),
                round_ids=group["round_id"].to_numpy(dtype=np.int64),
                scores=scores,
                round_shooter=inverse.astype(np.int64),
                shooters=tuple(int(s) for s in unique),
                counts=counts.astype(np.float64),
                means=sums / counts,
            )
        )
    return events


def _event_loglik(
    ev: _Event, mu: FloatArray, var: FloatArray, params: SkillParams
) -> float:
    """log N(y_t; m_t, obs_var*I + Z diag(var) Z^T + difficulty_var*11^T)."""
    idx = ev.round_shooter
    same = idx[:, None] == idx[None, :]
    cov = np.where(same, var[idx][:, None], 0.0) + params.difficulty_var
    cov[np.diag_indices_from(cov)] += params.obs_var
    resid = ev.scores - mu[idx]
    _, logdet = np.linalg.slogdet(cov)
    quad = float(resid @ np.linalg.solve(cov, resid))
    return -0.5 * (len(resid) * math.log(2 * math.pi) + float(logdet) + quad)


def _run(
    events: list[_Event], params: SkillParams, collected: _Collected | None
) -> tuple[float, dict[int, tuple[float, float, date]], float]:
    """Filter every event in date order -> (log-lik after burn-in, state, level).

    The log-likelihood is accumulated only for calibration runs (`collected is None`);
    `run_skill_model` passes a collector and ignores it.
    """
    mu: dict[int, float] = {}
    var: dict[int, float] = {}
    last: dict[int, date] = {}
    window: deque[tuple[date, float]] = deque()
    level = 0.0
    loglik = 0.0
    held_seen = 0
    for ev in events:
        n = len(ev.shooters)
        m = np.empty(n)
        v = np.empty(n)
        for j, shooter in enumerate(ev.shooters):
            if shooter in mu:
                weeks = (ev.event_date - last[shooter]).days / 7.0
                m[j] = mu[shooter]
                v[j] = min(
                    var[shooter] + params.drift_var_per_week * weeks, params.max_var
                )
            else:
                m[j] = params.prior_mu
                v[j] = params.prior_var
        while window and window[0][0] <= ev.event_date - LEVEL_WINDOW:
            window.popleft()
        if ev.held:
            held_seen += 1
            if collected is None and held_seen > BURN_IN_HELD_EVENTS:
                loglik += _event_loglik(ev, m, v, params)
            obs = params.obs_var / ev.counts
            w = 1.0 / (v + obs)
            r = ev.means - m
            precision = float(w.sum()) + 1.0 / params.difficulty_var
            total = float((w * r).sum())
            d = total / precision
            precision_loo = precision - w
            d_loo = (total - w * r) / precision_loo
            gain = v / (v + obs + 1.0 / precision_loo)
            m_after = m + gain * (ev.means - m - d_loo)
            v_after = v * (1.0 - gain)
            window.append((ev.event_date, d))
            level = sum(x for _, x in window) / len(window)
        else:
            d_loo = np.full(n, np.nan)
            m_after, v_after = m, v
            if window:
                level = sum(x for _, x in window) / len(window)
            d = math.nan
        if collected is not None:
            idx = ev.round_shooter
            expected = m[idx] + d_loo[idx]
            collected.rounds.append(
                pd.DataFrame(
                    {
                        "round_id": ev.round_ids,
                        "expected": expected,
                        "residual": ev.scores - expected,
                        "mu_before": m[idx] + level,
                        "var_before": v[idx],
                        "mu_after": m_after[idx] + level,
                        "var_after": v_after[idx],
                    }
                )
            )
            collected.events.append(
                (ev.event_date, -(d - level) if ev.held else math.nan, d, level)
            )
            collected.history.append(
                pd.DataFrame(
                    {
                        "shooter_id": np.array(ev.shooters, dtype=np.int64),
                        "event_date": [ev.event_date] * n,
                        "mu": m_after + level,
                        "var": v_after,
                    }
                )
            )
        for j, shooter in enumerate(ev.shooters):
            mu[shooter] = float(m_after[j])
            var[shooter] = float(v_after[j])
            last[shooter] = ev.event_date
    state = {s: (mu[s], var[s], last[s]) for s in mu}
    return loglik, state, level


def _concat(frames: list[pd.DataFrame], columns: Sequence[str]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in columns})
    return pd.concat(frames, ignore_index=True)


def run_skill_model(
    rounds: pd.DataFrame, params: SkillParams = DEFAULT_PARAMS
) -> SkillResult:
    """Run the online filter over every event in `rounds`.

    Required columns: round_id, event_date, shooter_id, name_key, ordinal, score, held.
    Held events update skills and difficulty; non-held events carry each attendee's
    drift-inflated state forward (expected/residual/difficulty NaN).
    """
    collected = _Collected(rounds=[], events=[], history=[])
    _, state, level = _run(_prepare(rounds), params, collected)
    events = pd.DataFrame(collected.events, columns=list(EVENT_OUTPUT_COLUMNS))
    return SkillResult(
        rounds=_concat(collected.rounds, ROUND_OUTPUT_COLUMNS),
        events=events,
        history=_concat(collected.history, HISTORY_COLUMNS),
        final_state=state,
        current_level=level,
    )


def calibrate(
    rounds: pd.DataFrame, grid: Mapping[str, Sequence[float]] = DEFAULT_GRID
) -> SkillParams:
    """Grid search maximizing the one-step-ahead log-likelihood (C7 objective).

    Held events after the first 8 are scored. Points are visited in lexicographic order
    of GRID_KEYS with values ascending; max() returns the first maximal item, so ties
    keep the lexicographically first point. max_var = prior_var. No `assert` here:
    ruff S101 applies to src/.
    """
    events = _prepare(rounds)
    combos = itertools.product(*(sorted(grid[key]) for key in GRID_KEYS))
    points = (dict(zip(GRID_KEYS, (float(x) for x in combo), strict=True)) for combo in combos)
    candidates = (SkillParams(**values, max_var=values["prior_var"]) for values in points)
    return max(candidates, key=lambda params: _run(events, params, None)[0])


def predict(
    state: Mapping[int, tuple[float, float, date]],
    shooter_ids: Sequence[int],
    on: date,
    params: SkillParams,
    level: float,
    difficulty: float | None = None,
    difficulty_sd: float = 0.0,
    attend_prob: Mapping[int, float] | None = None,
    n_sims: int = 10_000,
    seed: int = 0,
) -> pd.DataFrame:
    """Expected score, sd and win/podium odds for `shooter_ids` on `on` (C7 predict).

    Unknown shooters start at (prior_mu, prior_var). expected = mu + level -
    (difficulty or 0); sd = sqrt(var + obs_var + difficulty_sd^2). Each simulation
    draws one shared day effect, attendance ~ Bernoulli(attend_prob) (missing -> 1.0),
    skill ~ N(mu, var) and noise, then rounds and clips scores to 0..50. p_win and
    p_podium are conditional on attending (ties count as wins); NaN when the shooter
    never attends in the simulations.
    """
    ids = list(shooter_ids)
    n = len(ids)
    if n == 0:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in PREDICTION_COLUMNS})
    mu = np.empty(n)
    var = np.empty(n)
    for j, shooter in enumerate(ids):
        if shooter in state:
            m, v, last = state[shooter]
            mu[j] = m
            var[j] = min(
                v + params.drift_var_per_week * (on - last).days / 7.0, params.max_var
            )
        else:
            mu[j] = params.prior_mu
            var[j] = params.prior_var
    probs = np.array(
        [1.0 if attend_prob is None else attend_prob.get(s, 1.0) for s in ids]
    )
    expected = mu + level - (difficulty if difficulty is not None else 0.0)
    sd = np.sqrt(var + params.obs_var + difficulty_sd**2)

    rng = np.random.default_rng(seed)
    day = rng.standard_normal((n_sims, 1)) * difficulty_sd
    attends = rng.random((n_sims, n)) < probs
    skill = rng.standard_normal((n_sims, n)) * np.sqrt(var)
    noise = rng.standard_normal((n_sims, n)) * math.sqrt(params.obs_var)
    scores = np.clip(np.rint(expected + skill + noise + day), MIN_SCORE, MAX_SCORE)
    present = np.where(attends, scores, -np.inf)

    if n >= 2:
        top_two = np.partition(present, n - 2, axis=1)
        first, second = top_two[:, n - 1 : n], top_two[:, n - 2 : n - 1]
    else:
        first, second = present, np.full((n_sims, 1), -np.inf)
    best_other = np.where(present == first, second, first)
    wins = attends & (present >= best_other)
    better = np.stack(
        [(present > present[:, [i]]).sum(axis=1) for i in range(n)], axis=1
    )
    podiums = attends & (better + 1 <= 3)
    n_attend = attends.sum(axis=0)
    safe = np.maximum(n_attend, 1)
    p_win = np.where(n_attend > 0, wins.sum(axis=0) / safe, np.nan)
    p_podium = np.where(n_attend > 0, podiums.sum(axis=0) / safe, np.nan)
    return pd.DataFrame(
        {
            "shooter_id": np.array(ids, dtype=np.int64),
            "attend_prob": probs,
            "expected": expected,
            "sd": sd,
            "p_win": p_win,
            "p_podium": p_podium,
        }
    )
```

- [ ] **Step 5: Run the skill tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_skill_model.py tests/unit/analytics_core/test_skill_calibrate_predict.py -v`
Expected: PASS — 23 passed (10 + 13) in about 2 s.

- [ ] **Step 6: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass; coverage ≥ 90% lines and branches, with `analytics/skill.py` at 100%.

- [ ] **Step 7: Commit**

```bash
git add backend/src/sunday_clays/analytics/skill.py \
  backend/tests/unit/analytics_core/test_skill_model.py \
  backend/tests/unit/analytics_core/test_skill_calibrate_predict.py
git commit -m "feat(analytics): dynamic Gaussian skill model, calibration and predictions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 4: Recompute step s30 (skill) and rating classes (master Plan 06 T4)

**Branch:** `task/06-4-s30-skill-classes`

**Depends on:** Plan 06 T2, T3.

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/classes.py`
- Create: `backend/src/sunday_clays/analytics/steps/s30_skill.py`
- Modify: `backend/tests/integration/analytics_core/conftest.py` (add `LiveSeed.analyze()`, used by Tasks 4–9)
- Test: `backend/tests/unit/analytics_core/test_assign_classes.py`
- Test: `backend/tests/integration/analytics_core/test_s30_skill_step.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_rounds(session)`, `frames.db_records(df)`, `cache.clear_cache()`; unit fixture `make_rounds`; integration fixture `seed` (`LiveSeed.shooter/round/finish/bump`).
  - Task 2: `steps.s10_metrics.STEP` (writes the `round_metrics` rows s30 updates).
  - Task 3: `skill.SkillParams`, `skill.CALIBRATION_GRID`, `skill.calibrate(rounds, grid) -> SkillParams`, `skill.run_skill_model(rounds, params) -> SkillResult` (`rounds`, `events`, `history`, `current_level`).
  - C6: `pipeline.RecomputeStep`, `discover_steps()`. C6 `recompute {recalibrate: true}` (Plan 03 T7) deletes `app_state.skill_params` before `run_pipeline`, which makes s30 recalibrate.
  - C4: `round_metrics.expected/residual/mu_before/var_before/mu_after/var_after`, `event_metrics.difficulty`, `rating_history(shooter_id, event_date, mu, var)`, `app_state(key, value jsonb)`.
- Produces:
  - `sunday_clays.analytics.classes`: `ACTIVE_WINDOW = timedelta(days=364)`, `MIN_ROUNDS_ACTIVE = 5`, `CLASS_CUTOFFS`, `LOWEST_CLASS`; `active_shooter_ids(rounds: pd.DataFrame, as_of: date) -> set[int]` (C7 Activity: ≥1 round in (as_of − 364d, as_of] and ≥5 rounds ≤ as_of, counted from rounds); `assign_classes(history: pd.DataFrame, rounds: pd.DataFrame, as_of: date) -> pd.DataFrame[shooter_id, mu, klass]` (active, rated shooters only; mu = last rating_history mu ≤ as_of; sorted mu desc then shooter_id; q = (pos − 1)/n → A < 0.15 ≤ B < 0.50 ≤ C < 0.85 ≤ D).
  - `sunday_clays.analytics.steps.s30_skill`: `load_params(session) -> SkillParams | None`; `store_state(session, key: str, value: object) -> None` (JSON upsert into `app_state`); `run(session) -> None`; `STEP = RecomputeStep(name="skill", order=30, run=run)`. `run` uses stored `app_state.skill_params` when `load_params` accepts it (every field present, finite, and valid for `SkillParams`), otherwise `skill.calibrate(rounds, skill.CALIBRATION_GRID)` (looked up on the module at call time so tests can monkeypatch it) and stores `asdict(params)` only when `rounds` holds more than `skill.BURN_IN_HELD_EVENTS` held event dates (with none past the burn-in every grid point scores 0.0, so the arbitrary first point is used for this run but not persisted — an empty DB or a stations-only first import never pins degenerate params); writes the round skill columns, `event_metrics.difficulty` (published), `rating_history` (published mu), `app_state.skill_level = current_level`; clears the memo before reading and after writing.
  - Integration fixture addition: `LiveSeed.analyze(params: SkillParams | None = None) -> None` — stores `params` (default `SkillParams()`) as `app_state.skill_params`, runs s10 then s30, bumps `data_version`.

- [ ] **Step 1: Write the failing class tests**

Create `backend/tests/unit/analytics_core/test_assign_classes.py`:

```python
from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics.classes import active_shooter_ids, assign_classes

AS_OF = date(2026, 9, 27)


def _history(rows: list[tuple[int, date, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["shooter_id", "event_date", "mu"]).assign(
        var=4.0
    )


def test_classes_boundaries_and_multi_round_count(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    # 20 active shooters with 5 rounds each; shooter 21 has 5 rounds on 4 dates (a
    # doubleheader) and is active; shooter 22 has only 4 rounds and is not.
    dates = [AS_OF - timedelta(days=7 * k) for k in range(5)]
    specs = [(d, s, 30) for s in range(1, 21) for d in dates]
    specs += [(d, 21, 30) for d in dates[:4]] + [(dates[0], 21, 25)]
    specs += [(d, 22, 30) for d in dates[:4]]
    rounds = make_rounds(specs)
    history = _history([(s, AS_OF, 60.0 - s) for s in range(1, 23)])

    classes = assign_classes(history, rounds, AS_OF)

    assert 21 in set(classes["shooter_id"])
    assert 22 not in set(classes["shooter_id"])
    order = classes["shooter_id"].tolist()
    assert order == list(range(1, 22))  # mu desc
    counts = classes["klass"].value_counts().to_dict()
    # n = 21: q = (pos-1)/21 -> A: pos 1-4 (q<.15), B: 5-11, C: 12-18, D: 19-21
    assert counts == {"A": 4, "B": 7, "C": 7, "D": 3}
    assert classes.set_index("shooter_id").loc[4, "klass"] == "A"
    assert classes.set_index("shooter_id").loc[5, "klass"] == "B"
    assert classes.set_index("shooter_id").loc[19, "klass"] == "D"


def test_activity_window_is_364_days(make_rounds: Callable[..., pd.DataFrame]) -> None:
    old = [
        (AS_OF - timedelta(days=700 + 7 * k), s, 30) for s in (1, 2) for k in range(5)
    ]
    edge = [(AS_OF - timedelta(days=364), 1, 30), (AS_OF - timedelta(days=357), 2, 30)]
    rounds = make_rounds([*old, *edge])
    assert active_shooter_ids(rounds, AS_OF) == {2}


def test_uses_mu_at_last_event_on_or_before_as_of(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    dates = [AS_OF - timedelta(days=7 * k) for k in range(5)]
    rounds = make_rounds([(d, s, 30) for s in (1, 2) for d in dates])
    history = _history(
        [
            (1, dates[1], 40.0),
            (1, dates[0], 20.0),
            (2, dates[0], 30.0),
            (1, AS_OF + timedelta(days=7), 99.0),
        ]
    )

    classes = assign_classes(history, rounds, AS_OF).set_index("shooter_id")

    assert classes.loc[1, "mu"] == 20.0
    assert classes.index.tolist() == [2, 1]


def test_equal_mu_sorted_by_shooter_id(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    dates = [AS_OF - timedelta(days=7 * k) for k in range(5)]
    rounds = make_rounds([(d, s, 30) for s in (3, 1, 2) for d in dates])
    history = _history([(s, AS_OF, 30.0) for s in (3, 1, 2)])
    assert assign_classes(history, rounds, AS_OF)["shooter_id"].tolist() == [1, 2, 3]


def test_classes_no_leak(make_rounds: Callable[..., pd.DataFrame]) -> None:
    dates = [AS_OF - timedelta(days=7 * k) for k in range(6)]
    rounds = make_rounds([(d, s, 30) for s in range(1, 9) for d in dates])
    history = _history(
        [(s, d, 30.0 + s + d.day / 100) for s in range(1, 9) for d in dates]
    )
    future_dates = [AS_OF + timedelta(days=7 * k) for k in range(1, 4)]
    more_rounds = pd.concat(
        [rounds, make_rounds([(d, s, 50) for s in range(1, 12) for d in future_dates])]
    )
    more_history = pd.concat(
        [
            history,
            _history([(s, d, 90.0 - s) for s in range(1, 12) for d in future_dates]),
        ]
    )
    pd.testing.assert_frame_equal(
        assign_classes(history, rounds, AS_OF),
        assign_classes(more_history, more_rounds, AS_OF),
    )


def test_no_active_shooters_gives_empty_frame(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(AS_OF, 1, 30)])
    classes = assign_classes(_history([(1, AS_OF, 30.0)]), rounds, AS_OF)
    assert classes.empty
    assert list(classes.columns) == ["shooter_id", "mu", "klass"]
```

- [ ] **Step 2: Run the class tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_assign_classes.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.analytics.classes'`.

- [ ] **Step 3: Implement `analytics/classes.py`**

Create `backend/src/sunday_clays/analytics/classes.py`:

```python
"""C7 Activity and A/B/C/D classes from the published rating."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

ACTIVE_WINDOW = timedelta(days=364)
MIN_ROUNDS_ACTIVE = 5
CLASS_CUTOFFS: tuple[tuple[float, str], ...] = ((0.15, "A"), (0.50, "B"), (0.85, "C"))
LOWEST_CLASS = "D"


def active_shooter_ids(rounds: pd.DataFrame, as_of: date) -> set[int]:
    """Shooters with >=1 round in (as_of - 364d, as_of] and >=5 rounds <= as_of."""
    upto = rounds.loc[rounds["event_date"] <= as_of]
    counts = upto["shooter_id"].value_counts()
    eligible = {int(s) for s in counts[counts >= MIN_ROUNDS_ACTIVE].index.tolist()}
    recent = {
        int(s)
        for s in upto.loc[upto["event_date"] > as_of - ACTIVE_WINDOW, "shooter_id"]
    }
    return eligible & recent


def assign_classes(
    history: pd.DataFrame, rounds: pd.DataFrame, as_of: date
) -> pd.DataFrame:
    """[shooter_id, mu, klass] for active shooters rated at or before `as_of`.

    mu = the shooter's rating_history mu at their last event <= as_of. Sorted by mu
    desc then shooter_id; q = (pos - 1) / n: A if q < 0.15, B if q < 0.50,
    C if q < 0.85, else D.
    """
    active = active_shooter_ids(rounds, as_of)
    rated = history.loc[
        (history["event_date"] <= as_of) & history["shooter_id"].isin(active)
    ]
    latest = (
        rated.sort_values(["shooter_id", "event_date"]).groupby("shooter_id").tail(1)
    )
    ordered = latest.sort_values(["mu", "shooter_id"], ascending=[False, True])
    q = np.arange(len(ordered)) / max(len(ordered), 1)
    klass = np.full(len(ordered), LOWEST_CLASS, dtype=object)
    for cutoff, label in reversed(CLASS_CUTOFFS):
        klass[q < cutoff] = label
    return pd.DataFrame(
        {
            "shooter_id": ordered["shooter_id"].astype("int64").to_numpy(),
            "mu": ordered["mu"].astype("float64").to_numpy(),
            "klass": klass,
        }
    )
```

- [ ] **Step 4: Run the class tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_assign_classes.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 5: Add `LiveSeed.analyze()` to the integration conftest**

In `backend/tests/integration/analytics_core/conftest.py`, replace the import block at the top (everything between the module docstring and `class LiveSeed:`) with:

```python
import json
from dataclasses import asdict
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.analytics.skill import SkillParams
from sunday_clays.analytics.steps import s10_metrics, s30_skill
```

and insert this method into `LiveSeed` directly above `def bump(self) -> None:`:

```python
    def analyze(self, params: SkillParams | None = None) -> None:
        """Store `params` (default SkillParams()) as skill_params; run s10 + s30."""
        self.session.execute(
            text(
                "INSERT INTO app_state (key, value)"
                " VALUES ('skill_params', CAST(:v AS jsonb))"
                " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {"v": json.dumps(asdict(params or SkillParams()))},
        )
        s10_metrics.STEP.run(self.session)
        s30_skill.STEP.run(self.session)
        self.bump()

```

- [ ] **Step 6: Write the failing s30 tests**

Create `backend/tests/integration/analytics_core/test_s30_skill_step.py`:

```python
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, skill
from sunday_clays.analytics.pipeline import discover_steps
from sunday_clays.analytics.steps import s10_metrics, s30_skill

D1 = date(2026, 9, 6)
D2 = date(2026, 9, 13)


def _seed_two_events(seed: Any) -> tuple[int, int]:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    for d, a, b in ((D1, 40, 30), (D2, 42, 29)):
        seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.finish()
    return ann, bob


def _seed_past_burn_in(seed: Any) -> None:
    """BURN_IN_HELD_EVENTS + 1 (= 9) weekly held events for two shooters, so the last
    one is scored by calibration; Sundays 2026-07-19 .. 2026-09-13."""
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    first = D2 - timedelta(weeks=skill.BURN_IN_HELD_EVENTS)
    for k in range(skill.BURN_IN_HELD_EVENTS + 1):
        d = first + timedelta(weeks=k)
        seed.round(d, ann, 40 + k % 3)
        seed.round(d, bob, 30 - k % 2)
    seed.finish()


def _stored_params(session: Session) -> object:
    return session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_params'")
    ).scalar_one_or_none()


def _no_calibration(*args: object, **kwargs: object) -> skill.SkillParams:
    raise AssertionError("calibrate must not run when skill_params is stored")


def test_s30_is_discovered_after_s10() -> None:
    orders = {s.name: s.order for s in discover_steps()}
    assert orders["metrics"] < orders["skill"] == 30


def test_s30_uses_stored_params_without_calibrating(
    seed: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_two_events(seed)
    s30_skill.store_state(
        session, "skill_params", asdict(skill.SkillParams(prior_var=36.0, max_var=36.0))
    )
    monkeypatch.setattr(skill, "calibrate", _no_calibration)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    first_vars = (
        session.execute(
            text(
                "SELECT m.var_before FROM round_metrics m"
                " JOIN rounds r ON r.id = m.round_id"
                " WHERE r.event_date = :d"
            ),
            {"d": D1},
        )
        .scalars()
        .all()
    )
    assert first_vars == [36.0, 36.0]  # new shooters start at the stored prior_var


def test_s30_calibrates_and_stores_when_absent(
    seed: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_past_burn_in(seed)
    # One grid point that differs from SkillParams() in three fields, so the stored
    # value can only have come from calibrate() over the patched CALIBRATION_GRID.
    grid = {
        "obs_var": (12.0,),
        "drift_var_per_week": (0.05,),
        "difficulty_var": (2.0,),
        "prior_mu": (30.0,),
        "prior_var": (49.0,),
    }
    monkeypatch.setattr(skill, "CALIBRATION_GRID", grid)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    assert _stored_params(session) == asdict(
        skill.SkillParams(obs_var=12.0, drift_var_per_week=0.05, difficulty_var=2.0)
    )


def test_s30_does_not_store_params_from_burn_in_only_data(
    seed: Any, session: Session
) -> None:
    # 2 held events are all burn-in: every grid point scores 0.0, so the calibrated
    # point is arbitrary and must not be persisted for later runs.
    _seed_two_events(seed)

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    assert _stored_params(session) is None
    level = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()
    assert isinstance(level, float)


def test_incomplete_stored_params_trigger_calibration(
    seed: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_past_burn_in(seed)
    s30_skill.store_state(session, "skill_params", {"obs_var": 10.0})
    monkeypatch.setattr(
        skill, "CALIBRATION_GRID", {**skill.CALIBRATION_GRID, "obs_var": (16.0,)}
    )

    s10_metrics.STEP.run(session)
    s30_skill.STEP.run(session)

    stored = _stored_params(session)
    assert isinstance(stored, dict)
    assert stored["obs_var"] == 16.0
    assert set(stored) == set(asdict(skill.SkillParams()))  # overwritten in full


def test_s30_writes_history_difficulty_and_level(seed: Any, session: Session) -> None:
    ann, bob = _seed_two_events(seed)

    seed.analyze()

    history = session.execute(
        text(
            "SELECT shooter_id, event_date FROM rating_history"
            " ORDER BY event_date, shooter_id"
        )
    ).all()
    assert [tuple(h) for h in history] == [(ann, D1), (bob, D1), (ann, D2), (bob, D2)]
    difficulty = dict(
        session.execute(text("SELECT event_date, difficulty FROM event_metrics")).all()
    )
    assert difficulty[D1] == pytest.approx(0.0, abs=1e-6)  # level = the only day's d
    level = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()
    assert isinstance(level, float)
    missing = session.execute(
        text(
            "SELECT count(*) FROM round_metrics"
            " WHERE expected IS NULL OR mu_after IS NULL"
        )
    ).scalar_one()
    assert missing == 0


def test_s30_leaves_no_stale_memo(seed: Any, session: Session) -> None:
    _seed_two_events(seed)
    s30_skill.store_state(session, "skill_params", asdict(skill.SkillParams()))
    s10_metrics.STEP.run(session)
    assert frames.load_rounds(session)["mu_before"].isna().all()  # memoized, pre-s30

    s30_skill.STEP.run(session)  # a later step (e.g. s50) must see the skill columns

    assert frames.load_rounds(session)["mu_before"].notna().all()


def test_s30_on_empty_live_tables(session: Session) -> None:
    s30_skill.store_state(session, "skill_params", asdict(skill.SkillParams()))
    s30_skill.STEP.run(session)
    level = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_level'")
    ).scalar_one()
    assert level == 0.0
```

- [ ] **Step 7: Run the s30 tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_s30_skill_step.py -v`
Expected: ERROR — `ImportError while loading conftest ... cannot import name 's30_skill' from 'sunday_clays.analytics.steps'` (the Step 5 conftest imports it).

- [ ] **Step 8: Implement `steps/s30_skill.py`**

Create `backend/src/sunday_clays/analytics/steps/s30_skill.py`:

```python
"""Recompute step 30: skill model -> round_metrics, difficulty, rating_history."""

import json
from dataclasses import asdict, fields

from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, skill
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.pipeline import RecomputeStep

_UPDATE_ROUNDS = """
UPDATE round_metrics
SET expected = :expected, residual = :residual, mu_before = :mu_before,
    var_before = :var_before, mu_after = :mu_after, var_after = :var_after
WHERE round_id = :round_id
"""
_UPDATE_EVENTS = (
    "UPDATE event_metrics SET difficulty = :difficulty WHERE event_date = :event_date"
)
_INSERT_HISTORY = """
INSERT INTO rating_history (shooter_id, event_date, mu, var)
VALUES (:shooter_id, :event_date, :mu, :var)
"""
_UPSERT_STATE = """
INSERT INTO app_state (key, value) VALUES (:key, CAST(:value AS jsonb))
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
"""


def load_params(session: Session) -> skill.SkillParams | None:
    """`app_state.skill_params` as SkillParams, or None when absent or incomplete."""
    value = session.execute(
        text("SELECT value FROM app_state WHERE key = 'skill_params'")
    ).scalar_one_or_none()
    names = [f.name for f in fields(skill.SkillParams)]
    if not isinstance(value, dict) or any(name not in value for name in names):
        return None
    return skill.SkillParams(**{name: float(value[name]) for name in names})


def store_state(session: Session, key: str, value: object) -> None:
    session.execute(text(_UPSERT_STATE), {"key": key, "value": json.dumps(value)})


def run(session: Session) -> None:
    """Stored params if present, else calibrate over CALIBRATION_GRID.

    Calibration scores only held events after the burn-in. With no such event (empty
    DB, stations-only first import) every grid point ties at 0.0 and the first point
    wins, so that result is used for this run but never stored: the next run with
    enough data calibrates for real.
    """
    clear_cache()
    rounds = frames.load_rounds(session)
    params = load_params(session)
    if params is None:
        params = skill.calibrate(rounds, skill.CALIBRATION_GRID)
        if rounds.loc[rounds["held"], "event_date"].nunique() > skill.BURN_IN_HELD_EVENTS:
            store_state(session, "skill_params", asdict(params))
    result = skill.run_skill_model(rounds, params)
    if not result.rounds.empty:
        session.execute(text(_UPDATE_ROUNDS), frames.db_records(result.rounds))
        session.execute(
            text(_UPDATE_EVENTS),
            frames.db_records(result.events[["event_date", "difficulty"]]),
        )
    session.execute(text("DELETE FROM rating_history"))
    if not result.history.empty:
        session.execute(text(_INSERT_HISTORY), frames.db_records(result.history))
    store_state(session, "skill_level", result.current_level)
    clear_cache()


STEP = RecomputeStep(name="skill", order=30, run=run)
```

- [ ] **Step 9: Run the s30 tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_s30_skill_step.py -v`
Expected: PASS — 8 passed.

- [ ] **Step 10: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass — the `fx_engine` pipeline now also runs s30, calibrating over the 27-point `CALIBRATION_GRID` on the real fixture (≈0.4 s); coverage ≥ 90% lines and branches, with `analytics/classes.py` and `analytics/steps/s30_skill.py` at 100%.

- [ ] **Step 11: Commit**

```bash
git add backend/src/sunday_clays/analytics/classes.py \
  backend/src/sunday_clays/analytics/steps/s30_skill.py \
  backend/tests/integration/analytics_core/conftest.py \
  backend/tests/unit/analytics_core/test_assign_classes.py \
  backend/tests/integration/analytics_core/test_s30_skill_step.py
git commit -m "feat(analytics): recompute step s30 (skill, difficulty, ratings) and classes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 5: Events API — calendar list and event detail (master Plan 06 T5)

**Branch:** `task/06-5-events-api`

**Depends on:** Plan 06 T4. Runs in parallel with Tasks 6–9 (disjoint files).

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/api/routes/events.py`
- Test: `backend/tests/integration/analytics_core/test_events_routes.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_events`, `load_rounds`, `load_shooters`, `load_station_hits`, `frames.apply_round_type_filter`; `_filters.round_type_param`; `_convert.opt_float/opt_int/opt_str/rows`; integration fixtures `seed` (`LiveSeed.shooter/event/round/weather/finish`) and C2 `viewer_client`, `fx_viewer_client`.
  - Task 4: `LiveSeed.analyze()` (runs s10 + s30 with default `SkillParams`, so ranks, `mu_before/mu_after` and difficulty exist).
  - C2: `db.get_session`, `domain.errors.NotFoundError(code, message)` (→ 404 `{"error": {"code", "message"}}`); C5 `RoundType`.
- Produces (`sunday_clays.api.routes.events`, auto-discovered, `require_viewer`):
  - `GET /api/events?year=&round_type=` → `list[EventSummaryOut]` sorted by date ascending; `EventSummaryOut{event_date, round_type, round_type_source, head_count, n_rounds, n_shooters, has_scores, has_stations, results_complete, median, top_score, difficulty, condition, winners: list[WinnerOut{shooter_id, display_name, score}]}`; attendance-only events are included (`has_scores=false`, `head_count` set); `round_type` filters events by their round type; bad values → 422.
  - `GET /api/events/{date}` (C8 path template; the handler binds it as `event_date: Annotated[date, Path(alias="date")]`, so the OpenAPI path key is `/api/events/{date}` with path param `date`, as Plan 08's `paths['/api/events/{date}']` and Plan 04's route matrix expect) → `EventDetailOut{event_date, round_type, round_type_source, head_count, has_scores, has_stations, results_complete, n_rounds, n_shooters, median, mean, stdev, top_score, difficulty, results: list[EventResultOut], weather: EventWeatherOut | None, stations: StationMatrixOut | None, notables: list[NotableOut], vs_prev: VsPrevOut | None}`; unknown date → 404 `event_not_found`.
  - `EventResultOut{round_id, shooter_id, display_name, name_key, shooter_status, ordinal, score, gauge_class, is_best_round, event_rank, percentile, adjusted, expected, residual, mu_before, mu_after, rating_delta}` (`name_key` = `rounds.name_key`, the C4 identity key; with the event date and `ordinal` it is the `{event_date, name_key, ordinal}` target that Plan 08 T5b's round picker puts in `score_override`/`hide_round` payloads, C5); `EventWeatherOut{temp_f, apparent_f, precip_in, wind_mph, gust_mph, wind_dir_deg, cloud_pct, humidity_pct, pressure_hpa, condition}`; `StationMatrixOut{layout: list[StationLayoutOut{station_no, target_count}], entries: list[StationEntryOut{entry_row, name_key, shooter_id, display_name, round_id, hits: list[StationCellOut{station_no, hits}], total}]}`; `NotableOut{kind: "pb" | "first_timer" | "upset", shooter_id, display_name, detail, value}`; `VsPrevOut{prev_date, head_count_delta, median_delta, top_score_delta, difficulty_delta}`.
  - `event_notables(rounds: pd.DataFrame, shooters: pd.DataFrame, event_date: date) -> list[NotableOut]` (pure). Streak and milestone notables are NOT built here — Plan 10 T7's "Trophies earned today" eventSection covers them.

- [ ] **Step 1: Write the failing events route tests**

Create `backend/tests/integration/analytics_core/test_events_routes.py`. The fixture case uses numbers computed from the workbooks: 2026-09-13 had head count 13, 13 shooters, top score 42 (Nordquist, Sherman), median 34; its station sheet has stations 4–10 with targets 7,7,7,7,7,7,8 and Hadley, Ike's station total 36 against his 34; the previous held event 2026-09-06 had head count 24 and top score 48.

```python
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app

D1 = date(2026, 8, 30)
D2 = date(2026, 9, 6)
D3 = date(2026, 9, 13)


def test_detail_path_is_the_c8_template() -> None:
    # C8 fixes `/api/events/{date}`; Plan 08 indexes `paths['/api/events/{date}']` and
    # sends `params: {path: {date}}`, so the generated key and param name are the contract.
    detail = create_app().openapi()["paths"]["/api/events/{date}"]["get"]
    assert [p["name"] for p in detail["parameters"] if p["in"] == "path"] == ["date"]


def test_list_events_in_date_order_with_attendance_only_and_tied_winners(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, bob, cat = (
        seed.shooter(n) for n in ("Oakley, Ann", "Pratt, Bob", "Quinn, Cat")
    )
    seed.event(D1, head_count=3)
    seed.event(D2, held=False, has_scores=False, head_count=9)
    for sid, score in ((ann, 40), (bob, 35), (cat, 30)):
        seed.round(D1, sid, score)
    for sid, score in ((ann, 44), (bob, 44), (cat, 30)):
        seed.round(D3, sid, score)
    seed.finish()
    seed.analyze()

    body = viewer_client.get("/api/events").json()

    assert [e["event_date"] for e in body] == ["2026-08-30", "2026-09-06", "2026-09-13"]
    attendance_only = body[1]
    assert (attendance_only["has_scores"], attendance_only["head_count"]) == (False, 9)
    assert attendance_only["winners"] == []
    assert [w["display_name"] for w in body[2]["winners"]] == [
        "Oakley, Ann",
        "Pratt, Bob",
    ]
    assert body[0]["median"] == 35.0
    assert body[0]["top_score"] == 40


def test_list_events_year_filter(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(date(2025, 12, 28), ann, 30)
    seed.round(date(2026, 1, 4), ann, 31)
    seed.finish()

    body = viewer_client.get("/api/events", params={"year": 2026}).json()

    assert [e["event_date"] for e in body] == ["2026-01-04"]


def test_round_type_filter_restricts_rounds(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    for d, rt in ((D1, "sporting"), (D2, "super_sporting"), (D3, "unknown")):
        seed.event(d, round_type=rt)
        seed.round(d, ann, 30)
    seed.finish()

    one = viewer_client.get("/api/events", params={"round_type": "sporting"}).json()
    two = viewer_client.get(
        "/api/events", params=[("round_type", "sporting"), ("round_type", "unknown")]
    ).json()
    bad = viewer_client.get("/api/events", params={"round_type": "trap"})

    assert [e["event_date"] for e in one] == ["2026-08-30"]
    assert [e["event_date"] for e in two] == ["2026-08-30", "2026-09-13"]
    assert bad.status_code == 422


def test_event_detail_unknown_date_is_404(viewer_client: TestClient) -> None:
    r = viewer_client.get("/api/events/2001-01-07")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "event_not_found"


def test_event_detail_results_ranks_and_rating_delta(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.event(D3, head_count=2, round_type="sporting")
    seed.round(D3, ann, 44)
    seed.round(D3, ann, 30)
    seed.round(D3, bob, 42)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/events/{D3}").json()

    assert (body["round_type"], body["round_type_source"], body["head_count"]) == (
        "sporting",
        "override",
        2,
    )
    assert body["has_scores"] is True
    assert body["difficulty"] == pytest.approx(0.0, abs=1e-6)
    assert [
        (r["display_name"], r["score"], r["event_rank"]) for r in body["results"]
    ] == [
        ("Oakley, Ann", 44, 1),
        ("Pratt, Bob", 42, 2),
        ("Oakley, Ann", 30, None),
    ]
    # name_key + ordinal (with the date) is what the admin round picker sends in a
    # score_override / hide_round payload (C5); the seed stores name.casefold() minus ","
    assert [r["name_key"] for r in body["results"]] == [
        "oakley ann",
        "pratt bob",
        "oakley ann",
    ]
    assert [r["ordinal"] for r in body["results"]] == [1, 1, 2]
    first = body["results"][0]
    assert first["rating_delta"] == pytest.approx(
        first["mu_after"] - first["mu_before"]
    )
    assert body["weather"] is None
    assert body["stations"] is None
    assert body["vs_prev"] is None


def test_event_detail_attendance_only(seed: Any, viewer_client: TestClient) -> None:
    seed.event(D2, held=False, has_scores=False, head_count=9)
    seed.finish()

    body = viewer_client.get(f"/api/events/{D2}").json()

    assert (body["has_scores"], body["head_count"], body["results"]) == (False, 9, [])
    assert body["median"] is None
    assert body["difficulty"] is None


def test_event_detail_weather_card(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(D3, ann, 30)
    seed.weather(D3, temp_f=41.0, gust_mph=24.0, precip_in=0.1, condition="rain")
    seed.finish()

    weather = viewer_client.get(f"/api/events/{D3}").json()["weather"]

    assert (weather["temp_f"], weather["gust_mph"], weather["condition"]) == (
        41.0,
        24.0,
        "rain",
    )
    assert weather["pressure_hpa"] == 1015.0


def test_notables_personal_best_and_first_timers(
    seed: Any, viewer_client: TestClient
) -> None:
    vet = seed.shooter("Oakley, Ann")
    short = seed.shooter("Pratt, Bob")
    rookie = seed.shooter("Quinn, Cat")
    returning = seed.shooter("Reyes, Dan", left_censored=True)
    for week in range(5):
        seed.round(D3 - timedelta(days=7 * (week + 1)), vet, 40 - week)
    for week in range(4):
        seed.round(D3 - timedelta(days=7 * (week + 1)), short, 20)
    seed.round(D3, vet, 41)
    seed.round(D3, short, 45)
    seed.round(D3, rookie, 30)
    seed.round(D3, returning, 30)
    seed.finish()
    seed.analyze()

    notables = viewer_client.get(f"/api/events/{D3}").json()["notables"]

    assert [(n["kind"], n["display_name"], n["value"]) for n in notables] == [
        ("pb", "Oakley, Ann", 41.0),
        ("first_timer", "Quinn, Cat", None),
    ]


def _five_regulars(seed: Any) -> list[int]:
    ids = [seed.shooter(f"Shooter, {c}") for c in "ABCDE"]
    for week in range(1, 5):
        for sid, score in zip(ids, (45, 40, 35, 30, 25), strict=True):
            seed.round(D3 - timedelta(days=7 * week), sid, score)
    return ids


def test_notables_upset_when_fourth_rated_wins(
    seed: Any, viewer_client: TestClient
) -> None:
    ids = _five_regulars(seed)
    for sid, score in zip(ids, (44, 39, 34, 49, 24), strict=True):
        seed.round(D3, sid, score)
    seed.finish()
    seed.analyze()

    notables = viewer_client.get(f"/api/events/{D3}").json()["notables"]

    upsets = [(n["display_name"], n["value"]) for n in notables if n["kind"] == "upset"]
    assert upsets == [("Shooter, D", 4.0)]


def test_no_upset_with_fewer_than_five_shooters(
    seed: Any, viewer_client: TestClient
) -> None:
    ids = _five_regulars(seed)
    for sid, score in zip(ids[:4], (44, 39, 34, 49), strict=True):
        seed.round(D3, sid, score)
    seed.finish()
    seed.analyze()

    notables = viewer_client.get(f"/api/events/{D3}").json()["notables"]

    assert [n for n in notables if n["kind"] == "upset"] == []


def test_vs_prev_skips_non_held_events(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.event(D1, head_count=10)
    seed.event(D2, held=False, head_count=30)
    seed.event(D3, head_count=6)
    for d, a, b in ((D1, 40, 30), (D2, 20, 20), (D3, 44, 38)):
        seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.finish()
    seed.analyze()

    vs_prev = viewer_client.get(f"/api/events/{D3}").json()["vs_prev"]

    assert vs_prev["prev_date"] == "2026-08-30"
    assert vs_prev["head_count_delta"] == -4
    assert vs_prev["median_delta"] == pytest.approx(6.0)
    assert vs_prev["top_score_delta"] == 4
    assert vs_prev["difficulty_delta"] is not None


def test_station_event_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/events/2026-09-13").json()

    assert (body["round_type"], body["round_type_source"]) == (
        "super_sporting",
        "stations",
    )
    assert (body["head_count"], body["n_shooters"], body["top_score"]) == (13, 13, 42)
    assert body["median"] == 34.0
    layout = body["stations"]["layout"]
    assert [s["station_no"] for s in layout] == [4, 5, 6, 7, 8, 9, 10]
    assert [s["target_count"] for s in layout] == [7, 7, 7, 7, 7, 7, 8]
    entries = {e["name_key"]: e for e in body["stations"]["entries"]}
    assert len(entries) == 13
    hadley = entries["hadley ike"]
    assert hadley["total"] == 36
    assert len(hadley["hits"]) == 7
    hadley_result = next(r for r in body["results"] if r["round_id"] == hadley["round_id"])
    assert hadley_result["score"] == 34
    assert body["results"][0]["display_name"].startswith("Nordquist")
    assert body["vs_prev"]["prev_date"] == "2026-09-06"
    assert body["vs_prev"]["head_count_delta"] == -11
    assert body["vs_prev"]["top_score_delta"] == -6
```

- [ ] **Step 2: Run the events tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_events_routes.py -v`
Expected: FAIL (13 failed) — `/api/events` is not routed yet, so every request returns 404 `{"detail": "Not Found"}` (assertion errors, `TypeError`/`KeyError` on the body; the 404 test fails on the missing `error` key; `test_detail_path_is_the_c8_template` fails with `KeyError: '/api/events/{date}'`).

- [ ] **Step 3: Implement `api/routes/events.py`**

Create `backend/src/sunday_clays/api/routes/events.py`:

```python
"""GET /api/events and /api/events/{date}: calendar list and event detail."""

from datetime import date
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
from sunday_clays.api.routes._filters import round_type_param
from sunday_clays.db import get_session
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

PB_MIN_PRIOR_ROUNDS = 5
UPSET_MIN_SHOOTERS = 5
UPSET_MIN_FAVORITE_RANK = 4


class WinnerOut(BaseModel):
    shooter_id: int
    display_name: str
    score: int


class EventSummaryOut(BaseModel):
    event_date: date
    round_type: RoundType
    round_type_source: str
    head_count: int | None
    n_rounds: int
    n_shooters: int
    has_scores: bool
    has_stations: bool
    results_complete: bool
    median: float | None
    top_score: int | None
    difficulty: float | None
    condition: str | None
    winners: list[WinnerOut]


class EventResultOut(BaseModel):
    round_id: int
    shooter_id: int
    display_name: str
    name_key: str  # C4 identity key; with event_date + ordinal it targets C5 round rules
    shooter_status: str
    ordinal: int
    score: int
    gauge_class: str | None
    is_best_round: bool
    event_rank: int | None
    percentile: float | None
    adjusted: float | None
    expected: float | None
    residual: float | None
    mu_before: float | None
    mu_after: float | None
    rating_delta: float | None


class EventWeatherOut(BaseModel):
    temp_f: float | None
    apparent_f: float | None
    precip_in: float | None
    wind_mph: float | None
    gust_mph: float | None
    wind_dir_deg: float | None
    cloud_pct: float | None
    humidity_pct: float | None
    pressure_hpa: float | None
    condition: str | None


class StationLayoutOut(BaseModel):
    station_no: int
    target_count: int


class StationCellOut(BaseModel):
    station_no: int
    hits: int


class StationEntryOut(BaseModel):
    entry_row: int
    name_key: str
    shooter_id: int | None
    display_name: str | None
    round_id: int | None
    hits: list[StationCellOut]
    total: int


class StationMatrixOut(BaseModel):
    layout: list[StationLayoutOut]
    entries: list[StationEntryOut]


class NotableOut(BaseModel):
    kind: Literal["pb", "first_timer", "upset"]
    shooter_id: int
    display_name: str
    detail: str
    value: float | None


class VsPrevOut(BaseModel):
    prev_date: date
    head_count_delta: int | None
    median_delta: float | None
    top_score_delta: int | None
    difficulty_delta: float | None


class EventDetailOut(BaseModel):
    event_date: date
    round_type: RoundType
    round_type_source: str
    head_count: int | None
    has_scores: bool
    has_stations: bool
    results_complete: bool
    n_rounds: int
    n_shooters: int
    median: float | None
    mean: float | None
    stdev: float | None
    top_score: int | None
    difficulty: float | None
    results: list[EventResultOut]
    weather: EventWeatherOut | None
    stations: StationMatrixOut | None
    notables: list[NotableOut]
    vs_prev: VsPrevOut | None


def _winners(rounds: pd.DataFrame) -> dict[date, list[WinnerOut]]:
    top = rounds.loc[rounds["event_rank"] == 1].sort_values(
        ["event_date", "display_name"]
    )
    out: dict[date, list[WinnerOut]] = {}
    for row in rows(top):
        winner = WinnerOut(
            shooter_id=int(row["shooter_id"]),
            display_name=str(row["display_name"]),
            score=int(row["score"]),
        )
        out.setdefault(row["event_date"], []).append(winner)
    return out


@router.get("/api/events")
def list_events(
    session: Annotated[Session, Depends(get_session, scope="function")],
    year: int | None = None,
    round_types: list[RoundType] = round_type_param,
) -> list[EventSummaryOut]:
    events = frames.apply_round_type_filter(frames.load_events(session), round_types)
    if year is not None:
        events = events.loc[[d.year == year for d in events["event_date"]]]
    winners = _winners(frames.load_rounds(session))
    return [
        EventSummaryOut(
            event_date=row["event_date"],
            round_type=RoundType(row["round_type"]),
            round_type_source=str(row["round_type_source"]),
            head_count=opt_int(row["head_count"]),
            n_rounds=int(row["n_rounds"]),
            n_shooters=int(row["n_shooters"]),
            has_scores=bool(row["has_scores"]),
            has_stations=bool(row["has_stations"]),
            results_complete=bool(row["results_complete"]),
            median=opt_float(row["median"]),
            top_score=opt_int(row["top_score"]),
            difficulty=opt_float(row["difficulty"]),
            condition=opt_str(row["condition"]),
            winners=winners.get(row["event_date"], []),
        )
        for row in rows(events)
    ]


def _results(day: pd.DataFrame) -> list[EventResultOut]:
    ordered = day.sort_values(
        ["score", "display_name", "ordinal"], ascending=[False, True, True]
    )
    return [
        EventResultOut(
            round_id=int(r["round_id"]),
            shooter_id=int(r["shooter_id"]),
            display_name=str(r["display_name"]),
            name_key=str(r["name_key"]),
            shooter_status=str(r["shooter_status"]),
            ordinal=int(r["ordinal"]),
            score=int(r["score"]),
            gauge_class=opt_str(r["gauge_class"]),
            is_best_round=bool(r["is_best_round"]),
            event_rank=opt_int(r["event_rank"]),
            percentile=opt_float(r["percentile"]),
            adjusted=opt_float(r["adjusted"]),
            expected=opt_float(r["expected"]),
            residual=opt_float(r["residual"]),
            mu_before=opt_float(r["mu_before"]),
            mu_after=opt_float(r["mu_after"]),
            rating_delta=opt_float(r["mu_after"] - r["mu_before"]),
        )
        for r in rows(ordered)
    ]


def _weather(event: dict[str, Any]) -> EventWeatherOut | None:
    if opt_str(event["condition"]) is None and opt_float(event["temp_f"]) is None:
        return None
    return EventWeatherOut(
        temp_f=opt_float(event["temp_f"]),
        apparent_f=opt_float(event["apparent_f"]),
        precip_in=opt_float(event["precip_in"]),
        wind_mph=opt_float(event["wind_mph"]),
        gust_mph=opt_float(event["gust_mph"]),
        wind_dir_deg=opt_float(event["wind_dir_deg"]),
        cloud_pct=opt_float(event["cloud_pct"]),
        humidity_pct=opt_float(event["humidity_pct"]),
        pressure_hpa=opt_float(event["pressure_hpa"]),
        condition=opt_str(event["condition"]),
    )


def _stations(hits: pd.DataFrame, names: dict[int, str]) -> StationMatrixOut | None:
    if hits.empty:
        return None
    layout = (
        hits[["station_no", "target_count"]].drop_duplicates().sort_values("station_no")
    )
    entries: dict[int, StationEntryOut] = {}
    for cell in rows(hits.sort_values(["entry_row", "station_no"])):
        entry_row = int(cell["entry_row"])
        if entry_row not in entries:
            shooter_id = opt_int(cell["shooter_id"])
            entries[entry_row] = StationEntryOut(
                entry_row=entry_row,
                name_key=str(cell["name_key"]),
                shooter_id=shooter_id,
                display_name=None if shooter_id is None else names.get(shooter_id),
                round_id=opt_int(cell["round_id"]),
                hits=[],
                total=0,
            )
        entry = entries[entry_row]
        entry.hits.append(
            StationCellOut(station_no=int(cell["station_no"]), hits=int(cell["hits"]))
        )
        entry.total += int(cell["hits"])
    return StationMatrixOut(
        layout=[
            StationLayoutOut(
                station_no=int(r["station_no"]), target_count=int(r["target_count"])
            )
            for r in rows(layout)
        ],
        entries=list(entries.values()),
    )


def event_notables(
    rounds: pd.DataFrame, shooters: pd.DataFrame, event_date: date
) -> list[NotableOut]:
    """PBs (C12 personal_bests rule), first-timers (not left_censored) and upsets."""
    day = rounds.loc[rounds["event_date"] == event_date]
    earlier = rounds.loc[rounds["event_date"] < event_date]
    notables: list[NotableOut] = []
    best = day.loc[day["is_best_round"]].sort_values("display_name")
    prior = {
        int(r["shooter_id"]): (int(r["max"]), int(r["size"]))
        for r in rows(
            earlier.groupby("shooter_id")["score"].agg(["max", "size"]).reset_index()
        )
    }
    for r in rows(best):
        previous, n_prior = prior.get(int(r["shooter_id"]), (0, 0))
        if n_prior >= PB_MIN_PRIOR_ROUNDS and int(r["score"]) > previous:
            notables.append(
                NotableOut(
                    kind="pb",
                    shooter_id=int(r["shooter_id"]),
                    display_name=str(r["display_name"]),
                    detail=f"New personal best {int(r['score'])} (was {previous})",
                    value=float(r["score"]),
                )
            )
    firsts = shooters.loc[
        (shooters["first_event"] == event_date) & ~shooters["left_censored"]
    ]
    for s in rows(firsts.sort_values("display_name")):
        notables.append(
            NotableOut(
                kind="first_timer",
                shooter_id=int(s["shooter_id"]),
                display_name=str(s["display_name"]),
                detail="First Sunday Clays",
                value=None,
            )
        )
    if best["shooter_id"].nunique() >= UPSET_MIN_SHOOTERS:
        ranked = best.assign(
            pre_rank=best["mu_before"].rank(method="min", ascending=False)
        )
        for r in rows(ranked.loc[ranked["event_rank"] == 1]):
            rank = opt_float(r["pre_rank"])
            if rank is not None and rank >= UPSET_MIN_FAVORITE_RANK:
                notables.append(
                    NotableOut(
                        kind="upset",
                        shooter_id=int(r["shooter_id"]),
                        display_name=str(r["display_name"]),
                        detail=f"Won from #{int(rank)} on pre-event rating",
                        value=rank,
                    )
                )
    return notables


def _vs_prev(events: pd.DataFrame, event: dict[str, Any]) -> VsPrevOut | None:
    earlier = events.loc[
        events["results_complete"] & (events["event_date"] < event["event_date"])
    ]
    if earlier.empty:
        return None
    prev = rows(earlier)[-1]

    def delta(column: str) -> float | None:
        a, b = opt_float(event[column]), opt_float(prev[column])
        return None if a is None or b is None else a - b

    head, top = delta("head_count"), delta("top_score")
    return VsPrevOut(
        prev_date=prev["event_date"],
        head_count_delta=None if head is None else int(head),
        median_delta=delta("median"),
        top_score_delta=None if top is None else int(top),
        difficulty_delta=delta("difficulty"),
    )


@router.get("/api/events/{date}")
def get_event(
    event_date: Annotated[date, Path(alias="date")],
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> EventDetailOut:
    events = frames.load_events(session)
    match = events.loc[events["event_date"] == event_date]
    if match.empty:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    event = rows(match)[0]
    rounds = frames.load_rounds(session)
    shooters = frames.load_shooters(session)
    hits = frames.load_station_hits(session)
    names = {int(r["shooter_id"]): str(r["display_name"]) for r in rows(shooters)}
    return EventDetailOut(
        event_date=event_date,
        round_type=RoundType(str(event["round_type"])),
        round_type_source=str(event["round_type_source"]),
        head_count=opt_int(event["head_count"]),
        has_scores=bool(event["has_scores"]),
        has_stations=bool(event["has_stations"]),
        results_complete=bool(event["results_complete"]),
        n_rounds=int(event["n_rounds"]),
        n_shooters=int(event["n_shooters"]),
        median=opt_float(event["median"]),
        mean=opt_float(event["mean"]),
        stdev=opt_float(event["stdev"]),
        top_score=opt_int(event["top_score"]),
        difficulty=opt_float(event["difficulty"]),
        results=_results(rounds.loc[rounds["event_date"] == event_date]),
        weather=_weather(event),
        stations=_stations(hits.loc[hits["event_date"] == event_date], names),
        notables=event_notables(rounds, shooters, event_date),
        vs_prev=_vs_prev(events, event),
    )
```

- [ ] **Step 4: Run the events tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_events_routes.py -v`
Expected: PASS — 13 passed.

- [ ] **Step 5: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass (Plan 04's route auth matrix now also covers `/api/events` and `/api/events/2026-09-13` → 401 without a cookie); coverage ≥ 90% lines and branches, with `api/routes/events.py` at 100%.

- [ ] **Step 6: Commit**

```bash
git add backend/src/sunday_clays/api/routes/events.py \
  backend/tests/integration/analytics_core/test_events_routes.py
git commit -m "feat(api): events calendar and event detail with notables and station matrix

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 6: Streaks and the shooters API — directory, detail + odometer, rounds, rating, splits (master Plan 06 T6)

**Branch:** `task/06-6-streaks-shooters-api`

**Depends on:** Plan 06 T4. Runs in parallel with Tasks 5, 7, 8, 9 (disjoint files).

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/streaks.py`
- Create: `backend/src/sunday_clays/api/routes/shooters.py`
- Test: `backend/tests/unit/analytics_core/test_held_streaks.py`
- Test: `backend/tests/integration/analytics_core/test_shooters_routes.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_rounds/load_events/load_shooters/load_rating_history`, `frames.apply_round_type_filter`, `frames.season_label`, `frames.temp_band/wind_band/precip_band`, `frames.SEASONS/TEMP_BANDS/WIND_BANDS/PRECIP_BANDS`; `_filters.round_type_param`, `_filters.resolve_as_of` (tests monkeypatch `_filters.today_local`); `_convert.opt_float/opt_int/opt_str/rows`; unit fixtures `make_rounds`, `make_events` (`make_events` specs are dates or dicts, defaults `results_complete=True`); integration fixture `seed` incl. `weather()`.
  - Task 4: `classes.active_shooter_ids(rounds, as_of) -> set[int]`; `LiveSeed.analyze()`.
  - C2: `get_session`, `get_settings` (`settings.timezone`), `NotFoundError`; C5 `RoundType`; C4 `achievements_awarded(shooter_id, ...)` (exists from `0001_initial`; Plan 10 fills it).
- Produces:
  - `sunday_clays.analytics.streaks` (C7, the single implementation that Plan 09 T3 and Plan 10 `iron_streak` call): `STREAK_COLUMNS`; `held_event_dates(events: pd.DataFrame, as_of: date | None) -> list[date]`; `streaks(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date | None) -> pd.DataFrame[shooter_id, current_streak, longest_streak]` (every shooter with a round ≤ as_of; non-held dates skipped).
  - `sunday_clays.api.routes.shooters` (auto-discovered, `require_viewer`): `SplitBy(StrEnum)` = `season | month | year | round_type | gauge | temp_band | wind_band | precip_band`; `NO_WEATHER = "no_data"`; pure helpers `shooter_stats(rounds) -> ShooterStatsOut`, `odometer(rounds, streak_row, trophies) -> OdometerOut`, `personal_bests(rounds) -> list[PbOut]`, `splits(rounds, by: SplitBy) -> list[SplitOut]`.
  - `GET /api/shooters?q=&active=` → `list[ShooterSummaryOut{shooter_id, display_name, status, first_event, last_event, n_rounds, n_events, active, mu}]` sorted by display_name (`active` = C7 Activity as of today).
  - C8 path templates: every per-shooter route uses the literal `{id}` (`/api/shooters/{id}`, `/{id}/rounds`, `/{id}/rating`, `/{id}/splits`), bound as `shooter_id: ShooterId` with `ShooterId = Annotated[int, Path(alias="id")]`, so the OpenAPI keys are the C8 strings Plan 08 indexes (`paths['/api/shooters/{id}']`, path param `id`) and Plan 04's route matrix fills `id` with `1`.
  - `GET /api/shooters/{id}?round_type=` → `ShooterDetailOut{shooter_id, display_name, status, deceased, first_event, last_event, left_censored, current_mu, current_var, stats: ShooterStatsOut{n_rounds, n_events, avg_score, median_score, best_score, avg_adjusted, wins, podiums, avg_percentile}, odometer: OdometerOut{clays_thrown, clays_broken, hit_pct, rounds, events, years_active, current_streak, longest_streak, favorite_month, trophies}, pbs: list[PbOut{scope: "overall" | "year", key, score, event_date, round_id}]}` — `stats`/`pbs` honour `round_type`, the odometer is lifetime.
  - `GET /api/shooters/{id}/rounds?round_type=` → `list[ShooterRoundOut{round_id, event_date, ordinal, score, gauge_class, status, round_type, is_best_round, event_rank, percentile, field_median, adjusted, expected, residual, mu_before, mu_after, condition}]` in (event_date, ordinal) order.
  - `GET /api/shooters/{id}/rating` → `RatingOut{shooter_id, points: list[RatingPointOut{event_date, mu, var, lo, hi}], current_mu, peak_mu, peak_date}` (band ±1.96·√var).
  - `GET /api/shooters/{id}/splits?by=&round_type=` → `list[SplitOut{key, n_rounds, n_events, avg, median, best, avg_adjusted}]` (`best` = PB for that key; gauge NULL = `unspecified`; missing weather = `no_data`; seasons/bands/round types in their fixed order, others ascending).
  - Unknown shooter id → 404 `shooter_not_found` on all four `/{id}` routes.

- [ ] **Step 1: Write the failing streak tests**

Create `backend/tests/unit/analytics_core/test_held_streaks.py`:

```python
from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd

from sunday_clays.analytics.streaks import held_event_dates, streaks

W = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(8)]


def _by_shooter(frame: pd.DataFrame) -> dict[int, tuple[int, int]]:
    return {
        int(r.shooter_id): (int(r.current_streak), int(r.longest_streak))
        for r in frame.itertuples()
    }


def test_attendance_only_event_does_not_break_streak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = make_events(
        [
            W[0],
            W[1],
            {"event_date": W[2], "results_complete": False, "has_scores": False},
            W[3],
        ]
    )
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 30), (W[3], 1, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (3, 3)}


def test_incomplete_scored_event_is_skipped_even_when_attended(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = make_events([W[0], {"event_date": W[1], "results_complete": False}, W[2]])
    rounds = make_rounds([(W[0], 1, 30), (W[1], 1, 30), (W[2], 1, 30), (W[1], 2, 30)])

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 2), 2: (0, 0)}


def test_missed_held_event_breaks_and_current_needs_latest(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    events = make_events(W[:6])
    rounds = make_rounds(
        [
            (W[0], 1, 30),
            (W[1], 1, 30),
            (W[2], 1, 30),
            (W[4], 1, 30),
            (W[5], 1, 30),
            (W[0], 2, 30),
            (W[1], 2, 30),
        ]
    )

    assert _by_shooter(streaks(rounds, events, None)) == {1: (2, 3), 2: (0, 2)}


def test_as_of_limits_and_no_leak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    rounds = make_rounds([(d, 1, 30) for d in W[:4]] + [(W[3], 2, 30)])
    events = make_events(W[:4])
    more_rounds = pd.concat([rounds, make_rounds([(W[5], 1, 30), (W[5], 3, 30)])])
    more_events = make_events(W[:6])

    base = streaks(rounds, events, W[3])
    pd.testing.assert_frame_equal(base, streaks(more_rounds, more_events, W[3]))
    assert _by_shooter(base) == {1: (4, 4), 2: (1, 1)}
    assert _by_shooter(streaks(rounds, events, W[1])) == {1: (2, 2)}


def test_held_event_dates_filters_and_sorts(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    events = make_events([W[2], W[0], {"event_date": W[1], "results_complete": False}])
    assert held_event_dates(events, None) == [W[0], W[2]]
    assert held_event_dates(events, W[1]) == [W[0]]


def test_no_rounds_gives_empty_frame(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    empty = streaks(make_rounds([(W[0], 1, 30)]).iloc[0:0], make_events([W[0]]), None)
    assert empty.empty
    assert list(empty.columns) == ["shooter_id", "current_streak", "longest_streak"]
```

- [ ] **Step 2: Run the streak tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_held_streaks.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.analytics.streaks'`.

- [ ] **Step 3: Implement `analytics/streaks.py`**

Create `backend/src/sunday_clays/analytics/streaks.py`:

```python
"""Held events and attendance streaks (C7). The single streak implementation."""

from datetime import date

import pandas as pd

STREAK_COLUMNS: tuple[str, ...] = ("shooter_id", "current_streak", "longest_streak")


def held_event_dates(events: pd.DataFrame, as_of: date | None) -> list[date]:
    """Sorted dates of `results_complete` events, on or before `as_of` if given."""
    held = events.loc[events["results_complete"].astype(bool), "event_date"]
    return sorted(d for d in held if as_of is None or d <= as_of)


def streaks(
    rounds: pd.DataFrame, events: pd.DataFrame, as_of: date | None
) -> pd.DataFrame:
    """Consecutive held events attended, per shooter with a round on/before `as_of`.

    Non-held dates are skipped: they neither extend nor break a streak. current_streak
    is the run ending at the latest held date <= as_of (0 if the shooter missed it).
    """
    held = held_event_dates(events, as_of)
    position = {d: i for i, d in enumerate(held)}
    upto = rounds if as_of is None else rounds.loc[rounds["event_date"] <= as_of]
    attended: dict[int, set[int]] = {int(s): set() for s in upto["shooter_id"].unique()}
    for shooter_id, event_date in zip(
        upto["shooter_id"], upto["event_date"], strict=True
    ):
        if event_date in position:
            attended[int(shooter_id)].add(position[event_date])
    last = len(held) - 1
    rows: list[tuple[int, int, int]] = []
    for shooter_id in sorted(attended):
        longest = run = 0
        previous = -2
        for i in sorted(attended[shooter_id]):
            run = run + 1 if i == previous + 1 else 1
            longest = max(longest, run)
            previous = i
        current = run if previous == last else 0
        rows.append((shooter_id, current, longest))
    return pd.DataFrame(rows, columns=list(STREAK_COLUMNS)).astype("int64")
```

- [ ] **Step 4: Run the streak tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_held_streaks.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 5: Write the failing shooters route tests**

Create `backend/tests/integration/analytics_core/test_shooters_routes.py`. The fixture case uses numbers computed independently from `scores_2026-09-27.xlsx` (with the C4 held-event rule): "Ackerly, Alton" has 170 rounds, 7,313 clays broken, 167 event dates over 7 years, current streak 1 and longest 12 as of 2026-09-27, 18 dates each in March and November (so the lowest month, 3, is the favorite), and a best score of 49 first reached on 2021-03-28; 83 shooters are active as of 2026-09-27.

```python
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)
# W[0] is today, W[7] seven weeks ago
W = [TODAY - timedelta(days=7 * k) for k in range(8)]


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)


def test_shooter_paths_are_the_c8_templates() -> None:
    # C8 fixes `/api/shooters/{id}` (+ /rounds, /rating, /splits); Plan 08 indexes those
    # keys and sends `params: {path: {id}}`.
    paths = create_app().openapi()["paths"]
    for suffix in ("", "/rounds", "/rating", "/splits"):
        op = paths[f"/api/shooters/{{id}}{suffix}"]["get"]
        assert [p["name"] for p in op["parameters"] if p["in"] == "path"] == ["id"]


def test_list_search_and_active_filter(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob")
    for d in W[:5]:
        seed.round(d, ann, 30)
    seed.round(W[0], bob, 25)
    seed.finish()
    seed.analyze()

    everyone = viewer_client.get("/api/shooters").json()
    active = viewer_client.get("/api/shooters", params={"active": "true"}).json()
    inactive = viewer_client.get("/api/shooters", params={"active": "false"}).json()
    search = viewer_client.get("/api/shooters", params={"q": "PRA"}).json()

    assert [s["display_name"] for s in everyone] == ["Oakley, Ann", "Pratt, Bob"]
    assert [s["shooter_id"] for s in active] == [ann]
    assert [s["shooter_id"] for s in inactive] == [bob]
    assert [s["shooter_id"] for s in search] == [bob]
    assert everyone[0]["n_rounds"] == 5
    assert everyone[0]["mu"] is not None


def test_detail_stats_odometer_and_pbs(
    seed: Any, viewer_client: TestClient, session: Session
) -> None:
    ann = seed.shooter("Oakley, Ann", status="deceased")
    bob = seed.shooter("Pratt, Bob")
    seed.event(W[2], held=False)
    plan = [
        (W[7], 40, 30),
        (W[6], 38, 45),
        (W[3], 44, 30),
        (W[2], 20, 20),
        (W[1], 44, 20),
        (W[0], 35, 36),
    ]
    for d, a, b in plan:
        seed.round(d, ann, a)
        seed.round(d, bob, b)
    seed.round(W[0], ann, 12)
    seed.finish()
    seed.analyze()
    session.execute(
        text(
            "INSERT INTO achievements_awarded (shooter_id, code, event_date)"
            " VALUES (:s, 'events:1', :d)"
        ),
        {"s": ann, "d": W[7]},
    )

    body = viewer_client.get(f"/api/shooters/{ann}").json()

    assert (body["status"], body["deceased"], body["left_censored"]) == (
        "deceased",
        True,
        False,
    )
    odo = body["odometer"]
    assert odo["rounds"] == 7
    assert odo["clays_thrown"] == 350
    assert odo["clays_broken"] == 40 + 38 + 44 + 20 + 44 + 35 + 12
    assert odo["hit_pct"] == pytest.approx(233 / 350)
    assert (odo["events"], odo["years_active"]) == (6, 1)
    # held events W7, W6, W3, W1, W0 (W2 not held, skipped): attended all five
    assert (odo["current_streak"], odo["longest_streak"]) == (5, 5)
    assert odo["favorite_month"] == 9  # Aug has 2 dates (W7, W6); Sep has 4
    assert odo["trophies"] == 1
    stats = body["stats"]
    assert (stats["n_rounds"], stats["best_score"], stats["wins"]) == (7, 44, 4)
    assert stats["podiums"] == 6
    assert body["pbs"][0] == {
        "scope": "overall",
        "key": "all",
        "score": 44,
        "event_date": W[3].isoformat(),
        "round_id": body["pbs"][0]["round_id"],
    }
    assert [(p["scope"], p["key"], p["score"]) for p in body["pbs"]] == [
        ("overall", "all", 44),
        ("year", "2026", 44),
    ]
    assert body["current_mu"] is not None


def test_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    for path in ("", "/rounds", "/rating", "/splits?by=year"):
        r = viewer_client.get(f"/api/shooters/999999{path}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "shooter_not_found"


def test_round_type_filter_restricts_rounds(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(W[2], round_type="sporting")
    seed.event(W[1], round_type="super_sporting")
    seed.round(W[2], ann, 40)
    seed.round(W[1], ann, 30)
    seed.finish()
    seed.analyze()
    params = {"round_type": "super_sporting"}

    detail = viewer_client.get(f"/api/shooters/{ann}", params=params).json()
    rounds = viewer_client.get(f"/api/shooters/{ann}/rounds", params=params).json()
    by_year = viewer_client.get(
        f"/api/shooters/{ann}/splits", params={**params, "by": "year"}
    ).json()

    assert detail["stats"]["n_rounds"] == 1
    assert detail["stats"]["best_score"] == 30
    assert detail["odometer"]["rounds"] == 2  # lifetime odometer ignores the filter
    assert [r["score"] for r in rounds] == [30]
    assert [(s["key"], s["n_rounds"]) for s in by_year] == [("2026", 1)]
    none = viewer_client.get(
        f"/api/shooters/{ann}", params={"round_type": "unknown"}
    ).json()
    assert (none["stats"]["n_rounds"], none["stats"]["avg_score"], none["pbs"]) == (
        0,
        None,
        [],
    )
    assert none["stats"]["best_score"] is None


def test_rounds_list_in_date_order(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(W[0], ann, 30)
    seed.round(W[1], ann, 41)
    seed.round(W[1], ann, 35)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/shooters/{ann}/rounds").json()

    assert [(r["event_date"], r["ordinal"], r["score"]) for r in body] == [
        (W[1].isoformat(), 1, 41),
        (W[1].isoformat(), 2, 35),
        (W[0].isoformat(), 1, 30),
    ]
    assert [r["is_best_round"] for r in body] == [True, False, True]
    assert body[0]["round_type"] == "unknown"


def test_rating_series_band_and_peak(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    for d, a in ((W[3], 30), (W[2], 45), (W[1], 20)):
        seed.round(d, ann, a)
        seed.round(d, bob, 30)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(f"/api/shooters/{ann}/rating").json()

    points = body["points"]
    assert [p["event_date"] for p in points] == [
        W[3].isoformat(),
        W[2].isoformat(),
        W[1].isoformat(),
    ]
    for p in points:
        assert p["lo"] == pytest.approx(p["mu"] - 1.96 * p["var"] ** 0.5)
        assert p["hi"] == pytest.approx(p["mu"] + 1.96 * p["var"] ** 0.5)
    assert body["peak_date"] == W[2].isoformat()
    assert body["peak_mu"] == max(p["mu"] for p in points)
    assert body["current_mu"] == points[-1]["mu"]


def test_splits_by_gauge_includes_unspecified(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(W[2], ann, 40, gauge_class="Sub-Gauge")
    seed.round(W[1], ann, 30)
    seed.round(W[0], ann, 34)
    seed.finish()
    seed.analyze()

    body = viewer_client.get(
        f"/api/shooters/{ann}/splits", params={"by": "gauge"}
    ).json()

    assert [(s["key"], s["n_rounds"], s["best"]) for s in body] == [
        ("Sub-Gauge", 1, 40),
        ("unspecified", 2, 34),
    ]
    assert body[1]["avg"] == 32.0


def test_splits_by_weather_band_use_no_data_sentinel(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.round(W[2], ann, 40)
    seed.round(W[1], ann, 30)
    seed.round(W[0], ann, 20)
    seed.weather(W[2], temp_f=38.0, gust_mph=25.0, precip_in=0.3)
    seed.weather(W[1], temp_f=72.0, gust_mph=4.0, precip_in=0.0)
    seed.finish()
    seed.analyze()

    def keys(by: str) -> list[tuple[str, int]]:
        body = viewer_client.get(
            f"/api/shooters/{ann}/splits", params={"by": by}
        ).json()
        return [(s["key"], s["best"]) for s in body]

    assert keys("temp_band") == [("<40", 40), ("70-85", 30), ("no_data", 20)]
    assert keys("wind_band") == [("<10", 30), ("20+", 40), ("no_data", 20)]
    assert keys("precip_band") == [("dry", 30), ("wet", 40), ("no_data", 20)]


def test_splits_by_calendar_dims(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    for d, s in (
        (date(2025, 12, 7), 30),
        (date(2026, 1, 4), 32),
        (date(2026, 4, 5), 34),
        (date(2026, 7, 5), 36),
        (date(2026, 9, 6), 38),
    ):
        seed.round(d, ann, s)
    seed.finish()
    seed.analyze()

    def keys(by: str) -> list[str]:
        body = viewer_client.get(
            f"/api/shooters/{ann}/splits", params={"by": by}
        ).json()
        return [s["key"] for s in body]

    assert keys("season") == ["winter", "spring", "summer", "fall"]
    assert keys("month") == ["2025-12", "2026-01", "2026-04", "2026-07", "2026-09"]
    assert keys("year") == ["2025", "2026"]
    assert keys("round_type") == ["unknown"]
    season = viewer_client.get(
        f"/api/shooters/{ann}/splits", params={"by": "season"}
    ).json()
    assert (season[0]["n_rounds"], season[0]["avg"]) == (2, 31.0)
    assert (
        viewer_client.get(f"/api/shooters/{ann}/splits?by=weekday").status_code == 422
    )


def test_committed_fixture_shooter(fx_viewer_client: TestClient) -> None:
    found = fx_viewer_client.get("/api/shooters", params={"q": "ackerly, alton"}).json()
    assert [s["display_name"] for s in found] == ["Ackerly, Alton"]
    body = fx_viewer_client.get(f"/api/shooters/{found[0]['shooter_id']}").json()

    odo = body["odometer"]
    assert (odo["rounds"], odo["clays_broken"], odo["events"], odo["years_active"]) == (
        170,
        7313,
        167,
        7,
    )
    assert (odo["current_streak"], odo["longest_streak"]) == (1, 12)
    assert odo["favorite_month"] == 3  # March and November tie at 18; lowest month wins
    assert body["pbs"][0]["score"] == 49
    assert body["pbs"][0]["event_date"] == "2021-03-28"
    active = fx_viewer_client.get("/api/shooters", params={"active": "true"}).json()
    assert len(active) == 83
```

- [ ] **Step 6: Run the shooters route tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_shooters_routes.py -v`
Expected: FAIL (11 failed) — `/api/shooters…` is not routed yet, so every request returns 404 `{"detail": "Not Found"}` (assertion errors / `TypeError` / `KeyError` on the body; `test_shooter_paths_are_the_c8_templates` fails with `KeyError: '/api/shooters/{id}'`).

- [ ] **Step 7: Implement `api/routes/shooters.py`**

Create `backend/src/sunday_clays/api/routes/shooters.py`:

```python
"""Shooter directory, detail (stats, odometer, PBs), rounds, rating and splits."""

import math
from collections import Counter
from collections.abc import Callable
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.classes import active_shooter_ids
from sunday_clays.analytics.streaks import streaks
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
from sunday_clays.api.routes._filters import resolve_as_of, round_type_param
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

# C8 path template `{id}`, bound to a descriptive argument (as Plan 04 D2 does).
ShooterId = Annotated[int, Path(alias="id")]

TARGETS_PER_ROUND = 50
BAND_Z = 1.96
NO_WEATHER = "no_data"


class SplitBy(StrEnum):
    SEASON = "season"
    MONTH = "month"
    YEAR = "year"
    ROUND_TYPE = "round_type"
    GAUGE = "gauge"
    TEMP_BAND = "temp_band"
    WIND_BAND = "wind_band"
    PRECIP_BAND = "precip_band"


class ShooterSummaryOut(BaseModel):
    shooter_id: int
    display_name: str
    status: str
    first_event: date
    last_event: date
    n_rounds: int
    n_events: int
    active: bool
    mu: float | None


class ShooterStatsOut(BaseModel):
    n_rounds: int
    n_events: int
    avg_score: float | None
    median_score: float | None
    best_score: int | None
    avg_adjusted: float | None
    wins: int
    podiums: int
    avg_percentile: float | None


class OdometerOut(BaseModel):
    clays_thrown: int
    clays_broken: int
    hit_pct: float | None
    rounds: int
    events: int
    years_active: int
    current_streak: int
    longest_streak: int
    favorite_month: int | None
    trophies: int


class PbOut(BaseModel):
    scope: Literal["overall", "year"]
    key: str
    score: int
    event_date: date
    round_id: int


class ShooterDetailOut(BaseModel):
    shooter_id: int
    display_name: str
    status: str
    deceased: bool
    first_event: date
    last_event: date
    left_censored: bool
    current_mu: float | None
    current_var: float | None
    stats: ShooterStatsOut
    odometer: OdometerOut
    pbs: list[PbOut]


class ShooterRoundOut(BaseModel):
    round_id: int
    event_date: date
    ordinal: int
    score: int
    gauge_class: str | None
    status: str | None
    round_type: RoundType
    is_best_round: bool
    event_rank: int | None
    percentile: float | None
    field_median: float | None
    adjusted: float | None
    expected: float | None
    residual: float | None
    mu_before: float | None
    mu_after: float | None
    condition: str | None


class RatingPointOut(BaseModel):
    event_date: date
    mu: float
    var: float
    lo: float
    hi: float


class RatingOut(BaseModel):
    shooter_id: int
    points: list[RatingPointOut]
    current_mu: float | None
    peak_mu: float | None
    peak_date: date | None


class SplitOut(BaseModel):
    key: str
    n_rounds: int
    n_events: int
    avg: float
    median: float
    best: int
    avg_adjusted: float | None


def _profile(session: Session, shooter_id: int) -> dict[str, Any]:
    shooters = frames.load_shooters(session)
    match = shooters.loc[shooters["shooter_id"] == shooter_id]
    if match.empty:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    return rows(match)[0]


def _shooter_rounds(
    session: Session, shooter_id: int, round_types: list[RoundType]
) -> pd.DataFrame:
    rounds = frames.load_rounds(session)
    mine = rounds.loc[rounds["shooter_id"] == shooter_id]
    return frames.apply_round_type_filter(mine, round_types)


def _mean(series: pd.Series) -> float | None:
    clean = series.dropna()
    return None if clean.empty else float(clean.mean())


def shooter_stats(rounds: pd.DataFrame) -> ShooterStatsOut:
    """Stats over one shooter's (already filtered) rounds; ranks are full-field (C7)."""
    best = rounds.loc[rounds["is_best_round"]]
    return ShooterStatsOut(
        n_rounds=len(rounds),
        n_events=int(rounds["event_date"].nunique()),
        avg_score=_mean(rounds["score"]),
        median_score=None if rounds.empty else float(rounds["score"].median()),
        best_score=None if rounds.empty else int(rounds["score"].max()),
        avg_adjusted=_mean(rounds["adjusted"]),
        wins=int((best["event_rank"] == 1).sum()),
        podiums=int((best["event_rank"] <= 3).sum()),
        avg_percentile=_mean(best["percentile"]),
    )


def odometer(
    rounds: pd.DataFrame, streak_row: dict[str, Any] | None, trophies: int
) -> OdometerOut:
    """Lifetime counters over all of one shooter's rounds (C12 odometer)."""
    thrown = len(rounds) * TARGETS_PER_ROUND
    broken = int(rounds["score"].sum())
    dates = sorted(set(rounds["event_date"]))
    months = Counter(d.month for d in dates)
    top = max(months.values(), default=0)
    favorite = min((m for m, n in months.items() if n == top), default=None)
    return OdometerOut(
        clays_thrown=thrown,
        clays_broken=broken,
        hit_pct=None if thrown == 0 else broken / thrown,
        rounds=len(rounds),
        events=len(dates),
        years_active=len({d.year for d in dates}),
        current_streak=0 if streak_row is None else int(streak_row["current_streak"]),
        longest_streak=0 if streak_row is None else int(streak_row["longest_streak"]),
        favorite_month=favorite,
        trophies=trophies,
    )


def personal_bests(rounds: pd.DataFrame) -> list[PbOut]:
    """Best score overall and per calendar year, dated when first reached."""
    ordered = rounds.sort_values(
        ["score", "event_date", "ordinal"], ascending=[False, True, True]
    )
    out: list[PbOut] = []
    if ordered.empty:
        return out
    top = rows(ordered.head(1))[0]
    out.append(
        PbOut(
            scope="overall",
            key="all",
            score=int(top["score"]),
            event_date=top["event_date"],
            round_id=int(top["round_id"]),
        )
    )
    by_year = ordered.assign(year=[d.year for d in ordered["event_date"]])
    for r in rows(by_year.drop_duplicates("year").sort_values("year")):
        out.append(
            PbOut(
                scope="year",
                key=str(r["year"]),
                score=int(r["score"]),
                event_date=r["event_date"],
                round_id=int(r["round_id"]),
            )
        )
    return out


def _split_key(by: SplitBy) -> Callable[[dict[str, Any]], str]:
    def band(
        fn: Callable[[float | None], str | None], column: str
    ) -> Callable[[dict[str, Any]], str]:
        return lambda r: fn(opt_float(r[column])) or NO_WEATHER

    keys: dict[SplitBy, Callable[[dict[str, Any]], str]] = {
        SplitBy.SEASON: lambda r: frames.season_label(r["event_date"]),
        SplitBy.MONTH: lambda r: (
            f"{r['event_date'].year:04d}-{r['event_date'].month:02d}"
        ),
        SplitBy.YEAR: lambda r: str(r["event_date"].year),
        SplitBy.ROUND_TYPE: lambda r: str(r["round_type"]),
        SplitBy.GAUGE: lambda r: str(r["gauge"]),
        SplitBy.TEMP_BAND: band(frames.temp_band, "temp_f"),
        SplitBy.WIND_BAND: band(frames.wind_band, "gust_mph"),
        SplitBy.PRECIP_BAND: band(frames.precip_band, "precip_in"),
    }
    return keys[by]


def _split_order(by: SplitBy) -> tuple[str, ...]:
    orders: dict[SplitBy, tuple[str, ...]] = {
        SplitBy.SEASON: frames.SEASONS,
        SplitBy.ROUND_TYPE: tuple(rt.value for rt in RoundType),
        SplitBy.TEMP_BAND: (*frames.TEMP_BANDS, NO_WEATHER),
        SplitBy.WIND_BAND: (*frames.WIND_BANDS, NO_WEATHER),
        SplitBy.PRECIP_BAND: (*frames.PRECIP_BANDS, NO_WEATHER),
    }
    return orders.get(by, ())


def splits(rounds: pd.DataFrame, by: SplitBy) -> list[SplitOut]:
    """Per-key aggregates; `best` is the PB for the key. No weather -> "no_data"."""
    key_of = _split_key(by)
    keyed = rounds.assign(key=[key_of(r) for r in rows(rounds)])
    order = _split_order(by)
    out = []
    for key, group in keyed.groupby("key", sort=True):
        out.append(
            SplitOut(
                key=str(key),
                n_rounds=len(group),
                n_events=int(group["event_date"].nunique()),
                avg=float(group["score"].mean()),
                median=float(group["score"].median()),
                best=int(group["score"].max()),
                avg_adjusted=_mean(group["adjusted"]),
            )
        )
    if order:
        out.sort(key=lambda s: order.index(s.key) if s.key in order else len(order))
    return out


@router.get("/api/shooters")
def list_shooters(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str | None = None,
    active: bool | None = None,
) -> list[ShooterSummaryOut]:
    shooters = frames.load_shooters(session)
    active_ids = active_shooter_ids(
        frames.load_rounds(session), resolve_as_of(None, settings.timezone)
    )
    history = frames.load_rating_history(session)
    latest_mu = {
        int(r["shooter_id"]): float(r["mu"])
        for r in rows(history.groupby("shooter_id").tail(1))
    }
    out = []
    for r in rows(shooters.sort_values(["display_name", "shooter_id"])):
        sid = int(r["shooter_id"])
        is_active = sid in active_ids
        if q and q.casefold() not in str(r["display_name"]).casefold():
            continue
        if active is not None and is_active != active:
            continue
        out.append(
            ShooterSummaryOut(
                shooter_id=sid,
                display_name=str(r["display_name"]),
                status=str(r["status"]),
                first_event=r["first_event"],
                last_event=r["last_event"],
                n_rounds=int(r["n_rounds"]),
                n_events=int(r["n_events"]),
                active=is_active,
                mu=latest_mu.get(sid),
            )
        )
    return out


@router.get("/api/shooters/{id}")
def get_shooter(
    shooter_id: ShooterId,
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    round_types: list[RoundType] = round_type_param,
) -> ShooterDetailOut:
    profile = _profile(session, shooter_id)
    all_rounds = frames.load_rounds(session)
    lifetime = all_rounds.loc[all_rounds["shooter_id"] == shooter_id]
    filtered = frames.apply_round_type_filter(lifetime, round_types)
    today = resolve_as_of(None, settings.timezone)
    streak = streaks(all_rounds, frames.load_events(session), today)
    streak_rows = rows(streak.loc[streak["shooter_id"] == shooter_id])
    trophies = int(
        session.execute(
            text("SELECT count(*) FROM achievements_awarded WHERE shooter_id = :s"),
            {"s": shooter_id},
        ).scalar_one()
    )
    history = frames.load_rating_history(session)
    mine = rows(history.loc[history["shooter_id"] == shooter_id].tail(1))
    return ShooterDetailOut(
        shooter_id=shooter_id,
        display_name=str(profile["display_name"]),
        status=str(profile["status"]),
        deceased=profile["status"] == "deceased",
        first_event=profile["first_event"],
        last_event=profile["last_event"],
        left_censored=bool(profile["left_censored"]),
        current_mu=float(mine[0]["mu"]) if mine else None,
        current_var=float(mine[0]["var"]) if mine else None,
        stats=shooter_stats(filtered),
        odometer=odometer(lifetime, streak_rows[0] if streak_rows else None, trophies),
        pbs=personal_bests(filtered),
    )


@router.get("/api/shooters/{id}/rounds")
def get_shooter_rounds(
    shooter_id: ShooterId,
    session: Annotated[Session, Depends(get_session, scope="function")],
    round_types: list[RoundType] = round_type_param,
) -> list[ShooterRoundOut]:
    _profile(session, shooter_id)
    mine = _shooter_rounds(session, shooter_id, round_types)
    return [
        ShooterRoundOut(
            round_id=int(r["round_id"]),
            event_date=r["event_date"],
            ordinal=int(r["ordinal"]),
            score=int(r["score"]),
            gauge_class=opt_str(r["gauge_class"]),
            status=opt_str(r["status"]),
            round_type=RoundType(str(r["round_type"])),
            is_best_round=bool(r["is_best_round"]),
            event_rank=opt_int(r["event_rank"]),
            percentile=opt_float(r["percentile"]),
            field_median=opt_float(r["field_median"]),
            adjusted=opt_float(r["adjusted"]),
            expected=opt_float(r["expected"]),
            residual=opt_float(r["residual"]),
            mu_before=opt_float(r["mu_before"]),
            mu_after=opt_float(r["mu_after"]),
            condition=opt_str(r["condition"]),
        )
        for r in rows(mine.sort_values(["event_date", "ordinal"]))
    ]


@router.get("/api/shooters/{id}/rating")
def get_shooter_rating(
    shooter_id: ShooterId, session: Annotated[Session, Depends(get_session, scope="function")]
) -> RatingOut:
    _profile(session, shooter_id)
    history = frames.load_rating_history(session)
    mine = rows(history.loc[history["shooter_id"] == shooter_id])
    points = [
        RatingPointOut(
            event_date=r["event_date"],
            mu=float(r["mu"]),
            var=float(r["var"]),
            lo=float(r["mu"]) - BAND_Z * math.sqrt(float(r["var"])),
            hi=float(r["mu"]) + BAND_Z * math.sqrt(float(r["var"])),
        )
        for r in mine
    ]
    peak = max(points, key=lambda p: p.mu, default=None)
    return RatingOut(
        shooter_id=shooter_id,
        points=points,
        current_mu=points[-1].mu if points else None,
        peak_mu=None if peak is None else peak.mu,
        peak_date=None if peak is None else peak.event_date,
    )


@router.get("/api/shooters/{id}/splits")
def get_shooter_splits(
    shooter_id: ShooterId,
    by: SplitBy,
    session: Annotated[Session, Depends(get_session, scope="function")],
    round_types: list[RoundType] = round_type_param,
) -> list[SplitOut]:
    _profile(session, shooter_id)
    return splits(_shooter_rounds(session, shooter_id, round_types), by)
```

- [ ] **Step 8: Run the shooters route tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_shooters_routes.py -v`
Expected: PASS — 11 passed.

- [ ] **Step 9: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass (Plan 04's route auth matrix now also covers the five `/api/shooters…` routes — `/splits` still answers 401 without a cookie because `require_viewer` runs before query validation); coverage ≥ 90% lines and branches, with `analytics/streaks.py` and `api/routes/shooters.py` at 100%.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/streaks.py \
  backend/src/sunday_clays/api/routes/shooters.py \
  backend/tests/unit/analytics_core/test_held_streaks.py \
  backend/tests/integration/analytics_core/test_shooters_routes.py
git commit -m "feat(api): shooters directory, detail with odometer, rounds, rating and splits

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 7: Newcomer cohorts and the club API — summary, attendance, cohorts, distribution (master Plan 06 T7)

**Branch:** `task/06-7-cohorts-club-api`

**Depends on:** Plan 06 T4. Runs in parallel with Tasks 5, 6, 8, 9 (disjoint files).

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/cohorts.py`
- Create: `backend/src/sunday_clays/api/routes/club.py`
- Test: `backend/tests/unit/analytics_core/test_cohorts.py`
- Test: `backend/tests/integration/analytics_core/test_club_routes.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_events/load_rounds/load_shooters` (rounds carry per-row `status` and current `shooter_status`; shooters carry `left_censored`; events carry `head_count`, `has_scores`, `results_complete`, `n_rounds`, `n_shooters`), `frames.apply_round_type_filter`; `_filters.round_type_param`; `_convert.opt_float/opt_int/rows`; unit fixture `make_rounds` (tuples `(event_date, shooter_id, score)`); integration fixture `seed` (`shooter(name, status=, left_censored=)`, `event(date, held=, has_scores=, head_count=, round_type=)`, `round(date, shooter_id, score, status=)`, `finish()`) and C2 `viewer_client`, `fx_viewer_client`.
  - C2: `get_session`; C4 `left_censored` rule (excluded from cohorts and retention only); C5 `RoundType`; C7 status rule (the per-year member/guest split counts rounds by per-row `status`).
- Produces:
  - `sunday_clays.analytics.cohorts`: `COHORT_COLUMNS`, `RETURN_COLUMNS`; `newcomer_cohorts(rounds: pd.DataFrame, shooters: pd.DataFrame) -> pd.DataFrame[cohort_year, offset, n_cohort, n_active, share]` (cohort = calendar year of the first round; offsets 0..last data year; `left_censored` excluded); `cohort_returns(rounds, shooters) -> pd.DataFrame[cohort_year, n_cohort, n_returned]` (`n_returned` = cohort members with ≥ 2 event dates).
  - `sunday_clays.api.routes.club` (auto-discovered, `require_viewer`): `ROW_STATUSES = ("member", "guest", "deceased")`; pure helpers `status_by_year(rounds) -> list[StatusYearOut]` and `score_distribution(rounds) -> list[DistributionOut]`.
  - `GET /api/club/summary?round_type=` → `ClubSummaryOut{first_event, last_event, n_events, n_scored_events, n_held_events, n_rounds, n_shooters, avg_score, median_score, top_score, n_perfect, clays_thrown, clays_broken, avg_head_count, shooters_by_status: dict[str, int], status_by_year: list[StatusYearOut{year, member_rounds, guest_rounds, deceased_rounds, unrecorded_rounds}]}` (`first_event`/`last_event` span score events; `shooters_by_status` counts distinct shooters by current `shooter_status`).
  - `GET /api/club/attendance` → `list[AttendanceOut{event_date, head_count, n_rounds, n_shooters, has_scores, results_complete}]` for every event (attendance-only included), date ascending.
  - `GET /api/club/cohorts` → `list[CohortOut{year, n_new, n_returned, retention: list[RetentionOut{offset, n_active, share}]}]`.
  - `GET /api/club/distribution?by=year&round_type=` → `list[DistributionOut{key, n, mean, median, p10, p25, p75, p90, counts: list[int]}]` (numpy linear percentiles; `counts[i]` = rounds scoring `i`, 51 bins); any other `by` → 422.

- [ ] **Step 1: Write the failing cohort tests**

Create `backend/tests/unit/analytics_core/test_cohorts.py`:

```python
from collections.abc import Callable
from datetime import date

import pandas as pd

from sunday_clays.analytics.cohorts import cohort_returns, newcomer_cohorts


def _shooters(censored: set[int], ids: range) -> pd.DataFrame:
    return pd.DataFrame(
        {"shooter_id": list(ids), "left_censored": [i in censored for i in ids]}
    )


def test_cohorts_track_retention_and_skip_left_censored(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            (date(2024, 3, 3), 1, 30),
            (date(2025, 3, 2), 1, 30),
            (date(2026, 3, 1), 1, 30),
            (date(2024, 5, 5), 2, 30),
            (date(2025, 6, 1), 3, 30),
            (date(2025, 6, 8), 3, 30),
            (date(2024, 1, 7), 9, 30),
            (date(2026, 1, 4), 9, 30),
        ]
    )
    shooters = _shooters({9}, range(1, 10))

    table = newcomer_cohorts(rounds, shooters)

    assert [tuple(r) for r in table.itertuples(index=False)] == [
        (2024, 0, 2, 2, 1.0),
        (2024, 1, 2, 1, 0.5),
        (2024, 2, 2, 1, 0.5),
        (2025, 0, 1, 1, 1.0),
        (2025, 1, 1, 0, 0.0),
    ]
    returns = cohort_returns(rounds, shooters)
    assert [tuple(r) for r in returns.itertuples(index=False)] == [
        (2024, 2, 1),
        (2025, 1, 1),
    ]


def test_cohorts_empty_when_everyone_is_left_censored(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds([(date(2020, 1, 5), 1, 30)])
    table = newcomer_cohorts(rounds, _shooters({1}, range(1, 2)))
    assert table.empty
    assert list(table.columns) == [
        "cohort_year",
        "offset",
        "n_cohort",
        "n_active",
        "share",
    ]
    assert cohort_returns(rounds, _shooters({1}, range(1, 2))).empty
```

- [ ] **Step 2: Run the cohort tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_cohorts.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.analytics.cohorts'`.

- [ ] **Step 3: Implement `analytics/cohorts.py`**

Create `backend/src/sunday_clays/analytics/cohorts.py`:

```python
"""Newcomer cohorts and retention by calendar year (left-censored excluded, C4)."""

from collections import defaultdict
from datetime import date

import pandas as pd

COHORT_COLUMNS: tuple[str, ...] = (
    "cohort_year",
    "offset",
    "n_cohort",
    "n_active",
    "share",
)
RETURN_COLUMNS: tuple[str, ...] = ("cohort_year", "n_cohort", "n_returned")


def _dates_by_shooter(
    rounds: pd.DataFrame, shooters: pd.DataFrame
) -> dict[int, set[date]]:
    censored = {int(s) for s in shooters.loc[shooters["left_censored"], "shooter_id"]}
    dates: dict[int, set[date]] = defaultdict(set)
    for shooter_id, event_date in zip(
        rounds["shooter_id"], rounds["event_date"], strict=True
    ):
        if int(shooter_id) not in censored:
            dates[int(shooter_id)].add(event_date)
    return dates


def newcomer_cohorts(rounds: pd.DataFrame, shooters: pd.DataFrame) -> pd.DataFrame:
    """Rows (cohort_year, offset k, n_cohort, n_active in cohort_year + k, share).

    A shooter's cohort is the year of their first round; offsets run to the last
    year with data.
    """
    dates = _dates_by_shooter(rounds, shooters)
    if not dates:
        return pd.DataFrame({c: pd.Series(dtype="int64") for c in COHORT_COLUMNS})
    cohort = {s: min(ds).year for s, ds in dates.items()}
    last_year = max(d.year for ds in dates.values() for d in ds)
    out = []
    for cohort_year in sorted(set(cohort.values())):
        members = [s for s, y in cohort.items() if y == cohort_year]
        for year in range(cohort_year, last_year + 1):
            n_active = sum(1 for s in members if any(d.year == year for d in dates[s]))
            out.append(
                (
                    cohort_year,
                    year - cohort_year,
                    len(members),
                    n_active,
                    n_active / len(members),
                )
            )
    return pd.DataFrame(out, columns=list(COHORT_COLUMNS))


def cohort_returns(rounds: pd.DataFrame, shooters: pd.DataFrame) -> pd.DataFrame:
    """Per cohort year: size and how many came back for a second event date."""
    dates = _dates_by_shooter(rounds, shooters)
    size: dict[int, int] = defaultdict(int)
    returned: dict[int, int] = defaultdict(int)
    for ds in dates.values():
        year = min(ds).year
        size[year] += 1
        returned[year] += int(len(ds) >= 2)
    out = [(year, size[year], returned[year]) for year in sorted(size)]
    return pd.DataFrame(out, columns=list(RETURN_COLUMNS), dtype="int64")
```

- [ ] **Step 4: Run the cohort tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_cohorts.py -v`
Expected: PASS — 2 passed.

- [ ] **Step 5: Write the failing club route tests**

Create `backend/tests/integration/analytics_core/test_club_routes.py`. The fixture case uses numbers computed independently from `scores_2026-09-27.xlsx`: 7,480 rounds by 332 shooters with 6 perfect 50s and 261,461 clays broken; all 360 events record a head count and their mean is 22.558; the 2020 rounds split 793 member / 16 guest / 34 deceased by per-row status; the newcomer cohorts (48 left-censored shooters excluded) are 44, 34, 27, 46, 35, 57, 41 for 2020–2026 (sum 284 = 332 − 48); 2020 has 843 rounds and 2021 has 1,047.

```python
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

D1 = date(2025, 8, 31)
D2 = date(2026, 9, 6)
D3 = date(2026, 9, 13)


def test_summary_counts(seed: Any, viewer_client: TestClient) -> None:
    ann = seed.shooter("Oakley, Ann")
    bob = seed.shooter("Pratt, Bob", status="guest")
    seed.event(date(2026, 8, 30), held=False, has_scores=False, head_count=8)
    seed.event(D2, head_count=4)
    seed.round(D2, ann, 50)
    seed.round(D2, ann, 30)
    seed.round(D2, bob, 40)
    seed.finish()

    body = viewer_client.get("/api/club/summary").json()

    assert (body["n_events"], body["n_scored_events"], body["n_held_events"]) == (
        2,
        1,
        1,
    )
    assert (body["n_rounds"], body["n_shooters"], body["top_score"]) == (3, 2, 50)
    assert (body["avg_score"], body["median_score"], body["n_perfect"]) == (
        40.0,
        40.0,
        1,
    )
    assert (body["clays_thrown"], body["clays_broken"]) == (150, 120)
    assert body["avg_head_count"] == 6.0
    assert body["shooters_by_status"] == {"member": 1, "guest": 1}
    assert (body["first_event"], body["last_event"]) == ("2026-09-06", "2026-09-06")


def test_member_guest_split_uses_row_status(
    seed: Any, viewer_client: TestClient
) -> None:
    # current statuses: Ann is a member now; Bob has a set_status override
    convert = seed.shooter("Oakley, Ann", status="member")
    override = seed.shooter("Pratt, Bob", status="deceased")
    seed.round(D1, convert, 30, status="guest")
    seed.round(D2, convert, 31, status="member")
    seed.round(D2, override, 32, status="member")
    seed.round(D3, override, 33, status=None)
    seed.finish()

    years = viewer_client.get("/api/club/summary").json()["status_by_year"]

    assert years == [
        {
            "year": 2025,
            "member_rounds": 0,
            "guest_rounds": 1,
            "deceased_rounds": 0,
            "unrecorded_rounds": 0,
        },
        {
            "year": 2026,
            "member_rounds": 2,
            "guest_rounds": 0,
            "deceased_rounds": 0,
            "unrecorded_rounds": 1,
        },
    ]


def test_round_type_filter_restricts_rounds(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(D2, round_type="sporting")
    seed.event(D3, round_type="super_sporting")
    seed.round(D2, ann, 20)
    seed.round(D3, ann, 44)
    seed.finish()
    params = {"round_type": "super_sporting"}

    summary = viewer_client.get("/api/club/summary", params=params).json()
    dist = viewer_client.get("/api/club/distribution", params=params).json()

    assert (summary["n_rounds"], summary["n_events"], summary["top_score"]) == (
        1,
        1,
        44,
    )
    assert [(d["key"], d["n"], d["mean"]) for d in dist] == [("2026", 1, 44.0)]


def test_attendance_lists_every_event_with_head_count_and_rows(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    seed.event(date(2018, 12, 30), held=False, has_scores=False, head_count=7)
    seed.event(D2, head_count=12)
    seed.round(D2, ann, 30)
    seed.round(D2, ann, 31)
    seed.finish()

    body = viewer_client.get("/api/club/attendance").json()

    assert body == [
        {
            "event_date": "2018-12-30",
            "head_count": 7,
            "n_rounds": 0,
            "n_shooters": 0,
            "has_scores": False,
            "results_complete": False,
        },
        {
            "event_date": "2026-09-06",
            "head_count": 12,
            "n_rounds": 2,
            "n_shooters": 1,
            "has_scores": True,
            "results_complete": True,
        },
    ]


def test_cohorts_endpoint_excludes_left_censored(
    seed: Any, viewer_client: TestClient
) -> None:
    ann = seed.shooter("Oakley, Ann")
    old = seed.shooter("Pratt, Bob", left_censored=True)
    seed.round(D1, ann, 30)
    seed.round(D2, ann, 30)
    seed.round(D1, old, 30)
    seed.finish()

    body = viewer_client.get("/api/club/cohorts").json()

    assert body == [
        {
            "year": 2025,
            "n_new": 1,
            "n_returned": 1,
            "retention": [
                {"offset": 0, "n_active": 1, "share": 1.0},
                {"offset": 1, "n_active": 1, "share": 1.0},
            ],
        },
    ]


def test_distribution_histogram_and_percentiles(
    seed: Any, viewer_client: TestClient
) -> None:
    ids = [seed.shooter(f"Shooter, {c}") for c in "ABCDE"]
    for sid, score in zip(ids, (10, 20, 30, 40, 50), strict=True):
        seed.round(D2, sid, score)
    seed.finish()

    (year,) = viewer_client.get("/api/club/distribution", params={"by": "year"}).json()

    assert (year["key"], year["n"], year["median"]) == ("2026", 5, 30.0)
    assert (year["p10"], year["p25"], year["p75"], year["p90"]) == (
        14.0,
        20.0,
        40.0,
        46.0,
    )
    assert len(year["counts"]) == 51
    assert [i for i, c in enumerate(year["counts"]) if c] == [10, 20, 30, 40, 50]
    assert (
        viewer_client.get("/api/club/distribution", params={"by": "month"}).status_code
        == 422
    )


def test_club_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    summary = fx_viewer_client.get("/api/club/summary").json()
    assert (summary["n_rounds"], summary["n_shooters"], summary["n_perfect"]) == (
        7480,
        332,
        6,
    )
    assert summary["clays_broken"] == 261461
    assert summary["avg_head_count"] == pytest.approx(22.5583, abs=1e-3)
    first_year = summary["status_by_year"][0]
    assert (
        first_year["year"],
        first_year["member_rounds"],
        first_year["guest_rounds"],
        first_year["deceased_rounds"],
    ) == (2020, 793, 16, 34)
    cohorts = fx_viewer_client.get("/api/club/cohorts").json()
    assert {c["year"]: c["n_new"] for c in cohorts} == {
        2020: 44,
        2021: 34,
        2022: 27,
        2023: 46,
        2024: 35,
        2025: 57,
        2026: 41,
    }
    dist = fx_viewer_client.get("/api/club/distribution").json()
    assert [(d["key"], d["n"]) for d in dist][:2] == [("2020", 843), ("2021", 1047)]
    assert len(fx_viewer_client.get("/api/club/attendance").json()) == 360
```

- [ ] **Step 6: Run the club route tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_club_routes.py -v`
Expected: FAIL (7 failed) — `/api/club/…` is not routed yet, so every request returns 404 `{"detail": "Not Found"}` (`KeyError: 'n_events'` / `'status_by_year'` / `'n_rounds'` on the body, list-vs-dict assertion mismatches, and a `TypeError` in the distribution test, which unpacks the dict).

- [ ] **Step 7: Implement `api/routes/club.py`**

Create `backend/src/sunday_clays/api/routes/club.py`:

```python
"""Club summary, attendance, cohorts and score distribution (Plan 06 T7)."""

from datetime import date
from typing import Annotated, Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cohorts import cohort_returns, newcomer_cohorts
from sunday_clays.api.routes._convert import opt_float, opt_int, rows
from sunday_clays.api.routes._filters import round_type_param
from sunday_clays.db import get_session
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

TARGETS_PER_ROUND = 50
ROW_STATUSES: tuple[str, ...] = ("member", "guest", "deceased")


class StatusYearOut(BaseModel):
    year: int
    member_rounds: int
    guest_rounds: int
    deceased_rounds: int
    unrecorded_rounds: int


class ClubSummaryOut(BaseModel):
    first_event: date | None
    last_event: date | None
    n_events: int
    n_scored_events: int
    n_held_events: int
    n_rounds: int
    n_shooters: int
    avg_score: float | None
    median_score: float | None
    top_score: int | None
    n_perfect: int
    clays_thrown: int
    clays_broken: int
    avg_head_count: float | None
    shooters_by_status: dict[str, int]
    status_by_year: list[StatusYearOut]


class AttendanceOut(BaseModel):
    event_date: date
    head_count: int | None
    n_rounds: int
    n_shooters: int
    has_scores: bool
    results_complete: bool


class RetentionOut(BaseModel):
    offset: int
    n_active: int
    share: float


class CohortOut(BaseModel):
    year: int
    n_new: int
    n_returned: int
    retention: list[RetentionOut]


class DistributionOut(BaseModel):
    key: str
    n: int
    mean: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float
    counts: list[int]  # index = score 0..50


def status_by_year(rounds: pd.DataFrame) -> list[StatusYearOut]:
    """Round counts per calendar year by each round's recorded `status` (C7)."""
    out = []
    years = [d.year for d in rounds["event_date"]]
    for year, group in rounds.assign(year=years).groupby("year", sort=True):
        counts = group["status"].value_counts()
        known = {s: int(counts.get(s, 0)) for s in ROW_STATUSES}
        out.append(
            StatusYearOut(
                year=int(str(year)),
                member_rounds=known["member"],
                guest_rounds=known["guest"],
                deceased_rounds=known["deceased"],
                unrecorded_rounds=len(group) - sum(known.values()),
            )
        )
    return out


@router.get("/api/club/summary")
def club_summary(
    session: Annotated[Session, Depends(get_session, scope="function")],
    round_types: list[RoundType] = round_type_param,
) -> ClubSummaryOut:
    events = frames.apply_round_type_filter(frames.load_events(session), round_types)
    rounds = frames.apply_round_type_filter(frames.load_rounds(session), round_types)
    scored = events.loc[events["has_scores"]]
    shooters = rounds.drop_duplicates("shooter_id")
    by_status = shooters["shooter_status"].value_counts()
    return ClubSummaryOut(
        first_event=None if scored.empty else scored["event_date"].min(),
        last_event=None if scored.empty else scored["event_date"].max(),
        n_events=len(events),
        n_scored_events=len(scored),
        n_held_events=int(events["results_complete"].sum()),
        n_rounds=len(rounds),
        n_shooters=len(shooters),
        avg_score=None if rounds.empty else float(rounds["score"].mean()),
        median_score=None if rounds.empty else float(rounds["score"].median()),
        top_score=None if rounds.empty else int(rounds["score"].max()),
        n_perfect=int((rounds["score"] == TARGETS_PER_ROUND).sum()),
        clays_thrown=len(rounds) * TARGETS_PER_ROUND,
        clays_broken=int(rounds["score"].sum()),
        avg_head_count=opt_float(events["head_count"].mean()),
        shooters_by_status={str(k): int(v) for k, v in by_status.items()},
        status_by_year=status_by_year(rounds),
    )


@router.get("/api/club/attendance")
def club_attendance(
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> list[AttendanceOut]:
    return [
        AttendanceOut(
            event_date=r["event_date"],
            head_count=opt_int(r["head_count"]),
            n_rounds=int(r["n_rounds"]),
            n_shooters=int(r["n_shooters"]),
            has_scores=bool(r["has_scores"]),
            results_complete=bool(r["results_complete"]),
        )
        for r in rows(frames.load_events(session))
    ]


@router.get("/api/club/cohorts")
def club_cohorts(session: Annotated[Session, Depends(get_session, scope="function")]) -> list[CohortOut]:
    rounds = frames.load_rounds(session)
    shooters = frames.load_shooters(session)
    retention = newcomer_cohorts(rounds, shooters)
    return [
        CohortOut(
            year=int(c["cohort_year"]),
            n_new=int(c["n_cohort"]),
            n_returned=int(c["n_returned"]),
            retention=[
                RetentionOut(
                    offset=int(r["offset"]),
                    n_active=int(r["n_active"]),
                    share=float(r["share"]),
                )
                for r in rows(
                    retention.loc[retention["cohort_year"] == c["cohort_year"]]
                )
            ],
        )
        for c in rows(cohort_returns(rounds, shooters))
    ]


def score_distribution(rounds: pd.DataFrame) -> list[DistributionOut]:
    """Per calendar year: n, mean, median, P10/P25/P75/P90 and a 0..50 histogram."""
    out = []
    years = [d.year for d in rounds["event_date"]]
    for year, group in rounds.assign(year=years).groupby("year", sort=True):
        scores = group["score"].to_numpy(dtype=np.int64)
        p10, p25, p75, p90 = np.percentile(scores, [10, 25, 75, 90])
        out.append(
            DistributionOut(
                key=str(year),
                n=len(scores),
                mean=float(scores.mean()),
                median=float(np.median(scores)),
                p10=float(p10),
                p25=float(p25),
                p75=float(p75),
                p90=float(p90),
                counts=[
                    int(c) for c in np.bincount(scores, minlength=TARGETS_PER_ROUND + 1)
                ],
            )
        )
    return out


@router.get("/api/club/distribution")
def club_distribution(
    session: Annotated[Session, Depends(get_session, scope="function")],
    by: Literal["year"] = "year",
    round_types: list[RoundType] = round_type_param,
) -> list[DistributionOut]:
    rounds = frames.apply_round_type_filter(frames.load_rounds(session), round_types)
    return score_distribution(rounds)
```

- [ ] **Step 8: Run the club route tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_club_routes.py -v`
Expected: PASS — 7 passed.

- [ ] **Step 9: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass (Plan 04's route auth matrix now also covers the four `/api/club/…` routes → 401 without a cookie); coverage ≥ 90% lines and branches, with `analytics/cohorts.py` and `api/routes/club.py` at 100%.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/cohorts.py \
  backend/src/sunday_clays/api/routes/club.py \
  backend/tests/unit/analytics_core/test_cohorts.py \
  backend/tests/integration/analytics_core/test_club_routes.py
git commit -m "feat(api): club summary, attendance, newcomer cohorts and score distribution

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 8: Shooter insights — profile analytics and `GET /api/shooters/{id}/insights` (master Plan 06 T8)

**Branch:** `task/06-8-shooter-insights`

**Depends on:** Plan 06 T4. Runs in parallel with Tasks 5, 6, 7, 9 (disjoint files; the route lives in its own module, not in Task 6's `shooters.py`, and nothing here imports Task 6).

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/profile.py`
- Create: `backend/src/sunday_clays/api/routes/shooter_insights.py`
- Test: `backend/tests/unit/analytics_core/test_shooter_profile.py`
- Test: `backend/tests/integration/analytics_core/test_shooter_insights_route.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_rounds` (uses `shooter_id, event_date, ordinal, round_id, score, residual, adjusted, is_best_round, event_rank, percentile`), `frames.load_rating_history` (`shooter_id, event_date, mu, var`, published scale), `frames.load_shooters` (`shooter_id, left_censored`); `_filters.resolve_as_of(as_of, tz)` (tests monkeypatch `_filters.today_local`); unit fixture `make_rounds` (tuple or dict specs; unspecified metric columns are NaN, `is_best_round` False, `held` True, `round_id` 1..n); integration fixtures `seed`, C2 `viewer_client`, `fx_session`, `fx_viewer_client`.
  - Task 2: `adjusted` is NaN on non-held rounds; `event_rank`/`percentile` are set on best rounds. Task 4: `residual`, `mu_before` and `rating_history` after `LiveSeed.analyze()`.
  - C2: `get_session`, `get_settings`, `NotFoundError`; C4 `left_censored` (excluded from the club learning-curve median); C12 `events` tiers.
- Produces:
  - `sunday_clays.analytics.profile` (pure; every function sees only the frame it is given): constants `RECENT_ROUNDS = 20`, `BAD_DAY_RESIDUAL = -6.0`, `FORM_ROUNDS = 5`, `HOT = 3.0`, `COLD = -3.0`, `LAYOFF = timedelta(days=42)`, `RATE_WINDOW = timedelta(days=182)`, `RATE_WEEKS = 26`, `EVENT_MILESTONES = (1, 10, 25, 50, 100, 150, 200, 250)`; `FormLabel = Literal["hot", "cold", "steady"]`; frozen dataclasses `LearningPoint{k, value, club_median, n_club}`, `Rust{effect, n, club_effect}`, `Milestone{next_events, events_to_go, weekly_rate, projected_date}`, `ShooterInsights{as_of, n_rounds, floor, ceiling, recent_n, bad_day_rate, form, form_label, wins, podiums, avg_percentile, peak_mu, peak_date, learning_curve: tuple[LearningPoint, ...], rust: Rust, milestone: Milestone}`.
  - Functions: `floor_ceiling(rounds) -> tuple[float | None, float | None, int]`; `bad_day_rate(rounds) -> float | None`; `form(rounds) -> tuple[float | None, FormLabel | None]`; `event_values(rounds) -> pd.DataFrame[shooter_id, k, value]`; `learning_curve(rounds, shooters, shooter_id: int) -> tuple[LearningPoint, ...]`; `rust_effect(rounds) -> tuple[float | None, int]`; `peak(history) -> tuple[float | None, date | None]`; `milestone(event_dates: set[date], as_of: date) -> Milestone`; `shooter_insights(rounds, history, shooters, shooter_id: int, as_of: date) -> ShooterInsights` (slices every input to `event_date <= as_of`).
  - `sunday_clays.api.routes.shooter_insights` (auto-discovered, `require_viewer`): `GET /api/shooters/{id}/insights?as_of=` (C8 path template; bound as `shooter_id: Annotated[int, Path(alias="id")]`, so the OpenAPI key is `/api/shooters/{id}/insights` with path param `id`, as Plan 08 T2a indexes it) → `ShooterInsightsOut{shooter_id, as_of, n_rounds, floor, ceiling, recent_n, bad_day_rate, form, form_label, wins, podiums, avg_percentile, peak_mu, peak_date, learning_curve: list[LearningPointOut{k, value, club_median, n_club}], rust: RustOut{effect, n, club_effect}, milestone: MilestoneOut{next_events, events_to_go, weekly_rate, projected_date}}`; `as_of` defaults to today in the club timezone; unknown shooter → 404 `shooter_not_found`. Plan 08 T2a's insights card reads this.

- [ ] **Step 1: Write the failing profile tests**

Create `backend/tests/unit/analytics_core/test_shooter_profile.py`:

```python
import math
from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import profile

AS_OF = date(2026, 9, 27)


def _weeks_back(n: int) -> list[date]:
    return [AS_OF - timedelta(days=7 * k) for k in reversed(range(n))]


def _history(rows: list[tuple[int, date, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["shooter_id", "event_date", "mu"]).assign(
        var=4.0
    )


def _shooters(censored: set[int], ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {"shooter_id": ids, "left_censored": [i in censored for i in ids]}
    )


def test_floor_and_ceiling_use_last_twenty_rounds(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [(d, 1, s) for d, s in zip(_weeks_back(25), range(1, 26), strict=True)]
    )
    floor, ceiling, n = profile.floor_ceiling(rounds)
    # last 20 scores are 6..25: P10 = 6 + 0.1*19, P90 = 6 + 0.9*19
    assert (floor, ceiling, n) == (pytest.approx(7.9), pytest.approx(23.1), 20)
    assert profile.floor_ceiling(rounds.iloc[0:0]) == (None, None, 0)


def test_bad_day_rate_counts_residual_at_or_below_minus_six(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    dates = _weeks_back(5)
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": 30, "residual": r}
            for d, r in zip(dates, [-7.0, -6.0, -5.9, 2.0, math.nan], strict=True)
        ]
    )
    assert profile.bad_day_rate(rounds) == 0.5
    assert profile.bad_day_rate(rounds.assign(residual=math.nan)) is None


@pytest.mark.parametrize(
    ("residuals", "value", "label"),
    [
        ([9.0, 4.0, 3.0, 3.0, 2.0, 3.0], 3.0, "hot"),
        ([0.0, -4.0, -3.0, -2.0, -3.0, -3.0], -3.0, "cold"),
        ([1.0, 2.0, -2.0, 0.0, 1.0], 0.4, "steady"),
    ],
)
def test_form_is_mean_residual_of_last_five(
    make_rounds: Callable[..., pd.DataFrame],
    residuals: list[float],
    value: float,
    label: str,
) -> None:
    dates = _weeks_back(len(residuals))
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": 30, "residual": r}
            for d, r in zip(dates, residuals, strict=True)
        ]
    )
    assert profile.form(rounds) == (pytest.approx(value), label)
    assert profile.form(rounds.tail(4)) == (None, None)


def test_learning_curve_vs_club_median_excluding_left_censored(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = _weeks_back(3)
    specs = [
        {"event_date": d[0], "shooter_id": 1, "score": 30, "adjusted": -4.0},
        {"event_date": d[1], "shooter_id": 1, "score": 30, "adjusted": 0.0},
        {"event_date": d[1], "shooter_id": 1, "score": 34, "adjusted": 2.0},
        {"event_date": d[0], "shooter_id": 2, "score": 30, "adjusted": -2.0},
        {"event_date": d[1], "shooter_id": 2, "score": 30, "adjusted": 6.0},
        {"event_date": d[2], "shooter_id": 2, "score": 30, "adjusted": 8.0},
        {"event_date": d[0], "shooter_id": 3, "score": 30, "adjusted": 20.0},
        {
            "event_date": d[2],
            "shooter_id": 1,
            "score": 30,
            "adjusted": math.nan,
            "held": False,
        },
    ]
    curve = profile.learning_curve(make_rounds(specs), _shooters({3}, [1, 2, 3]), 1)

    assert curve == (
        profile.LearningPoint(k=1, value=-4.0, club_median=-3.0, n_club=2),
        profile.LearningPoint(k=2, value=1.0, club_median=3.5, n_club=2),
    )


def test_rust_effect_after_42_day_layoff(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d0 = date(2026, 1, 4)
    dates = [
        d0,
        d0 + timedelta(days=7),
        d0 + timedelta(days=56),
        d0 + timedelta(days=63),
        d0 + timedelta(days=104),
    ]
    rounds = make_rounds(
        [
            {"event_date": d, "shooter_id": 1, "score": 30, "residual": r}
            for d, r in zip(dates, [0.0, 2.0, -4.0, 2.0, 1.0], strict=True)
        ]
    )
    # gaps: 7, 49 (layoff), 7, 41 (not a layoff) -> post-layoff = [-4]; others mean 1.25
    effect, n = profile.rust_effect(rounds)
    assert (effect, n) == (pytest.approx(-4.0 - 1.25), 1)
    assert profile.rust_effect(rounds.iloc[:2]) == (None, 0)
    exactly = make_rounds(
        [
            {"event_date": d0, "shooter_id": 1, "score": 30, "residual": 0.0},
            {
                "event_date": d0 + timedelta(days=42),
                "shooter_id": 1,
                "score": 30,
                "residual": -3.0,
            },
        ]
    )
    # a gap of exactly 42 days is a layoff
    assert profile.rust_effect(exactly) == (-3.0, 1)
    only_post = make_rounds(
        [
            {"event_date": d0, "shooter_id": 1, "score": 30, "held": False},
            {
                "event_date": d0 + timedelta(days=50),
                "shooter_id": 1,
                "score": 30,
                "residual": -3.0,
            },
        ]
    )
    # the gap is measured from the non-held date; no residual round is left for "other"
    assert profile.rust_effect(only_post) == (None, 1)


def test_peak_prefers_earliest_date_on_ties() -> None:
    d = _weeks_back(3)
    history = _history([(1, d[0], 35.0), (1, d[1], 37.0), (1, d[2], 37.0)])
    assert profile.peak(history) == (37.0, d[1])
    assert profile.peak(history.iloc[0:0]) == (None, None)


def test_milestone_projection_from_26_week_rate() -> None:
    recent = set(_weeks_back(13))  # 13 events in the last 26 weeks -> 0.5 per week
    older = {AS_OF - timedelta(days=400 + 7 * k) for k in range(11)}
    m = profile.milestone(recent | older, AS_OF)  # 24 events -> next tier 25
    assert (m.next_events, m.events_to_go, m.weekly_rate) == (25, 1, 0.5)
    assert m.projected_date == AS_OF + timedelta(days=14)
    stale = profile.milestone(older, AS_OF)
    assert (stale.next_events, stale.weekly_rate, stale.projected_date) == (
        25,
        0.0,
        None,
    )
    done = profile.milestone({AS_OF - timedelta(days=7 * k) for k in range(250)}, AS_OF)
    assert (done.next_events, done.events_to_go, done.projected_date) == (
        None,
        None,
        None,
    )


def test_insights_wins_podiums_and_percentile(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = _weeks_back(3)
    rounds = make_rounds(
        [
            {
                "event_date": d[0],
                "shooter_id": 1,
                "score": 40,
                "is_best_round": True,
                "event_rank": 1.0,
                "percentile": 1.0,
            },
            {
                "event_date": d[0],
                "shooter_id": 1,
                "score": 20,
                "is_best_round": False,
                "event_rank": math.nan,
            },
            {
                "event_date": d[1],
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": 3.0,
                "percentile": 0.5,
            },
            {
                "event_date": d[2],
                "shooter_id": 1,
                "score": 25,
                "is_best_round": True,
                "event_rank": 6.0,
                "percentile": 0.0,
            },
        ]
    )
    out = profile.shooter_insights(
        rounds, _history([]), _shooters(set(), [1]), 1, AS_OF
    )
    assert (out.wins, out.podiums, out.n_rounds) == (1, 2, 4)
    assert out.avg_percentile == pytest.approx(0.5)
    assert out.peak_mu is None


def test_insights_no_leak(make_rounds: Callable[..., pd.DataFrame]) -> None:
    dates = _weeks_back(12)
    specs = [
        {
            "event_date": d,
            "shooter_id": s,
            "score": 25 + s + i % 4,
            "residual": float(i % 5 - 2),
            "adjusted": float(i % 3 - 1),
            "is_best_round": True,
            "event_rank": float(s),
            "percentile": 1.0 / s,
        }
        for i, d in enumerate(dates)
        for s in (1, 2, 3)
    ]
    rounds = make_rounds(specs)
    history = _history(
        [(s, d, 30.0 + s + i) for i, d in enumerate(dates) for s in (1, 2, 3)]
    )
    shooters = _shooters({3}, [1, 2, 3])
    later = [AS_OF + timedelta(days=7 * k) for k in range(1, 4)]
    more_rounds = pd.concat(
        [
            rounds,
            make_rounds(
                [
                    {
                        "event_date": d,
                        "shooter_id": s,
                        "score": 50,
                        "residual": 9.0,
                        "adjusted": 9.0,
                        "is_best_round": True,
                        "event_rank": 1.0,
                        "percentile": 1.0,
                        "round_id": 1000 + 10 * k + s,
                    }
                    for k, d in enumerate(later)
                    for s in (1, 2, 4)
                ]
            ),
        ]
    )
    more_history = pd.concat([history, _history([(1, d, 99.0) for d in later])])

    assert profile.shooter_insights(
        rounds, history, shooters, 1, AS_OF
    ) == profile.shooter_insights(more_rounds, more_history, shooters, 1, AS_OF)
```

- [ ] **Step 2: Run the profile tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_shooter_profile.py -v`
Expected: collection ERROR — `ImportError: cannot import name 'profile' from 'sunday_clays.analytics'`.

- [ ] **Step 3: Implement `analytics/profile.py`**

Create `backend/src/sunday_clays/analytics/profile.py`:

```python
"""Per-shooter insights as of a date (Plan 06 T8): pure functions over frames."""

import itertools
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd

RECENT_ROUNDS = 20
BAD_DAY_RESIDUAL = -6.0
FORM_ROUNDS = 5
HOT = 3.0
COLD = -3.0
LAYOFF = timedelta(days=42)
RATE_WINDOW = timedelta(days=182)  # 26 weeks
RATE_WEEKS = 26
# C12 `events` tiers
EVENT_MILESTONES: tuple[int, ...] = (1, 10, 25, 50, 100, 150, 200, 250)

FormLabel = Literal["hot", "cold", "steady"]


@dataclass(frozen=True)
class LearningPoint:
    k: int
    value: float
    club_median: float | None
    n_club: int


@dataclass(frozen=True)
class Rust:
    effect: float | None
    n: int
    club_effect: float | None


@dataclass(frozen=True)
class Milestone:
    next_events: int | None
    events_to_go: int | None
    weekly_rate: float
    projected_date: date | None


@dataclass(frozen=True)
class ShooterInsights:
    as_of: date
    n_rounds: int
    floor: float | None
    ceiling: float | None
    recent_n: int
    bad_day_rate: float | None
    form: float | None
    form_label: FormLabel | None
    wins: int
    podiums: int
    avg_percentile: float | None
    peak_mu: float | None
    peak_date: date | None
    learning_curve: tuple[LearningPoint, ...]
    rust: Rust
    milestone: Milestone


def _upto(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    return df.loc[df["event_date"] <= as_of]


def _chronological(rounds: pd.DataFrame) -> pd.DataFrame:
    return rounds.sort_values(["event_date", "ordinal", "round_id"], kind="mergesort")


def floor_ceiling(rounds: pd.DataFrame) -> tuple[float | None, float | None, int]:
    """P10/P90 (linear) of the last 20 rounds, and how many rounds were used."""
    recent = (
        _chronological(rounds).tail(RECENT_ROUNDS)["score"].to_numpy(dtype=np.float64)
    )
    if recent.size == 0:
        return None, None, 0
    p10, p90 = np.percentile(recent, [10, 90])
    return float(p10), float(p90), int(recent.size)


def bad_day_rate(rounds: pd.DataFrame) -> float | None:
    """Share of rounds (with a residual) whose residual is <= -6."""
    residuals = rounds["residual"].dropna()
    return None if residuals.empty else float((residuals <= BAD_DAY_RESIDUAL).mean())


def form(rounds: pd.DataFrame) -> tuple[float | None, FormLabel | None]:
    """Mean residual of the last 5 rounds with a residual; None with fewer than 5."""
    with_residual = _chronological(rounds.loc[rounds["residual"].notna()])
    if len(with_residual) < FORM_ROUNDS:
        return None, None
    value = float(with_residual.tail(FORM_ROUNDS)["residual"].mean())
    label: FormLabel = "hot" if value >= HOT else "cold" if value <= COLD else "steady"
    return value, label


def event_values(rounds: pd.DataFrame) -> pd.DataFrame:
    """[shooter_id, k, value]: mean `adjusted` per (shooter, held event), k by date."""
    held = rounds.loc[rounds["adjusted"].notna()]
    per_event = (
        held.groupby(["shooter_id", "event_date"])["adjusted"]
        .mean()
        .reset_index()
        .sort_values(["shooter_id", "event_date"])
    )
    per_event["k"] = per_event.groupby("shooter_id").cumcount() + 1
    return per_event.rename(columns={"adjusted": "value"})[["shooter_id", "k", "value"]]


def learning_curve(
    rounds: pd.DataFrame, shooters: pd.DataFrame, shooter_id: int
) -> tuple[LearningPoint, ...]:
    """The shooter's adjusted score by career event index k vs the club median at k.

    The club median excludes left_censored shooters (C4).
    """
    values = event_values(rounds)
    censored = set(shooters.loc[shooters["left_censored"], "shooter_id"])
    club = values.loc[~values["shooter_id"].isin(censored)].groupby("k")["value"]
    medians, sizes = club.median(), club.size()
    mine = values.loc[values["shooter_id"] == shooter_id]
    return tuple(
        LearningPoint(
            k=int(k),
            value=float(v),
            club_median=float(medians[k]) if k in medians.index else None,
            n_club=int(sizes[k]) if k in sizes.index else 0,
        )
        for k, v in zip(mine["k"], mine["value"], strict=True)
    )


def _post_layoff_mask(rounds: pd.DataFrame) -> pd.Series:
    """True for rounds at a shooter's first event after a gap of >= 42 days."""
    dates: dict[int, set[date]] = defaultdict(set)
    for shooter_id, event_date in zip(
        rounds["shooter_id"], rounds["event_date"], strict=True
    ):
        dates[int(shooter_id)].add(event_date)
    after: set[tuple[int, date]] = set()
    for shooter_id, attended in dates.items():
        ordered = sorted(attended)
        for previous, current in itertools.pairwise(ordered):
            if current - previous >= LAYOFF:
                after.add((shooter_id, current))
    flags = [
        (int(s), d) in after
        for s, d in zip(rounds["shooter_id"], rounds["event_date"], strict=True)
    ]
    return pd.Series(flags, index=rounds.index, dtype=bool)


def rust_effect(rounds: pd.DataFrame) -> tuple[float | None, int]:
    """Mean residual after a >= 42-day layoff minus the mean on all other rounds, and n.

    Gaps are measured between attended dates (held or not); only rounds with a residual
    enter either mean. None when either side is empty.
    """
    after_layoff = _post_layoff_mask(rounds)
    has_residual = rounds["residual"].notna()
    post, other = after_layoff & has_residual, ~after_layoff & has_residual
    n = int(post.sum())
    if n == 0 or not other.any():
        return None, n
    residual = rounds["residual"]
    return float(residual[post].mean() - residual[other].mean()), n


def peak(history: pd.DataFrame) -> tuple[float | None, date | None]:
    """Highest published mu (earliest date on ties)."""
    if history.empty:
        return None, None
    top = history.sort_values(["mu", "event_date"], ascending=[False, True]).iloc[0]
    return float(top["mu"]), top["event_date"]


def milestone(event_dates: set[date], as_of: date) -> Milestone:
    """Next `events` tier and a date projected from the 26-week attendance rate."""
    n_events = len(event_dates)
    rate = sum(1 for d in event_dates if d > as_of - RATE_WINDOW) / RATE_WEEKS
    upcoming = [m for m in EVENT_MILESTONES if m > n_events]
    if not upcoming:
        return Milestone(
            next_events=None, events_to_go=None, weekly_rate=rate, projected_date=None
        )
    to_go = upcoming[0] - n_events
    projected = (
        None if rate == 0 else as_of + timedelta(days=7 * math.ceil(to_go / rate))
    )
    return Milestone(
        next_events=upcoming[0],
        events_to_go=to_go,
        weekly_rate=rate,
        projected_date=projected,
    )


def shooter_insights(
    rounds: pd.DataFrame,
    history: pd.DataFrame,
    shooters: pd.DataFrame,
    shooter_id: int,
    as_of: date,
) -> ShooterInsights:
    """Everything is computed from rows dated <= as_of (no-leak)."""
    club_rounds = _upto(rounds, as_of)
    mine = club_rounds.loc[club_rounds["shooter_id"] == shooter_id]
    best = mine.loc[mine["is_best_round"]]
    floor, ceiling, recent_n = floor_ceiling(mine)
    form_value, form_label = form(mine)
    peak_mu, peak_date = peak(
        _upto(history.loc[history["shooter_id"] == shooter_id], as_of)
    )
    effect, n = rust_effect(mine)
    club_effect, _ = rust_effect(club_rounds)
    percentiles = best["percentile"].dropna()
    return ShooterInsights(
        as_of=as_of,
        n_rounds=len(mine),
        floor=floor,
        ceiling=ceiling,
        recent_n=recent_n,
        bad_day_rate=bad_day_rate(mine),
        form=form_value,
        form_label=form_label,
        wins=int((best["event_rank"] == 1).sum()),
        podiums=int((best["event_rank"] <= 3).sum()),
        avg_percentile=None if percentiles.empty else float(percentiles.mean()),
        peak_mu=peak_mu,
        peak_date=peak_date,
        learning_curve=learning_curve(club_rounds, shooters, shooter_id),
        rust=Rust(effect=effect, n=n, club_effect=club_effect),
        milestone=milestone(set(mine["event_date"]), as_of),
    )
```

- [ ] **Step 4: Run the profile tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_shooter_profile.py -v`
Expected: PASS — 11 passed.

- [ ] **Step 5: Write the failing insights route tests**

Create `backend/tests/integration/analytics_core/test_shooter_insights_route.py`. The fixture case looks the shooter up with SQL, so it does not need Task 6's `GET /api/shooters`. Its numbers come from `scores_2026-09-27.xlsx`: "Ackerly, Alton" has 170 rounds on 167 event dates, so his next `events` tier is 200, 33 events away.

```python
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)


def test_insights_path_is_the_c8_template() -> None:
    op = create_app().openapi()["paths"]["/api/shooters/{id}/insights"]["get"]
    assert [p["name"] for p in op["parameters"] if p["in"] == "path"] == ["id"]


def test_insights_as_of_defaults_to_today_and_slices(
    seed: Any, viewer_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    for k in range(6):
        d = TODAY - timedelta(days=7 * k)
        seed.round(d, ann, 30 + k)
        seed.round(d, bob, 29)
    seed.finish()
    seed.analyze()

    today = viewer_client.get(f"/api/shooters/{ann}/insights").json()
    earlier = viewer_client.get(
        f"/api/shooters/{ann}/insights",
        params={"as_of": (TODAY - timedelta(days=14)).isoformat()},
    ).json()

    assert today["as_of"] == TODAY.isoformat()
    assert (today["n_rounds"], today["wins"], today["podiums"]) == (6, 6, 6)
    assert today["milestone"]["next_events"] == 10
    assert len(today["learning_curve"]) == 6
    assert today["form_label"] in {"hot", "cold", "steady"}
    assert today["peak_mu"] is not None
    assert (earlier["n_rounds"], len(earlier["learning_curve"])) == (4, 4)


def test_insights_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    r = viewer_client.get("/api/shooters/999999/insights")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "shooter_not_found"


def test_insights_on_committed_fixtures(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    shooter_id = fx_session.execute(
        text("SELECT shooter_id FROM shooter_profiles WHERE display_name = :n"),
        {"n": "Ackerly, Alton"},
    ).scalar_one()
    body = fx_viewer_client.get(
        f"/api/shooters/{shooter_id}/insights", params={"as_of": "2026-09-27"}
    ).json()

    assert body["n_rounds"] == 170
    assert (body["milestone"]["next_events"], body["milestone"]["events_to_go"]) == (
        200,
        33,
    )
    assert body["recent_n"] == 20
    assert body["floor"] <= body["ceiling"]
    assert body["rust"]["club_effect"] is not None
```

- [ ] **Step 6: Run the insights route tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_shooter_insights_route.py -v`
Expected: FAIL (4 failed) — `/api/shooters/{id}/insights` is not routed yet, so requests return 404 `{"detail": "Not Found"}` (`KeyError: 'as_of'`, `KeyError: 'error'`, `KeyError: 'n_rounds'`) and the OpenAPI schema has no `/api/shooters/{id}/insights` key (`KeyError`).

- [ ] **Step 7: Implement `api/routes/shooter_insights.py`**

Create `backend/src/sunday_clays/api/routes/shooter_insights.py`:

```python
"""GET /api/shooters/{id}/insights?as_of= (Plan 06 T8)."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.profile import shooter_insights
from sunday_clays.api.routes._filters import resolve_as_of
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import NotFoundError

router = APIRouter()


class LearningPointOut(BaseModel):
    k: int
    value: float
    club_median: float | None
    n_club: int


class RustOut(BaseModel):
    effect: float | None
    n: int
    club_effect: float | None


class MilestoneOut(BaseModel):
    next_events: int | None
    events_to_go: int | None
    weekly_rate: float
    projected_date: date | None


class ShooterInsightsOut(BaseModel):
    shooter_id: int
    as_of: date
    n_rounds: int
    floor: float | None
    ceiling: float | None
    recent_n: int
    bad_day_rate: float | None
    form: float | None
    form_label: Literal["hot", "cold", "steady"] | None
    wins: int
    podiums: int
    avg_percentile: float | None
    peak_mu: float | None
    peak_date: date | None
    learning_curve: list[LearningPointOut]
    rust: RustOut
    milestone: MilestoneOut


@router.get("/api/shooters/{id}/insights")
def get_shooter_insights(
    shooter_id: Annotated[int, Path(alias="id")],
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: date | None = None,
) -> ShooterInsightsOut:
    shooters = frames.load_shooters(session)
    if shooters.loc[shooters["shooter_id"] == shooter_id].empty:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    insights = shooter_insights(
        frames.load_rounds(session),
        frames.load_rating_history(session),
        shooters,
        shooter_id,
        resolve_as_of(as_of, settings.timezone),
    )
    return ShooterInsightsOut.model_validate(
        {"shooter_id": shooter_id, **asdict(insights)}
    )
```

- [ ] **Step 8: Run the insights route tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_shooter_insights_route.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 9: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass (Plan 04's route auth matrix now also covers `/api/shooters/{id}/insights` → 401 without a cookie); coverage ≥ 90% lines and branches, with `analytics/profile.py` and `api/routes/shooter_insights.py` at 100%.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/profile.py \
  backend/src/sunday_clays/api/routes/shooter_insights.py \
  backend/tests/unit/analytics_core/test_shooter_profile.py \
  backend/tests/integration/analytics_core/test_shooter_insights_route.py
git commit -m "feat(api): shooter insights with floor/ceiling, form, rust and milestones

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

### Task 9: Club insights — regulars, guest conversion, parity and trends (master Plan 06 T9)

**Branch:** `task/06-9-club-insights`

**Depends on:** Plan 06 T4. Runs in parallel with Tasks 5, 6, 7, 8 (disjoint files; the routes live in their own module, not in Task 7's `club.py`, and nothing here imports Task 6 or 7 — see Decision 24).

**Test environment:** Integration tests need Docker running (testcontainers `postgres:17`) or an unshared `TEST_DATABASE_URL`. Every Run command starts from the worktree root (`cd backend && …`); the commit step stays root-relative (`git add backend/…`).

**Files:**
- Create: `backend/src/sunday_clays/analytics/club_insights.py`
- Create: `backend/src/sunday_clays/api/routes/club_insights.py`
- Test: `backend/tests/unit/analytics_core/test_club_insights.py`
- Test: `backend/tests/integration/analytics_core/test_club_insights_routes.py`

**Interfaces:**
- Consumes:
  - Task 1: `frames.load_rounds` (uses `shooter_id, display_name, event_date, status, shooter_status, is_best_round, event_rank, mu_before`), `frames.load_events` (uses `event_date, results_complete, head_count, top_score, median, difficulty`); `_filters.resolve_as_of(as_of, tz)` (tests monkeypatch `_filters.today_local`); unit fixtures `make_rounds`, `make_events` (event defaults `results_complete=True`, metrics NaN); integration fixtures `seed`, C2 `viewer_client`, `fx_viewer_client`.
  - Task 2: `event_rank` on best rounds, `event_metrics.top_score/median`. Task 4: `mu_before`, `difficulty`, `LiveSeed.analyze()`.
  - C2: `get_session`, `get_settings`; C4 held = `results_complete`; C7 status rules (regulars exclude current `shooter_status = 'deceased'`; conversion uses per-row `status`).
- Produces:
  - `sunday_clays.analytics.club_insights` (pure): constants `REGULAR_WINDOW = timedelta(days=364)`, `REGULAR_SHARE = 0.5`, `LAPSED_LOOKBACK = timedelta(days=180)`, `LAPSED_QUIET = timedelta(days=90)`, `ROLLING_EVENTS = 8`; frozen dataclasses `CoreShooter{shooter_id, display_name, events_attended, share}`, `LapsedShooter{shooter_id, display_name, last_event}`, `Regulars{as_of, n_held_window, core: tuple[CoreShooter, ...], lapsed: tuple[LapsedShooter, ...]}`, `ConversionYear{year, new_guests, converted, median_days_to_convert}`, `ParityYear{year, n_events, distinct_winners, top3_share, favorite_win_rate}`, `YearTrend{year, events_held, mean_head_count, unique_shooters, ytd_events, ytd_rounds, ytd_unique_shooters, ytd_events_yoy}`, `EventTrend{event_date, top_score, median, difficulty, top_score_rolling8, median_rolling8, difficulty_rolling8}`, `MonthTrend{month, n_events, mean_head_count, mean_median}`.
  - Functions: `regulars(rounds, events, as_of: date) -> Regulars`; `guest_conversion(rounds) -> list[ConversionYear]`; `parity(rounds) -> list[ParityYear]`; `yearly_trends(rounds, events, as_of: date) -> list[YearTrend]`; `event_trends(events, as_of: date) -> list[EventTrend]`; `seasonality(events, as_of: date) -> list[MonthTrend]` (always 12 rows).
  - `sunday_clays.api.routes.club_insights` (auto-discovered, `require_viewer`): `GET /api/club/regulars?as_of=` → `RegularsOut{as_of, n_held_window, core: list[CoreShooterOut], lapsed: list[LapsedShooterOut]}` (core sorted by events attended desc then name; lapsed by last event then name); `GET /api/club/conversion` → `list[ConversionYearOut]`; `GET /api/club/parity?by=year` → `list[ParityYearOut]` (any other `by` → 422); `GET /api/club/trends` → `ClubTrendsOut{as_of, years: list[YearTrendOut], events: list[EventTrendOut], months: list[MonthTrendOut]}` with `as_of` = today in the club timezone. The `*Out` models mirror the dataclasses field for field.

- [ ] **Step 1: Write the failing club-insights tests**

Create `backend/tests/unit/analytics_core/test_club_insights.py`:

```python
from collections.abc import Callable
from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import club_insights as ci

AS_OF = date(2026, 9, 27)
WEEKS = [AS_OF - timedelta(days=7 * k) for k in range(60)]  # WEEKS[0] = AS_OF


def test_regulars_core_needs_half_of_held_window(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    window = WEEKS[:10]  # 10 held events inside (as_of - 364d, as_of]
    specs = [(d, 1, 30) for d in window[:6]]  # 6/10 -> core
    specs += [(d, 2, 30) for d in window[:5]]  # 5/10 -> core (exactly 50%)
    specs += [(d, 3, 30) for d in window[:4]]  # 4/10 -> not core
    specs += [
        {"event_date": d, "shooter_id": 4, "score": 30, "shooter_status": "deceased"}
        for d in window
    ]
    specs += [(AS_OF - timedelta(days=364), 3, 30)]  # outside the window

    result = ci.regulars(make_rounds(specs), make_events(window), AS_OF)

    assert result.n_held_window == 10
    assert [(c.shooter_id, c.events_attended, c.share) for c in result.core] == [
        (1, 6, 0.6),
        (2, 5, 0.5),
    ]


def test_lapsed_regulars(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    # 8 held events in (as_of - 544d, as_of - 364d]: inside the as_of - 180d window only
    early = [AS_OF - timedelta(days=364 + 7 * k) for k in range(8)]
    events = make_events([*early, WEEKS[2]])
    specs = [(d, 5, 30) for d in early]  # regular then, silent since -> lapsed
    specs += [(d, 6, 30) for d in early] + [(WEEKS[2], 6, 30)]  # came back 14 days ago
    specs += [
        {"event_date": d, "shooter_id": 7, "score": 30, "shooter_status": "deceased"}
        for d in early
    ]

    result = ci.regulars(make_rounds(specs), events, AS_OF)

    assert [(x.shooter_id, x.last_event) for x in result.lapsed] == [(5, early[0])]
    assert [c.shooter_id for c in result.core] == [6]
    assert result.n_held_window == 1


def test_regulars_no_leak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    dates = WEEKS[:30]
    rounds = make_rounds([(d, s, 30) for d in dates for s in (1, 2) if (d.day + s) % 3])
    events = make_events(dates)
    future = [AS_OF + timedelta(days=7 * k) for k in range(1, 5)]
    more = pd.concat(
        [rounds, make_rounds([(d, s, 30) for d in future for s in (1, 3)])]
    )
    assert ci.regulars(rounds, events, AS_OF) == ci.regulars(
        more, make_events(dates + future), AS_OF
    )


def test_guest_conversion_by_year(make_rounds: Callable[..., pd.DataFrame]) -> None:
    def r(d: date, sid: int, status: str) -> dict[str, object]:
        return {"event_date": d, "shooter_id": sid, "score": 30, "status": status}

    rounds = make_rounds(
        [
            r(date(2024, 5, 5), 1, "guest"),
            r(date(2024, 6, 2), 1, "guest"),
            r(date(2025, 1, 5), 1, "member"),
            r(date(2025, 2, 2), 1, "member"),
            r(date(2024, 8, 4), 2, "guest"),
            r(date(2023, 3, 5), 3, "member"),
            r(date(2025, 3, 2), 3, "guest"),
            r(date(2025, 3, 30), 3, "member"),
        ]
    )

    assert ci.guest_conversion(rounds) == [
        ci.ConversionYear(2024, new_guests=2, converted=0, median_days_to_convert=None),
        ci.ConversionYear(
            2025, new_guests=1, converted=2, median_days_to_convert=(245 + 28) / 2
        ),
    ]


def test_parity_winners_top3_share_and_favorites(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    d = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(4)]

    def best(day: date, sid: int, rank: float, mu: float) -> dict[str, object]:
        return {
            "event_date": day,
            "shooter_id": sid,
            "score": 30,
            "is_best_round": True,
            "event_rank": rank,
            "mu_before": mu,
        }

    rounds = make_rounds(
        [
            best(d[0], 1, 1, 40),
            best(d[0], 2, 2, 30),
            best(d[1], 1, 1, 40),
            best(d[1], 2, 1, 30),
            best(d[2], 3, 1, 30),
            best(d[2], 1, 2, 41),
            best(d[3], 4, 1, float("nan")),
            best(d[3], 1, 2, float("nan")),
            {
                "event_date": date(2025, 6, 1),
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": 1.0,
                "mu_before": 35.0,
            },
        ]
    )

    by_year = {p.year: p for p in ci.parity(rounds)}

    assert by_year[2025] == ci.ParityYear(2025, 1, 1, 1.0, 1.0)
    p = by_year[2026]
    # wins: shooter 1 x2, 2 x1 (tie), 3 x1, 4 x1 -> total 5, top-3 = 2+1+1
    assert (p.n_events, p.distinct_winners) == (4, 4)
    assert p.top3_share == pytest.approx(4 / 5)
    assert p.favorite_win_rate == pytest.approx(2 / 3)  # event 4 has no ratings


def test_parity_skips_years_without_ranked_winners(
    make_rounds: Callable[..., pd.DataFrame],
) -> None:
    rounds = make_rounds(
        [
            {
                "event_date": date(2026, 1, 4),
                "shooter_id": 1,
                "score": 30,
                "is_best_round": True,
                "event_rank": float("nan"),
            }
        ]
    )
    assert ci.parity(rounds) == []


def test_yearly_trends_ytd_and_yoy(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    as_of = date(2026, 3, 1)
    specs = [
        (date(2025, 1, 5), 1, 30),
        (date(2025, 2, 2), 2, 30),
        (date(2025, 6, 1), 1, 30),
        (date(2026, 1, 4), 1, 30),
        (date(2026, 2, 1), 1, 30),
        (date(2026, 3, 1), 3, 30),
        (date(2026, 3, 8), 1, 30),
    ]
    events = make_events(
        [{"event_date": d, "head_count": 10.0 + i} for i, (d, _, _) in enumerate(specs)]
    )

    years = ci.yearly_trends(make_rounds(specs), events, as_of)

    assert [(y.year, y.events_held, y.unique_shooters) for y in years] == [
        (2025, 3, 2),
        (2026, 3, 2),
    ]
    assert [(y.ytd_events, y.ytd_rounds, y.ytd_unique_shooters) for y in years] == [
        (2, 2, 2),
        (3, 3, 2),
    ]
    assert years[0].ytd_events_yoy is None
    assert years[1].ytd_events_yoy == pytest.approx(0.5)
    assert years[1].mean_head_count == pytest.approx(14.0)


def test_leap_day_cutoff_clamps_to_feb_28(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    specs = [(date(2023, 2, 26), 1, 30), (date(2024, 2, 25), 1, 30)]
    years = ci.yearly_trends(
        make_rounds(specs), make_events([d for d, _, _ in specs]), date(2024, 2, 29)
    )
    assert [y.ytd_events for y in years] == [1, 1]


def test_event_trends_rolling_eight_and_seasonality(
    make_events: Callable[..., pd.DataFrame],
) -> None:
    dates = [date(2026, 1, 4) + timedelta(days=7 * k) for k in range(10)]
    events = make_events(
        [
            {
                "event_date": d,
                "top_score": 40 + k,
                "median": 30.0,
                "difficulty": float(k),
                "head_count": 20.0,
            }
            for k, d in enumerate(dates)
        ]
        + [
            {
                "event_date": date(2026, 3, 22),
                "results_complete": False,
                "top_score": 50,
                "median": 10.0,
                "difficulty": float("nan"),
                "head_count": 40.0,
            }
        ]
    )

    trend = ci.event_trends(events, date(2026, 12, 31))
    assert len(trend) == 10
    assert trend[0].top_score_rolling8 == 40.0
    assert trend[9].top_score_rolling8 == pytest.approx(sum(range(42, 50)) / 8)
    assert trend[9].difficulty_rolling8 == pytest.approx(sum(range(2, 10)) / 8)
    months = {m.month: m for m in ci.seasonality(events, date(2026, 12, 31))}
    assert (months[1].n_events, months[3].n_events, months[7].n_events) == (4, 2, 0)
    assert months[3].mean_head_count == 20.0  # the non-held March event is ignored
    assert months[7].mean_median is None


def test_trends_no_leak(
    make_rounds: Callable[..., pd.DataFrame], make_events: Callable[..., pd.DataFrame]
) -> None:
    dates = WEEKS[:20]
    rounds = make_rounds([(d, s, 30 + s) for d in dates for s in (1, 2)])
    events = make_events(
        [
            {
                "event_date": d,
                "top_score": 40,
                "median": 30.0,
                "difficulty": 0.5,
                "head_count": 12.0,
            }
            for d in dates
        ]
    )
    future = [AS_OF + timedelta(days=7 * k) for k in range(1, 4)]
    more_rounds = pd.concat([rounds, make_rounds([(d, 9, 50) for d in future])])
    more_events = make_events(
        [
            {
                "event_date": d,
                "top_score": 50,
                "median": 45.0,
                "difficulty": -3.0,
                "head_count": 30.0,
            }
            for d in dates + future
        ]
    )
    more_events.loc[
        more_events["event_date"] <= AS_OF,
        ["top_score", "median", "difficulty", "head_count"],
    ] = [40, 30.0, 0.5, 12.0]
    assert ci.yearly_trends(rounds, events, AS_OF) == ci.yearly_trends(
        more_rounds, more_events, AS_OF
    )
    assert ci.event_trends(events, AS_OF) == ci.event_trends(more_events, AS_OF)
    assert ci.seasonality(events, AS_OF) == ci.seasonality(more_events, AS_OF)
```

- [ ] **Step 2: Run the club-insights tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_club_insights.py -v`
Expected: collection ERROR — `ImportError: cannot import name 'club_insights' from 'sunday_clays.analytics'`.

- [ ] **Step 3: Implement `analytics/club_insights.py`**

Create `backend/src/sunday_clays/analytics/club_insights.py`:

```python
"""Club insights (Plan 06 T9): regulars/lapsed, guest conversion, parity, trends."""

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

REGULAR_WINDOW = timedelta(days=364)
REGULAR_SHARE = 0.5
LAPSED_LOOKBACK = timedelta(days=180)
LAPSED_QUIET = timedelta(days=90)
ROLLING_EVENTS = 8


@dataclass(frozen=True)
class CoreShooter:
    shooter_id: int
    display_name: str
    events_attended: int
    share: float


@dataclass(frozen=True)
class LapsedShooter:
    shooter_id: int
    display_name: str
    last_event: date


@dataclass(frozen=True)
class Regulars:
    as_of: date
    n_held_window: int
    core: tuple[CoreShooter, ...]
    lapsed: tuple[LapsedShooter, ...]


@dataclass(frozen=True)
class ConversionYear:
    year: int
    new_guests: int
    converted: int
    median_days_to_convert: float | None


@dataclass(frozen=True)
class ParityYear:
    year: int
    n_events: int
    distinct_winners: int
    top3_share: float | None
    favorite_win_rate: float | None


@dataclass(frozen=True)
class YearTrend:
    year: int
    events_held: int
    mean_head_count: float | None
    unique_shooters: int
    ytd_events: int
    ytd_rounds: int
    ytd_unique_shooters: int
    ytd_events_yoy: float | None  # fractional change vs the previous year's same window


@dataclass(frozen=True)
class EventTrend:
    event_date: date
    top_score: int
    median: float
    difficulty: float | None
    top_score_rolling8: float
    median_rolling8: float
    difficulty_rolling8: float | None


@dataclass(frozen=True)
class MonthTrend:
    month: int
    n_events: int
    mean_head_count: float | None
    mean_median: float | None


def _held_events(events: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Held (`results_complete`, C4) events dated on or before as_of."""
    return events.loc[events["results_complete"] & (events["event_date"] <= as_of)]


def _names(rounds: pd.DataFrame) -> dict[int, str]:
    return {
        int(s): str(n)
        for s, n in zip(rounds["shooter_id"], rounds["display_name"], strict=True)
    }


def _core_counts(
    rounds: pd.DataFrame, events: pd.DataFrame, as_of: date
) -> tuple[int, dict[int, int]]:
    held_dates = _held_events(events, as_of)["event_date"]
    window = [d for d in held_dates if d > as_of - REGULAR_WINDOW]
    held = set(window)
    counts: dict[int, int] = defaultdict(int)
    for shooter_id, event_date in set(
        zip(rounds["shooter_id"], rounds["event_date"], strict=True)
    ):
        if event_date in held:
            counts[int(shooter_id)] += 1
    core = {
        s: n for s, n in counts.items() if window and n >= REGULAR_SHARE * len(window)
    }
    return len(window), core


def regulars(rounds: pd.DataFrame, events: pd.DataFrame, as_of: date) -> Regulars:
    """Core and lapsed regulars as of `as_of`.

    Core = attended >= 50% of held events in (as_of - 364d, as_of]; lapsed = core at
    as_of - 180d with no round in (as_of - 90d, as_of]. Deceased (current status)
    shooters are excluded from both.
    """
    upto = rounds.loc[rounds["event_date"] <= as_of]
    deceased = {
        int(s) for s in upto.loc[upto["shooter_status"] == "deceased", "shooter_id"]
    }
    names = _names(upto)
    n_window, core = _core_counts(upto, events, as_of)
    _, earlier_core = _core_counts(upto, events, as_of - LAPSED_LOOKBACK)
    last_seen: dict[int, date] = {}
    for shooter_id, event_date in zip(
        upto["shooter_id"], upto["event_date"], strict=True
    ):
        sid = int(shooter_id)
        last_seen[sid] = max(event_date, last_seen.get(sid, event_date))
    core_rows = sorted(
        (
            CoreShooter(s, names[s], n, n / n_window)
            for s, n in core.items()
            if s not in deceased
        ),
        key=lambda c: (-c.events_attended, c.display_name),
    )
    lapsed_rows = sorted(
        (
            LapsedShooter(s, names[s], last_seen[s])
            for s in earlier_core
            if s not in deceased and last_seen[s] <= as_of - LAPSED_QUIET
        ),
        key=lambda x: (x.last_event, x.display_name),
    )
    return Regulars(as_of, n_window, tuple(core_rows), tuple(lapsed_rows))


def guest_conversion(rounds: pd.DataFrame) -> list[ConversionYear]:
    """Per year: new guests (year of the first guest round) and conversions.

    A conversion is the first member round dated after the first guest round, counted in
    that member round's year. Uses the per-row `status` (C7).
    """
    first_guest: dict[int, date] = {}
    member_dates: dict[int, list[date]] = defaultdict(list)
    for shooter_id, event_date, status in zip(
        rounds["shooter_id"], rounds["event_date"], rounds["status"], strict=True
    ):
        sid = int(shooter_id)
        if status == "guest" and (
            sid not in first_guest or event_date < first_guest[sid]
        ):
            first_guest[sid] = event_date
        elif status == "member":
            member_dates[sid].append(event_date)
    new_guests: dict[int, int] = defaultdict(int)
    days: dict[int, list[int]] = defaultdict(list)
    for sid, guest_date in first_guest.items():
        new_guests[guest_date.year] += 1
        later = [d for d in member_dates[sid] if d > guest_date]
        if later:
            joined = min(later)
            days[joined.year].append((joined - guest_date).days)
    return [
        ConversionYear(
            year=year,
            new_guests=new_guests.get(year, 0),
            converted=len(days.get(year, [])),
            median_days_to_convert=float(statistics.median(days[year]))
            if days.get(year)
            else None,
        )
        for year in sorted(set(new_guests) | set(days))
    ]


def parity(rounds: pd.DataFrame) -> list[ParityYear]:
    """Per year: distinct winners, top-3 winners' share of wins, favorite win rate.

    A tie for first gives each tied shooter a win. The favorite is the attendee with the
    highest mu_before; events without any mu_before are left out of that rate.
    """
    best = rounds.loc[rounds["is_best_round"]]
    out = []
    years = [d.year for d in best["event_date"]]
    for year, group in best.assign(year=years).groupby("year", sort=True):
        winners = group.loc[group["event_rank"] == 1]
        if winners.empty:
            continue
        wins = winners["shooter_id"].value_counts()
        top3 = sorted(wins.tolist(), reverse=True)[:3]
        rated = favorite_won = 0
        for _, day in group.groupby("event_date"):
            if day["mu_before"].notna().any():
                rated += 1
                favorites = day.loc[day["mu_before"] == day["mu_before"].max()]
                favorite_won += int((favorites["event_rank"] == 1).any())
        out.append(
            ParityYear(
                year=int(str(year)),
                n_events=int(winners["event_date"].nunique()),
                distinct_winners=len(wins),
                top3_share=sum(top3) / int(wins.sum()),
                favorite_win_rate=None if rated == 0 else favorite_won / rated,
            )
        )
    return out


def _ytd_cutoff(year: int, as_of: date) -> date:
    """as_of's month/day in `year` (Feb 29 clamps to Feb 28)."""
    return date(
        year, as_of.month, 28 if (as_of.month, as_of.day) == (2, 29) else as_of.day
    )


def yearly_trends(
    rounds: pd.DataFrame, events: pd.DataFrame, as_of: date
) -> list[YearTrend]:
    """Per calendar year up to as_of; the YTD window ends on as_of's month/day."""
    held = list(_held_events(events, as_of)["event_date"])
    upto = rounds.loc[rounds["event_date"] <= as_of]
    heads = events.loc[events["event_date"] <= as_of]
    years = sorted(
        {d.year for d in heads["event_date"]} | {d.year for d in upto["event_date"]}
    )
    out: list[YearTrend] = []
    previous_ytd: int | None = None
    for year in years:
        cutoff = _ytd_cutoff(year, as_of)
        in_year = upto.loc[[d.year == year for d in upto["event_date"]]]
        ytd = in_year.loc[in_year["event_date"] <= cutoff]
        head_counts = heads.loc[
            [d.year == year for d in heads["event_date"]], "head_count"
        ].dropna()
        ytd_events = sum(1 for d in held if d.year == year and d <= cutoff)
        out.append(
            YearTrend(
                year=year,
                events_held=sum(1 for d in held if d.year == year),
                mean_head_count=None
                if head_counts.empty
                else float(head_counts.mean()),
                unique_shooters=int(in_year["shooter_id"].nunique()),
                ytd_events=ytd_events,
                ytd_rounds=len(ytd),
                ytd_unique_shooters=int(ytd["shooter_id"].nunique()),
                ytd_events_yoy=None
                if not previous_ytd
                else (ytd_events - previous_ytd) / previous_ytd,
            )
        )
        previous_ytd = ytd_events
    return out


def event_trends(events: pd.DataFrame, as_of: date) -> list[EventTrend]:
    """Held events up to as_of: top score, median, difficulty and rolling-8 means."""
    held = _held_events(events, as_of).sort_values("event_date")
    rolling = (
        held[["top_score", "median", "difficulty"]]
        .rolling(ROLLING_EVENTS, min_periods=1)
        .mean()
    )
    out = []
    for (_, e), (_, r) in zip(held.iterrows(), rolling.iterrows(), strict=True):
        out.append(
            EventTrend(
                event_date=e["event_date"],
                top_score=int(e["top_score"]),
                median=float(e["median"]),
                difficulty=None if pd.isna(e["difficulty"]) else float(e["difficulty"]),
                top_score_rolling8=float(r["top_score"]),
                median_rolling8=float(r["median"]),
                difficulty_rolling8=None
                if pd.isna(r["difficulty"])
                else float(r["difficulty"]),
            )
        )
    return out


def seasonality(events: pd.DataFrame, as_of: date) -> list[MonthTrend]:
    """Month-of-year profile over held events up to as_of."""
    held = _held_events(events, as_of)
    out = []
    for month in range(1, 13):
        in_month = held.loc[[d.month == month for d in held["event_date"]]]
        heads = in_month["head_count"].dropna()
        medians = in_month["median"].dropna()
        out.append(
            MonthTrend(
                month=month,
                n_events=len(in_month),
                mean_head_count=None if heads.empty else float(heads.mean()),
                mean_median=None if medians.empty else float(medians.mean()),
            )
        )
    return out
```

- [ ] **Step 4: Run the club-insights tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/analytics_core/test_club_insights.py -v`
Expected: PASS — 10 passed.

- [ ] **Step 5: Write the failing club-insights route tests**

Create `backend/tests/integration/analytics_core/test_club_insights_routes.py`. The fixture case uses numbers computed independently from `scores_2026-09-27.xlsx` (held = the 310 score dates other than 2024-11-10): as of 2026-09-27 the trailing 364 days hold 48 held events and 18 living shooters attended at least 24 of them; the only lapsed regular is "Nesbitt, Rolf"; 114 shooters have a guest round, and their first member round after it falls once in 2022, twice in 2025 and four times in 2026.

```python
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.routes import _filters

TODAY = date(2026, 9, 27)


@pytest.fixture(autouse=True)
def _fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_filters, "today_local", lambda tz: TODAY)


def test_regulars_route_defaults_to_today(seed: Any, viewer_client: TestClient) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    for k in range(4):
        d = TODAY - timedelta(days=7 * k)
        seed.round(d, ann, 30)
        if k == 0:
            seed.round(d, bob, 30)
    seed.finish()

    today = viewer_client.get("/api/club/regulars").json()
    past = viewer_client.get(
        "/api/club/regulars", params={"as_of": "2026-09-13"}
    ).json()

    assert (today["as_of"], today["n_held_window"]) == ("2026-09-27", 4)
    assert [c["display_name"] for c in today["core"]] == ["Oakley, Ann"]
    assert (past["n_held_window"], [c["events_attended"] for c in past["core"]]) == (
        2,
        [2],
    )


def test_conversion_parity_and_trends_routes(
    seed: Any, viewer_client: TestClient
) -> None:
    ann, bob = seed.shooter("Oakley, Ann"), seed.shooter("Pratt, Bob")
    seed.round(date(2026, 8, 30), ann, 40, status="guest")
    seed.round(date(2026, 8, 30), bob, 30)
    seed.round(date(2026, 9, 6), ann, 35, status="member")
    seed.round(date(2026, 9, 6), bob, 36)
    seed.finish()
    seed.analyze()

    conversion = viewer_client.get("/api/club/conversion").json()
    parity = viewer_client.get("/api/club/parity", params={"by": "year"}).json()
    trends = viewer_client.get("/api/club/trends").json()

    assert conversion == [
        {"year": 2026, "new_guests": 1, "converted": 1, "median_days_to_convert": 7.0}
    ]
    assert (
        parity[0]["year"],
        parity[0]["n_events"],
        parity[0]["distinct_winners"],
    ) == (2026, 2, 2)
    assert trends["as_of"] == "2026-09-27"
    assert [(y["year"], y["events_held"]) for y in trends["years"]] == [(2026, 2)]
    assert [e["event_date"] for e in trends["events"]] == ["2026-08-30", "2026-09-06"]
    assert len(trends["months"]) == 12
    assert (
        viewer_client.get("/api/club/parity", params={"by": "month"}).status_code == 422
    )


def test_club_insights_on_committed_fixtures(fx_viewer_client: TestClient) -> None:
    regulars = fx_viewer_client.get("/api/club/regulars").json()
    assert (regulars["n_held_window"], len(regulars["core"])) == (48, 18)
    assert [x["display_name"] for x in regulars["lapsed"]] == ["Nesbitt, Rolf"]
    conversion = {
        c["year"]: c for c in fx_viewer_client.get("/api/club/conversion").json()
    }
    assert sum(c["new_guests"] for c in conversion.values()) == 114
    assert {y: c["converted"] for y, c in conversion.items() if c["converted"]} == {
        2022: 1,
        2025: 2,
        2026: 4,
    }
    trends = fx_viewer_client.get("/api/club/trends").json()
    assert sum(y["events_held"] for y in trends["years"]) == 310
    assert len(trends["events"]) == 310
```

- [ ] **Step 6: Run the club-insights route tests to verify they fail**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_club_insights_routes.py -v`
Expected: FAIL (3 failed) — `/api/club/regulars|conversion|parity|trends` are not routed yet, so requests return 404 `{"detail": "Not Found"}` (`KeyError: 'as_of'`, `assert {'detail': 'Not Found'} == [...]`, `KeyError: 'n_held_window'`).

- [ ] **Step 7: Implement `api/routes/club_insights.py`**

Create `backend/src/sunday_clays/api/routes/club_insights.py`:

```python
"""Club regulars, guest conversion, parity and trends (Plan 06 T9)."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sunday_clays.analytics import club_insights, frames
from sunday_clays.api.routes._filters import resolve_as_of
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session

router = APIRouter()


class CoreShooterOut(BaseModel):
    shooter_id: int
    display_name: str
    events_attended: int
    share: float


class LapsedShooterOut(BaseModel):
    shooter_id: int
    display_name: str
    last_event: date


class RegularsOut(BaseModel):
    as_of: date
    n_held_window: int
    core: list[CoreShooterOut]
    lapsed: list[LapsedShooterOut]


class ConversionYearOut(BaseModel):
    year: int
    new_guests: int
    converted: int
    median_days_to_convert: float | None


class ParityYearOut(BaseModel):
    year: int
    n_events: int
    distinct_winners: int
    top3_share: float | None
    favorite_win_rate: float | None


class YearTrendOut(BaseModel):
    year: int
    events_held: int
    mean_head_count: float | None
    unique_shooters: int
    ytd_events: int
    ytd_rounds: int
    ytd_unique_shooters: int
    ytd_events_yoy: float | None


class EventTrendOut(BaseModel):
    event_date: date
    top_score: int
    median: float
    difficulty: float | None
    top_score_rolling8: float
    median_rolling8: float
    difficulty_rolling8: float | None


class MonthTrendOut(BaseModel):
    month: int
    n_events: int
    mean_head_count: float | None
    mean_median: float | None


class ClubTrendsOut(BaseModel):
    as_of: date
    years: list[YearTrendOut]
    events: list[EventTrendOut]
    months: list[MonthTrendOut]


@router.get("/api/club/regulars")
def get_regulars(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: date | None = None,
) -> RegularsOut:
    result = club_insights.regulars(
        frames.load_rounds(session),
        frames.load_events(session),
        resolve_as_of(as_of, settings.timezone),
    )
    return RegularsOut.model_validate(asdict(result))


@router.get("/api/club/conversion")
def get_conversion(
    session: Annotated[Session, Depends(get_session, scope="function")],
) -> list[ConversionYearOut]:
    return [
        ConversionYearOut.model_validate(asdict(row))
        for row in club_insights.guest_conversion(frames.load_rounds(session))
    ]


@router.get("/api/club/parity")
def get_parity(
    session: Annotated[Session, Depends(get_session, scope="function")], by: Literal["year"] = "year"
) -> list[ParityYearOut]:
    return [
        ParityYearOut.model_validate(asdict(row))
        for row in club_insights.parity(frames.load_rounds(session))
    ]


@router.get("/api/club/trends")
def get_trends(
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClubTrendsOut:
    as_of = resolve_as_of(None, settings.timezone)
    rounds, events = frames.load_rounds(session), frames.load_events(session)
    return ClubTrendsOut(
        as_of=as_of,
        years=[
            YearTrendOut.model_validate(asdict(y))
            for y in club_insights.yearly_trends(rounds, events, as_of)
        ],
        events=[
            EventTrendOut.model_validate(asdict(e))
            for e in club_insights.event_trends(events, as_of)
        ],
        months=[
            MonthTrendOut.model_validate(asdict(m))
            for m in club_insights.seasonality(events, as_of)
        ],
    )
```

- [ ] **Step 8: Run the club-insights route tests to verify they pass**

Run: `cd backend && uv run pytest tests/integration/analytics_core/test_club_insights_routes.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 9: Full verification for the backend half**

Run:
```bash
cd backend && uv run ruff format . && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch --cov-report=term-missing
```
Expected: no lint/type issues; all tests pass (Plan 04's route auth matrix now also covers the four new `/api/club/…` routes → 401 without a cookie); coverage ≥ 90% lines and branches, with `analytics/club_insights.py` and `api/routes/club_insights.py` at 100%. Once Tasks 5–9 have all merged, `main` runs the whole Plan 06 suite together: 211 tests in `tests/unit/analytics_core`, `tests/integration/analytics_core`, `tests/unit/api/test_etag_helpers.py` and `tests/unit/api/test_route_convert.py`.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/analytics/club_insights.py \
  backend/src/sunday_clays/api/routes/club_insights.py \
  backend/tests/unit/analytics_core/test_club_insights.py \
  backend/tests/integration/analytics_core/test_club_insights_routes.py
git commit -m "feat(api): club regulars, guest conversion, parity and trends

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
