# Sunday Clays — Plan 04: Auth & Admin API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Every subagent and workflow agent runs on Opus** (master plan override of the SDD model guidance).
> An implementer receives only its own `### Task N` section; each task therefore restates the context it needs
> and points back to this plan's Global Constraints and Decisions.

**Goal:** Two-password login (viewer/admin) with signed, role-bound session cookies, a per-IP login rate limit and a
CSRF guard; role wiring for every API router; and the admin API — imports (upload → preview → commit / discard /
rollback), job status, overlay rules, shooter identity fixes, data issues, possible duplicates, audit log and
recompute — that the admin UI (Plan 08 T5a–T5c) and the e2e fixture seed build on.

**Architecture:** `auth/` holds pure-ish building blocks (argon2 verify with a memory cap, itsdangerous session tokens
bound to a fingerprint of the current password hash, `login_attempts`-backed rate limiting, FastAPI role
dependencies, `record_audit`). `create_app()` gets one edit: routers are included with `require_admin` /
`require_viewer` chosen by module name, and a pure-ASGI `CsrfGuardMiddleware` rejects cross-site writes before
routing. The admin route modules are thin: they validate input, call the Plan 03 domain API (C5/C6), enqueue the
coalesced `rebuild`/`recompute` job, and write `audit_log` in the same transaction.

**Tech Stack:** Python 3.13 · FastAPI ≥0.141 (Starlette 1.x) · SQLAlchemy 2 Core over the C4 metadata ·
pydantic v2 / pydantic-settings · argon2-cffi · itsdangerous · pytest + testcontainers (`postgres:17`) ·
Playwright (`request` fixture, `setup` project) · TypeScript strict.

**Spec:** `/Users/bryanmoran/code/sunday-clays/docs/superpowers/specs/2026-09-27-sunday-clays-design.md`

**Master:** `/Users/bryanmoran/code/sunday-clays/docs/superpowers/plans/2026-09-27-00-master.md` (Architecture
Contract C1–C12 is binding; C2, C4, C5, C6, C8 and C10 are the sections this plan implements or consumes).

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
None of the five master Review Focus items is owned by Plan 04 (they belong to Plans 02, 03, 06, 08 and 09). These
are the plan-specific input classes most likely to bite a person using this software, most likely first; each
line's pinning tests live in the named task.
1. **Password guessing from rotating addresses or spoofed forwarding headers** → failures are counted per client-IP
   bucket (`X-Real-IP` set by Caddy, never `X-Forwarded-For`; IPv6 per /64) and the 11th attempt in 15 minutes gets
   429 before any argon2 work. Task 1: `test_rate_limit_ignores_spoofed_x_forwarded_for`,
   `test_rate_limit_buckets_by_x_real_ip`, `test_ipv6_bucketed_by_64`, `test_eleventh_failure_returns_429`.
2. **A failed login whose attempt row is lost because the request session rolls back on the 401** (the limiter would
   then never trip) → the failure row is committed before the error is raised. Task 1:
   `test_failed_attempt_row_persists_after_401`.
3. **A router added in a later wave without auth, or an `/api/admin/` path defined outside an `admin_*` module** → every
   served route is enumerated at runtime: no cookie → 401 (except the three public routes, also with
   `If-None-Match: *`), viewer → 403 on every admin route, admin paths only from `admin_*` modules. Task 1:
   `test_every_route_needs_a_session_except_public`, `test_viewer_gets_403_on_every_admin_route`,
   `test_admin_paths_are_defined_only_in_admin_modules`.
4. **A page on a sibling site (e.g. `shop.claysmasher.com` — same-site, so SameSite=Strict still sends the cookie)
   posting to the admin API with the admin's cookie** → 403 `csrf` before routing. Task 1:
   `test_cross_site_post_is_blocked`, `test_cross_site_upload_with_admin_cookie_is_blocked`.
5. **Wrong or oversized uploads** (a 50 MB export, a `.csv`, a corrupt workbook, a stale scores copy missing the last
   week) → 413 before auth, 400 `unsupported_file_type` / `unreadable_file` with nothing staged, and a commit that
   needs `confirm_removals`. Task 2: `test_oversized_upload_without_session_gets_413`,
   `test_upload_backstop_rejects_one_byte_over_limit`, `test_non_xlsx_filename_is_rejected`,
   `test_unreadable_workbook_is_400_and_stages_nothing`, `test_stale_scores_upload_needs_confirmation_to_commit`
   (the API-level companion of master Review Focus #1, which Plan 03 T6 owns).

## Decisions
Choices made where the master is silent or leaves room; cross-plan auditors should check the ones that name another
plan.
- **D1 Route paths.** Every route module declares full paths through `APIRouter(prefix="/api/…")`; `create_app()`
  calls `app.include_router(router, dependencies=role_dependencies(name))` with no `prefix`. The route matrix compares
  router paths with served paths, so an include-time prefix fails `test_admin_paths_are_defined_only_in_admin_modules`.
- **D2 Path parameters** keep C8's literal `{id}` template (openapi-fetch callers write `params: { path: { id } }`) and
  bind it to a descriptive argument: `import_id: Annotated[int, Path(alias="id")]` (verified on FastAPI 0.141).
- **D3 Auth errors use the C2 envelope.** `auth/deps.py` defines `NotAuthenticatedError` (401), `ForbiddenError` (403)
  and `TooManyRequestsError` (429) as `DomainError` subclasses (C2: "tasks choose the status by raising the right
  subclass"; `api/errors.py` is not edited). Codes: `unauthenticated` (no, invalid, expired or revoked cookie),
  `invalid_password`, `forbidden`, `rate_limited`, `login_busy`. The master's "raise HTTPException(401)" is implemented
  as `raise NotAuthenticatedError("invalid_password", …)`, still after `session.commit()`.
- **D4 Tables through Core.** C4 fixes table and column names but not ORM class names, so Plan 04 reads and writes
  `sunday_clays.models.Base.metadata.tables["<table>"]` with SQLAlchemy Core (`login_attempts`, `audit_log`,
  `imports`, `jobs`, `rules`, `rounds`, `shooter_profiles`, `data_issues`, `app_state`, `shooters`).
- **D5 Settings access.** Routes and dependencies take `Annotated[Settings, Depends(get_settings)]`;
  `ratelimit.is_limited(session, ip)` calls `get_settings()` itself because its contract signature has no settings
  argument. Test fixture `auth_env` sets `SESSION_SECRET`, `VIEWER_PASSWORD_HASH`, `ADMIN_PASSWORD_HASH`,
  `COOKIE_SECURE=false` (and, when no `DATABASE_URL` is set, `postgresql+psycopg://nobody:x@127.0.0.1:<closed_port>/x`
  on Plan 01 T1's `closed_port` fixture, exactly as Plan 01's `settings_env` does, so a stray connection from a unit
  test is refused at once and never reaches a local Postgres on 5432), deletes their `*_FILE` twins (names from Plan
  01's `config.SECRET_FIELDS`) and clears the `get_settings` cache. Plan 01 T1's `client` and Plan 03 T6's
  `fx_client` read Settings from env vars through Plan 01's `test_settings` fixture and install no `get_settings`
  dependency override; `anon_client`, `viewer_client`, `admin_client` and `fx_*_client` still pop one defensively, so
  every caller sees the one `auth_env` Settings object. The passwords and session secret are Plan 01's conftest
  constants `VIEWER_TEST_PASSWORD`, `ADMIN_TEST_PASSWORD` and `TEST_SESSION_SECRET`, so a test that logs in through
  Plan 01's `client` world (`password_hashes`) and one using `auth_env` type the same passwords. Only the hashes
  differ: cheap argon2id parameters (m=8 KiB, t=1); verification reads the parameters from the hash.
- **D6 Extra test fixtures** beyond C2's four: `auth_env` → `Settings`, `login_passwords` → `dict[Role, str]`
  (Plan 01's `VIEWER_TEST_PASSWORD` / `ADMIN_TEST_PASSWORD`), `anon_client` (the C2 `client` wired to `auth_env`, no
  cookie). `viewer_client`/`admin_client` are separate `TestClient`s on the same app and DB session, so one test can
  hold an anonymous and a logged-in client.
- **D7 Hash memory cap.** `verify_password` refuses (returns False, logs an error) any stored hash whose memory cost
  exceeds 19,456 KiB — the master's "capping each verify at ~19 MiB" is enforced, so the 4 concurrent verifies stay
  near 80 MiB and a misconfigured hash fails closed. `match_role` checks the admin hash first.
- **D8 Audit actions.** Admin logins are audited as `auth.login` (viewer logins are only in `login_attempts`). Admin
  mutations: `imports.stage`, `imports.commit`, `imports.discard`, `imports.rollback`, `rules.create`,
  `rules.deactivate`, `shooters.merge`, `shooters.rename`, `shooters.status`, `shooters.alias`, `ops.recompute`. A merge
  dry run writes nothing and is not audited. `details` go through FastAPI's `jsonable_encoder` (dates → ISO strings).
- **D9 CSRF middleware** is pure ASGI, guards every HTTP request whose method is not GET/HEAD/OPTIONS (the API serves
  only `/api/*`, so this equals C8's scope), and is added after `BodySizeLimitMiddleware`, which makes it the outer
  one: a cross-site oversized upload gets 403.
- **D10 `client_ip`.** A non-IP `X-Real-IP` is ignored (falls back to the TCP peer); IPv4-mapped IPv6 → the IPv4
  address; IPv6 → `"<network>/64"`; a non-IP peer (TestClient's `testclient`) is used verbatim; no peer → `unknown`.
- **D11 Shared admin helpers** live in `api/routes/_admin.py` (leading underscore, skipped by discovery like
  `_filters.py`): `JobRefOut` and `ensure_exists` (Task 1), `RuleMutationOut` (Task 3). 404 codes:
  `import_not_found` and `job_not_found` come from Plan 03 itself (`get_import_preview`, `commit_import`,
  `discard_import`, `rollback_import` and `get_job` raise `NotFoundError` with those codes), so Task 2 runs no
  pre-check query. Task 3's `ensure_exists` raises `shooter_not_found` / `rule_not_found`, the same codes Plan 03 T5's
  `create_rule` and `deactivate_rule` raise (Plan 03 Decision 15). It is required for the merge dry run, which calls
  no domain function; on the other shooter and rule routes it only answers the 404 before the domain call would.
- **D12 Response shapes where C8 is silent.** `POST /api/auth/logout` → 204; `POST /api/admin/imports` → 200
  `ImportPreview`; discard → 204; commit, rollback and recompute → `JobRefOut{job_id}`; rule create/deactivate and
  shooter rename/status/aliases → `RuleMutationOut{rule_id, job_id}`; `GET /api/admin/rules` → `list[RuleOut]` newest
  first; `GET /api/admin/data-issues` → `list[DataIssueOut]` ordered by code, event_date desc (nulls last), id;
  `GET /api/admin/possible-duplicates` → `list[PossibleDuplicateOut{a, b: DuplicateSideOut}]`;
  `GET /api/admin/audit?limit=200&offset=0` (limit 1–1000) → `list[AuditEntryOut]` newest first. `DataIssueOut.details`
  and `AuditEntryOut.details` are a non-null `dict[str, Any]`: C4 `data_issues.details` and `audit_log.details` are
  NOT NULL with default `'{}'` (Plan 03 T1), so openapi-typescript emits `{[key: string]: unknown}`, which Plan 08
  T5c reads as `Record<string, unknown>` (`issue.details.name_key`, `detailsSummary(entry.details)`).
- **D13 Optional bodies.** `POST /api/admin/imports/{id}/commit` without a body means `confirm_removals=false`;
  `POST /api/admin/recompute` without a body means `recalibrate=false`.
- **D14 Upload type limit.** The basename (last `/`- or `\`-separated segment; the last 255 characters kept) must end
  in `.xlsx` or `.xlsm` (any case), else 400 `unsupported_file_type`. python-multipart (0.0.32) already cuts a
  drive-letter path such as `C:\Users\bob\x.xlsx` to its basename before the route runs, so `clean_filename` is tested
  with the paths that do reach it: `Users\bob\x.xlsx`, `reports/2026/x.xlsx` and a 300-character name. The upload
  route is `async` (for `await file.read(max_upload_bytes + 1)`) and runs `stage_import` + audit in
  `run_in_threadpool`, so parsing never blocks the event loop.
- **D15 Stored preview (cross-plan: Plan 03 T3, T6).** `GET /api/admin/imports/{id}` returns Plan 03 T3's
  `domain.imports.get_import_preview(session, import_id)` (404 `import_not_found` from Plan 03), and
  `GET /api/admin/imports` returns Plan 03 T6's `domain.imports.list_imports(session)` (newest first). Plan 04 never
  reads the `imports.summary`/`imports.findings` JSON itself, so Plan 03 alone owns that storage format.
- **D16 Recalibration.** `POST /api/admin/recompute {"recalibrate": true}` also deletes `app_state.skill_params` in the
  request transaction: C6's queued-only dedupe returns an already-queued plain `recompute` job without the new payload,
  so the request would otherwise be lost. The handler's own delete (C6) stays and is idempotent.
- **D17 Possible duplicates** are computed on demand from live `rounds` (identity key → event dates, key → shooter)
  with C3 `similar_name_keys`; key pairs already resolved to one shooter are dropped; each shooter pair is reported
  once, via its lexicographically smallest key pair; each side carries `shooter_profiles` stats.
- **D18 Shooter fixes.** Merging a shooter into itself → 400 `merge_same_shooter` (checked first, dry runs too, so
  Plan 03's `invalid_rule` for a self-merge is never reached through this route); an unknown shooter → 404. `shared_dates` = distinct live `rounds.event_date` values both ids have. Rename strips
  whitespace (1–100 chars). Aliases take the identity key verbatim after stripping (1–200 chars) and never re-run
  `name_key`, which would mangle keys such as `elias@2025-02-23`.
- **D19 e2e auth state.** `mobile`/`desktop` default `storageState` is the viewer state; admin specs opt in with
  `test.use({ storageState: ADMIN_STATE })`; unauthenticated specs (e.g. Plan 07 T3's login spec) use
  `test.use({ storageState: { cookies: [], origins: [] } })`. `e2e/authState.ts` exports the paths and
  `e2ePassword(role)`. The admin setup test also seeds the fixtures (Task 2), so seeded data exists before any spec.
- **D20 `.gitignore` (Plan 01 T4).** The root pattern `e2e/.auth/` contains a slash, so it is anchored to the repo
  root and does not match `frontend/e2e/.auth/`. Plan 01 T4 (its Decision 23) already appends `**/e2e/.auth/`, which
  does, so the setup's live session cookies are never committed. Plan 04 does not edit `.gitignore`; Task 1 Step 29
  only confirms the ignore with `git check-ignore -v`.
- **D21 e2e failed-login budget.** All e2e traffic reaches the API from one client IP and the limit is 10 failures per
  15 minutes; `auth.spec.ts` spends 2 per run (one wrong password per viewport project). Later specs keep their
  wrong-password attempts minimal (Plan 07 T3's login spec adds 2).
- **D22 Node typings for e2e (Plan 01 T2).** `authState.ts` and `auth.setup.ts` use `process.env`, `node:fs` and
  `node:path`. Their types come from `@types/node`, which Plan 01 T2 declares as a devDependency (its Decision 5);
  Plan 01 T2's `tsconfig.json` has `"types": ["vite/client", "node"]` and includes `e2e` and `playwright.config.ts`.
  Plan 04 adds no dependency.
- **D23 Route enumeration.** FastAPI ≥0.141 keeps each included router as one `_IncludedRouter` entry in `app.routes`
  instead of copying its `APIRoute`s, so the route matrix walks `fastapi.routing.iter_route_contexts(app.routes)`.
  `test_walk_sees_the_auth_routes` fails loudly if a FastAPI upgrade changes that walk, instead of letting the matrix
  pass vacuously.
- **D24 Role-wiring probes (cross-plan: Plan 06 T1).** `tests/unit/api/test_role_wiring.py` swaps
  `discover_routers` for probe routers whose `/api/admin/probe`, `/api/probe` and `/api/public-probe` carry no
  dependency of their own, so only `create_app()`'s wiring can make them 401/403 (a separate
  `/api/admin/actor-probe` exercises `admin_actor`). All four are POST: Plan 06 T1's `CacheHeadersMiddleware` opens
  `get_session` for every ETag-eligible GET before the route runs, which a `tests/unit` file must never do (C2), and a
  TestClient POST carries no `Origin`, so the CSRF guard lets it through.

## File Structure
Backend paths are relative to `backend/`, frontend paths to `frontend/`.

| File | Task | Responsibility |
|---|---|---|
| `src/sunday_clays/auth/__init__.py` | 1 | Package marker for the auth building blocks. |
| `src/sunday_clays/auth/sessions.py` | 1 | `Role`, `COOKIE_NAME`, `TTL`; sign and load fingerprint-bound session tokens. |
| `src/sunday_clays/auth/passwords.py` | 1 | argon2id hashing (OWASP profile), capped verification, `match_role`. |
| `src/sunday_clays/auth/hashpw.py` | 1 | `python -m sunday_clays.auth.hashpw`: prompt twice, print a hash. |
| `src/sunday_clays/auth/ratelimit.py` | 1 | `is_limited` / `record_attempt` over `login_attempts` (inline pruning). |
| `src/sunday_clays/auth/deps.py` | 1 | `client_ip`, role dependencies, `Actor`/`admin_actor`, `record_audit`, 401/403/429 errors. |
| `src/sunday_clays/api/csrf.py` | 1 | `CsrfGuardMiddleware` (Origin / Sec-Fetch-Site check). |
| `src/sunday_clays/api/routes/auth.py` | 1 | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`. |
| `src/sunday_clays/api/routes/_admin.py` | 1, 3 | Shared admin models (`JobRefOut`, `RuleMutationOut`) and `ensure_exists`. |
| `src/sunday_clays/api/app.py` | 1 (modify) | Role wiring by module name + CSRF middleware (the one-time C2 edit). |
| `tests/conftest.py` | 1 (modify) | `auth_env`, `login_passwords`, `anon_client`, `viewer_client`, `admin_client`, `fx_viewer_client`, `fx_admin_client`. |
| `tests/unit/auth/test_auth_sessions.py` | 1 | Token round trip, per-role rotation, per-role TTL, forgery. |
| `tests/unit/auth/test_auth_passwords.py` | 1 | Hash profile, verify, memory cap, `match_role`. |
| `tests/unit/auth/test_auth_hashpw.py` | 1 | CLI prompts, mismatch, argv refusal, `python -m` entry. |
| `tests/unit/auth/test_auth_client_ip.py` | 1 | `client_ip` table. |
| `tests/unit/api/test_csrf_middleware.py` | 1 | CSRF block/pass table. |
| `tests/unit/api/test_role_wiring.py` | 1 | `create_app()` picks the role dependency from the module name. |
| `tests/integration/auth/test_login_rate_limit.py` | 1 | Limiter window, threshold, pruning. |
| `tests/integration/auth/test_audit_helpers.py` | 1 | `record_audit`, `ensure_exists`. |
| `tests/integration/api/test_auth_routes.py` | 1 | Login/logout/me, cookie attributes, 401/429 paths, CSRF with an admin cookie. |
| `tests/integration/api/test_route_auth_matrix.py` | 1 | Runtime walk of every route (C2/C8 auth matrix). |
| `src/sunday_clays/api/routes/admin_imports.py` | 2 | Import upload/list/get/commit/discard/rollback and `GET /api/admin/jobs/{id}`. |
| `tests/integration/api/test_admin_imports_api.py` | 2 | Import and job endpoints, size/type limits, stale-file confirmation. |
| `src/sunday_clays/api/routes/admin_rules.py` | 3 | `GET` and `POST /api/admin/rules`, `POST /api/admin/rules/{id}/deactivate`. |
| `src/sunday_clays/api/routes/admin_shooters.py` | 3 | Merge (dry run), rename, status, aliases → rules. |
| `src/sunday_clays/api/routes/admin_ops.py` | 3 | Data issues, possible duplicates, audit log, recompute. |
| `tests/unit/api/test_duplicate_key_pairs.py` | 3 | Pairing/dedupe rules of `duplicate_key_pairs`. |
| `tests/integration/api/test_admin_rules_api.py` | 3 | Rule endpoints on the committed fixtures. |
| `tests/integration/api/test_admin_shooters_api.py` | 3 | Shooter-fix endpoints on the committed fixtures. |
| `tests/integration/api/test_admin_ops_api.py` | 3 | Issues, duplicates, audit, recompute. |
| `e2e/authState.ts` | 1 | Storage-state paths and `e2ePassword(role)`. |
| `e2e/auth.setup.ts` | 1, 2 (modify) | `setup` project: log in both roles, write storage states; Task 2 adds the fixture seed. |
| `e2e/auth.spec.ts` | 1 | API-level auth e2e at both viewports. |
| `playwright.config.ts` | 1 (modify) | `setup` project; `mobile`/`desktop` depend on it and default to the viewer state. |

## Waves
Waves: {T1} → {T2, T3}.

Task 1 = master T1 (Global Wave 2, after Plan 03 T1). Tasks 2 and 3 = master T2 and T3 (Global Wave 3, after Plan 03
T6 and T7); they are siblings on disjoint files (only Task 3 edits `_admin.py`; only Task 2 edits `auth.setup.ts`).

---

### Task 1: Auth core, role wiring and CSRF guard (master Plan 04 T1)

**Context.** Read this plan's Global Constraints and Decisions (D1–D10, D19–D24) and master sections C2 (backend
conventions, test fixtures, errors), C4 (`login_attempts`, `audit_log`) and C8 (sessions, client IP, CSRF, public
routes) first. Plan 01 is merged; Plan 03 T1's models exist. Integration tests need Docker (testcontainers) or
`TEST_DATABASE_URL`. Create files with the Write/Edit tools rather than shell heredocs (a local hook blocks shell
commands that contain `get_secret_value`). All backend commands run in `backend/`, all frontend commands in
`frontend/`.

**Files:**
- Create: `backend/src/sunday_clays/auth/__init__.py`, `backend/src/sunday_clays/auth/sessions.py`,
  `backend/src/sunday_clays/auth/passwords.py`, `backend/src/sunday_clays/auth/hashpw.py`,
  `backend/src/sunday_clays/auth/ratelimit.py`, `backend/src/sunday_clays/auth/deps.py`,
  `backend/src/sunday_clays/api/csrf.py`, `backend/src/sunday_clays/api/routes/auth.py`,
  `backend/src/sunday_clays/api/routes/_admin.py`
- Modify: `backend/src/sunday_clays/api/app.py` (router loop + one middleware line), `backend/tests/conftest.py`
  (append the Plan 04 fixture block), `frontend/playwright.config.ts`
- Create (frontend): `frontend/e2e/authState.ts`, `frontend/e2e/auth.setup.ts`, `frontend/e2e/auth.spec.ts`
- Test: `backend/tests/unit/auth/test_auth_sessions.py`, `backend/tests/unit/auth/test_auth_passwords.py`,
  `backend/tests/unit/auth/test_auth_hashpw.py`, `backend/tests/unit/auth/test_auth_client_ip.py`,
  `backend/tests/unit/api/test_csrf_middleware.py`, `backend/tests/unit/api/test_role_wiring.py`,
  `backend/tests/integration/auth/test_login_rate_limit.py`, `backend/tests/integration/auth/test_audit_helpers.py`,
  `backend/tests/integration/api/test_auth_routes.py`, `backend/tests/integration/api/test_route_auth_matrix.py`

**Interfaces:**
- Consumes:
  - Plan 01 T1: `sunday_clays.config.Settings` fields `session_secret: SecretStr`, `viewer_password_hash: SecretStr`,
    `admin_password_hash: SecretStr`, `cookie_secure: bool`, `login_max_failures: int = 10`,
    `login_window_minutes: int = 15`, `max_upload_bytes: int`; `sunday_clays.config.get_settings()` (an `lru_cache`
    function, so it has `cache_clear()`); `sunday_clays.db.get_session` (FastAPI dependency, commits on success and
    rolls back on any exception); `sunday_clays.domain.errors.DomainError(code, message)` with
    `status_code: ClassVar[int]` and `NotFoundError` (404); `sunday_clays.api.app.create_app() -> FastAPI`;
    `sunday_clays.api.routes.discover_routers() -> list[tuple[str, APIRouter]]`;
    `sunday_clays.api.bodylimit.BodySizeLimitMiddleware`; `sunday_clays.config.SECRET_FIELDS`; conftest fixtures
    `engine`, `session`, `client` (settings from env vars via `test_settings`, no `get_settings` override),
    `closed_port` (`-> int`, a localhost TCP port with nothing listening) and the conftest constants
    `VIEWER_TEST_PASSWORD = "viewer-test-password"`, `ADMIN_TEST_PASSWORD = "admin-test-password"`,
    `TEST_SESSION_SECRET` (module-level names defined above the Plan 04 block in `tests/conftest.py`).
  - Plan 01 T2: `@types/node` devDependency and `tsconfig.json` (`"types": ["vite/client", "node"]`, `include` covers
    `e2e` and `playwright.config.ts`) — Decision D22.
  - Plan 01 T4: `frontend/playwright.config.ts` (top-level `use.baseURL: 'http://localhost:8080'`; projects `desktop` =
    `{...devices['Desktop Chrome'], viewport 1440×900}` and `mobile` = `{...devices['Desktop Chrome'], viewport 390×844,
    deviceScaleFactor: 3, isMobile: true, hasTouch: true}`), `frontend/e2e/fixtures.ts` exporting `test` and
    `expect`; the root `.gitignore` entry `**/e2e/.auth/` (Decision D20); compose e2e stack (`compose.test.yaml`,
    `COOKIE_SECURE=false`), `scripts/dev-secrets.sh`.
  - Plan 03 T1: `sunday_clays.models.Base` whose metadata holds C4 tables `login_attempts(id, ip, at, success)`,
    `audit_log(id, at default now(), ip, role, action, details jsonb)`, `shooters(id, display_name, created_at)`.
  - Plan 03 T6 (only when requested; merges later in Wave 2 or 3): conftest fixture `fx_client`.
- Produces:
  - `sunday_clays.auth.sessions`: `Role = Literal["viewer", "admin"]`; `COOKIE_NAME: Final = "sc_session"`;
    `TTL: Final[Mapping[Role, timedelta]]` (viewer 30 days, admin 12 hours);
    `issue_session(settings: Settings, role: Role) -> str`;
    `load_session(settings: Settings, token: str, *, now: datetime | None = None) -> Role | None`.
  - `sunday_clays.auth.passwords`: `MEMORY_COST_KIB = 19_456`, `TIME_COST = 2`, `PARALLELISM = 1`,
    `MAX_VERIFY_MEMORY_KIB = 19_456`; `hash_password(password: str) -> str`;
    `verify_password(password_hash: str, password: str) -> bool`;
    `match_role(settings: Settings, password: str) -> Role | None`.
  - `sunday_clays.auth.hashpw.main(argv: Sequence[str] | None = None) -> int`; CLI `python -m sunday_clays.auth.hashpw`.
  - `sunday_clays.auth.ratelimit`: `is_limited(session: Session, ip: str) -> bool`;
    `record_attempt(session: Session, ip: str, success: bool) -> None`.
  - `sunday_clays.auth.deps`: `client_ip(request: Request) -> str`; `current_role(request, settings) -> Role | None`;
    `require_viewer(role) -> Role` (401 `unauthenticated`); `require_admin(role) -> Role` (403 `forbidden`);
    `@dataclass(frozen=True) class Actor: role: Role; ip: str`;
    `admin_actor(request: Request, role: Role) -> Actor` (a dependency; depends on `require_admin`);
    `record_audit(session: Session, ip: str | None, role: str, action: str, details: Mapping[str, Any]) -> None`;
    `NotAuthenticatedError` (401), `ForbiddenError` (403), `TooManyRequestsError` (429), all `DomainError`s.
  - `sunday_clays.api.csrf`: `is_cross_site(method: str, headers: Headers) -> bool`; `CsrfGuardMiddleware(app)`.
  - `sunday_clays.api.routes.auth`: `router`; `LoginIn{password: str}`; `RoleOut{role: Role}`;
    `POST /api/auth/login` → `RoleOut` + cookie; `POST /api/auth/logout` → 204; `GET /api/auth/me` → `RoleOut` | 401.
  - `sunday_clays.api.routes._admin`: `class JobRefOut(BaseModel): job_id: int`;
    `ensure_exists(session: Session, table: str, row_id: int, code: str, noun: str) -> None`.
  - `sunday_clays.api.app`: `PUBLIC_ROUTE_MODULES = frozenset({"health", "auth"})`;
    `role_dependencies(module_name: str) -> list[Any]`.
  - conftest: `auth_env` → `Settings`, `login_passwords` → `dict[Role, str]`, `anon_client`, `viewer_client`,
    `admin_client`, `fx_viewer_client`, `fx_admin_client` (all `TestClient`).
  - e2e: Playwright project `setup` (`e2e/auth.setup.ts`); `e2e/authState.ts` exports
    `VIEWER_STATE = 'e2e/.auth/viewer.json'`, `ADMIN_STATE = 'e2e/.auth/admin.json'`,
    `e2ePassword(role: 'viewer' | 'admin'): string`.
  - Consumers: Plan 04 T2/T3 (deps, `_admin.py`, fixtures), Plan 06 T1 (auth routes and fixtures in ETag tests),
    Plan 07 T3 (login UI calls the auth routes), every later route module (role wiring), every later e2e spec (the
    `setup` project and storage states).

**Branch:** `task/04-1-auth-core`

**Depends on:** Plan 01 T1–T5 (Wave 0), Plan 03 T1.

- [ ] **Step 1: Add the Plan 04 fixture block to `backend/tests/conftest.py` and write the failing session tests**

Merge these imports into the existing import block of `backend/tests/conftest.py` (skip any already present;
`ruff check --fix` sorts them):

```python
import os
from collections.abc import Iterator
from typing import cast

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sunday_clays.auth.sessions import Role
from sunday_clays.config import SECRET_FIELDS, Settings, get_settings
```

Append this block at the end of `backend/tests/conftest.py`. It reuses Plan 01's module-level constants
`VIEWER_TEST_PASSWORD`, `ADMIN_TEST_PASSWORD` and `TEST_SESSION_SECRET` (defined near the top of the same file) and
Plan 01's `SECRET_FIELDS` (Decision D5):

```python
# --- Plan 04 T1: auth fixtures (C2; plan Decisions D5, D6) ------------------------------------

_TEST_PASSWORDS: dict[Role, str] = {
    "viewer": VIEWER_TEST_PASSWORD,
    "admin": ADMIN_TEST_PASSWORD,
}
# Cheap argon2id parameters keep logins fast; verify reads the parameters from the hash.
_FAST_HASHER = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
_TEST_HASHES: dict[Role, str] = {
    role: _FAST_HASHER.hash(pw) for role, pw in _TEST_PASSWORDS.items()
}
_SECRET_ENV = tuple(name.upper() for name in SECRET_FIELDS)


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch, closed_port: int) -> Iterator[Settings]:
    """Settings with the known test passwords, via env vars, for every get_settings() caller.

    Keeps a DATABASE_URL already set (e.g. by ``client``); otherwise points at Plan 01's closed
    port, like ``settings_env``, so a stray connection from a unit test is refused at once.
    """
    for name in _SECRET_ENV:
        monkeypatch.delenv(f"{name}_FILE", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        os.environ.get("DATABASE_URL")
        or f"postgresql+psycopg://nobody:x@127.0.0.1:{closed_port}/x",
    )
    monkeypatch.setenv("SESSION_SECRET", TEST_SESSION_SECRET)
    monkeypatch.setenv("VIEWER_PASSWORD_HASH", _TEST_HASHES["viewer"])
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", _TEST_HASHES["admin"])
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def login_passwords() -> dict[Role, str]:
    return dict(_TEST_PASSWORDS)


def _use_env_settings(test_client: TestClient) -> FastAPI:
    app = cast(FastAPI, test_client.app)
    app.dependency_overrides.pop(get_settings, None)
    return app


def _logged_in(app: FastAPI, role: Role) -> TestClient:
    logged_in = TestClient(app)
    response = logged_in.post("/api/auth/login", json={"password": _TEST_PASSWORDS[role]})
    assert response.status_code == 200, response.text
    return logged_in


@pytest.fixture
def anon_client(client: TestClient, auth_env: Settings) -> TestClient:
    """The C2 ``client`` (no cookie) wired to the ``auth_env`` settings."""
    _use_env_settings(client)
    return client


@pytest.fixture
def viewer_client(anon_client: TestClient) -> Iterator[TestClient]:
    logged_in = _logged_in(cast(FastAPI, anon_client.app), "viewer")
    yield logged_in
    logged_in.close()


@pytest.fixture
def admin_client(anon_client: TestClient) -> Iterator[TestClient]:
    logged_in = _logged_in(cast(FastAPI, anon_client.app), "admin")
    yield logged_in
    logged_in.close()


@pytest.fixture
def fx_viewer_client(fx_client: TestClient, auth_env: Settings) -> Iterator[TestClient]:
    """Viewer over the committed-fixtures world; usable once Plan 03 T6's ``fx_client`` exists."""
    logged_in = _logged_in(_use_env_settings(fx_client), "viewer")
    yield logged_in
    logged_in.close()


@pytest.fixture
def fx_admin_client(fx_client: TestClient, auth_env: Settings) -> Iterator[TestClient]:
    """Admin over the committed-fixtures world; usable once Plan 03 T6's ``fx_client`` exists."""
    logged_in = _logged_in(_use_env_settings(fx_client), "admin")
    yield logged_in
    logged_in.close()
```

Create `backend/tests/unit/auth/test_auth_sessions.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from itsdangerous import URLSafeTimedSerializer
from pydantic import SecretStr

from sunday_clays.auth.sessions import Role, issue_session, load_session
from sunday_clays.config import Settings

ROTATED_HASH = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("rotated")


def _forge(settings: Settings, payload: object) -> str:
    secret = settings.session_secret.get_secret_value()
    return URLSafeTimedSerializer(secret, salt="sc-session").dumps(payload)


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_issued_token_loads_as_its_role(auth_env: Settings, role: Role) -> None:
    assert load_session(auth_env, issue_session(auth_env, role)) == role


def test_rotating_admin_hash_revokes_admin_sessions_only(auth_env: Settings) -> None:
    viewer_token = issue_session(auth_env, "viewer")
    admin_token = issue_session(auth_env, "admin")
    rotated = auth_env.model_copy(update={"admin_password_hash": SecretStr(ROTATED_HASH)})
    assert load_session(rotated, admin_token) is None
    assert load_session(rotated, viewer_token) == "viewer"


def test_rotating_viewer_hash_revokes_viewer_sessions_only(auth_env: Settings) -> None:
    viewer_token = issue_session(auth_env, "viewer")
    admin_token = issue_session(auth_env, "admin")
    rotated = auth_env.model_copy(update={"viewer_password_hash": SecretStr(ROTATED_HASH)})
    assert load_session(rotated, viewer_token) is None
    assert load_session(rotated, admin_token) == "admin"


@pytest.mark.parametrize(
    ("role", "ttl"), [("viewer", timedelta(days=30)), ("admin", timedelta(hours=12))]
)
def test_token_expires_after_its_role_ttl(auth_env: Settings, role: Role, ttl: timedelta) -> None:
    token = issue_session(auth_env, role)
    issued = datetime.now(UTC)
    assert load_session(auth_env, token, now=issued + ttl - timedelta(minutes=1)) == role
    assert load_session(auth_env, token, now=issued + ttl + timedelta(minutes=1)) is None


def test_token_signed_with_another_secret_is_rejected(auth_env: Settings) -> None:
    other = auth_env.model_copy(update={"session_secret": SecretStr("another-secret-" + "y" * 32)})
    assert load_session(auth_env, issue_session(other, "admin")) is None


@pytest.mark.parametrize("token", ["", "not-a-token", "eyJyIjoiYWRtaW4ifQ.bad.sig"])
def test_garbage_token_is_rejected(auth_env: Settings, token: str) -> None:
    assert load_session(auth_env, token) is None


@pytest.mark.parametrize(
    "payload",
    [["admin"], {"r": "root", "k": "0123456789abcdef"}, {"r": 1, "k": "x"}, {"r": "admin", "k": 7}],
)
def test_signed_but_malformed_payload_is_rejected(auth_env: Settings, payload: object) -> None:
    assert load_session(auth_env, _forge(auth_env, payload)) is None
```

- [ ] **Step 2: Run the session tests to verify they fail**

Run: `uv run pytest tests/unit/auth/test_auth_sessions.py -v`
Expected: ERROR — `ImportError while loading conftest '…/tests/conftest.py'` caused by
`ModuleNotFoundError: No module named 'sunday_clays.auth'` (the conftest imports `sunday_clays.auth.sessions`, so the
whole suite errors until Step 3 creates the module).

- [ ] **Step 3: Implement `auth/__init__.py` and `auth/sessions.py`**

Create `backend/src/sunday_clays/auth/__init__.py`:

```python
"""Authentication: password hashes, signed session cookies, login rate limit, role deps."""
```

Create `backend/src/sunday_clays/auth/sessions.py`:

```python
"""Signed, role-bound session tokens for the ``sc_session`` cookie (C8 Sessions)."""

import hashlib
import hmac
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Final, Literal

from itsdangerous import BadData, URLSafeTimedSerializer

from sunday_clays.config import Settings

Role = Literal["viewer", "admin"]
COOKIE_NAME: Final = "sc_session"
TTL: Final[Mapping[Role, timedelta]] = {
    "viewer": timedelta(days=30),
    "admin": timedelta(hours=12),
}
_ROLES: Final[Mapping[str, Role]] = {"viewer": "viewer", "admin": "admin"}


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret.get_secret_value(), salt="sc-session")


def _fingerprint(settings: Settings, role: Role) -> str:
    """First 16 hex chars of HMAC-SHA256(session_secret, the role's current password hash)."""
    current = settings.admin_password_hash if role == "admin" else settings.viewer_password_hash
    digest = hmac.new(
        settings.session_secret.get_secret_value().encode(),
        current.get_secret_value().encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16]


def issue_session(settings: Settings, role: Role) -> str:
    """Sign ``{r: role, k: fp}``; itsdangerous embeds the signing timestamp."""
    return _serializer(settings).dumps({"r": role, "k": _fingerprint(settings, role)})


def load_session(settings: Settings, token: str, *, now: datetime | None = None) -> Role | None:
    """Return the token's role, or None if forged, expired for its role, or its password rotated."""
    try:
        payload, signed_at = _serializer(settings).loads(token, return_timestamp=True)
    except BadData:
        return None
    if not isinstance(payload, dict):
        return None
    raw_role, fingerprint = payload.get("r"), payload.get("k")
    role = _ROLES.get(raw_role) if isinstance(raw_role, str) else None
    if role is None or not isinstance(fingerprint, str):
        return None
    if (now or datetime.now(UTC)) - signed_at > TTL[role]:
        return None
    if not hmac.compare_digest(fingerprint, _fingerprint(settings, role)):
        return None
    return role
```

- [ ] **Step 4: Run the session tests to verify they pass**

Run: `uv run pytest tests/unit/auth/test_auth_sessions.py -v`
Expected: PASS (14 passed).

- [ ] **Step 5: Write the failing password and hashpw tests**

Create `backend/tests/unit/auth/test_auth_passwords.py`:

```python
import pytest
from argon2 import PasswordHasher, Type, extract_parameters

from sunday_clays.auth.passwords import hash_password, match_role, verify_password
from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings


def test_hash_password_uses_owasp_argon2id_profile() -> None:
    params = extract_parameters(hash_password("correct horse"))
    assert (params.type, params.memory_cost, params.time_cost, params.parallelism) == (
        Type.ID,
        19_456,
        2,
        1,
    )


def test_verify_accepts_right_password_and_rejects_wrong_one() -> None:
    stored = hash_password("correct horse")
    assert verify_password(stored, "correct horse") is True
    assert verify_password(stored, "battery staple") is False


def test_verify_rejects_a_hash_that_is_not_argon2() -> None:
    assert verify_password("plain-text-not-a-hash", "plain-text-not-a-hash") is False


def test_verify_refuses_hash_above_memory_cap() -> None:
    costly = PasswordHasher(time_cost=1, memory_cost=19_457, parallelism=1).hash("pw")
    assert verify_password(costly, "pw") is False


def test_verify_accepts_hash_at_memory_cap() -> None:
    at_cap = PasswordHasher(time_cost=1, memory_cost=19_456, parallelism=1).hash("pw")
    assert verify_password(at_cap, "pw") is True


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_match_role_returns_the_role_whose_password_matches(
    auth_env: Settings, login_passwords: dict[Role, str], role: Role
) -> None:
    assert match_role(auth_env, login_passwords[role]) == role


def test_match_role_returns_none_for_unknown_password(auth_env: Settings) -> None:
    assert match_role(auth_env, "not-a-configured-password") is None
```

Create `backend/tests/unit/auth/test_auth_hashpw.py`:

```python
import getpass
import runpy
import sys

import pytest

from sunday_clays.auth import hashpw
from sunday_clays.auth.passwords import verify_password


def _prompts(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    asked: list[str] = []
    replies = iter(answers)

    def fake_getpass(prompt: str = "Password: ", stream: object = None) -> str:
        asked.append(prompt)
        return next(replies)

    monkeypatch.setattr(getpass, "getpass", fake_getpass)
    return asked


def test_prints_a_verifiable_hash_after_confirmation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    asked = _prompts(monkeypatch, "s3cret-pass", "s3cret-pass")
    assert hashpw.main([]) == 0
    printed = capsys.readouterr().out.strip()
    assert len(asked) == 2
    assert printed.startswith("$argon2id$")
    assert verify_password(printed, "s3cret-pass") is True


def test_mismatched_confirmation_prints_nothing_and_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prompts(monkeypatch, "s3cret-pass", "s3cret-pasS")
    assert hashpw.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "do not match" in captured.err


def test_empty_password_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prompts(monkeypatch, "", "")
    assert hashpw.main([]) == 1
    assert capsys.readouterr().out == ""


def test_password_on_the_command_line_is_rejected_before_prompting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _prompts(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        hashpw.main(["hunter2"])
    assert exc.value.code == 2
    assert asked == []


def test_module_entry_point_runs_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prompts(monkeypatch, "entry-pass", "entry-pass")
    monkeypatch.setattr(sys, "argv", ["hashpw"])
    monkeypatch.delitem(sys.modules, "sunday_clays.auth.hashpw")
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sunday_clays.auth.hashpw", run_name="__main__")
    assert exc.value.code == 0
    assert verify_password(capsys.readouterr().out.strip(), "entry-pass") is True
```

- [ ] **Step 6: Run them to verify they fail**

Run: `uv run pytest tests/unit/auth/test_auth_passwords.py tests/unit/auth/test_auth_hashpw.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.auth.passwords'` and
`ImportError: cannot import name 'hashpw' from 'sunday_clays.auth'`.

- [ ] **Step 7: Implement `auth/passwords.py` and `auth/hashpw.py`**

Create `backend/src/sunday_clays/auth/passwords.py`:

```python
"""argon2id password hashing and verification."""

import logging
from typing import Final

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError

from sunday_clays.auth.sessions import Role
from sunday_clays.config import Settings

log = logging.getLogger(__name__)

# OWASP argon2id profile; scripts/dev-secrets.sh (Plan 01 T4) uses the same parameters.
MEMORY_COST_KIB: Final = 19_456
TIME_COST: Final = 2
PARALLELISM: Final = 1
# verify() runs with the parameters stored in the hash; refuse any hash that would cost more
# memory than hashpw produces, so the 4 concurrent verifies of routes/auth.py stay near 80 MiB.
MAX_VERIFY_MEMORY_KIB: Final = MEMORY_COST_KIB

_HASHER: Final = PasswordHasher(
    time_cost=TIME_COST, memory_cost=MEMORY_COST_KIB, parallelism=PARALLELISM, type=Type.ID
)


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        params = extract_parameters(password_hash)
    except InvalidHashError:
        log.error("configured password hash is not a valid argon2 hash")
        return False
    if params.memory_cost > MAX_VERIFY_MEMORY_KIB:
        log.error(
            "configured password hash needs %d KiB (cap %d KiB); regenerate it with hashpw",
            params.memory_cost,
            MAX_VERIFY_MEMORY_KIB,
        )
        return False
    try:
        return _HASHER.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def match_role(settings: Settings, password: str) -> Role | None:
    """Admin is checked first, so a password matching both hashes logs in as admin."""
    if verify_password(settings.admin_password_hash.get_secret_value(), password):
        return "admin"
    if verify_password(settings.viewer_password_hash.get_secret_value(), password):
        return "viewer"
    return None
```

Create `backend/src/sunday_clays/auth/hashpw.py`:

```python
"""Print an argon2id hash for VIEWER_PASSWORD_HASH / ADMIN_PASSWORD_HASH.

Usage: ``python -m sunday_clays.auth.hashpw``. The password is read twice from the terminal
with getpass and is never accepted on the command line.
"""

import argparse
import getpass
import sys
from collections.abc import Sequence

from sunday_clays.auth.passwords import hash_password


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sunday_clays.auth.hashpw",
        description="Print an argon2id hash of a password typed at the prompt.",
    )
    parser.parse_args(argv)
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("error: the password is empty", file=sys.stderr)
        return 1
    if password != confirm:
        print("error: the passwords do not match", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Run them to verify they pass**

Run: `uv run pytest tests/unit/auth/test_auth_passwords.py tests/unit/auth/test_auth_hashpw.py -v`
Expected: PASS (13 passed).

- [ ] **Step 9: Write the failing rate-limit tests**

Create `backend/tests/integration/auth/test_login_rate_limit.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import is_limited, record_attempt
from sunday_clays.config import Settings
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["login_attempts"]


def _failures(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at, "success": False}] * n)


def test_limited_from_the_tenth_failure_in_window(session: Session, auth_env: Settings) -> None:
    _failures(session, "203.0.113.7", 9)
    assert is_limited(session, "203.0.113.7") is False
    _failures(session, "203.0.113.7", 1)
    assert is_limited(session, "203.0.113.7") is True


def test_failures_outside_the_window_do_not_count(session: Session, auth_env: Settings) -> None:
    _failures(session, "203.0.113.7", 10, age=timedelta(minutes=16))
    assert is_limited(session, "203.0.113.7") is False
    _failures(session, "203.0.113.7", 10, age=timedelta(minutes=14))
    assert is_limited(session, "203.0.113.7") is True


def test_successes_and_other_ips_do_not_count(session: Session, auth_env: Settings) -> None:
    now = datetime.now(UTC)
    session.execute(insert(ATTEMPTS), [{"ip": "203.0.113.7", "at": now, "success": True}] * 10)
    _failures(session, "198.51.100.1", 10)
    assert is_limited(session, "203.0.113.7") is False


def test_record_attempt_inserts_and_prunes_rows_older_than_a_day(
    session: Session, auth_env: Settings
) -> None:
    _failures(session, "198.51.100.1", 1, age=timedelta(hours=25))
    _failures(session, "198.51.100.1", 1, age=timedelta(hours=23))
    record_attempt(session, "203.0.113.7", True)
    rows = session.execute(select(ATTEMPTS.c.ip, ATTEMPTS.c.success).order_by(ATTEMPTS.c.id)).all()
    assert [tuple(r) for r in rows] == [("198.51.100.1", False), ("203.0.113.7", True)]
```

- [ ] **Step 10: Run them to verify they fail**

Run: `uv run pytest tests/integration/auth/test_login_rate_limit.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.auth.ratelimit'`.

- [ ] **Step 11: Implement `auth/ratelimit.py`**

Create `backend/src/sunday_clays/auth/ratelimit.py`:

```python
"""Failed-login rate limit per client-IP bucket, stored in ``login_attempts`` (C4, C8)."""

from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import Table, delete, func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base

PRUNE_AFTER: Final = timedelta(days=1)


def _attempts() -> Table:
    return Base.metadata.tables["login_attempts"]


def is_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already has ``login_max_failures`` failures in the login window."""
    settings = get_settings()
    t = _attempts()
    since = datetime.now(UTC) - timedelta(minutes=settings.login_window_minutes)
    failures = session.scalar(
        select(func.count())
        .select_from(t)
        .where(t.c.ip == ip, t.c.success.is_(False), t.c.at > since)
    )
    return (failures or 0) >= settings.login_max_failures


def record_attempt(session: Session, ip: str, success: bool) -> None:
    """Insert one attempt and prune rows older than a day, inside the caller's transaction."""
    t = _attempts()
    now = datetime.now(UTC)
    session.execute(insert(t).values(ip=ip, at=now, success=success))
    session.execute(delete(t).where(t.c.at < now - PRUNE_AFTER))
```

- [ ] **Step 12: Run them to verify they pass**

Run: `uv run pytest tests/integration/auth/test_login_rate_limit.py -v`
Expected: PASS (4 passed).

- [ ] **Step 13: Write the failing `client_ip`, audit and `ensure_exists` tests**

Create `backend/tests/unit/auth/test_auth_client_ip.py`:

```python
import pytest
from starlette.requests import Request

from sunday_clays.auth.deps import client_ip


def _request(headers: dict[str, str], peer: str | None) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 50000) if peer is not None else None,
    }
    return Request(scope)


@pytest.mark.parametrize(
    ("headers", "peer", "expected"),
    [
        ({"X-Real-IP": "203.0.113.7"}, "172.18.0.5", "203.0.113.7"),
        ({}, "172.18.0.5", "172.18.0.5"),
        ({"X-Forwarded-For": "198.51.100.1"}, "172.18.0.5", "172.18.0.5"),
        ({"X-Real-IP": "2001:db8:1:2:3:4:5:6"}, "172.18.0.5", "2001:db8:1:2::/64"),
        ({"X-Real-IP": "::ffff:198.51.100.9"}, "172.18.0.5", "198.51.100.9"),
        ({"X-Real-IP": "not-an-ip"}, "172.18.0.5", "172.18.0.5"),
        ({}, "testclient", "testclient"),
        ({}, None, "unknown"),
    ],
)
def test_client_ip(headers: dict[str, str], peer: str | None, expected: str) -> None:
    assert client_ip(_request(headers, peer)) == expected
```

Create `backend/tests/integration/auth/test_audit_helpers.py`:

```python
from datetime import date

import pytest
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import ensure_exists
from sunday_clays.auth.deps import record_audit
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
SHOOTERS = Base.metadata.tables["shooters"]


def test_record_audit_appends_json_encoded_row(session: Session) -> None:
    record_audit(
        session, "203.0.113.7", "admin", "rules.create", {"event_date": date(2026, 9, 13), "n": 2}
    )
    row = session.execute(select(AUDIT.c.ip, AUDIT.c.role, AUDIT.c.action, AUDIT.c.details)).one()
    assert tuple(row) == (
        "203.0.113.7",
        "admin",
        "rules.create",
        {"event_date": "2026-09-13", "n": 2},
    )


def test_ensure_exists_passes_for_existing_row(session: Session) -> None:
    shooter_id = session.execute(
        insert(SHOOTERS).values(display_name="Hadley, Ike").returning(SHOOTERS.c.id)
    ).scalar_one()
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")


def test_ensure_exists_raises_not_found_with_code(session: Session) -> None:
    with pytest.raises(NotFoundError) as exc:
        ensure_exists(session, "shooters", 987_654, "shooter_not_found", "Shooter")
    assert exc.value.code == "shooter_not_found"
    assert exc.value.status_code == 404
```

- [ ] **Step 14: Run them to verify they fail**

Run: `uv run pytest tests/unit/auth/test_auth_client_ip.py tests/integration/auth/test_audit_helpers.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.auth.deps'` and
`ModuleNotFoundError: No module named 'sunday_clays.api.routes._admin'`.

- [ ] **Step 15: Implement `auth/deps.py` and `api/routes/_admin.py`**

Create `backend/src/sunday_clays/auth/deps.py`:

```python
"""Role dependencies, client-IP bucketing and the audit helper (C8)."""

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

from fastapi import Depends, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import insert
from sqlalchemy.orm import Session

from sunday_clays.auth.sessions import COOKIE_NAME, Role, load_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.domain.errors import DomainError
from sunday_clays.models import Base


class NotAuthenticatedError(DomainError):
    status_code: ClassVar[int] = 401


class ForbiddenError(DomainError):
    status_code: ClassVar[int] = 403


class TooManyRequestsError(DomainError):
    status_code: ClassVar[int] = 429


def _bucket(value: str | None) -> str | None:
    """Normalize an IP; IPv6 collapses to its /64, IPv4-mapped IPv6 to the IPv4 address."""
    if not value:
        return None
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def client_ip(request: Request) -> str:
    """X-Real-IP (always set by Caddy) else the TCP peer; X-Forwarded-For is never read."""
    peer = request.client.host if request.client is not None else None
    return _bucket(request.headers.get("x-real-ip")) or _bucket(peer) or peer or "unknown"


def current_role(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> Role | None:
    token = request.cookies.get(COOKIE_NAME)
    return load_session(settings, token) if token else None


def require_viewer(role: Annotated[Role | None, Depends(current_role)]) -> Role:
    if role is None:
        raise NotAuthenticatedError("unauthenticated", "Log in to continue")
    return role


def require_admin(role: Annotated[Role, Depends(require_viewer)]) -> Role:
    if role != "admin":
        raise ForbiddenError("forbidden", "Admin access required")
    return role


@dataclass(frozen=True)
class Actor:
    role: Role
    ip: str


def admin_actor(request: Request, role: Annotated[Role, Depends(require_admin)]) -> Actor:
    return Actor(role=role, ip=client_ip(request))


def record_audit(
    session: Session, ip: str | None, role: str, action: str, details: Mapping[str, Any]
) -> None:
    """Append one ``audit_log`` row in the caller's transaction (dates/enums JSON-encoded)."""
    audit_log = Base.metadata.tables["audit_log"]
    session.execute(
        insert(audit_log).values(
            ip=ip, role=role, action=action, details=jsonable_encoder(dict(details))
        )
    )
```

Create `backend/src/sunday_clays/api/routes/_admin.py`:

```python
"""Helpers shared by the admin_* route modules (leading underscore: skipped by discovery)."""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.domain.errors import NotFoundError
from sunday_clays.models import Base


class JobRefOut(BaseModel):
    job_id: int


def ensure_exists(session: Session, table: str, row_id: int, code: str, noun: str) -> None:
    """Raise NotFoundError(code) → 404 unless ``table`` has a row with ``id == row_id``."""
    t = Base.metadata.tables[table]
    if session.scalar(select(t.c.id).where(t.c.id == row_id)) is None:
        raise NotFoundError(code, f"{noun} {row_id} does not exist")
```

- [ ] **Step 16: Run them to verify they pass**

Run: `uv run pytest tests/unit/auth/test_auth_client_ip.py tests/integration/auth/test_audit_helpers.py -v`
Expected: PASS (11 passed).

- [ ] **Step 17: Write the failing CSRF middleware tests**

Create `backend/tests/unit/api/test_csrf_middleware.py`:

```python
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sunday_clays.api.csrf import CsrfGuardMiddleware

SITE = "sundayclays.claysmasher.com"


@pytest.fixture
def guarded() -> Iterator[TestClient]:
    app = FastAPI()

    @app.post("/api/echo")
    def echo_post() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/echo")
    def echo_get() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(CsrfGuardMiddleware)
    with TestClient(app) as test_client:  # lifespan scope also passes through the middleware
        yield test_client


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": SITE, "Origin": "https://shop.claysmasher.com"},
        {"Host": "localhost:8080", "Origin": "http://localhost:3000"},
        {"Host": SITE, "Origin": "null"},
        {"Host": SITE, "Origin": "not a url"},
        {"Host": SITE, "Origin": "http://[::1"},
        {"Host": SITE, "Sec-Fetch-Site": "same-site"},
        {"Host": SITE, "Sec-Fetch-Site": "cross-site"},
        {"Host": SITE, "Origin": f"https://{SITE}", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_post_is_blocked(guarded: TestClient, headers: dict[str, str]) -> None:
    response = guarded.post("/api/echo", headers=headers)
    assert response.status_code == 403
    assert response.json() == {"error": {"code": "csrf", "message": "Cross-site request blocked"}}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Host": "localhost:8080", "Origin": "http://localhost:8080"},
        {"Host": SITE, "Origin": "https://SundayClays.ClaySmasher.com"},
        {"Host": SITE, "Origin": f"https://{SITE}", "Sec-Fetch-Site": "same-origin"},
        {"Host": SITE, "Sec-Fetch-Site": "none"},
    ],
)
def test_same_origin_or_headerless_post_passes(
    guarded: TestClient, headers: dict[str, str]
) -> None:
    assert guarded.post("/api/echo", headers=headers).status_code == 200


def test_get_with_foreign_origin_passes(guarded: TestClient) -> None:
    headers = {"Host": SITE, "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}
    assert guarded.get("/api/echo", headers=headers).status_code == 200


def test_delete_with_foreign_origin_is_blocked_before_routing(guarded: TestClient) -> None:
    headers = {"Host": SITE, "Origin": "https://evil.example"}
    assert guarded.delete("/api/echo", headers=headers).status_code == 403
```

- [ ] **Step 18: Run them to verify they fail**

Run: `uv run pytest tests/unit/api/test_csrf_middleware.py -v`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'sunday_clays.api.csrf'`.

- [ ] **Step 19: Implement `api/csrf.py`**

Create `backend/src/sunday_clays/api/csrf.py`:

```python
"""Block cross-site state-changing requests before routing (C8 CSRF). Pure ASGI."""

from typing import Final
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})
ALLOWED_FETCH_SITES: Final = frozenset({"same-origin", "none"})


def is_cross_site(method: str, headers: Headers) -> bool:
    if method in SAFE_METHODS:
        return False
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None and fetch_site.lower() not in ALLOWED_FETCH_SITES:
        return True
    origin = headers.get("origin")
    if origin is None:
        return False
    try:
        netloc = urlsplit(origin).netloc.lower()
    except ValueError:
        return True
    return not netloc or netloc != headers.get("host", "").lower()


class CsrfGuardMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and is_cross_site(scope["method"], Headers(scope=scope)):
            response = JSONResponse(
                {"error": {"code": "csrf", "message": "Cross-site request blocked"}},
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
```

- [ ] **Step 20: Run them to verify they pass**

Run: `uv run pytest tests/unit/api/test_csrf_middleware.py -v`
Expected: PASS (15 passed).

- [ ] **Step 21: Write the failing auth route tests**

Create `backend/tests/integration/api/test_auth_routes.py`:

```python
import threading
import time

import pytest
from fastapi.testclient import TestClient
from itsdangerous.timed import TimestampSigner
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.api.routes import auth as auth_routes
from sunday_clays.auth.sessions import COOKIE_NAME, Role, issue_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["login_attempts"]
AUDIT = Base.metadata.tables["audit_log"]
WRONG = {"password": "definitely-wrong"}


@pytest.mark.parametrize(("role", "max_age"), [("viewer", 2_592_000), ("admin", 43_200)])
def test_login_sets_role_cookie_and_me_reports_role(
    anon_client: TestClient, login_passwords: dict[Role, str], role: Role, max_age: int
) -> None:
    response = anon_client.post("/api/auth/login", json={"password": login_passwords[role]})
    assert response.status_code == 200
    assert response.json() == {"role": role}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert f"Max-Age={max_age}" in cookie
    assert "Secure" not in cookie
    assert anon_client.get("/api/auth/me").json() == {"role": role}


def test_login_cookie_secure_when_enabled(
    anon_client: TestClient,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    response = anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    assert "; Secure" in response.headers["set-cookie"]


def test_admin_login_is_audited(
    anon_client: TestClient, login_passwords: dict[Role, str], session: Session
) -> None:
    anon_client.post(
        "/api/auth/login",
        json={"password": login_passwords["admin"]},
        headers={"X-Real-IP": "203.0.113.7"},
    )
    rows = session.execute(select(AUDIT.c.ip, AUDIT.c.role, AUDIT.c.action)).all()
    assert [tuple(r) for r in rows] == [("203.0.113.7", "admin", "auth.login")]


def test_me_without_cookie_is_401(anon_client: TestClient) -> None:
    response = anon_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_wrong_password_is_401(anon_client: TestClient) -> None:
    response = anon_client.post("/api/auth/login", json=WRONG)
    assert response.status_code == 401
    assert response.json() == {"error": {"code": "invalid_password", "message": "Wrong password"}}
    assert "set-cookie" not in response.headers


def test_failed_attempt_row_persists_after_401(anon_client: TestClient, session: Session) -> None:
    anon_client.post("/api/auth/login", json=WRONG, headers={"X-Real-IP": "198.51.100.23"})
    rows = session.execute(select(ATTEMPTS.c.ip, ATTEMPTS.c.success)).all()
    assert [tuple(r) for r in rows] == [("198.51.100.23", False)]


def test_eleventh_failure_returns_429(
    anon_client: TestClient,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(10):
        assert anon_client.post("/api/auth/login", json=WRONG).status_code == 401
    verifies: list[str] = []
    real_match_role = auth_routes.match_role

    def counting_match_role(settings: Settings, password: str) -> Role | None:
        verifies.append(password)
        return real_match_role(settings, password)

    monkeypatch.setattr(auth_routes, "match_role", counting_match_role)
    response = anon_client.post("/api/auth/login", json={"password": login_passwords["admin"]})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert verifies == []  # limited before any argon2 work


def test_rate_limit_ignores_spoofed_x_forwarded_for(anon_client: TestClient) -> None:
    for i in range(10):
        spoofed = {"X-Forwarded-For": f"192.0.2.{i}"}
        assert anon_client.post("/api/auth/login", json=WRONG, headers=spoofed).status_code == 401
    spoofed = {"X-Forwarded-For": "192.0.2.200"}
    assert anon_client.post("/api/auth/login", json=WRONG, headers=spoofed).status_code == 429


def test_rate_limit_buckets_by_x_real_ip(anon_client: TestClient) -> None:
    first = {"X-Real-IP": "203.0.113.10"}
    second = {"X-Real-IP": "203.0.113.11"}
    for _ in range(10):
        assert anon_client.post("/api/auth/login", json=WRONG, headers=first).status_code == 401
    assert anon_client.post("/api/auth/login", json=WRONG, headers=first).status_code == 429
    assert anon_client.post("/api/auth/login", json=WRONG, headers=second).status_code == 401


def test_ipv6_bucketed_by_64(anon_client: TestClient) -> None:
    same_64 = ["2001:db8:0:1::a", "2001:db8:0:1:ffff:ffff:ffff:fffe"]
    for i in range(10):
        headers = {"X-Real-IP": same_64[i % 2]}
        assert anon_client.post("/api/auth/login", json=WRONG, headers=headers).status_code == 401
    neighbour = {"X-Real-IP": "2001:db8:0:1::77"}
    other_64 = {"X-Real-IP": "2001:db8:0:2::a"}
    assert anon_client.post("/api/auth/login", json=WRONG, headers=neighbour).status_code == 429
    assert anon_client.post("/api/auth/login", json=WRONG, headers=other_64).status_code == 401


def test_login_returns_429_when_no_verify_slot_frees_up(
    anon_client: TestClient,
    login_passwords: dict[Role, str],
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
) -> None:
    exhausted = threading.BoundedSemaphore(1)
    exhausted.acquire()
    monkeypatch.setattr(auth_routes, "_VERIFY_SLOTS", exhausted)
    monkeypatch.setattr(auth_routes, "VERIFY_ACQUIRE_TIMEOUT_S", 0.01)
    response = anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "login_busy"
    assert session.execute(select(ATTEMPTS.c.id)).all() == []


def test_verify_slots_are_released_after_each_login(
    anon_client: TestClient, login_passwords: dict[Role, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    slots = threading.BoundedSemaphore(4)
    monkeypatch.setattr(auth_routes, "_VERIFY_SLOTS", slots)
    anon_client.post("/api/auth/login", json=WRONG)
    anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    taken = [slots.acquire(blocking=False) for _ in range(4)]
    assert taken == [True, True, True, True]


def test_logout_clears_cookie(anon_client: TestClient, login_passwords: dict[Role, str]) -> None:
    anon_client.post("/api/auth/login", json={"password": login_passwords["viewer"]})
    response = anon_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert anon_client.get("/api/auth/me").status_code == 401


def test_expired_admin_token_rejected_regardless_of_cookie_max_age(
    anon_client: TestClient, auth_env: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    thirteen_hours_ago = int(time.time()) - 13 * 3600
    with monkeypatch.context() as m:
        m.setattr(TimestampSigner, "get_timestamp", lambda self: thirteen_hours_ago)
        old_admin = issue_session(auth_env, "admin")
        old_viewer = issue_session(auth_env, "viewer")
    anon_client.cookies.set(COOKIE_NAME, old_admin)
    assert anon_client.get("/api/auth/me").status_code == 401
    anon_client.cookies.set(COOKIE_NAME, old_viewer)
    assert anon_client.get("/api/auth/me").json() == {"role": "viewer"}


def test_cross_site_upload_with_admin_cookie_is_blocked(admin_client: TestClient) -> None:
    response = admin_client.post(
        "/api/admin/imports",
        files={"file": ("scores.xlsx", b"PK\x03\x04", "application/octet-stream")},
        headers={"Origin": "https://shop.claysmasher.com", "Host": "sundayclays.claysmasher.com"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf"
```

- [ ] **Step 22: Run them to verify they fail**

Run: `uv run pytest tests/integration/api/test_auth_routes.py -v`
Expected: collection ERROR — `ImportError: cannot import name 'auth' from 'sunday_clays.api.routes'`.

- [ ] **Step 23: Implement `api/routes/auth.py`**

Create `backend/src/sunday_clays/api/routes/auth.py`:

```python
"""POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me (C8)."""

import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import (
    NotAuthenticatedError,
    TooManyRequestsError,
    client_ip,
    record_audit,
    require_viewer,
)
from sunday_clays.auth.passwords import match_role
from sunday_clays.auth.ratelimit import is_limited, record_attempt
from sunday_clays.auth.sessions import COOKIE_NAME, TTL, Role, issue_session
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

# At most 4 argon2 verifies (~19 MiB each) run at once; a request waits up to 5 s for a slot.
_VERIFY_SLOTS = threading.BoundedSemaphore(4)
VERIFY_ACQUIRE_TIMEOUT_S = 5.0


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class RoleOut(BaseModel):
    role: Role


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session, scope="function")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RoleOut:
    ip = client_ip(request)
    if is_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many failed logins. Try again later.")
    if not _VERIFY_SLOTS.acquire(timeout=VERIFY_ACQUIRE_TIMEOUT_S):
        raise TooManyRequestsError("login_busy", "The server is busy. Try again in a moment.")
    try:
        role = match_role(settings, body.password)
    finally:
        _VERIFY_SLOTS.release()
    record_attempt(session, ip, role is not None)
    if role is None:
        session.commit()  # get_session rolls back on any exception; keep the failure row
        raise NotAuthenticatedError("invalid_password", "Wrong password")
    if role == "admin":
        record_audit(session, ip, role, "auth.login", {})
    response.set_cookie(
        COOKIE_NAME,
        issue_session(settings, role),
        max_age=int(TTL[role].total_seconds()),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return RoleOut(role=role)


@router.post("/logout", status_code=204)
def logout(response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict"
    )


@router.get("/me")
def me(role: Annotated[Role, Depends(require_viewer)]) -> RoleOut:
    return RoleOut(role=role)
```

- [ ] **Step 24: Run the auth route tests**

Run: `uv run pytest tests/integration/api/test_auth_routes.py -v`
Expected: 15 passed, 1 FAILED — `test_cross_site_upload_with_admin_cookie_is_blocked` with `assert 404 == 403` (the
CSRF middleware is not installed yet; Step 27 installs it).

- [ ] **Step 25: Write the role-wiring test and the runtime route matrix**

Create `backend/tests/unit/api/test_role_wiring.py`:

```python
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel

from sunday_clays.api import app as app_module
from sunday_clays.auth.deps import Actor, admin_actor
from sunday_clays.auth.sessions import COOKIE_NAME, Role, issue_session
from sunday_clays.config import Settings


class ProbeOut(BaseModel):
    who: str


def _probe_routers() -> list[tuple[str, APIRouter]]:
    """Probe routes; only /api/admin/actor-probe declares an auth dependency of its own.

    The other three rely on create_app()'s wiring alone, so a wrong role choice fails a test.
    All are POST (Decision D24): Plan 06's ETag middleware reads the DB for eligible GETs, and a
    TestClient POST carries no Origin, so the CSRF guard lets it through.
    """
    admin, viewer, public = APIRouter(), APIRouter(), APIRouter()

    @admin.post("/api/admin/probe")
    def admin_probe() -> ProbeOut:
        return ProbeOut(who="admin-route")

    @admin.post("/api/admin/actor-probe")
    def admin_actor_probe(actor: Annotated[Actor, Depends(admin_actor)]) -> ProbeOut:
        return ProbeOut(who=f"{actor.role}@{actor.ip}")

    @viewer.post("/api/probe")
    def viewer_probe() -> ProbeOut:
        return ProbeOut(who="viewer-route")

    @public.post("/api/public-probe")
    def public_probe() -> ProbeOut:
        return ProbeOut(who="public-route")

    return [("admin_probe", admin), ("health", public), ("probe", viewer)]


@pytest.fixture
def probe_client(monkeypatch: pytest.MonkeyPatch, auth_env: Settings) -> TestClient:
    monkeypatch.setattr(app_module, "discover_routers", _probe_routers)
    return TestClient(app_module.create_app())


def _as(test_client: TestClient, settings: Settings, role: Role | None) -> TestClient:
    test_client.cookies.clear()
    if role is not None:
        test_client.cookies.set(COOKIE_NAME, issue_session(settings, role))
    return test_client


@pytest.mark.parametrize(
    ("role", "admin_status", "viewer_status", "public_status"),
    [(None, 401, 401, 200), ("viewer", 403, 200, 200), ("admin", 200, 200, 200)],
)
def test_module_name_decides_required_role(
    probe_client: TestClient,
    auth_env: Settings,
    role: Role | None,
    admin_status: int,
    viewer_status: int,
    public_status: int,
) -> None:
    client = _as(probe_client, auth_env, role)
    assert client.post("/api/admin/probe").status_code == admin_status
    assert client.post("/api/probe").status_code == viewer_status
    assert client.post("/api/public-probe").status_code == public_status


def test_admin_actor_carries_role_and_bucketed_ip(
    probe_client: TestClient, auth_env: Settings
) -> None:
    client = _as(probe_client, auth_env, "admin")
    response = client.post("/api/admin/actor-probe", headers={"X-Real-IP": "2001:db8:5:6::9"})
    assert response.json() == {"who": "admin@2001:db8:5:6::/64"}


def test_denials_use_the_error_envelope(probe_client: TestClient, auth_env: Settings) -> None:
    assert _as(probe_client, auth_env, None).post("/api/probe").json() == {
        "error": {"code": "unauthenticated", "message": "Log in to continue"}
    }
    assert _as(probe_client, auth_env, "viewer").post("/api/admin/probe").json() == {
        "error": {"code": "forbidden", "message": "Admin access required"}
    }
```

Create `backend/tests/integration/api/test_route_auth_matrix.py`:

```python
"""Every route's auth requirement, enumerated from the live app (C2, C8).

Walks the effective routes of ``create_app()`` at runtime, so routers added by later
waves are covered without editing this file.
"""

from datetime import date
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient

from sunday_clays.api.routes import discover_routers
from sunday_clays.db import get_session

PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout")}


def _calls(app: FastAPI) -> list[tuple[str, str, str]]:
    """(method, path template, concrete url) for every API route the app serves."""
    calls: list[tuple[str, str, str]] = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if not isinstance(route, APIRoute) or context.path_format is None:
            continue
        values = {
            param.alias: "2026-09-13" if param.field_info.annotation is date else "1"
            for param in route.dependant.path_params
        }
        url = context.path_format.format(**values)
        calls.extend((method, context.path_format, url) for method in sorted(context.methods or ()))
    return calls


def test_walk_sees_the_auth_routes(anon_client: TestClient) -> None:
    seen = {(method, path) for method, path, _ in _calls(cast(FastAPI, anon_client.app))}
    assert {("GET", "/api/auth/me"), *PUBLIC} <= seen


def test_every_session_dependency_is_function_scoped(anon_client: TestClient) -> None:
    """C2 amendment: a request-scoped get_session commits after the response is sent."""
    wrong: list[str] = []

    def walk(dependant: Dependant, where: str) -> None:
        for sub in dependant.dependencies:
            if sub.call is get_session and sub.scope != "function":
                wrong.append(f"{where}: get_session scope={sub.scope!r}")
            walk(sub, where)

    for route in cast(FastAPI, anon_client.app).routes:
        if isinstance(route, APIRoute):
            walk(route.dependant, f"{sorted(route.methods)} {route.path}")
    assert wrong == []


@pytest.mark.parametrize("extra_headers", [{}, {"If-None-Match": "*"}])
def test_every_route_needs_a_session_except_public(
    anon_client: TestClient, extra_headers: dict[str, str]
) -> None:
    wrong: list[str] = []
    for method, path, url in _calls(cast(FastAPI, anon_client.app)):
        status = anon_client.request(method, url, headers=extra_headers).status_code
        public = (method, path) in PUBLIC
        if (public and status == 401) or (not public and status != 401):
            wrong.append(f"{method} {path} -> {status}")
    assert wrong == []


def test_viewer_gets_403_on_every_admin_route(
    anon_client: TestClient, viewer_client: TestClient
) -> None:
    wrong: list[str] = []
    for method, path, url in _calls(cast(FastAPI, anon_client.app)):
        if path.startswith("/api/admin/"):
            status = viewer_client.request(method, url).status_code
            if status != 403:
                wrong.append(f"{method} {path} -> {status}")
    assert wrong == []


def test_admin_paths_are_defined_only_in_admin_modules(anon_client: TestClient) -> None:
    from_admin_modules: set[tuple[str, str]] = set()
    misplaced: list[str] = []
    for module_name, router in discover_routers():
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            if module_name.startswith("admin_"):
                from_admin_modules |= {(m, route.path_format) for m in route.methods}
            elif route.path_format.startswith("/api/admin"):
                misplaced.append(f"{module_name}: {route.path_format}")
    served = [
        (m, p) for m, p, _ in _calls(cast(FastAPI, anon_client.app)) if p.startswith("/api/admin")
    ]
    assert misplaced == []
    assert [call for call in served if call not in from_admin_modules] == []
```

- [ ] **Step 26: Run them to verify the wiring test fails**

Run: `uv run pytest tests/unit/api/test_role_wiring.py tests/integration/api/test_route_auth_matrix.py -v`
Expected: `test_role_wiring.py` 3 FAILED, 2 passed — `test_module_name_decides_required_role[None-401-401-200]`
(`assert 200 == 401`), `[viewer-403-200-200]` (`assert 200 == 403`) and `test_denials_use_the_error_envelope`
(`/api/probe` answers `{"who": "viewer-route"}`), because every discovered router is still public and none of the
three probes guards itself. The 2 passes are `[admin-200-200-200]` and `test_admin_actor_carries_role_and_bucketed_ip`
(`/api/admin/actor-probe` depends on `admin_actor` itself). `[viewer-403-200-200]` is the check that fails if
`role_dependencies` ever gives `admin_*` modules `require_viewer` instead of `require_admin`.
`test_route_auth_matrix.py` already PASSES (6 passed): only the `health` and
`auth` routers exist in this task and `/api/auth/me` guards itself; from Tasks 2 and 3 on, the same tests check every
admin and viewer route without edits.

- [ ] **Step 27: Wire role dependencies and the CSRF middleware in `create_app()` (the one-time C2 edit)**

In `backend/src/sunday_clays/api/app.py`:
1. Make sure `discover_routers` is imported by name (the wiring test patches `sunday_clays.api.app.discover_routers`)
   and add the new imports:

```python
from typing import Any, Final

from fastapi import Depends, FastAPI

from sunday_clays.api.csrf import CsrfGuardMiddleware
from sunday_clays.api.routes import discover_routers
from sunday_clays.auth.deps import require_admin, require_viewer
```

2. Add these module-level definitions above `create_app()`:

```python
PUBLIC_ROUTE_MODULES: Final = frozenset({"health", "auth"})


def role_dependencies(module_name: str) -> list[Any]:
    """C2: ``health``/``auth`` are public, ``admin_*`` need admin, all other modules a viewer."""
    if module_name in PUBLIC_ROUTE_MODULES:
        return []
    if module_name.startswith("admin_"):
        return [Depends(require_admin)]
    return [Depends(require_viewer)]
```

3. Inside `create_app()`, replace Plan 01 T1's router loop with the one below (no `prefix`, Decision D1) and add the
   CSRF middleware on the line directly after Plan 01 T1's `app.add_middleware(BodySizeLimitMiddleware)`. Every other
   line of `create_app()` (the `FastAPI(docs_url=None, redoc_url=None, openapi_url=None, …)` call, exception handlers,
   the body-limit middleware) stays as Plan 01 T1 wrote it:

```python
    for name, router in discover_routers():
        app.include_router(router, dependencies=role_dependencies(name))
```

```python
    app.add_middleware(CsrfGuardMiddleware)
```

- [ ] **Step 28: Run every auth test to verify they pass**

Run: `uv run pytest tests/unit/auth tests/unit/api tests/integration/auth tests/integration/api -v`
Expected: PASS — including `test_role_wiring.py` (5 passed), `test_route_auth_matrix.py` (6 passed) and
`test_cross_site_upload_with_admin_cookie_is_blocked` (403 from the middleware before routing), plus the Plan 01 tests
in those folders (`test_export_openapi_without_env` still passes: `create_app()` reads no settings).

- [ ] **Step 29: Confirm the e2e storage states are ignored and add the Playwright `setup` project**

Plan 01 T4 already ignores the storage states with the root `.gitignore` line `**/e2e/.auth/` (Decision D20); do not
edit `.gitignore`. Verify from the repo root: `git check-ignore -v frontend/e2e/.auth/viewer.json`
Expected: `.gitignore:<line>:**/e2e/.auth/	frontend/e2e/.auth/viewer.json` (exit 0). `git check-ignore -v` names the
last matching pattern, which is Plan 01 T4's `**/e2e/.auth/` line.

Create `frontend/e2e/authState.ts`:

```ts
/** Storage-state files written by the `setup` project (e2e/auth.setup.ts); gitignored. */
export const VIEWER_STATE = 'e2e/.auth/viewer.json';
export const ADMIN_STATE = 'e2e/.auth/admin.json';

/** The e2e login passwords, exported by CI (C11 `e2e` job) or by hand for a local run. */
export function e2ePassword(role: 'viewer' | 'admin'): string {
  const name = role === 'viewer' ? 'E2E_VIEWER_PASSWORD' : 'E2E_ADMIN_PASSWORD';
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set for the e2e run`);
  return value;
}
```

Create `frontend/e2e/auth.setup.ts`:

```ts
import { expect, test as setup } from '@playwright/test';

import { ADMIN_STATE, VIEWER_STATE, e2ePassword } from './authState';

setup('log in as viewer', async ({ request }) => {
  const response = await request.post('/api/auth/login', {
    data: { password: e2ePassword('viewer') },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: 'viewer' });
  await request.storageState({ path: VIEWER_STATE });
});

setup('log in as admin', async ({ request }) => {
  const response = await request.post('/api/auth/login', {
    data: { password: e2ePassword('admin') },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: 'admin' });
  await request.storageState({ path: ADMIN_STATE });
});
```

Create `frontend/e2e/auth.spec.ts`:

```ts
import { e2ePassword } from './authState';
import { expect, test } from './fixtures';

// API-level auth checks; they start from an empty cookie jar, not the setup's storage state.
test.use({ storageState: { cookies: [], origins: [] } });

for (const role of ['viewer', 'admin'] as const) {
  test(`the ${role} password logs in as ${role}`, async ({ request }) => {
    const login = await request.post('/api/auth/login', { data: { password: e2ePassword(role) } });
    expect(login.status()).toBe(200);
    expect(await login.json()).toEqual({ role });
    const me = await request.get('/api/auth/me');
    expect(await me.json()).toEqual({ role });
  });
}

test('a wrong password is rejected with 401 and no session', async ({ request }) => {
  const login = await request.post('/api/auth/login', {
    data: { password: 'definitely-not-the-password' },
  });
  expect(login.status()).toBe(401);
  expect((await request.get('/api/auth/me')).status()).toBe(401);
});

test('logout clears the session cookie', async ({ request }) => {
  await request.post('/api/auth/login', { data: { password: e2ePassword('viewer') } });
  const logout = await request.post('/api/auth/logout');
  expect(logout.status()).toBe(204);
  expect((await request.get('/api/auth/me')).status()).toBe(401);
  const { cookies } = await request.storageState();
  expect(cookies.filter((cookie) => cookie.name === 'sc_session')).toEqual([]);
});
```

Edit `frontend/playwright.config.ts` (Plan 01 T4) as a delta; everything outside `projects` (including the top-level
`use.baseURL: 'http://localhost:8080'`, which the `setup` project inherits) stays exactly as Plan 01 T4 wrote it:
1. Add `import { VIEWER_STATE } from './e2e/authState';` below the `@playwright/test` import.
2. Prepend `{ name: 'setup', testMatch: /auth\.setup\.ts$/ }` to `projects`.
3. Add `dependencies: ['setup']` to the existing `desktop` and `mobile` entries and `storageState: VIEWER_STATE` to
   their `use` objects. Every key Plan 01 T4 gave them stays unchanged (`...devices['Desktop Chrome']`, the viewports,
   and on `mobile` `deviceScaleFactor: 3`, `isMobile: true`, `hasTouch: true`).

The resulting `projects` array:

```ts
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts$/ },
    {
      name: 'desktop',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        storageState: VIEWER_STATE,
      },
    },
    {
      name: 'mobile',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
        storageState: VIEWER_STATE,
      },
    },
  ],
```

`auth.setup.ts` does not match Playwright's default `testMatch` (`*.spec.*` / `*.test.*`), so `desktop` and `mobile`
never run it themselves.

- [ ] **Step 30: Lint, format and type-check the frontend changes**

Run: `pnpm exec prettier --write e2e playwright.config.ts && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage && pnpm exec playwright test --list`
(`pnpm test --coverage`, not `pnpm test -- --coverage`: under pnpm 10 the extra `--` reaches Vitest literally and
coverage is silently skipped — Plan 01 Decision 6.)
Expected: all succeed with 0 warnings; Vitest stays green above the 90% lines/branches thresholds (e2e files are
outside its coverage); the listing shows `[setup] › auth.setup.ts` (2 tests) and `auth.spec.ts` under both
`[mobile]` and `[desktop]` (4 tests each). `process`, `node:fs` and `node:path` type-check through Plan 01 T2's
`@types/node` (Decision D22).

- [ ] **Step 31: Run the e2e suite against the compose stack**

From the worktree root (it has no `./secrets/` yet, so `dev-secrets.sh` writes the e2e passwords; run
`pnpm exec playwright install chromium` in `frontend/` once if browsers are missing):

```bash
docker build -t ghcr.io/gitgat/sunday-clays-backend:ci backend
docker build -t ghcr.io/gitgat/sunday-clays-frontend:ci -f frontend/Dockerfile .
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test)
docker compose -f compose.yaml -f compose.test.yaml down -v
```

Expected: every project passes — `[setup]` 2 passed, `auth.spec.ts` 4 passed per viewport, Plan 01 T4's
`smoke.spec.ts` still green (its 413 checks run before any route; its requests carry no `Origin`). `git status` shows
no file under `frontend/e2e/.auth/`.

- [ ] **Step 32: Run the full backend suite with lint, types and coverage**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: all green; coverage ≥90% lines and branches (`fail_under=90`), with every new `auth/` module,
`api/csrf.py`, `api/routes/auth.py` and `api/routes/_admin.py` at 100% lines and branches.

- [ ] **Step 33: Commit**

```bash
git add backend/src/sunday_clays/auth backend/src/sunday_clays/api/csrf.py \
  backend/src/sunday_clays/api/routes/auth.py backend/src/sunday_clays/api/routes/_admin.py \
  backend/src/sunday_clays/api/app.py backend/tests/conftest.py \
  backend/tests/unit/auth backend/tests/unit/api/test_csrf_middleware.py \
  backend/tests/unit/api/test_role_wiring.py backend/tests/integration/auth \
  backend/tests/integration/api/test_auth_routes.py \
  backend/tests/integration/api/test_route_auth_matrix.py \
  frontend/e2e/authState.ts frontend/e2e/auth.setup.ts frontend/e2e/auth.spec.ts \
  frontend/playwright.config.ts
git commit -F - <<'EOF'
feat(auth): add sessions, login rate limit, role wiring and CSRF guard

Two argon2id passwords map to viewer/admin; sc_session tokens are bound to the
current password hash and expire per role. Failed logins are limited per
X-Real-IP bucket before any hashing. create_app() now wires require_admin /
require_viewer by router module name and blocks cross-site writes; a runtime
route matrix guards every router added later. Playwright gains the setup
project and API-level auth specs.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 2: Admin imports and job status API + e2e fixture seed (master Plan 04 T2)

**Context.** Read this plan's Global Constraints and Decisions (D1–D5, D8, D11–D15, D19, D21, D22) and master sections
C2 (body size limit, errors), C3 (`ParseError`, severity semantics), C5 (import API and schemas), C6 (`enqueue`,
`get_job`, dedupe key `rebuild`) and C8 (admin routes, 413 contract). Task 1 is merged, so `admin_*` routers
automatically get `require_admin`, the CSRF guard is on, and the `admin_client`, `anon_client`, `auth_env` and
`fx_admin_client` fixtures exist. Plan 03 T6 (commit/discard/rollback, `fx_client`) and T7 (queue) are merged.
Integration tests need Docker or `TEST_DATABASE_URL`. Backend commands run in `backend/`, frontend commands in
`frontend/`. When the upload route maps `ParseError` → `DomainError("unreadable_file", str(e))`, it first logs the
exception with its chained cause and traceback server-side (`logger.warning(..., exc_info=exc)`): Plan 02's
`parse_upload` chains the original exception (`__cause__`) but never logs it, so otherwise nothing records why a file
was unreadable. The client still gets only the user-facing message.

**Files:**
- Create: `backend/src/sunday_clays/api/routes/admin_imports.py`
- Modify: `frontend/e2e/auth.setup.ts` (the admin setup test also seeds the fixture imports)
- Test: `backend/tests/integration/api/test_admin_imports_api.py`

**Interfaces:**
- Consumes:
  - Task 1: `sunday_clays.auth.deps.Actor`, `admin_actor`, `record_audit(session, ip, role, action, details)`;
    `sunday_clays.api.routes._admin.JobRefOut`; fixtures `admin_client`, `anon_client`, `auth_env`,
    `fx_admin_client`; `frontend/e2e/authState.ts` (`ADMIN_STATE`, `VIEWER_STATE`, `e2ePassword`) and the Playwright
    `setup` project.
  - Plan 01 T1: `Settings.max_upload_bytes` (default 10,485,760), `get_settings`, `get_session`, `DomainError`;
    `BodySizeLimitMiddleware` (413 `payload_too_large` above `max_upload_bytes + 65_536` on
    `POST /api/admin/imports`, before routing and auth); fixtures `session`, `scores_bytes`, `stations_bytes`.
  - Plan 02 T1: `sunday_clays.ingest.types.ParseError` (`str(e)` is a user-facing message).
  - Plan 03 T3: `sunday_clays.domain.imports.stage_import(session, data: bytes, filename: str) -> ImportPreview`
    (Plan 03 Decision 7: when a `pending` or `committed` import has the same sha256, nothing is staged and that
    import's stored preview comes back with `import_id == duplicate_of == <existing id>`; a file whose earlier import
    was discarded or rolled back is staged again as a new import. The e2e seed relies on this: re-uploading a file
    left `pending` by an interrupted run returns the pending import's id, which the seed then commits. It parses
    before inserting anything and lets `ingest.types.ParseError` propagate);
    `sunday_clays.domain.imports.get_import_preview(session: Session, import_id: int) -> ImportPreview` (the preview
    stored at staging, `duplicate_of=None`; raises `NotFoundError("import_not_found")`); `sunday_clays.domain.
    schemas.ImportPreview(import_id, kind, filename, duplicate_of, findings, diff, requires_removal_confirmation)` and
    `ImportSummary(id, kind, filename, status, uploaded_at, committed_at, rolled_back_at, sha256)`.
  - Plan 03 T6: `commit_import(session, import_id: int, *, confirm_removals: bool = False) -> None` (raises
    `ConflictError("removals_not_confirmed")` / `ConflictError("not_pending")` → 409),
    `discard_import(session, import_id: int) -> None` (`ConflictError("not_pending")`),
    `rollback_import(session, import_id: int) -> None` (`ConflictError("not_committed")`) — all three raise
    `NotFoundError("import_not_found")` for an unknown id before anything else;
    `sunday_clays.domain.imports.list_imports(session: Session) -> list[ImportSummary]` (newest first, never loads
    `file_bytes`); the committed-fixtures world behind `fx_admin_client`.
  - Plan 03 T7: `sunday_clays.jobs.queue.enqueue(session, kind: str, payload: dict | None = None, *, run_after=None,
    dedupe_key: str | None = None) -> int` (never commits; a queued job with the same dedupe key is returned instead of
    a new one); `get_job(session, job_id: int) -> JobOut` (raises `NotFoundError("job_not_found")`) with
    `sunday_clays.jobs.queue.JobOut(BaseModel){id: int, kind: str, status: str, attempts: int, error: str | None,
    created_at: datetime, started_at: datetime | None, finished_at: datetime | None}` (Plan 03 Decision 17).
- Produces (all under `require_admin` via the module name):
  - `POST /api/admin/imports` (multipart field `file`) → 200 `ImportPreview`; 400 `unsupported_file_type` /
    `unreadable_file`; 413 `payload_too_large`.
  - `GET /api/admin/imports` → `list[ImportSummary]`, newest first (Plan 03 T6 `list_imports`).
  - `GET /api/admin/imports/{id}` → `ImportPreview` as staged (Plan 03 T3 `get_import_preview`); 404
    `import_not_found`.
  - `POST /api/admin/imports/{id}/commit` (optional body `CommitIn{confirm_removals: bool = False}`) → `JobRefOut`;
    409 `removals_not_confirmed` / `not_pending`; 404 `import_not_found`.
  - `POST /api/admin/imports/{id}/discard` → 204 (409 `not_pending`); `POST /api/admin/imports/{id}/rollback` →
    `JobRefOut` (409 `not_committed`); both 404 `import_not_found`.
  - `GET /api/admin/jobs/{id}` → `JobOut`; 404 `job_not_found`.
  - Python: `admin_imports.PayloadTooLargeError` (413), `CommitIn`, `clean_filename(raw: str | None) -> str`.
  - e2e: after the `setup` project runs, the compose stack holds committed scores and stations fixture imports and a
    finished rebuild (idempotent across runs).
  - Consumers: Plan 06 T1 (ETag tests call `GET /api/admin/imports` and `GET /api/admin/jobs/{id}`), Plan 08 T5a
    (imports UI), every e2e spec that reads seeded data (Plan 07 T8, Plans 08–11).

**Branch:** `task/04-2-admin-imports`

**Depends on:** Plan 04 T1, Plan 03 T6, Plan 03 T7 (Plan 02 T1–T5 and Plan 03 T3 come in through them).

- [ ] **Step 1: Write the failing upload / list / preview tests**

Create `backend/tests/integration/api/test_admin_imports_api.py`:

```python
import io
import logging
from datetime import datetime
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.config import Settings, get_settings
from sunday_clays.models import Base

IMPORTS = Base.metadata.tables["imports"]
JOBS = Base.metadata.tables["jobs"]
AUDIT = Base.metadata.tables["audit_log"]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _upload(
    client: TestClient, data: bytes, name: str = "stations_2026-09-27.xlsx"
) -> dict[str, Any]:
    response = client.post("/api/admin/imports", files={"file": (name, data, XLSX)})
    assert response.status_code == 200, response.text
    return response.json()


def _status(session: Session, import_id: int) -> str:
    return str(session.scalar(select(IMPORTS.c.status).where(IMPORTS.c.id == import_id)))


def _actions(session: Session) -> list[str]:
    return list(session.scalars(select(AUDIT.c.action).order_by(AUDIT.c.id)))


def _set_upload_limit(monkeypatch: pytest.MonkeyPatch, limit: int) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", str(limit))
    get_settings.cache_clear()


def _without_latest_event(scores_bytes: bytes) -> bytes:
    """The scores fixture minus every ALL SCORE DETAIL row of its newest event (2026-09-27)."""
    workbook = openpyxl.load_workbook(io.BytesIO(scores_bytes))
    sheet = workbook["ALL SCORE DETAIL"]
    event_col = [cell.value for cell in sheet[1]].index("Event") + 1
    dates = [sheet.cell(row, event_col).value for row in range(2, sheet.max_row + 1)]
    newest = max(value for value in dates if isinstance(value, datetime))
    for row in range(sheet.max_row, 1, -1):
        if sheet.cell(row, event_col).value == newest:
            sheet.delete_rows(row)
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def test_upload_returns_preview_and_is_audited(
    admin_client: TestClient, stations_bytes: bytes, session: Session
) -> None:
    preview = _upload(admin_client, stations_bytes)
    assert preview["kind"] == "stations"
    assert preview["filename"] == "stations_2026-09-27.xlsx"
    assert preview["duplicate_of"] is None
    assert _status(session, preview["import_id"]) == "pending"
    assert _actions(session)[-1] == "imports.stage"


# python-multipart already cuts a drive-letter path (C:\...) to its basename; these reach the route.
@pytest.mark.parametrize(
    "name", ["Users\\bob\\Station Scores.XLSX", "reports/2026/Station Scores.XLSX"]
)
def test_path_filename_is_reduced_to_basename(
    admin_client: TestClient, stations_bytes: bytes, name: str
) -> None:
    preview = _upload(admin_client, stations_bytes, name=name)
    assert preview["filename"] == "Station Scores.XLSX"


def test_long_filename_keeps_its_last_255_characters(
    admin_client: TestClient, stations_bytes: bytes
) -> None:
    preview = _upload(admin_client, stations_bytes, name="s" * 295 + ".xlsx")
    assert len(preview["filename"]) == 255
    assert preview["filename"].endswith(".xlsx")


def test_reupload_reports_duplicate_of(admin_client: TestClient, stations_bytes: bytes) -> None:
    first = _upload(admin_client, stations_bytes)
    second = _upload(admin_client, stations_bytes)
    assert second["duplicate_of"] == first["import_id"]


def test_get_import_returns_the_staged_preview(
    admin_client: TestClient, stations_bytes: bytes
) -> None:
    preview = _upload(admin_client, stations_bytes)
    response = admin_client.get(f"/api/admin/imports/{preview['import_id']}")
    assert response.status_code == 200
    assert response.json() == preview


def test_list_imports_is_newest_first(
    admin_client: TestClient, stations_bytes: bytes, scores_bytes: bytes
) -> None:
    older = _upload(admin_client, stations_bytes)
    newer = _upload(admin_client, scores_bytes, name="scores_2026-09-27.xlsx")
    listed = admin_client.get("/api/admin/imports").json()
    assert [row["id"] for row in listed] == [newer["import_id"], older["import_id"]]
    assert {row["status"] for row in listed} == {"pending"}
    assert len(listed[0]["sha256"]) == 64


@pytest.mark.parametrize("name", ["scores.csv", "scores.xls", "scores"])
def test_non_xlsx_filename_is_rejected(
    admin_client: TestClient, stations_bytes: bytes, name: str, session: Session
) -> None:
    response = admin_client.post("/api/admin/imports", files={"file": (name, stations_bytes, XLSX)})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"
    assert session.execute(select(IMPORTS.c.id)).all() == []


def test_unreadable_workbook_is_400_and_stages_nothing(
    admin_client: TestClient, session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    route_logger = "sunday_clays.api.routes.admin_imports"
    with caplog.at_level(logging.WARNING, logger=route_logger):
        response = admin_client.post(
            "/api/admin/imports", files={"file": ("junk.xlsx", b"this is not a zip file", XLSX)}
        )
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "unreadable_file",
        "message": "This file could not be read as an Excel workbook",
    }
    # The chained cause (the zipfile error) is logged server-side, never sent to the client.
    records = [r for r in caplog.records if r.name == route_logger]
    assert len(records) == 1
    exc_info = records[0].exc_info
    assert exc_info is not None
    _, exc, _ = exc_info
    assert exc is not None and exc.__cause__ is not None
    assert session.execute(select(IMPORTS.c.id)).all() == []
    assert "imports.stage" not in _actions(session)


def test_upload_backstop_rejects_one_byte_over_limit(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_upload_limit(monkeypatch, 2048)
    over = admin_client.post("/api/admin/imports", files={"file": ("a.xlsx", b"x" * 2049, XLSX)})
    at_limit = admin_client.post(
        "/api/admin/imports", files={"file": ("a.xlsx", b"x" * 2048, XLSX)}
    )
    assert over.status_code == 413
    assert over.json()["error"]["code"] == "payload_too_large"
    assert at_limit.status_code == 400  # size accepted; the parser rejects the bytes
    assert at_limit.json()["error"]["code"] == "unreadable_file"


def test_oversized_upload_without_session_gets_413(
    anon_client: TestClient, auth_env: Settings
) -> None:
    body = b"x" * (auth_env.max_upload_bytes + 65_536 + 1)
    response = anon_client.post("/api/admin/imports", files={"file": ("big.xlsx", body, XLSX)})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/integration/api/test_admin_imports_api.py -v`
Expected: every test FAILS with a 404 from the missing route (e.g. `AssertionError: {"detail":"Not Found"}` from
`_upload`, or `KeyError: 'error'`) — except `test_oversized_upload_without_session_gets_413`, which already PASSES
because Plan 01 T1's `BodySizeLimitMiddleware` answers before routing and auth.

- [ ] **Step 3: Implement upload, list and preview in `admin_imports.py`**

Create `backend/src/sunday_clays/api/routes/admin_imports.py`:

```python
"""Admin import workflow (C8): upload → preview → commit / discard / rollback, and job status."""

import logging
from pathlib import PurePosixPath
from typing import Annotated, ClassVar, Final

from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.config import Settings, get_settings
from sunday_clays.db import get_session
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.imports import get_import_preview, stage_import
from sunday_clays.domain.imports import list_imports as list_import_summaries
from sunday_clays.domain.schemas import ImportPreview, ImportSummary
from sunday_clays.ingest.types import ParseError

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES: Final = (".xlsx", ".xlsm")
MAX_FILENAME_CHARS: Final = 255

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
ActorDep = Annotated[Actor, Depends(admin_actor)]
ImportId = Annotated[int, Path(alias="id")]


class PayloadTooLargeError(DomainError):
    status_code: ClassVar[int] = 413


def clean_filename(raw: str | None) -> str:
    """Basename only (last `/`- or `\\`-separated segment), at most the last 255 characters."""
    name = PurePosixPath((raw or "").replace("\\", "/")).name.strip()
    return name[-MAX_FILENAME_CHARS:]


def _stage(session: Session, data: bytes, filename: str, actor: Actor) -> ImportPreview:
    preview = stage_import(session, data, filename)
    record_audit(
        session,
        actor.ip,
        actor.role,
        "imports.stage",
        {
            "import_id": preview.import_id,
            "kind": preview.kind,
            "filename": filename,
            "duplicate_of": preview.duplicate_of,
        },
    )
    return preview


@router.post("/imports")
async def upload_import(
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    actor: ActorDep,
) -> ImportPreview:
    filename = clean_filename(file.filename)
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise DomainError("unsupported_file_type", "Upload the Excel workbook (.xlsx or .xlsm)")
    limit = settings.max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError("payload_too_large", f"The file is larger than {limit} bytes")
    try:
        return await run_in_threadpool(_stage, session, data, filename, actor)
    except ParseError as exc:
        # parse_upload chains the original exception but never logs it; the client gets str(exc) only.
        logger.warning("Upload %r could not be parsed", filename, exc_info=exc)
        raise DomainError("unreadable_file", str(exc)) from exc


@router.get("/imports")
def list_imports(session: SessionDep) -> list[ImportSummary]:
    """Every import, newest first (Plan 03 T6)."""
    return list_import_summaries(session)


@router.get("/imports/{id}")
def get_import(import_id: ImportId, session: SessionDep) -> ImportPreview:
    """The preview stored at staging time (Plan 03 T3; Decision D15); 404 ``import_not_found``."""
    return get_import_preview(session, import_id)
```

`ruff check --fix` may reorder the two `sunday_clays.domain.imports` lines; ruff's isort keeps the aliased import
(`list_imports as list_import_summaries`, which avoids a clash with the route function `list_imports`) on its own
line.

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/integration/api/test_admin_imports_api.py -v`
Expected: PASS (13 passed).

- [ ] **Step 5: Write the failing commit / discard / rollback / job tests**

Append to `backend/tests/integration/api/test_admin_imports_api.py`:

```python
def test_commit_enqueues_rebuild_and_is_audited(
    admin_client: TestClient, stations_bytes: bytes, session: Session
) -> None:
    import_id = _upload(admin_client, stations_bytes)["import_id"]
    response = admin_client.post(
        f"/api/admin/imports/{import_id}/commit", json={"confirm_removals": False}
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = session.execute(select(JOBS.c.kind, JOBS.c.status).where(JOBS.c.id == job_id)).one()
    assert tuple(job) == ("rebuild", "queued")
    assert _status(session, import_id) == "committed"
    assert _actions(session)[-1] == "imports.commit"


def test_commit_without_body_does_not_confirm_removals(
    admin_client: TestClient, stations_bytes: bytes, session: Session
) -> None:
    import_id = _upload(admin_client, stations_bytes)["import_id"]
    assert admin_client.post(f"/api/admin/imports/{import_id}/commit").status_code == 200
    assert _status(session, import_id) == "committed"


def test_stale_scores_upload_needs_confirmation_to_commit(
    fx_admin_client: TestClient, scores_bytes: bytes
) -> None:
    preview = _upload(fx_admin_client, _without_latest_event(scores_bytes), name="scores_old.xlsx")
    assert preview["kind"] == "scores"
    assert preview["requires_removal_confirmation"] is True
    commit_url = f"/api/admin/imports/{preview['import_id']}/commit"
    refused = fx_admin_client.post(commit_url, json={"confirm_removals": False})
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "removals_not_confirmed"
    assert fx_admin_client.post(commit_url, json={"confirm_removals": True}).status_code == 200


def test_second_commit_is_409_not_pending(admin_client: TestClient, stations_bytes: bytes) -> None:
    import_id = _upload(admin_client, stations_bytes)["import_id"]
    admin_client.post(f"/api/admin/imports/{import_id}/commit")
    again = admin_client.post(f"/api/admin/imports/{import_id}/commit")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "not_pending"


def test_discard_marks_import_discarded(
    admin_client: TestClient, stations_bytes: bytes, session: Session
) -> None:
    import_id = _upload(admin_client, stations_bytes)["import_id"]
    response = admin_client.post(f"/api/admin/imports/{import_id}/discard")
    assert response.status_code == 204
    assert _status(session, import_id) == "discarded"
    assert _actions(session)[-1] == "imports.discard"


def test_rollback_marks_import_rolled_back_and_enqueues_rebuild(
    admin_client: TestClient, stations_bytes: bytes, session: Session
) -> None:
    import_id = _upload(admin_client, stations_bytes)["import_id"]
    admin_client.post(f"/api/admin/imports/{import_id}/commit")
    response = admin_client.post(f"/api/admin/imports/{import_id}/rollback")
    assert response.status_code == 200
    kind = session.scalar(select(JOBS.c.kind).where(JOBS.c.id == response.json()["job_id"]))
    assert kind == "rebuild"
    assert _status(session, import_id) == "rolled_back"
    assert _actions(session)[-1] == "imports.rollback"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/admin/imports/987654"),
        ("POST", "/api/admin/imports/987654/commit"),
        ("POST", "/api/admin/imports/987654/discard"),
        ("POST", "/api/admin/imports/987654/rollback"),
    ],
)
def test_unknown_import_is_404(admin_client: TestClient, method: str, path: str) -> None:
    response = admin_client.request(method, path)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "import_not_found"


def test_job_status_reports_the_queued_job(admin_client: TestClient, stations_bytes: bytes) -> None:
    import_id = _upload(admin_client, stations_bytes)["import_id"]
    job_id = admin_client.post(f"/api/admin/imports/{import_id}/commit").json()["job_id"]
    job = admin_client.get(f"/api/admin/jobs/{job_id}").json()
    assert (job["id"], job["kind"], job["status"]) == (job_id, "rebuild", "queued")


def test_unknown_job_is_404(admin_client: TestClient) -> None:
    response = admin_client.get("/api/admin/jobs/987654")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"
```

- [ ] **Step 6: Run them to verify the new tests fail**

Run: `uv run pytest tests/integration/api/test_admin_imports_api.py -v`
Expected: the 13 Step 1 tests still pass and `test_unknown_import_is_404[GET-…]` passes; every other new test FAILS
with a 404 `{"detail":"Not Found"}` for the missing commit / discard / rollback / jobs routes (e.g. `assert 404 == 200`
or `KeyError: 'job_id'`).

- [ ] **Step 7: Add commit, discard, rollback and job status**

In `backend/src/sunday_clays/api/routes/admin_imports.py`, replace the line
`from sunday_clays.domain.imports import get_import_preview, stage_import` with the imports below (keep the
`list_imports as list_import_summaries` line; then `uv run ruff check --fix` sorts them into place):

```python
from pydantic import BaseModel

from sunday_clays.api.routes._admin import JobRefOut
from sunday_clays.domain.imports import (
    commit_import,
    discard_import,
    get_import_preview,
    rollback_import,
    stage_import,
)
from sunday_clays.jobs.queue import JobOut, enqueue, get_job
```

Add directly under `ImportId = Annotated[int, Path(alias="id")]`:

```python
JobId = Annotated[int, Path(alias="id")]
```

Add directly under the `PayloadTooLargeError` class:

```python
class CommitIn(BaseModel):
    confirm_removals: bool = False
```

Append at the end of the module. An unknown id needs no pre-check query: `commit_import`, `discard_import`,
`rollback_import` and `get_job` raise Plan 03's `NotFoundError("import_not_found")` / `NotFoundError("job_not_found")`
before anything else (Decision D11), and `get_session` rolls the request back.

```python
@router.post("/imports/{id}/commit")
def commit(
    import_id: ImportId, session: SessionDep, actor: ActorDep, body: CommitIn | None = None
) -> JobRefOut:
    confirm = body.confirm_removals if body is not None else False
    commit_import(session, import_id, confirm_removals=confirm)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "imports.commit",
        {"import_id": import_id, "confirm_removals": confirm, "job_id": job_id},
    )
    return JobRefOut(job_id=job_id)


@router.post("/imports/{id}/discard", status_code=204)
def discard(import_id: ImportId, session: SessionDep, actor: ActorDep) -> None:
    discard_import(session, import_id)
    record_audit(session, actor.ip, actor.role, "imports.discard", {"import_id": import_id})


@router.post("/imports/{id}/rollback")
def rollback(import_id: ImportId, session: SessionDep, actor: ActorDep) -> JobRefOut:
    rollback_import(session, import_id)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "imports.rollback",
        {"import_id": import_id, "job_id": job_id},
    )
    return JobRefOut(job_id=job_id)


@router.get("/jobs/{id}")
def job_status(job_id: JobId, session: SessionDep) -> JobOut:
    return get_job(session, job_id)
```

- [ ] **Step 8: Run the import tests and the route matrix**

Run: `uv run pytest tests/integration/api/test_admin_imports_api.py tests/integration/api/test_route_auth_matrix.py -v`
Expected: PASS (25 + 6 passed). The matrix now also proves that every new `/api/admin/imports…` and
`/api/admin/jobs/{id}` route answers 401 without a cookie (also with `If-None-Match: *`) and 403 for a viewer.

- [ ] **Step 9: Seed the fixture imports in the admin setup test**

Replace `frontend/e2e/auth.setup.ts` with:

```ts
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { expect, test as setup } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';

import { ADMIN_STATE, VIEWER_STATE, e2ePassword } from './authState';

const FIXTURES_DIR = resolve('..', 'backend', 'tests', 'fixtures');
const XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const SEED = [
  { kind: 'scores', file: 'scores_2026-09-27.xlsx' },
  { kind: 'stations', file: 'stations_2026-09-27.xlsx' },
] as const;

interface ImportRow {
  id: number;
  kind: string;
  status: string;
}

interface JobRow {
  status: string;
  error?: string | null;
}

async function waitForJob(request: APIRequestContext, jobId: number): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const response = await request.get(`/api/admin/jobs/${jobId}`);
    expect(response.status()).toBe(200);
    const job = (await response.json()) as JobRow;
    if (job.status === 'done') return;
    if (job.status === 'failed') throw new Error(`job ${jobId} failed: ${job.error ?? ''}`);
    await new Promise((resolveWait) => setTimeout(resolveWait, 1_000));
  }
  throw new Error(`job ${jobId} was not done after 120 s`);
}

async function seedFixtureImports(request: APIRequestContext): Promise<void> {
  const listed = await request.get('/api/admin/imports');
  expect(listed.status()).toBe(200);
  const imports = (await listed.json()) as ImportRow[];
  for (const { kind, file } of SEED) {
    if (imports.some((row) => row.kind === kind && row.status === 'committed')) continue;
    const upload = await request.post('/api/admin/imports', {
      multipart: {
        file: { name: file, mimeType: XLSX_TYPE, buffer: readFileSync(join(FIXTURES_DIR, file)) },
      },
    });
    expect(upload.status(), await upload.text()).toBe(200);
    const { import_id: importId } = (await upload.json()) as { import_id: number };
    const commit = await request.post(`/api/admin/imports/${importId}/commit`, {
      data: { confirm_removals: false },
    });
    expect(commit.status(), await commit.text()).toBe(200);
    const { job_id: jobId } = (await commit.json()) as { job_id: number };
    await waitForJob(request, jobId);
  }
}

setup('log in as viewer', async ({ request }) => {
  const response = await request.post('/api/auth/login', {
    data: { password: e2ePassword('viewer') },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: 'viewer' });
  await request.storageState({ path: VIEWER_STATE });
});

setup('log in as admin and seed the fixture imports', async ({ request }) => {
  setup.setTimeout(300_000);
  const response = await request.post('/api/auth/login', {
    data: { password: e2ePassword('admin') },
  });
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ role: 'admin' });
  await request.storageState({ path: ADMIN_STATE });
  await seedFixtureImports(request);
});
```

`resolve('..', …)` is relative to the Playwright working directory, `frontend/` (C11 runs
`cd frontend && pnpm exec playwright test`). Uploading the 302,948-byte scores fixture through Caddy also proves it
passes the Caddy (11 MB) and API size limits.

- [ ] **Step 10: Lint, format and type-check the frontend change**

Run: `pnpm exec prettier --write e2e/auth.setup.ts && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage && pnpm exec playwright test --list`
(`pnpm test --coverage` per Plan 01 Decision 6; `pnpm test -- --coverage` would skip coverage under pnpm 10.)
Expected: all succeed with 0 warnings (Vitest green above its 90% thresholds); the listing shows
`[setup] › auth.setup.ts › log in as admin and seed the fixture imports`. `node:fs` and `node:path` type-check through
Plan 01 T2's `@types/node` (Decision D22).

- [ ] **Step 11: Run the e2e suite twice against the compose stack (seed + idempotency)**

From the worktree root (no `./secrets/` yet):

```bash
docker build -t ghcr.io/gitgat/sunday-clays-backend:ci backend
docker build -t ghcr.io/gitgat/sunday-clays-frontend:ci -f frontend/Dockerfile .
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh
IMAGE_TAG=ci docker compose -f compose.yaml -f compose.test.yaml up -d --wait
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test)
(cd frontend && E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test --project=setup)
docker compose -f compose.yaml -f compose.test.yaml exec -T db psql -U sunday -d sunday_clays -Atc "select kind, status from imports order by id"
docker compose -f compose.yaml -f compose.test.yaml down -v
```

Expected: the first run passes every project (the seed uploads, commits and waits for both rebuild jobs, well under
the 300 s setup timeout); the second `setup` run passes quickly without uploading again; the query prints exactly
`scores|committed` and `stations|committed`.

- [ ] **Step 12: Run the full backend suite with lint, types and coverage**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: all green; coverage ≥90% lines and branches, `api/routes/admin_imports.py` at 100%.

- [ ] **Step 13: Commit**

```bash
git add backend/src/sunday_clays/api/routes/admin_imports.py \
  backend/tests/integration/api/test_admin_imports_api.py frontend/e2e/auth.setup.ts
git commit -F - <<'EOF'
feat(admin): add import upload, preview, commit, discard, rollback and job status

Uploads are limited by type and size (413 backstop behind the body-size
middleware), parse failures become 400 unreadable_file, and every mutation
enqueues the coalesced rebuild job and writes audit_log. The Playwright
setup project now seeds the committed fixture imports idempotently.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

### Task 3: Admin rules, shooter fixes and ops API (master Plan 04 T3)

**Context.** Read this plan's Global Constraints and Decisions (D1–D4, D8, D11–D13, D16–D18) and master sections C3
(`similar_name_keys`), C4 (`rules`, `rounds`, `shooter_profiles`, `data_issues`, `audit_log`, `app_state`), C5 (rule
types, payloads, `create_rule`, `deactivate_rule`), C6 (`enqueue`, dedupe keys `rebuild` and `recompute`, the
`recalibrate` payload) and C8 (admin routes). Task 1 is merged (role wiring, `_admin.py`, fixtures); Plan 03 T5–T7
are merged. Task 2 runs in parallel on other files; only this task edits `_admin.py`. Integration tests need Docker or
`TEST_DATABASE_URL`. All commands run in `backend/`.

**Files:**
- Create: `backend/src/sunday_clays/api/routes/admin_rules.py`, `backend/src/sunday_clays/api/routes/admin_shooters.py`,
  `backend/src/sunday_clays/api/routes/admin_ops.py`
- Modify: `backend/src/sunday_clays/api/routes/_admin.py` (add `RuleMutationOut`)
- Test: `backend/tests/unit/api/test_duplicate_key_pairs.py`, `backend/tests/integration/api/test_admin_rules_api.py`,
  `backend/tests/integration/api/test_admin_shooters_api.py`, `backend/tests/integration/api/test_admin_ops_api.py`

**Interfaces:**
- Consumes:
  - Task 1: `sunday_clays.auth.deps.Actor`, `admin_actor`, `record_audit(session, ip, role, action, details)`;
    `sunday_clays.api.routes._admin.JobRefOut`, `ensure_exists(session, table, row_id, code, noun)`; fixtures
    `admin_client`, `fx_admin_client`; the `auth.login` audit row that each `admin_client` login writes (Decision D8).
  - Plan 02 T1: `sunday_clays.ingest.names.similar_name_keys(key: str, key_dates: AbstractSet[date],
    candidates: Mapping[str, AbstractSet[date]]) -> list[str]`.
  - Plan 03 T5: `sunday_clays.domain.rules.RuleType` (`merge_shooter`, `rename_shooter`, `score_override`,
    `hide_round`, `round_type_override`, `set_status`, `station_reset`, `alias_name`);
    `create_rule(session, rule_type: RuleType, payload: dict[str, Any], note: str | None) -> int` (validates with the
    `extra="forbid"` payload model and stores `model_dump(mode="json")`, so the stored payload has exactly the C5
    keys; never commits; errors per Plan 03 Decision 15: `DomainError("invalid_rule")` 400 for an invalid payload or
    a self-merge, `DomainError("merge_cycle")` 400, `NotFoundError("shooter_not_found")`,
    `NotFoundError("round_not_found")`); `deactivate_rule(session, rule_id: int) -> None`
    (`NotFoundError("rule_not_found")`, `ConflictError("rule_not_active")` 409, `DomainError("merge_cycle")` 400);
    payload shapes of C5.
  - Plan 03 T6: fixture `fx_session` and the committed-fixtures world (332 shooters, live `rounds` with identity keys,
    `shooter_profiles`, data issues incl. `station_score_mismatch` on 2026-09-13 and `incomplete_results` on
    2024-11-10).
  - Plan 03 T7: `sunday_clays.jobs.queue.enqueue(session, kind, payload=None, *, run_after=None, dedupe_key=None) -> int`.
  - Plan 01 T1 / Plan 03 T1: fixture `session`; tables `app_state(key, value)`, `jobs`, `rules`, `audit_log`.
- Produces (all under `require_admin` via the module name):
  - `api/routes/_admin.py`: `class RuleMutationOut(BaseModel): rule_id: int; job_id: int`.
  - `admin_rules`: `GET /api/admin/rules` → `list[RuleOut]` (`RuleOut{id, rule_type: RuleType, payload: dict,
    active: bool, note: str | None, created_at: datetime, deactivated_at: datetime | None}`, newest first);
    `POST /api/admin/rules` body `RuleIn{rule_type: RuleType, payload: dict[str, Any], note: str | None}` →
    `RuleMutationOut` (422 unknown `rule_type`; Plan 03's 400 `invalid_rule` / `merge_cycle`, 404
    `shooter_not_found` / `round_not_found`); `POST /api/admin/rules/{id}/deactivate` → `RuleMutationOut` (404
    `rule_not_found`, 409 `rule_not_active`, 400 `merge_cycle`).
  - `admin_shooters`: `POST /api/admin/shooters/merge` body `MergeIn{source_shooter_id: int, target_shooter_id: int,
    dry_run: bool = False}` → `MergeOut{shared_dates: int, job_id: int | None}` (400 `merge_same_shooter`, 404
    `shooter_not_found`, 400 `merge_cycle` from Plan 03 on a real merge);
    `POST /api/admin/shooters/{id}/rename` body `RenameIn{display_name}` → `RuleMutationOut`;
    `POST /api/admin/shooters/{id}/status` body `StatusIn{status: Literal["member", "guest", "deceased"]}` →
    `RuleMutationOut`; `POST /api/admin/shooters/{id}/aliases` body `AliasIn{name_key}` → `RuleMutationOut`;
    `shared_dates(session: Session, first_id: int, second_id: int) -> int`.
  - `admin_ops`: `GET /api/admin/data-issues` → `list[DataIssueOut]` (`DataIssueOut{id: int, code: str,
    severity: str, event_date: date | None, shooter_id: int | None, message: str, details: dict[str, Any]}`);
    `GET /api/admin/possible-duplicates` →
    `list[PossibleDuplicateOut{a: DuplicateSideOut, b: DuplicateSideOut}]` (`DuplicateSideOut{shooter_id, name_key,
    display_name, n_rounds, first_event, last_event}`); `GET /api/admin/audit?limit=&offset=` → `list[AuditEntryOut]`
    (`AuditEntryOut{id: int, at: datetime, ip: str | None, role: str, action: str, details: dict[str, Any]}`). Both
    `details` fields are non-null (C4 NOT NULL default `'{}'`, Plan 03 T1), so the generated TS type is
    `{[key: string]: unknown}`, matching Plan 08 T5c's `details: Record<string, unknown>` (Decision D12);
    `POST /api/admin/recompute` optional body `RecomputeIn{recalibrate: bool = False}` → `JobRefOut`;
    `duplicate_key_pairs(key_dates: Mapping[str, Set[date]], key_shooter: Mapping[str, int]) -> list[tuple[str, str]]`.
  - Consumers: Plan 08 T5b (possible-duplicates queue, merge dry run, rename/status forms, rules list/create/deactivate)
    and Plan 08 T5c (data issues, alias assignment, audit log, recompute with recalibrate).

**Branch:** `task/04-3-admin-rules-shooters-ops`

**Depends on:** Plan 04 T1, Plan 03 T6, Plan 03 T7 (Plan 03 T5 and Plan 02 T1 come in through them).

- [ ] **Step 1: Write the failing rules tests**

Create `backend/tests/integration/api/test_admin_rules_api.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
JOBS = Base.metadata.tables["jobs"]
RULES = Base.metadata.tables["rules"]
ROUND_TYPE_RULE = {
    "rule_type": "round_type_override",
    "payload": {"event_date": "2026-09-13", "round_type": "sporting"},
    "note": "stations were all even that week",
}


def _last_action(session: Session) -> str | None:
    return session.scalar(select(AUDIT.c.action).order_by(AUDIT.c.id.desc()).limit(1))


def test_create_rule_lists_it_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    created = fx_admin_client.post("/api/admin/rules", json=ROUND_TYPE_RULE)
    assert created.status_code == 200
    rule_id, job_id = created.json()["rule_id"], created.json()["job_id"]
    newest = fx_admin_client.get("/api/admin/rules").json()[0]
    assert (newest["id"], newest["rule_type"], newest["active"]) == (
        rule_id,
        "round_type_override",
        True,
    )
    assert newest["payload"]["round_type"] == "sporting"
    assert newest["note"] == "stations were all even that week"
    assert fx_session.scalar(select(JOBS.c.kind).where(JOBS.c.id == job_id)) == "rebuild"
    assert _last_action(fx_session) == "rules.create"


def test_invalid_payload_is_400_and_creates_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    before = fx_session.scalar(select(func.count()).select_from(RULES))
    response = fx_admin_client.post(
        "/api/admin/rules", json={"rule_type": "merge_shooter", "payload": {}}
    )
    assert response.status_code == 400
    assert set(response.json()["error"]) == {"code", "message"}
    assert response.json()["error"]["code"] == "invalid_rule"  # Plan 03 Decision 15
    assert fx_session.scalar(select(func.count()).select_from(RULES)) == before


def test_unknown_rule_type_is_422(fx_admin_client: TestClient) -> None:
    response = fx_admin_client.post(
        "/api/admin/rules", json={"rule_type": "delete_everything", "payload": {}}
    )
    assert response.status_code == 422


def test_deactivate_rule_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    rule_id = fx_admin_client.post("/api/admin/rules", json=ROUND_TYPE_RULE).json()["rule_id"]
    response = fx_admin_client.post(f"/api/admin/rules/{rule_id}/deactivate")
    assert response.status_code == 200
    assert response.json()["rule_id"] == rule_id
    listed = {rule["id"]: rule for rule in fx_admin_client.get("/api/admin/rules").json()}
    assert listed[rule_id]["active"] is False
    assert _last_action(fx_session) == "rules.deactivate"


def test_deactivate_unknown_rule_is_404(fx_admin_client: TestClient) -> None:
    response = fx_admin_client.post("/api/admin/rules/987654/deactivate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "rule_not_found"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/integration/api/test_admin_rules_api.py -v`
Expected: all 5 FAIL on the missing routes — 404 `{"detail":"Not Found"}` (e.g. `assert 404 == 200`,
`assert 404 == 422`, `KeyError: 'error'`).

- [ ] **Step 3: Add `RuleMutationOut` and implement `admin_rules.py`**

In `backend/src/sunday_clays/api/routes/_admin.py`, add directly under the `JobRefOut` class:

```python
class RuleMutationOut(BaseModel):
    rule_id: int
    job_id: int
```

Create `backend/src/sunday_clays/api/routes/admin_rules.py`:

```python
"""Overlay rules (C5, C8): list, create and deactivate; every mutation enqueues a rebuild."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import RuleMutationOut, ensure_exists
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import get_session
from sunday_clays.domain.rules import RuleType, create_rule, deactivate_rule
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base

router = APIRouter(prefix="/api/admin/rules", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
ActorDep = Annotated[Actor, Depends(admin_actor)]
RuleId = Annotated[int, Path(alias="id")]


class RuleIn(BaseModel):
    rule_type: RuleType
    payload: dict[str, Any]
    note: str | None = Field(default=None, max_length=500)


class RuleOut(BaseModel):
    id: int
    rule_type: RuleType
    payload: dict[str, Any]
    active: bool
    note: str | None
    created_at: datetime
    deactivated_at: datetime | None


@router.get("")
def list_rules(session: SessionDep) -> list[RuleOut]:
    t = Base.metadata.tables["rules"]
    rows = session.execute(
        select(
            t.c.id,
            t.c.rule_type,
            t.c.payload,
            t.c.active,
            t.c.note,
            t.c.created_at,
            t.c.deactivated_at,
        ).order_by(t.c.id.desc())
    ).mappings()
    return [RuleOut.model_validate(dict(row)) for row in rows]


@router.post("")
def add_rule(body: RuleIn, session: SessionDep, actor: ActorDep) -> RuleMutationOut:
    rule_id = create_rule(session, body.rule_type, body.payload, body.note)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "rules.create",
        {
            "rule_id": rule_id,
            "rule_type": body.rule_type,
            "payload": body.payload,
            "job_id": job_id,
        },
    )
    return RuleMutationOut(rule_id=rule_id, job_id=job_id)


@router.post("/{id}/deactivate")
def deactivate(rule_id: RuleId, session: SessionDep, actor: ActorDep) -> RuleMutationOut:
    ensure_exists(session, "rules", rule_id, "rule_not_found", "Rule")
    deactivate_rule(session, rule_id)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session, actor.ip, actor.role, "rules.deactivate", {"rule_id": rule_id, "job_id": job_id}
    )
    return RuleMutationOut(rule_id=rule_id, job_id=job_id)
```

- [ ] **Step 4: Run them to verify they pass**

Run: `uv run pytest tests/integration/api/test_admin_rules_api.py -v`
Expected: PASS (5 passed). Plan 03 T5's `create_rule` turns a pydantic `ValidationError` into
`DomainError("invalid_rule")` (its Decision 15). If `test_invalid_payload_is_400_and_creates_nothing` gets a 500 or
another code, the merged `create_rule` differs from that contract: stop and report NEEDS_CONTEXT rather than
papering over it in the route.

- [ ] **Step 5: Write the failing shooter-fix tests**

Create `backend/tests/integration/api/test_admin_shooters_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.models import Base

AUDIT = Base.metadata.tables["audit_log"]
PROFILES = Base.metadata.tables["shooter_profiles"]
RULES = Base.metadata.tables["rules"]


def _shooter(session: Session, display_name: str) -> int:
    return int(
        session.execute(
            select(PROFILES.c.shooter_id).where(PROFILES.c.display_name == display_name)
        ).scalar_one()
    )


def _count(session: Session, table_name: str) -> int:
    return int(session.scalar(select(func.count()).select_from(Base.metadata.tables[table_name])))


def _newest_rule(session: Session) -> tuple[str, dict[str, object]]:
    row = session.execute(
        select(RULES.c.rule_type, RULES.c.payload).order_by(RULES.c.id.desc()).limit(1)
    ).one()
    return row.rule_type, row.payload


def _last_action(session: Session) -> str | None:
    return session.scalar(select(AUDIT.c.action).order_by(AUDIT.c.id.desc()).limit(1))


def test_merge_dry_run_reports_shared_dates_and_changes_nothing(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    stroud, skelton = _shooter(fx_session, "Stroud, Jasper"), _shooter(fx_session, "Skelton, Jasper")
    rules_before, audit_before = _count(fx_session, "rules"), _count(fx_session, "audit_log")
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": skelton, "target_shooter_id": stroud, "dry_run": True},
    )
    assert response.status_code == 200
    assert response.json() == {"shared_dates": 18, "job_id": None}
    assert _count(fx_session, "rules") == rules_before
    assert _count(fx_session, "audit_log") == audit_before


def test_merge_creates_rule_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    stroud, skelton = _shooter(fx_session, "Stroud, Jasper"), _shooter(fx_session, "Skelton, Jasper")
    response = fx_admin_client.post(
        "/api/admin/shooters/merge", json={"source_shooter_id": skelton, "target_shooter_id": stroud}
    )
    body = response.json()
    assert body["shared_dates"] == 18
    assert isinstance(body["job_id"], int)
    assert _newest_rule(fx_session) == (
        "merge_shooter",
        {"source_shooter_id": skelton, "target_shooter_id": stroud},
    )
    assert _last_action(fx_session) == "shooters.merge"


def test_merge_with_itself_is_400(fx_admin_client: TestClient, fx_session: Session) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    response = fx_admin_client.post(
        "/api/admin/shooters/merge", json={"source_shooter_id": hadley, "target_shooter_id": hadley}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "merge_same_shooter"


def test_merge_with_unknown_shooter_is_404(
    fx_admin_client: TestClient, fx_session: Session
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    response = fx_admin_client.post(
        "/api/admin/shooters/merge",
        json={"source_shooter_id": 987_654, "target_shooter_id": hadley, "dry_run": True},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"


@pytest.mark.parametrize(
    ("path", "body", "action", "rule_type", "payload"),
    [
        (
            "rename",
            {"display_name": "  Ike Hadley  "},
            "shooters.rename",
            "rename_shooter",
            {"display_name": "Ike Hadley"},
        ),
        (
            "status",
            {"status": "deceased"},
            "shooters.status",
            "set_status",
            {"status": "deceased"},
        ),
        (
            "aliases",
            {"name_key": "hadley clint"},
            "shooters.alias",
            "alias_name",
            {"name_key": "hadley clint"},
        ),
    ],
)
def test_shooter_fix_creates_rule_enqueues_rebuild_and_audits(
    fx_admin_client: TestClient,
    fx_session: Session,
    path: str,
    body: dict[str, str],
    action: str,
    rule_type: str,
    payload: dict[str, str],
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    response = fx_admin_client.post(f"/api/admin/shooters/{hadley}/{path}", json=body)
    assert response.status_code == 200
    assert set(response.json()) == {"rule_id", "job_id"}
    assert _newest_rule(fx_session) == (rule_type, {"shooter_id": hadley, **payload})
    assert _last_action(fx_session) == action


@pytest.mark.parametrize(
    ("path", "body"),
    [("rename", {"display_name": "   "}), ("status", {"status": "ghost"}), ("aliases", {})],
)
def test_invalid_shooter_fix_body_is_422(
    fx_admin_client: TestClient, fx_session: Session, path: str, body: dict[str, str]
) -> None:
    hadley = _shooter(fx_session, "Hadley, Ike")
    assert fx_admin_client.post(f"/api/admin/shooters/{hadley}/{path}", json=body).status_code == 422


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("rename", {"display_name": "Nobody"}),
        ("status", {"status": "guest"}),
        ("aliases", {"name_key": "nobody"}),
    ],
)
def test_shooter_fix_for_unknown_shooter_is_404(
    fx_admin_client: TestClient, path: str, body: dict[str, str]
) -> None:
    response = fx_admin_client.post(f"/api/admin/shooters/987654/{path}", json=body)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "shooter_not_found"
```

- [ ] **Step 6: Run them to verify they fail**

Run: `uv run pytest tests/integration/api/test_admin_shooters_api.py -v`
Expected: all 13 FAIL on the missing routes — 404 `{"detail":"Not Found"}` (`assert 404 == 200`,
`assert 404 == 422`, `KeyError: 'shared_dates'` / `'error'`).

- [ ] **Step 7: Implement `admin_shooters.py`**

Create `backend/src/sunday_clays/api/routes/admin_shooters.py`:

```python
"""Shooter identity fixes (C8): merge (with dry run), rename, status, alias → overlay rules."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import RuleMutationOut, ensure_exists
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import get_session
from sunday_clays.domain.errors import DomainError
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base

router = APIRouter(prefix="/api/admin/shooters", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
ActorDep = Annotated[Actor, Depends(admin_actor)]
ShooterId = Annotated[int, Path(alias="id")]


class MergeIn(BaseModel):
    source_shooter_id: int
    target_shooter_id: int
    dry_run: bool = False


class MergeOut(BaseModel):
    shared_dates: int
    job_id: int | None


class RenameIn(BaseModel):
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]


class StatusIn(BaseModel):
    status: Literal["member", "guest", "deceased"]


class AliasIn(BaseModel):
    name_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def shared_dates(session: Session, first_id: int, second_id: int) -> int:
    """Number of distinct event dates on which both shooters have a live round."""
    rounds = Base.metadata.tables["rounds"]
    first = select(rounds.c.event_date).where(rounds.c.shooter_id == first_id)
    second = select(rounds.c.event_date).where(rounds.c.shooter_id == second_id)
    both = first.intersect(second).subquery()
    return int(session.scalar(select(func.count()).select_from(both)) or 0)


def _rule_then_rebuild(
    session: Session, actor: Actor, action: str, rule_type: RuleType, payload: dict[str, Any]
) -> RuleMutationOut:
    rule_id = create_rule(session, rule_type, payload, None)
    job_id = enqueue(session, "rebuild", dedupe_key="rebuild")
    record_audit(
        session, actor.ip, actor.role, action, {**payload, "rule_id": rule_id, "job_id": job_id}
    )
    return RuleMutationOut(rule_id=rule_id, job_id=job_id)


@router.post("/merge")
def merge(body: MergeIn, session: SessionDep, actor: ActorDep) -> MergeOut:
    if body.source_shooter_id == body.target_shooter_id:
        raise DomainError("merge_same_shooter", "Pick two different shooters to merge")
    for shooter_id in (body.source_shooter_id, body.target_shooter_id):
        ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    shared = shared_dates(session, body.source_shooter_id, body.target_shooter_id)
    if body.dry_run:
        return MergeOut(shared_dates=shared, job_id=None)
    payload = {
        "source_shooter_id": body.source_shooter_id,
        "target_shooter_id": body.target_shooter_id,
    }
    done = _rule_then_rebuild(session, actor, "shooters.merge", RuleType.MERGE_SHOOTER, payload)
    return MergeOut(shared_dates=shared, job_id=done.job_id)


@router.post("/{id}/rename")
def rename(
    shooter_id: ShooterId, body: RenameIn, session: SessionDep, actor: ActorDep
) -> RuleMutationOut:
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    payload = {"shooter_id": shooter_id, "display_name": body.display_name}
    return _rule_then_rebuild(session, actor, "shooters.rename", RuleType.RENAME_SHOOTER, payload)


@router.post("/{id}/status")
def set_status(
    shooter_id: ShooterId, body: StatusIn, session: SessionDep, actor: ActorDep
) -> RuleMutationOut:
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    payload = {"shooter_id": shooter_id, "status": body.status}
    return _rule_then_rebuild(session, actor, "shooters.status", RuleType.SET_STATUS, payload)


@router.post("/{id}/aliases")
def add_alias(
    shooter_id: ShooterId, body: AliasIn, session: SessionDep, actor: ActorDep
) -> RuleMutationOut:
    ensure_exists(session, "shooters", shooter_id, "shooter_not_found", "Shooter")
    payload = {"name_key": body.name_key, "shooter_id": shooter_id}
    return _rule_then_rebuild(session, actor, "shooters.alias", RuleType.ALIAS_NAME, payload)
```

- [ ] **Step 8: Run them to verify they pass**

Run: `uv run pytest tests/integration/api/test_admin_shooters_api.py -v`
Expected: PASS (13 passed) — the dry run reports the 18 dates Stroud, Jasper and Skelton, Jasper both shot (computed from
the fixture workbook) and writes nothing.

- [ ] **Step 9: Write the failing ops tests**

Create `backend/tests/unit/api/test_duplicate_key_pairs.py`:

```python
from datetime import date

from sunday_clays.api.routes.admin_ops import duplicate_key_pairs

JAN_05, JAN_12, JAN_19 = date(2025, 1, 5), date(2025, 1, 12), date(2025, 1, 19)


def test_similar_keys_of_two_shooters_form_one_ordered_pair() -> None:
    key_dates = {"pruett clay": {JAN_12}, "preutt clay": {JAN_05}}
    shooters = {"pruett clay": 2, "preutt clay": 1}
    assert duplicate_key_pairs(key_dates, shooters) == [("preutt clay", "pruett clay")]


def test_keys_already_resolved_to_one_shooter_are_not_paired() -> None:
    key_dates = {"preutt clay": {JAN_05}, "pruett clay": {JAN_12}}
    assert duplicate_key_pairs(key_dates, {"preutt clay": 7, "pruett clay": 7}) == []


def test_a_shooter_pair_is_reported_once_via_its_smallest_key_pair() -> None:
    key_dates = {"preutt clay": {JAN_05}, "pruett clay": {JAN_12}, "pruitt clay": {JAN_19}}
    shooters = {"preutt clay": 1, "pruett clay": 2, "pruitt clay": 2}
    assert duplicate_key_pairs(key_dates, shooters) == [("preutt clay", "pruett clay")]


def test_dissimilar_keys_are_not_paired() -> None:
    key_dates = {"hadley ike": {JAN_05}, "devlin sid": {JAN_12}}
    assert duplicate_key_pairs(key_dates, {"hadley ike": 1, "devlin sid": 2}) == []
```

Create `backend/tests/integration/api/test_admin_ops_api.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.models import Base

APP_STATE = Base.metadata.tables["app_state"]
JOBS = Base.metadata.tables["jobs"]


def test_data_issues_list_the_fixture_issues(fx_admin_client: TestClient) -> None:
    issues = fx_admin_client.get("/api/admin/data-issues").json()
    found = {(issue["code"], issue["event_date"]) for issue in issues}
    assert ("station_score_mismatch", "2026-09-13") in found
    assert ("incomplete_results", "2024-11-10") in found
    assert [issue["code"] for issue in issues] == sorted(issue["code"] for issue in issues)


def test_possible_duplicates_on_the_fixture(fx_admin_client: TestClient) -> None:
    pairs = fx_admin_client.get("/api/admin/possible-duplicates").json()
    keys = [(pair["a"]["name_key"], pair["b"]["name_key"]) for pair in pairs]
    assert len(pairs) == 25  # the Plan 02 T5 golden: 8 multi-token + 17 first-name-only hints
    assert ("preutt clay", "pruett clay") in keys
    assert ("stroud jasper", "skelton jasper") not in keys
    assert keys == sorted(keys)
    preutt = pairs[keys.index(("preutt clay", "pruett clay"))]
    assert (preutt["a"]["display_name"], preutt["b"]["display_name"]) == (
        "Preutt, Clay",
        "Pruett, Clay",
    )
    assert preutt["a"]["n_rounds"] == 1
    assert preutt["a"]["shooter_id"] != preutt["b"]["shooter_id"]


def test_audit_log_is_newest_first_and_paged(admin_client: TestClient) -> None:
    admin_client.post("/api/admin/recompute")
    admin_client.post("/api/admin/recompute", json={"recalibrate": True})
    newest = admin_client.get("/api/admin/audit", params={"limit": 1}).json()
    page = admin_client.get("/api/admin/audit", params={"limit": 2, "offset": 1}).json()
    assert [entry["action"] for entry in newest] == ["ops.recompute"]
    assert newest[0]["details"]["recalibrate"] is True
    assert [entry["action"] for entry in page] == ["ops.recompute", "auth.login"]
    assert page[0]["details"]["recalibrate"] is False


def test_audit_limit_is_bounded(admin_client: TestClient) -> None:
    assert admin_client.get("/api/admin/audit", params={"limit": 0}).status_code == 422
    assert admin_client.get("/api/admin/audit", params={"limit": 1001}).status_code == 422


def test_recompute_without_body_enqueues_plain_recompute(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(insert(APP_STATE).values(key="skill_params", value={"obs_var": 14}))
    job_id = admin_client.post("/api/admin/recompute").json()["job_id"]
    kind, payload = session.execute(
        select(JOBS.c.kind, JOBS.c.payload).where(JOBS.c.id == job_id)
    ).one()
    assert kind == "recompute"
    assert not (payload or {}).get("recalibrate")
    assert session.scalar(select(APP_STATE.c.key).where(APP_STATE.c.key == "skill_params"))


def test_recalibrate_clears_skill_params_and_flags_the_job(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(insert(APP_STATE).values(key="skill_params", value={"obs_var": 14}))
    response = admin_client.post("/api/admin/recompute", json={"recalibrate": True})
    payload = session.scalar(select(JOBS.c.payload).where(JOBS.c.id == response.json()["job_id"]))
    assert payload == {"recalibrate": True}
    assert session.scalar(select(APP_STATE.c.key).where(APP_STATE.c.key == "skill_params")) is None


def test_recalibrate_still_applies_when_a_plain_recompute_is_queued(
    admin_client: TestClient, session: Session
) -> None:
    session.execute(insert(APP_STATE).values(key="skill_params", value={"obs_var": 14}))
    plain = admin_client.post("/api/admin/recompute").json()["job_id"]
    coalesced = admin_client.post("/api/admin/recompute", json={"recalibrate": True}).json()
    assert coalesced["job_id"] == plain
    assert session.scalar(select(APP_STATE.c.key).where(APP_STATE.c.key == "skill_params")) is None
```

- [ ] **Step 10: Run them to verify they fail**

Run: `uv run pytest tests/unit/api/test_duplicate_key_pairs.py tests/integration/api/test_admin_ops_api.py -v`
Expected: the unit file errors at collection with
`ModuleNotFoundError: No module named 'sunday_clays.api.routes.admin_ops'`; the 7 integration tests FAIL on 404
`{"detail":"Not Found"}` (e.g. `KeyError: 'job_id'`, `assert 404 == 422`).

- [ ] **Step 11: Implement `admin_ops.py`**

Create `backend/src/sunday_clays/api/routes/admin_ops.py`:

```python
"""Admin operations (C8): data issues, possible duplicates, audit log, analytics recompute."""

from collections.abc import Mapping, Set
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes._admin import JobRefOut
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import get_session
from sunday_clays.ingest.names import similar_name_keys
from sunday_clays.jobs.queue import enqueue
from sunday_clays.models import Base

router = APIRouter(prefix="/api/admin", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session, scope="function")]
ActorDep = Annotated[Actor, Depends(admin_actor)]


class DataIssueOut(BaseModel):
    id: int
    code: str
    severity: str
    event_date: date | None
    shooter_id: int | None
    message: str
    details: dict[str, Any]  # C4 NOT NULL default '{}' (Plan 03 T1); non-null in openapi.json


class DuplicateSideOut(BaseModel):
    shooter_id: int
    name_key: str
    display_name: str
    n_rounds: int
    first_event: date | None
    last_event: date | None


class PossibleDuplicateOut(BaseModel):
    a: DuplicateSideOut
    b: DuplicateSideOut


class AuditEntryOut(BaseModel):
    id: int
    at: datetime
    ip: str | None
    role: str
    action: str
    details: dict[str, Any]  # C4 NOT NULL default '{}' (Plan 03 T1); non-null in openapi.json


class RecomputeIn(BaseModel):
    recalibrate: bool = False


def duplicate_key_pairs(
    key_dates: Mapping[str, Set[date]], key_shooter: Mapping[str, int]
) -> list[tuple[str, str]]:
    """Similar identity-key pairs (C3 rules) of different shooters, one pair per shooter pair.

    Pairs come back as (smaller key, larger key), sorted; a shooter pair reachable through
    several key pairs is reported once, via its smallest key pair.
    """
    key_pairs: set[tuple[str, str]] = set()
    for key, dates in key_dates.items():
        for other in similar_name_keys(key, dates, key_dates):
            if key_shooter[key] != key_shooter[other]:
                key_pairs.add((min(key, other), max(key, other)))
    seen: set[frozenset[int]] = set()
    result: list[tuple[str, str]] = []
    for first, second in sorted(key_pairs):
        shooters = frozenset((key_shooter[first], key_shooter[second]))
        if shooters not in seen:
            seen.add(shooters)
            result.append((first, second))
    return result


@router.get("/data-issues")
def data_issues(session: SessionDep) -> list[DataIssueOut]:
    t = Base.metadata.tables["data_issues"]
    rows = session.execute(
        select(
            t.c.id,
            t.c.code,
            t.c.severity,
            t.c.event_date,
            t.c.shooter_id,
            t.c.message,
            t.c.details,
        ).order_by(t.c.code, t.c.event_date.desc().nulls_last(), t.c.id)
    ).mappings()
    return [DataIssueOut.model_validate(dict(row)) for row in rows]


@router.get("/possible-duplicates")
def possible_duplicates(session: SessionDep) -> list[PossibleDuplicateOut]:
    rounds = Base.metadata.tables["rounds"]
    profiles = Base.metadata.tables["shooter_profiles"]
    key_dates: dict[str, set[date]] = {}
    key_shooter: dict[str, int] = {}
    for name_key, shooter_id, event_date in session.execute(
        select(rounds.c.name_key, rounds.c.shooter_id, rounds.c.event_date)
    ):
        key_dates.setdefault(name_key, set()).add(event_date)
        key_shooter[name_key] = shooter_id
    profile = {
        row["shooter_id"]: row
        for row in session.execute(
            select(
                profiles.c.shooter_id,
                profiles.c.display_name,
                profiles.c.n_rounds,
                profiles.c.first_event,
                profiles.c.last_event,
            )
        ).mappings()
    }

    def side(name_key: str) -> DuplicateSideOut:
        return DuplicateSideOut.model_validate(
            {**profile[key_shooter[name_key]], "name_key": name_key}
        )

    return [
        PossibleDuplicateOut(a=side(first), b=side(second))
        for first, second in duplicate_key_pairs(key_dates, key_shooter)
    ]


@router.get("/audit")
def audit(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEntryOut]:
    t = Base.metadata.tables["audit_log"]
    rows = session.execute(
        select(t.c.id, t.c.at, t.c.ip, t.c.role, t.c.action, t.c.details)
        .order_by(t.c.id.desc())
        .limit(limit)
        .offset(offset)
    ).mappings()
    return [AuditEntryOut.model_validate(dict(row)) for row in rows]


@router.post("/recompute")
def recompute(session: SessionDep, actor: ActorDep, body: RecomputeIn | None = None) -> JobRefOut:
    recalibrate = body is not None and body.recalibrate
    if recalibrate:
        # Also clear the key here: a plain recompute may already be queued under the same
        # dedupe key, and enqueue() would then return that job without our payload.
        app_state = Base.metadata.tables["app_state"]
        session.execute(delete(app_state).where(app_state.c.key == "skill_params"))
    payload = {"recalibrate": True} if recalibrate else None
    job_id = enqueue(session, "recompute", payload, dedupe_key="recompute")
    record_audit(
        session,
        actor.ip,
        actor.role,
        "ops.recompute",
        {"recalibrate": recalibrate, "job_id": job_id},
    )
    return JobRefOut(job_id=job_id)
```

- [ ] **Step 12: Run them to verify they pass**

Run: `uv run pytest tests/unit/api/test_duplicate_key_pairs.py tests/integration/api/test_admin_ops_api.py -v`
Expected: PASS (4 + 7 passed). `test_possible_duplicates_on_the_fixture` returns the same 25 pairs Plan 02 T5 pins for
`similar_name_keys` over the parsed fixture (co-attendees Stroud/Skelton Jasper are not flagged).

- [ ] **Step 13: Run the route matrix and the full backend suite with lint, types and coverage**

Run: `uv run pytest tests/integration/api/test_route_auth_matrix.py -v`
Expected: PASS (6 passed) — now also covering every `/api/admin/rules…`, `/api/admin/shooters…`,
`/api/admin/data-issues`, `/api/admin/possible-duplicates`, `/api/admin/audit` and `/api/admin/recompute` route.

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`
Expected: all green; coverage ≥90% lines and branches, `admin_rules.py`, `admin_shooters.py`, `admin_ops.py` and
`_admin.py` at 100%.

- [ ] **Step 14: Commit**

```bash
git add backend/src/sunday_clays/api/routes/_admin.py \
  backend/src/sunday_clays/api/routes/admin_rules.py \
  backend/src/sunday_clays/api/routes/admin_shooters.py \
  backend/src/sunday_clays/api/routes/admin_ops.py \
  backend/tests/unit/api/test_duplicate_key_pairs.py \
  backend/tests/integration/api/test_admin_rules_api.py \
  backend/tests/integration/api/test_admin_shooters_api.py \
  backend/tests/integration/api/test_admin_ops_api.py
git commit -F - <<'EOF'
feat(admin): add rules, shooter fixes, data issues, duplicates, audit and recompute APIs

Rule and shooter-fix mutations create overlay rules, enqueue the coalesced
rebuild and write audit_log; merge supports a dry run that reports shared
dates. Possible duplicates pair similar identity keys of distinct live
shooters. A recalibration request clears skill_params even when a plain
recompute is already queued.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```
