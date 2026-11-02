# Scores MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A remote MCP server for Sunday Clays, reached through an external MCP gateway (OAuth handled by the gateway, out of this repo). Phase 1
ships the read tools. Phase 2 adds the narrow, append-only import tools (preview, commit, rollback).

**Architecture:**
- A new `sunday_clays.mcp` package runs as a FastMCP streamable-HTTP app under uvicorn, as a new `mcp` swarm service
  built from the same backend image.
- Bearer middleware checks the gateway's shared upstream token.
- Tools call plain functions in `sunday_clays.mcp.reads` (and, in phase 2, `.writes`). The functions take a SQLAlchemy
  `Session`, so they are tested directly and again over real MCP requests.

**Tech Stack:** Python 3.13, `mcp==1.30.0` (FastMCP), SQLAlchemy 2, pydantic 2, uvicorn, pytest + testcontainers Postgres,
hypothesis.

**Spec:** `docs/superpowers/specs/2026-11-01-scores-mcp-design.md`

## Global Constraints
- **Dependency.** `mcp==1.30.0`, pinned exactly in `backend/pyproject.toml`, with `uv.lock` updated.
- **Transport.** Streamable HTTP at `/mcp` on `0.0.0.0:${MCP_PORT:-8080}`, SDK session defaults, not stateless.
- **Auth.**
  - `Authorization: Bearer <token>`, with the token from `MCP_AUTH_TOKEN_FILE` (or `MCP_AUTH_TOKEN`) via the existing
    `config.read_secret_env`.
  - Refuse to start if the token is missing or empty, unless `MCP_AUTH_DISABLED=1`.
  - Compare with `hmac.compare_digest`. A failure is a 401 whose body is `{"error":"unauthorized"}` and no more.
  - `GET /healthz` is unauthenticated and returns `{"ok":true}`.
- **Logging.** Never log the token, the request headers or tool arguments containing names. Log the tool name and the
  outcome only.
- **Tool inputs.** Pydantic models with `extra="forbid"`. Bounded strings: `query` has 1–60 characters, `limit` is 1–25.
  Dates are ISO `YYYY-MM-DD`. Raw SQL and file paths are never accepted.
- **Names in tests.** Only the repo's pseudonymous fixture names. No real club names anywhere in the repo.
- **TDD.** Each task pastes RED output (the new test failing on the base) and GREEN output into its report.
- **Running tests.** Run only the touched test files locally. The full suite and coverage run in CI. Push with
  `LEFTHOOK=0`. Coverage floors (backend 99% lines) are enforced by `ratchets/`, and `ratchets/` is never edited.
- **Commits.** End every commit with the session's attribution trailers.

## Review Focus
1. **The bearer is checked on every MCP path**, including `/mcp/` with a trailing slash, GET (the SSE stream), DELETE
   (session end) and OPTIONS. Only `/healthz` is open. Tested in Task 1.
2. **Empty or whitespace-only token file.** Startup refuses it, just like a missing file. Tested in Task 1.
3. **`find_shooters` with regex metacharacters or SQL wildcards** (`%`, `_`, `.*`, `\`) is treated literally and never
   errors or matches everything. Tested in Task 2.
4. **`get_event` for a date with no event, or a non-Sunday,** returns a clear "no event" result, not an exception or a
   500. Tested in Task 2.
5. **The compose service never lands on `traefik_public`/`edge_public`**, and check_stack fails if someone adds it. Tested
   in Task 3.

---

## Phase 1: read-only

### Task 1: MCP app skeleton with bearer auth

**Files:**
- Create: `backend/src/sunday_clays/mcp/__init__.py`, `backend/src/sunday_clays/mcp/auth.py`,
  `backend/src/sunday_clays/mcp/server.py`, `backend/src/sunday_clays/mcp/__main__.py`
- Modify: `backend/pyproject.toml` (add `mcp==1.30.0`), `backend/uv.lock`
- Test: `backend/tests/unit/mcp/test_auth.py`, `backend/tests/integration/mcp/test_http.py`,
  `backend/tests/integration/mcp/conftest.py`

**Interfaces:**
- Produces:
  - `auth.load_auth_token() -> str | None`. Returns None only when `MCP_AUTH_DISABLED=1`. Raises
    `config.ConfigError` if the token is missing or empty.
  - `auth.BearerMiddleware(app: ASGIApp, token: str | None)`. Pure ASGI. Lets through `/healthz` and every request when
    the token is None.
  - `server.build_mcp(session_factory: Callable[[], ContextManager[Session]]) -> FastMCP`. Registers the tools; there
    are none in this task.
  - `server.build_app(token: str | None, session_factory) -> Starlette`. This is `mcp.streamable_http_app()` with
    `/healthz` added, wrapped in `BearerMiddleware`. The SDK's lifespan must still run: use the app FastMCP returns and
    add the route to it. Don't mount it inside another app.
  - `server.default_session_factory()`. A context manager over `db.SessionFactory`: commit on success, roll back on
    error. It mirrors `db.get_session`.
  - `__main__`: `uvicorn.run(build_app(load_auth_token(), default_session_factory), host="0.0.0.0",
    port=int(env MCP_PORT or 8080), proxy_headers=False, access_log=False)`.
  - Test fixture in `tests/integration/mcp/conftest.py`: `mcp_server(session_factory) -> str`. It starts the app with
    uvicorn in a background thread on a free localhost port, waits for `/healthz`, yields the base URL and shuts down.
    `TOKEN = "test-token-not-secret"`. A helper, `async call_tool(url, name, args, token=TOKEN)`, uses
    `mcp.client.streamable_http.streamablehttp_client` and `ClientSession` and returns the parsed JSON result.

- [ ] **Step 1: Write failing tests.**
  - `tests/unit/mcp/test_auth.py`:
    - `test_missing_token_refuses_start`: no env set → `ConfigError` mentioning `MCP_AUTH_TOKEN`.
    - `test_blank_token_file_refuses_start`: a file containing `"  \n"` → `ConfigError`.
    - `test_disabled_returns_none`: `MCP_AUTH_DISABLED=1` → `None`.
    - `test_token_file_read_and_stripped`: file `"abc\n"` → `"abc"`.
  - `tests/integration/mcp/test_http.py`, against `mcp_server`:
    - `test_healthz_open`: GET `/healthz` with no auth → 200 `{"ok": true}`.
    - `test_mcp_requires_bearer`: parametrize over method×path for POST `/mcp`, GET `/mcp`, DELETE `/mcp`, POST
      `/mcp/` and OPTIONS `/mcp`, with no header, `Bearer wrong` and `Basic x`. Each → 401 with body exactly
      `{"error":"unauthorized"}`.
    - `test_initialize_and_list_tools`: the real MCP client with the right token initializes, and `list_tools()` succeeds.
- [ ] **Step 2: Run them and see the failure.**
  `cd backend && uv run pytest tests/unit/mcp tests/integration/mcp -q` → ImportError (`sunday_clays.mcp`).
- [ ] **Step 3: Implement the files listed under Interfaces.** Add `mcp==1.30.0` and run `uv lock`.
- [ ] **Step 4: Run the same tests and see them pass.** Also run `uv run ruff check src tests && uv run mypy src`.
- [ ] **Step 5: Commit:** `feat(mcp): MCP server skeleton with gateway bearer auth`.

### Task 2: Read tools

**Files:**
- Create: `backend/src/sunday_clays/mcp/reads.py`, `backend/src/sunday_clays/mcp/schemas.py`
- Modify: `backend/src/sunday_clays/mcp/server.py` (register the tools)
- Test: `backend/tests/integration/mcp/test_reads.py` (direct, on `fx_session`),
  `backend/tests/integration/mcp/test_tools_http.py` (over `mcp_server` with a factory yielding `fx_session`)

**Interfaces:**
- Consumes: `build_mcp`, `mcp_server` and `call_tool` from Task 1.
- Produces, in `reads.py`:
  - `find_shooters(session, query: str, limit: int = 10) -> list[ShooterHit]`. `ShooterHit` is `{display_name: str,
    rounds: int, last_shot: date | None, usual_status: str | None}`.
    - Case-insensitive, and every whitespace-separated token must appear in `display_name`. Use `ILIKE` with `%`, `_`
      and `\` escaped (escape character `\`).
    - Shooters listed in `shooter_aliases` match on their aliases too.
    - Ordered by token-prefix matches first, then rounds descending.
    - `usual_status` is the most common `rounds.status` over the last 12 months.
  - `get_event(session, event_date: date, include_rows: bool = False) -> EventSummary | NoEvent`.
    - `EventSummary` holds: `{date, head_count, round_type, stats_excluded, target_total, n_rounds, score_sum,
      average, stations: [{label, targets, dropped}], data_issues: [{severity, code, message}], rows?: [{name, score,
      status, gauge_class}]}`.
    - `NoEvent` is `{date, found: false, last_event_date}`.
  - `get_job(session, job_id: int) -> JobStatus | NotFound`. `JobStatus` is `{id, kind, status, created_at,
    finished_at, error}`, with whatever columns `jobs` really has. Phase 2 extends `get_job` to accept a preview_id.
- Tools registered as `find_shooters(query, limit=10)`, `get_event(date, include_rows=False)` and `get_job(id)`.
  - Each takes a pydantic-validated input, opens a session from the factory, and returns `model_dump(mode="json")`.
  - A validation error comes back as an MCP tool error, never a 500.
  - Each tool's description says what it is for in one or two sentences. `find_shooters` says to use it to map
    handwritten names to the exact stored "Last, First" spelling.

- [ ] **Step 1: Write failing tests.**
  - `test_reads.py`. Take the fixture names from the fx world (look them up in the test; don't hard-code anything
    outside the fixture data):
    - `test_find_shooters_tokens_any_order`: "first last" and "last" both find the shooter.
    - `test_find_shooters_literal_wildcards`: `"%"`, `"_"`, `".*"` and `"\\"` return [] and don't raise.
    - `test_find_shooters_limit_and_order`.
    - `test_find_shooters_alias`.
    - `test_get_event_summary`: on a fixture Sunday, `score_sum == sum(rounds.score)` and `head_count` matches
      `events`. `rows` is absent unless `include_rows` is set.
    - `test_get_event_thrown_out`: with the `fx_thrown_out_session` fixture, the station shows `dropped: true` and
      `stats_excluded` is true.
    - `test_get_event_missing_date`: `NoEvent` with `last_event_date` set, including for a non-Sunday.
    - `test_get_job`: a queued job and a missing id.
  - `test_tools_http.py`:
    - `test_tools_listed`: the three tool names are listed.
    - `test_find_shooters_over_mcp`.
    - `test_get_event_over_mcp`.
    - `test_bad_input_is_tool_error`: `limit=500`, `query=""` and an extra key each give an error result
      (`isError` true), and the server stays healthy.
- [ ] **Step 2: Run them and see the failure.** `uv run pytest tests/integration/mcp -q` → the tests fail because the
  tools and module are missing.
- [ ] **Step 3: Implement `reads.py`, `schemas.py` and the tool registration.**
- [ ] **Step 4: Run them and see them pass.** Then run ruff and mypy.
- [ ] **Step 5: Commit:** `feat(mcp): read tools find_shooters, get_event, get_job`.

### Task 3: Swarm service, stack checks, docs

**Files:**
- Modify: `compose.swarm.yaml`, `scripts/check_stack.py`, `deploy/README.md`
- Test: the existing check_stack tests (find them with `grep -rn check_stack backend/tests scripts`), or a new
  `backend/tests/unit/test_check_stack_mcp.py`

**Interfaces:**
- The `mcp` service in `compose.swarm.yaml`:
  - Same image line as `api`, with `command: ["python", "-m", "sunday_clays.mcp"]`.
  - `environment: {MCP_AUTH_TOKEN_FILE: /run/secrets/mcp_token, DATABASE_URL_FILE: /run/secrets/database_url,
    MCP_PORT: "8080"}`.
  - `secrets: [{source: mcp_token, target: mcp_token}, database_url]`.
  - `networks: {default: {}, mcp_gateway: {aliases: [sundayclays-mcp]}}`.
  - `deploy: {placement: *x86, update_config: *update-rollback, rollback_config: *rollback-stop-first,
    resources: {limits: {memory: 384M}, reservations: {memory: 128M}}, restart_policy: {condition: on-failure}}`.
  - A healthcheck on `/healthz` using python urllib, because the image has no curl.
- Top level:
  - `networks.mcp_gateway: {external: true, name: ${SC_MCP_NETWORK:-mcp_gateway}}`.
  - `secrets.mcp_token: {external: true, name: ${SC_MCP_TOKEN_SECRET:-sundayclays_mcp_token}}`.
  - Check how the existing `${SC_*}` variables (for example `SC_DB_NODE`) reach `docker stack deploy` through the deployer (`deploy/README.md`, `deploy/deployer/`), and pass these two the same way. Their real values live only in the private deploy env, never in this repo.
- `check_stack.py`:
  - Add `mcp` to `REQUIRED_SERVICES`.
  - Allow the x86 constraint on `mcp`, alongside api and worker.
  - New rule: `mcp` must be on the external `mcp_gateway` network with alias `sundayclays-mcp`, and must not join
    `traefik_public` or `edge_public`.
  - New rule: no other service may join `mcp_gateway`.
- In phase 2 the service gains `db_password` and the `/var/data/sunday-clays/backups:/backups` bind. Not now.

- [ ] **Step 1: Write failing tests.**
  - `test_stack_has_mcp_service`: run on the real compose file.
  - `test_mcp_on_traefik_public_rejected`: mutate a loaded copy so mcp joins `traefik_public` → problem reported.
  - `test_mcp_missing_alias_rejected`.
  - `test_other_service_on_mcp_gateway_rejected`.
- [ ] **Step 2: RED.** Run the tests → they fail.
- [ ] **Step 3: Implement the compose change and the check_stack rules.** Add a "Scores MCP" section to
  `deploy/README.md`:
  - what the service is;
  - that the gateway network and token secret are external, named by `SC_MCP_NETWORK`/`SC_MCP_TOKEN_SECRET` in the deploy env;
  - that routing, hostnames and the gateway itself are the deployment's concern, not this repo's;
  - that commits are disabled until phase 3.
- [ ] **Step 4: GREEN.** Also run `uv run --no-project --with pyyaml python scripts/check_stack.py < compose.swarm.yaml`
  the way CI does (`.github/workflows/ci.yml:285`).
- [ ] **Step 5: Commit:** `feat(mcp): mcp swarm service behind the MCP gateway`.

**Phase 1 exit:**
1. Open the PR, CI green, merge with the owner's OK.
2. The deployer rolls out.
3. The deployment connects the service to the gateway (outside this repo).
4. **Unattended test:** a scheduled agent run calls `get_event` through the gateway after the sign-in session's
   lifetime has passed. If it fails, stop and redesign auth.

---

## Phase 2: write tools (outline, to be detailed after the routine test passes)
- **T4: `mcp_operations` table.** Alembic migration 0011 and the model. Columns as in the spec. Unique
  `idempotency_key`. `get_job` accepts a uuid preview_id.
- **T5: `mcp/build.py`.** The skill's `build.py` logic as pure functions:
  - `WeekInput` validation, hypothesis-tested;
  - `build_scores(base: bytes, week) -> bytes`;
  - `build_stations(week) -> bytes`;
  - `build_correction(base, date, rows) -> bytes`.
- **T6: `mcp/backup.py`.**
  - `pre_import_dump(preview_id) -> Path`: pg_dump custom format, `pg_restore --list`, a 1 MiB floor, the
    `backup.lock` flock, and keep the last 20 `pre-import-*.dump`.
  - Fail-closed tests with a fake `pg_dump` on PATH.
  - Compose: add `db_password` and the backups bind.
- **T7: `preview_week` and `preview_correction`.**
  - The date rules and the append-only diff gate, which discards staged imports when it refuses.
  - The 1-hour expiry sweep.
  - Returns date and head_count first.
- **T8: `commit_week` and `rollback_week`.**
  - Gated by `MCP_COMMIT_ENABLED` (default false). A correction is always refused.
  - Idempotency.
  - Dump, then commit scores, then commit stations, then queue the rebuild, then write the audit row.
  - Rollback is for the latest commit only.
- **T9: `python -m sunday_clays.mcp.approve <preview_id>`.** A TTY confirm, then the same commit steps with
  `commit_path="cli-approve"`. Update the private skill to the MCP flow.
