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

## Phase 2: write tools

Branch `feat/scores-mcp-writes`, off main. Merging this branch auto-deploys, but no MCP commit can happen, because
`MCP_COMMIT_ENABLED` defaults to false. It still waits on the unattended gateway test (phase 1 exit) before merging.

**Phase 2 global constraints** (in addition to the ones above):
- **Writes are the only thing the read-only session factory doesn't cover.** Write tools use a separate
  `write_session_factory()`: same engine URL and 10 s statement timeout, not read-only.
- **No raw SQL, no file paths in tool args.** Workbooks are built in memory from the validated input and the latest
  committed scores import's bytes.
- **Every refusal is an MCP tool error** with a stable `code` and a plain message, and it writes an `mcp_operations`
  row with `status="refused"`, plus an `audit_log` row (`role="mcp"`, action `mcp.refuse`).
- **Same names and values as the spec.**
  - `MCP_COMMIT_ENABLED`: bool, default false.
  - `MCP_PREVIEW_TTL`: seconds, default 3600.
  - `MCP_BACKUP_DIR`: default `/backups`.
  - Previews older than the TTL are expired.
  - Week date rules: a Sunday; later than the last committed event; at most 14 days before today in
    America/Los_Angeles; no existing rounds.
  - Corrections: the latest committed Sunday only, at most 5 rows, no deletes, no new names.
  - At most 200 shooters.
- **The model never commits a correction.** `commit_week` always refuses a correction preview. Only the approve CLI
  commits corrections.

### Task 4: `mcp_operations` table and audit access
**Files:**
- Create: `backend/migrations/versions/0011_mcp_operations.py`, `backend/src/sunday_clays/models/mcp.py`.
- Modify: `models/__init__.py`, `mcp/reads.py` (`get_job`), `mcp/server.py` (the `get_job` arg accepts an int job id
  or a uuid string).

**Model `McpOperation`:**
- Columns:
  - `id: UUID` (pk, default uuid4)
  - `kind: str` (`week|correction`)
  - `event_date: date`
  - `caller: str | None`
  - `status: str` (`previewed|committed|rolled_back|expired|refused`, with a check constraint)
  - `scores_import_id: int | None` (FK imports), `stations_import_id: int | None` (FK imports)
  - `idempotency_key: str | None` (unique)
  - `commit_path: str | None` (`mcp-auto|cli-approve|web-ui-approve`, with a check constraint)
  - `backup_file: str | None`
  - `job_id: int | None`
  - `created_at`, `committed_at`, `rolled_back_at` (timestamptz)
  - `result: dict` (jsonb, default `{}`)
- Index on `(status, created_at)`.

**`get_job(session, ref: int | UUID)`:**
- For a uuid, return `OperationStatus`: `{preview_id, kind, event_date, status, commit_path, scores_import_id,
  stations_import_id, job_id, backup_file, created_at, committed_at, rolled_back_at}`.
- A missing id is NotFound, as for jobs.

**Tests:**
- `test_migration_0011_upgrade_downgrade`: upgrade, then downgrade, then upgrade, the way the existing migration tests do
  it.
- `test_status_check_constraint_rejects_unknown`
- `test_idempotency_key_unique`
- `test_get_job_by_preview_id`
- `test_get_job_unknown_uuid_not_found`
- Over MCP: `get_job` accepts a uuid string and still rejects ints below 1 or above 2^31-1.

### Task 5: Workbook builders (`mcp/build.py`)
Port of the private skill's `build.py`. Read it at `~/code/sunday-clays/.claude/skills/import-weekly-scores/scripts/build.py`.
It contains no real names; keep it that way.

**Inputs:**
- `WeekInput` (pydantic, `extra="forbid"`): `{date, stations: list[str] (1-12, each a station label like "7" or "7A"),
  counts: list[int] (1-10 each, same length, sum 50), expected_total: int | None, shooters: list[ShooterRow] (1-200)}`.
- `ShooterRow`: `{name: "Last, First" (3-60 chars, one comma), score: 0-50, status: "Member"|"Guest",
  class_: str | None (alias "class"; one of the known gauge classes in `ingest/scores.py` `_GAUGES` values, or
  `"Pump"`), hits: list[int] | None}`.
- Validators:
  - no duplicate names, compared case-insensitively;
  - each `hits` has the same length as `stations`, each value is within 0..count, and the sum equals `score`;
  - when `expected_total` is set, it equals the sum of scores.
- `CorrectionInput`: `{date, rows: list[CorrectionRow] (1-5)}`, where `CorrectionRow` is `{name, score, hits | None}`.

**Functions:**
- `build_scores(base: bytes, week: WeekInput) -> bytes`: append the rows to "ALL SCORE DETAIL", sorted by score
  descending, and set or append the "Attendance History" count. It raises `BuildError("date_present")` if the base
  already has that date.
- `build_stations(week: WeekInput) -> bytes | None`: None if no shooter has hits.
- `build_correction(base: bytes, c: CorrectionInput) -> tuple[bytes, bytes | None]`: rewrite the score (and class
  untouched) for each named row on that date. Raise `BuildError("name_not_on_date")` for a name that isn't there. The
  stations workbook covers only the corrected rows that have hits.

**Tests:**
- Hypothesis on `WeekInput` validation: generated valid weeks round-trip, and each rule violation is rejected.
- `build_scores` output parses with `ingest.parse_upload` and has exactly the new rows for the date. Use the fixture
  scores workbook as the base.
- `build_stations` output parses as stations, with the right station labels and counts.
- `build_correction` changes only the named rows.
- `date_present` and `name_not_on_date` raise.

### Task 6: Pre-import dump (`mcp/backup.py`) and service wiring
**`pre_import_dump(preview_id: UUID, *, backup_dir: Path, database_url: str) -> Path`:**
1. Convert the SQLAlchemy URL to a libpq URI without the password, and pass the password as `PGPASSWORD` in the
   child's environment, so it never appears in argv.
2. Take an exclusive `fcntl.flock` on `backup_dir/backup.lock`, waiting at most 600 s.
3. Run `pg_dump --format=custom --exclude-table-data=response_cache --file=<tmp>` to
   `pre-import-<preview_id>-<UTC %Y%m%dT%H%M%SZ>.dump.tmp`.
4. Verify with `pg_restore --list <tmp>`.
5. Require the size to be ≥ 1 MiB (`MIN_DUMP_BYTES`, overridable for tests). Then rename to `.dump`.
6. Prune to the newest 20 `pre-import-*.dump`, never touching other files.
7. Any failure raises `BackupError`, removes the tmp file, and leaves nothing behind.

**Tests** (fake `pg_dump` and `pg_restore` scripts on PATH via monkeypatch):
- the success path names and keeps the file;
- each of these raises and leaves no tmp: a failing pg_dump, a failing pg_restore, a too-small dump;
- prune keeps 20 and leaves `sc-*.dump` alone;
- the password is not in argv (the fake records argv);
- the lock is honoured (a held lock with a short timeout raises).

One integration test with the real `pg_dump` against the test container: it produces a restorable dump. Mark it
`@pytest.mark.slow` if the suite has that marker; otherwise keep it.

**Wiring:**
- In `compose.swarm.yaml`, the `mcp` service gains the bind `/var/data/sunday-clays/backups:/backups` (the same source
  as `backup`) and `MCP_BACKUP_DIR=/backups`.
- In `check_stack.py`, the rule allows that bind on `mcp`.
- Update the stack tests.
- Add `MCP_COMMIT_ENABLED: "false"` explicitly to the mcp environment.

### Task 7: `preview_week` and `preview_correction`
**Files:** `mcp/writes.py` (the logic, on a `Session`) and `mcp/server.py` (the tools).

**`preview_week(session, week, *, now) -> WeekPreview`:**
1. Sweep expired previews first: any `previewed` older than the TTL becomes `expired`, and its pending imports are
   discarded.
2. Apply the date rules.
3. Base = bytes of the latest committed scores import. With none, refuse (`no_base`).
4. Build both workbooks, then `stage_import` each (stations only if built).
5. Gate on the scores diff: `events_added == [date]`, `events_removed == []`, `rows_removed == 0`,
   `rows_changed == 0`. Otherwise `discard_import` both, then refuse with `not_append_only`.
6. Insert an `mcp_operations` row with `status="previewed"` and an `audit_log` row (`mcp.preview`).

`WeekPreview` fields, in this order:
- `date`, `head_count`, `score_sum`, `average`;
- `new_names`, `possible_duplicates`;
- `findings_for_date` (FindingOut for that date);
- `historical_findings` (a count);
- `preview_id`, `expires_at`;
- `note` (set when `len(new_names) > 3`: check `find_shooters`).

**`preview_correction(session, c, *, now) -> CorrectionPreview`:**
- The date must be the latest committed event, and every name must be on it.
- Build, stage, then gate: `rows_changed == len(rows)`, with `rows_added == rows_removed == 0` and no events
  added or removed. Otherwise discard and refuse.
- Returns `needs_human_approval: true`.

**Refusal codes:** `not_sunday`, `not_after_last_event`, `too_old`, `date_has_rounds`, `no_base`, `not_append_only`,
`not_latest_event`, `name_not_on_date`, `invalid_input`.

**Tests:**
- Each refusal code. Assert no pending imports remain afterwards, and an `mcp_operations` row is marked refused.
- A happy path on the fx world, with the clock frozen so the next Sunday is valid.
- Expiry sweep.
- Duplicate preview of identical bytes: `stage_import` returns `duplicate_of`. Treat that as the same preview: return
  the existing preview_id if it is still `previewed`; otherwise refuse with `duplicate`.
- Over MCP: both tools are listed with bounded schemas, and a refusal comes back as `isError` with the code in the text.

### Task 8: `commit_week` and `rollback_week`
**`commit_operation(session, preview_id, *, idempotency_key, commit_path, allow_correction, now, dump=pre_import_dump)`:**
the shared commit steps.
1. Lock the `mcp_operations` row `FOR UPDATE`.
2. If a row already has this idempotency key, return its stored `result`, provided it is for the same preview;
   otherwise refuse `key_reused`.
3. The row must be `previewed` and within the TTL (else `expired`).
4. `kind == "correction"` requires `allow_correction` (else `correction_needs_human`).
5. Dump; a `BackupError` refuses with `backup_failed`.
6. `commit_import` for scores, then stations.
7. `enqueue(session, "rebuild", dedupe_key="rebuild")`.
8. Update the row: committed, path, key, backup file, job id, result. Write `audit_log` (`mcp.commit`).

**`commit_week` tool:**
- Refuses `commits_disabled` unless `MCP_COMMIT_ENABLED`. The message says a human commits during the preview-only
  period, and gives the approve command with the preview_id.
- Otherwise calls `commit_operation(..., commit_path="mcp-auto", allow_correction=False)`.

**`rollback_operation(session, preview_id, *, idempotency_key, now, dump)` and the `rollback_week` tool:**
- Gated like commit.
- The operation must be `committed`; its scores import must be the active one (`active_scores_import`); and its date
  must be the latest event. Otherwise refuse `not_latest`.
- Dump, then `rollback_import` both, enqueue a rebuild, mark the row `rolled_back`, and audit `mcp.rollback`.

**Tests:**
- Disabled by default.
- A correction is refused even when enabled.
- Expired.
- A key reused with a different preview.
- The same key returns the same result, without a second dump.
- A dump failure changes no import status. Assert both imports are still `pending`.
- The happy path commits both, enqueues a rebuild and records the backup file.
- Rollback refuses a non-latest import, and the happy path works.

### Task 9: Approve CLI and the skill update
**`python -m sunday_clays.mcp.approve <preview_id> [--yes]`:**
- Prints the preview summary from `mcp_operations` plus the stored import previews (date, head count, sum, new
  names, findings count, kind).
- If stdin is a TTY, requires typing `yes`; `--yes` is for non-interactive runs by the owner.
- Calls `commit_operation(commit_path="cli-approve", allow_correction=True)` with a fresh key `cli-<uuid4>`.
- Prints the job id and the backup file.
- Exit codes: 0 committed; 1 refused, with the code printed; 2 bad args.

**Tests:** the confirm prompt (yes and no), `--yes`, a refusal exit code, and committing a correction.

**Docs:**
- In `deploy/README.md` "Scores MCP": the preview-only period, how to approve (`docker exec` into the mcp task, then
  `python -m sunday_clays.mcp.approve <id>`), and how to turn on auto-commit later (`MCP_COMMIT_ENABLED=true`, the
  owner's call).
- In the private skill (outside this repo): an MCP section.
