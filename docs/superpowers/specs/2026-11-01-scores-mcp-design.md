# Scores MCP: weekly score import over MCP

Status: approved by the owner 2026-11-01. Nothing is built yet.

## Why

Each week the club's newsletter editor emails a "Sunday Clays Update" PDF. It has the newsletter, then one scanned
scoresheet per squad, and sometimes a typed results table. Today a Claude Code session imports it by hand, and the
procedure is written up in the private repo's `import-weekly-scores` skill.

The goal is for an AI agent that reads the owner's inbox to run the import itself: read the PDF, then preview and
(later) commit the Sunday through a narrow MCP server. The owner stays in control of any write.

## Goals
- A remote MCP server that exposes the import as a few narrow tools. Clients reach it through an external MCP gateway
  that the deployment provides (see "Gateway contract").
- Append-only weekly imports with strict server-side limits, because the input chain (email → PDF → model) is untrusted.
- A fail-closed database dump before every write.
- **Preview-only at launch.** For the first 3 weeks, every commit is made by a human. Turning on auto-commit takes
  the owner's word and a config flip.
- Every MCP write is audited and readable back through a tool.

## Non-goals
- The server does not read PDFs or images. The model reads the scans and sends structured scores.
- No OAuth or login code in the app. The gateway handles user sign-in, and the app only checks the gateway's shared
  upstream bearer.
- No raw SQL, no file paths in tool arguments, and no general-purpose write tools.
- No routing, hostname or gateway configuration in this repo. That belongs to the deployment.
- No special-event imports over MCP.

## Anti-goals (a failure even if it "works")
- A model with the connector being able to change or delete existing committed scores, or commit a correction.
- A write that happens without a verified dump.
- Real club members' names reaching any shared or public endpoint. The gateway admits only the owner.

## Architecture

**Service.** A new `mcp` service in the `sundayclays` swarm stack.
- **Image and entrypoint.** Same backend image, different entrypoint: `python -m sunday_clays.mcp`, streamable
  HTTP on `:8080/mcp`.
- **Package.** Code lives in `backend/src/sunday_clays/mcp/` and uses the official Python MCP SDK (`mcp` package).
- **Network.** Joins an external gateway network (name supplied at deploy time) with alias `sundayclays-mcp`, plus the
  stack's internal network for the DB. It joins no other external network.
- **Placement and limits.** Not pinned to the db node; x86 placement like api/worker is fine. Multi-arch image.
  Memory limit 384M, reservation 128M.
- **Egress.** DB only, no outbound internet. Enforced by the deployment.
- **Secrets.** `database_url`, `db_password` (for pg_dump) and the gateway's shared upstream bearer (an external secret
  whose name is supplied at deploy time). Values never appear in logs.
- **Volume.** `/var/data/sunday-clays/backups:/backups`, the same bind the backup service uses (NFS-shared).

**Path in.** MCP client → gateway (OAuth sign-in, owner only) → gateway network → `sundayclays-mcp:8080/mcp`, with
`Authorization: Bearer <shared upstream token>`.

**Auth in the app.** Every request must carry `Authorization: Bearer <token>`, compared in constant time. A missing or wrong bearer gets 401 with no detail. `/healthz` is unauthenticated and returns no data.

## Tools

All inputs are strict pydantic models: `extra="forbid"`, bounded lengths and counts. The outputs are JSON. Tool
descriptions carry the procedure from the skill, with the gotchas below written in, so the model reading the scans
follows the same rules.

### Read
- **`find_shooters(query: str, limit: int = 10)`**
  - Searches by name substring or tokens.
  - Returns `display_name`, `rounds`, `last_shot`, `usual_status`.
  - Used to map handwriting to existing spellings.
- **`get_event(date)`**
  - Returns: head count, round type, `stats_excluded`, target total, number of rows, score sum, station layout
    (with `dropped`) and data issues.
  - No per-shooter rows by default. With `include_rows=true` it returns name and score per shooter.
- **`get_job(id)`**
  - Accepts either a rebuild job id or a `preview_id`.
  - Returns the status, plus the audit row for a preview.

### Write (narrow)

**`preview_week(week: WeekInput)`**
- **Input.** `WeekInput` is `{date, stations[], counts[], expected_total?, shooters[]}`. Each shooter is
  `{name "Last, First", score 0–50, status Member|Guest, class?, hits?[]}`, with the same rules as the skill's
  `build.py`:
  - `counts` sum to 50;
  - `hits` per station are between 0 and that station's count, and sum to `score`;
  - no duplicate names;
  - 1–200 shooters;
  - `class` is in the known set (`Pump`, `SxS`, `Sub-Gauge`, `12/20/28 Gauge`) or null.
- **Date rules.** The date must:
  - be a Sunday;
  - be later than the last committed event;
  - be no more than 14 days before today (America/Los_Angeles);
  - have no existing rounds.
- **What it does.**
  1. Loads the latest committed scores import's bytes as the base.
  2. Appends the rows and sets the Attendance History count.
  3. Builds the stations workbook.
  4. Stages both through `stage_import`.
- **Refusals.** It refuses, and discards both staged imports, if the scores diff shows `rows_removed > 0`,
  `rows_changed > 0`, `events_removed`, or any `events_added` other than the date. That makes it append-only by
  construction, independent of the model.
- **Returns.**
  - At the top: `date` and `head_count`.
  - Then: `score_sum`, `average`, `new_names`, `possible_duplicates`, the findings for that date (with the known
    historical warnings filtered into a count) and `preview_id`.
  - A note when `new_names` has more than 3 entries, saying to check `find_shooters`.

**`preview_correction(date, rows: [{name, score, hits?}])`**
- **Limits.** The date must be the latest committed Sunday. At most 5 rows. Every name must already be on that date.
  No deletes and no new names.
- **What it does.** Builds a corrected scores file from the latest base, and a stations file too if any hits were given.
- **Diff check.** The diff must show exactly the requested rows changed and nothing else.
- **Returns.** A preview with `needs_human_approval: true`.

**`commit_week(preview_id, idempotency_key)`**
- **Refusals.** It refuses when:
  - `MCP_COMMIT_ENABLED` is false. This is the launch state: the refusal message says a human commits during the
    preview-only period.
  - the preview is a correction. This is always refused: no MCP path can commit a correction.
  - the preview is older than 1 hour.
  - the preview was made by a different caller (the gateway does not forward caller identity, so this check is unused).
  - the preview is not `previewed`.
- **Idempotency.** The same `idempotency_key` returns the stored result of the first call. A different key on an
  already committed preview is refused.
- **Commit steps.** These are shared with the human approve path (below):
  1. Run the pre-import dump. Fail closed.
  2. Commit scores, then stations.
  3. Queue a rebuild, with `dedupe_key="rebuild"`.
  4. Write the audit row.
  5. Return `job_id` and `backup_file`.

**`rollback_week(preview_id, idempotency_key)`**
- Only for the latest committed MCP or human import whose date is still the latest event, and not superseded by any
  later committed scores import.
- Runs the dump, rolls back both imports through `rollback_import`, then queues a rebuild.
- Gated by `MCP_COMMIT_ENABLED` like commit.

### Human approve path (outside the MCP)
`python -m sunday_clays.mcp.approve <preview_id> [--correction]`, run in the api container by the owner, or by a
Claude Code session the owner is typing into.
- **What it does.** Prints the preview summary, asks for a typed `yes` on a TTY, then runs the same commit steps.
- **Corrections.** Works for both week and correction previews.
- **Audit.** Records `commit_path = "cli-approve"`.

This is how commits happen during the preview-only period. A web-UI approve button may come later and would record
`web-ui-approve`.

## Pre-import dump
- **What runs.** In-process `pg_dump --format=custom --exclude-table-data=response_cache` to
  `/backups/pre-import-<preview_id>-<UTC stamp>.dump.tmp`. That is verified with `pg_restore --list`, then checked for
  size above a floor (1 MiB), then renamed to `.dump`.
- **Failure.** Any failure aborts the write with a clear error.
- **Retention.** Keep the newest 20 `pre-import-*.dump` and delete only files matching that pattern in `/backups`.
- **The nightly backup is unaffected.** `backup_tools.py prune` only matches `sc-*.dump`, and the distinct prefix keeps
  these dumps from masking a stale nightly dump in the backup watch.
- **Locking.** Takes the same `backup.lock` flock as `backup.sh`, so it never races the nightly dump.

## Audit table `mcp_operations` (new migration)
- **Columns.**
  - `id` (uuid4 preview_id)
  - `kind` (week|correction)
  - `event_date`, `caller` (nullable), `created_at`
  - `status` (previewed|committed|rolled_back|expired|refused)
  - `scores_import_id`, `stations_import_id` (nullable)
  - `idempotency_key` (unique, nullable), `commit_path` (mcp-auto|cli-approve|web-ui-approve)
  - `backup_file`, `job_id`
  - `committed_at`, `rolled_back_at`
  - `result` (jsonb)
- **Readable** via `get_job`.
- **Every write is also logged** to `audit_log` with role `mcp` and the action `mcp.preview`, `mcp.commit`,
  `mcp.rollback` or `mcp.refuse`.
- **Expiry.** Previews over 1 hour old are swept to `expired` and their pending imports discarded. This happens lazily
  on the next preview call, and on a scheduler tick.

## Config
- `MCP_COMMIT_ENABLED` is a bool and defaults to false.
- `MCP_AUTH_TOKEN_FILE` is the path of the secret file.
- `MCP_PREVIEW_TTL` defaults to 3600.
- `MCP_BACKUP_DIR` defaults to `/backups`.

## Phasing
1. **Phase 1, read-only:**
   - service skeleton, bearer auth, `/healthz`;
   - `find_shooters`, `get_event`, `get_job` (jobs only);
   - compose service and CI image.
   Ship it, and the deployment connects it to the gateway. Then **test an unattended scheduled agent run calling a
   read tool through the gateway after the sign-in session would have expired.** If that fails, stop and redesign auth.
2. **Phase 2, writes:** `mcp_operations` migration, pre-import dump, `preview_week`, `preview_correction`,
   `commit_week` (disabled by config), `rollback_week` and the approve CLI.
3. **Phase 3, after 3 weeks of preview-only and the owner's word:** set `MCP_COMMIT_ENABLED=true`.

## Testing
- TDD with RED then GREEN evidence on every task. Tests run against testcontainers Postgres, like the rest of the
  backend.
- **Real encoded-request tests.** Drive the ASGI app over HTTP with the MCP streamable-HTTP client: initialize, list
  tools, call tools. Include missing and wrong bearer (401).
- **Property tests (hypothesis) for `WeekInput` validation.**
- **Append-only refusal.** A week whose rows collide with or alter history is refused, and leaves no pending imports.
- **Commit refusals.** commit_week refuses a correction preview, an expired preview, a disabled config, and a reused key
  with a different preview. The same key returns the same result.
- **Dump failure aborts the write.** Simulate a failing `pg_dump` and assert no import changes status.
- **Rollback refuses a non-latest import.**
- **Fixture data.** Only the repo's pseudonymous fixture names. Never real names.

## Left to the builder
- Module layout inside `sunday_clays/mcp/`.
- The exact search ranking for `find_shooters`.
- The scheduler wiring for the expiry sweep.
- Exact wording of the tool descriptions. They must carry the skill's rules:
  - count marks, not row totals;
  - a thrown-out station is credited perfect for everyone;
  - drop a card's hits if they can't be reconciled;
  - use existing name spellings.

## Gateway contract
- **Upstream auth.**
  - The gateway sends `Authorization: Bearer <shared upstream token>` on every call. Any other gateway headers are
    ignored.
  - The token is read from `MCP_AUTH_TOKEN_FILE` (a swarm secret mounted at `/run/secrets/mcp_token`).
  - Refuse to start if the token is unset or empty, unless `MCP_AUTH_DISABLED=1`, which is for tests and dev only.
  - ASGI middleware compares the token in constant time and returns 401 on a mismatch.
- **Caller identity.** Not forwarded. So `caller` stays null, and the commit gate is: unguessable preview_id, plus
  1-hour expiry, plus `MCP_COMMIT_ENABLED`, plus the audit trail.
- **Transport.**
  - Python MCP SDK `mcp==1.30.0` with FastMCP and streamable HTTP, SDK defaults (sessions).
  - `host 0.0.0.0`, port from `MCP_PORT` (default 8080), path `/mcp`.
  - Served as `mcp.streamable_http_app()` wrapped in the bearer middleware under uvicorn.
- **Deploy-time names.** The compose file uses neutral defaults, overridden from the private deploy environment:
  - `SC_MCP_NETWORK` (default `mcp_gateway`): the gateway's external network. The service has alias `sundayclays-mcp`.
  - `SC_MCP_TOKEN_SECRET` (default `sundayclays_mcp_token`): the external secret holding the bearer.
