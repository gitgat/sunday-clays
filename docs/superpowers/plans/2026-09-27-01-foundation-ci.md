# Plan 01 — Foundation & CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every implementer, reviewer and fix-loop agent runs on Opus. Tasks 1–4 have no CI yet: each merges after task review plus the local verification in its last steps (master §0 step 4a; paste that output into the PR body). Task 5 adds CI and is the first CI-gated PR; its implementer stops at the commit, and the push, first CI run and `ci-ok` canary are controller work ("Controller follow-up after Task 5", above Task 1, outside every task brief).

**Goal:** Stand up the backend and frontend skeletons, the container stack (Caddy, api, worker, Postgres 17, verified backups), a Playwright smoke suite and GitHub Actions CI with coverage ratchets, so every later plan lands through a green `ci-ok`.

**Architecture:** A uv-managed `sunday_clays` package: a FastAPI app factory with auto-discovered routers, lazily read pydantic-settings with `*_FILE` secrets, a pure-ASGI body-size limit, Alembic scaffolding whose `env.py` retries the first connect and takes an advisory lock, and a worker stub that honours the C6 worker-health contract. Next to it, a pnpm-managed React 19 + Vite 8 SPA whose routes are collected from `src/features/*/routes.tsx`. Two images (backend: api/worker/backup; frontend: Caddy + SPA) run from one Swarm-ready `compose.yaml`. CI builds the images once, runs Playwright against the stack, verifies a backup restore, and puts everything behind the single aggregate check `ci-ok`.

**Tech Stack:** Python 3.13.15 · uv 0.9.9 (uv_build) · FastAPI 0.141 / Starlette 1.7 · pydantic 2.13 + pydantic-settings 2.15 · SQLAlchemy 2.1 · Alembic 1.20 · psycopg 3.3 · pytest 9.1 + pytest-cov 7.1 + testcontainers 4.15 + httpx2 · ruff 0.16 · mypy 2.3 · Node 22.23 · pnpm 10.34.5 · React 19.3 · React Router 7.18 · Vite 8.3 · Vitest 5.0 · TypeScript 5.9 · ESLint 10 · Tailwind 4.3 · MSW 2.15 · Playwright 1.63 · Caddy 2.11.4 · Postgres 17 · Docker Compose · GitHub Actions · GHCR · lefthook 2. These versions were resolved and verified end to end on 2026-09-27; `uv lock` / `pnpm install` may resolve newer patch releases.

**Spec:** /Users/bryanmoran/code/sunday-clays/docs/superpowers/specs/2026-09-27-sunday-clays-design.md

**Master:** /Users/bryanmoran/code/sunday-clays/docs/superpowers/plans/2026-09-27-00-master.md (Architecture Contract C1–C12, §0 procedure, Sub-plan index)

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
The master's Review Focus items 1–5 are owned by Plans 02, 03, 06, 08 and 09. None of them belongs to this plan. Each of the five plan-specific failure modes below is pinned by tests in the task that owns the code:
1. **A misconfigured secret**: `X` and `X_FILE` both set, `X_FILE` pointing at a missing or empty file, a short `SESSION_SECRET`, or a password hash that is not argon2id. The api and worker then refuse to start, with a message that names the variable and the path and never echoes the value. Owner: Task 1 (`test_setting_both_var_and_file_names_both_and_hides_the_value`, `test_short_session_secret_is_rejected_without_echoing_it`, `test_non_argon2id_password_hash_is_rejected_without_echoing_it`, `test_startup_fails_on_conflicting_secret_sources`).
2. **An oversized or chunked request body**: a 12 MB workbook, a streamed upload with no `Content-Length`, or a 300 KB JSON login. A declared `Content-Length` over the limit gets 413 `payload_too_large` before routing, auth or multipart parsing. A body without `Content-Length` is counted as it is read and cut off with 413 as soon as the count passes the limit. A request that routing or auth rejects first (404/401/403) gets that status without its body being read. Never more than the limit is read. The API enforces this with or without Caddy in front. Caddy's edge limits sit slightly above the API's (264 KiB for `/api/*`, 11 MiB for `/api/admin/imports`): a declared `Content-Length` over them gets Caddy's own 413 before anything is proxied, with the API's JSON envelope and `Cache-Control: no-store`, and `request_body max_size` remains the backstop for chunked bodies. An unauthenticated chunked oversized upload therefore usually gets the API's 401 and occasionally Caddy's 413 (a pre-existing race). (Amended 2026-09-28 after the Plan 01 T4 review: "413 before auth" is impossible for chunked bodies without buffering, which would be worse.) Owner: Task 1 (`test_oversized_upload_with_content_length_never_reaches_the_parser`, `test_oversized_chunked_upload_is_rejected_without_touching_disk`, `test_chunked_body_is_cut_off_as_soon_as_it_passes_the_limit`) and Task 4 (e2e `oversized request bodies get 413 before any route runs`; `backend/tests/unit/api/test_edge_limits.py` pins the edge limits, the `Content-Length` guard and Caddy's 413 body).
3. **A start-order race**: api or worker up before Postgres, two api replicas migrating at once, or a worker started before migrations finish. `env.py` retries the first connect for up to 60 s and serialises on `pg_advisory_xact_lock(7263001)`. The worker heartbeats while it waits and exits 1 only after 180 s. Owner: Task 1 (`test_alembic_cli_retries_an_unreachable_database_before_failing`, `test_migrations_wait_for_the_advisory_lock`, `test_wait_for_schema_treats_connection_errors_as_not_current`, `test_wait_for_schema_keeps_waiting_while_a_revision_is_pending`, `test_main_exits_1_when_the_schema_never_becomes_current`).
4. **A PR merging while a CI job failed, was skipped or was cancelled, or a task PR lowering the coverage floor**. `ci-ok` fails on any `failure`, `cancelled` or `skipped` need; no other job has a job-level `if:`; the ratchet guard rejects `ratchets/` changes outside `chore/ratchet-*`; and the ratchet fails on any drop below baseline. Owner: Task 5 (`test_ci_ok_fails_on_failure_cancellation_or_skip`, `test_no_other_job_can_be_skipped_by_a_job_level_if`, `test_ratchet_guard_runs_on_pull_requests_after_a_full_history_checkout`, `test_ratchet_guard_blocks_ratchets_changes_outside_chore_branches`), Task 3 (`test_check_fails_when_backend_branch_coverage_drops`) and the live `ci-ok` canary in the controller follow-up after Task 5.
5. **Backups that silently stop protecting data**: a crash-restart loop writing dozens of dumps in one day, a DST change shifting the nightly slot, a `pg_dump` that fails or leaves a partial file, or a dump that cannot be restored. Retention is by date (newest dump per day for 14 days, newest per ISO week for 8 weeks). The 02:30 America/Los_Angeles slot is computed on UTC instants. A dump that fails or does not pass `pg_restore --list` exits 1, is never kept as `sc-*.dump`, leaves `last_success` alone and pings `<url>/fail`. Every CI run restores a fresh dump and compares row counts. Owner: Task 4 (`test_restart_loop_cannot_push_older_days_out`, `test_seconds_until_across_fall_back`, `test_failed_pg_dump_is_reported_as_a_failure`, `test_dump_that_pg_restore_cannot_list_is_never_kept`, `verify-restore.sh` in the e2e run).

## Decisions
Choices made here where the master is silent. Cross-plan auditors: the names below are what later plans consume.
1. **Pinned toolchain.** uv `0.9.9` in CI (`UV_VERSION`) and in `backend/Dockerfile`, matching the local Homebrew uv that writes `uv.lock`. `[tool.uv] required-version = ">=0.9.9"`. Bump all three together. The build backend is `uv_build`. Base images: `python:3.13.15-slim-trixie`, `node:22.23.3-trixie-slim`, `caddy:2.11.4-alpine`, `postgres:17` (as the master says). Node comes from a repo-root `.nvmrc` (`22`), pnpm `10.34.5` from `packageManager` via Corepack. Every GitHub Action, including `actions/*`, is pinned to a full SHA with a version comment.
2. **Resolved backend majors**, which later plans must write against: FastAPI 0.141 / Starlette 1.7, SQLAlchemy 2.1, pandas 3.0 (copy-on-write, `str` dtype by default), numpy 2.5, scipy 1.18, pydantic 2.13, pytest 9.1, mypy 2.3, ruff 0.16, testcontainers 4.15.
3. **Two dev packages beyond the master's list.** `httpx2`: Starlette 1.7's `TestClient` emits `StarletteDeprecationWarning` when only `httpx` is installed, and `filterwarnings = error` turns that into a failure. `httpx` stays the runtime client (Plan 05 + respx). `types-defusedxml`: defusedxml is the only untyped import found. `testcontainers` 4.15 ships type hints, so no `[[tool.mypy.overrides]]` is needed. Tests import `testcontainers.community.postgres`, because the old `testcontainers.postgres` path emits a DeprecationWarning.
4. **Frontend versions.** TypeScript `~5.9.3`: typescript-eslint 8.70 requires TS < 6.1 and openapi-typescript peers on `^5`. ESLint 10 + `@eslint/js` 10, because ESLint 9 is end-of-life. `eslint-plugin-react` 7.37.5 supplies `react/no-danger` and is allowed ESLint 10 through `pnpm.peerDependencyRules`. `eslint-plugin-react-hooks` 7 uses its flat `recommended` config. Others: `react-router ^7.18.4` (the master pins v7; v8 exists), `jsdom ^29.1.1` (jsdom 30 needs Node ≥ 22.22.2 or ≥ 24.15), Vite 8, Vitest 5, Tailwind 4.3, ECharts 6.1, lucide-react 1.48 (the home icon is `House`), msw 2.15 (its install script is ignored via `pnpm.ignoredBuiltDependencies`).
5. **Three frontend devDependencies beyond the master's list:** `@testing-library/dom` (a peer of `@testing-library/react`), `eslint-plugin-react` (needed for `react/no-danger`) and `@types/node` (config files and Playwright).
6. **Test command.** Under pnpm 10, `pnpm test -- --coverage` (the literal text of master §0 step 4a) forwards a literal `--` to Vitest, which then silently ignores `--coverage`. This plan, CONTRIBUTING.md and `ci.yml` use `pnpm test --coverage`. The controller should read §0 step 4a that way.
7. **Settings details.** `app_version` defaults to `"dev"`; the images set it from the `APP_VERSION` build arg, which `publish.yml` sets to `sha-<7>`. The Open-Meteo URL defaults are `https://archive-api.open-meteo.com/v1/archive` and `https://api.open-meteo.com/v1/forecast`. `hide_input_in_errors=True`, so no validation error echoes a secret. Env names are case-insensitive. Helpers: `config.ConfigError`, `config.SECRET_FIELDS`, `config.read_secret_env(name)`. `create_app()` stays settings-free; a FastAPI `lifespan` calls `get_settings()` (plus `configure_logging()`) at server startup, so a misconfigured secret fails uvicorn startup rather than the first request. Plan 05 T1 replaces the `club_lat`/`club_lon` defaults with 45.3525/-122.8082 (C2 allows exactly that) and, in the same PR, updates the two matching assert lines of Task 1's `test_defaults_match_the_contract` in `backend/tests/unit/test_config.py`; keep those two lines verbatim as `assert settings.club_lat == 45.3565` and `assert settings.club_lon == -122.8228`, because Plan 05 T1 Step 7 replaces them by exact text.
8. **`db.py` beyond C2.** `make_engine(url)` maps bare `postgresql://`/`postgres://` URLs to psycopg 3 and runs every session in UTC. `SessionFactory = sessionmaker(expire_on_commit=False)` is module-level and unbound; `get_session()` binds it from settings on first use, and tests and workers rebind it with `SessionFactory.configure(bind=engine)`. `alembic_config()` returns `./alembic.ini` if present (the image's `/app`), else the source tree's `backend/alembic.ini`. `connect_with_retry(engine, *, timeout_s=60.0, interval_s=2.0)` is used by `env.py`, which also accepts `-x connect_retry_seconds=<n>`.
9. **Naming convention.** `models.base.Base.metadata` carries `ix_%(table_name)s_%(column_0_N_name)s`, `uq_%(table_name)s_%(column_0_N_name)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s` and `pk_%(table_name)s`. There is deliberately no `ck` entry, so unnamed `CheckConstraint`s stay legal. Plan 03 T1's constraint names follow from this.
10. **Migration tooling.** `migrations/script.py.mako` generates modern typed revisions, and `alembic.ini` `post_write_hooks` run `ruff check --fix` and `ruff format` on every generated revision.
11. **Routers.** Each `api/routes/*` module declares full `/api/...` paths, e.g. `APIRouter(prefix="/api")`. `create_app()` includes every discovered router with no prefix and, until Plan 04 T1, no dependencies. `discover_routers()` raises `TypeError` for a public module without `router: APIRouter`.
12. **`logging.py`** (in C1 but unassigned) provides `configure_logging(level: int = logging.INFO) -> None`, used by the lifespan and the worker.
13. **conftest additions** (all Plan 01 T1). `_fresh_settings_cache` (autouse). `closed_port`. `password_hashes` (argon2id, m=19456, t=2, p=1, of `VIEWER_TEST_PASSWORD = "viewer-test-password"` and `ADMIN_TEST_PASSWORD = "admin-test-password"`). `settings_env`: a valid, DB-free env with `COOKIE_SECURE=false`. `test_settings`: `settings_env` plus the real test DB URL; the `client` fixture uses it. `database_url` (session scope). On macOS the testcontainers Ryuk socket is overridden to `/var/run/docker.sock`. pytest runs with `--import-mode=importlib`; coverage uses `source = ["src"]`.
14. **Worker stub names** (Plan 03 T7 keeps all except `idle_until_stopped`): `HEARTBEAT_PATH`, `POLL_SECONDS = 2.0`, `SCHEMA_TIMEOUT_SECONDS = 180.0`, `touch_heartbeat(path)`, `wait_for_schema(engine, stop, *, timeout_s, poll_s, heartbeat) -> bool`, `idle_until_stopped(stop, *, poll_s, heartbeat)` and `main() -> int`.
15. **Frontend shell names.** `app/registry.ts` exports `NavItem`, `FeatureModule`, `collectFeatures`, `featureRoutes` and `navItems`. `app/router.tsx` exports `appRoutes` (one root route `{ path: '/', children: featureRoutes }`) and `createAppRouter()`. Feature routes are relative children of that root: `index: true` or `'events'`, never `'/events'`. `test/render.tsx` exports `renderWithProviders(ui, { route })` and `renderRoute(route, routes = appRoutes)`. `src/theme/theme.css` is created here holding only `@import 'tailwindcss'`; Plan 07 T1 adds its `@theme` tokens to that file. `test/msw/handlers.ts` merges `handlers` from every `features/*/mocks.ts`. MSW runs with `onUnhandledRequest: 'error'`. `navigator.canShare` defaults to `false`. `test/setup.ts` sets undici's global origin (`Symbol.for('undici.globalOrigin.1')`) to `window.location.origin`, so relative `/api/...` URLs in `fetch` and `new Request` resolve as in a browser; C10's `baseUrl: ''` client depends on it (Plan 07 D6).
16. **Frontend coverage.** Thresholds are lines 90 and branches 90, the two metrics the contract gates. Coverage also excludes `src/test/**` (test harness) and the test files.
17. **Ratchet artifacts.** CI artifacts are named `backend-coverage` (`coverage.xml`), `frontend-coverage` (`coverage-summary.json`) and `bundle-stats` (`bundle-stats.json`). `scripts/ratchet.py` reads them from `artifacts/<name>/`, the layout `gh run download -D artifacts` produces. `entry_js_gz_kb` counts the Vite entry chunk plus its static-import closure, i.e. the JS a first page load fetches. `artifacts/` and `bundle-stats.json` are gitignored.
18. **Backups.** `backend/backup/backup_tools.py` (stdlib; `prune`, `seconds-until`) is unit-tested in `backend/tests/unit/backup/test_backup_tools.py`; `backup.sh --once` is run against stub `pg_dump`/`pg_restore` and a local Healthchecks stand-in in `test_backup_sh.py`. Retention keeps the newest dump per UTC day for 14 days and the newest per ISO week for 8 weeks. `backup.sh` waits up to 120 s for Postgres before the startup dump. `dump_once` is only ever called as an `if` condition, where bash ignores `set -e`, so each of its steps ends in `|| return 1`. A failed dump pings `<url>/fail` and leaves the container running, where its healthcheck turns unhealthy. The Healthchecks URL is a Swarm-only secret `backup_hc_url` read through `BACKUP_HC_URL_FILE`; an empty or missing file means no ping.
19. **Secret files.** `dev-secrets.sh` writes files mode 644 inside a mode-700 `secrets/` directory. Compose bind-mounts file secrets with their host permissions, and the uid-10001 containers must be able to read them. `deploy/README.md` tells the operator to `chmod 600` real Swarm secret files.
20. **`WEATHER_ENABLED=false` for the worker too.** `compose.test.yaml` sets it on the worker as well as the api, because C2's no-op scheduler and handlers run in the worker.
21. **Caddy caching.** `/assets/*` has its own `handle`: only a file that exists gets `Cache-Control: public, max-age=31536000, immutable`, and a missing chunk is a plain 404 with no `Cache-Control`. Every other path gets `no-cache` and the SPA fallback (`try_files {path} /index.html`), so no stale HTML is ever cached as a year-long asset. (`try_files` accepts no matcher; `try_files @name …` treats `@name` as a file name.) The security headers live in a `(security_headers)` snippet imported both in the site and in `handle_errors`, because Caddy drops headers already set when a handler fails; that keeps them on 404 and 413 responses too, with `Server` still removed (master Plan 01 T4: "Headers on all responses").
22. **Swarm required-variable messages** must not contain `-`: `docker stack config` reads `${VAR:?a-b}` as `${VAR:-b}`. The images use `${IMAGE_TAG:?IMAGE_TAG is required}`.
23. **`.gitignore` additions.** `**/e2e/.auth/` (Task 4): the existing `e2e/.auth/` entry matches only a root-level `e2e/`, so Plan 04's `frontend/e2e/.auth/*.json` session files would otherwise be committable. `artifacts/` and `bundle-stats.json` (Task 3).
24. **Playwright.** The `mobile` project is Desktop Chrome at 390×844 with `deviceScaleFactor: 3`, `isMobile` and `hasTouch`. CI uses 1 retry and an HTML report. `e2e/fixtures.ts` exposes the auto fixture `pageProblems: string[]`. Two `test.fail` self-tests prove the fixture catches a page error and a CSP violation.
25. **Extra repo-script tests** beyond C1's list: `scripts/tests/test_dev_secrets.py` and `scripts/tests/test_setup_branch_protection.py`, the latter against a fake `gh` on `PATH`.
26. **CI and runtime tunables.**
    - CI runs on `ubuntu-24.04` with per-job `timeout-minutes`. The `backend` job's Postgres service is `postgres:17` with `postgres`/`postgres` and database `sunday_clays_test`.
    - Buildx builds `platforms: linux/amd64`. Image tars travel as 1-day artifacts at compression level 1.
    - Dependabot groups each ecosystem into one monthly PR.
    - Compose healthcheck intervals: api, worker and caddy 30 s; db 10 s; backup 60 s. Timeouts are 5 s; caddy's `start_period` is 20 s.
    - The backend image installs the package non-editable with compiled bytecode.
    - `lefthook install` (Task 5) activates the hooks for every worktree of the clone.
27. **Worker process test.** `test_worker_module_heartbeats_and_stops_cleanly_on_sigterm` runs the real `worker.main()` in a subprocess with `HEARTBEAT_PATH` pointed at a private temporary file, and waits for that file, not for log text. Plan 03 T7 may therefore reword the worker's log lines freely, and parallel worktrees never mistake each other's `/tmp/worker-heartbeat` for this worker's. The test keeps its `(test_settings: Settings)` signature and its `env` dict, which Plan 03 T7 edits. The worker must keep the heartbeat and the clean SIGTERM/SIGINT exit.
28. **Plan 01 tests stay valid as later plans extend the app.** They never depend on the real router set or on GET-only middleware. Discovery tests replace the routes package's `__path__` with two temporary directories. `upload_probe` patches `sunday_clays.api.app.discover_routers` to return `[]`, the name Plan 04 T1's wiring test patches, so Plan 04 T2's real admin-only `POST /api/admin/imports` never shadows the probe. The error-handler probes are POST routes, clear of Plan 06 T1's `CacheHeadersMiddleware`, which reads settings and the database before every eligible GET. No later plan needs to edit these test files.

## File Structure
Task 1 (backend skeleton):
- `backend/pyproject.toml` / `backend/uv.lock`: complete Phase-1 backend dependency set + ruff/mypy/pytest/coverage config.
- `backend/src/sunday_clays/__init__.py`, `api/__init__.py`, `domain/__init__.py`, `jobs/__init__.py`: package markers.
- `backend/src/sunday_clays/config.py`: `Settings` (every C2 field), `*_FILE` resolution, `get_settings()`, `database_url_from_env()`.
- `backend/src/sunday_clays/logging.py`: `configure_logging()`.
- `backend/src/sunday_clays/db.py`: `make_engine`, `SessionFactory`, `get_session`, `alembic_config`, `schema_is_current`, `connect_with_retry`.
- `backend/src/sunday_clays/models/base.py`, `models/__init__.py`: declarative `Base` with the naming convention; re-export.
- `backend/src/sunday_clays/domain/errors.py`: `DomainError`, `NotFoundError`, `ConflictError`.
- `backend/src/sunday_clays/api/errors.py`: JSON error shape, domain-error and catch-all handlers.
- `backend/src/sunday_clays/api/bodylimit.py`: `BodySizeLimitMiddleware`.
- `backend/src/sunday_clays/api/routes/__init__.py`: `discover_routers()`.
- `backend/src/sunday_clays/api/routes/health.py`: `GET /api/health`.
- `backend/src/sunday_clays/api/app.py`: `create_app()` + startup `lifespan`.
- `backend/src/sunday_clays/api/export_openapi.py`: `python -m … --out <path>`.
- `backend/src/sunday_clays/jobs/worker.py`: worker stub honouring the C6 health contract.
- `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/.gitkeep`: migration scaffolding.
- `backend/tests/conftest.py`: shared fixtures (C2 Tests + Decision 13).
- `backend/tests/unit/{test_config,test_logging,test_db}.py`, `backend/tests/unit/api/{test_errors,test_app,test_health,test_routes_discovery,test_export_openapi,test_bodylimit}.py`: unit tests (no DB).
- `backend/tests/integration/{test_db,test_migrations_cli,test_fixtures}.py`, `backend/tests/integration/jobs/test_worker.py`: DB-backed tests.

Task 2 (frontend skeleton):
- `.nvmrc`: Node 22.
- `frontend/package.json` / `frontend/pnpm-lock.yaml`: complete Phase-1 frontend dependency set + scripts (C10).
- `frontend/tsconfig.json`, `vite.config.ts`, `vitest.config.ts`, `eslint.config.js`, `.prettierrc`, `.prettierignore`, `index.html`: tool config.
- `frontend/src/main.tsx`: entry (mount `App`, import the Tailwind CSS).
- `frontend/src/theme/theme.css`: Tailwind v4 entry (Plan 07 T1 adds tokens).
- `frontend/src/app/registry.ts`: feature discovery (`routes.tsx` glob).
- `frontend/src/app/router.tsx`: root route tree.
- `frontend/src/app/App.tsx`: `RouterProvider`.
- `frontend/src/features/home/routes.tsx`, `pages/HomePage.tsx`: placeholder home route.
- `frontend/src/test/setup.ts`, `test/msw/server.ts`, `test/msw/handlers.ts`, `test/render.tsx`: test harness.
- `frontend/src/test/setup.test.ts`, `src/app/{registry.test.ts,router.test.tsx,App.test.tsx}`: tests.

Task 3 (ratchet):
- `ratchets/baseline.json`, `ratchets/budgets.json`: coverage floors and bundle budgets.
- `scripts/ratchet.py`: `check` / `update`.
- `scripts/bundle_stats.py`: gzip sizes of built JS.
- `scripts/tests/test_ratchet.py`, `scripts/tests/test_bundle_stats.py`: behaviour tests.
- `.gitignore` (modify): `artifacts/`, `bundle-stats.json`.

Task 4 (containers, e2e, backups):
- `backend/Dockerfile`, `backend/.dockerignore`: api/worker/backup image.
- `backend/backup/backup.sh`, `restore.sh`, `verify-restore.sh`, `backup_tools.py`: verified dumps, restore, restore check, retention/schedule.
- `backend/tests/unit/backup/test_backup_tools.py`, `test_backup_sh.py`: retention and schedule tests; `backup.sh --once` success and failure paths against stub `pg_dump`/`pg_restore`.
- `frontend/Dockerfile`, `.dockerignore` (root): Caddy + SPA image.
- `deploy/caddy/Caddyfile`: edge config (headers, limits, SPA, `/api` proxy).
- `compose.yaml`, `compose.override.yaml`, `compose.test.yaml`, `compose.swarm.yaml`: stack definitions.
- `scripts/dev-secrets.sh`, `scripts/tests/test_dev_secrets.py`: local/CI secrets.
- `frontend/playwright.config.ts`, `frontend/e2e/fixtures.ts`, `frontend/e2e/smoke.spec.ts`: e2e.
- `deploy/README.md`: Swarm runbook.
- `.gitignore` (modify): `**/e2e/.auth/`.

Task 5 (CI):
- `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.github/dependabot.yml`: CI, image publishing, updates.
- `scripts/check_stack.py`, `scripts/tests/test_check_stack.py`: Swarm fleet rules.
- `scripts/tests/test_ci_config.py`: durable workflow-shape guard.
- `scripts/setup-branch-protection.sh`, `scripts/tests/test_setup_branch_protection.py`: repo settings + `main` protection.
- `lefthook.yml`: git hooks.
- `CONTRIBUTING.md`: workflow, stacked PRs, ratchet, dependency rules.

## Waves
Waves: {T1, T3} → {T2} → {T4} → {T5}.

Task N in this document is master Plan 01 T<N>. T1 and T3 touch disjoint files, so they run in parallel as two separate stacks off `main`. T2 depends on T1; T4 on T1 and T2; T5 on T3 and T4. Nothing runs concurrently with T5.

## Controller follow-up after Task 5 (not part of any implementer brief)

The SDD `task-brief` extractor copies a task from its `### Task N` heading up to the next task heading or the end of the file, so this controller-only work sits here, before Task 1, and never reaches an implementer. Run it after Task 5 passes task review. It uses `git push`, `gh stack` and `gh pr`, which implementers never run.

1. **First CI run (the controller pushes; the implementer fixes).**

The controller pushes `task/01-5-ci` and opens its PR (`gh stack init -b main task/01-5-ci && gh stack submit --auto --open`; T5 is a one-layer stack). Every job and `ci-ok` must be green:

```bash
gh pr checks task/01-5-ci --watch
```

Expected: `backend`, `frontend`, `ratchet`, `docker`, `stack-config`, `e2e` and `ci-ok` all `pass`; `publish` shows as skipped (this is not `main`). If a job fails because the runner differs from a laptop, the controller resumes the Task 5 implementer with the failing job's log; the implementer fixes it on `task/01-5-ci` with a new commit (any Task 1–4 file may change, `ratchets/` may not) and reports again, and the controller pushes and re-runs. Repeat until green. The PR merges only with a fully green `ci-ok` run.

2. **Live `ci-ok` canary (throwaway PR, never merged).**

Prove that a failing test makes `ci-ok` conclude `failure` (not `skipped` or `success`):

```bash
git worktree add -b chore/ci-ok-canary .wt/chore/ci-ok-canary task/01-5-ci
cd .wt/chore/ci-ok-canary
mkdir -p backend/tests/unit
printf 'def test_ci_ok_canary_fails_on_purpose() -> None:\n    assert 1 + 1 == 3\n' > backend/tests/unit/test_ci_canary.py
git add backend/tests/unit/test_ci_canary.py
git commit -m "test: ci-ok canary (do not merge)"
git push -u origin chore/ci-ok-canary
gh pr create --draft --base task/01-5-ci --head chore/ci-ok-canary \
  --title "ci-ok canary (do not merge)" --body "Deliberately failing pytest; proves ci-ok concludes failure."
gh pr checks chore/ci-ok-canary --watch; \
gh api "repos/{owner}/{repo}/commits/$(git rev-parse HEAD)/check-runs?check_name=ci-ok" --jq '.check_runs[0].conclusion'
gh pr close chore/ci-ok-canary --delete-branch
cd - && git worktree remove .wt/chore/ci-ok-canary && git branch -D chore/ci-ok-canary
```

Expected: `gh pr checks` reports `backend` and `ci-ok` as `fail`, and the `gh api` line prints `failure`. Record the canary PR number and that output in the Task 5 PR description. After this PR merges, the controller runs master §0 step 5b (the first `chore/ratchet-wave-0`) and, with the user's OK, §0 step 6 (`scripts/setup-branch-protection.sh`).

---

### Task 1: Backend skeleton (master Plan 01 T1)

**Files:**
- Create: `backend/pyproject.toml`, `backend/uv.lock` (generated by `uv lock`)
- Create: `backend/src/sunday_clays/__init__.py`, `backend/src/sunday_clays/api/__init__.py`, `backend/src/sunday_clays/domain/__init__.py`, `backend/src/sunday_clays/jobs/__init__.py` (empty package markers)
- Create: `backend/src/sunday_clays/config.py`, `backend/src/sunday_clays/logging.py`, `backend/src/sunday_clays/db.py`
- Create: `backend/src/sunday_clays/models/base.py`, `backend/src/sunday_clays/models/__init__.py`
- Create: `backend/src/sunday_clays/domain/errors.py`
- Create: `backend/src/sunday_clays/api/errors.py`, `backend/src/sunday_clays/api/bodylimit.py`, `backend/src/sunday_clays/api/app.py`, `backend/src/sunday_clays/api/export_openapi.py`
- Create: `backend/src/sunday_clays/api/routes/__init__.py`, `backend/src/sunday_clays/api/routes/health.py`
- Create: `backend/src/sunday_clays/jobs/worker.py`
- Create: `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/.gitkeep`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/unit/test_config.py`, `backend/tests/unit/test_logging.py`, `backend/tests/unit/test_db.py`
- Test: `backend/tests/unit/api/test_errors.py`, `test_app.py`, `test_health.py`, `test_routes_discovery.py`, `test_export_openapi.py`, `test_bodylimit.py` (all in `backend/tests/unit/api/`)
- Test: `backend/tests/integration/test_db.py`, `backend/tests/integration/test_migrations_cli.py`, `backend/tests/integration/test_fixtures.py`, `backend/tests/integration/jobs/test_worker.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. The committed fixtures `backend/tests/fixtures/scores_2026-09-27.xlsx` and `backend/tests/fixtures/stations_2026-09-27.xlsx` already exist (do not modify them).
- Produces (later plans rely on these exact names):
  - `sunday_clays.config`: `class Settings(BaseSettings)` with `database_url: SecretStr`, `session_secret: SecretStr`, `viewer_password_hash: SecretStr`, `admin_password_hash: SecretStr`, `club_lat: float = 45.3565`, `club_lon: float = -122.8228`, `timezone: str = "America/Los_Angeles"`, `max_upload_bytes: int = 10_485_760`, `open_meteo_archive_url: str`, `open_meteo_forecast_url: str`, `app_version: str = "dev"`, `weather_enabled: bool = True`, `login_max_failures: int = 10`, `login_window_minutes: int = 15`, `cookie_secure: bool = True`. Also `get_settings() -> Settings` (an `lru_cache`, with `.cache_clear()`), `database_url_from_env() -> str`, `read_secret_env(name: str) -> str | None`, `class ConfigError(RuntimeError)`, `SECRET_FIELDS: tuple[str, ...]`.
  - `sunday_clays.db`: `make_engine(url: str) -> Engine`, `SessionFactory: sessionmaker[Session]`, `get_session() -> Iterator[Session]` (FastAPI dependency), `alembic_config() -> alembic.config.Config`, `schema_is_current(engine: Engine) -> bool`, `connect_with_retry(engine: Engine, *, timeout_s: float = 60.0, interval_s: float = 2.0) -> Connection`.
  - `sunday_clays.logging.configure_logging(level: int = logging.INFO) -> None`.
  - `sunday_clays.models.Base` (from `sunday_clays.models.base`, with `NAMING_CONVENTION`).
  - `sunday_clays.domain.errors`: `class DomainError(Exception)` with `status_code: ClassVar[int] = 400`, `__init__(self, code: str, message: str)`, and attributes `.code` and `.message`. `class NotFoundError(DomainError)` (404) and `class ConflictError(DomainError)` (409).
  - `sunday_clays.api.errors`: `error_body(code: str, message: str) -> dict[str, dict[str, str]]`, `install_error_handlers(app: FastAPI) -> None` (domain errors map to `exc.status_code`; any other exception is logged and becomes 500 `internal`).
  - `sunday_clays.api.bodylimit`: `class BodySizeLimitMiddleware` (pure ASGI, `__init__(self, app: ASGIApp)`), `IMPORTS_PATH = "/api/admin/imports"`, `DEFAULT_LIMIT_BYTES = 262_144`, `UPLOAD_OVERHEAD_BYTES = 65_536`.
  - `sunday_clays.api.routes.discover_routers() -> list[tuple[str, APIRouter]]`; `sunday_clays.api.routes.health`: `router: APIRouter`, `class HealthOut(BaseModel)` (`status: Literal["ok"]`, `version: str`) serving `GET /api/health`.
  - `sunday_clays.api.app.create_app() -> FastAPI` (never reads Settings; `docs_url=None, redoc_url=None, openapi_url=None`). Plan 04 T1 makes the one-time edit that adds role wiring and `CsrfGuardMiddleware`.
  - `sunday_clays.api.export_openapi.main(argv: Sequence[str] | None = None) -> int`, run as `python -m sunday_clays.api.export_openapi --out <path>`.
  - `sunday_clays.jobs.worker`: `HEARTBEAT_PATH = Path("/tmp/worker-heartbeat")`, `POLL_SECONDS = 2.0`, `SCHEMA_TIMEOUT_SECONDS = 180.0`, `touch_heartbeat(path: Path) -> None`, `wait_for_schema(engine: Engine, stop: threading.Event, *, timeout_s: float, poll_s: float, heartbeat: Path) -> bool`, `idle_until_stopped(stop: threading.Event, *, poll_s: float, heartbeat: Path) -> None`, `main() -> int` (entrypoint `python -m sunday_clays.jobs.worker`).
  - Alembic: `backend/alembic.ini` (`script_location = %(here)s/migrations`, no `sqlalchemy.url`) and `migrations/env.py` (URL from `config.attributes["connection"]`, else `sqlalchemy.url`, else `database_url_from_env()`; connect retry, `-x connect_retry_seconds=<n>`; `pg_advisory_xact_lock(7263001)`; `target_metadata = Base.metadata`).
  - `backend/tests/conftest.py` fixtures: `engine` (session), `session`, `client`, `scores_bytes`, `stations_bytes`, plus `database_url` (session), `test_settings`, `settings_env`, `password_hashes` (session), `closed_port`, and the autouse `_fresh_settings_cache`. Constants `VIEWER_TEST_PASSWORD`, `ADMIN_TEST_PASSWORD`, `TEST_SESSION_SECRET` and `FIXTURES_DIR`.

**Branch:** `task/01-1-backend-skeleton`

**Depends on:** none

**Before you start:**
- Work at the root of your worktree; every backend command runs in `backend/` (`cd backend`).
- `uv --version` must print `0.9.9` or newer (`brew install uv`). uv installs Python 3.13 itself.
- Docker must be running (`docker info`): the DB tests start one `postgres:17` testcontainer per pytest run (the first run pulls the image). Alternatively export `TEST_DATABASE_URL=postgresql+psycopg://…` pointing at an empty database that no other worktree uses.
- A local hook may block shell commands whose text contains `get_secret_value`. Create files with your editor's write tool, not `cat <<EOF` heredocs.
- Coverage must stay ≥ 90% lines and branches; the complete code below measures 100%.

- [ ] **Step 1: Create the project manifest and package markers**

Create `backend/pyproject.toml`:

```toml
[project]
name = "sunday-clays"
version = "0.1.0"
description = "Sunday Clays: versioned score ingest and analytics API"
requires-python = ">=3.13,<3.14"
dependencies = [
    "alembic>=1.20",
    "argon2-cffi>=25.1",
    "defusedxml>=0.7.1",
    "fastapi>=0.141",
    "httpx>=0.28",
    "itsdangerous>=2.2",
    "numpy>=2.5",
    "openpyxl>=3.1.5",
    "pandas>=3.0",
    "psycopg[binary]>=3.3",
    "pydantic>=2.13",
    "pydantic-settings>=2.15",
    "python-multipart>=0.0.32",
    "scipy>=1.18",
    "sqlalchemy>=2.1",
    "tzdata>=2026.4",
    "uvicorn[standard]>=0.54",
]

[dependency-groups]
dev = [
    "httpx2>=2.13",
    "hypothesis>=6.168",
    "mypy>=2.3",
    "pandas-stubs>=3.0",
    "pytest>=9.1",
    "pytest-cov>=7.1",
    "respx>=0.23",
    "ruff>=0.16",
    "scipy-stubs>=1.18",
    "testcontainers[postgres]>=4.15",
    "types-defusedxml>=0.7",
    "types-openpyxl>=3.1.5",
]

[build-system]
requires = ["uv_build>=0.9.9,<0.10"]
build-backend = "uv_build"

[tool.uv]
required-version = ">=0.9.9"

[tool.ruff]
line-length = 100
target-version = "py313"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "SIM", "RUF", "PT", "C4", "DTZ", "S"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106", "S603"]

[tool.mypy]
strict = true
python_version = "3.13"
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--import-mode=importlib", "--strict-markers", "--strict-config", "-ra"]
filterwarnings = [
    "error",
    "ignore:Data Validation extension is not supported:UserWarning:openpyxl",
]

[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
fail_under = 90
show_missing = true
skip_covered = true
exclude_also = ["if TYPE_CHECKING:", "if __name__ == .__main__.:"]
```

Then create the empty package markers and directories:

```bash
mkdir -p backend/src/sunday_clays/api/routes backend/src/sunday_clays/domain \
  backend/src/sunday_clays/jobs backend/src/sunday_clays/models backend/migrations/versions \
  backend/tests/unit/api backend/tests/integration/jobs
touch backend/src/sunday_clays/__init__.py backend/src/sunday_clays/api/__init__.py \
  backend/src/sunday_clays/domain/__init__.py backend/src/sunday_clays/jobs/__init__.py \
  backend/migrations/versions/.gitkeep
```

- [ ] **Step 2: Lock and install**

Run: `cd backend && uv lock && uv sync && uv run python -c "import sunday_clays, fastapi, starlette; print(fastapi.__version__, starlette.__version__)"`
Expected: `Resolved … packages`, a `.venv/`, then a version line such as `0.141.1 1.7.0` (newer patch releases are fine).

- [ ] **Step 3: Write the failing settings tests**

Create `backend/tests/conftest.py` (first version; Step 23 replaces it with the full file):

```python
"""Shared pytest fixtures (C2 Tests). Plan 01 T1 owns every fixture in this file.

Later plans add their own fixtures here (Plan 03 T6/T7, Plan 04 T1, Plan 06 T1) and never
change these.
"""

import socket
from collections.abc import Iterator

import pytest
from argon2 import PasswordHasher

from sunday_clays.config import SECRET_FIELDS, get_settings

VIEWER_TEST_PASSWORD = "viewer-test-password"
ADMIN_TEST_PASSWORD = "admin-test-password"
TEST_SESSION_SECRET = "test-session-secret-0123456789abcdef-0123456789abcdef"


@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> Iterator[None]:
    """Every test starts and ends with an empty ``get_settings`` cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def closed_port() -> int:
    """A localhost TCP port with nothing listening (connections are refused at once)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def password_hashes() -> dict[str, str]:
    """argon2id hashes (m=19456 KiB, t=2, p=1) of the viewer and admin test passwords."""
    hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
    return {"viewer": hasher.hash(VIEWER_TEST_PASSWORD), "admin": hasher.hash(ADMIN_TEST_PASSWORD)}


@pytest.fixture
def settings_env(
    monkeypatch: pytest.MonkeyPatch, closed_port: int, password_hashes: dict[str, str]
) -> None:
    """Valid env for ``Settings`` with no database (DATABASE_URL points at a closed port)."""
    for name in SECRET_FIELDS:
        monkeypatch.delenv(f"{name.upper()}_FILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", password_hashes["viewer"])
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", password_hashes["admin"])
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()
```

Create `backend/tests/unit/test_config.py`:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from sunday_clays.config import ConfigError, Settings, database_url_from_env, get_settings


def test_defaults_match_the_contract(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_VERSION", "MAX_UPLOAD_BYTES", "WEATHER_ENABLED", "TIMEZONE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("COOKIE_SECURE")

    settings = get_settings()

    assert settings.club_lat == 45.3565
    assert settings.club_lon == -122.8228
    assert settings.timezone == "America/Los_Angeles"
    assert settings.max_upload_bytes == 10_485_760
    assert settings.weather_enabled is True
    assert settings.login_max_failures == 10
    assert settings.login_window_minutes == 15
    assert settings.cookie_secure is True
    assert settings.app_version == "dev"


def test_env_overrides_defaults(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEATHER_ENABLED", "false")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")

    settings = get_settings()

    assert settings.weather_enabled is False
    assert settings.max_upload_bytes == 1000
    assert settings.cookie_secure is False


def test_secret_file_contents_are_stripped(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "session_secret"
    secret_file.write_text("  " + "f" * 40 + "\n", encoding="utf-8")
    monkeypatch.delenv("SESSION_SECRET")
    monkeypatch.setenv("SESSION_SECRET_FILE", str(secret_file))

    assert get_settings().session_secret.get_secret_value() == "f" * 40


def test_setting_both_var_and_file_names_both_and_hides_the_value(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "db_url"
    secret_file.write_text("postgresql+psycopg://from-file", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:hunter2@db/x")
    monkeypatch.setenv("DATABASE_URL_FILE", str(secret_file))

    with pytest.raises(ConfigError) as excinfo:
        Settings()

    message = str(excinfo.value)
    assert "DATABASE_URL" in message
    assert "DATABASE_URL_FILE" in message
    assert str(secret_file) in message
    assert "hunter2" not in message
    assert "from-file" not in message


def test_file_variable_pointing_to_missing_file_is_an_error(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "nope"
    monkeypatch.delenv("ADMIN_PASSWORD_HASH")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH_FILE", str(missing))

    with pytest.raises(ConfigError, match="ADMIN_PASSWORD_HASH_FILE") as excinfo:
        Settings()

    assert str(missing) in str(excinfo.value)


def test_file_variable_pointing_to_empty_file_is_an_error(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blank = tmp_path / "blank"
    blank.write_text(" \n", encoding="utf-8")
    monkeypatch.delenv("VIEWER_PASSWORD_HASH")
    monkeypatch.setenv("VIEWER_PASSWORD_HASH_FILE", str(blank))

    with pytest.raises(ConfigError, match="empty") as excinfo:
        Settings()

    assert "VIEWER_PASSWORD_HASH_FILE" in str(excinfo.value)


def test_short_session_secret_is_rejected_without_echoing_it(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "short-secret-hunter2")

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert "session_secret" in str(excinfo.value)
    assert "hunter2" not in str(excinfo.value)


def test_non_argon2id_password_hash_is_rejected_without_echoing_it(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    bcrypt_hash = "$2b$12$abcdefghijklmnopqrstuvhunter2hunter2hunter2hunter2hu"
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", bcrypt_hash)

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert "admin_password_hash" in str(excinfo.value)
    assert "hunter2" not in str(excinfo.value)


def test_missing_secret_is_rejected(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SESSION_SECRET")

    with pytest.raises(ValidationError, match="session_secret"):
        Settings()


def test_database_url_from_env_needs_no_other_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("DATABASE_URL", "SESSION_SECRET", "VIEWER_PASSWORD_HASH", "ADMIN_PASSWORD_HASH"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    url_file = tmp_path / "database_url"
    url_file.write_text("postgresql+psycopg://sunday:pw@db:5432/sunday_clays\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL_FILE", str(url_file))

    assert database_url_from_env() == "postgresql+psycopg://sunday:pw@db:5432/sunday_clays"


def test_database_url_from_env_without_any_source_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_FILE", raising=False)

    with pytest.raises(ConfigError, match="DATABASE_URL"):
        database_url_from_env()
```

- [ ] **Step 4: Run the settings tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_config.py -q`
Expected: FAIL. `ImportError while loading conftest '…/backend/tests/conftest.py'` … `ModuleNotFoundError: No module named 'sunday_clays.config'`.

- [ ] **Step 5: Implement settings**

Create `backend/src/sunday_clays/config.py`:

```python
"""Application settings (C2): env vars plus ``<NAME>_FILE`` Docker secrets, read lazily."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

SECRET_FIELDS = ("database_url", "session_secret", "viewer_password_hash", "admin_password_hash")
ARGON2ID_PREFIX = "$argon2id$"
MIN_SESSION_SECRET_BYTES = 32


class ConfigError(RuntimeError):
    """Startup configuration error; the message names variables and paths, never values."""


def read_secret_env(name: str) -> str | None:
    """Value of env ``NAME``, or the stripped contents of the file named by ``NAME_FILE``."""
    env = {key.upper(): value for key, value in os.environ.items()}
    var = name.upper()
    file_var = f"{var}_FILE"
    file_path = env.get(file_var)
    if file_path is None:
        return env.get(var)
    if var in env:
        raise ConfigError(f"Set only one of {var} and {file_var} (file: {file_path})")
    path = Path(file_path)
    if not path.is_file():
        raise ConfigError(f"{file_var} points to a missing file: {file_path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ConfigError(f"{file_var} points to an empty file: {file_path}")
    return value


class SecretEnvSource(PydanticBaseSettingsSource):
    """Resolves every secret field from ``NAME`` or ``NAME_FILE`` (C2)."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return read_secret_env(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name in SECRET_FIELDS:
            value, key, _ = self.get_field_value(self.settings_cls.model_fields[name], name)
            if value is not None:
                values[key] = value
        return values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True, extra="ignore")

    database_url: SecretStr
    session_secret: SecretStr
    viewer_password_hash: SecretStr
    admin_password_hash: SecretStr
    club_lat: float = 45.3565
    club_lon: float = -122.8228
    timezone: str = "America/Los_Angeles"
    max_upload_bytes: int = 10_485_760
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    app_version: str = "dev"
    weather_enabled: bool = True
    login_max_failures: int = 10
    login_window_minutes: int = 15
    cookie_secure: bool = True

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, SecretEnvSource(settings_cls), env_settings)

    @field_validator("session_secret")
    @classmethod
    def _session_secret_long_enough(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < MIN_SESSION_SECRET_BYTES:
            raise ValueError(f"session_secret must be at least {MIN_SESSION_SECRET_BYTES} bytes")
        return value

    @field_validator("viewer_password_hash", "admin_password_hash")
    @classmethod
    def _argon2id_hash(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(ARGON2ID_PREFIX):
            raise ValueError(f"password hashes must start with {ARGON2ID_PREFIX}")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def database_url_from_env() -> str:
    """The database URL from ``DATABASE_URL`` / ``DATABASE_URL_FILE`` only (migrations/env.py)."""
    value = read_secret_env("database_url")
    if value is None:
        raise ConfigError("Set DATABASE_URL or DATABASE_URL_FILE")
    return value
```

- [ ] **Step 6: Run the settings tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_config.py -q`
Expected: PASS, `11 passed`.

- [ ] **Step 7: Write the failing logging test**

Create `backend/tests/unit/test_logging.py`:

```python
import logging
import re

import pytest

from sunday_clays.logging import configure_logging


def test_configure_logging_adds_one_timestamped_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)

    configure_logging()
    configure_logging()

    assert len(root.handlers) == 1
    record = logging.LogRecord("sunday_clays.probe", logging.INFO, __file__, 1, "hello", None, None)
    line = root.handlers[0].format(record)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} [\d:,]+ INFO sunday_clays\.probe hello", line)
    assert root.level == logging.INFO


def test_configure_logging_keeps_existing_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    existing = logging.NullHandler()
    monkeypatch.setattr(root, "handlers", [existing])
    monkeypatch.setattr(root, "level", logging.WARNING)

    configure_logging(logging.DEBUG)

    assert root.handlers == [existing]
    assert root.level == logging.DEBUG
```

- [ ] **Step 8: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_logging.py -q`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.logging'`.

- [ ] **Step 9: Implement `configure_logging`**

Create `backend/src/sunday_clays/logging.py`:

```python
"""Process-wide log format for the api and worker containers (stdout -> docker logs)."""

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Attach one stream handler to the root logger unless one exists; set the root level."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(level)
```

- [ ] **Step 10: Run it to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_logging.py -q`
Expected: PASS, `2 passed`.

- [ ] **Step 11: Write the failing API-skeleton tests**

Create `backend/tests/unit/api/test_errors.py`:

```python
"""Error-shape tests. The probe routes are POSTs on purpose: from Plan 06 T1 on, every eligible
GET /api/* request first passes through CacheHeadersMiddleware, which reads settings and the
database, and these tests run with neither."""

import logging

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app
from sunday_clays.domain.errors import ConflictError, DomainError, NotFoundError


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (DomainError("unreadable_file", "Could not read it"), 400),
        (NotFoundError("not_found", "No such import"), 404),
        (ConflictError("removals_not_confirmed", "Confirm the removals"), 409),
    ],
)
def test_domain_errors_become_json_with_their_status(error: DomainError, status: int) -> None:
    app = create_app()

    @app.post("/api/_raise")
    def raise_it() -> None:
        raise error

    response = TestClient(app).post("/api/_raise")

    assert response.status_code == status
    assert response.json() == {"error": {"code": error.code, "message": error.message}}


def test_unexpected_error_is_logged_and_hidden(caplog: pytest.LogCaptureFixture) -> None:
    app = create_app()

    @app.post("/api/_boom")
    def boom() -> None:
        raise RuntimeError("internal detail hunter2")

    with caplog.at_level(logging.ERROR, logger="sunday_clays.api.errors"):
        response = TestClient(app, raise_server_exceptions=False).post("/api/_boom")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal", "message": "Internal server error"}}
    assert "hunter2" not in response.text
    records = [r for r in caplog.records if r.name == "sunday_clays.api.errors"]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert isinstance(records[0].exc_info[1], RuntimeError)
```

Create `backend/tests/unit/api/test_app.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app
from sunday_clays.config import SECRET_FIELDS, ConfigError


def test_create_app_reads_no_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SECRET_FIELDS:
        monkeypatch.delenv(name.upper(), raising=False)
        monkeypatch.delenv(f"{name.upper()}_FILE", raising=False)

    app = create_app()

    assert "/api/health" in app.openapi()["paths"]


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_and_schema_are_not_served(settings_env: None, path: str) -> None:
    with TestClient(create_app()) as client:
        assert client.get(path).status_code == 404


def test_startup_fails_on_conflicting_secret_sources(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret_file = tmp_path / "session_secret"
    secret_file.write_text("x" * 40, encoding="utf-8")
    monkeypatch.setenv("SESSION_SECRET_FILE", str(secret_file))

    with pytest.raises(ConfigError, match="SESSION_SECRET_FILE"), TestClient(create_app()):
        pass
```

Create `backend/tests/unit/api/test_health.py`:

```python
import pytest
from fastapi.testclient import TestClient

from sunday_clays.api.app import create_app


def test_health_reports_ok_and_the_app_version(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_VERSION", "sha-abc1234")

    with TestClient(create_app()) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "sha-abc1234"}
```

Create `backend/tests/unit/api/test_routes_discovery.py`:

```python
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

import sunday_clays.api.routes as routes_pkg
from sunday_clays.api.app import create_app
from sunday_clays.api.routes import discover_routers

PROBE_ROUTER = """
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/{name}")
def probe() -> dict[str, str]:
    return {{"module": "{name}"}}
"""


@pytest.fixture
def routes_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path]]:
    """Replaces the routes package search path with two empty directories for one test.

    Only the probe modules a test writes are discovered, so these tests keep passing as later
    plans add real route modules. Two directories, because pkgutil already sorts the modules
    within one directory, and only a cross-directory order exercises discover_routers' sort.
    """
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(routes_pkg, "__path__", [str(first), str(second)])
    before = set(sys.modules)
    yield first, second
    for name in set(sys.modules) - before:
        if name.startswith("sunday_clays.api.routes."):
            del sys.modules[name]


def test_discovery_is_sorted_and_skips_underscore_modules(routes_dirs: tuple[Path, Path]) -> None:
    first, second = routes_dirs
    (first / "zz_probe.py").write_text(PROBE_ROUTER.format(name="zz_probe"))
    (first / "_shared_helpers.py").write_text("VALUE = 1\n")
    (second / "aa_probe.py").write_text(PROBE_ROUTER.format(name="aa_probe"))

    names = [name for name, _router in discover_routers()]

    assert names == ["aa_probe", "zz_probe"]


def test_module_without_router_is_rejected(routes_dirs: tuple[Path, Path]) -> None:
    first, _second = routes_dirs
    (first / "broken.py").write_text("VALUE = 1\n")

    with pytest.raises(TypeError, match=r"sunday_clays\.api\.routes\.broken"):
        discover_routers()


def test_create_app_includes_a_newly_added_module(routes_dirs: tuple[Path, Path]) -> None:
    first, _second = routes_dirs
    (first / "zz_probe.py").write_text(PROBE_ROUTER.format(name="zz_probe"))

    assert "/api/zz_probe" in create_app().openapi()["paths"]
```

- [ ] **Step 12: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/api -q`
Expected: FAIL. Four collection errors: `test_errors.py`, `test_app.py` and `test_health.py` with `ModuleNotFoundError: No module named 'sunday_clays.api.app'`, and `test_routes_discovery.py` with `No module named 'sunday_clays.api.routes'` (its `import sunday_clays.api.routes` line comes first).

- [ ] **Step 13: Implement errors, router discovery, health and the app factory**

Create `backend/src/sunday_clays/domain/errors.py`:

```python
"""Domain exceptions; api/errors.py maps each to its ``status_code`` (C2 Errors)."""

from typing import ClassVar


class DomainError(Exception):
    status_code: ClassVar[int] = 400

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFoundError(DomainError):
    status_code: ClassVar[int] = 404


class ConflictError(DomainError):
    status_code: ClassVar[int] = 409
```

Create `backend/src/sunday_clays/api/errors.py`:

```python
"""One JSON error shape for every failure: ``{"error": {"code", "message"}}`` (C2 Errors)."""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sunday_clays.domain.errors import DomainError

logger = logging.getLogger(__name__)


def error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    error = cast(DomainError, exc)
    return JSONResponse(
        status_code=error.status_code, content=error_body(error.code, error.message)
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content=error_body("internal", "Internal server error"))


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
```

Create `backend/src/sunday_clays/api/routes/__init__.py`:

```python
"""Router auto-discovery (C2): every public module here defines ``router: APIRouter``."""

import importlib
import pkgutil

from fastapi import APIRouter


def discover_routers() -> list[tuple[str, APIRouter]]:
    """(module name, router) for every module not starting with ``_``, sorted by module name."""
    found: list[tuple[str, APIRouter]] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{module.__name__} must define router: APIRouter")
        found.append((info.name, router))
    return sorted(found, key=lambda item: item[0])
```

Create `backend/src/sunday_clays/api/routes/health.py`:

```python
"""``GET /api/health`` (public; C8)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sunday_clays.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthOut:
    return HealthOut(status="ok", version=settings.app_version)
```

Create `backend/src/sunday_clays/api/app.py` (first version; Step 21 adds the body-size middleware):

```python
"""FastAPI application factory. Never edit this file to add a route (C2 API routers)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sunday_clays.api.errors import install_error_handlers
from sunday_clays.api.routes import discover_routers
from sunday_clays.config import get_settings
from sunday_clays.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    get_settings()  # a misconfigured secret fails server startup, not the first request
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sunday Clays API",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)
    for _name, router in discover_routers():
        app.include_router(router)
    return app
```

- [ ] **Step 14: Run the API tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/api -q`
Expected: PASS, `13 passed`.

- [ ] **Step 15: Write the failing OpenAPI-export tests**

Create `backend/tests/unit/api/test_export_openapi.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sunday_clays.api.export_openapi import main
from sunday_clays.config import SECRET_FIELDS


def test_export_openapi_without_env(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"

    result = subprocess.run(
        [sys.executable, "-m", "sunday_clays.api.export_openapi", "--out", str(out)],
        env={},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    schema = json.loads(text)
    assert text == json.dumps(schema, indent=2, sort_keys=True) + "\n"
    assert "/api/health" in schema["paths"]
    assert "HealthOut" in schema["components"]["schemas"]


def test_main_writes_the_schema_in_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SECRET_FIELDS:
        monkeypatch.delenv(name.upper(), raising=False)
    out = tmp_path / "openapi.json"

    assert main(["--out", str(out)]) == 0

    assert json.loads(out.read_text(encoding="utf-8"))["info"]["title"] == "Sunday Clays API"
```

- [ ] **Step 16: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/api/test_export_openapi.py -q`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.api.export_openapi'`.

- [ ] **Step 17: Implement the exporter**

Create `backend/src/sunday_clays/api/export_openapi.py`:

```python
"""``python -m sunday_clays.api.export_openapi --out <path>``: needs no env vars and no DB."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from sunday_clays.api.app import create_app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the API's OpenAPI schema as JSON.")
    parser.add_argument("--out", type=Path, required=True, help="output file path")
    args = parser.parse_args(argv)
    out: Path = args.out
    schema = create_app().openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 18: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/unit/api/test_export_openapi.py -q`
Expected: PASS, `2 passed` (`test_export_openapi_without_env` runs the module in a subprocess with an empty environment).

- [ ] **Step 19: Write the failing body-size-limit tests**

Create `backend/tests/unit/api/test_bodylimit.py`:

```python
import asyncio
import json
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest
import starlette.formparsers
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from sunday_clays.api import app as app_module
from sunday_clays.api.bodylimit import BodySizeLimitMiddleware

DEFAULT_LIMIT = 262_144
PAYLOAD_TOO_LARGE = {"error": {"code": "payload_too_large", "message": "Request body is too large"}}


class RecordingApp:
    """Inner ASGI app: reads the whole body, then answers 200 with the byte count."""

    def __init__(self) -> None:
        self.called = False
        self.bytes_seen = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.called = True
        if scope["type"] == "http":
            more = True
            while more:
                message = await receive()
                self.bytes_seen += len(message.get("body", b""))
                more = message.get("more_body", False)
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": str(self.bytes_seen).encode()})


class SwallowingApp:
    """Inner app that turns any body-read error into its own 400, as FastAPI's parser does."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            while (await receive()).get("more_body", False):
                pass
        except Exception:
            await send({"type": "http.response.start", "status": 400, "headers": []})
            await send({"type": "http.response.body", "body": b"parse error"})


class FailingApp:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise RuntimeError("unrelated failure")


def http_scope(path: str, *, method: str = "POST", content_length: str | None = None) -> Scope:
    headers = [] if content_length is None else [(b"content-length", content_length.encode())]
    return {"type": "http", "method": method, "path": path, "headers": headers}


def drive(app: Any, scope: Scope, chunks: list[bytes]) -> list[Message]:
    pending = list(chunks)
    sent: list[Message] = []

    async def receive() -> Message:
        body = pending.pop(0) if pending else b""
        return {"type": "http.request", "body": body, "more_body": bool(pending)}

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(BodySizeLimitMiddleware(app)(scope, receive, send))
    return sent


def status_of(sent: list[Message]) -> int:
    return int(next(m["status"] for m in sent if m["type"] == "http.response.start"))


def body_of(sent: list[Message]) -> Any:
    return json.loads(
        b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    )


def test_declared_length_over_limit_is_rejected_before_the_app_runs() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/api/auth/login", content_length=str(DEFAULT_LIMIT + 1)), [])

    assert status_of(sent) == 413
    assert body_of(sent) == PAYLOAD_TOO_LARGE
    assert inner.called is False


def test_body_exactly_at_the_limit_is_accepted() -> None:
    inner = RecordingApp()

    sent = drive(
        inner,
        http_scope("/api/auth/login", content_length=str(DEFAULT_LIMIT)),
        [b"x" * DEFAULT_LIMIT],
    )

    assert status_of(sent) == 200
    assert inner.bytes_seen == DEFAULT_LIMIT


def test_chunked_body_is_cut_off_as_soon_as_it_passes_the_limit() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/api/auth/login"), [b"x" * 100_000] * 4)

    assert status_of(sent) == 413
    assert body_of(sent) == PAYLOAD_TOO_LARGE
    assert inner.bytes_seen <= DEFAULT_LIMIT


def test_malformed_content_length_falls_back_to_counting() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/api/x", content_length="lots"), [b"x" * 200_000] * 2)

    assert status_of(sent) == 413


def test_app_error_response_after_the_cutoff_is_replaced_by_413() -> None:
    sent = drive(SwallowingApp(), http_scope("/api/x"), [b"x" * 200_000] * 2)

    assert [m["status"] for m in sent if m["type"] == "http.response.start"] == [413]


def test_disconnect_messages_pass_through_to_the_app() -> None:
    inner = RecordingApp()
    messages: list[Message] = [
        {"type": "http.request", "body": b"part", "more_body": True},
        {"type": "http.disconnect"},
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return messages.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(BodySizeLimitMiddleware(inner)(http_scope("/api/x"), receive, send))

    assert status_of(sent) == 200
    assert inner.bytes_seen == 4


def test_errors_unrelated_to_the_limit_propagate() -> None:
    with pytest.raises(RuntimeError, match="unrelated failure"):
        drive(FailingApp(), http_scope("/api/x"), [b"small"])


def test_non_api_paths_are_not_limited() -> None:
    inner = RecordingApp()

    sent = drive(inner, http_scope("/assets/app.js", content_length="999999999"), [b"ok"])

    assert status_of(sent) == 200


def test_non_http_scopes_pass_through() -> None:
    inner = RecordingApp()

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None:
        return None

    asyncio.run(BodySizeLimitMiddleware(inner)({"type": "lifespan"}, receive, send))

    assert inner.called is True


def test_imports_upload_limit_is_max_upload_bytes_plus_overhead(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    limit = 1000 + 65_536

    over = drive(
        RecordingApp(), http_scope("/api/admin/imports", content_length=str(limit + 1)), []
    )
    at_limit = drive(
        RecordingApp(),
        http_scope("/api/admin/imports/", content_length=str(limit)),
        [b"x" * limit],
    )
    listing = drive(
        RecordingApp(),
        http_scope("/api/admin/imports", method="GET", content_length=str(DEFAULT_LIMIT + 1)),
        [],
    )

    assert status_of(over) == 413
    assert status_of(at_limit) == 200
    assert status_of(listing) == 413


class RecordingSpool(tempfile.SpooledTemporaryFile[bytes]):
    """Counts multipart spool files created by Starlette and any rollover to disk."""

    created: ClassVar[int] = 0
    rolled_to_disk: ClassVar[int] = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        type(self).created += 1
        super().__init__(*args, **kwargs)

    def rollover(self) -> None:
        type(self).rolled_to_disk += 1
        super().rollover()


@dataclass
class UploadProbe:
    client: TestClient
    route_calls: list[str]


@pytest.fixture
def upload_probe(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[UploadProbe]:
    """create_app() plus a probe upload route at the imports path; MAX_UPLOAD_BYTES=1000.

    Router discovery is emptied, so once Plan 04 T2 adds the real (admin-only)
    POST /api/admin/imports route it cannot shadow the probe. The middleware stack that
    create_app() installs stays under test.
    """
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    RecordingSpool.created = 0
    RecordingSpool.rolled_to_disk = 0
    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", RecordingSpool)
    monkeypatch.setattr(app_module, "discover_routers", lambda: [])
    route_calls: list[str] = []
    app = app_module.create_app()

    @app.post("/api/admin/imports")
    async def upload(file: UploadFile) -> dict[str, int]:
        route_calls.append(file.filename or "")
        return {"size": len(await file.read())}

    with TestClient(app) as client:
        yield UploadProbe(client=client, route_calls=route_calls)


def multipart_body(boundary: str, size: int) -> bytes:
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="big.xlsx"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    return head + b"x" * size + f"\r\n--{boundary}--\r\n".encode()


def test_oversized_upload_with_content_length_never_reaches_the_parser(
    upload_probe: UploadProbe,
) -> None:
    response = upload_probe.client.post(
        "/api/admin/imports", files={"file": ("big.xlsx", b"x" * 70_000, "application/xlsx")}
    )

    assert response.status_code == 413
    assert response.json() == PAYLOAD_TOO_LARGE
    assert upload_probe.route_calls == []
    assert RecordingSpool.created == 0


def test_oversized_chunked_upload_is_rejected_without_touching_disk(
    upload_probe: UploadProbe,
) -> None:
    body = multipart_body("sc-boundary", 200_000)

    def chunks() -> Iterator[bytes]:
        for start in range(0, len(body), 16_384):
            yield body[start : start + 16_384]

    response = upload_probe.client.post(
        "/api/admin/imports",
        content=chunks(),
        headers={"content-type": "multipart/form-data; boundary=sc-boundary"},
    )

    assert response.status_code == 413
    assert response.json() == PAYLOAD_TOO_LARGE
    assert upload_probe.route_calls == []
    assert RecordingSpool.rolled_to_disk == 0


def test_upload_within_the_limit_reaches_the_route(upload_probe: UploadProbe) -> None:
    response = upload_probe.client.post(
        "/api/admin/imports", files={"file": ("ok.xlsx", b"x" * 500, "application/xlsx")}
    )

    assert response.json() == {"size": 500}
    assert upload_probe.route_calls == ["ok.xlsx"]
```

- [ ] **Step 20: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/api/test_bodylimit.py -q`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.api.bodylimit'`.

- [ ] **Step 21: Implement the middleware and register it**

Create `backend/src/sunday_clays/api/bodylimit.py`:

```python
"""Pure ASGI request-body size limit that runs before routing and auth (C2 Body size limit)."""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sunday_clays.api.errors import error_body
from sunday_clays.config import get_settings

IMPORTS_PATH = "/api/admin/imports"
DEFAULT_LIMIT_BYTES = 262_144
UPLOAD_OVERHEAD_BYTES = 65_536
_BODY_413 = json.dumps(error_body("payload_too_large", "Request body is too large")).encode()


class _BodyTooLarge(Exception):
    """Raised inside the wrapped ``receive`` once the running byte count passes the limit."""


async def _send_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_BODY_413)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _BODY_413})


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _limit_for(scope: Scope) -> int:
    if scope["method"] == "POST" and scope["path"].rstrip("/") == IMPORTS_PATH:
        return get_settings().max_upload_bytes + UPLOAD_OVERHEAD_BYTES  # read on first upload
    return DEFAULT_LIMIT_BYTES


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            await self.app(scope, receive, send)
            return
        limit = _limit_for(scope)
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await _send_413(send)
            return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                return  # the app's own error response is replaced by the 413 below
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started:
            await _send_413(send)
```

Replace `backend/src/sunday_clays/api/app.py` with the final version (adds the middleware import and `app.add_middleware(BodySizeLimitMiddleware)`):

```python
"""FastAPI application factory. Never edit this file to add a route (C2 API routers)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sunday_clays.api.bodylimit import BodySizeLimitMiddleware
from sunday_clays.api.errors import install_error_handlers
from sunday_clays.api.routes import discover_routers
from sunday_clays.config import get_settings
from sunday_clays.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    get_settings()  # a misconfigured secret fails server startup, not the first request
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sunday Clays API",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    install_error_handlers(app)
    for _name, router in discover_routers():
        app.include_router(router)
    app.add_middleware(BodySizeLimitMiddleware)
    return app
```

- [ ] **Step 22: Run every unit test to verify they pass**

Run: `cd backend && uv run pytest tests/unit -q`
Expected: PASS, `41 passed`.

- [ ] **Step 23: Write the failing database, migration and fixture tests**

Replace `backend/tests/conftest.py` with the full version (adds `database_url`, `engine`, `session`, `test_settings`, `client`, `scores_bytes`, `stations_bytes`):

```python
"""Shared pytest fixtures (C2 Tests). Plan 01 T1 owns every fixture in this file.

Later plans add their own fixtures here (Plan 03 T6/T7, Plan 04 T1, Plan 06 T1) and never
change these.
"""

import os
import socket
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

from sunday_clays.api.app import create_app
from sunday_clays.config import SECRET_FIELDS, Settings, get_settings
from sunday_clays.db import alembic_config, get_session, make_engine

FIXTURES_DIR = Path(__file__).parent / "fixtures"
VIEWER_TEST_PASSWORD = "viewer-test-password"
ADMIN_TEST_PASSWORD = "admin-test-password"
TEST_SESSION_SECRET = "test-session-secret-0123456789abcdef-0123456789abcdef"


@pytest.fixture(autouse=True)
def _fresh_settings_cache() -> Iterator[None]:
    """Every test starts and ends with an empty ``get_settings`` cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def closed_port() -> int:
    """A localhost TCP port with nothing listening (connections are refused at once)."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def password_hashes() -> dict[str, str]:
    """argon2id hashes (m=19456 KiB, t=2, p=1) of the viewer and admin test passwords."""
    hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
    return {"viewer": hasher.hash(VIEWER_TEST_PASSWORD), "admin": hasher.hash(ADMIN_TEST_PASSWORD)}


@pytest.fixture
def settings_env(
    monkeypatch: pytest.MonkeyPatch, closed_port: int, password_hashes: dict[str, str]
) -> None:
    """Valid env for ``Settings`` with no database (DATABASE_URL points at a closed port)."""
    for name in SECRET_FIELDS:
        monkeypatch.delenv(f"{name.upper()}_FILE", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", password_hashes["viewer"])
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", password_hashes["admin"])
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """``TEST_DATABASE_URL`` if set, else a ``postgres:17`` testcontainer for this pytest run."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    with pytest.MonkeyPatch.context() as mp:
        if sys.platform == "darwin" and "TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE" not in os.environ:
            # Docker Desktop/Colima/OrbStack: Ryuk must mount the VM-side socket path.
            mp.setenv("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")
        with PostgresContainer("postgres:17", driver="psycopg") as postgres:
            yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """Session-scoped engine on the test DB, upgraded once to the Alembic head."""
    test_engine = make_engine(database_url)
    config = alembic_config()
    with test_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session inside an outer transaction that is rolled back after the test."""
    connection = engine.connect()
    outer = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield db_session
    finally:
        db_session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def test_settings(
    settings_env: None, monkeypatch: pytest.MonkeyPatch, database_url: str
) -> Settings:
    """``settings_env`` pointed at the real test database; ``cookie_secure`` is False."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def client(session: Session, test_settings: Settings) -> Iterator[TestClient]:
    """TestClient whose ``get_session`` override mirrors production commit/rollback per request."""
    app = create_app()

    def session_override() -> Iterator[Session]:
        nested = session.begin_nested()
        try:
            yield session
        except BaseException:
            if nested.is_active:
                nested.rollback()
            raise
        else:
            if nested.is_active:
                nested.commit()

    app.dependency_overrides[get_session] = session_override
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def scores_bytes() -> bytes:
    return (FIXTURES_DIR / "scores_2026-09-27.xlsx").read_bytes()


@pytest.fixture(scope="session")
def stations_bytes() -> bytes:
    return (FIXTURES_DIR / "stations_2026-09-27.xlsx").read_bytes()
```

Create `backend/tests/unit/test_db.py`:

```python
import time
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from sunday_clays.db import SOURCE_ALEMBIC_INI, alembic_config, connect_with_retry, make_engine


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db:5432/x",
        "postgres://u:p@db:5432/x",
        "postgresql+psycopg://u:p@db:5432/x",
    ],
)
def test_make_engine_always_uses_psycopg3(url: str) -> None:
    engine = make_engine(url)

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "db"
    assert engine.url.database == "x"


def test_alembic_config_prefers_ini_in_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = elsewhere\n")
    monkeypatch.chdir(tmp_path)

    config = alembic_config()

    assert config.get_main_option("script_location") == "elsewhere"


def test_alembic_config_falls_back_to_source_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    config = alembic_config()

    assert config.config_file_name == str(SOURCE_ALEMBIC_INI)
    script_location = config.get_main_option("script_location")
    assert script_location is not None
    assert Path(script_location) == SOURCE_ALEMBIC_INI.parent / "migrations"


def test_connect_with_retry_gives_up_after_timeout(closed_port: int) -> None:
    engine = make_engine(f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    started = time.monotonic()

    with pytest.raises(OperationalError):
        connect_with_retry(engine, timeout_s=0.3, interval_s=0.1)

    elapsed = time.monotonic() - started
    assert 0.2 <= elapsed < 5.0
```

Create `backend/tests/integration/test_db.py`:

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from sunday_clays.config import Settings
from sunday_clays.db import SessionFactory, connect_with_retry, get_session, schema_is_current

PENDING_REVISION = """
revision = "0001_pending"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
"""


def test_schema_is_current_on_the_migrated_test_database(engine: Engine) -> None:
    assert schema_is_current(engine) is True


def test_schema_is_not_current_while_a_revision_is_pending(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_pending.py").write_text(PENDING_REVISION)
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = %(here)s/migrations\n")
    monkeypatch.chdir(tmp_path)

    assert schema_is_current(engine) is False


def test_connections_run_in_utc(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("SHOW timezone")).scalar_one() == "UTC"


def test_connect_with_retry_returns_a_live_connection(engine: Engine) -> None:
    with connect_with_retry(engine, timeout_s=1.0, interval_s=0.1) as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1


@pytest.fixture
def probe_table(engine: Engine) -> Iterator[None]:
    """A committed scratch table so real commits can be observed; dropped afterwards."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE plan01_session_probe (v int NOT NULL)"))
    yield
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE plan01_session_probe"))


@pytest.fixture
def factory_bound_to_test_engine(engine: Engine) -> Iterator[None]:
    SessionFactory.configure(bind=engine)
    yield
    SessionFactory.configure(bind=None)


def probe_app() -> FastAPI:
    app = FastAPI()

    @app.post("/ok")
    def ok(session: Session = Depends(get_session)) -> None:  # noqa: B008
        session.execute(text("INSERT INTO plan01_session_probe VALUES (1)"))

    @app.post("/fail")
    def fail(session: Session = Depends(get_session)) -> None:  # noqa: B008
        session.execute(text("INSERT INTO plan01_session_probe VALUES (2)"))
        raise HTTPException(status_code=401)

    return app


def committed_values(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return list(conn.execute(text("SELECT v FROM plan01_session_probe ORDER BY v")).scalars())


def test_get_session_commits_on_success_and_rolls_back_on_http_exception(
    engine: Engine, probe_table: None, factory_bound_to_test_engine: None
) -> None:
    client = TestClient(probe_app())

    assert client.post("/ok").status_code == 200
    assert client.post("/fail").status_code == 401

    assert committed_values(engine) == [1]


def test_get_session_binds_the_factory_from_settings_on_first_use(
    test_settings: Settings, engine: Engine, probe_table: None
) -> None:
    SessionFactory.configure(bind=None)
    try:
        assert TestClient(probe_app()).post("/ok").status_code == 200
        bound = SessionFactory.kw["bind"]
        assert bound is not engine
        assert bound.url.database == engine.url.database
        assert bound.url.port == engine.url.port
    finally:
        bound_engine = SessionFactory.kw.get("bind")
        SessionFactory.configure(bind=None)
        if bound_engine is not None:
            bound_engine.dispose()
    assert committed_values(engine) == [1]
```

Create `backend/tests/integration/test_migrations_cli.py`:

```python
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import Engine, text

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_LOCK_KEY = 7263001  # the pg_advisory_xact_lock key in migrations/env.py
WAITING_FOR_LOCK = text(
    "SELECT count(*) FROM pg_locks"
    " WHERE locktype = 'advisory' AND objid::bigint = :key AND NOT granted"
)


def run_alembic(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={"PATH": os.environ.get("PATH", ""), **env},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_alembic_cli_migrates_using_database_url(database_url: str) -> None:
    upgrade = run_alembic("upgrade", "head", env={"DATABASE_URL": database_url})
    current = run_alembic("current", env={"DATABASE_URL": database_url})

    assert upgrade.returncode == 0, upgrade.stderr
    assert current.returncode == 0, current.stderr


def test_alembic_cli_reads_database_url_file(database_url: str, tmp_path: Path) -> None:
    url_file = tmp_path / "database_url"
    url_file.write_text(database_url + "\n", encoding="utf-8")

    result = run_alembic("current", env={"DATABASE_URL_FILE": str(url_file)})

    assert result.returncode == 0, result.stderr


def test_alembic_cli_without_database_url_fails_with_a_clear_message() -> None:
    result = run_alembic("current", env={})

    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_alembic_cli_retries_an_unreachable_database_before_failing(closed_port: int) -> None:
    url = f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x"
    started = time.monotonic()

    result = run_alembic(
        "-x", "connect_retry_seconds=3", "upgrade", "head", env={"DATABASE_URL": url}
    )

    assert result.returncode != 0
    assert time.monotonic() - started >= 2.0


def lock_waiters(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(WAITING_FOR_LOCK, {"key": MIGRATION_LOCK_KEY}).scalar_one())


def test_migrations_wait_for_the_advisory_lock(database_url: str, engine: Engine) -> None:
    """Two `api` replicas starting at once: the second `alembic upgrade` blocks on the lock."""
    with engine.connect() as holder:
        holder.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        proc = subprocess.Popen(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND_DIR,
            env={"PATH": os.environ.get("PATH", ""), "DATABASE_URL": database_url},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            waiting = 0
            deadline = time.monotonic() + 30
            while proc.poll() is None and time.monotonic() < deadline:
                waiting = lock_waiters(engine)
                if waiting == 1:
                    break
                time.sleep(0.1)
            assert proc.poll() is None, "alembic finished without waiting for the migration lock"
            assert waiting == 1

            holder.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
            _, stderr = proc.communicate(timeout=60)
            assert proc.returncode == 0, stderr
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            holder.invalidate()  # closes the DB session, so the lock never outlives the test
```

Create `backend/tests/integration/test_fixtures.py`:

```python
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import DomainError


def test_client_keeps_good_writes_and_rolls_back_write_then_raise(
    client: TestClient, session: Session
) -> None:
    session.execute(text("CREATE TABLE fixture_probe (v int NOT NULL)"))
    app = client.app
    assert isinstance(app, FastAPI)

    @app.post("/api/_probe/ok")
    def ok(db: Session = Depends(get_session)) -> None:  # noqa: B008
        db.execute(text("INSERT INTO fixture_probe VALUES (1)"))

    @app.post("/api/_probe/fail")
    def fail(db: Session = Depends(get_session)) -> None:  # noqa: B008
        db.execute(text("INSERT INTO fixture_probe VALUES (2)"))
        raise DomainError("rejected", "write then raise")

    assert client.post("/api/_probe/ok").status_code == 200
    assert client.post("/api/_probe/fail").status_code == 400

    assert list(session.execute(text("SELECT v FROM fixture_probe")).scalars()) == [1]


def test_client_runs_with_insecure_cookies(client: TestClient) -> None:
    assert get_settings().cookie_secure is False


def test_client_keeps_a_write_committed_before_raising(
    client: TestClient, session: Session
) -> None:
    session.execute(text("CREATE TABLE fixture_probe (v int NOT NULL)"))
    app = client.app
    assert isinstance(app, FastAPI)

    @app.post("/api/_probe/commit-then-fail")
    def commit_then_fail(db: Session = Depends(get_session)) -> None:  # noqa: B008
        db.execute(text("INSERT INTO fixture_probe VALUES (3)"))
        db.commit()
        raise DomainError("rejected", "persisted first")

    assert client.post("/api/_probe/commit-then-fail").status_code == 400

    assert list(session.execute(text("SELECT v FROM fixture_probe")).scalars()) == [3]
```

- [ ] **Step 24: Run the suite to verify it fails**

Run: `cd backend && uv run pytest -q`
Expected: FAIL. `ImportError while loading conftest '…/backend/tests/conftest.py'` … `ModuleNotFoundError: No module named 'sunday_clays.db'`.

- [ ] **Step 25: Implement the database layer and migration scaffolding**

Create `backend/src/sunday_clays/db.py`:

```python
"""Engine, sessions and migration-state helpers (C2 ``db.py``)."""

import time
from collections.abc import Iterator
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from sunday_clays.config import get_settings

SOURCE_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
_BARE_SCHEMES = ("postgresql://", "postgres://")

SessionFactory: sessionmaker[Session] = sessionmaker(expire_on_commit=False)


def make_engine(url: str) -> Engine:
    """Engine for ``url``; bare ``postgresql://`` URLs use psycopg 3; sessions run in UTC."""
    for scheme in _BARE_SCHEMES:
        if url.startswith(scheme):
            url = "postgresql+psycopg://" + url.removeprefix(scheme)
            break
    return create_engine(url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"})


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request; commit on success, rollback on any error."""
    if SessionFactory.kw.get("bind") is None:
        SessionFactory.configure(bind=make_engine(get_settings().database_url.get_secret_value()))
    session = SessionFactory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


def alembic_config() -> Config:
    """``alembic.ini`` from the working directory (the image's /app), else the source tree."""
    ini = Path("alembic.ini")
    if not ini.is_file():
        ini = SOURCE_ALEMBIC_INI
    return Config(str(ini))


def schema_is_current(engine: Engine) -> bool:
    heads = set(ScriptDirectory.from_config(alembic_config()).get_heads())
    with engine.connect() as conn:
        current = set(MigrationContext.configure(conn).get_current_heads())
    return heads == current


def connect_with_retry(
    engine: Engine, *, timeout_s: float = 60.0, interval_s: float = 2.0
) -> Connection:
    """First connection for migrations: retry every ``interval_s`` until ``timeout_s`` elapses."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            return engine.connect()
        except OperationalError:
            if time.monotonic() + interval_s > deadline:
                raise
            time.sleep(interval_s)
```

Create `backend/src/sunday_clays/models/base.py`:

```python
"""Declarative base shared by every model module (Plan 03 T1 adds the tables)."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

Create `backend/src/sunday_clays/models/__init__.py`:

```python
"""All ORM models; ``Base.metadata`` is the autogenerate target (migrations/env.py)."""

from sunday_clays.models.base import Base

__all__ = ["Base"]
```

Create `backend/alembic.ini`:

```ini
# Alembic configuration. There is deliberately no sqlalchemy.url: migrations/env.py takes the
# connection from config.attributes["connection"] (tests), else sqlalchemy.url if a caller sets
# it, else DATABASE_URL / DATABASE_URL_FILE via sunday_clays.config.database_url_from_env().

[alembic]
script_location = %(here)s/migrations
path_separator = os

[post_write_hooks]
hooks = ruff_fix, ruff_format
ruff_fix.type = module
ruff_fix.module = ruff
ruff_fix.options = check --fix REVISION_SCRIPT_FILENAME
ruff_format.type = module
ruff_format.module = ruff
ruff_format.options = format REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/migrations/env.py`:

```python
"""Alembic environment: one connection, one advisory lock, then the migrations (Plan 01 T1)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, text

from sunday_clays.config import database_url_from_env
from sunday_clays.db import connect_with_retry, make_engine
from sunday_clays.models import Base

MIGRATION_LOCK_KEY = 7263001  # pg_advisory_xact_lock key; serialises concurrent `api` starts

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or database_url_from_env()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    shared = config.attributes.get("connection")
    if shared is not None:
        _run(shared)
        return
    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    x_args = context.get_x_argument(as_dictionary=True)
    retry_seconds = float(x_args.get("connect_retry_seconds", "60"))
    engine = make_engine(_database_url())
    try:
        with connect_with_retry(engine, timeout_s=retry_seconds) as connection:
            _run(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

(`backend/migrations/versions/.gitkeep` was created in Step 1. Plan 03 T1 adds `versions/0001_initial.py`.)

- [ ] **Step 26: Run the suite to verify it passes**

Run: `cd backend && uv run pytest -q`
Expected: PASS, `61 passed`. The first run pulls `postgres:17`. On macOS, if Ryuk still fails with `Port mapping for container … and port 8080 is not available`, export `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (the conftest already sets it when unset).

- [ ] **Step 27: Write the failing worker tests**

Create `backend/tests/integration/jobs/test_worker.py`:

```python
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine

from sunday_clays.config import Settings
from sunday_clays.db import make_engine
from sunday_clays.jobs import worker

# Runs the worker's real main() with HEARTBEAT_PATH = argv[1] (main() reads it at call time).
RUN_WORKER_MAIN = (
    "import pathlib, sys\n"
    "from sunday_clays.jobs import worker\n"
    "worker.HEARTBEAT_PATH = pathlib.Path(sys.argv[1])\n"
    "sys.exit(worker.main())\n"
)


@pytest.fixture
def restore_signal_handlers() -> Iterator[None]:
    saved = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    yield
    for sig, handler in saved.items():
        signal.signal(sig, handler)


@pytest.fixture
def fast_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Points the worker's heartbeat at ``tmp_path`` and polls every 20 ms."""
    heartbeat = tmp_path / "heartbeat"
    monkeypatch.setattr(worker, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr(worker, "POLL_SECONDS", 0.02)
    return heartbeat


def test_wait_for_schema_returns_true_on_a_current_schema(engine: Engine, tmp_path: Path) -> None:
    heartbeat = tmp_path / "hb"

    ok = worker.wait_for_schema(
        engine, threading.Event(), timeout_s=5, poll_s=0.01, heartbeat=heartbeat
    )

    assert ok is True
    assert heartbeat.exists()


def test_wait_for_schema_treats_connection_errors_as_not_current(
    closed_port: int, tmp_path: Path
) -> None:
    unreachable = make_engine(f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x")
    heartbeat = tmp_path / "hb"

    ok = worker.wait_for_schema(
        unreachable, threading.Event(), timeout_s=0.2, poll_s=0.02, heartbeat=heartbeat
    )

    assert ok is False
    assert heartbeat.exists()


def test_wait_for_schema_keeps_waiting_while_a_revision_is_pending(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    (versions / "0001_pending.py").write_text(
        'revision = "0001_pending"\ndown_revision = None\n'
        "def upgrade() -> None: ...\ndef downgrade() -> None: ...\n"
    )
    (tmp_path / "alembic.ini").write_text("[alembic]\nscript_location = %(here)s/migrations\n")
    monkeypatch.chdir(tmp_path)

    ok = worker.wait_for_schema(
        engine, threading.Event(), timeout_s=0.2, poll_s=0.02, heartbeat=tmp_path / "hb"
    )

    assert ok is False


def test_wait_for_schema_returns_false_once_stopped(engine: Engine, tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()

    ok = worker.wait_for_schema(engine, stop, timeout_s=5, poll_s=0.01, heartbeat=tmp_path / "hb")

    assert ok is False


def test_main_exits_1_when_the_schema_never_becomes_current(
    settings_env: None,
    fast_worker: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_signal_handlers: None,
) -> None:
    monkeypatch.setattr(worker, "SCHEMA_TIMEOUT_SECONDS", 0.2)

    assert worker.main() == 1
    assert fast_worker.exists()


def test_main_exits_0_when_stopped_while_waiting_for_the_schema(
    settings_env: None, fast_worker: Path, restore_signal_handlers: None
) -> None:
    threading.Timer(0.2, os.kill, (os.getpid(), signal.SIGTERM)).start()

    assert worker.main() == 0


def test_main_heartbeats_until_sigint_then_exits_0(
    test_settings: Settings, fast_worker: Path, restore_signal_handlers: None
) -> None:
    threading.Timer(0.3, os.kill, (os.getpid(), signal.SIGINT)).start()

    assert worker.main() == 0
    assert time.time() - fast_worker.stat().st_mtime < 5


def test_worker_module_heartbeats_and_stops_cleanly_on_sigterm(test_settings: Settings) -> None:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "DATABASE_URL": test_settings.database_url.get_secret_value(),
        "SESSION_SECRET": test_settings.session_secret.get_secret_value(),
        "VIEWER_PASSWORD_HASH": test_settings.viewer_password_hash.get_secret_value(),
        "ADMIN_PASSWORD_HASH": test_settings.admin_password_hash.get_secret_value(),
    }
    # The real main() in its own process, but with a heartbeat path private to this run:
    # parallel worktrees share /tmp/worker-heartbeat, and another run's heartbeat must not
    # count as this worker's (SIGTERM would then arrive before its handler is installed).
    with tempfile.TemporaryDirectory() as scratch:
        heartbeat = Path(scratch) / "heartbeat"
        with subprocess.Popen(
            [sys.executable, "-c", RUN_WORKER_MAIN, str(heartbeat)],
            env=env,
            stderr=subprocess.DEVNULL,
        ) as proc:
            try:
                deadline = time.monotonic() + 30
                while proc.poll() is None and time.monotonic() < deadline:
                    if heartbeat.exists():
                        break
                    time.sleep(0.1)
                assert proc.poll() is None, "worker exited before its first heartbeat"
                assert heartbeat.exists(), "no heartbeat within 30 s"
                proc.send_signal(signal.SIGTERM)
                assert proc.wait(timeout=10) == 0
            finally:
                if proc.poll() is None:
                    proc.kill()
```

- [ ] **Step 28: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/integration/jobs -q`
Expected: FAIL. Collection error `ModuleNotFoundError: No module named 'sunday_clays.jobs.worker'`.

- [ ] **Step 29: Implement the worker stub**

Create `backend/src/sunday_clays/jobs/worker.py`:

```python
"""Worker entrypoint ``python -m sunday_clays.jobs.worker`` (C6 worker-health contract).

Plan 01 T1 stub: wait for the schema, then idle with a heartbeat until SIGTERM/SIGINT.
Plan 03 T7 replaces ``idle_until_stopped`` with ``run_worker`` and keeps everything else.
"""

import logging
import signal
import sys
import threading
import time
from pathlib import Path
from types import FrameType

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from sunday_clays.config import get_settings
from sunday_clays.db import make_engine, schema_is_current
from sunday_clays.logging import configure_logging

HEARTBEAT_PATH = Path("/tmp/worker-heartbeat")  # noqa: S108 - fixed path read by the healthcheck
POLL_SECONDS = 2.0
SCHEMA_TIMEOUT_SECONDS = 180.0

logger = logging.getLogger(__name__)


def touch_heartbeat(path: Path) -> None:
    path.touch()


def wait_for_schema(
    engine: Engine,
    stop: threading.Event,
    *,
    timeout_s: float,
    poll_s: float,
    heartbeat: Path,
) -> bool:
    """True once the DB is at the Alembic head; False on timeout or stop. Heartbeats every poll."""
    deadline = time.monotonic() + timeout_s
    while not stop.is_set():
        touch_heartbeat(heartbeat)
        try:
            if schema_is_current(engine):
                return True
        except SQLAlchemyError:
            logger.info("database not reachable yet")
        if time.monotonic() >= deadline:
            return False
        stop.wait(poll_s)
    return False


def idle_until_stopped(stop: threading.Event, *, poll_s: float, heartbeat: Path) -> None:
    while not stop.is_set():
        touch_heartbeat(heartbeat)
        stop.wait(poll_s)


def main() -> int:
    configure_logging()
    stop = threading.Event()

    def request_stop(signum: int, frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    engine = make_engine(get_settings().database_url.get_secret_value())
    try:
        current = wait_for_schema(
            engine,
            stop,
            timeout_s=SCHEMA_TIMEOUT_SECONDS,
            poll_s=POLL_SECONDS,
            heartbeat=HEARTBEAT_PATH,
        )
        if stop.is_set():
            return 0
        if not current:
            logger.error("schema not at the Alembic head after %.0f s", SCHEMA_TIMEOUT_SECONDS)
            return 1
        logger.info("schema is current; worker idle until stopped")
        idle_until_stopped(stop, poll_s=POLL_SECONDS, heartbeat=HEARTBEAT_PATH)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 30: Run them to verify they pass**

Run: `cd backend && uv run pytest tests/integration/jobs -q`
Expected: PASS, `8 passed`.

- [ ] **Step 31: Full local verification (master §0 step 4a, T1)**

Run:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src \
  && uv run pytest --cov --cov-branch \
  && uv run python -m sunday_clays.api.export_openapi --out /tmp/openapi.json \
  && python3 -c "import json; print(sorted(json.load(open('/tmp/openapi.json'))['paths']))"
```

Expected: `All checks passed!`, `… files already formatted`, `Success: no issues found in 17 source files`, `69 passed`, `Required test coverage of 90.0% reached. Total coverage: 100.00%`, then `['/api/health']`. If `ruff format --check` lists a file, run `uv run ruff format .` and re-run. Paste this output into the PR body; this task has no CI (master §0 step 4a).

- [ ] **Step 32: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/alembic.ini backend/migrations backend/src backend/tests/conftest.py backend/tests/unit backend/tests/integration
git commit -F - <<'EOF'
feat(backend): add FastAPI skeleton, settings, db, migrations scaffold and worker stub

Settings with *_FILE secrets and lazy get_settings(), JSON error handlers, a pure-ASGI
body-size limit, router auto-discovery with /api/health, the OpenAPI exporter, Alembic
scaffolding with connect retry and an advisory lock, the worker health-contract stub and
the shared pytest fixtures (engine, session, client).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 2: Frontend skeleton (master Plan 01 T2)

**Files:**
- Create: `.nvmrc`
- Create: `frontend/package.json`, `frontend/pnpm-lock.yaml` (generated by `pnpm install`)
- Create: `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/eslint.config.js`, `frontend/.prettierrc`, `frontend/.prettierignore`, `frontend/index.html`
- Create: `frontend/src/main.tsx`, `frontend/src/theme/theme.css`
- Create: `frontend/src/app/registry.ts`, `frontend/src/app/router.tsx`, `frontend/src/app/App.tsx`
- Create: `frontend/src/features/home/routes.tsx`, `frontend/src/features/home/pages/HomePage.tsx`
- Create: `frontend/src/test/setup.ts`, `frontend/src/test/msw/server.ts`, `frontend/src/test/msw/handlers.ts`, `frontend/src/test/render.tsx`
- Test: `frontend/src/test/setup.test.ts`, `frontend/src/app/registry.test.ts`, `frontend/src/app/router.test.tsx`, `frontend/src/app/App.test.tsx`

**Interfaces:**
- Consumes: `python -m sunday_clays.api.export_openapi --out <path>` (Task 1), through the `gen:api` script.
- Produces (later plans rely on these exact names):
  - `frontend/package.json` scripts: `gen:api` (exactly as C10), `pretypecheck: "pnpm gen:api"`, `typecheck: "tsc --noEmit"`, `lint: "eslint . --max-warnings 0"`, `test: "vitest run"`, `build: "vite build"`, `e2e: "playwright test"`, `dev`, `preview`, `format`, `test:watch`. Plus the complete Phase-1 frontend dependency set.
  - `src/app/registry.ts`: `interface NavItem { label: string; path: string; icon: LucideIcon; order: number; mobileTab?: boolean; adminOnly?: boolean }`, `interface FeatureModule { routes: RouteObject[]; nav?: NavItem[] }`, `collectFeatures(modules: Record<string, FeatureModule>): { routes: RouteObject[]; nav: NavItem[] }`, `featureRoutes: RouteObject[]`, `navItems: NavItem[]` (collected with `import.meta.glob('../features/*/routes.tsx', { eager: true })`).
  - `src/app/router.tsx`: `appRoutes: RouteObject[]` (`[{ path: '/', children: featureRoutes }]`) and `createAppRouter()`. Only Plan 07 T2/T3 edit this file.
  - `src/app/App.tsx`: `App` (Plan 07 T4 adds providers).
  - `src/test/render.tsx`: `renderWithProviders(ui: ReactElement, { route }?: { route?: string }): RenderResult` and `renderRoute(route: string, routes?: RouteObject[]): RenderResult` (Plan 07 T4/T3 add providers and session state).
  - `src/test/setup.ts`: every jsdom shim (matchMedia, ResizeObserver, IntersectionObserver, vitest-canvas-mock, `URL.createObjectURL`/`revokeObjectURL`, `navigator.share`/`canShare`, `scrollTo`, undici's global origin (relative `/api/...` URLs resolve against `window.location.origin`, as in a browser), `scrollIntoView`, pointer capture, jest-dom matchers, MSW lifecycle). It is never edited later.
  - `src/test/msw/server.ts`: `server`. `src/test/msw/handlers.ts`: `handlers: RequestHandler[]`, which merges the `handlers` export of every `src/features/<name>/mocks.ts`.
  - `src/features/home/routes.tsx`: the placeholder index route + nav item `{label: 'Home', path: '/', icon: House, order: 10, mobileTab: true}` (Plan 08 T4 replaces the page).
  - `src/theme/theme.css`: Tailwind v4 entry (`@import 'tailwindcss'`), imported by `main.tsx`. Plan 07 T1 adds the `@theme` tokens here.

**Branch:** `task/01-2-frontend-skeleton`

**Depends on:** T1

**Before you start:**
- Task 1 is merged: `backend/` exists, so `pnpm gen:api` can run the exporter with uv.
- Node 22: `nvm install 22 && nvm use 22` (after Step 1, a bare `nvm use` reads `.nvmrc`). Then `corepack enable` once, which puts `pnpm` on `PATH`. Inside `frontend/`, `pnpm --version` must print `10.34.5`.
- Run frontend commands in `frontend/`.

- [ ] **Step 1: Create `.nvmrc` and the package manifest**

Create `.nvmrc` at the repo root:

```text
22
```

Create `frontend/package.json`:

```json
{
  "name": "sunday-clays-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "packageManager": "pnpm@10.34.5",
  "engines": {
    "node": ">=22.13.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "gen:api": "uv run --project ../backend python -m sunday_clays.api.export_openapi --out ../openapi.json && openapi-typescript ../openapi.json -o src/api/schema.d.ts",
    "pretypecheck": "pnpm gen:api",
    "typecheck": "tsc --noEmit",
    "lint": "eslint . --max-warnings 0",
    "format": "prettier --write .",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@fontsource/roboto": "^5.3.0",
    "@tanstack/react-query": "^5.104.0",
    "echarts": "^6.1.0",
    "html-to-image": "^1.11.13",
    "lucide-react": "^1.48.0",
    "openapi-fetch": "^0.17.0",
    "react": "^19.3.0",
    "react-dom": "^19.3.0",
    "react-router": "^7.18.4"
  },
  "devDependencies": {
    "@eslint/js": "^10.0.1",
    "@playwright/test": "^1.63.0",
    "@tailwindcss/vite": "^4.3.3",
    "@testing-library/dom": "^10.4.2",
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.7",
    "@types/node": "^22.20.4",
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@vitejs/plugin-react": "^6.1.1",
    "@vitest/coverage-v8": "^5.0.2",
    "eslint": "^10.11.0",
    "eslint-plugin-react": "^7.37.5",
    "eslint-plugin-react-hooks": "^7.1.1",
    "globals": "^17.12.0",
    "jsdom": "^29.1.1",
    "msw": "^2.15.0",
    "openapi-typescript": "^7.13.0",
    "prettier": "^3.9.9",
    "tailwindcss": "^4.3.3",
    "typescript": "~5.9.3",
    "typescript-eslint": "^8.70.1",
    "vite": "^8.3.1",
    "vitest": "^5.0.2",
    "vitest-canvas-mock": "^1.2.0"
  },
  "pnpm": {
    "peerDependencyRules": {
      "allowedVersions": {
        "eslint-plugin-react>eslint": "10"
      }
    },
    "ignoredBuiltDependencies": [
      "msw"
    ]
  }
}
```

- [ ] **Step 2: Install and lock**

Run: `cd frontend && pnpm install`
Expected: `Done in …s using pnpm v10.34.5`, a new `frontend/pnpm-lock.yaml`, no `Ignored build scripts` box and no unmet-peer warnings.

- [ ] **Step 3: Create the tool configuration**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "types": ["vite/client", "node"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "erasableSyntaxOnly": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "noEmit": true,
    "allowImportingTsExtensions": true
  },
  "include": ["src", "e2e", "vite.config.ts", "vitest.config.ts", "playwright.config.ts"]
}
```

Create `frontend/vite.config.ts`:

```ts
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Same origin in dev as in production: the SPA and /api share one host (C8 CSRF, cookies).
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: false } },
  },
  build: { manifest: true },
});
```

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig, mergeConfig } from 'vitest/config';

import viteConfig from './vite.config.ts';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      restoreMocks: true,
      unstubGlobals: true,
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,tsx}'],
        exclude: [
          'src/main.tsx',
          'src/api/schema.d.ts',
          '**/*.d.ts',
          'e2e/**',
          'src/test/**',
          'src/**/*.test.{ts,tsx}',
        ],
        reporter: ['text', 'json-summary'],
        thresholds: { lines: 90, branches: 90 },
      },
    },
  }),
);
```

Create `frontend/eslint.config.js`:

```js
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig(
  {
    ignores: [
      'dist/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'src/api/schema.d.ts',
    ],
  },
  js.configs.recommended,
  tseslint.configs.strict,
  reactHooks.configs.flat.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react },
    settings: { react: { version: '19.3' } },
    rules: {
      'react/no-danger': 'error',
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'separate-type-imports' },
      ],
    },
  },
  {
    files: ['*.config.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
);
```

Create `frontend/.prettierrc`:

```json
{
  "singleQuote": true,
  "printWidth": 100,
  "trailingComma": "all"
}
```

Create `frontend/.prettierignore`:

```text
dist
coverage
playwright-report
test-results
e2e/.auth
pnpm-lock.yaml
src/api/schema.d.ts
```

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <meta name="theme-color" content="#1A4D2E" />
    <title>Sunday Clays</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `frontend/src/theme/theme.css`:

```css
/* Tailwind v4 entry. Plan 07 T1 adds the ClaySmasher @theme tokens to this file. */
@import 'tailwindcss';
```

- [ ] **Step 4: Write the failing test-harness test**

Create `frontend/src/test/setup.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

describe('jsdom shims from test/setup.ts', () => {
  it('provides the browser APIs charts, layout and sharing rely on', () => {
    expect(window.matchMedia('(min-width: 1024px)').matches).toBe(false);
    expect(() => new ResizeObserver(() => undefined).observe(document.body)).not.toThrow();
    expect(() => new IntersectionObserver(() => undefined).observe(document.body)).not.toThrow();
    expect(URL.createObjectURL(new Blob(['x']))).toBe('blob:mock-object-url');
    expect(navigator.canShare()).toBe(false);
    expect(document.createElement('canvas').getContext('2d')).not.toBeNull();
    expect(() => window.scrollTo(0, 0)).not.toThrow();
  });

  it('fails any request no MSW handler matches', async () => {
    await expect(fetch('http://localhost/api/unmocked')).rejects.toThrow();
  });

  it('resolves relative /api URLs against the page origin, so only MSW rejects them', async () => {
    expect(new Request('/api/unmocked').url).toBe(`${window.location.origin}/api/unmocked`);
    await expect(fetch('/api/unmocked')).rejects.toThrow();
  });
});
```

- [ ] **Step 5: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/test/setup.test.ts`
Expected: FAIL. `FAIL  src/test/setup.test.ts` with `Error: Cannot find module '…/frontend/src/test/setup.ts'` (the setup file named in `vitest.config.ts` does not exist yet).

- [ ] **Step 6: Implement the harness**

Create `frontend/src/test/setup.ts`:

```ts
/**
 * Every jsdom shim the app's tests need (C10). Never edited after Plan 01 T2: a test that needs
 * different behaviour overrides it for itself with vi.stubGlobal / vi.spyOn
 * (vitest.config.ts sets unstubGlobals and restoreMocks, so overrides never leak).
 */
import '@testing-library/jest-dom/vitest';
import 'vitest-canvas-mock';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';

import { server } from './msw/server';

function mediaQueryList(query: string): MediaQueryList {
  return {
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  };
}

class ResizeObserverStub implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

class IntersectionObserverStub implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = '0px';
  readonly scrollMargin = '0px';
  readonly thresholds: readonly number[] = [0];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

Object.defineProperty(window, 'matchMedia', { writable: true, value: mediaQueryList });
Object.defineProperty(window, 'scrollTo', { writable: true, value: () => undefined });
globalThis.ResizeObserver = ResizeObserverStub;
globalThis.IntersectionObserver = IntersectionObserverStub;
URL.createObjectURL = () => 'blob:mock-object-url';
URL.revokeObjectURL = () => undefined;
Element.prototype.scrollIntoView = () => undefined;
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => undefined;
Element.prototype.releasePointerCapture = () => undefined;
Object.defineProperty(navigator, 'share', { writable: true, value: () => Promise.resolve() });
Object.defineProperty(navigator, 'canShare', { writable: true, value: () => false });
// Node's fetch/Request (undici) reject relative URLs, but the SPA calls same-origin '/api/...'
// paths (C10 `baseUrl: ''`): resolve them against the jsdom page origin, as a browser does.
(globalThis as Record<symbol, unknown>)[Symbol.for('undici.globalOrigin.1')] = new URL(
  window.location.origin,
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());
```

Create `frontend/src/test/msw/server.ts`:

```ts
import { setupServer } from 'msw/node';

import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

Create `frontend/src/test/msw/handlers.ts`:

```ts
import type { RequestHandler } from 'msw';

/** Merges every src/features/<name>/mocks.ts `handlers` export (C10). */
const featureMocks = import.meta.glob<{ handlers: RequestHandler[] }>('../../features/*/mocks.ts', {
  eager: true,
});

export const handlers: RequestHandler[] = Object.keys(featureMocks)
  .sort()
  .flatMap((key) => featureMocks[key]?.handlers ?? []);
```

- [ ] **Step 7: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/test/setup.test.ts`
Expected: PASS, `3 passed`.

- [ ] **Step 8: Write the failing app-shell tests**

Create `frontend/src/test/render.tsx` (test helper used by these tests):

```tsx
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router';

import { appRoutes } from '../app/router';

/**
 * Test render helpers (C10). Plan 07 T4 adds the app providers here and Plan 07 T3 adds session
 * state; tests call these helpers instead of RTL's render so they get the same providers as App.
 */
export function renderWithProviders(ui: ReactElement, { route = '/' } = {}): RenderResult {
  const router = createMemoryRouter([{ path: '*', element: ui }], { initialEntries: [route] });
  return render(<RouterProvider router={router} />);
}

/** Renders the real route tree (lazy routes resolve asynchronously: use findBy* queries). */
export function renderRoute(route: string, routes: RouteObject[] = appRoutes): RenderResult {
  const router = createMemoryRouter(routes, { initialEntries: [route] });
  return render(<RouterProvider router={router} />);
}
```

Create `frontend/src/app/registry.test.ts`:

```ts
import { House, Trophy } from 'lucide-react';
import { describe, expect, it } from 'vitest';

import { collectFeatures, featureRoutes, navItems, type FeatureModule } from './registry';

describe('collectFeatures', () => {
  it('flattens routes in feature path order and sorts nav by order', () => {
    const modules: Record<string, FeatureModule> = {
      '../features/zeta/routes.tsx': {
        routes: [{ path: 'zeta' }],
        nav: [{ label: 'Zeta', path: '/zeta', icon: Trophy, order: 120 }],
      },
      '../features/alpha/routes.tsx': {
        routes: [{ path: 'alpha' }, { path: 'alpha/:id' }],
        nav: [{ label: 'Alpha', path: '/alpha', icon: House, order: 20 }],
      },
      '../features/beta/routes.tsx': { routes: [{ path: 'beta' }] },
    };

    const { routes, nav } = collectFeatures(modules);

    expect(routes.map((r) => r.path)).toEqual(['alpha', 'alpha/:id', 'beta', 'zeta']);
    expect(nav.map((n) => n.label)).toEqual(['Alpha', 'Zeta']);
  });

  it('returns empty lists when no feature exists', () => {
    expect(collectFeatures({})).toEqual({ routes: [], nav: [] });
  });
});

describe('the discovered registry', () => {
  it('includes the home feature as the index route and first nav item', () => {
    expect(featureRoutes.some((route) => route.index === true)).toBe(true);
    expect(navItems[0]).toMatchObject({ label: 'Home', path: '/', order: 10, mobileTab: true });
  });
});
```

Create `frontend/src/app/router.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderRoute } from '../test/render';
import { appRoutes, createAppRouter } from './router';

describe('app router', () => {
  it('renders the home page at /', async () => {
    renderRoute('/');

    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
  });

  it('builds a browser router over the same route tree', () => {
    const router = createAppRouter();

    expect(router.routes[0]?.path).toBe(appRoutes[0]?.path);
    router.dispose();
  });
});
```

Create `frontend/src/app/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('renders the routed home page', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/app`
Expected: FAIL. Three failed suites with `Failed to resolve import "./registry"` / `"./router"` / `"./App"` (or `"../app/router"` from `render.tsx`).

- [ ] **Step 10: Implement the registry, router, app and home placeholder**

Create `frontend/src/app/registry.ts`:

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

/** What every src/features/<name>/routes.tsx exports. */
export interface FeatureModule {
  routes: RouteObject[];
  nav?: NavItem[];
}

/** Flattens feature modules in path order; nav items are sorted by `order`. */
export function collectFeatures(modules: Record<string, FeatureModule>): {
  routes: RouteObject[];
  nav: NavItem[];
} {
  const features = Object.keys(modules)
    .sort()
    .map((key) => modules[key] as FeatureModule);
  return {
    routes: features.flatMap((feature) => feature.routes),
    nav: features.flatMap((feature) => feature.nav ?? []).sort((a, b) => a.order - b.order),
  };
}

const featureModules = import.meta.glob<FeatureModule>('../features/*/routes.tsx', {
  eager: true,
});

const collected = collectFeatures(featureModules);

/** Every feature's routes; children of the root route in router.tsx. */
export const featureRoutes: RouteObject[] = collected.routes;
/** Every feature's nav items, sorted by `order`. */
export const navItems: NavItem[] = collected.nav;
```

Create `frontend/src/app/router.tsx`:

```tsx
import { createBrowserRouter, type RouteObject } from 'react-router';

import { featureRoutes } from './registry';

/**
 * The route tree: one root route whose children come from the feature registry.
 * Only Plan 07 T2 (AppShell layout route) and Plan 07 T3 (RequireRole) may edit this file (C10).
 */
export const appRoutes: RouteObject[] = [{ path: '/', children: featureRoutes }];

export function createAppRouter(): ReturnType<typeof createBrowserRouter> {
  return createBrowserRouter(appRoutes);
}
```

Create `frontend/src/app/App.tsx`:

```tsx
// From 'react-router', never 'react-router/dom': under vitest the two load separate module
// instances with separate router contexts (C10).
import { RouterProvider } from 'react-router';

import { createAppRouter } from './router';

const router = createAppRouter();

/** Plan 07 T4 wraps this in the app providers (QueryClient, ErrorBoundary). */
export function App() {
  return <RouterProvider router={router} />;
}
```

Create `frontend/src/features/home/routes.tsx`:

```tsx
import { House } from 'lucide-react';
import type { RouteObject } from 'react-router';

import type { NavItem } from '../../app/registry';

/** Placeholder home route (Plan 01 T2); Plan 08 T4 builds the real page. */
export const routes: RouteObject[] = [
  {
    index: true,
    lazy: async () => ({ Component: (await import('./pages/HomePage')).HomePage }),
  },
];

export const nav: NavItem[] = [
  { label: 'Home', path: '/', icon: House, order: 10, mobileTab: true },
];
```

Create `frontend/src/features/home/pages/HomePage.tsx`:

```tsx
export function HomePage() {
  return (
    <main>
      <h1>Sunday Clays</h1>
      <p>Scores and stats for the Sunday Clays group.</p>
    </main>
  );
}
```

Create `frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './app/App';
import './theme/theme.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('index.html is missing <div id="root">');
}
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 11: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run`
Expected: PASS, `Test Files  4 passed (4)`, `Tests  9 passed (9)`.

- [ ] **Step 12: Full local verification (master §0 step 4a, T2)**

Run:

```bash
cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . \
  && pnpm test --coverage && pnpm build && pnpm gen:api && git status --porcelain && git diff --exit-code
```

Expected: eslint prints nothing after its banner. `typecheck` first runs `gen:api` (`🚀 ../openapi.json → src/api/schema.d.ts`), then `tsc` prints nothing. `All matched files use Prettier code style!`. `Tests  9 passed (9)` with a coverage summary of `Lines : 100%`, `Branches : 100%` (thresholds 90/90). `vite build` lists `dist/.vite/manifest.json`, one `index-*.js` of about 100 kB gzip and a lazy `HomePage-*.js`. `git status --porcelain` lists only this task's new files (before `git add`), none under `src/api/`, and `git diff --exit-code` exits 0; the generated `src/api/schema.d.ts` and `/openapi.json` are gitignored. Use `pnpm test --coverage`, not `pnpm test -- --coverage`: pnpm 10 would forward the literal `--` and Vitest would silently skip coverage (Decision 6). Paste this output into the PR body (master §0 step 4a).

- [ ] **Step 13: Commit**

```bash
git add .nvmrc frontend/package.json frontend/pnpm-lock.yaml frontend/tsconfig.json frontend/vite.config.ts \
  frontend/vitest.config.ts frontend/eslint.config.js frontend/.prettierrc frontend/.prettierignore \
  frontend/index.html frontend/src
git commit -F - <<'EOF'
feat(frontend): add React/Vite skeleton with feature registry and test harness

Vite 8 + React 19 + React Router 7 SPA whose routes come from src/features/*/routes.tsx,
Tailwind v4 entry, strict TypeScript, ESLint 10 (react/no-danger, consistent-type-imports),
Prettier, Vitest + Testing Library + MSW with every jsdom shim, 90% coverage thresholds,
and the gen:api script that types the API from the backend's OpenAPI schema.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 3: Coverage ratchet and bundle budgets (master Plan 01 T3)

**Files:**
- Create: `ratchets/baseline.json`, `ratchets/budgets.json`
- Create: `scripts/ratchet.py`, `scripts/bundle_stats.py` (standard library only)
- Modify: `.gitignore` (append `artifacts/` and `bundle-stats.json`)
- Test: `scripts/tests/test_ratchet.py`, `scripts/tests/test_bundle_stats.py`

**Interfaces:**
- Consumes: nothing. The inputs are CI artifacts: pytest-cov Cobertura XML (root `line-rate`/`branch-rate`), Vitest `json-summary` (`total.lines.pct`/`total.branches.pct`) and Vite's `dist/.vite/manifest.json`.
- Produces:
  - `python3 scripts/ratchet.py check|update [--baseline ratchets/baseline.json] [--budgets ratchets/budgets.json] [--backend-coverage artifacts/backend-coverage/coverage.xml] [--frontend-coverage artifacts/frontend-coverage/coverage-summary.json] [--bundle-stats artifacts/bundle-stats/bundle-stats.json]`. `check` exits 0 when all is well, 1 when a coverage value is below its baseline or a bundle metric is over budget (each such line starts with `FAIL`), and 2 on unusable input. `update` rewrites the baseline to `max(old, max(90.0, floor(measured) - 1.0))` per key.
  - `python3 scripts/bundle_stats.py [--dist frontend/dist] [--out bundle-stats.json]` writes `{"entry_js_gz_kb": float, "total_js_gz_kb": float, "chunks": {"assets/<file>.js": float}}`, with gzip KiB rounded to 2 dp.
  - `ratchets/baseline.json` holds exactly `backend_lines`, `backend_branches`, `frontend_lines` and `frontend_branches` (all `90.0`); `ratchets/budgets.json` is `{"entry_js_gz_kb": 250, "total_js_gz_kb": 1600}`. Only controller `chore/ratchet-*` PRs change `ratchets/` after this task.
  - Artifact layout, used by Task 5's `ci.yml` and by master §0 step 5b (`gh run download <run> -D artifacts`): `artifacts/backend-coverage/coverage.xml`, `artifacts/frontend-coverage/coverage-summary.json`, `artifacts/bundle-stats/bundle-stats.json`.

**Branch:** `task/01-3-ratchet`

**Depends on:** none

**Before you start:**
- Work at the repo root. The tests run with `uv run --no-project --with pytest --with pyyaml pytest scripts/tests` (uv 0.9.9+; Python comes from uv).
- The scripts use only the standard library (no third-party imports) so CI can run them with bare `python3`.

- [ ] **Step 1: Write the failing ratchet tests**

Create `scripts/tests/test_ratchet.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "ratchet.py"
BASELINE_90 = {
    "backend_lines": 90.0,
    "backend_branches": 90.0,
    "frontend_lines": 90.0,
    "frontend_branches": 90.0,
}


def write_inputs(
    root: Path,
    *,
    backend: tuple[float, float] = (0.95, 0.93),
    frontend: tuple[float, float] = (94.5, 91.25),
    bundle: tuple[float, float] = (120.0, 900.0),
    baseline: dict[str, float] | None = None,
) -> list[str]:
    """Writes baseline, budgets and the three CI artifacts; returns the CLI path flags."""
    (root / "baseline.json").write_text(json.dumps(baseline or BASELINE_90))
    (root / "budgets.json").write_text(json.dumps({"entry_js_gz_kb": 250, "total_js_gz_kb": 1600}))
    (root / "coverage.xml").write_text(
        f'<?xml version="1.0" ?><coverage line-rate="{backend[0]}" branch-rate="{backend[1]}"/>'
    )
    (root / "coverage-summary.json").write_text(
        json.dumps({"total": {"lines": {"pct": frontend[0]}, "branches": {"pct": frontend[1]}}})
    )
    (root / "bundle-stats.json").write_text(
        json.dumps({"entry_js_gz_kb": bundle[0], "total_js_gz_kb": bundle[1], "chunks": {}})
    )
    return [
        f"--baseline={root / 'baseline.json'}",
        f"--budgets={root / 'budgets.json'}",
        f"--backend-coverage={root / 'coverage.xml'}",
        f"--frontend-coverage={root / 'coverage-summary.json'}",
        f"--bundle-stats={root / 'bundle-stats.json'}",
    ]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_check_passes_when_coverage_meets_baseline_and_bundles_fit(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL" not in result.stdout


def test_check_fails_when_backend_branch_coverage_drops(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, backend=(0.95, 0.899)))

    assert result.returncode == 1
    assert "FAIL backend_branches: 89.90" in result.stdout


def test_check_fails_when_frontend_line_coverage_drops(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, frontend=(89.99, 95.0)))

    assert result.returncode == 1
    assert "FAIL frontend_lines" in result.stdout


def test_check_fails_when_entry_bundle_exceeds_budget(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, bundle=(250.01, 900.0)))

    assert result.returncode == 1
    assert "FAIL entry_js_gz_kb" in result.stdout


def test_check_fails_when_total_bundle_exceeds_budget(tmp_path: Path) -> None:
    result = run("check", *write_inputs(tmp_path, bundle=(100.0, 1600.5)))

    assert result.returncode == 1
    assert "FAIL total_js_gz_kb" in result.stdout


def test_check_compares_against_a_raised_baseline(tmp_path: Path) -> None:
    raised = BASELINE_90 | {"frontend_branches": 92.0}

    result = run("check", *write_inputs(tmp_path, frontend=(95.0, 91.5), baseline=raised))

    assert result.returncode == 1
    assert "FAIL frontend_branches: 91.50 (baseline 92.00)" in result.stdout


@pytest.mark.parametrize(
    "bad_baseline",
    [
        BASELINE_90 | {"ruff_violations": 0},
        {k: v for k, v in BASELINE_90.items() if k != "backend_lines"},
    ],
)
def test_baseline_must_have_exactly_the_four_coverage_keys(
    tmp_path: Path, bad_baseline: dict[str, float]
) -> None:
    result = run("check", *write_inputs(tmp_path, baseline=bad_baseline))

    assert result.returncode == 2
    assert "baseline.json" in result.stderr


def test_missing_artifact_is_reported_not_crashed(tmp_path: Path) -> None:
    flags = write_inputs(tmp_path)
    (tmp_path / "coverage.xml").unlink()

    result = run("check", *flags)

    assert result.returncode == 2
    assert "coverage.xml" in result.stderr


def test_update_raises_to_floor_minus_one_and_never_lowers(tmp_path: Path) -> None:
    old = {
        "backend_lines": 90.0,
        "backend_branches": 93.0,
        "frontend_lines": 90.0,
        "frontend_branches": 90.0,
    }
    flags = write_inputs(tmp_path, backend=(0.976, 0.912), frontend=(88.0, 90.9), baseline=old)

    result = run("update", *flags)

    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "baseline.json").read_text()) == {
        "backend_branches": 93.0,
        "backend_lines": 96.0,
        "frontend_branches": 90.0,
        "frontend_lines": 90.0,
    }


def test_update_writes_sorted_indented_json(tmp_path: Path) -> None:
    flags = write_inputs(tmp_path, backend=(0.99, 0.99), frontend=(99.0, 99.0))

    run("update", *flags)

    text = (tmp_path / "baseline.json").read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_update_ignores_bundle_budgets(tmp_path: Path) -> None:
    flags = write_inputs(tmp_path, bundle=(999.0, 9999.0))

    assert run("update", *flags).returncode == 0


def test_committed_ratchet_files_are_well_formed(tmp_path: Path) -> None:
    """The committed files parse and have exactly the expected keys, whatever their values.

    Perfect coverage and empty bundles pass any legal baseline (update never writes above 99)
    and any non-negative budget, so a chore/ratchet-* PR that raises the floors keeps this
    green, while a malformed or mis-keyed committed file still exits 2.
    """
    repo_ratchets = SCRIPT.parents[1] / "ratchets"
    flags = write_inputs(tmp_path, backend=(1.0, 1.0), frontend=(100.0, 100.0), bundle=(0.0, 0.0))
    flags[0] = f"--baseline={repo_ratchets / 'baseline.json'}"
    flags[1] = f"--budgets={repo_ratchets / 'budgets.json'}"

    result = run("check", *flags)

    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_ratchet.py -q`
Expected: FAIL. `13 failed`: each run of the missing script exits 2 with `can't open file '…/scripts/ratchet.py'`, e.g. `assert 2 == 0`.

- [ ] **Step 3: Create the ratchet files and the script**

Create `ratchets/baseline.json`:

```json
{
  "backend_branches": 90.0,
  "backend_lines": 90.0,
  "frontend_branches": 90.0,
  "frontend_lines": 90.0
}
```

Create `ratchets/budgets.json`:

```json
{
  "entry_js_gz_kb": 250,
  "total_js_gz_kb": 1600
}
```

Create `scripts/ratchet.py`:

```python
#!/usr/bin/env python3
"""Coverage ratchet and bundle budgets (C11). Standard library only.

check:  fail if any measured coverage is below ratchets/baseline.json or any bundle metric
        exceeds ratchets/budgets.json.
update: raise ratchets/baseline.json to max(old, max(90.0, floor(measured) - 1.0)); never lowers.
"""

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

COVERAGE_KEYS = ("backend_lines", "backend_branches", "frontend_lines", "frontend_branches")
BUDGET_KEYS = ("entry_js_gz_kb", "total_js_gz_kb")
FLOOR = 90.0


class RatchetError(Exception):
    """Unusable input file; reported with exit code 2."""


def _load_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RatchetError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RatchetError(f"{path} must hold a JSON object")
    return data


def _exact_keys(data: dict[str, object], keys: Sequence[str], path: Path) -> dict[str, float]:
    if sorted(data) != sorted(keys):
        raise RatchetError(
            f"{path} must have exactly the keys {sorted(keys)}, found {sorted(data)}"
        )
    values: dict[str, float] = {}
    for key in keys:
        value = data[key]
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise RatchetError(f"{path}: {key} must be a number")
        values[key] = float(value)
    return values


def read_backend_coverage(path: Path) -> dict[str, float]:
    """Cobertura XML from pytest-cov: root line-rate / branch-rate (0..1) as percentages."""
    try:
        root = ET.parse(path).getroot()
        return {
            "backend_lines": float(root.attrib["line-rate"]) * 100,
            "backend_branches": float(root.attrib["branch-rate"]) * 100,
        }
    except (OSError, ET.ParseError, KeyError, ValueError) as exc:
        raise RatchetError(f"cannot read backend coverage {path}: {exc}") from exc


def read_frontend_coverage(path: Path) -> dict[str, float]:
    """Vitest json-summary: total.lines.pct / total.branches.pct."""
    data = _load_json(path)
    try:
        total = data["total"]
        return {
            "frontend_lines": float(total["lines"]["pct"]),
            "frontend_branches": float(total["branches"]["pct"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RatchetError(f"cannot read frontend coverage {path}: {exc}") from exc


def read_bundle_stats(path: Path) -> dict[str, float]:
    """bundle-stats.json from scripts/bundle_stats.py (extra keys such as "chunks" ignored)."""
    data = _load_json(path)
    return _exact_keys({key: data.get(key) for key in BUDGET_KEYS}, BUDGET_KEYS, path)


def check(
    baseline: dict[str, float],
    budgets: dict[str, float],
    coverage: dict[str, float],
    bundle: dict[str, float],
) -> list[str]:
    """Report lines; entries starting with FAIL mean the check failed."""
    report: list[str] = []
    for key in COVERAGE_KEYS:
        ok = coverage[key] >= baseline[key]
        verdict = "ok" if ok else "FAIL"
        report.append(f"{verdict} {key}: {coverage[key]:.2f} (baseline {baseline[key]:.2f})")
    for key in BUDGET_KEYS:
        ok = bundle[key] <= budgets[key]
        verdict = "ok" if ok else "FAIL"
        report.append(f"{verdict} {key}: {bundle[key]:.2f} (budget {budgets[key]:.2f})")
    return report


def updated_baseline(baseline: dict[str, float], coverage: dict[str, float]) -> dict[str, float]:
    return {
        key: max(baseline[key], max(FLOOR, math.floor(coverage[key]) - 1.0))
        for key in COVERAGE_KEYS
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("command", choices=("check", "update"))
    parser.add_argument("--baseline", type=Path, default=Path("ratchets/baseline.json"))
    parser.add_argument("--budgets", type=Path, default=Path("ratchets/budgets.json"))
    parser.add_argument(
        "--backend-coverage", type=Path, default=Path("artifacts/backend-coverage/coverage.xml")
    )
    parser.add_argument(
        "--frontend-coverage",
        type=Path,
        default=Path("artifacts/frontend-coverage/coverage-summary.json"),
    )
    parser.add_argument(
        "--bundle-stats", type=Path, default=Path("artifacts/bundle-stats/bundle-stats.json")
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        baseline = _exact_keys(_load_json(args.baseline), COVERAGE_KEYS, args.baseline)
        coverage = read_backend_coverage(args.backend_coverage) | read_frontend_coverage(
            args.frontend_coverage
        )
        if args.command == "update":
            new = updated_baseline(baseline, coverage)
            args.baseline.write_text(
                json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            for key in COVERAGE_KEYS:
                print(f"{key}: {baseline[key]:.2f} -> {new[key]:.2f}")
            return 0
        budgets = _exact_keys(_load_json(args.budgets), BUDGET_KEYS, args.budgets)
        bundle = read_bundle_stats(args.bundle_stats)
    except RatchetError as exc:
        print(f"ratchet: {exc}", file=sys.stderr)
        return 2
    report = check(baseline, budgets, coverage, bundle)
    print("\n".join(report))
    return 1 if any(line.startswith("FAIL") for line in report) else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_ratchet.py -q`
Expected: PASS, `13 passed`.

- [ ] **Step 5: Write the failing bundle-stats tests**

Create `scripts/tests/test_bundle_stats.py`:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "bundle_stats.py"


def build_dist(root: Path) -> Path:
    """A fake Vite dist: entry -> static shared chunk; a lazy route chunk; a CSS file."""
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / ".vite").mkdir()
    (dist / "assets" / "index-a1.js").write_bytes(os.urandom(20 * 1024))
    (dist / "assets" / "shared-b2.js").write_bytes(os.urandom(10 * 1024))
    (dist / "assets" / "HomePage-c3.js").write_bytes(b"a" * 200_000)
    (dist / "assets" / "index-d4.css").write_bytes(os.urandom(50 * 1024))
    manifest = {
        "index.html": {
            "file": "assets/index-a1.js",
            "isEntry": True,
            "imports": ["_shared-b2.js"],
            "dynamicImports": ["src/features/home/pages/HomePage.tsx"],
            "css": ["assets/index-d4.css"],
        },
        "_shared-b2.js": {"file": "assets/shared-b2.js", "imports": ["index.html"]},
        "src/features/home/pages/HomePage.tsx": {
            "file": "assets/HomePage-c3.js",
            "isDynamicEntry": True,
            "imports": ["index.html", "_shared-b2.js"],
        },
    }
    (dist / ".vite" / "manifest.json").write_text(json.dumps(manifest))
    return dist


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_entry_counts_entry_and_static_imports_but_not_lazy_chunks(tmp_path: Path) -> None:
    dist = build_dist(tmp_path)
    out = tmp_path / "bundle-stats.json"

    result = run(f"--dist={dist}", f"--out={out}")

    assert result.returncode == 0, result.stderr
    stats = json.loads(out.read_text())
    assert 30.0 <= stats["entry_js_gz_kb"] <= 30.2
    assert stats["total_js_gz_kb"] - stats["entry_js_gz_kb"] < 1.0
    assert stats["chunks"]["assets/HomePage-c3.js"] < 1.0
    assert "assets/index-d4.css" not in stats["chunks"]


def test_manifest_without_an_entry_is_an_error(tmp_path: Path) -> None:
    dist = build_dist(tmp_path)
    (dist / ".vite" / "manifest.json").write_text(json.dumps({"x.js": {"file": "assets/x.js"}}))

    result = run(f"--dist={dist}", f"--out={tmp_path / 'o.json'}")

    assert result.returncode == 2
    assert "no entry chunk" in result.stderr


def test_manifest_naming_a_missing_chunk_is_an_error(tmp_path: Path) -> None:
    dist = build_dist(tmp_path)
    (dist / "assets" / "shared-b2.js").unlink()

    result = run(f"--dist={dist}", f"--out={tmp_path / 'o.json'}")

    assert result.returncode == 2
    assert "assets/shared-b2.js" in result.stderr


def test_missing_dist_is_an_error(tmp_path: Path) -> None:
    result = run(f"--dist={tmp_path / 'nope'}", f"--out={tmp_path / 'o.json'}")

    assert result.returncode == 2
    assert "bundle_stats:" in result.stderr
    assert "nope" in result.stderr
```

- [ ] **Step 6: Run them to verify they fail**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_bundle_stats.py -q`
Expected: FAIL. `4 failed`: Python itself exits 2 with `can't open file '…/scripts/bundle_stats.py'`, so the tests fail on `assert 2 == 0` or on the missing `no entry chunk` / `assets/shared-b2.js` / `bundle_stats:` message (the exit code alone would not tell the script's own error handling from a missing script).

- [ ] **Step 7: Implement the bundle-stats script**

Create `scripts/bundle_stats.py`:

```python
#!/usr/bin/env python3
"""Gzip size of every built JS chunk for the bundle budgets (C11). Standard library only.

entry_js_gz_kb = the Vite entry chunk(s) plus every chunk they import statically (the JS a
first page load must fetch); total_js_gz_kb = every dist/assets/*.js.
"""

import argparse
import gzip
import json
import sys
from collections.abc import Sequence
from pathlib import Path


def gzip_bytes(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), compresslevel=9, mtime=0))


def entry_files(manifest: dict[str, dict[str, object]]) -> set[str]:
    """Output files of the entry chunks and their static-import closure."""
    pending = [key for key, chunk in manifest.items() if chunk.get("isEntry") is True]
    seen_keys: set[str] = set()
    files: set[str] = set()
    while pending:
        key = pending.pop()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        chunk = manifest[key]
        file = str(chunk["file"])
        if file.endswith(".js"):
            files.add(file)
        imports = chunk.get("imports", [])
        if isinstance(imports, list):
            pending.extend(str(item) for item in imports)
    return files


def bundle_stats(dist: Path) -> dict[str, object]:
    manifest = json.loads((dist / ".vite" / "manifest.json").read_text(encoding="utf-8"))
    sizes = {f"assets/{p.name}": gzip_bytes(p) for p in sorted((dist / "assets").glob("*.js"))}
    entries = entry_files(manifest)
    if not entries:
        raise ValueError(f"no entry chunk in {dist / '.vite' / 'manifest.json'}")
    missing = sorted(entries - sizes.keys())
    if missing:
        raise ValueError(f"manifest names chunks missing from dist/assets: {missing}")
    return {
        "entry_js_gz_kb": round(sum(sizes[f] for f in entries) / 1024, 2),
        "total_js_gz_kb": round(sum(sizes.values()) / 1024, 2),
        "chunks": {name: round(size / 1024, 2) for name, size in sizes.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--out", type=Path, default=Path("bundle-stats.json"))
    args = parser.parse_args(argv)
    try:
        stats = bundle_stats(args.dist)
    except (OSError, ValueError, KeyError) as exc:
        print(f"bundle_stats: {exc}", file=sys.stderr)
        return 2
    args.out.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"entry_js_gz_kb={stats['entry_js_gz_kb']} total_js_gz_kb={stats['total_js_gz_kb']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Run them to verify they pass**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_bundle_stats.py -q`
Expected: PASS, `4 passed`.

- [ ] **Step 9: Ignore local ratchet inputs**

Append to `.gitignore`:

```text
# ratchet inputs downloaded from CI and the local bundle report (scripts/ratchet.py, bundle_stats.py)
artifacts/
bundle-stats.json
```

Run: `git check-ignore -v artifacts/backend-coverage/coverage.xml bundle-stats.json`
Expected: two lines naming `.gitignore` and the matching pattern.

- [ ] **Step 10: Full local verification (master §0 step 4a, T3)**

Run:

```bash
uv run --no-project --with pytest --with pyyaml pytest scripts/tests && python3 scripts/ratchet.py --help | head -3 && python3 scripts/bundle_stats.py --help | head -1
```

Expected: `17 passed`, then the two usage lines (`usage: ratchet.py [-h] …`, `usage: bundle_stats.py [-h] …`). Paste this output into the PR body (master §0 step 4a).

- [ ] **Step 11: Commit**

```bash
git add ratchets/baseline.json ratchets/budgets.json scripts/ratchet.py scripts/bundle_stats.py \
  scripts/tests/test_ratchet.py scripts/tests/test_bundle_stats.py .gitignore
git commit -F - <<'EOF'
feat(ci): add coverage ratchet and bundle budget scripts

ratchet.py checks backend/frontend line and branch coverage against ratchets/baseline.json
and bundle sizes against ratchets/budgets.json, and raises the baseline (never lowers it);
bundle_stats.py measures gzip sizes of the entry closure and all built JS chunks.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 4: Containers, Caddy, compose stack, backups, deploy runbook and Playwright smoke (master Plan 01 T4)

**Files:**
- Create: `backend/Dockerfile`, `backend/.dockerignore`
- Create: `backend/backup/backup.sh`, `backend/backup/restore.sh`, `backend/backup/verify-restore.sh`, `backend/backup/backup_tools.py`
- Create: `frontend/Dockerfile`, `.dockerignore` (repo root), `deploy/caddy/Caddyfile`
- Create: `compose.yaml`, `compose.override.yaml`, `compose.test.yaml`, `compose.swarm.yaml`
- Create: `scripts/dev-secrets.sh`
- Create: `frontend/playwright.config.ts`, `frontend/e2e/fixtures.ts`, `frontend/e2e/smoke.spec.ts`
- Create: `deploy/README.md`
- Modify: `.gitignore` (append `**/e2e/.auth/`)
- Test: `backend/tests/unit/backup/test_backup_tools.py`, `backend/tests/unit/backup/test_backup_sh.py`, `scripts/tests/test_dev_secrets.py`, `frontend/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: Task 1: `sunday_clays.api.app:create_app` (uvicorn `--factory`), `GET /api/health`, `python -m sunday_clays.jobs.worker` (heartbeat `/tmp/worker-heartbeat`), `backend/alembic.ini` + `migrations/`, the `DATABASE_URL_FILE`/`SESSION_SECRET_FILE`/`VIEWER_PASSWORD_HASH_FILE`/`ADMIN_PASSWORD_HASH_FILE` settings and the `APP_VERSION` env. Task 2: `frontend/package.json` (`pnpm build` = `vite build`; `@playwright/test`), `.nvmrc`.
- Produces:
  - Images `ghcr.io/gitgat/sunday-clays-backend:<tag>` (context `backend/`; uid 10001; `WORKDIR /app` with `alembic.ini`, `migrations/`, `/app/backup/*.sh`; `pg_dump`/`psql` 17; build arg `APP_VERSION`) and `ghcr.io/gitgat/sunday-clays-frontend:<tag>` (context repo root, `-f frontend/Dockerfile`; Caddy serving `/srv`).
  - Compose services exactly `caddy`, `api`, `worker`, `db`, `backup`; secrets `session_secret`, `viewer_password_hash`, `admin_password_hash`, `db_password`, `database_url` (+ Swarm-only `backup_hc_url`); named volumes `db-data`, `backups`.
  - `scripts/dev-secrets.sh` (env `VIEWER_PASSWORD`, `ADMIN_PASSWORD`; writes `./secrets/*`, never overwrites).
  - `backend/backup/backup.sh [--once]`, `restore.sh <dump> [db]`, `verify-restore.sh`, `backup_tools.py prune <dir> | seconds-until HH:MM`.
  - `frontend/playwright.config.ts`: projects `desktop` (1440×900) and `mobile` (390×844, Chromium), `baseURL` `http://localhost:8080`. Plan 04 T1 adds the `setup` project; Plan 08 T5a adds `admin-mutations`.
  - `frontend/e2e/fixtures.ts`: `export const test` (with the auto fixture `pageProblems: string[]`) and `export { expect }`. Every later spec imports `test`/`expect` from here.
  - `frontend/e2e/smoke.spec.ts` (Plan 07 T3 appends the unauthenticated-redirect check).

**Branch:** `task/01-4-containers-e2e`

**Depends on:** T1, T2

**Before you start:**
- Tasks 1 and 2 are merged. Docker is running, and host port 8080 is free (`lsof -iTCP:8080 -sTCP:LISTEN` prints nothing).
- Node 22 + `corepack enable` as in Task 2; uv 0.9.9+; `openssl` on `PATH`.
- Work at the repo root unless a step says otherwise.
- A local hook may block shell commands whose text contains `get_secret_value`; write files with your editor's write tool.

- [ ] **Step 1: Keep Playwright session state out of git**

Append to `.gitignore`:

```text
# Playwright storage state (session cookies) under frontend/e2e/.auth/ (the entry above matches only a root e2e/)
**/e2e/.auth/
```

Run: `git check-ignore -v frontend/e2e/.auth/viewer.json`
Expected: `.gitignore:<line>:**/e2e/.auth/	frontend/e2e/.auth/viewer.json`.

- [ ] **Step 2: Write the failing backup-tools and backup.sh tests**

Create `backend/tests/unit/backup/test_backup_tools.py`:

```python
import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType

TOOLS_PATH = Path(__file__).resolve().parents[3] / "backup" / "backup_tools.py"


def load_tools() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backup_tools", TOOLS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tools = load_tools()


def test_restart_loop_cannot_push_older_days_out() -> None:
    today = date(2026, 9, 27)
    restart_loop = [f"sc-20260927T{h:02d}0000Z.dump" for h in range(20)]
    older_days = [f"sc-202609{d:02d}T093000Z.dump" for d in range(14, 27)]

    keep = tools.dumps_to_keep(restart_loop + older_days, today)

    assert set(older_days) <= keep
    assert "sc-20260927T190000Z.dump" in keep
    assert keep & set(restart_loop) == {"sc-20260927T190000Z.dump"}


def test_keeps_fourteen_daily_and_eight_weekly() -> None:
    today = date(2026, 9, 27)
    daily_for_ten_weeks = [
        f"sc-{(date.fromordinal(today.toordinal() - n)).strftime('%Y%m%d')}T093000Z.dump"
        for n in range(70)
    ]

    keep = tools.dumps_to_keep(daily_for_ten_weeks, today)

    assert {f"sc-202609{d:02d}T093000Z.dump" for d in range(14, 28)} <= keep
    assert "sc-20260913T093000Z.dump" in keep  # Sunday: newest of ISO week 37
    assert "sc-20260912T093000Z.dump" not in keep
    assert "sc-20260809T093000Z.dump" in keep  # Sunday of ISO week 32, the 8th week back
    assert "sc-20260802T093000Z.dump" not in keep  # ISO week 31 is outside the window
    assert len(keep) == 14 + 6


def test_prune_deletes_unkept_dumps_and_temp_files(tmp_path: Path) -> None:
    for name in [
        "sc-20260927T093000Z.dump",
        "sc-20260927T080000Z.dump",
        "sc-20260101T093000Z.dump",
        "sc-20260927T100000Z.dump.tmp",
        "last_success",
    ]:
        (tmp_path / name).write_text("x")

    deleted = tools.prune(tmp_path, datetime(2026, 9, 27, 12, tzinfo=UTC))

    assert deleted == [
        "sc-20260101T093000Z.dump",
        "sc-20260927T080000Z.dump",
        "sc-20260927T100000Z.dump.tmp",
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "last_success",
        "sc-20260927T093000Z.dump",
    ]


def test_seconds_until_later_today() -> None:
    now = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)  # 01:00 PDT

    assert tools.seconds_until("02:30", now) == 90 * 60


def test_seconds_until_rolls_to_tomorrow() -> None:
    now = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)  # 03:00 PDT

    assert tools.seconds_until("02:30", now) == 23 * 3600 + 30 * 60


def test_seconds_until_across_fall_back() -> None:
    now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)  # Sat 03:00 PDT; clocks fall back Sun 02:00

    assert tools.seconds_until("02:30", now) == 24 * 3600 + 30 * 60


def test_cli_rejects_unknown_command() -> None:
    assert tools.main(["explode"]) == 2
```

Create `backend/tests/unit/backup/test_backup_sh.py`. It runs the real `backup.sh --once` with stub `pg_dump`/`pg_restore` first on `PATH` and a local HTTP server standing in for Healthchecks.io, so the failure paths run without a database:

```python
"""backup.sh --once with stub pg_dump/pg_restore: only a verified dump counts as a success.

Bash ignores `set -e` inside a function called from an `if` condition, so every step of
dump_once must propagate its own failure. These tests pin that: a failed or unverifiable dump
exits 1, keeps no sc-*.dump, leaves last_success alone and pings Healthchecks' /fail URL.
"""

import os
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

BACKUP_SH = Path(__file__).resolve().parents[3] / "backup" / "backup.sh"
BASH = shutil.which("bash") or "/bin/bash"

WRITES_DUMP = """#!/usr/bin/env bash
for arg in "$@"; do
  case "$arg" in --file=*) printf 'PGDMP stub' >"${arg#--file=}" ;; esac
done
"""
WRITES_PART_THEN_FAILS = WRITES_DUMP + "exit 1\n"
FAILS = "#!/usr/bin/env bash\nexit 1\n"
SUCCEEDS = "#!/usr/bin/env bash\nexit 0\n"


@dataclass
class Healthchecks:
    """A local stand-in for Healthchecks.io: the URL file backup.sh reads and every ping path."""

    url_file: Path
    pings: list[str]


@pytest.fixture
def healthchecks(tmp_path: Path) -> Iterator[Healthchecks]:
    pings: list[str] = []

    class Recorder(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            pings.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            """Keeps the test output quiet."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url_file = tmp_path / "backup_hc_url"
    url_file.write_text(f"http://127.0.0.1:{server.server_address[1]}/check-uuid\n")
    try:
        yield Healthchecks(url_file=url_file, pings=pings)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def run_backup_once(
    tmp_path: Path, *, pg_dump: str, pg_restore: str, hc_url_file: Path
) -> subprocess.CompletedProcess[str]:
    """backup.sh --once with the stubs first on PATH; dumps go to tmp_path/backups."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("pg_dump", pg_dump), ("pg_restore", pg_restore)):
        stub = bin_dir / name
        stub.write_text(body)
        stub.chmod(0o755)
    (tmp_path / "backups").mkdir()
    password_file = tmp_path / "db_password"
    password_file.write_text("stub-password")
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "BACKUP_DIR": str(tmp_path / "backups"),
        "POSTGRES_PASSWORD_FILE": str(password_file),
        "BACKUP_HC_URL_FILE": str(hc_url_file),
    }
    return subprocess.run(
        [BASH, str(BACKUP_SH), "--once"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def kept_dumps(tmp_path: Path) -> list[str]:
    return sorted(p.name for p in (tmp_path / "backups").glob("sc-*.dump"))


@pytest.mark.parametrize(
    "pg_dump", [FAILS, WRITES_PART_THEN_FAILS], ids=["no-output", "partial-output"]
)
def test_failed_pg_dump_is_reported_as_a_failure(
    tmp_path: Path, healthchecks: Healthchecks, pg_dump: str
) -> None:
    result = run_backup_once(
        tmp_path, pg_dump=pg_dump, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 1
    assert "backup: dump failed" in result.stderr
    assert kept_dumps(tmp_path) == []
    assert not (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid/fail"]


def test_dump_that_pg_restore_cannot_list_is_never_kept(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=FAILS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 1
    assert kept_dumps(tmp_path) == []
    assert not (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid/fail"]


def test_verified_dump_is_kept_and_reported(tmp_path: Path, healthchecks: Healthchecks) -> None:
    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 0, result.stderr
    dumps = kept_dumps(tmp_path)
    assert len(dumps) == 1
    assert re.fullmatch(r"sc-\d{8}T\d{6}Z\.dump", dumps[0])
    assert (tmp_path / "backups" / "last_success").exists()
    assert healthchecks.pings == ["/check-uuid"]


def test_empty_healthcheck_url_file_means_no_ping(
    tmp_path: Path, healthchecks: Healthchecks
) -> None:
    healthchecks.url_file.write_text("")

    result = run_backup_once(
        tmp_path, pg_dump=WRITES_DUMP, pg_restore=SUCCEEDS, hc_url_file=healthchecks.url_file
    )

    assert result.returncode == 0, result.stderr
    assert healthchecks.pings == []
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/unit/backup/test_backup_tools.py -q; uv run pytest tests/unit/backup/test_backup_sh.py -q`
Expected: FAIL, twice. First a collection error `FileNotFoundError: [Errno 2] No such file or directory: '…/backend/backup/backup_tools.py'`. Then `5 failed`: bash exits 127 on the missing `backup.sh`, so every test fails its first assertion (`assert 127 == 1` or `assert 127 == 0`). Run the two files separately: a collection error in one file stops pytest before it runs the other.

- [ ] **Step 4: Implement retention, scheduling and the verified dump script**

Create `backend/backup/backup_tools.py`:

```python
"""Date-based backup retention and the nightly schedule for backup.sh (stdlib only).

python3 backup_tools.py prune <dir>          delete dumps outside 14 daily + 8 weekly slots
python3 backup_tools.py seconds-until HH:MM  seconds until the next HH:MM America/Los_Angeles
"""

import re
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DUMP_NAME = re.compile(r"^sc-(\d{8}T\d{6}Z)\.dump$")
KEEP_DAILY = 14
KEEP_WEEKLY = 8
LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def dump_time(name: str) -> datetime | None:
    match = DUMP_NAME.match(name)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)


def dumps_to_keep(names: Iterable[str], today: date) -> set[str]:
    """Newest dump of each of the last 14 UTC days and of each of the last 8 ISO weeks."""
    stamped = sorted(((t, n) for n in names if (t := dump_time(n)) is not None), reverse=True)
    keep: set[str] = set()
    days_seen: set[date] = set()
    weeks_seen: set[tuple[int, int]] = set()
    first_day = today - timedelta(days=KEEP_DAILY - 1)
    this_week = today.isocalendar()
    first_week_monday = date.fromisocalendar(this_week.year, this_week.week, 1) - timedelta(
        weeks=KEEP_WEEKLY - 1
    )
    for taken, name in stamped:
        day = taken.date()
        week = (day.isocalendar().year, day.isocalendar().week)
        if day >= first_day and day not in days_seen:
            days_seen.add(day)
            keep.add(name)
        if day >= first_week_monday and week not in weeks_seen:
            weeks_seen.add(week)
            keep.add(name)
    return keep


def prune(directory: Path, now: datetime) -> list[str]:
    """Deletes dumps that are not kept and leftover *.dump.tmp files; returns deleted names."""
    names = [p.name for p in directory.iterdir()]
    keep = dumps_to_keep(names, now.astimezone(UTC).date())
    deleted = []
    for name in sorted(names):
        if (DUMP_NAME.match(name) and name not in keep) or name.endswith(".dump.tmp"):
            (directory / name).unlink()
            deleted.append(name)
    return deleted


def seconds_until(hhmm: str, now: datetime) -> int:
    """Seconds from ``now`` until the next local HH:MM in America/Los_Angeles (DST-safe)."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    local_now = now.astimezone(LOCAL_TZ)
    target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local_now:
        target = (local_now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    return max(1, int((target.astimezone(UTC) - now.astimezone(UTC)).total_seconds()))


def main(argv: Sequence[str]) -> int:
    if len(argv) == 2 and argv[0] == "prune":
        for name in prune(Path(argv[1]), datetime.now(UTC)):
            print(f"pruned {name}")
        return 0
    if len(argv) == 2 and argv[0] == "seconds-until":
        print(seconds_until(argv[1], datetime.now(UTC)))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Create `backend/backup/backup.sh`:

```bash
#!/usr/bin/env bash
# Verified pg_dump of the sunday_clays DB (run by the `backup` service; C1, Plan 01 T4).
#   backup.sh          dump once at start, then daily at 02:30 America/Los_Angeles
#   backup.sh --once   one verified dump, then exit (used by verify-restore.sh)
# Env: PGHOST PGUSER PGDATABASE POSTGRES_PASSWORD_FILE [BACKUP_HC_URL_FILE] [BACKUP_DIR=/backups]
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
TOOLS="$(dirname "$0")/backup_tools.py"
PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
export PGPASSWORD

ping_healthcheck() { # suffix: "" on success, "/fail" on failure
  [[ -n "${BACKUP_HC_URL_FILE:-}" && -s "${BACKUP_HC_URL_FILE}" ]] || return 0
  local url
  url="$(tr -d '[:space:]' <"$BACKUP_HC_URL_FILE")$1"
  python3 -c 'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=10)' "$url" \
    || echo "backup: healthcheck ping failed" >&2
}

# Always called as `if dump_once`, where bash ignores `set -e`: every step must propagate its
# own failure, or a failed or unverifiable dump would be reported (and pinged) as a success.
dump_once() {
  local stamp tmp
  stamp="$(date -u +%Y%m%dT%H%M%SZ)" || return 1
  tmp="$BACKUP_DIR/sc-$stamp.dump.tmp"
  pg_dump --format=custom --file="$tmp" || return 1
  pg_restore --list "$tmp" >/dev/null || return 1
  mv "$tmp" "$BACKUP_DIR/sc-$stamp.dump" || return 1
  python3 "$TOOLS" prune "$BACKUP_DIR" || return 1
  touch "$BACKUP_DIR/last_success" || return 1
  echo "backup: wrote $BACKUP_DIR/sc-$stamp.dump"
}

run_dump() {
  if dump_once; then
    ping_healthcheck ""
  else
    echo "backup: dump failed" >&2
    ping_healthcheck "/fail"
    return 1
  fi
}

if [[ "${1:-}" == "--once" ]]; then
  run_dump
  exit $?
fi

trap 'exit 0' TERM INT
for _ in $(seq 60); do
  pg_isready --quiet && break
  sleep 2
done
run_dump || true
while true; do
  sleep "$(python3 "$TOOLS" seconds-until 02:30)" &
  wait $!
  run_dump || true
done
```

(A failed `pg_dump` can leave `sc-<UTC>.dump.tmp` behind; the next successful run's `prune` deletes it, and it never matches `sc-*.dump`.)

Run: `chmod +x backend/backup/backup.sh`

- [ ] **Step 5: Run them to verify they pass, then prove the backup.sh tests catch the `set -e` trap**

Run: `cd backend && uv run pytest tests/unit/backup -q && uv run ruff check backup tests/unit/backup && uv run ruff format --check backup tests/unit/backup`
Expected: PASS, `12 passed` (7 backup-tools + 5 backup.sh), `All checks passed!`, `3 files already formatted`.

Mutation check (do not commit it): delete every ` || return 1` from `dump_once`, which restores the silently-succeeding version, then re-run only the shell tests:

Run: `cd backend && cp backup/backup.sh /tmp/backup.sh.good && sed -i.bak 's/ || return 1$//' backup/backup.sh && uv run pytest tests/unit/backup/test_backup_sh.py -q; cp /tmp/backup.sh.good backup/backup.sh && rm -f backup/backup.sh.bak && uv run pytest tests/unit/backup/test_backup_sh.py -q`
Expected: first `3 failed, 2 passed` (both `test_failed_pg_dump_is_reported_as_a_failure` cases and `test_dump_that_pg_restore_cannot_list_is_never_kept` fail on `assert 0 == 1`: the dump "succeeds", keeps a partial or unverified `sc-*.dump` and pings the success URL), then `5 passed` with the file restored to Step 4's version.

- [ ] **Step 6: Write the failing dev-secrets tests**

Create `scripts/tests/test_dev_secrets.py`:

```python
import os
import shutil
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "dev-secrets.sh"
NAMES = [
    "admin_password_hash",
    "database_url",
    "db_password",
    "session_secret",
    "viewer_password_hash",
]


def run_in_copy(root: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Runs a copy of dev-secrets.sh from <root>/scripts so it writes <root>/secrets."""
    (root / "scripts").mkdir(exist_ok=True)
    shutil.copy2(SCRIPT, root / "scripts" / "dev-secrets.sh")
    full_env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", str(root)),
        **(env or {}),
    }
    return subprocess.run(
        ["bash", str(root / "scripts" / "dev-secrets.sh")],
        env=full_env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def argon2_verifies(hashed: str, password: str) -> bool:
    code = (
        "import sys\nfrom argon2 import PasswordHasher\n"
        "print(PasswordHasher().verify(sys.argv[1], sys.argv[2]))"
    )
    result = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "--no-project",
            "--with",
            "argon2-cffi",
            "python",
            "-c",
            code,
            hashed,
            password,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    return result.stdout.strip() == "True"


def test_writes_every_secret_with_the_given_passwords(tmp_path: Path) -> None:
    result = run_in_copy(tmp_path, {"VIEWER_PASSWORD": "e2e-viewer", "ADMIN_PASSWORD": "e2e-admin"})

    assert result.returncode == 0, result.stderr
    secrets = tmp_path / "secrets"
    assert sorted(p.name for p in secrets.iterdir()) == NAMES
    viewer_hash = (secrets / "viewer_password_hash").read_text()
    assert viewer_hash.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert argon2_verifies(viewer_hash, "e2e-viewer")
    assert argon2_verifies((secrets / "admin_password_hash").read_text(), "e2e-admin")
    db_password = (secrets / "db_password").read_text()
    assert len(db_password) == 64
    assert (secrets / "database_url").read_text() == (
        f"postgresql+psycopg://sunday:{db_password}@db:5432/sunday_clays"
    )
    assert len((secrets / "session_secret").read_text()) == 64
    assert stat.S_IMODE(secrets.stat().st_mode) == 0o700
    assert "shown once" not in result.stdout


def test_never_overwrites_existing_secrets(tmp_path: Path) -> None:
    run_in_copy(tmp_path, {"VIEWER_PASSWORD": "first", "ADMIN_PASSWORD": "first"})
    before = {p.name: p.read_text() for p in (tmp_path / "secrets").iterdir()}

    result = run_in_copy(tmp_path, {"VIEWER_PASSWORD": "second", "ADMIN_PASSWORD": "second"})

    assert result.returncode == 0, result.stderr
    assert {p.name: p.read_text() for p in (tmp_path / "secrets").iterdir()} == before


def test_generates_and_prints_passwords_when_unset(tmp_path: Path) -> None:
    result = run_in_copy(tmp_path)

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if "shown once" in line]
    assert len(lines) == 2
    viewer_password = next(line for line in lines if "viewer" in line).rsplit(": ", 1)[1]
    assert argon2_verifies(
        (tmp_path / "secrets" / "viewer_password_hash").read_text(), viewer_password
    )
```

- [ ] **Step 7: Run them to verify they fail**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_dev_secrets.py -q`
Expected: FAIL. `3 failed`: `FileNotFoundError` from `shutil.copy2` for the missing `scripts/dev-secrets.sh`.

- [ ] **Step 8: Implement `scripts/dev-secrets.sh`**

Create `scripts/dev-secrets.sh`:

```bash
#!/usr/bin/env bash
# Writes ./secrets/* for local compose and CI e2e (C1). Never overwrites an existing file:
# delete ./secrets/ to regenerate. VIEWER_PASSWORD / ADMIN_PASSWORD are used when set, else a
# random password is generated and printed once.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p secrets
chmod 700 secrets

write_secret() { # name value
  printf '%s' "$2" >"secrets/$1"
  # 644 inside a 700 directory: containers (uid 10001) can read the bind-mounted file,
  # other local users cannot reach it.
  chmod 644 "secrets/$1"
  echo "dev-secrets: wrote secrets/$1"
}

argon2_hash() { # password on stdin -> argon2id hash (m=19456 KiB, t=2, p=1, as hashpw.py)
  uv run --quiet --no-project --with argon2-cffi python -c '
import sys
from argon2 import PasswordHasher
print(PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1).hash(sys.stdin.read()), end="")'
}

password_hash_secret() { # secret-name role password-or-empty
  local name="$1" role="$2" password="$3"
  if [[ -e "secrets/$name" ]]; then
    echo "dev-secrets: kept secrets/$name"
    return
  fi
  if [[ -z "$password" ]]; then
    password="$(openssl rand -base64 18)"
    echo "dev-secrets: generated $role password (shown once): $password"
  fi
  write_secret "$name" "$(printf '%s' "$password" | argon2_hash)"
}

password_hash_secret viewer_password_hash viewer "${VIEWER_PASSWORD:-}"
password_hash_secret admin_password_hash admin "${ADMIN_PASSWORD:-}"

if [[ -e secrets/session_secret ]]; then
  echo "dev-secrets: kept secrets/session_secret"
else
  write_secret session_secret "$(openssl rand -hex 32)"
fi

if [[ -e secrets/db_password ]]; then
  echo "dev-secrets: kept secrets/db_password"
else
  write_secret db_password "$(openssl rand -hex 32)"
fi

if [[ -e secrets/database_url ]]; then
  echo "dev-secrets: kept secrets/database_url"
else
  write_secret database_url "postgresql+psycopg://sunday:$(cat secrets/db_password)@db:5432/sunday_clays"
fi
```

Run: `chmod +x scripts/dev-secrets.sh`

- [ ] **Step 9: Run them to verify they pass**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_dev_secrets.py -q`
Expected: PASS, `3 passed`. Each run hashes with `uv run --no-project --with argon2-cffi`, so the first run downloads argon2-cffi.

- [ ] **Step 10: Write the failing e2e smoke suite**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

/**
 * E2E against the compose stack on http://localhost:8080 (compose.test.yaml in CI).
 * Both projects are Chromium: WebKit drops Secure cookies on http://localhost, so an iPhone
 * preset would break login. Only Plan 01 T4, Plan 04 T1 and Plan 08 T5a edit this file (C10).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:8080',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'mobile',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
```

Create `frontend/e2e/fixtures.ts`:

```ts
import { expect, test as base } from '@playwright/test';

/**
 * Shared `test`/`expect` for every spec (C10): a test fails if the page throws an uncaught
 * error or the browser reports a Content Security Policy violation.
 */
export const test = base.extend<{ pageProblems: string[] }>({
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

Create `frontend/e2e/smoke.spec.ts`:

```ts
import { expect, test } from './fixtures';

test('health answers through Caddy without a Server header', async ({ request }) => {
  const response = await request.get('/api/health');

  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ status: 'ok' });
  expect(response.headers()['server']).toBeUndefined();
});

test('SPA shell renders with the security headers', async ({ page }) => {
  const response = await page.goto('/');

  const headers = response?.headers() ?? {};
  expect(headers['content-security-policy']).toContain("default-src 'self'");
  expect(headers['x-content-type-options']).toBe('nosniff');
  expect(headers['referrer-policy']).toBe('same-origin');
  expect(headers['cache-control']).toBe('no-cache');
  await expect(page.getByRole('heading', { name: 'Sunday Clays' })).toBeVisible();
});

test('deep links fall back to index.html, hashed assets are immutable, missing assets 404', async ({
  page,
  request,
}) => {
  const deepLink = await request.get('/events/2026-09-13');
  expect(deepLink.status()).toBe(200);
  expect(deepLink.headers()['content-type']).toContain('text/html');
  expect(deepLink.headers()['cache-control']).toBe('no-cache');

  await page.goto('/');
  const script = await page.locator('script[type="module"]').first().getAttribute('src');
  expect(script).toMatch(/^\/assets\//);
  const asset = await request.get(script ?? '');
  expect(asset.headers()['cache-control']).toBe('public, max-age=31536000, immutable');

  // A chunk removed by a deploy must 404, never be answered with index.html cached for a year.
  const missing = await request.get('/assets/does-not-exist.js');
  expect(missing.status()).toBe(404);
  expect(missing.headers()['cache-control']).toBeUndefined();
  expect(missing.headers()['x-content-type-options']).toBe('nosniff');
  expect(missing.headers()['server']).toBeUndefined();
});

test('oversized request bodies get 413 before any route runs', async ({ request }) => {
  const upload = await request.post('/api/admin/imports', {
    data: Buffer.alloc(12 * 1024 * 1024, 1),
    headers: { 'content-type': 'application/octet-stream' },
  });
  const login = await request.post('/api/auth/login', {
    data: Buffer.alloc(300 * 1024, 1),
    headers: { 'content-type': 'application/json' },
  });

  expect(upload.status()).toBe(413);
  expect(login.status()).toBe(413);
});

test.describe('the shared fixture', () => {
  test.fail('fails a test on an uncaught page error', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      setTimeout(() => {
        throw new Error('deliberate uncaught error');
      }, 0);
    });
    await page.waitForTimeout(200);
  });

  test.fail('fails a test on a Content Security Policy violation', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => {
      const inline = document.createElement('script');
      inline.textContent = 'window.__inline = true;';
      document.head.append(inline);
    });
    await page.waitForTimeout(200);
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd frontend && pnpm exec playwright install chromium && pnpm exec playwright test`
Expected: FAIL. `8 failed`, `4 passed`: every real check fails with `connect ECONNREFUSED 127.0.0.1:8080` or `net::ERR_CONNECTION_REFUSED`, because no stack is running yet. The 4 passes are the `test.fail` fixture self-tests (2 per project), which are expected to fail.

- [ ] **Step 12: Build the backend image definition and the restore scripts**

Create `backend/Dockerfile`:

```dockerfile
# Backend image: api, worker and backup services (C1). Build context: backend/.
FROM python:3.13.15-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /bin/uv
# Use the image's interpreter (never a uv-managed one) so the venv works in the runtime stage.
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13.15-slim-trixie
# pg_dump/pg_restore/psql 17 from PGDG so the client matches the postgres:17 server.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl tzdata; \
    install -d /usr/share/postgresql-common/pgdg; \
    curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc; \
    . /etc/os-release; \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-17; \
    apt-get purge -y curl; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home app \
    && install -d -o 10001 -g 10001 -m 0750 /backups
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY backup/ ./backup/
RUN chmod 0755 /app/backup/*.sh
ARG APP_VERSION=dev
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION=$APP_VERSION
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "sunday_clays.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
```

Create `backend/.dockerignore`:

```text
tests/
.venv/
**/*.xlsx
**/__pycache__
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
coverage.xml
```

Create `backend/backup/restore.sh`:

```bash
#!/usr/bin/env bash
# Restore a custom-format dump: restore.sh <dump> [db]   (db defaults to $PGDATABASE)
# Stop `api` and `worker` first when restoring over the live database.
set -euo pipefail

dump="${1:?usage: restore.sh <dump> [db]}"
db="${2:-$PGDATABASE}"
PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
export PGPASSWORD
pg_restore --clean --if-exists --no-owner --exit-on-error --dbname="$db" "$dump"
```

Create `backend/backup/verify-restore.sh`:

```bash
#!/usr/bin/env bash
# Take a fresh verified dump, restore it into a scratch DB and compare row counts of every
# public table with the live DB (run by the CI e2e job after Playwright; C11).
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
SCRATCH_DB=sc_restore_check
HERE="$(dirname "$0")"
PGPASSWORD="$(cat "$POSTGRES_PASSWORD_FILE")"
export PGPASSWORD

drop_scratch() {
  psql --quiet -v ON_ERROR_STOP=1 -d postgres -c "DROP DATABASE IF EXISTS $SCRATCH_DB"
}

row_counts() {
  local db="$1" table
  psql -At -v ON_ERROR_STOP=1 -d "$db" -c \
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1" |
    while read -r table; do
      printf '%s %s\n' "$table" "$(psql -At -v ON_ERROR_STOP=1 -d "$db" -c "SELECT count(*) FROM public.\"$table\"")"
    done
}

"$HERE/backup.sh" --once
latest="$(ls -1 "$BACKUP_DIR"/sc-*.dump | sort | tail -n 1)"
drop_scratch
trap drop_scratch EXIT
psql --quiet -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE $SCRATCH_DB"
"$HERE/restore.sh" "$latest" "$SCRATCH_DB"
live="$(row_counts "$PGDATABASE")"
restored="$(row_counts "$SCRATCH_DB")"
if [[ "$live" != "$restored" ]]; then
  echo "verify-restore: row counts differ" >&2
  diff <(echo "$live") <(echo "$restored") >&2 || true
  exit 1
fi
echo "verify-restore: $(echo "$live" | grep -c . || true) tables match ($latest)"
```

Run: `chmod +x backend/backup/*.sh`

- [ ] **Step 13: Build the frontend image definition and the Caddyfile**

Create `frontend/Dockerfile`:

```dockerfile
# Frontend image = Caddy serving the built SPA and proxying /api (C1).
# Build context: the repo root (docker build -f frontend/Dockerfile .), for deploy/caddy/Caddyfile.
FROM node:22.23.3-trixie-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM caddy:2.11.4-alpine
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/frontend/dist /srv
```

Create `.dockerignore` at the repo root (the frontend image's build context):

```text
.git
.wt
.superpowers
secrets/
**/*.xlsx
backend/
tools/
**/node_modules
frontend/dist
frontend/coverage
frontend/src/api/schema.d.ts
openapi.json
playwright-report/
test-results/
**/playwright-report
**/test-results
```

Create `deploy/caddy/Caddyfile` (tabs, as `caddy fmt` writes them):

```caddyfile
# Sunday Clays edge inside the stack: plain :80; TLS terminates at Traefik in the Swarm.
{
	servers {
		trusted_proxies static {$TRUSTED_PROXIES:127.0.0.1/32}
		trusted_proxies_strict
	}
}

# Security headers for every response, including the error responses Caddy generates itself.
(security_headers) {
	header {
		Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
		X-Content-Type-Options nosniff
		Referrer-Policy same-origin
		Permissions-Policy "camera=(), microphone=(), geolocation=()"
		Strict-Transport-Security "max-age=31536000"
		-Server
	}
}

# C8 client-IP contract: only Caddy reads forwarding headers; the API trusts X-Real-IP alone.
(api) {
	reverse_proxy api:8000 {
		header_up X-Real-IP {client_ip}
	}
}

:80 {
	encode zstd gzip

	import security_headers

	handle /api/admin/imports {
		request_body {
			max_size 11MB
		}
		import api
	}

	handle /api/* {
		request_body {
			max_size 256KB
		}
		import api
	}

	# Hashed build output: immutable only when the file exists; a missing chunk is a plain 404.
	handle /assets/* {
		root * /srv
		@asset file
		header @asset Cache-Control "public, max-age=31536000, immutable"
		file_server
	}

	# Everything else: the file if it exists, else index.html (SPA deep links); always revalidated.
	handle {
		root * /srv
		header Cache-Control "no-cache"
		try_files {path} /index.html
		file_server
	}

	# Caddy drops the headers set above when a handler fails (404, 413), so re-apply them.
	handle_errors {
		import security_headers
	}
}
```

Run:

```bash
docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2.11.4-alpine \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | grep 'Valid configuration'
docker run --rm -e TRUSTED_PROXIES=private_ranges -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.11.4-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | grep 'Valid configuration'
docker run --rm -v "$PWD/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2.11.4-alpine \
  caddy fmt /etc/caddy/Caddyfile | diff - deploy/caddy/Caddyfile && echo formatted
```

Expected: `Valid configuration` twice, then `formatted`. (`grep`, not `tail -1`: Caddy's shutdown log lines on stderr can land after the verdict.) The Step 10 smoke test (run in Step 16) pins the caching rules: `try_files` takes no matcher (a `@name` there is read as a literal file name), so `/assets/*` has its own `handle` in which only an existing file (`@asset file`) is marked immutable, and a missing chunk is a 404 that still carries the security headers through `handle_errors`.

- [ ] **Step 14: Build both images and smoke-test the backend image**

Run:

```bash
docker build -t ghcr.io/gitgat/sunday-clays-backend:ci backend
docker build -f frontend/Dockerfile -t ghcr.io/gitgat/sunday-clays-frontend:ci .
docker run --rm ghcr.io/gitgat/sunday-clays-backend:ci alembic --help | head -1
docker run --rm ghcr.io/gitgat/sunday-clays-backend:ci sh -c 'id -u && pg_dump --version && ls /app/backup'
```

Expected: both builds succeed. Then `usage: alembic [-h] …`, `10001`, `pg_dump (PostgreSQL) 17.…`, and `backup.sh backup_tools.py restore.sh verify-restore.sh`.

- [ ] **Step 15: Write the compose files**

Create `compose.yaml`:

```yaml
# Production-shaped stack (Swarm-ready): no published ports, no external networks, no host
# binds; configuration only via env vars and *_FILE secrets. Local: compose.override.yaml.
# CI e2e: -f compose.yaml -f compose.test.yaml. Swarm: -c compose.yaml -c compose.swarm.yaml.

x-backend-secrets-env: &backend-secrets-env
  DATABASE_URL_FILE: /run/secrets/database_url
  SESSION_SECRET_FILE: /run/secrets/session_secret
  VIEWER_PASSWORD_HASH_FILE: /run/secrets/viewer_password_hash
  ADMIN_PASSWORD_HASH_FILE: /run/secrets/admin_password_hash

services:
  caddy:
    image: ghcr.io/gitgat/sunday-clays-frontend:${IMAGE_TAG:-latest}
    build:
      context: .
      dockerfile: frontend/Dockerfile
    depends_on: [api]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s

  api:
    image: ghcr.io/gitgat/sunday-clays-backend:${IMAGE_TAG:-latest}
    build:
      context: backend
    command:
      - sh
      - -c
      - alembic upgrade head && exec uvicorn sunday_clays.api.app:create_app --factory --host 0.0.0.0 --port 8000 --no-proxy-headers
    environment: *backend-secrets-env
    secrets: [database_url, session_secret, viewer_password_hash, admin_password_hash]
    depends_on: [db]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 60s

  worker:
    image: ghcr.io/gitgat/sunday-clays-backend:${IMAGE_TAG:-latest}
    build:
      context: backend
    command: ["python", "-m", "sunday_clays.jobs.worker"]
    environment: *backend-secrets-env
    secrets: [database_url, session_secret, viewer_password_hash, admin_password_hash]
    depends_on: [db]
    restart: unless-stopped
    stop_grace_period: 5m
    deploy:
      replicas: 1
      update_config:
        order: stop-first
    healthcheck:
      test: ["CMD", "python", "-c", "import os,time,sys; sys.exit(time.time()-os.path.getmtime('/tmp/worker-heartbeat')>60)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s

  db:
    image: postgres:17
    environment:
      POSTGRES_USER: sunday
      POSTGRES_DB: sunday_clays
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5

  backup:
    image: ghcr.io/gitgat/sunday-clays-backend:${IMAGE_TAG:-latest}
    build:
      context: backend
    command: ["/app/backup/backup.sh"]
    environment:
      PGHOST: db
      PGUSER: sunday
      PGDATABASE: sunday_clays
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets: [db_password]
    volumes:
      - backups:/backups
    depends_on: [db]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import os,time,sys; sys.exit(time.time()-os.path.getmtime('/backups/last_success')>93600)"]
      interval: 60s
      timeout: 5s
      retries: 3
      start_period: 120s

volumes:
  db-data:
  backups:

secrets:
  session_secret:
    file: ./secrets/session_secret
  viewer_password_hash:
    file: ./secrets/viewer_password_hash
  admin_password_hash:
    file: ./secrets/admin_password_hash
  db_password:
    file: ./secrets/db_password
  database_url:
    file: ./secrets/database_url
```

Create `compose.override.yaml`:

```yaml
# Local development (auto-loaded by `docker compose up`): http://localhost:8080.
services:
  caddy:
    ports:
      - "8080:80"
    depends_on:
      api:
        condition: service_healthy
  api:
    environment:
      COOKIE_SECURE: "false"
    depends_on:
      db:
        condition: service_healthy
  worker:
    depends_on:
      db:
        condition: service_healthy
  backup:
    depends_on:
      db:
        condition: service_healthy
```

Create `compose.test.yaml`:

```yaml
# CI e2e: IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
# Images come from `docker load` (pull_policy: never; Compose would re-pull otherwise).
services:
  caddy:
    pull_policy: never
    ports:
      - "8080:80"
    depends_on:
      api:
        condition: service_healthy
  api:
    pull_policy: never
    environment:
      COOKIE_SECURE: "false"
      WEATHER_ENABLED: "false"
      # Every e2e login comes from one IP: the default 10 failures / 15 min would turn a re-run
      # against a long-lived stack into 429s. Backend unit tests cover the limiter itself.
      LOGIN_MAX_FAILURES: "1000"
    depends_on:
      db:
        condition: service_healthy
  worker:
    pull_policy: never
    environment:
      WEATHER_ENABLED: "false"
    depends_on:
      db:
        condition: service_healthy
  backup:
    pull_policy: never
    depends_on:
      db:
        condition: service_healthy
```

Create `compose.swarm.yaml`:

```yaml
# Swarm overlay: IMAGE_TAG=sha-<7> docker stack deploy --with-registry-auth \
#   -c compose.yaml -c compose.swarm.yaml sundayclays        (runbook: deploy/README.md)
x-arch: &amd64-only
  constraints:
    - node.platform.arch==x86_64

x-db-node: &db-node
  constraints:
    - node.platform.arch==x86_64
    - node.hostname==${SC_DB_NODE:-autopirate}

services:
  caddy:
    image: ghcr.io/gitgat/sunday-clays-frontend:${IMAGE_TAG:?IMAGE_TAG is required}
    environment:
      TRUSTED_PROXIES: private_ranges
    networks: [default, traefik_public]
    deploy:
      placement: *amd64-only
      restart_policy:
        condition: on-failure
      labels:
        - traefik.enable=true
        - traefik.swarm.network=traefik_public
        - traefik.http.routers.sundayclays.rule=Host(`sundayclays.claysmasher.com`)
        - traefik.http.routers.sundayclays.entrypoints=websecure
        - traefik.http.routers.sundayclays.tls=true
        - traefik.http.routers.sundayclays.tls.certresolver=cloudflare
        - traefik.http.services.sundayclays.loadbalancer.server.port=80

  api:
    image: ghcr.io/gitgat/sunday-clays-backend:${IMAGE_TAG:?IMAGE_TAG is required}
    deploy:
      placement: *amd64-only
      restart_policy:
        condition: on-failure

  worker:
    image: ghcr.io/gitgat/sunday-clays-backend:${IMAGE_TAG:?IMAGE_TAG is required}
    deploy:
      replicas: 1
      update_config:
        order: stop-first
      placement: *amd64-only
      # `any`, not on-failure: SIGTERM (e.g. an unhealthy task) makes the worker finish its job
      # and exit 0, and a long-running service must never stay stopped after a clean exit.
      restart_policy:
        condition: any

  db:
    volumes:
      - /var/data/sundayclays/db:/var/lib/postgresql/data
    deploy:
      replicas: 1
      update_config:
        order: stop-first
      placement: *db-node
      restart_policy:
        condition: on-failure

  backup:
    image: ghcr.io/gitgat/sunday-clays-backend:${IMAGE_TAG:?IMAGE_TAG is required}
    environment:
      BACKUP_HC_URL_FILE: /run/secrets/backup_hc_url
    secrets: [db_password, backup_hc_url]
    volumes:
      - /var/data/sundayclays/backups:/backups
    deploy:
      replicas: 1
      update_config:
        order: stop-first
      placement: *db-node
      restart_policy:
        condition: on-failure

networks:
  traefik_public:
    external: true

# Restated in full: `docker stack` replaces top-level secret entries rather than merging them.
# Swarm secrets are immutable: rotate = new file content + bump SECRETS_REV + redeploy.
secrets:
  session_secret:
    file: ./secrets/session_secret
    name: sundayclays_session_secret_v${SECRETS_REV:-1}
  viewer_password_hash:
    file: ./secrets/viewer_password_hash
    name: sundayclays_viewer_password_hash_v${SECRETS_REV:-1}
  admin_password_hash:
    file: ./secrets/admin_password_hash
    name: sundayclays_admin_password_hash_v${SECRETS_REV:-1}
  db_password:
    file: ./secrets/db_password
    name: sundayclays_db_password_v${SECRETS_REV:-1}
  database_url:
    file: ./secrets/database_url
    name: sundayclays_database_url_v${SECRETS_REV:-1}
  backup_hc_url:
    file: ./secrets/backup_hc_url
    name: sundayclays_backup_hc_url_v${SECRETS_REV:-1}
```

Run:

```bash
docker compose config -q && echo local-ok
IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml config -q && echo test-ok
IMAGE_TAG=sha-0000000 docker stack config -c compose.yaml -c compose.swarm.yaml | grep -E 'image:|name: sundayclays_|node\.hostname'
docker stack config -c compose.yaml -c compose.swarm.yaml > /dev/null; echo "without IMAGE_TAG: exit $?"
```

Expected: `local-ok`, `test-ok`. Then four `image: ghcr.io/gitgat/sunday-clays-*:sha-0000000` lines plus `image: postgres:17`, two `node.hostname==autopirate` lines, six `name: sundayclays_…_v1` lines, and finally `required variable IMAGE_TAG is missing a value: IMAGE_TAG is required` with `exit 1`. `docker stack config` is client-only; no swarm is needed.

- [ ] **Step 16: Run the stack, the smoke suite and the restore check (master §0 step 4a, T4)**

Run (repo root):

```bash
rm -rf secrets
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
(cd frontend && pnpm exec playwright test)
docker compose -f compose.yaml -f compose.test.yaml exec -T backup /app/backup/verify-restore.sh
docker compose -f compose.yaml -f compose.test.yaml down -v
```

Expected: five `dev-secrets: wrote secrets/…` lines. All five containers `Healthy`. Playwright `12 passed`; the two `the shared fixture` tests per project show as expected failures. Then `verify-restore: 1 tables match (/backups/sc-<UTC>.dump)`: only `alembic_version` exists until Plan 03 T1. Finally the containers, volumes and network are removed. Paste this output into the PR body (master §0 step 4a).

- [ ] **Step 17: Check the local-development path**

Run:

```bash
docker compose up -d --build --wait && curl -fsS http://localhost:8080/api/health && echo \
  && docker compose exec -T api python -c "import os; print(os.environ['COOKIE_SECURE'])" \
  && docker compose down -v
```

Expected: `{"status":"ok","version":"dev"}`, then `false` (compose.override.yaml is loaded automatically and publishes `8080:80`).

- [ ] **Step 18: Write the Swarm runbook**

Create `deploy/README.md`:

````markdown
# Deploying Sunday Clays to the Swarm

Stack `sundayclays`, public at https://sundayclays.claysmasher.com. TLS terminates at the existing
Traefik (`traefik_public` network, `websecure` entrypoint, `cloudflare` certresolver); Caddy serves the
SPA and proxies `/api` on plain `:80` inside the stack. `api`, `worker`, `db` and `backup` publish no
ports and never join `traefik_public`.

## Preconditions (not built by this repo)

- Traefik publishes 80/443 with `mode: host` and has no `forwardedHeaders.trustedIPs` on `websecure`,
  so the client IP it forwards is the real one (verified in `swarm-config/traefik-v3`). Caddy trusts
  forwarding headers only from private ranges (`TRUSTED_PROXIES=private_ranges` in
  `compose.swarm.yaml`) and always overwrites `X-Real-IP`, which is the only client-IP header the API
  reads.
- If this host ever moves behind Cloudflare's proxy or the cloudflared → traefik-public edge, add
  Cloudflare's IP ranges to `TRUSTED_PROXIES` and add `client_ip_headers CF-Connecting-IP` to the
  `servers` block of `deploy/caddy/Caddyfile`. Never publish Caddy ports with `mode: host`.
- Images are published to GHCR by the CI `publish` job only from CI-green `main` commits. Set the
  repository variable `PUBLISH_ON_PUSH=true` before the first deploy, or run the `ci` workflow on
  `main` with "Run workflow" (workflow_dispatch). Tags are `sha-<7>` and `latest`; deploy `sha-<7>`.

## One-time setup (on a manager node)

1. Log in to GHCR with a classic personal access token scoped `read:packages`:

   ```bash
   echo "$GHCR_PAT" | docker login ghcr.io -u <github-user> --password-stdin
   ```

2. Check out this repository (for `compose.yaml` and `compose.swarm.yaml`) and create `./secrets/`
   next to them. `scripts/dev-secrets.sh` needs `uv` and `openssl`; give it the real passwords. (Once
   Plan 04 has landed you can instead write the two hashes with
   `docker run --rm -it ghcr.io/gitgat/sunday-clays-backend:sha-<7> python -m sunday_clays.auth.hashpw`.)

   ```bash
   VIEWER_PASSWORD='<viewer password>' ADMIN_PASSWORD='<admin password>' scripts/dev-secrets.sh
   printf '%s' 'https://hc-ping.com/<check-uuid>' > secrets/backup_hc_url
   chmod 600 secrets/*
   ```

   `secrets/backup_hc_url` holds the Healthchecks.io ping URL of the nightly-backup check (create
   the check first: period 1 day, grace 2 hours). An empty file disables the ping.

3. On the database node (`autopirate`; override with `SC_DB_NODE=<hostname>` at deploy time) create
   the data directories with the owners the containers run as:

   ```bash
   sudo install -d -o 999 -g 999 /var/data/sundayclays/db        # postgres:17 (Debian) uid
   sudo install -d -o 10001 -g 10001 /var/data/sundayclays/backups   # backend image uid
   ```

4. Off-site copies: add `/var/data/sundayclays/*` to the fleet restic set (nightly at 03:30 to
   lakitu, then Backblaze). The app's own dump runs at 02:30 America/Los_Angeles, before restic.

## Deploy or upgrade

```bash
IMAGE_TAG=sha-<7> docker stack deploy --with-registry-auth -c compose.yaml -c compose.swarm.yaml sundayclays
curl -fsS https://sundayclays.claysmasher.com/api/health   # {"status":"ok","version":"sha-<7>"}
```

- `api` runs `alembic upgrade head` before uvicorn; migrations are expand/contract compatible with
  the previous release, so the old and new api may overlap during an update.
- `worker`, `db` and `backup` update stop-first with one replica each; the worker gets 5 minutes to
  finish its current job.
- `IMAGE_TAG` is required (`${IMAGE_TAG:?…}`); `latest` is never deployed.

## Rotating a secret

Swarm secrets are immutable, so a rotation creates a new version:

```bash
# 1. put the new value in ./secrets/<name>  2. bump SECRETS_REV and redeploy
SECRETS_REV=2 IMAGE_TAG=sha-<7> docker stack deploy --with-registry-auth -c compose.yaml -c compose.swarm.yaml sundayclays
# 3. once the services are healthy, remove the old version
docker secret rm sundayclays_<name>_v1
```

- A `db_password` change also needs `ALTER ROLE sunday PASSWORD '<new>';` (Postgres reads
  `POSTGRES_PASSWORD_FILE` only when it initialises an empty data directory) and a matching
  `database_url` in the same revision.
- Rotating `viewer_password_hash` or `admin_password_hash` signs out that role only; rotating
  `session_secret` signs out everyone.

## Backups and restore

- The `backup` service writes a verified custom-format dump at container start and daily at 02:30
  America/Los_Angeles to `/var/data/sundayclays/backups` (`sc-<UTC>.dump`), keeps the newest dump per
  day for 14 days and per ISO week for 8 weeks (pruned by date), touches `last_success` and pings
  Healthchecks (`/fail` on error).
- Check that the newest data restores cleanly, without touching live data:

  ```bash
  docker exec "$(docker ps -q -f name=sundayclays_backup)" /app/backup/verify-restore.sh
  ```

- Restore a dump over the live database (stop the writers first):

  ```bash
  docker service scale sundayclays_api=0 sundayclays_worker=0
  docker exec -it "$(docker ps -q -f name=sundayclays_backup)" /app/backup/restore.sh /backups/sc-<stamp>.dump
  docker service scale sundayclays_api=1 sundayclays_worker=1
  ```

  `restore.sh <dump> [db]` runs `pg_restore --clean --if-exists --no-owner --exit-on-error`.
````

- [ ] **Step 19: Regression run of everything this task touches**

Run:

```bash
(cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest -q)
uv run --no-project --with pytest --with pyyaml pytest scripts/tests -q
(cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test)
```

Expected: `All checks passed!`, `… files already formatted`, `81 passed` (Task 1's 69 + 12 backup tests: 7 backup-tools, 5 backup.sh); then `20 passed` (Task 3's 17 + these 3; Task 3 merged in an earlier wave); then eslint and tsc with no findings (they now cover `e2e/` and `playwright.config.ts`), Prettier clean, and `Tests  9 passed (9)`.

- [ ] **Step 20: Commit**

```bash
git add .gitignore .dockerignore compose.yaml compose.override.yaml compose.test.yaml compose.swarm.yaml \
  deploy backend/Dockerfile backend/.dockerignore backend/backup backend/tests/unit/backup \
  scripts/dev-secrets.sh scripts/tests/test_dev_secrets.py \
  frontend/Dockerfile frontend/playwright.config.ts frontend/e2e/fixtures.ts frontend/e2e/smoke.spec.ts
git commit -F - <<'EOF'
feat(deploy): add images, Caddy, compose stack, backups and Playwright smoke

Backend (api/worker/backup, uid 10001, pg_dump 17) and Caddy+SPA images; a Caddyfile with CSP
and security headers, body limits, X-Real-IP and SPA fallback; Swarm-ready compose.yaml with
local, CI-test and Swarm overlays; verified nightly backups with date-based retention and a
restore check; dev secrets; the Swarm runbook; Playwright desktop/mobile smoke tests with a
shared fixture that fails on page errors and CSP violations.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 5: CI workflows, Swarm stack check, git hooks, branch protection and CONTRIBUTING (master Plan 01 T5)

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `.github/dependabot.yml`
- Create: `scripts/check_stack.py`, `scripts/setup-branch-protection.sh`
- Create: `lefthook.yml`, `CONTRIBUTING.md`
- Test: `scripts/tests/test_ci_config.py`, `scripts/tests/test_check_stack.py`, `scripts/tests/test_setup_branch_protection.py`
- May modify (only to get this PR's first CI run green; master §0 step 4a): any Task 1–4 file **except** `ratchets/`

**Interfaces:**
- Consumes: Task 3: `python3 scripts/ratchet.py check`, `python3 scripts/bundle_stats.py --dist frontend/dist --out bundle-stats.json`, the `artifacts/<name>/` layout. Task 4: `compose.yaml` + `compose.test.yaml` + `compose.swarm.yaml`, both Dockerfiles, `scripts/dev-secrets.sh`, `/app/backup/verify-restore.sh`, the Playwright config and specs. Task 1: `uv run pytest --cov --cov-branch`, `python -m sunday_clays.api.export_openapi`. Task 2: `pnpm lint|typecheck|test|build|gen:api`, `.nvmrc`.
- Produces:
  - `.github/workflows/ci.yml` jobs `backend`, `frontend`, `ratchet`, `docker`, `stack-config`, `e2e`, `ci-ok` (the only required check) and `publish`. Artifacts: `backend-coverage`, `frontend-coverage`, `bundle-stats`, `backend-image`, `frontend-image`, `playwright-report` (the last on failure only). Plan 10 T5 adds a `tools` job and must add it to `ci-ok.needs` in the same PR.
  - `.github/workflows/publish.yml` (`on: workflow_call`): pushes `ghcr.io/gitgat/sunday-clays-{backend,frontend}:sha-<7>` and `:latest`.
  - `scripts/check_stack.py [rendered.yaml]` (reads stdin by default): `violations(stack: dict[str, Any]) -> list[str]`; exit 0 ok, 1 on violations, 2 on non-mapping input.
  - `scripts/setup-branch-protection.sh` (master §0 step 6).
  - `lefthook.yml`, `CONTRIBUTING.md` (the workflow every later task follows).

**Branch:** `task/01-5-ci`

**Depends on:** T3, T4

**Before you start:**
- Tasks 1–4 are merged. Nothing else runs concurrently with this task (master §0 step 4a).
- Docker is running (actionlint and `docker stack config` run through it). `lefthook` 2.x is installed (`brew install lefthook`). `git` is on `PATH` (the ratchet-guard test builds throwaway repos). You need no GitHub access: this task ends at its commit (Step 16), and the controller pushes, opens the PR and runs the `ci-ok` canary.
- Work at the repo root.

- [ ] **Step 1: Write the failing CI-shape test**

Create `scripts/tests/test_ci_config.py`:

```python
"""Durable guard on the shape of the CI workflows (C11); PyYAML reads the `on:` key as True."""

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
SHA_PIN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
GIT_ENV = {
    "PATH": os.environ["PATH"],
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "ci-config test",
    "GIT_AUTHOR_EMAIL": "ci-config@example.invalid",
    "GIT_COMMITTER_NAME": "ci-config test",
    "GIT_COMMITTER_EMAIL": "ci-config@example.invalid",
}


def load(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


CI = load("ci.yml")
JOBS: dict[str, dict[str, Any]] = CI["jobs"]


def all_steps(workflow: dict[Any, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def test_ci_ok_always_runs_and_needs_every_other_job() -> None:
    assert "always()" in JOBS["ci-ok"]["if"]
    assert set(JOBS["ci-ok"]["needs"]) == set(JOBS) - {"ci-ok", "publish"}


def test_ci_ok_fails_on_failure_cancellation_or_skip() -> None:
    conditions = " ".join(str(step.get("if", "")) for step in JOBS["ci-ok"]["steps"])
    for result in ("failure", "cancelled", "skipped"):
        assert f"contains(needs.*.result, '{result}')" in conditions


def test_publish_runs_only_after_ci_ok() -> None:
    needs = JOBS["publish"]["needs"]
    assert needs == "ci-ok" or needs == ["ci-ok"]
    assert JOBS["publish"]["uses"] == "./.github/workflows/publish.yml"


def test_no_other_job_can_be_skipped_by_a_job_level_if() -> None:
    conditional = {name for name, job in JOBS.items() if "if" in job}
    assert conditional <= {"ci-ok", "publish"}


def test_triggers_run_every_pull_request_and_no_merge_queue() -> None:
    on = CI[True]
    assert "merge_group" not in on
    pull_request = on["pull_request"] or {}
    for key in ("branches", "branches-ignore", "paths", "paths-ignore"):
        assert key not in pull_request
    assert on["push"] == {"branches": ["main"]}
    assert "workflow_dispatch" in on


def test_top_level_permissions_are_read_only() -> None:
    assert CI["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("workflow", ["ci.yml", "publish.yml"])
def test_checkouts_do_not_persist_credentials(workflow: str) -> None:
    checkouts = [
        s
        for s in all_steps(load(workflow))
        if str(s.get("uses", "")).startswith("actions/checkout@")
    ]
    assert checkouts
    for step in checkouts:
        assert step["with"]["persist-credentials"] is False


@pytest.mark.parametrize("workflow", ["ci.yml", "publish.yml"])
def test_third_party_actions_are_pinned_to_full_shas(workflow: str) -> None:
    for step in all_steps(load(workflow)):
        uses = str(step.get("uses", ""))
        if uses and not uses.startswith(("actions/", "./")):
            assert SHA_PIN.match(uses), uses


def test_dependabot_updates_actions_uv_and_npm_monthly() -> None:
    config = yaml.safe_load((WORKFLOWS.parent / "dependabot.yml").read_text(encoding="utf-8"))
    updates = {(u["package-ecosystem"], u["directory"]): u for u in config["updates"]}

    assert set(updates) == {("github-actions", "/"), ("uv", "/backend"), ("npm", "/frontend")}
    assert {u["schedule"]["interval"] for u in updates.values()} == {"monthly"}


def ratchet_guard() -> dict[str, Any]:
    guards = [s for s in JOBS["ratchet"]["steps"] if "-- ratchets/" in str(s.get("run", ""))]
    assert len(guards) == 1
    return guards[0]


def test_ratchet_guard_runs_on_pull_requests_after_a_full_history_checkout() -> None:
    steps = JOBS["ratchet"]["steps"]
    guard = ratchet_guard()
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout@"))

    assert guard["if"] == "github.event_name == 'pull_request'"
    assert checkout["with"]["fetch-depth"] == 0
    assert steps.index(checkout) < steps.index(guard)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=GIT_ENV, check=True, capture_output=True)


def pull_request_checkout(root: Path, changed: str) -> Path:
    """A full-history PR checkout: origin/main is the base commit; HEAD also changes ``changed``."""
    repo = root / "repo"
    (repo / "ratchets").mkdir(parents=True)
    (repo / "ratchets" / "baseline.json").write_text('{"backend_lines": 90.0}\n')
    (repo / "README.md").write_text("base\n")
    git(repo, "init", "--quiet")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "base")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    (repo / changed).write_text("changed\n")
    git(repo, "commit", "--quiet", "-am", "pull request")
    return repo


@pytest.mark.parametrize(
    ("head_ref", "changed", "returncode"),
    [
        ("task/01-5-ci", "ratchets/baseline.json", 1),
        ("chore/deps-openpyxl", "ratchets/baseline.json", 1),
        ("chore/ratchet-wave-1", "ratchets/baseline.json", 0),
        ("task/01-5-ci", "README.md", 0),
    ],
)
def test_ratchet_guard_blocks_ratchets_changes_outside_chore_branches(
    tmp_path: Path, head_ref: str, changed: str, returncode: int
) -> None:
    repo = pull_request_checkout(tmp_path, changed)

    result = subprocess.run(  # the runner's default `run` shell: bash -eo pipefail
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", ratchet_guard()["run"]],
        cwd=repo,
        env={**GIT_ENV, "BASE_REF": "main", "HEAD_REF": head_ref},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == returncode, result.stdout + result.stderr
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_ci_config.py -q`
Expected: FAIL. `1 error during collection`: `FileNotFoundError: … .github/workflows/ci.yml`.

- [ ] **Step 3: Write the workflows and the Dependabot config**

Create `.github/workflows/ci.yml`. Every action is pinned to the full commit SHA of the release named in its comment:

```yaml
# CI (C11). `ci-ok` is the only required check; it fails when any other job fails, is
# cancelled or is skipped. No job except `publish` may carry a job-level `if:`
# (scripts/tests/test_ci_config.py enforces the shape of this file).
name: ci

on:
  pull_request:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.head_ref || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

env:
  UV_VERSION: "0.9.9"
  PYTHON_VERSION: "3.13"

jobs:
  backend:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: sunday_clays_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 20
    env:
      TEST_DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/sunday_clays_test
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ env.PYTHON_VERSION }}
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy --strict src
      - run: uv run pytest --cov --cov-branch --cov-report=term --cov-report=xml
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: backend-coverage
          path: backend/coverage.xml
          if-no-files-found: error

  frontend:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ env.PYTHON_VERSION }}
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - run: uv sync --project backend --frozen
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          package-manager-cache: false
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
        with:
          package_json_file: frontend/package.json
          cache: true
          cache_dependency_path: frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
        working-directory: frontend
      - run: pnpm gen:api
        working-directory: frontend
      - run: pnpm lint
        working-directory: frontend
      - run: pnpm typecheck
        working-directory: frontend
      - run: pnpm exec prettier --check .
        working-directory: frontend
      - run: pnpm test --coverage
        working-directory: frontend
      - run: pnpm build
        working-directory: frontend
      - run: python3 scripts/bundle_stats.py --dist frontend/dist --out bundle-stats.json
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: frontend-coverage
          path: frontend/coverage/coverage-summary.json
          if-no-files-found: error
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: bundle-stats
          path: bundle-stats.json
          if-no-files-found: error

  ratchet:
    needs: [backend, frontend]
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 0
      - name: ratchets/ may change only in chore/ratchet-* PRs
        if: github.event_name == 'pull_request'
        env:
          BASE_REF: ${{ github.base_ref }}
          HEAD_REF: ${{ github.head_ref }}
        run: |
          if ! git diff --quiet "origin/${BASE_REF}...HEAD" -- ratchets/ && [[ "${HEAD_REF}" != chore/ratchet-* ]]; then
            echo "::error::ratchets/ changed outside a chore/ratchet-* branch (${HEAD_REF})"
            exit 1
          fi
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ env.PYTHON_VERSION }}
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: backend-coverage
          path: artifacts/backend-coverage
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: frontend-coverage
          path: artifacts/frontend-coverage
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: bundle-stats
          path: artifacts/bundle-stats
      - run: uv run --no-project --with pytest --with pyyaml pytest scripts/tests
      - run: python3 scripts/ratchet.py check

  docker:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1
      - uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
        with:
          context: backend
          platforms: linux/amd64
          tags: ghcr.io/gitgat/sunday-clays-backend:ci
          cache-from: type=gha,scope=backend
          cache-to: type=gha,mode=max,scope=backend
          outputs: type=docker,dest=/tmp/backend.tar
      - uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
        with:
          context: .
          file: frontend/Dockerfile
          platforms: linux/amd64
          tags: ghcr.io/gitgat/sunday-clays-frontend:ci
          cache-from: type=gha,scope=frontend
          cache-to: type=gha,mode=max,scope=frontend
          outputs: type=docker,dest=/tmp/frontend.tar
      - name: Smoke-test the backend image
        run: |
          docker load --input /tmp/backend.tar
          docker run --rm ghcr.io/gitgat/sunday-clays-backend:ci alembic --help
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: backend-image
          path: /tmp/backend.tar
          retention-days: 1
          compression-level: 1
          if-no-files-found: error
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: frontend-image
          path: /tmp/frontend.tar
          retention-days: 1
          compression-level: 1
          if-no-files-found: error

  stack-config:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Swarm stack renders and satisfies the fleet rules
        run: |
          IMAGE_TAG=sha-0000000 docker stack config -c compose.yaml -c compose.swarm.yaml \
            | uv run --no-project --with pyyaml python scripts/check_stack.py

  e2e:
    needs: [docker]
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: backend-image
          path: /tmp/images
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: frontend-image
          path: /tmp/images
      - run: |
          docker load --input /tmp/images/backend.tar
          docker load --input /tmp/images/frontend.tar
      - uses: astral-sh/setup-uv@c18668ad3cf93ea998bef934396af7bb5c839dc7 # v10.2.0
        with:
          version: ${{ env.UV_VERSION }}
          python-version: ${{ env.PYTHON_VERSION }}
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          package-manager-cache: false
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
        with:
          package_json_file: frontend/package.json
          cache: true
          cache_dependency_path: frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
        working-directory: frontend
      - uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ runner.os }}-${{ hashFiles('frontend/pnpm-lock.yaml') }}
      - run: pnpm exec playwright install --with-deps chromium
        working-directory: frontend
      - run: VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
      - run: IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
      - run: pnpm exec playwright test
        working-directory: frontend
        env:
          CI: "true"
          E2E_VIEWER_PASSWORD: e2e-viewer
          E2E_ADMIN_PASSWORD: e2e-admin
      - name: Backup restore verification
        run: docker compose -f compose.yaml -f compose.test.yaml exec -T backup /app/backup/verify-restore.sh
      - name: Compose logs
        if: failure()
        run: docker compose -f compose.yaml -f compose.test.yaml logs --no-color
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        if: failure()
        with:
          name: playwright-report
          path: frontend/playwright-report
          retention-days: 7
      - name: Stop the stack
        if: always()
        run: docker compose -f compose.yaml -f compose.test.yaml down -v

  ci-ok:
    if: always()
    needs: [backend, frontend, ratchet, docker, stack-config, e2e]
    runs-on: ubuntu-24.04
    steps:
      - name: Every CI job succeeded
        if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'skipped')
        run: exit 1

  publish:
    needs: ci-ok
    if: github.ref == 'refs/heads/main' && (github.event_name == 'workflow_dispatch' || (github.event_name == 'push' && vars.PUBLISH_ON_PUSH == 'true'))
    permissions:
      contents: read
      packages: write
    uses: ./.github/workflows/publish.yml
```

Create `.github/workflows/publish.yml`:

```yaml
# Push the CI-tested images to GHCR as sha-<7> and latest (C11). Called only by ci.yml's
# `publish` job, after `ci-ok`, on main. Reuses the buildx GHA cache the `docker` job wrote.
name: publish

on:
  workflow_call:

permissions:
  contents: read
  packages: write

jobs:
  images:
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - id: tag
        run: echo "tag=sha-${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"
      - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1
      - uses: docker/login-action@dbcb813823bdd20940b903addbd779551569679f # v4.6.0
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
        with:
          context: backend
          platforms: linux/amd64
          push: true
          build-args: APP_VERSION=${{ steps.tag.outputs.tag }}
          tags: |
            ghcr.io/gitgat/sunday-clays-backend:${{ steps.tag.outputs.tag }}
            ghcr.io/gitgat/sunday-clays-backend:latest
          labels: org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
          cache-from: type=gha,scope=backend
          cache-to: type=gha,mode=max,scope=backend
      - uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
        with:
          context: .
          file: frontend/Dockerfile
          platforms: linux/amd64
          push: true
          tags: |
            ghcr.io/gitgat/sunday-clays-frontend:${{ steps.tag.outputs.tag }}
            ghcr.io/gitgat/sunday-clays-frontend:latest
          labels: org.opencontainers.image.source=${{ github.server_url }}/${{ github.repository }}
          cache-from: type=gha,scope=frontend
          cache-to: type=gha,mode=max,scope=frontend
```

Create `.github/dependabot.yml`:

```yaml
# Monthly, grouped version updates (C11). Lockfile changes land as controller-reviewed PRs.
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: monthly
    groups:
      github-actions:
        patterns: ["*"]
  - package-ecosystem: uv
    directory: /backend
    schedule:
      interval: monthly
    groups:
      backend:
        patterns: ["*"]
  - package-ecosystem: npm
    directory: /frontend
    schedule:
      interval: monthly
    groups:
      frontend:
        patterns: ["*"]
```

- [ ] **Step 4: Run the shape test and actionlint**

Run:

```bash
uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_ci_config.py -q
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12 -color && echo actionlint-ok
```

Expected: PASS, `16 passed` (the ratchet-guard test runs the guard's own shell against four throwaway git checkouts), then `actionlint-ok` with no findings.

- [ ] **Step 5: Write the failing stack-check tests**

Create `scripts/tests/test_check_stack.py`:

```python
import copy
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "check_stack.py"
ARCH = ["node.platform.arch==x86_64"]
DB_NODE = ["node.platform.arch==x86_64", "node.hostname==autopirate"]


def backend(**extra: Any) -> dict[str, Any]:
    return {
        "image": "ghcr.io/gitgat/sunday-clays-backend:sha-0000000",
        "deploy": {"placement": {"constraints": list(ARCH)}},
        **extra,
    }


VALID: dict[str, Any] = {
    "services": {
        "caddy": {
            "image": "ghcr.io/gitgat/sunday-clays-frontend:sha-0000000",
            "deploy": {"placement": {"constraints": list(ARCH)}},
        },
        "api": backend(),
        "worker": backend(),
        "db": {
            "image": "postgres:17",
            "deploy": {"replicas": 1, "placement": {"constraints": list(DB_NODE)}},
            "volumes": [
                {
                    "type": "bind",
                    "source": "/var/data/sundayclays/db",
                    "target": "/var/lib/postgresql/data",
                }
            ],
        },
        "backup": backend(
            deploy={"replicas": 1, "placement": {"constraints": list(DB_NODE)}},
            volumes=[
                {"type": "bind", "source": "/var/data/sundayclays/backups", "target": "/backups"}
            ],
        ),
    },
    "secrets": {
        "db_password": {"name": "sundayclays_db_password_v1", "file": "/x/secrets/db_password"},
    },
}


def run(stack: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=yaml.safe_dump(stack),
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_stack_passes() -> None:
    result = run(VALID)

    assert result.returncode == 0, result.stderr
    assert "5 services ok" in result.stdout


def drop_arch(stack: dict[str, Any]) -> None:
    stack["services"]["worker"]["deploy"]["placement"]["constraints"] = []


def drop_hostname(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["deploy"]["placement"]["constraints"] = list(ARCH)


def two_replicas(stack: dict[str, Any]) -> None:
    stack["services"]["backup"]["deploy"]["replicas"] = 2


def named_volume(stack: dict[str, Any]) -> None:
    stack["services"]["db"]["volumes"] = [
        {"type": "volume", "source": "db-data", "target": "/var/lib/postgresql/data"}
    ]


def unprefixed_secret(stack: dict[str, Any]) -> None:
    stack["secrets"]["db_password"]["name"] = "db_password"


def caddy_ports(stack: dict[str, Any]) -> None:
    stack["services"]["caddy"]["ports"] = [{"target": 80, "published": 443, "mode": "host"}]


def latest_image(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["image"] = "ghcr.io/gitgat/sunday-clays-backend:latest"


def untagged_image(stack: dict[str, Any]) -> None:
    stack["services"]["api"]["image"] = "ghcr.io/gitgat/sunday-clays-backend"


def missing_backup(stack: dict[str, Any]) -> None:
    del stack["services"]["backup"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (drop_arch, "worker: missing placement constraint node.platform.arch==x86_64"),
        (drop_hostname, "db: missing node.hostname== placement constraint"),
        (two_replicas, "backup: deploy.replicas must be 1"),
        (named_volume, "db: needs a bind mount under /var/data/sundayclays/"),
        (unprefixed_secret, "secret db_password: name 'db_password' must start with sundayclays_"),
        (caddy_ports, "caddy: must not publish ports"),
        (latest_image, "api: image 'ghcr.io/gitgat/sunday-clays-backend:latest'"),
        (untagged_image, "api: image 'ghcr.io/gitgat/sunday-clays-backend'"),
        (missing_backup, "backup: service missing"),
    ],
)
def test_each_rule_rejects_its_violation(
    mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    stack = copy.deepcopy(VALID)
    mutate(stack)

    result = run(stack)

    assert result.returncode == 1
    assert message in result.stderr


def test_reads_a_file_argument(tmp_path: Path) -> None:
    rendered = tmp_path / "stack.yaml"
    rendered.write_text(yaml.safe_dump(VALID))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(rendered)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_non_mapping_input_is_rejected() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="- just\n- a list\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "not a rendered stack" in result.stderr
```

- [ ] **Step 6: Run them to verify they fail**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_check_stack.py -q`
Expected: FAIL. `12 failed`: Python itself exits 2 with `can't open file '…/scripts/check_stack.py'`, so `test_non_mapping_input_is_rejected` gets its exit code 2 but not the script's own `not a rendered stack` message, and the others fail on the exit code.

- [ ] **Step 7: Implement `scripts/check_stack.py`**

Create `scripts/check_stack.py`:

```python
#!/usr/bin/env python3
"""Fleet rules for the rendered Swarm stack (C11 `stack-config`).

IMAGE_TAG=sha-0000000 docker stack config -c compose.yaml -c compose.swarm.yaml \
    | uv run --no-project --with pyyaml python scripts/check_stack.py [rendered.yaml]
"""

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

ARCH = "node.platform.arch==x86_64"
PINNED_SERVICES = ("db", "backup")
DATA_ROOT = "/var/data/sundayclays/"


def _constraints(service: dict[str, Any]) -> list[str]:
    placement = (service.get("deploy") or {}).get("placement") or {}
    return [str(c).replace(" ", "") for c in placement.get("constraints") or []]


def _bind_sources(service: dict[str, Any]) -> list[str]:
    sources = []
    for volume in service.get("volumes") or []:
        if isinstance(volume, dict) and volume.get("type") == "bind":
            sources.append(str(volume.get("source", "")))
        elif isinstance(volume, str) and volume.startswith("/"):
            sources.append(volume.split(":", 1)[0])
    return sources


def violations(stack: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    services: dict[str, dict[str, Any]] = stack.get("services") or {}
    for name in PINNED_SERVICES:
        if name not in services:
            problems.append(f"{name}: service missing")
    for name, service in sorted(services.items()):
        constraints = _constraints(service)
        if ARCH not in constraints:
            problems.append(f"{name}: missing placement constraint {ARCH}")
        image = str(service.get("image", ""))
        if image.endswith(":latest") or ":" not in image.rsplit("/", 1)[-1]:
            problems.append(f"{name}: image {image!r} must carry an explicit tag other than latest")
        if name in PINNED_SERVICES:
            if not any(c.startswith("node.hostname==") for c in constraints):
                problems.append(f"{name}: missing node.hostname== placement constraint")
            if (service.get("deploy") or {}).get("replicas") != 1:
                problems.append(f"{name}: deploy.replicas must be 1")
            if not any(source.startswith(DATA_ROOT) for source in _bind_sources(service)):
                problems.append(f"{name}: needs a bind mount under {DATA_ROOT}")
    if (services.get("caddy") or {}).get("ports"):
        problems.append("caddy: must not publish ports (Traefik reaches it over traefik_public)")
    for key, secret in sorted((stack.get("secrets") or {}).items()):
        secret_name = str((secret or {}).get("name", ""))
        if not secret_name.startswith("sundayclays_"):
            problems.append(f"secret {key}: name {secret_name!r} must start with sundayclays_")
    return problems


def main(argv: Sequence[str]) -> int:
    text = Path(argv[0]).read_text(encoding="utf-8") if argv else sys.stdin.read()
    stack = yaml.safe_load(text)
    if not isinstance(stack, dict):
        print("check_stack: input is not a rendered stack", file=sys.stderr)
        return 2
    problems = violations(stack)
    for problem in problems:
        print(f"check_stack: {problem}", file=sys.stderr)
    if not problems:
        print(f"check_stack: {len(stack.get('services') or {})} services ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 8: Run the tests and the real stack through it**

Run:

```bash
uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_check_stack.py -q
IMAGE_TAG=sha-0000000 docker stack config -c compose.yaml -c compose.swarm.yaml \
  | uv run --no-project --with pyyaml python scripts/check_stack.py
```

Expected: PASS, `12 passed`, then `check_stack: 5 services ok`.

- [ ] **Step 9: Write the failing branch-protection tests**

Create `scripts/tests/test_setup_branch_protection.py`:

```python
"""Runs setup-branch-protection.sh against a fake `gh` that records every call."""

import json
import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "setup-branch-protection.sh"

FAKE_GH = """#!/usr/bin/env bash
if [[ "$1" == "repo" ]]; then echo "gitgat/sunday-clays"; exit 0; fi
body="$(cat)"
printf '%s\\t%s\\t%s\\n' "$3" "$4" "$(printf '%s' "$body" | tr -d '\\n')" >> "$GH_LOG"
if [[ -n "${GH_FAIL_ON:-}" && "$4" == *"$GH_FAIL_ON"* ]]; then
  echo '{"message":"Branch protection needs GitHub Pro here."}' >&2
  exit 1
fi
echo '{}'
"""


def run_with_fake_gh(
    tmp_path: Path, fail_on: str = ""
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gh"
    fake.write_text(FAKE_GH)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "gh.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_LOG": str(log),
        "GH_FAIL_ON": fail_on,
    }
    result = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )
    calls = [line.split("\t") for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_sets_merge_options_then_protects_main(tmp_path: Path) -> None:
    result, calls = run_with_fake_gh(tmp_path)

    assert result.returncode == 0, result.stderr
    assert [(method, path) for method, path, _ in calls] == [
        ("PATCH", "repos/gitgat/sunday-clays"),
        ("PUT", "repos/gitgat/sunday-clays/branches/main/protection"),
    ]
    assert json.loads(calls[0][2]) == {
        "allow_auto_merge": True,
        "delete_branch_on_merge": True,
        "allow_merge_commit": False,
        "allow_squash_merge": True,
    }
    assert json.loads(calls[1][2]) == {
        "required_status_checks": {"strict": True, "contexts": ["ci-ok"]},
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }


def test_api_error_is_printed_and_exits_1(tmp_path: Path) -> None:
    result, calls = run_with_fake_gh(tmp_path, fail_on="protection")

    assert result.returncode == 1
    assert "Branch protection needs GitHub Pro here." in result.stderr
    assert "branches/main/protection" in result.stderr
    assert len(calls) == 2
```

- [ ] **Step 10: Run them to verify they fail**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_setup_branch_protection.py -q`
Expected: FAIL. `2 failed` (`bash` exits 127 on the missing script, and no `gh` call is logged).

- [ ] **Step 11: Implement `scripts/setup-branch-protection.sh`**

Create `scripts/setup-branch-protection.sh`:

```bash
#!/usr/bin/env bash
# Idempotent repo settings + `main` protection (master plan §0 step 6). Run once, with the
# user's explicit OK, after `ci-ok` has completed at least once on main.
set -euo pipefail

repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

github_api() { # method path json-body
  local output
  if ! output="$(gh api --method "$1" "repos/$repo$2" --input - <<<"$3" 2>&1)"; then
    echo "setup-branch-protection: $1 repos/$repo$2 failed: $output" >&2
    exit 1
  fi
}

github_api PATCH "" '{
  "allow_auto_merge": true,
  "delete_branch_on_merge": true,
  "allow_merge_commit": false,
  "allow_squash_merge": true
}'

github_api PUT "/branches/main/protection" '{
  "required_status_checks": {"strict": true, "contexts": ["ci-ok"]},
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}'

echo "setup-branch-protection: $repo main now requires ci-ok (strict, linear, admins included)"
```

Run: `chmod +x scripts/setup-branch-protection.sh`

- [ ] **Step 12: Run them to verify they pass**

Run: `uv run --no-project --with pytest --with pyyaml pytest scripts/tests/test_setup_branch_protection.py -q`
Expected: PASS, `2 passed`. Do **not** run the script against GitHub here: the controller runs it once, with the user's explicit OK, after `ci-ok` has run on `main` (master §0 step 6).

- [ ] **Step 13: Add the git hooks**

Create `lefthook.yml`:

```yaml
# Git hooks, mirroring claysmasher. Install once per clone: `brew install lefthook && lefthook install`.
# pre-commit: fast lint/format on staged files (+ frontend typecheck, which regenerates the API schema).
# pre-push: full suites, scoped by path, so a frontend-only push never starts Postgres.
pre-commit:
  parallel: true
  commands:
    backend-lint:
      root: "backend/"
      glob: "*.py"
      run: uv run ruff check {staged_files} && uv run ruff format --check {staged_files}
    frontend-lint:
      root: "frontend/"
      glob: "*.{ts,tsx,js}"
      run: pnpm exec eslint --max-warnings 0 {staged_files}
    frontend-format:
      root: "frontend/"
      glob: "*.{ts,tsx,js,json,css,md,html,yaml,yml}"
      run: pnpm exec prettier --check {staged_files}
    frontend-typecheck:
      root: "frontend/"
      glob: "*.{ts,tsx}"
      run: pnpm typecheck

pre-push:
  parallel: true
  commands:
    backend-tests:
      root: "backend/"
      glob: "backend/**"
      run: uv run pytest -q
    frontend-tests:
      root: "frontend/"
      glob: "frontend/**"
      run: pnpm exec vitest --run
```

Run: `lefthook validate && lefthook install && lefthook run pre-commit --all-files --command backend-lint`
Expected: `All good`, `sync hooks: ✔️ (pre-commit, pre-push)`, then `backend-lint` passing (`All checks passed!` and `… files already formatted`).

- [ ] **Step 14: Write CONTRIBUTING.md**

Create `CONTRIBUTING.md`:

````markdown
# Contributing to Sunday Clays

The design spec lives in `docs/superpowers/specs/`; the master plan (Architecture Contract,
execution procedure) and the per-area sub-plans live in `docs/superpowers/plans/`. Every change is
test-driven (write the failing test, watch it fail, make it pass) and lands as a pull request that
passes the single required check, `ci-ok`.

## Toolchain

| Tool | Version | Install |
|---|---|---|
| uv | 0.9.9 or newer. CI and the backend image pin 0.9.9; bump `UV_VERSION` in `.github/workflows/ci.yml`, the `ghcr.io/astral-sh/uv` tag in `backend/Dockerfile` and `[tool.uv] required-version` in `backend/pyproject.toml` together. | `brew install uv` |
| Python | 3.13 (uv installs it) | |
| Node | 22 (`.nvmrc`) | `nvm install && nvm use` |
| pnpm | 10.34.5 (`packageManager` in `frontend/package.json`) | `corepack enable` |
| Docker | Desktop, Colima or OrbStack | |
| lefthook | 2.x | `brew install lefthook && lefthook install` |
| gh + gh-stack | gh 2.101.0 or newer | `gh extension install github/gh-stack` |

## Everyday commands

| What | Where | Command |
|---|---|---|
| Backend checks | `backend/` | `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch` |
| Frontend checks | `frontend/` | `pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage` |
| Repo-script tests | repo root | `uv run --no-project --with pytest --with pyyaml pytest scripts/tests` |
| Local stack | repo root | `scripts/dev-secrets.sh && docker compose up -d --build --wait`, then open http://localhost:8080 |
| E2E (stack running) | `frontend/` | `pnpm exec playwright install chromium && pnpm exec playwright test` |

- `pnpm typecheck` first regenerates `src/api/schema.d.ts` from the backend's OpenAPI schema
  (`pnpm gen:api`), so frontend code is always typed against the current backend.
- Run coverage as `pnpm test --coverage`. `pnpm test -- --coverage` forwards a literal `--`, and
  Vitest then silently skips coverage.
- Stop the local stack with `docker compose down`; add `-v` to wipe its database and backups.

## Tests and databases

- Backend tests start one `postgres:17` testcontainer per pytest run, so Docker must be running. On
  macOS the conftest points Ryuk at `/var/run/docker.sock` automatically.
- `TEST_DATABASE_URL=postgresql+psycopg://…` makes pytest use an existing, empty database instead;
  CI does this. **Never point two concurrent worktrees at the same `TEST_DATABASE_URL`**:
  `committed_engine` truncates every table after each test and `fx_engine` drops and recreates
  `<db>_fx`. Per-run testcontainers are the isolation mechanism.
- `tests/unit` never touches a database; `tests/integration` uses the `engine`, `session` and
  `client` fixtures from `backend/tests/conftest.py`.

## Branches, commits, worktrees and hooks

- One plan task = one branch = one worktree = one pull request. Task branches are
  `task/<NN>-<T>-<slug>` (for example `task/03-2-identity`); `chore/ratchet-wave-<N>` and
  `chore/deps-<pkg>` are controller-only.
- Conventional Commits. Every commit ends with the trailer
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Worktrees live under `.wt/` (gitignored): `git worktree add .wt/<branch> <branch>`; remove them
  with `git worktree remove .wt/<branch>` after the branch lands.
- lefthook's pre-commit hook runs ruff, eslint and prettier on staged files, plus `pnpm typecheck`
  when TypeScript changed. Its pre-push hook runs the backend suite when `backend/**` changed and the
  frontend suite when `frontend/**` changed, so a frontend-only push never starts Postgres.

## Stacked pull requests with gh stack

Each dependency chain in a plan is one stack of pull requests, managed with `gh stack` (extension
`github/gh-stack`). Independent chains are separate stacks off `main`. CI runs on every pull request,
including mid-stack ones whose base is another stack branch, because `ci.yml`'s `pull_request`
trigger has no branch filter.

1. **Build the stack.** In the main checkout run `gh stack init -b main task/03-1-models` and give
   the implementer a worktree: `git worktree add .wt/task/03-1-models task/03-1-models`. When a layer
   passes task review, run `gh stack add task/03-2-identity` from the top of the stack and create its
   worktree. The next implementer starts on top of reviewed but unmerged work.
2. **Siblings.** Same-wave siblings on the same parent that touch disjoint files are implemented
   concurrently on branches cut from the parent layer, then linearised in plan order. Run
   `gh stack add` for the first; for the second, run `git rebase --onto <first> <parent> <second>`,
   then adopt it with `gh stack init`/`gh stack add`. Disjoint files guarantee no conflicts.
3. **Publish.** Run `gh stack submit --auto` after each new layer. Pull requests open as drafts, and
   drafts still run CI. Once the whole chain has passed task review, run
   `gh stack submit --auto --open`.
4. **Fix a lower layer.** Commit on that layer's branch, then run `gh stack rebase --upstack` from
   that layer and `gh stack push`. On a conflict (exit code 3), resolve it in the conflicted layer's
   worktree, `git add` the files, run `gh stack rebase --continue`, then `gh stack push`.
5. **Land.** When every layer's `ci-ok` is green (`gh pr checks <N> --required --watch`), run
   `gh stack merge <stack-number> --squash --yes`, then `gh stack sync --prune` and
   `git worktree remove` for each layer. A ready lower prefix can land alone:
   `gh stack merge <pr-number-of-last-ready-layer> --squash --yes`; the remaining layers re-target
   `main`.
6. **One stack lands at a time.** After each merge, run `gh stack sync` on every other open stack.
   That rebases it onto the new `main` and re-runs CI before it can land. If CI on `main` is red,
   stop all merges until it is fixed.

`gh stack` exit codes: **3** means a rebase conflict (resolve as in step 4). **8** means the stack
is locked by another operation (wait and retry). **9** means stacked pull requests are not enabled
for the repository (ask the owner to enable the preview in the repository settings).

## Coverage ratchet and bundle budgets

- Floors are 90% lines **and** 90% branches, measured separately for the backend and the frontend.
  `ratchets/baseline.json` holds the current floors (`backend_lines`, `backend_branches`,
  `frontend_lines`, `frontend_branches`). `ratchets/budgets.json` holds absolute bundle budgets
  (`entry_js_gz_kb` 250, `total_js_gz_kb` 1600). CI's `ratchet` job fails on any value below its
  floor or over its budget.
- Task pull requests never edit `ratchets/`. CI rejects such a change unless the branch starts with
  `chore/ratchet-`. After each wave merges, the controller raises the floors:

  ```bash
  gh run download <id of the latest main ci run> -D artifacts
  python3 scripts/ratchet.py update     # floor = max(old, max(90, floor(measured) - 1)); never lowers
  ```

  The controller then opens `chore/ratchet-wave-<N>`, which merges like any other pull request.

## Dependencies and lockfiles

- Plan 01 declares the complete Phase-1 dependency set in `backend/pyproject.toml` and
  `frontend/package.json`. Task pull requests never change the dependency lists, `uv.lock` or
  `pnpm-lock.yaml`; tool-config sections and scripts may change.
- A genuinely new package first lands in a controller pull request `chore(deps): add <pkg>` on
  branch `chore/deps-<pkg>` (manifest and lockfile only). The task then rebases onto it.
- Never hand-merge a lockfile conflict. Regenerate the lockfile, then commit it:
  - backend: `git checkout origin/main -- backend/uv.lock && (cd backend && uv lock)`
  - frontend: `(cd frontend && pnpm install)`
- `tools/trophy_art` has its own `pyproject.toml` and is exempt.

## Continuous integration and deployment

- `.github/workflows/ci.yml` runs on every pull request, on pushes to `main` and on demand. Its jobs
  are `backend`, `frontend`, `ratchet`, `docker`, `stack-config` and `e2e`, plus the aggregate
  `ci-ok` (the only required check), which fails if any job fails, is cancelled or is skipped.
  `scripts/tests/test_ci_config.py` guards this shape. A new job needs no `if:` and must be added
  to `ci-ok.needs`.
- Images are published to GHCR only from CI-green `main` commits (`publish` job). Deploying is
  described in `deploy/README.md`.
- Branch protection on `main` is applied once, with the owner's OK, by
  `scripts/setup-branch-protection.sh`, after `ci-ok` has run on `main` at least once.
````

- [ ] **Step 15: Full local verification**

Run:

```bash
uv run --no-project --with pytest --with pyyaml pytest scripts/tests -q
(cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch -q)
(cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage)
```

Expected: `50 passed` (17 ratchet/bundle + 3 dev-secrets + 16 CI-shape + 12 stack + 2 branch-protection). Then the backend at `81 passed` with 100% coverage, and the frontend clean with `Tests  9 passed (9)`.

- [ ] **Step 16: Commit**

```bash
git add .github scripts/check_stack.py scripts/setup-branch-protection.sh scripts/tests/test_ci_config.py \
  scripts/tests/test_check_stack.py scripts/tests/test_setup_branch_protection.py lefthook.yml CONTRIBUTING.md
git commit -F - <<'EOF'
ci: add CI and publish workflows, stack check, hooks and contributing guide

ci.yml runs backend, frontend, ratchet, docker, stack-config and e2e jobs behind the single
required aggregate check ci-ok (fails on any failed, cancelled or skipped job); publish.yml
pushes sha-<7>/latest images from CI-green main; check_stack.py enforces the Swarm fleet rules;
lefthook mirrors the checks locally; setup-branch-protection.sh and CONTRIBUTING.md document
the stacked-PR, ratchet and dependency workflow.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

**Implementer: stop here and report.** Do not push, open pull requests or run anything against GitHub. The controller takes over with the "Controller follow-up after Task 5" section near the top of this plan, which is deliberately outside every task brief.

