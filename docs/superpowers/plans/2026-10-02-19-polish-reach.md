# Polish & Reach Implementation Plan (Sub-plan 19)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers, including fix rounds, run on Sonnet. Every reviewer, re-reviewer and verifier runs on Opus. Each task gets one branch, one worktree and one PR **into `feat/polish-reach`**, never `main`. Implementers commit but never push or open PRs. The controller pushes, opens the PRs and merges them, in the waves below.

**Goal:** Make Sunday Clays easier to find, share and understand without changing any number it shows: launch switches (the mechanism every other part ships behind), name-free link previews, a first-visit tour with a glossary, a weekly recap for the club email, Add to Home Screen, club milestones, a per-profile summary card, and a page cache with warm-up that makes the busiest pages open fast.

**Architecture:** Launch switches are `app_state` rows `feature.<key>` read by `domain/features.py`; viewer routes are gated by the `feature_gate(key)` dependency (404 for a viewer while off, admin preview while off), and the SPA reads `GET /api/features` through `lib/features.ts` (`useFeature`, `FeatureGate`, `AdminPreviewBadge`, nav filtering). Link previews are a public route module `og` (HTML meta page plus Pillow-drawn PNGs from a name-free `PreviewFacts`) that Caddy routes crawlers to, with a `/l/` share prefix. The tour, glossary, PWA shell, install tip, milestones card and chart, summary card and recap page are frontend features in their own folders, backed where needed by three new read endpoints (`/api/club/milestones`, `/api/shooters/{id}/summary`, `/api/admin/recap/{date}`). The page cache is an inner middleware under the ETag middleware that stores finished 200 JSON bodies of an exact allowlist of GET routes in the UNLOGGED table `response_cache` (migration `0009_response_cache`), keyed by app version, `data_version`, local date, role and URL; a queued `page_warm` job fills it for the default pages after every `data_version` change and each local midnight.

**Tech Stack:** Python 3.13 · FastAPI 0.141 · SQLAlchemy 2.1 · Alembic · Pydantic v2 · Pillow 12 (new) · pytest · Postgres 17 (psycopg 3) · React 19 · TypeScript (strict) · TanStack Query v5 · React Router v7 · ECharts via `ChartFrame` · Tailwind v4 · openapi-fetch · Vitest + Testing Library + MSW · Playwright · Caddy 2.11.

**Spec:** `docs/superpowers/specs/2026-10-02-19-polish-reach-design.md` (owner-approved 2026-10-02, including the §3.7 amendment, decisions D1–D37). The plan argues from the spec; executors read both. Where this plan departs from the spec's §7 delivery outline or settles something the spec leaves open, the **Decisions** section below says what and why.

**Base:** `main` @ `e4559db` (Plans 15, 16 and 17 merged, plus the Plan 19 and 20 specs). **Pre-flight** (controller, before each wave): every Create target must not exist, every Modify target must exist, and every "replace" block must occur exactly once in the task's base.

**Delivery:** The integration branch is `feat/polish-reach`, cut from `main`. Task branches are `task/19-<T>-<slug>` (for example `task/19-1-switches-backend`), cut from `feat/polish-reach` after the previous wave has merged. Every PR targets `feat/polish-reach`, and CI (`ci-ok`, which includes the full Playwright suite) must pass. Commits use the gitgat identity, which is already in the repo config. Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; an implementer on another model names its own model there instead. `feat/polish-reach` ships to `main` in one PR the owner approves after a local preview (Task 10's owner-preview step). Every user-facing feature merges switched **off** in production (`FEATURES_DEFAULT_ON` is empty there); the page cache merges **on** (D36).

## Global Constraints

**Binding owner rules (verbatim from the spec, §1):**

| # | Rule | Where it is enforced in this plan |
|---|---|---|
| R1 | App copy never uses he/she/his/her (or him/hers/himself/herself). | All copy in §3. There is no central lint; each new copy file gets its own language test, named in §5.1, using the same banned-word list as the existing per-feature `explainers.test.ts` files (plus "class"). |
| R2 | Named-shooter copy is positive or neutral only. | Recap (§3.3), summary card zero-hiding (§3.6, D19). |
| R3 | No rating ranking, rivals or head-to-head. | Recap shows the podium only (D15); milestones are club-level (§3.5); summary card has no rank. |
| R4 | Every data chart has Table, CSV, fullscreen and an ELI5 explainer. | The one new chart (§3.5 "Club totals over time") uses `ChartFrame`. |
| R5 | Time windows use the header window: 8W/3M/6M/12M/YTD/All and custom. | Summary card (§3.6) and the milestones chart (§3.5). |
| R6 | The password gate stays. | Only `/api/og/*` is public, and it serves no names or scores (§3.1, D6). |
| R7 | Nothing is removed from Home. | Home only gains: `data-tour` attributes, one milestone card, one install tip (§3.2, §3.4, §3.5). |
| R8 | Real names never go in tracked files; tests use invented names. | Fixture pseudonyms only (`Devlin, Sid`, `Kaplan, Noel`, `Hadley, Ike`, `Kim, Pat`, …). |
| R9 | Persistent data binds under `/var/data/sunday-clays/<svc>`, never named volumes. | Plan 19 adds no volume. Its one new table, `response_cache`, lives in the existing Postgres data directory (D22, D28). |
| R10 | Images are multi-arch (amd64 + arm64). | The one new dependency, Pillow, ships manylinux wheels for both (D8). |
| R11 | No IPs stored (rate limits use `ip_fingerprint`), no access log. | §4. |

**Repo conventions (carried from Plans 15–17):**

- Python `3.13`, Node `22` LTS and Postgres `17`, with `uv` (backend) and `pnpm` (frontend). The only new package is Pillow (`pillow>=12.0`, Task 3, `uv add`). Never edit any other entry of `[project].dependencies`, `[dependency-groups]`, `dependencies` or `devDependencies`; `uv.lock` changes only through Task 3's `uv add`, and `pnpm-lock.yaml` never changes.
- Coverage floor is **90% lines AND 90% branches**, backend and frontend measured separately. `ratchets/` is controller-only; the bundle budgets in `ratchets/budgets.json` (`entry_js_gz_kb` 250, `total_js_gz_kb` 1600) are absolute and must still pass.
- Backend gates (from `backend/`): `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src`, `uv run pytest -q --cov --cov-report=term-missing` (coverage ≥ 90%). pytest runs with `filterwarnings = error`. **Never use `Select.distinct(*cols)` (DISTINCT ON), which is deprecated in SQLAlchemy 2.1.**
- Frontend gates (from `frontend/`): `pnpm gen:api`, `pnpm lint` (`eslint --max-warnings 0`), `pnpm typecheck` (which runs `gen:api` first), `pnpm exec prettier --check .`, `pnpm exec vitest run --coverage` (≥ 90%). `src/api/schema.d.ts` is gitignored and regenerated.
- e2e: every task with UI runs its new or changed specs on the local e2e stack at **390×844 (`mobile`) and 1440×900 (`desktop`)**; admin mutations run in the `admin-mutations` project. A task that changes visible copy updates the e2e that asserts it, in the same task.
- **Strict TDD with evidence:** every production change starts from a failing test. Each implementer report pastes the RED output (the failing run) and then the GREEN output (the passing run) for every step pair. Reviewers re-run the task's new tests on the task's base to prove they fail there. Tests are mutation-proof: each names the mutation it kills where that is not obvious.
- Migrations are expand-only and compatible with the previous release (`api` runs `alembic upgrade head` on start). This plan's one migration is `0009_response_cache` (`down_revision = "0008"`); Plan 20 renumbers to `0010` (spec D5, §6).
- Routers are discovered (C2): `api/routes/<name>.py` needs a viewer, `admin_<name>.py` an admin, and `_<name>.py` is not discovered. `api/app.py` is edited only where the spec says: Task 3's `PUBLIC_ROUTE_MODULES` line (D6) and Task 11's one `add_middleware` line plus its `page_cache_allowlist` parameter (D30, D31). `frontend/src/app/router.tsx` is closed to edits (C10). Every `features/<name>/mocks.ts` `handlers` export is merged into the shared MSW server, which errors on unhandled requests.
- Viewports: phone `390×844` and desktop `1440×900` are both first-class. Tap targets ≥ 44 px, no page scrolls sideways.
- Dark theme only, existing Tailwind tokens. Never hard-code a colour in the SPA (the OG images and icons are drawn server-side with the spec's fixed hex colours, D8/D9).
- Copy says "Sunday", never "event", and never uses "class" (memory: neutral pronouns).
- Stage files explicitly (`git add <paths>`). Never `git add -A`: the repo root holds untracked workbooks.
- Workflows stay at about 10 agents or fewer; non-conflicting lanes run in parallel (the waves below).
- Actions budget: Pro included minutes plus the $75 Actions budget. If CI is blocked by billing, stop and tell the owner.

## Review Focus

Five conditions the spec implies but no feature test exercises directly, most likely to bite first. Each is pinned to a test in the task that owns the code.

1. **A switch flipped off while a cached 200 sits in a browser or in the page cache.** Expected: a gated route is never ETagged (it answers 404 off, so no 304 can revalidate a stale 200) and is never in the page-cache allowlist. Tests: T1 `test_gated_route_off_is_untagged_404_even_with_if_none_match`; T11 `test_allowlist_has_no_gated_admin_or_public_route` and `test_excluded_routes_are_never_stored`.
2. **A logged-out load or a flaky network wipes an installed PWA.** Expected: the service worker is unregistered only on `settled && !on` for a viewer; a pending, failed or 401 `/api/features` query and `/login` leave it alone. Tests: T9 `pwaLifecycle.test.tsx` ("leaves the registration alone while pending / after a network error / after a 401 / on /login"); T9 e2e "logging out keeps the registration".
3. **Crawler routing order and the open redirect.** Caddy sorts sibling `handle` blocks, so a crawler on `/l/…` could get the 302 instead of the meta page, and `/l//evil.com` could become a protocol-relative `Location`. Expected: one `route { … }` block, crawler first; every unsafe share path redirects to `/`. Tests: T4 `test_crawler_ua.sh` table and `link-previews.spec.ts` ("crawler on the share prefix gets the meta page, not a 302", "open-redirect guard").
4. **The page cache serving a body the route would not answer now.** A new `data_version`, a new local date, another role, an undeclared query parameter (`?_=1`), a HEAD, a 4xx/5xx, a full table, or a failing cache query. Expected: the uncached answer, byte for byte, and nothing wrong stored. Tests: T11 `test_page_cache.py` (byte-identical over every allowlisted template, bump, date roll, role separation, excluded routes, fail-open, caps).
5. **Warm-up warming the wrong keys.** If `warm_targets` sends a different query string than the SPA, every warm row is dead weight and Home stays slow. Expected: every default-page request the SPA makes is in `targets`. Tests: T12 `warm_targets` unit test (8W `since=2026-08-03&as_of=2026-09-27`, race `from=2025-09-28&to=2026-09-27`) and the e2e pin test in `page-cache.spec.ts`.

## Decisions

These settle what the spec's delivery outline (§7) leaves open or gets wrong. Every other choice is the spec's.

1. **Waves changed from §7 (dependency errors).** §7 runs T5 (tour + glossary) beside T6 (club milestones) and T7 (summary card). That cannot work as written: (a) T6's and T7's explainers carry `terms` (§3.5, §3.6), a field and a `GlossaryTermId` type that T5 creates; (b) T5 retrofits `terms` into every existing `features/*/explainers.ts`, including `features/club/explainers.ts`, which T6 also edits. Fix: the glossary **data** (`features/glossary/terms.ts`, `GlossaryTermId`) and the `Explainer.terms` field move into **T2** (wave 2), so T7 can run in wave 3 beside T5. **T6 moves to wave 4** (after T5's retrofit of `features/club/explainers.ts`), beside T9. **T8 moves to wave 5**, because the recap's `club_milestones` list calls T6's `club_milestones()`. T10 and T11 stay in wave 5 (their files are disjoint from T8's); T12 stays last. The waves table below is authoritative.
2. **The race warm target starts on 2025-09-28, not 2025-09-27.** §5.1 wrote `from=2025-09-27` (the spec now carries an amendment line pointing here, so no one "fixes" it back), but the SPA's 12M window is `monthsBack(anchor, 12)` = anchor − 12 months **+ 1 day** (`lib/timeWindowChoice.ts`), so the race page sends `from=2025-09-28`. §3.7.5 says the targets must equal what the SPA sends, and the e2e pin test enforces it, so the SPA's rule wins. `warm_targets` reproduces `monthsBack` in Python (`_months_back`).
3. **Explainer keys.** The existing `features/club/explainers.test.ts` requires an explainer key for every `urlKey` in the feature, so the "Club totals over time" explainer is keyed **`ctot`** (its `urlKey`), not `club-totals`. The milestone list card (§3.5 "Club milestones", scope `all-time`) has no copy in the spec; this plan writes it (Task 6, key `club-milestones`). The home card's explainer is `club-milestone` as specified.
4. **Explainer `terms` beyond the spec's lists.** T5's trigger lint would fail on two new explainers as specified: `summary-card` says "all round types" (trigger `round-types`) and "the chosen time window" (trigger `time-window`), and `ctot` says "include special shoots" and "Clays thrown". So `summary-card` gets `terms: ['special-shoot', 'personal-best', 'streak', 'round-types', 'time-window']` (T7 runs in wave 3 beside T5 and never sees T5's lint, so its terms must already be complete) and `ctot` gets `terms: ['clays-thrown', 'special-shoot', 'held-sunday']`. `GLOSSARY_TRIGGERS` lists a trigger for all 15 ids (the spec gives nine "for example").
5. **The page-cache switch read.** D31 says the ETag middleware's `_tag_inputs` "query" also reads `feature.page_cache`. It is read in the **same session**, as a second statement after `cache.read_data_version(session)`, not folded into one SQL statement. That keeps `cache.read_data_version` as the single monkeypatchable reader that the memo, the ETag and `/api/meta` share (its docstring's contract), and costs one cheap primary-key lookup on an already-open connection.
6. **`create_app(*, page_cache_allowlist=ALLOWLIST)`.** D30 makes `create_app` raise when an allowlisted template names no GET route. Three existing tests replace `discover_routers` with probe routers (`tests/unit/api/test_role_wiring.py`, `tests/unit/api/test_bodylimit.py`, `tests/integration/test_db.py`); Task 11 makes them call `create_app(page_cache_allowlist=())`. Production (`uvicorn --factory`) calls `create_app()` unchanged.
7. **`GET /api/admin/page-cache` lands in two steps.** Task 11 creates it without `targets`; Task 12 adds `targets` together with `warm_targets()`. No placeholder field ships.
8. **A warm target "fails" when it raises or answers anything but 200.** The in-process `TestClient` is built with `raise_server_exceptions=False`, so a route error arrives as a 500, not an exception; both count in `failed`.
9. **`page_warm` commits the prune before warming.** The requests run through the real app with their own sessions; committing the prune first means no request ever waits on a row the job deleted but has not committed. The commit comes after `warm_targets`' read, so the job's own connection holds no open transaction while the (up to 180 s) loop runs; the `last_warm` write afterwards opens a fresh one that the worker commits.
10. **The stampede test runs on `committed_engine`, not the fx world.** Concurrent requests need one session each (the production `get_session`), and the fx world shares one rolled-back session. On the empty database `/api/insights/home` answers its empty feed; the call counter wraps `api.routes.insights.held_dates`, which runs exactly once per route execution.
11. **Small, explicit API shapes the spec leaves open:** `FeatureSwitchIn` uses `StrictBool` and forbids extra keys (so `{"enabled": "yes"}` is a 422, §3.0); the `og` routes are `include_in_schema=False` (they are not JSON and the SPA never calls them); `FEATURES_DEFAULT_ON` is set on the `api` service only (the worker never reads feature switches; `page_cache` ignores it, D36); `Card` gains an optional `tour` prop and `NavItem` an optional `tourId` so `data-tour` attributes need no wrapper elements; `AppShell` gains a `featureVisible` prop that `SessionShell` fills from `useFeatures`, so `AppShell`'s own tests need no query client.
12. **The Features page gets a read-only e2e in Task 2** (`admin-features.spec.ts`, admin storage state, both sizes). §5.3 tests the page only through mutations (Task 10, 12); the gate "e2e where there is UI" needs it earlier.
13. **The crawler UA script runs in CI.** Task 4 adds one step to the `e2e` job in `.github/workflows/ci.yml` after the stack is up: `deploy/caddy/test_crawler_ua.sh http://localhost:8080 ghcr.io/gitgat/sunday-clays-frontend:ci`.
14. **Caddy layout.** Caddy runs `handle` before `route` in its fixed directive order, and the site ends in a catch-all `handle`, so the spec's top-level `route { … }` (§3.1.3) would never run. Task 4 keeps the spec's behaviour with a top-level `handle @crawler` plus a `handle /l/*` whose inner `route` checks `@crawler` first, then `@share_unsafe`, then redirects (details in Task 4). The UA table moves to `deploy/caddy/user-agents.tsv` so the script and the e2e read one list (§3.1.3 "the same table").
15. **Glossary order.** "Alphabetical" (§3.2.2) is read as alphabetical by id, which is the spec table's own order; sorting by display term would put "Sunday with full results" among the S's, away from its id `held-sunday`.
16. **The About sentence is behind `link_previews`.** §4 adds it to the privacy list without a condition, but it describes a feature that ships off in production (D25), and every user-facing addition ships behind its switch. So T10 shows it only while `useFeature('link_previews').visible` (admin preview badge while off), the pattern Plan 20 uses for its About lines. About shows five points with the switch off (the all-off e2e checks it) and six on (the e2e stack, `about.spec.ts`).
17. **D14's left-out trophies are a code set.** D14 and §3.6 name First Win, Podium, Station Top Gun and Hardest-Station Clean and say "category competition", but the registry files Station Top Gun and Hardest Station Clean under `stations`. Filtering by category would count and name them. `analytics.summary.LEFT_OUT_TROPHY_CODES` lists the four codes; the summary card and the recap both use it through `trophy_title`.

## File map

| File | Task | Responsibility |
|---|---|---|
| `backend/src/sunday_clays/domain/features.py` | 1, 11 | Feature registry, switch reads/writes, Pydantic shapes; T11 adds `kind`/`default_on`/`page_cache` |
| `backend/src/sunday_clays/api/routes/_features.py` | 1 | `feature_gate(key)` |
| `backend/src/sunday_clays/api/routes/features.py` | 1 | `GET /api/features` |
| `backend/src/sunday_clays/api/routes/admin_features.py` | 1 | `GET/PUT /api/admin/features…` |
| `backend/src/sunday_clays/api/etag.py` | 1, 3, 11 | No-store/no-ETag for `/api/features`, `/api/og/`; T11 reads the switch in `_tag_inputs` |
| `backend/src/sunday_clays/config.py` | 1, 3, 11 | `features_default_on`, `public_base_url`, `page_cache_enabled` |
| `compose.test.yaml` | 1 | `FEATURES_DEFAULT_ON` = all six keys on `api` |
| `frontend/src/lib/features.ts` | 2 | `useFeatures`, `useFeature`, `featureState` |
| `frontend/src/components/FeatureGate.tsx`, `components/ui/AdminPreviewBadge.tsx` | 2 | Gate and badge |
| `frontend/src/app/ErrorBoundary.tsx`, `app/registry.ts`, `components/layout/{nav.ts,AppShell.tsx}`, `features/auth/components/SessionShell.tsx` | 2 | `NotFoundView`, `NavItem.feature`, nav filtering |
| `frontend/src/features/admin-features/*` | 2, 11 | Features page; T11 adds the Infrastructure group |
| `frontend/src/features/glossary/terms.ts`, `components/charts/types.ts`, `src/test/language.ts` | 2 | Glossary data, `Explainer.terms`, banned words |
| `backend/src/sunday_clays/og/*`, `api/routes/og.py`, `api/app.py` | 3 | Link previews, logo, icons |
| `frontend/public/icons/*.png` | 3 | Generated icons (committed) |
| `deploy/caddy/Caddyfile`, `deploy/caddy/test_crawler_ua.sh`, `deploy/README.md`, `.github/workflows/ci.yml` | 4, 12 | Crawler routing, `/l/`, PWA headers, CSP, runbook; T12 adds the "Page cache" runbook section |
| `frontend/e2e/link-previews.spec.ts` | 4 | e2e |
| `frontend/src/features/tour/*`, `features/glossary/*`, `components/ui/Explainer.tsx`, `features/*/explainers.ts` | 5 | Tour, glossary page, "Words used here", trigger lint, terms retrofit |
| `frontend/e2e/{fixtures.ts,tour.spec.ts,glossary.spec.ts}` | 5, 9 | `tourSeen` (T5), `installTipSeen` (T9) |
| `backend/src/sunday_clays/analytics/club_milestones.py`, `api/routes/club.py` | 6 | Milestones |
| `frontend/src/features/club/*` | 6 | Home card, Club section, chart |
| `backend/src/sunday_clays/analytics/summary.py`, `analytics/personal_best.py`, `api/routes/shooters.py`, `api/routes/events.py` | 7 | Summary endpoint; the one PB rule shared with `event_notables` |
| `frontend/src/features/summary/*`, `lib/share.ts` | 7 | Summary card, `renderElementToPng`, `downloadElementAsImage` |
| `backend/src/sunday_clays/api/routes/admin_recap.py` | 8 | Recap facts |
| `frontend/src/features/admin-recap/*` | 8 | Recap page and formatting |
| `frontend/src/features/pwa/*`, `lib/{chunkReload,installPrompt}.ts`, `src/build/pwaShell.ts`, `vite.config.ts`, `index.html`, `public/manifest.webmanifest`, `main.tsx`, `playwright.config.ts` | 9 | PWA |
| `frontend/e2e/features.admin-mutations.spec.ts`, `features/about/*` | 10, 12 | Switch e2e, About sentence; T12 adds the page-cache test |
| `backend/migrations/versions/0009_response_cache.py`, `models/page_cache.py`, `api/page_cache.py`, `api/routes/admin_page_cache.py` | 11 | Page cache |
| `backend/src/sunday_clays/jobs/page_warm.py`, `jobs/scheduler.py`, `jobs/worker.py` | 12 | Warm-up |
| `frontend/e2e/page-cache.spec.ts` | 12 | e2e incl. the pin test |

## Waves

| Wave | Tasks (parallel lanes, disjoint files) | Needs |
|---|---|---|
| 1 | T1 launch switches backend | `main` |
| 2 | T2 switches frontend (incl. glossary data and `Explainer.terms`) ∥ T3 link previews backend | T1 |
| 3 | T4 Caddy, runbook, CI step, `link-previews.spec.ts` ∥ T5 tour + glossary ∥ T7 summary card | T2, T3 |
| 4 | T6 club milestones ∥ T9 PWA | T5 (explainers retrofit; tour state for the install tip) |
| 5 | T8 weekly recap ∥ T10 all-switches e2e + About sentence ∥ T11 page cache | T6 (recap milestones; T11's pin tests see every gated route), T7, T9 |
| 6 | T12 warm-up | T10 (`features.admin-mutations.spec.ts`), T11 |

Lane check (files that look shared but are not): T4 edits only `deploy/`, `.github/workflows/ci.yml` and `frontend/e2e/link-previews.spec.ts` (`index.html` is T9's). T5 and T7 share no file (`lib/share.ts` is T7's; `components/ui/Card.tsx`, `NavList.tsx`, `registry.ts` are T5's in wave 3). T6 and T9 both add a `homeWidget.tsx`, in different feature folders. T8, T10 and T11 touch disjoint files (T11's frontend is `features/admin-features/*`; T10's is `features/about/*` and `e2e/features.admin-mutations.spec.ts`; T8's is `features/admin-recap/*`), except `backend/tests/conftest.py`: T8 appends `fx_special_admin_client` at the end of the file and T11 inserts its autouse fixture after `_fresh_settings_cache` near the top, so the two hunks are far apart and merge without a conflict. Neither may move its fixture.

## Running the e2e stack

From the worktree root (each task uses its own project name and port, so parallel lanes never share a stack):

```bash
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh   # once per worktree
E2E_PORT=18080 IMAGE_TAG=task19 docker compose -p task19-<T> -f compose.yaml -f compose.test.yaml build
E2E_PORT=18080 IMAGE_TAG=task19 docker compose -p task19-<T> -f compose.yaml -f compose.test.yaml up -d --wait
cd frontend && pnpm exec playwright install chromium
E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test <specs>
```

Afterwards: `docker compose -p task19-<T> -f compose.yaml -f compose.test.yaml down -v`. Use a different `E2E_PORT` per lane in the same wave (18080, 18081, 18082).

From Task 1 on, `compose.test.yaml` sets `FEATURES_DEFAULT_ON` to all six keys on `api`, so the read-only projects see every feature (D4). From Task 5 on, `e2e/fixtures.ts`'s `tourSeen` fixture (default `true`) keeps the tour out of every existing spec; from Task 9 on, `installTipSeen` does the same for the install tip, and `playwright.config.ts` blocks service workers for every spec except `pwa.spec.ts`. From Task 11 on, the stack runs with the page cache on (the default), so the read-only projects exercise cache hits.

A mutating spec (`*.admin-mutations.spec.ts`) runs only in the `admin-mutations` project: `pnpm exec playwright test --project=admin-mutations <spec>`. It depends on the `desktop` and `mobile` projects, so pass `--no-deps` to run it alone on a stack that already has `e2e/.auth/*.json` from an earlier run (`pnpm exec playwright test --project=setup` writes them).

## Per-task gates (every task, before its final commit)

The code blocks in this plan are correct but not always formatter-exact. Run the formatters on the files you touched first (`uv run ruff format <files>` and `uv run ruff check --fix <files>` in `backend/`, `pnpm exec prettier --write <files>` in `frontend/`), then the checks.

Backend tasks (from `backend/`):

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src
uv run pytest -q --cov --cov-report=term-missing   # coverage total >= 90%
```

Frontend tasks (from `frontend/`):

```bash
pnpm gen:api && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage
```

Tasks with UI also run their e2e specs at both sizes on the local stack (see each task's last step). Paste the tail of each gate run (pass counts, coverage totals) in the report.

---
### Task 1: Launch switches backend (`task/19-1-switches-backend`, wave 1)

**Files:**
- Create: `backend/src/sunday_clays/domain/features.py`
- Create: `backend/src/sunday_clays/api/routes/_features.py`
- Create: `backend/src/sunday_clays/api/routes/features.py`
- Create: `backend/src/sunday_clays/api/routes/admin_features.py`
- Modify: `backend/src/sunday_clays/api/etag.py` (the two prefix tuples)
- Modify: `backend/src/sunday_clays/config.py` (one setting)
- Modify: `compose.test.yaml` (`api.environment`)
- Modify: `backend/tests/unit/api/test_etag_helpers.py` (two parametrize rows)
- Create: `backend/tests/unit/domain/test_features_copy.py`
- Create: `backend/tests/integration/domain/test_features_store.py`
- Create: `backend/tests/integration/api/test_features_api.py`

**Interfaces:**
- Consumes: `auth.deps.require_viewer`, `admin_actor`, `Actor`, `record_audit`; `auth.sessions.Role`; `db.SessionDep`; `config.Settings`, `get_settings`; `domain.errors.NotFoundError`; `analytics.insights.lints.lint_text`; fixtures `session`, `committed_engine`, `anon_client`, `viewer_client`, `admin_client`, `auth_env`.
- Produces (T2, T3, T6, T7, T8, T10, T11 rely on these):
  - `domain.features`: `FeatureKey = Literal["link_previews", "tour_glossary", "weekly_recap", "pwa", "club_milestones", "summary_card"]`; `@dataclass(frozen=True) Feature(key: FeatureKey, label: str, description: str)`; `FEATURES: tuple[Feature, ...]` (the six, in the order above); `KEY_PREFIX = "feature."`; `feature(key: str) -> Feature` (raises `NotFoundError("feature_not_found")`); `read_switches(session: Session, settings: Settings) -> dict[FeatureKey, bool]`; `switch_on(session: Session, settings: Settings, key: FeatureKey) -> bool`; `list_switches(session, settings) -> list[FeatureSwitchOut]`; `set_switch(session, settings, key: str, enabled: bool) -> FeatureSwitchOut`; Pydantic `FeatureSwitchOut(key: FeatureKey, label: str, description: str, enabled: bool, updated_at: datetime | None, updated_on: date | None)`, `FeatureSwitchIn(enabled: StrictBool)` (extra keys forbidden), `FeaturesOut(switches: dict[FeatureKey, bool])`.
  - `api.routes._features.feature_gate(key: FeatureKey) -> Any` (a `Depends(...)`; the inner callable carries attribute `feature_gate_key = key`).
  - `GET /api/features` → `FeaturesOut` (viewer: enabled keys only; admin: every key). `GET /api/admin/features` → `list[FeatureSwitchOut]`. `PUT /api/admin/features/{key}` body `FeatureSwitchIn` → `FeatureSwitchOut`, audit action `feature_switch` with `{key, enabled}`; 404 `feature_not_found`; 422 for any other body.
  - `config.Settings.features_default_on: str = ""` (env `FEATURES_DEFAULT_ON`, comma-separated keys).

- [ ] **Step 1: Write the failing copy test**

Create `backend/tests/unit/domain/test_features_copy.py`:

```python
"""R1 for the Features page copy: no he/she/his/her/him/hers/himself/herself and no "class"."""

import pytest

from sunday_clays.analytics.insights.lints import lint_text
from sunday_clays.domain.features import FEATURES, Feature

BANNED_CODES = ("pronoun", "class")


@pytest.mark.parametrize("feature", FEATURES, ids=lambda f: f.key)
def test_feature_label_and_description_use_no_banned_word(feature: Feature) -> None:
    for text in (feature.label, feature.description):
        problems = [p for p in lint_text(text, named=False) if p.startswith(BANNED_CODES)]
        assert problems == [], text


def test_the_lint_used_here_does_catch_the_banned_words() -> None:
    # Kills a mutation that filters on the wrong lint codes: both words must still be caught.
    assert any(p.startswith("pronoun") for p in lint_text("Her preview", named=False))
    assert any(p.startswith("class") for p in lint_text("A class of shooter", named=False))


def test_the_registry_holds_exactly_the_six_feature_keys_in_order() -> None:
    assert [f.key for f in FEATURES] == [
        "link_previews",
        "tour_glossary",
        "weekly_recap",
        "pwa",
        "club_milestones",
        "summary_card",
    ]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest -q tests/unit/domain/test_features_copy.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'sunday_clays.domain.features'`.

- [ ] **Step 3: Write the failing store tests**

Create `backend/tests/integration/domain/test_features_store.py`:

```python
"""Launch-switch storage (Plan 19 D1, D4, D26; §5.1, §5.2)."""

import logging
import threading
from datetime import date, datetime

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import record_audit
from sunday_clays.config import Settings
from sunday_clays.domain import features
from sunday_clays.domain.errors import NotFoundError


def _settings(default_on: str = "") -> Settings:
    return Settings.model_construct(features_default_on=default_on, timezone="America/Los_Angeles")


def _put_raw(session: Session, key: str, raw_json: str) -> None:
    session.execute(
        text("INSERT INTO app_state (key, value) VALUES (:k, CAST(:v AS jsonb))"),
        {"k": f"feature.{key}", "v": raw_json},
    )


def test_a_missing_row_is_off(session: Session) -> None:
    expected = {f.key: False for f in features.FEATURES}
    assert features.read_switches(session, _settings()) == expected


def test_features_default_on_turns_a_missing_row_on(session: Session) -> None:
    switches = features.read_switches(session, _settings(" pwa, summary_card ,"))
    assert switches["pwa"] is True
    assert switches["summary_card"] is True
    assert switches["link_previews"] is False


def test_a_stored_false_beats_the_default(session: Session) -> None:
    features.set_switch(session, _settings(), "pwa", False)
    assert features.read_switches(session, _settings("pwa"))["pwa"] is False


def test_a_stored_true_is_on(session: Session) -> None:
    out = features.set_switch(session, _settings(), "summary_card", True)
    assert out.enabled is True
    assert features.read_switches(session, _settings())["summary_card"] is True


@pytest.mark.parametrize("raw", ['"on"', '{"enabled": "yes"}', "null", '{"updated_at": "x"}'])
def test_a_corrupt_value_reads_as_off_with_one_warning_naming_the_key_only(
    session: Session, caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    _put_raw(session, "tour_glossary", raw)
    with caplog.at_level(logging.WARNING, logger="sunday_clays.domain.features"):
        switches = features.read_switches(session, _settings("tour_glossary"))
    assert switches["tour_glossary"] is False  # corrupt is off, never the default
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "tour_glossary" in warnings[0].getMessage()
    assert "yes" not in warnings[0].getMessage() and '"on"' not in warnings[0].getMessage()


def test_an_unknown_key_is_feature_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError) as caught:
        features.set_switch(session, _settings(), "nope", True)
    assert caught.value.code == "feature_not_found"


def test_updated_at_is_the_database_clock_and_updated_on_the_club_date(session: Session) -> None:
    db_now = session.execute(text("SELECT now()")).scalar_one()
    out = features.set_switch(session, _settings(), "pwa", True)
    assert out.updated_at == db_now  # now() is the transaction start, so equal, not "close"


def test_updated_on_converts_utc_to_the_club_timezone(session: Session) -> None:
    _put_raw(session, "pwa", '{"enabled": true, "updated_at": "2026-10-03T05:30:00+00:00"}')
    (row,) = [s for s in features.list_switches(session, _settings()) if s.key == "pwa"]
    assert row.updated_at == datetime.fromisoformat("2026-10-03T05:30:00+00:00")
    assert row.updated_on == date(2026, 10, 2)  # 22:30 on Oct 2 in Los Angeles


def test_list_switches_reports_never_changed_rows_with_no_dates(session: Session) -> None:
    rows = features.list_switches(session, _settings())
    assert [r.key for r in rows] == [f.key for f in features.FEATURES]
    assert all(r.updated_at is None and r.updated_on is None for r in rows)


def test_two_concurrent_puts_of_one_key_are_last_writer_wins(committed_engine: Engine) -> None:
    """§5.2: two admins flip one key at once. The row ends with exactly one writer's value and its
    database now(), that writer is the one that committed last, and both flips are audited.

    "Last" is read from the database, not from thread scheduling: each writer takes
    clock_timestamp() after its upsert, inside its transaction. The second upsert blocks on the
    first writer's row lock until that commit, so its clock_timestamp() is the later one."""
    barrier = threading.Barrier(2)
    writes: list[tuple[bool, datetime, datetime]] = []
    lock = threading.Lock()

    def flip(enabled: bool) -> None:
        with Session(committed_engine) as s:
            started = s.execute(text("SELECT now()")).scalar_one()
            barrier.wait()
            out = features.set_switch(s, _settings(), "weekly_recap", enabled)
            # the two calls PUT /api/admin/features/{key} makes, in its one transaction
            record_audit(s, None, "admin", "feature_switch", {"key": out.key, "enabled": out.enabled})
            wrote_at = s.execute(text("SELECT clock_timestamp()")).scalar_one()
            s.commit()
            with lock:
                writes.append((enabled, started, wrote_at))

    threads = [threading.Thread(target=flip, args=(v,)) for v in (True, False)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(writes) == 2
    last_enabled, last_started, _ = max(writes, key=lambda w: w[2])
    with Session(committed_engine) as s:
        (row,) = [r for r in features.list_switches(s, _settings()) if r.key == "weekly_recap"]
        audits = s.execute(
            text("SELECT details FROM audit_log WHERE action = 'feature_switch' ORDER BY id")
        ).scalars().all()
    assert row.enabled is last_enabled
    assert row.updated_at == last_started  # the later transaction's database now()
    assert sorted(a["enabled"] for a in audits) == [False, True]  # exactly two audit rows
    assert {a["key"] for a in audits} == {"weekly_recap"}
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/domain/test_features_copy.py tests/integration/domain/test_features_store.py`
Expected: FAIL, both files with `ModuleNotFoundError: No module named 'sunday_clays.domain.features'`. Paste this as the RED for Steps 3–6.

- [ ] **Step 5: Add the setting and the registry**

In `backend/src/sunday_clays/config.py`, replace

```python
    page_view_limit: int = 600  # Plan 16: page-view beacons per IP per 10 minutes
```

with

```python
    page_view_limit: int = 600  # Plan 16: page-view beacons per IP per 10 minutes
    # Plan 19 D4: comma-separated feature keys treated as on while their app_state row is missing
    features_default_on: str = ""
```

Create `backend/src/sunday_clays/domain/features.py`:

```python
"""Launch switches (Plan 19 §3.0): one ``app_state`` row per key, ``feature.<key>``.

The value is ``{"enabled": bool, "updated_at": "<ISO timestamp>"}``. ``updated_at`` comes from
the database (``now()`` inside the upsert), never the app clock. A missing row means off, unless
the key is listed in ``settings.features_default_on`` (D4). A corrupt value reads as off and logs
one warning per read that names the key only, never the stored value.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, Literal, get_args
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.domain.errors import NotFoundError

logger = logging.getLogger(__name__)

FeatureKey = Literal[
    "link_previews",
    "tour_glossary",
    "weekly_recap",
    "pwa",
    "club_milestones",
    "summary_card",
]
KEY_PREFIX: Final = "feature."


@dataclass(frozen=True)
class Feature:
    key: FeatureKey
    label: str
    description: str


FEATURES: Final[tuple[Feature, ...]] = (
    Feature(
        "link_previews",
        "Link previews",
        "Links shared in chat apps show the Sunday's date, how many shot and the round type. "
        "While off, every link shows the plain club preview.",
    ),
    Feature(
        "tour_glossary",
        "Welcome tour and glossary",
        'A 5-step tour on a first visit to Home, the Glossary page, and "Words used here" '
        "links in chart explainers.",
    ),
    Feature(
        "weekly_recap",
        "Weekly recap",
        "Admin tool: paste-ready text and an image of a Sunday for the club email.",
    ),
    Feature(
        "pwa",
        "Add to Home Screen",
        "Lets phones install the app, and shows a small install tip on Home.",
    ),
    Feature(
        "club_milestones",
        "Club milestones",
        "Club totals such as clays thrown and Sundays held, dated at the Sunday each round "
        "number was passed. Home card and Club page.",
    ),
    Feature(
        "summary_card",
        "Summary card",
        "A shareable card on every profile for the chosen time window.",
    ),
)
_BY_KEY: Final[dict[str, Feature]] = {f.key: f for f in FEATURES}
assert set(_BY_KEY) == set(get_args(FeatureKey)), "FEATURES must list every FeatureKey once"


class FeatureSwitchOut(BaseModel):
    key: FeatureKey
    label: str
    description: str
    enabled: bool
    updated_at: datetime | None
    updated_on: date | None  # updated_at as a date in the club timezone (D26)


class FeatureSwitchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class FeaturesOut(BaseModel):
    switches: dict[FeatureKey, bool]


def feature(key: str) -> Feature:
    """The registered feature for ``key``; 404 ``feature_not_found`` otherwise."""
    found = _BY_KEY.get(key)
    if found is None:
        raise NotFoundError("feature_not_found", f"No feature switch named {key!r}")
    return found


def _default_on(settings: Settings) -> frozenset[str]:
    return frozenset(k.strip() for k in settings.features_default_on.split(",") if k.strip())


def _stored(value: Any, key: str) -> tuple[bool, datetime | None] | None:
    """(enabled, updated_at) from a stored value; None (and a warning) when it is corrupt."""
    if isinstance(value, dict) and isinstance(value.get("enabled"), bool):
        raw = value.get("updated_at")
        try:
            updated = datetime.fromisoformat(raw) if isinstance(raw, str) else None
        except ValueError:
            updated = None
        return bool(value["enabled"]), updated
    logger.warning("feature switch %s has a corrupt value; reading it as off", key)
    return None


def _rows(session: Session) -> dict[str, Any]:
    result = session.execute(
        text("SELECT key, value FROM app_state WHERE key LIKE 'feature.%'")
    ).all()
    return {str(k).removeprefix(KEY_PREFIX): v for k, v in result}


def _state(
    rows: dict[str, Any], settings: Settings, f: Feature
) -> tuple[bool, datetime | None]:
    if f.key not in rows:
        return f.key in _default_on(settings), None
    stored = _stored(rows[f.key], f.key)
    return (False, None) if stored is None else stored


def read_switches(session: Session, settings: Settings) -> dict[FeatureKey, bool]:
    """Every registered key with its effective value (one SELECT)."""
    rows = _rows(session)
    return {f.key: _state(rows, settings, f)[0] for f in FEATURES}


def switch_on(session: Session, settings: Settings, key: FeatureKey) -> bool:
    return read_switches(session, settings)[key]


def _out(f: Feature, enabled: bool, updated: datetime | None, tz: str) -> FeatureSwitchOut:
    return FeatureSwitchOut(
        key=f.key,
        label=f.label,
        description=f.description,
        enabled=enabled,
        updated_at=updated,
        updated_on=None if updated is None else updated.astimezone(ZoneInfo(tz)).date(),
    )


def list_switches(session: Session, settings: Settings) -> list[FeatureSwitchOut]:
    rows = _rows(session)
    return [_out(f, *_state(rows, settings, f), settings.timezone) for f in FEATURES]


_UPSERT = text(
    "INSERT INTO app_state (key, value) "
    "VALUES (:key, jsonb_build_object("
    "'enabled', CAST(:enabled AS boolean), 'updated_at', now())) "
    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value "
    "RETURNING value"
)


def set_switch(session: Session, settings: Settings, key: str, enabled: bool) -> FeatureSwitchOut:
    """Upsert one switch; ``updated_at`` is the database's ``now()`` (D1)."""
    f = feature(key)
    params = {"key": KEY_PREFIX + f.key, "enabled": enabled}
    value = session.execute(_UPSERT, params).scalar_one()
    stored = _stored(value, f.key)
    assert stored is not None  # the upsert just wrote a well-formed value
    return _out(f, *stored, settings.timezone)
```

- [ ] **Step 6: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/domain/test_features_copy.py tests/integration/domain/test_features_store.py`
Expected: PASS (21 passed: 8 copy, 13 store).

- [ ] **Step 7: Write the failing API tests**

Create `backend/tests/integration/api/test_features_api.py`:

```python
"""GET /api/features, /api/admin/features, PUT, and feature_gate (Plan 19 D2, D3; §5.1, §5.2)."""

from typing import cast

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._features import feature_gate
from sunday_clays.domain.features import FEATURES
from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
ALL_KEYS = {f.key for f in FEATURES}


def _probe(app: FastAPI) -> None:
    """A gated viewer route, as T6/T7 will declare them."""
    router = APIRouter()

    @router.get("/api/probe-gated", dependencies=[feature_gate("summary_card")])
    def probe() -> dict[str, str]:
        return {"ok": "yes"}

    app.include_router(router)


@pytest.fixture
def gated(viewer_client: TestClient) -> TestClient:
    _probe(cast(FastAPI, viewer_client.app))
    return viewer_client


def test_viewer_sees_only_enabled_keys(viewer_client: TestClient, admin_client: TestClient) -> None:
    assert viewer_client.get("/api/features").json() == {"switches": {}}
    assert admin_client.put("/api/admin/features/pwa", json={"enabled": True}).status_code == 200
    assert viewer_client.get("/api/features").json() == {"switches": {"pwa": True}}


def test_admin_sees_every_key(admin_client: TestClient) -> None:
    switches = admin_client.get("/api/features").json()["switches"]
    assert set(switches) == ALL_KEYS
    assert set(switches.values()) == {False}


def test_features_is_no_store_and_never_tagged(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/features")
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers


def test_a_flip_shows_on_the_very_next_request(
    viewer_client: TestClient, admin_client: TestClient
) -> None:
    for enabled in (True, False, True):
        admin_client.put("/api/admin/features/club_milestones", json={"enabled": enabled})
        switches = viewer_client.get("/api/features").json()["switches"]
        assert ("club_milestones" in switches) is enabled


def test_admin_list_has_labels_dates_and_order(admin_client: TestClient) -> None:
    admin_client.put("/api/admin/features/pwa", json={"enabled": True})
    rows = admin_client.get("/api/admin/features").json()
    assert [r["key"] for r in rows] == [f.key for f in FEATURES]
    pwa = next(r for r in rows if r["key"] == "pwa")
    assert pwa["label"] == "Add to Home Screen"
    assert pwa["enabled"] is True and pwa["updated_on"] is not None
    assert next(r for r in rows if r["key"] == "tour_glossary")["updated_on"] is None


def test_put_is_audited_once_per_call(admin_client: TestClient, session: Session) -> None:
    admin_client.put("/api/admin/features/pwa", json={"enabled": True})
    admin_client.put("/api/admin/features/pwa", json={"enabled": False})
    rows = session.execute(
        select(AUDIT.c.action, AUDIT.c.details).where(AUDIT.c.action == "feature_switch")
    ).all()
    assert [r.details for r in rows] == [
        {"key": "pwa", "enabled": True},
        {"key": "pwa", "enabled": False},
    ]


def test_put_unknown_key_is_404(admin_client: TestClient) -> None:
    response = admin_client.put("/api/admin/features/nope", json={"enabled": True})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "feature_not_found"


@pytest.mark.parametrize(
    "body", [{}, {"enabled": "yes"}, {"enabled": 1}, {"enabled": True, "extra": 1}, None]
)
def test_put_other_bodies_are_422(admin_client: TestClient, body: object) -> None:
    assert admin_client.put("/api/admin/features/pwa", json=body).status_code == 422


def test_viewer_cannot_put(viewer_client: TestClient) -> None:
    assert viewer_client.put("/api/admin/features/pwa", json={"enabled": True}).status_code == 403


def test_gate_viewer_off_is_the_unknown_route_404(gated: TestClient) -> None:
    gated_404 = gated.get("/api/probe-gated")
    unknown_404 = gated.get("/api/no-such-route")
    assert gated_404.status_code == unknown_404.status_code == 404
    assert gated_404.json() == unknown_404.json() == {"detail": "Not Found"}


def test_gate_viewer_on_is_200(gated: TestClient, admin_client: TestClient) -> None:
    admin_client.put("/api/admin/features/summary_card", json={"enabled": True})
    assert gated.get("/api/probe-gated").json() == {"ok": "yes"}


def test_gate_admin_off_is_200(gated: TestClient, admin_client: TestClient) -> None:
    assert admin_client.get("/api/probe-gated").status_code == 200


def test_gate_without_session_is_401(gated: TestClient, anon_client: TestClient) -> None:
    anon_client.cookies.clear()
    assert anon_client.get("/api/probe-gated").status_code == 401


def test_gated_route_off_is_untagged_404_even_with_if_none_match(
    gated: TestClient, admin_client: TestClient
) -> None:
    """Review Focus 1: a 200 tagged while on can never be revalidated to 304 after a switch-off."""
    admin_client.put("/api/admin/features/summary_card", json={"enabled": True})
    on = gated.get("/api/probe-gated")
    assert on.status_code == 200 and "etag" in on.headers
    admin_client.put("/api/admin/features/summary_card", json={"enabled": False})
    off = gated.get("/api/probe-gated", headers={"If-None-Match": on.headers["etag"]})
    assert off.status_code == 404
    assert "etag" not in off.headers
```

The `gated`, `viewer_client`, `admin_client` and `anon_client` fixtures share one app and one rolled-back session (`tests/conftest.py`), so a `PUT` by the admin is visible to the viewer at once, and the probe route is on the same app.

In `backend/tests/unit/api/test_etag_helpers.py`, replace

```python
        ("GET", "/api/bumps", False),
        ("GET", "/index.html", False),
```

with

```python
        ("GET", "/api/bumps", False),
        ("GET", "/api/features", False),
        ("GET", "/index.html", False),
```

and replace

```python
        ("/api/bumps", "no-store"),
        ("/assets/app.js", None),
```

with

```python
        ("/api/bumps", "no-store"),
        ("/api/features", "no-store"),
        ("/assets/app.js", None),
```

- [ ] **Step 8: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_features_api.py tests/unit/api/test_etag_helpers.py`
Expected: FAIL. `test_features_api.py` errors with `ModuleNotFoundError: No module named 'sunday_clays.api.routes._features'`; the two new etag rows fail (`/api/features` is eligible and `private, no-cache`).

- [ ] **Step 9: Write the gate, the routes and the ETag rows**

Create `backend/src/sunday_clays/api/routes/_features.py`:

```python
"""``feature_gate(key)`` (Plan 19 D2): skipped by discovery (leading underscore)."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException

from sunday_clays.auth.deps import require_viewer
from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import FeatureKey, switch_on


def feature_gate(key: FeatureKey) -> Any:
    """A route dependency: 404 (the unknown-route body) for a viewer while ``key`` is off.

    It depends on ``require_viewer``, so a request without a session gets 401 first. An admin
    always passes (admin preview). The returned callable carries ``feature_gate_key`` so the
    page-cache pin tests (Plan 19 T11) can see that a route is gated.
    """

    def gate(
        role: Annotated[Role, Depends(require_viewer)],
        session: SessionDep,
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> None:
        if role != "admin" and not switch_on(session, settings, key):
            raise HTTPException(status_code=404)

    gate.feature_gate_key = key  # type: ignore[attr-defined]
    return Depends(gate)
```

Create `backend/src/sunday_clays/api/routes/features.py`:

```python
"""GET /api/features (Plan 19 D3): the switches the SPA needs to show or hide a feature."""

from typing import Annotated

from fastapi import APIRouter, Depends

from sunday_clays.auth.deps import require_viewer
from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import FeaturesOut, read_switches

router = APIRouter()


@router.get("/api/features")
def get_features(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    role: Annotated[Role, Depends(require_viewer)],
) -> FeaturesOut:
    """A viewer gets only the keys that are on (a missing key means off); an admin gets every key."""
    switches = read_switches(session, settings)
    if role != "admin":
        switches = {key: True for key, on in switches.items() if on}
    return FeaturesOut(switches=switches)
```

Create `backend/src/sunday_clays/api/routes/admin_features.py`:

```python
"""Admin launch switches (Plan 19 §3.0): list and flip, audited."""

from typing import Annotated

from fastapi import APIRouter, Depends

from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import (
    FeatureSwitchIn,
    FeatureSwitchOut,
    list_switches,
    set_switch,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/features")
def get_feature_switches(session: SessionDep, settings: SettingsDep) -> list[FeatureSwitchOut]:
    return list_switches(session, settings)


@router.put("/features/{key}")
def put_feature_switch(
    key: str, body: FeatureSwitchIn, session: SessionDep, settings: SettingsDep, actor: ActorDep
) -> FeatureSwitchOut:
    out = set_switch(session, settings, key, body.enabled)
    record_audit(
        session, actor.ip, actor.role, "feature_switch", {"key": out.key, "enabled": out.enabled}
    )
    return out
```

In `backend/src/sunday_clays/api/etag.py`, replace

```python
NO_ETAG_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/",
    "/api/admin/",
    "/api/predictions/",
)
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/")
```

with

```python
NO_ETAG_PREFIXES: tuple[str, ...] = (
    "/api/health",
    "/api/auth/",
    "/api/admin/",
    "/api/predictions/",
    "/api/features",  # Plan 19 D3: switches change without a data_version bump
)
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/", "/api/features")
```

- [ ] **Step 10: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_features_api.py tests/unit/api/test_etag_helpers.py tests/integration/api/test_route_auth_matrix.py`
Expected: PASS. The auth matrix still passes unchanged: both new modules need a session.

- [ ] **Step 11: Turn every feature on for the e2e stack**

In `compose.test.yaml`, replace

```yaml
      PAGE_VIEW_LIMIT: "100000"
    depends_on:
      db:
        condition: service_healthy
  worker:
```

with

```yaml
      PAGE_VIEW_LIMIT: "100000"
      # Plan 19 D4: the read-only e2e projects see every feature without a mutating setup step.
      # Production leaves FEATURES_DEFAULT_ON empty, so every feature starts off.
      FEATURES_DEFAULT_ON: "link_previews,tour_glossary,weekly_recap,pwa,club_milestones,summary_card"
    depends_on:
      db:
        condition: service_healthy
  worker:
```

- [ ] **Step 12: Run the backend gates**

Run (from `backend/`): the backend gates in "Per-task gates".
Expected: all clean; coverage ≥ 90%.

- [ ] **Step 13: Commit**

```bash
git add backend/src/sunday_clays/domain/features.py backend/src/sunday_clays/api/routes/_features.py \
  backend/src/sunday_clays/api/routes/features.py backend/src/sunday_clays/api/routes/admin_features.py \
  backend/src/sunday_clays/api/etag.py backend/src/sunday_clays/config.py compose.test.yaml \
  backend/tests/unit/api/test_etag_helpers.py backend/tests/unit/domain/test_features_copy.py \
  backend/tests/integration/domain/test_features_store.py backend/tests/integration/api/test_features_api.py
git commit -m "feat(features): launch switches in app_state, feature_gate and the switch API (Plan 19 T1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 2: Launch switches frontend, Features page, glossary data (`task/19-2-switches-frontend`, wave 2)

**Files:**
- Create: `frontend/src/lib/features.ts`, `frontend/src/lib/features.test.tsx`
- Create: `frontend/src/components/FeatureGate.tsx`, `frontend/src/components/FeatureGate.test.tsx`
- Create: `frontend/src/components/ui/AdminPreviewBadge.tsx`, `frontend/src/components/ui/AdminPreviewBadge.test.tsx`
- Modify: `frontend/src/app/ErrorBoundary.tsx` (extract `NotFoundView`)
- Modify: `frontend/src/app/registry.ts` (`NavItem.feature`)
- Modify: `frontend/src/components/layout/nav.ts`, `frontend/src/components/layout/nav.test.ts`
- Modify: `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/AppShell.test.tsx`
- Modify: `frontend/src/features/auth/components/SessionShell.tsx`
- Create: `frontend/src/features/admin-features/{routes.tsx, routes.test.tsx, api.ts, mocks.ts, copy.ts, copy.test.ts}`
- Create: `frontend/src/features/admin-features/pages/{FeaturesPage.tsx, FeaturesPage.test.tsx}`
- Modify: `frontend/src/app/navRegistry.test.ts` (`'admin-features': 940`)
- Create: `frontend/src/features/glossary/terms.ts`, `frontend/src/features/glossary/terms.test.ts`
- Modify: `frontend/src/components/charts/types.ts` (`Explainer.terms`)
- Create: `frontend/src/test/language.ts`
- Create: `frontend/e2e/admin-features.spec.ts`

**Interfaces:**
- Consumes: T1's `GET /api/features` (`FeaturesOut`), `GET /api/admin/features` (`FeatureSwitchOut[]`), `PUT /api/admin/features/{key}`; `features/auth/api` `useSession`, `Role`; `api/client` `api`, `unwrap`; `components/ui/{Card, Toggle}`; `lib/format.formatDate`; `lib/pageFilters.NO_FILTERS`.
- Produces:
  - `lib/features.ts`: `type FeatureKey` (from the generated schema, `Exclude<…, 'page_cache'>` so T11's infrastructure key never type-checks in `useFeature`), `FEATURES_QUERY_KEY = ['/api/features']`, `interface FeatureState { visible: boolean; preview: boolean; on: boolean; settled: boolean }`, `featureState(switches: Readonly<Record<string, boolean>> | undefined, role: Role | null, key: FeatureKey): FeatureState`, `useFeatures()` (TanStack query of `Record<string, boolean>`), `useFeature(key: FeatureKey): FeatureState`.
  - `components/FeatureGate.tsx`: `FeatureGate({ feature, children })`.
  - `components/ui/AdminPreviewBadge.tsx`: `AdminPreviewBadge({ feature })` (renders only while `useFeature(feature).preview`), `ADMIN_PREVIEW_HINT`.
  - `app/ErrorBoundary.tsx`: `NotFoundView()`.
  - `app/registry.ts`: `NavItem.feature?: FeatureKey`.
  - `components/layout/nav.ts`: `visibleNav(items, isAdmin, featureVisible?: (key: FeatureKey) => boolean)` (default: every gated item hidden).
  - `components/layout/AppShell.tsx`: prop `featureVisible?: (key: FeatureKey) => boolean`.
  - `features/admin-features/mocks.ts`: `featureSwitches` (the six rows), `DEFAULT_ON` (every key except `tour_glossary` and `pwa`), and handlers for `GET /api/features` (the `DEFAULT_ON` keys), `GET /api/admin/features`, `PUT /api/admin/features/:key`. Tests that need the tour, the glossary links or the PWA turn them on with `server.use`.
  - `features/glossary/terms.ts`: `type GlossaryTermId` (the 15 ids), `interface GlossaryTerm { id; term; definition }`, `GLOSSARY_TERMS: readonly GlossaryTerm[]` (sorted by id), `termById(id): GlossaryTerm`.
  - `components/charts/types.ts`: `Explainer.terms?: readonly GlossaryTermId[]`.
  - `src/test/language.ts`: `BANNED_WORDS = /\b(he|she|his|her|him|hers|himself|herself|class(es)?)\b/i`, `allStrings(value: unknown): string[]`.

- [ ] **Step 1: Write the failing feature-state tests**

Create `frontend/src/lib/features.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { AppProviders } from '../app/providers';
import { SESSION_QUERY_KEY, type Role } from '../features/auth/api';
import { server } from '../test/msw/server';
import { createTestQueryClient } from '../test/render';
import { featureState, useFeature } from './features';

describe('featureState', () => {
  it('takes launch-switch keys only, never the page-cache kill switch', () => {
    // @ts-expect-error page_cache is infrastructure: an admin would otherwise "preview" it
    expect(featureState({}, 'viewer', 'page_cache').visible).toBe(false);
  });

  it.each<[Role, boolean, { visible: boolean; preview: boolean; on: boolean }]>([
    ['viewer', true, { visible: true, preview: false, on: true }],
    ['viewer', false, { visible: false, preview: false, on: false }],
    ['admin', true, { visible: true, preview: false, on: true }],
    ['admin', false, { visible: true, preview: true, on: false }],
  ])('%s with the switch %s', (role, on, expected) => {
    const switches = on ? { pwa: true } : {};
    expect(featureState(switches, role, 'pwa')).toEqual({ ...expected, settled: true });
  });

  it('is invisible and unsettled before the switches are known, even for an admin', () => {
    expect(featureState(undefined, 'admin', 'pwa')).toEqual({
      visible: false,
      preview: false,
      on: false,
      settled: false,
    });
  });

  it('reads a missing key as off', () => {
    expect(featureState({ tour_glossary: true }, 'viewer', 'pwa').on).toBe(false);
  });
});

function wrapperFor(role: Role | null) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(SESSION_QUERY_KEY, role === null ? null : { role });
  return ({ children }: { children: ReactNode }) => (
    <AppProviders queryClient={queryClient}>{children}</AppProviders>
  );
}

describe('useFeature', () => {
  it('turns visible once /api/features answers', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { pwa: true } })));
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor('viewer') });
    expect(result.current.visible).toBe(false); // pending: nothing flashes in
    await waitFor(() => expect(result.current.settled).toBe(true));
    expect(result.current).toEqual({ visible: true, preview: false, on: true, settled: true });
  });

  it('never asks without a session (the login page)', async () => {
    let asked = 0;
    server.use(
      http.get('*/api/features', () => {
        asked += 1;
        return HttpResponse.json({ switches: {} });
      }),
    );
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor(null) });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(asked).toBe(0);
    expect(result.current.settled).toBe(false);
  });

  it('stays unsettled after a failed request', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    const { result } = renderHook(() => useFeature('pwa'), { wrapper: wrapperFor('admin') });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(result.current).toEqual({ visible: false, preview: false, on: false, settled: false });
  });
});
```

Check `frontend/src/app/providers.tsx` exports `AppProviders({ queryClient, children })` (it does: `test/render.tsx` uses it that way).

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && pnpm gen:api && pnpm exec vitest run src/lib/features.test.tsx`
Expected: FAIL, `Failed to resolve import "./features"`.

- [ ] **Step 3: Write `lib/features.ts` and the MSW handlers**

Create `frontend/src/lib/features.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../api/client';
import type { components } from '../api/schema';
import { useSession, type Role } from '../features/auth/api';

/** A launch-switch key (Plan 19 D23), from the generated API schema. */
/**
 * The launch-switch keys. `page_cache` (Plan 19 T11) is an infrastructure switch that
 * `/api/features` never lists, so it is excluded here; until T11 the Exclude is a no-op.
 */
export type FeatureKey = Exclude<components['schemas']['FeatureSwitchOut']['key'], 'page_cache'>;

export const FEATURES_QUERY_KEY = ['/api/features'] as const;

/**
 * `on`: the switch is on for everyone. `visible`: this viewer sees the feature (on, or an admin
 * previewing it). `preview`: an admin sees it while it is off. `settled`: the switches are known;
 * code that acts on "off" (the PWA unregister, D16) checks `settled && !on`.
 */
export interface FeatureState {
  visible: boolean;
  preview: boolean;
  on: boolean;
  settled: boolean;
}

const UNKNOWN: FeatureState = { visible: false, preview: false, on: false, settled: false };

export function featureState(
  switches: Readonly<Record<string, boolean>> | undefined,
  role: Role | null,
  key: FeatureKey,
): FeatureState {
  if (switches === undefined) return UNKNOWN;
  const on = switches[key] === true;
  const admin = role === 'admin';
  return { on, visible: on || admin, preview: !on && admin, settled: true };
}

/** GET /api/features, only once a session exists (never on /login, never a 401 redirect). */
export function useFeatures() {
  const { session } = useSession();
  return useQuery({
    queryKey: FEATURES_QUERY_KEY,
    queryFn: async (): Promise<Record<string, boolean>> =>
      (await unwrap(api.GET('/api/features'))).switches as Record<string, boolean>,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
    enabled: session !== null,
  });
}

export function useFeature(key: FeatureKey): FeatureState {
  const { session } = useSession();
  const query = useFeatures();
  return featureState(query.isSuccess ? query.data : undefined, session?.role ?? null, key);
}
```

Create `frontend/src/features/admin-features/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import type { FeatureSwitch } from './api';

/** The six switches as the API lists them (labels and descriptions as in domain/features.py). */
export const featureSwitches: FeatureSwitch[] = [
  {
    key: 'link_previews',
    label: 'Link previews',
    description:
      "Links shared in chat apps show the Sunday's date, how many shot and the round type. While off, every link shows the plain club preview.",
    enabled: true,
    updated_at: '2026-10-02T18:04:11+00:00',
    updated_on: '2026-10-02',
  },
  {
    key: 'tour_glossary',
    label: 'Welcome tour and glossary',
    description:
      'A 5-step tour on a first visit to Home, the Glossary page, and "Words used here" links in chart explainers.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'weekly_recap',
    label: 'Weekly recap',
    description: 'Admin tool: paste-ready text and an image of a Sunday for the club email.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'pwa',
    label: 'Add to Home Screen',
    description: 'Lets phones install the app, and shows a small install tip on Home.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'club_milestones',
    label: 'Club milestones',
    description:
      'Club totals such as clays thrown and Sundays held, dated at the Sunday each round number was passed. Home card and Club page.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
  {
    key: 'summary_card',
    label: 'Summary card',
    description: 'A shareable card on every profile for the chosen time window.',
    enabled: false,
    updated_at: null,
    updated_on: null,
  },
];

/**
 * The switches every test sees unless it overrides them with server.use. The tour and the PWA are
 * off by default: on, the tour would open over every Home test and the PWA would try to register a
 * service worker. Their own tests turn them on.
 */
export const DEFAULT_ON = ['link_previews', 'weekly_recap', 'club_milestones', 'summary_card'];

export const handlers = [
  http.get('*/api/features', () =>
    HttpResponse.json({ switches: Object.fromEntries(DEFAULT_ON.map((key) => [key, true])) }),
  ),
  http.get('*/api/admin/features', () => HttpResponse.json(featureSwitches)),
  http.put('*/api/admin/features/:key', async ({ params, request }) => {
    const row = featureSwitches.find((s) => s.key === params.key);
    if (row === undefined) {
      return HttpResponse.json(
        { error: { code: 'feature_not_found', message: 'No such switch' } },
        { status: 404 },
      );
    }
    const { enabled } = (await request.json()) as { enabled: boolean };
    return HttpResponse.json({
      ...row,
      enabled,
      updated_at: '2026-10-03T05:30:00+00:00',
      updated_on: '2026-10-02',
    });
  }),
];
```

Create `frontend/src/features/admin-features/api.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import { FEATURES_QUERY_KEY } from '../../lib/features';
import type { JsonOf } from '../admin/api';

export type FeatureSwitch = JsonOf<paths['/api/admin/features']['get']>[number];

export const SWITCHES_QUERY_KEY = ['/api/admin/features'] as const;

export function useFeatureSwitches() {
  return useQuery({
    queryKey: SWITCHES_QUERY_KEY,
    queryFn: () => unwrap(api.GET('/api/admin/features')),
  });
}

/** PUT one switch; on success both the admin list and the switch set are refetched. */
export function useSetFeatureSwitch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      unwrap(api.PUT('/api/admin/features/{key}', { params: { path: { key } }, body: { enabled } })),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: SWITCHES_QUERY_KEY }),
        queryClient.invalidateQueries({ queryKey: FEATURES_QUERY_KEY }),
      ]);
    },
  });
}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/lib/features.test.tsx`
Expected: PASS (7 passed).

- [ ] **Step 5: Write the failing gate, badge and nav tests**

Create `frontend/src/components/FeatureGate.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../test/msw/server';
import { renderWithProviders } from '../test/render';
import { FeatureGate } from './FeatureGate';

const off = () =>
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));

describe('FeatureGate', () => {
  it('shows "Page not found" to a viewer while the switch is off', async () => {
    off();
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
      { role: 'viewer' },
    );
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Milestones' })).not.toBeInTheDocument();
  });

  it('shows the page to an admin while the switch is off (preview)', async () => {
    off();
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
      { role: 'admin' },
    );
    expect(await screen.findByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
  });

  it('shows the page to a viewer while the switch is on', async () => {
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
    );
    expect(await screen.findByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
  });

  it('says the page could not load when the switches cannot be read', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    renderWithProviders(
      <FeatureGate feature="club_milestones">
        <h1>Milestones</h1>
      </FeatureGate>,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load this page');
  });
});
```

Create `frontend/src/components/ui/AdminPreviewBadge.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { ADMIN_PREVIEW_HINT, AdminPreviewBadge } from './AdminPreviewBadge';

const off = () =>
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));

describe('AdminPreviewBadge', () => {
  it('renders for an admin while the switch is off', async () => {
    off();
    renderWithProviders(<AdminPreviewBadge feature="summary_card" />, { role: 'admin' });
    const badge = await screen.findByText('Admin preview');
    expect(badge).toHaveAttribute('title', ADMIN_PREVIEW_HINT);
    expect(badge).toHaveAttribute('aria-description', ADMIN_PREVIEW_HINT);
  });

  it('renders nothing once the switch is on', async () => {
    const { container } = renderWithProviders(<AdminPreviewBadge feature="summary_card" />, {
      role: 'admin',
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for a viewer', async () => {
    off();
    const { container } = renderWithProviders(<AdminPreviewBadge feature="summary_card" />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
```

In `frontend/src/components/layout/nav.test.ts`, replace

```ts
describe('splitMobileNav', () => {
```

with

```ts
describe('visibleNav with launch switches', () => {
  const gated: NavItem = {
    label: 'Glossary',
    path: '/glossary',
    icon: Compass,
    order: 135,
    feature: 'tour_glossary',
  };

  it('hides an item whose feature is not visible, by default and when the check says no', () => {
    expect(visibleNav([...ITEMS, gated], true).map((i) => i.label)).not.toContain('Glossary');
    expect(visibleNav([...ITEMS, gated], false, () => false).map((i) => i.label)).not.toContain(
      'Glossary',
    );
  });

  it('shows it when the check says the feature is visible, asking with its key', () => {
    const asked: string[] = [];
    const labels = visibleNav([...ITEMS, gated], false, (key) => {
      asked.push(key);
      return true;
    }).map((i) => i.label);
    expect(labels).toContain('Glossary');
    expect(asked).toEqual(['tour_glossary']); // ungated items never ask
  });
});

describe('splitMobileNav', () => {
```

In `frontend/src/components/layout/AppShell.test.tsx`, add at the end of the file:

```tsx
describe('AppShell launch switches', () => {
  const GATED: NavItem[] = [
    ...ITEMS,
    { label: 'Glossary', path: '/glossary', icon: Compass, order: 135, feature: 'tour_glossary' },
  ];

  it('lists a gated nav item only when featureVisible says so', () => {
    stubViewport('desktop');
    const { unmount } = renderShell('/', { items: GATED });
    expect(screen.queryByRole('link', { name: 'Glossary' })).not.toBeInTheDocument();
    unmount();
    renderShell('/', { items: GATED, featureVisible: () => true });
    expect(screen.getByRole('link', { name: 'Glossary' })).toBeInTheDocument();
  });
});
```

Check `frontend/src/test/viewport.ts` exports `stubViewport('desktop' | 'mobile')`; if its name differs, use the export AppShell.test.tsx already imports from it.

- [ ] **Step 6: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/components/FeatureGate.test.tsx src/components/ui/AdminPreviewBadge.test.tsx src/components/layout/nav.test.ts src/components/layout/AppShell.test.tsx`
Expected: FAIL: unresolved `./FeatureGate` and `./AdminPreviewBadge`; nav/AppShell tests fail on the `feature` property (type error under Vitest's esbuild is not checked, so the assertions fail: "Glossary" is listed).

- [ ] **Step 7: Write the gate, the badge, `NotFoundView` and nav filtering**

In `frontend/src/app/ErrorBoundary.tsx`, replace

```tsx
/** errorElement for the root route: 404 for unknown paths, a generic message otherwise. */
export function RouteErrorPage() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) {
    return <Fallback title="Page not found" message="That page does not exist." />;
  }
```

with

```tsx
/** "Page not found": unknown paths, and gated pages while their launch switch is off (D21). */
export function NotFoundView() {
  return <Fallback title="Page not found" message="That page does not exist." />;
}

/** errorElement for the root route: 404 for unknown paths, a generic message otherwise. */
export function RouteErrorPage() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) {
    return <NotFoundView />;
  }
```

Create `frontend/src/components/FeatureGate.tsx`:

```tsx
import type { ReactNode } from 'react';
import { NotFoundView } from '../app/ErrorBoundary';
import { useFeature, useFeatures, type FeatureKey } from '../lib/features';

/**
 * Wraps a gated page (Plan 19 D21): a viewer with the switch off sees "Page not found", an admin
 * sees the page (the page shows its own AdminPreviewBadge). Nothing renders until the switches
 * are known, so a page never flashes in and then out.
 */
export function FeatureGate({ feature, children }: { feature: FeatureKey; children: ReactNode }) {
  const state = useFeature(feature);
  const query = useFeatures();
  if (query.isError) {
    return <p role="alert">Could not load this page. Reload to try again.</p>;
  }
  if (!state.settled) return null;
  if (!state.visible) return <NotFoundView />;
  return <>{children}</>;
}
```

Create `frontend/src/components/ui/AdminPreviewBadge.tsx`:

```tsx
import { useFeature, type FeatureKey } from '../../lib/features';

export const ADMIN_PREVIEW_HINT = 'Only admins can see this until it is turned on in Features.';

/** "Admin preview" pill beside a gated feature's title, only while an admin previews it. */
export function AdminPreviewBadge({ feature }: { feature: FeatureKey }) {
  const { preview } = useFeature(feature);
  if (!preview) return null;
  return (
    <span
      title={ADMIN_PREVIEW_HINT}
      aria-description={ADMIN_PREVIEW_HINT}
      className="inline-flex items-center rounded-button border border-accent px-2 py-0.5 text-xs font-medium text-accent"
    >
      Admin preview
    </span>
  );
}
```

In `frontend/src/app/registry.ts`, replace

```ts
import type { LucideIcon } from 'lucide-react';
import type { RouteObject } from 'react-router';

/** One navigation entry contributed by a feature's routes.tsx (C10). */
export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  order: number;
  mobileTab?: boolean;
  adminOnly?: boolean;
}
```

with

```ts
import type { LucideIcon } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { FeatureKey } from '../lib/features';

/** One navigation entry contributed by a feature's routes.tsx (C10). */
export interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  order: number;
  mobileTab?: boolean;
  adminOnly?: boolean;
  /** Plan 19 D21: hidden unless this launch switch's feature is visible to the viewer. */
  feature?: FeatureKey;
}
```

Replace the whole of `frontend/src/components/layout/nav.ts` with:

```ts
import type { NavItem } from '../../app/registry';
import type { FeatureKey } from '../../lib/features';

/**
 * Items the current role may see, in C10 `order`. An item naming a launch switch (`feature`) shows
 * only when `featureVisible(feature)` is true; without the check every gated item is hidden.
 */
export function visibleNav(
  items: readonly NavItem[],
  isAdmin: boolean,
  featureVisible: (key: FeatureKey) => boolean = () => false,
): NavItem[] {
  return items
    .filter((item) => isAdmin || item.adminOnly !== true)
    .filter((item) => item.feature === undefined || featureVisible(item.feature))
    .sort((a, b) => a.order - b.order);
}

/** Mobile: the (at most 4) `mobileTab` items become bottom tabs; everything else goes to "More". */
export function splitMobileNav(items: readonly NavItem[]): { tabs: NavItem[]; more: NavItem[] } {
  const tabs = items.filter((item) => item.mobileTab === true).slice(0, 4);
  return { tabs, more: items.filter((item) => !tabs.includes(item)) };
}
```

In `frontend/src/components/layout/AppShell.tsx`, replace

```tsx
import { navItems, type NavItem } from '../../app/registry';
```

with

```tsx
import { navItems, type NavItem } from '../../app/registry';
import type { FeatureKey } from '../../lib/features';
```

replace

```tsx
  /** Defaults to the feature registry's nav items. */
  items?: readonly NavItem[];
}
```

with

```tsx
  /** Defaults to the feature registry's nav items. */
  items?: readonly NavItem[];
  /** Whether a launch-switched nav item's feature is visible (Plan 19 D21); default: never. */
  featureVisible?: (key: FeatureKey) => boolean;
}
```

and replace

```tsx
export function AppShell({ isAdmin = false, account, items = navItems }: AppShellProps) {
```

```tsx
  const visible = visibleNav(items, isAdmin);
```

with (two separate replacements)

```tsx
export function AppShell({
  isAdmin = false,
  account,
  items = navItems,
  featureVisible,
}: AppShellProps) {
```

```tsx
  const visible = visibleNav(items, isAdmin, featureVisible);
```

Replace the whole of `frontend/src/features/auth/components/SessionShell.tsx` with:

```tsx
import { AppShell } from '../../../components/layout/AppShell';
import { featureState, useFeatures, type FeatureKey } from '../../../lib/features';
import { usePageViewBeacon } from '../../pageviews/beacon';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/**
 * The AppShell layout for the signed-in session (rendered inside RequireRole). It also sends the
 * anonymous page-view beacon on every page change (Plan 16; router.tsx is closed to edits), and
 * hides nav items whose launch switch is off for this viewer (Plan 19 D21).
 */
export function SessionShell() {
  const { session } = useSession();
  usePageViewBeacon(session?.role ?? null);
  const features = useFeatures();
  const role = session?.role ?? 'viewer';
  const switches = features.isSuccess ? features.data : undefined;
  const featureVisible = (key: FeatureKey) => featureState(switches, role, key).visible;
  return (
    <AppShell
      isAdmin={role === 'admin'}
      account={<AccountPanel role={role} />}
      featureVisible={featureVisible}
    />
  );
}
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/components src/features/auth src/app`
Expected: PASS (every existing test in these folders too).

- [ ] **Step 9: Write the failing glossary-data and language tests**

Create `frontend/src/test/language.ts`:

```ts
/**
 * R1 (Plan 19 §5.1): app copy never uses he/she/his/her/him/hers/himself/herself or "class".
 * Each new copy file's test asserts no match over every string it exports.
 */
export const BANNED_WORDS = /\b(he|she|his|her|him|hers|himself|herself|class(es)?)\b/i;

/** Every string inside a value: strings themselves, and the strings of arrays and objects. */
export function allStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(allStrings);
  if (value !== null && typeof value === 'object') return Object.values(value).flatMap(allStrings);
  return [];
}
```

Create `frontend/src/features/glossary/terms.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { GLOSSARY_TERMS, termById } from './terms';

describe('glossary terms', () => {
  it('has the 15 terms of the spec, sorted by id', () => {
    const ids = GLOSSARY_TERMS.map((t) => t.id);
    expect(ids).toHaveLength(15);
    expect(ids).toEqual([...ids].sort());
  });

  it('gives every term a unique id that is a valid anchor', () => {
    const ids = GLOSSARY_TERMS.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z][a-z-]*[a-z]$/);
  });

  it('looks a term up by id', () => {
    expect(termById('percentile').term).toBe('Percentile');
    expect(termById('held-sunday').term).toBe('Sunday with full results');
  });

  it('uses no banned word', () => {
    for (const text of allStrings(GLOSSARY_TERMS)) expect(text).not.toMatch(BANNED_WORDS);
  });

  it('catches a banned word (the check is not vacuous)', () => {
    expect('Her best round').toMatch(BANNED_WORDS);
    expect('top of the class').toMatch(BANNED_WORDS);
  });
});
```

- [ ] **Step 10: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/glossary/terms.test.ts`
Expected: FAIL, `Failed to resolve import "./terms"`.

- [ ] **Step 11: Write the glossary data and `Explainer.terms`**

Create `frontend/src/features/glossary/terms.ts` (copy from spec §3.2.2, verbatim):

```ts
/** The words Sunday Clays uses, in plain English (Plan 19 §3.2.2). The id is the page anchor. */
export type GlossaryTermId =
  | 'clays-thrown'
  | 'difficulty'
  | 'field-adjusted'
  | 'field-median'
  | 'first-timer'
  | 'fist-bump'
  | 'held-sunday'
  | 'percentile'
  | 'personal-best'
  | 'rarity'
  | 'round-types'
  | 'special-shoot'
  | 'streak'
  | 'time-window'
  | 'trophy-tiers';

export interface GlossaryTerm {
  id: GlossaryTermId;
  term: string;
  definition: string;
}

/** Sorted by id, the order the Glossary page lists them in. */
export const GLOSSARY_TERMS: readonly GlossaryTerm[] = [
  {
    id: 'clays-thrown',
    term: 'Clays thrown and broken',
    definition:
      'Thrown is 50 for every regular round. Broken is the score. Special shoots are left out of both.',
  },
  {
    id: 'difficulty',
    term: 'Difficulty',
    definition:
      'How much harder or easier a Sunday was than usual, in targets. It is worked out from how everyone scored compared with their own normal.',
  },
  {
    id: 'field-adjusted',
    term: 'Field-adjusted score',
    definition:
      "Your score minus that Sunday's field median. +4 means 4 targets better than the middle of the field, so easy and hard days compare fairly.",
  },
  {
    id: 'field-median',
    term: 'Field median',
    definition:
      'The middle score of all rounds that Sunday: half scored more, half scored less.',
  },
  {
    id: 'first-timer',
    term: 'First-timer',
    definition:
      'Someone whose first Sunday on record is that day. Special shoots count.',
  },
  {
    id: 'fist-bump',
    term: 'Fist bump',
    definition:
      'A thumbs-up on an insight. It is anonymous: it uses a random ID made by your browser, never your name.',
  },
  {
    id: 'held-sunday',
    term: 'Sunday with full results',
    definition:
      'A Sunday that has scores, where either no head count was written down or at least half the people counted have a score. Streaks, Sundays held and milestones count these.',
  },
  {
    id: 'percentile',
    term: 'Percentile',
    definition:
      'Where your best round of the day landed in the field, from 0% (lowest) to 100% (highest). Ties share a spot. It is (shooters − your average place) ÷ (shooters − 1).',
  },
  {
    id: 'personal-best',
    term: 'Personal best (PB)',
    definition:
      "Your best single round so far. On a Sunday's page, in the recap and on the summary card, a new PB counts once you have at least 5 earlier rounds.",
  },
  {
    id: 'rarity',
    term: 'Rarity',
    definition:
      'The share of everyone who has shot a round who holds that trophy. 5% means about 1 in 20 shooters.',
  },
  {
    id: 'round-types',
    term: 'Sporting and Super Sporting',
    definition:
      "Every regular round is 50 targets. If any station that day threw an odd number of targets, the round is Super Sporting (some single targets mixed with pairs). Otherwise it is Sporting (all pairs). An admin can correct a Sunday's type.",
  },
  {
    id: 'special-shoot',
    term: 'Special shoot',
    definition:
      'A Sunday with its own format, such as the 3-Bird Shoot (60 targets). It counts as a Sunday you came to, for streaks, Sundays shot and attendance trophies, but its scores stay out of averages, personal bests, records and leaderboards.',
  },
  {
    id: 'streak',
    term: 'Streak',
    definition:
      'Sundays in a row you came to, counting Sundays with full results. A special shoot adds one if you came, and never breaks a run if you did not.',
  },
  {
    id: 'time-window',
    term: 'Time window',
    definition:
      'The 8W / 3M / 6M / 12M / YTD / All / Custom control at the top. Charts and stats on the page follow it. Fullscreen and CSV downloads show everything.',
  },
  {
    id: 'trophy-tiers',
    term: 'Trophy tiers',
    definition:
      'Tiered trophies go Bronze, Silver, Gold, Platinum, then Diamond as the number grows.',
  },
];

export function termById(id: GlossaryTermId): GlossaryTerm {
  const found = GLOSSARY_TERMS.find((t) => t.id === id);
  if (found === undefined) throw new Error(`no glossary term ${id}`);
  return found;
}
```

In `frontend/src/components/charts/types.ts`, replace

```ts
import type { QueryKey } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
```

with

```ts
import type { QueryKey } from '@tanstack/react-query';
import type { EChartsOption } from 'echarts';
import type { GlossaryTermId } from '../../features/glossary/terms';
```

and replace

```ts
  scope?: 'windowed' | 'all-time' | 'lifetime' | 'year';
}
```

with

```ts
  scope?: 'windowed' | 'all-time' | 'lifetime' | 'year';
  /** Plan 19 D13: glossary terms the copy uses; shown as "Words used here" links. */
  terms?: readonly GlossaryTermId[];
}
```

- [ ] **Step 12: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/glossary/terms.test.ts`
Expected: PASS (5 passed).

- [ ] **Step 13: Write the failing Features page tests**

Create `frontend/src/features/admin-features/copy.ts`:

```ts
import { formatDate } from '../../lib/format';

export const FEATURES_INTRO =
  'Turn a finished feature on for everyone. While a switch is off, only admins see the feature, marked “Admin preview”. Changes reach everyone within a minute. No redeploy needed.';

/** "Changed Oct 2, 2026" from the club-timezone date (D26), or "Never changed". */
export function changedText(updatedOn: string | null): string {
  return updatedOn === null ? 'Never changed' : `Changed ${formatDate(updatedOn)}`;
}
```

Create `frontend/src/features/admin-features/copy.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { changedText, FEATURES_INTRO } from './copy';
import { featureSwitches } from './mocks';

describe('Features page copy', () => {
  it('formats the change date and the never-changed case', () => {
    expect(changedText('2026-10-02')).toBe('Changed Oct 2, 2026');
    expect(changedText(null)).toBe('Never changed');
  });

  it('uses no banned word in the intro, labels and descriptions', () => {
    const texts = [
      FEATURES_INTRO,
      ...allStrings(featureSwitches.map(({ label, description }) => ({ label, description }))),
    ];
    for (const text of texts) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

Create `frontend/src/features/admin-features/pages/FeaturesPage.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { featureSwitches } from '../mocks';
import { FeaturesPage } from './FeaturesPage';

describe('FeaturesPage', () => {
  it('lists exactly the six switches with labels, descriptions and dates', async () => {
    renderWithProviders(<FeaturesPage />, { role: 'admin', route: '/admin/features' });
    expect(screen.getByRole('heading', { level: 1, name: 'Features' })).toBeInTheDocument();
    const switches = await screen.findAllByRole('switch');
    expect(switches.map((s) => s.textContent)).toEqual(featureSwitches.map((f) => f.label));
    const first = screen.getByRole('listitem', { name: 'Link previews' });
    expect(within(first).getByText('Changed Oct 2, 2026')).toBeInTheDocument();
    expect(switches[0]).toHaveAttribute('aria-checked', 'true');
    const second = screen.getByRole('listitem', { name: 'Welcome tour and glossary' });
    expect(within(second).getByText('Never changed')).toBeInTheDocument();
  });

  it('flips a switch with a PUT and refetches the list', async () => {
    const puts: unknown[] = [];
    server.use(
      http.put('*/api/admin/features/:key', async ({ params, request }) => {
        puts.push({ key: params.key, body: await request.json() });
        return HttpResponse.json({ ...featureSwitches[3], enabled: true, updated_on: '2026-10-02' });
      }),
    );
    const { user } = renderWithProviders(<FeaturesPage />, { role: 'admin' });
    await user.click(await screen.findByRole('switch', { name: 'Add to Home Screen' }));
    expect(puts).toEqual([{ key: 'pwa', body: { enabled: true } }]);
  });

  it('says so when a flip fails, naming the switch', async () => {
    server.use(
      http.put('*/api/admin/features/:key', () =>
        HttpResponse.json({ error: { code: 'x', message: 'x' } }, { status: 500 }),
      ),
    );
    const { user } = renderWithProviders(<FeaturesPage />, { role: 'admin' });
    await user.click(await screen.findByRole('switch', { name: 'Summary card' }));
    expect(await screen.findByText('Could not change Summary card. Try again.')).toBeInTheDocument();
  });

  it('says so when the list cannot load', async () => {
    server.use(http.get('*/api/admin/features', () => HttpResponse.error()));
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the switches.');
  });
});
```

Create `frontend/src/features/admin-features/routes.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

describe('admin-features routes', () => {
  it('serve the Features page to an admin', async () => {
    renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
      route: '/admin/features',
      role: 'admin',
    });
    expect(await screen.findByRole('heading', { level: 1, name: 'Features' })).toBeInTheDocument();
  });

  it('give a viewer the admins-only page', async () => {
    renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
      route: '/admin/features',
      role: 'viewer',
    });
    expect(await screen.findByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
  });

  it('add an admin-only Features nav item at 940 with no header filters', () => {
    expect(
      nav.map(({ label, path, order, adminOnly }) => ({ label, path, order, adminOnly })),
    ).toEqual([{ label: 'Features', path: '/admin/features', order: 940, adminOnly: true }]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });
});
```

In `frontend/src/app/navRegistry.test.ts`, replace

```ts
  'admin-analytics': 930,
};
```

with

```ts
  'admin-analytics': 930,
  'admin-features': 940,
};
```

- [ ] **Step 14: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/admin-features src/app/navRegistry.test.ts`
Expected: FAIL: unresolved `./FeaturesPage` and `./routes`.

- [ ] **Step 15: Write the Features page and its route**

Create `frontend/src/features/admin-features/pages/FeaturesPage.tsx`:

```tsx
import { useState } from 'react';
import { Card } from '../../../components/ui/Card';
import { Toggle } from '../../../components/ui/Toggle';
import { useFeatureSwitches, useSetFeatureSwitch, type FeatureSwitch } from '../api';
import { changedText, FEATURES_INTRO } from '../copy';

function SwitchRow({
  row,
  onChange,
  pending,
}: {
  row: FeatureSwitch;
  onChange: (enabled: boolean) => void;
  pending: boolean;
}) {
  return (
    <li aria-label={row.label} className="flex flex-col gap-1 border-b border-outline-variant py-3 last:border-b-0">
      <Toggle label={row.label} checked={row.enabled} onChange={onChange} disabled={pending} />
      <p className="text-sm text-text-muted">{row.description}</p>
      <p className="text-xs text-text-muted">{changedText(row.updated_on)}</p>
    </li>
  );
}

/** Admin page: one launch switch per feature (Plan 19 §3.0). */
export function FeaturesPage() {
  const query = useFeatureSwitches();
  const mutation = useSetFeatureSwitch();
  const [failed, setFailed] = useState<string | null>(null);
  const change = (row: FeatureSwitch, enabled: boolean) => {
    setFailed(null);
    mutation.mutate(
      { key: row.key, enabled },
      { onError: () => setFailed(`Could not change ${row.label}. Try again.`) },
    );
  };
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-medium">Features</h1>
        <p className="text-text-muted">{FEATURES_INTRO}</p>
      </header>
      <p aria-live="polite" className="text-sm text-text-muted">
        {failed ?? ''}
      </p>
      {query.isPending ? (
        <p role="status">Loading switches…</p>
      ) : query.isError ? (
        <p role="alert">Could not load the switches.</p>
      ) : (
        <Card title="Launch switches">
          <ul className="flex flex-col">
            {query.data.map((row) => (
              <SwitchRow
                key={row.key}
                row={row}
                pending={mutation.isPending}
                onChange={(enabled) => change(row, enabled)}
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
```

Create `frontend/src/features/admin-features/routes.tsx`:

```tsx
import { ToggleRight } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { NO_FILTERS } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

// Admin pages render inside RequireRole role="admin"; the page stays lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin/features',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { FeaturesPage } = await import('./pages/FeaturesPage');
      return {
        element: (
          <RequireRole role="admin">
            <FeaturesPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Features', path: '/admin/features', icon: ToggleRight, order: 940, adminOnly: true },
];
```

- [ ] **Step 16: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/admin-features src/app/navRegistry.test.ts`
Expected: PASS.

- [ ] **Step 17: Write the read-only e2e**

Create `frontend/e2e/admin-features.spec.ts`:

```ts
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';

// Read-only: lists the switches; flipping them is the admin-mutations project's job (Task 10).
test.use({ storageState: ADMIN_STATE });

const LABELS = [
  'Link previews',
  'Welcome tour and glossary',
  'Weekly recap',
  'Add to Home Screen',
  'Club milestones',
  'Summary card',
];

test('the Features page lists the six launch switches', async ({ page }) => {
  await page.goto('/admin/features');
  await expect(page.getByRole('heading', { level: 1, name: 'Features' })).toBeVisible();
  await whenSettled(page);
  for (const label of LABELS) {
    await expect(page.getByRole('switch', { name: label })).toBeVisible();
  }
  await expect(page.getByRole('switch')).toHaveCount(LABELS.length);
  await expect(page.getByText(/^(Changed [A-Z][a-z]{2} \d{1,2}, \d{4}|Never changed)$/)).toHaveCount(
    LABELS.length,
  );
  await expectNoSideScroll(page);
  await expectTapTargets(page);
});

test('the nav lists Features for an admin', async ({ page, isMobile }) => {
  await page.goto('/');
  if (isMobile) await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('link', { name: 'Features' })).toBeVisible();
});
```

- [ ] **Step 18: Run the e2e at both sizes**

Build and start the stack ("Running the e2e stack", project `task19-2`). Run: `E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test admin-features.spec.ts --project=desktop --project=mobile`
Expected: 4 passed. If `expectTapTargets` flags the description paragraphs, it will not (they are not links or buttons); a flagged `Toggle` means the 44 px `min-h-11` was lost.

- [ ] **Step 19: Run the frontend gates**

Run (from `frontend/`): the frontend gates in "Per-task gates".
Expected: clean; coverage ≥ 90%.

- [ ] **Step 20: Commit**

```bash
git add frontend/src/lib/features.ts frontend/src/lib/features.test.tsx \
  frontend/src/components/FeatureGate.tsx frontend/src/components/FeatureGate.test.tsx \
  frontend/src/components/ui/AdminPreviewBadge.tsx frontend/src/components/ui/AdminPreviewBadge.test.tsx \
  frontend/src/app/ErrorBoundary.tsx frontend/src/app/registry.ts frontend/src/app/navRegistry.test.ts \
  frontend/src/components/layout/nav.ts frontend/src/components/layout/nav.test.ts \
  frontend/src/components/layout/AppShell.tsx frontend/src/components/layout/AppShell.test.tsx \
  frontend/src/features/auth/components/SessionShell.tsx frontend/src/features/admin-features \
  frontend/src/features/glossary/terms.ts frontend/src/features/glossary/terms.test.ts \
  frontend/src/components/charts/types.ts frontend/src/test/language.ts frontend/e2e/admin-features.spec.ts
git commit -m "feat(features): useFeature, FeatureGate, admin preview badge, nav gating and the Features page (Plan 19 T2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 3: Link previews backend, logo and icons (`task/19-3-link-previews-backend`, wave 2)

**Files:**
- Modify: `backend/pyproject.toml`, `backend/uv.lock` (`uv add 'pillow>=12.0'` only)
- Modify: `backend/src/sunday_clays/config.py` (`public_base_url`)
- Create: `backend/src/sunday_clays/og/__init__.py`, `og/facts.py`, `og/html.py`, `og/render.py`, `og/logo.py`, `og/icons.py`
- Create: `backend/src/sunday_clays/og/fonts/Roboto-Regular.ttf`, `og/fonts/Roboto-Medium.ttf`, `og/fonts/LICENSE.txt`
- Create: `backend/src/sunday_clays/api/routes/og.py`
- Modify: `backend/src/sunday_clays/api/app.py` (`PUBLIC_ROUTE_MODULES`, one line)
- Modify: `backend/src/sunday_clays/api/etag.py` (`/api/og/` untagged, `cache_control_for` → `None`)
- Create: `frontend/public/icons/{icon-192.png, icon-512.png, maskable-512.png, apple-touch-icon.png, favicon-32.png}` (generated)
- Create: `backend/tests/unit/og/test_html.py`, `backend/tests/unit/og/test_render.py`, `backend/tests/unit/og/test_logo_icons.py`
- Create: `backend/tests/integration/api/test_og_routes.py`
- Modify: `backend/tests/integration/api/test_route_auth_matrix.py` (`PUBLIC`)
- Modify: `backend/tests/unit/api/test_etag_helpers.py` (rows), `backend/tests/unit/api/test_app.py` (one test)

**Interfaces:**
- Consumes: T1's `domain.features.switch_on(session, settings, "link_previews")`, `set_switch`; `analytics.frames.load_calendar`; `analytics.cache.cached_by_data_version`, `read_data_version`; `api.routes._convert.{rows, opt_int, opt_str}`; `domain.round_type.RoundType`; fixtures `fx_client`, `fx_session`, `fx_special_client`, `fx_special_session`, `fx_viewer_client`, `test_settings`.
- Produces:
  - `config.Settings.public_base_url: str = "https://sundayclays.claysmasher.com"` (env `PUBLIC_BASE_URL`; T8's recap link uses it).
  - `og.facts`: `@dataclass(frozen=True) PreviewFacts(kind: Literal["generic", "sunday", "special"], event_date: date | None = None, n_shooters: int | None = None, round_type: RoundType | None = None, label: str | None = None)`, `GENERIC`, `page_path(path: str) -> str` (leading `/` and `l/` removed), `facts_for_path(session, path, switch_on: bool) -> PreviewFacts`.
  - `og.html`: `SITE_TITLE`, `title_of`, `description_of`, `image_alt_of`, `image_lines(facts) -> tuple[str, str] | None`, `image_url(facts, base_url, data_version) -> str`, `render_page(facts, path, base_url, data_version) -> str`.
  - `og.render`: `render_card(facts) -> bytes` (pure), `card_png(session, facts) -> bytes` (`@cached_by_data_version`).
  - `og.logo.draw_mark(size: int, *, background: bool = True) -> Image.Image`; colour constants `GREEN`, `DOME`, `RIM`, `HIGHLIGHT`.
  - `og.icons`: `ICONS`, `write_icons(out_dir: Path) -> list[Path]`, `main(argv: list[str] | None = None) -> int` (`uv run python -m sunday_clays.og.icons ../frontend/public/icons`).
  - Public routes (module `og`, GET and HEAD only, `include_in_schema=False`): `/api/og/page/`, `/api/og/page/{path:path}`, `/api/og/image/generic.png`, `/api/og/image/sunday/{day}.png`.
  - The PWA icons under `frontend/public/icons/` (T9 references them).

- [ ] **Step 1: Add Pillow and the fonts**

```bash
cd backend && uv add 'pillow>=12.0'
mkdir -p src/sunday_clays/og/fonts && cd src/sunday_clays/og/fonts
curl -fsSLo /tmp/roboto.zip https://github.com/googlefonts/roboto/releases/download/v2.138/roboto-unhinted.zip
unzip -j -o /tmp/roboto.zip 'Roboto-Regular.ttf' 'Roboto-Medium.ttf' 'LICENSE.txt' -d .
ls -l Roboto-Regular.ttf Roboto-Medium.ttf LICENSE.txt
grep -c "Apache License" LICENSE.txt
```

Expected: three files; `grep` prints a count ≥ 1 (the fonts are Apache-2.0, spec D8). If the zip names a file differently (for example `LICENSE`), keep the file but name it `LICENSE.txt`. Confirm `git diff backend/pyproject.toml` shows exactly one added dependency line, and `uv run python -c "import PIL; print(PIL.__version__)"` prints `12.` or later.

- [ ] **Step 2: Write the failing HTML and copy tests**

Create `backend/tests/unit/og/test_html.py`:

```python
"""Preview copy and meta page (Plan 19 §3.1.2, §3.1.4)."""

from datetime import date

import pytest

from sunday_clays.domain.round_type import RoundType
from sunday_clays.og.facts import GENERIC, PreviewFacts, page_path
from sunday_clays.og.html import (
    SITE_TITLE,
    description_of,
    image_alt_of,
    image_lines,
    image_url,
    render_page,
)

BASE = "https://sundayclays.claysmasher.com"
SUNDAY = PreviewFacts("sunday", date(2026, 9, 27), 23, RoundType.SPORTING)
SPECIAL = PreviewFacts("special", date(2026, 9, 20), 40, RoundType.SPORTING, "3-Bird Shoot")


@pytest.mark.parametrize(
    ("facts", "description", "alt"),
    [
        (
            GENERIC,
            "Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.",
            "Sunday Clays logo",
        ),
        (
            SUNDAY,
            "Sunday, Sep 27, 2026 · 23 shooters · Sporting",
            "Sunday Clays, Sunday Sep 27, 2026",
        ),
        (SPECIAL, "3-Bird Shoot · 40 shooters", "Sunday Clays, 3-Bird Shoot on Sep 20, 2026"),
    ],
)
def test_copy_table(facts: PreviewFacts, description: str, alt: str) -> None:
    assert description_of(facts) == description
    assert image_alt_of(facts) == alt


def test_title_is_always_the_club() -> None:
    assert SITE_TITLE == "Sunday Clays · Tri-County Gun Club"


def test_singular_super_sporting_and_no_count() -> None:
    one = PreviewFacts("sunday", date(2026, 9, 27), 1, RoundType.SUPER_SPORTING)
    assert description_of(one) == "Sunday, Sep 27, 2026 · 1 shooter · Super Sporting"
    none = PreviewFacts("sunday", date(2026, 9, 27), None, RoundType.SPORTING)
    assert description_of(none) == "Sunday, Sep 27, 2026 · Sporting"
    assert description_of(PreviewFacts("special", date(2026, 9, 20), None, None, "X")) == "X"


def test_image_lines() -> None:
    assert image_lines(GENERIC) is None
    assert image_lines(SUNDAY) == ("Sunday, Sep 27, 2026", "23 shooters · Sporting")
    assert image_lines(SPECIAL) == ("3-Bird Shoot", "Special shoot · 40 shooters")


def test_image_url_carries_the_data_version_only_for_a_sunday() -> None:
    assert image_url(GENERIC, BASE, 9) == f"{BASE}/api/og/image/generic.png"
    assert image_url(SUNDAY, BASE, 9) == f"{BASE}/api/og/image/sunday/2026-09-27.png?v=9"


@pytest.mark.parametrize(
    ("raw", "stripped"),
    [("/", ""), ("", ""), ("l/events/2026-09-27", "events/2026-09-27"), ("/events/x", "events/x")],
)
def test_page_path_strips_the_share_prefix(raw: str, stripped: str) -> None:
    assert page_path(raw) == stripped


def test_golden_sunday_page() -> None:
    expected = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        "<title>Sunday Clays · Tri-County Gun Club</title>\n"
        '<meta name="description" content="Sunday, Sep 27, 2026 · 23 shooters · Sporting">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="Sunday Clays">\n'
        '<meta property="og:title" content="Sunday Clays · Tri-County Gun Club">\n'
        '<meta property="og:description" content="Sunday, Sep 27, 2026 · 23 shooters · Sporting">\n'
        f'<meta property="og:url" content="{BASE}/l/events/2026-09-27">\n'
        f'<meta property="og:image" content="{BASE}/api/og/image/sunday/2026-09-27.png?v=4">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        '<meta property="og:image:alt" content="Sunday Clays, Sunday Sep 27, 2026">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        '<meta name="twitter:title" content="Sunday Clays · Tri-County Gun Club">\n'
        '<meta name="twitter:description" content="Sunday, Sep 27, 2026 · 23 shooters · Sporting">\n'
        f'<meta name="twitter:image" content="{BASE}/api/og/image/sunday/2026-09-27.png?v=4">\n'
        '</head><body><p><a href="/events/2026-09-27">Open Sunday Clays</a></p></body></html>\n'
    )
    assert render_page(SUNDAY, "/l/events/2026-09-27", BASE, 4) == expected
    assert render_page(SUNDAY, "/events/2026-09-27", BASE, 4) == expected  # og:url is /l/ either way


def test_generic_and_special_pages_have_their_own_facts() -> None:
    generic = render_page(GENERIC, "/", BASE, 4)
    assert f'<meta property="og:url" content="{BASE}/l/">' in generic
    assert f'content="{BASE}/api/og/image/generic.png"' in generic
    assert '<a href="/">Open Sunday Clays</a>' in generic
    special = render_page(SPECIAL, "/events/2026-09-20", BASE, 4)
    assert 'content="3-Bird Shoot · 40 shooters"' in special


def test_every_value_is_escaped_and_the_page_has_no_script_or_style() -> None:
    hostile = PreviewFacts("special", date(2026, 9, 20), 3, None, '<b a="1">&x')
    page = render_page(hostile, '/events/2026-09-20"><script>', BASE, 4)
    assert "<b " not in page and '"1">' not in page
    assert "&lt;b a=&quot;1&quot;&gt;&amp;x" in page
    assert "<script" not in page.lower() and "style=" not in page.lower()
```

Create `backend/tests/unit/og/__init__.py`? No: pytest runs with `--import-mode=importlib`, and sibling test folders have no `__init__.py`.

- [ ] **Step 3: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/og/test_html.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'sunday_clays.og'`.

- [ ] **Step 4: Write the facts and the HTML**

Create `backend/src/sunday_clays/og/__init__.py`:

```python
"""Link previews (Plan 19 §3.1): name-free facts, a meta page and a PNG card for crawlers."""
```

Create `backend/src/sunday_clays/og/facts.py`:

```python
"""The only input of a preview (Plan 19 D10): a facts object with no name field."""

import re
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.api.routes._convert import opt_int, opt_str, rows
from sunday_clays.domain.round_type import RoundType

PreviewKind = Literal["generic", "sunday", "special"]


@dataclass(frozen=True)
class PreviewFacts:
    kind: PreviewKind
    event_date: date | None = None
    n_shooters: int | None = None
    round_type: RoundType | None = None
    label: str | None = None  # a special shoot's admin-entered label (<= 60 characters)


GENERIC: Final = PreviewFacts("generic")
_EVENT_PATH: Final = re.compile(r"^events/(\d{4}-\d{2}-\d{2})/?$")


def page_path(path: str) -> str:
    """The SPA path without its leading slash and without a leading ``l/`` share prefix."""
    stripped = path.lstrip("/")
    return stripped.removeprefix("l/") if stripped.startswith("l/") else stripped


def facts_for_path(session: Session, path: str, switch_on: bool) -> PreviewFacts:
    """``events/<date>`` of a calendar Sunday (switch on) is a Sunday or special; all else generic.

    Profiles, Year in Review, unknown paths and unknown or malformed dates are generic, so a
    preview never confirms that a person exists (§3.1.5).
    """
    if not switch_on:
        return GENERIC
    match = _EVENT_PATH.match(page_path(path))
    if match is None:
        return GENERIC
    try:
        day = date.fromisoformat(match.group(1))
    except ValueError:
        return GENERIC
    calendar = frames.load_calendar(session)
    found = calendar.loc[calendar["event_date"] == day]
    if found.empty:
        return GENERIC
    row = rows(found)[0]
    count = int(row["n_shooters"]) if bool(row["has_scores"]) else opt_int(row["head_count"])
    round_type = RoundType(str(row["round_type"]))
    if row["kind"] == frames.EVENT_KIND_SPECIAL:
        return PreviewFacts("special", day, count, round_type, opt_str(row["label"]))
    return PreviewFacts("sunday", day, count, round_type)
```

Create `backend/src/sunday_clays/og/html.py`:

```python
"""Preview copy (§3.1.4) and the script-free, style-free meta page (§3.1.2)."""

import html
from datetime import date
from typing import Final

from sunday_clays.domain.round_type import RoundType
from sunday_clays.og.facts import PreviewFacts, page_path

SITE_TITLE: Final = "Sunday Clays · Tri-County Gun Club"
GENERIC_DESCRIPTION: Final = (
    "Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club."
)
_MONTHS: Final = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_ROUND_TYPES: Final = {RoundType.SPORTING: "Sporting", RoundType.SUPER_SPORTING: "Super Sporting"}


def _short(day: date) -> str:
    """Sep 27, 2026 (fixed English months: the container locale never matters)."""
    return f"{_MONTHS[day.month - 1]} {day.day}, {day.year}"


def _shooters(n: int | None) -> list[str]:
    if n is None:
        return []
    return ["1 shooter" if n == 1 else f"{n} shooters"]


def _round_type(facts: PreviewFacts) -> list[str]:
    return [] if facts.round_type is None else [_ROUND_TYPES[facts.round_type]]


def title_of(facts: PreviewFacts) -> str:
    return SITE_TITLE


def description_of(facts: PreviewFacts) -> str:
    if facts.kind == "generic" or facts.event_date is None:
        return GENERIC_DESCRIPTION
    if facts.kind == "special":
        return " · ".join([facts.label or "Special shoot", *_shooters(facts.n_shooters)])
    parts = [f"Sunday, {_short(facts.event_date)}", *_shooters(facts.n_shooters)]
    return " · ".join([*parts, *_round_type(facts)])


def image_alt_of(facts: PreviewFacts) -> str:
    if facts.kind == "generic" or facts.event_date is None:
        return "Sunday Clays logo"
    if facts.kind == "special":
        return f"Sunday Clays, {facts.label or 'Special shoot'} on {_short(facts.event_date)}"
    return f"Sunday Clays, Sunday {_short(facts.event_date)}"


def image_lines(facts: PreviewFacts) -> tuple[str, str] | None:
    """Line A and line B of a Sunday card; None for the generic card."""
    if facts.kind == "generic" or facts.event_date is None:
        return None
    if facts.kind == "special":
        line_b = " · ".join(["Special shoot", *_shooters(facts.n_shooters)])
        return facts.label or "Special shoot", line_b
    line_b = " · ".join([*_shooters(facts.n_shooters), *_round_type(facts)])
    return f"Sunday, {_short(facts.event_date)}", line_b


def image_url(facts: PreviewFacts, base_url: str, data_version: int) -> str:
    if facts.kind == "generic" or facts.event_date is None:
        return f"{base_url}/api/og/image/generic.png"
    return f"{base_url}/api/og/image/sunday/{facts.event_date.isoformat()}.png?v={data_version}"


def render_page(facts: PreviewFacts, path: str, base_url: str, data_version: int) -> str:
    """The meta page. Every value is escaped; ``og:url`` is always the ``/l/`` form (D7)."""

    def e(value: str) -> str:
        return html.escape(value, quote=True)

    shown = page_path(path)
    title, description = e(title_of(facts)), e(description_of(facts))
    image = e(image_url(facts, base_url, data_version))
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{description}">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="Sunday Clays">\n'
        f'<meta property="og:title" content="{title}">\n'
        f'<meta property="og:description" content="{description}">\n'
        f'<meta property="og:url" content="{e(f"{base_url}/l/{shown}")}">\n'
        f'<meta property="og:image" content="{image}">\n'
        '<meta property="og:image:width" content="1200">\n'
        '<meta property="og:image:height" content="630">\n'
        f'<meta property="og:image:alt" content="{e(image_alt_of(facts))}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{description}">\n'
        f'<meta name="twitter:image" content="{image}">\n'
        f'</head><body><p><a href="/{e(shown)}">Open Sunday Clays</a></p></body></html>\n'
    )
```

- [ ] **Step 5: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/og/test_html.py`
Expected: PASS.

- [ ] **Step 6: Write the failing render, logo and icon tests**

Create `backend/tests/unit/og/test_render.py`:

```python
"""The 1200x630 PNG card (Plan 19 §3.1.4, D8)."""

import io
import struct
from datetime import date

from PIL import Image, ImageDraw

from sunday_clays.domain.round_type import RoundType
from sunday_clays.og import render
from sunday_clays.og.facts import GENERIC, PreviewFacts

SUNDAY = PreviewFacts("sunday", date(2026, 9, 27), 23, RoundType.SPORTING)


def _chunks(png: bytes) -> list[bytes]:
    out, pos = [], 8
    while pos < len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        out.append(png[pos + 4 : pos + 8])
        pos += 12 + length
    return out


def test_same_facts_same_bytes_and_no_text_chunks() -> None:
    first, second = render.render_card(SUNDAY), render.render_card(SUNDAY)
    assert first == second
    chunks = _chunks(first)
    assert b"tEXt" not in chunks and b"iTXt" not in chunks and b"zTXt" not in chunks
    image = Image.open(io.BytesIO(first))
    assert image.size == (1200, 630)


def test_different_facts_different_bytes() -> None:
    assert render.render_card(SUNDAY) != render.render_card(GENERIC)


def test_background_pixel_is_the_club_green() -> None:
    image = Image.open(io.BytesIO(render.render_card(GENERIC))).convert("RGB")
    assert image.getpixel((1190, 10)) == (0x1A, 0x4D, 0x2E)


def test_fit_shrinks_then_truncates_a_long_label() -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    short_font, short = render.fit(draw, "3-Bird Shoot", render.MEDIUM, 52)
    assert short == "3-Bird Shoot" and short_font.size == 52
    long_label = "W" * 60
    font, text = render.fit(draw, long_label, render.MEDIUM, 52)
    assert font.size == render.MIN_SIZE
    assert text.endswith("…") and len(text) < 61
    assert draw.textlength(text, font=font) <= render.MAX_TEXT_WIDTH


def test_a_60_character_label_renders() -> None:
    label = "A very long special shoot label that runs past the card edge"
    assert len(label) == 60
    facts = PreviewFacts("special", date(2026, 9, 20), 40, RoundType.SPORTING, label)
    assert Image.open(io.BytesIO(render.render_card(facts))).size == (1200, 630)
```

Create `backend/tests/unit/og/test_logo_icons.py`:

```python
"""One logo drawn in code (D9) and the PWA icons written from it."""

from pathlib import Path

import pytest
from PIL import Image

from sunday_clays.og import icons, logo


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    return tuple(int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def test_mark_colours_and_rounded_corner() -> None:
    mark = logo.draw_mark(160)
    assert mark.size == (160, 160) and mark.mode == "RGBA"
    assert mark.getpixel((1, 1))[3] == 0  # rounded corner: transparent
    assert mark.getpixel((4, 80))[:3] == _rgb(logo.GREEN)
    r, g, b, _ = mark.getpixel((80, 85))  # the dome's centre, well inside the highlight ring
    assert (r, g, b) == _rgb(logo.DOME)


def test_mark_without_background_is_transparent_at_the_edge() -> None:
    assert logo.draw_mark(160, background=False).getpixel((4, 80))[3] == 0


def test_write_icons_writes_every_size(tmp_path: Path) -> None:
    written = icons.write_icons(tmp_path)
    assert sorted(p.name for p in written) == sorted(icons.ICONS)
    for name, (size, maskable) in icons.ICONS.items():
        image = Image.open(tmp_path / name)
        assert image.size == (size, size)
        if maskable:  # full bleed: the corner is the club green, not transparent
            assert image.convert("RGB").getpixel((0, 0)) == _rgb(logo.GREEN)


def test_main_writes_into_the_given_folder(tmp_path: Path) -> None:
    assert icons.main([str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "icon-512.png").is_file()


def test_main_without_a_folder_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        icons.main([])
```

- [ ] **Step 7: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/og/test_render.py tests/unit/og/test_logo_icons.py`
Expected: FAIL, `ImportError: cannot import name 'render' from 'sunday_clays.og'`.

- [ ] **Step 8: Write the logo, the icons and the renderer**

Create `backend/src/sunday_clays/og/logo.py`:

```python
"""The Sunday Clays mark (D9): a clay target in three-quarter view on a green rounded square."""

from typing import Final

from PIL import Image, ImageDraw

GREEN: Final = "#1A4D2E"
DOME: Final = "#C76D3F"
RIM: Final = "#9E5530"
HIGHLIGHT: Final = "#E8A77A"
_SUPERSAMPLE: Final = 4


def draw_mark(size: int, *, background: bool = True) -> Image.Image:
    """The mark as an RGBA square of ``size`` px, drawn 4x larger and scaled down (smooth edges)."""
    s = size * _SUPERSAMPLE
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if background:
        draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 5, fill=GREEN)
    width, height = s * 0.70, s * 0.30
    left, right = (s - width) / 2, (s + width) / 2
    draw.ellipse((left, s * 0.47, right, s * 0.47 + height), fill=RIM)  # the rim, below
    dome_top = s * 0.38
    draw.ellipse((left, dome_top, right, dome_top + height), fill=DOME)  # the dome
    inset_x, inset_y = width * 0.22, height * 0.22
    draw.ellipse(
        (left + inset_x, dome_top + inset_y, right - inset_x, dome_top + height - inset_y),
        outline=HIGHLIGHT,
        width=max(1, s // 40),
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)
```

Create `backend/src/sunday_clays/og/icons.py`:

```python
"""Write the PWA icons from the mark: ``uv run python -m sunday_clays.og.icons <folder>`` (D9)."""

import argparse
from pathlib import Path
from typing import Final

from PIL import Image

from sunday_clays.og.logo import GREEN, draw_mark

#: file name -> (size in px, maskable: full-bleed green with the mark inside the 80% safe zone)
ICONS: Final[dict[str, tuple[int, bool]]] = {
    "icon-192.png": (192, False),
    "icon-512.png": (512, False),
    "maskable-512.png": (512, True),
    "apple-touch-icon.png": (180, True),  # iOS rounds the corners itself
    "favicon-32.png": (32, False),
}


def _icon(size: int, maskable: bool) -> Image.Image:
    if not maskable:
        return draw_mark(size)
    canvas = Image.new("RGBA", (size, size), GREEN)
    inner = round(size * 0.8)
    offset = (size - inner) // 2
    mark = draw_mark(inner, background=False)
    canvas.alpha_composite(mark, (offset, offset))
    return canvas


def write_icons(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (size, maskable) in ICONS.items():
        path = out_dir / name
        _icon(size, maskable).save(path, format="PNG")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the Sunday Clays PWA icons.")
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    for path in write_icons(args.out_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `backend/src/sunday_clays/og/render.py`:

```python
"""The 1200x630 preview card (§3.1.4): fixed fonts, colours and coordinates, no metadata (D8)."""

import io
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.og.facts import PreviewFacts
from sunday_clays.og.html import image_lines
from sunday_clays.og.logo import GREEN, draw_mark

WIDTH: Final = 1200
HEIGHT: Final = 630
CREAM: Final = "#FEFBF6"
MINT: Final = "#D4E7DD"
CLAY_LIGHT: Final = "#E8A77A"
FONTS: Final = Path(__file__).parent / "fonts"
REGULAR: Final = FONTS / "Roboto-Regular.ttf"
MEDIUM: Final = FONTS / "Roboto-Medium.ttf"
MAX_TEXT_WIDTH: Final = 1040
MIN_SIZE: Final = 32
ELLIPSIS: Final = "…"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def fit(
    draw: ImageDraw.ImageDraw, text: str, path: Path, size: int
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Shrink in 2 px steps down to 32 px until ``text`` fits 1040 px, then truncate with …"""
    while size >= MIN_SIZE:
        font = _font(path, size)
        if draw.textlength(text, font=font) <= MAX_TEXT_WIDTH:
            return font, text
        size -= 2
    font = _font(path, MIN_SIZE)
    while text and draw.textlength(text + ELLIPSIS, font=font) > MAX_TEXT_WIDTH:
        text = text[:-1]
    return font, text.rstrip() + ELLIPSIS


def render_card(facts: PreviewFacts) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), GREEN)
    mark = draw_mark(160)
    image.paste(mark, (80, 80), mark)
    draw = ImageDraw.Draw(image)
    draw.text((80, 290), "Sunday Clays", font=_font(MEDIUM, 72), fill=CREAM)
    draw.text((80, 380), "Tri-County Gun Club", font=_font(REGULAR, 40), fill=MINT)
    lines = image_lines(facts)
    if lines is not None:
        font_a, line_a = fit(draw, lines[0], MEDIUM, 52)
        draw.text((80, 450), line_a, font=font_a, fill=CLAY_LIGHT)
        font_b, line_b = fit(draw, lines[1], REGULAR, 40)
        draw.text((80, 520), line_b, font=font_b, fill=CREAM)
    footer = _font(REGULAR, 28)
    draw.text((1120, 590), "sundayclays.claysmasher.com", font=footer, fill=MINT, anchor="rs")
    out = io.BytesIO()
    image.save(out, format="PNG")  # no pnginfo: no tEXt/iTXt chunks, same facts -> same bytes
    return out.getvalue()


@cached_by_data_version
def card_png(session: Session, facts: PreviewFacts) -> bytes:
    """The memoized card (per process, LRU 256, keyed by data_version; nothing on disk)."""
    return render_card(facts)
```

- [ ] **Step 9: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/og`
Expected: PASS. The dome's centre is at (80, 84.8) (0.38·160 + 0.15·160), about 9 px inside the highlight ring, so `test_mark_colours_and_rounded_corner` reads pure dome colour there; if it does not, fix the drawing, not the test.

- [ ] **Step 10: Generate and commit-stage the PWA icons**

Run: `cd backend && uv run python -m sunday_clays.og.icons ../frontend/public/icons`
Expected: five paths printed. Open `frontend/public/icons/icon-512.png` and `maskable-512.png` and check by eye: green rounded square (icon) / full green square (maskable), terracotta dome with a lighter ring, darker rim beneath.

- [ ] **Step 11: Write the failing route tests**

Create `backend/tests/integration/api/test_og_routes.py`:

```python
"""Public link-preview routes (Plan 19 §3.1, D6; §5.1, §5.2)."""

import io
import re
from datetime import date
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch

LATEST = "2026-09-27"
SCORE_NEAR_WORD = re.compile(r"\b(score|of)\s+([0-5]?\d|60)\b|\b([0-5]?\d|60)\s+(of|score)\b", re.I)


def _on(session: Session) -> None:
    set_switch(session, get_settings(), "link_previews", True)


def test_every_og_route_is_get_or_head_under_api_og(fx_client: TestClient) -> None:
    found = []
    for context in iter_route_contexts(cast(FastAPI, fx_client.app).routes):
        route = context.original_route
        if isinstance(route, APIRoute) and route.endpoint.__module__.endswith(".routes.og"):
            found.append(context.path_format)
            assert str(context.path_format).startswith("/api/og/")
            assert set(context.methods or ()) <= {"GET", "HEAD"}
    assert len(found) == 4


@pytest.mark.parametrize(
    "path", ["/api/og/page/", f"/api/og/page/events/{LATEST}", "/api/og/image/generic.png"]
)
def test_no_cookie_needed_and_head_mirrors_get(fx_client: TestClient, path: str) -> None:
    fx_client.cookies.clear()
    get = fx_client.get(path)
    head = fx_client.head(path)
    assert get.status_code == head.status_code == 200
    assert head.content == b""
    for name in ("content-type", "content-length", "cache-control", "x-robots-tag"):
        assert head.headers.get(name) == get.headers.get(name), name


def test_page_headers(fx_client: TestClient) -> None:
    response = fx_client.get(f"/api/og/page/events/{LATEST}")
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["cache-control"] == "private, no-cache"
    assert response.headers["vary"] == "User-Agent"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "etag" not in response.headers


def test_switch_off_every_path_is_generic(fx_client: TestClient) -> None:
    page = fx_client.get(f"/api/og/page/events/{LATEST}").text
    assert "Scores, trophies and stats" in page
    assert fx_client.get(f"/api/og/image/sunday/{LATEST}.png").status_code == 404


def test_switch_on_a_sunday_previews_its_facts(fx_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    n, round_type = fx_session.execute(
        text("SELECT n_shooters, round_type FROM events WHERE event_date = :d"),
        {"d": date(2026, 9, 27)},
    ).one()
    label = {"sporting": "Sporting", "super_sporting": "Super Sporting"}[round_type]
    page = fx_client.get(f"/api/og/page/l/events/{LATEST}").text
    assert f"Sunday, Sep 27, 2026 · {n} shooters · {label}" in page
    assert f'content="https://sundayclays.claysmasher.com/l/events/{LATEST}"' in page


def test_unknown_and_existing_dates_answer_the_same_status(
    fx_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    assert fx_client.get("/api/og/page/events/1999-01-03").status_code == 200
    assert fx_client.get(f"/api/og/page/events/{LATEST}").status_code == 200
    assert fx_client.get("/api/og/page/events/2026-13-45").status_code == 200


def test_sunday_png_on_off_and_deterministic(fx_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    first = fx_client.get(f"/api/og/image/sunday/{LATEST}.png?v=1")
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/png"
    assert first.headers["cache-control"] == "public, max-age=3600"
    assert Image.open(io.BytesIO(first.content)).size == (1200, 630)
    bump_data_version(fx_session)  # facts unchanged, so the bytes are too
    clear_cache()
    assert fx_client.get(f"/api/og/image/sunday/{LATEST}.png?v=2").content == first.content
    assert fx_client.get("/api/og/image/sunday/1999-01-03.png").status_code == 404
    assert fx_client.get("/api/og/image/sunday/nope.png").status_code == 404


def test_generic_png_is_cached_for_a_day(fx_client: TestClient) -> None:
    response = fx_client.get("/api/og/image/generic.png")
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"


def test_a_session_cookie_changes_nothing(
    fx_client: TestClient, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    fx_client.cookies.clear()
    path = f"/api/og/page/events/{LATEST}"
    assert fx_viewer_client.get(path).content == fx_client.get(path).content


def _assert_name_free(page: str, names: list[str]) -> None:
    for display_name in names:
        for part in {display_name, *[p.strip() for p in display_name.split(",")]}:
            if part:
                assert not re.search(rf"\b{re.escape(part)}\b", page), part
    assert not SCORE_NEAR_WORD.search(page)


@pytest.mark.parametrize("world", ["fx", "fx_special"])
def test_name_scan_every_sunday_and_every_shooter(
    request: pytest.FixtureRequest, world: str
) -> None:
    client = cast(TestClient, request.getfixturevalue(f"{world}_client"))
    session = cast(Session, request.getfixturevalue(f"{world}_session"))
    clear_cache()
    _on(session)
    names = [str(n) for n in session.execute(text("SELECT display_name FROM shooter_profiles")).scalars()]
    days = session.execute(text("SELECT event_date FROM events ORDER BY event_date")).scalars()
    ids = session.execute(text("SELECT shooter_id FROM shooter_profiles")).scalars()
    for day in days:
        _assert_name_free(client.get(f"/api/og/page/events/{day.isoformat()}").text, names)
    for shooter_id in ids:
        page = client.get(f"/api/og/page/shooters/{shooter_id}").text
        assert "Scores, trophies and stats" in page  # profiles are always generic
        _assert_name_free(page, names)
```

In `backend/tests/integration/api/test_route_auth_matrix.py`, replace

```python
PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout")}
```

with

```python
PUBLIC = {
    ("GET", "/api/health"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    # Plan 19 D6: link previews for crawlers, which cannot log in (no names, no scores)
    *{
        (method, path)
        for method in ("GET", "HEAD")
        for path in (
            "/api/og/page/",
            "/api/og/page/{path}",
            "/api/og/image/generic.png",
            "/api/og/image/sunday/{day}.png",
        )
    },
}
```

In `backend/tests/unit/api/test_etag_helpers.py`, replace

```python
        ("GET", "/api/features", False),
```

with

```python
        ("GET", "/api/features", False),
        ("GET", "/api/og/page/events/2026-09-27", False),
```

and replace

```python
        ("/api/features", "no-store"),
```

with

```python
        ("/api/features", "no-store"),
        ("/api/og/image/generic.png", None),  # the route's own Cache-Control stands
        ("/api/og/page/", None),
```

In `backend/tests/unit/api/test_app.py`, add at the end:

```python
def test_og_is_the_only_new_public_module() -> None:
    from sunday_clays.api.app import PUBLIC_ROUTE_MODULES, role_dependencies

    assert frozenset({"health", "auth", "og"}) == PUBLIC_ROUTE_MODULES
    assert role_dependencies("og") == []
```

- [ ] **Step 12: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_og_routes.py tests/integration/api/test_route_auth_matrix.py tests/unit/api/test_etag_helpers.py tests/unit/api/test_app.py`
Expected: FAIL: every `/api/og/*` request is 404 (no route), the og etag rows fail, and `test_og_is_the_only_new_public_module` fails.

- [ ] **Step 13: Write the routes, the public module and the ETag rule**

In `backend/src/sunday_clays/config.py`, replace

```python
    features_default_on: str = ""
```

with

```python
    features_default_on: str = ""
    # Plan 19 D11: every absolute URL (og:url, og:image, the recap link); the Host header is never used
    public_base_url: str = "https://sundayclays.claysmasher.com"
```

Create `backend/src/sunday_clays/api/routes/og.py`:

```python
"""Public link-preview routes (Plan 19 §3.1.2, D6): GET and HEAD under /api/og/ only.

Nothing here reads the session cookie, the User-Agent or the Host header, and nothing is logged
per request. Every answer is built from a ``PreviewFacts``, which has no name field (D10).
"""

from datetime import date
from typing import Annotated, Final

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from sunday_clays.analytics.cache import read_data_version
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import switch_on
from sunday_clays.og.facts import GENERIC, facts_for_path
from sunday_clays.og.html import render_page
from sunday_clays.og.render import card_png

router = APIRouter()

SettingsDep = Annotated[Settings, Depends(get_settings)]
GET_HEAD: Final = ["GET", "HEAD"]
NOINDEX: Final = {"X-Robots-Tag": "noindex, nofollow"}
PAGE_HEADERS: Final = {"Cache-Control": "private, no-cache", "Vary": "User-Agent", **NOINDEX}
SUNDAY_PNG_HEADERS: Final = {"Cache-Control": "public, max-age=3600", **NOINDEX}
GENERIC_PNG_HEADERS: Final = {"Cache-Control": "public, max-age=86400", **NOINDEX}


def _answer(request: Request, body: bytes, media_type: str, headers: dict[str, str]) -> Response:
    """A HEAD gets the GET's status and headers (Content-Length included) and no body (D6)."""
    if request.method == "HEAD":
        head = {**headers, "Content-Length": str(len(body))}
        return Response(content=b"", media_type=media_type, headers=head)
    return Response(content=body, media_type=media_type, headers=headers)


def _page(request: Request, session: SessionDep, settings: Settings, path: str) -> Response:
    facts = facts_for_path(session, path, switch_on(session, settings, "link_previews"))
    page = render_page(facts, path, settings.public_base_url, read_data_version(session))
    return _answer(request, page.encode(), "text/html", PAGE_HEADERS)


@router.api_route("/api/og/page/", methods=GET_HEAD, include_in_schema=False)
def og_home_page(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    return _page(request, session, settings, "")


@router.api_route("/api/og/page/{path:path}", methods=GET_HEAD, include_in_schema=False)
def og_page(path: str, request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    return _page(request, session, settings, path)


@router.api_route("/api/og/image/generic.png", methods=GET_HEAD, include_in_schema=False)
def og_generic_image(request: Request, session: SessionDep) -> Response:
    return _answer(request, card_png(session, GENERIC), "image/png", GENERIC_PNG_HEADERS)


@router.api_route("/api/og/image/sunday/{day}.png", methods=GET_HEAD, include_in_schema=False)
def og_sunday_image(
    day: str, request: Request, session: SessionDep, settings: SettingsDep
) -> Response:
    """404 while link_previews is off (for every caller: crawlers have no role) or for no Sunday.

    ``?v=<data_version>`` is a cache-buster only and is never read.
    """
    if not switch_on(session, settings, "link_previews"):
        raise HTTPException(status_code=404)
    try:
        event_date = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(status_code=404) from None
    facts = facts_for_path(session, f"events/{event_date.isoformat()}", True)
    if facts.kind == "generic":
        raise HTTPException(status_code=404)
    return _answer(request, card_png(session, facts), "image/png", SUNDAY_PNG_HEADERS)
```

In `backend/src/sunday_clays/api/app.py`, replace

```python
PUBLIC_ROUTE_MODULES: Final = frozenset({"health", "auth"})
```

with

```python
PUBLIC_ROUTE_MODULES: Final = frozenset({"health", "auth", "og"})  # og: Plan 19 D6
```

In `backend/src/sunday_clays/api/etag.py`, replace

```python
    "/api/features",  # Plan 19 D3: switches change without a data_version bump
)
```

with

```python
    "/api/features",  # Plan 19 D3: switches change without a data_version bump
    "/api/og/",  # Plan 19 D6: public previews set their own Cache-Control
)
# Plan 19: routes whose own Cache-Control must stand (the middleware sets none for them)
OWN_CACHE_CONTROL_PREFIXES: tuple[str, ...] = ("/api/og/",)
```

and replace

```python
    """`no-store` for auth, admin and bump counts, `private, no-cache` for other /api paths."""
    if path.startswith(NO_STORE_PREFIXES) or (
```

with

```python
    """`no-store` for auth, admin and bump counts, `private, no-cache` for other /api paths.

    None for link previews (their route sets public caching) and for non-API paths.
    """
    if path.startswith(OWN_CACHE_CONTROL_PREFIXES):
        return None
    if path.startswith(NO_STORE_PREFIXES) or (
```

- [ ] **Step 14: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_og_routes.py tests/integration/api/test_route_auth_matrix.py tests/unit/api tests/unit/og`
Expected: PASS. If `test_name_scan_every_sunday_and_every_shooter` fails on a word that is both a fixture name part and ordinary copy (for example a last name "Sunday"), report it; do not weaken the scan.

- [ ] **Step 15: Run the backend gates and check the image builds multi-arch**

Run the backend gates. Then: `docker buildx build --platform linux/arm64 -f backend/Dockerfile backend --load -t sc-backend-arm64-check` (from the repo root) and `docker run --rm --platform linux/arm64 sc-backend-arm64-check python -c "from sunday_clays.og.render import render_card; from sunday_clays.og.facts import GENERIC; print(len(render_card(GENERIC)))"`.
Expected: the gates are clean; the arm64 image prints a byte count (Pillow's aarch64 wheel installs, and the fonts ship inside the package). If buildx/QEMU is not available locally, say so in the report; CI's `docker-arm64` job builds the same image.

- [ ] **Step 16: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/sunday_clays/config.py \
  backend/src/sunday_clays/og backend/src/sunday_clays/api/routes/og.py backend/src/sunday_clays/api/app.py \
  backend/src/sunday_clays/api/etag.py frontend/public/icons backend/tests/unit/og \
  backend/tests/integration/api/test_og_routes.py backend/tests/integration/api/test_route_auth_matrix.py \
  backend/tests/unit/api/test_etag_helpers.py backend/tests/unit/api/test_app.py
git commit -m "feat(og): name-free link previews, the logo and the PWA icons (Plan 19 T3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: Caddy crawler routing, `/l/` share links, PWA headers, CSP, runbook and the link-preview e2e (`task/19-4-caddy-previews`, wave 3)

**Why the Caddy layout differs from the spec's snippet (Decision 14, recorded here because only this task touches it).** Caddy runs directives in a fixed order, and `handle` comes **before** `route`. The site already ends in a catch-all `handle { … }` that matches every request, so a top-level `route { … }` (the spec's §3.1.3 snippet) would never run. The spec's intent (crawler first on every SPA path including `/l/…`, then the open-redirect guard, then the share redirect) is kept with two blocks: a top-level `handle @crawler` (named-matcher handles sort after the path handles such as `/api/*`, `/assets/*`, `/icons/*`, which `@crawler` excludes anyway, and before the catch-all), and a `handle /l/*` whose `route` checks `@crawler` **first**, then `@share_unsafe`, then redirects. Inside `route`, directives run in the written order (D7's reason for `route`). The test script and the e2e pin the behaviour, so a wrong order fails CI.

**Files:**
- Modify: `deploy/caddy/Caddyfile`
- Create: `deploy/caddy/user-agents.tsv` (the shared UA table, §3.1.3)
- Create: `deploy/caddy/test_crawler_ua.sh`
- Modify: `deploy/README.md` ("Public access" step 4, new "Link previews and Cloudflare" subsection)
- Modify: `.github/workflows/ci.yml` (one step in the `e2e` job)
- Modify: `backend/tests/unit/api/test_edge_limits.py` (one new test pinning the block order)
- Create: `frontend/e2e/link-previews.spec.ts`

**Interfaces:**
- Consumes: T3's `/api/og/page/{path}`, `/api/og/image/*`; T1's `FEATURES_DEFAULT_ON` (link previews on in the e2e stack).
- Produces: the edge behaviour T9 relies on (`/sw.js` and `/manifest.webmanifest` served `no-cache` with the right headers, `/icons/*` cached a day, CSP `manifest-src 'self'; worker-src 'self'`); `deploy/caddy/user-agents.tsv` (columns `expect<TAB>user-agent`, `expect` ∈ {`crawler`, `person`}).

- [ ] **Step 1: Write the failing Caddyfile shape test**

In `backend/tests/unit/api/test_edge_limits.py`, add at the end of the file:

```python
def _site_block() -> str:
    text = CADDYFILE.read_text()
    return text[text.index(":80 {") :]


def test_crawlers_and_share_links_are_routed_before_the_spa() -> None:
    """Plan 19 D7: the crawler check and /l/ handling exist, and /l/ checks crawlers first."""
    site = _site_block()
    share = site[site.index("\thandle /l/* {") :]
    share = share[: share.index("\n\t}\n")]
    assert share.index("handle @crawler") < share.index("handle @share_unsafe")
    assert share.index("handle @share_unsafe") < share.index("uri strip_prefix /l")
    assert "\thandle @crawler {" in site  # crawlers on every other SPA path
    assert "rewrite * /api/og/page{path}?{query}" in site


def test_the_spa_varies_by_user_agent_and_the_csp_allows_the_pwa() -> None:
    site = _site_block()
    catch_all = site[site.rindex("\thandle {") :]
    assert "header Vary User-Agent" in catch_all
    csp = CADDYFILE.read_text()
    assert "manifest-src 'self'" in csp and "worker-src 'self'" in csp
    for path in ("/sw.js", "/manifest.webmanifest", "/icons/*"):
        assert f"\thandle {path} {{" in site, path
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest -q tests/unit/api/test_edge_limits.py`
Expected: FAIL: `ValueError: substring not found` (no `handle /l/*` yet) and the CSP assertion fails.

- [ ] **Step 3: Edit the Caddyfile**

In `deploy/caddy/Caddyfile`, replace

```caddyfile
		Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
```

with

```caddyfile
		Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
```

Replace

```caddyfile
:80 {
	encode zstd gzip

	import security_headers

```

with

```caddyfile
:80 {
	encode zstd gzip

	import security_headers

	# Plan 19 link previews (D7). Chat-app crawlers cannot log in, so on any SPA path they get a
	# name-free meta page from /api/og/page/<path>. In-app browsers (FBAN/FBAV, LinkedInApp,
	# "Twitter for iPhone", Discord's desktop client "discord/") are people and must not match.
	@crawler {
		method GET HEAD
		header_regexp User-Agent (?i)(facebookexternalhit|Twitterbot|Slackbot|Discordbot|WhatsApp|TelegramBot|LinkedInBot|Applebot|SkypeUriPreview)
		not path /api/* /assets/* /trophies/* /icons/* /sw.js /manifest.webmanifest
	}
	@share_unsafe path_regexp ^/l/[/\\]

	# Share links: "/l/<path>" previews for crawlers and redirects people to "/<path>" (query kept).
	# Caddy runs `handle` before `route`, and sorts sibling handles (path matchers first), so the
	# crawler check is repeated FIRST inside this block's `route`, where the written order holds.
	handle /l/* {
		route {
			handle @crawler {
				request_body {
					max_size 264KiB
				}
				rewrite * /api/og/page{path}?{query}
				import api
			}
			# "/l//evil.com" or "/l/\evil.com" would become a protocol-relative Location: refuse it.
			handle @share_unsafe {
				redir / 302
			}
			handle {
				uri strip_prefix /l
				redir * {uri} 302
			}
		}
	}

	# Crawlers on every other SPA path (named-matcher handles sort after the path handles below).
	handle @crawler {
		request_body {
			max_size 264KiB
		}
		rewrite * /api/og/page{path}?{query}
		import api
	}

	# Plan 19 PWA (§3.4): the service worker and manifest always revalidate; icons cache a day.
	handle /sw.js {
		root * /srv
		header Cache-Control "no-cache"
		header Service-Worker-Allowed "/"
		file_server
	}
	handle /manifest.webmanifest {
		root * /srv
		header Content-Type "application/manifest+json"
		header Cache-Control "no-cache"
		file_server
	}
	handle /icons/* {
		root * /srv
		header Cache-Control "public, max-age=86400"
		file_server
	}

```

Replace

```caddyfile
	# Everything else: the file if it exists, else index.html (SPA deep links); always revalidated.
	handle {
		root * /srv
		header Cache-Control "no-cache"
		try_files {path} /index.html
		file_server
	}
```

with

```caddyfile
	# Everything else: the file if it exists, else index.html (SPA deep links); always revalidated.
	# Vary: User-Agent, because crawlers get the meta page at the same URL (Plan 19 §3.1.3).
	handle {
		root * /srv
		header Cache-Control "no-cache"
		header Vary User-Agent
		try_files {path} /index.html
		file_server
	}
```

Until Task 9 ships `frontend/public/manifest.webmanifest` and the built `sw.js`, the two PWA handles answer 404, which no current page requests.

- [ ] **Step 4: Run it to verify it passes**

Run: `cd backend && uv run pytest -q tests/unit/api/test_edge_limits.py`
Expected: PASS (the existing limit tests still see exactly `{IMPORTS_PATH, "/api/*"}` at the top level: the crawler handles' `request_body` sits deeper than one tab).

- [ ] **Step 5: Write the UA table and the script**

Create `deploy/caddy/user-agents.tsv` (tab-separated; `link-previews.spec.ts` reads the same file):

```text
crawler	facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)
crawler	WhatsApp/2.23.20.0 A
crawler	Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)
crawler	Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)
crawler	TelegramBot (like TwitterBot)
crawler	LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)
crawler	Twitterbot/1.0
crawler	Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)
crawler	SkypeUriPreview Preview/0.5
person	Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/400.0.0.0]
person	LinkedInApp/9.0 (iPhone; iOS 17.0)
person	Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Twitter for iPhone/10.0
person	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9150 Chrome/120.0.0.0 Electron/28.0.0 Safari/537.36
person	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36
```

Create `deploy/caddy/test_crawler_ua.sh` (mode 0755):

```bash
#!/usr/bin/env bash
# Plan 19 §3.1.3: validate the Caddyfile, then check crawler routing and /l/ redirects against a
# running stack. Usage: deploy/caddy/test_crawler_ua.sh <base url> [frontend image]
set -euo pipefail

BASE="${1:?usage: test_crawler_ua.sh <base url> [frontend image]}"
IMAGE="${2:-ghcr.io/gitgat/sunday-clays-frontend:ci}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DAY="2026-09-27"
fail=0

docker run --rm "$IMAGE" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

check() { # $1 description, $2 expected, $3 actual
  if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1: expected [$2], got [$3]"; fail=1; fi
}

while IFS=$'\t' read -r expect ua; do
  [[ -z "$expect" ]] && continue
  body="$(curl -fsS -A "$ua" "$BASE/events/$DAY")"
  if grep -q 'property="og:title"' <<<"$body"; then got=crawler; else got=person; fi
  check "$expect: $ua" "$expect" "$got"
  if [[ "$expect" == crawler ]]; then
    status="$(curl -s -o /dev/null -w '%{http_code}' -A "$ua" "$BASE/l/events/$DAY")"
    check "share link previews for $ua" 200 "$status"
  fi
done <"$HERE/user-agents.tsv"

browser='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36'
location() { curl -s -o /dev/null -A "$browser" -w '%{redirect_url}' "$BASE$1"; }
check "share redirect" "$BASE/events/$DAY" "$(location "/l/events/$DAY")"
check "share redirect keeps the query" "$BASE/events/$DAY?w=3m" "$(location "/l/events/$DAY?w=3m")"
check "open redirect //" "$BASE/" "$(location '/l//evil.com')"
check "open redirect %2F%2F" "$BASE/" "$(location '/l/%2F%2Fevil.com')"
check "open redirect backslash" "$BASE/" "$(location '/l/%5Cevil.com')"
exit "$fail"
```

`curl -w '%{redirect_url}'` resolves a relative `Location` against the request URL, so `/events/…` reads back as `$BASE/events/…`; the e2e below checks the raw header.

- [ ] **Step 6: Write the failing e2e**

Create `frontend/e2e/link-previews.spec.ts`:

```ts
import { readFileSync } from 'node:fs';
import { request as pwRequest, type APIRequestContext } from '@playwright/test';
import { expect, test } from './fixtures';

/**
 * Link previews through Caddy (Plan 19 §3.1, §5.3). The stack runs with link_previews on
 * (FEATURES_DEFAULT_ON). The UA cases come from deploy/caddy/user-agents.tsv, the same table the
 * Caddy script reads.
 */

const DAY = '2026-09-27';
const FB = 'facebookexternalhit/1.1';
const WHATSAPP = 'WhatsApp/2.23.20.0 A';
const BROWSER =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0.0.0 Safari/537.36';
const BASE = 'https://sundayclays.claysmasher.com';
const ROUND_TYPES: Record<string, string> = { sporting: 'Sporting', super_sporting: 'Super Sporting' };

const table = readFileSync(new URL('../../deploy/caddy/user-agents.tsv', import.meta.url), 'utf8')
  .split('\n')
  .filter((line) => line.trim() !== '')
  .map((line) => {
    const [expectation, ua] = line.split('\t');
    return { expectation: expectation as 'crawler' | 'person', ua: ua as string };
  });

async function get(api: APIRequestContext, path: string, ua: string) {
  return api.get(path, { headers: { 'User-Agent': ua }, maxRedirects: 0 });
}

function meta(html: string, property: string): string | null {
  const match = new RegExp(`(?:property|name)="${property}" content="([^"]*)"`).exec(html);
  return match?.[1] ?? null;
}

test.describe('link previews', () => {
  test('a crawler on a Sunday gets its date, turnout and round type', async ({ request }) => {
    const event = (await (await request.get(`/api/events/${DAY}`)).json()) as {
      n_shooters: number;
      round_type: string;
    };
    const html = await (await get(request, `/events/${DAY}`, FB)).text();
    expect(meta(html, 'og:description')).toBe(
      `Sunday, Sep 27, 2026 · ${String(event.n_shooters)} shooters · ${ROUND_TYPES[event.round_type] ?? ''}`,
    );
    const image = meta(html, 'og:image') ?? '';
    expect(image.startsWith(`${BASE}/api/og/image/sunday/${DAY}.png?v=`)).toBe(true);
    const png = await request.get(new URL(image).pathname + new URL(image).search);
    expect(png.headers()['content-type']).toBe('image/png');
    const bytes = await png.body();
    // PNG IHDR: width and height are big-endian at bytes 16..23
    expect(bytes.readUInt32BE(16)).toBe(1200);
    expect(bytes.readUInt32BE(20)).toBe(630);
  });

  test('profiles and Home are generic', async ({ request }) => {
    for (const path of ['/shooters/3', '/']) {
      const html = await (await get(request, path, FB)).text();
      expect(meta(html, 'og:description'), path).toBe(
        'Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.',
      );
    }
  });

  test('a crawler on the share prefix gets the meta page, not a 302', async ({ request }) => {
    for (const ua of [FB, WHATSAPP]) {
      const response = await get(request, `/l/events/${DAY}`, ua);
      expect(response.status(), ua).toBe(200);
      const html = await response.text();
      expect(meta(html, 'og:description'), ua).toMatch(/^Sunday, Sep 27, 2026 · /);
      expect(meta(html, 'og:url'), ua).toBe(`${BASE}/l/events/${DAY}`);
    }
  });

  test('HEAD works for crawlers and images', async ({ request }) => {
    const page = await request.head(`/l/events/${DAY}`, { headers: { 'User-Agent': FB } });
    expect(page.status()).toBe(200);
    expect(page.headers()['content-type']).toMatch(/^text\/html/);
    const image = await request.head('/api/og/image/generic.png');
    expect(image.status()).toBe(200);
    expect(image.headers()['content-type']).toBe('image/png');
  });

  test('people on a share link are redirected, query kept', async ({ request }) => {
    const plain = await get(request, `/l/events/${DAY}`, BROWSER);
    expect(plain.status()).toBe(302);
    expect(plain.headers()['location']).toBe(`/events/${DAY}`);
    const query = await get(request, `/l/events/${DAY}?w=3m`, BROWSER);
    expect(query.headers()['location']).toBe(`/events/${DAY}?w=3m`);
  });

  test('the open-redirect guard sends unsafe share paths home', async ({ request }) => {
    for (const path of ['/l//evil.com', '/l/%2F%2Fevil.com', '/l/%5Cevil.com']) {
      const response = await get(request, path, BROWSER);
      expect(response.status(), path).toBe(302);
      expect(response.headers()['location'], path).toBe('/');
    }
  });

  test('the meta page is private, varies by UA and carries the CSP', async ({ request }) => {
    const response = await get(request, `/events/${DAY}`, FB);
    const headers = response.headers();
    expect(headers['cache-control']).toBe('private, no-cache');
    expect(headers['vary']).toMatch(/User-Agent/);
    expect(headers['content-security-policy']).toContain("default-src 'self'");
  });

  for (const { expectation, ua } of table) {
    test(`${expectation}: ${ua.slice(0, 60)}`, async ({ request }) => {
      const html = await (await get(request, `/events/${DAY}`, ua)).text();
      if (expectation === 'crawler') {
        expect(meta(html, 'og:title')).toBe('Sunday Clays · Tri-County Gun Club');
      } else {
        expect(meta(html, 'og:title')).toBeNull();
        expect(html).toContain('<div id="root">');
      }
    });
  }

  test('a spoofed crawler UA with a session gets the same name-free bytes', async ({
    request,
    baseURL,
  }) => {
    const anonymous = await pwRequest.newContext({ baseURL });
    try {
      const withCookie = await (await get(request, `/events/${DAY}`, FB)).text();
      const without = await (await get(anonymous, `/events/${DAY}`, FB)).text();
      expect(withCookie).toBe(without);
      for (const name of ['Finnegan', 'Stockton', 'Hadley', 'Kaplan']) {
        expect(withCookie).not.toContain(name);
      }
    } finally {
      await anonymous.dispose();
    }
  });
});
```

The `request` fixture carries the project's viewer storage state, so it is the "with a session" client; `pwRequest.newContext` has no cookies.

- [ ] **Step 7: Run the script and the e2e to verify they fail on the base stack**

Start the e2e stack from the **base** commit's images (`IMAGE_TAG=task19-4-base`, built before Step 3), then run `deploy/caddy/test_crawler_ua.sh http://localhost:18080 ghcr.io/gitgat/sunday-clays-frontend:task19-4-base` and `pnpm exec playwright test link-previews.spec.ts --project=desktop`.
Expected: FAIL: every crawler UA reads as `person` (the SPA), share links 404 into the SPA, and the e2e's crawler tests fail. Paste both as RED.

- [ ] **Step 8: Rebuild with the new Caddyfile and run both again**

Rebuild the frontend image with this task's Caddyfile (`docker compose … build caddy` then `up -d --wait`). Run: `deploy/caddy/test_crawler_ua.sh http://localhost:18080 ghcr.io/gitgat/sunday-clays-frontend:task19` and `pnpm exec playwright test link-previews.spec.ts --project=desktop --project=mobile`.
Expected: the script prints only `ok` lines and exits 0; the e2e passes in both projects.

- [ ] **Step 9: Run the crawler script in CI**

In `.github/workflows/ci.yml`, replace

```yaml
      - run: IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
      - run: pnpm exec playwright test
```

with

```yaml
      - run: IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
      # Plan 19: Caddyfile validation and crawler routing against the running stack
      - run: deploy/caddy/test_crawler_ua.sh http://localhost:8080 ghcr.io/gitgat/sunday-clays-frontend:ci
      - run: pnpm exec playwright test
```

- [ ] **Step 10: Write the runbook additions**

In `deploy/README.md`, replace

```markdown
   - Leave the default cache behaviour: the API sends `private, no-cache` and `/api/*` has no
     cacheable extension; `/assets/*` is immutable and may be cached.
   - Do **not** add Cloudflare Access.
```

with

```markdown
   - Leave the default cache behaviour. The API sends `private, no-cache`, except the link-preview
     images under `/api/og/image/` (`.png`, cached at the edge: generic one day, Sunday images one
     hour). The preview page sends `private, no-cache` and `Vary: User-Agent`. `/assets/*` is
     immutable and may be cached. Do **not** add a Cache Everything rule. Turning `link_previews`
     off stops new Sunday previews at once, but an image already at the edge can be served for up
     to an hour, and a preview already posted in a chat stays as it is.
   - Do **not** add Cloudflare Access (if it is ever added, see "Link previews and Cloudflare").
```

and replace

```markdown
On the LAN the site answers at `https://sundayclays.thehalf.io` (router `sundayclays-lan`, the
```

with

```markdown
### Link previews and Cloudflare

Chat apps fetch a shared link with a crawler that cannot log in. Caddy sends known crawlers
(`deploy/caddy/user-agents.tsv`) on any SPA path to a name-free preview page, and `/l/<path>` is
the app's share prefix: crawlers get the preview, people get a 302 to `/<path>`.

1. Today there is no Cloudflare Access, so no Cloudflare change is needed. Check it with
   `curl -s -A 'facebookexternalhit/1.1' https://sundayclays.claysmasher.com/events/<latest Sunday> | grep -E 'og:(description|url)'`,
   which must print the Sunday line and an `og:url` of
   `https://sundayclays.claysmasher.com/l/events/<latest Sunday>`. Check
   `curl -sI https://sundayclays.claysmasher.com/api/og/image/generic.png` for `200` and
   `content-type: image/png`.
2. Caching: see step 4 above (no Cache Everything rule; Sunday images can live at the edge for an
   hour after `link_previews` is turned off).
3. If Cloudflare Access is ever put in front of `sundayclays.claysmasher.com`, add this bypass
   **before** enabling the Access app for the host:
   - Zero Trust → Access → Applications → **Add an application** → **Self-hosted**.
   - Name `sundayclays-link-previews`. Session duration: default.
   - Application domain 1: subdomain `sundayclays`, domain `claysmasher.com`, path `l/*`.
   - Application domain 2: subdomain `sundayclays`, domain `claysmasher.com`, path `api/og/*`.
   - Policy: name `bypass-previews`, **Action: Bypass**, **Include: Everyone**. No other rules.
   - Save. Access evaluates the most specific path first, so these two paths stay public while the
     host-wide app gates everything else.
   - Verify: `curl -s -A 'WhatsApp/2.23' https://sundayclays.claysmasher.com/l/events/<latest Sunday> | grep -E 'og:(title|url)'`
     prints the title and an `og:url` under `/l/`; `curl -sI -A 'facebookexternalhit/1.1' <that og:url>`
     returns 200 (not the Access redirect); and
     `curl -sI https://sundayclays.claysmasher.com/events/<latest Sunday>` returns the Access
     redirect (302 to `*.cloudflareaccess.com`).
   - Only `/l/…` links preview while Access is on. The app's own share links already use `/l/`.
4. Leave Bot Fight Mode off (it is off today). It challenges unverified preview fetchers such as
   WhatsApp's.

On the LAN the site answers at `https://sundayclays.thehalf.io` (router `sundayclays-lan`, the
```

- [ ] **Step 11: Run the gates and commit**

Run the backend gates (for `test_edge_limits.py`), `cd frontend && pnpm lint && pnpm exec prettier --check e2e/link-previews.spec.ts`, and `shellcheck deploy/caddy/test_crawler_ua.sh` if `shellcheck` is installed.
Expected: clean.

```bash
chmod +x deploy/caddy/test_crawler_ua.sh
git add deploy/caddy/Caddyfile deploy/caddy/user-agents.tsv deploy/caddy/test_crawler_ua.sh deploy/README.md \
  .github/workflows/ci.yml backend/tests/unit/api/test_edge_limits.py frontend/e2e/link-previews.spec.ts
git commit -m "feat(edge): crawler previews, /l/ share links, PWA headers and the preview runbook (Plan 19 T4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 5: First-visit tour and glossary (`task/19-5-tour-glossary`, wave 3)

**Files:**
- Create: `frontend/src/features/tour/{steps.ts, steps.test.ts, state.ts, state.test.ts, target.ts, TourDialog.tsx, TourDialog.test.tsx, homeWidget.tsx, homeWidget.test.tsx}`
- Create: `frontend/src/features/glossary/{triggers.ts, explainerLint.test.ts, routes.tsx, routes.test.tsx, mocks.ts}`, `frontend/src/features/glossary/pages/{GlossaryPage.tsx, GlossaryPage.test.tsx}`
- Create: `frontend/src/components/ui/WordsUsedHere.tsx`, `frontend/src/components/ui/WordsUsedHere.test.tsx`
- Modify: `frontend/src/components/ui/Explainer.tsx` (render `WordsUsedHere`)
- Modify: `frontend/src/components/ui/Sheet.tsx` (export `trapTab`, `inertOthers`)
- Modify: `frontend/src/components/ui/Card.tsx` (`tour` prop), `frontend/src/components/ui/Card.test.tsx`
- Modify: `frontend/src/app/registry.ts` (`NavItem.tourId`), `frontend/src/components/layout/NavList.tsx`, `frontend/src/components/layout/AppShell.test.tsx`
- Modify: `frontend/src/features/home/pages/HomePage.tsx`, `frontend/src/features/home/pages/HomePage.test.tsx`
- Modify: `frontend/src/features/home/components/LatestEventCard.tsx`, `frontend/src/features/insights/components/FeedSections.tsx`, `frontend/src/features/achievements/NextTrophy.tsx`, `frontend/src/features/achievements/routes.tsx`, `frontend/src/components/layout/TimeWindowFilter.tsx`
- Modify: every `frontend/src/features/*/explainers.ts` the trigger lint names (Step 15), and any `frontend/src/features/*/explainers.test.ts` that compares one of those entries with `toEqual` (Step 15)
- Modify: `frontend/src/app/navRegistry.test.ts` (`glossary: 135`)
- Modify: `frontend/src/features/pageviews/pageKind.test.ts` (two pin rows: `/glossary`, `/admin/recap`)
- Modify: `frontend/e2e/fixtures.ts` (`tourSeen`)
- Create: `frontend/e2e/tour.spec.ts`, `frontend/e2e/glossary.spec.ts`

**Interfaces:**
- Consumes: T2's `useFeature`, `FeatureGate`, `AdminPreviewBadge`, `NavItem.feature`, `GLOSSARY_TERMS`, `termById`, `GlossaryTermId`, `Explainer.terms`, `BANNED_WORDS`, `allStrings`; `lib/useMediaQuery.useMediaQuery`; `features/home/widgets.HomeWidget`.
- Produces (T9 relies on the first three):
  - `features/tour/state.ts`: `TOUR_KEY = 'sc.tour.v1'`, `isTourDone(): boolean`, `markTourDone(): void`, `subscribeTour(listener): () => void`, `useTourDone(): boolean`, `resetTourForTests(): void`.
  - `features/tour/target.ts`: `firstVisible(id: string): HTMLElement | null`, `REDUCED_MOTION_QUERY`.
  - `features/tour/homeWidget.tsx`: `homeWidget = { id: 'tour', order: -10, slot: 'hero', Component: TourWidget }`; `HOME_TITLE_ID = 'home-title'`.
  - `features/glossary/triggers.ts`: `GLOSSARY_TRIGGERS: Record<GlossaryTermId, RegExp>`, `missingTerms(explainer: Explainer): GlossaryTermId[]`.
  - `components/ui/Card.tsx`: `CardProps.tour?: string` (rendered as `data-tour`).
  - `app/registry.ts`: `NavItem.tourId?: string` (rendered as `data-tour` on the nav link).
  - Route `/glossary` (wrapped in `FeatureGate feature="tour_glossary"`), nav `{ label: 'Glossary', path: '/glossary', icon: BookOpen, order: 135, feature: 'tour_glossary' }`.
  - `e2e/fixtures.ts`: option fixture `tourSeen` (default `true`).

- [ ] **Step 1: Write the failing tour copy and state tests**

Create `frontend/src/features/tour/steps.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { TOUR_STEPS } from './steps';

describe('tour steps', () => {
  it('has the five steps of the spec, in order', () => {
    expect(TOUR_STEPS.map((s) => [s.target, s.title])).toEqual([
      ['sunday', 'The latest Sunday'],
      ['you', 'Which one are you?'],
      ['insights', 'Insights and fist bumps'],
      ['trophies', 'Trophies'],
      ['window', 'Time window'],
    ]);
  });

  it('uses no banned word', () => {
    for (const text of allStrings(TOUR_STEPS)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

Create `frontend/src/features/tour/state.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { isTourDone, markTourDone, resetTourForTests, subscribeTour, TOUR_KEY } from './state';

afterEach(() => resetTourForTests());

describe('tour state', () => {
  it('is done once marked, and remembered in localStorage', () => {
    expect(isTourDone()).toBe(false);
    markTourDone();
    expect(isTourDone()).toBe(true);
    expect(localStorage.getItem(TOUR_KEY)).toBe('done');
  });

  it('reads a stored "done"', () => {
    localStorage.setItem(TOUR_KEY, 'done');
    expect(isTourDone()).toBe(true);
  });

  it('notifies subscribers', () => {
    const listener = vi.fn();
    const unsubscribe = subscribeTour(listener);
    markTourDone();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
    markTourDone();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('falls back to memory when storage throws (at most once per load)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(isTourDone()).toBe(false);
    markTourDone();
    expect(isTourDone()).toBe(true);
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/tour`
Expected: FAIL, unresolved `./steps` and `./state`.

- [ ] **Step 3: Write the steps, the state and the target helpers**

Create `frontend/src/features/tour/steps.ts` (copy from spec §3.2.1, verbatim):

```ts
export type TourTarget = 'sunday' | 'you' | 'insights' | 'trophies' | 'window';

export interface TourStep {
  target: TourTarget;
  title: string;
  body: string;
}

export const TOUR_STEPS: readonly TourStep[] = [
  {
    target: 'sunday',
    title: 'The latest Sunday',
    body: 'Every Sunday’s results land here once the scores are uploaded. Tap "Full results" for the whole sheet.',
  },
  {
    target: 'you',
    title: 'Which one are you?',
    body: 'Pick your name once and Home shows your own numbers, your next trophy and a link to your page. It is saved on this device only.',
  },
  {
    target: 'insights',
    title: 'Insights and fist bumps',
    body: 'Short, true things the numbers say about the club and its shooters. Tap the fist to give a bump. Bumps are anonymous.',
  },
  {
    target: 'trophies',
    title: 'Trophies',
    body: 'Trophies are earned by showing up and shooting. Your next one, and how close you are, shows on Home once you pick your name.',
  },
  {
    target: 'window',
    title: 'Time window',
    body: 'Charts and stats follow this window. 8W is the last 8 weeks. Pick 3M, 6M, 12M, YTD, All, or your own dates.',
  },
];
```

Create `frontend/src/features/tour/state.ts`:

```ts
import { useSyncExternalStore } from 'react';

/** "done" once the tour was finished, skipped or closed (Plan 19 D12). */
export const TOUR_KEY = 'sc.tour.v1';

let doneThisLoad = false; // storage blocked: the tour still shows at most once per page load
const listeners = new Set<() => void>();

export function isTourDone(): boolean {
  if (doneThisLoad) return true;
  try {
    return localStorage.getItem(TOUR_KEY) === 'done';
  } catch {
    return false;
  }
}

export function markTourDone(): void {
  doneThisLoad = true;
  try {
    localStorage.setItem(TOUR_KEY, 'done');
  } catch {
    // Private mode or blocked storage: the in-memory flag covers this page load.
  }
  for (const listener of listeners) listener();
}

export function subscribeTour(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTourDone(): boolean {
  return useSyncExternalStore(subscribeTour, isTourDone, () => true);
}

export function resetTourForTests(): void {
  doneThisLoad = false;
  listeners.clear();
}
```

Create `frontend/src/features/tour/target.ts`:

```ts
export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';
export const PHONE_QUERY = '(max-width: 640px)';

/** The first `[data-tour=id]` element in document order with a non-zero box, or null. */
export function firstVisible(id: string): HTMLElement | null {
  for (const el of document.querySelectorAll<HTMLElement>(`[data-tour="${id}"]`)) {
    const box = el.getBoundingClientRect();
    if (box.width > 0 && box.height > 0) return el;
  }
  return null;
}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/tour`
Expected: PASS.

- [ ] **Step 5: Write the failing dialog and widget tests**

Create `frontend/src/features/tour/TourDialog.test.tsx`:

```tsx
import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { TOUR_STEPS } from './steps';
import { TourDialog } from './TourDialog';

function box(width: number, height: number): DOMRect {
  return { x: 10, y: 20, top: 20, left: 10, width, height, right: 10 + width, bottom: 20 + height, toJSON: () => ({}) };
}

function target(id: string, visible: boolean): HTMLElement {
  const el = document.createElement('div');
  el.dataset.tour = id;
  el.getBoundingClientRect = () => box(visible ? 200 : 0, visible ? 100 : 0);
  document.body.appendChild(el);
  return el;
}

afterEach(() => {
  document.querySelectorAll('[data-tour]').forEach((el) => el.remove());
});

describe('TourDialog', () => {
  it('is a labelled, described modal dialog that starts on step 1 with focus on its title', async () => {
    target('sunday', true);
    renderWithProviders(<TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />);
    const dialog = screen.getByRole('dialog', { name: 'The latest Sunday' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleDescription(TOUR_STEPS[0]?.body ?? '');
    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'The latest Sunday' })).toHaveFocus();
  });

  it('walks Next to Done and closes on Done, Skip and Esc', async () => {
    const onClose = vi.fn();
    const { user } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={onClose} />,
    );
    for (const title of ['Which one are you?', 'Insights and fist bumps', 'Trophies', 'Time window']) {
      await user.click(screen.getByRole('button', { name: 'Next' }));
      expect(screen.getByRole('dialog', { name: title })).toBeInTheDocument();
    }
    await user.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByText('Step 4 of 5')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await user.click(screen.getByRole('button', { name: 'Done' }));
    await user.click(screen.getByRole('button', { name: 'Skip tour' }));
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it('traps Tab inside the dialog', async () => {
    const { user } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    await user.click(screen.getByRole('button', { name: 'Next' })); // step 2: Back, Next, Skip
    const skip = screen.getByRole('button', { name: 'Skip tour' });
    skip.focus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Back' })).toHaveFocus();
    await user.tab({ shift: true });
    expect(skip).toHaveFocus();
  });

  it('spotlights the first visible target and scrolls it to the centre', async () => {
    target('sunday', false); // hidden first: skipped
    const shown = target('sunday', true);
    const scroll = vi.spyOn(shown, 'scrollIntoView');
    renderWithProviders(<TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />);
    expect(await screen.findByTestId('tour-ring')).toHaveStyle({ width: '208px', height: '108px' });
    expect(scroll).toHaveBeenCalledWith({ block: 'center', behavior: 'smooth' });
  });

  it('centres a step whose target is missing, with no ring', async () => {
    renderWithProviders(<TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />);
    await act(async () => new Promise((resolve) => requestAnimationFrame(resolve)));
    expect(screen.queryByTestId('tour-ring')).not.toBeInTheDocument();
    expect(screen.getByRole('dialog')).toHaveClass('-translate-x-1/2');
  });

  it('under reduced motion scrolls instantly and has no transition', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          addEventListener: () => undefined,
          removeEventListener: () => undefined,
        }) as unknown as MediaQueryList,
    );
    const shown = target('sunday', true);
    const scroll = vi.spyOn(shown, 'scrollIntoView');
    renderWithProviders(<TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />);
    const ring = await screen.findByTestId('tour-ring');
    expect(ring.className).not.toMatch(/transition/);
    expect(scroll).toHaveBeenCalledWith({ block: 'center', behavior: 'auto' });
  });

  it('makes the rest of the page inert while open', () => {
    const outside = document.createElement('div');
    document.body.appendChild(outside);
    const { unmount } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    expect(outside).toHaveAttribute('inert');
    unmount();
    expect(outside).not.toHaveAttribute('inert');
    outside.remove();
  });

  it('shows the admin preview badge in preview', async () => {
    renderWithProviders(<TourDialog steps={TOUR_STEPS} preview onClose={() => undefined} />, {
      role: 'admin',
    });
    expect(screen.getByText('Admin preview')).toBeInTheDocument();
  });
});
```

The preview badge inside the dialog is rendered directly (not through `AdminPreviewBadge`, which reads the switch) because the widget already knows `preview`; the text and hint are the same (`ADMIN_PREVIEW_HINT`).

Create `frontend/src/features/tour/homeWidget.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { HomePage } from '../home/pages/HomePage';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { homeWidget } from './homeWidget';
import { resetTourForTests, TOUR_KEY } from './state';

const tourOn = () =>
  server.use(
    http.get('*/api/features', () => HttpResponse.json({ switches: { tour_glossary: true } })),
  );

beforeEach(() => tourOn());
afterEach(() => resetTourForTests());

describe('tour home widget', () => {
  it('declares a hero widget before every other', () => {
    expect(homeWidget).toMatchObject({ id: 'tour', order: -10, slot: 'hero' });
  });

  it('opens on a first visit, and Done stores it and returns focus to the Home title', async () => {
    const { user } = renderWithProviders(<HomePage widgets={[homeWidget]} />);
    const dialog = await screen.findByRole('dialog', { name: 'The latest Sunday' }, { timeout: 3000 });
    expect(dialog).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Skip tour' }));
    expect(localStorage.getItem(TOUR_KEY)).toBe('done');
    expect(screen.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toHaveFocus();
    expect(screen.getByRole('heading', { level: 1 })).toHaveAttribute('tabindex', '-1');
  });

  it('stays closed once done, and adds no node to the hero slot', async () => {
    localStorage.setItem(TOUR_KEY, 'done');
    const { container } = renderWithProviders(<HomePage widgets={[homeWidget]} />);
    const bare = renderWithProviders(<HomePage widgets={[]} />);
    await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    // WidgetSlot adds no wrapper, so a closed tour widget leaves the page column unchanged.
    const column = (root: HTMLElement) => root.querySelector('h1')?.parentElement?.children.length;
    expect(column(container)).toBe(column(bare.container));
  });

  it('?tour=1 reopens it and removes only the tour parameter', async () => {
    localStorage.setItem(TOUR_KEY, 'done');
    const { router } = renderWithProviders(<HomePage widgets={[homeWidget]} />, {
      route: '/?w=3m&tour=1',
    });
    expect(await screen.findByRole('dialog', {}, { timeout: 3000 })).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search).toBe('?w=3m'));
  });

  it('never opens while the feature is off for a viewer', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    renderWithProviders(<HomePage widgets={[homeWidget]} />);
    await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('opens at once when the latest-Sunday card is already there', async () => {
    const marker = document.createElement('div');
    marker.dataset.tour = 'sunday';
    document.body.appendChild(marker);
    renderWithProviders(<HomePage widgets={[homeWidget]} />);
    expect(await screen.findByRole('dialog', {}, { timeout: 500 })).toBeInTheDocument();
    marker.remove();
  });
});
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/tour`
Expected: FAIL, unresolved `./TourDialog` and `./homeWidget`.

- [ ] **Step 7: Write the dialog, the widget and the Home edits**

In `frontend/src/components/ui/Sheet.tsx`, replace

```tsx
function trapTab(event: KeyboardEvent<HTMLDivElement>) {
```

with

```tsx
export function trapTab(event: KeyboardEvent<HTMLDivElement>) {
```

and replace

```tsx
function inertOthers(keep: Element | null): () => void {
```

with

```tsx
export function inertOthers(keep: Element | null): () => void {
```

Create `frontend/src/features/tour/TourDialog.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { ADMIN_PREVIEW_HINT } from '../../components/ui/AdminPreviewBadge';
import { cx } from '../../components/ui/cx';
import { inertOthers, trapTab } from '../../components/ui/Sheet';
import { useMediaQuery } from '../../lib/useMediaQuery';
import type { TourStep } from './steps';
import { firstVisible, PHONE_QUERY, REDUCED_MOTION_QUERY } from './target';

const RING_PAD = 4;
const BUTTON =
  'inline-flex min-h-11 min-w-11 items-center justify-center rounded-button px-4 text-sm';

/** The target's box, kept up to date on resize and scroll (rAF-throttled); null when missing. */
function useTargetBox(id: string, reduced: boolean): DOMRect | null {
  const [state, setState] = useState<{ id: string; box: DOMRect | null } | null>(null);
  useEffect(() => {
    const el = firstVisible(id);
    let frame = requestAnimationFrame(() => setState({ id, box: el?.getBoundingClientRect() ?? null }));
    if (el === null) return () => cancelAnimationFrame(frame);
    el.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setState({ id, box: el.getBoundingClientRect() }));
    };
    const observer = new ResizeObserver(update);
    observer.observe(el);
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [id, reduced]);
  return state?.id === id ? state.box : null;
}

export function TourDialog({
  steps,
  preview,
  onClose,
}: {
  steps: readonly TourStep[];
  preview: boolean;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const step = steps[index] as TourStep;
  const last = index === steps.length - 1;
  const reduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const phone = useMediaQuery(PHONE_QUERY);
  const box = useTargetBox(step.target, reduced);
  const titleId = useId();
  const bodyId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => inertOthers(rootRef.current), []);
  useEffect(() => titleRef.current?.focus(), [index]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
    } else if (event.key === 'Tab') {
      trapTab(event);
    }
  };

  const placement =
    phone ? 'inset-x-4 bottom-20' : box === null ? 'left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2' : '';
  const beside =
    !phone && box !== null
      ? {
          left: Math.max(16, Math.min(box.right + 16, window.innerWidth - 376)),
          top: Math.max(16, Math.min(box.top, window.innerHeight - 280)),
        }
      : undefined;

  return createPortal(
    <div ref={rootRef}>
      <div aria-hidden="true" className="fixed inset-0 z-40 bg-black/60" />
      {box !== null && (
        <div
          aria-hidden="true"
          data-testid="tour-ring"
          className={cx(
            'pointer-events-none fixed z-40 rounded-card border-[3px] border-accent',
            !reduced && 'transition-all duration-200',
          )}
          style={{
            top: box.top - RING_PAD,
            left: box.left - RING_PAD,
            width: box.width + 2 * RING_PAD,
            height: box.height + 2 * RING_PAD,
          }}
        />
      )}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        onKeyDown={onKeyDown}
        style={beside}
        className={cx(
          'fixed z-50 flex flex-col gap-3 rounded-card bg-elevated p-4 text-text shadow-xl sm:w-[360px]',
          placement,
        )}
      >
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h2 id={titleId} ref={titleRef} tabIndex={-1} className="text-base font-medium focus:outline-none">
            {step.title}
          </h2>
          {preview && (
            <span
              title={ADMIN_PREVIEW_HINT}
              aria-description={ADMIN_PREVIEW_HINT}
              className="rounded-button border border-accent px-2 py-0.5 text-xs font-medium text-accent"
            >
              Admin preview
            </span>
          )}
        </header>
        <p id={bodyId} className="text-sm text-text-muted">
          {step.body}
        </p>
        <p className="text-xs text-text-muted">{`Step ${String(index + 1)} of ${String(steps.length)}`}</p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button type="button" onClick={onClose} className={cx(BUTTON, 'text-text-muted underline')}>
            Skip tour
          </button>
          <div className="flex gap-2">
            {index > 0 && (
              <button
                type="button"
                onClick={() => setIndex(index - 1)}
                className={cx(BUTTON, 'border border-outline-variant')}
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={() => (last ? onClose() : setIndex(index + 1))}
              className={cx(BUTTON, 'bg-primary text-text')}
            >
              {last ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
```

"Skip tour" is first in DOM order and Next/Done last, so `trapTab` wraps Tab from Next/Done to Skip tour and Shift+Tab from Skip tour to Next/Done. Append this case to the `describe` in `TourDialog.test.tsx` (it fails if the trap is removed: Tab would leave the dialog):

```tsx
  it('wraps Tab from the last control to the first', async () => {
    const { user } = renderWithProviders(
      <TourDialog steps={TOUR_STEPS} preview={false} onClose={() => undefined} />,
    );
    screen.getByRole('button', { name: 'Next' }).focus();
    await user.tab();
    expect(screen.getByRole('button', { name: 'Skip tour' })).toHaveFocus();
  });
```

Create `frontend/src/features/tour/homeWidget.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useFeature } from '../../lib/features';
import type { HomeWidget } from '../home/widgets';
import { markTourDone, useTourDone } from './state';
import { TOUR_STEPS } from './steps';
import { TourDialog } from './TourDialog';

/** The Home h1 (Plan 19 §3.2.1: focus returns here when the tour closes). */
export const HOME_TITLE_ID = 'home-title';
/** Open once the latest-Sunday card is in the DOM, or after this long at most. */
const READY_WAIT_MS = 1500;
const POLL_MS = 100;

/** Renders nothing until it opens the tour; never a visible card (no hero-slot node). */
function TourWidget() {
  const { visible, preview } = useFeature('tour_glossary');
  const [params, setParams] = useSearchParams();
  const asked = params.get('tour') === '1';
  const done = useTourDone();
  const [open, setOpen] = useState(false);
  const wanted = visible && !open && (asked || !done);

  useEffect(() => {
    if (!wanted) return undefined;
    const started = Date.now();
    const timer = window.setInterval(() => {
      const ready = document.querySelector('[data-tour="sunday"]') !== null;
      if (!ready && Date.now() - started < READY_WAIT_MS) return;
      window.clearInterval(timer);
      setOpen(true);
      if (asked) {
        setParams(
          (previous) => {
            const next = new URLSearchParams(previous);
            next.delete('tour');
            return next;
          },
          { replace: true }, // a reload does not reopen it
        );
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [wanted, asked, setParams]);

  if (!open) return null;
  const close = () => {
    markTourDone();
    setOpen(false);
    document.getElementById(HOME_TITLE_ID)?.focus();
  };
  return <TourDialog steps={TOUR_STEPS} preview={preview} onClose={close} />;
}

export const homeWidget: HomeWidget = { id: 'tour', order: -10, slot: 'hero', Component: TourWidget };
```

`setParams(..., { replace: true })` is React Router's navigation, which calls `history.replaceState` (§3.2.1) and keeps the router's own location in step.

In `frontend/src/features/home/pages/HomePage.tsx`, replace

```tsx
      <h1 className="text-2xl font-medium">Sunday Clays</h1>
```

with

```tsx
      {/* tabIndex -1: the tour returns focus here without adding a Tab stop (Plan 19). */}
      <h1 id="home-title" tabIndex={-1} className="text-2xl font-medium focus:outline-none">
        Sunday Clays
      </h1>
```

and replace

```tsx
        <aside ref={personal} aria-label="Personal" className="flex min-w-0 flex-col gap-4">
```

with

```tsx
        <aside
          ref={personal}
          aria-label="Personal"
          data-tour="you"
          className="flex min-w-0 flex-col gap-4"
        >
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/tour src/features/home src/components/ui/Sheet.test.tsx`
Expected: PASS.

- [ ] **Step 9: Write the failing `data-tour` tests**

In `frontend/src/components/ui/Card.test.tsx`, add at the end:

```tsx
describe('Card tour target', () => {
  it('renders data-tour only when given', () => {
    const { container, rerender } = render(<Card title="x" tour="sunday" />);
    expect(container.querySelector('section')).toHaveAttribute('data-tour', 'sunday');
    rerender(<Card title="x" />);
    expect(container.querySelector('section')).not.toHaveAttribute('data-tour');
  });
});
```

(`Card.test.tsx` already imports `render` from Testing Library and `Card`; if it imports only `renderWithProviders`, use that.)

In `frontend/src/components/layout/nav.test.ts`, the NavList is not tested there; add to `frontend/src/components/layout/AppShell.test.tsx` at the end:

```tsx
describe('AppShell tour targets', () => {
  it('puts a nav item tourId on its link as data-tour', () => {
    stubViewport('desktop');
    renderShell('/', {
      items: [...ITEMS, { label: 'Trophies', path: '/trophies', icon: Trophy, order: 70, tourId: 'trophies' }],
    });
    expect(screen.getByRole('link', { name: 'Trophies' })).toHaveAttribute('data-tour', 'trophies');
    expect(screen.getByRole('link', { name: 'Explorer' })).not.toHaveAttribute('data-tour');
  });
});
```

In `frontend/src/features/home/pages/HomePage.test.tsx`, add at the end:

```tsx
describe('HomePage tour targets', () => {
  it('marks the latest Sunday card and the Personal panel', async () => {
    const { container } = renderWithProviders(<HomePage widgets={[]} />);
    expect(container.querySelector('aside[data-tour="you"]')).not.toBeNull();
    await screen.findByRole('heading', { name: 'Latest Sunday' });
    expect(container.querySelector('section[data-tour="sunday"]')).not.toBeNull();
  });
});
```

- [ ] **Step 10: Run them to verify they fail, then add the attributes**

Run: `cd frontend && pnpm exec vitest run src/components/ui/Card.test.tsx src/components/layout/AppShell.test.tsx src/features/home/pages/HomePage.test.tsx`
Expected: FAIL on the three new tests.

In `frontend/src/components/ui/Card.tsx`, replace

```tsx
  className?: string;
  children?: ReactNode;
}
```

with

```tsx
  className?: string;
  children?: ReactNode;
  /** Plan 19 tour: the step this card is the spotlight target of (`data-tour`). */
  tour?: string;
}
```

replace

```tsx
export function Card({ id, title, subtitle, actions, className, children }: CardProps) {
```

with

```tsx
export function Card({ id, title, subtitle, actions, className, children, tour }: CardProps) {
```

and replace

```tsx
      aria-labelledby={title === undefined ? undefined : titleId}
```

with

```tsx
      aria-labelledby={title === undefined ? undefined : titleId}
      data-tour={tour}
```

In `frontend/src/app/registry.ts`, replace

```ts
  /** Plan 19 D21: hidden unless this launch switch's feature is visible to the viewer. */
  feature?: FeatureKey;
}
```

with

```ts
  /** Plan 19 D21: hidden unless this launch switch's feature is visible to the viewer. */
  feature?: FeatureKey;
  /** Plan 19 tour: rendered as `data-tour` on the nav link (the "trophies" step). */
  tourId?: string;
}
```

In `frontend/src/components/layout/NavList.tsx`, replace

```tsx
  item: { path, label, icon: Icon },
```

with

```tsx
  item: { path, label, icon: Icon, tourId },
```

and replace

```tsx
      end={path === '/'}
```

with

```tsx
      end={path === '/'}
      data-tour={tourId}
```

In `frontend/src/features/home/components/LatestEventCard.tsx`, replace

```tsx
    <Card title="Latest Sunday" subtitle="Not affected by the time filter">
```

with

```tsx
    <Card title="Latest Sunday" subtitle="Not affected by the time filter" tour="sunday">
```

In `frontend/src/features/insights/components/FeedSections.tsx`, replace

```tsx
        <Card
          title="Insights"
```

with

```tsx
        <Card
          tour="insights"
          title="Insights"
```

In `frontend/src/features/achievements/NextTrophy.tsx`, replace

```tsx
    <section aria-label="Your next trophy" className="flex flex-col gap-3">
```

with

```tsx
    <section aria-label="Your next trophy" data-tour="trophies" className="flex flex-col gap-3">
```

In `frontend/src/features/achievements/routes.tsx`, replace

```tsx
  { label: 'Trophies', path: '/achievements', icon: Trophy, order: 70 },
```

with

```tsx
  { label: 'Trophies', path: '/achievements', icon: Trophy, order: 70, tourId: 'trophies' },
```

In `frontend/src/components/layout/TimeWindowFilter.tsx`, replace

```tsx
      <span className="inline-flex shrink-0">
```

with

```tsx
      <span data-tour="window" className="inline-flex shrink-0">
```

and replace

```tsx
    <div role="group" aria-label="Time window" className="flex flex-wrap items-center gap-1">
```

with

```tsx
    <div
      role="group"
      aria-label="Time window"
      data-tour="window"
      className="flex flex-wrap items-center gap-1"
    >
```

Run the three test files again. Expected: PASS.

- [ ] **Step 11: Write the failing glossary page and link tests**

Create `frontend/src/features/glossary/pages/GlossaryPage.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { GLOSSARY_TERMS } from '../terms';
import { routes } from '../routes';

const on = () =>
  server.use(
    http.get('*/api/features', () => HttpResponse.json({ switches: { tour_glossary: true } })),
  );

function renderAt(route: string, role: 'viewer' | 'admin' = 'viewer') {
  return renderRoutes(
    [{ path: '/', HydrateFallback: () => null, children: [...routes, { index: true, element: <p>home</p> }] }],
    { route, role },
  );
}

describe('GlossaryPage', () => {
  beforeEach(() => on());

  it('lists every term in order with its anchor', async () => {
    renderAt('/glossary');
    expect(await screen.findByRole('heading', { level: 1, name: 'Glossary' })).toBeInTheDocument();
    expect(screen.getByText('The words Sunday Clays uses, in plain English.')).toBeInTheDocument();
    const terms = screen.getAllByRole('term');
    expect(terms.map((t) => t.id)).toEqual(GLOSSARY_TERMS.map((t) => t.id));
    expect(terms[0]).toHaveTextContent('Clays thrown and broken');
  });

  it('scrolls to and highlights the hash term for 2 s', async () => {
    const scroll = vi.spyOn(Element.prototype, 'scrollIntoView');
    renderAt('/glossary#percentile');
    const term = await screen.findByText('Percentile', { selector: 'dt' });
    await vi.waitFor(() => expect(term).toHaveClass('bg-elevated'));
    expect(scroll).toHaveBeenCalled();
    await vi.waitFor(() => expect(term).not.toHaveClass('bg-elevated'), { timeout: 3000 });
  });

  it('"Take the tour again" goes to /?tour=1', async () => {
    const { user, router } = renderAt('/glossary');
    await user.click(await screen.findByRole('button', { name: 'Take the tour again' }));
    expect(router.state.location.pathname + router.state.location.search).toBe('/?tour=1');
  });

  it('is "Page not found" for a viewer while the switch is off, with the badge for an admin', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    const viewer = renderAt('/glossary');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    viewer.unmount();
    renderAt('/glossary', 'admin');
    expect(await screen.findByText('Admin preview')).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/glossary/routes.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('glossary routes', () => {
  it('adds a gated Glossary nav item at 135 and no header filters', () => {
    expect(nav.map(({ label, path, order, feature }) => ({ label, path, order, feature }))).toEqual([
      { label: 'Glossary', path: '/glossary', order: 135, feature: 'tour_glossary' },
    ]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });
});
```

Create `frontend/src/components/ui/WordsUsedHere.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { ExplainerPanel } from './Explainer';

const explainer = {
  what: 'Shows things.',
  computed: ['Field-adjusted score is used.'],
  terms: ['field-adjusted', 'percentile'] as const,
};

describe('Words used here', () => {
  it('links each term to its glossary anchor while the glossary is visible', async () => {
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: { tour_glossary: true } })),
    );
    renderWithProviders(<ExplainerPanel id="x" explainer={explainer} />);
    const link = await screen.findByRole('link', { name: 'Field-adjusted score' });
    expect(link).toHaveAttribute('href', '/glossary#field-adjusted');
    expect(link).toHaveClass('min-h-11');
    expect(screen.getByRole('link', { name: 'Percentile' })).toHaveAttribute(
      'href',
      '/glossary#percentile',
    );
    expect(screen.getByText('Words used here:')).toBeInTheDocument();
  });

  it('is hidden while the glossary is off for a viewer', async () => {
    renderWithProviders(<ExplainerPanel id="x" explainer={explainer} />); // default: off
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByText('Words used here:')).not.toBeInTheDocument();
  });

  it('renders nothing for an explainer without terms (no query either)', () => {
    renderWithProviders(<ExplainerPanel id="x" explainer={{ what: 'a', computed: ['b'] }} />);
    expect(screen.queryByText('Words used here:')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 12: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/glossary src/components/ui/WordsUsedHere.test.tsx`
Expected: FAIL: unresolved `../routes` and no "Words used here:".

- [ ] **Step 13: Write the glossary page, its route and the links**

Create `frontend/src/features/glossary/pages/GlossaryPage.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Button } from '../../../components/ui/Button';
import { cx } from '../../../components/ui/cx';
import { useMediaQuery } from '../../../lib/useMediaQuery';
import { REDUCED_MOTION_QUERY } from '../../tour/target';
import { GLOSSARY_TERMS } from '../terms';

const HIGHLIGHT_MS = 2000;

/** The term named by the URL hash, highlighted for 2 s after scrolling to it. */
function useHashHighlight(): string | null {
  const { hash } = useLocation();
  const reduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  useEffect(() => {
    const id = decodeURIComponent(hash.slice(1));
    const el = id === '' ? null : document.getElementById(id);
    if (el === null) return undefined;
    el.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
    const show = requestAnimationFrame(() => setHighlighted(id));
    const hide = window.setTimeout(() => setHighlighted(null), HIGHLIGHT_MS);
    return () => {
      cancelAnimationFrame(show);
      window.clearTimeout(hide);
    };
  }, [hash, reduced]);
  return highlighted;
}

export function GlossaryPage() {
  const highlighted = useHashHighlight();
  const reduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const navigate = useNavigate();
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-medium">Glossary</h1>
          <AdminPreviewBadge feature="tour_glossary" />
        </div>
        <p className="text-text-muted">The words Sunday Clays uses, in plain English.</p>
      </header>
      <dl className="flex flex-col gap-1 rounded-card bg-surface">
        {GLOSSARY_TERMS.map(({ id, term, definition }) => (
          <div key={id} className="flex flex-col gap-1 p-3">
            <dt
              id={id}
              className={cx(
                'scroll-mt-28 rounded-button px-1 font-medium',
                highlighted === id && 'bg-elevated',
                !reduced && 'transition-colors duration-500',
              )}
            >
              {term}
            </dt>
            <dd className="px-1 text-sm text-text-muted">{definition}</dd>
          </div>
        ))}
      </dl>
      <Button variant="tonal" className="self-start" onClick={() => void navigate('/?tour=1')}>
        Take the tour again
      </Button>
    </div>
  );
}
```

Check `frontend/src/components/ui/Button.tsx`'s props: it takes `variant` (`'tonal'` exists: `WidenWindowButtons` uses it) and passes other button props through; if it has no `className` prop, wrap the button in `<div className="self-start">` instead.

Create `frontend/src/features/glossary/routes.tsx`:

```tsx
import { BookOpen } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { FeatureGate } from '../../components/FeatureGate';
import { NO_FILTERS } from '../../lib/pageFilters';

export const routes: RouteObject[] = [
  {
    path: '/glossary',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { GlossaryPage } = await import('./pages/GlossaryPage');
      return {
        element: (
          <FeatureGate feature="tour_glossary">
            <GlossaryPage />
          </FeatureGate>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Glossary', path: '/glossary', icon: BookOpen, order: 135, feature: 'tour_glossary' },
];
```

Create `frontend/src/features/glossary/mocks.ts`:

```ts
import type { RequestHandler } from 'msw';

/** The glossary is static content: nothing to mock. */
export const handlers: RequestHandler[] = [];
```

In `frontend/src/app/navRegistry.test.ts`, replace

```ts
  race: 130,
  about: 140,
```

with

```ts
  race: 130,
  glossary: 135,
  about: 140,
```

Create `frontend/src/components/ui/WordsUsedHere.tsx`:

```tsx
import { Fragment } from 'react';
import { Link } from 'react-router';
import { termById, type GlossaryTermId } from '../../features/glossary/terms';
import { useFeature } from '../../lib/features';

/** "Words used here:" links to the glossary (Plan 19 §3.2.2), while the glossary is visible. */
export function WordsUsedHere({ terms }: { terms: readonly GlossaryTermId[] }) {
  const { visible } = useFeature('tour_glossary');
  if (!visible) return null;
  return (
    <p className="flex flex-wrap items-center gap-x-1 text-sm text-text-muted">
      <span>Words used here:</span>
      {terms.map((id, index) => (
        <Fragment key={id}>
          {index > 0 && <span aria-hidden="true">·</span>}
          <Link to={`/glossary#${id}`} className="inline-flex min-h-11 items-center underline">
            {termById(id).term}
          </Link>
        </Fragment>
      ))}
    </p>
  );
}
```

In `frontend/src/components/ui/Explainer.tsx`, replace

```tsx
import { CardHeadingLevel } from './Card';
import { cx } from './cx';
```

with

```tsx
import { CardHeadingLevel } from './Card';
import { cx } from './cx';
import { WordsUsedHere } from './WordsUsedHere';
```

and replace

```tsx
      <Part title="How it's worked out" level={level}>
        <Bullets items={explainer.computed} />
      </Part>
    </div>
```

with

```tsx
      <Part title="How it's worked out" level={level}>
        <Bullets items={explainer.computed} />
      </Part>
      {explainer.terms !== undefined && explainer.terms.length > 0 && (
        <WordsUsedHere terms={explainer.terms} />
      )}
    </div>
```

- [ ] **Step 14: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/glossary src/components/ui src/app/navRegistry.test.ts`
Expected: PASS.

- [ ] **Step 15: Write the failing trigger lint, then add the missing terms**

Create `frontend/src/features/glossary/triggers.ts`:

```ts
import type { Explainer } from '../../components/charts/types';
import type { GlossaryTermId } from './terms';

/**
 * Words that mean an explainer uses a glossary term (Plan 19 §3.2.2). The lint requires the term id
 * in `terms` whenever the explainer's text matches.
 */
export const GLOSSARY_TRIGGERS: Record<GlossaryTermId, RegExp> = {
  'clays-thrown': /\bclays thrown\b/i,
  difficulty: /\bdifficult/i,
  'field-adjusted': /\b(field-)?adjusted\b/i,
  'field-median': /\bfield median\b/i,
  'first-timer': /\bfirst[- ]timers?\b/i,
  'fist-bump': /\bfist bumps?\b/i,
  'held-sunday': /full results/i,
  percentile: /\bpercentiles?\b/i,
  'personal-best': /\bpersonal best|\bPB\b/,
  rarity: /\brarity\b|\brare\b/i,
  'round-types': /\bsuper sporting\b|\bround type/i,
  'special-shoot': /\bspecial shoot/i,
  streak: /\bstreak/i,
  'time-window': /\btime window\b/i,
  'trophy-tiers': /\b(bronze|silver|platinum|diamond)\b/i,
};

/** Term ids whose trigger matches the explainer's text but which its `terms` does not list. */
export function missingTerms(explainer: Explainer): GlossaryTermId[] {
  const text = [explainer.what, ...(explainer.read ?? []), ...explainer.computed].join(' ');
  const listed = new Set(explainer.terms ?? []);
  return (Object.entries(GLOSSARY_TRIGGERS) as [GlossaryTermId, RegExp][])
    .filter(([id, trigger]) => trigger.test(text) && !listed.has(id))
    .map(([id]) => id);
}
```

Create `frontend/src/features/glossary/explainerLint.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { Explainer } from '../../components/charts/types';
import { missingTerms } from './triggers';

const modules = import.meta.glob<Record<string, unknown>>('../*/explainers.ts', { eager: true });

function isExplainer(value: unknown): value is Explainer {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Explainer).what === 'string' &&
    Array.isArray((value as Explainer).computed)
  );
}

/** Every static explainer exported by a feature: an Explainer export, or a record of them. */
function allExplainers(): [string, Explainer][] {
  const found: [string, Explainer][] = [];
  for (const [file, exports] of Object.entries(modules)) {
    for (const [name, value] of Object.entries(exports)) {
      if (isExplainer(value)) found.push([`${file} ${name}`, value]);
      else if (typeof value === 'object' && value !== null) {
        for (const [key, entry] of Object.entries(value)) {
          if (isExplainer(entry)) found.push([`${file} ${name}.${key}`, entry]);
        }
      }
    }
  }
  return found;
}

describe('glossary trigger lint', () => {
  it('walks a real set of explainers', () => {
    expect(allExplainers().length).toBeGreaterThan(40);
  });

  it('flags a trigger without its term, and passes once the term is listed', () => {
    const bare: Explainer = { what: 'Your percentile on the day.', computed: ['x'] };
    expect(missingTerms(bare)).toEqual(['percentile']);
    expect(missingTerms({ ...bare, terms: ['percentile'] })).toEqual([]);
  });

  it('every explainer lists the glossary terms its text uses', () => {
    const problems = allExplainers().flatMap(([name, explainer]) =>
      missingTerms(explainer).map((id) => `${name}: add '${id}' to terms`),
    );
    expect(problems).toEqual([]);
  });
});
```

Run: `cd frontend && pnpm exec vitest run src/features/glossary/explainerLint.test.ts`
Expected: FAIL. The last test prints every `<file> <export>.<key>: add '<id>' to terms` line; paste the list as RED. (At the plan's base, matches exist in at least these files: `club`, `events`, `explorer`, `home`, `leaderboards`, `records`, `shooters`, `stations`, `race`, `weather`, `yir`, `predictions`, `achievements`, `admin-analytics`.)

Now edit each named explainer entry: add a `terms` array listing exactly the ids the lint names for that entry, in the order of `GLOSSARY_TRIGGERS`, for example

```ts
  'adj-trend': {
    what: '…',
    computed: ['…'],
    scope: 'windowed',
    terms: ['field-adjusted', 'time-window'],
  },
```

Change no copy. If an explainer file's type annotation does not accept `terms` (for example a local interface instead of `Explainer`), widen it to `Explainer`. Re-run until the list is empty.

Expected after the edits: PASS (3 passed), and `pnpm exec vitest run src/features` still passes (no explainer test asserts the absence of a `terms` key; if one compares an entry with `toEqual`, add the `terms` there too).

Pin the new page's page-view kind (and the recap's, which no other task tests) in `frontend/src/features/pageviews/pageKind.test.ts`: replace

```ts
    ['/admin/analytics', 'admin'],
```

with

```ts
    ['/admin/analytics', 'admin'],
    ['/admin/recap', 'admin'], // Plan 19 T8's page
    ['/glossary', 'other'], // Plan 19: no kind of its own
```

Run: `cd frontend && pnpm exec vitest run src/features/pageviews/pageKind.test.ts`
Expected: PASS (pins today's `pageKind`; no production change).

- [ ] **Step 16: Add `tourSeen` to the e2e fixtures and write the e2e**

Replace the whole of `frontend/e2e/fixtures.ts` with:

```ts
import { expect, test as base } from '@playwright/test';

/**
 * Shared `test`/`expect` for every spec (C10): a test fails if the page throws an uncaught
 * error or the browser reports a Content Security Policy violation.
 *
 * Plan 19: `tourSeen` (default true) marks the first-visit tour as done before every page load,
 * so specs never meet the tour; the tour spec sets it false.
 */
export const test = base.extend<{ pageProblems: string[]; tourSeen: boolean; seenFlags: void }>({
  tourSeen: [true, { option: true }],
  seenFlags: [
    async ({ page, tourSeen }, use) => {
      if (tourSeen) {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('sc.tour.v1', 'done');
          } catch {
            // storage blocked: the spec meets the tour, as a real visitor would
          }
        });
      }
      await use();
    },
    { auto: true },
  ],
  pageProblems: [
    async ({ page }, use) => {
      const problems: string[] = [];
      page.on('pageerror', (error) => problems.push(`pageerror: ${error.message}`));
      page.on('console', (message) => {
        if (/Content Security Policy/i.test(message.text())) {
          problems.push(`csp: ${message.text()}`);
        }
      });
      await use(problems);
      expect(problems, 'uncaught page errors and CSP violations').toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
```

Create `frontend/e2e/tour.spec.ts`:

```ts
import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

test.use({ tourSeen: false });

const TITLES = [
  'The latest Sunday',
  'Which one are you?',
  'Insights and fist bumps',
  'Trophies',
  'Time window',
];

const dialog = (page: Page) => page.getByRole('dialog');

test('a first visit walks the five steps, then never again', async ({ page }) => {
  await page.goto('/');
  await expect(dialog(page)).toHaveAccessibleName(TITLES[0] as string, { timeout: 10_000 });
  await expect(page.getByText('Step 1 of 5')).toBeVisible();
  for (const title of TITLES.slice(1)) {
    await page.getByRole('button', { name: 'Next' }).click();
    await expect(dialog(page)).toHaveAccessibleName(title);
  }
  await page.getByRole('button', { name: 'Done' }).click();
  await expect(dialog(page)).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeFocused();
  await page.reload();
  await page.waitForTimeout(2000);
  await expect(dialog(page)).toHaveCount(0);
});

test('?tour=1 reopens it, drops the parameter, and Esc closes it', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('sc.tour.v1', 'done'));
  await page.goto('/?tour=1');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  await expect(page).not.toHaveURL(/tour=1/);
  await page.keyboard.press('Escape');
  await expect(dialog(page)).toHaveCount(0);
});

test('keyboard: Tab stays inside the dialog', async ({ page }) => {
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  for (let i = 0; i < 6; i += 1) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    );
    expect(inside, `Tab ${String(i + 1)}`).toBe(true);
  }
});

test('reduced motion still shows every step', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(dialog(page)).toHaveAccessibleName(TITLES[1] as string);
});

test('at phone width the dialog docks to the bottom with 44 px controls', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'phone layout only');
  await page.goto('/');
  await expect(dialog(page)).toBeVisible({ timeout: 10_000 });
  const box = await dialog(page).boundingBox();
  const viewport = page.viewportSize();
  expect(box !== null && viewport !== null && box.y + box.height > viewport.height * 0.6).toBe(true);
  for (const name of ['Next', 'Skip tour']) {
    const button = await page.getByRole('button', { name }).boundingBox();
    expect(button?.height ?? 0, name).toBeGreaterThanOrEqual(44);
  }
  await expectNoSideScroll(page);
});
```

Create `frontend/e2e/glossary.spec.ts`:

```ts
import { expect, test } from './fixtures';

test('a hash link scrolls to its term', async ({ page }) => {
  await page.goto('/glossary#percentile');
  await expect(page.getByRole('heading', { level: 1, name: 'Glossary' })).toBeVisible();
  await expect(page.locator('dt#percentile')).toBeInViewport();
});

test('an explainer on a profile links to the glossary', async ({ page }) => {
  await page.goto('/shooters/3');
  const about = page.getByRole('button', { name: 'About this chart' }).first();
  await about.click();
  const words = page.getByText('Words used here:').first();
  await expect(words).toBeVisible();
  const link = words.locator('xpath=..').getByRole('link').first();
  const href = (await link.getAttribute('href')) ?? '';
  expect(href).toMatch(/^\/glossary#[a-z-]+$/);
  await link.click();
  await expect(page.getByRole('heading', { level: 1, name: 'Glossary' })).toBeVisible();
  const url = new URL(page.url());
  expect(url.pathname + url.hash).toBe(href);
});

test('the nav lists Glossary', async ({ page, isMobile }) => {
  await page.goto('/');
  if (isMobile) await page.getByRole('button', { name: 'More' }).click();
  await expect(page.getByRole('link', { name: 'Glossary' })).toBeVisible();
});
```

- [ ] **Step 17: Run the e2e at both sizes**

Rebuild the stack (project `task19-5`, port 18081) and run: `pnpm exec playwright test tour.spec.ts glossary.spec.ts home.spec.ts --project=desktop --project=mobile`.
Expected: PASS; `home.spec.ts` (unchanged) proves `tourSeen` keeps the tour out of existing specs. If the profile's first "About this chart" explainer has no terms, pick the first chart whose explainer the lint gave terms (see the Step 15 list) and use its `name`.

- [ ] **Step 18: Run the frontend gates, then commit**

Run the frontend gates. Expected: clean, coverage ≥ 90%.

```bash
git add frontend/src/features/tour frontend/src/features/glossary frontend/src/components/ui/WordsUsedHere.tsx \
  frontend/src/components/ui/WordsUsedHere.test.tsx frontend/src/components/ui/Explainer.tsx \
  frontend/src/components/ui/Sheet.tsx frontend/src/components/ui/Card.tsx frontend/src/components/ui/Card.test.tsx \
  frontend/src/app/registry.ts frontend/src/components/layout/NavList.tsx \
  frontend/src/components/layout/AppShell.test.tsx frontend/src/components/layout/TimeWindowFilter.tsx \
  frontend/src/features/home/pages/HomePage.tsx frontend/src/features/home/pages/HomePage.test.tsx \
  frontend/src/features/home/components/LatestEventCard.tsx frontend/src/features/insights/components/FeedSections.tsx \
  frontend/src/features/achievements/NextTrophy.tsx frontend/src/features/achievements/routes.tsx \
  frontend/src/app/navRegistry.test.ts frontend/src/features/pageviews/pageKind.test.ts \
  frontend/e2e/fixtures.ts frontend/e2e/tour.spec.ts frontend/e2e/glossary.spec.ts
git add $(git diff --name-only -- 'frontend/src/features/*/explainers.ts' 'frontend/src/features/*/explainers.test.ts')
git status --short frontend/src   # must list nothing modified or untracked: every Step 15 edit is staged
git commit -m "feat(tour): first-visit tour, glossary page and Words-used-here links (Plan 19 T5)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: Club milestones (`task/19-6-club-milestones`, wave 4)

**Files:**
- Create: `backend/src/sunday_clays/analytics/club_milestones.py`
- Modify: `backend/src/sunday_clays/api/routes/club.py` (models and one route)
- Create: `backend/tests/unit/analytics/test_club_milestones.py`
- Create: `backend/tests/integration/api/test_club_milestones_api.py`
- Create: `frontend/src/features/club/milestones.ts`, `frontend/src/features/club/milestones.test.ts`
- Create: `frontend/src/features/club/homeWidget.tsx`, `frontend/src/features/club/homeWidget.test.tsx`
- Create: `frontend/src/features/club/components/MilestonesSection.tsx`, `frontend/src/features/club/components/MilestonesSection.test.tsx`
- Modify: `frontend/src/features/club/api.ts`, `frontend/src/features/club/mocks.ts`, `frontend/src/features/club/explainers.ts`, `frontend/src/features/club/explainers.test.ts`, `frontend/src/features/club/pages/ClubPage.tsx`
- Create: `frontend/e2e/club-milestones.spec.ts`

**Interfaces:**
- Consumes: T1 `feature_gate("club_milestones")`; T2 `useFeature`, `AdminPreviewBadge`; T5 `Explainer.terms` lint (new entries must pass it); `frames.load_rounds`, `load_appearances`, `load_calendar`; `_filters.latest_scored_day`; `cached_by_data_version`; `ChartFrame`, `lineOption`, `Chip`, `AboutBlock`, `useTimeWindow`, `useUrlState`, `enumCodec`.
- Produces (T8 relies on `club_milestones`):
  - `analytics.club_milestones`: `Metric = Literal["sundays_held", "clays_thrown", "shooters", "rounds"]`, `METRICS` (that tie order), `THRESHOLDS: dict[Metric, tuple[int, ...]]`, `milestone_label(metric, threshold) -> str`, frozen dataclasses `Crossing(metric, threshold, event_date, label, first_on_record)`, `NextUp(metric, threshold, current, remaining, label)`, `TotalsRow(event_date, clays_thrown, sundays_held, shooters, rounds)`, `ClubMilestones(as_of, milestones: tuple[Crossing, ...], latest: Crossing | None, next: tuple[NextUp, ...], series: tuple[TotalsRow, ...])`; `compute_milestones(rounds, appearances, calendar, as_of: date) -> ClubMilestones` (pure); `club_milestones(session, as_of: date) -> ClubMilestones` (`@cached_by_data_version`).
  - `GET /api/club/milestones?as_of=` → `ClubMilestonesOut` (gated; `as_of` defaults to the latest scored Sunday).
  - Frontend: `useClubMilestones(enabled: boolean)`, `nextUp(next)`, `totalsModel(series, crossings, metric)`, the `club-milestone` home widget, `MilestonesSection`.

- [ ] **Step 1: Write the failing milestone rules tests**

Create `backend/tests/unit/analytics/test_club_milestones.py`:

```python
"""Club milestone rules (Plan 19 §3.5.1) on hand-built frames."""

from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import club_milestones as cm

D0 = date(2026, 1, 4)


def sunday(i: int) -> date:
    return D0 + timedelta(weeks=i)


def world(
    regular: dict[int, list[int]],
    special: dict[int, list[int]] | None = None,
    not_held: tuple[int, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """regular/special: Sunday index -> shooter ids with one round each that day."""
    special = special or {}
    rounds = pd.DataFrame(
        [(sunday(i), s) for i, ids in regular.items() for s in ids],
        columns=["event_date", "shooter_id"],
    )
    appearances = pd.DataFrame(
        [(sunday(i), s) for days in (regular, special) for i, ids in days.items() for s in ids],
        columns=["event_date", "shooter_id"],
    )
    days = sorted({*regular, *special})
    calendar = pd.DataFrame(
        [(sunday(i), i not in not_held) for i in days], columns=["event_date", "results_complete"]
    )
    return rounds, appearances, calendar


@pytest.fixture(autouse=True)
def small_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cm,
        "THRESHOLDS",
        {"sundays_held": (2, 3), "clays_thrown": (100, 200), "shooters": (2, 3), "rounds": (3, 5)},
    )


def test_labels() -> None:
    assert cm.milestone_label("clays_thrown", 350_000) == "350,000 clays thrown"
    assert cm.milestone_label("sundays_held", 300) == "300 Sundays held"
    assert cm.milestone_label("shooters", 250) == "250 different shooters"
    assert cm.milestone_label("rounds", 10_000) == "10,000 rounds shot"


def test_crossing_dates_series_and_next() -> None:
    result = cm.compute_milestones(*world({0: [1], 1: [1, 2], 2: [1, 2, 3]}), sunday(2))
    assert [(r.event_date, r.rounds, r.clays_thrown, r.shooters, r.sundays_held) for r in result.series] == [
        (sunday(0), 1, 50, 1, 1),
        (sunday(1), 3, 150, 2, 2),
        (sunday(2), 6, 300, 3, 3),
    ]
    crossed = {(c.metric, c.threshold): c.event_date for c in result.milestones}
    assert crossed == {
        ("sundays_held", 2): sunday(1),
        ("sundays_held", 3): sunday(2),
        ("clays_thrown", 100): sunday(1),
        ("clays_thrown", 200): sunday(2),
        ("shooters", 2): sunday(1),
        ("shooters", 3): sunday(2),
        ("rounds", 3): sunday(1),
        ("rounds", 5): sunday(2),
    }
    assert result.next == ()  # every metric is past the (patched) table


def test_newest_first_and_the_latest_tie_order() -> None:
    result = cm.compute_milestones(*world({0: [1], 1: [1, 2], 2: [1, 2, 3]}), sunday(2))
    assert [(c.metric, c.threshold) for c in result.milestones[:4]] == [
        ("sundays_held", 3),
        ("clays_thrown", 200),
        ("shooters", 3),
        ("rounds", 5),
    ]
    assert result.latest == result.milestones[0]


def test_a_partial_results_sunday_dates_its_own_crossing() -> None:
    # Sunday 1 has scores but results_complete is false: clays and rounds still cross there.
    result = cm.compute_milestones(*world({0: [1], 1: [1, 2], 2: [3]}, not_held=(1,)), sunday(2))
    crossed = {(c.metric, c.threshold): c.event_date for c in result.milestones}
    assert crossed[("rounds", 3)] == sunday(1)
    assert crossed[("sundays_held", 2)] == sunday(2)  # held Sundays skip the partial one


def test_special_rows_add_to_held_and_shooters_only() -> None:
    plain = cm.compute_milestones(*world({0: [1], 2: [1]}), sunday(2))
    with_special = cm.compute_milestones(*world({0: [1], 2: [1]}, special={1: [1, 2]}), sunday(2))
    last_plain, last_special = plain.series[-1], with_special.series[-1]
    assert last_special.clays_thrown == last_plain.clays_thrown == 100
    assert last_special.rounds == last_plain.rounds == 2
    assert last_special.sundays_held == last_plain.sundays_held + 1
    assert last_special.shooters == last_plain.shooters + 1


def test_first_on_record() -> None:
    result = cm.compute_milestones(*world({0: [1, 2, 3]}), sunday(0))
    flagged = {(c.metric, c.threshold) for c in result.milestones if c.first_on_record}
    assert ("shooters", 2) in flagged and ("rounds", 3) in flagged
    assert all(c.first_on_record for c in result.milestones)


def test_next_is_the_first_threshold_above_the_current_value() -> None:
    result = cm.compute_milestones(*world({0: [1]}), sunday(0))
    nexts = {n.metric: (n.threshold, n.current, n.remaining) for n in result.next}
    assert nexts == {
        "sundays_held": (2, 1, 1),
        "clays_thrown": (100, 50, 50),
        "shooters": (2, 1, 1),
        "rounds": (3, 1, 2),
    }


def test_a_value_equal_to_a_threshold_has_crossed_it() -> None:
    # Kills `>` in place of `>=`: exactly 100 clays crosses 100.
    result = cm.compute_milestones(*world({0: [1, 2]}), sunday(0))
    assert ("clays_thrown", 100) in {(c.metric, c.threshold) for c in result.milestones}


def test_nothing_on_or_before_as_of() -> None:
    result = cm.compute_milestones(*world({3: [1]}), sunday(1))
    assert result.milestones == () and result.latest is None and result.series == ()


def test_as_of_cuts_the_data_no_leak() -> None:
    frames = world({0: [1], 1: [1, 2], 2: [1, 2, 3], 3: [4]})
    full = cm.compute_milestones(*frames, sunday(3))
    for i in range(4):
        cut = cm.compute_milestones(*frames, sunday(i))
        assert list(cut.milestones) == [m for m in full.milestones if m.event_date <= sunday(i)]
        assert cut.series == full.series[: i + 1]
        for n in cut.next:
            assert n.current == getattr(full.series[i], n.metric)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/analytics/test_club_milestones.py`
Expected: FAIL, `ImportError: cannot import name 'club_milestones'`.

- [ ] **Step 3: Write the rules**

Create `backend/src/sunday_clays/analytics/club_milestones.py`:

```python
"""Club milestones (Plan 19 §3.5.1, D17): running club totals, dated at the Sunday each round
number was first reached. Computed on read from the cached frames."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

import pandas as pd
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import cached_by_data_version

Metric = Literal["sundays_held", "clays_thrown", "shooters", "rounds"]
#: Also the order of crossings that share a Sunday (§3.5.2).
METRICS: Final[tuple[Metric, ...]] = ("sundays_held", "clays_thrown", "shooters", "rounds")
THRESHOLDS: dict[Metric, tuple[int, ...]] = {
    "clays_thrown": (
        10_000, 25_000, 50_000, 100_000, 150_000, 200_000, 250_000, 300_000, 350_000,
        400_000, 450_000, 500_000, 600_000, 700_000, 800_000, 900_000, 1_000_000,
    ),
    "sundays_held": (25, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500),
    "shooters": (25, 50, 100, 150, 200, 250, 300, 400, 500),
    "rounds": (100, 500, 1_000, 2_500, 5_000, 7_500, 10_000, 12_500, 15_000, 20_000),
}
_UNITS: Final[dict[Metric, str]] = {
    "clays_thrown": "clays thrown",
    "sundays_held": "Sundays held",
    "shooters": "different shooters",
    "rounds": "rounds shot",
}


def milestone_label(metric: Metric, threshold: int) -> str:
    return f"{threshold:,} {_UNITS[metric]}"


@dataclass(frozen=True)
class Crossing:
    metric: Metric
    threshold: int
    event_date: date
    label: str
    first_on_record: bool


@dataclass(frozen=True)
class NextUp:
    metric: Metric
    threshold: int
    current: int
    remaining: int
    label: str


@dataclass(frozen=True)
class TotalsRow:
    event_date: date
    clays_thrown: int
    sundays_held: int
    shooters: int
    rounds: int


@dataclass(frozen=True)
class ClubMilestones:
    as_of: date
    milestones: tuple[Crossing, ...]
    latest: Crossing | None
    next: tuple[NextUp, ...]
    series: tuple[TotalsRow, ...]


def compute_milestones(
    rounds: pd.DataFrame, appearances: pd.DataFrame, calendar: pd.DataFrame, as_of: date
) -> ClubMilestones:
    """Evaluate every Sunday <= as_of with a regular round or an appearance (special included).

    Clays and rounds count regular rounds only (a partial-results Sunday included); Sundays held
    counts `results_complete` Sundays of both kinds; shooters counts distinct appearances.
    """
    regular = Counter(d for d in rounds["event_date"] if d <= as_of)
    seen_by_day: dict[date, set[int]] = defaultdict(set)
    for day, shooter in zip(appearances["event_date"], appearances["shooter_id"], strict=True):
        if day <= as_of:
            seen_by_day[day].add(int(shooter))
    held = {
        d
        for d, done in zip(calendar["event_date"], calendar["results_complete"], strict=True)
        if bool(done) and d <= as_of
    }
    days = sorted(set(regular) | set(seen_by_day))
    series: list[TotalsRow] = []
    seen: set[int] = set()
    n_rounds = n_held = 0
    for day in days:
        n_rounds += regular.get(day, 0)
        n_held += day in held
        seen |= seen_by_day.get(day, set())
        series.append(
            TotalsRow(day, frames.REGULAR_TARGETS * n_rounds, n_held, len(seen), n_rounds)
        )
    crossings: list[Crossing] = []
    for metric in METRICS:
        for threshold in THRESHOLDS[metric]:
            hit = next((row for row in series if getattr(row, metric) >= threshold), None)
            if hit is None:
                break
            crossings.append(
                Crossing(
                    metric,
                    threshold,
                    hit.event_date,
                    milestone_label(metric, threshold),
                    hit.event_date == days[0],
                )
            )
    order = {metric: i for i, metric in enumerate(METRICS)}
    crossings.sort(key=lambda c: (-c.event_date.toordinal(), order[c.metric], -c.threshold))
    last = series[-1] if series else None
    nexts: list[NextUp] = []
    for metric in METRICS:
        current = int(getattr(last, metric)) if last is not None else 0
        upcoming = next((t for t in THRESHOLDS[metric] if t > current), None)
        if upcoming is not None:
            nexts.append(
                NextUp(metric, upcoming, current, upcoming - current, milestone_label(metric, upcoming))
            )
    return ClubMilestones(
        as_of=as_of,
        milestones=tuple(crossings),
        latest=crossings[0] if crossings else None,
        next=tuple(nexts),
        series=tuple(series),
    )


@cached_by_data_version
def club_milestones(session: Session, as_of: date) -> ClubMilestones:
    return compute_milestones(
        frames.load_rounds(session),
        frames.load_appearances(session),
        frames.load_calendar(session),
        as_of,
    )
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/analytics/test_club_milestones.py`
Expected: PASS (11 passed).

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/integration/api/test_club_milestones_api.py`:

```python
"""GET /api/club/milestones (Plan 19 §3.5.2, §5.2)."""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics import frames
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch

SPECIAL = "2026-09-20"


def _on(session: Session) -> None:
    set_switch(session, get_settings(), "club_milestones", True)


def test_viewer_gets_404_while_off_and_admin_gets_200(
    fx_viewer_client: TestClient, fx_admin_client: TestClient
) -> None:
    assert fx_viewer_client.get("/api/club/milestones").json() == {"detail": "Not Found"}
    assert fx_admin_client.get("/api/club/milestones").status_code == 200


def test_as_of_defaults_to_the_latest_scored_sunday(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    body = fx_viewer_client.get("/api/club/milestones").json()
    latest = fx_session.execute(text("SELECT max(event_date) FROM events WHERE has_scores")).scalar()
    assert body["as_of"] == latest.isoformat()
    assert body["series"][-1]["event_date"] <= body["as_of"]
    assert {"milestones", "latest", "next", "series"} <= set(body)


def test_special_sunday_adds_held_and_shooters_not_clays(
    fx_special_viewer_client: TestClient, fx_special_session: Session
) -> None:
    _on(fx_special_session)
    series = {r["event_date"]: r for r in fx_special_viewer_client.get("/api/club/milestones").json()["series"]}
    before = series["2026-09-13"]
    special = series[SPECIAL]
    assert special["clays_thrown"] == before["clays_thrown"]
    assert special["rounds"] == before["rounds"]
    assert special["sundays_held"] == before["sundays_held"] + 1
    assert special["shooters"] == before["shooters"] + 1  # Kim, Pat is new


def test_fx_world_is_the_special_world_without_its_special_sunday(
    fx_viewer_client: TestClient,
    fx_session: Session,
    fx_special_viewer_client: TestClient,
    fx_special_session: Session,
) -> None:
    _on(fx_session)
    _on(fx_special_session)
    plain = {r["event_date"]: r for r in fx_viewer_client.get("/api/club/milestones").json()["series"]}
    clear_cache()
    special = {
        r["event_date"]: r
        for r in fx_special_viewer_client.get("/api/club/milestones").json()["series"]
    }
    assert SPECIAL not in plain
    for day, row in plain.items():
        if day < SPECIAL:
            assert special[day] == row, day
        else:
            assert special[day]["clays_thrown"] == row["clays_thrown"]
            assert special[day]["rounds"] == row["rounds"]


def test_no_leak_for_every_held_sunday(fx_session: Session) -> None:
    calendar = frames.load_calendar(fx_session)
    held = sorted(calendar.loc[calendar["results_complete"].astype(bool), "event_date"])
    full = cm.club_milestones(fx_session, held[-1])
    for day in held:
        cut = cm.club_milestones(fx_session, day)
        assert list(cut.milestones) == [m for m in full.milestones if m.event_date <= day]
        position = next(i for i, r in enumerate(full.series) if r.event_date == day)
        for n in cut.next:
            assert n.current == getattr(full.series[position], n.metric)


def test_as_of_before_the_first_sunday_is_empty(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    _on(fx_session)
    body = fx_viewer_client.get("/api/club/milestones", params={"as_of": "1990-01-07"}).json()
    assert body["milestones"] == [] and body["latest"] is None and body["series"] == []
    assert date.fromisoformat(body["as_of"]) == date(1990, 1, 7)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_club_milestones_api.py`
Expected: FAIL: the route answers the unknown-route 404 for the admin too (`test_viewer_gets_404_while_off_and_admin_gets_200` fails on the admin's 404), the others fail with `KeyError`.

- [ ] **Step 7: Write the route**

In `backend/src/sunday_clays/api/routes/club.py`, replace

```python
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from sunday_clays.analytics import frames
from sunday_clays.analytics.cohorts import cohort_tables, first_round_scores
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
from sunday_clays.api.routes._filters import check_window, in_window, round_type_param
from sunday_clays.db import SessionDep
from sunday_clays.domain.round_type import RoundType
```

with

```python
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from sunday_clays.analytics import frames
from sunday_clays.analytics.club_milestones import Metric, club_milestones
from sunday_clays.analytics.cohorts import cohort_tables, first_round_scores
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
from sunday_clays.api.routes._features import feature_gate
from sunday_clays.api.routes._filters import (
    check_window,
    in_window,
    latest_scored_day,
    round_type_param,
)
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.round_type import RoundType
```

and append at the end of the file:

```python
class MilestoneOut(BaseModel):
    metric: Metric
    threshold: int
    event_date: date
    label: str
    first_on_record: bool


class NextMilestoneOut(BaseModel):
    metric: Metric
    threshold: int
    current: int
    remaining: int
    label: str


class ClubTotalsOut(BaseModel):
    event_date: date
    clays_thrown: int
    sundays_held: int
    shooters: int
    rounds: int


class ClubMilestonesOut(BaseModel):
    as_of: date
    milestones: list[MilestoneOut]  # newest first
    latest: MilestoneOut | None
    next: list[NextMilestoneOut]  # one per metric not yet past its table
    series: list[ClubTotalsOut]  # one row per evaluation Sunday <= as_of


@router.get("/api/club/milestones", dependencies=[feature_gate("club_milestones")])
def get_club_milestones(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    as_of: date | None = None,
) -> ClubMilestonesOut:
    """Plan 19 §3.5: club round numbers, dated at the Sunday each was first reached. Ignores the
    round-type filter; `as_of` defaults to the latest scored Sunday."""
    result = club_milestones(session, as_of or latest_scored_day(session, settings.timezone))
    return ClubMilestonesOut.model_validate(result, from_attributes=True)
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_club_milestones_api.py tests/integration/api/test_route_auth_matrix.py`
Expected: PASS.

- [ ] **Step 9: Write the failing frontend model and widget tests**

Run `cd frontend && pnpm gen:api` first (the new schema types).

Create `frontend/src/features/club/milestones.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { clubMilestones } from './mocks';
import { metricOf, nextUp, totalsModel } from './milestones';

describe('club milestone models', () => {
  it('picks the next milestone with the smallest share still to go', () => {
    expect(nextUp(clubMilestones.next)?.label).toBe('400,000 clays thrown');
    expect(nextUp([])).toBeNull();
  });

  it('builds a table of every metric and a line of the chosen one with marked crossings', () => {
    const model = totalsModel(clubMilestones.series, clubMilestones.milestones, 'clays_thrown');
    expect(model.columns.map((c) => c.label)).toEqual([
      'Sunday',
      'Clays thrown',
      'Sundays held',
      'Shooters',
      'Rounds',
    ]);
    expect(model.rows).toHaveLength(clubMilestones.series.length);
    const series = (model.option.series as { markPoint?: { data: unknown[] } }[])[0];
    const clayCrossings = clubMilestones.milestones.filter((m) => m.metric === 'clays_thrown');
    expect(series?.markPoint?.data).toHaveLength(clayCrossings.length);
  });

  it('reads the chip value from the URL key, defaulting to clays thrown', () => {
    expect(metricOf('rounds')).toBe('rounds');
    expect(metricOf('nonsense')).toBe('clays_thrown');
  });
});
```

Create `frontend/src/features/club/homeWidget.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { homeWidget } from './homeWidget';
import { clubMilestones } from './mocks';

const { Component } = homeWidget;

describe('club milestone home card', () => {
  it('is a main widget at order 20', () => {
    expect(homeWidget).toMatchObject({ id: 'club-milestone', order: 20, slot: 'main' });
  });

  it('shows the latest milestone, its Sunday, the next one and a link to the Club page', async () => {
    renderWithProviders(<Component meId={null} />);
    expect(await screen.findByRole('heading', { name: 'Club milestone' })).toBeInTheDocument();
    expect(screen.getByText('350,000 clays thrown')).toBeInTheDocument();
    expect(screen.getByText('Passed on Sunday, Sep 13, 2026')).toBeInTheDocument();
    expect(screen.getByText('Next up: 400,000 clays thrown, 41,250 to go')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'All club milestones' })).toHaveAttribute(
      'href',
      '/club#milestones',
    );
    expect(screen.getByRole('button', { name: 'About club milestones' })).toBeInTheDocument();
  });

  it('renders nothing and asks nothing while off for a viewer', async () => {
    let asked = 0;
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: {} })),
      http.get('*/api/club/milestones', () => {
        asked += 1;
        return HttpResponse.json(clubMilestones);
      }),
    );
    const { container } = renderWithProviders(<Component meId={null} />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(asked).toBe(0);
  });

  it('is hidden when there is no milestone yet', async () => {
    server.use(
      http.get('*/api/club/milestones', () =>
        HttpResponse.json({ ...clubMilestones, milestones: [], latest: null }),
      ),
    );
    const { container } = renderWithProviders(<Component meId={null} />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
```

Create `frontend/src/features/club/components/MilestonesSection.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { LAZY_CHART } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { clubMilestones } from '../mocks';
import { MilestonesSection } from './MilestonesSection';

describe('MilestonesSection', () => {
  it('lists milestones grouped by metric, newest first, linking to their Sunday', async () => {
    renderWithProviders(<MilestonesSection />, { route: '/club' });
    const list = await screen.findByRole('region', { name: 'Club milestones' });
    const link = within(list).getByRole('link', { name: '350,000 clays thrown — Sep 13, 2026' });
    expect(link).toHaveAttribute('href', '/events/2026-09-13');
    expect(within(list).getByText('On the first Sunday on record')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Milestones' })).toBeInTheDocument();
  });

  it('draws the totals chart with Table, CSV and an explainer', async () => {
    renderWithProviders(<MilestonesSection />, { route: '/club' });
    const chart = await screen.findByRole('region', { name: 'Club totals over time' }, LAZY_CHART);
    expectChartControls(chart);
    await expectExplainer(chart, 'About this chart', { read: true });
  });

  it('has no heading, no cards and no request for a viewer while off', async () => {
    let asked = 0;
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: {} })),
      http.get('*/api/club/milestones', () => {
        asked += 1;
        return HttpResponse.json(clubMilestones);
      }),
    );
    const { container } = renderWithProviders(<MilestonesSection />, { route: '/club' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    expect(asked).toBe(0);
  });

  it('says "No milestones yet." when there are none', async () => {
    server.use(
      http.get('*/api/club/milestones', () =>
        HttpResponse.json({ ...clubMilestones, milestones: [], latest: null, series: [] }),
      ),
    );
    renderWithProviders(<MilestonesSection />, { route: '/club' });
    expect(await screen.findByText('No milestones yet.')).toBeInTheDocument();
  });
});
```

In `frontend/src/features/club/explainers.test.ts`, the windowed list is exact: add `'ctot'` in sorted position (the test sorts), and append:

```ts
import { allStrings, BANNED_WORDS } from '../../test/language';

describe('club milestone explainers (Plan 19)', () => {
  it('have the three new entries with their scopes and glossary terms', () => {
    expect(explainers['club-milestone']?.scope).toBe('all-time');
    expect(explainers['club-milestones']?.scope).toBe('all-time');
    expect(explainers.ctot?.scope).toBe('windowed');
    expect(explainers['club-milestone']?.terms).toEqual(['held-sunday', 'special-shoot', 'clays-thrown']);
    expect(explainers.ctot?.terms).toEqual(['clays-thrown', 'special-shoot', 'held-sunday']);
  });

  it('use no banned word', () => {
    const entries = ['club-milestone', 'club-milestones', 'ctot'].map((key) => explainers[key]);
    for (const text of allStrings(entries)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

(Put the `import` line with the file's other imports.)

- [ ] **Step 10: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/club`
Expected: FAIL: unresolved `./milestones`, `./homeWidget`, `./components/MilestonesSection`, and `clubMilestones` is not exported by `./mocks`.

- [ ] **Step 11: Write the API hook, the mock, the models and the explainers**

In `frontend/src/features/club/api.ts`, append:

```ts
export type ClubMilestones = JsonOf<paths['/api/club/milestones']['get']>;
export type Milestone = ClubMilestones['milestones'][number];
export type NextMilestone = ClubMilestones['next'][number];
export type ClubTotals = ClubMilestones['series'][number];
export type MilestoneMetric = Milestone['metric'];

/** Plan 19 §3.5: asked only while the feature is visible, so a viewer never meets the 404. */
export function useClubMilestones(enabled: boolean) {
  return useQuery({
    queryKey: ['/api/club/milestones'],
    queryFn: () => unwrap(api.GET('/api/club/milestones')),
    enabled,
  });
}
```

In `frontend/src/features/club/mocks.ts`, replace

```ts
import type {
  AttendancePoint,
```

with

```ts
import type {
  ClubMilestones,
  AttendancePoint,
```

and add, before `export const handlers`:

```ts
export const clubMilestones: ClubMilestones = {
  as_of: '2026-09-27',
  milestones: [
    {
      metric: 'clays_thrown',
      threshold: 350000,
      event_date: '2026-09-13',
      label: '350,000 clays thrown',
      first_on_record: false,
    },
    {
      metric: 'sundays_held',
      threshold: 300,
      event_date: '2026-03-08',
      label: '300 Sundays held',
      first_on_record: false,
    },
    {
      metric: 'shooters',
      threshold: 25,
      event_date: '2020-01-05',
      label: '25 different shooters',
      first_on_record: true,
    },
  ],
  latest: {
    metric: 'clays_thrown',
    threshold: 350000,
    event_date: '2026-09-13',
    label: '350,000 clays thrown',
    first_on_record: false,
  },
  next: [
    { metric: 'sundays_held', threshold: 350, current: 310, remaining: 40, label: '350 Sundays held' },
    { metric: 'clays_thrown', threshold: 400000, current: 358750, remaining: 41250, label: '400,000 clays thrown' },
    { metric: 'shooters', threshold: 400, current: 332, remaining: 68, label: '400 different shooters' },
    { metric: 'rounds', threshold: 10000, current: 7175, remaining: 2825, label: '10,000 rounds shot' },
  ],
  series: [
    { event_date: '2020-01-05', clays_thrown: 1400, sundays_held: 1, shooters: 28, rounds: 28 },
    { event_date: '2026-09-13', clays_thrown: 357500, sundays_held: 309, shooters: 331, rounds: 7150 },
    { event_date: '2026-09-20', clays_thrown: 357500, sundays_held: 310, shooters: 332, rounds: 7150 },
    { event_date: '2026-09-27', clays_thrown: 358750, sundays_held: 310, shooters: 332, rounds: 7175 },
  ],
};
```

and add this handler to the `handlers` array:

```ts
  http.get('*/api/club/milestones', () => HttpResponse.json(clubMilestones)),
```

(Next up: `sundays_held` 40/350 = 0.114, `clays_thrown` 41,250/400,000 = 0.103, `shooters` 68/400 = 0.17, `rounds` 2,825/10,000 = 0.28, so clays thrown is the smallest share, as the widget test expects.)

Create `frontend/src/features/club/milestones.ts`:

```ts
import type { EChartsOption, LineSeriesOption } from 'echarts';
import { lineOption } from '../../components/charts/builders/line';
import type { TabularColumn, TabularData } from '../../components/charts/types';
import type { ClubTotals, Milestone, MilestoneMetric, NextMilestone } from './api';

export const METRIC_CHIPS: readonly { value: MilestoneMetric; label: string }[] = [
  { value: 'clays_thrown', label: 'Clays thrown' },
  { value: 'sundays_held', label: 'Sundays held' },
  { value: 'shooters', label: 'Shooters' },
  { value: 'rounds', label: 'Rounds' },
];

export const TOTALS_COLUMNS: TabularColumn[] = [
  { key: 'event_date', label: 'Sunday', type: 'date' },
  { key: 'clays_thrown', label: 'Clays thrown', type: 'int' },
  { key: 'sundays_held', label: 'Sundays held', type: 'int' },
  { key: 'shooters', label: 'Shooters', type: 'int' },
  { key: 'rounds', label: 'Rounds', type: 'int' },
];

/** The `mm` URL value as a metric; anything unknown is clays thrown. */
export function metricOf(raw: string | null): MilestoneMetric {
  return METRIC_CHIPS.find((c) => c.value === raw)?.value ?? 'clays_thrown';
}

/** The next milestone with the smallest share of its round number still to go (§3.5.3). */
export function nextUp(next: readonly NextMilestone[]): NextMilestone | null {
  return [...next].sort((a, b) => a.remaining / a.threshold - b.remaining / b.threshold)[0] ?? null;
}

/** Table rows of every metric, and a line of `metric` with a dot at each of its crossings. */
export function totalsModel(
  series: readonly ClubTotals[],
  crossings: readonly Milestone[],
  metric: MilestoneMetric,
): TabularData & { option: EChartsOption } {
  const rows = series.map((r) => ({ ...r }));
  const data: TabularData = { columns: TOTALS_COLUMNS, rows };
  const base = lineOption(data, { x: 'event_date', y: [metric] });
  const valueOn = new Map(series.map((r) => [r.event_date, r[metric]]));
  const [first, ...rest] = (base.series ?? []) as LineSeriesOption[];
  const marked: LineSeriesOption = {
    ...first,
    markPoint: {
      symbol: 'circle',
      symbolSize: 10,
      label: { show: true, position: 'top', formatter: '{b}' },
      data: crossings
        .filter((c) => c.metric === metric)
        .map((c) => ({
          name: c.threshold.toLocaleString('en-US'),
          coord: [c.event_date, valueOn.get(c.event_date) ?? c.threshold],
        })),
    },
  };
  return { ...data, option: { ...base, series: [marked, ...rest] } };
}
```

In `frontend/src/features/club/explainers.ts`, add these three entries to the exported `explainers` record (copy from spec §3.5.3; `club-milestones` is this plan's copy, Decision 3):

```ts
  'club-milestone': {
    what: "The club's most recent round number, such as total clays thrown or Sundays held.",
    computed: [
      'We add up every Sunday on record since Jan 5, 2020, in date order, and note the Sunday each total first reached a round number.',
      'Special shoots count as a Sunday held and add their shooters, but not their clays or rounds.',
    ],
    scope: 'all-time',
    terms: ['held-sunday', 'special-shoot', 'clays-thrown'],
  },
  'club-milestones': {
    what: 'Every round number the club has passed, with the Sunday it was passed on.',
    computed: [
      'Totals add up every Sunday on record, in date order.',
      'A milestone is dated at the first Sunday its total reached the round number.',
      'Special shoots count as a Sunday held and add their shooters, but not their clays or rounds.',
    ],
    scope: 'all-time',
    terms: ['held-sunday', 'special-shoot', 'clays-thrown'],
  },
  ctot: {
    what: "How the club's running totals have grown, Sunday by Sunday, with each round number marked.",
    read: ['A dot marks the Sunday a round number was passed.', 'A flat stretch means no Sundays were held.'],
    computed: [
      'Clays thrown: 50 for every regular round. Rounds: regular rounds only.',
      'Sundays held and Shooters include special shoots.',
      'Totals start at the first Sunday on record, Jan 5, 2020.',
    ],
    scope: 'windowed',
    terms: ['clays-thrown', 'special-shoot', 'held-sunday'],
  },
```

- [ ] **Step 12: Write the home card, the Club section and the page edit**

Create `frontend/src/features/club/homeWidget.tsx`:

```tsx
import { Link } from 'react-router';
import { AboutBlock } from '../../components/ui/AboutBlock';
import { AdminPreviewBadge } from '../../components/ui/AdminPreviewBadge';
import { Card } from '../../components/ui/Card';
import { useFeature } from '../../lib/features';
import { formatDay } from '../home/format';
import type { HomeWidget } from '../home/widgets';
import { useClubMilestones } from './api';
import { explainers } from './explainers';
import { nextUp } from './milestones';

function ClubMilestoneCard() {
  const { visible } = useFeature('club_milestones');
  const query = useClubMilestones(visible);
  const latest = query.data?.latest ?? null;
  if (!visible || latest === null) return null;
  const upcoming = nextUp(query.data?.next ?? []);
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          Club milestone
          <AdminPreviewBadge feature="club_milestones" />
        </span>
      }
    >
      <div className="flex flex-col gap-2">
        <p className="text-2xl font-medium">{latest.label}</p>
        <p className="text-sm text-text-muted">{`Passed on Sunday, ${formatDay(latest.event_date)}`}</p>
        {upcoming !== null && (
          <p>{`Next up: ${upcoming.label}, ${upcoming.remaining.toLocaleString('en-US')} to go`}</p>
        )}
        <Link to="/club#milestones" className="inline-flex min-h-11 items-center self-start underline">
          All club milestones
        </Link>
        <AboutBlock explainer={explainers['club-milestone']} label="About club milestones" />
      </div>
    </Card>
  );
}

export const homeWidget: HomeWidget = {
  id: 'club-milestone',
  order: 20,
  slot: 'main',
  Component: ClubMilestoneCard,
};
```

Create `frontend/src/features/club/components/MilestonesSection.tsx`:

```tsx
import { useId, useMemo } from 'react';
import { Link } from 'react-router';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import { AboutBlock } from '../../../components/ui/AboutBlock';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Card, CardHeadingLevel } from '../../../components/ui/Card';
import { Chip } from '../../../components/ui/Chip';
import { useFeature } from '../../../lib/features';
import { useTimeWindow } from '../../../lib/timeWindow';
import { enumCodec, useUrlState } from '../../../lib/useUrlState';
import { formatDay } from '../../home/format';
import { useClubMilestones, type ClubMilestones, type MilestoneMetric } from '../api';
import { explainers } from '../explainers';
import { METRIC_CHIPS, totalsModel } from '../milestones';

const METRIC_CODEC = enumCodec(METRIC_CHIPS.map((c) => c.value));

function MilestoneList({ data }: { data: ClubMilestones | undefined }) {
  return (
    <Card title="Club milestones">
      <AboutBlock explainer={explainers['club-milestones']} label="About club milestones" />
      {data === undefined ? (
        <p role="status">Loading milestones…</p>
      ) : data.milestones.length === 0 ? (
        <p>No milestones yet.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {METRIC_CHIPS.map(({ value, label }) => {
            const rows = data.milestones.filter((m) => m.metric === value);
            if (rows.length === 0) return null;
            return (
              <section key={value} aria-label={label} className="flex flex-col gap-1">
                <h4 className="text-sm font-medium text-text-muted">{label}</h4>
                <ul className="flex flex-col">
                  {rows.map((m) => (
                    <li key={`${m.metric}-${String(m.threshold)}`} className="flex flex-col">
                      <Link
                        to={`/events/${m.event_date}`}
                        className="inline-flex min-h-11 items-center underline"
                      >
                        {`${m.label} — ${formatDay(m.event_date)}`}
                      </Link>
                      {m.first_on_record && (
                        <span className="text-xs text-text-muted">On the first Sunday on record</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function TotalsChart({ data }: { data: ClubMilestones }) {
  const [metric, setMetric] = useUrlState<MilestoneMetric>('mm', METRIC_CODEC, 'clays_thrown');
  const { range } = useTimeWindow();
  const model = useMemo(
    () => totalsModel(data.series, data.milestones, metric),
    [data.series, data.milestones, metric],
  );
  return (
    <ChartFrame
      title="Club totals over time"
      option={model.option}
      columns={model.columns}
      rows={model.rows}
      csvName="club-totals"
      ariaLabel="Club running totals by Sunday"
      urlKey="ctot"
      window={range}
      full={{ rows: model.rows, option: model.option, note: 'Every Sunday on record.' }}
      explainer={explainers.ctot}
      controls={
        <div role="group" aria-label="Total" className="flex flex-wrap gap-2">
          {METRIC_CHIPS.map((c) => (
            <Chip key={c.value} selected={c.value === metric} onClick={() => setMetric(c.value)}>
              {c.label}
            </Chip>
          ))}
        </div>
      }
    />
  );
}

/** The Club page's first section (Plan 19 §3.5.3); nothing at all for a viewer while off. */
export function MilestonesSection() {
  const { visible } = useFeature('club_milestones');
  const query = useClubMilestones(visible);
  const headingId = useId();
  if (!visible) return null;
  return (
    <section id="milestones" aria-labelledby={headingId} className="flex scroll-mt-28 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={headingId} className="text-xl font-medium">
          Milestones
        </h2>
        <AdminPreviewBadge feature="club_milestones" />
      </div>
      <CardHeadingLevel value={3}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <MilestoneList data={query.data} />
          {query.data !== undefined && query.data.series.length > 0 && (
            <TotalsChart data={query.data} />
          )}
        </div>
      </CardHeadingLevel>
    </section>
  );
}
```

`ChartFrame` is the eager component the club charts already use through `ClubCharts`; importing it here keeps ECharts out of the entry chunk as long as `ChartFrame` itself loads ECharts lazily (it does: `EChart` is lazy). If the bundle-budget ratchet grows past `entry_js_gz_kb`, load `MilestonesSection` with `LazyChart` the way `ClubPage` loads `ClubCharts`.

In `frontend/src/features/club/pages/ClubPage.tsx`, replace

```tsx
import { LazyChart } from '../components/LazyChart';
```

with

```tsx
import { LazyChart } from '../components/LazyChart';
import { MilestonesSection } from '../components/MilestonesSection';
```

and replace

```tsx
      <PageTopSlot page="club" />
      <Section title="Attendance">
```

with

```tsx
      <PageTopSlot page="club" />
      <MilestonesSection />
      <Section title="Attendance">
```

- [ ] **Step 13: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/club src/features/home src/features/glossary/explainerLint.test.ts`
Expected: PASS (the trigger lint passes for the new entries).

- [ ] **Step 14: Write and run the e2e at both sizes**

Create `frontend/e2e/club-milestones.spec.ts`:

```ts
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

test('the Home card links to the Club milestones', async ({ page }) => {
  await page.goto('/');
  const card = page.getByRole('region', { name: /^Club milestone/ });
  await expect(card).toBeVisible();
  await card.getByRole('link', { name: 'All club milestones' }).click();
  await expect(page).toHaveURL(/\/club#milestones$/);
  await expect(page.getByRole('heading', { level: 2, name: /^Milestones/ })).toBeVisible();
});

test('the totals chart has Table, CSV, fullscreen and an explainer', async ({ page }) => {
  await page.goto('/club?w=all');
  await whenSettled(page);
  const chart = page.getByRole('region', { name: 'Club totals over time' });
  await expect(chart).toBeVisible();
  await chart.getByRole('button', { name: 'About this chart' }).click();
  await expect(chart.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  const download = page.waitForEvent('download');
  await chart.getByRole('button', { name: 'CSV' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^club-totals.*\.csv$/);
  const csv = await (await file.createReadStream()).toArray();
  expect(Buffer.concat(csv).toString('utf8')).toContain('Sunday,Clays thrown,Sundays held,Shooters,Rounds');
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(page.getByRole('dialog', { name: 'Club totals over time' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expectNoSideScroll(page);
});

test('the window trims the inline table, not the data', async ({ page }) => {
  const rowsAt = async (w: string) => {
    await page.goto(`/club?w=${w}&ctot=table`);
    await whenSettled(page);
    return page.getByRole('region', { name: 'Club totals over time' }).getByRole('row').count();
  };
  expect(await rowsAt('8w')).toBeLessThan(await rowsAt('all'));
});
```

Check the Table toggle's URL value: `ChartFrame` keeps its view in `?<urlKey>=table` (the doc comment on `urlKey` says "table", "full"); if the existing `club.spec.ts` opens tables another way, copy that.

Run the stack (project `task19-6`, port 18080) and: `pnpm exec playwright test club-milestones.spec.ts club.spec.ts home.spec.ts --project=desktop --project=mobile`.
Expected: PASS (`club.spec.ts` and `home.spec.ts` still pass with the new card and section).

- [ ] **Step 15: Run the backend and frontend gates, then commit**

```bash
git add backend/src/sunday_clays/analytics/club_milestones.py backend/src/sunday_clays/api/routes/club.py \
  backend/tests/unit/analytics/test_club_milestones.py backend/tests/integration/api/test_club_milestones_api.py \
  frontend/src/features/club frontend/e2e/club-milestones.spec.ts
git commit -m "feat(club): club milestones on Home and the Club page (Plan 19 T6)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: Summary card (`task/19-7-summary-card`, wave 3)

**Files:**
- Create: `backend/src/sunday_clays/analytics/personal_best.py` (the one PB rule, D18)
- Modify: `backend/src/sunday_clays/api/routes/events.py` (`event_notables` uses `is_new_pb`; the local constant goes)
- Create: `backend/src/sunday_clays/analytics/summary.py`
- Modify: `backend/src/sunday_clays/api/routes/shooters.py` (models and one route)
- Create: `backend/tests/unit/analytics/test_shooter_summary.py`
- Create: `backend/tests/integration/api/test_shooter_summary_api.py`
- Modify: `frontend/src/lib/share.ts`, `frontend/src/lib/share.test.ts`
- Create: `frontend/src/features/summary/{api.ts, mocks.ts, format.ts, format.test.ts, explainers.ts, explainers.test.ts, profileSection.tsx, profileSection.test.tsx}`
- Create: `frontend/src/features/summary/components/SummaryCard.tsx`
- Create: `frontend/e2e/summary-card.spec.ts`

**Interfaces:**
- Consumes: T1 `feature_gate("summary_card")`; T2 `useFeature`, `AdminPreviewBadge`, `Explainer.terms`, `BANNED_WORDS`; `frames.load_rounds`, `load_appearances`, `load_calendar`; `streaks.streaks`; `achievements.registry.trophy`; `_filters.check_window`; `shooters._profile`; `api.routes.events.event_notables` (edited to share the PB rule); `lib/timeWindow.useTimeWindow`, `lib/windowText.windowTagText`; `features/share/{ShareCard, filenames.slugify}`; `components/WidenWindowButtons`.
- Produces (T8 relies on `trophy_title`; T10 on the card's copy):
  - `analytics.personal_best`: `PB_MIN_PRIOR_ROUNDS = 5` (moved from `api.routes.events`, which imports it back), `is_new_pb(score: int, previous_best: int | None, n_prior: int) -> bool`; used by `event_notables` and `analytics.summary` (spec D18: one source for each rule).
  - `analytics.summary`: `LEFT_OUT_TROPHY_CODES` (the four D14 trophies: `first_win`, `podium`, `station_top_gun`, `hardest_station_clean`), `trophy_title(code: str) -> str | None` (None for unknown or left-out codes; `events:5` → "Events Attended — Silver", `doubleheader` → "Doubleheader"), frozen dataclasses `BestRound(score, event_date)` and `ShooterSummary(shooter_id, display_name, date_from: date | None, date_to: date, sundays, special_sundays, rounds, average: float | None, best: BestRound | None, pbs_set, trophies, trophy_names: tuple[str, ...], longest_streak)`, `compute_summary(...) -> ShooterSummary` (pure), `shooter_summary(session, shooter_id, date_from, date_to) -> ShooterSummary` (`@cached_by_data_version`).
  - `GET /api/shooters/{id}/summary?from=&to=` → `ShooterSummaryCardOut` (JSON keys `from` and `to`), gated.
  - `lib/share.ts`: `renderElementToPng(el: HTMLElement): Promise<Blob>`, `downloadElementAsImage(el: HTMLElement, filename: string): Promise<void>`.

- [ ] **Step 1: Write the failing summary rules tests**

Create `backend/tests/unit/analytics/test_shooter_summary.py`:

```python
"""Summary card facts (Plan 19 §3.6.1, D14, D18) on hand-built frames."""

from datetime import date, timedelta

import pandas as pd
import pytest

from sunday_clays.analytics import personal_best, summary
from sunday_clays.api.routes import events

D0 = date(2026, 1, 4)
ME = 3


def sunday(i: int) -> date:
    return D0 + timedelta(weeks=i)


def frames_for(
    scores: dict[int, list[int]], special: tuple[int, ...] = (), held_extra: tuple[int, ...] = ()
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """scores: Sunday index -> this shooter's regular scores that day."""
    rounds = pd.DataFrame(
        [(sunday(i), ME, s) for i, ss in scores.items() for s in ss],
        columns=["event_date", "shooter_id", "score"],
    )
    days = sorted({*scores, *special, *held_extra})
    appearances = pd.DataFrame(
        [(sunday(i), ME) for i in sorted({*scores, *special})], columns=["event_date", "shooter_id"]
    )
    calendar = pd.DataFrame(
        [
            (sunday(i), True, "special" if i in special else "regular")
            for i in days
        ],
        columns=["event_date", "results_complete", "kind"],
    )
    return rounds, appearances, calendar


def run(
    scores: dict[int, list[int]],
    date_from: date | None,
    date_to: date,
    *,
    special: tuple[int, ...] = (),
    held_extra: tuple[int, ...] = (),
    awards: tuple[tuple[str, date], ...] = (),
) -> summary.ShooterSummary:
    rounds, appearances, calendar = frames_for(scores, special, held_extra)
    return summary.compute_summary(
        ME, "Hadley, Ike", rounds, appearances, calendar, list(awards), date_from, date_to
    )


def test_the_card_and_the_sunday_page_share_one_pb_rule() -> None:
    """D18: one source. Kills a copied constant or a re-implemented comparison in either place."""
    assert summary.is_new_pb is personal_best.is_new_pb
    assert events.is_new_pb is personal_best.is_new_pb
    assert events.PB_MIN_PRIOR_ROUNDS is personal_best.PB_MIN_PRIOR_ROUNDS
    assert personal_best.PB_MIN_PRIOR_ROUNDS == 5
    assert not hasattr(summary, "PB_MIN_PRIOR_ROUNDS")


@pytest.mark.parametrize(
    ("score", "previous_best", "n_prior", "expected"),
    [
        (45, 40, 5, True),  # exactly 5 earlier rounds counts (kills > 5)
        (45, 40, 4, False),
        (45, 45, 5, False),  # equal is not a PB (kills >=)
        (45, None, 5, False),
    ],
)
def test_is_new_pb(score: int, previous_best: int | None, n_prior: int, expected: bool) -> None:
    assert personal_best.is_new_pb(score, previous_best, n_prior) is expected


def test_rounds_average_and_best_in_the_window() -> None:
    result = run({0: [40], 1: [44, 46], 2: [41]}, sunday(1), sunday(2))
    assert (result.sundays, result.rounds, result.average) == (2, 3, 43.7)
    assert result.best == summary.BestRound(46, sunday(1))


def test_a_pb_needs_five_earlier_rounds_and_a_strictly_higher_score() -> None:
    four_before = {0: [40], 1: [40], 2: [40], 3: [40], 4: [45]}
    assert run(four_before, None, sunday(4)).pbs_set == 0  # 4 earlier rounds: not yet
    five_before = {0: [40], 1: [40], 2: [40], 3: [40], 4: [40], 5: [45]}
    assert run(five_before, None, sunday(5)).pbs_set == 1  # exactly 5 counts (kills > 5)
    tie = {0: [40], 1: [40], 2: [40], 3: [40], 4: [45], 5: [45]}
    assert run(tie, None, sunday(5)).pbs_set == 1  # 45 again is not a new PB (kills >=)


def test_earlier_rounds_before_the_window_count_toward_the_pb_rule() -> None:
    history = {0: [40], 1: [40], 2: [40], 3: [40], 4: [40], 5: [45]}
    assert run(history, sunday(5), sunday(5)).pbs_set == 1


def test_window_edges_are_inclusive() -> None:
    result = run({0: [40], 1: [41], 2: [42]}, sunday(0), sunday(2))
    assert result.sundays == 3 and result.rounds == 3


def test_the_streak_counts_only_sundays_inside_the_window() -> None:
    result = run({i: [40] for i in range(6)}, sunday(3), sunday(5))
    assert result.longest_streak == 3


def test_a_special_only_shooter_has_sundays_and_nothing_else() -> None:
    result = run({}, sunday(0), sunday(2), special=(1,))
    assert (result.sundays, result.special_sundays, result.rounds) == (1, 1, 0)
    assert result.average is None and result.best is None and result.pbs_set == 0


def test_an_empty_window() -> None:
    result = run({5: [40]}, sunday(0), sunday(2))
    assert result.sundays == 0 and result.rounds == 0 and result.longest_streak == 0


def test_an_open_start_covers_everything_up_to_to() -> None:
    assert run({0: [40], 1: [41], 9: [50]}, None, sunday(2)).rounds == 2


def test_trophies_leave_out_competition_and_name_three_newest() -> None:
    awards = (
        ("events:5", sunday(1)),  # Events Attended, Silver
        ("iron_streak:1", sunday(2)),
        ("doubleheader", sunday(2)),
        ("first_win", sunday(2)),  # D14: never counted or named
        ("station_top_gun", sunday(2)),  # D14 too, though the registry files it under "stations"
        ("years_active:1", sunday(0)),
        ("events:1", date(2025, 1, 5)),  # before the window
    )
    result = run({0: [40], 1: [41], 2: [42]}, sunday(0), sunday(2), awards=awards)
    assert result.trophies == 4
    assert result.trophy_names == ("Doubleheader", "Iron Streak — Bronze", "Events Attended — Silver")


@pytest.mark.parametrize(
    ("code", "title"),
    [
        ("events:5", "Events Attended — Silver"),
        ("doubleheader", "Doubleheader"),
        ("station_cleaner:1", "Station Cleaner — Bronze"),  # a stations trophy D14 does not name
        ("first_win", None),
        ("podium", None),
        ("station_top_gun", None),
        ("hardest_station_clean", None),
        ("nope", None),
    ],
)
def test_trophy_title(code: str, title: str | None) -> None:
    assert summary.trophy_title(code) == title
```

The codes above were checked against the registry at the plan's base (`registry.load_all()`; `registry.trophy(code)`): `events:5` is Events Attended Silver (`events:1`–`events:4` are Bronze), `iron_streak:1` and `years_active:1` are Bronze, `doubleheader` is a one-off, `first_win` and `podium` are category `competition`, and `station_top_gun`, `hardest_station_clean` and `station_cleaner:1` are category `stations`. D14 names Station Top Gun and Hardest-Station Clean as left out, so the rule is a fixed code set, not the `competition` category alone.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/analytics/test_shooter_summary.py`
Expected: FAIL, `ImportError: cannot import name 'personal_best'` (and `summary`).

- [ ] **Step 3: Write the summary rules**

Create `backend/src/sunday_clays/analytics/personal_best.py`:

```python
"""The personal-best rule (C12), one source for the Sunday page's notables and the summary card
(Plan 19 D18). The insights milestone and the PB trophy keep their own copies; they are out of
Plan 19's scope and their tests pin the same 5."""

from typing import Final

PB_MIN_PRIOR_ROUNDS: Final = 5


def is_new_pb(score: int, previous_best: int | None, n_prior: int) -> bool:
    """A best round is a PB once at least 5 earlier rounds exist and it beats every one of them."""
    return n_prior >= PB_MIN_PRIOR_ROUNDS and previous_best is not None and score > previous_best
```

In `backend/src/sunday_clays/api/routes/events.py`, replace

```python
from sunday_clays.analytics import frames
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
```

with

```python
from sunday_clays.analytics import frames
from sunday_clays.analytics.personal_best import PB_MIN_PRIOR_ROUNDS as PB_MIN_PRIOR_ROUNDS
from sunday_clays.analytics.personal_best import is_new_pb
from sunday_clays.api.routes._convert import opt_float, opt_int, opt_str, rows
```

replace

```python
router = APIRouter()

PB_MIN_PRIOR_ROUNDS = 5
EventKind = Literal["regular", "special"]
```

with

```python
router = APIRouter()

EventKind = Literal["regular", "special"]
```

and replace

```python
        if n_prior >= PB_MIN_PRIOR_ROUNDS and int(r["score"]) > previous:
```

with

```python
        if is_new_pb(int(r["score"]), previous, n_prior):
```

(`previous` is 0 when there is no earlier round, but then `n_prior` is 0 and the rule is false either way.) The `as PB_MIN_PRIOR_ROUNDS` form is an explicit re-export (ruff and mypy accept it), so anything that imported the constant from `api.routes.events` keeps working. The existing notables tests (`tests/integration/analytics_core/test_events_routes.py`, `tests/integration/special/test_special_routes.py`) must still pass unchanged; run them in Step 4.

Create `backend/src/sunday_clays/analytics/summary.py`:

```python
"""The summary card's facts for one shooter and one window (Plan 19 §3.6.1, D18).

Round-type filters never apply: a PB set in a round-type slice is not a PB. Competition trophies
(First Win, Podium, Station Top Gun, Hardest-Station Clean) are never counted or named (D14).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, cast

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements.registry import trophy
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.personal_best import is_new_pb
from sunday_clays.analytics.streaks import streaks

TROPHY_NAMES_SHOWN: Final = 3
#: D14's four: First Win and Podium (category "competition"), Station Top Gun and Hardest-Station
#: Clean (category "stations" in the registry). By code, so a category filter cannot miss two.
LEFT_OUT_TROPHY_CODES: Final = frozenset(
    {"first_win", "podium", "station_top_gun", "hardest_station_clean"}
)


def trophy_title(code: str) -> str | None:
    """"Events Attended — Silver" for a tier, the achievement name for a one-off, None for an
    unknown trophy or one of D14's four."""
    found = trophy(code)
    if found is None or found.achievement.code in LEFT_OUT_TROPHY_CODES:
        return None
    if found.tier is None:
        return found.achievement.name
    return f"{found.achievement.name} — {found.tier.metal.value.title()}"


@dataclass(frozen=True)
class BestRound:
    score: int
    event_date: date


@dataclass(frozen=True)
class ShooterSummary:
    shooter_id: int
    display_name: str
    date_from: date | None
    date_to: date
    sundays: int
    special_sundays: int
    rounds: int
    average: float | None
    best: BestRound | None
    pbs_set: int
    trophies: int
    trophy_names: tuple[str, ...]
    longest_streak: int


def _inside(day: date, date_from: date | None, date_to: date) -> bool:
    return (date_from is None or day >= date_from) and day <= date_to


def _pbs_set(mine: pd.DataFrame, date_from: date | None, date_to: date) -> int:
    count = 0
    best_before: int | None = None
    n_before = 0
    for key, scores in mine.groupby("event_date", sort=True)["score"]:
        day = cast(date, key)
        top = int(scores.max())
        if _inside(day, date_from, date_to) and is_new_pb(top, best_before, n_before):
            count += 1
        best_before = top if best_before is None else max(best_before, top)
        n_before += len(scores)
    return count


def compute_summary(
    shooter_id: int,
    display_name: str,
    rounds: pd.DataFrame,
    appearances: pd.DataFrame,
    calendar: pd.DataFrame,
    awards: Sequence[tuple[str, date]],
    date_from: date | None,
    date_to: date,
) -> ShooterSummary:
    """`rounds`: regular rounds (any shooters; filtered here); `appearances`: shooter_id and
    event_date, special included; `calendar`: event_date, results_complete, kind."""
    mine = rounds.loc[rounds["shooter_id"] == shooter_id]
    mine = mine.loc[mine["event_date"] <= date_to]
    window = mine.loc[[_inside(d, date_from, date_to) for d in mine["event_date"]]]
    came = appearances.loc[appearances["shooter_id"] == shooter_id]
    came = came.loc[[_inside(d, date_from, date_to) for d in came["event_date"]]]
    cal = calendar.loc[[_inside(d, date_from, date_to) for d in calendar["event_date"]]]
    special_days = set(cal.loc[cal["kind"].eq(frames.EVENT_KIND_SPECIAL), "event_date"])
    sundays = set(came["event_date"])
    best: BestRound | None = None
    if not window.empty:
        top = int(window["score"].max())
        first_day = min(d for d, s in zip(window["event_date"], window["score"], strict=True) if s == top)
        best = BestRound(top, first_day)
    streak_rows = streaks(came, cal, date_to)
    mine_streak = streak_rows.loc[streak_rows["shooter_id"] == shooter_id, "longest_streak"]
    kept = sorted(
        (
            (day, title)
            for code, day in awards
            if _inside(day, date_from, date_to) and (title := trophy_title(code)) is not None
        ),
        key=lambda item: (-item[0].toordinal(), item[1]),
    )
    return ShooterSummary(
        shooter_id=shooter_id,
        display_name=display_name,
        date_from=date_from,
        date_to=date_to,
        sundays=len(sundays),
        special_sundays=len(sundays & special_days),
        rounds=len(window),
        average=None if window.empty else round(float(window["score"].mean()), 1),
        best=best,
        pbs_set=_pbs_set(mine, date_from, date_to),
        trophies=len(kept),
        trophy_names=tuple(title for _, title in kept[:TROPHY_NAMES_SHOWN]),
        longest_streak=int(mine_streak.iloc[0]) if not mine_streak.empty else 0,
    )


@cached_by_data_version
def shooter_summary(
    session: Session, shooter_id: int, date_from: date | None, date_to: date
) -> ShooterSummary:
    display_name = session.execute(
        text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s"), {"s": shooter_id}
    ).scalar_one()
    awards = [
        (str(code), day)
        for code, day in session.execute(
            text("SELECT code, event_date FROM achievements_awarded WHERE shooter_id = :s"),
            {"s": shooter_id},
        ).all()
    ]
    return compute_summary(
        shooter_id,
        str(display_name),
        frames.load_rounds(session),
        frames.load_appearances(session),
        frames.load_calendar(session),
        awards,
        date_from,
        date_to,
    )
```

The "best round" of a tie is its **earliest** Sunday in the window (the day the score was first reached).

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/analytics/test_shooter_summary.py tests/integration/analytics_core/test_events_routes.py tests/integration/special/test_special_routes.py`
Expected: PASS.

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/integration/api/test_shooter_summary_api.py`:

```python
"""GET /api/shooters/{id}/summary (Plan 19 §3.6.1, §5.2)."""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch

URL = "/api/shooters/{id}/summary"


def _on(session: Session) -> None:
    set_switch(session, get_settings(), "summary_card", True)


def _id(session: Session, name: str) -> int:
    return int(
        session.execute(
            text("SELECT shooter_id FROM shooter_profiles WHERE display_name = :n"), {"n": name}
        ).scalar_one()
    )


def test_gated_404_for_a_viewer_and_200_for_an_admin(
    fx_viewer_client: TestClient, fx_admin_client: TestClient
) -> None:
    params = {"to": "2026-09-27"}
    assert fx_viewer_client.get(URL.format(id=3), params=params).json() == {"detail": "Not Found"}
    assert fx_admin_client.get(URL.format(id=3), params=params).status_code == 200


def test_a_special_only_shooter(
    fx_special_viewer_client: TestClient, fx_special_session: Session
) -> None:
    _on(fx_special_session)
    kim = _id(fx_special_session, "Kim, Pat")
    body = fx_special_viewer_client.get(
        URL.format(id=kim), params={"from": "2026-08-03", "to": "2026-09-27"}
    ).json()
    assert body["display_name"] == "Kim, Pat"
    assert (body["sundays"], body["special_sundays"], body["rounds"]) == (1, 1, 0)
    assert body["average"] is None and body["best"] is None
    assert body["from"] == "2026-08-03" and body["to"] == "2026-09-27"


def test_the_special_sunday_extends_a_streak(
    fx_viewer_client: TestClient,
    fx_session: Session,
    fx_special_viewer_client: TestClient,
    fx_special_session: Session,
) -> None:
    _on(fx_session)
    _on(fx_special_session)
    params = {"from": "2026-09-13", "to": "2026-09-27"}
    plain = fx_viewer_client.get(URL.format(id=_id(fx_session, "Hadley, Ike")), params=params).json()
    special = fx_special_viewer_client.get(
        URL.format(id=_id(fx_special_session, "Hadley, Ike")), params=params
    ).json()
    assert special["sundays"] == plain["sundays"] + 1
    assert special["longest_streak"] >= plain["longest_streak"]
    assert special["rounds"] == plain["rounds"]


def test_from_omitted_is_an_open_start(fx_viewer_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    open_start = fx_viewer_client.get(URL.format(id=3), params={"to": "2026-09-27"}).json()
    lifetime = fx_viewer_client.get("/api/shooters/3").json()["odometer"]
    assert open_start["from"] is None
    assert open_start["rounds"] == lifetime["rounds"]


def test_errors(fx_viewer_client: TestClient, fx_session: Session) -> None:
    _on(fx_session)
    assert fx_viewer_client.get(URL.format(id=3)).status_code == 422  # `to` is required
    bad = fx_viewer_client.get(URL.format(id=3), params={"from": "2026-09-27", "to": "2026-09-13"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_range"
    missing = fx_viewer_client.get(URL.format(id=999999), params={"to": "2026-09-27"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "shooter_not_found"
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_shooter_summary_api.py`
Expected: FAIL (no route: the admin also gets 404).

- [ ] **Step 7: Write the route**

In `backend/src/sunday_clays/api/routes/shooters.py`, replace

```python
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
```

with

```python
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field
```

replace

```python
from sunday_clays.analytics.streaks import streaks
```

with

```python
from sunday_clays.analytics.streaks import streaks
from sunday_clays.analytics.summary import shooter_summary
from sunday_clays.api.routes._features import feature_gate
```

and append at the end of the file:

```python
class BestRoundOut(BaseModel):
    score: int
    event_date: date


class ShooterSummaryCardOut(BaseModel):
    """Plan 19 §3.6.1. JSON keys `from` and `to` match the query parameters."""

    model_config = ConfigDict(populate_by_name=True)

    shooter_id: int
    display_name: str
    date_from: date | None = Field(alias="from")
    date_to: date = Field(alias="to")
    sundays: int  # appearances in [from, to], special included
    special_sundays: int
    rounds: int  # regular rounds in the window
    average: float | None
    best: BestRoundOut | None
    pbs_set: int
    trophies: int  # awards in the window, competition left out
    trophy_names: list[str]  # up to 3, newest first
    longest_streak: int  # Sundays inside the window only


@router.get("/api/shooters/{id}/summary", dependencies=[feature_gate("summary_card")])
def get_shooter_summary(
    shooter_id: ShooterId,
    session: SessionDep,
    date_to: Annotated[date, Query(alias="to")],
    date_from: Annotated[date | None, Query(alias="from")] = None,
) -> ShooterSummaryCardOut:
    """The summary card for [from, to] (`from` absent: an open start). Every round type (D18)."""
    check_window(date_from, date_to)
    _profile(session, shooter_id)
    s = shooter_summary(session, shooter_id, date_from, date_to)
    return ShooterSummaryCardOut(
        shooter_id=s.shooter_id,
        display_name=s.display_name,
        date_from=s.date_from,
        date_to=s.date_to,
        sundays=s.sundays,
        special_sundays=s.special_sundays,
        rounds=s.rounds,
        average=s.average,
        best=None if s.best is None else BestRoundOut(score=s.best.score, event_date=s.best.event_date),
        pbs_set=s.pbs_set,
        trophies=s.trophies,
        trophy_names=list(s.trophy_names),
        longest_streak=s.longest_streak,
    )
```

FastAPI serializes responses by alias, so the JSON says `from`/`to`; `populate_by_name=True` lets the constructor use the Python names.

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_shooter_summary_api.py tests/integration/api/test_route_auth_matrix.py tests/integration/analytics_core/test_shooters_routes.py`
Expected: PASS.

- [ ] **Step 9: Write the failing share and card tests**

In `frontend/src/lib/share.test.ts`, replace

```ts
import { shareElementAsImage } from './share';
```

with

```ts
import { downloadElementAsImage, renderElementToPng, shareElementAsImage } from './share';
```

and append:

```ts
describe('renderElementToPng and downloadElementAsImage', () => {
  it('renders the element to a PNG blob with the share options', async () => {
    const el = document.createElement('div');
    await expect(renderElementToPng(el)).resolves.toBe(png);
    expect(vi.mocked(toBlob).mock.calls[0]?.[0]).toBe(el);
    expect(vi.mocked(toBlob).mock.calls[0]?.[1]?.skipFonts).toBe(true);
  });

  it('downloads and never opens the share sheet, even when sharing is possible', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    const share = vi.spyOn(navigator, 'share');
    const names = captureDownloads();
    await downloadElementAsImage(document.createElement('div'), 'card');
    expect(names).toEqual(['card.png']);
    expect(share).not.toHaveBeenCalled();
  });

  it('throws when nothing could be rendered', async () => {
    vi.mocked(toBlob).mockResolvedValue(null);
    await expect(renderElementToPng(document.createElement('div'))).rejects.toThrow(
      'Could not render the image',
    );
  });
});
```

Create `frontend/src/features/summary/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { summaryFixture } from './mocks';
import { summaryFilename, summaryLines, windowLine } from './format';

describe('summary card lines', () => {
  it('shows every line when every value is set', () => {
    expect(summaryLines(summaryFixture)).toEqual([
      ['Sundays shot', '11', '(1 special shoot)'],
      ['Rounds · Average', '12 · 41.3', ''],
      ['Best round', '46 · Sep 13', ''],
      ['Personal bests', '1', ''],
      ['Trophies earned', '3', 'Iron Streak — Bronze, Events Attended — Gold, …'],
      ['Longest streak', '6 Sundays in a row', ''],
    ]);
  });

  it('hides zero lines and a streak below 2 (D19)', () => {
    const none = { ...summaryFixture, rounds: 0, average: null, best: null, pbs_set: 0 };
    const quiet = { ...none, trophies: 0, trophy_names: [], longest_streak: 1, special_sundays: 0 };
    expect(summaryLines(quiet)).toEqual([['Sundays shot', '11', '']]);
  });

  it('pluralizes special shoots and lists names without "…" when all are named', () => {
    const lines = summaryLines({
      ...summaryFixture,
      special_sundays: 2,
      trophies: 2,
      trophy_names: ['Doubleheader', 'Iron Streak — Bronze'],
    });
    expect(lines[0]?.[2]).toBe('(2 special shoots)');
    expect(lines[4]?.[2]).toBe('Doubleheader, Iron Streak — Bronze');
  });

  it('names the window: a preset with its dates, All "through", a custom window by dates only', () => {
    expect(windowLine('3m', { from: '2026-07-06', to: '2026-09-27' })).toBe(
      'Last 3 months · Jul 6 – Sep 27',
    );
    expect(windowLine('all', { from: null, to: '2026-09-27' })).toBe('All time · through Sep 27, 2026');
    expect(windowLine('2026-01-04..2026-03-29', { from: '2026-01-04', to: '2026-03-29' })).toBe(
      'Jan 4, 2026 – Mar 29, 2026',
    );
  });

  it('builds the image file name; an open start says "all"', () => {
    expect(summaryFilename('Hadley, Ike', '2026-07-06', '2026-09-27')).toBe(
      'sunday-clays-hadley-ike-2026-07-06-to-2026-09-27.png',
    );
    expect(summaryFilename('Hadley, Ike', null, '2026-09-27')).toBe(
      'sunday-clays-hadley-ike-all-to-2026-09-27.png',
    );
  });

  it('uses no banned word in any line', () => {
    for (const text of allStrings(summaryLines(summaryFixture))) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

Create `frontend/src/features/summary/explainers.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { explainers } from './explainers';

describe('summary explainers', () => {
  it('has the summary-card entry with its scope and terms', () => {
    expect(explainers['summary-card']?.scope).toBe('windowed');
    expect(explainers['summary-card']?.terms).toEqual([
      'special-shoot',
      'personal-best',
      'streak',
      'round-types',
      'time-window', // "the chosen time window" matches T5's trigger; T5 and T7 are both wave 3
    ]);
  });

  it('uses no banned word', () => {
    for (const text of allStrings(explainers)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

Create `frontend/src/features/summary/profileSection.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import * as share from '../../lib/share';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { summaryFixture } from './mocks';
import { profileSection } from './profileSection';

const { Component } = profileSection;

function seen(): URL[] {
  const urls: URL[] = [];
  server.use(
    http.get('*/api/shooters/:id/summary', ({ request }) => {
      urls.push(new URL(request.url));
      return HttpResponse.json(summaryFixture);
    }),
  );
  return urls;
}

describe('summary profile section', () => {
  it('is a bare section just above Share', () => {
    expect(profileSection).toMatchObject({ id: 'summary', title: 'Summary card', order: 90, bare: true });
  });

  it('asks for the window, shows the card and downloads it', async () => {
    const urls = seen();
    const download = vi.spyOn(share, 'downloadElementAsImage').mockResolvedValue(undefined);
    const { user } = renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3?w=3m' });
    expect(await screen.findByRole('heading', { name: 'Summary card' })).toBeInTheDocument();
    expect(await screen.findByText('Hadley, Ike')).toBeInTheDocument();
    expect(screen.getByText('All round types · sundayclays.claysmasher.com')).toBeInTheDocument();
    expect(urls[0]?.searchParams.get('to')).toBe('2026-09-27');
    expect(urls[0]?.searchParams.has('from')).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Download image' }));
    expect(download.mock.calls[0]?.[1]).toBe('sunday-clays-hadley-ike-2026-06-28-to-2026-09-27.png');
    expect(screen.getByRole('button', { name: 'Share image' })).toBeInTheDocument();
  });

  it('sends no from for the All window', async () => {
    const urls = seen();
    renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3?w=all' });
    await screen.findByText('Hadley, Ike');
    expect(urls[0]?.searchParams.has('from')).toBe(false);
    expect(screen.getByText('All time · through Sep 27, 2026')).toBeInTheDocument();
  });

  it('shows the empty window with 12M and All, and no image buttons', async () => {
    server.use(
      http.get('*/api/shooters/:id/summary', () =>
        HttpResponse.json({ ...summaryFixture, sundays: 0, special_sundays: 0, rounds: 0 }),
      ),
    );
    renderWithProviders(<Component shooterId={3} />, { route: '/shooters/3' });
    expect(await screen.findByText('No Sundays shot in this window.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Show all time' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Download image' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Share image' })).not.toBeInTheDocument();
  });

  it('renders nothing at all (no heading) for a viewer while off', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    const { container } = renderWithProviders(<Component shooterId={3} />);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });
});
```

The 3M window anchored at the mock `/api/meta`'s `last_score_date` (2026-09-27) starts on 2026-06-28 (`monthsBack`: Jun 27 + 1 day). If the shared meta mock's `last_score_date` differs, use its value in the two date strings.

- [ ] **Step 10: Run them to verify they fail**

Run: `cd frontend && pnpm gen:api && pnpm exec vitest run src/lib/share.test.ts src/features/summary`
Expected: FAIL: `renderElementToPng` is not exported; `./mocks`, `./format`, `./explainers`, `./profileSection` unresolved.

- [ ] **Step 11: Write the share helpers**

In `frontend/src/lib/share.ts`, replace

```ts
export async function shareElementAsImage(
  el: HTMLElement,
  filename: string,
): Promise<ShareOutcome> {
  const name = filename.endsWith('.png') ? filename : `${filename}.png`;
  const blob = await toBlob(el, {
    pixelRatio: 2,
    cacheBust: true,
    filter: keepInImage,
    // html-to-image's own font embedding uses a temporary <base>, which the CSP blocks (see above).
    skipFonts: true,
    fontEmbedCSS: await robotoFontCss(),
    backgroundColor: getComputedStyle(document.body).backgroundColor,
  });
  if (!blob) throw new Error('Could not render the image');
  const file = new File([blob], name, { type: 'image/png' });
```

with

```ts
function pngName(filename: string): string {
  return filename.endsWith('.png') ? filename : `${filename}.png`;
}

/** Renders `el` to a PNG blob (2x, Roboto embedded, `data-share-exclude` left out). */
export async function renderElementToPng(el: HTMLElement): Promise<Blob> {
  const blob = await toBlob(el, {
    pixelRatio: 2,
    cacheBust: true,
    filter: keepInImage,
    // html-to-image's own font embedding uses a temporary <base>, which the CSP blocks (see above).
    skipFonts: true,
    fontEmbedCSS: await robotoFontCss(),
    backgroundColor: getComputedStyle(document.body).backgroundColor,
  });
  if (!blob) throw new Error('Could not render the image');
  return blob;
}

/** Renders `el` and saves it as a file; never opens the share sheet (Plan 19 D20). */
export async function downloadElementAsImage(el: HTMLElement, filename: string): Promise<void> {
  downloadBlob(await renderElementToPng(el), pngName(filename));
}

export async function shareElementAsImage(
  el: HTMLElement,
  filename: string,
): Promise<ShareOutcome> {
  const name = pngName(filename);
  const blob = await renderElementToPng(el);
  const file = new File([blob], name, { type: 'image/png' });
```

Run: `cd frontend && pnpm exec vitest run src/lib/share.test.ts`
Expected: PASS (the existing share tests unchanged).

- [ ] **Step 12: Write the summary feature**

Create `frontend/src/features/summary/api.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import type { WindowRange } from '../../lib/timeWindow';
import type { JsonOf } from '../admin/api';

export type ShooterSummary = JsonOf<paths['/api/shooters/{id}/summary']['get']>;

/** The card's numbers for the header window; `from` is left out for an open start ("All"). */
export function useShooterSummary(id: number, range: WindowRange | null, enabled: boolean) {
  const query = range === null ? null : { ...(range.from === null ? {} : { from: range.from }), to: range.to };
  return useQuery({
    queryKey: ['/api/shooters/{id}/summary', id, query],
    queryFn: () =>
      unwrap(
        api.GET('/api/shooters/{id}/summary', {
          params: { path: { id }, query: query as { from?: string; to: string } },
        }),
      ),
    enabled: enabled && query !== null,
  });
}
```

Create `frontend/src/features/summary/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import type { ShooterSummary } from './api';

export const summaryFixture: ShooterSummary = {
  shooter_id: 3,
  display_name: 'Hadley, Ike',
  from: '2026-06-28',
  to: '2026-09-27',
  sundays: 11,
  special_sundays: 1,
  rounds: 12,
  average: 41.3,
  best: { score: 46, event_date: '2026-09-13' },
  pbs_set: 1,
  trophies: 3,
  trophy_names: ['Iron Streak — Bronze', 'Events Attended — Gold'],
  longest_streak: 6,
};

export const handlers = [
  http.get('*/api/shooters/:id/summary', () => HttpResponse.json(summaryFixture)),
];
```

Create `frontend/src/features/summary/format.ts`:

```ts
import { formatShortDate } from '../../lib/format';
import type { TimeWindow, WindowRange } from '../../lib/timeWindow';
import { windowTagText } from '../../lib/windowText';
import { slugify } from '../share/filenames';
import type { ShooterSummary } from './api';

export type SummaryLine = [label: string, value: string, extra: string];

/** The card's lines; a 0 value or a streak below 2 is left out, never shown as 0 (D19). */
export function summaryLines(s: ShooterSummary): SummaryLine[] {
  const special =
    s.special_sundays === 0
      ? ''
      : `(${String(s.special_sundays)} special shoot${s.special_sundays === 1 ? '' : 's'})`;
  const lines: SummaryLine[] = [['Sundays shot', String(s.sundays), special]];
  if (s.rounds > 0 && s.average !== null) {
    lines.push(['Rounds · Average', `${String(s.rounds)} · ${s.average.toFixed(1)}`, '']);
  }
  if (s.rounds > 0 && s.best !== null) {
    lines.push(['Best round', `${String(s.best.score)} · ${formatShortDate(s.best.event_date)}`, '']);
  }
  if (s.pbs_set > 0) lines.push(['Personal bests', String(s.pbs_set), '']);
  if (s.trophies > 0) {
    const names = s.trophy_names.join(', ');
    lines.push(['Trophies earned', String(s.trophies), s.trophies > s.trophy_names.length ? `${names}, …` : names]);
  }
  if (s.longest_streak >= 2) {
    lines.push(['Longest streak', `${String(s.longest_streak)} Sundays in a row`, '']);
  }
  return lines;
}

/** "Last 3 months · Jul 6 – Sep 27", "All time · through Sep 27, 2026", or a custom window's dates. */
export function windowLine(window: TimeWindow, range: WindowRange): string {
  return windowTagText(window, range);
}

export function summaryFilename(name: string, from: string | null, to: string): string {
  return `sunday-clays-${slugify(name)}-${from ?? 'all'}-to-${to}.png`;
}
```

Create `frontend/src/features/summary/explainers.ts` (copy from spec §3.6.2; `round-types` added, Decision 4):

```ts
import type { Explainer } from '../../components/charts/types';

export const explainers: Record<string, Explainer> = {
  'summary-card': {
    what: "A shareable snapshot of one shooter's Sundays in the chosen time window.",
    computed: [
      'Sundays shot counts every Sunday you came to, special shoots included.',
      'Rounds, average, best round and personal bests use regular rounds only, all round types.',
      'A personal best counts once there are at least 5 earlier rounds.',
      'Longest streak counts only Sundays inside the window.',
    ],
    scope: 'windowed',
    terms: ['special-shoot', 'personal-best', 'streak', 'round-types', 'time-window'],
  },
};
```

Create `frontend/src/features/summary/components/SummaryCard.tsx`:

```tsx
import type { ShooterSummary } from '../api';
import { summaryLines } from '../format';

/** The element rendered to an image (max 480 px). Only positive or neutral facts (R2). */
export function SummaryCard({ summary, windowText }: { summary: ShooterSummary; windowText: string }) {
  return (
    <article className="flex max-w-[480px] flex-col gap-2 rounded-card bg-surface p-4 text-text">
      <p className="text-sm text-accent">Sunday Clays · Tri-County Gun Club</p>
      <h3 className="break-words text-xl font-bold">{summary.display_name}</h3>
      <p className="text-sm text-text-muted">{windowText}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        {summaryLines(summary).map(([label, value, extra]) => (
          <div key={label} className="contents">
            <dt className="text-text-muted">{label}</dt>
            <dd>
              {value}
              {extra !== '' && <span className="ml-2 text-sm text-text-muted">{extra}</span>}
            </dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-text-muted">All round types · sundayclays.claysmasher.com</p>
    </article>
  );
}
```

Create `frontend/src/features/summary/profileSection.tsx`:

```tsx
import { Download } from 'lucide-react';
import { useRef, useState } from 'react';
import { WidenWindowButtons } from '../../components/WidenWindowButtons';
import { AboutBlock } from '../../components/ui/AboutBlock';
import { AdminPreviewBadge } from '../../components/ui/AdminPreviewBadge';
import { Card } from '../../components/ui/Card';
import { useFeature } from '../../lib/features';
import { downloadElementAsImage } from '../../lib/share';
import { useTimeWindow } from '../../lib/timeWindow';
import { ShareCard } from '../share/ShareCard';
import type { ProfileSection } from '../shooters/sections';
import { useShooterSummary } from './api';
import { SummaryCard } from './components/SummaryCard';
import { explainers } from './explainers';
import { summaryFilename, windowLine } from './format';

function SummarySection({ shooterId }: { shooterId: number }) {
  const { visible } = useFeature('summary_card');
  const { window, range, ready } = useTimeWindow();
  const query = useShooterSummary(shooterId, range, visible && ready);
  const cardRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  if (!visible) return null; // a bare section: no title, no gap
  const data = query.data;
  const filename =
    data === undefined || range === null ? '' : summaryFilename(data.display_name, range.from, range.to);
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          Summary card
          <AdminPreviewBadge feature="summary_card" />
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        <AboutBlock explainer={explainers['summary-card']} label="About the summary card" />
        {query.isError ? (
          <p role="alert">Could not load the summary.</p>
        ) : data === undefined || range === null ? (
          <p role="status">Loading the summary…</p>
        ) : data.sundays === 0 ? (
          <div className="flex flex-col gap-2">
            <p>No Sundays shot in this window.</p>
            <WidenWindowButtons />
          </div>
        ) : (
          <>
            <ShareCard filename={filename}>
              <div ref={cardRef}>
                <SummaryCard summary={data} windowText={windowLine(window, range)} />
              </div>
            </ShareCard>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setFailed(false);
                  const el = cardRef.current;
                  if (el !== null) void downloadElementAsImage(el, filename).catch(() => setFailed(true));
                }}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-button border border-outline-variant px-4"
              >
                <Download aria-hidden="true" className="size-4" />
                Download image
              </button>
              <span aria-live="polite" className="text-sm text-text-muted">
                {failed ? 'Could not create the image.' : ''}
              </span>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

/** Plan 19 §3.6.2: a shareable summary for the header window, just above Share (95). */
export const profileSection: ProfileSection = {
  id: 'summary',
  title: 'Summary card',
  order: 90,
  bare: true,
  Component: SummarySection,
};
```

- [ ] **Step 13: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/lib src/features/summary src/features/shooters src/features/share src/features/glossary/explainerLint.test.ts`
Expected: PASS. The profile page tests still pass: the section asks `/api/shooters/:id/summary`, which `features/summary/mocks.ts` answers.

- [ ] **Step 14: Write and run the e2e at both sizes**

Create `frontend/e2e/summary-card.spec.ts`:

```ts
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

const card = (page: import('@playwright/test').Page) =>
  page.getByRole('region', { name: /^Summary card/ });

test('3M shows the card with its window', async ({ page }) => {
  await page.goto('/shooters/3?w=3m');
  await expect(card(page)).toBeVisible();
  await expect(card(page).getByText(/^Last 3 months · /)).toBeVisible();
  await expectNoSideScroll(page);
});

test('All sends no from and says "through"', async ({ page }) => {
  const asked = page.waitForRequest((r) => r.url().includes('/summary?'));
  await page.goto('/shooters/3?w=all');
  expect(new URL((await asked).url()).searchParams.has('from')).toBe(false);
  await expect(card(page).getByText(/^All time · through /)).toBeVisible();
});

test('a custom window updates the dates', async ({ page }) => {
  await page.goto('/shooters/3?w=2025-01-05..2025-03-30');
  await expect(card(page).getByText('Jan 5, 2025 – Mar 30, 2025')).toBeVisible();
});

test('Download image saves a PNG', async ({ page }) => {
  await page.goto('/shooters/3?w=12m');
  await whenSettled(page);
  const download = page.waitForEvent('download');
  await card(page).getByRole('button', { name: 'Download image' }).click();
  expect((await download).suggestedFilename()).toMatch(/^sunday-clays-.*\.png$/);
});

test('an empty window offers 12M and All', async ({ page }) => {
  await page.goto('/shooters/3?w=2010-01-03..2010-02-28');
  await expect(card(page).getByText('No Sundays shot in this window.')).toBeVisible();
  await expect(card(page).getByRole('button', { name: 'Show all time' })).toBeVisible();
});
```

Run (stack project `task19-7`, port 18082): `pnpm exec playwright test summary-card.spec.ts shooters.spec.ts share.spec.ts --project=desktop --project=mobile`.
Expected: PASS.

- [ ] **Step 15: Run the backend and frontend gates, then commit**

```bash
git add backend/src/sunday_clays/analytics/personal_best.py backend/src/sunday_clays/api/routes/events.py \
  backend/src/sunday_clays/analytics/summary.py backend/src/sunday_clays/api/routes/shooters.py \
  backend/tests/unit/analytics/test_shooter_summary.py backend/tests/integration/api/test_shooter_summary_api.py \
  frontend/src/lib/share.ts frontend/src/lib/share.test.ts frontend/src/features/summary frontend/e2e/summary-card.spec.ts
git commit -m "feat(summary): a shareable per-profile summary card for the time window (Plan 19 T7)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 8: Weekly recap (`task/19-8-weekly-recap`, wave 5)

**Files:**
- Create: `backend/src/sunday_clays/api/routes/admin_recap.py`
- Create: `backend/tests/unit/api/test_recap_rules.py`
- Create: `backend/tests/integration/api/test_admin_recap_api.py`
- Modify: `backend/tests/conftest.py` (append `fx_special_admin_client` at the end; T11, same wave, inserts its fixture near the top, so the two hunks merge cleanly)
- Create: `frontend/src/features/admin-recap/{routes.tsx, routes.test.tsx, api.ts, mocks.ts, format.ts, format.test.ts}`
- Create: `frontend/src/features/admin-recap/components/RecapImageCard.tsx`
- Create: `frontend/src/features/admin-recap/pages/{RecapPage.tsx, RecapPage.test.tsx}`
- Modify: `frontend/src/app/navRegistry.test.ts` (`'admin-recap': 935`)
- Create: `frontend/e2e/recap.spec.ts`

**Interfaces:**
- Consumes: T1 `switch_on`; T3 `Settings.public_base_url`; T6 `analytics.club_milestones.club_milestones`; T7 `analytics.summary.trophy_title`, `lib/share.downloadElementAsImage`; T2 `AdminPreviewBadge`, `NavItem.feature`; `api.routes.events.event_notables`; `analytics.achievements.participation.{normalize_label, THREE_BIRD_LABELS}`; `frames.load_calendar`, `load_rounds`, `load_shooters`, `load_special_rounds`; `domain.errors.{NotFoundError, ConflictError}`; `components/ui/{Select, Tabs, Card}`.
- Produces:
  - `GET /api/admin/recap/{date}` → `RecapOut` (fields as spec §3.3.1); 404 `event_not_found`; 409 `recap_not_ready`; 403 for a viewer.
  - Pure helpers in `admin_recap.py`: `podium_of(day_rounds: pd.DataFrame) -> list[PodiumPlaceOut]`, `is_three_bird(label: str | None) -> bool`, `three_bird_counts(award_dates: Sequence[date], day: date) -> tuple[int, int]`.
  - `features/admin-recap/format.ts`: `formatRecap(r: Recap): { text: string; markdown: string }`, `escapeMarkdown(s)`, `recapFilename(date)`.

- [ ] **Step 1: Write the failing recap rule tests**

Create `backend/tests/unit/api/test_recap_rules.py`:

```python
"""Recap rules (Plan 19 §3.3.1, D15): podium ties, the 3-bird counts."""

from datetime import date

import pandas as pd
import pytest

from sunday_clays.api.routes.admin_recap import is_three_bird, podium_of, three_bird_counts


def day(*best: tuple[str, int, int | None]) -> pd.DataFrame:
    """(display_name, score, event_rank) best rounds, plus one non-best round."""
    rows = [
        {"display_name": n, "score": s, "event_rank": r, "is_best_round": True} for n, s, r in best
    ]
    rows.append({"display_name": "Zed, Extra", "score": 10, "event_rank": None, "is_best_round": False})
    return pd.DataFrame(rows)


def places(frame: pd.DataFrame) -> list[tuple[int, bool, int, list[str]]]:
    return [(p.place, p.tied, p.score, p.names) for p in podium_of(frame)]


def test_tied_first_then_third() -> None:
    frame = day(("Stockton, Ethan", 49, 1), ("Finnegan, Stanton", 49, 1), ("Devlin, Sid", 47, 3), ("Kim, Pat", 40, 4))
    assert places(frame) == [
        (1, True, 49, ["Finnegan, Stanton", "Stockton, Ethan"]),
        (3, False, 47, ["Devlin, Sid"]),
    ]


def test_first_then_tied_second() -> None:
    frame = day(("Hadley, Ike", 48, 1), ("Kaplan, Noel", 46, 2), ("Devlin, Sid", 46, 2))
    assert places(frame) == [
        (1, False, 48, ["Hadley, Ike"]),
        (2, True, 46, ["Devlin, Sid", "Kaplan, Noel"]),
    ]


def test_five_tied_for_third_are_all_listed_and_nobody_below() -> None:
    thirds = [(f"Shooter{i}, Test", 44, 3) for i in range(5)]
    frame = day(("A, One", 49, 1), ("B, Two", 47, 2), *thirds, ("C, Low", 40, 8))
    result = places(frame)
    assert [p[0] for p in result] == [1, 2, 3]
    assert len(result[2][3]) == 5 and result[2][1] is True
    assert "C, Low" not in str(result)


def test_one_shooter() -> None:
    assert places(day(("Hadley, Ike", 44, 1))) == [(1, False, 44, ["Hadley, Ike"])]


@pytest.mark.parametrize(
    ("label", "expected"),
    [("3-Bird Shoot", True), ("Three Bird Shoot", True), ("Turkey Shoot", False), (None, False)],
)
def test_is_three_bird(label: str | None, expected: bool) -> None:
    assert is_three_bird(label) is expected


def test_three_bird_counts_first_and_second_shoot() -> None:
    first, second = date(2026, 9, 20), date(2027, 3, 21)
    awarded = [first] * 12 + [second] * 3  # three_bird_shoot is awarded at a shooter's first one
    assert three_bird_counts(awarded, first) == (12, 12)
    assert three_bird_counts(awarded, second) == (3, 15)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/api/test_recap_rules.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'sunday_clays.api.routes.admin_recap'`.

- [ ] **Step 3: Write the recap route**

Create `backend/src/sunday_clays/api/routes/admin_recap.py`:

```python
"""Weekly recap facts for the club email (Plan 19 §3.3.1, D14, D15). Admin only (module prefix).

The server owns the rules (podium ties, the PB rule, first-timers); the SPA owns the wording.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Annotated, Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import text

from sunday_clays.analytics import frames
from sunday_clays.analytics.achievements.participation import THREE_BIRD_LABELS, normalize_label
from sunday_clays.analytics.club_milestones import club_milestones
from sunday_clays.analytics.summary import trophy_title
from sunday_clays.api.routes._convert import opt_int, opt_str, rows
from sunday_clays.api.routes.events import event_notables
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import ConflictError, NotFoundError
from sunday_clays.domain.features import switch_on

router = APIRouter(prefix="/api/admin", tags=["admin"])

THREE_BIRD_CODE = "three_bird_shoot"
PODIUM_PLACES = 3


class PodiumPlaceOut(BaseModel):
    place: Literal[1, 2, 3]
    tied: bool
    score: int
    names: list[str]  # display names, alphabetical


class RecapPbOut(BaseModel):
    display_name: str
    score: int
    previous: int


class RecapTrophiesOut(BaseModel):
    display_name: str
    items: list[str]


class RecapOut(BaseModel):
    event_date: date
    kind: Literal["regular", "special"]
    label: str | None
    target_total: int
    shooters: int
    head_count: int | None
    rounds: int
    podium: list[PodiumPlaceOut]
    pbs: list[RecapPbOut]
    trophies: list[RecapTrophiesOut]
    club_milestones: list[str]
    first_timers: list[str]
    three_bird_new: int | None
    three_bird_holders: int | None
    top_score: int | None
    link: str


def podium_of(day_rounds: pd.DataFrame) -> list[PodiumPlaceOut]:
    """Best rounds with event_rank <= 3 (ties share a rank, so "Tied 1st" is followed by 3rd)."""
    best = day_rounds.loc[day_rounds["is_best_round"].eq(True) & day_rounds["event_rank"].notna()]
    by_place: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for r in rows(best):
        place = int(r["event_rank"])
        if place <= PODIUM_PLACES:
            by_place[place].append((str(r["display_name"]), int(r["score"])))
    return [
        PodiumPlaceOut(
            place=place,  # type: ignore[arg-type]
            tied=len(entries) > 1,
            score=entries[0][1],
            names=sorted(name for name, _ in entries),
        )
        for place, entries in sorted(by_place.items())
    ]


def is_three_bird(label: str | None) -> bool:
    return label is not None and normalize_label(label) in THREE_BIRD_LABELS


def three_bird_counts(award_dates: Sequence[date], day: date) -> tuple[int, int]:
    """(first-time earners on `day`, everyone holding it on `day`)."""
    return sum(d == day for d in award_dates), sum(d <= day for d in award_dates)


@router.get("/recap/{date}")
def get_recap(
    event_date: Annotated[date, Path(alias="date")],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecapOut:
    calendar = frames.load_calendar(session)
    match = calendar.loc[calendar["event_date"] == event_date]
    if match.empty:
        raise NotFoundError("event_not_found", f"No event on {event_date.isoformat()}")
    event = rows(match)[0]
    if not bool(event["results_complete"]):
        raise ConflictError("recap_not_ready", "This Sunday has no full results yet.")
    special = event["kind"] == frames.EVENT_KIND_SPECIAL
    label = opt_str(event["label"])
    rounds = frames.load_rounds(session)
    shooters = frames.load_shooters(session)
    notables = event_notables(rounds, shooters, event_date)
    earlier = rounds.loc[rounds["event_date"] < event_date]
    pbs = [
        RecapPbOut(
            display_name=n.display_name,
            score=int(n.value or 0),
            previous=int(earlier.loc[earlier["shooter_id"] == n.shooter_id, "score"].max()),
        )
        for n in notables
        if n.kind == "pb"
    ]
    awards = session.execute(
        text(
            "SELECT p.display_name, a.code FROM achievements_awarded a "
            "JOIN shooter_profiles p ON p.shooter_id = a.shooter_id "
            "WHERE a.event_date = :d ORDER BY p.display_name, a.code"
        ),
        {"d": event_date},
    ).all()
    items: dict[str, list[str]] = defaultdict(list)
    for name, code in awards:
        title = trophy_title(str(code)) if code != THREE_BIRD_CODE else None
        if title is not None:
            items[str(name)].append(title)
    milestones = (
        [c.label for c in club_milestones(session, event_date).milestones if c.event_date == event_date]
        if switch_on(session, settings, "club_milestones")
        else []
    )
    new = holders = None
    if special and is_three_bird(label):
        dates = list(
            session.execute(
                text("SELECT event_date FROM achievements_awarded WHERE code = :c"),
                {"c": THREE_BIRD_CODE},
            ).scalars()
        )
        new, holders = three_bird_counts(dates, event_date)
    top_score = None
    if special:
        day_special = frames.load_special_rounds(session)
        scores = day_special.loc[day_special["event_date"] == event_date, "score"]
        top_score = None if scores.empty else int(scores.max())
    return RecapOut(
        event_date=event_date,
        kind="special" if special else "regular",
        label=label,
        target_total=int(event["target_total"]),
        shooters=int(event["n_shooters"]),
        head_count=opt_int(event["head_count"]),
        rounds=int(event["n_rounds"]),
        podium=[] if special else podium_of(rounds.loc[rounds["event_date"] == event_date]),
        pbs=[] if special else pbs,
        trophies=[RecapTrophiesOut(display_name=n, items=i) for n, i in items.items()],
        club_milestones=milestones,
        first_timers=[n.display_name for n in notables if n.kind == "first_timer"],
        three_bird_new=new,
        three_bird_holders=holders,
        top_score=top_score,
        link=f"{settings.public_base_url}/l/events/{event_date.isoformat()}",
    )
```

`event_notables` is reused, not copied: its PB rule (`PB_MIN_PRIOR_ROUNDS`, a strictly higher best round) and its first-timers (`first_event == date`, not `left_censored`) are the recap's rules. The previous best is the shooter's highest earlier regular score, which is what the notable's "(was N)" says.

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/api/test_recap_rules.py`
Expected: PASS.

- [ ] **Step 5: Write the failing API tests**

Create `backend/tests/integration/api/test_admin_recap_api.py`:

```python
"""GET /api/admin/recap/{date} (Plan 19 §3.3.1, §5.2)."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from sunday_clays.analytics import club_milestones as cm
from sunday_clays.analytics.achievements.registry import trophy
from sunday_clays.analytics.cache import clear_cache
from sunday_clays.analytics.summary import LEFT_OUT_TROPHY_CODES
from sunday_clays.config import get_settings
from sunday_clays.domain.features import set_switch
from sunday_clays.models import Event

LATEST = "2026-09-27"
SPECIAL = "2026-09-20"


def test_regular_recap_agrees_with_the_sunday_page(fx_admin_client: TestClient) -> None:
    recap = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()
    event = fx_admin_client.get(f"/api/events/{LATEST}").json()
    podium_names = sorted(n for place in recap["podium"] for n in place["names"])
    page_names = sorted(
        r["display_name"]
        for r in event["results"]
        if r["is_best_round"] and r["event_rank"] is not None and r["event_rank"] <= 3
    )
    assert podium_names == page_names
    page_pbs = {n["display_name"] for n in event["notables"] if n["kind"] == "pb"}
    assert {p["display_name"] for p in recap["pbs"]} == page_pbs
    for pb in recap["pbs"]:
        assert pb["score"] > pb["previous"]
    assert recap["kind"] == "regular" and recap["target_total"] == 50
    assert recap["link"] == f"https://sundayclays.claysmasher.com/l/events/{LATEST}"
    assert recap["three_bird_new"] is None and recap["top_score"] is None


def test_trophies_are_that_sundays_awards_minus_the_d14_four(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    """Counted against achievements_awarded, not against names, so removing the filter fails.
    Two D14 trophies are added on LATEST (one per registry category, competition and stations), so
    the test does not depend on what the fixture happens to award that day."""
    shooter = fx_session.execute(
        text("SELECT shooter_id FROM achievements_awarded WHERE event_date = :d LIMIT 1"),
        {"d": LATEST},
    ).scalar_one()
    for code in ("first_win", "station_top_gun"):
        fx_session.execute(
            text(
                "INSERT INTO achievements_awarded (shooter_id, code, event_date) VALUES (:s, :c, :d)"
                " ON CONFLICT DO NOTHING"
            ),
            {"s": shooter, "c": code, "d": LATEST},
        )
    codes = fx_session.execute(
        text("SELECT code FROM achievements_awarded WHERE event_date = :d"), {"d": LATEST}
    ).scalars().all()
    left_out = [c for c in codes if c in LEFT_OUT_TROPHY_CODES]
    assert {"first_win", "station_top_gun"} <= set(left_out)
    kept = [
        c
        for c in codes
        if c not in LEFT_OUT_TROPHY_CODES and c != "three_bird_shoot" and trophy(c) is not None
    ]
    recap = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()
    items = [i for t in recap["trophies"] for i in t["items"]]
    assert len(items) == len(kept)
    for code in left_out:
        assert trophy(code) is not None
        assert not any(i.startswith(trophy(code).achievement.name) for i in items)  # type: ignore[union-attr]


def test_milestones_only_when_their_switch_is_on(
    fx_admin_client: TestClient, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thresholds are patched so one crossing lands on LATEST and one on an earlier Sunday.
    Kills: dropping the switch check (off must be []), dropping the date filter (the earlier
    crossing would show), and never calling club_milestones (on must be the exact label)."""
    series = cm.club_milestones(fx_session, date.fromisoformat(LATEST)).series
    assert series[-1].event_date == date.fromisoformat(LATEST)
    crossed = series[-1].rounds
    assert series[-2].rounds < crossed  # LATEST had rounds, so this threshold is crossed on it
    thresholds = {metric: () for metric in cm.METRICS}
    thresholds["rounds"] = (series[0].rounds, crossed)  # the first: crossed on the first Sunday
    monkeypatch.setattr(cm, "THRESHOLDS", thresholds)
    clear_cache()
    assert fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["club_milestones"] == []
    set_switch(fx_session, get_settings(), "club_milestones", True)
    clear_cache()
    on = fx_admin_client.get(f"/api/admin/recap/{LATEST}").json()["club_milestones"]
    assert on == [cm.milestone_label("rounds", crossed)]


def test_special_recap(fx_special_admin_client: TestClient, fx_special_session: Session) -> None:
    recap = fx_special_admin_client.get(f"/api/admin/recap/{SPECIAL}").json()
    awarded = fx_special_session.execute(
        text("SELECT count(*) FROM achievements_awarded WHERE code = 'three_bird_shoot' AND event_date = :d"),
        {"d": SPECIAL},
    ).scalar_one()
    held = fx_special_session.execute(
        text("SELECT count(*) FROM achievements_awarded WHERE code = 'three_bird_shoot' AND event_date <= :d"),
        {"d": SPECIAL},
    ).scalar_one()
    assert (recap["kind"], recap["label"], recap["target_total"]) == ("special", "3-Bird Shoot", 60)
    assert recap["three_bird_new"] == awarded and recap["three_bird_holders"] == held
    assert recap["podium"] == [] and recap["pbs"] == []
    assert recap["top_score"] == 55
    assert "Kim, Pat" in recap["first_timers"]


def test_a_turkey_shoot_has_no_three_bird_counts(
    fx_special_admin_client: TestClient, fx_special_session: Session
) -> None:
    fx_special_session.execute(
        update(Event).where(Event.event_date == SPECIAL).values(label="Turkey Shoot")
    )
    clear_cache()
    recap = fx_special_admin_client.get(f"/api/admin/recap/{SPECIAL}").json()
    assert recap["three_bird_new"] is None and recap["three_bird_holders"] is None


def test_errors(fx_admin_client: TestClient, fx_viewer_client: TestClient, fx_session: Session) -> None:
    missing = fx_admin_client.get("/api/admin/recap/1999-01-03")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "event_not_found"
    fx_session.execute(update(Event).where(Event.event_date == LATEST).values(results_complete=False))
    clear_cache()
    not_ready = fx_admin_client.get(f"/api/admin/recap/{LATEST}")
    assert not_ready.status_code == 409
    assert not_ready.json()["error"] == {
        "code": "recap_not_ready",
        "message": "This Sunday has no full results yet.",
    }
    assert fx_viewer_client.get(f"/api/admin/recap/{LATEST}").status_code == 403

```

Add the admin twin of `fx_special_viewer_client` to `backend/tests/conftest.py`, at the end of the file:

```python
@pytest.fixture
def fx_special_admin_client(
    fx_special_client: TestClient, auth_env: Settings
) -> Iterator[TestClient]:
    """Plan 19 T8: an admin over the special-Sunday world."""
    logged_in = _logged_in(_use_env_settings(fx_special_client), "admin")
    yield logged_in
    logged_in.close()
```

- [ ] **Step 6: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_admin_recap_api.py tests/integration/api/test_route_auth_matrix.py`
Expected: PASS. (RED evidence for Steps 3–6 is Step 2's run; reviewers run this file on the base to see it fail with 404 on every request.)

- [ ] **Step 7: Write the failing format goldens**

Run `cd frontend && pnpm gen:api`.

Create `frontend/src/features/admin-recap/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import type { Recap } from './api';

export const regularRecap: Recap = {
  event_date: '2026-09-27',
  kind: 'regular',
  label: null,
  target_total: 50,
  shooters: 23,
  head_count: 24,
  rounds: 27,
  podium: [
    { place: 1, tied: true, score: 49, names: ['Finnegan, Stanton', 'Stockton, Ethan'] },
    { place: 3, tied: false, score: 47, names: ['Devlin, Sid'] },
  ],
  pbs: [{ display_name: 'Kaplan, Noel', score: 45, previous: 43 }],
  trophies: [{ display_name: 'Abernathy, Preston', items: ['Events Attended — Silver'] }],
  club_milestones: ['350,000 clays thrown'],
  first_timers: ['Kim, Pat'],
  three_bird_new: null,
  three_bird_holders: null,
  top_score: null,
  link: 'https://sundayclays.claysmasher.com/l/events/2026-09-27',
};

export const specialRecap: Recap = {
  event_date: '2026-09-20',
  kind: 'special',
  label: '3-Bird Shoot',
  target_total: 60,
  shooters: 40,
  head_count: null,
  rounds: 40,
  podium: [],
  pbs: [],
  trophies: [],
  club_milestones: [],
  first_timers: ['Kim, Pat'],
  three_bird_new: 12,
  three_bird_holders: 58,
  top_score: 55,
  link: 'https://sundayclays.claysmasher.com/l/events/2026-09-20',
};

export const handlers = [
  http.get('*/api/admin/recap/:date', ({ params }) =>
    HttpResponse.json(params.date === '2026-09-20' ? specialRecap : regularRecap),
  ),
];
```

Create `frontend/src/features/admin-recap/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { escapeMarkdown, formatRecap, recapFilename } from './format';
import { regularRecap, specialRecap } from './mocks';

const REGULAR_TEXT = `Sunday Clays · Sunday, September 27, 2026

Turnout: 24 came out and 27 rounds were shot.

Podium (best round of the day)
Tied 1st: Finnegan, Stanton and Stockton, Ethan — 49
3rd: Devlin, Sid — 47

New personal bests
- Kaplan, Noel: 45 (was 43)

Milestones and trophies
- Abernathy, Preston: Events Attended — Silver
- Club: 350,000 clays thrown

Welcome to our first-timers
- Kim, Pat

See every score: https://sundayclays.claysmasher.com/l/events/2026-09-27`;

const REGULAR_MARKDOWN = `**Sunday Clays · Sunday, September 27, 2026**

Turnout: 24 came out and 27 rounds were shot.

**Podium (best round of the day)**
- Tied 1st: Finnegan, Stanton and Stockton, Ethan — 49
- 3rd: Devlin, Sid — 47

**New personal bests**
- Kaplan, Noel: 45 (was 43)

**Milestones and trophies**
- Abernathy, Preston: Events Attended — Silver
- Club: 350,000 clays thrown

**Welcome to our first-timers**
- Kim, Pat

[See every score](https://sundayclays.claysmasher.com/l/events/2026-09-27)`;

const SPECIAL_TEXT = `Sunday Clays · Sunday, September 20, 2026
3-Bird Shoot (special shoot, 60 targets)

40 shooters came out.
3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.
Top score: 55 of 60.

Welcome to our first-timers
- Kim, Pat

See every score: https://sundayclays.claysmasher.com/l/events/2026-09-20`;

describe('recap formatting', () => {
  it('regular, plain text', () => expect(formatRecap(regularRecap).text).toBe(REGULAR_TEXT));
  it('regular, Markdown', () => expect(formatRecap(regularRecap).markdown).toBe(REGULAR_MARKDOWN));
  it('special, plain text', () => expect(formatRecap(specialRecap).text).toBe(SPECIAL_TEXT));

  it('a later 3-bird shoot where nobody is new, and the first one on record', () => {
    expect(formatRecap({ ...specialRecap, three_bird_new: 0 }).text).toContain(
      '3-Bird Shoot trophy: 58 shooters hold it now.',
    );
    expect(formatRecap({ ...specialRecap, three_bird_new: 40, three_bird_holders: 40 }).text).toContain(
      '3-Bird Shoot trophy: 40 shooters earned it today.',
    );
    expect(formatRecap({ ...specialRecap, three_bird_new: 1, three_bird_holders: 1 }).text).toContain(
      '3-Bird Shoot trophy: 1 shooter earned it today.',
    );
  });

  it('a Turkey Shoot has no trophy line and is otherwise unchanged', () => {
    const turkey = { ...specialRecap, label: 'Turkey Shoot', three_bird_new: null, three_bird_holders: null };
    expect(formatRecap(turkey).text).toBe(
      SPECIAL_TEXT.replace('3-Bird Shoot (special', 'Turkey Shoot (special').replace(
        '3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.\n',
        '',
      ),
    );
  });

  it('omits empty sections with their headings, and uses the shooter count without a head count', () => {
    const bare = {
      ...regularRecap,
      head_count: null,
      pbs: [],
      trophies: [],
      club_milestones: [],
      first_timers: [],
    };
    const text = formatRecap(bare).text;
    expect(text).toContain('Turnout: 23 shooters and 27 rounds were shot.');
    for (const heading of ['New personal bests', 'Milestones and trophies', 'Welcome to our first-timers']) {
      expect(text).not.toContain(heading);
    }
  });

  it('one shooter, and five tied for third', () => {
    const one = { ...regularRecap, podium: [{ place: 1 as const, tied: false, score: 44, names: ['Hadley, Ike'] }] };
    expect(formatRecap(one).text).toContain('Podium (best round of the day)\n1st: Hadley, Ike — 44\n');
    const five = ['A, One', 'B, Two', 'C, Three', 'D, Four', 'E, Five'];
    const tied = { ...regularRecap, podium: [{ place: 3 as const, tied: true, score: 44, names: five }] };
    expect(formatRecap(tied).text).toContain(
      'Tied 3rd: A, One, B, Two, C, Three, D, Four and E, Five — 44',
    );
  });

  it('escapes Markdown characters in a label', () => {
    expect(escapeMarkdown('*Big* [shoot]_x')).toBe('\\*Big\\* \\[shoot\\]\\_x');
    const odd = { ...specialRecap, label: '*Big* Shoot', three_bird_new: null, three_bird_holders: null };
    expect(formatRecap(odd).markdown).toContain('\\*Big\\* Shoot (special shoot, 60 targets)');
  });

  it('names the image file by date', () => {
    expect(recapFilename('2026-09-27')).toBe('sunday-clays-recap-2026-09-27.png');
  });

  it('uses no banned word in any golden', () => {
    const outputs = [regularRecap, specialRecap].flatMap((r) => Object.values(formatRecap(r)));
    for (const text of allStrings(outputs)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

- [ ] **Step 8: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/admin-recap/format.test.ts`
Expected: FAIL, unresolved `./api`/`./format`.

- [ ] **Step 9: Write the API types and the formatter**

Create `frontend/src/features/admin-recap/api.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import type { paths } from '../../api/schema';
import type { JsonOf } from '../admin/api';

export type Recap = JsonOf<paths['/api/admin/recap/{date}']['get']>;

export function useRecap(date: string | null) {
  return useQuery({
    queryKey: ['/api/admin/recap/{date}', date],
    queryFn: () => unwrap(api.GET('/api/admin/recap/{date}', { params: { path: { date: date ?? '' } } })),
    enabled: date !== null,
  });
}
```

Create `frontend/src/features/admin-recap/format.ts`:

```ts
import { ordinal } from '../home/format';
import type { Recap } from './api';

const LONG = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

/** Sunday, September 27, 2026 */
function longDay(iso: string): string {
  return LONG.format(new Date(`${iso}T00:00:00Z`));
}

/** "A", "A and B", "A, B and C" */
function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names.at(-1) ?? ''}`;
}

function shooters(n: number): string {
  return n === 1 ? '1 shooter' : `${String(n)} shooters`;
}

export function escapeMarkdown(text: string): string {
  return text.replace(/([*_[\]])/g, '\\$1');
}

export function recapFilename(date: string): string {
  return `sunday-clays-recap-${date}.png`;
}

interface Section {
  heading: string;
  lines: string[];
  /** Plain text writes the lines without "- " (the podium); Markdown always lists them. */
  plainBullets: boolean;
}

function threeBirdLine(r: Recap): string | null {
  const holders = r.three_bird_holders;
  const fresh = r.three_bird_new;
  if (holders === null || holders === 0 || fresh === null) return null;
  if (fresh === holders) return `3-Bird Shoot trophy: ${shooters(holders)} earned it today.`;
  if (fresh === 0) return `3-Bird Shoot trophy: ${shooters(holders)} hold it now.`;
  return `3-Bird Shoot trophy: ${String(fresh)} earned it for the first time today. ${shooters(holders)} hold it now.`;
}

function rounds(n: number): string {
  return n === 1 ? '1 round was' : `${String(n)} rounds were`;
}

/** Plain text and Markdown of one Sunday's recap (Plan 19 §3.3.3). Names are only podium, PBs,
 * trophies and first-timers: positive or neutral facts (R2). */
export function formatRecap(r: Recap): { text: string; markdown: string } {
  const special = r.kind === 'special';
  const intro: string[] = [];
  const md = (s: string) => escapeMarkdown(s);
  const sections: Section[] = [];
  if (special) {
    const count = r.head_count ?? r.shooters;
    intro.push(`${shooters(count)} came out.`);
    const trophy = threeBirdLine(r);
    if (trophy !== null) intro.push(trophy);
    if (r.top_score !== null) intro.push(`Top score: ${String(r.top_score)} of ${String(r.target_total)}.`);
  } else {
    const who = r.head_count === null ? shooters(r.shooters) : `${String(r.head_count)} came out`;
    intro.push(`Turnout: ${who} and ${rounds(r.rounds)} shot.`);
    if (r.podium.length > 0) {
      sections.push({
        heading: 'Podium (best round of the day)',
        plainBullets: false,
        lines: r.podium.map(
          (p) => `${p.tied ? 'Tied ' : ''}${ordinal(p.place)}: ${joinNames(p.names)} — ${String(p.score)}`,
        ),
      });
    }
    if (r.pbs.length > 0) {
      sections.push({
        heading: 'New personal bests',
        plainBullets: true,
        lines: r.pbs.map((p) => `${p.display_name}: ${String(p.score)} (was ${String(p.previous)})`),
      });
    }
  }
  const trophyLines = [
    ...r.trophies.map((t) => `${t.display_name}: ${t.items.join(', ')}`),
    ...r.club_milestones.map((m) => `Club: ${m}`),
  ];
  if (trophyLines.length > 0) {
    sections.push({ heading: 'Milestones and trophies', plainBullets: true, lines: trophyLines });
  }
  if (r.first_timers.length > 0) {
    sections.push({ heading: 'Welcome to our first-timers', plainBullets: true, lines: [...r.first_timers] });
  }
  const title = `Sunday Clays · ${longDay(r.event_date)}`;
  const labelLine =
    special && r.label !== null ? `${r.label} (special shoot, ${String(r.target_total)} targets)` : null;

  const text = [
    [title, ...(labelLine === null ? [] : [labelLine])].join('\n'),
    intro.join('\n'),
    ...sections.map((s) => [s.heading, ...s.lines.map((l) => (s.plainBullets ? `- ${l}` : l))].join('\n')),
    `See every score: ${r.link}`,
  ].join('\n\n');

  const markdown = [
    [`**${md(title)}**`, ...(labelLine === null ? [] : [md(labelLine)])].join('\n'),
    intro.map(md).join('\n'),
    ...sections.map((s) => [`**${md(s.heading)}**`, ...s.lines.map((l) => `- ${md(l)}`)].join('\n')),
    `[See every score](${r.link})`,
  ].join('\n\n');

  return { text, markdown };
}
```

Check `ordinal` in `features/home/format.ts` returns "1st", "2nd", "3rd" (it does). Note: plain-text podium lines have no "- " (spec golden), Markdown lists them.

- [ ] **Step 10: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/admin-recap/format.test.ts`
Expected: PASS. Any golden mismatch is fixed in `format.ts`, never in the golden (the goldens are the spec's copy).

- [ ] **Step 11: Write the failing page tests**

Create `frontend/src/features/admin-recap/pages/RecapPage.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import * as share from '../../../lib/share';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { RecapPage } from './RecapPage';

describe('RecapPage', () => {
  it('defaults to the latest held Sunday from the data and keeps it in ?date=', async () => {
    const { router } = renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    const box = await screen.findByRole('textbox', { name: 'Recap (plain text)' });
    expect((box as HTMLTextAreaElement).value).toMatch(/^Sunday Clays · Sunday, /);
    expect(router.state.location.search).toBe('');
    expect(screen.getByRole('combobox', { name: 'Sunday' })).toHaveValue(
      (screen.getAllByRole('option')[0] as HTMLOptionElement).value,
    );
  });

  it('switches to Markdown and copies it', async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: write }, configurable: true });
    const { user } = renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2026-09-27' });
    await user.click(await screen.findByRole('tab', { name: 'Markdown' }));
    await user.click(screen.getByRole('button', { name: 'Copy Markdown' }));
    expect(write.mock.calls[0]?.[0]).toMatch(/^\*\*Sunday Clays · /);
    expect(await screen.findByText('Copied.')).toBeInTheDocument();
  });

  it('falls back to selecting the text when the clipboard API fails', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('no')) },
      configurable: true,
    });
    const exec = vi.fn().mockReturnValue(false);
    Object.defineProperty(document, 'execCommand', { value: exec, configurable: true });
    const { user } = renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2026-09-27' });
    await user.click(await screen.findByRole('button', { name: 'Copy text' }));
    expect(exec).toHaveBeenCalledWith('copy');
    expect(
      await screen.findByText('Could not copy. Select the text and copy it by hand.'),
    ).toBeInTheDocument();
  });

  it('downloads the image card with the dated file name', async () => {
    const download = vi.spyOn(share, 'downloadElementAsImage').mockResolvedValue(undefined);
    const { user } = renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap?date=2026-09-27' });
    await user.click(await screen.findByRole('button', { name: 'Download image' }));
    expect(download.mock.calls[0]?.[1]).toBe('sunday-clays-recap-2026-09-27.png');
    expect(await screen.findByText('Image ready.')).toBeInTheDocument();
  });

  it('shows the badge while the switch is off', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
    renderWithProviders(<RecapPage />, { role: 'admin', route: '/admin/recap' });
    expect(await screen.findByText('Admin preview')).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/admin-recap/routes.test.tsx`:

```tsx
import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('admin-recap routes', () => {
  it('adds an admin-only Recap nav item at 935, named for its switch', () => {
    expect(
      nav.map(({ label, path, order, adminOnly, feature }) => ({ label, path, order, adminOnly, feature })),
    ).toEqual([
      { label: 'Recap', path: '/admin/recap', order: 935, adminOnly: true, feature: 'weekly_recap' },
    ]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });
});
```

In `frontend/src/app/navRegistry.test.ts`, replace

```ts
  'admin-analytics': 930,
  'admin-features': 940,
```

with

```ts
  'admin-analytics': 930,
  'admin-recap': 935,
  'admin-features': 940,
```

- [ ] **Step 12: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/admin-recap src/app/navRegistry.test.ts`
Expected: FAIL, unresolved `./RecapPage` and `./routes`.

- [ ] **Step 13: Write the page, the image card and the route**

Create `frontend/src/features/admin-recap/components/RecapImageCard.tsx`:

```tsx
import type { Recap } from '../api';
import { formatRecap } from '../format';

/** The recap in the app's card style (600 px), rendered on screen as the image preview. */
export function RecapImageCard({ recap }: { recap: Recap }) {
  const [title, ...rest] = formatRecap(recap).text.split('\n\n');
  return (
    <article className="flex w-[600px] max-w-full flex-col gap-3 rounded-card bg-surface p-5 text-text">
      <h2 className="text-lg font-bold whitespace-pre-line">{title}</h2>
      {rest.map((block) => (
        <p key={block} className="text-sm whitespace-pre-line">
          {block}
        </p>
      ))}
    </article>
  );
}
```

Create `frontend/src/features/admin-recap/pages/RecapPage.tsx`:

```tsx
import { useMemo, useRef, useState } from 'react';
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { Select } from '../../../components/ui/Select';
import { Tabs } from '../../../components/ui/Tabs';
import { downloadElementAsImage } from '../../../lib/share';
import { isoDateCodec, useUrlState } from '../../../lib/useUrlState';
import { useAllSundays } from '../../events/api';
import { formatDay } from '../../home/format';
import { useRecap } from '../api';
import { RecapImageCard } from '../components/RecapImageCard';
import { formatRecap, recapFilename } from '../format';

type Tab = 'text' | 'markdown';
const TABS = [
  { value: 'text', label: 'Plain text' },
  { value: 'markdown', label: 'Markdown' },
] as const;
const BUTTON =
  'inline-flex min-h-11 items-center justify-center rounded-button border border-outline-variant px-4 text-sm';

async function copy(text: string, area: HTMLTextAreaElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    area?.select();
    return document.execCommand('copy');
  }
}

/** Admin tool (Plan 19 §3.3.2): one Sunday as paste-ready text, Markdown and an image. */
export function RecapPage() {
  const sundays = useAllSundays();
  const held = useMemo(
    () =>
      (sundays.data ?? [])
        .filter((e) => e.results_complete)
        .sort((a, b) => b.event_date.localeCompare(a.event_date)),
    [sundays.data],
  );
  const [chosen, setChosen] = useUrlState<string | null>('date', isoDateCodec, null);
  const date = chosen ?? held[0]?.event_date ?? null; // a date from the data, never "today" (D26)
  const recap = useRecap(date);
  const [tab, setTab] = useState<Tab>('text');
  const [message, setMessage] = useState('');
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const formatted = recap.data === undefined ? null : formatRecap(recap.data);
  const shown = formatted === null ? '' : tab === 'text' ? formatted.text : formatted.markdown;

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-medium">Weekly recap</h1>
        <AdminPreviewBadge feature="weekly_recap" />
      </header>
      {held.length > 0 && date !== null && (
        <Select
          label="Sunday"
          value={date}
          onChange={(value) => setChosen(value)}
          options={held.map((e) => ({
            value: e.event_date,
            label: e.kind === 'special' && e.label ? `${formatDay(e.event_date)} — ${e.label}` : formatDay(e.event_date),
          }))}
        />
      )}
      {recap.isError ? (
        <p role="alert">Could not build the recap for this Sunday.</p>
      ) : formatted === null || recap.data === undefined ? (
        <p role="status">Loading the recap…</p>
      ) : (
        <>
          <Tabs label="Format" tabs={TABS} value={tab} onChange={(next) => setTab(next)} />
          <textarea
            ref={areaRef}
            readOnly
            aria-label={tab === 'text' ? 'Recap (plain text)' : 'Recap (Markdown)'}
            value={shown}
            rows={shown.split('\n').length + 1}
            className="w-full rounded-card border border-outline-variant bg-surface p-3 font-mono text-sm text-text"
          />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className={BUTTON}
              onClick={() =>
                void copy(shown, areaRef.current).then((ok) =>
                  setMessage(ok ? 'Copied.' : 'Could not copy. Select the text and copy it by hand.'),
                )
              }
            >
              {tab === 'text' ? 'Copy text' : 'Copy Markdown'}
            </button>
            <button
              type="button"
              className={BUTTON}
              onClick={() => {
                const el = cardRef.current;
                if (el === null || date === null) return;
                void downloadElementAsImage(el, recapFilename(date)).then(
                  () => setMessage('Image ready.'),
                  () => setMessage('Could not create the image.'),
                );
              }}
            >
              Download image
            </button>
            <span aria-live="polite" className="text-sm text-text-muted">
              {message}
            </span>
          </div>
          <div ref={cardRef} className="overflow-x-auto">
            <RecapImageCard recap={recap.data} />
          </div>
        </>
      )}
    </div>
  );
}
```

`Select` renders a native `<select>` labelled "Sunday" (role `combobox`); `Tabs` renders `role="tab"` buttons. If `Tabs` needs `aria-controls`, it handles it itself. `useAllSundays` (from `features/events/api`) asks `GET /api/events` with the round-type filter, which is empty on this page.

Create `frontend/src/features/admin-recap/routes.tsx`:

```tsx
import { Mail } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { NO_FILTERS } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

export const routes: RouteObject[] = [
  {
    path: '/admin/recap',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { RecapPage } = await import('./pages/RecapPage');
      return {
        element: (
          <RequireRole role="admin">
            <RecapPage />
          </RequireRole>
        ),
      };
    },
  },
];

// Admins always see it (admin preview while weekly_recap is off); viewers never do.
export const nav: NavItem[] = [
  { label: 'Recap', path: '/admin/recap', icon: Mail, order: 935, adminOnly: true, feature: 'weekly_recap' },
];
```

- [ ] **Step 14: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/admin-recap src/app`
Expected: PASS.

- [ ] **Step 15: Write and run the e2e at both sizes**

Create `frontend/e2e/recap.spec.ts`:

```ts
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll } from './layout';

test.use({ storageState: ADMIN_STATE });

test('the recap defaults to the latest Sunday and copies and downloads', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/admin/recap');
  await expect(page.getByRole('heading', { level: 1, name: /^Weekly recap/ })).toBeVisible();
  const text = page.getByRole('textbox', { name: 'Recap (plain text)' });
  await expect(text).toHaveValue(/^Sunday Clays · Sunday, September 27, 2026/);
  await expect(text).toHaveValue(/Podium/);
  await page.getByRole('button', { name: 'Copy text' }).click();
  await expect(page.getByText('Copied.')).toBeVisible();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied.startsWith('Sunday Clays · Sunday, September 27, 2026')).toBe(true);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download image' }).click();
  expect((await download).suggestedFilename()).toBe('sunday-clays-recap-2026-09-27.png');
  await expectNoSideScroll(page);
});
```

Run (project `task19-8`, port 18080): `pnpm exec playwright test recap.spec.ts --project=desktop --project=mobile`.
Expected: PASS.

- [ ] **Step 16: Run the gates, then commit**

```bash
git add backend/src/sunday_clays/api/routes/admin_recap.py backend/tests/unit/api/test_recap_rules.py \
  backend/tests/integration/api/test_admin_recap_api.py backend/tests/conftest.py frontend/src/features/admin-recap \
  frontend/src/app/navRegistry.test.ts frontend/e2e/recap.spec.ts
git commit -m "feat(recap): the weekly recap as text, Markdown and an image (Plan 19 T8)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 9: PWA — Add to Home Screen (`task/19-9-pwa`, wave 4)

**What the shell-upgrade e2e can and cannot do (Decision 16).** §5.3 asks for a test that serves "a second build's files" to an open v1 tab. The e2e job has one build, and Playwright's `page.route` does not see requests a service worker answers. So the upgrade is pinned in two halves: Vitest proves the `activate` rule (`cachesToDelete` keeps the current and the newest previous cache) and the emitted worker's wiring; the e2e proves (a) after a load there is one `sc-shell-*` cache holding `/__sc-created` and no `/api/` URL, and (b) a lazy chunk that fails to load once makes the page reload once onto a working shell (`lib/chunkReload.ts`), in a context with service workers blocked so `page.route` can fail the chunk.

**Files:**
- Create: `frontend/public/manifest.webmanifest`
- Modify: `frontend/index.html` (two static `<link>` tags)
- Create: `frontend/src/build/pwaShell.ts`, `frontend/src/build/pwaShell.test.ts`
- Modify: `frontend/vite.config.ts` (add the plugin)
- Create: `frontend/src/lib/chunkReload.ts`, `frontend/src/lib/chunkReload.test.ts`
- Modify: `frontend/src/main.tsx` (one import)
- Create: `frontend/src/lib/installPrompt.ts`, `frontend/src/lib/installPrompt.test.ts`
- Modify: `frontend/src/components/layout/AppShell.tsx` (one side-effect import)
- Create: `frontend/src/features/pwa/{copy.ts, copy.test.ts, lifecycle.ts, lifecycle.test.tsx, homeWidget.tsx, homeWidget.test.tsx, mocks.ts}`
- Modify: `frontend/src/features/auth/components/SessionShell.tsx` (call `usePwaLifecycle`)
- Modify: `frontend/playwright.config.ts` (`serviceWorkers: 'block'`, C10 comment)
- Modify: `frontend/e2e/fixtures.ts` (`installTipSeen`)
- Create: `frontend/e2e/pwa.spec.ts`

**Interfaces:**
- Consumes: T2 `useFeature`, `AdminPreviewBadge`; T3 icons in `frontend/public/icons/`; T4 Caddy handles for `/sw.js`, `/manifest.webmanifest`, `/icons/*` and the CSP; T5 `useTourDone`, `useFeature('tour_glossary')`; `lib/me.getMe`; `lib/useMediaQuery.useIsTouch`, `useMediaQuery`.
- Produces:
  - `build/pwaShell.ts`: `pwaShell(): Plugin`, `precacheList(bundle) -> string[]`, `cacheNameFor(indexHtml) -> string`, `swSource(cacheName, precache) -> string`, `cachesToDelete(current, created) -> string[]`.
  - `lib/chunkReload.ts`: `RELOAD_KEY = 'sc.chunk.reloaded'`, `installChunkReload(win?: Window): void` (called once by `main.tsx`).
  - `lib/installPrompt.ts`: `DISMISSED_KEY = 'sc.install.dismissed'`, `isInstallDismissed()`, `dismissInstall()`, `useInstallPrompt(): BeforeInstallPromptEvent | null`, `promptInstall()`, `isIosSafari(ua?: string): boolean`, `resetInstallPromptForTests()`.
  - `features/pwa/lifecycle.ts`: `usePwaLifecycle(): void`, `MANIFEST_HREF`, `SHELL_CACHE_PREFIX = 'sc-shell-'`.
  - `features/pwa/homeWidget.tsx`: `{ id: 'install', order: 90, slot: 'main' }` (launch redirect + install tip); `LAUNCHED_KEY = 'sc.pwa.launched'`.
  - `e2e/fixtures.ts`: option fixture `installTipSeen` (default `true`).

- [ ] **Step 1: Write the failing plugin tests**

Create `frontend/src/build/pwaShell.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { cacheNameFor, cachesToDelete, precacheList, pwaShell, swSource } from './pwaShell';

const bundle = {
  'index.html': { type: 'asset', fileName: 'index.html', source: '<html>v1</html>' },
  'assets/index-AAA.js': {
    type: 'chunk',
    fileName: 'assets/index-AAA.js',
    isEntry: true,
    isDynamicEntry: false,
    imports: ['assets/vendor-BBB.js'],
    viteMetadata: { importedCss: new Set(['assets/index-CCC.css']) },
  },
  'assets/vendor-BBB.js': {
    type: 'chunk',
    fileName: 'assets/vendor-BBB.js',
    isEntry: false,
    isDynamicEntry: false,
    imports: [],
    viteMetadata: { importedCss: new Set<string>() },
  },
  'assets/ClubPage-DDD.js': {
    type: 'chunk',
    fileName: 'assets/ClubPage-DDD.js',
    isEntry: false,
    isDynamicEntry: true,
    imports: ['assets/vendor-BBB.js'],
    viteMetadata: { importedCss: new Set(['assets/ClubPage-EEE.css']) },
  },
} as const;

describe('pwaShell', () => {
  it('precaches the shell, the entry chunk, its static imports and CSS, never a lazy chunk', () => {
    expect(precacheList(bundle)).toEqual([
      '/',
      '/index.html',
      '/manifest.webmanifest',
      '/icons/icon-192.png',
      '/assets/index-AAA.js',
      '/assets/index-CCC.css',
      '/assets/vendor-BBB.js',
    ]);
  });

  it('names the cache after the first 12 hex of sha256(index.html)', () => {
    expect(cacheNameFor('<html>v1</html>')).toMatch(/^sc-shell-[0-9a-f]{12}$/);
    expect(cacheNameFor('<html>v1</html>')).not.toBe(cacheNameFor('<html>v2</html>'));
  });

  it('keeps the current cache and the newest previous one', () => {
    const created = new Map([
      ['sc-shell-old', 1],
      ['sc-shell-prev', 5],
      ['sc-shell-now', 9],
    ]);
    expect(cachesToDelete('sc-shell-now', created)).toEqual(['sc-shell-old']);
    expect(cachesToDelete('sc-shell-now', new Map([['sc-shell-now', 9]]))).toEqual([]);
  });

  it('emits a worker that never touches /api or /l and stamps each cache', () => {
    const source = swSource('sc-shell-abc', ['/', '/index.html']);
    expect(source).toContain("const CACHE = \"sc-shell-abc\"");
    expect(source).toContain("url.pathname.startsWith('/api/')");
    expect(source).toContain("url.pathname.startsWith('/l/')");
    expect(source).toContain('/__sc-created');
    expect(source).toContain('skipWaiting');
    expect(source).toContain('clients.claim');
    expect(source).toContain('function cachesToDelete');
    expect(() => new Function(source)).not.toThrow(); // valid JavaScript
  });

  it('emits sw.js from generateBundle', () => {
    const plugin = pwaShell();
    const emitted: { fileName: string; source: string }[] = [];
    const hook = plugin.generateBundle as (this: unknown, o: unknown, b: unknown) => void;
    hook.call({ emitFile: (f: { fileName: string; source: string }) => emitted.push(f) }, {}, bundle);
    expect(emitted.map((f) => f.fileName)).toEqual(['sw.js']);
    expect(emitted[0]?.source).toContain('/assets/index-AAA.js');
    expect(emitted[0]?.source).not.toContain('ClubPage-DDD');
    expect(plugin.apply).toBe('build');
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/build/pwaShell.test.ts`
Expected: FAIL, unresolved `./pwaShell`.

- [ ] **Step 3: Write the plugin, the manifest and the index links**

Create `frontend/src/build/pwaShell.ts`:

```ts
// Build-time only (vite.config.ts): emits /sw.js listing this build's shell files (Plan 19 D16).
import { createHash } from 'node:crypto';
import type { Plugin } from 'vite';

interface ChunkLike {
  type: 'chunk';
  fileName: string;
  isEntry: boolean;
  isDynamicEntry: boolean;
  imports: readonly string[];
  viteMetadata?: { importedCss: ReadonlySet<string> };
}
interface AssetLike {
  type: 'asset';
  fileName: string;
  source: string | Uint8Array;
}
type BundleLike = Readonly<Record<string, ChunkLike | AssetLike>>;

const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.png'];

/** The entry chunk, its static imports (transitively) and their CSS; never a lazy route chunk. */
export function precacheList(bundle: BundleLike): string[] {
  const chunks = Object.values(bundle).filter((f): f is ChunkLike => f.type === 'chunk');
  const byName = new Map(chunks.map((c) => [c.fileName, c]));
  const files = new Set<string>();
  const visit = (chunk: ChunkLike) => {
    if (files.has(chunk.fileName)) return;
    files.add(chunk.fileName);
    for (const css of chunk.viteMetadata?.importedCss ?? []) files.add(css);
    for (const name of chunk.imports) {
      const imported = byName.get(name);
      if (imported !== undefined) visit(imported);
    }
  };
  for (const chunk of chunks) if (chunk.isEntry) visit(chunk);
  return [...SHELL, ...[...files].sort().map((f) => `/${f}`)];
}

export function cacheNameFor(indexHtml: string | Uint8Array): string {
  return `sc-shell-${createHash('sha256').update(indexHtml).digest('hex').slice(0, 12)}`;
}

/** Every other sc-shell cache except the newest one, so an old tab keeps its lazy chunks. */
export function cachesToDelete(current: string, created: ReadonlyMap<string, number>): string[] {
  const others = [...created.keys()].filter((name) => name !== current);
  let newest: string | null = null;
  for (const name of others) {
    if (newest === null || (created.get(name) ?? 0) > (created.get(newest) ?? 0)) newest = name;
  }
  return others.filter((name) => name !== newest);
}

export function swSource(cacheName: string, precache: readonly string[]): string {
  return `// Sunday Clays app shell (Plan 19 D16). Never caches /api or /l.
const CACHE = ${JSON.stringify(cacheName)};
const PRECACHE = ${JSON.stringify(precache)};
${cachesToDelete.toString()}
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(PRECACHE);
    await cache.put('/__sc-created', new Response(String(Date.now())));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = (await caches.keys()).filter((name) => name.startsWith('sc-shell-'));
    const created = new Map();
    for (const name of names) {
      const stamp = await (await caches.open(name)).match('/__sc-created');
      created.set(name, stamp ? Number(await stamp.text()) : 0);
    }
    await Promise.all(cachesToDelete(CACHE, created).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/l/')) return;
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => (await caches.match('/index.html', { cacheName: CACHE })) || Response.error()),
    );
    return;
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    event.respondWith((async () => {
      const hit = await caches.match(request);
      if (hit) return hit;
      const response = await fetch(request);
      if (response.ok) await (await caches.open(CACHE)).put(request, response.clone());
      return response;
    })());
  }
});
`;
}

export function pwaShell(): Plugin {
  return {
    name: 'sunday-clays-pwa-shell',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const files = bundle as unknown as BundleLike;
      const index = files['index.html'];
      const html = index?.type === 'asset' ? index.source : '';
      this.emitFile({
        type: 'asset',
        fileName: 'sw.js',
        source: swSource(cacheNameFor(html), precacheList(files)),
      });
    },
  };
}
```

In `frontend/vite.config.ts`, replace

```ts
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
```

with

```ts
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { pwaShell } from './src/build/pwaShell';
```

and replace

```ts
  plugins: [react(), tailwindcss()],
```

with

```ts
  plugins: [react(), tailwindcss(), pwaShell()],
```

Create `frontend/public/manifest.webmanifest` (verbatim from spec §3.4):

```json
{
  "id": "/",
  "name": "Sunday Clays",
  "short_name": "Sunday Clays",
  "description": "Scores, trophies and stats for the Sunday Clays group.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#1A4D2E",
  "theme_color": "#1A4D2E",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

In `frontend/index.html`, replace

```html
    <meta name="theme-color" content="#1A4D2E" />
```

with

```html
    <meta name="theme-color" content="#1A4D2E" />
    <link rel="icon" href="/icons/favicon-32.png" />
    <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />
```

No manifest link here: it is added at run time while `pwa` is visible (D16).

- [ ] **Step 4: Run it to verify it passes, then check a real build**

Run: `cd frontend && pnpm exec vitest run src/build/pwaShell.test.ts && pnpm build && ls dist/sw.js && head -c 300 dist/sw.js`
Expected: PASS; `dist/sw.js` exists and starts with the comment and `const CACHE = "sc-shell-…"`. `grep -c '/assets/' dist/sw.js` is small (the entry, its imports and CSS only).

- [ ] **Step 5: Write the failing chunk-reload and install-prompt tests**

Create `frontend/src/lib/chunkReload.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { installChunkReload, RELOAD_KEY } from './chunkReload';

function fakeWindow() {
  const target = new EventTarget();
  const reload = vi.fn();
  const win = Object.assign(target, { location: { reload }, sessionStorage }) as unknown as Window;
  return { win, reload, target };
}

afterEach(() => sessionStorage.clear());

describe('chunk-load recovery', () => {
  it('reloads once on a preload error, and not twice', () => {
    const { win, reload, target } = fakeWindow();
    installChunkReload(win);
    const first = new Event('vite:preloadError', { cancelable: true });
    target.dispatchEvent(first);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(first.defaultPrevented).toBe(true);
    expect(sessionStorage.getItem(RELOAD_KEY)).toBe('1');
    target.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('clears the guard after a successful load', () => {
    const { win, target } = fakeWindow();
    sessionStorage.setItem(RELOAD_KEY, '1');
    installChunkReload(win);
    target.dispatchEvent(new Event('load'));
    expect(sessionStorage.getItem(RELOAD_KEY)).toBeNull();
  });
});
```

Create `frontend/src/lib/installPrompt.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  dismissInstall,
  DISMISSED_KEY,
  isInstallDismissed,
  isIosSafari,
  promptInstall,
  resetInstallPromptForTests,
} from './installPrompt';

afterEach(() => resetInstallPromptForTests());

function installEvent(outcome: 'accepted' | 'dismissed') {
  const event = new Event('beforeinstallprompt', { cancelable: true });
  return Object.assign(event, {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome }),
  });
}

describe('install prompt', () => {
  it('captures the event, prevents the mini-infobar, and prompts on demand', async () => {
    const event = installEvent('accepted');
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    await expect(promptInstall()).resolves.toBe('accepted');
    expect(event.prompt).toHaveBeenCalled();
    expect(isInstallDismissed()).toBe(true); // an install also dismisses the tip
  });

  it('is unavailable with no captured event', async () => {
    await expect(promptInstall()).resolves.toBe('unavailable');
  });

  it('remembers a dismissal', () => {
    dismissInstall();
    expect(localStorage.getItem(DISMISSED_KEY)).toBe('1');
    expect(isInstallDismissed()).toBe(true);
  });

  it.each([
    ['Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1', true],
    ['Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/129.0 Mobile/15E148 Safari/604.1', false],
    ['Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/129.0 Mobile/15E148 Safari/605.1.15', false],
    ['Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36', false],
  ])('isIosSafari(%s) is %s', (ua, expected) => {
    expect(isIosSafari(ua)).toBe(expected);
  });
});
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/lib/chunkReload.test.ts src/lib/installPrompt.test.ts`
Expected: FAIL, unresolved modules.

- [ ] **Step 7: Write the two lib modules and wire them in**

Create `frontend/src/lib/chunkReload.ts`:

```ts
/**
 * Plan 19 §3.4: a lazy chunk from an old build that is gone from both the cache and the server
 * reloads the page once onto the new build, instead of showing an error. Guarded per session.
 */
export const RELOAD_KEY = 'sc.chunk.reloaded';

export function installChunkReload(win: Window = window): void {
  win.addEventListener('vite:preloadError', (event) => {
    let reloaded = false;
    try {
      reloaded = win.sessionStorage.getItem(RELOAD_KEY) === '1';
      if (!reloaded) win.sessionStorage.setItem(RELOAD_KEY, '1');
    } catch {
      reloaded = false;
    }
    if (reloaded) return; // the error stands: the route's error page shows
    event.preventDefault();
    win.location.reload();
  });
  win.addEventListener('load', () => {
    try {
      win.sessionStorage.removeItem(RELOAD_KEY);
    } catch {
      // storage blocked: nothing to clear
    }
  });
}
```

In `frontend/src/main.tsx`, replace

```tsx
import { App } from './app/App';
import './theme/theme.css';
```

with

```tsx
import { App } from './app/App';
import { installChunkReload } from './lib/chunkReload';
import './theme/theme.css';

installChunkReload();
```

Create `frontend/src/lib/installPrompt.ts`:

```ts
import { useSyncExternalStore } from 'react';

/** Chromium's install event (not in lib.dom). */
export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export const DISMISSED_KEY = 'sc.install.dismissed';

let deferred: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => {
  for (const listener of listeners) listener();
};

// Attached at import (AppShell imports this module), so an early event is never missed.
window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  deferred = event as BeforeInstallPromptEvent;
  notify();
});
window.addEventListener('appinstalled', () => {
  deferred = null;
  dismissInstall();
});

export function isInstallDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function dismissInstall(): void {
  try {
    localStorage.setItem(DISMISSED_KEY, '1');
  } catch {
    // storage blocked: the tip may show again on the next load
  }
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useInstallPrompt(): BeforeInstallPromptEvent | null {
  return useSyncExternalStore(subscribe, () => deferred, () => null);
}

export function useInstallDismissed(): boolean {
  return useSyncExternalStore(subscribe, isInstallDismissed, () => true);
}

export async function promptInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  const event = deferred;
  if (event === null) return 'unavailable';
  await event.prompt();
  const { outcome } = await event.userChoice;
  deferred = null;
  dismissInstall(); // Install (either answer) never shows the tip again
  return outcome;
}

/** iPhone, iPad or iPod Safari (not Chrome or Firefox on iOS, which cannot add to home). */
export function isIosSafari(ua: string = navigator.userAgent): boolean {
  return /iP(hone|ad|od)/.test(ua) && /Safari/.test(ua) && !/CriOS|FxiOS/.test(ua);
}

export function resetInstallPromptForTests(): void {
  deferred = null;
}
```

In `frontend/src/components/layout/AppShell.tsx`, replace

```tsx
import { useState, type ReactNode } from 'react';
```

with

```tsx
import { useState, type ReactNode } from 'react';
// Plan 19 §3.4: listen for the install prompt as early as the shell exists.
import '../../lib/installPrompt';
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/lib src/components/layout`
Expected: PASS.

- [ ] **Step 9: Write the failing lifecycle and widget tests**

Create `frontend/src/features/pwa/copy.ts`:

```ts
export const TIP_TITLE = 'Add Sunday Clays to your home screen';
export const ANDROID_BODY = 'Opens like an app, straight to Home or to your own page.';
export const IOS_BODY = 'Tap the Share button, then “Add to Home Screen”.';
export const INSTALL = 'Install';
export const NOT_NOW = 'Not now';
export const GOT_IT = 'Got it';
```

Create `frontend/src/features/pwa/copy.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import * as copy from './copy';

describe('install tip copy', () => {
  it('uses no banned word', () => {
    for (const text of allStrings(Object.values(copy))) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

Create `frontend/src/features/pwa/mocks.ts`:

```ts
import type { RequestHandler } from 'msw';

/** The PWA feature calls no API of its own (it reads /api/features through lib/features). */
export const handlers: RequestHandler[] = [];
```

Create `frontend/src/features/pwa/lifecycle.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '../../app/providers';
import { SESSION_QUERY_KEY, type Role } from '../auth/api';
import { server } from '../../test/msw/server';
import { createTestQueryClient } from '../../test/render';
import { MANIFEST_HREF, usePwaLifecycle } from './lifecycle';

const register = vi.fn().mockResolvedValue({});
const unregister = vi.fn().mockResolvedValue(true);
const getRegistrations = vi.fn().mockResolvedValue([{ unregister }]);
const cacheKeys = vi.fn().mockResolvedValue(['sc-shell-aaa', 'other-cache']);
const cacheDelete = vi.fn().mockResolvedValue(true);

beforeEach(() => {
  vi.stubGlobal('navigator', { ...navigator, serviceWorker: { register, getRegistrations } });
  vi.stubGlobal('caches', { keys: cacheKeys, delete: cacheDelete });
});
afterEach(() => {
  document.querySelectorAll('link[rel="manifest"]').forEach((el) => el.remove());
  vi.clearAllMocks();
});

function wrapper(role: Role | null) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(SESSION_QUERY_KEY, role === null ? null : { role });
  return ({ children }: { children: ReactNode }) => (
    <AppProviders queryClient={queryClient}>{children}</AppProviders>
  );
}

const switches = (on: boolean) =>
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: on ? { pwa: true } : {} })));

const settle = () => new Promise((resolve) => setTimeout(resolve, 50));

describe('usePwaLifecycle', () => {
  it('links the manifest and registers the worker while visible', async () => {
    switches(true);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(register).toHaveBeenCalledWith('/sw.js', { scope: '/' }));
    expect(document.querySelector(`link[rel="manifest"][href="${MANIFEST_HREF}"]`)).not.toBeNull();
  });

  it('unregisters and deletes shell caches on a definite off for a viewer', async () => {
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await waitFor(() => expect(unregister).toHaveBeenCalled());
    await waitFor(() => expect(cacheDelete).toHaveBeenCalledWith('sc-shell-aaa'));
    expect(cacheDelete).not.toHaveBeenCalledWith('other-cache');
    expect(register).not.toHaveBeenCalled();
  });

  it('leaves the registration alone while pending', async () => {
    server.use(http.get('*/api/features', () => new Promise(() => undefined)));
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
    expect(cacheDelete).not.toHaveBeenCalled();
  });

  it('leaves the registration alone after a network error', async () => {
    server.use(http.get('*/api/features', () => HttpResponse.error()));
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
  });

  it('leaves the registration alone after a 401', async () => {
    server.use(
      http.get('*/api/features', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('viewer') });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
  });

  it('leaves the registration alone on /login (no session, no request)', async () => {
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper(null) });
    await settle();
    expect(getRegistrations).not.toHaveBeenCalled();
    expect(register).not.toHaveBeenCalled();
  });

  it('registers for an admin previewing it, and never unregisters for an admin', async () => {
    switches(false);
    renderHook(() => usePwaLifecycle(), { wrapper: wrapper('admin') });
    await waitFor(() => expect(register).toHaveBeenCalled());
    expect(getRegistrations).not.toHaveBeenCalled();
  });
});
```

The 401 case: `unwrap` throws `ApiError`, the query errors, `settled` stays false. (`shouldRedirectToLogin` would also navigate; `renderHook` has no router to break.)

Create `frontend/src/features/pwa/homeWidget.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { resetInstallPromptForTests } from '../../lib/installPrompt';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { homeWidget, LAUNCHED_KEY } from './homeWidget';

const { Component } = homeWidget;

function media(matches: Record<string, boolean>) {
  vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: matches[query] ?? false,
        media: query,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      }) as unknown as MediaQueryList,
  );
}

function fireInstallPrompt() {
  const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
    prompt: vi.fn().mockResolvedValue(undefined),
    userChoice: Promise.resolve({ outcome: 'dismissed' as const }),
  });
  window.dispatchEvent(event);
  return event;
}

beforeEach(() => {
  server.use(http.get('*/api/features', () => HttpResponse.json({ switches: { pwa: true } })));
});
afterEach(() => {
  resetInstallPromptForTests();
  sessionStorage.clear();
});

describe('install tip and launch redirect', () => {
  it('declares a main widget at order 90', () => {
    expect(homeWidget).toMatchObject({ id: 'install', order: 90, slot: 'main' });
  });

  it('shows the Android tip after the install event, and Not now hides it for good', async () => {
    media({ '(pointer: coarse)': true });
    const { user } = renderWithProviders(<Component meId={null} />);
    fireInstallPrompt();
    expect(await screen.findByRole('heading', { name: 'Add Sunday Clays to your home screen' })).toBeInTheDocument();
    expect(screen.getByText('Opens like an app, straight to Home or to your own page.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Not now' }));
    expect(localStorage.getItem('sc.install.dismissed')).toBe('1');
    expect(screen.queryByRole('heading', { name: /home screen/ })).not.toBeInTheDocument();
  });

  it('Install calls prompt()', async () => {
    media({ '(pointer: coarse)': true });
    const { user } = renderWithProviders(<Component meId={null} />);
    const event = fireInstallPrompt();
    await user.click(await screen.findByRole('button', { name: 'Install' }));
    expect(event.prompt).toHaveBeenCalled();
  });

  it('shows the iOS tip on iPhone Safari without any event', async () => {
    media({ '(pointer: coarse)': true });
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    );
    renderWithProviders(<Component meId={null} />);
    expect(await screen.findByText('Tap the Share button, then “Add to Home Screen”.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Got it' })).toBeInTheDocument();
  });

  it.each([
    ['on a desktop', { '(pointer: coarse)': false }, false],
    ['when installed', { '(pointer: coarse)': true, '(display-mode: standalone)': true }, false],
  ])('stays hidden %s', async (_name, matches, _shown) => {
    media(matches);
    const { container } = renderWithProviders(<Component meId={null} />);
    fireInstallPrompt();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
  });

  it('waits for the tour to be done', async () => {
    media({ '(pointer: coarse)': true });
    server.use(
      http.get('*/api/features', () =>
        HttpResponse.json({ switches: { pwa: true, tour_glossary: true } }),
      ),
    );
    const { container } = renderWithProviders(<Component meId={null} />);
    fireInstallPrompt();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(container).toBeEmptyDOMElement();
    localStorage.setItem('sc.tour.v1', 'done');
  });

  it('opens an installed app on the viewer’s own page once per session', async () => {
    media({ '(display-mode: standalone)': true });
    localStorage.setItem('sc.me', '3');
    const { router } = renderWithProviders(<Component meId={3} />, { route: '/' });
    await waitFor(() => expect(router.state.location.pathname).toBe('/shooters/3'));
    expect(sessionStorage.getItem(LAUNCHED_KEY)).toBe('1');
  });

  it('stays on Home without a picked name, or once already launched', async () => {
    media({ '(display-mode: standalone)': true });
    const first = renderWithProviders(<Component meId={null} />, { route: '/' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(first.router.state.location.pathname).toBe('/');
    first.unmount();
    localStorage.setItem('sc.me', '3');
    sessionStorage.setItem(LAUNCHED_KEY, '1');
    const second = renderWithProviders(<Component meId={3} />, { route: '/' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(second.router.state.location.pathname).toBe('/');
  });
});
```

The "waits for the tour" test relies on the tour state module: with `tour_glossary` on and `sc.tour.v1` unset, the tour is visible and not done, so the tip stays hidden (Task 5's `useTourDone`).

- [ ] **Step 10: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/pwa`
Expected: FAIL, unresolved `./lifecycle` and `./homeWidget`.

- [ ] **Step 11: Write the lifecycle hook, the widget and the SessionShell call**

Create `frontend/src/features/pwa/lifecycle.ts`:

```ts
import { useEffect } from 'react';
import { useFeature } from '../../lib/features';
import { useSession } from '../auth/api';

export const MANIFEST_HREF = '/manifest.webmanifest';
export const SHELL_CACHE_PREFIX = 'sc-shell-';

function linkManifest(): void {
  if (document.querySelector('link[rel="manifest"]') !== null) return;
  const link = document.createElement('link');
  link.rel = 'manifest';
  link.href = MANIFEST_HREF;
  document.head.appendChild(link);
}

function unlinkManifest(): void {
  document.querySelectorAll('link[rel="manifest"]').forEach((el) => el.remove());
}

async function registerShell(): Promise<void> {
  if (!('serviceWorker' in navigator)) return;
  await navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => undefined);
}

async function removeShell(): Promise<void> {
  if ('serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((r) => r.unregister()));
  }
  if ('caches' in window) {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.startsWith(SHELL_CACHE_PREFIX)).map((n) => caches.delete(n)));
  }
}

/**
 * Plan 19 D16: link the manifest and register /sw.js only while `pwa` is visible. Unregister
 * only on a definite off: a successful /api/features answer, for a viewer, without `pwa`. A
 * pending, failed or 401 answer, and the logged-out /login page, never touch the worker.
 */
export function usePwaLifecycle(): void {
  const { session } = useSession();
  const { visible, settled, on } = useFeature('pwa');
  const role = session?.role ?? null;
  useEffect(() => {
    if (visible) {
      linkManifest();
      void registerShell();
    } else if (settled && !on && role === 'viewer') {
      unlinkManifest();
      void removeShell();
    }
  }, [visible, settled, on, role]);
}
```

Create `frontend/src/features/pwa/homeWidget.tsx`:

```tsx
import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { AdminPreviewBadge } from '../../components/ui/AdminPreviewBadge';
import { Card } from '../../components/ui/Card';
import { useFeature } from '../../lib/features';
import {
  dismissInstall,
  isIosSafari,
  promptInstall,
  useInstallDismissed,
  useInstallPrompt,
} from '../../lib/installPrompt';
import { getMe } from '../../lib/me';
import { useIsTouch, useMediaQuery } from '../../lib/useMediaQuery';
import type { HomeWidget } from '../home/widgets';
import { useTourDone } from '../tour/state';
import { ANDROID_BODY, GOT_IT, INSTALL, IOS_BODY, NOT_NOW, TIP_TITLE } from './copy';

export const LAUNCHED_KEY = 'sc.pwa.launched';
const STANDALONE = '(display-mode: standalone)';
const BUTTON = 'inline-flex min-h-11 items-center justify-center rounded-button px-4 text-sm';

/** An installed app opens on the viewer's own page, once per session (§3.4 launch behaviour). */
function useLaunchRedirect(): void {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    if (!window.matchMedia(STANDALONE).matches || pathname !== '/') return;
    try {
      if (sessionStorage.getItem(LAUNCHED_KEY) !== null) return;
      const me = getMe();
      if (me === null) return;
      void navigate(`/shooters/${String(me)}`, { replace: true });
      sessionStorage.setItem(LAUNCHED_KEY, '1');
    } catch {
      // storage blocked: stay on Home
    }
  }, [navigate, pathname]);
}

/** Always mounts (the launch redirect runs first), then renders the install tip or nothing. */
function InstallTip() {
  useLaunchRedirect();
  const { visible } = useFeature('pwa');
  const tour = useFeature('tour_glossary');
  const tourDone = useTourDone();
  const touch = useIsTouch();
  const standalone = useMediaQuery(STANDALONE);
  const dismissed = useInstallDismissed();
  const prompt = useInstallPrompt();
  const ios = isIosSafari();
  const show =
    visible && touch && !standalone && !dismissed && (tourDone || !tour.visible) && (prompt !== null || ios);
  if (!show) return null;
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          {TIP_TITLE}
          <AdminPreviewBadge feature="pwa" />
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        <p>{prompt !== null ? ANDROID_BODY : IOS_BODY}</p>
        <div className="flex flex-wrap gap-2">
          {prompt !== null ? (
            <>
              <button type="button" className={`${BUTTON} bg-primary text-text`} onClick={() => void promptInstall()}>
                {INSTALL}
              </button>
              <button type="button" className={`${BUTTON} border border-outline-variant`} onClick={dismissInstall}>
                {NOT_NOW}
              </button>
            </>
          ) : (
            <button type="button" className={`${BUTTON} border border-outline-variant`} onClick={dismissInstall}>
              {GOT_IT}
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

export const homeWidget: HomeWidget = { id: 'install', order: 90, slot: 'main', Component: InstallTip };
```

In `frontend/src/features/auth/components/SessionShell.tsx`, replace

```tsx
import { usePageViewBeacon } from '../../pageviews/beacon';
```

with

```tsx
import { usePageViewBeacon } from '../../pageviews/beacon';
import { usePwaLifecycle } from '../../pwa/lifecycle';
```

and replace

```tsx
  usePageViewBeacon(session?.role ?? null);
  const features = useFeatures();
```

with

```tsx
  usePageViewBeacon(session?.role ?? null);
  usePwaLifecycle(); // Plan 19 D16: inside the session only, so /login never touches the worker
  const features = useFeatures();
```

- [ ] **Step 12: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/pwa src/features/auth src/features/home`
Expected: PASS. Existing SessionShell tests pass: the default mock has `pwa` off and jsdom has no `navigator.serviceWorker`, so nothing registers.

- [ ] **Step 13: Block service workers in e2e, add `installTipSeen`, write the PWA e2e**

In `frontend/playwright.config.ts`, replace

```ts
 * preset would break login. Only Plan 01 T4, Plan 04 T1 and Plan 08 T5a edit this file (C10).
```

with

```ts
 * preset would break login. Only Plan 01 T4, Plan 04 T1, Plan 08 T5a and Plan 19 T9
 * (serviceWorkers) edit this file (C10).
```

and replace

```ts
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
  },
```

with

```ts
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
    // Plan 19 D24: page.route cannot see requests a service worker answers, and a cache-first
    // /assets/* would carry state between tests. Only pwa.spec.ts opts back in.
    serviceWorkers: 'block',
  },
```

In `frontend/e2e/fixtures.ts`, replace

```ts
export const test = base.extend<{ pageProblems: string[]; tourSeen: boolean; seenFlags: void }>({
  tourSeen: [true, { option: true }],
  seenFlags: [
    async ({ page, tourSeen }, use) => {
      if (tourSeen) {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('sc.tour.v1', 'done');
          } catch {
            // storage blocked: the spec meets the tour, as a real visitor would
          }
        });
      }
      await use();
    },
```

with

```ts
export const test = base.extend<{
  pageProblems: string[];
  tourSeen: boolean;
  installTipSeen: boolean;
  seenFlags: void;
}>({
  tourSeen: [true, { option: true }],
  installTipSeen: [true, { option: true }],
  seenFlags: [
    async ({ page, tourSeen, installTipSeen }, use) => {
      await page.addInitScript(
        ({ tour, tip }) => {
          try {
            if (tour) localStorage.setItem('sc.tour.v1', 'done');
            if (tip) localStorage.setItem('sc.install.dismissed', '1');
          } catch {
            // storage blocked: the spec meets the tour and the tip, as a real visitor would
          }
        },
        { tour: tourSeen, tip: installTipSeen },
      );
      await use();
    },
```

and update the doc comment's last sentence to: "`tourSeen` and `installTipSeen` (both default true) mark the tour as done and the install tip as dismissed before every page load; the tour and PWA specs set them false."

Create `frontend/e2e/pwa.spec.ts`:

```ts
import type { Page } from '@playwright/test';
import { expect, test } from './fixtures';

test.use({ serviceWorkers: 'allow' });

async function shellCaches(page: Page): Promise<Record<string, string[]>> {
  return page.evaluate(async () => {
    const out: Record<string, string[]> = {};
    for (const name of await caches.keys()) {
      if (!name.startsWith('sc-shell-')) continue;
      const keys = await (await caches.open(name)).keys();
      out[name] = keys.map((r) => new URL(r.url).pathname);
    }
    return out;
  });
}

test('manifest and worker are served with the right headers', async ({ request }) => {
  const manifest = await request.get('/manifest.webmanifest');
  expect(manifest.headers()['content-type']).toMatch(/^application\/manifest\+json/);
  const worker = await request.get('/sw.js');
  expect(worker.headers()['cache-control']).toBe('no-cache');
  expect(worker.headers()['service-worker-allowed']).toBe('/');
});

test('the worker installs a small shell and never caches /api', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await expect(page.locator('link[rel="manifest"]')).toHaveCount(1);
  const before = await shellCaches(page);
  expect(Object.keys(before)).toHaveLength(1);
  const [files] = Object.values(before) as [string[]];
  expect(files).toContain('/index.html');
  expect(files).toContain('/__sc-created');
  expect(files.some((f) => /^\/assets\/.+\.css$/.test(f))).toBe(true);
  const jsBefore = files.filter((f) => f.endsWith('.js')).length;
  await page.reload(); // now controlled by the worker
  await page.goto('/club');
  await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible();
  await page.goto('/events');
  await page.goto('/shooters/3');
  const after = Object.values(await shellCaches(page)).flat();
  expect(after.some((f) => f.startsWith('/api/'))).toBe(false);
  expect(after.filter((f) => f.endsWith('.js')).length).toBeGreaterThan(jsBefore); // lazy chunks at run time
});

test('logging out and loading /login keeps the registration', async ({ page, isMobile }) => {
  await page.goto('/');
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  if (isMobile) await page.getByRole('button', { name: 'More' }).click();
  await page.getByRole('button', { name: 'Log out' }).click();
  await page.goto('/login');
  const count = await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length);
  expect(count).toBe(1);
});

test.describe('install tip', () => {
  test.use({ installTipSeen: false });

  test('a synthetic install event shows the tip and Not now hides it for good', async ({ page, isMobile }) => {
    test.skip(!isMobile, 'the tip is for touch devices');
    await page.goto('/');
    await page.evaluate(() => {
      const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
        prompt: () => Promise.resolve(),
        userChoice: Promise.resolve({ outcome: 'dismissed' }),
      });
      window.dispatchEvent(event);
    });
    const title = page.getByRole('heading', { name: 'Add Sunday Clays to your home screen' });
    await expect(title).toBeVisible();
    await page.getByRole('button', { name: 'Not now' }).click();
    await expect(title).toHaveCount(0);
    await page.reload();
    await page.waitForTimeout(500);
    await expect(title).toHaveCount(0);
  });
});

test.describe('chunk-load recovery', () => {
  test.use({ serviceWorkers: 'block' }); // so page.route sees the chunk request

  test('a lazy chunk that fails once reloads the page once and the route renders', async ({ page }) => {
    await page.goto('/');
    let failed = false;
    await page.route(/\/assets\/ClubPage-[^/]+\.js$/, async (route) => {
      if (failed) return route.continue();
      failed = true;
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('/club');
    await expect(page.getByRole('heading', { level: 1, name: 'Club' })).toBeVisible({ timeout: 15_000 });
    expect(failed).toBe(true);
  });
});
```

`page.goto('/club')` loads the shell, then the lazy Club chunk, which fails once; `lib/chunkReload.ts` reloads, and the second request goes through (the chunk name pattern `ClubPage-*.js` comes from the lazy `import('./pages/ClubPage')`; confirm it with `ls frontend/dist/assets | grep ClubPage` after Step 4's build and adjust the regex if Vite names it differently).

- [ ] **Step 14: Run the e2e at both sizes, plus the specs that use `page.route`**

Rebuild the stack (project `task19-9`, port 18081). Run: `pnpm exec playwright test pwa.spec.ts insight-bumps.spec.ts weather.spec.ts home.spec.ts --project=desktop --project=mobile`.
Expected: PASS (`insight-bumps` and `weather` prove the block keeps `page.route` working; `home` proves the tip stays out of other specs).

- [ ] **Step 15: Run the frontend gates (bundle budget included), then commit**

Run the frontend gates, then `pnpm build` and compare `dist/assets/index-*.js` gzip size with `ratchets/budgets.json` (`gzip -c dist/assets/index-*.js | wc -c` ≤ 250 KiB).

```bash
git add frontend/public/manifest.webmanifest frontend/index.html frontend/src/build frontend/vite.config.ts \
  frontend/src/lib/chunkReload.ts frontend/src/lib/chunkReload.test.ts frontend/src/main.tsx \
  frontend/src/lib/installPrompt.ts frontend/src/lib/installPrompt.test.ts \
  frontend/src/components/layout/AppShell.tsx frontend/src/features/pwa \
  frontend/src/features/auth/components/SessionShell.tsx frontend/playwright.config.ts \
  frontend/e2e/fixtures.ts frontend/e2e/pwa.spec.ts
git commit -m "feat(pwa): installable app shell, install tip and launch redirect (Plan 19 T9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 10: Switches end to end, the production default, the About sentence and the owner preview (`task/19-10-switches-e2e`, wave 5)

**Files:**
- Create: `frontend/e2e/features.admin-mutations.spec.ts`
- Modify: `frontend/src/features/about/pages/AboutPage.tsx` (export `PRIVACY`, the `link_previews`-gated line)
- Modify: `frontend/src/features/about/pages/AboutPage.test.tsx` (five points off, six on, admin preview)
- Create: `frontend/src/features/about/privacy.test.ts`
- Modify: `frontend/e2e/about.spec.ts` (five → six list items: the e2e stack has `link_previews` on)

**Interfaces:**
- Consumes: T2 `useFeature`, `AdminPreviewBadge`; every earlier task's UI and API: T1 `PUT /api/admin/features/{key}`, `GET /api/admin/features`, `GET /api/features`; T3/T4 previews; T5 tour and glossary; T6 milestones; T7 summary card; T9 install tip; `e2e/authState.{ADMIN_STATE, VIEWER_STATE}`.
- Produces: `features.admin-mutations.spec.ts` with helpers `adminSwitches(api)`, `setSwitch(api, key, enabled)`, `viewerPage(browser, size)` and the `beforeEach`/`afterEach` restore; Task 12 appends its page-cache test to this same file (no cross-spec import).

- [ ] **Step 1: Write the failing About tests**

The sentence describes `link_previews`, which ships **off** in production, so it shows only while that switch is visible (an admin sees it with the "Admin preview" badge), the pattern Plan 20 uses for its About lines.

Create `frontend/src/features/about/privacy.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { LINK_PREVIEWS_LINE, PRIVACY } from './pages/AboutPage';

describe('About privacy points', () => {
  it('say what link previews show, and never names or scores', () => {
    expect(LINK_PREVIEWS_LINE).toBe(
      'Links shared in chat apps show only the club name, and for a Sunday its date, how many shot and the round type. Never names or scores.',
    );
    expect(PRIVACY).not.toContain(LINK_PREVIEWS_LINE); // only behind its switch
  });

  it('use no banned word', () => {
    for (const text of allStrings([...PRIVACY, LINK_PREVIEWS_LINE])) {
      expect(text).not.toMatch(BANNED_WORDS);
    }
  });
});
```

In `frontend/src/features/about/pages/AboutPage.test.tsx`, add the imports `import { http, HttpResponse } from 'msw';` and `import { server } from '../../../test/msw/server';` (merge `beforeEach` into the existing vitest import), add at the top of the `describe` block

```tsx
  beforeEach(() => {
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));
  });
```

and replace

```tsx
  it('lists five privacy points', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    const section = screen.getByRole('region', { name: 'Your privacy' });
    expect(within(section).getByRole('list')).toBeInTheDocument();
    expect(within(section).getAllByRole('listitem')).toHaveLength(5);
  });
```

with

```tsx
  it('lists five privacy points while link previews are off', () => {
    renderWithProviders(<AboutPage />, { route: '/about' });
    const section = screen.getByRole('region', { name: 'Your privacy' });
    expect(within(section).getByRole('list')).toBeInTheDocument();
    expect(within(section).getAllByRole('listitem')).toHaveLength(5);
    expect(within(section).queryByText(/Links shared in chat apps/)).not.toBeInTheDocument();
  });

  it('adds the link-preview sentence once link previews are on', async () => {
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: { link_previews: true } })),
    );
    renderWithProviders(<AboutPage />, { route: '/about' });
    const section = screen.getByRole('region', { name: 'Your privacy' });
    expect(await within(section).findByText(/Links shared in chat apps/)).toBeInTheDocument();
    expect(within(section).getAllByRole('listitem')).toHaveLength(6);
    expect(within(section).queryByText('Admin preview')).not.toBeInTheDocument();
  });

  it('shows an admin the sentence with the preview badge while off', async () => {
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: { link_previews: false } })),
    );
    renderWithProviders(<AboutPage />, { route: '/about', role: 'admin' });
    const section = screen.getByRole('region', { name: 'Your privacy' });
    expect(await within(section).findByText(/Links shared in chat apps/)).toBeInTheDocument();
    expect(within(section).getByText('Admin preview')).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/about`
Expected: FAIL: `PRIVACY` and `LINK_PREVIEWS_LINE` are not exported, and the sentence never appears.

- [ ] **Step 3: Add the sentence behind its switch**

In `frontend/src/features/about/pages/AboutPage.tsx`, add the imports

```tsx
import { AdminPreviewBadge } from '../../../components/ui/AdminPreviewBadge';
import { useFeature } from '../../../lib/features';
```

replace

```tsx
const PRIVACY = [
```

with

```tsx
/** Plan 19 §4: shown only while `link_previews` is visible (it describes that feature). */
export const LINK_PREVIEWS_LINE =
  'Links shared in chat apps show only the club name, and for a Sunday its date, how many shot and the round type. Never names or scores.';

export const PRIVACY = [
```

add as the first line of `AboutPage()`:

```tsx
  const previews = useFeature('link_previews');
```

and replace

```tsx
          {PRIVACY.map((line) => (
            <li key={line}>{line}</li>
          ))}
```

with

```tsx
          {PRIVACY.map((line) => (
            <li key={line}>{line}</li>
          ))}
          {previews.visible && (
            <li>
              {LINK_PREVIEWS_LINE}
              {previews.preview && (
                <>
                  {' '}
                  <AdminPreviewBadge feature="link_previews" />
                </>
              )}
            </li>
          )}
```

In `frontend/e2e/about.spec.ts`, replace

```ts
  ).toHaveCount(5);
```

with

```ts
  ).toHaveCount(6); // the e2e stack turns every feature on (FEATURES_DEFAULT_ON), link previews too
```

Run: `cd frontend && pnpm exec vitest run src/features/about`
Expected: PASS.

- [ ] **Step 4: Write the switch e2e**

Create `frontend/e2e/features.admin-mutations.spec.ts`:

```ts
import type { APIRequestContext, Browser, Page } from '@playwright/test';
import { request as pwRequest } from '@playwright/test';
import { ADMIN_STATE, VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { whenSettled } from './layout';

// Project `admin-mutations` (one worker, after every read-only spec). Every switch is put back
// in `test.afterEach` on a fresh admin request context, so a timeout or a closed page still
// restores them. The e2e stack starts with every feature on (FEATURES_DEFAULT_ON).
test.use({ storageState: ADMIN_STATE });

export const FEATURE_KEYS = [
  'link_previews',
  'tour_glossary',
  'weekly_recap',
  'pwa',
  'club_milestones',
  'summary_card',
] as const;
const SIZES = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
] as const;
const DAY = '2026-09-27';
const FB = 'facebookexternalhit/1.1';
const GENERIC = 'Scores, trophies and stats for the Sunday Clays group at Tri-County Gun Club.';

export async function adminSwitches(api: APIRequestContext): Promise<Record<string, boolean>> {
  const response = await api.get('/api/admin/features');
  expect(response.ok()).toBe(true);
  const rows = (await response.json()) as { key: string; enabled: boolean }[];
  return Object.fromEntries(rows.map((r) => [r.key, r.enabled]));
}

export async function setSwitch(api: APIRequestContext, key: string, enabled: boolean): Promise<void> {
  const response = await api.put(`/api/admin/features/${key}`, { data: { enabled } });
  expect(response.ok(), `${key} -> ${String(enabled)}`).toBe(true);
}

export async function viewerPage(
  browser: Browser,
  size: { width: number; height: number },
): Promise<Page> {
  const context = await browser.newContext({
    storageState: VIEWER_STATE,
    viewport: size,
    isMobile: size.width < 600,
    hasTouch: size.width < 600,
    serviceWorkers: 'block',
  });
  return context.newPage();
}

let saved: Record<string, boolean> = {};

test.beforeEach(async ({ request }) => {
  saved = await adminSwitches(request);
});

test.afterEach(async ({ baseURL }) => {
  const api = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  try {
    // Only keys a test changed are put back. A blind PUT of every saved row would also PUT
    // page_cache=true after Task 11 (it is listed by /api/admin/features), which empties the
    // cache, forgets the last warm-up and turns its missing-row default into a stored row.
    const now = await adminSwitches(api);
    for (const [key, enabled] of Object.entries(saved)) {
      if (now[key] !== enabled) await setSwitch(api, key, enabled);
    }
  } finally {
    await api.dispose();
  }
});

async function description(api: APIRequestContext): Promise<string | null> {
  const html = await (await api.get(`/events/${DAY}`, { headers: { 'User-Agent': FB } })).text();
  return /property="og:description" content="([^"]*)"/.exec(html)?.[1] ?? null;
}

test('summary card off: hidden for a viewer, 404 from its API, previewed by an admin', async ({
  page,
  request,
  browser,
}) => {
  await setSwitch(request, 'summary_card', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto('/shooters/3');
    await whenSettled(viewer);
    await expect(viewer.getByRole('heading', { name: /Summary card/ })).toHaveCount(0);
    const api = await viewer.request.get(`/api/shooters/3/summary?from=2026-08-03&to=${DAY}`);
    expect(api.status()).toBe(404);
    expect(await api.json()).toEqual({ detail: 'Not Found' });
    await viewer.context().close();
  }
  await page.goto('/shooters/3');
  const card = page.getByRole('region', { name: /^Summary card/ });
  await expect(card).toBeVisible();
  await expect(card.getByText('Admin preview')).toBeVisible();
});

test('link previews off: every crawler gets the generic preview', async ({ request }) => {
  await setSwitch(request, 'link_previews', false);
  expect(await description(request)).toBe(GENERIC);
});

test('glossary off: "Page not found" and no nav item for a viewer', async ({ request, browser }) => {
  await setSwitch(request, 'tour_glossary', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto('/glossary');
    await expect(viewer.getByRole('heading', { name: 'Page not found' })).toBeVisible();
    await viewer.goto('/');
    if (size.width < 600) await viewer.getByRole('button', { name: 'More' }).click();
    await expect(viewer.getByRole('link', { name: 'Glossary' })).toHaveCount(0);
    await viewer.context().close();
  }
});

const TIP = 'Add Sunday Clays to your home screen';
/** Home's cards for a first-time viewer at the plan's base (R7: nothing is removed from Home). */
const HOME_CARDS = ['Latest Sunday', 'Club pulse', 'Insights', 'Which one are you?'] as const;

async function fireInstallPrompt(viewer: Page): Promise<void> {
  await viewer.evaluate(() => {
    const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      prompt: () => Promise.resolve(),
      userChoice: Promise.resolve({ outcome: 'dismissed' }),
    });
    window.dispatchEvent(event);
  });
}

test('all switches off (the production default): the viewer sees today\'s app', async ({
  request,
  browser,
}) => {
  // Positive control, same setup: only `pwa` on, a first-time phone viewer, the event fired after
  // the page settles (lib/installPrompt.ts listens from import). The tip shows, so its absence
  // below is the switch, not a missed event.
  for (const key of FEATURE_KEYS) await setSwitch(request, key, key === 'pwa');
  const control = await viewerPage(browser, SIZES[0]);
  await control.goto('/');
  await whenSettled(control);
  await fireInstallPrompt(control);
  await expect(control.getByRole('heading', { name: TIP })).toBeVisible();
  await control.context().close();

  await setSwitch(request, 'pwa', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    // As a first-time visitor: no tour done, no tip dismissed.
    await viewer.goto('/');
    await whenSettled(viewer);
    await fireInstallPrompt(viewer);
    await viewer.waitForTimeout(2000); // past the tour's 1.5 s wait
    await expect(viewer.getByRole('dialog')).toHaveCount(0);
    await expect(viewer.getByRole('heading', { name: /^Club milestone/ })).toHaveCount(0);
    // The tip is for touch devices, so only the 390 run (with its positive control) proves "off".
    await expect(viewer.getByRole('heading', { name: TIP })).toHaveCount(0);
    await expect(viewer.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeVisible();
    for (const name of HOME_CARDS) {
      await expect(viewer.getByRole('heading', { name, exact: true }), name).toBeVisible();
    }
    await expect(viewer.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
    if (size.width < 600) await viewer.getByRole('button', { name: 'More' }).click();
    await expect(viewer.getByRole('link', { name: 'Glossary' })).toHaveCount(0);

    await viewer.goto('/shooters/3');
    await whenSettled(viewer);
    await expect(viewer.getByText('Summary card')).toHaveCount(0); // no title leak
    await viewer.goto('/club');
    await whenSettled(viewer);
    await expect(viewer.getByRole('heading', { name: /^Milestones/ })).toHaveCount(0);
    await viewer.goto('/glossary');
    await expect(viewer.getByRole('heading', { name: 'Page not found' })).toBeVisible();

    await viewer.goto('/about');
    await whenSettled(viewer);
    await expect(
      viewer.getByRole('region', { name: 'Your privacy' }).getByRole('listitem'),
    ).toHaveCount(5); // the link-preview sentence is behind its switch

    const features = await viewer.request.get('/api/features');
    expect(await features.json()).toEqual({ switches: {} });
    await viewer.context().close();
  }
  expect(await description(request)).toBe(GENERIC);
  expect((await request.get(`/api/og/image/sunday/${DAY}.png`)).status()).toBe(404);
});
```

`viewerPage` contexts get no fixture init scripts, so the tour and the tip meet a first-time visitor, which is the point of the all-off test. `HOME_CARDS` is every Home card a first-time viewer sees at the plan's base (spec D25: "every existing Home card is still present"); before running, open Home on the base stack as a first-time viewer and add any other unconditional card heading you see (for example "Top story" when the fixture has a hero insight), never a card that depends on the season or the data.

- [ ] **Step 5: Run it at both sizes**

Rebuild the stack (project `task19-10`, port 18082), make the auth states (`pnpm exec playwright test --project=setup`), then run: `pnpm exec playwright test --project=admin-mutations --no-deps features.admin-mutations.spec.ts about.spec.ts`.
Expected: the four mutation tests pass; then `pnpm exec playwright test about.spec.ts --project=desktop --project=mobile` passes. Afterwards `curl -s -b <admin cookie> http://localhost:18082/api/admin/features` shows every switch back on (the `afterEach` restored them).

- [ ] **Step 6: Run the frontend gates, then commit**

```bash
git add frontend/e2e/features.admin-mutations.spec.ts frontend/src/features/about/pages/AboutPage.tsx \
  frontend/src/features/about/pages/AboutPage.test.tsx frontend/src/features/about/privacy.test.ts \
  frontend/e2e/about.spec.ts
git commit -m "test(features): switch e2e incl. the all-off production default; About preview sentence (Plan 19 T10)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Owner preview (controller, after Wave 5 has merged into `feat/polish-reach`)**

Start a local stack from `feat/polish-reach` with production defaults. Copy `compose.test.yaml` to the scratchpad as `compose.preview.yaml`, delete its `FEATURES_DEFAULT_ON` line, and run `E2E_PORT=18090 IMAGE_TAG=preview docker compose -p preview19 -f compose.yaml -f <scratchpad>/compose.preview.yaml up -d --wait` (after a `build`). Log in as admin, open `/admin/features`, and show the owner: every feature switch off and "Never changed", "Page cache" on under "Infrastructure" (after Task 11), and each feature in admin preview (badges). Then flip each switch on, one at a time, and show it as a viewer in a second browser. Report the owner's go/no-go per switch; the switches themselves are flipped in production by the owner after the release, never by this plan.

---
### Task 11: Page cache (`task/19-11-page-cache`, wave 5)

**Files:**
- Create: `backend/migrations/versions/0009_response_cache.py`
- Create: `backend/src/sunday_clays/models/page_cache.py`; Modify: `backend/src/sunday_clays/models/__init__.py`
- Modify: `backend/tests/integration/models/test_schema_0001.py`
- Modify: `backend/src/sunday_clays/config.py` (`page_cache_enabled`)
- Modify: `backend/tests/conftest.py` (autouse: cache off in tests, inserted after `_fresh_settings_cache` near the top, never appended: T8 appends in the same wave)
- Modify: `backend/src/sunday_clays/domain/features.py` (`kind`, `default_on`, `page_cache`, the purge)
- Modify: `backend/src/sunday_clays/api/routes/features.py` (feature keys only)
- Modify: `backend/tests/unit/domain/test_features_copy.py`, `backend/tests/integration/api/test_features_api.py`, `backend/tests/integration/domain/test_features_store.py`
- Modify: `backend/src/sunday_clays/api/etag.py` (`_tag_inputs` also reads the switch; `request.state`)
- Create: `backend/src/sunday_clays/api/page_cache.py`
- Modify: `backend/src/sunday_clays/api/app.py` (`create_app(*, page_cache_allowlist=ALLOWLIST)` and one `add_middleware` line)
- Modify: `backend/tests/unit/api/test_role_wiring.py`, `backend/tests/unit/api/test_bodylimit.py`, `backend/tests/integration/test_db.py` (pass `page_cache_allowlist=()`)
- Create: `backend/src/sunday_clays/api/routes/admin_page_cache.py`
- Create: `backend/tests/unit/api/test_page_cache_pure.py`, `backend/tests/integration/api/test_page_cache_allowlist.py`, `backend/tests/integration/api/test_page_cache.py`, `backend/tests/integration/api/test_admin_page_cache_api.py`
- Modify: `frontend/src/features/admin-features/{api.ts, mocks.ts, copy.ts, copy.test.ts, pages/FeaturesPage.tsx, pages/FeaturesPage.test.tsx}`

**Interfaces:**
- Consumes: T1's `domain.features` and `/api/features`; T3's `/api/og/*` (excluded); T6's `/api/club/milestones` and T7's `/api/shooters/{id}/summary` (gated, excluded); `api.etag.{compute_etag, sorted_query, _dependency, CacheHeadersMiddleware}`; `auth.sessions.{COOKIE_NAME, load_session}`; `db.get_session`; `fastapi.routing.{iter_route_contexts, APIRoute}`.
- Produces (T12 relies on these):
  - Table `response_cache` (UNLOGGED) and model `models.ResponseCache`.
  - `config.Settings.page_cache_enabled: bool = True` (env `PAGE_CACHE_ENABLED`).
  - `domain.features`: `FeatureKey` gains `"page_cache"`; `Feature.kind: Literal["feature", "infrastructure"] = "feature"`, `Feature.default_on: bool = False`; `FEATURE_KEYS` (the six feature-kind keys); `FeatureSwitchOut.kind`; `LAST_WARM_KEY = "page_cache.last_warm"`; `infrastructure_switch_on(session, key) -> bool` (the one reader of an infrastructure switch: one primary-key lookup, missing row = `default_on`); `page_cache_on(session, settings) -> bool` (`PAGE_CACHE_ENABLED` and `infrastructure_switch_on(session, "page_cache")`).
  - `api.page_cache`: `ALLOWLIST: tuple[str, ...]`, constants `MAX_BODY_BYTES = 2 * 1024 * 1024`, `MAX_ROWS = 2000`, `PRUNE_TO_ROWS = 1500`, `MAX_KEY_URL = 2048`, `FOLLOW_TIMEOUT_S = 30.0`, `KEY_VERSION = "v1"`; `CachedRoute(template, regex, query_names)`; `resolve_allowlist(app, templates) -> tuple[CachedRoute, ...]`; `match_route(routes, path) -> CachedRoute | None`; `cache_key(app_version, data_version, local_date, role, path, query) -> str`; `storable(status, content_type, has_set_cookie, size) -> bool`; `PageCacheMiddleware`; `_open_session(app)` (the seam the fail-open test patches); `CACHE_HEADER = "X-Page-Cache"`.
  - `GET /api/admin/page-cache` → `PageCacheStatusOut(enabled, forced_off, rows, bytes, last_warm: LastWarmOut | None, current: CurrentKeyOut)` (T12 adds `targets`).

- [ ] **Step 1: Write the failing schema tests**

In `backend/tests/integration/models/test_schema_0001.py`, replace

```python
    "import_special_events",  # 0008 (Plan 17)
}
```

with

```python
    "import_special_events",  # 0008 (Plan 17)
    "response_cache",  # 0009 (Plan 19)
}
```

replace

```python
TABLES_0008 = {"import_special_events"}
```

with

```python
TABLES_0008 = {"import_special_events"}
TABLES_0009 = {"response_cache"}
```

replace

```python
OTHER_CHECKS = {
    "ck_insights_field_negative_unnamed": (
```

with

```python
OTHER_CHECKS = {
    "ck_response_cache_body_size": (
        "octet_length(body) <= 2097152",
        "CHECK ((octet_length(body) <= 2097152))",
    ),
    "ck_insights_field_negative_unnamed": (
```

and in `test_upgrade_downgrade_roundtrip` replace

```python
    _alembic(scratch_engine, "downgrade", "0007")  # 0008 drops its table and the event kind
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0008) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0006")  # 0007 drops only its four tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0007 - TABLES_0008) | {"alembic_version"}
    later = TABLES_0006 | TABLES_0007 | TABLES_0008
```

with

```python
    _alembic(scratch_engine, "downgrade", "0008")  # 0009 drops only the response cache
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0009) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0007")  # 0008 drops its table and the event kind
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0008 - TABLES_0009) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0006")  # 0007 drops only its four tables
    newer = TABLES_0007 | TABLES_0008 | TABLES_0009
    assert _tables(scratch_engine) == (C4_TABLES - newer) | {"alembic_version"}
    later = TABLES_0006 | newer
```

and append at the end of the file:

```python
def test_response_cache_is_unlogged_and_bounded(engine: Engine, session: Session) -> None:
    """Plan 19 D28: UNLOGGED (no WAL), a role check, and a 2 MiB body cap."""
    with engine.connect() as conn:
        persistence = conn.execute(
            text("SELECT relpersistence FROM pg_class WHERE relname = 'response_cache'")
        ).scalar_one()
    assert persistence == "u"
    insert = text(
        "INSERT INTO response_cache (key, data_version, local_date, app_version, role, route, body)"
        " VALUES (:k, 1, '2026-10-02', 'dev', :role, '/api/meta', :body)"
    )
    session.execute(insert, {"k": "ok", "role": "viewer", "body": b"{}"})
    for bad in ({"role": "guest", "body": b"{}"}, {"role": "viewer", "body": b"x" * 2097153}):
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(insert, {"k": "bad", **bad})


def test_response_cache_is_never_a_live_table() -> None:
    """D28: disposable. rebuild_live must never copy or swap it (explicit, not only implied by
    the exact LIVE_TABLES tuple in test_rebuild_live.py)."""
    from sunday_clays.domain.rebuild import LIVE_TABLES

    assert "response_cache" not in LIVE_TABLES
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: FAIL: `response_cache` is missing after `upgrade head`, and `downgrade 0008` fails with "Can't locate revision".

- [ ] **Step 3: Write the migration and the model**

Create `backend/migrations/versions/0009_response_cache.py`:

```python
"""response cache: finished JSON bodies of allowlisted viewer GET routes (Plan 19 §3.7)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-02

Expand-only: one new table the previous release never reads. UNLOGGED: no write-ahead log, so
stores are cheap; Postgres empties it after a crash, which is harmless for a cache. It is
disposable (never in domain/rebuild.py LIVE_TABLES), and a restore needs no step for it.
If Plan 20 merges first and takes 0009, renumber this file to the next free number and set
down_revision to the head on main at that moment (spec D5).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNLOGGED TABLE response_cache (
            key text NOT NULL,
            data_version integer NOT NULL,
            local_date date NOT NULL,
            app_version text NOT NULL,
            role text NOT NULL,
            route text NOT NULL,
            body bytea NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT pk_response_cache PRIMARY KEY (key),
            CONSTRAINT ck_response_cache_role CHECK (role IN ('viewer', 'admin')),
            CONSTRAINT ck_response_cache_body_size CHECK (octet_length(body) <= 2097152)
        )
        """
    )


def downgrade() -> None:
    op.drop_table("response_cache")
```

Create `backend/src/sunday_clays/models/page_cache.py`:

```python
"""The page cache (Plan 19 D28): one row per stored response body. Disposable and UNLOGGED."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, LargeBinary, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class ResponseCache(Base):
    __tablename__ = "response_cache"
    __table_args__ = (
        CheckConstraint("role IN ('viewer', 'admin')", name=conv("ck_response_cache_role")),
        CheckConstraint(
            "octet_length(body) <= 2097152", name=conv("ck_response_cache_body_size")
        ),
        {"prefixes": ["UNLOGGED"]},
    )

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    data_version: Mapped[int] = mapped_column(Integer, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    app_version: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

In `backend/src/sunday_clays/models/__init__.py`, replace

```python
from sunday_clays.models.ops import AppState, Job
```

with

```python
from sunday_clays.models.ops import AppState, Job
from sunday_clays.models.page_cache import ResponseCache
```

and replace

```python
    "PageViewRollup",
    "RatingHistory",
```

with

```python
    "PageViewRollup",
    "RatingHistory",
    "ResponseCache",
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: PASS (including `test_migration_matches_models` and `test_check_constraints_match_models`).

- [ ] **Step 5: Turn the cache off for pytest and add the setting**

In `backend/src/sunday_clays/config.py`, replace

```python
    public_base_url: str = "https://sundayclays.claysmasher.com"
```

with

```python
    public_base_url: str = "https://sundayclays.claysmasher.com"
    # Plan 19 D36: operator hard override; false bypasses the page cache whatever the switch says
    page_cache_enabled: bool = True
```

In `backend/tests/conftest.py`, insert the fixture right after the existing autouse settings fixture, near the top of the file, **not** at the end: T8 (same wave) appends `fx_special_admin_client` at the end, and two appends at end of file would conflict on merge. Replace

```python
@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> Iterator[None]:
    """Every test starts and ends with an empty ``get_settings`` cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

with

```python
@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> Iterator[None]:
    """Every test starts and ends with an empty ``get_settings`` cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# Plan 19 T11: the page cache is off in tests unless a test turns it on (D36)
@pytest.fixture(autouse=True)
def _page_cache_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Many integration tests write fixture rows without bumping data_version; with the cache on
    they would read each other's stored bodies. The page-cache tests set PAGE_CACHE_ENABLED=true."""
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
```

- [ ] **Step 6: Write the failing switch tests for `page_cache`**

In `backend/tests/unit/domain/test_features_copy.py`, replace

```python
def test_the_registry_holds_exactly_the_six_feature_keys_in_order() -> None:
    assert [f.key for f in FEATURES] == [
        "link_previews",
        "tour_glossary",
        "weekly_recap",
        "pwa",
        "club_milestones",
        "summary_card",
    ]
```

with

```python
def test_the_registry_holds_six_features_then_the_page_cache_kill_switch() -> None:
    assert [(f.key, f.kind, f.default_on) for f in FEATURES] == [
        ("link_previews", "feature", False),
        ("tour_glossary", "feature", False),
        ("weekly_recap", "feature", False),
        ("pwa", "feature", False),
        ("club_milestones", "feature", False),
        ("summary_card", "feature", False),
        ("page_cache", "infrastructure", True),
    ]
```

In `backend/tests/integration/api/test_features_api.py`, replace

```python
ALL_KEYS = {f.key for f in FEATURES}
```

with

```python
ALL_KEYS = {f.key for f in FEATURES if f.kind == "feature"}  # /api/features never lists page_cache
```

and append:

```python
def test_page_cache_is_never_in_api_features(
    viewer_client: TestClient, admin_client: TestClient
) -> None:
    assert "page_cache" not in viewer_client.get("/api/features").json()["switches"]
    assert "page_cache" not in admin_client.get("/api/features").json()["switches"]
    rows = admin_client.get("/api/admin/features").json()
    assert rows[-1]["key"] == "page_cache" and rows[-1]["kind"] == "infrastructure"
    assert rows[-1]["enabled"] is True  # missing row: on
```

In `backend/tests/integration/domain/test_features_store.py`, append:

```python
def _cache_rows(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM response_cache")).scalar_one())


def _put_cache_row(session: Session, key: str) -> None:
    session.execute(
        text(
            "INSERT INTO response_cache (key, data_version, local_date, app_version, role, route, body)"
            " VALUES (:k, 1, '2026-10-02', 'dev', 'viewer', '/api/meta', '{}')"
        ),
        {"k": key},
    )


def test_page_cache_missing_row_is_on_whatever_the_default_list_says(session: Session) -> None:
    assert features.read_switches(session, _settings(""))["page_cache"] is True
    assert features.read_switches(session, _settings("pwa"))["page_cache"] is True


def test_page_cache_on_needs_the_switch_and_the_setting(session: Session) -> None:
    on = Settings.model_construct(features_default_on="", timezone="UTC", page_cache_enabled=True)
    off = Settings.model_construct(features_default_on="", timezone="UTC", page_cache_enabled=False)
    assert features.page_cache_on(session, on) is True
    assert features.page_cache_on(session, off) is False
    features.set_switch(session, on, "page_cache", False)
    assert features.page_cache_on(session, on) is False


def test_page_cache_on_reads_only_its_own_row(
    session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Kills reading every switch (read_switches) on the request path: a corrupt row of another
    feature must not log a warning on every cached GET."""
    on = Settings.model_construct(features_default_on="", timezone="UTC", page_cache_enabled=True)
    _put_raw(session, "tour_glossary", '"on"')
    with caplog.at_level(logging.WARNING, logger="sunday_clays.domain.features"):
        assert features.page_cache_on(session, on) is True
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []
    _put_raw(session, "page_cache", '"on"')
    assert features.infrastructure_switch_on(session, "page_cache") is False  # corrupt is off


@pytest.mark.parametrize("enabled", [False, True])
def test_flipping_page_cache_purges_the_table_either_way(session: Session, enabled: bool) -> None:
    _put_cache_row(session, "a")
    _put_cache_row(session, "b")
    session.execute(
        text("INSERT INTO app_state (key, value) VALUES (:k, '{\"data_version\": 1}'::jsonb)"),
        {"k": features.LAST_WARM_KEY},
    )
    features.set_switch(session, _settings(), "page_cache", enabled)
    assert _cache_rows(session) == 0
    last_warm = session.execute(
        text("SELECT count(*) FROM app_state WHERE key = :k"), {"k": features.LAST_WARM_KEY}
    ).scalar_one()
    assert last_warm == (0 if enabled else 1)  # "on" also forgets the last warm-up


def test_flipping_a_feature_leaves_the_cache_alone(session: Session) -> None:
    _put_cache_row(session, "a")
    features.set_switch(session, _settings(), "summary_card", True)
    assert _cache_rows(session) == 1
```

- [ ] **Step 7: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/domain/test_features_copy.py tests/integration/api/test_features_api.py tests/integration/domain/test_features_store.py`
Expected: FAIL (`Feature` has no `kind`, no `page_cache` key, no `page_cache_on` or `infrastructure_switch_on`).

- [ ] **Step 8: Extend the registry**

In `backend/src/sunday_clays/domain/features.py`, replace

```python
FeatureKey = Literal[
    "link_previews",
    "tour_glossary",
    "weekly_recap",
    "pwa",
    "club_milestones",
    "summary_card",
]
KEY_PREFIX: Final = "feature."


@dataclass(frozen=True)
class Feature:
    key: FeatureKey
    label: str
    description: str
```

with

```python
FeatureKey = Literal[
    "link_previews",
    "tour_glossary",
    "weekly_recap",
    "pwa",
    "club_milestones",
    "summary_card",
    "page_cache",
]
FeatureKind = Literal["feature", "infrastructure"]
KEY_PREFIX: Final = "feature."
LAST_WARM_KEY: Final = "page_cache.last_warm"  # Plan 19 §3.7.1, written by the page_warm job


@dataclass(frozen=True)
class Feature:
    key: FeatureKey
    label: str
    description: str
    kind: FeatureKind = "feature"
    # infrastructure keys: the value of a missing row (FEATURES_DEFAULT_ON is never consulted)
    default_on: bool = False
```

replace

```python
    Feature(
        "summary_card",
        "Summary card",
        "A shareable card on every profile for the chosen time window.",
    ),
)
```

with

```python
    Feature(
        "summary_card",
        "Summary card",
        "A shareable card on every profile for the chosen time window.",
    ),
    Feature(
        "page_cache",
        "Page cache",
        "Keeps each page's finished answer ready, so pages open fast. Refreshed after every "
        "upload and each midnight. Turn off only if a page looks wrong. Turning it off clears "
        "everything stored.",
        kind="infrastructure",
        default_on=True,
    ),
)
#: The launch-switch keys the SPA reads (GET /api/features); infrastructure keys are not listed.
FEATURE_KEYS: Final[tuple[FeatureKey, ...]] = tuple(f.key for f in FEATURES if f.kind == "feature")
```

replace

```python
class FeatureSwitchOut(BaseModel):
    key: FeatureKey
    label: str
    description: str
```

with

```python
class FeatureSwitchOut(BaseModel):
    key: FeatureKey
    kind: FeatureKind
    label: str
    description: str
```

replace

```python
    if f.key not in rows:
        return f.key in _default_on(settings), None
```

with

```python
    if f.key not in rows:
        if f.kind == "infrastructure":
            return f.default_on, None
        return f.key in _default_on(settings), None
```

replace

```python
    return FeatureSwitchOut(
        key=f.key,
        label=f.label,
```

with

```python
    return FeatureSwitchOut(
        key=f.key,
        kind=f.kind,
        label=f.label,
```

replace

```python
def set_switch(session: Session, settings: Settings, key: str, enabled: bool) -> FeatureSwitchOut:
    """Upsert one switch; ``updated_at`` is the database's ``now()`` (D1)."""
    f = feature(key)
```

with

```python
def infrastructure_switch_on(session: Session, key: FeatureKey) -> bool:
    """One infrastructure switch, read by primary key (D31: "one primary-key lookup").

    The one reader for ``page_cache``: the ETag middleware (through ``page_cache_on``), the admin
    status route and the worker's scheduler (T12) all call it. It never reads
    ``FEATURES_DEFAULT_ON`` (a missing row is ``default_on``), and it reads only its own row, so a
    corrupt row of any other key logs nothing on the request path.
    """
    f = feature(key)
    assert f.kind == "infrastructure", key
    row = session.execute(
        text("SELECT value FROM app_state WHERE key = :k"), {"k": KEY_PREFIX + f.key}
    ).first()
    if row is None:
        return f.default_on
    stored = _stored(row[0], f.key)
    return False if stored is None else stored[0]


def page_cache_on(session: Session, settings: Settings) -> bool:
    """The page cache runs only with ``PAGE_CACHE_ENABLED`` true AND the switch on (D36).
    The setting is checked first, so with it false no query runs at all."""
    return settings.page_cache_enabled and infrastructure_switch_on(session, "page_cache")


def set_switch(session: Session, settings: Settings, key: str, enabled: bool) -> FeatureSwitchOut:
    """Upsert one switch; ``updated_at`` is the database's ``now()`` (D1).

    ``page_cache`` (D36): both directions empty ``response_cache`` in the same transaction (a
    request that read "on" just before a switch-off may store one row after it); "on" also
    forgets the last warm-up, so the next worker poll warms the pages from empty.
    """
    f = feature(key)
    if f.key == "page_cache":
        session.execute(text("DELETE FROM response_cache"))
        if enabled:
            session.execute(text("DELETE FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY})
```

In `backend/src/sunday_clays/api/routes/features.py`, replace

```python
from sunday_clays.domain.features import FeaturesOut, read_switches
```

with

```python
from sunday_clays.domain.features import FEATURE_KEYS, FeaturesOut, read_switches
```

and replace

```python
    switches = read_switches(session, settings)
    if role != "admin":
        switches = {key: True for key, on in switches.items() if on}
    return FeaturesOut(switches=switches)
```

with

```python
    every = read_switches(session, settings)
    switches = {key: every[key] for key in FEATURE_KEYS}  # never the infrastructure keys (D36)
    if role != "admin":
        switches = {key: True for key, on in switches.items() if on}
    return FeaturesOut(switches=switches)
```

- [ ] **Step 9: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/domain tests/integration/api/test_features_api.py tests/integration/domain/test_features_store.py`
Expected: PASS.

- [ ] **Step 10: Write the failing pure page-cache tests**

Create `backend/tests/unit/api/test_page_cache_pure.py`:

```python
"""Page-cache key, storability and bypass rules (Plan 19 D29, D32; §5.1)."""

import pytest

from sunday_clays.api import page_cache as pc

BASE = ("1.4.0", 412, "2026-10-02", "viewer", "/api/shooters/3", "as_of=2026-09-27&since=2026-08-03")


def test_the_same_request_gives_the_same_key_and_the_key_shape() -> None:
    assert pc.cache_key(*BASE) == pc.cache_key(*BASE)
    assert pc.cache_key(*BASE) == (
        "v1|1.4.0|412|2026-10-02|viewer|GET /api/shooters/3?as_of=2026-09-27&since=2026-08-03"
    )


@pytest.mark.parametrize("index", range(6))
def test_every_input_changes_the_key(index: int) -> None:
    changed = list(BASE)
    changed[index] = f"{changed[index]}x" if isinstance(changed[index], str) else 413
    assert pc.cache_key(*changed) != pc.cache_key(*BASE)  # type: ignore[arg-type]


def test_query_order_does_not_change_the_key() -> None:
    from starlette.requests import Request

    def query(raw: str) -> str:
        scope = {"type": "http", "query_string": raw.encode(), "headers": []}
        return pc.sorted_query(Request(scope))

    assert query("since=1&as_of=2") == query("as_of=2&since=1")


@pytest.mark.parametrize(
    ("status", "content_type", "cookie", "size", "ok"),
    [
        (200, "application/json", False, 10, True),
        (200, "application/json", False, pc.MAX_BODY_BYTES, True),
        (200, "application/json", False, pc.MAX_BODY_BYTES + 1, False),
        (200, "text/html; charset=utf-8", False, 10, False),
        (200, "application/json", True, 10, False),
        *[(s, "application/json", False, 10, False) for s in (201, 204, 304, 400, 401, 403, 404, 409, 422, 500)],
    ],
)
def test_storable(status: int, content_type: str, cookie: bool, size: int, ok: bool) -> None:
    assert pc.storable(status, content_type, cookie, size) is ok


def test_undeclared_parameters_and_long_urls_bypass() -> None:
    route = pc.CachedRoute("/api/events", pc.compile_template("/api/events"), frozenset({"year"}))
    assert pc.bypass_reason(route, "/api/events", [("year", "2026")]) is None
    assert pc.bypass_reason(route, "/api/events", [("_", "1")]) == "undeclared"
    long_value = "x" * pc.MAX_KEY_URL
    assert pc.bypass_reason(route, "/api/events", [("year", long_value)]) == "too_long"


def test_a_route_an_allowlisted_template_would_swallow_fails_startup() -> None:
    """A fixed GET route that an allowlisted regex matches would be served and stored under the
    wrong template (match_route is first-match). At the plan's base no route does (checked over
    all 60 GET routes)."""
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/api/shooters/compare")
    def compare() -> dict[str, str]:
        return {}

    @app.get("/api/shooters/{id}")
    def shooter(id: int) -> dict[str, int]:
        return {"id": id}

    with pytest.raises(ValueError, match="GET /api/shooters/compare also matches /api/shooters/"):
        pc.resolve_allowlist(app, ("/api/shooters/{id}",))
    assert [r.template for r in pc.resolve_allowlist(app, ())] == []
```

- [ ] **Step 11: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/unit/api/test_page_cache_pure.py`
Expected: FAIL, `ImportError: cannot import name 'page_cache'`.

- [ ] **Step 12: Write the failing behaviour tests (before any page-cache code)**

Create `backend/tests/integration/api/test_page_cache.py`:

```python
"""Page-cache behaviour against real Postgres (Plan 19 §5.2)."""

import asyncio
import logging
import threading
import time
from collections.abc import Iterator
from datetime import date
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version
from sunday_clays.api import page_cache as pc
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import _filters
from sunday_clays.api.routes import insights as insights_routes
from sunday_clays.auth.sessions import COOKIE_NAME, issue_session
from sunday_clays.config import Settings, get_settings

#: At least one real URL per ALLOWLIST template (the meta-test below enforces it).
SAMPLE_URLS: tuple[str, ...] = (
    "/api/insights/home",
    "/api/insights/club",
    "/api/insights/leaderboards",
    "/api/insights/records",
    "/api/insights/stations",
    "/api/insights/sundays/2026-09-27",
    "/api/insights/shooters/3",
    "/api/events",
    "/api/events?year=2026",
    "/api/events/2026-09-27",
    "/api/events/2026-09-27/achievements",
    "/api/leaderboards",
    "/api/leaderboards/movers",
    "/api/leaderboards/history?from=2025-09-28&to=2026-09-27",
    "/api/stations",
    "/api/stations/1",
    "/api/shooters/3/stations",
    "/api/club/summary?since=2026-08-03&as_of=2026-09-27",
    "/api/club/attendance",
    "/api/club/cohorts",
    "/api/club/distribution?by=year",
    "/api/club/first-rounds",
    "/api/club/regulars",
    "/api/club/conversion",
    "/api/club/parity?by=year",
    "/api/club/trends",
    "/api/records",
    "/api/achievements",
    "/api/achievements/doubleheader",
    "/api/shooters/3/achievements",
    "/api/shooters",
    "/api/shooters/3",
    "/api/shooters/3/rounds",
    "/api/shooters/3/special",
    "/api/shooters/3/rating",
    "/api/shooters/3/splits?by=year",
    "/api/shooters/3/insights",
    "/api/yir/2026",
    "/api/yir/2026/shooters/3",
    "/api/on-this-day",
)
SAME = ("content-type", "content-length", "cache-control", "etag")


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _cache_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
    get_settings.cache_clear()


def _rows(session: Session) -> list[Any]:
    return list(session.execute(text("SELECT key, role, local_date FROM response_cache")).all())


def test_every_template_has_a_sample() -> None:
    routes = [pc.CachedRoute(t, pc.compile_template(t), frozenset()) for t in pc.ALLOWLIST]
    covered = {pc.match_route(routes, url.split("?")[0]).template for url in SAMPLE_URLS}  # type: ignore[union-attr]
    assert covered == set(pc.ALLOWLIST)


@pytest.mark.parametrize("world", ["fx", "fx_special"])
def test_byte_identical_for_every_allowlisted_route(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, world: str
) -> None:
    client = cast(TestClient, request.getfixturevalue(f"{world}_viewer_client"))
    for url in SAMPLE_URLS:
        _cache_off(monkeypatch)
        a = client.get(url)
        assert a.status_code == 200, url
        monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
        get_settings.cache_clear()
        b, c = client.get(url), client.get(url)
        assert (b.headers["x-page-cache"], c.headers["x-page-cache"]) == ("miss", "hit"), url
        assert a.status_code == b.status_code == c.status_code
        assert a.content == b.content == c.content, url
        for name in SAME:
            assert a.headers.get(name) == b.headers.get(name) == c.headers.get(name), (url, name)
        revalidated = client.get(url, headers={"If-None-Match": c.headers["etag"]})
        assert revalidated.status_code == 304, url


def test_a_data_version_bump_serves_fresh_data(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both URLs are stored before the bump and their rows poisoned with a sentinel, so a "miss"
    after the bump proves the key moved (§5.2). Kills: a key without data_version."""
    urls = ("/api/shooters/3", "/api/insights/home")
    first = {url: fx_viewer_client.get(url) for url in urls}
    assert {r.headers["x-page-cache"] for r in first.values()} == {"miss"}
    assert "Hadley, Ike" in first["/api/shooters/3"].text
    assert len(_rows(fx_session)) == 2
    fx_session.execute(text("UPDATE response_cache SET body = '{\"sentinel\": 1}'"))
    for url in urls:  # control: before the bump, a hit serves the stored (poisoned) row
        poisoned = fx_viewer_client.get(url)
        assert poisoned.headers["x-page-cache"] == "hit" and "sentinel" in poisoned.text, url
    fx_session.execute(
        text("UPDATE shooter_profiles SET display_name = 'Hadley, Ivo' WHERE shooter_id = 3")
    )
    bump_data_version(fx_session)
    after = {url: fx_viewer_client.get(url) for url in urls}
    _cache_off(monkeypatch)
    for url, response in after.items():
        assert response.headers["x-page-cache"] == "miss", url
        assert "sentinel" not in response.text, url
        assert response.content == fx_viewer_client.get(url).content, url  # the uncached answer
    assert "Hadley, Ivo" in after["/api/shooters/3"].text


def test_the_local_date_rolling_over_serves_fresh_data(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = ("/api/club/trends", "/api/on-this-day", "/api/shooters/3")
    for day in (date(2026, 10, 2), date(2026, 10, 3)):
        monkeypatch.setattr(_filters, "today_local", lambda _tz, d=day: d)
        for url in urls:
            response = fx_viewer_client.get(url)
            assert response.headers["x-page-cache"] == "miss", (day, url)
            monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
            get_settings.cache_clear()
            assert fx_viewer_client.get(url).content == response.content, (day, url)
            monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
            get_settings.cache_clear()
    assert {r.local_date for r in _rows(fx_session)} == {date(2026, 10, 2), date(2026, 10, 3)}


def test_viewer_and_admin_bodies_never_cross(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_admin_client: TestClient,
    fx_session: Session,
) -> None:
    url = "/api/shooters/3"
    assert fx_viewer_client.get(url).headers["x-page-cache"] == "miss"
    assert fx_admin_client.get(url).headers["x-page-cache"] == "miss"
    assert sorted(r.role for r in _rows(fx_session)) == ["admin", "viewer"]
    fx_session.execute(text("UPDATE response_cache SET body = '{\"admin_only\": 1}' WHERE role = 'admin'"))
    assert "admin_only" not in fx_viewer_client.get(url).text
    fx_session.execute(text("UPDATE response_cache SET body = '{\"viewer_only\": 1}' WHERE role = 'viewer'"))
    assert "viewer_only" not in fx_admin_client.get(url).text


def test_excluded_routes_are_never_stored(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_admin_client: TestClient,
    fx_session: Session,
) -> None:
    device = "0b6d3a8e-2f40-4c55-9a51-6b1f3e1f0a11"
    gated = ("/api/club/milestones", "/api/shooters/3/summary?to=2026-09-27")
    calls: list[tuple[TestClient, str, str]] = [
        (fx_viewer_client, "GET", f"/api/bumps?keys=x&device_id={device}"),
        (fx_viewer_client, "GET", "/api/features"),
        (fx_viewer_client, "GET", "/api/meta"),
        (fx_viewer_client, "GET", "/api/health"),
        (fx_viewer_client, "GET", "/api/auth/me"),
        (fx_viewer_client, "GET", "/api/predictions/next"),
        (fx_viewer_client, "GET", "/api/weather/events"),
        (fx_viewer_client, "GET", "/api/og/page/events/2026-09-27"),
        (fx_admin_client, "GET", "/api/admin/features"),
        (fx_viewer_client, "GET", "/api/events/1999-01-03"),  # 404
        (fx_viewer_client, "GET", "/api/shooters/abc"),  # 422
        (fx_viewer_client, "GET", "/api/shooters/3?since=2026-09-27&as_of=2026-09-01"),  # 400
        (fx_viewer_client, "GET", "/api/events?_=1"),  # undeclared parameter
        (fx_viewer_client, "HEAD", "/api/events"),
        *[(c, "GET", url) for c in (fx_viewer_client, fx_admin_client) for url in gated],
    ]
    for client, method, url in calls:
        response = client.request(method, url)
        assert response.headers.get("x-page-cache") != "hit", url
    for key in ("club_milestones", "summary_card"):
        fx_admin_client.put(f"/api/admin/features/{key}", json={"enabled": True})
    for client, method, url in [(c, "GET", url) for c in (fx_viewer_client, fx_admin_client) for url in gated]:
        client.request(method, url)
    assert _rows(fx_session) == []
    bypassed = fx_viewer_client.get("/api/events?_=1")
    assert bypassed.headers["x-page-cache"] == "bypass"
    assert "x-page-cache" not in fx_viewer_client.get("/api/features").headers


def test_fail_open_with_one_warning_per_request_naming_only_the_template(
    cache_on: None,
    fx_viewer_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(app: FastAPI) -> Any:
        raise RuntimeError("database is gone")

    monkeypatch.setattr(pc, "_open_session", broken)
    for url in ("/api/shooters/3", "/api/events/2026-09-27"):
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="sunday_clays.api.page_cache"):
            response = fx_viewer_client.get(url)
        assert response.status_code == 200 and response.headers["x-page-cache"] == "bypass"
        (record,) = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert "{" in record.getMessage()  # the template, e.g. /api/shooters/{id}
        assert url not in record.getMessage()


def test_the_row_cap_serves_but_does_not_store(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pc, "MAX_ROWS", 2)
    for url in ("/api/events", "/api/records"):
        fx_viewer_client.get(url)
    third = fx_viewer_client.get("/api/achievements")
    assert third.status_code == 200 and third.headers["x-page-cache"] == "miss"
    assert len(_rows(fx_session)) == 2
    assert fx_viewer_client.get("/api/achievements").headers["x-page-cache"] == "miss"


def test_the_kill_switch(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_admin_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx_viewer_client.get("/api/events")
    assert len(_rows(fx_session)) == 1
    assert fx_admin_client.put("/api/admin/features/page_cache", json={"enabled": False}).status_code == 200
    assert _rows(fx_session) == []
    audits = fx_session.execute(
        text("SELECT details FROM audit_log WHERE action = 'feature_switch'")
    ).scalars().all()
    assert audits == [{"key": "page_cache", "enabled": False}]
    assert fx_viewer_client.get("/api/events").headers["x-page-cache"] == "bypass"
    assert _rows(fx_session) == []
    fx_admin_client.put("/api/admin/features/page_cache", json={"enabled": True})
    assert fx_viewer_client.get("/api/events").headers["x-page-cache"] == "miss"
    _cache_off(monkeypatch)
    assert fx_viewer_client.get("/api/events").headers["x-page-cache"] == "bypass"


@pytest.fixture
def live_app_cookie(committed_engine: Engine, auth_env: Settings, cache_on: None) -> str:
    return issue_session(get_settings(), "viewer")


async def _hit_many(apps: list[FastAPI], cookie: str, url: str, n: int) -> list[httpx.Response]:
    clients = [
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies={COOKIE_NAME: cookie},
        )
        for app in apps
    ]
    try:
        return await asyncio.gather(*[clients[i % len(clients)].get(url) for i in range(n)])
    finally:
        for client in clients:
            await client.aclose()


def _count_calls(monkeypatch: pytest.MonkeyPatch, module: Any, name: str) -> list[int]:
    calls: list[int] = []
    lock = threading.Lock()
    real = getattr(module, name)

    def counted(*args: Any, **kwargs: Any) -> Any:
        with lock:
            calls.append(1)
        time.sleep(0.3)  # long enough for every follower to arrive while the leader computes
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_stampede_computes_once_per_process(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _count_calls(monkeypatch, insights_routes, "held_dates")
    responses = asyncio.run(_hit_many([create_app()], live_app_cookie, "/api/insights/home", 10))
    assert len(calls) == 1
    assert len({r.content for r in responses}) == 1 and {r.status_code for r in responses} == {200}
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 1


def test_two_replicas_compute_at_most_twice_and_keep_one_row(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _count_calls(monkeypatch, insights_routes, "held_dates")
    apps = [create_app(), create_app()]
    responses = asyncio.run(_hit_many(apps, live_app_cookie, "/api/insights/home", 10))
    assert len(calls) <= 2
    assert len({r.content for r in responses}) == 1
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 1


def test_a_leaders_404_is_not_shared_and_not_stored(
    live_app_cookie: str, committed_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sunday_clays.analytics import frames

    calls = _count_calls(monkeypatch, frames, "load_calendar")
    responses = asyncio.run(_hit_many([create_app()], live_app_cookie, "/api/events/1999-01-03", 4))
    assert {r.status_code for r in responses} == {404}
    # D33: the leader's 404 is not storable, so each of the 3 followers runs the route itself
    # (one load_calendar per run). Kills sharing the leader's response with the followers.
    assert len(calls) == 4
    with Session(committed_engine) as s:
        assert s.execute(text("SELECT count(*) FROM response_cache")).scalar_one() == 0
```

Create `backend/tests/integration/api/test_admin_page_cache_api.py`:

```python
"""GET /api/admin/page-cache (Plan 19 §3.7.6)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version


def test_status_shape_for_an_admin(fx_admin_client: TestClient, fx_session: Session) -> None:
    response = fx_admin_client.get("/api/admin/page-cache")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers
    body = response.json()
    assert body["forced_off"] is True and body["enabled"] is False  # pytest default: off
    assert (body["rows"], body["bytes"], body["last_warm"]) == (0, 0, None)
    assert body["current"]["data_version"] == get_data_version(fx_session)


def test_viewer_gets_403(fx_viewer_client: TestClient) -> None:
    assert fx_viewer_client.get("/api/admin/page-cache").status_code == 403
```

- [ ] **Step 13: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_page_cache.py tests/integration/api/test_admin_page_cache_api.py`
Expected: FAIL. `test_page_cache.py` errors at import (`ModuleNotFoundError: No module named 'sunday_clays.api.page_cache'`) and `test_admin_page_cache_api.py` fails with 404 (no route yet). Paste this run as the RED for Steps 14–18.

- [ ] **Step 14: Write `api/page_cache.py` and read the switch in the ETag middleware**

Create `backend/src/sunday_clays/api/page_cache.py`:

```python
"""The page cache (Plan 19 §3.7, D28-D33): finished 200 JSON bodies of an exact allowlist of GET
routes, stored in ``response_cache`` and keyed by everything the body may depend on.

It is an inner middleware under ``CacheHeadersMiddleware``: the outer one reads data_version, the
local date and the ``page_cache`` switch once (``request.state``) and still adds Cache-Control and
the ETag (and answers 304) for a cached body exactly as for a computed one. No ETag is stored.
A hit never runs the route; that is safe because the pin tests prove an allowlisted route depends
only on require_viewer, the session, settings and its own path and query parameters.
"""

import asyncio
import contextlib
import logging
import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from fastapi import FastAPI, Request, Response
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import compile_path
from starlette.types import ASGIApp

from sunday_clays.api.etag import _dependency, _TagInputs, sorted_query
from sunday_clays.auth.sessions import COOKIE_NAME, load_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session

logger = logging.getLogger(__name__)

KEY_VERSION: Final = "v1"
MAX_BODY_BYTES: Final = 2 * 1024 * 1024
MAX_ROWS = 2000
PRUNE_TO_ROWS: Final = 1500
MAX_KEY_URL: Final = 2048
FOLLOW_TIMEOUT_S: Final = 30.0
CACHE_HEADER: Final = "X-Page-Cache"

#: Exact GET route templates (D30). A route joins only on purpose, after the pin tests pass.
ALLOWLIST: Final[tuple[str, ...]] = (
    "/api/insights/home",
    "/api/insights/club",
    "/api/insights/leaderboards",
    "/api/insights/records",
    "/api/insights/stations",
    "/api/insights/sundays/{date}",
    "/api/insights/shooters/{id}",
    "/api/events",
    "/api/events/{date}",
    "/api/events/{date}/achievements",
    "/api/leaderboards",
    "/api/leaderboards/movers",
    "/api/leaderboards/history",
    "/api/stations",
    "/api/stations/{label}",
    "/api/shooters/{id}/stations",
    "/api/club/summary",
    "/api/club/attendance",
    "/api/club/cohorts",
    "/api/club/distribution",
    "/api/club/first-rounds",
    "/api/club/regulars",
    "/api/club/conversion",
    "/api/club/parity",
    "/api/club/trends",
    "/api/records",
    "/api/achievements",
    "/api/achievements/{code}",
    "/api/shooters/{id}/achievements",
    "/api/shooters",
    "/api/shooters/{id}",
    "/api/shooters/{id}/rounds",
    "/api/shooters/{id}/special",
    "/api/shooters/{id}/rating",
    "/api/shooters/{id}/splits",
    "/api/shooters/{id}/insights",
    "/api/yir/{year}",
    "/api/yir/{year}/shooters/{id}",
    "/api/on-this-day",
)


@dataclass(frozen=True)
class CachedRoute:
    template: str
    regex: re.Pattern[str]
    query_names: frozenset[str]


def compile_template(template: str) -> re.Pattern[str]:
    """The path regex Starlette compiles for a route template (what FastAPI matches with)."""
    return compile_path(template)[0]


def _query_names(dependant: Dependant) -> set[str]:
    names = {str(field.alias) for field in dependant.query_params}
    for sub in dependant.dependencies:
        names |= _query_names(sub)
    return names


def resolve_allowlist(app: FastAPI, templates: Sequence[str]) -> tuple[CachedRoute, ...]:
    """Every template must name exactly one GET route of ``app``, or startup fails (D30)."""
    contexts = [
        c
        for c in iter_route_contexts(app.routes)
        if isinstance(c.original_route, APIRoute) and "GET" in (c.methods or set())
    ]
    resolved = []
    for template in templates:
        found = [c for c in contexts if c.path_format == template]
        if len(found) != 1:
            raise ValueError(f"page cache: {template} names {len(found)} GET routes, not 1")
        dependant = cast(Dependant, found[0].dependant)
        resolved.append(
            CachedRoute(template, compile_template(template), frozenset(_query_names(dependant)))
        )
    # match_route takes the first allowlisted regex that matches, not the route FastAPI will run.
    # So no other GET route may match an allowlisted regex: a later fixed route such as
    # /api/shooters/compare would otherwise be cached as /api/shooters/{id}, past the D30 pins.
    allowlisted = set(templates)
    for c in contexts:
        if c.path_format in allowlisted:
            continue
        clash = next((r.template for r in resolved if r.regex.match(c.path_format)), None)
        if clash is not None:
            raise ValueError(f"page cache: GET {c.path_format} also matches {clash}")
    return tuple(resolved)


def match_route(routes: Sequence[CachedRoute], path: str) -> CachedRoute | None:
    """The allowlisted route for ``path``; unambiguous because resolve_allowlist rejects any other
    GET route that an allowlisted regex matches."""
    return next((r for r in routes if r.regex.match(path)), None)


def cache_key(
    app_version: str, data_version: int, local_date: str, role: str, path: str, query: str
) -> str:
    """v1|<app_version>|<data_version>|<local_date>|<role>|GET <path>?<sorted query> (D29)."""
    return f"{KEY_VERSION}|{app_version}|{data_version}|{local_date}|{role}|GET {path}?{query}"


def storable(status: int, content_type: str | None, has_set_cookie: bool, size: int) -> bool:
    """Only a clean 200 JSON answer of at most 2 MiB, with no Set-Cookie, is stored (D32)."""
    media = (content_type or "").split(";")[0].strip()
    return status == 200 and media == "application/json" and not has_set_cookie and size <= MAX_BODY_BYTES


def bypass_reason(
    route: CachedRoute, path: str, query: Sequence[tuple[str, str]]
) -> str | None:
    """None when the request may use the cache; else why not (never logged with the URL)."""
    if any(name not in route.query_names for name, _ in query):
        return "undeclared"
    if len(path) + sum(len(n) + len(v) + 2 for n, v in query) > MAX_KEY_URL:
        return "too_long"
    return None


@contextlib.contextmanager
def _open_session(app: FastAPI) -> Iterator[Session]:
    """A short session of its own (honouring test overrides), never the route's."""
    provider = cast(Callable[[], Iterator[Session]], _dependency(app, get_session))
    with contextlib.contextmanager(provider)() as session:
        yield session


def _read(app: FastAPI, key: str) -> bytes | None:
    with _open_session(app) as session:
        body = session.execute(
            text("SELECT body FROM response_cache WHERE key = :k"), {"k": key}
        ).scalar()
    return None if body is None else bytes(body)


_INSERT = text(
    "INSERT INTO response_cache (key, data_version, local_date, app_version, role, route, body) "
    "SELECT :key, :data_version, CAST(:local_date AS date), :app_version, :role, :route, :body "
    "WHERE (SELECT count(*) FROM response_cache) < :max_rows "
    "ON CONFLICT (key) DO NOTHING"
)


def _write(
    app: FastAPI, key: str, inputs: _TagInputs, role: str, route: str, body: bytes
) -> None:
    with _open_session(app) as session:
        session.execute(
            _INSERT,
            {
                "key": key,
                "data_version": inputs.data_version,
                "local_date": inputs.local_date,
                "app_version": inputs.app_version,
                "role": role,
                "route": route,
                "body": body,
                "max_rows": MAX_ROWS,
            },
        )


def _tagged(response: Response, value: str) -> Response:
    response.headers[CACHE_HEADER] = value
    return response


def _hit(body: bytes) -> Response:
    return _tagged(Response(content=body, status_code=200, media_type="application/json"), "hit")


class PageCacheMiddleware(BaseHTTPMiddleware):
    """Serve, or compute once and store, allowlisted viewer GET bodies (§3.7.3)."""

    def __init__(self, app: ASGIApp, routes: tuple[CachedRoute, ...]) -> None:
        super().__init__(app)
        self.routes = routes
        self.flights: dict[str, asyncio.Future[bytes | None]] = {}

    def _key(self, request: Request, route: CachedRoute) -> tuple[str, _TagInputs, str] | None:
        if request.method != "GET":
            return None
        state: Any = request.state
        inputs = cast(_TagInputs | None, getattr(state, "tag_inputs", None))
        if inputs is None or not getattr(state, "page_cache_on", False):
            return None
        settings = cast(Settings, _dependency(cast(FastAPI, request.app), get_settings)())
        token = request.cookies.get(COOKIE_NAME)
        role = load_session(settings, token) if token else None
        query = request.query_params.multi_items()
        if role is None or bypass_reason(route, request.url.path, query) is not None:
            return None
        key = cache_key(
            inputs.app_version,
            inputs.data_version,
            inputs.local_date,
            role,
            request.url.path,
            sorted_query(request),
        )
        return key, inputs, role

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        route = match_route(self.routes, request.url.path)
        if route is None:
            return await call_next(request)  # not allowlisted: no header at all
        keyed = self._key(request, route)
        if keyed is None:
            return _tagged(await call_next(request), "bypass")
        key, inputs, role = keyed
        app = cast(FastAPI, request.app)
        try:
            body = await run_in_threadpool(_read, app, key)
        except Exception:
            logger.warning("page cache unavailable for %s; answering uncached", route.template)
            return _tagged(await call_next(request), "bypass")
        if body is not None:
            return _hit(body)
        flight = self.flights.get(key)
        if flight is not None:  # D33: a follower waits for the leader, then uses its body
            try:
                leader_body = await asyncio.wait_for(asyncio.shield(flight), FOLLOW_TIMEOUT_S)
            except TimeoutError:
                leader_body = None  # waited 30 s: compute alone, store nothing
            if leader_body is not None:
                return _hit(leader_body)
            return _tagged(await call_next(request), "miss")
        flight = asyncio.get_running_loop().create_future()
        self.flights[key] = flight
        shared: bytes | None = None
        try:
            response = await call_next(request)
            content = b"".join([chunk async for chunk in response.body_iterator])  # type: ignore[attr-defined]
            if storable(
                response.status_code,
                response.headers.get("content-type"),
                "set-cookie" in response.headers,
                len(content),
            ):
                shared = content
                try:
                    await run_in_threadpool(_write, app, key, inputs, role, route.template, content)
                except Exception:
                    logger.warning("page cache unavailable for %s; not stored", route.template)
            rebuilt = Response(content=content, status_code=response.status_code)
            rebuilt.raw_headers = [*response.raw_headers]  # the route's own headers, unchanged
            return _tagged(rebuilt, "miss")
        finally:
            if not flight.done():
                flight.set_result(shared)
            self.flights.pop(key, None)
```

`sorted_query` is imported from `api/etag.py`, so the key hashes exactly the string the ETag hashes (D29). Re-export it from this module for the unit test (`pc.sorted_query` is the same object).

In `backend/src/sunday_clays/api/etag.py`, replace

```python
from sunday_clays.config import get_settings
from sunday_clays.db import get_session
```

with

```python
from sunday_clays.config import get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.features import page_cache_on
```

replace

```python
def _tag_inputs(app: FastAPI) -> _TagInputs:
    """Everything the tag needs except the URL, read before the route runs (D2)."""
    settings = _dependency(app, get_settings)()
    provider = cast(Callable[[], Iterator[Session]], _dependency(app, get_session))
    with contextlib.contextmanager(provider)() as session:
        data_version = cache.read_data_version(session)
    local_date = _filters.today_local(settings.timezone).isoformat()
    return _TagInputs(settings.app_version, data_version, local_date)
```

with

```python
def _tag_inputs(app: FastAPI) -> tuple[_TagInputs, bool]:
    """Everything the tag needs except the URL, read before the route runs (D2), plus whether
    the page cache is on (Plan 19 D31: same session, so the cache costs no extra connection)."""
    settings = _dependency(app, get_settings)()
    provider = cast(Callable[[], Iterator[Session]], _dependency(app, get_session))
    with contextlib.contextmanager(provider)() as session:
        data_version = cache.read_data_version(session)
        cache_on = page_cache_on(session, settings)
    local_date = _filters.today_local(settings.timezone).isoformat()
    return _TagInputs(settings.app_version, data_version, local_date), cache_on
```

and replace

```python
        inputs: _TagInputs | None = None
        if etag_eligible(request.method, path) and request.cookies.get(COOKIE_NAME):
            inputs = await run_in_threadpool(_tag_inputs, cast(FastAPI, request.app))
        response = await call_next(request)
```

with

```python
        inputs: _TagInputs | None = None
        if etag_eligible(request.method, path) and request.cookies.get(COOKIE_NAME):
            inputs, cache_on = await run_in_threadpool(_tag_inputs, cast(FastAPI, request.app))
            # Plan 19 D31: the page cache (the inner middleware) keys on these same values.
            request.state.tag_inputs = inputs
            request.state.page_cache_on = cache_on
        response = await call_next(request)
```

`page_cache_on` reads `PAGE_CACHE_ENABLED` first and only then the `feature.page_cache` row (one primary-key lookup through `infrastructure_switch_on`, never `read_switches`), so with the setting false (every test but the page-cache ones) it adds no query at all, and a corrupt row of another feature never logs on the request path.

- [ ] **Step 15: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/api/test_page_cache_pure.py tests/unit/api/test_etag_helpers.py tests/integration/analytics_core/test_etag_middleware.py`
Expected: PASS (the ETag tests are unchanged: the tag inputs are the same values).

- [ ] **Step 16: Write the failing allowlist pin tests**

Create `backend/tests/integration/api/test_page_cache_allowlist.py`:

```python
"""The page-cache allowlist pins (Plan 19 D30; §5.1)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from sunday_clays.api import page_cache as pc
from sunday_clays.api.app import PUBLIC_ROUTE_MODULES, create_app
from sunday_clays.auth.deps import current_role, require_viewer
from sunday_clays.config import get_settings
from sunday_clays.db import get_session

ALLOWED: set[Callable[..., Any]] = {require_viewer, current_role, get_settings, get_session}
NEVER = (
    "/api/bumps",
    "/api/pageviews",
    "/api/features",
    "/api/meta",
    "/api/health",
    "/api/predictions/next",
    "/api/club/milestones",
    "/api/shooters/{id}/summary",
)


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return create_app()


def _context(app: FastAPI, template: str) -> Any:
    (found,) = [
        c
        for c in iter_route_contexts(app.routes)
        if isinstance(c.original_route, APIRoute)
        and c.path_format == template
        and "GET" in (c.methods or set())
    ]
    return found


def _problems(dependant: Dependant, where: str) -> list[str]:
    problems = []
    if dependant.request_param_name or dependant.response_param_name:
        problems.append(f"{where}: reads Request/Response")
    if dependant.cookie_params or dependant.header_params:
        problems.append(f"{where}: reads cookies or headers")
    if any(str(f.alias) == "device_id" for f in dependant.query_params):
        problems.append(f"{where}: takes a device_id")
    for sub in dependant.dependencies:
        if sub.call in ALLOWED:
            continue  # require_viewer -> current_role reads the cookie by design; that is the role
        if getattr(sub.call, "feature_gate_key", None) is not None:
            problems.append(f"{where}: has a feature_gate")
        else:
            problems.append(f"{where}: depends on {getattr(sub.call, '__name__', sub.call)}")
    return problems


def test_every_template_names_exactly_one_get_route(app: FastAPI) -> None:
    assert len(pc.resolve_allowlist(app, pc.ALLOWLIST)) == len(pc.ALLOWLIST)


def test_allowlist_has_no_gated_admin_or_public_route(app: FastAPI) -> None:
    problems = []
    for template in pc.ALLOWLIST:
        context = _context(app, template)
        module = context.original_route.endpoint.__module__.rsplit(".", 1)[-1]
        if module in PUBLIC_ROUTE_MODULES or module.startswith("admin_"):
            problems.append(f"{template}: from module {module}")
        problems += _problems(context.dependant, template)
    assert problems == []


@pytest.mark.parametrize("template", NEVER)
def test_named_exclusions_are_not_allowlisted(template: str) -> None:
    assert template not in pc.ALLOWLIST
    assert not any(t.startswith(("/api/weather/", "/api/og/", "/api/admin/")) for t in pc.ALLOWLIST)


def test_a_bogus_template_fails_startup() -> None:
    with pytest.raises(ValueError, match="/api/nope names 0 GET routes"):
        create_app(page_cache_allowlist=("/api/nope",))

```

- [ ] **Step 17: Run them to verify they fail, then wire the middleware**

Run: `cd backend && uv run pytest -q tests/integration/api/test_page_cache_allowlist.py`
Expected: FAIL: `create_app()` takes no `page_cache_allowlist` (TypeError).

In `backend/src/sunday_clays/api/app.py`, replace

```python
from collections.abc import AsyncIterator
```

with

```python
from collections.abc import AsyncIterator, Sequence
```

replace

```python
from sunday_clays.api.etag import CacheHeadersMiddleware
```

with

```python
from sunday_clays.api.etag import CacheHeadersMiddleware
from sunday_clays.api.page_cache import ALLOWLIST, PageCacheMiddleware, resolve_allowlist
```

replace

```python
def create_app() -> FastAPI:
```

with

```python
def create_app(*, page_cache_allowlist: Sequence[str] = ALLOWLIST) -> FastAPI:
    """``page_cache_allowlist``: tests that replace the routers pass ``()`` (Plan 19 D30)."""
```

and replace

```python
    app.add_middleware(CsrfGuardMiddleware)
```

with

```python
    app.add_middleware(CsrfGuardMiddleware)
    app.add_middleware(PageCacheMiddleware, routes=resolve_allowlist(app, page_cache_allowlist))
```

(The docstring line goes directly under the `def`, above `app = FastAPI(`. `CacheHeadersMiddleware` stays last, so it stays outermost and the page cache sits just inside it, D31.)

In `backend/tests/unit/api/test_role_wiring.py`, replace

```python
    return TestClient(app_module.create_app())
```

with

```python
    return TestClient(app_module.create_app(page_cache_allowlist=()))
```

In `backend/tests/unit/api/test_bodylimit.py`, replace

```python
    app = app_module.create_app()
```

with

```python
    app = app_module.create_app(page_cache_allowlist=())
```

In `backend/tests/integration/test_db.py`, replace

```python
    app = app_module.create_app()
```

with

```python
    app = app_module.create_app(page_cache_allowlist=())
```

Run: `cd backend && uv run pytest -q tests/integration/api/test_page_cache_allowlist.py tests/unit/api tests/integration/test_db.py`
Expected: PASS. If a pin names a dependency that reads only its own path or query parameters, add its callable to `ALLOWED` with a one-line comment; if it reads `Request`, cookies or headers, take the route out of `ALLOWLIST` instead (D30).

Then run the behaviour tests written in Step 12: `cd backend && uv run pytest -q tests/integration/api/test_page_cache.py tests/integration/api/test_admin_page_cache_api.py`
Expected: `test_page_cache.py` PASSES (the GREEN for Step 13's RED); any failure there is a real gap in Step 14's code, fixed there, never in the test. `test_admin_page_cache_api.py` still FAILS with 404 until Step 18.

- [ ] **Step 18: Write the admin status route**

Create `backend/src/sunday_clays/api/routes/admin_page_cache.py`:

```python
"""GET /api/admin/page-cache (Plan 19 §3.7.6): what the page cache holds and when it last warmed."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from sunday_clays.analytics.cache import read_data_version
from sunday_clays.api.routes import _filters
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import SessionDep
from sunday_clays.domain.features import LAST_WARM_KEY, page_cache_on

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LastWarmOut(BaseModel):
    data_version: int
    local_date: date
    finished_at: datetime
    warmed: int
    skipped: int
    failed: int
    seconds: float


class CurrentKeyOut(BaseModel):
    data_version: int
    local_date: date


class PageCacheStatusOut(BaseModel):
    enabled: bool  # the switch and PAGE_CACHE_ENABLED both on
    forced_off: bool  # PAGE_CACHE_ENABLED is false
    rows: int
    bytes: int
    last_warm: LastWarmOut | None
    current: CurrentKeyOut


@router.get("/page-cache")
def get_page_cache_status(
    session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]
) -> PageCacheStatusOut:
    rows, size = session.execute(
        text("SELECT count(*), coalesce(sum(octet_length(body)), 0) FROM response_cache")
    ).one()
    raw = session.execute(
        text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
    ).scalar()
    return PageCacheStatusOut(
        enabled=page_cache_on(session, settings),
        forced_off=not settings.page_cache_enabled,
        rows=int(rows),
        bytes=int(size),
        last_warm=None if raw is None else LastWarmOut.model_validate(raw),
        current=CurrentKeyOut(
            data_version=read_data_version(session),
            local_date=_filters.today_local(settings.timezone),
        ),
    )
```

- [ ] **Step 18b: Run every backend test**

Run: `cd backend && uv run pytest -q`
Expected: PASS. The full suite runs with the cache off (autouse), proving no existing test depends on it; the page-cache tests turn it on.

- [ ] **Step 19: Write the failing Features-page Infrastructure tests**

Run `cd frontend && pnpm gen:api`.

In `frontend/src/features/admin-features/mocks.ts`, add `kind: 'feature'` to each of the six rows, append the infrastructure row to `featureSwitches`:

```ts
  {
    key: 'page_cache',
    kind: 'infrastructure',
    label: 'Page cache',
    description:
      "Keeps each page's finished answer ready, so pages open fast. Refreshed after every upload and each midnight. Turn off only if a page looks wrong. Turning it off clears everything stored.",
    enabled: true,
    updated_at: null,
    updated_on: null,
  },
```

and add the status fixture and handler:

```ts
export const pageCacheStatus: PageCacheStatus = {
  enabled: true,
  forced_off: false,
  rows: 1240,
  bytes: 38_000_000,
  last_warm: {
    data_version: 412,
    local_date: '2026-10-02',
    finished_at: '2026-10-02T07:00:41+00:00',
    warmed: 27,
    skipped: 0,
    failed: 0,
    seconds: 41.2,
  },
  current: { data_version: 412, local_date: '2026-10-02' },
};
```

```ts
  http.get('*/api/admin/page-cache', () => HttpResponse.json(pageCacheStatus)),
```

(import `PageCacheStatus` from `./api`). In `frontend/src/features/admin-features/api.ts`, append:

```ts
export type PageCacheStatus = JsonOf<paths['/api/admin/page-cache']['get']>;

export function usePageCacheStatus() {
  return useQuery({
    queryKey: ['/api/admin/page-cache'],
    queryFn: () => unwrap(api.GET('/api/admin/page-cache')),
  });
}
```

and in `useSetFeatureSwitch`'s `onSuccess`, also invalidate `['/api/admin/page-cache']`.

In `frontend/src/features/admin-features/copy.test.ts`, append:

```ts
import { cacheStatusText, INFRA_INTRO } from './copy';
import { pageCacheStatus } from './mocks';

describe('page cache status line', () => {
  it('reports stored pages, size and the last refresh', () => {
    expect(cacheStatusText(pageCacheStatus)).toBe(
      '1,240 pages stored · 38 MB · last refreshed Oct 2, 2026 (27 pages in 41 s)',
    );
  });

  it('says refreshing when the last warm-up is for an older version or date', () => {
    const stale = { ...pageCacheStatus, current: { data_version: 413, local_date: '2026-10-02' } };
    expect(cacheStatusText(stale)).toBe('Refreshing…');
    const tomorrow = { ...pageCacheStatus, current: { data_version: 412, local_date: '2026-10-03' } };
    expect(cacheStatusText(tomorrow)).toBe('Refreshing…');
  });

  it('says never refreshed, off, and forced off', () => {
    expect(cacheStatusText({ ...pageCacheStatus, last_warm: null })).toBe('Not refreshed yet');
    expect(cacheStatusText({ ...pageCacheStatus, enabled: false })).toBe(
      'Off. Pages compute live and nothing is stored.',
    );
    expect(cacheStatusText({ ...pageCacheStatus, enabled: false, forced_off: true })).toBe(
      'Off for this deployment (PAGE_CACHE_ENABLED=false)',
    );
  });

  it('uses no banned word', () => {
    const lines = [
      INFRA_INTRO,
      cacheStatusText(pageCacheStatus),
      cacheStatusText({ ...pageCacheStatus, last_warm: null }),
    ];
    for (const text of lines) expect(text).not.toMatch(BANNED_WORDS);
  });
});
```

(merge the imports with the file's existing ones). In `frontend/src/features/admin-features/pages/FeaturesPage.test.tsx`, replace the first test's switch list assertion

```tsx
    const switches = await screen.findAllByRole('switch');
    expect(switches.map((s) => s.textContent)).toEqual(featureSwitches.map((f) => f.label));
```

with

```tsx
    const launch = await screen.findByRole('region', { name: 'Launch switches' });
    const switches = within(launch).getAllByRole('switch');
    expect(switches.map((s) => s.textContent)).toEqual(
      featureSwitches.filter((f) => f.kind === 'feature').map((f) => f.label),
    );
```

and append:

```tsx
describe('FeaturesPage infrastructure group', () => {
  it('lists the page cache under Infrastructure with its status line and no badge', async () => {
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    const infra = await screen.findByRole('region', { name: 'Infrastructure' });
    expect(
      within(infra).getByText('Behind-the-scenes settings. They change how fast pages open, never what they show.'),
    ).toBeInTheDocument();
    expect(within(infra).getByRole('switch', { name: 'Page cache' })).toHaveAttribute('aria-checked', 'true');
    expect(
      await within(infra).findByText('1,240 pages stored · 38 MB · last refreshed Oct 2, 2026 (27 pages in 41 s)'),
    ).toBeInTheDocument();
    expect(within(infra).queryByText('Admin preview')).not.toBeInTheDocument();
  });

  it('disables the toggle when the deployment forces the cache off', async () => {
    server.use(
      http.get('*/api/admin/page-cache', () =>
        HttpResponse.json({ ...pageCacheStatus, enabled: false, forced_off: true }),
      ),
    );
    renderWithProviders(<FeaturesPage />, { role: 'admin' });
    const infra = await screen.findByRole('region', { name: 'Infrastructure' });
    await within(infra).findByText('Off for this deployment (PAGE_CACHE_ENABLED=false)');
    expect(within(infra).getByRole('switch', { name: 'Page cache' })).toBeDisabled();
  });
});
```

(import `pageCacheStatus` from `../mocks`).

- [ ] **Step 20: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/admin-features`
Expected: FAIL (no `cacheStatusText`, no Infrastructure region).

- [ ] **Step 21: Write the Infrastructure group**

In `frontend/src/features/admin-features/copy.ts`, append:

```ts
import type { PageCacheStatus } from './api';

export const INFRA_INTRO =
  'Behind-the-scenes settings. They change how fast pages open, never what they show.';

/** The status line under "Page cache" (§3.7.6); dates come from the club-timezone local_date. */
export function cacheStatusText(status: PageCacheStatus): string {
  if (status.forced_off) return 'Off for this deployment (PAGE_CACHE_ENABLED=false)';
  if (!status.enabled) return 'Off. Pages compute live and nothing is stored.';
  const warm = status.last_warm;
  if (warm === null) return 'Not refreshed yet';
  if (warm.data_version !== status.current.data_version || warm.local_date !== status.current.local_date) {
    return 'Refreshing…';
  }
  const megabytes = Math.round(status.bytes / 1_000_000);
  return `${status.rows.toLocaleString('en-US')} pages stored · ${String(megabytes)} MB · last refreshed ${formatDate(warm.local_date)} (${String(warm.warmed)} pages in ${String(Math.round(warm.seconds))} s)`;
}
```

(the `import type` goes at the top of the file with the existing `formatDate` import).

In `frontend/src/features/admin-features/pages/FeaturesPage.tsx`, replace

```tsx
import { useFeatureSwitches, useSetFeatureSwitch, type FeatureSwitch } from '../api';
import { changedText, FEATURES_INTRO } from '../copy';
```

with

```tsx
import {
  useFeatureSwitches,
  usePageCacheStatus,
  useSetFeatureSwitch,
  type FeatureSwitch,
} from '../api';
import { cacheStatusText, changedText, FEATURES_INTRO, INFRA_INTRO } from '../copy';
```

replace

```tsx
function SwitchRow({
  row,
  onChange,
  pending,
}: {
  row: FeatureSwitch;
  onChange: (enabled: boolean) => void;
  pending: boolean;
}) {
  return (
    <li aria-label={row.label} className="flex flex-col gap-1 border-b border-outline-variant py-3 last:border-b-0">
      <Toggle label={row.label} checked={row.enabled} onChange={onChange} disabled={pending} />
      <p className="text-sm text-text-muted">{row.description}</p>
      <p className="text-xs text-text-muted">{changedText(row.updated_on)}</p>
    </li>
  );
}
```

with

```tsx
function SwitchRow({
  row,
  onChange,
  pending,
  status,
  locked = false,
}: {
  row: FeatureSwitch;
  onChange: (enabled: boolean) => void;
  pending: boolean;
  status?: string;
  locked?: boolean;
}) {
  return (
    <li aria-label={row.label} className="flex flex-col gap-1 border-b border-outline-variant py-3 last:border-b-0">
      <Toggle label={row.label} checked={row.enabled} onChange={onChange} disabled={pending || locked} />
      <p className="text-sm text-text-muted">{row.description}</p>
      <p className="text-xs text-text-muted">{changedText(row.updated_on)}</p>
      {status !== undefined && <p className="text-xs text-text-muted">{status}</p>}
    </li>
  );
}
```

and replace

```tsx
        <Card title="Launch switches">
          <ul className="flex flex-col">
            {query.data.map((row) => (
              <SwitchRow
                key={row.key}
                row={row}
                pending={mutation.isPending}
                onChange={(enabled) => change(row, enabled)}
              />
            ))}
          </ul>
        </Card>
```

with

```tsx
        <>
          <Card title="Launch switches">
            <ul className="flex flex-col">
              {query.data
                .filter((row) => row.kind === 'feature')
                .map((row) => (
                  <SwitchRow
                    key={row.key}
                    row={row}
                    pending={mutation.isPending}
                    onChange={(enabled) => change(row, enabled)}
                  />
                ))}
            </ul>
          </Card>
          <Card title="Infrastructure" subtitle={INFRA_INTRO}>
            <ul className="flex flex-col">
              {query.data
                .filter((row) => row.kind === 'infrastructure')
                .map((row) => (
                  <SwitchRow
                    key={row.key}
                    row={row}
                    pending={mutation.isPending}
                    locked={row.key === 'page_cache' && cache.data?.forced_off === true}
                    status={row.key === 'page_cache' && cache.data ? cacheStatusText(cache.data) : undefined}
                    onChange={(enabled) => change(row, enabled)}
                  />
                ))}
            </ul>
          </Card>
        </>
```

and add `const cache = usePageCacheStatus();` under `const mutation = useSetFeatureSwitch();`.

- [ ] **Step 22: Run them to verify they pass, then the e2e that lists switches**

Run: `cd frontend && pnpm exec vitest run src/features/admin-features`
Expected: PASS.

`frontend/e2e/admin-features.spec.ts` counts every `switch` on the page: update it to count six inside the "Launch switches" region and one ("Page cache") inside "Infrastructure":

```ts
  const launch = page.getByRole('region', { name: 'Launch switches' });
  await expect(launch.getByRole('switch')).toHaveCount(LABELS.length);
  await expect(page.getByRole('region', { name: 'Infrastructure' }).getByRole('switch', { name: 'Page cache' })).toBeVisible();
```

(replacing `await expect(page.getByRole('switch')).toHaveCount(LABELS.length);` and scoping the "Changed …" count to `launch`). Rebuild the stack (project `task19-11`, port 18081) and run: `pnpm exec playwright test admin-features.spec.ts home.spec.ts club.spec.ts shooters.spec.ts --project=desktop --project=mobile`.
Expected: PASS with the cache on in the stack (read-only projects now exercise hits).

- [ ] **Step 23: Run all gates, then commit**

```bash
git add backend/migrations/versions/0009_response_cache.py backend/src/sunday_clays/models/page_cache.py \
  backend/src/sunday_clays/models/__init__.py backend/tests/integration/models/test_schema_0001.py \
  backend/src/sunday_clays/config.py backend/tests/conftest.py backend/src/sunday_clays/domain/features.py \
  backend/src/sunday_clays/api/routes/features.py backend/tests/unit/domain/test_features_copy.py \
  backend/tests/integration/api/test_features_api.py backend/tests/integration/domain/test_features_store.py \
  backend/src/sunday_clays/api/etag.py backend/src/sunday_clays/api/page_cache.py backend/src/sunday_clays/api/app.py \
  backend/tests/unit/api/test_role_wiring.py backend/tests/unit/api/test_bodylimit.py backend/tests/integration/test_db.py \
  backend/src/sunday_clays/api/routes/admin_page_cache.py backend/tests/unit/api/test_page_cache_pure.py \
  backend/tests/integration/api/test_page_cache_allowlist.py backend/tests/integration/api/test_page_cache.py \
  backend/tests/integration/api/test_admin_page_cache_api.py frontend/src/features/admin-features \
  frontend/e2e/admin-features.spec.ts
git commit -m "feat(cache): page cache for allowlisted viewer GETs, kill switch and status (Plan 19 T11)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 12: Warm-up job, the SPA pin test and the Page cache runbook (`task/19-12-page-warm`, wave 6)

**Files:**
- Create: `backend/src/sunday_clays/jobs/page_warm.py`
- Modify: `backend/src/sunday_clays/jobs/scheduler.py` (one check), `backend/src/sunday_clays/jobs/worker.py` (pass `page_cache_enabled`)
- Modify: `backend/src/sunday_clays/api/routes/admin_page_cache.py` (`targets`)
- Modify: `backend/tests/integration/jobs/test_worker_loop.py` (the settings stub and one expected-kwargs line)
- Modify: `backend/tests/integration/api/test_admin_page_cache_api.py` (targets)
- Create: `backend/tests/integration/jobs/test_page_warm.py`, `backend/tests/integration/jobs/test_page_warm_schedule.py`
- Create: `frontend/e2e/page-cache.spec.ts`
- Modify: `frontend/e2e/features.admin-mutations.spec.ts` (one test)
- Modify: `deploy/README.md` (new "Page cache" section)

**Interfaces:**
- Consumes: T11's `api.page_cache` (`ALLOWLIST`, `MAX_ROWS`, `PRUNE_TO_ROWS`, `resolve_allowlist`, `match_route`), `domain.features.{LAST_WARM_KEY, infrastructure_switch_on}`, `/api/admin/page-cache`; `jobs.handlers.handler`; `jobs.queue.enqueue`; `jobs.scheduler._created_since`; `analytics.pipeline.get_data_version`; `api.routes._filters.{latest_scored_day, today_local}`; `auth.sessions.{issue_session, COOKIE_NAME}`; `api.app.create_app`; T10's `features.admin-mutations.spec.ts` helpers.
- Produces:
  - `jobs.page_warm`: `WARM_BUDGET_S = 180.0`, `RETRY_AFTER = timedelta(minutes=5)`, `WARM_BASE_URL = "http://page-warm.internal"`, `warm_targets(session, settings) -> list[str]` (`path?sorted query`, Home first), `prune(session, data_version, local_date) -> int`, `WarmReport(warmed, skipped, failed, seconds)`, `run_page_warm(session, settings, app, *, budget_s=WARM_BUDGET_S, clock=time.monotonic) -> WarmReport`, job kind `page_warm`.
  - `jobs.scheduler.schedule_due(..., page_cache_enabled: bool = False)`.
  - `PageCacheStatusOut.targets: list[str]`.

- [ ] **Step 1: Write the failing target and prune tests**

Create `backend/tests/integration/jobs/test_page_warm.py`:

```python
"""page_warm (Plan 19 §3.7.5, D34, D35; §5.1, §5.2)."""

import time
from datetime import date
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.api import page_cache as pc
from sunday_clays.api.routes import _filters
from sunday_clays.config import get_settings
from sunday_clays.domain.features import LAST_WARM_KEY
from sunday_clays.jobs import page_warm


@pytest.fixture
def cache_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
    get_settings.cache_clear()


def _put(session: Session, key: str, data_version: int, local_date: str) -> None:
    session.execute(
        text(
            "INSERT INTO response_cache (key, data_version, local_date, app_version, role, route, body)"
            " VALUES (:k, :dv, CAST(:ld AS date), 'dev', 'viewer', '/api/meta', '{}')"
        ),
        {"k": key, "dv": data_version, "ld": local_date},
    )


def _count(session: Session) -> int:
    return int(session.execute(text("SELECT count(*) FROM response_cache")).scalar_one())


def test_targets_follow_the_spa_defaults(fx_session: Session, test_settings: Any) -> None:
    targets = page_warm.warm_targets(fx_session, get_settings())
    assert targets[0] == "/api/insights/home"
    assert "/api/events/2026-09-27" in targets[:4]
    assert "/api/records?as_of=2026-09-27&since=2026-08-03" in targets
    assert "/api/stations?as_of=2026-09-27&era=current&since=2026-08-03" in targets
    assert "/api/leaderboards?metric=avg_score&period=season" in targets
    assert "/api/leaderboards/movers?period=season" in targets
    assert "/api/insights/leaderboards" in targets  # no season= at the default URL state
    assert (
        "/api/leaderboards/history?from=2025-09-28&metric=season_points&period=rolling_12"
        "&to=2026-09-27&top=10"
    ) in targets
    routes = pc.resolve_allowlist(cast(FastAPI, _app()), pc.ALLOWLIST)
    for target in targets:
        assert pc.match_route(routes, urlsplit(target).path) is not None, target
    assert len(targets) == len(set(targets))


def test_months_back_matches_the_spa() -> None:
    assert page_warm._months_back(date(2026, 9, 27), 12) == date(2025, 9, 28)
    assert page_warm._months_back(date(2026, 3, 31), 1) == date(2026, 3, 1)  # Feb 28 + 1 day


def test_prune_drops_other_versions_and_dates_then_the_oldest(
    fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pc, "PRUNE_TO_ROWS", 2)
    _put(fx_session, "old-version", 1, "2026-10-02")
    _put(fx_session, "old-date", 7, "2026-10-01")
    for i in range(3):
        _put(fx_session, f"keep-{i}", 7, "2026-10-02")
        fx_session.execute(
            text("UPDATE response_cache SET created_at = now() + make_interval(secs => :s) WHERE key = :k"),
            {"s": i, "k": f"keep-{i}"},
        )
    deleted = page_warm.prune(fx_session, 7, date(2026, 10, 2))
    assert deleted == 3
    keys = set(fx_session.execute(text("SELECT key FROM response_cache")).scalars())
    assert keys == {"keep-1", "keep-2"}  # the oldest current row went last


def _app() -> FastAPI:
    from sunday_clays.api.app import create_app

    return create_app()


def test_warm_stores_every_target_then_each_is_a_hit_with_the_same_body(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = cast(FastAPI, fx_viewer_client.app)
    report = page_warm.run_page_warm(fx_session, get_settings(), app)
    targets = page_warm.warm_targets(fx_session, get_settings())
    assert (report.warmed, report.skipped, report.failed) == (len(targets), 0, 0)
    assert _count(fx_session) == len(targets)
    for target in targets:
        hit = fx_viewer_client.get(target)
        assert hit.headers["x-page-cache"] == "hit", target
        monkeypatch.setenv("PAGE_CACHE_ENABLED", "false")
        get_settings.cache_clear()
        assert fx_viewer_client.get(target).content == hit.content, target
        monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
        get_settings.cache_clear()
    last = fx_session.execute(
        text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}
    ).scalar_one()
    assert last["data_version"] == get_data_version(fx_session)
    assert last["local_date"] == _filters.today_local(get_settings().timezone).isoformat()
    assert last["warmed"] == len(targets) and last["failed"] == 0


def test_a_zero_budget_skips_everything_and_still_completes(
    cache_on: None, fx_viewer_client: TestClient, fx_session: Session
) -> None:
    report = page_warm.run_page_warm(
        fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app), budget_s=0
    )
    assert report.warmed == 0 and report.skipped == len(page_warm.warm_targets(fx_session, get_settings()))
    assert _count(fx_session) == 0


def test_a_failing_target_is_counted_and_the_rest_still_warm(
    cache_on: None,
    fx_viewer_client: TestClient,
    fx_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        page_warm,
        "warm_targets",
        lambda _s, _settings: ["/api/events", "/api/events/2026-13-45", "/api/records"],
    )
    report = page_warm.run_page_warm(fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app))
    assert (report.warmed, report.failed) == (2, 1)
    assert "/api/events/{date}" in caplog.text and "2026-13-45" not in caplog.text


@pytest.mark.slow
def test_loose_ceilings(cache_on: None, fx_viewer_client: TestClient, fx_session: Session) -> None:
    """Memory: perf tests only catch gross regressions on any runner."""
    started = time.monotonic()
    page_warm.run_page_warm(fx_session, get_settings(), cast(FastAPI, fx_viewer_client.app))
    assert time.monotonic() - started < 120
    for target in page_warm.warm_targets(fx_session, get_settings()):
        hit_started = time.monotonic()
        fx_viewer_client.get(target)
        assert time.monotonic() - hit_started < 2, target
```

Create `backend/tests/integration/jobs/test_page_warm_schedule.py`:

```python
"""When page_warm is enqueued (Plan 19 §3.7.5; §5.1) and the single-worker invariant (§5.2)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, select, text, update
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import bump_data_version, get_data_version
from sunday_clays.config import Settings, get_settings
from sunday_clays.domain.features import LAST_WARM_KEY, set_switch
from sunday_clays.jobs import worker
from sunday_clays.jobs.queue import enqueue
from sunday_clays.jobs.scheduler import schedule_due
from sunday_clays.models import Job

PT = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 10, 2, 9, 0, tzinfo=PT)  # 09:00: the 03:00 rollup is due too; filter on kind


def _warm_jobs(session: Session) -> int:
    return len(session.scalars(select(Job.id).where(Job.kind == "page_warm")).all())


def _last_warm(
    session: Session, data_version: int, local_date: str, *, skipped: int = 0, failed: int = 0
) -> None:
    session.execute(
        text(
            "INSERT INTO app_state (key, value) VALUES (:k, jsonb_build_object("
            "'data_version', CAST(:dv AS int), 'local_date', CAST(:ld AS text), "
            "'skipped', CAST(:s AS int), 'failed', CAST(:f AS int))) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        ),
        {"k": LAST_WARM_KEY, "dv": data_version, "ld": local_date, "s": skipped, "f": failed},
    )


def _due(session: Session, now: datetime = NOW, enabled: bool = True) -> None:
    schedule_due(session, now, weather_enabled=False, page_cache_enabled=enabled)


def test_never_warmed_is_due(session: Session) -> None:
    _due(session)
    assert _warm_jobs(session) == 1


def test_a_new_data_version_is_due(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02")
    bump_data_version(session)
    _due(session)
    assert _warm_jobs(session) == 1


def test_a_new_local_date_is_due_a_minute_after_midnight(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02")
    _due(session, datetime(2026, 10, 3, 0, 1, tzinfo=PT).astimezone(UTC))
    assert _warm_jobs(session) == 1


def test_nothing_changed_is_not_due(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02")
    _due(session)
    assert _warm_jobs(session) == 0


def test_a_partial_warm_up_is_due_again_after_five_minutes(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02", skipped=3)
    _due(session)
    assert _warm_jobs(session) == 1  # same version and date, but 3 targets never warmed
    # Finished (so dedupe cannot absorb a second one) 4 minutes ago: the 5-minute gap holds it back.
    session.execute(
        update(Job)
        .where(Job.kind == "page_warm")
        .values(status="done", created_at=NOW - timedelta(minutes=4))
    )
    _due(session)
    assert _warm_jobs(session) == 1
    session.execute(update(Job).where(Job.kind == "page_warm").values(created_at=NOW - timedelta(minutes=6)))
    _due(session)
    assert _warm_jobs(session) == 2  # still partial and over 5 minutes: retried


def test_a_failed_warm_up_is_due_again(session: Session) -> None:
    _last_warm(session, get_data_version(session), "2026-10-02", failed=1)
    _due(session)
    assert _warm_jobs(session) == 1


def test_not_due_with_the_switch_off_or_the_setting_false(session: Session) -> None:
    _due(session, enabled=False)
    assert _warm_jobs(session) == 0
    set_switch(session, Settings.model_construct(features_default_on="", timezone="UTC"), "page_cache", False)
    _due(session)
    assert _warm_jobs(session) == 0


def test_a_recent_attempt_waits_five_minutes_and_dedupe_keeps_one_queued(session: Session) -> None:
    _due(session)
    session.execute(update(Job).where(Job.kind == "page_warm").values(created_at=NOW - timedelta(minutes=4)))
    _due(session)
    assert _warm_jobs(session) == 1  # under 5 minutes: not again
    session.execute(update(Job).where(Job.kind == "page_warm").values(created_at=NOW - timedelta(minutes=6)))
    _due(session)
    assert _warm_jobs(session) == 1  # due again, but the queued twin absorbs it (dedupe)


def test_warm_waits_for_the_recompute_commit_then_warms_the_new_version(
    committed_engine: Engine, auth_env: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§5.2 single worker: page_warm is never due while the recompute that bumps data_version is
    queued or running, only once its commit lands; the warm-up then records the bumped version.
    Kills: enqueueing page_warm from the rebuild/recompute handlers, or reading an uncommitted
    data_version."""
    monkeypatch.setenv("PAGE_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    timezone = get_settings().timezone
    with Session(committed_engine) as s:
        now = datetime.now(UTC)
        before = get_data_version(s)
        _last_warm(s, before, now.astimezone(ZoneInfo(timezone)).date().isoformat())
        enqueue(s, "recompute", dedupe_key="recompute")
        s.commit()
        schedule_due(s, now, weather_enabled=False, timezone=timezone, page_cache_enabled=True)
        assert _warm_jobs(s) == 0  # the recompute has not run: nothing to warm yet
        s.commit()
        assert worker.process_one(s, weather_enabled=False)  # runs the recompute, commits the bump
        after = get_data_version(s)
        assert after > before
        assert _warm_jobs(s) == 0  # the handlers enqueue nothing themselves (D35)
        schedule_due(s, now, weather_enabled=False, timezone=timezone, page_cache_enabled=True)
        s.commit()
        assert _warm_jobs(s) == 1
        while worker.process_one(s, weather_enabled=False):
            pass
        last = s.execute(text("SELECT value FROM app_state WHERE key = :k"), {"k": LAST_WARM_KEY}).scalar_one()
        assert last["data_version"] == after
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/jobs/test_page_warm.py tests/integration/jobs/test_page_warm_schedule.py`
Expected: FAIL: `ImportError: cannot import name 'page_warm'` and `schedule_due() got an unexpected keyword argument 'page_cache_enabled'`.

- [ ] **Step 3: Write the job**

Create `backend/src/sunday_clays/jobs/page_warm.py`:

```python
"""The ``page_warm`` job (Plan 19 §3.7.5, D34, D35): prune the page cache, then request the busiest
default pages through the real app, in process, as a viewer, so their bodies are stored before
the first visitor arrives. Counts are logged, never paths."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.api import page_cache as pc
from sunday_clays.api.routes._filters import latest_scored_day, today_local
from sunday_clays.auth.sessions import COOKIE_NAME, issue_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.domain.features import LAST_WARM_KEY
from sunday_clays.jobs.handlers import handler

logger = logging.getLogger(__name__)

WARM_BUDGET_S: Final = 180.0
RETRY_AFTER: Final = timedelta(minutes=5)
WARM_BASE_URL: Final = "http://page-warm.internal"
EIGHT_WEEK_DAYS: Final = 56  # lib/timeWindowChoice.ts
RACE_TOP: Final = 10  # features/race/labels.ts


def _months_back(anchor: date, months: int) -> date:
    """The SPA's monthsBack: anchor minus `months` calendar months (day clamped), plus one day."""
    index = anchor.year * 12 + (anchor.month - 1) - months
    year, month = divmod(index, 12)
    first_next = date(year + (month + 1) // 12, (month + 1) % 12 + 1, 1)
    last_day = (first_next - timedelta(days=1)).day
    return date(year, month + 1, min(anchor.day, last_day)) + timedelta(days=1)


def _url(path: str, **query: Any) -> str:
    """``path?sorted query``: the string the ETag and the page-cache key hash (etag.sorted_query)."""
    items = sorted((k, str(v)) for k, v in query.items() if v is not None)
    return f"{path}?{urlencode(items)}" if items else path


def warm_targets(session: Session, settings: Settings) -> list[str]:
    """The default-page requests in order of cost x visits (§3.7.5). Each entry is read from the SPA
    code that sends it at default URL state (no `w`, no filters, so no `round_type`); the e2e pin
    test (page-cache.spec.ts) guards that they stay equal."""
    anchor = latest_scored_day(session, settings.timezone)
    latest = anchor.isoformat()
    since = (anchor - timedelta(days=EIGHT_WEEK_DAYS - 1)).isoformat()
    window = {"since": since, "as_of": latest}
    return [
        # 1 Home
        "/api/insights/home",  # insights/homeWidget -> FeedSections.HomeInsights
        f"/api/events/{latest}",  # home/api.ts (LatestEventCard)
        "/api/events",  # TurnoutChart's fullscreen/CSV fetch (no year, no window)
        _url("/api/events", **{"from": since, "to": latest}),  # lib/windowEvents.ts (ClubPulse)
        # 2 Latest Sunday
        f"/api/insights/sundays/{latest}",  # insights/api.ts
        f"/api/events/{latest}/achievements",  # achievements/api.ts
        # 3 Sundays list (the latest year)
        _url("/api/events", year=anchor.year),  # events/api.ts useEvents(year)
        # 4 Stations: stations/api.ts sends era (page default 'current') plus the window
        _url("/api/stations", era="current", **window),
        "/api/insights/stations",
        # 5 Club: features/club/api.ts
        "/api/club/trends",
        _url("/api/club/summary", **window),  # useClubSummary(range)
        "/api/club/summary",  # useClubStatusByYear (ignores the window)
        _url("/api/club/first-rounds", **{"from": since, "to": latest}),
        "/api/club/attendance",
        "/api/club/cohorts",
        _url("/api/club/distribution", by="year"),
        "/api/club/regulars",
        "/api/club/conversion",
        _url("/api/club/parity", by="year"),
        "/api/insights/club",
        # 6 Leaderboards: at the default window the board and the movers send the period only
        # (boardWindow gives since = as_of = null; LeaderboardsPage.test "'/leaderboards' asks for
        # period season and since null"), and PageInsights sends no `season` without an `as_of`.
        _url("/api/leaderboards", metric="avg_score", period="season"),
        _url("/api/leaderboards/movers", period="season"),
        "/api/insights/leaderboards",
        # 7 Race (rolling 12 months): race/api.ts historyQuery, RACE_TOP, the 12M window
        _url(
            "/api/leaderboards/history",
            period="rolling_12",
            metric="season_points",
            top=RACE_TOP,
            **{"from": _months_back(anchor, 12).isoformat(), "to": latest},
        ),
        # 8 Records: records/api.ts recordsQuery (no limit on the page's first load)
        _url("/api/records", **window),
        "/api/insights/records",
        # 9 Trophies
        "/api/achievements",
    ]


def prune(session: Session, data_version: int, local_date: date) -> int:
    """Drop rows of another data_version or local date, then the oldest beyond pc.PRUNE_TO_ROWS
    (the one constant, shared with the middleware's own prune)."""
    stale = session.execute(
        text("DELETE FROM response_cache WHERE data_version <> :dv OR local_date <> :ld"),
        {"dv": data_version, "ld": local_date},
    ).rowcount
    extra = session.execute(
        text(
            "DELETE FROM response_cache WHERE key IN ("
            "SELECT key FROM response_cache ORDER BY created_at DESC OFFSET :keep)"
        ),
        {"keep": pc.PRUNE_TO_ROWS},
    ).rowcount
    return int(stale or 0) + int(extra or 0)


@dataclass(frozen=True)
class WarmReport:
    warmed: int
    skipped: int
    failed: int
    seconds: float


_LAST_WARM = text(
    "INSERT INTO app_state (key, value) VALUES (:k, jsonb_build_object("
    "'data_version', CAST(:dv AS int), 'local_date', CAST(:ld AS text), 'finished_at', now(), "
    "'warmed', CAST(:w AS int), 'skipped', CAST(:s AS int), 'failed', CAST(:f AS int), "
    "'seconds', CAST(:secs AS float8))) "
    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
)


def run_page_warm(
    session: Session,
    settings: Settings,
    app: FastAPI,
    *,
    budget_s: float = WARM_BUDGET_S,
    clock: Callable[[], float] = time.monotonic,
) -> WarmReport:
    started = clock()
    data_version = get_data_version(session)
    local_date = today_local(settings.timezone)
    prune(session, data_version, local_date)
    targets = warm_targets(session, settings)
    # Decision 9: commit the prune so no warm request waits on a row this job deleted, and end the
    # transaction warm_targets read in, so no idle-in-transaction connection is held for the budget.
    session.commit()
    routes = pc.resolve_allowlist(app, pc.ALLOWLIST)
    client = TestClient(
        app,
        base_url=WARM_BASE_URL,
        raise_server_exceptions=False,
        cookies={COOKIE_NAME: issue_session(settings, "viewer")},
    )
    warmed = failed = skipped = 0
    for index, target in enumerate(targets):
        if clock() - started >= budget_s:
            skipped = len(targets) - index
            break
        try:
            ok = client.get(target).status_code == 200
        except Exception:
            ok = False
        if ok:
            warmed += 1
        else:
            failed += 1
            route = pc.match_route(routes, urlsplit(target).path)
            logger.warning("page_warm: a target failed (%s)", route.template if route else "?")
    seconds = round(clock() - started, 1)
    session.execute(
        _LAST_WARM,
        {
            "k": LAST_WARM_KEY,
            "dv": data_version,
            "ld": local_date.isoformat(),
            "w": warmed,
            "s": skipped,
            "f": failed,
            "secs": seconds,
        },
    )
    logger.info(
        "page_warm: %d warmed, %d skipped, %d failed in %.1f s", warmed, skipped, failed, seconds
    )
    return WarmReport(warmed, skipped, failed, seconds)


@handler("page_warm")
def handle_page_warm(session: Session, payload: dict[str, Any]) -> None:
    from sunday_clays.api.app import create_app  # the worker builds the same app the API runs

    run_page_warm(session, get_settings(), create_app())
```

In `backend/src/sunday_clays/jobs/scheduler.py`, replace

```python
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Job
```

with

```python
from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.domain.features import LAST_WARM_KEY, infrastructure_switch_on
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import AppState, Job
```

replace

```python
ROLLUP_LOCAL_HOUR = 3  # Plan 16: page_view_rollup, once a local day, weather or not
```

with

```python
ROLLUP_LOCAL_HOUR = 3  # Plan 16: page_view_rollup, once a local day, weather or not
PAGE_WARM_RETRY = timedelta(minutes=5)  # Plan 19 D35: a failed or partial warm-up waits this long


def _page_warm_due(session: Session, now: datetime, timezone: str) -> bool:
    """The last warm-up's (data_version, local date) differs from now's, or it skipped or failed a
    target (D35: a partial or failed warm-up is retried), and none was tried in the last 5 minutes."""
    current = (get_data_version(session), now.astimezone(ZoneInfo(timezone)).date().isoformat())
    raw = session.scalar(select(AppState.value).where(AppState.key == LAST_WARM_KEY))
    if isinstance(raw, dict):
        last = (raw.get("data_version"), raw.get("local_date"))
        incomplete = bool(raw.get("failed")) or bool(raw.get("skipped"))
    else:
        last, incomplete = None, True
    stale = last != current or incomplete
    return stale and not _created_since(session, "page_warm", now - PAGE_WARM_RETRY)
```

replace

```python
    weather_enabled: bool,
    timezone: str = "America/Los_Angeles",
) -> list[int]:
    """Enqueue page_view_rollup (daily after 03:00 local), and with weather on, weather_sync
    (daily after 14:00 local) and forecast_refresh (every 6 h), when due."""
    local_now = now.astimezone(ZoneInfo(timezone))
    job_ids: list[int] = []
```

with

```python
    weather_enabled: bool,
    timezone: str = "America/Los_Angeles",
    page_cache_enabled: bool = False,
) -> list[int]:
    """Enqueue page_view_rollup (daily after 03:00 local), page_warm (after every data_version
    change and each local midnight, with the page cache on), and with weather on, weather_sync
    (daily after 14:00 local) and forecast_refresh (every 6 h), when due."""
    local_now = now.astimezone(ZoneInfo(timezone))
    job_ids: list[int] = []
    if (
        page_cache_enabled
        and infrastructure_switch_on(session, "page_cache")
        and _page_warm_due(session, now, timezone)
    ):
        job_ids.append(enqueue(session, "page_warm", dedupe_key="page_warm"))
```

In `backend/src/sunday_clays/jobs/worker.py`, replace

```python
                    weather_enabled=settings.weather_enabled,
                    timezone=settings.timezone,
                )
```

with

```python
                    weather_enabled=settings.weather_enabled,
                    timezone=settings.timezone,
                    page_cache_enabled=settings.page_cache_enabled,
                )
```

In `backend/tests/integration/jobs/test_worker_loop.py`, replace

```python
        lambda: SimpleNamespace(weather_enabled=False, timezone="America/Los_Angeles"),
```

with

```python
        lambda: SimpleNamespace(
            weather_enabled=False, timezone="America/Los_Angeles", page_cache_enabled=False
        ),
```

and replace

```python
    assert schedule_calls == [{"weather_enabled": False, "timezone": "America/Los_Angeles"}]
```

with

```python
    assert schedule_calls == [
        {"weather_enabled": False, "timezone": "America/Los_Angeles", "page_cache_enabled": False}
    ]
```

In `backend/src/sunday_clays/api/routes/admin_page_cache.py`, add `targets: list[str]  # warm_targets(): what page_warm requests` as the last field of `PageCacheStatusOut`, import `from sunday_clays.jobs.page_warm import warm_targets`, and pass `targets=warm_targets(session, settings)` in the constructor. In `backend/tests/integration/api/test_admin_page_cache_api.py`, add to `test_status_shape_for_an_admin`:

```python
    from sunday_clays.config import get_settings
    from sunday_clays.jobs.page_warm import warm_targets

    assert body["targets"] == warm_targets(fx_session, get_settings())
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/jobs tests/integration/api/test_admin_page_cache_api.py tests/integration/api/test_page_cache.py`
Expected: PASS.

- [ ] **Step 5: Run the whole backend suite and the gates**

Run the backend gates. Expected: clean, coverage ≥ 90%.

- [ ] **Step 6: Write the SPA pin e2e and the page-cache e2e**

Create `frontend/e2e/page-cache.spec.ts`:

```ts
import { request as pwRequest, type Page } from '@playwright/test';
import { ADMIN_STATE } from './authState';
import { expect, test } from './fixtures';
import { whenSettled } from './layout';

/** §3.7.5: the templates each default page must find warm. */
const PAGES: Record<string, RegExp[]> = {
  '/': [/^\/api\/insights\/home$/, /^\/api\/events\/\d{4}-\d{2}-\d{2}$/, /^\/api\/events$/],
  '/events/LATEST': [/^\/api\/insights\/sundays\/[\d-]+$/, /^\/api\/events\/[\d-]+\/achievements$/],
  '/events': [/^\/api\/events$/],
  '/stations': [/^\/api\/stations$/, /^\/api\/insights\/stations$/],
  '/club': [/^\/api\/club\/[a-z-]+$/, /^\/api\/insights\/club$/],
  '/leaderboards': [/^\/api\/leaderboards$/, /^\/api\/leaderboards\/movers$/, /^\/api\/insights\/leaderboards$/],
  '/race': [/^\/api\/leaderboards\/history$/],
  '/records': [/^\/api\/records$/, /^\/api\/insights\/records$/],
  '/achievements': [/^\/api\/achievements$/],
};
const NOT_WARMED = /^\/api\/club\/milestones$/; // gated: never cached

/** path + sorted query, as etag.sorted_query and warm_targets write it. */
function keyOf(raw: string): string {
  const url = new URL(raw);
  const items = [...url.searchParams.entries()].sort(([ak, av], [bk, bv]) =>
    ak === bk ? av.localeCompare(bv) : ak.localeCompare(bk),
  );
  const query = new URLSearchParams(items).toString();
  return query === '' ? url.pathname : `${url.pathname}?${query}`;
}

function record(page: Page, patterns: RegExp[]): string[] {
  const seen: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (request.method() !== 'GET') return;
    if (NOT_WARMED.test(url.pathname)) return;
    if (patterns.some((p) => p.test(url.pathname))) seen.push(keyOf(request.url()));
  });
  return seen;
}

test('warm targets are exactly what the SPA asks on each default page', async ({ page, baseURL }) => {
  const admin = await pwRequest.newContext({ baseURL, storageState: ADMIN_STATE });
  const status = (await (await admin.get('/api/admin/page-cache')).json()) as { targets: string[] };
  const latest = (await (await admin.get('/api/meta')).json()) as { last_score_date: string };
  await admin.dispose();
  const targets = new Set(status.targets);
  const missing: string[] = [];
  for (const [path, patterns] of Object.entries(PAGES)) {
    const seen = record(page, patterns);
    await page.goto(path.replace('LATEST', latest.last_score_date));
    await whenSettled(page);
    page.removeAllListeners('request');
    for (const key of seen) if (!targets.has(key)) missing.push(`${path}: ${key}`);
  }
  expect(missing, 'SPA requests with no warm target (fix warm_targets, not the SPA)').toEqual([]);
});

test('Home insights come from the cache, and per-person routes never carry the header', async ({ page }) => {
  await page.goto('/');
  await whenSettled(page);
  const home = await page.request.get('/api/insights/home');
  expect(home.headers()['x-page-cache']).toBe('hit');
  for (const path of ['/api/features', '/api/auth/me', '/api/bumps?keys=x']) {
    const response = await page.request.get(path);
    expect(response.headers()['x-page-cache'], path).toBeUndefined();
  }
});
```

In `frontend/e2e/features.admin-mutations.spec.ts`, append:

```ts
test('page cache off: viewers get the same Home, computed live; on again in afterEach', async ({
  page,
  request,
  browser,
}) => {
  await setSwitch(request, 'page_cache', false);
  for (const size of SIZES) {
    const viewer = await viewerPage(browser, size);
    await viewer.goto('/');
    await whenSettled(viewer);
    await expect(viewer.getByRole('heading', { name: 'Latest Sunday' })).toBeVisible();
    const home = await viewer.request.get('/api/insights/home');
    expect(home.status()).toBe(200);
    expect(home.headers()['x-page-cache']).toBe('bypass');
    await viewer.context().close();
  }
  await page.goto('/admin/features');
  const infra = page.getByRole('region', { name: 'Infrastructure' });
  await expect(infra.getByRole('switch', { name: 'Page cache' })).toHaveAttribute('aria-checked', 'false');
  await expect(infra.getByText('Admin preview')).toHaveCount(0);
});
```

- [ ] **Step 7: Run the e2e (the pin test guards `warm_targets`)**

Rebuild the stack (project `task19-12`, port 18080; wait about 10 s after `up` for the worker's first poll to run `page_warm`). Run: `pnpm exec playwright test page-cache.spec.ts --project=desktop --project=mobile`.
Expected: PASS in both projects. Every entry of `warm_targets` was read from the SPA code named in its comment, so the pin test is a guard, not the way the list gets written. If it does fail, it lists `<page>: <path?query>` keys the SPA sends that `warm_targets` lacks; that is a defect in this plan's reading of the SPA: stop and report the listed keys and the SPA file that sends each, rather than editing entries to make the test pass. Never change the SPA to fit `warm_targets`. (RED evidence for this spec is the run on the task base, where `/api/admin/page-cache` has no `targets`.)

Then run the mutation test: `pnpm exec playwright test --project=admin-mutations --no-deps features.admin-mutations.spec.ts`.
Expected: PASS, and every switch is back on afterwards.

- [ ] **Step 8: Write the runbook section**

In `deploy/README.md`, add before `## Backups and restore`:

```markdown
## Page cache

The busiest pages answer from a stored, finished response (the `response_cache` table, UNLOGGED,
in the existing Postgres). The worker refreshes it after every upload, rule change or recompute,
and just after local midnight (`page_warm`). It changes how fast an answer arrives, never what it
says: every stored answer is keyed by the data version, the local date and the role.

1. **After the deploy that ships it:** open `/admin/features` and check "Page cache" is on and its
   status line shows a refresh with no failures ("… last refreshed <date> (27 pages in 41 s)"). In
   the browser's network panel, a second load of Home shows `x-page-cache: hit` on
   `/api/insights/home`, and that request takes well under a second.
2. **If a page looks wrong after an upload:** turn "Page cache" off on `/admin/features`. That
   clears everything stored, and every page then computes live. Turn it back on once the cause is
   understood; the next worker poll warms the pages again. If the admin page itself is
   unavailable, set `PAGE_CACHE_ENABLED=false` on both the `api` and the `worker` services and
   redeploy the stack (on `api` alone, the worker's in-process app would keep warming and
   writing rows).
3. **Backups:** `response_cache` is disposable. A restore needs no step for it, and
   `pg_dump --exclude-table-data=response_cache` is safe if a smaller dump is wanted.
4. **Separate operator item, not part of this release:** whether to constrain the `api` and
   `worker` services to x86 nodes (a `node.platform.arch == x86_64` placement constraint in
   `compose.swarm.yaml`) is the owner's own decision. This release does not change placement, the
   images stay multi-arch, and the page cache must meet its targets on arm64 as well.
```

- [ ] **Step 9: Run all gates, then commit**

```bash
git add backend/src/sunday_clays/jobs/page_warm.py backend/src/sunday_clays/jobs/scheduler.py \
  backend/src/sunday_clays/jobs/worker.py \
  backend/src/sunday_clays/api/routes/admin_page_cache.py backend/tests/integration/jobs/test_worker_loop.py \
  backend/tests/integration/api/test_admin_page_cache_api.py backend/tests/integration/jobs/test_page_warm.py \
  backend/tests/integration/jobs/test_page_warm_schedule.py frontend/e2e/page-cache.spec.ts \
  frontend/e2e/features.admin-mutations.spec.ts deploy/README.md
git commit -m "feat(cache): page_warm after every data change and at midnight, pinned to the SPA (Plan 19 T12)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review (plan author, 2026-10-02)

- **Spec coverage.** §3.0 → T1, T2 (+T11 for `page_cache`); §3.1 → T3, T4; §3.2 → T2 (data), T5; §3.3 → T8; §3.4 → T3 (icons), T4 (headers), T9; §3.5 → T6; §3.6 → T7; §3.7 → T11, T12; §4 About sentence → T10; §5.1–§5.3 tests → each owning task; the production default (D25) → T10; runbooks §3.1.6 → T4, §3.7.8 → T12; owner preview → T10 Step 7.
- **Placeholders.** One place is finished by a failing test rather than by this document: the explainer `terms` retrofit in T5 Step 15 gives the exact procedure and treats the lint as the source of truth, as the spec does. The `warm_targets` query strings (T12) are read from the SPA code, each entry naming its source; the pin test only guards them.
- **Type consistency checked:** `FeatureKey`, `FEATURE_KEYS`, `switch_on` (feature-kind keys, `feature_gate`), `infrastructure_switch_on` (T11, the one reader of `page_cache`, used by `page_cache_on`, the admin status and T12's scheduler), `page_cache_on`, `LAST_WARM_KEY`, `api.page_cache.PRUNE_TO_ROWS` (one constant; `page_warm.prune` reads it, its test patches it); `feature_gate`; `PreviewFacts`; `trophy_title`; `club_milestones`; `useFeature`/`featureState`; `GlossaryTermId`; `useTourDone`; `downloadElementAsImage`; `cache_key`/`sorted_query`; `warm_targets`.
- **Review Focus** lines each name their tests (T1, T9, T4, T11, T12).

## Review decisions (adversarial review, 2026-10-02)

All 24 points were applied. Where the fix differs from the review's suggestion, or the review was partly wrong, the reason is here.

- **2 (conftest conflict).** Neither task takes over the other's fixture: T8 still appends `fx_special_admin_client` at the end, and T11 now inserts its autouse fixture after `_fresh_settings_cache` near the top. The hunks are far apart and merge cleanly, and both lanes stay runnable on their own.
- **11 (warm targets).** Every target is now read from the SPA and names its source. The review's example was wrong, though: at the default window `boardWindow` gives `since = as_of = null`, so `/api/leaderboards?metric=avg_score&period=season` and `/api/leaderboards/movers?period=season` were already right (`LeaderboardsPage.test.tsx` pins this). The real defect was `/api/insights/leaderboards?season=<year>`. `PageInsights` sends `season` only with an `as_of`, so the target is now plain `/api/insights/leaderboards`. `era=current` (stations) and records' `since`/`as_of` were confirmed. Step 7 no longer edits targets to make the pin test pass.
- **13 (concurrency test).** "Last" now comes from each writer's `clock_timestamp()` after its upsert, inside its own transaction. The second upsert waits on the first writer's row lock, so this needs neither `xmin` nor `updated_at` arithmetic. The two audit rows come from calling `set_switch` and `record_audit` in each thread, which are the route's two calls, not from an HTTP PUT. The threads run on `committed_engine` sessions, which the `admin_client` fixture's rolled-back session cannot share.
- **15 (afterEach).** Restoring only the keys whose value changed covers both halves of the point. `page_cache` is restored only when a test flipped it (T12's test does), so no `kind` check is needed.
- **12 (route matching).** The clash check lives in `resolve_allowlist`, and its test is in `test_page_cache_pure.py` (Step 10), so it has a real RED. At the plan's base none of the 60 GET routes clashes, and neither do Plan 19's new routes.
- **24 (trophy codes), plus a defect the review missed.** The plan's `events_attended:N` codes do not exist; the registry code is `events:N`, and Silver is `events:5`. The registry check also showed that Station Top Gun and Hardest Station Clean are category `stations`, not `competition`, so the plan's category filter would have counted and named them. This is fixed with a code set (Decision 17), and both the summary and the recap tests now cover a `stations`-category D14 trophy. The recap test's old name check (`"Hardest-Station Clean"`) would also never have matched the real name, "Hardest Station Clean".
- **20, 18 (spec amendments).** Both one-line amendments are in the spec (§5.1 race `from`, §3.7.8 step 2), marked as made by this review.
- **5 (milestones test).** The recap test runs one crossing on LATEST and one on the first Sunday, so it also kills a missing date filter, not only a missing switch check. The trophy test inserts its own D14 awards (`first_win`, `station_top_gun`) and does not rely on the fixture awarding one.

