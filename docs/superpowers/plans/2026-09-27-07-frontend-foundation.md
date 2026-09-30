# Sunday Clays — Plan 07: Frontend Foundation & Explorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Every implementer and reviewer runs on Opus (master Global Constraints). Each task below is self-contained: an
> implementer reads only its own task, so every task repeats the commands and names it needs.

**Goal:** Give the SPA its ClaySmasher design system, responsive layout shell, session-guarded auth UI, API and URL-state
plumbing, the complete ECharts builder kit with `ChartFrame`/`ChartCard`, and the Explorer (backend `POST /api/explore`
plus the `/explorer` page) that every later UI plan (08–11) builds on.

**Architecture:** Tailwind v4 `@theme` tokens mirrored in `theme/tokens.ts` drive both CSS utilities and a registered
ECharts theme; a small UI kit (`components/ui`) and a registry-driven `AppShell` (side nav ≥1024 px, top bar + bottom
tabs + "More" sheet below) wrap every feature route, guarded by `RequireRole`. Data flows through a typed openapi-fetch
client (401 → `/login?next=`), TanStack Query, and query-string state (`useUrlState`); charts are pure option builders
over `TabularData`, rendered only inside `ChartFrame` (table, CSV, fullscreen, zoom) or `ChartCard` (explore controls
over `POST /api/explore`). The Explorer backend is a pure pandas `run_query(ExplorerFrames, QuerySpec)` over frames
cached per `data_version`.

**Tech Stack:** React 19 · Vite · TypeScript (strict, `verbatimModuleSyntax`) · Tailwind v4 · `@fontsource/roboto` ·
lucide-react · React Router v7 · TanStack Query v5 · openapi-fetch + openapi-typescript · ECharts (`echarts/core`) ·
html-to-image · Vitest + Testing Library + MSW + vitest-canvas-mock · Playwright · Python 3.13 · FastAPI · Pydantic v2 ·
pandas · SQLAlchemy 2 · pytest.

**Spec:** `/Users/bryanmoran/code/sunday-clays/docs/superpowers/specs/2026-09-27-sunday-clays-design.md`

**Master:** `/Users/bryanmoran/code/sunday-clays/docs/superpowers/plans/2026-09-27-00-master.md` (Architecture Contract
C1–C12 is binding; this plan implements Plan 07 T1–T8).

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
Master Review Focus items owned by this plan: none (items 1–5 belong to Plans 02, 03, 06, 08 and 09). Plan-specific
items, most likely to bite first; each names the test that pins it in the owning task:
1. **A session expires mid-use** (cookie past its TTL, a rotated password or `session_secret`, a logout in another
   tab) → the next data request's 401 clears the cached session and sends the visitor to `/login?next=<path+query>`,
   where they stay until they log in, then return; 401s from `/api/auth/me`, `/api/auth/login` and
   `/api/auth/logout` never redirect, and the login page never bounces back to the failing page on a stale cached role,
   so there is no loop. Owner: Task 4 (`sends an expired session on a data request to the login page with next`,
   `status %s from %s on page %s redirects: %s`) and Task 3 (`returns to next after a successful login (the ?next=
   round-trip)`, `lands a data 401 on the login page with next and stays there (no redirect loop)`, `routes a data 401
   to the login page and forgets the cached session`).
2. **A hostile `?next=`** (`//evil.com`, `/\evil.com`, `https://evil.com`, `/%0a/evil.com`, `javascript:alert(1)`) →
   login always lands on a same-origin path. Owner: Task 3 (`safeNext` table `rejects %s`, `never follows a hostile
   next=%s off the site`, e2e `a hostile next never leaves the site`).
3. **Explorer groups with no values** (adjusted or residual at non-held events, stdev of a single round, events without
   weather) → JSON `null` (never a 500 from NaN), sorted last, shown as `—`. Owner: Task 7
   (`test_missing_values_serialize_as_null_and_sort_last`) and Task 6 (`toggles a table of the exact rows and remembers
   it in the URL`).
4. **Invalid or hand-edited Explorer queries** (group by station with a non-hit metric, attendance by shooter, three
   dims, `?m=bogus&t=abc`) → a 400 `invalid_query` whose message the page shows, or safe defaults, never a crash; a
   previous result is never drawn with a newer grouping. Owner: Task 7 (`test_invalid_queries_are_rejected`,
   `test_hit_pct_without_station_data_is_rejected`, `test_invalid_query_is_a_400_with_the_error_envelope`), Task 8
   (`falls back to safe defaults for hand-edited, malformed parameters`, `shows the server's explanation when a
   combination is invalid`) and Task 6 (`shows the server's invalid_query message and retries`, `keeps drawing the
   previous result while a new grouping loads`).
5. **Hostile shooter names** (`<img src=x onerror=alert(1)>`, `=HYPERLINK(...)`) in chart tooltips and CSV exports →
   escaped HTML and neutralised spreadsheet formulas. Owner: Task 5 (every builder with a string tooltip formatter:
   `escapes names in the tooltip so a shooter name cannot inject HTML`, `escapes shooter names in the tooltip`,
   `escapes group names in the tooltip`) and Task 4 (`neutralises text that a spreadsheet would run as a formula, but
   not numbers`).

## Decisions
Choices made where the master is silent, so cross-plan auditors can check them against Plans 01, 04, 06 and 08–11.

**Consumed from other plans (names the cross-plan critic must reconcile)**
- D1 (Plan 01 T2 skeleton): `src/app/registry.ts` exports `interface NavItem {label: string; path: string; icon:
  LucideIcon; order: number; mobileTab?: boolean; adminOnly?: boolean}`, `interface FeatureModule {routes:
  RouteObject[]; nav?: NavItem[]}`, `featureRoutes: RouteObject[]` (every feature's routes, flattened) and `navItems:
  NavItem[]` (sorted by `order`); `src/app/router.tsx` exports `appRoutes: RouteObject[]` and `createAppRouter()`;
  `src/app/App.tsx` exports `App`; `src/main.tsx` renders `<App />` and imports `./theme/theme.css`;
  `src/test/render.tsx` exports `renderWithProviders(ui, { route? })` and `renderRoute(route, routes = appRoutes)`
  (used by Plan 01's `router.test.tsx`; Task 4 keeps both names); `vitest.config.ts` sets `restoreMocks: true` and
  `unstubGlobals: true`; `features/home/pages/HomePage.tsx` renders `<main><h1>Sunday Clays</h1>…</main>` (Plan 08 T4
  replaces it with a page that renders no `<main>`, D15); `src/test/msw/server.ts` exports `server`;
  `src/test/msw/handlers.ts` merges every `features/*/mocks.ts` `handlers` export; `src/test/setup.ts` defines
  `window.matchMedia` (never matching),
  `ResizeObserver`, `navigator.share`/`canShare`, `URL.createObjectURL`/`revokeObjectURL`, registers jest-dom and
  `vitest-canvas-mock`, and runs MSW with `onUnhandledRequest: 'error'`; `features/home/routes.tsx` exports an index
  route and `nav: [{label: 'Home', path: '/', icon: House, order: 10, mobileTab: true}]`; scripts `lint`
  (`eslint . --max-warnings 0`), `typecheck` (`tsc --noEmit`, with `pretypecheck` = `gen:api`), `build`, `gen:api`.
  Plan 01's Decision 15 makes feature routes relative children of the `/` root (`index: true` or `'events'`, never
  `'/events'`); this plan follows it (`path: 'login'`, `path: 'explorer'`), because the master is silent and the
  producer plan wins. Nav items, links and `navigate()` targets stay absolute URLs (`'/explorer'`, `'/login?next=…'`),
  and test-only route trees built inside a test file may use absolute top-level paths.
- D2 (Plan 01 T1): route modules declare full paths (`@router.post("/api/explore")`) and `create_app()` includes
  discovered routers without a prefix; `DomainError` exposes `.code` and `.message`, and `api/errors.py` renders it as
  `{"error": {"code", "message"}}` with `exc.status_code`.
- D3 (Plan 04 T1/T2): `GET /api/auth/me` → 200 `RoleOut{role}` or 401; `POST /api/auth/login {password}` → 200
  `RoleOut{role}`, 401 on a wrong password, 429 when rate-limited; `POST /api/auth/logout` → 204 (no body). Every
  auth failure uses the C2 envelope (Plan 04 Decision D3): 401 `{"error": {"code": "unauthenticated", "message":
  "Log in to continue"}}` for a missing, expired or revoked session (`/api/auth/me` and every data route), 401
  `invalid_password` ("Wrong password") from login, 429 `rate_limited` or `login_busy`; the MSW mocks here use those
  codes. `e2e/authState.ts` exports `VIEWER_STATE` (`e2e/.auth/viewer.json`), `ADMIN_STATE` and `e2ePassword(role)` (reads
  `E2E_VIEWER_PASSWORD`/`E2E_ADMIN_PASSWORD`); the Playwright `setup` project (`e2e/auth.setup.ts`) logs in both roles
  and, from Plan 04 T2, seeds both fixture workbooks; the `mobile` and `desktop` projects default to `VIEWER_STATE`.
- D4 (Plan 06 T1/T4, checked against its plan text): `analytics.frames` provides `load_rounds(session)` (C7 round
  columns incl. `display_name`, `status`, `shooter_status`, `round_type`, `gauge`, `adjusted`, `residual`,
  `event_rank`, `is_best_round`, `mu_after`, `temp_f`, `gust_mph`, `precip_in`, `condition`; `event_date` as
  `datetime.date`), `load_events(session)` (incl. `head_count` and the event-weather columns `temp_f`, `gust_mph`,
  `precip_in`, `condition`), `load_station_hits(session)` (incl. `target_count`, nullable `round_id`, `hits`),
  `load_rating_history(session)` (`shooter_id`, `event_date`, `mu`, `var`), `temp_band`/`wind_band`/`precip_band`
  (`float | None` → label or `None`, NaN → `None`; labels `<40`, `40-55`, `55-70`, `70-85`, `85+`; `<10`, `10-20`,
  `20+`; `dry`, `wet`), `season_label(date)` (`winter|spring|summer|fall`), the ordered constant `SEASONS =
  ("winter", "spring", "summer", "fall")` (the engine's season sort order) and `apply_round_type_filter(df,
  round_types)`; `load_station_hits` types `round_id`/`shooter_id` as nullable `Int64` (Plan 06 Decision 5; the
  engine's `notna()` + `astype("int64")` handles both that and the float NaN of the synthetic unit frames);
  `analytics.classes.assign_classes(history, rounds, as_of)` returns `[shooter_id, mu, klass]` for active, rated
  shooters only (absent = inactive, so the left join leaves `klass` missing);
  `analytics.cache.cached_by_data_version` wraps a `f(session)` loader with `functools.wraps`, so unit tests call
  `load_explorer_frames.__wrapped__`.

**Frontend contract extensions (produced here; Plans 08–11 consume them)**
- D5 C10 client options gain `fetch: (request) => globalThis.fetch(request)`: MSW patches `fetch` at `server.listen()`,
  after modules are imported, so a client that captured `fetch` at import bypasses it (verified: `ECONNREFUSED`).
  Browsers behave identically.
- D6 Node's `fetch`/`Request` reject relative URLs (`TypeError: Failed to parse URL from /api/health`, verified with
  vitest 5.0.2, openapi-fetch 0.17.0 and msw 2.15.0). C10 makes Plan 01 T2's `test/setup.ts` the home of every jsdom
  shim and forbids editing it later, so the one statement that fixes this,
  `(globalThis as Record<symbol, unknown>)[Symbol.for('undici.globalOrigin.1')] = new URL(window.location.origin);`,
  belongs in Plan 01 T2's `setup.ts`, with a `setup.test.ts` case asserting `new Request('/api/unmocked').url` equals
  `` `${window.location.origin}/api/unmocked` `` and that `fetch('/api/unmocked')` then fails on MSW's unhandled
  request rather than on URL parsing. **Cross-plan action (controller): amend Plan 01 T2 before it runs**; its current
  `setup.ts` text lacks the line (the Plan 07 cross-plan audit filed this as a producer request against Plan 01 T2). This plan adds no second setup file and never edits
  `vitest.config.ts`: Task 4 Step 1 checks the line is present and stops BLOCKED otherwise. (Stage-run with the line in
  `setup.ts`: every Plan 07 test passes and `setup.test.ts` gains the relative-URL case.)
- D7 401 handling is an openapi-fetch middleware: a 401 from any path except `/api/auth/me`, `/api/auth/login` and
  `/api/auth/logout` (and never while on `/login`) navigates to `loginPath()` =
  `/login?next=<encodeURIComponent(pathname + search)>`; Task 4's `App.tsx` routes that through `router.navigate` via
  `setNavigate`, and Task 3 wraps it in `onSessionExpired(queryClient, …)` (D11), which first sets the session query
  to `null`, so `LoginPage` never bounces a visitor whose cookie died back to the failing page (Review Focus #1).
  `unwrap()` throws `ApiError {status, code, message}` for every non-2xx response; network errors (fetch's `TypeError`)
  propagate unchanged.
- D8 `app/providers.tsx:AppProviders({queryClient, children})` (`AppErrorBoundary` + `QueryClientProvider`) is used by
  both `App.tsx` and `test/render.tsx`, which both import `RouterProvider` from `'react-router'`, never
  `'react-router/dom'` (under vitest the two load separate module instances with separate contexts, so page hooks would
  not see the router); `app/ErrorBoundary.tsx` also exports `RouteErrorPage` (root and layout `errorElement`);
  `createQueryClient()` retries network/5xx failures twice, never a 4xx, and never refetches on focus.
- D9 `test/render.tsx` (final form, after Task 3): `createTestQueryClient()`, `renderRoutes(routes, opts)`,
  `renderRoute(route, routes = appRoutes)` (Plan 01's name, now provider-backed) and `renderWithProviders(ui, opts)`
  with `opts = {route?, path?, queryClient?, role?: 'viewer' | 'admin' | null | 'unset'}`, returning RTL's result plus
  `{user, queryClient, router}`; `role` seeds the session query (default `'viewer'`; `null` = logged out; `'unset'` =
  fetched from MSW). Helpers `test/viewport.ts:stubViewport('desktop' | 'mobile', {touch?})` (spies on `matchMedia`;
  Plan 01's `restoreMocks: true` undoes it after every test, and tests also call `vi.restoreAllMocks()` in
  `afterEach`) and `test/charts.ts:expectChartControls(region)`.
- D10 A feature route with `handle: { public: true }` renders outside `RequireRole`/`AppShell` (only `/login` today);
  every other feature route renders inside `RequireRole` → `SessionShell` → `AppShell`. Admin pages wrap their elements
  in `<RequireRole role="admin">` (Plan 08). `features/auth` has no nav item.
- D11 `features/auth/api.ts`: `type Role = 'viewer' | 'admin'`, `SESSION_QUERY_KEY = ['/api/auth/me']`,
  `fetchSession()` (401 → `null`), `useSession()`, `useLogin()` (writes the session query), `useLogout()` (every other
  cached query dropped; session → `null` only on success or a 401: the httpOnly cookie is cleared only by the server,
  so a failed logout keeps the session and `AccountPanel` shows an error), `onSessionExpired(queryClient, navigate)`
  (the `setNavigate` target in `App.tsx`: session → `null`, then navigate). Navigation after login, and for a signed-in
  visitor to `/login`, happens only in `LoginPage` via `navigate(safeNext(params.get('next')), { replace: true })`.
- D12 Task 4 also owns `lib/useMediaQuery.ts` (`useMediaQuery`, `useIsDesktop` = `(min-width: 1024px)`, `useIsTouch` =
  `(pointer: coarse)`), `lib/roundTypes.ts` (`ROUND_TYPES`, `RoundTypeValue`, `ROUND_TYPE_LABELS`, `roundTypesCodec`,
  `useRoundTypes()` bound to `rt`; `features/*/api.ts` hooks use `const [rt] = useRoundTypes()`, put `rt` in the query
  key and send it as `round_type`), `lib/download.ts` (`downloadBlob`) and `test/viewport.ts`. `shareElementAsImage`
  resolves `'shared' | 'downloaded' | 'cancelled'`; `lib/me.ts` uses localStorage key `sc.me`; `lib/csv.ts` prefixes
  text cells starting with `= + - @`, tab or CR with `'`, uses CRLF, and prepends a UTF-8 BOM on download.
- D13 `useUrlState(key, codec, default)`: missing/invalid → default; writing the default deletes the key; history
  `replace`; one setter call per event. Codecs: `stringCodec`, `intCodec`, `numberCodec`, `boolCodec` (`1`/`0`),
  `enumCodec(values)`, `listCodec(item)` (comma list; invalid and duplicate items dropped), `rangeCodec` (`lo..hi`),
  `isoDateCodec`.
- D14 `rt` is a comma list of round types; selecting all three stores "no filter"; the chip reads
  `Filtered: Sporting + Unknown` and has a "Clear round type filter" button. The filter is global across navigation:
  Task 2 adds `useRoundTypeLink(path: string): To` to `lib/roundTypes.ts` (`{pathname: path, search: '?rt=…'}`, or no
  search when unfiltered); the shell's links (SideNav, BottomTabs, the More sheet, the brand) use it, and so does every
  in-app link on a feature page (to events, shooters, …), never a bare path string. It is a hook, so list rows use a
  small link component that calls it. Drill links built per row (`ChartFrame` `rowHref`, `ChartCard` `drill`) go through
  `withRoundTypes`/`useRoundTypeHref` (Task 6), which add the current `rt` unless the href names its own.
- D15 `AppShell({isAdmin?, account?, items?})` (`isAdmin?: boolean` shows `adminOnly` items, `account?: ReactNode`,
  `items?: readonly NavItem[]` defaults to the registry's `navItems`) owns the single `<main id="main">`; pages never
  render `<main>` (only the public `/login` page, outside the shell, has its own). Desktop side nav (`w-64`) holds the
  brand, `RoundTypeFilter`, `nav[aria-label=Main]` and the account panel; mobile has `TopBar` (brand + filter),
  `nav[aria-label=Tabs]` (≤4 `mobileTab` items + "More") and a bottom `Sheet` "More" with the remaining items and the
  account panel.
  `RoundTypeFilter({align?: 'left' | 'right'})` hangs its 224 px panel from that edge (default `'left'`); `TopBar` uses
  `'right'`, because `justify-between` puts the filter at the right edge of the 390 px top bar, where a left-hung panel
  would run about 80 px off screen.
- D16 `components/charts/types.ts` also exports `Cell`, `TabularColumn`, `TabularRow`, `ColumnType`, `ChartType = 'bar'
  | 'line' | 'heatmap'` and `LeaderboardFrame {date; rows: {id; name; value; rank}[]}` (typed input of `raceOption` and
  `bumpOption`; Plan 09 T6 maps `LeaderboardHistoryOut` frames onto it). `EChart` initializes with an explicit size
  (container size, else 320 px or the numeric `height`) so jsdom and hidden containers never hit ECharts' 0×0 warning,
  and its ResizeObserver calls `chart.resize({width: 'auto', height: 'auto'})`: zrender keeps an explicit init size for
  a bare `resize()` (`canvas/Painter.js`, `helper.getSize`), so charts would never follow a rotated phone, a resized
  window or a container that was hidden at mount. `EChart` also skips `setOption` when the new option's content key
  (JSON with every function replaced by its source text) equals the last one applied, so parent re-renders (any URL
  change) never reset the user's zoom or replay the entry animation. Consequence for builders and pages: a formatter
  must read only values that are also in the option (every Task 5 builder does), because two closures with the same
  source text compare equal. `EChartEvents` keys are `click`, `dblclick`, `mouseover`, `mouseout`. Builders keep axis
  names inside the canvas: `builders/common.ts` `GRID` uses `outerBoundsMode: 'same', outerBoundsContain: 'all'`
  (ECharts 6's form of `containLabel`), so the plot shrinks until tick labels and axis names fit.
- D17 `ChartFrame` optional extras beyond C10: `controls` (a row under the header), `height` (px, default 320), `rowHref`
  (table drill link on the first text column, else the first column; the href goes through `useRoundTypeHref`, so it
  keeps `?rt=`). Buttons are named exactly `Table`, `CSV` and `Fullscreen`; view state is one query key holding `table`
  and/or `full`; `zoom` (`ZoomMode = 'x' | 'y' | 'xy' | 'none'`) defaults to `defaultZoom(option)` (`'x'` when the
  option has both axes and no calendar, `'y'` for horizontal bars — a category y axis over a non-category x axis —
  which zoom along their categories with the slider on the right). Table cells: `int` columns print as-is (years, ids,
  counts), `number` columns use grouping and ≤2 dp, null → `—`. `ChartFrame` memoizes its zoomed options (`useMemo` on
  `option`, `mode`, `isTouch`), so a frame re-rendered by another frame's URL change hands `EChart` the same object.
- D18 `ChartCard` query keys: `<urlKey>.m` metric, `.g` first group-by dim, `.t` chart type, `.b` best-round-only, `.v`
  the ChartFrame view. Chips: metrics (when >1 allowed), group-by dims (when >1 allowed), chart types (when >1), a "Best
  round only" toggle (hidden for metrics the engine rejects it with, i.e. `attendance`; a `.b` left in the URL is then
  not sent), and read-only chips for the card's own filters. A `truncated` result adds "Showing the first N rows" under
  the chips. `drill` hrefs go through `useRoundTypeHref`, as `rowHref` does. `components/charts/explore.ts` exports
  schema aliases (`QuerySpec`, `QueryResult`, `Filters`, `Metric`, `Dim`, `Agg`), label maps, `querySpec(input)` (fills
  the server defaults, because the generated types mark defaulted fields required), `useExplore(spec)` →
  `{spec, result}` (the spec that produced the shown result, so a placeholder result is never drawn, or drilled, with a
  newer grouping: `ChartCard` passes that spec's `group_by` to both `buildExploreOption` and `rowForClick`),
  `toTabular`, `buildExploreOption(data, groupBy, chartType)` and `rowForClick`. Display names are not unique
  (first-name-only guests are event-scoped new shooters, spec §2), so both chart a `shooter` name held by more than one
  `shooter_id` as `<name> #<id>`, as `race.ts` does; `rowForClick` returns the raw row, and the table and CSV keep raw
  rows.

**Explorer semantics (Task 7; C9 is silent on these)**
- D19 Units per metric: `score`/`adjusted`/`residual` one value per round; `rating` = `mu_after` of the best round per
  (shooter, event); `wins` = best rounds with `event_rank == 1` (full-field rank, C7), summed; `rounds` = round count;
  `shooters` = distinct `shooter_id`; `hit_pct` = 100·Σhits/Σtarget_count over station entries linked to a round
  (unlinked entries — `station_name_unmatched`, `station_score_missing` — are excluded); `attendance` = the event's
  `head_count`. `agg` applies to `score`, `adjusted`, `residual`, `rating` and `attendance` (SUM with `min_count=1`,
  P90 = linear quantile 0.9, STDEV = sample sd) and is ignored for `rounds`, `shooters`, `wins` and `hit_pct`.
- D20 Output columns: one per dim (key = the dim value; `shooter` adds `shooter_id` (int) before `shooter` (display
  name); `event` = ISO date typed `date`; `month` = `YYYY-MM`; `year`, `month_of_year`, `station` are ints; `status` =
  `shooter_status`; `class` = `klass`), then `value` (`int` for rounds/shooters/wins, else `number`; label
  `"<Agg> <metric>"` such as `Avg score` or `Total attendance`, or the metric label for the counts) and `n` (non-null
  unit count). Group keys are never dropped (None → JSON `null`) and NaN values serialize as `null`. `n_rounds` =
  distinct round ids behind the result (0 for attendance).
- D21 Sorting: `key_*` orders by each dim in turn — seasons winter → spring → summer → fall, weather bands by their
  label order (`frames.TEMP_BANDS`/`WIND_BANDS`/`PRECIP_BANDS`, coldest/calmest/driest first; not by the lowest
  reading in the group), shooters by display name, None last; `value_*` orders by value (None last), then by the keys
  ascending. `limit` truncates after sorting and sets `truncated`.
- D22 Filters: `date_from`/`date_to` inclusive; weather ranges inclusive and exclude rows without weather; `statuses` on
  `shooter_status`; `gauges` on `gauge` (Plan 06 maps a missing gauge class to `unspecified`); `round_types` via
  `frames.apply_round_type_filter`; `min_rounds` counts a shooter's rounds after the other filters; `best_round_only`
  keeps `is_best_round` rows. `Filters`' optional fields default to `None`, so `Filters()` is constructible as C9's
  `filters: Filters = Filters()` requires.
- D23 `invalid_query` (400) when a dim repeats, `limit < 1`, `station` is grouped with any metric but `hit_pct`,
  `hit_pct` has no linked station entries, or `attendance` is grouped by `shooter`, `gauge`, `status`, `station` or
  `class` or filtered by `shooter_ids`, `statuses`, `gauges`, `min_rounds > 0` or `best_round_only`. More than two dims
  or `limit > 5000` fail pydantic validation (422).
- D24 `load_explorer_frames` reads only Plan 06's loaders (no SQL of its own): it adds `temp_band`, `wind_band` and
  `precip_band` to the rounds and to the events (`event_date`, `round_type`, `head_count` + `WEATHER_COLUMNS`) with
  Plan 06's band functions, and adds `klass` to each round from `assign_classes(history, rounds, as_of=event_date)`,
  called once per event date that has rounds; station hits are passed through unchanged.

**Explorer page (Task 8)**
- D25 URL parameters: `m` metric (default `score`), `a` agg (`avg`), `g` group-by list (default `year`; at most 2 used),
  `from`/`to` dates, `st` statuses, `ga` gauges (`12 Gauge`, `20 Gauge`, `28 Gauge`, `.410`, `Sub-Gauge`, `SxS`,
  `unspecified`), `sh` shooter ids (set by links from other pages and shown as a removable chip; there is no shooter
  picker because `/api/shooters` (Plan 06 T6) is not a Task 8 dependency), `t`/`w`/`p` temperature/gust/rain ranges
  `lo..hi` (a full-range slider clears it), `mr` min rounds, `best` (`1`), `s` sort, `c` chart type, `v` the ChartFrame
  view, plus the global `rt`. Nav item `{label: 'Explorer', path: '/explorer', icon: Compass, order: 60}`. Result rows
  link to `/shooters/<shooter_id>` or `/events/<event>` when the first dim is `shooter` or `event`. The Filters panel
  (`<details>`) starts open when the URL carries filters and then follows only the user's toggle (local state, not
  `open={count > 0}`), so clearing the last filter never collapses it mid-edit.

**Verification against Plan 01 (2026-09-27)**
- D26 Every frontend code block in this plan was stage-run on top of Plan 01 T2/T4's files taken verbatim from its
  plan text (`package.json` set incl. `@testing-library/dom` and `typescript ~5.9.3`, `tsconfig.json` with
  `erasableSyntaxOnly`, `eslint.config.js` with `eslint-plugin-react`, `vitest.config.ts`, `test/setup.ts`,
  `test/render.tsx`, `registry.ts`, `router.tsx`, `App.tsx`, the home placeholder and their tests) and Plan 04 T1's
  `e2e/authState.ts`, in task order 1, 4, 2, 5, 3, 6, 8. After each task `vitest run --coverage` (≥90% lines and
  branches), `tsc --noEmit`, `eslint . --max-warnings 0` and `prettier --check src e2e` pass, and Plan 01's own tests
  still pass unchanged. The Task 7 backend was run the same way on pandas 3 / pydantic 2 / FastAPI with stand-ins for
  Plan 06's `frames`, `classes` and `cache`; its integration tests need Plan 03 T6's `fx_session`/`fx_viewer_client`.
  The 2026-09-27 review fixes (Tasks 2–6 and 8) were stage-run the same way on that tree, with Plan 01 T2's
  `setup.ts` carrying the D6 line: 56 files and 279 Vitest tests (Plan 01's included) pass, coverage 99% lines and 94.8%
  branches, `tsc`, eslint and prettier are clean, and every new test fails against the code it guards.

**Review fixes (2026-09-27)**
- D27 Task 3 also edits `app/App.tsx`: one call, `setNavigate(onSessionExpired(queryClient, …))` (D7, D11). C10's
  "only permitted edits" sentence restricts `router.tsx`; its App-shell list gives Plan 07 T4 the providers edit to
  `App.tsx`, and Task 3 depends on Task 4 (T3 → T4), so no parallel task touches the file; Plans 08–11 never edit
  it.
- D28 Agent shells reset the working directory between calls, so every Run command starts from the worktree root with
  `cd frontend && …` (Tasks 1–6 and 8) or `cd backend && …` (Task 7), as Plans 01 and 06 do, and every commit or
  compose block starts with `cd "$(git rev-parse --show-toplevel)"`.

## Waves
{T1, T4} → {T2, T5} → {T3 (after Plan 04 T1)}; {T7 (after Plan 06 T4)} → {T6} → {T8}.

Task N below is master Plan 07 TN (Task 1 = T1 … Task 8 = T8). Global schedule: Wave 1 runs Tasks 1 and 4, then 2
and 5; Wave 2 runs Task 3 once Plan 04 T1 has merged; Wave 3 runs Task 7 once Plan 06 T4 has merged, then Task 6, then
Task 8.

## File Structure
All frontend paths are under `frontend/`, backend paths under `backend/`.

Task 1 — design system
- `src/theme/tokens.ts` — brand colors, radii, font stack, chart palette, grid-line color (single TS source).
- `src/theme/theme.css` — Tailwind v4 entry: `@import 'tailwindcss'`, self-hosted Roboto 400/500/700, `@theme` tokens,
  dark base styles.
- `src/theme/echartsTheme.ts` — the `sunday-clays` ECharts theme built from the tokens.
- `src/theme/theme.test.ts` — contrast and brand-color guarantees.
- `src/components/ui/cx.ts` — class-name joiner.
- `src/components/ui/{Button,Card,Chip,Tabs,Stat,Skeleton,EmptyState,Sheet,Select,Slider,Toggle}.tsx` (+ one
  `*.test.tsx` each) — accessible primitives; `Slider.tsx` also exports `RangeSlider`.
- `src/main.tsx` (modify only if needed) — imports `./theme/theme.css`.

Task 4 — API client, providers and lib
- `src/api/errors.ts` — `ApiError`, `toApiError`. `src/api/client.ts` — `api`, `unwrap`, 401 middleware, `loginPath`,
  `setNavigate`, `shouldRedirectToLogin`.
- `src/app/queryClient.ts` — `createQueryClient`, `shouldRetry`. `src/app/ErrorBoundary.tsx` — `AppErrorBoundary`,
  `RouteErrorPage`. `src/app/providers.tsx` — `AppProviders`. `src/app/App.tsx` (modify) — providers + router
  navigation for 401s.
- `src/test/render.tsx` (modify) — provider-backed render helpers. `src/test/viewport.ts` — `stubViewport`. (Relative
  `/api/...` fetches in tests rely on Plan 01 T2's `test/setup.ts`, Decision D6; no setup file is added here.)
- `src/lib/useUrlState.ts` — URL state hook + codecs. `src/lib/roundTypes.ts` — global `rt` filter hook.
  `src/lib/useMediaQuery.ts` — media-query hooks. `src/lib/format.ts` — number/date/weather formatters incl.
  `formatPressure`. `src/lib/download.ts` — Blob download. `src/lib/csv.ts` — CSV build + download. `src/lib/me.ts` —
  "That's me" storage. `src/lib/share.ts` — element → PNG → share/download.
- Tests: `src/api/{errors,client}.test.ts`, `src/app/{queryClient.test.ts,providers.test.tsx}`,
  `src/lib/{useUrlState,roundTypes,useMediaQuery}.test.tsx`, `src/lib/{format,csv,me,share}.test.ts`.

Task 2 — layout
- `src/components/layout/nav.ts` — role filtering and mobile tab split. `NavList.tsx` — vertical nav links.
  `RoundTypeFilter.tsx` — global filter popover (hung from the left or right edge) + "Filtered" chip. `SideNav.tsx`,
  `TopBar.tsx`, `BottomTabs.tsx`, `AppShell.tsx` — the responsive shell (+ `nav.test.ts`, `RoundTypeFilter.test.tsx`,
  `AppShell.test.tsx`).
- `src/app/router.tsx` (modify) — inserts the `AppShell` layout route. `src/app/navRegistry.test.ts` — C10 nav
  invariants over every discovered feature. `src/app/appRoutes.test.tsx` — the real route tree renders in the shell.

Task 5 — charts
- `src/components/charts/types.ts` — `TabularData` and friends. `EChart.tsx` — ECharts wrapper (+ test).
- `src/components/charts/builders/{common,line,bar,scatter,heatmap,histogram,boxplot,calendar,race,bump,ridgeline}.ts`
  (+ one `*.test.ts` each) — pure `EChartsOption` builders.

Task 3 — auth UI
- `src/lib/safeNext.ts` (+ test) — the only `next` sanitizer.
- `src/features/auth/{api.ts,mocks.ts,routes.tsx}`, `components/{RequireRole,AccountPanel,SessionShell}.tsx`,
  `pages/LoginPage.tsx` (+ `api.test.tsx`, `RequireRole.test.tsx`, `SessionShell.test.tsx`, `LoginPage.test.tsx`).
- `src/app/router.tsx` (modify) — public routes + `RequireRole`. `src/test/render.tsx` (modify) — `role` option.
  `src/app/appRoutes.test.tsx` (modify) — signed-out redirect. `src/app/App.tsx` (modify) —
  `setNavigate(onSessionExpired(…))`. `src/features/auth/sessionExpiry.test.tsx`, `src/app/App.session.test.tsx` — a
  data request's 401 lands on `/login` and stays there.
- `e2e/login.spec.ts` — UI login/logout/next at both viewports. `e2e/smoke.spec.ts` (modify) — signed-out `/` →
  `/login`.

Task 7 — Explorer backend
- `backend/src/sunday_clays/explorer/__init__.py`, `spec.py` (C9 models), `engine.py` (`ExplorerFrames`, `run_query`,
  `load_explorer_frames`).
- `backend/src/sunday_clays/api/routes/explore.py` — `POST /api/explore`.
- `backend/tests/unit/explorer/{conftest.py,test_explorer_spec.py,test_explorer_engine.py,test_explorer_loader.py}`,
  `backend/tests/integration/explorer/test_explorer_frames.py`, `backend/tests/integration/api/test_explore_route.py`.

Task 6 — ChartFrame and ChartCard
- `src/components/charts/zoom.ts` — `withZoom`, `defaultZoom`. `DataTable.tsx` — table view. `ChartFrame.tsx` — chart +
  Table/CSV/Fullscreen. `explore.ts` — schema aliases, labels, `querySpec`, `useExplore`, adapters. `ChartCard.tsx` —
  explore controls over `POST /api/explore` (+ `zoom.test.ts`, `ChartFrame.test.tsx`, `explore.test.ts`,
  `ChartCard.test.tsx`).
- `src/test/charts.ts` — `expectChartControls`.

Task 8 — Explorer page
- `src/features/explorer/{routes.tsx,mocks.ts,urlState.ts}`, `components/{QueryControls,FilterControls}.tsx`,
  `pages/ExplorerPage.tsx` (+ `pages/ExplorerPage.test.tsx`).
- `e2e/explorer.spec.ts` — the page against the seeded fixtures at both viewports.

---

### Task 1: Theme tokens, ECharts theme and UI kit (master Plan 07 T1)

**Context.** Plan 01 T2's `frontend/` skeleton (Vite + React 19 + TypeScript strict + Tailwind v4, with Vitest,
Testing Library, jest-dom matchers, MSW and `vitest-canvas-mock` set up in `src/test/setup.ts`) is in place. This task
creates the ClaySmasher design tokens, the `sunday-clays` ECharts theme and the UI primitives every page uses. No task
may change `package.json` dependencies; everything used here (`tailwindcss@4`, `@tailwindcss/vite`,
`@fontsource/roboto`, `lucide-react`) is already installed by Plan 01 T2. Run every command from the worktree root:
frontend commands start with `cd frontend && `, and the commit step starts with `cd "$(git rev-parse --show-toplevel)"`
(agent shells reset the working directory between calls, Decision D28).

**Files:**
- Create: `frontend/src/theme/tokens.ts`, `frontend/src/theme/echartsTheme.ts`, `frontend/src/theme/theme.test.ts`
- Create or replace: `frontend/src/theme/theme.css`
- Create: `frontend/src/components/ui/cx.ts`, `Button.tsx`, `Card.tsx`, `Chip.tsx`, `Tabs.tsx`, `Stat.tsx`,
  `Skeleton.tsx`, `EmptyState.tsx`, `Sheet.tsx`, `Select.tsx`, `Slider.tsx`, `Toggle.tsx` (all in
  `frontend/src/components/ui/`)
- Test: `frontend/src/components/ui/{Button,Card,Chip,Tabs,Stat,Skeleton,EmptyState,Sheet,Select,Slider,Toggle}.test.tsx`
- Modify (only if Step 4 finds it necessary): `frontend/src/main.tsx`

**Interfaces:**
- Consumes (Plan 01 T2): Tailwind v4 via `@tailwindcss/vite`; `src/main.tsx` renders the app; `@fontsource/roboto`,
  `lucide-react` installed; Vitest + jsdom + jest-dom.
- Produces:
  - `theme/tokens.ts`: `colors = {surface, elevated, primary, primaryContainer, accent, text, textMuted, outline,
    outlineVariant, error, errorContainer}` (Global Constraints hex values), `type ColorToken`, `radii = {card: 12,
    button: 20, sheet: 16}`, `fontFamily: string`, `chartPalette` (8 hex colors, each ≥3:1 on `elevated`),
    `gridLine: string`.
  - `theme/echartsTheme.ts`: `ECHARTS_THEME_NAME = 'sunday-clays'`, `echartsTheme` (object passed to
    `registerTheme`).
  - Tailwind utilities from `theme.css`: `bg|text|border-{surface,elevated,primary,primary-container,accent,text,
    text-muted,outline,outline-variant,error,error-container}`, `rounded-card|button|sheet`, `font-sans` (Roboto).
  - `components/ui/cx.ts`: `cx(...parts: (string | false | null | undefined)[]): string`.
  - `Button(props: ButtonHTMLAttributes & {variant?: 'primary' | 'tonal' | 'ghost' | 'danger'; loading?: boolean;
    icon?: ReactNode})` — `type="button"` by default, disabled + `aria-busy` while loading, ≥44 px tap target.
  - `Card({title?, subtitle?, actions?, className?, children?})` — `<section>` named by its title (a `region`).
  - `Chip({children, selected?, onClick?, onRemove?, removeLabel?, icon?})` — toggle button (`aria-pressed`) when
    `onClick` is set, static otherwise; optional labelled remove button (default label `Remove`).
  - `Tabs<T extends string>({label, tabs: readonly {value: T; label: string}[], value: T, onChange})` — ARIA tablist,
    roving tabindex, ←/→/Home/End.
  - `Stat({label, value, delta?: number | null, formatDelta?, hint?})` — `data-trend="up|down|flat"`, visible sign
    (`+`/`−`), sr-only direction word.
  - `Skeleton({label = 'Loading', lines = 3, className?})` — `role="status"`, `aria-busy`.
  - `EmptyState({title, description?, action?, icon?})` — `h3` title.
  - `Sheet({open, onClose, title, children, placement?: 'bottom' | 'center', size?: 'auto' | 'full'})` — portal modal
    dialog: focus on open, Escape/backdrop (`data-testid="sheet-backdrop"`)/"Close" button close it, Tab trapped, body
    scroll locked, focus restored.
  - `Select<T extends string>({label, value: T, options: readonly {value: T; label: string}[], onChange, hideLabel?,
    className?})`.
  - `Slider({label, min, max, step?, value: number, onChange, format?})` and `RangeSlider({label, min, max, step?,
    value: readonly [number, number], onChange: (v: [number, number]) => void, format?})` (inputs labelled
    `<label> minimum` / `<label> maximum`; the low thumb never passes the high one).
  - `Toggle({label, checked, onChange, disabled?})` — `role="switch"`.

**Branch:** `task/07-1-theme-ui-kit` · **Depends on:** Plan 01 (T2 frontend skeleton; T5 CI).

- [ ] **Step 1: Write the failing theme test**

Create the full contents of `frontend/src/theme/theme.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { echartsTheme } from './echartsTheme';
import { chartPalette, colors } from './tokens';

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

function strings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings);
  return [];
}

describe('theme tokens', () => {
  it('body text stays readable on both surfaces and on primary buttons', () => {
    expect(contrast(colors.text, colors.surface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.text, colors.elevated)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.textMuted, colors.elevated)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(colors.text, colors.primary)).toBeGreaterThanOrEqual(4.5);
  });

  it('every chart series color keeps 3:1 contrast on the card color', () => {
    for (const color of chartPalette) {
      expect(contrast(color, colors.elevated), color).toBeGreaterThanOrEqual(3);
    }
  });

  it('the ECharts theme only uses brand token colors', () => {
    const allowed = new Set<string>([...Object.values(colors), ...chartPalette]);
    const used = strings(echartsTheme).flatMap((s) => {
      const rgba = /^rgba\((\d+),\s*(\d+),\s*(\d+),/.exec(s);
      if (rgba) {
        const hex = rgba
          .slice(1, 4)
          .map((n) => Number(n).toString(16).padStart(2, '0'))
          .join('');
        return [`#${hex.toUpperCase()}`];
      }
      return /^#[0-9a-f]{6}$/i.test(s) ? [s.toUpperCase()] : [];
    });
    expect(used.length).toBeGreaterThan(10);
    expect(used.filter((c) => !allowed.has(c))).toEqual([]);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/theme/theme.test.ts`
Expected: FAIL — `Failed to resolve import "./echartsTheme" from "src/theme/theme.test.ts"` (the module does not exist
yet).

- [ ] **Step 3: Write the tokens, the ECharts theme and the Tailwind entry**

Create the full contents of `frontend/src/theme/tokens.ts`:

```ts
/** ClaySmasher defaultBrand tokens (Global Constraints). theme.css mirrors these values. */
export const colors = {
  surface: '#1A4D2E',
  elevated: '#2D5F3F',
  primary: '#9E5530',
  primaryContainer: '#C76D3F',
  accent: '#E8A77A',
  text: '#FEFBF6',
  textMuted: '#D4E7DD',
  outline: '#D1E7DA',
  outlineVariant: '#4A7C59',
  error: '#FEE2E2',
  errorContainer: '#DC2626',
} as const;

export type ColorToken = keyof typeof colors;

/** Radii in px: card 12, button 20, sheet 16. */
export const radii = { card: 12, button: 20, sheet: 16 } as const;

export const fontFamily = "Roboto, system-ui, -apple-system, 'Segoe UI', sans-serif";

/** Chart series colors; each keeps >= 3:1 contrast on the elevated card color. */
export const chartPalette = [
  '#E8A77A',
  '#90CAF9',
  '#D1E7DA',
  '#F59E0B',
  '#CE93D8',
  '#80CBC4',
  '#FFF59D',
  '#F48FB1',
] as const;

/** Grid and split lines: outline at low opacity. */
export const gridLine = 'rgba(209, 231, 218, 0.14)';
```

Create the full contents of `frontend/src/theme/echartsTheme.ts`:

```ts
import { chartPalette, colors, fontFamily, gridLine } from './tokens';

export const ECHARTS_THEME_NAME = 'sunday-clays';

const axis = {
  axisLine: { lineStyle: { color: colors.outlineVariant } },
  axisTick: { lineStyle: { color: colors.outlineVariant } },
  axisLabel: { color: colors.textMuted },
  splitLine: { lineStyle: { color: gridLine } },
  nameTextStyle: { color: colors.textMuted },
};

/** ECharts theme registered by EChart.tsx under ECHARTS_THEME_NAME. */
export const echartsTheme = {
  color: [...chartPalette],
  backgroundColor: 'transparent',
  textStyle: { fontFamily, color: colors.textMuted },
  title: { textStyle: { color: colors.text }, subtextStyle: { color: colors.textMuted } },
  legend: { textStyle: { color: colors.text } },
  tooltip: {
    backgroundColor: colors.elevated,
    borderColor: colors.outlineVariant,
    textStyle: { color: colors.text },
  },
  categoryAxis: axis,
  valueAxis: axis,
  timeAxis: axis,
  logAxis: axis,
  dataZoom: {
    borderColor: colors.outlineVariant,
    fillerColor: 'rgba(232, 167, 122, 0.2)',
    handleStyle: { color: colors.accent, borderColor: colors.accent },
    textStyle: { color: colors.textMuted },
  },
  visualMap: { inRange: { color: [colors.elevated, colors.accent] } },
  toolbox: {
    iconStyle: { borderColor: colors.textMuted },
    emphasis: { iconStyle: { borderColor: colors.accent } },
  },
  markLine: { lineStyle: { color: colors.outline } },
};
```

Create (or replace, if Plan 01 T2 created it) the full contents of `frontend/src/theme/theme.css`:

```css
@import 'tailwindcss';
@import '@fontsource/roboto/400.css';
@import '@fontsource/roboto/500.css';
@import '@fontsource/roboto/700.css';

/* Mirrors src/theme/tokens.ts: change both together. */
@theme {
  --color-surface: #1a4d2e;
  --color-elevated: #2d5f3f;
  --color-primary: #9e5530;
  --color-primary-container: #c76d3f;
  --color-accent: #e8a77a;
  --color-text: #fefbf6;
  --color-text-muted: #d4e7dd;
  --color-outline: #d1e7da;
  --color-outline-variant: #4a7c59;
  --color-error: #fee2e2;
  --color-error-container: #dc2626;
  --font-sans: Roboto, system-ui, -apple-system, 'Segoe UI', sans-serif;
  --radius-card: 12px;
  --radius-button: 20px;
  --radius-sheet: 16px;
}

@layer base {
  html {
    color-scheme: dark;
  }

  body {
    margin: 0;
    background-color: var(--color-surface);
    color: var(--color-text);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
  }

  :focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
}
```

- [ ] **Step 4: Make `theme.css` the single Tailwind entry**

Run: `cd frontend && grep -n "\.css'" src/main.tsx`
Expected: exactly one line, `import './theme/theme.css';` (Plan 01 T2 already imports it, so nothing changes). If `main.tsx` imports a different CSS file instead (Plan 01
T2's Tailwind placeholder, e.g. `./index.css` containing only `@import 'tailwindcss';`), replace that import line with
`import './theme/theme.css';` and delete the placeholder file, so Tailwind and Roboto are loaded once, from this file.
Fonts are self-hosted by `@fontsource/roboto` (no Google Fonts or other third-party origin, so CSP `font-src 'self'`
holds).

- [ ] **Step 5: Run the theme test to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/theme/theme.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 6: Write failing tests for Button, Card and Chip**

Create the full contents of `frontend/src/components/ui/Button.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('calls onClick and defaults to type=button so it never submits a form by accident', async () => {
    const onClick = vi.fn();
    const onSubmit = vi.fn((e: SubmitEvent) => e.preventDefault());
    render(
      <form onSubmit={(e) => onSubmit(e.nativeEvent as SubmitEvent)}>
        <Button onClick={onClick}>Save</Button>
      </form>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('is disabled and busy while loading, so a second click is ignored', async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Upload
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Upload' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders the icon when not loading and honours disabled', () => {
    render(
      <Button disabled variant="danger" icon={<svg data-testid="icon" />}>
        Delete
      </Button>,
    );
    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Delete' })).not.toHaveAttribute('aria-busy');
  });
});
```

Create the full contents of `frontend/src/components/ui/Card.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Card } from './Card';

describe('Card', () => {
  it('is a region named by its title, with subtitle and actions', () => {
    render(
      <Card title="Attendance" subtitle="Since 2018" actions={<button type="button">CSV</button>}>
        body
      </Card>,
    );
    const region = screen.getByRole('region', { name: 'Attendance' });
    expect(region).toHaveTextContent('Since 2018');
    expect(region).toHaveTextContent('body');
    expect(screen.getByRole('button', { name: 'CSV' })).toBeInTheDocument();
  });

  it('renders no header and no accessible name without a title', () => {
    const { container } = render(<Card>plain</Card>);
    expect(container.querySelector('header')).toBeNull();
    expect(container.querySelector('section')).not.toHaveAttribute('aria-labelledby');
  });
});
```

Create the full contents of `frontend/src/components/ui/Chip.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Chip } from './Chip';

describe('Chip', () => {
  it('is a toggle button exposing its pressed state', async () => {
    const onClick = vi.fn();
    render(
      <Chip selected onClick={onClick}>
        Sporting
      </Chip>,
    );
    const chip = screen.getByRole('button', { name: 'Sporting' });
    expect(chip).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(chip);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is static text without onClick, and offers a labelled remove button', async () => {
    const onRemove = vi.fn();
    render(
      <Chip onRemove={onRemove} removeLabel="Clear round type filter">
        Filtered: Sporting
      </Chip>,
    );
    expect(screen.queryByRole('button', { name: 'Filtered: Sporting' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Clear round type filter' }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it('falls back to a generic remove label', () => {
    render(<Chip onRemove={() => undefined}>x</Chip>);
    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/components/ui`
Expected: FAIL — 3 test files fail with `Failed to resolve import "./Button"` (and `./Card`, `./Chip`).

- [ ] **Step 8: Implement cx, Button, Card and Chip**

Create the full contents of `frontend/src/components/ui/cx.ts`:

```ts
/** Joins truthy class names. */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}
```

Create the full contents of `frontend/src/components/ui/Button.tsx`:

```tsx
import { LoaderCircle } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from './cx';

export type ButtonVariant = 'primary' | 'tonal' | 'ghost' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-text hover:bg-primary-container',
  tonal: 'bg-elevated text-text border border-outline-variant hover:border-outline',
  ghost: 'bg-transparent text-text-muted hover:bg-elevated hover:text-text',
  danger: 'bg-error-container text-text hover:brightness-110',
};

export function Button({
  variant = 'primary',
  loading = false,
  icon,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled === true || loading}
      aria-busy={loading || undefined}
      className={cx(
        'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}
```

Create the full contents of `frontend/src/components/ui/Card.tsx`:

```tsx
import { useId, type ReactNode } from 'react';
import { cx } from './cx';

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}

export function Card({ title, subtitle, actions, className, children }: CardProps) {
  const titleId = useId();
  const hasHeader = title !== undefined || actions !== undefined;
  return (
    <section
      aria-labelledby={title === undefined ? undefined : titleId}
      className={cx('rounded-card bg-elevated p-4 text-text shadow-sm', className)}
    >
      {hasHeader && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title !== undefined && (
              <h2 id={titleId} className="truncate text-base font-medium">
                {title}
              </h2>
            )}
            {subtitle !== undefined && <p className="text-sm text-text-muted">{subtitle}</p>}
          </div>
          {actions !== undefined && (
            <div className="flex shrink-0 items-center gap-1">{actions}</div>
          )}
        </header>
      )}
      {children}
    </section>
  );
}
```

Create the full contents of `frontend/src/components/ui/Chip.tsx`:

```tsx
import { X } from 'lucide-react';
import type { ReactNode } from 'react';
import { cx } from './cx';

export interface ChipProps {
  children: ReactNode;
  selected?: boolean;
  onClick?: () => void;
  /** When set, renders a remove button labelled `removeLabel`. */
  onRemove?: () => void;
  removeLabel?: string;
  icon?: ReactNode;
}

const BASE = 'inline-flex min-h-11 items-center gap-1.5 rounded-button border px-3 text-sm';

export function Chip({
  children,
  selected = false,
  onClick,
  onRemove,
  removeLabel,
  icon,
}: ChipProps) {
  const tone = selected
    ? 'border-accent bg-accent/15 text-text'
    : 'border-outline-variant bg-transparent text-text-muted';
  const content = (
    <>
      {icon}
      {children}
    </>
  );
  return (
    <span className="inline-flex items-center">
      {onClick === undefined ? (
        <span className={cx(BASE, tone)}>{content}</span>
      ) : (
        <button type="button" aria-pressed={selected} onClick={onClick} className={cx(BASE, tone)}>
          {content}
        </button>
      )}
      {onRemove !== undefined && (
        <button
          type="button"
          aria-label={removeLabel ?? 'Remove'}
          onClick={onRemove}
          className="-ml-1 inline-flex size-11 items-center justify-center rounded-full text-text-muted hover:text-text"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      )}
    </span>
  );
}
```

- [ ] **Step 9: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/components/ui`
Expected: PASS — 3 files, 8 tests.

- [ ] **Step 10: Write failing tests for Tabs, Stat, Skeleton and EmptyState**

Create the full contents of `frontend/src/components/ui/Tabs.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { Tabs } from './Tabs';

const TABS = [
  { value: 'season', label: 'Season' },
  { value: 'rolling_12', label: 'Rolling 12' },
  { value: 'all_time', label: 'All time' },
] as const;

function Harness() {
  const [value, setValue] = useState<(typeof TABS)[number]['value']>('season');
  return (
    <>
      <Tabs label="Period" tabs={TABS} value={value} onChange={setValue} />
      <p>selected:{value}</p>
    </>
  );
}

describe('Tabs', () => {
  it('marks exactly one tab selected and makes only it tabbable', () => {
    render(<Harness />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['true', 'false', 'false']);
    expect(tabs.map((t) => t.tabIndex)).toEqual([0, -1, -1]);
    expect(screen.getByRole('tablist', { name: 'Period' })).toBeInTheDocument();
  });

  it('selects on click', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('tab', { name: 'All time' }));
    expect(screen.getByText('selected:all_time')).toBeInTheDocument();
  });

  it('moves selection and focus with arrow, Home and End keys, wrapping at the ends', async () => {
    render(<Harness />);
    screen.getByRole('tab', { name: 'Season' }).focus();
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByText('selected:all_time')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'All time' })).toHaveFocus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByText('selected:season')).toBeInTheDocument();
    await userEvent.keyboard('{End}');
    expect(screen.getByText('selected:all_time')).toBeInTheDocument();
    await userEvent.keyboard('{Home}');
    expect(screen.getByText('selected:season')).toBeInTheDocument();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByText('selected:season')).toBeInTheDocument();
  });
});
```

Create the full contents of `frontend/src/components/ui/Stat.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Stat } from './Stat';

describe('Stat', () => {
  it.each([
    [2, 'up', '+2.0'],
    [-1.54, 'down', '−1.5'],
    [0, 'flat', '0.0'],
  ])('renders delta %s as trend %s with its sign', (delta, trend, visible) => {
    const { container } = render(<Stat label="Avg" value="35.2" delta={delta} />);
    const el = container.querySelector('[data-trend]');
    expect(el).toHaveAttribute('data-trend', trend);
    expect(el).toHaveTextContent(visible);
  });

  it('tells screen readers the direction in words', () => {
    render(<Stat label="Avg" value="35.2" delta={-3} />);
    expect(screen.getByText('down', { exact: false })).toHaveClass('sr-only');
  });

  it('omits the delta when null and shows the hint', () => {
    const { container } = render(
      <Stat label="Rounds" value={120} delta={null} hint="since 2020" />,
    );
    expect(container.querySelector('[data-trend]')).toBeNull();
    expect(screen.getByText('since 2020')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
  });

  it('uses a custom delta formatter', () => {
    render(<Stat label="Rank" value={3} delta={2} formatDelta={(n) => `${n} places`} />);
    expect(screen.getByText('+2 places')).toBeInTheDocument();
  });
});
```

Create the full contents of `frontend/src/components/ui/Skeleton.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Skeleton } from './Skeleton';

describe('Skeleton', () => {
  it('announces loading with the given label and renders the requested lines', () => {
    const { container } = render(<Skeleton label="Loading chart" lines={5} />);
    expect(screen.getByRole('status', { name: 'Loading chart' })).toHaveAttribute(
      'aria-busy',
      'true',
    );
    expect(container.querySelectorAll('[data-skeleton-line]')).toHaveLength(5);
  });

  it('defaults to three lines labelled Loading', () => {
    const { container } = render(<Skeleton />);
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
    expect(container.querySelectorAll('[data-skeleton-line]')).toHaveLength(3);
  });
});
```

Create the full contents of `frontend/src/components/ui/EmptyState.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('shows title, description, icon and action', () => {
    render(
      <EmptyState
        title="No weather yet"
        description="Weather sync is off."
        icon={<svg data-testid="icon" />}
        action={<button type="button">Retry</button>}
      />,
    );
    expect(screen.getByRole('heading', { name: 'No weather yet' })).toBeInTheDocument();
    expect(screen.getByText('Weather sync is off.')).toBeInTheDocument();
    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('renders only the title when nothing else is given', () => {
    const { container } = render(<EmptyState title="Nothing here" />);
    expect(container.querySelectorAll('p')).toHaveLength(0);
    expect(screen.queryByRole('button')).toBeNull();
  });
});
```

- [ ] **Step 11: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/components/ui`
Expected: FAIL — the 4 new files fail with `Failed to resolve import "./Tabs"` (and `./Stat`, `./Skeleton`,
`./EmptyState`); the 3 files from Step 6 still pass.

- [ ] **Step 12: Implement Tabs, Stat, Skeleton and EmptyState**

Create the full contents of `frontend/src/components/ui/Tabs.tsx`:

```tsx
import { useRef, type KeyboardEvent } from 'react';
import { cx } from './cx';

export interface TabItem<T extends string> {
  value: T;
  label: string;
}

export interface TabsProps<T extends string> {
  label: string;
  tabs: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
}

export function Tabs<T extends string>({ label, tabs, value, onChange }: TabsProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = tabs.length - 1;
    const next =
      event.key === 'ArrowRight'
        ? (index + 1) % tabs.length
        : event.key === 'ArrowLeft'
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === 'Home'
            ? 0
            : event.key === 'End'
              ? last
              : null;
    const tab = next === null ? undefined : tabs[next];
    if (next === null || tab === undefined) return;
    event.preventDefault();
    onChange(tab.value);
    refs.current[next]?.focus();
  };
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto">
      {tabs.map((tab, index) => {
        const selected = tab.value === value;
        return (
          <button
            key={tab.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cx(
              'min-h-11 shrink-0 rounded-button px-4 text-sm font-medium',
              selected ? 'bg-primary text-text' : 'text-text-muted hover:bg-elevated',
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
```

Create the full contents of `frontend/src/components/ui/Stat.tsx`:

```tsx
import type { ReactNode } from 'react';
import { cx } from './cx';

export interface StatProps {
  label: string;
  value: ReactNode;
  /** Change vs a previous value; rendered with an arrow, a word for screen readers and its sign. */
  delta?: number | null;
  formatDelta?: (magnitude: number) => string;
  hint?: string;
}

const TREND = {
  up: { arrow: '▲', word: 'up', sign: '+', tone: 'text-accent' },
  down: { arrow: '▼', word: 'down', sign: '−', tone: 'text-error' },
  flat: { arrow: '■', word: 'no change', sign: '', tone: 'text-text-muted' },
} as const;

export function Stat({ label, value, delta, formatDelta = (n) => n.toFixed(1), hint }: StatProps) {
  const trend = typeof delta !== 'number' ? null : delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  return (
    <div className="flex min-w-0 flex-col">
      <span className="text-xs uppercase tracking-wide text-text-muted">{label}</span>
      <span className="text-2xl font-medium text-text">{value}</span>
      {trend !== null && typeof delta === 'number' && (
        <span data-trend={trend} className={cx('text-sm', TREND[trend].tone)}>
          <span aria-hidden="true">{TREND[trend].arrow} </span>
          <span className="sr-only">{TREND[trend].word} </span>
          <span>
            {TREND[trend].sign}
            {formatDelta(Math.abs(delta))}
          </span>
        </span>
      )}
      {hint !== undefined && <span className="text-xs text-text-muted">{hint}</span>}
    </div>
  );
}
```

Create the full contents of `frontend/src/components/ui/Skeleton.tsx`:

```tsx
import { cx } from './cx';

export interface SkeletonProps {
  label?: string;
  lines?: number;
  className?: string;
}

export function Skeleton({ label = 'Loading', lines = 3, className }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label={label}
      className={cx('flex flex-col gap-2', className)}
    >
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          data-skeleton-line=""
          className="h-4 animate-pulse rounded bg-outline-variant/40"
        />
      ))}
    </div>
  );
}
```

Create the full contents of `frontend/src/components/ui/EmptyState.tsx`:

```tsx
import type { ReactNode } from 'react';

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      {icon !== undefined && <div className="text-text-muted">{icon}</div>}
      <h3 className="text-base font-medium text-text">{title}</h3>
      {description !== undefined && (
        <p className="max-w-prose text-sm text-text-muted">{description}</p>
      )}
      {action !== undefined && <div className="mt-2">{action}</div>}
    </div>
  );
}
```

- [ ] **Step 13: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/components/ui`
Expected: PASS — 7 files, 21 tests.

- [ ] **Step 14: Write failing tests for Sheet, Select, Slider and Toggle**

Create the full contents of `frontend/src/components/ui/Sheet.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Sheet } from './Sheet';

function Harness({ onClose = vi.fn() }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        More
      </button>
      <Sheet
        open={open}
        title="More"
        placement="center"
        size="full"
        onClose={() => {
          onClose();
          setOpen(false);
        }}
      >
        <a href="/club">Club</a>
        <button type="button">Log out</button>
      </Sheet>
    </>
  );
}

describe('Sheet', () => {
  it('renders nothing while closed', () => {
    render(
      <Sheet open={false} title="x" onClose={() => undefined}>
        body
      </Sheet>,
    );
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens as a labelled modal dialog, focuses it and locks body scroll', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const dialog = screen.getByRole('dialog', { name: 'More' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('closes on Escape and restores focus and scroll', async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole('button', { name: 'More' });
    await userEvent.click(opener);
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(opener).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
  });

  it('closes from the close button and from the backdrop', async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    await userEvent.click(screen.getByTestId('sheet-backdrop'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('keeps Tab focus inside the dialog in both directions', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'More' }));
    const close = screen.getByRole('button', { name: 'Close' });
    const last = screen.getByRole('button', { name: 'Log out' });
    last.focus();
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(last).toHaveFocus();
    await userEvent.tab({ shift: true });
    expect(screen.getByRole('link', { name: 'Club' })).toHaveFocus();
  });

  it('does not trap Tab when the dialog has no focusable content', async () => {
    render(
      <Sheet open title="Empty" onClose={() => undefined}>
        text only
      </Sheet>,
    );
    const close = screen.getByRole('button', { name: 'Close' });
    close.focus();
    await userEvent.tab();
    expect(close).toHaveFocus();
  });
});
```

Create the full contents of `frontend/src/components/ui/Select.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Select } from './Select';

const OPTIONS = [
  { value: 'avg', label: 'Average' },
  { value: 'max', label: 'Best' },
] as const;

describe('Select', () => {
  it('is labelled and reports the typed value of the chosen option', async () => {
    const onChange = vi.fn();
    render(<Select label="Aggregate" value="avg" options={OPTIONS} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText('Aggregate'), 'Best');
    expect(onChange).toHaveBeenCalledWith('max');
  });

  it('can hide its label visually while keeping it accessible', () => {
    render(
      <Select
        label="Aggregate"
        hideLabel
        value="avg"
        options={OPTIONS}
        onChange={() => undefined}
      />,
    );
    expect(screen.getByText('Aggregate')).toHaveClass('sr-only');
    expect(screen.getByLabelText('Aggregate')).toHaveValue('avg');
  });
});
```

Create the full contents of `frontend/src/components/ui/Slider.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RangeSlider, Slider } from './Slider';

describe('Slider', () => {
  it('reports numeric values and shows the formatted value', () => {
    const onChange = vi.fn();
    render(
      <Slider
        label="Min rounds"
        min={0}
        max={50}
        value={5}
        onChange={onChange}
        format={(n) => `${n} rounds`}
      />,
    );
    expect(screen.getByText('5 rounds')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Min rounds'), { target: { value: '12' } });
    expect(onChange).toHaveBeenCalledWith(12);
  });

  it('shows the raw number without a formatter', () => {
    render(<Slider label="Top" min={1} max={20} value={10} onChange={() => undefined} />);
    expect(screen.getByText('10')).toBeInTheDocument();
  });
});

describe('RangeSlider', () => {
  it('moves each thumb and never lets the low thumb pass the high one', () => {
    const onChange = vi.fn();
    render(
      <RangeSlider
        label="Temperature"
        min={0}
        max={100}
        value={[40, 70]}
        onChange={onChange}
        format={(n) => `${n}°F`}
      />,
    );
    expect(screen.getByText('40°F – 70°F')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '50' } });
    expect(onChange).toHaveBeenLastCalledWith([50, 70]);
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '90' } });
    expect(onChange).toHaveBeenLastCalledWith([70, 70]);
    fireEvent.change(screen.getByLabelText('Temperature maximum'), { target: { value: '20' } });
    expect(onChange).toHaveBeenLastCalledWith([40, 40]);
    fireEvent.change(screen.getByLabelText('Temperature maximum'), { target: { value: '80' } });
    expect(onChange).toHaveBeenLastCalledWith([40, 80]);
  });

  it('shows raw numbers without a formatter', () => {
    render(
      <RangeSlider label="Gust" min={0} max={40} value={[0, 40]} onChange={() => undefined} />,
    );
    expect(screen.getByText('0 – 40')).toBeInTheDocument();
  });
});
```

Create the full contents of `frontend/src/components/ui/Toggle.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('is a switch that reports the flipped state', async () => {
    const onChange = vi.fn();
    render(<Toggle label="Best round only" checked={false} onChange={onChange} />);
    const toggle = screen.getByRole('switch', { name: 'Best round only' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    await userEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('reports false when turning off, and ignores clicks while disabled', async () => {
    const onChange = vi.fn();
    const { rerender } = render(<Toggle label="Recalibrate" checked onChange={onChange} />);
    await userEvent.click(screen.getByRole('switch', { name: 'Recalibrate' }));
    expect(onChange).toHaveBeenCalledWith(false);
    rerender(<Toggle label="Recalibrate" checked disabled onChange={onChange} />);
    await userEvent.click(screen.getByRole('switch', { name: 'Recalibrate' }));
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 15: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/components/ui`
Expected: FAIL — the 4 new files fail with `Failed to resolve import "./Sheet"` (and `./Select`, `./Slider`,
`./Toggle`); the other 7 files pass.

- [ ] **Step 16: Implement Sheet, Select, Slider and Toggle**

Create the full contents of `frontend/src/components/ui/Sheet.tsx`:

```tsx
import { X } from 'lucide-react';
import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cx } from './cx';

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** 'bottom' slides up from the bottom edge (mobile); 'center' is a centered dialog (desktop). */
  placement?: 'bottom' | 'center';
  /** 'full' uses (almost) the whole viewport, e.g. fullscreen charts. */
  size?: 'auto' | 'full';
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function trapTab(event: KeyboardEvent<HTMLDivElement>, panel: HTMLDivElement | null) {
  const items = panel ? [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)] : [];
  const first = items[0];
  const last = items[items.length - 1];
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function Sheet({
  open,
  onClose,
  title,
  children,
  placement = 'bottom',
  size = 'auto',
}: SheetProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panelRef.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open]);

  if (!open) return null;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
    } else if (event.key === 'Tab') {
      trapTab(event, panelRef.current);
    }
  };

  return createPortal(
    <div
      className={cx(
        'fixed inset-0 z-50 flex',
        placement === 'bottom' ? 'items-end' : 'items-center justify-center p-6',
      )}
    >
      <div
        data-testid="sheet-backdrop"
        aria-hidden="true"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={cx(
          'relative flex max-h-full w-full flex-col bg-elevated text-text shadow-xl outline-none',
          placement === 'bottom' ? 'rounded-t-sheet' : 'max-w-5xl rounded-sheet',
          size === 'full' && (placement === 'bottom' ? 'h-[95dvh]' : 'h-[90dvh]'),
        )}
      >
        <header className="flex items-center justify-between gap-2 border-b border-outline-variant px-4 py-2">
          <h2 id={titleId} className="text-base font-medium">
            {title}
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="inline-flex size-11 items-center justify-center rounded-full text-text-muted hover:bg-surface hover:text-text"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
```

Create the full contents of `frontend/src/components/ui/Select.tsx`:

```tsx
import { useId, type ChangeEvent } from 'react';
import { cx } from './cx';

export interface SelectOption<T extends string> {
  value: T;
  label: string;
}

export interface SelectProps<T extends string> {
  label: string;
  value: T;
  options: readonly SelectOption<T>[];
  onChange: (value: T) => void;
  hideLabel?: boolean;
  className?: string;
}

export function Select<T extends string>({
  label,
  value,
  options,
  onChange,
  hideLabel = false,
  className,
}: SelectProps<T>) {
  const id = useId();
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const option = options.find((o) => o.value === event.target.value);
    if (option) onChange(option.value);
  };
  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <label htmlFor={id} className={cx('text-xs text-text-muted', hideLabel && 'sr-only')}>
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={handleChange}
        className="min-h-11 rounded-button border border-outline-variant bg-surface px-3 text-sm text-text"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
```

Create the full contents of `frontend/src/components/ui/Slider.tsx`:

```tsx
import { useId } from 'react';

interface BaseProps {
  label: string;
  min: number;
  max: number;
  step?: number;
  format?: (value: number) => string;
}

export interface SliderProps extends BaseProps {
  value: number;
  onChange: (value: number) => void;
}

export interface RangeSliderProps extends BaseProps {
  value: readonly [number, number];
  onChange: (value: [number, number]) => void;
}

const INPUT = 'h-11 w-full accent-accent';
const plain = (n: number) => String(n);

export function Slider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  format = plain,
}: SliderProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs text-text-muted">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{format(value)}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={INPUT}
      />
    </div>
  );
}

/** Two native range inputs; the low thumb never passes the high one. */
export function RangeSlider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  format = plain,
}: RangeSliderProps) {
  const [lo, hi] = value;
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="flex w-full justify-between text-xs text-text-muted">
        <span>{label}</span>
        <span>
          {format(lo)} – {format(hi)}
        </span>
      </legend>
      <input
        type="range"
        aria-label={`${label} minimum`}
        min={min}
        max={max}
        step={step}
        value={lo}
        onChange={(e) => onChange([Math.min(Number(e.target.value), hi), hi])}
        className={INPUT}
      />
      <input
        type="range"
        aria-label={`${label} maximum`}
        min={min}
        max={max}
        step={step}
        value={hi}
        onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo)])}
        className={INPUT}
      />
    </fieldset>
  );
}
```

Create the full contents of `frontend/src/components/ui/Toggle.tsx`:

```tsx
import { cx } from './cx';

export interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

export function Toggle({ label, checked, onChange, disabled = false }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex min-h-11 items-center gap-3 text-sm text-text disabled:opacity-50"
    >
      <span
        aria-hidden="true"
        className={cx(
          'relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors',
          checked ? 'bg-primary' : 'bg-outline-variant',
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 size-5 rounded-full bg-text transition-transform',
            checked ? 'translate-x-5' : 'translate-x-0.5',
          )}
        />
      </span>
      {label}
    </button>
  );
}
```

- [ ] **Step 17: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/components/ui src/theme`
Expected: PASS — 12 files, 38 tests, and no `stderr` output.

- [ ] **Step 18: Full suite, coverage, lint, types, format and build**

Run: `cd frontend && pnpm exec prettier --write src/theme src/components/ui src/main.tsx`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; the coverage summary shows ≥90% lines and ≥90% branches (the thresholds in
`vitest.config.ts` fail the run otherwise); `src/components/ui` and `src/theme` are above 90% each.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings.
Run: `cd frontend && pnpm build`
Expected: the build succeeds and `dist/assets/` contains `roboto-latin-400-normal-*.woff2` (fonts are self-hosted).

- [ ] **Step 19: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/theme frontend/src/components/ui frontend/src/main.tsx
git commit -F - <<'MSG'
feat(frontend): ClaySmasher theme tokens, ECharts theme and UI kit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```
(If Step 4 deleted a Tailwind placeholder file, `git add -A frontend/src` instead so the deletion is committed.)

### Task 2: Layout shell, navigation and global round-type filter (master Plan 07 T2)

**Context.** Task 1 (`components/ui/*`, theme) and Task 4 (`lib/useMediaQuery.ts`,
`lib/roundTypes.ts`, `app/ErrorBoundary.tsx`, `test/render.tsx` with `renderRoutes`, `test/viewport.ts`) have merged.
This task builds the responsive `AppShell` layout route (C10: side nav at ≥1024 px; top bar + 4 bottom tabs + "More"
below), the global round-type filter with its 'Filtered' chip, a registry test that enforces the C10 mobile tabs and nav
orders for every feature that will ever be added, and the one permitted `router.tsx` edit that inserts the layout route.
Nav items come only from the feature registry (`src/app/registry.ts`, Plan 01 T2) — never edit `router.tsx` to add a
page. The mobile top bar puts the filter at the right edge of a 390 px screen, so there its panel hangs from the right
edge (`align="right"`) and stays on screen. Run every command from the worktree root: frontend commands start with
`cd frontend && `, and the commit step starts with `cd "$(git rev-parse --show-toplevel)"` (agent shells reset the
working directory between calls, Decision D28).

**Files:**
- Create: `frontend/src/components/layout/nav.ts`, `NavList.tsx`, `RoundTypeFilter.tsx`, `SideNav.tsx`, `TopBar.tsx`,
  `BottomTabs.tsx`, `AppShell.tsx` (all in `frontend/src/components/layout/`)
- Test: `frontend/src/components/layout/nav.test.ts`, `RoundTypeFilter.test.tsx`, `AppShell.test.tsx`
- Create: `frontend/src/app/navRegistry.test.ts`, `frontend/src/app/appRoutes.test.tsx`
- Modify: `frontend/src/app/router.tsx` (C10: Plan 07 T2 inserts the AppShell layout route)
- Modify: `frontend/src/lib/roundTypes.ts`, `frontend/src/lib/roundTypes.test.tsx` (`useRoundTypeLink`, Decision D14)

**Interfaces:**
- Consumes:
  - Plan 01 T2 `src/app/registry.ts`: `interface NavItem {label: string; path: string; icon: LucideIcon; order: number;
    mobileTab?: boolean; adminOnly?: boolean}`, `interface FeatureModule {routes: RouteObject[]; nav?: NavItem[]}`,
    `featureRoutes: RouteObject[]`, `navItems: NavItem[]` (sorted by `order`); `src/app/router.tsx` exporting
    `appRoutes` and `createAppRouter()`; `features/home/routes.tsx`.
  - Task 1: `Chip`, `Sheet`, `cx`. Task 4: `useIsDesktop(): boolean`; `useRoundTypes(): [RoundTypeValue[], (next:
    RoundTypeValue[]) => void]`, `ROUND_TYPES`, `ROUND_TYPE_LABELS`, `RoundTypeValue`; `RouteErrorPage`;
    `renderRoutes(routes, {route?})` and `renderWithProviders(ui, {route?})` returning `{user, router, …}`;
    `stubViewport('desktop' | 'mobile')`.
- Produces:
  - `components/layout/nav.ts`: `visibleNav(items: readonly NavItem[], isAdmin: boolean): NavItem[]`,
    `splitMobileNav(items: readonly NavItem[]): {tabs: NavItem[]; more: NavItem[]}`.
  - `AppShell(props: {isAdmin?: boolean; account?: ReactNode; items?: readonly NavItem[]})` — layout route rendering
    `<Outlet />` in `<main id="main">`; desktop: `SideNav` (`aside` with brand, `RoundTypeFilter`,
    `nav[aria-label="Main"]`, `account`); mobile: `TopBar` (brand + `RoundTypeFilter`), `BottomTabs`
    (`nav[aria-label="Tabs"]`, ≤4 `mobileTab` links + a "More" button) and a bottom `Sheet` titled "More" holding
    `nav[aria-label="More"]` and `account`. `adminOnly` items appear only when `isAdmin`.
  - `RoundTypeFilter({align = 'left'}: {align?: 'left' | 'right'})` — "Round type" button (`aria-expanded`) opening a
    `group` "Round types" (hung from the `align` edge: `left-0` or `right-0`) with checkboxes Sporting / Super
    Sporting / Unknown bound to `?rt=`; while active shows the chip `Filtered: <A> + <B>` with a "Clear round type
    filter" button; selecting all three clears the filter.
  - `NavList({items, onNavigate?})`, `SideNav({items, account?})` (default `RoundTypeFilter`), `TopBar()` (renders
    `<RoundTypeFilter align="right" />`), `BottomTabs({tabs, moreOpen, onMore})`.
  - `lib/roundTypes.ts`: `useRoundTypeLink(path: string): To` — a link target for `path` that keeps the global `?rt=`
    (encoded as `useRoundTypes` writes it; no search when unfiltered). Every shell link (nav items, tabs, the More
    sheet, the brand) uses it, and so does every in-app link on a feature page (Decision D14, C10).
  - `app/router.tsx`: `appRoutes = [{path: '/', HydrateFallback: () => null, errorElement: <RouteErrorPage/>, children: [{element: <AppShell/>,
    children: [{errorElement: <RouteErrorPage/>, children: featureRoutes}]}]}]`, `createAppRouter()` unchanged in
    name.

**Branch:** `task/07-2-app-shell` · **Depends on:** Plan 07 T1, Plan 07 T4.

- [ ] **Step 1: Write the failing nav helper test**

Create the full contents of `frontend/src/components/layout/nav.test.ts`:

```ts
import { Building2, CalendarDays, Compass, House, Settings, Trophy, Users } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import type { NavItem } from '../../app/registry';
import { splitMobileNav, visibleNav } from './nav';

const ITEMS: NavItem[] = [
  { label: 'Explorer', path: '/explorer', icon: Compass, order: 60 },
  { label: 'Home', path: '/', icon: House, order: 10, mobileTab: true },
  { label: 'Imports', path: '/admin/imports', icon: Settings, order: 900, adminOnly: true },
  { label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30, mobileTab: true },
  { label: 'Shooters', path: '/shooters', icon: Users, order: 40, mobileTab: true },
  { label: 'Events', path: '/events', icon: CalendarDays, order: 20, mobileTab: true },
  { label: 'Club', path: '/club', icon: Building2, order: 50 },
];

describe('visibleNav', () => {
  it('hides admin-only items from viewers and sorts by order', () => {
    expect(visibleNav(ITEMS, false).map((i) => i.label)).toEqual([
      'Home',
      'Events',
      'Leaderboards',
      'Shooters',
      'Club',
      'Explorer',
    ]);
  });

  it('shows admin-only items to admins', () => {
    expect(visibleNav(ITEMS, true).map((i) => i.label)).toContain('Imports');
  });
});

describe('splitMobileNav', () => {
  it('puts the mobile tabs in the tab bar and the rest in More', () => {
    const { tabs, more } = splitMobileNav(visibleNav(ITEMS, true));
    expect(tabs.map((i) => i.label)).toEqual(['Home', 'Events', 'Leaderboards', 'Shooters']);
    expect(more.map((i) => i.label)).toEqual(['Club', 'Explorer', 'Imports']);
  });

  it('never shows more than four tabs', () => {
    const extra = { label: 'Extra', path: '/extra', icon: Compass, order: 150, mobileTab: true };
    const { tabs, more } = splitMobileNav(visibleNav([...ITEMS, extra], false));
    expect(tabs).toHaveLength(4);
    expect(more.map((i) => i.label)).toContain('Extra');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/layout/nav.test.ts`
Expected: FAIL — `Failed to resolve import "./nav"`.

- [ ] **Step 3: Implement the nav helpers**

Create the full contents of `frontend/src/components/layout/nav.ts`:

```ts
import type { NavItem } from '../../app/registry';

/** Items the current role may see, in C10 `order`. */
export function visibleNav(items: readonly NavItem[], isAdmin: boolean): NavItem[] {
  return items
    .filter((item) => isAdmin || item.adminOnly !== true)
    .sort((a, b) => a.order - b.order);
}

/** Mobile: the (at most 4) `mobileTab` items become bottom tabs; everything else goes to "More". */
export function splitMobileNav(items: readonly NavItem[]): { tabs: NavItem[]; more: NavItem[] } {
  const tabs = items.filter((item) => item.mobileTab === true).slice(0, 4);
  return { tabs, more: items.filter((item) => !tabs.includes(item)) };
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/layout/nav.test.ts`
Expected: PASS — 4 tests.

- [ ] **Step 5: Write the failing RoundTypeFilter test**

Create the full contents of `frontend/src/components/layout/RoundTypeFilter.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { RoundTypeFilter } from './RoundTypeFilter';

function setup(route = '/') {
  return renderWithProviders(
    <>
      <RoundTypeFilter />
      <p>outside</p>
    </>,
    { route },
  );
}

describe('RoundTypeFilter', () => {
  it('shows no Filtered chip while no round type is selected', () => {
    setup();
    expect(screen.queryByText(/Filtered:/)).toBeNull();
  });

  it('writes the selection to ?rt= and shows the Filtered chip', async () => {
    const { user, router } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    expect(router.state.location.search).toBe('?rt=sporting');
    expect(screen.getByText('Filtered: Sporting')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Unknown' }));
    expect(router.state.location.search).toBe('?rt=sporting%2Cunknown');
    expect(screen.getByText('Filtered: Sporting + Unknown')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    expect(router.state.location.search).toBe('?rt=unknown');
  });

  it('reads the filter from the URL and clears it from the chip', async () => {
    const { user, router } = setup('/?rt=super_sporting');
    expect(screen.getByText('Filtered: Super Sporting')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Clear round type filter' }));
    expect(router.state.location.search).toBe('');
    expect(screen.queryByText(/Filtered:/)).toBeNull();
  });

  it('treats selecting every round type as no filter', async () => {
    const { user, router } = setup('/?rt=sporting,super_sporting');
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.click(screen.getByRole('checkbox', { name: 'Unknown' }));
    expect(router.state.location.search).toBe('');
  });

  it('closes on Escape and on a click outside', async () => {
    const { user } = setup();
    const trigger = screen.getByRole('button', { name: 'Round type' });
    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
    await user.click(trigger);
    await user.click(screen.getByRole('checkbox', { name: 'Sporting' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
    await user.click(trigger);
    await user.click(screen.getByText('outside'));
    expect(screen.queryByRole('group', { name: 'Round types' })).toBeNull();
  });

  it('hangs the panel from the left edge by default and from the right edge when asked', async () => {
    const { user, unmount } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expect(screen.getByRole('group', { name: 'Round types' })).toHaveClass('left-0');
    unmount();
    const right = renderWithProviders(<RoundTypeFilter align="right" />);
    await right.user.click(screen.getByRole('button', { name: 'Round type' }));
    const panel = screen.getByRole('group', { name: 'Round types' });
    expect(panel).toHaveClass('right-0');
    expect(panel).not.toHaveClass('left-0');
  });

  it('stays open for clicks inside the panel', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    await user.click(screen.getByRole('group', { name: 'Round types' }));
    expect(screen.getByRole('group', { name: 'Round types' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/layout/RoundTypeFilter.test.tsx`
Expected: FAIL — `Failed to resolve import "./RoundTypeFilter"`.

- [ ] **Step 7: Implement RoundTypeFilter**

Create the full contents of `frontend/src/components/layout/RoundTypeFilter.tsx`:

```tsx
import { Filter } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import {
  ROUND_TYPE_LABELS,
  ROUND_TYPES,
  useRoundTypes,
  type RoundTypeValue,
} from '../../lib/roundTypes';
import { Chip } from '../ui/Chip';
import { cx } from '../ui/cx';

/**
 * The global round-type filter (C10): a checkbox popover bound to `?rt=` plus a 'Filtered' chip.
 * `align` picks the edge the panel hangs from; the mobile TopBar puts the filter at the right
 * edge of a 390px screen, so it opens its panel leftwards ('right').
 */
export function RoundTypeFilter({ align = 'left' }: { align?: 'left' | 'right' }) {
  const [selected, setSelected] = useRoundTypes();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  const toggle = (value: RoundTypeValue) => {
    const next = ROUND_TYPES.filter((t) =>
      t === value ? !selected.includes(t) : selected.includes(t),
    );
    // All three selected filters nothing out, so store it as "no filter".
    setSelected(next.length === ROUND_TYPES.length ? [] : next);
  };

  return (
    <div ref={rootRef} className="relative flex flex-wrap items-center gap-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
        className="inline-flex min-h-11 items-center gap-2 rounded-button border border-outline-variant px-3 text-sm text-text-muted hover:text-text"
      >
        <Filter aria-hidden="true" className="size-4" />
        Round type
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label="Round types"
          onKeyDown={(event) => {
            if (event.key === 'Escape') setOpen(false);
          }}
          className={cx(
            'absolute top-full z-40 mt-1 flex w-56 flex-col rounded-card border border-outline-variant bg-elevated p-2 shadow-xl',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {ROUND_TYPES.map((value) => (
            <label key={value} className="flex min-h-11 items-center gap-3 px-2 text-sm text-text">
              <input
                type="checkbox"
                checked={selected.includes(value)}
                onChange={() => toggle(value)}
                className="size-4 accent-accent"
              />
              {ROUND_TYPE_LABELS[value]}
            </label>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <Chip selected onRemove={() => setSelected([])} removeLabel="Clear round type filter">
          Filtered: {selected.map((t) => ROUND_TYPE_LABELS[t]).join(' + ')}
        </Chip>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/layout/RoundTypeFilter.test.tsx`
Expected: PASS — 7 tests.

- [ ] **Step 9: Write the failing AppShell test (desktop and mobile)**

Create the full contents of `frontend/src/components/layout/AppShell.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { CalendarDays, Compass, House, Settings, Trophy, Users } from 'lucide-react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { NavItem } from '../../app/registry';
import { renderRoutes } from '../../test/render';
import { stubViewport } from '../../test/viewport';
import { AppShell, type AppShellProps } from './AppShell';

const ITEMS: NavItem[] = [
  { label: 'Home', path: '/', icon: House, order: 10, mobileTab: true },
  { label: 'Events', path: '/events', icon: CalendarDays, order: 20, mobileTab: true },
  { label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30, mobileTab: true },
  { label: 'Shooters', path: '/shooters', icon: Users, order: 40, mobileTab: true },
  { label: 'Explorer', path: '/explorer', icon: Compass, order: 60 },
  { label: 'Imports', path: '/admin/imports', icon: Settings, order: 900, adminOnly: true },
];

function renderShell(route: string, props: AppShellProps = {}) {
  return renderRoutes(
    [
      {
        path: '/',
        element: <AppShell items={ITEMS} {...props} />,
        children: [
          { index: true, element: <p>home page</p> },
          { path: 'explorer', element: <p>explorer page</p> },
          { path: 'events', element: <p>events page</p> },
        ],
      },
    ],
    { route },
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AppShell on desktop', () => {
  it('renders the side nav with every visible item and the page in main', () => {
    stubViewport('desktop');
    renderShell('/explorer', { account: <button type="button">Log out</button> });
    const nav = screen.getByRole('navigation', { name: 'Main' });
    expect(
      within(nav)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Home', 'Events', 'Leaderboards', 'Shooters', 'Explorer']);
    expect(within(nav).getByRole('link', { name: 'Explorer' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByRole('main')).toHaveTextContent('explorer page');
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Tabs' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Round type' })).toBeInTheDocument();
  });

  it('shows admin-only items only to admins', () => {
    stubViewport('desktop');
    renderShell('/', { isAdmin: true });
    expect(screen.getByRole('link', { name: 'Imports' })).toBeInTheDocument();
  });
});

describe('AppShell on mobile', () => {
  it('renders exactly the four mobile tabs plus More, and no side nav', () => {
    stubViewport('mobile');
    renderShell('/');
    const tabs = screen.getByRole('navigation', { name: 'Tabs' });
    expect(
      within(tabs)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Home', 'Events', 'Leaderboards', 'Shooters']);
    expect(within(tabs).getByRole('button', { name: 'More' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.queryByRole('navigation', { name: 'Main' })).toBeNull();
    expect(screen.getByRole('main')).toHaveTextContent('home page');
  });

  it('opens the top-bar round-type panel leftwards so it stays on a phone screen', async () => {
    stubViewport('mobile');
    const { user } = renderShell('/');
    await user.click(screen.getByRole('button', { name: 'Round type' }));
    expect(screen.getByRole('group', { name: 'Round types' })).toHaveClass('right-0');
  });

  it('opens the More sheet with the remaining items and account, and closes it on navigation', async () => {
    stubViewport('mobile');
    const { user, router } = renderShell('/', { account: <button type="button">Log out</button> });
    await user.click(screen.getByRole('button', { name: 'More' }));
    const sheet = screen.getByRole('dialog', { name: 'More' });
    expect(
      within(sheet)
        .getAllByRole('link')
        .map((a) => a.textContent),
    ).toEqual(['Explorer']);
    expect(within(sheet).getByRole('button', { name: 'Log out' })).toBeInTheDocument();
    await user.click(within(sheet).getByRole('link', { name: 'Explorer' }));
    expect(router.state.location.pathname).toBe('/explorer');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.getByRole('main')).toHaveTextContent('explorer page');
  });

  it('shows admin-only items in More for admins', async () => {
    stubViewport('mobile');
    const { user } = renderShell('/', { isAdmin: true });
    await user.click(screen.getByRole('button', { name: 'More' }));
    expect(
      within(screen.getByRole('dialog', { name: 'More' })).getByRole('link', { name: 'Imports' }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 10: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/layout/AppShell.test.tsx`
Expected: FAIL — `Failed to resolve import "./AppShell"`.

- [ ] **Step 11: Implement NavList, SideNav, TopBar, BottomTabs and AppShell**

Create the full contents of `frontend/src/components/layout/NavList.tsx`:

```tsx
import { NavLink } from 'react-router';
import type { NavItem } from '../../app/registry';
import { cx } from '../ui/cx';

/** Vertical list of nav links (side nav and the "More" sheet). */
export function NavList({
  items,
  onNavigate,
}: {
  items: readonly NavItem[];
  onNavigate?: () => void;
}) {
  return (
    <ul className="flex flex-col gap-1">
      {items.map(({ path, label, icon: Icon }) => (
        <li key={path}>
          <NavLink
            to={path}
            end={path === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                'flex min-h-11 items-center gap-3 rounded-button px-4 text-sm',
                isActive
                  ? 'bg-primary text-text'
                  : 'text-text-muted hover:bg-surface hover:text-text',
              )
            }
          >
            <Icon aria-hidden="true" className="size-5" />
            {label}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}
```

Create the full contents of `frontend/src/components/layout/SideNav.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Link } from 'react-router';
import type { NavItem } from '../../app/registry';
import { NavList } from './NavList';
import { RoundTypeFilter } from './RoundTypeFilter';

/** Desktop (≥1024px) fixed left navigation. */
export function SideNav({ items, account }: { items: readonly NavItem[]; account?: ReactNode }) {
  return (
    <aside className="fixed inset-y-0 left-0 flex w-64 flex-col gap-4 border-r border-outline-variant bg-elevated p-4">
      <Link to="/" className="px-2 text-lg font-bold text-text">
        Sunday Clays
      </Link>
      <RoundTypeFilter />
      <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto">
        <NavList items={items} />
      </nav>
      {account !== undefined && (
        <div className="border-t border-outline-variant pt-3">{account}</div>
      )}
    </aside>
  );
}
```

Create the full contents of `frontend/src/components/layout/TopBar.tsx`:

```tsx
import { Link } from 'react-router';
import { RoundTypeFilter } from './RoundTypeFilter';

/** Mobile (<1024px) top bar: brand and the global round-type filter. */
export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant bg-surface/95 px-4 py-2 backdrop-blur">
      <Link to="/" className="text-base font-bold text-text">
        Sunday Clays
      </Link>
      <RoundTypeFilter align="right" />
    </header>
  );
}
```

Create the full contents of `frontend/src/components/layout/BottomTabs.tsx`:

```tsx
import { Ellipsis } from 'lucide-react';
import { NavLink } from 'react-router';
import type { NavItem } from '../../app/registry';
import { cx } from '../ui/cx';

const TAB = 'flex min-h-14 min-w-11 flex-1 flex-col items-center justify-center gap-0.5 text-xs';

/** Mobile bottom tab bar: the C10 mobile tabs, then "More". */
export function BottomTabs({
  tabs,
  moreOpen,
  onMore,
}: {
  tabs: readonly NavItem[];
  moreOpen: boolean;
  onMore: () => void;
}) {
  return (
    <nav
      aria-label="Tabs"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-outline-variant bg-elevated pb-[env(safe-area-inset-bottom)]"
    >
      {tabs.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          end={path === '/'}
          className={({ isActive }) => cx(TAB, isActive ? 'text-accent' : 'text-text-muted')}
        >
          <Icon aria-hidden="true" className="size-5" />
          {label}
        </NavLink>
      ))}
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={moreOpen}
        onClick={onMore}
        className={cx(TAB, 'text-text-muted')}
      >
        <Ellipsis aria-hidden="true" className="size-5" />
        More
      </button>
    </nav>
  );
}
```

Create the full contents of `frontend/src/components/layout/AppShell.tsx`:

```tsx
import { useState, type ReactNode } from 'react';
import { Outlet } from 'react-router';
import { navItems, type NavItem } from '../../app/registry';
import { useIsDesktop } from '../../lib/useMediaQuery';
import { Sheet } from '../ui/Sheet';
import { BottomTabs } from './BottomTabs';
import { NavList } from './NavList';
import { SideNav } from './SideNav';
import { TopBar } from './TopBar';
import { splitMobileNav, visibleNav } from './nav';

export interface AppShellProps {
  /** Shows `adminOnly` nav items. */
  isAdmin?: boolean;
  /** Account controls (e.g. log out), shown in the side nav and in the "More" sheet. */
  account?: ReactNode;
  /** Defaults to the feature registry's nav items. */
  items?: readonly NavItem[];
}

const SKIP_LINK =
  'sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-button focus:bg-primary focus:px-4 focus:py-2';

/** Layout route (C10): side nav at ≥1024px; top bar + bottom tabs + "More" sheet below. */
export function AppShell({ isAdmin = false, account, items = navItems }: AppShellProps) {
  const isDesktop = useIsDesktop();
  const [moreOpen, setMoreOpen] = useState(false);
  const visible = visibleNav(items, isAdmin);

  if (isDesktop) {
    return (
      <div className="min-h-dvh">
        <a href="#main" className={SKIP_LINK}>
          Skip to content
        </a>
        <SideNav items={visible} account={account} />
        <main id="main" className="min-w-0 pl-64">
          <div className="mx-auto max-w-7xl p-6">
            <Outlet />
          </div>
        </main>
      </div>
    );
  }

  const { tabs, more } = splitMobileNav(visible);
  const close = () => setMoreOpen(false);
  return (
    <div className="min-h-dvh">
      <a href="#main" className={SKIP_LINK}>
        Skip to content
      </a>
      <TopBar />
      <main id="main" className="min-w-0 px-4 pb-24 pt-4">
        <Outlet />
      </main>
      <BottomTabs tabs={tabs} moreOpen={moreOpen} onMore={() => setMoreOpen(true)} />
      <Sheet open={moreOpen} onClose={close} title="More">
        <nav aria-label="More">
          <NavList items={more} onNavigate={close} />
        </nav>
        {account !== undefined && (
          <div className="mt-4 border-t border-outline-variant pt-4">{account}</div>
        )}
      </Sheet>
    </div>
  );
}
```

- [ ] **Step 12: Run the layout tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/components/layout`
Expected: PASS — 3 files, 17 tests.

- [ ] **Step 13: Write the registry guard test and watch it catch a violation**

Create the full contents of `frontend/src/app/navRegistry.test.ts`:

```ts
import { matchRoutes } from 'react-router';
import { describe, expect, it } from 'vitest';
import { featureRoutes, navItems, type FeatureModule } from './registry';

/** C10: fixed nav orders; any other feature takes an unused value >= 140. */
const FIXED_ORDER: Record<string, number> = {
  home: 10,
  events: 20,
  leaderboards: 30,
  shooters: 40,
  club: 50,
  explorer: 60,
  achievements: 70,
  stations: 80,
  weather: 90,
  compare: 100,
  yir: 110,
  records: 120,
  race: 130,
  admin: 900,
  'admin-identity': 910,
  'admin-ops': 920,
};
/** C10: exactly these features are mobile tabs. */
const MOBILE_TABS = new Set(['home', 'events', 'leaderboards', 'shooters']);

const modules = import.meta.glob<FeatureModule>('../features/*/routes.tsx', { eager: true });
const features = Object.entries(modules).map(([file, mod]) => ({
  name: /features\/([^/]+)\/routes\.tsx$/.exec(file)?.[1] ?? file,
  nav: mod.nav ?? [],
}));

describe('feature registry', () => {
  it('discovers at least the home feature', () => {
    expect(features.map((f) => f.name)).toContain('home');
  });

  it('uses the C10 nav order for listed features and an unused order >= 140 otherwise', () => {
    const used = new Map<number, string>();
    for (const { name, nav } of features) {
      for (const item of nav) {
        const fixed = FIXED_ORDER[name];
        if (fixed === undefined) {
          expect(item.order, `${name} order`).toBeGreaterThanOrEqual(140);
          expect(Object.values(FIXED_ORDER), `${name} order`).not.toContain(item.order);
        } else {
          expect(item.order, `${name} order`).toBe(fixed);
        }
        const owner = used.get(item.order);
        expect(
          owner === undefined || owner === name,
          `order ${item.order} shared by ${owner} and ${name}`,
        ).toBe(true);
        used.set(item.order, name);
      }
    }
  });

  it('lets only home, events, leaderboards and shooters be mobile tabs', () => {
    const tabFeatures = features
      .filter((f) => f.nav.some((i) => i.mobileTab === true))
      .map((f) => f.name);
    expect(tabFeatures.filter((name) => !MOBILE_TABS.has(name))).toEqual([]);
  });

  it('marks every admin feature nav item adminOnly', () => {
    for (const { name, nav } of features.filter((f) => f.name.startsWith('admin'))) {
      for (const item of nav) expect(item.adminOnly, `${name} ${item.label}`).toBe(true);
    }
  });

  it('points every nav item at a registered route', () => {
    const tree = [{ path: '/', children: featureRoutes }];
    for (const item of navItems) {
      expect(matchRoutes(tree, item.path), item.path).not.toBeNull();
    }
  });

  it('exposes nav items sorted by order', () => {
    const orders = navItems.map((i) => i.order);
    expect(orders).toEqual([...orders].sort((a, b) => a - b));
  });
});
```

This test guards features that do not exist yet (Plans 08–11), so it passes against today's registry. Prove it can
fail: create a throwaway `frontend/src/features/zz-probe/routes.tsx` containing

```tsx
import { Compass } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [{ path: 'zz-probe', element: null }];
export const nav: NavItem[] = [
  { label: 'Probe', path: '/zz-probe', icon: Compass, order: 60, mobileTab: true },
];
```

Run: `cd frontend && pnpm exec vitest run src/app/navRegistry.test.ts`
Expected: FAIL — `uses the C10 nav order…` and `lets only home, events, leaderboards and shooters be mobile tabs` fail
(order 60 belongs to explorer; zz-probe is not a mobile-tab feature).
Then delete `frontend/src/features/zz-probe/` and re-run.
Expected: PASS — 6 tests.

- [ ] **Step 14: Write the failing route-tree test**

Create the full contents of `frontend/src/app/appRoutes.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderRoutes } from '../test/render';
import { stubViewport } from '../test/viewport';
import { appRoutes } from './router';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('appRoutes', () => {
  it('renders feature pages inside the AppShell layout', async () => {
    stubViewport('desktop');
    renderRoutes(appRoutes, { route: '/' });
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    // Pages must not render their own <main>: the shell's <main id="main"> is the only one. The
    // Plan 01 placeholder HomePage is the temporary exception (Plan 08 T4 removes its <main>), so
    // this looks at the first match.
    expect(screen.getAllByRole('main')[0]).toHaveAttribute('id', 'main');
  });

  it('shows Page not found for an unknown path', async () => {
    renderRoutes(appRoutes, { route: '/no-such-page' });
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 15: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/app/appRoutes.test.tsx`
Expected: FAIL — 2 failed: `Unable to find role="navigation" and name "Main"` (Plan 01's router has no layout route)
and `Unable to find role="heading" and name "Page not found"` (its root route has no `errorElement`, so React Router
shows its default error screen).

- [ ] **Step 16: Insert the AppShell layout route (the permitted C10 edit to `router.tsx`)**

The exported names `appRoutes` and `createAppRouter` stay as Plan 01 defined them, because `App.tsx`,
`test/render.tsx` and Plan 01's `router.test.tsx` import them. Replace the full contents of `frontend/src/app/router.tsx`:

```tsx
import { createBrowserRouter, type RouteObject } from 'react-router';
import { AppShell } from '../components/layout/AppShell';
import { RouteErrorPage } from './ErrorBoundary';
import { featureRoutes } from './registry';

export const appRoutes: RouteObject[] = [
  {
    path: '/',
    HydrateFallback: () => null,
    errorElement: <RouteErrorPage />,
    children: [
      {
        element: <AppShell />,
        children: [{ errorElement: <RouteErrorPage />, children: featureRoutes }],
      },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
```

- [ ] **Step 17: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/app`
Expected: PASS — `appRoutes.test.tsx` (2 tests), `navRegistry.test.ts` (6 tests), and Plan 01 T2's `router.test.tsx`,
`App.test.tsx` and `registry.test.ts` unchanged (they look for the home page's `Sunday Clays` heading, which now
renders inside the shell; the shell's brand is a link, not a heading).

- [ ] **Step 18: Full suite, coverage, lint, types and format**

Run: `cd frontend && pnpm exec prettier --write src/components/layout src/app`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; coverage ≥90% lines and ≥90% branches overall, `src/components/layout` ≥90%.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings.

- [ ] **Step 19: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/components/layout frontend/src/app/router.tsx frontend/src/app/navRegistry.test.ts frontend/src/app/appRoutes.test.tsx
git commit -F - <<'MSG'
feat(frontend): responsive AppShell, registry nav and global round-type filter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

### Task 3: Auth UI — login page, session guard, logout and `safeNext` (master Plan 07 T3)

**Context.** Tasks 1, 2 and 4 of this plan and Plan 04 T1 have merged: the backend serves
`GET /api/auth/me`, `POST /api/auth/login` and `POST /api/auth/logout` (Decision D3), `pnpm typecheck` regenerates
`src/api/schema.d.ts` with those paths, and Playwright has the `setup` project plus `e2e/authState.ts`. This task adds
the only `?next=` sanitizer (`lib/safeNext.ts`, verbatim from C10), the `features/auth` feature (session hooks, login
page, `RequireRole` guard, account panel with logout), the `role` option of the test render helpers, and the second and
last permitted `router.tsx` edit: public routes (`handle: { public: true }`, only `/login`) render bare; every other
feature route renders inside `RequireRole` → `SessionShell` → `AppShell` (Decision D10). Task 2's `router.tsx` renders
`<AppShell />` with no props, so no admin nav item and no logout control appear; this edit replaces that element with
`<RequireRole><SessionShell/></RequireRole>`, and `SessionShell` must pass `isAdmin={role === 'admin'}` and
`account={<AccountPanel role={role} />}` (`AppShellProps`: `isAdmin?: boolean`, `account?: ReactNode`,
`items?: readonly NavItem[]`). After login, and for a signed-in visitor who opens `/login`, the only navigation is
`navigate(safeNext(params.get('next')), { replace: true })` — never `window.location`. It also makes a data
request's 401 clear the cached session before the redirect (`onSessionExpired`, wired in `App.tsx`), so the login page
never bounces a visitor whose cookie died back to the failing page (Review Focus #1, Decisions D7 and D27). Run every command from the worktree root: frontend commands start
with `cd frontend && `, and the commit step starts with `cd "$(git rev-parse --show-toplevel)"` (agent shells reset
the working directory between calls, Decision D28).

**Files:**
- Create: `frontend/src/lib/safeNext.ts`; Test: `frontend/src/lib/safeNext.test.ts`
- Create: `frontend/src/features/auth/api.ts`, `frontend/src/features/auth/mocks.ts`,
  `frontend/src/features/auth/routes.tsx`, `frontend/src/features/auth/components/RequireRole.tsx`,
  `frontend/src/features/auth/components/AccountPanel.tsx`, `frontend/src/features/auth/components/SessionShell.tsx`,
  `frontend/src/features/auth/pages/LoginPage.tsx`
- Test: `frontend/src/features/auth/api.test.tsx`, `frontend/src/features/auth/components/RequireRole.test.tsx`,
  `frontend/src/features/auth/components/SessionShell.test.tsx`, `frontend/src/features/auth/pages/LoginPage.test.tsx`,
  `frontend/src/features/auth/sessionExpiry.test.tsx`, `frontend/src/app/App.session.test.tsx`
- Modify: `frontend/src/test/render.tsx` (C10: Plan 07 T3 adds session state), `frontend/src/app/router.tsx` (C10:
  Plan 07 T3 wraps the layout route in `RequireRole`), `frontend/src/app/appRoutes.test.tsx`, `frontend/src/app/App.tsx`
  (the `setNavigate` call only, Decision D27)
- Create: `frontend/e2e/login.spec.ts`; Modify: `frontend/e2e/smoke.spec.ts` (append the signed-out check)

**Interfaces:**
- Consumes:
  - Plan 04 T1 (Decision D3): `GET /api/auth/me` → 200 `RoleOut{role}` | 401 `unauthenticated`;
    `POST /api/auth/login {password}` → 200 `RoleOut{role}` | 401 `invalid_password` | 429 `rate_limited` or
    `login_busy` (errors in the C2 envelope `{"error": {"code", "message"}}`); `POST /api/auth/logout` → 204.
    `e2e/authState.ts`: `e2ePassword(role: 'viewer' | 'admin')`;
    the `mobile` (390×844) and `desktop` (1440×900) projects default to `VIEWER_STATE`.
  - Plan 01 T4: `e2e/fixtures.ts` (`test`, `expect`), `e2e/smoke.spec.ts`.
  - Task 1: `Button`, `EmptyState`, `Skeleton`. Task 2: `AppShell({isAdmin?: boolean; account?: ReactNode; items?:
    readonly NavItem[]})`. Task 4: `api`, `unwrap`,
    `setNavigate(fn: (to: string) => void): void` (`src/api/client.ts`), `ApiError`, `toApiError`
    (`src/api/errors.ts`), `RouteErrorPage`, `AppProviders`, `createQueryClient()`, `app/App.tsx`,
    `renderRoutes`/`renderWithProviders`/`renderRoute`, `stubViewport`; `src/test/msw/server.ts` `server`.
- Produces:
  - `lib/safeNext.ts`: `safeNext(n: string | null): string` (C10, verbatim).
  - `features/auth/api.ts`: `type Role = 'viewer' | 'admin'`, `interface Session {role: Role}`,
    `SESSION_QUERY_KEY = ['/api/auth/me'] as const`, `fetchSession(): Promise<Session | null>` (401 → `null`, other
    failures throw `ApiError`), `useSession(): {session: Session | null; isPending: boolean; error: Error | null;
    refetch}`, `useLogin()` (mutation `password → Session`, writes the session query), `useLogout()` (every other
    cached query removed; session → `null` only on success or a 401, so a failed logout keeps the session and
    `AccountPanel` shows an error), `onSessionExpired(queryClient: QueryClient,
    navigate: (to: string) => void): (to: string) => void` (sets the session query to `null`, then navigates).
  - `features/auth/components/RequireRole.tsx`: `RequireRole({role = 'viewer', children})`;
    `SessionShell()` (the `AppShell` with `isAdmin` and the account panel); `AccountPanel({role})`.
  - `features/auth/pages/LoginPage.tsx`: `LoginPage()`; `features/auth/routes.tsx`: relative route `login` (served at
    `/login`, Plan 01 Decision 15) with `handle: { public: true }` (no nav item); `features/auth/mocks.ts`:
    `handlers` (C2-envelope error bodies, Decision D3), `TEST_PASSWORDS = {viewer: 'viewer-pw', admin: 'admin-pw'}`.
  - `test/render.tsx`: option `role?: Role | null | 'unset'` (default `'viewer'`; `null` logged out; `'unset'` fetched
    from MSW) on `renderRoutes` and `renderWithProviders` (Decision D9).
  - `app/router.tsx`: `appRoutes = [{path: '/', HydrateFallback: () => null, errorElement, children: [...public feature routes, {element:
    <RequireRole><SessionShell/></RequireRole>, children: [{errorElement, children: other feature routes}]}]}]`.
  - `app/App.tsx`: `setNavigate(onSessionExpired(queryClient, (to) => { void router.navigate(to); }))`.

**Branch:** `task/07-3-auth-ui` · **Depends on:** Plan 07 T2, Plan 07 T4, Plan 04 T1.

- [ ] **Step 1: Write the failing `safeNext` test**

Create the full contents of `frontend/src/lib/safeNext.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { safeNext } from './safeNext';

describe('safeNext', () => {
  it.each([
    ['an absolute URL to another site', 'https://evil.com'],
    ['a protocol-relative URL', '//evil.com'],
    ['a backslash authority', '/\\evil.com'],
    ['a tab-smuggled authority', '/\t/evil.com'],
    ['?next=/%0a/evil.com as decoded by URLSearchParams', '/\n/evil.com'],
    ['the 401 redirect from pathname //evil.com/x (next=%2F%2Fevil.com%2Fx, decoded)', '//evil.com/x'],
    ['a javascript: URL', 'javascript:alert(1)'],
    ['a relative path without a leading slash', 'events'],
    ['an empty value', ''],
  ])('rejects %s', (_label, next) => {
    expect(safeNext(next)).toBe('/');
  });

  it('falls back to / when next is missing', () => {
    expect(safeNext(null)).toBe('/');
  });

  it('keeps a same-origin path with its query and hash', () => {
    expect(safeNext('/events/2026-09-13?x=1')).toBe('/events/2026-09-13?x=1');
    expect(safeNext('/explorer?m=score#chart')).toBe('/explorer?m=score#chart');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/safeNext.test.ts`
Expected: FAIL — `Failed to resolve import "./safeNext"`.

- [ ] **Step 3: Implement `safeNext` (the C10 function, verbatim)**

Create the full contents of `frontend/src/lib/safeNext.ts`:

```ts
/**
 * The only way a `?next=` value becomes a navigation target (C10): a same-origin path, else '/'.
 * URLSearchParams has already decoded the value, so `?next=/%0a/evil.com` arrives as '/\n/evil.com',
 * which the URL parser turns into '//evil.com' and is therefore rejected.
 * The prefix checks run on the raw value AND on the resolved path: the URL parser removes dot
 * segments, so '/.//evil.com' (or '/%2e//evil.com', '/x/..//evil.com') resolves to '//evil.com',
 * a protocol-relative URL that the router's pushState fallback would load from another site.
 */
export function safeNext(n: string | null): string {
  if (!n || !n.startsWith('/') || n.startsWith('//') || n.startsWith('/\\')) return '/';
  try {
    const u = new URL(n, window.location.origin);
    const p = u.pathname + u.search + u.hash;
    return u.origin === window.location.origin && !p.startsWith('//') && !p.startsWith('/\\')
      ? p
      : '/';
  } catch {
    return '/';
  }
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/safeNext.test.ts`
Expected: PASS — 11 tests.

- [ ] **Step 5: Write the failing session-fetch test**

Create the full contents of `frontend/src/features/auth/api.test.tsx`:

```tsx
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { fetchSession } from './api';

describe('fetchSession', () => {
  it('returns the role for a signed-in session', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ role: 'admin' })));
    await expect(fetchSession()).resolves.toEqual({ role: 'admin' });
  });

  it('returns null when logged out (401) without redirecting', async () => {
    server.use(
      http.get('/api/auth/me', () =>
        HttpResponse.json(
          { error: { code: 'unauthenticated', message: 'Log in to continue' } },
          { status: 401 },
        ),
      ),
    );
    await expect(fetchSession()).resolves.toBeNull();
  });

  it('throws on a server failure instead of pretending to be logged out', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({}, { status: 503 })));
    await expect(fetchSession()).rejects.toMatchObject({ status: 503 });
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/auth/api.test.tsx`
Expected: FAIL — `Failed to resolve import "./api"`.

- [ ] **Step 7: Implement the session hooks and the default MSW auth handlers**

Create the full contents of `frontend/src/features/auth/api.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { toApiError } from '../../api/errors';

/** Exactly two roles (Global Constraints); admin ⊇ viewer. */
export type Role = 'viewer' | 'admin';

export interface Session {
  role: Role;
}

export const SESSION_QUERY_KEY = ['/api/auth/me'] as const;

const toRole = (role: unknown): Role => (role === 'admin' ? 'admin' : 'viewer');

/** GET /api/auth/me: the session, or null when logged out (401). Other failures throw ApiError. */
export async function fetchSession(): Promise<Session | null> {
  const { data, error, response } = await api.GET('/api/auth/me');
  if (response.status === 401) return null;
  if (!response.ok) throw toApiError(response.status, error);
  return { role: toRole(data?.role) };
}

export function useSession() {
  const query = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: fetchSession,
    staleTime: 5 * 60_000,
  });
  return {
    session: query.data ?? null,
    isPending: query.isPending,
    error: query.error,
    refetch: query.refetch,
  };
}

/** POST /api/auth/login; on success the session query holds the new role. */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (password: string): Promise<Session> => {
      const data = await unwrap(api.POST('/api/auth/login', { body: { password } }));
      return { role: toRole(data.role) };
    },
    onSuccess: (session) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
    },
  });
}

/**
 * POST /api/auth/logout, then mark the session logged out (RequireRole sends the browser to
 * /login) and forget every other cached query. Runs even if the request fails.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/auth/logout')),
    onSettled: () => {
      queryClient.setQueryData(SESSION_QUERY_KEY, null);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== SESSION_QUERY_KEY[0],
      });
    },
  });
}
```

Create the full contents of `frontend/src/features/auth/mocks.ts` (merged into every test's MSW server by
`test/msw/handlers.ts`; error bodies are Plan 04's C2 envelopes, Decision D3):

```ts
import { http, HttpResponse } from 'msw';

/** Passwords accepted by the default MSW login handler. */
export const TEST_PASSWORDS = { viewer: 'viewer-pw', admin: 'admin-pw' } as const;

export const handlers = [
  http.get('/api/auth/me', () => HttpResponse.json({ role: 'viewer' })),
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { password?: unknown };
    if (body.password === TEST_PASSWORDS.admin) return HttpResponse.json({ role: 'admin' });
    if (body.password === TEST_PASSWORDS.viewer) return HttpResponse.json({ role: 'viewer' });
    return HttpResponse.json(
      { error: { code: 'invalid_password', message: 'Wrong password' } },
      { status: 401 },
    );
  }),
  http.post('/api/auth/logout', () => new HttpResponse(null, { status: 204 })),
];
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/auth/api.test.tsx`
Expected: PASS — 3 tests.

- [ ] **Step 9: Give the test render helpers a session (`role` option)**

Replace the full contents of `frontend/src/test/render.tsx`:

```tsx
import { QueryClient } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router';
import { AppProviders } from '../app/providers';
import { appRoutes } from '../app/router';
import { SESSION_QUERY_KEY, type Role } from '../features/auth/api';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
}

export interface RenderOptions {
  /** Initial URL (path + query), default '/'. */
  route?: string;
  /** Route pattern `ui` is mounted at (renderWithProviders only), default '*'. */
  path?: string;
  queryClient?: QueryClient;
  /**
   * Seeds the session query: 'viewer' (default), 'admin', null (logged out), or 'unset' to leave
   * it empty so it is fetched from the MSW /api/auth/me handler.
   */
  role?: Role | null | 'unset';
}

export interface ProvidersResult extends RenderResult {
  user: UserEvent;
  queryClient: QueryClient;
  router: ReturnType<typeof createMemoryRouter>;
}

/** Renders a route tree in a memory router inside the production provider stack. */
export function renderRoutes(routes: RouteObject[], options: RenderOptions = {}): ProvidersResult {
  const queryClient = options.queryClient ?? createTestQueryClient();
  const role = options.role === undefined ? 'viewer' : options.role;
  if (role !== 'unset') {
    queryClient.setQueryData(SESSION_QUERY_KEY, role === null ? null : { role });
  }
  const router = createMemoryRouter(routes, { initialEntries: [options.route ?? '/'] });
  const user = userEvent.setup();
  const result = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...result, user, queryClient, router };
}

/** Renders one element at `path` (default '*') with router, query client, session and boundary. */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderOptions = {},
): ProvidersResult {
  return renderRoutes([{ path: options.path ?? '*', element: ui }], options);
}

/** Plan 01 T2's helper, kept: the real route tree at `route` (lazy pages need findBy* queries). */
export function renderRoute(route: string, routes: RouteObject[] = appRoutes): ProvidersResult {
  return renderRoutes(routes, { route });
}
```

Run: `cd frontend && pnpm exec vitest run`
Expected: PASS — every existing test file (the default `role: 'viewer'` only seeds the session query, which nothing
reads yet).

- [ ] **Step 10: Write the failing `RequireRole` test**

Create the full contents of `frontend/src/features/auth/components/RequireRole.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { RequireRole } from './RequireRole';

function routes(role?: 'viewer' | 'admin') {
  return [
    { path: '/login', element: <p>login page</p> },
    {
      path: '/events',
      element: (
        <RequireRole {...(role ? { role } : {})}>
          <p>secret</p>
        </RequireRole>
      ),
    },
  ];
}

describe('RequireRole', () => {
  it('renders children for a signed-in viewer', () => {
    renderRoutes(routes(), { route: '/events', role: 'viewer' });
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('sends a signed-out visitor to /login with next = path + query', () => {
    const { router } = renderRoutes(routes(), { route: '/events?rt=sporting', role: null });
    expect(router.state.location.pathname).toBe('/login');
    expect(router.state.location.search).toBe('?next=%2Fevents%3Frt%3Dsporting');
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('shows Admins only to a viewer on an admin page', () => {
    renderRoutes(routes('admin'), { route: '/events', role: 'viewer' });
    expect(screen.getByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
    expect(screen.queryByText('secret')).toBeNull();
  });

  it('lets an admin through an admin page', () => {
    renderRoutes(routes('admin'), { route: '/events', role: 'admin' });
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('shows a loading state until the server answers', async () => {
    server.use(
      http.get('/api/auth/me', async () => {
        await delay(20);
        return HttpResponse.json({ role: 'viewer' });
      }),
    );
    renderRoutes(routes(), { route: '/events', role: 'unset' });
    expect(screen.getByRole('status', { name: 'Checking your session' })).toBeInTheDocument();
    expect(await screen.findByText('secret')).toBeInTheDocument();
  });

  it('offers a retry when the session check fails', async () => {
    let calls = 0;
    server.use(
      http.get('/api/auth/me', () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({}, { status: 503 })
          : HttpResponse.json({ role: 'viewer' });
      }),
    );
    const { user } = renderRoutes(routes(), { route: '/events', role: 'unset' });
    expect(
      await screen.findByRole('heading', { name: "Can't reach the server" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('secret')).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/auth/components/RequireRole.test.tsx`
Expected: FAIL — `Failed to resolve import "./RequireRole"`.

- [ ] **Step 12: Implement `RequireRole`**

Create the full contents of `frontend/src/features/auth/components/RequireRole.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { Button } from '../../../components/ui/Button';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useSession, type Role } from '../api';

/**
 * Renders children only for a session with `role` (admin ⊇ viewer). No session → /login with
 * `next` built from pathname + search (C10). A viewer on an admin page sees "Admins only".
 */
export function RequireRole({ role = 'viewer', children }: { role?: Role; children: ReactNode }) {
  const { session, isPending, error, refetch } = useSession();
  const location = useLocation();

  if (isPending) {
    return <Skeleton label="Checking your session" lines={4} className="mx-auto max-w-md p-8" />;
  }
  if (error) {
    return (
      <EmptyState
        title="Can't reach the server"
        description="Check your connection and try again."
        action={<Button onClick={() => void refetch()}>Try again</Button>}
      />
    );
  }
  if (!session) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (role === 'admin' && session.role !== 'admin') {
    return (
      <EmptyState
        title="Admins only"
        description="Log out and log in with the admin password to open this page."
      />
    );
  }
  return children;
}
```

- [ ] **Step 13: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/auth/components/RequireRole.test.tsx`
Expected: PASS — 6 tests.

- [ ] **Step 14: Write the failing login page test (incl. the `?next=` round-trip and hostile `next`)**

Create the full contents of `frontend/src/features/auth/pages/LoginPage.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { TEST_PASSWORDS } from '../mocks';
import { LoginPage } from './LoginPage';

const ROUTES = [
  { path: '/login', element: <LoginPage /> },
  { path: '*', element: <p>app</p> },
];

function renderLogin(search = '') {
  return renderRoutes(ROUTES, { route: `/login${search}`, role: null });
}

describe('LoginPage', () => {
  it('keeps the submit button disabled until a password is typed', async () => {
    const { user } = renderLogin();
    const submit = screen.getByRole('button', { name: 'Log in' });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText('Password'), 'x');
    expect(submit).toBeEnabled();
  });

  it('shows "Wrong password." for a rejected password and stays on the page', async () => {
    const { user, router } = renderLogin('?next=%2Fexplorer');
    await user.type(screen.getByLabelText('Password'), 'nope');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong password.');
    expect(router.state.location.pathname).toBe('/login');
  });

  it('explains the rate limit on 429', async () => {
    server.use(
      http.post('/api/auth/login', () =>
        HttpResponse.json(
          { error: { code: 'rate_limited', message: 'Too many failed logins. Try again later.' } },
          { status: 429 },
        ),
      ),
    );
    const { user } = renderLogin();
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts');
  });

  it('shows a connection message for other failures', async () => {
    server.use(http.post('/api/auth/login', () => HttpResponse.error()));
    const { user } = renderLogin();
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not log in');
  });

  it('returns to next after a successful login (the ?next= round-trip)', async () => {
    const { user, router, queryClient } = renderLogin('?next=%2Fevents%2F2026-09-13%3Fx%3D1');
    await user.type(screen.getByLabelText('Password'), TEST_PASSWORDS.admin);
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByText('app')).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/events/2026-09-13?x=1',
    );
    expect(router.state.historyAction).toBe('REPLACE');
    expect(queryClient.getQueryData(['/api/auth/me'])).toEqual({ role: 'admin' });
  });

  it.each([['//evil.com'], ['https%3A%2F%2Fevil.com'], ['%2F%0a%2Fevil.com']])(
    'never follows a hostile next=%s off the site',
    async (next) => {
      const { user, router } = renderLogin(`?next=${next}`);
      await user.type(screen.getByLabelText('Password'), TEST_PASSWORDS.viewer);
      await user.click(screen.getByRole('button', { name: 'Log in' }));
      expect(await screen.findByText('app')).toBeInTheDocument();
      expect(router.state.location.pathname).toBe('/');
    },
  );

  it('bounces an already signed-in visitor to next immediately', async () => {
    const { router } = renderRoutes(ROUTES, { route: '/login?next=%2Fclub', role: 'viewer' });
    expect(await screen.findByText('app')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/club');
  });
});
```

- [ ] **Step 15: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/auth/pages/LoginPage.test.tsx`
Expected: FAIL — `Failed to resolve import "./LoginPage"`.

- [ ] **Step 16: Implement the login page and its public route**

Create the full contents of `frontend/src/features/auth/pages/LoginPage.tsx`:

```tsx
import { useEffect, useId, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { Button } from '../../../components/ui/Button';
import { safeNext } from '../../../lib/safeNext';
import { useLogin, useSession } from '../api';

function errorMessage(error: unknown): string | null {
  if (error === null) return null;
  if (error instanceof ApiError && error.status === 401) return 'Wrong password.';
  if (error instanceof ApiError && error.status === 429) {
    return 'Too many attempts. Try again in a few minutes.';
  }
  return 'Could not log in. Check your connection and try again.';
}

export function LoginPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { session } = useSession();
  const login = useLogin();
  const [password, setPassword] = useState('');
  const inputId = useId();
  const next = params.get('next');

  // Signed in (already, or just now): leave through safeNext only (C10).
  useEffect(() => {
    if (session) void navigate(safeNext(next), { replace: true });
  }, [session, next, navigate]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    login.mutate(password);
  };
  const message = errorMessage(login.error);

  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <form
        onSubmit={onSubmit}
        className="flex w-full max-w-sm flex-col gap-4 rounded-card bg-elevated p-6 shadow-xl"
      >
        <h1 className="text-2xl font-bold text-text">Sunday Clays</h1>
        <p className="text-sm text-text-muted">Enter the club password to continue.</p>
        <div className="flex flex-col gap-1">
          <label htmlFor={inputId} className="text-sm text-text">
            Password
          </label>
          <input
            id={inputId}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="min-h-11 rounded-button border border-outline-variant bg-surface px-4 text-text"
          />
        </div>
        {message !== null && (
          <p role="alert" className="rounded-card bg-error-container px-3 py-2 text-sm text-text">
            {message}
          </p>
        )}
        <Button type="submit" loading={login.isPending} disabled={password === ''}>
          Log in
        </Button>
      </form>
    </main>
  );
}
```

Create the full contents of `frontend/src/features/auth/routes.tsx` (no `nav` export: the login page has no nav item;
the path is relative to the `/` root, Plan 01 Decision 15, so it is served at `/login`):

```tsx
import type { RouteObject } from 'react-router';

/** `handle.public` routes render outside RequireRole and the AppShell (see app/router.tsx). */
export const routes: RouteObject[] = [
  {
    path: 'login',
    handle: { public: true },
    lazy: async () => ({ Component: (await import('./pages/LoginPage')).LoginPage }),
  },
];
```

- [ ] **Step 17: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/auth/pages/LoginPage.test.tsx src/app/navRegistry.test.ts`
Expected: PASS — 9 tests in `LoginPage.test.tsx`, 6 in `navRegistry.test.ts` (the registry now discovers `auth`, which
has no nav items).

- [ ] **Step 18: Write the failing session shell test (account panel and logout)**

Create the full contents of `frontend/src/features/auth/components/SessionShell.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { RequireRole } from './RequireRole';
import { SessionShell } from './SessionShell';

const ROUTES = [
  { path: '/login', element: <p>login page</p> },
  {
    path: '/',
    element: (
      <RequireRole>
        <SessionShell />
      </RequireRole>
    ),
    children: [{ index: true, element: <p>home page</p> }],
  },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SessionShell', () => {
  it('shows who is signed in and logs out to the login page, forgetting cached data', async () => {
    stubViewport('desktop');
    let loggedOut = false;
    server.use(
      http.post('/api/auth/logout', () => {
        loggedOut = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user, router, queryClient } = renderRoutes(ROUTES, { route: '/', role: 'admin' });
    queryClient.setQueryData(['/api/events'], ['cached']);
    expect(screen.getByText('Signed in as admin')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(loggedOut).toBe(true);
    expect(router.state.location.pathname).toBe('/login');
    expect(queryClient.getQueryData(['/api/events'])).toBeUndefined();
  });

  it('still signs the browser out when the logout request fails', async () => {
    stubViewport('desktop');
    server.use(http.post('/api/auth/logout', () => HttpResponse.error()));
    const { user } = renderRoutes(ROUTES, { route: '/', role: 'viewer' });
    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
  });

  it('puts the account panel in the More sheet on mobile', async () => {
    stubViewport('mobile');
    const { user } = renderRoutes(ROUTES, { route: '/', role: 'viewer' });
    expect(screen.queryByText('Signed in as viewer')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByText('Signed in as viewer')).toBeInTheDocument();
  });
});
```

- [ ] **Step 19: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/auth/components/SessionShell.test.tsx`
Expected: FAIL — `Failed to resolve import "./SessionShell"`.

- [ ] **Step 20: Implement the account panel and the session shell**

Create the full contents of `frontend/src/features/auth/components/AccountPanel.tsx`:

```tsx
import { LogOut } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { useLogout, type Role } from '../api';

export function AccountPanel({ role }: { role: Role }) {
  const logout = useLogout();
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-sm text-text-muted">Signed in as {role}</span>
      <Button
        variant="ghost"
        icon={<LogOut aria-hidden="true" className="size-4" />}
        loading={logout.isPending}
        onClick={() => logout.mutate()}
      >
        Log out
      </Button>
    </div>
  );
}
```

Create the full contents of `frontend/src/features/auth/components/SessionShell.tsx`:

```tsx
import { AppShell } from '../../../components/layout/AppShell';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/** The AppShell layout for the signed-in session (rendered inside RequireRole). */
export function SessionShell() {
  const { session } = useSession();
  const role = session?.role ?? 'viewer';
  return <AppShell isAdmin={role === 'admin'} account={<AccountPanel role={role} />} />;
}
```

- [ ] **Step 21: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/auth`
Expected: PASS — 4 files, 21 tests.

- [ ] **Step 22: Write the failing signed-out route-tree test**

Replace the full contents of `frontend/src/app/appRoutes.test.tsx` (adds the signed-out case to Task 2's two tests):

```tsx
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderRoutes } from '../test/render';
import { stubViewport } from '../test/viewport';
import { appRoutes } from './router';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('appRoutes', () => {
  it('renders feature pages inside the AppShell layout', async () => {
    stubViewport('desktop');
    renderRoutes(appRoutes, { route: '/' });
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    // Pages must not render their own <main>: the shell's <main id="main"> is the only one. The
    // Plan 01 placeholder HomePage is the temporary exception (Plan 08 T4 removes its <main>), so
    // this looks at the first match.
    expect(screen.getAllByRole('main')[0]).toHaveAttribute('id', 'main');
  });

  it('sends a signed-out visitor from / to the login page, outside the shell', async () => {
    const { router } = renderRoutes(appRoutes, { route: '/', role: null });
    expect(await screen.findByLabelText('Password')).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe('/login?next=%2F');
    expect(screen.queryByRole('navigation', { name: 'Main' })).toBeNull();
  });

  it('shows Page not found for an unknown path', async () => {
    renderRoutes(appRoutes, { route: '/no-such-page' });
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 23: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/app/appRoutes.test.tsx`
Expected: FAIL — 1 failed, 2 passed: `sends a signed-out visitor from / to the login page, outside the shell` reports
`Unable to find a label with the text of: Password` (nothing guards the layout route yet).

- [ ] **Step 24: Wrap the layout route in `RequireRole` (the permitted C10 edit to `router.tsx`)**

The exported names `appRoutes` and `createAppRouter` stay unchanged. Replace the full contents of
`frontend/src/app/router.tsx`:

```tsx
import { createBrowserRouter, type RouteObject } from 'react-router';
import { RequireRole } from '../features/auth/components/RequireRole';
import { SessionShell } from '../features/auth/components/SessionShell';
import { RouteErrorPage } from './ErrorBoundary';
import { featureRoutes } from './registry';

/** Feature routes marked `handle: { public: true }` (the login page) skip the session guard. */
function isPublic(route: RouteObject): boolean {
  return (route.handle as { public?: boolean } | undefined)?.public === true;
}

export const appRoutes: RouteObject[] = [
  {
    path: '/',
    HydrateFallback: () => null,
    errorElement: <RouteErrorPage />,
    children: [
      ...featureRoutes.filter(isPublic),
      {
        element: (
          <RequireRole>
            <SessionShell />
          </RequireRole>
        ),
        children: [
          { errorElement: <RouteErrorPage />, children: featureRoutes.filter((r) => !isPublic(r)) },
        ],
      },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
```

- [ ] **Step 25: Run the app tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/app`
Expected: PASS — `appRoutes.test.tsx` 3 tests, plus Plan 01's `App.test.tsx` and `router.test.tsx` unchanged: `App`
now fetches the session from the MSW `/api/auth/me` handler (viewer) before rendering the home page, and
`renderRoute` seeds a viewer session.

- [ ] **Step 26: Write the failing session-expiry tests (Review Focus #1: no redirect loop)**

A data request that gets a 401 while the session query still holds a role (logged out in another tab, a rotated
password or `session_secret`, a cookie that expired within `useSession`'s 5-minute `staleTime`) must land on
`/login?next=…` and stay there. With Task 4's plain `setNavigate((to) => void router.navigate(to))`, `LoginPage` sees
the cached role and bounces straight back, the page refetches, gets 401 again, and the two navigate back and forth until
the session query goes stale.

Create the full contents of `frontend/src/features/auth/sessionExpiry.test.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { api, setNavigate, unwrap } from '../../api/client';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { SESSION_QUERY_KEY, onSessionExpired } from './api';
import { LoginPage } from './pages/LoginPage';

/** A page whose data request gets a 401: the cookie died while the app still holds a role. */
function Probe() {
  const { isError } = useQuery({
    queryKey: ['/api/health'],
    queryFn: () => unwrap(api.GET('/api/health')),
  });
  return <p>{isError ? 'probe failed' : 'probe loading'}</p>;
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('onSessionExpired', () => {
  it('lands a data 401 on the login page with next and stays there (no redirect loop)', async () => {
    let calls = 0;
    server.use(
      http.get('/api/health', () => {
        calls += 1;
        return HttpResponse.json(
          { error: { code: 'unauthenticated', message: 'x' } },
          { status: 401 },
        );
      }),
    );
    // The client builds next from window.location, which the browser router keeps in sync.
    window.history.replaceState(null, '', '/events');
    const { router, queryClient } = renderRoutes(
      [
        { path: '/login', element: <LoginPage /> },
        { path: '/events', element: <Probe /> },
      ],
      { route: '/events', role: 'viewer' },
    );
    setNavigate(onSessionExpired(queryClient, (to) => void router.navigate(to)));
    expect(await screen.findByLabelText('Password')).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/login?next=%2Fevents',
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(router.state.location.pathname).toBe('/login');
    expect(calls).toBe(1);
    expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toBeNull();
  });
});
```

Create the full contents of `frontend/src/app/App.session.test.tsx` (its own file, because `App.tsx` builds its browser
router and calls `setNavigate` once, at import):

```tsx
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { api, unwrap } from '../api/client';
import { server } from '../test/msw/server';
import { App } from './App';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('App session expiry', () => {
  it('routes a data 401 to the login page and forgets the cached session', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET('/api/health'))).rejects.toMatchObject({ status: 401 });
    expect(await screen.findByLabelText('Password')).toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe('/login?next=%2F');
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(window.location.pathname).toBe('/login');
  });
});
```

- [ ] **Step 27: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/auth/sessionExpiry.test.tsx src/app/App.session.test.tsx`
Expected: FAIL — 2 failed: `sessionExpiry.test.tsx` reports `TypeError: onSessionExpired is not a function`;
`App.session.test.tsx` reports `element could not be found in the document` at the `Password` assertion (the login page
rendered, then bounced straight back to `/` because the cached session still says `viewer`).

- [ ] **Step 28: Clear the cached session before the 401 redirect**

Replace the full contents of `frontend/src/features/auth/api.ts` (Step 7's file plus the `QueryClient` type import and
`onSessionExpired` at the end):

```ts
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { toApiError } from '../../api/errors';

/** Exactly two roles (Global Constraints); admin ⊇ viewer. */
export type Role = 'viewer' | 'admin';

export interface Session {
  role: Role;
}

export const SESSION_QUERY_KEY = ['/api/auth/me'] as const;

const toRole = (role: unknown): Role => (role === 'admin' ? 'admin' : 'viewer');

/** GET /api/auth/me: the session, or null when logged out (401). Other failures throw ApiError. */
export async function fetchSession(): Promise<Session | null> {
  const { data, error, response } = await api.GET('/api/auth/me');
  if (response.status === 401) return null;
  if (!response.ok) throw toApiError(response.status, error);
  return { role: toRole(data?.role) };
}

export function useSession() {
  const query = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: fetchSession,
    staleTime: 5 * 60_000,
  });
  return {
    session: query.data ?? null,
    isPending: query.isPending,
    error: query.error,
    refetch: query.refetch,
  };
}

/** POST /api/auth/login; on success the session query holds the new role. */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (password: string): Promise<Session> => {
      const data = await unwrap(api.POST('/api/auth/login', { body: { password } }));
      return { role: toRole(data.role) };
    },
    onSuccess: (session) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
    },
  });
}

/**
 * POST /api/auth/logout, then mark the session logged out (RequireRole sends the browser to
 * /login) and forget every other cached query. Runs even if the request fails.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/auth/logout')),
    onSettled: () => {
      queryClient.setQueryData(SESSION_QUERY_KEY, null);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== SESSION_QUERY_KEY[0],
      });
    },
  });
}

/**
 * The redirect the API client runs when a data request gets a 401 (App.tsx passes it to
 * setNavigate). The server has just said the session is gone, so the cached session is cleared
 * first; otherwise LoginPage would see the stale role and bounce straight back, looping.
 */
export function onSessionExpired(
  queryClient: QueryClient,
  navigate: (to: string) => void,
): (to: string) => void {
  return (to) => {
    queryClient.setQueryData(SESSION_QUERY_KEY, null);
    navigate(to);
  };
}
```

Replace the full contents of `frontend/src/app/App.tsx` (Task 4's providers stay; only the `setNavigate` call changes,
Decision D27):

```tsx
import { RouterProvider } from 'react-router';
import { setNavigate } from '../api/client';
import { onSessionExpired } from '../features/auth/api';
import { AppProviders } from './providers';
import { createQueryClient } from './queryClient';
import { createAppRouter } from './router';

const router = createAppRouter();
const queryClient = createQueryClient();

// A data request's 401 clears the cached session, then navigates in-app (no reload, no loop).
setNavigate(
  onSessionExpired(queryClient, (to) => {
    void router.navigate(to);
  }),
);

export function App() {
  return (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
```

- [ ] **Step 29: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/auth src/app`
Expected: PASS — `src/features/auth` 5 files, 22 tests; `src/app` 8 files, incl. `App.session.test.tsx` (1 test),
`appRoutes.test.tsx` (3) and Plan 01's `App.test.tsx`, `router.test.tsx` and `registry.test.ts` unchanged.

- [ ] **Step 30: Write the e2e login spec and the signed-out smoke check**

Create the full contents of `frontend/e2e/login.spec.ts`:

```ts
import type { Page } from '@playwright/test';
import { e2ePassword } from './authState';
import { expect, test } from './fixtures';

// Every test here starts signed out, independent of the setup project's storage state.
test.use({ storageState: { cookies: [], origins: [] } });

async function logIn(page: Page, password: string): Promise<void> {
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
}

/** Desktop shows the account panel in the side nav; mobile keeps it in the "More" sheet. */
async function openAccount(page: Page): Promise<void> {
  const more = page.getByRole('button', { name: 'More' });
  if (await more.isVisible()) await more.click();
}

test('a signed-out visit is sent to the login page with next', async ({ page }) => {
  await page.goto('/?rt=sporting');
  await expect(page).toHaveURL(/\/login\?next=%2F%3Frt%3Dsporting$/);
  await expect(page.getByRole('heading', { name: 'Sunday Clays' })).toBeVisible();
});

for (const role of ['viewer', 'admin'] as const) {
  test(`${role} logs in, lands on next, and logs out`, async ({ page }) => {
    await page.goto('/?rt=sporting');
    await logIn(page, e2ePassword(role));
    await expect(page).toHaveURL(/\/\?rt=sporting$/);
    await expect(page.getByText('Filtered: Sporting')).toBeVisible();
    await openAccount(page);
    await expect(page.getByText(`Signed in as ${role}`)).toBeVisible();
    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page).toHaveURL(/\/login/);
    await page.goto('/');
    await expect(page).toHaveURL(/\/login\?next=%2F$/);
  });
}

test('the round-type panel opens fully on screen', async ({ page }) => {
  await page.goto('/');
  await logIn(page, e2ePassword('viewer'));
  await page.getByRole('button', { name: 'Round type' }).click();
  const box = await page.getByRole('group', { name: 'Round types' }).boundingBox();
  const viewportWidth = page.viewportSize()?.width ?? 0;
  expect(box).not.toBeNull();
  expect(box?.x ?? -1).toBeGreaterThanOrEqual(0);
  expect((box?.x ?? 0) + (box?.width ?? Infinity)).toBeLessThanOrEqual(viewportWidth);
});

test('a wrong password shows an error and stays on the login page', async ({ page }) => {
  await page.goto('/login');
  await logIn(page, 'definitely-not-the-password');
  await expect(page.getByRole('alert')).toHaveText('Wrong password.');
  await expect(page).toHaveURL(/\/login$/);
});

test('a hostile next never leaves the site', async ({ page, baseURL }) => {
  await page.goto('/login?next=%2F%2Fevil.example');
  await logIn(page, e2ePassword('viewer'));
  await expect(page).toHaveURL(`${baseURL ?? ''}/`);
});
```

Append this block to the end of `frontend/e2e/smoke.spec.ts` (the file already imports `test` and `expect` from
`./fixtures`; the other smoke tests keep the project's viewer storage state, and Plan 01's `SPA shell renders with the
security headers` still finds the home page's `Sunday Clays` heading):

```ts
test.describe('signed out', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('an unauthenticated visit to / is sent to the login page', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/login\?next=%2F$/);
    await expect(page.getByLabel('Password')).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main' })).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: 'Tabs' })).toHaveCount(0);
  });
});
```

Run: `cd frontend && pnpm exec prettier --write e2e && pnpm lint && pnpm typecheck && pnpm exec playwright test --list`
Expected: lint and types clean; the listing shows `login.spec.ts` with 6 tests and `smoke.spec.ts › signed out` with 1
test under both `[mobile]` and `[desktop]`.

- [ ] **Step 31: Run the e2e suite against the compose stack**

From the worktree root (run `cd frontend && pnpm exec playwright install chromium` once if browsers are missing):

```bash
cd "$(git rev-parse --show-toplevel)"
docker build -t ghcr.io/gitgat/sunday-clays-backend:ci backend
docker build -t ghcr.io/gitgat/sunday-clays-frontend:ci -f frontend/Dockerfile .
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test)
docker compose -f compose.yaml -f compose.test.yaml down -v
```

Expected: every project passes — `login.spec.ts` 6 passed (incl. `the round-type panel opens fully on screen`, whose
right edge stays within 390 px on mobile) and `smoke.spec.ts` (incl. `signed out`) green at both viewports, with no
page errors or CSP violations reported by the shared fixture.

- [ ] **Step 32: Full suite, coverage, lint, types and format**

Run: `cd frontend && pnpm exec prettier --write src e2e`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; coverage ≥90% lines and ≥90% branches overall. `safeNext.ts` shows its `catch`
line uncovered: `new URL()` never throws for a value that starts with `/`, and the function stays C10's verbatim text.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings.

- [ ] **Step 33: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/lib/safeNext.ts frontend/src/lib/safeNext.test.ts frontend/src/features/auth \
  frontend/src/test/render.tsx frontend/src/app/router.tsx frontend/src/app/appRoutes.test.tsx \
  frontend/src/app/App.tsx frontend/src/app/App.session.test.tsx \
  frontend/e2e/login.spec.ts frontend/e2e/smoke.spec.ts
git commit -F - <<'MSG'
feat(frontend): login page, session guard, logout and safeNext

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

### Task 4: API client, query client, error boundary, URL state and lib helpers (master Plan 07 T4)

**Context.** This task builds on Plan 01 T2's skeleton (Vitest with `restoreMocks`/`unstubGlobals`, MSW with
`onUnhandledRequest: 'error'`, `test/setup.ts` shims, `test/render.tsx` with `renderWithProviders` and `renderRoute`,
`app/App.tsx` rendering the router). This task runs in Wave 1 next to Task 1 and touches none of its files. It adds the
typed openapi-fetch client with the C10 401 → `/login?next=` redirect, the query client and error boundaries, the
provider stack shared by `App.tsx` and the test helpers (C10 ownership: Plan 07 T4 adds providers to both), URL state
hooks, the global round-type filter hook, and the formatting, CSV, "that's me" and share helpers every page uses. Node's
`fetch` rejects the relative `/api/...` URLs the SPA uses; tests rely on Plan 01 T2's `test/setup.ts` resolving them
against the page origin (Decision D6, checked in Step 1), and this task adds no setup file of its own. The client looks
`fetch` up per request so MSW intercepts it (Decision D5). Run every command from the worktree root: frontend commands
start with `cd frontend && `, and the commit step starts with `cd "$(git rev-parse --show-toplevel)"` (agent shells
reset the working directory between calls, Decision D28).

**Files:**
- Create: `frontend/src/api/errors.ts`, `frontend/src/api/client.ts`; Test: `frontend/src/api/errors.test.ts`,
  `frontend/src/api/client.test.ts`
- Create: `frontend/src/test/viewport.ts`
- Create: `frontend/src/app/queryClient.ts`, `frontend/src/app/ErrorBoundary.tsx`, `frontend/src/app/providers.tsx`;
  Test: `frontend/src/app/queryClient.test.ts`, `frontend/src/app/providers.test.tsx`
- Modify: `frontend/src/app/App.tsx`, `frontend/src/test/render.tsx`
- Create: `frontend/src/lib/useMediaQuery.ts`, `useUrlState.ts`, `roundTypes.ts`, `format.ts`, `download.ts`, `csv.ts`,
  `me.ts`, `share.ts` (all in `frontend/src/lib/`)
- Test: `frontend/src/lib/{useMediaQuery,useUrlState,roundTypes}.test.tsx`, `frontend/src/lib/{format,csv,me,share}.test.ts`

**Interfaces:**
- Consumes (Plan 01 T2): `src/api/schema.d.ts` `paths` (generated by `pnpm gen:api`, which `pnpm typecheck` runs
  first; `GET /api/health` exists from Plan 01 T1), `app/router.tsx` (`appRoutes`, `createAppRouter`),
  `test/msw/server.ts` (`server`), `test/setup.ts` (`window.matchMedia` never matching, `navigator.canShare` → false,
  `URL.createObjectURL`, and undici's global origin set to `window.location.origin` so relative `/api/...` fetches
  resolve — Decision D6), packages `openapi-fetch`, `@tanstack/react-query`, `react-router`, `html-to-image`.
- Produces:
  - `api/errors.ts`: `class ApiError extends Error {status: number; code: string}`,
    `toApiError(status: number, body: unknown): ApiError` (C2 envelope → code/message, else `http_<status>` and a
    default message).
  - `api/client.ts`: `api` (`createClient<paths>({baseUrl: '', credentials: 'include', fetch})`),
    `unwrap<T>(request: Promise<FetchResult<T>>): Promise<T>` (throws `ApiError` for every non-2xx response; a network
    error, fetch's `TypeError`, propagates unchanged),
    `shouldRedirectToLogin(status, schemaPath, pathname): boolean`, `loginPath(): string`,
    `setNavigate(fn: (to: string) => void): void`, `interface FetchResult<T>`.
  - `app/queryClient.ts`: `shouldRetry(failureCount, error): boolean`, `createQueryClient(): QueryClient`.
  - `app/ErrorBoundary.tsx`: `AppErrorBoundary`, `RouteErrorPage` ("Page not found" for 404s).
  - `app/providers.tsx`: `AppProviders({queryClient, children})`.
  - `test/render.tsx`: `createTestQueryClient()`, `renderRoutes(routes, {route?, path?, queryClient?})`,
    `renderWithProviders(ui, opts)`, `renderRoute(route, routes = appRoutes)`, each returning RTL's result plus
    `{user, queryClient, router}`. `test/viewport.ts`: `stubViewport('desktop' | 'mobile', {touch?})`.
  - `lib/useUrlState.ts`: `interface Codec<T>`, `useUrlState<T>(key, codec, defaultValue): [T, (next: T) => void]`,
    `stringCodec`, `intCodec`, `numberCodec`, `boolCodec`, `enumCodec(values)`, `listCodec(item)`, `rangeCodec`,
    `isoDateCodec` (Decision D13).
  - `lib/roundTypes.ts`: `ROUND_TYPES`, `RoundTypeValue`, `ROUND_TYPE_LABELS`, `roundTypesCodec`,
    `useRoundTypes(): [RoundTypeValue[], (next: RoundTypeValue[]) => void]` (query key `rt`).
  - `lib/useMediaQuery.ts`: `useMediaQuery(query)`, `useIsDesktop()` (`(min-width: 1024px)`), `useIsTouch()`
    (`(pointer: coarse)`), `DESKTOP_QUERY`, `COARSE_POINTER_QUERY`.
  - `lib/format.ts`: `formatNumber(v, digits = 0)`, `formatPercent(v, digits = 1)`, `formatSigned(v, digits = 1)`,
    `formatTemp`, `formatWind`, `formatPrecip`, `formatPressure` (hPa × 0.02953, 2 dp, `inHg`), `parseIsoDate`,
    `formatDate`, `formatShortDate`, `formatMonth`; missing or non-finite values render `—`.
  - `lib/download.ts`: `downloadBlob(blob, filename)`. `lib/csv.ts`: `interface CsvColumn {key; label}`,
    `type CsvRow`, `toCsv(columns, rows): string`, `downloadCsv(name, columns, rows)`. `lib/me.ts`: `getMe()`,
    `setMe(id)`, `clearMe()` (localStorage `sc.me`). `lib/share.ts`: `type ShareOutcome`,
    `shareElementAsImage(el, filename): Promise<ShareOutcome>`.

**Branch:** `task/07-4-api-lib` · **Depends on:** Plan 01 (T2 frontend skeleton; T5 CI).

- [ ] **Step 1: Confirm Plan 01's relative-URL shim is in `test/setup.ts`**

Run: `cd frontend && grep -c "undici.globalOrigin.1" src/test/setup.ts`
Expected: a count of at least `1`. Node's `fetch`/`Request` (undici) reject relative URLs, while the SPA calls
same-origin `/api/...` paths (C10 `baseUrl: ''`), so every test that sends a request relies on Plan 01 T2's `setup.ts`
statement
`(globalThis as Record<symbol, unknown>)[Symbol.for('undici.globalOrigin.1')] = new URL(window.location.origin);`
(Decision D6). If the count is `0`, stop and report BLOCKED ("Plan 01 T2's test/setup.ts lacks the undici
global-origin line; the controller must amend Plan 01 T2"). C10 makes `test/setup.ts` the only home of jsdom shims and
forbids editing it later, so never add a second setup file, edit `vitest.config.ts` or patch `setup.ts` here.

- [ ] **Step 2: Write the failing API error test**

Create the full contents of `frontend/src/api/errors.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { ApiError, toApiError } from './errors';

describe('toApiError', () => {
  it('unpacks the C2 error envelope', () => {
    const e = toApiError(400, {
      error: { code: 'invalid_query', message: 'Group by station needs Hit %' },
    });
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({
      status: 400,
      code: 'invalid_query',
      message: 'Group by station needs Hit %',
    });
  });

  it.each([
    [422, { detail: [{ msg: 'x' }] }, 'http_422', 'The request was not valid.'],
    [429, 'Too Many Requests', 'http_429', 'Too many attempts. Try again in a few minutes.'],
    [502, undefined, 'http_502', 'Server error. Try again shortly.'],
    [418, null, 'http_418', 'Request failed.'],
    [409, { error: 'conflict' }, 'http_409', 'Request failed.'],
    [404, { error: { code: 7, message: null } }, 'http_404', 'Not found.'],
  ])('falls back to http_%s and a default message', (status, body, code, message) => {
    expect(toApiError(status, body)).toMatchObject({ status, code, message });
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/api/errors.test.ts`
Expected: FAIL — `Failed to resolve import "./errors"`.

- [ ] **Step 4: Implement `ApiError` and `toApiError`**

Create the full contents of `frontend/src/api/errors.ts`:

```ts
/** An API failure with the C2 error envelope {"error": {"code", "message"}} unpacked. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

const DEFAULT_MESSAGES: Record<number, string> = {
  401: 'Please log in again.',
  403: 'You do not have access to this.',
  404: 'Not found.',
  413: 'That file is too large.',
  422: 'The request was not valid.',
  429: 'Too many attempts. Try again in a few minutes.',
};

function defaultMessage(status: number): string {
  return (
    DEFAULT_MESSAGES[status] ??
    (status >= 500 ? 'Server error. Try again shortly.' : 'Request failed.')
  );
}

/** Builds an ApiError from a status and a parsed response body (JSON object, text or undefined). */
export function toApiError(status: number, body: unknown): ApiError {
  const envelope =
    typeof body === 'object' && body !== null && 'error' in body
      ? (body as { error: unknown }).error
      : null;
  const fields =
    typeof envelope === 'object' && envelope !== null ? (envelope as Record<string, unknown>) : {};
  const code = typeof fields.code === 'string' ? fields.code : `http_${status}`;
  const message = typeof fields.message === 'string' ? fields.message : defaultMessage(status);
  return new ApiError(status, code, message);
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/api/errors.test.ts`
Expected: PASS — 7 tests.

- [ ] **Step 6: Write the failing API client test (unwrap and the 401 redirect)**

Create the full contents of `frontend/src/api/client.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../test/msw/server';
import { api, loginPath, setNavigate, shouldRedirectToLogin, unwrap } from './client';
import { ApiError } from './errors';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('unwrap', () => {
  it('returns the data of a 2xx response from a same-origin relative path', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({ status: 'ok', version: 'test' })));
    await expect(unwrap(api.GET('/api/health'))).resolves.toEqual({
      status: 'ok',
      version: 'test',
    });
  });

  it('throws ApiError carrying the server code and message', async () => {
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    const error: unknown = await unwrap(api.GET('/api/health')).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 500,
      code: 'internal',
      message: 'Internal server error',
    });
  });
});

describe('401 handling', () => {
  it.each([
    [401, '/api/health', '/events', true],
    [401, '/api/auth/me', '/events', false],
    [401, '/api/auth/login', '/login', false],
    [401, '/api/auth/logout', '/', false],
    [401, '/api/health', '/login', false],
    [403, '/api/health', '/events', false],
  ])('status %s from %s on page %s redirects: %s', (status, schemaPath, pathname, expected) => {
    expect(shouldRedirectToLogin(status, schemaPath, pathname)).toBe(expected);
  });

  it('builds next only from pathname + search', () => {
    window.history.replaceState(null, '', '/explorer?m=score&g=year#chart');
    expect(loginPath()).toBe('/login?next=%2Fexplorer%3Fm%3Dscore%26g%3Dyear');
  });

  it('sends an expired session on a data request to the login page with next', async () => {
    const navigate = vi.fn();
    setNavigate(navigate);
    window.history.replaceState(null, '', '/events/2026-09-13?rt=sporting');
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET('/api/health'))).rejects.toMatchObject({ status: 401 });
    expect(navigate).toHaveBeenCalledWith('/login?next=%2Fevents%2F2026-09-13%3Frt%3Dsporting');
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/api/client.test.ts`
Expected: FAIL — `Failed to resolve import "./client"`.

- [ ] **Step 8: Implement the client**

Create the full contents of `frontend/src/api/client.ts`:

```ts
import createClient, { type Middleware } from 'openapi-fetch';
import { toApiError } from './errors';
import type { paths } from './schema';

// `fetch` is looked up per request (not captured once at import) so MSW's patched fetch is used in
// tests; in browsers this is the same global fetch.
export const api = createClient<paths>({
  baseUrl: '',
  credentials: 'include',
  fetch: (request) => globalThis.fetch(request),
});

/** 401s from these endpoints are answers (logged out / wrong password), not expired sessions. */
const NO_LOGIN_REDIRECT = new Set(['/api/auth/me', '/api/auth/login', '/api/auth/logout']);

export function shouldRedirectToLogin(
  status: number,
  schemaPath: string,
  pathname: string,
): boolean {
  return status === 401 && !NO_LOGIN_REDIRECT.has(schemaPath) && pathname !== '/login';
}

/** The login URL for the current page; `next` is built only from pathname + search (C10). */
export function loginPath(): string {
  const next = window.location.pathname + window.location.search;
  return `/login?next=${encodeURIComponent(next)}`;
}

type Navigate = (to: string) => void;

let navigate: Navigate = (to) => {
  window.location.assign(to);
};

/** App.tsx routes the redirect through the data router so the SPA is not reloaded. */
export function setNavigate(fn: Navigate): void {
  navigate = fn;
}

const redirectOn401: Middleware = {
  onResponse({ response, schemaPath }) {
    if (shouldRedirectToLogin(response.status, schemaPath, window.location.pathname)) {
      navigate(loginPath());
    }
    return undefined;
  },
};

api.use(redirectOn401);

export interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * Resolves to the response data. Throws ApiError for every non-2xx response; network errors (the
 * fetch TypeError) propagate unchanged.
 */
export async function unwrap<T>(request: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw toApiError(response.status, error);
  return data as T;
}
```

- [ ] **Step 9: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/api`
Expected: PASS — 2 files, 17 tests; the three request tests reach MSW through the relative `/api/health` path, which
Plan 01's `setup.ts` resolves against the page origin (Step 1). If they instead report
`TypeError: Failed to parse URL from /api/health`, that line is missing: stop and report BLOCKED as in Step 1.

- [ ] **Step 10: Write the failing query-client test**

Create the full contents of `frontend/src/app/queryClient.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/errors';
import { createQueryClient, shouldRetry } from './queryClient';

describe('shouldRetry', () => {
  it('never retries a 4xx answer', () => {
    expect(shouldRetry(0, new ApiError(404, 'not_found', 'x'))).toBe(false);
    expect(shouldRetry(0, new ApiError(401, 'http_401', 'x'))).toBe(false);
  });

  it('retries 5xx and network errors twice', () => {
    const e500 = new ApiError(503, 'http_503', 'x');
    expect([0, 1, 2].map((n) => shouldRetry(n, e500))).toEqual([true, true, false]);
    expect([0, 1, 2].map((n) => shouldRetry(n, new TypeError('fetch failed')))).toEqual([
      true,
      true,
      false,
    ]);
  });
});

describe('createQueryClient', () => {
  it('uses the retry policy and does not refetch on window focus', () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.queries?.retry).toBe(shouldRetry);
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false);
    expect(defaults.mutations?.retry).toBe(false);
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/app/queryClient.test.ts`
Expected: FAIL — `Failed to resolve import "./queryClient"`.

- [ ] **Step 12: Implement the query client**

Create the full contents of `frontend/src/app/queryClient.ts`:

```ts
import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/errors';

/** Retry network and 5xx failures twice; never retry a 4xx answer. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 60_000, retry: shouldRetry, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
}
```

- [ ] **Step 13: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/app/queryClient.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 14: Write the failing providers and error-page test**

Create the full contents of `frontend/src/app/providers.test.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createTestQueryClient } from '../test/render';
import { RouteErrorPage } from './ErrorBoundary';
import { AppProviders } from './providers';

afterEach(() => {
  vi.restoreAllMocks();
});

function UsesQuery() {
  const { data } = useQuery({ queryKey: ['answer'], queryFn: () => Promise.resolve(42) });
  return <p>answer:{data ?? '…'}</p>;
}

function Boom(): never {
  throw new Error('kaboom');
}

describe('AppProviders', () => {
  it('provides a QueryClient to the tree', async () => {
    render(
      <AppProviders queryClient={createTestQueryClient()}>
        <UsesQuery />
      </AppProviders>,
    );
    expect(await screen.findByText('answer:42')).toBeInTheDocument();
  });

  it('shows the fallback instead of a blank page when a render throws, and logs the error', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    render(
      <AppProviders queryClient={createTestQueryClient()}>
        <Boom />
      </AppProviders>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
    expect(screen.getByRole('link', { name: 'Go to home' })).toHaveAttribute('href', '/');
    expect(log).toHaveBeenCalled();
  });
});

describe('RouteErrorPage', () => {
  it('renders "Page not found" for an unknown path', async () => {
    const router = createMemoryRouter(
      [{ path: '/', element: <p>home</p>, errorElement: <RouteErrorPage /> }],
      {
        initialEntries: ['/nope'],
      },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('renders a generic message when a route throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const router = createMemoryRouter([
      { path: '/', element: <Boom />, errorElement: <RouteErrorPage /> },
    ]);
    render(<RouterProvider router={router} />);
    expect(
      await screen.findByRole('heading', { name: 'Something went wrong' }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 15: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/app/providers.test.tsx`
Expected: FAIL — `Failed to resolve import "./ErrorBoundary"`.

- [ ] **Step 16: Implement the error boundaries, the provider stack, the test helpers and the App wiring**

Create the full contents of `frontend/src/app/ErrorBoundary.tsx`:

```tsx
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { isRouteErrorResponse, useRouteError } from 'react-router';

function Fallback({ title, message }: { title: string; message: string }) {
  return (
    <div
      role="alert"
      className="mx-auto flex max-w-md flex-col items-center gap-3 px-4 py-16 text-center"
    >
      <h1 className="text-lg font-medium text-text">{title}</h1>
      <p className="text-sm text-text-muted">{message}</p>
      <a
        href="/"
        className="inline-flex min-h-11 items-center rounded-button bg-primary px-4 text-sm text-text"
      >
        Go to home
      </a>
    </div>
  );
}

interface BoundaryState {
  error: Error | null;
}

/** Last-resort boundary around the whole app (render errors outside any route). */
export class AppErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  override state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(error, info.componentStack);
  }

  override render(): ReactNode {
    if (this.state.error) {
      return <Fallback title="Something went wrong" message="Reload the page to try again." />;
    }
    return this.props.children;
  }
}

/** errorElement for the root route: 404 for unknown paths, a generic message otherwise. */
export function RouteErrorPage() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) {
    return <Fallback title="Page not found" message="That page does not exist." />;
  }
  return (
    <Fallback
      title="Something went wrong"
      message="This page hit an error. Reloading usually fixes it."
    />
  );
}
```

Create the full contents of `frontend/src/app/providers.tsx`:

```tsx
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { AppErrorBoundary } from './ErrorBoundary';

/** The provider stack shared by App.tsx and test/render.tsx. */
export function AppProviders({
  queryClient,
  children,
}: {
  queryClient: QueryClient;
  children: ReactNode;
}) {
  return (
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </AppErrorBoundary>
  );
}
```

Replace the full contents of `frontend/src/test/render.tsx` (Plan 01's `renderWithProviders` and `renderRoute` keep
their names and parameters, now inside the production providers):

```tsx
import { QueryClient } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router';
import { AppProviders } from '../app/providers';
import { appRoutes } from '../app/router';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
}

export interface RenderOptions {
  /** Initial URL (path + query), default '/'. */
  route?: string;
  /** Route pattern `ui` is mounted at (renderWithProviders only), default '*'. */
  path?: string;
  queryClient?: QueryClient;
}

export interface ProvidersResult extends RenderResult {
  user: UserEvent;
  queryClient: QueryClient;
  router: ReturnType<typeof createMemoryRouter>;
}

/** Renders a route tree in a memory router inside the production provider stack. */
export function renderRoutes(routes: RouteObject[], options: RenderOptions = {}): ProvidersResult {
  const queryClient = options.queryClient ?? createTestQueryClient();
  const router = createMemoryRouter(routes, { initialEntries: [options.route ?? '/'] });
  const user = userEvent.setup();
  const result = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...result, user, queryClient, router };
}

/** Renders one element at `path` (default '*') with router, query client and error boundary. */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderOptions = {},
): ProvidersResult {
  return renderRoutes([{ path: options.path ?? '*', element: ui }], options);
}

/** Plan 01 T2's helper, kept: the real route tree at `route` (lazy pages need findBy* queries). */
export function renderRoute(route: string, routes: RouteObject[] = appRoutes): ProvidersResult {
  return renderRoutes(routes, { route });
}
```

Replace the full contents of `frontend/src/app/App.tsx`:

```tsx
import { RouterProvider } from 'react-router';
import { setNavigate } from '../api/client';
import { AppProviders } from './providers';
import { createQueryClient } from './queryClient';
import { createAppRouter } from './router';

const router = createAppRouter();
const queryClient = createQueryClient();

setNavigate((to) => {
  void router.navigate(to);
});

export function App() {
  return (
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
```

- [ ] **Step 17: Run the app tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/app src/test`
Expected: PASS — `providers.test.tsx` 4 tests, `queryClient.test.ts` 3, and Plan 01's `App.test.tsx`,
`router.test.tsx`, `registry.test.ts` and `setup.test.ts` unchanged.

- [ ] **Step 18: Write the viewport helper and the failing media-query test**

Create the full contents of `frontend/src/test/viewport.ts`:

```ts
import { vi } from 'vitest';

/**
 * Makes window.matchMedia answer the C10 layout queries: '(min-width: 1024px)' matches only for
 * 'desktop'; '(pointer: coarse)' matches for 'mobile' unless `touch` says otherwise.
 * It spies on the setup.ts shim; vitest.config.ts's `restoreMocks: true` undoes it after every
 * test, and tests also call vi.restoreAllMocks() in afterEach so they never depend on that.
 */
export function stubViewport(kind: 'desktop' | 'mobile', { touch = kind === 'mobile' } = {}): void {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches:
          query === '(min-width: 1024px)'
            ? kind === 'desktop'
            : query === '(pointer: coarse)'
              ? touch
              : false,
        media: query,
        onchange: null,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}
```

Create the full contents of `frontend/src/lib/useMediaQuery.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { stubViewport } from '../test/viewport';
import { useIsDesktop, useIsTouch } from './useMediaQuery';

type Listener = () => void;

function stubMatchMedia(initial: Record<string, boolean>) {
  const state = { ...initial };
  const listeners = new Map<string, Set<Listener>>();
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        get matches() {
          return state[query] ?? false;
        },
        media: query,
        addEventListener: (_: string, l: Listener) => {
          listeners.set(query, (listeners.get(query) ?? new Set()).add(l));
        },
        removeEventListener: (_: string, l: Listener) => listeners.get(query)?.delete(l),
      }) as unknown as MediaQueryList,
  );
  return {
    set(query: string, matches: boolean) {
      state[query] = matches;
      listeners.get(query)?.forEach((l) => l());
    },
    listenerCount: (query: string) => listeners.get(query)?.size ?? 0,
  };
}

function Probe() {
  return (
    <p>
      desktop:{String(useIsDesktop())} touch:{String(useIsTouch())}
    </p>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useMediaQuery', () => {
  it('matches the C10 desktop and touch queries as stubbed by stubViewport', () => {
    stubViewport('desktop');
    render(<Probe />);
    expect(screen.getByText('desktop:true touch:false')).toBeInTheDocument();
  });

  it('treats a phone as touch-first', () => {
    stubViewport('mobile');
    render(<Probe />);
    expect(screen.getByText('desktop:false touch:true')).toBeInTheDocument();
  });

  it('reads the current match and follows changes', () => {
    const media = stubMatchMedia({ '(min-width: 1024px)': false, '(pointer: coarse)': true });
    render(<Probe />);
    expect(screen.getByText('desktop:false touch:true')).toBeInTheDocument();
    act(() => media.set('(min-width: 1024px)', true));
    expect(screen.getByText('desktop:true touch:true')).toBeInTheDocument();
  });

  it('unsubscribes on unmount', () => {
    const media = stubMatchMedia({});
    const { unmount } = render(<Probe />);
    expect(media.listenerCount('(min-width: 1024px)')).toBe(1);
    unmount();
    expect(media.listenerCount('(min-width: 1024px)')).toBe(0);
  });
});
```

- [ ] **Step 19: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/useMediaQuery.test.tsx`
Expected: FAIL — `Failed to resolve import "./useMediaQuery"`.

- [ ] **Step 20: Implement the media-query hooks**

Create the full contents of `frontend/src/lib/useMediaQuery.ts`:

```ts
import { useCallback, useSyncExternalStore } from 'react';

export const DESKTOP_QUERY = '(min-width: 1024px)';
export const COARSE_POINTER_QUERY = '(pointer: coarse)';

export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}

/** ≥1024px: side navigation layout (C10). */
export function useIsDesktop(): boolean {
  return useMediaQuery(DESKTOP_QUERY);
}

/** Touch-first device: charts pan only in fullscreen (C10 zoom rules). */
export function useIsTouch(): boolean {
  return useMediaQuery(COARSE_POINTER_QUERY);
}
```

- [ ] **Step 21: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/useMediaQuery.test.tsx`
Expected: PASS — 4 tests.

- [ ] **Step 22: Write the failing URL-state test**

Create the full contents of `frontend/src/lib/useUrlState.test.tsx`:

```tsx
import { act, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../test/render';
import {
  boolCodec,
  enumCodec,
  intCodec,
  isoDateCodec,
  listCodec,
  numberCodec,
  rangeCodec,
  stringCodec,
  useUrlState,
} from './useUrlState';

const METRICS = ['score', 'adjusted', 'rounds'] as const;
const metricCodec = enumCodec(METRICS);

function Probe({ onSet }: { onSet: (set: (v: (typeof METRICS)[number]) => void) => void }) {
  const [metric, setMetric] = useUrlState('m', metricCodec, 'score');
  onSet(setMetric);
  return <p>metric:{metric}</p>;
}

function setup(route: string) {
  let setter: (v: (typeof METRICS)[number]) => void = () => undefined;
  const view = renderWithProviders(<Probe onSet={(s) => (setter = s)} />, { route });
  return { ...view, set: (v: (typeof METRICS)[number]) => act(() => setter(v)) };
}

describe('useUrlState', () => {
  it('reads the default when the key is missing', () => {
    setup('/explorer');
    expect(screen.getByText('metric:score')).toBeInTheDocument();
  });

  it('reads a valid value and ignores an invalid one', () => {
    setup('/explorer?m=rounds');
    expect(screen.getByText('metric:rounds')).toBeInTheDocument();
    setup('/explorer?m=bogus');
    expect(screen.getByText('metric:score')).toBeInTheDocument();
  });

  it('writes to the query string, keeps other keys and replaces history', async () => {
    const { set, router } = setup('/explorer?g=year');
    await set('adjusted');
    expect(router.state.location.search).toBe('?g=year&m=adjusted');
    expect(router.state.historyAction).toBe('REPLACE');
    expect(screen.getByText('metric:adjusted')).toBeInTheDocument();
  });

  it('removes the key when set back to the default', async () => {
    const { set, router } = setup('/explorer?m=rounds&g=year');
    await set('score');
    expect(router.state.location.search).toBe('?g=year');
  });
});

describe('codecs', () => {
  const metricList = listCodec(metricCodec);
  it.each<[string, (raw: string) => unknown, string, unknown]>([
    ['string', stringCodec.parse, 'abc', 'abc'],
    ['int', intCodec.parse, '-12', -12],
    ['int rejects decimals', intCodec.parse, '1.5', null],
    ['number', numberCodec.parse, '1.5', 1.5],
    ['number rejects blank', numberCodec.parse, ' ', null],
    ['number rejects text', numberCodec.parse, 'x', null],
    ['bool true', boolCodec.parse, '1', true],
    ['bool false', boolCodec.parse, '0', false],
    ['bool rejects other', boolCodec.parse, 'yes', null],
    ['enum', metricCodec.parse, 'rounds', 'rounds'],
    ['enum rejects', metricCodec.parse, 'x', null],
    [
      'list drops invalid and duplicate items',
      metricList.parse,
      'rounds,x,rounds,score',
      ['rounds', 'score'],
    ],
    ['list empty', metricList.parse, '', []],
    ['range', rangeCodec.parse, '-5..40.5', [-5, 40.5]],
    ['range rejects reversed', rangeCodec.parse, '40..5', null],
    ['range rejects junk', rangeCodec.parse, '1..2..3', null],
    ['range rejects text', rangeCodec.parse, 'a..2', null],
    ['date', isoDateCodec.parse, '2026-09-13', '2026-09-13'],
    ['date rejects impossible day', isoDateCodec.parse, '2026-02-30', null],
    ['date rejects format', isoDateCodec.parse, '9/13/2026', null],
  ])('%s', (_name, parse, raw, expected) => {
    expect(parse(raw)).toEqual(expected);
  });

  it('serializes lists, ranges and booleans', () => {
    expect(listCodec(metricCodec).serialize(['score', 'rounds'])).toBe('score,rounds');
    expect(rangeCodec.serialize([0, 12.5])).toBe('0..12.5');
    expect(boolCodec.serialize(true)).toBe('1');
    expect(boolCodec.serialize(false)).toBe('0');
    expect(intCodec.serialize(7)).toBe('7');
  });
});
```

- [ ] **Step 23: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/useUrlState.test.tsx`
Expected: FAIL — `Failed to resolve import "./useUrlState"`.

- [ ] **Step 24: Implement `useUrlState` and the codecs**

Create the full contents of `frontend/src/lib/useUrlState.ts`:

```ts
import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

/** Converts one query-string value; parse returns null for anything invalid. */
export interface Codec<T> {
  parse: (raw: string) => T | null;
  serialize: (value: T) => string;
}

/**
 * State stored in the query string under `key`. Missing or invalid values read as `defaultValue`;
 * writing the default removes the key. Updates replace the history entry. `defaultValue` should be
 * referentially stable (a module constant) for list/object values. One setter call per event:
 * React Router applies each setSearchParams against the current URL, so a second call in the same
 * event would overwrite the first.
 */
export function useUrlState<T>(
  key: string,
  codec: Codec<T>,
  defaultValue: T,
): [T, (next: T) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(key);
  const parsed = raw === null ? null : codec.parse(raw);
  const value = parsed ?? defaultValue;
  const setValue = useCallback(
    (next: T) => {
      setParams(
        (prev) => {
          const out = new URLSearchParams(prev);
          const serialized = codec.serialize(next);
          if (serialized === codec.serialize(defaultValue)) out.delete(key);
          else out.set(key, serialized);
          return out;
        },
        { replace: true },
      );
    },
    [setParams, key, codec, defaultValue],
  );
  return [value, setValue];
}

export const stringCodec: Codec<string> = { parse: (raw) => raw, serialize: (v) => v };

export const intCodec: Codec<number> = {
  parse: (raw) => (/^-?\d+$/.test(raw) ? Number(raw) : null),
  serialize: (v) => String(v),
};

export const numberCodec: Codec<number> = {
  parse: (raw) => {
    const n = Number(raw);
    return raw.trim() !== '' && Number.isFinite(n) ? n : null;
  },
  serialize: (v) => String(v),
};

export const boolCodec: Codec<boolean> = {
  parse: (raw) => (raw === '1' ? true : raw === '0' ? false : null),
  serialize: (v) => (v ? '1' : '0'),
};

export function enumCodec<T extends string>(values: readonly T[]): Codec<T> {
  return { parse: (raw) => values.find((v) => v === raw) ?? null, serialize: (v) => v };
}

/** Comma-separated list; invalid and duplicate items are dropped. */
export function listCodec<T>(item: Codec<T>): Codec<T[]> {
  return {
    parse: (raw) => {
      const items = raw === '' ? [] : raw.split(',').map((part) => item.parse(part));
      const kept: T[] = [];
      for (const v of items) if (v !== null && !kept.includes(v)) kept.push(v);
      return kept;
    },
    serialize: (values) => values.map((v) => item.serialize(v)).join(','),
  };
}

/** `lo..hi` with finite numbers and lo <= hi. */
export const rangeCodec: Codec<[number, number]> = {
  parse: (raw) => {
    const parts = raw.split('..');
    if (parts.length !== 2) return null;
    const lo = numberCodec.parse(parts[0] ?? '');
    const hi = numberCodec.parse(parts[1] ?? '');
    return lo !== null && hi !== null && lo <= hi ? [lo, hi] : null;
  },
  serialize: ([lo, hi]) => `${lo}..${hi}`,
};

/** A real calendar date written as YYYY-MM-DD. */
export const isoDateCodec: Codec<string> = {
  parse: (raw) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
    const d = new Date(`${raw}T00:00:00Z`);
    return !Number.isNaN(d.getTime()) && d.toISOString().startsWith(raw) ? raw : null;
  },
  serialize: (v) => v,
};
```

- [ ] **Step 25: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/useUrlState.test.tsx`
Expected: PASS — 25 tests.

- [ ] **Step 26: Write the failing round-type filter hook test**

Create the full contents of `frontend/src/lib/roundTypes.test.tsx`:

```tsx
import { act, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../test/render';
import { useRoundTypes, type RoundTypeValue } from './roundTypes';

function Probe({ onSet }: { onSet: (s: (v: RoundTypeValue[]) => void) => void }) {
  const [rt, setRt] = useRoundTypes();
  onSet(setRt);
  return <p>rt:{rt.join('|') || 'all'}</p>;
}

describe('useRoundTypes', () => {
  it('binds the rt query parameter and drops unknown values', () => {
    renderWithProviders(<Probe onSet={() => undefined} />, { route: '/?rt=sporting,bogus' });
    expect(screen.getByText('rt:sporting')).toBeInTheDocument();
  });

  it('writes rt and clears it for no filter', async () => {
    let set: (v: RoundTypeValue[]) => void = () => undefined;
    const { router } = renderWithProviders(<Probe onSet={(s) => (set = s)} />);
    expect(screen.getByText('rt:all')).toBeInTheDocument();
    await act(() => set(['super_sporting', 'unknown']));
    expect(router.state.location.search).toBe('?rt=super_sporting%2Cunknown');
    await act(() => set([]));
    expect(router.state.location.search).toBe('');
  });
});
```

- [ ] **Step 27: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/roundTypes.test.tsx`
Expected: FAIL — `Failed to resolve import "./roundTypes"`.

- [ ] **Step 28: Implement the round-type filter hook**

Create the full contents of `frontend/src/lib/roundTypes.ts`:

```ts
import { enumCodec, listCodec, useUrlState, type Codec } from './useUrlState';

export const ROUND_TYPES = ['sporting', 'super_sporting', 'unknown'] as const;
export type RoundTypeValue = (typeof ROUND_TYPES)[number];

export const ROUND_TYPE_LABELS: Record<RoundTypeValue, string> = {
  sporting: 'Sporting',
  super_sporting: 'Super Sporting',
  unknown: 'Unknown',
};

export const roundTypesCodec: Codec<RoundTypeValue[]> = listCodec(enumCodec(ROUND_TYPES));

const NONE: RoundTypeValue[] = [];

/** The global round-type filter (C10), stored in the `rt` query parameter; [] = no filter. */
export function useRoundTypes(): [RoundTypeValue[], (next: RoundTypeValue[]) => void] {
  return useUrlState('rt', roundTypesCodec, NONE);
}
```

- [ ] **Step 29: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/roundTypes.test.tsx`
Expected: PASS — 2 tests.

- [ ] **Step 30: Write the failing formatter test**

Create the full contents of `frontend/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  formatDate,
  formatMonth,
  formatNumber,
  formatPercent,
  formatPrecip,
  formatPressure,
  formatShortDate,
  formatSigned,
  formatTemp,
  formatWind,
  parseIsoDate,
} from './format';

describe('format', () => {
  it('formats pressure from hPa to inHg with 2 decimals', () => {
    expect(formatPressure(1013.25)).toBe('29.92 inHg');
    expect(formatPressure(1000)).toBe('29.53 inHg');
  });

  it('formats numbers, percents and signed deltas', () => {
    expect(formatNumber(7480)).toBe('7,480');
    expect(formatNumber(35.2549, 2)).toBe('35.25');
    expect(formatPercent(72.1081)).toBe('72.1%');
    expect(formatSigned(2)).toBe('+2.0');
    expect(formatSigned(-1.46)).toBe('−1.5');
    expect(formatSigned(0.04)).toBe('0.0');
    expect(formatSigned(-0.04)).toBe('0.0');
  });

  it('formats weather units', () => {
    expect(formatTemp(54.6)).toBe('55°F');
    expect(formatWind(12.4)).toBe('12 mph');
    expect(formatPrecip(0.051)).toBe('0.05 in');
  });

  it('renders a dash for missing or non-finite values', () => {
    for (const fn of [
      formatNumber,
      formatPercent,
      formatSigned,
      formatTemp,
      formatWind,
      formatPrecip,
      formatPressure,
    ]) {
      expect(fn(null)).toBe('—');
      expect(fn(undefined)).toBe('—');
      expect(fn(Number.NaN)).toBe('—');
    }
  });

  it('formats ISO dates as local calendar dates (no UTC shift)', () => {
    expect(formatDate('2026-09-13')).toBe('Sep 13, 2026');
    expect(formatShortDate('2026-01-04')).toBe('Jan 4');
    expect(formatMonth('2025-03')).toBe('Mar 2025');
    expect(parseIsoDate('2026-09-13')?.getDate()).toBe(13);
  });

  it('rejects malformed or impossible dates', () => {
    expect(parseIsoDate('2026-02-30')).toBeNull();
    expect(parseIsoDate('13/09/2026')).toBeNull();
    expect(formatDate('garbage')).toBe('—');
    expect(formatDate(null)).toBe('—');
    expect(formatMonth(undefined)).toBe('—');
  });
});
```

- [ ] **Step 31: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/format.test.ts`
Expected: FAIL — `Failed to resolve import "./format"`.

- [ ] **Step 32: Implement the formatters**

Create the full contents of `frontend/src/lib/format.ts`:

```ts
const DASH = '—';
const MINUS = '−';

type Maybe = number | null | undefined;

const isNum = (v: Maybe): v is number => typeof v === 'number' && Number.isFinite(v);

export function formatNumber(v: Maybe, digits = 0): string {
  if (!isNum(v)) return DASH;
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v);
}

/** `v` is already a percentage (0–100). */
export function formatPercent(v: Maybe, digits = 1): string {
  return isNum(v) ? `${formatNumber(v, digits)}%` : DASH;
}

/** +1.5 / −1.5 (true minus sign) / 0.0 */
export function formatSigned(v: Maybe, digits = 1): string {
  if (!isNum(v)) return DASH;
  const magnitude = formatNumber(Math.abs(v), digits);
  if (Number(magnitude.replace(/,/g, '')) === 0) return magnitude;
  return `${v > 0 ? '+' : MINUS}${magnitude}`;
}

export function formatTemp(f: Maybe): string {
  return isNum(f) ? `${Math.round(f)}°F` : DASH;
}

export function formatWind(mph: Maybe): string {
  return isNum(mph) ? `${Math.round(mph)} mph` : DASH;
}

export function formatPrecip(inches: Maybe): string {
  return isNum(inches) ? `${inches.toFixed(2)} in` : DASH;
}

/** Stored in hPa, displayed in inHg (× 0.02953, 2 dp) — Global Constraints. */
export function formatPressure(hPa: Maybe): string {
  return isNum(hPa) ? `${(hPa * 0.02953).toFixed(2)} inHg` : DASH;
}

/** Parses YYYY-MM-DD as a local calendar date (never shifted by the UTC offset). */
export function parseIsoDate(iso: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.getMonth() === Number(m[2]) - 1 ? d : null;
}

function formatWith(iso: string | null | undefined, options: Intl.DateTimeFormatOptions): string {
  const d = iso ? parseIsoDate(iso) : null;
  return d ? new Intl.DateTimeFormat('en-US', options).format(d) : DASH;
}

/** 2026-09-13 → Sep 13, 2026 */
export function formatDate(iso: string | null | undefined): string {
  return formatWith(iso, { month: 'short', day: 'numeric', year: 'numeric' });
}

/** 2026-09-13 → Sep 13 */
export function formatShortDate(iso: string | null | undefined): string {
  return formatWith(iso, { month: 'short', day: 'numeric' });
}

/** 2025-03 → Mar 2025 */
export function formatMonth(yearMonth: string | null | undefined): string {
  return formatWith(yearMonth ? `${yearMonth}-01` : null, { month: 'short', year: 'numeric' });
}
```

- [ ] **Step 33: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/format.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 34: Write the failing CSV test**

Create the full contents of `frontend/src/lib/csv.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { downloadCsv, toCsv } from './csv';

const COLUMNS = [
  { key: 'shooter', label: 'Shooter' },
  { key: 'value', label: 'Avg score' },
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe('toCsv', () => {
  it('writes a header of labels and one CRLF line per row', () => {
    expect(
      toCsv(COLUMNS, [
        { shooter: 'Able, Ann', value: 35.5 },
        { shooter: 'Baker', value: null },
      ]),
    ).toBe('Shooter,Avg score\r\n"Able, Ann",35.5\r\nBaker,\r\n');
  });

  it('quotes embedded quotes and newlines', () => {
    expect(toCsv([{ key: 'n', label: 'Name' }], [{ n: 'Barrett "Raymond\'s Dad"\nX' }])).toBe(
      'Name\r\n"Barrett ""Raymond\'s Dad""\nX"\r\n',
    );
  });

  it('neutralises text that a spreadsheet would run as a formula, but not numbers', () => {
    const csv = toCsv(
      [
        { key: 'n', label: 'Name' },
        { key: 'v', label: 'Delta' },
      ],
      [
        { n: '=HYPERLINK("x")', v: -3 },
        { n: '@SUM(A1)', v: Number.NaN },
        { n: '+1', v: undefined },
      ],
    );
    expect(csv).toBe('Name,Delta\r\n"\'=HYPERLINK(""x"")",-3\r\n\'@SUM(A1),\r\n\'+1,\r\n');
  });
});

describe('downloadCsv', () => {
  it('downloads a UTF-8 CSV with a BOM under the given name', async () => {
    const clicked: { download: string; href: string }[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push({ download: this.download, href: this.href });
    });
    const createUrl = vi.spyOn(URL, 'createObjectURL');
    downloadCsv('scores-by-year', COLUMNS, [{ shooter: 'Slocum', value: 40 }]);
    expect(clicked).toEqual([
      {
        download: 'scores-by-year.csv',
        href: expect.stringMatching(/^blob:/) as unknown as string,
      },
    ]);
    const blob = createUrl.mock.calls[0]?.[0] as Blob;
    expect(blob.type).toBe('text/csv;charset=utf-8');
    const bytes = new Uint8Array(await blob.arrayBuffer());
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
    expect(new TextDecoder().decode(bytes.slice(3))).toBe('Shooter,Avg score\r\nSlocum,40\r\n');
    expect(document.querySelector('a[download]')).toBeNull();
  });

  it('keeps an existing .csv extension', () => {
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });
    downloadCsv('rounds.csv', COLUMNS, []);
    expect(names).toEqual(['rounds.csv']);
  });
});
```

- [ ] **Step 35: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/csv.test.ts`
Expected: FAIL — `Failed to resolve import "./csv"`.

- [ ] **Step 36: Implement the download helper and CSV export**

Create the full contents of `frontend/src/lib/download.ts`:

```ts
/** Saves a Blob through a temporary <a download> link. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}
```

Create the full contents of `frontend/src/lib/csv.ts` (keep the BOM as the `'\uFEFF'` escape, never a literal
character):

```ts
import { downloadBlob } from './download';

export interface CsvColumn {
  key: string;
  label: string;
}

export type CsvRow = Record<string, string | number | null | undefined>;

/** Text cells starting with these could run as spreadsheet formulas; they get a leading quote. */
const FORMULA_START = /^[=+\-@\t\r]/;

function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  let text = typeof value === 'number' ? (Number.isFinite(value) ? String(value) : '') : value;
  if (typeof value === 'string' && FORMULA_START.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** RFC 4180 CSV (CRLF line endings) with a header row of column labels. */
export function toCsv(columns: readonly CsvColumn[], rows: readonly CsvRow[]): string {
  const lines = [
    columns.map((c) => cell(c.label)).join(','),
    ...rows.map((row) => columns.map((c) => cell(row[c.key])).join(',')),
  ];
  return `${lines.join('\r\n')}\r\n`;
}

/** Downloads rows as `<name>.csv` (UTF-8 with BOM so Excel reads accents correctly). */
export function downloadCsv(
  name: string,
  columns: readonly CsvColumn[],
  rows: readonly CsvRow[],
): void {
  const filename = name.endsWith('.csv') ? name : `${name}.csv`;
  const blob = new Blob(['\uFEFF', toCsv(columns, rows)], { type: 'text/csv;charset=utf-8' });
  downloadBlob(blob, filename);
}
```

- [ ] **Step 37: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/csv.test.ts`
Expected: PASS — 5 tests.

- [ ] **Step 38: Write the failing "that's me" storage test**

Create the full contents of `frontend/src/lib/me.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, getMe, setMe } from './me';

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('me', () => {
  it('remembers, reads and clears the chosen shooter id', () => {
    expect(getMe()).toBeNull();
    setMe(42);
    expect(getMe()).toBe(42);
    clearMe();
    expect(getMe()).toBeNull();
  });

  it('ignores a corrupted stored value', () => {
    localStorage.setItem('sc.me', 'abc');
    expect(getMe()).toBeNull();
    localStorage.setItem('sc.me', '-3');
    expect(getMe()).toBeNull();
  });

  it('never throws when storage is unavailable', () => {
    const boom = () => {
      throw new DOMException('denied', 'SecurityError');
    };
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(boom);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(boom);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(boom);
    expect(getMe()).toBeNull();
    expect(() => setMe(1)).not.toThrow();
    expect(() => clearMe()).not.toThrow();
  });
});
```

- [ ] **Step 39: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/me.test.ts`
Expected: FAIL — `Failed to resolve import "./me"`.

- [ ] **Step 40: Implement the storage helpers**

Create the full contents of `frontend/src/lib/me.ts`:

```ts
/** "That's me" personalization: the viewer's own shooter id, kept only in this browser. */
const KEY = 'sc.me';

export function getMe(): number | null {
  try {
    const raw = localStorage.getItem(KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

export function setMe(id: number): void {
  try {
    localStorage.setItem(KEY, String(id));
  } catch {
    // Storage unavailable (private mode, quota): personalization is best-effort.
  }
}

export function clearMe(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Storage unavailable: nothing to clear.
  }
}
```

- [ ] **Step 41: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/me.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 42: Write the failing share test**

Create the full contents of `frontend/src/lib/share.test.ts`:

```ts
import { toBlob } from 'html-to-image';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from './share';

vi.mock('html-to-image', () => ({ toBlob: vi.fn() }));

const png = new Blob(['png-bytes'], { type: 'image/png' });

beforeEach(() => {
  vi.mocked(toBlob).mockResolvedValue(png);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function captureDownloads(): string[] {
  const names: string[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    names.push(this.download);
  });
  return names;
}

describe('shareElementAsImage', () => {
  it('shares a PNG file through the Web Share API when files can be shared', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    const share = vi.spyOn(navigator, 'share').mockResolvedValue(undefined);
    const el = document.createElement('div');
    await expect(shareElementAsImage(el, 'event-2026-09-13')).resolves.toBe('shared');
    expect(vi.mocked(toBlob).mock.calls[0]?.[0]).toBe(el);
    const file = share.mock.calls[0]?.[0]?.files?.[0];
    expect(file?.name).toBe('event-2026-09-13.png');
    expect(file?.type).toBe('image/png');
  });

  it('downloads the PNG when the browser cannot share files', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(false);
    const names = captureDownloads();
    await expect(shareElementAsImage(document.createElement('div'), 'odometer.png')).resolves.toBe(
      'downloaded',
    );
    expect(names).toEqual(['odometer.png']);
  });

  it('downloads when canShare is not supported at all', async () => {
    vi.stubGlobal('navigator', { ...navigator, canShare: undefined });
    const names = captureDownloads();
    await expect(shareElementAsImage(document.createElement('div'), 'x')).resolves.toBe(
      'downloaded',
    );
    expect(names).toEqual(['x.png']);
    vi.unstubAllGlobals();
  });

  it('reports a dismissed share sheet as cancelled and rethrows other failures', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    const share = vi.spyOn(navigator, 'share');
    share.mockRejectedValueOnce(new DOMException('dismissed', 'AbortError'));
    await expect(shareElementAsImage(document.createElement('div'), 'a')).resolves.toBe(
      'cancelled',
    );
    share.mockRejectedValueOnce(new DOMException('nope', 'NotAllowedError'));
    await expect(shareElementAsImage(document.createElement('div'), 'a')).rejects.toThrow('nope');
  });

  it('fails loudly when the element cannot be rendered', async () => {
    vi.mocked(toBlob).mockResolvedValue(null);
    await expect(shareElementAsImage(document.createElement('div'), 'a')).rejects.toThrow(
      'Could not render the image',
    );
  });
});
```

- [ ] **Step 43: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/share.test.ts`
Expected: FAIL — `Failed to resolve import "./share"`.

- [ ] **Step 44: Implement image sharing**

Create the full contents of `frontend/src/lib/share.ts`:

```ts
import { toBlob } from 'html-to-image';
import { downloadBlob } from './download';

export type ShareOutcome = 'shared' | 'downloaded' | 'cancelled';

/**
 * Renders `el` to a PNG and hands it to the Web Share API when the browser can share files,
 * otherwise downloads it. Resolves 'cancelled' when the user dismisses the share sheet.
 */
export async function shareElementAsImage(
  el: HTMLElement,
  filename: string,
): Promise<ShareOutcome> {
  const name = filename.endsWith('.png') ? filename : `${filename}.png`;
  const blob = await toBlob(el, {
    pixelRatio: 2,
    cacheBust: true,
    backgroundColor: getComputedStyle(document.body).backgroundColor,
  });
  if (!blob) throw new Error('Could not render the image');
  const file = new File([blob], name, { type: 'image/png' });
  if (typeof navigator.canShare === 'function' && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title: name });
      return 'shared';
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled';
      throw error;
    }
  }
  downloadBlob(blob, name);
  return 'downloaded';
}
```

- [ ] **Step 45: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib`
Expected: PASS — 7 files, 50 tests.

- [ ] **Step 46: Full suite, coverage, lint, types, format and build**

Run: `cd frontend && pnpm exec prettier --write src`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; coverage ≥90% lines and ≥90% branches; `src/api`, `src/app` and `src/lib` each
≥90% lines.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings.
Run: `cd frontend && pnpm build`
Expected: the build succeeds.

- [ ] **Step 47: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/api/errors.ts frontend/src/api/errors.test.ts frontend/src/api/client.ts \
  frontend/src/api/client.test.ts frontend/src/app frontend/src/test frontend/src/lib
git commit -F - <<'MSG'
feat(frontend): API client with 401 redirect, providers, URL state and lib helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

### Task 5: `EChart` wrapper, `TabularData` and every chart builder (master Plan 07 T5)

**Context.** Task 1 has merged (`theme/tokens.ts` `chartPalette`, `theme/echartsTheme.ts`
`ECHARTS_THEME_NAME`/`echartsTheme`). This task creates the chart layer's data type (`TabularData`, C10), the thin
`EChart` wrapper (tree-shaken `echarts/core` imports, the `sunday-clays` theme, a ResizeObserver that re-measures the
container, canvas renderer, and no `setOption` for an option equal to the last one, so re-renders keep the user's zoom;
Decision D16), and all ten C10 builders as pure functions `(data, opts) => EChartsOption`, unit-tested without
rendering. Builders never import `api/schema.d.ts`. Any `tooltip.formatter` that returns a string passes every
data-derived string through `escapeHtml` (`echarts/core` `format.encodeHTML`), and each such builder's test feeds the
name `<img src=x onerror=alert(1)>` and asserts `&lt;img` appears (C10). Formatters read only values that are also in
the option (D16). Later plans consume these builders unchanged (Plan 09 T6 maps leaderboard frames onto
`LeaderboardFrame`). Run every command from the worktree root: frontend commands start with `cd frontend && `, and the
commit step starts with `cd "$(git rev-parse --show-toplevel)"` (agent shells reset the working directory between
calls, Decision D28).

**Files:**
- Create: `frontend/src/components/charts/types.ts`, `frontend/src/components/charts/EChart.tsx`; Test:
  `frontend/src/components/charts/EChart.test.tsx`
- Create: `frontend/src/components/charts/builders/{common,line,bar,scatter,heatmap,histogram,boxplot,calendar,race,bump,ridgeline}.ts`
- Test: `frontend/src/components/charts/builders/{common,line,bar,scatter,heatmap,histogram,boxplot,calendar,race,bump,ridgeline}.test.ts`

**Interfaces:**
- Consumes (Task 1): `chartPalette`, `colors`, `gridLine` from `theme/tokens.ts`; `ECHARTS_THEME_NAME`, `echartsTheme`
  from `theme/echartsTheme.ts`. Packages `echarts`, `react`; `vitest-canvas-mock` from Plan 01's `test/setup.ts`.
- Produces:
  - `components/charts/types.ts`: `type ColumnType = 'date' | 'number' | 'string' | 'int'`,
    `interface TabularColumn {key; label; type: ColumnType}`, `type Cell = string | number | null`,
    `type TabularRow = Record<string, Cell>`, `interface TabularData {columns: TabularColumn[]; rows: TabularRow[]}`,
    `type ChartType = 'bar' | 'line' | 'heatmap'`, `interface LeaderboardFrame {date: string; rows: {id: number |
    string; name: string; value: number; rank: number}[]}` (Decision D16).
  - `components/charts/EChart.tsx`: `EChart({option, height, onEvents?, ariaLabel})`,
    `type EChartEventName = 'click' | 'dblclick' | 'mouseover' | 'mouseout'`,
    `type EChartEvents = {[K in EChartEventName]?: ((params: ECElementEvent) => void) | undefined}`,
    `interface EChartProps`. Renders `<div role="img" aria-label={ariaLabel}>`; re-measures its container on resize
    (`chart.resize({width: 'auto', height: 'auto'})`) and skips `setOption` for an option whose content equals the last
    one applied, so parent re-renders never reset zoom or replay animations (Decision D16).
  - `builders/common.ts`: `escapeHtml(value: unknown): string`, `requireColumn(data, key): TabularColumn` (throws
    `Unknown column "<key>"`), `numeric(cell): number | null`, `axisTypeFor(column): 'time' | 'category' | 'value'`,
    `distinct<T>(values): T[]`, `cellLabel(cell): string` (`—` for null), `GRID` (frozen shared grid margins; copy to
    adjust), `legendFor(seriesCount)`.
  - `builders/line.ts`: `interface LineOpts {x; y: string[]; seriesBy?; band?: {lower; upper; name?}; markers?:
    {flag; name}; area?; smooth?; yName?; scaleY?}`, `lineOption(data, opts)`.
  - `builders/bar.ts`: `interface BarOpts {x; y: string[]; seriesBy?; horizontal?; stack?; yName?; labels?}`,
    `barOption(data, opts)`.
  - `builders/scatter.ts`: `interface ScatterOpts {x; y; label?; seriesBy?; fit?; xName?; yName?}`,
    `interface LinearFit {slope; intercept}`, `linearFit(points): LinearFit | null`, `scatterOption(data, opts)`.
  - `builders/heatmap.ts`: `interface HeatmapOpts {x; y; value; min?; max?; labels?}`, `heatmapOption(data, opts)`.
  - `builders/histogram.ts`: `interface HistogramOpts {value; binWidth; min?; max?; seriesBy?; normalize?; xName?}`,
    `binValues(values, binWidth, min, max): number[]`, `histogramOption(data, opts)`.
  - `builders/boxplot.ts`: `interface BoxplotOpts {group; value; yName?}`, `interface FiveNumber {min; q1; median; q3;
    max; outliers}`, `quantile(sorted, p)`, `fiveNumber(values): FiveNumber | null`, `boxplotOption(data, opts)`.
  - `builders/calendar.ts`: `interface CalendarOpts {date; value; year; min?; max?; orient?: 'horizontal' |
    'vertical'}`, `calendarOption(data, opts)`.
  - `builders/race.ts`: `interface RaceOpts {top?; valueName?; durationMs?}`, `colorFor(id): string`,
    `raceOption(frame: LeaderboardFrame, opts?)`.
  - `builders/bump.ts`: `interface BumpOpts {top?}`, `bumpOption(frames: readonly LeaderboardFrame[], opts?)`.
  - `builders/ridgeline.ts`: `interface RidgelineOpts {group; value; min?; max?; step?; bandwidth?; overlap?}`,
    `silverman(values): number`, `kde(values, grid, bandwidth): number[]`, `ridgelineOption(data, opts)`.

**Branch:** `task/07-5-charts` · **Depends on:** Plan 07 T1.

- [ ] **Step 1: Create the shared chart data types**

Create the full contents of `frontend/src/components/charts/types.ts` (types only; every test below exercises them):

```ts
/** Column/row data every chart, table and CSV export consumes (C10). Never schema types. */
export type ColumnType = 'date' | 'number' | 'string' | 'int';

export interface TabularColumn {
  key: string;
  label: string;
  type: ColumnType;
}

export type Cell = string | number | null;

export type TabularRow = Record<string, Cell>;

export interface TabularData {
  columns: TabularColumn[];
  rows: TabularRow[];
}

/** Chart types a ChartCard can switch between. */
export type ChartType = 'bar' | 'line' | 'heatmap';

/** One time-machine frame (race + bump builders); pages map API frames onto this. */
export interface LeaderboardFrame {
  date: string;
  rows: { id: number | string; name: string; value: number; rank: number }[];
}
```

- [ ] **Step 2: Write the failing test for the shared builder helpers**

Create the full contents of `frontend/src/components/charts/builders/common.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import {
  axisTypeFor,
  cellLabel,
  distinct,
  escapeHtml,
  legendFor,
  numeric,
  requireColumn,
} from './common';

const DATA: TabularData = { columns: [{ key: 'year', label: 'Year', type: 'int' }], rows: [] };

describe('builder helpers', () => {
  it('escapes HTML in data-derived strings', () => {
    expect(escapeHtml('<img src=x onerror=alert(1)>')).toBe('&lt;img src=x onerror=alert(1)&gt;');
  });

  it('throws a clear error for an unknown column', () => {
    expect(requireColumn(DATA, 'year').label).toBe('Year');
    expect(() => requireColumn(DATA, 'nope')).toThrow('Unknown column "nope"');
  });

  it('maps column types to axis types', () => {
    expect(axisTypeFor({ key: 'd', label: 'D', type: 'date' })).toBe('time');
    expect(axisTypeFor({ key: 's', label: 'S', type: 'string' })).toBe('category');
    expect(axisTypeFor({ key: 'n', label: 'N', type: 'number' })).toBe('value');
    expect(axisTypeFor({ key: 'i', label: 'I', type: 'int' })).toBe('value');
  });

  it('keeps only finite numbers and labels missing cells with a dash', () => {
    expect([
      numeric(3),
      numeric('3'),
      numeric(null),
      numeric(Number.NaN),
      numeric(undefined),
    ]).toEqual([3, null, null, null, null]);
    expect([cellLabel(null), cellLabel(undefined), cellLabel(2026), cellLabel('A')]).toEqual([
      '—',
      '—',
      '2026',
      'A',
    ]);
  });

  it('dedupes in first-appearance order and shows a legend only for several series', () => {
    expect(distinct(['b', 'a', 'b'])).toEqual(['b', 'a']);
    expect(legendFor(1)).toEqual({ show: false });
    expect(legendFor(2)).toEqual({ type: 'scroll', top: 0 });
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/common.test.ts`
Expected: FAIL — `Failed to resolve import "./common"`.

- [ ] **Step 4: Implement the shared helpers**

Create the full contents of `frontend/src/components/charts/builders/common.ts`:

```ts
import { format } from 'echarts/core';
import type { Cell, TabularColumn, TabularData } from '../types';

/** Every data-derived string in a string tooltip formatter goes through this (C10). */
export function escapeHtml(value: unknown): string {
  return format.encodeHTML(String(value));
}

export function requireColumn(data: TabularData, key: string): TabularColumn {
  const column = data.columns.find((c) => c.key === key);
  if (!column) throw new Error(`Unknown column "${key}"`);
  return column;
}

export function numeric(cell: Cell | undefined): number | null {
  return typeof cell === 'number' && Number.isFinite(cell) ? cell : null;
}

export function axisTypeFor(column: TabularColumn): 'time' | 'category' | 'value' {
  if (column.type === 'date') return 'time';
  return column.type === 'string' ? 'category' : 'value';
}

/** Distinct values in first-appearance order. */
export function distinct<T>(values: readonly T[]): T[] {
  return [...new Set(values)];
}

export function cellLabel(cell: Cell | undefined): string {
  return cell === null || cell === undefined ? '—' : String(cell);
}

/** Shared grid margins, frozen so no chart changes them for all: copy (`{ ...GRID }`) to adjust. */
export const GRID = Object.freeze({ left: 8, right: 24, top: 40, bottom: 8, containLabel: true });

export function legendFor(seriesCount: number) {
  return seriesCount > 1 ? { type: 'scroll' as const, top: 0 } : { show: false };
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/common.test.ts`
Expected: PASS — 5 tests.

- [ ] **Step 6: Write the failing test for the line builder (time axis, long format, band, markers)**

Create the full contents of `frontend/src/components/charts/builders/line.test.ts`:

```ts
import type { LineSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { lineOption } from './line';

const RATING: TabularData = {
  columns: [
    { key: 'event_date', label: 'Event', type: 'date' },
    { key: 'mu', label: 'Rating', type: 'number' },
    { key: 'lo', label: 'Low', type: 'number' },
    { key: 'hi', label: 'High', type: 'number' },
    { key: 'pb', label: 'PB', type: 'int' },
  ],
  rows: [
    { event_date: '2026-09-06', mu: 35, lo: 31, hi: 39, pb: 0 },
    { event_date: '2026-09-13', mu: 36.5, lo: 33, hi: 40, pb: 1 },
    { event_date: '2026-09-20', mu: null, lo: null, hi: 41, pb: 0 },
  ],
};

const series = (o: ReturnType<typeof lineOption>) => o.series as LineSeriesOption[];

describe('lineOption', () => {
  it('draws one series per y column on a time axis for dates, with gaps for nulls', () => {
    const o = lineOption(RATING, { x: 'event_date', y: ['mu'] });
    expect(o.xAxis).toMatchObject({ type: 'time', name: 'Event' });
    expect(o.yAxis).toMatchObject({ name: 'Rating', scale: false });
    expect(series(o)).toHaveLength(1);
    expect(series(o)[0]).toMatchObject({
      type: 'line',
      name: 'Rating',
      data: [
        ['2026-09-06', 35],
        ['2026-09-13', 36.5],
        ['2026-09-20', null],
      ],
    });
    expect(o.legend).toMatchObject({ show: false });
  });

  it('adds a stacked band (lower + width) hidden from the tooltip, and PB markers', () => {
    const o = lineOption(RATING, {
      x: 'event_date',
      y: ['mu'],
      band: { lower: 'lo', upper: 'hi', name: '95% band' },
      markers: { flag: 'pb', name: 'Personal best' },
      scaleY: true,
      yName: 'Rating (μ)',
    });
    const [low, width, line, markers] = series(o) as [
      LineSeriesOption,
      LineSeriesOption,
      LineSeriesOption,
      LineSeriesOption,
    ];
    expect(low).toMatchObject({
      stack: 'band',
      tooltip: { show: false },
      data: [
        ['2026-09-06', 31],
        ['2026-09-13', 33],
        ['2026-09-20', null],
      ],
    });
    expect(width).toMatchObject({
      name: '95% band',
      stack: 'band',
      data: [
        ['2026-09-06', 8],
        ['2026-09-13', 7],
        ['2026-09-20', null],
      ],
    });
    expect(line.name).toBe('Rating');
    expect(markers).toMatchObject({
      type: 'scatter',
      name: 'Personal best',
      data: [['2026-09-13', 36.5]],
    });
    expect(o.legend).toMatchObject({ data: ['95% band', 'Rating', 'Personal best'] });
    expect(o.yAxis).toMatchObject({ name: 'Rating (μ)', scale: true });
  });

  it('splits long-format rows into one series per group, with optional area and smoothing', () => {
    const data: TabularData = {
      columns: [
        { key: 'month', label: 'Month', type: 'string' },
        { key: 'who', label: 'Who', type: 'string' },
        { key: 'value', label: 'Avg score', type: 'number' },
      ],
      rows: [
        { month: '2026-08', who: 'You', value: 38 },
        { month: '2026-08', who: 'Club', value: 35 },
        { month: '2026-09', who: 'You', value: 40 },
      ],
    };
    const o = lineOption(data, {
      x: 'month',
      y: ['value'],
      seriesBy: 'who',
      area: true,
      smooth: true,
    });
    expect(o.xAxis).toMatchObject({ type: 'category' });
    expect(series(o).map((s) => [s.name, s.data])).toEqual([
      [
        'You',
        [
          ['2026-08', 38],
          ['2026-09', 40],
        ],
      ],
      ['Club', [['2026-08', 35]]],
    ]);
    expect(series(o)[0]).toMatchObject({ smooth: true, areaStyle: { opacity: 0.2 } });
  });

  it('rejects an unknown column or an empty y list', () => {
    expect(() => lineOption(RATING, { x: 'nope', y: ['mu'] })).toThrow('Unknown column "nope"');
    expect(() => lineOption(RATING, { x: 'event_date', y: [] })).toThrow('at least one y column');
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/line.test.ts`
Expected: FAIL — `Failed to resolve import "./line"`.

- [ ] **Step 8: Implement `lineOption`**

Create the full contents of `frontend/src/components/charts/builders/line.ts`:

```ts
import type { EChartsOption, LineSeriesOption, ScatterSeriesOption } from 'echarts';
import { chartPalette } from '../../../theme/tokens';
import type { TabularData } from '../types';
import {
  GRID,
  axisTypeFor,
  cellLabel,
  distinct,
  legendFor,
  numeric,
  requireColumn,
} from './common';

export interface LineOpts {
  /** x column (date → time axis, string → category, number → value). */
  x: string;
  /** One series per y column, named by the column label. */
  y: string[];
  /** Long format: one series per distinct value of this column (uses y[0]). */
  seriesBy?: string;
  /** Shaded band between two columns, e.g. a rating ±1.96σ. */
  band?: { lower: string; upper: string; name?: string };
  /** Point markers at rows where `flag` is truthy (e.g. personal bests), placed on y[0]. */
  markers?: { flag: string; name: string };
  area?: boolean;
  smooth?: boolean;
  yName?: string;
  /** Fit the y axis to the data instead of starting at 0. */
  scaleY?: boolean;
}

export function lineOption(data: TabularData, opts: LineOpts): EChartsOption {
  const xCol = requireColumn(data, opts.x);
  const yCols = opts.y.map((key) => requireColumn(data, key));
  const firstY = yCols[0];
  if (!firstY) throw new Error('lineOption needs at least one y column');
  const point = (
    row: TabularData['rows'][number],
    key: string,
  ): [string | number, number | null] => [row[opts.x] ?? '', numeric(row[key])];
  const base = {
    type: 'line' as const,
    smooth: opts.smooth ?? false,
    showSymbol: data.rows.length <= 60,
  };
  const areaStyle = opts.area ? { opacity: 0.2 } : undefined;

  let series: (LineSeriesOption | ScatterSeriesOption)[];
  if (opts.seriesBy !== undefined) {
    const by = requireColumn(data, opts.seriesBy).key;
    series = distinct(data.rows.map((r) => r[by] ?? null)).map((group) => ({
      ...base,
      name: cellLabel(group),
      ...(areaStyle ? { areaStyle } : {}),
      data: data.rows.filter((r) => (r[by] ?? null) === group).map((r) => point(r, firstY.key)),
    }));
  } else {
    series = yCols.map((col) => ({
      ...base,
      name: col.label,
      ...(areaStyle ? { areaStyle } : {}),
      data: data.rows.map((r) => point(r, col.key)),
    }));
  }

  if (opts.band) {
    const lower = requireColumn(data, opts.band.lower).key;
    const upper = requireColumn(data, opts.band.upper).key;
    const bandName = opts.band.name ?? 'Range';
    series.unshift(
      {
        type: 'line',
        name: `${bandName} (low)`,
        stack: 'band',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        data: data.rows.map((r) => point(r, lower)),
      },
      {
        type: 'line',
        name: bandName,
        stack: 'band',
        symbol: 'none',
        lineStyle: { opacity: 0 },
        areaStyle: { color: chartPalette[0], opacity: 0.15 },
        tooltip: { show: false },
        data: data.rows.map((r) => {
          const lo = numeric(r[lower]);
          const hi = numeric(r[upper]);
          return [r[opts.x] ?? '', lo === null || hi === null ? null : hi - lo];
        }),
      },
    );
  }

  if (opts.markers) {
    const flag = requireColumn(data, opts.markers.flag).key;
    series.push({
      type: 'scatter',
      name: opts.markers.name,
      symbolSize: 10,
      itemStyle: { color: chartPalette[3] },
      data: data.rows.filter((r) => Boolean(r[flag])).map((r) => point(r, firstY.key)),
    });
  }

  const named = series.filter((s) => !String(s.name).endsWith('(low)'));
  return {
    grid: GRID,
    tooltip: { trigger: 'axis' },
    legend: { ...legendFor(named.length), data: named.map((s) => String(s.name)) },
    xAxis: { type: axisTypeFor(xCol), name: xCol.label, nameLocation: 'middle', nameGap: 28 },
    yAxis: { type: 'value', name: opts.yName ?? firstY.label, scale: opts.scaleY ?? false },
    series,
  };
}
```

- [ ] **Step 9: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/line.test.ts`
Expected: PASS — 4 tests.

- [ ] **Step 10: Write the failing test for the bar builder**

Create the full contents of `frontend/src/components/charts/builders/bar.test.ts`:

```ts
import type { BarSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { barOption } from './bar';

const BY_YEAR: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'status', label: 'Status', type: 'string' },
    { key: 'value', label: 'Rounds', type: 'int' },
  ],
  rows: [
    { year: 2025, status: 'member', value: 1200 },
    { year: 2025, status: 'guest', value: 67 },
    { year: 2026, status: 'member', value: 950 },
  ],
};

describe('barOption', () => {
  it('uses the x column as categories and one series per y column', () => {
    const o = barOption(
      {
        columns: BY_YEAR.columns,
        rows: [
          { year: 2025, value: 1267 },
          { year: 2026, value: 969 },
        ],
      },
      { x: 'year', y: ['value'], labels: true },
    );
    expect(o.xAxis).toMatchObject({ type: 'category', data: ['2025', '2026'], inverse: false });
    expect(o.yAxis).toMatchObject({ type: 'value', name: 'Rounds' });
    expect(o.series).toEqual([
      expect.objectContaining({
        type: 'bar',
        name: 'Rounds',
        data: [1267, 969],
        label: { show: true, position: 'top' },
      }),
    ]);
  });

  it('pivots long rows into aligned, stacked series with null for missing categories', () => {
    const o = barOption(BY_YEAR, { x: 'year', y: ['value'], seriesBy: 'status', stack: true });
    const series = o.series as BarSeriesOption[];
    expect(series.map((s) => [s.name, s.data, s.stack])).toEqual([
      ['member', [1200, 950], 'total'],
      ['guest', [67, null], 'total'],
    ]);
    expect(o.legend).toMatchObject({ type: 'scroll' });
  });

  it('puts categories on the y axis, first row on top, when horizontal', () => {
    const o = barOption(BY_YEAR, { x: 'status', y: ['value'], horizontal: true, yName: 'n' });
    expect(o.yAxis).toMatchObject({ type: 'category', inverse: true, data: ['member', 'guest'] });
    expect(o.xAxis).toMatchObject({ type: 'value', name: 'n' });
    expect((o.series as BarSeriesOption[])[0]?.label).toMatchObject({ position: 'right' });
  });

  it('needs at least one y column', () => {
    expect(() => barOption(BY_YEAR, { x: 'year', y: [] })).toThrow('at least one y column');
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/bar.test.ts`
Expected: FAIL — `Failed to resolve import "./bar"`.

- [ ] **Step 12: Implement `barOption`**

Create the full contents of `frontend/src/components/charts/builders/bar.ts`:

```ts
import type { BarSeriesOption, EChartsOption } from 'echarts';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, legendFor, numeric, requireColumn } from './common';

export interface BarOpts {
  /** Category column. */
  x: string;
  /** One series per y column. */
  y: string[];
  /** Long format: one series per distinct value of this column (uses y[0]). */
  seriesBy?: string;
  /** Categories on the y axis, first row at the top (long names, e.g. shooters). */
  horizontal?: boolean;
  stack?: boolean;
  yName?: string;
  /** Print values on the bars. */
  labels?: boolean;
}

export function barOption(data: TabularData, opts: BarOpts): EChartsOption {
  const xKey = requireColumn(data, opts.x).key;
  const yCols = opts.y.map((key) => requireColumn(data, key));
  const firstY = yCols[0];
  if (!firstY) throw new Error('barOption needs at least one y column');
  const categories = distinct(data.rows.map((r) => cellLabel(r[xKey])));
  const common = {
    type: 'bar' as const,
    ...(opts.stack ? { stack: 'total' } : {}),
    label: {
      show: opts.labels ?? false,
      position: opts.horizontal ? ('right' as const) : ('top' as const),
    },
  };

  let series: BarSeriesOption[];
  if (opts.seriesBy !== undefined) {
    const by = requireColumn(data, opts.seriesBy).key;
    series = distinct(data.rows.map((r) => cellLabel(r[by]))).map((group) => {
      const byCategory = new Map(
        data.rows
          .filter((r) => cellLabel(r[by]) === group)
          .map((r) => [cellLabel(r[xKey]), numeric(r[firstY.key])]),
      );
      return { ...common, name: group, data: categories.map((c) => byCategory.get(c) ?? null) };
    });
  } else {
    series = yCols.map((col) => ({
      ...common,
      name: col.label,
      data: data.rows.map((r) => numeric(r[col.key])),
    }));
  }

  const categoryAxis = {
    type: 'category' as const,
    data: categories,
    inverse: opts.horizontal ?? false,
  };
  const valueAxis = { type: 'value' as const, name: opts.yName ?? firstY.label };
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: legendFor(series.length),
    xAxis: opts.horizontal ? valueAxis : categoryAxis,
    yAxis: opts.horizontal ? categoryAxis : valueAxis,
    series,
  };
}
```

- [ ] **Step 13: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/bar.test.ts`
Expected: PASS — 4 tests.

- [ ] **Step 14: Write the failing test for the scatter builder and least-squares fit**

Create the full contents of `frontend/src/components/charts/builders/scatter.test.ts`:

```ts
import type { LineSeriesOption, ScatterSeriesOption, TooltipComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { linearFit, scatterOption } from './scatter';

const DATA: TabularData = {
  columns: [
    { key: 'gust', label: 'Gust (mph)', type: 'number' },
    { key: 'difficulty', label: 'Difficulty', type: 'number' },
    { key: 'event', label: 'Event', type: 'date' },
    { key: 'kind', label: 'Kind', type: 'string' },
  ],
  rows: [
    { gust: 0, difficulty: 1, event: '2026-01-04', kind: 'a' },
    { gust: 10, difficulty: 4, event: '<img src=x onerror=alert(1)>', kind: 'b' },
    { gust: 20, difficulty: 7, event: '2026-01-18', kind: 'a' },
    { gust: null, difficulty: 9, event: '2026-01-25', kind: 'a' },
  ],
};

function tooltipText(o: ReturnType<typeof scatterOption>, params: unknown): string {
  const formatter = (o.tooltip as TooltipComponentOption).formatter as (p: unknown) => string;
  return formatter(params);
}

describe('linearFit', () => {
  it('recovers slope and intercept of exact points', () => {
    expect(
      linearFit([
        [0, 1],
        [10, 4],
        [20, 7],
      ]),
    ).toEqual({ slope: 0.3, intercept: 1 });
  });

  it('returns null with fewer than two points or no spread in x', () => {
    expect(linearFit([[1, 1]])).toBeNull();
    expect(
      linearFit([
        [2, 1],
        [2, 5],
      ]),
    ).toBeNull();
  });
});

describe('scatterOption', () => {
  it('plots finite x/y pairs named by the label column and adds a dashed fit line', () => {
    const o = scatterOption(DATA, { x: 'gust', y: 'difficulty', label: 'event', fit: true });
    const [points, fit] = o.series as [ScatterSeriesOption, LineSeriesOption];
    expect(points.data).toEqual([
      { value: [0, 1], name: '2026-01-04' },
      { value: [10, 4], name: '<img src=x onerror=alert(1)>' },
      { value: [20, 7], name: '2026-01-18' },
    ]);
    expect(fit).toMatchObject({
      name: 'Fit',
      data: [
        [0, 1],
        [20, 7],
      ],
    });
  });

  it('escapes names in the tooltip so a shooter name cannot inject HTML', () => {
    const o = scatterOption(DATA, { x: 'gust', y: 'difficulty', label: 'event' });
    const html = tooltipText(o, { name: '<img src=x onerror=alert(1)>', value: [10, 4] });
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html).toContain('Gust (mph): 10');
  });

  it('omits the title line for unnamed points and splits series by a column', () => {
    const o = scatterOption(DATA, {
      x: 'gust',
      y: 'difficulty',
      seriesBy: 'kind',
      xName: 'Gust',
      yName: 'Diff',
    });
    expect((o.series as ScatterSeriesOption[]).map((s) => s.name)).toEqual(['a', 'b']);
    expect(tooltipText(o, { name: '', value: [1, 2] })).toBe('Gust: 1<br/>Diff: 2');
    expect(tooltipText(o, {})).toBe('Gust: NaN<br/>Diff: NaN');
  });

  it('skips the fit line when no fit is possible', () => {
    const one: TabularData = {
      columns: DATA.columns,
      rows: [{ gust: 1, difficulty: 2, event: 'x', kind: 'a' }],
    };
    expect(scatterOption(one, { x: 'gust', y: 'difficulty', fit: true }).series).toHaveLength(1);
  });
});
```

- [ ] **Step 15: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/scatter.test.ts`
Expected: FAIL — `Failed to resolve import "./scatter"`.

- [ ] **Step 16: Implement `linearFit` and `scatterOption`**

Create the full contents of `frontend/src/components/charts/builders/scatter.ts`:

```ts
import type { EChartsOption, LineSeriesOption, ScatterSeriesOption } from 'echarts';
import { chartPalette } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, escapeHtml, legendFor, numeric, requireColumn } from './common';

export interface ScatterOpts {
  x: string;
  y: string;
  /** Column naming each point in the tooltip (e.g. shooter or event). */
  label?: string;
  seriesBy?: string;
  /** Adds a least-squares line through all points. */
  fit?: boolean;
  xName?: string;
  yName?: string;
}

export interface LinearFit {
  slope: number;
  intercept: number;
}

/** Ordinary least squares y = intercept + slope·x; null with <2 points or no spread in x. */
export function linearFit(points: readonly (readonly [number, number])[]): LinearFit | null {
  const n = points.length;
  if (n < 2) return null;
  const mx = points.reduce((s, [x]) => s + x, 0) / n;
  const my = points.reduce((s, [, y]) => s + y, 0) / n;
  const sxx = points.reduce((s, [x]) => s + (x - mx) ** 2, 0);
  if (sxx === 0) return null;
  const sxy = points.reduce((s, [x, y]) => s + (x - mx) * (y - my), 0);
  const slope = sxy / sxx;
  return { slope, intercept: my - slope * mx };
}

interface PointDatum {
  value: [number, number];
  name: string;
}

export function scatterOption(data: TabularData, opts: ScatterOpts): EChartsOption {
  const xCol = requireColumn(data, opts.x);
  const yCol = requireColumn(data, opts.y);
  const labelKey = opts.label === undefined ? null : requireColumn(data, opts.label).key;
  const byKey = opts.seriesBy === undefined ? null : requireColumn(data, opts.seriesBy).key;

  const points = data.rows.flatMap((row) => {
    const x = numeric(row[xCol.key]);
    const y = numeric(row[yCol.key]);
    if (x === null || y === null) return [];
    const datum: PointDatum = {
      value: [x, y],
      name: labelKey === null ? '' : cellLabel(row[labelKey]),
    };
    return [{ datum, group: byKey === null ? yCol.label : cellLabel(row[byKey]) }];
  });
  const groups = distinct(points.map((p) => p.group));
  const series: (ScatterSeriesOption | LineSeriesOption)[] = groups.map((group) => ({
    type: 'scatter',
    name: group,
    symbolSize: 8,
    data: points.filter((p) => p.group === group).map((p) => p.datum),
  }));

  const fit = opts.fit ? linearFit(points.map((p) => p.datum.value)) : null;
  if (fit) {
    const xs = points.map((p) => p.datum.value[0]);
    const lo = Math.min(...xs);
    const hi = Math.max(...xs);
    series.push({
      type: 'line',
      name: 'Fit',
      symbol: 'none',
      lineStyle: { color: chartPalette[2], type: 'dashed' },
      tooltip: { show: false },
      data: [
        [lo, fit.intercept + fit.slope * lo],
        [hi, fit.intercept + fit.slope * hi],
      ],
    });
  }

  const xName = opts.xName ?? xCol.label;
  const yName = opts.yName ?? yCol.label;
  return {
    grid: GRID,
    legend: legendFor(series.length),
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { name?: string; value?: [number, number]; seriesName?: string };
        const [x, y] = p.value ?? [NaN, NaN];
        const title = p.name ? `<strong>${escapeHtml(p.name)}</strong><br/>` : '';
        return `${title}${escapeHtml(xName)}: ${escapeHtml(x)}<br/>${escapeHtml(yName)}: ${escapeHtml(y)}`;
      },
    },
    xAxis: { type: 'value', name: xName, nameLocation: 'middle', nameGap: 28, scale: true },
    yAxis: { type: 'value', name: yName, scale: true },
    series,
  };
}
```

- [ ] **Step 17: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/scatter.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 18: Write the failing test for the heatmap builder**

Create the full contents of `frontend/src/components/charts/builders/heatmap.test.ts`:

```ts
import type { HeatmapSeriesOption, TooltipComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { heatmapOption } from './heatmap';

const HITS: TabularData = {
  columns: [
    { key: 'station', label: 'Station', type: 'int' },
    { key: 'shooter', label: 'Shooter', type: 'string' },
    { key: 'hits', label: 'Hits', type: 'int' },
  ],
  rows: [
    { station: 4, shooter: 'Hadley, Ike', hits: 6 },
    { station: 5, shooter: 'Hadley, Ike', hits: 7 },
    { station: 4, shooter: '<img src=x onerror=alert(1)>', hits: 3 },
    { station: 5, shooter: '<img src=x onerror=alert(1)>', hits: null },
  ],
};

describe('heatmapOption', () => {
  it('indexes cells by category and skips empty cells', () => {
    const o = heatmapOption(HITS, { x: 'station', y: 'shooter', value: 'hits', labels: true });
    expect(o.xAxis).toMatchObject({ data: ['4', '5'] });
    expect(o.yAxis).toMatchObject({
      data: ['Hadley, Ike', '<img src=x onerror=alert(1)>'],
      inverse: true,
    });
    const [series] = o.series as [HeatmapSeriesOption];
    expect(series.data).toEqual([
      [0, 0, 6],
      [1, 0, 7],
      [0, 1, 3],
    ]);
    expect(series.label).toEqual({ show: true });
    expect(o.visualMap).toMatchObject({ min: 3, max: 7 });
  });

  it('honours explicit bounds and handles no data', () => {
    const o = heatmapOption(
      { columns: HITS.columns, rows: [] },
      { x: 'station', y: 'shooter', value: 'hits' },
    );
    expect(o.visualMap).toMatchObject({ min: 0, max: 1 });
    const bounded = heatmapOption(HITS, {
      x: 'station',
      y: 'shooter',
      value: 'hits',
      min: 0,
      max: 8,
    });
    expect(bounded.visualMap).toMatchObject({ min: 0, max: 8 });
  });

  it('escapes shooter names in the tooltip', () => {
    const o = heatmapOption(HITS, { x: 'station', y: 'shooter', value: 'hits' });
    const formatter = (o.tooltip as TooltipComponentOption).formatter as (p: unknown) => string;
    const html = formatter({ value: [0, 1, 3] });
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html).toBe('&lt;img src=x onerror=alert(1)&gt; · Station 4<br/>Hits: 3');
    expect(formatter({ value: [9, 9, 1] })).toBe(' · Station <br/>Hits: 1');
  });
});
```

- [ ] **Step 19: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/heatmap.test.ts`
Expected: FAIL — `Failed to resolve import "./heatmap"`.

- [ ] **Step 20: Implement `heatmapOption`**

Create the full contents of `frontend/src/components/charts/builders/heatmap.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { colors } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, escapeHtml, numeric, requireColumn } from './common';

export interface HeatmapOpts {
  /** Column categories (e.g. station). */
  x: string;
  /** Row categories (e.g. shooter). */
  y: string;
  value: string;
  min?: number;
  max?: number;
  /** Print values in the cells. */
  labels?: boolean;
}

export function heatmapOption(data: TabularData, opts: HeatmapOpts): EChartsOption {
  const xCol = requireColumn(data, opts.x);
  const yCol = requireColumn(data, opts.y);
  const valueCol = requireColumn(data, opts.value);
  const xs = distinct(data.rows.map((r) => cellLabel(r[xCol.key])));
  const ys = distinct(data.rows.map((r) => cellLabel(r[yCol.key])));
  const cells = data.rows.flatMap((r) => {
    const v = numeric(r[valueCol.key]);
    return v === null
      ? []
      : [[xs.indexOf(cellLabel(r[xCol.key])), ys.indexOf(cellLabel(r[yCol.key])), v]];
  });
  const values = cells.map((c) => c[2] ?? 0);
  return {
    grid: { ...GRID, bottom: 48 },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const [xi, yi, v] = (params as { value: [number, number, number] }).value;
        return `${escapeHtml(ys[yi] ?? '')} · ${escapeHtml(xCol.label)} ${escapeHtml(xs[xi] ?? '')}<br/>${escapeHtml(valueCol.label)}: ${escapeHtml(v)}`;
      },
    },
    xAxis: { type: 'category', data: xs, name: xCol.label, splitArea: { show: true } },
    yAxis: {
      type: 'category',
      data: ys,
      name: yCol.label,
      inverse: true,
      splitArea: { show: true },
    },
    visualMap: {
      type: 'continuous',
      min: opts.min ?? (values.length ? Math.min(...values) : 0),
      max: opts.max ?? (values.length ? Math.max(...values) : 1),
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      calculable: false,
    },
    series: [
      {
        type: 'heatmap',
        name: valueCol.label,
        data: cells,
        label: { show: opts.labels ?? false },
        emphasis: { itemStyle: { borderColor: colors.text, borderWidth: 1 } },
      },
    ],
  };
}
```

- [ ] **Step 21: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/heatmap.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 22: Write the failing test for the histogram builder**

Create the full contents of `frontend/src/components/charts/builders/histogram.test.ts`:

```ts
import type { BarSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { binValues, histogramOption } from './histogram';

const SCORES: TabularData = {
  columns: [
    { key: 'score', label: 'Score', type: 'int' },
    { key: 'who', label: 'Who', type: 'string' },
  ],
  rows: [
    { score: 30, who: 'You' },
    { score: 34, who: 'You' },
    { score: 35, who: 'Club' },
    { score: 36, who: 'Club' },
    { score: 50, who: 'Club' },
    { score: null, who: 'Club' },
  ],
};

describe('binValues', () => {
  it('counts half-open bins and drops values outside the range', () => {
    // bins [0,5) [5,10) [10,15); -1 and 15 fall outside
    expect(binValues([0, 4, 5, 9, 10, 14, 15, -1], 5, 0, 10)).toEqual([2, 2, 2]);
  });
});

describe('histogramOption', () => {
  it('bins by width with range labels and one series per group', () => {
    const o = histogramOption(SCORES, { value: 'score', binWidth: 5, seriesBy: 'who' });
    expect(o.xAxis).toMatchObject({ data: ['30–35', '35–40', '40–45', '45–50', '50–55'] });
    expect((o.series as BarSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['You', [2, 0, 0, 0, 0]],
      ['Club', [0, 2, 0, 0, 1]],
    ]);
    expect(o.yAxis).toMatchObject({ name: 'Count' });
  });

  it('normalizes each series to percent of its own total', () => {
    const o = histogramOption(SCORES, {
      value: 'score',
      binWidth: 5,
      min: 30,
      max: 50,
      seriesBy: 'who',
      normalize: true,
    });
    expect((o.series as BarSeriesOption[])[1]?.data).toEqual([0, (100 * 2) / 3, 0, 0, 100 / 3]);
    expect(o.yAxis).toMatchObject({ name: '% of rounds' });
  });

  it('labels single-width bins by value and tolerates empty data', () => {
    const o = histogramOption(SCORES, { value: 'score', binWidth: 1, min: 48, max: 50 });
    expect(o.xAxis).toMatchObject({ data: ['48', '49', '50'] });
    expect((o.series as BarSeriesOption[])[0]).toMatchObject({ name: 'Score', data: [0, 0, 1] });
    const empty = histogramOption(
      { columns: SCORES.columns, rows: [] },
      { value: 'score', binWidth: 1, normalize: true },
    );
    expect(empty.xAxis).toMatchObject({ data: ['0'] });
    expect(empty.series).toEqual([]);
  });

  it('rejects a non-positive bin width', () => {
    expect(() => histogramOption(SCORES, { value: 'score', binWidth: 0 })).toThrow(
      'binWidth must be positive',
    );
  });
});
```

- [ ] **Step 23: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/histogram.test.ts`
Expected: FAIL — `Failed to resolve import "./histogram"`.

- [ ] **Step 24: Implement `binValues` and `histogramOption`**

Create the full contents of `frontend/src/components/charts/builders/histogram.ts`:

```ts
import type { BarSeriesOption, EChartsOption } from 'echarts';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, legendFor, numeric, requireColumn } from './common';

export interface HistogramOpts {
  value: string;
  /** Bins are half-open [lo, lo + binWidth). */
  binWidth: number;
  /** First bin start; default = data min rounded down to a multiple of binWidth. */
  min?: number;
  /** Last value that must fall in a bin; default = data max. */
  max?: number;
  /** One histogram per distinct value (e.g. "You" vs "Club"). */
  seriesBy?: string;
  /** Show each series as % of its own total so different-sized groups compare. */
  normalize?: boolean;
  xName?: string;
}

/** Counts per bin [min + i·w, min + (i+1)·w) for i = 0..floor((max-min)/w); outside values are dropped. */
export function binValues(
  values: readonly number[],
  binWidth: number,
  min: number,
  max: number,
): number[] {
  const n = Math.floor((max - min) / binWidth) + 1;
  const counts = new Array<number>(n).fill(0);
  for (const v of values) {
    const i = Math.floor((v - min) / binWidth);
    if (i >= 0 && i < n) counts[i] = (counts[i] ?? 0) + 1;
  }
  return counts;
}

export function histogramOption(data: TabularData, opts: HistogramOpts): EChartsOption {
  if (!(opts.binWidth > 0)) throw new Error('binWidth must be positive');
  const valueCol = requireColumn(data, opts.value);
  const byKey = opts.seriesBy === undefined ? null : requireColumn(data, opts.seriesBy).key;
  const all = data.rows.flatMap((r) => {
    const v = numeric(r[valueCol.key]);
    return v === null ? [] : [{ v, group: byKey === null ? valueCol.label : cellLabel(r[byKey]) }];
  });
  const values = all.map((a) => a.v);
  const min =
    opts.min ??
    (values.length ? Math.floor(Math.min(...values) / opts.binWidth) * opts.binWidth : 0);
  const max = opts.max ?? (values.length ? Math.max(...values) : min);
  const labels = binValues([], opts.binWidth, min, max).map((_, i) => {
    const lo = min + i * opts.binWidth;
    return opts.binWidth === 1 ? String(lo) : `${lo}–${lo + opts.binWidth}`;
  });
  const series: BarSeriesOption[] = distinct(all.map((a) => a.group)).map((group) => {
    const counts = binValues(
      all.filter((a) => a.group === group).map((a) => a.v),
      opts.binWidth,
      min,
      max,
    );
    const total = counts.reduce((s, c) => s + c, 0);
    return {
      type: 'bar',
      name: group,
      barGap: '0%',
      data: opts.normalize ? counts.map((c) => (total ? (100 * c) / total : 0)) : counts,
    };
  });
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: legendFor(series.length),
    xAxis: {
      type: 'category',
      data: labels,
      name: opts.xName ?? valueCol.label,
      nameLocation: 'middle',
      nameGap: 28,
    },
    yAxis: { type: 'value', name: opts.normalize ? '% of rounds' : 'Count' },
    series,
  };
}
```

- [ ] **Step 25: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/histogram.test.ts`
Expected: PASS — 5 tests.

- [ ] **Step 26: Write the failing test for the box-plot builder**

Create the full contents of `frontend/src/components/charts/builders/boxplot.test.ts`:

```ts
import type { BoxplotSeriesOption, ScatterSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { boxplotOption, fiveNumber, quantile } from './boxplot';

describe('quantile / fiveNumber', () => {
  it('interpolates linearly between order statistics', () => {
    expect(quantile([1, 2, 3, 4], 0.25)).toBe(1.75);
    expect(quantile([10], 0.9)).toBe(10);
  });

  it('computes Tukey whiskers and outliers', () => {
    // q1 = 30.75, q3 = 36.5, IQR 5.75 → fences 22.125 and 45.125
    expect(fiveNumber([10, 30, 31, 33, 35, 36, 38, 50])).toEqual({
      min: 30,
      q1: 30.75,
      median: 34,
      q3: 36.5,
      max: 38,
      outliers: [10, 50],
    });
    expect(fiveNumber([])).toBeNull();
  });
});

describe('boxplotOption', () => {
  it('draws one box per group and outliers at their group index', () => {
    const data: TabularData = {
      columns: [
        { key: 'year', label: 'Year', type: 'int' },
        { key: 'score', label: 'Score', type: 'int' },
      ],
      rows: [
        ...[10, 30, 31, 33, 35, 36, 38, 50].map((score) => ({ year: 2025, score })),
        { year: 2026, score: 40 },
        { year: 2027, score: null },
      ],
    };
    const o = boxplotOption(data, { group: 'year', value: 'score' });
    expect(o.xAxis).toMatchObject({ data: ['2025', '2026', '2027'] });
    const [boxes, outliers] = o.series as [BoxplotSeriesOption, ScatterSeriesOption];
    expect(boxes.data).toEqual([[30, 30.75, 34, 36.5, 38], [40, 40, 40, 40, 40], []]);
    expect(outliers.data).toEqual([
      [0, 10],
      [0, 50],
    ]);
  });
});
```

- [ ] **Step 27: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/boxplot.test.ts`
Expected: FAIL — `Failed to resolve import "./boxplot"`.

- [ ] **Step 28: Implement `quantile`, `fiveNumber` and `boxplotOption`**

Create the full contents of `frontend/src/components/charts/builders/boxplot.ts`:

```ts
import type { BoxplotSeriesOption, EChartsOption, ScatterSeriesOption } from 'echarts';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, numeric, requireColumn } from './common';

export interface BoxplotOpts {
  group: string;
  value: string;
  yName?: string;
}

export interface FiveNumber {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers: number[];
}

/** Linear-interpolated quantile (numpy/pandas default) of sorted values. */
export function quantile(sorted: readonly number[], p: number): number {
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const a = sorted[lo] ?? NaN;
  const b = sorted[Math.min(lo + 1, sorted.length - 1)] ?? NaN;
  return a + (b - a) * (pos - lo);
}

/** Tukey box: whiskers at the most extreme values within 1.5·IQR of the box; the rest are outliers. */
export function fiveNumber(values: readonly number[]): FiveNumber | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const q1 = quantile(sorted, 0.25);
  const q3 = quantile(sorted, 0.75);
  const fence = 1.5 * (q3 - q1);
  const inside = sorted.filter((v) => v >= q1 - fence && v <= q3 + fence);
  return {
    min: inside[0] ?? q1,
    q1,
    median: quantile(sorted, 0.5),
    q3,
    max: inside[inside.length - 1] ?? q3,
    outliers: sorted.filter((v) => v < q1 - fence || v > q3 + fence),
  };
}

export function boxplotOption(data: TabularData, opts: BoxplotOpts): EChartsOption {
  const groupKey = requireColumn(data, opts.group).key;
  const valueCol = requireColumn(data, opts.value);
  const groups = distinct(data.rows.map((r) => cellLabel(r[groupKey])));
  const stats = groups.map((g) =>
    fiveNumber(
      data.rows
        .filter((r) => cellLabel(r[groupKey]) === g)
        .flatMap((r) => {
          const v = numeric(r[valueCol.key]);
          return v === null ? [] : [v];
        }),
    ),
  );
  const boxes: BoxplotSeriesOption = {
    type: 'boxplot',
    name: valueCol.label,
    data: stats.map((s) => (s ? [s.min, s.q1, s.median, s.q3, s.max] : [])),
  };
  const outliers: ScatterSeriesOption = {
    type: 'scatter',
    name: 'Outliers',
    symbolSize: 6,
    data: stats.flatMap((s, i) => (s ? s.outliers.map((v) => [i, v]) : [])),
  };
  return {
    grid: GRID,
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: groups },
    yAxis: { type: 'value', name: opts.yName ?? valueCol.label, scale: true },
    series: [boxes, outliers],
  };
}
```

- [ ] **Step 29: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/boxplot.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 30: Write the failing test for the calendar heatmap builder**

Create the full contents of `frontend/src/components/charts/builders/calendar.test.ts`:

```ts
import type { HeatmapSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { calendarOption } from './calendar';

const ATTENDED: TabularData = {
  columns: [
    { key: 'event_date', label: 'Event', type: 'date' },
    { key: 'score', label: 'Score', type: 'int' },
  ],
  rows: [
    { event_date: '2025-12-28', score: 30 },
    { event_date: '2026-09-06', score: 38 },
    { event_date: '2026-09-13', score: 41 },
    { event_date: '2026-09-20', score: null },
  ],
};

describe('calendarOption', () => {
  it('keeps only the requested year and scales colors to its values', () => {
    const o = calendarOption(ATTENDED, { date: 'event_date', value: 'score', year: 2026 });
    const [series] = o.series as [HeatmapSeriesOption];
    expect(series).toMatchObject({ coordinateSystem: 'calendar', name: 'Score' });
    expect(series.data).toEqual([
      ['2026-09-06', 38],
      ['2026-09-13', 41],
    ]);
    expect(o.calendar).toMatchObject({
      range: '2026',
      orient: 'horizontal',
      cellSize: ['auto', 16],
    });
    expect(o.visualMap).toMatchObject({ min: 38, max: 41 });
  });

  it('supports a vertical phone layout, fixed bounds and an empty year', () => {
    const o = calendarOption(ATTENDED, {
      date: 'event_date',
      value: 'score',
      year: 2024,
      orient: 'vertical',
      min: 0,
      max: 50,
    });
    expect(o.calendar).toMatchObject({ orient: 'vertical', cellSize: [16, 'auto'] });
    expect(o.visualMap).toMatchObject({ min: 0, max: 50 });
    const empty = calendarOption(ATTENDED, { date: 'event_date', value: 'score', year: 2024 });
    expect(empty.visualMap).toMatchObject({ min: 0, max: 1 });
  });
});
```

- [ ] **Step 31: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/calendar.test.ts`
Expected: FAIL — `Failed to resolve import "./calendar"`.

- [ ] **Step 32: Implement `calendarOption`**

Create the full contents of `frontend/src/components/charts/builders/calendar.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { colors } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { numeric, requireColumn } from './common';

export interface CalendarOpts {
  /** ISO date column. */
  date: string;
  value: string;
  year: number;
  min?: number;
  max?: number;
  /** 'vertical' fits phones (weeks run down the screen). */
  orient?: 'horizontal' | 'vertical';
}

export function calendarOption(data: TabularData, opts: CalendarOpts): EChartsOption {
  const dateKey = requireColumn(data, opts.date).key;
  const valueCol = requireColumn(data, opts.value);
  const prefix = `${opts.year}-`;
  const cells = data.rows.flatMap((r) => {
    const d = r[dateKey];
    const v = numeric(r[valueCol.key]);
    return typeof d === 'string' && d.startsWith(prefix) && v !== null
      ? [[d, v] as [string, number]]
      : [];
  });
  const values = cells.map(([, v]) => v);
  const vertical = opts.orient === 'vertical';
  return {
    tooltip: { trigger: 'item' },
    visualMap: {
      type: 'continuous',
      min: opts.min ?? (values.length ? Math.min(...values) : 0),
      max: opts.max ?? (values.length ? Math.max(...values) : 1),
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      calculable: false,
    },
    calendar: {
      range: String(opts.year),
      orient: opts.orient ?? 'horizontal',
      top: vertical ? 32 : 24,
      left: vertical ? 40 : 32,
      right: 16,
      bottom: 48,
      cellSize: vertical ? [16, 'auto'] : ['auto', 16],
      yearLabel: { show: false },
      dayLabel: { firstDay: 0, color: colors.textMuted },
      monthLabel: { color: colors.textMuted },
      itemStyle: { color: colors.surface, borderColor: colors.elevated, borderWidth: 2 },
      splitLine: { show: false },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', name: valueCol.label, data: cells }],
  };
}
```

- [ ] **Step 33: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/calendar.test.ts`
Expected: PASS — 2 tests.

- [ ] **Step 34: Write the failing test for the bar-race builder**

Create the full contents of `frontend/src/components/charts/builders/race.test.ts`:

```ts
import type { BarSeriesOption, GraphicComponentOption, YAXisComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import { chartPalette } from '../../../theme/tokens';
import type { LeaderboardFrame } from '../types';
import { colorFor, raceOption } from './race';

const FRAME: LeaderboardFrame = {
  date: '2026-09-13',
  rows: [
    { id: 7, name: 'Able, Ann', value: 58, rank: 1 },
    { id: 9, name: 'Tarleton, Jo', value: 51, rank: 2 },
    { id: 12, name: 'Tarleton, Jo', value: 40, rank: 3 },
  ],
};

describe('colorFor', () => {
  it('gives the same id the same palette color every time', () => {
    expect(colorFor(7)).toBe(colorFor('7'));
    expect(chartPalette).toContain(colorFor(12345));
  });
});

describe('raceOption', () => {
  it('builds a realtime-sorted bar frame with stable colors and the frame date', () => {
    const o = raceOption(FRAME, { top: 2, valueName: 'Points', durationMs: 500 });
    const yAxis = o.yAxis as YAXisComponentOption & { data: string[]; max: number };
    expect(yAxis).toMatchObject({ inverse: true, max: 1 });
    expect(yAxis.data).toEqual(['Able, Ann', 'Tarleton, Jo #9', 'Tarleton, Jo #12']);
    const [bars] = o.series as [BarSeriesOption];
    expect(bars).toMatchObject({ realtimeSort: true, name: 'Points' });
    expect(bars.data).toEqual([
      { value: 58, itemStyle: { color: colorFor(7) } },
      { value: 51, itemStyle: { color: colorFor(9) } },
      { value: 40, itemStyle: { color: colorFor(12) } },
    ]);
    expect(o.animationDurationUpdate).toBe(500);
    const graphic = o.graphic as { elements: GraphicComponentOption[] };
    expect(graphic.elements[0]).toMatchObject({ style: { text: '2026-09-13' } });
  });

  it('defaults to a top 10 and copes with an empty frame', () => {
    const o = raceOption({ date: '2026-01-04', rows: [] });
    expect(o.yAxis).toMatchObject({ max: 0, data: [] });
    expect(o.animationDurationUpdate).toBe(800);
  });
});
```

- [ ] **Step 35: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/race.test.ts`
Expected: FAIL — `Failed to resolve import "./race"`.

- [ ] **Step 36: Implement `colorFor` and `raceOption`**

Create the full contents of `frontend/src/components/charts/builders/race.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { chartPalette, colors } from '../../../theme/tokens';
import type { LeaderboardFrame } from '../types';

export interface RaceOpts {
  /** Bars visible at once. */
  top?: number;
  valueName?: string;
  /** Transition time between frames, ms. */
  durationMs?: number;
}

/** A stable palette color per shooter so bars keep their color from frame to frame. */
export function colorFor(id: number | string): string {
  const text = String(id);
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return chartPalette[hash % chartPalette.length] ?? chartPalette[0];
}

/** Names repeated within one frame get their id appended so categories stay unique. */
function uniqueNames(rows: LeaderboardFrame['rows']): string[] {
  const counts = new Map<string, number>();
  for (const r of rows) counts.set(r.name, (counts.get(r.name) ?? 0) + 1);
  return rows.map((r) => ((counts.get(r.name) ?? 0) > 1 ? `${r.name} #${r.id}` : r.name));
}

/** One frame of a bar-chart race; feed successive frames to the same EChart to animate. */
export function raceOption(frame: LeaderboardFrame, opts: RaceOpts = {}): EChartsOption {
  const top = opts.top ?? 10;
  const duration = opts.durationMs ?? 800;
  const names = uniqueNames(frame.rows);
  return {
    grid: { left: 8, right: 56, top: 16, bottom: 32, containLabel: true },
    xAxis: { type: 'value', max: 'dataMax', name: opts.valueName ?? '' },
    yAxis: {
      type: 'category',
      inverse: true,
      max: Math.max(0, Math.min(top, frame.rows.length) - 1),
      data: names,
      animationDuration: 300,
      animationDurationUpdate: 300,
    },
    series: [
      {
        type: 'bar',
        realtimeSort: true,
        name: opts.valueName ?? 'Value',
        data: frame.rows.map((r) => ({ value: r.value, itemStyle: { color: colorFor(r.id) } })),
        label: { show: true, position: 'right', valueAnimation: true },
      },
    ],
    animationDuration: 0,
    animationDurationUpdate: duration,
    animationEasing: 'linear',
    animationEasingUpdate: 'linear',
    graphic: {
      elements: [
        {
          type: 'text',
          right: 16,
          bottom: 40,
          style: { text: frame.date, font: 'bold 28px Roboto, sans-serif', fill: colors.textMuted },
        },
      ],
    },
  };
}
```

- [ ] **Step 37: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/race.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 38: Write the failing test for the bump-chart builder**

Create the full contents of `frontend/src/components/charts/builders/bump.test.ts`:

```ts
import type { LineSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { LeaderboardFrame } from '../types';
import { bumpOption } from './bump';
import { colorFor } from './race';

const FRAMES: LeaderboardFrame[] = [
  {
    date: '2026-09-06',
    rows: [
      { id: 1, name: 'Able', value: 10, rank: 1 },
      { id: 2, name: 'Baker', value: 8, rank: 2 },
      { id: 3, name: 'Slocum', value: 6, rank: 3 },
    ],
  },
  {
    date: '2026-09-13',
    rows: [
      { id: 2, name: 'Baker', value: 18, rank: 1 },
      { id: 1, name: 'Able', value: 16, rank: 2 },
    ],
  },
];

describe('bumpOption', () => {
  it('draws one rank line per shooter in the top N, with gaps when out of it', () => {
    const o = bumpOption(FRAMES, { top: 2 });
    const series = o.series as LineSeriesOption[];
    expect(series.map((s) => [s.name, s.data])).toEqual([
      ['Able', [1, 2]],
      ['Baker', [2, 1]],
    ]);
    expect(series[0]).toMatchObject({
      itemStyle: { color: colorFor('1') },
      endLabel: { show: true, formatter: 'Able' },
    });
    expect(o.xAxis).toMatchObject({ data: ['2026-09-06', '2026-09-13'] });
    expect(o.yAxis).toMatchObject({ inverse: true, min: 1, max: 2 });
  });

  it('defaults to the top 10', () => {
    const o = bumpOption(FRAMES);
    expect((o.series as LineSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['Able', [1, 2]],
      ['Baker', [2, 1]],
      ['Slocum', [3, null]],
    ]);
    expect(o.yAxis).toMatchObject({ max: 10 });
  });
});
```

- [ ] **Step 39: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/bump.test.ts`
Expected: FAIL — `Failed to resolve import "./bump"`.

- [ ] **Step 40: Implement `bumpOption`**

Create the full contents of `frontend/src/components/charts/builders/bump.ts`:

```ts
import type { EChartsOption, LineSeriesOption } from 'echarts';
import type { LeaderboardFrame } from '../types';
import { GRID } from './common';
import { colorFor } from './race';

export interface BumpOpts {
  /** Ranks shown (1..top); lower ranks leave gaps in a line. */
  top?: number;
}

/** Rank-over-time lines, one per shooter who reached the top N in any frame. */
export function bumpOption(
  frames: readonly LeaderboardFrame[],
  opts: BumpOpts = {},
): EChartsOption {
  const top = opts.top ?? 10;
  const dates = frames.map((f) => f.date);
  const names = new Map<string, string>();
  for (const f of frames)
    for (const r of f.rows) if (r.rank <= top) names.set(String(r.id), r.name);
  const series: LineSeriesOption[] = [...names].map(([id, name]) => ({
    type: 'line',
    name,
    smooth: true,
    symbolSize: 8,
    connectNulls: false,
    itemStyle: { color: colorFor(id) },
    emphasis: { focus: 'series' },
    endLabel: { show: true, formatter: name },
    data: frames.map((f) => {
      const row = f.rows.find((r) => String(r.id) === id);
      return row && row.rank <= top ? row.rank : null;
    }),
  }));
  return {
    grid: { ...GRID, right: 120 },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value', inverse: true, min: 1, max: top, interval: 1, name: 'Rank' },
    series,
  };
}
```

- [ ] **Step 41: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/bump.test.ts`
Expected: PASS — 2 tests.

- [ ] **Step 42: Write the failing test for the ridgeline (KDE) builder**

Create the full contents of `frontend/src/components/charts/builders/ridgeline.test.ts`:

```ts
import type { LineSeriesOption, TooltipComponentOption, YAXisComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { kde, ridgelineOption, silverman } from './ridgeline';

describe('kde', () => {
  it('is a normal density centred on a single value', () => {
    const [atMean, oneSdAway] = kde([30], [30, 32], 2);
    expect(atMean).toBeCloseTo(1 / (2 * Math.sqrt(2 * Math.PI)), 10);
    expect(oneSdAway).toBeCloseTo(Math.exp(-0.5) / (2 * Math.sqrt(2 * Math.PI)), 10);
  });

  it('is zero everywhere without values', () => {
    expect(kde([], [0, 1], 1)).toEqual([0, 0]);
  });
});

describe('silverman', () => {
  it('follows 1.06·sd·n^(-1/5) with a floor of 0.5 and 1 for tiny samples', () => {
    expect(silverman([30, 34, 38, 42])).toBeCloseTo(1.06 * Math.sqrt(80 / 3) * 4 ** -0.2, 10);
    expect(silverman([35, 35, 35])).toBe(0.5);
    expect(silverman([35])).toBe(1);
  });
});

const BY_YEAR: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'score', label: 'Score', type: 'int' },
  ],
  rows: [
    { year: 2025, score: 34 },
    { year: 2025, score: 36 },
    { year: 2026, score: 40 },
    { year: '<img src=x onerror=alert(1)>', score: null },
  ],
};

describe('ridgelineOption', () => {
  it('stacks one ridge per group, first group on top, filled from its own baseline', () => {
    const o = ridgelineOption(BY_YEAR, {
      group: 'year',
      value: 'score',
      min: 30,
      max: 44,
      step: 2,
      bandwidth: 2,
      overlap: 1,
    });
    const series = o.series as LineSeriesOption[];
    expect(series.map((s) => s.name)).toEqual(['2025', '2026', '<img src=x onerror=alert(1)>']);
    expect(series.map((s) => (s.areaStyle as { origin: number }).origin)).toEqual([2, 1, 0]);
    const tallest = Math.max(
      ...series.flatMap((s) =>
        (s.data as [number, number][]).map(
          ([, y]) => y - (s.areaStyle as { origin: number }).origin,
        ),
      ),
    );
    expect(tallest).toBeCloseTo(1, 10);
    expect((series[2]?.data as [number, number][]).every(([, y]) => y === 0)).toBe(true);
    const yAxis = o.yAxis as YAXisComponentOption & {
      axisLabel: { formatter: (v: number) => string };
    };
    expect([0, 1, 2, 3].map((v) => yAxis.axisLabel.formatter(v))).toEqual([
      '<img src=x onerror=alert(1)>',
      '2026',
      '2025',
      '',
    ]);
  });

  it('escapes group names in the tooltip', () => {
    const o = ridgelineOption(BY_YEAR, { group: 'year', value: 'score', bandwidth: 2 });
    const formatter = (o.tooltip as TooltipComponentOption).formatter as (p: unknown) => string;
    const html = formatter([
      { seriesName: '2025', seriesIndex: 0, dataIndex: 35 },
      { seriesName: '<img src=x onerror=alert(1)>', seriesIndex: 2, dataIndex: 35 },
    ]);
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html.startsWith('Score 35<br/>2025: ')).toBe(true);
    expect(formatter([])).toBe('Score 0');
  });

  it('handles no data at all', () => {
    const o = ridgelineOption(
      { columns: BY_YEAR.columns, rows: [] },
      { group: 'year', value: 'score' },
    );
    expect(o.series).toEqual([]);
    expect(o.yAxis).toMatchObject({ max: 1 });
  });
});
```

- [ ] **Step 43: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/ridgeline.test.ts`
Expected: FAIL — `Failed to resolve import "./ridgeline"`.

- [ ] **Step 44: Implement `silverman`, `kde` and `ridgelineOption`**

Create the full contents of `frontend/src/components/charts/builders/ridgeline.ts`:

```ts
import type { EChartsOption, LineSeriesOption } from 'echarts';
import { chartPalette } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, escapeHtml, numeric, requireColumn } from './common';

export interface RidgelineOpts {
  /** One ridge per distinct value, first value at the top (e.g. year). */
  group: string;
  value: string;
  /** Density grid; default 0..50 step 1 (round scores). */
  min?: number;
  max?: number;
  step?: number;
  /** Gaussian kernel bandwidth; default Silverman's rule per group. */
  bandwidth?: number;
  /** Ridge height in rows; >1 lets ridges overlap. */
  overlap?: number;
}

/** Silverman's rule of thumb (1.06·σ·n^-1/5), at least 0.5. */
export function silverman(values: readonly number[]): number {
  const n = values.length;
  if (n < 2) return 1;
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const sd = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1));
  return Math.max(0.5, 1.06 * sd * n ** -0.2);
}

/** Gaussian kernel density of `values` evaluated at each grid point. */
export function kde(
  values: readonly number[],
  grid: readonly number[],
  bandwidth: number,
): number[] {
  const n = values.length;
  if (n === 0) return grid.map(() => 0);
  const norm = 1 / (n * bandwidth * Math.sqrt(2 * Math.PI));
  return grid.map(
    (x) => norm * values.reduce((s, v) => s + Math.exp(-0.5 * ((x - v) / bandwidth) ** 2), 0),
  );
}

export function ridgelineOption(data: TabularData, opts: RidgelineOpts): EChartsOption {
  const groupKey = requireColumn(data, opts.group).key;
  const valueCol = requireColumn(data, opts.value);
  const min = opts.min ?? 0;
  const max = opts.max ?? 50;
  const step = opts.step ?? 1;
  const overlap = opts.overlap ?? 1.8;
  const grid: number[] = [];
  for (let x = min; x <= max; x += step) grid.push(x);
  const groups = distinct(data.rows.map((r) => cellLabel(r[groupKey])));
  const densities = groups.map((g) => {
    const values = data.rows
      .filter((r) => cellLabel(r[groupKey]) === g)
      .flatMap((r) => {
        const v = numeric(r[valueCol.key]);
        return v === null ? [] : [v];
      });
    return kde(values, grid, opts.bandwidth ?? silverman(values));
  });
  const peak = Math.max(0, ...densities.flat());
  const scale = peak > 0 ? overlap / peak : 0;
  const n = groups.length;
  const series: LineSeriesOption[] = groups.map((g, i) => {
    const baseline = n - 1 - i;
    const color = chartPalette[i % chartPalette.length] ?? chartPalette[0];
    return {
      type: 'line',
      name: g,
      smooth: true,
      symbol: 'none',
      z: i + 2,
      lineStyle: { width: 1.5, color },
      areaStyle: { origin: baseline, opacity: 0.35, color },
      data: grid.map((x, j) => [x, baseline + (densities[i]?.[j] ?? 0) * scale]),
    };
  });
  return {
    grid: { ...GRID, left: 16 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = params as { seriesName?: string; dataIndex?: number; seriesIndex?: number }[];
        const x = grid[list[0]?.dataIndex ?? 0];
        const lines = list.map((p) => {
          const d = densities[p.seriesIndex ?? 0]?.[p.dataIndex ?? 0] ?? 0;
          return `${escapeHtml(p.seriesName ?? '')}: ${(100 * d * step).toFixed(1)}%`;
        });
        return [`${escapeHtml(valueCol.label)} ${escapeHtml(x)}`, ...lines].join('<br/>');
      },
    },
    xAxis: { type: 'value', min, max, name: valueCol.label, nameLocation: 'middle', nameGap: 28 },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.max(1, n - 1 + overlap),
      interval: 1,
      axisLabel: { formatter: (v: number) => groups[n - 1 - v] ?? '' },
      splitLine: { show: false },
    },
    series,
  };
}
```

- [ ] **Step 45: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/builders/ridgeline.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 46: Write the failing `EChart` wrapper test**

Create the full contents of `frontend/src/components/charts/EChart.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import type { ECElementEvent, EChartsOption } from 'echarts';
import { getInstanceByDom } from 'echarts/core';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EChart } from './EChart';

const BAR: EChartsOption = {
  xAxis: { type: 'category', data: ['2025', '2026'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', name: 'Rounds', data: [1267, 969] }],
};
const LINE: EChartsOption = {
  xAxis: { type: 'category', data: ['a'] },
  yAxis: { type: 'value' },
  series: [{ type: 'line', name: 'Avg', data: [35] }],
};
const ZOOMABLE: EChartsOption = {
  xAxis: { type: 'category', data: ['2023', '2024', '2025', '2026'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', name: 'Rounds', data: [1100, 1180, 1267, 969] }],
  dataZoom: [{ type: 'inside' }],
};

function chartOf(): ReturnType<typeof getInstanceByDom> {
  return getInstanceByDom(screen.getByRole('img', { name: 'Rounds by year' }));
}

function clickPoint(dataIndex: number): void {
  chartOf()?.trigger('click', { dataIndex } as unknown as ECElementEvent);
}

const RealResizeObserver = globalThis.ResizeObserver;

afterEach(() => {
  globalThis.ResizeObserver = RealResizeObserver;
});

describe('EChart', () => {
  it('renders an accessible image region with the requested height and the sunday-clays theme', () => {
    render(<EChart option={BAR} height={240} ariaLabel="Rounds by year" />);
    const el = screen.getByRole('img', { name: 'Rounds by year' });
    expect(el).toHaveStyle({ height: '240px' });
    const option = chartOf()?.getOption() as { series: { name: string }[]; color: string[] };
    expect(option.series.map((s) => s.name)).toEqual(['Rounds']);
    expect(option.color[0]).toBe('#E8A77A');
  });

  it('replaces (not merges) the option when it changes', () => {
    const { rerender } = render(<EChart option={BAR} height="50vh" ariaLabel="Rounds by year" />);
    rerender(<EChart option={LINE} height="50vh" ariaLabel="Rounds by year" />);
    const option = chartOf()?.getOption() as { series: { type: string; name: string }[] };
    expect(option.series).toHaveLength(1);
    expect(option.series[0]).toMatchObject({ type: 'line', name: 'Avg' });
    expect(screen.getByRole('img', { name: 'Rounds by year' })).toHaveStyle({ height: '50vh' });
  });

  it('keeps the zoom when re-rendered with an equal option object', () => {
    const { rerender } = render(
      <EChart option={ZOOMABLE} height={200} ariaLabel="Rounds by year" />,
    );
    chartOf()?.dispatchAction({ type: 'dataZoom', start: 50, end: 100 });
    rerender(<EChart option={{ ...ZOOMABLE }} height={200} ariaLabel="Rounds by year" />);
    const option = chartOf()?.getOption() as { dataZoom: { start: number }[] };
    expect(option.dataZoom[0]?.start).toBe(50);
  });

  it('applies an option whose only change is the code of a formatter', () => {
    const { rerender } = render(
      <EChart
        option={{ ...BAR, tooltip: { formatter: () => 'old' } }}
        height={200}
        ariaLabel="Rounds by year"
      />,
    );
    rerender(
      <EChart
        option={{ ...BAR, tooltip: { formatter: () => 'new' } }}
        height={200}
        ariaLabel="Rounds by year"
      />,
    );
    const option = chartOf()?.getOption() as { tooltip: { formatter: () => string }[] };
    expect(option.tooltip[0]?.formatter()).toBe('new');
  });

  it('forwards chart events to onEvents and unbinds them when handlers change', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = render(
      <EChart option={BAR} height={200} ariaLabel="Rounds by year" onEvents={{ click: first }} />,
    );
    clickPoint(1);
    expect(first).toHaveBeenCalledWith(expect.objectContaining({ dataIndex: 1 }));
    rerender(
      <EChart
        option={BAR}
        height={200}
        ariaLabel="Rounds by year"
        onEvents={{ click: second, dblclick: undefined }}
      />,
    );
    clickPoint(0);
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('re-measures its container when it resizes and disposes the chart on unmount', () => {
    let onResize: () => void = () => undefined;
    globalThis.ResizeObserver = class {
      constructor(cb: () => void) {
        onResize = cb;
      }
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
    const { unmount } = render(<EChart option={BAR} height={200} ariaLabel="Rounds by year" />);
    const el = screen.getByRole('img', { name: 'Rounds by year' });
    // jsdom lays nothing out, so the chart starts at the 320px fallback width.
    expect(getInstanceByDom(el)?.getWidth()).toBe(320);
    Object.defineProperty(el, 'clientWidth', { configurable: true, value: 640 });
    onResize();
    expect(getInstanceByDom(el)?.getWidth()).toBe(640);
    unmount();
    expect(getInstanceByDom(el)).toBeUndefined();
  });
});
```

- [ ] **Step 47: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/EChart.test.tsx`
Expected: FAIL — `Failed to resolve import "./EChart"`.

- [ ] **Step 48: Implement the wrapper**

Create the full contents of `frontend/src/components/charts/EChart.tsx`:

```tsx
import type { EChartsOption, ECElementEvent } from 'echarts';
import { BarChart, BoxplotChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  CalendarComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
// `use` is aliased so eslint's rules-of-hooks does not mistake it for React's use().
import { init, registerTheme, use as registerModules, type EChartsType } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';
import { ECHARTS_THEME_NAME, echartsTheme } from '../../theme/echartsTheme';

// Only what the C10 builders use, so the charts chunk stays small.
registerModules([
  BarChart,
  BoxplotChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  CalendarComponent,
  DataZoomComponent,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);
registerTheme(ECHARTS_THEME_NAME, echartsTheme);

export type EChartEventName = 'click' | 'dblclick' | 'mouseover' | 'mouseout';
export type EChartEvents = {
  [K in EChartEventName]?: ((params: ECElementEvent) => void) | undefined;
};

export interface EChartProps {
  option: EChartsOption;
  /** CSS height; a number is px. */
  height: number | string;
  onEvents?: EChartEvents | undefined;
  ariaLabel: string;
}

/**
 * Content key of an option: JSON with every function replaced by its source text. Formatters
 * must read only values that are also in the option (every C10 builder does), because two
 * closures with the same source text compare equal.
 */
function optionKey(option: EChartsOption): string {
  return JSON.stringify(option, (_key, value: unknown) =>
    typeof value === 'function' ? String(value) : value,
  );
}

/**
 * Thin ECharts wrapper (C10). Data charts render inside ChartFrame/ChartCard, never bare.
 * An option object with the same content as the last one applied is skipped, so a parent
 * re-render (any URL change) never resets the user's zoom or replays the entry animation.
 */
export function EChart({ option, height, onEvents, ariaLabel }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const lastKey = useRef<string | null>(null);
  const initialHeight = useRef(height);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Explicit size so a not-yet-laid-out (or hidden) container never initializes at 0×0.
    const chart = init(el, ECHARTS_THEME_NAME, {
      renderer: 'canvas',
      width: el.clientWidth || 320,
      height:
        el.clientHeight ||
        (typeof initialHeight.current === 'number' ? initialHeight.current : 320),
    });
    chartRef.current = chart;
    // 'auto' re-measures the container; a bare resize() keeps the explicit init size forever.
    const observer = new ResizeObserver(() => chart.resize({ width: 'auto', height: 'auto' }));
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
      lastKey.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const key = optionKey(option);
    if (key === lastKey.current) return;
    lastKey.current = key;
    chart.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onEvents) return;
    const bound: [EChartEventName, (params: ECElementEvent) => void][] = [];
    for (const name of Object.keys(onEvents) as EChartEventName[]) {
      const handler = onEvents[name];
      if (handler) {
        chart.on(name, handler);
        bound.push([name, handler]);
      }
    }
    return () => {
      for (const [name, handler] of bound) chart.off(name, handler);
    };
  }, [onEvents]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={ariaLabel}
      style={{ height: typeof height === 'number' ? `${height}px` : height, width: '100%' }}
    />
  );
}
```

- [ ] **Step 49: Run the chart tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/components/charts`
Expected: PASS — 12 files, 49 tests, and no ECharts `Can't get DOM width or height` warning in the output.

- [ ] **Step 50: Prove the resize and equal-option guards are load-bearing**

In `frontend/src/components/charts/EChart.tsx`, make each change below on its own, run
`cd frontend && pnpm exec vitest run src/components/charts/EChart.test.tsx`, then revert it before the next:
1. `chart.resize({ width: 'auto', height: 'auto' })` → `chart.resize()`. Expected: FAIL — 1 failed, `re-measures its
   container when it resizes and disposes the chart on unmount` (`expected 320 to be 640`: a bare `resize()` keeps the
   explicit init size).
2. Delete the line `if (key === lastKey.current) return;`. Expected: FAIL — 1 failed, `keeps the zoom when
   re-rendered with an equal option object` (`expected +0 to be 50`).
3. Replace the body of `optionKey` with `return JSON.stringify(option);`. Expected: FAIL — 1 failed, `applies an option
   whose only change is the code of a formatter` (`expected 'old' to be 'new'`).

After reverting all three, run it again. Expected: PASS — 6 tests.

- [ ] **Step 51: Full suite, coverage, lint, types, format and build**

Run: `cd frontend && pnpm exec prettier --write src/components/charts`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; coverage ≥90% lines and ≥90% branches overall; `src/components/charts/builders`
≥90% lines and branches.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings (the aliased `use as registerModules` import keeps `react-hooks/rules-of-hooks` quiet).
Run: `cd frontend && pnpm build`
Expected: the build succeeds; nothing imports `EChart.tsx` yet, so the entry chunk does not grow.

- [ ] **Step 52: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/components/charts
git commit -F - <<'MSG'
feat(frontend): EChart wrapper, TabularData and the chart builder kit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

### Task 6: `ChartFrame`, zoom and `ChartCard` over `POST /api/explore` (master Plan 07 T6)

**Context.** Tasks 4, 5 and 7 of this plan have merged, so `pnpm typecheck` (which runs `pnpm gen:api` first)
generates `src/api/schema.d.ts` with `paths['/api/explore']` and the schemas `QuerySpec`, `QueryResult`, `Filters`,
`Column`, `Metric`, `Dim` and `Agg` (Task 7). Run `cd frontend && pnpm gen:api` once before starting so the editor sees
them. Run every command from the worktree root: frontend commands start with `cd frontend && `, and the commit step
starts with `cd "$(git rev-parse --show-toplevel)"` (agent shells reset the working directory between calls, Decision
D28). This task builds the two components every data chart in Plans 08–11 renders inside (C10): `ChartFrame`
(chart + "Table" toggle + CSV + "Fullscreen", view state in the URL, box/pinch zoom on cartesian charts, a drill link
on table rows) and `ChartCard` (a `ChartFrame` fed by `POST /api/explore`, with URL-backed chips for metric, group-by,
chart type and best-round-only, read-only chips for the card's own filters, and the global `rt` filter merged into
`spec.filters.round_types` unless the card sets its own). `useExplore` returns the spec that produced the shown result,
so while a new grouping loads the previous result is still drawn, and drilled, with its own grouping, never with the
new one (Decision D18). `ChartFrame` memoizes its zoomed option, and `EChart` (Task 5) skips an option equal to the last
one, so toggling one chart's Table or any URL filter never resets the zoom of the other charts on the page. Shooters
who share a display name get unique chart labels (`Jim #7`, `Jim #9`), so bars never shift onto the wrong name.
Builder grids come from the frozen `GRID` in `builders/common.ts` (Task 5), and one builder output can be shared (a
memoized option, several frames), so `withZoom` must never mutate `option.grid` or any other part of a builder output
in place (a frozen object throws in strict mode): it spreads/copies, e.g. `{ ...option, grid: { ...option.grid, … } }`.

**Files:**
- Create: `frontend/src/components/charts/zoom.ts`, `frontend/src/components/charts/DataTable.tsx`,
  `frontend/src/components/charts/ChartFrame.tsx`, `frontend/src/components/charts/explore.ts`,
  `frontend/src/components/charts/ChartCard.tsx`, `frontend/src/test/charts.ts`
- Test: `frontend/src/components/charts/zoom.test.ts`, `frontend/src/components/charts/ChartFrame.test.tsx`,
  `frontend/src/components/charts/explore.test.ts`, `frontend/src/components/charts/ChartCard.test.tsx`

**Interfaces:**
- Consumes: Task 7 `POST /api/explore` (C9 `QuerySpec` → `QueryResult`; 400 `{"error": {"code": "invalid_query",
  "message"}}`) through the generated `components['schemas']`; Task 5 `EChart`, `EChartEvents`, `TabularData`,
  `TabularRow`, `ChartType`, `barOption`, `lineOption`, `heatmapOption`, `cellLabel`; Task 4 `api`, `unwrap`,
  `downloadCsv`, `useUrlState`, `enumCodec`, `listCodec`, `boolCodec`, `useIsDesktop`, `useIsTouch`, `useRoundTypes`,
  `ROUND_TYPE_LABELS`, `formatNumber`, `renderWithProviders`, `stubViewport`; Task 1 `Button`, `Card`, `Chip`,
  `EmptyState`, `Skeleton`, `Sheet`.
- Produces:
  - `zoom.ts`: `type ZoomMode = 'x' | 'y' | 'xy' | 'none'`, `withZoom(option, mode, isTouch): EChartsOption` (inside
    zoom with `moveOnMouseMove: !isTouch`, a slider only without touch, toolbox zoom/restore; `'none'` → unchanged;
    otherwise a new object, never mutating `option` or its `grid`),
    `defaultZoom(option): ZoomMode` (`'y'` for horizontal bars, D17).
  - `DataTable.tsx`: `DataTable({caption, columns, rows, rowHref?})` (Decision D17 cell formatting).
  - `ChartFrame.tsx`: `ChartFrame(props: ChartFrameProps)` with the C10 props `{title, subtitle?, option, columns,
    rows, csvName, ariaLabel, urlKey, zoom?, onEvents?, actions?}` plus `controls?`, `height?` (default 320) and
    `rowHref?`. Buttons `Table`, `CSV`, `Fullscreen`; the view flags `table`/`full` live in `?<urlKey>=`.
  - `explore.ts`: `type QuerySpec`, `QueryResult`, `Filters`, `Metric`, `Dim`, `Agg` (schema aliases),
    `METRIC_LABELS`, `DIM_LABELS`, `AGG_LABELS`, `METRICS`, `DIMS`, `AGGS`, `DEFAULT_FILTERS`,
    `type QuerySpecInput`, `querySpec(input): QuerySpec`, `interface ExploreData {spec; result}`,
    `useExplore(spec)` (TanStack query keyed `['/api/explore', spec]`, `keepPreviousData`), `toTabular(result)`,
    `buildExploreOption(data, groupBy, chartType)` (a `shooter` display name held by more than one `shooter_id` is
    charted as `<name> #<id>`), `rowForClick(data, groupBy, params)` (returns the raw row, matched on those labels).
  - `ChartCard.tsx`: `ChartCard(props: ChartCardProps)` with `{title, subtitle?, spec, chartTypes, allowedGroupBy?,
    allowedMetrics?, urlKey, drill?}`; URL keys `<urlKey>.m`, `.g`, `.t`, `.b`, `.v` (Decision D18).
  - `test/charts.ts`: `expectChartControls(region: HTMLElement)` — asserts the `Table` and `CSV` buttons (C10 per-page
    chart test helper for Plans 08–11).

**Branch:** `task/07-6-chartframe-chartcard` · **Depends on:** Plan 07 T4, Plan 07 T5, Plan 07 T7.

- [ ] **Step 1: Write the failing zoom test**

Create the full contents of `frontend/src/components/charts/zoom.test.ts`:

```ts
import type { EChartsOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import { defaultZoom, withZoom } from './zoom';

const CARTESIAN: EChartsOption = {
  xAxis: { type: 'category' },
  yAxis: { type: 'value' },
  series: [],
};

describe('withZoom', () => {
  it("adds inside + slider zoom along x for 'x' on a pointer device", () => {
    const o = withZoom(CARTESIAN, 'x', false);
    expect(o.dataZoom).toEqual([
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: true },
      { type: 'slider', height: 18, bottom: 4 },
    ]);
    expect(o.toolbox).toMatchObject({ feature: { dataZoom: { yAxisIndex: 'none' }, restore: {} } });
    expect(o.series).toBe(CARTESIAN.series);
  });

  it('never pans on one-finger drag and drops the slider on touch', () => {
    const o = withZoom(CARTESIAN, 'x', true);
    expect(o.dataZoom).toEqual([
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: false },
    ]);
  });

  it("lets the toolbox box-zoom both axes for 'xy'", () => {
    const o = withZoom(CARTESIAN, 'xy', false) as {
      toolbox: { feature: { dataZoom: { yAxisIndex?: unknown } } };
    };
    expect(o.toolbox.feature.dataZoom.yAxisIndex).toBeUndefined();
  });

  it("returns the option untouched for 'none'", () => {
    expect(withZoom(CARTESIAN, 'none', false)).toBe(CARTESIAN);
  });
});

describe('defaultZoom', () => {
  it('zooms x on charts with both axes, not on calendars or axis-less charts', () => {
    expect(defaultZoom(CARTESIAN)).toBe('x');
    expect(defaultZoom({ ...CARTESIAN, calendar: {} })).toBe('none');
    expect(defaultZoom({ series: [] })).toBe('none');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/zoom.test.ts`
Expected: FAIL — `Failed to resolve import "./zoom"`.

- [ ] **Step 3: Implement the zoom helpers**

Create the full contents of `frontend/src/components/charts/zoom.ts`:

```ts
import type { EChartsOption } from 'echarts';

export type ZoomMode = 'x' | 'xy' | 'none';

/**
 * Box/pinch zoom for cartesian charts (C10): an inside dataZoom (mouse wheel zooms only with
 * Shift; drag pans except on touch, where one-finger drag must scroll the page), a slider on
 * non-touch devices, and toolbox zoom/restore buttons. 'none' returns the option unchanged.
 */
export function withZoom(option: EChartsOption, mode: ZoomMode, isTouch: boolean): EChartsOption {
  if (mode === 'none') return option;
  return {
    ...option,
    dataZoom: [
      { type: 'inside', zoomOnMouseWheel: 'shift', moveOnMouseMove: !isTouch },
      ...(isTouch ? [] : [{ type: 'slider' as const, height: 18, bottom: 4 }]),
    ],
    toolbox: {
      right: 8,
      top: 0,
      feature: { dataZoom: mode === 'x' ? { yAxisIndex: 'none' as const } : {}, restore: {} },
    },
  };
}

/** Charts with both axes zoom along x by default; calendars and axis-less charts do not. */
export function defaultZoom(option: EChartsOption): ZoomMode {
  return option.xAxis !== undefined && option.yAxis !== undefined && option.calendar === undefined
    ? 'x'
    : 'none';
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/zoom.test.ts`
Expected: PASS — 5 tests.

- [ ] **Step 5: Add the chart-controls test helper and write the failing `ChartFrame` test**

Create the full contents of `frontend/src/test/charts.ts`:

```ts
import { within } from '@testing-library/react';
import { expect } from 'vitest';

/** C10: every data chart exposes Table and CSV controls. `region` = the chart's titled card. */
export function expectChartControls(region: HTMLElement): void {
  expect(within(region).getByRole('button', { name: 'Table' })).toBeInTheDocument();
  expect(within(region).getByRole('button', { name: 'CSV' })).toBeInTheDocument();
}
```

Create the full contents of `frontend/src/components/charts/ChartFrame.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import type { EChartsOption } from 'echarts';
import { getInstanceByDom } from 'echarts/core';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { expectChartControls } from '../../test/charts';
import { renderWithProviders } from '../../test/render';
import { stubViewport } from '../../test/viewport';
import { ChartFrame, type ChartFrameProps } from './ChartFrame';
import type { TabularData } from './types';

const DATA: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'value', label: 'Avg score', type: 'number' },
    { key: 'note', label: 'Note', type: 'string' },
  ],
  rows: [
    { year: 2025, value: 35.2668, note: '=cmd' },
    { year: 2026, value: null, note: 'ok' },
  ],
};
const OPTION: EChartsOption = {
  xAxis: { type: 'category', data: ['2025', '2026'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: [35.27, null] }],
};

function renderFrame(props: Partial<ChartFrameProps> = {}, route = '/club') {
  return renderWithProviders(
    <ChartFrame
      title="Average score by year"
      option={OPTION}
      columns={DATA.columns}
      rows={DATA.rows}
      csvName="avg-by-year"
      ariaLabel="Average score by year chart"
      urlKey="avg"
      {...props}
    />,
    { route },
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ChartFrame', () => {
  it('renders the chart in a titled card with Table, CSV and Fullscreen controls', () => {
    renderFrame({ subtitle: 'Since 2020', actions: <button type="button">Extra</button> });
    const region = screen.getByRole('region', { name: 'Average score by year' });
    expectChartControls(region);
    expect(within(region).getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
    expect(within(region).getByRole('button', { name: 'Extra' })).toBeInTheDocument();
    expect(within(region).getByText('Since 2020')).toBeInTheDocument();
    expect(
      within(region).getByRole('img', { name: 'Average score by year chart' }),
    ).toBeInTheDocument();
  });

  it('adds x zoom to cartesian charts by default and honours an explicit mode', () => {
    renderFrame();
    const chart = getInstanceByDom(
      screen.getByRole('img', { name: 'Average score by year chart' }),
    );
    expect((chart?.getOption() as { dataZoom?: unknown[] }).dataZoom).toHaveLength(2);
  });

  it('keeps zoom off when asked', () => {
    renderFrame({ zoom: 'none' });
    const chart = getInstanceByDom(
      screen.getByRole('img', { name: 'Average score by year chart' }),
    );
    expect((chart?.getOption() as { dataZoom?: unknown[] }).dataZoom ?? []).toHaveLength(0);
  });

  it('toggles a table of the exact rows and remembers it in the URL', async () => {
    const { user, router } = renderFrame();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(router.state.location.search).toBe('?avg=table');
    expect(screen.getByRole('button', { name: 'Table' })).toHaveAttribute('aria-pressed', 'true');
    const table = screen.getByRole('table', { name: 'Average score by year' });
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Year', 'Avg score', 'Note']);
    expect(
      within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) => r.textContent),
    ).toEqual(['202535.27=cmd', '2026—ok']);
    expect(screen.queryByRole('img')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(router.state.location.search).toBe('');
  });

  it('opens the table directly from a shared URL, linking the first text column', () => {
    renderFrame({ rowHref: (row) => `/club?year=${String(row.year)}` }, '/club?avg=table');
    expect(screen.getByRole('link', { name: '=cmd' })).toHaveAttribute('href', '/club?year=2025');
  });

  it('links the first column when the table has no text column', () => {
    renderFrame(
      {
        columns: DATA.columns.slice(0, 2),
        rows: DATA.rows,
        rowHref: (row) => `/club?year=${String(row.year)}`,
      },
      '/club?avg=table',
    );
    expect(screen.getByRole('link', { name: '2026' })).toHaveAttribute('href', '/club?year=2026');
  });

  it('downloads the rows as CSV', async () => {
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });
    const createUrl = vi.spyOn(URL, 'createObjectURL');
    const { user } = renderFrame();
    await user.click(screen.getByRole('button', { name: 'CSV' }));
    expect(names).toEqual(['avg-by-year.csv']);
    const blob = createUrl.mock.calls.at(-1)?.[0] as Blob;
    const text = new TextDecoder().decode((await blob.arrayBuffer()).slice(3));
    expect(text).toBe("Year,Avg score,Note\r\n2025,35.2668,'=cmd\r\n2026,,ok\r\n");
  });

  it('opens fullscreen as a centered dialog on desktop and closes it', async () => {
    stubViewport('desktop');
    const { user, router } = renderFrame();
    await user.click(screen.getByRole('button', { name: 'Fullscreen' }));
    const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
    expect(
      within(dialog).getByRole('img', { name: 'Average score by year chart' }),
    ).toBeInTheDocument();
    expect(router.state.location.search).toBe('?avg=full');
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(router.state.location.search).toBe('');
  });

  it('shows the table inside the fullscreen sheet on mobile when both are on', () => {
    stubViewport('mobile');
    renderFrame({}, '/club?avg=table,full');
    const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
    expect(within(dialog).getByRole('table')).toBeInTheDocument();
  });

  it("keeps a chart's zoom when another frame's Table toggle changes the URL", async () => {
    const frame = (key: string) => (
      <ChartFrame
        title={`Frame ${key}`}
        option={OPTION}
        columns={DATA.columns}
        rows={DATA.rows}
        csvName={key}
        ariaLabel={`Chart ${key}`}
        urlKey={key}
      />
    );
    const { user } = renderWithProviders(
      <>
        {frame('a')}
        {frame('b')}
      </>,
    );
    const chartA = getInstanceByDom(screen.getByRole('img', { name: 'Chart a' }));
    chartA?.dispatchAction({ type: 'dataZoom', start: 50, end: 100 });
    await user.click(
      within(screen.getByRole('region', { name: 'Frame b' })).getByRole('button', {
        name: 'Table',
      }),
    );
    const option = chartA?.getOption() as { dataZoom: { start: number }[] };
    expect(option.dataZoom[0]?.start).toBe(50);
  });

  it('forwards chart clicks to onEvents', () => {
    const click = vi.fn();
    renderFrame({ onEvents: { click } });
    getInstanceByDom(screen.getByRole('img', { name: 'Average score by year chart' }))?.trigger(
      'click',
      { dataIndex: 0 } as never,
    );
    expect(click).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/ChartFrame.test.tsx`
Expected: FAIL — `Failed to resolve import "./ChartFrame"`.

- [ ] **Step 7: Implement the table view and `ChartFrame`**

Create the full contents of `frontend/src/components/charts/DataTable.tsx`:

```tsx
import { Link } from 'react-router';
import { formatNumber } from '../../lib/format';
import type { Cell, TabularColumn, TabularRow } from './types';

/** 'int' cells (years, ids, stations, counts) print as-is; 'number' cells get grouping and ≤2 dp. */
function formatCell(value: Cell | undefined, column: TabularColumn): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    if (column.type === 'int' && Number.isInteger(value)) return String(value);
    return formatNumber(value, Number.isInteger(value) ? 0 : 2);
  }
  return value;
}

export interface DataTableProps {
  caption: string;
  columns: readonly TabularColumn[];
  rows: readonly TabularRow[];
  /** Drill-down: links the first text column's cell (else the first cell) of each row. */
  rowHref?: ((row: TabularRow) => string) | undefined;
}

/** The "Table" view of a chart: the exact rows behind it. */
export function DataTable({ caption, columns, rows, rowHref }: DataTableProps) {
  const linkIndex = Math.max(
    0,
    columns.findIndex((c) => c.type === 'string'),
  );
  return (
    <div className="max-h-96 overflow-auto">
      <table className="w-full border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-elevated">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={`border-b border-outline-variant px-2 py-2 font-medium text-text-muted ${c.type === 'number' || c.type === 'int' ? 'text-right' : ''}`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-outline-variant/40">
              {columns.map((c, j) => {
                const text = formatCell(row[c.key], c);
                const numericCol = c.type === 'number' || c.type === 'int';
                return (
                  <td
                    key={c.key}
                    className={`px-2 py-2 ${numericCol ? 'text-right tabular-nums' : ''}`}
                  >
                    {j === linkIndex && rowHref ? (
                      <Link
                        to={rowHref(row)}
                        className="text-accent underline-offset-2 hover:underline"
                      >
                        {text}
                      </Link>
                    ) : (
                      text
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

Create the full contents of `frontend/src/components/charts/ChartFrame.tsx`:

```tsx
import type { EChartsOption } from 'echarts';
import { Download, Maximize2, Table2 } from 'lucide-react';
import { useMemo, type ReactNode } from 'react';
import { downloadCsv } from '../../lib/csv';
import { useIsDesktop, useIsTouch } from '../../lib/useMediaQuery';
import { enumCodec, listCodec, useUrlState } from '../../lib/useUrlState';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Sheet } from '../ui/Sheet';
import { DataTable } from './DataTable';
import { EChart, type EChartEvents } from './EChart';
import type { TabularData, TabularRow } from './types';
import { defaultZoom, withZoom, type ZoomMode } from './zoom';

export interface ChartFrameProps {
  title: string;
  subtitle?: string | undefined;
  option: EChartsOption;
  columns: TabularData['columns'];
  rows: TabularData['rows'];
  csvName: string;
  ariaLabel: string;
  /** Query-string key holding this frame's view state ("table", "full"). */
  urlKey: string;
  /** Default 'x' for charts with x and y axes, 'none' otherwise. */
  zoom?: ZoomMode | undefined;
  onEvents?: EChartEvents | undefined;
  actions?: ReactNode;
  /** Rendered between the header and the chart (e.g. ChartCard's chips). */
  controls?: ReactNode;
  /** Chart height in px (default 320). */
  height?: number | undefined;
  /** Drill-down link for each table row's first cell. */
  rowHref?: ((row: TabularRow) => string) | undefined;
}

type ViewFlag = 'table' | 'full';
const viewCodec = listCodec(enumCodec<ViewFlag>(['table', 'full']));
const NO_FLAGS: ViewFlag[] = [];

/** Every data chart renders inside this (C10): chart, Table toggle, CSV export, fullscreen. */
export function ChartFrame({
  title,
  subtitle,
  option,
  columns,
  rows,
  csvName,
  ariaLabel,
  urlKey,
  zoom,
  onEvents,
  actions,
  controls,
  height = 320,
  rowHref,
}: ChartFrameProps) {
  const [flags, setFlags] = useUrlState(urlKey, viewCodec, NO_FLAGS);
  const isDesktop = useIsDesktop();
  const isTouch = useIsTouch();
  const showTable = flags.includes('table');
  const fullscreen = flags.includes('full');
  const toggle = (flag: ViewFlag) =>
    setFlags(flags.includes(flag) ? flags.filter((f) => f !== flag) : [...flags, flag]);
  const mode = zoom ?? defaultZoom(option);
  // Stable option objects: this frame re-renders on every URL change (useUrlState).
  const inlineOption = useMemo(() => withZoom(option, mode, isTouch), [option, mode, isTouch]);
  const fullscreenOption = useMemo(() => withZoom(option, mode, false), [option, mode]);

  const body = (inFullscreen: boolean) =>
    showTable ? (
      <DataTable caption={title} columns={columns} rows={rows} rowHref={rowHref} />
    ) : (
      <EChart
        option={inFullscreen ? fullscreenOption : inlineOption}
        height={inFullscreen ? '70dvh' : height}
        ariaLabel={ariaLabel}
        onEvents={onEvents}
      />
    );

  const toolbar = (
    <>
      {actions}
      <Button
        variant="ghost"
        aria-pressed={showTable}
        aria-label="Table"
        title="Show the data as a table"
        icon={<Table2 aria-hidden="true" className="size-4" />}
        onClick={() => toggle('table')}
      />
      <Button
        variant="ghost"
        aria-label="CSV"
        title="Download CSV"
        icon={<Download aria-hidden="true" className="size-4" />}
        onClick={() => downloadCsv(csvName, columns, rows)}
      />
      <Button
        variant="ghost"
        aria-label="Fullscreen"
        aria-pressed={fullscreen}
        icon={<Maximize2 aria-hidden="true" className="size-4" />}
        onClick={() => toggle('full')}
      />
    </>
  );

  return (
    <Card title={title} subtitle={subtitle} actions={toolbar}>
      {controls !== undefined && <div className="mb-3 flex flex-wrap gap-2">{controls}</div>}
      {fullscreen ? <div style={{ height }} aria-hidden="true" /> : body(false)}
      <Sheet
        open={fullscreen}
        onClose={() => toggle('full')}
        title={title}
        placement={isDesktop ? 'center' : 'bottom'}
        size="full"
      >
        {body(true)}
      </Sheet>
    </Card>
  );
}
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/ChartFrame.test.tsx`
Expected: PASS — 11 tests.

- [ ] **Step 9: Write the failing explore adapter test**

Create the full contents of `frontend/src/components/charts/explore.test.ts`:

```ts
import type { BarSeriesOption, HeatmapSeriesOption, LineSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import { buildExploreOption, querySpec, rowForClick, toTabular, type QueryResult } from './explore';
import type { TabularData } from './types';

const BY_YEAR_STATUS: QueryResult = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'status', label: 'Status', type: 'string' },
    { key: 'value', label: 'Rounds', type: 'int' },
    { key: 'n', label: 'n', type: 'int' },
  ],
  rows: [
    { year: 2025, status: 'member', value: 1200, n: 1200 },
    { year: 2025, status: null, value: 67, n: 67 },
    { year: 2026, status: 'member', value: 950, n: 950 },
  ],
  n_rounds: 2217,
  truncated: false,
};

describe('querySpec', () => {
  it('fills server defaults and merges partial filters', () => {
    expect(
      querySpec({ metric: 'score', group_by: ['year'], filters: { best_round_only: true } }),
    ).toEqual({
      metric: 'score',
      agg: 'avg',
      group_by: ['year'],
      sort: 'key_asc',
      limit: 500,
      filters: {
        best_round_only: true,
        gauges: [],
        min_rounds: 0,
        round_types: [],
        shooter_ids: [],
        statuses: [],
      },
    });
  });
});

describe('buildExploreOption', () => {
  const data = toTabular(BY_YEAR_STATUS);

  it('adapts a QueryResult to TabularData', () => {
    expect(data.columns.map((c) => c.key)).toEqual(['year', 'status', 'value', 'n']);
    expect(data.rows).toBe(BY_YEAR_STATUS.rows);
  });

  it('draws bars by the first dim with one series per second-dim value', () => {
    const o = buildExploreOption(data, ['year', 'status'], 'bar');
    expect(o.xAxis).toMatchObject({ type: 'category', data: ['2025', '2026'] });
    expect((o.series as BarSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['member', [1200, 950]],
      ['—', [67, null]],
    ]);
  });

  it('draws horizontal bars for shooters and lines when asked', () => {
    const shooters: TabularData = {
      columns: [
        { key: 'shooter_id', label: 'Shooter ID', type: 'int' },
        { key: 'shooter', label: 'Shooter', type: 'string' },
        { key: 'value', label: 'Avg score', type: 'number' },
      ],
      rows: [{ shooter_id: 3, shooter: 'Slocum, Cy', value: 42 }],
    };
    expect(buildExploreOption(shooters, ['shooter'], 'bar').yAxis).toMatchObject({
      type: 'category',
      data: ['Slocum, Cy'],
    });
    const line = buildExploreOption(data, ['year'], 'line');
    expect((line.series as LineSeriesOption[])[0]?.type).toBe('line');
  });

  it('draws a heatmap for two dims and falls back to bars with one', () => {
    const heat = buildExploreOption(data, ['year', 'status'], 'heatmap');
    expect((heat.series as HeatmapSeriesOption[])[0]?.type).toBe('heatmap');
    expect(heat.yAxis).toMatchObject({ data: ['2025', '2026'] });
    expect(
      (buildExploreOption(data, ['year'], 'heatmap').series as BarSeriesOption[])[0]?.type,
    ).toBe('bar');
  });

  it('shows a single "All" bar without dims', () => {
    const total: TabularData = {
      columns: [{ key: 'value', label: 'Rounds', type: 'int' }],
      rows: [{ value: 7480 }],
    };
    const o = buildExploreOption(total, [], 'line');
    expect(o.xAxis).toMatchObject({ data: ['All'] });
    expect((o.series as BarSeriesOption[])[0]?.data).toEqual([7480]);
  });
});

describe('shooters who share a display name', () => {
  const twoJims: TabularData = {
    columns: [
      { key: 'shooter_id', label: 'Shooter ID', type: 'int' },
      { key: 'shooter', label: 'Shooter', type: 'string' },
      { key: 'value', label: 'Avg score', type: 'number' },
    ],
    rows: [
      { shooter_id: 7, shooter: 'Desmond', value: 30 },
      { shooter_id: 9, shooter: 'Desmond', value: 40 },
    ],
  };

  it('get their id appended so each keeps its own bar', () => {
    const o = buildExploreOption(twoJims, ['shooter'], 'bar');
    expect(o.yAxis).toMatchObject({ data: ['Jim #7', 'Jim #9'] });
    expect((o.series as BarSeriesOption[])[0]?.data).toEqual([30, 40]);
    expect(twoJims.rows[1]?.shooter).toBe('Desmond');
  });

  it('drill to the raw row of the shooter that was clicked', () => {
    expect(rowForClick(twoJims, ['shooter'], { name: 'Jim #9' })).toBe(twoJims.rows[1]);
  });

  it('leave one shooter spread over several rows unchanged', () => {
    const byYear: TabularData = {
      columns: [...twoJims.columns, { key: 'year', label: 'Year', type: 'int' }],
      rows: [
        { shooter_id: 3, shooter: 'Slocum, Cy', year: 2025, value: 40 },
        { shooter_id: 3, shooter: 'Slocum, Cy', year: 2026, value: 41 },
      ],
    };
    expect(buildExploreOption(byYear, ['shooter', 'year'], 'bar').yAxis).toMatchObject({
      data: ['Slocum, Cy'],
    });
  });
});

describe('rowForClick', () => {
  const data = toTabular(BY_YEAR_STATUS);
  it('finds the row behind a bar by category and series', () => {
    expect(rowForClick(data, ['year', 'status'], { name: '2025', seriesName: '—' })).toBe(
      data.rows[1],
    );
    expect(rowForClick(data, ['year'], { name: '', value: ['2026', 950] })).toBe(data.rows[2]);
    expect(rowForClick(data, [], {})).toBe(data.rows[0]);
    expect(rowForClick(data, ['year'], { name: '1999' })).toBeUndefined();
    expect(rowForClick(data, ['year'], {})).toBeUndefined();
  });
});
```

- [ ] **Step 10: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/explore.test.ts`
Expected: FAIL — `Failed to resolve import "./explore"`.

- [ ] **Step 11: Implement the explore types, hook and adapters**

Create the full contents of `frontend/src/components/charts/explore.ts`:

```ts
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { barOption } from './builders/bar';
import { cellLabel } from './builders/common';
import { heatmapOption } from './builders/heatmap';
import { lineOption } from './builders/line';
import type { ChartType, TabularData, TabularRow } from './types';

export type QuerySpec = components['schemas']['QuerySpec'];
export type QueryResult = components['schemas']['QueryResult'];
export type Filters = components['schemas']['Filters'];
export type Metric = components['schemas']['Metric'];
export type Dim = components['schemas']['Dim'];
export type Agg = components['schemas']['Agg'];

export const METRIC_LABELS: Record<Metric, string> = {
  score: 'Score',
  adjusted: 'Adjusted score',
  residual: 'Residual',
  rating: 'Rating',
  rounds: 'Rounds',
  shooters: 'Shooters',
  attendance: 'Attendance',
  wins: 'Wins',
  hit_pct: 'Hit %',
};

export const DIM_LABELS: Record<Dim, string> = {
  shooter: 'Shooter',
  event: 'Event',
  month: 'Month',
  year: 'Year',
  season: 'Season',
  month_of_year: 'Month of year',
  round_type: 'Round type',
  gauge: 'Gauge',
  status: 'Status',
  temp_band: 'Temperature',
  wind_band: 'Wind',
  precip_band: 'Precipitation',
  condition: 'Conditions',
  station: 'Station',
  class: 'Class',
};

export const AGG_LABELS: Record<Agg, string> = {
  avg: 'Average',
  median: 'Median',
  max: 'Max',
  min: 'Min',
  sum: 'Total',
  count: 'Count',
  p90: '90th percentile',
  stdev: 'Std dev',
};

export const METRICS = Object.keys(METRIC_LABELS) as Metric[];
export const DIMS = Object.keys(DIM_LABELS) as Dim[];
export const AGGS = Object.keys(AGG_LABELS) as Agg[];

export const DEFAULT_FILTERS: Filters = {
  best_round_only: false,
  gauges: [],
  min_rounds: 0,
  round_types: [],
  shooter_ids: [],
  statuses: [],
};

export type QuerySpecInput = Pick<QuerySpec, 'metric'> &
  Partial<Omit<QuerySpec, 'metric' | 'filters'>> & { filters?: Partial<Filters> };

/** A complete QuerySpec from the fields a caller cares about (server defaults for the rest). */
export function querySpec(input: QuerySpecInput): QuerySpec {
  return {
    agg: 'avg',
    group_by: [],
    sort: 'key_asc',
    limit: 500,
    ...input,
    filters: { ...DEFAULT_FILTERS, ...input.filters },
  };
}

export interface ExploreData {
  /** The spec that produced `result` (while a new spec loads, the previous pair stays shown). */
  spec: QuerySpec;
  result: QueryResult;
}

/** POST /api/explore (C9); keeps the previous result on screen while a new spec loads. */
export function useExplore(spec: QuerySpec) {
  return useQuery({
    queryKey: ['/api/explore', spec],
    queryFn: async (): Promise<ExploreData> => ({
      spec,
      result: await unwrap(api.POST('/api/explore', { body: spec })),
    }),
    placeholderData: keepPreviousData,
  });
}

export function toTabular(result: QueryResult): TabularData {
  return {
    columns: result.columns.map((c) => ({ key: c.key, label: c.label, type: c.type })),
    rows: result.rows,
  };
}

const ALL = '_all';

/**
 * Chart categories must be unique, but two shooters can share a display name (first-name-only
 * guests are event-scoped new shooters, spec §2). A name held by more than one shooter_id gets
 * the id appended ('Jim #9'), as race.ts does. Row order is kept, so row i still matches
 * data.rows[i]; the table and CSV keep the raw rows.
 */
function withUniqueShooterNames(data: TabularData): TabularData {
  if (!data.columns.some((c) => c.key === 'shooter')) return data;
  const idsByName = new Map<string, Set<string>>();
  for (const r of data.rows) {
    const name = cellLabel(r.shooter);
    idsByName.set(name, (idsByName.get(name) ?? new Set<string>()).add(cellLabel(r.shooter_id)));
  }
  const shared = new Set([...idsByName].filter(([, ids]) => ids.size > 1).map(([name]) => name));
  return {
    columns: data.columns,
    rows: data.rows.map((r) =>
      shared.has(cellLabel(r.shooter))
        ? { ...r, shooter: `${cellLabel(r.shooter)} #${cellLabel(r.shooter_id)}` }
        : r,
    ),
  };
}

/**
 * Chart option for an explore result: dims[0] on the category/time axis, dims[1] as series.
 * Each dim's label column key equals the dim name (shooter → display name; 'shooter_id' is the id).
 */
export function buildExploreOption(
  data: TabularData,
  groupBy: readonly Dim[],
  chartType: ChartType,
): EChartsOption {
  const chart = withUniqueShooterNames(data);
  const [first, second] = groupBy;
  if (first === undefined) {
    const withAll: TabularData = {
      columns: [{ key: ALL, label: '', type: 'string' }, ...chart.columns],
      rows: chart.rows.map((r) => ({ ...r, [ALL]: 'All' })),
    };
    return barOption(withAll, { x: ALL, y: ['value'], labels: true });
  }
  const x: string = first;
  const by = second === undefined ? {} : { seriesBy: second };
  if (chartType === 'heatmap' && second !== undefined) {
    return heatmapOption(chart, {
      x: second,
      y: x,
      value: 'value',
      labels: chart.rows.length <= 150,
    });
  }
  if (chartType === 'line') return lineOption(chart, { x, y: ['value'], ...by, scaleY: true });
  return barOption(chart, { x, y: ['value'], ...by, horizontal: first === 'shooter' });
}

/** The raw result row behind a clicked bar or point (first dim = category, second = series). */
export function rowForClick(
  data: TabularData,
  groupBy: readonly Dim[],
  params: { name?: string; seriesName?: string; value?: unknown },
): TabularRow | undefined {
  const [first, second] = groupBy;
  if (first === undefined) return data.rows[0];
  const x = params.name || (Array.isArray(params.value) ? String(params.value[0]) : '');
  const index = withUniqueShooterNames(data).rows.findIndex(
    (r) =>
      cellLabel(r[first]) === x &&
      (second === undefined || cellLabel(r[second]) === (params.seriesName ?? '')),
  );
  return index === -1 ? undefined : data.rows[index];
}
```

- [ ] **Step 12: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/explore.test.ts`
Expected: PASS — 10 tests.

- [ ] **Step 13: Write the failing `ChartCard` test**

Create the full contents of `frontend/src/components/charts/ChartCard.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { getInstanceByDom } from 'echarts/core';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectChartControls } from '../../test/charts';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { ChartCard, type ChartCardProps } from './ChartCard';
import { querySpec, type QueryResult, type QuerySpec } from './explore';

function result(spec: QuerySpec): QueryResult {
  const dim = spec.group_by[0] ?? 'year';
  return {
    columns: [
      { key: dim, label: dim, type: 'string' },
      { key: 'value', label: 'Value', type: 'number' },
      { key: 'n', label: 'n', type: 'int' },
    ],
    rows: [
      { [dim]: 'a', value: 1, n: 1 },
      { [dim]: 'b', value: 2, n: 2 },
    ],
    n_rounds: 3,
    truncated: false,
  };
}

function captureExplore(): QuerySpec[] {
  const seen: QuerySpec[] = [];
  server.use(
    http.post('/api/explore', async ({ request }) => {
      const spec = (await request.json()) as QuerySpec;
      seen.push(spec);
      return HttpResponse.json(result(spec));
    }),
  );
  return seen;
}

const BASE: ChartCardProps = {
  title: 'Turnout vs weather',
  spec: querySpec({ metric: 'attendance', group_by: ['condition'] }),
  chartTypes: ['bar', 'line'],
  allowedGroupBy: ['condition', 'temp_band'],
  urlKey: 'turnout',
};

describe('ChartCard', () => {
  it('queries /api/explore with the spec and renders the result in a ChartFrame', async () => {
    const seen = captureExplore();
    renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    const region = screen.getByRole('region', { name: 'Turnout vs weather' });
    expect(within(region).getByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
    expectChartControls(region);
    expect(seen[0]).toEqual(BASE.spec);
  });

  it('merges the global round-type filter unless the card sets its own', async () => {
    const seen = captureExplore();
    renderWithProviders(<ChartCard {...BASE} />, { route: '/?rt=sporting' });
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    expect(seen[0]?.filters.round_types).toEqual(['sporting']);

    const own = querySpec({
      metric: 'attendance',
      group_by: ['condition'],
      filters: { round_types: ['unknown'] },
    });
    renderWithProviders(<ChartCard {...BASE} urlKey="own" spec={own} />, {
      route: '/?rt=sporting',
    });
    expect(await screen.findByText('Round type: Unknown')).toBeInTheDocument();
    expect(seen.at(-1)?.filters.round_types).toEqual(['unknown']);
  });

  it('switches group-by, metric, chart type and best-round-only through URL-backed chips', async () => {
    const seen = captureExplore();
    const { user, router } = renderWithProviders(
      <ChartCard
        {...BASE}
        spec={querySpec({ metric: 'score', group_by: ['condition'] })}
        allowedMetrics={['score', 'adjusted']}
      />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    await user.click(screen.getByRole('button', { name: 'Adjusted score' }));
    await user.click(screen.getByRole('button', { name: 'Line' }));
    await user.click(screen.getByRole('button', { name: 'Best round only' }));
    expect(router.state.location.search).toBe(
      '?turnout.g=temp_band&turnout.m=adjusted&turnout.t=line&turnout.b=1',
    );
    const last = seen.at(-1);
    expect(last?.group_by).toEqual(['temp_band']);
    expect(last?.metric).toBe('adjusted');
    expect(last?.filters.best_round_only).toBe(true);
    const chart = getInstanceByDom(screen.getByRole('img', { name: 'Turnout vs weather' }));
    expect((chart?.getOption() as { series: { type: string }[] }).series[0]?.type).toBe('line');
  });

  it('keeps drawing the previous result while a new grouping loads', async () => {
    let calls = 0;
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('/api/explore', async ({ request }) => {
        calls += 1;
        const spec = (await request.json()) as QuerySpec;
        if (calls > 1) await held; // the second (temperature) answer waits for release()
        return HttpResponse.json(result(spec));
      }),
    );
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    // The condition-grouped result is still on screen, drawn with its own grouping.
    expect(screen.getByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'condition',
      'Value',
      'n',
    ]);
    release();
    expect(await screen.findByRole('columnheader', { name: 'temp_band' })).toBeInTheDocument();
  });

  it('drills by the grouping on screen while a new grouping loads', async () => {
    let calls = 0;
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('/api/explore', async ({ request }) => {
        calls += 1;
        const spec = (await request.json()) as QuerySpec;
        if (calls > 1) await held;
        return HttpResponse.json(result(spec));
      }),
    );
    const { user, router } = renderWithProviders(
      <ChartCard {...BASE} drill={(row) => `/x?c=${String(row.condition)}`} />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    // Still the condition-grouped chart: bar 'b' is the row whose condition is 'b'.
    getInstanceByDom(screen.getByRole('img', { name: 'Turnout vs weather' }))?.trigger('click', {
      name: 'b',
      seriesName: 'Value',
    } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe('/x?c=b');
    release();
  });

  it('describes its own filters as chips', async () => {
    captureExplore();
    const spec = querySpec({
      metric: 'score',
      group_by: ['year'],
      filters: {
        date_from: '2025-01-01',
        date_to: '2025-12-31',
        statuses: ['member'],
        gauges: ['unspecified'],
        shooter_ids: [1, 2],
        min_rounds: 5,
        temp_f: [40, 70],
        gust_mph: [0, 10],
        precip_in: [0, 0.02],
      },
    });
    renderWithProviders(
      <ChartCard {...BASE} allowedGroupBy={undefined} chartTypes={['bar']} spec={spec} />,
    );
    for (const text of [
      'From 2025-01-01',
      'To 2025-12-31',
      'Status: member',
      'Gauge: unspecified',
      '2 shooter(s)',
      '≥5 rounds',
      '40–70 °F',
      'Gusts 0–10 mph',
      'Rain 0–0.02 in',
    ]) {
      expect(await screen.findByText(text)).toBeInTheDocument();
    }
    expect(screen.queryByRole('button', { name: 'Bar' })).toBeNull();
  });

  it('shows a loading skeleton, then an empty state when nothing matches', async () => {
    server.use(
      http.post('/api/explore', async () => {
        await delay(20);
        return HttpResponse.json({ columns: [], rows: [], n_rounds: 0, truncated: false });
      }),
    );
    renderWithProviders(<ChartCard {...BASE} />);
    expect(screen.getByRole('status', { name: 'Loading Turnout vs weather' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'No data for these filters' }),
    ).toBeInTheDocument();
  });

  it("shows the server's invalid_query message and retries", async () => {
    let calls = 0;
    server.use(
      http.post('/api/explore', async ({ request }) => {
        calls += 1;
        const spec = (await request.json()) as QuerySpec;
        return calls === 1
          ? HttpResponse.json(
              {
                error: {
                  code: 'invalid_query',
                  message: 'Grouping by station needs the Hit % metric',
                },
              },
              { status: 400 },
            )
          : HttpResponse.json(result(spec));
      }),
    );
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    expect(
      await screen.findByText('Grouping by station needs the Hit % metric'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
  });

  it('drills from a table row link and from a clicked bar', async () => {
    captureExplore();
    const { user, router } = renderWithProviders(
      <ChartCard {...BASE} drill={(row) => `/events?c=${String(row.condition)}`} />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('link', { name: 'a' })).toHaveAttribute('href', '/events?c=a');
    await user.click(screen.getByRole('button', { name: 'Table' }));
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    getInstanceByDom(img)?.trigger('click', { name: 'b', seriesName: 'Value' } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe('/events?c=b');
  });

  it('ignores clicks that match no row', async () => {
    captureExplore();
    const { router } = renderWithProviders(<ChartCard {...BASE} drill={() => '/elsewhere'} />);
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    getInstanceByDom(img)?.trigger('click', { name: 'zzz' } as never);
    expect(router.state.location.pathname).toBe('/');
  });
});
```

- [ ] **Step 14: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/components/charts/ChartCard.test.tsx`
Expected: FAIL — `Failed to resolve import "./ChartCard"`.

- [ ] **Step 15: Implement `ChartCard`**

Create the full contents of `frontend/src/components/charts/ChartCard.tsx`:

```tsx
import type { ECElementEvent } from 'echarts';
import { useNavigate } from 'react-router';
import { ROUND_TYPE_LABELS, useRoundTypes } from '../../lib/roundTypes';
import { boolCodec, enumCodec, useUrlState } from '../../lib/useUrlState';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Chip } from '../ui/Chip';
import { EmptyState } from '../ui/EmptyState';
import { Skeleton } from '../ui/Skeleton';
import { ChartFrame } from './ChartFrame';
import {
  DIM_LABELS,
  METRIC_LABELS,
  buildExploreOption,
  rowForClick,
  toTabular,
  useExplore,
  type Dim,
  type Filters,
  type Metric,
  type QuerySpec,
} from './explore';
import type { ChartType, TabularRow } from './types';

export interface ChartCardProps {
  title: string;
  subtitle?: string | undefined;
  spec: QuerySpec;
  /** Offered chart types; the first is the default. */
  chartTypes: ChartType[];
  /** Choices for the first group-by dim (chips); default: fixed to spec.group_by[0]. */
  allowedGroupBy?: Dim[] | undefined;
  /** Metric choices (chips); default: fixed to spec.metric. */
  allowedMetrics?: Metric[] | undefined;
  urlKey: string;
  /** href for a clicked bar/point or table row. */
  drill?: ((row: TabularRow) => string) | undefined;
}

const CHART_TYPE_LABELS: Record<ChartType, string> = {
  bar: 'Bar',
  line: 'Line',
  heatmap: 'Heatmap',
};

/** Read-only chips describing the card's own filters (the global round type has its own chip). */
function filterLabels(filters: Filters, cardRoundTypes: boolean): string[] {
  const labels: string[] = [];
  if (cardRoundTypes) {
    labels.push(`Round type: ${filters.round_types.map((t) => ROUND_TYPE_LABELS[t]).join(' + ')}`);
  }
  if (filters.date_from) labels.push(`From ${filters.date_from}`);
  if (filters.date_to) labels.push(`To ${filters.date_to}`);
  if (filters.statuses.length) labels.push(`Status: ${filters.statuses.join(', ')}`);
  if (filters.gauges.length) labels.push(`Gauge: ${filters.gauges.join(', ')}`);
  if (filters.shooter_ids.length) labels.push(`${filters.shooter_ids.length} shooter(s)`);
  if (filters.min_rounds > 0) labels.push(`≥${filters.min_rounds} rounds`);
  if (filters.temp_f) labels.push(`${filters.temp_f[0]}–${filters.temp_f[1]} °F`);
  if (filters.gust_mph) labels.push(`Gusts ${filters.gust_mph[0]}–${filters.gust_mph[1]} mph`);
  if (filters.precip_in) labels.push(`Rain ${filters.precip_in[0]}–${filters.precip_in[1]} in`);
  return labels;
}

/** ChartFrame + explore controls over POST /api/explore (C10). All control state lives in the URL. */
export function ChartCard({
  title,
  subtitle,
  spec,
  chartTypes,
  allowedGroupBy,
  allowedMetrics,
  urlKey,
  drill,
}: ChartCardProps) {
  const navigate = useNavigate();
  const [globalRoundTypes] = useRoundTypes();
  const metrics = allowedMetrics ?? [spec.metric];
  const dims = allowedGroupBy ?? (spec.group_by[0] === undefined ? [] : [spec.group_by[0]]);
  const [metric, setMetric] = useUrlState(`${urlKey}.m`, enumCodec(metrics), spec.metric);
  const [primary, setPrimary] = useUrlState<Dim | ''>(
    `${urlKey}.g`,
    enumCodec<Dim | ''>(dims),
    spec.group_by[0] ?? '',
  );
  const [chartType, setChartType] = useUrlState(
    `${urlKey}.t`,
    enumCodec(chartTypes),
    chartTypes[0] ?? 'bar',
  );
  const [bestOnly, setBestOnly] = useUrlState(
    `${urlKey}.b`,
    boolCodec,
    spec.filters.best_round_only,
  );

  const cardRoundTypes = spec.filters.round_types.length > 0;
  const groupBy = [
    ...new Set([primary, ...spec.group_by.slice(1)].filter((d): d is Dim => d !== '')),
  ];
  const effective: QuerySpec = {
    ...spec,
    metric,
    group_by: groupBy,
    filters: {
      ...spec.filters,
      best_round_only: bestOnly,
      round_types: cardRoundTypes ? spec.filters.round_types : globalRoundTypes,
    },
  };
  const query = useExplore(effective);

  const controls = (
    <>
      {metrics.length > 1 &&
        metrics.map((m) => (
          <Chip key={m} selected={m === metric} onClick={() => setMetric(m)}>
            {METRIC_LABELS[m]}
          </Chip>
        ))}
      {dims.length > 1 &&
        dims.map((d) => (
          <Chip key={d} selected={d === primary} onClick={() => setPrimary(d)}>
            By {DIM_LABELS[d].toLowerCase()}
          </Chip>
        ))}
      {chartTypes.length > 1 &&
        chartTypes.map((t) => (
          <Chip key={t} selected={t === chartType} onClick={() => setChartType(t)}>
            {CHART_TYPE_LABELS[t]}
          </Chip>
        ))}
      <Chip selected={bestOnly} onClick={() => setBestOnly(!bestOnly)}>
        Best round only
      </Chip>
      {filterLabels(effective.filters, cardRoundTypes).map((label) => (
        <Chip key={label}>{label}</Chip>
      ))}
    </>
  );

  if (query.isPending) {
    return (
      <Card title={title} subtitle={subtitle}>
        <Skeleton label={`Loading ${title}`} lines={6} />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card title={title} subtitle={subtitle}>
        <EmptyState
          title="Couldn't load this chart"
          description={query.error.message}
          action={<Button onClick={() => void query.refetch()}>Try again</Button>}
        />
      </Card>
    );
  }

  // Render with the spec that produced the data: while a new spec loads the previous result stays.
  const shownGroupBy = query.data.spec.group_by;
  const data = toTabular(query.data.result);
  if (data.rows.length === 0) {
    return (
      <Card title={title} subtitle={subtitle}>
        <div className="mb-3 flex flex-wrap gap-2">{controls}</div>
        <EmptyState
          title="No data for these filters"
          description="Try a wider date range or fewer filters."
        />
      </Card>
    );
  }

  // Match the click against the grouping of the chart on screen, never the one still loading.
  const onClick = (params: ECElementEvent) => {
    const row = drill
      ? rowForClick(
          data,
          shownGroupBy,
          params as { name?: string; seriesName?: string; value?: unknown },
        )
      : undefined;
    if (drill && row) void navigate(drill(row));
  };
  return (
    <ChartFrame
      title={title}
      subtitle={subtitle}
      option={buildExploreOption(data, shownGroupBy, chartType)}
      columns={data.columns}
      rows={data.rows}
      csvName={urlKey}
      ariaLabel={title}
      urlKey={`${urlKey}.v`}
      controls={controls}
      onEvents={drill ? { click: onClick } : undefined}
      rowHref={drill}
    />
  );
}
```

- [ ] **Step 16: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/components/charts/ChartCard.test.tsx`
Expected: PASS — 10 tests.

- [ ] **Step 17: Prove the stale-result guards are load-bearing**

In `frontend/src/components/charts/ChartCard.tsx`, temporarily change
`const shownGroupBy = query.data.spec.group_by;` to `const shownGroupBy = effective.group_by;`.
Run: `cd frontend && pnpm exec vitest run src/components/charts/ChartCard.test.tsx`
Expected: FAIL — 3 failed (`switches group-by, metric, chart type and best-round-only through URL-backed chips`,
`keeps drawing the previous result while a new grouping loads` and `drills by the grouping on screen while a new
grouping loads`, with `Unknown column "temp_band"` in the output). Revert the change.
Then, in `onClick`, temporarily pass `groupBy` instead of `shownGroupBy` to `rowForClick` and run the same command.
Expected: FAIL — 1 failed (`drills by the grouping on screen while a new grouping loads`: the click matches no row, so
the page stays on `/?turnout.g=temp_band`). Revert the change and re-run: PASS — 10 tests.

- [ ] **Step 18: Full suite, coverage, lint, types and format**

Run: `cd frontend && pnpm exec prettier --write src/components/charts src/test/charts.ts`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; coverage ≥90% lines and ≥90% branches overall; `src/components/charts` ≥90% lines
and branches.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings.

- [ ] **Step 19: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/components/charts frontend/src/test/charts.ts
git commit -F - <<'MSG'
feat(frontend): ChartFrame with table, CSV, fullscreen and zoom; ChartCard over /api/explore

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

### Task 7: Explorer backend — `QuerySpec`, engine, frame loader and `POST /api/explore` (master Plan 07 T7)

**Context.** Plan 06 T1–T4 have merged: `analytics/frames.py` (loaders, band functions,
`season_label`, `apply_round_type_filter`), `analytics/cache.py` (`cached_by_data_version` plus the autouse fixture that
clears its memo before each test) and `analytics/classes.py` (`assign_classes`) — Decision D4 lists the exact names and
columns used here. Plan 03 T6 (`fx_session`, the committed-fixtures database) and Plan 04 T1 (`fx_viewer_client`,
role wiring by module name) have merged too. This task implements C9: the pydantic `QuerySpec`/`QueryResult` models,
a pure pandas `run_query(ExplorerFrames, QuerySpec)` tested on hand-built frames (every Metric × Dim combination, plus
filters, sorting, limits, NaN → `null` and every `invalid_query` rule), a `load_explorer_frames(session)` loader cached
per `data_version`, and the route module `api/routes/explore.py`, which `create_app()` discovers and guards with
`require_viewer` (module name `explore`); never edit `app.py`. Semantics the master leaves open are fixed in Decisions
D19–D24. Errors are `DomainError("invalid_query", message)` → 400 `{"error": {"code", "message"}}` (C2); more than two
dims or `limit > 5000` are pydantic 422s. Run every command from the worktree root: backend commands start with
`cd backend && ` (Step 18's schema regeneration with `cd frontend && `), and the commit step starts with
`cd "$(git rev-parse --show-toplevel)"` (agent shells reset the working directory between calls, Decision D28).

**Files:**
- Create: `backend/src/sunday_clays/explorer/__init__.py` (empty), `backend/src/sunday_clays/explorer/spec.py`,
  `backend/src/sunday_clays/explorer/engine.py`, `backend/src/sunday_clays/api/routes/explore.py`
- Test: `backend/tests/unit/explorer/conftest.py`, `backend/tests/unit/explorer/test_explorer_spec.py`,
  `backend/tests/unit/explorer/test_explorer_engine.py`, `backend/tests/unit/explorer/test_explorer_loader.py`,
  `backend/tests/integration/explorer/test_explorer_frames.py`, `backend/tests/integration/api/test_explore_route.py`

**Interfaces:**
- Consumes: Plan 06 (Decision D4) `sunday_clays.analytics.frames` as `fr` (`load_rounds`, `load_events`,
  `load_station_hits`, `load_rating_history`, `temp_band`, `wind_band`, `precip_band`, `season_label`, `SEASONS`,
  `apply_round_type_filter`), `sunday_clays.analytics.classes.assign_classes(history, rounds, as_of)`,
  `sunday_clays.analytics.cache.cached_by_data_version`; Plan 03 `sunday_clays.domain.round_type.RoundType`; Plan 01
  `sunday_clays.domain.errors.DomainError(code, message)`, `sunday_clays.db.get_session`, route discovery (C2);
  fixtures `fx_session` (Plan 03 T6) and `fx_viewer_client` (Plan 04 T1).
- Produces:
  - `explorer/spec.py` (C9): `Metric`, `Agg`, `Dim` (`StrEnum`s with the C9 values), `Filters` (optional fields
    default to `None`, lists to `[]`, `min_rounds` 0, `best_round_only` False), `QuerySpec {metric; agg = avg;
    group_by: list[Dim] (≤2); filters = Filters(); sort = 'key_asc'; limit = 500 (≤5000)}`, `Column {key; label;
    type: 'date' | 'number' | 'string' | 'int'}`, `QueryResult {columns; rows; n_rounds; truncated}`.
  - `explorer/engine.py`: `@dataclass(frozen=True) ExplorerFrames(rounds, station_hits, events)`,
    `run_query(frames: ExplorerFrames, spec: QuerySpec) -> QueryResult`,
    `load_explorer_frames(session: Session) -> ExplorerFrames` (`@cached_by_data_version`), `WEATHER_COLUMNS`,
    `METRIC_LABELS`, `AGG_LABELS`.
  - `api/routes/explore.py`: `router` with `POST /api/explore` (body `QuerySpec`, `response_model=QueryResult`), so the
    generated frontend schema gains `paths['/api/explore']` and the schemas `QuerySpec`, `QueryResult`, `Filters`,
    `Column`, `Metric`, `Dim`, `Agg` (consumed by Task 6).

**Branch:** `task/07-7-explorer-backend` · **Depends on:** Plan 06 T4.

- [ ] **Step 1: Write the failing `QuerySpec` test**

Create the full contents of `backend/tests/unit/explorer/test_explorer_spec.py`:

```python
from typing import Any

import pytest
from pydantic import ValidationError

from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec


def test_minimal_spec_gets_the_documented_defaults() -> None:
    spec = QuerySpec.model_validate({"metric": "score"})
    assert spec.agg is Agg.AVG
    assert spec.group_by == []
    assert spec.sort == "key_asc"
    assert spec.limit == 500
    assert spec.filters == Filters()
    assert spec.filters.date_from is None
    assert spec.filters.temp_f is None
    assert spec.filters.min_rounds == 0
    assert spec.filters.best_round_only is False


def test_group_by_allows_at_most_two_dims() -> None:
    assert QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR, Dim.GAUGE]).group_by == [
        Dim.YEAR,
        Dim.GAUGE,
    ]
    with pytest.raises(ValidationError, match="at most 2"):
        QuerySpec.model_validate({"metric": "score", "group_by": ["year", "gauge", "status"]})


def test_limit_is_capped_at_5000() -> None:
    assert QuerySpec(metric=Metric.SCORE, limit=5000).limit == 5000
    with pytest.raises(ValidationError):
        QuerySpec(metric=Metric.SCORE, limit=5001)


@pytest.mark.parametrize(
    "payload",
    [
        {"metric": "handicap"},
        {"metric": "score", "agg": "mode"},
        {"metric": "score", "group_by": ["weekday"]},
        {"metric": "score", "sort": "random"},
        {"metric": "score", "filters": {"round_types": ["trap"]}},
        {"metric": "score", "filters": {"temp_f": [40, 50, 60]}},
    ],
)
def test_unknown_values_are_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        QuerySpec.model_validate(payload)


def test_weather_ranges_are_numeric_pairs() -> None:
    assert Filters.model_validate({"temp_f": [40, 70]}).temp_f == (40.0, 70.0)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/unit/explorer/test_explorer_spec.py -q`
Expected: FAIL — collection error `ModuleNotFoundError: No module named 'sunday_clays.explorer'`.

- [ ] **Step 3: Implement the C9 models**

Create `backend/src/sunday_clays/explorer/__init__.py` as an empty file.

Create the full contents of `backend/src/sunday_clays/explorer/spec.py`:

```python
"""Explorer QuerySpec (C9): the validated JSON query the Explorer and every ChartCard send."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from sunday_clays.domain.round_type import RoundType


class Metric(StrEnum):
    SCORE = "score"
    ADJUSTED = "adjusted"
    RESIDUAL = "residual"
    RATING = "rating"
    ROUNDS = "rounds"
    SHOOTERS = "shooters"
    ATTENDANCE = "attendance"
    WINS = "wins"
    HIT_PCT = "hit_pct"


class Agg(StrEnum):
    AVG = "avg"
    MEDIAN = "median"
    MAX = "max"
    MIN = "min"
    SUM = "sum"
    COUNT = "count"
    P90 = "p90"
    STDEV = "stdev"


class Dim(StrEnum):
    SHOOTER = "shooter"
    EVENT = "event"
    MONTH = "month"
    YEAR = "year"
    SEASON = "season"
    MONTH_OF_YEAR = "month_of_year"
    ROUND_TYPE = "round_type"
    GAUGE = "gauge"
    STATUS = "status"
    TEMP_BAND = "temp_band"
    WIND_BAND = "wind_band"
    PRECIP_BAND = "precip_band"
    CONDITION = "condition"
    STATION = "station"
    CLASS = "class"


class Filters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    shooter_ids: list[int] = []
    round_types: list[RoundType] = []
    statuses: list[str] = []
    gauges: list[str] = []
    temp_f: tuple[float, float] | None = None
    gust_mph: tuple[float, float] | None = None
    precip_in: tuple[float, float] | None = None
    min_rounds: int = 0
    best_round_only: bool = False


class QuerySpec(BaseModel):
    metric: Metric
    agg: Agg = Agg.AVG
    group_by: list[Dim] = Field(default=[], max_length=2)
    filters: Filters = Filters()
    sort: Literal["value_desc", "value_asc", "key_asc", "key_desc"] = "key_asc"
    limit: int = Field(default=500, le=5000)


class Column(BaseModel):
    key: str
    label: str
    type: Literal["date", "number", "string", "int"]


class QueryResult(BaseModel):
    columns: list[Column]
    rows: list[dict[str, str | int | float | None]]
    n_rounds: int
    truncated: bool
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd backend && uv run pytest tests/unit/explorer/test_explorer_spec.py -q`
Expected: PASS — 10 passed.

- [ ] **Step 5: Write the synthetic frames and the failing engine test**

Create the full contents of `backend/tests/unit/explorer/conftest.py`:

```python
"""Synthetic ExplorerFrames for the pure run_query tests (no DB): the `frames` fixture.

Three held events with rounds, one attendance-only event, station data on 2025-07-06 only.
Every expected value in the tests is derived by hand from the literals below.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from sunday_clays.explorer.engine import ExplorerFrames

NAN = np.nan
E1, E2, E3, E4 = date(2024, 12, 1), date(2025, 3, 2), date(2025, 7, 6), date(2025, 11, 2)

# event_date, round_type, head_count, temp_f, gust_mph, precip_in, condition,
# temp_band, wind_band, precip_band
EVENTS = [
    (E1, "unknown", 3, 38.0, 8.0, 0.0, "clear", "<40", "<10", "dry"),
    (E2, "sporting", 4, 50.0, 15.0, 0.05, "rain", "40-55", "10-20", "wet"),
    (E3, "super_sporting", 2, 90.0, 22.0, 0.0, "windy", "85+", "20+", "dry"),
    (E4, "unknown", 12, NAN, NAN, NAN, None, None, None, None),
]
SHOOTERS = {
    1: ("Able, Ann", "member", "12 Gauge"),
    2: ("Baker, Bob", "guest", "unspecified"),
    3: ("Slocum, Cy", "deceased", "Sub-Gauge"),
}
# round_id, event_date, shooter_id, ordinal, score, adjusted, residual, mu_after,
# event_rank, is_best_round, klass
ROUNDS = [
    (1, E1, 1, 1, 40, 4.0, 2.0, 36.0, 1, True, "A"),
    (2, E1, 2, 1, 30, -6.0, -3.0, 29.0, 3, True, None),
    (3, E1, 3, 1, 36, 0.0, 1.0, 33.0, 2, True, "B"),
    (4, E2, 1, 1, 44, 4.5, 3.0, 37.0, 1, True, "A"),
    (5, E2, 1, 2, 38, -1.5, -3.0, 37.0, NAN, False, "A"),
    (6, E2, 2, 1, 32, -7.5, -1.0, 29.5, 3, True, None),
    (7, E2, 3, 1, 41, 1.5, 2.0, 34.0, 2, True, "B"),
    (8, E3, 1, 1, 39, -3.0, -2.0, 36.5, 2, True, "A"),
    (9, E3, 3, 1, 45, 3.0, 4.0, 35.0, 1, True, "A"),
]
# event_date, station_no, round_id, hits, target_count (the last entry is an unmatched name)
STATION_HITS = [
    (E3, 4, 8, 5, 7),
    (E3, 10, 8, 6, 8),
    (E3, 4, 9, 7, 7),
    (E3, 10, 9, 8, 8),
    (E3, 4, NAN, 3, 7),
]


def make_frames() -> ExplorerFrames:
    weather = {e[0]: e for e in EVENTS}
    rounds = pd.DataFrame(
        [
            {
                "round_id": rid,
                "event_date": d,
                "shooter_id": sid,
                "name_key": SHOOTERS[sid][0].lower(),
                "display_name": SHOOTERS[sid][0],
                "ordinal": ordinal,
                "score": score,
                "gauge_class": None if SHOOTERS[sid][2] == "unspecified" else SHOOTERS[sid][2],
                "gauge": SHOOTERS[sid][2],
                "status": SHOOTERS[sid][1],
                "shooter_status": SHOOTERS[sid][1],
                "round_type": weather[d][1],
                "field_median": NAN,
                "adjusted": adjusted,
                "event_rank": rank,
                "is_best_round": best,
                "percentile": NAN,
                "expected": NAN,
                "residual": residual,
                "mu_before": NAN,
                "mu_after": mu_after,
                "temp_f": weather[d][3],
                "apparent_f": NAN,
                "precip_in": weather[d][5],
                "wind_mph": NAN,
                "gust_mph": weather[d][4],
                "wind_dir_deg": NAN,
                "cloud_pct": NAN,
                "condition": weather[d][6],
                "temp_band": weather[d][7],
                "wind_band": weather[d][8],
                "precip_band": weather[d][9],
                "klass": klass,
            }
            for (
                rid,
                d,
                sid,
                ordinal,
                score,
                adjusted,
                residual,
                mu_after,
                rank,
                best,
                klass,
            ) in ROUNDS
        ]
    )
    events = pd.DataFrame(
        EVENTS,
        columns=[
            "event_date",
            "round_type",
            "head_count",
            "temp_f",
            "gust_mph",
            "precip_in",
            "condition",
            "temp_band",
            "wind_band",
            "precip_band",
        ],
    )
    station_hits = pd.DataFrame(
        STATION_HITS, columns=["event_date", "station_no", "round_id", "hits", "target_count"]
    )
    return ExplorerFrames(rounds=rounds, station_hits=station_hits, events=events)


@pytest.fixture
def frames() -> ExplorerFrames:
    return make_frames()
```

Create the full contents of `backend/tests/unit/explorer/test_explorer_engine.py`:

```python
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.round_type import RoundType
from sunday_clays.explorer.engine import ExplorerFrames, run_query
from sunday_clays.explorer.spec import Agg, Dim, Filters, Metric, QuerySpec

ROUND_KEYS: dict[Dim, list[object]] = {
    Dim.SHOOTER: [1, 2, 3],
    Dim.EVENT: ["2024-12-01", "2025-03-02", "2025-07-06"],
    Dim.MONTH: ["2024-12", "2025-03", "2025-07"],
    Dim.YEAR: [2024, 2025],
    Dim.SEASON: ["winter", "spring", "summer"],
    Dim.MONTH_OF_YEAR: [3, 7, 12],
    Dim.ROUND_TYPE: ["sporting", "super_sporting", "unknown"],
    Dim.GAUGE: ["12 Gauge", "Sub-Gauge", "unspecified"],
    Dim.STATUS: ["deceased", "guest", "member"],
    Dim.TEMP_BAND: ["<40", "40-55", "85+"],
    Dim.WIND_BAND: ["<10", "10-20", "20+"],
    Dim.PRECIP_BAND: ["dry", "wet"],
    Dim.CONDITION: ["clear", "rain", "windy"],
    Dim.CLASS: ["A", "B", None],
}
STATION_KEYS: dict[Dim, list[object]] = {
    Dim.SHOOTER: [1, 3],
    Dim.EVENT: ["2025-07-06"],
    Dim.MONTH: ["2025-07"],
    Dim.YEAR: [2025],
    Dim.SEASON: ["summer"],
    Dim.MONTH_OF_YEAR: [7],
    Dim.ROUND_TYPE: ["super_sporting"],
    Dim.GAUGE: ["12 Gauge", "Sub-Gauge"],
    Dim.STATUS: ["deceased", "member"],
    Dim.TEMP_BAND: ["85+"],
    Dim.WIND_BAND: ["20+"],
    Dim.PRECIP_BAND: ["dry"],
    Dim.CONDITION: ["windy"],
    Dim.STATION: [4, 10],
    Dim.CLASS: ["A"],
}
EVENT_KEYS: dict[Dim, list[object]] = {
    Dim.EVENT: ["2024-12-01", "2025-03-02", "2025-07-06", "2025-11-02"],
    Dim.MONTH: ["2024-12", "2025-03", "2025-07", "2025-11"],
    Dim.YEAR: [2024, 2025],
    Dim.SEASON: ["winter", "spring", "summer", "fall"],
    Dim.MONTH_OF_YEAR: [3, 7, 11, 12],
    Dim.ROUND_TYPE: ["sporting", "super_sporting", "unknown"],
    Dim.TEMP_BAND: ["<40", "40-55", "85+", None],
    Dim.WIND_BAND: ["<10", "10-20", "20+", None],
    Dim.PRECIP_BAND: ["dry", "wet", None],
    Dim.CONDITION: ["clear", "rain", "windy", None],
}
ROUND_METRICS = [
    Metric.SCORE,
    Metric.ADJUSTED,
    Metric.RESIDUAL,
    Metric.RATING,
    Metric.ROUNDS,
    Metric.SHOOTERS,
    Metric.WINS,
]


def _expected_keys(metric: Metric, dim: Dim) -> list[object] | None:
    """Hand-listed group keys, or None when the combination must be rejected."""
    if metric is Metric.HIT_PCT:
        return STATION_KEYS[dim]
    if metric is Metric.ATTENDANCE:
        return EVENT_KEYS.get(dim)
    return ROUND_KEYS.get(dim)


def _key_column(dim: Dim) -> str:
    return {Dim.SHOOTER: "shooter_id", Dim.CLASS: "class", Dim.STATION: "station"}.get(
        dim, dim.value
    )


def _values(result_rows: Sequence[Mapping[str, object]], key: str) -> dict[object, object]:
    return {row[key]: row["value"] for row in result_rows}


@pytest.mark.parametrize("metric", list(Metric))
@pytest.mark.parametrize("dim", list(Dim))
def test_every_metric_dim_combination(metric: Metric, dim: Dim, frames: ExplorerFrames) -> None:
    spec = QuerySpec(metric=metric, group_by=[dim])
    expected = _expected_keys(metric, dim)
    if expected is None:
        with pytest.raises(DomainError) as excinfo:
            run_query(frames, spec)
        assert excinfo.value.code == "invalid_query"
        return
    result = run_query(frames, spec)
    assert [row[_key_column(dim)] for row in result.rows] == expected
    assert [c.key for c in result.columns][-2:] == ["value", "n"]
    json.loads(result.model_dump_json())  # every combination is JSON-serializable


def test_combination_count_matches_contract() -> None:
    valid = [(m, d) for m in Metric for d in Dim if _expected_keys(m, d) is not None]
    assert len(valid) == 7 * 14 + 15 + 10


def test_score_aggregations_overall(frames: ExplorerFrames) -> None:
    got = {
        agg: run_query(frames, QuerySpec(metric=Metric.SCORE, agg=agg)).rows[0]["value"]
        for agg in Agg
    }
    # scores: 40 30 36 44 38 32 41 39 45 -> sorted 30 32 36 38 39 40 41 44 45
    assert got[Agg.AVG] == pytest.approx(345 / 9)
    assert got[Agg.MEDIAN] == 39
    assert got[Agg.MAX] == 45
    assert got[Agg.MIN] == 30
    assert got[Agg.SUM] == 345
    assert got[Agg.COUNT] == 9
    assert got[Agg.P90] == pytest.approx(44.2)
    assert got[Agg.STDEV] == pytest.approx((202 / 8) ** 0.5)


def test_score_avg_by_year(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR]))
    assert _values(result.rows, "year") == {
        2024: pytest.approx(106 / 3),
        2025: pytest.approx(239 / 6),
    }
    assert [(r["year"], r["n"]) for r in result.rows] == [(2024, 3), (2025, 6)]
    assert result.n_rounds == 9
    assert result.columns[1].label == "Avg score"


def test_adjusted_and_residual_use_their_columns(frames: ExplorerFrames) -> None:
    adjusted = run_query(frames, QuerySpec(metric=Metric.ADJUSTED, group_by=[Dim.EVENT]))
    assert _values(adjusted.rows, "event") == {
        "2024-12-01": pytest.approx(-2 / 3),
        "2025-03-02": pytest.approx(-3 / 4),
        "2025-07-06": pytest.approx(0.0),
    }
    residual = run_query(frames, QuerySpec(metric=Metric.RESIDUAL, group_by=[Dim.SHOOTER]))
    assert _values(residual.rows, "shooter_id") == {
        1: pytest.approx(0.0),
        2: pytest.approx(-2.0),
        3: pytest.approx(7 / 3),
    }


def test_rating_counts_one_best_round_per_shooter_event(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.RATING, group_by=[Dim.SHOOTER]))
    # Able: 36.0 (E1), 37.0 (E2 best round only), 36.5 (E3); the E2 second round is not counted
    assert _values(result.rows, "shooter_id") == {
        1: pytest.approx(36.5),
        2: pytest.approx(29.25),
        3: pytest.approx(34.0),
    }
    assert result.rows[0]["shooter"] == "Able, Ann"


def test_counting_metrics_ignore_agg(frames: ExplorerFrames) -> None:
    rounds = run_query(frames, QuerySpec(metric=Metric.ROUNDS, agg=Agg.MAX, group_by=[Dim.SHOOTER]))
    assert _values(rounds.rows, "shooter_id") == {1: 4, 2: 2, 3: 3}
    assert rounds.columns[-2].type == "int"
    assert rounds.columns[-2].label == "Rounds"
    shooters = run_query(frames, QuerySpec(metric=Metric.SHOOTERS, group_by=[Dim.EVENT]))
    assert _values(shooters.rows, "event") == {"2024-12-01": 3, "2025-03-02": 3, "2025-07-06": 2}
    wins = run_query(frames, QuerySpec(metric=Metric.WINS, group_by=[Dim.SHOOTER]))
    assert _values(wins.rows, "shooter_id") == {1: 2, 2: 0, 3: 1}


def test_hit_pct_pools_targets_and_ignores_unlinked_entries(frames: ExplorerFrames) -> None:
    by_station = run_query(frames, QuerySpec(metric=Metric.HIT_PCT, group_by=[Dim.STATION]))
    assert _values(by_station.rows, "station") == {
        4: pytest.approx(100 * 12 / 14),
        10: pytest.approx(100 * 14 / 16),
    }
    overall = run_query(frames, QuerySpec(metric=Metric.HIT_PCT))
    assert overall.rows[0]["value"] == pytest.approx(100 * 26 / 30)
    assert overall.rows[0]["n"] == 4
    assert overall.n_rounds == 2


def test_attendance_by_year_uses_event_head_counts(frames: ExplorerFrames) -> None:
    avg = run_query(frames, QuerySpec(metric=Metric.ATTENDANCE, group_by=[Dim.YEAR]))
    assert _values(avg.rows, "year") == {2024: 3.0, 2025: 6.0}
    assert avg.n_rounds == 0
    total = run_query(frames, QuerySpec(metric=Metric.ATTENDANCE, agg=Agg.SUM, group_by=[Dim.YEAR]))
    assert _values(total.rows, "year") == {2024: 3.0, 2025: 18.0}
    assert total.columns[-2].label == "Total attendance"


def test_group_by_gauge_keeps_unspecified(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.GAUGE]))
    assert result.rows == [
        {"gauge": "12 Gauge", "value": 4, "n": 4},
        {"gauge": "Sub-Gauge", "value": 3, "n": 3},
        {"gauge": "unspecified", "value": 2, "n": 2},
    ]


def test_dim_season_december_is_winter(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.SEASON]))
    # the only winter rounds are the three shot on 2024-12-01
    assert result.rows[0] == {"season": "winter", "value": 3, "n": 3}


def test_two_dims_group_by_combination(frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.YEAR, Dim.STATUS]))
    assert [(r["year"], r["status"], r["value"]) for r in result.rows] == [
        (2024, "deceased", 1),
        (2024, "guest", 1),
        (2024, "member", 1),
        (2025, "deceased", 2),
        (2025, "guest", 1),
        (2025, "member", 3),
    ]


@pytest.mark.parametrize(
    ("filters", "expected_rounds"),
    [
        (Filters(date_from=date(2025, 1, 1)), 6),
        (Filters(date_to=date(2025, 3, 2)), 7),
        (Filters(shooter_ids=[3]), 3),
        (Filters(round_types=[RoundType.SPORTING]), 4),
        (Filters(statuses=["guest"]), 2),
        (Filters(gauges=["unspecified"]), 2),
        (Filters(temp_f=(45.0, 95.0)), 6),
        (Filters(gust_mph=(0.0, 10.0)), 3),
        (Filters(precip_in=(0.02, 1.0)), 4),
        (Filters(min_rounds=3), 7),
        (Filters(best_round_only=True), 8),
    ],
)
def test_round_filters(filters: Filters, expected_rounds: int, frames: ExplorerFrames) -> None:
    result = run_query(frames, QuerySpec(metric=Metric.ROUNDS, filters=filters))
    assert result.rows[0]["value"] == expected_rounds
    assert result.n_rounds == expected_rounds


def test_event_filters_apply_to_attendance(frames: ExplorerFrames) -> None:
    by_temp = run_query(
        frames, QuerySpec(metric=Metric.ATTENDANCE, agg=Agg.SUM, filters=Filters(temp_f=(0, 60)))
    )
    assert by_temp.rows[0]["value"] == 7.0  # E1 + E2; the weatherless E4 never matches a range
    by_type = run_query(
        frames,
        QuerySpec(
            metric=Metric.ATTENDANCE,
            agg=Agg.SUM,
            filters=Filters(round_types=[RoundType.UNKNOWN], date_from=date(2025, 1, 1)),
        ),
    )
    assert by_type.rows[0]["value"] == 12.0


def test_sorting_and_limit(frames: ExplorerFrames) -> None:
    desc = run_query(
        frames,
        QuerySpec(metric=Metric.SCORE, group_by=[Dim.SHOOTER], sort="value_desc", limit=2),
    )
    assert [r["shooter_id"] for r in desc.rows] == [3, 1]
    assert desc.truncated is True
    asc = run_query(
        frames, QuerySpec(metric=Metric.SCORE, group_by=[Dim.SHOOTER], sort="value_asc")
    )
    assert [r["shooter_id"] for r in asc.rows] == [2, 1, 3]
    assert asc.truncated is False
    key_desc = run_query(
        frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.YEAR], sort="key_desc")
    )
    assert [r["year"] for r in key_desc.rows] == [2025, 2024]


def test_missing_values_serialize_as_null_and_sort_last(frames: ExplorerFrames) -> None:
    rounds = frames.rounds.copy()
    rounds.loc[rounds["event_date"] == date(2024, 12, 1), "adjusted"] = np.nan
    result = run_query(
        replace(frames, rounds=rounds),
        QuerySpec(metric=Metric.ADJUSTED, group_by=[Dim.EVENT], sort="value_desc"),
    )
    assert result.rows[-1] == {"event": "2024-12-01", "value": None, "n": 0}
    assert json.loads(result.model_dump_json())["rows"][-1]["value"] is None
    single = run_query(
        frames, QuerySpec(metric=Metric.SCORE, agg=Agg.STDEV, group_by=[Dim.SHOOTER])
    )
    assert all(row["value"] is not None for row in single.rows)
    one_round = run_query(
        frames,
        QuerySpec(
            metric=Metric.SCORE,
            agg=Agg.STDEV,
            group_by=[Dim.SHOOTER],
            filters=Filters(date_to=date(2024, 12, 1)),
        ),
    )
    assert [row["value"] for row in one_round.rows] == [None, None, None]


def test_empty_result_after_filters(frames: ExplorerFrames) -> None:
    result = run_query(
        frames,
        QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR], filters=Filters(shooter_ids=[99])),
    )
    assert result.rows == []
    assert result.n_rounds == 0
    assert result.truncated is False


@pytest.mark.parametrize(
    ("spec", "fragment"),
    [
        (QuerySpec(metric=Metric.SCORE, group_by=[Dim.YEAR, Dim.YEAR]), "only once"),
        (QuerySpec(metric=Metric.SCORE, limit=0), "limit"),
        (QuerySpec(metric=Metric.SCORE, group_by=[Dim.STATION]), "Hit %"),
        (QuerySpec(metric=Metric.ATTENDANCE, group_by=[Dim.GAUGE]), "gauge"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(shooter_ids=[1])), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(statuses=["member"])), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(gauges=["SxS"])), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(min_rounds=5)), "filters"),
        (QuerySpec(metric=Metric.ATTENDANCE, filters=Filters(best_round_only=True)), "filters"),
    ],
)
def test_invalid_queries_are_rejected(
    spec: QuerySpec, fragment: str, frames: ExplorerFrames
) -> None:
    with pytest.raises(DomainError) as excinfo:
        run_query(frames, spec)
    assert excinfo.value.code == "invalid_query"
    assert fragment in str(excinfo.value)


def test_hit_pct_without_station_data_is_rejected(frames: ExplorerFrames) -> None:
    unlinked = frames.station_hits.assign(round_id=np.nan)
    with pytest.raises(DomainError, match="station data"):
        run_query(replace(frames, station_hits=unlinked), QuerySpec(metric=Metric.HIT_PCT))
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/unit/explorer/test_explorer_engine.py -q`
Expected: FAIL — collection error `ModuleNotFoundError: No module named 'sunday_clays.explorer.engine'` (raised while
importing `conftest.py`).

- [ ] **Step 7: Implement the pure query engine**

Create the full contents of `backend/src/sunday_clays/explorer/engine.py` (the loader follows in Step 11):

```python
"""Explorer engine (C9): a cached frame loader plus a pure pandas query runner."""

import math
import numbers
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

import pandas as pd

from sunday_clays.analytics import frames as fr
from sunday_clays.domain.errors import DomainError
from sunday_clays.explorer.spec import (
    Agg,
    Column,
    Dim,
    Filters,
    Metric,
    QueryResult,
    QuerySpec,
)

ColumnType = Literal["date", "number", "string", "int"]
Cell = str | int | float | None
Reducer = str | Callable[[pd.Series], float]


@dataclass(frozen=True)
class ExplorerFrames:
    rounds: pd.DataFrame  # C7 load_rounds columns + temp_band, wind_band, precip_band, klass
    station_hits: pd.DataFrame  # C7 load_station_hits columns (incl. target_count)
    events: pd.DataFrame  # event_date, round_type, head_count, WEATHER_COLUMNS + the three bands


METRIC_LABELS: Final[dict[Metric, str]] = {
    Metric.SCORE: "Score",
    Metric.ADJUSTED: "Adjusted score",
    Metric.RESIDUAL: "Residual",
    Metric.RATING: "Rating",
    Metric.ROUNDS: "Rounds",
    Metric.SHOOTERS: "Shooters",
    Metric.ATTENDANCE: "Attendance",
    Metric.WINS: "Wins",
    Metric.HIT_PCT: "Hit %",
}
AGG_LABELS: Final[dict[Agg, str]] = {
    Agg.AVG: "Avg",
    Agg.MEDIAN: "Median",
    Agg.MAX: "Max",
    Agg.MIN: "Min",
    Agg.SUM: "Total",
    Agg.COUNT: "Count of",
    Agg.P90: "P90",
    Agg.STDEV: "Std dev of",
}
DIM_COLUMNS: Final[dict[Dim, tuple[Column, ...]]] = {
    Dim.SHOOTER: (
        Column(key="shooter_id", label="Shooter ID", type="int"),
        Column(key="shooter", label="Shooter", type="string"),
    ),
    Dim.EVENT: (Column(key="event", label="Event", type="date"),),
    Dim.MONTH: (Column(key="month", label="Month", type="string"),),
    Dim.YEAR: (Column(key="year", label="Year", type="int"),),
    Dim.SEASON: (Column(key="season", label="Season", type="string"),),
    Dim.MONTH_OF_YEAR: (Column(key="month_of_year", label="Month of year", type="int"),),
    Dim.ROUND_TYPE: (Column(key="round_type", label="Round type", type="string"),),
    Dim.GAUGE: (Column(key="gauge", label="Gauge", type="string"),),
    Dim.STATUS: (Column(key="status", label="Status", type="string"),),
    Dim.TEMP_BAND: (Column(key="temp_band", label="Temperature", type="string"),),
    Dim.WIND_BAND: (Column(key="wind_band", label="Wind", type="string"),),
    Dim.PRECIP_BAND: (Column(key="precip_band", label="Precipitation", type="string"),),
    Dim.CONDITION: (Column(key="condition", label="Conditions", type="string"),),
    Dim.STATION: (Column(key="station", label="Station", type="int"),),
    Dim.CLASS: (Column(key="class", label="Class", type="string"),),
}
# Metrics whose per-unit values are combined with spec.agg; the others are fixed counts/rates.
AGGREGATED: Final[dict[Metric, str]] = {
    Metric.SCORE: "score",
    Metric.ADJUSTED: "adjusted",
    Metric.RESIDUAL: "residual",
    Metric.RATING: "mu_after",
    Metric.ATTENDANCE: "head_count",
}
AGG_FUNCS: Final[dict[Agg, Reducer]] = {
    Agg.AVG: "mean",
    Agg.MEDIAN: "median",
    Agg.MAX: "max",
    Agg.MIN: "min",
    Agg.SUM: lambda s: float(s.sum(min_count=1)),
    Agg.COUNT: "count",
    Agg.P90: lambda s: float(s.quantile(0.9)),
    Agg.STDEV: "std",
}
FIXED_REDUCERS: Final[dict[Metric, Reducer]] = {
    Metric.ROUNDS: "sum",
    Metric.SHOOTERS: "nunique",
    Metric.WINS: "sum",
    Metric.HIT_PCT: "sum",
}
INT_METRICS: Final = frozenset({Metric.ROUNDS, Metric.SHOOTERS, Metric.WINS})
EVENT_DIMS: Final = frozenset(
    {
        Dim.EVENT,
        Dim.MONTH,
        Dim.YEAR,
        Dim.SEASON,
        Dim.MONTH_OF_YEAR,
        Dim.ROUND_TYPE,
        Dim.TEMP_BAND,
        Dim.WIND_BAND,
        Dim.PRECIP_BAND,
        Dim.CONDITION,
    }
)
# C7 sort order winter, spring, summer, fall, from Plan 06's single definition (frames.SEASONS).
SEASON_ORDER: Final[dict[str, int]] = {season: i for i, season in enumerate(fr.SEASONS)}
BAND_SOURCES: Final[dict[Dim, str]] = {
    Dim.TEMP_BAND: "temp_f",
    Dim.WIND_BAND: "gust_mph",
    Dim.PRECIP_BAND: "precip_in",
}
PLAIN_DIMS: Final[dict[Dim, str]] = {
    Dim.ROUND_TYPE: "round_type",
    Dim.GAUGE: "gauge",
    Dim.STATUS: "shooter_status",
    Dim.CONDITION: "condition",
    Dim.STATION: "station_no",
    Dim.CLASS: "klass",
}


def _invalid(message: str) -> DomainError:
    return DomainError("invalid_query", message)


def _validate(frames: ExplorerFrames, spec: QuerySpec) -> None:
    dims = spec.group_by
    if len(set(dims)) != len(dims):
        raise _invalid("Each group-by dimension can be used only once")
    if spec.limit < 1:
        raise _invalid("limit must be at least 1")
    if Dim.STATION in dims and spec.metric is not Metric.HIT_PCT:
        raise _invalid("Grouping by station needs the Hit % metric")
    if spec.metric is Metric.HIT_PCT and not frames.station_hits["round_id"].notna().any():
        raise _invalid("Hit % needs station data, and no station sheet has been imported")
    if spec.metric is Metric.ATTENDANCE:
        bad = [d for d in dims if d not in EVENT_DIMS]
        if bad:
            label = DIM_COLUMNS[bad[0]][-1].label.lower()
            raise _invalid(f"Attendance is an event total and cannot be grouped by {label}")
        f = spec.filters
        if f.shooter_ids or f.statuses or f.gauges or f.min_rounds > 0 or f.best_round_only:
            raise _invalid(
                "Attendance is an event total; shooter, status, gauge, minimum-rounds and "
                "best-round filters do not apply"
            )


def _common_mask(df: pd.DataFrame, f: Filters) -> "pd.Series[bool]":
    ts = pd.to_datetime(df["event_date"])
    mask = pd.Series(True, index=df.index)
    if f.date_from is not None:
        mask &= ts >= pd.Timestamp(f.date_from)
    if f.date_to is not None:
        mask &= ts <= pd.Timestamp(f.date_to)
    for column, bounds in (
        ("temp_f", f.temp_f),
        ("gust_mph", f.gust_mph),
        ("precip_in", f.precip_in),
    ):
        if bounds is not None:
            mask &= df[column].between(bounds[0], bounds[1])
    return mask


def _filter_events(events: pd.DataFrame, f: Filters) -> pd.DataFrame:
    return fr.apply_round_type_filter(events[_common_mask(events, f)], f.round_types)


def _filter_rounds(rounds: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = _common_mask(rounds, f)
    if f.shooter_ids:
        mask &= rounds["shooter_id"].isin(f.shooter_ids)
    if f.statuses:
        mask &= rounds["shooter_status"].isin(f.statuses)
    if f.gauges:
        mask &= rounds["gauge"].isin(f.gauges)
    out = fr.apply_round_type_filter(rounds[mask], f.round_types)
    if f.min_rounds > 0:
        per_shooter = out.groupby("shooter_id")["round_id"].transform("size")
        out = out[per_shooter >= f.min_rounds]
    if f.best_round_only:
        out = out[out["is_best_round"].eq(True)]
    return out


def _keys(df: pd.DataFrame, dims: Sequence[Dim]) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Output key columns plus one hidden sort column per dim, aligned with df's index."""
    ts = pd.to_datetime(df["event_date"])
    out = pd.DataFrame(index=df.index)
    key_cols: list[str] = []
    sort_cols: list[str] = []
    for i, dim in enumerate(dims):
        sort = f"_sort{i}"
        if dim is Dim.SHOOTER:
            out["shooter_id"] = df["shooter_id"].astype("int64")
            out["shooter"] = df["display_name"].astype(str)
            out[sort] = out["shooter"].str.casefold()
        elif dim is Dim.EVENT:
            out["event"] = ts.dt.strftime("%Y-%m-%d")
            out[sort] = out["event"]
        elif dim is Dim.MONTH:
            out["month"] = ts.dt.strftime("%Y-%m")
            out[sort] = out["month"]
        elif dim is Dim.YEAR:
            out["year"] = ts.dt.year.astype("int64")
            out[sort] = out["year"]
        elif dim is Dim.SEASON:
            out["season"] = ts.dt.date.map(fr.season_label)
            out[sort] = out["season"].map(SEASON_ORDER)
        elif dim is Dim.MONTH_OF_YEAR:
            out["month_of_year"] = ts.dt.month.astype("int64")
            out[sort] = out["month_of_year"]
        elif dim in BAND_SOURCES:
            out[dim.value] = df[dim.value]
            out[sort] = df[BAND_SOURCES[dim]].astype(float)
        else:
            key = DIM_COLUMNS[dim][-1].key
            out[key] = df[PLAIN_DIMS[dim]]
            out[sort] = out[key]
        key_cols.extend(c.key for c in DIM_COLUMNS[dim])
        sort_cols.append(sort)
    return out, key_cols, sort_cols


def _units(
    frames: ExplorerFrames, spec: QuerySpec
) -> tuple[pd.DataFrame, list[str], list[str], int]:
    """One row per counted unit (round, shooter-event, station entry or event) with a 'value'."""
    metric = spec.metric
    if metric is Metric.ATTENDANCE:
        events = _filter_events(frames.events, spec.filters)
        units, key_cols, sort_cols = _keys(events, spec.group_by)
        units["value"] = events["head_count"].astype(float)
        return units, key_cols, sort_cols, 0
    rounds = _filter_rounds(frames.rounds, spec.filters)
    if metric is Metric.HIT_PCT:
        hits = frames.station_hits
        hits = hits[hits["round_id"].notna()].astype({"round_id": "int64"})
        joined = hits[["round_id", "station_no", "hits", "target_count"]].merge(
            rounds, on="round_id", how="inner"
        )
        units, key_cols, sort_cols = _keys(joined, spec.group_by)
        units["value"] = joined["hits"].astype(float)
        units["weight"] = joined["target_count"].astype(float)
        return units, key_cols, sort_cols, int(joined["round_id"].nunique())
    if metric in (Metric.RATING, Metric.WINS):
        rounds = rounds[rounds["is_best_round"].eq(True)]
    units, key_cols, sort_cols = _keys(rounds, spec.group_by)
    if metric is Metric.ROUNDS:
        units["value"] = 1
    elif metric is Metric.SHOOTERS:
        units["value"] = rounds["shooter_id"].astype("int64")
    elif metric is Metric.WINS:
        units["value"] = rounds["event_rank"].eq(1).astype("int64")
    else:
        units["value"] = rounds[AGGREGATED[metric]].astype(float)
    return units, key_cols, sort_cols, int(rounds["round_id"].nunique())


def _cell(value: object) -> Cell:
    """JSON-safe cell: numpy scalars become int/float; NaN, None and NA become None."""
    if isinstance(value, str):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real) and not math.isnan(float(value)):
        return float(value)
    return None


def run_query(frames: ExplorerFrames, spec: QuerySpec) -> QueryResult:
    _validate(frames, spec)
    units, key_cols, sort_cols, n_rounds = _units(frames, spec)
    group_cols = key_cols or ["_all"]
    if not key_cols:
        units["_all"] = 0
    named: dict[str, tuple[str, Reducer]] = {c: (c, "min") for c in sort_cols}
    reducer = AGG_FUNCS[spec.agg] if spec.metric in AGGREGATED else FIXED_REDUCERS[spec.metric]
    named["value"] = ("value", reducer)
    named["n"] = ("value", "count")
    if spec.metric is Metric.HIT_PCT:
        named["weight"] = ("weight", "sum")
    grouped = units.groupby(group_cols, dropna=False, sort=False).agg(**named).reset_index()
    if spec.metric is Metric.HIT_PCT:
        grouped["value"] = 100.0 * grouped["value"] / grouped["weight"]
    if spec.sort in ("key_asc", "key_desc"):
        by = [*sort_cols, *key_cols, "n"]
        ascending = spec.sort == "key_asc"
        grouped = grouped.sort_values(by, ascending=ascending, na_position="last", kind="stable")
    else:
        by = ["value", *sort_cols, *key_cols]
        flags = [spec.sort == "value_asc", *([True] * (len(by) - 1))]
        grouped = grouped.sort_values(by, ascending=flags, na_position="last", kind="stable")
    truncated = len(grouped) > spec.limit
    grouped = grouped.head(spec.limit)

    if spec.metric in AGGREGATED:
        value_label = f"{AGG_LABELS[spec.agg]} {METRIC_LABELS[spec.metric].lower()}"
    else:
        value_label = METRIC_LABELS[spec.metric]
    value_type: ColumnType = "int" if spec.metric in INT_METRICS else "number"
    columns = [c for d in spec.group_by for c in DIM_COLUMNS[d]]
    columns += [
        Column(key="value", label=value_label, type=value_type),
        Column(key="n", label="n", type="int"),
    ]
    keys = [c.key for c in columns]
    rows = [
        {k: _cell(v) for k, v in zip(keys, record, strict=True)}
        for record in grouped[keys].itertuples(index=False, name=None)
    ]
    return QueryResult(columns=columns, rows=rows, n_rounds=n_rounds, truncated=truncated)
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd backend && uv run pytest tests/unit/explorer -q`
Expected: PASS — 181 passed (10 spec, 171 engine: 135 Metric × Dim combinations, 123 of them valid, plus the
aggregation, filter, sorting, limit, null and `invalid_query` cases).

- [ ] **Step 9: Write the failing loader tests (stubbed unit test and the fixture-database test)**

Create the full contents of `backend/tests/unit/explorer/test_explorer_loader.py`:

```python
"""load_explorer_frames over stubbed Plan 06 loaders; tests/integration covers the real database."""

import math
from datetime import date

import pandas as pd
import pytest

from sunday_clays.analytics import frames as fr
from sunday_clays.explorer import engine
from sunday_clays.explorer.spec import Dim, Metric, QuerySpec

D1 = date(2025, 1, 5)
D2 = date(2025, 7, 6)
NAN = math.nan


@pytest.fixture
def as_of_calls(monkeypatch: pytest.MonkeyPatch) -> list[date]:
    """Stubs every loader the Explorer reads; returns the as_of dates assign_classes sees."""
    rounds = pd.DataFrame(
        {
            "round_id": [1, 2, 3],
            "event_date": [D1, D1, D2],
            "shooter_id": [10, 11, 10],
            "score": [40, 30, 42],
            "temp_f": [38.0, 38.0, NAN],
            "gust_mph": [22.0, 22.0, NAN],
            "precip_in": [0.0, 0.0, NAN],
        }
    )
    events = pd.DataFrame(
        {
            "event_date": [D1, D2],
            "round_type": ["sporting", "unknown"],
            "head_count": [2.0, 1.0],
            "n_rounds": [2, 1],
            "temp_f": [38.0, NAN],
            "gust_mph": [22.0, NAN],
            "precip_in": [0.0, NAN],
            "condition": ["windy", None],
        }
    )
    hits = pd.DataFrame(
        {"event_date": [D2], "station_no": [4], "target_count": [7], "round_id": [3], "hits": [5]}
    )
    calls: list[date] = []

    def fake_classes(history: pd.DataFrame, rounds: pd.DataFrame, as_of: date) -> pd.DataFrame:
        calls.append(as_of)
        return pd.DataFrame(
            {"shooter_id": [10], "mu": [1.0], "klass": ["A" if as_of == D1 else "B"]}
        )

    monkeypatch.setattr(fr, "load_rounds", lambda session: rounds)
    monkeypatch.setattr(fr, "load_rating_history", lambda session: pd.DataFrame())
    monkeypatch.setattr(fr, "load_events", lambda session: events)
    monkeypatch.setattr(fr, "load_station_hits", lambda session: hits)
    monkeypatch.setattr(engine, "assign_classes", fake_classes)
    return calls


def test_loader_adds_the_class_each_shooter_held_on_each_event_date(
    as_of_calls: list[date],
) -> None:
    frames = engine.load_explorer_frames.__wrapped__(None)  # skip the data_version cache

    assert as_of_calls == [D1, D2]
    klass = frames.rounds.set_index("round_id")["klass"]
    assert (klass[1], klass[3]) == ("A", "B")
    assert pd.isna(klass[2])  # shooter 11 had no class that day


def test_loader_adds_weather_bands_and_keeps_missing_weather_missing(
    as_of_calls: list[date],
) -> None:
    frames = engine.load_explorer_frames.__wrapped__(None)

    first = frames.rounds.iloc[0]
    assert (first["temp_band"], first["wind_band"], first["precip_band"]) == ("<40", "20+", "dry")
    assert frames.rounds.iloc[2][["temp_band", "wind_band", "precip_band"]].isna().all()
    assert list(frames.events.columns) == [
        "event_date",
        "round_type",
        "head_count",
        *engine.WEATHER_COLUMNS,
        "temp_band",
        "wind_band",
        "precip_band",
    ]
    assert frames.station_hits["target_count"].tolist() == [7]


def test_loaded_frames_answer_queries(as_of_calls: list[date]) -> None:
    frames = engine.load_explorer_frames.__wrapped__(None)

    result = engine.run_query(frames, QuerySpec(metric=Metric.ROUNDS, group_by=[Dim.CLASS]))

    assert [(r["class"], r["value"]) for r in result.rows] == [("A", 1), ("B", 1), (None, 1)]
```

Create the full contents of `backend/tests/integration/explorer/test_explorer_frames.py`:

```python
"""load_explorer_frames over the committed fixtures (`fx_session`, Plan 03 T6)."""

from sqlalchemy.orm import Session

from sunday_clays.explorer.engine import WEATHER_COLUMNS, load_explorer_frames


def test_frames_cover_the_committed_fixtures(fx_session: Session) -> None:
    frames = load_explorer_frames(fx_session)

    assert len(frames.rounds) == 7480
    assert {"klass", "temp_band", "wind_band", "precip_band"} <= set(frames.rounds.columns)
    assert frames.rounds["klass"].notna().any()
    assert len(frames.events) == 360
    assert set(WEATHER_COLUMNS) <= set(frames.events.columns)
    # 37 station-sheet entries x 7 stations on the two station events, every one linked.
    assert len(frames.station_hits) == 259
    assert frames.station_hits["round_id"].notna().all()
    assert set(frames.station_hits["target_count"]) == {7, 8}
```

- [ ] **Step 10: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/explorer/test_explorer_loader.py tests/integration/explorer -q`
Expected: FAIL — the three unit tests error in setup with `AttributeError: <module 'sunday_clays.explorer.engine' …>
has no attribute 'assign_classes'`, and the integration file fails to collect with
`ImportError: cannot import name 'WEATHER_COLUMNS'`.

- [ ] **Step 11: Add the cached frame loader to the engine**

Make three edits to `backend/src/sunday_clays/explorer/engine.py`.

(a) Replace the module docstring and import block (everything above the blank line that precedes
`ColumnType = Literal[...]`) with:

```python
"""Explorer engine (C9): a cached frame loader plus a pure pandas query runner."""

import math
import numbers
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames as fr
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.classes import assign_classes
from sunday_clays.domain.errors import DomainError
from sunday_clays.explorer.spec import (
    Agg,
    Column,
    Dim,
    Filters,
    Metric,
    QueryResult,
    QuerySpec,
)
```

(b) Directly below the closing `}` of `PLAIN_DIMS`, add:

```python
WEATHER_COLUMNS: Final = ["temp_f", "gust_mph", "precip_in", "condition"]
```

(c) Append at the end of the file (after two blank lines):

```python
def _add_bands(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        temp_band=df["temp_f"].map(fr.temp_band),
        wind_band=df["gust_mph"].map(fr.wind_band),
        precip_band=df["precip_in"].map(fr.precip_band),
    )


def _classes_by_event(history: pd.DataFrame, rounds: pd.DataFrame) -> pd.DataFrame:
    records: list[tuple[object, int, object]] = []
    for event_date in pd.unique(rounds["event_date"]):
        classes = assign_classes(history, rounds, pd.Timestamp(event_date).date())
        for shooter_id, klass in zip(classes["shooter_id"], classes["klass"], strict=True):
            records.append((event_date, int(shooter_id), klass))
    frame = pd.DataFrame.from_records(records, columns=["event_date", "shooter_id", "klass"])
    return frame.astype({"event_date": rounds["event_date"].dtype, "shooter_id": "int64"})


@cached_by_data_version
def load_explorer_frames(session: Session) -> ExplorerFrames:
    """Plan 06 frames plus weather bands (rounds and events) and each round's class that day."""
    rounds = fr.load_rounds(session)
    classes = _classes_by_event(fr.load_rating_history(session), rounds)
    rounds = _add_bands(rounds.merge(classes, on=["event_date", "shooter_id"], how="left"))
    events = fr.load_events(session)[["event_date", "round_type", "head_count", *WEATHER_COLUMNS]]
    return ExplorerFrames(
        rounds=rounds, station_hits=fr.load_station_hits(session), events=_add_bands(events)
    )
```

- [ ] **Step 12: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/unit/explorer tests/integration/explorer -q`
Expected: PASS — 185 passed (184 unit, 1 integration; the integration test needs Docker for the testcontainers
Postgres, or `TEST_DATABASE_URL`).

- [ ] **Step 13: Write the failing route test against the committed fixtures**

Create the full contents of `backend/tests/integration/api/test_explore_route.py`:

```python
"""POST /api/explore over the committed fixtures (`fx_viewer_client`, Plans 03 T6 and 04 T1).

Expected numbers were counted from the fixture workbooks with openpyxl/pandas.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

ROUNDS_BY_YEAR = {2020: 843, 2021: 1047, 2022: 1078, 2023: 1083, 2024: 1193, 2025: 1267, 2026: 969}
ROUNDS_BY_GAUGE = [
    ("unspecified", 7302),
    ("12 Gauge", 151),
    ("Sub-Gauge", 10),
    ("SxS", 9),
    ("28 Gauge", 7),
    ("20 Gauge", 1),
]
# station_no: (hits, targets) summed over the 37 linked station-sheet entries
HITS_BY_STATION = {
    4: (184, 259),
    5: (190, 259),
    6: (190, 259),
    7: (205, 259),
    8: (205, 259),
    9: (130, 259),
    10: (230, 296),
}


def _explore(client: TestClient, spec: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/explore", json=spec)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_rounds_by_year(fx_viewer_client: TestClient) -> None:
    body = _explore(fx_viewer_client, {"metric": "rounds", "group_by": ["year"]})

    assert body["columns"] == [
        {"key": "year", "label": "Year", "type": "int"},
        {"key": "value", "label": "Rounds", "type": "int"},
        {"key": "n", "label": "n", "type": "int"},
    ]
    assert {row["year"]: row["value"] for row in body["rows"]} == ROUNDS_BY_YEAR
    assert body["n_rounds"] == 7480
    assert body["truncated"] is False


def test_rounds_by_gauge_keep_unspecified(fx_viewer_client: TestClient) -> None:
    body = _explore(
        fx_viewer_client, {"metric": "rounds", "group_by": ["gauge"], "sort": "value_desc"}
    )

    assert [(row["gauge"], row["value"]) for row in body["rows"]] == ROUNDS_BY_GAUGE


def test_hit_pct_by_station(fx_viewer_client: TestClient) -> None:
    body = _explore(fx_viewer_client, {"metric": "hit_pct", "group_by": ["station"]})

    assert {row["station"]: row["value"] for row in body["rows"]} == pytest.approx(
        {no: 100 * hits / targets for no, (hits, targets) in HITS_BY_STATION.items()}
    )
    assert {row["n"] for row in body["rows"]} == {37}
    assert body["n_rounds"] == 37


def test_invalid_query_is_a_400_with_the_error_envelope(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.post(
        "/api/explore", json={"metric": "score", "group_by": ["station"]}
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_query",
            "message": "Grouping by station needs the Hit % metric",
        }
    }


def test_more_than_two_dims_fail_validation(fx_viewer_client: TestClient) -> None:
    response = fx_viewer_client.post(
        "/api/explore", json={"metric": "rounds", "group_by": ["year", "month", "season"]}
    )

    assert response.status_code == 422
```

- [ ] **Step 14: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/integration/api/test_explore_route.py -q`
Expected: FAIL — 5 failed; each response is `404 {"detail":"Not Found"}` because no router serves `/api/explore` yet.

- [ ] **Step 15: Implement the route module**

Create the full contents of `backend/src/sunday_clays/api/routes/explore.py`:

```python
"""POST /api/explore (C8/C9): run a validated Explorer QuerySpec against the cached frames."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sunday_clays.db import get_session
from sunday_clays.explorer.engine import load_explorer_frames, run_query
from sunday_clays.explorer.spec import QueryResult, QuerySpec

router = APIRouter(tags=["explore"])


@router.post("/api/explore", response_model=QueryResult)
def explore(spec: QuerySpec, session: Annotated[Session, Depends(get_session, scope="function")]) -> QueryResult:
    return run_query(load_explorer_frames(session), spec)
```

- [ ] **Step 16: Run it to verify it passes**

Run: `cd backend && uv run pytest tests/integration/api/test_explore_route.py tests/integration/api/test_route_auth_matrix.py -q`
Expected: PASS — the 5 route tests, and Plan 04's runtime auth matrix now also covers `POST /api/explore` (401 without
a cookie).

- [ ] **Step 17: Full backend suite, lint, types and coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: all green with 0 findings; coverage ≥90% lines and branches (`fail_under=90`), with
`src/sunday_clays/explorer/engine.py` and `spec.py` at 100% lines and branches.

- [ ] **Step 18: Regenerate the frontend API types**

Run: `cd frontend && pnpm gen:api && grep -c "QuerySpec" src/api/schema.d.ts`
Expected: `gen:api` succeeds and the count is ≥1 (the schema file is gitignored and generated in CI, so nothing to
commit).

- [ ] **Step 19: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add backend/src/sunday_clays/explorer backend/src/sunday_clays/api/routes/explore.py \
  backend/tests/unit/explorer backend/tests/integration/explorer backend/tests/integration/api/test_explore_route.py
git commit -F - <<'MSG'
feat(explorer): QuerySpec engine, cached frames and POST /api/explore

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```

### Task 8: Explorer page with shareable URL state (master Plan 07 T8)

**Context.** Tasks 3, 6 and 7 of this plan and Plan 04 T2 have merged: `POST /api/explore` is
live and generated into `src/api/schema.d.ts`, `ChartFrame`/`useExplore`/`buildExploreOption` exist, every feature
route renders inside `RequireRole` → `AppShell`, and Playwright's `setup` project seeds both fixture workbooks before
any spec runs (Decision D3). This task adds the `explorer` feature: the `/explorer` route and its nav item (C10 order
60, not a mobile tab), a URL-state hook that keeps the whole query in the query string (Decision D25, so any view is a
shareable link and hand-edited or malformed parameters fall back to safe defaults), the query and filter controls, the
result chart in a `ChartFrame` (table, CSV, fullscreen, zoom, drill links to shooter and event pages), a default MSW
handler for `/api/explore`, and an e2e spec against the seeded fixtures at both viewports. The global `rt` filter is
merged into `spec.filters.round_types`. The Filters panel starts open when the URL carries filters and afterwards opens
and closes only when the user toggles it, so clearing the last filter never collapses it mid-edit (Decision D25). Run
every command from the worktree root: frontend commands start with `cd frontend && `, and the commit step starts with
`cd "$(git rev-parse --show-toplevel)"` (agent shells reset the working directory between calls, Decision D28).

**Files:**
- Create: `frontend/src/features/explorer/routes.tsx`, `frontend/src/features/explorer/mocks.ts`,
  `frontend/src/features/explorer/urlState.ts`, `frontend/src/features/explorer/components/QueryControls.tsx`,
  `frontend/src/features/explorer/components/FilterControls.tsx`,
  `frontend/src/features/explorer/pages/ExplorerPage.tsx`
- Test: `frontend/src/features/explorer/pages/ExplorerPage.test.tsx`, `frontend/e2e/explorer.spec.ts`

**Interfaces:**
- Consumes: Task 7 `POST /api/explore` (C9); Task 6 `ChartFrame`, `useExplore`, `buildExploreOption`, `toTabular`,
  `querySpec`, `METRICS`, `DIMS`, `AGGS`, `METRIC_LABELS`, `DIM_LABELS`, `AGG_LABELS`, `type QuerySpec`,
  `QueryResult`, `Metric`, `Dim`, `Agg`, `expectChartControls`; Task 5 `ChartType`, `TabularRow`; Task 4
  `useUrlState` + codecs, `useRoundTypes`, `formatNumber`, `renderWithProviders`, `server`; Task 1 `Button`, `Card`,
  `Chip`, `EmptyState`, `Skeleton`, `Select`, `RangeSlider`, `Toggle`; Plan 01 T2 registry (`NavItem`); Plan 01 T4
  `e2e/fixtures.ts`; Plan 04 `e2e/authState.ts` (`VIEWER_STATE`) and the seeded fixtures.
- Produces:
  - Relative route `explorer` (served at `/explorer`, Plan 01 Decision 15; lazy `ExplorerPage`) and
    `nav: [{label: 'Explorer', path: '/explorer', icon: Compass, order: 60}]`.
  - `features/explorer/urlState.ts`: `STATUSES`, `GAUGES`, `SORTS`, `CHART_TYPES`, `AGGREGATED_METRICS`,
    `type RangeFilter`, `RANGE_FILTERS`, `useExplorerState(): {spec: QuerySpec; chartType: ChartType; ranges; set}`
    with the query keys `m`, `a`, `g`, `from`, `to`, `st`, `ga`, `sh`, `t`, `w`, `p`, `mr`, `best`, `s`, `c` (and the
    ChartFrame view key `v`).
  - `features/explorer/mocks.ts`: `fakeExploreResult(spec): QueryResult` and the default `POST /api/explore` MSW
    handler (every later test that renders a `ChartCard` gets a result without its own handler).
  - Deep links other pages may build: `/explorer?m=<metric>&g=<dim>[,<dim>]&sh=<id>[,<id>]&…`.

**Branch:** `task/07-8-explorer-page` · **Depends on:** Plan 07 T3, Plan 07 T6, Plan 07 T7, Plan 04 T2.

- [ ] **Step 1: Add the default MSW handler for `/api/explore`**

Create the full contents of `frontend/src/features/explorer/mocks.ts` (test infrastructure, merged into every test's
server by `test/msw/handlers.ts`):

```ts
import { http, HttpResponse } from 'msw';
import type { QueryResult, QuerySpec } from '../../components/charts/explore';

/**
 * Deterministic fake result shaped like the real one: a column per group-by dim (shooter also
 * gets shooter_id), then value and n. Two rows: first dim 'A' and 'B'; any second dim 'X'.
 */
export function fakeExploreResult(spec: QuerySpec): QueryResult {
  const [first, second] = spec.group_by;
  const columns: QueryResult['columns'] = [];
  for (const dim of spec.group_by) {
    if (dim === 'shooter') columns.push({ key: 'shooter_id', label: 'Shooter ID', type: 'int' });
    columns.push({ key: dim, label: dim, type: 'string' });
  }
  columns.push(
    { key: 'value', label: 'Value', type: 'number' },
    { key: 'n', label: 'n', type: 'int' },
  );
  const row = (key: string, id: number, value: number, n: number) => ({
    ...(first === undefined ? {} : { [first]: key }),
    ...(first === 'shooter' || second === 'shooter' ? { shooter_id: id } : {}),
    ...(second === undefined ? {} : { [second]: 'X' }),
    value,
    n,
  });
  const rows =
    first === undefined ? [{ value: 35, n: 10 }] : [row('A', 3, 36, 6), row('B', 4, 34, 4)];
  return { columns, rows, n_rounds: 10, truncated: false };
}

export const handlers = [
  http.post('/api/explore', async ({ request }) =>
    HttpResponse.json(fakeExploreResult((await request.json()) as QuerySpec)),
  ),
];
```

Run: `cd frontend && pnpm exec vitest run src/components/charts`
Expected: PASS — unchanged (the `ChartCard` tests install their own `/api/explore` handlers with `server.use`).

- [ ] **Step 2: Write the failing Explorer page test**

Create the full contents of `frontend/src/features/explorer/pages/ExplorerPage.test.tsx`:

```tsx
import { fireEvent, screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import type { QuerySpec } from '../../../components/charts/explore';
import { expectChartControls } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { fakeExploreResult } from '../mocks';
import { ExplorerPage } from './ExplorerPage';

function captureSpecs(): QuerySpec[] {
  const seen: QuerySpec[] = [];
  server.use(
    http.post('/api/explore', async ({ request }) => {
      const spec = (await request.json()) as QuerySpec;
      seen.push(spec);
      return HttpResponse.json(fakeExploreResult(spec));
    }),
  );
  return seen;
}

function renderPage(route = '/explorer') {
  return renderWithProviders(<ExplorerPage />, { route, path: '/explorer' });
}

describe('ExplorerPage', () => {
  it('runs the default query (average score by year) and shows it with Table and CSV controls', async () => {
    const seen = captureSpecs();
    renderPage();
    const chart = await screen.findByRole('img', { name: 'Value by year' });
    expect(chart).toBeInTheDocument();
    expectChartControls(screen.getByRole('region', { name: 'Value by year' }));
    expect(screen.getByText('Based on 10 rounds')).toBeInTheDocument();
    expect(seen[0]).toEqual({
      metric: 'score',
      agg: 'avg',
      group_by: ['year'],
      sort: 'key_asc',
      limit: 500,
      filters: {
        date_from: null,
        date_to: null,
        shooter_ids: [],
        round_types: [],
        statuses: [],
        gauges: [],
        temp_f: null,
        gust_mph: null,
        precip_in: null,
        min_rounds: 0,
        best_round_only: false,
      },
    });
  });

  it('restores a shared URL into the query and the controls', async () => {
    const seen = captureSpecs();
    renderPage(
      '/explorer?m=rounds&g=status,year&st=member&ga=unspecified&sh=3,4&t=40..70&w=0..10&p=0..0.02&mr=5&best=1&s=value_desc&from=2025-01-01&to=2025-12-31&rt=sporting&c=line',
    );
    await screen.findByRole('img', { name: 'Value by status and year' });
    expect(seen[0]).toMatchObject({
      metric: 'rounds',
      group_by: ['status', 'year'],
      sort: 'value_desc',
      filters: {
        date_from: '2025-01-01',
        date_to: '2025-12-31',
        shooter_ids: [3, 4],
        round_types: ['sporting'],
        statuses: ['member'],
        gauges: ['unspecified'],
        temp_f: [40, 70],
        gust_mph: [0, 10],
        precip_in: [0, 0.02],
        min_rounds: 5,
        best_round_only: true,
      },
    });
    expect(screen.getByLabelText('Metric')).toHaveValue('rounds');
    expect(screen.queryByLabelText('Aggregate')).toBeNull();
    expect(screen.getByText('Filters (10)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Line' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('2 shooters')).toBeInTheDocument();
  });

  it('falls back to safe defaults for hand-edited, malformed parameters', async () => {
    const seen = captureSpecs();
    renderPage(
      '/explorer?m=bogus&a=nope&g=year,year,shooter,class&t=abc&mr=-3&from=2026-02-30&sh=x&c=pie',
    );
    await screen.findByRole('img', { name: 'Value by year and shooter' });
    expect(seen[0]).toMatchObject({
      metric: 'score',
      agg: 'avg',
      group_by: ['year', 'shooter'],
      filters: { temp_f: null, min_rounds: 0, date_from: null, shooter_ids: [] },
    });
  });

  it('writes every control change to the URL', async () => {
    const seen = captureSpecs();
    const { user, router } = renderPage();
    await screen.findByRole('img', { name: 'Value by year' });
    await user.selectOptions(screen.getByLabelText('Aggregate'), 'Median');
    await user.selectOptions(screen.getByLabelText('Group by'), 'Gauge');
    await user.selectOptions(screen.getByLabelText('Then by'), 'Status');
    await user.selectOptions(screen.getByLabelText('Sort'), 'Value, highest first');
    await user.click(screen.getByRole('button', { name: 'Heatmap' }));
    await user.click(screen.getByText('Filters'));
    await user.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    await user.click(
      within(screen.getByRole('group', { name: 'Gauge' })).getByRole('button', {
        name: 'Not recorded',
      }),
    );
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2024-01-07' } });
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '40' } });
    fireEvent.change(screen.getByLabelText('Minimum rounds per shooter'), {
      target: { value: '10' },
    });
    await user.click(screen.getByRole('switch', { name: 'Best round only' }));
    await user.selectOptions(screen.getByLabelText('Metric'), 'Rounds');
    const params = new URLSearchParams(router.state.location.search);
    expect(Object.fromEntries(params)).toEqual({
      a: 'median',
      g: 'gauge,status',
      s: 'value_desc',
      c: 'heatmap',
      st: 'guest',
      ga: 'unspecified',
      from: '2024-01-07',
      t: '40..110',
      mr: '10',
      best: '1',
      m: 'rounds',
    });
    await screen.findByRole('img', { name: 'Value by gauge and status' });
    expect(seen.at(-1)).toMatchObject({ metric: 'rounds', group_by: ['gauge', 'status'] });
  });

  it('removes filters again: full-range sliders, cleared dates, toggled chips and the shooter chip', async () => {
    captureSpecs();
    const { user, router } = renderPage(
      '/explorer?t=40..110&from=2024-01-07&to=2024-12-29&st=guest&sh=3',
    );
    await screen.findByRole('img', { name: 'Value by year' });
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '0' } });
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('To'), { target: { value: '' } });
    await user.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    await user.click(screen.getByRole('button', { name: 'Clear shooter filter' }));
    expect(router.state.location.search).toBe('');
  });

  it('clears the grouping with None', async () => {
    const seen = captureSpecs();
    const { user } = renderPage('/explorer?g=year,status');
    await screen.findByRole('img', { name: 'Value by year and status' });
    await user.selectOptions(screen.getByLabelText('Then by'), 'None');
    await user.selectOptions(screen.getByLabelText('Group by'), 'None');
    expect(await screen.findByRole('img', { name: 'Value' })).toBeInTheDocument();
    expect(seen.at(-1)?.group_by).toEqual([]);
  });

  it("shows the server's explanation when a combination is invalid", async () => {
    server.use(
      http.post('/api/explore', () =>
        HttpResponse.json(
          {
            error: { code: 'invalid_query', message: 'Grouping by station needs the Hit % metric' },
          },
          { status: 400 },
        ),
      ),
    );
    renderPage('/explorer?g=station');
    expect(
      await screen.findByRole('heading', { name: "This query can't run" }),
    ).toBeInTheDocument();
    expect(screen.getByText('Grouping by station needs the Hit % metric')).toBeInTheDocument();
  });

  it('shows loading, empty and truncated states', async () => {
    server.use(
      http.post('/api/explore', async () => {
        await delay(20);
        return HttpResponse.json({
          columns: [{ key: 'value', label: 'Wins', type: 'int' }],
          rows: [],
          n_rounds: 0,
          truncated: false,
        });
      }),
    );
    renderPage();
    expect(screen.getByRole('status', { name: 'Running query' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'No data for these filters' }),
    ).toBeInTheDocument();
  });

  it('notes a truncated result', async () => {
    server.use(
      http.post('/api/explore', async ({ request }) =>
        HttpResponse.json({
          ...fakeExploreResult((await request.json()) as QuerySpec),
          n_rounds: 7480,
          truncated: true,
        }),
      ),
    );
    renderPage();
    expect(
      await screen.findByText('Based on 7,480 rounds · showing the first 2 rows'),
    ).toBeInTheDocument();
  });

  it('links shooter rows to profiles from the table', async () => {
    captureSpecs();
    renderPage('/explorer?g=shooter&v=table');
    expect(await screen.findByRole('link', { name: 'A' })).toHaveAttribute('href', '/shooters/3');
  });

  it('links event rows to event pages from the table', async () => {
    captureSpecs();
    renderPage('/explorer?g=event&v=table');
    expect(await screen.findByRole('link', { name: 'B' })).toHaveAttribute('href', '/events/B');
  });

  it('keeps the Filters panel open when the last filter is cleared', async () => {
    captureSpecs();
    const { user } = renderPage('/explorer?st=guest');
    await screen.findByRole('img', { name: 'Value by year' });
    expect(screen.getByText('Filters (1)').closest('details')).toHaveAttribute('open');
    await user.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    expect(screen.getByText('Filters').closest('details')).toHaveAttribute('open');
  });

  it.each([
    ['/explorer?m=rounds&g=year', 'Value by year', 'explorer-rounds-by-year.csv'],
    ['/explorer?m=rounds&g=', 'Value', 'explorer-rounds.csv'],
  ])('names the CSV of %s after the query', async (route, chartName, filename) => {
    captureSpecs();
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });
    const { user } = renderPage(route);
    await screen.findByRole('img', { name: chartName });
    await user.click(screen.getByRole('button', { name: 'CSV' }));
    expect(names).toEqual([filename]);
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/explorer`
Expected: FAIL — `Failed to resolve import "./ExplorerPage"`.

- [ ] **Step 4: Implement the URL state**

Create the full contents of `frontend/src/features/explorer/urlState.ts`:

```ts
import {
  AGGS,
  DIMS,
  METRICS,
  querySpec,
  type Agg,
  type Dim,
  type Metric,
  type QuerySpec,
} from '../../components/charts/explore';
import type { ChartType } from '../../components/charts/types';
import { useRoundTypes } from '../../lib/roundTypes';
import {
  boolCodec,
  enumCodec,
  isoDateCodec,
  listCodec,
  rangeCodec,
  useUrlState,
  type Codec,
} from '../../lib/useUrlState';

export const STATUSES = ['member', 'guest', 'deceased'] as const;
/** Normalized gauge classes (C3) plus 'unspecified' for "not recorded" (C7). */
export const GAUGES = [
  '12 Gauge',
  '20 Gauge',
  '28 Gauge',
  '.410',
  'Sub-Gauge',
  'SxS',
  'unspecified',
] as const;
export const SORTS = ['key_asc', 'key_desc', 'value_desc', 'value_asc'] as const;
export const CHART_TYPES: ChartType[] = ['bar', 'line', 'heatmap'];
/** Metrics whose values are combined with the chosen aggregate (the rest are counts/rates). */
export const AGGREGATED_METRICS: readonly Metric[] = [
  'score',
  'adjusted',
  'residual',
  'rating',
  'attendance',
];

export type RangeFilter = 'temp_f' | 'gust_mph' | 'precip_in';
export const RANGE_FILTERS: Record<
  RangeFilter,
  { param: string; label: string; min: number; max: number; step: number; unit: string }
> = {
  temp_f: { param: 't', label: 'Temperature', min: 0, max: 110, step: 1, unit: '°F' },
  gust_mph: { param: 'w', label: 'Wind gust', min: 0, max: 50, step: 1, unit: 'mph' },
  precip_in: { param: 'p', label: 'Rain', min: 0, max: 2, step: 0.01, unit: 'in' },
};

/** Empty string ⇄ null, so "no filter" drops the parameter. */
function optional<T>(codec: Codec<T>): Codec<T | null> {
  return {
    parse: (raw) => (raw === '' ? null : codec.parse(raw)),
    serialize: (value) => (value === null ? '' : codec.serialize(value)),
  };
}

const countCodec: Codec<number> = {
  parse: (raw) => (/^\d{1,4}$/.test(raw) ? Number(raw) : null),
  serialize: (v) => String(v),
};
const idsCodec = listCodec<number>({
  parse: (raw) => (/^\d+$/.test(raw) ? Number(raw) : null),
  serialize: (v) => String(v),
});
const dateCodec = optional(isoDateCodec);
const rangeParam = optional(rangeCodec);

const DEFAULT_DIMS: Dim[] = ['year'];
const NO_STATUSES: (typeof STATUSES)[number][] = [];
const NO_GAUGES: (typeof GAUGES)[number][] = [];
const NO_IDS: number[] = [];

const codecs = {
  metric: enumCodec<Metric>(METRICS),
  agg: enumCodec<Agg>(AGGS),
  dims: listCodec(enumCodec<Dim>(DIMS)),
  statuses: listCodec(enumCodec(STATUSES)),
  gauges: listCodec(enumCodec(GAUGES)),
  sort: enumCodec(SORTS),
  chart: enumCodec(CHART_TYPES),
};

/** The whole Explorer query lives in the URL, so any view is a shareable link. */
export function useExplorerState() {
  const [metric, setMetric] = useUrlState('m', codecs.metric, 'score');
  const [agg, setAgg] = useUrlState('a', codecs.agg, 'avg');
  const [dims, setDims] = useUrlState('g', codecs.dims, DEFAULT_DIMS);
  const [from, setFrom] = useUrlState('from', dateCodec, null);
  const [to, setTo] = useUrlState('to', dateCodec, null);
  const [statuses, setStatuses] = useUrlState('st', codecs.statuses, NO_STATUSES);
  const [gauges, setGauges] = useUrlState('ga', codecs.gauges, NO_GAUGES);
  const [shooterIds, setShooterIds] = useUrlState('sh', idsCodec, NO_IDS);
  const [temp, setTemp] = useUrlState(RANGE_FILTERS.temp_f.param, rangeParam, null);
  const [gust, setGust] = useUrlState(RANGE_FILTERS.gust_mph.param, rangeParam, null);
  const [precip, setPrecip] = useUrlState(RANGE_FILTERS.precip_in.param, rangeParam, null);
  const [minRounds, setMinRounds] = useUrlState('mr', countCodec, 0);
  const [bestOnly, setBestOnly] = useUrlState('best', boolCodec, false);
  const [sort, setSort] = useUrlState('s', codecs.sort, 'key_asc');
  const [chartType, setChartType] = useUrlState('c', codecs.chart, 'bar');
  const [roundTypes] = useRoundTypes();

  const groupBy = dims.slice(0, 2);
  const spec: QuerySpec = querySpec({
    metric,
    agg,
    group_by: groupBy,
    sort,
    filters: {
      date_from: from,
      date_to: to,
      shooter_ids: shooterIds,
      round_types: roundTypes,
      statuses: [...statuses],
      gauges: [...gauges],
      temp_f: temp,
      gust_mph: gust,
      precip_in: precip,
      min_rounds: minRounds,
      best_round_only: bestOnly,
    },
  });
  const ranges: Record<
    RangeFilter,
    [[number, number] | null, (v: [number, number] | null) => void]
  > = {
    temp_f: [temp, setTemp],
    gust_mph: [gust, setGust],
    precip_in: [precip, setPrecip],
  };
  return {
    spec,
    chartType,
    ranges,
    set: {
      metric: setMetric,
      agg: setAgg,
      dims: setDims,
      from: setFrom,
      to: setTo,
      statuses: setStatuses,
      gauges: setGauges,
      shooterIds: setShooterIds,
      minRounds: setMinRounds,
      bestOnly: setBestOnly,
      sort: setSort,
      chartType: setChartType,
    },
  };
}
```

- [ ] **Step 5: Implement the query and filter controls**

Create the full contents of `frontend/src/features/explorer/components/QueryControls.tsx`:

```tsx
import {
  AGG_LABELS,
  AGGS,
  DIM_LABELS,
  DIMS,
  METRIC_LABELS,
  METRICS,
  type Dim,
  type QuerySpec,
} from '../../../components/charts/explore';
import type { ChartType } from '../../../components/charts/types';
import { Chip } from '../../../components/ui/Chip';
import { Select } from '../../../components/ui/Select';
import { AGGREGATED_METRICS, CHART_TYPES, SORTS, type useExplorerState } from '../urlState';

type Setters = ReturnType<typeof useExplorerState>['set'];

const SORT_LABELS: Record<(typeof SORTS)[number], string> = {
  key_asc: 'Group, ascending',
  key_desc: 'Group, descending',
  value_desc: 'Value, highest first',
  value_asc: 'Value, lowest first',
};
const CHART_LABELS: Record<ChartType, string> = { bar: 'Bar', line: 'Line', heatmap: 'Heatmap' };
const NONE = '' as const;
const dimOptions = [
  { value: NONE, label: 'None' },
  ...DIMS.map((d) => ({ value: d, label: DIM_LABELS[d] })),
];

/** Metric, aggregate, group-by (≤2), sort and chart type. */
export function QueryControls({
  spec,
  chartType,
  set,
}: {
  spec: QuerySpec;
  chartType: ChartType;
  set: Setters;
}) {
  const [first, second] = spec.group_by;
  const setDims = (a: Dim | typeof NONE, b: Dim | typeof NONE) =>
    set.dims([a, b].filter((d): d is Dim => d !== NONE));
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1">
      <Select
        label="Metric"
        value={spec.metric}
        options={METRICS.map((m) => ({ value: m, label: METRIC_LABELS[m] }))}
        onChange={set.metric}
      />
      {AGGREGATED_METRICS.includes(spec.metric) && (
        <Select
          label="Aggregate"
          value={spec.agg}
          options={AGGS.map((a) => ({ value: a, label: AGG_LABELS[a] }))}
          onChange={set.agg}
        />
      )}
      <Select
        label="Group by"
        value={first ?? NONE}
        options={dimOptions}
        onChange={(d) => setDims(d, second ?? NONE)}
      />
      <Select
        label="Then by"
        value={second ?? NONE}
        options={dimOptions.filter((o) => o.value === NONE || o.value !== first)}
        onChange={(d) => setDims(first ?? NONE, d)}
      />
      <Select
        label="Sort"
        value={spec.sort}
        options={SORTS.map((s) => ({ value: s, label: SORT_LABELS[s] }))}
        onChange={set.sort}
      />
      <div role="group" aria-label="Chart type" className="flex flex-wrap gap-2">
        {CHART_TYPES.map((t) => (
          <Chip key={t} selected={t === chartType} onClick={() => set.chartType(t)}>
            {CHART_LABELS[t]}
          </Chip>
        ))}
      </div>
    </div>
  );
}
```

Create the full contents of `frontend/src/features/explorer/components/FilterControls.tsx`:

```tsx
import type { QuerySpec } from '../../../components/charts/explore';
import { Chip } from '../../../components/ui/Chip';
import { RangeSlider, Slider } from '../../../components/ui/Slider';
import { Toggle } from '../../../components/ui/Toggle';
import {
  GAUGES,
  RANGE_FILTERS,
  STATUSES,
  type RangeFilter,
  type useExplorerState,
} from '../urlState';

type State = ReturnType<typeof useExplorerState>;

const STATUS_LABELS: Record<(typeof STATUSES)[number], string> = {
  member: 'Member',
  guest: 'Guest',
  deceased: 'Deceased',
};

function toggled<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Count of active filters, for the collapsed "Filters (n)" summary. */
export function activeFilterCount(spec: QuerySpec): number {
  const f = spec.filters;
  return [
    f.date_from,
    f.date_to,
    f.shooter_ids.length > 0,
    f.statuses.length > 0,
    f.gauges.length > 0,
    f.temp_f,
    f.gust_mph,
    f.precip_in,
    f.min_rounds > 0,
    f.best_round_only,
  ].filter(Boolean).length;
}

export function FilterControls({ spec, ranges, set }: Pick<State, 'spec' | 'ranges' | 'set'>) {
  const f = spec.filters;
  const statuses = f.statuses.filter((s): s is (typeof STATUSES)[number] =>
    (STATUSES as readonly string[]).includes(s),
  );
  const gauges = f.gauges.filter((g): g is (typeof GAUGES)[number] =>
    (GAUGES as readonly string[]).includes(g),
  );
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          From
          <input
            type="date"
            value={f.date_from ?? ''}
            onChange={(e) => set.from(e.target.value === '' ? null : e.target.value)}
            className="min-h-11 rounded-button border border-outline-variant bg-surface px-3 text-sm text-text"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          To
          <input
            type="date"
            value={f.date_to ?? ''}
            onChange={(e) => set.to(e.target.value === '' ? null : e.target.value)}
            className="min-h-11 rounded-button border border-outline-variant bg-surface px-3 text-sm text-text"
          />
        </label>
      </div>
      <div role="group" aria-label="Status" className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <Chip
            key={s}
            selected={statuses.includes(s)}
            onClick={() => set.statuses(toggled(statuses, s))}
          >
            {STATUS_LABELS[s]}
          </Chip>
        ))}
      </div>
      <div role="group" aria-label="Gauge" className="flex flex-wrap gap-2">
        {GAUGES.map((g) => (
          <Chip
            key={g}
            selected={gauges.includes(g)}
            onClick={() => set.gauges(toggled(gauges, g))}
          >
            {g === 'unspecified' ? 'Not recorded' : g}
          </Chip>
        ))}
      </div>
      {f.shooter_ids.length > 0 && (
        <div>
          <Chip onRemove={() => set.shooterIds([])} removeLabel="Clear shooter filter">
            {f.shooter_ids.length === 1 ? '1 shooter' : `${f.shooter_ids.length} shooters`}
          </Chip>
        </div>
      )}
      {(Object.keys(RANGE_FILTERS) as RangeFilter[]).map((key) => {
        const { label, min, max, step, unit } = RANGE_FILTERS[key];
        const [value, setValue] = ranges[key];
        return (
          <RangeSlider
            key={key}
            label={label}
            min={min}
            max={max}
            step={step}
            value={value ?? [min, max]}
            format={(n) => `${n} ${unit}`}
            onChange={([lo, hi]) => setValue(lo === min && hi === max ? null : [lo, hi])}
          />
        );
      })}
      <Slider
        label="Minimum rounds per shooter"
        min={0}
        max={50}
        value={f.min_rounds}
        onChange={set.minRounds}
      />
      <Toggle label="Best round only" checked={f.best_round_only} onChange={set.bestOnly} />
    </div>
  );
}
```

- [ ] **Step 6: Implement the page and register the route**

Create the full contents of `frontend/src/features/explorer/pages/ExplorerPage.tsx`:

```tsx
import { useState } from 'react';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import {
  DIM_LABELS,
  buildExploreOption,
  toTabular,
  useExplore,
  type QuerySpec,
} from '../../../components/charts/explore';
import type { TabularRow } from '../../../components/charts/types';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatNumber } from '../../../lib/format';
import { FilterControls, activeFilterCount } from '../components/FilterControls';
import { QueryControls } from '../components/QueryControls';
import { useExplorerState } from '../urlState';

function describe(spec: QuerySpec, valueLabel: string): string {
  const dims = spec.group_by.map((d) => DIM_LABELS[d].toLowerCase());
  return dims.length ? `${valueLabel} by ${dims.join(' and ')}` : valueLabel;
}

/** Links a result row to the page for its first dim (shooter profile or event), if any. */
function rowLink(spec: QuerySpec): ((row: TabularRow) => string) | undefined {
  const first = spec.group_by[0];
  if (first === 'shooter') return (row) => `/shooters/${String(row.shooter_id)}`;
  if (first === 'event') return (row) => `/events/${String(row.event)}`;
  return undefined;
}

export function ExplorerPage() {
  const state = useExplorerState();
  const query = useExplore(state.spec);
  const filters = activeFilterCount(state.spec);
  // Open at first when the URL carries filters; afterwards only the user opens or closes it, so
  // clearing the last filter never collapses the panel mid-edit.
  const [filtersOpen, setFiltersOpen] = useState(filters > 0);

  let result;
  if (query.isPending) {
    result = (
      <Card title="Result">
        <Skeleton label="Running query" lines={8} />
      </Card>
    );
  } else if (query.isError) {
    result = (
      <Card title="Result">
        <EmptyState
          title="This query can't run"
          description={query.error.message}
          action={<Button onClick={() => void query.refetch()}>Try again</Button>}
        />
      </Card>
    );
  } else {
    const { spec, result: data } = query.data;
    const tabular = toTabular(data);
    const valueLabel = data.columns.find((c) => c.key === 'value')?.label ?? 'Value';
    const title = describe(spec, valueLabel);
    result =
      data.rows.length === 0 ? (
        <Card title={title}>
          <EmptyState
            title="No data for these filters"
            description="Try a wider date range or fewer filters."
          />
        </Card>
      ) : (
        <ChartFrame
          title={title}
          subtitle={`Based on ${formatNumber(data.n_rounds)} rounds${data.truncated ? ` · showing the first ${formatNumber(data.rows.length)} rows` : ''}`}
          option={buildExploreOption(tabular, spec.group_by, state.chartType)}
          columns={tabular.columns}
          rows={tabular.rows}
          csvName={`explorer-${spec.metric}${spec.group_by.length ? `-by-${spec.group_by.join('-')}` : ''}`}
          ariaLabel={title}
          urlKey="v"
          height={420}
          rowHref={rowLink(spec)}
        />
      );
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-text">Explorer</h1>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <Card title="Query">
            <QueryControls spec={state.spec} chartType={state.chartType} set={state.set} />
          </Card>
          <Card>
            <details open={filtersOpen} onToggle={(e) => setFiltersOpen(e.currentTarget.open)}>
              <summary className="min-h-11 cursor-pointer py-2 text-base font-medium text-text">
                Filters{filters > 0 ? ` (${filters})` : ''}
              </summary>
              <div className="pt-3">
                <FilterControls spec={state.spec} ranges={state.ranges} set={state.set} />
              </div>
            </details>
          </Card>
        </div>
        <div className="min-w-0">{result}</div>
      </div>
    </div>
  );
}
```

Create the full contents of `frontend/src/features/explorer/routes.tsx` (the route path is relative to the `/` root,
Plan 01 Decision 15, so it is served at `/explorer`; the nav item keeps the absolute URL):

```tsx
import { Compass } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: 'explorer',
    lazy: async () => ({ Component: (await import('./pages/ExplorerPage')).ExplorerPage }),
  },
];

export const nav: NavItem[] = [{ label: 'Explorer', path: '/explorer', icon: Compass, order: 60 }];
```

- [ ] **Step 7: Run the page and registry tests to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/explorer src/app`
Expected: PASS — `ExplorerPage.test.tsx` 14 tests; `navRegistry.test.ts` accepts `explorer` at order 60 and finds
`/explorer` among the registered routes; `appRoutes.test.tsx` unchanged.

Prove the Filters-panel state is load-bearing: in `ExplorerPage.tsx`, temporarily replace
`<details open={filtersOpen} onToggle={(e) => setFiltersOpen(e.currentTarget.open)}>` with
`<details open={filters > 0}>`.
Run: `cd frontend && pnpm exec vitest run src/features/explorer`
Expected: FAIL — 1 failed, `keeps the Filters panel open when the last filter is cleared` (the controlled `open` prop
drops the attribute as soon as the count reaches 0). Revert the change and re-run: PASS — 14 tests.

- [ ] **Step 8: Write the e2e spec against the seeded fixtures**

Create the full contents of `frontend/e2e/explorer.spec.ts` (keep the BOM in the regular expression as the `\uFEFF`
escape, never a literal character; the numbers are the fixture's rounds per year and per gauge):

```ts
import { readFile } from 'node:fs/promises';
import { VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';

// Signed in as a viewer; the fixtures were seeded once by auth.setup.ts (Plan 04 T2).
test.use({ storageState: VIEWER_STATE });

test('rounds by year come from the seeded fixtures', async ({ page }) => {
  await page.goto('/explorer?m=rounds&g=year');
  await expect(page.getByRole('img', { name: 'Rounds by year' })).toBeVisible();
  await expect(page.getByText('Based on 7,480 rounds')).toBeVisible();
  await page.getByRole('button', { name: 'Table' }).click();
  const table = page.getByRole('table', { name: 'Rounds by year' });
  await expect(table.getByRole('row')).toHaveCount(8);
  await expect(table.getByRole('row', { name: /^2020 843 843$/ })).toBeVisible();
  await expect(table.getByRole('row', { name: /^2025 1267 1267$/ })).toBeVisible();
  await expect(page).toHaveURL(/v=table/);
});

test('the query lives in the URL and survives a reload', async ({ page }) => {
  await page.goto('/explorer');
  await expect(page.getByRole('img', { name: 'Avg score by year' })).toBeVisible();
  await page.getByLabel('Metric').selectOption('rounds');
  await page.getByLabel('Group by').selectOption('gauge');
  await expect(page).toHaveURL(/m=rounds/);
  await expect(page).toHaveURL(/g=gauge/);
  await page.reload();
  await expect(page.getByLabel('Metric')).toHaveValue('rounds');
  await expect(page.getByLabel('Group by')).toHaveValue('gauge');
  await page.getByRole('button', { name: 'Table' }).click();
  await expect(
    page
      .getByRole('table', { name: 'Rounds by gauge' })
      .getByRole('row', { name: /^unspecified 7302 7302$/ }),
  ).toBeVisible();
});

test('the CSV export matches the query', async ({ page }) => {
  await page.goto('/explorer?m=rounds&g=year');
  await expect(page.getByRole('img', { name: 'Rounds by year' })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'CSV' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe('explorer-rounds-by-year.csv');
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.split('\r\n').slice(0, 2)).toEqual(['Year,Rounds,n', '2020,843,843']);
});

test('an invalid combination explains itself instead of breaking the page', async ({ page }) => {
  await page.goto('/explorer?m=score&g=station');
  await expect(page.getByRole('heading', { name: "This query can't run" })).toBeVisible();
  await expect(page.getByText('Grouping by station needs the Hit % metric')).toBeVisible();
});
```

Run: `cd frontend && pnpm exec prettier --write e2e && pnpm lint && pnpm typecheck && pnpm exec playwright test --list`
Expected: lint and types clean; `explorer.spec.ts` lists 4 tests under both `[mobile]` and `[desktop]`.

- [ ] **Step 9: Run the e2e suite against the compose stack**

From the worktree root (run `cd frontend && pnpm exec playwright install chromium` once if browsers are missing):

```bash
cd "$(git rev-parse --show-toplevel)"
docker build -t ghcr.io/gitgat/sunday-clays-backend:ci backend
docker build -t ghcr.io/gitgat/sunday-clays-frontend:ci -f frontend/Dockerfile .
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test)
docker compose -f compose.yaml -f compose.test.yaml down -v
```

Expected: every project passes; `explorer.spec.ts` 4 passed at both viewports (rounds by year 2020 = 843 … 2025 =
1267 from 7,480 rounds; `unspecified` gauge 7,302 rounds; the CSV named `explorer-rounds-by-year.csv` starting
`Year,Rounds,n` / `2020,843,843`; the station/score query shows `This query can't run`).

- [ ] **Step 10: Full suite, coverage, lint, types, format and build**

Run: `cd frontend && pnpm exec prettier --write src/features/explorer e2e/explorer.spec.ts`
Run: `cd frontend && pnpm exec vitest run --coverage`
Expected: every test file passes; coverage ≥90% lines and ≥90% branches overall; `src/features/explorer` ≥90% lines
and branches.
Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`
Expected: exit 0 with 0 warnings.
Run: `cd frontend && pnpm build`
Expected: the build succeeds with a separate lazy `ExplorerPage-*.js` chunk that carries ECharts; the entry chunk stays
far below the 250 KB gzip budget (C11; about 120 KB when this plan was verified).

- [ ] **Step 11: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/features/explorer frontend/e2e/explorer.spec.ts
git commit -F - <<'MSG'
feat(explorer): Explorer page with shareable URL state and e2e coverage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
MSG
```
