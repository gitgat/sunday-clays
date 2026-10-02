# Insight Bumps and "Which one are you?" Implementation Plan (Sub-plan 15)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers, including fix rounds, run on Sonnet. Every reviewer, re-reviewer and verifier runs on Opus. Each task gets one branch, one worktree and one PR **into `feat/insight-bumps`**, never `main`. Implementers commit but never push or open PRs. The controller pushes, opens the PRs and merges them, in the waves below.

**Goal:** Put anonymous 🤜🤛 fist bumps on every insight row on the site, keyed by the insight's stable `key` so that one count follows the insight everywhere. Also add "Which one are you?" to Home's personal slot. Everything else about today's Home layout stays as it is.

**Architecture:** The backend gains a durable `fist_bumps` table (one row per insight key and device) and a `bump_attempts` table for the per-IP rate limit (migration `0006`). It serves a new discovered router, `api/routes/bumps.py`, with three endpoints. `GET /api/bumps?keys=…&device_id=…` returns batched counts and is never ETagged or stored. `POST /api/bumps` and `DELETE /api/bumps` are idempotent writes. A key is valid when it is a row in the `insights` table right now. That is checked with one `IN` query, `analytics/insights/store.py` `existing_keys`. On the frontend, a new `features/bumps/` feature owns the device-aware queries, the reviewed `BumpButton`, a `BumpsProvider` that fetches one page section's counts in a single request, and `InsightBump`, which reads that context. The shared insight row components (`InsightCard`, `RecapCard`, and the kudos "and N more" rows) render `InsightBump`. Every feed section in `FeedSections.tsx` wraps itself in a `BumpsProvider`. Home's personal slot shows the reviewed `WhichOneAreYou` until a "me" is picked or skipped, and `MePanel` gains "Not me".

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · pytest · Postgres 17 · React 19 · TypeScript (strict) · TanStack Query v5 (mutation `scope`, `keepPreviousData`) · React Router v7 · Tailwind v4 · openapi-fetch · Vitest + Testing Library + MSW · Playwright.

**Spec:** The approved design (owner, 2026-10-01) is quoted verbatim in "Approved design" below, and it is binding. The reviewed source it reuses is on the parked branch `origin/feat/sunday-sheet`: read files with `git show origin/feat/sunday-sheet:<path>`. Its design doc is `docs/superpowers/specs/2026-09-30-sunday-sheet-design.md` on that branch, and its review ledger is `.superpowers/sdd/2026-09-30-14-sunday-sheet/progress.md`. Do not merge or cherry-pick that branch. This plan ports the needed files by content.

**Base:** `main` @ `39acf96` ("fix(home): reserve space for the insights cards while they load (#1)"). The controller cuts `feat/insight-bumps` from it. **Pre-flight** (controller, before each wave): every Create target must not exist, every Modify target must exist, and every "replace" block must occur exactly once in the task's base.

**Delivery:** Task branches are `task/15-<N>-<slug>`, cut from `feat/insight-bumps` after the previous wave has merged. Every PR targets `feat/insight-bumps`, and CI (`ci-ok`, which includes the full Playwright suite) must pass. Commits use the gitgat identity, which is already in the repo config. Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. An implementer on another model names its own model there instead. After Task 4, the owner previews the branch locally. Only when the owner says so does one PR take `feat/insight-bumps` to `main`.

## Approved design (owner, 2026-10-01; verbatim)

> The owner previewed the Sunday Sheet redesign (branch feat/sunday-sheet, parked, do not merge) and preferred today's Home layout. They want ONLY these brought over, built on a fresh integration branch feat/insight-bumps cut from main (39acf96):
>
> 1. Fist bumps 🤜🤛 on EVERY insight site-wide: Home (Top story, spotlight, kudos, more insights), shooter profile insights, event-page insights, Year in Review — wherever an insight row renders. Keyed by the insight's stable `key`, so one count follows the insight everywhere. Anonymous, one per device (UUID in localStorage "sc.device"), viewer-password gated, no-store counts (never in cached/ETag'd bodies).
>    Backend: reuse the reviewed Sheet code: fist_bumps table + migration (PK post_key/device_id — may rename column to key or keep post_key, decide), bump_attempts rate limit 120 per IP per 10 min via shared limiter helpers, domain/bumps.py. New API: GET /api/bumps?keys=k1,k2,…&device_id= → {key: {bumps, bumped}} (batched for one page; cap the keys count); POST /api/bumps and DELETE /api/bumps with {key, device_id}, idempotent, return {bumps, bumped}; 400 bad_device_id (non-UUID), 404 when the key is not a currently existing insight, 429 over limit. Bumps on insights that later vanish are kept but not shown.
>    Frontend: reuse lib/device.ts and the reviewed BumpButton behaviour (optimistic update, per-post rollback with "Couldn't send that bump", out-of-order answer guard, cancel only when counts loaded + refetch after settle when not loaded, disabled with "Bumps need this browser to remember you" when storage blocked). Put the button on the SHARED insight row component(s) so every insight list gets it; batch counts per page (a provider/context or a hook that collects visible keys → one GET). No admin wipe card, no share images.
> 2. "Which one are you?" on Home's me slot when no "me" is set (getMe()==null && !isMeSkipped()): name search, pick → fills the Your panel, "Not a shooter / skip" hides it on the device, "Not me" clears. Reuse the reviewed WhichOneAreYou component (with the final-review fixes: live region, 8-result cap test, focus management, useShooters({enabled}) instead of a duplicate hook). Remove/adjust Home copy that tells people to go to Shooters and tap "That's me" if it conflicts.
>
> Owner rules: app copy never he/she/his/her; named-shooter text positive only; invented names only in tests/docs; every chart keeps Table/CSV/fullscreen/explainer; nothing currently on Home is removed.

## Global Constraints

**Owner rules (binding), verbatim:**

- App copy never uses he/she/his/her.
- Named-shooter text is positive or neutral only. Negatives appear only at the club or field level.
- No skill-rating ranking and no rivals or head-to-head. Nobody is ever shown who bumped.
- Real people's names never appear in the repo. Tests and docs use the invented names: `Ike Hadley` / `Hadley, Ike` (shooter 3), `Amy Ace`, `Bob Bee`, `Cal Cy`, `Pat Kim`, and the e2e fixture names already in `frontend/e2e`.
- Every chart keeps Table, CSV, fullscreen and its explainer. This plan adds no chart and changes none.
- Nothing currently on Home is removed.

**Repo conventions:**

- Python `3.13`, Node `22` LTS and Postgres `17`, with `uv` (backend) and `pnpm` (frontend). This plan adds no package. Never edit `[project].dependencies`, `[dependency-groups]`, `uv.lock`, `dependencies`, `devDependencies` or `pnpm-lock.yaml`.
- Coverage floor is **90% lines AND 90% branches**, with backend and frontend measured separately. `ratchets/` is controller-only.
- Backend gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src`. Frontend gates: `pnpm lint` (`eslint --max-warnings 0`), `pnpm typecheck` (which first regenerates the gitignored `src/api/schema.d.ts` with `pnpm gen:api`) and `pnpm exec prettier --check .`.
- **Strict TDD with evidence:** every production change starts from a failing test. Each implementer report pastes the RED output (the failing run) and then the GREEN output (the passing run) for every step pair. Reviewers re-run the task's new tests on the task's base to prove they fail there.
- Migrations are expand-only and compatible with the previous release (`api` runs `alembic upgrade head` on start). This plan's one migration is `0006_insight_bumps`. Its two tables are durable: `domain/rebuild.py` `LIVE_TABLES` never lists them.
- Routers are discovered (C2). A module `api/routes/<name>.py` needs a viewer. Never edit `api/app.py`. Every `features/<name>/mocks.ts` `handlers` export is merged into the shared MSW server, which errors on unhandled requests (`src/test/setup.ts`).
- Viewports: phone `390×844` and desktop `1440×900` are both first-class. Tap targets are at least 44 px, no page scrolls sideways, and the e2e runs at both sizes.
- Copy says "Sunday", never "event", and never uses "class".
- The theme is dark only and uses the existing Tailwind tokens (`bg-elevated`, `bg-surface`, `bg-primary`, `text-text`, `text-text-muted`, `text-accent`, `border-outline-variant`, `border-accent`, `rounded-card`, `rounded-button`). Never hard-code a colour.
- Stage files explicitly (`git add <paths>`). Never `git add -A`: the repo root can hold untracked workbooks.
- Every PR runs the full Playwright suite under the required `ci-ok`. A task that changes visible copy also updates the existing e2e that asserts that copy, in the same task (lesson PF-1 from the Sheet ledger).
- Workflows stay at about 10 agents or fewer. Non-conflicting lanes run in parallel (the waves below).
- Actions budget: Pro included minutes plus the $75 Actions budget. If CI is blocked by billing, stop and tell the owner.

## Review Focus

Five inputs or conditions that the design implies but does not spell out, and that are most likely to bite a person using this. Each is pinned to tests in the task that owns the code.

1. **A profile with more insights than one ask can carry.** "Show all" on a busy profile can list well over 100 insights. Expected: the server refuses more than 100 keys with 400 `too_many_keys`, and the client splits a larger set into parallel asks of at most 100 and merges them, so every card still gets its count. Tests: Task 1 `test_at_most_100_keys_per_ask_and_duplicates_count_once`. Task 2 `api.test.tsx` "splits more than 100 keys into parallel asks and merges the answers".
2. **An insight that disappears while the page is open.** A recompute drops or re-keys an insight that someone is looking at. Expected: the bumps stay in the table, the next counts leave the key out, a tap on it gets 404 `insight_not_found`, and the button rolls back and says "Couldn’t send that bump". Tests: Task 1 `test_an_insight_that_is_gone_keeps_its_bumps_but_never_shows`. Task 2 `BumpButton.test.tsx` "rolls back and says so when the insight is gone (404)".
3. **The same insight on screen twice.** A kudos insight can show in the kudos chip's sheet and in a list on the same page. Expected: both buttons show one count and agree after a tap. Test: Task 2 `FeedSections.test.tsx` "one insight shown twice shares one count".
4. **The key set changes under the counts.** A profile's "Show all" adds keys, which makes a new counts query. Expected: the cards already on screen keep their counts while the new set loads, with no flash to 0. Tests: Task 2 `FeedSections.test.tsx` "keeps the counts on screen while Show all loads more" and "a tap while Show all loads keeps the other cards’ counts".
5. **A browser that cannot keep a device id on Home.** Private mode or blocked site data. Expected: Home renders, every bump button is disabled with "Bumps need this browser to remember you" said once per section (not once per card), counts still show, and no `device_id` is sent. Test: Task 2 `FeedSections.test.tsx` "turns bumps off, says why once, and still shows counts when storage is blocked".

## Decisions

1. **Column name `insight_key`.** The table is `fist_bumps(insight_key text, device_id uuid, created_at timestamptz)` with PK `(insight_key, device_id)`. That matches `insight_picks.insight_key`. The ported Sheet code said `post_key`, a Sheet-only term. The JSON field is `key`, as the design says.
2. **Migration revision `0006`, file `0006_insight_bumps.py`.** The parked Sheet branch also has a `0006`. That branch is not to be merged, and if it is ever revived it must rebase onto this one and drop its own `0006`. That is noted here so nobody is surprised.
3. **"Currently existing insight" means a row in `insights` now.** `existing_keys(session, keys)` runs one `SELECT key FROM insights WHERE key IN (…)` and does no per-key work. A row that exists but is not shown on some page (for example, superseded on Home) still counts as existing. That is harmless: its count simply appears wherever it is shown.
4. **Batch cap 100 keys per GET (`MAX_KEYS = 100`).** Keys are 20 hex characters, so 100 keys come to about 2.1 KB of URL, well under proxy limits (Traefik, Cloudflare). Home's feed is at most about 50 keys, and a capped profile about 35. An uncapped "Show all" can exceed 100, so the client splits the set into chunks of `BATCH = 100` inside one query function (one TanStack query, N parallel requests). Duplicates are removed on both sides. An empty `keys` returns `{}`. A key longer than 200 characters can never be an insight, so GET refuses it with 400 `bad_key` (the whole request fails; real keys are 20 hex characters, so this never happens in practice). A bump belongs to the insight's identity (its key), not its current wording, so evergreen insights keep their bumps when their numbers change. The POST/DELETE body rejects it with 422 (`max_length=200`, ported).
5. **The GET leaves out unknown keys instead of answering 404.** Its keys come from feeds that may be a recompute behind, so a 404 would break a whole section over one stale key. The write endpoints answer 404 `insight_not_found` (the design's rule).
6. **Rate limit.** 600 actions per client IP per 10 minutes (controller ruling P15-R3, raised from the ported 120: club Wi-Fi and carrier NAT put 20 to 30 phones behind one IPv4 address, and the shoot is when bumps get used; bumps are idempotent per device, so the limit only guards against volume abuse), counted in `bump_attempts` through the shared `_count_since` and `_insert_and_prune` helpers. The login limiter is refactored onto those helpers, and its behaviour does not change. Every POST/DELETE that the limit itself does not refuse counts, including ones that then fail with 400 or 404, so key scanning is limited too. The action is recorded and committed before validation. GET is not limited.
7. **Cache rules (ported).** `api/etag.py` gains `NO_STORE_SUFFIXES = ("/bumps",)`, so `/api/bumps` is never ETagged and is `Cache-Control: no-store`. Insight feeds keep their data_version ETag and never carry counts.
8. **Store API trimmed.** `domain/bumps.py` keeps `add_bump`, `remove_bump`, `bump_states` and `bump_state`, ported verbatim apart from the rename. `wipe_bumps` and `bump_totals` existed only for the admin wipe card, which the design excludes (YAGNI), so they and their tests are not ported.
9. **Where the button lives.** `InsightCard` (every list: Top story, spotlight, "Around the club", Top insights on profiles, Sundays and the club/leaderboards/records/stations pages, More insights, and the kudos chip's sheet), `RecapCard` (Home's pinned "Last Sunday" insight) and each row of the kudos "and N more" sheet. Those are all the places on `main` that render an insight. **Year in Review renders no insight rows on `main`** (`features/yir` never imports the insights feature), so nothing is added there. If insight rows reach YiR later, they get bumps for free by rendering `InsightCard` inside a `BumpsProvider`.
10. **Batching by context, per feed section.** Each feed section (`HomeInsights`, `ProfileInsights`, `SundayInsights`, `PageInsights`) already holds its whole feed, so it wraps its output in `<BumpsProvider keys={feedKeys(feed)}>`. That makes one GET per section, which is one per page because each page mounts one section. `InsightBump` renders nothing outside a provider, so a lone `InsightCard` (in tests or a future preview) never fetches per card. The query key is `['/api/bumps', deviceId, sortedDistinctKeys]` with `staleTime: 0`. Every mount refetches, and a page reached by Back shows fresh counts. `placeholderData: keepPreviousData` keeps counts on screen when the key set changes (Review Focus 4).
11. **Bump state across pages.** Each section's query is separate. A bump on Home shows on a profile because that page refetches on mount (`staleTime: 0`), not through cache sharing. That is enough for counts that change any time.
12. **The "bumps off" note.** When `getDeviceId()` is null, the provider renders `<p id={noteId}>Bumps need this browser to remember you</p>` once, above its section's content, and every button in the section points `aria-describedby` at it. On Home, that puts one muted line above the insights cards.
13. **No layout shift from counts.** The button renders with the card in the same paint, with a count of 0 until the GET answers. Only the digits change, at a fixed button height of `min-h-11` and at the end of the card's existing action row. The card's own height therefore never depends on the counts. Task 4 measures this.
14. **BumpButton ported verbatim** apart from these props: `{queryKey, insightKey, deviceId, state, noteId}` replace `{date, postKey, …}`. `useBumpToggle(queryKey, deviceId, insightKey, shown)` is the reviewed toggle with the mutation scope `bump:{insightKey}`. That covers optimistic updates, per-insight rollback, the guard against out-of-order answers, cancelling only when the counts are loaded, and refetching after settle when they are not. One addition: `shown` is the counts the section has on screen (the provider's `bumps.data`, which includes the `keepPreviousData` placeholder). When the cache entry for `queryKey` is empty, because a new key set is still loading after "Show all", `send` seeds the optimistic map and `previous` from `shown`, so no other card drops to 0 (Review Focus 4), and it keeps `refetch: true`. `InsightBump` passes it through `BumpButton`'s optional `counts` prop.
15. **Data attribute.** `InsightCard`'s `<li>`, `RecapCard`'s action row and the kudos rows carry `data-insight-key={key}` so e2e can find one insight's button.
16. **"Which one are you?" placement.** `HomePage`'s `aside[aria-label="Personal"]` shows `WhichOneAreYou` when `meId === null && !skipped`, and otherwise `MePanel`, unchanged except for "Not me". The component moves to `features/home/components/WhichOneAreYou.tsx` because `main` has no sheet feature. Its code is ported verbatim, including the final-review fixes (the always-present `role="status"` live region, the 8-result cap, and `useShooters(query, false, { enabled })`).
17. **Copy after a skip, and the other “That’s me” prompts.** After "Not a shooter / skip", the question goes away and `MePanel`'s existing prompt shows ("Find yourself in Shooters and tap “That’s me”…" plus "Go to Shooters"). That prompt is current Home content (owner rule: nothing removed), and it is still the right way back for someone who skipped. It does not conflict, because it only shows once the question has been dismissed. Two e2e checks of `home.spec.ts` that asserted the prompt on a fresh visit now assert the question (Task 3).
    - **`NextSundayCard` (`features/predictions/homeWidget.tsx`, `slot: 'main'`) does conflict.** It renders whenever `meId` is null, so on every fresh visit it says "Choose “That’s me” on your Shooters profile to see your own expected score here." right beside the new question. Task 3 rewrites that line to point at the question first: "To see your own expected score here, pick your name in “Which one are you?” or choose “That’s me” on your Shooters profile." The "Go to Shooters" link stays (nothing on Home is removed), so the line still makes sense after a skip, when only the Shooters route is left. Task 3 updates `NextSundayCard.test.tsx` and `e2e/predictions.spec.ts` (the `/Choose “That’s me”/` assertion) in the same task (PF-1).
    - **`NextTrophy` (`slot: 'me'`) needs no change.** It renders only inside `MePanel`'s `MeDetails`, where `meId` is set, so its "Tap “That’s me”…" prompt never shows on Home when there is no "me" and never sits beside the question.
18. **"Not me".** `main` has no "Not me" today. `MePanel` gets a `Not me` ghost button in its card header when `meId` is set. It calls `clearMe()` and `onCleared()`, and the question comes back because `clearMe` does not set the skip (ported `lib/me.ts` semantics). Picking anyone (`setMe`, from the question or the profile's "That's me") clears an earlier skip.
19. **Focus management (ported from the Sheet's `YourSunday`).** When the personal slot swaps cards (pick, skip, "Not me" or "Choose again"), focus moves to the new card's `h2` (`tabIndex = -1`), so keyboard and screen-reader users are not dropped at the top of the page.
20. **e2e collisions.** Both Playwright projects share one stack, and they may share the same `sc.device` through the auth storage state. So the bump round-trip test bumps a different insight per project: desktop uses Home's `hero`, and mobile uses Home's first `top` card. It reads "before" from the GET body and deletes its bump in `finally` (ported from the Sheet's reviewed T11).

## File map

| File | Task | Responsibility |
|---|---|---|
| `backend/migrations/versions/0006_insight_bumps.py` | 1 | `fist_bumps` and `bump_attempts` |
| `backend/src/sunday_clays/models/bumps.py`, `models/__init__.py` | 1 | ORM models |
| `backend/src/sunday_clays/domain/bumps.py` | 1 | Idempotent bump store |
| `backend/src/sunday_clays/auth/ratelimit.py` | 1 | Shared limiter helpers and the bump limit |
| `backend/src/sunday_clays/analytics/insights/store.py` | 1 | `existing_keys` (one query) |
| `backend/src/sunday_clays/api/etag.py` | 1 | `/bumps` never tagged or stored |
| `backend/src/sunday_clays/api/routes/bumps.py` | 1 | `GET/POST/DELETE /api/bumps` |
| `frontend/src/lib/me.ts` | 3 | `isMeSkipped`, `skipMe` |
| `frontend/src/features/shooters/api.ts` | 3 | `useShooters(q, active, { enabled })` |
| `frontend/src/features/home/components/WhichOneAreYou.tsx` | 3 | The question |
| `frontend/src/features/home/components/MePanel.tsx` | 3 | "Not me" |
| `frontend/src/features/home/pages/HomePage.tsx` | 3 | Personal slot swap and focus |
| `frontend/e2e/home.spec.ts` | 3 | Two prompt assertions become the question |
| `frontend/src/features/predictions/components/NextSundayCard.tsx`, `NextSundayCard.test.tsx` | 3 | No-"me" line points at "Which one are you?" (Decision 17) |
| `frontend/e2e/predictions.spec.ts` | 3 | Its no-"me" copy assertion follows the new line |
| `frontend/src/lib/device.ts` | 2 | This browser's device id |
| `frontend/src/features/bumps/{api.ts, mocks.ts, BumpButton.tsx, BumpsProvider.tsx}` | 2 | Counts, toggle, button, per-section batching |
| `frontend/src/features/insights/feedKeys.ts` | 2 | Every key a feed shows |
| `frontend/src/features/insights/components/{InsightCard, RecapCard, KudosStrip, FeedSections}.tsx` | 2 | The button on every insight row; a provider per section |
| `frontend/e2e/insight-bumps.spec.ts` | 4 | End to end at both viewports |

## Waves

Tasks in one wave touch disjoint files and can run in parallel lanes. A wave starts once every PR of the waves before it has merged into `feat/insight-bumps`.

| Wave | Tasks (parallel) | Needs |
|---|---|---|
| 1 | Task 1 ∥ Task 3 | — (Task 1 is backend only; Task 3 is `lib/me`, `shooters/api`, `features/home/*`, `predictions/components/NextSundayCard*`, `e2e/home.spec.ts`, `e2e/predictions.spec.ts`) |
| 2 | Task 2 | Task 1 (the frontend types come from the new routes through `pnpm gen:api`) |
| 3 | Task 4 | Tasks 1–3 |

## Running the e2e stack (Tasks 2, 3 and 4)

From the worktree root, build and start a stack from the branch on its own port, then run Playwright against it:

```bash
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh   # once per worktree
E2E_PORT=18080 IMAGE_TAG=task15 docker compose -p task15 -f compose.yaml -f compose.test.yaml build
E2E_PORT=18080 IMAGE_TAG=task15 docker compose -p task15 -f compose.yaml -f compose.test.yaml up -d --wait
cd frontend && pnpm exec playwright install chromium
E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test <specs>
```

Afterwards, run `docker compose -p task15 -f compose.yaml -f compose.test.yaml down -v`.

---

### Task 1: Backend bump store and the insight-keyed API

Ports the reviewed Sheet backend: migration, models, store, limiter and cache rule. The route is new and keyed by insight.

**Files:**
- Create: `backend/migrations/versions/0006_insight_bumps.py` (port of the Sheet's `0006_fist_bumps.py`, with `post_key` renamed to `insight_key`)
- Create: `backend/src/sunday_clays/models/bumps.py` (port, renamed)
- Modify: `backend/src/sunday_clays/models/__init__.py`
- Create: `backend/src/sunday_clays/domain/bumps.py` (port, renamed, without `wipe_bumps`/`bump_totals`)
- Modify: `backend/src/sunday_clays/auth/ratelimit.py` (port verbatim)
- Modify: `backend/src/sunday_clays/analytics/insights/store.py` (add `existing_keys`)
- Modify: `backend/src/sunday_clays/api/etag.py` (port verbatim)
- Create: `backend/src/sunday_clays/api/routes/bumps.py`
- Modify: `backend/tests/integration/models/test_schema_0001.py`
- Create: `backend/tests/integration/domain/test_bumps_store.py` (port, renamed, trimmed)
- Create: `backend/tests/integration/auth/test_bump_rate_limit.py` (port verbatim)
- Create: `backend/tests/integration/insights/test_existing_keys.py`
- Modify: `backend/tests/unit/api/test_etag_helpers.py`
- Create: `backend/tests/integration/api/test_bumps_api.py`

**Interfaces:**
- Consumes: `analytics.insights.store.insights_table() -> Table`, `load_rows(session, *where) -> list[InsightRow]` (`InsightRow.key: str`); `auth.deps.client_ip(request) -> str`, `TooManyRequestsError` (429); `domain.errors.DomainError` (400), `NotFoundError` (404); the fixtures `session`, `committed_engine`, `fx_session`, `fx_viewer_client`, `scratch_engine`.
- Produces (Task 2 relies on the OpenAPI that these generate):
  - `GET /api/bumps` with query `keys: str = ""` (comma-separated) and `device_id: str | None` → `dict[str, BumpStateOut]`. `BumpStateOut = {bumps: int, bumped: bool}`.
  - `POST /api/bumps` and `DELETE /api/bumps` with body `BumpIn = {key: str (1..200), device_id: str}` → `BumpStateOut`.
  - Errors: 400 `bad_device_id`, 400 `too_many_keys`, 404 `insight_not_found`, 429 `rate_limited`, 401 without a viewer session.
  - `api.routes.bumps.MAX_KEYS = 100`, `parse_device_id(value: str) -> uuid.UUID`, `parse_keys(raw: str) -> list[str]`.
  - `store.existing_keys(session: Session, keys: Collection[str]) -> set[str]`.
  - `domain.bumps`: `BumpState(bumps: int, bumped: bool)`, `add_bump(session, insight_key: str, device_id: uuid.UUID) -> None`, `remove_bump(...) -> None`, `bump_states(session, insight_keys: Collection[str], device_id: uuid.UUID | None) -> dict[str, BumpState]`, `bump_state(session, insight_key, device_id) -> BumpState`.
  - `auth.ratelimit`: `BUMP_LIMIT = 600`, `BUMP_WINDOW = timedelta(minutes=10)`, `bumps_limited(session, ip) -> bool`, `record_bump_action(session, ip) -> None`.

- [ ] **Step 1: Write the failing migration test**

In `backend/tests/integration/models/test_schema_0001.py`, replace

```python
    "insights",  # 0003 (Plan 12)
    "insight_picks",  # 0003 (Plan 12)
}
TABLES_0003 = {"insights", "insight_picks"}
```

with

```python
    "insights",  # 0003 (Plan 12)
    "insight_picks",  # 0003 (Plan 12)
    "fist_bumps",  # 0006 (Plan 15)
    "bump_attempts",  # 0006 (Plan 15)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}
```

and in `test_upgrade_downgrade_roundtrip` replace

```python
    _alembic(scratch_engine, "downgrade", "0004")  # 0005 drops the station labels
    _alembic(scratch_engine, "downgrade", "0003")  # 0004 is a data-only no-op
    _alembic(scratch_engine, "downgrade", "0002")  # 0003 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0001")  # 0002 drops only its index
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003) | {"alembic_version"}
```

with

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

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: FAIL in `test_upgrade_downgrade_roundtrip`, because the migrated tables lack `fist_bumps` and `bump_attempts`.

- [ ] **Step 3: Add the migration and the models**

Create `backend/migrations/versions/0006_insight_bumps.py`:

```python
"""insight bumps: anonymous per-device fist bumps on insights, and their rate-limit log

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01

Expand-only: two new tables that the previous release never reads, so it runs unchanged on this
schema. Both are durable: rebuild_live only clears the live tables (domain/rebuild.py LIVE_TABLES).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fist_bumps",
        sa.Column("insight_key", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("insight_key", "device_id", name=op.f("pk_fist_bumps")),
    )
    op.create_table(
        "bump_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bump_attempts")),
    )
    op.create_index(op.f("ix_bump_attempts_ip_at"), "bump_attempts", ["ip", "at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_bump_attempts_ip_at"), table_name="bump_attempts")
    op.drop_table("bump_attempts")
    op.drop_table("fist_bumps")
```

Create `backend/src/sunday_clays/models/bumps.py`:

```python
"""Fist bumps on insights and their rate-limit log (Plan 15); durable, never rebuilt."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class FistBump(Base):
    """One anonymous bump: an insight key and the random id of the device that bumped it."""

    __tablename__ = "fist_bumps"

    insight_key: Mapped[str] = mapped_column(Text, primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BumpAttempt(Base):
    """One bump action (add or take back) per row, for the per-IP rate limit."""

    __tablename__ = "bump_attempts"
    __table_args__ = (Index(conv("ix_bump_attempts_ip_at"), "ip", "at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

In `backend/src/sunday_clays/models/__init__.py`, add the import line `from sunday_clays.models.bumps import BumpAttempt, FistBump` directly after `from sunday_clays.models.base import Base`. Add `"BumpAttempt",` after `"Base",` and `"FistBump",` after `"EventWeather",` in `__all__`, which keeps it alphabetical.

- [ ] **Step 4: Run it to verify it passes**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`
Expected: PASS, including `test_migration_matches_models` and `test_server_defaults_match_models`.

- [ ] **Step 5: Write the failing store tests**

Create `backend/tests/integration/domain/test_bumps_store.py`:

```python
"""Fist-bump store (Plan 15 Task 1): idempotent writes, per-device state and durability."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import run_pipeline
from sunday_clays.domain.bumps import (
    BumpState,
    add_bump,
    bump_state,
    bump_states,
    remove_bump,
)
from sunday_clays.domain.rebuild import LIVE_TABLES, rebuild_live
from sunday_clays.models import FistBump

A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
B = uuid.UUID("00000000-0000-4000-8000-00000000000b")


def test_add_is_idempotent_per_device(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "k1", A)
    add_bump(session, "k1", B)
    assert bump_state(session, "k1", A) == BumpState(2, True)
    assert bump_state(session, "k1", None) == BumpState(2, False)


def test_add_over_a_row_another_writer_stored_never_raises(session: Session) -> None:
    session.execute(insert(FistBump).values(insight_key="k1", device_id=A))
    add_bump(session, "k1", A)
    assert bump_state(session, "k1", A) == BumpState(1, True)


def test_concurrent_identical_bumps_store_one_row(committed_engine: Engine) -> None:
    with Session(committed_engine) as first, Session(committed_engine) as second:
        add_bump(first, "k1", A)  # holds the key's index entry until it commits

        def racer() -> None:
            add_bump(second, "k1", A)  # waits for `first`, then does nothing
            second.commit()

        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(racer)
            first.commit()
            waiting.result(timeout=10)
    with Session(committed_engine) as check:
        assert bump_state(check, "k1", A) == BumpState(1, True)


def test_remove_is_idempotent_and_never_goes_negative(session: Session) -> None:
    add_bump(session, "k1", A)
    remove_bump(session, "k1", A)
    remove_bump(session, "k1", A)
    remove_bump(session, "k2", B)
    assert bump_state(session, "k1", A) == BumpState(0, False)


def test_states_zero_fill_asked_keys_and_ignore_the_rest(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "stale", A)
    assert bump_states(session, ["k1", "k2", "k1"], A) == {
        "k1": BumpState(1, True),
        "k2": BumpState(0, False),
    }
    assert bump_states(session, [], A) == {}


def test_bump_tables_are_not_live_tables() -> None:
    assert "fist_bumps" not in LIVE_TABLES
    assert "bump_attempts" not in LIVE_TABLES


def test_bumps_survive_a_rebuild_and_a_recompute(fx_session: Session) -> None:
    add_bump(fx_session, "k1", A)
    rebuild_live(fx_session)
    run_pipeline(fx_session)
    assert bump_state(fx_session, "k1", A) == BumpState(1, True)


def test_remove_takes_back_one_device_on_one_insight_only(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "k2", A)
    add_bump(session, "k1", B)
    remove_bump(session, "k1", A)
    assert bump_state(session, "k2", A) == BumpState(1, True)
    assert bump_state(session, "k1", B) == BumpState(1, True)
    assert bump_state(session, "k1", A) == BumpState(1, False)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_bumps_store.py`
Expected: ERROR at collection: `ModuleNotFoundError: No module named 'sunday_clays.domain.bumps'`.

- [ ] **Step 7: Write the store**

Create `backend/src/sunday_clays/domain/bumps.py`:

```python
"""Fist-bump store (Plan 15): one row per (insight key, device), so every write is idempotent.

Nothing here checks that an insight exists: the API checks the key before it writes, and a bump
on an insight that later disappears (a recompute or a data correction) is kept but never shown.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.models import FistBump


@dataclass(frozen=True)
class BumpState:
    bumps: int
    bumped: bool


def add_bump(session: Session, insight_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: a repeat from the same device, even a concurrent one, changes nothing."""
    session.execute(
        pg_insert(FistBump)
        .values(insight_key=insight_key, device_id=device_id)
        .on_conflict_do_nothing(index_elements=[FistBump.insight_key, FistBump.device_id])
    )


def remove_bump(session: Session, insight_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: taking back a bump that is not there changes nothing."""
    session.execute(
        delete(FistBump).where(
            FistBump.insight_key == insight_key, FistBump.device_id == device_id
        )
    )


def bump_states(
    session: Session, insight_keys: Collection[str], device_id: uuid.UUID | None
) -> dict[str, BumpState]:
    """The count and "this device bumped it" for each key; a key nobody bumped is (0, False)."""
    keys = sorted(set(insight_keys))
    if not keys:
        return {}
    counts = {
        str(key): int(n)
        for key, n in session.execute(
            select(FistBump.insight_key, func.count())
            .where(FistBump.insight_key.in_(keys))
            .group_by(FistBump.insight_key)
        )
    }
    mine: set[str] = set()
    if device_id is not None:
        mine = set(
            session.scalars(
                select(FistBump.insight_key).where(
                    FistBump.insight_key.in_(keys), FistBump.device_id == device_id
                )
            )
        )
    return {key: BumpState(counts.get(key, 0), key in mine) for key in keys}


def bump_state(session: Session, insight_key: str, device_id: uuid.UUID | None) -> BumpState:
    return bump_states(session, [insight_key], device_id)[insight_key]
```

- [ ] **Step 8: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_bumps_store.py`
Expected: 8 passed. The rebuild test recomputes the fx world, so it takes a few seconds.

- [ ] **Step 9: Write the failing limiter tests** (ported verbatim)

Create `backend/tests/integration/auth/test_bump_rate_limit.py`:

```python
"""Bump rate limit (Plan 15 Task 1): 120 actions per client IP per 10 minutes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import (
    BUMP_LIMIT,
    bumps_limited,
    record_bump_action,
)
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["bump_attempts"]


def _actions(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at}] * n)


def test_120_actions_are_allowed_and_the_next_is_limited(session: Session) -> None:
    ip = "203.0.113.7"
    for _ in range(BUMP_LIMIT):
        assert bumps_limited(session, ip) is False
        record_bump_action(session, ip)
    assert BUMP_LIMIT == 120
    assert bumps_limited(session, ip) is True  # the 121st is refused


def test_window_edges_are_10_minutes(session: Session) -> None:
    _actions(session, "203.0.113.7", BUMP_LIMIT, age=timedelta(minutes=10, seconds=30))
    assert bumps_limited(session, "203.0.113.7") is False
    _actions(session, "198.51.100.1", BUMP_LIMIT, age=timedelta(minutes=9, seconds=30))
    assert bumps_limited(session, "198.51.100.1") is True


def test_limited_from_the_120th_action_in_the_window(session: Session) -> None:
    _actions(session, "203.0.113.7", BUMP_LIMIT - 1)
    assert bumps_limited(session, "203.0.113.7") is False
    _actions(session, "203.0.113.7", 1)
    assert bumps_limited(session, "203.0.113.7") is True


def test_actions_outside_the_window_and_other_ips_do_not_count(session: Session) -> None:
    _actions(session, "203.0.113.7", BUMP_LIMIT, age=timedelta(minutes=11))
    _actions(session, "198.51.100.1", BUMP_LIMIT)
    assert bumps_limited(session, "203.0.113.7") is False
    assert bumps_limited(session, "198.51.100.1") is True


def test_record_inserts_one_row_and_prunes_rows_outside_the_window(session: Session) -> None:
    _actions(session, "198.51.100.1", 1, age=timedelta(minutes=11))
    _actions(session, "198.51.100.1", 1, age=timedelta(minutes=9))
    record_bump_action(session, "203.0.113.7")
    rows = session.execute(select(ATTEMPTS.c.ip).order_by(ATTEMPTS.c.id)).scalars().all()
    assert rows == ["198.51.100.1", "203.0.113.7"]
```

- [ ] **Step 10: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/auth/test_bump_rate_limit.py`
Expected: ERROR at collection: `ImportError: cannot import name 'BUMP_LIMIT' from 'sunday_clays.auth.ratelimit'`.

- [ ] **Step 11: Write the limiter** (ported verbatim from the Sheet's reviewed `auth/ratelimit.py`)

Replace the whole of `backend/src/sunday_clays/auth/ratelimit.py` with:

```python
"""Rate limits per client-IP bucket: failed logins (``login_attempts``, C4, C8) and fist bumps
(``bump_attempts``, Plan 15)."""

from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import ColumnElement, Table, delete, func, insert, select
from sqlalchemy.orm import Session

from sunday_clays.config import get_settings
from sunday_clays.models import Base

PRUNE_AFTER: Final = timedelta(days=1)


def _attempts() -> Table:
    return Base.metadata.tables["login_attempts"]


def _bump_attempts() -> Table:
    return Base.metadata.tables["bump_attempts"]


def _count_since(
    session: Session, t: Table, ip: str, since: datetime, *extra: ColumnElement[bool]
) -> int:
    """Rows in ``t`` for ``ip`` newer than ``since`` that also match ``extra``."""
    n = session.scalar(
        select(func.count()).select_from(t).where(t.c.ip == ip, t.c.at > since, *extra)
    )
    return n or 0


def _insert_and_prune(session: Session, t: Table, keep_for: timedelta, **values: object) -> None:
    """Insert one row stamped now and delete rows older than ``keep_for``, in the caller's txn."""
    now = datetime.now(UTC)
    session.execute(insert(t).values(at=now, **values))
    session.execute(delete(t).where(t.c.at < now - keep_for))


def is_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already has ``login_max_failures`` failures in the login window."""
    settings = get_settings()
    t = _attempts()
    since = datetime.now(UTC) - timedelta(minutes=settings.login_window_minutes)
    failures = _count_since(session, t, ip, since, t.c.success.is_(False))
    return failures >= settings.login_max_failures


def record_attempt(session: Session, ip: str, success: bool) -> None:
    """Insert one attempt and prune rows older than a day, inside the caller's transaction."""
    _insert_and_prune(session, _attempts(), PRUNE_AFTER, ip=ip, success=success)


# --- Plan 15: fist bumps -------------------------------------------------------------------------
BUMP_LIMIT: Final = 120
BUMP_WINDOW: Final = timedelta(minutes=10)


def bumps_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already made ``BUMP_LIMIT`` bump actions in the last ``BUMP_WINDOW``."""
    since = datetime.now(UTC) - BUMP_WINDOW
    return _count_since(session, _bump_attempts(), ip, since) >= BUMP_LIMIT


def record_bump_action(session: Session, ip: str) -> None:
    """Insert one action and prune rows outside the window, inside the caller's transaction."""
    _insert_and_prune(session, _bump_attempts(), BUMP_WINDOW, ip=ip)
```

- [ ] **Step 12: Run the new and the login limiter tests**

Run: `cd backend && uv run pytest -q tests/integration/auth/`
Expected: all pass. The 5 new tests pass, and the login limiter tests still pass, which shows its behaviour is unchanged.

- [ ] **Step 13: Write the failing `existing_keys` tests**

Create `backend/tests/integration/insights/test_existing_keys.py`:

```python
"""existing_keys (Plan 15 Task 1): which asked keys are stored insights now, in one query."""

from sqlalchemy import event
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.store import existing_keys, load_rows

GONE = "fedcba9876543210fedc"  # insight-shaped, in no insights row


def test_keeps_only_stored_insights_in_one_query(fx_session: Session) -> None:
    rows = load_rows(fx_session)
    assert len(rows) >= 2, "the fx world has insights"
    stored = {rows[0].key, rows[1].key}
    statements: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        statements.append(statement)

    connection = fx_session.connection()
    event.listen(connection, "before_cursor_execute", record)
    try:
        found = existing_keys(fx_session, [*stored, GONE, rows[0].key])
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert found == stored
    assert len(statements) == 1


def test_no_keys_asks_nothing(fx_session: Session) -> None:
    assert existing_keys(fx_session, []) == set()
```

- [ ] **Step 14: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/insights/test_existing_keys.py`
Expected: ERROR at collection: `ImportError: cannot import name 'existing_keys' from 'sunday_clays.analytics.insights.store'`.

- [ ] **Step 15: Add `existing_keys`**

In `backend/src/sunday_clays/analytics/insights/store.py`, replace

```python
from collections.abc import Mapping, Sequence
```

with

```python
from collections.abc import Collection, Mapping, Sequence
```

and replace

```python
def insights_table() -> Table:
    return _tables()[0]
```

with

```python
def insights_table() -> Table:
    return _tables()[0]


def existing_keys(session: Session, keys: Collection[str]) -> set[str]:
    """The asked keys that are stored insights now, in one query (Plan 15 bumps)."""
    wanted = sorted(set(keys))
    if not wanted:
        return set()
    insights = insights_table()
    return {str(k) for k in session.scalars(select(insights.c.key).where(insights.c.key.in_(wanted)))}
```

- [ ] **Step 16: Run them to verify they pass**

Run: `cd backend && uv run pytest -q tests/integration/insights/test_existing_keys.py`
Expected: 2 passed.

- [ ] **Step 17: Write the failing cache-rule rows**

In `backend/tests/unit/api/test_etag_helpers.py`, replace

```python
        ("GET", "/api/predictions/next", False),
        ("GET", "/index.html", False),
```

with

```python
        ("GET", "/api/predictions/next", False),
        ("GET", "/api/insights/home", True),
        ("GET", "/api/bumps", False),
        ("GET", "/index.html", False),
```

and replace

```python
        ("/api/admin/jobs/1", "no-store"),
        ("/assets/app.js", None),
```

with

```python
        ("/api/admin/jobs/1", "no-store"),
        ("/api/insights/home", "private, no-cache"),
        ("/api/bumps", "no-store"),
        ("/assets/app.js", None),
        ("/assets/bumps", None),
```

- [ ] **Step 18: Run it to verify it fails**

Run: `cd backend && uv run pytest -q tests/unit/api/test_etag_helpers.py`
Expected: FAIL on the `/api/bumps` eligibility row and the `/api/bumps` cache-control row.

- [ ] **Step 19: Add the cache rule** (ported verbatim from the Sheet)

In `backend/src/sunday_clays/api/etag.py`, replace

```python
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/")


def etag_eligible(method: str, path: str) -> bool:
    """GET under /api/, except health, auth, admin and predictions."""
    return method == "GET" and path.startswith("/api/") and not path.startswith(NO_ETAG_PREFIXES)


def cache_control_for(path: str) -> str | None:
    """`no-store` for auth/admin, `private, no-cache` for other /api paths."""
    if path.startswith(NO_STORE_PREFIXES):
        return "no-store"
```

with

```python
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/")
# Plan 15: fist-bump counts change without a data_version bump, so a data_version ETag would
# answer 304 with stale counts. They are never tagged and never stored.
NO_STORE_SUFFIXES: tuple[str, ...] = ("/bumps",)


def etag_eligible(method: str, path: str) -> bool:
    """GET under /api/, except health, auth, admin, predictions and bump counts."""
    return (
        method == "GET"
        and path.startswith("/api/")
        and not path.startswith(NO_ETAG_PREFIXES)
        and not path.endswith(NO_STORE_SUFFIXES)
    )


def cache_control_for(path: str) -> str | None:
    """`no-store` for auth, admin and bump counts, `private, no-cache` for other /api paths."""
    if path.startswith(NO_STORE_PREFIXES) or (
        path.startswith("/api/") and path.endswith(NO_STORE_SUFFIXES)
    ):
        return "no-store"
```

- [ ] **Step 20: Run the cache tests to verify they pass**

Run: `cd backend && uv run pytest -q tests/unit/api/test_etag_helpers.py tests/unit/api/test_etag_anonymous.py tests/integration/analytics_core/test_etag_middleware.py`
Expected: all pass.

- [ ] **Step 21: Write the failing API tests**

Create `backend/tests/integration/api/test_bumps_api.py`:

```python
"""/api/bumps on the fx world (Plan 15 Task 1): keyed by insight, idempotent, refused,
rate-limited and never cached."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.api.routes.bumps import MAX_KEYS
from sunday_clays.auth.ratelimit import BUMP_LIMIT
from sunday_clays.domain.bumps import BumpState, add_bump, bump_state
from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
B = "00000000-0000-4000-8000-00000000000b"
IP = {"X-Real-IP": "203.0.113.7"}
ATTEMPTS = Base.metadata.tables["bump_attempts"]
GONE = "fedcba9876543210fedc"  # insight-shaped, in no insights row


def _keys(client: TestClient, n: int = 2) -> list[str]:
    feed = client.get("/api/insights/home").json()
    keys = [row["key"] for row in feed["top"]] + [row["key"] for row in feed["more"]]
    assert len(keys) >= n, "the fx world's home feed has enough insights"
    return keys[:n]


def _post(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.post("/api/bumps", json={"key": key, "device_id": device}, headers=headers)


def _delete(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.request(
        "DELETE", "/api/bumps", json={"key": key, "device_id": device}, headers=headers
    )


def _counts(client: TestClient, keys: list[str], device: str | None = None, **headers: str):
    params = {"keys": ",".join(keys)} | ({} if device is None else {"device_id": device})
    return client.get("/api/bumps", params=params, headers=headers)


def test_bumping_is_idempotent_per_device_and_taking_back_too(
    fx_viewer_client: TestClient,
) -> None:
    key = _keys(fx_viewer_client)[0]
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, B).json() == {"bumps": 2, "bumped": True}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    assert _counts(fx_viewer_client, [key], B).json() == {key: {"bumps": 1, "bumped": True}}
    assert _counts(fx_viewer_client, [key], A).json() == {key: {"bumps": 1, "bumped": False}}


def test_counts_cover_every_asked_insight_with_zeros(fx_viewer_client: TestClient) -> None:
    keys = _keys(fx_viewer_client)
    counts = _counts(fx_viewer_client, keys).json()
    assert set(counts) == set(keys)
    assert all(state == {"bumps": 0, "bumped": False} for state in counts.values())
    assert fx_viewer_client.get("/api/bumps").json() == {}


def test_an_insight_that_is_gone_keeps_its_bumps_but_never_shows(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    key = _keys(fx_viewer_client)[0]
    add_bump(fx_session, GONE, uuid.UUID(A))
    assert set(_counts(fx_viewer_client, [key, GONE]).json()) == {key}
    response = _post(fx_viewer_client, GONE, B)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "insight_not_found"
    assert bump_state(fx_session, GONE, None) == BumpState(1, False)


def test_an_unknown_key_is_404(fx_viewer_client: TestClient) -> None:
    for key in (GONE, "trophy:no_such_trophy:2026-09-27"):
        for response in (_post(fx_viewer_client, key, A), _delete(fx_viewer_client, key, A)):
            assert response.status_code == 404, key
            assert response.json()["error"]["code"] == "insight_not_found"


def test_a_device_id_that_is_not_a_uuid_is_400(fx_viewer_client: TestClient) -> None:
    key = _keys(fx_viewer_client)[0]
    bad_ids = ("not-a-uuid", "00000000000040008000000000000000a", "{" + A + "}", A + "x", "0" * 65)
    for bad in bad_ids:
        for response in (
            _post(fx_viewer_client, key, bad),
            _delete(fx_viewer_client, key, bad),
            _counts(fx_viewer_client, [key], bad),
        ):
            assert response.status_code == 400, bad
            assert response.json()["error"]["code"] == "bad_device_id"
    assert _post(fx_viewer_client, key, A.upper()).status_code == 200


def test_at_most_100_keys_per_ask_and_duplicates_count_once(
    fx_viewer_client: TestClient,
) -> None:
    key = _keys(fx_viewer_client)[0]
    too_many = [f"{i:020x}" for i in range(MAX_KEYS + 1)]
    response = _counts(fx_viewer_client, too_many)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_many_keys"
    assert _counts(fx_viewer_client, too_many[:MAX_KEYS]).status_code == 200
    assert _counts(fx_viewer_client, [key] * (MAX_KEYS + 50)).json() == {
        key: {"bumps": 0, "bumped": False}
    }
    spaced = fx_viewer_client.get("/api/bumps", params={"keys": f" {key} ,, "}).json()
    assert spaced == {key: {"bumps": 0, "bumped": False}}


def test_the_120th_action_in_10_minutes_is_the_last(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    key = _keys(fx_viewer_client)[0]
    now = datetime.now(UTC)
    fx_session.execute(insert(ATTEMPTS), [{"ip": "203.0.113.7", "at": now}] * (BUMP_LIMIT - 1))
    assert _post(fx_viewer_client, key, A).status_code == 200
    refused = _delete(fx_viewer_client, key, A)
    assert refused.status_code == 429
    assert refused.json()["error"]["code"] == "rate_limited"
    other = {"X-Real-IP": "198.51.100.1"}
    assert _delete(fx_viewer_client, key, A, headers=other).json() == {
        "bumps": 0,
        "bumped": False,
    }
    assert _counts(fx_viewer_client, [key]).status_code == 200  # reading is never limited


def test_refused_requests_still_count_toward_the_limit(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    before = len(fx_session.execute(select(ATTEMPTS.c.id)).all())
    _post(fx_viewer_client, GONE, A)
    _post(fx_viewer_client, _keys(fx_viewer_client)[0], "nope")
    assert len(fx_session.execute(select(ATTEMPTS.c.id)).all()) == before + 2


def test_counts_are_never_cached_and_never_in_a_feed(fx_viewer_client: TestClient) -> None:
    key = _keys(fx_viewer_client)[0]
    before = fx_viewer_client.get("/api/insights/home")
    counts = _counts(fx_viewer_client, [key])
    assert counts.headers["cache-control"] == "no-store"
    assert "etag" not in counts.headers
    _post(fx_viewer_client, key, A)
    again = _counts(fx_viewer_client, [key], **{"If-None-Match": "*"})
    assert again.status_code == 200
    assert again.json() != counts.json()
    after = fx_viewer_client.get("/api/insights/home")
    assert after.json() == before.json()
    assert after.headers["etag"] == before.headers["etag"]
```

- [ ] **Step 22: Run them to verify they fail**

Run: `cd backend && uv run pytest -q tests/integration/api/test_bumps_api.py`
Expected: ERROR at collection: `ModuleNotFoundError: No module named 'sunday_clays.api.routes.bumps'`.

- [ ] **Step 23: Write the route**

Create `backend/src/sunday_clays/api/routes/bumps.py`. `parse_device_id` and the body of `_bump_action` are ported verbatim from the Sheet's reviewed `api/routes/sheet.py`. Only the key check and the names change.

```python
"""/api/bumps (Plan 15): anonymous fist bumps on insights, keyed by the insight's stable `key`.

Counts change without a data_version bump, so they are never part of an insight feed (which is
ETagged by data_version), and this path is never ETagged or stored (api/etag.py, "/bumps").
A bump on an insight that later disappears is kept but never listed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sunday_clays.analytics.insights.store import existing_keys
from sunday_clays.auth.deps import TooManyRequestsError, client_ip
from sunday_clays.auth.ratelimit import bumps_limited, record_bump_action
from sunday_clays.db import SessionDep
from sunday_clays.domain.bumps import add_bump, bump_state, bump_states, remove_bump
from sunday_clays.domain.errors import DomainError, NotFoundError

router = APIRouter(tags=["bumps"])

MAX_KEYS = 100


class BumpIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    device_id: str = Field(min_length=1)


class BumpStateOut(BaseModel):
    bumps: int
    bumped: bool


def parse_device_id(value: str) -> uuid.UUID:
    """A canonical UUID (8-4-4-4-12 hex, any case), else a 400."""
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        parsed = None
    if parsed is None or str(parsed) != value.lower():
        raise DomainError("bad_device_id", "device_id must be a UUID")
    return parsed


def parse_keys(raw: str) -> list[str]:
    """`k1,k2,…` as distinct non-empty keys in order; more than MAX_KEYS is a 400."""
    keys = list(dict.fromkeys(k for k in (part.strip() for part in raw.split(",")) if k))
    if len(keys) > MAX_KEYS:
        raise DomainError("too_many_keys", f"Ask for at most {MAX_KEYS} keys at a time")
    return keys


@router.get("/api/bumps")
def bump_counts(
    session: SessionDep, keys: str = "", device_id: str | None = None
) -> dict[str, BumpStateOut]:
    """Counts for the asked keys that are insights now, zeros included; any other key is left out."""
    device = None if device_id is None else parse_device_id(device_id)
    current = existing_keys(session, parse_keys(keys))
    states = bump_states(session, current, device)
    return {key: BumpStateOut(bumps=s.bumps, bumped=s.bumped) for key, s in states.items()}


def _bump_action(
    request: Request,
    session: Session,
    body: BumpIn,
    act: Callable[[Session, str, uuid.UUID], None],
) -> BumpStateOut:
    ip = client_ip(request)
    if bumps_limited(session, ip):
        raise TooManyRequestsError("rate_limited", "Too many bumps from here. Try again soon.")
    record_bump_action(session, ip)
    session.commit()  # get_session rolls back on any error; a refused action still counts
    device = parse_device_id(body.device_id)
    if not existing_keys(session, [body.key]):
        raise NotFoundError("insight_not_found", "That insight is not on the site now")
    act(session, body.key, device)
    state = bump_state(session, body.key, device)
    return BumpStateOut(bumps=state.bumps, bumped=state.bumped)


@router.post("/api/bumps")
def bump_insight(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: bumping twice from one device counts once."""
    return _bump_action(request, session, body, add_bump)


@router.delete("/api/bumps")
def unbump_insight(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: taking back a bump that is not there changes nothing."""
    return _bump_action(request, session, body, remove_bump)
```

- [ ] **Step 24: Run the API, auth-matrix and discovery tests**

Run: `cd backend && uv run pytest -q tests/integration/api/test_bumps_api.py tests/integration/api/test_route_auth_matrix.py tests/unit/api/test_routes_discovery.py tests/unit/api/test_export_openapi.py`
Expected: all pass. The auth matrix walks the three new routes and gets 401 without a session.

- [ ] **Step 25: Gates and the full backend suite with coverage**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src && uv run pytest -q --cov --cov-branch`
Expected: "All checks passed!", "N files already formatted", "Success: no issues found", the whole suite green, and coverage at or above 90% lines and 90% branches. If `ruff format --check` flags the long `existing_keys` return line, run `uv run ruff format .` and re-check.

- [ ] **Step 26: Commit**

```bash
git add backend/migrations/versions/0006_insight_bumps.py backend/src/sunday_clays/models/bumps.py backend/src/sunday_clays/models/__init__.py backend/src/sunday_clays/domain/bumps.py backend/src/sunday_clays/auth/ratelimit.py backend/src/sunday_clays/analytics/insights/store.py backend/src/sunday_clays/api/etag.py backend/src/sunday_clays/api/routes/bumps.py backend/tests/integration/models/test_schema_0001.py backend/tests/integration/domain/test_bumps_store.py backend/tests/integration/auth/test_bump_rate_limit.py backend/tests/integration/insights/test_existing_keys.py backend/tests/unit/api/test_etag_helpers.py backend/tests/integration/api/test_bumps_api.py
git commit -m "feat(bumps): insight-keyed fist bump store and /api/bumps (Plan 15 T1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Device id, bump hooks, BumpButton and a bump on every insight row

**Files:**
- Create: `frontend/src/lib/device.ts`, `frontend/src/lib/device.test.ts` (ported verbatim)
- Create: `frontend/src/features/bumps/api.ts`, `frontend/src/features/bumps/api.test.tsx`
- Create: `frontend/src/features/bumps/mocks.ts`
- Create: `frontend/src/features/bumps/BumpButton.tsx`, `frontend/src/features/bumps/BumpButton.test.tsx` (ported, with renamed props and endpoints)
- Create: `frontend/src/features/bumps/BumpsProvider.tsx`, `frontend/src/features/bumps/BumpsProvider.test.tsx`
- Create: `frontend/src/features/insights/feedKeys.ts`, `frontend/src/features/insights/feedKeys.test.ts`
- Modify: `frontend/src/features/insights/components/InsightCard.tsx`, `InsightCard.test.tsx`
- Modify: `frontend/src/features/insights/components/RecapCard.tsx`
- Modify: `frontend/src/features/insights/components/KudosStrip.tsx`, `KudosStrip.test.tsx`
- Modify: `frontend/src/features/insights/components/FeedSections.tsx`, `FeedSections.test.tsx`

**Interfaces:**
- Consumes (Task 1, through `pnpm gen:api`): `paths['/api/bumps']` GET (query `keys?: string`, `device_id?: string | null`), POST and DELETE (body `{key, device_id}`), and `components['schemas']['BumpStateOut'] = {bumps: number; bumped: boolean}`. From main: `Insight`, `InsightFeed` (`features/insights/api.ts`), `insightFixture`, `feedFixture`, `kudosFixture` (`features/insights/mocks.ts`), `renderWithProviders`, `createTestQueryClient` (`src/test/render.tsx`), `server` (`src/test/msw/server.ts`).
- Produces (Task 4 relies on these selectors and labels):
  - `lib/device.ts`: `newUuid(): string`, `getDeviceId(): string | null` (`localStorage['sc.device']`).
  - `features/bumps/api.ts`: `BATCH = 100`, `BUMPS_OFF = 'Bumps need this browser to remember you'`, `type BumpState`, `type BumpCounts = Record<string, BumpState>`, `bumpsKey(keys: readonly string[], deviceId: string | null)`, `type BumpsKey`, `sortedKeys(keys: Iterable<string>): string[]`, `useBumps(keys, deviceId)`, `toggled(old, key, bump): BumpCounts`, `useBumpToggle(queryKey: BumpsKey, deviceId: string, insightKey: string, shown?: BumpCounts): { send(bump: boolean): void; failed: boolean }`.
  - `BumpButton({queryKey, insightKey, deviceId, state, noteId, counts?})`: a button labelled `Fist bump, N bump(s)` with `aria-pressed`. On failure, a `role="alert"` "Couldn’t send that bump".
  - `BumpsProvider({keys, children})` and `InsightBump({insightKey})`.
  - `feedKeys(feed: InsightFeed): string[]`.
  - DOM: `[data-insight-key="<key>"]` on every insight row (`InsightCard` `<li>`, `RecapCard` action row, kudos "and N more" `<li>`).

- [ ] **Step 1: Regenerate the API types from Task 1**

Run: `cd frontend && pnpm gen:api`
Expected: `src/api/schema.d.ts` now has `"/api/bumps"` and `BumpStateOut`. The file is gitignored, so do not commit it.

- [ ] **Step 2: Write the failing device tests** (ported verbatim)

Create `frontend/src/lib/device.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getDeviceId, newUuid } from './device';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('newUuid', () => {
  it('uses crypto.randomUUID where the browser has it', () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('11111111-2222-4333-8444-555555555555');
    expect(newUuid()).toBe('11111111-2222-4333-8444-555555555555');
  });

  it('builds a version-4 UUID from getRandomValues on an insecure (plain http) page', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => bytes.fill(0xff),
    });
    expect(newUuid()).toBe('ffffffff-ffff-4fff-bfff-ffffffffffff');
    expect(newUuid()).toMatch(UUID_V4);
  });
});

describe('getDeviceId', () => {
  it('creates a UUID once and keeps it', () => {
    const id = getDeviceId();
    expect(id).toMatch(UUID_V4);
    expect(getDeviceId()).toBe(id);
    expect(localStorage.getItem('sc.device')).toBe(id);
  });

  it('replaces a stored value that is not a UUID instead of sending it', () => {
    localStorage.setItem('sc.device', 'hello');
    const id = getDeviceId();
    expect(id).toMatch(UUID_V4);
    expect(localStorage.getItem('sc.device')).toBe(id);
  });

  it('is null when storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    expect(getDeviceId()).toBeNull();
  });

  it('is null when storage does not keep what is written', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => undefined);
    expect(getDeviceId()).toBeNull();
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/device.test.ts`
Expected: FAIL: `Failed to resolve import "./device"`.

- [ ] **Step 4: Write the device id** (ported verbatim, with the docstring's plan reference updated)

Create `frontend/src/lib/device.ts`:

```ts
/**
 * The random id this browser sends with fist bumps (Plan 15), kept only in localStorage. It is
 * never tied to a name and goes nowhere but the bump requests.
 */
const KEY = 'sc.device';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * A random version-4 UUID. `crypto.randomUUID` exists only in secure contexts (https and
 * localhost), so a page opened over plain http on the LAN builds one from getRandomValues.
 */
export function newUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Byte 6 carries the version (4), byte 8 the RFC 4122 variant (10xx).
  const bytes = crypto
    .getRandomValues(new Uint8Array(16))
    .map((b, i) => (i === 6 ? (b & 0x0f) | 0x40 : i === 8 ? (b & 0x3f) | 0x80 : b));
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * This browser's device id, created on first use. Null when localStorage is unavailable or does
 * not keep what is written (private mode, blocked site data): bumps then stay disabled rather
 * than sending an id that changes on every visit.
 */
export function getDeviceId(): string | null {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored !== null && UUID.test(stored)) return stored;
    const id = newUuid();
    localStorage.setItem(KEY, id);
    return localStorage.getItem(KEY) === id ? id : null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/device.test.ts`
Expected: 6 passed.

- [ ] **Step 6: Write the failing bump API tests**

Create `frontend/src/features/bumps/api.test.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { createTestQueryClient } from '../../test/render';
import { BATCH, sortedKeys, toggled, useBumps } from './api';

const DEVICE = '00000000-0000-4000-8000-00000000000a';

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

describe('toggled', () => {
  it('adds and takes back this device’s bump', () => {
    const start = { k: { bumps: 2, bumped: false } };
    expect(toggled(start, 'k', true)).toEqual({ k: { bumps: 3, bumped: true } });
    expect(toggled({ k: { bumps: 3, bumped: true } }, 'k', false)).toEqual({
      k: { bumps: 2, bumped: false },
    });
  });

  it('is a no-op when the state already matches, and never goes below zero', () => {
    expect(toggled({ k: { bumps: 3, bumped: true } }, 'k', true)).toEqual({
      k: { bumps: 3, bumped: true },
    });
    expect(toggled({ k: { bumps: 0, bumped: true } }, 'k', false)).toEqual({
      k: { bumps: 0, bumped: false },
    });
  });

  it('starts an insight nobody bumped at zero and keeps the others', () => {
    expect(toggled(undefined, 'k', true)).toEqual({ k: { bumps: 1, bumped: true } });
    expect(toggled({ j: { bumps: 4, bumped: false } }, 'k', true)).toEqual({
      j: { bumps: 4, bumped: false },
      k: { bumps: 1, bumped: true },
    });
  });
});

describe('sortedKeys', () => {
  it('drops repeats and sorts, so one set is one query', () => {
    expect(sortedKeys(['b', 'a', 'b'])).toEqual(['a', 'b']);
  });
});

describe('useBumps', () => {
  it('asks once for every key, with this device', async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get('*/api/bumps', ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json({ a: { bumps: 2, bumped: true }, b: { bumps: 0, bumped: false } });
      }),
    );
    const { result } = renderHook(() => useBumps(['a', 'b'], DEVICE), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      a: { bumps: 2, bumped: true },
      b: { bumps: 0, bumped: false },
    });
    expect(asked).toHaveLength(1);
    expect(asked[0]?.get('keys')).toBe('a,b');
    expect(asked[0]?.get('device_id')).toBe(DEVICE);
  });

  it('sends no device id when this browser has none', async () => {
    const asked: URLSearchParams[] = [];
    server.use(
      http.get('*/api/bumps', ({ request }) => {
        asked.push(new URL(request.url).searchParams);
        return HttpResponse.json({});
      }),
    );
    const { result } = renderHook(() => useBumps(['a'], null), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(asked[0]?.has('device_id')).toBe(false);
  });

  it('asks nothing for no keys', () => {
    const { result } = renderHook(() => useBumps([], DEVICE), { wrapper });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('splits more than 100 keys into parallel asks and merges the answers', async () => {
    const sizes: number[] = [];
    server.use(
      http.get('*/api/bumps', ({ request }) => {
        const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',');
        sizes.push(keys.length);
        return HttpResponse.json(
          Object.fromEntries(keys.map((k) => [k, { bumps: 1, bumped: false }])),
        );
      }),
    );
    const keys = Array.from({ length: BATCH + 50 }, (_, i) => `k${String(i).padStart(3, '0')}`);
    const { result } = renderHook(() => useBumps(keys, DEVICE), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(sizes.sort((x, y) => y - x)).toEqual([100, 50]);
    expect(Object.keys(result.current.data ?? {})).toHaveLength(150);
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/bumps/api.test.tsx`
Expected: FAIL: `Failed to resolve import "./api"`.

- [ ] **Step 8: Write the bump API**

Create `frontend/src/features/bumps/api.ts`. `toggled` and `useBumpToggle` are ported verbatim from the Sheet's reviewed `features/sheet/api.ts` (renames only: `postKey` becomes `insightKey`, `bumpsKey(date, …)` becomes the passed `queryKey`, and the endpoint is `/api/bumps`). There is one addition: the optional `shown` argument. A section's key set can change under it (a profile's "Show all"), and while the new set loads the cache entry for the new key is empty and the provider is showing `keepPreviousData` placeholder counts. Seeding the optimistic write from the empty entry would write a map holding only the tapped insight and drop every other card to 0. So `send` seeds from `shown` (the counts on screen) when the entry is empty. Step 26's "a tap while Show all loads" test pins this.

```ts
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type BumpState = components['schemas']['BumpStateOut'];
export type BumpCounts = Record<string, BumpState>;

/** The server's cap on keys per GET /api/bumps (api/routes/bumps.py MAX_KEYS). */
export const BATCH = 100;

export const BUMPS_OFF = 'Bumps need this browser to remember you';

/** Distinct keys in a stable order, so one set of insights is one query. */
export function sortedKeys(keys: Iterable<string>): string[] {
  return [...new Set(keys)].sort();
}

export function bumpsKey(keys: readonly string[], deviceId: string | null) {
  return ['/api/bumps', deviceId, keys] as const;
}
export type BumpsKey = ReturnType<typeof bumpsKey>;

async function fetchCounts(keys: readonly string[], deviceId: string | null): Promise<BumpCounts> {
  const chunks: string[][] = [];
  for (let i = 0; i < keys.length; i += BATCH) chunks.push(keys.slice(i, i + BATCH));
  const device = deviceId === null ? {} : { device_id: deviceId };
  const parts = await Promise.all(
    chunks.map((chunk) =>
      unwrap(api.GET('/api/bumps', { params: { query: { keys: chunk.join(','), ...device } } })),
    ),
  );
  return parts.reduce<BumpCounts>((all, part) => ({ ...all, ...part }), {});
}

/**
 * Bump counts for one page section's insights: one request for up to BATCH keys, and more go
 * in parallel chunks. Never cached by the server, and refetched whenever a page mounts. While a
 * new set of keys loads (a profile's "Show all"), the previous counts stay on screen.
 */
export function useBumps(keys: readonly string[], deviceId: string | null) {
  return useQuery({
    queryKey: bumpsKey(keys, deviceId),
    queryFn: () => fetchCounts(keys, deviceId),
    enabled: keys.length > 0,
    staleTime: 0,
    placeholderData: keepPreviousData,
  });
}

/** `old` with this device's bump on `key` set to `bump` (a no-op when it already is). */
export function toggled(old: BumpCounts | undefined, key: string, bump: boolean): BumpCounts {
  const current = old?.[key] ?? { bumps: 0, bumped: false };
  if (current.bumped === bump) return { ...old, [key]: current };
  return {
    ...old,
    [key]: { bumps: Math.max(0, current.bumps + (bump ? 1 : -1)), bumped: bump },
  };
}

/**
 * Bump or take back a bump on one insight. The count changes at once (optimistic). The request
 * runs after any earlier one for the same insight (one mutation scope per insight), so two quick
 * taps reach the server in order. A failure puts this insight's count back and sets `failed`.
 * Only the last request for an insight writes the server's answer, so an earlier answer never
 * undoes a newer tap.
 */
export function useBumpToggle(
  queryKey: BumpsKey,
  deviceId: string,
  insightKey: string,
  /** The counts on screen, including a keepPreviousData placeholder while a new key set loads. */
  shown?: BumpCounts,
) {
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const mutationKey = ['bump', insightKey];
  const mutation = useMutation({
    mutationKey,
    scope: { id: `bump:${insightKey}` },
    mutationFn: ({
      bump,
    }: {
      bump: boolean;
      previous: BumpState | undefined;
      refetch: boolean;
    }) => {
      const body = { key: insightKey, device_id: deviceId };
      return bump
        ? unwrap(api.POST('/api/bumps', { body }))
        : unwrap(api.DELETE('/api/bumps', { body }));
    },
    onError: (_error, { previous }) => {
      // Only this insight goes back: a bump on another one may have succeeded meanwhile.
      qc.setQueryData<BumpCounts>(queryKey, (old) => ({
        ...old,
        [insightKey]: previous ?? { bumps: 0, bumped: false },
      }));
      setFailed(true);
    },
    onSuccess: (state) => {
      // This request still counts as pending here: 1 means no newer tap is queued behind it.
      if (qc.isMutating({ mutationKey }) <= 1) {
        qc.setQueryData<BumpCounts>(queryKey, (old) => ({ ...old, [insightKey]: state }));
      }
    },
    onSettled: (_data, _error, { refetch }) => {
      // The counts were not loaded when this was tapped, so the map holds only this insight: once
      // the last queued tap for it settles, fetch the whole map again.
      if (refetch && qc.isMutating({ mutationKey }) <= 1) {
        void qc.invalidateQueries({ queryKey });
      }
    },
  });
  function send(bump: boolean) {
    setFailed(false);
    const cached = qc.getQueryData<BumpCounts>(queryKey);
    const loaded = cached !== undefined && qc.getQueryState(queryKey)?.status !== 'error';
    // While a new key set loads ("Show all"), this key's entry is empty but the section still shows
    // the previous counts (keepPreviousData). Seed from those, so no other card flashes to 0.
    const counts = cached ?? shown;
    // A load still in flight is left alone: cancelling it would leave every other insight at 0.
    // (If it lands before this request settles, this insight may briefly look un-bumped;
    // onSuccess or the refetch in onSettled then corrects it.)
    if (loaded) void qc.cancelQueries({ queryKey });
    qc.setQueryData<BumpCounts>(queryKey, toggled(counts, insightKey, bump));
    mutation.mutate({ bump, previous: counts?.[insightKey], refetch: !loaded });
  }
  return { send, failed };
}
```

Create `frontend/src/features/bumps/mocks.ts`. It is merged into the shared MSW server, which errors on unhandled requests, so every test that renders an insight feed gets zero counts by default:

```ts
import { http, HttpResponse } from 'msw';

/** Zero counts for every asked key. Tests override this with server.use. */
export const handlers = [
  http.get('*/api/bumps', ({ request }) => {
    const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',').filter(Boolean);
    return HttpResponse.json(
      Object.fromEntries(keys.map((key) => [key, { bumps: 0, bumped: false }])),
    );
  }),
];
```

- [ ] **Step 9: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/bumps/api.test.tsx`
Expected: 8 passed.

- [ ] **Step 10: Write the failing BumpButton tests**

These are ported from the Sheet's reviewed `BumpButton.test.tsx`: the same eight behaviours, with the endpoints renamed, plus one new 404 case (Review Focus 2). Create `frontend/src/features/bumps/BumpButton.test.tsx`:

```tsx
import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../test/render';
import { bumpsKey, useBumps, type BumpCounts } from './api';
import { BumpButton } from './BumpButton';

const DEVICE = '00000000-0000-4000-8000-00000000000a';
const KEY = 'k-pb-3';
const KEYS = [KEY];
const A = 'k-a';
const B = 'k-b';
const TWO = [A, B];

/** The button wired to the bumps query, as an insight list renders it. */
function Harness({ deviceId = DEVICE }: { deviceId?: string | null }) {
  const bumps = useBumps(KEYS, deviceId);
  return (
    <>
      <p id="note">Bumps need this browser to remember you</p>
      <BumpButton
        queryKey={bumpsKey(KEYS, deviceId)}
        insightKey={KEY}
        deviceId={deviceId}
        state={bumps.data?.[KEY]}
        noteId="note"
      />
    </>
  );
}

function Two() {
  const bumps = useBumps(TWO, DEVICE);
  return (
    <>
      <p id="note">off</p>
      {TWO.map((k) => (
        <section key={k} aria-label={k}>
          <BumpButton
            queryKey={bumpsKey(TWO, DEVICE)}
            insightKey={k}
            deviceId={DEVICE}
            state={bumps.data?.[k]}
            noteId="note"
          />
        </section>
      ))}
    </>
  );
}

const buttonIn = (name: string) => within(screen.getByRole('region', { name })).getByRole('button');

function seeded(keys: string[], counts: BumpCounts) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(bumpsKey(keys, DEVICE), counts);
  server.use(http.get('*/api/bumps', () => HttpResponse.json(counts)));
  return queryClient;
}

describe('BumpButton', () => {
  it('counts the tap at once, before the server answers, then keeps the server count', async () => {
    let release: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('*/api/bumps', async () => {
        await answered;
        return HttpResponse.json({ bumps: 7, bumped: true });
      }),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    const button = screen.getByRole('button', { name: 'Fist bump, 2 bumps' });
    expect(button).toHaveAttribute('aria-pressed', 'false');
    await user.click(button);
    expect(screen.getByRole('button', { name: 'Fist bump, 3 bumps' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    release();
    expect(await screen.findByRole('button', { name: 'Fist bump, 7 bumps' })).toBeInTheDocument();
  });

  it('rolls back and says so when the bump fails', async () => {
    server.use(
      http.post('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('rolls back and says so when the insight is gone (404)', async () => {
    server.use(
      http.post('*/api/bumps', () =>
        HttpResponse.json(
          { error: { code: 'insight_not_found', message: 'x' } },
          { status: 404 },
        ),
      ),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 1, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 1 bump' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(screen.getByRole('button', { name: 'Fist bump, 1 bump' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('takes a bump back on a second tap, sends the taps in order and ignores the stale answer', async () => {
    const calls: string[] = [];
    const gate = () => {
      let open: () => void = () => undefined;
      const opened = new Promise<void>((resolve) => {
        open = resolve;
      });
      return { opened, open };
    };
    const post = gate();
    const del = gate();
    server.use(
      http.post('*/api/bumps', async () => {
        calls.push('POST');
        await post.opened;
        return HttpResponse.json({ bumps: 3, bumped: true });
      }),
      http.delete('*/api/bumps', async ({ request }) => {
        calls.push('DELETE');
        expect(await request.json()).toEqual({ key: KEY, device_id: DEVICE });
        await del.opened;
        return HttpResponse.json({ bumps: 2, bumped: false });
      }),
    );
    const queryClient = seeded(KEYS, { [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 3 bumps' }));
    await waitFor(() => expect(calls).toEqual(['POST']));
    post.open();
    await waitFor(() => expect(calls).toEqual(['POST', 'DELETE']));
    // The POST's answer (3, bumped) arrived while the DELETE was queued: it must not show.
    const held = screen.getByRole('button', { name: 'Fist bump, 2 bumps' });
    expect(held).toHaveAttribute('aria-pressed', 'false');
    del.open();
    await waitFor(() => expect(queryClient.isMutating()).toBe(0));
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('rolls back only the insight that failed, keeping a bump that succeeded meanwhile', async () => {
    let failA: () => void = () => undefined;
    const aHeld = new Promise<void>((resolve) => {
      failA = resolve;
    });
    server.use(
      http.post('*/api/bumps', async ({ request }) => {
        const body = (await request.json()) as { key: string };
        if (body.key === A) {
          await aHeld;
          return HttpResponse.json({ error: { code: 'not_found', message: 'x' } }, { status: 404 });
        }
        return HttpResponse.json({ bumps: 1, bumped: true });
      }),
    );
    const queryClient = seeded(TWO, {
      [A]: { bumps: 0, bumped: false },
      [B]: { bumps: 0, bumped: false },
    });
    const { user } = renderWithProviders(<Two />, { queryClient });
    await user.click(buttonIn(A));
    await user.click(buttonIn(B));
    await waitFor(() => expect(buttonIn(B)).toHaveAccessibleName('Fist bump, 1 bump'));
    failA();
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(buttonIn(A)).toHaveAttribute('aria-pressed', 'false');
    expect(buttonIn(B)).toHaveAttribute('aria-pressed', 'true');
  });

  it('puts the button back when the bump fails before the counts ever loaded', async () => {
    server.use(
      http.get('*/api/bumps', async () => {
        await delay('infinite');
        return HttpResponse.json({});
      }),
      http.post('*/api/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const { user } = renderWithProviders(<Harness />, { queryClient: createTestQueryClient() });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 0 bumps' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(screen.getByRole('button', { name: 'Fist bump, 0 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('refetches the counts when a bump was tapped before they first loaded', async () => {
    let gets = 0;
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/bumps', async () => {
        gets += 1;
        if (gets === 1) await held;
        return HttpResponse.json({
          [A]: { bumps: 6, bumped: true },
          [B]: { bumps: 4, bumped: false },
        });
      }),
      http.post('*/api/bumps', () => HttpResponse.json({ bumps: 6, bumped: true })),
    );
    const { user } = renderWithProviders(<Two />, { queryClient: createTestQueryClient() });
    await user.click(buttonIn(A));
    release();
    await waitFor(() => expect(gets).toBeGreaterThanOrEqual(2));
    expect(
      await within(screen.getByRole('region', { name: B })).findByRole('button', {
        name: 'Fist bump, 4 bumps',
      }),
    ).toBeInTheDocument();
  });

  it('lets the first counts land while a bump is still being sent', async () => {
    let releaseGet: () => void = () => undefined;
    const getHeld = new Promise<void>((resolve) => {
      releaseGet = resolve;
    });
    let releasePost: () => void = () => undefined;
    const postHeld = new Promise<void>((resolve) => {
      releasePost = resolve;
    });
    server.use(
      http.get('*/api/bumps', async () => {
        await getHeld;
        return HttpResponse.json({
          [A]: { bumps: 5, bumped: false },
          [B]: { bumps: 4, bumped: false },
        });
      }),
      http.post('*/api/bumps', async () => {
        await postHeld;
        return HttpResponse.json({ bumps: 6, bumped: true });
      }),
    );
    const { user } = renderWithProviders(<Two />, { queryClient: createTestQueryClient() });
    await user.click(buttonIn(A));
    releaseGet();
    // A's POST is still pending: the load must not have been cancelled, so B has its count.
    expect(
      await within(screen.getByRole('region', { name: B })).findByRole('button', {
        name: 'Fist bump, 4 bumps',
      }),
    ).toBeInTheDocument();
    releasePost();
  });

  it('shows the count but is off when this browser cannot keep a device id', () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(bumpsKey(KEYS, null), { [KEY]: { bumps: 4, bumped: false } });
    renderWithProviders(<Harness deviceId={null} />, { queryClient });
    const button = screen.getByRole('button', { name: 'Fist bump, 4 bumps' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Bumps need this browser to remember you');
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/bumps/BumpButton.test.tsx`
Expected: FAIL: `Failed to resolve import "./BumpButton"`.

- [ ] **Step 12: Write BumpButton** (ported verbatim apart from the props)

Create `frontend/src/features/bumps/BumpButton.tsx`:

```tsx
import { useBumpToggle, type BumpCounts, type BumpState, type BumpsKey } from './api';

const FIST = '🤜🤛';
const BUTTON =
  'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button border px-3 text-sm tabular-nums transition-colors disabled:cursor-not-allowed disabled:opacity-60';

function label(state: BumpState | undefined): string {
  const n = state?.bumps ?? 0;
  return `Fist bump, ${String(n)} ${n === 1 ? 'bump' : 'bumps'}`;
}

function Face({ state }: { state: BumpState | undefined }) {
  return (
    <>
      <span aria-hidden="true">{FIST}</span>
      <span aria-hidden="true">{state?.bumps ?? 0}</span>
    </>
  );
}

export interface BumpButtonProps {
  /** The counts query this button reads and writes (its section's BumpsProvider). */
  queryKey: BumpsKey;
  insightKey: string;
  /** Null when this browser cannot remember a device id: the count shows, the button is off. */
  deviceId: string | null;
  state: BumpState | undefined;
  /** The id of the note that says why bumps are off. */
  noteId: string;
  /** Every count the section has on screen: seeds a tap while a new key set loads. */
  counts?: BumpCounts;
}

/** 🤜🤛 and the count. Nobody is ever shown who bumped; you can bump an insight about yourself. */
export function BumpButton({
  queryKey,
  insightKey,
  deviceId,
  state,
  noteId,
  counts,
}: BumpButtonProps) {
  if (deviceId === null) {
    return (
      <button
        type="button"
        disabled
        aria-label={label(state)}
        aria-describedby={noteId}
        className={`${BUTTON} border-outline-variant`}
      >
        <Face state={state} />
      </button>
    );
  }
  return (
    <LiveBumpButton
      queryKey={queryKey}
      insightKey={insightKey}
      deviceId={deviceId}
      state={state}
      counts={counts}
    />
  );
}

function LiveBumpButton({
  queryKey,
  insightKey,
  deviceId,
  state,
  counts,
}: {
  queryKey: BumpsKey;
  insightKey: string;
  deviceId: string;
  state: BumpState | undefined;
  counts: BumpCounts | undefined;
}) {
  const { send, failed } = useBumpToggle(queryKey, deviceId, insightKey, counts);
  const bumped = state?.bumped ?? false;
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        aria-pressed={bumped}
        aria-label={label(state)}
        onClick={() => send(!bumped)}
        className={`${BUTTON} ${bumped ? 'border-accent bg-primary' : 'border-outline-variant'}`}
      >
        <Face state={state} />
      </button>
      {failed && (
        <span role="alert" className="text-sm text-text-muted">
          Couldn’t send that bump
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 13: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/bumps/BumpButton.test.tsx`
Expected: 9 passed.

- [ ] **Step 14: Write the failing provider tests**

Create `frontend/src/features/bumps/BumpsProvider.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { BumpsProvider, InsightBump } from './BumpsProvider';

function asking() {
  const asked: URLSearchParams[] = [];
  server.use(
    http.get('*/api/bumps', ({ request }) => {
      asked.push(new URL(request.url).searchParams);
      return HttpResponse.json({ a: { bumps: 3, bumped: false }, b: { bumps: 1, bumped: true } });
    }),
  );
  return asked;
}

describe('BumpsProvider', () => {
  it('asks once for every key inside and hands each button its count', async () => {
    const asked = asking();
    renderWithProviders(
      <BumpsProvider keys={['b', 'a', 'b']}>
        <section aria-label="a">
          <InsightBump insightKey="a" />
        </section>
        <section aria-label="b">
          <InsightBump insightKey="b" />
        </section>
      </BumpsProvider>,
    );
    expect(await screen.findByRole('button', { name: 'Fist bump, 3 bumps' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fist bump, 1 bump' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(asked).toHaveLength(1);
    expect(asked[0]?.get('keys')).toBe('a,b');
    expect(asked[0]?.get('device_id')).toBe(localStorage.getItem('sc.device'));
  });

  it('renders no button outside a provider', () => {
    renderWithProviders(<InsightBump insightKey="a" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('turns the buttons off and says why once when storage is blocked', async () => {
    const asked = asking();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    renderWithProviders(
      <BumpsProvider keys={['a', 'b']}>
        <InsightBump insightKey="a" />
        <InsightBump insightKey="b" />
      </BumpsProvider>,
    );
    expect(screen.getAllByText('Bumps need this browser to remember you')).toHaveLength(1);
    const button = await screen.findByRole('button', { name: 'Fist bump, 3 bumps' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Bumps need this browser to remember you');
    await waitFor(() => expect(asked).toHaveLength(1));
    expect(asked[0]?.has('device_id')).toBe(false);
  });
});
```

- [ ] **Step 15: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/bumps/BumpsProvider.test.tsx`
Expected: FAIL: `Failed to resolve import "./BumpsProvider"`.

- [ ] **Step 16: Write the provider**

Create `frontend/src/features/bumps/BumpsProvider.tsx`:

```tsx
import { createContext, useContext, useId, useState, type ReactNode } from 'react';
import { getDeviceId } from '../../lib/device';
import { BUMPS_OFF, bumpsKey, sortedKeys, useBumps, type BumpCounts, type BumpsKey } from './api';
import { BumpButton } from './BumpButton';

interface BumpsContextValue {
  queryKey: BumpsKey;
  deviceId: string | null;
  counts: BumpCounts | undefined;
  noteId: string;
}

const BumpsContext = createContext<BumpsContextValue | null>(null);

/**
 * Fetches the bump counts for every insight a page section shows, in one request, and hands them
 * to each `InsightBump` inside. When this browser cannot keep a device id, it says once why the
 * buttons are off.
 */
export function BumpsProvider({ keys, children }: { keys: Iterable<string>; children: ReactNode }) {
  const [deviceId] = useState(getDeviceId);
  const noteId = useId();
  const sorted = sortedKeys(keys);
  const bumps = useBumps(sorted, deviceId);
  const value = { queryKey: bumpsKey(sorted, deviceId), deviceId, counts: bumps.data, noteId };
  return (
    <BumpsContext value={value}>
      {deviceId === null && (
        <p id={noteId} className="text-sm text-text-muted">
          {BUMPS_OFF}
        </p>
      )}
      {children}
    </BumpsContext>
  );
}

/** 🤜🤛 for one insight; nothing outside a BumpsProvider, so a lone card never fetches. */
export function InsightBump({ insightKey }: { insightKey: string }) {
  const bumps = useContext(BumpsContext);
  if (bumps === null) return null;
  return (
    <BumpButton
      queryKey={bumps.queryKey}
      insightKey={insightKey}
      deviceId={bumps.deviceId}
      state={bumps.counts?.[insightKey]}
      noteId={bumps.noteId}
      counts={bumps.counts}
    />
  );
}
```

- [ ] **Step 17: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/bumps/`
Expected: all bumps tests pass (8 + 9 + 3).

- [ ] **Step 18: Write the failing `feedKeys` test**

Create `frontend/src/features/insights/feedKeys.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { feedKeys } from './feedKeys';
import { feedFixture, insightFixture, kudosFixture } from './mocks';

describe('feedKeys', () => {
  it('lists every insight a feed can show: lead cards, lists, kudos and More', () => {
    const feed = feedFixture({
      pinned: insightFixture({ key: 'pinned' }),
      hero: insightFixture({ key: 'hero' }),
      spotlight: insightFixture({ key: 'spot' }),
      conditions: insightFixture({ key: 'cond' }),
      top: [insightFixture({ key: 't1' })],
      kudos: kudosFixture(1),
      more: [insightFixture({ key: 'm1' })],
    });
    expect(feedKeys(feed)).toEqual(['pinned', 'hero', 'spot', 'cond', 't1', 'k-0', 'm1']);
  });

  it('is empty for an empty feed', () => {
    expect(feedKeys(feedFixture())).toEqual([]);
  });
});
```

- [ ] **Step 19: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/insights/feedKeys.test.ts`
Expected: FAIL: `Failed to resolve import "./feedKeys"`.

- [ ] **Step 20: Write `feedKeys`**

Create `frontend/src/features/insights/feedKeys.ts`:

```ts
import type { InsightFeed } from './api';

/** Every insight key a feed can put on screen, in feed order (BumpsProvider dedupes and sorts). */
export function feedKeys(feed: InsightFeed): string[] {
  const rows = [
    feed.pinned,
    feed.hero,
    feed.spotlight,
    feed.conditions,
    ...feed.top,
    ...feed.kudos.map((chip) => chip.insight),
    ...feed.more,
  ];
  return rows.flatMap((row) => (row == null ? [] : [row.key]));
}
```

- [ ] **Step 21: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/insights/feedKeys.test.ts`
Expected: 2 passed.

- [ ] **Step 22: Write the failing InsightCard and KudosStrip tests**

In `frontend/src/features/insights/components/InsightCard.test.tsx`, add `import { BumpsProvider } from '../../bumps/BumpsProvider';` to the imports, and append this `describe` block at the end of the file. It uses `renderWithProviders`, `screen` and `insightFixture`, which the file already imports. If any of them is missing, add it from `../../../test/render`, `@testing-library/react` or `../mocks`.

```tsx
describe('InsightCard bumps', () => {
  it('carries its key and a fist bump inside a BumpsProvider', async () => {
    const { container } = renderWithProviders(
      <BumpsProvider keys={['k-pb-3']}>
        <ul>
          <InsightCard insight={insightFixture()} />
        </ul>
      </BumpsProvider>,
    );
    expect(container.querySelector('li')).toHaveAttribute('data-insight-key', 'k-pb-3');
    expect(await screen.findByRole('button', { name: 'Fist bump, 0 bumps' })).toBeInTheDocument();
  });

  it('has no fist bump on its own', () => {
    renderWithProviders(
      <ul>
        <InsightCard insight={insightFixture()} />
      </ul>,
    );
    expect(screen.queryByRole('button', { name: /^Fist bump/ })).toBeNull();
  });
});
```

In `frontend/src/features/insights/components/KudosStrip.test.tsx`, add `import { BumpsProvider } from '../../bumps/BumpsProvider';` to the imports, and append this test inside the top-level `describe`. It reuses the file's existing `kudosFixture` import and the `user` from `renderWithProviders`.

```tsx
  it('puts a fist bump on every row of the full list and on an opened chip', async () => {
    const kudos = kudosFixture(12);
    const { user } = renderWithProviders(
      <BumpsProvider keys={kudos.map((chip) => chip.insight.key)}>
        <KudosStrip kudos={kudos} meId={null} />
      </BumpsProvider>,
    );
    await user.click(screen.getByRole('button', { name: 'and 2 more' }));
    const sheet = await screen.findByRole('dialog');
    expect(within(sheet).getAllByRole('button', { name: /^Fist bump/ })).toHaveLength(12);
    expect(sheet.querySelector('[data-insight-key="k-11"]')).not.toBeNull();
  });
```

- [ ] **Step 23: Run them to verify they fail**

Run: `cd frontend && pnpm exec vitest run src/features/insights/components/InsightCard.test.tsx src/features/insights/components/KudosStrip.test.tsx`
Expected: FAIL. The new InsightCard test finds no `data-insight-key` and no "Fist bump" button. The kudos test finds 0 fist bumps in the dialog. (If the KudosStrip `Sheet` is not exposed as `role="dialog"`, query it the way the file's existing "and N more" test does, and keep the two assertions.)

- [ ] **Step 24: Put the button on the shared rows**

In `frontend/src/features/insights/components/InsightCard.tsx`, add `import { InsightBump } from '../../bumps/BumpsProvider';` after the `ExplainerToggle` import. Then replace

```tsx
    <li
      className={`flex min-w-0 flex-col gap-2 border-t border-outline-variant pt-3 first:border-t-0 first:pt-0 ${className}`.trim()}
    >
```

with

```tsx
    <li
      data-insight-key={insight.key}
      className={`flex min-w-0 flex-col gap-2 border-t border-outline-variant pt-3 first:border-t-0 first:pt-0 ${className}`.trim()}
    >
```

and replace

```tsx
        <ExplainerToggle
          label="How we worked it out"
          panelId={panelId}
          open={open}
          onToggle={() => setOpen((v) => !v)}
        />
      </div>
```

with

```tsx
        <ExplainerToggle
          label="How we worked it out"
          panelId={panelId}
          open={open}
          onToggle={() => setOpen((v) => !v)}
        />
        <InsightBump insightKey={insight.key} />
      </div>
```

In `frontend/src/features/insights/components/RecapCard.tsx`, add `import { InsightBump } from '../../bumps/BumpsProvider';` after the `Card` import. Then replace

```tsx
      <div className="flex flex-wrap items-center gap-2">
```

with

```tsx
      <div data-insight-key={insight.key} className="flex flex-wrap items-center gap-2">
```

and replace

```tsx
          See the results
        </Link>
      </div>
```

with

```tsx
          See the results
        </Link>
        <InsightBump insightKey={insight.key} />
      </div>
```

In `frontend/src/features/insights/components/KudosStrip.tsx`, add `import { InsightBump } from '../../bumps/BumpsProvider';` after the `Sheet` import. Then replace

```tsx
              <li key={chip.shooter_id} className="flex flex-col gap-1">
```

with

```tsx
              <li
                key={chip.shooter_id}
                data-insight-key={chip.insight.key}
                className="flex flex-col gap-1"
              >
```

and replace

```tsx
                    segments={you ? (chip.insight.headline_you ?? []) : chip.insight.headline}
                  />
                </p>
              </li>
```

with

```tsx
                    segments={you ? (chip.insight.headline_you ?? []) : chip.insight.headline}
                  />
                </p>
                <InsightBump insightKey={chip.insight.key} />
              </li>
```

- [ ] **Step 25: Run them to verify they pass**

Run: `cd frontend && pnpm exec vitest run src/features/insights/components/InsightCard.test.tsx src/features/insights/components/KudosStrip.test.tsx`
Expected: all pass, the existing tests included.

- [ ] **Step 26: Write the failing feed-section tests**

In `frontend/src/features/insights/components/FeedSections.test.tsx`, add `vi` to the `vitest` import and `import { feedKeys } from '../feedKeys';` to the imports. Then append:

```tsx
/** Records every GET /api/bumps and answers `counts` (zeros for any other asked key). */
function bumpCounts(counts: Record<string, { bumps: number; bumped: boolean }> = {}) {
  const asked: URLSearchParams[] = [];
  server.use(
    http.get('*/api/bumps', ({ request }) => {
      const params = new URL(request.url).searchParams;
      asked.push(params);
      const keys = (params.get('keys') ?? '').split(',').filter(Boolean);
      return HttpResponse.json(
        Object.fromEntries(keys.map((k) => [k, counts[k] ?? { bumps: 0, bumped: false }])),
      );
    }),
  );
  return asked;
}

const homeBumpFeed = feedFixture({
  pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap', family: 'recap' }),
  hero: insightFixture({ key: 'hero' }),
  spotlight: insightFixture({ key: 'spot' }),
  top: [insightFixture({ key: 't1' }), insightFixture({ key: 't2' })],
  kudos: kudosFixture(2),
  more: [insightFixture({ key: 'm1', family: 'streak' })],
  n_more: 1,
});

describe('fist bumps on every feed', () => {
  it('Home asks for every insight’s bumps in one request and puts a button on each row', async () => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(homeBumpFeed)));
    const asked = bumpCounts({ hero: { bumps: 4, bumped: false } });
    const { container } = renderWithProviders(<HomeInsights meId={null} />);
    const topStory = await screen.findByRole('list', { name: 'Top story' });
    expect(
      await within(topStory).findByRole('button', { name: 'Fist bump, 4 bumps' }),
    ).toBeInTheDocument();
    expect(asked).toHaveLength(1);
    expect(asked[0]?.get('keys')).toBe([...new Set(feedKeys(homeBumpFeed))].sort().join(','));
    for (const key of ['recap', 'spot', 't1', 't2', 'm1']) {
      const row = container.querySelector(`[data-insight-key="${key}"]`);
      expect(row, key).not.toBeNull();
      expect(
        within(row as HTMLElement).getByRole('button', { name: /^Fist bump/ }),
      ).toBeInTheDocument();
    }
  });

  it.each([
    ['a profile', () => <ProfileInsights shooterId={3} />, '*/api/insights/shooters/:id'],
    ['a Sunday', () => <SundayInsights date="2026-09-27" />, '*/api/insights/sundays/:date'],
    ['the club page', () => <PageInsights page="club" />, '*/api/insights/club'],
  ])('%s puts a fist bump on its insights', async (_name, ui, route) => {
    server.use(
      http.get(route, () => HttpResponse.json(feedFixture({ top: [insightFixture()] }))),
    );
    const asked = bumpCounts({ 'k-pb-3': { bumps: 2, bumped: true } });
    renderWithProviders(ui());
    const button = await screen.findByRole('button', { name: 'Fist bump, 2 bumps' });
    expect(button).toHaveAttribute('aria-pressed', 'true');
    expect(asked).toHaveLength(1);
  });

  it('one insight shown twice shares one count', async () => {
    const shared = insightFixture();
    server.use(
      http.get('*/api/insights/sundays/:date', () =>
        HttpResponse.json(
          feedFixture({
            top: [shared],
            kudos: [{ shooter_id: 3, display_name: 'Hadley, Ike', insight: shared }],
          }),
        ),
      ),
      http.post('*/api/bumps', () => HttpResponse.json({ bumps: 1, bumped: true })),
    );
    bumpCounts();
    const { user } = renderWithProviders(<SundayInsights date="2026-09-27" />);
    const top = await screen.findByRole('list', { name: 'Top insights' });
    await within(top).findByRole('button', { name: 'Fist bump, 0 bumps' });
    await user.click(screen.getByRole('button', { name: /Ike Hadley · / }));
    const sheet = await screen.findByRole('dialog');
    await user.click(within(sheet).getByRole('button', { name: 'Fist bump, 0 bumps' }));
    // The open Sheet makes the page behind it inert, so the list is queried with hidden: true.
    expect(
      await within(top).findByRole('button', { name: 'Fist bump, 1 bump', hidden: true }),
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps the counts on screen while Show all loads more', async () => {
    let releaseSecond: () => void = () => undefined;
    const secondHeld = new Promise<void>((resolve) => {
      releaseSecond = resolve;
    });
    let gets = 0;
    server.use(
      http.get('*/api/insights/shooters/:id', ({ request }) => {
        const all = new URL(request.url).searchParams.has('all');
        const more = [insightFixture({ key: 'm1', family: 'streak' })];
        if (all) more.push(insightFixture({ key: 'm2', family: 'streak' }));
        return HttpResponse.json(feedFixture({ top: [insightFixture()], more, n_more: 2 }));
      }),
      http.get('*/api/bumps', async ({ request }) => {
        gets += 1;
        if (gets === 2) await secondHeld;
        const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',');
        return HttpResponse.json(
          Object.fromEntries(keys.map((k) => [k, { bumps: k === 'k-pb-3' ? 5 : 0, bumped: false }])),
        );
      }),
    );
    const { user } = renderWithProviders(<ProfileInsights shooterId={3} />);
    const top = await screen.findByRole('list', { name: 'Top insights' });
    await within(top).findByRole('button', { name: 'Fist bump, 5 bumps' });
    await user.click(screen.getByRole('button', { name: 'Show all 2' }));
    await waitFor(() => expect(gets).toBe(2));
    // The second ask is held: the card on screen keeps its 5, not a flash to 0.
    expect(within(top).getByRole('button', { name: 'Fist bump, 5 bumps' })).toBeInTheDocument();
    releaseSecond();
  });

  it('a tap while Show all loads keeps the other cards’ counts', async () => {
    let releaseSecond: () => void = () => undefined;
    const secondHeld = new Promise<void>((resolve) => {
      releaseSecond = resolve;
    });
    let gets = 0;
    const counts: Record<string, { bumps: number; bumped: boolean }> = {
      'k-pb-3': { bumps: 5, bumped: false },
      t2: { bumps: 2, bumped: false },
    };
    server.use(
      http.get('*/api/insights/shooters/:id', ({ request }) => {
        const all = new URL(request.url).searchParams.has('all');
        const more = [insightFixture({ key: 'm1', family: 'streak' })];
        if (all) more.push(insightFixture({ key: 'm2', family: 'streak' }));
        return HttpResponse.json(
          feedFixture({ top: [insightFixture(), insightFixture({ key: 't2' })], more, n_more: 2 }),
        );
      }),
      http.get('*/api/bumps', async ({ request }) => {
        gets += 1;
        if (gets === 2) await secondHeld;
        const keys = (new URL(request.url).searchParams.get('keys') ?? '').split(',');
        return HttpResponse.json(
          Object.fromEntries(keys.map((k) => [k, counts[k] ?? { bumps: 0, bumped: false }])),
        );
      }),
      http.post('*/api/bumps', () => {
        counts.t2 = { bumps: 3, bumped: true };
        return HttpResponse.json(counts.t2);
      }),
    );
    const { user, container } = renderWithProviders(<ProfileInsights shooterId={3} />);
    const top = await screen.findByRole('list', { name: 'Top insights' });
    await within(top).findByRole('button', { name: 'Fist bump, 5 bumps' });
    const t2 = () => container.querySelector('[data-insight-key="t2"]') as HTMLElement;
    await within(t2()).findByRole('button', { name: 'Fist bump, 2 bumps' });
    await user.click(screen.getByRole('button', { name: 'Show all 2' }));
    await waitFor(() => expect(gets).toBe(2));
    // The new counts are still held. Tap a card already on screen.
    await user.click(within(t2()).getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(
      await within(t2()).findByRole('button', { name: 'Fist bump, 3 bumps' }),
    ).toHaveAttribute('aria-pressed', 'true');
    // The other card keeps its 5: the tap is seeded from the counts on screen, not an empty map.
    expect(within(top).getByRole('button', { name: 'Fist bump, 5 bumps' })).toBeInTheDocument();
    releaseSecond();
    await waitFor(() =>
      expect(within(t2()).getByRole('button', { name: 'Fist bump, 3 bumps' })).toBeInTheDocument(),
    );
    expect(within(top).getByRole('button', { name: 'Fist bump, 5 bumps' })).toBeInTheDocument();
  });

  it('turns bumps off, says why once, and still shows counts when storage is blocked', async () => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(homeBumpFeed)));
    const asked = bumpCounts({ hero: { bumps: 4, bumped: false } });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });
    renderWithProviders(<HomeInsights meId={null} />);
    const button = await screen.findByRole('button', { name: 'Fist bump, 4 bumps' });
    expect(button).toBeDisabled();
    expect(screen.getAllByText('Bumps need this browser to remember you')).toHaveLength(1);
    expect(asked[0]?.has('device_id')).toBe(false);
  });
});
```

- [ ] **Step 27: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/insights/components/FeedSections.test.tsx`
Expected: FAIL. The new tests find no "Fist bump" buttons (no section renders a provider yet), and `asked` is empty. The existing tests still pass.

- [ ] **Step 28: Wrap every feed section in a provider**

In `frontend/src/features/insights/components/FeedSections.tsx`, add these two imports after the `../api` import:

```tsx
import { BumpsProvider } from '../../bumps/BumpsProvider';
import { feedKeys } from '../feedKeys';
```

In `ProfileInsights`, replace

```tsx
      <div className="flex min-w-0 flex-col gap-3">
        <InsightList
          items={first}
          you={you}
          label="Top insights"
          columns={3}
          wideFirst={f.pinned != null}
        />
        <MoreInsights
          items={f.more}
          total={f.n_more}
          you={you}
          onShowAll={() => setAll(true)}
          loadingAll={all && feed.isPlaceholderData}
        />
      </div>
```

with

```tsx
      <BumpsProvider keys={feedKeys(f)}>
        <div className="flex min-w-0 flex-col gap-3">
          <InsightList
            items={first}
            you={you}
            label="Top insights"
            columns={3}
            wideFirst={f.pinned != null}
          />
          <MoreInsights
            items={f.more}
            total={f.n_more}
            you={you}
            onShowAll={() => setAll(true)}
            loadingAll={all && feed.isPlaceholderData}
          />
        </div>
      </BumpsProvider>
```

In `SundayInsights`, replace

```tsx
      <div className="flex min-w-0 flex-col gap-3">
        <InsightList items={first} meId={meId} label="Top insights" columns={4} />
        <KudosStrip kudos={f.kudos} meId={meId} />
        <MoreInsights items={f.more} total={f.n_more} meId={meId} />
      </div>
```

with

```tsx
      <BumpsProvider keys={feedKeys(f)}>
        <div className="flex min-w-0 flex-col gap-3">
          <InsightList items={first} meId={meId} label="Top insights" columns={4} />
          <KudosStrip kudos={f.kudos} meId={meId} />
          <MoreInsights items={f.more} total={f.n_more} meId={meId} />
        </div>
      </BumpsProvider>
```

In `HomeInsights`, replace

```tsx
  const f = feed.data;
  return (
    <>
      {(f.pinned != null || f.hero != null) && (
```

with

```tsx
  const f = feed.data;
  return (
    <BumpsProvider keys={feedKeys(f)}>
      {(f.pinned != null || f.hero != null) && (
```

and replace the end of `HomeInsights`

```tsx
            <InsightList items={f.top} meId={meId} label="Around the club" columns={2} />
            <MoreInsights items={f.more} total={f.n_more} meId={meId} />
          </div>
        </Card>
      )}
    </>
  );
}
```

with

```tsx
            <InsightList items={f.top} meId={meId} label="Around the club" columns={2} />
            <MoreInsights items={f.more} total={f.n_more} meId={meId} />
          </div>
        </Card>
      )}
    </BumpsProvider>
  );
}
```

In `PageInsights`, replace

```tsx
      <div className="flex min-w-0 flex-col gap-3">
        <InsightList items={f.top} meId={getMe()} label="Top insights" columns={3} />
        <MoreInsights items={f.more} total={f.n_more} meId={getMe()} />
      </div>
```

with

```tsx
      <BumpsProvider keys={feedKeys(f)}>
        <div className="flex min-w-0 flex-col gap-3">
          <InsightList items={f.top} meId={getMe()} label="Top insights" columns={3} />
          <MoreInsights items={f.more} total={f.n_more} meId={getMe()} />
        </div>
      </BumpsProvider>
```

- [ ] **Step 29: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/insights/`
Expected: all pass. That covers the 7 new feed-section tests and every existing insights test, including the `.lg\:grid-cols-2` child count. In jsdom localStorage works, so no note is rendered.

Then prove the "a tap while Show all loads keeps the other cards’ counts" test is not vacuous: in `features/bumps/api.ts`, change `const counts = cached ?? shown;` to `const counts = cached;` locally and re-run `FeedSections.test.tsx`. That test must fail on `Fist bump, 5 bumps` (the top card drops to 0). Paste that RED, restore `?? shown`, and re-run to GREEN.

- [ ] **Step 30: Gates and the full frontend suite with coverage**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage`
Expected: all pass, and coverage is at or above 90% lines and 90% branches. If prettier reports files, run `pnpm exec prettier --write <those files>` and re-check.

- [ ] **Step 31: Check the existing e2e on a stack from this branch**

Build the stack as in "Running the e2e stack", then run:
`E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/insights.spec.ts e2e/home.spec.ts e2e/events.spec.ts e2e/shooters.spec.ts e2e/club.spec.ts`
Expected: all pass at both projects. The new buttons are `min-h-11 min-w-11`, so the tap-target checks still hold. If one fails because it counts buttons inside an insight card, narrow that assertion by name, and say so in the report.

- [ ] **Step 32: Commit**

```bash
git add frontend/src/lib/device.ts frontend/src/lib/device.test.ts frontend/src/features/bumps/api.ts frontend/src/features/bumps/api.test.tsx frontend/src/features/bumps/mocks.ts frontend/src/features/bumps/BumpButton.tsx frontend/src/features/bumps/BumpButton.test.tsx frontend/src/features/bumps/BumpsProvider.tsx frontend/src/features/bumps/BumpsProvider.test.tsx frontend/src/features/insights/feedKeys.ts frontend/src/features/insights/feedKeys.test.ts frontend/src/features/insights/components/InsightCard.tsx frontend/src/features/insights/components/InsightCard.test.tsx frontend/src/features/insights/components/RecapCard.tsx frontend/src/features/insights/components/KudosStrip.tsx frontend/src/features/insights/components/KudosStrip.test.tsx frontend/src/features/insights/components/FeedSections.tsx frontend/src/features/insights/components/FeedSections.test.tsx
git commit -m "feat(bumps): fist bumps on every insight row, one ask per page (Plan 15 T2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: "Which one are you?" on Home, and "Not me"

**Files:**
- Modify: `frontend/src/lib/me.ts`, `frontend/src/lib/me.test.ts` (port verbatim)
- Modify: `frontend/src/features/shooters/api.ts` (port verbatim)
- Create: `frontend/src/features/home/components/WhichOneAreYou.tsx` (port verbatim), `WhichOneAreYou.test.tsx` (port, with a non-vacuous single-letter test)
- Modify: `frontend/src/features/home/components/MePanel.tsx`, `MePanel.test.tsx`
- Modify: `frontend/src/features/home/pages/HomePage.tsx`, `HomePage.test.tsx`
- Modify: `frontend/src/features/predictions/components/NextSundayCard.tsx`, `NextSundayCard.test.tsx` (Decision 17)
- Modify: `frontend/e2e/home.spec.ts`, `frontend/e2e/predictions.spec.ts`

**Interfaces:**
- Consumes: `getMe`, `setMe` and `clearMe` from `lib/me.ts`; `useShooters(q, active)` from `features/shooters/api.ts`; `shooterList` (has `Hadley, Ike`, id 3) from `features/shooters/mocks.ts`; `homeMeta`, `latestEvent`, `seasonEvents`, `meDetail` and `meRounds` from `features/home/mocks.ts`; `Card` (`actions`) and `Button` (`variant: 'tonal' | 'ghost'`).
- Produces (Task 4 relies on these): `isMeSkipped(): boolean`, `skipMe(): void` (`localStorage['sc.me.skip'] = '1'`; `setMe` clears it, `clearMe` does not); `useShooters(q, active, opts?: { enabled?: boolean })`; `WhichOneAreYou({onPicked(id: number), onSkipped()})`, which is a Card titled "Which one are you?" with the input "Your name", the list "Matching shooters", a `role="status"` live region and the button "Not a shooter / skip"; `MePanel`'s "Not me" button; in Home's `aside[aria-label="Personal"]`, focus goes to the new card's `h2` after a swap.

- [ ] **Step 1: Write the failing `me` tests** (ported verbatim)

In `frontend/src/lib/me.test.ts`, replace

```ts
import { clearMe, getMe, setMe } from './me';
```

with

```ts
import { clearMe, getMe, isMeSkipped, setMe, skipMe } from './me';
```

and replace

```ts
    expect(() => setMe(1)).not.toThrow();
    expect(() => clearMe()).not.toThrow();
  });
```

with

```ts
    expect(() => setMe(1)).not.toThrow();
    expect(() => clearMe()).not.toThrow();
    expect(isMeSkipped()).toBe(false);
    expect(() => skipMe()).not.toThrow();
  });

  it('remembers a skip until someone is picked; "Not me" does not skip', () => {
    expect(isMeSkipped()).toBe(false);
    skipMe();
    expect(isMeSkipped()).toBe(true);
    setMe(42);
    expect(isMeSkipped()).toBe(false);
    clearMe();
    expect(isMeSkipped()).toBe(false);
    expect(getMe()).toBeNull();
  });
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/me.test.ts`
Expected: FAIL: `isMeSkipped` / `skipMe` are not exported (`TypeError: … is not a function`).

- [ ] **Step 3: Add skip to `lib/me.ts`** (ported verbatim)

In `frontend/src/lib/me.ts`, replace

```ts
const KEY = 'sc.me';
```

with

```ts
const KEY = 'sc.me';
/** "Not a shooter / skip" on Home (Plan 15): stop asking "Which one are you?". */
const SKIP_KEY = 'sc.me.skip';
```

and replace

```ts
export function setMe(id: number): void {
  try {
    localStorage.setItem(KEY, String(id));
```

with

```ts
/** Remembers the viewer's shooter; picking someone also undoes an earlier skip. */
export function setMe(id: number): void {
  try {
    localStorage.setItem(KEY, String(id));
    localStorage.removeItem(SKIP_KEY);
```

Then append to the end of the file:

```ts

/** True once this browser said "Not a shooter / skip". */
export function isMeSkipped(): boolean {
  try {
    return localStorage.getItem(SKIP_KEY) === '1';
  } catch {
    return false;
  }
}

export function skipMe(): void {
  try {
    localStorage.setItem(SKIP_KEY, '1');
  } catch {
    // Storage unavailable: the question comes back next visit.
  }
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/lib/me.test.ts`
Expected: all pass.

- [ ] **Step 5: Write the failing WhichOneAreYou tests**

These are ported from the Sheet's reviewed test, with the final-review fixes (the live region and the 8-result cap). The single-letter test is made non-vacuous: it types a second letter and proves that only the two-letter query was ever sent. Create `frontend/src/features/home/components/WhichOneAreYou.test.tsx`:

```tsx
import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getMe, isMeSkipped } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { shooterList } from '../../shooters/mocks';
import { WhichOneAreYou } from './WhichOneAreYou';

afterEach(() => {
  localStorage.clear();
});

function searched() {
  const asked: (string | null)[] = [];
  server.use(
    http.get('*/api/shooters', ({ request }) => {
      const q = new URL(request.url).searchParams.get('q');
      asked.push(q);
      const hits = shooterList.filter((s) =>
        s.display_name.toLowerCase().includes((q ?? '').toLowerCase()),
      );
      return HttpResponse.json(hits);
    }),
  );
  return asked;
}

describe('WhichOneAreYou', () => {
  it('searches by name and remembers the pick', async () => {
    const asked = searched();
    const onPicked = vi.fn();
    const { user } = renderWithProviders(
      <WhichOneAreYou onPicked={onPicked} onSkipped={vi.fn()} />,
    );
    await user.type(screen.getByLabelText('Your name'), 'Hadley');
    const list = await screen.findByRole('list', { name: 'Matching shooters' });
    await user.click(within(list).getByRole('button', { name: 'Hadley, Ike' }));
    expect(getMe()).toBe(3);
    expect(onPicked).toHaveBeenCalledWith(3);
    expect(asked.at(-1)).toBe('Hadley');
  });

  it('does not search for a single letter', async () => {
    const asked = searched();
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'H');
    expect(screen.queryByRole('list', { name: 'Matching shooters' })).toBeNull();
    await user.type(screen.getByLabelText('Your name'), 'a');
    // The two-letter search does go out, and it is the only one: "H" was never asked.
    await waitFor(() => expect(asked).toEqual(['Ha']));
  });

  it('says when no shooter matches', async () => {
    searched();
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'Zz');
    expect(await screen.findByText('No shooter matches “Zz”.')).toBeInTheDocument();
  });

  it('lists at most eight matches and says how many it found, in a live region', async () => {
    const many = Array.from({ length: 10 }, (_, i) => ({
      ...(shooterList[0] as (typeof shooterList)[number]),
      shooter_id: 200 + i,
      display_name: `Ann Anders${String(i + 1)}`,
    }));
    server.use(http.get('*/api/shooters', () => HttpResponse.json(many)));
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'An');
    const list = await screen.findByRole('list', { name: 'Matching shooters' });
    expect(within(list).getAllByRole('button')).toHaveLength(8);
    expect(screen.getByRole('status')).toHaveTextContent('Showing 8 of 10 matches');
  });

  it('announces the feedback in a live region that is there before the search', async () => {
    searched();
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    const live = screen.getByRole('status');
    expect(live).toBeEmptyDOMElement();
    await user.type(screen.getByLabelText('Your name'), 'Zz');
    expect(await within(live).findByText('No shooter matches “Zz”.')).toBeInTheDocument();
  });

  it('announces a failed search in the live region', async () => {
    server.use(
      http.get('*/api/shooters', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'Hadley');
    expect(
      await within(screen.getByRole('status')).findByText('Couldn’t search the shooters just now.'),
    ).toBeInTheDocument();
  });

  it('skips for good on this browser', async () => {
    const onSkipped = vi.fn();
    const { user } = renderWithProviders(
      <WhichOneAreYou onPicked={vi.fn()} onSkipped={onSkipped} />,
    );
    await user.click(screen.getByRole('button', { name: 'Not a shooter / skip' }));
    expect(isMeSkipped()).toBe(true);
    expect(onSkipped).toHaveBeenCalledTimes(1);
    expect(getMe()).toBeNull();
  });
});
```

- [ ] **Step 6: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/WhichOneAreYou.test.tsx`
Expected: FAIL: `Failed to resolve import "./WhichOneAreYou"`.

- [ ] **Step 7: Add the `enabled` option and port the component**

In `frontend/src/features/shooters/api.ts`, replace

```ts
export function useShooters(q: string, active: boolean) {
  return useQuery({
    queryKey: ['/api/shooters', { q, active }],
```

with

```ts
export function useShooters(q: string, active: boolean, opts?: { enabled?: boolean }) {
  return useQuery({
    ...opts,
    queryKey: ['/api/shooters', { q, active }],
```

Create `frontend/src/features/home/components/WhichOneAreYou.tsx` (ported verbatim, with the docstring's plan reference updated):

```tsx
import { useId, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { setMe, skipMe } from '../../../lib/me';
import { useShooters } from '../../shooters/api';

const MIN_QUERY = 2;
const SHOWN = 8;

/**
 * "Which one are you?" (Plan 15): pick yourself once and this browser remembers it (lib/me), or
 * skip. No modal, no tour; nothing is sent anywhere but the name search.
 */
export function WhichOneAreYou({
  onPicked,
  onSkipped,
}: {
  onPicked: (id: number) => void;
  onSkipped: () => void;
}) {
  const inputId = useId();
  const [q, setQ] = useState('');
  const query = q.trim();
  const asked = query.length >= MIN_QUERY;
  const search = useShooters(query, false, { enabled: asked });
  const found = asked ? (search.data ?? []) : [];
  const matches = found.slice(0, SHOWN);
  return (
    <Card title="Which one are you?" subtitle="Pick your name once; this browser remembers it.">
      <div className="flex flex-col gap-3">
        <label htmlFor={inputId} className="text-sm text-text-muted">
          Your name
        </label>
        <input
          id={inputId}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoComplete="off"
          className="min-h-11 rounded-button border border-outline-variant bg-surface px-3 text-text"
        />
        <div role="status" className="empty:hidden">
          {asked && search.isError && (
            <p className="text-sm text-text-muted">Couldn’t search the shooters just now.</p>
          )}
          {asked && search.isSuccess && matches.length === 0 && (
            <p className="text-sm text-text-muted">{`No shooter matches “${query}”.`}</p>
          )}
          {matches.length > 0 && (
            <p className="text-sm text-text-muted">
              {found.length > matches.length
                ? `Showing ${String(matches.length)} of ${String(found.length)} matches`
                : `${String(matches.length)} ${matches.length === 1 ? 'match' : 'matches'}`}
            </p>
          )}
        </div>
        {matches.length > 0 && (
          <ul aria-label="Matching shooters" className="flex flex-col gap-2">
            {matches.map((s) => (
              <li key={s.shooter_id}>
                <Button
                  variant="tonal"
                  className="w-full justify-start"
                  onClick={() => {
                    setMe(s.shooter_id);
                    onPicked(s.shooter_id);
                  }}
                >
                  {s.display_name}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <Button
          variant="ghost"
          className="self-start"
          onClick={() => {
            skipMe();
            onSkipped();
          }}
        >
          Not a shooter / skip
        </Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 8: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/WhichOneAreYou.test.tsx src/features/shooters/`
Expected: 7 passed, and the shooters tests still pass.

- [ ] **Step 9: Write the failing "Not me" test**

In `frontend/src/features/home/components/MePanel.test.tsx`, append this inside `describe('MePanel', …)`:

```tsx
  it('offers "Not me" once a shooter is chosen, which forgets the choice', async () => {
    server.use(
      http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
    );
    setMe(3);
    const onCleared = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<MePanel meId={3} onCleared={onCleared} widgets={[]} />);
    await user.click(await screen.findByRole('button', { name: 'Not me' }));
    expect(getMe()).toBeNull();
    expect(onCleared).toHaveBeenCalledTimes(1);
  });

  it('has no "Not me" before anyone is chosen', () => {
    renderWithProviders(<MePanel meId={null} onCleared={vi.fn()} widgets={[]} />);
    expect(screen.queryByRole('button', { name: 'Not me' })).toBeNull();
  });
```

- [ ] **Step 10: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/MePanel.test.tsx`
Expected: FAIL: there is no button "Not me". The second new test and all existing tests pass.

- [ ] **Step 11: Add "Not me"**

In `frontend/src/features/home/components/MePanel.tsx`, replace

```tsx
  const shootersLink = useRoundTypeLink('/shooters');
  return (
    <Card title="Your panel">
```

with

```tsx
  const shootersLink = useRoundTypeLink('/shooters');
  const notMe =
    meId === null ? undefined : (
      <Button
        variant="ghost"
        onClick={() => {
          clearMe();
          onCleared();
        }}
      >
        Not me
      </Button>
    );
  return (
    <Card title="Your panel" actions={notMe}>
```

- [ ] **Step 12: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/MePanel.test.tsx`
Expected: all pass.

- [ ] **Step 13: Write the failing Home tests**

In `frontend/src/features/home/pages/HomePage.test.tsx`, change the `me` import to `import { clearMe, getMe, isMeSkipped, setMe, skipMe } from '../../../lib/me';`, and add `import { shooterList } from '../../shooters/mocks';`.

In the `beforeEach`, add this handler to the `server.use(...)` list, after the `*/api/shooters/:id/rounds` handler:

```tsx
      http.get('*/api/shooters', ({ request }) => {
        const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
        return HttpResponse.json(
          shooterList.filter((s) => s.display_name.toLowerCase().includes(q)),
        );
      }),
```

and add `localStorage.removeItem('sc.me.skip');` directly after `clearMe();`.

Replace

```tsx
  it('shows the latest event, the club pulse, main widgets and the me prompt', async () => {
    renderWithProviders(<HomePage widgets={widgets} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeInTheDocument();
    expect(
      await screen.findByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49'),
    ).toBeInTheDocument();
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    expect(within(panel).getByText(/tap “That’s me”/)).toBeInTheDocument();
    await chartLoaded();
  });
```

with

```tsx
  it('shows the latest event, the club pulse, main widgets and asks which one you are', async () => {
    renderWithProviders(<HomePage widgets={widgets} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeInTheDocument();
    expect(
      await screen.findByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49'),
    ).toBeInTheDocument();
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    expect(
      within(panel).getByRole('heading', { name: 'Which one are you?' }),
    ).toBeInTheDocument();
    expect(within(panel).queryByText(/tap “That’s me”/)).toBeNull();
    await chartLoaded();
  });

  it('a pick fills the panel, passes the id on and moves focus to the panel', async () => {
    const user = userEvent.setup();
    renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    await user.type(within(panel).getByLabelText('Your name'), 'Hadley');
    await user.click(await within(panel).findByRole('button', { name: 'Hadley, Ike' }));
    expect(await within(panel).findByText('37 · 16th')).toBeInTheDocument();
    expect(within(panel).getByRole('heading', { name: 'Your panel' })).toHaveFocus();
    expect(screen.getByText('next sunday for 3')).toBeInTheDocument();
    expect(getMe()).toBe(3);
    await chartLoaded();
  });

  it('"Not me" forgets the choice and asks again, with focus on the question', async () => {
    setMe(3);
    const user = userEvent.setup();
    renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    await user.click(await within(panel).findByRole('button', { name: 'Not me' }));
    expect(within(panel).getByRole('heading', { name: 'Which one are you?' })).toHaveFocus();
    expect(getMe()).toBeNull();
    expect(screen.getByText('next sunday for null')).toBeInTheDocument();
    await chartLoaded();
  });

  it('a skip puts back the usual prompt and is remembered on this browser', async () => {
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(<HomePage widgets={widgets} />);
    const panel = screen.getByRole('complementary', { name: 'Personal' });
    await user.click(within(panel).getByRole('button', { name: 'Not a shooter / skip' }));
    expect(within(panel).getByRole('heading', { name: 'Your panel' })).toHaveFocus();
    expect(within(panel).getByText(/tap “That’s me”/)).toBeInTheDocument();
    expect(isMeSkipped()).toBe(true);
    await chartLoaded();
    unmount();
    renderWithProviders(<HomePage widgets={widgets} />);
    const again = screen.getByRole('complementary', { name: 'Personal' });
    expect(within(again).queryByRole('heading', { name: 'Which one are you?' })).toBeNull();
    expect(within(again).getByText(/tap “That’s me”/)).toBeInTheDocument();
    await chartLoaded();
  });

  it('a skipped browser still shows a chosen shooter', async () => {
    skipMe();
    setMe(3);
    renderWithProviders(<HomePage widgets={widgets} />);
    expect(await screen.findByText('37 · 16th')).toBeInTheDocument();
    await chartLoaded();
  });
```

and replace

```tsx
    await user.click(await screen.findByRole('button', { name: 'Choose again' }));
    await waitFor(() => expect(screen.getByText(/tap “That’s me”/)).toBeInTheDocument());
```

with

```tsx
    await user.click(await screen.findByRole('button', { name: 'Choose again' }));
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Which one are you?' })).toBeInTheDocument(),
    );
```

and rename that test's title from `'stale me id falls back to the prompt after choosing again'` to `'stale me id asks which one you are after choosing again'`.

- [ ] **Step 14: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/home/pages/HomePage.test.tsx`
Expected: FAIL. There is no "Which one are you?" heading in the Personal aside, and the pick, "Not me" and skip tests fail with it.

- [ ] **Step 15: Swap the personal slot on Home**

Replace the whole of `frontend/src/features/home/pages/HomePage.tsx` with:

```tsx
import { useEffect, useRef, useState } from 'react';
import { getMe, isMeSkipped } from '../../../lib/me';
import { ClubPulse } from '../components/ClubPulse';
import { LatestEventCard } from '../components/LatestEventCard';
import { MePanel } from '../components/MePanel';
import { WhichOneAreYou } from '../components/WhichOneAreYou';
import { WidgetSlot } from '../components/WidgetSlot';
import { homeWidgets } from '../widgets';
import type { HomeWidget } from '../widgets';

export function HomePage({ widgets = homeWidgets }: { widgets?: HomeWidget[] }) {
  const [meId, setMeId] = useState<number | null>(() => getMe());
  const [skipped, setSkipped] = useState(isMeSkipped);
  const asking = meId === null && !skipped;
  // Which card the personal slot holds: the question, the prompt, or a shooter's panel.
  const slot = asking ? 'ask' : String(meId);
  const personal = useRef<HTMLElement>(null);
  const before = useRef(slot);
  // A pick, a skip or "Not me" swaps the card that held focus: carry on at the new card's heading.
  useEffect(() => {
    if (before.current === slot) return;
    before.current = slot;
    const heading = personal.current?.querySelector<HTMLElement>('h2');
    if (heading === null || heading === undefined) return;
    heading.tabIndex = -1;
    heading.focus();
  }, [slot]);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-medium">Sunday Clays</h1>
      <WidgetSlot slot="hero" widgets={widgets} meId={meId} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          <LatestEventCard />
          <ClubPulse />
          <WidgetSlot slot="main" widgets={widgets} meId={meId} />
        </div>
        {/* Named apart from the "Your panel" card inside it: landmark names stay unique. */}
        <aside ref={personal} aria-label="Personal" className="flex min-w-0 flex-col gap-4">
          {asking ? (
            <WhichOneAreYou onPicked={setMeId} onSkipped={() => setSkipped(true)} />
          ) : (
            <MePanel meId={meId} onCleared={() => setMeId(null)} widgets={widgets} />
          )}
        </aside>
      </div>
    </div>
  );
}
```

- [ ] **Step 16: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/home/`
Expected: all pass. The landmark test still finds unique names: with `setMe(3)` it sees "Your panel", and on a fresh visit it sees "Which one are you?".

- [ ] **Step 17: Write the failing `NextSundayCard` test for the no-"me" line**

`NextSundayCard` is a `main`-slot widget, so on a fresh visit its no-"me" line sits beside the new question (Decision 17). In `frontend/src/features/predictions/components/NextSundayCard.test.tsx`, replace the test `'points to Shooters when nobody is picked, with a link that keeps the filters'` with:

```tsx
  it('points to Which one are you? and Shooters when nobody is picked', async () => {
    serve(NEXT_PREDICTIONS);
    renderWithProviders(<NextSundayCard meId={null} />, { route: '/?rt=sporting' });
    const link = await screen.findByRole('link', { name: 'Go to Shooters' });
    expect(link).toHaveAttribute('href', '/shooters?rt=sporting');
    expect(
      screen.getByText(
        'To see your own expected score here, pick your name in “Which one are you?” or choose “That’s me” on your Shooters profile.',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Choose “That’s me”/)).toBeNull();
  });
```

- [ ] **Step 18: Run it to verify it fails**

Run: `cd frontend && pnpm exec vitest run src/features/predictions/components/NextSundayCard.test.tsx`
Expected: FAIL: `Unable to find an element with the text: To see your own expected score here, …`. Every other `NextSundayCard` test passes.

- [ ] **Step 19: Rewrite the no-"me" line**

In `frontend/src/features/predictions/components/NextSundayCard.tsx`, inside `YourExpectation`, replace

```tsx
        <p>Choose “That’s me” on your Shooters profile to see your own expected score here.</p>
```

with

```tsx
        <p>
          To see your own expected score here, pick your name in “Which one are you?” or choose
          “That’s me” on your Shooters profile.
        </p>
```

Keep the "Go to Shooters" link below it as it is.

- [ ] **Step 20: Run it to verify it passes**

Run: `cd frontend && pnpm exec vitest run src/features/predictions/`
Expected: all pass.

- [ ] **Step 21: Update the existing e2e that asserted the old prompts on a fresh visit**

In `frontend/e2e/predictions.spec.ts` (the no-forecast Home test, line 39), replace

```ts
  await expect(card.getByText(/Choose “That’s me”/)).toBeVisible();
```

with

```ts
  await expect(card.getByText(/pick your name in “Which one are you\?”/)).toBeVisible();
  await expect(card.getByRole('link', { name: 'Go to Shooters' })).toBeVisible();
```

Then, in `frontend/e2e/home.spec.ts`, replace

```ts
test('home shows the latest event, the club pulse and the me prompt', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sep 27, 2026' }).first()).toBeVisible();
  await expect(page.getByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49')).toBeVisible();
  await expect(page.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
  await expect(page.getByText(/tap “That’s me”/)).toBeVisible();
});
```

with

```ts
test('home shows the latest event, the club pulse and asks which one you are', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Sunday Clays' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sep 27, 2026' }).first()).toBeVisible();
  await expect(page.getByText('Winners: Finnegan, Stanton & Stockton, Ethan — 49')).toBeVisible();
  await expect(page.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Which one are you?' })).toBeVisible();
});
```

and replace

```ts
test('every home tap target is at least 44px with the me prompt', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByText(/tap “That’s me”/)).toBeVisible();
  await expectTapTargets(page);
});
```

with

```ts
test('every home tap target is at least 44px while asking which one you are', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Which one are you?' })).toBeVisible();
  await expectTapTargets(page);
});

test('every home tap target is at least 44px with the prompt after a skip', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('sc.me.skip', '1'));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByText(/tap “That’s me”/)).toBeVisible();
  await expectTapTargets(page);
});
```

Run (stack as in "Running the e2e stack"): `E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/home.spec.ts e2e/predictions.spec.ts`
Expected: all pass at both projects. Paste the RED from a run on the base. The two renamed home tests fail there because there is no "Which one are you?" heading, and the predictions test fails because the card still says "Choose “That’s me”…".

- [ ] **Step 22: Gates and the full frontend suite with coverage**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check . && pnpm exec vitest run --coverage`
Expected: all pass, with coverage at or above 90% lines and 90% branches.

- [ ] **Step 23: Commit**

```bash
git add frontend/src/lib/me.ts frontend/src/lib/me.test.ts frontend/src/features/shooters/api.ts frontend/src/features/home/components/WhichOneAreYou.tsx frontend/src/features/home/components/WhichOneAreYou.test.tsx frontend/src/features/home/components/MePanel.tsx frontend/src/features/home/components/MePanel.test.tsx frontend/src/features/home/pages/HomePage.tsx frontend/src/features/home/pages/HomePage.test.tsx frontend/src/features/predictions/components/NextSundayCard.tsx frontend/src/features/predictions/components/NextSundayCard.test.tsx frontend/e2e/home.spec.ts frontend/e2e/predictions.spec.ts
git commit -m "feat(home): Which one are you? and Not me in the personal slot (Plan 15 T3)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: End to end at both viewports

**Files:**
- Create: `frontend/e2e/insight-bumps.spec.ts`

**Interfaces:**
- Consumes: `GET /api/insights/home`, `/api/insights/shooters/{id}`, `/api/insights/sundays/{date}`, `/api/shooters?q=`, and `GET/DELETE /api/bumps` (Task 1); `[data-insight-key]` and "Fist bump, N bump(s)" (Task 2); "Which one are you?", "Your name", "Matching shooters", "Not a shooter / skip", "Not me" and "Your panel" (Task 3); `expect`/`test` from `e2e/fixtures.ts`, `whenSettled` and `expectNoSideScroll` from `e2e/layout.ts`, and `VIEWER_STATE` from `e2e/authState.ts`.
- Produces: no code interface.

- [ ] **Step 1: Write the spec**

Create `frontend/e2e/insight-bumps.spec.ts`. The round-trip test is ported from the Sheet's reviewed T11 (Decision 20).

```ts
import type { Page } from '@playwright/test';

import { VIEWER_STATE } from './authState';
import { expect, test } from './fixtures';
import { expectNoSideScroll, whenSettled } from './layout';

/** Fist bumps on insights and "Which one are you?" (Plan 15). Expectations come from the API. */

interface Insight {
  key: string;
}
interface Feed {
  as_of: string | null;
  hero: Insight | null;
  top: Insight[];
}
type Counts = Record<string, { bumps: number; bumped: boolean }>;

async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

const bumpOf = (page: Page, key: string) =>
  page.locator(`[data-insight-key="${key}"]`).first().getByRole('button', { name: /^Fist bump/ });

const named = (count: number) => new RegExp(`^Fist bump, ${String(count)} bump`);

const countsLoaded = (page: Page) =>
  page.waitForResponse(
    (r) => r.url().includes('/api/bumps?') && r.request().method() === 'GET' && r.ok(),
  );

test('a bump counts at once, survives a reload and can be taken back', async ({
  page,
  playwright,
  baseURL,
}, testInfo) => {
  const feed = await getJson<Feed>(page, '/api/insights/home');
  // The two projects share one stack: each bumps its own insight, so the counts never collide.
  const insight = testInfo.project.name === 'mobile' ? feed.top[0] : feed.hero;
  if (insight == null) throw new Error('the fx world has a top story and a top insight');
  const sent = (method: 'POST' | 'DELETE') =>
    page.waitForResponse(
      (r) => r.url().endsWith('/api/bumps') && r.request().method() === method && r.ok(),
    );
  const button = bumpOf(page, insight.key);
  let device: string | null = null;
  try {
    let loaded = countsLoaded(page);
    await page.goto('/');
    const first = (await (await loaded).json()) as Counts;
    device = await page.evaluate(() => localStorage.getItem('sc.device'));
    const before = first[insight.key]?.bumps ?? Number.NaN;
    // Polls until React has rendered the server's count.
    await expect(button).toHaveAccessibleName(named(before));
    await expect(button).toHaveAttribute('aria-pressed', 'false');
    await Promise.all([sent('POST'), button.click()]);
    await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(button).toHaveAccessibleName(named(before + 1));
    loaded = countsLoaded(page);
    await page.reload();
    await loaded;
    await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(button).toHaveAccessibleName(named(before + 1));
    await Promise.all([sent('DELETE'), button.click()]);
    await expect(button).toHaveAttribute('aria-pressed', 'false');
    await expect(button).toHaveAccessibleName(named(before));
    loaded = countsLoaded(page);
    await page.reload();
    const last = (await (await loaded).json()) as Counts;
    expect(last[insight.key]).toEqual({ bumps: before, bumped: false });
    await expect(button).toHaveAccessibleName(named(before));
  } finally {
    // A failed attempt must not leave a bump on the shared stack.
    if (device !== null) {
      // A fresh context: at a test timeout the page's own is already closed.
      const cleanup = await playwright.request.newContext({ baseURL, storageState: VIEWER_STATE });
      await cleanup
        .delete('/api/bumps', { data: { key: insight.key, device_id: device } })
        .catch(() => undefined);
      await cleanup.dispose();
    }
  }
});

test('every insight list offers a bump: Home, a profile and a Sunday', async ({ page }) => {
  const home = await getJson<Feed>(page, '/api/insights/home');
  const shooters = await getJson<{ shooter_id: number; display_name: string }[]>(
    page,
    '/api/shooters?q=Hadley',
  );
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  if (hadley === undefined) throw new Error('the fx world has Hadley, Ike');
  const profile = await getJson<Feed>(page, `/api/insights/shooters/${String(hadley.shooter_id)}`);
  if (home.as_of === null) throw new Error('the fx world has a latest Sunday');
  const sunday = await getJson<Feed>(page, `/api/insights/sundays/${home.as_of}`);
  const pages: [string, Insight | undefined][] = [
    ['/', home.top[0]],
    [`/shooters/${String(hadley.shooter_id)}`, profile.top[0]],
    [`/events/${home.as_of}`, sunday.top[0]],
  ];
  for (const [path, insight] of pages) {
    if (insight === undefined) throw new Error(`${path} has a top insight in the fx world`);
    await page.goto(path);
    const button = bumpOf(page, insight.key);
    await expect(button, path).toBeVisible();
    const box = await button.boundingBox();
    expect(box?.height ?? 0, `${path} bump height`).toBeGreaterThanOrEqual(44);
    expect(box?.width ?? 0, `${path} bump width`).toBeGreaterThanOrEqual(44);
    await whenSettled(page);
    await expectNoSideScroll(page);
  }
});

test('bump counts arriving never move the page', async ({ page }) => {
  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/bumps?**', async (route) => {
    await held;
    await route.continue();
  });
  await page.addInitScript(() => {
    const w = window as unknown as { __shift: number };
    w.__shift = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as (PerformanceEntry & {
        value: number;
        hadRecentInput: boolean;
      })[]) {
        if (!entry.hadRecentInput) w.__shift += entry.value;
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto('/');
  await expect(
    page.locator('[data-insight-key]').first().getByRole('button', { name: /^Fist bump/ }),
  ).toBeVisible();
  await whenSettled(page);
  // Measure only what the counts do once they land.
  await page.evaluate(() => {
    (window as unknown as { __shift: number }).__shift = 0;
  });
  const loaded = countsLoaded(page);
  release();
  await loaded;
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  const shift = await page.evaluate(() => (window as unknown as { __shift: number }).__shift);
  expect(shift, 'layout shift from bump counts').toBeLessThan(0.01);
});

test('"Which one are you?": a pick fills the panel, "Not me" asks again, a skip stays away', async ({
  page,
}) => {
  await page.goto('/');
  const personal = page.getByRole('complementary', { name: 'Personal' });
  const question = personal.getByRole('heading', { name: 'Which one are you?' });
  await expect(question).toBeVisible();
  await personal.getByLabel('Your name').fill('Hadley');
  await personal
    .getByRole('list', { name: 'Matching shooters' })
    .getByRole('button', { name: 'Hadley, Ike' })
    .click();
  await expect(personal.getByText('Last out')).toBeVisible();
  await expect(personal.getByRole('heading', { name: 'Your panel' })).toBeFocused();
  await page.reload();
  await expect(personal.getByText('Last out')).toBeVisible();
  await personal.getByRole('button', { name: 'Not me' }).click();
  await expect(question).toBeVisible();
  await expect(question).toBeFocused();
  expect(await page.evaluate(() => localStorage.getItem('sc.me'))).toBeNull();
  await personal.getByRole('button', { name: 'Not a shooter / skip' }).click();
  await expect(question).toHaveCount(0);
  await expect(personal.getByText(/tap “That’s me”/)).toBeVisible();
  await page.reload();
  await expect(personal.getByRole('heading', { name: 'Your panel' })).toBeVisible();
  await expect(question).toHaveCount(0);
  await expectNoSideScroll(page);
});
```

- [ ] **Step 2: Run it on the base to see it fail (RED)**

Build a stack from `feat/insight-bumps` *before* Tasks 1–3 merged (or from `main` @ `39acf96`), then run:
`E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/insight-bumps.spec.ts`
Expected: all four fail at both projects. The bump tests time out waiting for `/api/bumps` or for `[data-insight-key]`, and the question test finds no "Which one are you?" heading. Paste this output as the RED evidence.

- [ ] **Step 3: Run it on the integrated branch (GREEN)**

Rebuild the stack from `feat/insight-bumps` with Tasks 1–3 merged, then run:
`E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/insight-bumps.spec.ts`
Expected: 8 passed (4 tests × desktop and mobile).

- [ ] **Step 4: Run the full suite and the gates**

Run: `E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test` then `cd frontend && pnpm lint && pnpm exec prettier --check .`
Expected: the whole Playwright suite passes. Re-run a known flaky spec once before reporting it, and name it if it still fails. Lint and prettier are clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/insight-bumps.spec.ts
git commit -m "test(e2e): insight bumps and Which one are you? at both viewports (Plan 15 T4)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review (author)

- **Design coverage:**
  - Bumps on Home (Top story, spotlight, kudos, more), profiles and event pages: T2, through `InsightCard`, `RecapCard` and `KudosStrip`, with every `FeedSections` section in a provider.
  - Year in Review: none on `main` (Decision 9).
  - Keyed by `key` and anonymous per device: T1 and T2 (`lib/device.ts`).
  - Viewer-gated: T1 (a discovered router, covered by the auth matrix).
  - No-store: T1, through the etag rule and its tests.
  - Store and limiter port: T1.
  - GET batched, with a cap: T1 (`MAX_KEYS`) and T2 (chunking).
  - POST/DELETE idempotent, 400/404/429: T1.
  - Vanished insights kept but hidden: T1 and T2.
  - The reviewed BumpButton behaviour: T2 (9 tests).
  - Shared row and per-page batching: T2.
  - No admin card and no share images: none added.
  - "Which one are you?", skip, "Not me" and focus: T3. The copy conflict is resolved in Decision 17: `MePanel`'s prompt shows only after a skip, `NextSundayCard`'s no-"me" line is rewritten to point at the question (T3, with its unit test and `predictions.spec.ts`), and `NextTrophy` never renders without a "me".
  - e2e at both viewports: T4 (round trip, presence on three pages, no layout shift, question flow), plus the T3 home.spec updates.
- **Placeholder scan:** none. Every code step carries its code.
- **Type consistency:**
  - `bumpsKey(keys, deviceId)`, `BumpsKey`, `useBumpToggle(queryKey, deviceId, insightKey, shown?)`, `BumpButton{queryKey, insightKey, deviceId, state, noteId, counts?}` and `InsightBump{insightKey}` (which passes the provider's `counts`) agree across T2.
  - The JSON `key` and `device_id` agree between T1's `BumpIn` and T2's body and T4's cleanup.
  - `MAX_KEYS = 100` matches `BATCH = 100`.
  - `isMeSkipped`, `skipMe` and `useShooters(q, active, {enabled})` agree between T3 and T4.
