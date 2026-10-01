# Sunday Sheet Implementation Plan (Sub-plan 14)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implementers (including fix rounds) run on Sonnet; every reviewer, re-reviewer and verifier runs on Opus (Global Constraints). Each task is one branch, one worktree and one PR **into `feat/sunday-sheet`**, never `main`. Implementers commit; they never push or open PRs. The controller pushes, opens the PRs and merges them, in the waves below.

**Goal:** Make `/` "The Sunday Sheet": a per-Sunday page (masthead, four numbers, headline, spotlight and a feed of posts about the day and its people, with Home's rail beside it) that a club email can link to. It adds anonymous 🤜🤛 fist bumps per post, "Which one are you?", Share-as-image and "See why →" into each post's chart, and loses nothing Home shows today.

**Architecture:** The backend assembles one issue per held Sunday from rows that are already stored. `analytics/sheet.py` is pure: it maps insight kinds to six post types, adds one post per trophy earned and per "On this day" look-back, interleaves the feed and groups the rest. `api/routes/sheet.py` loads the rows, caches the issue by `data_version` and serves `GET /api/sheet/latest` and `GET /api/sheet/{date}`. Bump counts never enter that cached body. They live in a new durable table `fist_bumps` (migration `0006`, with `bump_attempts` for the 120-per-10-minutes IP limit), are served by `GET /api/sheet/{date}/bumps` (never ETagged or stored) and change through idempotent `POST`/`DELETE /api/sheet/bumps`. An admin lists and wipes them, audited. On the frontend, a new feature `features/sheet/` owns `/` and `/sheet/:date`. Home's components stay in `features/home/` and its `homeWidget` registry is re-pointed to Sheet slots: `hero` becomes the lead (the insights feature's `SheetLead`), `main` the rail and `me` Your Sunday. A random device id in `lib/device.ts` drives the bumps, which are optimistic and run in tap order.

**Tech Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · pytest + Hypothesis · Postgres 17 · React 19 · TypeScript (strict) · TanStack Query v5 (mutation `scope`) · React Router v7 · Tailwind v4 · ECharts (Plan 07 `ChartFrame`) · openapi-fetch · html-to-image (`lib/share.ts`) · Vitest + Testing Library + MSW · Playwright.

**Spec:** `docs/superpowers/specs/2026-09-30-sunday-sheet-design.md` (binding; read it before your task).

**Base:** `feat/sunday-sheet` @ `7b65f55` ("docs: Sunday Sheet design"), which is `main` @ `39acf96` plus the spec. The final code of every task was validated in a scratch worktree on that base, and the result passed `ruff check`, `ruff format --check`, `mypy --strict src`, the full backend suite with coverage (2,796 tests, 99.78%, before a handful of extra coverage tests were added; after the review revision the backend gates and the 151 new and changed backend tests were re-run, not the whole suite), `tsc`, `eslint --max-warnings 0`, `prettier --check .`, the full Vitest suite with coverage (247 files, 2,190 tests, coverage thresholds met; 2,194 after the review revision, lines 99.74%, branches 99.11%), and the full Playwright suite on a compose stack built from the result (one unrelated failure, Decision 27; not re-run after the review revision). **Pre-flight** (controller, before each wave): every Create target must not exist, every Modify target must exist, and every "replace" block must occur exactly once in the task's base. If a block fails, regenerate only that block against the current `feat/sunday-sheet`.

**Delivery:** task branches are `task/14-<N>-<slug>`, cut from `feat/sunday-sheet` after the previous wave has merged. Every PR targets `feat/sunday-sheet`. CI runs on each PR, and the deployer ignores the branch because it watches only `main`. Commits use the gitgat identity, which is already set in the repo config. Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; an implementer on another model names its own model there instead (Decision 28). Implementers never push or open PRs. After Task 11 the owner previews the branch locally, using the compose stack from the branch and a copy of the production database (spec "Delivery", step 6). Only on the owner's say-so does one final PR take `feat/sunday-sheet` to `main`.

## Global Constraints

**Owner rules (spec, unchanged and binding), verbatim:**

- Named-shooter posts are positive or neutral only. Negatives appear only at the club or field level.
- No skill-rating ranking and no rivals or head-to-head. Improvement is called out instead.
- App copy never uses he/she/his/her.
- Real people's names never appear in the repo. Tests and docs use the invented names.
- The spreadsheet score is authoritative.

**Repo conventions:**

- Python `3.13`, Node `22` LTS and Postgres `17`, with `uv` (backend) and `pnpm` (frontend). Lockfiles are committed. This plan adds no package: Hypothesis, MSW, html-to-image and lucide-react are already declared. Never edit `[project].dependencies`, `[dependency-groups]`, `uv.lock`, `dependencies`, `devDependencies` or `pnpm-lock.yaml`.
- Coverage floor is **90% lines AND 90% branches**, backend and frontend measured separately. `ratchets/` is controller-only.
- Backend gates: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict src`. Frontend gates: `pnpm lint` (`eslint --max-warnings 0`), `pnpm typecheck` (it first regenerates `src/api/schema.d.ts` from the backend with `pnpm gen:api`) and `pnpm exec prettier --check .`.
- TDD: every production change starts from a failing test (superpowers:test-driven-development).
- Migrations are expand/contract compatible with the previous release (`api` runs `alembic upgrade head` on start). This plan's one migration is `0006_fist_bumps` (Task 1). Its two tables are new and durable like `rules` and `audit_log`: `domain/rebuild.py` `LIVE_TABLES` never lists them.
- Routers are discovered (C2): a module `api/routes/<name>.py` needs a viewer, and `admin_<name>.py` needs an admin. Never edit `api/app.py`. Feature routes come from `features/*/routes.tsx` (C10). Nav orders are fixed (`navRegistry.test.ts`). Exactly four features are phone tabs.
- Viewports: phone `390×844` and desktop `1440×900` are both first-class. Tap targets are at least 44 px, no page scrolls sideways, and every page has an e2e check at both sizes.
- Every chart renders in `ChartFrame` with Table, CSV, fullscreen and a plain-language explainer ("what this shows / how it's worked out"). Fullscreen and the CSV cover every row.
- Copy says "Sunday", never "event", and never uses "class". Pronouns are neutral (owner rule above).
- Invented names only: `Ike Hadley` / `Hadley, Ike` (shooter 3), `Amy Ace`, `Bob Bee`, `Cal Cy`, and the e2e fixture names already in `frontend/e2e`.
- The theme is dark only, with the existing Tailwind tokens (`bg-elevated`, `bg-surface`, `text-text`, `text-text-muted`, `text-accent`, `border-outline-variant`, `rounded-card`, `rounded-button`). Never hard-code a colour.
- Stage files explicitly (`git add <paths>`, `git rm <paths>`). Never `git add -A`: the repo root can hold untracked workbooks.
- Agents: implementers, including fix rounds, run on Sonnet. Every reviewer, re-reviewer and verifier runs on Opus. Workflows stay at about 10 agents or fewer and run the waves below one at a time.
- Actions budget: Pro included minutes plus the $75 Actions budget. If CI is blocked by billing, stop and tell the owner.

## Review Focus

Five ways a person using this could be hurt that the spec implies but never tests. Each one is pinned to tests in its owning task:

1. **A bump that "doesn't stick" because a cache served the old count.** The issue body is ETagged by `data_version`, but bumps change without a data_version bump. If the counts were in the body, or if `GET …/bumps` were tagged, a reload would answer `304` with yesterday's counts. Expected: counts are never in the issue body, the bumps endpoint is `no-store` with no ETag (so `If-None-Match: *` still gets a fresh 200), and a reload shows the server's count. Tests: Task 3 `test_counts_are_never_cached_and_never_in_the_issue_body` and the `test_etag_eligibility` / `test_cache_control_by_path` bump rows. Task 2 `test_the_body_never_carries_bump_counts_and_is_etagged`. Task 11 "a bump counts at once, survives a reload and can be taken back".
2. **Double taps and races.** A quick double tap, two tabs on one phone, or two identical requests in flight. Expected: a device counts once, a count never goes below zero, the server never answers 500 on a duplicate, and two taps reach the server in tap order so the button ends where the last tap left it. Tests: Task 1 `test_concurrent_identical_bumps_store_one_row`, `test_add_over_a_row_another_writer_stored_never_raises` and `test_remove_is_idempotent_and_never_goes_negative`. Task 3 `test_bumping_is_idempotent_per_device_and_taking_back_too`. Task 4 `BumpButton.test.tsx` "takes a bump back on a second tap, and sends the two taps in order".
3. **A browser that cannot keep a device id.** Private mode, blocked site data, a corrupted `sc.device` value, or the owner's preview opened over plain `http://` on the LAN, where `crypto.randomUUID` does not exist. Expected: the page never crashes and never sends an id the server answers 400 to. Counts still show, the buttons are off, and the page says "Bumps need this browser to remember you". Tests: Task 4 `device.test.ts` (all six), `BumpButton.test.tsx` "shows the count but is off…" and `SheetPage.test.tsx` "shows the counts but turns bumps off…". Task 3 `test_a_device_id_that_is_not_a_uuid_is_400`.
4. **Lopsided or thin Sundays.** A Sunday where nearly every post is a PB, or an older Sunday with few insights, or none at all. Expected: every post type ①–⑥ the Sunday has gets at least one feed post, however low it scores (a lone "On this day" or welcome is never buried in More). The feed still fills to 10 by score. No type runs three in a row while another chosen type is left, and when only one type remains it carries on in score order. A Sunday with no posts shows "Nothing to report for this Sunday yet", never a blank page. Tests: Task 2 `test_the_feed_has_one_post_of_every_type_the_issue_has` (lopsided), `test_a_thin_sunday_puts_every_post_in_the_feed` (thin), Hypothesis `test_interleave_never_runs_a_type_three_times_while_another_is_left` (also checks every present type posts), `test_the_feed_interleaves_types_and_caps_at_ten`, and on the fx world `test_the_feed_never_runs_a_type_three_times_while_another_is_left` (last 8 issues) and `test_the_latest_issue_carries_on_this_day_whenever_it_has_a_look_back`. Task 4 `SheetPage.test.tsx` "says so when a Sunday has no posts yet".
5. **A data correction under live bumps.** A re-upload removes a PB or a trophy that people bumped. Expected: the bumps stay in the table (durable, never truncated) but never show on a Sheet. A new bump on that key is refused with 404, and the client rolls back with "Couldn't send that bump". An admin can still find the stale key (flagged "no longer on a Sheet") and wipe it. Tests: Task 1 `test_bumps_survive_a_rebuild_and_a_recompute`. Task 3 `test_stale_bumps_are_kept_hidden_and_wipeable` and `test_an_unknown_post_key_is_404`. Task 4 `BumpButton.test.tsx` "rolls back and says so when the bump fails". Task 7 `BumpsPanel.test.tsx` "…flags stale ones".

## Decisions

Rulings where the spec is silent or ambiguous, or where the code it names works differently from what the spec assumes. Rulings marked (X) touch another plan's surface or a C10 contract.

1. **Which Sundays have a Sheet.** One issue per *held* Sunday (`events.results_complete`, the insights' `held_dates`). This is the same set that has anchored insights and home picks. `/` is the latest held Sunday. Any other date, including an attendance-only Sunday, answers 404 `sheet_not_found`, and the page shows "No Sunday Sheet for this date" with links to All issues and the latest issue. **Newer Sunday note (review I-3, controller ruling):** Home's Latest Sunday card followed the newest Sunday, held or not. So when the newest Sunday is after the latest issue (attendance only, or only partly scored), the latest issue's masthead carries `masthead.newer = {date, has_scores, head_count, n_shooters}` and shows "Newer Sunday, Oct 4, 2026: Attendance only — 14 shooters, no scores recorded." (Home's wording; "No scores recorded" without a head count; "Partial results — 6 shooters so far" when partly scored), linking "See Oct 4, 2026" to `/events/{date}`. Past issues and an up-to-date latest issue have `newer: null`. The issue number is the 1-based position among held Sundays. Previous and next are the neighbouring held Sundays (`null` at the ends).
2. **Which insights become posts.** The pool is every row anchored on the issue's Sunday, from any page (so Sunday-page kinds such as `ev.how-it-played` post too). On the latest issue only, it also takes the evergreen rows whose `pages` include `home`. Home's pool also held rows anchored on the *previous* held Sunday (`select.HOME_SUNDAYS = 2`); on the Sheet those post on issue N−1 instead, so nothing is lost, but they leave the front page (review M-7). Four kinds in the spec's ①② lists are evergreen and profile-only (`pf.season-best`, `pf.hot-form`, `pf.up-on-usual`, `pf.year-up`). Taking all of them would swamp the feed (the fixture world has dozens), so **on the latest issue a row of these kinds posts when its date param is the issue Sunday** (`day`, or `last` for `pf.hot-form`): the rows that are news that Sunday (review I-4, controller ruling). This is `sheet.FRESH_EVERGREEN` and `sheet.fresh_on`; `_issue_rows` loads those kinds with Home's evergreen rows. Past issues never take evergreen rows, because they are "as of now". An evergreen key carries no date, so an evergreen post that is still true next week keeps its bumps, and those bumps leave the past issue they were given on (review M-6: a known behaviour for the owner preview). Home's pinned recap (`home.sunday-recap`) is never a post: it is the headline's deck.
3. **Ranking.** `rank_score` is relative to the *latest* Sunday at recompute time, so older issues would rank near zero. Posts use the Sunday page's rule instead: `base_score × recency(anchor, issue Sunday)`, which is ×1.5 for the issue's own rows and ×1.0 for evergreen rows. Trophy posts score `18.0` and "On this day" `9.0`. The calibration is the fx world's anchored base scores (8.7 / 12.5 / 18 / 24 at the 25th / 50th / 75th / 90th percentile) × 1.5. Ties break on `post_key`.
4. **Feed size, type mix and interleave (review I-1, controller ruling).** `FEED_CAP = 10` (the spec says "about 8–12"). The feed first takes the best post of every feed type ①–⑥ the issue has (at most six), then the best of the rest by score up to the cap. Those chosen posts are ordered greedily: take the best chosen post that does not make a third of one type in a row; when only that type is left, take it anyway, because the rule cannot hold. So "On this day" (score 9) and thin types such as welcomes always reach the feed when present. Posts of kinds outside ①–⑥ (type `other`) and everything past the cap go to "More from this Sunday".
5. **Lead.** The headline is the Sunday's stored `hero` pick (`insight_picks`) and the spotlight its `spotlight` pick. Both are removed from the posts. A pick that names a shooter with a polarity other than positive or neutral is dropped (owner rule). With no hero, the deck shows alone under "Top story".
6. **Named posts.** A row with `named_shooter_ids` must be `positive` or `neutral`, or it is dropped. The DB already forbids named `field_negative`, but `mixed` rows such as `ev.rain-day` may name people.
7. **Trophy posts.** There is one post per trophy code earned that day, keyed `trophy:{code}:{date}`. The code can contain `:`; the key is parsed from the right. The headline is "{Name — Tier} unlocked by A, B, C and N more", with names in `First Last` form via `natural_name`. **When more than three people earned it, the card lists every holder under the headline as profile links ("Earned by"): the first 8 show, and "+N more" opens the rest in place. Every name is in the DOM either way** (review I-2, controller ruling). Catalog titles such as "Events Attended — …" headline these posts as they are named in the Trophy Room; renaming that achievement is out of scope and is flagged for the owner (review M-8). Codes missing from the catalog are skipped. Its "See why" opens `/achievements/{code}`, the Trophy Room entry.
8. **"On this day" posts.** There is one post per look-back Sunday, keyed `otd:{date}:{years_ago}`. The headline is "One year ago, on Sep 28, 2025, 31 shooters came out; the top score of 48 was shot by Amy Ace." It names the top scorers (positive, never against anyone), which keeps the winners Home's On-this-day card showed. A look-back without scores posts too, as Home's card listed it: "Two years ago, on Sep 28, 2024, 18 shooters came out (attendance only)." or, with no head count, "… a Sunday was shot; no scores were recorded." (review M-1). Its "See why" opens that Sunday's page, and its "How we worked it out" opens `sheetExplainers.onThisDay`, the yir card's text moved to the Sheet (Task 8 deletes the yir entry).
9. **The four numbers.** Shooters, field median and top score come from the event row, exactly as Home's Latest Sunday card showed them. "Trophies" counts awards that day, so two people earning one trophy count as two. The card's winners line is not repeated on the Sheet: the `ev.top-score` post and the "Latest Sunday details" link carry it.
10. **More from this Sunday.** The server groups the rest by family in rank order, with labels; the synthetic families are `trophy` and `on_this_day`. The client renders the labels it is given. It is a closed `<details>`, and its posts are bumpable.
11. **Bump API details.** `device_id` must be a canonical hyphenated UUID (any case), else 400 `bad_device_id`. `GET /api/sheet/{date}/bumps` takes `device_id` as optional. The response lists every current post of the issue with zeros, and never a stale key. `POST` and `DELETE` resolve the key against the issue it names (trophy and OTD keys carry their date; an insight key uses its anchor, or the latest issue if evergreen). A key not on that issue as the data stands now is 404 `post_not_found`. Both verbs return the post's `{bumps, bumped}` for that device.
12. **Rate limit.** 120 actions per client IP per 10 minutes, counted in `bump_attempts`. Every `POST` or `DELETE` that the limit itself does not refuse counts, including ones that then fail with 400 or 404, so key scanning is limited too. The action is recorded and committed before validation, as the login limiter does. Rows outside the window are pruned inline. `GET` counts are not limited. In e2e all traffic comes from one IP, but the bump specs make fewer than 10 actions.
13. **(X) Cache rules.** `api/etag.py` gains `NO_STORE_SUFFIXES = ("/bumps",)`. A GET under `/api/` whose path ends in `/bumps` is never ETagged and is `Cache-Control: no-store`. The issue body keeps the normal weak ETag.
14. **Admin.** The spec names only the wipe. The ops page also needs to find a key, so `GET /api/admin/sheet/bumps` lists bumped posts (up to 100, most recently bumped first). Each entry has a readable label (the insight's headline, "Trophy {code}, {date}", "On this day, {date}", or "No longer on a Sheet"), the issue date and `current`. `DELETE /api/admin/sheet/bumps/{post_key}` wipes stale keys too (never 404) and records `sheet.wipe_bumps` with `{post_key, wiped}`. The panel asks for a second tap before wiping.
15. **(X) Where the Sheet lives.** A new feature `features/sheet/` owns `/` (index) and `/sheet/:date`. Its nav item is `{label: 'Sheet', path: '/', icon: Newspaper, order: 10, mobileTab: true}`. The C10 tables in `navRegistry.test.ts` move order 10 and the phone tab from `home` to `sheet`. `features/home/` keeps owning its components (MePanel, ClubPulse, TurnoutChart, WidgetSlot) and the `homeWidget` registry (`features/home/widgets.ts`, unchanged file names), as the spec asks ("the features keep owning their components"). Its route, `HomePage` and `LatestEventCard` are retired.
16. **(X) Slots.** `HomeWidget.Component` takes `HomeWidgetProps = { meId; issue? }`. `hero` renders in the lead block with the issue: the insights feature's `SheetLead` (headline with the recap as its deck, then the spotlight). `main` renders in the rail on the latest issue only: the predictions feature's Next Sunday, which is about the coming Sunday and would mislead on a past issue. `me` renders inside Your Sunday: the achievements feature's Your next trophy. The yir feature's On-this-day home widget is removed, because "On this day" is now feed post ⑥.
17. **Filters.** Both Sheet routes declare `ROUND_TYPE_ONLY`. The spec asks only that the filter bar show "no date control". The rail's Your Sunday and Club pulse keep following the round type, as on Home. The issue itself (numbers and posts) ignores both filters and says so. On the Sheet, Club pulse shows a fixed window, the 8 weeks up to the issue's Sunday ("8 weeks to Sep 27, 2026 · not affected by the time filter"), with its own explainers and no window tag. It no longer shows the header's window.
18. **Phone order and desktop layout.** Each block carries a `data-sheet-block` name and an `order-N` class from `SHEET_ORDER`. Below 1024 px the two column wrappers are `display: contents`, so every block is one flex item in the spec's order: masthead, numbers, Your Sunday, lead, feed, More, Next Sunday, Club pulse, details. From 1024 px the main column (lead, feed, More) spans two of three grid columns, beside the rail (Your Sunday, Next Sunday, Club pulse, details).
19. **Device id.** `localStorage['sc.device']` holds a random v4 UUID, created on first use. It comes from `crypto.randomUUID`, or from `getRandomValues` where that does not exist (an insecure origin). A stored value that is not a UUID is replaced. When storage throws, or does not keep what is written, the id is `null` and bumps are off.
20. **"Which one are you?" and "Not me".** Skip sets `localStorage['sc.me.skip'] = '1'`, and picking anyone (`setMe`, from the Sheet or the "That's me" button) clears it. There is no "Not me" control on Home today: the only way to clear the choice is the profile's "That's me" toggle. So Your Sunday gets a "Not me" button (`clearMe`), which brings the question back.
21. **Bump UI.** The count changes at once, in the click handler. Requests for one post run serially (TanStack mutation `scope`), and only the last request for a post writes the server's answer, so a quick un-bump is never undone by the earlier answer. A failure restores the counts it started from and shows "Couldn’t send that bump". The button is `aria-pressed`, labelled "Fist bump, N bumps", and never shows who bumped.
22. **"See why" and nothing lost from Home's insight cards (review I-5, controller ruling).** An insight post uses `chartHref` from the insights feature (an explicit window and no `rt`, Plan 12). Trophy and "On this day" links keep the global filters (`useRoundTypeHref`). Every insight post (feed and More) also keeps what Home's `InsightCard` had: the "New" tag (`insight.is_new`), the `chart.also` extra chart links ("See the chart: …", second-person labels for the viewer's own post) and "How we worked it out", which opens `InsightExplainer` with `you` for the viewer's own post.
23. **Share images.** `lib/share.ts` is reused. The image is a 360 px branded card rendered off screen only while the image is made: a masthead strip, the headline, and either the trophy art or a 📈 line with the linked chart's label. The spec's "chart snippet" is that label line. **Flag for the owner at preview (review M-2):** this reduces the spec item; a later follow-up could draw a sparkline for profile-trend charts. No chart data is fetched for an image, because most posts link a chart on another page. The file is named `sunday-sheet-{date}-{first six headline words}.png`.
24. **Share this Sheet.** It uses the Web Share API `{title, text, url}`. Without it, or on `NotAllowedError`, it copies "text\nurl" to the clipboard and says "Link copied." The text is "The Sunday Sheet, Sep 27, 2026: 23 shooters, field median 39, top score 49, 13 trophies."
25. **Copy.** The masthead's h1 is "The Sunday Sheet", shown in capitals by CSS. Lead cards are "Top story" and "Spotlight" (subtitle "Shooter to know"). "Top story" is subtitled "Not affected by the time filter", or "Sep 20, 2026 · not affected by the time filter" when the hero pick is about an earlier Sunday than the issue's (picks draw on the last two held Sundays, as Home's did; review M-4). The feed heading is "This Sunday", subtitled "All round types · not affected by the filters" (review M-5). Type tags read "Milestone", "On the up", "Trophy unlocked", "The day", "Welcome", "On this day" and "From the Sunday".
26. **Kept for other readers.** `GET /api/insights/home`, `useHomeFeed` and `GET /api/on-this-day` stay: the insights e2e, the API tests and the yir mocks use them.
27. **Known unrelated e2e failure.** In the final replay, `e2e/window-labels.spec.ts` "window tags carry their dates…" failed on the mobile project 3 times out of 3. It loads `/club?w=…` and calls `select.isVisible()` before the lazy route has rendered the top-bar select. No task here touches that page or that spec. The controller should check it on `main` before treating it as a regression.
28. **Commit trailer (review M-9).** The commit commands carry `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, as the controller set. An implementer running on another model (implementers run on Sonnet) replaces the model name in that trailer with its own; nothing else in the command changes.
29. **Owner-preview notes.** Flag at the step-6 preview: the share card's chart snippet is a label line (Decision 23, M-2); evergreen posts carry their bumps to later issues and leave the past issue (Decision 2, M-6); trophy titles come straight from the catalog, including "Events Attended — …" (Decision 7, M-8).

## File Structure

| Path | Task | Responsibility |
|---|---|---|
| `backend/migrations/versions/0006_fist_bumps.py` | 1 | Creates `fist_bumps` and `bump_attempts` (expand-only) |
| `backend/src/sunday_clays/models/bumps.py` | 1 | `FistBump`, `BumpAttempt` ORM models |
| `backend/src/sunday_clays/domain/bumps.py` | 1 | Idempotent bump store: add, remove, states, wipe, totals |
| `backend/src/sunday_clays/auth/ratelimit.py` | 1 | + `bumps_limited`, `record_bump_action` (120 / 10 min / IP) |
| `backend/src/sunday_clays/analytics/sheet.py` | 2 | Pure assembler: post types, trophy and OTD posts, interleave, More, issue |
| `backend/src/sunday_clays/api/routes/sheet.py` | 2, 3 | `GET /api/sheet/latest`, `GET /api/sheet/{date}` (cached); bumps routes (Task 3) |
| `backend/src/sunday_clays/api/routes/admin_sheet.py` | 3 | Admin list and audited wipe of bumps |
| `backend/src/sunday_clays/api/etag.py` | 3 | Bump counts never ETagged, always `no-store` |
| `frontend/src/lib/device.ts` | 4 | This browser's random device id |
| `frontend/src/features/sheet/api.ts`, `mocks.ts`, `explainers.ts`, `routes.tsx` | 4 (8, 9) | Sheet queries, bump toggle, fixtures, number explainers, routes |
| `frontend/src/features/sheet/components/*` | 4, 6, 8, 10 | Masthead, Numbers, BumpButton, PostCard, Feed, MoreFromSunday, SheetSkeleton, WhichOneAreYou, YourSunday, SundayDetails, SeeWhy, PostShareCard, SharePostButton, ShareSheetButton |
| `frontend/src/features/sheet/pages/SheetPage.tsx` | 4, 8 | The page: blocks, order, slots |
| `frontend/src/features/insights/components/SheetLead.tsx` | 5 | Headline with its recap deck, and the spotlight |
| `frontend/src/lib/me.ts` | 6 | + "skip" (`isMeSkipped`, `skipMe`) |
| `frontend/src/features/admin-ops/components/BumpsPanel.tsx` | 7 | Ops page: bumped posts and the two-step wipe |
| `frontend/src/features/home/{widgets.ts, components/*}` | 8, 9 | Slots re-pointed to the Sheet; Club pulse fixed window; MePanel title and actions; Home route retired |
| `frontend/src/lib/share.ts` | 10 | + `shareLink` (Web Share API or clipboard) |
| `frontend/e2e/sheet.spec.ts` | 11 | The Sheet end to end at both viewports |

## Waves

Tasks in one wave touch disjoint files and can run in parallel lanes. A wave starts once every PR of the waves before it has merged into `feat/sunday-sheet`.

| Wave | Tasks (parallel) | Needs |
|---|---|---|
| 1 | Task 1 ∥ Task 2 ∥ Task 5 ∥ Task 6 | — |
| 2 | Task 3 | Tasks 1, 2 |
| 3 | Task 4 ∥ Task 7 | Task 3 (frontend types come from the backend routes via `pnpm gen:api`) |
| 4 | Task 8 ∥ Task 10 | Task 8: Tasks 4, 5, 6. Task 10: Task 4 |
| 5 | Task 9 | Task 8 |
| 6 | Task 11 | Tasks 1–10 |

The replay applied the tasks in the order 1, 2, 3, 5, 6, 4, 7, 10, 8, 9, 11. Applying Task 10 before Task 8 checks that the two touch nothing in common.

## Running the e2e stack (Tasks 9 and 11)

From the worktree root, build and start a stack from the branch on its own port, then run Playwright against it:

```bash
VIEWER_PASSWORD=e2e-viewer ADMIN_PASSWORD=e2e-admin scripts/dev-secrets.sh   # once per worktree
E2E_PORT=18080 IMAGE_TAG=task14 docker compose -p task14 -f compose.yaml -f compose.test.yaml build
E2E_PORT=18080 IMAGE_TAG=task14 docker compose -p task14 -f compose.yaml -f compose.test.yaml up -d --wait
cd frontend && pnpm exec playwright install chromium
E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test <specs>
```

Afterwards, run `docker compose -p task14 -f compose.yaml -f compose.test.yaml down -v`.

---

### Task 1: Fist-bump store and rate limit

**Wave 1** · parallel with: Task 2, Task 5, Task 6 · branch `task/14-1-bump-store` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Create: `backend/migrations/versions/0006_fist_bumps.py`
- Create: `backend/src/sunday_clays/models/bumps.py`
- Modify: `backend/src/sunday_clays/models/__init__.py` (export `BumpAttempt`, `FistBump`)
- Create: `backend/src/sunday_clays/domain/bumps.py`
- Modify: `backend/src/sunday_clays/auth/ratelimit.py` (docstring; append the bump limit)
- Test: `backend/tests/integration/models/test_schema_0001.py` (C4 table set and the downgrade walk)
- Test: `backend/tests/integration/domain/test_bumps_store.py`
- Test: `backend/tests/integration/auth/test_bump_rate_limit.py`

**Interfaces:**
- Consumes:
  - `sunday_clays.models.base.Base`; `sunday_clays.domain.rebuild.LIVE_TABLES` and `rebuild_live(session)`; `sunday_clays.analytics.pipeline.run_pipeline(session)`.
  - Fixtures from `backend/tests/conftest.py`: `session`, `engine`, `committed_engine`, `fx_session`.
- Produces:
  - Tables `fist_bumps(post_key text, device_id uuid, created_at timestamptz default now(), PRIMARY KEY (post_key, device_id))` and `bump_attempts(id serial PK, ip text, at timestamptz default now())` with index `ix_bump_attempts_ip_at`. Alembic revision `"0006"` (down `"0005"`).
  - `sunday_clays.models.FistBump`, `sunday_clays.models.BumpAttempt`.
  - `sunday_clays.domain.bumps`: `BumpState(bumps: int, bumped: bool)`, `BumpTotal(post_key: str, bumps: int, last_at: datetime)` (frozen dataclasses); `add_bump(session: Session, post_key: str, device_id: uuid.UUID) -> None`; `remove_bump(session, post_key: str, device_id: uuid.UUID) -> None`; `bump_states(session, post_keys: Collection[str], device_id: uuid.UUID | None) -> dict[str, BumpState]` (every asked key, zero-filled); `bump_state(session, post_key: str, device_id: uuid.UUID | None) -> BumpState`; `wipe_bumps(session, post_key: str) -> int`; `bump_totals(session, limit: int) -> list[BumpTotal]` (most recently bumped first).
  - `sunday_clays.auth.ratelimit`: `BUMP_LIMIT: Final = 120`, `BUMP_WINDOW: Final = timedelta(minutes=10)`, `bumps_limited(session: Session, ip: str) -> bool`, `record_bump_action(session: Session, ip: str) -> None` (inserts and prunes rows older than the window, in the caller's transaction).

#### 1.1 Migration 0006 and the models

- [ ] **Step 1: Write the failing test**

Extend the C4 table set and walk the downgrade through 0006.

In `backend/tests/integration/models/test_schema_0001.py`, replace:

```python
    "insights",  # 0003 (Plan 12)
    "insight_picks",  # 0003 (Plan 12)
}
TABLES_0003 = {"insights", "insight_picks"}
```

with:

```python
    "insights",  # 0003 (Plan 12)
    "insight_picks",  # 0003 (Plan 12)
    "fist_bumps",  # 0006 (Plan 14)
    "bump_attempts",  # 0006 (Plan 14)
}
TABLES_0003 = {"insights", "insight_picks"}
TABLES_0006 = {"fist_bumps", "bump_attempts"}
```

In `backend/tests/integration/models/test_schema_0001.py`, replace:

```python
    assert _tables(scratch_engine) == C4_TABLES | {"alembic_version"}
    assert _round_id_index(scratch_engine) == ROUND_ID_INDEX_DEF
    _alembic(scratch_engine, "downgrade", "0004")  # 0005 drops the station labels
    _alembic(scratch_engine, "downgrade", "0003")  # 0004 is a data-only no-op
    _alembic(scratch_engine, "downgrade", "0002")  # 0003 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0001")  # 0002 drops only its index
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003) | {"alembic_version"}
    assert _round_id_index(scratch_engine) is None
    _alembic(scratch_engine, "downgrade", "base")
```

with:

```python
    assert _tables(scratch_engine) == C4_TABLES | {"alembic_version"}
    assert _round_id_index(scratch_engine) == ROUND_ID_INDEX_DEF
    _alembic(scratch_engine, "downgrade", "0005")  # 0006 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0006) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0004")  # 0005 drops the station labels
    _alembic(scratch_engine, "downgrade", "0003")  # 0004 is a data-only no-op
    _alembic(scratch_engine, "downgrade", "0002")  # 0003 drops only its two tables
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - TABLES_0006) | {"alembic_version"}
    _alembic(scratch_engine, "downgrade", "0001")  # 0002 drops only its index
    assert _tables(scratch_engine) == (C4_TABLES - TABLES_0003 - TABLES_0006) | {"alembic_version"}
    assert _round_id_index(scratch_engine) is None
    _alembic(scratch_engine, "downgrade", "base")
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`

Expected: FAIL: `test_upgrade_downgrade_roundtrip` (the migrated tables lack `fist_bumps` and `bump_attempts`).

- [ ] **Step 3: Write the implementation**

Create `backend/migrations/versions/0006_fist_bumps.py`:

```python
"""fist bumps: anonymous per-device bumps on Sunday Sheet posts, and their rate-limit log

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30

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
        sa.Column("post_key", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("post_key", "device_id", name=op.f("pk_fist_bumps")),
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
"""Fist bumps on Sunday Sheet posts and their rate-limit log (Plan 14); durable, never rebuilt."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import conv

from sunday_clays.models.base import Base


class FistBump(Base):
    """One anonymous bump: a post and the random id of the device that bumped it."""

    __tablename__ = "fist_bumps"

    post_key: Mapped[str] = mapped_column(Text, primary_key=True)
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

In `backend/src/sunday_clays/models/__init__.py`, replace:

```python
)
from sunday_clays.models.base import Base
from sunday_clays.models.identity import AuditLog, LoginAttempt, Rule, Shooter, ShooterAlias
from sunday_clays.models.insights import Insight, InsightPick
```

with:

```python
)
from sunday_clays.models.base import Base
from sunday_clays.models.bumps import BumpAttempt, FistBump
from sunday_clays.models.identity import AuditLog, LoginAttempt, Rule, Shooter, ShooterAlias
from sunday_clays.models.insights import Insight, InsightPick
```

In `backend/src/sunday_clays/models/__init__.py`, replace:

```python
    "AuditLog",
    "Base",
    "DataIssue",
    "Event",
    "EventMetric",
    "EventWeather",
    "ForecastCache",
    "Import",
```

with:

```python
    "AuditLog",
    "Base",
    "BumpAttempt",
    "DataIssue",
    "Event",
    "EventMetric",
    "EventWeather",
    "FistBump",
    "ForecastCache",
    "Import",
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/integration/models/test_schema_0001.py`

Expected: PASS (including `test_migration_matches_models` and `test_server_defaults_match_models`).

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add backend/tests/integration/models/test_schema_0001.py backend/migrations/versions/0006_fist_bumps.py backend/src/sunday_clays/models/bumps.py backend/src/sunday_clays/models/__init__.py
git commit -m "feat(sheet): fist_bumps and bump_attempts tables (migration 0006)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 1.2 The bump store

- [ ] **Step 6: Write the failing test**

Create `backend/tests/integration/domain/test_bumps_store.py`:

```python
"""Fist-bump store (Plan 14 Task 1): idempotent writes, per-device state, wipe and durability."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, insert
from sqlalchemy.orm import Session

from sunday_clays.analytics.pipeline import run_pipeline
from sunday_clays.domain.bumps import (
    BumpState,
    add_bump,
    bump_state,
    bump_states,
    bump_totals,
    remove_bump,
    wipe_bumps,
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
    session.execute(insert(FistBump).values(post_key="k1", device_id=A))
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


def test_wipe_removes_every_device_on_one_post_only(session: Session) -> None:
    add_bump(session, "k1", A)
    add_bump(session, "k1", B)
    add_bump(session, "k2", A)
    assert wipe_bumps(session, "k1") == 2
    assert wipe_bumps(session, "k1") == 0
    assert bump_states(session, ["k1", "k2"], None) == {
        "k1": BumpState(0, False),
        "k2": BumpState(1, False),
    }


def test_totals_list_the_most_recently_bumped_first(session: Session) -> None:
    now = datetime.now(UTC)
    session.execute(
        insert(FistBump),
        [
            {"post_key": "old", "device_id": A, "created_at": now - timedelta(days=2)},
            {"post_key": "new", "device_id": A, "created_at": now - timedelta(hours=1)},
            {"post_key": "new", "device_id": B, "created_at": now},
        ],
    )
    totals = bump_totals(session, 10)
    assert [(t.post_key, t.bumps) for t in totals] == [("new", 2), ("old", 1)]
    assert totals[0].last_at == now
    assert [t.post_key for t in bump_totals(session, 1)] == ["new"]


def test_bump_tables_are_not_live_tables() -> None:
    assert "fist_bumps" not in LIVE_TABLES
    assert "bump_attempts" not in LIVE_TABLES


def test_bumps_survive_a_rebuild_and_a_recompute(fx_session: Session) -> None:
    add_bump(fx_session, "k1", A)
    rebuild_live(fx_session)
    run_pipeline(fx_session)
    assert bump_state(fx_session, "k1", A) == BumpState(1, True)
```

- [ ] **Step 7: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_bumps_store.py`

Expected: ERROR at collection: `ModuleNotFoundError: No module named 'sunday_clays.domain.bumps'`.

- [ ] **Step 8: Write the implementation**

Create `backend/src/sunday_clays/domain/bumps.py`:

```python
"""Fist-bump store (Plan 14): one row per (post, device), so every write is idempotent.

Nothing here checks that a post exists: the API resolves a post key before it writes, and a bump
on a post that later disappears (a data correction) is kept but never counted on a Sheet.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sunday_clays.models import FistBump


@dataclass(frozen=True)
class BumpState:
    bumps: int
    bumped: bool


@dataclass(frozen=True)
class BumpTotal:
    post_key: str
    bumps: int
    last_at: datetime


def add_bump(session: Session, post_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: a repeat from the same device, even a concurrent one, changes nothing."""
    session.execute(
        pg_insert(FistBump)
        .values(post_key=post_key, device_id=device_id)
        .on_conflict_do_nothing(index_elements=[FistBump.post_key, FistBump.device_id])
    )


def remove_bump(session: Session, post_key: str, device_id: uuid.UUID) -> None:
    """Idempotent: taking back a bump that is not there changes nothing."""
    session.execute(
        delete(FistBump).where(FistBump.post_key == post_key, FistBump.device_id == device_id)
    )


def bump_states(
    session: Session, post_keys: Collection[str], device_id: uuid.UUID | None
) -> dict[str, BumpState]:
    """The count and "this device bumped it" for each key; a key nobody bumped is (0, False)."""
    keys = sorted(set(post_keys))
    if not keys:
        return {}
    counts = {
        str(key): int(n)
        for key, n in session.execute(
            select(FistBump.post_key, func.count())
            .where(FistBump.post_key.in_(keys))
            .group_by(FistBump.post_key)
        )
    }
    mine: set[str] = set()
    if device_id is not None:
        mine = set(
            session.scalars(
                select(FistBump.post_key).where(
                    FistBump.post_key.in_(keys), FistBump.device_id == device_id
                )
            )
        )
    return {key: BumpState(counts.get(key, 0), key in mine) for key in keys}


def bump_state(session: Session, post_key: str, device_id: uuid.UUID | None) -> BumpState:
    return bump_states(session, [post_key], device_id)[post_key]


def wipe_bumps(session: Session, post_key: str) -> int:
    """Delete every bump on one post; returns how many there were."""
    removed = session.scalars(
        delete(FistBump).where(FistBump.post_key == post_key).returning(FistBump.device_id)
    )
    return len(removed.all())


def bump_totals(session: Session, limit: int) -> list[BumpTotal]:
    """Bumped posts, most recently bumped first (ties by key), at most `limit` of them."""
    last = func.max(FistBump.created_at)
    rows = session.execute(
        select(FistBump.post_key, func.count(), last)
        .group_by(FistBump.post_key)
        .order_by(last.desc(), FistBump.post_key)
        .limit(limit)
    )
    return [BumpTotal(str(key), int(n), at) for key, n, at in rows]
```

- [ ] **Step 9: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/integration/domain/test_bumps_store.py`

Expected: 9 passed (the last one rebuilds and recomputes the fx world, so it takes a few seconds).

- [ ] **Step 10: Commit**

From the worktree root:

```bash
git add backend/tests/integration/domain/test_bumps_store.py backend/src/sunday_clays/domain/bumps.py
git commit -m "feat(sheet): idempotent fist-bump store" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 1.3 The bump rate limit

- [ ] **Step 11: Write the failing test**

Create `backend/tests/integration/auth/test_bump_rate_limit.py`:

```python
"""Bump rate limit (Plan 14 Task 1): 120 actions per client IP per 10 minutes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import (
    BUMP_LIMIT,
    BUMP_WINDOW,
    bumps_limited,
    record_bump_action,
)
from sunday_clays.models import Base

ATTEMPTS = Base.metadata.tables["bump_attempts"]


def _actions(session: Session, ip: str, n: int, *, age: timedelta = timedelta(0)) -> None:
    at = datetime.now(UTC) - age
    session.execute(insert(ATTEMPTS), [{"ip": ip, "at": at}] * n)


def test_the_limit_is_120_actions_in_10_minutes() -> None:
    assert BUMP_LIMIT == 120
    assert timedelta(minutes=10) == BUMP_WINDOW


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

- [ ] **Step 12: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/integration/auth/test_bump_rate_limit.py`

Expected: ERROR at collection: `ImportError: cannot import name 'BUMP_LIMIT' from 'sunday_clays.auth.ratelimit'`.

- [ ] **Step 13: Write the implementation**

In `backend/src/sunday_clays/auth/ratelimit.py`, replace:

```python
"""Failed-login rate limit per client-IP bucket, stored in ``login_attempts`` (C4, C8)."""

from datetime import UTC, datetime, timedelta
```

with:

```python
"""Rate limits per client-IP bucket: failed logins (``login_attempts``, C4, C8) and fist bumps
(``bump_attempts``, Plan 14)."""

from datetime import UTC, datetime, timedelta
```

In `backend/src/sunday_clays/auth/ratelimit.py`, replace:

```python
    session.execute(insert(t).values(ip=ip, at=now, success=success))
    session.execute(delete(t).where(t.c.at < now - PRUNE_AFTER))
```

with:

```python
    session.execute(insert(t).values(ip=ip, at=now, success=success))
    session.execute(delete(t).where(t.c.at < now - PRUNE_AFTER))


# --- Plan 14: fist bumps -------------------------------------------------------------------------
BUMP_LIMIT: Final = 120
BUMP_WINDOW: Final = timedelta(minutes=10)


def _bump_attempts() -> Table:
    return Base.metadata.tables["bump_attempts"]


def bumps_limited(session: Session, ip: str) -> bool:
    """True when ``ip`` already made ``BUMP_LIMIT`` bump actions in the last ``BUMP_WINDOW``."""
    t = _bump_attempts()
    since = datetime.now(UTC) - BUMP_WINDOW
    actions = session.scalar(
        select(func.count()).select_from(t).where(t.c.ip == ip, t.c.at > since)
    )
    return (actions or 0) >= BUMP_LIMIT


def record_bump_action(session: Session, ip: str) -> None:
    """Insert one action and prune rows outside the window, inside the caller's transaction."""
    t = _bump_attempts()
    now = datetime.now(UTC)
    session.execute(insert(t).values(ip=ip, at=now))
    session.execute(delete(t).where(t.c.at < now - BUMP_WINDOW))
```

- [ ] **Step 14: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/integration/auth/test_bump_rate_limit.py tests/integration/auth/test_login_rate_limit.py`

Expected: all pass (the login limiter is untouched).

- [ ] **Step 15: Commit**

From the worktree root:

```bash
git add backend/tests/integration/auth/test_bump_rate_limit.py backend/src/sunday_clays/auth/ratelimit.py
git commit -m "feat(sheet): 120 bump actions per IP per 10 minutes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 1.4 Gates

- [ ] **Step 16: Run the gates before handing the branch back**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src`

Expected: all three pass ("All checks passed!", "N files already formatted", "Success: no issues found")

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 2: Sheet assembler and read API

**Wave 1** · parallel with: Task 1, Task 5, Task 6 · branch `task/14-2-sheet-api` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Create: `backend/src/sunday_clays/analytics/sheet.py`
- Create: `backend/src/sunday_clays/api/routes/sheet.py`
- Test: `backend/tests/unit/analytics/test_sheet_assembly.py`
- Test: `backend/tests/integration/api/test_sheet_api.py`

**Interfaces:**
- Consumes:
  - Insights (Plan 12): `analytics.insights.select.supersede`, `select.PINNED_HOME`; `analytics.insights.rank.recency(anchor, ref, held) -> float`; `analytics.insights.store.InsightRow`, `load_rows(session, *where)`, `load_picks(session, sunday)`, `insights_table()`, `get_new_since(session)`; `analytics.insights.picks.picked(rows, picks, day) -> (hero, spotlight)`; `analytics.insights.templates.Segment`, `fmt_full_date`, `fmt_int`, `natural_name`; `analytics.insights.lints.lint_segments` (tests).
  - `api.routes.insights`: `InsightOut`, `InsightChartOut`, `InsightSegmentOut`, `held_dates(session) -> list[date]`, `insight_out(row, new_since) -> InsightOut`, `supersedes_of(kind) -> frozenset[str]`.
  - `analytics.yir.OnThisDayItem`, `Winner`, `on_this_day(frames, day)`, `load_yir_frames(session)`; `analytics.achievements.registry.trophies()`, `Metal`; `analytics.frames.load_events(session)`; `api.routes._convert.rows`, `opt_float`, `opt_int`; `analytics.cache.cached_by_data_version`; `analytics.pipeline.get_data_version`.
  - Fixtures: `fx_viewer_client`, `fx_session`, `viewer_client`, `session`.
- Produces:
  - `sunday_clays.analytics.sheet`: `PostType = Literal["milestone","improvement","trophy","conditions","welcome","on_this_day","other"]`; `FEED_CAP = 10`, `MAX_RUN = 2`, `TROPHY_SCORE = 18.0`, `OTD_SCORE = 9.0`, `KIND_TYPES: Mapping[str, PostType]`, `FRESH_EVERGREEN: Mapping[str, str]` (kind → its date param: `pf.season-best`/`pf.up-on-usual`/`pf.year-up` → `"day"`, `pf.hot-form` → `"last"`), `FEED_TYPES`, `FAMILY_LABELS`; frozen dataclasses `Award(shooter_id, display_name, code)`, `TrophyInfo(code, title, art_key, metal: str | None)`, `TrophyPost(code, title, art_key, metal, holders: tuple[tuple[int, str], ...])`, `Post(post_key, type, family, score, headline: tuple[Segment, ...], named_shooter_ids, row: InsightRow | None, trophy: TrophyPost | None, on_this_day: OnThisDayItem | None)`, `MoreGroup(family, label, posts)`, `Issue(day, number, previous, next, latest, headline, recap, spotlight, feed, more)` with `.posts` and `.post_keys: frozenset[str]`; `post_type(kind) -> PostType`, `names_ok(row) -> bool`, `fresh_on(row, day) -> bool`, `trophy_key(code, day)`, `otd_key(day, years_ago)`, `synthetic_key_date(post_key) -> date | None`, `name_list(people, shown=3) -> list[Segment]`, `trophy_headline`, `otd_headline` (attendance-only look-backs read "… 18 shooters came out (attendance only)."), `insight_pool` (latest issue: Home's evergreen rows and `fresh_on` rows), `insight_posts`, `trophy_posts`, `otd_posts` (every look-back, with or without scores), `ranked`, `interleave(posts, cap=FEED_CAP, max_run=MAX_RUN) -> (feed, rest)` (the best post of every feed type present first, then by score to the cap, then ordered so no type runs more than `max_run` while another chosen type is left), `group_more(rest) -> list[MoreGroup]`, `assemble(day, held, rows, *, hero, spotlight, awards, catalog, on_this_day, supersedes) -> Issue`.
  - `sunday_clays.api.routes.sheet`: response models `SheetOut{data_version, masthead: SheetMastheadOut{date, issue, previous, next, latest, newer: NewerSundayOut{date, has_scores, head_count: int | None, n_shooters} | None}, numbers: SheetNumbersOut{shooters, median, top_score, trophies}, headline: InsightOut | None, recap, spotlight, posts: list[SheetPostOut], more: list[SheetMoreGroupOut{family, label, posts}]}`; `SheetPostOut{post_key, type, family, headline: list[InsightSegmentOut], named_shooter_ids, see_why: SeeWhyOut{kind: "chart"|"link", label, chart: InsightChartOut | None, href: str | None}, insight: InsightOut | None, trophy: SheetTrophyOut{code, title, art_key, metal, holders: list[SheetShooterOut{shooter_id, name}]} | None, on_this_day: SheetOnThisDayOut{years_ago, event_date, n_shooters, top_score} | None}`.
  - Same module, functions: `trophy_catalog() -> dict[str, sheet.TrophyInfo]`; `build_issue(session, day: date) -> sheet.Issue` (cached by data_version); `sheet_body(session, day) -> SheetOut` (cached); `newer_sunday(session, issue: sheet.Issue) -> NewerSundayOut | None` (the newest Sunday when it is after the latest issue; None on past issues); `see_why(post) -> SeeWhyOut`; `post_issue_date(session, post_key) -> date | None`; `resolves(session, post_key) -> bool`; `held_or_404(session, day) -> None`. Routes: `GET /api/sheet/latest`, `GET /api/sheet/{date}`, both 404 `sheet_not_found`.

#### 2.1 The pure assembler

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/analytics/test_sheet_assembly.py`:

```python
"""The Sunday Sheet assembler (Plan 14 Task 2), on synthetic rows: pure, no database."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sunday_clays.analytics import sheet
from sunday_clays.analytics.insights.lints import lint_segments
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.yir import OnThisDayItem, Winner

DAY = date(2026, 9, 27)
HELD = [date(2026, 9, 13), date(2026, 9, 20), DAY]
CATALOG = {
    "first_win": sheet.TrophyInfo("first_win", "First win", "first_win", None),
    "round_score:4": sheet.TrophyInfo("round_score:4", "Round score — 45", "round_score", "gold"),
}


def no_supersedes(_kind: str) -> frozenset[str]:
    return frozenset()


def row(key: str, kind: str = "pf.pb", **overrides: Any) -> InsightRow:
    values: dict[str, Any] = {
        "key": key,
        "value_hash": "h",
        "generation": 1,
        "first_generation": 1,
        "kind": kind,
        "family": "milestone",
        "home_slot": None,
        "subject_type": "shooter",
        "subject_id": "3",
        "anchor_date": DAY,
        "variant": "default",
        "pages": ("home", "profile", "sunday"),
        "expires": {},
        "named_shooter_ids": (3,),
        "polarity": "positive",
        "kudos": False,
        "template_id": "t",
        "params": {},
        "strength": 1.0,
        "base_score": 10.0,
        "rank_score": 15.0,
        "headline": [{"t": "text", "v": f"Story {key}."}],
        "headline_you": None,
        "how": [],
        "how_you": None,
        "chart": {
            "type": "page",
            "label": "x",
            "window": {"from": "2026-09-01", "to": "2026-09-27"},
        },
    }
    values.update(overrides)
    return InsightRow(**values)


def post(key: str, type_: sheet.PostType, score: float) -> sheet.Post:
    return sheet.Post(key, type_, "form", score, (), ())


def assemble(rows: list[InsightRow], day: date = DAY, **kw: Any) -> sheet.Issue:
    args: dict[str, Any] = {
        "hero": None,
        "spotlight": None,
        "awards": [],
        "catalog": CATALOG,
        "on_this_day": [],
        "supersedes": no_supersedes,
    }
    args.update(kw)
    return sheet.assemble(day, HELD, rows, **args)


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        *[(k, "milestone") for k in sheet._MILESTONE],
        ("rec.drought-clock", "milestone"),
        ("rec.anything-new", "milestone"),
        *[(k, "improvement") for k in sheet._IMPROVEMENT],
        *[(k, "conditions") for k in sheet._CONDITIONS],
        *[(k, "welcome") for k in sheet._WELCOME],
        ("pf.best-stretch", "other"),
        ("ev.close-finish", "other"),
        ("no.such-kind", "other"),
    ],
)
def test_every_spec_kind_maps_to_its_post_type(kind: str, expected: str) -> None:
    assert sheet.post_type(kind) == expected


SPEC_KINDS = {
    "milestone": {
        "pf.pb", "pf.season-best", "pf.career-first", "pf.first-since", "pf.sunday-milestone",
        "pf.targets-milestone", "pf.average-milestone", "pf.first-tier",
        "pf.shooter-anniversary", "ev.top-score",
    },
    "improvement": {
        "pf.hot-form", "pf.rank-climb", "pf.up-on-usual", "pf.beat-own-usual",
        "pf.three-rising", "pf.year-up", "lb.most-improved", "lb.biggest-climb",
    },
    "conditions": {"ev.how-it-played", "ev.toughest-since", "ev.rain-day", "ev.week-jump"},
    "welcome": {"ev.new-faces", "ev.second-visit", "pf.back-strong"},
}  # fmt: skip


def test_the_spec_tables_kinds_are_all_mapped() -> None:
    """The spec's Posts table, written out: a typo in a kind id fails here."""
    expected = {kind: type_ for type_, kinds in SPEC_KINDS.items() for kind in kinds}
    assert dict(sheet.KIND_TYPES) == expected
    assert len(expected) == 25


def test_posts_are_the_sundays_anchored_rows_ranked_with_its_recency() -> None:
    issue = assemble(
        [
            row("a", base_score=10.0),
            row("b", base_score=20.0),
            row("old", anchor_date=date(2026, 9, 20)),
            row("profile-only", anchor_date=None, pages=("profile",)),
        ]
    )
    assert [p.post_key for p in issue.posts] == ["b", "a"]
    assert [p.score for p in issue.posts] == [30.0, 15.0]


def test_the_latest_issue_adds_homes_evergreen_rows_only() -> None:
    rows = [
        row("a"),
        row(
            "home-ever",
            "cl.turnout-trend",
            anchor_date=None,
            family="turnout",
            named_shooter_ids=(),
        ),
        row("profile-ever", "pf.hot-form", anchor_date=None, pages=("profile",)),
    ]
    assert assemble(rows).post_keys == {"a", "home-ever"}
    past = assemble(
        [replace(r, anchor_date=date(2026, 9, 20)) if r.key == "a" else r for r in rows],
        day=date(2026, 9, 20),
    )
    assert past.post_keys == {"a"}


@pytest.mark.parametrize(("kind", "param"), sorted(sheet.FRESH_EVERGREEN.items()))
def test_profile_only_spec_kinds_post_on_the_latest_issue_when_about_that_sunday(
    kind: str, param: str
) -> None:
    def ever(key: str, day: date) -> InsightRow:
        return row(key, kind, anchor_date=None, pages=("profile",), params={param: day.isoformat()})

    rows = [ever("fresh", DAY), ever("stale", date(2026, 9, 20))]
    issue = assemble(rows)
    assert issue.post_keys == {"fresh"}
    assert issue.posts[0].type == sheet.post_type(kind)
    assert assemble(rows, day=date(2026, 9, 20)).post_keys == set()  # past issues: never


def test_named_posts_are_positive_or_neutral_only() -> None:
    issue = assemble(
        [
            row("pos"),
            row("neu", polarity="neutral"),
            row("mixed-named", "ev.rain-day", polarity="mixed"),
            row("mixed-unnamed", "ev.rain-day", polarity="mixed", named_shooter_ids=()),
            row("field", "ev.how-it-played", polarity="field_negative", named_shooter_ids=()),
        ]
    )
    assert issue.post_keys == {"pos", "neu", "mixed-unnamed", "field"}
    for p in issue.posts:
        assert p.row is not None
        assert not p.named_shooter_ids or p.row.polarity in {"positive", "neutral"}


def test_a_named_negative_pick_never_leads() -> None:
    bad = row("bad", polarity="mixed")
    issue = assemble([bad], hero=bad, spotlight=bad)
    assert issue.headline is None
    assert issue.spotlight is None


def test_the_recap_is_the_deck_and_the_picks_lead_instead_of_posting() -> None:
    recap = row("recap", "home.sunday-recap", polarity="mixed", named_shooter_ids=())
    hero, spot, other = row("hero"), row("spot"), row("other")
    issue = assemble([recap, hero, spot, other], hero=hero, spotlight=spot)
    assert issue.recap == recap
    assert (issue.headline, issue.spotlight) == (hero, spot)
    assert issue.post_keys == {"other"}


def test_superseded_rows_are_dropped() -> None:
    first = row("first-tier", "pf.first-tier", base_score=30.0)
    pb = row("pb")

    def supersedes(kind: str) -> frozenset[str]:
        return frozenset({"pf.first-tier"}) if kind == "pf.pb" else frozenset()

    assert assemble([first, pb], supersedes=supersedes).post_keys == {"pb"}


def test_one_trophy_post_per_trophy_names_everyone_who_earned_it() -> None:
    awards = [
        sheet.Award(2, "Bee, Bob", "first_win"),
        sheet.Award(1, "Ace, Amy", "first_win"),
        sheet.Award(3, "Hadley, Ike", "round_score:4"),
        sheet.Award(4, "Cy, Cal", "retired_trophy"),  # not in the catalog: skipped
    ]
    issue = assemble([], awards=awards)
    trophies = {p.post_key: p for p in issue.posts}
    assert set(trophies) == {"trophy:first_win:2026-09-27", "trophy:round_score:4:2026-09-27"}
    win = trophies["trophy:first_win:2026-09-27"]
    assert win.trophy is not None
    assert win.trophy.holders == ((1, "Amy Ace"), (2, "Bob Bee"))
    assert win.named_shooter_ids == (1, 2)
    assert "".join(s["v"] for s in win.headline) == "First win unlocked by Amy Ace and Bob Bee."
    assert trophies["trophy:round_score:4:2026-09-27"].trophy == sheet.TrophyPost(
        "round_score:4", "Round score — 45", "round_score", "gold", ((3, "Ike Hadley"),)
    )


def test_name_lists_join_with_commas_and_and_then_count_the_rest() -> None:
    people = [(1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "E")]

    def text(n: int) -> str:
        return "".join(s["v"] for s in sheet.name_list(people[:n]))

    assert [text(n) for n in range(1, 6)] == [
        "A",
        "A and B",
        "A, B and C",
        "A, B, C and 1 more",
        "A, B, C and 2 more",
    ]


def otd(
    years: int,
    *,
    has_scores: bool = True,
    winners: tuple[Winner, ...] = (),
    top_score: int | None = 48,
) -> OnThisDayItem:
    return OnThisDayItem(
        years_ago=years,
        event_date=date(2026 - years, 9, 28),
        has_scores=has_scores,
        head_count=None,
        n_shooters=31 if years != 3 else 1,
        top_score=top_score,
        median=40.0,
        winners=winners,
    )


def test_on_this_day_posts_name_the_top_score_and_keep_attendance_only_sundays() -> None:
    items = [
        otd(1, winners=(Winner(1, "Ace, Amy", 48),)),
        replace(otd(2, has_scores=False, top_score=None), head_count=18),
        otd(3),
    ]
    issue = assemble([], on_this_day=items)
    by_key = {p.post_key: p for p in issue.posts}
    assert set(by_key) == {"otd:2026-09-27:1", "otd:2026-09-27:2", "otd:2026-09-27:3"}
    assert "".join(s["v"] for s in by_key["otd:2026-09-27:2"].headline) == (
        "Two years ago, on Sep 28, 2024, 18 shooters came out (attendance only)."
    )
    assert by_key["otd:2026-09-27:2"].named_shooter_ids == ()
    one_head = sheet.otd_posts([replace(otd(2, has_scores=False), head_count=1)], DAY)[0]
    assert "".join(s["v"] for s in one_head.headline).endswith(
        " 1 shooter came out (attendance only)."
    )
    no_count = sheet.otd_posts([otd(2, has_scores=False)], DAY)[0]
    assert "".join(s["v"] for s in no_count.headline) == (
        "Two years ago, on Sep 28, 2024, a Sunday was shot; no scores were recorded."
    )
    one = by_key["otd:2026-09-27:1"]
    assert "".join(s["v"] for s in one.headline) == (
        "One year ago, on Sep 28, 2025, 31 shooters came out; "
        "the top score of 48 was shot by Amy Ace."
    )
    assert one.named_shooter_ids == (1,)
    three = by_key["otd:2026-09-27:3"]
    assert "".join(s["v"] for s in three.headline) == (
        "Three years ago, on Sep 28, 2023, 1 shooter came out and the top score was 48."
    )
    no_top = sheet.otd_posts([otd(2, top_score=None)], DAY)[0]
    assert "".join(s["v"] for s in no_top.headline) == (
        "Two years ago, on Sep 28, 2024, 31 shooters came out."
    )


def test_trophy_and_on_this_day_headlines_pass_the_insight_lints() -> None:
    issue = assemble(
        [],
        awards=[sheet.Award(1, "Ace, Amy", "first_win"), sheet.Award(2, "Bee, Bob", "first_win")],
        on_this_day=[
            otd(1, winners=(Winner(1, "Ace, Amy", 48), Winner(2, "Bee, Bob", 48))),
            replace(otd(2, has_scores=False), head_count=18),
            otd(3, has_scores=False),
        ],
    )
    assert len(issue.posts) == 4
    for p in issue.posts:
        assert lint_segments(p.headline) == []


def test_the_feed_interleaves_types_and_caps_at_ten() -> None:
    posts = [
        *[post(f"m{i}", "milestone", 100 - i) for i in range(8)],
        post("t0", "trophy", 50),
        post("w0", "welcome", 40),
        *[post(f"o{i}", "other", 200 - i) for i in range(3)],
    ]
    feed, rest = sheet.interleave(sheet.ranked(posts))
    assert [p.post_key for p in feed] == [
        "m0", "m1", "t0", "m2", "m3", "w0", "m4", "m5", "m6", "m7",
    ]  # fmt: skip
    assert [p.post_key for p in rest] == ["o0", "o1", "o2"]


@given(
    st.lists(
        st.tuples(st.sampled_from(sorted(sheet.FEED_TYPES | {"other"})), st.integers(0, 50)),
        max_size=30,
    )
)
def test_interleave_never_runs_a_type_three_times_while_another_is_left(
    spec: list[tuple[sheet.PostType, int]],
) -> None:
    posts = sheet.ranked(post(f"p{i}", t, float(s)) for i, (t, s) in enumerate(spec))
    feed, rest = sheet.interleave(posts)
    eligible = [p for p in posts if p.type in sheet.FEED_TYPES]
    assert len(feed) == min(sheet.FEED_CAP, len(eligible))
    assert {p.type for p in feed} == {p.type for p in eligible}  # every type present posts
    assert sorted(p.post_key for p in feed + rest) == sorted(p.post_key for p in posts)
    assert rest == [p for p in posts if p not in feed]
    for i in range(sheet.MAX_RUN, len(feed)):
        window = {p.type for p in feed[i - sheet.MAX_RUN : i + 1]}
        if len(window) == 1:  # a third in a row: only when nothing else chosen was left
            assert {p.type for p in feed[i:]} == window


def test_the_feed_has_one_post_of_every_type_the_issue_has() -> None:
    """A lopsided Sunday: twelve strong milestones cannot push out the one trophy, look-back or
    welcome, however low they score."""
    posts = sheet.ranked(
        [
            *[post(f"m{i:02}", "milestone", 100 - i) for i in range(12)],
            post("t0", "trophy", sheet.TROPHY_SCORE),
            post("d0", "on_this_day", sheet.OTD_SCORE),
            post("w0", "welcome", 1.0),
        ]
    )
    feed, rest = sheet.interleave(posts)
    assert len(feed) == sheet.FEED_CAP
    assert [p.post_key for p in feed] == [
        "m00", "m01", "t0", "m02", "m03", "d0", "m04", "m05", "w0", "m06",
    ]  # fmt: skip
    assert [p.post_key for p in rest] == [f"m{i:02}" for i in range(7, 12)]


def test_a_thin_sunday_puts_every_post_in_the_feed() -> None:
    issue = assemble(
        [row("a")],
        awards=[sheet.Award(1, "Ace, Amy", "first_win")],
        on_this_day=[otd(1)],
    )
    assert {p.type for p in issue.feed} == {"milestone", "trophy", "on_this_day"}
    assert issue.more == ()


def test_more_groups_by_family_in_rank_order() -> None:
    rows = [row(f"m{i}", base_score=50 - i) for i in range(11)]
    rows += [
        row("s1", "pf.podium-run", family="streak", base_score=60.0),
        row("s2", "pf.tier-run", family="streak", base_score=1.0),
        row("x", "pf.wins", family="mystery", base_score=2.0),
    ]
    issue = assemble(rows)
    assert len(issue.feed) == 10
    assert [(g.family, g.label, [p.post_key for p in g.posts]) for g in issue.more] == [
        ("streak", "Streaks", ["s1", "s2"]),
        ("milestone", "Milestones", ["m10"]),
        ("mystery", "Mystery", ["x"]),
    ]


def test_issue_numbers_and_neighbours() -> None:
    first = assemble([], day=HELD[0])
    assert (first.number, first.previous, first.next, first.latest) == (1, None, HELD[1], False)
    last = assemble([])
    assert (last.number, last.previous, last.next, last.latest) == (3, HELD[1], None, True)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("trophy:first_win:2026-09-27", DAY),
        ("trophy:round_score:4:2026-09-27", DAY),
        ("otd:2026-09-27:2", DAY),
        ("trophy:first_win:nonsense", None),
        ("otd:", None),
        ("otd:2026-13-01:1", None),
        ("0123456789abcdef0123", None),
    ],
)
def test_synthetic_keys_name_their_issue(key: str, expected: date | None) -> None:
    assert sheet.synthetic_key_date(key) == expected
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/unit/analytics/test_sheet_assembly.py`

Expected: ERROR at collection: `ImportError: cannot import name 'sheet' from 'sunday_clays.analytics'`.

- [ ] **Step 3: Write the implementation**

Create `backend/src/sunday_clays/analytics/sheet.py`:

```python
"""The Sunday Sheet (Plan 14): one issue per held Sunday, assembled from stored rows. Pure.

An issue's posts are the insights anchored on its Sunday (on the latest issue also Home's
evergreen rows and the profile-only rows that are news that Sunday, FRESH_EVERGREEN), one post per
trophy earned that day and the "On this day" look-backs. The feed takes the best post of every
feed type the issue has, fills up to FEED_CAP by score, and is interleaved so that no type runs
more than MAX_RUN in a row while another type is left. Everything else is "More from this
Sunday", grouped by family. The hero and spotlight picks lead the issue instead of being posts, and
Home's pinned recap is the headline's deck.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from sunday_clays.analytics.insights import select as sel
from sunday_clays.analytics.insights.rank import recency
from sunday_clays.analytics.insights.store import InsightRow
from sunday_clays.analytics.insights.templates import (
    Segment,
    fmt_full_date,
    fmt_int,
    natural_name,
)
from sunday_clays.analytics.yir import OnThisDayItem

PostType = Literal[
    "milestone", "improvement", "trophy", "conditions", "welcome", "on_this_day", "other"
]

FEED_CAP: Final = 10
MAX_RUN: Final = 2
NAMES_SHOWN: Final = 3
# Measured on the fx world: an anchored insight's base score is 8.7 / 12.5 / 18 / 24 at the
# 25th / 50th / 75th / 90th percentile, and the Sheet ranks anchored rows at base x 1.5.
TROPHY_SCORE: Final = 18.0  # a fresh trophy ranks with a median anchored story (12 x 1.5)
OTD_SCORE: Final = 9.0  # a look-back ranks with a light one (6 x 1.5)
NAMED_POLARITIES: Final = frozenset({"positive", "neutral"})

_MILESTONE: Final = (
    "pf.pb",
    "pf.season-best",
    "pf.career-first",
    "pf.first-since",
    "pf.sunday-milestone",
    "pf.targets-milestone",
    "pf.average-milestone",
    "pf.first-tier",
    "pf.shooter-anniversary",
    "ev.top-score",
)
_IMPROVEMENT: Final = (
    "pf.hot-form",
    "pf.rank-climb",
    "pf.up-on-usual",
    "pf.beat-own-usual",
    "pf.three-rising",
    "pf.year-up",
    "lb.most-improved",
    "lb.biggest-climb",
)
_CONDITIONS: Final = ("ev.how-it-played", "ev.toughest-since", "ev.rain-day", "ev.week-jump")
_WELCOME: Final = ("ev.new-faces", "ev.second-visit", "pf.back-strong")
KIND_TYPES: Final[Mapping[str, PostType]] = {
    **dict.fromkeys(_MILESTONE, "milestone"),
    **dict.fromkeys(_IMPROVEMENT, "improvement"),
    **dict.fromkeys(_CONDITIONS, "conditions"),
    **dict.fromkeys(_WELCOME, "welcome"),
}
# Profile-only evergreen kinds the spec lists as feed sources. On the latest issue a row posts when
# its date param (the Sunday it is about) is the issue Sunday, so it is news that Sunday.
FRESH_EVERGREEN: Final[Mapping[str, str]] = {
    "pf.season-best": "day",
    "pf.hot-form": "last",
    "pf.up-on-usual": "day",
    "pf.year-up": "day",
}
FEED_TYPES: Final[frozenset[PostType]] = frozenset(
    {"milestone", "improvement", "trophy", "conditions", "welcome", "on_this_day"}
)
FAMILY_LABELS: Final[Mapping[str, str]] = {
    "form": "Form",
    "streak": "Streaks",
    "milestone": "Milestones",
    "race": "The race",
    "record": "Records",
    "weather": "Weather and the day",
    "turnout": "Turnout",
    "newcomer": "New faces",
    "station": "Stations",
    "trophy": "Trophies",
    "recap": "Recaps",
    "on_this_day": "On this day",
}
_YEARS_AGO: Final[Mapping[int, str]] = {1: "One year", 2: "Two years", 3: "Three years"}


@dataclass(frozen=True)
class Award:
    """One trophy earned on the issue's Sunday (an `achievements_awarded` row with its name)."""

    shooter_id: int
    display_name: str
    code: str


@dataclass(frozen=True)
class TrophyInfo:
    """A trophy's catalog entry: `title` is "Name — Tier" as the Trophy Room writes it."""

    code: str
    title: str
    art_key: str
    metal: str | None


@dataclass(frozen=True)
class TrophyPost:
    code: str
    title: str
    art_key: str
    metal: str | None
    holders: tuple[tuple[int, str], ...]  # (shooter_id, "First Last"), by name


@dataclass(frozen=True)
class Post:
    post_key: str
    type: PostType
    family: str
    score: float
    headline: tuple[Segment, ...]
    named_shooter_ids: tuple[int, ...]
    row: InsightRow | None = None
    trophy: TrophyPost | None = None
    on_this_day: OnThisDayItem | None = None


@dataclass(frozen=True)
class MoreGroup:
    family: str
    label: str
    posts: tuple[Post, ...]


@dataclass(frozen=True)
class Issue:
    day: date
    number: int  # held Sundays up to and including this one
    previous: date | None
    next: date | None
    latest: bool
    headline: InsightRow | None
    recap: InsightRow | None
    spotlight: InsightRow | None
    feed: tuple[Post, ...]
    more: tuple[MoreGroup, ...]

    @property
    def posts(self) -> tuple[Post, ...]:
        return self.feed + tuple(p for group in self.more for p in group.posts)

    @property
    def post_keys(self) -> frozenset[str]:
        return frozenset(p.post_key for p in self.posts)


def post_type(kind: str) -> PostType:
    if kind.startswith("rec."):
        return "milestone"
    return KIND_TYPES.get(kind, "other")


def names_ok(row: InsightRow) -> bool:
    """Owner rule: a post that names a shooter is positive or neutral."""
    return not row.named_shooter_ids or row.polarity in NAMED_POLARITIES


def fresh_on(row: InsightRow, day: date) -> bool:
    """True for a FRESH_EVERGREEN row whose date param is `day`."""
    param = FRESH_EVERGREEN.get(row.kind)
    return param is not None and str(row.params.get(param)) == day.isoformat()


def trophy_key(code: str, day: date) -> str:
    return f"trophy:{code}:{day.isoformat()}"


def otd_key(day: date, years_ago: int) -> str:
    return f"otd:{day.isoformat()}:{years_ago}"


def synthetic_key_date(post_key: str) -> date | None:
    """The issue date a trophy or "On this day" key names; None for any other key."""
    try:
        if post_key.startswith("trophy:"):
            return date.fromisoformat(post_key.rsplit(":", 1)[1])
        if post_key.startswith("otd:"):
            return date.fromisoformat(post_key.split(":")[1])
    except (ValueError, IndexError):
        return None
    return None


def name_list(people: Sequence[tuple[int, str]], shown: int = NAMES_SHOWN) -> list[Segment]:
    """Names as "A", "A and B", "A, B and C" or "A, B, C and 2 more".

    Only ", " and " and " ever sit between two names (D9).
    """
    head = list(people[:shown])
    rest = len(people) - len(head)
    out: list[Segment] = []
    for i, (sid, name) in enumerate(head):
        if i > 0:
            last = i == len(head) - 1 and rest == 0
            out.append({"t": "text", "v": " and " if last else ", "})
        out.append({"t": "shooter", "v": name, "id": sid})
    if rest > 0:
        out.append({"t": "text", "v": f" and {rest} more"})
    return out


def trophy_headline(trophy: TrophyPost) -> list[Segment]:
    return [
        {"t": "trophy", "v": trophy.title},
        {"t": "text", "v": " unlocked by "},
        *name_list(trophy.holders),
        {"t": "text", "v": "."},
    ]


def otd_headline(item: OnThisDayItem) -> list[Segment]:
    """Reads "One year ago, on Sep 28, 2025, 31 shooters came out; the top score of 48 was shot
    by Amy Ace." Winners are named only beside the top score: positive, never against anyone. A
    Sunday without scores reads "... 18 shooters came out (attendance only)." as Home's card did."""
    ago = _YEARS_AGO.get(item.years_ago, f"{item.years_ago} years")
    out: list[Segment] = [
        {"t": "text", "v": f"{ago} ago, on "},
        {"t": "date", "v": fmt_full_date(item.event_date)},
    ]
    if not item.has_scores:
        if item.head_count is None:
            out.append({"t": "text", "v": ", a Sunday was shot; no scores were recorded."})
            return out
        noun = "shooter" if item.head_count == 1 else "shooters"
        out += [
            {"t": "text", "v": ", "},
            {"t": "num", "v": fmt_int(item.head_count)},
            {"t": "text", "v": f" {noun} came out (attendance only)."},
        ]
        return out
    noun = "shooter" if item.n_shooters == 1 else "shooters"
    out += [
        {"t": "text", "v": ", "},
        {"t": "num", "v": fmt_int(item.n_shooters)},
        {"t": "text", "v": f" {noun} came out"},
    ]
    if item.top_score is not None and item.winners:
        winners = [(w.shooter_id, natural_name(w.display_name)) for w in item.winners]
        out += [
            {"t": "text", "v": "; the top score of "},
            {"t": "num", "v": str(item.top_score)},
            {"t": "text", "v": " was shot by "},
            *name_list(winners),
        ]
    elif item.top_score is not None:
        out += [
            {"t": "text", "v": " and the top score was "},
            {"t": "num", "v": str(item.top_score)},
        ]
    out.append({"t": "text", "v": "."})
    return out


def insight_pool(
    rows: Iterable[InsightRow],
    day: date,
    *,
    latest: bool,
    supersedes: Callable[[str], frozenset[str]],
    exclude: frozenset[str],
) -> list[InsightRow]:
    """The issue's insight posts: rows anchored on `day`, plus (latest issue) Home's evergreen rows
    and the FRESH_EVERGREEN rows about `day`; never the recap, a negative named row, a superseded
    row or an `exclude` key."""
    candidates = [
        r
        for r in rows
        if (
            r.anchor_date == day
            or (latest and r.anchor_date is None and ("home" in r.pages or fresh_on(r, day)))
        )
        and r.kind != sel.PINNED_HOME
        and names_ok(r)
    ]
    return [r for r in sel.supersede(candidates, supersedes) if r.key not in exclude]


def insight_posts(pool: Iterable[InsightRow], day: date, held: Sequence[date]) -> list[Post]:
    """Ranked as on the Sunday page: base score x recency (1.5 for the issue's own Sunday)."""
    return [
        Post(
            post_key=r.key,
            type=post_type(r.kind),
            family=r.family,
            score=r.base_score * recency(r.anchor_date, day, held),
            headline=tuple(r.headline),
            named_shooter_ids=r.named_shooter_ids,
            row=r,
        )
        for r in pool
    ]


def trophy_posts(
    awards: Iterable[Award], catalog: Mapping[str, TrophyInfo], day: date
) -> list[Post]:
    """One post per trophy earned that day, naming everyone who earned it."""
    by_code: dict[str, set[tuple[int, str]]] = {}
    for a in awards:
        if a.code in catalog:
            by_code.setdefault(a.code, set()).add((a.shooter_id, natural_name(a.display_name)))
    posts: list[Post] = []
    for code in sorted(by_code):
        info = catalog[code]
        holders = tuple(sorted(by_code[code], key=lambda h: (h[1], h[0])))
        trophy = TrophyPost(code, info.title, info.art_key, info.metal, holders)
        posts.append(
            Post(
                post_key=trophy_key(code, day),
                type="trophy",
                family="trophy",
                score=TROPHY_SCORE,
                headline=tuple(trophy_headline(trophy)),
                named_shooter_ids=tuple(sid for sid, _ in holders),
                trophy=trophy,
            )
        )
    return posts


def otd_posts(items: Iterable[OnThisDayItem], day: date) -> list[Post]:
    """One post per look-back Sunday, with or without scores."""
    return [
        Post(
            post_key=otd_key(day, item.years_ago),
            type="on_this_day",
            family="on_this_day",
            score=OTD_SCORE,
            headline=tuple(otd_headline(item)),
            named_shooter_ids=tuple(w.shooter_id for w in item.winners),
            on_this_day=item,
        )
        for item in items
    ]


def ranked(posts: Iterable[Post]) -> list[Post]:
    return sorted(posts, key=lambda p: (-p.score, p.post_key))


def interleave(
    posts: Sequence[Post], cap: int = FEED_CAP, max_run: int = MAX_RUN
) -> tuple[list[Post], list[Post]]:
    """(feed, rest) from `posts`, best first.

    The feed takes the best post of every feed type present (so a thin type such as "On this day"
    always shows), then the best of the rest up to `cap`. It is ordered greedily: each step takes
    the best chosen post that does not make a run of more than `max_run` of one type; when only
    that type is left, it takes it anyway. `rest` keeps the input order."""
    eligible = [p for p in posts if p.type in FEED_TYPES]
    seeds: dict[PostType, Post] = {}
    for p in eligible:
        seeds.setdefault(p.type, p)
    chosen = {p.post_key for p in list(seeds.values())[:cap]}
    for p in eligible:
        if len(chosen) >= cap:
            break
        chosen.add(p.post_key)
    pending = [p for p in eligible if p.post_key in chosen]
    feed: list[Post] = []
    while pending:
        run = feed[-max_run:]
        blocked = run[0].type if len(run) == max_run and len({p.type for p in run}) == 1 else None
        pick = next((p for p in pending if p.type != blocked), pending[0])
        feed.append(pick)
        pending.remove(pick)
    taken = {p.post_key for p in feed}
    return feed, [p for p in posts if p.post_key not in taken]


def group_more(rest: Iterable[Post]) -> list[MoreGroup]:
    """The rest by family, families in the order of their best post, posts best first."""
    by_family: dict[str, list[Post]] = {}
    for p in rest:
        by_family.setdefault(p.family, []).append(p)
    return [
        MoreGroup(family, FAMILY_LABELS.get(family, family.capitalize()), tuple(posts))
        for family, posts in by_family.items()
    ]


def assemble(
    day: date,
    held: Sequence[date],
    rows: Sequence[InsightRow],
    *,
    hero: InsightRow | None,
    spotlight: InsightRow | None,
    awards: Iterable[Award],
    catalog: Mapping[str, TrophyInfo],
    on_this_day: Iterable[OnThisDayItem],
    supersedes: Callable[[str], frozenset[str]],
) -> Issue:
    """The issue for `day`, which must be one of `held` (sorted)."""
    i = list(held).index(day)
    latest = i == len(held) - 1
    lead = hero if hero is not None and names_ok(hero) else None
    spot = spotlight if spotlight is not None and names_ok(spotlight) else None
    recap = next((r for r in rows if r.kind == sel.PINNED_HOME and r.anchor_date == day), None)
    exclude = frozenset(r.key for r in (lead, spot) if r is not None)
    pool = insight_pool(rows, day, latest=latest, supersedes=supersedes, exclude=exclude)
    posts = ranked(
        [
            *insight_posts(pool, day, held),
            *trophy_posts(awards, catalog, day),
            *otd_posts(on_this_day, day),
        ]
    )
    feed, rest = interleave(posts)
    return Issue(
        day=day,
        number=i + 1,
        previous=held[i - 1] if i > 0 else None,
        next=None if latest else held[i + 1],
        latest=latest,
        headline=lead,
        recap=recap,
        spotlight=spot,
        feed=tuple(feed),
        more=tuple(group_more(rest)),
    )
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/unit/analytics/test_sheet_assembly.py`

Expected: 58 passed.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add backend/tests/unit/analytics/test_sheet_assembly.py backend/src/sunday_clays/analytics/sheet.py
git commit -m "feat(sheet): pure Sunday Sheet assembler" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 2.2 The read API

- [ ] **Step 6: Write the failing test**

Create `backend/tests/integration/api/test_sheet_api.py`:

```python
"""GET /api/sheet/* on the fx world (Plan 14 Task 2): issues, numbers, posts and their keys."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sunday_clays.analytics import sheet
from sunday_clays.api.routes import sheet as sheet_routes

LATEST = date(2026, 9, 27)


def _held(fx_session: Session) -> list[date]:
    return list(
        fx_session.scalars(
            text("SELECT event_date FROM events WHERE results_complete ORDER BY event_date")
        )
    )


def _all_posts(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [*body["posts"], *(p for g in body["more"] for p in g["posts"])]


def test_latest_is_the_newest_held_sunday(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    held = _held(fx_session)
    body = fx_viewer_client.get("/api/sheet/latest").json()
    assert body["masthead"] == {
        "date": LATEST.isoformat(),
        "issue": len(held),
        "previous": held[-2].isoformat(),
        "next": None,
        "latest": True,
        "newer": None,
    }
    assert fx_viewer_client.get(f"/api/sheet/{LATEST.isoformat()}").json() == body


def test_the_first_issue_has_no_previous(fx_viewer_client: TestClient, fx_session: Session) -> None:
    held = _held(fx_session)
    masthead = fx_viewer_client.get(f"/api/sheet/{held[0].isoformat()}").json()["masthead"]
    assert (masthead["issue"], masthead["previous"], masthead["next"]) == (
        1,
        None,
        held[1].isoformat(),
    )
    assert masthead["latest"] is False


def test_a_sunday_without_a_sheet_is_404(fx_viewer_client: TestClient, fx_session: Session) -> None:
    not_held = fx_session.scalar(
        text("SELECT event_date FROM events WHERE NOT results_complete ORDER BY event_date LIMIT 1")
    )
    for day in ("2026-09-26", str(not_held)):
        response = fx_viewer_client.get(f"/api/sheet/{day}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "sheet_not_found"


def test_the_four_numbers_match_the_sunday(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    event = fx_viewer_client.get(f"/api/events/{LATEST.isoformat()}").json()
    awards = fx_viewer_client.get(f"/api/events/{LATEST.isoformat()}/achievements").json()
    assert body["numbers"] == {
        "shooters": event["n_shooters"],
        "median": event["median"],
        "top_score": event["top_score"],
        "trophies": len(awards["awards"]),
    }


def test_posts_map_to_their_types_and_trophies_match_the_sunday(
    fx_viewer_client: TestClient,
) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    posts = _all_posts(body)
    assert 8 <= len(body["posts"]) <= sheet.FEED_CAP
    for p in posts:
        if p["insight"] is not None:
            assert p["post_key"] == p["insight"]["key"]
            assert p["type"] == sheet.post_type(p["insight"]["kind"])
            assert p["see_why"]["kind"] == "chart"
    awards = fx_viewer_client.get(f"/api/events/{LATEST.isoformat()}/achievements").json()
    trophy_posts = {p["trophy"]["code"]: p for p in posts if p["type"] == "trophy"}
    assert set(trophy_posts) == {a["code"] for a in awards["awards"]}
    for code, p in trophy_posts.items():
        assert p["post_key"] == f"trophy:{code}:{LATEST.isoformat()}"
        assert p["see_why"] == {
            "kind": "link",
            "label": f"{p['trophy']['title']} in the Trophy Room",
            "chart": None,
            "href": f"/achievements/{code}",
        }
        holders = {a["shooter_id"] for a in awards["awards"] if a["code"] == code}
        assert {h["shooter_id"] for h in p["trophy"]["holders"]} == holders


def test_the_feed_never_runs_a_type_three_times_while_another_is_left(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    for day in _held(fx_session)[-8:]:
        body = fx_viewer_client.get(f"/api/sheet/{day.isoformat()}").json()
        feed = [p["type"] for p in body["posts"]]
        rest = [p["type"] for p in _all_posts(body)[len(feed) :] if p["type"] in sheet.FEED_TYPES]
        for i in range(2, len(feed)):
            if feed[i] == feed[i - 1] == feed[i - 2]:
                assert set(feed[i:]) | set(rest) == {feed[i]}, (day, feed)


def test_named_shooter_posts_are_positive_or_neutral(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    for day in _held(fx_session)[-8:]:
        body = fx_viewer_client.get(f"/api/sheet/{day.isoformat()}").json()
        leads = [body[k] for k in ("headline", "spotlight") if body[k] is not None]
        for item in [*leads, *(p["insight"] for p in _all_posts(body) if p["insight"])]:
            if item["headline"] and any(s["t"] == "shooter" for s in item["headline"]):
                assert item["polarity"] in {"positive", "neutral"}, (day, item["key"])


def test_more_is_grouped_by_family(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    families = [g["family"] for g in body["more"]]
    assert len(families) == len(set(families))
    for group in body["more"]:
        assert group["posts"]
        assert {p["family"] for p in group["posts"]} == {group["family"]}


def test_the_headline_is_the_hero_pick_and_the_recap_its_deck(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    hero = fx_session.scalar(
        text("SELECT insight_key FROM insight_picks WHERE sunday = :d AND slot = 'hero'"),
        {"d": LATEST},
    )
    assert body["headline"]["key"] == hero
    assert body["recap"]["kind"] == "home.sunday-recap"
    keys = {p["post_key"] for p in _all_posts(body)}
    assert body["headline"]["key"] not in keys
    assert body["recap"]["key"] not in keys


def test_every_post_key_resolves_and_nothing_else_does(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    held = _held(fx_session)
    for day in (held[-1], held[-5]):
        body = fx_viewer_client.get(f"/api/sheet/{day.isoformat()}").json()
        for p in _all_posts(body):
            assert sheet_routes.resolves(fx_session, p["post_key"]), p["post_key"]
    latest = fx_viewer_client.get("/api/sheet/latest").json()
    for key in (
        latest["headline"]["key"],
        "trophy:no_such_trophy:2026-09-27",
        "otd:2026-09-27:9",
        "otd:2026-09-26:1",
        "deadbeefdeadbeefdead",
    ):
        assert not sheet_routes.resolves(fx_session, key), key


def test_without_a_held_sunday_there_is_no_sheet(
    viewer_client: TestClient, session: Session
) -> None:
    response = viewer_client.get("/api/sheet/latest")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "sheet_not_found"
    assert sheet_routes.post_issue_date(session, "otd:2026-09-27:1") is None


@pytest.mark.parametrize(
    ("has_scores", "head_count", "n_shooters"), [(False, 14, 0), (True, None, 6)]
)
def test_a_newer_sunday_without_full_results_is_on_the_latest_issue_only(
    session: Session, has_scores: bool, head_count: int | None, n_shooters: int
) -> None:
    """Home's Latest Sunday card followed the newest Sunday; the Sheet keeps the latest held issue
    and points at a newer attendance-only or partly scored one."""
    insert = text(
        "INSERT INTO events (event_date, round_type, round_type_source, head_count, n_rounds,"
        " n_shooters, has_scores, has_stations, results_complete)"
        " VALUES (:d, 'sporting', 'none', :hc, 0, :n, :hs, false, :rc)"
    )
    held = [date(2026, 9, 13), date(2026, 9, 20)]
    for day in held:
        session.execute(insert, {"d": day, "hc": None, "n": 0, "hs": True, "rc": True})
    newer = {"d": LATEST, "hc": head_count, "n": n_shooters, "hs": has_scores, "rc": False}
    session.execute(insert, newer)

    def issue(day: date) -> sheet.Issue:
        return sheet.assemble(
            day,
            held,
            [],
            hero=None,
            spotlight=None,
            awards=[],
            catalog={},
            on_this_day=[],
            supersedes=lambda _kind: frozenset(),
        )

    out = sheet_routes.newer_sunday(session, issue(held[-1]))
    assert out is not None
    assert out.model_dump() == {
        "date": LATEST,
        "has_scores": has_scores,
        "head_count": head_count,
        "n_shooters": n_shooters,
    }
    assert sheet_routes.newer_sunday(session, issue(held[0])) is None


def test_the_latest_issue_has_no_newer_sunday_when_it_is_the_newest(
    fx_session: Session,
) -> None:
    held = _held(fx_session)
    issue = sheet_routes.build_issue(fx_session, held[-1])
    assert sheet_routes.newer_sunday(fx_session, issue) is None


def test_the_latest_issue_carries_on_this_day_whenever_it_has_a_look_back(
    fx_viewer_client: TestClient,
) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    if any(p["type"] == "on_this_day" for p in _all_posts(body)):
        assert any(p["type"] == "on_this_day" for p in body["posts"])
    present = {p["type"] for p in _all_posts(body) if p["type"] in sheet.FEED_TYPES}
    assert {p["type"] for p in body["posts"]} == present


def test_a_post_without_a_source_is_a_bug_not_a_link() -> None:
    orphan = sheet.Post("k", "other", "form", 1.0, (), ())
    with pytest.raises(ValueError, match="post k has no source"):
        sheet_routes.see_why(orphan)


def test_the_body_never_carries_bump_counts_and_is_etagged(
    fx_viewer_client: TestClient,
) -> None:
    first = fx_viewer_client.get("/api/sheet/latest")
    assert '"bumps"' not in first.text
    assert '"bumped"' not in first.text
    etag = first.headers["etag"]
    again = fx_viewer_client.get("/api/sheet/latest", headers={"If-None-Match": etag})
    assert again.status_code == 304
```

- [ ] **Step 7: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/integration/api/test_sheet_api.py`

Expected: ERROR at collection: `ImportError: cannot import name 'sheet' from 'sunday_clays.api.routes'`.

- [ ] **Step 8: Write the implementation**

Create `backend/src/sunday_clays/api/routes/sheet.py`:

```python
"""GET /api/sheet/* (Plan 14): the Sunday Sheet, one issue per held Sunday.

The body is cached by data_version (the memo here and the ETag middleware). Bump counts are never
part of it: they change without a data_version bump, so the client reads them from
GET /api/sheet/{date}/bumps (Task 3).
"""

from __future__ import annotations

import datetime as dt
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path
from pydantic import BaseModel
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from sunday_clays.analytics import frames, sheet, yir
from sunday_clays.analytics.achievements.registry import Metal, trophies
from sunday_clays.analytics.cache import cached_by_data_version
from sunday_clays.analytics.insights.picks import picked
from sunday_clays.analytics.insights.store import (
    InsightRow,
    get_new_since,
    insights_table,
    load_picks,
    load_rows,
)
from sunday_clays.analytics.pipeline import get_data_version
from sunday_clays.api.routes._convert import opt_float, opt_int, rows
from sunday_clays.api.routes.insights import (
    InsightChartOut,
    InsightOut,
    InsightSegmentOut,
    held_dates,
    insight_out,
    supersedes_of,
)
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError

router = APIRouter(tags=["sheet"])

PostTypeOut = Literal[
    "milestone", "improvement", "trophy", "conditions", "welcome", "on_this_day", "other"
]

_AWARDS_SQL = text(
    "SELECT a.shooter_id, p.display_name, a.code FROM achievements_awarded a"
    " JOIN shooter_profiles p ON p.shooter_id = a.shooter_id WHERE a.event_date = :d"
    " ORDER BY a.code, p.display_name, a.shooter_id"
)


class NewerSundayOut(BaseModel):
    """A Sunday after the latest issue that has no full results yet (attendance only or partial):
    the masthead points at it the way Home's Latest Sunday card did."""

    date: dt.date
    has_scores: bool
    head_count: int | None
    n_shooters: int


class SheetMastheadOut(BaseModel):
    date: dt.date
    issue: int  # held Sundays up to and including this one
    previous: dt.date | None
    next: dt.date | None
    latest: bool
    newer: NewerSundayOut | None


class SheetNumbersOut(BaseModel):
    shooters: int
    median: float | None
    top_score: int | None
    trophies: int


class SeeWhyOut(BaseModel):
    """`chart`: an insight's chart link (the frontend builds its URL); `link`: a page `href`."""

    kind: Literal["chart", "link"]
    label: str
    chart: InsightChartOut | None = None
    href: str | None = None


class SheetShooterOut(BaseModel):
    shooter_id: int
    name: str


class SheetTrophyOut(BaseModel):
    code: str
    title: str
    art_key: str
    metal: Metal | None
    holders: list[SheetShooterOut]


class SheetOnThisDayOut(BaseModel):
    years_ago: int
    event_date: date
    n_shooters: int
    top_score: int | None


class SheetPostOut(BaseModel):
    post_key: str
    type: PostTypeOut
    family: str
    headline: list[InsightSegmentOut]
    named_shooter_ids: list[int]
    see_why: SeeWhyOut
    insight: InsightOut | None = None
    trophy: SheetTrophyOut | None = None
    on_this_day: SheetOnThisDayOut | None = None


class SheetMoreGroupOut(BaseModel):
    family: str
    label: str
    posts: list[SheetPostOut]


class SheetOut(BaseModel):
    data_version: int
    masthead: SheetMastheadOut
    numbers: SheetNumbersOut
    headline: InsightOut | None
    recap: InsightOut | None
    spotlight: InsightOut | None
    posts: list[SheetPostOut]
    more: list[SheetMoreGroupOut]


def trophy_catalog() -> dict[str, sheet.TrophyInfo]:
    """Every trophy, titled as the Trophy Room titles it ("Name — Tier")."""
    out: dict[str, sheet.TrophyInfo] = {}
    for t in trophies():
        name = t.achievement.name
        title = name if t.tier is None else f"{name} — {t.tier.label}"
        metal = None if t.tier is None else t.tier.metal.value
        out[t.code] = sheet.TrophyInfo(t.code, title, t.achievement.art_key, metal)
    return out


def _issue_rows(session: Session, day: date, latest: bool) -> list[InsightRow]:
    """Rows anchored on `day`, the day's picks and (latest issue) Home's evergreen rows and the
    FRESH_EVERGREEN kinds (the assembler keeps those about `day`)."""
    t = insights_table()
    keys = [p.insight_key for p in load_picks(session, day)]
    clauses = [t.c.anchor_date == day, t.c.key.in_(keys)]
    if latest:
        evergreen = or_(t.c.pages.contains(["home"]), t.c.kind.in_(sorted(sheet.FRESH_EVERGREEN)))
        clauses.append(and_(t.c.anchor_date.is_(None), evergreen))
    return load_rows(session, or_(*clauses))


@cached_by_data_version
def build_issue(session: Session, day: date) -> sheet.Issue:
    """The assembled issue for a held Sunday (callers check that `day` is held)."""
    held = held_dates(session)
    rows_ = _issue_rows(session, day, day == held[-1])
    hero, spotlight = picked(rows_, load_picks(session, day), day)
    awards = [
        sheet.Award(int(sid), str(name), str(code))
        for sid, name, code in session.execute(_AWARDS_SQL, {"d": day})
    ]
    return sheet.assemble(
        day,
        held,
        rows_,
        hero=hero,
        spotlight=spotlight,
        awards=awards,
        catalog=trophy_catalog(),
        on_this_day=yir.on_this_day(yir.load_yir_frames(session), day),
        supersedes=supersedes_of,
    )


def see_why(post: sheet.Post) -> SeeWhyOut:
    if post.row is not None:
        chart = InsightChartOut.model_validate(dict(post.row.chart))
        return SeeWhyOut(kind="chart", label=chart.label, chart=chart)
    if post.trophy is not None:
        return SeeWhyOut(
            kind="link",
            label=f"{post.trophy.title} in the Trophy Room",
            href=f"/achievements/{post.trophy.code}",
        )
    if post.on_this_day is not None:
        return SeeWhyOut(
            kind="link",
            label="That Sunday's results",
            href=f"/events/{post.on_this_day.event_date.isoformat()}",
        )
    raise ValueError(f"post {post.post_key} has no source")


def _post_out(post: sheet.Post, new_since: int | None) -> SheetPostOut:
    trophy, otd = post.trophy, post.on_this_day
    return SheetPostOut(
        post_key=post.post_key,
        type=post.type,
        family=post.family,
        headline=[InsightSegmentOut.model_validate(s) for s in post.headline],
        named_shooter_ids=list(post.named_shooter_ids),
        see_why=see_why(post),
        insight=None if post.row is None else insight_out(post.row, new_since),
        trophy=None
        if trophy is None
        else SheetTrophyOut(
            code=trophy.code,
            title=trophy.title,
            art_key=trophy.art_key,
            metal=None if trophy.metal is None else Metal(trophy.metal),
            holders=[SheetShooterOut(shooter_id=sid, name=name) for sid, name in trophy.holders],
        ),
        on_this_day=None
        if otd is None
        else SheetOnThisDayOut(
            years_ago=otd.years_ago,
            event_date=otd.event_date,
            n_shooters=otd.n_shooters,
            top_score=otd.top_score,
        ),
    )


def newer_sunday(session: Session, issue: sheet.Issue) -> NewerSundayOut | None:
    """On the latest issue: the newest Sunday when it is after the issue (so not fully scored)."""
    if not issue.latest:
        return None
    events = frames.load_events(session)
    newest = rows(events.loc[events["event_date"] == events["event_date"].max()])[0]
    if newest["event_date"] <= issue.day:
        return None
    return NewerSundayOut(
        date=newest["event_date"],
        has_scores=bool(newest["has_scores"]),
        head_count=opt_int(newest["head_count"]),
        n_shooters=int(newest["n_shooters"]),
    )


def _numbers(session: Session, issue: sheet.Issue) -> SheetNumbersOut:
    events = frames.load_events(session)
    event = rows(events.loc[events["event_date"] == issue.day])[0]
    return SheetNumbersOut(
        shooters=int(event["n_shooters"]),
        median=opt_float(event["median"]),
        top_score=opt_int(event["top_score"]),
        trophies=sum(len(p.trophy.holders) for p in issue.posts if p.trophy is not None),
    )


@cached_by_data_version
def sheet_body(session: Session, day: date) -> SheetOut:
    issue = build_issue(session, day)
    new_since = get_new_since(session)

    def maybe(row: InsightRow | None) -> InsightOut | None:
        return None if row is None else insight_out(row, new_since)

    return SheetOut(
        data_version=get_data_version(session),
        masthead=SheetMastheadOut(
            date=issue.day,
            issue=issue.number,
            previous=issue.previous,
            next=issue.next,
            latest=issue.latest,
            newer=newer_sunday(session, issue),
        ),
        numbers=_numbers(session, issue),
        headline=maybe(issue.headline),
        recap=maybe(issue.recap),
        spotlight=maybe(issue.spotlight),
        posts=[_post_out(p, new_since) for p in issue.feed],
        more=[
            SheetMoreGroupOut(
                family=g.family, label=g.label, posts=[_post_out(p, new_since) for p in g.posts]
            )
            for g in issue.more
        ],
    )


def post_issue_date(session: Session, post_key: str) -> date | None:
    """The held Sunday whose issue a key would be on: a trophy or "On this day" key names it; an
    insight key's anchor (an evergreen row: the latest issue). None for an unknown key."""
    held = held_dates(session)
    if not held:
        return None
    day = sheet.synthetic_key_date(post_key)
    if day is None:
        t = insights_table()
        found = session.execute(select(t.c.anchor_date).where(t.c.key == post_key)).first()
        if found is None:
            return None
        day = held[-1] if found.anchor_date is None else found.anchor_date
    return day if day in held else None


def resolves(session: Session, post_key: str) -> bool:
    """True when the key is a post on its issue as the data stands now (feed or "More")."""
    day = post_issue_date(session, post_key)
    return day is not None and post_key in build_issue(session, day).post_keys


def held_or_404(session: Session, day: date) -> None:
    if day not in held_dates(session):
        raise NotFoundError("sheet_not_found", f"No Sunday Sheet for {day.isoformat()}")


@router.get("/api/sheet/latest")
def latest_sheet(session: SessionDep) -> SheetOut:
    held = held_dates(session)
    if not held:
        raise NotFoundError("sheet_not_found", "No Sunday has full results yet")
    return sheet_body(session, held[-1])


@router.get("/api/sheet/{date}")
def sheet_for_date(day: Annotated[date, Path(alias="date")], session: SessionDep) -> SheetOut:
    held_or_404(session, day)
    return sheet_body(session, day)
```

- [ ] **Step 9: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_sheet_api.py tests/integration/api/test_route_auth_matrix.py tests/unit/api/test_routes_discovery.py`

Expected: all pass (the auth matrix walks the two new routes and gets 401 without a session).

- [ ] **Step 10: Commit**

From the worktree root:

```bash
git add backend/tests/integration/api/test_sheet_api.py backend/src/sunday_clays/api/routes/sheet.py
git commit -m "feat(sheet): GET /api/sheet/latest and /api/sheet/{date}" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 2.3 Gates

- [ ] **Step 11: Run the gates before handing the branch back**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src`

Expected: all three pass ("All checks passed!", "N files already formatted", "Success: no issues found")

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 3: Bump API, admin wipe and cache rules

**Wave 2** · parallel with: none (Wave 2 is this task alone) · branch `task/14-3-bump-api` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Modify: `backend/src/sunday_clays/api/etag.py`
- Modify: `backend/src/sunday_clays/api/routes/sheet.py` (docstring, imports; append the bump routes)
- Create: `backend/src/sunday_clays/api/routes/admin_sheet.py`
- Test: `backend/tests/unit/api/test_etag_helpers.py`
- Test: `backend/tests/integration/api/test_sheet_bumps_api.py`
- Test: `backend/tests/unit/api/test_admin_sheet_labels.py`

**Interfaces:**
- Consumes:
  - Task 1: `domain.bumps.add_bump`, `remove_bump`, `bump_state`, `bump_states`, `bump_totals`, `wipe_bumps`, `BumpState`; `auth.ratelimit.bumps_limited`, `record_bump_action`, `BUMP_LIMIT`.
  - Task 2: `api.routes.sheet.build_issue`, `held_or_404`, `resolves`, `post_issue_date`; `analytics.sheet.synthetic_key_date`.
  - `auth.deps.client_ip(request)`, `TooManyRequestsError`, `Actor`, `admin_actor`, `record_audit(session, ip, role, action, details)`; `domain.errors.DomainError` (400), `NotFoundError`; `analytics.insights.templates.plain`; fixtures `fx_viewer_client`, `fx_admin_client`, `fx_session`.
- Produces:
  - `GET /api/sheet/{date}/bumps?device_id=` → `dict[str, BumpStateOut{bumps: int, bumped: bool}]` for every current post of the issue (zeros included).
  - `POST /api/sheet/bumps` and `DELETE /api/sheet/bumps` with body `BumpIn{post_key: str (1..200), device_id: str (1..64)}` → `BumpStateOut`. Errors: 400 `bad_device_id`, 404 `post_not_found`, 404 `sheet_not_found`, 429 `rate_limited`. `parse_device_id(value: str) -> uuid.UUID`.
  - `GET /api/admin/sheet/bumps` → `list[BumpTotalOut{post_key, bumps, last_at: datetime, label: str, issue_date: date | None, current: bool}]`; `DELETE /api/admin/sheet/bumps/{post_key}` → `WipeOut{post_key, wiped: int}`, audited as `sheet.wipe_bumps` with `{post_key, wiped}`; `admin_sheet.post_label(post_key, headlines: Mapping[str, str]) -> str`.
  - `api.etag.NO_STORE_SUFFIXES = ("/bumps",)`: such paths are never ETagged and are `Cache-Control: no-store`.

#### 3.1 Bump counts are never cached

- [ ] **Step 1: Write the failing test**

In `backend/tests/unit/api/test_etag_helpers.py`, replace:

```python
        ("GET", "/api/admin/imports", False),
        ("GET", "/api/predictions/next", False),
        ("GET", "/index.html", False),
    ],
```

with:

```python
        ("GET", "/api/admin/imports", False),
        ("GET", "/api/predictions/next", False),
        ("GET", "/api/sheet/latest", True),
        ("GET", "/api/sheet/2026-09-27", True),
        ("GET", "/api/sheet/2026-09-27/bumps", False),
        ("GET", "/index.html", False),
    ],
```

In `backend/tests/unit/api/test_etag_helpers.py`, replace:

```python
        ("/api/auth/me", "no-store"),
        ("/api/admin/jobs/1", "no-store"),
        ("/assets/app.js", None),
    ],
)
```

with:

```python
        ("/api/auth/me", "no-store"),
        ("/api/admin/jobs/1", "no-store"),
        ("/api/sheet/2026-09-27", "private, no-cache"),
        ("/api/sheet/2026-09-27/bumps", "no-store"),
        ("/api/sheet/bumps", "no-store"),
        ("/assets/app.js", None),
        ("/assets/bumps", None),
    ],
)
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/unit/api/test_etag_helpers.py`

Expected: FAIL: the `/api/sheet/2026-09-27/bumps` eligibility case and the `/bumps` cache-control cases.

- [ ] **Step 3: Write the implementation**

In `backend/src/sunday_clays/api/etag.py`, replace:

```python
)
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/")


def etag_eligible(method: str, path: str) -> bool:
    """GET under /api/, except health, auth, admin and predictions."""
    return method == "GET" and path.startswith("/api/") and not path.startswith(NO_ETAG_PREFIXES)


def cache_control_for(path: str) -> str | None:
    """`no-store` for auth/admin, `private, no-cache` for other /api paths."""
    if path.startswith(NO_STORE_PREFIXES):
        return "no-store"
    if path == "/api" or path.startswith("/api/"):
```

with:

```python
)
NO_STORE_PREFIXES: tuple[str, ...] = ("/api/auth/", "/api/admin/")
# Plan 14: fist-bump counts change without a data_version bump, so a data_version ETag would
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
    if path == "/api" or path.startswith("/api/"):
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/unit/api/test_etag_helpers.py tests/unit/api/test_etag_anonymous.py`

Expected: all pass.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add backend/tests/unit/api/test_etag_helpers.py backend/src/sunday_clays/api/etag.py
git commit -m "feat(sheet): bump counts are never ETagged or stored" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 3.2 The bump routes and the admin wipe

- [ ] **Step 6: Write the failing test**

Create `backend/tests/integration/api/test_sheet_bumps_api.py`:

```python
"""Fist-bump routes on the fx world (Plan 14 Task 3): idempotent, refused, rate-limited, never
cached, and wiped by an admin with an audit entry."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from sunday_clays.auth.ratelimit import BUMP_LIMIT
from sunday_clays.domain.bumps import BumpState, add_bump, bump_state
from sunday_clays.models import Base

A = "00000000-0000-4000-8000-00000000000a"
B = "00000000-0000-4000-8000-00000000000b"
IP = {"X-Real-IP": "203.0.113.7"}
LATEST = "2026-09-27"
ATTEMPTS = Base.metadata.tables["bump_attempts"]
AUDIT = Base.metadata.tables["audit_log"]


def _key(client: TestClient, index: int = 0) -> str:
    return str(client.get("/api/sheet/latest").json()["posts"][index]["post_key"])


def _post(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.post(
        "/api/sheet/bumps", json={"post_key": key, "device_id": device}, headers=headers
    )


def _delete(client: TestClient, key: str, device: str, headers: dict[str, str] = IP):
    return client.request(
        "DELETE", "/api/sheet/bumps", json={"post_key": key, "device_id": device}, headers=headers
    )


def test_bumping_is_idempotent_per_device_and_taking_back_too(
    fx_viewer_client: TestClient,
) -> None:
    key = _key(fx_viewer_client)
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": True}
    assert _post(fx_viewer_client, key, B).json() == {"bumps": 2, "bumped": True}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    assert _delete(fx_viewer_client, key, A).json() == {"bumps": 1, "bumped": False}
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", params={"device_id": B}).json()
    assert counts[key] == {"bumps": 1, "bumped": True}
    mine = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", params={"device_id": A}).json()
    assert mine[key] == {"bumps": 1, "bumped": False}


def test_counts_cover_every_post_on_the_issue_with_zeros(fx_viewer_client: TestClient) -> None:
    body = fx_viewer_client.get("/api/sheet/latest").json()
    keys = {p["post_key"] for p in body["posts"]} | {
        p["post_key"] for g in body["more"] for p in g["posts"]
    }
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps").json()
    assert set(counts) == keys
    assert set(map(str, counts.values())) == {str({"bumps": 0, "bumped": False})}


def test_a_device_id_that_is_not_a_uuid_is_400(fx_viewer_client: TestClient) -> None:
    key = _key(fx_viewer_client)
    for bad in ("not-a-uuid", "00000000000040008000000000000000a", "{" + A + "}", A + "x"):
        for response in (_post(fx_viewer_client, key, bad), _delete(fx_viewer_client, key, bad)):
            assert response.status_code == 400, bad
            assert response.json()["error"]["code"] == "bad_device_id"
    response = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", params={"device_id": "nope"})
    assert response.status_code == 400
    assert _post(fx_viewer_client, key, A.upper()).status_code == 200


def test_an_unknown_post_key_is_404(fx_viewer_client: TestClient) -> None:
    for key in ("deadbeefdeadbeefdead", "trophy:no_such_trophy:2026-09-27", "otd:2026-09-27:9"):
        response = _post(fx_viewer_client, key, A)
        assert response.status_code == 404, key
        assert response.json()["error"]["code"] == "post_not_found"
    assert fx_viewer_client.get("/api/sheet/2026-09-26/bumps").status_code == 404


def test_stale_bumps_are_kept_hidden_and_wipeable(
    fx_viewer_client: TestClient, fx_admin_client: TestClient, fx_session: Session
) -> None:
    stale = "trophy:retired_trophy:2026-09-27"
    add_bump(fx_session, stale, uuid.UUID(A))
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps").json()
    assert stale not in counts
    assert _post(fx_viewer_client, stale, B).status_code == 404
    assert bump_state(fx_session, stale, None) == BumpState(1, False)
    listed = {row["post_key"]: row for row in fx_admin_client.get("/api/admin/sheet/bumps").json()}
    assert listed[stale]["current"] is False
    assert listed[stale]["label"] == "Trophy retired_trophy, 2026-09-27"
    response = fx_admin_client.delete(f"/api/admin/sheet/bumps/{stale}")
    assert response.json() == {"post_key": stale, "wiped": 1}


def test_the_120th_action_in_10_minutes_is_the_last(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    key = _key(fx_viewer_client)
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


def test_refused_requests_still_count_toward_the_limit(
    fx_viewer_client: TestClient, fx_session: Session
) -> None:
    before = len(fx_session.execute(select(ATTEMPTS.c.id)).all())
    _post(fx_viewer_client, "deadbeefdeadbeefdead", A)
    _post(fx_viewer_client, _key(fx_viewer_client), "nope")
    assert len(fx_session.execute(select(ATTEMPTS.c.id)).all()) == before + 2


def test_counts_are_never_cached_and_never_in_the_issue_body(fx_viewer_client: TestClient) -> None:
    before = fx_viewer_client.get("/api/sheet/latest")
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps")
    assert counts.headers["cache-control"] == "no-store"
    assert "etag" not in counts.headers
    _post(fx_viewer_client, _key(fx_viewer_client), A)
    again = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps", headers={"If-None-Match": "*"})
    assert again.status_code == 200
    assert again.json() != counts.json()
    after = fx_viewer_client.get("/api/sheet/latest")
    assert after.json() == before.json()
    assert after.headers["etag"] == before.headers["etag"]


def test_an_admin_wipe_clears_one_post_and_is_audited(
    fx_viewer_client: TestClient, fx_admin_client: TestClient, fx_session: Session
) -> None:
    posts = fx_viewer_client.get("/api/sheet/latest").json()["posts"]
    first = next(p for p in posts if p["insight"] is not None)
    key, other = first["post_key"], next(p["post_key"] for p in posts if p is not first)
    for device in (A, B):
        _post(fx_viewer_client, key, device)
    _post(fx_viewer_client, other, A)
    listed = fx_admin_client.get("/api/admin/sheet/bumps").json()
    row = next(r for r in listed if r["post_key"] == key)
    assert (row["bumps"], row["current"], row["issue_date"]) == (2, True, LATEST)
    assert row["label"] == first["insight"]["headline_text"]
    assert fx_viewer_client.delete(f"/api/admin/sheet/bumps/{key}").status_code == 403
    assert fx_admin_client.delete(f"/api/admin/sheet/bumps/{key}").json() == {
        "post_key": key,
        "wiped": 2,
    }
    counts = fx_viewer_client.get(f"/api/sheet/{LATEST}/bumps").json()
    assert counts[key] == {"bumps": 0, "bumped": False}
    assert counts[other]["bumps"] == 1
    action, details = fx_session.execute(
        select(AUDIT.c.action, AUDIT.c.details).order_by(AUDIT.c.id.desc()).limit(1)
    ).one()
    assert (action, details) == ("sheet.wipe_bumps", {"post_key": key, "wiped": 2})
```

Create `backend/tests/unit/api/test_admin_sheet_labels.py`:

```python
"""What an admin reads for a bumped post key (Plan 14 Task 3)."""

import pytest

from sunday_clays.api.routes.admin_sheet import post_label


@pytest.mark.parametrize(
    ("key", "label"),
    [
        ("0123456789abcdef0123", "New personal best for Ike Hadley: 46."),
        ("trophy:round_score:4:2026-09-27", "Trophy round_score:4, 2026-09-27"),
        ("otd:2026-09-27:2", "On this day, 2026-09-27"),
        ("fedcba9876543210fedc", "No longer on a Sheet"),
        ("trophy:broken", "No longer on a Sheet"),
    ],
)
def test_post_labels(key: str, label: str) -> None:
    headlines = {"0123456789abcdef0123": "New personal best for Ike Hadley: 46."}
    assert post_label(key, headlines) == label
```

- [ ] **Step 7: Run it to make sure it fails**

Run: `cd backend && uv run pytest -q tests/integration/api/test_sheet_bumps_api.py tests/unit/api/test_admin_sheet_labels.py`

Expected: ERROR at collection of the labels test (`No module named 'sunday_clays.api.routes.admin_sheet'`); the bump tests FAIL with 405 / 404 responses.

- [ ] **Step 8: Write the implementation**

In `backend/src/sunday_clays/api/routes/sheet.py`, replace:

```python
"""GET /api/sheet/* (Plan 14): the Sunday Sheet, one issue per held Sunday.

The body is cached by data_version (the memo here and the ETag middleware). Bump counts are never
part of it: they change without a data_version bump, so the client reads them from
GET /api/sheet/{date}/bumps (Task 3).
"""
```

with:

```python
"""/api/sheet/* (Plan 14): the Sunday Sheet, one issue per held Sunday, and its fist bumps.

The issue body is cached by data_version (the memo here and the ETag middleware). Bump counts are
never part of it: they change without a data_version bump, so the client reads them from
GET /api/sheet/{date}/bumps, which is never ETagged or stored (api/etag.py).
"""
```

In `backend/src/sunday_clays/api/routes/sheet.py`, replace:

```python

import datetime as dt
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path
from pydantic import BaseModel
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session
```

with:

```python

import datetime as dt
import uuid
from collections.abc import Callable
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session
```

In `backend/src/sunday_clays/api/routes/sheet.py`, replace:

```python
    supersedes_of,
)
from sunday_clays.db import SessionDep
from sunday_clays.domain.errors import NotFoundError

router = APIRouter(tags=["sheet"])
```

with:

```python
    supersedes_of,
)
from sunday_clays.auth.deps import TooManyRequestsError, client_ip
from sunday_clays.auth.ratelimit import bumps_limited, record_bump_action
from sunday_clays.db import SessionDep
from sunday_clays.domain.bumps import add_bump, bump_state, bump_states, remove_bump
from sunday_clays.domain.errors import DomainError, NotFoundError

router = APIRouter(tags=["sheet"])
```

In `backend/src/sunday_clays/api/routes/sheet.py`, replace:

```python
    held_or_404(session, day)
    return sheet_body(session, day)
```

with:

```python
    held_or_404(session, day)
    return sheet_body(session, day)


# --- Fist bumps (Plan 14 Task 3) ------------------------------------------------------------------
class BumpIn(BaseModel):
    post_key: str = Field(min_length=1, max_length=200)
    device_id: str = Field(min_length=1, max_length=64)


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


@router.get("/api/sheet/{date}/bumps")
def sheet_bumps(
    day: Annotated[date, Path(alias="date")],
    session: SessionDep,
    device_id: Annotated[str | None, Query(max_length=64)] = None,
) -> dict[str, BumpStateOut]:
    """Counts for every post on the issue (zeros included); a stale key is never listed."""
    held_or_404(session, day)
    device = None if device_id is None else parse_device_id(device_id)
    states = bump_states(session, build_issue(session, day).post_keys, device)
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
    if not resolves(session, body.post_key):
        raise NotFoundError("post_not_found", "That post is not on a Sunday Sheet")
    act(session, body.post_key, device)
    state = bump_state(session, body.post_key, device)
    return BumpStateOut(bumps=state.bumps, bumped=state.bumped)


@router.post("/api/sheet/bumps")
def bump_post(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: bumping twice from one device counts once."""
    return _bump_action(request, session, body, add_bump)


@router.delete("/api/sheet/bumps")
def unbump_post(body: BumpIn, request: Request, session: SessionDep) -> BumpStateOut:
    """Idempotent: taking back a bump that is not there changes nothing."""
    return _bump_action(request, session, body, remove_bump)
```

Create `backend/src/sunday_clays/api/routes/admin_sheet.py`:

```python
"""Admin: fist bumps on Sunday Sheet posts (Plan 14). Lists the bumped posts and wipes one."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import select

from sunday_clays.analytics import sheet
from sunday_clays.analytics.insights.store import insights_table
from sunday_clays.analytics.insights.templates import plain
from sunday_clays.api.routes.sheet import post_issue_date, resolves
from sunday_clays.auth.deps import Actor, admin_actor, record_audit
from sunday_clays.db import SessionDep
from sunday_clays.domain.bumps import bump_totals, wipe_bumps

router = APIRouter(prefix="/api/admin/sheet", tags=["admin"])

ActorDep = Annotated[Actor, Depends(admin_actor)]
LIST_LIMIT = 100


class BumpTotalOut(BaseModel):
    post_key: str
    bumps: int
    last_at: dt.datetime
    label: str
    issue_date: dt.date | None
    current: bool  # still a post on its Sheet; a stale key is kept but never shown


class WipeOut(BaseModel):
    post_key: str
    wiped: int


def post_label(post_key: str, headlines: Mapping[str, str]) -> str:
    """What an admin reads for a key: the insight's headline, or the trophy / look-back it names."""
    if post_key in headlines:
        return headlines[post_key]
    day = sheet.synthetic_key_date(post_key)
    if day is not None and post_key.startswith("trophy:"):
        code = post_key.removeprefix("trophy:").rsplit(":", 1)[0]
        return f"Trophy {code}, {day.isoformat()}"
    if day is not None:
        return f"On this day, {day.isoformat()}"
    return "No longer on a Sheet"


@router.get("/bumps")
def list_bumped_posts(session: SessionDep) -> list[BumpTotalOut]:
    """The most recently bumped posts first, at most LIST_LIMIT."""
    totals = bump_totals(session, LIST_LIMIT)
    t = insights_table()
    headlines = {
        str(key): plain(headline)
        for key, headline in session.execute(
            select(t.c.key, t.c.headline).where(t.c.key.in_([x.post_key for x in totals]))
        )
    }
    return [
        BumpTotalOut(
            post_key=x.post_key,
            bumps=x.bumps,
            last_at=x.last_at,
            label=post_label(x.post_key, headlines),
            issue_date=post_issue_date(session, x.post_key),
            current=resolves(session, x.post_key),
        )
        for x in totals
    ]


@router.delete("/bumps/{post_key}")
def wipe_post_bumps(
    post_key: Annotated[str, Path(min_length=1, max_length=200)],
    session: SessionDep,
    actor: ActorDep,
) -> WipeOut:
    """Wipes every bump on one post, current or stale, and records it in the audit log."""
    wiped = wipe_bumps(session, post_key)
    record_audit(
        session, actor.ip, actor.role, "sheet.wipe_bumps", {"post_key": post_key, "wiped": wiped}
    )
    return WipeOut(post_key=post_key, wiped=wiped)
```

- [ ] **Step 9: Run the tests and make sure they pass**

Run: `cd backend && uv run pytest -q tests/integration/api/test_sheet_bumps_api.py tests/unit/api/test_admin_sheet_labels.py tests/integration/api/test_sheet_api.py tests/integration/api/test_route_auth_matrix.py`

Expected: all pass (the matrix now also walks the four bump routes: 401 without a session).

- [ ] **Step 10: Commit**

From the worktree root:

```bash
git add backend/tests/integration/api/test_sheet_bumps_api.py backend/tests/unit/api/test_admin_sheet_labels.py backend/src/sunday_clays/api/routes/sheet.py backend/src/sunday_clays/api/routes/admin_sheet.py
git commit -m "feat(sheet): fist-bump routes, rate limit and the audited admin wipe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 3.3 Gates

- [ ] **Step 11: Run the gates before handing the branch back**

Run: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy --strict src`

Expected: all three pass ("All checks passed!", "N files already formatted", "Success: no issues found")

Run: `cd backend && uv run pytest --cov --cov-branch`

Expected: the whole suite passes; coverage stays at or above the ratchet (99.8% in the replay)

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 4: Sheet page: masthead, numbers, feed, More and bumps

**Wave 3** · parallel with: Task 7 · branch `task/14-4-sheet-page` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Create: `frontend/src/lib/device.ts`
- Create: `frontend/src/features/sheet/api.ts`, `mocks.ts`, `explainers.ts`, `routes.tsx`
- Create: `frontend/src/features/sheet/components/BumpButton.tsx`, `Masthead.tsx`, `Numbers.tsx`, `PostCard.tsx`, `Feed.tsx`, `MoreFromSunday.tsx`, `SheetSkeleton.tsx`
- Create: `frontend/src/features/sheet/pages/SheetPage.tsx`
- Modify: `frontend/src/app/registry.test.ts` (the page-filter audit lists `/sheet/:date`)
- Test: `frontend/src/lib/device.test.ts`
- Test: `frontend/src/features/sheet/api.test.ts`, `explainers.test.ts`, `routes.test.tsx`, `components/BumpButton.test.tsx`, `pages/SheetPage.test.tsx`

**Interfaces:**
- Consumes:
  - Tasks 2 and 3 through `pnpm gen:api`: the `GET /api/sheet/latest`, `/api/sheet/{date}`, `/api/sheet/{date}/bumps`, `POST`/`DELETE /api/sheet/bumps` paths and schemas.
  - `api/client` `api`, `unwrap`; `api/errors` `ApiError`; `lib/me` `getMe`, `setMe`, `clearMe`; `lib/roundTypes` `useRoundTypeLink`; `lib/pageFilters` `NO_FILTERS`; `components/ui` `Card`, `Stat`, `Skeleton`, `EmptyState`; `components/charts/types` `Explainer`.
  - `features/home/format` `formatDay`, `formatScore`; `features/insights/segments` `Segments`; `features/insights/components/InsightList` `isMine`; `features/insights/components/InsightExplainer` `InsightExplainer({ id, insight, you })`; `features/insights/chartLink` `chartHref`; `components/ui/Explainer` `ExplainerToggle`, `ExplainerPanel`; `lib/timeWindowChoice` `useExplicitWindow`; `features/insights/mocks` `insightFixture`; `features/achievements/components/TrophyIcon` `TrophyIcon`.
  - Test helpers: `test/render` `renderWithProviders`, `renderRoutes`, `createTestQueryClient`; `test/msw/server` `server`.
- Produces:
  - `lib/device.ts`: `newUuid(): string`, `getDeviceId(): string | null` (`localStorage["sc.device"]`).
  - `features/sheet/api.ts`: types `SheetIssue`, `SheetPost`, `SheetPostType`, `SheetMoreGroup`, `BumpCounts`, `BumpState`, `IssueRef = "latest" | string`; `useSheet(ref: IssueRef)` (key `["/api/sheet", ref]`), `bumpsKey(date, deviceId)`, `useBumps(date: string, deviceId: string | null)`, `toggled(old, postKey, bump): BumpCounts`, `useBumpToggle(date, deviceId: string, postKey) -> { send(bump: boolean): void; failed: boolean }`.
  - `features/sheet/mocks.ts`: `postFixture(overrides?)`, `trophyPost`, `onThisDayPost`, `streakPost`, `sheetFixture(overrides?)`, `bumpsFixture`, `handlers` (latest, by date, bumps, POST, DELETE).
  - Components: `Masthead({ issue })` (with the "Newer Sunday" note when `masthead.newer` is set) and `newerText(newer) -> string`, `Numbers({ issue })`, `BumpButton({ date, postKey, deviceId, state, noteId })`, `PostCard({ post, date, deviceId, bumps, meId, noteId })` (New tag, "Earned by" holder list past 3 holders with 8 shown and "+N more", `chart.also` links, "How we worked it out") and `TYPE_LABELS`, `HEADLINE_NAMES = 3`, `HOLDERS_SHOWN = 8`, `Feed({ issue, bumps, deviceId, meId, noteId })` and `BUMPS_OFF`, `MoreFromSunday({ issue, bumps, deviceId, meId, noteId })`, `SheetSkeleton()`, `SheetPage()` (reads `:date`, else the latest issue); `sheetExplainers` (`shooters`, `median`, `top`, `trophies`, `onThisDay`); `routes` with `/sheet/:date` (`NO_FILTERS`; Task 8 makes it `ROUND_TYPE_ONLY`, Task 9 adds `/`).

#### 4.1 This browser’s device id

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/device.test.ts`

Expected: FAIL: `Failed to resolve import "./device"`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/lib/device.ts`:

```ts
/**
 * The random id this browser sends with fist bumps (Plan 14), kept only in localStorage. It is
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

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/lib/device.test.ts`

Expected: 6 passed.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add frontend/src/lib/device.test.ts frontend/src/lib/device.ts
git commit -m "feat(sheet): a random per-browser device id for bumps" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 4.2 Sheet queries and the bump button

- [ ] **Step 6: Write the failing test**

Create `frontend/src/features/sheet/api.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { toggled } from './api';

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

  it('starts a post nobody bumped at zero and keeps the other posts', () => {
    expect(toggled(undefined, 'k', true)).toEqual({ k: { bumps: 1, bumped: true } });
    expect(toggled({ j: { bumps: 4, bumped: false } }, 'k', true)).toEqual({
      j: { bumps: 4, bumped: false },
      k: { bumps: 1, bumped: true },
    });
  });
});
```

Create `frontend/src/features/sheet/components/BumpButton.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { createTestQueryClient, renderWithProviders } from '../../../test/render';
import { bumpsKey, useBumps, type BumpCounts } from '../api';
import { BumpButton } from './BumpButton';

const DATE = '2026-09-27';
const DEVICE = '00000000-0000-4000-8000-00000000000a';
const KEY = 'k-pb-3';

/** The button wired to the bumps query, as the feed renders it. */
function Harness({ deviceId = DEVICE }: { deviceId?: string | null }) {
  const bumps = useBumps(DATE, deviceId);
  return (
    <>
      <p id="note">Bumps need this browser to remember you</p>
      <BumpButton
        date={DATE}
        postKey={KEY}
        deviceId={deviceId}
        state={bumps.data?.[KEY]}
        noteId="note"
      />
    </>
  );
}

function seeded(counts: BumpCounts) {
  const queryClient = createTestQueryClient();
  queryClient.setQueryData(bumpsKey(DATE, DEVICE), counts);
  server.use(http.get('*/api/sheet/:date/bumps', () => HttpResponse.json(counts)));
  return queryClient;
}

describe('BumpButton', () => {
  it('counts the tap at once, before the server answers, then keeps the server count', async () => {
    let release: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('*/api/sheet/bumps', async () => {
        await answered;
        return HttpResponse.json({ bumps: 7, bumped: true });
      }),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
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
      http.post('*/api/sheet/bumps', () =>
        HttpResponse.json({ error: { code: 'rate_limited', message: 'x' } }, { status: 429 }),
      ),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Couldn’t send that bump');
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('takes a bump back on a second tap, and sends the two taps in order', async () => {
    const calls: string[] = [];
    server.use(
      http.post('*/api/sheet/bumps', async () => {
        calls.push('POST');
        await delay(30);
        return HttpResponse.json({ bumps: 3, bumped: true });
      }),
      http.delete('*/api/sheet/bumps', async ({ request }) => {
        calls.push('DELETE');
        expect(await request.json()).toEqual({ post_key: KEY, device_id: DEVICE });
        return HttpResponse.json({ bumps: 2, bumped: false });
      }),
    );
    const queryClient = seeded({ [KEY]: { bumps: 2, bumped: false } });
    const { user } = renderWithProviders(<Harness />, { queryClient });
    await user.click(screen.getByRole('button', { name: 'Fist bump, 2 bumps' }));
    await user.click(screen.getByRole('button', { name: 'Fist bump, 3 bumps' }));
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await waitFor(() => expect(calls).toEqual(['POST', 'DELETE']));
    // The POST's answer (3) arrived while the DELETE was queued: it never showed.
    expect(screen.getByRole('button', { name: 'Fist bump, 2 bumps' })).toBeInTheDocument();
  });

  it('shows the count but is off when this browser cannot keep a device id', () => {
    const queryClient = createTestQueryClient();
    queryClient.setQueryData(bumpsKey(DATE, null), { [KEY]: { bumps: 4, bumped: false } });
    renderWithProviders(<Harness deviceId={null} />, { queryClient });
    const button = screen.getByRole('button', { name: 'Fist bump, 4 bumps' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Bumps need this browser to remember you');
  });
});
```

- [ ] **Step 7: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/sheet/api.test.ts src/features/sheet/components/BumpButton.test.tsx`

Expected: FAIL: `Failed to resolve import "./api"` and `"../api"`.

- [ ] **Step 8: Write the implementation**

`mocks.ts` is picked up by `src/test/msw/handlers.ts` (C10), so every test gets the Sheet handlers.

Create `frontend/src/features/sheet/api.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap } from '../../api/client';

/**
 * The issue as the API client returns it. Typed through the hooks, like the insight feeds, so an
 * issue's insights are the same type as `features/insights` `Insight`.
 */
export type SheetIssue = NonNullable<ReturnType<typeof useSheet>['data']>;
export type SheetPost = SheetIssue['posts'][number];
export type SheetPostType = SheetPost['type'];
export type SheetMoreGroup = SheetIssue['more'][number];
export type BumpCounts = NonNullable<ReturnType<typeof useBumps>['data']>;
export type BumpState = BumpCounts[string];

/** The newest issue (`GET /api/sheet/latest`), or a Sunday's (`YYYY-MM-DD`). */
export type IssueRef = 'latest' | (string & {});

/** The issue body changes only with data_version (server ETag), so it may stay fresh a while. */
const STALE = 5 * 60 * 1000;

export function useSheet(ref: IssueRef) {
  return useQuery({
    queryKey: ['/api/sheet', ref],
    queryFn: () =>
      ref === 'latest'
        ? unwrap(api.GET('/api/sheet/latest'))
        : unwrap(api.GET('/api/sheet/{date}', { params: { path: { date: ref } } })),
    staleTime: STALE,
  });
}

export function bumpsKey(date: string, deviceId: string | null) {
  return ['/api/sheet/{date}/bumps', date, deviceId] as const;
}

/** Bump counts for every post of an issue; never cached by the server (they change any time). */
export function useBumps(date: string, deviceId: string | null) {
  return useQuery({
    queryKey: bumpsKey(date, deviceId),
    queryFn: () =>
      unwrap(
        api.GET('/api/sheet/{date}/bumps', {
          params: { path: { date }, query: deviceId === null ? {} : { device_id: deviceId } },
        }),
      ),
  });
}

/** `old` with this device's bump on `postKey` set to `bump` (a no-op when it already is). */
export function toggled(old: BumpCounts | undefined, postKey: string, bump: boolean): BumpCounts {
  const current = old?.[postKey] ?? { bumps: 0, bumped: false };
  if (current.bumped === bump) return { ...old, [postKey]: current };
  return {
    ...old,
    [postKey]: { bumps: Math.max(0, current.bumps + (bump ? 1 : -1)), bumped: bump },
  };
}

/**
 * Bump or take back a bump on one post. The count changes at once (optimistic); the request runs
 * after any earlier one for the same post (one mutation scope per post), so two quick taps reach
 * the server in order. A failure puts the counts back and sets `failed`; only the last request
 * for a post writes the server's answer, so an earlier answer never undoes a newer tap.
 */
export function useBumpToggle(date: string, deviceId: string, postKey: string) {
  const qc = useQueryClient();
  const [failed, setFailed] = useState(false);
  const key = bumpsKey(date, deviceId);
  const mutationKey = ['bump', date, postKey];
  const mutation = useMutation({
    mutationKey,
    scope: { id: `bump:${date}:${postKey}` },
    mutationFn: ({ bump }: { bump: boolean; previous: BumpCounts | undefined }) => {
      const body = { post_key: postKey, device_id: deviceId };
      return bump
        ? unwrap(api.POST('/api/sheet/bumps', { body }))
        : unwrap(api.DELETE('/api/sheet/bumps', { body }));
    },
    onError: (_error, { previous }) => {
      qc.setQueryData(key, previous);
      setFailed(true);
    },
    onSuccess: (state) => {
      // This request still counts as pending here: 1 means no newer tap is queued behind it.
      if (qc.isMutating({ mutationKey }) <= 1) {
        qc.setQueryData<BumpCounts>(key, (old) => ({ ...old, [postKey]: state }));
      }
    },
  });
  function send(bump: boolean) {
    setFailed(false);
    const previous = qc.getQueryData<BumpCounts>(key);
    void qc.cancelQueries({ queryKey: key });
    qc.setQueryData<BumpCounts>(key, toggled(previous, postKey, bump));
    mutation.mutate({ bump, previous });
  }
  return { send, failed };
}
```

Create `frontend/src/features/sheet/mocks.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { insightFixture } from '../insights/mocks';
import type { BumpCounts, SheetIssue, SheetPost } from './api';

/** An insight post about Ike Hadley (shooter 3): a personal best, linking the profile trend chart. */
export function postFixture(overrides: Partial<SheetPost> = {}): SheetPost {
  const insight = insightFixture();
  return {
    post_key: insight.key,
    type: 'milestone',
    family: 'milestone',
    headline: insight.headline,
    named_shooter_ids: [3],
    see_why: { kind: 'chart', label: insight.chart.label, chart: insight.chart, href: null },
    insight,
    trophy: null,
    on_this_day: null,
    ...overrides,
  };
}

export const trophyPost: SheetPost = postFixture({
  post_key: 'trophy:first_win:2026-09-27',
  type: 'trophy',
  family: 'trophy',
  headline: [
    { t: 'trophy', v: 'First win' },
    { t: 'text', v: ' unlocked by ' },
    { t: 'shooter', v: 'Amy Ace', id: 1 },
    { t: 'text', v: ' and ' },
    { t: 'shooter', v: 'Bob Bee', id: 2 },
    { t: 'text', v: '.' },
  ],
  named_shooter_ids: [1, 2],
  see_why: {
    kind: 'link',
    label: 'First win in the Trophy Room',
    chart: null,
    href: '/achievements/first_win',
  },
  insight: null,
  trophy: {
    code: 'first_win',
    title: 'First win',
    art_key: 'first_win',
    metal: null,
    holders: [
      { shooter_id: 1, name: 'Amy Ace' },
      { shooter_id: 2, name: 'Bob Bee' },
    ],
  },
});

export const onThisDayPost: SheetPost = postFixture({
  post_key: 'otd:2026-09-27:1',
  type: 'on_this_day',
  family: 'on_this_day',
  headline: [
    { t: 'text', v: 'One year ago, on ' },
    { t: 'date', v: 'Sep 28, 2025' },
    { t: 'text', v: ', ' },
    { t: 'num', v: '31' },
    { t: 'text', v: ' shooters came out and the top score was ' },
    { t: 'num', v: '48' },
    { t: 'text', v: '.' },
  ],
  named_shooter_ids: [],
  see_why: {
    kind: 'link',
    label: "That Sunday's results",
    chart: null,
    href: '/events/2025-09-28',
  },
  insight: null,
  on_this_day: { years_ago: 1, event_date: '2025-09-28', n_shooters: 31, top_score: 48 },
});

export const streakPost: SheetPost = postFixture({
  post_key: 'k-streak-5',
  type: 'other',
  family: 'streak',
  headline: [
    { t: 'num', v: '6' },
    { t: 'text', v: ' Sundays in a row above ' },
    { t: 'shooter', v: 'Cal Cy', id: 5 },
    { t: 'text', v: "'s own average." },
  ],
  named_shooter_ids: [5],
  insight: insightFixture({ key: 'k-streak-5', kind: 'pf.above-own-avg-streak', subject_id: '5' }),
});

export function sheetFixture(overrides: Partial<SheetIssue> = {}): SheetIssue {
  return {
    data_version: 7,
    masthead: {
      date: '2026-09-27',
      issue: 310,
      previous: '2026-09-13',
      next: null,
      latest: true,
      newer: null,
    },
    numbers: { shooters: 23, median: 39, top_score: 49, trophies: 13 },
    headline: null,
    recap: null,
    spotlight: null,
    posts: [postFixture(), trophyPost, onThisDayPost],
    more: [{ family: 'streak', label: 'Streaks', posts: [streakPost] }],
    ...overrides,
  };
}

export const bumpsFixture: BumpCounts = {
  'k-pb-3': { bumps: 2, bumped: false },
  'trophy:first_win:2026-09-27': { bumps: 5, bumped: true },
  'otd:2026-09-27:1': { bumps: 0, bumped: false },
  'k-streak-5': { bumps: 1, bumped: false },
};

export const handlers = [
  http.get('*/api/sheet/latest', () => HttpResponse.json(sheetFixture())),
  http.get('*/api/sheet/:date/bumps', () => HttpResponse.json(bumpsFixture)),
  http.get('*/api/sheet/:date', () => HttpResponse.json(sheetFixture())),
  http.post('*/api/sheet/bumps', () => HttpResponse.json({ bumps: 3, bumped: true })),
  http.delete('*/api/sheet/bumps', () => HttpResponse.json({ bumps: 2, bumped: false })),
];
```

Create `frontend/src/features/sheet/components/BumpButton.tsx`:

```tsx
import { useBumpToggle, type BumpState } from '../api';

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
  date: string;
  postKey: string;
  /** Null when this browser cannot remember a device id: the count shows, the button is off. */
  deviceId: string | null;
  state: BumpState | undefined;
  /** The id of the note that says why bumps are off. */
  noteId: string;
}

/** 🤜🤛 and the count. Nobody is ever shown who bumped; you can bump a post about yourself. */
export function BumpButton({ date, postKey, deviceId, state, noteId }: BumpButtonProps) {
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
  return <LiveBumpButton date={date} postKey={postKey} deviceId={deviceId} state={state} />;
}

function LiveBumpButton({
  date,
  postKey,
  deviceId,
  state,
}: {
  date: string;
  postKey: string;
  deviceId: string;
  state: BumpState | undefined;
}) {
  const { send, failed } = useBumpToggle(date, deviceId, postKey);
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

- [ ] **Step 9: Run the tests and make sure they pass**

Run: `cd frontend && pnpm typecheck && pnpm exec vitest run src/features/sheet/api.test.ts src/features/sheet/components/BumpButton.test.tsx`

Expected: tsc exits 0 (schema regenerated from the backend); 7 passed.

- [ ] **Step 10: Commit**

From the worktree root:

```bash
git add frontend/src/features/sheet/api.test.ts frontend/src/features/sheet/components/BumpButton.test.tsx frontend/src/features/sheet/api.ts frontend/src/features/sheet/mocks.ts frontend/src/features/sheet/components/BumpButton.tsx
git commit -m "feat(sheet): sheet queries and an optimistic, ordered bump button" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 4.3 The page

- [ ] **Step 11: Write the failing test**

Create `frontend/src/features/sheet/explainers.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { sheetExplainers } from './explainers';

const sources = import.meta.glob(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

function texts(): [string, string][] {
  return Object.entries(sheetExplainers).flatMap(([key, e]) => [
    [key, e.what] as [string, string],
    ...(e.read ?? []).map((t): [string, string] => [key, t]),
    ...e.computed.map((t): [string, string] => [key, t]),
  ]);
}

describe('sheet explainers', () => {
  it('has an entry for every explainer the feature wires in, and wires in every entry', () => {
    const wired = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/sheetExplainers\.(\w+)/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(wired)).toEqual(new Set(Object.keys(sheetExplainers)));
  });

  it('uses neutral pronouns, says Sunday and never says class', () => {
    for (const [key, text] of texts()) {
      expect(text, key).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
      expect(text, key).not.toMatch(/\bclass(es)?\b/i);
      expect(text, key).not.toMatch(/\bevents?\b/i);
    }
  });

  it('says the numbers and look-backs ignore the time filter', () => {
    for (const e of Object.values(sheetExplainers)) {
      expect(e.computed.join(' ')).toContain('time filters do not apply');
      expect(e.scope).toBeUndefined();
    }
  });
});
```

Create `frontend/src/features/sheet/pages/SheetPage.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../../insights/mocks';
import { newerText } from '../components/Masthead';
import { sheetExplainers } from '../explainers';
import { onThisDayPost, postFixture, sheetFixture, trophyPost } from '../mocks';
import { SheetPage } from './SheetPage';

afterEach(() => {
  clearMe();
  localStorage.clear();
  vi.restoreAllMocks();
});

function renderAt(route = '/sheet/2026-09-27') {
  return renderWithProviders(<SheetPage />, { route, path: '/sheet/:date' });
}

describe('SheetPage', () => {
  it('holds the page with one loading status, then shows the issue', async () => {
    server.use(
      http.get('*/api/sheet/:date', async () => {
        await delay(50);
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderAt();
    expect(screen.getAllByRole('status')).toHaveLength(1);
    expect(screen.getByRole('status', { name: 'Loading the Sunday Sheet' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Loading the Sunday Sheet' })).toBeNull();
  });

  it('shows the masthead, the four numbers, the feed in order and More closed', async () => {
    renderAt();
    expect(await screen.findByText('Sep 27, 2026 · Issue 310')).toBeInTheDocument();
    const numbers = screen.getByRole('region', { name: 'This Sunday in numbers' });
    for (const [label, value] of [
      ['Shooters', '23'],
      ['Field median', '39'],
      ['Top score', '49'],
      ['Trophies', '13'],
    ] as const) {
      expect(within(numbers).getByText(label)).toBeInTheDocument();
      expect(within(numbers).getByText(value)).toBeInTheDocument();
    }
    const posts = within(screen.getByRole('list', { name: 'Posts' })).getAllByRole('listitem');
    expect(posts.map((p) => p.dataset['postType'])).toEqual(['milestone', 'trophy', 'on_this_day']);
    expect(posts[0]).toHaveTextContent('New personal best for Ike Hadley: 46.');
    expect(screen.getByText('All round types · not affected by the filters')).toBeInTheDocument();
    expect(within(posts[1] as HTMLElement).getByRole('link', { name: 'Amy Ace' })).toHaveAttribute(
      'href',
      '/shooters/1',
    );
    const more = screen.getByText('More from this Sunday (1)').closest('details');
    expect(more).not.toHaveAttribute('open');
    expect(
      within(more as HTMLElement).getByRole('region', { name: 'Streaks' }),
    ).toBeInTheDocument();
  });

  it('links the previous issue and all issues, and the latest has no next', async () => {
    renderAt();
    const nav = await screen.findByRole('navigation', { name: 'Issues' });
    expect(within(nav).getByRole('link', { name: '← Previous issue' })).toHaveAttribute(
      'href',
      '/sheet/2026-09-13',
    );
    expect(within(nav).getByRole('link', { name: 'All issues' })).toHaveAttribute(
      'href',
      '/events',
    );
    expect(within(nav).queryByRole('link', { name: 'Next issue →' })).toBeNull();
  });

  it('asks for the latest issue when the URL names no date', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/latest', () => {
        asked.push('latest');
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderWithProviders(<SheetPage />, { route: '/', path: '/' });
    expect(await screen.findByText('Sep 27, 2026 · Issue 310')).toBeInTheDocument();
    expect(asked).toEqual(['latest']);
  });

  it('asks for the issue of the date in the URL, and a past issue links the next one', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/:date', ({ params }) => {
        asked.push(String(params['date']));
        return HttpResponse.json(
          sheetFixture({
            masthead: {
              date: '2026-09-13',
              issue: 309,
              previous: null,
              next: '2026-09-27',
              latest: false,
              newer: null,
            },
          }),
        );
      }),
    );
    renderAt('/sheet/2026-09-13');
    const nav = await screen.findByRole('navigation', { name: 'Issues' });
    expect(asked).toEqual(['2026-09-13']);
    expect(within(nav).getByRole('link', { name: 'Next issue →' })).toHaveAttribute(
      'href',
      '/sheet/2026-09-27',
    );
    expect(within(nav).queryByRole('link', { name: '← Previous issue' })).toBeNull();
  });

  it('says there is no Sheet for a date without one, and links the way back', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          { error: { code: 'sheet_not_found', message: 'No Sunday Sheet' } },
          { status: 404 },
        ),
      ),
    );
    renderAt('/sheet/2026-09-26');
    expect(await screen.findByText('No Sunday Sheet for this date')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Latest issue' })).toHaveAttribute('href', '/');
  });

  it('says so when the issue fails to load', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'Boom' } }, { status: 500 }),
      ),
    );
    renderAt();
    expect(await screen.findByText("Couldn't load the Sunday Sheet")).toBeInTheDocument();
  });

  it('says so when a Sunday has no posts yet', async () => {
    server.use(
      http.get('*/api/sheet/:date', () => HttpResponse.json(sheetFixture({ posts: [], more: [] }))),
    );
    renderAt();
    expect(await screen.findByText('Nothing to report for this Sunday yet')).toBeInTheDocument();
    expect(screen.queryByText(/More from this Sunday/)).toBeNull();
  });

  it('shows the counts but turns bumps off when this browser cannot remember a device', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => undefined);
    renderAt();
    expect(await screen.findByText('Bumps need this browser to remember you')).toBeInTheDocument();
    const button = await screen.findByRole('button', { name: 'Fist bump, 5 bumps' });
    expect(button).toBeDisabled();
  });

  it('sends this device’s id with the bump counts', async () => {
    const asked: (string | null)[] = [];
    server.use(
      http.get('*/api/sheet/:date/bumps', ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('device_id'));
        return HttpResponse.json({});
      }),
    );
    renderAt();
    await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' });
    await vi.waitFor(() => expect(asked).toHaveLength(1));
    expect(asked[0]).toBe(localStorage.getItem('sc.device'));
  });

  it('reads the viewer’s own insight post in the second person', async () => {
    setMe(3);
    renderAt();
    const posts = await screen.findByRole('list', { name: 'Posts' });
    expect(within(posts).getAllByRole('listitem')[0]).toHaveTextContent('New personal best: 46.');
  });

  it('notes a newer Sunday without full results and links it', async () => {
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            masthead: {
              ...sheetFixture().masthead,
              newer: { date: '2026-10-04', has_scores: false, head_count: 14, n_shooters: 0 },
            },
          }),
        ),
      ),
    );
    renderAt();
    expect(
      await screen.findByText(
        'Newer Sunday, Oct 4, 2026: Attendance only — 14 shooters, no scores recorded.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See Oct 4, 2026' })).toHaveAttribute(
      'href',
      '/events/2026-10-04',
    );
    const partial = { date: '2026-10-04', has_scores: true, head_count: null, n_shooters: 6 };
    expect(newerText(partial)).toBe('Partial results — 6 shooters so far');
    expect(newerText({ ...partial, has_scores: false })).toBe('No scores recorded');
  });

  it('lists everyone who earned a trophy: eight at first, the rest in place', async () => {
    const holders = Array.from({ length: 10 }, (_, i) => ({
      shooter_id: 100 + i,
      name: `Pat Shooter${String(i + 1)}`,
    }));
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            posts: [
              {
                ...trophyPost,
                trophy: {
                  code: 'first_win',
                  title: 'First win',
                  art_key: 'first_win',
                  metal: null,
                  holders,
                },
              },
            ],
          }),
        ),
      ),
    );
    const { user } = renderAt();
    const list = await screen.findByRole('list', { name: 'Earned by' });
    const links = within(list).getAllByRole('link', { hidden: true });
    expect(links.map((a) => a.getAttribute('href'))).toEqual(
      holders.map((h) => `/shooters/${String(h.shooter_id)}`),
    );
    expect(within(list).getAllByRole('link')).toHaveLength(8);
    await user.click(screen.getByRole('button', { name: '+2 more' }));
    expect(within(list).getAllByRole('link')).toHaveLength(10);
    expect(screen.getByRole('button', { name: 'Show fewer' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('keeps the insight card’s New tag, extra charts and "How we worked it out"', async () => {
    const insight = insightFixture({ is_new: true });
    const also = { ...insight.chart, label: 'Turnout per Sunday', label_you: null, also: [] };
    server.use(
      http.get('*/api/sheet/:date', () =>
        HttpResponse.json(
          sheetFixture({
            posts: [
              postFixture({ insight: { ...insight, chart: { ...insight.chart, also: [also] } } }),
              onThisDayPost,
            ],
          }),
        ),
      ),
    );
    const { user } = renderAt();
    const [post, otd] = within(await screen.findByRole('list', { name: 'Posts' })).getAllByRole(
      'listitem',
    ) as [HTMLElement, HTMLElement];
    expect(within(post).getByText('New')).toBeInTheDocument();
    expect(
      within(post).getByRole('link', { name: 'See the chart: Turnout per Sunday' }),
    ).toBeInTheDocument();
    await user.click(within(post).getByRole('button', { name: 'How we worked it out' }));
    expect(within(post).getByText('The best round beats every earlier round.')).toBeInTheDocument();
    await user.click(within(otd).getByRole('button', { name: 'How we worked it out' }));
    expect(within(otd).getByText(sheetExplainers.onThisDay.what)).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/sheet/routes.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { routes } from './routes';

describe('sheet routes', () => {
  it('serve an issue at /sheet/:date', async () => {
    renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
      route: '/sheet/2026-09-27',
    });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
  });
});
```

In `frontend/src/app/registry.test.ts`, replace:

```ts
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
  '/shooters': NO_FILTERS,
  '/shooters/:id': BOTH_FILTERS,
```

with:

```ts
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
  '/sheet/:date': NO_FILTERS,
  '/shooters': NO_FILTERS,
  '/shooters/:id': BOTH_FILTERS,
```

- [ ] **Step 12: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/sheet src/app/registry.test.ts`

Expected: FAIL: unresolved `./explainers`, `./SheetPage`, `./routes`; `registry.test.ts` "declares the audited filters" fails (no `/sheet/:date` route yet).

- [ ] **Step 13: Write the implementation**

Create `frontend/src/features/sheet/explainers.ts`:

```ts
import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the Sheet's numbers and "On this day" posts, written against
 * api/routes/sheet.py and analytics/sheet.py (STYLE.md: no jargon, neutral pronouns, "Sunday" not
 * "event").
 */
const explainers = {
  shooters: {
    what: 'How many people have at least one recorded score this Sunday.',
    computed: [
      'Counts shooters with a recorded round, not everyone who came, so it can be lower than the head count.',
      'All round types count; the round-type and time filters do not apply.',
    ],
  },
  median: {
    what: 'The middle score this Sunday: half the rounds were this or better, half this or worse.',
    computed: [
      'Every round that day counts, second rounds included. Sorted by score, the middle one is taken.',
      'The round-type and time filters do not apply.',
    ],
  },
  top: {
    what: 'The best single round this Sunday, out of 50.',
    computed: [
      'The highest score among all rounds that day, second rounds included.',
      'The round-type and time filters do not apply.',
    ],
  },
  trophies: {
    what: 'How many trophies people earned this Sunday.',
    read: ['Each trophy has its own post below, naming everyone who earned it.'],
    computed: [
      'Counts every trophy earned that day: two people earning the same trophy count as two.',
      'The round-type and time filters do not apply.',
    ],
  },
  onThisDay: {
    what: 'The Sundays closest to this Sunday’s date one, two and three years ago, and who won them.',
    computed: [
      'For each of the last three years we take this Sunday’s date that many years back (29 February becomes 28 February) and pick the Sunday within three days of it, the earlier one if two are equally close.',
      'Winners: everyone whose best round of that Sunday was first, so a tie lists every winner. A Sunday with no scores shows only its head count.',
      'The round-type and time filters do not apply.',
    ],
  },
} satisfies Record<string, Explainer>;

/** Typed by key, so a wired-in lookup is never undefined. */
export const sheetExplainers: Record<keyof typeof explainers, Explainer> = explainers;
```

Create `frontend/src/features/sheet/components/Masthead.tsx`:

```tsx
import { Link } from 'react-router';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { formatDay } from '../../home/format';
import type { SheetIssue } from '../api';

const LINK = 'inline-flex min-h-11 items-center rounded-button px-2 underline underline-offset-2';

type Newer = NonNullable<SheetIssue['masthead']['newer']>;

/** Home's Latest Sunday wording for a Sunday without full results. */
export function newerText(newer: Newer): string {
  if (newer.has_scores) return `Partial results — ${String(newer.n_shooters)} shooters so far`;
  return newer.head_count === null
    ? 'No scores recorded'
    : `Attendance only — ${String(newer.head_count)} shooters, no scores recorded`;
}

/** The latest issue points at a newer Sunday that has no full results yet. */
function NewerSunday({ newer }: { newer: Newer }) {
  const link = useRoundTypeLink(`/events/${newer.date}`);
  return (
    <p className="flex flex-wrap items-center gap-x-2 rounded-card bg-surface px-3 py-2 text-sm">
      <span>{`Newer Sunday, ${formatDay(newer.date)}: ${newerText(newer)}.`}</span>
      <Link to={link} className={LINK}>
        {`See ${formatDay(newer.date)}`}
      </Link>
    </p>
  );
}

/**
 * "THE SUNDAY SHEET", the Sunday, its issue number and the way to the other issues; on the latest
 * issue, a note about a newer Sunday that has no full results yet.
 */
export function Masthead({ issue }: { issue: SheetIssue }) {
  const { date, issue: number, previous, next, newer } = issue.masthead;
  const previousLink = useRoundTypeLink(previous === null ? '/' : `/sheet/${previous}`);
  const nextLink = useRoundTypeLink(next === null ? '/' : `/sheet/${next}`);
  const allIssues = useRoundTypeLink('/events');
  return (
    <section
      aria-labelledby="sheet-title"
      className="flex flex-col gap-2 rounded-card border-y-4 border-accent bg-elevated px-4 py-3 text-text"
    >
      <p className="text-xs uppercase tracking-widest text-text-muted">Sunday Clays</p>
      <h1 id="sheet-title" className="text-3xl font-bold uppercase tracking-wide">
        The Sunday Sheet
      </h1>
      <p className="text-sm text-text-muted">{`${formatDay(date)} · Issue ${String(number)}`}</p>
      <nav aria-label="Issues" className="-mx-2 flex flex-wrap items-center gap-x-2">
        {previous !== null && (
          <Link to={previousLink} className={LINK}>
            ← Previous issue
          </Link>
        )}
        {next !== null && (
          <Link to={nextLink} className={LINK}>
            Next issue →
          </Link>
        )}
        <Link to={allIssues} className={LINK}>
          All issues
        </Link>
      </nav>
      {newer !== null && <NewerSunday newer={newer} />}
    </section>
  );
}
```

Create `frontend/src/features/sheet/components/Numbers.tsx`:

```tsx
import { Card } from '../../../components/ui/Card';
import { Stat } from '../../../components/ui/Stat';
import { formatScore } from '../../home/format';
import type { SheetIssue } from '../api';
import { sheetExplainers } from '../explainers';

/** The four numbers of the Sunday: shooters, field median, top score and trophies earned. */
export function Numbers({ issue }: { issue: SheetIssue }) {
  const n = issue.numbers;
  return (
    <Card title="This Sunday in numbers" subtitle="Not affected by the time filter">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Shooters" value={String(n.shooters)} explainer={sheetExplainers.shooters} />
        <Stat
          label="Field median"
          value={formatScore(n.median)}
          explainer={sheetExplainers.median}
        />
        <Stat label="Top score" value={formatScore(n.top_score)} explainer={sheetExplainers.top} />
        <Stat label="Trophies" value={String(n.trophies)} explainer={sheetExplainers.trophies} />
      </div>
    </Card>
  );
}
```

Create `frontend/src/features/sheet/components/PostCard.tsx`:

```tsx
import { useId, useState } from 'react';
import { Link } from 'react-router';
import { ExplainerPanel, ExplainerToggle } from '../../../components/ui/Explainer';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { TrophyIcon } from '../../achievements/components/TrophyIcon';
import { chartHref } from '../../insights/chartLink';
import { InsightExplainer } from '../../insights/components/InsightExplainer';
import { isMine } from '../../insights/components/InsightList';
import { Segments } from '../../insights/segments';
import type { BumpState, SheetPost, SheetPostType } from '../api';
import { sheetExplainers } from '../explainers';
import { BumpButton } from './BumpButton';

export const TYPE_LABELS: Record<SheetPostType, string> = {
  milestone: 'Milestone',
  improvement: 'On the up',
  trophy: 'Trophy unlocked',
  conditions: 'The day',
  welcome: 'Welcome',
  on_this_day: 'On this day',
  other: 'From the Sunday',
};

/** The headline names this many holders (analytics/sheet.py NAMES_SHOWN); more get a list. */
export const HEADLINE_NAMES = 3;
/** The holder list shows this many names until "+N more" opens the rest in place. */
export const HOLDERS_SHOWN = 8;

const ACTION =
  'inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline';

type Holder = NonNullable<SheetPost['trophy']>['holders'][number];

/** Everyone who earned the trophy, each linked; past HOLDERS_SHOWN the rest open in place. */
function TrophyHolders({ holders }: { holders: Holder[] }) {
  const [all, setAll] = useState(false);
  const listId = useId();
  const extra = holders.length - HOLDERS_SHOWN;
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p className="text-sm text-text-muted">Earned by</p>
      <ul id={listId} aria-label="Earned by" className="flex flex-wrap gap-x-3">
        {holders.map((h, i) => (
          <li key={h.shooter_id} hidden={!all && i >= HOLDERS_SHOWN}>
            <Link
              to={`/shooters/${String(h.shooter_id)}`}
              className="inline-flex min-h-11 items-center underline underline-offset-2"
            >
              {h.name}
            </Link>
          </li>
        ))}
      </ul>
      {extra > 0 && (
        <button
          type="button"
          aria-expanded={all}
          aria-controls={listId}
          onClick={() => setAll((v) => !v)}
          className="min-h-11 self-start rounded-button px-3 text-sm text-text-muted hover:text-text"
        >
          {all ? 'Show fewer' : `+${String(extra)} more`}
        </button>
      )}
    </div>
  );
}

/** An insight post's extra charts (its `chart.also`), as Home's insight cards linked them. */
function AlsoLinks({ insight, you }: { insight: NonNullable<SheetPost['insight']>; you: boolean }) {
  const viewerWindow = useExplicitWindow();
  return insight.chart.also.map((extra, i) => {
    const text = you && extra.label_you ? extra.label_you : extra.label;
    return (
      <Link
        key={`${String(i)}-${extra.anchor ?? ''}`}
        to={chartHref(extra, viewerWindow)}
        aria-label={`See the chart: ${text}`}
        className={ACTION}
      >
        {text}
      </Link>
    );
  });
}

export interface PostCardProps {
  post: SheetPost;
  date: string;
  deviceId: string | null;
  bumps: BumpState | undefined;
  meId: number | null;
  /** The id of the note that says why bumps are off. */
  noteId: string;
}

/**
 * One post: its type, a "New" tag, its headline (names link to profiles), trophy art and everyone
 * who earned a trophy, the bump button, any extra charts and "How we worked it
 * out" (an insight's own explainer, or the "On this day" one). The viewer's own single-shooter
 * insight reads in the second person.
 */
export function PostCard({ post, date, deviceId, bumps, meId, noteId }: PostCardProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const insight = post.insight ?? null;
  const you = insight !== null && isMine(insight, meId);
  const headline = you && insight.headline_you !== null ? insight.headline_you : post.headline;
  const holders = post.trophy?.holders ?? [];
  const explained = insight !== null || post.on_this_day != null;
  return (
    <li
      data-post-key={post.post_key}
      data-post-type={post.type}
      className="flex min-w-0 flex-col gap-2 rounded-card bg-elevated p-4 text-text"
    >
      <p className="text-xs font-medium uppercase tracking-wide text-accent">
        {TYPE_LABELS[post.type]}
      </p>
      <div className="flex min-w-0 items-start gap-3">
        {post.trophy != null && (
          <TrophyIcon
            artKey={post.trophy.art_key}
            metal={post.trophy.metal}
            locked={false}
            size={48}
          />
        )}
        <p className="min-w-0 break-words text-base">
          {insight?.is_new === true && (
            <span className="mr-2 rounded-button bg-primary px-2 py-0.5 align-middle text-xs font-bold">
              New
            </span>
          )}
          <Segments segments={headline} />
        </p>
      </div>
      {holders.length > HEADLINE_NAMES && <TrophyHolders holders={holders} />}
      <div data-share-exclude="" className="flex flex-wrap items-center gap-2">
        <BumpButton
          date={date}
          postKey={post.post_key}
          deviceId={deviceId}
          state={bumps}
          noteId={noteId}
        />
        {insight !== null && <AlsoLinks insight={insight} you={you} />}
        {explained && (
          <ExplainerToggle
            label="How we worked it out"
            panelId={panelId}
            open={open}
            onToggle={() => setOpen((v) => !v)}
          />
        )}
      </div>
      {open &&
        (insight !== null ? (
          <InsightExplainer id={panelId} insight={insight} you={you} />
        ) : (
          <ExplainerPanel id={panelId} explainer={sheetExplainers.onThisDay} />
        ))}
    </li>
  );
}
```

Create `frontend/src/features/sheet/components/Feed.tsx`:

```tsx
import { EmptyState } from '../../../components/ui/EmptyState';
import type { BumpCounts, SheetIssue } from '../api';
import { PostCard } from './PostCard';

export const BUMPS_OFF = 'Bumps need this browser to remember you';

export interface FeedProps {
  issue: SheetIssue;
  bumps: BumpCounts | undefined;
  deviceId: string | null;
  meId: number | null;
  noteId: string;
}

/** The Sunday's posts in the server's order (best first, interleaved by type). */
export function Feed({ issue, bumps, deviceId, meId, noteId }: FeedProps) {
  const date = issue.masthead.date;
  return (
    <section aria-labelledby="sheet-feed" className="flex min-w-0 flex-col gap-3">
      <div>
        <h2 id="sheet-feed" className="text-lg font-medium">
          This Sunday
        </h2>
        <p className="text-sm text-text-muted">All round types · not affected by the filters</p>
      </div>
      {deviceId === null && (
        <p id={noteId} className="text-sm text-text-muted">
          {BUMPS_OFF}
        </p>
      )}
      {issue.posts.length === 0 ? (
        <EmptyState
          title="Nothing to report for this Sunday yet"
          description="Its stories appear here once the results are in."
        />
      ) : (
        <ol aria-label="Posts" className="flex flex-col gap-3">
          {issue.posts.map((post) => (
            <PostCard
              key={post.post_key}
              post={post}
              date={date}
              deviceId={deviceId}
              bumps={bumps?.[post.post_key]}
              meId={meId}
              noteId={noteId}
            />
          ))}
        </ol>
      )}
    </section>
  );
}
```

Create `frontend/src/features/sheet/components/MoreFromSunday.tsx`:

```tsx
import type { BumpCounts, SheetIssue } from '../api';
import { PostCard } from './PostCard';

/** The Sunday's other posts, grouped by family, closed until asked for. Still bumpable. */
export function MoreFromSunday({
  issue,
  bumps,
  deviceId,
  meId,
  noteId,
}: {
  issue: SheetIssue;
  bumps: BumpCounts | undefined;
  deviceId: string | null;
  meId: number | null;
  noteId: string;
}) {
  const total = issue.more.reduce((n, group) => n + group.posts.length, 0);
  if (total === 0) return null;
  return (
    <details className="min-w-0 rounded-card bg-elevated p-4 text-text">
      <summary className="min-h-11 cursor-pointer py-2 text-base font-medium">
        {`More from this Sunday (${String(total)})`}
      </summary>
      <div className="flex flex-col gap-4 pt-2">
        {issue.more.map((group) => (
          <section key={group.family} aria-label={group.label} className="flex flex-col gap-2">
            <h3 className="text-sm text-text-muted">{group.label}</h3>
            <ol className="flex flex-col gap-3">
              {group.posts.map((post) => (
                <PostCard
                  key={post.post_key}
                  post={post}
                  date={issue.masthead.date}
                  deviceId={deviceId}
                  bumps={bumps?.[post.post_key]}
                  meId={meId}
                  noteId={noteId}
                />
              ))}
            </ol>
          </section>
        ))}
      </div>
    </details>
  );
}
```

Create `frontend/src/features/sheet/components/SheetSkeleton.tsx`:

```tsx
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';

/**
 * Holds the masthead, the numbers, the lead and the first posts at about their final height while
 * the issue loads, so nothing jumps when it arrives. One status for the lot; the rest is hidden
 * from assistive tech.
 */
export function SheetSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Card className="min-h-36">
        <Skeleton label="Loading the Sunday Sheet" lines={4} />
      </Card>
      <div aria-hidden="true" className="flex flex-col gap-4">
        <Card className="min-h-36">
          <Skeleton lines={3} />
        </Card>
        <Card className="min-h-48">
          <Skeleton lines={5} />
        </Card>
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className="min-h-32">
            <Skeleton lines={3} />
          </Card>
        ))}
      </div>
    </div>
  );
}
```

Create `frontend/src/features/sheet/pages/SheetPage.tsx`:

```tsx
import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { EmptyState } from '../../../components/ui/EmptyState';
import { getDeviceId } from '../../../lib/device';
import { getMe } from '../../../lib/me';
import { useBumps, useSheet, type SheetIssue } from '../api';
import { Feed } from '../components/Feed';
import { Masthead } from '../components/Masthead';
import { MoreFromSunday } from '../components/MoreFromSunday';
import { Numbers } from '../components/Numbers';
import { SheetSkeleton } from '../components/SheetSkeleton';

const NOTE_ID = 'sheet-bumps-off';

function SheetBody({ issue, deviceId }: { issue: SheetIssue; deviceId: string | null }) {
  const [meId] = useState<number | null>(getMe);
  const bumps = useBumps(issue.masthead.date, deviceId);
  const shared = { issue, bumps: bumps.data, deviceId, meId, noteId: NOTE_ID };
  return (
    <div className="flex flex-col gap-4">
      <Masthead issue={issue} />
      <Numbers issue={issue} />
      <Feed {...shared} />
      <MoreFromSunday {...shared} />
    </div>
  );
}

function SheetError({ error }: { error: Error }) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState
        title="No Sunday Sheet for this date"
        description="There is a Sheet for every Sunday with full results."
        action={
          <span className="flex flex-wrap justify-center gap-3">
            <Link to="/events" className="inline-flex min-h-11 items-center underline">
              All issues
            </Link>
            <Link to="/" className="inline-flex min-h-11 items-center underline">
              Latest issue
            </Link>
          </span>
        }
      />
    );
  }
  return <EmptyState title="Couldn't load the Sunday Sheet" description={error.message} />;
}

/** The Sunday Sheet: `/sheet/:date` (and, once Home retires, `/` for the latest issue). */
export function SheetPage() {
  const { date } = useParams();
  const sheet = useSheet(date ?? 'latest');
  const [deviceId] = useState<string | null>(getDeviceId);
  if (sheet.isPending) return <SheetSkeleton />;
  if (sheet.isError) return <SheetError error={sheet.error} />;
  return <SheetBody issue={sheet.data} deviceId={deviceId} />;
}
```

Create `frontend/src/features/sheet/routes.tsx`:

```tsx
import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';

/** The Sunday Sheet (Plan 14): one issue per held Sunday. */
export const routes: RouteObject[] = [
  {
    path: '/sheet/:date',
    handle: { filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/SheetPage')).SheetPage }),
  },
];
```

- [ ] **Step 14: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/features/sheet src/lib/device.test.ts src/app`

Expected: all pass.

- [ ] **Step 15: Commit**

From the worktree root:

```bash
git add frontend/src/features/sheet/explainers.test.ts frontend/src/features/sheet/pages/SheetPage.test.tsx frontend/src/features/sheet/routes.test.tsx frontend/src/app/registry.test.ts frontend/src/features/sheet/explainers.ts frontend/src/features/sheet/components/Masthead.tsx frontend/src/features/sheet/components/Numbers.tsx frontend/src/features/sheet/components/PostCard.tsx frontend/src/features/sheet/components/Feed.tsx frontend/src/features/sheet/components/MoreFromSunday.tsx frontend/src/features/sheet/components/SheetSkeleton.tsx frontend/src/features/sheet/pages/SheetPage.tsx frontend/src/features/sheet/routes.tsx
git commit -m "feat(sheet): the Sunday Sheet page at /sheet/:date" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 4.4 Gates

- [ ] **Step 16: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Run: `cd frontend && pnpm test --coverage`

Expected: the whole suite passes; lines and branches stay at or above the ratchet

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 5: Headline and spotlight (insights feature)

**Wave 1** · parallel with: Task 1, Task 2, Task 6 · branch `task/14-5-sheet-lead` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Create: `frontend/src/features/insights/components/SheetLead.tsx`
- Test: `frontend/src/features/insights/components/SheetLead.test.tsx`

**Interfaces:**
- Consumes:
  - `features/insights`: `Insight` (api.ts), `chartHref` (chartLink.ts), `Segments` (segments.tsx), `InsightCard`, `isMine` (components), `insightFixture` (mocks); `lib/timeWindowChoice` `useExplicitWindow`; `components/ui/Card`; `features/shooters/format` `formatDay`.
- Produces:
  - `SheetLead({ headline, recap, spotlight, meId, date }: SheetLeadProps)` where each insight is `Insight | null` and `date` is the issue Sunday; `leadSubtitle(headline, date) -> string` ("Sep 20, 2026 · not affected by the time filter" when the headline is about another Sunday, else "Not affected by the time filter"). It renders the region "Top story" (list "Top story" for the headline and a deck with Show all / Show less and "See the results") and the region "Spotlight" (subtitle "Shooter to know", list "Spotlight"), or nothing when all three are null. Task 8 mounts it in the `hero` slot.

#### 5.1 The lead

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/insights/components/SheetLead.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../mocks';
import { leadSubtitle, SheetLead } from './SheetLead';

const DAY = '2026-09-27';

const hero = insightFixture({
  key: 'hero',
  kind: 'lb.most-improved',
  headline: [
    { t: 'text', v: 'Most improved this year: ' },
    { t: 'shooter', v: 'Amy Ace', id: 1 },
    { t: 'text', v: '.' },
  ],
  subject_id: '1',
});
const recap = insightFixture({
  key: 'recap',
  kind: 'home.sunday-recap',
  family: 'recap',
  subject_type: 'sunday',
  subject_id: '2026-09-27',
  headline: [{ t: 'text', v: '23 shooters came out; the top score was 49.' }],
  headline_you: null,
});
const spotlight = insightFixture(); // Ike Hadley (3), with a "you" twin

describe('SheetLead', () => {
  it('shows the headline with the recap as its deck, then the spotlight', () => {
    renderWithProviders(
      <SheetLead headline={hero} recap={recap} spotlight={spotlight} meId={null} date={DAY} />,
    );
    const lead = screen.getByRole('region', { name: 'Top story' });
    expect(within(lead).getByRole('list', { name: 'Top story' })).toHaveTextContent(
      'Most improved this year: Amy Ace.',
    );
    expect(
      within(lead).getByText('23 shooters came out; the top score was 49.'),
    ).toBeInTheDocument();
    const spot = screen.getByRole('region', { name: 'Spotlight' });
    expect(within(spot).getByText('Shooter to know')).toBeInTheDocument();
    expect(within(spot).getByRole('link', { name: 'Ike Hadley' })).toHaveAttribute(
      'href',
      '/shooters/3',
    );
    expect(lead.compareDocumentPosition(spot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('clamps the deck to three lines until "Show all", and links the results', async () => {
    const { user } = renderWithProviders(
      <SheetLead headline={hero} recap={recap} spotlight={null} meId={null} date={DAY} />,
    );
    const deck = screen.getByText('23 shooters came out; the top score was 49.').closest('p');
    expect(deck).toHaveClass('line-clamp-3');
    await user.click(screen.getByRole('button', { name: 'Show all' }));
    expect(deck).not.toHaveClass('line-clamp-3');
    await user.click(screen.getByRole('button', { name: 'Show less' }));
    expect(deck).toHaveClass('line-clamp-3');
    expect(screen.getByRole('link', { name: 'See the results' })).toHaveAttribute(
      'href',
      expect.stringContaining('/shooters/3?'),
    );
  });

  it('reads the viewer’s own spotlight in the second person', () => {
    renderWithProviders(
      <SheetLead headline={null} recap={null} spotlight={spotlight} meId={3} date={DAY} />,
    );
    expect(screen.getByRole('list', { name: 'Spotlight' })).toHaveTextContent(
      'New personal best: 46.',
    );
    expect(screen.queryByRole('region', { name: 'Top story' })).toBeNull();
  });

  it('shows the deck alone when the Sunday has no headline pick', () => {
    renderWithProviders(
      <SheetLead headline={null} recap={recap} spotlight={null} meId={null} date={DAY} />,
    );
    expect(screen.getByRole('region', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Top story' })).toBeNull();
    expect(screen.getByText('23 shooters came out; the top score was 49.')).toBeInTheDocument();
  });

  it('names the Sunday a headline is about when it is not the issue’s', () => {
    renderWithProviders(
      <SheetLead
        headline={{ ...hero, anchor_date: '2026-09-20' }}
        recap={null}
        spotlight={null}
        meId={null}
        date={DAY}
      />,
    );
    expect(screen.getByText('Sep 20, 2026 · not affected by the time filter')).toBeInTheDocument();
    expect(leadSubtitle(hero, DAY)).toBe('Not affected by the time filter');
    expect(leadSubtitle({ ...hero, anchor_date: null }, DAY)).toBe(
      'Not affected by the time filter',
    );
  });

  it('renders nothing when the Sunday has no lead at all', () => {
    const { container } = renderWithProviders(
      <SheetLead headline={null} recap={null} spotlight={null} meId={null} date={DAY} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/insights/components/SheetLead.test.tsx`

Expected: FAIL: `Failed to resolve import "./SheetLead"`.

- [ ] **Step 3: Write the implementation**

Create `frontend/src/features/insights/components/SheetLead.tsx`:

```tsx
import { useState } from 'react';
import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { formatDay } from '../../shooters/format';
import type { Insight } from '../api';
import { chartHref } from '../chartLink';
import { Segments } from '../segments';
import { InsightCard } from './InsightCard';
import { isMine } from './InsightList';

export interface SheetLeadProps {
  /** The Sunday's hero pick (Home's "Top story"). */
  headline: Insight | null;
  /** The Sunday's pinned recap (Home's "Last Sunday"), shown as the headline's deck. */
  recap: Insight | null;
  /** The Sunday's "Shooter to know". */
  spotlight: Insight | null;
  meId: number | null;
  /** The issue's Sunday: a headline about an earlier Sunday names its date. */
  date: string;
}

/** "Sep 20, 2026 · not affected by the time filter" when the headline is about another Sunday. */
export function leadSubtitle(headline: Insight | null, date: string): string {
  const anchor = headline?.anchor_date ?? null;
  return anchor === null || anchor === date
    ? 'Not affected by the time filter'
    : `${formatDay(anchor)} · not affected by the time filter`;
}

/** The recap under the headline: clamped to 3 lines until "Show all", with its results link. */
function Deck({ recap }: { recap: Insight }) {
  const [all, setAll] = useState(false);
  const viewerWindow = useExplicitWindow();
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <p className={all ? 'text-base text-text-muted' : 'line-clamp-3 text-base text-text-muted'}>
        <Segments segments={recap.headline} />
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          aria-expanded={all}
          onClick={() => setAll((v) => !v)}
          className="min-h-11 rounded-button px-3 text-sm text-text-muted hover:text-text"
        >
          {all ? 'Show less' : 'Show all'}
        </button>
        <Link
          to={chartHref(recap.chart, viewerWindow)}
          className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline"
        >
          See the results
        </Link>
      </div>
    </div>
  );
}

/**
 * The Sheet's lead (Plan 14): the headline with the recap as its deck, then the spotlight. The
 * viewer's own single-shooter story reads in the second person. Picks may be about the Sunday
 * before the issue's; then the subtitle names that Sunday, as Home's "Top story" did. Nothing at all when the Sunday
 * has none of the three.
 */
export function SheetLead({ headline, recap, spotlight, meId, date }: SheetLeadProps) {
  if (headline === null && recap === null && spotlight === null) return null;
  return (
    <div className="flex min-w-0 flex-col gap-4">
      {(headline !== null || recap !== null) && (
        <Card title="Top story" subtitle={leadSubtitle(headline, date)}>
          <div className="flex min-w-0 flex-col gap-3">
            {headline !== null && (
              <ul aria-label="Top story" className="flex flex-col gap-3">
                <InsightCard insight={headline} you={isMine(headline, meId)} />
              </ul>
            )}
            {recap !== null && <Deck recap={recap} />}
          </div>
        </Card>
      )}
      {spotlight !== null && (
        <Card title="Spotlight" subtitle="Shooter to know">
          <ul aria-label="Spotlight" className="flex flex-col gap-3">
            <InsightCard insight={spotlight} you={isMine(spotlight, meId)} />
          </ul>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/features/insights`

Expected: all pass (6 new).

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add frontend/src/features/insights/components/SheetLead.test.tsx frontend/src/features/insights/components/SheetLead.tsx
git commit -m "feat(sheet): the Sheet lead, headline with its recap deck and the spotlight" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 5.2 Gates

- [ ] **Step 6: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 6: "Which one are you?"

**Wave 1** · parallel with: Task 1, Task 2, Task 5 · branch `task/14-6-which-one` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Modify: `frontend/src/lib/me.ts` (replace the whole file: add skip)
- Create: `frontend/src/features/sheet/components/WhichOneAreYou.tsx`
- Test: `frontend/src/lib/me.test.ts`
- Test: `frontend/src/features/sheet/components/WhichOneAreYou.test.tsx`

**Interfaces:**
- Consumes:
  - `GET /api/shooters?q=` (existing); `api/client`; `components/ui` `Button`, `Card`; `features/shooters/mocks` `shooterList` (tests).
- Produces:
  - `lib/me.ts`: `isMeSkipped(): boolean`, `skipMe(): void` (`localStorage["sc.me.skip"] = "1"`); `setMe(id)` now also clears the skip; `getMe`, `clearMe` unchanged.
  - `WhichOneAreYou({ onPicked: (id: number) => void; onSkipped: () => void })`: the region "Which one are you?" with the input "Your name", the list "Matching shooters" (a button per name; searches from 2 characters, at most 8) and the button "Not a shooter / skip". Its query key `["/api/shooters", { q, active: false }]` matches `useShooters`.

#### 6.1 Skip, and the question card

- [ ] **Step 1: Write the failing test**

In `frontend/src/lib/me.test.ts`, replace:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, getMe, setMe } from './me';

afterEach(() => {
```

with:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, getMe, isMeSkipped, setMe, skipMe } from './me';

afterEach(() => {
```

In `frontend/src/lib/me.test.ts`, replace:

```ts
    expect(() => setMe(1)).not.toThrow();
    expect(() => clearMe()).not.toThrow();
  });
});
```

with:

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
});
```

Create `frontend/src/features/sheet/components/WhichOneAreYou.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
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
    expect(asked).toEqual([]);
  });

  it('says when no shooter matches', async () => {
    searched();
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'Zz');
    expect(await screen.findByText('No shooter matches “Zz”.')).toBeInTheDocument();
  });

  it('says so when the search fails', async () => {
    server.use(
      http.get('*/api/shooters', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    const { user } = renderWithProviders(<WhichOneAreYou onPicked={vi.fn()} onSkipped={vi.fn()} />);
    await user.type(screen.getByLabelText('Your name'), 'Hadley');
    expect(await screen.findByText('Couldn’t search the shooters just now.')).toBeInTheDocument();
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

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/me.test.ts src/features/sheet/components/WhichOneAreYou.test.tsx`

Expected: FAIL: `isMeSkipped is not a function`; `Failed to resolve import "./WhichOneAreYou"`.

- [ ] **Step 3: Write the implementation**

Replace the whole of `frontend/src/lib/me.ts` with:

```ts
/** "That's me" personalization: the viewer's own shooter id, kept only in this browser. */
const KEY = 'sc.me';
/** "Not a shooter / skip" on the Sunday Sheet (Plan 14): stop asking "Which one are you?". */
const SKIP_KEY = 'sc.me.skip';

export function getMe(): number | null {
  try {
    const raw = localStorage.getItem(KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

/** Remembers the viewer's shooter; picking someone also undoes an earlier skip. */
export function setMe(id: number): void {
  try {
    localStorage.setItem(KEY, String(id));
    localStorage.removeItem(SKIP_KEY);
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

Create `frontend/src/features/sheet/components/WhichOneAreYou.tsx`:

```tsx
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useId, useState } from 'react';
import { api, unwrap } from '../../../api/client';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { setMe, skipMe } from '../../../lib/me';

const MIN_QUERY = 2;
const SHOWN = 8;

/** The shooters list for a name search; the key matches features/shooters' `useShooters`. */
function useNameSearch(q: string) {
  return useQuery({
    queryKey: ['/api/shooters', { q, active: false }],
    queryFn: () => unwrap(api.GET('/api/shooters', { params: { query: { q } } })),
    enabled: q.length >= MIN_QUERY,
    placeholderData: keepPreviousData,
  });
}

/**
 * "Which one are you?" (Plan 14): pick yourself once and this browser remembers it (lib/me), or
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
  const search = useNameSearch(query);
  const asked = query.length >= MIN_QUERY;
  const matches = asked ? (search.data ?? []).slice(0, SHOWN) : [];
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
        {asked && search.isError && (
          <p className="text-sm text-text-muted">Couldn’t search the shooters just now.</p>
        )}
        {asked && search.isSuccess && matches.length === 0 && (
          <p className="text-sm text-text-muted">{`No shooter matches “${query}”.`}</p>
        )}
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

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/lib src/features/sheet src/features/shooters`

Expected: all pass (the "That's me" button still works through `setMe`).

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add frontend/src/lib/me.test.ts frontend/src/features/sheet/components/WhichOneAreYou.test.tsx frontend/src/lib/me.ts frontend/src/features/sheet/components/WhichOneAreYou.tsx
git commit -m 'feat(sheet): "Which one are you?" with skip' -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 6.2 Gates

- [ ] **Step 6: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 7: Admin ops: fist bumps

**Wave 3** · parallel with: Task 4 · branch `task/14-7-admin-bumps` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Modify: `frontend/src/features/admin-ops/api.ts`, `mocks.ts`, `pages/OpsPage.tsx`
- Create: `frontend/src/features/admin-ops/components/BumpsPanel.tsx`
- Test: `frontend/src/features/admin-ops/components/BumpsPanel.test.tsx`, `pages/OpsPage.test.tsx`

**Interfaces:**
- Consumes:
  - Task 3 through `pnpm gen:api`: `GET /api/admin/sheet/bumps`, `DELETE /api/admin/sheet/bumps/{post_key}`.
  - `features/admin/api` `JsonOf`; `features/admin/components/AdminError` `AdminError`; `features/home/format` `formatDay`; `components/ui` `Button`, `Card`, `Skeleton`.
- Produces:
  - `admin-ops/api.ts`: `BumpedPost` type, `useBumpedPosts()`, `useWipeBumps()` (invalidates the list and the audit log); `mocks.ts`: `bumpedPosts`, handlers for both routes; `BumpsPanel()`; the ops page card "Fist bumps".

#### 7.1 The fist bumps card

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/admin-ops/components/BumpsPanel.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { auditEntries, bumpedPosts } from '../mocks';
import { BumpsPanel } from './BumpsPanel';

describe('BumpsPanel', () => {
  it('lists bumped posts with their counts, dates and keys, and flags stale ones', async () => {
    renderWithProviders(<BumpsPanel />);
    const list = await screen.findByRole('list', { name: 'Bumped posts' });
    const [first, stale] = within(list).getAllByRole('listitem');
    expect(first).toHaveTextContent('New personal best for Ike Hadley: 46.');
    expect(first).toHaveTextContent('4 bumps · Sep 27, 2026');
    expect(first).toHaveTextContent('k-pb-3');
    expect(stale).toHaveTextContent('1 bump · Sep 13, 2026 · no longer on a Sheet');
  });

  it('wipes only after a second, explicit tap, then refreshes the list', async () => {
    const posts = [...bumpedPosts];
    const wiped: string[] = [];
    server.use(
      http.get('*/api/admin/sheet/bumps', () => HttpResponse.json(posts)),
      http.delete('*/api/admin/sheet/bumps/:postKey', ({ params }) => {
        const key = String(params['postKey']);
        wiped.push(key);
        posts.splice(
          posts.findIndex((p) => p.post_key === key),
          1,
        );
        return HttpResponse.json({ post_key: key, wiped: 4 });
      }),
      http.get('*/api/admin/audit', () => HttpResponse.json(auditEntries)),
    );
    const { user } = renderWithProviders(<BumpsPanel />);
    const list = await screen.findByRole('list', { name: 'Bumped posts' });
    const first = within(list).getAllByRole('listitem')[0] as HTMLElement;
    await user.click(within(first).getByRole('button', { name: 'Wipe bumps' }));
    expect(wiped).toEqual([]);
    await user.click(within(first).getByRole('button', { name: 'Keep them' }));
    await user.click(within(first).getByRole('button', { name: 'Wipe bumps' }));
    await user.click(within(first).getByRole('button', { name: 'Yes, wipe 4 bumps' }));
    expect(await screen.findByText('Trophy retired_trophy, 2026-09-13')).toBeInTheDocument();
    expect(screen.queryByText('New personal best for Ike Hadley: 46.')).toBeNull();
    expect(wiped).toEqual(['k-pb-3']);
  });

  it('shows a refused wipe next to the post', async () => {
    server.use(
      http.delete('*/api/admin/sheet/bumps/:postKey', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 }),
      ),
    );
    const { user } = renderWithProviders(<BumpsPanel />);
    const list = await screen.findByRole('list', { name: 'Bumped posts' });
    const first = within(list).getAllByRole('listitem')[0] as HTMLElement;
    await user.click(within(first).getByRole('button', { name: 'Wipe bumps' }));
    await user.click(within(first).getByRole('button', { name: 'Yes, wipe 4 bumps' }));
    expect(await within(first).findByRole('alert')).toHaveTextContent(
      'Admins only — sign in with the admin password.',
    );
  });

  it('says when nothing has been bumped', async () => {
    server.use(http.get('*/api/admin/sheet/bumps', () => HttpResponse.json([])));
    renderWithProviders(<BumpsPanel />);
    expect(await screen.findByText('No bumps yet.')).toBeInTheDocument();
  });

  it('shows a refused list', async () => {
    server.use(
      http.get('*/api/admin/sheet/bumps', () =>
        HttpResponse.json({ error: { code: 'forbidden', message: 'Forbidden' } }, { status: 403 }),
      ),
    );
    renderWithProviders(<BumpsPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Admins only');
  });
});
```

In `frontend/src/features/admin-ops/pages/OpsPage.test.tsx`, replace:

```tsx

describe('OpsPage', () => {
  it('shows data issues, the recompute panel and the audit log', async () => {
    server.use(
      http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)),
```

with:

```tsx

describe('OpsPage', () => {
  it('shows data issues, the recompute panel, fist bumps and the audit log', async () => {
    server.use(
      http.get('*/api/admin/data-issues', () => HttpResponse.json(dataIssues)),
```

In `frontend/src/features/admin-ops/pages/OpsPage.test.tsx`, replace:

```tsx
    expect(await screen.findByRole('table', { name: 'Audit log' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recompute analytics' })).toBeInTheDocument();
  });
```

with:

```tsx
    expect(await screen.findByRole('table', { name: 'Audit log' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Recompute analytics' })).toBeInTheDocument();
    const bumps = screen.getByRole('region', { name: 'Fist bumps' });
    expect(await within(bumps).findByRole('list', { name: 'Bumped posts' })).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/admin-ops`

Expected: FAIL: `Failed to resolve import "./BumpsPanel"` and "…mocks" has no export `bumpedPosts`; OpsPage finds no region "Fist bumps".

- [ ] **Step 3: Write the implementation**

In `frontend/src/features/admin-ops/api.ts`, replace:

```ts

export type DataIssue = JsonOf<paths['/api/admin/data-issues']['get']>[number];
export type AuditEntry = JsonOf<paths['/api/admin/audit']['get']>[number];

export function useDataIssues() {
  return useQuery({
```

with:

```ts

export type DataIssue = JsonOf<paths['/api/admin/data-issues']['get']>[number];
export type AuditEntry = JsonOf<paths['/api/admin/audit']['get']>[number];
export type BumpedPost = JsonOf<paths['/api/admin/sheet/bumps']['get']>[number];

export function useDataIssues() {
  return useQuery({
```

In `frontend/src/features/admin-ops/api.ts`, replace:

```ts
      unwrap(api.POST('/api/admin/recompute', { body })),
  });
}
```

with:

```ts
      unwrap(api.POST('/api/admin/recompute', { body })),
  });
}

/** Sunday Sheet posts with fist bumps, most recently bumped first (Plan 14). */
export function useBumpedPosts() {
  return useQuery({
    queryKey: ['/api/admin/sheet/bumps'],
    queryFn: () => unwrap(api.GET('/api/admin/sheet/bumps')),
  });
}

/** Wipes every bump on one post; the wipe is audited, so the audit log refreshes too. */
export function useWipeBumps() {
  const qc = useQueryClient();
  return useMutation({
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['/api/admin/sheet/bumps'] });
      await qc.invalidateQueries({ queryKey: ['/api/admin/audit'] });
    },
    mutationFn: (postKey: string) =>
      unwrap(
        api.DELETE('/api/admin/sheet/bumps/{post_key}', {
          params: { path: { post_key: postKey } },
        }),
      ),
  });
}
```

In `frontend/src/features/admin-ops/mocks.ts`, replace:

```ts
import { http, HttpResponse } from 'msw';
import type { AuditEntry, DataIssue } from './api';

export const dataIssues: DataIssue[] = [
```

with:

```ts
import { http, HttpResponse } from 'msw';
import type { AuditEntry, BumpedPost, DataIssue } from './api';

export const dataIssues: DataIssue[] = [
```

In `frontend/src/features/admin-ops/mocks.ts`, replace:

```ts
];

// Default handlers: branch-free, exercised by routes.test.tsx.
export const handlers = [
```

with:

```ts
];

export const bumpedPosts: BumpedPost[] = [
  {
    post_key: 'k-pb-3',
    bumps: 4,
    last_at: '2026-09-28T09:15:00Z',
    label: 'New personal best for Ike Hadley: 46.',
    issue_date: '2026-09-27',
    current: true,
  },
  {
    post_key: 'trophy:retired_trophy:2026-09-13',
    bumps: 1,
    last_at: '2026-09-14T20:00:00Z',
    label: 'Trophy retired_trophy, 2026-09-13',
    issue_date: '2026-09-13',
    current: false,
  },
];

// Default handlers: branch-free, exercised by routes.test.tsx.
export const handlers = [
```

In `frontend/src/features/admin-ops/mocks.ts`, replace:

```ts
    HttpResponse.json({ rule_id: 4, job_id: 82 }),
  ),
];
```

with:

```ts
    HttpResponse.json({ rule_id: 4, job_id: 82 }),
  ),
  http.get('*/api/admin/sheet/bumps', () => HttpResponse.json(bumpedPosts)),
  http.delete('*/api/admin/sheet/bumps/:postKey', ({ params }) =>
    HttpResponse.json({ post_key: String(params['postKey']), wiped: 4 }),
  ),
];
```

Create `frontend/src/features/admin-ops/components/BumpsPanel.tsx`:

```tsx
import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatDay } from '../../home/format';
import { AdminError } from '../../admin/components/AdminError';
import { useBumpedPosts, useWipeBumps, type BumpedPost } from '../api';

function BumpedRow({ post }: { post: BumpedPost }) {
  const [confirming, setConfirming] = useState(false);
  const wipe = useWipeBumps();
  const plural = post.bumps === 1 ? 'bump' : 'bumps';
  return (
    <li className="flex flex-col gap-2 border-t border-outline-variant pt-3 first:border-t-0 first:pt-0">
      <p className="break-words">{post.label}</p>
      <p className="text-sm text-text-muted">
        {`${String(post.bumps)} ${plural}`}
        {post.issue_date !== null && ` · ${formatDay(post.issue_date)}`}
        {!post.current && ' · no longer on a Sheet'}
      </p>
      <p className="break-all font-mono text-xs text-text-muted">{post.post_key}</p>
      {confirming ? (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="danger"
            loading={wipe.isPending}
            onClick={() => wipe.mutate(post.post_key)}
          >
            {`Yes, wipe ${String(post.bumps)} ${plural}`}
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            Keep them
          </Button>
        </div>
      ) : (
        <Button variant="tonal" className="self-start" onClick={() => setConfirming(true)}>
          Wipe bumps
        </Button>
      )}
      {wipe.isError && <AdminError error={wipe.error} />}
    </li>
  );
}

/** Admin (Plan 14): every bumped post, with a two-step wipe that the audit log records. */
export function BumpsPanel() {
  const posts = useBumpedPosts();
  if (posts.isPending) return <Skeleton label="Loading bumped posts" />;
  if (posts.isError) return <AdminError error={posts.error} />;
  if (posts.data.length === 0) return <p className="text-text-muted">No bumps yet.</p>;
  return (
    <ul aria-label="Bumped posts" className="flex flex-col gap-3">
      {posts.data.map((post) => (
        <BumpedRow key={post.post_key} post={post} />
      ))}
    </ul>
  );
}
```

Replace the whole of `frontend/src/features/admin-ops/pages/OpsPage.tsx` with:

```tsx
import { Card } from '../../../components/ui/Card';
import { AuditLog } from '../components/AuditLog';
import { BumpsPanel } from '../components/BumpsPanel';
import { DataIssues } from '../components/DataIssues';
import { RecomputePanel } from '../components/RecomputePanel';

export function OpsPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-medium">Data & ops</h1>
      <Card title="Data issues">
        <DataIssues />
      </Card>
      <Card title="Recompute analytics">
        <RecomputePanel />
      </Card>
      <Card title="Fist bumps" subtitle="Sunday Sheet posts with bumps, most recent first">
        <BumpsPanel />
      </Card>
      <Card title="Audit log">
        <AuditLog />
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm typecheck && pnpm exec vitest run src/features/admin-ops`

Expected: tsc exits 0; all pass.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add frontend/src/features/admin-ops/components/BumpsPanel.test.tsx frontend/src/features/admin-ops/pages/OpsPage.test.tsx frontend/src/features/admin-ops/api.ts frontend/src/features/admin-ops/mocks.ts frontend/src/features/admin-ops/components/BumpsPanel.tsx frontend/src/features/admin-ops/pages/OpsPage.tsx
git commit -m "feat(sheet): fist bumps on the admin ops page, with a two-step wipe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 7.2 Gates

- [ ] **Step 6: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 8: The rail and Your Sunday: Home’s pieces move onto the Sheet

**Wave 4** · parallel with: Task 10 · branch `task/14-8-sheet-rail` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

Until Task 9, `/` still renders Home. Home keeps working: its hero slot has no issue, so the insights widget falls back to the home feed. Home loses its On-this-day card (now feed post ⑥) one task early.

**Files:**
- Modify: `frontend/src/lib/windowEvents.ts` (optional fixed range)
- Modify: `frontend/src/features/home/components/TurnoutChart.tsx`, `ClubPulse.tsx`, `MePanel.tsx`, `WidgetSlot.tsx`
- Modify: `frontend/src/features/home/widgets.ts`, `explainers.ts`
- Modify: `frontend/src/features/insights/homeWidget.tsx` (the lead, with `date={issue.masthead.date}`)
- Delete: `frontend/src/features/yir/homeWidget.tsx`, `components/OnThisDayCard.tsx`, `components/OnThisDayCard.test.tsx`
- Modify: `frontend/src/features/yir/api.ts`, `explainers.ts`, `routes.test.tsx`
- Create: `frontend/src/features/sheet/components/YourSunday.tsx`, `SundayDetails.tsx`
- Modify: `frontend/src/features/sheet/pages/SheetPage.tsx` (replace the whole file), `routes.tsx`
- Test: `frontend/src/features/home/components/ClubPulse.test.tsx`, `MePanel.test.tsx`, `explainers.test.ts`
- Test: `frontend/src/features/sheet/components/YourSunday.test.tsx`, `pages/SheetPage.test.tsx`; `frontend/src/app/registry.test.ts`

**Interfaces:**
- Consumes:
  - Task 4: `SheetIssue`, `useSheet`, `useBumps`, the Sheet components and mocks; Task 5: `SheetLead`; Task 6: `WhichOneAreYou`, `isMeSkipped`.
  - `features/home`: `MePanel`, `ClubPulse`, `TurnoutChart`, `WidgetSlot`, `homeWidgets`, `HomeWidget`, `homeExplainers`, mocks `meDetail`, `meRounds`, `seasonEvents`, `homeMeta`; `lib/timeWindowChoice` `daysBack`, `EIGHT_WEEK_DAYS`, `WindowRange`; `components/ui/cx`; `test/charts` `expectChartControls`, `expectExplainer`; `test/lazyChart` `LAZY_CHART`, `LAZY_TEST_TIMEOUT`.
- Produces:
  - `HomeWidgetProps = { meId: number | null; issue?: SheetIssue }` and `HomeWidget.Component: FC<HomeWidgetProps>` (`features/home/widgets.ts`); `WidgetSlot({ slot, widgets, meId, issue? })`.
  - `MePanel({ meId, onCleared, widgets, title = "Your panel", actions? })`; `ClubPulse({ range?: WindowRange })` (fixed window, label "8 weeks to {date}"); `TurnoutChart({ …, explainer? })`; `useWindowEvents(fixed?: WindowRange)`; explainers `pulseSheet`, `pulseHeldSheet`, `pulseTurnoutSheet`, `pulseHighSheet` (no `scope`).
  - `YourSunday({ meId, skipped, widgets, onPicked, onCleared, onSkipped })`, `SundayDetails({ date, latest })`; `SHEET_ORDER` (block → classes) and `SheetPage({ widgets = homeWidgets })` in `pages/SheetPage.tsx`; `/sheet/:date` is `ROUND_TYPE_ONLY`.

#### 8.1 Club pulse on a fixed window

- [ ] **Step 1: Write the failing test**

In `frontend/src/features/home/components/ClubPulse.test.tsx`, replace:

```tsx
    expect(await screen.findByText('No scored Sundays yet')).toBeInTheDocument();
  });
});
```

with:

```tsx
    expect(await screen.findByText('No scored Sundays yet')).toBeInTheDocument();
  });

  it(
    'on the Sunday Sheet, shows the 8 weeks up to the issue whatever the header window says',
    async () => {
      const seen: URLSearchParams[] = [];
      server.use(
        metaHandler(),
        http.get('*/api/events', ({ request }) => {
          seen.push(new URL(request.url).searchParams);
          return HttpResponse.json(seasonEvents);
        }),
      );
      const { user } = renderWithProviders(
        <ClubPulse range={{ from: '2026-07-20', to: '2026-09-13' }} />,
        { route: '/?w=all' },
      );
      const region = await chart();
      const pulse = screen.getByRole('region', { name: 'Club pulse' });
      expect(
        within(pulse).getByText('8 weeks to Sep 13, 2026 · not affected by the time filter'),
      ).toBeInTheDocument();
      expect(seen.map((q) => [q.get('from'), q.get('to')])).toEqual([['2026-07-20', '2026-09-13']]);
      await user.click(within(region).getByRole('button', { name: 'About this chart' }));
      expect(within(region).getByText(/the Sheet always shows the 8 weeks/)).toBeInTheDocument();
      expect(within(region).queryByText(/Last 8 weeks|All time/)).toBeNull();
      await user.click(within(pulse).getByRole('button', { name: 'About Highest score' }));
      expect(within(pulse).getByText(/in those 8 weeks/)).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );
});
```

In `frontend/src/features/home/explainers.test.ts`, replace:

```ts
    expect(homeExplainers.latestMedian.scope).toBeUndefined();
  });
});
```

with:

```ts
    expect(homeExplainers.latestMedian.scope).toBeUndefined();
  });

  it('leaves the Sheet’s fixed 8-week club numbers untagged: the header window does not apply', () => {
    for (const key of [
      'pulseSheet',
      'pulseHeldSheet',
      'pulseTurnoutSheet',
      'pulseHighSheet',
    ] as const) {
      expect(homeExplainers[key].scope, key).toBeUndefined();
    }
  });
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/ClubPulse.test.tsx src/features/home/explainers.test.ts`

Expected: FAIL: the Sheet test still sees the header window (no "8 weeks to Sep 13, 2026 …"); `homeExplainers.pulseSheet` is undefined.

- [ ] **Step 3: Write the implementation**

In `frontend/src/lib/windowEvents.ts`, replace:

```ts
/**
 * The Sundays inside the time window in ONE request (`GET /api/events?from&to`), however many
 * calendar years it spans: "All" used to cost a request per year.
 */
export function useWindowEvents(): WindowEvents {
  const { range } = useTimeWindow();
  const meta = useMeta();
  const [roundTypes] = useRoundTypes();
```

with:

```ts
/**
 * The Sundays inside the time window in ONE request (`GET /api/events?from&to`), however many
 * calendar years it spans: "All" used to cost a request per year. `fixed` replaces the header
 * window with set dates (the Sunday Sheet's 8 weeks up to its Sunday).
 */
export function useWindowEvents(fixed?: WindowRange): WindowEvents {
  const { range: chosen } = useTimeWindow();
  const range = fixed ?? chosen;
  const meta = useMeta();
  const [roundTypes] = useRoundTypes();
```

In `frontend/src/lib/windowEvents.ts`, replace:

```ts
    events,
    sundays: events.filter((e) => e.has_scores).length,
    isPending: meta.isPending || (range !== null && query.isPending),
    error: query.error ?? meta.error,
  };
}
```

with:

```ts
    events,
    sundays: events.filter((e) => e.has_scores).length,
    isPending: (fixed === undefined && meta.isPending) || (range !== null && query.isPending),
    error: query.error ?? (fixed === undefined ? meta.error : null),
  };
}
```

In `frontend/src/features/home/components/TurnoutChart.tsx`, replace:

```tsx
import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery, TabularData } from '../../../components/charts/types';
import { api, unwrap } from '../../../api/client';
import { useRoundTypes } from '../../../lib/roundTypes';
```

with:

```tsx
import { barOption } from '../../../components/charts/builders/bar';
import { ChartFrame } from '../../../components/charts/ChartFrame';
import type { ChartFullQuery, Explainer, TabularData } from '../../../components/charts/types';
import { api, unwrap } from '../../../api/client';
import { useRoundTypes } from '../../../lib/roundTypes';
```

In `frontend/src/features/home/components/TurnoutChart.tsx`, replace:

```tsx
  range,
  label,
}: {
  events: EventSummary[];
```

with:

```tsx
  range,
  label,
  explainer = homeExplainers.pulse,
}: {
  events: EventSummary[];
```

In `frontend/src/features/home/components/TurnoutChart.tsx`, replace:

```tsx
  /** The window's name, for the accessible label. */
  label: string;
}) {
  const [roundTypes] = useRoundTypes();
```

with:

```tsx
  /** The window's name, for the accessible label. */
  label: string;
  /** The Sunday Sheet's fixed 8 weeks explain themselves differently (Plan 14). */
  explainer?: Explainer;
}) {
  const [roundTypes] = useRoundTypes();
```

In `frontend/src/features/home/components/TurnoutChart.tsx`, replace:

```tsx
      ariaLabel={`Turnout per Sunday, ${label.toLowerCase()}`}
      urlKey="pulse"
      explainer={homeExplainers.pulse}
    />
  );
```

with:

```tsx
      ariaLabel={`Turnout per Sunday, ${label.toLowerCase()}`}
      urlKey="pulse"
      explainer={explainer}
    />
  );
```

In `frontend/src/features/home/components/ClubPulse.tsx`, replace:

```tsx
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { useTimeWindow, filterRowsByWindow } from '../../../lib/timeWindow';
import { windowTagText } from '../../../lib/windowText';
import { useWindowEvents } from '../api';
import type { EventSummary } from '../api';
import { homeExplainers } from '../explainers';
import { formatScore, round1 } from '../format';
import { turnout } from '../turnout';
```

with:

```tsx
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { useTimeWindow, filterRowsByWindow, type WindowRange } from '../../../lib/timeWindow';
import { windowTagText } from '../../../lib/windowText';
import { useWindowEvents } from '../api';
import type { EventSummary } from '../api';
import { homeExplainers } from '../explainers';
import { formatDay, formatScore, round1 } from '../format';
import { turnout } from '../turnout';
```

In `frontend/src/features/home/components/ClubPulse.tsx`, replace:

```tsx
}

export function ClubPulse() {
  const { window, range, label } = useTimeWindow();
  const { events, isPending, error } = useWindowEvents();
  const pulseCard = (body: ReactNode) => <Card title="Club pulse">{body}</Card>;
```

with:

```tsx
}

/**
 * The club's numbers and the turnout chart. On the Sunday Sheet `range` fixes the 8 weeks up to
 * the issue's Sunday (the header window does not apply there); elsewhere the header window does.
 */
export function ClubPulse({ range: fixed }: { range?: WindowRange } = {}) {
  const { window, range: chosen, label: chosenLabel } = useTimeWindow();
  const { events, isPending, error } = useWindowEvents(fixed);
  const range = fixed ?? chosen;
  const label = fixed === undefined ? chosenLabel : `8 weeks to ${formatDay(fixed.to)}`;
  const pulseCard = (body: ReactNode) => <Card title="Club pulse">{body}</Card>;
```

In `frontend/src/features/home/components/ClubPulse.tsx`, replace:

```tsx
    );
  const stats = pulseStats(filterRowsByWindow(events, 'event_date', range));
  const tag = windowTagText(window, range);
  const chart = (
    <Suspense
```

with:

```tsx
    );
  const stats = pulseStats(filterRowsByWindow(events, 'event_date', range));
  const tag =
    fixed === undefined
      ? windowTagText(window, range)
      : `${label} · not affected by the time filter`;
  const chart = (
    <Suspense
```

In `frontend/src/features/home/components/ClubPulse.tsx`, replace:

```tsx
      }
    >
      <TurnoutChart events={events} range={range} label={label} />
    </Suspense>
  );
```

with:

```tsx
      }
    >
      <TurnoutChart
        events={events}
        range={range}
        label={label}
        explainer={fixed === undefined ? homeExplainers.pulse : homeExplainers.pulseSheet}
      />
    </Suspense>
  );
```

In `frontend/src/features/home/components/ClubPulse.tsx`, replace:

```tsx
            label="Sundays with full results"
            value={String(stats.held)}
            explainer={homeExplainers.pulseHeld}
          />
          <Stat
            label="Avg turnout"
            value={formatScore(stats.avgTurnout)}
            explainer={homeExplainers.pulseTurnout}
          />
          <Stat
            label="Highest score"
            value={formatScore(stats.seasonHigh)}
            explainer={homeExplainers.pulseHigh}
          />
        </div>
```

with:

```tsx
            label="Sundays with full results"
            value={String(stats.held)}
            explainer={
              fixed === undefined ? homeExplainers.pulseHeld : homeExplainers.pulseHeldSheet
            }
          />
          <Stat
            label="Avg turnout"
            value={formatScore(stats.avgTurnout)}
            explainer={
              fixed === undefined ? homeExplainers.pulseTurnout : homeExplainers.pulseTurnoutSheet
            }
          />
          <Stat
            label="Highest score"
            value={formatScore(stats.seasonHigh)}
            explainer={
              fixed === undefined ? homeExplainers.pulseHigh : homeExplainers.pulseHighSheet
            }
          />
        </div>
```

In `frontend/src/features/home/explainers.ts`, replace:

```ts
    ],
    scope: 'windowed',
  },
  latestShooters: {
```

with:

```ts
    ],
    scope: 'windowed',
  },
  pulseSheet: {
    what: 'How many people came to each Sunday in the 8 weeks up to this issue’s Sunday.',
    read: [
      'Tall bars are big turnouts; a dip is a slow Sunday (weather, holidays).',
      'Fullscreen and the CSV download cover every Sunday on record.',
    ],
    computed: [
      'One bar per Sunday with scores.',
      'Bar height is the attendance head count, or the number of shooters with scores when there is no head count.',
      'The round-type filter applies. The time filter does not: the Sheet always shows the 8 weeks up to its Sunday.',
    ],
  },
  pulseHeldSheet: {
    what: 'How many Sundays in the 8 weeks up to this issue’s Sunday have full results.',
    computed: [
      'A Sunday has full results when scores were entered and at least half of the people who came have scores.',
      'The round-type filter applies; the time filter does not.',
    ],
  },
  pulseTurnoutSheet: {
    what: 'The typical crowd: the average number of people per scored Sunday in the 8 weeks up to this issue’s Sunday.',
    computed: [
      'Adds up the head count of each scored Sunday (or the number with scores when there is no head count) and divides by the number of Sundays, to 0.1.',
      'The round-type filter applies; the time filter does not.',
    ],
  },
  pulseHighSheet: {
    what: 'The best single round anyone shot in the 8 weeks up to this issue’s Sunday, out of 50.',
    computed: [
      'The highest score of any round on a scored Sunday in those 8 weeks, second rounds included.',
      'It is one round, not an average. The round-type filter applies; the time filter does not.',
    ],
  },
  latestShooters: {
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/features/home src/lib`

Expected: all pass.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add frontend/src/features/home/components/ClubPulse.test.tsx frontend/src/features/home/explainers.test.ts frontend/src/lib/windowEvents.ts frontend/src/features/home/components/TurnoutChart.tsx frontend/src/features/home/components/ClubPulse.tsx frontend/src/features/home/explainers.ts
git commit -m "feat(sheet): Club pulse can show a fixed 8-week window with its own explainers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 8.2 Your panel takes a title and header controls

- [ ] **Step 6: Write the failing test**

In `frontend/src/features/home/components/MePanel.test.tsx`, replace:

```tsx
  beforeEach(() => {
    clearMe();
  });
```

with:

```tsx
  beforeEach(() => {
    clearMe();
  });

  it('takes another title and header controls (the Sheet’s "Your Sunday" and "Not me")', async () => {
    renderWithProviders(
      <MePanel
        meId={3}
        onCleared={vi.fn()}
        widgets={[]}
        title="Your Sunday"
        actions={<button type="button">Not me</button>}
      />,
    );
    const panel = await screen.findByRole('region', { name: 'Your Sunday' });
    expect(within(panel).getByRole('button', { name: 'Not me' })).toBeInTheDocument();
  });
```

- [ ] **Step 7: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/MePanel.test.tsx`

Expected: FAIL: no region "Your Sunday".

- [ ] **Step 8: Write the implementation**

In `frontend/src/features/home/components/MePanel.tsx`, replace:

```tsx
  onCleared,
  widgets,
}: {
  meId: number | null;
  onCleared: () => void;
  widgets: HomeWidget[];
}) {
  const shootersLink = useRoundTypeLink('/shooters');
  return (
    <Card title="Your panel">
      {meId === null ? (
        // The link stands on its own line: inline in the sentence it could not be 44px tall (C10).
```

with:

```tsx
  onCleared,
  widgets,
  title = 'Your panel',
  actions,
}: {
  meId: number | null;
  onCleared: () => void;
  widgets: HomeWidget[];
  /** The Sunday Sheet calls it "Your Sunday" (Plan 14). */
  title?: string;
  /** Header controls ("Not me" on the Sheet). */
  actions?: ReactNode;
}) {
  const shootersLink = useRoundTypeLink('/shooters');
  return (
    <Card title={title} actions={actions}>
      {meId === null ? (
        // The link stands on its own line: inline in the sentence it could not be 44px tall (C10).
```

- [ ] **Step 9: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/features/home/components/MePanel.test.tsx`

Expected: all pass.

- [ ] **Step 10: Commit**

From the worktree root:

```bash
git add frontend/src/features/home/components/MePanel.test.tsx frontend/src/features/home/components/MePanel.tsx
git commit -m "feat(sheet): MePanel title and header controls" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 8.3 The rail, the slots and the page layout

- [ ] **Step 11: Write the failing test**

Create `frontend/src/features/sheet/components/YourSunday.test.tsx`:

```tsx
import { screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getMe, setMe } from '../../../lib/me';
import { renderWithProviders } from '../../../test/render';
import type { HomeWidget } from '../../home/widgets';
import { YourSunday } from './YourSunday';

const nextTrophy: HomeWidget = {
  id: 'next-trophy',
  order: 10,
  slot: 'me',
  Component: ({ meId }) => <p>next trophy for {meId}</p>,
};

afterEach(() => {
  localStorage.clear();
});

function renderSlot(meId: number | null, skipped = false) {
  const handlers = { onPicked: vi.fn(), onCleared: vi.fn(), onSkipped: vi.fn() };
  const view = renderWithProviders(
    <YourSunday meId={meId} skipped={skipped} widgets={[nextTrophy]} {...handlers} />,
  );
  return { ...view, ...handlers };
}

describe('YourSunday', () => {
  it('asks "Which one are you?" while no shooter is picked', () => {
    renderSlot(null);
    expect(screen.getByRole('region', { name: 'Which one are you?' })).toBeInTheDocument();
  });

  it('shows nothing once this browser skipped', () => {
    const { container } = renderSlot(null, true);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the panel and the next trophy for "me", and "Not me" forgets the pick', async () => {
    setMe(3);
    const { user, onCleared } = renderSlot(3);
    const panel = await screen.findByRole('region', { name: 'Your Sunday' });
    expect(await within(panel).findByText('next trophy for 3')).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: 'Not me' }));
    expect(getMe()).toBeNull();
    expect(onCleared).toHaveBeenCalledTimes(1);
  });
});
```

In `frontend/src/features/sheet/pages/SheetPage.test.tsx`, replace:

```tsx
import { screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { insightFixture } from '../../insights/mocks';
import { newerText } from '../components/Masthead';
import { sheetExplainers } from '../explainers';
import { onThisDayPost, postFixture, sheetFixture, trophyPost } from '../mocks';
import { SheetPage } from './SheetPage';

afterEach(() => {
```

with:

```tsx
import { screen, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { expectChartControls } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { meDetail, meRounds, seasonEvents } from '../../home/mocks';
import { insightFixture } from '../../insights/mocks';
import { newerText } from '../components/Masthead';
import { sheetExplainers } from '../explainers';
import { onThisDayPost, postFixture, sheetFixture, trophyPost } from '../mocks';
import { SHEET_ORDER, SheetPage } from './SheetPage';

// The rail's turnout chart loads lazily: warm it once so findBy*'s budget never covers a cold import.
beforeAll(async () => {
  await import('../../home/components/TurnoutChart');
});
const turnoutChart = () => screen.findByRole('region', { name: 'Turnout per Sunday' }, LAZY_CHART);

afterEach(() => {
```

In `frontend/src/features/sheet/pages/SheetPage.test.tsx`, replace:

```tsx
    expect(within(otd).getByText(sheetExplainers.onThisDay.what)).toBeInTheDocument();
  });
});
```

with:

```tsx
    expect(within(otd).getByText(sheetExplainers.onThisDay.what)).toBeInTheDocument();
  });

  it(
    'stacks the blocks in the Sheet order on a phone and splits main and rail on desktop',
    async () => {
      const { container } = renderAt();
      await turnoutChart();
      const blocks = [...container.querySelectorAll<HTMLElement>('[data-sheet-block]')];
      const order = (el: HTMLElement) => Number(/(?:^| )order-(\d)/.exec(el.className)?.[1]);
      const stacked = [...blocks].sort((a, b) => order(a) - order(b));
      expect(stacked.map((b) => b.dataset['sheetBlock'])).toEqual([
        'masthead',
        'numbers',
        'you',
        'lead',
        'feed',
        'more',
        'next',
        'pulse',
        'details',
      ]);
      for (const block of blocks) {
        const name = block.dataset['sheetBlock'] as keyof typeof SHEET_ORDER;
        expect(block.className).toContain(SHEET_ORDER[name]);
      }
      const lead = container.querySelector('[data-sheet-block="lead"]')?.parentElement;
      const rail = container.querySelector('[data-sheet-block="you"]')?.parentElement;
      expect(lead?.className).toContain('lg:col-span-2');
      expect(rail).not.toBe(lead);
      expect(rail?.className).toContain('lg:flex');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'keeps every former Home piece: numbers, lead, posts, Your Sunday, Next Sunday, Club pulse and details',
    async () => {
      setMe(3);
      server.use(
        http.get('*/api/sheet/:date', () =>
          HttpResponse.json(
            sheetFixture({
              headline: insightFixture({ key: 'hero' }),
              recap: insightFixture({
                key: 'recap',
                kind: 'home.sunday-recap',
                headline: [{ t: 'text', v: '23 shooters came out.' }],
                headline_you: null,
              }),
              spotlight: insightFixture({ key: 'spot', subject_id: '5' }),
            }),
          ),
        ),
        http.get('*/api/events', () => HttpResponse.json(seasonEvents)),
        http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
        http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
      );
      renderAt();
      expect(await screen.findByRole('region', { name: 'This Sunday in numbers' })).toBeVisible();
      expect(screen.getByRole('list', { name: 'Top story' })).toBeInTheDocument();
      expect(screen.getByText('23 shooters came out.')).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Spotlight' })).toBeInTheDocument();
      expect(screen.getByRole('list', { name: 'Posts' })).toBeInTheDocument();
      const you = await screen.findByRole('region', { name: 'Your Sunday' });
      expect(await within(you).findByText('37 · 16th')).toBeInTheDocument();
      expect(await screen.findByRole('region', { name: 'Next Sunday' })).toBeVisible();
      expect(screen.getByRole('region', { name: 'Club pulse' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Full results, Sep 27, 2026' })).toHaveAttribute(
        'href',
        '/events/2026-09-27',
      );
      await turnoutChart();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'gives every chart on the Sheet Table and CSV, and the turnout chart is its only one',
    async () => {
      renderAt();
      expectChartControls(await turnoutChart());
      expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(1);
      expect(screen.getAllByRole('button', { name: 'Table' })).toHaveLength(1);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'asks for the club pulse of the 8 weeks up to the issue’s Sunday',
    async () => {
      const seen: string[] = [];
      server.use(
        http.get('*/api/events', ({ request }) => {
          const q = new URL(request.url).searchParams;
          seen.push(`${q.get('from') ?? ''}..${q.get('to') ?? ''}`);
          return HttpResponse.json(seasonEvents);
        }),
      );
      renderAt();
      await turnoutChart();
      expect(seen[0]).toBe('2026-08-03..2026-09-27');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'shows Next Sunday on the latest issue only',
    async () => {
      server.use(
        http.get('*/api/sheet/:date', () =>
          HttpResponse.json(
            sheetFixture({
              masthead: {
                date: '2026-09-13',
                issue: 309,
                previous: null,
                next: '2026-09-27',
                latest: false,
                newer: null,
              },
            }),
          ),
        ),
      );
      const { container } = renderAt('/sheet/2026-09-13');
      await turnoutChart();
      expect(container.querySelector('[data-sheet-block="next"]')).toBeNull();
      expect(screen.getByRole('region', { name: 'Sunday details' })).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'asks "Which one are you?", then fills Your Sunday, and "Not me" asks again',
    async () => {
      server.use(
        http.get('*/api/shooters', () =>
          HttpResponse.json([{ ...meDetail, shooter_id: 3, display_name: 'Hadley, Ike' }]),
        ),
        http.get('*/api/shooters/:id', () => HttpResponse.json(meDetail)),
        http.get('*/api/shooters/:id/rounds', () => HttpResponse.json(meRounds)),
      );
      const { user } = renderAt();
      const ask = await screen.findByRole('region', { name: 'Which one are you?' });
      await user.type(within(ask).getByLabelText('Your name'), 'Hadley');
      await user.click(await within(ask).findByRole('button', { name: 'Hadley, Ike' }));
      const you = await screen.findByRole('region', { name: 'Your Sunday' });
      await user.click(within(you).getByRole('button', { name: 'Not me' }));
      expect(await screen.findByRole('region', { name: 'Which one are you?' })).toBeInTheDocument();
      await turnoutChart();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'hides the question after "skip", also on the next visit',
    async () => {
      const first = renderAt();
      await first.user.click(await screen.findByRole('button', { name: 'Not a shooter / skip' }));
      expect(screen.queryByRole('region', { name: 'Which one are you?' })).toBeNull();
      await turnoutChart();
      first.unmount();
      renderAt();
      await turnoutChart();
      expect(screen.queryByRole('region', { name: 'Which one are you?' })).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );
});
```

In `frontend/src/app/registry.test.ts`, replace:

```ts
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
  '/sheet/:date': NO_FILTERS,
  '/shooters': NO_FILTERS,
  '/shooters/:id': BOTH_FILTERS,
```

with:

```ts
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
  '/sheet/:date': ROUND_TYPE_ONLY,
  '/shooters': NO_FILTERS,
  '/shooters/:id': BOTH_FILTERS,
```

- [ ] **Step 12: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/sheet src/app/registry.test.ts`

Expected: FAIL: `Failed to resolve import "./YourSunday"`; SheetPage has no `SHEET_ORDER` export and no rail; the filter audit expects `ROUND_TYPE_ONLY`.

- [ ] **Step 13: Write the implementation**

The yir On-this-day card and its home widget go: "On this day" is feed post ⑥ now (Decision 16). `useOnThisDay` and the `onThisDay` explainer had no other reader.

In `frontend/src/features/home/widgets.ts`, replace:

```ts
import type { FC } from 'react';

/**
 * Extension point (C10): a feature exports `homeWidget` from `src/features/<name>/homeWidget.tsx`. `hero` widgets
 * render full width under the page title (Plan 12); `main` widgets render in the main column with `meId` (possibly
 * null); `me` widgets render inside the me panel once a me profile has loaded.
 */
export type HomeWidget = {
```

with:

```ts
import type { FC } from 'react';
import type { SheetIssue } from '../sheet/api';

/**
 * What a widget gets: the viewer's "me" id (possibly null) and, on the Sunday Sheet, the issue
 * being shown (Plan 14).
 */
export type HomeWidgetProps = { meId: number | null; issue?: SheetIssue };

/**
 * Extension point (C10): a feature exports `homeWidget` from `src/features/<name>/homeWidget.tsx`.
 * On the Sunday Sheet (Plan 14) `hero` widgets are the lead (the headline and the spotlight),
 * `main` widgets are rail cards (shown on the latest issue), and `me` widgets render inside
 * "Your Sunday" once a me profile has loaded.
 */
export type HomeWidget = {
```

In `frontend/src/features/home/widgets.ts`, replace:

```ts
  order: number;
  slot: 'hero' | 'main' | 'me';
  Component: FC<{ meId: number | null }>;
};
```

with:

```ts
  order: number;
  slot: 'hero' | 'main' | 'me';
  Component: FC<HomeWidgetProps>;
};
```

Replace the whole of `frontend/src/features/home/components/WidgetSlot.tsx` with:

```tsx
import type { SheetIssue } from '../../sheet/api';
import { widgetsForSlot } from '../widgets';
import type { HomeWidget } from '../widgets';

/** Renders a slot's widgets in order; each widget renders itself (no wrapper card, D5). */
export function WidgetSlot({
  slot,
  widgets,
  meId,
  issue,
}: {
  slot: HomeWidget['slot'];
  widgets: HomeWidget[];
  meId: number | null;
  /** The Sunday Sheet's issue, for widgets that show part of it (Plan 14). */
  issue?: SheetIssue;
}) {
  return (
    <>
      {widgetsForSlot(widgets, slot).map(({ id, Component }) => (
        <Component key={id} meId={meId} issue={issue} />
      ))}
    </>
  );
}
```

Replace the whole of `frontend/src/features/insights/homeWidget.tsx` with:

```tsx
import type { HomeWidget, HomeWidgetProps } from '../home/widgets';
import { HomeInsights } from './components/FeedSections';
import { SheetLead } from './components/SheetLead';

/**
 * The Sunday Sheet's lead (Plan 14): the issue's headline with its recap as the deck, then the
 * spotlight. Without an issue (the Home page, until Task 9 retires it) it is the home feed.
 */
function InsightsLead({ meId, issue }: HomeWidgetProps) {
  if (issue === undefined) return <HomeInsights meId={meId} />;
  return (
    <SheetLead
      headline={issue.headline}
      recap={issue.recap}
      spotlight={issue.spotlight}
      meId={meId}
      date={issue.masthead.date}
    />
  );
}

export const homeWidget: HomeWidget = {
  id: 'insights',
  order: 0,
  slot: 'hero',
  Component: InsightsLead,
};
```

Delete `frontend/src/features/yir/homeWidget.tsx` (`git rm frontend/src/features/yir/homeWidget.tsx`).

Delete `frontend/src/features/yir/components/OnThisDayCard.tsx` (`git rm frontend/src/features/yir/components/OnThisDayCard.tsx`).

Delete `frontend/src/features/yir/components/OnThisDayCard.test.tsx` (`git rm frontend/src/features/yir/components/OnThisDayCard.test.tsx`).

In `frontend/src/features/yir/api.ts`, replace:

```ts
}

export function useOnThisDay() {
  return useQuery({
    queryKey: ['/api/on-this-day'],
    queryFn: () => unwrap(api.GET('/api/on-this-day')),
  });
}

/**
 * A calendar-year board: the leaderboards' "this year" period (1 January to `asOf`, or to today when
```

with:

```ts
}

/**
 * A calendar-year board: the leaderboards' "this year" period (1 January to `asOf`, or to today when
```

In `frontend/src/features/yir/explainers.ts`, replace:

```ts
    ],
  },
  onThisDay: {
    what: 'The Sundays closest to today’s date one, two and three years ago, and who won them.',
    computed: [
      'For each of the last three years we take today’s date that many years back (29 February becomes 28 February) and pick the Sunday within three days of it, the earlier one if two are equally close.',
      'Winners: everyone whose best round of that Sunday was first, so a tie lists every winner. A Sunday with no scores shows only its head count.',
    ],
  },
} as const satisfies Record<string, Explainer>;
```

with:

```ts
    ],
  },
} as const satisfies Record<string, Explainer>;
```

In `frontend/src/features/yir/routes.test.tsx`, replace:

```tsx
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../test/lazyChart';
import { server } from '../../test/msw/server';
import { homeWidget } from './homeWidget';
import { leaderboardHandler } from './mocks';
import { nav, routes } from './routes';
```

with:

```tsx
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../test/lazyChart';
import { server } from '../../test/msw/server';
import { leaderboardHandler } from './mocks';
import { nav, routes } from './routes';
```

In `frontend/src/features/yir/routes.test.tsx`, replace:

```tsx
        path: '/',
        HydrateFallback: () => null,
        children: [...routes, { index: true, element: <homeWidget.Component meId={null} /> }],
      },
    ],
```

with:

```tsx
        path: '/',
        HydrateFallback: () => null,
        children: routes,
      },
    ],
```

In `frontend/src/features/yir/routes.test.tsx`, replace:

```tsx
    ).toBeInTheDocument();
  });

  it('puts On this day on the home page', async () => {
    renderAt('/');
    expect(homeWidget.slot).toBe('main');
    expect(
      await screen.findByText('23 shooters · won by Rookwood, Derek (45)'),
    ).toBeInTheDocument();
  });
});
```

with:

```tsx
    ).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/sheet/components/YourSunday.tsx`:

```tsx
import { Button } from '../../../components/ui/Button';
import { clearMe } from '../../../lib/me';
import { MePanel } from '../../home/components/MePanel';
import type { HomeWidget } from '../../home/widgets';
import { WhichOneAreYou } from './WhichOneAreYou';

/**
 * The rail's personal slot (Plan 14): the viewer's last result, totals and next trophy once
 * "me" is set; "Which one are you?" until then; nothing once this browser said "skip".
 */
export function YourSunday({
  meId,
  skipped,
  widgets,
  onPicked,
  onCleared,
  onSkipped,
}: {
  meId: number | null;
  skipped: boolean;
  widgets: HomeWidget[];
  onPicked: (id: number) => void;
  onCleared: () => void;
  onSkipped: () => void;
}) {
  if (meId === null) {
    return skipped ? null : <WhichOneAreYou onPicked={onPicked} onSkipped={onSkipped} />;
  }
  return (
    <MePanel
      meId={meId}
      title="Your Sunday"
      actions={
        <Button
          variant="ghost"
          onClick={() => {
            clearMe();
            onCleared();
          }}
        >
          Not me
        </Button>
      }
      onCleared={onCleared}
      widgets={widgets}
    />
  );
}
```

Create `frontend/src/features/sheet/components/SundayDetails.tsx`:

```tsx
import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { formatDay } from '../../home/format';

/** The rail's way to the full results of the issue's Sunday. */
export function SundayDetails({ date, latest }: { date: string; latest: boolean }) {
  const eventLink = useRoundTypeLink(`/events/${date}`);
  return (
    <Card title={latest ? 'Latest Sunday details' : 'Sunday details'}>
      <Link to={eventLink} className="inline-flex min-h-11 items-center underline">
        {`Full results, ${formatDay(date)}`}
      </Link>
    </Card>
  );
}
```

Replace the whole of `frontend/src/features/sheet/pages/SheetPage.tsx` with:

```tsx
import { useState, type ReactNode } from 'react';
import { Link, useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { cx } from '../../../components/ui/cx';
import { EmptyState } from '../../../components/ui/EmptyState';
import { getDeviceId } from '../../../lib/device';
import { getMe, isMeSkipped } from '../../../lib/me';
import { daysBack, EIGHT_WEEK_DAYS } from '../../../lib/timeWindowChoice';
import { ClubPulse } from '../../home/components/ClubPulse';
import { WidgetSlot } from '../../home/components/WidgetSlot';
import { homeWidgets, type HomeWidget } from '../../home/widgets';
import { useBumps, useSheet, type SheetIssue } from '../api';
import { Feed } from '../components/Feed';
import { Masthead } from '../components/Masthead';
import { MoreFromSunday } from '../components/MoreFromSunday';
import { Numbers } from '../components/Numbers';
import { SheetSkeleton } from '../components/SheetSkeleton';
import { SundayDetails } from '../components/SundayDetails';
import { YourSunday } from '../components/YourSunday';

const NOTE_ID = 'sheet-bumps-off';

/**
 * Where each block sits. A phone stacks them in this order (the column wrappers are `contents`
 * below 1024 px, so every block is an item of one flex column); from 1024 px the main column
 * (lead, feed, More) sits beside the rail (you, next, pulse, details), each in this order.
 */
export const SHEET_ORDER = {
  masthead: 'order-1 lg:order-none lg:col-span-3',
  numbers: 'order-2 lg:order-none lg:col-span-3',
  you: 'order-3',
  lead: 'order-4',
  feed: 'order-5',
  more: 'order-6',
  next: 'order-7',
  pulse: 'order-8',
  details: 'order-9',
} as const;

function Block({ name, children }: { name: keyof typeof SHEET_ORDER; children: ReactNode }) {
  return (
    <div
      data-sheet-block={name}
      className={cx('flex min-w-0 flex-col gap-4 empty:hidden', SHEET_ORDER[name])}
    >
      {children}
    </div>
  );
}

function SheetBody({
  issue,
  deviceId,
  widgets,
}: {
  issue: SheetIssue;
  deviceId: string | null;
  widgets: HomeWidget[];
}) {
  const [meId, setMeId] = useState<number | null>(getMe);
  const [skipped, setSkipped] = useState(isMeSkipped);
  const { date, latest } = issue.masthead;
  const bumps = useBumps(date, deviceId);
  const shared = { issue, bumps: bumps.data, deviceId, meId, noteId: NOTE_ID };
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-3 lg:items-start">
      <Block name="masthead">
        <Masthead issue={issue} />
      </Block>
      <Block name="numbers">
        <Numbers issue={issue} />
      </Block>
      <div className="contents lg:col-span-2 lg:flex lg:min-w-0 lg:flex-col lg:gap-4">
        <Block name="lead">
          <WidgetSlot slot="hero" widgets={widgets} meId={meId} issue={issue} />
        </Block>
        <Block name="feed">
          <Feed {...shared} />
        </Block>
        <Block name="more">
          <MoreFromSunday {...shared} />
        </Block>
      </div>
      <div className="contents lg:flex lg:min-w-0 lg:flex-col lg:gap-4">
        <Block name="you">
          <YourSunday
            meId={meId}
            skipped={skipped}
            widgets={widgets}
            onPicked={setMeId}
            onCleared={() => setMeId(null)}
            onSkipped={() => setSkipped(true)}
          />
        </Block>
        {latest && (
          <Block name="next">
            <WidgetSlot slot="main" widgets={widgets} meId={meId} issue={issue} />
          </Block>
        )}
        <Block name="pulse">
          <ClubPulse range={{ from: daysBack(date, EIGHT_WEEK_DAYS - 1), to: date }} />
        </Block>
        <Block name="details">
          <SundayDetails date={date} latest={latest} />
        </Block>
      </div>
    </div>
  );
}

function SheetError({ error }: { error: Error }) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState
        title="No Sunday Sheet for this date"
        description="There is a Sheet for every Sunday with full results."
        action={
          <span className="flex flex-wrap justify-center gap-3">
            <Link to="/events" className="inline-flex min-h-11 items-center underline">
              All issues
            </Link>
            <Link to="/" className="inline-flex min-h-11 items-center underline">
              Latest issue
            </Link>
          </span>
        }
      />
    );
  }
  return <EmptyState title="Couldn't load the Sunday Sheet" description={error.message} />;
}

/** The Sunday Sheet: `/sheet/:date` (and, once Home retires, `/` for the latest issue). */
export function SheetPage({ widgets = homeWidgets }: { widgets?: HomeWidget[] }) {
  const { date } = useParams();
  const sheet = useSheet(date ?? 'latest');
  const [deviceId] = useState<string | null>(getDeviceId);
  if (sheet.isPending) return <SheetSkeleton />;
  if (sheet.isError) return <SheetError error={sheet.error} />;
  return <SheetBody issue={sheet.data} deviceId={deviceId} widgets={widgets} />;
}
```

Replace the whole of `frontend/src/features/sheet/routes.tsx` with:

```tsx
import type { RouteObject } from 'react-router';
import { ROUND_TYPE_ONLY } from '../../lib/pageFilters';

/** The Sunday Sheet (Plan 14): one issue per held Sunday. */
export const routes: RouteObject[] = [
  {
    path: '/sheet/:date',
    handle: { filters: ROUND_TYPE_ONLY },
    lazy: async () => ({ Component: (await import('./pages/SheetPage')).SheetPage }),
  },
];
```

- [ ] **Step 14: Run the tests and make sure they pass**

Run: `cd frontend && pnpm typecheck && pnpm exec vitest run src/features src/app src/lib`

Expected: tsc exits 0; all pass.

- [ ] **Step 15: Commit**

From the worktree root:

```bash
# the deletions above are already staged by `git rm`
git add frontend/src/features/sheet/components/YourSunday.test.tsx frontend/src/features/sheet/pages/SheetPage.test.tsx frontend/src/app/registry.test.ts frontend/src/features/home/widgets.ts frontend/src/features/home/components/WidgetSlot.tsx frontend/src/features/insights/homeWidget.tsx frontend/src/features/yir/api.ts frontend/src/features/yir/explainers.ts frontend/src/features/yir/routes.test.tsx frontend/src/features/sheet/components/YourSunday.tsx frontend/src/features/sheet/components/SundayDetails.tsx frontend/src/features/sheet/pages/SheetPage.tsx frontend/src/features/sheet/routes.tsx
git commit -m "feat(sheet): the rail, Your Sunday and the Sheet slots" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 8.4 Gates

- [ ] **Step 16: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Run: `cd frontend && pnpm test --coverage`

Expected: the whole suite passes; lines and branches stay at or above the ratchet

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 9: Retire Home: `/` is the Sheet

**Wave 5** · parallel with: none (Wave 5 is this task alone) · branch `task/14-9-retire-home` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Modify: `frontend/src/features/sheet/routes.tsx` (replace the whole file: index route and nav), `routes.test.tsx` (replace the whole file)
- Delete: `frontend/src/features/home/routes.tsx`, `routes.test.tsx`, `pages/HomePage.tsx`, `pages/HomePage.test.tsx`, `components/LatestEventCard.tsx`, `components/LatestEventCard.test.tsx`
- Delete: `frontend/src/features/insights/components/RecapCard.tsx`
- Modify: `frontend/src/features/home/explainers.ts`, `explainers.test.ts`
- Modify: `frontend/src/features/insights/homeWidget.tsx`, `components/FeedSections.tsx`, `components/FeedSections.test.tsx`, `components/MoreInsights.test.tsx`
- Create: `frontend/src/features/insights/homeWidget.test.tsx`
- Modify: `frontend/src/app/App.test.tsx`, `App.session.test.tsx`, `router.test.tsx`, `registry.test.ts`, `navRegistry.test.ts`
- Modify: `frontend/e2e/home.spec.ts` (replace the whole file), `insights.spec.ts`, `yir.spec.ts`, `filters-placement.spec.ts`, `thin-window.spec.ts`, `ux-foundation.spec.ts`, `date-range.spec.ts`, `smoke.spec.ts`

**Interfaces:**
- Consumes:
  - Task 8: the full Sheet page; Task 4: `sheetFixture`; Task 5: `SheetLead`.
- Produces:
  - `features/sheet/routes.tsx`: `routes` = index (`/`) and `/sheet/:date`, both `ROUND_TYPE_ONLY`; `nav = [{ label: "Sheet", path: "/", icon: Newspaper, order: 10, mobileTab: true }]`.
  - C10 nav tables: `sheet` takes order 10 and the phone tab from `home` (Decision 15).
  - No more `HomePage`, `LatestEventCard`, `HomeInsights`, `HomeInsightsPlaceholder`, `RecapCard`, `latestSubtitle`, or the `latestShooters` / `latestMedian` / `latestTop` explainers.

#### 9.1 The route switch

- [ ] **Step 1: Write the failing test**

Replace the whole of `frontend/src/features/sheet/routes.test.tsx` with:

```tsx
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { sheetFixture } from './mocks';
import { nav, routes } from './routes';

function renderAt(route: string) {
  return renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], { route });
}

describe('sheet routes', () => {
  it('serve the latest issue at /', async () => {
    const asked: string[] = [];
    server.use(
      http.get('*/api/sheet/latest', () => {
        asked.push('latest');
        return HttpResponse.json(sheetFixture());
      }),
    );
    renderAt('/');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
    expect(asked).toEqual(['latest']);
  });

  it('serve an issue at /sheet/:date', async () => {
    renderAt('/sheet/2026-09-27');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
  });

  it('are the first nav item and a phone tab', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Sheet', path: '/', order: 10, mobileTab: true }),
    ]);
  });
});
```

In `frontend/src/app/registry.test.ts`, replace:

```ts

describe('the discovered registry', () => {
  it('includes the home feature as the index route and first nav item', () => {
    expect(featureRoutes.some((route) => route.index === true)).toBe(true);
    expect(navItems[0]).toMatchObject({ label: 'Home', path: '/', order: 10, mobileTab: true });
  });
});
```

with:

```ts

describe('the discovered registry', () => {
  it('includes the Sunday Sheet as the index route and first nav item', () => {
    expect(featureRoutes.some((route) => route.index === true)).toBe(true);
    expect(navItems[0]).toMatchObject({ label: 'Sheet', path: '/', order: 10, mobileTab: true });
  });
});
```

In `frontend/src/app/registry.test.ts`, replace:

```ts
 */
const EXPECTED: Record<string, PageFilters> = {
  '/': BOTH_FILTERS,
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
```

with:

```ts
 */
const EXPECTED: Record<string, PageFilters> = {
  '/': ROUND_TYPE_ONLY,
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
```

In `frontend/src/app/navRegistry.test.ts`, replace:

```ts
/** C10: fixed nav orders; any other feature takes an unused value >= 140. */
const FIXED_ORDER: Record<string, number> = {
  home: 10,
  events: 20,
  leaderboards: 30,
```

with:

```ts
/** C10: fixed nav orders; any other feature takes an unused value >= 140. */
const FIXED_ORDER: Record<string, number> = {
  sheet: 10,
  events: 20,
  leaderboards: 30,
```

In `frontend/src/app/navRegistry.test.ts`, replace:

```ts
};
/** C10: exactly these features are mobile tabs. */
const MOBILE_TABS = new Set(['home', 'events', 'leaderboards', 'shooters']);

const modules = import.meta.glob<FeatureModule>('../features/*/routes.tsx', { eager: true });
```

with:

```ts
};
/** C10: exactly these features are mobile tabs. */
const MOBILE_TABS = new Set(['sheet', 'events', 'leaderboards', 'shooters']);

const modules = import.meta.glob<FeatureModule>('../features/*/routes.tsx', { eager: true });
```

In `frontend/src/app/navRegistry.test.ts`, replace:

```ts

describe('feature registry', () => {
  it('discovers at least the home feature', () => {
    expect(features.map((f) => f.name)).toContain('home');
  });
```

with:

```ts

describe('feature registry', () => {
  it('discovers at least the sheet feature', () => {
    expect(features.map((f) => f.name)).toContain('sheet');
  });
```

In `frontend/src/app/navRegistry.test.ts`, replace:

```ts
  });

  it('lets only home, events, leaderboards and shooters be mobile tabs', () => {
    const tabFeatures = features
      .filter((f) => f.nav.some((i) => i.mobileTab === true))
```

with:

```ts
  });

  it('lets only sheet, events, leaderboards and shooters be mobile tabs', () => {
    const tabFeatures = features
      .filter((f) => f.nav.some((i) => i.mobileTab === true))
```

In `frontend/src/app/navRegistry.test.ts`, replace:

```ts
  });

  it('makes home, events, leaderboards and shooters mobile tabs whenever they are registered', () => {
    const present = features.filter((f) => MOBILE_TABS.has(f.name));
    expect(present.map((f) => f.name)).toContain('home');
    for (const { name, nav } of present) {
      expect(
```

with:

```ts
  });

  it('makes sheet, events, leaderboards and shooters mobile tabs whenever they are registered', () => {
    const present = features.filter((f) => MOBILE_TABS.has(f.name));
    expect(present.map((f) => f.name)).toContain('sheet');
    for (const { name, nav } of present) {
      expect(
```

Replace the whole of `frontend/src/app/App.test.tsx` with:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('renders the Sunday Sheet at /', async () => {
    render(<App />);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
  });
});
```

In `frontend/src/app/App.session.test.tsx`, replace:

```tsx
  it('routes a data 401 to the login page and forgets the cached session', async () => {
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
    server.use(
      http.get('/api/health', () =>
```

with:

```tsx
  it('routes a data 401 to the login page and forgets the cached session', async () => {
    render(<App />);
    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
    server.use(
      http.get('/api/health', () =>
```

In `frontend/src/app/router.test.tsx`, replace:

```tsx
  });

  it('renders the home page at /', async () => {
    renderRoute('/');

    expect(await screen.findByRole('heading', { name: 'Sunday Clays' })).toBeInTheDocument();
  });
});
```

with:

```tsx
  });

  it('renders the Sunday Sheet at /', async () => {
    renderRoute('/');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'The Sunday Sheet' }),
    ).toBeInTheDocument();
  });
});
```

Create `frontend/src/features/insights/homeWidget.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { sheetFixture } from '../sheet/mocks';
import { homeWidget } from './homeWidget';
import { insightFixture } from './mocks';

describe('insights home widget', () => {
  it('leads the Sheet with the issue’s headline, deck and spotlight', () => {
    const issue = sheetFixture({ headline: insightFixture({ key: 'hero' }) });
    renderWithProviders(<homeWidget.Component meId={null} issue={issue} />);
    expect(screen.getByRole('list', { name: 'Top story' })).toBeInTheDocument();
  });

  it('renders nothing outside an issue', () => {
    const { container } = renderWithProviders(<homeWidget.Component meId={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

In `frontend/src/features/home/explainers.test.ts`, replace:

```ts
  });

  it('tags the club numbers with the time window and leaves the latest Sunday untagged', () => {
    for (const key of ['pulse', 'pulseHeld', 'pulseTurnout', 'pulseHigh'] as const) {
      expect(homeExplainers[key].scope, key).toBe('windowed');
    }
    expect(homeExplainers.latestMedian.scope).toBeUndefined();
  });
```

with:

```ts
  });

  it('tags the club numbers with the time window', () => {
    for (const key of ['pulse', 'pulseHeld', 'pulseTurnout', 'pulseHigh'] as const) {
      expect(homeExplainers[key].scope, key).toBe('windowed');
    }
  });
```

In `frontend/src/features/insights/components/FeedSections.test.tsx`, replace:

```tsx
import { screen, waitFor, within } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
```

with:

```tsx
import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
```

In `frontend/src/features/insights/components/FeedSections.test.tsx`, replace:

```tsx
import { renderWithProviders } from '../../../test/render';
import { feedFixture, insightFixture, kudosFixture } from '../mocks';
import { HomeInsights, PageInsights, ProfileInsights, SundayInsights } from './FeedSections';

afterEach(() => {
```

with:

```tsx
import { renderWithProviders } from '../../../test/render';
import { feedFixture, insightFixture, kudosFixture } from '../mocks';
import { PageInsights, ProfileInsights, SundayInsights } from './FeedSections';

afterEach(() => {
```

In `frontend/src/features/insights/components/FeedSections.test.tsx`, replace:

```tsx
});

describe('HomeInsights', () => {
  it('holds the place of the cards while the feed loads, then swaps them for the real ones', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get('*/api/insights/home', async () => {
        await gate;
        return HttpResponse.json(
          feedFixture({
            pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap' }),
            hero: insightFixture({ key: 'hero' }),
            top: [insightFixture({ key: 'top' })],
          }),
        );
      }),
    );
    const { container } = renderWithProviders(<HomeInsights meId={3} />);
    expect(screen.getByRole('status', { name: 'Loading insights' })).toBeInTheDocument();
    // Two cards side by side on desktop, then the Insights card: three placeholders in all.
    expect(container.querySelector('.lg\\:grid-cols-2')?.children).toHaveLength(2);
    expect(container.querySelectorAll('[data-skeleton-line]').length).toBeGreaterThan(8);
    expect(screen.queryByRole('region', { name: 'Last Sunday' })).not.toBeInTheDocument();
    release();
    expect(await screen.findByRole('region', { name: 'Last Sunday' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Insights' })).toBeInTheDocument();
    expect(screen.queryByRole('status', { name: 'Loading insights' })).not.toBeInTheDocument();
    expect(container.querySelector('[data-skeleton-line]')).toBeNull();
  });

  it('keeps the placeholder up while the request is still pending', async () => {
    server.use(http.get('*/api/insights/home', () => delay('infinite')));
    renderWithProviders(<HomeInsights meId={null} />);
    expect(screen.getByRole('status', { name: 'Loading insights' })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByRole('status', { name: 'Loading insights' })).toBeInTheDocument();
  });

  it('shows nothing once the feed has loaded empty, and nothing on a fetch error', async () => {
    server.use(http.get('*/api/insights/home', () => HttpResponse.json(feedFixture())));
    const empty = renderWithProviders(<HomeInsights meId={null} />);
    await waitFor(() =>
      expect(screen.queryByRole('status', { name: 'Loading insights' })).not.toBeInTheDocument(),
    );
    expect(empty.container).toBeEmptyDOMElement();
    empty.unmount();
    server.use(http.get('*/api/insights/home', () => new HttpResponse(null, { status: 500 })));
    const failed = renderWithProviders(<HomeInsights meId={null} />);
    await waitFor(() =>
      expect(screen.queryByRole('status', { name: 'Loading insights' })).not.toBeInTheDocument(),
    );
    expect(failed.container).toBeEmptyDOMElement();
  });

  it("shows the latest Sunday's kudos, with the recap and the top story side by side, each dated", async () => {
    server.use(
      http.get('*/api/insights/home', () =>
        HttpResponse.json(
          feedFixture({
            pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap' }),
            hero: insightFixture({ key: 'hero' }),
            kudos: kudosFixture(2),
          }),
        ),
      ),
    );
    renderWithProviders(<HomeInsights meId={3} />);
    const hero = await screen.findByRole('list', { name: 'Top story' });
    expect(within(hero).getByText(/New personal best:/)).toBeInTheDocument();
    expect(hero.closest('.lg\\:grid-cols-2')).not.toBeNull();
    expect(screen.getByRole('region', { name: 'Kudos from Sep 27' })).toBeInTheDocument();
    // The latest-Sunday cards name their Sunday and say the time filter does not move them.
    for (const card of ['Last Sunday', 'Top story']) {
      expect(screen.getByRole('region', { name: card })).toHaveTextContent(
        'Sep 27, 2026 · not affected by the time filter',
      );
    }
  });

  it('still labels the latest-Sunday cards when the feed carries no date', async () => {
    server.use(
      http.get('*/api/insights/home', () =>
        HttpResponse.json(
          feedFixture({
            as_of: null,
            pinned: insightFixture({ key: 'recap', kind: 'home.sunday-recap', anchor_date: null }),
            hero: insightFixture({ key: 'hero', anchor_date: null }),
            spotlight: insightFixture({ key: 'spot' }),
            kudos: kudosFixture(2),
          }),
        ),
      ),
    );
    renderWithProviders(<HomeInsights meId={3} />);
    expect(await screen.findByRole('region', { name: 'Last Sunday' })).toHaveTextContent(
      'Not affected by the time filter',
    );
    expect(screen.getByRole('region', { name: 'Top story' })).toHaveTextContent(
      'Not affected by the time filter',
    );
    expect(screen.getByRole('region', { name: 'Kudos' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Insights' })).toHaveTextContent(
      'Not affected by the time filter',
    );
  });

  it('pins the recap and shows the hero, the shooter to know and the rest', async () => {
    const recap = insightFixture({
      key: 'recap',
      kind: 'home.sunday-recap',
      headline: [{ t: 'text', v: 'Sunday 9/27: 23 shooters.' }],
    });
    server.use(
      http.get('*/api/insights/home', () =>
        HttpResponse.json(
          feedFixture({
            pinned: recap,
            hero: insightFixture({ key: 'hero' }),
            spotlight: insightFixture({ key: 'spot' }),
            top: [insightFixture({ key: 'top' })],
          }),
        ),
      ),
    );
    renderWithProviders(<HomeInsights meId={null} />);
    expect(await screen.findByRole('region', { name: 'Last Sunday' })).toHaveTextContent(
      'Sunday 9/27: 23 shooters.',
    );
    expect(screen.getByRole('list', { name: 'Top story' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Shooter to know' })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Around the club' })).toBeInTheDocument();
  });
});

describe('PageInsights', () => {
  it.each(['club', 'leaderboards', 'records', 'stations'] as const)(
```

with:

```tsx
});

describe('PageInsights', () => {
  it.each(['club', 'leaderboards', 'records', 'stations'] as const)(
```

In `frontend/src/features/insights/components/MoreInsights.test.tsx`, replace:

```tsx
import { insightFixture } from '../mocks';
import { MoreInsights } from './MoreInsights';
import { RecapCard } from './RecapCard';

describe('MoreInsights', () => {
```

with:

```tsx
import { insightFixture } from '../mocks';
import { MoreInsights } from './MoreInsights';

describe('MoreInsights', () => {
```

In `frontend/src/features/insights/components/MoreInsights.test.tsx`, replace:

```tsx
  });
});

describe('RecapCard', () => {
  it('links the results with the viewer window when the insight has no dates of its own', () => {
    const base = insightFixture();
    renderWithProviders(
      <RecapCard
        insight={insightFixture({ chart: { ...base.chart, type: 'explorer', spec: null } })}
      />,
      { route: '/?w=6m' },
    );
    expect(screen.getByRole('link', { name: 'See the results' })).toHaveAttribute(
      'href',
      '/explorer?w=6m',
    );
  });

  it('clamps to three lines until "Show all" and links the results', async () => {
    const { user } = renderWithProviders(<RecapCard insight={insightFixture()} />);
    const text = screen.getByText(/New personal best for/).closest('p');
    expect(text).toHaveClass('line-clamp-3');
    await user.click(screen.getByRole('button', { name: 'Show all' }));
    expect(text).not.toHaveClass('line-clamp-3');
    expect(screen.getByRole('link', { name: 'See the results' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show less' }));
    expect(text).toHaveClass('line-clamp-3');
  });
});
```

with:

```tsx
  });
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/app src/features/sheet/routes.test.tsx src/features/insights/homeWidget.test.tsx`

Expected: FAIL: no index route renders the Sheet ("The Sunday Sheet" heading not found at `/`); nav order 10 belongs to `home`; the insights widget still renders the home feed without an issue.

- [ ] **Step 3: Write the implementation**

Replace the whole of `frontend/src/features/sheet/routes.tsx` with:

```tsx
import { Newspaper } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { ROUND_TYPE_ONLY } from '../../lib/pageFilters';

const page = async () => ({ Component: (await import('./pages/SheetPage')).SheetPage });

/** The Sunday Sheet (Plan 14): the latest issue at `/`, any held Sunday's at `/sheet/:date`. */
export const routes: RouteObject[] = [
  { index: true, handle: { filters: ROUND_TYPE_ONLY }, lazy: page },
  { path: '/sheet/:date', handle: { filters: ROUND_TYPE_ONLY }, lazy: page },
];

export const nav: NavItem[] = [
  { label: 'Sheet', path: '/', icon: Newspaper, order: 10, mobileTab: true },
];
```

Delete `frontend/src/features/home/routes.tsx` (`git rm frontend/src/features/home/routes.tsx`).

Delete `frontend/src/features/home/routes.test.tsx` (`git rm frontend/src/features/home/routes.test.tsx`).

Delete `frontend/src/features/home/pages/HomePage.tsx` (`git rm frontend/src/features/home/pages/HomePage.tsx`).

Delete `frontend/src/features/home/pages/HomePage.test.tsx` (`git rm frontend/src/features/home/pages/HomePage.test.tsx`).

Delete `frontend/src/features/home/components/LatestEventCard.tsx` (`git rm frontend/src/features/home/components/LatestEventCard.tsx`).

Delete `frontend/src/features/home/components/LatestEventCard.test.tsx` (`git rm frontend/src/features/home/components/LatestEventCard.test.tsx`).

In `frontend/src/features/home/explainers.ts`, replace:

```ts
    ],
  },
  latestShooters: {
    what: 'How many people have at least one recorded score at the latest Sunday.',
    computed: [
      'Counts shooters with a recorded round, not everyone who came, so it can be lower than the head count.',
      'The round-type filter does not apply.',
    ],
  },
  latestMedian: {
    what: 'The middle score at the latest Sunday: half the rounds were this or better, half this or worse.',
    computed: [
      'Every round that day counts, second rounds included. Sorted by score, the middle one is taken.',
      'The round-type filter does not apply.',
    ],
  },
  latestTop: {
    what: 'The best single round at the latest Sunday, out of 50.',
    computed: [
      'The highest score among all rounds that day, second rounds included.',
      'The round-type filter does not apply.',
    ],
  },
  meLast: {
    what: 'Your most recent Sunday: the date, your best score, where it placed and how your rating moved.',
```

with:

```ts
    ],
  },
  meLast: {
    what: 'Your most recent Sunday: the date, your best score, where it placed and how your rating moved.',
```

In `frontend/src/features/insights/homeWidget.tsx`, replace:

```tsx
import type { HomeWidget, HomeWidgetProps } from '../home/widgets';
import { HomeInsights } from './components/FeedSections';
import { SheetLead } from './components/SheetLead';

/**
 * The Sunday Sheet's lead (Plan 14): the issue's headline with its recap as the deck, then the
 * spotlight. Without an issue (the Home page, until Task 9 retires it) it is the home feed.
 */
function InsightsLead({ meId, issue }: HomeWidgetProps) {
  if (issue === undefined) return <HomeInsights meId={meId} />;
  return (
    <SheetLead
```

with:

```tsx
import type { HomeWidget, HomeWidgetProps } from '../home/widgets';
import { SheetLead } from './components/SheetLead';

/**
 * The Sunday Sheet's lead (Plan 14): the issue's headline with its recap as the deck, then the
 * spotlight. Nothing outside an issue.
 */
function InsightsLead({ meId, issue }: HomeWidgetProps) {
  if (issue === undefined) return null;
  return (
    <SheetLead
```

In `frontend/src/features/insights/components/FeedSections.tsx`, replace:

```tsx
import type { PageKey } from '../../../components/layout/pageTop';
import { Card } from '../../../components/ui/Card';
import { Skeleton } from '../../../components/ui/Skeleton';
import { formatShortDate } from '../../../lib/format';
import { getMe } from '../../../lib/me';
import { formatDay } from '../../shooters/format';
import { useHomeFeed, usePageFeed, useShooterFeed, useSundayFeed, type InsightFeed } from '../api';
import { InsightCard } from './InsightCard';
import { InsightList, isMine } from './InsightList';
import { KudosStrip } from './KudosStrip';
import { MoreInsights } from './MoreInsights';
import { latestSubtitle, RecapCard } from './RecapCard';

function isEmpty(feed: InsightFeed): boolean {
```

with:

```tsx
import type { PageKey } from '../../../components/layout/pageTop';
import { Card } from '../../../components/ui/Card';
import { getMe } from '../../../lib/me';
import { formatDay } from '../../shooters/format';
import { usePageFeed, useShooterFeed, useSundayFeed, type InsightFeed } from '../api';
import { InsightList } from './InsightList';
import { KudosStrip } from './KudosStrip';
import { MoreInsights } from './MoreInsights';

function isEmpty(feed: InsightFeed): boolean {
```

In `frontend/src/features/insights/components/FeedSections.tsx`, replace:

```tsx

/**
 * Stands in for the home cards while the feed loads, at roughly their final height, so the page
 * below does not jump when they arrive. One status for the lot; the extra cards are hidden from
 * assistive tech.
 */
function HomeInsightsPlaceholder() {
  return (
    <>
      <div className="grid min-w-0 gap-4 lg:grid-cols-2">
        <Card>
          <Skeleton label="Loading insights" lines={4} className="min-h-40" />
        </Card>
        <Card>
          <div aria-hidden="true">
            <Skeleton label="Loading top story" lines={4} className="min-h-40" />
          </div>
        </Card>
      </div>
      <Card>
        <div aria-hidden="true">
          <Skeleton label="Loading more insights" lines={8} className="min-h-72" />
        </div>
      </Card>
    </>
  );
}

/**
 * Home: the pinned recap and the hero side by side on desktop, then "Shooter to know", the
 * latest Sunday's kudos across the page, one card per slot in a 2 × 2 grid, and the rest.
 */
export function HomeInsights({ meId }: { meId: number | null }) {
  const feed = useHomeFeed();
  if (feed.isPending) return <HomeInsightsPlaceholder />;
  // A failed fetch shows nothing: the other home cards already report an outage.
  if (feed.data === undefined || isEmpty(feed.data)) return null;
  const f = feed.data;
  return (
    <>
      {(f.pinned != null || f.hero != null) && (
        <div className="grid min-w-0 gap-4 lg:grid-cols-2">
          {f.pinned != null && <RecapCard insight={f.pinned} />}
          {f.hero != null && (
            <Card title="Top story" subtitle={latestSubtitle(f.hero.anchor_date)}>
              <ul aria-label="Top story" className="flex flex-col gap-3">
                <InsightCard insight={f.hero} you={isMine(f.hero, meId)} />
              </ul>
            </Card>
          )}
        </div>
      )}
      {(f.spotlight != null || f.top.length > 0 || f.kudos.length > 0 || f.more.length > 0) && (
        <Card
          title="Insights"
          subtitle={
            f.as_of == null
              ? 'Not affected by the time filter'
              : `As of ${formatDay(f.as_of)} · not affected by the time filter`
          }
        >
          <div className="flex min-w-0 flex-col gap-3">
            {f.spotlight != null && (
              <section aria-label="Shooter to know" className="flex flex-col gap-2">
                <h3 className="text-sm font-medium text-text-muted">Shooter to know</h3>
                <ul className="flex flex-col gap-3">
                  <InsightCard insight={f.spotlight} you={isMine(f.spotlight, meId)} />
                </ul>
              </section>
            )}
            <KudosStrip
              kudos={f.kudos}
              meId={meId}
              title={f.as_of == null ? 'Kudos' : `Kudos from ${formatShortDate(f.as_of)}`}
            />
            <InsightList items={f.top} meId={meId} label="Around the club" columns={2} />
            <MoreInsights items={f.more} total={f.n_more} meId={meId} />
          </div>
        </Card>
      )}
    </>
  );
}

/**
 * Club, leaderboards, records and stations: the page's top 3 (one per family) and the rest,
 * under the page title. Built as of the latest Sunday, so the header window does not change them.
```

with:

```tsx

/**
 * Club, leaderboards, records and stations: the page's top 3 (one per family) and the rest,
 * under the page title. Built as of the latest Sunday, so the header window does not change them.
```

Delete `frontend/src/features/insights/components/RecapCard.tsx` (`git rm frontend/src/features/insights/components/RecapCard.tsx`).

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm typecheck && pnpm test --coverage`

Expected: tsc exits 0; the whole suite passes (243 files in the replay); lines and branches stay at or above the ratchet.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
# the deletions above are already staged by `git rm`
git add frontend/src/features/sheet/routes.test.tsx frontend/src/app/registry.test.ts frontend/src/app/navRegistry.test.ts frontend/src/app/App.test.tsx frontend/src/app/App.session.test.tsx frontend/src/app/router.test.tsx frontend/src/features/insights/homeWidget.test.tsx frontend/src/features/home/explainers.test.ts frontend/src/features/insights/components/FeedSections.test.tsx frontend/src/features/insights/components/MoreInsights.test.tsx frontend/src/features/sheet/routes.tsx frontend/src/features/home/explainers.ts frontend/src/features/insights/homeWidget.tsx frontend/src/features/insights/components/FeedSections.tsx
git commit -m "feat(sheet): / is the Sunday Sheet; Home retires" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 9.2 e2e: specs that visited Home

- [ ] **Step 6: Write the specs**

These specs describe pages that changed in the cycle above: Home is gone, the Sheet has no time-window control, and the phone tab is "Sheet". Build and start the stack from this branch first (see "Running the e2e stack"), then run them from `frontend/`.

Replace the whole of `frontend/e2e/home.spec.ts` (it now checks the Sheet at `/` and the rail Home handed over) with:

```ts
import { readFile } from 'node:fs/promises';

import { expect, test } from './fixtures';
import { expectNoSideScroll, expectTapTargets, whenSettled } from './layout';
import { longDate } from './window';

/**
 * `/` is the Sunday Sheet (Plan 14): the latest issue, with Home's rail (Your Sunday, Next
 * Sunday, Club pulse and the latest Sunday's details) beside the feed.
 */
interface Meta {
  first_event_date: string;
  last_score_date: string;
}

test('the front door is the latest Sunday Sheet, with the rail and the "Which one are you?" card', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await expect(
    page.getByRole('link', { name: `Full results, ${longDate(meta.last_score_date)}` }),
  ).toBeVisible();
  await expect(page.getByRole('region', { name: 'Which one are you?' })).toBeVisible();
  await expect(page.getByText('Turnout per Sunday', { exact: true })).toBeVisible();
});

test('the latest Sunday details link opens the full results', async ({ page }) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  await page.goto('/');
  await page.getByRole('link', { name: /^Full results, / }).click();
  await expect(page).toHaveURL(new RegExp(`/events/${meta.last_score_date}$`));
});

test('every Sheet tap target is at least 44px with the "Which one are you?" card', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Which one are you?' })).toBeVisible();
  await whenSettled(page);
  await expectTapTargets(page);
});

test('every Sheet tap target is at least 44px with a me id', async ({ page }) => {
  const response = await page.request.get('/api/shooters?q=Hadley');
  expect(response.status()).toBe(200);
  const shooters = (await response.json()) as { shooter_id: number; display_name: string }[];
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  expect(hadley).toBeDefined();
  await page.addInitScript((id) => localStorage.setItem('sc.me', String(id)), hadley?.shooter_id);
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible();
  await expect(page.getByText('Last out')).toBeVisible();
  await whenSettled(page);
  await expectTapTargets(page);
});

test('the club pulse shows the 8 weeks up to the issue, whatever the time window says', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  await page.goto('/?w=all');
  const pulse = page.getByRole('region', { name: 'Club pulse' });
  await expect(
    pulse.getByText(
      `8 weeks to ${longDate(meta.last_score_date)} · not affected by the time filter`,
    ),
  ).toBeVisible();
  const chart = page.getByRole('region', { name: 'Turnout per Sunday' });
  await chart.getByRole('button', { name: 'About this chart' }).click();
  await expect(chart.getByRole('heading', { name: 'What this shows' })).toBeVisible();
  await expect(chart.getByText(/the Sheet always shows the 8 weeks/)).toBeVisible();
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('the turnout chart lists and exports every Sunday on record, not just the 8 weeks', async ({
  page,
}) => {
  // Every scored Sunday, year by year, read from the API at run time.
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  const first = Number(meta.first_event_date.slice(0, 4));
  const last = Number(meta.last_score_date.slice(0, 4));
  let scored = 0;
  for (let year = first; year <= last; year += 1) {
    const events = (await (await page.request.get(`/api/events?year=${year}`)).json()) as {
      has_scores: boolean;
    }[];
    scored += events.filter((e) => e.has_scores).length;
  }
  expect(scored).toBeGreaterThan(0);

  await page.goto('/');
  const chart = page.getByRole('region', { name: 'Turnout per Sunday' });
  const download = page.waitForEvent('download');
  await chart.getByRole('button', { name: 'CSV' }).click({ timeout: 15_000 });
  const file = await download;
  const text = (await readFile(await file.path(), 'utf8')).replace(/^\uFEFF/, '');
  expect(text.trimEnd().split('\r\n')).toHaveLength(scored + 1);

  await chart.getByRole('button', { name: 'Table' }).click();
  await expect(chart.getByRole('row').nth(1)).toBeVisible();
  const inlineRows = await chart.getByRole('row').count();
  expect(inlineRows - 1).toBeLessThan(scored);
  await page.setViewportSize({ width: 1440, height: 900 });
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  const dialog = page.getByRole('dialog', { name: 'Turnout per Sunday' });
  await expect(dialog.getByRole('row')).toHaveCount(scored + 1);
  await page.keyboard.press('Escape');

  await page.setViewportSize({ width: 390, height: 844 });
  await chart.getByRole('button', { name: 'Fullscreen' }).click();
  await expect(dialog.getByRole('row')).toHaveCount(scored + 1);
  await expectNoSideScroll(page);
});
```

In `frontend/e2e/insights.spec.ts`, replace:

```ts
}

test('home shows the recap, the top story, the insight cards and kudos', async ({ page }) => {
  const feed = await getJson<Feed>(page, '/api/insights/home');
  expect(feed.pinned, 'the fx world has a latest Sunday to recap').not.toBeNull();
  await page.goto('/');
  await whenSettled(page);
  await expect(page.getByRole('region', { name: 'Last Sunday' })).toBeVisible();
  if (feed.hero !== null) {
    await expect(page.getByRole('list', { name: 'Top story' })).toBeVisible();
  }
  if (feed.top.length > 0) {
    await expect(
      page.getByRole('list', { name: 'Around the club' }).getByRole('listitem'),
    ).toHaveCount(feed.top.length);
  }
  if (feed.kudos.length > 0) {
    await expect(page.getByRole('region', { name: /^Kudos/ })).toBeVisible();
  }
  await expectNoSideScroll(page);
```

with:

```ts
}

test('the Sunday Sheet leads with the top story, its recap deck and the spotlight', async ({
  page,
}) => {
  const issue = await getJson<{
    headline: Insight | null;
    recap: Insight | null;
    spotlight: Insight | null;
  }>(page, '/api/sheet/latest');
  expect(issue.recap, 'the fx world has a latest Sunday to recap').not.toBeNull();
  await page.goto('/');
  await whenSettled(page);
  const lead = page.getByRole('region', { name: 'Top story' });
  await expect(lead.getByRole('button', { name: 'Show all' })).toBeVisible();
  if (issue.headline !== null) {
    await expect(lead.getByRole('list', { name: 'Top story' })).toBeVisible();
  }
  if (issue.spotlight !== null) {
    await expect(page.getByRole('list', { name: 'Spotlight' })).toBeVisible();
  }
  await expectNoSideScroll(page);
```

In `frontend/e2e/yir.spec.ts`, replace:

```ts
  await expectTitlesUntruncated(page);
});

test('home shows On this day', async ({ page }) => {
  await page.goto('/');
  const card = page.getByRole('region', { name: 'On this day' });
  await expect(card.getByRole('heading', { name: 'On this day' })).toBeVisible();
  // Which Sundays appear depends on today's date, so only the loaded state is checked.
  await expect(card.getByText(/years? ago|No Sunday near this date/).first()).toBeVisible();
  await expectNoSideScroll(page);
});
```

with:

```ts
  await expectTitlesUntruncated(page);
});
```

In `frontend/e2e/filters-placement.spec.ts`, replace:

```ts
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the content header only exists from 1024 px');
  await page.goto('/');
  const bar = page.getByRole('group', { name: 'Page filters' });
  await expect(bar).toBeVisible();
```

with:

```ts
}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'the content header only exists from 1024 px');
  await page.goto('/club');
  const bar = page.getByRole('group', { name: 'Page filters' });
  await expect(bar).toBeVisible();
```

In `frontend/e2e/filters-placement.spec.ts`, replace:

```ts
}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the top bar only exists below 1024 px');
  await page.goto('/');
  const top = page.locator('header').first();
  await expect(top.getByRole('button', { name: 'Round type' })).toBeVisible();
```

with:

```ts
}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the top bar only exists below 1024 px');
  await page.goto('/club');
  const top = page.locator('header').first();
  await expect(top.getByRole('button', { name: 'Round type' })).toBeVisible();
```

In `frontend/e2e/filters-placement.spec.ts`, replace:

```ts
});

test('Trophies shows no filter bar at all', async ({ page }, testInfo) => {
  await page.goto('/achievements?rt=sporting&w=6m');
```

with:

```ts
});

test('The Sunday Sheet shows the round-type filter and no time window', async ({
  page,
}, testInfo) => {
  await page.goto('/?w=6m');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  const shown = await shownFilters(page, testInfo);
  await expect(shown.roundType).toBeVisible();
  await expect(shown.window).toHaveCount(0);
  await expect(page).toHaveURL(/[?&]w=6m(&|$)/);
  await expectNoSideScroll(page);
});

test('the phone top bar keeps its brand, filter and time window on one row', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'the top bar only exists below 1024 px');
  for (const width of [360, 390, 414]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/club');
    const header = page.locator('header').first();
    await expect(header).toBeVisible();
    const select = header.getByRole('combobox', { name: 'Time window' });
    await expect(select).toBeVisible();
    // Short labels on screen, the full wording for assistive tech.
    expect(
      await select.evaluate((el: HTMLSelectElement) => el.selectedOptions[0]?.textContent),
    ).toBe('8W');
    await expect(select).toHaveAccessibleDescription('Last 8 weeks');
    const tops = await header
      .locator(':scope > *')
      .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().top)));
    expect(tops.length).toBeGreaterThanOrEqual(3);
    expect(new Set(tops).size, `children start on different rows at ${width} px`).toBe(1);
    const box = await header.boundingBox();
    expect(box?.height ?? 0, `header height at ${width} px`).toBeLessThanOrEqual(64);
    await expectNoSideScroll(page);
  }
});

test('Trophies shows no filter bar at all', async ({ page }, testInfo) => {
  await page.goto('/achievements?rt=sporting&w=6m');
```

In `frontend/e2e/thin-window.spec.ts`, replace:

```ts
});

test('Home at All time asks for the club pulse in one request, not one per year', async ({
  page,
}) => {
  const eventRequests: string[] = [];
  page.on('request', (r) => {
```

with:

```ts
});

test('the Sheet asks for its club pulse in one request, for its own 8 weeks even at All time', async ({
  page,
}) => {
  const meta = (await (await page.request.get('/api/meta')).json()) as Meta;
  const from = new Date(`${meta.last_score_date}T12:00:00Z`);
  from.setUTCDate(from.getUTCDate() - 55);
  const eventRequests: string[] = [];
  page.on('request', (r) => {
```

In `frontend/e2e/thin-window.spec.ts`, replace:

```ts
  const pulse = eventRequests.filter((url) => !new URL(url).searchParams.has('year'));
  expect(pulse).toHaveLength(1);
  expect(new URL(pulse[0] ?? '').searchParams.has('from')).toBe(false);
  expect(eventRequests.filter((url) => new URL(url).searchParams.has('year'))).toEqual([]);
  await expectNoSideScroll(page);
```

with:

```ts
  const pulse = eventRequests.filter((url) => !new URL(url).searchParams.has('year'));
  expect(pulse).toHaveLength(1);
  const query = new URL(pulse[0] ?? '').searchParams;
  expect(query.get('from')).toBe(from.toISOString().slice(0, 10));
  expect(query.get('to')).toBe(meta.last_score_date);
  expect(eventRequests.filter((url) => new URL(url).searchParams.has('year'))).toEqual([]);
  await expectNoSideScroll(page);
```

In `frontend/e2e/ux-foundation.spec.ts`, replace:

```ts
  await home.click();
  await expect(page).toHaveURL(/[?&]w=6m(&|$)/);
  const after = await windowControl(page);
  if (after.kind === 'select') await expect(after.select).toHaveValue('6m');
```

with:

```ts
  await home.click();
  await expect(page).toHaveURL(/[?&]w=6m(&|$)/);
  // The Sunday Sheet keeps `w` in its URL but shows no window control; back on the profile the
  // window still applies.
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await page.goBack();
  const after = await windowControl(page);
  if (after.kind === 'select') await expect(after.select).toHaveValue('6m');
```

In `frontend/e2e/ux-foundation.spec.ts`, replace:

```ts
  page,
}) => {
  await page.goto('/');
  const control = await windowControl(page);
  if (control.kind === 'select') {
```

with:

```ts
  page,
}) => {
  await page.goto('/club');
  const control = await windowControl(page);
  if (control.kind === 'select') {
```

In `frontend/e2e/ux-foundation.spec.ts`, replace:

```ts
  await expect(page).toHaveURL(/[?&]w=ytd(&|$)/);

  await page.goto('/?w=season');
  const retired = await windowControl(page);
  if (retired.kind === 'select') await expect(retired.select).toHaveValue('8w');
```

with:

```ts
  await expect(page).toHaveURL(/[?&]w=ytd(&|$)/);

  await page.goto('/club?w=season');
  const retired = await windowControl(page);
  if (retired.kind === 'select') await expect(retired.select).toHaveValue('8w');
```

In `frontend/e2e/date-range.spec.ts`, replace:

```ts
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  // In-app navigation keeps it: Home is a tab, Club sits in More.
  await page.getByRole('navigation', { name: 'Tabs' }).getByRole('link', { name: 'Home' }).click();
  await expect(page).toHaveURL(new RegExp(`w=${start}\\.\\.${end}`));
  await page
```

with:

```ts
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  // In-app navigation keeps it: the Sheet is a tab, Club sits in More.
  await page.getByRole('navigation', { name: 'Tabs' }).getByRole('link', { name: 'Sheet' }).click();
  await expect(page).toHaveURL(new RegExp(`w=${start}\\.\\.${end}`));
  await page
```

In `frontend/e2e/smoke.spec.ts`, replace:

```ts
  expect(headers['referrer-policy']).toBe('same-origin');
  expect(headers['cache-control']).toBe('no-cache');
  await expect(page.getByRole('heading', { name: 'Sunday Clays' })).toBeVisible();
});
```

with:

```ts
  expect(headers['referrer-policy']).toBe('same-origin');
  expect(headers['cache-control']).toBe('no-cache');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
});
```

- [ ] **Step 7: Run them on a stack built from this branch**

Run: `cd frontend && E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/home.spec.ts e2e/insights.spec.ts e2e/yir.spec.ts e2e/filters-placement.spec.ts e2e/thin-window.spec.ts e2e/ux-foundation.spec.ts e2e/date-range.spec.ts e2e/smoke.spec.ts e2e/login.spec.ts e2e/predictions.spec.ts e2e/leaderboards.spec.ts`

Expected: all pass at both viewports (the `smoke` "shared fixture" tests are `test.fail` and show as expected failures).

- [ ] **Step 8: Commit**

From the worktree root:

```bash
git add frontend/e2e/home.spec.ts frontend/e2e/insights.spec.ts frontend/e2e/yir.spec.ts frontend/e2e/filters-placement.spec.ts frontend/e2e/thin-window.spec.ts frontend/e2e/ux-foundation.spec.ts frontend/e2e/date-range.spec.ts frontend/e2e/smoke.spec.ts
git commit -m "test(e2e): specs follow Home to the Sunday Sheet" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 9.3 Gates

- [ ] **Step 9: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 10: Share and "See why"

**Wave 4** · parallel with: Task 8 · branch `task/14-10-share-see-why` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

**Files:**
- Modify: `frontend/src/lib/share.ts` (add `shareLink`), `frontend/src/features/share/filenames.ts` (add `sheetPostFilename`)
- Create: `frontend/src/features/sheet/components/SeeWhy.tsx`, `PostShareCard.tsx`, `SharePostButton.tsx`, `ShareSheetButton.tsx`
- Modify: `frontend/src/features/sheet/components/PostCard.tsx`, `Masthead.tsx`
- Test: `frontend/src/lib/share.test.ts`, `frontend/src/features/share/filenames.test.ts`
- Test: `frontend/src/features/sheet/components/SeeWhy.test.tsx`, `SharePostButton.test.tsx`, `ShareSheetButton.test.tsx`

**Interfaces:**
- Consumes:
  - Task 4: `SheetPost`, `SheetIssue`, `PostCard`, `Masthead`, mocks `postFixture`, `trophyPost`, `onThisDayPost`, `sheetFixture`.
  - `lib/share` `shareElementAsImage(el, filename)`; `features/share/filenames` `slugify`; `features/insights/chartLink` `chartHref`; `features/insights/segments` `segmentsText`; `lib/roundTypes` `useRoundTypeHref`; `lib/timeWindowChoice` `useExplicitWindow`; `features/achievements/components/TrophyIcon`; `react-dom` `createPortal`, `flushSync`.
- Produces:
  - `lib/share.ts`: `type LinkShareOutcome = "shared" | "copied" | "cancelled"`, `shareLink({ title, text, url }): Promise<LinkShareOutcome>`; `features/share/filenames.ts`: `sheetPostFilename(date, headline): string`.
  - `SeeWhy({ post })` (link "See why →", accessible name `See why: {label}`), `PostShareCard({ post, date })`, `SharePostButton({ post, date })` (button "Share image"), `ShareSheetButton({ issue })` (button "Share this Sheet"), `sheetShareText(issue): string`. Every post shows "See why →" and Share; the masthead shows "Share this Sheet".

#### 10.1 Share helpers

- [ ] **Step 1: Write the failing test**

In `frontend/src/lib/share.test.ts`, replace:

```ts
import { toBlob } from 'html-to-image';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from './share';

vi.mock('html-to-image', () => ({ toBlob: vi.fn() }));
```

with:

```ts
import { toBlob } from 'html-to-image';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage, shareLink } from './share';

vi.mock('html-to-image', () => ({ toBlob: vi.fn() }));
```

In `frontend/src/lib/share.test.ts`, replace:

```ts
    vi.unstubAllGlobals();
  });
});
```

with:

```ts
    vi.unstubAllGlobals();
  });
});

describe('shareLink', () => {
  const data = {
    title: 'The Sunday Sheet',
    text: '23 shooters',
    url: 'https://x.test/sheet/2026-09-27',
  };

  function stubClipboard() {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    return writeText;
  }

  it('shares through the Web Share API when the browser can', async () => {
    const share = vi.spyOn(navigator, 'share').mockResolvedValue(undefined);
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    await expect(shareLink(data)).resolves.toBe('shared');
    expect(share).toHaveBeenCalledWith(data);
  });

  it('is cancelled when the share sheet is dismissed', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('no', 'AbortError'));
    await expect(shareLink(data)).resolves.toBe('cancelled');
  });

  it('copies the text and link when sharing is refused or missing', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('no', 'NotAllowedError'));
    const writeText = stubClipboard();
    await expect(shareLink(data)).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledWith('23 shooters\nhttps://x.test/sheet/2026-09-27');
  });

  it('copies when the browser cannot share this link', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(false);
    const writeText = stubClipboard();
    await expect(shareLink(data)).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledTimes(1);
  });

  it('passes any other share failure on', async () => {
    vi.spyOn(navigator, 'canShare').mockReturnValue(true);
    vi.spyOn(navigator, 'share').mockRejectedValue(new DOMException('no', 'DataError'));
    await expect(shareLink(data)).rejects.toThrow('no');
    vi.spyOn(navigator, 'share').mockRejectedValue(new TypeError('bad'));
    await expect(shareLink(data)).rejects.toThrow('bad');
  });
});
```

Replace the whole of `frontend/src/features/share/filenames.test.ts` with:

```ts
import { describe, expect, it } from 'vitest';
import {
  cardFilename,
  eventFilename,
  profileFilename,
  sheetPostFilename,
  slugify,
  trophyFilename,
} from './filenames';

describe('share filenames', () => {
  it('slugifies names, codes and titles', () => {
    expect(slugify('Hadley, Ike')).toBe('hadley-ike');
    expect(slugify('Ömer  Çelik!')).toBe('omer-celik');
    expect(slugify('!!!')).toBe('image');
  });

  it('names each kind of image', () => {
    expect(eventFilename('2026-09-13')).toBe('sunday-clays-2026-09-13.png');
    expect(profileFilename('Hadley, Ike')).toBe('sunday-clays-hadley-ike.png');
    expect(trophyFilename('clays_broken:3')).toBe('sunday-clays-trophy-clays-broken-3.png');
    expect(cardFilename('2025 at a glance')).toBe('sunday-clays-2025-at-a-glance.png');
    expect(sheetPostFilename('2026-09-27', 'New personal best for Ike Hadley: 46, and more.')).toBe(
      'sunday-sheet-2026-09-27-new-personal-best-for-ike-hadley.png',
    );
    expect(sheetPostFilename('2026-09-27', '!!!')).toBe('sunday-sheet-2026-09-27-image.png');
  });
});
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/lib/share.test.ts src/features/share/filenames.test.ts`

Expected: FAIL: `shareLink is not a function`; `sheetPostFilename is not a function`.

- [ ] **Step 3: Write the implementation**

In `frontend/src/lib/share.ts`, replace:

```ts
}

/**
 * Renders `el` to a PNG and hands it to the Web Share API when the browser can share files,
```

with:

```ts
}

export type LinkShareOutcome = 'shared' | 'copied' | 'cancelled';

/**
 * Shares a link with the Web Share API when the browser has it, otherwise copies "text, newline,
 * url" to the clipboard. Resolves 'cancelled' when the user dismisses the share sheet. A
 * NotAllowedError (Safari after an async gap) falls back to the clipboard too.
 */
export async function shareLink(data: {
  title: string;
  text: string;
  url: string;
}): Promise<LinkShareOutcome> {
  const canShare = typeof navigator.canShare !== 'function' || navigator.canShare(data);
  if (typeof navigator.share === 'function' && canShare) {
    try {
      await navigator.share(data);
      return 'shared';
    } catch (error) {
      if (!(error instanceof DOMException)) throw error;
      if (error.name === 'AbortError') return 'cancelled';
      if (error.name !== 'NotAllowedError') throw error;
    }
  }
  await navigator.clipboard.writeText(`${data.text}\n${data.url}`);
  return 'copied';
}

/**
 * Renders `el` to a PNG and hands it to the Web Share API when the browser can share files,
```

In `frontend/src/features/share/filenames.ts`, replace:

```ts
  return `sunday-clays-${slugify(title)}.png`;
}
```

with:

```ts
  return `sunday-clays-${slugify(title)}.png`;
}

/** A Sunday Sheet post: the issue's date and the first words of the headline. */
export function sheetPostFilename(date: string, headline: string): string {
  const words = slugify(headline).split('-').slice(0, 6).join('-');
  return `sunday-sheet-${date}-${words}.png`;
}
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/lib/share.test.ts src/features/share`

Expected: all pass.

- [ ] **Step 5: Commit**

From the worktree root:

```bash
git add frontend/src/lib/share.test.ts frontend/src/features/share/filenames.test.ts frontend/src/lib/share.ts frontend/src/features/share/filenames.ts
git commit -m "feat(sheet): share a link (Web Share API or clipboard) and name post images" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 10.2 "See why", post images and "Share this Sheet"

- [ ] **Step 6: Write the failing test**

Create `frontend/src/features/sheet/components/SeeWhy.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { chartHref } from '../../insights/chartLink';
import { onThisDayPost, postFixture, trophyPost } from '../mocks';
import { SeeWhy } from './SeeWhy';

describe('SeeWhy', () => {
  it('opens an insight post’s chart with its own window and highlight, never a round type', () => {
    const post = postFixture();
    renderWithProviders(<SeeWhy post={post} />, { route: '/?rt=sporting' });
    const link = screen.getByRole('link', {
      name: "See why: Ike Hadley's scores, with the personal-best line",
    });
    expect(link).toHaveTextContent('See why →');
    const chart = post.see_why.chart;
    if (chart == null) throw new Error('the fixture post links a chart');
    expect(link).toHaveAttribute('href', chartHref(chart, null));
    expect(link.getAttribute('href')).toContain('trend.hl=2026-09-27');
    expect(link.getAttribute('href')).toContain('#chart-trend');
    expect(link.getAttribute('href')).not.toContain('rt=');
  });

  it('opens a trophy’s Trophy Room entry and keeps the global filters', () => {
    renderWithProviders(<SeeWhy post={trophyPost} />, { route: '/?rt=sporting' });
    expect(
      screen.getByRole('link', { name: 'See why: First win in the Trophy Room' }),
    ).toHaveAttribute('href', '/achievements/first_win?rt=sporting');
  });

  it('opens that Sunday’s page for "On this day"', () => {
    renderWithProviders(<SeeWhy post={onThisDayPost} />);
    expect(screen.getByRole('link', { name: "See why: That Sunday's results" })).toHaveAttribute(
      'href',
      '/events/2025-09-28',
    );
  });
});
```

Create `frontend/src/features/sheet/components/SharePostButton.test.tsx`:

```tsx
import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { shareElementAsImage } from '../../../lib/share';
import { renderWithProviders } from '../../../test/render';
import { postFixture, trophyPost } from '../mocks';
import { PostShareCard } from './PostShareCard';
import { SharePostButton } from './SharePostButton';

vi.mock('../../../lib/share', () => ({ shareElementAsImage: vi.fn() }));

afterEach(() => {
  vi.mocked(shareElementAsImage).mockReset();
});

describe('SharePostButton', () => {
  it('renders the branded card off screen, shares it, then removes it', async () => {
    const shared: { text: string; filename: string }[] = [];
    vi.mocked(shareElementAsImage).mockImplementation((el, filename) => {
      shared.push({ text: el.textContent ?? '', filename });
      return Promise.resolve('downloaded');
    });
    const { user } = renderWithProviders(
      <SharePostButton post={postFixture()} date="2026-09-27" />,
    );
    await user.click(screen.getByRole('button', { name: 'Share image' }));
    await waitFor(() => expect(shared).toHaveLength(1));
    expect(shared[0]?.filename).toBe(
      'sunday-sheet-2026-09-27-new-personal-best-for-ike-hadley.png',
    );
    expect(shared[0]?.text).toContain('The Sunday Sheet · Sep 27, 2026');
    expect(shared[0]?.text).toContain('New personal best for Ike Hadley: 46.');
    await waitFor(() => expect(document.body.textContent).not.toContain('The Sunday Sheet ·'));
    expect(screen.getByRole('button', { name: 'Share image' })).toBeEnabled();
  });

  it('says so when the image cannot be made', async () => {
    vi.mocked(shareElementAsImage).mockRejectedValue(new Error('canvas'));
    const { user } = renderWithProviders(<SharePostButton post={trophyPost} date="2026-09-27" />);
    await user.click(screen.getByRole('button', { name: 'Share image' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not create the image.');
  });
});

describe('PostShareCard', () => {
  it('carries the masthead strip, the headline and the chart it links to', () => {
    renderWithProviders(<PostShareCard post={postFixture()} date="2026-09-27" />);
    expect(screen.getByText('The Sunday Sheet · Sep 27, 2026')).toBeInTheDocument();
    expect(screen.getByText('46').tagName).toBe('STRONG');
    expect(
      screen.getByText("📈 Ike Hadley's scores, with the personal-best line"),
    ).toBeInTheDocument();
  });

  it('carries the trophy art for a trophy post, and no chart line', () => {
    const { container } = renderWithProviders(
      <PostShareCard post={trophyPost} date="2026-09-27" />,
    );
    expect(container.querySelector('svg, img')).not.toBeNull();
    expect(screen.queryByText(/📈/)).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });
});
```

Create `frontend/src/features/sheet/components/ShareSheetButton.test.tsx`:

```tsx
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { shareLink } from '../../../lib/share';
import { renderWithProviders } from '../../../test/render';
import { sheetFixture } from '../mocks';
import { ShareSheetButton, sheetShareText } from './ShareSheetButton';

vi.mock('../../../lib/share', () => ({ shareLink: vi.fn() }));

afterEach(() => {
  vi.mocked(shareLink).mockReset();
});

describe('ShareSheetButton', () => {
  it('shares the issue link with the four numbers as text', async () => {
    vi.mocked(shareLink).mockResolvedValue('shared');
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(shareLink).toHaveBeenCalledWith({
      title: 'The Sunday Sheet',
      text: 'The Sunday Sheet, Sep 27, 2026: 23 shooters, field median 39, top score 49, 13 trophies.',
      url: `${window.location.origin}/sheet/2026-09-27`,
    });
    expect(screen.queryByText('Link copied.')).toBeNull();
  });

  it('says when the link was copied instead, and when it failed', async () => {
    vi.mocked(shareLink).mockResolvedValueOnce('copied').mockRejectedValueOnce(new Error('no'));
    const { user } = renderWithProviders(<ShareSheetButton issue={sheetFixture()} />);
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(await screen.findByText('Link copied.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Share this Sheet' }));
    expect(await screen.findByText('Could not share the link.')).toBeInTheDocument();
  });

  it('writes one shooter and one trophy in the singular', () => {
    const issue = sheetFixture({
      numbers: { shooters: 1, median: null, top_score: null, trophies: 1 },
    });
    expect(sheetShareText(issue)).toBe(
      'The Sunday Sheet, Sep 27, 2026: 1 shooter, field median —, top score —, 1 trophy.',
    );
  });
});
```

- [ ] **Step 7: Run it to make sure it fails**

Run: `cd frontend && pnpm exec vitest run src/features/sheet/components`

Expected: FAIL: `Failed to resolve import "./SeeWhy"`, `"./SharePostButton"`, `"./PostShareCard"`, `"./ShareSheetButton"`.

- [ ] **Step 8: Write the implementation**

Create `frontend/src/features/sheet/components/SeeWhy.tsx`:

```tsx
import { Link } from 'react-router';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import { useExplicitWindow } from '../../../lib/timeWindowChoice';
import { chartHref } from '../../insights/chartLink';
import type { SheetPost } from '../api';

/**
 * "See why →": an insight post opens its chart, which scrolls into view and rings the evidence
 * (the Plan 12 chart-target link, never a round-type filter); a trophy post opens its Trophy Room
 * entry and an "On this day" post that Sunday's page, both keeping the global filters.
 */
export function SeeWhy({ post }: { post: SheetPost }) {
  const viewerWindow = useExplicitWindow();
  const withFilters = useRoundTypeHref();
  const why = post.see_why;
  const to =
    why.kind === 'chart' && why.chart != null
      ? chartHref(why.chart, viewerWindow)
      : withFilters(why.href ?? '/');
  return (
    <Link
      to={to}
      aria-label={`See why: ${why.label}`}
      className="inline-flex min-h-11 items-center rounded-button px-3 text-sm text-accent hover:underline"
    >
      See why →
    </Link>
  );
}
```

Create `frontend/src/features/sheet/components/PostShareCard.tsx`:

```tsx
import { TrophyIcon } from '../../achievements/components/TrophyIcon';
import { formatDay } from '../../home/format';
import type { SheetPost } from '../api';

/**
 * The image a post is shared as: a masthead strip, the headline, and the trophy art or the chart
 * it links to. Theme tokens only; no external fonts or images (the CSP allows none).
 */
export function PostShareCard({ post, date }: { post: SheetPost; date: string }) {
  const why = post.see_why;
  return (
    <article className="flex w-[360px] flex-col gap-3 rounded-card bg-surface p-4 text-text">
      <p className="border-b-2 border-accent pb-2 text-xs font-bold uppercase tracking-widest">
        {`The Sunday Sheet · ${formatDay(date)}`}
      </p>
      <div className="flex items-start gap-3">
        {post.trophy != null && (
          <TrophyIcon
            artKey={post.trophy.art_key}
            metal={post.trophy.metal}
            locked={false}
            size={64}
          />
        )}
        <p className="text-lg font-medium">
          {post.headline.map((s, i) =>
            s.t === 'num' ? (
              <strong key={`${String(i)}-num`}>{s.v}</strong>
            ) : (
              <span key={`${String(i)}-${s.t}`}>{s.v}</span>
            ),
          )}
        </p>
      </div>
      {why.kind === 'chart' && <p className="text-sm text-text-muted">{`📈 ${why.label}`}</p>}
      <p className="text-xs text-text-muted">Sunday Clays</p>
    </article>
  );
}
```

Create `frontend/src/features/sheet/components/SharePostButton.tsx`:

```tsx
import { Share2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import { shareElementAsImage } from '../../../lib/share';
import { segmentsText } from '../../insights/segments';
import { sheetPostFilename } from '../../share/filenames';
import type { SheetPost } from '../api';
import { PostShareCard } from './PostShareCard';

/**
 * Shares one post as a branded image (lib/share: the Web Share API, else a download). The card is
 * rendered off screen only while the image is made.
 */
export function SharePostButton({ post, date }: { post: SheetPost; date: string }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [rendering, setRendering] = useState(false);
  const [status, setStatus] = useState<'idle' | 'busy' | 'failed'>('idle');

  async function share() {
    setStatus('busy');
    flushSync(() => setRendering(true));
    try {
      const card = cardRef.current;
      if (card === null) throw new Error('The share card did not render');
      await shareElementAsImage(card, sheetPostFilename(date, segmentsText(post.headline)));
      setStatus('idle');
    } catch {
      setStatus('failed');
    } finally {
      setRendering(false);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Share image"
        onClick={() => void share()}
        disabled={status === 'busy'}
        className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button px-3 text-sm text-text-muted hover:text-text disabled:opacity-60"
      >
        <Share2 aria-hidden="true" className="size-4" />
        Share
      </button>
      {status === 'failed' && (
        <span role="alert" className="text-sm text-text-muted">
          Could not create the image.
        </span>
      )}
      {rendering &&
        createPortal(
          <div aria-hidden="true" className="pointer-events-none fixed top-0 left-[-10000px]">
            <div ref={cardRef}>
              <PostShareCard post={post} date={date} />
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
```

Create `frontend/src/features/sheet/components/ShareSheetButton.tsx`:

```tsx
import { Link2 } from 'lucide-react';
import { useState } from 'react';
import { shareLink } from '../../../lib/share';
import { formatDay, formatScore } from '../../home/format';
import type { SheetIssue } from '../api';

const MESSAGES = { idle: '', copied: 'Link copied.', failed: 'Could not share the link.' } as const;

/** "The Sunday Sheet, Sep 27, 2026: 23 shooters, field median 39, top score 49, 13 trophies." */
export function sheetShareText(issue: SheetIssue): string {
  const n = issue.numbers;
  const shooters = `${String(n.shooters)} ${n.shooters === 1 ? 'shooter' : 'shooters'}`;
  return (
    `The Sunday Sheet, ${formatDay(issue.masthead.date)}: ${shooters}, ` +
    `field median ${formatScore(n.median)}, top score ${formatScore(n.top_score)}, ` +
    `${String(n.trophies)} ${n.trophies === 1 ? 'trophy' : 'trophies'}.`
  );
}

/**
 * Shares this issue's `/sheet/{date}` link with the four numbers as text (the site stays behind
 * its password, so there is no preview image), or copies them when the browser cannot share.
 */
export function ShareSheetButton({ issue }: { issue: SheetIssue }) {
  const [status, setStatus] = useState<keyof typeof MESSAGES>('idle');
  async function share() {
    const url = new URL(`/sheet/${issue.masthead.date}`, window.location.origin).toString();
    try {
      const outcome = await shareLink({
        title: 'The Sunday Sheet',
        text: sheetShareText(issue),
        url,
      });
      setStatus(outcome === 'copied' ? 'copied' : 'idle');
    } catch {
      setStatus('failed');
    }
  }
  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void share()}
        className="inline-flex min-h-11 items-center gap-2 rounded-button px-2 underline underline-offset-2"
      >
        <Link2 aria-hidden="true" className="size-4" />
        Share this Sheet
      </button>
      {/* A polite live line, not role="status": pages wait for "no status left" to be settled. */}
      <span aria-live="polite" className="text-sm text-text-muted">
        {MESSAGES[status]}
      </span>
    </span>
  );
}
```

In `frontend/src/features/sheet/components/PostCard.tsx`, replace:

```tsx
import { sheetExplainers } from '../explainers';
import { BumpButton } from './BumpButton';

export const TYPE_LABELS: Record<SheetPostType, string> = {
```

with:

```tsx
import { sheetExplainers } from '../explainers';
import { BumpButton } from './BumpButton';
import { SeeWhy } from './SeeWhy';
import { SharePostButton } from './SharePostButton';

export const TYPE_LABELS: Record<SheetPostType, string> = {
```

In `frontend/src/features/sheet/components/PostCard.tsx`, replace:

```tsx
/**
 * One post: its type, a "New" tag, its headline (names link to profiles), trophy art and everyone
 * who earned a trophy, the bump button, any extra charts and "How we worked it
 * out" (an insight's own explainer, or the "On this day" one). The viewer's own single-shooter
 * insight reads in the second person.
```

with:

```tsx
/**
 * One post: its type, a "New" tag, its headline (names link to profiles), trophy art and everyone
 * who earned a trophy, the bump button, "See why →", any extra charts, Share and "How we worked it
 * out" (an insight's own explainer, or the "On this day" one). The viewer's own single-shooter
 * insight reads in the second person.
```

In `frontend/src/features/sheet/components/PostCard.tsx`, replace:

```tsx
          noteId={noteId}
        />
        {insight !== null && <AlsoLinks insight={insight} you={you} />}
        {explained && (
          <ExplainerToggle
```

with:

```tsx
          noteId={noteId}
        />
        <SeeWhy post={post} />
        {insight !== null && <AlsoLinks insight={insight} you={you} />}
        <SharePostButton post={post} date={date} />
        {explained && (
          <ExplainerToggle
```

In `frontend/src/features/sheet/components/Masthead.tsx`, replace:

```tsx
import { formatDay } from '../../home/format';
import type { SheetIssue } from '../api';

const LINK = 'inline-flex min-h-11 items-center rounded-button px-2 underline underline-offset-2';
```

with:

```tsx
import { formatDay } from '../../home/format';
import type { SheetIssue } from '../api';
import { ShareSheetButton } from './ShareSheetButton';

const LINK = 'inline-flex min-h-11 items-center rounded-button px-2 underline underline-offset-2';
```

In `frontend/src/features/sheet/components/Masthead.tsx`, replace:

```tsx
          All issues
        </Link>
      </nav>
      {newer !== null && <NewerSunday newer={newer} />}
```

with:

```tsx
          All issues
        </Link>
        <ShareSheetButton issue={issue} />
      </nav>
      {newer !== null && <NewerSunday newer={newer} />}
```

- [ ] **Step 9: Run the tests and make sure they pass**

Run: `cd frontend && pnpm exec vitest run src/features/sheet src/lib`

Expected: all pass.

- [ ] **Step 10: Commit**

From the worktree root:

```bash
git add frontend/src/features/sheet/components/SeeWhy.test.tsx frontend/src/features/sheet/components/SharePostButton.test.tsx frontend/src/features/sheet/components/ShareSheetButton.test.tsx frontend/src/features/sheet/components/SeeWhy.tsx frontend/src/features/sheet/components/PostShareCard.tsx frontend/src/features/sheet/components/SharePostButton.tsx frontend/src/features/sheet/components/ShareSheetButton.tsx frontend/src/features/sheet/components/PostCard.tsx frontend/src/features/sheet/components/Masthead.tsx
git commit -m 'feat(sheet): "See why", post share images and "Share this Sheet"' -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 10.3 Gates

- [ ] **Step 11: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm typecheck && pnpm exec prettier --check .`

Expected: no output from eslint, tsc exits 0, "All matched files use Prettier code style!"

Run: `cd frontend && pnpm test --coverage`

Expected: the whole suite passes; lines and branches stay at or above the ratchet

Fix anything they flag in a follow-up commit with the same trailer.

---

### Task 11: The full e2e pass

**Wave 6** · parallel with: none (Wave 6 is this task alone) · branch `task/14-11-sheet-e2e` (cut from `feat/sunday-sheet`, PR into `feat/sunday-sheet`)

The behaviour exists after Tasks 1–10, so this task adds verification only. If a test here fails, the bug is in the task that owns that behaviour: fix it there (a follow-up commit on this branch is fine) and say which task it was in the PR.

**Files:**
- Create: `frontend/e2e/sheet.spec.ts`

**Interfaces:**
- Consumes:
  - Everything above, through the running stack; `e2e/fixtures` `test`, `expect`; `e2e/layout` `whenSettled`, `expectNoSideScroll`, `expectTapTargets`, `expectTitlesUntruncated`; `e2e/window` `longDate`.
- Produces:
  - `e2e/sheet.spec.ts`: the spec's e2e list at both viewports. `/` shows the Sheet with no layout shift after load (summed `layout-shift` entries < 0.05, with and without a "me"). Phone stacking order and the desktop rail. Previous / next / All issues. A bump that counts at once, survives a reload and reverts. "See why" rings its chart. Share downloads a PNG on desktop. "Which one are you?" pick, "Not me", and a skip that sticks.

#### 11.1 The Sheet end to end

- [ ] **Step 1: Write the specs**

Build and start the stack from this branch first (see "Running the e2e stack"). The tests read their expectations from the API at run time. The bump test uses a different post on each project, because both projects share one stack.

Create `frontend/e2e/sheet.spec.ts`:

```ts
import { readFile } from 'node:fs/promises';

import type { Page } from '@playwright/test';

import { expect, test } from './fixtures';
import {
  expectNoSideScroll,
  expectTapTargets,
  expectTitlesUntruncated,
  whenSettled,
} from './layout';
import { longDate } from './window';

/** The Sunday Sheet end to end (Plan 14). Expectations come from the API at run time. */

interface Chart {
  type: 'explorer' | 'page';
  route: string | null;
  anchor: string | null;
  window: { from: string; to: string };
  highlight: Record<string, unknown[] | null>;
}
interface Post {
  post_key: string;
  type: string;
  see_why: { kind: 'chart' | 'link'; label: string; chart?: Chart | null; href?: string | null };
}
interface Issue {
  masthead: { date: string; issue: number; previous: string | null; next: string | null };
  numbers: { shooters: number; median: number | null; top_score: number | null; trophies: number };
  posts: Post[];
  more: { posts: Post[] }[];
}

async function getJson<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(path);
  expect(response.ok(), path).toBe(true);
  return (await response.json()) as T;
}

/** Sum of layout shifts not caused by input, from the page's first paint (CLS without windows). */
async function trackLayoutShift(page: Page): Promise<() => Promise<number>> {
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
  return () => page.evaluate(() => (window as unknown as { __shift: number }).__shift);
}

const BLOCKS = ['masthead', 'numbers', 'you', 'lead', 'feed', 'more', 'next', 'pulse', 'details'];

test('/ is the latest issue: masthead, the four numbers, and nothing jumps once it loads', async ({
  page,
}) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  const shift = await trackLayoutShift(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await expect(
    page.getByText(`${longDate(issue.masthead.date)} · Issue ${String(issue.masthead.issue)}`),
  ).toBeVisible();
  const numbers = page.getByRole('region', { name: 'This Sunday in numbers' });
  await expect(numbers.getByText(String(issue.numbers.shooters), { exact: true })).toBeVisible();
  await expect(numbers.getByText(String(issue.numbers.trophies), { exact: true })).toBeVisible();
  await whenSettled(page);
  expect(await shift(), 'layout shift after load').toBeLessThan(0.05);
  await expectNoSideScroll(page);
  await expectTitlesUntruncated(page);
  await expectTapTargets(page);
});

test('nothing jumps for a returning shooter either', async ({ page }) => {
  const shooters = await getJson<{ shooter_id: number; display_name: string }[]>(
    page,
    '/api/shooters?q=Hadley',
  );
  const hadley = shooters.find((s) => s.display_name === 'Hadley, Ike');
  await page.addInitScript((id) => localStorage.setItem('sc.me', String(id)), hadley?.shooter_id);
  const shift = await trackLayoutShift(page);
  await page.goto('/');
  await expect(
    page.getByRole('region', { name: 'Your Sunday' }).getByText('Last out'),
  ).toBeVisible();
  await whenSettled(page);
  expect(await shift(), 'layout shift after load').toBeLessThan(0.05);
});

test('a phone stacks the blocks in Sheet order; a desktop puts the rail beside the feed', async ({
  page,
}, testInfo) => {
  await page.goto('/');
  await whenSettled(page);
  const tops: Record<string, { x: number; y: number }> = {};
  for (const name of BLOCKS) {
    const box = await page.locator(`[data-sheet-block="${name}"]`).boundingBox();
    if (box !== null) tops[name] = { x: box.x, y: box.y };
  }
  const present = BLOCKS.filter((name) => name in tops);
  expect(present).toEqual(expect.arrayContaining(['masthead', 'numbers', 'you', 'feed', 'pulse']));
  if (testInfo.project.name === 'mobile') {
    const ys = present.map((name) => tops[name]?.y ?? 0);
    expect(ys).toEqual([...ys].sort((a, b) => a - b));
  } else {
    expect(tops['you']?.x ?? 0).toBeGreaterThan(tops['feed']?.x ?? 0);
    expect(tops['you']?.y ?? 0).toBeLessThan((tops['feed']?.y ?? 0) + 1);
  }
});

test('previous and next issue links walk the issues', async ({ page }) => {
  const latest = await getJson<Issue>(page, '/api/sheet/latest');
  const previous = latest.masthead.previous;
  if (previous === null) throw new Error('the fx world has more than one held Sunday');
  await page.goto('/');
  await page.getByRole('link', { name: '← Previous issue' }).click();
  await expect(page).toHaveURL(new RegExp(`/sheet/${previous}$`));
  await expect(
    page.getByText(`${longDate(previous)} · Issue ${String(latest.masthead.issue - 1)}`),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Next issue →' }).click();
  await expect(page).toHaveURL(new RegExp(`/sheet/${latest.masthead.date}$`));
  await expect(page.getByRole('link', { name: 'Next issue →' })).toHaveCount(0);
  await page.getByRole('link', { name: 'All issues' }).click();
  await expect(page).toHaveURL(/\/events$/);
});

test('a bump counts at once, survives a reload and can be taken back', async ({
  page,
}, testInfo) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  // The two projects share one stack: each bumps its own post, so the counts never collide.
  const post = issue.posts[testInfo.project.name === 'mobile' ? 1 : 0];
  if (post === undefined) throw new Error('the latest issue has at least two posts');
  await page.goto('/');
  const button = page
    .locator(`[data-post-key="${post.post_key}"]`)
    .getByRole('button', { name: /^Fist bump/ });
  await expect(button).toHaveAttribute('aria-pressed', 'false');
  const before = Number(/(\d+)/.exec((await button.getAttribute('aria-label')) ?? '')?.[1]);
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before + 1)} bump`));
  await page.reload();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before + 1)} bump`));
  await button.click();
  await expect(button).toHaveAttribute('aria-pressed', 'false');
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before)} bump`));
  await page.reload();
  await expect(button).toHaveAccessibleName(new RegExp(`^Fist bump, ${String(before)} bump`));
});

test('"See why" opens a post’s chart and rings the evidence', async ({ page }) => {
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  const post = issue.posts.find((p) => {
    const chart = p.see_why.chart;
    return (
      chart != null &&
      chart.type === 'page' &&
      (chart.route ?? '').startsWith('/shooters/') &&
      Object.values(chart.highlight).some((items) => (items ?? []).length > 0)
    );
  });
  if (post === undefined) throw new Error('the fx world has a feed post with a profile chart');
  const chart = post.see_why.chart as Chart;
  await page.goto('/');
  await page
    .locator(`[data-post-key="${post.post_key}"]`)
    .getByRole('link', { name: /^See why/ })
    .click();
  await expect(page).toHaveURL(new RegExp(`#chart-${chart.anchor ?? ''}$`));
  const target = page.locator(`#chart-${chart.anchor ?? ''}`);
  await expect(target).toBeVisible();
  const chip = target.locator('[data-marked]');
  await expect(chip).toContainText('Showing what the insight points to.');
  await expect(chip).not.toHaveAttribute('data-marked', '0');
  await whenSettled(page);
  await expectNoSideScroll(page);
});

test('Share on a post downloads its image on desktop', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'a phone hands the image to the share sheet');
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
    Object.defineProperty(navigator, 'canShare', { value: undefined, configurable: true });
  });
  const issue = await getJson<Issue>(page, '/api/sheet/latest');
  const post = issue.posts[0];
  if (post === undefined) throw new Error('the latest issue has posts');
  await page.goto('/');
  const pending = page.waitForEvent('download');
  await page
    .locator(`[data-post-key="${post.post_key}"]`)
    .getByRole('button', { name: 'Share image' })
    .click();
  const file = await pending;
  expect(file.suggestedFilename()).toMatch(
    new RegExp(`^sunday-sheet-${issue.masthead.date}-[a-z0-9-]+\\.png$`),
  );
  const bytes = await readFile(await file.path());
  expect([...bytes.subarray(0, 4)]).toEqual([0x89, 0x50, 0x4e, 0x47]);
});

test('"Which one are you?" fills Your Sunday, "Not me" asks again, and skip sticks', async ({
  page,
}) => {
  await page.goto('/');
  const ask = page.getByRole('region', { name: 'Which one are you?' });
  await ask.getByLabel('Your name').fill('Hadley');
  await ask.getByRole('button', { name: 'Hadley, Ike' }).click();
  const you = page.getByRole('region', { name: 'Your Sunday' });
  await expect(you.getByText('Last out')).toBeVisible();
  await you.getByRole('button', { name: 'Not me' }).click();
  await expect(ask).toBeVisible();
  await ask.getByRole('button', { name: 'Not a shooter / skip' }).click();
  await expect(ask).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: 'The Sunday Sheet' })).toBeVisible();
  await whenSettled(page);
  await expect(page.getByRole('region', { name: 'Which one are you?' })).toHaveCount(0);
});
```

- [ ] **Step 2: Run them on a stack built from this branch**

Run: `cd frontend && E2E_BASE_URL=http://localhost:18080 E2E_VIEWER_PASSWORD=e2e-viewer E2E_ADMIN_PASSWORD=e2e-admin pnpm exec playwright test e2e/sheet.spec.ts`

Expected: 17 passed and 1 skipped (Share is desktop-only), plus the 2 setup steps. Then run the whole suite (`pnpm exec playwright test`): everything passes except Decision 27's known mobile `window-labels` failure, which is unrelated.

- [ ] **Step 3: Commit**

From the worktree root:

```bash
git add frontend/e2e/sheet.spec.ts
git commit -m "test(e2e): the Sunday Sheet end to end at both viewports" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

#### 11.2 Gates

- [ ] **Step 4: Run the gates before handing the branch back**

Run: `cd frontend && pnpm lint && pnpm exec prettier --check e2e`

Expected: clean

Fix anything they flag in a follow-up commit with the same trailer.

---

## Self-review

**1. Spec coverage.** Every requirement in the spec, and the task that meets it:

| Spec | Task(s) |
|---|---|
| `/` is the latest scored Sunday's Sheet; `/sheet/:date` any Sunday's; "All issues" opens the events calendar; the Home route retires | 9 (index, nav), 4 (`/sheet/:date`, masthead links, "Newer Sunday" note), 2 (`masthead.newer`), Decision 1 |
| Order 1–10 (masthead, four numbers, Your Sunday, headline, spotlight, feed, More, Next Sunday, Club pulse, Latest Sunday details) and the ≥ 1024 px main + rail layout | 4 (masthead, numbers, feed, More), 5 (headline, spotlight), 8 (rail, `SHEET_ORDER`, layout), 11 (e2e order at 390 px, rail beside the feed at 1440 px) |
| Masthead: "THE SUNDAY SHEET", date, issue N, previous / next / All issues | 2 (`number`, neighbours), 4 (`Masthead`), 11 (walk) |
| Four numbers from the Latest Sunday card | 2 (`SheetNumbersOut`), 4 (`Numbers`), Decision 9 |
| Loading placeholders reserve space; no layout shift | 4 (`SheetSkeleton`, one status), 11 (summed layout shift < 0.05, with and without a "me") |
| No date control, and cards say "not affected by the time filter" | 8 (`ROUND_TYPE_ONLY`, Club pulse fixed window), 4 (feed subtitle "All round types · not affected by the filters") and 5 ("Top story" subtitle, dated when the pick is about an earlier Sunday), 9 (e2e "shows the round-type filter and no time window") |
| Post types ①–⑥, sources and `post_key`s; feed order by rank with no type more than twice in a row; "More from this Sunday" | 2 (`KIND_TYPES` checked against the spec's ids written out, `FRESH_EVERGREEN`, trophy and OTD posts incl. attendance-only look-backs, `interleave` with one post of every present type, `group_more`), 4 (holder list, OTD explainer), Decisions 2–4, 7, 8, 10 |
| A post carries type, headline, named shooter links, `see_why`, `bumps` / `bumped` | 2 (`SheetPostOut`), 4 (`PostCard`: `Segments` links, every trophy holder linked, counts, and from Home's `InsightCard` the New tag, `chart.also` links and "How we worked it out"), 10 (`SeeWhy`), Decision 22 |
| `GET /api/sheet/{date}` and `/latest` (viewer), body cached by `data_version` | 2 (`build_issue` and `sheet_body` memoized, ETag middleware) |
| Bump counts not in the cached body; `GET …/bumps?device_id=` | 3, plus the ETag rule (Decision 13) |
| `POST` / `DELETE /api/sheet/bumps`: idempotent, 400 / 404 / 429 | 3 (`parse_device_id`, `resolves`, `bumps_limited`) |
| `DELETE /api/admin/sheet/bumps/{post_key}`: admin, audited, on the ops page | 3 (route, `sheet.wipe_bumps`), 7 (`BumpsPanel`), Decision 14 |
| `fist_bumps` table in a new migration; durable; stale keys kept, not shown; 120 per IP per 10 min in `bump_attempts`, pruned inline | 1 (`0006`, store, limiter), 3 (stale keys hidden; refused actions count) |
| `lib/device.ts` random UUID; storage unavailable: counts show, buttons off, "Bumps need this browser to remember you" | 4 (`device.ts`, `BumpButton`, `Feed` note), Decision 19 |
| "Which one are you?": name search, "Not a shooter / skip", pick via `lib/me.ts`, skip hides it, "Not me" clears; no modal | 6 (`WhichOneAreYou`, skip), 8 (`YourSunday`, "Not me", page flow), 11 (e2e), Decision 20 |
| 🤜🤛: tap updates at once, rollback with "Couldn't send that bump", tap again takes it back, nobody shown, own posts bumpable | 4 (`useBumpToggle`, `BumpButton`), Decision 21 |
| Post Share (html-to-image, Web Share API or download; masthead strip, headline, chart snippet) | 10 (`PostShareCard`, `SharePostButton`), Decision 23 |
| "Share this Sheet": `/sheet/{date}` link with the four numbers as text | 10 (`ShareSheetButton`, `shareLink`), Decision 24 |
| "See why →" reuses the chart-target mechanism (opens, scrolls, rings) | 10 (`SeeWhy` via `chartHref`), 11 (e2e ring check) |
| Every Home piece finds a place (the ten-row table) | 2 (posts incl. Home's evergreen rows, OTD with attendance-only look-backs, the newer-Sunday note), 4 (numbers, insight-card extras on every post), 5 (headline, deck, spotlight), 8 (Your Sunday, next trophy, Next Sunday, Club pulse and turnout, details link), 8 test "keeps every former Home piece" |
| `homeWidget` registry re-pointed: `hero` → lead, `main` → rail cards, `me` → Your Sunday | 8 (`HomeWidgetProps`, `WidgetSlot`, insights lead widget), Decision 16 |
| Backend tests (assembly on 2026-09-27, keys resolve, positive-only, numbering, bump behaviour, durability, never cached) | 1, 2, 3 |
| Frontend tests (loading / empty / error, phone order, optimistic and rollback, storage blocked, which-one flow, Table and CSV on every chart, every former Home chart present) | 4, 6, 8 |
| e2e at both viewports (`/` with no layout shift, previous / next, bump and revert, "See why" rings, Share downloads on desktop) | 11, with 9 moving the Home specs |
| Delivery: integration branch, PRs into it, owner preview, final PR on say-so | header "Delivery", Waves |

No requirement is left without a task.

**2. Placeholder scan.** The plan was searched for "TBD", "TODO", "implement later", "fill in", "add appropriate", "handle edge cases", "similar to Task" and "write tests for". There are no hits. Every code step carries the complete code, and every Modify step quotes the exact block it replaces.

**3. Type and name consistency.** The plan's blocks were generated from, and replayed against, one tree. Names line up across tasks, and `mypy --strict`, `tsc --noEmit` and the test suites passed after every task in replay order (1, 2, 3, 5, 6, 4, 7, 10, 8, 9, 11). These names were checked in particular: `post_key` / `postKey`, `bumps` / `bumped`, `see_why.kind` (`chart` | `link`), `masthead.{date, issue, previous, next, latest, newer}`, `SheetLead`'s `date` prop (Task 5 defines it, Task 8's `homeWidget` passes `issue.masthead.date`), `HEADLINE_NAMES` = `NAMES_SHOWN` = 3, `HomeWidgetProps.issue`, `SHEET_ORDER` keys (`masthead, numbers, you, lead, feed, more, next, pulse, details`) and `data-sheet-block`, `sc.device` / `sc.me` / `sc.me.skip`, and the error codes `sheet_not_found`, `post_not_found`, `bad_device_id`, `rate_limited`.

**Waves after the revision.** File sets are still disjoint within each wave: the revision touched Task 2 (`analytics/sheet.py`, `api/routes/sheet.py` and their tests), Task 4 (`PostCard`, `Masthead`, `Feed`, `explainers`, `mocks`, `SheetPage.test`), Task 5 (`SheetLead` and its test) and Task 8 (`insights/homeWidget.tsx`), and no file moved between tasks. Wave 1 (1, 2, 5, 6), Wave 3 (4, 7) and Wave 4 (8, 10) share no file; Task 10 still edits only `PostCard`/`Masthead` internals that Task 4 created, after Wave 3.

**4. Review focus.** The five items above are each pinned to named tests in their owning tasks, and those tests ran in the replay. Two items were checked and are already covered by the spec's own tests, so they are not listed. Negative named posts are covered by `test_named_posts_are_positive_or_neutral_only` and `test_named_shooter_posts_are_positive_or_neutral`. Phone order is covered by the Task 8 unit test and the Task 11 e2e test.

**5. Replay record.** Before the review, Tasks 1, 2, 3, 5 and 6 were replayed block by block in replay order on a fresh worktree; every red step failed and every green step passed as the plan says, apart from a blank line at the end of Task 2's `sheet.py` that `ruff format --check` rejected, now fixed. After the review revision, the rendered plan text was applied in replay order to a fresh worktree on `7b65f55`, and the result is file-for-file identical to the validated tree. The Task 2 state passed the backend gates and its tests (75 passed). The Task 4 state, after Tasks 3, 5 and 6, passed the frontend gates and the sheet, insights, lib and app tests (326 passed). The Task 10 state, after Task 7, passed lint, typecheck and the sheet and admin-ops tests.
