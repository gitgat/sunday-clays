# Admin Analytics Implementation Plan (Sub-plan 16)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers, including fix rounds, run on Sonnet. Every reviewer, re-reviewer and verifier runs on Opus. Each task gets one branch, one worktree and one PR **into `feat/insight-bumps`**, never `main`. Implementers commit but never push or open PRs. The controller pushes, opens the PRs and merges them, in the waves below.

**Goal:** Count anonymous page views from the SPA (a coarse page kind, the "Which one are you?" state and the random device id from Plan 15, nothing else), keep them for about 90 days, then roll them into daily and weekly totals that are kept forever. Add an admin-only **Analytics** page that shows four ChartFrame charts: visitors, page views by page kind, fist bumps, and "Which one are you?" uptake.

**Architecture:** Migration `0007_page_views` adds four durable tables. `page_views` holds raw visits (`device_id`, `page_kind`, `me_state`, `at`). `page_view_attempts` is the per-IP rate-limit log: rows older than 10 minutes are pruned on the next beacon, and the daily rollup job prunes any left over. `page_view_rollups(period, start_day, devices, me_picked, me_skipped, me_none)` holds unique-device totals per local day and per local ISO week. `page_kind_rollups(day, page_kind, views)` holds views per day and kind. `domain/page_views.py` records a view (deduped per device and kind for 30 minutes under an advisory lock) and rolls up raw rows older than the Monday on or before today minus 90 days, in whole weeks. A new discovered viewer router, `api/routes/pageviews.py`, serves `POST /api/pageviews`. It answers 204 and drops the view for an admin session. A daily `page_view_rollup` job is scheduled by `jobs/scheduler.py` and handled by `jobs/page_view_rollup.py`. `domain/site_analytics.py` and the admin router `api/routes/admin_analytics.py` serve four read-only `GET /api/admin/analytics/*` endpoints, which merge rollups with raw rows. On the frontend, `features/pageviews/` maps a pathname to a page kind and sends one fire-and-forget `fetch(…, {keepalive: true})` per pathname change from `SessionShell`. `features/admin-analytics/` adds the `/admin/analytics` page, which has four ChartFrame cards with explainers.

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2.1 · Alembic · Pydantic v2 · pytest · Postgres 17 (psycopg 3) · React 19 · TypeScript (strict) · TanStack Query v5 · React Router v7 · ECharts via `ChartFrame` · Tailwind v4 · openapi-fetch · Vitest + Testing Library + MSW · Playwright.

**Spec:** The approved design (owner, 2026-10-01) is quoted below and is binding. The format, global constraints and lessons come from `docs/superpowers/plans/2026-10-01-15-insight-bumps.md` on `origin/feat/insight-bumps`.

**Base:** `feat/insight-bumps` @ `d937d8f` **plus the pending Plan 15 fix wave (`fix/15-final`)**. That wave touches `api/routes/bumps.py`, `auth/ratelimit.py` (`BUMP_LIMIT = 600`), `features/bumps/*`, `features/home/components/WhichOneAreYou*`, `predictions/components/NextSundayCard*`, `lib/me.ts` and `e2e/insight-bumps.spec.ts`. The controller merges `fix/15-final` into `feat/insight-bumps` before Wave 1. This plan's replace blocks avoid every hunk of that wave: `auth/ratelimit.py` is anchored on `record_bump_action`, which the fix leaves alone, and `lib/me.ts` is only imported. **Pre-flight** (controller, before each wave): every Create target must not exist, every Modify target must exist, and every "replace" block must occur exactly once in the task's base.

**Delivery:** Task branches are `task/16-<N>-<slug>`, cut from `feat/insight-bumps` after the previous wave has merged. Every PR targets `feat/insight-bumps`, and CI (`ci-ok`, which includes the full Playwright suite) must pass. Commits use the gitgat identity, which is already in the repo config. Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. An implementer on another model names its own model there instead. This feature ships to `main` together with Plan 15, in the one PR the owner approves after a local preview.

## Approved design (owner, 2026-10-01)

> Build on integration branch feat/insight-bumps (origin/feat/insight-bumps, d937d8f plus a pending fix wave on fix/15-final that touches bumps, ratelimit, NextSundayCard and e2e/insight-bumps.spec.ts). It ships with Plan 15 fist bumps and reuses its anonymous device id (lib/device.ts, localStorage "sc.device").
>
> **Data collection:** On each client-side route change the SPA sends a small page-view beacon: {device_id, page_kind, me_state, at}. page_kind is a coarse category taken from the route pattern (home, profile, event, leaderboards, records, club, stations, weather, yir, explorer, achievements, race, compare, events-list, admin, other). It is never the full URL or a shooter id. me_state is one of picked | skipped | none (the "Which one are you?" state). It never says which name.
>
> **Exclusions:** Not counted for admin sessions: the server checks the session role and drops the beacon (204). Not counted when storage is blocked (no device id). Throttled: the same device + page_kind within 30 minutes counts once (dedupe server-side).
>
> **Privacy:** No names, no IP addresses, nothing else that identifies a person is stored for analytics. The IP may still be used transiently for an abuse rate limit, as bumps already do. Viewer login required. Must not break the CSP (same-origin fetch). Use navigator.sendBeacon or fetch keepalive. Must never block or slow navigation, and failures are silent.
>
> **Retention:** a scheduled worker job (the existing jobs/scheduler pattern) rolls raw page_views older than 90 days into daily aggregate rows, kept forever, then deletes the raw rows. The aggregates must keep unique-device counts per day/week correct, so aggregate per day before deleting.
>
> **Admin page "Analytics"** (new admin feature folder, nav adminOnly, next to Ops), with a time-range control: (1) Visitors: unique devices per day and per week as a chart, plus the busiest days. (2) Page views by page kind. (3) Fist bumps: per day, most-bumped insights (headline + count), and the number of devices that have bumped at least once. Source: the existing fist_bumps table. (4) "Which one are you?" uptake: devices whose latest me_state is picked / skipped / none. Every chart uses ChartFrame (Table/CSV/fullscreen) with an ELI5 explainer, following the repo's chart conventions (explainers, time-window conventions). Admin API under /api/admin/analytics/*, admin-only, no-store.
>
> **Owner rules:** copy never uses he/she/his/her; invented names only in tests; every chart keeps Table/CSV/fullscreen/ELI5 explainer; admin mutations are audited (this page is read-only); migrations are expand-only and safe while the previous release runs; strict TDD (failing test, run, FAIL, implement, PASS), with mutation-proof tests; coverage ≥90% lines and branches; e2e at both viewports (390x844 and 1440x900).

## Global Constraints

**Owner rules (binding):**

- App copy never uses he/she/his/her. Copy says "Sunday", never "event", and never uses "class". The internal kind names `event` and `events-list` never appear in copy. The page shows them as "One Sunday" and "Sundays list".
- Real people's names never appear in the repo. Tests and docs use invented names: `Ike Hadley` / `Hadley, Ike` (shooter 3), `Amy Ace`, `Bob Bee`, `Cal Cy`, `Pat Kim`.
- Every chart keeps Table, CSV, fullscreen and an ELI5 explainer (What this shows / How to read it / How it's worked out). Fullscreen and the CSV cover all the data on record, not just the window (memory: charts-fullscreen-all-data).
- Admin mutations are audited. This page is read-only, so it writes no audit row. `POST /api/pageviews` is a viewer beacon, not an admin mutation.
- Nothing identifies a person: no name, no IP and no URL is stored with a view. The IP lives only in `page_view_attempts`. Rows older than 10 minutes are pruned on the next beacon, as `bump_attempts` is, and the daily `page_view_rollup` job also deletes every row older than 10 minutes. So after the last beacon of a quiet spell, an IP stays for about a day at most, never indefinitely. Copy and comments never claim "10 minutes at most".

**Repo conventions (unchanged from Plan 15):**

- Python `3.13`, Node `22` LTS and Postgres `17`, with `uv` (backend) and `pnpm` (frontend). This plan adds no package. Never edit `[project].dependencies`, `[dependency-groups]`, `uv.lock`, `dependencies`, `devDependencies` or `pnpm-lock.yaml`.
- Coverage floor is **90% lines AND 90% branches**, with backend and frontend measured separately. `ratchets/` is controller-only.
- Backend gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src`. pytest runs with `filterwarnings = error`, so no SQLAlchemy deprecation may fire. In particular, **never use `Select.distinct(*cols)` (DISTINCT ON), which is deprecated in SQLAlchemy 2.1.** Use `row_number() OVER (…)`. Frontend gates: `pnpm lint` (`eslint --max-warnings 0`), `pnpm typecheck` (which first regenerates the gitignored `src/api/schema.d.ts` with `pnpm gen:api`) and `pnpm exec prettier --check .`.
- **Strict TDD with evidence:** every production change starts from a failing test. Each implementer report pastes the RED output (the failing run) and then the GREEN output (the passing run) for every step pair. Reviewers re-run the task's new tests on the task's base to prove they fail there. Tests are mutation-proof: each names the mutation it kills where that is not obvious (for example, inserting rows out of time order so that "last by id" cannot pass for "last by time").
- Migrations are expand-only and compatible with the previous release (`api` runs `alembic upgrade head` on start). This plan's one migration is `0007_page_views` (`down_revision = "0006"`). Its four tables are durable: `domain/rebuild.py` `LIVE_TABLES` never lists them.
- Routers are discovered (C2). A module `api/routes/<name>.py` needs a viewer, and `admin_<name>.py` needs an admin. Never edit `api/app.py`. `/api/admin/*` is already `no-store` and never ETagged (`api/etag.py`). `frontend/src/app/router.tsx` is closed to edits (C10). Every `features/<name>/mocks.ts` `handlers` export is merged into the shared MSW server, which errors on unhandled requests.
- Viewports: phone `390×844` and desktop `1440×900` are both first-class. Tap targets are at least 44 px, no page scrolls sideways, and the e2e runs at both sizes.
- The theme is dark only and uses the existing Tailwind tokens. Never hard-code a colour.
- Stage files explicitly (`git add <paths>`). Never `git add -A`: the repo root can hold untracked workbooks.
- Every PR runs the full Playwright suite under the required `ci-ok`. A task that changes visible copy updates the e2e that asserts it, in the same task (PF-1).
- Workflows stay at about 10 agents or fewer. Non-conflicting lanes run in parallel (the waves below).
- Actions budget: Pro included minutes plus the $75 Actions budget. If CI is blocked by billing, stop and tell the owner.

## Review Focus

Six conditions that the design implies but does not spell out, and that are most likely to bite. Each is pinned to tests in the task that owns the code.

1. **A week's unique devices is not the sum of its days, including across the rollup line.** Expected: the rollup writes a separate `week` row from the raw rows. It rolls only whole weeks (the cutoff is a Monday), so no week is split between rollup and raw. A device seen on Tuesday and Thursday counts 2 day-devices but 1 week-device. Tests: T1 `test_rollup_counts_old_visits_by_local_day_and_week` (week Jun 22 = 3 devices, not 4). T2 `test_visitors_merge_rollups_and_raw_and_zero_fill`.
2. **Local day, not UTC day.** A visit at 23:30 on a Sunday (Pacific) is Monday in UTC. Expected: it belongs to Sunday's day and to the week ending that Sunday, in rollups and in raw reads. The rollup boundary is local midnight. Tests: T1 (device D at 2026-06-28 23:30 PT is rolled into week Jun 22, and 2026-06-29 00:30 PT stays raw). T2 (device C at 2026-09-20 23:30 PT is on Sep 20).
3. **Two identical beacons at once.** React StrictMode in dev, a double tap, or the same tab firing twice. Expected: one row. A transaction-scoped advisory lock serialises the dedupe check per device and kind. Test: T1 `test_two_identical_beacons_at_once_count_once`. It waits until the second session is actually blocked on the lock, so a version without the lock fails every time, not just sometimes.
4. **Who is never counted.** Admin sessions, browsers that block storage, and query-string-only changes (`?w=12m`, `?table`). Expected: the server answers 204 to an admin and writes neither a view nor an attempt row. The client sends nothing for an admin, nothing without a device id, and nothing when only the query string changes. Tests: T1 `test_an_admin_beacon_is_dropped_and_leaves_no_trace`. T3 `beacon.test.tsx` and `SessionShell.test.tsx`. T4 e2e "admin pages send no beacon…".
5. **GROUP BY a bound parameter under psycopg 3.** psycopg binds parameters on the server, so `GROUP BY CAST(timezone($1, at) AS DATE)` does not match the select list's `CAST(timezone($2, at) AS DATE)`, and Postgres rejects the query. Expected: every grouped bucket is computed once in a subquery, and the outer query groups by that subquery's column. Tests: every T1/T2 rollup and aggregate test runs the real SQL against Postgres.
6. **"Latest" means latest by time, not by id.** Expected: a device's state in a bucket is from its row with the greatest `at`, then the greatest `id`. Tests: T1 and T2 insert the later visit first, so ordering by id or by insertion picks the wrong state and fails.

## Decisions

1. **Four tasks, split frontend-first by dependency.** T3 as listed in the request (beacon plus page) cannot run beside T2, because the page needs T2's generated OpenAPI types. So **T3 is the beacon alone** (frontend, disjoint from T2's backend files) and runs in Wave 2 beside T2. **T4 is the Analytics page plus the e2e at both viewports**: one spec that covers the beacon end to end and the page. That keeps four tasks and three waves.
2. **Migration `0007_page_views`, four tables, all durable.** `page_views(id bigserial, device_id uuid, page_kind text, me_state text CHECK IN ('picked','skipped','none'), at timestamptz default now())` has indexes `(device_id, page_kind, at)` for the dedupe and `(at)` for the rollup and reads. `page_view_attempts(id, ip, at)` has an index `(ip, at)`. `page_view_rollups(period text CHECK IN ('day','week'), start_day date, devices int, me_picked int, me_skipped int, me_none int)` has PK `(period, start_day)`. `page_kind_rollups(day date, page_kind text, views int)` has PK `(day, page_kind)`. The previous release never reads them, so this is expand-only.
3. **`page_kind` has no DB CHECK.** The API validates it with a `Literal` (`PageKind`), so adding a kind later is code only, with no migration. `me_state` and `period` are closed sets and get CHECKs. The admin API reads `page_kind` as `str`, so an old kind in a rollup never breaks a response.
4. **The server's clock stamps every view.** The beacon carries `at` (the design's field, an ISO string from the browser). The API accepts it and never stores it: a phone with a wrong clock would put a visit on the wrong day and defeat the 30-minute dedupe.
5. **Dedupe rule.** The same device and kind within the last 30 minutes (`at > now − 30 min`, strictly) is not stored again, whatever its `me_state`. So a new "Which one are you?" answer shows at that device's next counted view. The check runs under `pg_advisory_xact_lock(7263004, hashtext(device || ':' || kind))`. The rebuild uses class key `7263003`, and `7263004` is new.
6. **Admin drop order.** `POST /api/pageviews` checks the session role first. For an admin it returns 204 before the rate limit, before validating the device id, and before any write. So an admin leaves neither a view nor an IP row. The client also sends nothing for an admin session, to save the request. The server check is the rule, and the client check is only an optimisation.
7. **Rate limit (ported from bumps).** `settings.page_view_limit` (default 600, env `PAGE_VIEW_LIMIT`) beacons per client IP per 10 minutes, in `page_view_attempts`, through the shared `_count_since` and `_insert_and_prune` helpers. The default matches the shared club Wi-Fi reasoning of `BUMP_LIMIT` in the fix wave. It is a setting, not a constant, because the whole e2e suite comes from one IP: about 190 `page.goto` calls times 2 projects, plus in-app navigation, each sending a beacon. `compose.test.yaml` raises it to 100000 for the e2e stack, as it already raises `LOGIN_MAX_FAILURES`, so a full run never sees a 429 and the T4 viewer test (which asserts 204) stays deterministic. Backend tests cover the limiter itself, at the default and at an overridden value. `_insert_and_prune` only prunes when a beacon arrives, so the daily `page_view_rollup` job also calls `prune_page_view_attempts` (see Global Constraints). Over the limit is 429 `rate_limited`. The attempt is recorded and committed before the device id is validated, so a refused 400 still counts. A 422 (an unknown kind or state) is refused by Pydantic before the handler runs and does not count. The beacon is fire-and-forget, so the client ignores 429.
8. **Buckets are the club's local day and the local ISO week (Monday to Sunday),** in `settings.timezone`. A week therefore ends on its Sunday. The week is labelled by its Monday ("Week of").
9. **Retention in whole weeks.** `rollup_cutoff(today)` is the Monday on or before `today − 90 days`, so raw rows are kept for 90 to 96 days. The rollup writes `day` and `week` rows (devices, plus each device's latest state in that bucket) and `page_kind_rollups` rows. It then deletes the raw rows before local midnight of the cutoff, all in the job's transaction. `ON CONFLICT DO NOTHING` makes a repeat harmless. The server stamps `at`, so no raw row can later appear on a rolled day. The job `page_view_rollup` is due once per local day after 03:00 (`ROLLUP_LOCAL_HOUR = 3`). It does not depend on `weather_enabled`, so `schedule_due` checks it before the weather early return. It uses `dedupe_key="page_view_rollup"`. A previous-release worker would fail this job as `no_handler`, but only the new worker schedules it, and the stack runs a single worker.
10. **Reads aggregate in Python over small sets.** There are at most one rollup row per day and week, raw rows cover at most 96 days, and `fist_bumps` has one row per insight and device. Each endpoint therefore reads the rollups and the per-bucket raw counts once and filters by the span in Python. That keeps the SQL simple and the window logic in one testable place (`Span.has`).
11. **API shape.** `GET /api/admin/analytics/{visitors,pages,bumps,me-states}?since=&as_of=`. The names follow the other routes (`check_window`, 400 `invalid_range`). `as_of` defaults to today in the club's timezone. When `since` is missing, a series starts at the first data on or before `as_of`. Day and week series are zero-filled, so a quiet day shows as 0, not as a gap. `busiest` is the top 5 days with any devices, by devices and then the later day. `top` is the 10 most-bumped insights, by bumps and then key, with `headline` as plain text (`templates.plain`) or `null` when the insight is gone.
12. **Bumps in a window** are the bumps that still stand (a taken-back bump is deleted), by the local day they were given (`created_at`). `devices` is the distinct devices with a standing bump in the window. `devices_all_time` is the same over every standing bump.
13. **Uptake.** `weeks` gives each device's last answer per week (rollups plus raw). `latest` gives each device's last answer across the window, from raw rows only, because the rollups keep no per-device state. `latest_since` says where that detail starts: the later of `since` and the first raw day, or `null` when nothing raw is in range. The page says "since <date>" so a 12-month window never overstates.
14. **The page's window follows the header `w` but is anchored at today.** `windowRange(w, today)`: visits happen every day, while the global window is anchored at the last scored Sunday. The default is 8W (memory: date-filter-model). The dates show once, under the `h1`. The cards carry no `scope: 'windowed'` tag, because `ScopeTag` would print the scored-Sunday dates. Fullscreen and CSV fetch the same endpoint without `since` (all time) through `fullQuery`.
15. **`fetch(…, { keepalive: true })`, not `navigator.sendBeacon`, and not the openapi client.** `fetch` lets us send `Content-Type: application/json` and `credentials: 'same-origin'`. It is same-origin, so CSP `connect-src 'self'` holds, and MSW intercepts it in tests. The openapi client's 401 middleware would redirect to `/login`, which breaks "failures are silent". The call is `void`, wrapped in `try/catch` with `.catch(() => undefined)`, and runs in a `useEffect` after paint. It never blocks or slows navigation.
16. **Where the hook lives.** `SessionShell` (inside `RequireRole`, inside the router) calls `usePageViewBeacon(session?.role ?? null)`. It fires on `pathname` changes only. `router.tsx` is closed to edits (C10).
17. **The Shooters list is `other`.** The approved kinds have no list kind for `/shooters`, and the kinds are kept exactly as approved. `/shooters/:id` is `profile`, `/events` is `events-list`, `/events/:date` is `event`, every `/yir…` path is `yir` and every `/admin…` path is `admin`. A new kind later is a code-only change (Decision 3).
18. **Nav.** `{ label: 'Analytics', path: '/admin/analytics', icon: ChartColumn, order: 930, adminOnly: true }` sits after "Data & ops" (920). `navRegistry.test.ts` gains `'admin-analytics': 930`. The route handle is `{ roundType: false, window: true }`, so the header shows only the time-window control.

## File map

| File | Task | Responsibility |
|---|---|---|
| `backend/migrations/versions/0007_page_views.py` | 1 | Four durable tables |
| `backend/src/sunday_clays/models/page_views.py`, `models/__init__.py` | 1 | ORM models |
| `backend/src/sunday_clays/domain/page_views.py` | 1 | Kinds, record + dedupe, buckets, latest state, rollup |
| `backend/src/sunday_clays/auth/ratelimit.py` | 1 | Page-view limit (`page_view_limit` / IP / 10 min) and the daily prune |
| `backend/src/sunday_clays/config.py` | 1 | `page_view_limit: int = 600` |
| `compose.test.yaml` | 1 | `PAGE_VIEW_LIMIT: "100000"` for the one-IP e2e stack |
| `backend/tests/integration/jobs/test_worker_loop.py` | 1 | Keeps the loop tests off the clock (stubs `schedule_due`) |
| `backend/src/sunday_clays/api/routes/pageviews.py` | 1 | `POST /api/pageviews` |
| `backend/src/sunday_clays/jobs/page_view_rollup.py` | 1 | `page_view_rollup` handler (rollup, then the rate-limit prune) |
| `backend/src/sunday_clays/jobs/scheduler.py` | 1 | Daily rollup after 03:00 local |
| `backend/src/sunday_clays/domain/site_analytics.py` | 2 | Visitors, kinds, bumps, uptake |
| `backend/src/sunday_clays/api/routes/admin_analytics.py` | 2 | `GET /api/admin/analytics/*` |
| `frontend/src/features/pageviews/{pageKind.ts, beacon.ts, mocks.ts}` | 3 | Kind mapping, fire-and-forget beacon, hook |
| `frontend/src/features/auth/components/SessionShell.tsx` | 3 | Calls the hook |
| `frontend/src/features/admin-analytics/{routes.tsx, api.ts, mocks.ts, models.ts, explainers.ts}` | 4 | Route, queries, chart models, explainers |
| `frontend/src/features/admin-analytics/components/{VisitorsCard, PageKindsCard, BumpsCard, UptakeCard}.tsx` | 4 | The four ChartFrame cards |
| `frontend/src/features/admin-analytics/pages/AnalyticsPage.tsx` | 4 | The page |
| `frontend/src/app/navRegistry.test.ts` | 4 | Fixed order 930 |
| `frontend/e2e/admin-analytics.spec.ts` | 4 | End to end at both viewports |

## Waves

| Wave | Tasks (parallel) | Needs |
|---|---|---|
| 1 | Task 1 | The `fix/15-final` merge |
| 2 | Task 2 ∥ Task 3 | Task 1. T2 is backend only (`domain/site_analytics.py`, `api/routes/admin_analytics.py`, their tests). T3 is frontend only (`features/pageviews/*`, `features/auth/components/SessionShell*`) and needs T1's `PageViewIn` schema via `pnpm gen:api`. |
| 3 | Task 4 | Tasks 2 and 3 (T2's generated types; T3's beacon for the e2e) |

## Running the e2e stack (Tasks 3 and 4)

From the worktree root:

```bash
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh   # once per worktree
E2E_PORT=18080 IMAGE_TAG=task16 docker compose -p task16 -f compose.yaml -f compose.test.yaml build
E2E_PORT=18080 IMAGE_TAG=task16 docker compose -p task16 -f compose.yaml -f compose.test.yaml up -d --wait
cd frontend && pnpm exec playwright install chromium
E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test <specs>
```

Afterwards, run `docker compose -p task16 -f compose.yaml -f compose.test.yaml down -v`.

From Task 1 on, `compose.test.yaml` sets `PAGE_VIEW_LIMIT: "100000"` on `api` (Decision 7), so the beacons of a full run from one IP are never refused.

---

### Task 1: Page-view store, the beacon endpoint and the rollup job

**Files:**
- Create: `backend/migrations/versions/0007_page_views.py`
- Create: `backend/src/sunday_clays/models/page_views.py`
- Modify: `backend/src/sunday_clays/models/__init__.py`
- Create: `backend/src/sunday_clays/domain/page_views.py`
- Modify: `backend/src/sunday_clays/auth/ratelimit.py`
- Modify: `backend/src/sunday_clays/config.py`
- Modify: `compose.test.yaml`
- Create: `backend/src/sunday_clays/api/routes/pageviews.py`
- Create: `backend/src/sunday_clays/jobs/page_view_rollup.py`
- Modify: `backend/src/sunday_clays/jobs/scheduler.py`
- Modify: `backend/tests/integration/models/test_schema_0001.py`
- Create: `backend/tests/integration/domain/test_page_views_store.py`
- Create: `backend/tests/integration/domain/test_page_view_rollup.py`
- Create: `backend/tests/integration/auth/test_page_view_rate_limit.py`
- Create: `backend/tests/integration/api/test_pageviews_api.py`
- Modify: `backend/tests/integration/jobs/test_job_scheduler.py` (rewritten in full below)
- Create: `backend/tests/integration/jobs/test_page_view_rollup_job.py`
- Modify: `backend/tests/integration/jobs/test_worker_loop.py` (the `worker_settings` fixture)

**Interfaces:**
- Consumes: `auth.deps.client_ip`, `require_viewer`, `TooManyRequestsError`; `auth.ratelimit._count_since`, `_insert_and_prune`; `api.routes.bumps.parse_device_id(value: str) -> uuid.UUID` (400 `bad_device_id`); `db.SessionDep`; `jobs.handlers.handler`; `jobs.queue.enqueue`; `config.get_settings().timezone`; the fixtures `session`, `committed_engine`, `scratch_engine`, `auth_env`, `viewer_client`, `admin_client`.
- Produces (T2 and T3 rely on these):
  - `domain.page_views`: `PageKind` (Literal of the 16 approved kinds), `MeState` (`"picked" | "skipped" | "none"`), `Period` (`"day" | "week"`), `PAGE_KINDS`, `ME_STATES`, `PERIODS`, `DEDUPE_WINDOW = timedelta(minutes=30)`, `RAW_DAYS = 90`, `record_page_view(session, device_id: uuid.UUID, page_kind: str, me_state: str, now: datetime) -> bool`, `rollup_cutoff(today: date) -> date`, `local_midnight(day: date, tz: str) -> datetime`, `bucket_of(period: Period, tz: str) -> ColumnElement[date]`, `latest_states(tz: str, period: Period | None, *where) -> Subquery` (columns `bucket` when period is set, `device_id`, `me_state`), `state_counts(latest: Subquery) -> tuple[...]` (`count`, `picked`, `skipped`, `none`), `RollupReport(cutoff: date, rolled: int)`, `rollup_page_views(session, today: date, tz: str) -> RollupReport`.
  - `config.Settings.page_view_limit: int = 600` (env `PAGE_VIEW_LIMIT`).
  - `auth.ratelimit`: `PAGE_VIEW_WINDOW = timedelta(minutes=10)`, `page_views_limited(session, ip) -> bool` (reads `get_settings().page_view_limit`), `record_page_view_attempt(session, ip) -> None`, `prune_page_view_attempts(session) -> None`.
  - `POST /api/pageviews` with body `PageViewIn = {device_id: str, page_kind: PageKind, me_state: MeState, at?: datetime | null}` → 204 with no body. Errors: 400 `bad_device_id`, 422 for a kind or state outside the lists, 429 `rate_limited`, 401 without a session.
  - `jobs.scheduler.ROLLUP_LOCAL_HOUR = 3`. Job kind `page_view_rollup` (rolls up, then prunes `page_view_attempts`).

- [ ] **Step 1: Write the failing migration test**

In `backend/tests/integration/models/test_schema_0001.py`, replace

```python
    "fist_bumps",  # 0006 (Plan 15)
    "bump_attempts",  # 0006 (Plan 15)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}
```

with

```python
    "fist_bumps",  # 0006 (Plan 15)
    "bump_attempts",  # 0006 (Plan 15)
    "page_views",  # 0007 (Plan 16)
    "page_view_attempts",  # 0007 (Plan 16)
    "page_view_rollups",  # 0007 (Plan 16)
    "page_kind_rollups",  # 0007 (Plan 16)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}
TABLES_0007 = {"page_views", "page_view_attempts", "page_view_rollups", "page_kind_rollups"}
```

and in `test_upgrade_downgrade_roundtrip` replace

```python
    _alembic(scratch_engine, "downgrade", "0005")  # 0006 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0006) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0004")  # 0005 drops the station labels
    _alembic(scratch_engine, "downgrade", "0003")  # 0004 is a data-only no-op
    _alembic(scratch_engine, "downgrade", "0002")  # 0003 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - TABLES_0006) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0001")  # 0002 drops only its index
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - TABLES_0006) | {"alembic_version"}
```

with

```python
    _alembic(scratch_engine, "downgrade", "0006")  # 0007 drops only its four tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0007) | {"alembic_version"}
    later = TABLES_0006 | TABLES_0007
    _alembic(scratch_engine, "downgrade", "0005")  # 0006 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - later) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0004")  # 0005 drops the station labels
    _alembic(scratch_engine, "downgrade", "0003")  # 0004 is a data-only no-op
    _alembic(scratch_engine, "downgrade", "0002")  # 0003 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - later) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0001")  # 0002 drops only its index
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - later) | {"alembic_version"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: FAIL. The table set after `upgrade head` lacks the four `page_*` tables, and `downgrade 0006` fails with "Can't locate revision".

- [ ] **Step 3: Write the migration**

Create `backend/migrations/versions/0007_page_views.py`:

```python
"""page views: anonymous page-view counts, their rate-limit log, and day/week rollups

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01

Expand-only: four new tables that the previous release never reads, so it runs unchanged on this
schema. All are durable: rebuild_live only clears the live tables (domain/rebuild.py LIVE_TABLES).
page_kind has no CHECK on purpose (Plan 16 Decision 3): the API validates it, so a new kind needs
no migration. page_view_attempts holds an IP only for the rate limit: rows older than 10 minutes are
pruned on the next beacon (as bump_attempts is) and by the daily page_view_rollup job.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("page_kind", sa.Text(), nullable=False),
        sa.Column("me_state", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "me_state IN ('picked', 'skipped', 'none')", name=op.f("ck_page_views_me_state")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_views")),
    )
    op.create_index(
        op.f("ix_page_views_device_id_page_kind_at"),
        "page_views",
        ["device_id", "page_kind", "at"],
    )
    op.create_index(op.f("ix_page_views_at"), "page_views", ["at"])
    op.create_table(
        "page_view_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_view_attempts")),
    )
    op.create_index(op.f("ix_page_view_attempts_ip_at"), "page_view_attempts", ["ip", "at"])
    op.create_table(
        "page_view_rollups",
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("start_day", sa.Date(), nullable=False),
        sa.Column("devices", sa.Integer(), nullable=False),
        sa.Column("me_picked", sa.Integer(), nullable=False),
        sa.Column("me_skipped", sa.Integer(), nullable=False),
        sa.Column("me_none", sa.Integer(), nullable=False),
        sa.CheckConstraint("period IN ('day', 'week')", name=op.f("ck_page_view_rollups_period")),
        sa.PrimaryKeyConstraint("period", "start_day", name=op.f("pk_page_view_rollups")),
    )
    op.create_table(
        "page_kind_rollups",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("page_kind", sa.Text(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", "page_kind", name=op.f("pk_page_kind_rollups")),
    )


def downgrade() -> None:
    op.drop_table("page_kind_rollups")
    op.drop_table("page_view_rollups")
    op.drop_index(op.f("ix_page_view_attempts_ip_at"), table_name="page_view_attempts")
    op.drop_table("page_view_attempts")
    op.drop_index(op.f("ix_page_views_at"), table_name="page_views")
    op.drop_index(op.f("ix_page_views_device_id_page_kind_at"), table_name="page_views")
    op.drop_table("page_views")
```

- [ ] **Step 4: Write the models**

Create `backend/src/sunday_clays/models/page_views.py`:

```python
"""Anonymous page views (Plan 16): raw visits, their rate-limit log, and the day/week rollups
kept after the raw rows go. Durable: never rebuilt."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class PageView(Base):
    """One counted visit: a random device id, a coarse page kind and the "Which one are you?"
    state. Never a name, a URL or an IP."""

    __tablename__ = "page_views"
    __table_args__ = (
        CheckConstraint(
            "me_state IN ('picked', 'skipped', 'none')", name=conv("ck_page_views_me_state")
        ),
        Index(conv("ix_page_views_device_id_page_kind_at"), "device_id", "page_kind", "at"),
        Index(conv("ix_page_views_at"), "at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    page_kind: Mapped[str] = mapped_column(Text, nullable=False)
    me_state: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PageViewAttempt(Base):
    """One beacon per row, for the per-IP rate limit. Rows older than the window are pruned on
    the next beacon and by the daily page_view_rollup job."""

    __tablename__ = "page_view_attempts"
    __table_args__ = (Index(conv("ix_page_view_attempts_ip_at"), "ip", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PageViewRollup(Base):
    """Unique devices in one local day or ISO week, split by each device's last answer there."""

    __tablename__ = "page_view_rollups"
    __table_args__ = (
        CheckConstraint("period IN ('day', 'week')", name=conv("ck_page_view_rollups_period")),
    )

    period: Mapped[str] = mapped_column(Text, primary_key=True)
    start_day: Mapped[date] = mapped_column(Date, primary_key=True)
    devices: Mapped[int] = mapped_column(Integer, nullable=False)
    me_picked: Mapped[int] = mapped_column(Integer, nullable=False)
    me_skipped: Mapped[int] = mapped_column(Integer, nullable=False)
    me_none: Mapped[int] = mapped_column(Integer, nullable=False)


class PageKindRollup(Base):
    """Counted views of one page kind on one local day."""

    __tablename__ = "page_kind_rollups"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    page_kind: Mapped[str] = mapped_column(Text, primary_key=True)
    views: Mapped[int] = mapped_column(Integer, nullable=False)
```

In `backend/src/sunday_clays/models/__init__.py`, replace

```python
from sunday_clays.models.ops import AppState, Job
```

with

```python
from sunday_clays.models.ops import AppState, Job
from sunday_clays.models.page_views import (
    PageKindRollup,
    PageView,
    PageViewAttempt,
    PageViewRollup,
)
```

and replace

```python
    "LoginAttempt",
```

with

```python
    "LoginAttempt",
    "PageKindRollup",
    "PageView",
    "PageViewAttempt",
    "PageViewRollup",
```

- [ ] **Step 5: Run the schema tests to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py tests/integration/test_migrations_cli.py`
Expected: PASS. The roundtrip passes, and the model and catalog CHECK and default comparisons agree. (`alembic check` finds no drift between the models and `0007`.)

- [ ] **Step 6: Write the failing store tests**

Create `backend/tests/integration/domain/test_page_views_store.py`:

```python
"""Page-view store (Plan 16 Task 1): one count per device and page kind every 30 minutes."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import ME_STATES, PAGE_KINDS, record_page_view
from sunday_clays.domain.rebuild import LIVE_TABLES
from sunday_clays.models import PageView

A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
NOW = datetime(2026, 10, 1, 18, 0, tzinfo=UTC)


def _rows(session: Session) -> list[tuple[uuid.UUID, str, str, datetime]]:
    rows = session.execute(
        select(PageView.device_id, PageView.page_kind, PageView.me_state, PageView.at).order_by(
            PageView.id
        )
    )
    return [(d, k, s, at) for d, k, s, at in rows]


def test_the_kinds_and_states_are_exactly_the_approved_lists() -> None:
    assert PAGE_KINDS == (
        "home",
        "profile",
        "event",
        "leaderboards",
        "records",
        "club",
        "stations",
        "weather",
        "yir",
        "explorer",
        "achievements",
        "race",
        "compare",
        "events-list",
        "admin",
        "other",
    )
    assert ME_STATES == ("picked", "skipped", "none")


def test_a_device_counts_once_per_page_kind_every_30_minutes(session: Session) -> None:
    assert record_page_view(session, A, "home", "none", NOW) is True
    almost = NOW + timedelta(minutes=29, seconds=59)
    assert record_page_view(session, A, "home", "picked", almost) is False
    later = NOW + timedelta(minutes=30)
    assert record_page_view(session, A, "home", "picked", later) is True
    assert _rows(session) == [(A, "home", "none", NOW), (A, "home", "picked", later)]


def test_other_kinds_and_other_devices_count_on_their_own(session: Session) -> None:
    record_page_view(session, A, "home", "none", NOW)
    soon = NOW + timedelta(minutes=1)
    assert record_page_view(session, A, "leaderboards", "none", soon) is True
    assert record_page_view(session, B, "home", "skipped", soon) is True
    assert [(d, k) for d, k, _, _ in _rows(session)] == [
        (A, "home"),
        (A, "leaderboards"),
        (B, "home"),
    ]


def _someone_waits_on_an_advisory_lock(engine: Engine) -> bool:
    with engine.connect() as conn:
        waiting = conn.scalar(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")
        )
    return bool(waiting)


def test_two_identical_beacons_at_once_count_once(committed_engine: Engine) -> None:
    """Kills "no lock": the second session must block until the first commits, then see it."""
    with Session(committed_engine) as first, Session(committed_engine) as second:
        assert record_page_view(first, A, "home", "none", NOW) is True  # holds the lock

        def racer() -> bool:
            counted = record_page_view(second, A, "home", "none", NOW + timedelta(seconds=1))
            second.commit()
            return counted

        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(racer)
            deadline = time.monotonic() + 10
            while not _someone_waits_on_an_advisory_lock(committed_engine):
                assert time.monotonic() < deadline, "the second beacon never waited for the first"
                time.sleep(0.01)
            first.commit()
            assert waiting.result(timeout=10) is False
    with Session(committed_engine) as check:
        assert check.scalar(select(func.count()).select_from(PageView)) == 1


def test_page_view_tables_are_not_live_tables() -> None:
    for table in ("page_views", "page_view_attempts", "page_view_rollups", "page_kind_rollups"):
        assert table not in LIVE_TABLES


def test_a_view_stores_only_a_device_a_kind_a_state_and_a_time() -> None:
    assert set(PageView.__table__.columns.keys()) == {
        "id",
        "device_id",
        "page_kind",
        "me_state",
        "at",
    }
```

Create `backend/tests/integration/domain/test_page_view_rollup.py`:

```python
"""Page-view rollup (Plan 16 Task 1): raw visits older than about 90 days become daily and
weekly totals in whole weeks of the club's local time, and the raw rows go."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import RollupReport, rollup_cutoff, rollup_page_views
from sunday_clays.models import PageKindRollup, PageView, PageViewRollup

TZ = "America/Los_Angeles"
PT = ZoneInfo(TZ)
TODAY = date(2026, 10, 1)  # 90 days back is Fri 2026-07-03, so the cutoff is Mon 2026-06-29
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
C = uuid.UUID("00000000-0000-4000-8000-00000000000c")
D = uuid.UUID("00000000-0000-4000-8000-00000000000d")


def _view(session: Session, device: uuid.UUID, kind: str, state: str, at: datetime) -> None:
    session.execute(
        insert(PageView).values(device_id=device, page_kind=kind, me_state=state, at=at)
    )


def _seed(session: Session) -> None:
    # The later visit goes in first: a rollup that took the last *id* instead of the last *time*
    # would call A "none" on Jun 23.
    _view(session, A, "leaderboards", "picked", datetime(2026, 6, 23, 12, 0, tzinfo=PT))
    _view(session, A, "home", "none", datetime(2026, 6, 23, 10, 0, tzinfo=PT))
    _view(session, A, "home", "skipped", datetime(2026, 6, 25, 9, 0, tzinfo=PT))
    _view(session, B, "home", "none", datetime(2026, 6, 23, 11, 0, tzinfo=PT))
    # Sunday 23:30 local is Monday 06:30 UTC: still Sunday, still the week of Jun 22.
    _view(session, D, "home", "none", datetime(2026, 6, 28, 23, 30, tzinfo=PT))
    # From local midnight of the cutoff on, rows stay raw.
    _view(session, D, "records", "picked", datetime(2026, 6, 29, 0, 30, tzinfo=PT))
    _view(session, C, "home", "picked", datetime(2026, 6, 30, 9, 0, tzinfo=PT))


def _rollups(session: Session) -> list[tuple[str, date, int, int, int, int]]:
    rows = session.execute(
        select(
            PageViewRollup.period,
            PageViewRollup.start_day,
            PageViewRollup.devices,
            PageViewRollup.me_picked,
            PageViewRollup.me_skipped,
            PageViewRollup.me_none,
        )
    )
    return sorted((p, s, n, a, b, c) for p, s, n, a, b, c in rows)


def _kinds(session: Session) -> list[tuple[date, str, int]]:
    rows = session.execute(
        select(PageKindRollup.day, PageKindRollup.page_kind, PageKindRollup.views)
    )
    return sorted((d, k, v) for d, k, v in rows)


def _raw(session: Session) -> list[tuple[uuid.UUID, str]]:
    return sorted((d, k) for d, k in session.execute(select(PageView.device_id, PageView.page_kind)))


def test_the_cutoff_is_the_monday_on_or_before_90_days_back() -> None:
    assert rollup_cutoff(TODAY) == date(2026, 6, 29)
    assert rollup_cutoff(date(2026, 9, 27)) == date(2026, 6, 29)  # 90 back is that Monday
    assert rollup_cutoff(date(2026, 10, 5)) == date(2026, 7, 6)  # 90 back is Tue Jul 7


def test_rollup_counts_old_visits_by_local_day_and_week(session: Session) -> None:
    _seed(session)
    assert rollup_page_views(session, TODAY, TZ) == RollupReport(date(2026, 6, 29), 5)
    # (period, start, devices, picked, skipped, none): a week counts A once, not twice.
    assert _rollups(session) == [
        ("day", date(2026, 6, 23), 2, 1, 0, 1),
        ("day", date(2026, 6, 25), 1, 0, 1, 0),
        ("day", date(2026, 6, 28), 1, 0, 0, 1),
        ("week", date(2026, 6, 22), 3, 0, 1, 2),
    ]
    assert _kinds(session) == [
        (date(2026, 6, 23), "home", 2),
        (date(2026, 6, 23), "leaderboards", 1),
        (date(2026, 6, 25), "home", 1),
        (date(2026, 6, 28), "home", 1),
    ]
    assert _raw(session) == sorted([(D, "records"), (C, "home")])


def test_a_second_run_changes_nothing(session: Session) -> None:
    _seed(session)
    rollup_page_views(session, TODAY, TZ)
    before = (_rollups(session), _kinds(session), _raw(session))
    assert rollup_page_views(session, TODAY, TZ) == RollupReport(date(2026, 6, 29), 0)
    assert (_rollups(session), _kinds(session), _raw(session)) == before


def test_nothing_from_the_cutoff_on_is_touched(session: Session) -> None:
    _view(session, C, "home", "picked", datetime(2026, 6, 29, 0, 0, tzinfo=PT))
    assert rollup_page_views(session, TODAY, TZ).rolled == 0
    assert _rollups(session) == []
    assert _kinds(session) == []
    assert _raw(session) == [(C, "home")]
```

- [ ] **Step 7: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_page_views_store.py tests/integration/domain/test_page_view_rollup.py`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'sunday_clays.domain.page_views'`.

- [ ] **Step 8: Write the store and the rollup**

Create `backend/src/sunday_clays/domain/page_views.py`:

```python
"""Anonymous page views (Plan 16): count a visit at most once per device and page kind every 30
minutes, and roll raw visits older than about 90 days into day and week totals.

Nothing here stores a name, a URL or an IP address. A device id is the random UUID a browser keeps
in localStorage ("sc.device"); after the rollup only counts remain. Buckets are the club's local
day and local ISO week (Monday to Sunday). Every grouped bucket is computed once in a subquery and
grouped by that column: psycopg binds parameters server-side, so a GROUP BY that repeats
``timezone($n, at)`` would not match the select list's ``timezone($m, at)``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Final, Literal, get_args
from zoneinfo import ZoneInfo

from sqlalchemy import (
    ColumnElement,
    Date,
    Subquery,
    Text,
    cast,
    delete,
    func,
    insert,
    literal,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.models import PageKindRollup, PageView, PageViewRollup

PageKind = Literal[
    "home",
    "profile",
    "event",
    "leaderboards",
    "records",
    "club",
    "stations",
    "weather",
    "yir",
    "explorer",
    "achievements",
    "race",
    "compare",
    "events-list",
    "admin",
    "other",
]
MeState = Literal["picked", "skipped", "none"]
Period = Literal["day", "week"]

PAGE_KINDS: Final[tuple[str, ...]] = get_args(PageKind)
ME_STATES: Final[tuple[str, ...]] = get_args(MeState)
PERIODS: Final[tuple[Period, ...]] = ("day", "week")
DEDUPE_WINDOW: Final = timedelta(minutes=30)
RAW_DAYS: Final = 90
# pg_advisory_xact_lock class key for one device+kind's dedupe check (rebuild_live holds 7263003)
DEDUPE_LOCK_KEY: Final = 7263004


def record_page_view(
    session: Session, device_id: uuid.UUID, page_kind: str, me_state: str, now: datetime
) -> bool:
    """Store one view unless this device was counted on this kind in the last 30 minutes.

    The advisory lock serialises two identical beacons that arrive together, so the second one
    sees the first after it commits. Returns whether the view was stored.
    """
    session.execute(
        select(func.pg_advisory_xact_lock(DEDUPE_LOCK_KEY, func.hashtext(f"{device_id}:{page_kind}")))
    )
    recent = session.scalar(
        select(PageView.id)
        .where(
            PageView.device_id == device_id,
            PageView.page_kind == page_kind,
            PageView.at > now - DEDUPE_WINDOW,
        )
        .limit(1)
    )
    if recent is not None:
        return False
    session.execute(
        insert(PageView).values(
            device_id=device_id, page_kind=page_kind, me_state=me_state, at=now
        )
    )
    return True


def rollup_cutoff(today: date) -> date:
    """The Monday on or before ``today - RAW_DAYS``: every raw day before it is a whole week."""
    edge = today - timedelta(days=RAW_DAYS)
    return edge - timedelta(days=edge.weekday())


def local_midnight(day: date, tz: str) -> datetime:
    """The instant ``day`` starts in the club's timezone."""
    return datetime.combine(day, time(), ZoneInfo(tz))


def bucket_of(period: Period, tz: str) -> ColumnElement[date]:
    """A view's local day, or the Monday of its local ISO week."""
    local = func.timezone(tz, PageView.at)
    if period == "day":
        return cast(local, Date)
    return cast(func.date_trunc("week", local), Date)


def latest_states(tz: str, period: Period | None, *where: ColumnElement[bool]) -> Subquery:
    """Each device's last me_state per local day or week (or over every matching row when
    ``period`` is None): one row per (bucket, device), the latest by time, then by id."""
    partition: list[ColumnElement[Any]] = [PageView.device_id]
    columns: list[ColumnElement[Any]] = [PageView.device_id, PageView.me_state]
    if period is not None:
        bucket = bucket_of(period, tz)
        partition.insert(0, bucket)
        columns.insert(0, bucket.label("bucket"))
    rank = func.row_number().over(
        partition_by=partition, order_by=(PageView.at.desc(), PageView.id.desc())
    )
    ranked = select(*columns, rank.label("rank")).where(*where).subquery("ranked")
    keep = [column for column in ranked.c if column.key != "rank"]
    return select(*keep).where(ranked.c.rank == 1).subquery("latest")


def state_counts(latest: Subquery) -> tuple[ColumnElement[Any], ...]:
    """Devices, then how many of them last answered picked, skipped and none."""
    me = latest.c.me_state
    return (
        func.count(),
        func.count().filter(me == "picked"),
        func.count().filter(me == "skipped"),
        func.count().filter(me == "none"),
    )


@dataclass(frozen=True)
class RollupReport:
    cutoff: date
    rolled: int  # raw rows counted into the rollups and deleted


def rollup_page_views(session: Session, today: date, tz: str) -> RollupReport:
    """Fold raw views before local midnight of ``rollup_cutoff(today)`` into day and week rows
    and per-day kind counts, then delete them, all in the caller's transaction.

    Days and weeks are counted separately from the raw rows (a week's devices is not the sum of
    its days). ON CONFLICT DO NOTHING makes a repeat harmless; the server stamps ``at``, so no
    raw row can appear later on a rolled day.
    """
    cutoff = rollup_cutoff(today)
    old = PageView.at < local_midnight(cutoff, tz)
    rolled = session.scalar(select(func.count()).select_from(PageView).where(old)) or 0
    for period in PERIODS:
        latest = latest_states(tz, period, old)
        counts = select(
            cast(literal(period), Text), latest.c.bucket, *state_counts(latest)
        ).group_by(latest.c.bucket)
        session.execute(
            pg_insert(PageViewRollup)
            .from_select(
                ["period", "start_day", "devices", "me_picked", "me_skipped", "me_none"], counts
            )
            .on_conflict_do_nothing(index_elements=["period", "start_day"])
        )
    raw = select(bucket_of("day", tz).label("day"), PageView.page_kind).where(old).subquery()
    per_kind = select(raw.c.day, raw.c.page_kind, func.count()).group_by(
        raw.c.day, raw.c.page_kind
    )
    session.execute(
        pg_insert(PageKindRollup)
        .from_select(["day", "page_kind", "views"], per_kind)
        .on_conflict_do_nothing(index_elements=["day", "page_kind"])
    )
    session.execute(delete(PageView).where(old))
    return RollupReport(cutoff, rolled)
```

- [ ] **Step 9: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_page_views_store.py tests/integration/domain/test_page_view_rollup.py`
Expected: PASS (10 passed). If `ruff format` rewraps the long `pg_advisory_xact_lock` line, keep what it produces.

- [ ] **Step 10: Write the failing rate-limit test**

Create `backend/tests/integration/auth/test_page_view_rate_limit.py`:

```python
"""Page-view rate limit (Plan 16 Task 1): ``page_view_limit`` (default 600) beacons per client IP
per 10 minutes, and the daily prune that clears the IPs a quiet spell leaves behind."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import (
    PAGE_VIEW_WINDOW,
    page_views_limited,
    prune_page_view_attempts,
    record_page_view_attempt,
)
from sunday_clays.config import Settings, get_settings
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["page_view_attempts"]


def _attempts(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at}] * n)


def _ips(session: Session) -> list[str]:
    return [ip for (ip,) in session.execute(select(ATTEMPTS.c.ip))]


def test_the_default_is_600_per_10_minutes() -> None:
    assert Settings.model_fields["page_view_limit"].default == 600
    assert PAGE_VIEW_WINDOW == timedelta(minutes=10)


def test_the_limitth_beacon_is_the_last_allowed(session: Session, auth_env: Settings) -> None:
    limit = auth_env.page_view_limit
    assert limit == 600  # the test env leaves PAGE_VIEW_LIMIT unset
    _attempts(session, "203.0.113.7", limit - 1)
    assert page_views_limited(session, "203.0.113.7") is False
    record_page_view_attempt(session, "203.0.113.7")
    assert page_views_limited(session, "203.0.113.7") is True
    assert page_views_limited(session, "198.51.100.1") is False


def test_the_limit_comes_from_settings(
    session: Session, auth_env: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Kills a hard-coded 600: the e2e stack relies on PAGE_VIEW_LIMIT to raise it.
    monkeypatch.setenv("PAGE_VIEW_LIMIT", "3")
    get_settings.cache_clear()
    _attempts(session, "203.0.113.7", 2)
    assert page_views_limited(session, "203.0.113.7") is False
    record_page_view_attempt(session, "203.0.113.7")
    assert page_views_limited(session, "203.0.113.7") is True


def test_the_window_is_10_minutes(session: Session, auth_env: Settings) -> None:
    limit = auth_env.page_view_limit
    _attempts(session, "203.0.113.7", limit, age=timedelta(minutes=10, seconds=30))
    assert page_views_limited(session, "203.0.113.7") is False
    _attempts(session, "198.51.100.1", limit, age=timedelta(minutes=9, seconds=30))
    assert page_views_limited(session, "198.51.100.1") is True


def test_recording_prunes_rows_outside_the_window(session: Session) -> None:
    _attempts(session, "203.0.113.7", 3, age=timedelta(minutes=11))
    record_page_view_attempt(session, "198.51.100.1")
    assert _ips(session) == ["198.51.100.1"]


def test_the_daily_prune_clears_old_rows_with_no_new_beacon(session: Session) -> None:
    # The last burst before a quiet spell: no beacon arrives to prune it, so the job must.
    _attempts(session, "203.0.113.7", 2, age=timedelta(minutes=11))
    _attempts(session, "198.51.100.1", 1, age=timedelta(minutes=9))
    prune_page_view_attempts(session)
    assert _ips(session) == ["198.51.100.1"]  # a row inside the window is kept
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd backend && uv run pytest -q tests/integration/auth/test_page_view_rate_limit.py`
Expected: FAIL with `ImportError: cannot import name 'PAGE_VIEW_WINDOW'`.

- [ ] **Step 12: Add the limiter**

In `backend/src/sunday_clays/auth/ratelimit.py`, replace

```python
def record_bump_action(session: Session, ip: str) -> None:
    """Insert one action and prune rows outside the window, inside the caller's transaction."""
    _insert_and_prune(session, _bump_attempts(), BUMP_WINDOW, ip=ip)
```

with

```python
def record_bump_action(session: Session, ip: str) -> None:
    """Insert one action and prune rows outside the window, inside the caller's transaction."""
    _insert_and_prune(session, _bump_attempts(), BUMP_WINDOW, ip=ip)


# --- Plan 16: page views -------------------------------------------------------------------------
# Per IP, like bumps: club Wi-Fi puts many phones behind one address. Each device's views are
# already deduped per page kind, so this only guards volume. The limit is settings.page_view_limit
# (default 600) so the one-IP e2e stack can raise it. Rows older than the window are pruned on the
# next beacon and by the daily page_view_rollup job (prune_page_view_attempts).
PAGE_VIEW_WINDOW: Final = timedelta(minutes=10)


def _page_view_attempts() -> Table:
    return Base.metadata.tables["page_view_attempts"]


def page_views_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already sent ``page_view_limit`` beacons in the last ``PAGE_VIEW_WINDOW``."""
    since = datetime.now(UTC) - PAGE_VIEW_WINDOW
    limit = get_settings().page_view_limit
    return _count_since(session, _page_view_attempts(), ip, since) >= limit


def record_page_view_attempt(session: Session, ip: str) -> None:
    """Insert one beacon and prune rows outside the window, inside the caller's transaction."""
    _insert_and_prune(session, _page_view_attempts(), PAGE_VIEW_WINDOW, ip=ip)


def prune_page_view_attempts(session: Session) -> None:
    """Delete beacons older than the window, in the caller's transaction. The daily rollup job
    calls this so the last burst before a quiet spell does not keep its IPs until the next beacon."""
    t = _page_view_attempts()
    session.execute(delete(t).where(t.c.at < datetime.now(UTC) - PAGE_VIEW_WINDOW))
```

In `backend/src/sunday_clays/config.py`, replace

```python
    login_max_failures: int = 10
    login_window_minutes: int = 15
```

with

```python
    login_max_failures: int = 10
    login_window_minutes: int = 15
    page_view_limit: int = 600  # Plan 16: page-view beacons per IP per 10 minutes
```

In `compose.test.yaml`, replace

```yaml
      # Every e2e login comes from one IP: the default 10 failures / 15 min would turn a re-run
      # against a long-lived stack into 429s. Backend unit tests cover the limiter itself.
      LOGIN_MAX_FAILURES: "1000"
```

with

```yaml
      # Every e2e login comes from one IP: the default 10 failures / 15 min would turn a re-run
      # against a long-lived stack into 429s. Backend unit tests cover the limiter itself.
      LOGIN_MAX_FAILURES: "1000"
      # Every page-view beacon comes from that one IP too (about 190 page loads x 2 projects, plus
      # in-app navigation): the default 600 / 10 min would 429 late in a full run (Plan 16).
      PAGE_VIEW_LIMIT: "100000"
```

and replace the module docstring

```python
"""Rate limits per client-IP bucket: failed logins (``login_attempts``, C4, C8) and fist bumps
(``bump_attempts``, Plan 15)."""
```

with

```python
"""Rate limits per client-IP bucket: failed logins (``login_attempts``, C4, C8), fist bumps
(``bump_attempts``, Plan 15) and page-view beacons (``page_view_attempts``, Plan 16)."""
```

- [ ] **Step 13: Run it to verify it passes**

Run: `cd backend && uv run pytest -q tests/integration/auth/test_page_view_rate_limit.py tests/integration/auth/test_bump_rate_limit.py tests/integration/auth/test_login_rate_limit.py tests/unit/test_config.py`
Expected: PASS. The bump and login limiters and the config defaults test are unchanged. Then check the e2e override parses: `docker compose -f compose.yaml -f compose.test.yaml config | grep PAGE_VIEW_LIMIT` prints `PAGE_VIEW_LIMIT: "100000"` under `api`.

- [ ] **Step 14: Write the failing API tests**

Create `backend/tests/integration/api/test_pageviews_api.py`:

```python
"""POST /api/pageviews (Plan 16 Task 1): counted for viewers, dropped for admins, deduped,
validated and rate-limited, with nothing that identifies a person stored with a view."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
IP = {"X-Real-IP": "203.0.113.7"}
VIEWS = Base.metadata.tables["page_views"]
ATTEMPTS = Base.metadata.tables["page_view_attempts"]


def _beacon(
    client: TestClient,
    device: str = A,
    kind: str = "home",
    state: str = "none",
    headers: dict[str, str] = IP,
    **extra: object,
):
    body = {"device_id": device, "page_kind": kind, "me_state": state, **extra}
    return client.post("/api/pageviews", json=body, headers=headers)


def _views(session: Session) -> list[tuple[str, str, str]]:
    rows = session.execute(
        select(VIEWS.c.device_id, VIEWS.c.page_kind, VIEWS.c.me_state).order_by(VIEWS.c.id)
    )
    return [(str(d), k, s) for d, k, s in rows]


def _attempt_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ATTEMPTS)) or 0


def test_a_viewer_beacon_is_counted_once_per_kind_every_30_minutes(
    viewer_client: TestClient, session: Session
) -> None:
    first = _beacon(viewer_client)
    assert first.status_code == 204
    assert first.content == b""
    assert _beacon(viewer_client, state="picked").status_code == 204  # deduped, still 204
    assert _beacon(viewer_client, kind="profile", state="picked").status_code == 204
    assert _views(session) == [(A, "home", "none"), (A, "profile", "picked")]


def test_an_admin_beacon_is_dropped_and_leaves_no_trace(
    admin_client: TestClient, session: Session
) -> None:
    assert _beacon(admin_client).status_code == 204
    assert _beacon(admin_client, device="not-a-uuid").status_code == 204  # dropped before checks
    assert _views(session) == []
    assert _attempt_count(session) == 0


def test_the_browser_clock_is_accepted_but_never_stored(
    viewer_client: TestClient, session: Session
) -> None:
    before = datetime.now(UTC)
    assert _beacon(viewer_client, at="2001-01-01T00:00:00Z").status_code == 204
    stored = session.scalar(select(VIEWS.c.at))
    assert stored is not None
    assert stored >= before - timedelta(seconds=5)


def test_a_device_id_that_is_not_a_uuid_is_400_and_still_counts_toward_the_limit(
    viewer_client: TestClient, session: Session
) -> None:
    for bad in ("not-a-uuid", "{" + A + "}", A + "x"):
        response = _beacon(viewer_client, device=bad)
        assert response.status_code == 400, bad
        assert response.json()["error"]["code"] == "bad_device_id"
    assert _views(session) == []
    assert _attempt_count(session) == 3


def test_a_kind_or_state_outside_the_lists_is_422(
    viewer_client: TestClient, session: Session
) -> None:
    assert _beacon(viewer_client, kind="/shooters/3").status_code == 422
    assert _beacon(viewer_client, state="Hadley, Ike").status_code == 422
    assert _views(session) == []
    assert _attempt_count(session) == 0  # refused before the handler runs


def test_the_limitth_beacon_in_10_minutes_is_the_last(
    viewer_client: TestClient, session: Session
) -> None:
    now = datetime.now(UTC)
    limit = get_settings().page_view_limit  # 600: viewer_client's auth_env leaves it unset
    session.execute(insert(ATTEMPTS), [{"ip": "203.0.113.7", "at": now}] * (limit - 1))
    assert _beacon(viewer_client).status_code == 204
    refused = _beacon(viewer_client, kind="records")
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "rate_limited"
    other = {"X-Real-IP": "198.51.100.1"}
    assert _beacon(viewer_client, kind="records", headers=other).status_code == 204
    assert _views(session) == [(A, "home", "none"), (A, "records", "none")]
```

- [ ] **Step 15: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_pageviews_api.py`
Expected: FAIL. Every test gets 404 for `POST /api/pageviews` (no such route).

- [ ] **Step 16: Write the route**

Create `backend/src/sunday_clays/api/routes/pageviews.py`:

```python
"""POST /api/pageviews (Plan 16): one anonymous page-view beacon from the SPA.

Answers 204 with no body whether the view was stored or dropped: an admin session is dropped
before anything is written (Decision 6), and the same device and kind inside 30 minutes is
deduped (domain/page_views.py). The server's clock stamps the view; the browser's ``at`` is
accepted and ignored (Decision 4). The IP feeds only the rate-limit log, as for bumps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from sunday_clays.api.routes.bumps import parse_device_id
from sunday_clays.auth.deps import TooManyRequestsError, client_ip, require_viewer
from sunday_clays.auth.ratelimit import page_views_limited, record_page_view_attempt
from sunday_clays.auth.sessions import Role
from sunday_clays.db import SessionDep
from sunday_clays.domain.page_views import MeState, PageKind, record_page_view

router = APIRouter(tags=["pageviews"])


class PageViewIn(BaseModel):
    device_id: str
    page_kind: PageKind
    me_state: MeState
    at: datetime | None = None  # the browser's clock: accepted, never stored


@router.post("/api/pageviews", status_code=204)
def page_view(
    body: PageViewIn,
    request: Request,
    session: SessionDep,
    role: Annotated[Role, Depends(require_viewer)],
) -> None:
    if role == "admin":
        return
    ip = client_ip(request)
    if page_views_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many page views from here. Try again soon.")
    record_page_view_attempt(session, ip)
    session.commit()  # get_session rolls back on any error; a refused beacon still counts
    device = parse_device_id(body.device_id)
    record_page_view(session, device, body.page_kind, body.me_state, datetime.now(UTC))
```

- [ ] **Step 17: Run the API, auth-matrix and discovery tests**

Run: `cd backend && uv run pytest -q tests/integration/api/test_pageviews_api.py tests/integration/api/test_route_auth_matrix.py tests/unit/api/test_routes_discovery.py tests/unit/api/test_export_openapi.py`
Expected: PASS. The auth matrix walks `POST /api/pageviews` and gets 401 without a session.

- [ ] **Step 18: Write the failing scheduler and job tests**

Replace the whole of `backend/tests/integration/jobs/test_job_scheduler.py` with:

```python
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from sunday_clays.jobs.scheduler import ROLLUP_LOCAL_HOUR, schedule_due
from sunday_clays.models import Job

PT = ZoneInfo("America/Los_Angeles")
AFTERNOON = datetime(2020, 1, 5, 15, 0, tzinfo=PT)  # a past date: real created_at values are later
WEATHER = frozenset({"weather_sync", "forecast_refresh"})


def _kinds(session: Session, only: frozenset[str] | None = None) -> list[str]:
    kinds = sorted(session.scalars(select(Job.kind)))
    return kinds if only is None else [kind for kind in kinds if kind in only]


def _old_job(session: Session, kind: str, created_at: datetime) -> None:
    session.add(Job(kind=kind, status="done", created_at=created_at, dedupe_key=kind))
    session.flush()


def test_only_the_rollup_is_scheduled_when_weather_is_disabled(session: Session) -> None:
    assert len(schedule_due(session, AFTERNOON, weather_enabled=False)) == 1
    assert _kinds(session) == ["page_view_rollup"]


def test_after_14_local_every_job_is_due(session: Session) -> None:
    ids = schedule_due(session, AFTERNOON.astimezone(UTC), weather_enabled=True)
    assert len(ids) == 3
    assert _kinds(session) == ["forecast_refresh", "page_view_rollup", "weather_sync"]


def test_before_14_local_the_weather_sync_is_not_due(session: Session) -> None:
    schedule_due(session, AFTERNOON.replace(hour=13, minute=59), weather_enabled=True)
    assert _kinds(session, WEATHER) == ["forecast_refresh"]


def test_called_twice_in_the_same_slot_creates_one_job_each(session: Session) -> None:
    first = schedule_due(session, AFTERNOON, weather_enabled=True)
    session.execute(update(Job).values(status="done"))  # finished, so dedupe cannot hide a repeat
    assert schedule_due(session, AFTERNOON + timedelta(hours=1), weather_enabled=True) == []
    assert len(first) == 3
    assert _kinds(session) == ["forecast_refresh", "page_view_rollup", "weather_sync"]


def test_weather_sync_is_due_again_the_next_day_and_forecast_after_6h(session: Session) -> None:
    _old_job(session, "weather_sync", AFTERNOON - timedelta(days=1))
    _old_job(session, "forecast_refresh", AFTERNOON - timedelta(hours=5))
    schedule_due(session, AFTERNOON, weather_enabled=True)
    assert _kinds(session, WEATHER) == ["forecast_refresh", "weather_sync", "weather_sync"]
    session.execute(update(Job).values(status="done"))
    schedule_due(session, AFTERNOON + timedelta(hours=2), weather_enabled=True)
    assert _kinds(session, WEATHER).count("forecast_refresh") == 2


def test_the_rollup_waits_for_3_local(session: Session) -> None:
    assert ROLLUP_LOCAL_HOUR == 3
    early = datetime(2020, 1, 5, 2, 59, tzinfo=PT)
    assert schedule_due(session, early, weather_enabled=False) == []
    assert len(schedule_due(session, early.replace(hour=3, minute=0), weather_enabled=False)) == 1


def test_the_rollup_slot_is_local_time_not_utc(session: Session) -> None:
    # 10:59 UTC is 02:59 in Los Angeles (PST, UTC-8): not yet due there.
    assert schedule_due(session, datetime(2020, 1, 5, 10, 59, tzinfo=UTC), weather_enabled=False) == []
    assert _kinds(session) == []
    schedule_due(session, datetime(2020, 1, 5, 11, 0, tzinfo=UTC), weather_enabled=False)
    assert _kinds(session) == ["page_view_rollup"]


def test_the_rollup_runs_once_a_local_day(session: Session) -> None:
    # A job created now gets a real (later) created_at, so the earlier day's job is backdated, as
    # in the weather test: it counts for its own day only.
    morning = datetime(2020, 1, 5, 3, 0, tzinfo=PT)
    _old_job(session, "page_view_rollup", morning)
    assert schedule_due(session, morning.replace(hour=23), weather_enabled=False) == []
    next_day = morning + timedelta(days=1)
    assert len(schedule_due(session, next_day, weather_enabled=False)) == 1
    session.execute(update(Job).values(status="done"))  # finished, so dedupe cannot hide a repeat
    assert schedule_due(session, next_day.replace(hour=23), weather_enabled=False) == []
    assert _kinds(session) == ["page_view_rollup", "page_view_rollup"]
```

Create `backend/tests/integration/jobs/test_page_view_rollup_job.py`:

```python
"""The page_view_rollup job (Plan 16 Task 1): registered, run by the worker in the club's
timezone, and it folds old views into the rollups."""

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.domain.page_views import RollupReport
from sunday_clays.jobs import page_view_rollup, worker
from sunday_clays.jobs.handlers import load_handlers
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Job, PageView, PageViewAttempt, PageViewRollup


def test_the_handler_is_registered() -> None:
    assert "page_view_rollup" in load_handlers()


def test_the_job_runs_the_rollup_for_today_in_the_club_timezone(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    def fake(_: Session, today: object, tz: str) -> RollupReport:
        seen.update(today=today, tz=tz)
        return RollupReport(date(2026, 1, 5), 0)

    monkeypatch.setattr(page_view_rollup, "rollup_page_views", fake)
    monkeypatch.setattr(
        page_view_rollup, "get_settings", lambda: SimpleNamespace(timezone="Pacific/Auckland")
    )
    job_id = enqueue(session, "page_view_rollup")
    assert worker.process_one(session, weather_enabled=False) is True
    assert session.scalar(select(Job.status).where(Job.id == job_id)) == "done"
    assert seen == {"today": datetime.now(ZoneInfo("Pacific/Auckland")).date(), "tz": "Pacific/Auckland"}


def test_the_job_folds_a_view_older_than_96_days(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        page_view_rollup,
        "get_settings",
        lambda: SimpleNamespace(timezone="America/Los_Angeles"),
    )
    old = datetime.now(UTC) - timedelta(days=120)
    session.execute(
        insert(PageView).values(
            device_id=uuid.uuid4(), page_kind="home", me_state="none", at=old
        )
    )
    enqueue(session, "page_view_rollup")
    worker.process_one(session, weather_enabled=False)
    assert session.scalar(select(func.count()).select_from(PageView)) == 0
    assert session.scalar(
        select(func.count()).select_from(PageViewRollup).where(PageViewRollup.period == "week")
    ) == 1


def test_the_job_prunes_rate_limit_rows_left_by_a_quiet_spell(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        page_view_rollup,
        "get_settings",
        lambda: SimpleNamespace(timezone="America/Los_Angeles"),
    )
    now = datetime.now(UTC)
    session.execute(
        insert(PageViewAttempt),
        [{"ip": "203.0.113.7", "at": now - timedelta(hours=5)}, {"ip": "198.51.100.1", "at": now}],
    )
    enqueue(session, "page_view_rollup")
    worker.process_one(session, weather_enabled=False)
    assert list(session.scalars(select(PageViewAttempt.ip))) == ["198.51.100.1"]
```

- [ ] **Step 19: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/jobs/test_job_scheduler.py tests/integration/jobs/test_page_view_rollup_job.py`
Expected: FAIL. The scheduler test fails at import with `ImportError: cannot import name 'ROLLUP_LOCAL_HOUR'`, and the job test with `ImportError: cannot import name 'page_view_rollup'`. (Once the handler exists, `test_the_job_prunes_rate_limit_rows_left_by_a_quiet_spell` fails on its own if the handler leaves out the prune: the 5-hour-old row survives, because no beacon arrives to prune it.)

- [ ] **Step 20: Write the handler and schedule it**

Create `backend/src/sunday_clays/jobs/page_view_rollup.py`:

```python
"""The ``page_view_rollup`` job (Plan 16): once a day, fold raw page views older than about 90
days into day and week totals and delete them (domain/page_views.py), then delete page-view
rate-limit rows older than their 10-minute window (auth/ratelimit.py)."""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import prune_page_view_attempts
from sunday_clays.config import get_settings
from sunday_clays.domain.page_views import rollup_page_views
from sunday_clays.jobs.handlers import handler

logger = logging.getLogger(__name__)


@handler("page_view_rollup")
def handle_page_view_rollup(session: Session, payload: dict[str, Any]) -> None:
    tz = get_settings().timezone
    report = rollup_page_views(session, datetime.now(ZoneInfo(tz)).date(), tz)
    # A beacon only prunes when one arrives: clear what the last burst before a quiet spell left.
    prune_page_view_attempts(session)
    logger.info("rolled up %d page views before %s", report.rolled, report.cutoff)
```

In `backend/src/sunday_clays/jobs/scheduler.py`, replace

```python
WEATHER_SYNC_LOCAL_HOUR = 14
FORECAST_INTERVAL = timedelta(hours=6)
```

with

```python
WEATHER_SYNC_LOCAL_HOUR = 14
FORECAST_INTERVAL = timedelta(hours=6)
ROLLUP_LOCAL_HOUR = 3  # Plan 16: page_view_rollup, once a local day, weather or not
```

and replace

```python
    """Enqueue weather_sync (daily after 14:00 local) and forecast_refresh (every 6 h) when due."""
    if not weather_enabled:
        return []
    local_now = now.astimezone(ZoneInfo(timezone))
    slot_start = local_now.replace(hour=WEATHER_SYNC_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    job_ids: list[int] = []
```

with

```python
    """Enqueue page_view_rollup (daily after 03:00 local), and with weather on, weather_sync
    (daily after 14:00 local) and forecast_refresh (every 6 h), when due."""
    local_now = now.astimezone(ZoneInfo(timezone))
    job_ids: list[int] = []
    rollup_slot = local_now.replace(hour=ROLLUP_LOCAL_HOUR, minute=0, second=0, microsecond=0)
    if local_now >= rollup_slot and not _created_since(session, "page_view_rollup", rollup_slot):
        job_ids.append(enqueue(session, "page_view_rollup", dedupe_key="page_view_rollup"))
    if not weather_enabled:
        return job_ids
    slot_start = local_now.replace(hour=WEATHER_SYNC_LOCAL_HOUR, minute=0, second=0, microsecond=0)
```

Then keep the worker-loop tests off the clock. `run_worker` now queues `page_view_rollup` on every poll from 03:00 local onwards, and the `committed_engine` tests in `test_worker_loop.py` patch only `worker.get_settings`. Between 03:00 and midnight PT they would pick up the rollup job, whose handler calls the real `get_settings()` (no secrets in the test env) and fails. In `backend/tests/integration/jobs/test_worker_loop.py`, replace

```python
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(weather_enabled=False, timezone="America/Los_Angeles"),
    )
    return heartbeat
```

with

```python
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(weather_enabled=False, timezone="America/Los_Angeles"),
    )
    # Plan 16: the real scheduler queues page_view_rollup from 03:00 local every day, which would
    # make these loop tests depend on the time of day. They test the loop; test_job_scheduler.py
    # tests the schedule.
    monkeypatch.setattr(worker, "schedule_due", lambda *_args, **_kwargs: [])
    return heartbeat
```

- [ ] **Step 21: Run them to verify they pass, plus the worker suites**

Run: `cd backend && uv run pytest -q tests/integration/jobs`
Expected: PASS.

Evidence that the `worker_settings` change is needed at any hour: edit `ROLLUP_LOCAL_HOUR = 0` in `jobs/scheduler.py` locally (so the rollup is always due), stash the `test_worker_loop.py` change, and run `uv run pytest -q tests/integration/jobs/test_worker_loop.py`. The `run_worker` tests fail (RED): the rollup job is claimed and its handler's `get_settings()` raises. Restore the fixture change and they pass (GREEN). Then revert `ROLLUP_LOCAL_HOUR` to 3 and paste both runs.

- [ ] **Step 22: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: "All checks passed!", "N files already formatted", "Success: no issues found", the whole suite green, and coverage at or above 90% lines and 90% branches. If `ruff format --check` flags a file, run `uv run ruff format .` and re-check.

- [ ] **Step 23: Commit**

```bash
git add backend/migrations/versions/0007_page_views.py backend/src/sunday_clays/models/page_views.py backend/src/sunday_clays/models/__init__.py backend/src/sunday_clays/domain/page_views.py backend/src/sunday_clays/auth/ratelimit.py backend/src/sunday_clays/config.py compose.test.yaml backend/src/sunday_clays/api/routes/pageviews.py backend/src/sunday_clays/jobs/page_view_rollup.py backend/src/sunday_clays/jobs/scheduler.py backend/tests/integration/models/test_schema_0001.py backend/tests/integration/domain/test_page_views_store.py backend/tests/integration/domain/test_page_view_rollup.py backend/tests/integration/auth/test_page_view_rate_limit.py backend/tests/integration/api/test_pageviews_api.py backend/tests/integration/jobs/test_job_scheduler.py backend/tests/integration/jobs/test_page_view_rollup_job.py backend/tests/integration/jobs/test_worker_loop.py
git commit -m "feat(analytics): anonymous page-view store, POST /api/pageviews and the daily rollup (Plan 16 T1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The admin analytics API

**Files:**
- Create: `backend/src/sunday_clays/domain/site_analytics.py`
- Create: `backend/src/sunday_clays/api/routes/admin_analytics.py`
- Create: `backend/tests/integration/domain/test_site_analytics.py`
- Create: `backend/tests/integration/api/test_admin_analytics_api.py`

**Interfaces:**
- Consumes (T1): `domain.page_views.bucket_of`, `latest_states`, `state_counts`, `local_midnight`, `Period`; the models `PageView`, `PageViewRollup`, `PageKindRollup`; and also `FistBump`, `Insight`, `analytics.insights.templates.plain`, `api.routes._filters.check_window`, `config.get_settings`. Fixtures: `session`, `fx_session`, `admin_client`, `viewer_client`, `auth_env`.
- Produces (T4 relies on the OpenAPI this generates):
  - `GET /api/admin/analytics/visitors?since=&as_of=` → `VisitorsOut {days: [{day, devices}], weeks: [{week, devices}], busiest: [{day, devices}]}`
  - `GET /api/admin/analytics/pages?since=&as_of=` → `list[PageKindViewsOut {page_kind: str, views: int}]`
  - `GET /api/admin/analytics/bumps?since=&as_of=` → `BumpsOut {days: [{day, bumps}], top: [{key, headline: str | null, bumps}], devices, devices_all_time}`
  - `GET /api/admin/analytics/me-states?since=&as_of=` → `UptakeOut {weeks: [{week, picked, skipped, none}], latest: {picked, skipped, none}, latest_since: date | null}`
  - Errors: 400 `invalid_range` (since after as_of), 401 without a session, 403 `forbidden` for a viewer. Every response is `Cache-Control: no-store` with no ETag.
  - `domain.site_analytics`: `Span(since: date | None, as_of: date)` with `.has(day)`, `monday(day)`, `visitors(session, tz, span)`, `page_kinds(...)`, `bumps(...)`, `uptake(...)`, `BUSIEST = 5`, `TOP_INSIGHTS = 10`.

- [ ] **Step 1: Write the failing domain tests**

Create `backend/tests/integration/domain/test_site_analytics.py`:

```python
"""Admin analytics reads (Plan 16 Task 2): rollups and raw rows merged, local days, zero-filled."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.templates import plain
from sunday_clays.domain.site_analytics import (
    BumpDay,
    MeStates,
    PageKindViews,
    Span,
    TopInsight,
    VisitorDay,
    VisitorWeek,
    WeekMeStates,
    bumps,
    monday,
    page_kinds,
    uptake,
    visitors,
)
from sunday_clays.models import FistBump, Insight, PageKindRollup, PageView, PageViewRollup

TZ = "America/Los_Angeles"
PT = ZoneInfo(TZ)
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
C = uuid.UUID("00000000-0000-4000-8000-00000000000c")
WEEK = Span(date(2026, 9, 14), date(2026, 9, 20))  # Monday to Sunday
GONE = "fedcba9876543210fedc"


def _view(session: Session, device: uuid.UUID, kind: str, state: str, at: datetime) -> None:
    session.execute(
        insert(PageView).values(device_id=device, page_kind=kind, me_state=state, at=at)
    )


def _seed(session: Session) -> None:
    session.execute(
        insert(PageViewRollup),
        [
            {"period": "day", "start_day": date(2026, 6, 23), "devices": 2, "me_picked": 1,
             "me_skipped": 0, "me_none": 1},
            {"period": "day", "start_day": date(2026, 6, 25), "devices": 1, "me_picked": 0,
             "me_skipped": 1, "me_none": 0},
            {"period": "week", "start_day": date(2026, 6, 22), "devices": 3, "me_picked": 0,
             "me_skipped": 1, "me_none": 2},
        ],
    )
    session.execute(
        insert(PageKindRollup),
        [
            {"day": date(2026, 6, 23), "page_kind": "home", "views": 2},
            {"day": date(2026, 6, 23), "page_kind": "leaderboards", "views": 1},
        ],
    )
    # A's later answer goes in first: "last by id" would call A "none" on Sep 14.
    _view(session, A, "records", "picked", datetime(2026, 9, 14, 15, 0, tzinfo=PT))
    _view(session, A, "home", "none", datetime(2026, 9, 14, 10, 0, tzinfo=PT))
    _view(session, B, "home", "skipped", datetime(2026, 9, 14, 11, 0, tzinfo=PT))
    _view(session, A, "home", "picked", datetime(2026, 9, 16, 9, 0, tzinfo=PT))
    # Sunday 23:30 local is Monday in UTC: it stays on Sunday Sep 20.
    _view(session, C, "leaderboards", "none", datetime(2026, 9, 20, 23, 30, tzinfo=PT))


def test_monday_and_span() -> None:
    assert monday(date(2026, 9, 20)) == date(2026, 9, 14)
    assert monday(date(2026, 9, 14)) == date(2026, 9, 14)
    assert WEEK.has(date(2026, 9, 14)) and WEEK.has(date(2026, 9, 20))
    assert not WEEK.has(date(2026, 9, 13)) and not WEEK.has(date(2026, 9, 21))
    assert Span(None, date(2026, 9, 20)).has(date(2001, 1, 1))


def test_visitors_merge_rollups_and_raw_and_zero_fill(session: Session) -> None:
    _seed(session)
    result = visitors(session, TZ, WEEK)
    assert result.days == [
        VisitorDay(date(2026, 9, 14), 2),
        VisitorDay(date(2026, 9, 15), 0),
        VisitorDay(date(2026, 9, 16), 1),
        VisitorDay(date(2026, 9, 17), 0),
        VisitorDay(date(2026, 9, 18), 0),
        VisitorDay(date(2026, 9, 19), 0),
        VisitorDay(date(2026, 9, 20), 1),
    ]
    assert result.weeks == [VisitorWeek(date(2026, 9, 14), 3)]  # A, B and C once each
    # Most devices first, then the later day.
    assert result.busiest == [
        VisitorDay(date(2026, 9, 14), 2),
        VisitorDay(date(2026, 9, 20), 1),
        VisitorDay(date(2026, 9, 16), 1),
    ]


def test_all_time_visitors_start_at_the_first_rolled_day(session: Session) -> None:
    _seed(session)
    result = visitors(session, TZ, Span(None, date(2026, 9, 20)))
    assert result.days[0] == VisitorDay(date(2026, 6, 23), 2)
    assert len(result.days) == 90  # Jun 23 to Sep 20, zero-filled
    assert result.weeks[0] == VisitorWeek(date(2026, 6, 22), 3)
    assert result.weeks[-1] == VisitorWeek(date(2026, 9, 14), 3)
    assert len(result.weeks) == 13


def test_no_data_and_no_since_is_empty_not_an_error(session: Session) -> None:
    result = visitors(session, TZ, Span(None, date(2026, 9, 20)))
    assert (result.days, result.weeks, result.busiest) == ([], [], [])


def test_busiest_keeps_the_top_five_days_with_visits(session: Session) -> None:
    for day in range(1, 8):
        for n in range(day):
            _view(session, uuid.UUID(int=day * 100 + n), "home", "none",
                  datetime(2026, 9, day, 12, 0, tzinfo=PT))
    busiest = visitors(session, TZ, Span(date(2026, 9, 1), date(2026, 9, 10))).busiest
    assert [d.devices for d in busiest] == [7, 6, 5, 4, 3]


def test_page_kinds_merge_rollups_and_raw_in_the_span(session: Session) -> None:
    _seed(session)
    assert page_kinds(session, TZ, WEEK) == [
        PageKindViews("home", 3),
        PageKindViews("leaderboards", 1),
        PageKindViews("records", 1),
    ]
    assert page_kinds(session, TZ, Span(None, date(2026, 9, 20))) == [
        PageKindViews("home", 5),
        PageKindViews("leaderboards", 2),
        PageKindViews("records", 1),
    ]


def test_uptake_uses_each_devices_last_answer(session: Session) -> None:
    _seed(session)
    result = uptake(session, TZ, WEEK)
    assert result.weeks == [WeekMeStates(date(2026, 9, 14), 1, 1, 1)]
    assert result.latest == MeStates(picked=1, skipped=1, none=1)
    assert result.latest_since == date(2026, 9, 14)


def test_uptake_weeks_include_rollups_and_detail_starts_at_the_first_raw_day(
    session: Session,
) -> None:
    _seed(session)
    result = uptake(session, TZ, Span(date(2026, 6, 1), date(2026, 9, 20)))
    assert result.weeks[0] == WeekMeStates(date(2026, 6, 1), 0, 0, 0)
    assert WeekMeStates(date(2026, 6, 22), 0, 1, 2) in result.weeks
    assert result.latest_since == date(2026, 9, 14)
    assert result.latest == MeStates(picked=1, skipped=1, none=1)


def test_uptake_without_raw_rows_has_no_detail(session: Session) -> None:
    result = uptake(session, TZ, WEEK)
    assert result.latest == MeStates(0, 0, 0)
    assert result.latest_since is None
    assert result.weeks == [WeekMeStates(date(2026, 9, 14), 0, 0, 0)]


def test_uptake_with_raw_rows_only_after_the_span_has_no_detail(session: Session) -> None:
    _view(session, A, "home", "picked", datetime(2026, 9, 25, 9, 0, tzinfo=PT))
    assert uptake(session, TZ, WEEK).latest_since is None


def test_bumps_per_day_top_insights_and_devices(fx_session: Session) -> None:
    key, headline = fx_session.execute(select(Insight.key, Insight.headline).limit(1)).one()

    def bump(insight: str, device: uuid.UUID, at: datetime) -> None:
        fx_session.execute(
            insert(FistBump).values(insight_key=insight, device_id=device, created_at=at)
        )

    bump(key, A, datetime(2026, 9, 14, 12, 0, tzinfo=PT))
    bump(key, B, datetime(2026, 9, 16, 12, 0, tzinfo=PT))
    bump(GONE, A, datetime(2026, 9, 16, 13, 0, tzinfo=PT))
    bump(GONE, C, datetime(2026, 8, 1, 12, 0, tzinfo=PT))  # outside the week
    result = bumps(fx_session, TZ, WEEK)
    assert result.days[:3] == [
        BumpDay(date(2026, 9, 14), 1),
        BumpDay(date(2026, 9, 15), 0),
        BumpDay(date(2026, 9, 16), 2),
    ]
    assert len(result.days) == 7
    assert result.top == [TopInsight(key, plain(headline), 2), TopInsight(GONE, None, 1)]
    assert result.devices == 2
    assert result.devices_all_time == 3
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_site_analytics.py`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'sunday_clays.domain.site_analytics'`.

- [ ] **Step 3: Write the reads**

Create `backend/src/sunday_clays/domain/site_analytics.py`:

```python
"""Read side of the admin Analytics page (Plan 16): visitors, page kinds, fist bumps and "Which
one are you?" uptake over a span of the club's local days.

Each read merges the rollups with the raw page_views still kept. The two never overlap: the
rollup deletes the raw rows it counts, in whole weeks (domain/page_views.py). The sets are small
(one rollup row per day and week, raw rows for at most 96 days, one fist bump per insight and
device), so each read loads its buckets once and filters by the span in Python (Decision 10).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.templates import plain
from sunday_clays.domain.page_views import (
    Period,
    bucket_of,
    latest_states,
    local_midnight,
    state_counts,
)
from sunday_clays.models import FistBump, Insight, PageKindRollup, PageView, PageViewRollup

BUSIEST: Final = 5
TOP_INSIGHTS: Final = 10


@dataclass(frozen=True)
class Span:
    """Local days from ``since`` to ``as_of``; ``since`` None reaches back to the first data."""

    since: date | None
    as_of: date

    def has(self, day: date) -> bool:
        return (self.since is None or day >= self.since) and day <= self.as_of


@dataclass(frozen=True)
class VisitorDay:
    day: date
    devices: int


@dataclass(frozen=True)
class VisitorWeek:
    week: date
    devices: int


@dataclass(frozen=True)
class Visitors:
    days: list[VisitorDay]
    weeks: list[VisitorWeek]
    busiest: list[VisitorDay]


@dataclass(frozen=True)
class PageKindViews:
    page_kind: str
    views: int


@dataclass(frozen=True)
class BumpDay:
    day: date
    bumps: int


@dataclass(frozen=True)
class TopInsight:
    key: str
    headline: str | None  # None when the insight is no longer on the site
    bumps: int


@dataclass(frozen=True)
class Bumps:
    days: list[BumpDay]
    top: list[TopInsight]
    devices: int
    devices_all_time: int


@dataclass(frozen=True)
class MeStates:
    picked: int
    skipped: int
    none: int


@dataclass(frozen=True)
class WeekMeStates:
    week: date
    picked: int
    skipped: int
    none: int


@dataclass(frozen=True)
class Uptake:
    weeks: list[WeekMeStates]
    latest: MeStates
    latest_since: date | None


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _run(first: date | None, last: date, step_days: int) -> list[date]:
    """``first``, ``first + step``, … up to ``last``; empty when there is no start."""
    days: list[date] = []
    day = first
    while day is not None and day <= last:
        days.append(day)
        day += timedelta(days=step_days)
    return days


def _first(span: Span, days: Iterable[date]) -> date | None:
    """Where a zero-filled series starts: ``since``, else the first day with data up to as_of."""
    if span.since is not None:
        return span.since
    return min((day for day in days if day <= span.as_of), default=None)


def _weeks_from(first: date | None) -> date | None:
    return None if first is None else monday(first)


def _rolled_devices(session: Session, period: Period) -> dict[date, int]:
    rows = session.execute(
        select(PageViewRollup.start_day, PageViewRollup.devices).where(
            PageViewRollup.period == period
        )
    )
    return {start: devices for start, devices in rows}


def _raw_devices(session: Session, tz: str, period: Period) -> dict[date, int]:
    raw = select(bucket_of(period, tz).label("bucket"), PageView.device_id).subquery()
    rows = session.execute(
        select(raw.c.bucket, func.count(func.distinct(raw.c.device_id))).group_by(raw.c.bucket)
    )
    return {bucket: devices for bucket, devices in rows}


def visitors(session: Session, tz: str, span: Span) -> Visitors:
    by_day = _rolled_devices(session, "day") | _raw_devices(session, tz, "day")
    by_week = _rolled_devices(session, "week") | _raw_devices(session, tz, "week")
    first = _first(span, by_day)
    days = [VisitorDay(day, by_day.get(day, 0)) for day in _run(first, span.as_of, 1)]
    weeks = [
        VisitorWeek(week, by_week.get(week, 0))
        for week in _run(_weeks_from(first), span.as_of, 7)
    ]
    busiest = sorted(
        (day for day in days if day.devices > 0),
        key=lambda d: (-d.devices, -d.day.toordinal()),
    )[:BUSIEST]
    return Visitors(days, weeks, busiest)


def page_kinds(session: Session, tz: str, span: Span) -> list[PageKindViews]:
    raw = select(bucket_of("day", tz).label("day"), PageView.page_kind).subquery()
    raw_counts = select(raw.c.day, raw.c.page_kind, func.count()).group_by(
        raw.c.day, raw.c.page_kind
    )
    rolled = select(PageKindRollup.day, PageKindRollup.page_kind, PageKindRollup.views)
    totals: Counter[str] = Counter()
    for day, kind, views in [*session.execute(raw_counts), *session.execute(rolled)]:
        if span.has(day):
            totals[kind] += views
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [PageKindViews(kind, views) for kind, views in ranked]


def bumps(session: Session, tz: str, span: Span) -> Bumps:
    local_day = cast(func.timezone(tz, FistBump.created_at), Date)
    rows = [
        (day, key, device)
        for day, key, device in session.execute(
            select(local_day, FistBump.insight_key, FistBump.device_id)
        )
        if span.has(day)
    ]
    per_day = Counter(day for day, _, _ in rows)
    days = [BumpDay(day, per_day.get(day, 0)) for day in _run(_first(span, per_day), span.as_of, 1)]
    ranked = sorted(Counter(key for _, key, _ in rows).items(), key=lambda kv: (-kv[1], kv[0]))
    ranked = ranked[:TOP_INSIGHTS]
    headlines: dict[str, str] = {}
    if ranked:
        found = session.execute(
            select(Insight.key, Insight.headline).where(Insight.key.in_([k for k, _ in ranked]))
        )
        headlines = {key: plain(headline) for key, headline in found}
    all_time = session.scalar(select(func.count(func.distinct(FistBump.device_id)))) or 0
    return Bumps(
        days=days,
        top=[TopInsight(key, headlines.get(key), n) for key, n in ranked],
        devices=len({device for _, _, device in rows}),
        devices_all_time=all_time,
    )


def uptake(session: Session, tz: str, span: Span) -> Uptake:
    rolled = {
        start: (picked, skipped, none)
        for start, picked, skipped, none in session.execute(
            select(
                PageViewRollup.start_day,
                PageViewRollup.me_picked,
                PageViewRollup.me_skipped,
                PageViewRollup.me_none,
            ).where(PageViewRollup.period == "week")
        )
    }
    per_week = latest_states(tz, "week")
    raw = {
        week: (picked, skipped, none)
        for week, _, picked, skipped, none in session.execute(
            select(per_week.c.bucket, *state_counts(per_week)).group_by(per_week.c.bucket)
        )
    }
    by_week = rolled | raw
    weeks = [
        WeekMeStates(week, *by_week.get(week, (0, 0, 0)))
        for week in _run(_weeks_from(_first(span, by_week)), span.as_of, 7)
    ]
    nothing = Uptake(weeks, MeStates(0, 0, 0), None)
    first_raw = session.scalar(select(func.min(PageView.at)))
    if first_raw is None:
        return nothing
    kept_since = first_raw.astimezone(ZoneInfo(tz)).date()
    since = kept_since if span.since is None else max(span.since, kept_since)
    if since > span.as_of:
        return nothing
    latest = latest_states(
        tz,
        None,
        PageView.at >= local_midnight(since, tz),
        PageView.at < local_midnight(span.as_of + timedelta(days=1), tz),
    )
    _, picked, skipped, none = session.execute(select(*state_counts(latest))).one()
    return Uptake(weeks, MeStates(picked, skipped, none), since)
```

(`_first(span, by_week)` with no `since` starts at the first week that has data. `_weeks_from` then keeps it on that Monday.)

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_site_analytics.py`
Expected: PASS (12 passed).

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/integration/api/test_admin_analytics_api.py`:

```python
"""/api/admin/analytics/* (Plan 16 Task 2): admin-only, read-only, no-store, windowed."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.models import Base, PageView

PATHS = ("visitors", "pages", "bumps", "me-states")
PT = ZoneInfo("America/Los_Angeles")
A = uuid.UUID("00000000-0000-4000-8000-00000000000a")


@pytest.mark.parametrize("path", PATHS)
def test_admin_only_and_never_cached(
    path: str, admin_client: TestClient, viewer_client: TestClient
) -> None:
    response = admin_client.get(f"/api/admin/analytics/{path}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    refused = viewer_client.get(f"/api/admin/analytics/{path}")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("path", PATHS)
def test_a_since_after_as_of_is_400(path: str, admin_client: TestClient) -> None:
    response = admin_client.get(
        f"/api/admin/analytics/{path}", params={"since": "2026-09-21", "as_of": "2026-09-20"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_range"


def test_as_of_defaults_to_today_in_the_club_timezone(
    admin_client: TestClient, auth_env: Settings
) -> None:
    today = datetime.now(ZoneInfo(auth_env.timezone)).date()
    since = (today - timedelta(days=2)).isoformat()
    days = admin_client.get("/api/admin/analytics/visitors", params={"since": since}).json()["days"]
    assert [d["day"] for d in days] == [
        (today - timedelta(days=n)).isoformat() for n in (2, 1, 0)
    ]


def test_the_four_answers_have_the_documented_shape(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(
        insert(PageView).values(
            device_id=A, page_kind="profile", me_state="picked",
            at=datetime(2026, 9, 14, 10, 0, tzinfo=PT),
        )
    )
    window = {"since": "2026-09-14", "as_of": "2026-09-20"}
    visitors = admin_client.get("/api/admin/analytics/visitors", params=window).json()
    assert visitors["days"][0] == {"day": "2026-09-14", "devices": 1}
    assert visitors["weeks"] == [{"week": "2026-09-14", "devices": 1}]
    assert visitors["busiest"] == [{"day": "2026-09-14", "devices": 1}]
    pages = admin_client.get("/api/admin/analytics/pages", params=window).json()
    assert pages == [{"page_kind": "profile", "views": 1}]
    bumps = admin_client.get("/api/admin/analytics/bumps", params=window).json()
    assert bumps["top"] == []
    assert (bumps["devices"], bumps["devices_all_time"]) == (0, 0)
    assert len(bumps["days"]) == 7
    states = admin_client.get("/api/admin/analytics/me-states", params=window).json()
    assert states == {
        "weeks": [{"week": "2026-09-14", "picked": 1, "skipped": 0, "none": 0}],
        "latest": {"picked": 1, "skipped": 0, "none": 0},
        "latest_since": "2026-09-14",
    }


def test_reading_analytics_writes_nothing(admin_client: TestClient, session: Session) -> None:
    audit = Base.metadata.tables["audit_log"]
    before = session.scalar(select(func.count()).select_from(audit))  # the login's own entry
    for path in PATHS:
        assert admin_client.get(f"/api/admin/analytics/{path}").status_code == 200
    assert session.scalar(select(func.count()).select_from(audit)) == before
    assert session.scalar(select(func.count()).select_from(PageView)) == 0
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_admin_analytics_api.py`
Expected: FAIL. Every path is 404.

- [ ] **Step 7: Write the router**

Create `backend/src/sunday_clays/api/routes/admin_analytics.py`:

```python
"""Admin Analytics (Plan 16): read-only site usage for the admin page.

Admin-only by discovery (``admin_*``), never ETagged or stored (``/api/admin/`` in api/etag.py).
Nothing here mutates, so nothing is audited.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, NamedTuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sunday_clays.api.routes._filters import check_window
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain import site_analytics as usage
from sunday_clays.domain.site_analytics import Span

router = APIRouter(prefix="/api/admin/analytics", tags=["admin"])


class Window(NamedTuple):
    tz: str
    span: Span


def analytics_window(
    settings: Annotated[Settings, Depends(get_settings)],
    since: date | None = None,
    as_of: date | None = None,
) -> Window:
    """``as_of`` defaults to today in the club's timezone; no ``since`` means from the first data."""
    end = as_of if as_of is not None else datetime.now(ZoneInfo(settings.timezone)).date()
    check_window(since, end)
    return Window(settings.timezone, Span(since, end))


WindowDep = Annotated[Window, Depends(analytics_window)]


class VisitorDayOut(BaseModel):
    day: date
    devices: int


class VisitorWeekOut(BaseModel):
    week: date
    devices: int


class VisitorsOut(BaseModel):
    days: list[VisitorDayOut]
    weeks: list[VisitorWeekOut]
    busiest: list[VisitorDayOut]


class PageKindViewsOut(BaseModel):
    page_kind: str
    views: int


class BumpDayOut(BaseModel):
    day: date
    bumps: int


class TopInsightOut(BaseModel):
    key: str
    headline: str | None
    bumps: int


class BumpsOut(BaseModel):
    days: list[BumpDayOut]
    top: list[TopInsightOut]
    devices: int
    devices_all_time: int


class MeStatesOut(BaseModel):
    picked: int
    skipped: int
    none: int


class WeekMeStatesOut(MeStatesOut):
    week: date


class UptakeOut(BaseModel):
    weeks: list[WeekMeStatesOut]
    latest: MeStatesOut
    latest_since: date | None


@router.get("/visitors")
def visitors(session: SessionDep, window: WindowDep) -> VisitorsOut:
    result = usage.visitors(session, window.tz, window.span)
    return VisitorsOut(
        days=[VisitorDayOut(day=d.day, devices=d.devices) for d in result.days],
        weeks=[VisitorWeekOut(week=w.week, devices=w.devices) for w in result.weeks],
        busiest=[VisitorDayOut(day=d.day, devices=d.devices) for d in result.busiest],
    )


@router.get("/pages")
def pages(session: SessionDep, window: WindowDep) -> list[PageKindViewsOut]:
    return [
        PageKindViewsOut(page_kind=k.page_kind, views=k.views)
        for k in usage.page_kinds(session, window.tz, window.span)
    ]


@router.get("/bumps")
def bumps(session: SessionDep, window: WindowDep) -> BumpsOut:
    result = usage.bumps(session, window.tz, window.span)
    return BumpsOut(
        days=[BumpDayOut(day=d.day, bumps=d.bumps) for d in result.days],
        top=[TopInsightOut(key=t.key, headline=t.headline, bumps=t.bumps) for t in result.top],
        devices=result.devices,
        devices_all_time=result.devices_all_time,
    )


@router.get("/me-states")
def me_states(session: SessionDep, window: WindowDep) -> UptakeOut:
    result = usage.uptake(session, window.tz, window.span)
    latest = result.latest
    return UptakeOut(
        weeks=[
            WeekMeStatesOut(week=w.week, picked=w.picked, skipped=w.skipped, none=w.none)
            for w in result.weeks
        ],
        latest=MeStatesOut(picked=latest.picked, skipped=latest.skipped, none=latest.none),
        latest_since=result.latest_since,
    )
```

- [ ] **Step 8: Run the API, auth-matrix and discovery tests**

Run: `cd backend && uv run pytest -q tests/integration/api/test_admin_analytics_api.py tests/integration/api/test_route_auth_matrix.py tests/unit/api/test_routes_discovery.py tests/unit/api/test_export_openapi.py`
Expected: PASS. The matrix walks the four routes and gets 401 without a session.

- [ ] **Step 9: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: everything clean and green, with coverage at or above 90% lines and branches. Run `uv run ruff format .` first if the formatter wants to rewrap the seed dicts in the tests.

- [ ] **Step 10: Commit**

```bash
git add backend/src/sunday_clays/domain/site_analytics.py backend/src/sunday_clays/api/routes/admin_analytics.py backend/tests/integration/domain/test_site_analytics.py backend/tests/integration/api/test_admin_analytics_api.py
git commit -m "feat(analytics): admin analytics API for visitors, page kinds, bumps and uptake (Plan 16 T2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The page-view beacon

**Files:**
- Create: `frontend/src/features/pageviews/pageKind.ts`, `pageKind.test.ts`
- Create: `frontend/src/features/pageviews/beacon.ts`, `beacon.test.tsx`
- Create: `frontend/src/features/pageviews/mocks.ts`
- Modify: `frontend/src/features/auth/components/SessionShell.tsx`, `SessionShell.test.tsx`

**Interfaces:**
- Consumes: T1's `components['schemas']['PageViewIn']` (via `pnpm gen:api`); `lib/device.getDeviceId()`; `lib/me.getMe()`, `isMeSkipped()`; `features/auth/api.Role`, `useSession`.
- Produces: `pageKind(pathname: string): PageKind`, `PageKind`, `meState(): MeState`, `sendPageView(view: PageView): void`, `usePageViewBeacon(role: Role | null): void`, `PAGE_VIEWS_PATH = '/api/pageviews'`, and a default MSW handler that answers 204.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/features/pageviews/pageKind.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { pageKind } from './pageKind';

describe('pageKind', () => {
  it.each([
    ['/', 'home'],
    ['/shooters/3', 'profile'],
    ['/shooters/3/', 'profile'],
    ['/shooters', 'other'],
    ['/events', 'events-list'],
    ['/events/2026-09-27', 'event'],
    ['/leaderboards', 'leaderboards'],
    ['/records', 'records'],
    ['/club', 'club'],
    ['/stations', 'stations'],
    ['/weather', 'weather'],
    ['/yir', 'yir'],
    ['/yir/2025/shooters/3', 'yir'],
    ['/explorer', 'explorer'],
    ['/achievements/first_25', 'achievements'],
    ['/race', 'race'],
    ['/compare', 'compare'],
    ['/admin/analytics', 'admin'],
    ['/login', 'other'],
    ['/constructor', 'other'],
    ['/no-such-page', 'other'],
  ])('%s is %s', (path, kind) => {
    expect(pageKind(path)).toBe(kind);
  });

  it('never carries an id or a path', () => {
    for (const path of ['/shooters/3', '/events/2026-09-27', '/yir/2025/shooters/3']) {
      expect(pageKind(path)).not.toMatch(/\d|\//);
    }
  });
});
```

Create `frontend/src/features/pageviews/beacon.test.tsx`:

```tsx
import { act, render, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resetMeForTests, setMe, skipMe } from '../../lib/me';
import { meState, PAGE_VIEWS_PATH, sendPageView, usePageViewBeacon } from './beacon';

const DEVICE = '11111111-2222-4333-8444-555555555555';
const VIEW = { device_id: DEVICE, page_kind: 'home', me_state: 'none', at: '2026-10-01T18:00:00.000Z' } as const;

afterEach(() => {
  // lib/me keeps an in-memory skip (fix/15-final): reset it so no state leaks between tests.
  resetMeForTests();
  localStorage.clear();
});

function at(path: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
}

describe('meState', () => {
  it('is none, then skipped, then picked, and never a name', () => {
    expect(meState()).toBe('none');
    skipMe();
    expect(meState()).toBe('skipped');
    setMe(3);
    expect(meState()).toBe('picked');
  });
});

describe('sendPageView', () => {
  it('posts the JSON same-origin with keepalive and returns at once', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => undefined));
    expect(sendPageView(VIEW)).toBeUndefined(); // never awaited: the fetch never settles here
    expect(fetchSpy).toHaveBeenCalledWith(PAGE_VIEWS_PATH, {
      method: 'POST',
      keepalive: true,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(VIEW),
    });
  });

  it('swallows a rejected fetch (offline, blocked)', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    sendPageView(VIEW);
    await Promise.resolve(); // an unhandled rejection would fail the run
  });

  it('swallows a fetch that throws synchronously', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => {
      throw new TypeError('no fetch');
    });
    expect(() => sendPageView(VIEW)).not.toThrow();
  });
});

describe('usePageViewBeacon', () => {
  function spyFetch() {
    return vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 204 }));
  }

  it('sends the kind, the state and this browser’s device id for a viewer', async () => {
    localStorage.setItem('sc.device', DEVICE);
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon('viewer'), { wrapper: at('/shooters/3?w=12m') });
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(1));
    const body = JSON.parse(String(fetchSpy.mock.calls[0]?.[1]?.body)) as Record<string, string>;
    expect(Object.keys(body).sort()).toEqual(['at', 'device_id', 'me_state', 'page_kind']);
    expect(body).toMatchObject({ device_id: DEVICE, page_kind: 'profile', me_state: 'none' });
    expect(JSON.stringify(body)).not.toContain('shooters');
  });

  it('sends one beacon per pathname and none for a query-only change', async () => {
    // A synchronous fetch spy: each call is recorded the moment the effect runs, so an extra
    // beacon for `?w=12m` cannot arrive after the assertion (kills keying the effect on search).
    localStorage.setItem('sc.device', DEVICE);
    const fetchSpy = spyFetch();
    function Probe() {
      usePageViewBeacon('viewer');
      return null;
    }
    const router = createMemoryRouter([{ path: '*', element: <Probe /> }], {
      initialEntries: ['/shooters/3'],
    });
    render(<RouterProvider router={router} />);
    await act(() => router.navigate('/shooters/3?w=12m'));
    await act(() => router.navigate('/'));
    const kinds = fetchSpy.mock.calls.map(
      (call) => (JSON.parse(String(call[1]?.body)) as { page_kind: string }).page_kind,
    );
    expect(kinds).toEqual(['profile', 'home']);
  });

  it('sends nothing for an admin session or without a session', () => {
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon('admin'), { wrapper: at('/') });
    renderHook(() => usePageViewBeacon(null), { wrapper: at('/') });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('sends nothing when the browser cannot keep a device id', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    const fetchSpy = spyFetch();
    renderHook(() => usePageViewBeacon('viewer'), { wrapper: at('/') });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
```

In `frontend/src/features/auth/components/SessionShell.test.tsx`, add `act` and `waitFor` to the `@testing-library/react` import (replace `import { screen } from '@testing-library/react';` with `import { act, screen, waitFor } from '@testing-library/react';`), add `import { resetMeForTests } from '../../../lib/me';` just before `import { server } from '../../../test/msw/server';`, and append at the end of the file:

```tsx
const PAGE_ROUTES = [
  {
    path: '/',
    element: (
      <RequireRole>
        <SessionShell />
      </RequireRole>
    ),
    children: [
      { index: true, element: <p>home page</p> },
      { path: 'shooters/:id', element: <p>profile page</p> },
    ],
  },
];

describe('SessionShell page views', () => {
  function capture(): unknown[] {
    const sent: unknown[] = [];
    server.use(
      http.post('*/api/pageviews', async ({ request }) => {
        sent.push(await request.json());
        return new HttpResponse(null, { status: 204 });
      }),
    );
    return sent;
  }

  afterEach(() => {
    resetMeForTests();
    localStorage.clear();
  });

  it('sends one beacon per page for a viewer and none for a query-only change', async () => {
    stubViewport('desktop');
    const sent = capture();
    const kinds = () => sent.map((b) => (b as { page_kind: string }).page_kind);
    const { router } = renderRoutes(PAGE_ROUTES, { route: '/', role: 'viewer' });
    await waitFor(() => expect(sent).toHaveLength(1));
    await act(() => router.navigate('/shooters/3'));
    await waitFor(() => expect(sent).toHaveLength(2));
    await act(() => router.navigate('/shooters/3?w=12m'));
    // Then a real page change: its beacon is pushed after any stray one for the query change
    // (the handler pushes in order), so waiting for it proves no beacon was sent for `?w=12m`.
    await act(() => router.navigate('/'));
    await waitFor(() => expect(sent.length).toBeGreaterThanOrEqual(3));
    expect(kinds()).toEqual(['home', 'profile', 'home']);
  });

  it('sends nothing for an admin session', async () => {
    stubViewport('desktop');
    const sent = capture();
    renderRoutes(PAGE_ROUTES, { route: '/', role: 'admin' });
    await screen.findByText('home page');
    expect(sent).toEqual([]);
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && pnpm gen:api && pnpm exec vitest run src/features/pageviews src/features/auth/components/SessionShell.test.tsx`
Expected: FAIL. `pageKind.test.ts` and `beacon.test.tsx` fail to resolve `./pageKind` and `./beacon`. The two new `SessionShell` tests time out waiting for a beacon, or record none for the viewer. After Step 3, a reviewer can mutate the hook's deps to `[pathname, search, role]` (with `search` from `useLocation`) and see both query-only tests fail: `['profile', 'profile', 'home']` and `['home', 'profile', 'profile', 'home']`.

- [ ] **Step 3: Write the kind mapping, the beacon and the mock**

Create `frontend/src/features/pageviews/pageKind.ts`:

```ts
import type { components } from '../../api/schema';

export type PageKind = components['schemas']['PageViewIn']['page_kind'];

/** First path segment → kind, for pages whose deeper levels do not matter. */
const BY_SEGMENT = new Map<string, PageKind>([
  ['leaderboards', 'leaderboards'],
  ['records', 'records'],
  ['club', 'club'],
  ['stations', 'stations'],
  ['weather', 'weather'],
  ['yir', 'yir'],
  ['explorer', 'explorer'],
  ['achievements', 'achievements'],
  ['race', 'race'],
  ['compare', 'compare'],
  ['admin', 'admin'],
]);

/**
 * The coarse category of a path (Plan 16). Never the URL and never an id: every profile is
 * "profile" and every Sunday's page is "event". The Shooters list is "other" (Decision 17).
 */
export function pageKind(pathname: string): PageKind {
  const [first, second] = pathname.split('/').filter(Boolean);
  if (first === undefined) return 'home';
  if (first === 'events') return second === undefined ? 'events-list' : 'event';
  if (first === 'shooters') return second === undefined ? 'other' : 'profile';
  return BY_SEGMENT.get(first) ?? 'other';
}
```

Create `frontend/src/features/pageviews/beacon.ts`:

```ts
import { useEffect } from 'react';
import { useLocation } from 'react-router';
import type { components } from '../../api/schema';
import { getDeviceId } from '../../lib/device';
import { getMe, isMeSkipped } from '../../lib/me';
import type { Role } from '../auth/api';
import { pageKind } from './pageKind';

export type PageView = components['schemas']['PageViewIn'];
export type MeState = PageView['me_state'];

export const PAGE_VIEWS_PATH = '/api/pageviews';

/** "Which one are you?" as a state, never the name: picked, skipped or not answered yet. */
export function meState(): MeState {
  if (getMe() !== null) return 'picked';
  return isMeSkipped() ? 'skipped' : 'none';
}

/**
 * Fire-and-forget POST of one page view. Same-origin (CSP connect-src 'self'), keepalive so it
 * outlives the page, and never awaited. It never throws and never redirects to the login page:
 * the openapi client would on a 401 (Decision 15).
 */
export function sendPageView(view: PageView): void {
  try {
    void globalThis
      .fetch(PAGE_VIEWS_PATH, {
        method: 'POST',
        keepalive: true,
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(view),
      })
      .catch(() => undefined);
  } catch {
    // fetch itself threw: page views are best-effort.
  }
}

/**
 * One page view per client-side page change (the pathname, not the query string), sent after
 * paint. Admin sessions and browsers that cannot keep a device id send nothing; the server also
 * drops admin views, and dedupes a device on a kind for 30 minutes.
 */
export function usePageViewBeacon(role: Role | null): void {
  const { pathname } = useLocation();
  useEffect(() => {
    if (role !== 'viewer') return;
    const deviceId = getDeviceId();
    if (deviceId === null) return;
    sendPageView({
      device_id: deviceId,
      page_kind: pageKind(pathname),
      me_state: meState(),
      at: new Date().toISOString(),
    });
  }, [pathname, role]);
}
```

Create `frontend/src/features/pageviews/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';

/** Every page view is accepted (204). Tests that inspect beacons override this with server.use. */
export const handlers = [http.post('*/api/pageviews', () => new HttpResponse(null, { status: 204 }))];
```

- [ ] **Step 4: Wire the hook into SessionShell**

In `frontend/src/features/auth/components/SessionShell.tsx`, replace

```tsx
import { AppShell } from '../../../components/layout/AppShell';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/** The AppShell layout for the signed-in session (rendered inside RequireRole). */
export function SessionShell() {
  const { session } = useSession();
  const role = session?.role ?? 'viewer';
```

with

```tsx
import { AppShell } from '../../../components/layout/AppShell';
import { usePageViewBeacon } from '../../pageviews/beacon';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/**
 * The AppShell layout for the signed-in session (rendered inside RequireRole). It also sends the
 * anonymous page-view beacon on every page change (Plan 16; router.tsx is closed to edits).
 */
export function SessionShell() {
  const { session } = useSession();
  usePageViewBeacon(session?.role ?? null);
  const role = session?.role ?? 'viewer';
```

- [ ] **Step 5: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/pageviews src/features/auth`
Expected: PASS. The existing `SessionShell` tests still pass, because the default `pageviews` mock answers 204.

- [ ] **Step 6: Gates, the whole unit suite with coverage, and the e2e suite**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage`
Expected: clean, all green, and coverage at or above 90% lines and branches. Then build the stack from this branch (see "Running the e2e stack") and run the full `pnpm exec playwright test`. Expected: green. No spec breaks, because every beacon is answered 204 by T1's endpoint, and `fixtures.ts` fails a test on any CSP violation.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/pageviews/pageKind.ts frontend/src/features/pageviews/pageKind.test.ts frontend/src/features/pageviews/beacon.ts frontend/src/features/pageviews/beacon.test.tsx frontend/src/features/pageviews/mocks.ts frontend/src/features/auth/components/SessionShell.tsx frontend/src/features/auth/components/SessionShell.test.tsx
git commit -m "feat(analytics): fire-and-forget page-view beacon on every page change (Plan 16 T3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The admin Analytics page, and the e2e at both viewports

**Files:**
- Create: `frontend/src/features/admin-analytics/routes.tsx`, `routes.test.tsx`
- Create: `frontend/src/features/admin-analytics/api.ts`, `api.test.tsx`
- Create: `frontend/src/features/admin-analytics/mocks.ts`
- Create: `frontend/src/features/admin-analytics/models.ts`, `models.test.ts`
- Create: `frontend/src/features/admin-analytics/explainers.ts`, `explainers.test.ts`
- Create: `frontend/src/features/admin-analytics/components/VisitorsCard.tsx`, `PageKindsCard.tsx`, `BumpsCard.tsx`, `UptakeCard.tsx`, `cards.test.tsx`
- Create: `frontend/src/features/admin-analytics/pages/AnalyticsPage.tsx`, `AnalyticsPage.test.tsx`
- Modify: `frontend/src/app/navRegistry.test.ts`
- Create: `frontend/e2e/admin-analytics.spec.ts`

**Interfaces:**
- Consumes: T2's OpenAPI paths `/api/admin/analytics/{visitors,pages,bumps,me-states}`; `ChartFrame` (`fullQuery`, `controls`, `explainer`); `barOption`; `Card`, `Chip`, `Skeleton`, `EmptyState`; `AdminError`; `JsonOf`; `useWindowChoice`, `windowRange`, `windowTagText`; `formatDate`; `RequireRole`; and the test helpers `expectChartControls`, `expectExplainer`, `openFullscreen`, `captureCsv`, `chartOptionIn`, `LAZY_CHART`, `LAZY_TEST_TIMEOUT`, `renderRoutes`, `renderWithProviders`.
- Produces: the route `/admin/analytics`; the nav item `Analytics` (order 930, adminOnly); `useAnalyticsRange()`, `todayIso()`, `allTime(asOf)`; the four cards; the explainers `visitors`, `pages`, `bumps`, `uptake`.

- [ ] **Step 1: Write the failing unit tests**

Create `frontend/src/features/admin-analytics/models.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { bumps, pageKinds, uptake, visitors } from './mocks';
import { bumpsModel, pageKindLabel, pageKindsModel, uptakeModel, visitorsModel } from './models';

type Series = { name: string; stack?: string; data: (number | null)[] };

describe('analytics chart models', () => {
  it('charts visitors per day or per week', () => {
    const day = visitorsModel(visitors, 'day');
    expect(day.columns.map((c) => c.label)).toEqual(['Day', 'Devices']);
    expect(day.rows[0]).toEqual({ day: '2026-09-27', devices: 14 });
    const week = visitorsModel(visitors, 'week');
    expect(week.columns.map((c) => c.label)).toEqual(['Week of', 'Devices']);
    expect(week.rows).toEqual([
      { week: '2026-09-21', devices: 18 },
      { week: '2026-09-28', devices: 7 },
    ]);
  });

  it('names page kinds in plain words and never says "event"', () => {
    expect(pageKindLabel('event')).toBe('One Sunday');
    expect(pageKindLabel('events-list')).toBe('Sundays list');
    expect(pageKindLabel('profile')).toBe('Shooter profiles');
    expect(pageKindLabel('brand-new-kind')).toBe('brand-new-kind');
    const model = pageKindsModel(pageKinds);
    expect(model.rows.map((r) => r.page)).toEqual([
      'Home',
      'Shooter profiles',
      'One Sunday',
      'Leaderboards',
    ]);
    expect(JSON.stringify(model.rows)).not.toMatch(/\bevents?\b/i);
  });

  it('charts bumps per day', () => {
    expect(bumpsModel(bumps).rows).toEqual(bumps.days.map((d) => ({ day: d.day, bumps: d.bumps })));
  });

  it('stacks the three answers per week', () => {
    const model = uptakeModel(uptake);
    const series = model.option.series as Series[];
    expect(series.map((s) => s.name)).toEqual(['Picked a name', 'Skipped', 'Not answered']);
    expect(series.every((s) => s.stack === 'total')).toBe(true);
    expect(series[0]?.data).toEqual([9, 4]);
  });
});
```

Create `frontend/src/features/admin-analytics/api.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../test/render';
import { allTime, todayIso, useAnalyticsRange, useVisitors } from './api';
import { visitors } from './mocks';

afterEach(() => {
  vi.useRealTimers();
});

function at(path: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
}

describe('analytics range', () => {
  it('is today in the browser’s calendar', () => {
    expect(todayIso(new Date(2026, 9, 1, 23, 59))).toBe('2026-10-01');
    expect(todayIso(new Date(2026, 0, 5, 0, 0))).toBe('2026-01-05');
  });

  it('follows the header window, anchored at today (default 8 weeks)', () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 9, 1, 12, 0));
    const { result } = renderHook(() => useAnalyticsRange(), { wrapper: at('/admin/analytics') });
    expect(result.current.range).toEqual({ since: '2026-08-07', asOf: '2026-10-01' });
    expect(result.current.tag).toBe('Last 8 weeks · Aug 7 – Oct 1');
    const all = renderHook(() => useAnalyticsRange(), { wrapper: at('/admin/analytics?w=all') });
    expect(all.result.current.range).toEqual({ since: null, asOf: '2026-10-01' });
  });

  it('sends since and as_of, and leaves since out for all time', async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('*/api/admin/analytics/visitors', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json(visitors);
      }),
    );
    const queryClient = createTestQueryClient();
    function Probe({ all }: { all: boolean }) {
      useVisitors(all ? allTime('2026-10-01') : { since: '2026-08-07', asOf: '2026-10-01' });
      return null;
    }
    renderWithProviders(<Probe all={false} />, { queryClient });
    renderWithProviders(<Probe all />, { queryClient });
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(seen.map((p) => [p.get('since'), p.get('as_of')])).toEqual(
      expect.arrayContaining([
        ['2026-08-07', '2026-10-01'],
        [null, '2026-10-01'],
      ]),
    );
  });
});
```

Create `frontend/src/features/admin-analytics/explainers.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { analyticsExplainers } from './explainers';

const sources = import.meta.glob(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

function texts(): [string, string][] {
  return Object.entries(analyticsExplainers).flatMap(([key, e]) => [
    [key, e.what] as [string, string],
    ...(e.read ?? []).map((t): [string, string] => [key, t]),
    ...e.computed.map((t): [string, string] => [key, t]),
  ]);
}

describe('analytics explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature, and uses every entry', () => {
    const keys = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/urlKey="([^"]+)"/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(keys)).toEqual(new Set(['visitors', 'pages', 'bumps', 'uptake']));
    const wired = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/analyticsExplainers\.(\w+)/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(wired)).toEqual(new Set(Object.keys(analyticsExplainers)));
  });

  it('says fullscreen and the CSV cover everything on record', () => {
    for (const [key, e] of Object.entries(analyticsExplainers)) {
      expect(e.read?.join(' '), key).toMatch(/Fullscreen and the CSV download cover every/);
    }
  });

  it('uses neutral pronouns, says Sunday and never says class', () => {
    for (const [key, text] of texts()) {
      expect(text, key).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
      expect(text, key).not.toMatch(/\bclass(es)?\b/i);
      expect(text, key).not.toMatch(/\bevents?\b/i);
    }
  });

  it('keeps each explainer short', () => {
    const totals = new Map<string, number>();
    for (const [key, text] of texts()) {
      totals.set(key, (totals.get(key) ?? 0) + text.split(/\s+/).length);
    }
    for (const [key, words] of totals) expect(words, key).toBeLessThanOrEqual(95);
  });
});
```

Create `frontend/src/features/admin-analytics/components/cards.test.tsx`:

```tsx
import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { AnalyticsRange } from '../api';
import { bumps, uptake, visitors } from '../mocks';
import { BumpsCard } from './BumpsCard';
import { PageKindsCard } from './PageKindsCard';
import { UptakeCard } from './UptakeCard';
import { VisitorsCard } from './VisitorsCard';

const RANGE: AnalyticsRange = { since: '2026-08-07', asOf: '2026-10-01' };

afterEach(() => {
  vi.restoreAllMocks();
});

async function region(name: string): Promise<HTMLElement> {
  return screen.findByRole('region', { name }, LAZY_CHART);
}

describe('VisitorsCard', () => {
  it(
    'charts devices per day with Table, CSV, fullscreen and an explainer, and lists the busiest days',
    async () => {
      renderWithProviders(<VisitorsCard range={RANGE} />);
      const card = await region('Visitors');
      expectChartControls(card);
      expect(within(card).getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
      await expectExplainer(card, 'About this chart', { read: true });
      const busiest = screen.getByRole('list', { name: 'Busiest days' });
      expect(within(busiest).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
        'Sep 27, 202614 devices',
        'Sep 30, 20264 devices',
        'Sep 28, 20263 devices',
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'switches to weeks',
    async () => {
      const { user } = renderWithProviders(<VisitorsCard range={RANGE} />);
      const card = await region('Visitors');
      await user.click(within(card).getByRole('button', { name: 'Per week' }));
      expect(within(card).getByRole('button', { name: 'Per week' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      await user.click(within(card).getByRole('button', { name: 'Table' }));
      expect(within(card).getByRole('columnheader', { name: 'Week of' })).toBeInTheDocument();
      expect(within(card).getAllByRole('row')).toHaveLength(3);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'opens fullscreen and downloads the CSV from all time (no since)',
    async () => {
      const seen: (string | null)[] = [];
      server.use(
        http.get('*/api/admin/analytics/visitors', ({ request }) => {
          seen.push(new URL(request.url).searchParams.get('since'));
          return HttpResponse.json(visitors);
        }),
      );
      const csv = captureCsv();
      const { user } = renderWithProviders(<VisitorsCard range={RANGE} />);
      const card = await region('Visitors');
      const dialog = await openFullscreen(user, card, 'Visitors');
      expect(await within(dialog).findByText('Every day on record.')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toEqual(['visitors-day-2026-10-01.csv']));
      expect(seen).toEqual(['2026-08-07', null]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says why when the server refuses', async () => {
    server.use(
      http.get('*/api/admin/analytics/visitors', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Admin access required' } }, { status: 403 }),
      ),
    );
    renderWithProviders(<VisitorsCard range={RANGE} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Admins only');
  });

  it('shows an empty state when nothing was counted', async () => {
    server.use(
      http.get('*/api/admin/analytics/visitors', () =>
        HttpResponse.json({ days: [], weeks: [], busiest: [] }),
      ),
    );
    renderWithProviders(<VisitorsCard range={{ since: null, asOf: '2026-10-01' }} />);
    expect(await screen.findByText('Nothing counted in this window yet.')).toBeInTheDocument();
  });
});

describe('PageKindsCard', () => {
  it(
    'charts views per page kind in plain words',
    async () => {
      renderWithProviders(<PageKindsCard range={RANGE} />);
      const card = await region('Page views by page');
      expectChartControls(card);
      await expectExplainer(card, 'About this chart', { read: true });
      const option = chartOptionIn(card, 'Page views by page');
      expect((option.yAxis as { data: string[] }[])[0]?.data).toEqual([
        'Home',
        'Shooter profiles',
        'One Sunday',
        'Leaderboards',
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );
});

describe('BumpsCard', () => {
  it(
    'charts bumps per day, says how many devices bumped and lists the most-bumped insights',
    async () => {
      renderWithProviders(<BumpsCard range={RANGE} />);
      const card = await region('Fist bumps per day');
      expectChartControls(card);
      await expectExplainer(card, 'About this chart', { read: true });
      expect(within(card).getByText('8 devices bumped in this window · 12 all time')).toBeVisible();
      const top = screen.getByRole('list', { name: 'Most-bumped insights' });
      expect(within(top).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
        'Ike Hadley broke 45 for the first time6 bumps',
        'An insight no longer on the site1 bump',
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says when nothing was bumped', async () => {
    server.use(
      http.get('*/api/admin/analytics/bumps', () =>
        HttpResponse.json({ ...bumps, top: [], devices: 1, devices_all_time: 1 }),
      ),
    );
    renderWithProviders(<BumpsCard range={RANGE} />);
    expect(await screen.findByText('No bumps in this window yet.')).toBeInTheDocument();
    expect(await screen.findByText('1 device bumped in this window · 1 all time')).toBeInTheDocument();
  });
});

describe('UptakeCard', () => {
  it(
    'stacks the answers per week and sums up each device’s last answer',
    async () => {
      renderWithProviders(<UptakeCard range={RANGE} />);
      const card = await region('“Which one are you?” answers');
      expectChartControls(card);
      await expectExplainer(card, 'About this chart', { read: true });
      expect(
        within(card).getByText(
          'Last answer of each device since Jul 3, 2026: 11 picked a name, 3 skipped, 8 not answered',
        ),
      ).toBeVisible();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('says when no visits are kept in detail', async () => {
    server.use(
      http.get('*/api/admin/analytics/me-states', () =>
        HttpResponse.json({ ...uptake, latest: { picked: 0, skipped: 0, none: 0 }, latest_since: null }),
      ),
    );
    renderWithProviders(<UptakeCard range={RANGE} />);
    expect(
      await screen.findByText('No visits in this window are kept in detail.', {}, LAZY_CHART),
    ).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/admin-analytics/pages/AnalyticsPage.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { renderWithProviders } from '../../../test/render';
import { AnalyticsPage } from './AnalyticsPage';

afterEach(() => {
  vi.useRealTimers();
});

describe('AnalyticsPage', () => {
  it(
    'shows the window once and the four charts',
    async () => {
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date(2026, 9, 1, 12, 0));
      renderWithProviders(<AnalyticsPage />, { route: '/admin/analytics' });
      expect(screen.getByRole('heading', { level: 1, name: 'Analytics' })).toBeInTheDocument();
      expect(screen.getByText(/^Last 8 weeks · Aug 7 – Oct 1\./)).toBeInTheDocument();
      for (const name of [
        'Visitors',
        'Busiest days',
        'Page views by page',
        'Fist bumps per day',
        'Most-bumped insights',
        '“Which one are you?” answers',
      ]) {
        expect(await screen.findByRole('region', { name }, LAZY_CHART)).toBeInTheDocument();
      }
    },
    LAZY_TEST_TIMEOUT,
  );
});
```

Create `frontend/src/features/admin-analytics/routes.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

function renderAt(role: 'viewer' | 'admin') {
  renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
    route: '/admin/analytics',
    role,
  });
}

describe('admin-analytics routes', () => {
  it('serve the Analytics page to an admin', async () => {
    renderAt('admin');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Analytics' }),
    ).toBeInTheDocument();
  });

  it('give a viewer the admins-only page', async () => {
    renderAt('viewer');
    expect(await screen.findByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: 'Analytics' })).not.toBeInTheDocument();
  });

  it('add an admin-only nav item next to Data & ops and honour only the time window', () => {
    expect(nav.map(({ label, path, order, adminOnly }) => ({ label, path, order, adminOnly }))).toEqual([
      { label: 'Analytics', path: '/admin/analytics', order: 930, adminOnly: true },
    ]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: true } });
  });
});
```

In `frontend/src/app/navRegistry.test.ts`, replace

```ts
  'admin-ops': 920,
};
```

with

```ts
  'admin-ops': 920,
  'admin-analytics': 930,
};
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && pnpm gen:api && pnpm exec vitest run src/features/admin-analytics src/app/navRegistry.test.ts`
Expected: FAIL. Every `admin-analytics` test fails to resolve its module (`./models`, `./api`, `./explainers`, `./BumpsCard`, `./AnalyticsPage`, `./routes`). `navRegistry.test.ts` still passes: the new entry only allows order 930, and RED is shown by the routes test.

- [ ] **Step 3: Write the API layer, mocks, models and explainers**

Create `frontend/src/features/admin-analytics/api.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { useWindowChoice, windowRange } from '../../lib/timeWindow';
import { windowTagText } from '../../lib/windowText';
import type { JsonOf } from '../admin/api';

export type Visitors = JsonOf<paths['/api/admin/analytics/visitors']['get']>;
export type PageKindViews = JsonOf<paths['/api/admin/analytics/pages']['get']>[number];
export type BumpsSummary = JsonOf<paths['/api/admin/analytics/bumps']['get']>;
export type Uptake = JsonOf<paths['/api/admin/analytics/me-states']['get']>;

/** Local days from `since` (null: from the first data) to `asOf`. */
export interface AnalyticsRange {
  since: string | null;
  asOf: string;
}

/** Today as YYYY-MM-DD in the browser's calendar. */
export function todayIso(now: Date = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${String(now.getFullYear())}-${month}-${day}`;
}

/** Every day on record up to `asOf`: what fullscreen and the CSV show. */
export function allTime(asOf: string): AnalyticsRange {
  return { since: null, asOf };
}

/**
 * The header's time window (`w`, default 8 weeks), anchored at today rather than the latest
 * scored Sunday: visits happen every day (Decision 14). `tag` names it with its dates.
 */
export function useAnalyticsRange(): { range: AnalyticsRange; tag: string } {
  const [window] = useWindowChoice();
  const today = todayIso();
  return useMemo(() => {
    const dates = windowRange(window, today);
    return { range: { since: dates.from, asOf: dates.to }, tag: windowTagText(window, dates) };
  }, [window, today]);
}

function params(range: AnalyticsRange) {
  const query =
    range.since === null ? { as_of: range.asOf } : { since: range.since, as_of: range.asOf };
  return { params: { query } };
}

export const visitorsKey = (range: AnalyticsRange) =>
  ['/api/admin/analytics/visitors', range] as const;
export const pagesKey = (range: AnalyticsRange) => ['/api/admin/analytics/pages', range] as const;
export const bumpsKey = (range: AnalyticsRange) => ['/api/admin/analytics/bumps', range] as const;
export const uptakeKey = (range: AnalyticsRange) =>
  ['/api/admin/analytics/me-states', range] as const;

export const fetchVisitors = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/visitors', params(range)));
export const fetchPages = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/pages', params(range)));
export const fetchBumps = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/bumps', params(range)));
export const fetchUptake = (range: AnalyticsRange) =>
  unwrap(api.GET('/api/admin/analytics/me-states', params(range)));

export function useVisitors(range: AnalyticsRange) {
  return useQuery({ queryKey: visitorsKey(range), queryFn: () => fetchVisitors(range) });
}
export function usePages(range: AnalyticsRange) {
  return useQuery({ queryKey: pagesKey(range), queryFn: () => fetchPages(range) });
}
export function useBumps(range: AnalyticsRange) {
  return useQuery({ queryKey: bumpsKey(range), queryFn: () => fetchBumps(range) });
}
export function useUptake(range: AnalyticsRange) {
  return useQuery({ queryKey: uptakeKey(range), queryFn: () => fetchUptake(range) });
}
```

Create `frontend/src/features/admin-analytics/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import type { BumpsSummary, PageKindViews, Uptake, Visitors } from './api';

export const visitors: Visitors = {
  days: [
    { day: '2026-09-27', devices: 14 },
    { day: '2026-09-28', devices: 3 },
    { day: '2026-09-29', devices: 2 },
    { day: '2026-09-30', devices: 4 },
    { day: '2026-10-01', devices: 1 },
  ],
  weeks: [
    { week: '2026-09-21', devices: 18 },
    { week: '2026-09-28', devices: 7 },
  ],
  busiest: [
    { day: '2026-09-27', devices: 14 },
    { day: '2026-09-30', devices: 4 },
    { day: '2026-09-28', devices: 3 },
  ],
};

export const pageKinds: PageKindViews[] = [
  { page_kind: 'home', views: 40 },
  { page_kind: 'profile', views: 22 },
  { page_kind: 'event', views: 9 },
  { page_kind: 'leaderboards', views: 5 },
];

export const bumps: BumpsSummary = {
  days: [
    { day: '2026-09-27', bumps: 5 },
    { day: '2026-09-28', bumps: 2 },
  ],
  top: [
    { key: 'a1b2c3d4e5f6a7b8c9d0', headline: 'Ike Hadley broke 45 for the first time', bumps: 6 },
    { key: 'ffffeeeeddddccccbbbb', headline: null, bumps: 1 },
  ],
  devices: 8,
  devices_all_time: 12,
};

export const uptake: Uptake = {
  weeks: [
    { week: '2026-09-21', picked: 9, skipped: 2, none: 7 },
    { week: '2026-09-28', picked: 4, skipped: 1, none: 2 },
  ],
  latest: { picked: 11, skipped: 3, none: 8 },
  latest_since: '2026-07-03',
};

export const handlers = [
  http.get('*/api/admin/analytics/visitors', () => HttpResponse.json(visitors)),
  http.get('*/api/admin/analytics/pages', () => HttpResponse.json(pageKinds)),
  http.get('*/api/admin/analytics/bumps', () => HttpResponse.json(bumps)),
  http.get('*/api/admin/analytics/me-states', () => HttpResponse.json(uptake)),
];
```

Create `frontend/src/features/admin-analytics/models.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { barOption } from '../../components/charts/builders/bar';
import type { TabularData } from '../../components/charts/types';
import type { BumpsSummary, PageKindViews, Uptake, Visitors } from './api';

export type Model = TabularData & { option: EChartsOption };
export type Per = 'day' | 'week';

/** Plain names for the page kinds; copy says "Sunday", never "event" (Global Constraints). */
const PAGE_KIND_LABELS = new Map<string, string>([
  ['home', 'Home'],
  ['profile', 'Shooter profiles'],
  ['event', 'One Sunday'],
  ['events-list', 'Sundays list'],
  ['leaderboards', 'Leaderboards'],
  ['records', 'Records'],
  ['club', 'Club'],
  ['stations', 'Stations'],
  ['weather', 'Weather'],
  ['yir', 'Year in Review'],
  ['explorer', 'Explorer'],
  ['achievements', 'Trophies'],
  ['race', 'Race'],
  ['compare', 'Compare'],
  ['admin', 'Admin pages'],
  ['other', 'Other pages'],
]);

/** A kind added later without a label shows as its own name. */
export function pageKindLabel(kind: string): string {
  return PAGE_KIND_LABELS.get(kind) ?? kind;
}

export function visitorsModel(data: Visitors, per: Per): Model {
  const columns: TabularData['columns'] = [
    per === 'day'
      ? { key: 'day', label: 'Day', type: 'date' }
      : { key: 'week', label: 'Week of', type: 'date' },
    { key: 'devices', label: 'Devices', type: 'int' },
  ];
  const rows =
    per === 'day'
      ? data.days.map((d) => ({ day: d.day, devices: d.devices }))
      : data.weeks.map((w) => ({ week: w.week, devices: w.devices }));
  return { columns, rows, option: barOption({ columns, rows }, { x: per, y: ['devices'] }) };
}

export function pageKindsModel(data: PageKindViews[]): Model {
  const columns: TabularData['columns'] = [
    { key: 'page', label: 'Page', type: 'string' },
    { key: 'views', label: 'Views', type: 'int' },
  ];
  const rows = data.map((k) => ({ page: pageKindLabel(k.page_kind), views: k.views }));
  const option = barOption(
    { columns, rows },
    { x: 'page', y: ['views'], horizontal: true, labels: true },
  );
  return { columns, rows, option };
}

export function bumpsModel(data: BumpsSummary): Model {
  const columns: TabularData['columns'] = [
    { key: 'day', label: 'Day', type: 'date' },
    { key: 'bumps', label: 'Bumps', type: 'int' },
  ];
  const rows = data.days.map((d) => ({ day: d.day, bumps: d.bumps }));
  return { columns, rows, option: barOption({ columns, rows }, { x: 'day', y: ['bumps'] }) };
}

export function uptakeModel(data: Uptake): Model {
  const columns: TabularData['columns'] = [
    { key: 'week', label: 'Week of', type: 'date' },
    { key: 'picked', label: 'Picked a name', type: 'int' },
    { key: 'skipped', label: 'Skipped', type: 'int' },
    { key: 'none', label: 'Not answered', type: 'int' },
  ];
  const rows = data.weeks.map((w) => ({
    week: w.week,
    picked: w.picked,
    skipped: w.skipped,
    none: w.none,
  }));
  const option = barOption(
    { columns, rows },
    { x: 'week', y: ['picked', 'skipped', 'none'], stack: true, yName: 'Devices' },
  );
  return { columns, rows, option };
}
```

Create `frontend/src/features/admin-analytics/explainers.ts`:

```ts
import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the admin Analytics page, keyed by ChartFrame urlKey. Written against
 * domain/page_views.py and domain/site_analytics.py (STYLE.md: no jargon, neutral pronouns,
 * "Sunday" not "event").
 */
export const analyticsExplainers = {
  visitors: {
    what: 'How many different phones and computers opened the site each day or week in the time window.',
    read: [
      'Tall bars are busy days.',
      'Per week runs Monday to Sunday.',
      'Fullscreen and the CSV download cover every day on record.',
    ],
    computed: [
      'Each browser keeps a random id that says nothing about who uses it.',
      'A week counts each id once, so a week is not its days added up.',
      'Admin visits and browsers that block site storage are never counted.',
      'After about 90 days only the totals are kept.',
    ],
  },
  pages: {
    what: 'Which parts of the site people open most in the time window.',
    read: [
      'Longer bars are the pages people open most.',
      'Fullscreen and the CSV download cover every day on record.',
    ],
    computed: [
      'A device opening a page counts once per page type every 30 minutes.',
      'Pages are grouped: every shooter profile is “Shooter profiles” and every Sunday’s results page is “One Sunday”.',
      'Admin visits are never counted.',
    ],
  },
  bumps: {
    what: 'How many fist bumps insights got each day, and which insights got the most.',
    read: [
      'A bar is the bumps given that day that still stand.',
      'Fullscreen and the CSV download cover every day on record.',
    ],
    computed: [
      'One bump per device per insight. Taking a bump back removes it from every count.',
      'An insight that is no longer on the site keeps its bumps but loses its headline.',
      'Devices that bumped counts each device once, however many bumps it gave.',
    ],
  },
  uptake: {
    what: 'How many devices answered “Which one are you?” on Home, week by week.',
    read: [
      'Picked a name: the device chose a shooter. Skipped: it said it is not a shooter. Not answered: neither yet.',
      'Fullscreen and the CSV download cover every week on record.',
    ],
    computed: [
      'Each device counts once a week, with its last answer that week.',
      'The line above the chart uses each device’s last answer in the window, from visits kept in detail (about the last 90 days).',
      'Only the answer is kept, never the name picked.',
    ],
  },
} satisfies Record<string, Explainer>;
```

- [ ] **Step 4: Run the model, API and explainer tests**

Run: `cd frontend && pnpm exec vitest run src/features/admin-analytics/models.test.ts src/features/admin-analytics/api.test.tsx`
Expected: PASS. (`explainers.test.ts` waits for the cards in Step 5, because its urlKey set is still empty.)

- [ ] **Step 5: Write the cards, the page and the route**

Create `frontend/src/features/admin-analytics/components/VisitorsCard.tsx`:

```tsx
import { useMemo, useState } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDate } from '../../../lib/format';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, fetchVisitors, useVisitors, visitorsKey, type AnalyticsRange } from '../api';
import { analyticsExplainers } from '../explainers';
import { visitorsModel, type Per } from '../models';

const TITLE = 'Visitors';
const plural = (n: number) => `${String(n)} ${n === 1 ? 'device' : 'devices'}`;

/** Unique devices per day or week (switchable), and the busiest days of the window. */
export function VisitorsCard({ range }: { range: AnalyticsRange }) {
  const [per, setPer] = useState<Per>('day');
  const query = useVisitors(range);
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(range.asOf);
    return {
      queryKey: [...visitorsKey(all), per, 'chart-full'],
      queryFn: async () => ({
        ...visitorsModel(await fetchVisitors(all), per),
        note: per === 'day' ? 'Every day on record.' : 'Every week on record.',
      }),
    };
  }, [range.asOf, per]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading visitors" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={TITLE}>
        <AdminError error={query.error} />
      </Card>
    );
  }
  const model = visitorsModel(query.data, per);
  if (query.data.days.length === 0) {
    return (
      <Card title={TITLE}>
        <EmptyState title="Nothing counted in this window yet." />
      </Card>
    );
  }
  return (
    <>
      <ChartFrame
        title={TITLE}
        subtitle={per === 'day' ? 'Different devices each day' : 'Different devices each week'}
        option={model.option}
        columns={model.columns}
        rows={model.rows}
        csvName={`visitors-${per}-${range.asOf}`}
        ariaLabel={`Visitors per ${per}`}
        urlKey="visitors"
        explainer={analyticsExplainers.visitors}
        fullQuery={fullQuery}
        controls={
          <>
            <Chip selected={per === 'day'} onClick={() => setPer('day')}>
              Per day
            </Chip>
            <Chip selected={per === 'week'} onClick={() => setPer('week')}>
              Per week
            </Chip>
          </>
        }
      />
      <Card title="Busiest days">
        {query.data.busiest.length === 0 ? (
          <p className="text-sm text-text-muted">No visits in this window yet.</p>
        ) : (
          <ol aria-label="Busiest days" className="flex flex-col gap-2 text-sm">
            {query.data.busiest.map((d) => (
              <li key={d.day} className="flex min-w-0 justify-between gap-3">
                <span>{formatDate(d.day)}</span>
                <span className="text-text-muted">{plural(d.devices)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}
```

Create `frontend/src/features/admin-analytics/components/PageKindsCard.tsx`:

```tsx
import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, fetchPages, pagesKey, usePages, type AnalyticsRange } from '../api';
import { analyticsExplainers } from '../explainers';
import { pageKindsModel } from '../models';

const TITLE = 'Page views by page';

export function PageKindsCard({ range }: { range: AnalyticsRange }) {
  const query = usePages(range);
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(range.asOf);
    return {
      queryKey: [...pagesKey(all), 'chart-full'],
      queryFn: async () => ({ ...pageKindsModel(await fetchPages(all)), note: 'Every day on record.' }),
    };
  }, [range.asOf]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading page views" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={TITLE}>
        <AdminError error={query.error} />
      </Card>
    );
  }
  if (query.data.length === 0) {
    return (
      <Card title={TITLE}>
        <EmptyState title="Nothing counted in this window yet." />
      </Card>
    );
  }
  const model = pageKindsModel(query.data);
  return (
    <ChartFrame
      title={TITLE}
      subtitle="Counted views of each kind of page"
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName={`page-views-${range.asOf}`}
      ariaLabel={TITLE}
      urlKey="pages"
      explainer={analyticsExplainers.pages}
      fullQuery={fullQuery}
      height={Math.max(240, 40 * model.rows.length)}
    />
  );
}
```

Create `frontend/src/features/admin-analytics/components/BumpsCard.tsx`:

```tsx
import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, bumpsKey, fetchBumps, useBumps, type AnalyticsRange } from '../api';
import { analyticsExplainers } from '../explainers';
import { bumpsModel } from '../models';

const TITLE = 'Fist bumps per day';
const devices = (n: number) => `${String(n)} ${n === 1 ? 'device' : 'devices'}`;
const bumpCount = (n: number) => `${String(n)} ${n === 1 ? 'bump' : 'bumps'}`;

/** Bumps per day, how many devices bumped, and the most-bumped insights of the window. */
export function BumpsCard({ range }: { range: AnalyticsRange }) {
  const query = useBumps(range);
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(range.asOf);
    return {
      queryKey: [...bumpsKey(all), 'chart-full'],
      queryFn: async () => ({ ...bumpsModel(await fetchBumps(all)), note: 'Every day on record.' }),
    };
  }, [range.asOf]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading fist bumps" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={TITLE}>
        <AdminError error={query.error} />
      </Card>
    );
  }
  const data = query.data;
  const model = bumpsModel(data);
  const summary = `${devices(data.devices)} bumped in this window · ${String(data.devices_all_time)} all time`;
  return (
    <>
      {model.rows.length === 0 ? (
        <Card title={TITLE} subtitle={summary}>
          <EmptyState title="Nothing counted in this window yet." />
        </Card>
      ) : (
        <ChartFrame
          title={TITLE}
          subtitle={summary}
          option={model.option}
          columns={model.columns}
          rows={model.rows}
          csvName={`fist-bumps-${range.asOf}`}
          ariaLabel={TITLE}
          urlKey="bumps"
          explainer={analyticsExplainers.bumps}
          fullQuery={fullQuery}
        />
      )}
      <Card title="Most-bumped insights">
        {data.top.length === 0 ? (
          <p className="text-sm text-text-muted">No bumps in this window yet.</p>
        ) : (
          <ol aria-label="Most-bumped insights" className="flex flex-col gap-2 text-sm">
            {data.top.map((t) => (
              <li key={t.key} className="flex min-w-0 justify-between gap-3">
                <span className="min-w-0 break-words">
                  {t.headline ?? 'An insight no longer on the site'}
                </span>
                <span className="shrink-0 text-text-muted">{bumpCount(t.bumps)}</span>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </>
  );
}
```

Create `frontend/src/features/admin-analytics/components/UptakeCard.tsx`:

```tsx
import { useMemo } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery } from '../../../components/charts/types';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDate } from '../../../lib/format';
import { AdminError } from '../../admin/components/AdminError';
import { allTime, fetchUptake, uptakeKey, useUptake, type AnalyticsRange, type Uptake } from '../api';
import { analyticsExplainers } from '../explainers';
import { uptakeModel } from '../models';

const TITLE = '“Which one are you?” answers';

function summary(data: Uptake): string {
  if (data.latest_since === null) return 'No visits in this window are kept in detail.';
  const { picked, skipped, none } = data.latest;
  return `Last answer of each device since ${formatDate(data.latest_since)}: ${String(picked)} picked a name, ${String(skipped)} skipped, ${String(none)} not answered`;
}

/** Answers per week (stacked), with each device's last answer across the window above. */
export function UptakeCard({ range }: { range: AnalyticsRange }) {
  const query = useUptake(range);
  const fullQuery = useMemo<ChartFullQuery>(() => {
    const all = allTime(range.asOf);
    return {
      queryKey: [...uptakeKey(all), 'chart-full'],
      queryFn: async () => ({ ...uptakeModel(await fetchUptake(all)), note: 'Every week on record.' }),
    };
  }, [range.asOf]);

  if (query.isPending) {
    return (
      <Card title={TITLE}>
        <Skeleton label="Loading answers" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={TITLE}>
        <AdminError error={query.error} />
      </Card>
    );
  }
  const model = uptakeModel(query.data);
  if (model.rows.length === 0) {
    return (
      <Card title={TITLE} subtitle={summary(query.data)}>
        <EmptyState title="Nothing counted in this window yet." />
      </Card>
    );
  }
  return (
    <ChartFrame
      title={TITLE}
      subtitle={summary(query.data)}
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName={`which-one-are-you-${range.asOf}`}
      ariaLabel="Which one are you? answers per week"
      urlKey="uptake"
      explainer={analyticsExplainers.uptake}
      fullQuery={fullQuery}
    />
  );
}
```

Create `frontend/src/features/admin-analytics/pages/AnalyticsPage.tsx`:

```tsx
import { useAnalyticsRange } from '../api';
import { BumpsCard } from '../components/BumpsCard';
import { PageKindsCard } from '../components/PageKindsCard';
import { UptakeCard } from '../components/UptakeCard';
import { VisitorsCard } from '../components/VisitorsCard';

/** Admin Analytics (Plan 16): anonymous site usage over the header's time window, to today. */
export function AnalyticsPage() {
  const { range, tag } = useAnalyticsRange();
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <h1 className="text-2xl font-medium">Analytics</h1>
      <p className="min-w-0 text-sm text-text-muted">
        {tag}. Signed-in visitors only: admin visits are never counted, and nothing here says who
        anyone is.
      </p>
      <VisitorsCard range={range} />
      <PageKindsCard range={range} />
      <BumpsCard range={range} />
      <UptakeCard range={range} />
    </div>
  );
}
```

Create `frontend/src/features/admin-analytics/routes.tsx`:

```tsx
import { ChartColumn } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import type { PageFilters } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

/** The header shows only the time window: these counts have no round type (Decision 18). */
const WINDOW_ONLY: PageFilters = { roundType: false, window: true };

// Admin pages render inside RequireRole role="admin"; the page stays lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin/analytics',
    handle: { filters: WINDOW_ONLY },
    lazy: async () => {
      const { AnalyticsPage } = await import('./pages/AnalyticsPage');
      return {
        element: (
          <RequireRole role="admin">
            <AnalyticsPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Analytics', path: '/admin/analytics', icon: ChartColumn, order: 930, adminOnly: true },
];
```

- [ ] **Step 6: Run the unit tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/admin-analytics src/app`
Expected: PASS, including `explainers.test.ts` (four urlKeys, all wired) and `navRegistry.test.ts` (Analytics at 930).

- [ ] **Step 7: Write the e2e spec**

Create `frontend/e2e/admin-analytics.spec.ts`:

```ts
import { randomUUID } from 'node:crypto';

import type { APIRequestContext, Page } from '@playwright/test';

import { ADMIN_STATE, VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

/**
 * Admin Analytics and the page-view beacon (Plan 16). Counts are read from the API before and
 * after, never hard-coded: both projects share one stack and run at once.
 */

type Kinds = { page_kind: string; views: number }[];
type Beacon = Record<string, unknown>;

async function views(request: APIRequestContext, kind: string): Promise<number> {
  const response = await request.get('/api/admin/analytics/pages'); // all time, to today
  expect(response.ok()).toBe(true);
  return ((await response.json()) as Kinds).find((k) => k.page_kind === kind)?.views ?? 0;
}

function recordBeacons(page: Page): Beacon[] {
  const sent: Beacon[] = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/pageviews') && request.method() === 'POST') {
      sent.push(request.postDataJSON() as Beacon);
    }
  });
  return sent;
}

const beaconAnswered = (page: Page) =>
  page.waitForResponse(
    (r) => r.url().endsWith('/api/pageviews') && r.request().method() === 'POST',
  );

test.describe('as a viewer', () => {
  test('each page sends one beacon with only a kind, a state, a time and a random id', async ({
    page,
    playwright,
    baseURL,
  }) => {
    const device = randomUUID();
    await page.addInitScript((id) => {
      localStorage.setItem('sc.device', id);
    }, device);
    const admin = await playwright.request.newContext({ baseURL, storageState: ADMIN_STATE });
    const before = await views(admin, 'leaderboards');
    const sent = recordBeacons(page);

    const first = beaconAnswered(page);
    await page.goto('/leaderboards');
    expect((await first).status()).toBe(204);
    const second = beaconAnswered(page);
    await page.getByRole('link', { name: 'Home', exact: true }).first().click();
    expect((await second).status()).toBe(204);

    expect(sent.map((b) => b.page_kind)).toEqual(['leaderboards', 'home']);
    for (const body of sent) {
      expect(Object.keys(body).sort()).toEqual(['at', 'device_id', 'me_state', 'page_kind']);
      expect(body.device_id).toBe(device);
      expect(body.me_state).toMatch(/^(picked|skipped|none)$/);
      expect(JSON.stringify(body)).not.toContain('/');
    }
    await expect.poll(() => views(admin, 'leaderboards')).toBeGreaterThanOrEqual(before + 1);
    await admin.dispose();
  });
});

test.describe('as an admin', () => {
  test.use({ storageState: ADMIN_STATE });

  // With no counted view in the window, "Page views by page" and "Busiest days" are empty states
  // with no chart controls. A fresh stack, or this file running before any viewer page
  // (fullyParallel; auth.setup logs in through the API), may have none yet: store one first.
  // The kind is 'other', so the admin test's 'compare' count is untouched.
  test.beforeAll(async ({ playwright }, testInfo) => {
    const viewer = await playwright.request.newContext({
      baseURL: testInfo.project.use.baseURL,
      storageState: VIEWER_STATE,
    });
    const response = await viewer.post('/api/pageviews', {
      data: { device_id: randomUUID(), page_kind: 'other', me_state: 'none' },
    });
    expect(response.status()).toBe(204);
    await viewer.dispose();
  });

  test('admin pages send no beacon, and the server drops one an admin sends anyway', async ({
    page,
  }) => {
    const sent = recordBeacons(page);
    await page.goto('/admin/analytics');
    await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
    await page.goto('/leaderboards');
    await whenSettled(page);
    expect(sent).toEqual([]);
    // Nothing in the e2e suite opens /compare, so its count only moves if this beacon counts.
    const before = await views(page.request, 'compare');
    const response = await page.request.post('/api/pageviews', {
      data: { device_id: randomUUID(), page_kind: 'compare', me_state: 'none' },
    });
    expect(response.status()).toBe(204);
    expect(await views(page.request, 'compare')).toBe(before);
  });

  test('the Analytics page shows four charts, each with Table, CSV, fullscreen and an explainer', async ({
    page,
  }) => {
    await page.goto('/admin/analytics');
    await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
    await expect(page.getByText(/^Last 8 weeks · /)).toBeVisible();
    for (const title of [
      'Visitors',
      'Page views by page',
      'Fist bumps per day',
      '“Which one are you?” answers',
    ]) {
      const card = page.getByRole('region', { name: title });
      await expect(card).toBeVisible();
      for (const name of ['Table', 'CSV', 'Fullscreen', 'About this chart']) {
        await expect(card.getByRole('button', { name })).toBeVisible();
      }
    }
    await expect(page.getByRole('region', { name: 'Busiest days' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Most-bumped insights' })).toBeVisible();
    await whenSettled(page);
    await expectNoSideScroll(page);
    await expectTapTargets(page);
  });

  test('visitors switch to weeks, show a table, open fullscreen and download every day', async ({
    page,
  }) => {
    await page.goto('/admin/analytics');
    const card = page.getByRole('region', { name: 'Visitors' });
    await card.getByRole('button', { name: 'About this chart' }).click();
    await expect(card.getByRole('heading', { name: 'What this shows' })).toBeVisible();
    await card.getByRole('button', { name: 'Per week' }).click();
    await card.getByRole('button', { name: 'Table' }).click();
    await expect(card.getByRole('columnheader', { name: 'Week of' })).toBeVisible();
    await card.getByRole('button', { name: 'Fullscreen' }).click();
    const dialog = page.getByRole('dialog', { name: 'Visitors' });
    await expect(dialog.getByText('Every week on record.')).toBeVisible();
    const download = page.waitForEvent('download');
    await dialog.getByRole('button', { name: 'CSV' }).click();
    expect((await download).suggestedFilename()).toMatch(/^visitors-week-\d{4}-\d{2}-\d{2}\.csv$/);
    await expectNoSideScroll(page);
  });

  test('Analytics is in the admin navigation', async ({ page }, testInfo) => {
    await page.goto('/admin/ops');
    if (testInfo.project.name === 'mobile') {
      await page.getByRole('button', { name: 'More' }).click();
      await page.getByRole('navigation', { name: 'More' }).getByRole('link', { name: 'Analytics' }).click();
    } else {
      await page.getByRole('complementary').getByRole('link', { name: 'Analytics' }).click();
    }
    await expect(page).toHaveURL(/\/admin\/analytics$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
  });
});
```

- [ ] **Step 8: Run the e2e on the base to see it fail (RED)**

Build a stack from `feat/insight-bumps` with T1–T3 merged but **without** this task (that is the task's base), then run:
`E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/admin-analytics.spec.ts`
Expected: the viewer test passes, because T1–T3 already provide the beacon. The four admin page tests fail at both projects: `/admin/analytics` has no route, so no "Analytics" heading or nav link. Paste this output as the RED evidence.

- [ ] **Step 9: Run it on this branch (GREEN)**

Rebuild the stack from this task's branch, then run the same command.
Expected: 10 passed (5 tests × desktop and mobile).

- [ ] **Step 10: Full suites and gates**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage`, then the full `pnpm exec playwright test` against the stack.
Expected: clean, all green, and coverage at or above 90% lines and branches. Re-run a known flaky spec once before reporting it, and name it if it still fails.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/features/admin-analytics frontend/src/app/navRegistry.test.ts frontend/e2e/admin-analytics.spec.ts
git commit -m "feat(analytics): admin Analytics page with four explained charts, e2e at both viewports (Plan 16 T4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review (author)

- **Design coverage:**
  - Beacon `{device_id, page_kind, me_state, at}` on each client-side route change: T3 (`usePageViewBeacon` on pathname) and T1 (`PageViewIn`).
  - Coarse kinds only, never a URL or id: T3 `pageKind` with its "never carries an id or a path" test, T1 `Literal` (422 otherwise), and T4 e2e (no `/` in any beacon body).
  - me_state with no name: T3 `meState`, T1 CHECK and `Literal`.
  - Admin dropped server-side with 204: T1 (`test_an_admin_beacon_is_dropped_and_leaves_no_trace`); the client skip is in T3.
  - Storage blocked: T3 (no device id, no beacon).
  - 30-minute dedupe server-side: T1 store tests, including the race.
  - No names, IPs or identifying data stored: T1 column-set tests; IP only in `page_view_attempts`, pruned on the next beacon and by the daily job (`test_the_daily_prune_clears_old_rows_with_no_new_beacon`, `test_the_job_prunes_rate_limit_rows_left_by_a_quiet_spell`).
  - Viewer login: T1 discovery (auth matrix 401).
  - CSP and never blocking: T3 same-origin `fetch` keepalive, `void` and `try/catch`, sent after paint; the e2e `fixtures.ts` fails on any CSP violation.
  - Retention via a scheduled job, aggregated before delete, with day and week uniques kept correct: T1 rollup (separate day and week rows, whole weeks) and scheduler tests.
  - Admin page, adminOnly nav next to Ops, time-range control: T4 (route handle `window: true`, order 930).
  - Visitors per day and week chart plus busiest days: T2 `visitors`, T4 `VisitorsCard`.
  - Page views by kind: T2 `page_kinds`, T4 `PageKindsCard`.
  - Bumps per day, top insights with headline and count, bumping devices: T2 `bumps`, T4 `BumpsCard`.
  - Uptake by latest state: T2 `uptake`, T4 `UptakeCard`.
  - ChartFrame with Table, CSV, fullscreen and ELI5 explainer on every chart: T4 card tests and e2e.
  - Admin API `/api/admin/analytics/*`, admin-only, no-store: T2 (403 for a viewer, `no-store`, no ETag).
  - Read-only, so no audit: T2 `test_reading_analytics_writes_nothing`.
  - Expand-only migration `0007` after Plan 15's `0006`: T1.
  - e2e at both viewports: T4.
- **Placeholder scan:** none. Every code step carries its code and every run step its command and expected outcome.
- **Type consistency:**
  - `PageKind` and `MeState` (T1 `domain/page_views.py`) feed the OpenAPI `PageViewIn`, which T3 reads as `components['schemas']['PageViewIn']`.
  - `latest_states`, `state_counts`, `bucket_of` and `local_midnight` are produced by T1 and consumed by T2.
  - The JSON names `day`, `week`, `devices`, `bumps`, `picked`, `skipped`, `none` and `latest_since` agree between T2's `*Out` models, T4's `mocks.ts` and `models.ts`.
  - `allTime(asOf)` and the `*Key(range)` query keys agree across T4's cards and the fullscreen `fullQuery` keys (each ends in `'chart-full'`).
