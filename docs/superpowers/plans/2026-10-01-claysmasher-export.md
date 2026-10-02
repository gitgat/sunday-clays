# ClaySmasher Export and Shooter-Page Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the ClaySmasher app what it needs from Sunday Clays: a one-call shooter export endpoint, and an "Import into ClaySmasher" button on the shooter page that links to `https://claysmasher.com/link/sunday-clays?shooter=<id>` and stays hidden behind a flag.

**Architecture:** A new auto-discovered route module `api/routes/claysmasher.py` (viewer auth comes from its module name) serves `GET /api/shooters/{id}/export`. It runs a fixed number of raw-SQL queries over the live tables and keys every round by its natural key, because `rebuild_live` renumbers round ids. Pure helpers live in `api/routes/_claysmasher.py`, which discovery skips. A new frontend feature `features/claysmasher/` adds a `profileSection` extension whose button is a plain outbound link to claysmasher.com. The claysmasher.com website (its own plan) serves the association files and the landing page, so this repo touches neither Caddy, the router, nor `features/shooters/`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 (`text()` SQL), Pydantic v2, pytest with a testcontainers Postgres 17; React 19, Vitest with Testing Library, lucide-react.

**Spec:** (ClaySmasher repo) `docs/superpowers/specs/2026-10-01-sunday-clays-link-design.md` (amended 2026-10-01 with U1, U2 and this plan's final contract; the amendments are binding). This plan implements §4.1, §4.2, the Sunday Clays part of §7, and §11 step 1. §4.3 (association files and the `/link/sunday-clays` landing page) belongs to the claysmasher.com plan ((claysmasher.com repo) `docs/superpowers/plans/2026-10-01-sunday-clays-link.md`), and the app half to the ClaySmasher plan in that repo.

**Workspace:** branch `feat/claysmasher-export`, cut from `main` (ported onto `fc2a101`, after Plan 17 special events). Every command below runs from a checkout of that branch; `cd "$(git rev-parse --show-toplevel)"` is its root. Never open `secrets/` or any `.env*` file.

## Contract (final, cross-repo; the ClaySmasher plan matches this)

This is the **single source of truth** for the export JSON. The amended spec reproduces it verbatim in §4.1 (spec "Amendments (2026-10-01)" item 5), and the ClaySmasher plan must parse exactly this shape. The example is literal: every value shown is a value the endpoint can emit.

```json
{
  "schema_version": 1,
  "club": {"name": "Tri-County Gun Club", "event_name": "Sunday Clays", "city": "Sherwood", "region": "OR"},
  "shooter": {"id": 17, "display_name": "Doe, Jane"},
  "generated_at": "2026-10-01T18:00:00.123456Z",
  "rounds": [
    {
      "round_key": "2026-09-06:doe jane:1",
      "event_date": "2026-09-06",
      "ordinal": 1,
      "round_type": "sporting",
      "score": 41,
      "target_count": 50,
      "gauge_class": "12 Gauge",
      "status": "member",
      "updated_at": "2026-09-07T02:11:00.654321Z",
      "stations": [
        {"order": 1, "station_label": "4", "target_count": 8, "hits": 6}
      ]
    }
  ]
}
```

- **`round_key` (string) replaces `round_id` (int).** The format is `"{event_date}:{name_key}:{ordinal}"`, and ClaySmasher stores it as an opaque string. `round_id` is **never** emitted. `schema_version` stays `1`, because no consumer exists yet.
- Rounds are sorted by `event_date` ascending, then `ordinal` (the per-day number below).
- `ordinal` is the shooter's 1-based round number on that day (ruling 2). The `ordinal` inside `round_key` is the club's native ordinal. The two differ only when a merge left one shooter with rounds under two name keys on the same day.
- `stations` is `[]` when the round has no linked station entries. When it is non-empty, `target_count == sum(station.target_count)`. When it is empty, `target_count` is `50`. `score` and the station `hits` are exported exactly as recorded and may disagree.
- `status` is one of `"member"`, `"guest"`, `"deceased"` (lowercase, `ingest/scores.py` `_STATUSES`) or `null`. `gauge_class` is a display string such as `"12 Gauge"` or `null`.
- `updated_at` is **informational only** (ruling 4): coarse, not per-round. Consumers must not use it for change detection; ClaySmasher reconciles by its own fingerprint (spec §5.3).
- Timestamps are UTC ISO-8601 with a `Z` suffix and may carry microseconds.
- **404, unknown shooter:** `{"error":{"code":"shooter_not_found","message":"No shooter with id N"}}`
- **404, merged-away shooter:** `{"error":{"code":"shooter_merged","message":"Shooter N was merged into M"},"merged_into":M}`. `merged_into` is a **top-level** sibling of `error`, not a bare `{"merged_into": M}` body.
- **401** without a session cookie: `{"error":{"code":"unauthenticated","message":"Log in to continue"}}`
- A 200 carries `Cache-Control: private, no-cache` and a weak `ETag`, and answers `304` to a matching `If-None-Match`. This comes from the existing middleware.
- Login for a non-browser client: `POST /api/auth/login` with JSON `{"password": "..."}` sets the session cookie; a wrong password answers `401` `{"error":{"code":"invalid_password",...}}`. Task 5 checks this path through Cloudflare with a Dart user agent.
- **Special Sundays are not exported (Plan 17).** `rounds` lists only rounds on regular Sundays (`events.kind = 'regular'`). A special Sunday such as the 3-Bird Shoot (`kind = 'special'`, its own `label` and `target_total`, e.g. 10 stations x 6 = 60) counts only as an appearance at the club, and its rounds are left out of the export entirely, stations included. Rationale: its rounds carry a real score, but out of a different format and target total; its `round_type` defaults to `sporting` (Plan 17 Decision 16), and ClaySmasher maps any `round_type` it does not know to Sporting, so exporting it would import a 3-bird score as a Sporting round (a bogus score and PB in the app). This matches the club's own rule that a special Sunday's score stays out of every score-based number, and `GET /api/shooters/{id}/rounds` staying regular-only. A shooter whose only Sunday was special exports `200` with `"rounds": []`. Contract fields and types are unchanged; a future special format worth importing would need its own `round_type` value and a ClaySmasher change first. Pinned by `backend/tests/integration/special/test_special_claysmasher_export.py`.

### Spec amendments (recorded here and in the PR body)

The spec's original §4.1 example showed `"round_id": 9123`, `"status": "Member"` and a bare `{"merged_into": 23}`. Both plans implement the following instead, and the spec now carries them (its "Amendments (2026-10-01)" item 5 and the rewritten §4.1):

1. `round_key` only; no `round_id` (ruling 1).
2. `ordinal` is the per-day ordinal (ruling 2).
3. `target_count` is the sum of the stations' targets, else `50` (ruling 3).
4. 404 uses the standard error envelope plus a top-level `merged_into` (ruling 5).
5. `status` is lowercase `member|guest|deceased|null`.
6. `updated_at` is coarse and informational (ruling 4).

The same amendment (items 1 and 2 of the spec's list) moved the link host to claysmasher.com (U1, ruling 7): Sunday Clays serves **no** `/.well-known/*` files and **no** landing route. Nothing in this plan edits `deploy/caddy/Caddyfile`, `compose.swarm.yaml` or `deploy/README.md`.

### Decisions already taken (2026-10-01)

- **U1, link host.** The button links to `https://claysmasher.com/link/sunday-clays?shooter=<id>`, a different domain from the page it sits on, so iOS and Android hand the tap to the app. This resolves the same-domain universal-link risk the earlier draft of this plan raised (ruling 11). The residual risk sits on the claysmasher.com side: GitHub Pages serves the extensionless AASA as `application/octet-stream`. The claysmasher.com plan validates it through Apple's CDN after its deploy. If Apple rejects it, the fallback is the custom scheme `claysmasher://sunday-clays/link?shooter=<id>`, which this plan pre-builds as a second link mode (ruling 8), so switching is a one-line constant change.
- **U2, unlink and re-link.** ClaySmasher-only (detached markers, re-attach, tombstones). Nothing in Sunday Clays changes for it: the export is stateless, and the stable `round_key` (ruling 1) is what lets the app re-attach detached rounds without duplicates.

## Rulings on spec ambiguities

1. **`round_id` is unstable, so the export uses `round_key`.** `domain/rebuild.py:124-137` clears every live table with `DELETE` and never restarts the identity sequences. `_write_rounds` inserts rounds without ids. `backend/tests/integration/domain/test_rebuild_live.py:606-613` asserts that a rebuild over identical inputs gives new ids: `min(new ids) > max(first_ids)`. A rebuild runs on every import commit and rollback, every rule creation and deactivation, and every shooter merge or rename. The natural key `(event_date, name_key, ordinal)` is DB-unique (`uq_rounds_event_date_name_key_ordinal`), and the overlay rules already target rounds by it. Task 3 pins its stability across a re-import.
   - The key changes in two documented cases: a corrected raw score that re-ranks two rounds on one day (ordinals are ranked by raw score), and a re-spelled name. ClaySmasher sees either case as one removal plus one addition.
2. **`ordinal` is the shooter's per-day number.** Reason: after a merge, two rounds on one day can both have native ordinal 1. ClaySmasher titles a session "Round {ordinal}" and times a day's second round at 10:01, so it needs distinct 1..n numbers.
3. **`target_count`** is the sum of the round's station targets when it has stations, otherwise 50 (`LAYOUT_TOTAL`). This keeps the invariant `sum(stations.target_count) == target_count` that ClaySmasher's targets check needs, even on a sheet whose layout is not 50 (`layout_total_not_50`).
4. **`updated_at`** is the newest of these timestamps:
   - the newest `committed_at` / `rolled_back_at` of any scores import
   - the same for any stations import that has a sheet for the round's date
   - the newest `created_at` / `deactivated_at` of any `score_override` or `hide_round` rule on the round's natural key
   - the same for any `round_type_override` rule on its date

   Counting rollbacks means a rollback never moves `updated_at` backwards. If none of these exists (only in seeded test databases), `updated_at` is `generated_at`. The field is informational: ClaySmasher reconciles by its own fingerprint (spec §5.3), so a re-commit of identical content that bumps `updated_at` is harmless.

   **Known deviation from the original spec wording ("the latest change to that round's score, station hits or overlay rules"), accepted on purpose and now reflected in the amended spec §4.1:**
   - It is **coarse, not per-round.** The scores-import term is the newest scores import of any kind, so every scores import bumps every round's `updated_at`, changed or not.
   - It **ignores** `station_reset`, `set_status`, `rename_shooter`, `merge_shooter` and `alias_name` rules. These can change a round's exported station data, `status` or ownership, or (via `alias_name` / `merge_shooter`) which station entries link to it, without moving `updated_at`. `alias_name` has no date in its payload, so the only correct stamp for it would be a global one like the scores-import term.
   - Consumers must therefore **not** rely on `updated_at` for change detection. The ClaySmasher plan parses and ignores it, and the contract keeps the "informational only" wording. Making it exact is out of scope; if a future consumer needs it, add per-date `station_reset` stamps and per-shooter `set_status`/`merge_shooter`/`rename_shooter` stamps to `rule_stamps`.
5. **Merged shooter:** the route returns the standard error envelope plus a top-level `merged_into`, built as a `JSONResponse` because `install_error_handlers` cannot add fields. `merged_into` is the final target from `merge_map`, with chains already resolved.
6. **Stations** are the `station_hits` rows whose `round_id` is this round (it is NULL for unlinked entries), joined to `station_layouts` for `target_count`. `order` is the 1-based rank of the label within that event's whole layout, sorted by `label_sort_key` (4, 5, 6, 7, 7A, 8, 9, 10).
7. **The link host is claysmasher.com (U1), and Sunday Clays only links out.** The button is an outbound `<a>` to `https://claysmasher.com/link/sunday-clays?shooter=<id>`. Sunday Clays serves no association files and no landing route; the App Store / Play links, the "Open in ClaySmasher" retry and the pending Android SHA-256 all live on claysmasher.com (spec §4.3). The CSP is unchanged: it governs what the page loads, not where a top-level link navigates, and `Referrer-Policy: same-origin` sends no referrer to claysmasher.com, which needs none (the shooter id is in the query).
8. **The flag and the link mode** are constants in `frontend/src/features/claysmasher/links.ts`:
   - `CLAYSMASHER_BUTTON_ENABLED = false`. A merge to `main` auto-deploys, so turning the button on is a one-line PR after the ClaySmasher release ships and claysmasher.com's AASA is validated (spec §11 step 4). Doing that is out of this plan.
   - `CLAYSMASHER_LINK_MODE: ClaySmasherLinkMode = 'universal'`. The other value, `'scheme'`, is the spec §4.2 fallback for an AASA that Apple rejects: the button's `href` becomes `claysmasher://sunday-clays/link?shooter=<id>`, and a small "Don’t have ClaySmasher?" link to the claysmasher.com page sits under it, because a scheme link does nothing useful in a browser without the app. It is built and tested now so the fallback, if needed, ships in the same one-line flag-flip PR rather than as new code.
9. **Same tab, plain anchor.** The button is an `<a href>` with no `target`, no `rel` and no click handler. Reasons:
   - iOS and Android route a user-initiated top-level navigation to a claimed URL into the app; a script-driven or `window.open` navigation is not reliably treated as a link tap.
   - Without the app, the claysmasher.com page opens in the same tab, and the browser's Back returns to the shooter page. On a phone a new tab is a worse experience (tab switcher, no Back).
   - In scheme mode, a new tab would be left blank when the app opens.

   `ImportIntoClaySmasher.test.tsx` pins it (`is a plain same-tab link`).
10. **Branching:** the orchestrator assigned the single branch `feat/claysmasher-export`, so it replaces CONTRIBUTING's one-branch-per-task `task/<NN>-<T>-<slug>` stack. It lands as one PR. CI only checks branch names for `chore/ratchet-*`.
11. **Same-domain universal links: resolved by U1.** The earlier draft linked from `sundayclays.claysmasher.com` to the same host, which iOS keeps in Safari ("iOS respects the user's most likely intent and opens the link in Safari"). The link host is now claysmasher.com, a different domain from the shooter page. The landing page's own retry button, which *is* on claysmasher.com, uses the custom scheme for the same reason (spec §4.3). What remains is the on-device check before the flag flip (Task 5 Step 5).

## Global Constraints

- Export endpoint: `GET /api/shooters/{shooter_id}/export`, with the OpenAPI template kept as `{id}` (C8). Same auth as the other shooter routes: viewer or admin cookie, given by `role_dependencies` for a non-`admin_` module.
- Response field names exactly as in the contract above. The `club` values are exactly `"Tri-County Gun Club"`, `"Sunday Clays"`, `"Sherwood"`, `"OR"`.
- `round_type` is `"sporting"` or `"super_sporting"`, with unknown defaulting to sporting (already guaranteed by `events.round_type`).
- Performance target: under 300 ms for the largest **production** shooter, with a fixed query count (no N+1). The fixed query count is pinned in CI (`test_query_count_does_not_grow_with_rounds`). The 300 ms target is measured in production (Task 5 Step 4), because CI runners (with coverage, and `docker-arm64`) vary too much for a tight wall-clock bound; CI keeps a `@pytest.mark.slow` gross-regression ceiling over the `fx` dataset, as `tests/integration/insights/test_performance.py` does.
- Button: label "Import into ClaySmasher", `href="https://claysmasher.com/link/sunday-clays?shooter=<id>"`, same tab, hidden behind `CLAYSMASHER_BUTTON_ENABLED = false`. Fallback mode `'scheme'`: `href="claysmasher://sunday-clays/link?shooter=<id>"` plus a "Don’t have ClaySmasher?" link to the https URL.
- Sunday Clays serves no `/.well-known/*` files and no `/claysmasher/link` route (U1). The CSP is unchanged.
- No real member names or scores anywhere. Use only invented names: "Doe, Jane", "Roe, Rick", "Roe, Richard".
- CONTRIBUTING.md:
  - TDD.
  - Conventional Commits, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - No edits to `ratchets/`, dependency lists, `uv.lock` or `pnpm-lock.yaml`.
  - Coverage floors are 99% lines and 99% branches for both backend and frontend.
- Architecture contract: never edit `frontend/src/app/router.tsx`, `frontend/src/features/shooters/*` or `frontend/playwright.config.ts`. Never edit `backend/src/sunday_clays/api/app.py` to add a route.
- Backend gate (in `backend/`): `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch`. Docker must be running. Never set `TEST_DATABASE_URL` to a database another checkout uses.
- Frontend gate (in `frontend/`): `pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage`.

## Review Focus

1. **A merged shooter with two rounds on one day under different name keys** (`merged_same_day_rounds`). Expect two distinct `round_key`s and day ordinals 1 and 2, never two rounds both numbered 1. Pinned in Task 2 (`test_merged_same_day_rounds_get_distinct_keys_and_day_ordinals`).
2. **A station sheet entry that never linked to a round** (`station_hits.round_id IS NULL`, for example an unmatched name). Expect the round to export with `stations: []` and `target_count: 50`, never another round's hits. Pinned in Task 2 (`test_unlinked_station_entries_are_not_a_rounds_stations`).
3. **A layout that does not add up to 50, or hits that disagree with the score.** Expect the data exported as recorded, with `target_count` equal to the stations' sum. Pinned in Task 2 (`test_station_data_is_exported_as_recorded`).
4. **An import rollback.** Expect `updated_at` to move forward to the rollback time, never back to the older import's commit time. Pinned in Task 3 (`test_updated_at_moves_forward_on_reimport_and_on_rollback`).
5. **A phone tap on the button.** Expect a plain same-tab `<a>` to `https://claysmasher.com/link/sunday-clays?shooter=<id>` (a different host from the page, so the OS can open the app), never `target="_blank"`, never a `sundayclays.claysmasher.com` URL. Pinned in Task 4 (`ImportIntoClaySmasher.test.tsx`, `is a plain same-tab link to the claysmasher.com page`).
6. **Same-day merged keys whose order differs between the DB collation and codepoint order** (`"dela ann"` vs `"de la roe ann"`). Expect rounds listed in day-ordinal order (1 then 2). Pinned in Task 2 (`test_same_day_order_follows_day_ordinals_not_the_db_collation`), fixed by `ORDER BY ... name_key COLLATE "C"`.
7. **The scheme fallback on a phone without ClaySmasher.** A `claysmasher://` link does nothing there, so expect a second, ordinary link to the claysmasher.com page right under the button. Pinned in Task 4 (`scheme mode adds a web link for phones without the app`).

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `backend/src/sunday_clays/api/routes/_claysmasher.py` | Create | Pure helpers: `round_key`, `station_orders`, `day_ordinals`, `latest`, `rule_stamps`, `TARGETS_PER_ROUND`. Skipped by router discovery (leading `_`). |
| `backend/src/sunday_clays/api/routes/claysmasher.py` | Create | Router, `*Out` models, export SQL, the 404 / merged-shooter response. |
| `backend/tests/unit/api/test_claysmasher_helpers.py` | Create | Unit tests for the pure helpers (no DB). |
| `backend/tests/integration/analytics_core/test_claysmasher_export_route.py` | Create | Route tests over directly seeded live rows (`seed` fixture), plus the auth, N+1 and performance checks. |
| `backend/tests/integration/domain/test_claysmasher_export_rebuild.py` | Create | Tests through real imports, rebuilds, rules and merges: key stability, `merged_into`, `updated_at`. |
| `frontend/src/features/claysmasher/links.ts` | Create | Flag, link mode, the claysmasher.com page URL and the custom-scheme URL for a shooter. |
| `frontend/src/features/claysmasher/links.test.ts` | Create | Unit tests for links.ts. |
| `frontend/src/features/claysmasher/components/ImportIntoClaySmasher.tsx` | Create | The flag-gated "Import into ClaySmasher" link, in universal or scheme mode. |
| `frontend/src/features/claysmasher/components/ImportIntoClaySmasher.test.tsx` | Create | Ships off; universal href, same tab; scheme mode plus web link. |
| `frontend/src/features/claysmasher/profileSection.tsx` | Create | C10 extension: `placement: 'top'`, `bare: true`, order 5. |
| `frontend/src/features/claysmasher/profileSection.test.ts` | Create | The section is mounted where intended. |

---

### Task 0: Commit this plan

**Files:**
- Add: `docs/superpowers/plans/2026-10-01-claysmasher-export.md` (this file; untracked until now)

- [ ] **Step 1: Commit the plan so it lands in the PR and the tree is clean**

```bash
cd "$(git rev-parse --show-toplevel)"
git status --short   # expect only: ?? docs/superpowers/plans/2026-10-01-claysmasher-export.md
git add docs/superpowers/plans/2026-10-01-claysmasher-export.md
git commit -m "docs: ClaySmasher export plan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git status --short   # expect: empty
```

The lefthook pre-commit hook only matches `*.py` and frontend globs, so a Markdown file under `docs/` triggers no command.

---

### Task 1: Pure export helpers

**Files:**
- Create: `backend/src/sunday_clays/api/routes/_claysmasher.py`
- Test: `backend/tests/unit/api/test_claysmasher_helpers.py`

**Interfaces:**
- Consumes: `sunday_clays.station_label.label_sort_key(label: str) -> tuple[int, str]`
- Produces:
  - `TARGETS_PER_ROUND: int = 50`
  - `RoundNaturalKey = tuple[date, str, int]`
  - `round_key(event_date: date, name_key: str, ordinal: int) -> str`
  - `station_orders(labels: Iterable[str]) -> dict[str, int]`
  - `day_ordinals(keys: Iterable[RoundNaturalKey]) -> dict[RoundNaturalKey, int]`
  - `latest(*stamps: datetime | None) -> datetime | None` (the result is in UTC)
  - `rule_stamps(rules: Iterable[tuple[str, Mapping[str, Any], datetime]]) -> tuple[dict[RoundNaturalKey, datetime], dict[date, datetime]]`

- [ ] **Step 1: Prepare the toolchain (first task only)**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv sync && docker info --format '{{.ServerVersion}}'`
Expected: uv finishes without changing `uv.lock` (`git status --short` is empty, because Task 0 committed the plan), and Docker prints a server version.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/unit/api/test_claysmasher_helpers.py`:

```python
"""Pure helpers behind the ClaySmasher export (spec 2026-10-01 §4.1); no database."""

from datetime import UTC, date, datetime, timedelta, timezone

from sunday_clays.api.routes._claysmasher import (
    TARGETS_PER_ROUND,
    day_ordinals,
    latest,
    round_key,
    rule_stamps,
    station_orders,
)

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)


def test_round_key_is_the_natural_key_joined_by_colons() -> None:
    assert round_key(D1, "doe jane", 2) == "2026-09-06:doe jane:2"
    # one-token identity keys carry their own @date; ':' never occurs in a key
    assert round_key(D1, "jane@2026-09-06", 1) == "2026-09-06:jane@2026-09-06:1"


def test_station_orders_rank_labels_in_station_order() -> None:
    assert station_orders(["10", "7A", "4", "7", "8", "4"]) == {
        "4": 1,
        "7": 2,
        "7A": 3,
        "8": 4,
        "10": 5,
    }
    assert station_orders([]) == {}


def test_day_ordinals_number_a_shooters_rounds_per_day() -> None:
    keys = [(D1, "doe jane", 1), (D1, "doe j", 1), (D1, "doe jane", 2), (D2, "doe jane", 1)]
    assert day_ordinals(keys) == {
        (D1, "doe j", 1): 1,
        (D1, "doe jane", 1): 2,
        (D1, "doe jane", 2): 3,
        (D2, "doe jane", 1): 1,
    }


def test_latest_is_the_newest_present_stamp_in_utc() -> None:
    pdt = timezone(timedelta(hours=-7))
    a = datetime(2026, 9, 7, 2, 11, tzinfo=UTC)
    b = datetime(2026, 9, 6, 20, 0, tzinfo=pdt)  # 2026-09-07T03:00Z
    newest = latest(a, None, b)
    assert newest == datetime(2026, 9, 7, 3, 0, tzinfo=UTC)
    assert newest is not None
    assert newest.tzinfo is UTC
    assert latest(None, None) is None
    assert latest() is None


def test_rule_stamps_key_round_rules_by_round_and_round_type_rules_by_day() -> None:
    t1 = datetime(2026, 9, 8, tzinfo=UTC)
    t2 = t1 + timedelta(days=1)
    rules = [
        (
            "score_override",
            {"event_date": "2026-09-06", "name_key": "doe jane", "ordinal": 1, "score": 45},
            t2,
        ),
        ("hide_round", {"event_date": "2026-09-06", "name_key": "doe jane", "ordinal": 1}, t1),
        ("round_type_override", {"event_date": "2026-09-06", "round_type": "super_sporting"}, t1),
        ("round_type_override", {"event_date": "2026-09-06", "round_type": "sporting"}, t2),
    ]
    by_round, by_day = rule_stamps(rules)
    assert by_round == {(D1, "doe jane", 1): t2}
    assert by_day == {D1: t2}


def test_a_round_without_stations_counts_fifty_targets() -> None:
    assert TARGETS_PER_ROUND == 50
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run pytest tests/unit/api/test_claysmasher_helpers.py -q`
Expected: FAIL on collection with `ModuleNotFoundError: No module named 'sunday_clays.api.routes._claysmasher'`.

- [ ] **Step 4: Write the implementation**

Create `backend/src/sunday_clays/api/routes/_claysmasher.py`:

```python
"""Pure helpers for the ClaySmasher export (spec 2026-10-01 §4.1; skipped by discovery).

Rounds are keyed by their natural key, (event_date, identity name_key, ordinal): rebuild_live
renumbers every live id, while this key is DB-unique and is what overlay rules target.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from sunday_clays.station_label import label_sort_key

# A round without station data: the club's 50-target round (ingest.validate.LAYOUT_TOTAL).
TARGETS_PER_ROUND = 50

RoundNaturalKey = tuple[date, str, int]


def round_key(event_date: date, name_key: str, ordinal: int) -> str:
    """The export's stable round id. Keys hold only [\\w\\s'-] and '@', so ':' is unambiguous."""
    return f"{event_date.isoformat()}:{name_key}:{ordinal}"


def station_orders(labels: Iterable[str]) -> dict[str, int]:
    """label -> 1-based position in station order (4, 5, 6, 7, 7A, 8) within one event."""
    ordered = sorted(set(labels), key=label_sort_key)
    return {label: position for position, label in enumerate(ordered, start=1)}


def day_ordinals(keys: Iterable[RoundNaturalKey]) -> dict[RoundNaturalKey, int]:
    """Natural key -> the shooter's 1-based round number that day, by (ordinal, name_key).

    Equal to the native ordinal unless a merge left one shooter with rounds under two name keys
    on the same day (both ordinal 1), which this numbers 1 and 2.
    """
    by_day: dict[date, list[tuple[str, int]]] = defaultdict(list)
    for event_date, name_key, ordinal in keys:
        by_day[event_date].append((name_key, ordinal))
    numbers: dict[RoundNaturalKey, int] = {}
    for event_date, rounds in by_day.items():
        ranked = sorted(rounds, key=lambda pair: (pair[1], pair[0]))
        for number, (name_key, ordinal) in enumerate(ranked, start=1):
            numbers[(event_date, name_key, ordinal)] = number
    return numbers


def latest(*stamps: datetime | None) -> datetime | None:
    """The newest of the given aware datetimes, in UTC; None when none is given."""
    present = [stamp for stamp in stamps if stamp is not None]
    return max(present).astimezone(UTC) if present else None


def rule_stamps(
    rules: Iterable[tuple[str, Mapping[str, Any], datetime]],
) -> tuple[dict[RoundNaturalKey, datetime], dict[date, datetime]]:
    """Newest change per targeted round and per event date from (rule_type, payload, changed_at).

    `round_type_override` targets a date; `score_override` and `hide_round` target a round key.
    """
    by_round: dict[RoundNaturalKey, datetime] = {}
    by_day: dict[date, datetime] = {}
    for rule_type, payload, changed_at in rules:
        day = date.fromisoformat(str(payload["event_date"]))
        if rule_type == "round_type_override":
            by_day[day] = max(by_day.get(day, changed_at), changed_at)
        else:
            key = (day, str(payload["name_key"]), int(payload["ordinal"]))
            by_round[key] = max(by_round.get(key, changed_at), changed_at)
    return by_round, by_day
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run pytest tests/unit/api/test_claysmasher_helpers.py -q && uv run pytest tests/unit/api/test_routes_discovery.py -q`
Expected: PASS. The discovery test still passes because `_claysmasher` starts with `_`.

- [ ] **Step 6: Lint, format, type-check, commit**

```bash
cd "$(git rev-parse --show-toplevel)"/backend
uv run ruff format src/sunday_clays/api/routes/_claysmasher.py tests/unit/api/test_claysmasher_helpers.py
uv run ruff check src/sunday_clays/api/routes/_claysmasher.py tests/unit/api/test_claysmasher_helpers.py
uv run mypy --strict src
cd ..
git add backend/src/sunday_clays/api/routes/_claysmasher.py backend/tests/unit/api/test_claysmasher_helpers.py
git commit -m "feat(api): pure helpers for the ClaySmasher export

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Export endpoint

**Files:**
- Create: `backend/src/sunday_clays/api/routes/claysmasher.py`
- Test: `backend/tests/integration/analytics_core/test_claysmasher_export_route.py`

**Interfaces:**
- Consumes: everything Task 1 produces. Also `SessionDep` (`sunday_clays.db`), `NotFoundError` (`sunday_clays.domain.errors`), `RoundType` (`sunday_clays.domain.round_type`), and the fixtures `seed` (analytics_core conftest, `LiveSeed`), `viewer_client`, `admin_client`, `anon_client`, `session`, `fx_session` and `fx_viewer_client` (root conftest).
- Produces:
  - `router: APIRouter` with `GET /api/shooters/{id}/export`, `response_model=ShooterExportOut`
  - the models `ClubOut`, `ExportShooterOut`, `ExportStationOut`, `ExportRoundOut`, `ShooterExportOut`
  - the constant `CLUB`
  - the handler `get_shooter_export(shooter_id: int, session: Session) -> ShooterExportOut`. Task 3 widens its return type to `ShooterExportOut | JSONResponse`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/integration/analytics_core/test_claysmasher_export_route.py`:

```python
"""GET /api/shooters/{id}/export over directly seeded live rows (spec 2026-10-01 §4.1)."""

import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from sunday_clays.station_label import label_number

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
# Gross-regression ceiling only (an accidental N+1 or full-table scan per round), not the 300 ms
# target: CI runners with coverage vary too much for that. 300 ms is checked in production (Task 5).
CI_CEILING_SECONDS = 1.0
SPORTING = (("4", 8), ("5", 8), ("6", 6), ("7", 8), ("8", 6), ("9", 8), ("10", 6))
SPORTING_HITS = (6, 7, 5, 6, 5, 7, 5)  # 41


def _station_entry(
    session: Session,
    d: date,
    round_id: int | None,
    shooter_id: int,
    key: str,
    layout: Sequence[tuple[str, int]],
    hits: Sequence[int],
    entry_row: int = 1,
) -> None:
    """One station-sheet entry as rebuild writes it: the event's layout plus this entry's hits."""
    for (label, targets), value in zip(layout, hits, strict=True):
        session.execute(
            text(
                "INSERT INTO station_layouts (event_date, station_no, station_label,"
                " target_count, source_import_id) VALUES (:d, :no, :l, :t, 0)"
                " ON CONFLICT (event_date, station_label) DO NOTHING"
            ),
            {"d": d, "no": label_number(label), "l": label, "t": targets},
        )
        session.execute(
            text(
                "INSERT INTO station_hits (event_date, station_no, station_label, sheet_id,"
                " entry_row, name_key, shooter_id, round_id, hits)"
                " VALUES (:d, :no, :l, 0, :row, :k, :s, :r, :h)"
            ),
            {
                "d": d,
                "no": label_number(label),
                "l": label,
                "row": entry_row,
                "k": key,
                "s": shooter_id,
                "r": round_id,
                "h": value,
            },
        )


def _export(client: TestClient, shooter_id: int) -> dict[str, Any]:
    response = client.get(f"/api/shooters/{shooter_id}/export")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@contextmanager
def _statements(session: Session) -> Iterator[list[str]]:
    seen: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        seen.append(statement)

    connection = session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(connection, "before_cursor_execute", record)


def test_export_shape(seed: Any, session: Session, viewer_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 41, gauge_class="12 Gauge", status="member")
    _station_entry(session, D1, rid, jane, "doe jane", SPORTING, SPORTING_HITS)
    seed.finish()

    body = _export(viewer_client, jane)

    assert body["schema_version"] == 1
    assert body["club"] == {
        "name": "Tri-County Gun Club",
        "event_name": "Sunday Clays",
        "city": "Sherwood",
        "region": "OR",
    }
    assert body["shooter"] == {"id": jane, "display_name": "Doe, Jane"}
    assert body["generated_at"].endswith("Z")
    # no import or rule exists in a seeded database, so updated_at falls back to generated_at
    assert body["rounds"] == [
        {
            "round_key": "2026-09-06:doe jane:1",
            "event_date": "2026-09-06",
            "ordinal": 1,
            "round_type": "sporting",
            "score": 41,
            "target_count": 50,
            "gauge_class": "12 Gauge",
            "status": "member",
            "updated_at": body["generated_at"],
            "stations": [
                {"order": n, "station_label": label, "target_count": targets, "hits": hits}
                for n, ((label, targets), hits) in enumerate(
                    zip(SPORTING, SPORTING_HITS, strict=True), start=1
                )
            ],
        }
    ]


def test_round_without_station_data_has_no_stations_and_fifty_targets(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 38, gauge_class=None, status=None)
    seed.finish()

    (only,) = _export(viewer_client, jane)["rounds"]

    assert (only["stations"], only["target_count"], only["score"]) == ([], 50, 38)
    assert (only["gauge_class"], only["status"]) == (None, None)


def test_two_round_day_lists_ordinals_1_and_2_in_date_order(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D2, jane, 41)
    seed.round(D2, jane, 35)
    seed.round(D1, jane, 30)
    seed.finish()

    rounds = _export(viewer_client, jane)["rounds"]

    assert [(r["round_key"], r["ordinal"], r["score"]) for r in rounds] == [
        ("2026-09-06:doe jane:1", 1, 30),
        ("2026-09-13:doe jane:1", 1, 41),
        ("2026-09-13:doe jane:2", 2, 35),
    ]


def test_super_sporting_event(seed: Any, viewer_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.event(D1, round_type="super_sporting")
    seed.round(D1, jane, 44)
    seed.finish()

    assert _export(viewer_client, jane)["rounds"][0]["round_type"] == "super_sporting"


def test_lettered_stations_come_out_in_station_order(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 39, ordinal=1)
    shuffled = (("8", 8), ("7A", 6), ("4", 7), ("10", 7), ("7", 8), ("5", 7), ("6", 7))
    _station_entry(session, D1, rid, jane, "doe jane", shuffled, (6, 4, 5, 6, 7, 5, 6))
    seed.finish()

    stations = _export(viewer_client, jane)["rounds"][0]["stations"]

    assert [(s["order"], s["station_label"], s["target_count"], s["hits"]) for s in stations] == [
        (1, "4", 7, 5),
        (2, "5", 7, 5),
        (3, "6", 7, 6),
        (4, "7", 8, 7),
        (5, "7A", 6, 4),
        (6, "8", 8, 6),
        (7, "10", 7, 6),
    ]


def test_unlinked_station_entries_are_not_a_rounds_stations(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    # the same day's sheet has an entry for an unmatched name: round_id is NULL
    _station_entry(session, D1, None, jane, "doe jayne", SPORTING, SPORTING_HITS)
    seed.finish()

    (only,) = _export(viewer_client, jane)["rounds"]

    assert (only["stations"], only["target_count"]) == ([], 50)


def test_station_data_is_exported_as_recorded(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    rid = seed.round(D1, jane, 40)
    short_layout = (("4", 8), ("5", 8), ("6", 6), ("7", 8), ("8", 6), ("9", 8), ("10", 4))  # 48
    _station_entry(session, D1, rid, jane, "doe jane", short_layout, (8, 8, 6, 8, 6, 8, 4))  # 48
    seed.finish()

    (only,) = _export(viewer_client, jane)["rounds"]

    assert only["score"] == 40
    assert only["target_count"] == 48 == sum(s["target_count"] for s in only["stations"])
    assert sum(s["hits"] for s in only["stations"]) == 48


def test_merged_same_day_rounds_get_distinct_keys_and_day_ordinals(
    seed: Any, viewer_client: TestClient
) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)  # "doe jane", ordinal 1
    seed.round(D1, jane, 38, name_key="doe j", ordinal=1)  # a merged spelling, also ordinal 1
    seed.finish()

    rounds = _export(viewer_client, jane)["rounds"]

    assert [(r["round_key"], r["ordinal"], r["score"]) for r in rounds] == [
        ("2026-09-06:doe j:1", 1, 38),
        ("2026-09-06:doe jane:1", 2, 41),
    ]


def test_same_day_order_follows_day_ordinals_not_the_db_collation(
    seed: Any, viewer_client: TestClient
) -> None:
    # en_US.utf8 ignores spaces, so it sorts "dela ann" before "de la roe ann"; codepoint order
    # (and so day_ordinals) puts "de la roe ann" first, because ' ' < 'l'.
    ann = seed.shooter("De La Roe, Ann")
    seed.round(D1, ann, 40, name_key="dela ann", ordinal=1)  # a merged spelling
    seed.round(D1, ann, 37, name_key="de la roe ann", ordinal=1)
    seed.finish()

    rounds = _export(viewer_client, ann)["rounds"]

    assert [(r["round_key"], r["ordinal"]) for r in rounds] == [
        ("2026-09-06:de la roe ann:1", 1),
        ("2026-09-06:dela ann:1", 2),
    ]


def test_export_requires_a_session(seed: Any, anon_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()

    response = anon_client.get(f"/api/shooters/{jane}/export")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_admin_sessions_can_export_too(seed: Any, admin_client: TestClient) -> None:
    jane = seed.shooter("Doe, Jane")
    seed.round(D1, jane, 41)
    seed.finish()

    assert len(_export(admin_client, jane)["rounds"]) == 1


def test_unknown_shooter_is_404(viewer_client: TestClient) -> None:
    response = viewer_client.get("/api/shooters/999999/export")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "shooter_not_found", "message": "No shooter with id 999999"}
    }


def test_query_count_does_not_grow_with_rounds(
    seed: Any, session: Session, viewer_client: TestClient
) -> None:
    one = seed.shooter("Doe, Jane")
    many = seed.shooter("Roe, Rick")
    seed.round(D1, one, 41)
    for week in range(6):
        d = D1 + timedelta(weeks=week)
        rid = seed.round(d, many, 30 + week)
        _station_entry(session, d, rid, many, "roe rick", SPORTING, SPORTING_HITS, entry_row=2)
    seed.finish()

    with _statements(session) as small:
        _export(viewer_client, one)
    with _statements(session) as big:
        _export(viewer_client, many)

    assert len(big) == len(small)


@pytest.mark.slow
def test_the_largest_fx_history_exports_under_the_ceiling(
    fx_session: Session, fx_viewer_client: TestClient
) -> None:
    top = fx_session.execute(
        text(
            "SELECT shooter_id FROM rounds GROUP BY shooter_id"
            " ORDER BY count(*) DESC, shooter_id LIMIT 1"
        )
    ).scalar_one()
    _export(fx_viewer_client, top)  # warm-up: imports, first-request setup

    started = time.perf_counter()
    body = _export(fx_viewer_client, top)
    elapsed = time.perf_counter() - started

    assert body["rounds"]
    assert elapsed < CI_CEILING_SECONDS, f"export took {elapsed:.3f}s"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run pytest tests/integration/analytics_core/test_claysmasher_export_route.py -q`
Expected: FAIL. The route does not exist yet, so the 200 assertions fail with a `404 {"detail":"Not Found"}` routing response. `test_export_requires_a_session` also fails, because an unknown route answers 404, not 401.

- [ ] **Step 3: Write the implementation**

Create `backend/src/sunday_clays/api/routes/claysmasher.py`:

```python
"""ClaySmasher export (spec 2026-10-01 §4.1): one shooter's whole history in one viewer call.

`round_key` ("{event_date}:{name_key}:{ordinal}") stands in for the spec's `round_id`: rebuild_live
renumbers every live id on each import commit, rollback and rule change, while the natural key is
DB-unique (uq_rounds_event_date_name_key_ordinal) and is what overlay rules already target.
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Path
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.api.routes._claysmasher import (
    TARGETS_PER_ROUND,
    day_ordinals,
    latest,
    round_key,
    rule_stamps,
    station_orders,
)
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType

router = APIRouter()

# C8 path template `{id}`, bound to a descriptive argument (as shooters.py does).
ShooterId = Annotated[int, Path(alias="id")]


class ClubOut(BaseModel):
    name: str
    event_name: str
    city: str
    region: str


CLUB = ClubOut(name="Tri-County Gun Club", event_name="Sunday Clays", city="Sherwood", region="OR")


class ExportShooterOut(BaseModel):
    id: int
    display_name: str


class ExportStationOut(BaseModel):
    order: int
    station_label: str
    target_count: int
    hits: int


class ExportRoundOut(BaseModel):
    round_key: str
    event_date: date
    ordinal: int
    round_type: RoundType
    score: int
    target_count: int
    gauge_class: str | None
    status: str | None
    updated_at: datetime
    stations: list[ExportStationOut]


class ShooterExportOut(BaseModel):
    schema_version: Literal[1] = 1
    club: ClubOut
    shooter: ExportShooterOut
    generated_at: datetime
    rounds: list[ExportRoundOut]


_PROFILE_SQL = text("SELECT display_name FROM shooter_profiles WHERE shooter_id = :s")
# COLLATE "C": byte order equals Python's codepoint order, which day_ordinals ranks by. The DB's
# default collation (en_US.utf8 in postgres:17) ignores spaces, hyphens and apostrophes at the first
# level, so it could list a day's ordinal 2 before its ordinal 1 after a merge.
_ROUNDS_SQL = text(
    """
SELECT r.id, r.event_date, r.name_key, r.ordinal, r.score, r.gauge_class, r.status,
       e.round_type
FROM rounds r
JOIN events e ON e.event_date = r.event_date
WHERE r.shooter_id = :s
ORDER BY r.event_date, r.ordinal, r.name_key COLLATE "C"
"""
)
# Linked entries only: station_hits.round_id is NULL for an entry that matched no round.
_STATIONS_SQL = text(
    """
SELECT h.round_id, h.station_label, h.hits, l.target_count
FROM station_hits h
JOIN rounds r ON r.id = h.round_id
JOIN station_layouts l ON l.event_date = h.event_date AND l.station_label = h.station_label
WHERE r.shooter_id = :s
"""
)
_LAYOUTS_SQL = text(
    """
SELECT l.event_date, l.station_label
FROM station_layouts l
WHERE l.event_date IN (SELECT event_date FROM rounds WHERE shooter_id = :s)
"""
)
# Commits and rollbacks both change what is live; counting rollbacks keeps updated_at monotonic.
_SCORES_CHANGED_SQL = text(
    """
SELECT max(GREATEST(committed_at, rolled_back_at))
FROM imports
WHERE kind = 'scores' AND status IN ('committed', 'rolled_back')
"""
)
_STATIONS_CHANGED_SQL = text(
    """
SELECT s.event_date, max(GREATEST(i.committed_at, i.rolled_back_at))
FROM import_station_sheets s
JOIN imports i ON i.id = s.import_id
WHERE i.kind = 'stations' AND i.status IN ('committed', 'rolled_back')
  AND s.event_date IN (SELECT event_date FROM rounds WHERE shooter_id = :s)
GROUP BY s.event_date
"""
)
_RULES_SQL = text(
    """
SELECT rule_type, payload, GREATEST(created_at, deactivated_at)
FROM rules
WHERE rule_type IN ('score_override', 'hide_round', 'round_type_override')
"""
)


def _rounds(session: Session, shooter_id: int, generated_at: datetime) -> list[ExportRoundOut]:
    """Every live round of the shooter with its linked station hits; a fixed number of queries."""
    params = {"s": shooter_id}
    rounds = session.execute(_ROUNDS_SQL, params).all()
    hits: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
    for round_id, label, value, targets in session.execute(_STATIONS_SQL, params):
        hits[int(round_id)].append((str(label), int(value), int(targets)))
    labels: dict[date, list[str]] = defaultdict(list)
    for event_date, label in session.execute(_LAYOUTS_SQL, params):
        labels[event_date].append(str(label))
    orders = {day: station_orders(day_labels) for day, day_labels in labels.items()}
    scores_changed: datetime | None = session.execute(_SCORES_CHANGED_SQL).scalar()
    stations_changed: dict[date, datetime] = dict(
        session.execute(_STATIONS_CHANGED_SQL, params).tuples().all()
    )
    by_round, by_day = rule_stamps(session.execute(_RULES_SQL).tuples())
    numbers = day_ordinals((r.event_date, r.name_key, r.ordinal) for r in rounds)

    out: list[ExportRoundOut] = []
    for r in rounds:
        natural = (r.event_date, r.name_key, r.ordinal)
        stations = sorted(
            (
                ExportStationOut(
                    order=orders[r.event_date][label],
                    station_label=label,
                    target_count=targets,
                    hits=value,
                )
                for label, value, targets in hits[r.id]
            ),
            key=lambda station: station.order,
        )
        changed = latest(
            scores_changed,
            stations_changed.get(r.event_date),
            by_round.get(natural),
            by_day.get(r.event_date),
        )
        out.append(
            ExportRoundOut(
                round_key=round_key(*natural),
                event_date=r.event_date,
                ordinal=numbers[natural],
                round_type=RoundType(str(r.round_type)),
                score=int(r.score),
                target_count=(
                    sum(station.target_count for station in stations)
                    if stations
                    else TARGETS_PER_ROUND
                ),
                gauge_class=r.gauge_class,
                status=r.status,
                updated_at=changed or generated_at,
                stations=stations,
            )
        )
    return out


@router.get("/api/shooters/{id}/export", response_model=ShooterExportOut)
def get_shooter_export(shooter_id: ShooterId, session: SessionDep) -> ShooterExportOut:
    """One shooter's rounds with their per-station hits, for the ClaySmasher app."""
    name = session.execute(_PROFILE_SQL, {"s": shooter_id}).scalar_one_or_none()
    if name is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    generated_at = datetime.now(UTC)
    return ShooterExportOut(
        club=CLUB,
        shooter=ExportShooterOut(id=shooter_id, display_name=str(name)),
        generated_at=generated_at,
        rounds=_rounds(session, shooter_id, generated_at),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run pytest tests/integration/analytics_core/test_claysmasher_export_route.py tests/integration/api/test_route_auth_matrix.py tests/unit/api -q`
Expected: PASS. The auth matrix walks the new route and gets 401 anonymously, and its `get_session` dependency is function-scoped.
Locally, also note the elapsed time `test_the_largest_fx_history_exports_under_the_ceiling` reports with `-s` / `--durations=5`; it should be well under 300 ms on a developer machine. If the test fails, or the local time is near 300 ms, do not raise the ceiling. Print `EXPLAIN ANALYZE` for each statement and add the missing index through a migration in a separate task. `ix_rounds_shooter_id` and `ix_station_hits_round_id` already cover the hot paths.

- [ ] **Step 5: Lint, format, type-check, commit**

```bash
cd "$(git rev-parse --show-toplevel)"/backend
uv run ruff format src/sunday_clays/api/routes/claysmasher.py tests/integration/analytics_core/test_claysmasher_export_route.py
uv run ruff check src/sunday_clays/api/routes/claysmasher.py tests/integration/analytics_core/test_claysmasher_export_route.py
uv run mypy --strict src
cd ..
git add backend/src/sunday_clays/api/routes/claysmasher.py backend/tests/integration/analytics_core/test_claysmasher_export_route.py
git commit -m "feat(api): GET /api/shooters/{id}/export for the ClaySmasher app

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Merged shooters, key stability and `updated_at` through real rebuilds

**Files:**
- Modify: `backend/src/sunday_clays/api/routes/claysmasher.py` (imports, a new `_not_found`, and the handler's 404 branch)
- Test: `backend/tests/integration/domain/test_claysmasher_export_rebuild.py`

**Interfaces:**
- Consumes:
  - from Task 2: `GET /api/shooters/{id}/export`, `get_shooter_export`
  - from the domain package: `stage_import(session, data: bytes, filename: str) -> ImportPreview` (`.import_id`), `commit_import(session, import_id: int, *, confirm_removals: bool = False) -> None`, `rollback_import(session, import_id: int) -> None`, `rebuild_live(session)`, `create_rule(session, rule_type: RuleType, payload: dict[str, Any], note: str | None) -> int`, `merge_map(session) -> dict[int, int]`, `error_body(code, message)`
  - the domain conftest fixtures `scores_workbook(rows) -> bytes` and `stations_workbook(sheets) -> bytes`
- Produces: `get_shooter_export(...) -> ShooterExportOut | JSONResponse`. For a merged-away shooter it returns a 404 body with `merged_into: int`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/integration/domain/test_claysmasher_export_rebuild.py`:

```python
"""ClaySmasher export across real imports, rebuilds, rules and merges (spec 2026-10-01 §4.1)."""

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from sunday_clays.domain.imports import commit_import, rollback_import, stage_import
from sunday_clays.domain.rebuild import rebuild_live
from sunday_clays.domain.rules import RuleType, create_rule
from sunday_clays.ingest.names import identity_key, name_key
from sunday_clays.models import Round, ShooterAlias

D1, D2 = date(2026, 9, 6), date(2026, 9, 13)
LAYOUT = (8, 8, 6, 8, 6, 8, 6)  # stations 4..10 (the workbook default), 50 targets, all even
JANE_HITS = (6, 7, 5, 6, 5, 7, 5)  # 41


def _commit(session: Session, data: bytes, filename: str) -> int:
    import_id = stage_import(session, data, filename).import_id
    commit_import(session, import_id)
    rebuild_live(session)
    return import_id


def _shooter(session: Session, raw_name: str, day: date) -> int:
    shooter_id = session.scalar(
        select(ShooterAlias.shooter_id).where(
            ShooterAlias.name_key == identity_key(name_key(raw_name), day)
        )
    )
    assert shooter_id is not None
    return shooter_id


def _export(client: TestClient, shooter_id: int) -> dict[str, Any]:
    response = client.get(f"/api/shooters/{shooter_id}/export")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _stamp(round_out: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(round_out["updated_at"])


def _import_time(session: Session, import_id: int, column: str) -> datetime:
    value = session.execute(
        text(f"SELECT {column} FROM imports WHERE id = :id"),  # noqa: S608 - fixed column names
        {"id": import_id},
    ).scalar_one()
    assert isinstance(value, datetime)
    return value


def test_round_keys_survive_a_reimport_while_round_ids_do_not(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    rows = [("Doe, Jane", 41, D1), ("Doe, Jane", 38, D2), ("Roe, Rick", 30, D1)]
    _commit(session, scores_workbook(rows), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    before = _export(viewer_client, jane)
    ids_before = set(session.scalars(select(Round.id).where(Round.shooter_id == jane)))

    _commit(session, scores_workbook([*rows, ("Roe, Rick", 33, D2)]), "v2.xlsx")
    after = _export(viewer_client, jane)
    ids_after = set(session.scalars(select(Round.id).where(Round.shooter_id == jane)))

    assert ids_before.isdisjoint(ids_after)  # rebuild renumbered every round
    key = identity_key(name_key("Doe, Jane"), D1)
    assert [r["round_key"] for r in after["rounds"]] == [
        f"2026-09-06:{key}:1",
        f"2026-09-13:{key}:1",
    ]
    assert [r["round_key"] for r in after["rounds"]] == [r["round_key"] for r in before["rounds"]]


def test_merged_away_shooter_is_404_with_the_survivor(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    _commit(
        session,
        scores_workbook([("Roe, Rick", 30, D1), ("Roe, Richard", 33, D2)]),
        "v1.xlsx",
    )
    rick = _shooter(session, "Roe, Rick", D1)
    richard = _shooter(session, "Roe, Richard", D2)
    create_rule(
        session,
        RuleType.MERGE_SHOOTER,
        {"source_shooter_id": richard, "target_shooter_id": rick},
        None,
    )
    rebuild_live(session)

    response = viewer_client.get(f"/api/shooters/{richard}/export")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "shooter_merged",
            "message": f"Shooter {richard} was merged into {rick}",
        },
        "merged_into": rick,
    }
    survivor = _export(viewer_client, rick)
    assert [(r["round_key"], r["score"]) for r in survivor["rounds"]] == [
        (f"2026-09-06:{identity_key(name_key('Roe, Rick'), D1)}:1", 30),
        (f"2026-09-13:{identity_key(name_key('Roe, Richard'), D2)}:1", 33),
    ]


def test_updated_at_moves_forward_on_reimport_and_on_rollback(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    v1 = _commit(session, scores_workbook([("Doe, Jane", 41, D1)]), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    first = _export(viewer_client, jane)["rounds"][0]
    assert _stamp(first) == _import_time(session, v1, "committed_at")

    v2 = _commit(session, scores_workbook([("Doe, Jane", 42, D1)]), "v2.xlsx")
    second = _export(viewer_client, jane)["rounds"][0]
    assert (second["score"], second["round_key"]) == (42, first["round_key"])
    assert _stamp(second) == _import_time(session, v2, "committed_at")

    rollback_import(session, v2)  # v1 is live again; its commit time is older than v2's
    rebuild_live(session)
    third = _export(viewer_client, jane)["rounds"][0]
    assert third["score"] == 41
    assert _stamp(third) == _import_time(session, v2, "rolled_back_at")
    assert _stamp(third) > _stamp(second)


def test_station_sheet_rounds_export_in_station_order_and_bump_updated_at(
    session: Session,
    viewer_client: TestClient,
    scores_workbook: Callable[..., bytes],
    stations_workbook: Callable[..., bytes],
) -> None:
    _commit(session, scores_workbook([("Doe, Jane", 41, D2)]), "scores.xlsx")
    stations = _commit(
        session,
        stations_workbook([("9 13 26", D2, LAYOUT, [("Doe, Jane", JANE_HITS)])]),
        "stations.xlsx",
    )
    jane = _shooter(session, "Doe, Jane", D2)

    (only,) = _export(viewer_client, jane)["rounds"]

    assert [(s["order"], s["station_label"], s["target_count"], s["hits"]) for s in only["stations"]] == [
        (1, "4", 8, 6),
        (2, "5", 8, 7),
        (3, "6", 6, 5),
        (4, "7", 8, 6),
        (5, "8", 6, 5),
        (6, "9", 8, 7),
        (7, "10", 6, 5),
    ]
    assert (only["target_count"], only["round_type"]) == (50, "sporting")
    assert _stamp(only) == _import_time(session, stations, "committed_at")


def test_a_score_override_rule_moves_updated_at_to_the_rule(
    session: Session, viewer_client: TestClient, scores_workbook: Callable[..., bytes]
) -> None:
    _commit(session, scores_workbook([("Doe, Jane", 41, D1)]), "v1.xlsx")
    jane = _shooter(session, "Doe, Jane", D1)
    rule_id = create_rule(
        session,
        RuleType.SCORE_OVERRIDE,
        {
            "event_date": D1.isoformat(),
            "name_key": identity_key(name_key("Doe, Jane"), D1),
            "ordinal": 1,
            "score": 45,
        },
        None,
    )
    # now() is this test transaction's start, before the import's clock_timestamp(); in
    # production each rule is created in its own request transaction, after the import.
    created = session.execute(
        text("UPDATE rules SET created_at = clock_timestamp() WHERE id = :id RETURNING created_at"),
        {"id": rule_id},
    ).scalar_one()
    rebuild_live(session)

    (only,) = _export(viewer_client, jane)["rounds"]

    assert only["score"] == 45
    assert _stamp(only) == created
```

- [ ] **Step 2: Run them to verify which fail**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run pytest tests/integration/domain/test_claysmasher_export_rebuild.py -q`
Expected: `test_merged_away_shooter_is_404_with_the_survivor` FAILS. Its body is `{"error":{"code":"shooter_not_found",...}}`, with no `merged_into`.
The other four PASS. They pin behavior Task 2 built: key stability (ruling 1), monotonic `updated_at` (ruling 4) and station order (ruling 6). If any of them fails, stop and fix Task 2's route before going on.

- [ ] **Step 3: Implement the merged-shooter 404**

Edit `backend/src/sunday_clays/api/routes/claysmasher.py`.

Replace the import block lines

```python
from fastapi import APIRouter, Path
from pydantic import BaseModel
```

with

```python
from fastapi import APIRouter, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
```

Replace

```python
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.round_type import RoundType
```

with

```python
from sunday_clays.api.errors import error_body
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError
from sunday_clays.domain.identity import merge_map
from sunday_clays.domain.round_type import RoundType
```

Replace the whole handler (from `@router.get("/api/shooters/{id}/export", ...` to the end of the file) with:

```python
def _not_found(session: Session, shooter_id: int) -> JSONResponse:
    """404: `shooter_merged` plus `merged_into` for a merged-away shooter, else shooter_not_found.

    A merged-away shooter keeps its `shooters` row but has no profile, as no live round names it.
    The standard handler only renders {"error": ...}, so the merged case is built here.
    """
    target = merge_map(session).get(shooter_id)
    if target is None:
        raise NotFoundError("shooter_not_found", f"No shooter with id {shooter_id}")
    content: dict[str, object] = {
        **error_body("shooter_merged", f"Shooter {shooter_id} was merged into {target}"),
        "merged_into": target,
    }
    return JSONResponse(status_code=404, content=content)


@router.get("/api/shooters/{id}/export", response_model=ShooterExportOut)
def get_shooter_export(
    shooter_id: ShooterId, session: SessionDep
) -> ShooterExportOut | JSONResponse:
    """One shooter's rounds with their per-station hits, for the ClaySmasher app."""
    name = session.execute(_PROFILE_SQL, {"s": shooter_id}).scalar_one_or_none()
    if name is None:
        return _not_found(session, shooter_id)
    generated_at = datetime.now(UTC)
    return ShooterExportOut(
        club=CLUB,
        shooter=ExportShooterOut(id=shooter_id, display_name=str(name)),
        generated_at=generated_at,
        rounds=_rounds(session, shooter_id, generated_at),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run pytest tests/integration/domain/test_claysmasher_export_rebuild.py tests/integration/analytics_core/test_claysmasher_export_route.py tests/integration/api/test_route_auth_matrix.py -q`
Expected: PASS. `test_unknown_shooter_is_404` from Task 2 still sees exactly `shooter_not_found`, without `merged_into`.

- [ ] **Step 5: Check the generated OpenAPI still builds**

Run: `cd "$(git rev-parse --show-toplevel)"/backend && uv run python -m sunday_clays.api.export_openapi --out /tmp/claysmasher-openapi.json && python3 -c "import json; d=json.load(open('/tmp/claysmasher-openapi.json')); print(sorted(d['paths']['/api/shooters/{id}/export']['get']['responses']))"`
Expected: prints `['200', '422']`. The response schema is `ShooterExportOut`, because `response_model` overrides the union annotation.

- [ ] **Step 6: Run the backend gate, then commit**

```bash
cd "$(git rev-parse --show-toplevel)"/backend
uv run ruff format src/sunday_clays/api/routes/claysmasher.py tests/integration/domain/test_claysmasher_export_rebuild.py
uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch -q
```
Expected: everything passes. Coverage stays at or above `fail_under` and the 99% ratchet floors. Every line and branch of `claysmasher.py` and `_claysmasher.py` is exercised by Tasks 1-3.

```bash
cd "$(git rev-parse --show-toplevel)"
git add backend/src/sunday_clays/api/routes/claysmasher.py backend/tests/integration/domain/test_claysmasher_export_rebuild.py
git commit -m "feat(api): merged shooters answer 404 with merged_into on the ClaySmasher export

Pins round_key stability across re-imports, monotonic updated_at across
rollbacks, and station order through a real rebuild.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: "Import into ClaySmasher" button behind the flag

**Files:**
- Create: `frontend/src/features/claysmasher/links.ts`
- Create: `frontend/src/features/claysmasher/links.test.ts`
- Create: `frontend/src/features/claysmasher/components/ImportIntoClaySmasher.tsx`
- Create: `frontend/src/features/claysmasher/components/ImportIntoClaySmasher.test.tsx`
- Create: `frontend/src/features/claysmasher/profileSection.tsx`
- Create: `frontend/src/features/claysmasher/profileSection.test.ts`

**Interfaces:**
- Consumes:
  - `ProfileSection` and `profileSections` (`src/features/shooters/sections`), which this task reads but never edits. `ProfileSection.Component` is `FC<{ shooterId: number }>`; sections are collected by `import.meta.glob('../*/profileSection.tsx')`, so no registration edit is needed.
  - `renderWithProviders` (`src/test/render`)
  - `Smartphone` from `lucide-react` (already a dependency)
- Produces, from `links.ts`:
  - `CLAYSMASHER_WEB_LINK = 'https://claysmasher.com/link/sunday-clays'`
  - `CLAYSMASHER_SCHEME_LINK = 'claysmasher://sunday-clays/link'`
  - `CLAYSMASHER_BUTTON_ENABLED: boolean` (`false`)
  - `type ClaySmasherLinkMode = 'universal' | 'scheme'` and `CLAYSMASHER_LINK_MODE: ClaySmasherLinkMode` (`'universal'`)
  - `claysmasherWebUrl(shooterId: number): string`
  - `claysmasherSchemeUrl(shooterId: number): string`
- Produces, from the components:
  - `ImportIntoClaySmasher({ shooterId, enabled = CLAYSMASHER_BUTTON_ENABLED, mode = CLAYSMASHER_LINK_MODE }: { shooterId: number; enabled?: boolean; mode?: ClaySmasherLinkMode })`
  - `profileSection: ProfileSection` with `id: 'claysmasher'`, `placement: 'top'`, `bare: true`, `order: 5`

- [ ] **Step 1: Install frontend dependencies (first task that commits a frontend file)**

This task's commit adds frontend files. The shared lefthook pre-commit hook (`frontend-lint`, `frontend-format`, `frontend-typecheck`: `pnpm exec eslint`, `pnpm exec prettier`, `pnpm typecheck`, installed in `.git/hooks`) and every `pnpm` command below need `frontend/node_modules`, which a fresh checkout or worktree does not have.

Run: `cd "$(git rev-parse --show-toplevel)"/frontend && corepack enable && pnpm install --frozen-lockfile && git status --short`
Expected: the install completes, and `git status --short` prints nothing (no lockfile change).

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/features/claysmasher/links.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { claysmasherSchemeUrl, claysmasherWebUrl } from './links';

describe('ClaySmasher link URLs', () => {
  it('points the web link at the claysmasher.com page the app claims', () => {
    expect(claysmasherWebUrl(17)).toBe('https://claysmasher.com/link/sunday-clays?shooter=17');
  });

  it('links to another host than this site, so iOS hands the tap to the app (U1)', () => {
    const url = new URL(claysmasherWebUrl(17));

    expect(url.host).toBe('claysmasher.com');
    expect(url.searchParams.get('shooter')).toBe('17');
  });

  it('points the scheme link at the URI the app normalizes to the same route', () => {
    expect(claysmasherSchemeUrl(17)).toBe('claysmasher://sunday-clays/link?shooter=17');
  });
});
```

Create `frontend/src/features/claysmasher/components/ImportIntoClaySmasher.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { CLAYSMASHER_BUTTON_ENABLED, CLAYSMASHER_LINK_MODE } from '../links';
import { ImportIntoClaySmasher } from './ImportIntoClaySmasher';

const WEB = 'https://claysmasher.com/link/sunday-clays?shooter=3';

describe('ImportIntoClaySmasher', () => {
  // The flag-flip PR (spec §11 step 4) updates this test, and only this test.
  it('ships off, in universal mode', () => {
    expect(CLAYSMASHER_BUTTON_ENABLED).toBe(false);
    expect(CLAYSMASHER_LINK_MODE).toBe('universal');

    renderWithProviders(<ImportIntoClaySmasher shooterId={3} />);

    expect(screen.queryByRole('link', { name: /ClaySmasher/ })).toBeNull();
  });

  it('is a plain same-tab link to the claysmasher.com page', () => {
    renderWithProviders(<ImportIntoClaySmasher shooterId={3} enabled mode="universal" />);

    const link = screen.getByRole('link', { name: 'Import into ClaySmasher' });
    expect(link).toHaveAttribute('href', WEB);
    expect(link).not.toHaveAttribute('target');
    expect(link).not.toHaveAttribute('rel');
    expect(screen.getAllByRole('link')).toHaveLength(1);
  });

  it('scheme mode adds a web link for phones without the app', () => {
    renderWithProviders(<ImportIntoClaySmasher shooterId={3} enabled mode="scheme" />);

    expect(screen.getByRole('link', { name: 'Import into ClaySmasher' })).toHaveAttribute(
      'href',
      'claysmasher://sunday-clays/link?shooter=3',
    );
    const fallback = screen.getByRole('link', { name: 'Don’t have ClaySmasher?' });
    expect(fallback).toHaveAttribute('href', WEB);
    expect(fallback).not.toHaveAttribute('target');
  });
});
```

Create `frontend/src/features/claysmasher/profileSection.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { profileSections } from '../shooters/sections';
import { ImportIntoClaySmasher } from './components/ImportIntoClaySmasher';

describe('ClaySmasher profile section', () => {
  it('sits at the top of the shooter page and renders its own (or no) element', () => {
    expect(profileSections.find((s) => s.id === 'claysmasher')).toMatchObject({
      placement: 'top',
      bare: true,
      order: 5,
      Component: ImportIntoClaySmasher,
    });
  });
});
```

- [ ] **Step 3: Run them to verify they fail**

Run: `cd "$(git rev-parse --show-toplevel)"/frontend && pnpm exec vitest run src/features/claysmasher`
Expected: FAIL with `Failed to resolve import "./links"`, `"../links"` and `"./components/ImportIntoClaySmasher"`.

- [ ] **Step 4: Write `links.ts`**

Create `frontend/src/features/claysmasher/links.ts`:

```ts
/**
 * ClaySmasher link (spec 2026-10-01 §3.1, §4.2, U1). The app claims the claysmasher.com page as an
 * iOS universal link and an Android App Link; claysmasher.com serves the association files and the
 * page shown without the app. It is a different host from this site on purpose: iOS keeps a
 * universal link tapped on a page of its own domain in Safari.
 */
export const CLAYSMASHER_WEB_LINK = 'https://claysmasher.com/link/sunday-clays';
/** The custom scheme the app registers from its first release (spec §5.1). */
export const CLAYSMASHER_SCHEME_LINK = 'claysmasher://sunday-clays/link';

/**
 * Off until the ClaySmasher release that handles the link ships and claysmasher.com's AASA is
 * validated (spec §11 step 4). Merging to main deploys, so turning the button on is a one-line PR.
 */
export const CLAYSMASHER_BUTTON_ENABLED = false;

/**
 * 'universal' opens the claysmasher.com page (the app, when installed). 'scheme' is the fallback if
 * Apple rejects the AASA that GitHub Pages serves (spec §4.2, §10.2): the button opens the app's
 * custom scheme, with a web link under it for phones without the app.
 */
export type ClaySmasherLinkMode = 'universal' | 'scheme';
export const CLAYSMASHER_LINK_MODE: ClaySmasherLinkMode = 'universal';

export function claysmasherWebUrl(shooterId: number): string {
  return `${CLAYSMASHER_WEB_LINK}?shooter=${shooterId}`;
}

export function claysmasherSchemeUrl(shooterId: number): string {
  return `${CLAYSMASHER_SCHEME_LINK}?shooter=${shooterId}`;
}
```

- [ ] **Step 5: Write the component and the section**

Create `frontend/src/features/claysmasher/components/ImportIntoClaySmasher.tsx`:

```tsx
import { Smartphone } from 'lucide-react';
import {
  CLAYSMASHER_BUTTON_ENABLED,
  CLAYSMASHER_LINK_MODE,
  claysmasherSchemeUrl,
  claysmasherWebUrl,
} from '../links';
import type { ClaySmasherLinkMode } from '../links';

/** components/ui/Button's tonal look for an <a> (Button renders a <button> only). */
const BUTTON_CLASS =
  'inline-flex min-h-11 min-w-11 self-start items-center justify-center gap-2 rounded-button border border-outline-variant bg-elevated px-4 text-sm font-medium text-text transition-colors hover:border-outline';

/**
 * Spec §3.1, §4.2: a plain same-tab <a> (no target, no window.open), so the phone treats the tap as
 * a universal link / App Link and opens ClaySmasher when it is installed; without the app the
 * claysmasher.com page opens and Back returns here. Hidden while the flag is off (spec §11).
 */
export function ImportIntoClaySmasher({
  shooterId,
  enabled = CLAYSMASHER_BUTTON_ENABLED,
  mode = CLAYSMASHER_LINK_MODE,
}: {
  shooterId: number;
  enabled?: boolean;
  mode?: ClaySmasherLinkMode;
}) {
  if (!enabled) return null;
  const button = (href: string) => (
    <a href={href} className={BUTTON_CLASS}>
      <Smartphone aria-hidden="true" className="size-4" />
      Import into ClaySmasher
    </a>
  );
  if (mode === 'universal') return button(claysmasherWebUrl(shooterId));
  return (
    <div className="flex flex-col items-start self-start">
      {button(claysmasherSchemeUrl(shooterId))}
      <a
        href={claysmasherWebUrl(shooterId)}
        className="inline-flex min-h-11 items-center text-sm text-text-muted underline"
      >
        Don’t have ClaySmasher?
      </a>
    </div>
  );
}
```

Create `frontend/src/features/claysmasher/profileSection.tsx`:

```tsx
import type { ProfileSection } from '../shooters/sections';
import { ImportIntoClaySmasher } from './components/ImportIntoClaySmasher';

/** C10 profile section: the "Import into ClaySmasher" button under the hero (bare: no card). */
export const profileSection: ProfileSection = {
  id: 'claysmasher',
  title: 'ClaySmasher',
  order: 5,
  placement: 'top',
  bare: true,
  Component: ImportIntoClaySmasher,
};
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd "$(git rev-parse --show-toplevel)"/frontend && pnpm exec vitest run src/features/claysmasher src/features/shooters src/features/insights`
Expected: PASS, 7 tests in `src/features/claysmasher`. The existing profile and insights mount tests still pass, because the new section renders `null` while the flag is off.

- [ ] **Step 7: Run the frontend gate and the bundle build**

Run: `cd "$(git rev-parse --show-toplevel)"/frontend && pnpm exec prettier --write src/features/claysmasher && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage && pnpm build && python3 ../scripts/bundle_stats.py --dist dist --out ../bundle-stats.json`
Expected: everything passes, and the coverage summary shows 100% lines and branches for `src/features/claysmasher/**` (both modes and the flag-off path are covered). `bundle_stats.py`'s defaults (`--dist frontend/dist`, `--out bundle-stats.json`) are relative to the repo root, so from `frontend/` both paths are passed explicitly (CI runs `python3 scripts/bundle_stats.py --dist frontend/dist --out bundle-stats.json` from the root). The script only **prints** the sizes; it does not compare them. Compare the printed `entry_js_gz_kb` and `total_js_gz_kb` by hand against `ratchets/budgets.json` (250 and 1600); CI's `ratchet` job enforces them with `scripts/ratchet.py check`. The button joins the shooter page's chunk and adds well under 1 KB gzipped. `bundle-stats.json` is gitignored, so writing it at the root leaves `git status` clean.

- [ ] **Step 8: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add frontend/src/features/claysmasher
git commit -m "feat(frontend): Import into ClaySmasher button on the shooter page, behind a flag

Links to https://claysmasher.com/link/sunday-clays?shooter=<id> in the
same tab; a scheme mode is built in as the fallback if Apple rejects the
AASA that claysmasher.com serves.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git status --short   # expect: empty
```

---

### Task 5: Full gate, pull request, deploy and production check

**Files:**
- No source changes.

**Interfaces:**
- Consumes: everything from Tasks 1-4.
- Produces:
  - the merged PR, deployed to `sundayclays.claysmasher.com`
  - the live export contract for the ClaySmasher plan
  - the recorded production checks

- [ ] **Step 1: Run every local gate once more**

```bash
cd "$(git rev-parse --show-toplevel)"/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest --cov --cov-branch -q
cd ../frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm test --coverage
cd .. && git status --short
```
Expected: all green. `git status --short` is empty (Task 0 committed the plan doc).
Confirm the protected paths are untouched, and that nothing at the edge changed (U1 moved the association files to claysmasher.com):

```bash
git diff --stat origin/main -- ratchets frontend/src/app/router.tsx frontend/src/features/shooters frontend/playwright.config.ts backend/uv.lock frontend/pnpm-lock.yaml backend/src/sunday_clays/api/app.py deploy compose.swarm.yaml
```
Expected: no output.

- [ ] **Step 2: Push and open the PR**

```bash
cd "$(git rev-parse --show-toplevel)"
git push -u origin feat/claysmasher-export
gh pr create --base main --head feat/claysmasher-export \
  --title "feat: ClaySmasher export endpoint and shooter-page link button" \
  --body "$(cat <<'EOF'
Sunday Clays half of the ClaySmasher link (ClaySmasher spec 2026-10-01 §4.1, §4.2, §7, §11 step 1).

- `GET /api/shooters/{id}/export` (viewer or admin): one shooter's full history in one call.
  The final contract is the plan's "Contract" section (docs/superpowers/plans/2026-10-01-claysmasher-export.md);
  the amended spec §4.1 reproduces it. **Amendments to the original §4.1 example:**
  1. rounds carry `round_key` (`"{event_date}:{name_key}:{ordinal}"`) only, never `round_id`, because
     `rebuild_live` renumbers every round id on each import and rule change;
  2. `ordinal` is the shooter's per-day ordinal (distinct 1..n even after a same-day merge);
  3. `target_count` is the sum of the stations' targets, else 50;
  4. a merged-away shooter answers 404 with the standard `{"error":{...}}` envelope plus a top-level `merged_into`;
  5. `status` is lowercase `member|guest|deceased|null`;
  6. `updated_at` is coarse and informational only (newest import/rule time; not per-round).
- "Import into ClaySmasher" button on the shooter page, **off** (`CLAYSMASHER_BUTTON_ENABLED = false`).
  It is a plain same-tab link to `https://claysmasher.com/link/sunday-clays?shooter=<id>`: a different
  host from this site, because iOS keeps a universal link tapped on its own domain in Safari.
  claysmasher.com (its own PR) serves the association files and the page shown without the app, so this
  PR changes nothing at the edge (no Caddyfile, compose or `/.well-known` change).
- `CLAYSMASHER_LINK_MODE = 'universal'`; `'scheme'` switches the button to `claysmasher://sunday-clays/link?shooter=<id>`
  plus a "Don’t have ClaySmasher?" web link, the fallback if Apple rejects the AASA GitHub Pages serves.

The button is turned on in a separate one-line PR after the ClaySmasher release ships, claysmasher.com's
AASA is validated through Apple's CDN, and the link is checked on a real iPhone and Android phone.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI and merge**

Run: `gh pr checks --required --watch`
Expected: `ci-ok` passes. It covers `backend`, `frontend`, `ratchet`, `docker`, `docker-arm64`, `stack-config` and `e2e` (the existing suite; the button is hidden, so no e2e change is expected).
**Checkpoint: stop and confirm with the user before merging.** A merge to `main` auto-deploys to production: with `PUBLISH_ON_PUSH=true`, the deployer rolls out `sha-<7>` within minutes (deploy/README.md "Automatic deploys"). Merge only after an explicit yes.

Then, from the branch checkout:

```bash
cd "$(git rev-parse --show-toplevel)"
gh pr merge --squash
git push origin --delete feat/claysmasher-export
```

Do **not** pass `--delete-branch` if `main` is checked out in another worktree: gh then tries to check out `main` locally after the merge and fails partway (`'main' is already used by worktree`). Delete the local branch by hand afterwards instead.

- [ ] **Step 4: Verify production**

Wait until `curl -fsS https://sundayclays.claysmasher.com/api/health` reports `"version":"sha-<7>"` for the merge commit (`git rev-parse --short=7 origin/main` after a `git fetch origin`), then:

```bash
curl -sS -w '\n%{http_code} %{content_type}\n' https://sundayclays.claysmasher.com/api/shooters/1/export
curl -sS -i -X POST -H 'Content-Type: application/json' -A 'Dart/3.5 (dart:io)' \
  -d '{"password":"x"}' https://sundayclays.claysmasher.com/api/auth/login
```
Expected:
- Export without a cookie: body `{"error":{"code":"unauthenticated","message":"Log in to continue"}}`, then `401 application/json`. A `404` means the route is not deployed yet; an HTML body means an edge rule intercepted it.
- Dart-agent login: `HTTP/2 401`, `content-type: application/json`, and a body whose `error.code` is `invalid_password`. Not a Cloudflare challenge page (HTML, `cf-mitigated: challenge`, or a 403). This is the path the ClaySmasher app uses: a non-browser client with no `Origin` or `Sec-Fetch-Site` headers. The CSRF middleware allows requests with no `Origin`, so only an edge rule could block it.

Then check the 300 ms target on the largest production history. This needs the real viewer password, so **the user runs it** (or types the password at the prompt); never write the password or the cookie into the repo, and do not print shooter names.

```bash
JAR="$(mktemp)"; read -rs -p 'Viewer password: ' PW; echo
curl -sS -o /dev/null -w 'login %{http_code}\n' -c "$JAR" -H 'Content-Type: application/json' \
  -A 'Dart/3.5 (dart:io)' -d "$(python3 -c 'import json,sys; print(json.dumps({"password": sys.argv[1]}))' "$PW")" \
  https://sundayclays.claysmasher.com/api/auth/login
unset PW
TOP="$(curl -sS -b "$JAR" https://sundayclays.claysmasher.com/api/shooters \
  | python3 -c 'import json,sys; print(max(json.load(sys.stdin), key=lambda s: s["n_rounds"])["shooter_id"])')"
for i in 1 2 3 4; do
  curl -sS -o /dev/null -b "$JAR" -A 'Dart/3.5 (dart:io)' \
    -w "export $TOP %{http_code} %{time_starttransfer}s ttfb %{time_total}s total\n" \
    "https://sundayclays.claysmasher.com/api/shooters/$TOP/export"
done
curl -sS -b "$JAR" "https://sundayclays.claysmasher.com/api/shooters/$TOP/export" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d["rounds"]; print(d["schema_version"], len(r), sum(1 for x in r if x["stations"]), sorted(r[0]) if r else [])'
rm -f "$JAR"
```
Expected: `login 200`, then four `200` lines, then one line `1 <rounds> <rounds with stations> [...]` whose key list is exactly `['event_date', 'gauge_class', 'ordinal', 'round_key', 'round_type', 'score', 'stations', 'status', 'target_count', 'updated_at']` (no `round_id`; counts only, no names). Record the times in the PR (as a comment) and the hand-off. Ignore the first (cold) run; the target is `time_starttransfer` under 0.3 s on the rest (it is server time plus one network round trip, so it overstates server time). If it is over, open a follow-up issue with `EXPLAIN ANALYZE` of the export statements; do not block the ClaySmasher work on it.

If the Dart-agent login or the export is challenged, ask the owner to add a Cloudflare WAF skip rule for `/api/*` for that client (for example, skip Bot Fight / managed challenge on `/api/*`). That is outside this repo.

- [ ] **Step 5: Hand-off notes (no code)**

Report these to the user:
1. The export contract is live and matches this plan's "Contract" section, which the amended spec §4.1 already reproduces; no spec edit is needed.
2. The production results from Step 4: the 401 envelope, the Dart-agent login result, and the timings (300 ms target).
3. Sunday Clays serves no `/.well-known/*` files and no landing route (U1). The association files, the `/link/sunday-clays` page and the **pending Android SHA-256** are owned by the claysmasher.com plan; Android App Links verify only for Play-distributed builds (internal testing track is fine).
4. Cleanup for the user: delete the local `feat/claysmasher-export` branch (and its worktree, if one was used).
5. **Before flipping `CLAYSMASHER_BUTTON_ENABLED`** (spec §11 step 4; a separate one-line PR that also updates the `ships off, in universal mode` test), all of these must hold:
   - the ClaySmasher release with the `/link/sunday-clays` route and the `claysmasher://` scheme is **live in the App Store and on Google Play** (a production release, not TestFlight or a Play testing track). Testing builds are fine for trying things out earlier, but they never satisfy this condition;
   - the claysmasher.com plan's Task 6 has a recorded outcome in its PR: **VALIDATED** (Apple's CDN at `https://app-site-association.cdn-apple.com/a/v1/claysmasher.com` returns the AASA) or **FALLBACK-SCHEME**. FALLBACK-HEADERS is not an end state; it repeats the check until it ends in one of those two;
   - the on-device check passes **against the store build** (installed from the App Store / Google Play): on a real iPhone and a real Android phone, with the button enabled locally or on a preview, tapping it on a `sundayclays.claysmasher.com` shooter page opens ClaySmasher on the link screen for that shooter. On Android, if the fingerprint is not yet in claysmasher.com's `assetlinks.json`, the https link opens the claysmasher.com landing page instead, and the check there is that its "Open in ClaySmasher" button (custom scheme) opens the app on the link screen.

   The pending Android SHA-256 does **not** block the flip unless the user decides it should. This matches the ClaySmasher plan's release gate (d), where shipping before the fingerprint arrives is a user call. Without it, Android users go through the landing page, whose button still opens the app.

   If Apple's CDN rejects the AASA (spec §10.2) and the user picks the scheme fallback, the same PR also sets `CLAYSMASHER_LINK_MODE = 'scheme'`, and the device check becomes: the button opens ClaySmasher, and on a phone without the app "Don’t have ClaySmasher?" opens the claysmasher.com page.
